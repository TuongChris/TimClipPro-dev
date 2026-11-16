# -*- coding: utf-8 -*-
"""YouTube Data API v3 (D-51, docs/YOUTUBE_DATA_API.md): đọc khoá, ``videos.list`` theo lô, phân loại lỗi TÁCH khỏi cầu
dao yt-dlp, lùi về yt-dlp, ngày đăng từ ``publishedAt``. Không mạng thật: transport giả ``tests/youtube_api_gia.py``;
khoá giả ghép chuỗi (không có khoá 39 ký tự trông như thật trong mã)."""

import dataclasses
import json
import logging
import os
import threading
import urllib.request

import pytest

import publication_date as pd
import truy_cap_youtube as t
import youtube_api as ya
import youtube_api_gia as gia

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


# ---------------------------------------------------------------- youtube_api: file khoá

def _ghi_khoa(thu_muc, noi_dung, ma_hoa="utf-8"):
    f = thu_muc / ya.TEN_FILE_KHOA
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(noi_dung.encode(ma_hoa) if isinstance(noi_dung, str) else noi_dung)
    return str(f)


def _loi_khoa(path):
    """Đọc phải hỏng; thông điệp chỉ nêu TÊN file — không thư mục, không phần nào của khoá, không lỗi gốc bám theo."""
    with pytest.raises(ya.LoiKhoaApi) as ei:
        ya.doc_khoa_api(path)
    tin = str(ei.value)
    assert ya.TEN_FILE_KHOA in tin and os.path.dirname(path) not in tin
    assert gia.KHOA_GIA not in tin and "GiaKhongBiMat" not in tin
    assert ei.value.__cause__ is None and ei.value.__context__ is None
    return tin


def test_duong_dan_khoa_co_dinh_canh_data_dir(tmp_path):
    data = str(tmp_path / "data")
    assert ya.duong_dan_khoa_api(data) == os.path.join(str(tmp_path), "secrets", "youtube_api_key.txt")
    assert ya.duong_dan_khoa_api(data + os.sep) == ya.duong_dan_khoa_api(data)


def test_doc_khoa_bo_dong_trong_chu_thich_va_bom(tmp_path):
    assert ya.doc_khoa_api(str(tmp_path / "khong_co" / ya.TEN_FILE_KHOA)) == ""
    noi_dung = "﻿# khoá YouTube Data API\r\n\r\n   " + gia.KHOA_GIA + "  \r\n# hết\r\n"
    assert ya.doc_khoa_api(_ghi_khoa(tmp_path, noi_dung)) == gia.KHOA_GIA
    assert issubclass(ya.LoiKhoaApi, ValueError)


@pytest.mark.parametrize("noi_dung, ma_hoa, chu", [
    (gia.KHOA_GIA + "\n" + gia.KHOA_GIA[:-1] + "B\n", "utf-8", "nhiều hơn một dòng"),
    (gia.KHOA_GIA + "\n", "utf-16", "lưu lại dạng UTF-8"),      # Notepad «Unicode» / PowerShell 5.1 (có BOM)
    (gia.KHOA_GIA + "\n", "utf-16-le", "UTF-16"),               # không BOM
    ("# chỉ có chú thích\n\n", "utf-8", "không có dòng khoá"),
    (gia.KHOA_GIA[:-1] + "\n", "utf-8", "không đúng dạng"),
    (gia.KHOA_GIA + "0\n", "utf-8", "không đúng dạng"),
    ('"' + gia.KHOA_GIA + '"\n', "utf-8", "không đúng dạng"),
    ("key = " + gia.KHOA_GIA + "\n", "utf-8", "không đúng dạng"),
    ("Bza" + gia.KHOA_GIA[3:] + "\n", "utf-8", "không đúng dạng"),
])
def test_doc_khoa_sai_dang_chi_neu_ten_file(tmp_path, noi_dung, ma_hoa, chu):
    assert chu in _loi_khoa(_ghi_khoa(tmp_path, noi_dung, ma_hoa))


