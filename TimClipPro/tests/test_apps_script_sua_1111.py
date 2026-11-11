# -*- coding: utf-8 -*-
"""Apps Script (Google Sheet) — 6 lỗi của audit tổng 11/11, tái hiện trên Google Sheet GIẢ chạy bằng Node.

Bộ giả (`apps_script_gia.js`) chạy đúng tệp người dùng dán vào Sheet (`TOAN_BO_AppsScript.gs`, sinh từ 7 tệp gốc —
test cuối kiểm hai bên không lệch). Không gọi Google; chỉ giả lập phần API các hàm dưới đây dùng.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess

import pytest

NODE = shutil.which("node")
TESTS = os.path.dirname(os.path.abspath(__file__))
THU_MUC_GS = os.path.join(os.path.dirname(TESTS), "apps_script")
TOAN_BO = os.path.join(THU_MUC_GS, "TOAN_BO_AppsScript.gs")
GIA = os.path.join(TESTS, "apps_script_gia.js")
can_node = pytest.mark.skipif(not NODE, reason="cần Node.js")


def _chay(tmp_path, than_js):
    f = tmp_path / "than.js"
    f.write_text(than_js, encoding="utf-8")
    r = subprocess.run(
        [NODE, GIA, TOAN_BO, str(f)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout)


TRANG_THAI = r"""
const tieuDe = KETQUAQUET_COT_MAC_DINH.concat([KET_QUA_JSON_FIELDS.STATUS]);
const cot = tieuDe.length;
const dong = (trangThai) => KETQUAQUET_COT_MAC_DINH.map(() => 'x').concat([trangThai]);
"""


@can_node
def test_chuan_hoa_trang_thai_giu_nguyen_cong_thuc(tmp_path):
    """Chuẩn hoá cột «Trạng thái» đọc GIÁ TRỊ rồi ghi lại CẢ cột (kể cả khi không sửa gì): ô công thức thành chữ cứng."""
    kq = _chay(
        tmp_path,
        TRANG_THAI
        + r"""
const s = taoSheet('KetQuaQuet', [tieuDe, dong({ v: 'đã làm', f: '=IF(A2<>"","đã làm","")' }), dong('Đã làm')], 6000);
thietLapChuanHoaTrangThai();
return { congThuc: s.o_(2, cot).f, hang3: s.o_(3, cot).v };
""",
    )
    assert kq == {"congThuc": '=IF(A2<>"","đã làm","")', "hang3": "đã làm"}


@can_node
def test_chuan_hoa_trang_thai_tren_trang_it_hang_khong_loi(tmp_path):
    """Danh sách thả xuống áp cho 5000 hàng từ hàng 2: trang chưa tới 5001 hàng (mặc định 1000) → «outside the
    dimensions of the sheet», menu hỏng ngay sau khi đã sửa một phần."""
    kq = _chay(
        tmp_path,
        TRANG_THAI
        + r"""
const s = taoSheet('KetQuaQuet', [tieuDe, dong('Đã làm')], 1000);
thietLapChuanHoaTrangThai();
return { soHang: s.getMaxRows(), kiemTra: s.kiemTra.map(k => [k.hang, k.cot, k.soHang]), hang2: s.o_(2, cot).v, cot: cot };
""",
    )
    assert kq["soHang"] >= 5001
    assert kq["kiemTra"] == [[2, kq["cot"], 5000]]
    assert kq["hang2"] == "đã làm"


@can_node
@pytest.mark.parametrize("co_tieu_de", [False, True])
def test_mo_bang_ket_qua_json_khong_de_dong_dau(tmp_path, co_tieu_de):
    """«Mở bảng Ket_Qua_Json» (và mỗi lần xuất) GHI ĐÈ hàng 1 bằng tiêu đề: người dùng đã xoá hàng tiêu đề → báo cáo
    đầu tiên mất hẳn."""
    kq = _chay(
        tmp_path,
        r"""
const bao = [1, 'KetQuaQuet', 2, '01/01/2026', 'BÁO CÁO GỐC'];
const s = taoSheet('Ket_Qua_Json', (%s ? [KET_QUA_JSON_CONFIG.OUTPUT_HEADERS] : []).concat([bao]), 1000);
moBangKetQuaJson();
return { tieuDe: KET_QUA_JSON_CONFIG.OUTPUT_HEADERS, h1: s.getRange(1, 1, 1, 5).getValues()[0],
         h2: s.getRange(2, 1, 1, 5).getValues()[0], soHang: s.getLastRow() };
"""
        % ("true" if co_tieu_de else "false"),
    )
    assert kq["h1"] == kq["tieuDe"]
    assert kq["h2"][4] == "BÁO CÁO GỐC"
    assert kq["soHang"] == 2


@can_node
def test_cot_link_nguon_doi_ten_khong_to_lai_link_da_quet(tmp_path):
    """Cột «Link video vi phạm» bị đổi tên (tiêu đề vẫn nhận ra nhờ các cột khác) → tập «đã quét» RỖNG → mọi link ở
    «Link SML» bị tô về trắng như chưa quét, không báo gì (đúng kiểu hỏng im lặng README từng ghi)."""
    kq = _chay(
        tmp_path,
        r"""
