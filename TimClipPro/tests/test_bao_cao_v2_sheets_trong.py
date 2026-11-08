# -*- coding: utf-8 -*-
"""Sheets nghiêm ngặt: «hàng 1 trống» KHÔNG có nghĩa là «trang tính trống» (audit P1-03).

Trước bản sửa, chế độ nghiêm ngặt chỉ đọc hàng 1 trong bề rộng báo cáo; trống là ghi tiêu đề rồi
ghi dòng — kể cả khi hàng 2 trở đi đã có dữ liệu cũ, có ô ở cột ngoài bề rộng báo cáo, hay một ô
lẻ ở xa. Hợp đồng mới: hàng 1 trống → dò LẦN HAI toàn trang tính; có bất kỳ giá trị nào → lỗi
tiêu đề vĩnh viễn, KHÔNG ghi gì; trống thật → True (người gọi ghi tiêu đề một lần rồi dòng); dò lỗi
→ không ghi gì. Kiểm thẳng ``sheets.kiem_tieu_de_nghiem_ngat`` — hàm outbox dùng.

Trang tính giả dạng LƯỚI ghi lại MỌI thao tác theo thứ tự — không gọi Google.
"""
import re

import pytest

import bang_ngang
import sheets

HEADER = list(bang_ngang.HEADER_NGANG)
DONG = [["2026-01-02 03:04:05"] + ["x"] * 32 + [1]]
CU = ["2025-12-31 23:00:00"] + ["dữ liệu cũ"] * 33
DOC = ("get_values", "get_all_values")


def _so_cot(chu):
    n = 0
    for ch in chu:
        n = n * 26 + (ord(ch) - 64)
    return n


class _Luoi:
    """Trang tính giả: ``get_values`` cắt ĐÚNG vùng A1 như API (bỏ ô/hàng trống ở cuối),
    ``get_all_values`` trả cả bảng; mọi thao tác khác đều là GHI và bị ghi lại."""

    def __init__(self, hang, loi_do=None):
        self.hang = [list(h) for h in hang]
        self.ops = []
        self.title = "KetQuaQuet"
        self.loi_do = loi_do

    def _o(self, r, c):
        if r - 1 < len(self.hang) and c - 1 < len(self.hang[r - 1]):
            return self.hang[r - 1][c - 1]
        return ""

    def get_values(self, vung=None):
        self.ops.append(("get_values", vung))
        m = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", vung or "")
        r0, c0, r1, c1 = int(m[2]), _so_cot(m[1]), int(m[4]), _so_cot(m[3])
        ra = [[self._o(r, c) for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]
        ra = [h[:max([i + 1 for i, x in enumerate(h) if x != ""], default=0)] for h in ra]
        while ra and not ra[-1]:
            ra.pop()
        return ra

    def get_all_values(self):
        self.ops.append(("get_all_values",))
        if self.loi_do is not None:
            raise self.loi_do
        return [list(h) for h in self.hang]

    def append_row(self, row, value_input_option=None):
        self.ops.append(("append_row", "header" if list(row) == HEADER else list(row)))
        self.hang.append(list(row))

    def append_rows(self, rows, value_input_option=None):
        self.ops.append(("append_rows", len(rows)))
        self.hang.extend(list(r) for r in rows)

    def __getattr__(self, ten):            # insert_row/update/clear/resize/sort/delete_rows…
        if ten.startswith("_"):
            raise AttributeError(ten)

        def ghi(*a, **k):
            self.ops.append((ten,))
        return ghi


def _kiem(ws):
    return sheets.kiem_tieu_de_nghiem_ngat(ws, HEADER, ws.title)


def _ghi(ws):
    return [op for op in ws.ops if op[0] not in DOC]


@pytest.mark.parametrize("bang", [
    [[""] * 34, CU],                               # hàng 1 trống, hàng 2 dữ liệu cũ
    [[], CU, CU],                                  # hàng 1 trống hẳn, nhiều hàng cũ
    [[""] * 35 + ["ghi chú tay"]],                 # chỉ có ô ở cột AJ (ngoài bề rộng báo cáo)
    [[], [], [""] * 51 + ["x"]],                   # một ô lẻ ở xa (hàng 3, cột AZ)
    [[], [" "]],                                   # ô chỉ có dấu cách vẫn là có dữ liệu
], ids=["hang2_cu", "nhieu_hang_cu", "cot_ngoai_be_rong", "o_le_xa", "o_dau_cach"])
def test_hang1_trong_ma_trang_co_du_lieu_thi_loi_va_khong_ghi_gi(bang):
    ws = _Luoi(bang)
    truoc = [list(h) for h in ws.hang]
    with pytest.raises(sheets.LoiHeaderSheet) as loi:
        _kiem(ws)
    assert _ghi(ws) == [], "không được ghi bất kỳ thứ gì vào trang tính có dữ liệu"
    assert ws.hang == truoc
    assert ("get_all_values",) in ws.ops                 # đã dò lần hai
    assert "không tự" in str(loi.value)
    assert loi.value.vinh_vien is True


def test_trang_trong_that_thi_bao_ghi_tieu_de():
    ws = _Luoi([])
    assert _kiem(ws) is True
    assert ws.ops == [("get_values", "A1:AH1"), ("get_all_values",)]


def test_tieu_de_dung_thi_chi_noi_dong_khong_doc_them():
    ws = _Luoi([HEADER, CU])
    assert _kiem(ws) is False
    assert ws.ops == [("get_values", "A1:AH1")]                      # đường chính: 1 lần đọc
    assert ws.hang[:2] == [HEADER, CU]


def test_tieu_de_sai_van_dung_va_khong_ghi():
    ws = _Luoi([HEADER[:5] + ["Trạng thái"] + HEADER[5:33], CU])
    with pytest.raises(sheets.LoiHeaderSheet):
        _kiem(ws)
    assert _ghi(ws) == []


def test_do_lan_hai_loi_thi_khong_ghi_gi():
    ws = _Luoi([], loi_do=ConnectionError("timeout (giả lập)"))
    with pytest.raises(ConnectionError):
        _kiem(ws)
    assert _ghi(ws) == []
