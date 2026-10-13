# -*- coding: utf-8 -*-
"""Tiến độ lô quét từ đầu tới cuối: engine → sổ tiến độ → ``ScanJobController`` → màn hình.

* lô mang chế độ giới hạn video dài xuống ĐÚNG bản sao của job; sổ ghi số đo thật của video đang chạy;
* phiên mới (tải lại trang) nhận lại lô đang chạy, không tạo lô trùng;
* Dừng: nhật ký ghi rõ, video bị dừng không thành «hoàn tất»;
* màn hình: hiện thời lượng nguồn, phạm vi, chế độ, giai đoạn thật, nhịp sống tách khỏi tiến triển;
  ETA «chưa đủ dữ liệu» thay vì số bịa; vẽ lại (rerun) không tạo lô mới.
"""

from __future__ import annotations

import threading
import time
import types
from pathlib import Path

import pytest

import engine as engine_mod
import tien_do_quet as tdq
import ui_tien_do_quet as ui
from engine import GHVD_TU_DONG, Engine, ScanResult
from scan_jobs import PHASE_TAI, ScanJobController, doan_phase

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def eng(tmp_path):
    return Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))


def _cho_xong(ctl, han=30.0):
    het = time.monotonic() + han
    while ctl.running and time.monotonic() < het:
        time.sleep(0.02)
    assert not ctl.running


def test_lo_ghim_che_do_va_so_tien_do_tren_ban_sao(eng, monkeypatch):
    thay = []

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        thay.append((getattr(self, "_gioi_han_video_dai", None),
                     getattr(self, "_so_tien_do", None) is not None))
        self._td(tdq.GD_METADATA, ghi="Đang lấy thông tin video từ YouTube")
        self._td(thoi_luong_nguon_s=65 * 3600 + 114.0, pham_vi_tu_s=0.0, pham_vi_den_s=10800.0,
                 che_do="Giới hạn video dài — 3 giờ đầu", ghi="Áp dụng giới hạn quét")
        self._td(tdq.GD_TAI, audio_can_s=10800.0, byte_dau_ra=12 * 1024 * 1024,
                 audio_da_nhan_s=600.0)
        r = ScanResult(source_name=f"V {url}", source_ref=url)
        r.source_id = url
        return r

    monkeypatch.setattr(Engine, "scan_youtube", scan_youtube)
    ctl = ScanJobController(eng)
    ctl.start(["a", "b"], "youtube", gioi_han_video_dai=GHVD_TU_DONG)
    _cho_xong(ctl)
    assert thay == [(GHVD_TU_DONG, True)] * 2
    assert getattr(eng, "_gioi_han_video_dai", None) is None, "Engine gốc không mang chế độ của lô"
    anh = ctl.snapshot()
    assert anh.completed == 2 and anh.gioi_han_video_dai == GHVD_TU_DONG
    nk = [s.noi_dung for s in anh.nhat_ky]
    assert nk[0] == "Bắt đầu video 1/2" and "Bắt đầu video 2/2" in nk
    assert "Áp dụng giới hạn quét" in nk and "Video 2: hoàn tất, 0 đoạn" in nk
    assert nk[-1] == "Quét hoàn tất."
    assert anh.tien_do.index == 2 and anh.tien_do.giai_doan == tdq.GD_XONG


def test_phien_moi_nhan_lai_lo_dang_chay_khong_tao_lo_trung(eng, monkeypatch):
    di_tiep = threading.Event()

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        di_tiep.wait(20)
        return ScanResult(source_name=url, source_ref=url)

    monkeypatch.setattr(Engine, "scan_youtube", scan_youtube)
    ctl1 = ScanJobController(eng)
    ctl1.start(["a"], "youtube")
    try:
        # Phiên khác (tải lại trang): Engine KHÁC, cùng thư mục dữ liệu.
        eng2 = types.SimpleNamespace(data_dir=eng.data_dir)
        assert ScanJobController.dang_chay_cua(eng2) is ctl1
        with pytest.raises(RuntimeError, match="lô quét chạy ở một cửa sổ/phiên khác"):
            ScanJobController(eng2).start(["b"], "youtube")
    finally:
        di_tiep.set()
    _cho_xong(ctl1)
    assert ScanJobController.dang_chay_cua(eng) is None
    ctl3 = ScanJobController(eng)                       # lô trước xong rồi: bắt đầu lô mới được
    ctl3.start(["c"], "youtube")
    _cho_xong(ctl3)


