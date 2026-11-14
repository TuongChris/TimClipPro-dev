# -*- coding: utf-8 -*-
"""Phản biện HIỆU NĂNG (14/11/2026): tách thời gian tinh_chinh (Cách C) thành đường nền tại chỗ / bám từng giây / mép,
trên ca «clip 60 phút dùng trọn» của thang_do (video_B, giây 1800). Chỉ bọc hàm của tuong_dong để đo giờ.
Chạy: PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B -X utf8 do_phan_tach.py
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import do_tinh_chinh as d  # noqa: E402

td = d.td
DO: dict = {}


def boc(ten: str):
    goc = getattr(td, ten)

    def f(*a, **k):
        t = time.perf_counter()
        try:
            return goc(*a, **k)
        finally:
            DO[ten] = DO.get(ten, 0.0) + time.perf_counter() - t
    setattr(td, ten, f)


for ten in ("duong_nen_tai_cho", "ho_so_tung_giay", "mep_tinh"):
    boc(ten)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    clip = os.path.join(d.GOC, "thang_do", "goc_dau_3600.opus")
    video = os.path.join(d.DU_LIEU, "video_B.webm")
    m = {"start_s": 1800.0, "vung_khop_s": 1980.0, "clip_offset_s": 180.0, "end_s": 5220.0}
    C, c0, n_c = d.log_mel_dong(clip, 0.0, 3600.0)
    tu, dai = d.cua_so_video(m, 0.0, n_c / td.SR, 1.0, d.ffprobe_dai(video))
    V, T0, _ = d.log_mel_dong(video, tu, dai)
    t = time.perf_counter()
    kq = td.tinh_chinh(C, V, T0, n_c / td.SR, m, video_den=10800.0)
    tong = time.perf_counter() - t
    ra = {"ca": "clip 60 phút dùng trọn (V1t)", "tinh_chinh_tong_s": round(tong, 3),
          **{k: round(v, 3) for k, v in DO.items()},
          "doan": [(x["video_tu"], x["video_den"]) for x in kq["doan"]], "so_lan_do_nen": kq["duong_nen"]["so_giay"],
          "so_giay_bam": kq["so_giay_bam"]}
    print(json.dumps(ra, ensure_ascii=False))
    with open(os.path.join(d.GOC, "thang_do", "phan_tach_tinh_chinh.json"), "w", encoding="utf-8") as f:
        json.dump(ra, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
