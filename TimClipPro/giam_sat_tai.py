# -*- coding: utf-8 -*-
"""Giám sát MỘT lượt tải audio của yt-dlp bằng một luồng phụ nhỏ (chu kỳ 1 giây).

yt-dlp giao tải MỘT PHẦN (``download_ranges``) cho ffmpeg (``FFmpegFD``): ffmpeg đọc thẳng luồng
audio với ``-t`` (dừng đúng sau N giây đầu — giới hạn ở NGUỒN, không tải hết rồi cắt), nhưng
yt-dlp chỉ ``proc.wait()`` — không hạn chờ, không phát progress hook nào tới khi ffmpeg thoát
(yt_dlp/downloader/external.py, FFmpegFD._call_downloader). Hậu quả đã gặp trên PC2 (12/10/2026):

* màn hình đứng ở «chuẩn bị tải audio…» suốt 24 phút, không biết đang tải hay đang treo;
* nút Dừng chỉ đặt cờ huỷ — cờ được kiểm trong progress hook, mà hook không bao giờ chạy, nên
  ffmpeg tải tiếp tới hết phần đã hẹn;
* mạng đứng (server giữ kết nối mà không gửi byte) thì ffmpeg chờ vô hạn.

Luồng này, không sửa yt-dlp:

* đọc file ``-progress`` mà ffmpeg ghi (``external_downloader_args``) → byte ffmpeg đã GHI ra file
  (``total_size`` — dung lượng đầu ra, KHÔNG phải byte mạng), giây audio đã nhận, tốc độ — số đo THẬT;
* có yêu cầu huỷ → giết ffmpeg đang ghi ĐÚNG file đích (chỉ tiến trình con của chính app);
* không thêm byte nào quá ``han_dung_s`` trong lúc ffmpeg còn chạy → giết, đánh dấu ``dung_hinh``
  để nơi gọi báo lỗi mạng rõ ràng thay vì chờ vô hạn.

Đường tải thường (tải trọn, yt-dlp tự tải trong tiến trình) đã có progress hook; luồng này khi đó
chỉ không tìm thấy ffmpeg nào và không làm gì.

Tải CHẬM của chính đường ffmpeg (pilot 13/10, video 66 giờ: 2,03× thời gian thực): ffmpeg xin MỘT yêu cầu
``Range: bytes=0-`` và googlevideo nhả nó theo nhịp phát. ``KHOI_YEU_CAU_TAI`` + ``ffmpeg_chia_khoi_duoc`` để
engine đặt ``-request_size`` (tuỳ chọn ĐẦU VÀO): ffmpeg xin từng khối Range ĐÓNG như yt-dlp tải thường.
"""

from __future__ import annotations

import functools
import logging
import os
import threading
import time
from typing import Callable, Optional

from process_runner import chay_lenh_media

LOGGER = logging.getLogger("scan.download")

# ffmpeg còn chạy mà không thêm byte nào quá mức này → coi là mạng đứng, giết.
HAN_DUNG_TAI_S = 180.0

# Cỡ mỗi yêu cầu HTTP khi ffmpeg tải phần đầu — bằng `CHUNK_SIZE` yt-dlp dùng cho YouTube: googlevideo nhả
# một yêu cầu LỚN hoặc MỞ theo nhịp phát (~1–2× thời gian thực), còn khối ≤ 10 MiB thì nhả hết tốc.
KHOI_YEU_CAU_TAI = 10 << 20


@functools.lru_cache(maxsize=1)
def ffmpeg_chia_khoi_duoc() -> bool:
    """ffmpeg trên PATH (cũng là ffmpeg yt-dlp gọi) có tuỳ chọn ``request_size`` của giao thức http không.

    FFmpeg 9.0.1 trên PC2: có. Bản cũ không có — truyền vào thì ffmpeg thoát ngay vì tuỳ chọn lạ, nên thà tải
    chậm như cũ còn hơn hỏng. Hỏi MỘT lần mỗi tiến trình: ffmpeg không đổi khi app đang chạy.
    """
    try:
        r = chay_lenh_media(["ffmpeg", "-hide_banner", "-h", "protocol=http"], tran_tong_s=15)
    except (OSError, ValueError):
        return False
    return not r.timed_out and "request_size" in (r.stdout or "") + (r.stderr or "")


