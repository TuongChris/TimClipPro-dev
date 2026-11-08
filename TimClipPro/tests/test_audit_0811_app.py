# -*- coding: utf-8 -*-
"""Audit 08/11 — giao diện: tên file từ tiêu đề YouTube không phá Markdown; nút hỏi YouTube khoá khi đang đồng bộ."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def _app(tmp_path, monkeypatch):
    import streamlit

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    return at


def test_duong_dan_co_dau_backtick_khong_thanh_anh_tu_xa(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    doc = "D:\\V\\x` ![a](https://evil.example/p.png) `y [abcdefghij1].mkv"
    at.session_state.job.update(
        {
            "running": False,
            "kind": "tai_video",
            "error": "",
            "results": [
                {
                    "url": "https://youtu.be/abcdefghij1",
                    "trang_thai": "xong",
                    "duong_dan": doc,
                    "tieu_de": "T",
                    "chat_luong": "",
                    "ghi_chu": "",
                }
            ],
        }
    )
    at.run()
    assert not at.exception
    assert all("![a](" not in m.value for m in at.markdown)


def test_nut_hoi_youtube_o_tab_dong_bo_khoa_khi_dang_dong_bo(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    next(t for t in at.text_input if t.label == "Link kênh YouTube của bạn").set_value(
        "https://www.youtube.com/@K"
    )
    next(
        t for t in at.text_input if t.label.startswith("Thư mục kho clip gốc")
    ).set_value(str(tmp_path / "kho"))
    at.run()
    nut = {b.label: b for b in at.button}
    assert not nut[
        "👀 Xem danh sách video của kênh"
    ].disabled  # đối chứng: rảnh thì bấm được
    at.session_state.job_dong_bo.update({"running": True, "kind": "channel"})
    at.run()
    nut = {b.label: b for b in at.button}
    assert nut["👀 Xem danh sách video của kênh"].disabled
    assert nut["🔍 Kiểm tra còn thiếu video nào"].disabled
