# -*- coding: utf-8 -*-
"""Engine + outbox: ý định gửi GHIM theo job, xếp hàng CÙNG giao dịch với lần quét, xoá lần quét.

* ``save_job`` trên bản Engine có ý định gửi chèn việc gửi trong CÙNG giao dịch với jobs/matches/
  bao_cao_job — lỗi ở bất kỳ bước nào thì không còn dòng nào (kể cả việc gửi);
* chỉ kết quả ``ok`` có dòng mới tạo việc gửi; báo cáo V2 lỗi → BLOCKED_REPORT (không payload);
* lô app (``scan_iter(y_dinh_gui=…)``) ghim trên bản sao của job — Engine gốc không mang ý định nào;
  Watch/CLI ghim cả lượt bằng ``ghim_y_dinh_gui``;
* xoá lần quét: việc chưa gửi bị xoá cùng giao dịch; đang gửi/không rõ → từ chối; đã gửi → chỉ giữ
  tombstone tối thiểu (không giữ payload).
Dữ liệu tổng hợp; transport giả; khoá dịch vụ GIẢ.
"""
import sqlite3
import threading

import pytest

import bao_cao_v2 as v2
import outbox as ob
import sheet_destinations as sd
from engine import ScanResult
from outbox_gia import CongGia, khoa_gia
from test_bao_cao_v2 import _bc, _kq_ca_that

ID_A = "1" + "a" * 43


