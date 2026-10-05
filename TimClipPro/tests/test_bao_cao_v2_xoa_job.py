# -*- coding: utf-8 -*-
"""Xoá một lần quét khỏi lịch sử phải xoá CẢ ảnh chụp báo cáo V2 của nó (audit P1-01).

Trước bản sửa, ``Engine.delete_job`` chỉ xoá ``matches`` và ``jobs``: dòng ``bao_cao_job`` ở lại
mồ côi (tái hiện: ảnh chụp trước 1 → jobs 0, matches 0, ảnh chụp sau vẫn 1). Ba bảng thuộc
cùng một lần quét phải biến mất trong CÙNG một giao dịch; lần quét khác không bị đụng tới.
Dữ liệu tổng hợp.
"""
import dataclasses
import sqlite3

import pytest

from engine import ScanResult
from test_bao_cao_v2 import _bc, _kq_ca_that


def _dem(engine, job_id):
    con = sqlite3.connect(engine.sqlite_file)
    try:
        return tuple(con.execute(sql, (job_id,)).fetchone()[0] for sql in (
            "SELECT COUNT(*) FROM jobs WHERE id=?",
            "SELECT COUNT(*) FROM matches WHERE job_id=?",
            "SELECT COUNT(*) FROM bao_cao_job WHERE job_id=?"))
    finally:
        con.close()


def _luu_v2(engine):
    kq = _kq_ca_that()
    kq.bao_cao = _bc(kq)
    return engine.save_job(kq, "youtube")


def test_xoa_job_v2_xoa_ca_jobs_matches_va_anh_chup(engine):
    job_id = _luu_v2(engine)
    assert _dem(engine, job_id) == (1, 1, 1)
    engine.delete_job(job_id)
    assert _dem(engine, job_id) == (0, 0, 0)
    assert engine.bao_cao_cua_job(job_id) is None


def test_xoa_job_cu_khong_co_anh_chup_van_nhu_truoc(engine):
    kq = dataclasses.replace(_kq_ca_that(), bao_cao=None)
    job_id = engine.save_job(kq, "youtube")
    assert _dem(engine, job_id) == (1, 1, 0)
    engine.delete_job(job_id)
    assert _dem(engine, job_id) == (0, 0, 0)


def test_xoa_job_khong_ton_tai_la_khong_lam_gi(engine):
    giu = _luu_v2(engine)
    engine.delete_job(giu + 1000)                    # không ném lỗi — như bản cũ
    assert _dem(engine, giu) == (1, 1, 1)


def test_xoa_job_a_khong_dung_toi_job_b(engine):
    a = _luu_v2(engine)
    b = _luu_v2(engine)
    c = engine.save_job(ScanResult(source_name="cũ", source_ref="u"), "youtube")
    bc_b = engine.bao_cao_cua_job(b)
    engine.delete_job(a)
    assert _dem(engine, a) == (0, 0, 0)
    assert _dem(engine, b) == (1, 1, 1)
    assert engine.bao_cao_cua_job(b) == bc_b
    assert _dem(engine, c) == (1, 0, 0)


def test_loi_giua_chung_khong_de_trang_thai_xoa_mot_nua(engine):
    """Lệnh xoá `jobs` hỏng (trigger chặn) → cả giao dịch lùi lại: ảnh chụp và matches còn đủ."""
    job_id = _luu_v2(engine)
    con = sqlite3.connect(engine.sqlite_file)
    try:
        with con:
            con.execute("CREATE TRIGGER chan_xoa BEFORE DELETE ON jobs "
                        "BEGIN SELECT RAISE(ABORT, 'chặn xoá (test)'); END")
    finally:
        con.close()
    with pytest.raises(sqlite3.DatabaseError):
        engine.delete_job(job_id)
    assert _dem(engine, job_id) == (1, 1, 1)
    assert engine.bao_cao_cua_job(job_id) is not None
