# -*- coding: utf-8 -*-
"""Đo ưu tiên ổ cứng khi dựng kho (06/11/2026, PC2). Chỉ ĐỌC file audio trên HDD, không ghi gì lên đó.

Bài đo: «việc khác» = luồng đọc ưu tiên thường trên cùng HDD; «dựng kho» = 8 FFmpeg giải mã clip chưa đọc lần nào trong
lượt đo, ở Below Normal + từng mức ưu tiên ổ cứng. Hai câu hỏi: việc khác có đỡ chậm không, và FFmpeg có lúc nào im
quá 10 giây không (`audio_read.read_data` coi đó là treo, clip phải thử lại).

Chạy: python -B do_uu_tien_o_cung.py <thư_mục_kết_quả> [số_giây_mỗi_ca]
      python -B do_uu_tien_o_cung.py that <thư_mục_mã> <thư_mục_kết_quả> <số_clip> <giây_tải>   (runner thật)
"""
import ctypes
import glob
import json
import mmap
import os
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
from ctypes import wintypes

import psutil

KHO = r"E:\Kho_Tool_Quet\Kho_Joe_Games"
FF = shutil.which("ffmpeg")
KHOI = 65536
SO_FFMPEG = 8
HANDLE_LOI = wintypes.HANDLE(-1).value
MUC = {"thuong": psutil.IOPRIO_NORMAL, "thap": psutil.IOPRIO_LOW, "rat_thap": psutil.IOPRIO_VERYLOW}


def mo_khong_dem(path: str):
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
    k32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                             wintypes.LPVOID]
    k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, wintypes.LPVOID, wintypes.DWORD]
    h = k32.CreateFileW(path, 0x80000000, 7, None, 3, 0x20000000, None)  # GENERIC_READ, FILE_FLAG_NO_BUFFERING
    if h == HANDLE_LOI:
        raise OSError(ctypes.get_last_error(), path)
    return k32, h


