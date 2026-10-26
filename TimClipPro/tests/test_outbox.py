# -*- coding: utf-8 -*-
"""Outbox gửi Google Sheets lưu bền (docs/MANAGED_RUNTIME_DESIGN.md §5).

Khoá các bất biến:
* việc gửi xếp hàng trong giao dịch của người gọi; ý định trùng không tạo dòng thứ hai;
* SENDING được COMMIT trước khi request đi; mơ hồ sau dispatch → UNKNOWN_DELIVERY, không bao giờ gửi
  lại mù; khởi động lại: SENDING của chủ cũ → UNKNOWN, CLAIMED → PENDING;
* SENT chỉ khi biên nhận khớp (spreadsheetId + replies của batchUpdate nguyên tử, mã tab + dòng trong thân
  request đã phát);
* lỗi cấu hình/khoá → BLOCKED_CONFIG (0 request), lỗi tạm → RETRY_WAIT có hạn mức;
* đích lấy từ ảnh chụp đã ghim, không từ hồ sơ hiện tại; tạm dừng không đổi đích;
* một hồ sơ lỗi không chặn hồ sơ khác.
Transport giả (``outbox_gia.CongGia``), khoá dịch vụ GIẢ.
"""
import dataclasses
import json
import sqlite3

import pytest

import lich_su
import outbox as ob
import sheet_destinations as sd
from outbox_gia import CongGia, khoa_gia, phan_hoi_dung

ID_A = "1" + "a" * 43
ID_B = "1" + "b" * 43
IID = "c" * 32
HEADER = [f"Cột {i}" for i in range(1, 35)]


