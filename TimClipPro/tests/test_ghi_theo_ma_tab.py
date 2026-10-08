# -*- coding: utf-8 -*-
"""MR-R2-P1-01 (tái audit độc lập 78ba20c, 08/10/2026): transport ghi theo TÊN A1, không theo mã tab đã ghim.

Mã cũ: ``CongGspread.gui`` tìm tab THEO MÃ (metadata) nhưng đọc hàng tiêu đề và GHI qua ``Worksheet`` của gspread —
``get_values``/``append_rows`` dựng range A1 từ ``self.title`` (gspread 6.2.1 ``worksheet.py:1852``), mà
``spreadsheets.values.append`` định tuyến theo TÊN tại lúc request tới. Tab 101 đổi tên + tab 202 mang tên cũ giữa
lúc kiểm và lúc ghi → dòng vào 202, biên nhận vẫn nói 101 (``ws.id`` local) → SENT.

Nay: MỌI request chạm nội dung tab định tuyến bằng ``sheetId`` — đọc qua ``values:batchGetByDataFilter``
(``gridRange.sheetId``), ghi bằng MỘT ``spreadsheets.batchUpdate`` ``AppendCells{sheetId}``; biên nhận đọc mã tab TỪ
THÂN REQUEST đã phát. Chạy gspread THẬT trên máy chủ Sheets GIẢ ở tầng HTTP (``sheets_http_gia``) — không mock ở
mức "ghi theo chot.worksheet_id": mỗi assert kiểm request thật sự tới máy chủ và nơi máy chủ (theo ngữ nghĩa tài
liệu) đã ghi. Không mạng, dữ liệu tổng hợp.
"""
import json

import gspread
import pytest
import requests

import lich_su
import outbox as ob
import sheet_destinations as sd
from outbox_gia import khoa_gia
from sheets_http_gia import DOC, GHI, MayChuSheetsGia, TabGia, moc_mot_lan

ID_A = "1" + "a" * 43
IID = "c" * 32
HEADER = [f"Cột {i}" for i in range(1, 35)]
CU = ["dòng cũ"]                                       # dòng dữ liệu có sẵn trong tab thật (đã định dạng)