def test_doc_khoa_qua_lon_khong_phai_utf8_hay_la_thu_muc(tmp_path):
    assert "4 KB" in _loi_khoa(_ghi_khoa(tmp_path / "a", "#" * 5000 + "\n" + gia.KHOA_GIA + "\n"))
    assert "UTF-8" in _loi_khoa(_ghi_khoa(tmp_path / "b", b"\xc3\x28" + gia.KHOA_GIA.encode()))
    (tmp_path / "c" / ya.TEN_FILE_KHOA).mkdir(parents=True)
    assert "Không đọc được" in _loi_khoa(str(tmp_path / "c" / ya.TEN_FILE_KHOA))


def test_doc_khoa_nho_theo_duong_dan_gio_sua_va_co(tmp_path, monkeypatch):
    path = _ghi_khoa(tmp_path, gia.KHOA_GIA + "\n")
    doc_that = ya._doc_file_khoa
    so_lan = []
    monkeypatch.setattr(ya, "_doc_file_khoa", lambda p, ten: so_lan.append(p) or doc_that(p, ten))
    assert ya.doc_khoa_api(path) == gia.KHOA_GIA == ya.doc_khoa_api(path)
    assert len(so_lan) == 1
    _ghi_khoa(tmp_path, "# đã đổi\n" + gia.KHOA_GIA + "\n")         # khác cỡ → đọc lại
    assert ya.doc_khoa_api(path) == gia.KHOA_GIA and len(so_lan) == 2
    _ghi_khoa(tmp_path, "sai\n")
    _loi_khoa(path)
    _loi_khoa(path)
    assert len(so_lan) == 3, "lỗi cũng được nhớ theo (đường dẫn, giờ sửa, cỡ)"


def test_trang_thai_khoa_cho_giao_dien_khong_mang_khoa(tmp_path, khoa_api_that):
    data = str(tmp_path / "data")
    tt = ya.trang_thai_khoa(data)
    assert (tt.ma, tt.ly_do) == (ya.CHUA_CO, "") and tt.duong_dan == ya.duong_dan_khoa_api(data)
    assert tt.duong_dan in tt.cau and "yt-dlp" in tt.cau
    _ghi_khoa(tmp_path / "secrets", "khong phai khoa\n")
    tt = ya.trang_thai_khoa(data)
    assert tt.ma == ya.SAI_DANG and "không đúng dạng" in tt.ly_do and tt.ly_do in tt.cau
    _ghi_khoa(tmp_path / "secrets", gia.KHOA_GIA + "\n")
    tt = ya.trang_thai_khoa(data)
    assert (tt.ma, tt.ly_do) == (ya.CO_KHOA, "")
    for chuoi in (repr(tt), str(tt), tt.cau, repr(dataclasses.asdict(tt))):
        assert gia.KHOA_GIA not in chuoi and "GiaKhongBiMat" not in chuoi
    with pytest.raises(dataclasses.FrozenInstanceError):
        tt.ma = ya.CHUA_CO


def test_mac_dinh_moi_test_chay_nhu_chua_co_khoa(tmp_path):
    """Fixture autouse (conftest): dù file khoá nằm đúng chỗ, test không xin ``khoa_api_that``/``api_youtube_gia`` vẫn
    thấy «chưa có khoá» — máy có khoá thật không gửi yêu cầu API nào khi chạy test."""
    _ghi_khoa(tmp_path / "secrets", gia.KHOA_GIA + "\n")
    assert ya.trang_thai_khoa(str(tmp_path / "data")).ma == ya.CHUA_CO
    assert ya._doc_khoa_cho(str(tmp_path / "data")) == ""


# ---------------------------------------------------------------- youtube_api: link dùng được API

MA = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={MA}", f"http://youtube.com/watch?v={MA}&t=42s&list=PL0123",
    f"https://m.youtube.com/watch?feature=share&v={MA}", f"https://music.youtube.com/watch?v={MA}",
    f"https://youtu.be/{MA}", f"https://youtu.be/{MA}?si=abc", f"https://www.youtube.com/shorts/{MA}",
    f"https://www.youtube.com/live/{MA}?feature=share", f"https://www.youtube.com/embed/{MA}",
    f"https://www.youtube-nocookie.com/embed/{MA}", f"https://youtube-nocookie.com/embed/{MA}",
    f"  https://WWW.YouTube.com/watch?v={MA}  ",
])
def test_ma_video_cho_api_nhan_link_video_youtube(url):
    assert ya.ma_video_cho_api(url) == MA


