# -*- coding: utf-8 -*-
"""Adapter quan sát audfprint mà không sửa source vendored.

Wrapper thêm JSON event cho từng clip và phát clip cho worker theo RAM (D-31). Thuật toán Analyzer,
HashTable, tham số CLI và format ``.pklz`` vẫn do audfprint vendored thực hiện.
"""

from __future__ import annotations

import gzip
import json
import os
import pickle
import shutil
import sys
import tempfile
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


PREFIX = "TIMCLIP_FINGERPRINT_EVENT "

# Thời gian tối đa một worker được phép IM LẶNG — tức là chưa trả lời việc đang giữ (một clip,
# hoặc lệnh ghi bảng hash cuối lượt). ĐÂY KHÔNG PHẢI ngân sách cho tổng phần việc của worker.
#
# Sự cố 2026-09-07: bản đầu dùng hằng số này làm hạn cho TOÀN BỘ danh sách của worker, kho 1178
# clip bị giết ở 94,8% trong lúc cả 8 worker đều khoẻ (mất ~7 giờ CPU). Nay cha phát từng clip nên
# hạn tính lại từ mỗi lần giao: worker chạy 3 tiếng vẫn an toàn miễn là nó còn trả lời, worker kẹt
# thật vẫn bị bắt trong thời gian có giới hạn. Clip 1 giờ mất ~25 giây ⇒ clip 18,2 giờ ~8 phút.
CHO_WORKER_S = 1800.0

# RAM đỉnh một worker cần (đo 06/11/2026, `--shifts 4`, docs/PHAN_TICH_TAI_DUNG_KHO_2026-11.md): clip
# 1 giờ 1,35 GB, 3 giờ 4,27 GB — audfprint nạp trọn audio rồi tính phổ nên tăng tuyến tính.
CAN_RAM_GB_MOI_GIO = 1.5
CAN_RAM_TOI_THIEU_GB = 0.7      # tiến trình Python + bảng hash ~419 MB
BYTE_MOI_GIAY_OPUS = 8000       # opus 64 kbps của kho do tool tải về
# Dưới ngưỡng này clip chỉ cỡ 30 phút: tính theo dung lượng là đủ, khỏi chạy ffprobe hàng trăm lần.
NGUONG_DO_THAT_BYTE = 15 * 10**6
# Không còn clip nào chạy mà RAM vẫn thiếu: clip dài chờ chừng này giây rồi bị bỏ qua; clip ngắn
# chờ tới CHO_WORKER_S, vì RAM tụt giữa lượt không đáng để bỏ mấy trăm clip còn lại.
CHO_RAM_S = 60.0

# Nhịp poll ngắn của cha. Đừng hạ xuống dưới ~0,1 s: mỗi `wait()` trên Windows mở rồi
# huỷ một overlapped ReadFile. Không ảnh hưởng tốc độ phát hiện worker chết — pipe gãy
# được xếp là "ready" nên EOF vẫn nổi lên tức thì.
NHIP_KIEM_S = 0.5

# Thư mục đặt bảng hash tạm của các worker (``timclip_ht_*``). ``main()`` đặt nó = thư mục
# chứa ``--dbase`` — với engine đó là bản làm việc ``data/fingerprint_jobs/<job>``, được dọn
# cùng job (kể cả khi Dừng: terminate bỏ qua ``finally`` của runner) và bị ``dondep``/Watch thu
# hồi nếu crash. Không đặt → %TEMP% hệ thống như cũ, chỉ cho lối gọi trực tiếp (audit C-7).
BIEN_THU_MUC_BANG_TAM = "TIMCLIP_THU_MUC_BANG_TAM"


def _thu_muc_bang_tam():
    """Thư mục cha cho ``tempfile.mkdtemp`` của bảng hash; ``None`` = %TEMP% hệ thống."""
    thu_muc = os.environ.get(BIEN_THU_MUC_BANG_TAM, "")
    return thu_muc if thu_muc and os.path.isdir(thu_muc) else None


