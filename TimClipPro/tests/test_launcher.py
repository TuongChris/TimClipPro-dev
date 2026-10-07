# -*- coding: utf-8 -*-
"""launcher.py — chọn bản đang kích hoạt, môi trường managed cho tiến trình con, khôi phục cập nhật dở
TRƯỚC khi mở app/Watch, không mạng khi mở. Tiến trình con được THAY bằng hàm ghi lại (không mở app thật).
"""
import json
import os

import pytest

import launcher
import maintenance_gate as mg
import managed_update as mu
from cap_nhat_gia import KhoaThu, MoiTruongGia, phat_hanh


@pytest.fixture()
def cai(tmp_path, monkeypatch):
    khoa = KhoaThu()
    goc = str(tmp_path / "Cai Dat TimClip")
    state = str(tmp_path / "state")
    nguon = str(tmp_path / "nguon")
    os.makedirs(nguon)
    os.makedirs(os.path.join(goc, "launcher"))
    khoa.ghi_tin_cay(os.path.join(goc, "launcher", launcher.TEN_KHOA_TIN_CAY))
    with open(os.path.join(goc, "launcher", launcher.TEN_CAU_HINH), "w", encoding="utf-8") as f:
        json.dump({"state_root": state, "nguon": {"loai": "thu_muc", "duong_dan": nguon},
                   "python_goc": "", "han_cho_ranh_s": 0.3}, f)
    gia = MoiTruongGia(state)
    import runtime_paths

    runtime_paths.tao_dinh_danh(state, installation_root=goc)       # như bootstrap thật
    thay = dict(tao_moi_truong=gia.tao_moi_truong, kiem_suc_khoe=gia.kiem_suc_khoe,
                di_chuyen=gia.di_chuyen, sao_luu=gia.sao_luu, phien_ban_db=gia.phien_ban_db)
    goi = []

    def chay(argv, **kw):
        goi.append((argv, kw))
        return 0

    for bien in ("TIMCLIP_DATA_DIR", "SHEET_LINK"):
        monkeypatch.setenv(bien, "gia_tri_legacy")

    def main(*doi_so, **kw):
        return launcher.main(list(doi_so), goc=goc, chay=chay, **{**thay, **kw})

    return {"goc": goc, "state": state, "nguon": nguon, "khoa": khoa, "gia": gia, "goi": goi,
            "main": main, "thay": thay}


def _cai_ban(cai, pb):
    phat_hanh(cai["nguon"], pb, cai["khoa"])
    assert cai["main"]("update", "prepare") == 0
    assert cai["main"]("update", "apply") == 0


def test_chua_bootstrap_thi_bao_ro(tmp_path, capsys):
    assert launcher.main(["app"], goc=str(tmp_path)) == 1
    assert "chưa được bootstrap" in capsys.readouterr().err


def test_chua_co_ban_kich_hoat_thi_khong_mo(cai, capsys):
    assert cai["main"]("app") == 1
    assert "Chưa có bản nào" in capsys.readouterr().err and cai["goi"] == []


def test_app_chay_ban_dang_kich_hoat_moi_truong_managed(cai):
    _cai_ban(cai, "1.0.0")
    assert cai["main"]("app") == 0
    (argv, kw), = cai["goi"]
    rel = os.path.join(cai["goc"], "releases", "1.0.0")
    assert argv[0] == os.path.join(cai["goc"], "environments", "py312-thu", "Scripts", "python.exe")
    assert argv[1:4] == ["-m", "streamlit", "run"] and argv[4] == os.path.join(rel, "TimClipPro", "app.py")
    assert "--server.address=127.0.0.1" in argv
    env = kw["env"]
    assert env["TIMCLIP_RUNTIME_MODE"] == "managed" and env["TIMCLIP_STATE_ROOT"] == cai["state"]
    assert env["PYTHONPYCACHEPREFIX"].startswith(cai["state"])       # release bất biến
    assert "TIMCLIP_DATA_DIR" not in env and "SHEET_LINK" not in env
    assert kw["cwd"] == cai["state"]


