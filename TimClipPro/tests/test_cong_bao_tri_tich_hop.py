# -*- coding: utf-8 -*-
"""Cổng bảo trì nối vào MỌI loại việc (brief §14): lô quét app, lượt Watch, dựng kho, gửi Google Sheets,
lệnh CLI — và bản CŨ không nhận việc mới sau khi bản mới đã kích hoạt (managed).

* Cổng đang rút (updater chuẩn bị đổi mã) → việc mới bị từ chối NGAY, chưa làm gì (không tải, không quét,
  không claim); "đang bảo trì" là một dạng "bận" (`DangChayRoi`) nên mọi chỗ báo bận cũ báo đúng.
* Việc đang chạy giữ lease → updater CHỜ tới khi xong (không giết).
"""
import json
import os
import threading
import time

import pytest

import cli
import maintenance_gate as mg
import outbox as ob
import sheet_destinations as sd
from khoa import DangChayRoi
from outbox_gia import CongGia, dich_gia
from scan_jobs import ScanJobController
from watch import MucTheoDoi, WatchList, chay_giam_sat


def _cho(dk, han=10.0):
    het = time.monotonic() + han
    while not dk():
        assert time.monotonic() < het, "quá hạn chờ"
        time.sleep(0.02)


def test_dang_bao_tri_la_mot_dang_ban():
    assert issubclass(mg.DangBaoTri, DangChayRoi)


def test_lo_quet_app_bi_tu_choi_khi_dang_rut_va_giu_lease_suot_lo(engine, monkeypatch):
    ctl = ScanJobController(engine)
    rut = engine.cong_bao_tri.bat_dau_rut("cập nhật thử")
    try:
        with pytest.raises(mg.DangBaoTri):
            ctl.start(["https://youtu.be/dQw4w9WgXcQ"], "youtube")
        assert not ctl.running
    finally:
        rut.ket_thuc()
    vao, cho_phep = threading.Event(), threading.Event()

    def scan_iter_gia(nguon, source_type, progress=None, on_video=None, **kw):
        vao.set()
        cho_phep.wait(10)
        return iter(())

    monkeypatch.setattr(engine, "scan_iter", scan_iter_gia)
    ctl.start(["u"], "youtube")
    assert vao.wait(10)
    assert [v["ten"] for v in engine.cong_bao_tri.viec_dang_chay()] == ["lô quét (youtube)"]
    rut = engine.cong_bao_tri.bat_dau_rut("cập nhật")
    try:
        assert rut.cho_ranh(0.3, 0.05) is False                 # lô đang chạy → updater chờ
        cho_phep.set()
        _cho(lambda: not ctl.running)
        assert rut.cho_ranh(5, 0.05) is True
    finally:
        rut.ket_thuc()


def test_luot_watch_khi_dang_rut_la_ban_khong_quet(engine, monkeypatch):
    monkeypatch.setattr(engine, "scan_youtube", lambda *a, **k: pytest.fail("không được quét"))
    rut = engine.cong_bao_tri.bat_dau_rut("cập nhật")
    try:
        bc = chay_giam_sat(engine, WatchList(muc=[MucTheoDoi("link", "https://youtu.be/dQw4w9WgXcQ")]),
                           lister=lambda url, limit: [])
    finally:
        rut.ket_thuc()
    assert bc.ban is True and "cập nhật" in " ".join(bc.loi)


def test_dung_kho_khi_dang_rut_bi_tu_choi(engine, tmp_path):
    (tmp_path / "kho").mkdir()
    rut = engine.cong_bao_tri.bat_dau_rut("cập nhật")
    try:
        with pytest.raises(DangChayRoi):
            engine.build_database(str(tmp_path / "kho"), mode="new")
    finally:
        rut.ket_thuc()


def test_nguoi_gui_khong_claim_khi_dang_rut_va_updater_cho_viec_dang_bay(engine, tmp_path):
    _, y = dich_gia(engine.sqlite_file, tmp_path, installation_id=engine.installation_id())
    with sd.ket_noi(engine.sqlite_file, ghi=True) as con:
        v1 = ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=["h"] * 34, rows=[["r"] * 34])
    cong = CongGia()
    ng = ob.NguoiGui(engine.sqlite_file, engine.data_dir, cong)
    assert ng.nhan_quyen()
    rut = engine.cong_bao_tri.bat_dau_rut("cập nhật")
    try:
        dem = ng.chay_mot_vong()
        assert dem["tam_dung"] == 1 and cong.lan_goi == 0
        assert ob.lay_viec(engine.sqlite_file, v1).trang_thai == ob.PENDING
    finally:
        rut.ket_thuc()
    # Việc đang bay giữ lease: updater bật rút giữa chừng phải CHỜ, không đổi mã giữa request.
    with sd.ket_noi(engine.sqlite_file, ghi=True) as con:
        v2 = ob.them_viec(con, y, job_id=2, chinh_sach="v2", header=["h"] * 34, rows=[["r"] * 34])
    dang_bay, cho_phep = threading.Event(), threading.Event()

    class CongCham(CongGia):
        def gui(self, chot, khoa, header, rows, truoc_khi_gui):
            def truoc(gid, ten):
                truoc_khi_gui(gid, ten)
                dang_bay.set()
                cho_phep.wait(10)
            return super().gui(chot, khoa, header, rows, truoc)

    ng.cong = CongCham()
    t = threading.Thread(target=ng.chay_mot_vong)
    t.start()
    assert dang_bay.wait(10)
    rut = engine.cong_bao_tri.bat_dau_rut("cập nhật")
    try:
        assert rut.cho_ranh(0.3, 0.05) is False
        cho_phep.set()
        t.join(10)
        assert rut.cho_ranh(5, 0.05) is True
        # Việc đang bay (v1) chạy xong; việc kế (v2) KHÔNG được claim khi cổng đang rút.
        assert ob.lay_viec(engine.sqlite_file, v1).trang_thai == ob.SENT
        assert ob.lay_viec(engine.sqlite_file, v2).trang_thai == ob.PENDING
    finally:
        rut.ket_thuc()
    ng.cong = CongGia()
    ng.chay_mot_vong()
    assert ob.lay_viec(engine.sqlite_file, v2).trang_thai == ob.SENT


