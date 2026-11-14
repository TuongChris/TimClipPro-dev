# -*- coding: utf-8 -*-
"""Phản biện đo lường — chạy Cách B (dòng thời gian hash) trên CÁC CA KHÓ đã chạy engine (ca_kho.py), để biết lỗi của
Cách C ở ca khó là riêng của Cách C hay chung cho kiểu «tinh chỉnh sau chấp nhận».

Theo đúng quy trình của chay_cach_b.main (import, không sửa): pha 1 (hồ sơ, nền cùng video, tự giống) → ngưỡng theo dòng
(+ luật «tự lặp» so với ngưỡng chung, ngưỡng chung = nền S0 + nền các ca khó) → pha 3 (đoạn + mép). Chấm bằng
cham_doc_lap (lưới 1 ms).
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B -X utf8 ca_kho_cach_b.py [H1b H3 H4 ...]
"""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
GOC_CC = r"C:\Dev\pc2_test_tools\khop_tung_giay"
sys.path.insert(0, os.path.join(GOC_CC, "bo_thu"))
sys.path.insert(0, os.path.join(GOC_CC, "cach_b"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chay_cach_b as cbb  # noqa: E402  (kiểm môi trường chặn mạng khi import)
import cham_doc_lap as ch  # noqa: E402

RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_do_luong\ca_kho"


def _json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ds = sys.argv[1:] or ["H1a", "H1b", "H1c", "H2a", "H2b", "H3", "H4"]
    tam = os.path.join(RA, "_tam_cach_b")
    os.makedirs(tam, exist_ok=True)
    s0 = cbb.nen_s0(tam)                     # BO_THU còn trỏ bo_thu gốc: nền S0 như Cách B đã dùng
    cbb.BO_THU = RA                          # từ đây đọc video của ca khó
    du_lieu = {}
    for S in ds:
        st, ket = (_json(os.path.join(RA, S, x)) for x in ("su_that.json", "ket_qua_engine.json"))
        dong = ket["dong_cho_clip"]["matches"] + ket["dong_clip_khac"]["matches"]
        x = du_lieu[S] = {"st": st, "ket": ket, "dong": []}
        for i, m in enumerate(dong):
            d = cbb.pha1_dong(S, i, m, ket, st, "de_xuat", tam)
            d["nen"] = cbb.nen_cung_video(d, ket, st, tam)
            d["tu_giong"] = cbb.tu_giong(d)
            x["dong"].append(d)
        print(f"[pha 1] {S}: {len(dong)} dòng", flush=True)
    tat_ca_nen = [p for x in du_lieu.values() for d in x["dong"] for p in d["nen"]["ho_so"]] + s0
    kq = _json(os.path.join(RA, "tong_hop_ca_kho.json")) if os.path.exists(os.path.join(RA, "tong_hop_ca_kho.json")) \
        else {}
    for S, x in du_lieu.items():
        ra_dong = []
        for d in x["dong"]:
            w = d["ts"]["w"]
            chung = cbb.nguong_tu_nen(tat_ca_nen, w)
            ng = cbb.nguong_tu_nen(d["nen"]["ho_so"], w)
            if not ng["so_ho_so_nen"]:
                ng = dict(chung)
            tg = [p for p in d["tu_giong"] if not p["cham_can_chinh_that"]]
            muc_lap = max((cbb._thong_ke(p["_n"], p["_k"], w).get("max_trung_vi") or 0.0 for p in tg), default=0.0)
            ng["muc_tu_lap"], ng["tu_lap"] = muc_lap, bool(muc_lap >= cbb.TU_LAP)
            if ng["tu_lap"]:
                ng["nguong_cao"] = max(ng["nguong_cao"], chung["nguong_cao"])
                ng["nguong_thap"] = max(ng["nguong_thap"], chung["nguong_thap"])
            r = cbb.pha3_dong(d, ng, d["ts"])
            ra_dong.append(r)
        st = x["st"]
        that = sorted(st["doan"], key=lambda z: z["video_tu"])
        doan = [z for r in ra_dong for z in r["doan"]]
        dur = float(x["ket"]["duration_s"])
        cham = {"doan": [[z["video_tu"], z["video_den"], z["clip_tu"], z["clip_den"], z["cach_dau"], z["cach_cuoi"]]
                         for z in doan],
                "pr": ch.pr([(z["video_tu"], z["video_den"]) for z in doan], [(z["video_tu"], z["video_den"])
                                                                                for z in that], dur),
                "mep": ch.mep(doan, that),
                "tung_dong": [{"engine_start_s": r["engine"]["start_s"], "A_moi": r["can_chinh_tim_duoc"]["A_moi"],
                               "k_moi": r["can_chinh_tim_duoc"]["k_moi"], "w": r["tham_so"]["w"],
                               "nguong": [r["tham_so"]["nguong_cao"], r["tham_so"]["nguong_thap"]],
                               "tu_lap": r["tham_so"]["tu_lap"], "so_doan": len(r["doan"]),
                               "giu_nguyen_engine": r["giu_nguyen_engine"],
                               "thoi_gian_s": r["thoi_gian_s"].get("tong")} for r in ra_dong]}
        if "chu_ky_vong_lap_s" in st:
            cham["lech_clip_theo_chu_ky"] = [None if e is None else round(e["clip_dau"] / st["chu_ky_vong_lap_s"], 3)
                                             for e in cham["mep"]]
        kq.setdefault(S, {})["cach_b"] = cham
        print(f"[{S}] Cách B đoạn {cham['doan']} | P/R {cham['pr']} | mép {cham['mep']} | {cham['tung_dong']}",
              flush=True)
    with open(os.path.join(RA, "tong_hop_ca_kho.json"), "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1, default=str)
    shutil.rmtree(tam, ignore_errors=True)


if __name__ == "__main__":
    main()
