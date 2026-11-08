# -*- coding: utf-8 -*-
"""Dùng lại kết nối Google Sheets. Không gọi mạng — gspread giả đếm số lượt gọi."""

from __future__ import annotations

import threading

import pytest

import sheets
from sheets import SheetsExporter, xoa_cache_ket_noi

HEADER = ["A", "B"]
ROWS = [["1", "2"]]


class _Worksheet:
    """Mô phỏng LƯỚI THẬT chứ không chỉ đếm lượt gọi.

    Nếu fake chỉ đếm thì bug «1718 dòng trên lưới 1000» — ca chắc chắn xảy ra ngoài
    đời với kho Cory — sẽ không test nào bắt được.
    """

    def __init__(self, dem, noi_dung=None):
        self.dem = dem
        self.noi_dung = noi_dung if noi_dung is not None else []
        self.title = "KetQuaQuet"
        self.spreadsheet = type("S", (), {"title": "Bang"})()
        self.row_count = 1000
        self.col_count = 12
        self.vio = None
        self.range_update = None

    def get_values(self, o=None):
        self.dem["get_values"] += 1
        return [self.noi_dung[0]] if self.noi_dung else []

    def get_all_values(self):
        self.dem["get_all_values"] += 1
        return list(self.noi_dung)

    def resize(self, rows=None, cols=None):
        self.dem["resize"] += 1
        if rows is not None:
            self.row_count = rows
        if cols is not None:
            self.col_count = cols
        # Thu nhỏ là XOÁ HẲN ô ngoài lưới (hành vi thật của updateSheetProperties).
        del self.noi_dung[self.row_count:]
        self.noi_dung[:] = [list(r)[:self.col_count] for r in self.noi_dung]

    def update(self, values=None, range_name=None, value_input_option=None):
        # Chỉ nhận KEYWORD: gọi positional sẽ nổ TypeError, đúng cách bảo vệ tính
        # tương thích gspread 5.x (range_name, values) với 6.x (values, range_name).
        self.dem["update"] += 1
        self.vio = value_input_option
        self.range_update = range_name
        # Tái hiện lỗi THẬT: values.update KHÔNG tự nới lưới (khác values.append).
        if (len(values) > self.row_count
                or max((len(r) for r in values), default=0) > self.col_count):
            raise RuntimeError(
                f"Range (A1:B{len(values)}) exceeds grid limits. "
                f"Max rows: {self.row_count}")
        for i, r in enumerate(values):
            while len(self.noi_dung) <= i:
                self.noi_dung.append([])
            self.noi_dung[i] = list(r)

    def clear(self):
        self.dem["clear"] += 1
        self.noi_dung.clear()


class _Spreadsheet:
    def __init__(self, dem, ws):
        self.dem = dem
        self._ws = ws

    def worksheet(self, ten):
        self.dem["worksheet"] += 1
        return self._ws

    def add_worksheet(self, title, rows, cols):
        self.dem["add_worksheet"] += 1
        self.tao_voi = (rows, cols)
        self._ws.title = title
        self._ws.row_count = rows
        self._ws.col_count = cols
        return self._ws


class _Client:
    def __init__(self, dem, sh):
        self.dem = dem
        self._sh = sh

    def set_timeout(self, _han):
        pass

    def open_by_key(self, key):
        self.dem["open_by_key"] += 1
        return self._sh


@pytest.fixture()
def moi_truong(tmp_path, monkeypatch):
    import gspread

    xoa_cache_ket_noi()
    key = tmp_path / "google_key.json"
    key.write_text('{"client_email": "x@y.iam.gserviceaccount.com"}', encoding="utf-8")

    dem = {k: 0 for k in ("service_account", "open_by_key", "worksheet",
                          "get_values", "get_all_values",
                          "clear", "resize", "update", "add_worksheet")}
    ws = _Worksheet(dem)
    sh = _Spreadsheet(dem, ws)

    def service_account(filename=None):
        dem["service_account"] += 1
        return _Client(dem, sh)

    monkeypatch.setattr(gspread, "service_account", service_account)
    yield {"key": str(key), "dem": dem, "ws": ws}
    xoa_cache_ket_noi()


