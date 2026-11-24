# -*- coding: utf-8 -*-
"""Chống bấm nhầm + chữ dễ hiểu + nút chọn còn sót (đợt khảo sát giao diện 24/11: việc nhỏ #6, #24, #26, #37, #41).

AppTest, dữ liệu tổng hợp trong thư mục tạm, không mạng: Google Sheets, hộp thoại chọn file và File Explorer đều bị thay.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
TAO_LAI = "🔄 Tạo lại kho từ đầu"


def _app(tmp_path, monkeypatch):
    import streamlit

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _chay(x):
    """Chạy lại app (``x`` = AppTest hoặc một widget vừa đặt giá trị) và trả AppTest."""
    at = x.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _nut(at, nhan: str):
    return next(b for b in at.button if b.label == nhan)


def _o_xac_nhan(at, dau: str):
    return [c for c in at.checkbox if (c.key or "").startswith(dau)]


# ---------------------------------------------------------------- #24: hỏi lại trước nút phá huỷ
def test_tao_lai_kho_dang_co_van_tay_phai_tick_va_khong_con_la_nut_chinh(tmp_path, monkeypatch):
    a, b = tmp_path / "A", tmp_path / "B"
    a.mkdir()
    b.mkdir()
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    eng.add_kho("Kho A", str(a))
    eng.add_kho("Kho B", str(b))
    eng.use_kho("Kho A")
    # Kho đã có vân tay (dựng thật mất nhiều giờ) — giả danh sách clip, không dựng vân tay thật.
    monkeypatch.setattr(eng, "db_clips", lambda *a_, **k: [{"ten": "x.opus", "so_hash": 9, "duong_dan": "x.opus"}])
    _chay(at)
    nut = _nut(at, TAO_LAI)
    assert nut.disabled and nut.proto.type != "primary"
    o = _o_xac_nhan(at, "xac_nhan_thay_kho::Kho A::")
    assert len(o) == 1 and "Kho A" in o[0].label
    _chay(o[0].check())
    assert not _nut(at, TAO_LAI).disabled
    eng.use_kho("Kho B")
    _chay(at)
    assert _nut(at, TAO_LAI).disabled, "đổi kho là phải tick lại"


def test_tao_lai_kho_chua_co_van_tay_khong_hoi_lai(tmp_path, monkeypatch):
    """Kho trống: không có gì để mất — nút dùng được ngay (trang vẫn hướng dẫn bấm «Tạo lại kho từ đầu» lần đầu)."""
    a = tmp_path / "A"
    a.mkdir()
    at = _app(tmp_path, monkeypatch)
    at.session_state.eng.add_kho("Kho A", str(a))
    at.session_state.eng.use_kho("Kho A")
    _chay(at)
    assert not _nut(at, TAO_LAI).disabled
    assert not _o_xac_nhan(at, "xac_nhan_thay_kho::")


def test_day_danh_sach_len_sheet_phai_tick_theo_tung_kho(tmp_path, monkeypatch):
    import danh_sach_video
    import sheets

    a, b = tmp_path / "A", tmp_path / "B"
    for d in (a, b):
        d.mkdir()
        (d / "20260101 - Video thu [abcdefghijk].opus").write_bytes(b"x")
    da_day = []
    monkeypatch.setattr(sheets.SheetsExporter, "san_sang", lambda self: True)
    monkeypatch.setattr(danh_sach_video, "day_len_sheet", lambda kq, link: da_day.append(kq.ten_kho) or (True, "Đã ghi."))
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    eng.add_kho("Kho A", str(a))
    eng.add_kho("Kho B", str(b))
    eng.use_kho("Kho A")
    at.session_state["sheet_link"] = "https://docs.google.com/spreadsheets/d/gia/edit"
    _chay(at)
    _chay(at.button(key="dsv_quet").click())
    for nut, xn in (("dsv_day_sheet", "xac_nhan_day_dsv::Kho A"), ("dsv_day_tat_ca", "xac_nhan_day_tat_ca::Kho A")):
        assert at.button(key=nut).disabled, nut
        _chay(at.checkbox(key=xn).check())
        assert not at.button(key=nut).disabled, nut
    _chay(at.button(key="dsv_day_sheet").click())
    assert da_day == ["Kho A"]
    _chay(at.selectbox(key="dsv_kho").set_value("Kho B"))
    _chay(at.button(key="dsv_quet").click())
    assert at.button(key="dsv_day_sheet").disabled and at.button(key="dsv_day_tat_ca").disabled, "đổi kho: tick lại"


# ---------------------------------------------------------------- #6: gợi ý sai ở thanh bên + cảnh báo lệch mặc định
def test_canh_bao_khi_tham_so_nhan_dien_khac_mac_dinh(tmp_path, monkeypatch):
    import json

    data = tmp_path / "data"
    data.mkdir()
    (data / "cau_hinh.json").write_text(json.dumps({"min_hash": 10, "chunk_s": 1800}), encoding="utf-8")
    at = _app(tmp_path, monkeypatch)
    canh = [w.value for w in at.sidebar.warning if "khác mặc định" in w.value]
    assert len(canh) == 1, canh
    assert "Số hash tối thiểu" in canh[0] and "10" in canh[0] and "15" in canh[0]
    assert "Độ dài mỗi khúc" in canh[0] and "1800" in canh[0] and "3600" in canh[0]
    assert "Giám sát" in canh[0] and "Khúc gối" not in canh[0]
    goi_y_hash = next(s for s in at.sidebar.slider if s.label == "Số hash tối thiểu").help
    goi_y_khuc = next(n for n in at.sidebar.number_input if n.label.startswith("Độ dài mỗi khúc")).help
    assert "giảm xuống" not in goi_y_hash and "1800" not in goi_y_khuc
    assert "Giám sát" in goi_y_hash and "Giám sát" in goi_y_khuc


def test_tham_so_mac_dinh_thi_khong_canh_bao(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    assert not [w for w in at.sidebar.warning if "khác mặc định" in w.value]


# ---------------------------------------------------------------- #37, #41: chữ dễ hiểu ở Lịch sử / Thống kê
def test_lich_su_chu_viet_ba_nut_tai_co_giai_thich_thong_ke_noi_ro_ngay(tmp_path, monkeypatch):
    from engine import Engine, ScanResult
    from test_bao_cao_v2 import _bc, _kq_ca_that

    e = Engine(data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ketqua"))
    e.save_job(ScanResult(source_name="Lượt lỗi", source_ref="u1", status="error", note="mạng"), "youtube")
    kq = _kq_ca_that()
    kq.bao_cao = _bc(kq)
    e.save_job(kq, "youtube")
    at = _app(tmp_path, monkeypatch)
    bang = next(d.value for d in at.dataframe if {"ID", "Trạng thái", "Kho", "Phạm vi"} <= set(d.value.columns))
    assert sorted(bang["Trạng thái"]) == ["Lỗi", "Quét xong"]
    giai_thich = {el.proto.label: el.proto.help for el in at.get("download_button")}
    for nhan in ("⬇️ Tải báo cáo ngang (34 cột)", "⬇️ Tải báo cáo dọc (16 cột)", "⬇️ Tải CSV lần quét này"):
        assert giai_thich.get(nhan), nhan
    assert any("ngày quét đầu tiên" in m.value for m in at.markdown), "biểu đồ theo tháng nói rõ tính theo ngày nào"


def test_chu_thich_trung_ten_dung_voi_ma():
    nguon = APP_PY.read_text(encoding="utf-8")
    assert "« (2)»" not in nguon and "«_2»" in nguon


# ---------------------------------------------------------------- #26: nút chọn còn sót + mở thư mục kết quả
def _thay_chon(monkeypatch, files: list):
    import tai_video_goc

    monkeypatch.setattr(tai_video_goc, "chon_file", lambda ban_dau="", nhieu=False, tieu_de="": list(files))


def test_chon_file_cookie_youtube_o_thanh_ben(tmp_path, monkeypatch):
    ck = str(tmp_path / "cookies.txt")
    _thay_chon(monkeypatch, [ck])
    at = _app(tmp_path, monkeypatch)
    _chay(at.button(key="chon_cookie_youtube").click())
    assert at.text_input(key="ytdlp_cookiefile").value == ck
    assert at.session_state.eng.config.ytdlp_cookiefile == ck
    _chay(at.text_input(key="ytdlp_cookiefile").set_value("gõ dở"))
    assert at.session_state.eng.config.ytdlp_cookiefile == "gõ dở"
    _chay(at.button(key="chon_cookie_youtube").click())
    assert at.text_input(key="ytdlp_cookiefile").value == ck, "chọn lại đúng file cũ vẫn có tác dụng"
    assert at.session_state.eng.config.ytdlp_cookiefile == ck


def test_chon_file_khoa_google(tmp_path, monkeypatch):
    khoa = str(tmp_path / "khoa_gia.json")
    _thay_chon(monkeypatch, [khoa])
    at = _app(tmp_path, monkeypatch)
    _chay(at.button(key="chon_xt_duong").click())
    assert at.text_input(key="xt_duong").value == khoa


def test_luu_csv_xong_co_nut_mo_thu_muc_ketqua(tmp_path, monkeypatch):
    import os

    from test_app_cau_tom_tat_ket_qua import _ok

    mo = []
    monkeypatch.setattr(os, "startfile", mo.append, raising=False)
    at = _app(tmp_path, monkeypatch)
    at.session_state.job.update({"running": False, "kind": "scan", "results": [_ok("Video mot", "vidthu00000")],
                                 "error": "", "pct": 1.0, "msg": ""})
    _chay(at)
    assert not [b for b in at.button if b.key == "mo_tm_ketqua"], "chưa lưu gì thì chưa cần nút mở"
    _chay(_nut(at, "💾 Lưu CSV vào thư mục ketqua\\").click())
    assert any("Đã lưu" in s.value for s in at.success)
    _chay(at.button(key="mo_tm_ketqua").click())
    assert mo == [str(tmp_path / "ketqua")]