def _dbase_trong_lenh(tham_so: list):
    """Giá trị ``--dbase``/``-d`` trong dòng lệnh audfprint; không có → ``None``."""
    for i, muc in enumerate(tham_so):
        if muc in ("--dbase", "-d") and i + 1 < len(tham_so):
            return tham_so[i + 1]
        if muc.startswith("--dbase="):
            return muc.split("=", 1)[1]
    return None


def _emit(event: str, **payload) -> None:
    """Ghi một dòng event bằng ĐÚNG MỘT syscall.

    Tới 8 tiến trình con cùng ghi vào một pipe stdout. ``print()`` có thể tách
    thành nhiều lần ghi, hai dòng lồng vào nhau và engine mất event (đã quan sát:
    7/8 event thay vì 8/8). Một ``os.write`` cho dòng dưới 4 KB là nguyên tử trên
    cả Windows lẫn POSIX.
    """
    dong = PREFIX + json.dumps({"event": event, **payload}, ensure_ascii=False) + "\n"
    du_lieu = dong.encode("utf-8", errors="replace")
    try:
        sys.stdout.flush()          # giữ đúng thứ tự với output của audfprint
        os.write(sys.stdout.fileno(), du_lieu)
    except (OSError, ValueError):
        # stdout đã đóng (job bị hủy) — mất một dòng log không được làm chết worker.
        pass


@dataclass(frozen=True)
class Clip:
    file: str
    can_gb: float


def _ram_trong_gb() -> float:
    import psutil

    return psutil.virtual_memory().available / 2**30


def _du_phong_ram_gb() -> float:
    """Phần RAM luôn chừa cho Windows và ứng dụng khác."""
    import psutil

    return max(2.0, 0.1 * psutil.virtual_memory().total / 2**30)


