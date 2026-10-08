# -*- coding: utf-8 -*-
"""Transport Google Sheets thật của outbox (``outbox.CongGspread``) — gspread THẬT trên máy chủ Sheets GIẢ ở tầng
HTTP (``sheets_http_gia``), ngoại lệ THẬT của gspread/requests/google-auth.

Khoá:
* thứ tự: tìm tab (metadata) → kiểm tiêu đề CHỈ ĐỌC, THEO MÃ (``values:batchGetByDataFilter``) → ``truoc_khi_gui``
  (commit SENDING) → MỘT ``spreadsheets.batchUpdate`` AppendCells{sheetId}; không request nào sau bước tìm tab mang
  tên tab (MR-R2-P1-01 — gspread ``get_values``/``append_rows`` dựng A1 từ TÊN);
* mọi lỗi trước dispatch → ``ChuaGui`` và 0 request ghi; sau dispatch chỉ kiểu chứng minh "không tới / bị từ chối"
  mới là ``ChuaGui`` — ReadTimeout, 5xx, 408, mất kết nối giữa chừng → ``KhongRo``;
* lý do không chứa mã bảng/URL dù message gốc có;
* timeout được đặt cho MỌI request (HTTPClient mặc định chờ vô hạn).
Không mạng: ``gspread.service_account`` → ``gspread.Client(auth=None, session=máy_chủ_giả)``.
"""
import google.auth.exceptions as gae
import gspread
import pytest
import requests
import urllib3.exceptions as u3

import outbox as ob
import sheet_destinations as sd
from sheets_http_gia import DOC, GHI, LoiHttp, MayChuSheetsGia, TabGia, moc_mot_lan

ID = "1" + "z" * 43
URL_BANG = f"https://docs.google.com/spreadsheets/d/{ID}/edit"
HEADER = [f"Cột {i}" for i in range(1, 35)]
ROWS = [["v1"] + [""] * 33, ["v2"] + [""] * 33]


@pytest.fixture()
def gia(monkeypatch, tmp_path):
    may = MayChuSheetsGia(ID, [TabGia(0, "KetQuaQuet", [HEADER], so_cot=34)])
    monkeypatch.setattr(gspread, "service_account", lambda filename: gspread.Client(auth=None, session=may))
    khoa = tmp_path / "k.json"
    khoa.write_text("{}", encoding="utf-8")
    return {"may": may, "khoa": str(khoa), "su_kien": []}


def _chot(gid=0, ten="KetQuaQuet"):
    return sd.DichGuiChot(dich_id="d", phien_ban=1, workspace="mac_dinh", installation_id="c" * 32,
                          ten="Bảng", spreadsheet_id=ID, worksheet_id=gid, worksheet_ten=ten,
                          schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh",
                          principal="gui@x.invalid", key_id="k1", cho_xoay_khoa=True)


def _gui(gia, chot=None):
    def truoc(gid, ten):
        gia["su_kien"].append(("SENDING", len(gia["may"].nhat_ky)))
        gia["tab_da_tim"] = (gid, ten)
    return ob.CongGspread().gui(chot or _chot(), gia["khoa"], HEADER, ROWS, truoc)


def _ghi(gia):
    return [y for y in gia["may"].nhat_ky if y["loai"] in GHI]


def _sending(gia):
    return any(s[0] == "SENDING" for s in gia["su_kien"])


def _nem(loi):
    def viec(su_kien, yc):
        raise loi
    return viec


def test_thu_tu_tim_tab_doc_theo_ma_roi_sending_roi_mot_batchUpdate(gia):
    kq = _gui(gia)
    nk = gia["may"].nhat_ky
    assert [y["loai"] for y in nk] == ["metadata", "metadata", "batchGetByDataFilter", "batchUpdate"]
    assert gia["su_kien"] == [("SENDING", 3)]                          # SENDING sau khi đọc, trước request ghi
    # Đọc ĐÚNG hàng tiêu đề (hàng 1, đủ bề rộng báo cáo) — không kéo cả trang tính về mỗi lần gửi.
    assert nk[2]["body"]["dataFilters"] == [{"gridRange": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1,
                                                           "startColumnIndex": 0, "endColumnIndex": 34}}]
    assert set(gia["may"].timeouts) == {ob.CongGspread.THOI_GIAN_CHO}
    (yc,) = nk[-1]["body"]["requests"]
    assert yc["appendCells"]["sheetId"] == 0 and len(yc["appendCells"]["rows"]) == 2
    assert kq.yeu_cau == nk[-1]["body"] and kq.worksheet_ten == "KetQuaQuet"
    assert gia["may"].tab(0).du_lieu() == [HEADER, ["v1"], ["v2"]]


