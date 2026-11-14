# -*- coding: utf-8 -*-
"""Kiểm độ bền của Cách C khi NEO engine lệch (audfprint làm tròn 0,1 s; dòng chưa bù tốc độ còn lệch hơn).

Với một số dòng đã chấp nhận: dời vung_khop_s ±0,2 / ±0,4 s (giữ clip_offset_s) rồi tinh chỉnh lại; in độ lệch lớn nhất
của mép đoạn so với khi neo đúng. Chỉ đọc bộ thử; ghi cach_c/kiem_neo_lech.json.
"""
from __future__ import annotations

import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chay_cach_c as cc  # noqa: E402  (kiểm môi trường chặn mạng khi import)
import tuong_dong as td  # noqa: E402

RA = os.path.join(cc.RA_MAC_DINH, "kiem_neo_lech.json")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    kq = []
    for S in ("S1", "S3", "S4", "S7", "S7b", "X1", "X2", "X3"):
        d = cc._thu_muc(S)
        st, ke = cc._json(os.path.join(d, "su_that.json")), cc._json(os.path.join(d, "ket_qua_engine.json"))
        dur = float(ke["duration_s"])
        for m in ke["dong_cho_clip"]["matches"]:
            xc, _ = td.doc_pcm(cc._an_toan(m["duong_dan_kho"]))
            C, L = td.log_mel(xc), round(len(xc) / td.SR, 3)
            tu, dai = cc.vung_video(m, L, dur)
            xv, T0 = td.doc_pcm(cc._an_toan(os.path.join(d, st["video"])), tu - 1.0, dai + 2.0)
            V = td.log_mel(xv)
            goc = td.tinh_chinh(C, V, T0, L, m, video_den=dur)["doan"]
            lech_max, so_doan = 0.0, []
            for dl in (-0.45, -0.4, -0.2, 0.2, 0.4, 0.45):
                r = td.tinh_chinh(C, V, T0, L, {**m, "vung_khop_s": m["vung_khop_s"] + dl}, video_den=dur)["doan"]
                so_doan.append(len(r))
                if len(r) == len(goc):
                    lech_max = max([lech_max] + [abs(a[x] - b[x]) for a, b in zip(goc, r)
                                                 for x in ("video_tu", "video_den")])
                else:
                    lech_max = float("inf")
            kq.append({"kich_ban": S, "start_s": m["start_s"], "so_doan_goc": len(goc), "so_doan_khi_lech": so_doan,
                       "lech_mep_lon_nhat_s": round(lech_max, 3)})
            print(kq[-1], flush=True)
    with open(RA, "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