def _do_dai_giay(path: str) -> float | None:
    """Thời lượng đo bằng ffprobe; không đo được thì ``None`` để lùi về dung lượng."""
    from process_runner import chay_lenh_media

    try:
        kq = chay_lenh_media(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", path], tran_tong_s=30.0)
        return float(kq.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001 - thiếu thời lượng chính xác không được làm hỏng build
        return None


def uoc_luong_ram_gb(path: str) -> float:
    """RAM đỉnh một worker cần cho clip này, theo thời lượng (mp4 lớn có thể chỉ dài vài phút)."""
    try:
        byte = os.path.getsize(path)
    except OSError:
        return CAN_RAM_TOI_THIEU_GB
    giay = _do_dai_giay(path) if byte >= NGUONG_DO_THAT_BYTE else None
    giay = giay or byte / BYTE_MOI_GIAY_OPUS
    return max(CAN_RAM_TOI_THIEU_GB, CAN_RAM_GB_MOI_GIO * giay / 3600)


def xep_thu_tu(clips: list, phan_moi_worker_gb: float) -> list:
    """Clip vừa phần RAM của một worker giữ nguyên thứ tự; clip lớn hơn xếp sau, nhỏ trước lớn."""
    return ([c for c in clips if c.can_gb <= phan_moi_worker_gb]
            + sorted((c for c in clips if c.can_gb > phan_moi_worker_gb), key=lambda c: c.can_gb))


class LichTheoRam:
    """Chính sách phát clip cho worker. Thuần logic: RAM và đồng hồ do nơi gọi đưa vào để mô phỏng được.

    Bất biến: một clip chỉ được phát khi RAM trống đủ cho nó CỘNG phần các clip đang chạy còn sẽ chiếm,
    sau khi đã chừa dự phòng. Hàng là FIFO: clip đầu hàng chưa vừa thì chờ, vì phía sau chỉ có
    clip bằng hoặc lớn hơn nó (đoạn clip dài) hoặc clip ngắn sẽ vừa ngay khi RAM trống lại.
    """

    def __init__(self, clips: list, ram_trong_gb: float, du_phong_gb: float, ncores: int):
        self.du_phong_gb = du_phong_gb
        ngan_sach = max(0.0, ram_trong_gb - du_phong_gb)
        self.phan_moi_worker = max(CAN_RAM_TOI_THIEU_GB, ngan_sach / max(1, ncores))
        self.hang = deque(xep_thu_tu(clips, self.phan_moi_worker))
        self.thu_lai: list = []
        self.dang_thu_lai = False
        self.cho_ram_tu: float | None = None
        self.thua_worker = False        # worker rảnh nên nghỉ để nhả RAM

    @property
    def xong(self) -> bool:
        return not self.hang and not self.thu_lai

    def buoc(self, ram_trong_gb: float, con_phai_chua_gb: float, so_dang_chay: int, bay_gio: float):
        """Việc tiếp theo: ``("giao"|"bo"|"cho", clip)``, hoặc ``None`` = chờ kết quả clip đang chạy."""
        if not self.hang and self.thu_lai and not so_dang_chay:
            self.hang, self.thu_lai, self.dang_thu_lai = deque(self.thu_lai), [], True
        if not self.hang or (self.dang_thu_lai and so_dang_chay):
            self.thua_worker = True
            return None
        clip = self.hang[0]
        # Chạy một mình chỉ giữ nửa dự phòng: máy ít RAM thì dựng chậm từng clip, không bỏ cả kho.
        giu_lai = self.du_phong_gb if so_dang_chay else self.du_phong_gb / 2
        if ram_trong_gb - con_phai_chua_gb - clip.can_gb >= giu_lai:
            self.cho_ram_tu, self.thua_worker = None, False
            return "giao", self.hang.popleft()
        clip_dai = clip.can_gb > self.phan_moi_worker
        self.thua_worker = clip_dai or not so_dang_chay
        if so_dang_chay:
            return None
        if self.cho_ram_tu is None:
            self.cho_ram_tu = bay_gio
            return "cho", clip
        # Không đặt lại mốc khi bỏ: máy hết RAM thì không chờ lại 60 giây cho từng clip.
        han_cho = CHO_RAM_S if clip_dai else CHO_WORKER_S
        return ("bo", self.hang.popleft()) if bay_gio - self.cho_ram_tu >= han_cho else None

    def ghi_loi(self, clip: Clip) -> bool:
        """Clip lỗi đọc/thiếu RAM: ``True`` = thử lại một mình cuối lượt, ``False`` = đã thử đủ."""
        if self.dang_thu_lai:
            return False
        self.thu_lai.append(clip)
        return True


# Lý do thật của lỗi giải mã: ``wavfile2peaks`` nuốt exception và chỉ in «Error reading», nên
# MemoryError và FFmpeg im quá 10 giây trông như nhau. Mỗi tiến trình một bản, xoá trước mỗi clip.
_LOI_GIAI_MA: dict = {}


def _mo_ta_loi(exc: BaseException) -> str:
    # ``audio_read.read_data`` ghép stderr dạng bytes bằng ``''.join`` nên FFmpeg treo lộ ra thành TypeError.
    if isinstance(exc, TypeError) and "expected str instance, bytes found" in str(exc):
        return "FFmpegTreo: FFmpeg không trả dữ liệu quá 10 giây (máy quá tải hoặc file đọc không được)"
    return f"{type(exc).__name__}: {str(exc)[:300]}"


def _xu_ly_clip(analyzer, ht, filename: str) -> dict:
    """Tạo vân tay một clip trong worker. ``{}`` = đã chốt kết quả, ``{"loi": ...}`` = chưa ghi gì.

    Clip lỗi không vào ``ht``: lần thử lại có thể rơi vào worker khác, ghi tên ở đây sẽ sinh hai bản
    ghi cho một clip (audit C-3). Clip lỗi hẳn vắng khỏi kho nên «Bổ sung» sau vẫn tự thử lại.
    """
    started = time.monotonic()
    _emit("clip_started", file=filename, phase="fingerprinting", process_pid=os.getpid())
    _LOI_GIAI_MA.clear()
    try:
        hashes = analyzer.wavfile2hashes(filename)
        loi = _LOI_GIAI_MA.get(filename)
    except Exception as exc:  # noqa: BLE001 - một clip hỏng không được kéo chết cả worker
        loi = _mo_ta_loi(exc)
    if loi:
        return {"loi": loi.replace(filename, os.path.basename(filename)),
                "giay": time.monotonic() - started}
    ht.store(filename, hashes)
    _emit(
        "clip_finished",
        file=filename,
        status="success" if len(hashes) else "failed",
        category="" if len(hashes) else "zero_hashes",
        message="" if len(hashes) else "Không tạo được hash từ audio.",
        hash_count=len(hashes),
        elapsed_seconds=time.monotonic() - started,
        process_pid=os.getpid(),
    )
    return {}


_DA_CAI_THEO_DOI_GIAI_MA = False


def cai_dat_theo_doi_giai_ma() -> None:
    """Phát phase ``decoding`` từ đúng nơi FFmpeg thực sự được gọi.

    Trước đây phase này chỉ được suy ra bằng cách *bắt gặp* tiến trình ffmpeg lúc
    lấy mẫu cây process. Với clip ngắn, ffmpeg chỉ sống vài chục mili giây nên bắt
    được hay không là may rủi — giao diện lúc hiện lúc không, và test thì flaky.

    ``audfprint_analyze.wavfile2peaks`` gọi ``audio_read.audio_read()``; bọc đúng
    hàm đó cho tín hiệu tất định. Không sửa code vendored, chỉ thay tham chiếu.

    Phải gọi trong **mỗi** tiến trình con vì Windows dùng spawn: bản vá ở tiến trình
    cha không đi theo sang con.
    """
    global _DA_CAI_THEO_DOI_GIAI_MA
    if _DA_CAI_THEO_DOI_GIAI_MA:
        return
    try:
        import audio_read
    except ImportError:
        return          # không có module thì giữ nguyên hành vi cũ, không làm chết job
    goc = audio_read.audio_read

    def audio_read_co_su_kien(*args, **kwargs):
        ten = str(args[0] if args else kwargs.get("filename") or "")
        _emit("clip_phase", file=ten, phase="decoding", process_pid=os.getpid())
        try:
            return goc(*args, **kwargs)
        except Exception as exc:
            _LOI_GIAI_MA[ten] = _mo_ta_loi(exc)
            raise
        finally:
            _emit("clip_phase", file=ten, phase="fingerprinting", process_pid=os.getpid())

    audio_read.audio_read = audio_read_co_su_kien
    _DA_CAI_THEO_DOI_GIAI_MA = True


def _worker_ghi_hash_table(analyzer, ket_noi, hashbits, depth, maxtime, duong_dan) -> None:
    """Chạy trong tiến trình con: nhận từng clip từ cha, khi được cho nghỉ thì GHI bảng hash RA FILE.

    Pipe chỉ mang tên clip và dict trạng thái nhỏ: bảng ~419 MB qua pipe chính là nguyên nhân treo cứng
    của bản vendored.
    """
    import hash_table

    cai_dat_theo_doi_giai_ma()      # spawn: bản vá của cha không đi theo sang con
    try:
        ht = hash_table.HashTable(hashbits=hashbits, depth=depth, maxtime=maxtime)
        while (filename := ket_noi.recv()) is not None:
            ket_noi.send(_xu_ly_clip(analyzer, ht, filename))
        with gzip.open(duong_dan, "wb", compresslevel=1) as fh:
            pickle.dump(ht, fh, protocol=pickle.HIGHEST_PROTOCOL)
        ket_noi.send({"ok": True})
    except BaseException as exc:  # noqa: BLE001 - phải báo về cha rồi mới chết
        try:
            ket_noi.send({
                "ok": False,
                "loi": f"{type(exc).__name__}: {str(exc)[:500]}",
            })
        except (BrokenPipeError, OSError):
            pass
        raise
    finally:
        try:
            ket_noi.close()
        except OSError:
            pass


def giai_phong_ban_ghi_rong(hash_tab, ten_moi) -> int:
    """Nhả mọi bản ghi 0 hash của ``hash_tab`` mang tên có trong ``ten_moi``; trả số ô đã nhả.

    Clip hỏng/im lặng vẫn được ghi TÊN với 0 hash (``--continue-on-error``) và được thử
    lại ở lần «Bổ sung» sau. Nhánh một nhân (``HashTable.store`` → ``name_to_id``) tái dùng
    đúng id cũ; nhánh đa nhân ``merge`` chỉ nối ``names`` không khử trùng, nên thiếu bước
    này clip có thêm một bản ghi mỗi lần thử lại — đếm clip sai, «Một video gốc chung» coi
    là trùng tên mãi mãi (audit C-3). Ô 0 hash không có giá trị nào trong bảng hash nên
    đặt ``None`` (ô trống, ``store`` sau này dùng lại được) là tương đương ``store``.
    Bản ghi CÓ hash không bị đụng: engine luôn gỡ chúng (``audfprint remove``) trước khi
    thêm lại.
    """
    can = {ten for ten in ten_moi or () if ten}
    so_hash = getattr(hash_tab, "hashesperid", None)
    if not can or so_hash is None or getattr(hash_tab, "names", None) is None:
        return 0
    da_nha = 0
    for i, ten in enumerate(hash_tab.names):
        if ten in can and i < len(so_hash) and int(so_hash[i]) == 0:
            hash_tab.names[i] = None
            da_nha += 1
    if da_nha:
        hash_tab.dirty = True
    return da_nha


@dataclass
class _Worker:
    so: int
    process: object
    ket_noi: object
    duong_dan: str
    so_xong: int = 0
    viec: Clip | None = None
    luc_giao: float = 0.0       # lần gửi gần nhất; watchdog tính từ mốc này
    rss_luc_giao: int = 0
    dang_nghi: bool = False


def _rss(w: _Worker) -> int:
    import psutil

    try:
        return psutil.Process(w.process.pid).memory_info().rss
    except psutil.Error:
        return w.rss_luc_giao


def _con_phai_chua_gb(ban: list) -> float:
    """Phần clip đang chạy CÒN sẽ chiếm; phần đã chiếm thì RAM trống đã phản ánh rồi."""
    return sum(max(0.0, w.viec.can_gb - max(0, _rss(w) - w.rss_luc_giao) / 2**30) for w in ban)


def _worker_chet(w: _Worker) -> RuntimeError:
    w.process.join(timeout=30)
    return RuntimeError(
        f"Worker vân tay {w.so} kết thúc bất thường "
        f"(exit code {w.process.exitcode}) mà không trả kết quả."
    )


def _gui(w: _Worker, thong_diep) -> None:
    w.luc_giao = time.monotonic()
    try:
        w.ket_noi.send(thong_diep)
    except OSError as exc:
        raise _worker_chet(w) from exc


def _phat_viec(lich: LichTheoRam, ranh: list, ban: list) -> None:
    """Phát clip cho worker rảnh tới khi RAM hoặc worker không còn đủ. Sửa ``ranh``/``ban`` tại chỗ."""
    while ranh:
        trong = _ram_trong_gb()
        buoc = lich.buoc(trong, _con_phai_chua_gb(ban), len(ban), time.monotonic())
        if buoc is None:
            return
        hanh_dong, clip = buoc
        ten = os.path.basename(clip.file)
        if hanh_dong == "giao":
            w = ranh.pop(0)
            w.viec, w.rss_luc_giao = clip, _rss(w)
            _gui(w, clip.file)
            ban.append(w)
        elif hanh_dong == "cho":
            _emit("thong_bao_ram", message=(
                f"{ten} cần khoảng {clip.can_gb:.0f} GB RAM, máy còn {trong:.1f} GB trống. "
                f"Chờ tối đa {CHO_RAM_S:.0f} giây, bạn đóng bớt ứng dụng để clip này được chạy."))
        else:
            _emit(
                "clip_finished",
                file=clip.file,
                status="failed",
                category="thieu_ram",
                message=(f"{ten}: cần khoảng {clip.can_gb:.0f} GB RAM nhưng máy chỉ còn {trong:.1f} GB "
                         "trống nên đã bỏ qua để không làm treo máy. Đóng bớt ứng dụng rồi bấm "
                         "«Bổ sung» để thử lại."),
                elapsed_seconds=0.0,
            )


def _nhan_ket_qua(w: _Worker, lich: LichTheoRam) -> bool:
    """Đọc một thông điệp của worker; ``True`` = worker đã ghi xong bảng hash."""
    try:
        kq = w.ket_noi.recv()
    except (EOFError, OSError) as exc:
        raise _worker_chet(w) from exc
    if "ok" in kq:
        if not kq["ok"]:
            raise RuntimeError(f"Worker vân tay {w.so} lỗi: {kq.get('loi') or 'không rõ'}")
        return True
    clip, w.viec = w.viec, None
    w.so_xong += 1
    loi = kq.get("loi")
    if not loi:
        return False
    if lich.ghi_loi(clip):
        _emit("clip_cho_thu_lai", file=clip.file, message=loi)
    else:
        _emit(
            "clip_finished",
            file=clip.file,
            status="failed",
            category=loi.split(":", 1)[0],
            message=f"{os.path.basename(clip.file)}: không tạo được vân tay sau 2 lần thử. {loi}",
            elapsed_seconds=kq.get("giay", 0.0),
        )
    return False


def _chet_khong_loi_nhan(w: _Worker) -> bool:
    """Windows: con chết trước khi nhận handle pipe thì cha không thấy EOF, phải hỏi trực tiếp tiến trình."""
    if w.process.is_alive():
        return False
    try:
        return not w.ket_noi.poll()     # còn thông điệp trong pipe: đọc nó ở vòng sau
    except OSError:
        return True


def _kiem_nhip(song: list) -> None:
    bay_gio = time.monotonic()
    for w in song:
        if _chet_khong_loi_nhan(w):
            raise _worker_chet(w)
        if (w.viec or w.dang_nghi) and bay_gio - w.luc_giao > CHO_WORKER_S:
            raise RuntimeError(
                f"Worker vân tay {w.so} không phản hồi sau {CHO_WORKER_S:.0f} giây "
                f"(đã xong {w.so_xong} file, không tiến thêm)."
            )


def _dieu_phoi(lich: LichTheoRam, workers: list) -> None:
    """Vòng phát việc của cha, chạy tới khi mọi worker đã ghi xong bảng hash."""
    from multiprocessing.connection import wait

    song = list(workers)
    while song:
        ban = [w for w in song if w.viec]
        ranh = [w for w in song if not w.viec and not w.dang_nghi]
        _phat_viec(lich, ranh, ban)
        if lich.xong and not ban:
            du = ranh
        elif lich.thua_worker:
            du = ranh[0 if ban else 1:]     # giữ một worker tới cuối lượt để còn thử lại
        else:
            du = []
        for w in du:
            w.dang_nghi = True
            _gui(w, None)
        doi = {w.ket_noi: w for w in song}
        for ket_noi in wait(list(doi), NHIP_KIEM_S):
            if _nhan_ket_qua(doi[ket_noi], lich):
                song.remove(doi[ket_noi])
        _kiem_nhip(song)


def instrumented_multiproc_add(analyzer, hash_tab, filename_iter, report, ncores):
    """Bản thay thế ``multiproc_add``: cùng ``HashTable`` và ``merge()``, không kẹt, không cạn RAM.

    Bản vendored (``audfprint.py:199``) có ba khiếm khuyết cộng lại thành treo cứng:

    1. Mỗi worker gửi trả nguyên một ``HashTable`` qua ``multiprocessing.Pipe``.
       Bảng luôn được cấp phát đủ ``2**hashbits x depth`` ô ``uint32`` bất kể xử lý
       bao nhiêu file — với tham số mặc định là **419 MB mỗi worker**, tức khoảng
       3,3 GB đi qua named pipe khi ``--ncores 8``. Đây là phần không ổn định.
    2. Tiến trình cha **giữ nguyên mọi đầu ghi** ``tx[ix]``. Worker chết không tạo
       EOF nên ``recv()`` chờ mãi mãi.
    3. Không có timeout ở bất kỳ đâu.

    Đã tái hiện treo trên chính audfprint gốc (không qua wrapper), 3/6 lần chạy.

    Bản này cho worker ghi bảng ra file tạm (gzip — bảng gần như toàn số 0 nên nén cực tốt) và thay
    cách chia cứng ``filelists[ix % ncores]`` bằng phát từng clip theo RAM (D-31): chia cứng để clip
    18,2 giờ chạy cùng 7 worker khác, cạn RAM, sụp cả lượt (06/11/2026).
    """
    import multiprocessing

    files = list(filename_iter)
    with ThreadPoolExecutor(max_workers=8) as nhom:
        clips = [Clip(f, can) for f, can in zip(files, nhom.map(uoc_luong_ram_gb, files))]
    trong, du_phong = _ram_trong_gb(), _du_phong_ram_gb()
    lich = LichTheoRam(clips, trong, du_phong, ncores)
    so_dai = sum(1 for c in clips if c.can_gb > lich.phan_moi_worker)
    _emit("thong_bao_ram", message=(f"RAM trống {trong:.1f} GB, giữ lại {du_phong:.1f} GB cho máy; "
                                    f"{so_dai} clip dài được xếp cuối."))

    thu_muc = tempfile.mkdtemp(prefix="timclip_ht_", dir=_thu_muc_bang_tam())
    workers: list = []
    try:
        for ix in range(min(ncores, len(clips))):
            cha, con = multiprocessing.Pipe()
            path = os.path.join(thu_muc, f"hash_table_{ix}.pklz")
            process = multiprocessing.Process(
                target=_worker_ghi_hash_table,
                args=(analyzer, con, hash_tab.hashbits, hash_tab.depth,
                      (1 << hash_tab.maxtimebits), path),
            )
            process.start()
            # Cha không được giữ đầu của worker: worker chết phải thành EOF, không phải treo.
            con.close()
            workers.append(_Worker(ix, process, cha, path))

        _dieu_phoi(lich, workers)

        for w in workers:
            with gzip.open(w.duong_dan, "rb") as fh:
                hash_tabx = pickle.load(fh)
            # Giải phóng sớm để đỉnh dung lượng đĩa không cộng dồn cả 8 worker.
            try:
                os.remove(w.duong_dan)
            except OSError:
                pass

            report([
                "hash_table " + str(w.so) + " has "
                + str(len(hash_tabx.names))
                + " files " + str(sum(hash_tabx.counts)) + " hashes"
            ])
            # Clip 0 hash của lần trước được thử lại: nhả ô rỗng cũ TRƯỚC khi merge, nếu
            # không clip có hai bản ghi (audit C-3).
            giai_phong_ban_ghi_rong(hash_tab, hash_tabx.names)
            hash_tab.merge(hash_tabx)
            del hash_tabx
            w.process.join(timeout=60)
    finally:
        for w in workers:
            dung_worker_va_cay_con(w.process)
            w.ket_noi.close()
        shutil.rmtree(thu_muc, ignore_errors=True)


def dung_worker_va_cay_con(process, cho_s: float = 5.0) -> None:
    """Dừng một worker CÙNG mọi hậu duệ của nó (audit TCP-14).

    ``Process.terminate()`` chỉ dừng đúng worker: FFmpeg mà worker đang chạy sẽ sống
    tiếp, giữ file và CPU. Lấy danh sách cây con khi worker CÒN SỐNG (psutil chỉ thấy
    được cây khi cha còn đó), dừng chúng trước, rồi mới tới worker; mọi bước đều có
    hạn chờ. Không giết theo tên, chỉ đúng các PID thuộc cây của worker này.
    """
    if process.pid is None:
        return
    if not process.is_alive():
        process.join(0)
        return
    try:
        import psutil

        con = psutil.Process(process.pid).children(recursive=True)
    except Exception:  # noqa: BLE001 - không đọc được cây thì vẫn phải dừng worker
        con = []
    for p in reversed(con):
        try:
            p.terminate()
        except Exception:  # noqa: BLE001
            pass
    process.terminate()
    process.join(cho_s)
    if process.is_alive():
        process.kill()
        process.join(cho_s)
    if con:
        import psutil

        _, con_song = psutil.wait_procs(con, timeout=cho_s)
        for p in con_song:
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass


def cai_dat_instrumentation(audfprint) -> None:
    """Gắn bản vá vào audfprint vendored. Tách riêng để test được.

    Thiếu ``multiproc_add`` là quay lại nguy cơ treo cứng và cạn RAM; thiếu ``do_cmd`` thì nhánh một
    nhân (mặc định của CLI) không có event, không qua lịch RAM, một clip quá dài làm sập cả lượt.
    """
    audfprint.multiproc_add = instrumented_multiproc_add
    do_cmd_goc = audfprint.do_cmd

    def do_cmd(cmd, analyzer, hash_tab, filename_iter, matcher, outdir, type_, report, **kwargs):
        if cmd in ("new", "add"):
            return instrumented_multiproc_add(analyzer, hash_tab, filename_iter, report, 1)
        return do_cmd_goc(cmd, analyzer, hash_tab, filename_iter, matcher, outdir, type_, report,
                          **kwargs)

    audfprint.do_cmd = do_cmd
    cai_dat_theo_doi_giai_ma()


def _ha_uu_tien_tien_trinh() -> None:
    """Dựng kho chạy Below Normal; worker và FFmpeg thừa hưởng theo quy tắc CreateProcess của Windows."""
    try:
        import psutil

        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:  # noqa: BLE001 - lớp phụ, không được làm hỏng build
        pass


_NHOM_CUA_RUNNER = None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if len(argv) < 3:
        print("Dùng: audfprint_progress_runner.py <audfprint.py> <command> ...", file=sys.stderr)
        return 2
    vendor_script = os.path.abspath(argv[1])
    vendor_dir = os.path.dirname(vendor_script)
    if vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)

    # Runner tự vào một Job Object riêng: chết vì bất kỳ lý do gì thì worker và FFmpeg
    # do nó sinh ra cũng chết theo, không thành process mồ côi (audit TCP-14).
    global _NHOM_CUA_RUNNER
    try:
        from process_runner import NhomTienTrinh

        _NHOM_CUA_RUNNER = NhomTienTrinh()
        _NHOM_CUA_RUNNER.gan_chinh_minh()
    except Exception:  # noqa: BLE001 - lớp bảo vệ thêm, không được làm hỏng build
        _NHOM_CUA_RUNNER = None

    _ha_uu_tien_tien_trinh()

    # Bảng hash tạm nằm cạnh database đang dựng (bản làm việc của job), không ở %TEMP%.
    dbase = _dbase_trong_lenh(argv[2:])
    if dbase:
        os.environ.setdefault(BIEN_THU_MUC_BANG_TAM, os.path.dirname(os.path.abspath(dbase)))

    import audfprint

    cai_dat_instrumentation(audfprint)
    audfprint.main([vendor_script, *argv[2:]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
