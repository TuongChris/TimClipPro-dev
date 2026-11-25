# -*- coding: utf-8 -*-
"""Thanh bên «Tình trạng hệ thống»: dung lượng đệm audio của lượt quét + chỗ trống ổ chứa dữ liệu, cảnh báo vàng khi
ổ gần đầy (một phần việc nhỏ #1) + đoạn trích bằng chứng. Luật dọn đệm D-66 (25/11): không có nút xoá thẳng — nút
«🧹 Dọn đệm audio…» chỉ mở hộp xem trước (``test_giu_bang_chung_dem.py``).

Synthetic: thư mục dữ liệu tạm, hai file đệm giả; chỗ trống ổ giả qua ``shutil.disk_usage``.
"""

import shutil
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def _mo(tmp_path, monkeypatch, trong_gb):
    dem = tmp_path / "data" / "downloads"
    dem.mkdir(parents=True)
    (dem / "aaaaaaaaaaa.opus").write_bytes(b"x" * 3000)
    (dem / "bbbbbbbbbbb__p10800.m4a").write_bytes(b"y" * 2000)
    (dem / "bang_chung" / "ccccccccccc").mkdir(parents=True)     # đoạn trích (D-66): không phải file đệm
    (dem / "bang_chung" / "ccccccccccc" / "ccccccccccc_00h00m40s-00h03m10s.webm").write_bytes(b"z" * (2 ** 27))
    monkeypatch.delenv("TIMCLIP_UI_VE_MOI_TRANG", raising=False)   # chỉ trang mặc định: thanh bên vẫn vẽ đủ
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    that = shutil.disk_usage
    monkeypatch.setattr(shutil, "disk_usage", lambda p: that(p)._replace(free=int(trong_gb * 2 ** 30)))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_hien_dung_luong_dem_va_cho_trong_o_du_lieu(tmp_path, monkeypatch):
    at = _mo(tmp_path, monkeypatch, 120)
    chu = " ".join(c.value for c in at.sidebar.caption)
    assert "Đệm audio của lượt quét: 2 file" in chu and "còn trống 120 GB" in chu, chu
    assert "đoạn trích bằng chứng 0.1 GB" in chu, chu
    assert not any("GB trống" in (w.value or "") for w in at.sidebar.warning)
    assert not any("Xoá" in b.label or "Xóa" in b.label for b in at.sidebar.button), "không có nút xoá thẳng"
    assert at.button(key="mo_don_dem").label.startswith("🧹 Dọn đệm audio")


def test_o_du_lieu_duoi_30_gb_thi_canh_bao_vang(tmp_path, monkeypatch):
    at = _mo(tmp_path, monkeypatch, 12.5)
    assert any("chỉ còn 12.5 GB trống" in (w.value or "") for w in at.sidebar.warning)
