# -*- coding: utf-8 -*-
"""Phản biện đo lường — chạy lại TRỌN Cách B (chay_cach_b.main, import, không sửa) vào thư mục của tôi, rồi so điểm
chấm từng kịch bản với cach_b/tong_hop_cach_b.json của bước trước."""
from __future__ import annotations

import json
import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, r"C:\Dev\pc2_test_tools\khop_tung_giay\bo_thu")
sys.path.insert(0, r"C:\Dev\pc2_test_tools\khop_tung_giay\cach_b")
import chay_cach_b as cbb  # noqa: E402

RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_do_luong\chay_lai_cach_b"
CU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_b\tong_hop_cach_b.json"

if __name__ == "__main__":
    cbb.KET_QUA = RA
    cbb.main()
    a = {k["kich_ban"]: k for k in json.load(open(os.path.join(RA, "tong_hop_cach_b.json"), encoding="utf-8"))["kich_ban"]}
    b = {k["kich_ban"]: k for k in json.load(open(CU, encoding="utf-8"))["kich_ban"]}
    khac = []
    for S in b:
        da = [(z["video_tu"], z["video_den"]) for r in a.get(S, {}).get("dong", []) for z in r["doan"]]
        db = [(z["video_tu"], z["video_den"]) for r in b[S].get("dong", []) for z in r["doan"]]
        if da != db:
            khac.append((S, da, db))
    print("so kich ban", len(b), "khac:", khac)
    json.dump({"khac": khac}, open(os.path.join(RA, "so_sanh.json"), "w", encoding="utf-8"), ensure_ascii=False)
