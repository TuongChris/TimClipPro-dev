# -*- coding: utf-8 -*-
"""Audit F-1 (tổng hợp, không mạng): phiên NHẬN LẠI lô đang chạy của phiên khác (tải lại trang / mở tab
thứ hai giữa lúc quét) KHÔNG được gắn mãi vào Engine của phiên CŨ.

Lô nhận lại xong rồi, lô kế tiếp bắt đầu từ phiên mới phải dùng kho, ngưỡng và cookie mà thanh bên của CHÍNH
phiên này đang hiện (``eng`` của nó), không phải của phiên cũ.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from engine import Engine, ScanResult
from scan_jobs import ScanJobController

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def _cho_xong(ctl, han=30.0):
    het = time.monotonic() + han
    while ctl.running and time.monotonic() < het:
        time.sleep(0.02)
    assert not ctl.running


def _ghi_lai_va_giu(monkeypatch, giu_url: str):
    """Patch scan_youtube: record the pinned state actually used, hold on ``giu_url``."""
    thay: list = []
    di_tiep = threading.Event()

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        thay.append({"url": url, "kho": self.kho_dang_dung, "db": Path(self.db_file).name,
                     "min_hash": self.config.min_hash,
                     "cookie": self.config.ytdlp_cookiefile})
        if url == giu_url:
            di_tiep.wait(20)
        r = ScanResult(source_name=url, source_ref=url)
        r.source_id = url
        return r

    monkeypatch.setattr(Engine, "scan_youtube", scan_youtube)
    return thay, di_tiep


def test_phien_nhan_lai_lo_xong_roi_lo_moi_dung_kho_va_cau_hinh_cua_phien_nay(tmp_path, monkeypatch):
    # Session A: kho «KhoA», default thresholds, no cookie.
    engA = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    engA.add_kho("KhoA")
    engA.add_kho("KhoB")
    engA.use_kho("KhoA")
    min_hash_A = engA.config.min_hash
    # Session B (reload / second tab): a fresh Engine on the SAME data_dir.
    engB = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    assert engB is not engA

    thay, di_tiep = _ghi_lai_va_giu(monkeypatch, giu_url="a")
    ctlA = ScanJobController(engA)
    ctlA.start(["a"], "youtube")
    try:
        # Exactly what app.py does for a new session (each rerun: ScanJobController.cua_phien).
        ctl_B = ScanJobController.cua_phien(engB, None, dang_hien_lo=False)
        assert ctl_B is ctlA, "reattach to the running batch is the intended behaviour"
        assert ScanJobController.cua_phien(engB, ctl_B, dang_hien_lo=True) is ctl_B
    finally:
        di_tiep.set()
    _cho_xong(ctl_B)
    # Rerun of B while its screen still shows the finished batch (results not copied yet): kept.
    assert ScanJobController.cua_phien(engB, ctl_B, dang_hien_lo=True) is ctl_B

    # Batch ended. Owner keeps working in session B: sidebar changes only B's Engine.
    engB.use_kho("KhoB")
    engB.config.min_hash = 77
    engB.config.ytdlp_cookiefile = str(tmp_path / "c_gia_khong_ton_tai.txt")
    assert engB.kho_dang_dung == "KhoB"           # what B's sidebar shows

    # B clicks «Bắt đầu quét»: the click reruns app.py (cua_phien, results already copied → job not
    # running), then chay_quet() calls start() on the session's scan_controller.
    ctl_B = ScanJobController.cua_phien(engB, ctl_B, dang_hien_lo=False)
    ctl_B.start(["b"], "youtube")
    _cho_xong(ctl_B)

    lo_b = [x for x in thay if x["url"] == "b"]
    assert len(lo_b) == 1
    da_dung = lo_b[0]
    assert (da_dung["kho"], da_dung["min_hash"], da_dung["cookie"]) == (
        "KhoB", 77, engB.config.ytdlp_cookiefile), (
        f"new batch in session B ran with kho={da_dung['kho']!r} min_hash={da_dung['min_hash']} "
        f"cookie={da_dung['cookie']!r} (session A had KhoA/{min_hash_A}/'') while B's sidebar "
        f"shows KhoB/77/cookie")


def test_app_phien_moi_sau_lo_cua_phien_cu_quet_tren_engine_cua_chinh_no(tmp_path, monkeypatch):
    """Same defect through the real app.py (Streamlit AppTest), two sessions on one data dir."""
    import streamlit
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)

    at1 = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at1.exception
    eng1 = at1.session_state.eng
    eng1.add_kho("KhoA")
    eng1.add_kho("KhoB")
    eng1.use_kho("KhoA")

    thay, di_tiep = _ghi_lai_va_giu(monkeypatch, giu_url="a")
    ctl1 = at1.session_state.scan_controller
    ctl1.start(["a"], "youtube")
    try:
        at2 = AppTest.from_file(str(APP_PY), default_timeout=120).run()   # F5 / second tab
        assert not at2.exception
        assert at2.session_state.scan_controller is ctl1, "reattach while running (intended)"
        assert at2.session_state.job.get("running") is True
    finally:
        di_tiep.set()
    _cho_xong(ctl1)
    at2.run()                       # session B sees the batch finished
    assert not at2.exception
    assert not at2.session_state.job.get("running")

    eng2 = at2.session_state.eng
    assert eng2 is not eng1
    eng2.use_kho("KhoB")            # what the «Kho đang dùng» selectbox does
    eng2.config.min_hash = 77       # what the «Số hash tối thiểu» slider writes
    at2.run()
    assert not at2.exception
    assert "Kho «KhoB»" in "\n".join(str(w.value) for w in list(at2.warning) + list(at2.info))

    # «Bắt đầu quét» → chay_quet() → scan_controller.start(...) of this session.
    at2.session_state.scan_controller.start(["b"], "youtube")
    _cho_xong(at2.session_state.scan_controller)

    da_dung = [x for x in thay if x["url"] == "b"][0]
    assert (da_dung["kho"], da_dung["min_hash"]) == ("KhoB", 77), (
        f"session B's sidebar shows KhoB/min_hash 77 but its batch ran on "
        f"kho={da_dung['kho']!r} min_hash={da_dung['min_hash']} (session A's Engine)")


def _kich_ban_banner_phien_nhan_lai():
    import streamlit as st

    import ui_gui_sheets

    # Phiên nhận lại lô: ``job`` không có «tab_quet» → app.py truyền "".
    ui_gui_sheets.banner_lo_dang_chay(st.session_state["eng_gia"], "ho_so_dang_gui", "Hồ sơ A", "")


def test_banner_phien_nhan_lai_khong_bao_lua_chon_chi_luu_cuc_bo():
    """F-1 phụ: phiên nhận lại không biết tab đã bắt đầu lượt — không được báo «lựa chọn «Chỉ lưu cục bộ»
    dùng cho lượt tiếp theo» (lựa chọn đó không ai chọn)."""
    from types import SimpleNamespace

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_kich_ban_banner_phien_nhan_lai, default_timeout=60)
    at.session_state["eng_gia"] = SimpleNamespace(sqlite_file="khong_dung.db")
    at.run()
    assert not at.exception
    assert not at.info, [i.value for i in at.info]
