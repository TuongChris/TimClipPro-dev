# -*- coding: utf-8 -*-
"""Đo tải HDD của TimClipPro (06/11/2026, PC2). Chỉ ĐỌC file audio thật; dữ liệu giả ghi vào thư mục tạm rồi xoá.

Dừng ngay nếu thấy DEV (python TimClipPro_VanHanh/DevRuntime) đang chạy: không tranh tài nguyên với việc của người dùng.
Chạy: python -B do_o_cung.py <a|b|c|d|e ...>
"""
import csv
import ctypes
import glob
import json
import os
import random
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes

import psutil

RA = os.path.dirname(os.path.abspath(__file__))
KHO = r"E:\Kho_Tool_Quet\Kho_Joe_Games"
MA = r"C:\Dev\TimClipPro_VanHanh\TimClipPro"
FF = shutil.which("ffmpeg")
DIA = r"\PhysicalDisk(0 D: E:)"
BO_DEM = [DIA + r"\% Idle Time", DIA + r"\Current Disk Queue Length", DIA + r"\Disk Reads/sec",
          DIA + r"\Disk Read Bytes/sec", DIA + r"\Avg. Disk sec/Read", r"\Processor(_Total)\% Processor Time",
          r"\Process(MsMpEng)\IO Read Bytes/sec"]


def dev_dang_chay() -> bool:
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if "python" in (p.info["name"] or "").lower():
                c = " ".join(p.info["cmdline"] or [])
                if "TimClipPro_VanHanh" in c or "TimClipPro_DevRuntime" in c:
                    if "do_o_cung" not in c:
                        return True
        except psutil.Error:
            pass
    return False


def chan_neu_dev():
    if dev_dang_chay():
        print("DUNG: DEV dang chay, khong do de khoi anh huong viec cua nguoi dung", flush=True)
        sys.exit(3)


def doc_typeperf(path: str) -> dict:
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        hang = [r for r in csv.reader(f)]
    if len(hang) < 3:
        return {}
    cot: dict = {i: [] for i in range(1, len(hang[0]))}
    for r in hang[1:]:
        for i in cot:
            try:
                cot[i].append(float(r[i]))
            except (ValueError, IndexError):
                pass
    tb = lambda i: statistics.fmean(cot[i]) if cot[i] else 0.0     # noqa: E731
    return {"ban_pct": round(100 - tb(1), 1), "ban_toi_thieu_mau_idle0_pct": round(
                100 * sum(1 for x in cot[1] if x < 1) / max(1, len(cot[1])), 1),
            "hang_doi_tb": round(tb(2), 1), "hang_doi_max": max(cot[2] or [0]),
            "doc_moi_giay": round(tb(3)), "disk_MB_s": round(tb(4) / 1e6, 1),
            "ms_moi_doc": round(tb(5) * 1000, 1), "cpu_pct": round(tb(6), 1),
            "defender_doc_MB_s": round(tb(7) / 1e6, 1), "so_mau": len(cot[1])}