class DongHo:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture()
def moi_truong(tmp_path):
    db = str(tmp_path / "data" / "lichsu.db")
    (tmp_path / "data").mkdir()
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    a = sd.tao_dich(db, ten="Bảng A", spreadsheet_id=ID_A, worksheet_id=0,
                    worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    b = sd.tao_dich(db, ten="Bảng B", spreadsheet_id=ID_B, worksheet_id=7,
                    worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    return {"db": db, "data": str(tmp_path / "data"), "a": a, "b": b, "tmp": tmp_path}


def _xep(mt, dich, job_id, rows=None, **kw):
    y = sd.chot_y_dinh(mt["db"], dich.id, installation_id=IID, lo_id="lo1")
    with sd.ket_noi(mt["db"], ghi=True) as con:
        return ob.them_viec(con, y, job_id=job_id, chinh_sach="v2", header=HEADER,
                            rows=rows if rows is not None else [[f"dòng {job_id}"] + [""] * 33],
                            **kw)


def _nguoi_gui(mt, cong, dong_ho=None):
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=dong_ho or DongHo())
    assert ng.nhan_quyen()
    return ng


def _tt(mt, viec_id):
    return ob.lay_viec(mt["db"], viec_id).trang_thai


# ---------- xếp hàng ----------

def test_xep_hang_nguyen_tu_va_y_dinh_trung_khong_tao_dong_moi(moi_truong):
    v1 = _xep(moi_truong, moi_truong["a"], 1)
    v2 = _xep(moi_truong, moi_truong["a"], 1)
    assert v1 and v2 is None
    assert [v.id for v in ob.ds_viec(moi_truong["db"])] == [v1]
    v = ob.lay_viec(moi_truong["db"], v1)
    assert v.trang_thai == ob.PENDING and v.job_id == 1 and v.so_dong == 1
    assert v.dich.spreadsheet_id == ID_A and v.dich.phien_ban == 1


def test_xep_hang_trong_giao_dich_loi_thi_khong_con_gi(moi_truong):
    y = sd.chot_y_dinh(moi_truong["db"], moi_truong["a"].id, installation_id=IID)
    with pytest.raises(RuntimeError):
        with sd.ket_noi(moi_truong["db"], ghi=True) as con:
            ob.them_viec(con, y, job_id=5, chinh_sach="v2", header=HEADER, rows=[["x"]])
            raise RuntimeError("lỗi giữa giao dịch")
    assert ob.ds_viec(moi_truong["db"]) == []


def test_payload_la_ban_chot_khong_doi_theo_list_cua_nguoi_goi(moi_truong):
    rows = [["gốc"] + [""] * 33]
    vid = _xep(moi_truong, moi_truong["a"], 2, rows=rows)
    rows[0][0] = "ĐÃ SỬA SAU KHI XẾP HÀNG"
    assert ob.lay_viec(moi_truong["db"], vid).rows[0][0] == "gốc"


def test_dich_lay_tu_anh_chup_khong_tu_ho_so_hien_tai(moi_truong):
    vid = _xep(moi_truong, moi_truong["a"], 3)
    sd.sua_dich(moi_truong["db"], moi_truong["a"].id, spreadsheet_id=ID_B, worksheet_id=9)
    cong = CongGia()
    _nguoi_gui(moi_truong, cong).chay_mot_vong()
    assert _tt(moi_truong, vid) == ob.SENT
    assert [(s, g) for s, g, _ in cong.bang] == [(ID_A, 0)]


# ---------- gửi ----------

def test_gui_thanh_cong_luu_bien_nhan(moi_truong):
    vid = _xep(moi_truong, moi_truong["a"], 4)
    cong = CongGia()
    kq = _nguoi_gui(moi_truong, cong).chay_mot_vong()
    v = ob.lay_viec(moi_truong["db"], vid)
    assert kq["da_gui"] == 1 and v.trang_thai == ob.SENT
    bn = json.loads(v.bien_nhan)
    assert bn["kieu"] == "batchUpdate.appendCells" and bn["so_reply"] == 1 and bn["so_dong_gui"] == 1
    assert bn["spreadsheet_id"] == ID_A and bn["worksheet_id"] == 0
    assert "updated_rows" not in bn and "updated_range" not in bn       # AppendCells không trả: không dựng giả
    assert cong.bang == [(ID_A, 0, v.rows)]


def test_mo_ho_sau_khi_gui_thanh_unknown_va_khong_gui_lai(moi_truong):
    import requests
    vid = _xep(moi_truong, moi_truong["a"], 5)
    cong = CongGia()
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("ReadTimeout sau khi gửi"))]
    ng = _nguoi_gui(moi_truong, cong)
    ng.chay_mot_vong()
    assert _tt(moi_truong, vid) == ob.UNKNOWN
    for _ in range(3):
        ng.chay_mot_vong()
    assert len(cong.bang) == 1 and cong.lan_goi == 1           # KHÔNG gửi lại mù
    assert requests  # (import để chắc môi trường test có requests như production)


def test_loi_tam_truoc_dispatch_thu_lai_co_han_muc(moi_truong):
    vid = _xep(moi_truong, moi_truong["a"], 6)
    dh = DongHo()
    cong = CongGia()
    cong.ke_hoach = [("truoc", ob.ChuaGui("mất mạng", tam_thoi=True))] * 20
    ng = _nguoi_gui(moi_truong, cong, dh)
    ng.chay_mot_vong()
    v = ob.lay_viec(moi_truong["db"], vid)
    assert v.trang_thai == ob.RETRY_WAIT and v.thu_lai_sau > dh.t
    ng.chay_mot_vong()                                          # chưa tới hạn: không gọi
    assert cong.lan_goi == 1
    for _ in range(ob.SO_LAN_THU_TOI_DA + 2):
        dh.t += 10_000
        ng.chay_mot_vong()
    v = ob.lay_viec(moi_truong["db"], vid)
    assert v.trang_thai == ob.BLOCKED_CONFIG and "số lần thử" in v.loi
    assert cong.lan_goi == ob.SO_LAN_THU_TOI_DA and cong.bang == []


