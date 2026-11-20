# -*- coding: utf-8 -*-
"""Tìm video nghi vấn theo tiêu đề clip gốc (D-51, ``docs/YOUTUBE_DATA_API.md``).

Tìm trên YouTube (``search.list``) tiêu đề các clip đã chọn của một kho, gộp kết quả theo mã video, bỏ video của chính
kênh gốc, xếp theo số truy vấn khớp rồi thời lượng, đánh dấu video đã quét. Chỉ TÌM — không tải, không quét, không đường
yt-dlp nào: người dùng chọn video rồi đưa sang ô link của tab «▶️ Quét YouTube».

Hai hạn mức của Google: ``search.list`` RIÊNG 100 lượt/ngày (mỗi truy vấn 1 lượt), ``videos.list`` (thời lượng, kênh gốc)
trong hạn mức 10.000 đơn vị. Mỗi hạn mức một phiên con ``PhienYouTube.api`` riêng: hết hạn mức tìm kiếm giữa chừng vẫn lấy
được thời lượng cho phần đã tìm, và ngược lại. Không import ``streamlit``.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Container, Iterable, Optional

import bao_cao_v2
import truy_cap_youtube as tc
import youtube_api
from clip_metadata import load_metadata_strict
from publication_date import format_publication_date, ngay_utc_tu_published_at

TOI_DA_MAC_DINH = 10    # truy vấn mỗi lần bấm «Tìm»
TOI_DA = 50
NHAN_THOI_LUONG = {"long": "Dài (trên 20 phút)", "medium": "Vừa (4–20 phút)", "any": "Mọi độ dài"}
COT = ("Tiêu đề", "Kênh", "Thời lượng", "Ngày đăng", "Link", "Khớp bao nhiêu truy vấn", "Đã quét chưa")

_DAT_LAI = "đặt lại lúc nửa đêm giờ Thái Bình Dương — khoảng 14–15 giờ chiều giờ Việt Nam"
HET_HAN_MUC_TIM = f"Hết hạn mức tìm kiếm YouTube trong ngày (mặc định 100 lượt/ngày, {_DAT_LAI})"
# Câu của ``truy_cap_youtube.THONG_BAO_API`` hứa «lấy bằng yt-dlp như cũ» — tính năng này không có đường yt-dlp nào.
_LY_DO_TAT = {
    tc.API_HET_HAN_MUC: f"Hết hạn mức YouTube Data API của khoá trong ngày (mặc định 10.000 đơn vị, {_DAT_LAI})",
    tc.API_KHOA_HONG: ("Khoá YouTube Data API không dùng được (sai khoá, khoá bị chặn hoặc hết hạn, hay dự án Google "
                       "Cloud chưa bật YouTube Data API v3) — kiểm tra khoá trong Google Cloud Console"),
    tc.API_GIOI_HAN: "YouTube Data API đang giới hạn tốc độ yêu cầu — thử lại sau ít phút",
    tc.API_TAM_THOI: "YouTube Data API lỗi mạng / máy chủ 3 lần liên tiếp — thử lại sau",
    tc.API_PHAN_HOI_LA: "YouTube Data API trả phản hồi không như mong đợi (có thể do proxy / mạng chặn)",
}


def _ly_do(phien: tc.PhienYouTube, ly_do: str, *, tim_kiem: bool = False) -> str:
    """API đã tắt tới hết lượt → câu theo loại lỗi (đúng hạn mức của phiên); còn bật → lý do gốc của ``youtube_api``."""
    loai = phien.api.loai_tat
    if loai == tc.API_HET_HAN_MUC and tim_kiem:
        return HET_HAN_MUC_TIM
    return _LY_DO_TAT.get(loai, ly_do)


# =====================================================================
#  Clip của kho → truy vấn
# =====================================================================

@dataclass(frozen=True)
class ClipKho:
    khoa: str       # tên file trong clips_meta.json
    tieu_de: str
    ma: str         # mã video YouTube; "" khi metadata không có


_BO_NHO_CLIP: dict = {}  # đường dẫn clips_meta.json -> ((mtime_ns, cỡ), clip)


def clip_cua_kho(thu_muc: str) -> tuple:
    """Clip có tiêu đề trong ``clips_meta.json`` của kho, mới nhất trước. CHỈ ĐỌC (``load_metadata_strict`` không phục hồi
    hay ghi gì). Nhớ theo (giờ sửa, cỡ) của file: Streamlit vẽ lại mọi tab sau mỗi lần bấm, ở bất kỳ đâu."""
    if not thu_muc:
        return ()   # os.path.join("", …) sẽ đọc nhầm clips_meta.json ở thư mục đang chạy
    path = os.path.join(thu_muc, "clips_meta.json")
    try:
        st = os.stat(path)
    except OSError:
        return ()
    dau = (st.st_mtime_ns, st.st_size)
    cu = _BO_NHO_CLIP.get(path)
    if cu is None or cu[0] != dau:
        nguon = load_metadata_strict(path, kind="live", priority=10)
        moi = sorted((e for e in nguon.entries if e.title), key=lambda e: (e.upload_date, e.key), reverse=True)
        cu = (dau, tuple(ClipKho(e.key, e.title, e.video_id) for e in moi))
        if not nguon.warnings:
            _BO_NHO_CLIP[path] = cu
    return cu[1]


def _ky_tu(c: str) -> str:
    loai = unicodedata.category(c)
    if loai == "So":
        return " "      # emoji / ký hiệu đứng giữa hai chữ là chỗ ngắt từ
    if loai in ("Cf", "Me") or "︀" <= c <= "️" or "\U0001f3fb" <= c <= "\U0001f3ff":
        return ""       # ZWJ, thẻ cờ, khung keycap, biến thể, màu da: dính vào ký tự trước
    return c


def _lam_sach(tieu_de: str, ma: str) -> str:
    """Bỏ mã của CHÍNH clip trong ngoặc vuông và emoji; dấu tiếng Việt (kể cả dạng tổ hợp) giữ nguyên. Thận trọng:
    «[Compilation]» cũng đủ 11 chữ như một mã video — chỉ bỏ đúng mã của clip."""
    if ma:
        tieu_de = tieu_de.replace(f"[{ma}]", " ")
    return " ".join("".join(map(_ky_tu, tieu_de)).split())


def tao_truy_van(clips: Iterable[ClipKho], them: str = "") -> list:
    """Truy vấn theo thứ tự: từng dòng của ``them`` (người dùng tự gõ — giữ nguyên chữ) rồi tiêu đề từng clip đã làm
    sạch; bỏ dòng rỗng và truy vấn trùng (không phân biệt hoa thường, dấu cách thừa)."""
    ra: dict = {}
    for q in [*(" ".join(d.split()) for d in them.splitlines()), *(_lam_sach(c.tieu_de, c.ma) for c in clips)]:
        if q:
            ra.setdefault(q.casefold(), q)
    return list(ra.values())


def kenh_cua_kho(phien: tc.PhienYouTube, data_dir: str, ma: Iterable[str]) -> tuple:
    """Mã kênh của chính kho: MỘT ``videos.list`` cho tối đa 50 mã clip đầu của ``ma`` (nơi gọi đưa clip đã chọn lên
    trước). Trả ``(frozenset mã kênh, lý do)``; lý do rỗng khi lấy được — hoặc khi chưa có khoá (0 yêu cầu)."""
    kq = youtube_api.lay_video(phien, data_dir, [m for m in dict.fromkeys(ma) if m][:youtube_api.LO_TOI_DA])
    kenh = frozenset(v["channel_id"] for v in kq.thong_tin.values() if v["channel_id"])
    return kenh, "" if kenh else _ly_do(phien, kq.ly_do_lui)


# =====================================================================
#  Tìm
# =====================================================================

@dataclass(frozen=True)
class KetQuaTim:
    """``video``: dict (id, title, channel, duration, published_at, khop) đã xếp — khớp nhiều truy vấn trước, rồi dài
    trước. ``da_tim``/``tong``: số truy vấn tìm được / đã chạy; ``luot_tim``: số lượt tìm kiếm đã tốn (kể cả lượt hỏng);
    ``bo_kenh_goc``: số video của kênh gốc đã bỏ; ``ghi_chu``: câu tiếng Việt (kết quả một phần, thiếu thời lượng)."""

    video: tuple
    da_tim: int
    tong: int
    luot_tim: int
    bo_kenh_goc: int
    ghi_chu: tuple


def tim(phien: tc.PhienYouTube, data_dir: str, truy_van: Iterable[str], *, phien_tim: tc.PhienYouTube,
        kenh_goc: Container[str] = frozenset(), thoi_luong: str = "long", sau: Optional[date] = None) -> KetQuaTim:
    """Chạy tối đa ``TOI_DA`` truy vấn bằng ``search.list`` qua ``phien_tim`` (phiên RIÊNG của hạn mức tìm kiếm), bỏ video
    của ``kenh_goc``, gộp theo mã, rồi MỘT lượt ``videos.list`` mỗi 50 video qua ``phien`` để lấy thời lượng. Hết hạn mức
    / lỗi giữa chừng: giữ kết quả đã tìm, ``ghi_chu`` nói rõ. ``sau``: chỉ video đăng từ ngày này (0 giờ UTC)."""
    truy_van = list(truy_van)[:TOI_DA]
    moc = f"{sau.isoformat()}T00:00:00Z" if sau else ""
    gap: dict = {}          # mã -> kết quả search.list đầu tiên (thứ tự liên quan)
    khop: dict = {}         # mã -> số truy vấn
    cua_kenh_goc: set = set()
    loi: dict = {}
    da_tim = 0
    for q in truy_van:
        ds, ly_do = youtube_api.tim_video(phien_tim, data_dir, q, thoi_luong=thoi_luong, sau=moc)
        if ly_do:
            loi[_ly_do(phien_tim, ly_do, tim_kiem=True)] = None
            continue
        da_tim += 1
        for v in {v["id"]: v for v in ds}.values():
            if v["channel_id"] in kenh_goc:
                cua_kenh_goc.add(v["id"])
            else:
                gap.setdefault(v["id"], v)
                khop[v["id"]] = khop.get(v["id"], 0) + 1
    ct = youtube_api.lay_video(phien, data_dir, list(gap))
    video = []
    for ma, v in gap.items():
        tt = ct.thong_tin.get(ma, {})   # videos.list: tiêu đề không mã hoá HTML, có thời lượng
        video.append({"id": ma, "title": tt.get("title", v["title"]), "channel": tt.get("channel", v["channel"]),
                      "duration": tt.get("duration", 0), "published_at": tt.get("published_at", v["published_at"]),
                      "khop": khop[ma]})
    video.sort(key=lambda v: (-v["khop"], -v["duration"]))
    ghi_chu = []
    if loi:
        ghi_chu.append(f"Chỉ tìm được {da_tim}/{len(truy_van)} truy vấn — " + "; ".join(loi))
    if ct.thieu:
        ghi_chu.append(f"{len(ct.thieu)} video chưa lấy được thời lượng — {_ly_do(phien, ct.ly_do_lui)}")
    return KetQuaTim(tuple(video), da_tim, len(truy_van), phien_tim.api.tom_tat()["yeu_cau"], len(cua_kenh_goc),
                     tuple(ghi_chu))


# =====================================================================
#  Bảng, ô quét
# =====================================================================

def bang(video: Iterable[dict], da_quet: Container[str]) -> list:
    """Dòng bảng (cột ``COT``). ``da_quet``: mã đã kiểm xong với kho đang dùng (``Engine.ids_da_quet``) — tính lúc vẽ:
    quét xong một video là cột tự đổi, không phải tìm lại (tốn hạn mức)."""
    return [{"Tiêu đề": v["title"], "Kênh": v["channel"], "Thời lượng": bao_cao_v2.hien_thi_thoi_luong(v["duration"]),
             "Ngày đăng": format_publication_date(ngay_utc_tu_published_at(v["published_at"])),
             "Link": f"https://www.youtube.com/watch?v={v['id']}", "Khớp bao nhiêu truy vấn": v["khop"],
             "Đã quét chưa": "Rồi" if v["id"] in da_quet else "Chưa"} for v in video]


def noi_link(van_ban: str, links: Iterable[str]) -> str:
    """Thêm vào ô link (mỗi dòng một link) các link CHƯA có — so theo mã video; giữ nguyên mọi dòng người dùng đã gõ."""
    dong = van_ban.splitlines()
    co = {youtube_api.ma_video_cho_api(d) or d.strip() for d in dong}
    moi = [x for x in dict.fromkeys(links) if (youtube_api.ma_video_cho_api(x) or x) not in co]
    return "\n".join(dong + moi) if moi else van_ban
