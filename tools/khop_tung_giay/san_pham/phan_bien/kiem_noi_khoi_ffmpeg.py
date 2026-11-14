# -*- coding: utf-8 -*-
"""Phản biện đường FFmpeg THẬT của tinh_chinh_moc theo định dạng file (tín hiệu tổng hợp 700 s, thư mục tạm, không mạng).

Hai phép đo:
1. Vòng giải mã theo khối của ``tcm._dac_trung`` (gọi THẲNG hàm của module với bộ đọc FFmpeg thật, bọc để ghi từng lần
   gọi; ``moc`` ngắt sau 20 lần gọi): khối cuối thiếu < 0,05 s thì không coi là hết file, khối kế xin phần dư vài ms,
   FFmpeg trả 0 mẫu → ``vi_tri`` không tiến → lặp mãi (chỉ ``han_chot``/``kiem_huy`` ngắt được). Ghi cửa sổ nào kẹt.
2. Mẫu đầu tiên FFmpeg trả có đúng là giây ``tu`` không (``_doc_pcm_ffmpeg`` trả ``tu`` làm «giây thật»): so tương quan
   chéo ±50 ms với bản WAV gốc giải mã cùng ``tu``.

Chạy (Git Bash, ~2 phút):
  cd /c/Dev/Tool_Quet/TimClipPro
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \\
      -B -X utf8 ../tools/khop_tung_giay/san_pham/phan_bien/kiem_noi_khoi_ffmpeg.py
Ghi ``<RA>\\noi_khoi_ffmpeg.json``.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_doi_khang as h  # noqa: E402

import numpy as np  # noqa: E402

tcm = h.tcm
DINH_DANG = {                     # tên: (đuôi, tham số mã hoá FFmpeg)
    "wav": (".wav", ["-c:a", "pcm_s16le"]),
    "flac": (".flac", ["-c:a", "flac"]),
    "opus_ogg_16k_64k": (".opus", ["-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "64k"]),
    "opus_webm_48k": (".webm", ["-c:a", "libopus", "-b:a", "96k"]),
    "mp3_cbr": (".mp3", ["-c:a", "libmp3lame", "-b:a", "128k"]),
    "mp3_vbr": (".mp3", ["-c:a", "libmp3lame", "-q:a", "4"]),
    "aac_m4a_22k": (".m4a", ["-c:a", "aac", "-b:a", "128k"]),
    "aac_mp4_44k_stereo": (".mp4", ["-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "160k"]),
}
CUA_SO = [(37.3, 690.0), (37.3, 337.3), (10.0, 400.0), (0.0, 650.0), (123.45, 456.78)]


class _Ngat(Exception):
    pass


def thu_vong(duong: str, tu: float, den: float) -> dict:
    goi: list = []

    def doc(d, a, b):
        x, t = tcm._doc_pcm_ffmpeg(d, a, b)
        goi.append([round(a, 5), round(b, 5), int(len(x)), round(b * tcm.SR - len(x), 1)])
        return x, t

    def moc():
        if len(goi) >= 20:
            raise _Ngat
    try:
        cs = tcm._dac_trung(doc, duong, tu, den, moc)
        return {"cua_so": [tu, den], "ket_qua": "xong", "so_khung": int(len(cs.X)), "goi": goi}
    except _Ngat:
        return {"cua_so": [tu, den], "ket_qua": "VONG_LAP_KHONG_TIEN", "goi": goi[:4]}


def lech_tai(a: np.ndarray, b: np.ndarray, i: int, w: int = 4096, tim: int = 551) -> int:
    """d sao cho b[i + d] ≈ a[i] (tương quan chéo chuẩn hoá trong ±tim mẫu)."""
    ref = a[i: i + w].astype(np.float64)
    best, arg = -np.inf, 0
    for d in range(-tim, tim + 1):
        seg = b[i + d: i + d + w].astype(np.float64)
        if i + d < 0 or len(seg) < w:
            continue
        c = float(np.dot(ref, seg) / (np.linalg.norm(ref) * np.linalg.norm(seg) + 1e-12))
        if c > best:
            best, arg = c, d
    return arg


def main() -> int:
    tmp = os.path.join(h.RA, "tmp", "noi_khoi")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    goc = os.path.join(tmp, "goc.wav")
    h._ghi_wav(goc, h._giai_dieu(700, seed=9931))
    ra = {}
    try:
        for ten, (duoi, ts) in DINH_DANG.items():
            f = os.path.join(tmp, ten + duoi)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", goc, *ts, f], check=True)
            vong = [thu_vong(f, tu, den) for tu, den in CUA_SO]
            lech = {}
            for tu in (0.0, 37.3):
                x, _ = tcm._doc_pcm_ffmpeg(f, tu, 30.0)
                r, _ = tcm._doc_pcm_ffmpeg(goc, tu, 30.0)
                d = lech_tai(r, x, 2000)
                lech[str(tu)] = {"mau": d, "ms": round(1000.0 * d / tcm.SR, 1)}   # d < 0: mẫu đầu MUỘN hơn tu
            ra[ten] = {"vong": vong, "lech_dau": lech}
            ket = sum(v["ket_qua"] != "xong" for v in vong)
            print(f"{ten:20s} kẹt {ket}/{len(vong)} cửa sổ; mẫu đầu lệch so với tu: "
                  f"{ {k: v['ms'] for k, v in lech.items()} } ms", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(os.path.join(h.RA, "noi_khoi_ffmpeg.json"), "w", encoding="utf-8") as fh:
        json.dump(ra, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
