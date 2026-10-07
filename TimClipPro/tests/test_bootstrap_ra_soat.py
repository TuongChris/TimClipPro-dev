# -*- coding: utf-8 -*-
"""Rà soát đối nghịch M3+M4, P2-E (+ P3-11/15) — bootstrap hỏng dở thì KHÔNG bootstrap lại được:

* đường dẫn có dấu (vd. ``D:\\Công cụ\\TimClipPro``) → ghi ``.bat`` bằng ASCII sập SAU khi đã tạo định danh và
  launcher.json → chạy lại bị từ chối;
* lệnh trong hướng dẫn dùng Python gốc (không có ``cryptography``) → sập ngay (traceback);
* lỗi lạ in traceback; ``kiem_truoc`` nhận thư mục nằm TRONG một bản clone git, hoặc đã có dữ liệu cập nhật cũ.

Nay: ``.bat`` chỉ ASCII (``%~dp0`` cho đường dẫn trong thư mục cài đặt); định danh + launcher.json ghi CUỐI;
dở dang sau định danh (cùng thư mục cài đặt) thì làm TIẾP; Python thiếu gói → tạo môi trường launcher rồi
chạy lại chính bootstrap bằng Python đó; mọi lỗi → ``[LỖI]`` không traceback."""
import json
import os
import subprocess
import sys

import pytest

import bootstrap as bs
import managed_update as mu
import runtime_paths
from cap_nhat_gia import KhoaThu, MoiTruongGia, phat_hanh
from test_bootstrap import KIT


@pytest.fixture()
def bo(tmp_path):
    khoa = KhoaThu()
    tin_cay = khoa.ghi_tin_cay(str(tmp_path / "kit" / "trusted_keys.json"))
    nguon = tmp_path / "nguon"
    nguon.mkdir()
    return {"khoa": khoa, "tin_cay": tin_cay, "nguon": str(nguon), "tmp": tmp_path}


def _tham(bo, state, **kw):
    gia = MoiTruongGia(str(state))
    tham = dict(kit_dir=KIT, python_goc=sys.executable, tin_cay=bo["tin_cay"],
                nguon={"loai": "thu_muc", "duong_dan": bo["nguon"]}, py_launcher=sys.executable,
                tao_moi_truong=gia.tao_moi_truong, kiem_suc_khoe=gia.kiem_suc_khoe, di_chuyen=gia.di_chuyen,
                sao_luu=gia.sao_luu, phien_ban_db=gia.phien_ban_db)
    tham.update(kw)
    return tham


def _anh(tmp):
    return sorted(str(p) for p in tmp.rglob("*"))


def test_duong_dan_co_dau_bat_chi_ascii_va_cai_xong(bo):
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    goc, state = bo["tmp"] / "Công cụ" / "TimClipPro", bo["tmp"] / "Công cụ" / "State"
    kq = bs.bootstrap(str(goc), str(state), **_tham(bo, state))
    assert kq["cai_dat"]["trang_thai"] == mu.ACTIVE, kq["cai_dat"]
    for ten in ("TimClipPro.bat", "GiamSat.bat", "CapNhat.bat"):
        noi_dung = open(os.path.join(kq["goc"], ten), "rb").read()
        noi_dung.decode("ascii")                                         # cmd.exe đọc theo trang mã OEM
        assert b"%~dp0launcher\\launcher.py" in noi_dung


def test_python_launcher_ngoai_thu_muc_cai_dat_co_dau_bi_tu_choi_truoc_khi_ghi(bo):
    py = bo["tmp"] / "Người dùng Sơn" / "python.exe"
    py.parent.mkdir()
    py.write_bytes(b"")
    goc, state = bo["tmp"] / "pc2" / "goc", bo["tmp"] / "pc2" / "state"
    tham = _tham(bo, state, py_launcher=str(py))          # (môi trường giả tự tạo state/data trước)
    truoc = _anh(bo["tmp"])
    with pytest.raises(bs.LoiBootstrap):
        bs.bootstrap(str(goc), str(state), **tham)
    assert _anh(bo["tmp"]) == truoc


def test_lan_truoc_dung_sau_khi_tao_dinh_danh_thi_lam_tiep(bo):
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    goc, state = bo["tmp"] / "pc2" / "goc", bo["tmp"] / "pc2" / "state"
    state.mkdir(parents=True)
    dd = runtime_paths.tao_dinh_danh(str(state), installation_root=os.path.abspath(str(goc)))
    kq = bs.bootstrap(str(goc), str(state), **_tham(bo, state))
    assert kq["installation_id"] == dd["installation_id"]                  # GIỮ định danh, không tạo mới
    assert kq["cai_dat"]["trang_thai"] == mu.ACTIVE


