# -*- coding: utf-8 -*-
"""Lược đồ ``lichsu.db`` phiên bản 4 — cột ``hang_doi_gui.gui_worksheet_id`` (mã tab của TỪNG lần phát, MR-R2-P2-01).

CHỈ THÊM CỘT: dòng outbox cũ giữ nguyên mọi cột, cột mới NULL — với việc đã phát, NULL CÓ NGHĨA «bản cũ phát, không
ghi mã» (không bao giờ tự gửi lại theo tên); sao lưu trước bằng backup API khi outbox có dữ liệu; chạy lại không làm
gì; bản 78ba20c (phiên bản 3) mở DB v4 không nâng/hạ gì và vẫn xếp hàng được (ghi theo tên cột). Dữ liệu tổng hợp.
"""
import importlib.util
import os
import sqlite3
import subprocess

import pytest

import lich_su

COT_V3 = ("id", "dedupe_key", "installation_id", "workspace", "job_id", "lo_id", "nguon", "dich_id",
          "dich_phien_ban", "dich_json", "schema_id", "chinh_sach", "header_json", "rows_json", "so_dong",
          "payload_sha256", "trang_thai", "so_lan_thu", "thu_lai_sau", "chu_so_huu", "claim_token", "claim_luc",
          "gui_luc", "loi", "bien_nhan", "da_xoa_job", "tao_luc", "sua_luc")
