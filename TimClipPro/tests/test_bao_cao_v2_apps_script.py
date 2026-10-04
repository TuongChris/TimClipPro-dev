# -*- coding: utf-8 -*-
"""Hợp đồng Apps Script (KetQuaQuet, bảng Ngang 34 cột) với dòng báo cáo V2 — fixture, offline.

Apps Script trong repo ĐỌC giá trị đã có theo TÊN CỘT (File01 `KETQUAQUET_COT_MAC_DINH`, File03
xuất văn bản bằng `getDisplayValues()`), không tự dựng tên/link/ngày. Nên V2 không đổi Apps
Script: chỉ cần (1) thứ tự cột y như cũ ở cả bản chia file lẫn bản tổng, (2) giá trị V2 mà
script đọc ra không còn hậu tố/lùi giây, ngày giữ ngày lịch, link gốc vẫn nhận ra được mã video.
Đây không chứng minh bản gắn vào Sheet thật trùng repo — bản đó không được sửa trong vòng này.
"""
import os
import re

import bao_cao_v2 as v2
import bang_ngang
from test_bao_cao_v2 import _bc

THU_MUC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apps_script")


def _cot_mac_dinh(ten_file):
    with open(os.path.join(THU_MUC, ten_file), encoding="utf-8") as f:
        noi_dung = f.read()
    khoi = re.search(r"const KETQUAQUET_COT_MAC_DINH = Object\.freeze\(\[(.*?)\]\);",
                     noi_dung, re.S).group(1)
    return re.findall(r"'([^']*)'", khoi)


def test_thu_tu_cot_apps_script_trung_header_ngang_ca_hai_ban():
    assert _cot_mac_dinh("File01_CauHinh_TienIch.gs") == bang_ngang.HEADER_NGANG
    assert _cot_mac_dinh("TOAN_BO_AppsScript.gs") == bang_ngang.HEADER_NGANG


def _lay_youtube_video_id(gia_tri):
    """Bản Python của `layYoutubeVideoId_` (File01)."""
    m = re.search(r"(?:[?&]v=|youtu\.be/)([A-Za-z0-9_-]{11})", str(gia_tri or "").strip())
    return m.group(1) if m else ""


def _chuan_hoa_ngay(text):
    """Bản Python của `chuanHoaChuoiNgayGio_(text, preferDayFirst=true, includeTime=false)`."""
    m = re.fullmatch(r"(\d{1,4})[/-](\d{1,2})[/-](\d{1,4})", text.strip())
    if not m:
        return ""
    a, b, c = (int(x) for x in m.groups())
    if len(m.group(1)) == 4:
        nam, thang, ngay = a, b, c
    else:
        nam, ngay, thang = c, a, b
    return f"{ngay:02d}/{thang:02d}/{nam:04d}"


def test_gia_tri_v2_doc_qua_apps_script_khong_them_hau_to_hay_lui_giay():
    o = dict(zip(bang_ngang.HEADER_NGANG, v2.dong_ngang(_bc())))
    # File03 in «Tên video vi phạm : <ô hiển thị>» — ô V2 không còn hậu tố phạm vi.
    assert "QUÉT MỘT PHẦN" not in o["Tên video vi phạm"]
    doan = o["Đoạn vi phạm 1 trong video vi phạm"]
    assert doan.startswith("00:15:15 ") and doan.endswith("?t=915")
    # Ngày gửi bằng chuỗi (RAW) → Apps Script chuẩn hoá dd/MM/yyyy giữ đúng ngày lịch.
    assert _chuan_hoa_ngay(o["Ngày đăng video vi phạm"]) == "15/03/2026"
    assert _chuan_hoa_ngay(o["Ngày đăng video gốc 1"]) == "12/03/2025"
    # Link gốc dạng watch?v= vẫn được File04 nhận ra mã video (đánh dấu «đã quét»).
    assert _lay_youtube_video_id(o["Link video gốc 1"]) == "goc00000001"
    assert _lay_youtube_video_id(doan.split(" · ")[1]) == "vidvipham01"