@pytest.mark.parametrize("url", [
    "", None, MA, f"youtube.com/watch?v={MA}", f"ftp://www.youtube.com/watch?v={MA}",
    "https://www.youtube.com/channel/UCkenhGia000000000000000", "https://www.youtube.com/@kenh/videos",
    "https://www.youtube.com/@kenh/live", "https://www.youtube.com/playlist?list=PL0123456789",
    "https://www.youtube.com/watch?list=PL0123456789", "https://www.youtube.com/embed/videoseries?list=PL0123",
    "https://www.twitch.tv/videos/123456789", f"https://www.twitch.tv/x?v={MA}",
    f"https://youtube.com.evil.example/watch?v={MA}", f"https://evilyoutube.com/watch?v={MA}",
    f"https://youtube.co/watch?v={MA}", f"https://www.youtube.com@evil.example/watch?v={MA}",
    "https://www.youtube.com/watch?v=dQw4w9WgXc", "https://www.youtube.com/watch?v=dQw4w9WgXcQQ",
    "https://youtu.be/dQw4w9WgXc", "https://www.youtube.com/shorts/dQw4w9WgXcQQ",
    f"https://youtu.be/{MA}/khac", f"https://www.youtube.com/shorts/{MA}/khac",
    "https://www.youtube.com/watch?v=dQw4w9WgX!Q", "http://[::1",
])
def test_ma_video_cho_api_tu_choi_moi_thu_khac(url):
    assert ya.ma_video_cho_api(url) == ""


@pytest.mark.parametrize("iso, giay", [("PT1H2M3S", 3723), ("PT45S", 45), ("P1DT2H", 93600), ("P0D", 0), (None, 0),
                                       ("", 0), ("PT", 0), ("1:02:03", 0), ("PT10M", 600), ("P1W", 604800),
                                       ("PT1.5S", 1)])
def test_thoi_luong_iso8601(iso, giay):
    assert ya.thoi_luong_giay(iso) == giay


# ---------------------------------------------------------------- youtube_api: lay_video

def _phien():
    da_cho = []

    def cho(giay, ev=None):
        da_cho.append(giay)
        return False

    return t.PhienYouTube(ham_cho=cho), da_cho


def _ma(i):
    return f"vid{i:08d}"


def _so_ytdlp(phien):
    """Mọi số đo + cầu dao của yt-dlp (không gồm phần API, thời gian)."""
    so = phien.tom_tat()
    return {k: so[k] for k in t.TRUONG_SO_DO} | {"breaker_open": so["breaker_open"], "mo": phien.mo}


def test_120_ma_thanh_ba_lo_50_50_20_moi_ma_mot_lan_giu_thu_tu(api_youtube_gia, tmp_path):
    ids = [_ma(i) for i in range(120)]
    for m in ids:
        api_youtube_gia.video[m] = gia.video_gia(m)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "cau_hinh.json").write_text(json.dumps({"network_timeout_s": 17}), encoding="utf-8")
    phien, da_cho = _phien()
    truoc = _so_ytdlp(phien)
    kq = ya.lay_video(phien, str(tmp_path / "data"), ids + ids[:5])
    yc = api_youtube_gia.yeu_cau
    assert [len(y.ids) for y in yc] == [50, 50, 20]
    assert [m for y in yc for m in y.ids] == ids
    assert all(y.endpoint == "videos" and y.key_in_header and y.timeout == 17 for y in yc)
    assert all(y.part == "snippet,contentDetails,liveStreamingDetails" and y.params["fields"].startswith("items(")
               for y in yc)
    assert list(kq.thong_tin) == ids and kq.thieu == () and kq.ly_do_lui == ""
    m = ids[0]
    assert kq.thong_tin[m] == {"id": m, "title": f"Video {m}", "duration": 600, "channel": "Kênh giả",
                               "uploader": "Kênh giả", "channel_id": gia.KENH_GIA,
                               "channel_url": "https://www.youtube.com/channel/" + gia.KENH_GIA,
                               "published_at": "2026-07-31T20:00:34Z", "live_broadcast_content": "none"}
    so = phien.tom_tat()["api"]
    assert (so["yeu_cau"], so["don_vi"], so["video_api"], so["video_lui"], so["tat"]) == (3, 3, 120, 0, False)
    assert da_cho == [] and _so_ytdlp(phien) == truoc, "lượt API thành công không chạm số đo yt-dlp"
    with pytest.raises(dataclasses.FrozenInstanceError):
        kq.thieu = ()


