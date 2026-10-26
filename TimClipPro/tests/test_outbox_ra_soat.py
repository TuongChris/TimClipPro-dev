# -*- coding: utf-8 -*-
"""Các lỗi do lượt rà soát độc lập M2 (07/10/2026) tìm ra — mỗi test tái hiện ĐÚNG kịch bản đã nêu.

* P1-A: link cũ mang ``#gid=`` từng gửi vào tab của gid (thường là tab đầu "Sheet1") thay vì «KetQuaQuet»
  như bản cũ; sau lần gửi đầu hồ sơ bị đổi nhãn → mỗi lượt Watch tạo một hồ sơ MỚI.
* P3-2: chốt mã tab đọc hồ sơ HIỆN TẠI theo nhãn → một lô bị tách sang hai tab khi tab đổi tên/tạo lại.
* Tên tab "để đối chiếu" của hồ sơ có mã tab chưa bao giờ được đối chiếu.
* P2-B/P2-C: bảng chưa chia sẻ (PermissionError của gspread) bị coi là lỗi mạng tạm; RefreshError bỏ qua
  cờ ``retryable``.
* P2-D: hồ sơ tạm dừng / nhóm đang chờ thử lại chiếm hết suất mỗi vòng → hồ sơ khác không bao giờ gửi.
* P2-E: dừng người gửi giữa lúc request đang bay → việc thành KHÔNG RÕ dù không có sự cố.
* P2-H: gửi thêm thủ công chỉ cảnh báo trùng theo HỒ SƠ, không theo bảng + tab thật.
* P3-1: chốt chặn xoá binding còn việc tham chiếu là mã chết (``suppress(ValueError)`` nuốt lỗi).
* P3-9: khởi động người gửi nền đồng thời tạo nhiều luồng.
* P3-10: phân loại "chưa gửi" lần theo ``__context__`` — không phải bằng chứng.
"""
import inspect
import sqlite3
import threading
import time

import google.auth.exceptions as gae
import pytest
import requests
import urllib3.exceptions as u3

import lich_su
import outbox as ob
import sheet_destinations as sd
from outbox_gia import CongGia, CongNhieuTab, khoa_gia

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
def mt(tmp_path):
    db = str(tmp_path / "data" / "lichsu.db")
    (tmp_path / "data").mkdir()
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    khoa = khoa_gia(tmp_path)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa)
    return {"db": db, "data": str(tmp_path / "data"), "tmp": tmp_path, "khoa": khoa}


def _ho_so(mt, *, ten="Bảng", sid=ID_A, gid=None, tab="KetQuaQuet"):
    return sd.tao_dich(mt["db"], ten=ten, spreadsheet_id=sid, worksheet_id=gid, worksheet_ten=tab,
                       schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh", workspace="mac_dinh")


def _xep(mt, dich, job_id, nguon=ob.NGUON_AUTO, rieng=""):
    y = sd.chot_y_dinh(mt["db"], dich.id, installation_id=IID, lo_id="lo")
    with sd.ket_noi(mt["db"], ghi=True) as con:
        return ob.them_viec(con, y, job_id=job_id, chinh_sach="v2", header=HEADER,
                            rows=[[f"dòng {job_id}"] + [""] * 33], nguon=nguon, khoa_rieng=rieng)


def _ng(mt, cong, *, moi_vong=20, dong_ho=None):
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, moi_vong=moi_vong, dong_ho=dong_ho or DongHo())
    assert ng.nhan_quyen()
    return ng


def _tt(mt, vid):
    return ob.lay_viec(mt["db"], vid).trang_thai


# ---------------------------------------------------------------- P1-A: link cũ

def test_link_cu_co_gid_van_gui_tab_ketquaquet_nhu_ban_cu(mt):
    link = f"https://docs.google.com/spreadsheets/d/{ID_A}/edit#gid=0"
    d = sd.nhap_link_cu(mt["db"], link, schema_id=sd.SCHEMA_NGANG, duong_dan_khoa=mt["khoa"],
                        workspace="mac_dinh")
    assert d.worksheet_id is None and d.worksheet_ten == sd.TAB_MAC_DINH   # gid của link bị BỎ QUA
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({0: "Sheet1", 555: "KetQuaQuet"})
    _ng(mt, cong).chay_mot_vong()
    assert [g for g, _ in cong.ghi] == [555] and _tt(mt, v) == ob.SENT


