# -*- coding: utf-8 -*-
"""Audit D-14: «Trạng thái YouTube» ở thanh bên phải phản ánh cả lượt ĐỒNG BỘ KÊNH / «Lấy lại tên thật».

Thanh bên đọc ``eng.phien_youtube_cuoi`` (docs/YOUTUBE_ACCESS_RELIABILITY.md §8: «lượt gần nhất (bị chặn / cookie
bị từ chối / …)»). Trước đây chỉ job quét và Watch công bố phiên đó; ``ChannelSync`` dùng phiên riêng không bao giờ
tới thanh bên → lượt đồng bộ bị YouTube chặn mà thanh bên vẫn báo xanh «truy cập YouTube bình thường» của lượt quét
trước.

Kịch bản synthetic (không mạng, không dữ liệu thật): lượt quét trước thành công (thanh bên xanh); sau đó tác vụ nền
gặp bot-check ngay video đầu — bản giả ghi lỗi bot (khuôn câu yt-dlp thật, phân loại thật) vào CHÍNH ``self.phien``
của ``ChannelSync`` nên cầu dao của lượt đó mở. Khẳng định: thanh bên thôi báo xanh và có dòng lỗi của cầu dao.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import channel
from channel import ChannelSync
from truy_cap_youtube import PhienYouTube

APP_PY = Path(channel.__file__).resolve().parent / "app.py"
NHAN_KENH = "Link kênh YouTube của bạn"
NHAN_KHO = "Thư mục kho clip gốc (ổ D, E... tùy bạn)"
NUT_DONG_BO = "⬇️ Bắt đầu đồng bộ kênh"
NUT_TEN_THAT = "🌐 Lấy lại tên video thật cho kho này"
LOI_BOT = "ERROR: [youtube] abcdefghijk: Sign in to confirm you're not a bot. This helps protect our community."
XANH = ("success", "Lượt gần nhất: truy cập YouTube bình thường.")


def _o(at, nhan):
    return next(x for x in at.text_input if x.label == nhan)


def _nut(at, nhan):
    return next((b for b in at.button if b.label == nhan), None)


def _cho(dieu_kien, han_s=20.0):
    het = time.monotonic() + han_s
    while time.monotonic() < het:
        if dieu_kien():
            return True
        time.sleep(0.02)
    return dieu_kien()


def _dong_thanh_ben(at) -> list:
    ra = []
    for muc in ("success", "info", "warning", "error"):
        ra.extend((muc, str(x.value)) for x in getattr(at.sidebar, muc))
    return ra


def _gia_dong_bo(phien_luot: list, da_chay: threading.Event):
    def sync_gia(self, url, limit, progress, cancel_check, thu_lai_han_che=False):
        # Đúng như _sync_da_khoa thật: lỗi tải của video đầu đi vào self.phien.ghi_loi → BOT_CHALLENGE (ngưỡng 1).
        self.phien.ghi_loi(LOI_BOT, "download", "abcdefghijk")
        phien_luot.append(self.phien)
        da_chay.set()
        return {"tong": 3, "moi": 0, "bo_qua": 0, "loi": ["abcdefghijk: bị chặn"], "thu_muc": self.dest,
                "da_huy": False, "nghi_hong": [], "da_cach_ly": [], "da_doi_soat": 0,
                "chan_youtube": self.phien.thong_bao_dung(), "youtube": self.phien.tom_tat(),
                "trang_thai": "BI_CHAN", "can_tai": 3, "so_loi": 1, "chua_thu": 2, "gioi_han_tuoi": 0,
                "chi_hoi_vien": 0, "xac_thuc": {}, "han_che_bo_qua": 0, "canh_bao_cookie": ""}
    return "_sync_da_khoa", sync_gia


def _gia_ten_that(phien_luot: list, da_chay: threading.Event):
    def va_metadata_gia(self, progress=None, fetcher=None, chi_thieu=True, *, lay_title=False, cancel_check=None):
        # Như va_metadata thật: lỗi hỏi metadata đi vào self.phien.ghi_loi, cầu dao mở thì dừng cả lượt.
        self.phien.ghi_loi(LOI_BOT, "metadata", "abcdefghijk")
        phien_luot.append(self.phien)
        da_chay.set()
        return {"tong": 3, "da_va": 0, "bo_qua": 0, "da_them_tu_dia": 0,
                "loi": [f"{self.phien.thong_bao_dung()} Còn 3 mục chưa hỏi."]}
    return "va_metadata", va_metadata_gia


@pytest.mark.parametrize("nut, tao_gia", [(NUT_DONG_BO, _gia_dong_bo), (NUT_TEN_THAT, _gia_ten_that)],
                         ids=["dong_bo_kenh", "lay_lai_ten_that"])
def test_thanh_ben_phai_phan_anh_luot_kenh_bi_chan(tmp_path, monkeypatch, nut, tao_gia):
    import streamlit

    assert APP_PY.is_file(), f"không thấy {APP_PY}"
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    kho = tmp_path / "KhoGia"
    kho.mkdir()

    da_chay = threading.Event()
    phien_luot: list = []
    ten_ham, ham_gia = tao_gia(phien_luot, da_chay)
    monkeypatch.setattr(ChannelSync, ten_ham, ham_gia)
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)

    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    eng = at.session_state.eng

    # Lượt quét TRƯỚC thành công (đúng thứ Engine._nhan_ket_qua_job công bố sau một job quét).
    truoc = PhienYouTube()
    truoc.ghi_thanh_cong("metadata")
    truoc.ghi_thanh_cong("download")
    eng.phien_youtube_cuoi = truoc
    at.run()
    assert XANH in _dong_thanh_ben(at), "đối chứng: sau lượt quét tốt thanh bên báo xanh"

    _o(at, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
    _o(at, NHAN_KHO).set_value(str(kho))
    at.run()
    _nut(at, nut).click().run()
    assert not at.exception
    assert da_chay.wait(15), "thiết lập: lượt giả không chạy"
    job = at.session_state.job
    assert _cho(lambda: not job.get("running"), 20.0), "lượt giả không kết thúc"
    at.run()
    at.run()

    assert phien_luot and phien_luot[0].mo, "tiền đề: cầu dao của lượt đã mở (bot-check)"
    dong = _dong_thanh_ben(at)
    thong_bao_dung = phien_luot[0].thong_bao_dung()
    assert XANH not in dong and ("error", thong_bao_dung) in dong, (
        "Lượt vừa bị YouTube chặn (cầu dao mở) nhưng «Trạng thái YouTube» ở thanh bên vẫn nói về lượt quét "
        f"trước. eng.phien_youtube_cuoi is phiên quét cũ: {eng.phien_youtube_cuoi is truoc}; "
        f"các dòng thanh bên: {dong!r}")