def test_het_han_muc_o_yeu_cau_2_tat_api_toi_het_luot_ca_luong_khac(api_youtube_gia, tmp_path):
    ids = [_ma(i) for i in range(120)]
    for m in ids:
        api_youtube_gia.video[m] = gia.video_gia(m)
    api_youtube_gia.kich_ban = [None, gia.QUOTA]
    phien, da_cho = _phien()
    truoc = _so_ytdlp(phien)
    data = str(tmp_path / "data")
    kq = ya.lay_video(phien, data, ids)
    assert list(kq.thong_tin) == ids[:50] and kq.thieu == tuple(ids[50:])
    assert kq.ly_do_lui == t.THONG_BAO_API[t.API_HET_HAN_MUC] and phien.api.tat
    assert api_youtube_gia.dem() == 2 and da_cho == []
    ket_luong = []
    luong = threading.Thread(target=lambda: ket_luong.append(ya.lay_video(phien, data, ids[:3])))
    luong.start()
    luong.join()
    assert ket_luong[0].thieu == tuple(ids[:3]) and ket_luong[0].thong_tin == {}
    assert api_youtube_gia.dem() == 2, "đã tắt: không gửi thêm yêu cầu nào trong lượt, kể cả từ luồng khác"
    assert _so_ytdlp(phien) == truoc, "lỗi API không chạm cầu dao / bộ đếm yt-dlp"
    so = phien.tom_tat()["api"]
    assert (so["yeu_cau"], so["video_api"], so["video_lui"], so["loai_tat"]) == (2, 50, 73, t.API_HET_HAN_MUC)
    assert t.dong_trang_thai_api(so).startswith(
        "API YouTube: 50 video lấy bằng API (~2 đơn vị) · 73 video lùi về yt-dlp — Hết hạn mức")


@pytest.mark.parametrize("loi", [gia.KEY_INVALID, gia.API_DISABLED])
def test_khoa_hong_hay_api_chua_bat_tat_api_va_noi_ro_ly_do(api_youtube_gia, tmp_path, caplog, loi):
    caplog.set_level(logging.DEBUG)
    a, b = _ma(1), _ma(2)
    api_youtube_gia.video[a] = gia.video_gia(a)
    api_youtube_gia.kich_ban = [loi]
    phien, da_cho = _phien()
    truoc = _so_ytdlp(phien)
    kq = ya.lay_video(phien, str(tmp_path / "data"), [a, b])
    assert kq.thong_tin == {} and kq.thieu == (a, b)
    assert kq.ly_do_lui == t.THONG_BAO_API[t.API_KHOA_HONG] and "Google Cloud" in kq.ly_do_lui
    assert phien.api.loai_tat == t.API_KHOA_HONG and api_youtube_gia.dem() == 1 and da_cho == []
    assert _so_ytdlp(phien) == truoc
    for chuoi in (repr(kq), repr(phien.tom_tat()), caplog.text):
        assert gia.SO_DU_AN_GIA not in chuoi and gia.KHOA_GIA not in chuoi


@pytest.mark.parametrize("loi", [gia.SERVER, gia.TIMEOUT, gia.THAN_CUT])
def test_loi_tam_thoi_thu_lai_mot_lan_qua_ham_cho_roi_thanh_cong(api_youtube_gia, tmp_path, loi):
    m = _ma(1)
    api_youtube_gia.video[m] = gia.video_gia(m)
    api_youtube_gia.kich_ban = [loi, None]
    phien, da_cho = _phien()
    kq = ya.lay_video(phien, str(tmp_path / "data"), [m])
    assert list(kq.thong_tin) == [m] and kq.thieu == ()
    assert da_cho == [t.CHO_THU_LAI_API_S] and api_youtube_gia.dem() == 2 and not phien.api.tat
    assert phien.tom_tat()["api"]["don_vi"] == 2


