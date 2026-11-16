# -*- coding: utf-8 -*-
"""YouTube Data API trên đường QUÉT (D-51, docs/YOUTUBE_DATA_API.md): ``Engine.youtube_info`` hỏi API trước, mã trong
``KetQuaApi.thieu`` đi đường yt-dlp cũ y nguyên; ngày V2 theo ``published_at``; dòng trạng thái ở thanh bên / CLI / Watch.

Engine, sổ kho, SQLite là thật; yt-dlp giả theo kịch bản (``tests/ytdlp_gia.py``), Data API giả ở tầng ``urlopen``
(``tests/youtube_api_gia.py``, khoá GIẢ). Không mạng.
"""

import dataclasses
import json
import sys

import pytest

import bao_cao_v2 as v2
import cli
import scan_ui
import truy_cap_youtube as t
import watch
import youtube_api
import youtube_api_gia as gia
from publication_date import epoch_tu_published_at, resolve_publication_date
from test_truy_cap_youtube_lo import _eng, _ma, _quet_gia, _url
from ytdlp_gia import YdlKichBan, info_mau

# Số đo thật trong publication_date.py: T_mKh8IUpWw đăng UTC 2025-06-20 18:45:39 — yt-dlp upload_date '20250620'.
PUBLISHED_AT = "2025-06-20T18:45:39Z"
NGAY_QUY_DOI = resolve_publication_date({"timestamp": 1750445139}).yyyymmdd


def test_youtube_info_qua_api_du_moi_khoa_cua_duong_ytdlp_them_published_at(tmp_path, monkeypatch, api_youtube_gia):
    ma = _ma(1)
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    api_youtube_gia.video[ma] = gia.video_gia(ma, title="Tiêu đề API", duration="PT1H2M3S",
                                              published_at=PUBLISHED_AT, ten_kenh="Kênh API")
    api_youtube_gia.kich_ban = [gia.QUOTA]          # lần 1: API hết hạn mức → đường yt-dlp cũ
    tu_ytdlp = e.youtube_info(_url(ma))
    tu_api = e.youtube_info(_url(ma))
    assert ydl.dem("info") == 1 and api_youtube_gia.dem() == 2
    assert set(tu_ytdlp) == set(tu_api) and tu_ytdlp["published_at"] == ""     # yt-dlp không có publishedAt
    assert tu_api == {
        "id": ma, "title": "Tiêu đề API", "title_raw": "Tiêu đề API", "duration": 3723,
        "uploader": "Kênh API", "channel": "Kênh API", "channel_id": gia.KENH_GIA,
        "channel_url": f"https://www.youtube.com/channel/{gia.KENH_GIA}",
        "upload_date": NGAY_QUY_DOI,                # ngày QUY ĐỔI cũ: resolver hiện có
        "upload_date_raw": "",                      # chỉ mang ngày yt-dlp nguyên văn — đường API không giả làm yt-dlp
        "publication_date_source": "timestamp", "publication_date_confidence": "high",
        "published_at": PUBLISHED_AT,
    }


def test_cung_video_api_va_ytdlp_cho_cung_ngay_v2_va_cung_ngay_quy_doi(tmp_path, monkeypatch, api_youtube_gia):
    ma = "T_mKh8IUpWw"
    ydl = YdlKichBan(info={"*": lambda _p, m: {**info_mau(m), "upload_date": "20250620", "timestamp": 1750445139}})
    e = _eng(tmp_path, monkeypatch, ydl)
    api_youtube_gia.video[ma] = gia.video_gia(ma, published_at=PUBLISHED_AT)
    api_youtube_gia.kich_ban = [gia.QUOTA]
    tu_ytdlp, tu_api = e.youtube_info(_url(ma)), e.youtube_info(_url(ma))
    assert (ydl.dem("info"), api_youtube_gia.dem()) == (1, 2)
    assert tu_ytdlp["upload_date"] == tu_api["upload_date"] == NGAY_QUY_DOI
    ngay_ytdlp, ngay_api = v2.ngay_tu_info(tu_ytdlp), v2.ngay_tu_info(tu_api)
    assert ngay_ytdlp.gia_tri == ngay_api.gia_tri == "20250620"
    assert (ngay_ytdlp.nguon, ngay_api.nguon) == (v2.NGUON_UPLOAD_DATE, "youtube_api.published_at")


