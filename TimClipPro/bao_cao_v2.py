# -*- coding: utf-8 -*-
"""Chính sách báo cáo V2: dữ liệu báo cáo CHỤP một lần khi lượt quét kết thúc.

Vì sao có module này
====================
Báo cáo cũ được DỰNG LẠI mỗi lần xuất từ ``ScanResult`` + resolver metadata của kho ĐANG
chọn lúc xuất, kèm vài quy tắc trình bày rải ở nhiều nơi: tên video bị nối hậu tố
``[QUÉT MỘT PHẦN — …]``, link nhảy mốc ở bảng ngang lùi 3 giây, ngày đăng đã quy đổi sang
múi giờ hiển thị, link video gốc dạng ``youtu.be``. V2 đổi bốn điều đó cho LƯỢT QUÉT MỚI:

1. tên video chỉ là tên nguồn (``yt-dlp`` ``title``); phạm vi quét nằm ở trường riêng;
2. link nhảy mốc dùng ĐÚNG giây đang hiển thị: ``00:15:15`` ↔ ``t=915``;
3. ngày đăng là ``upload_date`` NGUYÊN BẢN của yt-dlp, không quy đổi múi giờ; thiếu thì để
   thiếu kèm lý do, không đoán từ ``timestamp``/``release_*``/tên file;
4. link video gốc ``https://www.youtube.com/watch?v=<ID>`` dựng từ ID đã xác minh.

Vòng đời (xem docs/REPORT_POLICY_V2.md)
======================================
* Chính sách được GHIM một lần ở ranh giới tạo job (``Engine._ban_sao_cho_job``); ảnh chụp
  ``BaoCaoV2`` được chốt sau chọn lọc + bổ sung ngày, trước khi lưu lịch sử / xếp hàng
  Sheets / xuất. Ảnh chụp chỉ chứa GIÁ TRỊ (không tham chiếu config/resolver).
* Kết quả KHÔNG có ảnh chụp là kết quả theo luật cũ — exporter cũ giữ nguyên, không bao giờ
  tự nâng thành V2. Bản ghi lịch sử thiếu ảnh chụp cũng vậy.
* Lượt quét V2 mà ảnh chụp KHÔNG dựng được, hoặc ảnh chụp đã lưu KHÔNG đọc được, mang
  ``LoiBaoCaoV2`` — không bao giờ ``None`` (``None`` chỉ còn một nghĩa: luật cũ thật). Kết quả
  khớp giữ nguyên; mọi exporter và đường gửi Sheets CHẶN (``LoiXuatBaoCaoV2``), không lùi về
  tên/ngày/link của luật cũ (audit P1-02).
* Xuất lại (kể cả sau khi khởi động lại app) dựng TỪ ẢNH CHỤP, không hỏi resolver hiện tại.

Module THUẦN: không I/O, không mạng, không Streamlit. Escape công thức bảng tính là việc
của tầng ghi CSV; giá trị ở đây là giá trị nguồn nguyên văn.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Iterable, Mapping, Optional

from clip_metadata import YOUTUBE_ID_PATTERN, valid_upload_date, youtube_ids_from_url

CHINH_SACH_V2 = "v2"
# Chính sách mà job MỚI được ghim. Chỉ ``Engine._ban_sao_cho_job`` đọc hằng này; exporter
# luôn đọc chính sách từ BẢN GHI (ảnh chụp), không bao giờ từ đây.
CHINH_SACH_HIEN_HANH = CHINH_SACH_V2
# Phiên bản cấu trúc dữ liệu của ảnh chụp (đổi khi đổi trường, để bộ đọc biết cách đọc).
PHIEN_BAN_ANH_CHUP = 1

NGUON_UPLOAD_DATE = "yt_dlp.upload_date"
NGUON_TIEU_DE_YTDLP = "yt_dlp.title"
NGUON_TIEU_DE_TEN_FILE = "ten_file"
NGUON_TIEU_DE_KHO = "clips_meta"
NGUON_TIEU_DE_TEN_FILE_KHO = "ten_file_kho"

DINH_DANG_THOI_DIEM = "%Y-%m-%d %H:%M:%S"
DAU_KHONG_HOP_LE = "?"

HEADER_PHAM_VI = [
    "Link video vi phạm", "Tên video vi phạm", "Phạm vi quét", "Mô tả phạm vi",
    "Lý do", "Vùng chưa kiểm", "Ghi chú", "Chính sách báo cáo",
]
_LY_DO_PHAM_VI = {
    "dung_som": "dừng sớm vì đã đủ bằng chứng",
    "gioi_han_tai": "chỉ tải phần đầu video",
    "loi_khuc": "có vùng không xử lý được",
    "tai_thieu": "file tải về thiếu phần cuối",
    "huy": "đã huỷ",
    "am_thanh_ngan_hon": "âm thanh YouTube ngắn hơn thời lượng video — đã tải lại kiểm",
}


# =====================================================================
#  Quy tắc giá trị dùng chung (mốc, link, URL gốc, ngày)
# =====================================================================

def giay_moc(gia_tri: Any) -> Optional[int]:
    """Giây nguyên DÙNG CHUNG cho ô hiển thị ``HH:MM:SS`` và tham số ``t`` của link.

    Cắt phần lẻ như ``engine.hhmmss`` (trình phát cắt, không làm tròn): 915,8 → 915.
    Không phải số thực hữu hạn không âm (NaN, vô cực, âm, bool, chuỗi, None) → ``None``:
    không bao giờ biến dữ liệu hỏng thành một mốc trông hợp lệ.
    """
    if isinstance(gia_tri, bool) or not isinstance(gia_tri, (int, float)):
        return None
    so = float(gia_tri)
    if not math.isfinite(so) or so < 0:
        return None
    return int(math.floor(so))


def hien_thi_moc(giay: Optional[int]) -> str:
    """``HH:MM:SS`` của một giây đã qua ``giay_moc``; giờ có thể vượt 24 (video dài)."""
    if giay is None:
        return DAU_KHONG_HOP_LE
    return f"{giay // 3600:02d}:{(giay % 3600) // 60:02d}:{giay % 60:02d}"


def hien_thi_thoi_luong(gia_tri: Any) -> str:
    """Thời lượng > 0 → ``HH:MM:SS`` (cắt phần lẻ); không có/không hợp lệ → ``""``."""
    giay = giay_moc(gia_tri)
    return hien_thi_moc(giay) if giay else ""


def ma_video_hop_le(ma: Any) -> str:
    """Mã video YouTube 11 ký tự hợp lệ, hoặc ``""``."""
    if not isinstance(ma, str):
        return ""
    ma = ma.strip()
    return ma if YOUTUBE_ID_PATTERN.fullmatch(ma) else ""


def ma_tu_link(link: Any) -> str:
    """Mã video từ một URL YouTube THẬT (đúng host, đúng một mã); không phải URL → ``""``.

    Chỉ đọc URL: không suy mã từ tên file hay một cụm 11 ký tự trong tiêu đề, và không nhận
    host giả kiểu ``youtube.com.evil.example`` (xem ``clip_metadata.youtube_ids_from_url``).
    """
    ma = youtube_ids_from_url(link)
    return next(iter(ma)) if len(ma) == 1 else ""


def link_nhay(source_id: Any, source_ref: Any, giay: Optional[int]) -> str:
    """Link mở video vi phạm tại ĐÚNG giây ``giay`` (đã qua ``giay_moc``).

    Dựng mới từ mã video, không nối chuỗi vào URL người dùng (tránh hai tham số ``t`` mâu
    thuẫn, ``&start=``, ``#t=``...). Không có mã hợp lệ hoặc mốc không hợp lệ → ``""``.
    """
    if giay is None:
        return ""
    ma = ma_video_hop_le(source_id) or ma_tu_link(source_ref)
    return f"https://youtu.be/{ma}?t={giay}" if ma else ""


def url_goc_chuan(video_id: Any) -> str:
    """Link định danh video gốc: ``https://www.youtube.com/watch?v=<ID>`` hoặc ``""``."""
    ma = ma_video_hop_le(video_id)
    return f"https://www.youtube.com/watch?v={ma}" if ma else ""


def ngay_hop_le(gia_tri: Any) -> str:
    """Chuỗi ``YYYYMMDD`` là ngày có thật, hoặc ``""`` (không sửa, không đoán)."""
    return valid_upload_date(gia_tri) if isinstance(gia_tri, str) else ""


@dataclass(frozen=True)
class NgayNguon:
    """Ngày đăng kèm đường đi của nó. ``gia_tri`` rỗng = chưa có, ``ly_do_thieu`` nói vì sao."""
    gia_tri: str = ""
    nguon: str = ""
    ly_do_thieu: str = ""

    def hien_thi(self) -> str:
        """``DD/MM/YYYY`` giữ NGUYÊN ngày lịch của nguồn; chưa có → ``""``."""
        g = ngay_hop_le(self.gia_tri)
        return f"{g[6:8]}/{g[4:6]}/{g[0:4]}" if g else ""


def ngay_tu_info(info: Optional[Mapping]) -> NgayNguon:
    """Ngày đăng NGUYÊN BẢN của video được quét, từ dict ``Engine.youtube_info``.

    Đọc ``upload_date_raw`` — giá trị yt-dlp trả về TRƯỚC khi resolver cũ chọn/quy đổi.
    KHÔNG đọc ``upload_date`` của dict đó: ở tầng wrapper khoá này đã mang ngày quy đổi.
    """
    info = info or {}
    if "upload_date_raw" not in info:
        return NgayNguon(ly_do_thieu="thông tin video không có upload_date gốc của yt-dlp")
    tho = info.get("upload_date_raw")
    g = ngay_hop_le(tho)
    if g:
        return NgayNguon(gia_tri=g, nguon=NGUON_UPLOAD_DATE)
    if tho in (None, ""):
        return NgayNguon(ly_do_thieu="yt-dlp không trả upload_date")
    return NgayNguon(ly_do_thieu="upload_date của yt-dlp không phải ngày hợp lệ")


def tieu_de_tu_info(info: Optional[Mapping], source_ref: str = "") -> tuple:
    """``(tiêu đề, nguồn, lý do thiếu)`` của video YouTube được quét.

    Chỉ nhận tiêu đề yt-dlp trả về; ``Engine.youtube_info`` cũ lùi về URL khi thiếu tiêu đề —
    URL đó KHÔNG được coi là tên video.
    """
    info = info or {}
    if "title_raw" in info:
        tieu_de = info.get("title_raw")
    else:
        tieu_de = info.get("title")
        if tieu_de == source_ref or tieu_de == info.get("webpage_url"):
            tieu_de = ""
    if isinstance(tieu_de, str) and tieu_de.strip():
        return tieu_de, NGUON_TIEU_DE_YTDLP, ""
    if not info:
        return "", "", "chưa lấy được thông tin video"
    return "", "", "yt-dlp không trả tiêu đề video"


# =====================================================================
#  Ảnh chụp
# =====================================================================

@dataclass(frozen=True)
class GocV2:
    """Video gốc của một đoạn khớp, đã chốt giá trị lúc chụp."""
    clip: str
    video_id: str = ""
    url: str = ""                       # rỗng khi không xác minh được đúng MỘT mã video
    tieu_de: str = ""
    nguon_tieu_de: str = ""
    ngay_dang: NgayNguon = field(default_factory=NgayNguon)
    # Ngày kho đang lưu (đã quy đổi múi giờ theo chính sách cũ) — chỉ để chẩn đoán, KHÔNG
    # bao giờ được hiển thị như ngày đăng nguyên bản.
    ngay_kho_quy_doi: str = ""
    nguon_ngay_kho: str = ""
    thoi_luong_s: Optional[float] = None
    trang_thai_metadata: str = ""
    canh_bao: tuple = ()


@dataclass(frozen=True)
class DoanV2:
    """Một đoạn khớp đã chọn. Giữ NGUYÊN số thực của matching bên cạnh giây hiển thị."""
    goc: GocV2
    start_s: Optional[float]
    end_s: Optional[float]
    vung_khop_s: Optional[float]
    matched_s: float
    clip_offset_s: float
    hashes: int
    ty_le: float
    confidence: str
    vung: str
    giay_bat_dau: Optional[int]
    giay_ket_thuc: Optional[int]
    link: str


@dataclass(frozen=True)
class PhamViV2:
    """Trạng thái phạm vi quét — tách khỏi tên video nhưng không bao giờ bị bỏ."""
    quet_day_du: bool = False
    quet_mot_phan: bool = False
    ly_do: str = ""
    mo_ta: str = ""
    vung_da_khop: Optional[tuple] = None
    vung_loi: tuple = ()
    pham_vi_quet_s: float = 0.0
    dat_muc_tieu: bool = False


@dataclass(frozen=True)
class BaoCaoV2:
    """Ảnh chụp báo cáo của MỘT video vi phạm (một lượt quét)."""
    chinh_sach: str
    thoi_diem_quet: str
    trang_thai: str
    ghi_chu: str
    nguon_loai: str                     # youtube | file
    video_id: str
    link_video: str
    tieu_de: str
    nguon_tieu_de: str
    ly_do_thieu_tieu_de: str
    kenh_ten: str
    kenh_id: str
    kenh_link: str
    thoi_luong_s: float
    ngay_dang: NgayNguon
    pham_vi: PhamViV2
    doan: tuple
    so_dat_nguong: int
    co_ket_qua_loai: bool
    kho_id: str = ""
    kho_ten: str = ""
    kho_phien_ban: str = ""
    chinh_sach_nhan_dien: str = ""
    bo_sung_ngay: tuple = ()            # ((mã video, kết quả), …) — số lần hỏi YouTube
    phien_ban_anh_chup: int = PHIEN_BAN_ANH_CHUP

    # ---------- lưu / đọc ----------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping) -> "BaoCaoV2":
        """Đọc lại ảnh chụp đã lưu. Sai chính sách/cấu trúc → ``ValueError`` (không đoán)."""
        if not isinstance(d, Mapping) or d.get("chinh_sach") != CHINH_SACH_V2:
            raise ValueError("Ảnh chụp báo cáo không phải chính sách V2.")
        if int(d.get("phien_ban_anh_chup") or 0) != PHIEN_BAN_ANH_CHUP:
            raise ValueError("Phiên bản ảnh chụp báo cáo không được hỗ trợ.")

        def ngay(x) -> NgayNguon:
            x = x or {}
            return NgayNguon(gia_tri=str(x.get("gia_tri") or ""), nguon=str(x.get("nguon") or ""),
                             ly_do_thieu=str(x.get("ly_do_thieu") or ""))

        def goc(x) -> GocV2:
            return GocV2(
                clip=str(x["clip"]), video_id=str(x.get("video_id") or ""),
                url=str(x.get("url") or ""), tieu_de=str(x.get("tieu_de") or ""),
                nguon_tieu_de=str(x.get("nguon_tieu_de") or ""), ngay_dang=ngay(x.get("ngay_dang")),
                ngay_kho_quy_doi=str(x.get("ngay_kho_quy_doi") or ""),
                nguon_ngay_kho=str(x.get("nguon_ngay_kho") or ""),
                thoi_luong_s=x.get("thoi_luong_s"),
                trang_thai_metadata=str(x.get("trang_thai_metadata") or ""),
                canh_bao=tuple(x.get("canh_bao") or ()))

        def khoang(ds):
            return None if ds is None else tuple(tuple(float(v) for v in k) for k in ds)

        pv = d.get("pham_vi") or {}
        return cls(
            chinh_sach=CHINH_SACH_V2, thoi_diem_quet=str(d.get("thoi_diem_quet") or ""),
            trang_thai=str(d.get("trang_thai") or ""), ghi_chu=str(d.get("ghi_chu") or ""),
            nguon_loai=str(d.get("nguon_loai") or ""), video_id=str(d.get("video_id") or ""),
            link_video=str(d.get("link_video") or ""), tieu_de=str(d.get("tieu_de") or ""),
            nguon_tieu_de=str(d.get("nguon_tieu_de") or ""),
            ly_do_thieu_tieu_de=str(d.get("ly_do_thieu_tieu_de") or ""),
            kenh_ten=str(d.get("kenh_ten") or ""), kenh_id=str(d.get("kenh_id") or ""),
            kenh_link=str(d.get("kenh_link") or ""),
            thoi_luong_s=float(d.get("thoi_luong_s") or 0.0), ngay_dang=ngay(d.get("ngay_dang")),
            pham_vi=PhamViV2(
                quet_day_du=bool(pv.get("quet_day_du")), quet_mot_phan=bool(pv.get("quet_mot_phan")),
                ly_do=str(pv.get("ly_do") or ""), mo_ta=str(pv.get("mo_ta") or ""),
                vung_da_khop=khoang(pv.get("vung_da_khop")),
                vung_loi=khoang(pv.get("vung_loi") or ()) or (),
                pham_vi_quet_s=float(pv.get("pham_vi_quet_s") or 0.0),
                dat_muc_tieu=bool(pv.get("dat_muc_tieu"))),
            doan=tuple(DoanV2(
                goc=goc(x["goc"]), start_s=x.get("start_s"), end_s=x.get("end_s"),
                vung_khop_s=x.get("vung_khop_s"), matched_s=float(x.get("matched_s") or 0.0),
                clip_offset_s=float(x.get("clip_offset_s") or 0.0), hashes=int(x.get("hashes") or 0),
                ty_le=float(x.get("ty_le") or 0.0), confidence=str(x.get("confidence") or ""),
                vung=str(x.get("vung") or ""), giay_bat_dau=x.get("giay_bat_dau"),
                giay_ket_thuc=x.get("giay_ket_thuc"), link=str(x.get("link") or ""))
                for x in d.get("doan") or ()),
            so_dat_nguong=int(d.get("so_dat_nguong") or 0),
            co_ket_qua_loai=bool(d.get("co_ket_qua_loai")),
            kho_id=str(d.get("kho_id") or ""), kho_ten=str(d.get("kho_ten") or ""),
            kho_phien_ban=str(d.get("kho_phien_ban") or ""),
            chinh_sach_nhan_dien=str(d.get("chinh_sach_nhan_dien") or ""),
            bo_sung_ngay=tuple(tuple(x) for x in d.get("bo_sung_ngay") or ()),
        )


# =====================================================================
#  Lỗi báo cáo V2 — KHÔNG BAO GIỜ là luật cũ (audit P1-02)
# =====================================================================

LOI_TAO = "loi_tao"     # lượt quét mang chính sách V2 nhưng không dựng được ảnh chụp
LOI_HONG = "hong"       # ảnh chụp đã lưu không đọc được (JSON hỏng, cụt, phiên bản/chính sách lạ)
KHOA_LOI = "loi_bao_cao"
_TRUONG_ANH_CHUP = frozenset(f.name for f in fields(BaoCaoV2))


@dataclass(frozen=True)
class LoiBaoCaoV2:
    """Lượt quét THUỘC chính sách V2 mà không có ảnh chụp dùng được.

    Phân biệt với ``None`` (luật cũ thật): kết quả khớp, lịch sử, phạm vi vẫn giữ, nhưng mọi
    exporter và đường gửi Sheets phải CHẶN — không dựng bảng 34/16 cột, ngày, URL hay hậu tố tên
    theo luật cũ. Chỉ mang TÊN LỚP ngoại lệ (không thông điệp thô, không dict yt-dlp) nên lưu
    vào ``bao_cao_job`` an toàn; ``to_dict`` là dấu lỗi bền qua khởi động lại.
    """
    loai: str                           # LOI_TAO | LOI_HONG
    chinh_sach: str = CHINH_SACH_V2
    ngoai_le: str = ""

    def to_dict(self) -> dict:
        return {KHOA_LOI: {"loai": self.loai, "ngoai_le": self.ngoai_le}}

    def thong_bao(self) -> str:
        if self.loai == LOI_HONG:
            dau = "Báo cáo V2 đã lưu của lượt quét này bị hỏng, không đọc được."
        else:
            dau = ("Báo cáo V2 của lượt quét này không tạo được"
                   + (f" ({self.ngoai_le})" if self.ngoai_le else "") + ".")
        return (dau + " Kết quả khớp vẫn được giữ, nhưng không thể xuất báo cáo hoặc gửi Google "
                "Sheets cho tới khi lỗi báo cáo được xử lý — quét lại video này để có báo cáo mới.")


class LoiXuatBaoCaoV2(RuntimeError):
    """Đòi xuất/gửi một kết quả mang ``LoiBaoCaoV2`` — bị CHẶN, không lùi về luật cũ.

    ``vinh_vien``: hàng đợi Sheets không thử lại (thử lại không chữa được ảnh chụp).
    """
    vinh_vien = True


def la_loi_bao_cao(bc: Any) -> bool:
    return isinstance(bc, LoiBaoCaoV2)


def chan_neu_loi(bc: Any) -> None:
    """Chốt chặn ở mọi bộ dựng dòng V2: ảnh chụp lỗi/hỏng thì ném ``LoiXuatBaoCaoV2``."""
    if isinstance(bc, LoiBaoCaoV2):
        raise LoiXuatBaoCaoV2(bc.thong_bao())


def ten_ngoai_le(e: BaseException) -> str:
    """Tên lớp ngoại lệ đã làm sạch — điều DUY NHẤT về lỗi được lưu/ghi chú."""
    return re.sub(r"[^A-Za-z0-9_.]", "", type(e).__name__)[:80]


def doc_anh_chup_da_luu(chinh_sach: Any, du_lieu: Any) -> "BaoCaoV2 | LoiBaoCaoV2":
    """Đọc MỘT dòng ``bao_cao_job``. Có dòng = lượt quét V2, nên không bao giờ trả ``None``.

    Đọc được → ``BaoCaoV2``; dấu lỗi đã lưu → ``LoiBaoCaoV2(LOI_TAO)``; còn lại (JSON hỏng, không
    phải object, thiếu trường, phiên bản/chính sách lạ) → ``LoiBaoCaoV2(LOI_HONG)``. Không tái dựng
    bằng resolver hiện tại, không đoán.
    """
    try:
        d = json.loads(du_lieu)
    except (TypeError, ValueError):
        return LoiBaoCaoV2(LOI_HONG)
    if chinh_sach != CHINH_SACH_V2 or not isinstance(d, dict):
        return LoiBaoCaoV2(LOI_HONG)
    if KHOA_LOI in d:
        loi = d[KHOA_LOI]
        if isinstance(loi, dict) and loi.get("loai") == LOI_TAO:
            ten = re.sub(r"[^A-Za-z0-9_.]", "", str(loi.get("ngoai_le") or ""))[:80]
            return LoiBaoCaoV2(LOI_TAO, ngoai_le=ten)
        return LoiBaoCaoV2(LOI_HONG)
    if not _TRUONG_ANH_CHUP <= d.keys():
        return LoiBaoCaoV2(LOI_HONG)
    try:
        return BaoCaoV2.from_dict(d)
    except (ValueError, TypeError, KeyError, AttributeError):
        return LoiBaoCaoV2(LOI_HONG)


def tach_loi_bao_cao(ket: Iterable) -> tuple:
    """``(hợp lệ, có báo cáo V2 lỗi)`` — giữ thứ tự; nơi gọi xuất phần hợp lệ và BÁO phần lỗi."""
    hop_le, loi = [], []
    for kq in ket:
        (loi if la_loi_bao_cao(getattr(kq, "bao_cao", None)) else hop_le).append(kq)
    return hop_le, loi


def thong_bao_ket_qua_loi(loi: Iterable) -> str:
    """Một câu cho giao diện / Watch / CLI: lượt quét nào bị chặn xuất vì báo cáo V2 lỗi."""
    ten = [str(getattr(kq, "source_name", "") or getattr(kq, "source_ref", "")
               or "(không rõ nguồn)")[:80] for kq in loi]
    return (f"Báo cáo V2 của {len(ten)} lượt quét không tạo/đọc được: " + "; ".join(ten[:5])
            + (" …" if len(ten) > 5 else "") + ". Kết quả khớp vẫn được giữ trong lịch sử, nhưng "
            "không thể xuất báo cáo hoặc gửi Google Sheets cho tới khi lỗi báo cáo được xử lý — "
            "quét lại các video này để có báo cáo mới.")


def goc_tu_metadata(clip: str, meta: Any, ngay_bo_sung: Optional[NgayNguon] = None) -> GocV2:
    """Chốt thông tin video gốc từ một ``ResolvedClipMetadata`` (hoặc ``None``).

    * URL chỉ dựng từ ``video_id`` resolver đã xác minh (ambiguous/thiếu → rỗng);
    * ngày: ngày nguyên bản trong kho (``ngay_raw``, có nguồn rõ ràng) → ngày bổ sung từ
      yt-dlp → thiếu kèm lý do. Ngày kho đã quy đổi chỉ được giữ ở trường chẩn đoán.
    """
    if meta is None:
        return GocV2(clip=clip, ngay_dang=ngay_bo_sung or NgayNguon(
            ly_do_thieu="không đọc được metadata kho"), trang_thai_metadata="loi")
    video_id = ma_video_hop_le(getattr(meta, "video_id", ""))
    trang_thai = str(getattr(meta, "status", "") or "")
    if trang_thai == "ambiguous":
        video_id = ""
    raw = ngay_hop_le(getattr(meta, "ngay_raw", ""))
    ngay_kho = ngay_hop_le(getattr(meta, "upload_date", ""))
    nguon_ngay_kho = str(getattr(meta, "nguon_ngay", "") or "")
    if raw:
        ngay = NgayNguon(gia_tri=raw, nguon=str(getattr(meta, "nguon_ngay_raw", "") or ""))
    elif ngay_bo_sung is not None and ngay_bo_sung.gia_tri:
        ngay = ngay_bo_sung
    else:
        if not video_id:
            ly_do = "chưa xác minh được video gốc (metadata kho thiếu hoặc mơ hồ)"
        elif ngay_kho:
            ly_do = ("kho chỉ lưu ngày đã quy đổi múi giờ"
                     + (f" (nguồn: {nguon_ngay_kho})" if nguon_ngay_kho else "")
                     + " — chưa có upload_date gốc")
        else:
            ly_do = "kho không có ngày đăng"
        if ngay_bo_sung is not None and ngay_bo_sung.ly_do_thieu:
            ly_do = f"{ly_do}; {ngay_bo_sung.ly_do_thieu}"
        ngay = NgayNguon(ly_do_thieu=ly_do)
    phuong_phap = str(getattr(meta, "resolution_method", "") or "")
    tieu_de = str(getattr(meta, "title", "") or "")
    if phuong_phap in ("filename_fallback", "basename_fallback"):
        nguon_tieu_de = NGUON_TIEU_DE_TEN_FILE_KHO
    else:
        nguon_tieu_de = NGUON_TIEU_DE_KHO if tieu_de else ""
    thoi_luong = getattr(meta, "duration", None)
    if isinstance(thoi_luong, bool) or not isinstance(thoi_luong, (int, float)) \
            or not math.isfinite(float(thoi_luong)) or thoi_luong <= 0:
        thoi_luong = None
    return GocV2(
        clip=clip, video_id=video_id, url=url_goc_chuan(video_id), tieu_de=tieu_de,
        nguon_tieu_de=nguon_tieu_de, ngay_dang=ngay, ngay_kho_quy_doi=ngay_kho,
        nguon_ngay_kho=nguon_ngay_kho,
        thoi_luong_s=None if thoi_luong is None else float(thoi_luong),
        trang_thai_metadata=trang_thai,
        canh_bao=tuple(str(x) for x in (getattr(meta, "warnings", ()) or ())))


def _so_hoac_none(x: Any) -> Optional[float]:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    return float(x) if math.isfinite(float(x)) else None


def _khoang(ds) -> Optional[tuple]:
    if ds is None:
        return None
    return tuple((float(a), float(b)) for a, b in ds)


def dung_bao_cao(
    kq: Any,
    *,
    thoi_diem_quet: str,
    nguon_loai: str,
    tieu_de: str,
    nguon_tieu_de: str,
    ly_do_thieu_tieu_de: str,
    ngay_dang: NgayNguon,
    goc_theo_clip: Mapping[str, GocV2],
    mo_ta_pham_vi: str,
    bo_sung_ngay: Iterable = (),
) -> BaoCaoV2:
    """Lắp ảnh chụp từ một ``ScanResult`` đã chọn lọc xong. Hàm thuần — mọi giá trị cần tra
    (tiêu đề, ngày, video gốc) do tầng job chuẩn bị TRƯỚC và truyền vào."""
    ok = getattr(kq, "status", "ok") == "ok"
    source_id = str(getattr(kq, "source_id", "") or "")
    source_ref = str(getattr(kq, "source_ref", "") or "")
    doan = []
    for m in (getattr(kq, "matches", None) or []) if ok else []:
        start = _so_hoac_none(getattr(m, "start_s", None))
        end = _so_hoac_none(getattr(m, "end_s", None))
        g0, g1 = giay_moc(start), giay_moc(end)
        goc = goc_theo_clip.get(m.clip) or GocV2(
            clip=m.clip, ngay_dang=NgayNguon(ly_do_thieu="không đọc được metadata kho"))
        doan.append(DoanV2(
            goc=goc, start_s=start, end_s=end,
            vung_khop_s=_so_hoac_none(getattr(m, "vung_khop_s", None)),
            matched_s=float(getattr(m, "matched_s", 0.0) or 0.0),
            clip_offset_s=float(getattr(m, "clip_offset_s", 0.0) or 0.0),
            hashes=int(getattr(m, "hashes", 0) or 0), ty_le=float(getattr(m, "ty_le", 0.0) or 0.0),
            confidence=str(getattr(m, "confidence", "") or ""), vung=str(getattr(m, "vung", "") or ""),
            giay_bat_dau=g0, giay_ket_thuc=g1, link=link_nhay(source_id, source_ref, g0)))
    so_dat = getattr(kq, "so_dat_nguong", 0)
    return BaoCaoV2(
        chinh_sach=CHINH_SACH_V2, thoi_diem_quet=thoi_diem_quet,
        trang_thai="ok" if ok else "error", ghi_chu=str(getattr(kq, "note", "") or ""),
        nguon_loai=nguon_loai, video_id=ma_video_hop_le(source_id), link_video=source_ref,
        tieu_de=tieu_de, nguon_tieu_de=nguon_tieu_de, ly_do_thieu_tieu_de=ly_do_thieu_tieu_de,
        kenh_ten=str(getattr(kq, "channel_name", "") or ""),
        kenh_id=str(getattr(kq, "channel_id", "") or ""),
        kenh_link=str(getattr(kq, "channel_url", "") or ""),
        thoi_luong_s=float(getattr(kq, "duration_s", 0.0) or 0.0), ngay_dang=ngay_dang,
        pham_vi=PhamViV2(
            quet_day_du=bool(getattr(kq, "quet_day_du", False)),
            quet_mot_phan=bool(getattr(kq, "quet_mot_phan", False)),
            ly_do=str(getattr(kq, "ly_do_pham_vi", "") or ""), mo_ta=mo_ta_pham_vi,
            vung_da_khop=_khoang(getattr(kq, "vung_da_khop", None)),
            vung_loi=_khoang(getattr(kq, "vung_loi", None) or ()) or (),
            pham_vi_quet_s=float(getattr(kq, "pham_vi_quet_s", 0.0) or 0.0),
            dat_muc_tieu=bool(getattr(kq, "dat_muc_tieu", False))),
        doan=tuple(doan),
        so_dat_nguong=so_dat if isinstance(so_dat, int) and not isinstance(so_dat, bool) else 0,
        co_ket_qua_loai=bool(getattr(kq, "matches_loai", None)),
        kho_id=str(getattr(kq, "kho_id", "") or ""), kho_ten=str(getattr(kq, "kho_ten", "") or ""),
        kho_phien_ban=str(getattr(kq, "kho_phien_ban", "") or ""),
        chinh_sach_nhan_dien=str(getattr(kq, "chinh_sach", "") or ""),
        bo_sung_ngay=tuple(tuple(x) for x in bo_sung_ngay),
    )


# =====================================================================
#  Dựng dòng xuất — MỌI exporter V2 đi qua đây (một nguồn quy tắc)
# =====================================================================

SO_DOAN_NGANG = 5


def doan_hien_thi(d: DoanV2) -> str:
    """``HH:MM:SS – HH:MM:SS · link`` — mốc đầu và ``t`` của link là CÙNG một giây."""
    noi_dung = f"{hien_thi_moc(d.giay_bat_dau)} – {hien_thi_moc(d.giay_ket_thuc)}"
    return f"{noi_dung} · {d.link}" if d.link else noi_dung


def dong_ngang(bc: BaoCaoV2) -> list:
    """Đúng 34 phần tử theo ``bang_ngang.HEADER_NGANG`` (hợp đồng Apps Script giữ nguyên)."""
    chan_neu_loi(bc)
    doan = list(bc.doan[:SO_DOAN_NGANG]) if bc.trang_thai == "ok" else []
    dong = [
        bc.thoi_diem_quet, bc.kenh_link, bc.kenh_ten, bc.kenh_id, bc.link_video, bc.tieu_de,
        hien_thi_moc(giay_moc(bc.thoi_luong_s)) if giay_moc(bc.thoi_luong_s) is not None else "",
        bc.ngay_dang.hien_thi(),
    ]
    for i in range(SO_DOAN_NGANG):
        dong.append(doan_hien_thi(doan[i]) if i < len(doan) else "")
    for i in range(SO_DOAN_NGANG):
        if i >= len(doan):
            dong.extend(["", "", "", ""])
            continue
        g = doan[i].goc
        dong.extend([g.url, g.tieu_de, g.ngay_dang.hien_thi(), hien_thi_thoi_luong(g.thoi_luong_s)])
    dong.append(bc.so_dat_nguong)
    return dong


def dong_doc(bc: BaoCaoV2) -> list:
    """Các dòng 16 cột theo ``Engine.HEADER`` (một dòng mỗi đoạn)."""
    chan_neu_loi(bc)
    dau = [bc.thoi_diem_quet, bc.tieu_de, bc.link_video]
    if bc.trang_thai != "ok":
        return [dau + [f"(LỖI: {bc.ghi_chu})"] + [""] * 12]
    if not bc.doan:
        nhan = ("(không có kết quả nào đạt ngưỡng)" if bc.co_ket_qua_loai
                else "(không tìm thấy clip nào)")
        return [dau + [nhan] + [""] * 12]
    rows = []
    for d in bc.doan:
        g = d.goc
        rows.append(dau + [
            g.clip, g.tieu_de, g.url, d.vung, hien_thi_moc(d.giay_bat_dau),
            hien_thi_moc(giay_moc(d.vung_khop_s)), hien_thi_moc(d.giay_ket_thuc), d.link,
            round(d.matched_s), round(d.clip_offset_s), d.hashes, d.ty_le, d.confidence])
    return rows


def nhan_pham_vi(bc: BaoCaoV2) -> str:
    if bc.trang_thai != "ok":
        return "Lỗi"
    if bc.pham_vi.quet_day_du:
        return "Trọn video"
    return "Một phần" if bc.pham_vi.quet_mot_phan else "Chưa rõ"


def dong_pham_vi(bc: BaoCaoV2) -> list:
    """Một dòng sidecar phạm vi (``HEADER_PHAM_VI``): tên video vẫn sạch, phạm vi không mất."""
    chan_neu_loi(bc)
    vung_loi = ", ".join(f"{hien_thi_moc(giay_moc(a))}–{hien_thi_moc(giay_moc(b))}"
                         for a, b in bc.pham_vi.vung_loi)
    return [bc.link_video, bc.tieu_de, nhan_pham_vi(bc), bc.pham_vi.mo_ta,
            _LY_DO_PHAM_VI.get(bc.pham_vi.ly_do, bc.pham_vi.ly_do), vung_loi, bc.ghi_chu,
            bc.chinh_sach]


def ngay_goc_thieu(bc: BaoCaoV2) -> list:
    """Video gốc (đã chọn) chưa có ngày đăng nguyên bản: ``[(clip, lý do)]`` để giao diện báo.
    Báo cáo V2 lỗi/hỏng không có video gốc nào để liệt kê (lỗi được báo riêng)."""
    if la_loi_bao_cao(bc):
        return []
    return [(d.goc.clip, d.goc.ngay_dang.ly_do_thieu) for d in bc.doan
            if not d.goc.ngay_dang.gia_tri]
