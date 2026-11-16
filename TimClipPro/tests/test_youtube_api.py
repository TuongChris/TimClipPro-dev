# -*- coding: utf-8 -*-
"""YouTube Data API v3 (D-51, docs/YOUTUBE_DATA_API.md): đọc khoá, ``videos.list`` theo lô, phân loại lỗi TÁCH khỏi cầu
dao yt-dlp, lùi về yt-dlp, ngày đăng từ ``publishedAt``. Không mạng thật: transport giả ``tests/youtube_api_gia.py``;
khoá giả ghép chuỗi (không có khoá 39 ký tự trông như thật trong mã)."""

import publication_date as pd

# ---------------------------------------------------------------- ngày đăng từ snippet.publishedAt

# Asv1kjFuX-4 (docstring publication_date): timestamp yt-dlp 1785528034 = 2026-07-31 20:00:34 UTC.
EPOCH_THAT = 1785528034


def test_epoch_tu_published_at_nhan_z_giay_le_va_mui_gio():
    for s in ("2026-07-31T20:00:34Z", "2026-07-31T20:00:34.000Z", "2026-08-01T03:00:34+07:00",
              " 2026-07-31T20:00:34z "):
        assert pd.epoch_tu_published_at(s) == EPOCH_THAT, s
    assert pd.epoch_tu_published_at("2026-07-31T20:00:34.999Z") == EPOCH_THAT


def test_epoch_tu_published_at_khong_bia_ngay():
    for s in (None, "", "   ", "abc", 1785528034, "2026-07-31", "2026-07-31T20:00:34",
              "2026-13-01T00:00:00Z", "1999-12-31T23:59:59Z", "2101-01-01T00:00:00Z"):
        assert pd.epoch_tu_published_at(s) is None, s
        assert pd.ngay_utc_tu_published_at(s) == "", s


def test_ngay_utc_la_ngay_lich_utc_nhu_upload_date_cua_yt_dlp():
    """Mốc 17:00 UTC: giờ VN đã sang ngày mới, nhưng ngày V2 (D-51) là ngày UTC — video đăng bình thường giữ ngày cũ."""
    assert pd.ngay_utc_tu_published_at("2026-07-31T16:59:59Z") == "20260731"
    assert pd.ngay_utc_tu_published_at("2026-07-31T17:00:00Z") == "20260731"
    assert pd.ngay_utc_tu_published_at("2026-07-31T23:59:59.999Z") == "20260731"
    assert pd.ngay_utc_tu_published_at("2026-08-01T00:00:00Z") == "20260801"
    assert pd.ngay_utc_tu_published_at("2026-08-01T03:00:34+07:00") == "20260731"
    # Đối chứng: phép quy đổi giờ VN cũ cho ra ngày khác ở cùng mốc — không được dùng cho ngày V2.
    assert pd.ngay_tu_epoch(pd.epoch_tu_published_at("2026-07-31T17:00:00Z"), "Asia/Ho_Chi_Minh").isoformat() == (
        "2026-08-01")
