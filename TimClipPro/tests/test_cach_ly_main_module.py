# -*- coding: utf-8 -*-
"""Cách ly test: AppTest (Streamlit) để lại ``sys.modules['__main__']`` = module của app.py. Tiến trình con
multiprocessing (spawn — Windows) của một test SAU đó sẽ CHẠY LẠI app.py ở cấp module → dựng Engine trên
``data/`` mặc định của THƯ MỤC MÃ (trên máy thật: lịch sử thật; với outbox còn có thể khởi động người gửi
Sheets). Tái hiện 08/10/2026 (`test_audfprint_multiproc` tạo ``data/lichsu.db`` trong thư mục mã).

Hai test chạy theo THỨ TỰ trong file: test 1 chạy AppTest, test 2 kiểm ``__main__`` đã được trả lại.
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def test_1_apptest_chay_app(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    assert not AppTest.from_file(str(APP_PY), default_timeout=120).run().exception


def test_2_main_module_khong_con_la_app():
    main = sys.modules.get("__main__")
    assert not str(getattr(main, "__file__", "") or "").endswith("app.py")
