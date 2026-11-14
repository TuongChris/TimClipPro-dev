# -*- coding: utf-8 -*-
"""Thí nghiệm phụ của Cách C: đặc trưng nào tách «có clip» khỏi «không có clip» tốt hơn (14/11/2026).

Tính độ tương đồng từng giây DỌC ĐƯỜNG CĂN CHỈNH THẬT (sự thật của bộ thử, không bám), lấy đỉnh trong ±W, cho:
  mel40 = log-mel 40 dải (đang dùng) | lin = log phổ tuyến tính 21,5 Hz/ô (219 ô, 300–5000 Hz);
  W = 0,1 / 0,3 s; cửa sổ 1 s / 3 s (đặt giữa giây).
Dương: giây trong đoạn thật (S1, S2, S5, S5b, S6, S6b, S7b). Âm: cùng cặp lệch 6,1 / −13,7 / 29,3 / −52,9 s; video
S0 (không liên quan) × clip nốt ngẫu nhiên S1/S4/S9 và nhạc có nhịp S6/S6b. Chỉ đọc bộ thử; in bảng + ghi JSON.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
import json  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tuong_dong as td  # noqa: E402

BO_THU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"
RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_c\so_sanh_dac_trung.json"
LECH = (6.1, -13.7, 29.3, -52.9)
B0, B1 = int(np.ceil(td.FMIN / (td.SR / td.N_FFT))), int(np.floor(td.FMAX / (td.SR / td.N_FFT)))


def chuan_hoa(lm: np.ndarray) -> np.ndarray:
    """Cách chuẩn hoá của BẢN ĐẦU tuong_dong: trừ trung bình từng dải trên cả đoạn đã giải mã."""
    return lm - lm.mean(axis=0) if len(lm) else lm


def _ncc(a: np.ndarray, vung: np.ndarray) -> np.ndarray:
    """Pearson thường (chỉ trừ trung bình vô hướng) theo từng độ trễ — hàm của BẢN ĐẦU tuong_dong."""
    F, B = a.shape
    na = np.sqrt(float(np.dot(a.ravel(), a.ravel())))
    tu = np.lib.stride_tricks.sliding_window_view(vung.ravel(), F * B)[::B] @ a.ravel()
    c1 = np.concatenate([[0.0], np.cumsum(vung.sum(axis=1))])
    c2 = np.concatenate([[0.0], np.cumsum(np.einsum("fb,fb->f", vung, vung))])
    s1, s2 = c1[F:] - c1[:-F], c2[F:] - c2[:-F]
    return tu / (na * np.sqrt(np.maximum(s2 - s1 * s1 / (F * B), 1e-12)) + 1e-12)


def pho(x: np.ndarray, kieu: str) -> np.ndarray:
    if kieu == "mel40":
        return td.log_mel(x)
    n = 1 + (len(x) - td.N_FFT) // td.HOP
    ra = np.empty((n, B1 - B0 + 1))
    khung = np.lib.stride_tricks.sliding_window_view(x, td.N_FFT)[::td.HOP]
    for i in range(0, n, 4096):
        ra[i:i + 4096] = (np.abs(np.fft.rfft(khung[i:i + 4096] * td._CUA_SO, axis=1)) ** 2)[:, B0:B1 + 1]
    san = max(np.percentile(ra, 99) * 10 ** (td.SAN_DB / 10), 1e-20)
    return np.log10(np.maximum(ra, san))


def gia_tri(C, V, cs, taus, W, w) -> np.ndarray:
    """Đỉnh Pearson trong ±W của cửa sổ w giây đặt giữa giây clip c (vị trí video dự đoán = tau)."""
    F, L, ra = int(round(w * td.FPS)), int(round(W * td.FPS)), []
    for c, tau in zip(cs, taus):
        fc = int(round((c + 0.5 - w / 2) * td.FPS))
        if fc < 0 or fc + F > len(C):
            continue
        p = int(round((tau + 0.5 - w / 2) * td.FPS))
        lo, hi = max(0, p - L), min(len(V) - F, p + L)
        if hi < lo:
            continue
        a = C[fc:fc + F] - C[fc:fc + F].mean()
        ra.append(float(_ncc(a, V[lo:hi + F]).max()))
    return np.array(ra)


def doc(S, ten=None):
    d = os.path.join(BO_THU, S)
    st = json.load(open(os.path.join(d, "su_that.json"), encoding="utf-8"))
    xc, _ = td.doc_pcm(os.path.join(d, "kho", ten or st["ten_clip"]))
    xv, _ = td.doc_pcm(os.path.join(d, st["video"]))
    return st, xc, xv


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    am_thanh = {S: doc(S) for S in ("S1", "S2", "S3", "S5", "S5b", "S6", "S6b", "S7b")}
    d0 = os.path.join(BO_THU, "S0")
    xv0, _ = td.doc_pcm(os.path.join(d0, "video_vi_pham.wav"))
    clip0 = {t: td.doc_pcm(os.path.join(d0, "kho", t))[0] for t in ("goc_S1.wav", "goc_S4.wav", "goc_S9.wav",
                                                                     "goc_S6.wav", "goc_S6b.wav")}
    kq = {}
    for kieu in ("mel40", "lin"):
        dt = {S: (st, chuan_hoa(pho(xc, kieu)), chuan_hoa(pho(xv, kieu))) for S, (st, xc, xv) in am_thanh.items()}
        V0 = chuan_hoa(pho(xv0, kieu))
        C0 = {t: chuan_hoa(pho(x, kieu)) for t, x in clip0.items()}
        for W in (0.1, 0.3):
            for w in (1.0, 3.0):
                t = time.perf_counter()
                cfg = f"{kieu}|W={W}|cua_so={w:g}s"
                duong, am_not, am_nhip = {}, [], []
                for S, (st, C, V) in dt.items():
                    for dn in st["doan"]:
                        cs = np.arange(int(np.ceil(dn["clip_tu"])), int(dn["clip_den"]))
                        taus = dn["video_tu"] + (cs - dn["clip_tu"]) / dn["he_so"]
                        duong[S] = gia_tri(C, V, cs, taus, W, w)
                        for dl in LECH:
                            g = gia_tri(C, V, cs, taus + dl, W, w)
                            (am_nhip if S in ("S6", "S6b") else am_not).extend(g)
                for ten, C in C0.items():
                    for t0 in np.arange(0.0, 1000.0 - len(C) / td.FPS, 61.7):
                        cs = np.arange(0, int(len(C) / td.FPS) - 1)
                        g = gia_tri(C, V0, cs, t0 + cs, W, w)
                        (am_nhip if ten in ("goc_S6.wav", "goc_S6b.wav") else am_not).extend(g)
                pv = lambda x, q: round(100 * float(np.percentile(x, q)), 1)  # noqa: E731
                kq[cfg] = {"duong": {S: {"p1": pv(g, 1), "p5": pv(g, 5), "p50": pv(g, 50)} for S, g in duong.items()},
                           "am_not_ngau_nhien": {"n": len(am_not), "p99": pv(am_not, 99), "p99_9": pv(am_not, 99.9),
                                                 "max": round(100 * max(am_not), 1)},
                           "am_nhac_co_nhip": {"n": len(am_nhip), "p99": pv(am_nhip, 99), "p99_9": pv(am_nhip, 99.9),
                                               "max": round(100 * max(am_nhip), 1)},
                           "giay_chay": round(time.perf_counter() - t, 1)}
                r = kq[cfg]
                print(cfg, "| S5 p5/p50", r["duong"]["S5"]["p5"], r["duong"]["S5"]["p50"],
                      "| S5b p5/p50", r["duong"]["S5b"]["p5"], r["duong"]["S5b"]["p50"],
                      "| S2 p5", r["duong"]["S2"]["p5"], "| S6 p5", r["duong"]["S6"]["p5"],
                      "| S7b p5", r["duong"]["S7b"]["p5"],
                      "| âm nốt p99/max", r["am_not_ngau_nhien"]["p99"], r["am_not_ngau_nhien"]["max"],
                      "| âm nhịp p99/max", r["am_nhac_co_nhip"]["p99"], r["am_nhac_co_nhip"]["max"], flush=True)
    with open(RA, "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
