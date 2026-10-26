# -*- coding: utf-8 -*-
"""Audit B-6: lượt Watch KHÔNG có video mới vẫn gửi việc đã tới hạn của lượt TRƯỚC.

Dữ liệu synthetic: ``lichsu.db`` tạm, khoá dịch vụ GIẢ, transport giả ``CongGia`` (không mạng).
Lượt Watch trước (``lo_cu``) gặp lỗi tạm của Google → việc ở RETRY_WAIT, nay ĐÃ tới hạn thử lại.
Lượt sau (``lo_moi``) không có gì mới để quét: đúng trình tự ``watch._thuc_hien_giam_sat`` —
``NguoiGuiNen.start()`` → (vòng quét rỗng) → ``_tong_ket_gui`` → ``nen.stop()``.

Mã cũ: ``cho_gui_xong`` chỉ đếm việc của lượt này (0) nên trả ngay, ``nen.stop()`` chạy trước khi
người gửi kịp giành quyền — transport không được gọi lần nào, việc nằm RETRY_WAIT tới lượt có
video mới / tới khi mở app, dù docstring ``_tong_ket_gui`` hứa «người gửi lượt sau» gửi tiếp.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import lich_su
import outbox as ob
import sheet_destinations as sd
import watch
from outbox_gia import CongGia, khoa_gia

IID = "c" * 32
HEADER = [f"Cột {i}" for i in range(1, 35)]


def _chuan_bi(tmp_path):
    """DB tạm + một hồ sơ đích + một việc của lượt trước đang RETRY_WAIT đã tới hạn."""
    data = tmp_path / "data"
    data.mkdir()
    db = str(data / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    d = sd.tao_dich(db, ten="Bảng A", spreadsheet_id="1" + "a" * 43, worksheet_id=0,
                    worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    y_cu = sd.chot_y_dinh(db, d.id, installation_id=IID, lo_id="lo_cu")
    with sd.ket_noi(db, ghi=True) as con:
        vid = ob.them_viec(con, y_cu, job_id=1, chinh_sach="v2", header=HEADER,
                           rows=[["dòng 1"] + [""] * 33])
        # Lượt trước: một lần lỗi tạm → RETRY_WAIT, hẹn thử lại đã qua.
        con.execute("UPDATE hang_doi_gui SET trang_thai=?, thu_lai_sau=0, so_lan_thu=1 WHERE id=?",
                    (ob.RETRY_WAIT, vid))
    y_moi = sd.chot_y_dinh(db, d.id, installation_id=IID, lo_id="lo_moi")
    return db, str(data), vid, y_moi


def _luot_rong(db, data, y_moi, cong):
    """Một lượt Watch không có gì để quét, đúng chu kỳ người gửi của watch.py."""
    engine = SimpleNamespace(sqlite_file=db, data_dir=data)
    nen = ob.NguoiGuiNen(db, data, lambda: cong, chu_ky_s=2.0, chu_ky_gianh_s=5.0)
    nen.start()                                     # như watch.py: sau lay_ung_vien
    bc = watch.BaoCao()
    try:
        watch._tong_ket_gui(engine, nen, y_moi, bc, 120.0)
    finally:
        nen.stop()                                  # ExitStack của lượt
    return bc


def test_luot_khong_co_gi_moi_van_gui_viec_toi_han_cua_luot_truoc(tmp_path):
    db, data, vid, y_moi = _chuan_bi(tmp_path)
    cong = CongGia()
    _luot_rong(db, data, y_moi, cong)
    assert ob.lay_viec(db, vid).trang_thai == ob.SENT, (
        f"việc tới hạn của lượt trước vẫn {ob.lay_viec(db, vid).trang_thai}; "
        f"số lần gọi transport = {cong.lan_goi}")
    assert len(cong.bang) == 1


def test_luot_rong_khong_ngoi_cho_khi_nguoi_gui_khac_giu_quyen(tmp_path):
    """Người gửi của app đang giữ quyền: lượt rỗng thôi chờ ngay sau một lần giành hụt (không ngồi
    đợi 10 s hay cả ``cho_gui_s``); việc để người gửi của app gửi."""
    db, data, vid, y_moi = _chuan_bi(tmp_path)
    app = ob.NguoiGui(db, data, CongGia())
    assert app.nhan_quyen()
    try:
        bat_dau = time.monotonic()
        _luot_rong(db, data, y_moi, CongGia())
        assert time.monotonic() - bat_dau < 5
    finally:
        app.tha_quyen()
    assert ob.lay_viec(db, vid).trang_thai == ob.RETRY_WAIT
