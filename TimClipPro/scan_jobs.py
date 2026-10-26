# -*- coding: utf-8 -*-
"""Điều phối một batch quét: tiến độ, kết quả streaming, trạng thái giao Sheets.

Không phụ thuộc Streamlit — worker chỉ phát event; main thread của UI đọc snapshot.
Đây là đúng ranh giới mà ``fingerprint_progress.FingerprintJobController`` đã dùng và
đã có test; tái dùng pattern thay vì phát minh cái mới.
"""

from __future__ import annotations

import contextlib
import logging
import os
import queue
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

import maintenance_gate
import tien_do_quet as tdq

LOGGER = logging.getLogger("scan.job")

# Phase phản ánh đúng những gì engine thực sự làm (xem Engine.scan_youtube/scan_media).
PHASE_CHO = "queued"
PHASE_METADATA = "fetching_metadata"
PHASE_TAI = "downloading"
PHASE_CAT_KHUC = "chunking"
PHASE_SO_KHOP = "matching"
PHASE_TONG_HOP = "merging"
PHASE_XONG = "completed"
PHASE_LOI = "failed"
PHASE_HUY = "cancelled"

# Trạng thái QUÉT của một video — tách hẳn khỏi trạng thái giao Sheets.
QUET_CHO = "queued"
QUET_DANG_CHAY = "running"
QUET_XONG = "completed"
QUET_LOI = "failed"

_TU_KHOA_PHASE = (
    ("Đang lấy thông tin video", PHASE_METADATA),
    # «<tên> (thời lượng) — chuẩn bị tải audio...» phát SAU khi đã có thông tin video, ngay trước
    # khi tải: đó là bước TẢI. Ánh xạ cũ về «metadata» làm màn hình PC2 ghi «Đang lấy thông tin
    # video» suốt 24 phút trong lúc ffmpeg đang tải (12/10/2026).
    ("chuẩn bị tải", PHASE_TAI),
    ("Giới hạn video dài", PHASE_TAI),
    ("Đang tải", PHASE_TAI),
    ("Đã có sẵn audio", PHASE_TAI),
    ("Đang cắt khúc", PHASE_CAT_KHUC),
    ("Đang đo", PHASE_CAT_KHUC),
    ("Đang so khớp", PHASE_SO_KHOP),
    ("Đang nạp kho", PHASE_SO_KHOP),
    ("Xong —", PHASE_TONG_HOP),
)


def doan_phase(thong_bao: str) -> Optional[str]:
    """Suy phase từ thông báo tiến độ của engine.

    Engine đã phát thông báo tiếng Việt rất mô tả cho từng bước; ánh xạ chúng thành
    phase có cấu trúc rẻ hơn nhiều so với việc sửa chữ ký mọi hàm trong engine chỉ
    để mang thêm một tham số phase. Không khớp thì trả None và giữ phase cũ.
    """
    for tu_khoa, phase in _TU_KHOA_PHASE:
        if tu_khoa in thong_bao:
            return phase
    return None


@dataclass(frozen=True)
class VideoState:
    """Trạng thái một video trong batch. Bất biến; cập nhật bằng ``replace``."""

    index: int
    nguon: str
    scan_status: str = QUET_CHO
    phase: str = PHASE_CHO
    video_id: str = ""
    title: str = ""
    matches: Optional[int] = None
    so_dat_nguong: Optional[int] = None
    progress: float = 0.0
    message: str = ""
    error: str = ""
    delivery_key: str = ""          # mã việc gửi trong outbox (rỗng = không gửi)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        return (self.finished_at or time.time()) - self.started_at


