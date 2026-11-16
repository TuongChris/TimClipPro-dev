# -*- coding: utf-8 -*-
"""YouTube Data API v3 (D-51, docs/YOUTUBE_DATA_API.md): đọc khoá, ``videos.list`` theo lô, phân loại lỗi TÁCH khỏi cầu
dao yt-dlp, lùi về yt-dlp, ngày đăng từ ``publishedAt``. Không mạng thật: transport giả ``tests/youtube_api_gia.py``;
khoá giả ghép chuỗi (không có khoá 39 ký tự trông như thật trong mã)."""

import pytest

import publication_date as pd
import truy_cap_youtube as t

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


# ---------------------------------------------------------------- chính sách thuần (truy_cap_youtube)

def _loi_google(ma, *ly_do, trang_thai="", chi_tiet=(), thong_diep="x"):
    loi = {"code": ma, "message": thong_diep, "errors": [{"reason": r, "domain": "youtube"} for r in ly_do]}
    if trang_thai:
        loi["status"] = trang_thai
    if chi_tiet:
        loi["details"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": r} for r in chi_tiet]
    return {"error": loi}


@pytest.mark.parametrize("ma, than, loai", [
    (403, _loi_google(403, "quotaExceeded"), t.API_HET_HAN_MUC),
    (403, _loi_google(403, "dailyLimitExceeded"), t.API_HET_HAN_MUC),
    (400, _loi_google(400, "badRequest", trang_thai="INVALID_ARGUMENT", chi_tiet=["API_KEY_INVALID"]), t.API_KHOA_HONG),
    (400, _loi_google(400, "keyInvalid"), t.API_KHOA_HONG),
    (400, _loi_google(400, "keyExpired"), t.API_KHOA_HONG),
    (403, _loi_google(403, "accessNotConfigured"), t.API_KHOA_HONG),
    (403, _loi_google(403, trang_thai="PERMISSION_DENIED", chi_tiet=["SERVICE_DISABLED"]), t.API_KHOA_HONG),
    (403, _loi_google(403, chi_tiet=["API_KEY_SERVICE_BLOCKED"]), t.API_KHOA_HONG),
    (403, _loi_google(403, chi_tiet=["API_KEY_HTTP_REFERRER_BLOCKED"]), t.API_KHOA_HONG),
    (403, _loi_google(403, "forbidden"), t.API_KHOA_HONG),
    (403, None, t.API_KHOA_HONG),
    (401, None, t.API_KHOA_HONG),
    (403, _loi_google(403, "rateLimitExceeded"), t.API_GIOI_HAN),
    (403, _loi_google(403, "userRateLimitExceeded"), t.API_GIOI_HAN),
    (429, _loi_google(429, trang_thai="RESOURCE_EXHAUSTED", chi_tiet=["RATE_LIMIT_EXCEEDED"]), t.API_GIOI_HAN),
    (429, None, t.API_GIOI_HAN),
    (500, None, t.API_TAM_THOI),
    (503, _loi_google(503, "backendError"), t.API_TAM_THOI),
    (None, None, t.API_TAM_THOI),
    (200, None, t.API_PHAN_HOI_LA),
    (302, None, t.API_PHAN_HOI_LA),
    (404, _loi_google(404, "notFound"), t.API_PHAN_HOI_LA),
    (400, _loi_google(400, "badRequest"), t.API_PHAN_HOI_LA),
    (400, "<html>proxy</html>", t.API_PHAN_HOI_LA),
    (400, {"error": "chuỗi thay vì object"}, t.API_PHAN_HOI_LA),
])
def test_phan_loai_loi_api_chi_theo_ly_do_google_va_ma_http(ma, than, loai):
    assert t.phan_loai_loi_api(ma, than) == loai


def test_phan_loai_loi_api_khong_doc_chu_trong_message():
    """Chữ trong ``message`` có thể đổi theo ngôn ngữ/phiên bản — chỉ ``reason``/``status`` + mã HTTP được tin."""
    than = _loi_google(400, "badRequest", thong_diep="quotaExceeded keyInvalid rateLimitExceeded")
    assert t.phan_loai_loi_api(400, than) == t.API_PHAN_HOI_LA


def test_phien_api_tat_toi_het_luot_theo_nguong_va_noi_ro_ly_do():
    api = t.PhienApiYouTube()
    assert t.NGUONG_TAT_API[t.API_TAM_THOI] == 3
    assert not api.ghi_loi(t.API_TAM_THOI) and not api.ghi_loi(t.API_TAM_THOI)
    api.ghi_thanh_cong()                               # thành công xen giữa: đếm lại từ đầu
    assert not api.ghi_loi(t.API_TAM_THOI) and not api.ghi_loi(t.API_TAM_THOI) and not api.tat
    assert api.ghi_loi(t.API_TAM_THOI) and api.tat and api.loai_tat == t.API_TAM_THOI
    assert api.ly_do_tat == t.THONG_BAO_API[t.API_TAM_THOI] and "yt-dlp" in api.ly_do_tat
    api.ghi_thanh_cong()
    assert api.tat, "đã tắt thì giữ tới hết lượt"
    for loai in (t.API_HET_HAN_MUC, t.API_KHOA_HONG, t.API_GIOI_HAN, t.API_PHAN_HOI_LA):
        moi = t.PhienApiYouTube()
        assert moi.ghi_loi(loai) and moi.loai_tat == loai, loai
        assert moi.ly_do_tat and moi.ly_do_tat != api.ly_do_tat, loai
    assert set(t.THONG_BAO_API) == set(t.CAC_LOAI_API) == set(t.NGUONG_TAT_API)


def test_phien_youtube_co_phien_con_api_rieng_dung_chung_ham_cho():
    da_cho = []

    def cho(giay, ev=None):
        da_cho.append(giay)
        return False

    p = t.PhienYouTube(ham_cho=cho)
    assert isinstance(p.api, t.PhienApiYouTube)
    assert p.api.cho_thu_lai(None) is False and da_cho == [t.CHO_THU_LAI_API_S] == [3.0]
    p.api.ghi_yeu_cau()
    p.api.ghi_loi(t.API_KHOA_HONG)
    p.api.ghi_video(2, ["lý do A", "lý do A", "lý do B"])
    so = p.tom_tat()
    assert not p.mo and so["breaker_open"] is False and so["http_403"] == 0 and so["successes"] == 0
    assert so["api"] == {"yeu_cau": 1, "don_vi": 1, "video_api": 2, "video_lui": 3, "tat": True,
                         "loai_tat": t.API_KHOA_HONG, "ly_do_tat": t.THONG_BAO_API[t.API_KHOA_HONG],
                         "ly_do_lui": "lý do A; lý do B"}
    assert t.PhienYouTube().api is not p.api


def test_dong_trang_thai_api():
    assert t.dong_trang_thai_api({}) == "" == t.dong_trang_thai_api(None)
    assert t.dong_trang_thai_api(t.PhienApiYouTube().tom_tat()) == ""
    assert t.dong_trang_thai_api({"video_api": 12, "don_vi": 1, "video_lui": 0}) == (
        "API YouTube: 12 video lấy bằng API (~1 đơn vị)")
    assert t.dong_trang_thai_api({"video_api": 50, "don_vi": 2, "video_lui": 70, "ly_do_lui": "hết hạn mức"}) == (
        "API YouTube: 50 video lấy bằng API (~2 đơn vị) · 70 video lùi về yt-dlp — hết hạn mức")
