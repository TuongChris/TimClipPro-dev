# -*- coding: utf-8 -*-
"""Đo lại sự thật CA ẨN VÒNG 2 (P-8) từ audio — ``kiem_su_that.kiem`` của vòng 1 (import, không sửa) + phép thêm cho các
kiểu mới của vòng 2. Không gọi engine, audfprint, tinh_chinh_moc hay Cách C.

Phép vòng 1 (kiem_su_that.py): ánh xạ tương quan dọc đoạn, biên độ theo phần ba, mép CUSUM / tương quan cửa sổ, bản sao
nguyên mẫu, dò toàn video, vùng im lặng mẫu 0. Thêm ở vòng 2:
  A. mép MỜ (``mep_mo``, he_so 1): khớp bình phương tối thiểu TỪNG MẪU mô hình video ≈ A·dốc(t − τ)·clip quanh tâm khai,
     quét τ ±0,5 s bước 2 ms, với hai hình dốc (công suất không đổi sin/cos, tuyến tính) → tâm dốc đo được và hình dốc nào
     khớp hơn. CUSUM vòng 1 tìm chỗ clip đạt NỬA biên độ: ở dốc công suất không đổi chỗ đó nằm ở 1/3 dốc (0,33 s trước tâm)
     nên mép mờ chấm bằng phép A; lời phàn nàn CUSUM về mép đó được miễn khi phép A đạt (|τ| ≤ 20 ms, đúng hình dốc khai).
  B. bản sao NGUYÊN MẪU khai (``doan_ban_sao_nguyen_mau``): mẫu int16 video trùng tuyệt đối clip trên ≥ 99,9 % đoạn (trừ
     vùng mờ), mỗi mép cứng = mép dải trùng tới 1,5 mẫu. Mép cứng xác nhận như vậy thì lời phàn nàn CUSUM về mép đó (ví dụ
     trống khớp nhịp hai bên chỗ nối làm tích video·clip không về 0 — B06, B13) được miễn, kèm bằng chứng.
  C. vùng GẦN im (``vung_gan_im_lang``): mức RMS so với tiếng clip đúng ``muc_gan_im_lang_db`` ±1 dB, không có tiếng clip
     (|biên độ chiếu| < 0,02 theo cả hai căn chỉnh kề).
«khop» khi không còn lý do nào sau miễn trừ có bằng chứng; lý do gốc của vòng 1 giữ ở ``ly_do_xem_lai_vong_1``.

Chạy riêng (ghi lại ``kiem_su_that`` vào su_that.json; dung_ca_2.py tự gọi sau khi dựng):
  <venv python> -B -X utf8 kiem_su_that_2.py [B01 ...]      # không đối số = mọi ca trong RA
  <venv python> -B -X utf8 kiem_su_that_2.py --tu-kiem       # tự kiểm phép A (dốc thật sin/cos → τ≈0; khai lệch → hỏng)
"""
from __future__ import annotations

import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import kiem_su_that as k1  # noqa: E402

SR = k1.SR
_i = k1._i
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\ca_an_2"
TAU_TOI_DA_S = 0.020
PHU_NGUYEN_MAU_TOI_THIEU = 0.999
LECH_MUC_GAN_IM_DB = 1.0
BIEN_DO_GAN_IM_TOI_DA = 0.02


def _nua_rong(st: dict, e: float) -> float:
    return next((float(m["nua_rong"]) for m in st.get("mep_mo", []) if abs(m["t"] - e) < 1e-6), 0.0)


def khop_doc(c: np.ndarray, v: np.ndarray, d: dict, t: float, h: float, phia: str) -> dict:
    """(A) Tâm dốc chuyển mờ đo từ audio: argmin_τ Σ(v − A·g(t − τ)·c)² với A tối ưu, cho hai hình dốc."""
    delta = _i(d["video_tu"] - d["clip_tu"])
    a, b = max(0, _i(t - h - 0.6)), min(len(v), _i(t + h + 0.6))
    tt = np.arange(a, b)
    tc = tt - delta
    ok = (tc >= 0) & (tc < len(c))
    cm = np.zeros(b - a)
    cm[ok] = c[tc[ok]]
    vv = v[a:b].astype(np.float64)
    ra = {}
    for kieu in ("cong_suat_khong_doi", "tuyen_tinh"):
        tot = None
        for tau in np.arange(-0.5, 0.5 + 1e-9, 0.002):
            u = np.clip((tt / SR - (t + tau - h)) / (2 * h), 0.0, 1.0)
            if kieu == "cong_suat_khong_doi":
                g = np.sin(0.5 * np.pi * u) if phia == "dau" else np.cos(0.5 * np.pi * u)
            else:
                g = u if phia == "dau" else 1.0 - u
            x = g * cm
            xx = float(x @ x)
            vx = float(vv @ x)
            sse = float(vv @ vv) - vx * vx / (xx + 1e-12)
            if tot is None or sse < tot[0]:
                tot = (sse, float(tau), vx / (xx + 1e-12))
        ra[kieu] = {"tau_s": round(tot[1], 4), "bien_do": round(tot[2], 4), "sse": tot[0]}
    return ra


