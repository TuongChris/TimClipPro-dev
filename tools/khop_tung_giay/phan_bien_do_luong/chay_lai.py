# -*- coding: utf-8 -*-
"""Phản biện đo lường — CHẠY LẠI engine THẬT trên vài kịch bản (dựng lại audio + kho + quét, thư mục RIÊNG của tôi) rồi
chạy lại Cách C trên kết quả MỚI; so từng trường với lần chạy của bước trước (bo_thu, cach_c).

Dùng ``chay_bo_thu.chay_mot`` (import, KHÔNG sửa): đổi ``KET_QUA`` sang thư mục của tôi → bo_thu không bị đụng.
Cách C: import ``chay_cach_c``, đổi BO_THU (đường dẫn đọc) sang thư mục chạy lại.
  cd /c/Dev/pc2_test_tools/khop_tung_giay/phan_bien_do_luong
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B -X utf8 chay_lai.py S1 S4 S7b S6b
"""
from __future__ import annotations

import json
import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
GOC_CC = r"C:\Dev\pc2_test_tools\khop_tung_giay"
sys.path.insert(0, os.path.join(GOC_CC, "bo_thu"))
sys.path.insert(0, os.path.join(GOC_CC, "cach_c"))

import chay_bo_thu as cb  # noqa: E402  (kiểm môi trường chặn mạng + bọc Engine trong tiến trình)
import chay_cach_c as cc  # noqa: E402
import tuong_dong as td  # noqa: E402

RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_do_luong\chay_lai"
BO_THU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"
TRUONG = ("start_s", "vung_khop_s", "end_s", "matched_s", "clip_offset_s", "hashes", "ty_le", "confidence",
          "moc_mo_ho", "ty_so_doi_thu")


def _json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def so_engine(S: str) -> dict:
    moi, cu = (_json(os.path.join(g, S, "ket_qua_engine.json")) for g in (RA, BO_THU))
    rm = [{k: m.get(k) for k in TRUONG} for m in moi["dong_cho_clip"]["matches"]]
    rc = [{k: m.get(k) for k in TRUONG} for m in cu["dong_cho_clip"]["matches"]]
    tho_m = sorted(x.split(": ", 1)[1] for x in moi["dong_tho_matched"])
    tho_c = sorted(x.split(": ", 1)[1] for x in cu["dong_tho_matched"])
    nhom_m = [{k: g.get(k) for k in TRUONG} for g in moi["merge_cuoi"]["tat_ca_nhom_sau_merge"]]
    nhom_c = [{k: g.get(k) for k in TRUONG} for g in cu["merge_cuoi"]["tat_ca_nhom_sau_merge"]]
    return {"dong_trung": rm == rc, "dong_moi": rm, "dong_cu": rc,
            "dong_loai_trung": ([{k: m.get(k) for k in TRUONG} for m in moi["dong_cho_clip"]["matches_loai"]]
                                == [{k: m.get(k) for k in TRUONG} for m in cu["dong_cho_clip"]["matches_loai"]]),
            "dong_tho_trung": tho_m == tho_c, "so_dong_tho": [len(tho_m), len(tho_c)],
            "nhom_sau_merge_trung": nhom_m == nhom_c,
            "bao_cao_v2_trung": moi["bao_cao_v2_doan"] == cu["bao_cao_v2_doan"],
            "thoi_gian_quet_s": [moi["thoi_gian_quet_s"], cu["thoi_gian_quet_s"]]}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ds = sys.argv[1:] or ["S1", "S4", "S7b", "S6b"]
    os.makedirs(RA, exist_ok=True)
    cb.KET_QUA = RA
    kq = {}
    for S in ds:
        s = cb.chay_mot(S)
        kq[S] = {"engine": so_engine(S), "sai_so_moi": {k: s.get(k) for k in (
            "sai_so_dau_clip_s", "sai_so_dau_vung_s", "sai_so_cuoi_s", "precision_giay", "recall_giay")}}
        print(S, "engine", json.dumps({k: kq[S]["engine"][k] for k in (
            "dong_trung", "dong_loai_trung", "dong_tho_trung", "so_dong_tho", "nhom_sau_merge_trung",
            "bao_cao_v2_trung", "thoi_gian_quet_s")}, ensure_ascii=False), flush=True)
    # Cách C trên kết quả engine MỚI (đọc thư mục chạy lại), so với cach_c/tong_hop.json
    cc.BO_THU = RA
    cu_c = _json(os.path.join(r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_c", "tong_hop.json"))["kich_ban"]
    ts = dict(td.THAM_SO_MAC_DINH)
    for S in ds:
        nen = {"duong": {}, "ngoai_doan_that": {}}
        kb = cc.kich_ban(S, ts, os.path.join(RA, "_cach_c"), nen)
        moi = [[x["video_tu"], x["video_den"], x["clip_tu"], x["clip_den"]] for dg in kb["dong"]
               if dg["loai"] == "chap_nhan" for x in dg["doan"]]
        cu = [[x["video_tu"], x["video_den"], x["clip_tu"], x["clip_den"]] for dg in cu_c[S]["tung_dong"]
              if dg["loai"] == "chap_nhan" for x in dg["doan"]]
        kq[S]["cach_c"] = {"doan_moi": moi, "doan_cu": cu, "trung": moi == cu,
                           "lech_lon_nhat_s": max((abs(a - b) for x, y in zip(moi, cu) for a, b in zip(x, y)),
                                                  default=None) if len(moi) == len(cu) else "khác số đoạn",
                           "pr_moi": [kb["danh_gia"]["precision_giay"], kb["danh_gia"]["recall_giay"]],
                           "pr_cu": [cu_c[S]["danh_gia"]["precision_giay"], cu_c[S]["danh_gia"]["recall_giay"]],
                           "thoi_gian_moi_s": kb["thoi_gian_tong_s"], "thoi_gian_cu_s": cu_c[S]["thoi_gian_tong_s"]}
        print(S, "cach_c", json.dumps(kq[S]["cach_c"], ensure_ascii=False), flush=True)
    with open(os.path.join(RA, "so_sanh_chay_lai.json"), "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