def test_trang_tinh_trong_that_ghi_tieu_de_va_dong_trong_mot_lan(gia):
    gia["may"].tabs[0] = TabGia(0, "KetQuaQuet", [], so_cot=34)
    _gui(gia)
    doc = [y for y in gia["may"].nhat_ky if y["loai"] in DOC]
    assert len(doc) == 2 and doc[1]["body"]["dataFilters"] == [{"gridRange": {"sheetId": 0}}]   # dò lần hai
    (ghi,) = _ghi(gia)
    assert len(ghi["body"]["requests"][-1]["appendCells"]["rows"]) == 3
    assert gia["may"].tab(0).du_lieu() == [HEADER, ["v1"], ["v2"]]


@pytest.mark.parametrize("hang", [
    [["Sai tiêu đề"]],
    [[], ["dữ liệu cũ ở hàng 2"]],
    [[""] * 34 + ["ô ngoài bề rộng"]],
])
def test_tieu_de_sai_hoac_hang1_trong_co_du_lieu_la_chua_gui_0_ghi(gia, hang):
    gia["may"].tabs[0] = TabGia(0, "KetQuaQuet", hang, so_cot=40)
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia)
    assert e.value.tam_thoi is False
    assert _ghi(gia) == [] and not _sending(gia)


def test_tab_theo_id_khong_con_la_chua_gui(gia):
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia, _chot(gid=99))
    assert e.value.tam_thoi is False and "tab" in e.value.ly_do and _ghi(gia) == []


def test_bo_loc_theo_ma_khong_tra_vung_nao_la_khong_thay_tab_0_ghi(gia):
    gia["may"].khong_tra_vung = True
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia)
    assert e.value.tam_thoi is False and "tab" in e.value.ly_do and _ghi(gia) == [] and not _sending(gia)


def test_ghim_theo_ten_khi_chua_co_gid_chi_dung_ten_de_tim_ma(gia):
    gia["may"].tabs[5] = TabGia(5, "Tab khác", [HEADER], so_cot=34)
    kq = _gui(gia, _chot(gid=None, ten="KetQuaQuet"))
    assert gia["tab_da_tim"] == (0, "KetQuaQuet")
    assert kq.yeu_cau["requests"][-1]["appendCells"]["sheetId"] == 0
    assert all(y["loai"] in ("metadata", "batchGetByDataFilter", "batchUpdate") for y in gia["may"].nhat_ky)


@pytest.mark.parametrize("noi, loi, tam_thoi", [
    ("metadata", LoiHttp(403, f"loi 403 {URL_BANG}"), False),            # open_by_key: 403 → PermissionError
    ("metadata", LoiHttp(404, f"loi 404 {URL_BANG}"), False),            # → SpreadsheetNotFound
    ("metadata", LoiHttp(429, "quá hạn mức"), True),
    ("metadata", LoiHttp(503, "bận"), True),
    ("doc", LoiHttp(403, f"loi 403 {URL_BANG}"), False),                 # APIError 403 khi đọc tiêu đề
    ("doc", LoiHttp(400, "Invalid dataFilters"), False),
    ("metadata", gae.RefreshError("invalid_grant"), False),
    ("metadata", gae.RefreshError("5xx", retryable=True), True),
    ("metadata", gae.TransportError("dns"), True),
    ("metadata", requests.exceptions.ConnectionError("x"), True),
    ("doc", requests.exceptions.ReadTimeout("đọc tiêu đề quá hạn"), True),
])
def test_loi_truoc_khi_phat_la_chua_gui_0_ghi(gia, noi, loi, tam_thoi):
    loai = ("metadata",) if noi == "metadata" else DOC
    gia["may"].moc = moc_mot_lan(lambda sk, yc: sk == "den" and yc["loai"] in loai, _nem(loi))
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia)
    assert e.value.tam_thoi is tam_thoi and _ghi(gia) == [] and not _sending(gia)
    assert ID not in e.value.ly_do and "docs.google.com" not in e.value.ly_do


def _ket_noi_moi_loi():
    return requests.exceptions.ConnectionError(u3.MaxRetryError(
        None, "/v4/x", reason=u3.NewConnectionError(None, "Failed to establish a new connection")))


