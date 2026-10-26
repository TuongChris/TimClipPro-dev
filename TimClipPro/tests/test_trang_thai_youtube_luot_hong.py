# -*- coding: utf-8 -*-
"""Audit D-10 (synthetic): «Trạng thái YouTube» ở thanh bên không được báo XANH «truy cập YouTube bình thường»
sau một lượt mà MỌI thao tác YouTube đều hỏng (cầu dao vẫn đóng vì chưa tới ngưỡng).

Không mạng, không dữ liệu thật: ``ham`` giả ném lỗi có câu giống yt-dlp; phiên dùng ``PhienYouTube`` thật và
``scan_ui.dong_trang_thai_youtube`` thật (đúng hàm app.py:759 gọi với ``eng.phien_youtube_cuoi``).
"""
from __future__ import annotations

import pytest

import scan_ui
import truy_cap_youtube as t


def _ham_loi(thong_diep: str):
    def ham():
        raise RuntimeError(thong_diep)
    return ham


def _dong_xanh_binh_thuong(dong: list) -> list:
    return [(muc, cau) for muc, cau in dong if muc == "success" and "bình thường" in cau]


@pytest.mark.parametrize("thong_diep, truong", [
    ("ERROR: unable to download video data: HTTP Error 403: Forbidden", "http_403"),
    ("ERROR: Read timed out", "transient"),
])
def test_lo_hong_het_khong_duoc_bao_xanh(thong_diep, truong):
    p = t.PhienYouTube()
    # Lô hai link: cả hai lượt tải đều hỏng; 2 < ngưỡng 3 nên cầu dao vẫn đóng.
    for vid in ("aaaaaaaaaaa", "bbbbbbbbbbb"):
        with pytest.raises(t.LoiTruyCapYouTube):
            p.chay("download", _ham_loi(thong_diep), video_id=vid)
    so = p.tom_tat()
    # Tiền đề của kịch bản (đúng như audit mô tả) — nếu hỏng ở đây là lỗi dựng test, không phải lỗi D-10.
    assert so["breaker_open"] is False
    assert so["youtube_operations"] == 2 and so["successes"] == 0 and so[truong] == 2

    dong = scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie(""), p, None)
    assert not _dong_xanh_binh_thuong(dong), (
        f"0 thao tác thành công / {so[truong]} lỗi ({truong}) mà thanh bên vẫn báo xanh: {dong}")


def test_doi_chung_co_thanh_cong_thi_duoc_bao_xanh():
    p = t.PhienYouTube()
    assert p.chay("download", lambda: "ok", video_id="ccccccccccc") == "ok"
    dong = scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie(""), p, None)
    assert _dong_xanh_binh_thuong(dong), dong


def test_duong_that_metadata_duoc_tai_403_khong_bao_xanh():
    """Đường quét thật: ``youtube_info`` (metadata) thành công rồi mới tải — mỗi link 1 thành công + 1 lỗi 403. Thành
    công của metadata xoá chuỗi liên tiếp nên cầu dao không bao giờ mở; vẫn không được nói «bình thường»."""
    p = t.PhienYouTube()
    for vid in ("aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"):
        assert p.chay("metadata", lambda: {"id": vid}, video_id=vid)
        with pytest.raises(t.LoiTruyCapYouTube):
            p.chay("download", _ham_loi("ERROR: unable to download video data: HTTP Error 403: Forbidden"),
                   video_id=vid)
    assert p.tom_tat()["breaker_open"] is False
    dong = scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie(""), p, None)
    assert not _dong_xanh_binh_thuong(dong), dong
    muc, cau = dong[0]
    assert muc == "info" and "3 thao tác YouTube thành công" in cau and "3 lỗi (HTTP 403: 3)" in cau
    assert "cookie" not in cau.lower(), "403 một mình không phải bằng chứng cookie hỏng"


def test_lo_hong_het_bao_canh_bao_kem_so_loi():
    p = t.PhienYouTube()
    for vid in ("aaaaaaaaaaa", "bbbbbbbbbbb"):
        with pytest.raises(t.LoiTruyCapYouTube):
            p.chay("download", _ham_loi("ERROR: unable to download video data: HTTP Error 403: Forbidden"),
                   video_id=vid)
    muc, cau = scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie(""), p, None)[0]
    assert muc == "warning" and "KHÔNG thao tác YouTube nào thành công" in cau and "2 lỗi (HTTP 403: 2)" in cau


def test_luot_chua_thao_tac_nao_xong_khong_bao_xanh():
    class _Dung(Exception):
        pass

    def ham():
        raise _Dung()

    p = t.PhienYouTube()
    with pytest.raises(_Dung):
        p.chay("download", ham, video_id="aaaaaaaaaaa", bo_qua=(_Dung,))
    dong = scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie(""), p, None)
    assert dong[0][0] == "info" and "chưa thao tác YouTube nào chạy xong" in dong[0][1]


def test_nhan_loi_phu_moi_truong_dem_loi():
    """Mọi trường ``_ghi_that_bai`` có thể tăng đều được tính vào tóm tắt — loại lỗi mới không lọt thành «xanh»."""
    # Hai nhóm rời nhau, hợp lại phủ đủ: lỗi truy cập (cộng vào «lỗi») + loại không phải lỗi (báo dòng riêng, DR-8).
    assert not set(t.NHAN_TRUONG_THAT_BAI) & set(t.NHAN_TRUONG_KHONG_PHAI_LOI)
    assert ({*t.NHAN_TRUONG_THAT_BAI, *t.NHAN_TRUONG_KHONG_PHAI_LOI}
            == {*t._DEM_THEO_LOAI.values(), "other_failures"})
    assert {*t.NHAN_TRUONG_THAT_BAI, *t.NHAN_TRUONG_KHONG_PHAI_LOI} <= set(t.TRUONG_SO_DO)
    # Loại «không phải lỗi» thì không bao giờ mở cầu dao.
    assert not {c for c, k in t._DEM_THEO_LOAI.items() if k in t.NHAN_TRUONG_KHONG_PHAI_LOI} & set(t.NGUONG_MO)