@pytest.fixture()
def mt(engine, tmp_path):
    db = engine.sqlite_file
    iid = engine.installation_id()
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    a = sd.tao_dich(db, ten="Bảng A", spreadsheet_id=ID_A, worksheet_id=0,
                    worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    d = sd.tao_dich(db, ten="Bảng dọc", spreadsheet_id=ID_A, worksheet_id=5,
                    worksheet_ten="Doc", schema_id=sd.SCHEMA_DOC,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    return {"eng": engine, "db": db, "iid": iid, "a": a, "doc": d, "tmp": tmp_path}


def _y(mt, dich="a", lo="lo1"):
    return sd.chot_y_dinh(mt["db"], mt[dich].id, installation_id=mt["iid"], lo_id=lo)


def _kq_v2(**them):
    kq = _kq_ca_that(**them)
    kq.bao_cao = _bc(kq)
    return kq


def _dem(db, bang, job_id):
    cot = "id" if bang == "jobs" else "job_id"
    con = sqlite3.connect(db)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {bang} WHERE {cot}=?", (job_id,)).fetchone()[0]
    finally:
        con.close()


def test_khong_ghim_thi_khong_co_viec_gui(mt):
    mt["eng"].save_job(_kq_v2(), "youtube")
    assert ob.ds_viec(mt["db"]) == []


def test_ghim_thi_xep_hang_cung_giao_dich_payload_tu_anh_chup(mt):
    eng = mt["eng"]
    kq = _kq_v2()
    with eng.ghim_y_dinh_gui(_y(mt)):
        job_id = eng.save_job(kq, "youtube")
    (v,) = ob.ds_viec(mt["db"])
    assert v.job_id == job_id and v.trang_thai == ob.PENDING and v.lo_id == "lo1"
    assert v.rows == [v2.dong_ngang(kq.bao_cao)] and len(v.header) == 34
    assert v.dich.dich_id == mt["a"].id and v.dich.spreadsheet_id == ID_A
    assert getattr(eng, "_y_dinh_gui", None) is None            # hết lượt thì gỡ ghim


def test_loi_giua_giao_dich_khong_con_dong_nao(mt):
    """Ghi lỗi giữa giao dịch (đĩa đầy giả) → không còn dòng nào, và lỗi là LỖI LƯU BỀN tường minh
    (nơi gọi dừng nhận việc mới, không báo «đã lưu»); thông báo không lộ đường dẫn DB."""
    from engine import LoiLuuBen

    con = sqlite3.connect(mt["db"])
    con.execute("CREATE TRIGGER chan_outbox BEFORE INSERT ON hang_doi_gui "
                "BEGIN SELECT RAISE(ABORT, 'disk full gia'); END")
    con.commit()
    con.close()
    with pytest.raises(LoiLuuBen) as loi:
        with mt["eng"].ghim_y_dinh_gui(_y(mt)):
            mt["eng"].save_job(_kq_v2(), "youtube")
    assert isinstance(loi.value.__cause__, sqlite3.DatabaseError)
    assert "chưa được lưu" in str(loi.value) and mt["db"] not in str(loi.value)
    con = sqlite3.connect(mt["db"])
    for bang in ("jobs", "matches", "bao_cao_job", "hang_doi_gui"):
        assert con.execute(f"SELECT COUNT(*) FROM {bang}").fetchone()[0] == 0, bang
    con.close()


def test_bao_cao_v2_loi_thanh_blocked_report_khong_payload(mt):
    kq = _kq_ca_that()
    kq.bao_cao = v2.LoiBaoCaoV2(v2.LOI_TAO, ngoai_le="RuntimeError")
    with mt["eng"].ghim_y_dinh_gui(_y(mt)):
        job_id = mt["eng"].save_job(kq, "youtube")
    (v,) = ob.ds_viec(mt["db"])
    assert v.job_id == job_id and v.trang_thai == ob.BLOCKED_REPORT
    assert v.rows is None and v.header is None and "V2" in v.loi


def test_ket_qua_loi_hoac_khong_dong_thi_khong_xep_hang(mt):
    with mt["eng"].ghim_y_dinh_gui(_y(mt)):
        mt["eng"].save_job(_kq_v2(status="error", note="lỗi"), "youtube")
        khong_khop = _kq_ca_that(matches=[], so_dat_nguong=0)
        khong_khop.bao_cao = _bc(khong_khop)
        mt["eng"].save_job(khong_khop, "youtube")              # ngang: không có dòng
    assert ob.ds_viec(mt["db"]) == []


def test_doc16_khong_khop_van_gui_dong_bao_khong_tim_thay(mt):
    kq = _kq_ca_that(matches=[], so_dat_nguong=0)
    kq.bao_cao = _bc(kq)
    with mt["eng"].ghim_y_dinh_gui(_y(mt, "doc")):
        mt["eng"].save_job(kq, "youtube")
    (v,) = ob.ds_viec(mt["db"])
    assert v.trang_thai == ob.PENDING and len(v.header) == 16 and v.rows == v2.dong_doc(kq.bao_cao)


def test_sua_ho_so_sau_khi_ghim_khong_doi_viec_da_xep(mt):
    y = _y(mt)
    sd.sua_dich(mt["db"], mt["a"].id, spreadsheet_id="1" + "q" * 43)
    with mt["eng"].ghim_y_dinh_gui(y):
        mt["eng"].save_job(_kq_v2(), "youtube")
    (v,) = ob.ds_viec(mt["db"])
    assert v.dich.spreadsheet_id == ID_A and v.dich.phien_ban == 1


def test_ban_sao_job_ke_thua_ghim_cua_luot(mt):
    y = _y(mt)
    with mt["eng"].ghim_y_dinh_gui(y):
        job = mt["eng"]._ban_sao_cho_job()
        assert job._y_dinh_gui is y
    assert mt["eng"]._y_dinh_gui is None


def test_scan_iter_ghim_tren_ban_sao_khong_dong_toi_engine_goc(mt, monkeypatch):
    """Lô app: mọi video của lô xếp hàng về ĐÚNG đích đã chụp lúc Bắt đầu; Engine gốc sạch."""
    import engine as engine_mod

    def quet_gia(self, url, progress=None, luu_lich_su=True, **kw):
        kq = _kq_v2(source_ref=url, source_id=url[-11:])
        if luu_lich_su:
            kq.job_id = self.save_job(kq, "youtube")
        return kq

    monkeypatch.setattr(engine_mod.Engine, "scan_youtube", quet_gia)
    y = _y(mt, lo="lo-A")
    nguon = [f"https://youtu.be/vid{i:08d}" for i in range(3)]
    ket = list(mt["eng"].scan_iter(nguon, "youtube", y_dinh_gui=y))
    assert len(ket) == 3 and getattr(mt["eng"], "_y_dinh_gui", None) is None
    viec = ob.ds_viec(mt["db"])
    assert len(viec) == 3 and {v.lo_id for v in viec} == {"lo-A"}
    assert {v.dich.dich_id for v in viec} == {mt["a"].id}
    list(mt["eng"].scan_iter(nguon[:1], "youtube"))            # lô sau KHÔNG ghim → không xếp
    assert len(ob.ds_viec(mt["db"])) == 3


def test_luu_xong_thi_danh_thuc_nguoi_gui(mt, monkeypatch):
    goi = []
    monkeypatch.setattr(ob, "danh_thuc", lambda db: goi.append(db))
    with mt["eng"].ghim_y_dinh_gui(_y(mt)):
        mt["eng"].save_job(_kq_v2(), "youtube")
    assert goi == [mt["db"]]


# ---------- xoá lần quét ----------

def _luu_ghim(mt):
    with mt["eng"].ghim_y_dinh_gui(_y(mt)):
        return mt["eng"].save_job(_kq_v2(), "youtube")


def _ep(db, job_id, trang_thai):
    con = sqlite3.connect(db)
    con.execute("UPDATE hang_doi_gui SET trang_thai=? WHERE job_id=?", (trang_thai, job_id))
    con.commit()
    con.close()


def test_xoa_job_xoa_viec_chua_gui_cung_giao_dich(mt):
    job_id = _luu_ghim(mt)
    mt["eng"].delete_job(job_id)
    assert ob.ds_viec(mt["db"]) == [] and _dem(mt["db"], "jobs", job_id) == 0
    assert _dem(mt["db"], "bao_cao_job", job_id) == 0           # P1-01 giữ nguyên


@pytest.mark.parametrize("tt", [ob.CLAIMED, ob.SENDING, ob.UNKNOWN])
def test_xoa_job_dang_gui_hoac_khong_ro_bi_tu_choi(mt, tt):
    from engine import LoiXoaJob
    job_id = _luu_ghim(mt)
    _ep(mt["db"], job_id, tt)
    with pytest.raises(LoiXoaJob):
        mt["eng"].delete_job(job_id)
    assert _dem(mt["db"], "jobs", job_id) == 1 and len(ob.ds_viec(mt["db"])) == 1


def test_xoa_job_da_gui_chi_giu_tombstone(mt):
    job_id = _luu_ghim(mt)
    ng = ob.NguoiGui(mt["db"], mt["eng"].data_dir, CongGia())
    assert ng.nhan_quyen()
    ng.chay_mot_vong()
    ng.tha_quyen()
    mt["eng"].delete_job(job_id)
    (v,) = ob.ds_viec(mt["db"])
    assert v.trang_thai == ob.SENT and v.da_xoa_job == 1
    assert v.rows_json is None and v.header_json is None and v.bien_nhan and v.payload_sha256


def test_tranh_chap_xoa_va_claim_khong_de_viec_mo_coi(mt):
    """Xoá lần quét và người gửi claim cùng lúc: hoặc job còn + việc đang trong tay người gửi, hoặc
    job đã xoá + KHÔNG còn việc chưa gửi nào của nó. Không bao giờ: job đã xoá mà việc vẫn bay."""
    from engine import LoiXoaJob
    ng = ob.NguoiGui(mt["db"], mt["eng"].data_dir, CongGia())
    assert ng.nhan_quyen()
    for _ in range(25):
        job_id = _luu_ghim(mt)
        (v,) = [x for x in ob.ds_viec(mt["db"]) if x.job_id == job_id]
        loi = []
        rao = threading.Barrier(2)

        def xoa():
            rao.wait()
            try:
                mt["eng"].delete_job(job_id)
            except LoiXoaJob:
                loi.append("tu_choi")

        def claim():
            rao.wait()
            ng._claim(v.id, 10 ** 12)

        t1, t2 = threading.Thread(target=xoa), threading.Thread(target=claim)
        t1.start(), t2.start()
        t1.join(), t2.join()
        con_job = _dem(mt["db"], "jobs", job_id)
        viec = [x for x in ob.ds_viec(mt["db"]) if x.job_id == job_id]
        if con_job:
            assert loi == ["tu_choi"] and viec[0].trang_thai == ob.CLAIMED
            _ep(mt["db"], job_id, ob.PENDING)
            mt["eng"].delete_job(job_id)
        else:
            assert viec == []
    ng.tha_quyen()


def test_ket_qua_dung_tay_khong_co_bao_cao_la_luat_cu_bi_chan(mt):
    kq = ScanResult(source_name="x", source_ref="u", source_id="idx", status="ok",
                    matches=_kq_ca_that().matches)
    with mt["eng"].ghim_y_dinh_gui(_y(mt)):
        mt["eng"].save_job(kq, "youtube")
    (v,) = ob.ds_viec(mt["db"])
    assert v.trang_thai == ob.BLOCKED_REPORT and "luật" in v.loi


def test_bo_dieu_khien_lo_ghim_dich_luc_bat_dau_doi_lua_chon_khong_doi_lo(mt, monkeypatch):
    """Lô A đang chạy, UI đổi sang B: mọi việc của lô vẫn A; snapshot báo đúng đích đang chạy."""
    import threading

    import engine as engine_mod
    from scan_jobs import ScanJobController

    cho = threading.Event()
    di_tiep = threading.Event()

    def quet_gia(self, url, progress=None, luu_lich_su=True, **kw):
        kq = _kq_v2(source_ref=url, source_id=url[-11:])
        kq.job_id = self.save_job(kq, "youtube")
        cho.set()
        di_tiep.wait(10)
        return kq

    monkeypatch.setattr(engine_mod.Engine, "scan_youtube", quet_gia)
    b = sd.tao_dich(mt["db"], ten="Bảng B", spreadsheet_id="1" + "b" * 43, worksheet_id=3,
                    worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    ctl = ScanJobController(mt["eng"])
    y_a = _y(mt, lo="lo-A")
    ctl.start([f"https://youtu.be/vid{i:08d}" for i in range(3)], "youtube", y_dinh_gui=y_a)
    assert cho.wait(10)
    anh = ctl.snapshot()
    assert anh.dich_gui == y_a.dich.nhan and anh.lo_id == "lo-A"
    _ = sd.chot_y_dinh(mt["db"], b.id, installation_id=mt["iid"])   # «UI chọn B» giữa chừng
    di_tiep.set()
    ctl._thread.join(30)
    viec = ob.ds_viec(mt["db"], lo_id="lo-A")
    assert len(viec) == 3 and {v.dich.dich_id for v in viec} == {mt["a"].id}
    assert getattr(mt["eng"], "_y_dinh_gui", None) is None
