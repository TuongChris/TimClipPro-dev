# -*- coding: utf-8 -*-
"""Audit D-5 (P2): ``GiamSatTai`` giữ mốc byte/giây audio CAO NHẤT suốt cả lượt ``download_audio`` và không đặt lại khi
yt-dlp đổi player client — ffmpeg KHOẺ của client thứ hai bị giết là «Mạng đứng» nếu không vượt mốc của client trước
trong 180 giây.

Hợp đồng của chính module (``giam_sat_tai`` docstring): «không thêm byte nào quá ``han_dung_s`` trong lúc ffmpeg còn
chạy → giết». Client B ghi thêm byte đều đặn (nhịp phát 1×) nên KHÔNG được coi là mạng đứng.

Dữ liệu tổng hợp, không mạng, không ffmpeg thật, không ngủ: đồng hồ do test truyền vào ``tick``.
"""

from __future__ import annotations

import os

import pytest
import yt_dlp

import giam_sat_tai as gst
import truy_cap_youtube as t
from engine import Engine, TaiAudioDungHinh

HAN = 180.0
A_BYTE_MOI_S = 600_000          # client A: 60 MB ...
A_AUDIO_MOI_S = 20.0            # ... và 2000 s audio sau 100 s (tải nhanh, rồi luồng bị cắt)
A_HET = 100                     # t = 100: luồng của A bị cắt, ffmpeg thoát mã khác 0
B_BAT_DAU = 130                 # yt-dlp trích xuất lại cho client B, ffmpeg của B chạy từ t = 130
B_BYTE_MOI_S = 16_000           # B: opus ~128 kbps theo nhịp phát 1× — vẫn ĐANG tiến triển
B_AUDIO_MOI_S = 1.0
KET_THUC = 1000


def _ghi_tien_do(duong: str, byte: int, audio_s: float) -> None:
    # ffmpeg mở file -progress bằng ghi đè (O_TRUNC): tiến trình mới bắt đầu lại từ 0.
    with open(duong, "w", encoding="utf-8") as f:
        f.write(f"total_size={int(byte)}\nout_time_us={int(audio_s * 1_000_000)}\n"
                f"speed=1.0x\nprogress=continue\n")


# ---------------------------------------------------------------- mức đơn vị: GiamSatTai.tick

def test_client_sau_dang_tien_trien_khong_bi_coi_la_mang_dung(tmp_path):
    file_td = str(tmp_path / "td.txt")
    trang = {"ffmpeg": False}
    da_giet: list = []
    gs = gst.GiamSatTai(str(tmp_path / "vid__p10800"), file_td, None, han_dung_s=HAN,
                        tim=lambda _p: [object()] if trang["ffmpeg"] else [],
                        ham_giet=lambda ds: da_giet.append(len(ds)) or len(ds))

    # Client A: ffmpeg tải nhanh 0..100 s → 60 MB / 2000 s audio, rồi luồng bị cắt (ffmpeg thoát).
    trang["ffmpeg"] = True
    for tg in range(0, A_HET + 1, 10):
        _ghi_tien_do(file_td, A_BYTE_MOI_S * tg, A_AUDIO_MOI_S * tg)
        gs.tick(float(tg))
    trang["ffmpeg"] = False
    for tg in range(A_HET + 10, B_BAT_DAU, 10):       # trích xuất lại cho client B: chưa có ffmpeg
        gs.tick(float(tg))

    # Client B: ffmpeg mới, file tiến độ bắt đầu lại từ 0, ghi thêm byte đều mỗi chu kỳ.
    trang["ffmpeg"] = True
    bi_giet_luc = None
    for tg in range(B_BAT_DAU, KET_THUC + 1, 10):
        _ghi_tien_do(file_td, B_BYTE_MOI_S * (tg - B_BAT_DAU), B_AUDIO_MOI_S * (tg - B_BAT_DAU))
        gs.tick(float(tg))
        if gs.dung_hinh and bi_giet_luc is None:
            bi_giet_luc = tg
    assert not gs.dung_hinh and da_giet == [], (
        f"ffmpeg của client B đang ghi thêm {B_BYTE_MOI_S} B/s mà bị giết là «mạng đứng» lúc t={bi_giet_luc} "
        f"(mốc giữ từ client A: byte_cuoi={gs.byte_cuoi}, audio_cuoi={gs.audio_cuoi})")


class _FFPid:
    """ffmpeg giả có PID (như ``psutil.Process``)."""

    def __init__(self, pid: int):
        self.pid = pid


def test_ffmpeg_moi_bat_dau_muon_khong_bi_giet_ngay(tmp_path):
    # Client A dừng tiến triển ở t=100; trích xuất cho các client sau mất > 180 s; ffmpeg của B (PID mới) xuất hiện
    # lúc t=300 khi file -progress chưa có khối nào. Đồng hồ «đứng yên» phải chạy lại từ lúc B xuất hiện.
    file_td = str(tmp_path / "td.txt")
    trang: dict = {"ff": []}
    da_giet: list = []
    gs = gst.GiamSatTai(str(tmp_path / "vid__p10800"), file_td, None, han_dung_s=HAN,
                        tim=lambda _p: list(trang["ff"]), ham_giet=lambda ds: da_giet.append(len(ds)) or len(ds))
    trang["ff"] = [_FFPid(11)]
    for tg in range(0, A_HET + 1, 10):
        _ghi_tien_do(file_td, A_BYTE_MOI_S * tg, A_AUDIO_MOI_S * tg)
        gs.tick(float(tg))
    trang["ff"] = []
    os.remove(file_td)
    for tg in range(A_HET + 10, 300, 10):
        gs.tick(float(tg))
    trang["ff"] = [_FFPid(22)]
    gs.tick(300.0)
    assert not gs.dung_hinh and da_giet == [], "ffmpeg vừa khởi động bị giết ngay vì đồng hồ của client trước"
    assert gs.byte_cuoi == 0 and gs.audio_cuoi == 0.0, "mốc là của ffmpeg đang chạy, không phải của client trước"
    gs.tick(300.0 + HAN)
    assert gs.dung_hinh and da_giet == [1], "B thật sự không ghi gì suốt han_dung_s: vẫn là mạng đứng"