def doc_tien_do_ffmpeg(duong: str, toi_da_byte: int = 16384) -> dict:
    """Khối tiến độ HOÀN CHỈNH cuối cùng của file ``-progress`` của ffmpeg.

    Trả ``{"byte": int|None, "audio_s": float|None, "toc_do_x": float|None, "ket_thuc": bool}``,
    hoặc ``{}`` khi chưa có khối nào. ``byte`` = ``total_size`` = byte ffmpeg ĐÃ GHI ra file đầu ra,
    không phải byte nhận qua mạng. Chỉ đọc phần đuôi file (file chỉ ghi nối thêm).
    """
    try:
        with open(duong, "rb") as f:
            f.seek(0, os.SEEK_END)
            n = f.tell()
            f.seek(max(0, n - toi_da_byte))
            tho = f.read().decode("utf-8", "replace")
    except OSError:
        return {}
    khoi: dict = {}
    hoan_chinh: dict = {}
    for dong in tho.splitlines():
        khoa, sep, gia_tri = dong.partition("=")
        if not sep:
            continue
        khoa, gia_tri = khoa.strip(), gia_tri.strip()
        khoi[khoa] = gia_tri
        if khoa == "progress":
            hoan_chinh, khoi = khoi, {}
    if not hoan_chinh:
        return {}

    def so_nguyen(x) -> Optional[int]:
        try:
            v = int(str(x))
        except (TypeError, ValueError):
            return None
        return v if v >= 0 else None

    us = so_nguyen(hoan_chinh.get("out_time_us"))
    toc_do = None
    tho_toc_do = str(hoan_chinh.get("speed") or "").rstrip("x").strip()
    try:
        toc_do = float(tho_toc_do) if tho_toc_do and tho_toc_do != "N/A" else None
    except ValueError:
        toc_do = None
    return {
        "byte": so_nguyen(hoan_chinh.get("total_size")),
        "audio_s": None if us is None else us / 1_000_000,
        "toc_do_x": toc_do,
        "ket_thuc": hoan_chinh.get("progress") == "end",
    }


def _chuan_hoa(duong: str) -> str:
    return os.path.normcase(os.path.abspath(duong)).replace("/", "\\")


def tim_ffmpeg_ghi(tien_to: str) -> list:
    """Tiến trình ffmpeg CON của app này có đối số trỏ vào file đích (``tien_to`` + đuôi bất kỳ)."""
    import psutil

    dich = _chuan_hoa(tien_to)
    ra = []
    try:
        con = psutil.Process(os.getpid()).children(recursive=True)
    except psutil.Error:
        return ra
    for p in con:
        try:
            if "ffmpeg" not in (p.name() or "").lower():
                continue
            if any(dich in _chuan_hoa(a) for a in p.cmdline() if a and not a.startswith("-")):
                ra.append(p)
        except (psutil.Error, OSError, ValueError):
            continue
    return ra


def giet(tien_trinh: list) -> int:
    """Giết các tiến trình (và con của chúng). Trả số tiến trình đã giết."""
    import psutil

    so = 0
    for p in tien_trinh:
        try:
            for c in p.children(recursive=True):
                try:
                    c.kill()
                except psutil.Error:
                    pass
            p.kill()
            so += 1
        except psutil.Error:
            continue
    if tien_trinh:
        psutil.wait_procs(tien_trinh, timeout=5)
    return so


