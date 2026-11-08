# -*- coding: utf-8 -*-
"""Audit 08/11 — đường Sheets cũ («Kiểm tra kết nối», đẩy danh sách video) phải đặt hạn chờ mạng như outbox."""

from __future__ import annotations

import gspread

import outbox
from sheets import SheetsExporter, xoa_cache_ket_noi


class _ClientGia:
    def __init__(self):
        self.han = None

    def set_timeout(self, han):
        self.han = han

    def open_by_key(self, _id):
        if self.han is None:
            raise AssertionError(
                "mở bảng khi CHƯA đặt hạn chờ — mạng treo là treo luôn giao diện"
            )
        raise gspread.WorksheetNotFound("dừng ở đây là đủ")


def test_mo_bang_dat_han_cho_mang_nhu_outbox(tmp_path, monkeypatch):
    khoa = tmp_path / "khoa.json"
    khoa.write_text("{}", encoding="utf-8")
    client = _ClientGia()
    monkeypatch.setattr(gspread, "service_account", lambda filename=None: client)
    xoa_cache_ket_noi()
    ok, _ = SheetsExporter(str(khoa), "1" + "s" * 43).kiem_tra()
    assert ok is False and client.han == outbox.CongGspread.THOI_GIAN_CHO
