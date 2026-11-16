# -*- coding: utf-8 -*-
"""Đồng bộ kênh ghi ngày đăng của YouTube Data API (D-51, docs/YOUTUBE_DATA_API.md).

Sau các lượt tải: MỘT ``videos.list`` cho mã vừa tải → chỉ thêm ``published_at`` vào mục ``clips_meta.json``. Tên file,
``upload_date`` / ``upload_date_raw`` (của yt-dlp) không đổi; không khoá / API lỗi → y như hôm nay. yt-dlp giả
(``tests/ytdlp_gia.py``), API giả (``tests/youtube_api_gia.py``), FFmpeg nén thay bằng chép file — không mạng.
"""

import json
import os
import shutil
import urllib.request

import pytest
import yt_dlp

import channel
import truy_cap_youtube as t
import youtube_api_gia as g
from channel import ChannelSync
from ytdlp_gia import BOT, YdlKichBan

DAI = 600.0
NGAY_API = "2026-07-31T20:00:34Z"   # ngày lịch UTC 20260731 — KHÁC ngày yt-dlp của info_mau (20260101)


def _ma(i: int) -> str:
    return f"api{i:08d}"


def _danh_sach(ids):
    return {"_type": "playlist", "id": "UCthu", "entries": [
        {"id": m, "title": f"Video {m}", "url": f"https://www.youtube.com/watch?v={m}", "duration": DAI} for m in ids]}


def _ten(m: str) -> str:
    return f"20260101 - Video {m} [{m}].opus"   # tên file theo ngày của yt-dlp, như hôm nay


def _dong_bo(kho, ydl, monkeypatch, data_dir=None, **kw):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    cs = ChannelSync(str(kho), data_dir=data_dir)

    def nen(nguon, tam, _tham_chieu, _huy):
        shutil.copyfile(nguon, tam)
        return ""
    cs._nen_va_kiem = nen
    return cs, cs.sync("https://www.youtube.com/@KenhThu", **kw)


def _video_api(tp, ids):
    for m in ids:
        tp.video[m] = g.video_gia(m, published_at=NGAY_API)


def test_dong_bo_ba_video_moi_mot_yeu_cau_api_ghi_published_at(tmp_path, monkeypatch, api_youtube_gia):
    ids = [_ma(i) for i in range(3)]
    _video_api(api_youtube_gia, ids)
    ydl = YdlKichBan(liet_ke=lambda _p, _u: _danh_sach(ids))
    luc_goi = []   # số lượt yt-dlp đã chạy khi yêu cầu API tới
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, **kw: (luc_goi.append(len(ydl.goi)), api_youtube_gia(req, **kw))[1])
    cs, r = _dong_bo(tmp_path / "kho", ydl, monkeypatch, data_dir=str(tmp_path / "data"))
    assert r["moi"] == 3 and r["trang_thai"] == channel.DONG_BO_DAY_DU and r["loi"] == []
    assert api_youtube_gia.dem() == 1 and api_youtube_gia.yeu_cau[0].ids == tuple(ids)
    assert luc_goi == [4], "MỘT yêu cầu API, SAU khi liệt kê + tải xong cả 3 video (ngoài đường tải từng video)"
    meta = cs.load_meta()
    assert sorted(meta) == sorted(_ten(m) for m in ids)
    assert sorted(f for f in os.listdir(tmp_path / "kho") if f.endswith(".opus")) == sorted(meta)
    for m in ids:
        muc = meta[_ten(m)]
        assert muc["published_at"] == NGAY_API
        assert (muc["upload_date"], muc["publication_date"], muc["upload_date_raw"]) == ("20260101",) * 3
    assert [x[0] for x in ydl.goi] == ["liet_ke", "tai", "tai", "tai"], "không thêm lượt yt-dlp nào"
    assert r["youtube"]["metadata_requests"] == 0
    assert (r["youtube"]["api"]["yeu_cau"], r["youtube"]["api"]["video_api"]) == (1, 3)


def test_het_han_muc_api_ket_qua_dong_bo_va_clips_meta_y_nhu_khong_co_api(tmp_path, monkeypatch, api_youtube_gia):
    ids = [_ma(i) for i in range(3)]
    _video_api(api_youtube_gia, ids)
    cs_goc, goc = _dong_bo(tmp_path / "kho_goc", YdlKichBan(liet_ke=lambda _p, _u: _danh_sach(ids)), monkeypatch)
    assert api_youtube_gia.dem() == 0, "đối chứng: lượt không gắn thư mục data = không dùng API (như hôm nay)"
    api_youtube_gia.kich_ban = [g.QUOTA]
    cs, r = _dong_bo(tmp_path / "kho", YdlKichBan(liet_ke=lambda _p, _u: _danh_sach(ids)), monkeypatch,
                     data_dir=str(tmp_path / "data"))
    assert api_youtube_gia.dem() == 1 and r["youtube"]["api"]["loai_tat"] == t.API_HET_HAN_MUC
    assert cs.load_meta() == cs_goc.load_meta()
    assert all("published_at" not in m for m in cs.load_meta().values())
    bo = ("thu_muc", "youtube", "hieu_suat")
    assert {k: v for k, v in r.items() if k not in bo} == {k: v for k, v in goc.items() if k not in bo}
    assert {k: r["youtube"][k] for k in t.TRUONG_SO_DO} == {k: goc["youtube"][k] for k in t.TRUONG_SO_DO}