def tai_viec_khac(files: list, so_luong: int, dung: threading.Event, ngau_nhien: bool) -> dict:
    """Việc khác trên cùng HDD: đọc thẳng đĩa ở ưu tiên thường, ghi lại độ trễ từng lần đọc."""
    do_tre: list = []
    khoa = threading.Lock()

    def tho(so: int):
        rng = random.Random(so)
        bo_dem = mmap.mmap(-1, KHOI)
        dia_chi = ctypes.addressof(ctypes.c_char.from_buffer(bo_dem))
        doc = wintypes.DWORD()
        rieng = []
        k32, h = mo_khong_dem(files[so % len(files)])
        dai = os.path.getsize(files[so % len(files)]) // KHOI * KHOI
        vi_tri = 0
        while not dung.is_set():
            vi_tri = rng.randrange(0, dai // KHOI) * KHOI if ngau_nhien else (vi_tri + KHOI) % dai
            k32.SetFilePointerEx(h, vi_tri, None, 0)
            t = time.perf_counter()
            k32.ReadFile(h, dia_chi, KHOI, ctypes.byref(doc), None)
            rieng.append(time.perf_counter() - t)
        k32.CloseHandle(h)
        with khoa:
            do_tre.extend(rieng)

    luong = [threading.Thread(target=tho, args=(i,)) for i in range(so_luong)]
    for t in luong:
        t.start()
    dung.wait()
    for t in luong:
        t.join()
    if not do_tre:
        return {"lan_doc": 0}
    do_tre.sort()
    return {"lan_doc": len(do_tre), "tre_tb_ms": round(statistics.mean(do_tre) * 1000, 1),
            "tre_p95_ms": round(do_tre[int(len(do_tre) * 0.95)] * 1000, 1),
            "tre_max_ms": round(do_tre[-1] * 1000, 1)}


def dung_kho_gia(hang_cho: list, muc: str, giay: float) -> dict:
    """Tiến trình con để ưu tiên chỉ áp cho nhánh FFmpeg, không áp cho luồng đo việc khác."""
    ma = (
        "import json,os,subprocess,sys,threading,time,psutil\n"
        "p=psutil.Process();p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);p.ionice(int(sys.argv[1]))\n"
        "hang=json.load(sys.stdin);het=time.monotonic()+float(sys.argv[2]);kq=[];k=threading.Lock()\n"
        "def tho():\n"
        "  while time.monotonic()<het:\n"
        "    with k:\n"
        "      if not hang: return\n"
        "      f=hang.pop()\n"
        "    q=subprocess.Popen([sys.argv[3],'-v','error','-i',f,'-f','s16le','-ac','1','-ar','11025','-'],\n"
        "      stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)\n"
        "    t=time.monotonic();cuoi=t;gap=0.0;n=0\n"
        "    while True:\n"
        "      d=q.stdout.read(4096)\n"
        "      b=time.monotonic();gap=max(gap,b-cuoi);cuoi=b\n"
        "      if not d: break\n"
        "      n+=len(d)\n"
        "      if b>=het+30: q.kill();break\n"
        "    q.wait()\n"
        "    with k: kq.append({'gap':round(gap,2),'giay_am':n/22050,'giay':round(cuoi-t,2),'rc':q.returncode})\n"
        f"ls=[threading.Thread(target=tho) for _ in range({SO_FFMPEG})]\n"
        "[x.start() for x in ls];[x.join() for x in ls];print(json.dumps(kq))\n"
    )
    kq = subprocess.run([sys.executable, "-I", "-B", "-c", ma, str(int(MUC[muc])), str(giay), FF],
                        input=json.dumps(hang_cho), capture_output=True, text=True, check=True, timeout=giay + 600)
    ds = json.loads(kq.stdout)
    gap = [d["gap"] for d in ds] or [0.0]
    return {"clip_xong": len(ds), "gio_am_thanh": round(sum(d["giay_am"] for d in ds) / 3600, 2),
            "ffmpeg_loi": sum(1 for d in ds if d["rc"] not in (0, 1)), "gap_max_s": max(gap),
            "gap_tren_5s": sum(1 for g in gap if g > 5), "gap_tren_10s": sum(1 for g in gap if g > 10)}


def mot_ca(ten: str, tai_file: list, so_luong: int, ngau_nhien: bool, muc, hang_cho: list, giay: float) -> dict:
    dung = threading.Event()
    kq: dict = {"ca": ten, "muc": muc}
    bat_dau = time.monotonic()
    tai = {}
    t = threading.Thread(target=lambda: tai.update(tai_viec_khac(tai_file, so_luong, dung, ngau_nhien)))
    if so_luong:
        t.start()
    if muc:
        kq["dung_kho"] = dung_kho_gia(hang_cho, muc, giay)
    else:
        time.sleep(giay)
    dung.set()
    if so_luong:
        t.join()
    kq["giay"] = round(time.monotonic() - bat_dau, 1)
    kq["viec_khac"] = tai
    print(json.dumps(kq, ensure_ascii=False), flush=True)
    return kq


def dung_that(ma: str, ra: str, files: list, giay_tai: float) -> dict:
    """Runner thật 8 worker: HDD bị đọc dồn ``giay_tai`` giây đầu rồi rảnh. Báo clip đạt, lỗi và thời gian."""
    import tempfile
    tam = tempfile.mkdtemp(prefix="do_ut_", dir=ra)
    ds = os.path.join(tam, "list.txt")
    with open(ds, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(files))
    log = os.path.join(ra, f"that_tai{int(giay_tai)}.txt")
    dung, tai = threading.Event(), {}
    tai_file = sorted(glob.glob(os.path.join(glob.escape(KHO), "*.opus")), key=os.path.getsize, reverse=True)[:8]
    t = threading.Thread(target=lambda: tai.update(tai_viec_khac(tai_file, 8, dung, True)))
    if giay_tai:
        t.start()
        threading.Timer(giay_tai, dung.set).start()
    bat_dau = time.monotonic()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    with open(log, "w", encoding="utf-8") as ra_log:
        rc = subprocess.run([sys.executable, "-B", "-u", os.path.join(ma, "audfprint_progress_runner.py"),
                             os.path.join(ma, "audfprint-master", "audfprint.py"), "new", "--dbase",
                             os.path.join(tam, "db.pklz"), "--ncores", "8", "--continue-on-error", "--maxtimebits",
                             "16", "--shifts", "4", "--list", ds], stdout=ra_log, stderr=subprocess.STDOUT, env=env,
                            cwd=tam).returncode
    giay = round(time.monotonic() - bat_dau, 1)
    if giay_tai:
        dung.set()
        t.join()
    su_kien = [json.loads(d.split(" ", 1)[1]) for d in open(log, encoding="utf-8", errors="replace")
               if d.startswith("TIMCLIP_FINGERPRINT_EVENT ")]
    ket = [e for e in su_kien if e.get("event") == "clip_finished"]
    hash_ = sorted((os.path.basename(e["file"]), e.get("hash_count")) for e in ket if e.get("status") == "success")
    kq = {"rc": rc, "giay": giay, "clip": len(files), "dat": len(hash_), "viec_khac": tai,
          "cho_thu_lai": sum(1 for e in su_kien if e.get("event") == "clip_cho_thu_lai"),
          "hong": [e.get("message") for e in ket if e.get("status") != "success"], "hash": hash_}
    shutil.rmtree(tam, ignore_errors=True)
    return kq


def main():
    if sys.argv[1] == "that":   # that <mã> <thư_mục_kết_quả> <số_clip> <giây_tải>
        ma, ra, so_clip, giay_tai = sys.argv[2], sys.argv[3], int(sys.argv[4]), float(sys.argv[5])
        clips = sorted(glob.glob(os.path.join(glob.escape(KHO), "*.opus")), key=os.path.getsize, reverse=True)[8:]
        random.Random(61106).shuffle(clips)
        kq = dung_that(ma, ra, clips[-so_clip:], giay_tai)
        print(json.dumps({k: v for k, v in kq.items() if k != "hash"}, ensure_ascii=False), flush=True)
        with open(os.path.join(ra, f"that_tai{int(giay_tai)}.json"), "w", encoding="utf-8") as f:
            json.dump(kq, f, ensure_ascii=False, indent=1)
        return
    ra, giay = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    os.makedirs(ra, exist_ok=True)
    clips = sorted(glob.glob(os.path.join(glob.escape(KHO), "*.opus")), key=os.path.getsize, reverse=True)
    tai_file, con_lai = clips[:8], clips[8:]    # file lớn nhất làm «việc khác», không trùng clip giải mã
    random.Random(61106).shuffle(con_lai)
    moi_ca = 45
    ket_qua = []

    def lay():
        nonlocal con_lai
        phan, con_lai = con_lai[:moi_ca], con_lai[moi_ca:]
        return phan

    # Hai kiểu việc khác: 8 luồng nhảy lung tung (xấu nhất với HDD) và 2 luồng đọc tuần tự (như chép file lớn).
    for ten, so_luong, ngau_nhien in (("ngau_nhien_8", 8, True), ("tuan_tu_2", 2, False)):
        ket_qua.append(mot_ca(ten, tai_file, so_luong, ngau_nhien, None, [], giay))
        for muc in MUC:
            ket_qua.append(mot_ca(ten, tai_file, so_luong, ngau_nhien, muc, lay(), giay))
    # Không có việc khác: đo xem hạ ưu tiên có làm chậm khi máy rảnh không. Clip mới hẳn để bộ nhớ đệm không làm đẹp số.
    for muc in MUC:
        ket_qua.append(mot_ca("may_ranh", tai_file, 0, False, muc, lay(), giay))
    with open(os.path.join(ra, "ket_qua_uu_tien.json"), "w", encoding="utf-8") as f:
        json.dump(ket_qua, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
