# -*- coding: utf-8 -*-
"""Thống kê vi phạm cho tab «📊 Thống kê» — CHỈ ĐỌC ``lichsu.db`` (kết nối ``mode=ro``, không bao giờ ghi).

Cách đếm — để con số không phình theo số lần quét lại:

* Lần quét = mọi dòng ``jobs`` có ngày quét trong khoảng, kể cả lỗi/đã huỷ (huỷ cũng lưu ``status = error``).
* Vi phạm chỉ tính từ lần quét ``ok`` có ít nhất một dòng ``matches``. Một video = ``source_id`` (mã YouTube),
  không có thì ``source_ref`` (link / đường dẫn file), rồi ``source_name``.
* Mỗi cặp (video vi phạm, clip gốc) tính MỘT lần, theo lần quét có nhiều đoạn / nhiều giây khớp nhất.
* Kênh vi phạm chỉ nằm trong ảnh chụp báo cáo V2 (``bao_cao_job``); ``jobs``/``matches`` không lưu kênh. Ảnh chụp
  đọc ĐÚNG luật ``bao_cao_v2.doc_anh_chup_da_luu``: hỏng hay dấu lỗi → bỏ qua, đếm «không đọc được», không đoán
  kênh từ chỗ khác. Lần quét luật cũ (không có ảnh chụp) → video «chưa rõ kênh».
* Theo tháng = số video vi phạm phát hiện LẦN ĐẦU (trong khoảng ngày) ở mỗi tháng, theo ngày quét.

Gộp bằng SQL (không lặp Python trên từng dòng ``matches``); Python chỉ đọc ảnh chụp của các lần quét vi phạm.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import bao_cao_v2
from lich_su import BANG_BAO_CAO, _co_bang, _cot_jobs, _mo_chi_doc

_THANG = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


@dataclass
class ThongKe:
    so_lan_quet: int = 0
    so_lan_loi: int = 0                 # lỗi / đã huỷ — có trong số lần quét, không tính vào vi phạm
    so_video_vi_pham: int = 0
    so_doan_khop: int = 0
    tong_giay_khop: float = 0.0
    ngay_dau: str = ""                  # YYYYMMDD của lần quét đầu / cuối trong khoảng ("" = không rõ)
    ngay_cuoi: str = ""
    kenh: list = field(default_factory=list)        # {ten, link, so_video, so_doan, tong_giay}, nhiều video trước
    clip: list = field(default_factory=list)        # {clip, tieu_de, so_video, so_doan, tong_giay}, nhiều video trước
    theo_thang: list = field(default_factory=list)  # [(YYYY-MM, số video phát hiện lần đầu)], đủ mọi tháng ở giữa
    video_chua_ro_kenh: int = 0
    anh_chup_khong_doc_duoc: int = 0    # số lần quét vi phạm có ảnh chụp V2 hỏng / dấu lỗi


def nhan_thang(thang: str) -> str:
    """``2026-11`` → «Tháng 11/2026»."""
    return f"Tháng {thang[5:]}/{thang[:4]}" if _THANG.fullmatch(thang or "") else "Không rõ thời điểm"


def _du_thang(dem: dict) -> list:
    """``[(YYYY-MM, số)]`` liên tục từ tháng đầu tới tháng cuối — tháng không có video mới vẫn hiện số 0."""
    thang = sorted(k for k in dem if _THANG.fullmatch(k))
    ra = []
    if thang:
        y, m = map(int, thang[0].split("-"))
        cuoi = tuple(map(int, thang[-1].split("-")))
        while (y, m) <= cuoi:
            k = f"{y:04d}-{m:02d}"
            ra.append((k, dem.get(k, 0)))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return ra + [(k, v) for k, v in dem.items() if not _THANG.fullmatch(k)]


def tinh(db_path: str, tu_ngay: Optional[date] = None, den_ngay: Optional[date] = None) -> ThongKe:
    """Thống kê các lần quét có ngày quét trong ``[tu_ngay, den_ngay]`` (bỏ trống = không giới hạn).

    DB chưa có / rỗng / lược đồ cũ → số 0 hoặc phần đọc được; không tạo, không nâng cấp, không ghi gì.
    """
    tk = ThongKe()
    if not os.path.isfile(db_path):
        return tk
    con = _mo_chi_doc(db_path)
    try:
        con.execute("BEGIN")    # mọi truy vấn cùng một ảnh chụp: Watch/lô quét có thể đang lưu lần quét mới
        if not _co_bang(con, "jobs"):
            return tk
        dk, tham = [], []
        for ngay, so_sanh in ((tu_ngay, ">="), (den_ngay, "<=")):
            if ngay:
                dk.append(f"substr(created_at, 1, 10) {so_sanh} ?")
                tham.append(ngay.isoformat())
        ma = "NULLIF(source_id, ''), " if "source_id" in _cot_jobs(con) else ""   # DB rất cũ chưa có cột này
        j = (f"j AS (SELECT id, status, created_at, COALESCE({ma}NULLIF(source_ref, ''), NULLIF(source_name, ''),"
             f" '#' || id) AS vid FROM jobs{' WHERE ' + ' AND '.join(dk) if dk else ''})")
        hang = con.execute(f"WITH {j} SELECT COUNT(*), COALESCE(SUM(status IS NOT 'ok'), 0),"
                           " replace(substr(MIN(created_at), 1, 10), '-', ''),"
                           " replace(substr(MAX(created_at), 1, 10), '-', '') FROM j", tham).fetchone()
        tk.so_lan_quet, tk.so_lan_loi, tk.ngay_dau, tk.ngay_cuoi = hang[0], hang[1], hang[2] or "", hang[3] or ""
        if not _co_bang(con, "matches"):
            return tk
        vc = (f"WITH {j}, jc AS (SELECT j.vid, m.clip, j.created_at AS luc, COUNT(*) AS n,"
              " SUM(COALESCE(m.matched_s, 0)) AS s FROM matches m JOIN j ON j.id = m.job_id"
              " WHERE j.status = 'ok' GROUP BY m.job_id, m.clip),"
              " vc AS (SELECT vid, clip, MIN(luc) AS luc, MAX(n) AS n, MAX(s) AS s FROM jc GROUP BY vid, clip) ")
        clip = con.execute(vc + "SELECT clip, COUNT(*), SUM(n), SUM(s) FROM vc GROUP BY clip"
                           " ORDER BY COUNT(*) DESC, SUM(s) DESC, clip", tham).fetchall()
        video = con.execute(vc + "SELECT vid, MIN(luc), SUM(n), SUM(s) FROM vc GROUP BY vid", tham).fetchall()
        anh = con.execute(
            f"WITH {j} SELECT j.vid, b.chinh_sach, b.du_lieu FROM j JOIN {BANG_BAO_CAO} b ON b.job_id = j.id"
            " WHERE j.status = 'ok' AND EXISTS (SELECT 1 FROM matches m WHERE m.job_id = j.id)"
            " ORDER BY j.id DESC", tham).fetchall() if _co_bang(con, BANG_BAO_CAO) else []
    finally:
        con.close()

    kenh_cua_video, ten_kenh, tieu_de = {}, {}, {}
    for vid, chinh_sach, du_lieu in anh:                    # mới nhất trước: tên kênh / tiêu đề mới nhất thắng
        bc = bao_cao_v2.doc_anh_chup_da_luu(chinh_sach, du_lieu)
        if bao_cao_v2.la_loi_bao_cao(bc):
            tk.anh_chup_khong_doc_duoc += 1
            continue
        khoa = bc.kenh_id or bc.kenh_ten
        if khoa:
            kenh_cua_video.setdefault(vid, khoa)
            ten_kenh.setdefault(khoa, (bc.kenh_ten or bc.kenh_id, bc.kenh_link))
        for d in bc.doan:
            if d.goc.tieu_de:
                tieu_de.setdefault(d.goc.clip, d.goc.tieu_de)

    gop, dem_thang = {}, Counter()
    for vid, luc, n, s in video:
        tk.so_doan_khop += n
        tk.tong_giay_khop += s
        dem_thang[(luc or "")[:7]] += 1
        khoa = kenh_cua_video.get(vid)
        if khoa is None:
            tk.video_chua_ro_kenh += 1
            continue
        g = gop.setdefault(khoa, [0, 0, 0.0])
        g[0], g[1], g[2] = g[0] + 1, g[1] + n, g[2] + s
    tk.so_video_vi_pham = len(video)
    tk.kenh = sorted(({"ten": ten_kenh[k][0], "link": ten_kenh[k][1], "so_video": v, "so_doan": n, "tong_giay": s}
                      for k, (v, n, s) in gop.items()), key=lambda r: (-r["so_video"], -r["tong_giay"], r["ten"]))
    tk.clip = [{"clip": c, "tieu_de": tieu_de.get(c, ""), "so_video": v, "so_doan": n, "tong_giay": s}
               for c, v, n, s in clip]
    tk.theo_thang = _du_thang(dem_thang)
    return tk