def test_cung_ffmpeg_tam_khuat_mot_chu_ky_van_bi_giet_khi_dung(tmp_path):
    # Cùng một PID không thấy trong một chu kỳ (psutil lỗi thoáng qua) rồi hiện lại: KHÔNG phải ffmpeg mới — không
    # đặt lại đồng hồ, ffmpeg đứng thật vẫn bị giết đúng hạn.
    file_td = str(tmp_path / "td.txt")
    trang: dict = {"ff": [_FFPid(7)]}
    da_giet: list = []
    gs = gst.GiamSatTai(str(tmp_path / "vid__p10800"), file_td, None, han_dung_s=HAN,
                        tim=lambda _p: list(trang["ff"]), ham_giet=lambda ds: da_giet.append(len(ds)) or len(ds))
    _ghi_tien_do(file_td, 5_000_000, 300.0)
    gs.tick(0.0)
    trang["ff"] = []
    gs.tick(100.0)
    trang["ff"] = [_FFPid(7)]
    gs.tick(150.0)
    assert not gs.dung_hinh
    gs.tick(HAN)
    assert gs.dung_hinh and da_giet == [1]


# ---------------------------------------------------------------- mức Engine.download_audio (tải phần đầu, 2 client)

class _GiamSatTay(gst.GiamSatTai):
    """GiamSatTai thật, chỉ thay: không chạy luồng (test gọi ``tick`` bằng đồng hồ giả), ffmpeg giả theo ``TRANG``."""

    TRANG: dict = {}
    DA_TAO: list = []

    def __init__(self, *a, **k):
        k["tim"] = lambda _p: [object()] if _GiamSatTay.TRANG.get("ffmpeg") else []
        k["ham_giet"] = lambda ds: (_GiamSatTay.TRANG.__setitem__("bi_giet", True), len(ds))[1]
        super().__init__(*a, **k)
        _GiamSatTay.DA_TAO.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


class _YdlHaiClient:
    """yt-dlp giả: client ``android`` tải 60 MB rồi luồng bị cắt (ffmpeg thoát mã 1); client ``ios`` tải khoẻ ở 1×."""

    def __init__(self):
        self.client_da_chay: list = []

    def __call__(self, opts):
        ngoai = self

        class _Phien:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def download(self, urls):
                client = opts["extractor_args"]["youtube"]["player_client"][0]
                ngoai.client_da_chay.append(client)
                gs = _GiamSatTay.DA_TAO[-1]
                file_td = opts["external_downloader_args"]["ffmpeg_o"][1][len("file:"):]
                dich = opts["outtmpl"].replace("%(ext)s", "webm")
                trang = _GiamSatTay.TRANG
                if client == "android":
                    trang["ffmpeg"] = True
                    for tg in range(0, A_HET + 1, 10):
                        _ghi_tien_do(file_td, A_BYTE_MOI_S * tg, A_AUDIO_MOI_S * tg)
                        with open(dich + ".part", "wb") as f:
                            f.write(b"a" * 64)
                        gs.tick(float(tg))
                    trang["ffmpeg"] = False
                    raise yt_dlp.utils.DownloadError("ERROR: ffmpeg exited with code 1")
                for tg in range(A_HET + 10, B_BAT_DAU, 10):   # trích xuất lại cho client B
                    gs.tick(float(tg))
                trang["ffmpeg"] = True
                for tg in range(B_BAT_DAU, KET_THUC + 1, 10):
                    _ghi_tien_do(file_td, B_BYTE_MOI_S * (tg - B_BAT_DAU), B_AUDIO_MOI_S * (tg - B_BAT_DAU))
                    with open(dich + ".part", "wb") as f:
                        f.write(b"b" * 64)
                    gs.tick(float(tg))
                    if trang.get("bi_giet"):
                        trang["ffmpeg"] = False
                        raise yt_dlp.utils.DownloadError("ERROR: ffmpeg exited with code 1")
                trang["ffmpeg"] = False
                os.replace(dich + ".part", dich)            # B tải xong phần cần

        return _Phien()


def test_download_audio_doi_client_khong_bao_mang_dung_nham(tmp_path, monkeypatch):
    _GiamSatTay.TRANG = {}
    _GiamSatTay.DA_TAO = []
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ra"))
    e.config.ytdlp_player_clients = ["android", "ios"]
    e.config.ytdlp_sleep_requests_s = 0.0
    e.config.ytdlp_cookies_browser = ""
    phien = t.PhienYouTube()
    monkeypatch.setattr(e, "phien_youtube_hien_tai", lambda: phien)
    ydl = _YdlHaiClient()
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    monkeypatch.setattr(gst, "ffmpeg_chia_khoi_duoc", lambda: True, raising=False)
    monkeypatch.setattr(gst, "GiamSatTai", _GiamSatTay)
    try:
        duong = e.download_audio("https://youtu.be/v1", "v1", gioi_han_giay=10800)
    except TaiAudioDungHinh as loi:
        pytest.fail(f"client B đang tải khoẻ bị giết là mạng đứng (client đã chạy: {ydl.client_da_chay}): {loi}")
    assert ydl.client_da_chay == ["android", "ios"]
    assert os.path.exists(duong)
