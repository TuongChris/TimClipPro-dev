# -*- coding: utf-8 -*-
"""Cuối lượt Watch khi việc gửi Google Sheets đang TẠM DỪNG (audit B-5).

Dữ liệu synthetic: ``lichsu.db`` tạm, khoá dịch vụ GIẢ, transport giả ``CongGia`` (không mạng). Một
việc PENDING của lượt ``L``; người dùng đã bật «⏸ Tạm dừng toàn bộ việc gửi» (``dat_tam_dung``) hoặc
«⏸ Tạm dừng gửi» của hồ sơ đích. Người gửi nền của Watch (``NguoiGuiNen``) giữ quyền như trong
``watch._thuc_hien_giam_sat``.

Đang tạm dừng thì người gửi KHÔNG nhận việc (HUONG_DAN_PC2 «Tạm dừng toàn bộ»: việc vẫn xếp hàng;
bật lại thì gửi tiếp). Trước đây lượt vẫn ngồi chờ hết ``cho_gui_s`` (giữ ``tool.lock``) rồi báo
«sẽ tự gửi tiếp» — người quên tắt tạm dừng không biết vì sao Sheet không có dòng mới.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

import lich_su
import outbox as ob
import sheet_destinations as sd
import watch
from outbox_gia import CongGia, khoa_gia

IID = "c" * 32
HEADER = [f"Cột {i}" for i in range(1, 35)]
CHO_GUI_S = 3.0


def _moi_truong(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    db = str(data / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    d = sd.tao_dich(db, ten="Bảng A", spreadsheet_id="1" + "a" * 43, worksheet_id=0,
                    worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    y = sd.chot_y_dinh(db, d.id, installation_id=IID, lo_id="L")
    with sd.ket_noi(db, ghi=True) as con:
        ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=HEADER,
                     rows=[["dòng 1"] + [""] * 33])
    return db, str(data), y, d


def _tong_ket(db, data, y):
    engine = SimpleNamespace(sqlite_file=db, data_dir=data)
    nen = ob.NguoiGuiNen(db, data, CongGia, chu_ky_s=2.0, chu_ky_gianh_s=5.0)
    nen.start()
    bc = watch.BaoCao()
    try:
        bat_dau = time.monotonic()
        watch._tong_ket_gui(engine, nen, y, bc, CHO_GUI_S)
        da = time.monotonic() - bat_dau
    finally:
        nen.stop()
    return bc, da


@pytest.mark.parametrize("cach", ["toan_bo", "ho_so"])
def test_cuoi_luot_watch_bao_tam_dung_va_khong_cho_het_han(tmp_path, cach):
    db, data, y, d = _moi_truong(tmp_path)
    if cach == "toan_bo":
        ob.dat_tam_dung(db, True)                   # người dùng bật tạm dừng rồi quên
    else:
        sd.doi_trang_thai(db, d.id, sd.TT_TAM_DUNG)
    bc, da = _tong_ket(db, data, y)
    assert bc.gui[ob.PENDING] == 1                  # việc vẫn bền trong hàng đợi
    for chu in (bc.sheets_note, bc.tom_tat()):
        assert "TẠM DỪNG" in chu, chu
    assert "sẽ tự gửi tiếp" not in bc.sheets_note + bc.tom_tat()
    assert da < CHO_GUI_S * 0.5, f"chờ {da:.1f} s / {CHO_GUI_S} s dù việc gửi đang tạm dừng"


def test_khong_tam_dung_van_gui_va_khong_bao_tam_dung(tmp_path):
    db, data, y, _ = _moi_truong(tmp_path)
    bc, _ = _tong_ket(db, data, y)
    assert bc.gui[ob.SENT] == 1 and bc.gui[ob.PENDING] == 0
    assert "TẠM DỪNG" not in bc.sheets_note + bc.tom_tat()