def test_loi_tam_roi_het_loi_thi_gui_duoc(moi_truong):
    vid = _xep(moi_truong, moi_truong["a"], 7)
    dh = DongHo()
    cong = CongGia()
    cong.ke_hoach = [("truoc", ob.ChuaGui("429", tam_thoi=True))]
    ng = _nguoi_gui(moi_truong, cong, dh)
    ng.chay_mot_vong()
    dh.t += 10_000
    ng.chay_mot_vong()
    assert _tt(moi_truong, vid) == ob.SENT and len(cong.bang) == 1


def test_loi_cau_hinh_chan_ca_nhom_cung_dich_khong_chan_dich_khac(moi_truong):
    a1 = _xep(moi_truong, moi_truong["a"], 8)
    a2 = _xep(moi_truong, moi_truong["a"], 9)
    b1 = _xep(moi_truong, moi_truong["b"], 10)
    cong = CongGia()
    cong.ke_hoach = [("truoc", ob.ChuaGui("Hàng tiêu đề sai", tam_thoi=False))]
    _nguoi_gui(moi_truong, cong).chay_mot_vong()
    assert _tt(moi_truong, a1) == ob.BLOCKED_CONFIG and _tt(moi_truong, a2) == ob.BLOCKED_CONFIG
    assert _tt(moi_truong, b1) == ob.SENT
    assert cong.lan_goi == 2 and [s for s, _, _ in cong.bang] == [ID_B]
    ob.thu_lai(moi_truong["db"], a1)                            # người dùng sửa bảng rồi bấm
    assert _tt(moi_truong, a1) == ob.PENDING


@pytest.mark.parametrize("phan_hoi", [
    "khong-phai-dict",
    {"spreadsheetId": ID_B, "replies": [{}]},                     # bảng khác
    {"spreadsheetId": ID_A, "replies": [{}, {}]},                 # số reply khác số request đã gửi
    {"spreadsheetId": ID_A, "replies": []},
    {"spreadsheetId": ID_A},                                      # thiếu replies
    {"spreadsheetId": ID_A, "replies": None},
    # Dạng phản hồi values.append của transport CŨ (ghi theo TÊN): không còn là biên nhận hợp lệ.
    {"spreadsheetId": ID_A, "updates": {"updatedRange": "'KetQuaQuet'!A2:AH2", "updatedRows": 1}},
])
def test_bien_nhan_bat_thuong_la_unknown(moi_truong, phan_hoi):
    vid = _xep(moi_truong, moi_truong["a"], 11)
    cong = CongGia()
    cong.ke_hoach = [("phan_hoi", phan_hoi)]
    ng = _nguoi_gui(moi_truong, cong)
    ng.chay_mot_vong()
    ng.chay_mot_vong()
    assert _tt(moi_truong, vid) == ob.UNKNOWN and cong.lan_goi == 1


