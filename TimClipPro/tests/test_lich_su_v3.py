# -*- coding: utf-8 -*-
"""Lược đồ ``lichsu.db`` phiên bản 3 — bảng hồ sơ đích gửi + outbox (docs/MANAGED_RUNTIME_DESIGN.md §5).

CHỈ THÊM BẢNG: dòng ``jobs``/``matches``/``bao_cao_job`` giữ nguyên byte-cho-byte về nội dung, sao lưu
trước bằng backup API, chạy lại không làm gì; bản cũ ``6dc3f9d`` mở DB v3 không nâng/hạ gì và vẫn ghi
được lịch sử theo tên cột. Dữ liệu tổng hợp.
"""
import importlib.util
import os
import sqlite3
import subprocess

import pytest

import lich_su

BANG_V3 = {"cai_dat_may", "xac_thuc_gui", "dich_gui", "dich_gui_phien_ban", "dich_gui_tab_chot",
           "hang_doi_gui"}


def _db_v2(path):
    """DB phiên bản 2 có dữ liệu (đúng DDL của 6dc3f9d)."""
    con = sqlite3.connect(path)
    for lenh in lich_su._DDL_GOC:
        con.execute(lenh)
    for ten, kieu in lich_su.COT_MOI:
        con.execute(f"ALTER TABLE jobs ADD COLUMN {ten} {kieu}")
    for lenh in (*lich_su._CHI_MUC, *lich_su._DDL_BAO_CAO):
        con.execute(lenh)
    con.execute("INSERT INTO jobs(created_at, source_type, source_name, source_ref, duration_s,"
                " status, n_matches, note, source_id, kho_id, kho_ten, kho_phien_ban, chinh_sach,"
                " day_du, dat_muc_tieu, pham_vi) VALUES ('2026-10-01 10:00:00','youtube','Video A',"
                "'https://youtu.be/AAAAAAAAAAA',3600,'ok',1,'','AAAAAAAAAAA','k1','Kho','3:10',"
                "'v1:x',1,1,'{}')")
    con.execute("INSERT INTO matches(job_id, clip, start_s, end_s, matched_s, clip_offset_s,"
                " hashes, confidence) VALUES (1,'a.opus',10,70,60,0,900,'cao')")
    con.execute("INSERT INTO bao_cao_job(job_id, chinh_sach, du_lieu, created_at)"
                " VALUES (1,'v2','{}','2026-10-01 10:00:01')")
    con.execute("PRAGMA user_version = 2")
    con.commit()
    con.close()


def _chup(path):
    con = sqlite3.connect(path)
    try:
        return {b: con.execute(f"SELECT * FROM {b} ORDER BY 1").fetchall()
                for b in ("jobs", "matches", "bao_cao_job")}
    finally:
        con.close()


def _bang(path):
    con = sqlite3.connect(path)
    try:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def test_phien_ban_hien_hanh_la_3():
    assert lich_su.PHIEN_BAN == 3
    assert set(lich_su.BANG_GUI) == BANG_V3


def test_db_moi_co_du_bang_v3_khong_sao_luu(tmp_path):
    db = str(tmp_path / "moi.db")
    kq = lich_su.dam_bao_luoc_do(db)
    assert kq["sao_luu"] == "" and kq["phien_ban"] == 3
    assert BANG_V3 <= _bang(db)
    tt = lich_su.thong_ke(db)
    assert tt["phien_ban"] == 3 and tt["can_nang_cap"] is False and tt["bang_se_them"] == []


