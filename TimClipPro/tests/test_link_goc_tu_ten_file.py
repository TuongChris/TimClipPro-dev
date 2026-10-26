# -*- coding: utf-8 -*-
"""Link video gốc lấy từ mã trong TÊN FILE — giới hạn đã chấp nhận (audit A-6, TCP-12, D-4).

Resolver bước 6 (``filename_fallback``) đọc mã video theo NGỮ PHÁP bộ tải
(``YYYYMMDD - <tiêu đề> [<11 ký tự>].<đuôi>``) khi kho không có mục metadata dùng được. Cú pháp
không phân biệt được mã thật với một chữ 11 ký tự: ``… [Compilation].mp3`` cho mã
``Compilation`` và báo cáo V2 dựng ``watch?v=Compilation`` — link không tồn tại. Phán quyết
audit A-6 (``DOC_ONLY``, P3): GIỮ hành vi này (bỏ link từ tên file sẽ xoá link hợp lệ của cả kho
legacy — 1631/1717 clip trong kho đã kiểm); chỉ ghi rõ trong REPORT_POLICY_V2 §1/§2,
CLIP_METADATA_ARCHITECTURE bước 6 và cảnh báo giao diện. Test này KHOÁ hành vi đã ghi trong tài
liệu để lần sau không ai «sửa» lặng lẽ theo một hướng nào (xoá link của kho legacy, hoặc bỏ nhánh
ambiguous an toàn). Muốn đổi: quyết định mới thay D-4/TCP-12, sửa tài liệu và test này cùng lúc.

Dữ liệu hoàn toàn tổng hợp; không mạng, không kho thật.
"""
from __future__ import annotations

import pytest

import bao_cao_v2 as v2
from bang_ngang import HEADER_NGANG
from clip_metadata import ClipMetadataResolver, source_from_mapping
from engine import Match, ScanResult

TEN_CHU_11 = [
    "20240101 - Best of Jeffy [Compilation].mp3",
    "20240101 - Live at the Hall [Performance].mp3",
    "20240101 - Nature Film [Documentary].opus",
]
MA_THAT = "dQw4w9WgXcQ"


def _ma_trong_ngoac(ten: str) -> str:
    return ten.rsplit("[", 1)[1].split("]", 1)[0]


@pytest.mark.parametrize("ten", TEN_CHU_11)
def test_chu_11_ky_tu_o_hau_to_van_doc_nhu_ma_va_dung_link(ten):
    """(1) Giới hạn đã chấp nhận: kho không metadata → filename_fallback/partial, có link."""
    ma = _ma_trong_ngoac(ten)
    meta = ClipMetadataResolver([]).resolve(ten)

    assert meta.resolution_method == "filename_fallback"
    assert meta.status == "partial"
    assert meta.video_id == ma
    assert meta.url == f"https://youtu.be/{ma}"
    assert "official_metadata_missing" in meta.warnings

    g = v2.goc_tu_metadata(meta.clip_name, meta)
    assert g.video_id == ma
    assert g.url == f"https://www.youtube.com/watch?v={ma}"
    assert g.trang_thai_metadata == "partial"
    assert g.nguon_tieu_de == v2.NGUON_TIEU_DE_TEN_FILE_KHO


def test_ma_that_o_hau_to_co_link_goc():
    """Đối chứng dương: tên do bộ tải đặt (mã thật) → link watch?v=<mã>."""
    ten = f"20240101 - Never Gonna [{MA_THAT}].opus"
    meta = ClipMetadataResolver([]).resolve(ten)
    g = v2.goc_tu_metadata(meta.clip_name, meta)

    assert meta.resolution_method == "filename_fallback" and meta.status == "partial"
    assert g.url == f"https://www.youtube.com/watch?v={MA_THAT}"


def test_metadata_mang_url_khac_hau_to_thi_ambiguous_khong_link():
    """(2) Lớp an toàn duy nhất của TCP-12: metadata nói mã khác hậu tố → mơ hồ, ô link trống."""
    ten = TEN_CHU_11[0]
    nguon = source_from_mapping({ten: {"url": f"https://youtu.be/{MA_THAT}"}}, kind="live")
    meta = ClipMetadataResolver([nguon]).resolve(ten)
    g = v2.goc_tu_metadata(meta.clip_name, meta)

    assert meta.status == "ambiguous"
    assert g.url == "" and g.video_id == ""


def test_khong_co_tien_to_ngay_thi_khong_doc_ma_khong_link():
    """(3) Tên không đúng ngữ pháp bộ tải (thiếu ``YYYYMMDD - ``) → basename_fallback, không link."""
    ten = "Best of Jeffy [Compilation].mp3"
    meta = ClipMetadataResolver([]).resolve(ten)
    g = v2.goc_tu_metadata(meta.clip_name, meta)

    assert meta.resolution_method == "basename_fallback"
    assert meta.video_id == "" and meta.url == ""
    assert g.url == "" and g.video_id == ""


def test_dong_ngang_va_dong_doc_mang_link_tu_ten_file():
    """Đầu-cuối: link từ tên file đi thẳng vào Sheets 34 cột và CSV 16 cột (không có cột nguồn).

    Đây là lý do tài liệu + cảnh báo giao diện phải dặn người dùng mở link kiểm tra trước khi
    dùng hồ sơ cho clip tự đặt tên/tự chép vào kho.
    """
    ten = TEN_CHU_11[0]
    meta = ClipMetadataResolver([]).resolve(ten)
    goc = v2.goc_tu_metadata(ten, meta)
    m = Match(clip=ten, start_s=100.0, end_s=200.0, matched_s=90.0, clip_offset_s=0.0,
              hashes=5000, confidence="Rất chắc chắn", ty_le=60.0, vung="Đầu",
              clip_bat_dau_s=100.0, vung_khop_s=100.0)
    kq = ScanResult(source_name="Video thử", source_ref="https://www.youtube.com/watch?v=vidvipham01",
                    source_id="vidvipham01", duration_s=600.0, matches=[m], so_dat_nguong=1)
    bc = v2.dung_bao_cao(
        kq, thoi_diem_quet="2026-01-02 03:04:05", nguon_loai="youtube", tieu_de="Video thử",
        nguon_tieu_de=v2.NGUON_TIEU_DE_YTDLP, ly_do_thieu_tieu_de="",
        ngay_dang=v2.NgayNguon(gia_tri="20260315", nguon=v2.NGUON_UPLOAD_DATE),
        goc_theo_clip={ten: goc}, mo_ta_pham_vi="thử")

    o = dict(zip(HEADER_NGANG, v2.dong_ngang(bc)))
    assert o["Link video gốc 1"] == "https://www.youtube.com/watch?v=Compilation"
    assert any("watch?v=Compilation" in str(x) for dong in v2.dong_doc(bc) for x in dong)
