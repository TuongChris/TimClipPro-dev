# -*- coding: utf-8 -*-
"""MR-P1-02 (audit độc lập f4d3cb7, 08/10/2026): mã tab đích được ghim QUÁ MUỘN.

Mã cũ: ``truoc_khi_gui(gid, tên)`` chỉ COMMIT ``SENDING``; mã tab của revision chỉ được chốt SAU ``SENT`` và lỗi
chốt bị ``contextlib.suppress``. Hồ sơ theo TÊN (gồm đường nhập link cũ) thì lần gửi kế tìm lại tab theo tên:
* Biến thể A — gửi vào gid 101 rồi mất phản hồi (UNKNOWN, chưa có mã); tab 101 đổi tên, tab mới 202 mang tên cũ;
  người dùng duyệt «Gửi lại (có thể trùng)» sau khởi động lại → payload cũ vào 202 rồi SENT.
* Biến thể B — SENT vào 101 nhưng ghi mã lỗi (bị nuốt) → việc kế cùng revision vào 202.

Nay: mã tab CHỐT cho revision (lần đầu thắng) trong CÙNG giao dịch CLAIMED→SENDING, có fencing ``claim_token``;
chốt lỗi / mã đã chốt khác mã vừa tìm / mất claim → rollback, KHÔNG phát request. Mọi lần gửi sau (thử lại, gửi
lại sau UNKNOWN, khởi động lại, việc khác cùng revision) đi theo MÃ đã chốt; tab bị xoá → chặn đúng lỗi, không
bao giờ nhận tab mới cùng tên. Mọi assert kiểm gid của TỪNG request (``CongNhieuTab.phat``/``ghi``).
"""
import json
import sqlite3

import pytest

import lich_su
import outbox as ob
import sheet_destinations as sd
from outbox_gia import CongGia, CongNhieuTab, khoa_gia, phan_hoi_dung

ID_A = "1" + "a" * 43
IID = "c" * 32
HEADER = [f"Cột {i}" for i in range(1, 35)]


class MatDien(BaseException):
    """Tiến trình chết tại chỗ (không bị ``except Exception`` bắt)."""


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
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    return {"db": db, "data": str(tmp_path / "data"), "tmp": tmp_path, "dong_ho": DongHo()}


def _ho_so(mt, *, gid=None, tab="KetQuaQuet"):
    return sd.tao_dich(mt["db"], ten="Bảng thử", spreadsheet_id=ID_A, worksheet_id=gid, worksheet_ten=tab,
                       schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh", workspace="mac_dinh")


def _link_cu(mt):
    """Đường nhập link cũ của audit: bỏ ``#gid``, hồ sơ theo TÊN «KetQuaQuet»."""
    return sd.nhap_link_cu(mt["db"], f"https://docs.google.com/spreadsheets/d/{ID_A}/edit#gid=0",
                           schema_id=sd.SCHEMA_NGANG, duong_dan_khoa=str(mt["tmp"] / "khoa.json"),
                           workspace="mac_dinh")


def _xep(mt, dich, job_id):
    y = sd.chot_y_dinh(mt["db"], dich.id, installation_id=IID, lo_id="lo")
    with sd.ket_noi(mt["db"], ghi=True) as con:
        return ob.them_viec(con, y, job_id=job_id, chinh_sach="v2", header=HEADER,
                            rows=[[f"dòng {job_id}"] + [""] * 33])


def _ng(mt, cong):
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=mt["dong_ho"])
    assert ng.nhan_quyen()
    return ng


def _viec(mt, vid):
    return ob.lay_viec(mt["db"], vid)


def _ma_chot(mt, dich):
    tc = sd.tab_da_chot(mt["db"], dich.id, dich.phien_ban)
    return None if tc is None else tc.worksheet_id


def _doi_ten_va_tao_lai(cong):
    cong.doi_ten(101, "ArchivedOriginal")
    cong.them(202, "KetQuaQuet")                 # tab MỚI mang đúng tên cũ


# ---------------------------------------------------------------- biến thể A (đúng kịch bản audit)

