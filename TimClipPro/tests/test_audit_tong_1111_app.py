# -*- coding: utf-8 -*-
"""Audit tổng 11/11 — giao diện: không tạo kho khi có tác vụ; nút sửa hồ sơ Sheets gắn đúng hồ sơ đã vẽ."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

import lich_su
import sheet_destinations as sd
from outbox_gia import khoa_gia  # noqa: E402  (đồ giả dùng chung của dự án)

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def test_dang_co_tac_vu_thi_khong_tao_kho_moi(tmp_path, monkeypatch):
    """Vá metadata chạy trên CHÍNH Engine của phiên (không ghim bản sao): «Tạo kho» giữa chừng chuyển kho đang dùng,
    các bản vá sau ghi danh tính kho MỚI vào snapshot của kho cũ. Ô chọn kho và nút xoá kho vốn đã khoá khi có tác vụ."""
    import streamlit

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    next(t for t in at.text_input if t.label == "Tên kho").set_value("Kho mới")
    at.run()
    assert not next(
        b for b in at.button if b.label == "Tạo kho"
    ).disabled  # tiền đề: không có tác vụ thì bấm được
    at.session_state.job.update(
        {
            "running": True,
            "pct": 0.0,
            "msg": "",
            "results": [],
            "error": "",
            "kind": "metadata_network",
        }
    )
    at.run()
    assert not at.exception
    assert next(b for b in at.button if b.label == "Tạo kho").disabled


def _kich_ban_ho_so(db):
    from types import SimpleNamespace

    import ui_gui_sheets

    ui_gui_sheets._ve_ho_so(
        SimpleNamespace(
            sqlite_file=db, runtime=SimpleNamespace(workspace="mac_dinh"), HEADER=[]
        )
    )


def test_xoa_ho_so_vua_bien_mat_khong_xoa_nham_ho_so_khac(tmp_path):
    """Hai tab trình duyệt: tab kia xoá hồ sơ đang hiện ở tab này; bấm «Xoá» ở tab này (bản vẽ cũ) → ô chọn lùi sang
    hồ sơ còn lại và nút xoá (khoá chung «hs_xoa») xoá NHẦM nó."""
    db = str(tmp_path / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    for ten, c in (("A", "a"), ("B", "b")):
        sd.tao_dich(
            db,
            ten=ten,
            spreadsheet_id="1" + c * 43,
            worksheet_id=None,
            worksheet_ten="KetQuaQuet",
            schema_id=sd.SCHEMA_NGANG,
            xac_thuc_ref="mac_dinh",
            workspace="mac_dinh",
        )
    at = AppTest.from_function(
        _kich_ban_ho_so, kwargs={"db": db}, default_timeout=60
    ).run()
    assert not at.exception
    dang_hien = at.selectbox(key="hs_chon").value
    con_lai = {d.id for d in sd.ds_dich(db)} - {dang_hien}
    assert len(con_lai) == 1
    sd.xoa_dich(db, dang_hien)  # tab khác xoá đúng hồ sơ đang hiện ở tab này
    next(b for b in at.button if b.label.startswith("🗑 Xoá")).click().run()
    assert not at.exception
    assert {d.id for d in sd.ds_dich(db)} == con_lai
