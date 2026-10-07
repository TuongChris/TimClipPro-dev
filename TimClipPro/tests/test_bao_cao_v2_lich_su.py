# -*- coding: utf-8 -*-
"""Lược đồ lịch sử phiên bản 2: CHỈ THÊM bảng ``bao_cao_job`` (ảnh chụp báo cáo V2).

Nâng cấp phải: sao lưu trước, giữ nguyên từng dòng cũ, chạy lại bao nhiêu lần cũng được, và để
bản code cũ (rollback) vẫn đọc/ghi được — bảng ``jobs`` không thêm cột nào.
"""
import os
import sqlite3

import lich_su

DDL_V1_JOBS = """CREATE TABLE jobs(
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, source_type TEXT, source_name TEXT,
    source_ref TEXT, duration_s REAL, status TEXT, n_matches INTEGER, note TEXT,
    source_id TEXT DEFAULT '', kho_id TEXT DEFAULT '', kho_ten TEXT DEFAULT '',
    kho_phien_ban TEXT DEFAULT '', chinh_sach TEXT DEFAULT '', day_du INTEGER,
    dat_muc_tieu INTEGER, pham_vi TEXT DEFAULT '')"""
DDL_MATCHES = """CREATE TABLE matches(id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER,
    clip TEXT, start_s REAL, end_s REAL, matched_s REAL, clip_offset_s REAL, hashes INTEGER,
    confidence TEXT)"""


def _db_v1(path):
    con = sqlite3.connect(path)
    con.execute(DDL_V1_JOBS)
    con.execute(DDL_MATCHES)
    con.execute("INSERT INTO jobs(created_at, source_type, source_name, source_ref, duration_s,"
                " status, n_matches, note, source_id, kho_id, kho_ten, kho_phien_ban,"
                " chinh_sach, day_du, dat_muc_tieu, pham_vi) VALUES"
                " ('2026-01-02 03:04:05','youtube','Video cũ','u',14523.4,'ok',1,'',"
                " 'vidvipham01','ten:kho','Kho','-:1','v1:x',0,1,'{}')")
    con.execute("INSERT INTO matches(job_id, clip, start_s, end_s, matched_s, clip_offset_s,"
                " hashes, confidence) VALUES (1,'c [goc00000001].opus',915.5,2350.0,1300.5,"
                " 55.5,20000,'Rất chắc chắn')")
    con.execute("PRAGMA user_version = 1")
    con.commit()
    con.close()


def _chup(path):
    con = sqlite3.connect(path)
    try:
        return {b: con.execute(f"SELECT * FROM {b} ORDER BY id").fetchall()
                for b in ("jobs", "matches")}, [r[1] for r in con.execute(
                    "PRAGMA table_info(jobs)")]
    finally:
        con.close()


def test_nang_cap_v1_len_v2_sao_luu_va_giu_nguyen_dong_cu(tmp_path):
    db = str(tmp_path / "lichsu.db")
    _db_v1(db)
    truoc, cot_truoc = _chup(db)
    kq = lich_su.dam_bao_luoc_do(db)
    assert kq["da_nang_cap"] is True and kq["phien_ban_cu"] == 1
    assert kq["phien_ban"] == lich_su.PHIEN_BAN
    assert kq["sao_luu"] and os.path.isfile(kq["sao_luu"])
    sau, cot_sau = _chup(db)
    assert sau == truoc and cot_sau == cot_truoc          # không đổi dòng, không thêm cột
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == lich_su.PHIEN_BAN
    assert con.execute("SELECT COUNT(*) FROM bao_cao_job").fetchone()[0] == 0
    con.close()
    # Bản sao lưu là bản v1 nguyên vẹn (để rollback).
    bak, cot_bak = _chup(kq["sao_luu"])
    assert bak == truoc and cot_bak == cot_truoc


def test_chay_lai_khong_lam_gi_them(tmp_path):
    db = str(tmp_path / "lichsu.db")
    _db_v1(db)
    lich_su.dam_bao_luoc_do(db)
    lan2 = lich_su.dam_bao_luoc_do(db)
    assert lan2["da_nang_cap"] is False and lan2["sao_luu"] == ""
    assert len([f for f in os.listdir(tmp_path) if f.endswith(".bak")]) == 1


def test_ban_cu_rollback_van_ghi_doc_duoc_db_v2(tmp_path):
    """Code cũ (fe07985/7ee527a) ghi theo TÊN CỘT và kiểm `user_version < 1 or thiếu cột` —
    cả hai vẫn đúng trên DB v2."""
    db = str(tmp_path / "lichsu.db")
    _db_v1(db)
    lich_su.dam_bao_luoc_do(db)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO jobs(created_at, source_type, source_name, source_ref, duration_s,"
                " status, n_matches, note, source_id, kho_id, kho_ten, kho_phien_ban,"
                " chinh_sach, day_du, dat_muc_tieu, pham_vi) VALUES"
                " ('t','youtube','x','u',1.0,'ok',0,'','id','k','K','v','c',1,0,'{}')")
    con.commit()
    phien_ban = con.execute("PRAGMA user_version").fetchone()[0]
    cot = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
    con.close()
    can_nang_cap_theo_ban_cu = phien_ban < 1 or any(t not in cot for t, _ in lich_su.COT_MOI)
    assert can_nang_cap_theo_ban_cu is False


def test_thong_ke_bao_bang_se_them_ma_khong_ghi(tmp_path):
    db = str(tmp_path / "lichsu.db")
    _db_v1(db)
    with open(db, "rb") as f:
        truoc = f.read()
    tt = lich_su.thong_ke(db)
    assert tt["can_nang_cap"] is True
    assert tt["bang_se_them"] == ["bao_cao_job", *lich_su.BANG_GUI]
    with open(db, "rb") as f:
        assert f.read() == truoc


def test_db_moi_tao_co_san_bang_anh_chup(tmp_path):
    db = str(tmp_path / "moi.db")
    kq = lich_su.dam_bao_luoc_do(db)
    assert kq["sao_luu"] == ""
    tt = lich_su.thong_ke(db)
    assert tt["phien_ban"] == lich_su.PHIEN_BAN and tt["can_nang_cap"] is False
    assert tt["bang_se_them"] == []
