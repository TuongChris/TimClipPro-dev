# -*- coding: utf-8 -*-
"""Tiến độ THẬT của một lô quét: số đo từ pipeline, nhịp sống, nhật ký ngắn.

Engine (luồng quét và luồng giám sát tải) GHI vào ``SoTienDo``; giao diện ĐỌC ảnh chụp bất biến
(``anh()``). Không phụ thuộc Streamlit, không ước đoán: trường nào chưa đo được thì là ``None`` và
giao diện phải nói «chưa biết» — không vẽ phần trăm giả, không tự tăng số theo đồng hồ.

Vì sao có module này (PC2 12/10/2026): video 65 giờ, màn hình đứng ở «0/5 — 1%», «Đang lấy thông
tin video… chuẩn bị tải audio…» suốt 24 phút. Thật ra khi đó ffmpeg đang tải (yt-dlp giao tải một
phần cho ffmpeg và không phát tiến độ nào), còn nhãn giai đoạn được ĐOÁN từ chữ trong thông báo.
Thông báo ``progress(pct, msg)`` cũ giữ nguyên (golden ghi nguyên văn); số liệu có cấu trúc đi
riêng qua đây.

Hai mốc thời gian TÁCH BIỆT:

* ``nhip_luc`` — tiến trình còn sống: có tín hiệu bất kỳ (luồng giám sát thấy ffmpeg còn chạy,
  audfprint còn chạy, hay một cập nhật nào đó);
* ``tien_trien_luc`` — lần cuối có TIẾN TRIỂN thật: thêm byte/giây audio, thêm khúc, đổi giai đoạn.

Một bước dài không phát số liệu (audfprint nạp kho, so khớp một khúc 1 giờ) KHÔNG phải là treo:
ngưỡng cảnh báo đặt theo từng giai đoạn và luôn nói kèm nhịp sống của tiến trình.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, replace
from typing import Optional

GD_CHO = "cho"
GD_METADATA = "metadata"
GD_TAI = "tai"
GD_KIEM_AUDIO = "kiem_audio"
GD_CAT = "cat_khuc"
GD_KHOP = "so_khop"
GD_TONG_HOP = "tong_hop"
GD_LUU = "luu"
GD_XONG = "xong"
GD_LOI = "loi"
GD_HUY = "huy"

TEN_GIAI_DOAN = {
    GD_CHO: "Đang chờ",
    GD_METADATA: "Đang lấy thông tin video",
    GD_TAI: "Đang tải audio",
    GD_KIEM_AUDIO: "Đang kiểm audio đã tải",
    GD_CAT: "Đang cắt khúc audio",
    GD_KHOP: "Đang so khớp vân tay",
    GD_TONG_HOP: "Đang hợp nhất và lọc kết quả",
    GD_LUU: "Đang lưu lịch sử và báo cáo",
    GD_XONG: "Hoàn tất",
    GD_LOI: "Lỗi",
    GD_HUY: "Đã dừng",
}
GD_KET_THUC = (GD_XONG, GD_LOI, GD_HUY)

# Không có TIẾN TRIỂN mới quá lâu (giây) → cảnh báo. Đặt rộng theo bản chất từng bước: audfprint
# nạp kho rồi so khớp một khúc dài (cấu hình PC2: khúc 1 giờ) có thể vài phút mới có một mốc mới.
NGUONG_CHAM_S = {
    GD_METADATA: 60.0,
    GD_TAI: 60.0,
    GD_KIEM_AUDIO: 90.0,
    GD_CAT: 180.0,
    GD_KHOP: 600.0,
    GD_TONG_HOP: 180.0,
    GD_LUU: 120.0,
}
# Nhịp sống mới hơn mức này thì coi tiến trình còn chạy.
NHIP_CON_SONG_S = 30.0
# Cần ít nhất bấy nhiêu giây dữ liệu tốc độ mới tính ETA (tránh ETA nhảy loạn lúc mới bắt đầu).
CUA_SO_TOC_DO_S = 10.0

_SO_HOC = ("byte_da_nhan", "byte_dau_ra", "audio_da_nhan_s", "khuc_xong", "khop_xong")
_KHONG_PHAI_TIEN_TRIEN = frozenset({"toc_do_byte_s", "toc_do_x", "eta_buoc_s", "giai_doan",
                                    "giai_doan_luc"})


@dataclass(frozen=True)
class SuKien:
    luc: float
    noi_dung: str


@dataclass(frozen=True)
class AnhTienDo:
    """Ảnh chụp tiến độ của video ĐANG chạy. Trường ``None`` = chưa đo được."""

    batch_id: str = ""
    index: int = 0
    tong: int = 0
    nguon: str = ""
    tieu_de: str = ""
    giai_doan: str = GD_CHO
    giai_doan_luc: float = 0.0
    bat_dau_luc: float = 0.0
    nhip_luc: float = 0.0
    tien_trien_luc: float = 0.0
    thoi_luong_nguon_s: Optional[float] = None
    pham_vi_tu_s: Optional[float] = None
    pham_vi_den_s: Optional[float] = None
    che_do: str = ""
    # Byte nhận QUA MẠNG (progress hook của yt-dlp, đường tải thường) — khác hẳn ``byte_dau_ra``.
    byte_da_nhan: Optional[int] = None
    byte_tong: Optional[int] = None
    # Byte ffmpeg đã GHI ra file khi tải một phần (``-progress total_size`` / kích thước file đang ghi):
    # dung lượng ĐẦU RA của muxer, không phải byte mạng (ffmpeg đọc trước vào bộ đệm, khác vỏ container).
    byte_dau_ra: Optional[int] = None
    toc_do_byte_s: Optional[float] = None
    toc_do_x: Optional[float] = None          # ffmpeg: giây audio / giây thực
    audio_da_nhan_s: Optional[float] = None
    audio_can_s: Optional[float] = None
    khuc_tong: Optional[int] = None
    khuc_xong: Optional[int] = None
    khuc_hien_tai: str = ""
    khop_tong: Optional[int] = None
    khop_xong: Optional[int] = None
    so_dat_chuan: Optional[int] = None
    eta_buoc_s: Optional[float] = None

    @property
    def ten_giai_doan(self) -> str:
        return TEN_GIAI_DOAN.get(self.giai_doan, self.giai_doan)

    @property
    def ty_le_buoc(self) -> Optional[float]:
        """Phần đã xong của BƯỚC hiện tại — chỉ khi có mẫu số đo được; không bao giờ 1.0 trước khi xong."""
        a, b = None, None
        if self.giai_doan == GD_TAI:
            if self.audio_can_s and self.audio_da_nhan_s is not None:
                a, b = self.audio_da_nhan_s, self.audio_can_s
            elif self.byte_tong and self.byte_da_nhan is not None:
                a, b = self.byte_da_nhan, self.byte_tong
        elif self.giai_doan == GD_CAT and self.khuc_tong:
            a, b = self.khuc_xong or 0, self.khuc_tong
        elif self.giai_doan == GD_KHOP and self.khop_tong:
            a, b = self.khop_xong or 0, self.khop_tong
        if a is None or not b:
            return None
        return max(0.0, min(0.99, float(a) / float(b)))

    def cham(self, bay_gio: Optional[float] = None) -> float:
        """Đã bao lâu không có tiến triển mới (giây)."""
        bay_gio = time.time() if bay_gio is None else bay_gio
        return max(0.0, bay_gio - (self.tien_trien_luc or bay_gio))

    def nhip_cach(self, bay_gio: Optional[float] = None) -> Optional[float]:
        bay_gio = time.time() if bay_gio is None else bay_gio
        return None if not self.nhip_luc else max(0.0, bay_gio - self.nhip_luc)

    def canh_bao(self, bay_gio: Optional[float] = None) -> str:
        """Câu cảnh báo khi quá lâu không có tiến triển; rỗng nếu bình thường."""
        nguong = NGUONG_CHAM_S.get(self.giai_doan)
        if nguong is None:
            return ""
        cham = self.cham(bay_gio)
        if cham < nguong:
            return ""
        nhip = self.nhip_cach(bay_gio)
        con_song = nhip is not None and nhip < NHIP_CON_SONG_S
        if self.giai_doan == GD_TAI:
            return (f"Đang chờ phản hồi mạng lâu bất thường — {int(cham)} giây không nhận thêm dữ liệu "
                    "audio." + (" Tiến trình tải vẫn còn chạy." if con_song else ""))
        if self.giai_doan == GD_METADATA:
            return f"YouTube chưa trả thông tin video sau {int(cham)} giây — đang chờ phản hồi mạng."
        if con_song:
            return (f"Không có tiến triển mới trong {int(cham)} giây — tiến trình vẫn còn hoạt động "
                    f"(nhịp {int(nhip)} giây trước); bước này có thể dài.")
        return f"Không có tiến triển mới trong {int(cham)} giây — cần kiểm tra."


class SoTienDo:
    """Sổ tiến độ của MỘT lô quét. An toàn đa luồng; ghi rẻ (một khoá, vài phép gán)."""

    def __init__(self, toi_da_su_kien: int = 200):
        self._lock = threading.Lock()
        self._anh = AnhTienDo()
        self._su_kien: deque = deque(maxlen=toi_da_su_kien)
        # Mẫu (thời điểm, giá trị) để tính tốc độ thật cho ETA của bước hiện tại.
        self._mau: deque = deque(maxlen=60)

    # ---------- ghi ----------

    def bat_dau_lo(self, batch_id: str, tong: int) -> None:
        with self._lock:
            self._anh = AnhTienDo(batch_id=batch_id, tong=tong)
            self._su_kien.clear()
            self._mau.clear()

    def bat_dau_video(self, index: int, tong: int, nguon: str) -> None:
        bay_gio = time.time()
        with self._lock:
            self._anh = AnhTienDo(batch_id=self._anh.batch_id, index=index, tong=tong, nguon=nguon,
                                  giai_doan=GD_CHO, giai_doan_luc=bay_gio, bat_dau_luc=bay_gio,
                                  nhip_luc=bay_gio, tien_trien_luc=bay_gio)
            self._mau.clear()
            self._them_su_kien(bay_gio, f"Bắt đầu video {index}/{tong}")

    def cap_nhat(self, giai_doan: Optional[str] = None, ghi: str = "", **truong) -> None:
        """Đổi giai đoạn / gán số đo. Giai đoạn mới hoặc số đo TĂNG = có tiến triển."""
        bay_gio = time.time()
        with self._lock:
            cu = self._anh
            thay = {k: v for k, v in truong.items() if hasattr(cu, k)}
            tien_trien = False
            if giai_doan and giai_doan != cu.giai_doan:
                thay["giai_doan"] = giai_doan
                thay["giai_doan_luc"] = bay_gio
                thay["eta_buoc_s"] = None
                self._mau.clear()
                tien_trien = True
            for k in _SO_HOC:
                if k in thay and thay[k] is not None and (getattr(cu, k) is None
                                                          or thay[k] > getattr(cu, k)):
                    tien_trien = True
            # Thông tin MỚI (thời lượng nguồn, phạm vi, tổng số khúc…) cũng là tiến triển; số đo
            # tốc độ thì không — tốc độ đổi mà không thêm byte nào vẫn là đứng yên.
            if any(k not in _SO_HOC and k not in _KHONG_PHAI_TIEN_TRIEN and thay[k] != getattr(cu, k)
                   for k in thay):
                tien_trien = True
            thay["nhip_luc"] = bay_gio
            if tien_trien:
                thay["tien_trien_luc"] = bay_gio
            moi = replace(cu, **thay)
            moi = replace(moi, eta_buoc_s=self._eta(moi, bay_gio))
            self._anh = moi
            if ghi:
                self._them_su_kien(bay_gio, ghi)

    def nhip(self) -> None:
        """Tiến trình còn sống, KHÔNG phải tiến triển."""
        with self._lock:
            self._anh = replace(self._anh, nhip_luc=time.time())

    def ghi(self, noi_dung: str) -> None:
        with self._lock:
            self._them_su_kien(time.time(), noi_dung)

    def _them_su_kien(self, luc: float, noi_dung: str) -> None:
        noi_dung = " ".join(str(noi_dung).split())[:300]
        if not noi_dung:
            return
        if self._su_kien and self._su_kien[-1].noi_dung == noi_dung:
            return
        self._su_kien.append(SuKien(luc, noi_dung))

    def _eta(self, a: AnhTienDo, bay_gio: float) -> Optional[float]:
        """ETA của BƯỚC hiện tại từ tốc độ ĐO được; ``None`` khi chưa đủ dữ liệu."""
        if a.giai_doan == GD_TAI and a.audio_can_s and a.audio_da_nhan_s is not None:
            gia_tri, can = a.audio_da_nhan_s, a.audio_can_s
        elif a.giai_doan == GD_TAI and a.byte_tong and a.byte_da_nhan is not None:
            gia_tri, can = float(a.byte_da_nhan), float(a.byte_tong)
        elif a.giai_doan == GD_CAT and a.khuc_tong and a.khuc_xong is not None:
            gia_tri, can = float(a.khuc_xong), float(a.khuc_tong)
        elif a.giai_doan == GD_KHOP and a.khop_tong and a.khop_xong is not None:
            gia_tri, can = float(a.khop_xong), float(a.khop_tong)
        else:
            return None
        if not self._mau or self._mau[-1][1] != gia_tri:
            self._mau.append((bay_gio, gia_tri))
        dau = next((m for m in self._mau if m[1] < gia_tri), None)
        if dau is None or bay_gio - dau[0] < CUA_SO_TOC_DO_S:
            return None
        toc_do = (gia_tri - dau[1]) / (bay_gio - dau[0])
        if toc_do <= 0 or gia_tri >= can:
            return None
        return (can - gia_tri) / toc_do

    # ---------- đọc ----------

    def anh(self) -> AnhTienDo:
        with self._lock:
            return self._anh

    def su_kien(self, n: int = 20) -> list:
        with self._lock:
            return list(self._su_kien)[-n:]
