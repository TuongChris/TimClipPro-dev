# -*- coding: utf-8 -*-
"""Chạy Cách C (tuong_dong.py) trên bộ thử 15 kịch bản + 3 kịch bản thêm, và đo đường nền (14/11/2026).

Chỉ ĐỌC bộ thử ``bo_thu`` (audio giả lập + kết quả engine của bước trước) và ``cach_c/them`` (kich_ban_them.py);
không chạy engine, không gọi audfprint, không đụng mã sản phẩm. Ghi vào ``--ra``:
  <S>/ket_qua_cach_c.json  — từng dòng engine: hồ sơ từng giây, ngưỡng tại chỗ, các đoạn dùng thật, thời gian.
  duong_nen.json           — tương đồng từng giây ở chỗ KHÔNG có clip: video không liên quan, căn chỉnh lệch, đề xuất
                             sai của audfprint ở S0; «bóng» nhạc lặp tách riêng; kết quả tinh chỉnh trên các dòng giả đó.
  tong_hop.json            — số liệu cả bộ.
Chạy (Git Bash, ~3–5 phút):
  cd /c/Dev/pc2_test_tools/khop_tung_giay/cach_c
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \
      -B -X utf8 chay_cach_c.py [--nguong 0.5] [--ra <thư mục>] [S1 S4 ...]
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

THU_MUC = os.path.dirname(os.path.abspath(__file__))
BO_THU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"
THEM = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_c\them"
RA_MAC_DINH = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_c"
CHAN_MANG = r"C:\Dev\Tool_Quet\tools\test\chan_mang"
THU_TU = ["S1", "S2", "S3", "S4", "S4b", "S5", "S5b", "S6", "S6b", "S7", "S7b", "S7c", "S8", "S9", "S0",
          "X1", "X2", "X3"]
LECH = (6.1, -13.7, 29.3, -52.9)                    # căn chỉnh lệch tuỳ ý (giây) cho đường nền toàn cục
O_NHIP = 240.0 / 113.0                               # ô nhịp của am_thanh_lap
BONG = {"S6": (O_NHIP, -O_NHIP, 2 * O_NHIP, 4 * O_NHIP),
        "S6b": (O_NHIP, -O_NHIP, 4 * O_NHIP, 8 * O_NHIP, -8 * O_NHIP),
        "X3": (O_NHIP, -O_NHIP, 4 * O_NHIP)}
NHAC_CO_NHIP = {"S6", "S6b", "X3", "goc_S6.wav", "goc_S6b.wav"}

sc = sys.modules.get("sitecustomize")
if sc is None or os.path.normcase(os.path.dirname(os.path.abspath(sc.__file__))) != os.path.normcase(CHAN_MANG):
    raise SystemExit(f"Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH={CHAN_MANG}")
if shutil.which("ffmpeg") is None:
    raise SystemExit("Cần ffmpeg trong PATH.")
sys.path.insert(0, THU_MUC)
sys.path.insert(0, os.path.join(os.path.dirname(THU_MUC), "bo_thu"))
import danh_gia  # noqa: E402  (bo_thu — chỉ import hàm thuần)
import tuong_dong as td  # noqa: E402


def _json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _ghi(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def _thu_muc(S: str) -> str:
    return os.path.join(THEM if S.startswith("X") else BO_THU, S)


def _an_toan(p: str) -> str:
    p = os.path.abspath(p)
    if not any(os.path.normcase(p).startswith(os.path.normcase(g)) for g in (BO_THU, THEM)):
        raise SystemExit(f"Đường dẫn ngoài bộ thử: {p}")      # chỉ audio giả lập của bộ thử
    return p


def vung_video(m: dict, do_dai_clip: float, dur: float) -> tuple:
    """Đoạn video cần giải mã cho một dòng: [giây 0 clip − biên, cuối clip + biên]; biên đủ cho độ trôi ±4,5% và
    cho các đường lệch của đường nền tại chỗ."""
    k0 = td.he_so_tu_engine(m)
    t0 = float(m["vung_khop_s"]) - float(m["clip_offset_s"]) / k0
    bien = 2.0 + 0.045 * do_dai_clip + td.BIEN_NEN_S
    tu = max(0.0, t0 - bien)
    return tu, min(dur, t0 + do_dai_clip / k0 + bien) - tu


def nhan_giay(n: int, t_video: float, doan: list) -> str:
    """'co' = giây clip n THẬT SỰ nằm ở t_video (±0,35 s); 'bien' = miếng 3 s vắt qua mép đoạn thật; 'khong' = không."""
    for d in doan:
        if d["clip_tu"] - 2 < n < d["clip_den"] + 1:
            t_dung = d["video_tu"] + (n - d["clip_tu"]) / d["he_so"]
            if abs(t_video - t_dung) <= 0.35:
                return "co" if (d["clip_tu"] + 1 <= n and n + 2 <= d["clip_den"]) else "bien"
    return "khong"


def phan_vi(x) -> dict:
    x = np.asarray(x, dtype=float)
    if not len(x):
        return {"n": 0}
    pv = lambda q: round(float(np.percentile(x, q)), 1)  # noqa: E731
    return {"n": int(len(x)), "min": round(float(x.min()), 1), "p1": pv(1), "p5": pv(5), "p50": pv(50),
            "p95": pv(95), "p99": pv(99), "p99_9": pv(99.9), "max": round(float(x.max()), 1)}


def kich_ban(S: str, ts: dict, ra: str, nen: dict) -> dict:
    d = _thu_muc(S)
    st, ke = _json(os.path.join(d, "su_that.json")), _json(os.path.join(d, "ket_qua_engine.json"))
    ss = _json(os.path.join(d, "sai_so.json"))
    video = _an_toan(os.path.join(d, st["video"]))
    dur = float(ke["duration_s"])
    doan_that = sorted(st["doan"], key=lambda x: x["video_tu"])
    dong = [("chap_nhan", m) for m in ke["dong_cho_clip"]["matches"]]
    if S == "S5b":                     # chỉ để THAM KHẢO: dòng bị loại (bước tinh chỉnh thật không chạy trên nó)
        dong += [("bi_loai_tham_khao", m) for m in ke["dong_cho_clip"]["matches_loai"]]
    ra_kb = {"kich_ban": S, "mo_ta": st["mo_ta"], "doan_that": doan_that, "dong": [],
             "sai_so_engine": {x: ss.get(x) for x in ("sai_so_dau_clip_s", "sai_so_dau_vung_s", "sai_so_cuoi_s",
                                                     "precision_giay", "recall_giay")}}
    bo_nho_clip: dict = {}
    for loai, m in dong:
        clip = _an_toan(m["duong_dan_kho"])
        tg = {}
        t = time.perf_counter()
        if clip not in bo_nho_clip:
            xc, _ = td.doc_pcm(clip)
            tg["giai_ma_clip_s"] = round(time.perf_counter() - t, 3)
            t = time.perf_counter()
            bo_nho_clip[clip] = (td.log_mel(xc), round(len(xc) / td.SR, 3))
            tg["dac_trung_clip_s"] = round(time.perf_counter() - t, 3)
        C, do_dai_clip = bo_nho_clip[clip]
        tu, dai = vung_video(m, do_dai_clip, dur)
        t = time.perf_counter()
        xv, T0 = td.doc_pcm(video, tu, dai)
        tg["giai_ma_vung_video_s"] = round(time.perf_counter() - t, 3)
        t = time.perf_counter()
        V = td.log_mel(xv)
        tg["dac_trung_video_s"] = round(time.perf_counter() - t, 3)
        t = time.perf_counter()
        kq = td.tinh_chinh(C, V, T0, do_dai_clip, m, ts, video_den=dur)
        tg["tinh_chinh_s"] = round(time.perf_counter() - t, 3)
        tg["tong_s"] = round(sum(tg.values()), 3)
        nhan = {"co": [], "khong": [], "bien": []}
        for h in kq["ho_so"]:
            if h is not None:
                nhan[nhan_giay(h[0], h[2], doan_that)].append(h[1])
        if loai == "chap_nhan":
            nen["duong"].setdefault(S, []).extend(nhan["co"])
            nen["ngoai_doan_that"].setdefault(S, []).extend(nhan["khong"])
        else:
            nen["duong"].setdefault(S + "_dong_bi_loai", []).extend(nhan["co"])
        nd = kq["nguong_dung"]
        ra_kb["dong"].append({
            "loai": loai, "engine": {x: m[x] for x in ("start_s", "vung_khop_s", "end_s", "clip_offset_s",
                                                       "matched_s", "hashes")},
            "vung_video_giai_ma": [round(T0, 3), round(T0 + len(xv) / td.SR, 3)], "do_dai_clip_s": do_dai_clip,
            "thoi_gian": tg, "phan_bo_theo_su_that": {x: phan_vi(v) for x, v in nhan.items()},
            "giay_sai_tren_nguong": sum(v >= nd for v in nhan["khong"]),
            "giay_dung_duoi_nguong": sum(v < nd for v in nhan["co"]), **kq})
    doan_tim = sorted([x for dg in ra_kb["dong"] if dg["loai"] == "chap_nhan" for x in dg["doan"]],
                      key=lambda x: x["video_tu"])
    ra_kb["danh_gia"] = danh_gia_doan(doan_tim, doan_that)
    tk = [x for dg in ra_kb["dong"] if dg["loai"] != "chap_nhan" for x in dg["doan"]]
    if any(dg["loai"] != "chap_nhan" for dg in ra_kb["dong"]):
        ra_kb["danh_gia_dong_bi_loai_tham_khao"] = danh_gia_doan(sorted(tk, key=lambda x: x["video_tu"]), doan_that)
    ra_kb["thoi_gian_tong_s"] = round(sum(dg["thoi_gian"]["tong_s"] for dg in ra_kb["dong"]
                                          if dg["loai"] == "chap_nhan"), 3)
    _ghi(os.path.join(ra, S, "ket_qua_cach_c.json"), ra_kb)
    return ra_kb


def danh_gia_doan(doan_tim: list, doan_that: list) -> dict:
    that = [(x["video_tu"], x["video_den"]) for x in doan_that]
    bao = [(x["video_tu"], x["video_den"]) for x in doan_tim]
    kq = {"so_doan_tim": len(doan_tim), "so_doan_that": len(doan_that),
          "doan_tim": [[x["video_tu"], x["video_den"], x["clip_tu"], x["clip_den"], x["tuong_dong_tb"],
                        x["k_uoc_luong"]] for x in doan_tim],
          "precision_giay": None, "recall_giay": None, "sai_so_dau_s": None, "sai_so_cuoi_s": None,
          "tung_doan_that": []}
    if not doan_that:
        kq["giay_bao_sai"] = round(danh_gia.do_dai(bao), 3)
        return kq
    if not doan_tim:
        kq["recall_giay"] = 0.0
        return kq
    kq["precision_giay"], kq["recall_giay"] = danh_gia.precision_recall(bao, that)
    kq["sai_so_dau_s"] = round(doan_tim[0]["video_tu"] - doan_that[0]["video_tu"], 3)
    kq["sai_so_cuoi_s"] = round(max(x["video_den"] for x in doan_tim) - max(x["video_den"] for x in doan_that), 3)
    for t in doan_that:
        gan = max(doan_tim, key=lambda x: danh_gia.do_dai(danh_gia.giao([(x["video_tu"], x["video_den"])],
                                                                         [(t["video_tu"], t["video_den"])])))
        kq["tung_doan_that"].append({
            "that_video": [t["video_tu"], t["video_den"]], "that_clip": [t["clip_tu"], t["clip_den"]],
            "tim_video": [gan["video_tu"], gan["video_den"]], "tim_clip": [gan["clip_tu"], gan["clip_den"]],
            "loi_video_dau_s": round(gan["video_tu"] - t["video_tu"], 3),
            "loi_video_cuoi_s": round(gan["video_den"] - t["video_den"], 3),
            "loi_clip_dau_s": round(gan["clip_tu"] - t["clip_tu"], 3),
            "loi_clip_cuoi_s": round(gan["clip_den"] - t["clip_den"], 3),
            "k_that": t["he_so"], "k_uoc_luong": gan["k_uoc_luong"],
            "moc_giay0_that": round(danh_gia.dau_clip(t), 3), "moc_giay0_uoc_luong": gan["moc_giay0_clip_tren_video"]})
    kq["giay_bao_ngoai_that"] = round(danh_gia.do_dai(bao) - danh_gia.do_dai(danh_gia.giao(bao, that)), 3)
    return kq


# ---------------------------------------------------------------- đường nền

def _lm_ca_video(duong: str) -> np.ndarray:
    x, _ = td.doc_pcm(duong)
    return td.log_mel(x)


def _tinh_tren_dong_gia(LM, C, L, dur, m, ts) -> dict:
    tu, dai = vung_video(m, L, dur)
    f0, f1 = int(round(tu * td.FPS)), int(round((tu + dai) * td.FPS))
    return td.tinh_chinh(C, LM[f0:f1], f0 / td.FPS, L, m, ts, video_den=dur)


def _tom(kq: dict, gia_tri: list) -> dict:
    return {"so_giay": len(gia_tri), "max": max(gia_tri) if gia_tri else None, "p99": phan_vi(gia_tri).get("p99"),
            "muc_trong": kq["muc_trong"], "nen_tai_cho_p99": kq["duong_nen"]["p99"], "nguong_dung": kq["nguong_dung"],
            "tuong_phan_thap": kq["tuong_phan_thap"], "so_doan_bao_sai": len(kq["doan"]), "doan": kq["doan"],
            "so_giay_bam": kq["so_giay_bam"]}


def duong_nen(ts: dict, nen: dict) -> dict:
    nhom = ("khong_lien_quan", "lech_can_chinh", "de_xuat_sai_S0", "bong_nhac_lap")
    ra: dict = {k: [] for k in nhom}
    gia_tri: dict = {f"{k}|{c}": [] for k in nhom for c in ("not_ngau_nhien", "nhac_co_nhip")}
    # (a) video KHÔNG liên quan: video S0 (600 s nốt ngẫu nhiên + 400 s nhạc có nhịp) × 9 clip của kho S0
    d0 = os.path.join(BO_THU, "S0")
    LM0 = _lm_ca_video(_an_toan(os.path.join(d0, "video_vi_pham.wav")))
    dur0 = 1000.0
    for ten in sorted(os.listdir(os.path.join(d0, "kho"))):
        xc, _ = td.doc_pcm(_an_toan(os.path.join(d0, "kho", ten)))
        C, L = td.log_mel(xc), len(xc) / td.SR
        loai = "nhac_co_nhip" if ten in NHAC_CO_NHIP else "not_ngau_nhien"
        for t0 in np.arange(0.0, dur0 - L + 1e-6, 47.3):
            m = {"start_s": float(t0), "vung_khop_s": float(t0) + 0.05 * L, "clip_offset_s": 0.05 * L,
                 "end_s": float(t0) + 0.95 * L}
            kq = _tinh_tren_dong_gia(LM0, C, L, dur0, m, ts)
            v = [h[1] for h in kq["ho_so"] if h is not None]
            gia_tri[f"khong_lien_quan|{loai}"].extend(v)
            ra["khong_lien_quan"].append({"clip": ten, "giay0_clip": round(float(t0), 1), **_tom(kq, v)})
    # (b) đề xuất sai của audfprint ở S0 (dòng bị loại với goc_S6) — chạy như thể đã được chấp nhận
    ke0 = _json(os.path.join(d0, "ket_qua_engine.json"))
    for m in ke0["dong_clip_khac"]["matches_loai"]:
        xc, _ = td.doc_pcm(_an_toan(m["duong_dan_kho"]))
        C, L = td.log_mel(xc), len(xc) / td.SR
        kq = _tinh_tren_dong_gia(LM0, C, L, dur0, m, ts)
        v = [h[1] for h in kq["ho_so"] if h is not None]
        gia_tri["de_xuat_sai_S0|nhac_co_nhip"].extend(v)
        ra["de_xuat_sai_S0"].append({"clip": m["clip"], "start_s": m["start_s"], "hashes": m["hashes"], **_tom(kq, v)})
    # (c) căn chỉnh LỆCH trên đúng cặp clip–video của từng kịch bản; (d) «bóng» nhạc lặp: lệch đúng bội ô nhịp
    for S in THU_TU:
        if S == "S0":
            continue
        d = _thu_muc(S)
        st, ke = _json(os.path.join(d, "su_that.json")), _json(os.path.join(d, "ket_qua_engine.json"))
        dong = ke["dong_cho_clip"]["matches"] or ke["dong_cho_clip"]["matches_loai"][:1]
        if not dong:
            continue
        LM = _lm_ca_video(_an_toan(os.path.join(d, st["video"])))
        dur = float(ke["duration_s"])
        xc, _ = td.doc_pcm(_an_toan(dong[0]["duong_dan_kho"]))
        C, L = td.log_mel(xc), len(xc) / td.SR
        loai = "nhac_co_nhip" if S in NHAC_CO_NHIP else "not_ngau_nhien"
        for m in dong:
            for ten_nhom, lech in (("lech_can_chinh", LECH), ("bong_nhac_lap", BONG.get(S, ()))):
                for dl in lech:
                    mg = {"start_s": m["start_s"] + dl, "vung_khop_s": m["vung_khop_s"] + dl,
                          "clip_offset_s": m["clip_offset_s"], "end_s": m["end_s"] + dl}
                    kq = _tinh_tren_dong_gia(LM, C, L, dur, mg, ts)
                    v = [h[1] for h in kq["ho_so"] if h is not None and nhan_giay(h[0], h[2], st["doan"]) == "khong"]
                    gia_tri[f"{ten_nhom}|{loai}"].extend(v)
                    ra[ten_nhom].append({"kich_ban": S, "dong_start_s": m["start_s"], "lech_s": round(dl, 3),
                                         **_tom(kq, v)})
    tom = {k: phan_vi(v) for k, v in gia_tri.items() if v}
    tom["ngoai_doan_that_o_can_chinh_dung"] = {S: phan_vi(v) for S, v in nen["ngoai_doan_that"].items() if v}
    tom["duong_theo_kich_ban"] = {S: phan_vi(v) for S, v in nen["duong"].items()}
    ra["tom_tat_phan_bo"] = tom
    ra["dong_gia_van_ra_doan"] = {k: sum(1 for x in ra[k] if x["so_doan_bao_sai"]) for k in nhom}
    ra["dong_gia_tuong_phan_thap"] = {k: sum(1 for x in ra[k] if x["tuong_phan_thap"]) for k in nhom}
    ra["so_dong_gia"] = {k: len(ra[k]) for k in nhom}
    return ra


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--nguong", type=float, default=None, help="ngưỡng CỐ ĐỊNH (0..1) thay cho ngưỡng tại chỗ")
    ap.add_argument("--ra", default=RA_MAC_DINH)
    ap.add_argument("kich_ban", nargs="*")
    a = ap.parse_args()
    ts = dict(td.THAM_SO_MAC_DINH)
    if a.nguong is not None:
        ts.update(nguong_bam=a.nguong, nguong_dung=a.nguong)
    nen: dict = {"duong": {}, "ngoai_doan_that": {}}
    tong = {"tham_so": {k: list(v) if isinstance(v, tuple) else v for k, v in ts.items()}, "kich_ban": {}}
    for S in (a.kich_ban or THU_TU):
        t = time.perf_counter()
        kb = kich_ban(S, ts, a.ra, nen)
        dg = kb["danh_gia"]
        nguong = [(x["muc_trong"], x["duong_nen"]["p99"], x["nguong_dung"], x["tuong_phan_thap"]) for x in kb["dong"]]
        print(f"{S}: {dg['so_doan_tim']} đoạn {dg['doan_tim']} | P {dg['precision_giay']} R {dg['recall_giay']} "
              f"đầu {dg['sai_so_dau_s']} cuối {dg['sai_so_cuoi_s']} | (trong, nền p99, ngưỡng, tp thấp) {nguong} | "
              f"{kb['thoi_gian_tong_s']} s (chạy {time.perf_counter() - t:.1f} s)", flush=True)
        tong["kich_ban"][S] = {
            "danh_gia": dg, "sai_so_engine": kb["sai_so_engine"], "thoi_gian_tong_s": kb["thoi_gian_tong_s"],
            "tung_dong": [{"loai": x["loai"], "engine": x["engine"], "k_engine": x["k_engine"],
                           "muc_trong": x["muc_trong"], "duong_nen": x["duong_nen"], "nguong_bam": x["nguong_bam"],
                           "nguong_dung": x["nguong_dung"], "tuong_phan_thap": x["tuong_phan_thap"],
                           "so_giay_bam": x["so_giay_bam"], "giay_sai_tren_nguong": x["giay_sai_tren_nguong"],
                           "giay_dung_duoi_nguong": x["giay_dung_duoi_nguong"], "thoi_gian": x["thoi_gian"],
                           "phan_bo_theo_su_that": x["phan_bo_theo_su_that"], "doan": x["doan"]}
                          for x in kb["dong"]],
            "tham_khao_dong_bi_loai": kb.get("danh_gia_dong_bi_loai_tham_khao")}
    if not a.kich_ban:
        t = time.perf_counter()
        nen_kq = duong_nen(ts, nen)
        nen_kq["thoi_gian_s"] = round(time.perf_counter() - t, 1)
        _ghi(os.path.join(a.ra, "duong_nen.json"), nen_kq)
        tong["duong_nen"] = {k: nen_kq[k] for k in ("tom_tat_phan_bo", "dong_gia_van_ra_doan",
                                                    "dong_gia_tuong_phan_thap", "so_dong_gia")}
        print(json.dumps({k: tong["duong_nen"][k] for k in ("dong_gia_van_ra_doan", "dong_gia_tuong_phan_thap",
                                                             "so_dong_gia")}, ensure_ascii=False))
        for k, v in tong["duong_nen"]["tom_tat_phan_bo"].items():
            print(k, json.dumps(v, ensure_ascii=False))
    _ghi(os.path.join(a.ra, "tong_hop.json" if not a.kich_ban else "tong_hop_mot_phan.json"), tong)


if __name__ == "__main__":
    main()