# Đúng câu INSERT của ``outbox.them_viec`` ở 78ba20c/f4d3cb7 (liệt kê cột, không có cột v4).
INSERT_BAN_CU = (
    "INSERT INTO hang_doi_gui(id, dedupe_key, installation_id, workspace, job_id, lo_id, nguon,"
    " dich_id, dich_phien_ban, dich_json, schema_id, chinh_sach, header_json, rows_json,"
    " so_dong, payload_sha256, trang_thai, loi, tao_luc, sua_luc)"
    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")


def _viec(i, trang_thai="PENDING"):
    return (f"v{i}", f"k{i}", "c" * 32, "mac_dinh", i, "lo", "auto", "d", 1, "{}", "ngang", "v2", "[]", "[]", 0,
            "", trang_thai, "", 1.0, 1.0)


def _db_v3(path, *, so_viec=2):
    """DB phiên bản 3 như bản 78ba20c/f4d3cb7 để lại: lược đồ hiện hành bỏ cột v4, ``user_version`` 3; một việc
    đã phát (UNKNOWN, ``gui_luc``) và một việc chờ."""
    lich_su.dam_bao_luoc_do(path)
    con = sqlite3.connect(path)
    con.execute("ALTER TABLE hang_doi_gui DROP COLUMN gui_worksheet_id")
    for i in range(1, so_viec + 1):
        con.execute(INSERT_BAN_CU, _viec(i, "UNKNOWN_DELIVERY" if i == 1 else "PENDING"))
    con.execute("UPDATE hang_doi_gui SET gui_luc=99.0 WHERE id='v1'")
    con.execute("PRAGMA user_version = 3")
    con.commit()
    con.close()


def _cot(path):
    con = sqlite3.connect(path)
    try:
        return [r[1] for r in con.execute("PRAGMA table_info(hang_doi_gui)")]
    finally:
        con.close()


def _dong(path, cot=COT_V3):
    con = sqlite3.connect(path)
    try:
        return con.execute(f"SELECT {', '.join(cot)} FROM hang_doi_gui ORDER BY id").fetchall()
    finally:
        con.close()


def test_phien_ban_hien_hanh_la_4_them_cot_ma_tab_cua_lan_phat():
    assert lich_su.PHIEN_BAN == 4
    assert lich_su.COT_GUI_MOI == (("gui_worksheet_id", "INTEGER"),)


def test_db_moi_co_san_cot_v4_khong_can_nang_cap(tmp_path):
    db = str(tmp_path / "moi.db")
    kq = lich_su.dam_bao_luoc_do(db)
    assert kq["sao_luu"] == "" and kq["phien_ban"] == 4 and "gui_worksheet_id" in _cot(db)
    tt = lich_su.thong_ke(db)
    assert tt["can_nang_cap"] is False and tt["cot_gui_se_them"] == []


def test_nang_cap_v3_len_v4_chi_them_cot_sao_luu_truoc_va_giu_nguyen_dong_cu(tmp_path):
    db = str(tmp_path / "lichsu.db")
    _db_v3(db)
    truoc = _dong(db)
    with open(db, "rb") as f:
        byte_truoc = f.read()
    tt = lich_su.thong_ke(db)                                          # chạy thử: CHỈ ĐỌC
    assert tt["can_nang_cap"] is True and tt["cot_gui_se_them"] == ["gui_worksheet_id"] and tt["so_viec_gui"] == 2
    with open(db, "rb") as f:
        assert f.read() == byte_truoc
    kq = lich_su.dam_bao_luoc_do(db)
    assert kq["da_nang_cap"] is True and kq["phien_ban_cu"] == 3 and kq["phien_ban"] == 4
    assert os.path.basename(kq["sao_luu"]).startswith("lichsu.db.v3_")  # outbox có dữ liệu → sao lưu TRƯỚC
    assert "gui_worksheet_id" not in _cot(kq["sao_luu"]) and _dong(kq["sao_luu"]) == truoc
    assert _dong(db) == truoc                                          # mọi cột cũ giữ nguyên giá trị
    assert _dong(db, ("id", "gui_worksheet_id")) == [("v1", None), ("v2", None)]
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 4
    con.close()
    lan2 = lich_su.dam_bao_luoc_do(db)
    assert lan2["da_nang_cap"] is False and lan2["sao_luu"] == ""
    assert len([f for f in os.listdir(tmp_path) if f.endswith(".bak")]) == 1


def test_v3_bi_thieu_cot_du_user_version_da_la_4_van_bo_sung(tmp_path):
    """DB v4 bị mất cột (khôi phục lệch, sửa tay): bổ sung, không hạ phiên bản."""
    db = str(tmp_path / "lichsu.db")
    _db_v3(db, so_viec=1)
    con = sqlite3.connect(db)
    con.execute("PRAGMA user_version = 4")
    con.commit()
    con.close()
    assert lich_su.thong_ke(db)["cot_gui_se_them"] == ["gui_worksheet_id"]
    assert lich_su.dam_bao_luoc_do(db)["da_nang_cap"] is True and "gui_worksheet_id" in _cot(db)


def _lich_su_78ba20c():
    """lich_su.py của 78ba20c (phiên bản 3) lấy từ Git (TIMCLIP_REPO_GOC hoặc repo chứa file test này)."""
    goc = os.environ.get("TIMCLIP_REPO_GOC") or os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    try:
        ma = subprocess.run(["git", "-C", goc, "show", "78ba20c:TimClipPro/lich_su.py"],
                            capture_output=True, check=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("không chạy trong repo git (đặt TIMCLIP_REPO_GOC để kiểm bản cũ)")
    spec = importlib.util.spec_from_loader("lich_su_78ba20c", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(ma, "lich_su_78ba20c.py", "exec"), mod.__dict__)  # noqa: S102 — mã của chính repo
    return mod


def test_ban_78ba20c_mo_db_v4_khong_nang_khong_ha_va_van_xep_hang(tmp_path):
    cu = _lich_su_78ba20c()
    assert cu.PHIEN_BAN == 3
    db = str(tmp_path / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    with open(db, "rb") as f:
        truoc = f.read()
    assert cu.dam_bao_luoc_do(db)["da_nang_cap"] is False
    with open(db, "rb") as f:
        assert f.read() == truoc                                       # bản cũ chỉ ĐỌC
    con = sqlite3.connect(db)
    con.execute(INSERT_BAN_CU, _viec(7))                               # bản cũ xếp hàng theo tên cột
    con.commit()
    assert con.execute("SELECT gui_worksheet_id FROM hang_doi_gui WHERE id='v7'").fetchone()[0] is None
    assert con.execute("PRAGMA user_version").fetchone()[0] == 4
    con.close()