@pytest.mark.parametrize("tao_ho_so", [_link_cu, lambda mt: _ho_so(mt, gid=None)], ids=["link_cu", "theo_ten"])
def test_A_unknown_doi_ten_tao_lai_khoi_dong_lai_gui_lai_van_dung_tab_cu(mt, tao_ho_so):
    d = tao_ho_so(mt)
    assert d.worksheet_id is None
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet"})
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("ReadTimeout sau khi gửi"))]
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    assert _viec(mt, v).trang_thai == ob.UNKNOWN
    assert _ma_chot(mt, d) == 101                        # ghim TRƯỚC request, không chờ SENT
    ng.tha_quyen()                                       # tắt app
    _doi_ten_va_tao_lai(cong)
    ob.gui_lai_co_the_trung(mt["db"], v)                 # người dùng chấp nhận TRÙNG, không chấp nhận ĐỔI TAB
    _ng(mt, cong).chay_mot_vong()                        # khởi động lại → người gửi mới
    assert cong.phat == [101, 101] and [g for g, _ in cong.ghi] == [101, 101]
    viec = _viec(mt, v)
    assert viec.trang_thai == ob.SENT and json.loads(viec.bien_nhan)["worksheet_id"] == 101


def test_A_tab_cu_bi_xoa_thi_chan_khong_nhan_tab_moi_cung_ten(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet"})
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("mất phản hồi"))]
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    ng.tha_quyen()
    cong.xoa(101)
    cong.them(202, "KetQuaQuet")
    ob.gui_lai_co_the_trung(mt["db"], v)
    _ng(mt, cong).chay_mot_vong()
    assert cong.phat == [101] and [g for g, _ in cong.ghi] == [101]       # không request nào vào 202
    assert _viec(mt, v).trang_thai == ob.BLOCKED_CONFIG


# ---------------------------------------------------------------- biến thể B: ghim lỗi → KHÔNG gửi

def test_B_ghim_loi_thi_khong_phat_request_roi_viec_ke_cung_revision_van_dung_tab(mt, monkeypatch):
    d = _link_cu(mt)
    v1 = _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet"})

    def hong(*a, **k):
        raise OSError("đĩa đầy (giả)")

    monkeypatch.setattr(sd, "chot_tab", hong, raising=False)       # đường ghim CŨ (sau SENT, đã bỏ)
    monkeypatch.setattr(sd, "_chot_tab", hong, raising=False)      # đường ghim trong giao dịch SENDING
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    viec = _viec(mt, v1)
    assert cong.phat == [] and cong.ghi == []                       # không ghim được thì KHÔNG gửi
    assert viec.trang_thai == ob.RETRY_WAIT and viec.gui_luc is None
    assert _ma_chot(mt, d) is None
    monkeypatch.undo()
    mt["dong_ho"].t += 3600
    ng.chay_mot_vong()
    assert _viec(mt, v1).trang_thai == ob.SENT and _ma_chot(mt, d) == 101
    _doi_ten_va_tao_lai(cong)
    v2 = _xep(mt, d, 2)
    ng.chay_mot_vong()
    assert [g for g, _ in cong.ghi] == [101, 101] and _viec(mt, v2).trang_thai == ob.SENT


def test_nhieu_viec_cung_revision_sau_unknown_deu_theo_ma_da_chot(mt):
    d = _link_cu(mt)
    ids = [_xep(mt, d, j) for j in (1, 2, 3)]
    cong = CongNhieuTab({101: "KetQuaQuet"})
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("mất phản hồi"))]
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=mt["dong_ho"], moi_vong=1)
    assert ng.nhan_quyen()
    ng.chay_mot_vong()                                             # việc 1: UNKNOWN (đã ghim 101)
    _doi_ten_va_tao_lai(cong)
    ng.chay_mot_vong()
    ng.chay_mot_vong()
    assert cong.phat == [101, 101, 101]
    assert [_viec(mt, i).trang_thai for i in ids] == [ob.UNKNOWN, ob.SENT, ob.SENT]