def test_nhap_link_cu_lan_sau_khong_tao_ho_so_moi_du_tab_doi_ten(mt):
    link = f"https://docs.google.com/spreadsheets/d/{ID_A}/edit#gid=0"
    d = sd.nhap_link_cu(mt["db"], link, schema_id=sd.SCHEMA_NGANG, duong_dan_khoa=mt["khoa"],
                        workspace="mac_dinh")
    _xep(mt, d, 1)
    cong = CongNhieuTab({0: "Sheet1", 555: "KetQuaQuet"})
    _ng(mt, cong).chay_mot_vong()
    cong.doi_ten(555, "KetQuaQuet (đổi tên)")
    for _ in range(3):                                          # ba lượt Watch kế tiếp
        d2 = sd.nhap_link_cu(mt["db"], link, schema_id=sd.SCHEMA_NGANG, duong_dan_khoa=mt["khoa"],
                             workspace="mac_dinh")
        assert d2.id == d.id
    assert len(sd.ds_dich(mt["db"])) == 1


# ---------------------------------------------------------------- P3-2 + đối chiếu tên tab

def test_ghim_theo_ten_chot_ma_tab_lan_dau_tab_tao_lai_khong_tach_lo(mt):
    d = _ho_so(mt, gid=None)
    ids = [_xep(mt, d, j) for j in (1, 2, 3)]
    cong = CongNhieuTab({111: "KetQuaQuet"})
    ng = _ng(mt, cong, moi_vong=1)
    ng.chay_mot_vong()                                          # lần gửi đầu: chốt mã 111
    cong.doi_ten(111, "Cũ")
    cong.them(222, "KetQuaQuet")                                # tab cùng tên được tạo lại
    ng.chay_mot_vong()
    ng.chay_mot_vong()
    assert [g for g, _ in cong.ghi] == [111, 111, 111]
    assert all(_tt(mt, v) == ob.SENT for v in ids)


def test_ma_tab_co_ten_doi_chieu_khac_thi_chan_khong_ghi(mt):
    d = _ho_so(mt, gid=0, tab="KetQuaQuet")                     # người dùng dán link tab đầu
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({0: "Sheet1", 555: "KetQuaQuet"})
    _ng(mt, cong).chay_mot_vong()
    viec = ob.lay_viec(mt["db"], v)
    assert viec.trang_thai == ob.BLOCKED_CONFIG and cong.ghi == []
    assert "Sheet1" in viec.loi and "KetQuaQuet" in viec.loi


def test_da_chot_ma_tab_doi_ten_tab_van_gui_dung_ma(mt):
    d = _ho_so(mt, gid=555, tab="KetQuaQuet")
    _xep(mt, d, 1)
    cong = CongNhieuTab({0: "Sheet1", 555: "KetQuaQuet"})
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    cong.doi_ten(555, "KQ đổi tên")
    v2 = _xep(mt, d, 2)
    ng.chay_mot_vong()
    assert [g for g, _ in cong.ghi] == [555, 555] and _tt(mt, v2) == ob.SENT


def test_sua_ho_so_giu_ma_tab_da_chot(mt):
    d = _ho_so(mt, gid=None)
    _xep(mt, d, 1)
    cong = CongNhieuTab({111: "KetQuaQuet"})
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    sd.sua_dich(mt["db"], d.id, ten="Đổi tên hồ sơ")            # revision mới, cùng bảng + tab
    cong.doi_ten(111, "Cũ")
    cong.them(222, "KetQuaQuet")
    v2 = _xep(mt, d, 2)
    ng.chay_mot_vong()
    assert [g for g, _ in cong.ghi] == [111, 111] and _tt(mt, v2) == ob.SENT


