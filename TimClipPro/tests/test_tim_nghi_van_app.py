# -*- coding: utf-8 -*-
"""Tab «🔎 Tìm video nghi vấn» (AppTest): chưa có khoá → chỉ nói nơi đặt khoá, khoá nút «Tìm», 0 yêu cầu; có khoá → bảng
kết quả, chọn dòng, «Đưa vào ô quét YouTube» ghi link vào ô của tab «▶️ Quét YouTube» — không gọi mạng thêm, không tự
quét. Không mạng thật: transport giả ``tests/youtube_api_gia.py``."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

import tim_nghi_van as tn
import youtube_api as ya
import youtube_api_gia as gia

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
KENH_KHAC = "UC" + "kenhKhac" + "0" * 14


def _ma(i):
    return f"vid{i:08d}"


def _tim(*muc):
    return {"items": [{"id": {"kind": "youtube#video", "videoId": ma},
                       "snippet": {"publishedAt": "2026-08-01T03:00:00Z", "channelId": kenh, "title": f"Tổng hợp {ma}",
                                   "channelTitle": "Kênh lạ"}} for ma, kenh in muc]}


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    return at


def _van_ban(at):
    return "\n".join(str(x.value) for nhom in (at.warning, at.info, at.caption, at.markdown, at.error, at.success)
                     for x in nhom)


def _kho(tmp_path, at, **meta):
    kho = tmp_path / "kho_thu"
    kho.mkdir()
    (kho / "clips_meta.json").write_text(json.dumps(
        {f"20260101 - {ten} [{ma}].opus": {"id": ma, "title": ten} for ten, ma in meta.items()}, ensure_ascii=False),
        encoding="utf-8")
    at.session_state.eng.add_kho("Kho thử", str(kho))
    at.run()
    assert not at.exception


def test_tab_chua_co_khoa_chi_noi_dat_khoa_va_khoa_nut_tim(tmp_path, monkeypatch):
    tp = gia.lap_transport(monkeypatch)
    at = _app(tmp_path, monkeypatch)
    _kho(tmp_path, at, **{"Clip một": _ma(1)})
    assert ya.duong_dan_khoa_api(at.session_state.eng.data_dir) in _van_ban(at)
    assert at.button(key="tim_nut").disabled
    assert tp.dem() == 0


def test_tab_tim_hien_ket_qua_va_dua_link_vao_o_quet(api_youtube_gia, tmp_path, monkeypatch):
    vp = _ma(9)
    for m in (_ma(1), _ma(2)):
        api_youtube_gia.video[m] = gia.video_gia(m)
    api_youtube_gia.video[vp] = gia.video_gia(vp, title="Tổng hợp 10 giờ", duration="PT10H", ten_kenh="Kênh lạ")
    at = _app(tmp_path, monkeypatch)
    _kho(tmp_path, at, **{"Clip một": _ma(1), "Clip hai": _ma(2)})
    assert at.number_input(key="tim_toi_da").value == tn.TOI_DA_MAC_DINH
    assert not at.button(key="tim_nut").disabled
    # kênh gốc (videos.list theo bảng) → 2 truy vấn → thời lượng (videos.list theo bảng)
    api_youtube_gia.kich_ban = [None, _tim((vp, KENH_KHAC), (_ma(1), gia.KENH_GIA)), _tim((vp, KENH_KHAC))]
    at.button(key="tim_nut").click().run()
    assert not at.exception
    assert [y.endpoint for y in api_youtube_gia.yeu_cau] == ["videos", "search", "search", "videos"]
    bang = next(df.value for df in at.dataframe if "Khớp bao nhiêu truy vấn" in df.value.columns)
    assert tuple(bang.columns) == tn.COT and len(bang) == 1
    assert (bang.iloc[0]["Tiêu đề"], bang.iloc[0]["Khớp bao nhiêu truy vấn"]) == ("Tổng hợp 10 giờ", 2)
    at.session_state["tim_bang_1"] = {"selection": {"rows": [0], "columns": [], "cells": []}}
    at.run()
    at.button(key="tim_dua").click().run()
    assert not at.exception
    link = f"https://www.youtube.com/watch?v={vp}"
    assert next(x for x in at.text_area if x.label.startswith("Dán link YouTube")).value == link
    assert "Đã đưa link vào ô «Dán link YouTube»" in _van_ban(at)
    assert api_youtube_gia.dem() == 4, "đưa vào ô quét không gọi mạng, không tự quét"


def test_tab_tim_giu_ket_qua_khi_nguoi_dung_cham_widget_luc_dang_tim(api_youtube_gia, tmp_path, monkeypatch):
    """Người dùng chạm widget khi đang tìm → Streamlit chen lượt chạy lại ở điểm nhường kế tiếp (đọc/ghi st.session_state, thoát spinner).
    Kết quả đã tốn hạn mức phải được lưu TRƯỚC điểm đó, không thì lượt chạy lại không thấy gì."""
    from streamlit.runtime.scriptrunner_utils.script_requests import RerunData
    from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx

    vp = _ma(9)
    for m in (_ma(1), vp):
        api_youtube_gia.video[m] = gia.video_gia(m)
    at = _app(tmp_path, monkeypatch)
    _kho(tmp_path, at, **{"Clip một": _ma(1)})
    tim_that = tn.tim

    def tim_roi_bi_chen(*a, **k):
        kq = tim_that(*a, **k)
        get_script_run_ctx().script_requests.request_rerun(RerunData())   # = người dùng chạm widget lúc này
        return kq

    monkeypatch.setattr(tn, "tim", tim_roi_bi_chen)
    api_youtube_gia.kich_ban = [None, _tim((vp, KENH_KHAC))]
    at.button(key="tim_nut").click().run()
    assert not at.exception
    assert [y.endpoint for y in api_youtube_gia.yeu_cau] == ["videos", "search", "videos"]
    assert any("Khớp bao nhiêu truy vấn" in df.value.columns for df in at.dataframe), "kết quả đã tốn hạn mức bị mất"
