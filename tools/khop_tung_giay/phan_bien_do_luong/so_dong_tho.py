# -*- coding: utf-8 -*-
"""So dòng thô «Matched …» của audfprint giữa lần chạy lại (của tôi) và bo_thu, sau khi bỏ đường dẫn (thư mục khác
nhau nên chuỗi thô không thể trùng nguyên văn). Trùng = cùng (file raw, khớp, bắt đầu, tên khúc, t_clip, tên clip, n, m).
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.dont_write_bytecode = True
RE = re.compile(r"Matched\s+(\S+)\s+s\s+starting\s+at\s+(\S+)\s+s\s+in\s+(.+?)\s+to\s+time\s+(\S+)\s+s\s+in\s+(.+?)\s+with\s+(\d+)\s+of\s+(\d+)\s+common")
RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_do_luong\chay_lai"
BO_THU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"


def chuan(dong: str) -> tuple:
    ten_raw, phan = dong.split(": ", 1)
    m = RE.search(phan)
    if not m:
        return (ten_raw, phan)
    k, b, khuc, t, clip, n, tong = m.groups()
    return (ten_raw, k, b, os.path.basename(khuc), t, os.path.basename(clip), n, tong)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    kq = {}
    for S in sys.argv[1:] or ["S1", "S4", "S7b", "S6b"]:
        a, b = (json.load(open(os.path.join(g, S, "ket_qua_engine.json"), encoding="utf-8"))["dong_tho_matched"]
                for g in (RA, BO_THU))
        ca, cb_ = sorted(chuan(x) for x in a), sorted(chuan(x) for x in b)
        kq[S] = {"so_dong": [len(ca), len(cb_)], "trung_sau_bo_duong_dan": ca == cb_,
                 "khac": [list(x) for x in sorted(set(ca) ^ set(cb_))][:5]}
        print(S, json.dumps(kq[S], ensure_ascii=False))
    with open(os.path.join(RA, "so_dong_tho.json"), "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