def _mat_ket_noi_giua_chung():
    return requests.exceptions.ConnectionError(
        u3.ProtocolError("Connection aborted.", ConnectionResetError(10054, "reset")))


@pytest.mark.parametrize("loi, kieu, tam_thoi", [
    (requests.exceptions.ReadTimeout("read timed out"), ob.KhongRo, None),
    (_mat_ket_noi_giua_chung(), ob.KhongRo, None),
    (LoiHttp(500, f"loi 500 {URL_BANG}"), ob.KhongRo, None),
    (LoiHttp(502, "bad gateway"), ob.KhongRo, None),
    (LoiHttp(408, "request timeout"), ob.KhongRo, None),
    (RuntimeError("lạ"), ob.KhongRo, None),
    (requests.exceptions.ConnectTimeout("connect timeout"), ob.ChuaGui, True),
    (_ket_noi_moi_loi(), ob.ChuaGui, True),
    (LoiHttp(429, "quá hạn mức"), ob.ChuaGui, True),
    (LoiHttp(400, f"Invalid requests[0].appendCells: No grid with id: 0 {URL_BANG}"), ob.ChuaGui, False),
    (LoiHttp(403, f"loi 403 {URL_BANG}"), ob.ChuaGui, False),
    (gae.RefreshError("revoked"), ob.ChuaGui, False),
])
def test_phan_loai_loi_sau_dispatch(gia, loi, kieu, tam_thoi):
    gia["may"].moc = moc_mot_lan(lambda sk, yc: sk == "den" and yc["loai"] in GHI, _nem(loi))
    with pytest.raises(kieu) as e:
        _gui(gia)
    if tam_thoi is not None:
        assert e.value.tam_thoi is tam_thoi
    assert _sending(gia) and len(_ghi(gia)) == 1
    assert gia["may"].tab(0).du_lieu() == [HEADER]                     # máy chủ không áp dụng gì
    assert ID not in e.value.ly_do and "docs.google.com" not in e.value.ly_do


def test_mat_phan_hoi_sau_khi_may_chu_da_ghi_la_khong_ro(gia):
    gia["may"].moc = moc_mot_lan(lambda sk, yc: sk == "xong" and yc["loai"] in GHI,
                                 _nem(requests.exceptions.ReadTimeout("mất phản hồi")))
    with pytest.raises(ob.KhongRo):
        _gui(gia)
    assert gia["may"].tab(0).du_lieu() == [HEADER, ["v1"], ["v2"]]


def test_khong_dung_loi_tu_message_de_doan_chua_ghi():
    """Message nói «connection refused» nhưng KIỂU là ReadTimeout → vẫn mơ hồ."""
    loi = requests.exceptions.ReadTimeout("connection refused; Max retries exceeded")
    assert isinstance(ob.phan_loai_loi(loi, da_phat=True), ob.KhongRo)


def test_kiem_dich_chi_doc_theo_ma_khong_ghi_gi(gia):
    ok, tb = ob.CongGspread().kiem(_chot(), gia["khoa"], HEADER)
    assert ok is True and "đọc được" in tb and _ghi(gia) == []
    assert "quyền ghi" in tb                      # nói rõ: đọc được ≠ đã xác minh quyền ghi
    assert {y["loai"] for y in gia["may"].nhat_ky} == {"metadata", "batchGetByDataFilter"}


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
    gia["may"].tabs[0] = TabGia(0, "KetQuaQuet", [["Sai"]], so_cot=34)
    ok, tb = ob.CongGspread().kiem(_chot(), gia["khoa"], HEADER)
    assert ok is False and "tiêu đề" in tb and _ghi(gia) == []


def test_hang1_trong_ma_lan_do_thu_hai_loi_mang_la_chua_gui_tam_0_ghi(gia):
    """P1-03 qua outbox: hàng 1 trống → dò lần hai (theo mã); lần dò lỗi (mạng) → chưa gửi (tạm), 0 ghi."""
    gia["may"].tabs[0] = TabGia(0, "KetQuaQuet", [], so_cot=34)
    dem = {"n": 0}

    def lan_doc_thu_hai(su_kien, yc):
        if su_kien == "den" and yc["loai"] in DOC:
            dem["n"] += 1
            if dem["n"] == 2:
                raise requests.exceptions.ConnectionError("dò lần hai mất mạng")

    gia["may"].moc = lan_doc_thu_hai
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia)
    assert e.value.tam_thoi is True and _ghi(gia) == [] and not _sending(gia)
