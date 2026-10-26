# -*- coding: utf-8 -*-
"""Audit D-23: ffmpeg mà yt-dlp sinh ra khi tải PHẦN ĐẦU (FFmpegFD) nằm ngoài Job Object của tool — app chết đột
ngột thì nó sống tiếp (mồ côi), giữ ``downloads/<id>__p<giây>.*.part``.

Hợp đồng của chính dự án (``process_runner`` docstring, HARDENING_FIX_MATRIX TCP-14): mỗi lệnh dài chạy trong một
``NhomTienTrinh`` (Job Object ``KILL_ON_JOB_CLOSE``) — «nếu chính tool chết, Windows đóng handle và tự dọn cây».

Kịch bản synthetic (không mạng, không ffmpeg thật): một tiến trình con chạy ``Engine.download_audio(...,
gioi_han_giay=10800)`` với yt-dlp giả; ``download`` của yt-dlp giả làm đúng việc FFmpegFD làm — ``subprocess.Popen``
một tiến trình tải dài (ở đây: python ngủ, ghi ``.part``) rồi chờ nó. Tiến trình con (= app) bị giết đột ngột
(TerminateProcess, như «End task» / app sập) giữa lúc tải.

Hành vi ĐÚNG được khẳng định: tiến trình tải do lượt tải của app sinh ra chết theo app, không còn mồ côi.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time

import psutil
import pytest

import engine as engine_mod

THU_MUC_MA = os.path.dirname(os.path.abspath(engine_mod.__file__))

CON = textwrap.dedent(r'''
    import os, subprocess, sys, time
    sys.path.insert(0, sys.argv[1])
    goc = sys.argv[2]
    import yt_dlp
    import giam_sat_tai as gst
    from engine import Engine

    NGU = "import sys, time\nf = open(sys.argv[1], 'ab')\nwhile True:\n    f.write(b'x'); f.flush(); time.sleep(0.2)\n"

    class _Ydl:
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def download(self, urls):
            dich = self.opts["outtmpl"].replace("%(ext)s", "webm") + ".part"
            p = subprocess.Popen([sys.executable, "-I", "-B", "-c", NGU, dich])   # như FFmpegFD._call_downloader
            with open(os.path.join(goc, "chau.pid"), "w") as f:
                f.write(str(p.pid))
            p.wait()

    yt_dlp.YoutubeDL = _Ydl
    gst.ffmpeg_chia_khoi_duoc = lambda: True
    e = Engine(root=goc, data_dir=os.path.join(goc, "data"), out_dir=os.path.join(goc, "ra"))
    e.config.ytdlp_player_clients = ["android"]
    e.config.ytdlp_sleep_requests_s = 0.0
    e.config.ytdlp_cookies_browser = ""
    e.download_audio("https://youtu.be/aaaaaaaaaaa", "aaaaaaaaaaa", gioi_han_giay=10800)
''')


@pytest.mark.skipif(os.name != "nt", reason="Job Object là của Windows")
def test_tien_trinh_tai_chet_theo_app_khi_app_chet_dot_ngot(tmp_path):
    kich_ban = tmp_path / "app_gia.py"
    kich_ban.write_text(CON, encoding="utf-8")
    pid_file = tmp_path / "chau.pid"
    con = subprocess.Popen([sys.executable, "-B", str(kich_ban), THU_MUC_MA, str(tmp_path)], cwd=THU_MUC_MA,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    chau = None
    try:
        het = time.monotonic() + 60
        while not pid_file.exists() and time.monotonic() < het and con.poll() is None:
            time.sleep(0.1)
        if not pid_file.exists():
            con.kill()
            ra = con.communicate(timeout=10)[0].decode("utf-8", "replace")
            pytest.fail(f"app giả không tới bước tải: {ra[-2000:]}")
        time.sleep(0.3)
        chau = psutil.Process(int(pid_file.read_text()))
        part = [p for p in os.listdir(tmp_path / "data" / "downloads") if p.endswith(".part")]
        assert part, "tiến trình tải chưa ghi .part"

        con.kill()                    # app chết đột ngột giữa lúc tải
        con.wait(timeout=10)
        try:
            chau.wait(timeout=5)
        except psutil.TimeoutExpired:
            pass
        assert not chau.is_running(), (
            f"tiến trình tải (pid {chau.pid}) vẫn sống sau khi app chết — mồ côi, vẫn giữ {part[0]}")
    finally:
        if con.poll() is None:
            con.kill()
        if chau is not None and chau.is_running():
            chau.kill()              # chỉ tiến trình do chính test này sinh ra