def mep_toc_rong(c: np.ndarray, v: np.ndarray, d: dict, e: float, phia: str, muc_trong: float) -> float | None:
    """(D) Mép đoạn he_so ≠ 1 như ``kiem_su_that.mep_ncc`` nhưng tìm đỉnh tương quan trong ±20 ms quanh ánh xạ DANH NGHĨA
    (không cộng độ lệch trung vị): atempo chép từng khung với độ rung ±15 ms nên tìm ±3 ms quanh độ lệch trung vị (vòng 1)
    trượt khỏi đỉnh thật ở những chỗ độ rung cục bộ khác trung vị."""
    w, k = 0.05, d["he_so"]
    luoi = np.arange(e - 1.0, e + 1.0, 0.005)
    x = np.full(len(luoi), np.nan)
    for n, t in enumerate(luoi):
        tv0 = t - w / 2
        ct0 = d["clip_tu"] + (tv0 - d["video_tu"]) * k
        if 0 <= ct0 and _i(ct0) + _i(w) <= len(c):
            kq = k1.ncc_tim(c[_i(ct0):_i(ct0) + _i(w)], v, _i(tv0), _i(0.020))
            if kq:
                x[n] = kq[1]
    tren = np.nan_to_num(x, nan=-1.0) >= 0.5 * muc_trong
    thu_tu = range(len(luoi)) if phia == "dau" else range(len(luoi) - 1, -1, -1)
    for n in thu_tu:
        o = tren[n:n + 40] if phia == "dau" else tren[max(0, n - 39):n + 1]
        if o.mean() > 0.9:
            return round(float(luoi[n]), 4)
    return None


def _chieu(c: np.ndarray, v: np.ndarray, delta: int, a: int, b: int) -> float | None:
    tc = np.arange(a, b) - delta
    if b <= a or tc[0] < 0 or tc[-1] >= len(c):
        return None
    cm = c[tc].astype(np.float64)
    return float(v[a:b].astype(np.float64) @ cm / (cm @ cm + 1e-12))


