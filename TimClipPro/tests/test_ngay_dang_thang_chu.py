# -*- coding: utf-8 -*-
"""Ngày đăng trong báo cáo (Google Sheets, CSV, hồ sơ, giao diện) dạng «October 31, 2026» (người dùng yêu cầu 02/11/2026).

Một hàm định dạng duy nhất: luật cũ (``publication_date.format_publication_date``) và báo cáo V2
(``bao_cao_v2.NgayNguon.hien_thi``) phải cho CÙNG một chuỗi. Tên tháng cố định tiếng Anh — không phụ thuộc locale của
Windows (``strftime("%B")`` đổi theo locale máy).
"""
import locale
from datetime import date

import pytest

import bao_cao_v2
from publication_date import format_publication_date


@pytest.mark.parametrize("vao, ra", [
    ("20261031", "October 31, 2026"),
    ("20250105", "January 5, 2025"),       # ngày không có số 0 đứng đầu
    ("20240229", "February 29, 2024"),
    (date(2025, 12, 1), "December 1, 2025"),
    ("", ""),
    ("2026-10-31", ""),                    # sai định dạng nguồn → trống, không đoán
    ("20261332", ""),
])
def test_format_publication_date_thang_chu(vao, ra):
    assert format_publication_date(vao) == ra


def test_bao_cao_v2_cung_dinh_dang_voi_luat_cu():
    for g in ("20261031", "20250105", "20000101"):
        assert bao_cao_v2.NgayNguon(gia_tri=g).hien_thi() == format_publication_date(g)
    assert bao_cao_v2.NgayNguon(gia_tri="").hien_thi() == ""


def test_khong_phu_thuoc_locale_may():
    cu = locale.setlocale(locale.LC_TIME)
    try:
        for ten in ("vi_VN.UTF-8", "Vietnamese_Vietnam.1258", "de_DE.UTF-8", "German_Germany.1252"):
            try:
                locale.setlocale(locale.LC_TIME, ten)
                break
            except locale.Error:
                continue
        assert format_publication_date("20261031") == "October 31, 2026"
    finally:
        locale.setlocale(locale.LC_TIME, cu)
