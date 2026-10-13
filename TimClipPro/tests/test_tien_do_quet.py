# -*- coding: utf-8 -*-
"""Sổ tiến độ THẬT của lô quét (``tien_do_quet``) và luồng giám sát tải (``giam_sat_tai``).

Ràng buộc: chỉ số đo có nguồn; nhịp sống (tiến trình còn chạy) TÁCH khỏi tiến triển; không phần
trăm/ETA khi chưa đủ dữ liệu; không bao giờ 100% trước khi xong; nhật ký có giới hạn; huỷ và mạng đứng
giết đúng ffmpeg của lượt tải.
"""

from __future__ import annotations

import threading

import pytest

import giam_sat_tai as gst
import tien_do_quet as tdq


@pytest.fixture
def dong_ho(monkeypatch):
    """Đồng hồ giả cho ``tien_do_quet`` — điều khiển được thời gian."""
    t = {"now": 1_000_000.0}
    monkeypatch.setattr(tdq.time, "time", lambda: t["now"])
    return t


def test_bat_dau_lo_xoa_trang_thai_lo_truoc(dong_ho):
    so = tdq.SoTienDo()
    so.bat_dau_lo("lo1", 2)
    so.bat_dau_video(1, 2, "u1")
    so.cap_nhat(tdq.GD_TAI, byte_da_nhan=10)
    so.bat_dau_lo("lo2", 5)
    a = so.anh()
    assert a.batch_id == "lo2" and a.index == 0 and a.byte_da_nhan is None
    assert so.su_kien() == [], "nhật ký lô trước không được lẫn sang lô mới"


def test_nhip_khong_phai_tien_trien(dong_ho):
    so = tdq.SoTienDo()
    so.bat_dau_video(1, 1, "u")
    so.cap_nhat(tdq.GD_TAI, byte_da_nhan=100)
    luc = so.anh().tien_trien_luc
    dong_ho["now"] += 50
    so.nhip()
    so.cap_nhat(toc_do_x=2.0)                       # tốc độ đổi, không thêm byte
    so.cap_nhat(byte_da_nhan=100)                   # cùng số byte
    a = so.anh()
    assert a.tien_trien_luc == luc, "nhịp/tốc độ/không thêm byte KHÔNG phải tiến triển"
    assert a.nhip_luc == dong_ho["now"]
    dong_ho["now"] += 1
    so.cap_nhat(byte_da_nhan=101)
    assert so.anh().tien_trien_luc == dong_ho["now"]


def test_ty_le_buoc_chi_khi_co_mau_so_va_khong_bao_gio_100(dong_ho):
    so = tdq.SoTienDo()
    so.bat_dau_video(1, 1, "u")
    so.cap_nhat(tdq.GD_TAI, byte_da_nhan=5_000_000)
    assert so.anh().ty_le_buoc is None, "chưa biết tổng thì không có phần trăm"
    so.cap_nhat(audio_can_s=10800.0, audio_da_nhan_s=5400.0)
    assert so.anh().ty_le_buoc == pytest.approx(0.5)
    so.cap_nhat(audio_da_nhan_s=10800.0)
    assert so.anh().ty_le_buoc == 0.99, "đủ số liệu cũng chưa phải xong — tối đa 99%"
    so.cap_nhat(tdq.GD_KHOP, khop_tong=4, khop_xong=1)
    assert so.anh().ty_le_buoc == pytest.approx(0.25)
    so.cap_nhat(tdq.GD_TONG_HOP)
    assert so.anh().ty_le_buoc is None


def test_eta_chi_khi_du_du_lieu_toc_do(dong_ho):
    so = tdq.SoTienDo()
    so.bat_dau_video(1, 1, "u")
    so.cap_nhat(tdq.GD_TAI, audio_can_s=10800.0, audio_da_nhan_s=0.0)
    assert so.anh().eta_buoc_s is None
    dong_ho["now"] += 5
    so.cap_nhat(audio_da_nhan_s=300.0)
    assert so.anh().eta_buoc_s is None, "mới 5 giây dữ liệu — chưa đủ để ước tính"
    dong_ho["now"] += 5
    so.cap_nhat(audio_da_nhan_s=600.0)               # 600 s âm thanh / 10 s thực = 60x
    assert so.anh().eta_buoc_s == pytest.approx((10800 - 600) / 60.0)
    so.cap_nhat(tdq.GD_CAT, khuc_tong=4, khuc_xong=0)
    assert so.anh().eta_buoc_s is None, "đổi bước: ETA tính lại từ đầu"


def test_canh_bao_theo_giai_doan_va_noi_kem_nhip(dong_ho):
    so = tdq.SoTienDo()
    so.bat_dau_video(1, 1, "u")
    so.cap_nhat(tdq.GD_TAI, byte_da_nhan=1)
    bay_gio = dong_ho["now"]
    assert so.anh().canh_bao(bay_gio + 30) == ""
    cb = so.anh().canh_bao(bay_gio + 61)
    assert "chờ phản hồi mạng lâu bất thường" in cb and "61 giây" in cb
    so.cap_nhat(tdq.GD_KHOP, khop_tong=4, khop_xong=0)
    bay_gio = dong_ho["now"]
    assert so.anh().canh_bao(bay_gio + 300) == "", "so khớp khúc dài: 5 phút chưa phải bất thường"
    dong_ho["now"] = bay_gio + 650
    so.nhip()
    cb = so.anh().canh_bao(bay_gio + 655)
    assert "vẫn còn hoạt động" in cb, "audfprint còn nhịp → nói rõ là còn chạy, không báo treo"
    cb = so.anh().canh_bao(bay_gio + 900)
    assert "cần kiểm tra" in cb


