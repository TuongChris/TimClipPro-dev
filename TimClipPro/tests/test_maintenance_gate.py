# -*- coding: utf-8 -*-
"""Cổng bảo trì (docs/MANAGED_RUNTIME_DESIGN.md §6-§7): admission control giữa việc nghiệp vụ và updater.

* Mỗi việc (lô quét, lượt Watch, dựng kho, một lần gửi Sheets…) giữ một LEASE (khoá HĐH) suốt thời gian
  chạy; lease tạo dưới mutex ngắn của cổng.
* Updater bật cờ RÚT dưới cùng mutex đó → từ lúc ấy không việc mới nào được nhận (không race giữa
  "kiểm rảnh" và "kích hoạt"), rồi CHỜ CÓ HẠN các lease đang có; hết hạn thì huỷ rút, giữ bản cũ.
* Không bao giờ giết việc; lease/cờ rút của tiến trình đã chết không chặn ai (khoá HĐH tự nhả).
"""
import os
import subprocess
import sys
import textwrap
import threading
import time

import pytest

import maintenance_gate as mg


@pytest.fixture()
def cong(tmp_path):
    return mg.CongBaoTri(str(tmp_path / "data"))


def test_viec_giu_lease_va_tra_khi_xong(cong, tmp_path):
    with cong.viec("lô quét YouTube"):
        dang = cong.viec_dang_chay()
        assert [v["ten"] for v in dang] == ["lô quét YouTube"]
    assert cong.viec_dang_chay() == []
    assert not [f for f in os.listdir(cong.thu_muc) if f.startswith(mg.TIEN_TO_VIEC)]


def test_viec_loi_van_tra_lease(cong):
    with pytest.raises(ValueError):
        with cong.viec("dựng kho"):
            raise ValueError("lỗi của việc")
    assert cong.viec_dang_chay() == []


def test_dang_rut_thi_tu_choi_viec_moi(cong):
    rut = cong.bat_dau_rut("cập nhật lên 1.2.0")
    try:
        with pytest.raises(mg.DangBaoTri) as loi:
            with cong.viec("lượt Watch"):
                pass
        assert "cập nhật" in str(loi.value)
        assert cong.trang_thai_rut()["chu"] == "cập nhật lên 1.2.0"
    finally:
        rut.ket_thuc()
    with cong.viec("lượt Watch"):
        pass


def test_rut_cho_viec_dang_chay_xong_khong_giet(cong):
    bat_dau, xong = threading.Event(), threading.Event()

    def viec_dai():
        with cong.viec("lô quét"):
            bat_dau.set()
            xong.wait(10)

    t = threading.Thread(target=viec_dai)
    t.start()
    assert bat_dau.wait(5)
    rut = cong.bat_dau_rut("cập nhật")
    try:
        assert rut.cho_ranh(han_s=0.3, chu_ky_s=0.05) is False      # việc còn chạy → chưa rảnh
        assert t.is_alive()                                        # không bị giết
        xong.set()
        t.join(5)
        assert rut.cho_ranh(han_s=5, chu_ky_s=0.05) is True
    finally:
        rut.ket_thuc()


def test_khong_race_viec_dang_vao_cong_luc_bat_rut(cong, monkeypatch):
    """Việc đã vượt kiểm cờ rút nhưng chưa tạo lease: updater phải CHỜ mutex, rồi thấy lease đó."""
    trong_mutex, cho_phep = threading.Event(), threading.Event()
    goc = cong._tao_lease

    def tao_lease_cham(ten):
        trong_mutex.set()
        cho_phep.wait(5)
        return goc(ten)

    monkeypatch.setattr(cong, "_tao_lease", tao_lease_cham)
    giu, xong = threading.Event(), threading.Event()

    def viec():
        with cong.viec("lô quét"):
            giu.set()
            xong.wait(10)

    t = threading.Thread(target=viec)
    t.start()
    assert trong_mutex.wait(5)
    ket = {}

    def updater():
        ket["rut"] = cong.bat_dau_rut("cập nhật")

    u = threading.Thread(target=updater)
    u.start()
    time.sleep(0.2)
    assert "rut" not in ket                      # updater đang chờ mutex của cổng
    cho_phep.set()
    assert giu.wait(5)
    u.join(5)
    rut = ket["rut"]
    try:
        assert rut.cho_ranh(han_s=0.2, chu_ky_s=0.05) is False  # thấy lease vừa tạo
    finally:
        xong.set()
        t.join(5)
        rut.ket_thuc()


