# -*- coding: utf-8 -*-
"""Báo cáo cuối lượt Watch phải nêu việc gửi ``BLOCKED_REPORT`` của lượt (audit B-11).

Dữ liệu synthetic: ``lichsu.db`` tạm, khoá dịch vụ GIẢ, không mạng. Lượt Watch ``L`` ghim hồ sơ «Bảng A».
Một video quét XONG (``status='ok'``, báo cáo V2 hợp lệ) nhưng dựng dòng Sheets ném lỗi: chạy ĐÚNG
``Engine._xep_hang_gui`` (đồ giả cho ``self``: chỉ ý định gửi + ``dong_gui_sheets`` ném ``RuntimeError``) →
hàng đợi có MỘT việc ``BLOCKED_REPORT`` không payload (không bao giờ gửi, không tự thử lại; lịch sử đã
ghi video là 'ok' nên Watch không quét lại).

Trước đây ``_tong_ket_gui`` chỉ tính ``BLOCKED_CONFIG``/``UNKNOWN``: lượt báo Sheets sạch, không một dòng
lỗi — trong khi CLI ``_in_tong_ket_gui`` và giao diện đều cộng ``BLOCKED_REPORT`` vào «bị chặn». Việc
``BLOCKED_REPORT`` do báo cáo V2 lỗi thì Watch đã báo bằng dòng của chính video — không lặp lại.
"""
from __future__ import annotations

from types import SimpleNamespace

import bao_cao_v2
import engine as engine_mod
import lich_su
import outbox as ob
import sheet_destinations as sd
import watch
from outbox_gia import khoa_gia

IID = "c" * 32


def _loi_dung_dong(*a, **k):
    raise RuntimeError("lỗi dựng dòng giả")


def _y_dinh(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    db = str(data / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    d = sd.tao_dich(db, ten="Bảng A", spreadsheet_id="1" + "a" * 43, worksheet_id=0,
                    worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    return db, str(data), sd.chot_y_dinh(db, d.id, installation_id=IID, lo_id="L")


def _xep_hang(db, y, bao_cao):
    """Chạy ĐÚNG ``Engine._xep_hang_gui`` như ``save_job`` của lượt quét (một giao dịch)."""
    gia_self = SimpleNamespace(_y_dinh_gui=y, dong_gui_sheets=_loi_dung_dong)
    kq = SimpleNamespace(status="ok", bao_cao=bao_cao)
    with sd.ket_noi(db, ghi=True) as con:
        assert engine_mod.Engine._xep_hang_gui(gia_self, con, kq, 7) is True
    assert ob.tom_tat(db, lo_id="L")[ob.BLOCKED_REPORT] == 1        # tiền đề: việc bị chặn có trong hàng đợi


def test_viec_blocked_report_do_dung_dong_hien_trong_bao_cao_watch(tmp_path):
    db, data, y = _y_dinh(tmp_path)
    _xep_hang(db, y, SimpleNamespace(chinh_sach="v2"))

    bc = watch.BaoCao(dich_gui=y.dich.nhan)
    watch._tong_ket_gui(SimpleNamespace(sqlite_file=db, data_dir=data), None, y, bc, 0.0)
    tom_tat = bc.tom_tat()
    assert bc.sheets_ok is False, f"lượt có việc BLOCKED_REPORT vẫn sheets_ok=True; loi={bc.loi!r}"
    assert "bị chặn 1" in tom_tat, f"tóm tắt Watch không nhắc việc bị chặn:\n{tom_tat}"
    dong_sheets = [d for d in bc.loi if d.startswith("Google Sheets:")]
    assert len(dong_sheets) == 1 and "Không dựng được dòng gửi" in dong_sheets[0], bc.loi


def test_viec_blocked_report_do_bao_cao_v2_loi_khong_bao_lap(tmp_path):
    """Báo cáo V2 lỗi: Watch đã ghi dòng «<video>: <thông báo>» lúc quét — tóm tắt vẫn đếm «bị chặn»
    nhưng không thêm dòng lỗi Google Sheets trùng nội dung."""
    db, data, y = _y_dinh(tmp_path)
    loi_bc = bao_cao_v2.LoiBaoCaoV2(bao_cao_v2.LOI_TAO, ngoai_le="ValueError")
    _xep_hang(db, y, loi_bc)

    bc = watch.BaoCao(dich_gui=y.dich.nhan)
    bc.loi.append(f"Video A: {loi_bc.thong_bao()}")      # đúng dòng của `_thuc_hien_giam_sat`
    watch._tong_ket_gui(SimpleNamespace(sqlite_file=db, data_dir=data), None, y, bc, 0.0)
    assert bc.sheets_ok is False
    assert "bị chặn 1" in bc.tom_tat()
    assert bc.loi == [f"Video A: {loi_bc.thong_bao()}"], bc.loi