@dataclass(frozen=True)
class BatchSnapshot:
    """Ảnh chụp bất biến để UI vẽ mà không sợ dữ liệu đổi giữa chừng."""

    batch_id: str
    total: int
    current_index: int
    completed: int
    failed: int
    running: bool
    cancelled: bool
    elapsed_seconds: float
    eta_seconds: Optional[float]
    message: str
    videos: tuple = ()
    # Đích Google Sheets ĐÃ GHIM của lô (nhãn) + mã lô trong outbox; rỗng = chỉ lưu cục bộ.
    dich_gui: str = ""
    dich_id: str = ""
    lo_id: str = ""
    # Số đo THẬT của video đang chạy + nhật ký ngắn (``tien_do_quet``); luồng quét còn sống không.
    tien_do: tdq.AnhTienDo = field(default_factory=tdq.AnhTienDo)
    nhat_ky: tuple = ()
    worker_alive: bool = False
    gioi_han_video_dai: str = ""

    @property
    def batch_progress(self) -> float:
        if self.total <= 0:
            return 0.0
        xong = self.completed + self.failed
        dang = self.videos[self.current_index - 1].progress if (
            0 < self.current_index <= len(self.videos)
        ) else 0.0
        if self.videos and 0 < self.current_index <= len(self.videos):
            if self.videos[self.current_index - 1].scan_status != QUET_DANG_CHAY:
                dang = 0.0
        return max(0.0, min(1.0, (xong + dang) / self.total))


# Lô quét ĐANG CHẠY của tiến trình, theo thư mục dữ liệu. Mỗi phiên trình duyệt (tải lại trang = phiên
# mới) có controller riêng trong ``st.session_state``: không có sổ chung này thì tải lại trang trong lúc
# quét sẽ mất màn hình tiến độ và cho bấm «Bắt đầu quét» lần nữa — hai lô chạy song song trên cùng kho.
_DANG_CHAY: dict = {}
_KHOA_DANG_CHAY = threading.Lock()


def _khoa_lo(engine) -> str:
    thu_muc = getattr(engine, "data_dir", None)
    return os.path.normcase(os.path.abspath(thu_muc)) if thu_muc else f"id:{id(engine)}"