def test_video_da_phat_truc_tiep_ngay_quy_doi_theo_actual_start_time(tmp_path, monkeypatch, api_youtube_gia):
    """``actualStartTime`` đóng vai ``release_timestamp`` của yt-dlp; ngày V2 vẫn là ngày lịch UTC của publishedAt."""
    ma = _ma(2)
    e = _eng(tmp_path, monkeypatch, YdlKichBan())
    api_youtube_gia.video[ma] = gia.video_gia(ma, published_at="2025-06-20T09:00:00Z",
                                              actual_start="2025-06-20T18:00:00Z")
    info = e.youtube_info(_url(ma))
    assert info["publication_date_source"] == "release_timestamp"
    assert info["upload_date"] == resolve_publication_date(
        {"release_timestamp": epoch_tu_published_at("2025-06-20T18:00:00Z")}).yyyymmdd
    assert v2.ngay_tu_info(info).gia_tri == "20250620"


def test_video_dang_phat_truc_tiep_live_lay_thong_tin_bang_ytdlp_nhu_cu(tmp_path, monkeypatch, api_youtube_gia):
    """Google gửi ``liveBroadcastContent: live`` cho video đang phát: đường yt-dlp cũ, ngày V2 không theo publishedAt."""
    ma = _ma(3)
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    api_youtube_gia.video[ma] = gia.video_gia(ma, live="live", duration="P0D", published_at=PUBLISHED_AT)
    info = e.youtube_info(_url(ma))
    assert (ydl.dem("info"), api_youtube_gia.dem()) == (1, 1)
    assert info["published_at"] == "" and v2.ngay_tu_info(info).nguon != "youtube_api.published_at"


def test_quet_lay_thong_tin_bang_api_khong_hoi_ytdlp_anh_chup_v2_theo_published_at(tmp_path, monkeypatch,
                                                                                    api_youtube_gia):
    ma = _ma(1)
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    monkeypatch.setattr(e, "scan_media", _quet_gia(e))
    api_youtube_gia.video[ma] = gia.video_gia(ma, title="Video API", published_at=PUBLISHED_AT)
    kq = e.scan_youtube(_url(ma))
    assert kq.status == "ok", kq.note
    assert (ydl.dem("info"), ydl.dem("tai"), api_youtube_gia.dem()) == (0, 1, 1), "yt-dlp chỉ còn tải"
    assert kq.upload_date == NGAY_QUY_DOI and kq.source_name == "Video API"
    bc = kq.bao_cao
    assert (bc.ngay_dang.gia_tri, bc.ngay_dang.nguon) == ("20250620", "youtube_api.published_at")
    # Không đổi trường / phiên bản ảnh chụp → Watch không quét lại, ảnh chụp cũ đọc như cũ, rollback an toàn.
    d = bc.to_dict()
    assert set(d) == {f.name for f in dataclasses.fields(v2.BaoCaoV2)} and d["phien_ban_anh_chup"] == 1
    assert v2.doc_anh_chup_da_luu(v2.CHINH_SACH_V2, json.dumps(d, ensure_ascii=False)) == bc
    assert e.bao_cao_cua_job(e.list_jobs()[0]["id"]) == bc
    # Không có khoá thì không có gì để báo trong ghi chú; có khoá cũng KHÔNG vào ghi chú từng kết quả.
    assert e.canh_bao_mang == [] and "API" not in (kq.note or "")
    assert t.dong_trang_thai_api(e.phien_youtube_cuoi.tom_tat()["api"]) == (
        "API YouTube: 1 video lấy bằng API (~1 đơn vị)")


@pytest.mark.parametrize("loi, ly_do", [(gia.QUOTA, "Hết hạn mức"),
                                        (gia.KEY_INVALID, "Khoá YouTube Data API không dùng được")])
def test_het_han_muc_hay_khoa_hong_trong_lo_3_video_mot_yeu_cau_api_roi_ytdlp_ca_lo(tmp_path, monkeypatch,
                                                                                  api_youtube_gia, loi, ly_do):
    ma = [_ma(i) for i in range(3)]
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    monkeypatch.setattr(e, "scan_media", _quet_gia(e))
    for m in ma:
        api_youtube_gia.video[m] = gia.video_gia(m)
    api_youtube_gia.kich_ban = [loi]
    ket = list(e.scan_iter([_url(m) for m in ma]))
    assert api_youtube_gia.dem() == 1, "API tắt tới hết lượt ngay lần lỗi đầu tiên"
    assert ydl.dem("info") == 3 and [k.status for k in ket] == ["ok"] * 3
    assert [k.bao_cao.ngay_dang.nguon for k in ket] == [v2.NGUON_UPLOAD_DATE] * 3
    phien = e.phien_youtube_cuoi
    so = phien.tom_tat()
    assert so["api"]["tat"] and so["api"]["video_lui"] == 3 and so["api"]["yeu_cau"] == 1
    # 403 quotaExceeded / 400 API_KEY_INVALID của API không chạm cầu dao / bộ đếm lỗi của yt-dlp.
    assert not phien.mo and so["metadata_requests"] == 3
    assert not any(so.get(k) for k in t.NHAN_TRUONG_THAT_BAI)
    # Không vào ghi chú từng kết quả; dòng trạng thái nói rõ lý do.
    assert e.canh_bao_mang == [] and not any("API" in (k.note or "") for k in ket)
    dong = scan_ui.dong_trang_thai_api_youtube(youtube_api.trang_thai_khoa(e.data_dir), phien)
    assert any(muc == "warning" and ly_do in cau and "3 video lùi về yt-dlp" in cau for muc, cau in dong)


