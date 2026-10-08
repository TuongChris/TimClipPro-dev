# -*- coding: utf-8 -*-
"""MR-R2-P2-01 (tái audit độc lập 78ba20c, 08/10/2026): việc KHÔNG RÕ do bản CŨ phát được «hợp thức hoá» bởi mã tab
mà một việc MỚI cùng revision chốt sau đó.

Bản f4d3cb7 chỉ chốt mã tab SAU ``SENT``: việc X ghi vào tab 101 (tìm theo TÊN) rồi mất phản hồi → UNKNOWN, revision
chưa có mã. Mã 78ba20c chỉ chặn gửi lại X khi revision CHƯA có mã chốt — nên khi việc mới Y (cùng hồ sơ/revision)
gửi vào tab 202 (tab mới mang tên «KetQuaQuet» sau khi 101 bị đổi tên) và chốt 202, X hết bị chặn, giao diện báo X
«đã ghim 202», «Gửi lại» ghi payload X vào 202.

Nay (lược đồ v4): mã tab của TỪNG LẦN PHÁT (``hang_doi_gui.gui_worksheet_id``) ghi trong CÙNG giao dịch SENDING. Việc
đã phát (``gui_luc``) mà không có mã của chính nó + hồ sơ theo tên = bản cũ phát theo tên → KHÔNG BAO GIỜ gửi lại; mã
chốt của revision (tạo trước hay sau) không xoá được tính không chắc chắn đó — đối soát tay / huỷ / gửi thêm có xác
nhận. Hồ sơ có mã: mã của hồ sơ (bản cũ cũng tìm tab theo mã đó). Dữ liệu tổng hợp; test chéo phiên bản chạy ĐÚNG mã
f4d3cb7 trong tiến trình con để tạo trạng thái cũ mà không sửa tay DB.
"""
import io
import json
import os
import sqlite3
import subprocess
import sys
import tarfile

import pytest

import lich_su
import outbox as ob
import sheet_destinations as sd
from outbox_gia import CongGia, CongNhieuTab, khoa_gia

ID_A = "1" + "a" * 43
IID = "c" * 32
HEADER = [f"Cột {i}" for i in range(1, 35)]
F4D3CB7 = "f4d3cb7a5e55dd3429d16c645e02dedb202e7c04"


