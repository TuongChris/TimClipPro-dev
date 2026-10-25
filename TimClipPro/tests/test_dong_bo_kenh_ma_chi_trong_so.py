"""Audit D-7 (tổng hợp, ngoại tuyến): «Kiểm tra còn thiếu» và «Đồng bộ kênh» phải nói cùng một điều về mã CHỈ có trong
sổ đã tải (``downloaded.txt``) mà kho không có file (người dùng xoá file hỏng, phần mềm diệt virus / OneDrive cách ly,
archive cũ).

Trước đây «Kiểm tra» liệt kê mã đó là còn thiếu và hứa «chỉ những video này được tải», còn đồng bộ lại đếm nó là «có
sẵn (giữ nguyên)», không tải, báo xanh «✅ Đồng bộ xong». Thiết kế giữ nguyên: đồng bộ KHÔNG tự tải lại mã chỉ có trong
sổ (người dùng có thể đã chủ ý xoá) — nhưng cả hai màn hình báo riêng nhóm này và chỉ đường «Dựng lại danh sách đã
tải». Không mạng: ``list_channel`` và bước tải được thay bằng bản giả.
"""
from __future__ import annotations

import os

from channel import DONG_BO_DAY_DU, ChannelSync, VideoInfo
from scan_ui import tom_tat_dong_bo_kenh

VID = "vidA0000000"


def _kho_chi_co_so(tmp_path):
    cs = ChannelSync(str(tmp_path / "kho"))
    with open(cs.archive, "w", encoding="utf-8") as f:
        f.write(f"youtube {VID}\n")
    cs.list_channel = lambda *a, **k: [VideoInfo(VID, "Video A", "20260101", 600, f"https://youtu.be/{VID}")]
    # Không có file âm thanh nào của VID trong kho.
    assert not [t for t in os.listdir(cs.dest) if VID in t]
    return cs


def test_kiem_tra_thieu_va_dong_bo_nhat_quan_voi_ma_chi_co_trong_so(tmp_path):
    cs = _kho_chi_co_so(tmp_path)

    r_kiem = cs.kiem_tra_thieu("kenh")
    thieu = [v.id for v in r_kiem["thieu"]]

    goi_tai: list = []

    def tai_gia(v):
        goi_tai.append(v.id)
        raise RuntimeError("synthetic: không tải thật")

    cs._tai_va_nen = tai_gia
    r_sync = cs.sync("kenh")
    tieu_de = tom_tat_dong_bo_kenh(r_sync)[0]

    print("kiem_tra_thieu thieu =", thieu, "co_roi =", r_kiem["co_roi"])
    print("sync can_tai =", r_sync["can_tai"], "bo_qua =", r_sync["bo_qua"], "trang_thai =", r_sync["trang_thai"],
          "goi_tai =", goi_tai)
    print("tieu_de UI =", tieu_de)

    if VID in thieu:
        # «Kiểm tra» đã hứa: đồng bộ sẽ tải đúng video này. Đồng bộ phải giữ lời (thử tải) hoặc ít nhất KHÔNG báo
        # xanh «xong» và đếm nó là «có sẵn (giữ nguyên)» trong khi kho không có file.
        assert goi_tai == [VID] or r_sync["trang_thai"] != DONG_BO_DAY_DU, (
            f"Kiểm tra báo còn thiếu {thieu} và hứa đồng bộ sẽ tải, nhưng đồng bộ không thử tải "
            f"(can_tai={r_sync['can_tai']}, bo_qua={r_sync['bo_qua']}, trang_thai={r_sync['trang_thai']}) "
            f"và báo: {tieu_de[1]!r}")
    else:
        # Ngược lại: nếu kiểm tra coi nó là «đã có», đồng bộ được bỏ qua — nhất quán.
        assert goi_tai == []


def test_dong_bo_khong_dem_ma_khong_co_file_la_co_san(tmp_path):
    cs = _kho_chi_co_so(tmp_path)
    cs._tai_va_nen = lambda v: (_ for _ in ()).throw(RuntimeError("synthetic: không tải thật"))

    r_sync = cs.sync("kenh")
    co_file = [t for t in os.listdir(cs.dest) if VID in t]

    # «có sẵn N (giữ nguyên)» chỉ đúng khi kho thật sự có file; mã chỉ nằm trong sổ mà không có file thì phải được
    # tính riêng (hoặc tải lại), không lẫn vào «có sẵn».
    assert r_sync["bo_qua"] <= len(co_file) or r_sync.get("trong_so_khong_file"), (
        f"bo_qua={r_sync['bo_qua']} nhưng kho có {len(co_file)} file của {VID}; "
        f"UI: {tom_tat_dong_bo_kenh(r_sync)[0][1]!r}")


def test_hai_man_hinh_bao_rieng_ma_chi_trong_so_va_chi_duong_dung_lai(tmp_path):
    cs = _kho_chi_co_so(tmp_path)
    cs._tai_va_nen = lambda v: (_ for _ in ()).throw(AssertionError("không được tải mã chỉ có trong sổ"))

    r_kiem = cs.kiem_tra_thieu("kenh")
    assert r_kiem["thieu"] == [] and r_kiem["co_roi"] == 0
    assert [v.id for v in r_kiem["trong_so_khong_file"]] == [VID]

    r_sync = cs.sync("kenh")
    assert r_sync["bo_qua"] == 0 and r_sync["can_tai"] == 0 and r_sync["trong_so_khong_file"] == 1
    dong = tom_tat_dong_bo_kenh(r_sync)
    assert "trong sổ đã tải nhưng không có file **1**" in dong[0][1]
    assert any(muc == "warning" and "Dựng lại danh sách đã tải" in cau for muc, cau in dong), dong


def test_sau_khi_dung_lai_so_kiem_tra_va_dong_bo_cung_tai_lai(tmp_path):
    cs = _kho_chi_co_so(tmp_path)
    cs.sua_archive()                   # «Dựng lại danh sách đã tải»: sổ chỉ còn mã thật có file

    assert [v.id for v in cs.kiem_tra_thieu("kenh")["thieu"]] == [VID]
    goi_tai: list = []

    def tai_gia(v):
        goi_tai.append(v.id)
        raise RuntimeError("synthetic: không tải thật")

    cs._tai_va_nen = tai_gia
    r = cs.sync("kenh")
    assert goi_tai == [VID] and r["trong_so_khong_file"] == 0 and r["trang_thai"] != DONG_BO_DAY_DU


def test_ma_trong_so_co_file_nghi_hong_van_la_con_thieu_va_duoc_tai_lai(tmp_path):
    cs = _kho_chi_co_so(tmp_path)
    open(os.path.join(cs.dest, f"Video A [{VID}].opus"), "wb").close()   # file 0 byte = nghi hỏng

    r_kiem = cs.kiem_tra_thieu("kenh")
    assert [v.id for v in r_kiem["thieu"]] == [VID] and r_kiem["trong_so_khong_file"] == []
    goi_tai: list = []
    cs._tai_va_nen = lambda v: goi_tai.append(v.id) or (_ for _ in ()).throw(RuntimeError("synthetic"))
    r = cs.sync("kenh")
    assert goi_tai == [VID] and r["trong_so_khong_file"] == 0 and r["bo_qua"] == 0
