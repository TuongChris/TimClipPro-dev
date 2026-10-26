# -*- coding: utf-8 -*-
"""Màn kết quả (audit F-9): lô quét gặp lỗi CẤP LÔ giữa chừng không được che các kết quả ĐÃ XONG.

Kịch bản tổng hợp (không mạng, không dữ liệu thật; AppTest + thư mục tạm): lô 3 link YouTube giả.
Video 1 quét xong với 1 bằng chứng (đã lưu lịch sử + xếp hàng Sheets trong engine thật). Ở video 2,
``save_job`` không ghi bền được (đĩa đầy / ``lichsu.db`` bị khoá quá lâu) → engine ném ``LoiLuuBen``
— thiết kế CỐ Ý dừng nhận việc mới (engine.LoiLuuBen docstring) — ngoại lệ thoát ``scan_iter``,
``ScanJobController`` giữ ``results()`` = [video 1] và đặt ``error``.

Hành vi ĐÚNG được khẳng định: màn kết quả vẫn báo lỗi lô, NHƯNG vẫn hiện bảng kết quả của video 1
(tên nguồn trong bảng, nút lưu CSV / hồ sơ) — docs/MANAGED_RUNTIME_DESIGN.md §3 câu 1: «Commit lỗi
→ lượt quét báo lỗi lưu bền (kết quả vẫn trả về UI)»; ``ScanJobController.cancel`` cũng hứa «kết quả
đã xong vẫn được giữ». Người dùng không được phải quét lại cả lô hay không biết video 1 đã vào hàng gửi.
"""

from __future__ import annotations

import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

import engine as engine_mod
from test_bao_cao_v2 import _bc, _kq_ca_that

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
URLS = [f"https://www.youtube.com/watch?v=vidthu0000{i}" for i in range(3)]


def _cac_doan_chu(at) -> list:
    phan = []
    for nhom in (at.markdown, at.info, at.caption, at.warning, at.error, at.success,
                 at.header, at.subheader):
        phan.extend(str(i.value) for i in nhom)
    for df in at.dataframe:
        try:
            phan.append(df.value.to_string())
        except Exception:  # noqa: BLE001
            pass
    return phan


def test_loi_cap_lo_khong_che_ket_qua_da_xong(tmp_path, monkeypatch):
    import streamlit

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)

    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)

    goi = []

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        goi.append(url)
        if url == URLS[0]:
            kq = _kq_ca_that(source_name="Video mot da xong", source_ref=url,
                             source_id="vidthu00000", duration_s=3600.0, vung_da_khop=None,
                             ly_do_pham_vi="", pham_vi_quet_s=3600.0)
            kq.bao_cao = _bc(kq, mo_ta_pham_vi="")
            return kq
        # Đúng ngoại lệ engine thật ném từ `_luu_ben` khi commit lịch sử thất bại.
        raise engine_mod.LoiLuuBen(
            "Không lưu bền được vào lịch sử (OperationalError SQLITE_FULL) — kết quả lần quét chưa "
            "được lưu và chưa xếp hàng gửi Google Sheets.")

    monkeypatch.setattr(engine_mod.Engine, "scan_youtube", scan_youtube)

    controller = at.session_state.scan_controller
    controller.start(URLS, "youtube")
    at.session_state.job.update({
        "running": True, "pct": 0.0, "msg": "", "results": [], "error": "",
        "kind": "scan", "da_day_sheet": True, "scan_batch_id": "test",
    })
    han = time.monotonic() + 30
    while controller.running and time.monotonic() < han:
        time.sleep(0.02)
    assert not controller.running

    # Tiền đề (đúng như audit mô tả): controller GIỮ kết quả video 1 và đặt lỗi lô.
    assert goi == URLS[:2]
    assert [k.source_name for k in controller.results()] == ["Video mot da xong"]
    assert "Không lưu bền" in controller.error

    at.run()          # màn tiến độ thấy lô xong → chép results + error vào job
    assert not at.exception
    at.run()          # chỉ còn màn kết quả
    assert not at.exception
    assert not at.session_state.job["running"]

    chu = "\n".join(_cac_doan_chu(at))
    assert "Không lưu bền" in chu, "tiền đề: lỗi lô phải được báo"
    nut = [b.label for b in at.button]
    co_bang = any("Video mot da xong" in df.value.to_string() for df in at.dataframe)
    co_nut_luu = any("Lưu CSV" in n for n in nut)
    assert "1 video đã quét xong TRƯỚC lỗi" in chu, "phải nói video đã xong vẫn được giữ"
    assert co_bang and co_nut_luu, (
        "F-9: lỗi cấp lô che kết quả video 1 đã xong (đã lưu lịch sử, đã xếp hàng Sheets): "
        f"bảng có video 1={co_bang}, nút Lưu CSV={co_nut_luu}; nút đang có={nut}")