def kiem(thu_muc: str) -> dict:
    with open(os.path.join(thu_muc, "su_that.json"), encoding="utf-8") as f:
        st = json.load(f)
    k = k1.kiem(thu_muc)                                  # phép vòng 1, y nguyên
    goc = list(k["ly_do_xem_lai"])
    them: dict = {"doc_mo": [], "nguyen_mau": [], "gan_im": []}
    moi, mien = [], []
    can_doc = st.get("mep_mo") or st.get("vung_gan_im_lang") or any(d["he_so"] != 1.0 for d in st["doan"])
    v = k1.doc_am(os.path.join(thu_muc, st["video"])) if can_doc else None
    am = {ten: k1.doc_am(os.path.join(thu_muc, "kho", ten)) for ten in {d["clip"] for d in st["doan"]}} if can_doc else {}

    # (A) mép mờ
    for n, d in enumerate(st["doan"]):
        for e, phia in ((d["video_tu"], "dau"), (d["video_den"], "cuoi")):
            h = _nua_rong(st, e)
            if not h:
                continue
            if d["he_so"] != 1.0:
                moi.append(f"đoạn {n}: mép mờ {e} ở đoạn he_so ≠ 1 — chưa có phép kiểm")
                continue
            kq = khop_doc(am[d["clip"]], v, d, e, h, phia)
            khai = st.get("kieu_chuyen_mo", "tuyen_tinh")
            khac = "tuyen_tinh" if khai == "cong_suat_khong_doi" else "cong_suat_khong_doi"
            dat = abs(kq[khai]["tau_s"]) <= TAU_TOI_DA_S and kq[khai]["sse"] < kq[khac]["sse"]
            them["doc_mo"].append({"doan_so": n, "mep": e, "phia": phia, "kieu_khai": khai, "dat": dat,
                                   **{x: {"tau_s": kq[x]["tau_s"], "bien_do": kq[x]["bien_do"],
                                          "sse_tuong_doi": round(kq[x]["sse"] / kq[khai]["sse"], 6)} for x in kq}})
            if dat:
                mien.append({"doan_so": n, "mep": e, "ly_do": f"mép mờ: tâm dốc {khai} đo được lệch "
                             f"{kq[khai]['tau_s'] * 1000:+.0f} ms, hình dốc khai khớp hơn {khac}"})
            else:
                moi.append(f"đoạn {n}: mép mờ {e} — tâm dốc đo được lệch {kq[khai]['tau_s']} s hoặc sai hình dốc {kq}")

    # (D) đoạn he_so ≠ 1 (atempo): ánh xạ vòng 1 đòi trung vị độ lệch ≤ 5 ms, nhưng atempo chép từng khung với độ rung ±15 ms
    # (p95 ~15 ms ở mọi ca tốc độ, cả nốt ngẫu nhiên) nên trung vị có thể ±10 ms tuỳ nội dung → nhận ≤ 15 ms khi p95 ≤ 20 ms và
    # không trôi; mép đo lại bằng ``mep_toc_rong``.
    them["toc_do"] = []
    for n, d in enumerate(st["doan"]):
        if d["he_so"] == 1.0:
            continue
        an = k["doan"][n]["anh_xa"]
        anh_xa_dat = (an.get("so_moc", 0) >= 5 and abs(an["lech_trung_vi_ms"]) <= 15.0
                      and an["lech_p95_tuyet_doi_ms"] <= 20.0 and abs(an.get("doc_ms_moi_100s", 0.0)) <= 20.0
                      and an["ncc_trung_vi"] >= 0.9)
        mep = [mep_toc_rong(am[d["clip"]], v, d, d["video_tu"], "dau", an.get("ncc_trung_vi", 0.0)),
               mep_toc_rong(am[d["clip"]], v, d, d["video_den"], "cuoi", an.get("ncc_trung_vi", 0.0))]
        lech = [None if m is None else round(m - e, 4) for m, e in zip(mep, (d["video_tu"], d["video_den"]))]
        mep_dat = [x is not None and abs(x) <= k1.DUNG_SAI["mep_s_toc"] for x in lech]
        them["toc_do"].append({"doan_so": n, "anh_xa_dat_dung_sai_rung_atempo": anh_xa_dat, "mep_do_tim_rong_s": mep,
                               "lech_mep_s": lech, "mep_dat": mep_dat})
        for x in [x for x in goc if x.startswith(f"đoạn {n}: lệch ánh xạ ")]:
            if anh_xa_dat:
                mien.append({"doan_so": n, "mep": None, "ly_do": f"«{x}» — độ rung khung của atempo: trung vị "
                             f"{an['lech_trung_vi_ms']} ms ≤ 15, p95 {an['lech_p95_tuyet_doi_ms']} ms ≤ 20, độ dốc "
                             f"{an.get('doc_ms_moi_100s')} ms/100 s (không trôi), tương quan trung vị {an['ncc_trung_vi']}",
                             "thay_ly_do": x})
        for e, ok, m in zip((d["video_tu"], d["video_den"]), mep_dat, mep):
            if ok:
                mien.append({"doan_so": n, "mep": e,
                             "ly_do": f"mép đo lại bằng tương quan cửa sổ 0,05 s tìm ±20 ms quanh ánh xạ danh nghĩa: "
                                      f"{m} (lệch {round(m - e, 4)} s ≤ {k1.DUNG_SAI['mep_s_toc']})"})
            else:
                moi.append(f"đoạn {n}: mép {e} (he_so {d['he_so']}) đo lại tìm rộng được {m}")
    da_thay = {m["thay_ly_do"] for m in mien if m.get("thay_ly_do")}
    goc = [x for x in goc if x not in da_thay]

    # (B') kiểm lại MỌI dải trùng nguyên mẫu với dung sai kề 1,5 mẫu: phép vòng 1 so mép dải (số đúng) với giây khai đã
    # làm tròn 6 chữ số, nên hai đoạn CÙNG clip kề nhau (cắt không khe, B06) «chồng» nhau 0,35 µs và bị báo lệch/tràn.
    runs_moi_clip = k.get("ban_sao_nguyen_mau") or {}
    loi_mau = []
    for ten, runs in runs_moi_clip.items():
        khai = [d for d in st["doan"] if d["clip"] == ten and d["he_so"] == 1.0]
        for x in runs:
            cung = [d for d in khai
                    if min(x["video_den"], d["video_den"]) - max(x["video_tu"], d["video_tu"]) > 1.5 / SR]
            if not cung:
                loi_mau.append(f"bản sao nguyên mẫu ngoài mọi đoạn khai: {x}")
            for d in cung:
                if x["delta_mau"] != _i(d["video_tu"] - d["clip_tu"]):
                    loi_mau.append(f"bản sao nguyên mẫu lệch căn chỉnh so với đoạn khai: {x}")
                if (x["video_tu"] < d["video_tu"] - _nua_rong(st, d["video_tu"]) - 1.5 / SR
                        or x["video_den"] > d["video_den"] + _nua_rong(st, d["video_den"]) + 1.5 / SR):
                    loi_mau.append(f"bản sao nguyên mẫu tràn ra ngoài đoạn khai: {x}")
    goc_mau = [x for x in goc if x.startswith("bản sao nguyên mẫu")]
    them["kiem_lai_nguyen_mau_dung_sai_ke"] = {"thay_cho_ly_do_vong_1": goc_mau, "ly_do": loi_mau}
    goc = [x for x in goc if not x.startswith("bản sao nguyên mẫu")]
    moi += loi_mau

    # (B) bản sao nguyên mẫu khai
    for n in st.get("doan_ban_sao_nguyen_mau", []):
        d = st["doan"][n]
        delta = _i(d["video_tu"] - d["clip_tu"])
        runs = [x for x in runs_moi_clip.get(d["clip"], []) if x["delta_mau"] == delta]
        h0, h1 = _nua_rong(st, d["video_tu"]), _nua_rong(st, d["video_den"])
        lo, hi = d["video_tu"] + h0, d["video_den"] - h1
        phu = sum(max(0.0, min(x["video_den"], hi) - max(x["video_tu"], lo)) for x in runs) / (hi - lo)
        dau = None if h0 else any(abs(x["video_tu"] - d["video_tu"]) <= 1.5 / SR for x in runs)
        cuoi = None if h1 else any(abs(x["video_den"] - d["video_den"]) <= 1.5 / SR for x in runs)
        them["nguyen_mau"].append({"doan_so": n, "so_dai_trung": len(runs), "phu_tru_vung_mo": round(phu, 6),
                                   "mep_dau_trung_toi_mau": dau, "mep_cuoi_trung_toi_mau": cuoi})
        if phu < PHU_NGUYEN_MAU_TOI_THIEU or dau is False or cuoi is False:
            moi.append(f"đoạn {n}: khai là bản sao nguyên mẫu nhưng phủ {phu:.6f}, mép đầu {dau}, mép cuối {cuoi}")
            continue
        for e, ok in ((d["video_tu"], dau), (d["video_den"], cuoi)):
            if ok:
                mien.append({"doan_so": n, "mep": e, "ly_do": "mép cứng trùng mép dải mẫu int16 trùng tuyệt đối (≤ 1,5 "
                             "mẫu) — chính xác hơn CUSUM"})

    # (C) vùng gần im
    for a_s, b_s in st.get("vung_gan_im_lang", []):
        a, b = _i(a_s), _i(b_s)
        ke = [d for d in st["doan"] if abs(d["video_den"] - a_s) < 1e-3 or abs(d["video_tu"] - b_s) < 1e-3]
        muc = None
        if ke:
            c = am[ke[0]["clip"]]
            ref = np.concatenate([c[_i(d["clip_tu"]):_i(d["clip_den"])] for d in st["doan"] if d["clip"] == ke[0]["clip"]])
            muc = 20 * np.log10(np.sqrt(np.mean(v[a:b].astype(np.float64) ** 2)) / np.sqrt(np.mean(ref ** 2)))
        chieu = [_chieu(c, v, _i(d["video_tu"] - d["clip_tu"]), a, b) for d in ke]
        dat = (muc is not None and abs(muc - st.get("muc_gan_im_lang_db", muc)) <= LECH_MUC_GAN_IM_DB
               and all(x is not None and abs(x) < BIEN_DO_GAN_IM_TOI_DA for x in chieu))
        them["gan_im"].append({"vung": [a_s, b_s], "muc_db_so_voi_clip": None if muc is None else round(float(muc), 2),
                               "bien_do_chieu_theo_can_chinh_ke": [None if x is None else round(x, 5) for x in chieu],
                               "dat": dat})
        if not dat:
            moi.append(f"vùng gần im {a_s}–{b_s}: mức {muc} dB, biên độ chiếu {chieu}")

    def la_ly_do_mep(x: str, m: dict) -> bool:
        return m["mep"] is not None and x.startswith(f"đoạn {m['doan_so']}: mép {m['mep']} đo được")

    vong_1 = list(k["ly_do_xem_lai"])
    con = [x for x in goc if not any(la_ly_do_mep(x, m) for m in mien)]
    k["ly_do_xem_lai_vong_1"] = vong_1
    k["kiem_them_vong_2"] = them
    k["mien_tru_co_bang_chung"] = [m for m in mien if m.get("thay_ly_do") or any(la_ly_do_mep(x, m) for x in vong_1)]
    k["mep_xac_nhan_them"] = [m for m in mien if m not in k["mien_tru_co_bang_chung"]]
    k["ly_do_xem_lai"] = con + moi
    k["ket_luan"] = "khop" if not k["ly_do_xem_lai"] else "XEM LAI"
    k["cach"] = k.get("cach", "") + (" + (vòng 2) khớp hình dốc mép mờ, kiểm lại dải nguyên mẫu với dung sai kề, "
                                     "phủ/mép bản sao nguyên mẫu khai, mức vùng gần im, mép đoạn tốc độ tìm ±20 ms")
    return k