class ScanJobController:
    """Một batch, một worker thread, snapshot bất biến cho UI."""

    @staticmethod
    def dang_chay_cua(engine) -> Optional["ScanJobController"]:
        """Controller đang chạy lô trên CÙNG thư mục dữ liệu (phiên khác của tiến trình), nếu có."""
        with _KHOA_DANG_CHAY:
            ctl = _DANG_CHAY.get(_khoa_lo(engine))
        return ctl if ctl is not None and ctl.running else None

    @staticmethod
    def cua_phien(engine, hien_tai: Optional["ScanJobController"] = None,
                  dang_hien_lo: bool = False) -> "ScanJobController":
        """Controller của phiên trình duyệt sở hữu ``engine`` — gọi MỖI lần vẽ lại (``hien_tai`` = controller
        phiên đang giữ). Phiên mới: lô của phiên khác (cùng thư mục dữ liệu) còn chạy → NHẬN LẠI nó (tiến độ,
        Dừng). Controller nhận lại GIỮ Engine của phiên cũ (kho, ngưỡng, cookie đã ghim) nên chỉ mượn khi lô
        còn chạy hoặc phiên còn đang hiện lô đó (``dang_hien_lo``: chưa chép kết quả); xong rồi → controller
        MỚI gắn Engine của chính phiên, lô sau dùng đúng kho/cấu hình thanh bên đang hiện (audit F-1)."""
        if hien_tai is not None and (hien_tai.engine is engine or hien_tai.running or dang_hien_lo):
            return hien_tai
        return ScanJobController.dang_chay_cua(engine) or ScanJobController(engine)

    def __init__(self, engine, recent_maxlen: int = 60):
        self.engine = engine
        self.so_tien_do = tdq.SoTienDo()
        self._gioi_han_video_dai = ""
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._batch_id = ""
        self._videos: list = []
        self._results: list = []
        self._recent: deque = deque(maxlen=recent_maxlen)
        self._events: queue.Queue = queue.Queue(maxsize=512)
        self._running = False
        self._cancelled = False
        self._started_mono: Optional[float] = None
        self._finished_mono: Optional[float] = None
        self._xong_gan_day: deque = deque(maxlen=10)
        self._message = ""
        self._error = ""
        self._y_dinh_gui = None

    # ---------- điều khiển ----------

    def start(
        self,
        nguon: list,
        source_type: str = "youtube",
        on_result: Optional[Callable] = None,
        y_dinh_gui=None,
        gioi_han_video_dai: Optional[str] = None,
    ) -> str:
        """``y_dinh_gui``: ý định gửi đã chụp lúc bấm Bắt đầu (``sheet_destinations.YDinhGui``) —
        ghim trên bản Engine của lô, đổi lựa chọn trên giao diện giữa chừng không ảnh hưởng.
        ``gioi_han_video_dai``: chế độ giới hạn video dài (``engine.GHVD_*``) của lô; ``None`` = như cũ."""
        khac = ScanJobController.dang_chay_cua(self.engine)
        if khac is not None and khac is not self:
            raise RuntimeError("Đang có lô quét chạy ở một cửa sổ/phiên khác của Tool — tải lại trang "
                               "để xem tiến độ; không tạo lô trùng.")
        with self._lock:
            if self._running or (self._thread and self._thread.is_alive()):
                raise RuntimeError("Đang có batch quét chạy; không tạo batch trùng.")
            # Vào cổng bảo trì TRƯỚC khi đổi trạng thái: đang cập nhật → `DangBaoTri` (một dạng "bận"),
            # lô chưa bắt đầu gì. Lease giữ suốt lô, trả ở luồng nền khi lô kết thúc.
            lease = maintenance_gate.nhan_viec_cua(self.engine, f"lô quét ({source_type})")
            self._batch_id = uuid.uuid4().hex
            self._videos = [
                VideoState(index=i, nguon=str(x)) for i, x in enumerate(nguon, 1)
            ]
            self._results = []
            self._recent.clear()
            self._xong_gan_day.clear()
            self._running = True
            self._cancelled = False
            self._error = ""
            self._message = "Đang chuẩn bị..."
            self._started_mono = time.monotonic()
            self._finished_mono = None
            self._y_dinh_gui = y_dinh_gui
            self._gioi_han_video_dai = gioi_han_video_dai or ""
            batch_id = self._batch_id
        self.so_tien_do.bat_dau_lo(batch_id, len(nguon))
        with _KHOA_DANG_CHAY:
            _DANG_CHAY[_khoa_lo(self.engine)] = self

        self.engine.cancel_event.clear()
        LOGGER.info(
            "event=scan.batch.started batch_id=%s total=%d type=%s",
            batch_id, len(nguon), source_type,
        )
        self._thread = threading.Thread(
            target=self._chay,
            args=(list(nguon), source_type, on_result, lease),
            name=f"scan-{batch_id[:8]}",
            daemon=True,
        )
        self._thread.start()
        return batch_id

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            self._message = "Đang yêu cầu dừng; giữ nguyên kết quả đã xong..."
        LOGGER.warning("event=scan.batch.cancel_requested batch_id=%s", self._batch_id)
        self.so_tien_do.ghi("Đã yêu cầu DỪNG — đang dừng tác vụ con (tải/ffmpeg/audfprint); kết quả đã "
                            "xong được giữ")
        self.engine.cancel()

    # ---------- worker ----------

    def _sua_video(self, index: int, **thay_doi) -> None:
        with self._lock:
            if 0 < index <= len(self._videos):
                self._videos[index - 1] = replace(self._videos[index - 1], **thay_doi)

    def _ghi_su_kien(self, noi_dung: str) -> None:
        self.so_tien_do.ghi(noi_dung)
        with self._lock:
            self._recent.append((time.time(), noi_dung))
        try:
            self._events.put_nowait(noi_dung)
        except queue.Full:
            try:
                self._events.get_nowait()
                self._events.put_nowait(noi_dung)
            except (queue.Empty, queue.Full):
                pass

    def _chay(self, nguon: list, source_type: str, on_result: Optional[Callable],
              lease=None) -> None:
        try:
            self._chay_trong_cong(nguon, source_type, on_result)
        finally:
            if lease is not None:
                lease.tra()
            with _KHOA_DANG_CHAY:
                if _DANG_CHAY.get(_khoa_lo(self.engine)) is self:
                    del _DANG_CHAY[_khoa_lo(self.engine)]

    def _chay_trong_cong(self, nguon: list, source_type: str, on_result: Optional[Callable]) -> None:
        try:
            def tien_do(pct: float, msg: str) -> None:
                # Engine gắn tiền tố "[i/n] " ở scan_iter; bóc ra để biết video nào.
                index, thong_bao = self._tach_chi_so(msg)
                if index is None:
                    with self._lock:
                        self._message = thong_bao
                    return
                phase = doan_phase(thong_bao)
                trong_video = self._pct_trong_video(pct, index, len(nguon))
                thay_doi = {
                    "scan_status": QUET_DANG_CHAY,
                    "progress": trong_video,
                    "message": thong_bao,
                }
                if phase:
                    thay_doi["phase"] = phase
                with self._lock:
                    hien_tai = self._videos[index - 1] if 0 < index <= len(self._videos) else None
                    if hien_tai is not None and hien_tai.started_at is None:
                        thay_doi["started_at"] = time.time()
                    self._message = thong_bao
                self._sua_video(index, **thay_doi)

            def sau_moi_video(index: int, tong: int, ket_qua) -> None:
                self._hoan_tat_video(index, ket_qua)
                if on_result:
                    on_result(index, tong, ket_qua)

            # Cờ huỷ đã được xoá ĐÚNG MỘT LẦN ở start(); scan_iter không xoá lại để một
            # cú bấm Dừng rơi vào khoảng giữa start() và lúc thread chạy không bị nuốt.
            # Chỉ truyền khi có, để engine giả trong test giữ chữ ký cũ.
            them = {"y_dinh_gui": self._y_dinh_gui} if self._y_dinh_gui is not None else {}
            if self._gioi_han_video_dai:
                them["gioi_han_video_dai"] = self._gioi_han_video_dai
            them["so_tien_do"] = self.so_tien_do
            for ket_qua in self.engine.scan_iter(
                nguon, source_type, tien_do, on_video=sau_moi_video, xoa_co_huy=False, **them
            ):
                with self._lock:
                    self._results.append(ket_qua)
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._error = str(exc)
            LOGGER.exception("event=scan.batch.failed batch_id=%s", self._batch_id)
        finally:
            # Batch YouTube bị dừng vì cầu dao (bot-check, 429, đăng nhập lặp lại…): nói rõ
            # đó là YouTube chặn, không phải "Quét hoàn tất" — các video còn lại CHƯA quét.
            phien = getattr(self.engine, "phien_youtube_cuoi", None)
            bi_chan = phien.thong_bao_dung() if getattr(phien, "mo", False) is True else ""
            with self._lock:
                self._running = False
                self._finished_mono = time.monotonic()
                if not self._error:
                    self._message = (
                        "Đã dừng theo yêu cầu." if self._cancelled
                        else bi_chan or "Quét hoàn tất."
                    )
                ket = f"Lô quét lỗi: {self._error[:160]}" if self._error else self._message
            self.so_tien_do.ghi(ket)
            LOGGER.info(
                "event=scan.batch.finished batch_id=%s completed=%d failed=%d",
                self._batch_id,
                sum(1 for v in self._videos if v.scan_status == QUET_XONG),
                sum(1 for v in self._videos if v.scan_status == QUET_LOI),
            )

    @staticmethod
    def _tach_chi_so(msg: str) -> tuple:
        if msg.startswith("[") and "]" in msg:
            dau, _, duoi = msg[1:].partition("]")
            phan = dau.split("/")
            if len(phan) == 2 and phan[0].strip().isdigit():
                return int(phan[0].strip()), duoi.strip()
        return None, msg

    @staticmethod
    def _pct_trong_video(pct_batch: float, index: int, tong: int) -> float:
        """scan_iter phát pct theo cả batch; đổi ngược lại thành pct của video."""
        if tong <= 0:
            return 0.0
        return max(0.0, min(1.0, pct_batch * tong - (index - 1)))

    def _hoan_tat_video(self, index: int, ket_qua) -> None:
        loi = getattr(ket_qua, "status", "ok") != "ok"
        so_match = len(getattr(ket_qua, "matches", []) or [])
        self._sua_video(
            index,
            scan_status=QUET_LOI if loi else QUET_XONG,
            phase=PHASE_LOI if loi else PHASE_XONG,
            progress=1.0,
            video_id=str(getattr(ket_qua, "source_id", "") or ""),
            title=str(getattr(ket_qua, "source_name", "") or ""),
            matches=so_match,
            so_dat_nguong=int(getattr(ket_qua, "so_dat_nguong", 0) or 0),
            error=str(getattr(ket_qua, "note", "") or "") if loi else "",
            finished_at=time.time(),
            message="Lỗi" if loi else f"Hoàn tất — {so_match} đoạn",
        )
        with self._lock:
            self._xong_gan_day.append(time.monotonic())
        LOGGER.info(
            "event=scan.video.completed batch_id=%s index=%d status=%s matches=%d",
            self._batch_id, index, "failed" if loi else "ok", so_match,
        )
        huy = loi and (getattr(ket_qua, "ly_do_pham_vi", "") or "") == "huy"
        with contextlib.suppress(Exception):
            self.so_tien_do.cap_nhat(giai_doan=tdq.GD_HUY if huy else tdq.GD_LOI if loi else tdq.GD_XONG)
        if loi:
            ghi_chu = " ".join(str(getattr(ket_qua, "note", "") or "").split())[:160]
            self._ghi_su_kien(f"Video {index}: " + ("đã dừng theo yêu cầu" if huy
                                                     else f"lỗi — {ghi_chu}" if ghi_chu else "lỗi"))
        else:
            self._ghi_su_kien(f"Video {index}: hoàn tất, {so_match} đoạn")

    def ghi_nhan_giao_hang(self, index: int, delivery_key: str) -> None:
        self._sua_video(index, delivery_key=delivery_key)

    # ---------- đọc trạng thái ----------

    def _eta(self, con_lai: int) -> Optional[float]:
        with self._lock:
            moc = list(self._xong_gan_day)
        if con_lai <= 0 or len(moc) < 2:
            return None
        khoang = moc[-1] - moc[0]
        if khoang <= 0:
            return None
        return khoang / (len(moc) - 1) * con_lai

    def snapshot(self) -> BatchSnapshot:
        with self._lock:
            videos = tuple(self._videos)
            xong = sum(1 for v in videos if v.scan_status == QUET_XONG)
            loi = sum(1 for v in videos if v.scan_status == QUET_LOI)
            dang = next(
                (v.index for v in videos if v.scan_status == QUET_DANG_CHAY),
                xong + loi + 1 if xong + loi < len(videos) else len(videos),
            )
            moc_dau = self._started_mono
            moc_cuoi = self._finished_mono
            running = self._running or bool(self._thread and self._thread.is_alive())
            snapshot = BatchSnapshot(
                batch_id=self._batch_id,
                total=len(videos),
                current_index=dang,
                completed=xong,
                failed=loi,
                running=running,
                cancelled=self._cancelled,
                elapsed_seconds=(
                    0.0 if moc_dau is None
                    else (moc_cuoi or time.monotonic()) - moc_dau
                ),
                eta_seconds=None,
                message=self._message,
                videos=videos,
                dich_gui=(self._y_dinh_gui.dich.nhan if self._y_dinh_gui is not None else ""),
                dich_id=(self._y_dinh_gui.dich.dich_id if self._y_dinh_gui is not None else ""),
                lo_id=(self._y_dinh_gui.lo_id if self._y_dinh_gui is not None else ""),
                tien_do=self.so_tien_do.anh(),
                nhat_ky=tuple(self.so_tien_do.su_kien(20)),
                worker_alive=bool(self._thread and self._thread.is_alive()),
                gioi_han_video_dai=self._gioi_han_video_dai,
            )
        return replace(snapshot, eta_seconds=self._eta(len(videos) - xong - loi))

    def results(self) -> list:
        with self._lock:
            return list(self._results)

    def recent(self, n: int = 20) -> list:
        with self._lock:
            return list(self._recent)[-n:]

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running or bool(self._thread and self._thread.is_alive())

    @property
    def error(self) -> str:
        with self._lock:
            return self._error