class DongHo:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture()
def mt(tmp_path):
    (tmp_path / "data").mkdir()
    db = str(tmp_path / "data" / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    return {"db": db, "data": str(tmp_path / "data"), "tmp": tmp_path, "dong_ho": DongHo()}


def _link_cu(mt):
    return sd.nhap_link_cu(mt["db"], f"https://docs.google.com/spreadsheets/d/{ID_A}/edit#gid=0",
                           schema_id=sd.SCHEMA_NGANG, duong_dan_khoa=str(mt["tmp"] / "khoa.json"),
                           workspace="mac_dinh")


def _ho_so(mt, *, gid=None, tab="KetQuaQuet"):
    return sd.tao_dich(mt["db"], ten="Bảng thử", spreadsheet_id=ID_A, worksheet_id=gid, worksheet_ten=tab,
                       schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh", workspace="mac_dinh")


def _xep(mt, dich, job_id, nhan=None):
    y = sd.chot_y_dinh(mt["db"], dich.id, installation_id=IID, lo_id="lo")
    with sd.ket_noi(mt["db"], ghi=True) as con:
        return ob.them_viec(con, y, job_id=job_id, chinh_sach="v2", header=HEADER,
                            rows=[[nhan or f"dòng {job_id}"] + [""] * 33])


def _ng(mt, cong):
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=mt["dong_ho"])
    assert ng.nhan_quyen()
    return ng


def _viec(mt, vid):
    return ob.lay_viec(mt["db"], vid)


def _ma_chot(mt, dich):
    tc = sd.tab_da_chot(mt["db"], dich.id, dich.phien_ban)
    return None if tc is None else tc.worksheet_id


def _sql(mt, lenh, *tham):
    con = sqlite3.connect(mt["db"])
    con.execute(lenh, tham)
    con.commit()
    con.close()


def _viec_ban_cu_da_phat(mt, d, *, trang_thai=ob.UNKNOWN, job_id=1, thu_lai_sau=0.0):
    """Dòng do bản CŨ để lại: đã phát request (``gui_luc``), KHÔNG có mã tab của chính lần phát."""
    v = _xep(mt, d, job_id, nhan="OLD_PAYLOAD")
    _sql(mt, "UPDATE hang_doi_gui SET trang_thai=?, gui_luc=?, so_lan_thu=1, thu_lai_sau=? WHERE id=?",
         trang_thai, 999.0, thu_lai_sau, v)
    return v


# ---------------------------------------------------------------- kịch bản reviewer

def test_unknown_cu_va_viec_moi_cung_revision_viec_cu_van_bi_chan_vinh_vien(mt):
    d = _link_cu(mt)
    x = _viec_ban_cu_da_phat(mt, d)
    assert ob.ly_do_khong_gui_lai(mt["db"], _viec(mt, x)) == ob.LY_DO_BAN_CU_CHUA_CO_MA_TAB
    cong = CongNhieuTab({101: "ArchivedOriginal", 202: "KetQuaQuet"})   # 101 đã đổi tên, 202 mang tên cũ
    y = _xep(mt, d, 2, nhan="NEW_PAYLOAD")                              # việc MỚI, cùng hồ sơ + revision
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    assert _viec(mt, y).trang_thai == ob.SENT and _ma_chot(mt, d) == 202
    assert ob.ly_do_khong_gui_lai(mt["db"], _viec(mt, x)) == ob.LY_DO_BAN_CU_CHUA_CO_MA_TAB
    assert ob.tab_da_ghim(mt["db"], _viec(mt, x)) is None              # giao diện không được nói X ở 202
    with pytest.raises(ob.LoiHangDoi, match="mã tab"):
        ob.gui_lai_co_the_trung(mt["db"], x)
    ng.chay_mot_vong()
    assert [(g, r[0][0]) for g, r in cong.ghi] == [(202, "NEW_PAYLOAD")]
    assert _viec(mt, x).trang_thai == ob.UNKNOWN
    assert _viec(mt, y).gui_worksheet_id == 202 and _viec(mt, x).gui_worksheet_id is None
    ob.xac_nhan_da_gui(mt["db"], x, "đã thấy dòng trên tab cũ")         # đối soát tay vẫn làm được
    assert _viec(mt, x).trang_thai == ob.SENT


def test_viec_cu_dang_cho_khong_bao_gio_duoc_phat_theo_ma_chot_cua_viec_moi(mt):
    """Bản cũ: request bị từ chối sau dispatch (429) → chờ thử lại, ``gui_luc`` có, chưa mã. Việc mới chốt 202 trước."""
    d = _link_cu(mt)
    x = _viec_ban_cu_da_phat(mt, d, trang_thai=ob.RETRY_WAIT, thu_lai_sau=mt["dong_ho"].t + 600)
    cong = CongNhieuTab({101: "ArchivedOriginal", 202: "KetQuaQuet"})
    y = _xep(mt, d, 2, nhan="NEW_PAYLOAD")
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    assert _viec(mt, y).trang_thai == ob.SENT and _ma_chot(mt, d) == 202
    mt["dong_ho"].t += 3600
    ng.chay_mot_vong()
    assert cong.phat == [202] and _viec(mt, x).trang_thai == ob.BLOCKED_CONFIG
    assert "mã tab" in _viec(mt, x).loi


# ---------------------------------------------------------------- mã tab của TỪNG lần phát

def test_lan_phat_ghi_ma_tab_cua_chinh_viec_trong_cung_giao_dich_sending(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet"})
    luc = {}
    cong.sau_khi_chot = lambda gid: luc.update(viec=_viec(mt, v), chot=_ma_chot(mt, d))   # kết nối SQLite KHÁC
    _ng(mt, cong).chay_mot_vong()
    assert luc["viec"].trang_thai == ob.SENDING and luc["viec"].gui_worksheet_id == 101 and luc["chot"] == 101
    assert _viec(mt, v).gui_worksheet_id == 101


def test_mat_claim_truoc_sending_rollback_ca_ma_tab_cua_viec(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    cong = CongGia(gid=101)
    cong.ke_hoach = [("hook", lambda: _sql(mt, "UPDATE hang_doi_gui SET claim_token='nguoi-khac' WHERE id=?", v))]
    _ng(mt, cong).chay_mot_vong()
    viec = _viec(mt, v)
    assert cong.bang == [] and viec.gui_luc is None and viec.gui_worksheet_id is None and _ma_chot(mt, d) is None


def test_mat_ma_chot_cua_revision_viec_moi_van_gui_lai_theo_ma_cua_chinh_no(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet"})
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("mất phản hồi"))]
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    _sql(mt, "DELETE FROM dich_gui_tab_chot")                          # DB bị sửa/khôi phục lệch
    cong.doi_ten(101, "ArchivedOriginal")
    cong.them(202, "KetQuaQuet")
    ob.gui_lai_co_the_trung(mt["db"], v)
    ng.chay_mot_vong()
    assert cong.phat == [101, 101] and _viec(mt, v).trang_thai == ob.SENT


class CongTraMaKhac(CongNhieuTab):
    """Transport lỗi: tìm ra tab KHÁC mã đã định (``ma_tra``) khi phát lại."""

    def __init__(self, tabs, ma_tra):
        super().__init__(tabs)
        self.ma_tra = ma_tra

    def _tim(self, chot):
        return self.ma_tra if chot.worksheet_id is not None else super()._tim(chot)


def test_ma_tab_cua_lan_phat_truoc_la_bat_bien_ke_ca_khi_mat_ma_chot(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    cong = CongTraMaKhac({101: "KetQuaQuet", 999: "Lạ"}, ma_tra=999)
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("mất phản hồi"))]
    ng = _ng(mt, cong)
    ng.chay_mot_vong()                                                 # lần đầu theo tên → 101, UNKNOWN
    _sql(mt, "DELETE FROM dich_gui_tab_chot")
    ob.gui_lai_co_the_trung(mt["db"], v)
    ng.chay_mot_vong()                                                 # transport lỗi tìm ra 999
    viec = _viec(mt, v)
    assert cong.phat == [101] and viec.trang_thai == ob.BLOCKED_CONFIG
    assert viec.gui_worksheet_id == 101 and _ma_chot(mt, d) is None   # không ghi đè mã của lần phát, không chốt 999


def test_ma_tab_cua_viec_khac_ma_chot_cua_revision_thi_chan(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet", 202: "Khác"})
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("mất phản hồi"))]
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    _sql(mt, "UPDATE dich_gui_tab_chot SET worksheet_id=202")          # DB bị sửa lệch: việc nói 101, revision nói 202
    ly_do = ob.ly_do_khong_gui_lai(mt["db"], _viec(mt, v))
    assert "101" in ly_do and "202" in ly_do
    with pytest.raises(ob.LoiHangDoi):
        ob.gui_lai_co_the_trung(mt["db"], v)
    assert cong.phat == [101]


