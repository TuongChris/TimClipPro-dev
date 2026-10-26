# -*- coding: utf-8 -*-
"""Audit E-8: nút «⬇️ Tải CSV lần quét này» (tab Lịch sử) cũng phải chặn công thức bảng tính.

Dữ liệu synthetic (AppTest, không mạng): lịch sử trong thư mục tạm có một lần quét kiểu cũ (không ảnh chụp V2) với
một kết quả khớp mà clip gốc là file của kho dựng từ thư mục máy, tên bắt đầu bằng ký tự công thức
(«-Intro reel.mp4», «=SUM(1,2) Bonus.mp4» — tên file Windows hợp lệ).

Bối cảnh: TimClipPro/CLAUDE.md «CSV vẫn chặn công thức ở tầng ghi»; mọi đường xuất CSV khác (engine.export_csv,
nút Ngang/Dọc ở tab Lịch sử app.py:1822/1830, scan_ui.csv_nguon_chung) bọc ô bằng ``o_bang_tinh_an_toan``
(AUD-226 đã nêu đúng đường này).

Hành vi ĐÚNG được khẳng định: trong dữ liệu CSV của nút tải, ô «Clip gốc» của clip có tên bắt đầu bằng = + - @
được thêm nháy đơn ở đầu (``o_bang_tinh_an_toan``), không ghi thô.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from streamlit.testing.v1 import AppTest

import engine
from engine import Engine, Match, ScanResult, o_bang_tinh_an_toan

APP_PY = Path(engine.__file__).resolve().parent / "app.py"
NHAN = "⬇️ Tải CSV lần quét này"


@pytest.mark.parametrize("ten_clip", ["-Intro reel.mp4", "=SUM(1,2) Bonus.mp4"])  # tên file Windows hợp lệ
def test_csv_lan_quet_chan_cong_thuc_o_clip_goc(tmp_path, monkeypatch, ten_clip):
    data_dir, out_dir = tmp_path / "data", tmp_path / "ketqua"
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(out_dir))
    e = Engine(data_dir=str(data_dir), out_dir=str(out_dir))
    kq = ScanResult(source_name="Video thử E8", source_ref="u", status="ok", matches=[
        Match(clip=ten_clip, start_s=60.0, end_s=120.0, matched_s=55.0, clip_offset_s=0.0,
              hashes=400, confidence="Rất chắc chắn")])
    job_id = e.save_job(kq, "youtube")

    # Bắt dữ liệu mà st.download_button nạp vào kho media trong bộ nhớ của AppTest (theo tên file tải).
    tep_tai: dict = {}
    goc_nap = MemoryMediaFileStorage.load_and_get_id

    def nap(self, path_or_data, mimetype, kind, filename=None):
        if filename and filename.startswith("ketqua_job") and isinstance(path_or_data, bytes):
            tep_tai[NHAN] = path_or_data
        return goc_nap(self, path_or_data, mimetype, kind, filename)

    monkeypatch.setattr(MemoryMediaFileStorage, "load_and_get_id", nap)

    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    chon = next(sb for sb in at.selectbox if sb.label == "Xem chi tiết lần quét số")
    assert chon.value == job_id
    nut = [el for el in at.get("download_button") if el.proto.label == NHAN]
    assert len(nut) == 1, [el.proto.label for el in at.get("download_button")]
    tep = tep_tai[nut[0].proto.label]
    dong = list(csv.DictReader(io.StringIO(tep.decode("utf-8-sig"))))
    assert len(dong) == 1
    assert dong[0]["Clip gốc"] == o_bang_tinh_an_toan(ten_clip), (
        f"ô «Clip gốc» ghi thô, bảng tính sẽ hiểu là công thức: {dong[0]['Clip gốc']!r}")

