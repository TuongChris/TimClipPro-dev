# -*- coding: utf-8 -*-
"""Phản biện đo lường — CHẤM LẠI ĐỘC LẬP kết quả đã báo của engine (bo_thu), Cách B, Cách C.

Không dùng danh_gia.py (hàm chấm của bo_thu, Cách B và Cách C cùng dùng) — kiểm xem phép chấm có vòng vo/sai không.
Cách chấm: rải mọi khoảng lên LƯỚI 1 ms của trục video (mảng bool), đếm mẫu: precision = |báo ∩ thật| / |báo|,
recall = |báo ∩ thật| / |thật|; mép: mỗi đoạn thật lấy đoạn báo GIAO DÀI NHẤT. Sự thật = đoạn ĐO TỪ AUDIO
(su_that_doc_lap.json: nguyên mẫu → tới 1 mẫu; tương quan → giả thuyết đã kiểm ánh xạ), không đọc su_that.json để chấm
trừ khi audio không đo được mép chính xác (Opus, nhạc đè, atempo: ánh xạ đã kiểm ±2,4 ms, mép theo cách dựng).

Hàm thuần dùng lại được cho ca khó (ca_kho.py). Tự kiểm: ``python cham_doc_lap.py --tu-kiem``.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
BUOC = 0.001
GOC = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay"
RA = os.path.join(GOC, "phan_bien_do_luong")


def luoi(khoang, dur: float) -> np.ndarray:
    m = np.zeros(int(np.ceil(dur / BUOC)) + 2, bool)
    for a, b in khoang:
        i0, i1 = int(round(max(a, 0.0) / BUOC)), int(round(min(b, dur) / BUOC))
        if i1 > i0:
            m[i0:i1] = True
    return m


def pr(bao, that, dur: float) -> tuple:
    b, t = luoi(bao, dur), luoi(that, dur)
    g = int((b & t).sum())
    return (round(g / b.sum(), 4) if b.sum() else None, round(g / t.sum(), 4) if t.sum() else None)


def mep(bao: list, that: list) -> list:
    """bao/that: list dict {video_tu, video_den, (clip_tu, clip_den)}. Trả lỗi từng đoạn thật (None = không thấy)."""
    ra = []
    for t in that:
        def giao(x, t=t):
            return max(0.0, min(x["video_den"], t["video_den"]) - max(x["video_tu"], t["video_tu"]))
        tot = max(bao, key=giao, default=None)
        if tot is None or giao(tot) <= 0:
            ra.append(None)
            continue
        e = {"dau": round(tot["video_tu"] - t["video_tu"], 3), "cuoi": round(tot["video_den"] - t["video_den"], 3)}
        if "clip_tu" in tot and "clip_tu" in t:
            e["clip_dau"] = round(tot["clip_tu"] - t["clip_tu"], 3)
            e["clip_cuoi"] = round(tot["clip_den"] - t["clip_den"], 3)
        ra.append(e)
    return ra


def _json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def su_that_do_duoc(S: str, doc_lap: dict, st: dict) -> list:
    r = doc_lap.get(S, {})
    if r.get("cach") == "mau_trung_khop" and r.get("doan_do_duoc"):
        return [{k: x[k] for k in ("video_tu", "video_den", "clip_tu", "clip_den", "he_so")} for x in r["doan_do_duoc"]]
    return sorted(st["doan"], key=lambda x: x["video_tu"])


def cham_lai_tat_ca() -> dict:
    doc_lap = _json(os.path.join(RA, "su_that_doc_lap.json"))
    cc = _json(os.path.join(GOC, "cach_c", "tong_hop.json"))["kich_ban"]
    ra = {}
    for S in ["S1", "S2", "S3", "S4", "S4b", "S5", "S6", "S6b", "S7", "S7b", "S7c", "S8", "S9", "X1", "X2", "X3"]:
        d = os.path.join(GOC, "cach_c", "them", S) if S.startswith("X") else os.path.join(GOC, "bo_thu", S)
        st, ke = _json(os.path.join(d, "su_that.json")), _json(os.path.join(d, "ket_qua_engine.json"))
        dur = float(ke["duration_s"])
        that = su_that_do_duoc(S, doc_lap, st)
        tk = [(x["video_tu"], x["video_den"]) for x in that]
        row = {"su_that": [[round(x["video_tu"], 4), round(x["video_den"], 4)] for x in that]}
        # engine — so với sai_so.json (bo_thu) hoặc cach_c/them/<X>/sai_so.json
        dong = ke["dong_cho_clip"]["matches"]
        ss = _json(os.path.join(d, "sai_so.json"))
        p1, r1 = pr([(m["start_s"], m["end_s"]) for m in dong], tk, dur)
        p2, r2 = pr([(m["vung_khop_s"], m["end_s"]) for m in dong], tk, dur)
        row["engine"] = {"toi": [p1, r1, p2, r2],
                         "da_bao": [ss.get("precision_giay"), ss.get("recall_giay"),
                                    ss.get("precision_giay_tu_vung_khop"), ss.get("recall_giay_tu_vung_khop")]}
        # Cách C
        if S in cc:
            doan = [x for dg in cc[S]["tung_dong"] if dg["loai"] == "chap_nhan" for x in dg["doan"]]
            pc, rc = pr([(x["video_tu"], x["video_den"]) for x in doan], tk, dur)
            e = mep(doan, that)
            da = cc[S]["danh_gia"]
            row["cach_c"] = {"toi": [pc, rc], "da_bao": [da["precision_giay"], da["recall_giay"]],
                             "mep_toi": e,
                             "mep_da_bao": [{"dau": x["loi_video_dau_s"], "cuoi": x["loi_video_cuoi_s"],
                                             "clip_dau": x["loi_clip_dau_s"], "clip_cuoi": x["loi_clip_cuoi_s"]}
                                            for x in da["tung_doan_that"]],
                             "cach_tim_mep": [x["cach_tim_mep"] for x in doan]}
        # Cách B
        pb = os.path.join(GOC, "cach_b", S, "ket_qua_cach_b.json")
        if os.path.exists(pb):
            kb = _json(pb)
            doan = [x for r in kb["dong"] for x in r["doan"]]
            pbb, rbb = pr([(x["video_tu"], x["video_den"]) for x in doan], tk, dur)
            row["cach_b"] = {"toi": [pbb, rbb], "da_bao": [kb["cham"]["precision_giay"], kb["cham"]["recall_giay"]],
                             "mep_toi": mep(doan, that),
                             "mep_da_bao": [{"dau": x.get("sai_so_dau_s"), "cuoi": x.get("sai_so_cuoi_s")}
                                            for x in kb["cham"]["tung_doan_that"]],
                             "cach_tim_mep": [[x["cach_dau"], x["cach_cuoi"]] for x in doan]}
        ra[S] = row
    # độ lệch lớn nhất giữa phép chấm của tôi và số đã báo
    lech = {"engine": 0.0, "cach_c_pr": 0.0, "cach_c_mep": 0.0, "cach_b_pr": 0.0, "cach_b_mep": 0.0}
    for S, row in ra.items():
        lech["engine"] = max([lech["engine"]] + [abs(a - b) for a, b in zip(*[row["engine"][k] for k in ("toi", "da_bao")])
                                                 if a is not None and b is not None])
        for ten in ("cach_c", "cach_b"):
            if ten in row:
                lech[f"{ten}_pr"] = max([lech[f"{ten}_pr"]] + [abs(a - b) for a, b in zip(row[ten]["toi"], row[ten]["da_bao"])
                                                              if a is not None and b is not None])
                for x, y in zip(row[ten]["mep_toi"], row[ten]["mep_da_bao"]):
                    if x and y:
                        lech[f"{ten}_mep"] = max(lech[f"{ten}_mep"], abs(x["dau"] - y["dau"]), abs(x["cuoi"] - y["cuoi"]))
    return {"kich_ban": ra, "lech_lon_nhat_giua_toi_va_da_bao": lech}


def _tu_kiem() -> None:
    assert pr([(0, 10)], [(5, 15)], 20) == (0.5, 0.5)
    assert pr([(0, 10), (5, 12)], [(0, 12)], 20) == (1.0, 1.0)
    assert pr([], [(0, 1)], 5) == (None, 0.0)
    assert mep([{"video_tu": 1.0, "video_den": 9.0}], [{"video_tu": 0.0, "video_den": 10.0}]) == [{"dau": 1.0, "cuoi": -1.0}]
    assert mep([], [{"video_tu": 0.0, "video_den": 10.0}]) == [None]
    print("cham_doc_lap: tự kiểm ĐẠT")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _tu_kiem()
    if "--tu-kiem" not in sys.argv:
        kq = cham_lai_tat_ca()
        with open(os.path.join(RA, "cham_lai_doc_lap.json"), "w", encoding="utf-8") as f:
            json.dump(kq, f, ensure_ascii=False, indent=1)
        print(json.dumps(kq["lech_lon_nhat_giua_toi_va_da_bao"], ensure_ascii=False))
        for S, row in kq["kich_ban"].items():
            print(S, "engine", row["engine"]["toi"], "vs", row["engine"]["da_bao"],
                  "| C", row.get("cach_c", {}).get("toi"), row.get("cach_c", {}).get("mep_toi"),
                  "| B", row.get("cach_b", {}).get("toi"), row.get("cach_b", {}).get("mep_toi"))
