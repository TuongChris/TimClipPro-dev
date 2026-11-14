# -*- coding: utf-8 -*-
"""Phản biện HIỆU NĂNG của bước tinh chỉnh (14/11/2026) — sinh audio GIẢ LẬP dài, định dạng như tải thật.

Chỉ dùng bộ sinh của repo (tests/conftest._giai_dieu = nốt ngẫu nhiên; tests/am_thanh_lap.nhac_co_nhip = âm thanh LẶP).
Không audio thật. Ghi vào DU_LIEU:
  kho\\k01..k14.opus     clip 10 phút (k11–k14 nhạc có nhịp), opus 64k mono 16 kHz như kho đồng bộ kênh (channel.py)
  kho\\goc_2h.opus       clip 7140 s (≈ 2 giờ, dưới trần D-31 7200 s): 12 khối 600 s xen kẽ nốt / nhạc có nhịp
  kho_dai\\goc_2h.opus + .kho_video_dai   cùng clip trong kho video dài D-34 (mốc 21 bit)
  video_A.webm          3 giờ, 14 lần dùng clip 10 phút (trọn / một phần / cắt giữa) — webm/opus 96k stereo 48 kHz
  video_B.webm          3 giờ: goc_2h dùng TRỌN ở 1800 s + 5 phút trích clip[3000..3300] ở 9600 s
  su_that_A.json, su_that_B.json
Chạy: PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B tao_du_lieu.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import wave

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, r"C:\Dev\Tool_Quet\TimClipPro\tests")
from am_thanh_lap import nhac_co_nhip  # noqa: E402
from conftest import _giai_dieu  # noqa: E402

DU_LIEU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_hieu_nang\du_lieu"
SR = 22050
KHO_10P = {f"k{i:02d}": ("nhip" if i >= 11 else "not", 3100 + i) for i in range(1, 15)}
DAI_2H = 7140
KHOI = 600


def _chuan(x: np.ndarray) -> np.ndarray:
    return x * (0.7 / max(float(np.abs(x).max()), 1e-9))


def _sinh(loai: str, dai: float, seed: int) -> np.ndarray:
    return _chuan(nhac_co_nhip(dai, seed) if loai == "nhip" else _giai_dieu(dai, seed, sr=SR))


def clip_10p(ten: str) -> np.ndarray:
    loai, seed = KHO_10P[ten]
    return _sinh(loai, 600, seed)


def goc_2h_khoi(i: int) -> np.ndarray:
    dai = min(KHOI, DAI_2H - i * KHOI)
    return _sinh("nhip" if i % 2 else "not", dai, 3200 + i)


def doan_clip(ten: str, a: float, b: float):
    """Sinh từng khối PCM của clip[a..b) (mẫu chính xác)."""
    ia, ib = int(round(a * SR)), int(round(b * SR))
    if ten != "goc_2h":
        yield clip_10p(ten)[ia:ib]
        return
    for i in range(int(np.ceil(DAI_2H / KHOI))):
        k0 = i * KHOI * SR
        k1 = k0 + min(KHOI, DAI_2H - i * KHOI) * SR
        if k1 <= ia or k0 >= ib:
            continue
        yield goc_2h_khoi(i)[max(ia, k0) - k0: min(ib, k1) - k0]


def nen(dai: float, j: int):
    """Nền: từng khối ≤ 600 s; cứ 3 mục thì 1 mục nhạc có nhịp (cùng mẫu kick tất định → khớp tình cờ, bóng)."""
    con, s = dai, 0
    while con > 1e-9:
        d = min(KHOI, con)
        yield _sinh("nhip" if j % 3 == 2 else "not", d, 3300 + 40 * j + s)
        con -= d
        s += 1


def _ghi(w: wave.Wave_write, x: np.ndarray) -> int:
    w.writeframes((np.clip(x, -1, 1) * 32000).astype(np.int16).tobytes())
    return len(x)


def _ffmpeg(*ts: str) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *ts], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])


def _dai(p: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def ghi_kho() -> None:
    kho, kho_dai = os.path.join(DU_LIEU, "kho"), os.path.join(DU_LIEU, "kho_dai")
    os.makedirs(kho, exist_ok=True)
    os.makedirs(kho_dai, exist_ok=True)
    tam = os.path.join(DU_LIEU, "_tam.wav")
    for ten in [*KHO_10P, "goc_2h"]:
        with wave.open(tam, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            for x in doan_clip(ten, 0, 600 if ten != "goc_2h" else DAI_2H):
                _ghi(w, x)
        _ffmpeg("-i", tam, "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "64k",
                os.path.join(kho, f"{ten}.opus"))
    os.remove(tam)
    shutil.copy2(os.path.join(kho, "goc_2h.opus"), os.path.join(kho_dai, "goc_2h.opus"))
    open(os.path.join(kho_dai, ".kho_video_dai"), "w").close()


DONG_THOI_GIAN = {
    "A": [("nen", 150), ("clip", "k01", 0, 600), ("nen", 90), ("clip", "k02", 0, 600),
          ("nen", 200), ("clip", "k11", 0, 600), ("nen", 120), ("clip", "k03", 100, 280),
          ("nen", 75), ("clip", "k04", 0, 600), ("nen", 160), ("clip", "k05", 0, 600),
          ("nen", 110), ("clip", "k12", 0, 600), ("nen", 95), ("clip", "k06", 0, 600),
          ("nen", 140), ("clip", "k07", 0, 300), ("khac", 20), ("clip", "k07", 340, 600),
          ("nen", 130), ("clip", "k08", 0, 600), ("nen", 85), ("clip", "k13", 200, 500),
          ("nen", 170), ("clip", "k09", 0, 600), ("nen", 100), ("clip", "k10", 0, 600),
          ("nen", 125), ("clip", "k14", 0, 600), ("nen", None)],
    "B": [("nen", 1800), ("clip", "goc_2h", 0, DAI_2H), ("nen", 660), ("clip", "goc_2h", 3000, 3300), ("nen", None)],
}
DAI_VIDEO = 10800


def ghi_video(ten: str) -> dict:
    tam = os.path.join(DU_LIEU, "_tam.wav")
    t, doan = 0.0, []
    with wave.open(tam, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        for j, muc in enumerate(DONG_THOI_GIAN[ten]):
            if muc[0] == "clip":
                _, c, a, b = muc
                n = sum(_ghi(w, x) for x in doan_clip(c, a, b))
                doan.append({"clip": f"{c}.opus", "video_tu": t, "video_den": t + (b - a), "clip_tu": a, "clip_den": b,
                             "he_so": 1.0})
            elif muc[0] == "khac":
                n = _ghi(w, _sinh("not", muc[1], 3501))
            else:
                dai = muc[1] if muc[1] is not None else DAI_VIDEO - t
                n = sum(_ghi(w, x) for x in nen(dai, j))
            t += n / SR
    out = os.path.join(DU_LIEU, f"video_{ten}.webm")
    _ffmpeg("-i", tam, "-ac", "2", "-ar", "48000", "-c:a", "libopus", "-b:a", "96k", out)
    os.remove(tam)
    st = {"video": os.path.basename(out), "do_dai_video_s": _dai(out), "doan": doan,
          "ghi_chu": "video webm/opus 96k stereo 48 kHz; clip kho opus 64k mono 16 kHz; mốc theo giây đúng mẫu 22050 Hz"}
    with open(os.path.join(DU_LIEU, f"su_that_{ten}.json"), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    return st


def ghi_w40() -> None:
    """Ca CUỘN MỐC 16 bit: clip 2400 s chỉ nốt ngẫu nhiên (quét nhanh) trong kho THƯỜNG; video 3600 s dùng trọn clip ở
    600 s + trích clip[1800..2100] ở 3200 s. Mốc 16 bit cuộn sau 65536·256/11025 = 1521,8 s."""
    kho = os.path.join(DU_LIEU, "kho_w40")
    os.makedirs(kho, exist_ok=True)
    clip = np.concatenate([_sinh("not", 600, 3600 + i) for i in range(4)])
    tam = os.path.join(DU_LIEU, "_tam.wav")
    with wave.open(tam, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        _ghi(w, clip)
    _ffmpeg("-i", tam, "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "64k", os.path.join(kho, "w40.opus"))
    with wave.open(tam, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        _ghi(w, _sinh("not", 600, 3700))
        _ghi(w, clip)
        _ghi(w, _sinh("not", 200, 3701))
        _ghi(w, clip[1800 * SR: 2100 * SR])
        _ghi(w, _sinh("not", 100, 3702))
    out = os.path.join(DU_LIEU, "video_W.webm")
    _ffmpeg("-i", tam, "-ac", "2", "-ar", "48000", "-c:a", "libopus", "-b:a", "96k", out)
    os.remove(tam)
    st = {"video": "video_W.webm", "do_dai_video_s": _dai(out),
          "doan": [{"clip": "w40.opus", "video_tu": 600.0, "video_den": 3000.0, "clip_tu": 0, "clip_den": 2400,
                    "he_so": 1.0},
                   {"clip": "w40.opus", "video_tu": 3200.0, "video_den": 3500.0, "clip_tu": 1800, "clip_den": 2100,
                    "he_so": 1.0}]}
    with open(os.path.join(DU_LIEU, "su_that_W.json"), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    print("w40:", st["do_dai_video_s"], "s")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(DU_LIEU, exist_ok=True)
    if sys.argv[1:] == ["w40"]:
        ghi_w40()
        return
    t = time.perf_counter()
    ghi_kho()
    print(f"kho xong {time.perf_counter() - t:.1f} s", flush=True)
    for ten in ("A", "B"):
        t = time.perf_counter()
        st = ghi_video(ten)
        print(f"video {ten}: {st['do_dai_video_s']:.2f} s, {len(st['doan'])} đoạn, {time.perf_counter() - t:.1f} s",
              flush=True)
    for ten in sorted(os.listdir(os.path.join(DU_LIEU, "kho"))):
        p = os.path.join(DU_LIEU, "kho", ten)
        print(ten, round(_dai(p), 3), "s", os.path.getsize(p), "B")


if __name__ == "__main__":
    main()
