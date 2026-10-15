# -*- coding: utf-8 -*-
"""Tiến độ + hiệu suất của MỘT lượt đồng bộ kênh (``channel.ChannelSync.sync``) — số đo có cấu trúc, an toàn luồng.

Worker (luồng đồng bộ, hook tiến độ của yt-dlp, luồng đọc ``-progress`` của FFmpeg) chỉ GHI vào :class:`SoDongBo`;
giao diện chỉ ĐỌC ảnh chụp bất biến :class:`AnhDongBo` (:meth:`SoDongBo.anh`) — worker không bao giờ gọi Streamlit.
Không suy số liệu từ chữ trên giao diện. Không lưu cookie, header, URL hay đường dẫn: chỉ mã video, tiêu đề (cắt ngắn),
số đo, loại lỗi.

Chi phí thấp: một khoá, cập nhật byte/FFmpeg được GỘP NHỊP (``NHIP_TAI_S``/``NHIP_FFMPEG_S`` — hook yt-dlp có thể gọi
hàng trăm lần/giây), mọi hàng đợi đều có trần (``TRAN_MAU``, ``TRAN_SU_KIEN``). ETA chỉ có khi đủ dữ liệu và tốc độ ổn
định; không thì ``None`` = «Đang ước tính», không bịa số.
"""

from __future__ import annotations

import math
import re
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Optional

# Giai đoạn của video đang xử lý (và hai giai đoạn đầu lượt).
GD_LIET_KE = "LISTING"
GD_KIEM = "CHECKING"
GD_TRICH_XUAT = "EXTRACTING"
GD_CHO = "WAITING"
GD_TAI = "DOWNLOADING"
GD_NEN = "TRANSCODING"
GD_XAC_MINH = "VERIFYING"
GD_LUU = "SAVING"
TEN_GIAI_DOAN = {
    GD_LIET_KE: "Lấy danh sách video", GD_KIEM: "Kiểm file đã có", GD_TRICH_XUAT: "Hỏi YouTube (trích xuất)",
    GD_CHO: "Nghỉ giãn nhịp", GD_TAI: "Tải audio", GD_NEN: "Nén opus (FFmpeg)", GD_XAC_MINH: "Kiểm file (FFprobe)",
    GD_LUU: "Ghi metadata + archive",
}
# Giai đoạn được tính thời gian theo từng video (bảng hiệu suất).
GD_THEO_VIDEO = (GD_TRICH_XUAT, GD_CHO, GD_TAI, GD_NEN, GD_XAC_MINH, GD_LUU)

# Trạng thái tổng (tương ứng channel.DONG_BO_* khi kết thúc).
TT_DANG_CHAY = "RUNNING"
TT_MOT_PHAN = "PARTIAL"
TT_BI_CHAN = "BLOCKED"
TT_DA_HUY = "CANCELLED"
TT_XONG = "COMPLETED"
TU_DONG_BO = {"DAY_DU": TT_XONG, "MOT_PHAN": TT_MOT_PHAN, "BI_CHAN": TT_BI_CHAN, "DA_HUY": TT_DA_HUY}

NHIP_TAI_S = 0.25          # cập nhật byte tải tối đa 4 lần/giây
NHIP_FFMPEG_S = 0.5        # cập nhật tiến độ nén tối đa 2 lần/giây
TRAN_MAU = 500             # số video gần nhất giữ để tính trung vị / p95
TRAN_SU_KIEN = 50          # nhật ký gần nhất
TRAN_TIEU_DE = 90
ETA_TOI_THIEU_VIDEO = 5    # dưới số video đã xét này: «Đang ước tính»
ETA_TOI_THIEU_S = 60.0
ETA_HE_SO_EWMA = 0.2
ETA_LECH_TOI_DA = 2.0      # EWMA lệch trung vị gần đây quá ×2 → tốc độ đang đổi mạnh → «Đang ước tính»
# «[download] Sleeping 3.2 seconds …» (nghỉ trước khi tải), «[youtube] Sleeping 1.0 seconds …» (giữa request), «Sleeping …» (chờ
# thử lại HTTP) — mọi dòng nghỉ của yt-dlp 2026.08.19.
_RE_NGHI = re.compile(r"^(\[[^\]]+\] )?Sleeping ([0-9]+(?:\.[0-9]+)?) seconds(.*)$")