def test_viec_cu_cua_ho_so_co_ma_tab_van_gui_lai_duoc_vao_ma_ho_so(mt):
    """Đối chứng: bản cũ cũng tìm tab theo mã của hồ sơ — gửi lại vào đúng mã đó vẫn được (như 78ba20c)."""
    d = _ho_so(mt, gid=101)
    x = _viec_ban_cu_da_phat(mt, d)
    assert ob.ly_do_khong_gui_lai(mt["db"], _viec(mt, x)) == ""
    assert ob.tab_da_ghim(mt["db"], _viec(mt, x)).worksheet_id == 101
    cong = CongNhieuTab({101: "KetQuaQuet"})
    ob.gui_lai_co_the_trung(mt["db"], x)
    _ng(mt, cong).chay_mot_vong()
    assert cong.phat == [101] and _viec(mt, x).trang_thai == ob.SENT


def test_tab_da_ghim_la_ma_cua_chinh_lan_phat(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    assert ob.tab_da_ghim(mt["db"], _viec(mt, v)) is None             # theo tên, chưa phát: chưa biết
    cong = CongNhieuTab({101: "KetQuaQuet"})
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("mất phản hồi"))]
    _ng(mt, cong).chay_mot_vong()
    tc = ob.tab_da_ghim(mt["db"], _viec(mt, v))
    assert (tc.worksheet_id, tc.worksheet_ten) == (101, "KetQuaQuet")
    x = _viec_ban_cu_da_phat(mt, d, job_id=3)                          # cùng revision, đã có mã chốt 101
    assert ob.tab_da_ghim(mt["db"], _viec(mt, x)) is None
    assert ob.ly_do_khong_gui_lai(mt["db"], _viec(mt, x)) == ob.LY_DO_BAN_CU_CHUA_CO_MA_TAB
    w = _xep(mt, d, 4)                                                 # chưa phát: sẽ gửi theo mã chốt
    assert ob.tab_da_ghim(mt["db"], _viec(mt, w)).worksheet_id == 101


