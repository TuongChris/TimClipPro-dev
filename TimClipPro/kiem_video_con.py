# -*- coding: utf-8 -*-
"""Video vi phạm đã tìm thấy còn trên YouTube hay đã gỡ — theo dõi kết quả khiếu nại (D-51, docs/YOUTUBE_DATA_API.md).

CHỈ YouTube Data API (``youtube_api.lay_video(..., can_trang_thai=True)``: 50 video một yêu cầu, ~1 đơn vị hạn mức) —
KHÔNG lùi về yt-dlp: mục đích là không chạm YouTube bằng yt-dlp. Lô lỗi, hết hạn mức, chưa có khoá → «Chưa kiểm được —
lý do»; kết quả đã kiểm được trước đó giữ nguyên. Sổ ``<data_dir>/kiem_video_con.json`` ghi bằng ``luu_tru.cap_nhat_json``
(nguyên tử, có khoá, có ``.bak``) SAU khi xong mạng. Không đổi ``lichsu.db``, không gửi Google Sheets.
"""

from __future__ import annotations

import collections
import math
import os
from datetime import datetime
from typing import Iterable

import luu_tru
import truy_cap_youtube
import youtube_api

TEN_FILE = "kiem_video_con.json"

# Nhãn cột «Trên YouTube» — KHÔNG gọi là «Trạng thái»: chữ đó đã mang nghĩa trạng thái quét / gửi.
CON_CONG_KHAI = "Còn (công khai)"
CON_KHONG_CONG_KHAI = "Còn (không công khai — ai có link vẫn xem được)"
CON_TRUC_TIEP = "Còn (đang phát trực tiếp hoặc sắp công chiếu)"
KHONG_CON = "Không còn xem được (đã gỡ hoặc riêng tư)"
DA_GO = "Đã bị gỡ ({})"
CHUA_KIEM_DUOC = "Chưa kiểm được — {}"
CHUA_KIEM = "Chưa kiểm"
_LY_DO_GO = {"rejected": "YouTube từ chối video", "deleted": "video đã bị xoá"}
_THEO_CONG_KHAI = {"public": CON_CONG_KHAI, "unlisted": CON_KHONG_CONG_KHAI, "private": KHONG_CON}


def nhom(ket_qua: str) -> str:
    """«con» | «khong_con» (đã gỡ hoặc không còn xem được) | «chua» (chưa kiểm / chưa kiểm được)."""
    if ket_qua.startswith("Còn ("):
        return "con"
    if ket_qua == KHONG_CON or ket_qua.startswith("Đã bị gỡ ("):
        return "khong_con"
    return "chua"


def _ket_qua(ma: str, kq: youtube_api.KetQuaApi) -> str:
    v = kq.thong_tin.get(ma)
    if v is None:
        ly_do = kq.ly_do_tung_ma.get(ma, "")
        if ly_do == youtube_api.LY_DO_VANG:   # vắng trong phản hồi 200: riêng tư hoặc đã gỡ (khoá API không thấy)
            return KHONG_CON
        if ly_do == youtube_api.LY_DO_SAP_PHAT:
            return CON_TRUC_TIEP
        return CHUA_KIEM_DUOC.format(ly_do or youtube_api.LY_DO_CHUA_CO_KHOA)
    if v["upload_status"] in _LY_DO_GO:
        return DA_GO.format(_LY_DO_GO[v["upload_status"]])
    return _THEO_CONG_KHAI.get(v["privacy_status"],
                               CHUA_KIEM_DUOC.format("YouTube không cho biết video công khai hay riêng tư"))


def _bay_gio() -> str:
    return datetime.now().isoformat(timespec="seconds")


def kiem_tra(phien: truy_cap_youtube.PhienYouTube, data_dir: str, ids: Iterable[str]) -> dict:
    """Hỏi Data API ``ids`` trong MỘT lượt (``phien``) rồi ghi sổ; trả {mã: kết quả của lượt này}.

    Mỗi mã trong sổ: ``ket_qua``, ``kiem_luc``, ``lan_dau_khong_con`` (ghi MỘT lần rồi giữ), ``lan_cuoi_con`` (ISO giờ
    máy, "" = chưa có). Lượt «chưa kiểm được» không đè kết quả đã kiểm được. Sổ sai cấu trúc → ``luu_tru.LoiDuLieu``,
    không ghi gì."""
    ids = list(dict.fromkeys(ids))
    kq = youtube_api.lay_video(phien, data_dir, ids, can_trang_thai=True)
    ket = {m: _ket_qua(m, kq) for m in ids}
    luc = _bay_gio()

    def sua(so: dict) -> None:
        if not isinstance(so, dict):
            raise luu_tru.LoiDuLieu(f"Sổ {TEN_FILE} sai cấu trúc — không ghi đè; sửa hoặc xoá file đó rồi kiểm lại.")
        if not isinstance(so.get("video"), dict):
            so["video"] = {}
        so["phien_ban"] = 1
        for m, moi in ket.items():
            cu = so["video"].get(m)
            cu = cu if isinstance(cu, dict) else {}
            n = nhom(moi)
            if n == "chua" and nhom(str(cu.get("ket_qua") or "")) != "chua":
                continue
            so["video"][m] = {
                "ket_qua": moi, "kiem_luc": luc,
                "lan_dau_khong_con": str(cu.get("lan_dau_khong_con") or (luc if n == "khong_con" else "")),
                "lan_cuoi_con": luc if n == "con" else str(cu.get("lan_cuoi_con") or "")}

    luu_tru.cap_nhat_json(os.path.join(data_dir, TEN_FILE), sua, {"phien_ban": 1, "video": {}})
    return ket


def doc_so(data_dir: str) -> dict:
    """{mã: mục sổ}; chưa có sổ hay sổ sai cấu trúc → rỗng. Sổ hỏng cả bản sao → ``luu_tru.LoiDuLieu`` (bản hỏng giữ lại)."""
    so = luu_tru.doc_json_an_toan(os.path.join(data_dir, TEN_FILE), {})
    video = so.get("video") if isinstance(so, dict) else None
    return {m: muc for m, muc in video.items() if isinstance(muc, dict)} if isinstance(video, dict) else {}


def dong_bang(vi_pham: list, so: dict) -> list:
    """Một dòng mỗi video vi phạm (``Engine.video_vi_pham``) kèm kết quả kiểm đã lưu — bảng của tab Lịch sử."""
    def gio(x) -> str:
        return str(x or "").replace("T", " ")

    bang = []
    for v in vi_pham:
        muc = so.get(v["ma"], {})
        bang.append({"Video vi phạm": v["tieu_de"], "Link": f"https://www.youtube.com/watch?v={v['ma']}",
                     "Kênh": v["kenh_ten"] or v["kenh_link"], "Lần quét gần nhất": v["lan_quet_cuoi"],
                     "Số lần quét": v["so_lan_quet"], "Trên YouTube": str(muc.get("ket_qua") or CHUA_KIEM),
                     "Kiểm lúc": gio(muc.get("kiem_luc")),
                     "Lần đầu thấy không còn": gio(muc.get("lan_dau_khong_con"))})
    return bang


def dem(bang: list) -> collections.Counter:
    """Số video theo nhóm («con», «khong_con», «chua») của cột «Trên YouTube»."""
    return collections.Counter(nhom(d["Trên YouTube"]) for d in bang)


def so_don_vi(so_video: int) -> int:
    """Hạn mức ước tính của một lần kiểm: 1 đơn vị mỗi 50 video (lỗi tạm thời thử lại tốn thêm)."""
    return math.ceil(so_video / youtube_api.LO_TOI_DA)
