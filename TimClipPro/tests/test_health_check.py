# -*- coding: utf-8 -*-
"""health_check.py — chạy như updater chạy (tiến trình riêng), trên DB TỔNG HỢP.

* staging/kích hoạt: DB thật chỉ được ĐỌC (byte không đổi), mạng bị chặn, Engine chạy trên state root tạm;
* schema mới hơn mã → lỗi; kích hoạt mà DB chưa nâng cấp → lỗi; ảnh chụp V2 không đọc được → lỗi;
* migrate: nâng cấp DB thật bằng mã của release, idempotent.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys

import health_check
import lich_su
from test_bao_cao_v2 import _bc, _kq_ca_that

HC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "health_check.py")
BANG_V3 = ("cai_dat_may", "xac_thuc_gui", "dich_gui", "dich_gui_phien_ban", "hang_doi_gui")


def _chay(*doi_so):
    p = subprocess.run([sys.executable, HC, *doi_so], capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    dau = health_check.DAU_KET_QUA + " "
    dong = [x[len(dau):] for x in p.stdout.splitlines() if x.startswith(dau)]
    return p.returncode, (json.loads(dong[-1]) if dong else {"stderr": p.stderr})


def _bam(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _db_co_anh_chup(engine):
    kq = _kq_ca_that()
    kq.bao_cao = _bc(kq)
    engine.save_job(kq, "youtube")
    return engine.sqlite_file


def test_staging_chi_doc_db_that_va_dat(engine):
    db = _db_co_anh_chup(engine)
    truoc = _bam(db)
    ma, kq = _chay("kiem", "--che-do", "staging", "--data-dir", os.path.dirname(db))
    assert ma == 0 and kq["ok"], kq
    assert kq["db"]["phien_ban_db"] == lich_su.PHIEN_BAN and kq["db"]["anh_chup_doc_duoc"] == 1
    assert kq["thu_vien"]["streamlit"] and kq["sqlite"]
    assert kq["engine_tam"]["lich_su_tam"] == 0
    assert _bam(db) == truoc
    assert not os.path.exists(db + "-journal") and not os.path.exists(db + "-wal")


def test_schema_moi_hon_ma_thi_loi(engine):
    db = _db_co_anh_chup(engine)
    con = sqlite3.connect(db)
    con.execute(f"PRAGMA user_version={lich_su.PHIEN_BAN + 5}")
    con.commit()
    con.close()
    ma, kq = _chay("kiem", "--che-do", "staging", "--data-dir", os.path.dirname(db))
    assert ma == 1 and any("schema quá mới" in x for x in kq["loi"])


def _ha_ve_v2(db):
    con = sqlite3.connect(db)
    for b in BANG_V3:
        con.execute(f"DROP TABLE IF EXISTS {b}")
    con.execute("PRAGMA user_version=2")
    con.commit()
    con.close()


def test_kich_hoat_doi_db_da_nang_cap_migrate_idempotent(engine):
    db = _db_co_anh_chup(engine)
    _ha_ve_v2(db)
    data = os.path.dirname(db)
    assert _chay("kiem", "--che-do", "staging", "--data-dir", data)[0] == 0
    ma, kq = _chay("kiem", "--che-do", "kich_hoat", "--data-dir", data)
    assert ma == 1 and any("chưa được nâng cấp" in x for x in kq["loi"])
    ma, kq = _chay("migrate", "--data-dir", data)
    assert ma == 0 and kq["da_nang_cap"] and kq["phien_ban"] == lich_su.PHIEN_BAN
    assert _chay("migrate", "--data-dir", data)[1]["da_nang_cap"] is False
    assert _chay("kiem", "--che-do", "kich_hoat", "--data-dir", data)[0] == 0


def test_anh_chup_khong_doc_duoc_thi_loi(engine):
    db = _db_co_anh_chup(engine)
    con = sqlite3.connect(db)
    con.execute("UPDATE bao_cao_job SET du_lieu='{hỏng'")
    con.commit()
    con.close()
    ma, kq = _chay("kiem", "--che-do", "staging", "--data-dir", os.path.dirname(db))
    assert ma == 1 and any("ảnh chụp" in x for x in kq["loi"])


def test_chan_mang_truoc_khi_import():
    ma = ("import sys; sys.path.insert(0, %r); import health_check as h; h.chan_mang();"
          "import socket\ntry:\n    socket.create_connection(('example.com', 80), timeout=1)\n"
          "except OSError as e:\n    print(e)") % os.path.dirname(HC)
    p = subprocess.run([sys.executable, "-c", ma], capture_output=True, text=True, encoding="utf-8",
                       timeout=60)
    assert "health_check: mạng bị chặn" in p.stdout
