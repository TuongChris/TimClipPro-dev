# -*- coding: utf-8 -*-
"""Thí nghiệm phụ 2 của Cách C: cách chuẩn hoá phổ nào KHÔNG phụ thuộc nội dung xung quanh (14/11/2026).

Như so_sanh_dac_trung.py (dọc căn chỉnh THẬT, W = 0,1 s, cửa sổ 3 s), so 3 cách chuẩn hoá trên mel40 và lin:
  vung  = trừ trung bình từng dải trên CẢ file đã giải mã (phụ thuộc nội dung quanh clip);
  khong = không trừ theo dải (chỉ trừ trung bình vô hướng của miếng, như Pearson thường);
  mieng = trừ trung bình từng dải TRONG từng miếng 3 s (cả clip lẫn video) — không phụ thuộc gì ngoài miếng.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
import json  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import so_sanh_dac_trung as ss  # noqa: E402
import tuong_dong as td  # noqa: E402

RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_c\so_sanh_chuan_hoa.json"


def ncc_mieng(a, vung):
    """Pearson sau khi trừ trung bình TỪNG DẢI trong miếng (a đã trừ theo dải)."""
    F, B = a.shape
    na = np.sqrt(float((a * a).sum()))
    cs = np.lib.stride_tricks.sliding_window_view(vung.ravel(), F * B)[::B]
    tu = cs @ a.ravel()
    c1 = np.vstack([np.zeros((1, B)), np.cumsum(vung, axis=0)])
    c2 = np.concatenate([[0.0], np.cumsum((vung * vung).sum(axis=1))])
    s1 = c1[F:] - c1[:-F]                      # (2L+1, B) tổng theo dải của từng cửa sổ
    nang = (c2[F:] - c2[:-F]) - (s1 * s1).sum(axis=1) / F
    return tu / (na * np.sqrt(np.maximum(nang, 1e-12)) + 1e-12)


def gia_tri(C, V, cs_, taus, W, w, kieu_cn):
    F, L, ra = int(round(w * td.FPS)), int(round(W * td.FPS)), []
    for c, tau in zip(cs_, taus):
        fc = int(round((c + 0.5 - w / 2) * td.FPS))
        if fc < 0 or fc + F > len(C):
            continue
        p = int(round((tau + 0.5 - w / 2) * td.FPS))
        lo, hi = max(0, p - L), min(len(V) - F, p + L)
        if hi < lo:
            continue
        a = C[fc:fc + F]
        if kieu_cn == "mieng":
            ra.append(float(ncc_mieng(a - a.mean(axis=0), V[lo:hi + F]).max()))
        else:
            ra.append(float(ss._ncc(a - a.mean(), V[lo:hi + F]).max()))
    return np.array(ra)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    am = {S: ss.doc(S) for S in ("S1", "S2", "S3", "S5", "S5b", "S6", "S6b", "S7b")}
    d0 = os.path.join(ss.BO_THU, "S0")
    xv0, _ = td.doc_pcm(os.path.join(d0, "video_vi_pham.wav"))
    clip0 = {t: td.doc_pcm(os.path.join(d0, "kho", t))[0] for t in ("goc_S1.wav", "goc_S4.wav", "goc_S9.wav",
                                                                     "goc_S6.wav", "goc_S6b.wav")}
    kq = {}
    for kieu in ("mel40", "lin"):
        tho = {S: (st, ss.pho(xc, kieu), ss.pho(xv, kieu)) for S, (st, xc, xv) in am.items()}
        V0t = ss.pho(xv0, kieu)
        C0t = {t: ss.pho(x, kieu) for t, x in clip0.items()}
        for cn in ("vung", "khong", "mieng"):
            f = ss.chuan_hoa if cn == "vung" else (lambda z: z)
            W, w = 0.1, 3.0
            duong, am_not, am_nhip = {}, [], []
            for S, (st, C, V) in tho.items():
                C, V = f(C), f(V)
                for dn in st["doan"]:
                    cs_ = np.arange(int(np.ceil(dn["clip_tu"])), int(dn["clip_den"]))
                    taus = dn["video_tu"] + (cs_ - dn["clip_tu"]) / dn["he_so"]
                    duong[S] = gia_tri(C, V, cs_, taus, W, w, cn)
                    for dl in ss.LECH:
                        (am_nhip if S in ("S6", "S6b") else am_not).extend(gia_tri(C, V, cs_, taus + dl, W, w, cn))
            V0 = f(V0t)
            for ten, C in C0t.items():
                C = f(C)
                for t0 in np.arange(0.0, 1000.0 - len(C) / td.FPS, 61.7):
                    cs_ = np.arange(0, int(len(C) / td.FPS) - 1)
                    (am_nhip if ten in ("goc_S6.wav", "goc_S6b.wav") else am_not).extend(
                        gia_tri(C, V0, cs_, t0 + cs_, W, w, cn))
            pv = lambda x, q: round(100 * float(np.percentile(x, q)), 1)  # noqa: E731
            cfg = f"{kieu}|{cn}|W=0.1|cua_so=3s"
            kq[cfg] = {"duong": {S: {"p1": pv(g, 1), "p5": pv(g, 5), "p50": pv(g, 50)} for S, g in duong.items()},
                       "am_not_ngau_nhien": {"n": len(am_not), "p99": pv(am_not, 99), "p99_9": pv(am_not, 99.9),
                                             "max": round(100 * max(am_not), 1)},
                       "am_nhac_co_nhip": {"n": len(am_nhip), "p99": pv(am_nhip, 99), "p99_9": pv(am_nhip, 99.9),
                                           "max": round(100 * max(am_nhip), 1)}}
            r = kq[cfg]
            print(cfg, "| S5 p1/p5/p50", r["duong"]["S5"]["p1"], r["duong"]["S5"]["p5"], r["duong"]["S5"]["p50"],
                  "| S5b p1/p5/p50", r["duong"]["S5b"]["p1"], r["duong"]["S5b"]["p5"], r["duong"]["S5b"]["p50"],
                  "| S2 p1", r["duong"]["S2"]["p1"], "| S6 p1", r["duong"]["S6"]["p1"], "| S6b p1", r["duong"]["S6b"]["p1"],
                  "| S7b p1", r["duong"]["S7b"]["p1"],
                  "| âm nốt p99/p99.9/max", r["am_not_ngau_nhien"]["p99"], r["am_not_ngau_nhien"]["p99_9"],
                  r["am_not_ngau_nhien"]["max"],
                  "| âm nhịp p99/p99.9/max", r["am_nhac_co_nhip"]["p99"], r["am_nhac_co_nhip"]["p99_9"],
                  r["am_nhac_co_nhip"]["max"], flush=True)
    with open(RA, "w", encoding="utf-8") as fo:
        json.dump(kq, fo, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
