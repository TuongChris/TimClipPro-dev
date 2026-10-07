# -*- coding: utf-8 -*-
"""HAI CÀI ĐẶT GIẢ LẬP trên một máy (brief §17 «Hai PC giả lập») — end-to-end với mã THẬT của nhánh:

đóng gói bằng ``release_tool`` (đường lọc + quét bí mật + ZIP tất định thật) → ký khoá THỬ → bootstrap hai
installation/state RIÊNG → runtime venv THẬT tạo tại đường dẫn cuối (chế độ thử: ``.pth`` dùng lại
site-packages đã nghiệm thu, chỉ đọc, kèm rào chắn) → health check THẬT (tiến trình con, chặn mạng) →
``launcher cli`` chạy ``cli.py`` của release ở chế độ managed → cập nhật CHỈ máy B.

Không mạng, không Google/YouTube. Đây là hai root/tiến trình trên PC1 — KHÔNG phải nghiệm thu PC2 vật lý.
"""
import hashlib
import os
import sqlite3
import subprocess
import sys

import pytest

import bootstrap as bs
import managed_update as mu
import release_tool as rt
import sheet_destinations as sd

pytestmark = pytest.mark.slow

MA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BO_QUA = {"__pycache__", "data", "ketqua", ".venv", "bin", ".pytest_cache", ".ruff_cache", "tests"}


def _files_ma_dang_test() -> dict:
    files = {}
    for goc, dirs, fs in os.walk(MA):
        dirs[:] = [d for d in dirs if d not in _BO_QUA]
        for f in fs:
            p = os.path.join(goc, f)
            rel = os.path.relpath(p, os.path.dirname(MA)).replace(os.sep, "/")
            with open(p, "rb") as fh:
                files[rel] = fh.read()
    return files


def _tao_runtime_thu(m, rel, rt_dir):
    """CHẾ ĐỘ THỬ (không pip, không mạng): venv thật tại đường dẫn cuối; ``.pth`` trỏ rào chắn + site-packages
    của runtime đã nghiệm thu (chỉ đọc)."""
    subprocess.run([sys._base_executable, "-m", "venv", "--without-pip", rt_dir], check=True, timeout=300)
    them = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    with open(os.path.join(rt_dir, "Lib", "site-packages", "_timclip_thu.pth"), "w", encoding="utf-8") as f:
        f.write("\n".join([*them, os.path.join(sys.prefix, "Lib", "site-packages")]) + "\n")


def _phat_hanh(nguon, khoa_rieng, files, pb):
    goc = rt.dong_goi_tu_files(files, "a" * 40, "b" * 40, pb, b"# lock thu (runtime tai dung)\n",
                               str(nguon), tao_luc="2026-10-08T00:00:00Z")
    rt.sign(goc, khoa_rieng)


def _bam_cay(*thu_muc) -> str:
    h = hashlib.sha256()
    for goc_tm in thu_muc:
        for goc, dirs, fs in os.walk(goc_tm):
            dirs.sort()
            for f in sorted(fs):
                p = os.path.join(goc, f)
                h.update(p.encode())
                with open(p, "rb") as fh:
                    h.update(fh.read())
    return h.hexdigest()


