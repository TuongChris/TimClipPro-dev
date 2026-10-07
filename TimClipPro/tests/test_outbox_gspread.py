# -*- coding: utf-8 -*-
"""Transport Google Sheets thật của outbox (``outbox.CongGspread``) với gspread GIẢ, ngoại lệ THẬT.

Khoá:
* thứ tự: kiểm tab theo ID + tiêu đề (CHỈ ĐỌC) → ``truoc_khi_gui`` (commit SENDING) → MỘT append RAW;
* mọi lỗi trước dispatch → ``ChuaGui`` và 0 lần ghi; sau dispatch chỉ kiểu chứng minh "không tới /
  bị từ chối" mới là ``ChuaGui`` — ReadTimeout, 5xx, mất kết nối giữa chừng → ``KhongRo``;
* lý do không chứa mã bảng/URL dù message gốc có;
* timeout được đặt (HTTPClient mặc định chờ vô hạn).
Không mạng: ``gspread.service_account`` bị thay bằng client giả.
"""
import google.auth.exceptions as gae
import gspread
import pytest
import requests
import urllib3.exceptions as u3

import outbox as ob
import sheet_destinations as sd

ID = "1" + "z" * 43
HEADER = [f"Cột {i}" for i in range(1, 35)]
ROWS = [["v1"] + [""] * 33, ["v2"] + [""] * 33]


class PhanHoiLoi:
    def __init__(self, ma, trang_thai="LOI", thong_diep=None):
        self.status_code = ma
        self.text = thong_diep or f"loi {ma} https://docs.google.com/spreadsheets/d/{ID}/edit"
        self._ma, self._tt, self._td = ma, trang_thai, self.text

    def json(self):
        return {"error": {"code": self._ma, "message": self._td, "status": self._tt}}


def loi_api(ma, tt="LOI"):
    return gspread.exceptions.APIError(PhanHoiLoi(ma, tt))


class Tab:
    def __init__(self, ghi, gid=0, ten="KetQuaQuet", hang1=None, toan_bang=None):
        self.id, self.title, self._ghi = gid, ten, ghi
        self.hang1 = [list(HEADER)] if hang1 is None else hang1
        self.toan_bang = toan_bang
        self.loi_append = None

    def get_values(self, rng):
        self._ghi.append(("doc", rng))
        return self.hang1

    def get_all_values(self):
        self._ghi.append(("doc_tat_ca",))
        return self.toan_bang if self.toan_bang is not None else self.hang1

    def append_rows(self, values, value_input_option=None, **kw):
        self._ghi.append(("append", len(values), value_input_option))
        if self.loi_append is not None:
            raise self.loi_append
        return {"spreadsheetId": ID, "updates": {"spreadsheetId": ID,
                "updatedRange": f"'{self.title}'!A2:AH{1 + len(values)}",
                "updatedRows": len(values)}}

    def append_row(self, *a, **k):   # outbox KHÔNG được dùng đường hai lần ghi
        raise AssertionError("append_row không được gọi")


class Bang:
    def __init__(self, tab, loi_mo=None):
        self.tab, self.loi_mo = tab, loi_mo

    def get_worksheet_by_id(self, gid):
        if gid != self.tab.id:
            raise gspread.exceptions.WorksheetNotFound(gid)
        return self.tab

    def worksheet(self, ten):
        if ten != self.tab.title:
            raise gspread.exceptions.WorksheetNotFound(ten)
        return self.tab


class Khach:
    def __init__(self, bang, nhat_ky):
        self.bang, self.nhat_ky = bang, nhat_ky

    def set_timeout(self, t):
        self.nhat_ky.append(("timeout", t))

    def open_by_key(self, key):
        self.nhat_ky.append(("mo", key))
        if self.bang.loi_mo is not None:
            raise self.bang.loi_mo
        return self.bang


@pytest.fixture()
def gia(monkeypatch, tmp_path):
    nk = []
    tab = Tab(nk)
    bang = Bang(tab)
    monkeypatch.setattr(gspread, "service_account", lambda filename: Khach(bang, nk))
    khoa = tmp_path / "k.json"
    khoa.write_text("{}", encoding="utf-8")
    return {"nk": nk, "tab": tab, "bang": bang, "khoa": str(khoa)}