def test_nang_cap_v2_len_v3_sao_luu_va_giu_nguyen_du_lieu(tmp_path):
    db = str(tmp_path / "lichsu.db")
    _db_v2(db)
    truoc = _chup(db)
    kq = lich_su.dam_bao_luoc_do(db)
    assert kq["da_nang_cap"] is True and kq["phien_ban_cu"] == 2 and kq["phien_ban"] == 3
    assert os.path.basename(kq["sao_luu"]).startswith("lichsu.db.v2_")
    assert _chup(db) == truoc
    assert _chup(kq["sao_luu"]) == truoc                 # bản sao lưu là v2 nguyên vẹn
    assert BANG_V3 <= _bang(db) and not (BANG_V3 & _bang(kq["sao_luu"]))
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 3
    assert all(con.execute(f"SELECT COUNT(*) FROM {b}").fetchone()[0] == 0 for b in BANG_V3)
    con.close()


def test_chay_lai_khong_lam_gi_them(tmp_path):
    db = str(tmp_path / "lichsu.db")
    _db_v2(db)
    lich_su.dam_bao_luoc_do(db)
    lan2 = lich_su.dam_bao_luoc_do(db)
    assert lan2["da_nang_cap"] is False and lan2["sao_luu"] == ""
    assert len([f for f in os.listdir(tmp_path) if f.endswith(".bak")]) == 1


def test_thieu_mot_bang_v3_thi_bo_sung(tmp_path):
    """DB v3 bị mất bảng (sửa tay, khôi phục lỗi): nâng cấp bổ sung, không hạ phiên bản."""
    db = str(tmp_path / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    con = sqlite3.connect(db)
    con.execute("DROP TABLE dich_gui_phien_ban")
    con.commit()
    con.close()
    assert lich_su.thong_ke(db)["bang_se_them"] == ["dich_gui_phien_ban"]
    assert lich_su.dam_bao_luoc_do(db)["da_nang_cap"] is True
    assert BANG_V3 <= _bang(db)


def test_thong_ke_tren_v2_chi_doc_va_liet_ke_bang_se_them(tmp_path):
    db = str(tmp_path / "lichsu.db")
    _db_v2(db)
    with open(db, "rb") as f:
        truoc = f.read()
    tt = lich_su.thong_ke(db)
    assert tt["can_nang_cap"] is True and set(tt["bang_se_them"]) == BANG_V3
    with open(db, "rb") as f:
        assert f.read() == truoc


def _lich_su_cu():
    """lich_su.py của 6dc3f9d lấy từ Git (TIMCLIP_REPO_GOC hoặc repo chứa file test này)."""
    goc = os.environ.get("TIMCLIP_REPO_GOC") or os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    try:
        ma = subprocess.run(["git", "-C", goc, "show", "6dc3f9d:TimClipPro/lich_su.py"],
                            capture_output=True, check=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("không chạy trong repo git (đặt TIMCLIP_REPO_GOC để kiểm bản cũ)")
    spec = importlib.util.spec_from_loader("lich_su_6dc3f9d", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(ma, "lich_su_6dc3f9d.py", "exec"), mod.__dict__)  # noqa: S102 — mã của chính repo
    return mod


def test_ban_cu_6dc3f9d_mo_db_v3_khong_nang_khong_ha_va_van_ghi(tmp_path):
    cu = _lich_su_cu()
    assert cu.PHIEN_BAN == 2
    db = str(tmp_path / "lichsu.db")
    _db_v2(db)
    lich_su.dam_bao_luoc_do(db)
    with open(db, "rb") as f:
        truoc = f.read()
    kq = cu.dam_bao_luoc_do(db)
    assert kq["da_nang_cap"] is False
    with open(db, "rb") as f:
        assert f.read() == truoc                         # bản cũ chỉ ĐỌC
    con = sqlite3.connect(db)
    con.execute("INSERT INTO jobs(created_at, source_type, source_name, source_ref, duration_s,"
                " status, n_matches, note, source_id, kho_id, kho_ten, kho_phien_ban,"
                " chinh_sach, day_du, dat_muc_tieu, pham_vi) VALUES"
                " ('t','youtube','x','u',1.0,'ok',0,'','id','k','K','v','c',1,0,'{}')")
    con.commit()
    assert con.execute("PRAGMA user_version").fetchone()[0] == 3
    con.close()
