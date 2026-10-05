# -*- coding: utf-8 -*-
"""Google Sheets cho báo cáo V2 — không gọi mạng (gspread giả).

* Gửi V2 ở chế độ NGHIÊM NGẶT: hàng 1 phải đúng tiêu đề của công cụ; bảng có dữ liệu mà
  thiếu/sai tiêu đề thì DỪNG và hướng dẫn — không chèn/sửa hàng 1, không append lệch cột,
  không clear/resize/update hàng cũ. Bảng rỗng thật sự mới được khởi tạo tiêu đề.
* Payload đã xếp hàng là cố định: thử lại gửi đúng các dòng đã chốt, không dựng lại.
* Đường gửi CŨ giữ nguyên hành vi cũ (test_sheets_session.py).
"""
import pytest

import bang_ngang
import sheet_delivery as sd
import sheets
from sheet_delivery import SheetDelivery, SheetDeliveryWorker
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


def test_loi_tieu_de_khong_duoc_thu_lai():
    assert sd.phan_loai_loi(sheets.LoiHeaderSheet("x")) is False


def test_che_do_cu_van_tu_chen_tieu_de_nhu_truoc(bang):
    """Đường gửi cũ không đổi (ca «mất hàng tiêu đề» vẫn được chèn như bản trước)."""
    bang["hop"]["noi_dung"][:] = [["https://youtu.be/aaaaaaaaaaa", "46229.41"]]
    _sx(bang).append(HEADER, DONG)
    assert bang["dem"]["insert_row"] == 1


# ---------------------------------------------------------------------------
#  Hàng đợi giao hàng
# ---------------------------------------------------------------------------

def _worker(gui):
    return SheetDeliveryWorker(sender=gui, base_delay=0.0, sleep_fn=lambda s: None)


def test_payload_v2_gui_nghiem_ngat_payload_cu_giu_chu_ky_cu():
    nhan = []

    def gui(link, header, rows, **kw):
        nhan.append((header, rows, kw))
        return len(rows)

    w = _worker(gui)
    w.enqueue(SheetDelivery("k_moi", "a", "A", HEADER, DONG, sheet_link="s", nghiem_ngat=True))
    w.enqueue(SheetDelivery("k_cu", "b", "B", HEADER, DONG, sheet_link="s"))
    w._giao("k_moi")
    w._giao("k_cu")
    assert nhan[0][2] == {"nghiem_ngat": True}
    assert nhan[1][2] == {}


def test_sender_cu_ba_tham_so_van_chay_voi_payload_cu():
    def gui(link, header, rows):          # chữ ký cũ, không nhận keyword
        return len(rows)

    w = _worker(gui)
    w.enqueue(SheetDelivery("k", "a", "A", HEADER, DONG, sheet_link="s"))
    w._giao("k")
    assert w.snapshot()["k"].status == sd.DA_GUI


def test_thu_lai_gui_dung_cac_dong_da_chot():
    lan = []

    def gui(link, header, rows, **kw):
        lan.append([list(r) for r in rows])
        if len(lan) == 1:
            raise RuntimeError("503 tạm thời")
        return len(rows)

    w = _worker(gui)
    rows = [list(DONG[0])]
    w.enqueue(SheetDelivery("k", "a", "A", HEADER, rows, sheet_link="s", nghiem_ngat=True))
    w._giao("k")
    assert len(lan) == 2 and lan[0] == lan[1] == [list(DONG[0])]
    assert w.snapshot()["k"].status == sd.DA_GUI


def test_sai_tieu_de_that_bai_ngay_khong_append_lap_lai():
    lan = []

    def gui(link, header, rows, **kw):
        lan.append(1)
        raise sheets.LoiHeaderSheet("Hàng tiêu đề sai — không tự sửa.")

    w = _worker(gui)
    w.enqueue(SheetDelivery("k", "a", "A", HEADER, DONG, sheet_link="s", nghiem_ngat=True))
    w._giao("k")
    assert lan == [1]
    assert w.snapshot()["k"].status == sd.THAT_BAI
    assert "tiêu đề" in w.snapshot()["k"].last_error
