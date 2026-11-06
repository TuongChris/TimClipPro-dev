# -*- coding: utf-8 -*-
"""Bài đo I (06/11/2026): HDD phản ứng ra sao khi RAM gần cạn — giả thuyết «bộ đệm đĩa mất tác dụng».

Một tiến trình phụ chiếm RAM tới khi Available còn ~X GB rồi giữ trong thời gian ngắn; trong lúc đó chạy lại đúng bài giải
mã song song của phần A (đọc file thật, không ghi gì vào kho). Tự trả RAM khi xong. Dừng nếu DEV đang chạy.
Chạy: python -B do_ram.py
"""
import json
import os
import random
import subprocess
import sys
import time

import psutil

from do_o_cung import KHO, RA, chan_neu_dev, chay_a


def giu_ram(muc_gb: float, giay: float) -> None:
    khoi, kt = [], 256 << 20
    het = time.monotonic() + giay
    while time.monotonic() < het:
        con = psutil.virtual_memory().available / 2**30
        if con > muc_gb + 0.3:
            khoi.append(bytearray(kt))
        elif con < muc_gb - 0.2 and khoi:
            khoi.pop()
        for b in khoi:                       # giữ trang «nóng» để Windows không đẩy ra pagefile thay vì lấy bộ đệm
            b[::4096] = b"\x01" * len(range(0, kt, 4096))
        time.sleep(0.05)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--giu":
        giu_ram(float(sys.argv[2]), float(sys.argv[3]))
        sys.exit(0)
    chan_neu_dev()
    tat = sorted(os.path.join(KHO, f) for f in os.listdir(KHO) if f.endswith(".opus"))[430:]
    ung = [f for f in tat if 12e6 <= os.path.getsize(f) <= 45e6]
    random.Random(20261106).shuffle(ung)
    kq, vt = [], 96
    for ten, muc, n, so in (("i_n8_ram1GB", 1.0, 8, 24), ("i_n8_ram03GB", 0.3, 8, 24), ("i_n2_ram03GB", 0.3, 2, 8)):
        chan_neu_dev()
        ds = ung[vt:vt + so]
        vt += so
        p = subprocess.Popen([sys.executable, "-B", __file__, "--giu", str(muc), "75"])
        t0 = time.monotonic()
        while time.monotonic() - t0 < 25 and psutil.virtual_memory().available / 2**30 > muc + 0.5:
            time.sleep(0.5)
        print("RAM trong khi bat dau:", round(psutil.virtual_memory().available / 2**30, 2), "GB; cho", round(time.monotonic() - t0), "s", flush=True)
        kq.append(chay_a(ten, ds, n, False))
        p.terminate()
        p.wait(20)
        time.sleep(8)
    with open(os.path.join(RA, "ket_qua_i.json"), "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)
    print("XONG", time.strftime("%H:%M:%S"), flush=True)