def test_ba_loi_tam_thoi_lien_tiep_thi_tat_api(api_youtube_gia, tmp_path):
    ids = [_ma(i) for i in range(120)]
    api_youtube_gia.kich_ban = [gia.SERVER] * 10
    phien, da_cho = _phien()
    truoc = _so_ytdlp(phien)
    kq = ya.lay_video(phien, str(tmp_path / "data"), ids)
    assert kq.thieu == tuple(ids) and kq.thong_tin == {}
    assert api_youtube_gia.dem() == 3 and da_cho == [t.CHO_THU_LAI_API_S]
    assert phien.api.loai_tat == t.API_TAM_THOI
    assert kq.ly_do_lui == ya.LY_DO_TAM_THOI + "; " + t.THONG_BAO_API[t.API_TAM_THOI]
    assert _so_ytdlp(phien) == truoc


def test_ma_vang_sap_phat_dang_phat_vao_thieu(api_youtube_gia, tmp_path):
    co, vang, sap, dang, xong = (_ma(i) for i in range(5))
    api_youtube_gia.video.update({
        co: gia.video_gia(co, duration="PT1H2M3S"),
        sap: gia.video_gia(sap, live="upcoming", duration="P0D"),
        dang: gia.video_gia(dang, live="active", actual_start="2026-11-16T01:00:00Z"),
        xong: gia.video_gia(xong, duration="P1DT2H", actual_start="2026-11-15T10:00:00Z"),
    })
    phien, _ = _phien()
    kq = ya.lay_video(phien, str(tmp_path / "data"), [co, vang, sap, dang, xong])
    assert list(kq.thong_tin) == [co, xong] and kq.thieu == (vang, sap, dang)
    assert kq.thong_tin[co]["duration"] == 3723 and kq.thong_tin[xong]["duration"] == 93600
    assert kq.thong_tin[xong]["actual_start_time"] == "2026-11-15T10:00:00Z"
    assert "actual_start_time" not in kq.thong_tin[co] and "privacy_status" not in kq.thong_tin[co]
    assert kq.ly_do_lui == ya.LY_DO_VANG + "; " + ya.LY_DO_SAP_PHAT
    so = phien.tom_tat()["api"]
    assert (so["yeu_cau"], so["video_api"], so["video_lui"], so["tat"]) == (1, 2, 3, False)


def test_ma_la_trong_items_bi_bo_qua(api_youtube_gia, tmp_path):
    """Mục của mã KHÔNG hỏi bị bỏ qua — kể cả khi trông lạ (không làm tắt API)."""
    m = _ma(1)
    api_youtube_gia.kich_ban = [{"items": [{"id": "zzzzzzzzzzz", "snippet": "rác"}, gia.video_gia(m)]}]
    phien, _ = _phien()
    kq = ya.lay_video(phien, str(tmp_path / "data"), [m])
    assert list(kq.thong_tin) == [m] and kq.thieu == () and not phien.api.tat


@pytest.mark.parametrize("than", [b"<html>cong dang nhap wifi</html>", {"items": "khong phai danh sach"},
                                  {"items": [{"id": "vid00000000", "snippet": "x"}]}, {"items": [["sai"]]},
                                  b"[1, 2]"])
def test_phan_hoi_2xx_sai_dang_tat_api(api_youtube_gia, tmp_path, than):
    api_youtube_gia.kich_ban = [than]
    phien, da_cho = _phien()
    kq = ya.lay_video(phien, str(tmp_path / "data"), [_ma(0)])
    assert kq.thieu == (_ma(0),) and phien.api.loai_tat == t.API_PHAN_HOI_LA and da_cho == []
    assert kq.ly_do_lui == t.THONG_BAO_API[t.API_PHAN_HOI_LA]


def test_chuyen_huong_hay_than_qua_4mb_tat_api(api_youtube_gia, tmp_path, monkeypatch):
    m = _ma(1)
    api_youtube_gia.video[m] = gia.video_gia(m)
    api_youtube_gia.kich_ban = [gia.CHUYEN_HUONG]
    phien, _ = _phien()
    assert ya.lay_video(phien, str(tmp_path / "data"), [m]).thieu == (m,)
    assert phien.api.loai_tat == t.API_PHAN_HOI_LA
    monkeypatch.setattr(ya, "GIOI_HAN_THAN", 10)          # thân lớn hơn trần: sai dạng, KHÔNG phải «thân cụt»
    phien, da_cho = _phien()
    assert ya.lay_video(phien, str(tmp_path / "data"), [m]).thieu == (m,)
    assert phien.api.loai_tat == t.API_PHAN_HOI_LA and da_cho == []