def test_bien_nhan_khac_ma_tab_da_gui_la_khong_ro():
    chot = sd.DichGuiChot(dich_id="d", phien_ban=1, workspace="w", installation_id=IID, ten="B",
                          spreadsheet_id=ID_A, worksheet_id=5, worksheet_ten="KetQuaQuet",
                          schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh", principal="p@x",
                          key_id="k", cho_xoay_khoa=True)
    from outbox_gia import ket_qua
    kq = ket_qua(chot, 6, "KetQuaQuet", [["x"]])                  # request ghi theo mã 6, mã đã ghim 5
    assert ob.kiem_bien_nhan(kq, chot)[0] is False


# ---------------------------------------------------------------- P2-B / P2-C / P3-10

def test_bang_chua_chia_se_permission_error_la_loi_cau_hinh():
    loi = ob.phan_loai_loi(PermissionError(), da_phat=False)    # gspread.open_by_key gặp HTTP 403
    assert isinstance(loi, ob.ChuaGui) and loi.tam_thoi is False and "chia sẻ" in loi.ly_do


@pytest.mark.parametrize("retryable, tam_thoi", [(True, True), (False, False)])
def test_refresh_error_theo_co_retryable(retryable, tam_thoi):
    loi = ob.phan_loai_loi(gae.RefreshError("x", retryable=retryable), da_phat=False)
    assert isinstance(loi, ob.ChuaGui) and loi.tam_thoi is tam_thoi


def test_chua_gui_khong_suy_tu_context_ngam():
    """Sau dispatch: lỗi đọc có __context__ là lỗi kết nối CŨ → vẫn mơ hồ (không phải bằng chứng)."""
    try:
        try:
            raise u3.NewConnectionError(None, "kết nối cũ")
        except u3.NewConnectionError:
            raise requests.exceptions.ReadTimeout("đọc quá hạn")
    except requests.exceptions.ReadTimeout as e:
        loi = e
    assert isinstance(ob.phan_loai_loi(loi, da_phat=True), ob.KhongRo)


# ---------------------------------------------------------------- P2-D: không nghẽn

def test_ho_so_tam_dung_nhieu_viec_khong_lam_nghen_ho_so_khac(mt):
    a, b = _ho_so(mt, ten="A", sid=ID_A, gid=0), _ho_so(mt, ten="B", sid=ID_B, gid=0)
    for j in range(100, 125):
        _xep(mt, a, j)
    vb = _xep(mt, b, 200)
    sd.doi_trang_thai(mt["db"], a.id, sd.TT_TAM_DUNG)
    _ng(mt, CongGia()).chay_mot_vong()
    assert _tt(mt, vb) == ob.SENT


def test_nhom_dang_cho_thu_lai_khong_lam_nghen_nhom_khac(mt):
    a, b = _ho_so(mt, ten="A", sid=ID_A, gid=0), _ho_so(mt, ten="B", sid=ID_B, gid=0)
    for j in range(300, 325):
        _xep(mt, a, j)
    vb = _xep(mt, b, 400)
    cong = CongGia()
    cong.ke_hoach = [("truoc", ob.ChuaGui("mạng chập chờn", tam_thoi=True))]
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    ng.chay_mot_vong()
    assert _tt(mt, vb) == ob.SENT
    # Hoãn của nhóm A lưu bền: người gửi MỚI (khởi động lại) cũng không dồn vào bảng A ngay.
    ng.tha_quyen()
    cong2 = CongGia()
    _ng(mt, cong2).chay_mot_vong()
    assert cong2.lan_goi == 0


def test_ho_so_tam_dung_van_nhan_luot_moi_viec_xep_hang_cho(mt):
    a = _ho_so(mt, gid=0)
    sd.doi_trang_thai(mt["db"], a.id, sd.TT_TAM_DUNG)
    v = _xep(mt, a, 1)                                          # tạm dừng GỬI, không chặn quét
    _ng(mt, CongGia()).chay_mot_vong()
    assert _tt(mt, v) == ob.PENDING
    sd.doi_trang_thai(mt["db"], a.id, sd.TT_LUU_TRU)
    with pytest.raises(sd.LoiDichGui):
        sd.chot_y_dinh(mt["db"], a.id, installation_id=IID)     # lưu trữ thì không dùng cho lượt mới