def test_khong_co_khoa_lo_quet_y_nhu_cu_khong_mot_yeu_cau_api(tmp_path, monkeypatch):
    tp = gia.lap_transport(monkeypatch)             # chỉ để ĐẾM — máy «chưa có khoá» (mặc định của conftest)
    ma = [_ma(i) for i in range(3)]
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    monkeypatch.setattr(e, "scan_media", _quet_gia(e))
    ket = list(e.scan_iter([_url(m) for m in ma]))
    assert tp.dem() == 0 and ydl.dem("info") == 3 and [k.status for k in ket] == ["ok"] * 3
    assert [k.bao_cao.ngay_dang.nguon for k in ket] == [v2.NGUON_UPLOAD_DATE] * 3
    assert t.dong_trang_thai_api(e.phien_youtube_cuoi.tom_tat()["api"]) == ""


@pytest.mark.parametrize("url", ["https://www.twitch.tv/videos/2345678901", "https://www.youtube.com/@kenh/videos",
                                 "https://www.youtube.com/playlist?list=PLabcdefghijk"])
def test_link_khong_phai_video_youtube_khong_hoi_api(tmp_path, monkeypatch, api_youtube_gia, url):
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    e.youtube_info(url)
    assert api_youtube_gia.dem() == 0 and ydl.dem("info") == 1


def test_cli_youtube_in_dong_api_het_han_muc_khong_doi_ma_thoat(tmp_path, monkeypatch, capsys, api_youtube_gia):
    ma = [_ma(1), _ma(2)]
    e = _eng(tmp_path, monkeypatch, YdlKichBan())
    monkeypatch.setattr(e, "scan_media", _quet_gia(e))
    for m in ma:
        api_youtube_gia.video[m] = gia.video_gia(m)
    api_youtube_gia.kich_ban = [gia.QUOTA]
    monkeypatch.setattr(cli, "Engine", lambda: e)
    monkeypatch.setattr(sys, "argv", ["cli.py", "youtube", *[_url(m) for m in ma]])
    cli.main()                      # quét xong cả hai: hết hạn mức API KHÔNG phải YouTube chặn (mã 3), không phải lỗi
    ra = capsys.readouterr().out
    assert "===> API YouTube: 0 video lấy bằng API (~1 đơn vị) · 2 video lùi về yt-dlp — Hết hạn mức" in ra


def test_cli_kenh_in_dong_api_tu_so_do_cua_luot(tmp_path, monkeypatch, capsys):
    e = _eng(tmp_path, monkeypatch, YdlKichBan())
    monkeypatch.setattr(cli, "Engine", lambda: e)

    def dong_bo(self, url, limit=None, progress=None, **_kw):
        return {"trang_thai": "DAY_DU", "bo_qua": 0, "moi": 1, "loi": [],
                "youtube": {"api": {"video_api": 1, "don_vi": 1, "video_lui": 0}}}

    monkeypatch.setattr(cli.ChannelSync, "sync", dong_bo)
    monkeypatch.setattr(sys, "argv", ["cli.py", "kenh", "https://www.youtube.com/@kenh",
                                      "--kho", str(tmp_path / "kho_kenh")])
    cli.main()
    assert "API YouTube: 1 video lấy bằng API (~1 đơn vị)" in capsys.readouterr().out


def test_bao_cao_watch_co_dong_api_cua_luot(tmp_path, monkeypatch, api_youtube_gia):
    ma = _ma(1)
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    monkeypatch.setattr(e, "scan_media", _quet_gia(e))
    api_youtube_gia.video[ma] = gia.video_gia(ma)
    bc = watch.chay_giam_sat(e, watch.WatchList(muc=[watch.MucTheoDoi("link", _url(ma))], kho="A"))
    assert bc.quet_moi == 1 and ydl.dem("info") == 0 and api_youtube_gia.dem() == 1
    assert "API YouTube: 1 video lấy bằng API (~1 đơn vị)" in bc.tom_tat()
    assert "API YouTube" not in watch.BaoCao(youtube={"youtube_operations": 1}).tom_tat()