def test_bien_nhan_khong_phu_thuoc_ten_tab_co_dau_nhay(moi_truong):
    # Hồ sơ đối chiếu ĐÚNG tên tab thật (tên có dấu nháy) — tên khác thì lần gửi đầu bị chặn. Biên nhận định danh
    # tab bằng MÃ trong thân request, tên chỉ là nhãn.
    d = sd.tao_dich(moi_truong["db"], ten="Bảng nháy", spreadsheet_id=ID_A, worksheet_id=0,
                    worksheet_ten="Kết quả 'mới'", schema_id=sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    vid = _xep(moi_truong, d, 12)
    _nguoi_gui(moi_truong, CongGia(ten_tab="Kết quả 'mới'")).chay_mot_vong()
    bn = json.loads(ob.lay_viec(moi_truong["db"], vid).bien_nhan)
    assert _tt(moi_truong, vid) == ob.SENT and (bn["worksheet_id"], bn["worksheet_ten"]) == (0, "Kết quả 'mới'")


@pytest.mark.parametrize("hong", ["sheetId_khac", "them_request", "dong_khac", "thieu_dong", "fields_khac"])
def test_bien_nhan_doc_tu_than_request_da_phat(moi_truong, hong):
    """Mã tab/dòng của biên nhận lấy từ THÂN REQUEST đã phát: request lệch mã đã chốt, có request ngoài hợp đồng,
    hay mang dòng khác payload → không bao giờ SENT."""
    y = sd.chot_y_dinh(moi_truong["db"], moi_truong["a"].id, installation_id=IID)
    chot = dataclasses.replace(y.dich, worksheet_id=0)
    rows = [["x"] + [""] * 33]
    yc = ob.dung_yeu_cau_ghi(0, rows)
    assert ob.kiem_bien_nhan(ob.KetQuaGui(phan_hoi_dung(chot, yc), yc, "KetQuaQuet"), chot, rows=rows)[0]
    if hong == "sheetId_khac":
        yc = ob.dung_yeu_cau_ghi(7, rows)
    elif hong == "them_request":
        yc = {"requests": [{"deleteDimension": {"range": {"sheetId": 0, "dimension": "ROWS"}}},
                           *yc["requests"]]}
    elif hong == "dong_khac":
        yc = ob.dung_yeu_cau_ghi(0, [["y"] + [""] * 33])
    elif hong == "thieu_dong":
        yc = ob.dung_yeu_cau_ghi(0, [])
    else:
        yc["requests"][-1]["appendCells"]["fields"] = "*"
    kq = ob.KetQuaGui(phan_hoi_dung(chot, yc), yc, "KetQuaQuet")
    assert ob.kiem_bien_nhan(kq, chot, rows=rows)[0] is False


# ---------- phục hồi sau crash / fencing ----------

def _ep_trang_thai(mt, vid, trang_thai, chu="tien-trinh-cu"):
    con = sqlite3.connect(mt["db"])
    con.execute("UPDATE hang_doi_gui SET trang_thai=?, chu_so_huu=?, claim_token='cu' WHERE id=?",
                (trang_thai, chu, vid))
    con.commit()
    con.close()


def test_khoi_dong_lai_sending_thanh_unknown_claimed_ve_pending(moi_truong):
    v_gui = _xep(moi_truong, moi_truong["a"], 13)
    v_claim = _xep(moi_truong, moi_truong["a"], 14)
    _ep_trang_thai(moi_truong, v_gui, ob.SENDING)
    _ep_trang_thai(moi_truong, v_claim, ob.CLAIMED)
    cong = CongGia()
    ng = _nguoi_gui(moi_truong, cong)          # nhận quyền → phục hồi
    assert _tt(moi_truong, v_gui) == ob.UNKNOWN
    assert "khởi động lại" in ob.lay_viec(moi_truong["db"], v_gui).loi
    ng.chay_mot_vong()
    assert _tt(moi_truong, v_claim) == ob.SENT and _tt(moi_truong, v_gui) == ob.UNKNOWN
    assert len(cong.bang) == 1


def test_mat_claim_truoc_dispatch_thi_khong_gui(moi_truong):
    """Claim bị lấy mất (fencing token đổi) ngay trước dispatch → hủy lần gửi, KHÔNG ghi."""
    vid = _xep(moi_truong, moi_truong["a"], 15)
    cong = CongGia()

    def cuop():
        con = sqlite3.connect(moi_truong["db"])
        con.execute("UPDATE hang_doi_gui SET claim_token='nguoi-khac' WHERE id=?", (vid,))
        con.commit()
        con.close()

    cong.ke_hoach = [("hook", cuop)]
    _nguoi_gui(moi_truong, cong).chay_mot_vong()
    assert cong.bang == [] and _tt(moi_truong, vid) == ob.CLAIMED


def test_chi_mot_nguoi_gui_giu_quyen(moi_truong):
    ng1 = ob.NguoiGui(moi_truong["db"], moi_truong["data"], CongGia())
    ng2 = ob.NguoiGui(moi_truong["db"], moi_truong["data"], CongGia())
    assert ng1.nhan_quyen() is True and ng2.nhan_quyen() is False
    with pytest.raises(RuntimeError):
        ng2.chay_mot_vong()                      # không có quyền thì không được gửi
    ng1.tha_quyen()
    assert ng2.nhan_quyen() is True
    ng2.tha_quyen()


# ---------- khoá / đích hỏng ----------

def test_khoa_doi_tai_khoan_dich_vu_bi_chan_khong_request(moi_truong):
    vid = _xep(moi_truong, moi_truong["a"], 16)
    khoa_gia(moi_truong["tmp"], email="ke-khac@x.invalid")       # ghi đè file khoá cùng đường dẫn
    cong = CongGia()
    _nguoi_gui(moi_truong, cong).chay_mot_vong()
    v = ob.lay_viec(moi_truong["db"], vid)
    assert v.trang_thai == ob.BLOCKED_CONFIG and "tài khoản dịch vụ" in v.loi
    assert cong.lan_goi == 0


@pytest.mark.parametrize("cho_xoay, mong", [(True, ob.SENT), (False, ob.BLOCKED_CONFIG)])
def test_xoay_khoa_cung_principal_theo_chinh_sach(moi_truong, cho_xoay, mong):
    if not cho_xoay:
        con = sqlite3.connect(moi_truong["db"])
        con.execute("UPDATE xac_thuc_gui SET cho_xoay_khoa=0")
        con.commit()
        con.close()
    vid = _xep(moi_truong, moi_truong["a"], 17)
    khoa_gia(moi_truong["tmp"], kid="k2")
    _nguoi_gui(moi_truong, CongGia()).chay_mot_vong()
    assert _tt(moi_truong, vid) == mong


def test_dich_ghim_hong_va_payload_bi_sua_bi_chan(moi_truong):
    v1 = _xep(moi_truong, moi_truong["a"], 18)
    v2 = _xep(moi_truong, moi_truong["a"], 19)
    con = sqlite3.connect(moi_truong["db"])
    con.execute("UPDATE hang_doi_gui SET dich_json='{hỏng' WHERE id=?", (v1,))
    con.execute("UPDATE hang_doi_gui SET rows_json='[[\"bị sửa\"]]' WHERE id=?", (v2,))
    con.commit()
    con.close()
    cong = CongGia()
    _nguoi_gui(moi_truong, cong).chay_mot_vong()
    assert _tt(moi_truong, v1) == ob.BLOCKED_CONFIG
    assert _tt(moi_truong, v2) == ob.BLOCKED_REPORT
    assert cong.lan_goi == 0


# ---------- tạm dừng ----------

def test_tam_dung_toan_bo_va_tam_dung_ho_so(moi_truong):
    va = _xep(moi_truong, moi_truong["a"], 20)
    vb = _xep(moi_truong, moi_truong["b"], 21)
    cong = CongGia()
    ng = _nguoi_gui(moi_truong, cong)
    ob.dat_tam_dung(moi_truong["db"], True)
    ng.chay_mot_vong()
    assert cong.lan_goi == 0 and _tt(moi_truong, va) == ob.PENDING
    ob.dat_tam_dung(moi_truong["db"], False)
    sd.doi_trang_thai(moi_truong["db"], moi_truong["a"].id, sd.TT_TAM_DUNG)
    ng.chay_mot_vong()
    assert _tt(moi_truong, va) == ob.PENDING and _tt(moi_truong, vb) == ob.SENT
    assert ob.lay_viec(moi_truong["db"], va).dich.spreadsheet_id == ID_A   # không đổi đích
    sd.doi_trang_thai(moi_truong["db"], moi_truong["a"].id, sd.TT_LUU_TRU)
    ng.chay_mot_vong()                     # lưu trữ KHÔNG phá ý định gửi đã ghim
    assert _tt(moi_truong, va) == ob.SENT


def test_tam_dung_toan_bo_giua_vong_khong_claim_them_viec(moi_truong):
    # Audit F-15: vòng gửi đã chọn 5 ứng viên; chủ máy bật «Tạm dừng toàn bộ» (UI chỉ ghi cờ DB) đúng lúc việc
    # ĐẦU đang bay. Việc đã claim được đi nốt; 4 việc chưa claim phải ở nguyên PENDING — không ghi thêm lên Sheets.
    viec = [_xep(moi_truong, moi_truong["a"], 100 + i) for i in range(5)]
    cong = CongGia()
    cong.ke_hoach = [("hook", lambda: ob.dat_tam_dung(moi_truong["db"], True))]
    dem = _nguoi_gui(moi_truong, cong).chay_mot_vong()
    assert len(cong.bang) == 1 and _tt(moi_truong, viec[0]) == ob.SENT
    assert [_tt(moi_truong, v) for v in viec[1:]] == [ob.PENDING] * 4
    assert dem["da_gui"] == 1 and dem["tam_dung"] == 1


def test_tam_dung_ho_so_giua_vong_khong_claim_them_viec_cua_ho_so_do(moi_truong):
    # Audit F-15 (hồ sơ): tạm dừng hồ sơ A giữa vòng → việc chưa claim của A ở nguyên PENDING; hồ sơ B vẫn gửi.
    va = [_xep(moi_truong, moi_truong["a"], 110 + i) for i in range(3)]
    vb = _xep(moi_truong, moi_truong["b"], 120)
    cong = CongGia()
    cong.ke_hoach = [("hook", lambda: sd.doi_trang_thai(moi_truong["db"], moi_truong["a"].id, sd.TT_TAM_DUNG))]
    _nguoi_gui(moi_truong, cong).chay_mot_vong()
    assert _tt(moi_truong, va[0]) == ob.SENT
    assert [_tt(moi_truong, v) for v in va[1:]] == [ob.PENDING] * 2
    assert _tt(moi_truong, vb) == ob.SENT and len(cong.bang) == 2


# ---------- thao tác người dùng ----------

def test_unknown_xac_nhan_da_gui_hoac_gui_lai_co_the_trung(moi_truong):
    v1 = _xep(moi_truong, moi_truong["a"], 22)
    v2 = _xep(moi_truong, moi_truong["a"], 23)
    cong = CongGia()
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("mất phản hồi")),
                     ("sau_chua_ghi", ob.KhongRo("mất phản hồi"))]
    ng = _nguoi_gui(moi_truong, cong)
    ng.chay_mot_vong()
    assert _tt(moi_truong, v1) == ob.UNKNOWN and _tt(moi_truong, v2) == ob.UNKNOWN
    ob.xac_nhan_da_gui(moi_truong["db"], v1, ghi_chu="đã thấy dòng trên Sheet")
    assert _tt(moi_truong, v1) == ob.SENT
    assert json.loads(ob.lay_viec(moi_truong["db"], v1).bien_nhan)["xac_nhan_tay"] is True
    ob.gui_lai_co_the_trung(moi_truong["db"], v2)
    ng.chay_mot_vong()
    assert _tt(moi_truong, v2) == ob.SENT and len(cong.bang) == 2


