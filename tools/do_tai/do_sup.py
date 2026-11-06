# -*- coding: utf-8 -*-
"""Bài đo J (06/11/2026): tái hiện lúc dựng vân tay chạm clip #291 (18,2 giờ) — ghi từng giây HDD, SSD, RAM, tiến trình.

Đúng lệnh dựng thật (runner + 8 worker + --shifts 4), audio chỉ đọc, bảng hash ở thư mục tạm cạnh script. Không đụng kho thật
hay dữ liệu DEV. Chốt an toàn: dừng ở 5 phút hoặc khi commit chạm 88% trần. Dừng ngay nếu DEV đang chạy.
"""
import contextlib
import csv
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

import psutil

from do_o_cung import KHO, MA, RA, chan_neu_dev

HDD = r"\PhysicalDisk(0 D: E:)"
SSD = r"\PhysicalDisk(1 C:)"
BO_DEM = [HDD + r"\% Idle Time", HDD + r"\Current Disk Queue Length", HDD + r"\Disk Reads/sec",
          HDD + r"\Disk Read Bytes/sec", HDD + r"\Disk Writes/sec", HDD + r"\Disk Write Bytes/sec",
          HDD + r"\Avg. Disk sec/Transfer", SSD + r"\% Idle Time", SSD + r"\Current Disk Queue Length",
          SSD + r"\Disk Bytes/sec", r"\Processor(_Total)\% Processor Time", r"\Memory\Available MBytes",
          r"\Memory\Pages Input/sec", r"\Memory\Pages Output/sec", r"\Paging File(_Total)\% Usage"]


class PERF(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("CommitTotal", ctypes.c_size_t), ("CommitLimit", ctypes.c_size_t),
                ("CommitPeak", ctypes.c_size_t), ("PhysicalTotal", ctypes.c_size_t),
                ("PhysicalAvailable", ctypes.c_size_t), ("SystemCache", ctypes.c_size_t),
                ("KernelTotal", ctypes.c_size_t), ("KernelPaged", ctypes.c_size_t),
                ("KernelNonpaged", ctypes.c_size_t), ("PageSize", ctypes.c_size_t),
                ("HandleCount", wintypes.DWORD), ("ProcessCount", wintypes.DWORD), ("ThreadCount", wintypes.DWORD)]


def commit() -> tuple:
    p = PERF()
    p.cb = ctypes.sizeof(PERF)
    ctypes.WinDLL("psapi").GetPerformanceInfo(ctypes.byref(p), p.cb)
    return p.CommitTotal * p.PageSize / 2**30, p.CommitLimit * p.PageSize / 2**30


def top_io(truoc: dict) -> tuple:
    """Top tiến trình theo byte đọc+ghi kể từ lần trước (mọi ổ — chỉ để biết ai đang gây tải)."""
    nay, ds = {}, []
    for p in psutil.process_iter(["name"]):
        with contextlib.suppress(psutil.Error, OSError):
            io = p.io_counters()
            tong = io.read_bytes + io.write_bytes
            nay[p.pid] = tong
            d = tong - truoc.get(p.pid, tong)
            if d > 1 << 20:
                ds.append((d, p.info["name"]))
    ds.sort(reverse=True)
    return nay, [f"{n}:{d >> 20}MB" for d, n in ds[:4]]


if __name__ == "__main__":
    chan_neu_dev()
    tat = sorted(os.path.join(KHO, f) for f in os.listdir(KHO) if f.endswith(".opus"))[284:]
    tam = tempfile.mkdtemp(prefix="do_f_", dir=RA)
    ds = os.path.join(tam, "list.txt")
    with open(ds, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(tat))
    csv_ra = os.path.join(RA, "j_tai_hien.csv")
    tp = subprocess.Popen(["typeperf", *BO_DEM, "-si", "1", "-sc", "900", "-f", "CSV", "-o", csv_ra, "-y"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    lenh = [sys.executable, "-B", "-u", os.path.join(MA, "audfprint_progress_runner.py"),
            os.path.join(MA, "audfprint-master", "audfprint.py"), "new", "--dbase", os.path.join(tam, "db.pklz"),
            "--ncores", "8", "--continue-on-error", "--maxtimebits", "16", "--shifts", "4", "--list", ds]
    log = open(os.path.join(tam, "out.txt"), "wb")
    p = subprocess.Popen(lenh, stdout=log, stderr=subprocess.STDOUT, cwd=MA,
                         env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    ps = psutil.Process(p.pid)
    t0 = time.monotonic()
    ly_do = "het 300 giay"
    io_truoc: dict = {}
    nhat_ky = open(os.path.join(RA, "j_tien_trinh.log"), "w", encoding="utf-8")
    dinh_cm = 0.0
    try:
        while time.monotonic() - t0 < 300:
            if p.poll() is not None:
                ly_do = f"tien trinh thoat {p.returncode}"
                break
            cm, han = commit()
            dinh_cm = max(dinh_cm, cm)
            if cm >= 0.88 * han:
                ly_do = f"cham chot commit {cm:.1f}/{han:.1f} GB"
                break
            io_truoc, top = top_io(io_truoc)
            lon = []
            with contextlib.suppress(psutil.Error):
                for c in ps.children(recursive=True):
                    with contextlib.suppress(psutil.Error):
                        m = c.memory_info()
                        if m.rss > 2 << 30:
                            lon.append(f"{c.pid}:{m.rss / 2**30:.1f}G")
            nhat_ky.write(f"{time.monotonic() - t0:5.0f}s commit {cm:5.1f}/{han:.0f} worker_lon {lon} top {top}\n")
            nhat_ky.flush()
            time.sleep(2)
    finally:
        with contextlib.suppress(psutil.Error):
            for c in ps.children(recursive=True):
                with contextlib.suppress(psutil.Error):
                    c.kill()
            ps.kill()
        p.wait(30)
        log.close()
        tp.terminate()
        tp.wait(10)
        nhat_ky.close()
    with open(os.path.join(tam, "out.txt"), "rb") as fh:
        ra = fh.read()
    print(json.dumps({"ly_do_dung": ly_do, "giay": round(time.monotonic() - t0), "clip_xong": ra.count(b'"clip_finished"'),
                      "dinh_commit_may_GB": round(dinh_cm, 1)}, ensure_ascii=False), flush=True)
    time.sleep(2)
    shutil.rmtree(tam, ignore_errors=True)
    print("XONG", flush=True)
