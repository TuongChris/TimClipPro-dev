# -*- coding: utf-8 -*-
"""Màn kết quả sau khi bấm Dừng (audit F-5): bấm «⏹️ Dừng lại» giữa lô quét → màn hình kết quả
phải nói rõ lô ĐÃ DỪNG và còn bao nhiêu video CHƯA QUÉT — không được trông như một lô đã quét
xong hết.

Kịch bản tổng hợp (không mạng, không dữ liệu thật): 5 link YouTube giả; video 1 xong với 1 bằng
chứng; trong lúc video 2 đang «tải», người dùng bấm nút Dừng THẬT trên giao diện (AppTest). Engine
dừng trước khi nhận video 3–5 (``scan_iter``), nên ``results()`` chỉ có 2 kết quả.

Đúng (cùng tinh thần banner đỏ của cầu dao YouTube, app.py «các video "Chưa quét" KHÔNG phải âm
tính và không được tính là đã quét»): màn hình kết quả phải có câu «đã dừng» ở cấp LÔ và nói 3 video
chưa quét (hoặc liệt kê đủ 3 link chưa quét).
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

from engine import ScanResult

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
URLS = [f"https://www.youtube.com/watch?v=vidthu0000{i}" for i in range(5)]


def _cac_doan_chu(at) -> list:
    phan = []
    for nhom in (at.markdown, at.info, at.caption, at.warning, at.error, at.success,
                 at.header, at.subheader, at.toast):
        phan.extend(str(i.value) for i in nhom)
    for df in at.dataframe:
        try:
            phan.append(df.value.to_string())
        except Exception:  # noqa: BLE001
            pass
    return phan


def test_ket_qua_sau_khi_bam_dung_noi_ro_lo_da_dung_va_video_chua_quet(tmp_path, monkeypatch):
    import streamlit

    import engine as engine_mod
    from test_bao_cao_v2 import _bc, _kq_ca_that

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))

    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    # Màn tiến độ tự gọi st.rerun; vô hiệu hoá để điều khiển từng khung hình.
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)

    video2_dang_tai = threading.Event()
    goi = []

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        goi.append(url)
        if url == URLS[0]:
            if progress:
                progress(0.9, "Đang so khớp vân tay... khúc 1/1")
            # Video 1 quét TRỌN (không «một phần»), để màn kết quả không có chữ «dừng sớm» gây nhiễu.
            kq = _kq_ca_that(source_name="Video 1", source_ref=url, source_id="vidthu00000",
                             duration_s=3600.0, vung_da_khop=None, ly_do_pham_vi="",
                             pham_vi_quet_s=3600.0)
            kq.bao_cao = _bc(kq, mo_ta_pham_vi="")
            return kq
        # Video 2: «đang tải» cho tới khi người dùng bấm Dừng — rồi trả đúng kết quả engine thật
        # trả khi bắt Cancelled (engine.scan_youtube: status error, «Đã hủy theo yêu cầu.», «huy»).
        if progress:
            progress(0.3, "Đang tải audio...")
        video2_dang_tai.set()
        assert self.cancel_event.wait(30), "không nhận được yêu cầu Dừng"
        kq = ScanResult(source_name="Video 2", source_ref=url, source_id="vidthu00001",
                        status="error", note="Đã hủy theo yêu cầu.")
        kq.ly_do_pham_vi = "huy"
        return kq

    monkeypatch.setattr(engine_mod.Engine, "scan_youtube", scan_youtube)

    controller = at.session_state.scan_controller
    controller.start(URLS, "youtube")
    at.session_state.job.update({
        "running": True, "pct": 0.0, "msg": "", "results": [], "error": "",
        "kind": "scan", "da_day_sheet": True, "scan_batch_id": "test",
    })

    assert video2_dang_tai.wait(30)
    # Khung tiến độ, rồi bấm nút «⏹️ Dừng lại» THẬT của màn quét.
    at.run()
    assert not at.exception
    nut_dung = [b for b in at.button if b.label == "⏹️ Dừng lại"]
    assert nut_dung, "không thấy nút Dừng trên màn quét"
    nut_dung[0].click().run()
    assert not at.exception

    han = time.monotonic() + 30
    while controller.running and time.monotonic() < han:
        time.sleep(0.02)
    assert not controller.running

    # Tiền đề của kịch bản (đúng như audit mô tả): 3 video sau chưa bao giờ bắt đầu.
    assert goi == URLS[:2]
    assert len(controller.results()) == 2
    anh = controller.snapshot()
    assert anh.cancelled and anh.message == "Đã dừng theo yêu cầu."

    # Lần 1: màn tiến độ thấy lô đã xong → chép kết quả vào job. Lần 2: CHỈ màn kết quả.
    at.run()
    assert not at.exception
    at.run()
    assert not at.exception
    assert not at.session_state.job["running"]

    doan = _cac_doan_chu(at)
    chu = "\n".join(doan)
    # Màn kết quả đúng là màn này (không phải màn tiến độ).
    assert "Đang quét video" not in chu
    assert any("bằng chứng tốt nhất" in d for d in doan), chu[:3000]

    ket_qua_lien_quan = [d for d in doan if any(
        k in d for k in ("bằng chứng tốt nhất", "nguồn bị lỗi", "dừng", "Dừng", "chưa quét",
                         "Chưa quét", "vidthu"))]
    tom_tat = "\n".join(ket_qua_lien_quan)

    loi = []
    # (1) Lô ĐÃ DỪNG theo yêu cầu phải được nói ở cấp lô (không chỉ «Đã hủy» trong dòng lỗi video 2).
    if not re.search(r"dừng theo yêu cầu|bấm dừng|lô (quét )?(đã )?(bị )?dừng|đã dừng (lô|quét)"
                     r"|dừng giữa chừng", chu, re.IGNORECASE):
        loi.append("F-5(1): man ket qua KHONG noi lo da bi dung (khong co 'Da dung theo yeu cau').")
    # (2) 3 link chưa bao giờ được quét phải được nhắc: «3 video chưa quét» hoặc liệt kê đủ 3 link.
    noi_so_luong = re.search(r"\b3\b[^\n]{0,40}chưa (được )?quét", chu, re.IGNORECASE)
    liet_ke_du = all(u in chu or u.rsplit("=", 1)[-1] in chu for u in URLS[2:])
    if not (noi_so_luong or liet_ke_du):
        loi.append("F-5(2): man ket qua KHONG nhac 3 video chua quet (link 3-5 vang mat).")
    assert not loi, "\n".join(loi) + "\n--- cac dong lien quan tren man ket qua ---\n" + \
        tom_tat.encode("ascii", "backslashreplace").decode("ascii")


# ---------- câu cấp lô (scan_ui, không Streamlit) ----------

def test_lo_chay_het_khong_co_cau_dung():
    from scan_ui import thong_bao_lo_da_dung

    assert thong_bao_lo_da_dung(False, []) == ""


def test_dung_o_video_cuoi_van_noi_da_dung_khong_bia_video_chua_quet():
    from scan_ui import thong_bao_lo_da_dung

    cau = thong_bao_lo_da_dung(True, [])
    assert "Đã dừng theo yêu cầu" in cau and "chưa quét" not in cau


def test_chua_quet_lay_cac_nguon_sau_ket_qua_cuoi_va_thoat_markdown():
    from types import SimpleNamespace

    from scan_ui import chua_quet_cua_lo, thong_bao_lo_da_dung

    anh = SimpleNamespace(videos=tuple(SimpleNamespace(nguon=n) for n in
                                       ("a", "b", "C:/thu/*video*_[1].mp4", "d")))
    chua = chua_quet_cua_lo(anh, 2)
    assert chua == ["C:/thu/*video*_[1].mp4", "d"]
    cau = thong_bao_lo_da_dung(True, chua)
    assert "**2 video chưa quét**" in cau and "KHÔNG phải «không có vi phạm»" in cau
    assert "*video*" not in cau and r"\*video\*" in cau      # chữ ngoài: không thành Markdown
    assert chua_quet_cua_lo(anh, 9) == [] and chua_quet_cua_lo(SimpleNamespace(), 0) == []


def test_danh_sach_chua_quet_dai_bi_cat_nhung_van_dem_du():
    from scan_ui import thong_bao_lo_da_dung

    cau = thong_bao_lo_da_dung(True, [f"link{i}" for i in range(25)], toi_da=10)
    assert "**25 video chưa quét**" in cau and "… và 15 video khác" in cau
    assert "link9" in cau and "link10" not in cau