def test_dung_ghi_nhat_ky_va_video_bi_dung_khong_thanh_hoan_tat(eng, monkeypatch):
    dang_tai = threading.Event()

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        self._td(tdq.GD_TAI, byte_da_nhan=1)
        dang_tai.set()
        het = time.monotonic() + 20
        while not self.cancel_event.is_set() and time.monotonic() < het:
            time.sleep(0.01)
        return ScanResult(source_name=url, source_ref=url, status="error",
                          note="Đã hủy theo yêu cầu.", ly_do_pham_vi="huy")

    monkeypatch.setattr(Engine, "scan_youtube", scan_youtube)
    ctl = ScanJobController(eng)
    ctl.start(["a", "b", "c"], "youtube")
    assert dang_tai.wait(20)
    ctl.cancel()
    _cho_xong(ctl)
    anh = ctl.snapshot()
    nk = [s.noi_dung for s in anh.nhat_ky]
    assert any(x.startswith("Đã yêu cầu DỪNG") for x in nk)
    assert "Video 1: đã dừng theo yêu cầu" in nk
    assert anh.completed == 0 and anh.failed == 1, "video bị dừng không được tính là hoàn tất"
    assert "Bắt đầu video 2/3" not in nk, "đã Dừng thì không nhận video mới"
    assert anh.tien_do.giai_doan == tdq.GD_HUY and nk[-1] == "Đã dừng theo yêu cầu."


def test_thong_bao_chuan_bi_tai_la_buoc_tai_khong_phai_metadata():
    assert doan_phase("65 Hours of SML MOVIE Marathon (65:01:54) — chuẩn bị tải audio...") == PHASE_TAI


# ---------------------------------------------------------------- định dạng màn hình (thuần)

def _anh(**td):
    from scan_jobs import BatchSnapshot, VideoState
    v = VideoState(index=1, nguon="https://youtu.be/x", scan_status="running", phase="downloading",
                   message="Đang tải audio...")
    return BatchSnapshot(batch_id="b", total=5, current_index=1, completed=0, failed=0, running=True,
                         cancelled=False, elapsed_seconds=1459.0, eta_seconds=None, message="",
                         videos=(v,), tien_do=tdq.AnhTienDo(batch_id="b", index=1, tong=5, **td),
                         worker_alive=True), v


def test_man_hinh_hien_so_do_that_cua_video_dai():
    bay_gio = 2_000_000.0
    anh, v = _anh(tieu_de="65 Hours of SML MOVIE Marathon", giai_doan=tdq.GD_TAI,
                  giai_doan_luc=bay_gio - 120, nhip_luc=bay_gio - 5, tien_trien_luc=bay_gio - 8,
                  thoi_luong_nguon_s=234114.0, pham_vi_tu_s=0.0, pham_vi_den_s=10800.0,
                  che_do="Giới hạn video dài — 3 giờ đầu", byte_dau_ra=12 * 1024 * 1024,
                  audio_da_nhan_s=600.0, audio_can_s=10800.0, toc_do_x=5.0)
    dong = "\n".join(ui.dong_chi_tiet(anh, v, {}, bay_gio))
    assert "65 Hours of SML MOVIE Marathon" in dong
    assert "**Thời lượng nguồn:** 65:01:54" in dong
    assert "**Phạm vi quét:** 00:00:00 → 03:00:00" in dong
    assert "Giới hạn video dài — 3 giờ đầu" in dong and "**Giai đoạn hiện tại:** Đang tải audio" in dong
    assert "ffmpeg đã ghi 12.0 MB (dung lượng file, không phải byte mạng)" in dong
    assert "qua mạng" not in dong, "byte đầu ra ffmpeg không được gọi là byte nhận qua mạng"
    assert "00:10:00 / 03:00:00 âm thanh" in dong
    nhip = ui.dong_nhip(anh, bay_gio)
    assert "nhịp tiến trình 5 giây trước" in nhip and "lần cuối có tiến triển 8 giây trước" in nhip
    assert ui.dong_eta_buoc(anh).endswith("chưa đủ dữ liệu để ước tính")
    assert anh.tien_do.ty_le_buoc == pytest.approx(600 / 10800)