def _exporter(moi_truong, sheet="abc123"):
    return SheetsExporter(key_path=moi_truong["key"], sheet=sheet)


# ---------------------------------------------------------------------------
# Điểm chính: dùng lại kết nối
# ---------------------------------------------------------------------------

def test_muoi_lan_ghi_chi_xac_thuc_va_mo_bang_mot_lan(moi_truong):
    dem = moi_truong["dem"]
    for _ in range(10):
        _exporter(moi_truong).ghi_de(HEADER, ROWS)

    assert dem["service_account"] == 1, "Xác thực lại mỗi lần ghi là lãng phí"
    assert dem["open_by_key"] == 1
    assert dem["worksheet"] == 1
    assert dem["update"] == 10, "Vẫn phải ghi đủ 10 lượt"


# ---------------------------------------------------------------------------
# Cache phải mất hiệu lực đúng lúc
# ---------------------------------------------------------------------------

def test_doi_sheet_thi_mo_ket_noi_moi(moi_truong):
    dem = moi_truong["dem"]
    _exporter(moi_truong, "sheet_mot").ghi_de(HEADER, ROWS)
    _exporter(moi_truong, "sheet_hai").ghi_de(HEADER, ROWS)

    assert dem["open_by_key"] == 2


def test_doi_file_key_thi_xac_thuc_lai(moi_truong, tmp_path):
    import os
    import time

    dem = moi_truong["dem"]
    _exporter(moi_truong).ghi_de(HEADER, ROWS)
    time.sleep(0.01)
    os.utime(moi_truong["key"], None)          # giả lập thay khoá
    _exporter(moi_truong).ghi_de(HEADER, ROWS)

    assert dem["service_account"] == 2, "Thay google_key.json phải xác thực lại"


def test_loi_khi_ghi_thi_bo_cache_de_lan_sau_ket_noi_lai(moi_truong, monkeypatch):
    dem = moi_truong["dem"]
    ws = moi_truong["ws"]
    goc = ws.update
    lan = {"n": 0}

    def hong(values=None, range_name=None, value_input_option=None):
        lan["n"] += 1
        if lan["n"] == 1:
            raise RuntimeError("connection reset")
        return goc(values=values, range_name=range_name, value_input_option=value_input_option)

    monkeypatch.setattr(ws, "update", hong)

    # Kết nối mới mở (chưa từ cache) → ghi_de không tự thử lại, lỗi ném ra.
    with pytest.raises(RuntimeError, match="connection reset"):
        _exporter(moi_truong).ghi_de(HEADER, ROWS)
    _exporter(moi_truong).ghi_de(HEADER, ROWS)

    assert dem["service_account"] == 2, "Sau lỗi phải mở kết nối mới"


# ---------------------------------------------------------------------------
# Tương thích và an toàn luồng
# ---------------------------------------------------------------------------

def test_lui_ve_get_all_values_khi_gspread_cu(moi_truong, monkeypatch):
    """gspread cũ không có ``get_values``: kiểm tiêu đề nghiêm ngặt (outbox dùng) đọc ``get_all_values``."""
    ws = moi_truong["ws"]
    monkeypatch.setattr(ws, "get_values", None, raising=False)
    ws.noi_dung[:] = [list(HEADER), ["du lieu", "cu"]]

    assert sheets.kiem_tieu_de_nghiem_ngat(ws, HEADER, ws.title) is False

    assert moi_truong["dem"]["get_all_values"] == 1
    assert moi_truong["dem"]["get_values"] == 0


def test_chua_cau_hinh_thi_bao_loi_ro_rang(tmp_path):
    xoa_cache_ket_noi()
    ex = SheetsExporter(key_path=str(tmp_path / "khong_co.json"), sheet="abc")
    with pytest.raises(RuntimeError):
        ex.ghi_de(HEADER, ROWS)