# ---------------------------------------------------------------- P2-E / P3-9: luồng nền

def test_dung_nguoi_gui_nen_cho_het_thoi_han_transport():
    assert ob.NguoiGuiNen.HAN_DUNG_S >= sum(ob.CongGspread.THOI_GIAN_CHO) + 10
    assert inspect.signature(ob.NguoiGuiNen.stop).parameters["cho_s"].default is None


def test_dung_nguoi_gui_nen_khong_bo_do_viec_dang_bay(mt):
    a = _ho_so(mt, gid=0)
    v = _xep(mt, a, 1)
    dang_bay, cho_phep = threading.Event(), threading.Event()

    class CongCham(CongGia):
        def gui(self, chot, khoa, header, rows, truoc_khi_gui):
            def truoc(gid, ten):
                truoc_khi_gui(gid, ten)
                dang_bay.set()
                cho_phep.wait(10)
            return super().gui(chot, khoa, header, rows, truoc)

    nen = ob.NguoiGuiNen(mt["db"], mt["data"], CongCham, chu_ky_s=0.05, chu_ky_gianh_s=0.05)
    nen.start()
    assert dang_bay.wait(10)
    ket = {}
    t = threading.Thread(target=lambda: ket.setdefault("tt", (nen.stop(), _tt(mt, v))[1]))
    t.start()
    time.sleep(0.3)
    assert t.is_alive()                                          # stop() đang chờ việc đang bay
    cho_phep.set()
    t.join(15)
    assert ket["tt"] == ob.SENT


def test_cho_gui_xong_han_0_khong_khoi_dong_nguoi_gui(mt, monkeypatch):
    goi = []
    monkeypatch.setattr(ob.NguoiGuiNen, "start", lambda self: goi.append(1))
    ob.cho_gui_xong(mt["db"], mt["data"], "lo", han_s=0, tao_cong=CongGia)
    assert goi == []


class _NenKhongGui:
    """Người gửi giữ quyền nhưng không bao giờ gửi: việc PENDING cứ chờ mãi."""
    co_quyen = True
    dang_chay = True
    so_luot_bat_dau = so_luot_xong = 0

    def danh_thuc(self):
        pass


def test_cho_gui_xong_dung_som_khi_duoc_yeu_cau(mt):
    a = _ho_so(mt, gid=0)
    _xep(mt, a, 1)
    bat_dau = time.monotonic()
    ob.cho_gui_xong(mt["db"], mt["data"], "lo", han_s=30, nen=_NenKhongGui(), dung=lambda: True)
    assert time.monotonic() - bat_dau < 5


def test_cho_gui_xong_khong_cho_viec_dang_tam_dung_nhung_cho_viec_dang_bay(mt):
    """Audit B-5: việc chỉ chờ vì tạm dừng (toàn bộ / hồ sơ) thì thôi chờ ngay; việc đang bay vẫn
    được chờ tới kết cục dù vừa bật tạm dừng."""
    a = _ho_so(mt, gid=0)
    v = _xep(mt, a, 1)
    assert ob.ly_do_tam_dung(mt["db"], "lo") == ""
    ob.dat_tam_dung(mt["db"], True)
    assert ob.ly_do_tam_dung(mt["db"], "lo") == "toan_bo"
    bat_dau = time.monotonic()
    tt = ob.cho_gui_xong(mt["db"], mt["data"], "lo", han_s=30, nen=_NenKhongGui())
    assert time.monotonic() - bat_dau < 5 and tt[ob.PENDING] == 1
    ob.dat_tam_dung(mt["db"], False)
    sd.doi_trang_thai(mt["db"], a.id, sd.TT_TAM_DUNG)
    assert ob.ly_do_tam_dung(mt["db"], "lo") == "ho_so"
    with sd.ket_noi(mt["db"], ghi=True) as con:                  # việc đang bay: không phải «tạm dừng»
        con.execute("UPDATE hang_doi_gui SET trang_thai=? WHERE id=?", (ob.SENDING, v))
    assert ob.ly_do_tam_dung(mt["db"], "lo") == ""
    assert ob.ly_do_tam_dung(mt["db"], "lo-khac") == ""          # lượt không có việc chờ


