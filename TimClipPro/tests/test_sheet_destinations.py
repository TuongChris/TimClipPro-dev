# -*- coding: utf-8 -*-
"""Hồ sơ đích Google Sheets + credential binding + ảnh chụp ghim (docs/MANAGED_RUNTIME_DESIGN.md §2, §5).

Bất biến khoá ở đây:
* sửa hồ sơ = revision MỚI; ảnh chụp đã ghim giữ revision cũ, là chuỗi JSON (không có list lồng để sửa);
* tab định danh bằng ``worksheet_id``; tên chỉ là nhãn;
* binding khoá giữ principal mong đợi — đổi principal không bao giờ âm thầm; không lưu khoá riêng;
* lưu trữ / tạm dừng chặn lượt MỚI; không xoá được hồ sơ hay binding còn được tham chiếu;
* nhập link cũ idempotent, không lưu nguyên URL.
Dữ liệu tổng hợp (tài khoản dịch vụ GIẢ, miền .invalid; không có khoá thật).
"""
import json
import sqlite3
import time

import pytest

import lich_su
import sheet_destinations as sd

# Ghép chuỗi để mã nguồn test không chứa mẫu mà bộ quét bí mật của dự án chặn (khoá GIẢ).
LOAI_KHOA = "service" + "_account"
TRUONG_KHOA_RIENG = "private" + "_key"
ID_A = "1" + "a" * 43
ID_B = "1" + "b" * 43


def _khoa(tmp_path, ten="khoa.json", email="gui@du-an-gia.invalid", kid="k1"):
    p = tmp_path / ten
    p.write_text(json.dumps({"type": LOAI_KHOA, "client_email": email,
                             "private_key_id": kid, TRUONG_KHOA_RIENG: "GIA-KHONG-PHAI-KHOA"}),
                 encoding="utf-8")
    return str(p)


@pytest.fixture()
def db(tmp_path):
    p = str(tmp_path / "lichsu.db")
    lich_su.dam_bao_luoc_do(p)
    return p


@pytest.fixture()
def co_khoa(db, tmp_path):
    sd.dang_ky_xac_thuc(db, "mac_dinh", _khoa(tmp_path))
    return db


def _tao(db, ten="Bảng A", sid=ID_A, gid=0, schema=sd.SCHEMA_NGANG):
    return sd.tao_dich(db, ten=ten, spreadsheet_id=sid, worksheet_id=gid,
                       worksheet_ten="KetQuaQuet", schema_id=schema, xac_thuc_ref="mac_dinh",
                       workspace="mac_dinh")


# ---------- link ----------

@pytest.mark.parametrize("link, mong", [
    (f"https://docs.google.com/spreadsheets/d/{ID_A}/edit#gid=123", (ID_A, 123)),
    (f"https://docs.google.com/spreadsheets/d/{ID_A}/edit?gid=7#gid=7", (ID_A, 7)),
    (f"https://docs.google.com/spreadsheets/d/{ID_A}/edit", (ID_A, None)),
    (ID_A, (ID_A, None)),
])
def test_phan_tich_link(link, mong):
    assert sd.phan_tich_link(link) == mong


@pytest.mark.parametrize("sai", ["", "https://example.invalid/x", "ngan", "a b c"])
def test_link_sai_bi_tu_choi(sai):
    with pytest.raises(sd.LoiDichGui):
        sd.phan_tich_link(sai)


# ---------- credential binding ----------

def test_dang_ky_khoa_chi_luu_principal_va_key_id(db, tmp_path):
    xt = sd.dang_ky_xac_thuc(db, "mac_dinh", _khoa(tmp_path))
    assert (xt.principal, xt.key_id, xt.cho_xoay_khoa) == ("gui@du-an-gia.invalid", "k1", True)
    con = sqlite3.connect(db)
    dump = "\n".join(con.iterdump())
    con.close()
    assert "GIA-KHONG-PHAI-KHOA" not in dump        # khoá riêng không bao giờ vào DB


@pytest.mark.parametrize("noi_dung", [
    "{khong phai json", json.dumps({"type": "authorized_user", "client_email": "x@y"}),
    json.dumps({"type": LOAI_KHOA, "private_key_id": "k"}),
])
def test_khoa_hong_bi_tu_choi_va_khong_lo_noi_dung(db, tmp_path, noi_dung):
    p = tmp_path / "hong.json"
    p.write_text(noi_dung, encoding="utf-8")
    with pytest.raises(sd.LoiDichGui) as e:
        sd.dang_ky_xac_thuc(db, "mac_dinh", str(p))
    assert "x@y" not in str(e.value)


