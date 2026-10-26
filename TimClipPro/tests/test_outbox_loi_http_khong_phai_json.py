# -*- coding: utf-8 -*-
"""Phân loại lỗi HTTP của Google Sheets khi THÂN lỗi không phải JSON (audit B-7).

gspread 6.2.1 không đọc được JSON (trang lỗi HTML của front-end Google, proxy/captive portal) thì đặt
``APIError.code = -1`` và ``error["status"] = "invalid JSON: ..."``. ``outbox._ma_http`` từng tin ``code``
trước mã HTTP thật → 4xx thành «HTTP -1»: sau dispatch rơi vào KHÔNG RÕ (đối soát tay dù 4xx chứng minh
chưa ghi), trước dispatch thành lỗi TẠM (thử lại ~3 giờ). Hợp đồng (``phan_loai_loi``, MANAGED_RUNTIME_DESIGN
§«Mơ hồ khi gửi»): phân loại theo mã HTTP THẬT của phản hồi. Dữ liệu synthetic, không mạng.
"""
from __future__ import annotations

import json

import gspread
import pytest
from requests.models import Response

import outbox


def _phan_hoi(ma: int, than: bytes, loai: str) -> Response:
    r = Response()
    r.status_code = ma
    r._content = than
    r.headers["Content-Type"] = loai
    r.encoding = "utf-8"
    return r


def _loi_html(ma: int) -> gspread.exceptions.APIError:
    return gspread.exceptions.APIError(
        _phan_hoi(ma, f"<html><body>Error {ma}</body></html>".encode(), "text/html"))


def test_doi_chung_403_than_json_la_chua_gui_vinh_vien():
    than = json.dumps({"error": {"code": 403, "message": "x", "status": "PERMISSION_DENIED"}})
    e = gspread.exceptions.APIError(_phan_hoi(403, than.encode(), "application/json"))
    kq = outbox.phan_loai_loi(e, da_phat=True)
    assert isinstance(kq, outbox.ChuaGui) and kq.tam_thoi is False
    assert "HTTP 403 PERMISSION_DENIED" in kq.ly_do


def test_ma_http_lay_ma_that_khi_than_loi_khong_phai_json():
    e = _loi_html(403)
    assert e.code == -1                                          # gspread: không đọc được JSON
    assert outbox._ma_http(e) == 403


@pytest.mark.parametrize("da_phat", [True, False])
def test_4xx_than_html_la_chua_gui_vinh_vien(da_phat):
    kq = outbox.phan_loai_loi(_loi_html(403), da_phat=da_phat)
    assert isinstance(kq, outbox.ChuaGui), f"{type(kq).__name__}: {kq}"
    assert kq.tam_thoi is False, str(kq)
    assert "HTTP 403" in kq.ly_do and "-1" not in kq.ly_do
    assert "invalid JSON" not in kq.ly_do                         # chỉ mã HTTP, không chép lỗi phân tích


@pytest.mark.parametrize("ma, da_phat, kieu, tam_thoi", [
    (429, True, outbox.ChuaGui, True),
    (408, True, outbox.KhongRo, None),
    (502, True, outbox.KhongRo, None),
    (502, False, outbox.ChuaGui, True),
])
def test_cac_ma_khac_than_html_giu_nguyen_luat(ma, da_phat, kieu, tam_thoi):
    kq = outbox.phan_loai_loi(_loi_html(ma), da_phat=da_phat)
    assert isinstance(kq, kieu), f"{type(kq).__name__}: {kq}"
    if tam_thoi is not None:
        assert kq.tam_thoi is tam_thoi
    assert f"HTTP {ma}" in kq.ly_do
