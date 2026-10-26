# -*- coding: utf-8 -*-
"""Chẩn đoán gửi Google Sheets — PC2 12/10/2026, lượt quét #15 (việc tự động bị BLOCKED_CONFIG).

Bối cảnh: Drive báo tài khoản dịch vụ CÓ quyền Writer mà việc gửi vẫn bị chặn với câu chung «Tài khoản dịch vụ
không có quyền mở bảng — chia sẻ bảng…». gspread 6.2.1 ``Client.open_by_key`` biến MỌI HTTP 403 thành
``PermissionError`` trần (``gspread/client.py:172``); chi tiết của Google (``error.status`` + ``details[].reason``,
vd. ``SERVICE_DISABLED`` khi Google Sheets API chưa bật trong project của tài khoản dịch vụ) chỉ còn ở
``__cause__``. Hệ quả: API chưa bật, khoá của tài khoản KHÁC, bảng KHÁC đều hiện cùng một câu — người dùng
không biết phải sửa gì, và không thấy việc đang dùng tài khoản dịch vụ / bảng nào.

Khoá (không đổi phân loại: vẫn ``ChuaGui`` vĩnh viễn, 0 ghi):
* lý do nêu ĐÚNG nguyên nhân theo ``reason`` liệt kê của Google — không chép message gốc (có thể mang URL/mã);
* lỗi truy cập (403/404/khoá bị từ chối) kèm tài khoản dịch vụ + binding + mã bảng RÚT GỌN của chính việc;
* giao diện nói được VÌ SAO một việc chưa gửi (tạm dừng, hồ sơ tạm dừng, hẹn giờ, người gửi chưa giữ quyền,
  người gửi giữ việc lâu bất thường).
Máy chủ Sheets GIẢ ở tầng HTTP + gspread thật; khoá GIẢ; không mạng.
"""
from types import SimpleNamespace

import google.auth.exceptions as gae
import gspread
import pytest

import lich_su
import outbox as ob
import sheet_destinations as sd
from outbox_gia import khoa_gia
from sheets_http_gia import DOC, GHI, LoiHttp, MayChuSheetsGia, TabGia, moc_mot_lan

ID = "1" + "z" * 43
ID_NGAN = ID[:6]
HEADER = [f"Cột {i}" for i in range(1, 35)]
ROWS = [["v1"] + [""] * 33]
SA = "gui@du-an-gia.invalid"
_CHUA_SUA = pytest.mark.xfail(strict=True, reason="chưa có bản sửa chẩn đoán — commit sửa gỡ dấu này")


@pytest.fixture()
def gia(monkeypatch, tmp_path):
    may = MayChuSheetsGia(ID, [TabGia(0, "KetQuaQuet", [HEADER], so_cot=34)])
    monkeypatch.setattr(gspread, "service_account", lambda filename: gspread.Client(auth=None, session=may))
    khoa = tmp_path / "k.json"
    khoa.write_text("{}", encoding="utf-8")
    return {"may": may, "khoa": str(khoa)}


def _chot(gid=0, ref="timclip_02", principal=SA, sid=ID):
    return sd.DichGuiChot(dich_id="d", phien_ban=1, workspace="mac_dinh", installation_id="c" * 32,
                          ten="VanPhong", spreadsheet_id=sid, worksheet_id=gid, worksheet_ten="KetQuaQuet",
                          schema_id=sd.SCHEMA_NGANG, xac_thuc_ref=ref, principal=principal, key_id="k1",
                          cho_xoay_khoa=True)


def _gui(gia, chot=None):
    return ob.CongGspread().gui(chot or _chot(), gia["khoa"], HEADER, ROWS, lambda gid, ten: None)


def _ghi(gia):
    return [y for y in gia["may"].nhat_ky if y["loai"] in GHI]


def _loi_gui(gia, loi, noi=("metadata",)):
    gia["may"].moc = moc_mot_lan(lambda sk, yc: sk == "den" and yc["loai"] in noi, _nem(loi))
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia)
    assert e.value.tam_thoi is False and _ghi(gia) == []
    assert ID not in e.value.ly_do and "docs.google.com" not in e.value.ly_do
    return e.value.ly_do


def _nem(loi):
    def viec(su_kien, yc):
        raise loi
    return viec


# ---------------------------------------------------------------- lý do theo reason của Google

@_CHUA_SUA
def test_403_api_chua_bat_noi_dung_nguyen_nhan_khong_bao_chia_se(gia):
    ly_do = _loi_gui(gia, LoiHttp(403, "Google Sheets API has not been used in project 123456 before or it is "
                                       "disabled. Enable it by visiting https://console.developers.google.com",
                                  ly_do_google="SERVICE_DISABLED"))
    assert "Google Sheets API" in ly_do and "chưa bật" in ly_do
    assert "123456" not in ly_do and "console.developers" not in ly_do          # không chép message gốc


