# -*- coding: utf-8 -*-
"""YouTube Data API theo lô cho các CÔNG CỤ metadata chạy loạt (D-51, docs/YOUTUBE_DATA_API.md «Phạm vi theo nhánh»).

Mỗi nơi gọi: gom mã -> ``youtube_api.lay_video`` (50 mã một yêu cầu) -> ghi ``thong_tin`` -> đường yt-dlp CŨ cho
``KetQuaApi.thieu``. Không mạng: API giả ở tầng ``urllib.request.urlopen`` (``tests/youtube_api_gia.py``), yt-dlp giả
đếm từng lượt (``tests/ytdlp_gia.py``). Không có khoá (mặc định của conftest) = số lượt yt-dlp y như cũ, 0 yêu cầu API.
``fetcher=`` / ``chi_tiet=`` tiêm vào = không bao giờ gọi API.
"""

import json
from pathlib import Path

import yt_dlp

import truy_cap_youtube as t
import youtube_api_gia as gia
from channel import ChannelSync
from ytdlp_gia import BOT, YdlKichBan

VN = "Asia/Ho_Chi_Minh"
NGAY_API = "2026-07-31T20:00:34Z"   # publishedAt mặc định của video_gia (20:00:34 UTC)
NGAY_VN = "20260801"                # ngày quy đổi giờ VN — resolver cũ với timestamp = publishedAt
NGAY_YTDLP = "20260101"             # upload_date của info_mau (đường yt-dlp giả)


def _ma(i: int) -> str:
    return f"vid{i:08d}"


def _co_tren_api(tp, ids, **kw) -> None:
    for m in ids:
        tp.video[m] = gia.video_gia(m, **kw)


def _ytdlp(monkeypatch, **kw) -> YdlKichBan:
    ydl = YdlKichBan(**kw)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    return ydl


def _hoi_ytdlp(ydl) -> list:
    return [g[1] for g in ydl.goi if g[0] == "info"]


def _phien_da_dung_api(so_video: int) -> t.PhienYouTube:
    p = t.PhienYouTube()
    p.api.ghi_yeu_cau()
    p.api.ghi_video(so_video)
    return p


def test_info_tu_api_ngay_quy_doi_theo_luc_bat_dau_phat_khong_co_upload_date():
    """Hợp đồng «Ngày đăng»: resolver cũ nhận release_timestamp = actualStartTime (nếu có), timestamp = publishedAt;
    không có upload_date (upload_date_raw chỉ dành cho ngày yt-dlp nguyên văn)."""
    from channel import info_tu_api, ngay_dang_tu_info
    from publication_date import epoch_tu_published_at

    video = {"id": "vid00000001", "title": "Phát trực tiếp", "duration": 3600,
             "published_at": "2026-07-30T10:00:00Z", "actual_start_time": "2026-08-01T18:30:00Z"}
    info = info_tu_api(video)

    assert info["timestamp"] == epoch_tu_published_at(video["published_at"])
    assert info["release_timestamp"] == epoch_tu_published_at(video["actual_start_time"])
    assert "upload_date" not in info and info["title"] == "Phát trực tiếp"
    assert ngay_dang_tu_info(info) == "20260802", "18:30 UTC ngày 01/08 = 01:30 ngày 02/08 giờ VN"
    assert ngay_dang_tu_info(info_tu_api({**video, "actual_start_time": ""})) == "20260730"


# =====================================================================
#  vameta — ChannelSync.va_metadata («🌐 Lấy lại tên video thật», cli.py vameta)
# =====================================================================