def test_hai_cai_dat_doc_lap_cap_nhat_mot_may_khong_dong_toi_may_kia(tmp_path):
    import launcher

    khoa_rieng, tin_cay = rt.tao_khoa_thu(str(tmp_path / "khoa"))
    nguon = tmp_path / "nguon"
    files = _files_ma_dang_test()
    _phat_hanh(nguon, khoa_rieng, files, "1.0.0")
    may = {}
    for ten in ("pc_a", "pc_b"):
        kq = bs.bootstrap(str(tmp_path / ten / "Cai Dat"), str(tmp_path / ten / "State"), kit_dir=MA,
                          python_goc=sys._base_executable, tin_cay=tin_cay,
                          nguon={"loai": "thu_muc", "duong_dan": str(nguon)}, py_launcher=sys.executable,
                          tao_moi_truong=_tao_runtime_thu)
        assert kq["cai_dat"]["trang_thai"] == mu.ACTIVE, kq["cai_dat"]
        may[ten] = kq
    a, b = may["pc_a"], may["pc_b"]
    assert a["installation_id"] != b["installation_id"]

    # Lệnh THẬT qua launcher: cli.py của release chạy managed trên state của B.
    assert launcher.main(["cli", "dich"], goc=b["goc"], tao_moi_truong=_tao_runtime_thu) == 0

    def iid_trong_db(m):
        db = os.path.join(m["state"], "data", "lichsu.db")
        if not os.path.isfile(db):
            return None
        con = sqlite3.connect(db)
        try:
            h = con.execute("SELECT gia_tri FROM cai_dat_may WHERE khoa='installation_id'").fetchone()
        finally:
            con.close()
        return h and h[0]

    # Lần cài đầu đã khởi tạo lịch sử v3 (migration bằng mã release mới) ở state của TỪNG máy; lệnh trên B
    # chỉ gắn định danh của B vào lịch sử của B — A không bị đụng.
    assert iid_trong_db(b) == b["installation_id"]
    assert iid_trong_db(a) in (None, a["installation_id"])
    rel_b = mu.doc_json(os.path.join(b["goc"], "update_state", "current.json"))["release"]
    assert not [d for d, _, fs in os.walk(rel_b) if "__pycache__" in d or any(f.endswith(".pyc") for f in fs)]

    # Bản 1.1.0: CHỈ cập nhật B — A không đổi một byte (mã, trạng thái, dữ liệu).
    truoc_a = _bam_cay(a["goc"], a["state"])
    _phat_hanh(nguon, khoa_rieng, files, "1.1.0")
    cn_b = launcher.tao_cap_nhat(b["goc"], launcher.doc_cau_hinh(b["goc"]), tao_moi_truong=_tao_runtime_thu)
    assert cn_b.chuan_bi().trang_thai == mu.STAGED
    assert cn_b.ap_dung().trang_thai == mu.ACTIVE
    assert cn_b.hien_tai()["phien_ban"] == "1.1.0" and _bam_cay(a["goc"], a["state"]) == truoc_a
    assert mu.doc_json(os.path.join(a["goc"], "update_state", "current.json"))["phien_ban"] == "1.0.0"

    # Hai máy, CÙNG số lần quét #1, cùng một bảng: khoá chống trùng / mã việc khác nhau (installation_id);
    # binding khoá của mỗi máy trỏ file khoá trong state RIÊNG của nó.
    from outbox_gia import khoa_gia

    khoa_cua = {}
    for ten, m in (("pc_a", a), ("pc_b", b)):
        db = os.path.join(m["state"], "data", "lichsu.db")
        if not os.path.exists(db):
            import lich_su

            lich_su.dam_bao_luoc_do(db)
        iid = sd.dinh_danh_may(db, mong_doi=m["installation_id"])
        khoa = khoa_gia(__import__("pathlib").Path(m["state"]) / "secrets")
        sd.dang_ky_xac_thuc(db, "mac_dinh", khoa)
        d = sd.tao_dich(db, ten="Bảng chung", spreadsheet_id="1" + "q" * 43, worksheet_id=0,
                        worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh",
                        workspace="mac_dinh")
        y = sd.chot_y_dinh(db, d.id, installation_id=iid)
        import outbox as ob

        with sd.ket_noi(db, ghi=True) as con:
            ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=["h"] * 34, rows=[["r"] * 34])
        con = sqlite3.connect(db)
        khoa_cua[ten] = con.execute("SELECT dedupe_key, id FROM hang_doi_gui").fetchone()
        con.close()
        assert sd.lay_xac_thuc(db, "mac_dinh").duong_dan.startswith(m["state"])
    assert khoa_cua["pc_a"][0] != khoa_cua["pc_b"][0] and khoa_cua["pc_a"][1] != khoa_cua["pc_b"][1]