def test_nhieu_thread_ghi_dong_thoi_van_dung_mot_ket_noi(moi_truong):
    dem, ws = moi_truong["dem"], moi_truong["ws"]
    loi = []
    da_ghi = []
    # Lưới giả không an toàn luồng; ở đây chỉ đếm lượt ghi (list.append là nguyên tử).
    ws.resize = lambda rows=None, cols=None: None
    ws.update = lambda values=None, range_name=None, value_input_option=None: da_ghi.append(1)

    def chay():
        try:
            _exporter(moi_truong).ghi_de(HEADER, ROWS)
        except Exception as e:  # noqa: BLE001
            loi.append(e)

    ts = [threading.Thread(target=chay) for _ in range(12)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=15)

    assert not loi
    assert dem["service_account"] == 1
    assert len(da_ghi) == 12


def test_kiem_tra_ket_noi_van_mo_moi_khong_dung_cache(moi_truong):
    """«Kiểm tra kết nối» phải thật sự chạm tới Google, không trả lời từ cache."""
    dem = moi_truong["dem"]
    _exporter(moi_truong).ghi_de(HEADER, ROWS)
    ok, _ = _exporter(moi_truong).kiem_tra()

    assert ok is True
    assert dem["service_account"] == 2


def test_cache_o_cap_module_nen_instance_moi_van_dung_lai(moi_truong):
    """app.py tạo SheetsExporter mới mỗi lần đẩy — cache theo instance sẽ vô dụng."""
    dem = moi_truong["dem"]
    a = _exporter(moi_truong)
    b = _exporter(moi_truong)
    assert a is not b

    a.ghi_de(HEADER, ROWS)
    b.ghi_de(HEADER, ROWS)

    assert dem["service_account"] == 1


def test_xoa_cache_buoc_ket_noi_lai(moi_truong):
    dem = moi_truong["dem"]
    _exporter(moi_truong).ghi_de(HEADER, ROWS)
    sheets.xoa_cache_ket_noi()
    _exporter(moi_truong).ghi_de(HEADER, ROWS)

    assert dem["service_account"] == 2


# ---------------------------------------------------------------------------
# Ghi đè (dùng cho tab «Danh sách video trong kho»)
# ---------------------------------------------------------------------------

def test_ghi_de_hai_lan_lien_tiep_khong_nhan_doi_dong(moi_truong):
    """Yêu cầu đã chốt: chạy lại thì ghi đè, không bao giờ trùng dòng."""
    ws = moi_truong["ws"]
    _exporter(moi_truong).ghi_de(HEADER, ROWS)
    _exporter(moi_truong).ghi_de(HEADER, ROWS)

    assert len(ws.noi_dung) == 1 + len(ROWS)
    assert ws.noi_dung[0] == HEADER


def test_ghi_de_bang_cu_dai_hon_khong_con_dong_cu_sot_lai(moi_truong):
    ws = moi_truong["ws"]
    ws.row_count, ws.col_count = 5000, 12
    ws.noi_dung[:] = [[f"cu{i}"] * 12 for i in range(5000)]

    rows = [["1", "a"], ["2", "b"], ["3", "c"]]
    _exporter(moi_truong).ghi_de(HEADER, rows)

    assert len(ws.noi_dung) == 4
    assert ws.row_count == 4 and ws.col_count == 2
    assert not any("cu" in str(o) for dong in ws.noi_dung for o in dong)


def test_ghi_de_1718_dong_tren_luoi_1000_van_thanh_cong(moi_truong):
    """Đúng ca kho Cory: 1717 clip -> 1718 dòng, lưới tab mới chỉ 1000."""
    ws = moi_truong["ws"]
    rows = [[i, f"video {i}"] for i in range(1, 1718)]
    n = _exporter(moi_truong).ghi_de(HEADER, rows)

    assert n == 1717
    assert len(ws.noi_dung) == 1718
    assert ws.row_count == 1718


def test_ghi_de_khong_goi_clear(moi_truong):
    """``clear()`` là thừa (resize+update đã phủ hết lưới) và tạo khoảng bảng trống."""
    dem, ws = moi_truong["dem"], moi_truong["ws"]
    _exporter(moi_truong).ghi_de(HEADER, ROWS)

    assert dem["clear"] == 0
    assert ws.noi_dung == [HEADER, list(ROWS[0])]


