# -*- coding: utf-8 -*-
"""Giao diện cho báo cáo V2 (AppTest, không mạng): xuất lại từ ảnh chụp ở tab Lịch sử,
lịch sử cũ nói rõ giới hạn, công tắc bổ sung ngày gốc mặc định TẮT."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

import bao_cao_v2 as v2
from engine import Engine, ScanResult
from test_bao_cao_v2 import _bc, _kq_ca_that

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def _du_lieu(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "ketqua"
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(out_dir))
    e = Engine(data_dir=str(data_dir), out_dir=str(out_dir))
    id_cu = e.save_job(ScanResult(source_name="Lượt quét cũ", source_ref="u", status="ok"),
                       "youtube")
    kq = _kq_ca_that()
    kq.bao_cao = _bc(kq)
    id_moi = e.save_job(kq, "youtube")
    return id_cu, id_moi


def test_lich_su_v2_tai_lai_tu_anh_chup(tmp_path, monkeypatch):
    id_cu, id_moi = _du_lieu(tmp_path, monkeypatch)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    chon = next(sb for sb in at.selectbox if sb.label == "Xem chi tiết lần quét số")
    assert chon.value == id_moi
    assert any("chính sách báo cáo V2" in c.value for c in at.caption)
    nut = [el.proto.label for el in at.get("download_button")]
    assert "⬇️ Tải báo cáo ngang (34 cột)" in nut and "⬇️ Tải báo cáo dọc (16 cột)" in nut
    eng = at.session_state.eng
    dong = eng.dong_bao_cao_job(id_moi, dang_ngang=True)[0]
    assert dong[5] == "Video tổng hợp thử (Phần 2)"
    assert dong[8].endswith("?t=915")

    at = chon.set_value(id_cu).run()
    assert not at.exception
    assert any("Lần quét cũ (trước báo cáo V2)" in c.value for c in at.caption)
    nut = [el.proto.label for el in at.get("download_button")]
    assert "⬇️ Tải báo cáo ngang (34 cột)" not in nut


def test_cong_tac_bo_sung_ngay_goc_mac_dinh_tat(tmp_path, monkeypatch):
    _du_lieu(tmp_path, monkeypatch)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    o = next(c for c in at.sidebar.checkbox if c.label == "Bổ sung ngày đăng gốc từ YouTube")
    assert o.value is False and at.session_state.eng.config.bo_sung_ngay_goc is False
    at = o.check().run()
    assert at.session_state.eng.config.bo_sung_ngay_goc is True


def test_anh_chup_trong_lich_su_la_chinh_sach_v2(tmp_path, monkeypatch):
    id_cu, id_moi = _du_lieu(tmp_path, monkeypatch)
    e = Engine(data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ketqua"))
    assert e.bao_cao_cua_job(id_moi).chinh_sach == v2.CHINH_SACH_V2
    assert e.bao_cao_cua_job(id_cu) is None
