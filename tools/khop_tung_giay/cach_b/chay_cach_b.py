# -*- coding: utf-8 -*-
"""Chạy Cách B («dòng thời gian hash», dong_thoi_gian_hash.py) trên bộ thử 15 kịch bản của bước trước (14/11/2026).

Chỉ ĐỌC bộ thử (C:\\Dev\\pc2_test_runs\\2026-11-14_khop_tung_giay\\bo_thu) và mã sản phẩm; ghi vào KET_QUA. Không gọi
engine: dùng dòng kết quả engine đã chấp nhận trong ``ket_qua_engine.json`` (matches), clip trong ``kho/`` và video.

Ba pha:
  1. Hồ sơ từng giây ở căn chỉnh của từng dòng + ĐƯỜNG NỀN:
     a. «nền cùng video»: chính clip đó trên CHÍNH video đó, ở các vùng nằm ngoài mọi dòng engine báo (± đệm) — làm được
        y hệt trong sản phẩm, không cần sự thật;
     b. video S0 (không chứa clip nào) × 9 clip ở lưới căn chỉnh 50 s + đúng các nhóm khớp ngẫu nhiên engine đã loại;
     c. «tự giống»: cùng cửa sổ có clip nhưng căn chỉnh SAI (A ± 3,1…61,7 s; nhạc có nhịp thêm bội ô nhịp) — đo rủi ro
        nhạc lặp/sample y hệt, KHÔNG dùng đặt ngưỡng.
  2. Ngưỡng trễ hai mức TỪ đường nền: theo từng dòng (nền a của dòng đó; clip «tự lặp» theo c thì không thấp hơn ngưỡng
     chung — đề xuất) và một bộ ngưỡng chung (a + b, w 5 s) để so.
  3. Đoạn + mép tới 0,1 s, chỗ cắt giữa giữa các dòng của cùng clip, chấm so với su_that.json.

Chạy (Git Bash, ~3–5 phút, một tiến trình Python một luồng):
  cd /c/Dev/pc2_test_tools/khop_tung_giay/cach_b
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \\
      -B chay_cach_b.py
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import csv  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import wave  # noqa: E402

import numpy as np  # noqa: E402

CONG_CU = os.path.dirname(os.path.abspath(__file__))
MA = r"C:\Dev\Tool_Quet\TimClipPro"
BO_THU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"
KET_QUA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_b"
CHAN_MANG = r"C:\Dev\Tool_Quet\tools\test\chan_mang"
THU_TU = ["S1", "S2", "S3", "S4", "S4b", "S5", "S5b", "S6", "S6b", "S7", "S7b", "S7c", "S8", "S9", "S0"]
LUOI_S = [k * 5e-5 for k in range(-30, 31)]          # độ dốc ±0,15 % (= ngưỡng trôi tối thiểu của engine)
TIM_D = 15                                          # ±15 khung (±0,35 s) quanh căn chỉnh engine báo (làm tròn 0,1 s)
O_NHIP = 240.0 / 113.0                              # tests/am_thanh_lap.O_NHIP — một ô nhịp của nhạc có nhịp
# |δ| ≥ 3 s: với lưới độ dốc ±0,15 % và ±15 khung, đường tìm KHÔNG thể chạm căn chỉnh thật trong cửa sổ ≤ 15 phút
# (δ = ±0,6 s thì chạm — đo ở lần chạy đầu: tự giống giả 0,75–0,8). Vẫn kiểm từng hồ sơ (cờ ``cham_can_chinh_that``).
DELTA_LECH = [-61.7, -23.9, -7.7, -3.1, 3.1, 7.7, 23.9, 61.7]
DELTA_BONG = [s * m * O_NHIP for m in (0.5, 1, 4, 8) for s in (-1, 1)]   # bội ô nhịp: «bóng» của nhạc có nhịp
W_CHUNG, MIN_DAI = 5, 3                             # cửa sổ làm mượt của bộ ngưỡng chung; đoạn ngắn nhất 3 s
NEN_TOI_DA_S, NEN_BUOC_S = 600.0, 20.0              # nền cùng video: tối đa 600 s audio, căn chỉnh mỗi 20 s
# Clip «tự lặp»: hồ sơ của CHÍNH clip ở căn chỉnh sai (|δ| ≥ 3 s, không chạm căn chỉnh thật) có trung vị trượt ≥ mức này.
# Đo ở lần chạy thứ hai: clip nốt ngẫu nhiên ≤ 0,03; nhạc có nhịp dùng sample y hệt 0,29–0,40 (bội ô nhịp tới 0,67).
# Khi đó nền cùng video có thể không chứa thứ gây trùng (video S0 có cùng mẫu kick sinh đoạn giả) → ngưỡng ≥ nền chung.
TU_LAP = 0.1


def _kiem_moi_truong() -> None:
    sc = sys.modules.get("sitecustomize")
    if sc is None or os.path.normcase(os.path.dirname(os.path.abspath(sc.__file__))) != os.path.normcase(CHAN_MANG):
        raise SystemExit(f"Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH={CHAN_MANG}")
    for lenh in ("ffmpeg", "ffprobe"):
        if shutil.which(lenh) is None:
            raise SystemExit(f"Cần {lenh} trong PATH.")


_kiem_moi_truong()
sys.path.insert(0, CONG_CU)
sys.path.insert(0, os.path.join(os.path.dirname(CONG_CU), "bo_thu"))
sys.path.insert(0, MA)
import danh_gia  # noqa: E402  (bộ thử bước trước: hop/giao/do_dai/precision_recall — hàm thuần)
import dong_thoi_gian_hash as dt  # noqa: E402
import toc_do_khop as tdk  # noqa: E402  (mã sản phẩm, module thuần: ước lượng độ trôi + bộ lọc đổi tốc độ)


def _doc_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ghi_json(path: str, obj) -> None:
    def chuyen(x):
        if isinstance(x, np.generic):
            return x.item()
        if isinstance(x, np.ndarray):
            return x.tolist()
        return str(x)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=chuyen)


def _do_dai_wav(path: str) -> float:
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


def _r(x, n=3):
    return None if x is None else round(float(x), n)


# ---------------------------------------------------------------- mô hình thời gian của một dòng kết quả
def mo_hinh(m: dict, ket: dict, che_do: str) -> dict:
    """Căn chỉnh A (giây video của giây 0 clip, CHƯA kẹp), k_tong (giây video / giây clip), sigma (hệ số áp lên cửa sổ).

    Hệ số lượt: của mảnh CHÍNH cho ra mốc đầu clip (align = vung_khop_s − k·clip_offset_s). ``che_do``:
    "chi_engine" = chỉ tin hệ số của lượt; "de_xuat" = lượt thường mà các mảnh của clip có độ trôi (đo bằng ĐÚNG
    ``toc_do_khop.uoc_luong_toc_do`` của engine, tham số mặc định = Config) thì bù theo độ trôi như lượt bù tempo.
    """
    ten = os.path.basename(m["duong_dan_kho"])
    manh = [x for x in ket["merge_cuoi"]["manh_tho_cua_clip"] if os.path.basename(x["clip"]) == ten]
    # Mảnh CHÍNH: align = vung_khop_s − k·clip_offset_s đúng tới sai số dấu phẩy động. Lấy mảnh lệch NHỎ NHẤT — một mảnh
    # của lượt khác có thể tình cờ lệch < 0,05 s (S7c: mảnh k = 1 lệch 0,007 s so với dòng của lượt bù k = 0,98048).
    lech = [(abs(x["align"] - (m["vung_khop_s"] - x["he_so"] * m["clip_offset_s"])), n) for n, x in enumerate(manh)]
    chinh = [manh[min(lech)[1]]] if lech and min(lech)[0] < 0.05 else []
    he_so = float(chinh[0]["he_so"]) if chinh else 1.0
    ho = "tempo"
    if abs(he_so - 1.0) > 1e-9:
        tien_to = f"k{tdk.ma_he_so(he_so)}_"
        ho = next((g["luot_bu"][len(tien_to):] for g in ket["goi_audfprint_match"]
                   if g["luot_bu"].startswith(tien_to)), "tempo")
    A = m["vung_khop_s"] - he_so * m["clip_offset_s"]
    mh = {"che_do": che_do, "he_so_luot": he_so, "ho": ho, "A_engine": A, "A": A, "k_tong": he_so, "sigma": he_so,
          "co_manh_chinh": bool(chinh),
          "nguon": "lượt thường (k = 1)" if he_so == 1.0 else f"lượt bù tốc độ k = {he_so:.5f} ({ho})"}
    if che_do == "de_xuat" and he_so == 1.0:
        k1 = [x for x in manh if abs(x["he_so"] - 1.0) <= 1e-9]
        uoc = tdk.uoc_luong_toc_do(k1)
        if uoc:
            r = uoc[0].ty_le
            k = 1.0 / r
            mh.update(A=float(np.median([x["bat_dau"] - k * x["t_clip"] for x in k1])), k_tong=k, sigma=k,
                      ho="tempo", r_do_troi=r, nguon=f"lượt thường + độ trôi r = {r:.5f} → bù tempo k = {k:.5f}")
    return mh


def cua_so(m: dict, mh: dict, L: float, dur: float) -> tuple:
    """[W0, W1): vùng engine báo ± đệm (10 % độ dài clip + 30 s), trong phạm vi clip trên trục video."""
    dem = 0.1 * L + 30.0
    W0 = max(0.0, m["vung_khop_s"] - dem, mh["A"] - 2.0)
    W1 = min(float(dur), m["end_s"] + dem, mh["A"] + mh["k_tong"] * L + 2.0)
    return W0, W1


def _tung_giay(n: np.ndarray, k: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n >= dt.N_MIN, k / np.maximum(n, 1), np.nan)


def _thong_ke(n: np.ndarray, k: np.ndarray, w: int) -> dict:
    """Một hồ sơ đường nền: max của trung vị trượt (thứ mở đoạn) và của tỉ lệ gộp (thứ kéo dài đoạn), cửa sổ w giây."""
    hop_le = n >= dt.N_MIN
    if not hop_le.any():
        return {"so_giay": 0}
    tung = _tung_giay(n, k)
    tv = dt.trung_vi_truot(tung, w)
    tv[~hop_le] = np.nan
    return {"so_giay": int(hop_le.sum()), "max_tung_giay": _r(np.nanmax(tung), 4),
            "max_trung_vi": _r(np.nanmax(tv), 4), "max_gop": _r(np.nanmax(dt.ty_le_truot(n, k, w)), 4),
            "ty_le_gop_ca_ho_so": _r(k[hop_le].sum() / n[hop_le].sum(), 5)}


# ---------------------------------------------------------------- pha 1: hồ sơ + đường nền
def pha1_dong(S: str, i: int, m: dict, ket: dict, st: dict, che_do: str, tam: str) -> dict:
    t = {}
    clip = m["duong_dan_kho"]
    L = _do_dai_wav(clip)
    mh = mo_hinh(m, ket, che_do)
    W0, W1 = cua_so(m, mh, L, ket["duration_s"])
    t0 = time.perf_counter()
    wav = dt.cat_cua_so(os.path.join(BO_THU, S, st["video"]), W0, W1, os.path.join(tam, f"{S}_{i}_{che_do}.wav"),
                        mh["sigma"], mh["ho"])
    t["cat_cua_so"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    wh = dt.hash_file(wav, ket["cau_hinh"]["shifts_quet"], la_kho=False)
    t["hash_cua_so"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    ch = dt.hash_file(clip, ket["cau_hinh"]["shifts_kho"], la_kho=True)
    t["hash_clip"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    cap = dt.cap_hash(ch, wh)
    f_ref = ((m["vung_khop_s"] + m["end_s"]) / 2 - W0) / (mh["sigma"] * dt.T)
    h = dt.ho_so(ch, wh, cap, W0, W1, mh["sigma"], mh["A"], mh["k_tong"], f_ref, TIM_D, LUOI_S)
    t["khop_ho_so"] = time.perf_counter() - t0
    os.remove(wav)
    d = {"S": S, "i": i, "m": m, "mh": mh, "L": L, "W0": W0, "W1": W1, "f_ref": f_ref, "ch": ch, "wh": wh,
         "cap": cap, "h": h, "t": t}
    d["ts"] = tham_so_dong(d)
    return d


def tham_so_dong(d: dict) -> dict:
    """Tham số theo MẬT ĐỘ BẰNG CHỨNG của dòng (hash clip khớp mỗi giây trong vùng engine đã báo — vùng chắc chắn có
    clip): cửa sổ làm mượt đủ ~20 hash khớp kỳ vọng (3…15 s, lẻ); nối khoảng hở ngắn hơn thời gian có ~10 hash khớp."""
    h, m = d["h"], d["m"]
    g = h["giay0"] + np.arange(len(h["n_clip"]))
    vung = (g >= m["vung_khop_s"]) & (g + 1 <= m["end_s"])
    lam = float(h["n_khop"][vung].sum() / max(1, vung.sum()))
    w = int(min(15, max(3, np.ceil(20.0 / max(lam, 1e-9))))) | 1
    return {"hash_khop_moi_giay": _r(lam, 2), "w": w, "noi_ho": int(max(2, np.ceil(10.0 / max(lam, 1e-9)))),
            "le": max(5.0, w / 2 + 2)}


def nen_cung_video(d: dict, ket: dict, st: dict, tam: str) -> dict:
    """Chính clip của dòng trên CHÍNH video đó ở các vùng ngoài MỌI dòng engine báo (chấp nhận lẫn bị loại, mọi clip;
    ± đệm 10 % độ dài clip + 30 s), cùng phép đổi tốc độ của dòng, căn chỉnh mỗi NEN_BUOC_S giây — không cần sự thật."""
    t0 = time.perf_counter()
    loai_tru = []
    for nhom in ("dong_cho_clip", "dong_clip_khac"):
        for r in ket[nhom]["matches"] + ket[nhom]["matches_loai"]:
            dem = 0.1 * _do_dai_wav(r["duong_dan_kho"]) + 30.0
            loai_tru.append((r["vung_khop_s"] - dem, r["end_s"] + dem))
    dur = float(ket["duration_s"])
    khoang, moc, con = [], 0.0, NEN_TOI_DA_S
    for a, b in danh_gia.hop(loai_tru) + [(dur, dur)]:
        if a - moc >= 40.0 and con > 0:
            khoang.append((moc, min(a, moc + con)))
            con -= khoang[-1][1] - khoang[-1][0]
        moc = max(moc, b)
    mh, ch, L = d["mh"], d["ch"], d["L"]
    ho_so_nen = []
    for b0, b1 in khoang:
        wav = dt.cat_cua_so(os.path.join(BO_THU, d["S"], st["video"]), b0, b1,
                            os.path.join(tam, f"{d['S']}_{d['i']}_nen.wav"), mh["sigma"], mh["ho"])
        wh = dt.hash_file(wav, ket["cau_hinh"]["shifts_quet"], la_kho=False)
        os.remove(wav)
        cap = dt.cap_hash(ch, wh)
        for A in np.arange(b0 - mh["k_tong"] * L + 20.0, b1 - 20.0 + 1e-9, NEN_BUOC_S):
            giua = (max(b0, A) + min(b1, A + mh["k_tong"] * L)) / 2
            h = dt.ho_so(ch, wh, cap, b0, b1, mh["sigma"], float(A), mh["k_tong"],
                         (giua - b0) / (mh["sigma"] * dt.T), TIM_D, LUOI_S)
            ho_so_nen.append({"nguon": f"{d['S']} dòng {d['i']}", "clip": os.path.basename(d["m"]["duong_dan_kho"]),
                              "loai": "nen_cung_video", "A": round(float(A), 2), "_n": h["n_clip"], "_k": h["n_khop"]})
    return {"khoang": [[_r(a), _r(b)] for a, b in khoang], "ho_so": ho_so_nen, "giay": time.perf_counter() - t0}


def tu_giong(d: dict) -> list:
    """Cửa sổ CÓ clip, căn chỉnh SAI A + δ (cùng thủ tục tìm). Cờ ``cham_can_chinh_that``: đường tìm được đi qua căn
    chỉnh thật (lệch ≤ 4 khung ở đâu đó trong cửa sổ) — khi đó hồ sơ không còn là «căn chỉnh sai»."""
    nhip = os.path.basename(d["m"]["duong_dan_kho"]).startswith("goc_S6")
    mh, h0 = d["mh"], d["h"]
    F = (d["W1"] - d["W0"]) / (mh["sigma"] * dt.T)
    ra = []
    for delta in DELTA_LECH + (DELTA_BONG if nhip else []):
        h = dt.ho_so(d["ch"], d["wh"], d["cap"], d["W0"], d["W1"], mh["sigma"], mh["A"] + delta, mh["k_tong"],
                     d["f_ref"], TIM_D, LUOI_S)
        lech = [(h["d0"] - h0["d0"]) + (h["s"] - h0["s"]) * (f - d["f_ref"]) for f in (0.0, F)]
        cham_that = min(abs(x) for x in lech) <= 4 or lech[0] * lech[1] < 0
        bong = nhip and abs(delta / (O_NHIP / 2) - round(delta / (O_NHIP / 2))) * (O_NHIP / 2) < 0.4
        ra.append({"nguon": f"{d['S']} dòng {d['i']}", "clip": os.path.basename(d["m"]["duong_dan_kho"]),
                   "loai": ("tu_giong_bong_o_nhip" if bong else ("tu_giong_nhac_co_nhip" if nhip else "tu_giong")),
                   "delta_s": round(delta, 3), "cham_can_chinh_that": bool(cham_that),
                   "_n": h["n_clip"], "_k": h["n_khop"]})
    return ra


def nen_s0(tam: str) -> list:
    """Video S0 (không chứa clip nào) × 9 clip: lưới căn chỉnh 50 s + đúng các nhóm ngẫu nhiên engine đã loại."""
    S = "S0"
    st, ket = (_doc_json(os.path.join(BO_THU, S, x)) for x in ("su_that.json", "ket_qua_engine.json"))
    video = os.path.join(BO_THU, S, st["video"])
    dur = float(ket["duration_s"])
    sh_q, sh_k = ket["cau_hinh"]["shifts_quet"], ket["cau_hinh"]["shifts_kho"]
    wav = dt.cat_cua_so(video, 0.0, dur, os.path.join(tam, "S0_toan_bo.wav"))
    wh = dt.hash_file(wav, sh_q, la_kho=False)
    os.remove(wav)
    ra = []
    kho = os.path.join(BO_THU, S, "kho")
    for ten in sorted(os.listdir(kho)):
        clip = os.path.join(kho, ten)
        L = _do_dai_wav(clip)
        ch = dt.hash_file(clip, sh_k, la_kho=True)
        cap = dt.cap_hash(ch, wh)
        ds = [(float(A), 1.0, "tempo", "khong_clip_S0") for A in np.arange(-0.5 * L, dur - 0.5 * L + 1, 50.0)]
        for g in ket["merge_cuoi"]["tat_ca_nhom_sau_merge"]:
            if g["clip"] == ten:
                mh = mo_hinh({"vung_khop_s": g["vung_khop_s"], "clip_offset_s": g["clip_offset_s"],
                              "duong_dan_kho": clip}, ket, "chi_engine")
                ds.append((mh["A"], mh["sigma"], mh["ho"], "khong_clip_S0_nhom_engine_loai"))
        for A, sigma, ho, loai in ds:
            if sigma != 1.0:
                wav = dt.cat_cua_so(video, 0.0, dur, os.path.join(tam, "S0_k.wav"), sigma, ho)
                wh_k = dt.hash_file(wav, sh_q, la_kho=False)
                os.remove(wav)
                cap_k = dt.cap_hash(ch, wh_k)
            else:
                wh_k, cap_k = wh, cap
            giua = (max(0.0, A) + min(dur, A + sigma * L)) / 2
            h = dt.ho_so(ch, wh_k, cap_k, 0.0, dur, sigma, A, sigma, giua / (sigma * dt.T), TIM_D, LUOI_S)
            ra.append({"nguon": "S0", "clip": ten, "loai": loai, "A": round(A, 3), "he_so": sigma,
                       "_n": h["n_clip"], "_k": h["n_khop"]})
    return ra


# ---------------------------------------------------------------- pha 2: ngưỡng từ đường nền
def nguong_tu_nen(ho_so: list, w: int) -> dict:
    """Ngưỡng trễ từ đường nền với cửa sổ w: cao = 2 × max trung vị trượt (không hồ sơ nền nào mở được đoạn), thấp =
    1,25 × max tỉ lệ gộp (không hồ sơ nền nào kéo dài được đoạn); sàn 0,04 / 0,02 (≈ 2 / 1 hash khớp mỗi giây khi
    clip có ~45 hash/giây)."""
    tk = [_thong_ke(x["_n"], x["_k"], w) for x in ho_so]
    tk = [x for x in tk if x.get("so_giay")]
    if not tk:
        return {"nguong_cao": 0.04, "nguong_thap": 0.02, "so_ho_so_nen": 0}
    f_tv, f_gop = max(x["max_trung_vi"] for x in tk), max(x["max_gop"] for x in tk)
    cao = max(0.04, 2.0 * f_tv)
    return {"nguong_cao": round(cao, 4), "nguong_thap": round(min(cao, max(0.02, 1.25 * f_gop)), 4),
            "max_trung_vi_nen": f_tv, "max_gop_nen": f_gop, "so_ho_so_nen": len(tk),
            "so_giay_nen": int(sum(x["so_giay"] for x in tk)), "w": w}


def doan_gia(ho_so: list, ng: dict, w: int, noi_ho: int) -> dict:
    """Số đoạn và số giây mà bộ dò đoạn sinh ra trên các hồ sơ KHÔNG có clip ở căn chỉnh đó."""
    so_doan = so_giay = 0
    for x in ho_so:
        ds = dt.tim_doan(x["_n"], x["_k"], ng["nguong_cao"], ng["nguong_thap"], w, MIN_DAI, noi_ho)
        so_doan += len(ds)
        so_giay += sum(b - a for a, b in ds)
    return {"so_ho_so": len(ho_so), "so_doan_gia": so_doan, "so_giay_gia": so_giay}


# ---------------------------------------------------------------- pha 3: đoạn + mép + chấm điểm
def pha3_dong(d: dict, ng: dict, ts: dict) -> dict:
    h, mh = d["h"], d["mh"]
    t0 = time.perf_counter()
    tho = dt.tim_doan(h["n_clip"], h["n_khop"], ng["nguong_cao"], ng["nguong_thap"], ts["w"], MIN_DAI, ts["noi_ho"])
    g0 = h["giay0"]
    doan = []
    for n, (a, b) in enumerate(tho):
        trai = d["W0"] if n == 0 else (g0 + tho[n - 1][1] + g0 + a) / 2
        phai = d["W1"] if n == len(tho) - 1 else (g0 + b + g0 + tho[n + 1][0]) / 2
        mep = dt.mep_tinh(h["v"], h["e"], h["khop"], g0 + a, g0 + b, trai, phai, h["A_moi"],
                          h["A_moi"] + h["k_moi"] * d["L"], h["k_moi"] * dt.T, le=ts["le"])
        doan.append({"video_tu": _r(mep["tu"]), "video_den": _r(mep["den"]),
                     "clip_tu": _r((mep["tu"] - h["A_moi"]) / h["k_moi"]),
                     "clip_den": _r((mep["den"] - h["A_moi"]) / h["k_moi"]),
                     "cach_dau": mep["cach_dau"], "cach_cuoi": mep["cach_cuoi"], "tho": [g0 + a, g0 + b]})
    t_doan = time.perf_counter() - t0
    m = d["m"]
    hop = [(x["video_tu"], x["video_den"]) for x in doan]
    t = {k: _r(v, 2) for k, v in {**d["t"], "doan_mep": t_doan}.items()}
    t["tong_khong_ke_nen"] = _r(sum(d["t"].values()) + t_doan, 2)
    if "nen" in d:
        t["nen_cung_video"] = _r(d["nen"]["giay"], 2)
        t["tong"] = _r(t["tong_khong_ke_nen"] + d["nen"]["giay"], 2)
    khoang_ho = [{"video_tu": doan[n]["video_den"], "video_den": doan[n + 1]["video_tu"],
                  "clip_tu": doan[n]["clip_den"], "clip_den": doan[n + 1]["clip_tu"]}
                 for n in range(len(doan) - 1) if doan[n + 1]["video_tu"] - doan[n]["video_den"] >= 2.0]
    return {
        "dong": d["i"], "clip": os.path.basename(m["duong_dan_kho"]),
        "engine": {k: _r(m[k]) if isinstance(m[k], float) else m[k]
                   for k in ("start_s", "vung_khop_s", "end_s", "matched_s", "clip_offset_s", "hashes")},
        "mo_hinh": {k: (_r(v, 6) if isinstance(v, float) else v) for k, v in mh.items()},
        "tham_so": {**ts, **{k: ng.get(k) for k in ("nguong_cao", "nguong_thap", "tu_lap", "muc_tu_lap",
                                                    "nguong_cao_nen_dong", "nguong_thap_nen_dong")}},
        "cua_so_s": [_r(d["W0"]), _r(d["W1"])], "do_dai_clip_s": _r(d["L"]),
        "can_chinh_tim_duoc": {"A_moi": _r(h["A_moi"], 4), "k_moi": _r(h["k_moi"], 6), "s": h["s"],
                               "d0_lech_tien_nghiem_khung": _r(h["d0"] - h["d_exp"], 2), "so_cap": h["so_cap"]},
        "so_hash": {k: h[k] for k in ("so_hash_clip_trong_cua_so", "so_hash_clip_khop", "so_hash_cua_so",
                                      "so_hash_cua_so_khop")},
        "doan": doan, "khoang_ho_trong_dong": khoang_ho,
        "tinh_chinh": ({"start_s": _r(h["A_moi"]), "vung_khop_s": doan[0]["video_tu"], "end_s": doan[-1]["video_den"],
                        "matched_s": _r(danh_gia.do_dai(hop)), "clip_offset_s": doan[0]["clip_tu"]} if doan else None),
        "giu_nguyen_engine": not doan,
        "trung_vung_engine_s": _r(danh_gia.do_dai(danh_gia.giao(hop, [(m["vung_khop_s"], m["end_s"])])) if hop
                                  else 0.0),
        "thoi_gian_s": t,
    }


def cat_giua(dong: list) -> list:
    """Chỗ cắt giữa: hai đoạn liên tiếp (theo video) của CÙNG clip nằm ở hai căn chỉnh khác nhau."""
    theo_clip: dict = {}
    for r in dong:
        for x in r["doan"]:
            theo_clip.setdefault(r["clip"], []).append((x, r["can_chinh_tim_duoc"]["A_moi"], r["dong"]))
    ra = []
    for clip, ds in theo_clip.items():
        ds.sort(key=lambda z: z[0]["video_tu"])
        for (a, Aa, ra_), (b, Ab, rb) in zip(ds, ds[1:]):
            ho = b["video_tu"] - a["video_den"]
            if abs(Aa - Ab) > 1.0 and -2.0 <= ho <= 300.0:
                ra.append({"clip": clip, "dong_truoc": ra_, "dong_sau": rb,
                           "video_tu": a["video_den"], "video_den": b["video_tu"], "video_chen_s": _r(ho),
                           "clip_tu": a["clip_den"], "clip_den": b["clip_tu"],
                           "clip_bo_s": _r(b["clip_tu"] - a["clip_den"])})
    return ra


def cat_giua_that(st: dict) -> list:
    doan = sorted(st["doan"], key=lambda d: d["video_tu"])
    return [{"video_tu": a["video_den"], "video_den": b["video_tu"], "video_chen_s": _r(b["video_tu"] - a["video_den"]),
             "clip_tu": a["clip_den"], "clip_den": b["clip_tu"], "clip_bo_s": _r(b["clip_tu"] - a["clip_den"])}
            for a, b in zip(doan, doan[1:])]


def cham(st: dict, dong: list) -> dict:
    """Sai số mép từng đoạn sự thật (đoạn tinh chỉnh giao dài nhất) + precision/recall theo giây của hợp các đoạn."""
    that = sorted(st["doan"], key=lambda d: d["video_tu"])
    doan = [x for r in dong for x in r["doan"]]
    hop = [(x["video_tu"], x["video_den"]) for x in doan]
    p, r_ = danh_gia.precision_recall(hop, [(d["video_tu"], d["video_den"]) for d in that])
    tung = []
    for d in that:
        def giao(x, d=d):
            return danh_gia.do_dai(danh_gia.giao([(x["video_tu"], x["video_den"])], [(d["video_tu"], d["video_den"])]))
        tot = max(doan, key=giao, default=None)
        if tot is None or giao(tot) <= 0:
            tung.append({"video_tu_that": d["video_tu"], "video_den_that": _r(d["video_den"]), "tim_thay": False})
            continue
        tung.append({"video_tu_that": d["video_tu"], "video_den_that": _r(d["video_den"]), "tim_thay": True,
                     "video_tu": tot["video_tu"], "video_den": tot["video_den"],
                     "sai_so_dau_s": _r(tot["video_tu"] - d["video_tu"]),
                     "sai_so_cuoi_s": _r(tot["video_den"] - d["video_den"]),
                     "sai_so_clip_tu_s": _r(tot["clip_tu"] - d["clip_tu"]),
                     "sai_so_clip_den_s": _r(tot["clip_den"] - d["clip_den"]),
                     "cach_dau": tot["cach_dau"], "cach_cuoi": tot["cach_cuoi"]})
    co = [x for x in tung if x["tim_thay"]]
    return {"precision_giay": p, "recall_giay": r_, "so_doan_tinh_chinh": len(doan), "so_doan_that": len(that),
            "tung_doan_that": tung,
            "sai_so_dau_max_abs_s": _r(max((abs(x["sai_so_dau_s"]) for x in co), default=None)),
            "sai_so_cuoi_max_abs_s": _r(max((abs(x["sai_so_cuoi_s"]) for x in co), default=None))}


def muc_trong_doan(d: dict, st: dict, w: int) -> dict:
    """Mức tương đồng trong đoạn thật CỦA dòng (đoạn thật giao vùng engine báo; bỏ 2 s mỗi mép) — để so với ngưỡng."""
    h, m = d["h"], d["m"]
    giay = h["giay0"] + np.arange(len(h["n_clip"])) + 0.5
    trong = np.zeros(len(giay), bool)
    for x in st["doan"]:
        if min(x["video_den"], m["end_s"]) > max(x["video_tu"], m["vung_khop_s"]):
            trong |= (giay >= x["video_tu"] + 2) & (giay <= x["video_den"] - 2)
    tung = _tung_giay(h["n_clip"], h["n_khop"])
    tv = dt.trung_vi_truot(tung, w)
    tv[np.isnan(tung)] = np.nan
    gop = dt.ty_le_truot(h["n_clip"], h["n_khop"], w)
    ra = {"so_giay": int(trong.sum())}
    for ten, x in (("trung_vi", tv), ("gop", gop)):
        v = x[trong & ~np.isnan(x)]
        if len(v):
            ra[ten] = {"p1": _r(np.percentile(v, 1), 4), "p5": _r(np.percentile(v, 5), 4), "p50": _r(np.median(v), 4)}
    return ra


def ghi_csv(path: str, d: dict, r: dict, st: dict) -> None:
    h, w = d["h"], d["ts"]["w"]
    tung = _tung_giay(h["n_clip"], h["n_khop"])
    tv = dt.trung_vi_truot(tung, w)
    tv[np.isnan(tung)] = np.nan                      # như tim_doan: giây không đủ hash clip giữ trống
    gop = dt.ty_le_truot(h["n_clip"], h["n_khop"], w)

    def o(x):
        return "" if np.isnan(x) else round(float(x), 4)

    def trong(ds, g):
        return int(any(x["video_tu"] < g + 1 and x["video_den"] > g for x in ds))
    with open(path, "w", encoding="utf-8", newline="") as f:
        cs = csv.writer(f)
        cs.writerow(["giay", "n_hash_clip", "n_hash_clip_khop", "tuong_dong", f"trung_vi_{w}s", f"ty_le_gop_{w}s",
                     "n_hash_video", "n_hash_video_khop", "trong_doan_tinh_chinh", "trong_doan_that"])
        for n in range(len(tung)):
            g = h["giay0"] + n
            cs.writerow([g, int(h["n_clip"][n]), int(h["n_khop"][n]), o(tung[n]), o(tv[n]), o(gop[n]),
                         int(h["n_cua_so"][n]), int(h["n_cua_so_khop"][n]), trong(r["doan"], g), trong(st["doan"], g)])


def tong_hop_loai(ho_so: list) -> dict:
    """Theo loại đường nền (cùng w = W_CHUNG): số hồ sơ, số giây, max từng giây / trung vị trượt / tỉ lệ gộp."""
    ra: dict = {}
    for x in ho_so:
        loai = x["loai"]
        if loai == "khong_clip_S0":
            loai += "_nhac_co_nhip" if x["clip"].startswith("goc_S6") else "_not_ngau_nhien"
        tk = _thong_ke(x["_n"], x["_k"], W_CHUNG)
        if not tk.get("so_giay"):
            continue
        g = ra.setdefault(loai, {"so_ho_so": 0, "so_giay": 0, "max_tung_giay": 0.0, "max_trung_vi": 0.0,
                                 "max_gop": 0.0, "max_ty_le_ca_ho_so": 0.0})
        g["so_ho_so"] += 1
        g["so_giay"] += tk["so_giay"]
        for k_ra, k_tk in (("max_tung_giay", "max_tung_giay"), ("max_trung_vi", "max_trung_vi"), ("max_gop", "max_gop"),
                           ("max_ty_le_ca_ho_so", "ty_le_gop_ca_ho_so")):
            g[k_ra] = max(g[k_ra], tk[k_tk])
    return ra


def _gon(ho_so: list, w: int) -> list:
    return [{**{k: v for k, v in x.items() if not k.startswith("_")}, **_thong_ke(x["_n"], x["_k"], w)} for x in ho_so]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    t_bat_dau = time.perf_counter()
    os.makedirs(KET_QUA, exist_ok=True)
    tam = os.path.join(KET_QUA, "_tam")
    os.makedirs(tam, exist_ok=True)

    # Pha 1 — hồ sơ ở căn chỉnh của từng dòng ĐƯỢC CHẤP NHẬN + đường nền.
    du_lieu: dict = {}
    for S in THU_TU:
        if S == "S0":
            continue
        st, ket = (_doc_json(os.path.join(BO_THU, S, x)) for x in ("su_that.json", "ket_qua_engine.json"))
        dong = ket["dong_cho_clip"]["matches"] + ket["dong_clip_khac"]["matches"]
        x = du_lieu[S] = {"st": st, "ket": ket, "dong": [], "chi_engine": [], "loai": []}
        for i, m in enumerate(dong):
            d = pha1_dong(S, i, m, ket, st, "de_xuat", tam)
            d["nen"] = nen_cung_video(d, ket, st, tam)
            d["tu_giong"] = tu_giong(d)
            x["dong"].append(d)
            if d["mh"]["nguon"] != mo_hinh(m, ket, "chi_engine")["nguon"]:
                x["chi_engine"].append(pha1_dong(S, i, m, ket, st, "chi_engine", tam))
        for i, m in enumerate(ket["dong_cho_clip"]["matches_loai"]):   # CHỈ tham khảo: dòng bị loại không là kết quả
            d = pha1_dong(S, i, m, ket, st, "de_xuat", tam)
            d["nen"] = nen_cung_video(d, ket, st, tam)
            x["loai"].append(d)
        print(f"[pha 1] {S}: {len(dong)} dòng chấp nhận, {len(x['loai'])} dòng bị loại — " + "; ".join(
            f"A {d['h']['A_moi']:.3f} khớp {d['h']['so_hash_clip_khop']}/{d['h']['so_hash_clip_trong_cua_so']} "
            f"λ {d['ts']['hash_khop_moi_giay']} w {d['ts']['w']} nền {len(d['nen']['ho_so'])} hồ sơ"
            for d in x["dong"]), flush=True)
    t0 = time.perf_counter()
    s0 = nen_s0(tam)
    print(f"[pha 1] S0: {len(s0)} hồ sơ đường nền ({time.perf_counter() - t0:.0f} s)", flush=True)

    # Pha 2 — ngưỡng. Theo dòng: từ nền cùng video của dòng (cửa sổ w của dòng). Chung: mọi nền (a + b), w = W_CHUNG.
    tat_ca_nen = [p for x in du_lieu.values() for d in x["dong"] + x["loai"] for p in d["nen"]["ho_so"]] + s0
    ng_chung = nguong_tu_nen(tat_ca_nen, W_CHUNG)
    ts_chung = {"w": W_CHUNG, "noi_ho": 2, "le": 5.0}
    print(f"[pha 2] ngưỡng chung (w {W_CHUNG}): {ng_chung}", flush=True)
    tu_giong_ca = [p for x in du_lieu.values() for d in x["dong"] for p in d["tu_giong"]]
    duong_nen = {
        "nguong_chung": ng_chung,
        "doan_gia_nguong_chung": {
            loai: doan_gia([p for p in tat_ca_nen + tu_giong_ca
                            if p["loai"] == loai and not p.get("cham_can_chinh_that")], ng_chung, W_CHUNG, 2)
            for loai in sorted({p["loai"] for p in tat_ca_nen + tu_giong_ca})},
        "theo_loai_w5": tong_hop_loai(tat_ca_nen + [p for p in tu_giong_ca if not p["cham_can_chinh_that"]]),
        "so_tu_giong_cham_can_chinh_that": sum(1 for p in tu_giong_ca if p["cham_can_chinh_that"]),
        "theo_dong": [],
        "S0": _gon(s0, W_CHUNG),
    }
    chung_theo_w: dict = {}
    for S, x in du_lieu.items():
        for d in x["dong"] + x["loai"]:
            w = d["ts"]["w"]
            if w not in chung_theo_w:
                chung_theo_w[w] = nguong_tu_nen(tat_ca_nen, w)
            ng = nguong_tu_nen(d["nen"]["ho_so"], w)
            if not ng["so_ho_so_nen"]:
                ng = dict(chung_theo_w[w])
            tg = [p for p in d.get("tu_giong", []) if not p["cham_can_chinh_that"]]
            muc_lap = max((_thong_ke(p["_n"], p["_k"], w).get("max_trung_vi") or 0.0 for p in tg), default=0.0)
            ng["muc_tu_lap"] = muc_lap
            ng["tu_lap"] = bool(muc_lap >= TU_LAP)
            if ng["tu_lap"]:
                ng["nguong_cao_nen_dong"], ng["nguong_thap_nen_dong"] = ng["nguong_cao"], ng["nguong_thap"]
                ng["nguong_cao"] = max(ng["nguong_cao"], chung_theo_w[w]["nguong_cao"])
                ng["nguong_thap"] = max(ng["nguong_thap"], chung_theo_w[w]["nguong_thap"])
            d["ng"] = ng
            cung_clip = [p for p in s0 if p["clip"] == os.path.basename(d["m"]["duong_dan_kho"])]
            duong_nen["theo_dong"].append({
                "nguon": f"{S} dòng {d['i']}" + (" (bị loại)" if any(d is z for z in x["loai"]) else ""),
                "tham_so": d["ts"], "nguong": d["ng"], "khoang_nen_s": d["nen"]["khoang"],
                "doan_gia_tren_nen_cung_video": doan_gia(d["nen"]["ho_so"], d["ng"], d["ts"]["w"], d["ts"]["noi_ho"]),
                "doan_gia_tren_S0_cung_clip": (doan_gia(cung_clip, d["ng"], w, d["ts"]["noi_ho"]) if cung_clip
                                               else "S0 không có clip này"),
                "doan_gia_tren_S0_moi_clip": doan_gia(s0, d["ng"], w, d["ts"]["noi_ho"]),
                "tu_giong": _gon(d.get("tu_giong", []), d["ts"]["w"]),
                "doan_gia_tu_giong": {
                    loai: doan_gia([p for p in tg if p["loai"] == loai], d["ng"], d["ts"]["w"], d["ts"]["noi_ho"])
                    for loai in sorted({p["loai"] for p in tg})},
                "so_tu_giong_cham_can_chinh_that": sum(1 for p in d.get("tu_giong", []) if p["cham_can_chinh_that"]),
            })
    _ghi_json(os.path.join(KET_QUA, "duong_nen.json"), duong_nen)

    # Pha 3 — đoạn, mép, chấm.
    tong = {"nguong_chung": ng_chung,
            "tham_so": {"TIM_D_khung": TIM_D, "luoi_do_doc": [LUOI_S[0], LUOI_S[-1], len(LUOI_S)],
                        "cua_so_khop_khung": dt.CUA_SO_KHOP, "doan_ngan_nhat_s": MIN_DAI,
                        "dem_cua_so": "10 % độ dài clip + 30 s", "w_chung": W_CHUNG}, "kich_ban": []}
    for S in THU_TU:
        if S == "S0":
            tong["kich_ban"].append({"kich_ban": "S0", "so_dong_engine": 0, "ghi_chu":
                                     "Không có kết quả được chấp nhận → Cách B không chạy; video dùng làm đường nền."})
            continue
        x = du_lieu[S]
        st = x["st"]
        os.makedirs(os.path.join(KET_QUA, S), exist_ok=True)
        dong = [pha3_dong(d, d["ng"], d["ts"]) for d in x["dong"]]
        for d, r in zip(x["dong"], dong):
            ghi_csv(os.path.join(KET_QUA, S, f"ho_so_dong{d['i']}.csv"), d, r, st)
        chung = [pha3_dong(d, ng_chung, ts_chung) for d in x["dong"]]
        kq = {"kich_ban": S, "mo_ta": st["mo_ta"], "doan_su_that": st["doan"], "so_dong_engine": len(dong),
              "dong": dong, "cham": cham(st, dong) if dong else None,
              "cat_giua_tim_duoc": cat_giua(dong), "cat_giua_that": cat_giua_that(st),
              "muc_trong_doan_that": [muc_trong_doan(d, st, d["ts"]["w"]) for d in x["dong"]],
              "bien_the_nguong_chung": {"cham": cham(st, chung) if chung else None,
                                        "doan": [z for r in chung for z in r["doan"]]},
              "engine_sai_so": {k: v for k, v in _doc_json(os.path.join(BO_THU, S, "sai_so.json")).items()
                                if k in ("sai_so_dau_clip_s", "sai_so_dau_vung_s", "sai_so_cuoi_s", "precision_giay",
                                         "recall_giay", "precision_giay_tu_vung_khop", "recall_giay_tu_vung_khop")},
              "thoi_gian_quet_engine_s": x["ket"]["thoi_gian_quet_s"]}
        kq["do_nhay_nguong"] = {}
        for he in ((0.5, 2.0) if x["dong"] else ()):
            nh = [pha3_dong(d, {**d["ng"], "nguong_cao": d["ng"]["nguong_cao"] * he,
                                "nguong_thap": d["ng"]["nguong_thap"] * he}, d["ts"]) for d in x["dong"]]
            c_nh = cham(st, nh)
            kq["do_nhay_nguong"][f"x{he:g}"] = {k: c_nh[k] for k in ("precision_giay", "recall_giay",
                                                                      "sai_so_dau_max_abs_s", "sai_so_cuoi_max_abs_s",
                                                                      "so_doan_tinh_chinh")}
        if x["chi_engine"]:
            for d in x["chi_engine"]:
                d["ts"] = tham_so_dong(d)
                d["ng"] = nguong_tu_nen(x["dong"][d["i"]]["nen"]["ho_so"], d["ts"]["w"])
                if not d["ng"]["so_ho_so_nen"]:
                    d["ng"] = nguong_tu_nen(tat_ca_nen, d["ts"]["w"])
            ce = [pha3_dong(d, d["ng"], d["ts"]) for d in x["chi_engine"]]
            kq["bien_the_chi_engine"] = {"ghi_chu": "Chỉ tin hệ số tốc độ của lượt engine (không đo độ trôi).",
                                         "dong": ce, "cham": cham(st, ce)}
        if x["loai"]:
            lo = [pha3_dong(d, d["ng"], d["ts"]) for d in x["loai"]]
            kq["tham_khao_dong_bi_loai"] = {"ghi_chu": "Dòng engine đã LOẠI — không thành kết quả; chỉ đo tham khảo.",
                                           "dong": lo, "cham": cham(st, lo)}
        _ghi_json(os.path.join(KET_QUA, S, "ket_qua_cach_b.json"), kq)
        c, cc = kq["cham"], kq["bien_the_nguong_chung"]["cham"]
        print(f"[pha 3] {S}: " + ("không có dòng chấp nhận" if not c else
              f"P {c['precision_giay']} R {c['recall_giay']} — " + "; ".join(
                  f"[{z['video_tu']}, {z['video_den']}] ({z['cach_dau']}/{z['cach_cuoi']})"
                  for r in dong for z in r["doan"]) + " | thật " + "; ".join(
                  f"[{z['video_tu']}, {z['video_den']}]" for z in st["doan"])
              + f" | {sum(r['thoi_gian_s']['tong'] for r in dong):.1f} s"
              + f" | ngưỡng chung P {cc['precision_giay']} R {cc['recall_giay']}"), flush=True)
        tong["kich_ban"].append(
            {k: kq[k] for k in ("kich_ban", "doan_su_that", "so_dong_engine", "cham", "cat_giua_tim_duoc",
                                "cat_giua_that", "muc_trong_doan_that", "engine_sai_so", "thoi_gian_quet_engine_s",
                                "do_nhay_nguong")}
            | {"bien_the_nguong_chung_cham": cc,
               "dong": [{k: r[k] for k in ("dong", "engine", "tinh_chinh", "doan", "mo_hinh", "tham_so",
                                           "can_chinh_tim_duoc", "so_hash", "thoi_gian_s", "giu_nguyen_engine",
                                           "khoang_ho_trong_dong")} for r in dong]}
            | ({"bien_the_chi_engine_cham": kq["bien_the_chi_engine"]["cham"],
                "bien_the_chi_engine_doan": [z for r in kq["bien_the_chi_engine"]["dong"] for z in r["doan"]]}
               if "bien_the_chi_engine" in kq else {})
            | ({"tham_khao_dong_bi_loai_cham": kq["tham_khao_dong_bi_loai"]["cham"],
                "tham_khao_dong_bi_loai_doan": [z for r in kq["tham_khao_dong_bi_loai"]["dong"] for z in r["doan"]]}
               if "tham_khao_dong_bi_loai" in kq else {}))
    ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    tong["moi_truong"] = {"python": sys.version.split()[0], "numpy": np.__version__, "ffmpeg": ff,
                          "ma_san_pham_head": subprocess.run(["git", "-C", MA, "rev-parse", "HEAD"],
                                                             capture_output=True, text=True).stdout.strip(),
                          "thoi_gian_chay_toan_bo_s": round(time.perf_counter() - t_bat_dau, 1)}
    _ghi_json(os.path.join(KET_QUA, "tong_hop_cach_b.json"), tong)
    shutil.rmtree(tam, ignore_errors=True)
    print(f"Xong trong {time.perf_counter() - t_bat_dau:.0f} s → {KET_QUA}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
