# -*- coding: utf-8 -*-
"""Lịch sử quét giả (lược đồ thật) cho test dọn đệm: luật giữ D-66 xử lý file đệm theo kết quả trong ``lichsu.db``
— file không có trong lịch sử không bao giờ bị dọn, video vi phạm chỉ giữ đoạn quanh mốc."""

from __future__ import annotations

import os
import sqlite3

import lich_su


def ghi_lich_su(data_dir, sach=(), vi_pham=None, loi=(), thoi_luong=None) -> str:
    """Ghi THÊM vào ``<data_dir>/lichsu.db`` (tạo nếu chưa có): ``sach`` = mã đã quét, không vi phạm; ``vi_pham`` =
    ``{mã: [(bắt đầu, kết thúc), ...]}``; ``loi`` = mã chỉ có lượt lỗi; ``thoi_luong`` = ``{mã: giây}`` (mặc định 0 =
    không rõ). Trả đường dẫn DB."""
    duong = os.path.join(str(data_dir), "lichsu.db")
    lich_su.dam_bao_luoc_do(duong, sao_luu=False)
    thoi_luong = thoi_luong or {}
    con = sqlite3.connect(duong)
    try:
        def them(ma: str, trang_thai: str, doan) -> None:
            cur = con.execute(
                "INSERT INTO jobs(created_at, source_type, source_name, source_ref, duration_s, status, n_matches,"
                " note, source_id) VALUES('2026-11-25 08:00:00', 'youtube', ?, ?, ?, ?, ?, '', ?)",
                (f"Video {ma}", f"https://www.youtube.com/watch?v={ma}", float(thoi_luong.get(ma, 0)), trang_thai,
                 len(doan), ma))
            for a, b in doan:
                con.execute("INSERT INTO matches(job_id, clip, start_s, end_s, matched_s, clip_offset_s, hashes,"
                            " confidence) VALUES(?, 'clip_goc.opus', ?, ?, ?, 0, 5000, 'cao')",
                            (cur.lastrowid, float(a), float(b), float(b) - float(a)))

        for ma in sach:
            them(ma, "ok", [])
        for ma in loi:
            them(ma, "error", [])
        for ma, doan in (vi_pham or {}).items():
            them(ma, "ok", doan)
        con.commit()
    finally:
        con.close()
    return duong
