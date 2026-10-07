# -*- coding: utf-8 -*-
"""Rà soát đối nghịch M3+M4 — launcher (phụ thuộc production của bộ cập nhật + chạy app). Mỗi test ĐỎ trên mã
trước khi sửa:

* B   — health check timeout / không chạy được = KHÔNG ĐẠT (không thoát khỏi updater); lock chưa băm = từ chối
        gói (cách ly); lỗi SQLite khi sao lưu/đọc phiên bản lịch sử → ``LoiCapNhat``; khôi phục lỗi lạ không
        chặn mở app.
* D   — máy mới chưa có ``lichsu.db`` → phiên bản ``None`` (không phải migration).
* F   — wheel kèm trong release (vd. docopt chỉ có sdist trên PyPI) được dùng qua ``--find-links``.
* P3  — kết quả health đọc theo DÒNG ĐÁNH DẤU + cwd ngoài release; bỏ biến PYTHON* nguy hiểm; ``-P`` cho
        ``-m``; Ctrl+C ở cửa sổ launcher không giết app; doctor so con trỏ với manifest; ``update bo-cach-ly``.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import types

import pytest

import launcher
import managed_update as mu
from cap_nhat_gia import KhoaThu, MoiTruongGia, phat_hanh
from test_launcher import _cai_ban


@pytest.fixture()
def cai(tmp_path, monkeypatch):
    """Cài đặt giả (như ``test_launcher.cai``): launcher.json + khoá tin cậy + định danh, runtime/health giả."""
    import runtime_paths

    khoa = KhoaThu()
    goc, state, nguon = str(tmp_path / "Cai Dat TimClip"), str(tmp_path / "state"), str(tmp_path / "nguon")
    os.makedirs(nguon)
    os.makedirs(os.path.join(goc, "launcher"))
    khoa.ghi_tin_cay(os.path.join(goc, "launcher", launcher.TEN_KHOA_TIN_CAY))
    with open(os.path.join(goc, "launcher", launcher.TEN_CAU_HINH), "w", encoding="utf-8") as f:
        json.dump({"state_root": state, "nguon": {"loai": "thu_muc", "duong_dan": nguon},
                   "python_goc": "", "han_cho_ranh_s": 0.3}, f)
    gia = MoiTruongGia(state)
    runtime_paths.tao_dinh_danh(state, installation_root=goc)
    thay = dict(tao_moi_truong=gia.tao_moi_truong, kiem_suc_khoe=gia.kiem_suc_khoe,
                di_chuyen=gia.di_chuyen, sao_luu=gia.sao_luu, phien_ban_db=gia.phien_ban_db)
    goi = []

    def chay(argv, **kw):
        goi.append((argv, kw))
        return 0

    def main(*doi_so, **kw):
        return launcher.main(list(doi_so), goc=goc, chay=chay, **{**thay, **kw})

    return {"goc": goc, "state": state, "nguon": nguon, "khoa": khoa, "gia": gia, "goi": goi,
            "main": main, "thay": thay}


def _cd(tmp_path):
    return mu.CaiDat(goc=str(tmp_path / "goc"), state_root=str(tmp_path / "state"))


def _rel(tmp_path):
    rel = tmp_path / "goc" / "releases" / "1.0.0"
    (rel / "TimClipPro").mkdir(parents=True)
    return str(rel)


# ---------------------------------------------------------------- B: health check

def test_chay_health_timeout_la_khong_dat(tmp_path, monkeypatch):
    def run(*a, **k):
        raise subprocess.TimeoutExpired(a[0], k.get("timeout"))

    monkeypatch.setattr(launcher.subprocess, "run", run)
    ok, kq = launcher._chay_health(_cd(tmp_path), _rel(tmp_path), str(tmp_path / "rt"), ["kiem"], 1.0)
    assert ok is False and "TimeoutExpired" in " ".join(kq["loi"])


def test_chay_health_khong_chay_duoc_python_la_khong_dat(tmp_path, monkeypatch):
    def run(*a, **k):
        raise FileNotFoundError("python.exe")

    monkeypatch.setattr(launcher.subprocess, "run", run)
    ok, kq = launcher._chay_health(_cd(tmp_path), _rel(tmp_path), str(tmp_path / "rt"), ["kiem"], 1.0)
    assert ok is False and "FileNotFoundError" in " ".join(kq["loi"])


def test_chay_health_doc_dong_danh_dau_va_cwd_ngoai_release(tmp_path, monkeypatch):
    goi = {}

    def run(argv, **k):
        goi.update(k)
        return types.SimpleNamespace(returncode=0, stderr="", stdout=(
            "khởi động...\n" + launcher.DAU_KET_QUA_HEALTH + ' {"ok": true}\n'
            "Exception ignored in atexit callback (thư viện in khi thoát)\n"))

    monkeypatch.setattr(launcher.subprocess, "run", run)
    rel = _rel(tmp_path)
    ok, _ = launcher._chay_health(_cd(tmp_path), rel, str(tmp_path / "rt"), ["kiem"], 1.0)
    assert ok is True
    cwd = os.path.normcase(os.path.abspath(goi["cwd"]))
    assert not cwd.startswith(os.path.normcase(os.path.abspath(rel)))      # không ghi gì vào cây đã ký


def test_health_check_in_dong_danh_dau(tmp_path):
    import health_check

    assert health_check.DAU_KET_QUA == launcher.DAU_KET_QUA_HEALTH       # hợp đồng launcher ↔ release

    p = subprocess.run([sys.executable, health_check.__file__, "kiem", "--data-dir", str(tmp_path / "data"),
                        "--che-do", "staging"], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=300)
    assert any(d.startswith(launcher.DAU_KET_QUA_HEALTH + " ") for d in p.stdout.splitlines()), p.stdout[-500:]


# ---------------------------------------------------------------- B/F: tạo runtime

def _m(lock: bytes):
    return types.SimpleNamespace(lock_sha256=hashlib.sha256(lock).hexdigest(), phien_ban="1.0.0")


def _lock(rel, du: bytes):
    with open(os.path.join(rel, "TimClipPro", "requirements-lock.txt"), "wb") as f:
        f.write(du)


def test_lock_chua_bam_la_tu_choi_goi_de_cach_ly(tmp_path, monkeypatch):
    rel = _rel(tmp_path)
    du = b"docopt==0.6.2\n"
    _lock(rel, du)
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: pytest.fail("không được chạy pip"))
    with pytest.raises(mu.TuChoiGoi) as e:
        launcher.tao_moi_truong_pip(sys.executable)(_m(du), rel, str(tmp_path / "rt"))
    assert e.value.ma == "lock_chua_bam"


def test_tao_runtime_dung_wheel_kem_release_va_khong_dat_cwd_vao_sys_path(tmp_path, monkeypatch):
    rel = _rel(tmp_path)
    du = b"docopt==0.6.2 \\\n    --hash=sha256:" + b"e" * 64 + b"\n"
    _lock(rel, du)
    os.makedirs(os.path.join(rel, "TimClipPro", "wheels"))
    goi = []
    monkeypatch.setattr(launcher.subprocess, "run", lambda argv, **k: goi.append(argv))
    launcher.tao_moi_truong_pip(sys.executable)(_m(du), rel, str(tmp_path / "rt"))
    venv, pip = goi[0], goi[1]
    assert venv[1:3] == ["-P", "-m"] and pip[1:3] == ["-P", "-m"]
    i = pip.index("--find-links")
    assert pip[i + 1] == os.path.join(rel, "TimClipPro", "wheels")
    assert "--require-hashes" in pip and "--only-binary=:all:" in pip


# ---------------------------------------------------------------- B/D: SQLite

def test_phien_ban_db_may_moi_la_none(tmp_path):
    assert launcher.phien_ban_db(_cd(tmp_path))() is None


def _db_hong(cd):
    os.makedirs(cd.data_dir, exist_ok=True)
    with open(os.path.join(cd.data_dir, "lichsu.db"), "wb") as f:
        f.write(b"day khong phai sqlite" * 100)


def test_phien_ban_db_hong_bao_loi_cap_nhat(tmp_path):
    cd = _cd(tmp_path)
    _db_hong(cd)
    with pytest.raises(mu.LoiCapNhat):
        launcher.phien_ban_db(cd)()


def test_sao_luu_db_hong_bao_loi_cap_nhat(tmp_path):
    cd = _cd(tmp_path)
    _db_hong(cd)
    with pytest.raises(mu.LoiCapNhat):
        launcher.sao_luu_sqlite(cd)(types.SimpleNamespace(phien_ban="1.1.0"))


def test_sao_luu_db_that_van_chay(tmp_path):
    cd = _cd(tmp_path)
    os.makedirs(cd.data_dir)
    con = sqlite3.connect(os.path.join(cd.data_dir, "lichsu.db"))
    con.execute("CREATE TABLE t(x)")
    con.commit()
    con.close()
    dich = launcher.sao_luu_sqlite(cd)(types.SimpleNamespace(phien_ban="1.1.0"))
    assert os.path.isfile(os.path.join(dich, "lichsu.db"))


# ---------------------------------------------------------------- P3: môi trường tiến trình con

def test_moi_truong_con_bo_bien_python_nguy_hiem(tmp_path):
    env = launcher.moi_truong_con(_cd(tmp_path), {"phien_ban": "1.0.0"}, environ={
        "PATH": "x", "PYTHONINSPECT": "1", "PYTHONWARNINGS": "error", "PYTHONOPTIMIZE": "2",
        "PYTHONSTARTUP": "C:/x.py", "PYTHONBREAKPOINT": "pdb.set_trace", "PYTHONDEVMODE": "1",
        "PYTHONUSERBASE": "C:/u", "PYTHONEXECUTABLE": "C:/p.exe"})
    for k in ("PYTHONINSPECT", "PYTHONWARNINGS", "PYTHONOPTIMIZE", "PYTHONSTARTUP", "PYTHONBREAKPOINT",
              "PYTHONDEVMODE", "PYTHONUSERBASE", "PYTHONEXECUTABLE"):
        assert k not in env, k
    assert env["PATH"].endswith("x")


def test_lenh_app_khong_dat_cwd_vao_sys_path():
    argv = launcher.lenh_app({"runtime": "C:/rt", "release": "C:/rel"})
    assert argv[1:4] == ["-P", "-m", "streamlit"]


def test_ctrl_c_o_cua_so_launcher_khong_giet_ung_dung(monkeypatch):
    """Ctrl+C của cửa sổ console tới CẢ app (tự tắt êm, người gửi Sheets chờ việc đang bay) — launcher chỉ
    chờ tiếp, không ``kill`` (``subprocess.call`` giết con sau 0,25 s → việc đang gửi thành KHÔNG RÕ)."""
    class PopenGia:
        def __init__(self, argv, **kw):
            self.lan, self.da_giet = 0, False

        def wait(self):
            self.lan += 1
            if self.lan == 1:
                raise KeyboardInterrupt
            return 0

        def kill(self):
            self.da_giet = True

    tao = []
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda argv, **kw: tao.append(PopenGia(argv, **kw))
                        or tao[-1])
    assert launcher._chay_cho_con(["python", "app.py"], env={}) == 0
    assert tao[0].lan == 2 and not tao[0].da_giet
    import inspect

    assert inspect.signature(launcher.main).parameters["chay"].default is launcher._chay_cho_con


# ---------------------------------------------------------------- P3: doctor / bỏ cách ly / khôi phục

def test_doctor_bao_loi_khi_con_tro_khong_khop_manifest_da_ky(cai, capsys):
    _cai_ban(cai, "1.0.0")
    cd = mu.CaiDat(cai["goc"], cai["state"])
    cur = mu.doc_json(cd.file_trang_thai("current.json"))
    cur["manifest_sha256"] = "0" * 64
    mu.ghi_json_nguyen_tu(cd.file_trang_thai("current.json"), cur)
    capsys.readouterr()
    assert cai["main"]("doctor") == 1
    dong = next(d for d in capsys.readouterr().out.splitlines() if "Bản đang kích hoạt" in d)
    assert dong.startswith(launcher.LOI)


def test_update_bo_cach_ly_qua_launcher(cai, capsys):
    _cai_ban(cai, "1.0.0")
    phat_hanh(cai["nguon"], "1.1.0", cai["khoa"])
    cai["gia"].suc_khoe["staging"] = False
    assert cai["main"]("update", "prepare") == 1
    cd = mu.CaiDat(cai["goc"], cai["state"])
    assert "1.1.0" in mu.doc_json(cd.file_trang_thai("quarantine.json"))
    cai["gia"].suc_khoe["staging"] = True
    assert cai["main"]("update", "bo-cach-ly", "1.1.0") == 0
    assert "1.1.0" not in mu.doc_json(cd.file_trang_thai("quarantine.json"))
    assert cai["main"]("update", "bo-cach-ly", "9.9.9") == 1
    assert cai["main"]("update", "prepare") == 0


def test_khoi_phuc_loi_la_khong_chan_mo_app(cai, monkeypatch, capsys):
    _cai_ban(cai, "1.0.0")

    def hong(self):
        raise RuntimeError("lỗi lạ trong khôi phục")

    monkeypatch.setattr(mu.CapNhat, "phuc_hoi", hong)
    assert cai["main"]("app") == 0
    assert "CẢNH BÁO" in capsys.readouterr().err


def test_mo_app_khi_bo_cap_nhat_khong_dung_duoc_van_chay_ban_dang_kich_hoat(cai, capsys):
    """P3-6: khoá tin cậy hỏng / thiếu thư viện / chưa cấu hình nguồn chỉ chặn CẬP NHẬT, không chặn mở app."""
    _cai_ban(cai, "1.0.0")
    with open(os.path.join(cai["goc"], "launcher", launcher.TEN_KHOA_TIN_CAY), "w", encoding="utf-8") as f:
        f.write("{hỏng")
    capsys.readouterr()
    assert cai["main"]("app") == 0
    (argv, _), = cai["goi"]
    assert os.path.join("releases", "1.0.0") in argv[5]
    assert "CẢNH BÁO" in capsys.readouterr().err
    assert cai["main"]("update", "prepare") == 1                   # cập nhật thì vẫn bị chặn


def test_mo_app_khi_bo_cap_nhat_hong_ma_cap_nhat_dang_do_thi_tu_choi(cai, capsys):
    _cai_ban(cai, "1.0.0")
    phat_hanh(cai["nguon"], "1.1.0", cai["khoa"])

    def chet(ten):
        if ten == mu.HEALTHCHECK:
            raise mu.MatDien(ten)

    assert cai["main"]("update", "prepare") == 0
    with pytest.raises(mu.MatDien):
        cai["main"]("update", "apply", diem_dung=chet)
    with open(os.path.join(cai["goc"], "launcher", launcher.TEN_KHOA_TIN_CAY), "w", encoding="utf-8") as f:
        f.write("{hỏng")
    assert cai["main"]("app") == 1 and cai["goi"] == []


# ---------------------------------------------------------------- rà soát lại 908d946 (N2, N3, N7)

def test_khoi_phuc_loi_giua_luc_kich_hoat_thi_khong_mo_ban_chua_kiem(cai, capsys):
    """N2: một updater khác đang chạy (BAN) / khôi phục lỗi mà nhật ký đang giữa lúc kích hoạt → KHÔNG mở bản
    chưa qua health; báo đợi rồi mở lại."""
    from khoa import KhoaTienTrinh

    _cai_ban(cai, "1.0.0")
    phat_hanh(cai["nguon"], "1.1.0", cai["khoa"])

    def chet(ten):
        if ten == mu.HEALTHCHECK:
            raise mu.MatDien(ten)

    assert cai["main"]("update", "prepare") == 0
    with pytest.raises(mu.MatDien):
        cai["main"]("update", "apply", diem_dung=chet)
    with KhoaTienTrinh(os.path.join(cai["goc"], "update_state", "updater.lock"), "updater khác"):
        assert cai["main"]("app") == 1
    assert cai["goi"] == []


def test_doctor_dang_cho_ranh_la_canh_bao(cai, capsys):
    _cai_ban(cai, "1.0.0")
    mu.NhatKy(mu.CaiDat(cai["goc"], cai["state"])).ghi(mu.WAITING_IDLE)
    capsys.readouterr()
    cai["main"]("doctor")
    dong = next(d for d in capsys.readouterr().out.splitlines() if "Nhật ký cập nhật" in d)
    assert dong.startswith(launcher.CANH_BAO)


def test_health_khong_chay_duoc_bao_loi_tam_thoi(tmp_path, monkeypatch):
    def run(*a, **k):
        raise subprocess.TimeoutExpired(a[0], k.get("timeout"))

    monkeypatch.setattr(launcher.subprocess, "run", run)
    ok, kq = launcher._chay_health(_cd(tmp_path), _rel(tmp_path), str(tmp_path / "rt"), ["kiem"], 1.0)
    assert ok is False and kq.get("tam_thoi") is True
    monkeypatch.setattr(launcher, "_chay_health", lambda *a, **k: (False, {"loi": ["x"], "tam_thoi": True}))
    with pytest.raises(mu.LoiTamThoi):
        launcher.kiem_suc_khoe_tien_trinh(_cd(tmp_path))(None, "", "", "staging")
    with pytest.raises(mu.LoiTamThoi):
        launcher.di_chuyen_tien_trinh(_cd(tmp_path))(None, "", "")
    monkeypatch.setattr(launcher, "_chay_health", lambda *a, **k: (False, {"loi": ["migration hỏng"]}))
    with pytest.raises(mu.LoiCapNhat) as e:
        launcher.di_chuyen_tien_trinh(_cd(tmp_path))(None, "", "")
    assert not isinstance(e.value, mu.LoiTamThoi)


def test_health_check_phan_loai_csdl_bi_khoa_la_tam_thoi():
    import health_check

    assert health_check.la_loi_tam_thoi(sqlite3.OperationalError("database is locked")) is True
    assert health_check.la_loi_tam_thoi(sqlite3.OperationalError("no such table: jobs")) is False
    assert health_check.la_loi_tam_thoi(ValueError("x")) is False


# ---------------------------------------------------------------- P3 sau lượt kiểm 34a0e80

def test_nhat_ky_hong_ma_con_tro_khac_ban_da_chot_thi_khong_mo(cai, capsys):
    """Nhật ký HỎNG — không biết có đang giữa lúc kích hoạt không: chỉ mở khi con trỏ hiện tại TRÙNG bản đã
    chốt (last_good); khác thì từ chối (có thể là bản chưa qua health)."""
    _cai_ban(cai, "1.0.0")
    phat_hanh(cai["nguon"], "1.1.0", cai["khoa"])

    def chet(ten):
        if ten == mu.HEALTHCHECK:
            raise mu.MatDien(ten)

    assert cai["main"]("update", "prepare") == 0
    with pytest.raises(mu.MatDien):
        cai["main"]("update", "apply", diem_dung=chet)
    with open(os.path.join(cai["goc"], "update_state", "journal.json"), "w", encoding="utf-8") as f:
        f.write("{hỏng")
    assert cai["main"]("app") == 1 and cai["goi"] == []


def test_nhat_ky_hong_ma_con_tro_trung_ban_da_chot_van_mo(cai, capsys):
    _cai_ban(cai, "1.0.0")
    with open(os.path.join(cai["goc"], "update_state", "journal.json"), "w", encoding="utf-8") as f:
        f.write("{hỏng")
    capsys.readouterr()
    assert cai["main"]("app") == 0
    assert "CẢNH BÁO" in capsys.readouterr().err


def test_update_recover_in_trang_thai_ro_rang(cai, capsys):
    _cai_ban(cai, "1.0.0")
    capsys.readouterr()
    assert cai["main"]("update", "recover") == 0
    out = capsys.readouterr().out
    assert "trạng thái" in out and "ACTIVE" in out


def test_chua_co_ban_kich_hoat_huong_dan_chay_capnhat(cai, capsys):
    """Bootstrap xong mà bản đầu chưa cài được (hoặc lỗi tạm thời lúc cài lần đầu): chạy lại bootstrap bị TỪ
    CHỐI — hướng dẫn đúng là CapNhat.bat."""
    capsys.readouterr()
    assert cai["main"]("app") == 1
    assert "CapNhat.bat" in capsys.readouterr().err


def test_health_tam_thoi_chi_khi_csdl_khoa_la_loi_duy_nhat(tmp_path, monkeypatch):
    """Lần health có lỗi TẤT ĐỊNH (vd. engine/thư viện hỏng) kèm CSDL bị khoá không được coi là tạm thời
    (không được 3 lượt thử)."""
    import health_check as hc

    def khoa(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(hc, "_doc_db_that", khoa)
    monkeypatch.setattr(hc, "_engine_tam", lambda: {"ok": True})
    kq = hc.kiem(str(tmp_path / "data"), "staging")
    assert kq["ok"] is False and kq.get("tam_thoi") is True, kq["loi"]

    def hong():
        raise RuntimeError("thư viện hỏng (giả)")

    monkeypatch.setattr(hc, "_engine_tam", hong)
    kq = hc.kiem(str(tmp_path / "data"), "staging")
    assert kq["ok"] is False and not kq.get("tam_thoi"), kq["loi"]