@_CHUA_SUA
def test_403_thieu_scope_noi_dung_nguyen_nhan(gia):
    ly_do = _loi_gui(gia, LoiHttp(403, "Request had insufficient authentication scopes.",
                                  ly_do_google="ACCESS_TOKEN_SCOPE_INSUFFICIENT"))
    assert "phạm vi" in ly_do and "insufficient" not in ly_do


@_CHUA_SUA
def test_403_khong_co_quyen_neu_tai_khoan_binding_va_bang_rut_gon(gia):
    ly_do = _loi_gui(gia, LoiHttp(403, "The caller does not have permission"))
    assert "chia sẻ" in ly_do                                        # giữ hướng dẫn cũ cho đúng trường hợp này
    assert SA in ly_do and "timclip_02" in ly_do and ID_NGAN in ly_do


@_CHUA_SUA
def test_404_khong_thay_bang_neu_tai_khoan_va_bang_rut_gon(gia):
    ly_do = _loi_gui(gia, LoiHttp(404, "Requested entity was not found."))
    assert SA in ly_do and "timclip_02" in ly_do and ID_NGAN in ly_do


@_CHUA_SUA
def test_khoa_bi_google_tu_choi_neu_tai_khoan(gia):
    ly_do = _loi_gui(gia, gae.RefreshError("invalid_grant: account not found"))
    assert SA in ly_do and "timclip_02" in ly_do and "invalid_grant" not in ly_do


@_CHUA_SUA
def test_403_khi_doc_tieu_de_cung_neu_reason(gia):
    ly_do = _loi_gui(gia, LoiHttp(403, "disabled", ly_do_google="SERVICE_DISABLED"), noi=DOC)
    assert "Google Sheets API" in ly_do and "chưa bật" in ly_do


@_CHUA_SUA
def test_404_khi_doc_tieu_de_cung_kem_ngu_canh(gia):
    ly_do = _loi_gui(gia, LoiHttp(404, "Requested entity was not found."), noi=DOC)
    assert SA in ly_do and "timclip_02" in ly_do and ID_NGAN in ly_do


def test_loi_tam_va_lo_cau_hinh_khac_khong_bi_gan_ngu_canh(gia):
    gia["may"].moc = moc_mot_lan(lambda sk, yc: sk == "den" and yc["loai"] == "metadata",
                                 _nem(LoiHttp(429, "quota")))
    with pytest.raises(ob.ChuaGui) as e:
        _gui(gia)
    assert e.value.tam_thoi is True and SA not in e.value.ly_do


@_CHUA_SUA
def test_kiem_chi_doc_cung_chan_doan_dung(gia):
    gia["may"].loi_mo = LoiHttp(403, "disabled", ly_do_google="SERVICE_DISABLED")
    ok, tb = ob.CongGspread().kiem(_chot(), gia["khoa"], HEADER)
    assert ok is False and "Google Sheets API" in tb and _ghi(gia) == []
    gia["may"].loi_mo = LoiHttp(403, "The caller does not have permission")
    ok, tb = ob.CongGspread().kiem(_chot(), gia["khoa"], HEADER)
    assert ok is False and SA in tb and "timclip_02" in tb and ID not in tb


def test_permission_error_tran_khong_cause_van_la_loi_cau_hinh_chia_se():
    loi = ob.phan_loai_loi(PermissionError(), da_phat=False)
    assert isinstance(loi, ob.ChuaGui) and loi.tam_thoi is False and "chia sẻ" in loi.ly_do


# ---------------------------------------------------------------- vì sao việc chưa gửi

IID = "c" * 32