@pytest.mark.parametrize("tu", [ob.SENDING, ob.SENT])
def test_khong_huy_viec_dang_gui_hoac_da_gui(moi_truong, tu):
    vid = _xep(moi_truong, moi_truong["a"], 24)
    _ep_trang_thai(moi_truong, vid, tu)
    with pytest.raises(ob.LoiHangDoi):
        ob.huy(moi_truong["db"], vid)


def test_huy_viec_claimed_thi_nguoi_gui_dang_cam_khong_phat(moi_truong):
    """CLAIMED = chưa phát request (thiết kế §5: CANCELLED = chưa SENDING) → huỷ được (audit B-1: việc kẹt CLAIMED
    phải huỷ được). Huỷ ngay trước dispatch: fencing CLAIMED→SENDING chặn người gửi đang cầm việc — không ghi gì."""
    vid = _xep(moi_truong, moi_truong["a"], 24)
    cong = CongGia()
    cong.ke_hoach = [("hook", lambda: ob.huy(moi_truong["db"], vid))]
    _nguoi_gui(moi_truong, cong).chay_mot_vong()
    assert cong.bang == [] and _tt(moi_truong, vid) == ob.CANCELLED
    assert ob.lay_viec(moi_truong["db"], vid).gui_luc is None


def test_huy_va_thu_lai_chi_tu_trang_thai_hop_le(moi_truong):
    vid = _xep(moi_truong, moi_truong["a"], 25)
    ob.huy(moi_truong["db"], vid)
    assert _tt(moi_truong, vid) == ob.CANCELLED
    with pytest.raises(ob.LoiHangDoi):
        ob.thu_lai(moi_truong["db"], vid)
    cong = CongGia()
    _nguoi_gui(moi_truong, cong).chay_mot_vong()
    assert cong.lan_goi == 0