def test_gui_them_thu_cong_canh_bao_trung_khi_viec_cu_khong_ro_tab(mt):
    d = _link_cu(mt)
    _viec_ban_cu_da_phat(mt, d)                                        # job 1: đã phát theo tên, không rõ tab
    cong = CongNhieuTab({101: "ArchivedOriginal", 202: "KetQuaQuet"})
    _xep(mt, d, 2)
    _ng(mt, cong).chay_mot_vong()                                      # việc khác chốt revision = 202
    d101 = _ho_so(mt, gid=101, tab="ArchivedOriginal")
    y = sd.chot_y_dinh(mt["db"], d101.id, installation_id=IID, lo_id="lo")
    with pytest.raises(ob.LoiHangDoi, match="TRÙNG"):
        ob.tao_viec_thu_cong(mt["db"], y, 1, HEADER, [["x"] + [""] * 33], chinh_sach="v2")


# ---------------------------------------------------------------- giao diện đối soát

def test_ui_viec_cu_va_ma_chot_do_viec_moi_tao_khong_hien_tab_moi_va_khoa_gui_lai(tmp_path, monkeypatch):
    from test_ui_gui_sheets import _app, _nut

    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    db = eng.sqlite_file
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    d = sd.nhap_link_cu(db, f"https://docs.google.com/spreadsheets/d/{ID_A}/edit#gid=0",
                        schema_id=sd.SCHEMA_NGANG, duong_dan_khoa=str(tmp_path / "khoa.json"),
                        workspace="mac_dinh")
    y = sd.chot_y_dinh(db, d.id, installation_id=eng.installation_id(), lo_id="lo")
    with sd.ket_noi(db, ghi=True) as con:
        x = ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=HEADER, rows=[["x"] + [""] * 33])
        con.execute("UPDATE hang_doi_gui SET trang_thai=?, gui_luc=1.0 WHERE id=?", (ob.UNKNOWN, x))
        sd._chot_tab(con, d.id, d.phien_ban, worksheet_id=202, worksheet_ten="KetQuaQuet")   # do việc MỚI chốt
    at.run()
    chu = " ".join(str(e.value) for e in [*at.caption, *at.warning, *at.error, *at.info])
    assert "mã 202" not in chu and any("mã tab" in e.value for e in at.error)
    next(c for c in at.checkbox if c.key == f"gui_dong_y_trung_{x}").check().run()
    assert _nut(at, "⚠️ Gửi lại").disabled is True
    assert ob.lay_viec(db, x).trang_thai == ob.UNKNOWN


# ---------------------------------------------------------------- chéo phiên bản: ĐÚNG mã f4d3cb7 tạo trạng thái cũ

_KICH_BAN_CU = r'''
import json, os, sys
nguon, db, data, khoa = sys.argv[1:5]
sys.path.insert(0, nguon)
import lich_su, outbox as ob, sheet_destinations as sd
assert os.path.dirname(os.path.abspath(ob.__file__)) == os.path.abspath(nguon), ob.__file__
ID_A, IID = "1" + "a" * 43, "c" * 32
HEADER = [f"Cột {i}" for i in range(1, 35)]
lich_su.dam_bao_luoc_do(db)
sd.dinh_danh_may(db, mong_doi=IID)
sd.dang_ky_xac_thuc(db, "mac_dinh", khoa)
d = sd.nhap_link_cu(db, f"https://docs.google.com/spreadsheets/d/{ID_A}/edit#gid=0", schema_id=sd.SCHEMA_NGANG,
                    duong_dan_khoa=khoa, workspace="mac_dinh")
y = sd.chot_y_dinh(db, d.id, installation_id=IID, lo_id="lo")
with sd.ket_noi(db, ghi=True) as con:
    vid = ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=HEADER, rows=[["OLD_PAYLOAD"] + [""] * 33])
phat = []
class Cong:
    def gui(self, chot, duong_dan_khoa, header, rows, truoc_khi_gui):
        truoc_khi_gui(101, "KetQuaQuet")                      # bản cũ: tìm theo TÊN → 101, COMMIT SENDING
        phat.append(101)
        raise ob.KhongRo("ReadTimeout sau khi gửi (giả)")     # Google đã ghi vào 101, phản hồi mất
ng = ob.NguoiGui(db, data, Cong())
assert ng.nhan_quyen()
ng.chay_mot_vong()
ng.tha_quyen()
v = ob.lay_viec(db, vid)
print(json.dumps({"vid": vid, "dich_id": d.id, "trang_thai": v.trang_thai, "gui_luc": v.gui_luc, "phat": phat,
                  "co_ma_chot": sd.tab_da_chot(db, d.id, d.phien_ban) is not None,
                  "phien_ban_ma": lich_su.PHIEN_BAN}))
'''


