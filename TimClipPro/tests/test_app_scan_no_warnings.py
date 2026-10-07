# -*- coding: utf-8 -*-
"""Chạy app.py thật qua AppTest và khẳng định terminal KHÔNG còn hai lỗi cũ.

Đây là test tái hiện sát nhất với triệu chứng người dùng thấy:
    pyarrow.lib.ArrowInvalid: Could not convert '—' with type str...
    Thread 'scan-xxxxxxxx': missing ScriptRunContext!
    KeyError: st.session_state has no key "sheet_link"
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pyarrow as pa
from streamlit.testing.v1 import AppTest

from scan_ui import build_scan_status_dataframe

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def test_quet_batch_khong_sinh_canh_bao_arrow_hay_scriptruncontext(
    tmp_path, monkeypatch, caplog
):
    import streamlit

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))

    import engine as engine_mod
    import outbox
    import ui_gui_sheets
    from outbox_gia import CongGia, dich_gia
    from test_bao_cao_v2 import _bc, _kq_ca_that

    cong = CongGia()                      # transport Sheets GIẢ — không gửi thật
    monkeypatch.setattr(outbox, "CongGspread", lambda: cong)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception

    # sheet_link PHẢI có sẵn ngay từ lần render đầu (cau_hinh.GIA_TRI_GIAO_DIEN_MAC_DINH).
    assert "sheet_link" in at.session_state

    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)

    eng = at.session_state.eng
    db = eng.sqlite_file
    dich, _ = dich_gia(db, tmp_path, installation_id=eng.installation_id())
    urls = ["aaa", "bbb", "ccc"]

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        if progress:
            progress(0.5, "Đang so khớp vân tay... khúc 1/2")
        time.sleep(0.12)
        kq = _kq_ca_that(source_name=f"Video {url}", source_ref=f"https://youtu.be/{url}",
                         source_id=(url * 4)[:11])
        if url == "bbb":
            kq.matches, kq.so_dat_nguong = [], 0
        kq.bao_cao = _bc(kq)
        kq.job_id = self.save_job(kq, "youtube")      # xếp việc gửi CÙNG giao dịch (như thật)
        return kq

    monkeypatch.setattr(engine_mod.Engine, "scan_youtube", scan_youtube)
    controller = at.session_state.scan_controller
    # Đúng các bước của app.chay_quet: chụp + ghim đích, preflight cục bộ, người gửi nền.
    y_dinh, loi = ui_gui_sheets.chot_cho_lo(eng, dich.id, True, "lo-thu")
    assert loi == "" and y_dinh is not None
    ui_gui_sheets.dam_bao_nguoi_gui(eng, bat_buoc=True)

    def sau_moi_video(index, tong, ket_qua):
        viec = outbox.ds_viec(db, job_id=ket_qua.job_id, lo_id=y_dinh.lo_id)
        if viec:
            controller.ghi_nhan_giao_hang(index, viec[0].id)

    with caplog.at_level(logging.WARNING):
        controller.start(urls, "youtube", on_result=sau_moi_video, y_dinh_gui=y_dinh)
        at.session_state.job.update({
            "running": True, "pct": 0.0, "msg": "", "results": [], "error": "",
            "kind": "scan", "da_day_sheet": True, "scan_batch_id": "test",
        })

        so_lan_ve = 0
        han = time.monotonic() + 60
        while controller.running and time.monotonic() < han and so_lan_ve < 4:
            at.run()
            assert not at.exception
            so_lan_ve += 1

        han = time.monotonic() + 60
        while controller.running and time.monotonic() < han:
            time.sleep(0.02)

    ban_ghi = "\n".join(r.getMessage() for r in caplog.records)

    # AppTest ở bare mode tự sinh cảnh báo cho 'MainThread' — đó là artefact của
    # harness, không phải lỗi. Lỗi thật là cảnh báo mang tên THREAD NỀN, ví dụ
    # "Thread 'scan-2924d458': missing ScriptRunContext!".
    thieu_ctx_o_worker = [
        dong for dong in ban_ghi.splitlines()
        if "missing ScriptRunContext" in dong and "MainThread" not in dong
    ]
    assert not thieu_ctx_o_worker, thieu_ctx_o_worker
    assert "on_video_callback_failed" not in ban_ghi, (
        "Callback vẫn hỏng — thread nền còn chạm Streamlit"
    )
    assert "ArrowInvalid" not in ban_ghi
    assert "Serialization of dataframe to Arrow table was unsuccessful" not in ban_ghi

    anh = controller.snapshot()
    assert anh.completed == 3 and anh.failed == 0 and anh.lo_id == "lo-thu"
    # Bảng hiển thị cuối cùng vẫn chuyển Arrow thẳng được.
    pa.Table.from_pandas(
        build_scan_status_dataframe(anh.videos, ui_gui_sheets.trang_thai_viec_lo(eng, "lo-thu"))
    )
    han = time.monotonic() + 30
    while time.monotonic() < han and outbox.tom_tat(db, lo_id="lo-thu")[outbox.SENT] < 2:
        time.sleep(0.1)
    try:
        # aaa, ccc có kết quả → 2 việc gửi tới ĐÚNG bảng đã ghim; bbb không có dòng.
        assert outbox.tom_tat(db, lo_id="lo-thu")[outbox.SENT] == 2
        assert {sid for sid, _, _ in cong.bang} == {dich.spreadsheet_id}
    finally:
        nen = outbox._NEN.get(outbox._khoa_db(db))
        if nen is not None:
            nen.stop()