const LINK = 'https://www.youtube.com/watch?v=abcdefghijk';
const URL = KET_QUA_JSON_FIELDS.INFRINGING_URL;
taoSheet('KetQuaQuet', [KETQUAQUET_COT_MAC_DINH.map(t => (t === URL ? 'Video URL' : t)),
                        KETQUAQUET_COT_MAC_DINH.map(t => (t === URL ? LINK : 'x'))], 1000);
const bang = taoSheet('Link SML', [['Link'], [{ v: LINK, nen: MAU_SAC.DA_QUET_NEN }]], 1000);
const tk = danhDauLinkDaQuetTatCa_();
const b = tk.theoBang.find(x => x.sheetName === 'Link SML');
return { nen: bang.o_(2, 1).nen, daQuetNen: MAU_SAC.DA_QUET_NEN, choXuLy: b.choXuLy, loi: b.loi || '' };
""",
    )
    assert kq["nen"] == kq["daQuetNen"]
    assert kq["choXuLy"] == 0
    assert "Link video vi phạm" in kq["loi"]


@can_node
def test_thoi_luong_tren_24_gio_dang_so_khong_quay_vong(tmp_path):
    """Ô thời lượng dạng SỐ (ngày) định dạng hh:mm:ss hiện «18:00:00» cho 66 giờ — báo cáo xuất ra sai 48 giờ."""
    kq = _chay(
        tmp_path,
        r"""
return [dinhDangThoiLuong_(2.75, '18:00:00'), dinhDangThoiLuong_(2.75, '66:00:00'),
        dinhDangThoiLuong_(0.5, '12:00:00'), dinhDangThoiLuong_('01:02:03', '01:02:03'),
        dinhDangThoiLuong_('', '')];
""",
    )
    assert kq == ["66:00:00", "66:00:00", "12:00:00", "1:02:03", ""]


@can_node
def test_hai_lan_khoi_phuc_tieu_de_cung_luc_chi_chen_mot_hang(tmp_path):
    """Phòng hờ: hộp thoại xác nhận mở trong lúc một lần khôi phục khác (tab khác) đã chèn xong hàng tiêu đề → bấm
    «Có» chèn THÊM một hàng tiêu đề, hàng đó bị đọc như dữ liệu quét."""
    kq = _chay(
        tmp_path,
        r"""
const dong = KETQUAQUET_COT_MAC_DINH.map((t, i) => 'gia_tri_' + i);
const s = taoSheet('KetQuaQuet', [dong, dong], 1000);   // mất hàng tiêu đề: hàng 1 là dữ liệu
ui.khi = function () {
  ui.khi = () => 'YES';
  khoiPhucHangTieuDeKetQuaQuet();   // lần khôi phục khác chạy xong trong lúc hộp thoại này còn mở
  return 'YES';
};
khoiPhucHangTieuDeKetQuaQuet();
return { tieuDe0: KETQUAQUET_COT_MAC_DINH[0], cotA: [1, 2, 3, 4].map(r => s.getRange(r, 1).getValue()) };
""",
    )
    assert kq["cotA"] == [kq["tieuDe0"], "gia_tri_0", "gia_tri_0", ""]


@can_node
def test_xuat_hang_khi_bang_ket_qua_het_hang_trong(tmp_path):
    """Ket_Qua_Json tích dần mỗi lần xuất; lưới đầy (mặc định 1000 hàng) → getRange ngoài lưới → mọi lần xuất sau
    đều «Không thể chuyển đổi dữ liệu»."""
    kq = _chay(
        tmp_path,
        r"""
const dong = KETQUAQUET_COT_MAC_DINH.map((t, i) => 'gia_tri_' + i);
const nguon = taoSheet('KetQuaQuet', [KETQUAQUET_COT_MAC_DINH, dong, dong], 1000);
const ra = taoSheet('Ket_Qua_Json', [KET_QUA_JSON_CONFIG.OUTPUT_HEADERS], 2);   // lưới còn đúng 1 hàng trống
ss.hoatDong = nguon;
ss.vungChon = nguon.getRange(2, 1, 2, 1);
xuatHangDaChonSangKetQuaJson();
return { soHang: ra.getLastRow(), hangNguon: [2, 3].map(r => ra.getRange(r, 3).getValue()),
         loi: ui.thongBao.filter(t => String(t[0]).indexOf('Không thể') === 0).length };
""",
    )
    assert kq == {"soHang": 3, "hangNguon": [2, 3], "loi": 0}


def test_toan_bo_sinh_dung_tu_bay_tep_goc():
    """`TOAN_BO_AppsScript.gs` là bản người dùng dán vào Sheet — phải đúng là bản gộp của 7 tệp gốc (README)."""
    spec = importlib.util.spec_from_file_location(
        "gop_toan_bo", os.path.join(THU_MUC_GS, "gop_toan_bo.py")
    )
    gop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gop)
    with open(TOAN_BO, encoding="utf-8") as f:
        assert f.read().replace("\r\n", "\n") == gop.gop(), (
            "chạy apps_script/gop_toan_bo.py sau khi sửa tệp gốc"
        )