def _kho_vameta(tmp_path, ids) -> Path:
    kho = tmp_path / "kho"
    kho.mkdir()
    meta = {f"00000000 - Clip [{m}].opus": {"id": m, "title": f"Clip {m}", "upload_date": "", "duration": None}
            for m in ids}
    (kho / "clips_meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return kho


def _meta(kho) -> dict:
    return json.loads((kho / "clips_meta.json").read_text(encoding="utf-8"))


def _muc(meta, ma) -> dict:
    return meta[f"00000000 - Clip [{ma}].opus"]


def test_vameta_60_muc_hai_yeu_cau_api_khong_hoi_yt_dlp(api_youtube_gia, tmp_path, monkeypatch):
    ids = [_ma(i) for i in range(60)]
    _co_tren_api(api_youtube_gia, ids, duration="PT12M")
    kho = _kho_vameta(tmp_path, ids)
    meta = _meta(kho)
    _muc(meta, ids[0])["upload_date_raw"] = "20200101"     # ngày yt-dlp NGUYÊN VĂN đã có: không được đụng
    (kho / "clips_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    ydl = _ytdlp(monkeypatch)
    cs = ChannelSync(str(kho), data_dir=str(tmp_path / "data"))
    tien_do = []

    r = cs.va_metadata(lambda pct, msg: tien_do.append(pct), lay_title=True)

    assert api_youtube_gia.dem() == 2 and ydl.dem("info") == 0
    assert (r["da_va"], r["loi"]) == (60, [])
    meta = _meta(kho)
    m0 = _muc(meta, ids[0])
    assert (m0["published_at"], m0["upload_date"], m0["duration"], m0["title"]) == (
        NGAY_API, NGAY_VN, 720, f"Video {ids[0]}")
    assert m0["upload_date_raw"] == "20200101"
    assert all("upload_date_raw" not in _muc(meta, m) for m in ids[1:]), "API không phải ngày yt-dlp nguyên văn"
    assert tien_do and tien_do[-1] == 1.0
    so = cs.phien.tom_tat()["api"]
    assert (so["yeu_cau"], so["video_api"], so["video_lui"]) == (2, 60, 0)


def test_vameta_het_han_muc_giua_luot_phan_con_lai_qua_yt_dlp(api_youtube_gia, tmp_path, monkeypatch):
    ids = [_ma(i) for i in range(60)]
    _co_tren_api(api_youtube_gia, ids)
    api_youtube_gia.kich_ban = [None, gia.QUOTA]
    kho = _kho_vameta(tmp_path, ids)
    ydl = _ytdlp(monkeypatch)
    cs = ChannelSync(str(kho), data_dir=str(tmp_path / "data"))

    r = cs.va_metadata()

    assert api_youtube_gia.dem() == 2 and _hoi_ytdlp(ydl) == ids[50:]
    assert (r["da_va"], r["loi"]) == (60, [])
    meta = _meta(kho)
    assert all(_muc(meta, m)["published_at"] == NGAY_API for m in ids[:50])
    assert all("published_at" not in _muc(meta, m) and _muc(meta, m)["upload_date"] == NGAY_YTDLP for m in ids[50:])
    so = cs.phien.tom_tat()["api"]
    assert (so["video_api"], so["video_lui"], so["loai_tat"]) == (50, 10, t.API_HET_HAN_MUC)
    assert not cs.phien.mo, "hết hạn mức API không chạm cầu dao yt-dlp"


def test_vameta_yt_dlp_bi_chan_van_ghi_muc_api_da_tra_loi(api_youtube_gia, tmp_path, monkeypatch):
    ids = [_ma(i) for i in range(3)]
    _co_tren_api(api_youtube_gia, ids[1:])          # ids[0] vắng trong phản hồi API -> đi yt-dlp, bị nghi là bot
    kho = _kho_vameta(tmp_path, ids)
    ydl = _ytdlp(monkeypatch, info={ids[0]: BOT})
    cs = ChannelSync(str(kho), data_dir=str(tmp_path / "data"))

    r = cs.va_metadata()

    assert _hoi_ytdlp(ydl) == ids[:1] and cs.phien.mo
    assert r["da_va"] == 2 and len(r["loi"]) == 1
    meta = _meta(kho)
    assert [m for m in ids if "published_at" in _muc(meta, m)] == ids[1:], "cầu dao yt-dlp mở không làm mất bản API"


def test_vameta_khong_co_khoa_so_luot_yt_dlp_nhu_cu(tmp_path, monkeypatch):
    tp = gia.lap_transport(monkeypatch)
    ids = [_ma(i) for i in range(60)]
    kho = _kho_vameta(tmp_path, ids)
    ydl = _ytdlp(monkeypatch)

    r = ChannelSync(str(kho), data_dir=str(tmp_path / "data")).va_metadata()

    assert tp.dem() == 0 and _hoi_ytdlp(ydl) == ids and r["da_va"] == 60
    assert not any("published_at" in m for m in _meta(kho).values())


def test_vameta_fetcher_tiem_vao_khong_goi_api(api_youtube_gia, tmp_path):
    ids = [_ma(i) for i in range(3)]
    _co_tren_api(api_youtube_gia, ids)
    kho = _kho_vameta(tmp_path, ids)
    da_goi = []

    r = ChannelSync(str(kho), data_dir=str(tmp_path / "data")).va_metadata(
        fetcher=lambda vid: da_goi.append(vid) or {"upload_date": "20250115", "duration": 180})

    assert api_youtube_gia.dem() == 0 and da_goi == ids and r["da_va"] == 3


# =====================================================================
#  Xem trước kênh kèm ngày — ChannelSync.list_channel(lay_ngay_dang=True)
# =====================================================================

def _danh_sach(ids) -> dict:
    return {"_type": "playlist", "id": "UCkenh", "entries": [
        {"id": m, "title": f"Video {m}", "url": f"https://www.youtube.com/watch?v={m}", "duration": 600.0}
        for m in ids]}


def test_xem_truoc_kenh_kem_ngay_60_video_hai_yeu_cau_api(api_youtube_gia, tmp_path, monkeypatch):
    ids = [_ma(i) for i in range(60)]
    _co_tren_api(api_youtube_gia, ids, duration="PT12M")
    ydl = _ytdlp(monkeypatch, liet_ke=lambda _p, _u: _danh_sach(ids))
    p = t.PhienYouTube()

    ds = ChannelSync.list_channel("https://www.youtube.com/@kenh", lay_ngay_dang=True, phien_youtube=p,
                                  data_dir=str(tmp_path / "data"))

    assert api_youtube_gia.dem() == 2 and ydl.dem("info") == 0 and ydl.dem("liet_ke") == 1
    assert [v.id for v in ds] == ids
    assert all((v.upload_date, v.duration, v.upload_date_raw) == (NGAY_VN, 720.0, "") for v in ds)
    assert p.tom_tat()["api"]["video_api"] == 60


def test_xem_truoc_kenh_het_han_muc_giua_luot_phan_con_lai_qua_yt_dlp(api_youtube_gia, tmp_path, monkeypatch):
    ids = [_ma(i) for i in range(60)]
    _co_tren_api(api_youtube_gia, ids)
    api_youtube_gia.kich_ban = [None, gia.QUOTA]
    ydl = _ytdlp(monkeypatch, liet_ke=lambda _p, _u: _danh_sach(ids))

    ds = ChannelSync.list_channel("https://www.youtube.com/@kenh", lay_ngay_dang=True, data_dir=str(tmp_path / "data"))

    assert api_youtube_gia.dem() == 2 and _hoi_ytdlp(ydl) == ids[50:]
    assert [v.upload_date for v in ds] == [NGAY_VN] * 50 + [NGAY_YTDLP] * 10


def test_xem_truoc_kenh_khong_co_khoa_so_luot_yt_dlp_nhu_cu(tmp_path, monkeypatch):
    tp = gia.lap_transport(monkeypatch)
    ids = [_ma(i) for i in range(60)]
    ydl = _ytdlp(monkeypatch, liet_ke=lambda _p, _u: _danh_sach(ids))

    ds = ChannelSync.list_channel("https://www.youtube.com/@kenh", lay_ngay_dang=True, data_dir=str(tmp_path / "data"))

    assert tp.dem() == 0 and _hoi_ytdlp(ydl) == ids and all(v.upload_date == NGAY_YTDLP for v in ds)


def test_xem_truoc_kenh_chi_tiet_tiem_vao_khong_goi_api(api_youtube_gia, tmp_path, monkeypatch):
    ids = [_ma(i) for i in range(3)]
    _co_tren_api(api_youtube_gia, ids)
    _ytdlp(monkeypatch, liet_ke=lambda _p, _u: _danh_sach(ids))
    da_hoi = []

    ds = ChannelSync.list_channel("https://www.youtube.com/@kenh", lay_ngay_dang=True, data_dir=str(tmp_path / "data"),
                                  chi_tiet=lambda vid: da_hoi.append(vid) or {"id": vid, "upload_date": "20250102"})

    assert api_youtube_gia.dem() == 0 and da_hoi == ids and all(v.upload_date == "20250102" for v in ds)