def test_can_trang_thai_them_part_status(api_youtube_gia, tmp_path):
    m = _ma(1)
    api_youtube_gia.video[m] = gia.video_gia(m, privacy="unlisted")
    kq = ya.lay_video(_phien()[0], str(tmp_path / "data"), [m], can_trang_thai=True)
    yc = api_youtube_gia.yeu_cau[0]
    assert yc.part == "snippet,contentDetails,liveStreamingDetails,status" and "status(" in yc.params["fields"]
    assert (kq.thong_tin[m]["privacy_status"], kq.thong_tin[m]["upload_status"]) == ("unlisted", "processed")


def test_ly_do_tung_ma_tach_vang_sap_phat_lo_loi_va_ma_sai(api_youtube_gia, tmp_path):
    """Lý do của TỪNG mã trong ``thieu``: nơi gọi KHÔNG lùi về yt-dlp (kiểm video còn trên YouTube) phải tách mã vắng trong
    phản hồi 200 (riêng tư / đã gỡ) khỏi lô lỗi và video sắp phát / đang phát — ``ly_do_lui`` gộp chung không tách được."""
    ids = [_ma(i) for i in range(51)]
    vang, sap = ids[1], ids[2]
    for m in ids:
        if m != vang:
            api_youtube_gia.video[m] = gia.video_gia(m, live="upcoming" if m == sap else "none")
    api_youtube_gia.kich_ban = [None, gia.QUOTA]
    kq = ya.lay_video(_phien()[0], str(tmp_path / "data"), ids + ["sai"], can_trang_thai=True)
    assert kq.thieu == (vang, sap, ids[50], "sai")
    assert kq.ly_do_tung_ma == {vang: ya.LY_DO_VANG, sap: ya.LY_DO_SAP_PHAT,
                                ids[50]: t.THONG_BAO_API[t.API_HET_HAN_MUC], "sai": ya.LY_DO_MA_SAI}


def test_ma_sai_dang_khong_gui_di(api_youtube_gia, tmp_path):
    m = _ma(1)
    api_youtube_gia.video[m] = gia.video_gia(m)
    sai = ["", "ngan", "a" * 12, "abc,defghij", "abcdefghi j"]
    kq = ya.lay_video(_phien()[0], str(tmp_path / "data"), sai + [m])
    assert [y.ids for y in api_youtube_gia.yeu_cau] == [(m,)]
    assert kq.thieu == tuple(sai) and kq.ly_do_lui == ya.LY_DO_MA_SAI


@pytest.mark.parametrize("buoc", [None, gia.QUOTA, gia.KEY_INVALID, gia.TIMEOUT])
def test_khoa_khong_bao_gio_lot_ra(api_youtube_gia, tmp_path, caplog, buoc):
    caplog.set_level(logging.DEBUG)
    m = _ma(1)
    api_youtube_gia.video[m] = gia.video_gia(m)
    api_youtube_gia.kich_ban = [buoc] * 3
    phien, _ = _phien()
    data = str(tmp_path / "data")
    kq = ya.lay_video(phien, data, [m])
    assert api_youtube_gia.yeu_cau and all(y.key_in_header for y in api_youtube_gia.yeu_cau)
    api_youtube_gia.kich_ban = [buoc]
    loi = None
    try:
        ya._gui(ya.GOC_API + "videos?id=" + m, gia.KHOA_GIA, 5)
    except ya._LoiApi as e:
        loi = e
    chuoi_loi = []
    while loi is not None:
        chuoi_loi.append(f"{loi!r} {loi}")
        loi = loi.__cause__ or loi.__context__
    for c in [caplog.text, repr(kq), str(kq), repr(phien.tom_tat()), repr(api_youtube_gia.yeu_cau),
              repr(ya.trang_thai_khoa(data)), *chuoi_loi]:
        assert gia.KHOA_GIA not in c and "GiaKhongBiMat" not in c