def test_cli_quet_khi_dang_rut_thoat_ma_ban(engine, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["cli.py", "youtube", "https://youtu.be/dQw4w9WgXcQ"])
    monkeypatch.setattr(cli, "Engine", lambda *a, **k: engine)
    monkeypatch.setattr(engine, "scan_many", lambda *a, **k: pytest.fail("không được quét"))
    monkeypatch.setattr(engine, "scan_iter", lambda *a, **k: pytest.fail("không được quét"))
    rut = engine.cong_bao_tri.bat_dau_rut("cập nhật")
    try:
        with pytest.raises(SystemExit) as e:
            cli.main()
    finally:
        rut.ket_thuc()
    assert e.value.code == 2 and "cập nhật" in capsys.readouterr().err


def test_cli_dondep_khi_dang_rut_thoat_ma_ban(engine, monkeypatch, capsys):
    """Rà soát M3+M4 (P3-9): ``dondep`` xoá đệm + thư mục job quét — cũng là việc, phải vào cổng."""
    monkeypatch.setattr("sys.argv", ["cli.py", "dondep", "--xem-truoc"])
    monkeypatch.setattr(cli, "Engine", lambda *a, **k: engine)
    monkeypatch.setattr(cli.don_dep, "don_kho_dem", lambda *a, **k: pytest.fail("không được dọn"))
    rut = engine.cong_bao_tri.bat_dau_rut("cập nhật")
    try:
        with pytest.raises(SystemExit) as e:
            cli.main()
    finally:
        rut.ket_thuc()
    assert e.value.code == 2 and "cập nhật" in capsys.readouterr().err


def test_cli_vameta_khi_dang_rut_thoat_ma_ban(engine, tmp_path, monkeypatch, capsys):
    """Rà soát M3+M4 (P3-9): ``vameta`` gọi mạng + ghi metadata kho — vào cổng TRƯỚC khi gọi gì."""
    monkeypatch.setattr("sys.argv", ["cli.py", "vameta", "--kho", str(tmp_path / "kho")])
    monkeypatch.setattr(cli, "thu_muc_data_mac_dinh", lambda *a, **k: engine.data_dir)
    monkeypatch.setattr(cli, "ChannelSync", lambda *a, **k: pytest.fail("không được gọi mạng"))
    rut = engine.cong_bao_tri.bat_dau_rut("cập nhật")
    try:
        with pytest.raises(SystemExit) as e:
            cli.main()
    finally:
        rut.ket_thuc()
    assert e.value.code == 2 and "cập nhật" in capsys.readouterr().err


def test_ban_cu_khong_nhan_viec_moi_sau_khi_ban_moi_kich_hoat(tmp_path):
    goc = tmp_path / "cai dat"
    rel_cu = goc / "releases" / "1.0.0"
    rel_cu.mkdir(parents=True)
    (rel_cu / "MANAGED_RELEASE.json").write_text("{}", encoding="utf-8")
    (goc / "update_state").mkdir()
    env = {"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_INSTALLATION_ROOT": str(goc)}

    def con_tro(phien_ban):
        (goc / "update_state" / "current.json").write_text(json.dumps(
            {"phien_ban": phien_ban, "release": str(goc / "releases" / phien_ban)}), encoding="utf-8")

    con_tro("1.0.0")
    assert mg.ly_do_ban_cu(env, rel_cua_toi=str(rel_cu)) == ""
    con_tro("1.1.0")
    assert "mở lại" in mg.ly_do_ban_cu(env, rel_cua_toi=str(rel_cu))
    assert mg.ly_do_ban_cu({}, rel_cua_toi=str(rel_cu)) == ""                 # legacy: không áp dụng
    assert mg.ly_do_ban_cu(env, rel_cua_toi=str(tmp_path / "worktree")) == ""  # không phải release
    (goc / "update_state" / "current.json").write_text("{hỏng", encoding="utf-8")
    assert mg.ly_do_ban_cu(env, rel_cua_toi=str(rel_cu))                       # hỏng → không nhận việc
    cong = mg.CongBaoTri(str(tmp_path / "data"),
                         kiem_them=lambda: mg.ly_do_ban_cu(env, rel_cua_toi=str(rel_cu)))
    con_tro("1.1.0")
    with pytest.raises(mg.DangBaoTri):
        with cong.viec("lô quét"):
            pass
    assert os.path.isdir(str(tmp_path / "data" / mg.THU_MUC))
