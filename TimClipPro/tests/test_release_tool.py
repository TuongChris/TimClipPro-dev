# -*- coding: utf-8 -*-
"""release_tool.py (PC1): gói lấy ĐÚNG cây git, loại test/.bat/updater cũ, chặn bí mật, ZIP tất định,
ký bằng khoá THỬ, xác minh y hệt PC2 rồi cài được qua bộ cập nhật. Không mạng, không phát hành thật.

Cần repo git có commit gốc của nhánh (``TIMCLIP_REPO_GOC`` khi chạy trong bản gương) — không có thì bỏ qua.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

import pytest

import maintenance_gate as mg
import managed_update as mu
import release_tool as rt
from cap_nhat_gia import MoiTruongGia

REPO = os.environ.get("TIMCLIP_REPO_GOC") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = "6dc3f9db4935571bdb7b90f3c902839dc3b998e1"          # baseline Report Policy V2 (lịch sử v2)
M1 = "e341a1c9a14248df43d025edacf8c6304ec1829b"            # lịch sử v3
LOCK = b"streamlit==1.62.0 \\\n    --hash=sha256:" + b"a" * 64 + b"\n"
TAO_LUC = "2026-10-07T00:00:00Z"


def _co_commit(c):
    try:
        subprocess.run(["git", "-C", REPO, "cat-file", "-e", f"{c}^{{commit}}"], check=True,
                       capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


pytestmark = pytest.mark.skipif(not (_co_commit(BASE) and _co_commit(M1)),
                                reason="cần repo git có commit gốc của nhánh")


def _goi(goc, pb="1.0.0"):
    return os.path.join(goc, f"TimClipPro-{pb}-win_amd64.zip")


@pytest.fixture()
def ban_ky(tmp_path):
    out = tmp_path / "phat_hanh"
    goc = rt.build(REPO, M1, "1.0.0", LOCK, str(out), tao_luc=TAO_LUC)
    khoa_rieng, tin_cay = rt.tao_khoa_thu(str(tmp_path / "khoa"))
    rt.sign(goc, khoa_rieng)
    return {"out": str(out), "goc": goc, "tin_cay": tin_cay, "tmp": tmp_path}


def test_build_lay_dung_cay_commit_va_loai_file_khong_phat_hanh(tmp_path):
    goc = rt.build(REPO, BASE, "1.0.0", LOCK, str(tmp_path), tao_luc=TAO_LUC)
    m = mu.doc_manifest(open(os.path.join(goc, mu.TEN_MANIFEST), "rb").read())
    assert m.commit == BASE and m.tree == "469ae2bda66b8523b353f05618c6791c76c0a56d"
    assert m.lich_su == 2 and m.kenh == "stable" and os.path.basename(goc) == "stable-1.0.0"
    with zipfile.ZipFile(_goi(goc)) as z:
        ten = z.namelist()
        assert "TimClipPro/engine.py" in ten and mu.TEN_DAU_RELEASE in ten and mu.TEN_DS_FILE in ten
        assert not [t for t in ten if t.startswith(("TimClipPro/tests/", "TimClipPro/docs/"))
                    or t.lower().endswith(".bat") or "/data/" in t or "/bin/" in t
                    or t.endswith(("cap_nhat.py", "dong_goi.py", "session.log", "CLAUDE.md"))]
        assert z.read("TimClipPro/requirements-lock.txt") == LOCK
        blob = subprocess.run(["git", "-C", REPO, "-c", "core.autocrlf=false", "show",
                               f"{BASE}:TimClipPro/engine.py"], capture_output=True, check=True).stdout
        assert z.read("TimClipPro/engine.py") == blob          # đúng blob git, không phải cây làm việc
        dau = json.loads(z.read(mu.TEN_DAU_RELEASE))
        assert dau["commit"] == BASE and dau["phien_ban"] == "1.0.0"


def test_build_tat_dinh_cung_commit_cung_lock_cung_bam(tmp_path):
    a = rt.build(REPO, BASE, "1.0.0", LOCK, str(tmp_path / "a"), tao_luc=TAO_LUC)
    b = rt.build(REPO, BASE, "1.0.0", LOCK, str(tmp_path / "b"), tao_luc=TAO_LUC)
    assert open(_goi(a), "rb").read() == open(_goi(b), "rb").read()
    assert open(os.path.join(a, mu.TEN_MANIFEST), "rb").read() == \
        open(os.path.join(b, mu.TEN_MANIFEST), "rb").read()


def test_chan_noi_dung_nhay_cam_khong_lo_noi_dung():
    bi_mat = b"https://docs.google.com/spreadsheets/d/" + b"Z" * 30 + b"/edit"
    files = {"TimClipPro/app.py": b"x", "TimClipPro/engine.py": b"y", "TimClipPro/ghi_chu.md": bi_mat}
    with pytest.raises(rt.LoiPhatHanh) as e:
        rt.chon_file_phat_hanh(files)
    assert "ghi_chu.md" in str(e.value) and "ZZZZZ" not in str(e.value)
    khoa = {"TimClipPro/app.py": b"x", "TimClipPro/engine.py": b"y",
            "TimClipPro/cau_hinh_mau.py": b'{"type": "service' + b'_account"}'}
    with pytest.raises(rt.LoiPhatHanh):
        rt.chon_file_phat_hanh(khoa)


def test_ky_xac_minh_roi_cai_qua_bo_cap_nhat_nhu_pc2(ban_ky):
    m = rt.verify(ban_ky["goc"], ban_ky["tin_cay"])
    assert m.phien_ban == "1.0.0" and m.commit == M1 and m.lich_su == 3
    tmp = ban_ky["tmp"]
    cd = mu.CaiDat(goc=str(tmp / "cai dat"), state_root=str(tmp / "state"))
    gia = MoiTruongGia(cd.state_root)
    cn = mu.CapNhat(cd, nguon=mu.NguonThuMuc(ban_ky["out"]),
                    khoa_tin_cay=mu.doc_khoa_tin_cay(ban_ky["tin_cay"]), cong=mg.CongBaoTri(cd.data_dir),
                    tao_moi_truong=gia.tao_moi_truong, kiem_suc_khoe=gia.kiem_suc_khoe,
                    di_chuyen=gia.di_chuyen, sao_luu=gia.sao_luu, phien_ban_db=gia.phien_ban_db,
                    han_cho_ranh_s=0.3, chu_ky_cho_s=0.05)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    assert cn.ap_dung().trang_thai == mu.ACTIVE
    rel = cd.release_dir("1.0.0")
    assert os.path.isfile(os.path.join(rel, "TimClipPro", "engine.py"))
    assert os.path.isfile(os.path.join(rel, mu.TEN_DAU_RELEASE))


def test_verify_tu_choi_goi_bi_sua_va_khoa_la(ban_ky):
    tin_cay_la = rt.tao_khoa_thu(str(ban_ky["tmp"] / "khoa_la"))[1]
    with pytest.raises(mu.TuChoiGoi):
        rt.verify(ban_ky["goc"], tin_cay_la)
    sua = str(ban_ky["tmp"] / "sua" / "stable-1.0.0")
    shutil.copytree(ban_ky["goc"], sua)
    with open(_goi(sua), "r+b") as f:
        f.seek(100)
        b = f.read(1)
        f.seek(100)
        f.write(bytes([b[0] ^ 1]))
    with pytest.raises((rt.LoiPhatHanh, mu.TuChoiGoi)):
        rt.verify(sua, ban_ky["tin_cay"])


def test_publish_chi_in_lenh_khong_chay_gi(ban_ky, monkeypatch, capsys):
    def cam(*a, **k):
        raise AssertionError("publish không được chạy lệnh nào")

    monkeypatch.setattr(rt.subprocess, "run", cam)
    assert rt.main(["publish", "--dir", ban_ky["goc"], "--repo", "chu/du-an"]) == 0
    out = capsys.readouterr().out
    assert "CHƯA PHÁT HÀNH" in out and "gh release create stable-1.0.0" in out and M1 in out


def test_publish_in_lenh_dan_nguyen_van_duoc(ban_ky, capsys):
    """Lệnh in ra phải chạy ĐÚNG khi dán nguyên văn vào Command Prompt/PowerShell: tham số có dấu cách (tiêu
    đề, ghi chú) nằm trong ngoặc kép — nối bằng dấu cách thì «TimClipPro 1.0.0 (Stable)» vỡ thành nhiều đối số."""
    assert rt.main(["publish", "--dir", ban_ky["goc"], "--repo", "chu/du-an"]) == 0
    dong = next(d.strip() for d in capsys.readouterr().out.splitlines()
                if d.strip().startswith("gh release create"))
    assert dong == subprocess.list2cmdline(rt.lenh_publish(ban_ky["goc"], "chu/du-an"))
    assert '--title "TimClipPro 1.0.0 (Stable)"' in dong


def test_lock_tu_moi_truong_da_nghiem_thu(tmp_path):
    van_ban = rt.tao_lock(sys.executable)
    assert re.search(r"^streamlit==\S+$", van_ban, re.M)
    assert not re.search(r"^pip==", van_ban, re.M) and "--hash" not in van_ban
    ver = re.search(r"^streamlit==(\S+)$", van_ban, re.M).group(1)
    (tmp_path / f"streamlit-{ver}-py3-none-any.whl").write_bytes(b"wheel gia")
    co_bam = rt.tao_lock(sys.executable, wheelhouse=str(tmp_path))
    assert re.search(rf"^streamlit=={re.escape(ver)} \\\n    --hash=sha256:[0-9a-f]{{64}}$", co_bam, re.M)
