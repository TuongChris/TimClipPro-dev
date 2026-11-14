# -*- coding: utf-8 -*-
"""Phản biện HIỆU NĂNG (14/11/2026): đòn bẩy «đường nền tại chỗ lấy mẫu thưa» của Cách C.

duong_nen_tai_cho đo MỌI giây clip × 6 đường lệch (82% thời gian tinh_chinh ở clip 60 phút — do_phan_tach.py). Ở đây chạy
lại chay_cach_c.kich_ban (chỉ import, không sửa) trên 15 kịch bản bo_thu + X1–X3 với bước lấy mẫu nền 1 (gốc) và 4, so số
đoạn, mép, ngưỡng, thời gian. Ghi vào phan_bien_hieu_nang/nen_thua/<bước>/ — không đụng kết quả bước trước.
Chạy: PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B -X utf8 do_nen_thua.py
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cach_c"))
import chay_cach_c as cc  # noqa: E402
import tuong_dong as td  # noqa: E402

RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_hieu_nang\nen_thua"
GOC_NEN = td.duong_nen_tai_cho


def nen_thua(buoc: int):
    def f(do, so_giay, duong, toc, ts):
        ra = []
        for dl in ts["lech_nen_s"]:
            for n in range(0, so_giay, buoc):
                m = do(n, duong(n) + dl, ts["W"], toc)
                if m is not None:
                    ra.append(m[0])
        import numpy as np
        return np.array(ra)
    return f


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tong: dict = {}
    for buoc in (1, 4):
        td.duong_nen_tai_cho = GOC_NEN if buoc == 1 else nen_thua(buoc)
        nen: dict = {"duong": {}, "ngoai_doan_that": {}}
        kq_buoc = {}
        for S in cc.THU_TU:
            if S == "S0":
                continue
            t = time.perf_counter()
            kb = cc.kich_ban(S, dict(td.THAM_SO_MAC_DINH), os.path.join(RA, f"buoc_{buoc}"), nen)
            kq_buoc[S] = {"danh_gia": {k: kb["danh_gia"][k] for k in ("so_doan_tim", "doan_tim", "precision_giay",
                                                                      "recall_giay", "sai_so_dau_s", "sai_so_cuoi_s")},
                          "tinh_chinh_s": round(sum(dg["thoi_gian"]["tinh_chinh_s"] for dg in kb["dong"]
                                                    if dg["loai"] == "chap_nhan"), 3),
                          "tong_s": kb["thoi_gian_tong_s"],
                          "nguong": [(dg["muc_trong"], dg["duong_nen"]["p99"], dg["duong_nen"]["max"], dg["nguong_bam"],
                                      dg["nguong_dung"], dg["tuong_phan_thap"], dg["giay_sai_tren_nguong"],
                                      dg["giay_dung_duoi_nguong"]) for dg in kb["dong"]],
                          "chay_s": round(time.perf_counter() - t, 2)}
            print(f"bước {buoc} {S}: {kq_buoc[S]['danh_gia']['doan_tim']} tinh_chinh {kq_buoc[S]['tinh_chinh_s']} s "
                  f"ngưỡng {kq_buoc[S]['nguong']}", flush=True)
        tong[f"buoc_{buoc}"] = kq_buoc
    so = {}
    for S in tong["buoc_1"]:
        a, b = tong["buoc_1"][S], tong["buoc_4"][S]
        da, db = a["danh_gia"]["doan_tim"], b["danh_gia"]["doan_tim"]
        so[S] = {"cung_so_doan": len(da) == len(db),
                 "lech_mep_max_s": max([max(abs(x[0] - y[0]), abs(x[1] - y[1])) for x, y in zip(da, db)], default=None),
                 "tinh_chinh_s": [a["tinh_chinh_s"], b["tinh_chinh_s"]],
                 "nguong_dung": [[x[4] for x in a["nguong"]], [x[4] for x in b["nguong"]]],
                 "giay_sai_tren_nguong_buoc4": [x[6] for x in b["nguong"]],
                 "giay_dung_duoi_nguong_buoc4": [x[7] for x in b["nguong"]]}
    tong["so_sanh"] = so
    tong["tinh_chinh_tong_s"] = {k: round(sum(v["tinh_chinh_s"] for v in tong[k].values()), 2) for k in ("buoc_1", "buoc_4")}
    os.makedirs(RA, exist_ok=True)
    with open(os.path.join(RA, "so_sanh.json"), "w", encoding="utf-8") as f:
        json.dump(tong, f, ensure_ascii=False, indent=1)
    print(json.dumps({"tinh_chinh_tong_s": tong["tinh_chinh_tong_s"], "so_sanh": so}, ensure_ascii=False))


if __name__ == "__main__":
    main()