class GiamSatTai:
    """Dùng dạng ``with``: luồng phụ chạy suốt lượt tải, dừng và join khi ra khỏi khối."""

    def __init__(self, tien_to: str, file_tien_do: Optional[str], cancel_event, *,
                 khi_so_lieu: Optional[Callable[[dict], None]] = None,
                 khi_nhip: Optional[Callable[[], None]] = None,
                 han_dung_s: float = HAN_DUNG_TAI_S, chu_ky_s: float = 1.0,
                 tim: Callable[[str], list] = tim_ffmpeg_ghi,
                 ham_giet: Callable[[list], int] = giet):
        self.tien_to = tien_to
        self.file_tien_do = file_tien_do
        self.cancel_event = cancel_event
        self.khi_so_lieu = khi_so_lieu
        self.khi_nhip = khi_nhip
        self.han_dung_s = float(han_dung_s)
        self.chu_ky_s = float(chu_ky_s)
        self._tim = tim
        self._giet = ham_giet
        self._dung = threading.Event()
        self._luong: Optional[threading.Thread] = None
        self.da_giet_vi_huy = False
        self.dung_hinh = False
        self.byte_cuoi = 0
        self.audio_cuoi = 0.0
        self.luc_tien_trien: Optional[float] = None

    def __enter__(self) -> "GiamSatTai":
        self._luong = threading.Thread(target=self._vong, name="giam-sat-tai", daemon=True)
        self._luong.start()
        return self

    def __exit__(self, *exc) -> None:
        self._dung.set()
        if self._luong is not None:
            self._luong.join(timeout=10)

    def _vong(self) -> None:
        while not self._dung.is_set():
            try:
                self.tick(time.monotonic())
            except Exception:  # noqa: BLE001 — giám sát hỏng không được làm hỏng lượt tải
                LOGGER.exception("event=download.monitor_failed")
            self._dung.wait(self.chu_ky_s)

    def _kich_thuoc(self) -> int:
        thu_muc, ten = os.path.split(self.tien_to)
        tong = 0
        try:
            for f in os.listdir(thu_muc or "."):
                if f.startswith(ten + "."):
                    try:
                        tong = max(tong, os.path.getsize(os.path.join(thu_muc, f)))
                    except OSError:
                        continue
        except OSError:
            return 0
        return tong

    def tick(self, bay_gio: float) -> None:
        """Một chu kỳ giám sát (tách ra để test gọi trực tiếp, không cần luồng)."""
        so = doc_tien_do_ffmpeg(self.file_tien_do) if self.file_tien_do else {}
        byte = so.get("byte") or self._kich_thuoc()
        audio = so.get("audio_s")
        tien = byte > self.byte_cuoi or (audio is not None and audio > self.audio_cuoi)
        ffmpeg = self._tim(self.tien_to)
        if ffmpeg and self.luc_tien_trien is None:
            # Đồng hồ «đứng yên» chỉ chạy khi ffmpeg đã thật sự tồn tại — trích xuất lại thông tin
            # (yt-dlp làm trước khi gọi ffmpeg) có hạn chờ riêng của nó.
            self.luc_tien_trien = bay_gio
        if tien:
            self.byte_cuoi = max(self.byte_cuoi, byte)
            if audio is not None:
                self.audio_cuoi = max(self.audio_cuoi, audio)
            self.luc_tien_trien = bay_gio
            if self.khi_so_lieu is not None:
                self.khi_so_lieu({"byte_dau_ra": int(self.byte_cuoi),
                                  "audio_da_nhan_s": audio, "toc_do_x": so.get("toc_do_x")})
        elif ffmpeg and self.khi_nhip is not None:
            self.khi_nhip()
        if not ffmpeg:
            return
        if self.cancel_event is not None and self.cancel_event.is_set():
            if not self.da_giet_vi_huy:
                self.da_giet_vi_huy = True
                LOGGER.warning("event=download.kill_on_cancel count=%d", len(ffmpeg))
            self._giet(ffmpeg)
            return
        if self.luc_tien_trien is not None and bay_gio - self.luc_tien_trien >= self.han_dung_s:
            if not self.dung_hinh:
                self.dung_hinh = True
                LOGGER.warning("event=download.stalled seconds=%.0f bytes=%d", self.han_dung_s,
                               self.byte_cuoi)
            self._giet(ffmpeg)