# ---------------------------------------------------------------- chết ở từng điểm

def test_chet_trong_giao_dich_ghim_sending_khong_de_lai_gi(mt, monkeypatch):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet"})
    goc = sd._chot_tab

    def chet(con, *a, **k):
        goc(con, *a, **k)                                           # đã INSERT trong giao dịch…
        raise MatDien()                                             # …chết trước COMMIT

    monkeypatch.setattr(sd, "_chot_tab", chet)
    ng = _ng(mt, cong)
    with pytest.raises(MatDien):
        ng.chay_mot_vong()
    ng.tha_quyen()
    monkeypatch.undo()
    assert cong.phat == [] and _ma_chot(mt, d) is None              # rollback cả mã tab lẫn SENDING
    assert _viec(mt, v).trang_thai == ob.CLAIMED and _viec(mt, v).gui_luc is None
    _ng(mt, cong).chay_mot_vong()                                   # khởi động lại: CLAIMED → PENDING → gửi
    assert cong.phat == [101] and _viec(mt, v).trang_thai == ob.SENT and _ma_chot(mt, d) == 101


@pytest.mark.parametrize("diem", ["chet_truoc_ghi", "sau_da_ghi"])
def test_chet_sau_khi_chot_khoi_dong_lai_unknown_gui_lai_dung_tab(mt, diem):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet"})
    cong.ke_hoach = [(diem, MatDien())]
    ng = _ng(mt, cong)
    with pytest.raises(MatDien):
        ng.chay_mot_vong()
    ng.tha_quyen()
    assert _viec(mt, v).trang_thai == ob.SENDING and _ma_chot(mt, d) == 101
    _doi_ten_va_tao_lai(cong)
    ng2 = _ng(mt, cong)                                             # khôi phục: SENDING → UNKNOWN
    assert _viec(mt, v).trang_thai == ob.UNKNOWN
    ob.gui_lai_co_the_trung(mt["db"], v)
    ng2.chay_mot_vong()
    assert cong.phat == [101, 101] and all(g == 101 for g, _ in cong.ghi)
    assert _viec(mt, v).trang_thai == ob.SENT


def test_mat_claim_truoc_dispatch_khong_ghim_khong_gui(mt):
    """Ghim + SENDING là MỘT giao dịch có fencing: người gửi đã mất claim thì không để lại mã tab nào."""
    d = _ho_so(mt, gid=None)
    v = _xep(mt, d, 1)
    cong = CongGia(gid=101)

    def gianh():
        con = sqlite3.connect(mt["db"])
        con.execute("UPDATE hang_doi_gui SET claim_token='chu-khac'")
        con.commit()
        con.close()

    cong.ke_hoach = [("hook", gianh)]
    _ng(mt, cong).chay_mot_vong()
    assert cong.bang == [] and _ma_chot(mt, d) is None
    assert _viec(mt, v).trang_thai == ob.CLAIMED


def test_ma_da_chot_khac_tab_vua_tim_thi_khong_ghi(mt):
    """Mã của revision được chốt (lần đầu thắng) ngay trước lúc transport tìm tab theo tên → tab vừa tìm KHÁC mã
    đã chốt: không ghi đè mã cũ, không gửi; lần sau gửi theo mã đã chốt."""
    d = _ho_so(mt, gid=None)
    v = _xep(mt, d, 1)
    cong = CongGia(gid=101)

    def chot_truoc():
        with sd.ket_noi(mt["db"], ghi=True) as con:
            sd._chot_tab(con, d.id, d.phien_ban, worksheet_id=555, worksheet_ten="KetQuaQuet")

    cong.ke_hoach = [("hook", chot_truoc)]
    _ng(mt, cong).chay_mot_vong()
    assert cong.bang == [] and _ma_chot(mt, d) == 555
    assert _viec(mt, v).trang_thai == ob.RETRY_WAIT and _viec(mt, v).gui_luc is None


