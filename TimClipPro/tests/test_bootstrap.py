# -*- coding: utf-8 -*-
"""bootstrap.py — dựng cài đặt managed cho PC2: kiểm đường dẫn TRƯỚC khi ghi, định danh mới mỗi máy, launcher
ngoài release, khoá tin cậy, .bat gọi launcher bằng đường dẫn tuyệt đối, XML lịch Windows CHỈ để xem (không
đăng ký), cài bản đầu qua đúng bộ cập nhật. Runtime/health giả (``cap_nhat_gia``); không mạng."""
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

import bootstrap as bs
import managed_update as mu
from cap_nhat_gia import KhoaThu, MoiTruongGia, phat_hanh

KIT = os.path.dirname(os.path.abspath(mu.__file__))
NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


@pytest.fixture()
def bo(tmp_path):
    khoa = KhoaThu()
    tin_cay = khoa.ghi_tin_cay(str(tmp_path / "kit" / "trusted_keys.json"))
    nguon = tmp_path / "nguon"
    nguon.mkdir()
    return {"khoa": khoa, "tin_cay": tin_cay, "nguon": str(nguon), "tmp": tmp_path}


def _bootstrap(bo, ten="pc2", **kw):
    goc, state = bo["tmp"] / ten / "Cai Dat", bo["tmp"] / ten / "State"
    gia = MoiTruongGia(str(state))
    tham = dict(kit_dir=KIT, python_goc=sys.executable, tin_cay=bo["tin_cay"],
                nguon={"loai": "thu_muc", "duong_dan": bo["nguon"]}, py_launcher=sys.executable,
                tao_moi_truong=gia.tao_moi_truong, kiem_suc_khoe=gia.kiem_suc_khoe, di_chuyen=gia.di_chuyen,
                sao_luu=gia.sao_luu, phien_ban_db=gia.phien_ban_db)
    tham.update(kw)
    return bs.bootstrap(str(goc), str(state), **tham)


def test_bootstrap_dung_cai_dat_rieng_va_cai_ban_dau(bo, monkeypatch):
    def cam(args, *a, **k):
        assert "schtasks" not in " ".join(map(str, args)).lower(), "không được đăng ký lịch thật"
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", cam)
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    kq = _bootstrap(bo)
    assert kq["cai_dat"]["trang_thai"] == mu.ACTIVE
    goc, state = kq["goc"], kq["state"]
    for f in bs.FILE_LAUNCHER + ("launcher.json", "trusted_keys.json"):
        assert os.path.isfile(os.path.join(goc, "launcher", f)), f
    cfg = json.load(open(os.path.join(goc, "launcher", "launcher.json"), encoding="utf-8"))
    assert cfg["state_root"] == state and cfg["tu_ap_dung"] is False
    dd = json.load(open(os.path.join(state, "installation.json"), encoding="utf-8"))
    assert dd["installation_id"] == kq["installation_id"] and len(dd["installation_id"]) == 32
    bat = open(os.path.join(goc, "TimClipPro.bat"), encoding="ascii").read()
    assert f'"{sys.executable}" "{os.path.join(goc, "launcher", "launcher.py")}" app' in bat
    assert "cap_nhat.py" not in bat and "git" not in bat.lower()
    for p in kq["lich"]:
        goc_xml = ET.fromstring(open(p, encoding="utf-16").read().split("?>", 1)[1])
        assert goc_xml.find(".//t:MultipleInstancesPolicy", NS).text == "IgnoreNew"
        assert goc_xml.find(".//t:RunLevel", NS).text == "LeastPrivilege"
        assert goc_xml.find(".//t:WorkingDirectory", NS).text == state
        assert os.path.isabs(goc_xml.find(".//t:Command", NS).text)
    assert mu.doc_json(os.path.join(goc, "update_state", "current.json"))["phien_ban"] == "1.0.0"


def test_hai_lan_bootstrap_hai_dinh_danh_khac_nhau(bo):
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    a, b = _bootstrap(bo, "pc_a"), _bootstrap(bo, "pc_b")
    assert a["installation_id"] != b["installation_id"]


@pytest.mark.parametrize("hong", ["onedrive", "trung", "git", "dinh_danh", "python"])
def test_kiem_truoc_tu_choi_va_chua_ghi_gi(bo, monkeypatch, hong):
    goc, state, py = bo["tmp"] / "x" / "goc", bo["tmp"] / "x" / "state", sys.executable
    if hong == "onedrive":
        state = bo["tmp"] / "OneDrive" / "state"
    elif hong == "trung":
        state = goc
    elif hong == "git":
        (goc / ".git").mkdir(parents=True)
    elif hong == "dinh_danh":
        state.mkdir(parents=True)
        (state / "installation.json").write_text("{}", encoding="utf-8")
    else:
        py = str(bo["tmp"] / "khong_co_python.exe")
    truoc = sorted(str(p) for p in bo["tmp"].rglob("*"))
    with pytest.raises(bs.LoiBootstrap):
        bs.bootstrap(str(goc), str(state), kit_dir=KIT, python_goc=py, tin_cay=bo["tin_cay"],
                     nguon={"loai": "thu_muc", "duong_dan": bo["nguon"]}, py_launcher=sys.executable)
    assert sorted(str(p) for p in bo["tmp"].rglob("*")) == truoc


def test_moi_truong_launcher_chi_cai_lock_co_bam(tmp_path):
    kit = tmp_path / "kit"
    kit.mkdir()
    (kit / "launcher-lock.txt").write_text("cryptography==50.0.0\n", encoding="utf-8")
    with pytest.raises(bs.LoiBootstrap):
        bs.tao_moi_truong_launcher(str(tmp_path / "goc"), sys.executable, str(kit),
                                   chay=lambda *a, **k: pytest.fail("không được chạy"))
    (kit / "launcher-lock.txt").write_text(
        "cryptography==50.0.0 \\\n    --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    goi = []
    py = bs.tao_moi_truong_launcher(str(tmp_path / "goc"), sys.executable, str(kit),
                                    chay=lambda args, **k: goi.append(args))
    assert py.endswith(os.path.join("launcher", "env", "Scripts", "python.exe"))
    assert goi[0][1:3] == ["-m", "venv"] and "--require-hashes" in goi[1]


def test_launcher_da_chep_chay_doc_lap_chi_voi_file_cua_no(bo):
    """Thư mục launcher sau bootstrap tự đủ: `doctor` chạy được bằng tiến trình RIÊNG chỉ với các file đã
    chép (không phụ thuộc thư mục mã của release hay của PC1)."""
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    kq = _bootstrap(bo)
    lc = os.path.join(kq["goc"], "launcher")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
    env["PYTHONPATH"] = os.pathsep.join(p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                                        if p and "guard" in p.lower())
    p = subprocess.run([sys.executable, "-I", "-c",
                        "import sys; sys.path.insert(0, sys.argv[1]); import launcher; "
                        "raise SystemExit(launcher.main(['doctor'], goc=sys.argv[2]))", lc, kq["goc"]],
                       capture_output=True, text=True, encoding="utf-8", timeout=120, cwd=lc, env=env)
    assert "launcher.json" in p.stdout and "Bản đang kích hoạt" in p.stdout, p.stdout + p.stderr
