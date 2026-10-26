# -*- coding: utf-8 -*-
"""Tab «Lịch sử»: cảnh báo «chỉ nói về phần đã quét» dựa vào DỮ LIỆU phạm vi, không vào chữ nhãn (audit F-12).

Lượt quét YouTube mà âm thanh YouTube ngắn hơn lengthSeconds, đã tải lại kiểm, được nhận là quét
TRỌN (``engine``: ``ly_do_pham_vi = "am_thanh_ngan_hon"``, ``day_du = 1``; DATA_MIGRATION_AND_RECOVERY
mục 8). Nhãn của nó là «Trọn video (âm thanh YouTube ngắn hơn …)» — lý do chỉ để rà lại sau. Mã cũ so
nhãn ĐÚNG BẰNG «Trọn video» nên lượt trọn này bị cảnh báo vàng như quét một phần.

Lượt một phần (``day_du = 0``) và lịch sử cũ chưa rõ phạm vi (``day_du`` NULL) vẫn phải cảnh báo.
Dữ liệu tổng hợp, thư mục tạm, AppTest — không mạng, không dữ liệu thật.
"""

from __future__ import annotations

import os
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

import engine as engine_mod
import lich_su
from engine import Engine, ScanResult

APP_PY = os.path.join(os.path.dirname(os.path.abspath(engine_mod.__file__)), "app.py")


def _canh_bao_pham_vi(tmp_path, monkeypatch, vung, ly_do, xoa_day_du=False):
    data = tmp_path / "data"
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)

    # Lần đầu mở app để nó tự dựng cấu trúc dữ liệu trong thư mục tạm.
    at = AppTest.from_file(APP_PY, default_timeout=120).run()
    assert not at.exception

    eng = Engine(root=str(tmp_path), data_dir=str(data), out_dir=str(tmp_path / "ketqua"))
    kq = ScanResult(source_name="Video gia", source_ref="https://youtu.be/AAAAAAAAAAA",
                    duration_s=600.0, vung_da_khop=vung, ly_do_pham_vi=ly_do)
    kq.source_id = "AAAAAAAAAAA"
    eng.save_job(kq, "youtube")
    if xoa_day_du:
        # Dòng lịch sử cũ (trước lược đồ có phạm vi): day_du để NULL.
        with sqlite3.connect(eng.sqlite_file) as cx:
            cx.execute("UPDATE jobs SET day_du = NULL")
    hang = eng.list_jobs()[0]

    at = AppTest.from_file(APP_PY, default_timeout=120).run()
    assert not at.exception
    return hang, [w.value for w in at.warning if "phần đã quét" in w.value]


def test_luot_tron_am_thanh_ngan_hon_khong_bi_canh_bao_mot_phan(tmp_path, monkeypatch):
    hang, canh_bao = _canh_bao_pham_vi(tmp_path, monkeypatch, [(0.0, 600.0)], "am_thanh_ngan_hon")
    assert hang["day_du"] == 1
    nhan = lich_su.mo_ta_pham_vi(hang)
    assert nhan.startswith("Trọn video") and "ngắn hơn" in nhan, nhan
    assert canh_bao == [], "Lượt quét TRỌN bị cảnh báo như quét một phần: " + repr(canh_bao)


@pytest.mark.parametrize("xoa_day_du", [False, True], ids=["mot_phan", "lich_su_cu_chua_ro"])
def test_luot_mot_phan_va_chua_ro_van_bi_canh_bao(tmp_path, monkeypatch, xoa_day_du):
    hang, canh_bao = _canh_bao_pham_vi(tmp_path, monkeypatch, [(0.0, 300.0)], "", xoa_day_du)
    assert hang["day_du"] == (None if xoa_day_du else 0)
    assert len(canh_bao) == 1 and lich_su.mo_ta_pham_vi(hang) in canh_bao[0], canh_bao