def test_tai_thuong_hien_byte_mang_that():
    anh, v = _anh(giai_doan=tdq.GD_TAI, giai_doan_luc=1.0, byte_da_nhan=50 * 1024 * 1024,
                  byte_tong=200 * 1024 * 1024, toc_do_byte_s=2 * 1024 * 1024)
    dong = "\n".join(ui.dong_chi_tiet(anh, v, {}, 10.0))
    assert "đã nhận 50.0 MB qua mạng / 200.0 MB" in dong and "tốc độ 2,048 KB/s" in dong
    assert anh.tien_do.ty_le_buoc == pytest.approx(0.25)


def test_man_hinh_khong_dung_so_do_cua_video_khac():
    anh, v = _anh(giai_doan=tdq.GD_KHOP, khop_tong=4, khop_xong=3)
    anh = anh.__class__(**{**anh.__dict__, "current_index": 2,
                           "videos": anh.videos + (v.__class__(index=2, nguon="u2",
                                                                phase="fetching_metadata"),)})
    v2 = anh.videos[1]
    dong = "\n".join(ui.dong_chi_tiet(anh, v2, {"fetching_metadata": "Đang lấy thông tin video"}))
    assert "Đang lấy thông tin video" in dong and "So khớp" not in dong


# ---------------------------------------------------------------- Streamlit thật (AppTest)

def _van_ban(at) -> str:
    phan = []
    for nhom in (at.markdown, at.info, at.caption, at.warning, at.error, at.header, at.subheader,
                 at.code):
        phan.extend(str(i.value) for i in nhom)
    phan.extend(str(i.label) for i in at.metric)
    phan.extend(str(i.value) for i in at.metric)
    return "\n".join(phan)


def test_app_man_hinh_quet_cap_nhat_so_do_that(tmp_path, monkeypatch):
    import streamlit
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    radio = at.radio(key="gioi_han_video_dai")
    assert radio.value == GHVD_TU_DONG, "mặc định: video trên 6 giờ chỉ quét 3 giờ đầu"
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)

    da_chup = threading.Event()

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        self._td(tdq.GD_METADATA, ghi="Đang lấy thông tin video từ YouTube")
        self._td(tieu_de="65 Hours of SML MOVIE Marathon", thoi_luong_nguon_s=234114.0,
                 pham_vi_tu_s=0.0, pham_vi_den_s=10800.0, che_do="Giới hạn video dài — 3 giờ đầu",
                 ghi="Metadata OK — nguồn dài 65:01:54")
        self._td(tdq.GD_TAI, audio_can_s=10800.0, byte_dau_ra=3 * 1024 * 1024, audio_da_nhan_s=180.0)
        da_chup.wait(60)
        return ScanResult(source_name=url, source_ref=url)

    monkeypatch.setattr(engine_mod.Engine, "scan_youtube", scan_youtube)
    controller = at.session_state.scan_controller
    controller.start(["u1"], "youtube", gioi_han_video_dai=GHVD_TU_DONG)
    at.session_state.job.update({"running": True, "pct": 0.0, "msg": "", "results": [], "error": "",
                                 "kind": "scan", "da_day_sheet": True, "scan_batch_id": "t"})
    try:
        het = time.monotonic() + 30
        van_ban = ""
        while time.monotonic() < het:
            at.run()
            assert not at.exception
            van_ban = _van_ban(at)
            if "Đang tải audio" in van_ban and "Phạm vi quét" in van_ban:
                break
            time.sleep(0.1)
    finally:
        da_chup.set()
    assert "**Thời lượng nguồn:** 65:01:54" in van_ban
    assert "**Phạm vi quét:** 00:00:00 → 03:00:00" in van_ban
    assert "00:03:00 / 03:00:00 âm thanh" in van_ban
    assert "Metadata OK — nguồn dài 65:01:54" in van_ban, "nhật ký trực tiếp phải hiện trên trang"
    assert "ETA" in van_ban and "Chưa đủ dữ liệu để ước tính" in van_ban
    _cho_xong(controller)


def test_app_quet_toan_bo_phai_chu_dong_xac_nhan(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    at.radio(key="gioi_han_video_dai").set_value("toan_bo").run()
    assert not at.exception
    assert any("Tôi chủ động chọn quét toàn bộ" in c.label for c in at.checkbox)
    assert any("hàng chục GB" in str(w.value) for w in at.warning)