def test_dinh_danh_cua_thu_muc_cai_dat_khac_van_bi_tu_choi(bo):
    goc, state = bo["tmp"] / "pc2" / "goc", bo["tmp"] / "pc2" / "state"
    state.mkdir(parents=True)
    runtime_paths.tao_dinh_danh(str(state), installation_root=str(bo["tmp"] / "khac"))
    with pytest.raises(bs.LoiBootstrap):
        bs.bootstrap(str(goc), str(state), **_tham(bo, state))


def test_cau_hinh_launcher_khong_con_truong_chet(bo):
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    goc, state = bo["tmp"] / "pc2" / "goc", bo["tmp"] / "pc2" / "state"
    kq = bs.bootstrap(str(goc), str(state), **_tham(bo, state))
    cfg = json.load(open(os.path.join(kq["goc"], "launcher", "launcher.json"), encoding="utf-8"))
    assert "tu_ap_dung" not in cfg


def test_python_goc_thieu_cryptography_tao_moi_truong_roi_chay_lai(bo, monkeypatch):
    goc, state = bo["tmp"] / "pc2" / "goc", bo["tmp"] / "pc2" / "state"
    py_env = str(bo["tmp"] / "env" / "python.exe")
    tao, chay = [], []
    monkeypatch.setattr(bs, "_thieu_goi", lambda nguon: ["cryptography"])
    monkeypatch.setattr(bs, "tao_moi_truong_launcher", lambda g, p, k: tao.append((g, p, k)) or py_env)
    monkeypatch.setattr(bs.subprocess, "run",
                        lambda argv, **k: chay.append(argv) or subprocess.CompletedProcess(argv, 0))
    doi_so = ["--goc", str(goc), "--state", str(state), "--python-goc", sys.executable,
              "--tin-cay", bo["tin_cay"], "--nguon-thu-muc", bo["nguon"]]
    assert bs.main(doi_so) == 0
    assert tao and tao[0][0] == os.path.abspath(str(goc))
    (argv,) = chay
    assert argv[0] == py_env and argv[-2:] == ["--python-launcher", py_env]
    i = argv.index(os.path.abspath(bs.__file__))                       # chạy lại CHÍNH bootstrap.py
    assert argv[i + 1:-2] == doi_so                                     # với đúng đối số gốc


def test_main_loi_la_bao_ngan_khong_traceback(bo, monkeypatch, capsys):
    def hong(*a, **k):
        raise RuntimeError("lỗi lạ giả")

    monkeypatch.setattr(bs, "bootstrap", hong)
    monkeypatch.setattr(bs, "_thieu_goi", lambda nguon: [])
    assert bs.main(["--goc", str(bo["tmp"] / "g"), "--state", str(bo["tmp"] / "s"), "--python-goc",
                    sys.executable, "--tin-cay", bo["tin_cay"], "--nguon-thu-muc", bo["nguon"]]) == 1
    err = capsys.readouterr().err
    assert "[LỖI]" in err and "RuntimeError" in err and "Traceback" not in err


def test_kiem_truoc_tu_choi_thu_muc_nam_trong_ban_clone_git(bo):
    (bo["tmp"] / "clone" / ".git").mkdir(parents=True)
    goc, state = bo["tmp"] / "clone" / "TimClipPro" / "goc", bo["tmp"] / "state"
    with pytest.raises(bs.LoiBootstrap):
        bs.kiem_truoc(str(goc), str(state), sys.executable)


def test_kiem_truoc_tu_choi_thu_muc_da_co_du_lieu_cap_nhat_cu(bo):
    goc, state = bo["tmp"] / "goc", bo["tmp"] / "state"
    (goc / "update_state").mkdir(parents=True)
    (goc / "update_state" / "current.json").write_text("{}", encoding="utf-8")
    with pytest.raises(bs.LoiBootstrap):
        bs.kiem_truoc(str(goc), str(state), sys.executable)


def test_duong_dan_khong_dau_bat_dung_duong_dan_tuyet_doi(bo):
    """N5: người vận hành hay CHÉP TimClipPro.bat ra Desktop — đường dẫn không dấu thì ghi TUYỆT ĐỐI (chép đi
    đâu cũng chạy); chỉ đường dẫn có dấu mới dùng %~dp0 (khi đó hướng dẫn dùng lối tắt)."""
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    goc, state = bo["tmp"] / "pc2" / "goc", bo["tmp"] / "pc2" / "state"
    kq = bs.bootstrap(str(goc), str(state), **_tham(bo, state))
    bat = open(os.path.join(kq["goc"], "TimClipPro.bat"), encoding="ascii").read()
    assert "%~dp0" not in bat
    assert f'"{os.path.join(kq["goc"], "launcher", "launcher.py")}"' in bat