def _chot(gid=0, ten="KetQuaQuet"):
    return sd.DichGuiChot(dich_id="d", phien_ban=1, workspace="mac_dinh", installation_id="c" * 32,
                          ten="Bảng", spreadsheet_id=ID, worksheet_id=gid, worksheet_ten=ten,
                          schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh",
                          principal="gui@x.invalid", key_id="k1", cho_xoay_khoa=True)


def _gui(gia, chot=None):
    def truoc(gid, ten):
        gia["nk"].append(("SENDING",))
        gia["tab_da_tim"] = (gid, ten)
    return ob.CongGspread().gui(chot or _chot(), gia["khoa"], HEADER, ROWS, truoc)


def _ghi(gia):
    return [x for x in gia["nk"] if x[0] == "append"]


def test_thu_tu_doc_roi_sending_roi_mot_append_raw(gia):
    kq = _gui(gia)
    buoc = [x[0] for x in gia["nk"]]
    assert buoc == ["timeout", "mo", "doc", "SENDING", "append"]
    assert gia["nk"][0] == ("timeout", ob.CongGspread.THOI_GIAN_CHO)
    assert _ghi(gia) == [("append", 2, "RAW")]
    assert (kq.so_dong_gui, kq.worksheet_id, kq.worksheet_ten) == (2, 0, "KetQuaQuet")


def test_trang_tinh_trong_that_ghi_tieu_de_va_dong_trong_mot_lan(gia):
    gia["tab"].hang1, gia["tab"].toan_bang = [], []
    kq = _gui(gia)
    assert _ghi(gia) == [("append", 3, "RAW")] and kq.so_dong_gui == 3


@pytest.mark.parametrize("hang1, toan_bang", [
    ([["Sai tiêu đề"]], None),
    ([], [[], ["dữ liệu cũ ở hàng 2"]]),
    ([[""] * 34], [[""] * 34 + ["ô ngoài bề rộng"]]),
])
def test_tieu_de_sai_hoac_hang1_trong_co_du_lieu_la_chua_gui_0_ghi(gia, hang1, toan_bang):
    gia["tab"].hang1, gia["tab"].toan_bang = hang1, toan_bang
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia)
    assert e.value.tam_thoi is False
    assert _ghi(gia) == [] and ("SENDING",) not in gia["nk"]


def test_tab_theo_id_khong_con_la_chua_gui(gia):
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia, _chot(gid=99))
    assert e.value.tam_thoi is False and "tab" in e.value.ly_do and _ghi(gia) == []


def test_ghim_theo_ten_khi_chua_co_gid(gia):
    kq = _gui(gia, _chot(gid=None, ten="KetQuaQuet"))
    assert kq.worksheet_id == 0 and _ghi(gia)


@pytest.mark.parametrize("loi, tam_thoi", [
    (PermissionError(), False),                     # gspread.open_by_key: HTTP 403
    (loi_api(403, "PERMISSION_DENIED"), False), (loi_api(404, "NOT_FOUND"), False),
    (loi_api(429), True), (loi_api(503), True),
    (gae.RefreshError("invalid_grant"), False), (gae.RefreshError("5xx", retryable=True), True),
    (gae.TransportError("dns"), True),
    (requests.exceptions.ConnectionError("x"), True),
])
def test_loi_khi_mo_bang_la_chua_gui(gia, loi, tam_thoi):
    gia["bang"].loi_mo = loi
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia)
    assert e.value.tam_thoi is tam_thoi and _ghi(gia) == []


def _ket_noi_moi_loi():
    return requests.exceptions.ConnectionError(u3.MaxRetryError(
        None, "/v4/x", reason=u3.NewConnectionError(None, "Failed to establish a new connection")))


def _mat_ket_noi_giua_chung():
    return requests.exceptions.ConnectionError(
        u3.ProtocolError("Connection aborted.", ConnectionResetError(10054, "reset")))