def test_watch_qua_launcher_mang_log_va_doi_so(cai):
    _cai_ban(cai, "1.0.0")
    assert cai["main"]("watch", "--destination", "abc") == 0
    (argv, _), = cai["goi"]
    assert argv[1].endswith(os.path.join("TimClipPro", "cli.py"))
    assert argv[2:] == ["watch", "--log", "--destination", "abc"]


def test_mo_app_khong_goi_mang_kiem_ban_moi(cai):
    _cai_ban(cai, "1.0.0")

    class NguonCam:
        def ds(self):
            raise AssertionError("mở app không được gọi nguồn phát hành")

    assert cai["main"]("app", nguon=NguonCam()) == 0


def test_khoi_phuc_cap_nhat_do_truoc_khi_mo(cai):
    _cai_ban(cai, "1.0.0")
    phat_hanh(cai["nguon"], "1.1.0", cai["khoa"])

    def chet(ten):
        if ten == "POINTER_SWITCHED":
            raise mu.MatDien(ten)

    with pytest.raises(mu.MatDien):
        assert cai["main"]("update", "prepare") == 0
        cai["main"]("update", "apply", diem_dung=chet)
    assert cai["main"]("app") == 0                 # tiến trình mới: khôi phục rồi mới mở
    (argv, _), = cai["goi"]
    assert os.path.join("releases", "1.1.0") in argv[4]
    cd = mu.CaiDat(cai["goc"], cai["state"])
    assert mu.doc_json(cd.file_trang_thai("last_good.json"))["phien_ban"] == "1.1.0"


def test_update_hoan_khi_con_viec_thi_ma_2(cai):
    _cai_ban(cai, "1.0.0")
    phat_hanh(cai["nguon"], "1.1.0", cai["khoa"])
    assert cai["main"]("update", "prepare") == 0
    with mg.CongBaoTri(os.path.join(cai["state"], "data")).viec("lượt Watch"):
        assert cai["main"]("update", "apply") == 2


def test_launcher_khong_dung_updater_cu_hay_git():
    """Mã (không tính docstring) không import ``cap_nhat`` và không có chuỗi lệnh ``git``/``cap_nhat.py``."""
    import ast

    cay = ast.parse(open(launcher.__file__, encoding="utf-8").read())
    mod = {a.name for n in ast.walk(cay) if isinstance(n, ast.Import) for a in n.names}
    mod |= {n.module for n in ast.walk(cay) if isinstance(n, ast.ImportFrom)}
    chuoi = {n.value for n in ast.walk(cay) if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and len(n.value) < 40}
    assert "cap_nhat" not in mod
    assert not {c for c in chuoi if c in ("git", "git.exe") or c.endswith("cap_nhat.py")}


def test_doctor_cai_dat_lanh_dat_va_phat_hien_cay_release_bi_sua(cai, capsys):
    _cai_ban(cai, "1.0.0")
    capsys.readouterr()
    assert cai["main"]("doctor") == 0
    out = capsys.readouterr().out
    assert "✅" in out and "1.0.0" in out and "❌" not in out
    app = os.path.join(cai["goc"], "releases", "1.0.0", "TimClipPro", "app.py")
    with open(app, "a", encoding="utf-8") as f:
        f.write("# bị sửa tay\n")
    assert cai["main"]("doctor") == 1
    assert "❌" in capsys.readouterr().out


def test_doctor_van_chay_khi_khoa_tin_cay_hong(cai, capsys):
    _cai_ban(cai, "1.0.0")
    with open(os.path.join(cai["goc"], "launcher", launcher.TEN_KHOA_TIN_CAY), "w", encoding="utf-8") as f:
        f.write("{hỏng")
    capsys.readouterr()
    assert cai["main"]("doctor") == 1
    out = capsys.readouterr().out
    assert "khoá tin cậy" in out.lower() and "❌" in out
