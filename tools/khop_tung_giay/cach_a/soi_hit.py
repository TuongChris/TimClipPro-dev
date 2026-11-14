# -*- coding: utf-8 -*-
"""Soi TỪNG hash khớp của một căn chỉnh (cùng phép tính audfprint dùng cho --find-time-range) để chứng minh vì sao
-Q 0 kéo mép ra xa: mép = hit SỚM/MUỘN nhất trong cửa sổ mode ± --match-win, kể cả hit tình cờ.

Gọi thẳng module của audfprint-master (chỉ import, không sửa) trên kho CHÉP + khúc của bo_thu; analyzer đặt đúng tham số
mặc định của CLI ``match`` (density 20, fanout 3, pks-per-frame 5, freq-sd 30, shifts 4, sr 11025, match-win 2).

Chạy: PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B soi_hit.py S4 S4b
"""
from __future__ import annotations

import os
import sys

import numpy as np

import chung as c

sys.path.insert(0, os.path.join(c.MA, "audfprint-master"))
import audfprint_analyze  # noqa: E402
import hash_table  # noqa: E402

WIN = 2


def soi(ten: str) -> dict:
    d = os.path.join(c.BO_THU, ten)
    st = c.doc_json(os.path.join(d, "su_that.json"))
    db = os.path.join(c.KET_QUA, "truc_tiep", ten, "kho_chep_tu_bo_thu.pklz")
    ht = hash_table.HashTable(db)
    an = audfprint_analyze.Analyzer()
    an.density, an.maxpksperframe, an.maxpairsperpeak, an.f_sd = 20.0, 5, 3, 30.0
    an.shifts, an.target_sr, an.n_fft, an.n_hop = 4, 11025, 512, 256
    t_hop = an.n_hop / an.target_sr
    khuc = os.path.join(d, "khuc", "chunk_0000000.wav")
    hits = ht.get_hits(an.wavfile2hashes(khuc))
    ids = [i for i, n in enumerate(ht.names) if n and os.path.basename(n) == st["ten_clip"]]
    hits = hits[hits[:, 0] == ids[0]]
    ra = {"kich_ban": ten, "so_hit_cua_clip": int(len(hits)), "doan": []}
    for dd in st["doan"]:
        align = dd["video_tu"] - dd["clip_tu"] / dd["he_so"]
        dk = -align / t_hop                                    # dtime = t_ref − t_query (khung)
        gan = hits[np.abs(hits[:, 1] - dk) <= 3 * WIN]
        mode = int(np.bincount(gan[:, 1] - gan[:, 1].min()).argmax() + gan[:, 1].min())
        t = np.sort(hits[np.abs(hits[:, 1] - mode) <= WIN, 3]) * t_hop     # đúng tập match_times của audfprint
        trong = (t >= dd["video_tu"] - 1) & (t <= dd["video_den"] + 1)
        ra["doan"].append({
            "video_tu": dd["video_tu"], "video_den": dd["video_den"], "so_hit": int(len(t)),
            "so_hit_ngoai_doan": int((~trong).sum()), "hit_ngoai_doan_s": [round(float(x), 2) for x in t[~trong]][:40],
            "min_s": round(float(t[0]), 2), "max_s": round(float(t[-1]), 2),
            "phan_vi": {q: [round(float(t[int(len(t) * q)]), 2), round(float(t[int(len(t) * (1 - q)) - 1]), 2)]
                        for q in (0.05, 0.02, 0.01, 0.005, 0.002, 0.0)},
        })
    return ra


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c.kiem_moi_truong()
    out = {}
    for ten in sys.argv[1:]:
        out[ten] = soi(ten)
        for x in out[ten]["doan"]:
            print(ten, f"[{x['video_tu']}, {x['video_den']}]", "hit", x["so_hit"], "ngoài đoạn", x["so_hit_ngoai_doan"],
                  x["hit_ngoai_doan_s"][:12], "phân vị", x["phan_vi"], flush=True)
    c.ghi_json(os.path.join(c.KET_QUA, "truc_tiep", "soi_hit.json"), out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
