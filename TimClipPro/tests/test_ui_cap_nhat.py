# -*- coding: utf-8 -*-
"""Bảng «Phiên bản và cập nhật» (brief §15): bản đang chạy, bản đang kích hoạt, bản mới chờ áp dụng, việc
đang chạy, lỗi/cách ly, hoãn — CHỈ ĐỌC trạng thái (không gọi mạng), nút hoãn ghi file hoãn của cài đặt."""
import json
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

import maintenance_gate as mg
import managed_update as mu


def _kich_ban():
    import streamlit as st

    import ui_cap_nhat

    ui_cap_nhat.ve_phien_ban(st.session_state["eng_gia"])


def _eng(tmp_path):
    data = tmp_path / "state" / "data"
    data.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(data_dir=str(data), cong_bao_tri=mg.CongBaoTri(str(data)))


def _chay(tmp_path, monkeypatch, env):
    for k in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_INSTALLATION_ROOT", "TIMCLIP_RELEASE"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    at = AppTest.from_function(_kich_ban, default_timeout=60)
    at.session_state["eng_gia"] = _eng(tmp_path)
    return at.run()


def _chu(at):
    return " ".join(str(x.value) for x in [*at.caption, *at.markdown, *at.info, *at.warning,
                                             *at.error, *at.success])


def test_legacy_noi_ro_khong_tu_cap_nhat(tmp_path, monkeypatch):
    at = _chay(tmp_path, monkeypatch, {})
    assert not at.exception and "không tự cập nhật" in _chu(at)


def test_managed_hien_ban_chay_kich_hoat_va_ban_moi_cho_ap_dung(tmp_path, monkeypatch):
    goc = tmp_path / "cai dat"
    cd = mu.CaiDat(goc=str(goc), state_root=str(tmp_path / "state"))
    mu.ghi_json_nguyen_tu(cd.file_trang_thai("current.json"),
                          {"phien_ban": "1.0.0", "release": cd.release_dir("1.0.0")})
    mu.ghi_json_nguyen_tu(cd.file_trang_thai("journal.json"),
                          {"trang_thai": mu.STAGED, "ung_vien": "1.1.0", "loi": "",
                           "lich_su": [{"trang_thai": mu.STAGED, "luc": "2026-10-07 21:00:00"}]})
    mu.ghi_json_nguyen_tu(cd.file_trang_thai("quarantine.json"), {"1.0.5": {"ly_do": "health lỗi"}})
    at = _chay(tmp_path, monkeypatch, {"TIMCLIP_RUNTIME_MODE": "managed",
                                       "TIMCLIP_INSTALLATION_ROOT": str(goc), "TIMCLIP_RELEASE": "1.0.0"})
    chu = _chu(at)
    assert not at.exception
    assert "1.0.0" in chu and "1.1.0" in chu and "1.0.5" in chu and "2026-10-07 21:00:00" in chu


def test_ban_dang_chay_cu_hon_ban_kich_hoat_thi_bao_mo_lai(tmp_path, monkeypatch):
    goc = tmp_path / "cai dat"
    cd = mu.CaiDat(goc=str(goc), state_root=str(tmp_path / "state"))
    mu.ghi_json_nguyen_tu(cd.file_trang_thai("current.json"),
                          {"phien_ban": "1.1.0", "release": cd.release_dir("1.1.0")})
    at = _chay(tmp_path, monkeypatch, {"TIMCLIP_RUNTIME_MODE": "managed",
                                       "TIMCLIP_INSTALLATION_ROOT": str(goc), "TIMCLIP_RELEASE": "1.0.0"})
    assert any("mở lại" in w.value for w in at.warning)


def test_nut_hoan_ghi_file_hoan_cua_cai_dat(tmp_path, monkeypatch):
    goc = tmp_path / "cai dat"
    cd = mu.CaiDat(goc=str(goc), state_root=str(tmp_path / "state"))
    mu.ghi_json_nguyen_tu(cd.file_trang_thai("current.json"),
                          {"phien_ban": "1.0.0", "release": cd.release_dir("1.0.0")})
    at = _chay(tmp_path, monkeypatch, {"TIMCLIP_RUNTIME_MODE": "managed",
                                       "TIMCLIP_INSTALLATION_ROOT": str(goc), "TIMCLIP_RELEASE": "1.0.0"})
    next(b for b in at.button if b.label.startswith("⏸ Hoãn cập nhật")).click().run()
    assert mu.doc_hoan(str(goc)) is not None
    d = json.loads(open(cd.file_trang_thai(mu.TEN_HOAN), encoding="utf-8").read())
    assert d["den"] > 0