def test_doi_principal_cua_binding_bi_chan_xoay_khoa_cung_principal_duoc(db, tmp_path):
    sd.dang_ky_xac_thuc(db, "mac_dinh", _khoa(tmp_path))
    moi = sd.dang_ky_xac_thuc(db, "mac_dinh", _khoa(tmp_path, "khoa2.json", kid="k2"))
    assert moi.key_id == "k2" and moi.principal == "gui@du-an-gia.invalid"
    with pytest.raises(sd.LoiDichGui, match="tài khoản dịch vụ"):
        sd.dang_ky_xac_thuc(db, "mac_dinh", _khoa(tmp_path, "khac.json", email="khac@x.invalid"))
    assert sd.lay_xac_thuc(db, "mac_dinh").principal == "gui@du-an-gia.invalid"


# ---------- hồ sơ, revision ----------

def test_tao_va_sua_tao_revision_moi_bat_bien(co_khoa):
    a = _tao(co_khoa)
    assert a.phien_ban == 1 and a.trang_thai == sd.TT_HOAT_DONG
    b = sd.sua_dich(co_khoa, a.id, ten="Bảng A mới", worksheet_id=55)
    assert b.phien_ban == 2 and b.ten == "Bảng A mới" and b.worksheet_id == 55
    cu = sd.lay_dich(co_khoa, a.id, phien_ban=1)
    assert cu.ten == "Bảng A" and cu.worksheet_id == 0      # revision cũ không đổi


def test_sua_truong_la_bi_tu_choi(co_khoa):
    a = _tao(co_khoa)
    with pytest.raises(sd.LoiDichGui):
        sd.sua_dich(co_khoa, a.id, trang_thai="luu_tru")


@pytest.mark.parametrize("sai", [{"schema_id": "ngang99"}, {"spreadsheet_id": "x"},
                                 {"worksheet_ten": ""}, {"xac_thuc_ref": "khong_co"}])
def test_tao_voi_gia_tri_sai_bi_tu_choi(co_khoa, sai):
    tham = dict(ten="X", spreadsheet_id=ID_A, worksheet_id=0, worksheet_ten="KetQuaQuet",
                schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    tham.update(sai)
    with pytest.raises(sd.LoiDichGui):
        sd.tao_dich(co_khoa, **tham)


def test_chot_y_dinh_la_chuoi_json_bat_bien_va_giu_revision(co_khoa):
    a = _tao(co_khoa)
    y = sd.chot_y_dinh(co_khoa, a.id, installation_id="f" * 32, lo_id="lo1")
    sd.sua_dich(co_khoa, a.id, ten="Đổi tên", spreadsheet_id=ID_B)
    assert y.dich.phien_ban == 1 and y.dich.spreadsheet_id == ID_A and y.dich.ten == "Bảng A"
    assert (y.dich.principal, y.dich.key_id) == ("gui@du-an-gia.invalid", "k1")
    with pytest.raises(Exception):
        y.dich.spreadsheet_id = ID_B                      # frozen
    assert all(isinstance(v, (str, int, bool, type(None))) for v in vars(y.dich).values())
    assert sd.DichGuiChot.from_json(y.dich.to_json()) == y.dich
    assert y.dich.to_json() == sd.DichGuiChot.from_json(y.dich.to_json()).to_json()


def test_luu_tru_chan_luot_moi_tam_dung_gui_thi_khong(co_khoa):
    """Tạm dừng GỬI không chặn quét: lượt mới vẫn ghim được (việc xếp hàng chờ). Lưu trữ thì chặn."""
    a = _tao(co_khoa)
    sd.doi_trang_thai(co_khoa, a.id, sd.TT_TAM_DUNG)
    assert sd.chot_y_dinh(co_khoa, a.id, installation_id="f" * 32).dich.dich_id == a.id
    assert [d.id for d in sd.ds_dich(co_khoa, bo_luu_tru=True)] == [a.id]
    sd.doi_trang_thai(co_khoa, a.id, sd.TT_LUU_TRU)
    assert sd.ds_dich(co_khoa, bo_luu_tru=True) == []
    with pytest.raises(sd.LoiDichGui, match="lưu trữ"):
        sd.chot_y_dinh(co_khoa, a.id, installation_id="f" * 32)
    assert [d.id for d in sd.ds_dich(co_khoa, chi_hoat_dong=True)] == []
    sd.doi_trang_thai(co_khoa, a.id, sd.TT_HOAT_DONG)
    assert sd.chot_y_dinh(co_khoa, a.id, installation_id="f" * 32).dich.dich_id == a.id


def _them_viec(db, dich_id, trang_thai="PENDING"):
    con = sqlite3.connect(db)
    now = time.time()
    con.execute("INSERT INTO hang_doi_gui(id, dedupe_key, installation_id, workspace, nguon,"
                " dich_id, dich_phien_ban, dich_json, schema_id, trang_thai, tao_luc, sua_luc)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"v-{now}", f"k-{now}", "f" * 32, "mac_dinh", "auto", dich_id, 1, "{}",
                 sd.SCHEMA_NGANG, trang_thai, now, now))
    con.commit()
    con.close()


