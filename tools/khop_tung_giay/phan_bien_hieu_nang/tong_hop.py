# -*- coding: utf-8 -*-
"""Phản biện HIỆU NĂNG (14/11/2026): gom số đo của do_tinh_chinh.py + chay_engine.py + mốc nghiệm thu thật 13/10 →
tong_hop.json. Mô hình tuyến tính khớp từ số ĐO (thang_do V0 dùng trọn 10/30/60/119 phút); mọi số suy từ mô hình mang
khoá «uoc_luong». Chạy: <venv python> -B -X utf8 tong_hop.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

GOC = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_hieu_nang"
NGHIEM_THU = r"C:\Dev\pc2_test_runs\2026-10-13_tai_nhanh\pilot_nghiem_thu.json"
BUOC = ("giai_ma_clip_s", "dac_trung_clip_s", "giai_ma_video_s", "dac_trung_video_s", "tinh_chinh_s")
NEN_WSET_MB = 30.0          # python + numpy + tuong_dong sau import (đo: 28–32 MB)


def _doc(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _co(p):
    return os.path.exists(p)


def mo_hinh(thang: list) -> dict:
    """Khớp tuyến tính theo giây clip (bước clip + tinh_chinh) và giây video (bước video) trên các ca dùng trọn V0."""
    ca = [r for r in thang if r.get("bien_the") == "V0" and r["ca"].startswith("tron_") and "loi" not in r]
    Lc = np.array([r["giay_clip_xu_ly"] for r in ca])
    Lv = np.array([r["giay_video_xu_ly"] for r in ca])
    ra = {"so_diem": len(ca), "L_clip_s": Lc.tolist()}
    for b in BUOC:
        x = Lv if "video" in b else Lc
        y = np.array([r["thoi_gian"][b] for r in ca])
        k, c = np.polyfit(x, y, 1)
        ra[b] = {"ms_moi_giay": round(1000 * k, 3), "co_dinh_s": round(c, 3)}
    w = np.array([r["bo_nho_sau"]["peak_wset_mb"] - NEN_WSET_MB for r in ca])
    x = Lc + Lv
    k, c = np.polyfit(x, w, 1)
    ra["dinh_wset_tang_them"] = {"mb_moi_giay_clip_cong_video": round(k, 4), "co_dinh_mb": round(c, 1)}
    return ra


def mo_hinh_v1t(thang: list) -> dict | None:
    """V1t (dòng chảy + float32): thời gian và đỉnh RAM tuyến tính theo (giây clip + giây video) đã xử lý."""
    ca = [r for r in thang if r.get("bien_the") == "V1t" and r["ca"].startswith("tron_") and "loi" not in r]
    if len(ca) < 2:
        return None
    x = np.array([r["giay_clip_xu_ly"] + r["giay_video_xu_ly"] for r in ca])
    kt, ct = np.polyfit(x, [r["thoi_gian"]["tong_s"] for r in ca], 1)
    kw, cw = np.polyfit(x, [r["bo_nho_sau"]["peak_wset_mb"] for r in ca], 1)
    return {"so_diem": len(ca), "ms_moi_giay_clip_cong_video": round(1000 * kt, 3), "co_dinh_s": round(ct, 3),
            "mb_moi_giay_clip_cong_video": round(kw, 4), "co_dinh_mb": round(cw, 1)}


def du_doan(mh: dict, Lc: float, Lv: float, bo_giai_ma_video: bool = False) -> dict:
    t = 0.0
    for b in BUOC:
        if bo_giai_ma_video and b == "giai_ma_video_s":
            continue
        x = Lv if "video" in b else Lc
        t += mh[b]["ms_moi_giay"] / 1000 * x + mh[b]["co_dinh_s"]
    w = mh["dinh_wset_tang_them"]["mb_moi_giay_clip_cong_video"] * (Lc + Lv) + mh["dinh_wset_tang_them"]["co_dinh_mb"]
    return {"giay": round(t, 1), "dinh_ram_mb": round(w + NEN_WSET_MB)}


def cua_so_v1(S: float) -> tuple:
    """Độ dài cửa sổ clip/video của V1 cho lõi engine dài S giây (k = 1), như do_tinh_chinh.cua_so_*."""
    lc = S + 2 * (30 + 0.10 * S)
    return lc, lc + 2 * (2 + 0.045 * lc + 42)


def cua_so_v0(L: float, dur: float) -> tuple:
    return L, min(dur, L + 2 * (2 + 0.045 * L + 42))


def tom_lo(p: str) -> dict:
    lo = _doc(p)
    ra = {"tap": lo["tap"], "so_ket_qua": lo["so_ket_qua"], "thoi_gian_quet_engine_s": lo["thoi_gian_quet_engine_s"],
          "bien_the": {}, "tung_ket_qua": []}
    for bt in ("V0", "V1", "V2", "V1t"):
        rs = [d["do"][bt] for d in lo["ket_qua"] if bt in d["do"] and "loi" not in d["do"][bt]]
        if not rs:
            continue
        tg = [r["thoi_gian"]["tong_s"] for r in rs]
        ra["bien_the"][bt] = {
            "tong_giay": round(sum(tg), 2), "moi_ket_qua_min_max_s": [min(tg), max(tg)],
            "dinh_wset_max_mb": max(r["bo_nho_sau"]["peak_wset_mb"] for r in rs),
            "giai_ma_video_tong_s": round(sum(r["thoi_gian"].get("giai_ma_video_s", 0.0) for r in rs), 2),  # V1t gộp
            "dinh_commit_max_mb": max(r["bo_nho_sau"]["peak_commit_mb"] for r in rs),
            "so_mo_rong": sum(r["mo_rong"] for r in rs), "so_tuong_phan_thap": sum(r["tuong_phan_thap"] for r in rs),
            "so_khong_ra_doan": sum(not r["doan"] for r in rs),
            "ty_le_so_voi_quet": round(sum(tg) / lo["thoi_gian_quet_engine_s"], 4)}
    for d in lo["ket_qua"]:
        m = d["match"]
        dong = {"clip": m["clip"], "vung_khop_s": m["vung_khop_s"], "end_s": m["end_s"], "trong_top_n": d["trong_top_n"]}
        for bt, r in d["do"].items():
            if "loi" in r:
                dong[bt] = {"loi": r["loi"][-200:]}
                continue
            dong[bt] = {"tong_s": r["thoi_gian"]["tong_s"], "dinh_wset_mb": r["bo_nho_sau"]["peak_wset_mb"],
                        "giay_clip": r["giay_clip_xu_ly"], "giay_video": r["giay_video_xu_ly"],
                        "doan": [[x["video_tu"], x["video_den"]] for x in r["doan"]],
                        "loi_mep": r.get("cham_diem", {}).get("loi_mep"),
                        "P": r.get("cham_diem", {}).get("precision_giay"), "R": r.get("cham_diem", {}).get("recall_giay")}
        if "V0" in d["do"] and "loi" not in d["do"]["V0"]:
            for bt in ("V1", "V2", "V1t"):
                r0, r1 = d["do"]["V0"], d["do"].get(bt)
                if r1 and "loi" not in r1 and len(r0["doan"]) == len(r1["doan"]):
                    dong[f"lech_mep_{bt}_vs_V0_s"] = max(
                        [max(abs(a["video_tu"] - b["video_tu"]), abs(a["video_den"] - b["video_den"]))
                         for a, b in zip(r0["doan"], r1["doan"])], default=0.0)
        ra["tung_ket_qua"].append(dong)
    return ra


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ra: dict = {}
    nt = _doc(NGHIEM_THU)["cong_doan"]
    ra["nghiem_thu_that_13_10"] = {
        "tai_s": nt["tai"]["giay"], "kiem_am_thanh_s": nt["kiem_am_thanh"]["giay"], "cat_khuc_s": nt["cat_khuc"]["giay"],
        "so_khop_s": nt["so_khop"]["giay"], "tu_bat_dau_tai_toi_xong_s": 171.0,
        "ghi_chu": "video 66 giờ chỉ quét 3 giờ đầu, kho SML 779 clip, 5 kết quả; 16:02:25 → 16:05:16 (pilot_nghiem_thu.json)"}
    thang = []
    for ten in sorted(os.listdir(os.path.join(GOC, "thang_do"))):
        if ten.startswith("thang_do_") and ten.endswith(".json"):
            thang += _doc(os.path.join(GOC, "thang_do", ten))
    ra["thang_do"] = [{k: r.get(k) for k in ("ca", "bien_the", "thoi_gian", "giay_clip_xu_ly", "giay_video_xu_ly",
                                              "bo_nho_sau", "loi_mep", "precision_recall", "mo_rong")} for r in thang]
    mh = mo_hinh(thang)
    ra["mo_hinh_tuyen_tinh_V0"] = mh
    mt = mo_hinh_v1t(thang)
    ra["mo_hinh_tuyen_tinh_V1t"] = mt
    for ten in sorted(os.listdir(GOC)):
        d = os.path.join(GOC, ten)
        if ten.startswith("quet_") and _co(os.path.join(d, "ket_qua.json")):
            kq = _doc(os.path.join(d, "ket_qua.json"))
            ra[ten] = {"quet": {k: kq[k] for k in ("thoi_gian_quet_s", "cat_khuc_s", "khop_s", "merge_s", "so_dat_nguong",
                                                   "cau_hinh", "duration_s")},
                       "so_matches": len(kq["matches"]), "so_ung_vien_dat": len(kq["ung_vien_dat"])}
            for tap in ("matches", "ung_vien_dat"):
                p = os.path.join(d, f"tinh_chinh_{tap}.json")
                if _co(p):
                    ra[ten][f"tinh_chinh_{tap}"] = tom_lo(p)
            p = os.path.join(d, "cuon_moc.json")
            if _co(p):
                ra[ten]["cuon_moc_16bit"] = [
                    {"chon": x["chon"], "clip": x["match"]["clip"], "start_s": x["match"]["start_s"],
                     "vung_khop_s": x["match"]["vung_khop_s"], "end_s": x["match"]["end_s"],
                     "clip_offset_s": x["match"]["clip_offset_s"], "hashes": x["match"]["hashes"],
                     "neo": [{"j": n["j"], "tong_s": (n.get("thoi_gian") or {}).get("tong_s"),
                              "tuong_phan_thap": n.get("tuong_phan_thap"), "so_giay_bam": n.get("so_giay_bam"),
                              "doan": [[d_["video_tu"], d_["video_den"], d_["clip_tu"], d_["clip_den"]]
                                       for d_ in (n.get("doan") or [])],
                              "loi_mep": (n.get("cham_diem") or {}).get("loi_mep")} for n in x["neo"]]}
                    for x in _doc(p)]
    # ca xấu nhất — ƯỚC LƯỢNG từ mô hình đo được (video được quét dur giây)
    uoc = []
    for ten_ca, L, S, dur in (("clip 10 phút dùng trọn", 600, 540, 10800), ("clip 2 giờ dùng trọn", 7140, 6426, 10800),
                              ("5 phút giữa clip 2 giờ", 7140, 270, 10800),
                              ("kho D-34: 5 phút giữa clip 13 giờ, quét 3 giờ", 46800, 270, 10800),
                              ("kho D-34: clip 13 giờ dùng 8 giờ, quét 30 giờ", 46800, 25920, 108000),
                              ("kho D-34: clip 13 giờ dùng trọn, quét 30 giờ", 46800, 42120, 108000)):
        v0 = du_doan(mh, *cua_so_v0(L, dur))
        lc, lv = cua_so_v1(S)
        lc, lv = min(lc, L), min(lv, dur)
        dong = {"ca": ten_ca, "L_clip_s": L, "loi_engine_s": S, "V0": v0, "V1": du_doan(mh, lc, lv),
                "V2": du_doan(mh, lc, lv, bo_giai_ma_video=True)}
        if mt:
            dong["V1t"] = {"giay": round(mt["ms_moi_giay_clip_cong_video"] / 1000 * (lc + lv) + mt["co_dinh_s"], 1),
                           "dinh_ram_mb": round(mt["mb_moi_giay_clip_cong_video"] * (lc + lv) + mt["co_dinh_mb"])}
        uoc.append(dong)
    ra["uoc_luong_moi_ket_qua"] = uoc
    with open(os.path.join(GOC, "tong_hop.json"), "w", encoding="utf-8") as f:
        json.dump(ra, f, ensure_ascii=False, indent=1)
    print(json.dumps({"mo_hinh_V0": mh, "mo_hinh_V1t": mt, "uoc_luong_moi_ket_qua": uoc}, ensure_ascii=False))
    for k, v in ra.items():
        if k.startswith("quet_"):
            print(k, json.dumps({x: v[x] for x in v if not x.startswith("tinh_chinh")}, ensure_ascii=False))
            for tap in ("tinh_chinh_matches", "tinh_chinh_ung_vien_dat"):
                if tap in v:
                    print("  ", tap, json.dumps(v[tap]["bien_the"], ensure_ascii=False))


if __name__ == "__main__":
    main()