def test_nhat_ky_co_gioi_han_va_bo_dong_lap(dong_ho):
    so = tdq.SoTienDo(toi_da_su_kien=5)
    for i in range(10):
        so.ghi(f"sự kiện {i}")
        so.ghi(f"sự kiện {i}")
    sk = so.su_kien(20)
    assert [s.noi_dung for s in sk] == [f"sự kiện {i}" for i in range(5, 10)]


def test_ghi_tu_nhieu_luong_khong_hong(dong_ho):
    so = tdq.SoTienDo()
    so.bat_dau_video(1, 1, "u")
    so.cap_nhat(tdq.GD_TAI)

    def ghi(n):
        for i in range(500):
            so.cap_nhat(byte_da_nhan=n * 1000 + i)
            so.nhip()

    luong = [threading.Thread(target=ghi, args=(k,)) for k in range(4)]
    for t in luong:
        t.start()
    for t in luong:
        t.join()
    assert so.anh().byte_da_nhan is not None


# ---------------------------------------------------------------- file -progress của ffmpeg

def test_doc_tien_do_ffmpeg_lay_khoi_hoan_chinh_cuoi(tmp_path):
    p = tmp_path / "p.txt"
    p.write_text(
        "total_size=1000\nout_time_us=1000000\nspeed=N/A\nprogress=continue\n"
        "total_size=52000\nout_time_us=600500000\nspeed=37.5x\nprogress=continue\n"
        "total_size=99999\nout_time_us=", encoding="utf-8")       # khối dở dang cuối: bỏ qua
    so = gst.doc_tien_do_ffmpeg(str(p))
    assert so == {"byte": 52000, "audio_s": pytest.approx(600.5), "toc_do_x": 37.5,
                  "ket_thuc": False}
    p.write_text("total_size=N/A\nout_time_us=N/A\nspeed=N/A\nprogress=end\n", encoding="utf-8")
    so = gst.doc_tien_do_ffmpeg(str(p))
    assert so["byte"] is None and so["audio_s"] is None and so["ket_thuc"] is True
    assert gst.doc_tien_do_ffmpeg(str(tmp_path / "khong_co.txt")) == {}


class _FF:
    """Tiến trình ffmpeg giả cho giám sát."""


def _giam_sat(tmp_path, *, ffmpeg=True, han=5.0):
    file_td = tmp_path / "td.txt"
    da_giet, so_lieu, nhip = [], [], []
    huy = threading.Event()
    gs = gst.GiamSatTai(str(tmp_path / "vid__p10800"), str(file_td), huy,
                        khi_so_lieu=so_lieu.append, khi_nhip=lambda: nhip.append(1),
                        han_dung_s=han, tim=lambda tt: [_FF()] if ffmpeg else [],
                        ham_giet=lambda ds: da_giet.append(len(ds)) or len(ds))
    return gs, file_td, huy, da_giet, so_lieu, nhip


def test_giam_sat_bao_so_lieu_that_va_nhip(tmp_path):
    gs, file_td, _huy, da_giet, so_lieu, nhip = _giam_sat(tmp_path)
    gs.tick(0.0)
    assert so_lieu == [] and nhip == [1], "chưa có byte: chỉ là nhịp sống"
    file_td.write_text("total_size=2048\nout_time_us=60000000\nspeed=20x\nprogress=continue\n",
                       encoding="utf-8")
    gs.tick(1.0)
    assert so_lieu == [{"byte_da_nhan": 2048, "audio_da_nhan_s": 60.0, "toc_do_x": 20.0}]
    assert da_giet == []


def test_huy_giet_ffmpeg_dang_tai(tmp_path):
    gs, _f, huy, da_giet, _s, _n = _giam_sat(tmp_path)
    gs.tick(0.0)
    huy.set()
    gs.tick(1.0)
    assert da_giet == [1] and gs.da_giet_vi_huy and not gs.dung_hinh


def test_mang_dung_qua_han_thi_giet_va_danh_dau(tmp_path):
    gs, file_td, _h, da_giet, _s, _n = _giam_sat(tmp_path, han=5.0)
    gs.tick(0.0)                                         # thấy ffmpeg lần đầu: đồng hồ bắt đầu
    file_td.write_text("total_size=10\nout_time_us=1\nprogress=continue\n", encoding="utf-8")
    gs.tick(3.0)                                         # có byte mới: đặt lại đồng hồ
    gs.tick(7.0)
    assert da_giet == [] and not gs.dung_hinh, "4 giây không có byte mới — chưa quá hạn 5 giây"
    gs.tick(8.5)
    assert gs.dung_hinh and da_giet == [1]


def test_khong_co_ffmpeg_thi_khong_giet_gi(tmp_path):
    gs, _f, huy, da_giet, _s, _n = _giam_sat(tmp_path, ffmpeg=False, han=1.0)
    huy.set()
    for t in range(10):
        gs.tick(float(t))
    assert da_giet == [] and not gs.dung_hinh, "tải thường (không ffmpeg): yt-dlp tự kiểm huỷ"