def ghi_vao_su_that(thu_muc: str) -> dict:
    kq = kiem(thu_muc)
    p = os.path.join(thu_muc, "su_that.json")
    with open(p, encoding="utf-8") as f:
        st = json.load(f)
    st["kiem_su_that"] = kq
    with open(p, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    return kq


def tu_kiem() -> None:
    """Phép A trên tín hiệu dựng tại chỗ: dốc sin/cos thật → τ ≈ 0, nhận đúng hình; dốc tuyến tính → nhận tuyến tính."""
    rng = np.random.default_rng(7999)
    n = _i(20.0)
    t = np.arange(_i(0.4)) / SR
    clip = np.concatenate([np.sin(2 * np.pi * f * t) * np.hanning(len(t)) for f in rng.uniform(200, 4000, 60)])[:n]
    nen = 0.5 * rng.standard_normal(n)
    d = {"video_tu": 10.0, "clip_tu": 10.0}             # delta 0
    i0, m = _i(10.0), _i(1.0)
    u = (np.arange(2 * m) + 0.5) / (2 * m)
    for kieu, g in (("cong_suat_khong_doi", np.sin(0.5 * np.pi * u)), ("tuyen_tinh", u)):
        v = nen.copy()
        v[i0 - m:i0 + m] = np.sqrt(1 - g * g) * nen[i0 - m:i0 + m] + g * clip[i0 - m:i0 + m]
        v[i0 + m:] = clip[i0 + m:]
        kq = khop_doc(clip, v, d, 10.0, 1.0, "dau")
        khac = "tuyen_tinh" if kieu == "cong_suat_khong_doi" else "cong_suat_khong_doi"
        print(f"tự kiểm dốc {kieu}: τ {kq[kieu]['tau_s']} s, biên độ {kq[kieu]['bien_do']}, "
              f"sse khác/khai {kq[khac]['sse'] / kq[kieu]['sse']:.4f}")
        assert abs(kq[kieu]["tau_s"]) <= 0.01 and kq[kieu]["sse"] < kq[khac]["sse"], kq
        kq = khop_doc(clip, v, {"video_tu": 10.3, "clip_tu": 10.3}, 10.3, 1.0, "dau")    # khai lệch 0,3 s
        assert abs(kq[kieu]["tau_s"] + 0.3) <= 0.01, kq
    print("kiem_su_that_2: tự kiểm phép A ĐẠT")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--tu-kiem" in sys.argv:
        tu_kiem()
        return
    ds = [x for x in sys.argv[1:] if not x.startswith("--")]
    tat_ca = sorted(x for x in os.listdir(RA) if os.path.isfile(os.path.join(RA, x, "su_that.json")))
    for ten in [t for t in tat_ca if not ds or t in ds or t.split("_")[0] in ds]:
        kq = ghi_vao_su_that(os.path.join(RA, ten))
        print(f"[{ten}] {kq['ket_luan']} miễn {len(kq['mien_tru_co_bang_chung'])} {kq['ly_do_xem_lai']}", flush=True)


if __name__ == "__main__":
    main()
