# -*- coding: utf-8 -*-
"""health_check.py — chạy như updater chạy (tiến trình riêng), trên DB TỔNG HỢP.

* staging/kích hoạt: DB thật chỉ được ĐỌC (byte không đổi), mạng bị chặn, Engine chạy trên state root tạm;
* schema mới hơn mã → lỗi; kích hoạt mà DB chưa nâng cấp → lỗi; ảnh chụp V2 không đọc được → lỗi;
* migrate: nâng cấp DB thật bằng mã của release, idempotent.
* bảng mã: khởi động THẬT (script → ``main``, hay ``launcher._chay_health``) in được tiếng Việt dù stdout của
  máy là cp1252 (Windows tiếng Anh — PC2) hay UTF-8; mỗi test ép bảng mã của tiến trình con nên máy nào cũng như nhau.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys

import pytest

import health_check
import launcher
import lich_su
import managed_update as mu
from test_bao_cao_v2 import _bc, _kq_ca_that

HC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "health_check.py")
GOC_MA = os.path.dirname(os.path.dirname(HC))      # chứa TimClipPro/ — đóng vai thư mục release cho launcher
BANG_V3 = ("cai_dat_may", "xac_thuc_gui", "dich_gui", "dich_gui_phien_ban", "hang_doi_gui")
MA_HOA = ["cp1252", "utf-8"]


def _bien_ma_hoa(ma_hoa):
    """Ép bảng mã stdio của tiến trình con — giả lập máy cp1252 ở MỌI máy, kể cả máy đang bật UTF-8."""
    return {"PYTHONIOENCODING": ma_hoa, "PYTHONUTF8": "1" if ma_hoa == "utf-8" else "0"}


def _chay(*doi_so, env=None, tep=HC):
    p = subprocess.run([sys.executable, tep, *doi_so], capture_output=True, text=True,
                       encoding="utf-8", timeout=300, env=env)
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


@pytest.mark.parametrize("ma_hoa", MA_HOA)
def test_chan_mang_truoc_khi_import(ma_hoa):
    # Tiến trình con làm ĐÚNG thứ tự của main(): đầu ra UTF-8 rồi mới chặn mạng. Bản cũ bỏ _utf8_dau_ra() nên
    # print tiếng Việt sập trên stdout cp1252 (PC2) — lỗi của test, health_check thật không sập (hai test dưới).
    ma = ("import sys; sys.path.insert(0, %r); import health_check as h; h._utf8_dau_ra(); h.chan_mang();"
          "import socket\ntry:\n    socket.create_connection(('example.com', 80), timeout=1)\n"
          "except OSError as e:\n    print(e)") % os.path.dirname(HC)
    p = subprocess.run([sys.executable, "-c", ma], capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env={**os.environ, **_bien_ma_hoa(ma_hoa)})
    assert "health_check: mạng bị chặn" in p.stdout, p.stderr


@pytest.mark.parametrize("ma_hoa", MA_HOA)
def test_khoi_dong_that_khong_qua_launcher_van_in_tieng_viet(ma_hoa, tmp_path):
    """``python health_check.py`` (→ ``main``) gọi THẲNG, không có môi trường UTF-8 của launcher: ``main`` tự chuyển
    đầu ra sang UTF-8 nên dòng kết quả có tiếng Việt không làm sập tiến trình trên stdout cp1252."""
    ma, kq = _chay("kiem", "--che-do", "staging", "--data-dir", str(tmp_path),
                   env={**os.environ, **_bien_ma_hoa(ma_hoa)})
    assert ma == 0 and kq.get("ok") is True, kq
    assert any("Không thấy manifest.json cạnh mã" in x for x in kq["canh_bao"]), kq


@pytest.mark.parametrize("ma_hoa", MA_HOA)
def test_release_hong_van_bao_loi_tieng_viet(ma_hoa, tmp_path):
    """Release HỎNG (không import được lõi): dòng kết quả in TRƯỚC khi ``cli`` kịp đổi stdout sang UTF-8 lúc import
    — chỉ ``_utf8_dau_ra`` của ``main`` giữ cho lỗi tiếng Việt về được tới updater thay vì sập trên cp1252."""
    tep = tmp_path / "TimClipPro" / "health_check.py"
    tep.parent.mkdir()
    shutil.copy(HC, tep)                                       # một mình health_check.py — lõi không import được
    ma, kq = _chay("kiem", "--data-dir", str(tmp_path), env={**os.environ, **_bien_ma_hoa(ma_hoa)}, tep=str(tep))
    assert ma == 1 and kq.get("ok") is False, kq
    assert any("Không import được lõi" in x for x in kq["loi"]), kq


@pytest.mark.parametrize("ma_hoa", MA_HOA)
def test_launcher_chay_health_that_tren_may(ma_hoa, tmp_path, monkeypatch):
    """Đường production: ``launcher._chay_health`` chạy health_check.py THẬT của cây mã này (không giả subprocess)
    với môi trường ``moi_truong_con`` — ép UTF-8 dù máy đang cp1252 — rồi đọc dòng kết quả."""
    for k, v in _bien_ma_hoa(ma_hoa).items():
        monkeypatch.setenv(k, v)                                   # «máy» đang cp1252 hay UTF-8
    monkeypatch.setattr(launcher, "python_runtime", lambda con_tro: sys.executable)
    cd = mu.CaiDat(goc=str(tmp_path / "goc"), state_root=str(tmp_path / "state"))
    os.makedirs(cd.data_dir)
    env = launcher.moi_truong_con(cd, {})
    assert (env["PYTHONUTF8"], env["PYTHONIOENCODING"]) == ("1", "utf-8")
    ok, kq = launcher._chay_health(cd, GOC_MA, "khong-dung", ["kiem", "--che-do", "staging"], 300)
    assert ok is True, kq
    assert any("Không thấy manifest.json cạnh mã" in x for x in kq["canh_bao"]), kq