def test_tai_lai_va_doi_soat_giu_published_at_khi_khong_co_khoa(tmp_path, monkeypatch):
    """Mục đã có ``published_at``: tải lại (thay CẢ mục) hay đối soát tại chỗ (gộp trường) đều không làm mất nó."""
    tp = g.lap_transport(monkeypatch)   # máy «chưa có khoá» (mặc định của conftest): đếm yêu cầu API
    a, b = _ma(0), _ma(1)
    kho = tmp_path / "kho"
    kho.mkdir()
    (kho / _ten(a)).write_bytes(b"")              # 0 byte: nghi hỏng → tải lại, thay cả mục
    (kho / _ten(b)).write_bytes(b"opus cu b")     # đọc được, chưa có dấu xác nhận → đối soát tại chỗ
    meta = {_ten(m): {"id": m, "title": f"Video {m}", "upload_date": "20260101", "duration": DAI,
                      "url": f"https://youtu.be/{m}", "published_at": f"2025-03-0{i + 1}T10:00:00Z"}
            for i, m in enumerate((a, b))}
    (kho / "clips_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (kho / "downloaded.txt").write_text(f"youtube {a}\nyoutube {b}\n", encoding="utf-8")
    ydl = YdlKichBan(liet_ke=lambda _p, _u: _danh_sach([a, b]))
    cs, r = _dong_bo(kho, ydl, monkeypatch, data_dir=str(tmp_path / "data"))
    assert (r["moi"], r["da_doi_soat"], ydl.dem("tai")) == (1, 1, 1)
    sau = cs.load_meta()
    assert sau[_ten(a)]["published_at"] == "2025-03-01T10:00:00Z" and sau[_ten(a)]["xac_nhan_tep"]
    assert sau[_ten(a)]["upload_date_raw"] == "20260101"
    assert sau[_ten(b)]["published_at"] == "2025-03-02T10:00:00Z" and sau[_ten(b)]["xac_nhan_tep"]
    assert tp.dem() == 0


def test_cli_kenh_gan_thu_muc_data_cua_engine(monkeypatch):
    """``cli.py kenh`` trao thư mục data của Engine (khoá Data API nằm cạnh nó); giao diện: test_dong_bo_song_song_quet."""
    from types import SimpleNamespace

    import cli

    gan = {}

    class _EngineGia:
        config = SimpleNamespace(ncores=1, ytdlp_player_clients=())
        data_dir = "D:/DataGia"

        def cau_hinh_mang(self):
            return None

    class _SyncGia:
        def __init__(self, kho, **kw):
            gan.update(kw)

        def sync(self, *a, **kw):
            return {"trang_thai": channel.DONG_BO_DAY_DU, "bo_qua": 0, "moi": 0, "loi": []}

    monkeypatch.setattr("sys.argv", ["cli.py", "kenh", "https://youtube.com/@Kenh", "--kho", "D:/KhoGia"])
    monkeypatch.setattr(cli, "Engine", _EngineGia)
    monkeypatch.setattr(cli, "ChannelSync", _SyncGia)
    cli.main()
    assert gan["data_dir"] == "D:/DataGia"


@pytest.mark.parametrize("kieu, so_yeu_cau, trang_thai", [
    ("dung", 1, channel.DONG_BO_DA_HUY),      # Dừng sau video đầu: video đã tải vẫn được ghi ngày (một yêu cầu)
    ("bot", 0, channel.DONG_BO_BI_CHAN),      # cầu dao yt-dlp mở: API cũng không gửi (lay_video tự chặn)
])
def test_dung_som_van_ghi_ngay_cho_video_da_tai_tru_khi_cau_dao_mo(tmp_path, monkeypatch, api_youtube_gia,
                                                                    kieu, so_yeu_cau, trang_thai):
    ids = [_ma(i) for i in range(3)]
    _video_api(api_youtube_gia, ids)
    bam = {"dung": False}
    tai = ({ids[0]: lambda _p, _m: bam.__setitem__("dung", True)} if kieu == "dung" else {ids[1]: BOT})
    ydl = YdlKichBan(tai=tai, liet_ke=lambda _p, _u: _danh_sach(ids))
    cs, r = _dong_bo(tmp_path / "kho", ydl, monkeypatch, data_dir=str(tmp_path / "data"),
                     cancel_check=lambda: bam["dung"])
    assert r["trang_thai"] == trang_thai and r["moi"] == 1 and ydl.dem("tai") == (1 if kieu == "dung" else 2)
    assert api_youtube_gia.dem() == so_yeu_cau
    assert [m.get("published_at") for m in cs.load_meta().values()] == [NGAY_API if so_yeu_cau else None]
