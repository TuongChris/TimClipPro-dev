# -*- coding: utf-8 -*-
"""Google Sheets cho báo cáo V2 — không gọi mạng (trang tính giả).

* Kiểm tiêu đề NGHIÊM NGẶT (``sheets.kiem_tieu_de_nghiem_ngat``, outbox gọi trước mỗi lần gửi):
  hàng 1 phải đúng tiêu đề của công cụ; bảng có dữ liệu mà thiếu/sai tiêu đề thì DỪNG và hướng
  dẫn — không chèn/sửa hàng 1, không ghi gì. Chỉ bảng rỗng thật sự mới được khởi tạo tiêu đề.
* Gửi thật (tiêu đề + dòng, RAW) và payload cố định: outbox lưu bền (tests/test_outbox*.py).
"""
import pytest

import bang_ngang
import sheets

HEADER = list(bang_ngang.HEADER_NGANG)
DONG = [["2026-01-02 03:04:05"] + ["x"] * 32 + [1]]


class _WS:
    def __init__(self, dem, noi_dung):
        self.dem = dem
        self.noi_dung = noi_dung
        self.title = "KetQuaQuet"

    def get_values(self, o=None):
        self.dem["get_values"] += 1
        return [self.noi_dung[0]] if self.noi_dung else []

    def get_all_values(self):
        # Hàng 1 trống → chế độ nghiêm ngặt dò lần hai toàn trang (audit P1-03).
        self.dem["get_all_values"] += 1
        return [list(r) for r in self.noi_dung]

    def append_row(self, row, value_input_option=None):
        self.dem["append_row"] += 1
        self.dem["vio"] = value_input_option
        self.noi_dung.append(list(row))

    def append_rows(self, rows, value_input_option=None):
        self.dem["append_rows"] += 1
        self.dem["vio"] = value_input_option
        self.noi_dung.extend([list(r) for r in rows])

    def insert_row(self, values, index=1, value_input_option=None):
        self.dem["insert_row"] += 1
        self.noi_dung.insert(index - 1, list(values))

    def update(self, *a, **k):
        self.dem["update"] += 1

    def resize(self, *a, **k):
        self.dem["resize"] += 1

    def clear(self):
        self.dem["clear"] += 1

    def sort(self, *a, **k):
        self.dem["sort"] += 1


@pytest.fixture()
def bang():
    dem = {k: 0 for k in ("get_values", "get_all_values", "append_row", "append_rows",
                          "insert_row", "update", "resize", "clear", "sort")}
    hop = {"noi_dung": []}
    return {"dem": dem, "hop": hop, "ws": _WS(dem, hop["noi_dung"])}


def _kiem(bang):
    return sheets.kiem_tieu_de_nghiem_ngat(bang["ws"], HEADER, "KetQuaQuet")


def _khong_ghi_gi(dem):
    return all(dem[k] == 0 for k in ("append_row", "append_rows", "insert_row", "update",
                                     "resize", "clear", "sort"))


def test_bang_rong_thi_bao_ghi_tieu_de(bang):
    assert _kiem(bang) is True                 # người gọi ghi tiêu đề rồi mới ghi dòng
    assert _khong_ghi_gi(bang["dem"])


def test_tieu_de_dung_thi_chi_noi_them(bang):
    bang["hop"]["noi_dung"][:] = [list(HEADER), ["dong cu"] * 34]
    assert _kiem(bang) is False                # không ghi lại tiêu đề
    assert _khong_ghi_gi(bang["dem"])
    assert bang["hop"]["noi_dung"][1] == ["dong cu"] * 34          # hàng cũ nguyên vẹn


def test_tieu_de_dung_kem_cot_nguoi_dung_them_o_cuoi_van_ghi(bang):
    bang["hop"]["noi_dung"][:] = [list(HEADER) + ["Trạng thái"]]
    assert _kiem(bang) is False


@pytest.mark.parametrize("hang_1", [
    ["https://youtu.be/aaaaaaaaaaa", "46229.41"] + ["x"] * 32,   # mất tiêu đề: hàng 1 là dữ liệu
    list(__import__("engine").Engine.HEADER),                  # tiêu đề của schema dọc
    HEADER[:5] + ["Trạng thái"] + HEADER[5:33],                # chèn cột giữa: append sẽ lệch
    ["Thời gian quét"] + ["Cột lạ"] * 33,
])
def test_bang_co_du_lieu_ma_sai_tieu_de_thi_dung_khong_sua(bang, hang_1):
    bang["hop"]["noi_dung"][:] = [list(hang_1), ["dong cu"] * 34]
    truoc = [list(r) for r in bang["hop"]["noi_dung"]]
    with pytest.raises(sheets.LoiHeaderSheet) as loi:
        _kiem(bang)
    assert _khong_ghi_gi(bang["dem"])
    assert bang["hop"]["noi_dung"] == truoc
    assert "hàng tiêu đề" in str(loi.value) and "không tự" in str(loi.value)


# ---------------------------------------------------------------------------
#  Hàng đợi giao hàng
# ---------------------------------------------------------------------------