def test_tom_tat_dem_theo_trang_thai(moi_truong):
    _xep(moi_truong, moi_truong["a"], 26)
    _xep(moi_truong, moi_truong["b"], 27, trang_thai=ob.BLOCKED_REPORT, loi="báo cáo V2 lỗi")
    tt = ob.tom_tat(moi_truong["db"])
    assert tt[ob.PENDING] == 1 and tt[ob.BLOCKED_REPORT] == 1


def test_phan_hoi_dung_cua_do_gia_khop_api_that(moi_truong):
    """Mẫu phản hồi giả đúng cấu trúc BatchUpdateSpreadsheetResponse: ``replies`` 1:1 với request."""
    y = sd.chot_y_dinh(moi_truong["db"], moi_truong["a"].id, installation_id=IID)
    yc = ob.dung_yeu_cau_ghi(0, [["a"], ["b"]], so_cot_hien_co=0)
    assert phan_hoi_dung(y.dich, yc) == {"spreadsheetId": ID_A, "replies": [{}, {}]}


# ---------- tiện ích cho giao diện ----------

def test_kiem_khoa_cuc_bo_truoc_khi_bat_dau_lo(moi_truong):
    y = sd.chot_y_dinh(moi_truong["db"], moi_truong["a"].id, installation_id=IID)
    assert ob.kiem_khoa_cuc_bo(moi_truong["db"], y.dich) == ""
    khoa_gia(moi_truong["tmp"], email="ke-khac@x.invalid")
    assert "tài khoản dịch vụ" in ob.kiem_khoa_cuc_bo(moi_truong["db"], y.dich)


def test_gui_thu_cong_trung_phai_xac_nhan(moi_truong):
    y = sd.chot_y_dinh(moi_truong["db"], moi_truong["a"].id, installation_id=IID)
    rows = [["x"] + [""] * 33]
    v1 = ob.tao_viec_thu_cong(moi_truong["db"], y, 77, HEADER, rows, chinh_sach="v2")
    with pytest.raises(ob.LoiHangDoi, match="đã có việc gửi"):
        ob.tao_viec_thu_cong(moi_truong["db"], y, 77, HEADER, rows, chinh_sach="v2")
    v2 = ob.tao_viec_thu_cong(moi_truong["db"], y, 77, HEADER, rows, chinh_sach="v2",
                              cho_phep_trung=True)
    assert v1 != v2 and {v.nguon for v in ob.ds_viec(moi_truong["db"], job_id=77)} == {
        ob.NGUON_THU_CONG}
    ob.huy(moi_truong["db"], v1)
    ob.huy(moi_truong["db"], v2)
    assert ob.tao_viec_thu_cong(moi_truong["db"], y, 77, HEADER, rows, chinh_sach="v2")
