# -*- coding: utf-8 -*-
"""Phản biện đo lường — gom mọi bằng chứng của thư mục phan_bien_do_luong vào MỘT file tong_hop_phan_bien.json.

Không chạy lại gì: chỉ đọc kết quả của su_that_doc_lap.py, tai_tao_kich_ban.py, cham_doc_lap.py, chay_lai.py,
so_dong_tho.py, ca_kho.py, ca_kho_cach_b.py và cach_c/tong_hop.json (đếm mép «chốt về đầu/cuối clip» so với mép tìm thật).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
GOC = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay"
RA = os.path.join(GOC, "phan_bien_do_luong")


def _json(*p):
    path = os.path.join(*p)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tong: dict = {}
    tt = _json(RA, "tai_tao_kich_ban.json") or {}
    tong["tai_tao"] = {"so_kich_ban": len(tt), "moi_file_trung": sum(v["moi_file_trung"] for v in tt.values()),
                       "su_that_trung": sum(v["su_that_trung"] for v in tt.values())}
    sd = _json(RA, "su_that_doc_lap.json") or {}
    tong["su_that_doc_lap"] = {S: {k: v.get(k) for k in ("cach", "ket_luan", "lech_lon_nhat_s", "lech_mep_lon_nhat_s")}
                               | ({"anh_xa": [{k: x.get(k) for k in ("ncc_trung_vi", "lech_trung_vi_ms", "lech_p5_ms",
                                                                     "lech_p95_ms", "lech_hoi_quy")}
                                              for x in v["kiem_doan"]], "dinh_la": v["do_toan_video"][
                                       "so_dinh_la_xa_gia_thuyet"]} if v.get("kiem_doan") else {})
                               | ({"so_doan_bong_cung_am_thanh": len(v["doan_bong_cung_am_thanh"])}
                                  if v.get("doan_bong_cung_am_thanh") else {})
                               for S, v in sd.items()}
    cl = _json(RA, "cham_lai_doc_lap.json") or {}
    tong["cham_lai_doc_lap"] = cl.get("lech_lon_nhat_giua_toi_va_da_bao")
    cc = (_json(GOC, "cach_c", "tong_hop.json") or {}).get("kich_ban", {})
    chot = tim = 0
    loi_tim, loi_chot = [], []
    for S, v in cc.items():
        for dg in v["tung_dong"]:
            if dg["loai"] != "chap_nhan":
                continue
            for x in dg["doan"]:
                for cach in x["cach_tim_mep"]:
                    if cach in ("dau_clip", "cuoi_clip"):
                        chot += 1
                    else:
                        tim += 1
        for e in v["danh_gia"].get("tung_doan_that", []):
            pass
    tong["cach_c_mep_trong_bo_thu"] = {"mep_chot_ve_dau_cuoi_clip": chot, "mep_tim_bang_bac_thang": tim}
    tong["chay_lai"] = _json(RA, "chay_lai", "so_sanh_chay_lai.json")
    tong["dong_tho_chay_lai"] = _json(RA, "chay_lai", "so_dong_tho.json")
    tong["ca_kho"] = _json(RA, "ca_kho", "tong_hop_ca_kho.json")
    # chạy lại TRỌN Cách C (có đường nền) và Cách B vào thư mục của tôi — so với bước trước
    moi_c, cu_c = _json(RA, "chay_lai_cach_c_day_du", "tong_hop.json"), _json(GOC, "cach_c", "tong_hop.json")
    if moi_c and cu_c:
        def doan(t, S):
            return [(x["video_tu"], x["video_den"], x["clip_tu"], x["clip_den"])
                    for d in t["kich_ban"][S]["tung_dong"] for x in d["doan"]]
        tong["chay_lai_cach_c_day_du"] = {
            "kich_ban_khac": [S for S in cu_c["kich_ban"] if doan(moi_c, S) != doan(cu_c, S)],
            "so_kich_ban": len(cu_c["kich_ban"]),
            "duong_nen_moi": {k: moi_c["duong_nen"][k] for k in ("dong_gia_van_ra_doan", "dong_gia_tuong_phan_thap",
                                                                  "so_dong_gia")},
            "phan_bo_nen_trung": moi_c["duong_nen"]["tom_tat_phan_bo"] == cu_c["duong_nen"]["tom_tat_phan_bo"]}
    tong["chay_lai_cach_b"] = _json(RA, "chay_lai_cach_b", "so_sanh.json")
    tong["repo"] = {
        "head": subprocess.run(["git", "-C", r"C:\Dev\Tool_Quet", "rev-parse", "HEAD"], capture_output=True,
                               text=True).stdout.strip(),
        "status_porcelain": subprocess.run(["git", "-C", r"C:\Dev\Tool_Quet", "status", "--porcelain"],
                                           capture_output=True, text=True).stdout.strip()}
    with open(os.path.join(RA, "tong_hop_phan_bien.json"), "w", encoding="utf-8") as f:
        json.dump(tong, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: tong[k] for k in ("tai_tao", "cham_lai_doc_lap", "cach_c_mep_trong_bo_thu", "repo")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
