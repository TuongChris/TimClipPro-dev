# -*- coding: utf-8 -*-
"""Bảng «Hồ sơ đích»: cột «Mã tab» trộn mã số (tab đã ghim) với chữ (hồ sơ chốt tab theo tên).

PC2 12/10/2026, console Stable: «Serialization of dataframe to Arrow table was unsuccessful … Could not
convert 'theo tên — chốt ở lần gửi đầu' with type str: tried to convert to int64 … Conversion failed for
column Mã tab». Sửa ở TẦNG HIỂN THỊ: cột hiện toàn chuỗi; mã tab lưu trong DB giữ nguyên kiểu số.

Bẫy kiểm thử: logger của Streamlit đặt ``propagate=False`` nên ``caplog`` (gắn ở logger gốc) KHÔNG
BAO GIỜ thấy cảnh báo này — khẳng định «không có cảnh báo» qua ``caplog`` luôn xanh kể cả trên mã lỗi.
Ở đây gắn bộ ghi thẳng vào logger ``streamlit.dataframe_util`` (nơi phát cảnh báo).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


class _BoGhi(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.dong: list = []

    def emit(self, record):
        self.dong.append(record.getMessage())


def test_bo_ghi_bat_duoc_canh_bao_arrow_that():
    """Đối chứng dương: bộ ghi phải bắt được cảnh báo khi cột THẬT SỰ trộn kiểu."""
    from streamlit import dataframe_util

    bo_ghi = _BoGhi()
    lg = logging.getLogger("streamlit.dataframe_util")
    lg.addHandler(bo_ghi)
    try:
        dataframe_util.convert_pandas_df_to_arrow_bytes(
            pd.DataFrame({"Mã tab": [82967006, "theo tên — chốt ở lần gửi đầu"]}))
    finally:
        lg.removeHandler(bo_ghi)
    assert any("Serialization of dataframe to Arrow table was unsuccessful" in x for x in bo_ghi.dong)


def test_bang_ho_so_ma_tab_tron_so_va_chu_khong_loi_arrow(tmp_path, monkeypatch):
    import sheet_destinations as sd
    from outbox_gia import khoa_gia

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    db = at.session_state.eng.sqlite_file
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    chung = dict(worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh",
                 workspace="mac_dinh")
    co_ma = sd.tao_dich(db, ten="Có mã tab", spreadsheet_id="1" + "a" * 43, worksheet_id=82967006,
                        **chung)
    sd.tao_dich(db, ten="Theo tên", spreadsheet_id="1" + "b" * 43, worksheet_id=None, **chung)

    bo_ghi = _BoGhi()
    lg = logging.getLogger("streamlit.dataframe_util")
    lg.addHandler(bo_ghi)
    try:
        at.run()
    finally:
        lg.removeHandler(bo_ghi)
    assert not at.exception
    assert not [x for x in bo_ghi.dong if "Arrow" in x], bo_ghi.dong
    bang = next(df.value for df in at.dataframe if "Mã tab" in df.value.columns)
    assert set(bang["Mã tab"]) == {"82967006", "theo tên — chốt ở lần gửi đầu"}
    # Giá trị LƯU không đổi kiểu: mã tab vẫn là số nguyên trong hồ sơ.
    assert sd.lay_dich(db, co_ma.id).worksheet_id == 82967006
