# -*- coding: utf-8 -*-
"""Google Sheets cho báo cáo V2 — không gọi mạng (gspread giả).

* Gửi V2 ở chế độ NGHIÊM NGẶT: hàng 1 phải đúng tiêu đề của công cụ; bảng có dữ liệu mà
  thiếu/sai tiêu đề thì DỪNG và hướng dẫn — không chèn/sửa hàng 1, không append lệch cột,
  không clear/resize/update hàng cũ. Bảng rỗng thật sự mới được khởi tạo tiêu đề.
* Payload đã xếp hàng là cố định — nay ở outbox lưu bền (tests/test_outbox*.py).
* Đường gửi CŨ giữ nguyên hành vi cũ (test_sheets_session.py).
"""
import pytest

import bang_ngang
import sheets
from sheets import SheetsExporter, xoa_cache_ket_noi

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
def bang(tmp_path, monkeypatch):
    import gspread

    xoa_cache_ket_noi()
    key = tmp_path / "google_key.json"
    key.write_text('{"client_email": "x@y.iam.gserviceaccount.com"}', encoding="utf-8")
    dem = {k: 0 for k in ("get_values", "get_all_values", "append_row", "append_rows",
                          "insert_row", "update", "resize", "clear", "sort")}
    hop = {"noi_dung": []}

    class _SH:
        def worksheet(self, ten):
            return _WS(dem, hop["noi_dung"])

    class _CL:
        def open_by_key(self, k):
            return _SH()

    monkeypatch.setattr(gspread, "service_account", lambda filename=None: _CL())
    yield {"key": str(key), "dem": dem, "hop": hop}
    xoa_cache_ket_noi()


def _sx(bang):
    return SheetsExporter(key_path=bang["key"], sheet="abc123")


def _khong_ghi_gi(dem):
    return all(dem[k] == 0 for k in ("append_row", "append_rows", "insert_row", "update",
                                     "resize", "clear", "sort"))


def test_bang_rong_thi_khoi_tao_tieu_de_roi_ghi(bang):
    n = _sx(bang).append(HEADER, DONG, nghiem_ngat=True)
    assert n == 1
    assert bang["hop"]["noi_dung"][0] == HEADER and bang["hop"]["noi_dung"][1] == DONG[0]
    assert bang["dem"]["vio"] == "RAW"


def test_tieu_de_dung_thi_chi_noi_them(bang):
    bang["hop"]["noi_dung"][:] = [list(HEADER), ["dong cu"] * 34]
    _sx(bang).append(HEADER, DONG, nghiem_ngat=True)
    assert bang["dem"]["append_rows"] == 1 and bang["dem"]["append_row"] == 0
    assert bang["dem"]["insert_row"] == 0
    assert bang["hop"]["noi_dung"][1] == ["dong cu"] * 34          # hàng cũ nguyên vẹn


def test_tieu_de_dung_kem_cot_nguoi_dung_them_o_cuoi_van_ghi(bang):
    bang["hop"]["noi_dung"][:] = [list(HEADER) + ["Trạng thái"]]
    _sx(bang).append(HEADER, DONG, nghiem_ngat=True)
    assert bang["dem"]["append_rows"] == 1


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
        _sx(bang).append(HEADER, DONG, nghiem_ngat=True)
    assert _khong_ghi_gi(bang["dem"])
    assert bang["hop"]["noi_dung"] == truoc
    assert "hàng tiêu đề" in str(loi.value) and "không tự" in str(loi.value)


def test_che_do_cu_van_tu_chen_tieu_de_nhu_truoc(bang):
    """Đường gửi cũ không đổi (ca «mất hàng tiêu đề» vẫn được chèn như bản trước)."""
    bang["hop"]["noi_dung"][:] = [["https://youtu.be/aaaaaaaaaaa", "46229.41"]]
    _sx(bang).append(HEADER, DONG)
    assert bang["dem"]["insert_row"] == 1


# ---------------------------------------------------------------------------
#  Hàng đợi giao hàng
# ---------------------------------------------------------------------------
