# -*- coding: utf-8 -*-
"""Rà soát đối nghịch M3+M4, P2-C: sau khi bản mới được kích hoạt mà ứng dụng BẢN CŨ còn mở, người gửi nền
của bản cũ từ chối mọi việc (cổng: «bản cũ») nhưng vẫn GIỮ quyền người gửi suốt đời tiến trình → Watch/CLI/app
của bản mới không gửi được gì tới khi ai đó đóng app cũ. Nay: bản cũ NHƯỜNG quyền và dừng hẳn; đang rút cổng
(cập nhật) thì chỉ tạm dừng, giữ quyền. App cũ hiện cảnh báo nổi (không chỉ trong ô thu gọn)."""
import os
import time

from streamlit.testing.v1 import AppTest

import pytest

import lich_su
import maintenance_gate as mg
import outbox as ob
import sheet_destinations as sd
from outbox_gia import CongGia, khoa_gia
from test_outbox_ra_soat import IID, _ho_so, _tt, _xep


@pytest.fixture()
def mt(tmp_path):
    db = str(tmp_path / "data" / "lichsu.db")
    (tmp_path / "data").mkdir()
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    khoa = khoa_gia(tmp_path)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa)
    return {"db": db, "data": str(tmp_path / "data"), "tmp": tmp_path, "khoa": khoa}

LY_DO = "Bản mới đã được kích hoạt — đóng và mở lại ứng dụng bằng launcher để dùng bản mới."


def _cho(dieu_kien, han_s=5.0):
    het = time.monotonic() + han_s
    while time.monotonic() < het:
        if dieu_kien():
            return True
        time.sleep(0.02)
    return dieu_kien()


def test_ban_cu_nguoi_gui_nen_nhuong_quyen_va_khong_tu_khoi_dong_lai(mt, monkeypatch):
    a = _ho_so(mt, gid=0)
    v = _xep(mt, a, 1)
    monkeypatch.setattr(mg, "ly_do_ban_cu", lambda *a, **k: LY_DO)       # tiến trình này = bản cũ
    nen = ob.NguoiGuiNen(mt["db"], mt["data"], CongGia, chu_ky_s=0.05, chu_ky_gianh_s=0.05)
    nen.start()
    try:
        assert _cho(lambda: not nen.dang_chay), "người gửi của bản cũ vẫn chạy và giữ quyền"
        assert _tt(mt, v) == ob.PENDING                                  # bản cũ không gửi gì
        moi = ob.NguoiGui(mt["db"], mt["data"], CongGia(),
                          cong_bao_tri=mg.CongBaoTri(mt["data"], kiem_them=lambda: ""))   # bản đang kích hoạt
        assert moi.nhan_quyen()
        moi.chay_mot_vong()
        moi.tha_quyen()
        assert _tt(mt, v) == ob.SENT
        nen.start()                                                      # giao diện cũ rerun: không dậy lại
        assert not nen.dang_chay
    finally:
        nen.stop(cho_s=5)


def test_dang_rut_cong_chi_tam_dung_va_giu_quyen(mt):
    a = _ho_so(mt, gid=0)
    v = _xep(mt, a, 1)
    rut = mg.CongBaoTri(mt["data"], kiem_them=lambda: "").bat_dau_rut("cập nhật thử")
    nen = ob.NguoiGuiNen(mt["db"], mt["data"], CongGia, chu_ky_s=0.05, chu_ky_gianh_s=0.05)
    nen.start()
    try:
        assert _cho(lambda: nen.co_quyen)
        time.sleep(0.3)
        assert nen.dang_chay and _tt(mt, v) == ob.PENDING
        khac = ob.NguoiGui(mt["db"], mt["data"], CongGia(),
                           cong_bao_tri=mg.CongBaoTri(mt["data"], kiem_them=lambda: ""))
        assert not khac.nhan_quyen()                                     # vẫn giữ quyền: chỉ tạm dừng
    finally:
        rut.ket_thuc()
        nen.stop(cho_s=5)


def _kich_ban_canh_bao():
    import ui_cap_nhat

    ui_cap_nhat.canh_bao_ban_cu()


def test_app_ban_cu_hien_canh_bao_noi(monkeypatch):
    monkeypatch.setattr(mg, "ly_do_ban_cu", lambda *a, **k: LY_DO)
    at = AppTest.from_function(_kich_ban_canh_bao, default_timeout=60).run()
    assert not at.exception and any("đóng và mở lại" in str(w.value) for w in at.warning)
    monkeypatch.setattr(mg, "ly_do_ban_cu", lambda *a, **k: "")
    at = AppTest.from_function(_kich_ban_canh_bao, default_timeout=60).run()
    assert not at.exception and not at.warning


def test_app_goi_canh_bao_ban_cu_o_cap_trang():
    app = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"),
               encoding="utf-8").read()
    assert "\nui_cap_nhat.canh_bao_ban_cu()\n" in app.replace("\r\n", "\n")