@pytest.fixture()
def mt(tmp_path):
    db = str(tmp_path / "data" / "lichsu.db")
    (tmp_path / "data").mkdir()
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    a = sd.tao_dich(db, ten="VanPhong", spreadsheet_id=ID, worksheet_id=0, worksheet_ten="KetQuaQuet",
                    schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    return {"db": db, "a": a}


def _xep(mt, job_id=1):
    y = sd.chot_y_dinh(mt["db"], mt["a"].id, installation_id=IID, lo_id="lo1")
    with sd.ket_noi(mt["db"], ghi=True) as con:
        return ob.them_viec(con, y, job_id=job_id, chinh_sach="v2", header=HEADER, rows=ROWS)


def _nen(dang_chay=True, co_quyen=True, loi_cuoi="", ban_cu=""):
    return SimpleNamespace(dang_chay=dang_chay, co_quyen=co_quyen, loi_cuoi=loi_cuoi, ban_cu=ban_cu)


def _ly_do(mt, vid, **kw):
    return ob.ly_do_chua_gui(mt["db"], ob.lay_viec(mt["db"], vid), **kw)


def _sua(mt, vid, **cot):
    with sd.ket_noi(mt["db"], ghi=True) as con:
        con.execute(f"UPDATE hang_doi_gui SET {', '.join(f'{k}=?' for k in cot)} WHERE id=?", (*cot.values(), vid))


@_CHUA_SUA
def test_cho_vi_tam_dung_toan_bo(mt):
    vid = _xep(mt)
    ob.dat_tam_dung(mt["db"], True)
    assert "tạm dừng toàn bộ" in _ly_do(mt, vid, bay_gio=1e9, nen=_nen())


@_CHUA_SUA
def test_cho_vi_ho_so_tam_dung(mt):
    vid = _xep(mt)
    sd.doi_trang_thai(mt["db"], mt["a"].id, sd.TT_TAM_DUNG)
    assert "Hồ sơ đích đang tạm dừng" in _ly_do(mt, vid, bay_gio=1e9, nen=_nen())


@_CHUA_SUA
def test_cho_vi_hen_gio_thu_lai(mt):
    vid = _xep(mt)
    _sua(mt, vid, trang_thai=ob.RETRY_WAIT, thu_lai_sau=2e9, loi="Lỗi mạng khi kiểm bảng (ConnectionError).")
    ly_do = _ly_do(mt, vid, bay_gio=1e9, nen=_nen())
    assert "Hẹn thử" in ly_do and "Lỗi mạng" in ly_do


@_CHUA_SUA
def test_gio_do_tang_giao_dien_dinh_dang(mt):
    vid = _xep(mt)
    _sua(mt, vid, trang_thai=ob.RETRY_WAIT, thu_lai_sau=2e9, loi="x")
    assert "lúc 12:34:56" in _ly_do(mt, vid, bay_gio=1e9, nen=_nen(), gio=lambda t: "12:34:56")
    assert "lúc" not in _ly_do(mt, vid, bay_gio=1e9, nen=_nen())          # lõi không tự đổi epoch sang giờ


@_CHUA_SUA
def test_cho_vi_hoan_theo_nhom(mt):
    vid = _xep(mt)
    _sua(mt, vid, thu_lai_sau=2e9)
    assert "cùng bảng/tab" in _ly_do(mt, vid, bay_gio=1e9, nen=_nen())


@_CHUA_SUA
@pytest.mark.parametrize("nen, mau", [
    (None, "chưa chạy"),
    (_nen(dang_chay=False), "chưa chạy"),
    (_nen(ban_cu="bản mới đã kích hoạt"), "nhường"),
    (_nen(co_quyen=False), "chưa giữ quyền"),
    (_nen(loi_cuoi="OperationalError"), "OperationalError"),
])
def test_cho_vi_nguoi_gui(mt, nen, mau):
    vid = _xep(mt)
    assert mau in _ly_do(mt, vid, bay_gio=1e9, nen=nen)


@_CHUA_SUA
def test_san_sang_thi_bao_sap_gui(mt):
    vid = _xep(mt)
    assert "Sắp gửi" in _ly_do(mt, vid, bay_gio=1e9, nen=_nen())


@_CHUA_SUA
def test_claimed_lau_bat_thuong_bao_cach_xu_ly_khong_gui_trung(mt):
    vid = _xep(mt)
    _sua(mt, vid, trang_thai=ob.CLAIMED, claim_luc=1000.0)
    assert "đang xử lý" in _ly_do(mt, vid, bay_gio=1010.0, nen=_nen())
    lau = _ly_do(mt, vid, bay_gio=1000.0 + ob.HAN_GIU_VIEC_LAU_S + 1, nen=_nen())
    assert "lâu bất thường" in lau and "chưa ghi gì" in lau


@_CHUA_SUA
@pytest.mark.parametrize("trang_thai", [ob.SENT, ob.BLOCKED_CONFIG, ob.UNKNOWN, ob.CANCELLED, ob.SENDING])
def test_trang_thai_khac_khong_co_ly_do_cho(mt, trang_thai):
    vid = _xep(mt)
    _sua(mt, vid, trang_thai=trang_thai)
    assert _ly_do(mt, vid, bay_gio=1e9, nen=_nen()) == ""


# ---------------------------------------------------------------- bảng hồ sơ nói rõ bảng + tài khoản dịch vụ

@_CHUA_SUA
def test_dong_ho_so_hien_bang_rut_gon_va_tai_khoan_dich_vu(mt):
    import ui_gui_sheets as ui
    xt = {x.ref: x for x in sd.ds_xac_thuc(mt["db"])}
    dong = ui.dong_ho_so(sd.lay_dich(mt["db"], mt["a"].id), xt)
    assert dong["Bảng"].startswith(ID_NGAN) and ID not in dong["Bảng"]
    assert dong["Tài khoản dịch vụ"] == "gui@du-an-gia.invalid" and dong["Khoá"] == "mac_dinh"
