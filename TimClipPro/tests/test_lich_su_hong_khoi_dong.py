# -*- coding: utf-8 -*-
"""Audit P3 B-8: ``lichsu.db`` hỏng (trang đầu bị ghi đè sau mất điện) khi khởi động GUI/CLI/Watch.

Dữ liệu synthetic: ``TIMCLIP_DATA_DIR`` → thư mục tạm; ``lichsu.db`` = 4096 byte 0 (SQLite: «file is not a
database»). Chạy ``cli.main()`` như GiamSat.bat / Task Scheduler (``watch``) và ``cli.py dich``, và ``app.py``.

Hành vi ĐÚNG (cùng khuôn với ``SoKhoHong`` / ``LoiRuntime`` / ``LoiLuuBen`` trong ``cli.main``: lỗi vận hành
báo gọn, không traceback): CLI thoát ``SystemExit(1)`` với một dòng tiếng Việt trên stderr nói lịch sử
``lichsu.db`` không đọc được và chỉ cách kiểm/khôi phục (``lich_su.py --kiem`` / ``--khoi-phuc``,
DATA_MIGRATION_AND_RECOVERY §3/§9) — KHÔNG để ``sqlite3.DatabaseError`` thô thoát ra; file hỏng không bị sửa.
CSDL bị KHOÁ vẫn là ``OperationalError`` gốc (tạm thời — bộ cập nhật đếm lần qua ``la_loi_tam_thoi``).
"""
from __future__ import annotations

import os
import sqlite3
import sys

import cli
import health_check
import lich_su
import pytest

GOC_MA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HONG = b"\x00" * 4096


@pytest.fixture()
def db_hong(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "lichsu.db").write_bytes(HONG)
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("TIMCLIP_STATE_ROOT", raising=False)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))      # Engine() chèn bin\ vào PATH — hoàn lại sau test
    monkeypatch.chdir(tmp_path)                                 # watchlist.json / nhật ký (nếu có) nằm ở tmp
    return data


@pytest.mark.parametrize("lenh", ["watch", "dich"])
def test_cli_db_lich_su_hong_bao_gon_tieng_viet(db_hong, monkeypatch, capsys, lenh):
    monkeypatch.setattr(sys, "argv", ["cli.py", lenh])
    try:
        cli.main()
    except SystemExit as e:
        thoat = e
    except sqlite3.DatabaseError as e:                         # hành vi SAI cũ: traceback thô
        pytest.fail(f"`cli.py {lenh}`: sqlite3.{type(e).__name__} thô thoát khỏi main(): {e}")
    else:
        pytest.fail(f"`cli.py {lenh}` chạy tiếp với lichsu.db hỏng")
    assert thoat.code == 1
    loi = capsys.readouterr().err
    assert "LỖI LỊCH SỬ" in loi
    assert "lichsu.db" in loi and "--kiem" in loi and "--khoi-phuc" in loi, loi
    assert (db_hong / "lichsu.db").read_bytes() == HONG        # không sửa file hỏng


def test_dam_bao_luoc_do_file_hong_bao_loi_rieng_khong_sua_file(tmp_path):
    db = tmp_path / "lichsu.db"
    db.write_bytes(HONG)
    with pytest.raises(lich_su.LoiLichSuHong) as ei:
        lich_su.dam_bao_luoc_do(str(db))
    assert isinstance(ei.value, sqlite3.DatabaseError)          # nơi bắt lỗi SQLite chung vẫn bắt được
    assert not health_check.la_loi_tam_thoi(ei.value)           # hỏng = tất định, không phải tạm thời
    assert db.read_bytes() == HONG
    assert [p.name for p in tmp_path.iterdir()] == ["lichsu.db"]  # không sinh bản sao/file phụ


def test_dam_bao_luoc_do_db_bi_khoa_giu_loi_tam_thoi_goc(tmp_path):
    db = str(tmp_path / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    giu = sqlite3.connect(db, isolation_level=None)
    try:
        giu.execute("BEGIN EXCLUSIVE")
        with pytest.raises(sqlite3.OperationalError) as ei:
            lich_su.dam_bao_luoc_do(db, han_cho_s=0.05)
        assert not isinstance(ei.value, lich_su.LoiLichSuHong)
        assert health_check.la_loi_tam_thoi(ei.value)
    finally:
        giu.execute("ROLLBACK")
        giu.close()


def test_app_db_lich_su_hong_bao_loi_ro_khong_traceback(db_hong):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(os.path.join(GOC_MA, "app.py"), default_timeout=120).run()
    assert not at.exception
    loi = [e.value for e in at.error]
    assert any("Không khởi động được TimClip Pro" in x and "--khoi-phuc" in x for x in loi), loi
    assert (db_hong / "lichsu.db").read_bytes() == HONG