def test_ghi_de_dung_value_input_option_RAW_va_range_A1(moi_truong):
    """Đổi sang USER_ENTERED là phải xem lại quyết định không bọc o_bang_tinh_an_toan."""
    ws = moi_truong["ws"]
    _exporter(moi_truong).ghi_de(HEADER, ROWS)

    assert ws.vio == "RAW"
    assert ws.range_update == "A1"


def test_ghi_de_giu_nguyen_chuoi_bat_dau_bang_dau_bang(moi_truong):
    ws = moi_truong["ws"]
    _exporter(moi_truong).ghi_de(["STT", "Tên video"], [[1, "=SUM(A1)"]])

    assert ws.noi_dung[1] == [1, "=SUM(A1)"]


def test_ghi_de_khong_co_dong_thi_tu_choi(moi_truong):
    dem = moi_truong["dem"]
    with pytest.raises(ValueError):
        _exporter(moi_truong).ghi_de(HEADER, [])

    assert dem["service_account"] == 0
    assert dem["update"] == 0


def test_ghi_de_cho_phep_rong_chi_con_dung_mot_dong_header(moi_truong):
    """Khoá cái bẫy ``max(so_dong, 2)``: resize dư một dòng là dòng cũ còn sót."""
    ws = moi_truong["ws"]
    ws.noi_dung[:] = [["cu1", "cu1"], ["cu2", "cu2"], ["cu3", "cu3"]]

    n = _exporter(moi_truong).ghi_de(HEADER, [], cho_phep_rong=True)

    assert n == 0
    assert ws.row_count == 1
    assert ws.noi_dung == [HEADER]


def test_ghi_de_dem_dong_khong_deu_thanh_bang_chu_nhat(moi_truong):
    ws = moi_truong["ws"]
    _exporter(moi_truong).ghi_de(["A", "B"], [["1"]])

    assert all(len(dong) == 2 for dong in ws.noi_dung)
    assert ws.noi_dung[1] == ["1", ""]


def test_ghi_de_thu_lai_mot_lan_khi_ket_noi_cu_trong_cache_da_chet(moi_truong):
    """Người dùng tự xoá tab trên trình duyệt giữa phiên -> Worksheet trong cache chết."""
    dem, ws = moi_truong["dem"], moi_truong["ws"]
    _exporter(moi_truong).ghi_de(HEADER, ROWS)      # nạp cache
    assert dem["service_account"] == 1

    that_bai = {"con": 1}
    resize_that = ws.resize

    def resize_chet(rows=None, cols=None):
        if that_bai["con"]:
            that_bai["con"] -= 1
            raise RuntimeError("Worksheet đã bị xoá")
        return resize_that(rows=rows, cols=cols)

    ws.resize = resize_chet
    _exporter(moi_truong).ghi_de(HEADER, ROWS)

    assert dem["service_account"] == 2              # đã mở lại kết nối mới
    assert ws.noi_dung == [HEADER, list(ROWS[0])]


def test_ghi_de_ket_noi_moi_that_bai_thi_khong_thu_lai(moi_truong, monkeypatch):
    """Sai link / mất quyền: thử lại vô ích và bắt người dùng chờ gấp đôi."""
    import gspread

    dem = moi_truong["dem"]
    sheets.xoa_cache_ket_noi()

    def service_account_loi(filename=None):
        dem["service_account"] += 1
        raise RuntimeError("PERMISSION_DENIED")

    monkeypatch.setattr(gspread, "service_account", service_account_loi)
    with pytest.raises(RuntimeError):
        _exporter(moi_truong).ghi_de(HEADER, ROWS)

    assert dem["service_account"] == 1


def test_o_cot_doi_dung_chu_cai():
    """34 cột của bảng Ngang phải ra tới AH — sai chữ cái là đọc nhầm vùng."""
    assert sheets._o_cot(1) == "A"
    assert sheets._o_cot(26) == "Z"
    assert sheets._o_cot(27) == "AA"
    assert sheets._o_cot(34) == "AH"