class DongHo:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture()
def mt(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    db = str(tmp_path / "data" / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    may = MayChuSheetsGia(ID_A, [TabGia(101, "KetQuaQuet", [HEADER, CU + [""] * 33], so_cot=34)])
    monkeypatch.setattr(gspread, "service_account", lambda filename: gspread.Client(auth=None, session=may))
    return {"db": db, "data": str(tmp_path / "data"), "tmp": tmp_path, "may": may}


def _ho_so(mt, *, gid=None, tab="KetQuaQuet"):
    return sd.tao_dich(mt["db"], ten="Bảng thử", spreadsheet_id=ID_A, worksheet_id=gid, worksheet_ten=tab,
                       schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh", workspace="mac_dinh")


def _link_cu(mt):
    """Đường nhập link cũ: bỏ ``#gid``, hồ sơ theo TÊN «KetQuaQuet»."""
    return sd.nhap_link_cu(mt["db"], f"https://docs.google.com/spreadsheets/d/{ID_A}/edit#gid=0",
                           schema_id=sd.SCHEMA_NGANG, duong_dan_khoa=str(mt["tmp"] / "khoa.json"),
                           workspace="mac_dinh")


HO_SO = {"link_cu": _link_cu, "theo_ten": lambda mt: _ho_so(mt), "co_ma": lambda mt: _ho_so(mt, gid=101)}


def _xep(mt, dich, job_id, rows=None):
    y = sd.chot_y_dinh(mt["db"], dich.id, installation_id=IID, lo_id="lo")
    with sd.ket_noi(mt["db"], ghi=True) as con:
        return ob.them_viec(con, y, job_id=job_id, chinh_sach="v2", header=HEADER,
                            rows=rows or [[f"dòng {job_id}"] + [""] * 33])


def _ng(mt):
    ng = ob.NguoiGui(mt["db"], mt["data"], ob.CongGspread(), dong_ho=DongHo())
    assert ng.nhan_quyen()
    return ng


def _viec(mt, vid):
    return ob.lay_viec(mt["db"], vid)


def _yc(mt, loai):
    return [y for y in mt["may"].nhat_ky if y["loai"] in loai]


def _doi_ten_va_tao_lai(may, *, hang=(HEADER,)):
    """Thao tác quản trị phía máy chủ: tab 101 đổi tên, tab MỚI 202 mang đúng tên cũ."""
    may.doi_ten(101, "ArchivedOriginal")
    may.them_tab(202, "KetQuaQuet", [list(h) for h in hang], so_cot=34)


def _nem(loi):
    def viec(su_kien, yc):
        raise loi
    return viec


# ---------------------------------------------------------------- dựng request thật

@pytest.mark.parametrize("ho_so", ["link_cu", "co_ma"])
def test_request_doc_va_ghi_deu_dinh_tuyen_bang_sheetId_khong_mang_ten_tab(mt, ho_so):
    d = HO_SO[ho_so](mt)
    v = _xep(mt, d, 1)
    _ng(mt).chay_mot_vong()
    assert _viec(mt, v).trang_thai == ob.SENT
    ghi = _yc(mt, GHI)
    assert [y["loai"] for y in ghi] == ["batchUpdate"]                  # MỘT request ghi, theo mã
    (yc,) = ghi[0]["body"]["requests"]
    assert set(yc) == {"appendCells"} and yc["appendCells"]["sheetId"] == 101
    assert yc["appendCells"]["fields"] == "userEnteredValue"
    assert "KetQuaQuet" not in json.dumps(ghi[0]["body"], ensure_ascii=False)
    doc = _yc(mt, DOC)
    assert doc and {y["loai"] for y in doc} == {"batchGetByDataFilter"}
    assert all(f["gridRange"]["sheetId"] == 101 for y in doc for f in y["body"]["dataFilters"])
    assert mt["may"].tab(101).du_lieu() == [HEADER, CU, ["dòng 1"]]


# ---------------------------------------------------------------- race đổi tên / tạo lại (kịch bản reviewer)

@pytest.mark.parametrize("ho_so", ["link_cu", "theo_ten", "co_ma"])
def test_doi_ten_va_tao_tab_cung_ten_ngay_sau_khi_doc_tieu_de_van_ghi_vao_tab_da_ghim(mt, ho_so):
    d = HO_SO[ho_so](mt)
    v = _xep(mt, d, 1)
    may = mt["may"]
    may.moc = moc_mot_lan(lambda sk, yc: sk == "xong" and yc["loai"] in DOC,
                          lambda sk, yc: _doi_ten_va_tao_lai(may))
    _ng(mt).chay_mot_vong()
    assert may.tab(202).du_lieu() == [HEADER]                            # 0 dòng vào tab mới cùng tên
    assert may.tab(101).du_lieu() == [HEADER, CU, ["dòng 1"]]
    viec = _viec(mt, v)
    assert viec.trang_thai == ob.SENT and json.loads(viec.bien_nhan)["worksheet_id"] == 101


def test_doi_ten_va_tao_lai_SAU_khi_commit_ghim_va_SENDING_truoc_request_ghi(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    may, luc_ghi = mt["may"], {}

    def chen(su_kien, yc):
        luc_ghi["viec"] = ob.lay_viec(mt["db"], v)                       # kết nối SQLite KHÁC: đã COMMIT chưa?
        luc_ghi["chot"] = sd.tab_da_chot(mt["db"], d.id, d.phien_ban)
        _doi_ten_va_tao_lai(may)

    may.moc = moc_mot_lan(lambda sk, yc: sk == "den" and yc["loai"] in GHI, chen)
    _ng(mt).chay_mot_vong()
    assert luc_ghi["viec"].trang_thai == ob.SENDING and luc_ghi["chot"].worksheet_id == 101
    assert may.tab(202).du_lieu() == [HEADER]
    assert may.tab(101).du_lieu() == [HEADER, CU, ["dòng 1"]]
    assert _viec(mt, v).trang_thai == ob.SENT


def test_tab_trong_cung_ten_xuat_hien_truoc_khi_doc_tieu_de_khong_chen_tieu_de_vao_tab_that(mt):
    """Đọc tiêu đề theo TÊN rơi vào tab trống mới → "trang tính trống" → chèn thêm hàng tiêu đề. Đọc theo MÃ: không."""
    d = _ho_so(mt, gid=101)
    v = _xep(mt, d, 1)
    may = mt["may"]
    may.moc = moc_mot_lan(lambda sk, yc: sk == "den" and yc["loai"] in DOC,
                          lambda sk, yc: _doi_ten_va_tao_lai(may, hang=()))
    _ng(mt).chay_mot_vong()
    assert may.tab(202).du_lieu() == []
    assert may.tab(101).du_lieu() == [HEADER, CU, ["dòng 1"]]           # không có hàng tiêu đề thứ hai
    assert _viec(mt, v).trang_thai == ob.SENT


def test_tab_da_ghim_bi_xoa_giua_luc_doc_va_luc_ghi_0_dong_va_khong_bao_gio_chon_tab_moi(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    may = mt["may"]

    def xoa_va_tao(su_kien, yc):
        may.xoa_tab(101)
        may.them_tab(202, "KetQuaQuet", [HEADER], so_cot=34)

    may.moc = moc_mot_lan(lambda sk, yc: sk == "xong" and yc["loai"] in DOC, xoa_va_tao)
    ng = _ng(mt)
    ng.chay_mot_vong()
    assert may.tab(202).du_lieu() == [HEADER]
    assert _viec(mt, v).trang_thai == ob.BLOCKED_CONFIG                # batchUpdate nguyên tử bị từ chối: chưa ghi
    assert sd.tab_da_chot(mt["db"], d.id, d.phien_ban).worksheet_id == 101
    ob.thu_lai(mt["db"], v)                                             # người dùng bấm «Thử gửi lại»
    ng.chay_mot_vong()
    assert may.tab(202).du_lieu() == [HEADER]                           # vẫn không nhận tab mới cùng tên
    viec = _viec(mt, v)
    assert viec.trang_thai == ob.BLOCKED_CONFIG and "mã tab" in viec.loi


def test_mat_phan_hoi_sau_khi_ghi_theo_ma_la_khong_ro_khong_gui_lai_mu_gui_lai_van_vao_tab_da_ghim(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    may = mt["may"]
    may.moc = moc_mot_lan(lambda sk, yc: sk == "xong" and yc["loai"] in GHI,
                          _nem(requests.exceptions.ReadTimeout("mất phản hồi")))
    ng = _ng(mt)
    ng.chay_mot_vong()
    assert _viec(mt, v).trang_thai == ob.UNKNOWN
    assert may.tab(101).du_lieu() == [HEADER, CU, ["dòng 1"]]           # máy chủ ĐÃ ghi
    ng.chay_mot_vong()
    assert len(_yc(mt, GHI)) == 1                                       # không gửi lại mù
    _doi_ten_va_tao_lai(may)
    ob.gui_lai_co_the_trung(mt["db"], v)                                # người dùng chấp nhận TRÙNG, không ĐỔI TAB
    ng.chay_mot_vong()
    assert may.tab(202).du_lieu() == [HEADER]
    assert may.tab(101).du_lieu() == [HEADER, CU, ["dòng 1"], ["dòng 1"]]
    assert _viec(mt, v).trang_thai == ob.SENT


# ---------------------------------------------------------------- biên nhận + giá trị

def test_bien_nhan_lay_ma_tab_tu_than_request_da_phat_khong_gia_vung_ghi(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    _ng(mt).chay_mot_vong()
    bn = json.loads(_viec(mt, v).bien_nhan)
    (ghi,) = _yc(mt, GHI)
    assert bn["worksheet_id"] == ghi["body"]["requests"][-1]["appendCells"]["sheetId"] == 101
    assert bn["spreadsheet_id"] == ID_A and bn["so_reply"] == 1 and bn["so_dong_gui"] == 1
    assert "updated_range" not in bn and "updated_rows" not in bn       # AppendCells không trả vùng ghi


def test_o_gui_giu_dung_kieu_nhu_values_append_RAW_va_khong_bao_gio_la_cong_thuc(mt):
    gia_tri = [["=1+1", "+84 912", "-5", "@x", "'abc", "0123", "", "chuỗi có dấu", 7, 2.5, 0, -3, 10 ** 12],
               ["=HYPERLINK(\"https://x.invalid\",\"x\")", "2026-10-08", "1,5", "50%", True, None, 1e-7]]
    may = mt["may"]
    may.them_tab(301, "RAW", so_cot=40)
    may.them_tab(302, "AC", so_cot=40)
    sh = gspread.service_account(filename="khong-dung").open_by_key(ID_A)
    sh.get_worksheet_by_id(301).append_rows(gia_tri, value_input_option="RAW")     # đường cũ (để đối chiếu kiểu)
    sh.batch_update(ob.dung_yeu_cau_ghi(302, gia_tri, 40))
    assert may.tab(302).hang_kieu() == may.tab(301).hang_kieu()
    assert all(o is None or o[0] != "f" for d in may.tab(302).hang_kieu() for o in d)


def test_tab_hep_hon_bao_cao_noi_cot_trong_cung_mot_batchUpdate_nguyen_tu(mt):
    mt["may"].them_tab(7, "Tab mới", so_cot=26)                         # tab mới tạo: 26 cột < 34 cột báo cáo
    d = _ho_so(mt, gid=7, tab="Tab mới")
    v = _xep(mt, d, 1)
    _ng(mt).chay_mot_vong()
    (ghi,) = _yc(mt, GHI)
    yc = ghi["body"]["requests"]
    assert [list(r) for r in yc] == [["appendDimension"], ["appendCells"]]
    assert yc[0]["appendDimension"] == {"sheetId": 7, "dimension": "COLUMNS", "length": 8}
    assert mt["may"].tab(7).du_lieu() == [HEADER, ["dòng 1"]]           # trang tính trống: tiêu đề + dòng, MỘT lần
    assert _viec(mt, v).trang_thai == ob.SENT


def test_o_so_khong_huu_han_bi_chan_truoc_khi_phat_request(mt):
    d = _ho_so(mt, gid=101)
    v = _xep(mt, d, 1, rows=[[float("nan")] + [""] * 33])
    _ng(mt).chay_mot_vong()
    assert _yc(mt, GHI) == []
    viec = _viec(mt, v)
    assert viec.trang_thai == ob.BLOCKED_REPORT and viec.gui_luc is None