def giai_ma(f: str) -> None:
    # Đúng lệnh audio_read.FFmpegAudioFile; stdout bỏ đi vì đo phần ĐĨA.
    subprocess.run([FF, "-v", "error", "-i", f, "-f", "s16le", "-ac", "1", "-ar", "11025", "-"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def chay_a(ten: str, files: list, n: int, doc_truoc: bool) -> dict:
    chan_neu_dev()
    csv_ra = os.path.join(RA, f"a_{ten}.csv")
    tp = subprocess.Popen(["typeperf", *BO_DEM, "-si", "1", "-sc", "900", "-f", "CSV", "-o", csv_ra, "-y"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    khoa = threading.Lock()
    hang = list(files)
    khoa_hang = threading.Lock()
    giu = {"doc_s": 0.0}

    def tho():
        while True:
            with khoa_hang:
                if not hang:
                    return
                f = hang.pop()
            if doc_truoc:
                with khoa:          # đĩa đọc TUẦN TỰ từng file một, ffmpeg sau đó ăn từ cache Windows
                    t = time.monotonic()
                    with open(f, "rb", buffering=0) as fh:
                        while fh.read(1 << 20):
                            pass
                    giu["doc_s"] += time.monotonic() - t
            giai_ma(f)

    t0 = time.monotonic()
    ds = [threading.Thread(target=tho) for _ in range(n)]
    for t in ds:
        t.start()
    for t in ds:
        t.join()
    giay = time.monotonic() - t0
    tp.terminate()
    tp.wait(10)
    mb = sum(os.path.getsize(f) for f in files) / 1e6
    kq = {"ten": ten, "luong": n, "doc_truoc": doc_truoc, "so_file": len(files), "MB_audio": round(mb, 1),
          "giay": round(giay, 1), "MB_s_xu_ly": round(mb / giay, 2),
          "lan_thoi_gian_thuc": round(mb / 0.008 / giay), **doc_typeperf(csv_ra)}
    print(json.dumps(kq, ensure_ascii=False), flush=True)
    return kq


def phan_a() -> list:
    tat = sorted(os.path.join(KHO, f) for f in os.listdir(KHO) if f.endswith(".opus"))[430:]
    ung = [f for f in tat if 12e6 <= os.path.getsize(f) <= 45e6]
    random.Random(20261106).shuffle(ung)
    print("ung vien", len(ung), flush=True)
    kich_ban = [("n1", 1, False, 8), ("n2", 2, False, 8), ("n4", 4, False, 16), ("n8", 8, False, 24),
                ("n8_doc_truoc", 8, True, 24), ("n4_doc_truoc", 4, True, 16)]
    kq, vt = [], 0
    for ten, n, dt, so in kich_ban:
        ds = ung[vt:vt + so]
        vt += so
        kq.append(chay_a(ten, ds, n, dt))
        time.sleep(3)
    return kq


def phan_b() -> list:
    """RAM + CPU thật của MỘT worker cho clip 1 giờ và 3 giờ — đúng lệnh dựng kho (`--shifts 4 --maxtimebits 16`)."""
    tat = [os.path.join(KHO, f) for f in os.listdir(KHO) if f.endswith(".opus")]

    def gan(mb):
        return min(tat, key=lambda f: abs(os.path.getsize(f) / 1e6 - mb))

    kq = []
    for ten, mb in (("1_gio", 28.8), ("3_gio", 86.4)):
        chan_neu_dev()
        f = gan(mb)
        tam = tempfile.mkdtemp(prefix="do_b_", dir=RA)
        ds = os.path.join(tam, "list.txt")
        with open(ds, "w", encoding="utf-8") as fh:
            fh.write(f + "\n")
        lenh = [sys.executable, "-B", "-u", os.path.join(MA, "audfprint-master", "audfprint.py"), "new", "--dbase",
                os.path.join(tam, "db.pklz"), "--ncores", "1", "--continue-on-error", "--maxtimebits", "16",
                "--shifts", "4", "--list", ds]
        t0 = time.monotonic()
        p = subprocess.Popen(lenh, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ps = psutil.Process(p.pid)
        dinh_rss, dinh_priv, cpu = 0, 0, 0.0
        while p.poll() is None:
            try:
                nhom = [ps] + ps.children(recursive=True)
                r, q = 0, 0
                for c in nhom:
                    with_m = c.memory_info()
                    r += with_m.rss
                    q += getattr(with_m, "private", 0)
                dinh_rss, dinh_priv = max(dinh_rss, r), max(dinh_priv, q)
                cpu = ps.cpu_times().user + ps.cpu_times().system
            except psutil.Error:
                pass
            time.sleep(0.2)
        giay = time.monotonic() - t0
        kq.append({"ten": ten, "MB_file": round(os.path.getsize(f) / 1e6, 1), "giay": round(giay, 1),
                   "cpu_python_s": round(cpu, 1), "dinh_RSS_GB": round(dinh_rss / 2**30, 2),
                   "dinh_commit_GB": round(dinh_priv / 2**30, 2), "ma_thoat": p.returncode})
        print(json.dumps(kq[-1], ensure_ascii=False), flush=True)
        shutil.rmtree(tam, ignore_errors=True)
    return kq


def phan_c() -> dict:
    """Chi phí MỘT lần cập nhật clips_meta.json (đúng hàm thật) + fsync trên HDD vs SSD, dữ liệu GIẢ."""
    sys.path.insert(0, MA)
    import luu_tru

    meta = {f"20250101 - Video gia so {i} [{i:011d}].opus": {
        "id": f"{i:011d}", "title": "Tieu de gia " * 3, "upload_date": "20250101", "publication_date": "20250101",
        "publication_date_source": "x", "duration": 600, "duration_media": 600.1, "url": "https://youtu.be/x",
        "xac_nhan_tep": {"kich_thuoc": 123456, "do_dai": 600.1}} for i in range(2900)}
    kq: dict = {}
    for ten, goc in (("HDD_E", "E:\\"), ("SSD_C", RA)):
        chan_neu_dev()
        tam = tempfile.mkdtemp(prefix="_TimClipPro_DoDia_tam_", dir=goc)
        try:
            p = os.path.join(tam, "clips_meta.json")
            luu_tru.ghi_json_an_toan(p, meta)
            co = os.path.getsize(p)
            lan = []
            for i in range(15):
                t = time.perf_counter()
                luu_tru.cap_nhat_json(p, lambda d, i=i: d.__setitem__(f"moi{i}", {"id": str(i)}), mac_dinh={})
                lan.append(time.perf_counter() - t)
                time.sleep(0.3)
            fs = []
            for i in range(15):
                f = os.path.join(tam, f"f{i}.bin")
                with open(f, "wb") as fh:
                    fh.write(b"x" * 65536)
                    fh.flush()
                    t = time.perf_counter()
                    os.fsync(fh.fileno())
                    fs.append(time.perf_counter() - t)
                time.sleep(0.2)
            kq[ten] = {"KB_json": round(co / 1024), "cap_nhat_ms_tb": round(statistics.fmean(lan) * 1000),
                       "cap_nhat_ms_max": round(max(lan) * 1000), "fsync_ms_tb": round(statistics.fmean(fs) * 1000, 1),
                       "fsync_ms_max": round(max(fs) * 1000, 1)}
        finally:
            shutil.rmtree(tam, ignore_errors=True)
    t = time.perf_counter()
    d = r"E:\Kho_Tool_Quet\Kho_Flamingo"
    glob.glob(glob.escape(os.path.join(d, "clips_meta.json")) + "*.tmp")
    kq["glob_tmp_trong_kho_2900_file_ms"] = round((time.perf_counter() - t) * 1000, 1)
    t = time.perf_counter()
    n = sum(os.path.getsize(os.path.join(d, f)) > 0 for f in os.listdir(d))
    kq["thong_ke_listdir_getsize_ms"] = round((time.perf_counter() - t) * 1000, 1)
    kq["thong_ke_so_file"] = n
    print(json.dumps(kq, ensure_ascii=False), flush=True)
    return kq


def so_manh(path: str):
    """Số mảnh (extent) + LCN đầu của file — FSCTL_GET_RETRIEVAL_POINTERS, chỉ cần quyền đọc thuộc tính."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
    h = k32.CreateFileW(path, 0x80, 7, None, 3, 0x02000000, None)
    if h == wintypes.HANDLE(-1).value:
        return None
    try:
        vao = struct.pack("<q", 0)
        ra = ctypes.create_string_buffer(1 << 20)
        n = wintypes.DWORD()
        if not k32.DeviceIoControl(wintypes.HANDLE(h), 0x00090073, vao, 8, ra, len(ra), ctypes.byref(n), None):
            return None
        so = struct.unpack_from("<I", ra.raw, 0)[0]
        lcn0 = struct.unpack_from("<q", ra.raw, 24)[0] if so else -1
        return so, lcn0
    finally:
        k32.CloseHandle(wintypes.HANDLE(h))


def phan_d() -> dict:
    kq: dict = {}
    for ten in ("Kho_Joe_Games", "Kho_Cory", "Kho_SML"):
        d = rf"E:\Kho_Tool_Quet\{ten}"
        tat = sorted(f for f in os.listdir(d) if f.endswith(".opus"))
        mau = random.Random(1).sample(tat, min(300, len(tat)))
        dem, kt = [], []
        for f in mau:
            p = os.path.join(d, f)
            r = so_manh(p)
            if r:
                dem.append(r[0])
                kt.append(os.path.getsize(p) / 1e6)
        dem_s = sorted(dem)
        kq[ten] = {"mau": len(dem), "manh_trung_vi": dem_s[len(dem_s) // 2], "manh_p90": dem_s[int(len(dem_s) * .9)],
                   "manh_max": dem_s[-1], "MB_tb_moi_manh": round(sum(kt) / max(1, sum(dem)), 1)}
    print(json.dumps(kq, ensure_ascii=False), flush=True)
    return kq


def phan_e() -> list:
    """Chạy lại đường ĐỒNG BỘ ngoại tuyến (không YouTube): ghi nguồn .part → đổi tên → nén opus → ffprobe → đổi tên → xoá
    nguồn → cập nhật metadata, tất cả trên E: như thật. Nguồn nạp sẵn vào RAM để phần «tải» không đọc HDD."""
    sys.path.insert(0, MA)
    import luu_tru

    tat = sorted(os.path.join(KHO, f) for f in os.listdir(KHO) if f.endswith(".opus"))
    nguon = [f for f in tat if 8e6 <= os.path.getsize(f) <= 14e6][:6]
    bytes_ = [open(f, "rb").read() for f in nguon]
    meta = {f"f{i}": {"id": str(i), "title": "x" * 80, "xac_nhan_tep": {"kich_thuoc": 1}} for i in range(1800)}
    kq = []
    for ten, nghi_s, so in (("co_nhip_that_14s", 11.0, 10), ("lien_tuc_khong_nghi", 0.0, 12)):
        chan_neu_dev()
        tam = tempfile.mkdtemp(prefix="_TimClipPro_DoDia_tam_", dir="E:\\")
        csv_ra = os.path.join(RA, f"e_{ten}.csv")
        tp = subprocess.Popen(["typeperf", *BO_DEM, DIA + r"\Disk Writes/sec", DIA + r"\Disk Write Bytes/sec",
                               "-si", "1", "-sc", "900", "-f", "CSV", "-o", csv_ra, "-y"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        try:
            mj = os.path.join(tam, "clips_meta.json")
            luu_tru.ghi_json_an_toan(mj, meta)
            t0 = time.monotonic()
            for i in range(so):
                b = bytes_[i % len(bytes_)]
                src = os.path.join(tam, f"v{i}.webm")
                with open(src + ".part", "wb") as fh:
                    for k in range(0, len(b), 1 << 16):
                        fh.write(b[k:k + (1 << 16)])
                os.replace(src + ".part", src)
                ra = os.path.join(tam, f"v{i}.dang_nen.opus")
                subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar",
                                "16000", "-c:a", "libopus", "-b:a", "64k", ra],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                subprocess.run([FF.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0", ra],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                os.replace(ra, os.path.join(tam, f"v{i}.opus"))
                os.remove(src)
                luu_tru.cap_nhat_json(mj, lambda d, i=i: d.__setitem__(f"m{i}", {"id": str(i)}), mac_dinh={})
                if nghi_s:
                    time.sleep(nghi_s)
            giay = time.monotonic() - t0
        finally:
            tp.terminate()
            tp.wait(10)
            shutil.rmtree(tam, ignore_errors=True)
        d = doc_typeperf(csv_ra)
        with open(csv_ra, encoding="utf-8", errors="replace", newline="") as f:
            h = list(csv.reader(f))
        gh = [float(r[9]) for r in h[1:] if len(r) > 9 and r[9].strip()]
        kq.append({"ten": ten, "so_video": so, "giay": round(giay, 1), "giay_moi_video": round(giay / so, 1),
                   "ghi_MB_s_tb": round(statistics.fmean(gh) / 1e6, 2) if gh else 0, **d})
        print(json.dumps(kq[-1], ensure_ascii=False), flush=True)
    return kq


if __name__ == "__main__":
    chan_neu_dev()
    phan = sys.argv[1:] or ["d", "c", "a", "b"]
    kq = {}
    for x in phan:
        print("=== phan", x, time.strftime("%H:%M:%S"), flush=True)
        kq[x] = {"a": phan_a, "b": phan_b, "c": phan_c, "d": phan_d, "e": phan_e}[x]()
    with open(os.path.join(RA, "ket_qua_" + "".join(phan) + ".json"), "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)
    print("XONG", time.strftime("%H:%M:%S"), flush=True)