def _bach_phan_vi(ds: list, p: float) -> Optional[float]:
    if not ds:
        return None
    x = sorted(ds)
    k = (len(x) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return x[lo] if lo == hi else x[lo] + (x[hi] - x[lo]) * (k - lo)


@dataclass(frozen=True)
class ThongKe:
    """Thống kê thời gian (giây) của một công đoạn trên các video gần nhất."""
    so_mau: int = 0
    trung_vi: Optional[float] = None
    p95: Optional[float] = None
    tong: float = 0.0


@dataclass(frozen=True)
class AnhVideo:
    chi_so: int                          # 1-based trong danh sách sẽ thử của lượt này
    tong: int
    video_id: str
    tieu_de: str
    giai_doan: str
    bat_dau: float                       # time.time()
    giai_doan_bat_dau: float
    byte_tai: Optional[int] = None
    byte_tong: Optional[int] = None      # None = chưa biết
    toc_do_tai: Optional[float] = None   # byte/giây (yt-dlp đo trên byte thật)
    eta_tai_s: Optional[float] = None
    nghi_du_kien_s: Optional[float] = None
    nghi_ly_do: str = ""
    dinh_dang: str = ""                  # vd. "251 webm opus (audio)" / "18 mp4 avc1+mp4a (CÓ HÌNH)"
    chi_audio: Optional[bool] = None     # None = chưa biết
    client: str = ""
    so_audio_san_co: Optional[int] = None   # số định dạng CHỈ-TIẾNG client đã cung cấp (bằng chứng)
    so_dinh_dang: Optional[int] = None
    ffmpeg_da_s: Optional[float] = None  # out_time đã nén
    ffmpeg_tong_s: Optional[float] = None
    ffmpeg_toc_do_x: Optional[float] = None
    so_doi_client: int = 0

    @property
    def ty_le_tai(self) -> Optional[float]:
        if self.byte_tai is None or not self.byte_tong:
            return None
        return max(0.0, min(1.0, self.byte_tai / self.byte_tong))

    @property
    def ty_le_nen(self) -> Optional[float]:
        if self.ffmpeg_da_s is None or not self.ffmpeg_tong_s:
            return None
        return max(0.0, min(1.0, self.ffmpeg_da_s / self.ffmpeg_tong_s))


@dataclass(frozen=True)
class SuKien:
    luc: float
    noi_dung: str


@dataclass(frozen=True)
class AnhDongBo:
    """Ảnh chụp BẤT BIẾN — giao diện đọc, không bao giờ sửa."""
    trang_thai: str = TT_DANG_CHAY
    bat_dau: float = 0.0
    ket_thuc: Optional[float] = None
    giai_doan_luot: str = GD_LIET_KE
    tong_kenh: Optional[int] = None
    da_co: Optional[int] = None
    can_tai: Optional[int] = None
    se_thu: Optional[int] = None         # can_tai trừ video đã biết bị hạn chế (bỏ qua)
    kiem_da: int = 0
    kiem_tong: int = 0
    moi: int = 0
    loi: int = 0
    gioi_han_tuoi: int = 0
    chi_hoi_vien: int = 0
    han_che_bo_qua: int = 0
    video: Optional[AnhVideo] = None
    thong_ke: dict = field(default_factory=dict)   # giai đoạn | "VIDEO" -> ThongKe
    byte_tai_tong: int = 0
    byte_nen_tong: int = 0
    media_s_tong: float = 0.0
    nghi_tong_s: float = 0.0
    doi_client_tong: int = 0
    tai_co_hinh: int = 0                 # số video tải về là định dạng CÓ HÌNH (không có audio-only)
    eta_s: Optional[float] = None
    eta_ly_do: str = ""                  # vì sao chưa có ETA
    eta_tin_cay: str = ""                # "cao" | "trung bình" | ""
    ly_do_dung: str = ""
    dang_nhap: str = ""
    su_kien: tuple = ()
    luc_anh: float = 0.0

    @property
    def da_xet(self) -> int:
        return self.moi + self.loi

    @property
    def chua_thu(self) -> Optional[int]:
        if self.se_thu is None:
            return None
        return max(0, self.se_thu - self.da_xet)

    @property
    def chay_s(self) -> float:
        return max(0.0, (self.ket_thuc or self.luc_anh) - self.bat_dau) if self.bat_dau else 0.0

    @property
    def ty_le(self) -> Optional[float]:
        """Phần đã XÉT trên số video sẽ thử (video đã có/đã bỏ qua không tính) — None khi chưa biết."""
        if not self.se_thu:
            return 1.0 if self.se_thu == 0 else None
        return max(0.0, min(1.0, self.da_xet / self.se_thu))

    @property
    def video_moi_gio(self) -> Optional[float]:
        tk = self.thong_ke.get("LUOT_VIDEO_S")
        if not self.moi or not tk or not tk.tong:
            return None
        return self.moi / (tk.tong / 3600.0)

    @property
    def media_gio_moi_gio(self) -> Optional[float]:
        tk = self.thong_ke.get("LUOT_VIDEO_S")
        if not self.media_s_tong or not tk or not tk.tong:
            return None
        return (self.media_s_tong / 3600.0) / (tk.tong / 3600.0)

    @property
    def diem_nghen(self) -> Optional[tuple]:
        """``(giai đoạn, tổng giây, tỷ lệ)`` chiếm nhiều thời gian nhất trên các video đã xét."""
        tong = {gd: self.thong_ke[gd].tong for gd in GD_THEO_VIDEO if gd in self.thong_ke and self.thong_ke[gd].tong}
        if not tong:
            return None
        gd = max(tong, key=tong.get)
        return gd, tong[gd], tong[gd] / sum(tong.values())


class SoDongBo:
    """Sổ tiến độ của một lượt đồng bộ: worker ghi, giao diện đọc ``anh()``. Mọi phương thức đều an toàn luồng và
    KHÔNG BAO GIỜ ném lỗi ra worker (đo đạc hỏng không được làm hỏng lượt đồng bộ)."""

    def __init__(self, dong_ho: Callable[[], float] = time.time,
                 dong_ho_don_dieu: Callable[[], float] = time.perf_counter):
        self._now = dong_ho
        self._mono = dong_ho_don_dieu
        self._khoa = threading.Lock()
        self._anh = AnhDongBo(bat_dau=self._now(), luc_anh=self._now())
        self._su_kien: deque = deque(maxlen=TRAN_SU_KIEN)
        self._mau: dict = {gd: deque(maxlen=TRAN_MAU) for gd in (*GD_THEO_VIDEO, "VIDEO")}
        self._tong_gd: dict = {gd: 0.0 for gd in (*GD_THEO_VIDEO, "VIDEO", "LUOT_VIDEO_S")}
        self._gd_video: dict = {}             # giai đoạn -> giây của video đang xử lý
        self._gd_moc: Optional[float] = None  # mốc đơn điệu của giai đoạn hiện tại
        self._video_moc: Optional[float] = None
        self._chu_ky: deque = deque(maxlen=20)  # giây giữa hai video xét xong liên tiếp
        self._ewma: Optional[float] = None
        self._xet_moc: Optional[float] = None
        self._nhip_tai = 0.0
        self._nhip_ffmpeg = 0.0
        self._ffmpeg_moc: Optional[float] = None
        self._nghi_trong_gd = 0.0          # giây nghỉ yt-dlp đã báo trong giai đoạn hiện tại

    # ---------- nội bộ ----------

    def _ghi(self, noi_dung: str) -> None:
        noi_dung = (noi_dung or "").strip()[:300]
        if noi_dung and not (self._su_kien and self._su_kien[-1].noi_dung == noi_dung):
            self._su_kien.append(SuKien(self._now(), noi_dung))

    def _dong_gd(self) -> None:
        """Cộng thời gian giai đoạn hiện tại của video vào bộ đếm của video; phần NGHỈ yt-dlp đã báo trong giai đoạn
        (nghỉ giữa request, chờ thử lại) được tính vào WAITING thay vì giai đoạn đó."""
        v = self._anh.video
        if v is None or self._gd_moc is None:
            return
        troi = max(0.0, self._mono() - self._gd_moc)
        nghi = min(self._nghi_trong_gd, troi)
        self._nghi_trong_gd = 0.0
        if v.giai_doan in GD_THEO_VIDEO:
            self._gd_video[v.giai_doan] = self._gd_video.get(v.giai_doan, 0.0) + troi - nghi
            if nghi:
                self._gd_video[GD_CHO] = self._gd_video.get(GD_CHO, 0.0) + nghi
        self._gd_moc = self._mono()

    def _an_toan(ham):  # noqa: N805 — trang trí nội bộ
        def boc(self, *a, **k):
            try:
                with self._khoa:
                    return ham(self, *a, **k)
            except Exception:  # noqa: BLE001 — đo đạc không được làm hỏng lượt đồng bộ
                return None
        boc.__name__ = ham.__name__
        boc.__doc__ = ham.__doc__
        return boc

    # ---------- cả lượt ----------

    @_an_toan
    def liet_ke(self) -> None:
        self._anh = replace(self._anh, giai_doan_luot=GD_LIET_KE)
        self._ghi("Đang lấy danh sách video của kênh…")

    @_an_toan
    def liet_ke_xong(self, tong: int) -> None:
        self._anh = replace(self._anh, tong_kenh=int(tong))
        self._ghi(f"Kênh có {int(tong)} video.")

    @_an_toan
    def kiem(self, da: int, tong: int) -> None:
        self._anh = replace(self._anh, giai_doan_luot=GD_KIEM, kiem_da=int(da), kiem_tong=int(tong))

    @_an_toan
    def ke_hoach(self, da_co: int, can_tai: int, han_che_bo_qua: int, se_thu: int) -> None:
        self._anh = replace(self._anh, da_co=int(da_co), can_tai=int(can_tai), han_che_bo_qua=int(han_che_bo_qua),
                            se_thu=int(se_thu), giai_doan_luot=GD_TRICH_XUAT)
        self._xet_moc = self._mono()
        self._ghi(f"Đã có {da_co} video (giữ nguyên); cần tải {can_tai}"
                  + (f", bỏ qua {han_che_bo_qua} video đã biết bị hạn chế" if han_che_bo_qua else "") + ".")

    @_an_toan
    def dang_nhap(self, cau: str) -> None:
        self._anh = replace(self._anh, dang_nhap=str(cau or "")[:300])

    @_an_toan
    def ket_thuc(self, trang_thai_dong_bo: str, ly_do_dung: str = "") -> None:
        if self._anh.video is not None:
            self._dong_gd()
        tt = TU_DONG_BO.get(trang_thai_dong_bo, TT_MOT_PHAN)
        self._anh = replace(self._anh, trang_thai=tt, ket_thuc=self._now(), video=None,
                            ly_do_dung=str(ly_do_dung or "")[:400])
        self._ghi({TT_XONG: "Đồng bộ xong.", TT_MOT_PHAN: "Đồng bộ xong MỘT PHẦN.", TT_BI_CHAN: "Đồng bộ DỪNG giữa chừng.",
                   TT_DA_HUY: "Đã dừng theo yêu cầu."}[tt])

    # ---------- từng video ----------

    @_an_toan
    def video_bat_dau(self, chi_so: int, tong: int, video_id: str, tieu_de: str) -> None:
        now = self._now()
        self._gd_video = {}
        self._gd_moc = self._video_moc = self._mono()
        self._nhip_tai = 0.0         # cập nhật tải ĐẦU TIÊN của video mới luôn được nhận (mang định dạng)
        self._nghi_trong_gd = 0.0
        self._anh = replace(self._anh, video=AnhVideo(
            chi_so=int(chi_so), tong=int(tong), video_id=str(video_id)[:20], tieu_de=str(tieu_de or "")[:TRAN_TIEU_DE],
            giai_doan=GD_TRICH_XUAT, bat_dau=now, giai_doan_bat_dau=now), giai_doan_luot=GD_TRICH_XUAT)

    @_an_toan
    def giai_doan(self, gd: str, **truong: Any) -> None:
        v = self._anh.video
        if v is None:
            return
        if gd != v.giai_doan:
            self._dong_gd()
            v = replace(v, giai_doan=gd, giai_doan_bat_dau=self._now())
            if gd == GD_NEN:
                self._ffmpeg_moc = self._mono()
                v = replace(v, ffmpeg_da_s=None, ffmpeg_toc_do_x=None)
        if truong:
            v = replace(v, **{k: val for k, val in truong.items() if hasattr(v, k)})
        self._anh = replace(self._anh, video=v, giai_doan_luot=gd)

    def thong_diep_ytdlp(self, msg: str) -> None:
        """Thông điệp ``to_screen`` của yt-dlp (qua ``logger.debug``): chỉ nhận dòng NGHỈ của chính yt-dlp. Lọc bằng chuỗi
        TRƯỚC khi lấy khoá — dòng tiến trình tải đến rất dày. Không bao giờ ném lỗi."""
        try:
            if "Sleeping" not in msg:
                return
        except Exception:  # noqa: BLE001
            return
        self._ghi_nghi(str(msg))

    @_an_toan
    def _ghi_nghi(self, msg: str) -> None:
        v = self._anh.video
        m = _RE_NGHI.match(msg.strip())
        if v is None or not m:
            return
        s = float(m.group(2))
        if not (m.group(1) or "").startswith("[download]"):
            # Nghỉ giữa request (`sleep_interval_requests`, «[youtube] Sleeping…») / chờ thử lại HTTP: không đổi giai đoạn,
            # chỉ chuyển phần giây đã báo sang WAITING khi giai đoạn hiện tại khép lại.
            self._nghi_trong_gd += s
            return
        self._dong_gd()
        ly_do = "theo yêu cầu của trang" if "required by the site" in (m.group(3) or "") else "theo cấu hình giãn nhịp"
        self._anh = replace(self._anh, video=replace(v, giai_doan=GD_CHO, giai_doan_bat_dau=self._now(),
                                                     nghi_du_kien_s=s, nghi_ly_do=ly_do), giai_doan_luot=GD_CHO)

    def hook_tai(self, d: dict) -> None:
        """``progress_hooks`` của yt-dlp — gộp nhịp NGOÀI khoá (gọi rất dày). Không bao giờ ném lỗi."""
        try:
            trang_thai = d.get("status")
            if trang_thai == "downloading" and self._mono() - self._nhip_tai < NHIP_TAI_S:
                return
            self._nhip_tai = self._mono()
            self._cap_nhat_tai(d)
        except Exception:  # noqa: BLE001
            return

    @_an_toan
    def _cap_nhat_tai(self, d: dict) -> None:
        v = self._anh.video
        if v is None:
            return
        if v.giai_doan != GD_TAI:
            self._dong_gd()
            v = replace(v, giai_doan=GD_TAI, giai_doan_bat_dau=self._now())
        if not v.dinh_dang:
            v = replace(v, **_mo_ta_dinh_dang(d.get("info_dict") or {}))
        da = d.get("downloaded_bytes")
        tong = d.get("total_bytes") or d.get("total_bytes_estimate")
        v = replace(v, byte_tai=int(da) if isinstance(da, (int, float)) else v.byte_tai,
                    byte_tong=int(tong) if isinstance(tong, (int, float)) and tong > 0 else v.byte_tong,
                    toc_do_tai=float(d["speed"]) if isinstance(d.get("speed"), (int, float)) else v.toc_do_tai,
                    eta_tai_s=float(d["eta"]) if isinstance(d.get("eta"), (int, float)) else None)
        if d.get("status") == "finished":
            self._gd_video["BYTE"] = self._gd_video.get("BYTE", 0) + int(v.byte_tai or v.byte_tong or 0)
            v = replace(v, eta_tai_s=0.0)
        self._anh = replace(self._anh, video=v, giai_doan_luot=GD_TAI)

    def tien_do_ffmpeg(self, gia_tri: dict) -> None:
        """Callback ``-progress`` của FFmpeg (luồng đọc stdout) — gộp nhịp, không bao giờ ném lỗi."""
        try:
            if gia_tri.get("progress") != "end" and self._mono() - self._nhip_ffmpeg < NHIP_FFMPEG_S:
                return
            self._nhip_ffmpeg = self._mono()
            us = gia_tri.get("out_time_us") or gia_tri.get("out_time_ms")   # cả hai đều là micro giây (FFmpeg)
            self._cap_nhat_ffmpeg(int(us) / 1e6 if us not in (None, "", "N/A") else None)
        except Exception:  # noqa: BLE001
            return

    @_an_toan
    def _cap_nhat_ffmpeg(self, da_s: Optional[float]) -> None:
        v = self._anh.video
        if v is None or da_s is None or da_s < 0:
            return
        troi = self._mono() - self._ffmpeg_moc if self._ffmpeg_moc is not None else 0.0
        self._anh = replace(self._anh, video=replace(
            v, ffmpeg_da_s=da_s, ffmpeg_toc_do_x=(da_s / troi) if troi >= 0.5 else v.ffmpeg_toc_do_x))

    @_an_toan
    def doi_client(self, ten: str = "") -> None:
        """Gọi NGAY TRƯỚC lần thử với client kế tiếp (``thu_tung_client(truoc_khi_thu_lai=…)``) — chỉ khi thật sự đổi."""
        v = self._anh.video
        self._nhip_tai = 0.0
        if v is not None:
            self._dong_gd()
            self._anh = replace(self._anh, video=replace(
                v, giai_doan=GD_TRICH_XUAT, giai_doan_bat_dau=self._now(), so_doi_client=v.so_doi_client + 1,
                byte_tai=None, byte_tong=None, dinh_dang="", chi_audio=None, so_audio_san_co=None, so_dinh_dang=None),
                giai_doan_luot=GD_TRICH_XUAT)
        self._anh = replace(self._anh, doi_client_tong=self._anh.doi_client_tong + 1)
        self._ghi("Thử player client khác" + (f" sau lỗi ở client {ten}" if ten else "") + ".")

    @_an_toan
    def client_thanh_cong(self, ten: str) -> None:
        v = self._anh.video
        if v is not None:
            self._anh = replace(self._anh, video=replace(v, client=str(ten or "mặc định")[:20]))

    @_an_toan
    def video_xong(self, ket_qua: str, *, loai: str = "", ly_do: str = "", media_s: Optional[float] = None,
                   byte_nen: Optional[int] = None) -> None:
        """``ket_qua``: ``"moi"`` (tải + kiểm + ghi xong) hoặc ``"loi"`` (``loai`` = loại lỗi truy cập)."""
        v = self._anh.video
        if v is None:
            return
        self._dong_gd()
        now_m = self._mono()
        tong_video = max(0.0, now_m - (self._video_moc or now_m))
        a = self._anh
        for gd in GD_THEO_VIDEO:
            if gd in self._gd_video:            # đã đi qua giai đoạn này (kể cả rất ngắn)
                self._mau[gd].append(self._gd_video[gd])
                self._tong_gd[gd] += self._gd_video[gd]
        self._tong_gd["LUOT_VIDEO_S"] += tong_video
        thay = dict(nghi_tong_s=a.nghi_tong_s + self._gd_video.get(GD_CHO, 0.0),
                    byte_tai_tong=a.byte_tai_tong + int(self._gd_video.get("BYTE", 0)))
        if ket_qua == "moi":
            self._mau["VIDEO"].append(tong_video)
            self._tong_gd["VIDEO"] += tong_video
            thay.update(moi=a.moi + 1, media_s_tong=a.media_s_tong + float(media_s or 0.0),
                        byte_nen_tong=a.byte_nen_tong + int(byte_nen or 0),
                        tai_co_hinh=a.tai_co_hinh + (1 if v.chi_audio is False else 0))
            self._ghi(f"[{v.chi_so}/{v.tong}] Xong «{v.tieu_de[:60]}» trong {tong_video:.0f} s"
                      + (f" — tải {v.dinh_dang}" if v.dinh_dang else "")
                      + (f" — client {v.client or 'mặc định'} có {_so(v.so_audio_san_co)} định dạng chỉ-tiếng / "
                         f"{_so(v.so_dinh_dang)}" if v.chi_audio is False else "") + ".")
        else:
            thay.update(loi=a.loi + 1, gioi_han_tuoi=a.gioi_han_tuoi + (loai == "AGE_RESTRICTED"),
                        chi_hoi_vien=a.chi_hoi_vien + (loai == "MEMBERS_ONLY"))
            self._ghi(f"[{v.chi_so}/{v.tong}] Không tải được «{v.tieu_de[:60]}»: {loai or 'lỗi'}"
                      + (f" — {ly_do[:160]}" if ly_do else "") + ".")
        # Chu kỳ = thời gian thật giữa hai lần xét xong (gồm mọi thứ: hỏi YouTube, nghỉ, tải, nén, ghi).
        if self._xet_moc is not None:
            chu_ky = max(0.0, now_m - self._xet_moc)
            self._chu_ky.append(chu_ky)
            self._ewma = chu_ky if self._ewma is None else (
                ETA_HE_SO_EWMA * chu_ky + (1 - ETA_HE_SO_EWMA) * self._ewma)
        self._xet_moc = now_m
        self._gd_video = {}
        self._anh = replace(a, video=None, **thay)

    @_an_toan
    def ghi(self, noi_dung: str) -> None:
        self._ghi(noi_dung)

    # ---------- đọc ----------

    def anh(self) -> AnhDongBo:
        """Ảnh chụp bất biến (giao diện gọi ~1 lần/giây) — tính thống kê + ETA trên mẫu có trần."""
        with self._khoa:
            a = self._anh
            mau = {gd: list(d) for gd, d in self._mau.items()}
            tong = dict(self._tong_gd)
            chu_ky = list(self._chu_ky)
            ewma = self._ewma
            su_kien = tuple(self._su_kien)
            dang_video_s = (self._mono() - self._video_moc) if (a.video is not None and self._video_moc) else 0.0
        thong_ke = {gd: ThongKe(len(ds), _bach_phan_vi(ds, 0.5), _bach_phan_vi(ds, 0.95), tong.get(gd, 0.0))
                    for gd, ds in mau.items()}
        thong_ke["LUOT_VIDEO_S"] = ThongKe(a.da_xet, None, None, tong["LUOT_VIDEO_S"] + dang_video_s)
        eta, ly_do, tin_cay = _uoc_tinh(a, chu_ky, ewma, dang_video_s)
        return replace(a, thong_ke=thong_ke, eta_s=eta, eta_ly_do=ly_do, eta_tin_cay=tin_cay, su_kien=su_kien,
                       luc_anh=self._now())

    def tom_tat(self) -> dict:
        """Tóm tắt hiệu suất (dict thuần, không bí mật) cho kết quả lượt đồng bộ / CLI / báo cáo. Không bao giờ ném
        lỗi (gọi trong ``finally`` của lượt đồng bộ)."""
        try:
            return self._tom_tat()
        except Exception:  # noqa: BLE001
            return {}

    def _tom_tat(self) -> dict:
        a = self.anh()
        ra = {"chay_s": round(a.chay_s, 1), "moi": a.moi, "loi": a.loi, "byte_tai": a.byte_tai_tong,
              "byte_nen": a.byte_nen_tong, "media_s": round(a.media_s_tong, 1), "nghi_s": round(a.nghi_tong_s, 1),
              "doi_client": a.doi_client_tong, "tai_co_hinh": a.tai_co_hinh,
              "video_moi_gio": round(a.video_moi_gio, 1) if a.video_moi_gio else None,
              "media_gio_moi_gio": round(a.media_gio_moi_gio, 2) if a.media_gio_moi_gio else None,
              "giai_doan": {gd: {"n": tk.so_mau, "trung_vi_s": _tron(tk.trung_vi), "p95_s": _tron(tk.p95),
                                 "tong_s": round(tk.tong, 1)}
                            for gd, tk in a.thong_ke.items() if gd in (*GD_THEO_VIDEO, "VIDEO")}}
        nghen = a.diem_nghen
        ra["diem_nghen"] = {"giai_doan": nghen[0], "tong_s": round(nghen[1], 1), "ty_le": round(nghen[2], 3)} if nghen \
            else None
        return ra


def _so(x: Optional[int]) -> str:
    return "?" if x is None else str(x)


def _tron(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(x, 2)


def _uoc_tinh(a: AnhDongBo, chu_ky: list, ewma: Optional[float], dang_video_s: float = 0.0) -> tuple:
    """``(eta giây | None, lý do khi None, độ tin cậy)`` — EWMA của CHU KỲ thật giữa các video xét xong."""
    if a.trang_thai != TT_DANG_CHAY:
        return None, "Lượt đã kết thúc.", ""
    con = a.chua_thu
    if con is None:
        return None, "Chưa biết số video cần tải.", ""
    if con == 0:
        return 0.0, "", "cao"
    if len(chu_ky) < ETA_TOI_THIEU_VIDEO or ewma is None or sum(chu_ky) < ETA_TOI_THIEU_S:
        return None, (f"Đang ước tính — cần ít nhất {ETA_TOI_THIEU_VIDEO} video và "
                      f"{ETA_TOI_THIEU_S:.0f} giây số đo."), ""
    trung_vi = statistics.median(chu_ky)
    if trung_vi > 0 and not (1 / ETA_LECH_TOI_DA <= ewma / trung_vi <= ETA_LECH_TOI_DA):
        return None, "Đang ước tính — tốc độ đang thay đổi mạnh (vd. loạt video bị hạn chế / video dài).", ""
    tb = statistics.fmean(chu_ky)
    lech = statistics.pstdev(chu_ky) / tb if tb > 0 else 0.0
    # Đếm lùi trong lúc xử lý video hiện tại (đã tính trong `con`).
    return max(0.0, con * ewma - dang_video_s), "", ("cao" if len(chu_ky) >= 15 and lech < 0.5 else "trung bình")


def _mo_ta_dinh_dang(info: dict) -> dict:
    """Định dạng yt-dlp đã chọn — chỉ mã/đuôi/codec/dung lượng, không URL."""
    vc = str(info.get("vcodec") or "")
    ac = str(info.get("acodec") or "")
    chi_audio = None if not (vc or ac) else (vc in ("none", "") and ac not in ("none", ""))
    co_hinh = chi_audio is False
    bit = " ".join(x for x in (str(info.get("format_id") or ""), str(info.get("ext") or ""),
                               (ac if chi_audio else f"{vc.split('.')[0]}+{ac.split('.')[0]}") if (vc or ac) else "")
                   if x)
    ds = info.get("formats")
    ds = ds if isinstance(ds, list) else None
    so_audio = None if ds is None else sum(
        1 for f in ds if isinstance(f, dict) and str(f.get("vcodec") or "") == "none"
        and str(f.get("acodec") or "none") != "none")
    return {"dinh_dang": (bit + (" (CÓ HÌNH — không có audio-only)" if co_hinh else " (audio)" if chi_audio else ""))[:80],
            "chi_audio": chi_audio, "so_audio_san_co": so_audio, "so_dinh_dang": None if ds is None else len(ds)}