def _nguon_f4d3cb7(tmp_path):
    """``TimClipPro`` của ĐÚNG f4d3cb7: ``TIMCLIP_NGUON_F4D3CB7`` (thư mục đã giải nén, vd. từ gói audit f4d3cb7) hoặc
    ``git archive`` từ ``TIMCLIP_REPO_GOC``/repo chứa file test này; không có → bỏ qua."""
    p = os.environ.get("TIMCLIP_NGUON_F4D3CB7")
    if p:
        p = os.path.join(p, "TimClipPro") if os.path.isfile(os.path.join(p, "TimClipPro", "outbox.py")) else p
        assert os.path.isfile(os.path.join(p, "outbox.py")), "TIMCLIP_NGUON_F4D3CB7 không chứa outbox.py"
        return p
    goc = os.environ.get("TIMCLIP_REPO_GOC") or os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    try:
        tar = subprocess.run(["git", "-C", goc, "archive", "--format=tar", F4D3CB7, "TimClipPro"],
                             capture_output=True, check=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("không có mã f4d3cb7 (đặt TIMCLIP_NGUON_F4D3CB7 hoặc chạy trong repo git)")
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(tmp_path / "f4d3cb7", filter="data")
    return str(tmp_path / "f4d3cb7" / "TimClipPro")


def test_cheo_phien_ban_unknown_cua_f4d3cb7_khong_bi_hop_thuc_hoa_sau_nang_cap(tmp_path):
    nguon = _nguon_f4d3cb7(tmp_path)
    (tmp_path / "state" / "data").mkdir(parents=True)
    db, data = str(tmp_path / "state" / "data" / "lichsu.db"), str(tmp_path / "state" / "data")
    khoa = khoa_gia(tmp_path / "state")
    kich_ban = tmp_path / "giai_doan_cu.py"
    kich_ban.write_text(_KICH_BAN_CU, encoding="utf-8")
    r = subprocess.run([sys.executable, str(kich_ban), nguon, db, data, khoa], capture_output=True, text=True,
                       encoding="utf-8", timeout=180, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr[-3000:]
    cu = json.loads(r.stdout.strip().splitlines()[-1])
    assert cu["phien_ban_ma"] == 3 and cu["trang_thai"] == ob.UNKNOWN and cu["phat"] == [101]
    assert cu["gui_luc"] is not None and cu["co_ma_chot"] is False
    # Mở bằng mã MỚI — chỉ qua API, không sửa tay DB (nâng lược đồ nếu mã mới cần).
    kq = lich_su.dam_bao_luoc_do(db)
    x = cu["vid"]
    assert ob.ly_do_khong_gui_lai(db, ob.lay_viec(db, x)) == ob.LY_DO_BAN_CU_CHUA_CO_MA_TAB
    y_dinh = sd.chot_y_dinh(db, cu["dich_id"], installation_id=IID, lo_id="lo")
    with sd.ket_noi(db, ghi=True) as con:
        y = ob.them_viec(con, y_dinh, job_id=2, chinh_sach="v2", header=HEADER,
                         rows=[["NEW_PAYLOAD"] + [""] * 33])
    cong = CongNhieuTab({101: "ArchivedOriginal", 202: "KetQuaQuet"})
    ng = ob.NguoiGui(db, data, cong, dong_ho=DongHo())
    assert ng.nhan_quyen()
    ng.chay_mot_vong()
    assert ob.lay_viec(db, y).trang_thai == ob.SENT
    vx = ob.lay_viec(db, x)
    assert ob.ly_do_khong_gui_lai(db, vx) == ob.LY_DO_BAN_CU_CHUA_CO_MA_TAB and ob.tab_da_ghim(db, vx) is None
    with pytest.raises(ob.LoiHangDoi):
        ob.gui_lai_co_the_trung(db, x)
    ng.chay_mot_vong()
    assert [(g, r_[0][0]) for g, r_ in cong.ghi] == [(202, "NEW_PAYLOAD")]
    assert kq["da_nang_cap"] is True and kq["phien_ban_cu"] == 3 and kq["phien_ban"] == lich_su.PHIEN_BAN == 4
    assert kq["sao_luu"] and os.path.isfile(kq["sao_luu"])            # outbox có dữ liệu → sao lưu trước khi ALTER
    assert ob.lay_viec(db, x).gui_worksheet_id is None and ob.lay_viec(db, y).gui_worksheet_id == 202
