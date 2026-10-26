# -*- coding: utf-8 -*-
"""Audit D-18 (P3): ``.part`` cũ của một lượt TẢI PHẦN ĐẦU bị cắt ngang (đóng cửa sổ Development / mất điện) nằm lại
trong ``data/downloads`` mãi mãi, và lượt tải sau của cùng video báo «ffmpeg đã ghi …» theo kích thước của nó.

Bản một phần đi qua ffmpeg (FFmpegFD, ``-y``) không bao giờ nối tiếp được — chính mã đã nói thế ở nhánh Dừng/mạng đứng.
Nhưng ``don_file_do_dang`` chỉ chạy khi đổi client / Dừng / mạng đứng, còn ``don_kho_dem`` bỏ qua ``.part``: file cũ
(vd. ``mp4.part`` có hình của client ``android``, nặng hơn hẳn bản audio) sống sót. ``GiamSatTai`` lấy mẫu trong khoảng
ffmpeg đã chạy mà file ``-progress`` chưa có byte nào → rơi về ``max(kích thước <ten>.*)`` = file cũ, và ``byte_cuoi``
chỉ tăng nên số sai đó ở lại suốt lượt tải (cả trong câu «Mạng đứng … file đã có N MB»).

Hành vi ĐÚNG: trước một lượt tải phần đầu, ``.part``/``.ytdl`` cũ của đúng video đó bị bỏ; số «ffmpeg đã ghi» là của
chính lượt này. Dữ liệu tổng hợp, không mạng, không ffmpeg thật, không ngủ.
"""

from __future__ import annotations

import os

import yt_dlp

import giam_sat_tai as gst
import truy_cap_youtube as t
from engine import Engine

CU = 5_000_000                  # mp4.part (có hình) sót lại sau lượt bị cắt ngang
MOI = (100_000, 200_000)        # byte ffmpeg của lượt này ghi ra webm.part, hai chu kỳ


class _GiamSatGhi(gst.GiamSatTai):
    """GiamSatTai thật, không luồng (yt-dlp giả gọi ``tick``); ffmpeg giả theo ``TRANG``; ghi lại mọi số liệu báo lên."""

    TRANG: dict = {}
    DA_TAO: list = []
    DA_BAO: list = []

    def __init__(self, *a, **k):
        goc = k.get("khi_so_lieu")

        def ghi(s: dict) -> None:
            _GiamSatGhi.DA_BAO.append(int(s["byte_dau_ra"]))
            if goc is not None:
                goc(s)

        k["khi_so_lieu"] = ghi
        k["tim"] = lambda _p: [object()] if _GiamSatGhi.TRANG.get("ffmpeg") else []
        k["ham_giet"] = lambda ds: len(ds)
        super().__init__(*a, **k)
        _GiamSatGhi.DA_TAO.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


def _ydl_gia(opts):
    class _Phien:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            gs = _GiamSatGhi.DA_TAO[-1]
            file_td = opts["external_downloader_args"]["ffmpeg_o"][1][len("file:"):]
            dich = opts["outtmpl"].replace("%(ext)s", "webm")
            _GiamSatGhi.TRANG["ffmpeg"] = True
            gs.tick(1.0)                         # ffmpeg đang dò luồng vào: chưa có file ra, chưa có -progress
            for i, byte in enumerate(MOI, start=2):
                with open(dich + ".part", "wb") as f:
                    f.write(b"\0" * byte)
                with open(file_td, "w", encoding="utf-8") as f:
                    f.write(f"total_size={byte}\nout_time_us={i * 10_000_000}\nspeed=1.0x\nprogress=continue\n")
                gs.tick(float(i))
            _GiamSatGhi.TRANG["ffmpeg"] = False
            os.replace(dich + ".part", dich)

    return _Phien()


def test_part_cu_bi_bo_va_khong_thanh_so_ffmpeg_da_ghi(tmp_path, monkeypatch):
    _GiamSatGhi.TRANG, _GiamSatGhi.DA_TAO, _GiamSatGhi.DA_BAO = {}, [], []
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ra"))
    e.config.ytdlp_player_clients = ["ios"]
    e.config.ytdlp_sleep_requests_s = 0.0
    e.config.ytdlp_cookies_browser = ""
    phien = t.PhienYouTube()
    monkeypatch.setattr(e, "phien_youtube_hien_tai", lambda: phien)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _ydl_gia)
    monkeypatch.setattr(gst, "ffmpeg_chia_khoi_duoc", lambda: True, raising=False)
    monkeypatch.setattr(gst, "GiamSatTai", _GiamSatGhi)
    ten = e._ten_phan_dau("v1", 10800)
    cu = os.path.join(e.dl_dir, ten + ".mp4.part")
    os.makedirs(e.dl_dir, exist_ok=True)
    with open(cu, "wb") as f:
        f.write(b"\0" * CU)

    duong = e.download_audio("https://youtu.be/v1", "v1", gioi_han_giay=10800)

    assert os.path.getsize(duong) == MOI[-1]
    assert _GiamSatGhi.DA_BAO and max(_GiamSatGhi.DA_BAO) <= MOI[-1], (
        f"«ffmpeg đã ghi» báo theo .part cũ của lượt bị cắt ngang: {_GiamSatGhi.DA_BAO}")
    assert not os.path.exists(cu), ".part của bản một phần không nối tiếp được: phải bỏ, không để nằm lại trên đĩa"
