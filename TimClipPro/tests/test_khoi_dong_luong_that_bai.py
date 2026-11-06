# -*- coding: utf-8 -*-
"""Audit 06/11 (cùng gốc DR-6 của ``tac_vu_nen``): hết tài nguyên luồng, ``Thread.start`` ném lỗi.

Thread chưa từng chạy nên ``finally`` của nó không dọn: không gỡ thì việc «ma» giữ ``running``, chỗ trong sổ và lease tới
khi tắt Tool, mọi lần bấm sau bị từ chối, updater chờ mãi.
"""

import threading

import pytest

import common_original_jobs
import fingerprint_progress
import scan_jobs
from common_original_jobs import CommonOriginalJobController
from engine import Engine
from fingerprint_progress import FingerprintJobController
from scan_jobs import ScanJobController

LOI = "can't start new thread"


@pytest.fixture()
def e(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    return Engine(root=str(tmp_path))


def _start_hong(monkeypatch, ham):
    def hong(_self):
        raise RuntimeError(LOI)

    with monkeypatch.context() as m:
        m.setattr(threading.Thread, "start", hong)
        with pytest.raises(RuntimeError, match=LOI):
            ham()


def test_lo_quet(e, monkeypatch):
    c = ScanJobController(e)
    _start_hong(monkeypatch, lambda: c.start(["x"], "file"))
    assert not c.running and not scan_jobs._DANG_CHAY
    assert e.cong_bao_tri.viec_dang_chay() == [], "lease phải được trả"


def test_dung_kho(e, monkeypatch, tmp_path):
    c = FingerprintJobController(e)
    _start_hong(monkeypatch, lambda: c.start(str(tmp_path), "new"))
    assert not c.running and fingerprint_progress._SO_DUNG_KHO.dang_chay_cua(e) is None
    assert c.error == LOI and c.snapshot().status == "failed"


def test_lo_nguon_chung(e, monkeypatch):
    c = CommonOriginalJobController(e)
    _start_hong(monkeypatch, lambda: c.start(["x", "y"], "file"))
    assert not c.running and common_original_jobs._SO_NGUON_CHUNG.dang_chay_cua(e) is None
    assert c.error == LOI