def test_hai_updater_khong_rut_cung_luc(cong):
    rut = cong.bat_dau_rut("cập nhật A")
    try:
        with pytest.raises(mg.DangBaoTri):
            cong.bat_dau_rut("cập nhật B")
    finally:
        rut.ket_thuc()


def test_co_rut_mo_coi_khong_chan_viec(cong):
    """Updater chết giữa chừng (cờ còn, khoá rút đã nhả theo tiến trình) → cờ vô hiệu, việc vẫn chạy."""
    os.makedirs(cong.thu_muc, exist_ok=True)
    with open(os.path.join(cong.thu_muc, mg.TEN_CO_RUT), "w", encoding="utf-8") as f:
        f.write('{"chu": "updater đã chết", "pid": 999999}')
    assert cong.trang_thai_rut() is None
    with cong.viec("lô quét"):
        pass
    assert not os.path.exists(os.path.join(cong.thu_muc, mg.TEN_CO_RUT))


def test_lease_mo_coi_khong_chan_rut(cong):
    os.makedirs(cong.thu_muc, exist_ok=True)
    mo_coi = os.path.join(cong.thu_muc, mg.TIEN_TO_VIEC + "dead.lock")
    with open(mo_coi, "w", encoding="utf-8") as f:
        f.write("\nPID: 999999\nTác vụ: lô quét cũ")
    rut = cong.bat_dau_rut("cập nhật")
    try:
        assert rut.cho_ranh(han_s=1, chu_ky_s=0.05) is True
    finally:
        rut.ket_thuc()
    assert not os.path.exists(mo_coi)


def test_kiem_them_tu_choi_viec_khi_ban_moi_da_kich_hoat(tmp_path):
    cong = mg.CongBaoTri(str(tmp_path / "data"),
                         kiem_them=lambda: "Bản mới đã được kích hoạt — đóng và mở lại ứng dụng.")
    with pytest.raises(mg.DangBaoTri) as loi:
        with cong.viec("lô quét"):
            pass
    assert "mở lại" in str(loi.value)


def test_lease_cua_tien_trinh_khac_duoc_thay_va_tu_nha_khi_tien_trinh_chet(cong, tmp_path):
    """Khoá HĐH thật giữa HAI tiến trình: lease của tiến trình con chặn rút; giết con → lease mồ côi."""
    ma = textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {os.path.dirname(os.path.abspath(mg.__file__))!r})
        import maintenance_gate as mg
        with mg.CongBaoTri({cong.data_dir!r}).viec("tiến trình con"):
            print("san_sang", flush=True)
            time.sleep(60)
    """)
    con = subprocess.Popen([sys.executable, "-c", ma], stdout=subprocess.PIPE, text=True)
    try:
        assert con.stdout.readline().strip() == "san_sang"
        assert [v["ten"] for v in cong.viec_dang_chay()] == ["tiến trình con"]
        rut = cong.bat_dau_rut("cập nhật")
        try:
            assert rut.cho_ranh(han_s=0.3, chu_ky_s=0.05) is False
            con.kill()
            con.wait(10)
            assert rut.cho_ranh(han_s=5, chu_ky_s=0.05) is True
        finally:
            rut.ket_thuc()
    finally:
        if con.poll() is None:
            con.kill()
            con.wait(10)