@pytest.mark.parametrize("loi, kieu, tam_thoi", [
    (requests.exceptions.ReadTimeout("read timed out"), ob.KhongRo, None),
    (_mat_ket_noi_giua_chung(), ob.KhongRo, None),
    (loi_api(500), ob.KhongRo, None),
    (loi_api(502), ob.KhongRo, None),
    (loi_api(408), ob.KhongRo, None),
    (RuntimeError("lạ"), ob.KhongRo, None),
    (requests.exceptions.ConnectTimeout("connect timeout"), ob.ChuaGui, True),
    (_ket_noi_moi_loi(), ob.ChuaGui, True),
    (loi_api(429), ob.ChuaGui, True),
    (loi_api(400, "INVALID_ARGUMENT"), ob.ChuaGui, False),
    (loi_api(403, "PERMISSION_DENIED"), ob.ChuaGui, False),
    (gae.RefreshError("revoked"), ob.ChuaGui, False),
])
def test_phan_loai_loi_sau_dispatch(gia, loi, kieu, tam_thoi):
    gia["tab"].loi_append = loi
    with pytest.raises(kieu) as e:
        _gui(gia)
    if tam_thoi is not None:
        assert e.value.tam_thoi is tam_thoi
    assert ("SENDING",) in gia["nk"]
    assert ID not in e.value.ly_do and "docs.google.com" not in e.value.ly_do


def test_khong_dung_loi_tu_message_de_doan_chua_ghi():
    """Message nói «connection refused» nhưng KIỂU là ReadTimeout → vẫn mơ hồ."""
    loi = requests.exceptions.ReadTimeout("connection refused; Max retries exceeded")
    assert isinstance(ob.phan_loai_loi(loi, da_phat=True), ob.KhongRo)


def test_kiem_dich_chi_doc_khong_ghi_gi(gia):
    ok, tb = ob.CongGspread().kiem(_chot(), gia["khoa"], HEADER)
    assert ok is True and "đọc được" in tb and _ghi(gia) == []
    assert "quyền ghi" in tb                      # nói rõ: đọc được ≠ đã xác minh quyền ghi


def test_gui_bao_ma_va_ten_tab_da_tim_truoc_khi_ghi(gia):
    _gui(gia, _chot(gid=None, ten="KetQuaQuet"))
    assert gia["tab_da_tim"] == (0, "KetQuaQuet")


def test_truoc_khi_gui_tu_choi_thi_khong_ghi_gi(gia):
    def tu_choi(gid, ten):
        raise ob.ChuaGui("đối chiếu sai", tam_thoi=False)
    with pytest.raises(ob.ChuaGui):
        ob.CongGspread().gui(_chot(), gia["khoa"], HEADER, ROWS, tu_choi)
    assert _ghi(gia) == []


def test_kiem_doi_chieu_ten_tab(gia):
    ok, tb = ob.CongGspread().kiem(_chot(), gia["khoa"], HEADER, ten_doi_chieu="Tên khác")
    assert ok is False and "khác tên đối chiếu" in tb and _ghi(gia) == []


def test_kiem_dich_chi_doc_tab_khong_con(gia):
    ok, tb = ob.CongGspread().kiem(_chot(gid=99), gia["khoa"], HEADER)
    assert ok is False and _ghi(gia) == []


def test_kiem_dich_chi_doc_tieu_de_sai(gia):
    gia["tab"].hang1 = [["Sai"]]
    ok, tb = ob.CongGspread().kiem(_chot(), gia["khoa"], HEADER)
    assert ok is False and "tiêu đề" in tb and _ghi(gia) == []


def test_hang1_trong_ma_lan_do_thu_hai_loi_mang_la_chua_gui_tam_0_ghi(gia, monkeypatch):
    """P1-03 qua outbox: hàng 1 trống → dò lần hai; lần dò lỗi (mạng) → chưa gửi (tạm), 0 ghi."""
    gia["tab"].hang1 = []

    def do_loi():
        raise requests.exceptions.ConnectionError("dò lần hai mất mạng")

    monkeypatch.setattr(gia["tab"], "get_all_values", do_loi)
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia)
    assert e.value.tam_thoi is True and _ghi(gia) == [] and ("SENDING",) not in gia["nk"]
