# -*- coding: utf-8 -*-
"""Tải PHẦN ĐẦU video dài phải xin từng khối Range ĐÓNG ≤ 10 MiB (ffmpeg ``-request_size``), như yt-dlp tải thường.

Bối cảnh (pilot PC2 13/10/2026, video 66 giờ): yt-dlp giao ``download_ranges`` cho ffmpeg (FFmpegFD); ffmpeg xin
MỘT yêu cầu ``Range: bytes=0-`` và YouTube nhả nó theo nhịp ~1–2× thời gian thực — 3 giờ đầu mất ~1,5 giờ. Đường
tải thường của yt-dlp xin từng khối 10 MiB (``http_chunk_size``) nên không bị hãm; FFmpegFD bỏ qua tuỳ chọn đó.
A/B thật cùng video, cùng định dạng 250, cùng client: một yêu cầu mở 0,7×; khối 10 MiB 1280× (40 phút âm thanh
trong 1,9 giây), âm thanh đủ 2400,01 s. Test thật với ffmpeg + máy chủ cục bộ: ``test_tai_mot_phan_that.py``.
"""

from __future__ import annotations

import pytest

import giam_sat_tai
from engine import Config, Engine


class _YdlGhi:
    """Giả ``yt_dlp.YoutubeDL``: ghi lại tuỳ chọn, «tải» ra đúng file theo ``outtmpl``."""

    def __init__(self):
        self.opts: list = []

    def __call__(self, opts):
        self.opts.append(opts)

        class _Phien:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def download(self, urls):
                with open(opts["outtmpl"].replace("%(ext)s", "webm"), "wb") as f:
                    f.write(b"audio gia")

        return _Phien()


def _xoa_bo_nho():
    ham = getattr(giam_sat_tai, "ffmpeg_chia_khoi_duoc", None)
    if hasattr(ham, "cache_clear"):
        ham.cache_clear()


@pytest.fixture(autouse=True)
def _xoa_bo_nho_kiem_ffmpeg():
    """``ffmpeg_chia_khoi_duoc`` nhớ kết quả cả tiến trình — test nào cũng bắt đầu và kết thúc sạch."""
    _xoa_bo_nho()
    yield
    _xoa_bo_nho()


@pytest.fixture
def eng(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ra"))
    e.config = Config(ytdlp_player_clients=[""], ytdlp_sleep_requests_s=0.0, ytdlp_sleep_min_s=0.0,
                      ytdlp_sleep_max_s=0.0)
    return e


def _tai(monkeypatch, eng, gioi_han, co_tuy_chon=True) -> dict:
    import yt_dlp

    ghi = _YdlGhi()
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ghi)
    monkeypatch.setattr(giam_sat_tai, "ffmpeg_chia_khoi_duoc", lambda: co_tuy_chon, raising=False)
    eng.download_audio("https://youtu.be/v1", "v1", gioi_han_giay=gioi_han)
    return ghi.opts[-1]


def test_tai_phan_dau_dat_request_size_10mib_o_phia_dau_vao(monkeypatch, eng):
    opts = _tai(monkeypatch, eng, 10800)
    eda = opts["external_downloader_args"]
    # `ffmpeg_i` = tuỳ chọn ĐẦU VÀO: FFmpegFD đặt ngay trước `-i <url>`. `-request_size` là tuỳ chọn của giao thức
    # http phía ĐỌC; để ở phía ra (`ffmpeg_o`) thì không yêu cầu tải nào bị chia.
    assert eda.get("ffmpeg_i") == ["-request_size", str(10 * 1024 * 1024)]
    assert "-request_size" not in eda["ffmpeg_o"]
    assert opts["download_ranges"], "giới hạn THỜI GIAN vẫn đặt ở đường tải"


def test_ffmpeg_cu_khong_co_tuy_chon_thi_giu_cach_cu_va_noi_ro(monkeypatch, eng):
    import tien_do_quet as tdq

    so = tdq.SoTienDo()
    so.bat_dau_video(1, 1, "u")
    eng._so_tien_do = so
    opts = _tai(monkeypatch, eng, 10800, co_tuy_chon=False)
    # ffmpeg cũ không biết `-request_size`: thêm vào là ffmpeg thoát ngay vì tuỳ chọn lạ — thà chậm còn hơn hỏng.
    assert "ffmpeg_i" not in opts["external_downloader_args"]
    assert any("không chia nhỏ được yêu cầu tải" in s.noi_dung for s in so.su_kien(50)), \
        "phải nói rõ trên màn hình vì sao lượt tải phần đầu sẽ chậm"


def test_tai_tron_khong_qua_ffmpeg_nen_khong_them_gi(monkeypatch, eng):
    opts = _tai(monkeypatch, eng, None)
    # Đường tải thường của yt-dlp đã tự xin khối 10 MiB (`http_chunk_size` của YouTube) — không đụng tới.
    assert "external_downloader_args" not in opts and "download_ranges" not in opts


def test_kiem_ffmpeg_doc_tro_giup_giao_thuc_http_mot_lan(monkeypatch):
    from process_runner import KetQuaLenh

    lenh: list = []

    def gia(ds, **k):
        lenh.append(ds)
        return KetQuaLenh(0, "  -request_size      <int64>      .D......... size (in bytes) of requests to make", "")

    monkeypatch.setattr(giam_sat_tai, "chay_lenh_media", gia, raising=False)
    assert giam_sat_tai.ffmpeg_chia_khoi_duoc() is True
    assert giam_sat_tai.ffmpeg_chia_khoi_duoc() is True
    assert lenh == [["ffmpeg", "-hide_banner", "-h", "protocol=http"]], "hỏi ffmpeg MỘT lần mỗi tiến trình"


@pytest.mark.parametrize("tinh_huong", ["ffmpeg_cu", "khong_chay_duoc", "het_gio"])
def test_ffmpeg_cu_khong_chay_duoc_hoac_het_gio_thi_khong_chia(monkeypatch, tinh_huong):
    from process_runner import KetQuaLenh

    def gia(ds, **k):
        if tinh_huong == "khong_chay_duoc":
            raise FileNotFoundError("không có ffmpeg trên PATH")
        if tinh_huong == "het_gio":
            return KetQuaLenh(-1, "  -seekable <boolean>", "", timed_out=True)
        return KetQuaLenh(0, "  -seekable          <boolean>    .D......... control seekability", "")

    monkeypatch.setattr(giam_sat_tai, "chay_lenh_media", gia, raising=False)
    assert giam_sat_tai.ffmpeg_chia_khoi_duoc() is False
