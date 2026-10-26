# -*- coding: utf-8 -*-
"""Thư mục người dùng Windows trong câu lỗi yt-dlp phải được ẩn trước khi vào GHI CHÚ kết quả (audit E-6).

Dữ liệu synthetic: câu lỗi đúng khuôn yt-dlp 2026.08.19 (``cookies.py``: «could not find firefox cookies database in
{search_root}») với tên người dùng giả «nguoithu_e6»; không mạng, không file thật.

Bối cảnh: ``ytdlp_chung.an_thu_muc_nguoi_dung`` tồn tại chính vì chữ của yt-dlp «đi vào GHI CHÚ kết quả (lịch sử,
CSV, Google Sheets)» (docstring), và ``docs/ai/GIT_WORKFLOW.md`` coi «[A-Z]:\\Users\\» là dữ liệu nhạy cảm. Hai cửa
ghi chú ``giai_thich_loi`` (→ ``kq.note`` ở engine.py, channel.py) và ``phan_loai_loi(...).technical_summary`` (→
``tom_tat_ky_thuat``) chỉ chạy ``che_bi_mat``.

Hành vi ĐÚNG được khẳng định: tên người dùng Windows KHÔNG có mặt trong ``giai_thich_loi(e)`` lẫn
``phan_loai_loi(e).technical_summary``; phần chẩn đoán còn lại («firefox cookies database») vẫn giữ.
"""
from __future__ import annotations

import pytest
from yt_dlp.utils import DownloadError

import truy_cap_youtube
import ytdlp_chung

TEN = "nguoithu_e6"
CAU = ("ERROR: could not find firefox cookies database in "
       f"C:\\Users\\{TEN}\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles")


def _loi():
    try:
        raise FileNotFoundError(CAU.removeprefix("ERROR: "))
    except FileNotFoundError as goc:
        loi = DownloadError(CAU)
        loi.__cause__ = goc
        return loi


@pytest.mark.parametrize("cua", ["giai_thich_loi", "technical_summary"])
def test_ghi_chu_khong_mang_ten_nguoi_dung_windows(cua):
    e = _loi()
    if cua == "giai_thich_loi":
        tin = ytdlp_chung.giai_thich_loi(e, co_cookie=True)
    else:
        tin = truy_cap_youtube.phan_loai_loi(e, thao_tac="tai").technical_summary
    assert "firefox cookies database" in tin, tin
    assert TEN not in tin, f"{cua} lộ thư mục người dùng Windows: {tin!r}"
