# -*- coding: utf-8 -*-
"""Bài đo F, G, H (06/11/2026): tải dựng vân tay thật, ghi file lớn, vân tay loại ổ. Dùng chung hàm của do_o_cung.py.

F chỉ đọc audio thật; G, H ghi vào thư mục tạm trên E: rồi xoá. Dừng ngay nếu DEV đang chạy.
Chạy: python -B do_mo_rong.py <f|g|h ...>
"""
import contextlib
import csv
import ctypes
import json
import mmap
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

import psutil

from do_o_cung import BO_DEM, DIA, FF, KHO, MA, RA, chan_neu_dev, doc_typeperf

BO_DEM_DU = BO_DEM + [DIA + r"\Disk Writes/sec", DIA + r"\Disk Write Bytes/sec", r"\Memory\Available MBytes"]


def bat_dem(ten: str):
    csv_ra = os.path.join(RA, f"{ten}.csv")
    tp = subprocess.Popen(["typeperf", *BO_DEM_DU, "-si", "1", "-sc", "1800", "-f", "CSV", "-o", csv_ra, "-y"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    return tp, csv_ra


def tat_dem(tp, csv_ra: str) -> dict:
    tp.terminate()
    tp.wait(10)
    kq = doc_typeperf(csv_ra)
    with open(csv_ra, encoding="utf-8", errors="replace", newline="") as f:
        h = list(csv.reader(f))

    def cot(i):
        ra = []
        for r in h[1:]:
            try:
                ra.append(float(r[i]))
            except (ValueError, IndexError):
                pass
        return ra
    gh, ram, idle, q = cot(9), cot(10), cot(1), cot(2)
    kq.update({"ghi_moi_giay": round(statistics.fmean(cot(8))) if cot(8) else 0,
               "ghi_MB_s_tb": round(statistics.fmean(gh) / 1e6, 1) if gh else 0,
               "ghi_MB_s_max": round(max(gh) / 1e6, 1) if gh else 0,
               "ram_trong_min_GB": round(min(ram) / 1024, 1) if ram else 0,
               "so_giay_ban_tren_90pct": sum(1 for x in idle if x < 10),
               "so_giay_hang_doi_ge5": sum(1 for x in q if x >= 5)})
    return kq


def phan_f() -> dict:
    """ĐÚNG tiến trình dựng vân tay (runner + 8 worker + --shifts 4), 120 giây trên các clip tiếp theo của kho, rồi giết.
    Audio chỉ đọc; bảng hash ở thư mục tạm cạnh script. Không đụng kho thật / dữ liệu DEV."""
    chan_neu_dev()
    tat = sorted(os.path.join(KHO, f) for f in os.listdir(KHO) if f.endswith(".opus"))[360:]
    tam = tempfile.mkdtemp(prefix="do_f_", dir=RA)
    ds = os.path.join(tam, "list.txt")
    with open(ds, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(tat))
    lenh = [sys.executable, "-B", "-u", os.path.join(MA, "audfprint_progress_runner.py"),
            os.path.join(MA, "audfprint-master", "audfprint.py"), "new", "--dbase", os.path.join(tam, "db.pklz"),
            "--ncores", "8", "--continue-on-error", "--maxtimebits", "16", "--shifts", "4", "--list", ds]
    tp, csv_ra = bat_dem("f_build_8_worker")
    log = open(os.path.join(tam, "out.txt"), "wb")
    p = subprocess.Popen(lenh, stdout=log, stderr=subprocess.STDOUT, cwd=MA,
                         env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    ps = psutil.Process(p.pid)
    t0 = time.monotonic()
    dinh = 0
    while time.monotonic() - t0 < 120 and p.poll() is None:
        with contextlib.suppress(psutil.Error):
            r = 0
            for c in [ps] + ps.children(recursive=True):
                r += getattr(c.memory_info(), "private", 0)
            dinh = max(dinh, r)
        time.sleep(1)
    with contextlib.suppress(psutil.Error):
        for c in ps.children(recursive=True):
            with contextlib.suppress(psutil.Error):
                c.kill()
        ps.kill()
    p.wait(20)
    log.close()
    kq = tat_dem(tp, csv_ra)
    with open(os.path.join(tam, "out.txt"), "rb") as fh:
        ra = fh.read()
    kq.update({"clip_xong": ra.count(b'"clip_finished"'), "dinh_commit_tool_GB": round(dinh / 2**30, 1),
               "giay": round(time.monotonic() - t0)})
    print(json.dumps({"ten": "f_build_8_worker", **kq}, ensure_ascii=False), flush=True)
    time.sleep(2)
    shutil.rmtree(tam, ignore_errors=True)
    return kq


def phan_g() -> list:
    """Ghi file LỚN như tải livestream dài: nhịp mạng 40 MB/s, rồi không giới hạn, rồi một vòng nén thật file nguồn lớn."""
    kq = []
    goi = os.urandom(1 << 20)
    tam = tempfile.mkdtemp(prefix="_TimClipPro_DoDia_tam_", dir="E:\\")
    try:
        chan_neu_dev()
        tp, csv_ra = bat_dem("g1_tai_40MBs")
        t0 = time.monotonic()
        with open(os.path.join(tam, "a.part"), "wb") as f:
            for i in range(800):
                f.write(goi)
                cho = t0 + (i + 1) / 40 - time.monotonic()
                if cho > 0:
                    time.sleep(cho)
        time.sleep(12)
        kq.append({"ten": "g1_tai_40MBs_800MB", **tat_dem(tp, csv_ra)})
        print(json.dumps(kq[-1], ensure_ascii=False), flush=True)
        os.remove(os.path.join(tam, "a.part"))

        chan_neu_dev()
        tp, csv_ra = bat_dem("g2_ghi_het_toc_luc")
        t0 = time.monotonic()
        with open(os.path.join(tam, "b.part"), "wb") as f:
            for _ in range(4000):
                f.write(goi)
        t1 = time.monotonic() - t0
        time.sleep(25)
        kq.append({"ten": "g2_ghi_4GB_het_toc_luc", "giay_ghi_vao_cache": round(t1, 1), **tat_dem(tp, csv_ra)})
        print(json.dumps(kq[-1], ensure_ascii=False), flush=True)
        os.remove(os.path.join(tam, "b.part"))

        chan_neu_dev()
        lon = max((os.path.join(KHO, f) for f in os.listdir(KHO) if f.endswith(".opus")
                   and os.path.getsize(os.path.join(KHO, f)) < 190e6), key=lambda x: os.path.getsize(x))
        with open(lon, "rb") as f:
            b = f.read()
        tp, csv_ra = bat_dem("g3_nen_nguon_lon")
        src = os.path.join(tam, "v.webm")
        t0 = time.monotonic()
        with open(src + ".part", "wb") as f:
            for k in range(0, len(b), 1 << 20):
                f.write(b[k:k + (1 << 20)])
                cho = t0 + (k + (1 << 20)) / 40e6 - time.monotonic()
                if cho > 0:
                    time.sleep(cho)
        os.replace(src + ".part", src)
        ra = os.path.join(tam, "v.dang_nen.opus")
        t1 = time.monotonic()
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                        "-c:a", "libopus", "-b:a", "64k", ra], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
        t2 = time.monotonic()
        os.remove(src)
        time.sleep(5)
        kq.append({"ten": "g3_nen_nguon_lon", "MB_nguon": round(len(b) / 1e6), "giay_nen": round(t2 - t1, 1),
                   "MB_ra": round(os.path.getsize(ra) / 1e6), **tat_dem(tp, csv_ra)})
        print(json.dumps(kq[-1], ensure_ascii=False), flush=True)
    finally:
        shutil.rmtree(tam, ignore_errors=True)
    return kq


def phan_h() -> dict:
    """Vân tay loại ổ: ghi ngẫu nhiên 64 KB không qua cache Windows, 60 giây. Ổ CMR 5400 vòng bị giới hạn cơ học ~100-200
    IOPS; ổ SMR nhận vào vùng đệm nên giữ hàng nghìn IOPS tới khi đầy vùng đệm."""
    chan_neu_dev()
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
    tam = tempfile.mkdtemp(prefix="_TimClipPro_DoDia_tam_", dir="E:\\")
    p = os.path.join(tam, "r.bin")
    try:
        goi = os.urandom(1 << 20)
        with open(p, "wb") as f:
            for _ in range(4096):
                f.write(goi)
            f.flush()
            os.fsync(f.fileno())
        time.sleep(5)
        h = k32.CreateFileW(p, 0x40000000, 1, None, 3, 0x20000000 | 0x80000000, None)
        if h == wintypes.HANDLE(-1).value:
            raise OSError(ctypes.get_last_error())
        buf = mmap.mmap(-1, 65536)
        buf.write(os.urandom(65536))
        dia_chi = ctypes.addressof(ctypes.c_char.from_buffer(buf))
        n = wintypes.DWORD()
        rng = random.Random(7)
        moi_10s, dem = [], 0
        tp, csv_ra = bat_dem("h_ghi_ngau_nhien")
        t0 = moc = time.monotonic()
        while time.monotonic() - t0 < 60:
            vt = rng.randrange(0, (4096 << 20) // 65536) * 65536
            k32.SetFilePointerEx(wintypes.HANDLE(h), ctypes.c_longlong(vt), None, 0)
            if not k32.WriteFile(wintypes.HANDLE(h), ctypes.c_void_p(dia_chi), 65536, ctypes.byref(n), None):
                raise OSError(ctypes.get_last_error())
            dem += 1
            if time.monotonic() - moc >= 10:
                moi_10s.append(round(dem / (time.monotonic() - moc)))
                dem, moc = 0, time.monotonic()
        k32.CloseHandle(wintypes.HANDLE(h))
        kq = {"IOPS_moi_10s": moi_10s, **tat_dem(tp, csv_ra)}
        print(json.dumps(kq, ensure_ascii=False), flush=True)
        return kq
    finally:
        shutil.rmtree(tam, ignore_errors=True)


if __name__ == "__main__":
    chan_neu_dev()
    phan = sys.argv[1:] or ["f", "g", "h"]
    kq = {}
    for x in phan:
        print("=== phan", x, time.strftime("%H:%M:%S"), flush=True)
        kq[x] = {"f": phan_f, "g": phan_g, "h": phan_h}[x]()
    with open(os.path.join(RA, "ket_qua_" + "".join(phan) + ".json"), "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)
    print("XONG", time.strftime("%H:%M:%S"), flush=True)
