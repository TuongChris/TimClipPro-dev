# -*- coding: utf-8 -*-
"""Tải MỘT PHẦN thật: yt-dlp + ffmpeg THẬT, máy chủ HTTP cục bộ (127.0.0.1) — không gọi YouTube.

Chứng minh ở tầng thật (không giả yt-dlp/ffmpeg), đúng đường ``Engine.download_audio`` dùng cho
giới hạn video dài (``download_ranges`` → ffmpeg ``-t``):

* giới hạn đặt ở ĐƯỜNG TẢI: tải 120 giây đầu của file 30 phút chỉ kéo phần byte tương ứng;
* tiến độ THẬT (byte, giây âm thanh) tới được sổ tiến độ trong lúc ffmpeg còn chạy;
* Dừng giữa lúc ffmpeg đang tải: dừng trong vài giây, không còn ffmpeg con, không còn file tạm;
* mạng đứng (máy chủ giữ kết nối, không gửi byte): báo lỗi rõ sau hạn, không chờ vô hạn;
* máy chủ cắt kết nối sớm: ffmpeg vẫn có thể giao file CỤT — lý do phải kiểm độ dài giải mã.

YouTube thật (DASH, giới hạn tốc độ, client) KHÔNG được kiểm ở đây — cần pilot có duyệt.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from engine import Cancelled, Config, Engine

# Chạy tiến trình thật (ffmpeg, yt-dlp) và đo thời gian → nhóm CHẬM (`pytest -m slow`, TEST_MATRIX).
pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                 reason="cần ffmpeg/ffprobe trên PATH")]

DAI_NGUON_S = 1800        # 30 phút
GIOI_HAN_S = 120


@pytest.fixture(scope="module")
def am_thanh(tmp_path_factory):
    p = tmp_path_factory.mktemp("nguon") / "am.webm"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=440:sample_rate=16000:duration={DAI_NGUON_S}", "-ac", "1",
                        "-c:a", "libopus", "-b:a", "24k", str(p)], capture_output=True, timeout=120)
    if r.returncode != 0 or not p.exists():
        pytest.skip("ffmpeg không mã hoá được opus/webm trên máy này")
    return p.read_bytes()


class MayChu:
    """Máy chủ HTTP cục bộ phát ``du_lieu``; đếm byte ĐÃ GỬI; giới hạn tốc độ/đứng/cắt theo ``che_do``."""

    def __init__(self, du_lieu: bytes):
        self.du_lieu = du_lieu
        self.che_do: dict = {}
        self.da_gui = 0
        self.dung = threading.Event()
        cha = self

        class XuLy(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _dau(self):
                self.send_response(200)
                self.send_header("Content-Type", "audio/webm")
                self.send_header("Content-Length", str(len(cha.du_lieu)))
                self.send_header("Accept-Ranges", "none")
                self.end_headers()

            def do_HEAD(self):
                self._dau()

            def do_GET(self):
                self._dau()
                toc_do = cha.che_do.get("toc_do")            # byte/giây
                dung_sau = cha.che_do.get("dung_sau")        # gửi N byte rồi giữ kết nối, im lặng
                dong_sau = cha.che_do.get("dong_sau")        # gửi N byte rồi đóng kết nối
                da, buoc = 0, 4096
                try:
                    while da < len(cha.du_lieu) and not cha.dung.is_set():
                        if dong_sau is not None and da >= dong_sau:
                            return
                        if dung_sau is not None and da >= dung_sau:
                            cha.dung.wait(60)
                            return
                        khoi = cha.du_lieu[da:da + buoc]
                        self.wfile.write(khoi)
                        da += len(khoi)
                        cha.da_gui += len(khoi)
                        if toc_do:
                            time.sleep(len(khoi) / toc_do)
                except (ConnectionError, OSError):
                    return

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), XuLy)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def url(self) -> str:
        return f"http://127.0.0.1:{self.srv.server_address[1]}/am.webm"

    def tat(self):
        self.dung.set()
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture
def may_chu(am_thanh):
    mc = MayChu(am_thanh)
    yield mc
    mc.tat()


@pytest.fixture
def eng(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    e.config = Config(ytdlp_player_clients=[""], ytdlp_sleep_requests_s=0.0, ytdlp_sleep_min_s=0.0,
                      ytdlp_sleep_max_s=0.0, ytdlp_format="ba/b")
    return e


def _ffmpeg_con(chua: str) -> list:
    import psutil
    ra = []
    for p in psutil.Process().children(recursive=True):
        try:
            if "ffmpeg" in p.name().lower() and any(chua in a for a in p.cmdline()):
                ra.append(p)
        except psutil.Error:
            continue
    return ra


def _don(ma: str) -> None:
    for p in _ffmpeg_con(ma):
        p.kill()


def test_gioi_han_o_duong_tai_chi_keo_phan_byte_tuong_ung(may_chu, eng, am_thanh):
    import tien_do_quet as tdq

    so = tdq.SoTienDo()
    so.bat_dau_video(1, 1, may_chu.url())
    eng._so_tien_do = so
    may_chu.che_do = {"toc_do": 96 * 1024}          # đủ chậm để thấy tiến độ giữa chừng
    f = eng.download_audio(may_chu.url(), "thu_mot_phan", gioi_han_giay=GIOI_HAN_S)
    dai = eng.duration_of(f)
    assert dai is not None and GIOI_HAN_S - 2 <= dai <= GIOI_HAN_S + 2, dai
    ty_le_byte = may_chu.da_gui / len(am_thanh)
    # 120/1800 = 6,7% byte cần; cho rộng tới 30% vì đệm TCP/ffmpeg — vẫn KHÔNG phải tải trọn.
    assert ty_le_byte < 0.30, f"đã kéo {ty_le_byte:.1%} file — không được tải trọn rồi mới cắt"
    a = so.anh()
    assert a.byte_dau_ra and a.byte_dau_ra > 0, "tiến độ THẬT (byte ffmpeg ghi) phải tới sổ khi đang tải"
    assert a.byte_da_nhan in (None, 0), "đường ffmpeg không đo được byte MẠNG — không được gán nhãn đó"
    assert a.audio_da_nhan_s and a.audio_da_nhan_s > 0
    nk = [s.noi_dung for s in so.su_kien(50)]
    assert any(x.startswith("Bắt đầu nhận audio — tối đa 00:02:00 đầu") for x in nk)
    assert not glob.glob(os.path.join(eng.data_dir, "tien_do_tai", "*")), "file -progress phải được dọn"


def test_dung_khi_ffmpeg_dang_tai_thi_dung_ngay_khong_de_tien_trinh_mo_coi(may_chu, eng):
    may_chu.che_do = {"toc_do": 8 * 1024}            # 120 s âm thanh ≈ 45 s tải: đủ để bấm Dừng giữa chừng
    ket: dict = {}

    def chay():
        try:
            ket["f"] = eng.download_audio(may_chu.url(), "thu_huy", gioi_han_giay=GIOI_HAN_S)
        except BaseException as e:  # noqa: BLE001
            ket["loi"] = e

    t = threading.Thread(target=chay, daemon=True)
    t.start()
    try:
        het = time.monotonic() + 20
        while not _ffmpeg_con("thu_huy") and time.monotonic() < het:
            time.sleep(0.1)
        assert _ffmpeg_con("thu_huy"), "ffmpeg phải đang tải lúc bấm Dừng"
        time.sleep(1.0)
        bam = time.monotonic()
        eng.cancel_event.set()
        t.join(15)
        assert not t.is_alive(), "bấm Dừng mà lượt tải vẫn chạy (cũ: chờ ffmpeg tải hết phần đã hẹn)"
        assert time.monotonic() - bam < 10
        assert isinstance(ket.get("loi"), Cancelled), ket
        assert not _ffmpeg_con("thu_huy"), "không được để ffmpeg mồ côi sau khi Dừng"
        assert not glob.glob(os.path.join(eng.dl_dir, "thu_huy__p*")), "file tạm phải được dọn"
    finally:
        eng.cancel_event.set()
        _don("thu_huy")
        t.join(30)


def test_mang_dung_bao_loi_ro_sau_han_khong_cho_vo_han(may_chu, eng, monkeypatch):
    import giam_sat_tai
    from engine import TaiAudioDungHinh

    monkeypatch.setattr(giam_sat_tai, "HAN_DUNG_TAI_S", 4.0)
    may_chu.che_do = {"dung_sau": 64 * 1024}         # gửi 64 KB rồi im lặng, giữ kết nối
    ket: dict = {}

    def chay():
        try:
            ket["f"] = eng.download_audio(may_chu.url(), "thu_dung", gioi_han_giay=GIOI_HAN_S)
        except BaseException as e:  # noqa: BLE001
            ket["loi"] = e

    t = threading.Thread(target=chay, daemon=True)
    t.start()
    try:
        t.join(40)
        assert not t.is_alive(), "mạng đứng mà lượt tải chờ vô hạn"
        assert isinstance(ket.get("loi"), TaiAudioDungHinh), ket
        assert "Mạng đứng" in str(ket["loi"])
        assert not _ffmpeg_con("thu_dung")
    finally:
        may_chu.dung.set()
        _don("thu_dung")
        t.join(30)


def test_may_chu_cat_som_thi_file_co_the_cut_ma_van_bao_xong(may_chu, eng):
    """Đúng hiện tượng G3-A (12/10): ffmpeg kết thúc «thành công» với file ngắn hơn phạm vi đã hẹn.
    Vì vậy giới hạn video dài phải đo độ dài GIẢI MÃ của file, không tin mã thoát."""
    may_chu.che_do = {"dong_sau": 100 * 1024}       # ~33 s âm thanh rồi đóng kết nối
    try:
        f = eng.download_audio(may_chu.url(), "thu_cut", gioi_han_giay=GIOI_HAN_S)
    except Exception:  # noqa: BLE001 — báo lỗi cũng là cách xử lý đúng
        return
    dai = eng.duration_of(f)
    assert dai is not None and dai < GIOI_HAN_S - 5, dai
    assert Engine._thieu_duoi(GIOI_HAN_S, dai), "kiểm độ dài phải bắt được file cụt này"