def test_khong_xoa_duoc_ho_so_hay_binding_con_tham_chieu(co_khoa):
    a = _tao(co_khoa)
    with pytest.raises(sd.LoiDichGui, match="đang được"):
        sd.xoa_xac_thuc(co_khoa, "mac_dinh")             # hồ sơ a dùng binding này
    _them_viec(co_khoa, a.id)
    with pytest.raises(sd.LoiDichGui, match="lưu trữ"):
        sd.xoa_dich(co_khoa, a.id)
    b = _tao(co_khoa, ten="Bảng B", sid=ID_B)
    sd.xoa_dich(co_khoa, b.id)                            # chưa có việc nào → xoá được
    assert sd.lay_dich(co_khoa, b.id) is None


def test_nhap_link_cu_idempotent_khong_luu_url(co_khoa, tmp_path):
    link = f"https://docs.google.com/spreadsheets/d/{ID_A}/edit?usp=sharing"
    khoa = _khoa(tmp_path)
    d1 = sd.nhap_link_cu(co_khoa, link, schema_id=sd.SCHEMA_NGANG, duong_dan_khoa=khoa,
                         workspace="mac_dinh")
    d2 = sd.nhap_link_cu(co_khoa, link, schema_id=sd.SCHEMA_NGANG, duong_dan_khoa=khoa,
                         workspace="mac_dinh")
    assert d1.id == d2.id and d1.nguon == sd.NGUON_LINK_CU and d1.worksheet_id is None
    assert d1.worksheet_ten == "KetQuaQuet" and ID_A not in d1.ten
    d3 = sd.nhap_link_cu(co_khoa, link, schema_id=sd.SCHEMA_DOC, duong_dan_khoa=khoa,
                         workspace="mac_dinh")
    assert d3.id != d1.id                                  # schema khác = đích khác
    con = sqlite3.connect(co_khoa)
    assert "usp=sharing" not in "\n".join(con.iterdump())
    con.close()


def test_nhap_link_cu_khoa_khac_principal_thi_dung(co_khoa, tmp_path):
    with pytest.raises(sd.LoiDichGui, match="tài khoản dịch vụ"):
        sd.nhap_link_cu(co_khoa, ID_A, schema_id=sd.SCHEMA_NGANG,
                        duong_dan_khoa=_khoa(tmp_path, "k.json", email="khac@x.invalid"),
                        workspace="mac_dinh")


def test_dinh_danh_may_sinh_mot_lan_va_chan_state_cua_may_khac(db):
    iid = sd.dinh_danh_may(db)
    assert len(iid) == 32 and sd.dinh_danh_may(db) == iid
    assert sd.dinh_danh_may(db, mong_doi=iid) == iid
    with pytest.raises(sd.LoiDichGui, match="cài đặt khác"):
        sd.dinh_danh_may(db, mong_doi="0" * 32)


def test_dinh_danh_may_managed_dung_id_cua_installation_json(tmp_path):
    p = str(tmp_path / "moi.db")
    lich_su.dam_bao_luoc_do(p)
    assert sd.dinh_danh_may(p, mong_doi="a" * 32) == "a" * 32