def test_goi_dung_chung_cho_endpoint_khac_khoa_khong_roi_module(api_youtube_gia, tmp_path, monkeypatch):
    """``_goi`` cho endpoint khác (search.list, part=status… của nhánh khác): khoá đọc BÊN TRONG youtube_api, đơn vị hạn
    mức theo endpoint, trả JSON thô khi không có ``doc``."""
    api_youtube_gia.kich_ban = [{"items": [{"id": {"videoId": _ma(1)}}]}]
    phien, _ = _phien()
    data = str(tmp_path / "data")
    ket, ly_do = ya._goi(phien, data, "search", {"part": "snippet", "q": "clip", "type": "video"}, don_vi=100)
    assert ket == {"items": [{"id": {"videoId": _ma(1)}}]} and ly_do == ""
    yc = api_youtube_gia.yeu_cau[0]
    assert yc.endpoint == "search" and yc.key_in_header and yc.params["q"] == "clip"
    assert phien.tom_tat()["api"]["don_vi"] == 100
    monkeypatch.setattr(ya, "_doc_khoa_cho", lambda data_dir: "")
    assert ya._goi(phien, data, "search", {"q": "x"}) == (None, ya.LY_DO_CHUA_CO_KHOA)
    assert api_youtube_gia.dem() == 1


def test_khong_co_khoa_khong_gui_yeu_cau_nao(monkeypatch, tmp_path):
    tp = gia.lap_transport(monkeypatch)
    phien, _ = _phien()
    kq = ya.lay_video(phien, str(tmp_path / "data"), [_ma(1), _ma(2), _ma(1)])
    assert kq == ya.KetQuaApi({}, (_ma(1), _ma(2)), "") and tp.dem() == 0
    assert t.dong_trang_thai_api(phien.tom_tat()["api"]) == ""


def test_khong_co_file_khoa_that_cung_khong_gui(monkeypatch, tmp_path, khoa_api_that):
    tp = gia.lap_transport(monkeypatch)
    kq = ya.lay_video(_phien()[0], str(tmp_path / "data"), [_ma(1)])
    assert kq == ya.KetQuaApi({}, (_ma(1),), "") and tp.dem() == 0


def test_khoa_sai_dang_khong_gui_yeu_cau_nao_va_noi_ro(monkeypatch, tmp_path, khoa_api_that):
    tp = gia.lap_transport(monkeypatch)
    _ghi_khoa(tmp_path / "secrets", gia.KHOA_GIA + "\n" + gia.KHOA_GIA + "\n")
    phien, _ = _phien()
    kq = ya.lay_video(phien, str(tmp_path / "data"), [_ma(1), _ma(2)])
    assert kq.thong_tin == {} and kq.thieu == (_ma(1), _ma(2)) and tp.dem() == 0
    assert kq.ly_do_lui.startswith(ya.LY_DO_SAI_KHOA) and "nhiều hơn một dòng" in kq.ly_do_lui
    assert kq.ly_do_tung_ma == dict.fromkeys((_ma(1), _ma(2)), kq.ly_do_lui)
    assert phien.tom_tat()["api"]["video_lui"] == 2 and not phien.api.tat


def test_cau_dao_yt_dlp_dang_mo_thi_api_cung_khong_gui(api_youtube_gia, tmp_path):
    phien, _ = _phien()
    phien.ghi_loi(RuntimeError("ERROR: [youtube] x: Sign in to confirm you're not a bot."))
    assert phien.mo
    kq = ya.lay_video(phien, str(tmp_path / "data"), [_ma(1)])
    assert kq.thieu == (_ma(1),) and kq.ly_do_lui == ya.LY_DO_CAU_DAO and api_youtube_gia.dem() == 0
    assert phien.tom_tat()["api"]["video_lui"] == 0


def test_bam_dung_truoc_khi_gui_thi_khong_gui(api_youtube_gia, tmp_path):
    ev = threading.Event()
    ev.set()
    kq = ya.lay_video(_phien()[0], str(tmp_path / "data"), [_ma(1)], cancel_event=ev)
    assert kq.thieu == (_ma(1),) and kq.ly_do_lui == ya.LY_DO_DA_HUY and api_youtube_gia.dem() == 0


def test_assertion_cua_fixture_chan_mang_noi_len(api_youtube_gia, tmp_path, monkeypatch):
    """Chỉ bắt đúng lỗi truyền tải: AssertionError của fixture chặn mạng (và lỗi lập trình) phải nổi lên."""
    def cam(*a, **k):
        raise AssertionError("không được gọi mạng")

    monkeypatch.setattr(urllib.request, "urlopen", cam)
    with pytest.raises(AssertionError):
        ya.lay_video(_phien()[0], str(tmp_path / "data"), [_ma(1)])