class CongSaiMa(CongGia):
    """Transport hỏng: đích có mã 101 nhưng báo đã tìm được tab mã 999."""

    def gui(self, chot, duong_dan_khoa, header, rows, truoc_khi_gui):
        truoc_khi_gui(999, "KetQuaQuet")
        self.bang.append((chot.spreadsheet_id, 999, [list(r) for r in rows]))
        return ob.KetQuaGui(phan_hoi_dung(chot, "KetQuaQuet", len(rows)), 999, "KetQuaQuet", len(rows))


def test_transport_tra_tab_khac_ma_ho_so_thi_chan(mt):
    d = _ho_so(mt, gid=101, tab="KetQuaQuet")
    v = _xep(mt, d, 1)
    cong = CongSaiMa()
    _ng(mt, cong).chay_mot_vong()
    assert cong.bang == [] and _ma_chot(mt, d) is None
    assert _viec(mt, v).trang_thai == ob.BLOCKED_CONFIG


class CongKhongBao(CongGia):
    """Transport vi phạm hợp đồng: ghi rồi trả kết quả mà KHÔNG gọi ``truoc_khi_gui``."""

    def gui(self, chot, duong_dan_khoa, header, rows, truoc_khi_gui):
        self.bang.append((chot.spreadsheet_id, 101, [list(r) for r in rows]))
        return ob.KetQuaGui(phan_hoi_dung(chot, "KetQuaQuet", len(rows)), 101, "KetQuaQuet", len(rows))


def test_transport_khong_qua_buoc_chot_la_khong_ro(mt):
    d = _ho_so(mt, gid=None)
    v = _xep(mt, d, 1)
    _ng(mt, CongKhongBao()).chay_mot_vong()
    assert _viec(mt, v).trang_thai == ob.UNKNOWN and _ma_chot(mt, d) is None


# ---------------------------------------------------------------- hồ sơ có mã tab: CÙNG bất biến

def test_ho_so_co_ma_tab_unknown_doi_ten_gui_lai_dung_ma(mt):
    d = _ho_so(mt, gid=101, tab="KetQuaQuet")
    v = _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet"})
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("mất phản hồi"))]
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    assert _ma_chot(mt, d) == 101
    _doi_ten_va_tao_lai(cong)                                       # tên đối chiếu không còn khớp
    ob.gui_lai_co_the_trung(mt["db"], v)
    ng.chay_mot_vong()
    assert cong.phat == [101, 101] and _viec(mt, v).trang_thai == ob.SENT


def test_ho_so_co_ma_tab_bi_xoa_thi_chan(mt):
    d = _ho_so(mt, gid=101, tab="KetQuaQuet")
    _xep(mt, d, 1)
    cong = CongNhieuTab({101: "KetQuaQuet"})
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    cong.xoa(101)
    cong.them(202, "KetQuaQuet")
    v2 = _xep(mt, d, 2)
    ng.chay_mot_vong()
    assert cong.phat == [101] and _viec(mt, v2).trang_thai == ob.BLOCKED_CONFIG


# ---------------------------------------------------------------- biên nhận phải khớp mã đã ghim

class CongTraMaKhac(CongGia):
    """Phát request vào tab 101 nhưng báo đã ghi tab 202 (transport/biên nhận bất thường)."""

    def gui(self, chot, duong_dan_khoa, header, rows, truoc_khi_gui):
        truoc_khi_gui(101, "KetQuaQuet")
        self.bang.append((chot.spreadsheet_id, 101, [list(r) for r in rows]))
        return ob.KetQuaGui(phan_hoi_dung(chot, "KetQuaQuet", len(rows)), 202, "KetQuaQuet", len(rows))


