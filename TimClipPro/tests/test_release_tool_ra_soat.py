# -*- coding: utf-8 -*-
"""Rà soát đối nghịch M3+M4 — release_tool. Mỗi test ĐỎ trên mã trước khi sửa:

* P2-D — «migration tự động an toàn» + «tương thích ngược» không còn mặc định BẬT: phải khai bằng cờ.
* P2-F — gói không có wheel trên PyPI (docopt 0.6.2 chỉ có sdist) đi KÈM release (``TimClipPro/wheels/``), băm
         của đúng file wheel phải có trong lock — PC2 cài ``--only-binary=:all: --require-hashes``.
* P3-10 — lock cũng được quét bí mật; thêm mẫu (dict service account nháy đơn, client secret ``GOCSPX-``,
          refresh token ``1//0``, PEM mã hoá/DSA); file ``.py`` bị luật đóng gói loại → LỖI (không âm thầm thiếu
          module); khoá ký có mật khẩu → hỏi mật khẩu thay vì TypeError.
"""
import hashlib
import json
import os
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import managed_update as mu
import release_tool as rt
from test_release_tool import LOCK, M1, REPO, TAO_LUC, _co_commit

pytestmark = pytest.mark.skipif(not _co_commit(M1), reason="cần repo git có commit gốc của nhánh")


def _manifest(goc):
    return json.load(open(os.path.join(goc, mu.TEN_MANIFEST), encoding="utf-8"))


# ---------------------------------------------------------------- D: cờ migration

def test_build_mac_dinh_khong_khai_migration_tu_dong(tmp_path):
    md = _manifest(rt.build(REPO, M1, "1.0.0", LOCK, str(tmp_path), tao_luc=TAO_LUC))
    assert md["migration"]["tu_dong_an_toan"] is False and md["du_lieu"]["tuong_thich_nguoc"] is False


def test_build_cli_khai_co_migration_tuong_minh(tmp_path):
    lock = tmp_path / "lock.txt"
    lock.write_bytes(LOCK)
    out = tmp_path / "ra"
    assert rt.main(["build", "--repo", REPO, "--commit", M1, "--phien-ban", "1.0.0", "--lock", str(lock),
                    "--out", str(out), "--tu-dong-an-toan", "--tuong-thich-nguoc"]) == 0
    md = _manifest(os.path.join(str(out), "stable-1.0.0"))
    assert md["migration"]["tu_dong_an_toan"] is True and md["du_lieu"]["tuong_thich_nguoc"] is True
    # Tự động an toàn mà KHÔNG tương thích ngược: chính sách PC2 cấm → từ chối ngay lúc build.
    assert rt.main(["build", "--repo", REPO, "--commit", M1, "--phien-ban", "1.0.1", "--lock", str(lock),
                    "--out", str(out), "--tu-dong-an-toan"]) == 1


# ---------------------------------------------------------------- F: wheel kèm release

def _wheel(tmp_path, ten="docopt-0.6.2-py2.py3-none-any.whl"):
    p = tmp_path / ten
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("docopt.py", "# docopt (giả cho kiểm thử)\n")
    return str(p), hashlib.sha256(p.read_bytes()).hexdigest()


def test_wheel_kem_vao_release_duoc_ky_va_kiem(tmp_path):
    whl, bam = _wheel(tmp_path)
    lock = LOCK + f"docopt==0.6.2 \\\n    --hash=sha256:{bam}\n".encode()
    goc = rt.build(REPO, M1, "1.0.0", lock, str(tmp_path / "ra"), tao_luc=TAO_LUC, wheel_kem=[whl])
    khoa_rieng, tin_cay = rt.tao_khoa_thu(str(tmp_path / "khoa"))
    rt.sign(goc, khoa_rieng)
    rt.verify(goc, tin_cay)
    goi = os.path.join(goc, "TimClipPro-1.0.0-win_amd64.zip")
    with zipfile.ZipFile(goi) as z:
        ten = "TimClipPro/wheels/docopt-0.6.2-py2.py3-none-any.whl"
        assert z.read(ten) == open(whl, "rb").read()
        ds = json.loads(z.read(mu.TEN_DS_FILE))
    assert any(f["path"] == ten for f in ds["files"])


def test_wheel_kem_khong_co_bam_trong_lock_bi_tu_choi(tmp_path):
    whl, _ = _wheel(tmp_path)
    with pytest.raises(rt.LoiPhatHanh):
        rt.build(REPO, M1, "1.0.0", LOCK, str(tmp_path / "ra"), tao_luc=TAO_LUC, wheel_kem=[whl])


def test_wheel_kem_ten_sai_bi_tu_choi(tmp_path):
    whl, bam = _wheel(tmp_path, "docopt.zip")
    lock = LOCK + f"docopt==0.6.2 \\\n    --hash=sha256:{bam}\n".encode()
    with pytest.raises(rt.LoiPhatHanh):
        rt.build(REPO, M1, "1.0.0", lock, str(tmp_path / "ra"), tao_luc=TAO_LUC, wheel_kem=[whl])


# ---------------------------------------------------------------- P3-10: quét bí mật

def test_lock_cung_bi_quet_bi_mat(tmp_path):
    lock = LOCK + b"# ghp_" + b"A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8" + b"\n"
    with pytest.raises(rt.LoiPhatHanh):
        rt.build(REPO, M1, "1.0.0", lock, str(tmp_path / "ra"), tao_luc=TAO_LUC)


@pytest.mark.parametrize("bi_mat", [
    b"KHOA = {'type': 'service" + b"_account', 'project_id': 'x'}",
    b"CLIENT = 'GOCSPX-" + b"Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9'",
    b"TOKEN = '1//0" + b"gAbCdEfGhIjKlMnOpQrStUvWxYz0123456789'",
    b"-----BEGIN ENCRYPTED " + b"PRIVATE KEY-----\nMIIE\n",
    b"-----BEGIN DSA " + b"PRIVATE KEY-----\nMIIE\n",
], ids=["sa_nhay_don", "client_secret", "refresh_token", "pem_ma_hoa", "pem_dsa"])
def test_mau_bi_mat_bo_sung(bi_mat):
    files = {"TimClipPro/app.py": b"# app\n", "TimClipPro/engine.py": b"# engine\n",
             "TimClipPro/cau_hinh_mau.py": bi_mat}
    with pytest.raises(rt.LoiPhatHanh):
        rt.chon_file_phat_hanh(files)


def test_file_py_bi_luat_dong_goi_loai_thi_bao_loi(tmp_path):
    files = {"TimClipPro/app.py": b"# app\n", "TimClipPro/engine.py": b"# engine\n",
             "TimClipPro/_tam/tien_ich.py": b"# module that\n"}
    with pytest.raises(rt.LoiPhatHanh) as e:
        rt.chon_file_phat_hanh(files)
    assert "_tam/tien_ich.py" in str(e.value)


def test_sign_khoa_co_mat_khau(tmp_path):
    goc = rt.build(REPO, M1, "1.0.0", LOCK, str(tmp_path / "ra"), tao_luc=TAO_LUC)
    k = Ed25519PrivateKey.generate()
    p = tmp_path / "khoa_ma_hoa.pem"
    p.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.BestAvailableEncryption(b"mat-khau-thu")))
    with pytest.raises(rt.LoiPhatHanh):
        rt.sign(goc, str(p))
    rt.sign(goc, str(p), mat_khau=b"mat-khau-thu")
    assert os.path.isfile(os.path.join(goc, mu.TEN_CHU_KY))