def test_khoi_dong_nen_dong_thoi_chi_mot_luong(mt, monkeypatch):
    class DictCham(dict):
        def get(self, *a, **k):
            time.sleep(0.05)                                     # nới rộng khe kiểm-rồi-tạo
            return super().get(*a, **k)

    monkeypatch.setattr(ob, "_NEN", DictCham())
    cung_luc = threading.Barrier(6)
    nen = []

    def chay():
        cung_luc.wait()
        nen.append(ob.dam_bao_chay_nen(mt["db"], mt["data"], CongGia))

    ts = [threading.Thread(target=chay) for _ in range(6)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(10)
    try:
        assert len({id(x) for x in nen}) == 1
        assert sum(1 for t in threading.enumerate() if t.name == "outbox-sender" and t.is_alive()) == 1
    finally:
        for x in {id(x): x for x in nen}.values():
            x.stop(cho_s=5)


# ---------------------------------------------------------------- P2-H / P3-1

def test_gui_thu_cong_canh_bao_trung_khi_cung_bang_cung_tab_khac_ho_so(mt):
    a = _ho_so(mt, ten="Link cũ", gid=None)
    b = _ho_so(mt, ten="Tạo tay", gid=None)                     # cùng bảng + cùng tab KetQuaQuet
    _xep(mt, a, 7)
    y = sd.chot_y_dinh(mt["db"], b.id, installation_id=IID)
    with pytest.raises(ob.LoiHangDoi):
        ob.tao_viec_thu_cong(mt["db"], y, 7, HEADER, [["x"] + [""] * 33], chinh_sach="v2")
    assert ob.tao_viec_thu_cong(mt["db"], y, 7, HEADER, [["x"] + [""] * 33], chinh_sach="v2",
                                cho_phep_trung=True)


def test_xoa_binding_con_viec_gui_chua_xong_tham_chieu_bi_chan(mt):
    sd.dang_ky_xac_thuc(mt["db"], "phu", mt["khoa"])
    a = _ho_so(mt, gid=0)
    _xep(mt, a, 1)
    con = sqlite3.connect(mt["db"])                              # việc gửi trỏ binding «phu»
    con.execute("UPDATE hang_doi_gui SET dich_json=replace(dich_json, '\"mac_dinh\"', '\"phu\"')")
    con.commit()
    con.close()
    with pytest.raises(sd.LoiDichGui):
        sd.xoa_xac_thuc(mt["db"], "phu")
    assert sd.lay_xac_thuc(mt["db"], "phu") is not None


def test_thoat_tien_trinh_dung_moi_nguoi_gui_nen(mt):
    """App thoát êm (Ctrl+C): hook thoát dừng mọi người gửi nền — chờ việc đang bay, nhả quyền."""
    nen = ob.dam_bao_chay_nen(mt["db"], mt["data"], CongGia)
    assert nen.dang_chay
    ob._dung_tat_ca_khi_thoat()
    assert not nen.dang_chay and ob._NEN.get(ob._khoa_db(mt["db"])) is None


def test_chot_cua_chu_cu_khong_ghi_de_ket_qua_cua_chu_moi(mt):
    """Fencing: người gửi cũ (token cũ) chốt muộn sau khi việc đã được claim lại → không ghi gì."""
    a = _ho_so(mt, gid=0)
    v = _xep(mt, a, 1)
    ng = _ng(mt, CongGia())
    t1 = ng._claim(v, 1_000_000.0)
    con = sqlite3.connect(mt["db"])                     # mô phỏng: chủ mới phục hồi + claim lại
    con.execute("UPDATE hang_doi_gui SET trang_thai=?, claim_token='' WHERE id=?", (ob.PENDING, v))
    con.commit()
    con.close()
    t2 = ng._claim(v, 1_000_000.0)
    assert t1 and t2 and t1 != t2
    assert ng._chot(v, t1, ob.SENT, bien_nhan="{}") is False
    viec = ob.lay_viec(mt["db"], v)
    assert viec.trang_thai == ob.CLAIMED