def test_bien_nhan_khac_ma_vua_ghim_la_khong_ro_khong_chot_ma_moi(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    _ng(mt, CongTraMaKhac()).chay_mot_vong()
    assert _viec(mt, v).trang_thai == ob.UNKNOWN
    assert _ma_chot(mt, d) == 101


# ---------------------------------------------------------------- việc của bản cũ: đã phát mà chưa có mã tab

def _viec_ban_cu_da_phat(mt, d, *, trang_thai=ob.UNKNOWN):
    """Dòng do mã CŨ để lại: đã phát request (``gui_luc``), hồ sơ theo tên, KHÔNG có mã tab đã chốt."""
    v = _xep(mt, d, 1)
    con = sqlite3.connect(mt["db"])
    con.execute("UPDATE hang_doi_gui SET trang_thai=?, gui_luc=?, so_lan_thu=1 WHERE id=?",
                (trang_thai, 999.0, v))
    con.commit()
    con.close()
    return v


def test_viec_ban_cu_chua_co_ma_tab_khong_cho_gui_lai_theo_ten(mt):
    d = _link_cu(mt)
    v = _viec_ban_cu_da_phat(mt, d)
    with pytest.raises(ob.LoiHangDoi, match="mã tab"):
        ob.gui_lai_co_the_trung(mt["db"], v)
    assert _viec(mt, v).trang_thai == ob.UNKNOWN
    ob.xac_nhan_da_gui(mt["db"], v, "đã thấy dòng trên Sheet")         # đối soát tay vẫn làm được
    assert _viec(mt, v).trang_thai == ob.SENT


def test_nguoi_gui_chan_viec_ban_cu_chua_co_ma_tab(mt):
    d = _link_cu(mt)
    v = _viec_ban_cu_da_phat(mt, d, trang_thai=ob.PENDING)
    cong = CongNhieuTab({202: "KetQuaQuet"})
    _ng(mt, cong).chay_mot_vong()
    assert cong.phat == [] and _viec(mt, v).trang_thai == ob.BLOCKED_CONFIG
    assert "mã tab" in _viec(mt, v).loi


def test_tab_da_ghim_cua_viec_cho_doi_soat(mt):
    d = _link_cu(mt)
    v = _xep(mt, d, 1)
    assert ob.tab_da_ghim(mt["db"], _viec(mt, v)) is None                # theo tên, chưa phát lần nào
    cong = CongNhieuTab({101: "KetQuaQuet"})
    cong.ke_hoach = [("sau_da_ghi", ob.KhongRo("mất phản hồi"))]
    _ng(mt, cong).chay_mot_vong()
    tc = ob.tab_da_ghim(mt["db"], _viec(mt, v))
    assert (tc.worksheet_id, tc.worksheet_ten) == (101, "KetQuaQuet")
    d2 = _ho_so(mt, gid=7, tab="Tab B")
    v2 = _xep(mt, d2, 2)
    assert ob.tab_da_ghim(mt["db"], _viec(mt, v2)).worksheet_id == 7      # hồ sơ có mã: biết trước


# ---------------------------------------------------------------- giao diện đối soát

def test_ui_viec_khong_ro_hien_ma_tab_da_ghim(tmp_path, monkeypatch):
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
        v = ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=HEADER, rows=[["x"] + [""] * 33])
        sd._chot_tab(con, d.id, d.phien_ban, worksheet_id=101, worksheet_ten="KetQuaQuet")
        con.execute("UPDATE hang_doi_gui SET trang_thai=?, gui_luc=1.0 WHERE id=?", (ob.UNKNOWN, v))
    at.run()
    chu = " ".join(str(x.value) for x in [*at.caption, *at.warning, *at.error, *at.info])
    assert "mã 101" in chu
    next(c for c in at.checkbox if c.key == f"gui_dong_y_trung_{v}").check().run()
    assert _nut(at, "⚠️ Gửi lại").disabled is False


def test_ui_viec_ban_cu_khong_co_ma_tab_khoa_nut_gui_lai(tmp_path, monkeypatch):
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
        v = ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=HEADER, rows=[["x"] + [""] * 33])
        con.execute("UPDATE hang_doi_gui SET trang_thai=?, gui_luc=1.0 WHERE id=?", (ob.UNKNOWN, v))
    at.run()
    next(c for c in at.checkbox if c.key == f"gui_dong_y_trung_{v}").check().run()
    assert _nut(at, "⚠️ Gửi lại").disabled is True
    assert any("mã tab" in e.value for e in at.error)
    assert ob.lay_viec(db, v).trang_thai == ob.UNKNOWN
