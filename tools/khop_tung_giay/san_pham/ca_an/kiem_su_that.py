# -*- coding: utf-8 -*-
"""Đo lại sự thật của một CA ẨN (P-8) TỪ AUDIO trên đĩa — không gọi engine, audfprint, tinh_chinh_moc hay Cách C.

Đầu vào: thư mục ca có ``su_that.json`` (các đoạn khai = GIẢ THUYẾT), ``kho/`` và file video. Với mỗi đoạn khai:
  1. ánh xạ: dọc đoạn, cứ 2 s một cửa sổ clip (1 s; 0,05 s khi he_so ≠ 1 vì atempo chép lại từng khung ngắn) tìm đỉnh
     tương quan chuẩn hoá trong ±50 ms quanh chỗ dự đoán → độ lệch (ms) và mức tương quan; he_so ≠ 1 thêm độ dốc của
     độ lệch theo giây clip (ánh xạ có thật sự tuyến tính với hệ số khai không);
  2. biên độ G = hình chiếu video lên clip đã ánh xạ (he_so = 1), cả đoạn và từng phần ba (clip còn nguyên dưới lớp đè?);
  3. mép: he_so = 1 → CUSUM trên tích mẫu p = video·clip — mép = chỗ tổng Σ(p − G·clip²/2) đổi chiều, chính xác tới
     mẫu, và rơi đúng TÂM dốc khi mép là chuyển mờ tuyến tính; he_so ≠ 1 → tương quan cửa sổ 0,05 s trượt 5 ms, mép =
     chỗ vượt nửa mức trong đoạn;
  4. clip và video cùng là WAV: dò bản sao NGUYÊN MẪU (mẫu int16 trùng tuyệt đối) → các đoạn trùng, mép tới 1 mẫu;
     đoạn trùng KHÔNG thuộc đoạn khai nào, lệch căn chỉnh, hay dài hơn đoạn khai = sự thật khai sai/thiếu;
  5. dò toàn video (hạ mẫu ×4, cửa sổ clip 4 s ở nhiều giây clip, cả giây clip không dùng) → đỉnh tương quan xa mọi
     chỗ dự đoán = clip xuất hiện ở chỗ không khai.
Kết luận «khop» khi mọi phép trong dung sai (``DUNG_SAI``), không thì «XEM LAI» kèm lý do.

Chạy riêng (ghi lại ``kiem_su_that`` vào su_that.json; dung_ca.py tự gọi sau khi dựng):
  <venv python> -B -X utf8 kiem_su_that.py [A01 ...]       # không đối số = mọi ca trong RA
  <venv python> -B -X utf8 kiem_su_that.py --tu-kiem        # tự kiểm: ca nhỏ đúng → khop, khai lệch 0,2 s → XEM LAI
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import wave

sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
from scipy import signal  # noqa: E402

SR = 22050
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\ca_an"
TIM_S = 0.05               # tìm đỉnh tương quan trong ±50 ms quanh chỗ dự đoán
MEP_NUA_S = 1.5            # cửa sổ đo mép: ±1,5 s quanh mép khai
DUNG_SAI = {
    "lech_ms_wav": 1.0,        # trung vị độ lệch ánh xạ, clip + video đều PCM
    "lech_ms_nen": 3.0,        # một phía qua codec (Opus/AAC)
    "lech_ms_toc": 5.0,        # he_so ≠ 1 (atempo)
    "doc_ms_100s": 20.0,       # độ dốc độ lệch theo giây clip (he_so ≠ 1)
    "mep_s_wav": 0.010, "mep_s_nen": 0.020, "mep_s_toc": 0.050, "mep_mo_s": 0.050,
    "ncc_toi_thieu": 0.3,      # trung vị tương quan dọc đoạn
    "dinh_la_toi_da": 0.5,     # đỉnh tương quan xa mọi chỗ khai phải dưới mức này
    "bien_do_phan_ba": 0.8,    # G phần ba yếu nhất ≥ 0,8 × G phần ba mạnh nhất
}


def _i(giay: float) -> int:
    return int(round(giay * SR))


def doc_i16(path: str):
    """Mẫu int16 của WAV mono 22050 Hz 16 bit; định dạng khác → None."""
    if not path.lower().endswith(".wav"):
        return None
    with wave.open(path, "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, SR):
            return None
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def doc_am(path: str) -> np.ndarray:
    """Mọi định dạng → float32 mono 22050 Hz thang 1/32768. Khác WAV thì FFmpeg giải mã TỪ ĐẦU file (không tua)."""
    i16 = doc_i16(path)
    if i16 is not None:
        return i16.astype(np.float32) / 32768.0
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", path, "-map", "0:a:0",
                        "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def ncc_tim(cw: np.ndarray, v: np.ndarray, i_du: int, tim: int):
    """Đỉnh tương quan chuẩn hoá của cửa sổ clip ``cw`` đặt vào video quanh mẫu ``i_du`` (±``tim`` mẫu).
    Trả (lệch mẫu, nội suy parabol; dương = video trễ hơn dự đoán, ncc) hoặc None khi ra ngoài video."""
    m = len(cw)
    lo, hi = i_du - tim, i_du + tim + m
    if m < 2 or lo < 0 or hi > len(v):
        return None
    seg = v[lo:hi].astype(np.float64)
    a = cw.astype(np.float64)
    a -= a.mean()
    r = signal.correlate(seg, a, mode="valid")
    c1 = np.concatenate([[0.0], np.cumsum(seg)])
    c2 = np.concatenate([[0.0], np.cumsum(seg * seg)])
    s1, s2 = c1[m:] - c1[:-m], c2[m:] - c2[:-m]
    nr = r / (np.sqrt(np.maximum(s2 - s1 * s1 / m, 1e-12)) * np.sqrt(a @ a) + 1e-12)
    j = int(np.argmax(nr))
    dj = 0.0
    if 0 < j < len(nr) - 1:
        cong = nr[j - 1] - 2 * nr[j] + nr[j + 1]
        if cong < 0:
            dj = 0.5 * (nr[j - 1] - nr[j + 1]) / cong
    return lo + j + dj - i_du, float(nr[j])


def _vi_tri_video(d: dict, ct: float) -> float:
    return d["video_tu"] + (ct - d["clip_tu"]) / d["he_so"]


def kiem_anh_xa(c: np.ndarray, v: np.ndarray, d: dict) -> dict:
    """(1) Độ lệch ánh xạ clip → video dọc đoạn khai."""
    k = d["he_so"]
    w = 1.0 if k == 1.0 else 0.05
    moc, lech, ncc = [], [], []
    for ct in np.arange(d["clip_tu"] + 0.5, d["clip_den"] - 0.5 - w, 2.0):
        kq = ncc_tim(c[_i(ct):_i(ct) + _i(w)], v, _i(_vi_tri_video(d, ct)), _i(TIM_S))
        if kq:
            moc.append(float(ct))
            lech.append(kq[0] / SR)
            ncc.append(kq[1])
    if not moc:
        return {"so_moc": 0, "cua_so_s": w}
    moc, lech, ncc = np.array(moc), np.array(lech), np.array(ncc)
    tot = ncc >= 0.5 * np.median(ncc)          # bỏ cửa sổ rơi vào chỗ clip bị che (vd. im lặng)
    ra = {"so_moc": int(len(moc)), "cua_so_s": w, "ncc_trung_vi": round(float(np.median(ncc)), 3),
          "ncc_p5": round(float(np.percentile(ncc, 5)), 3), "so_moc_tot": int(tot.sum()),
          "lech_trung_vi_ms": round(1000 * float(np.median(lech[tot])), 3),
          "lech_p95_tuyet_doi_ms": round(1000 * float(np.percentile(np.abs(lech[tot]), 95)), 3)}
    if k != 1.0 and tot.sum() >= 10:
        p = np.polyfit(moc[tot], lech[tot], 1)
        ra["doc_ms_moi_100s"] = round(1e5 * float(p[0]), 3)
    return ra


def bien_do(c: np.ndarray, v: np.ndarray, delta: int, t0: float, t1: float):
    """(2) Biên độ clip trong video trên [t0, t1) (giây video), ánh xạ video mẫu t ↔ clip mẫu t − delta."""
    a, b = _i(t0), _i(t1)
    tc = np.arange(a, b) - delta
    if b <= a or tc[0] < 0 or tc[-1] >= len(c):
        return None
    cm = c[tc].astype(np.float64)
    return round(float(v[a:b].astype(np.float64) @ cm / (cm @ cm + 1e-12)), 4)


def mep_cusum(c: np.ndarray, v: np.ndarray, delta: int, e: float, phia: str, G: float) -> tuple:
    """(3) Mép (giây video) của đoạn he_so = 1 quanh mép khai ``e``: chỗ Σ(video·clip − G·clip²/2) đổi chiều.
    Trả (mép, khoảng_từ, khoảng_đến): khoảng = mọi vị trí có tổng kém đỉnh dưới «bằng chứng 5 ms» (G/2 × công suất clip
    trung bình × 5 ms) — mép rơi chỗ clip gần im (đuôi bao nốt) thì khoảng rộng ra, nói thật độ mơ hồ vật lý.
    Ngoài phạm vi clip (mép trùng đầu/cuối clip) tích = 0 → hoà; mép lấy điểm hoà phía TRONG đoạn."""
    a, b = max(0, _i(e - MEP_NUA_S)), min(len(v), _i(e + MEP_NUA_S))
    tc = np.arange(a, b) - delta
    ok = (tc >= 0) & (tc < len(c))
    cm = np.zeros(b - a)
    cm[ok] = c[tc[ok]]
    x = v[a:b].astype(np.float64) * cm - 0.5 * G * cm * cm
    if phia == "dau":                        # F[t] = Σ_{s ≥ t} x: lớn nhất ở mẫu đầu đoạn
        F, bu = np.cumsum(x[::-1])[::-1], 0
        j = len(F) - 1 - int(np.argmax(F[::-1]))
    else:                                    # F[t] = Σ_{s ≤ t} x: lớn nhất ở mẫu cuối đoạn → mép = t + 1
        F, bu = np.cumsum(x), 1
        j = int(np.argmax(F))
    gan = np.flatnonzero(F >= F[j] - 0.5 * G * float(np.mean(cm[ok] ** 2) if ok.any() else 0.0) * 0.005 * SR)
    return (a + j + bu) / SR, (a + int(gan[0]) + bu) / SR, (a + int(gan[-1]) + bu) / SR


def mep_ncc(c: np.ndarray, v: np.ndarray, d: dict, e: float, phia: str, lech_s: float, muc_trong: float):
    """(3) Mép của đoạn he_so ≠ 1: tương quan cửa sổ 0,05 s (tâm t) trượt 5 ms; mép = chỗ vượt nửa mức trong đoạn
    (≥ 90 % của 0,2 s kế tiếp phía trong ở trên ngưỡng)."""
    w, k = 0.05, d["he_so"]
    luoi = np.arange(e - 1.0, e + 1.0, 0.005)
    x = np.full(len(luoi), np.nan)
    for n, t in enumerate(luoi):
        tv0 = t - w / 2
        ct0 = d["clip_tu"] + (tv0 - d["video_tu"]) * k
        if 0 <= ct0 and _i(ct0) + _i(w) <= len(c):
            kq = ncc_tim(c[_i(ct0):_i(ct0) + _i(w)], v, _i(tv0 + lech_s), _i(0.003))
            if kq:
                x[n] = kq[1]
    tren = np.nan_to_num(x, nan=-1.0) >= 0.5 * muc_trong
    if phia == "dau":
        for n in range(len(luoi)):
            if tren[n:n + 40].mean() > 0.9:
                return round(float(luoi[n]), 4)
    else:
        for n in range(len(luoi) - 1, -1, -1):
            if tren[max(0, n - 39):n + 1].mean() > 0.9:
                return round(float(luoi[n]), 4)
    return None


def ban_sao_nguyen_mau(c16: np.ndarray, v16: np.ndarray, buoc_s: float) -> list:
    """(4) Các đoạn video trùng TỪNG MẪU int16 với clip: dò mẫu 64 mẫu mỗi ``buoc_s`` giây clip, gom độ lệch, so cả đoạn."""
    vb, dem = v16.tobytes(), {}
    for j in range(0, len(c16) - 64, max(1, _i(buoc_s))):
        mau = c16[j:j + 64].tobytes()
        pos, n = vb.find(mau), 0
        while pos != -1 and n < 50:
            if pos % 2 == 0:
                dem[pos // 2 - j] = dem.get(pos // 2 - j, 0) + 1
            pos, n = vb.find(mau, pos + 1), n + 1
    ra = []
    for dl in sorted(dem):
        j0, j1 = max(0, -dl), min(len(c16), len(v16) - dl)
        if j1 <= j0:
            continue
        dd = np.diff(np.concatenate([[0], (c16[j0:j1] == v16[j0 + dl:j1 + dl]).astype(np.int8), [0]]))
        for a, b in zip(np.flatnonzero(dd == 1).tolist(), np.flatnonzero(dd == -1).tolist()):
            if b - a >= SR // 2:
                ra.append({"video_tu": (j0 + a + dl) / SR, "video_den": (j0 + b + dl) / SR,
                           "clip_tu": (j0 + a) / SR, "clip_den": (j0 + b) / SR, "delta_mau": int(dl)})
    return ra


def do_toan_video(c: np.ndarray, v: np.ndarray, doan_clip: list, moi_doan: list, so_moc_ngoai: int = 3) -> dict:
    """(5) Hạ mẫu ×4; tương quan cửa sổ clip 4 s với TOÀN video ở 3 giây clip mỗi đoạn khai + vài giây clip không dùng.
    Đỉnh ≥ 0,3 cách mọi chỗ dự đoán > 1 s: nằm TRONG một đoạn khai (``moi_doan``, mọi clip) = «bóng» (clip tự giống
    mình, vd. trống mẫu cố định của nhạc có nhịp lặp mỗi ô nhịp) — chỉ báo; nằm NGOÀI mọi đoạn khai = «đỉnh lạ».
    Lọc thông cao 400 Hz trước khi hạ mẫu: kick của am_thanh_lap là MỘT mẫu tất định chung mọi seed (50 Hz) — không lọc
    thì mọi nền nhạc có nhịp «giống» clip nhạc có nhịp tới 0,85 dù không chứa clip."""
    q = 4
    sr4 = SR / q
    sos = signal.butter(4, 400.0, "highpass", fs=SR, output="sos")
    vd = signal.decimate(signal.sosfiltfilt(sos, v.astype(np.float64)), q, ftype="fir", zero_phase=True)
    m = int(4 * sr4)
    c1 = np.concatenate([[0.0], np.cumsum(vd)])
    c2 = np.concatenate([[0.0], np.cumsum(vd * vd)])
    s1, s2 = c1[m:] - c1[:-m], c2[m:] - c2[:-m]
    chuan = np.sqrt(np.maximum(s2 - s1 * s1 / m, 1e-12))
    dai_c = len(c) / SR
    moc = [float(x) for d in doan_clip for x in np.linspace(d["clip_tu"] + 1.0, max(d["clip_tu"] + 1.0,
                                                                                 d["clip_den"] - 5.0), 3)]
    ngoai = [float(x) for x in np.linspace(1.0, dai_c - 5.0, 40)
             if all(not (d["clip_tu"] - 5.0 <= x <= d["clip_den"]) for d in doan_clip)]
    if ngoai:
        moc += [ngoai[int(n)] for n in np.linspace(0, len(ngoai) - 1, min(so_moc_ngoai, len(ngoai)))]
    ket, dinh_la, bong = [], [], []
    for ct in moc:
        r = None
        for pha in range(q):                 # lưới hạ mẫu của video và cửa sổ clip lệch nhau tới q−1 mẫu: thử cả q pha
            i_ct = _i(ct) + pha
            a0 = i_ct - min(i_ct, 2048) // q * q
            wd = signal.decimate(signal.sosfiltfilt(sos, c[a0:i_ct + _i(4.0) + 2048].astype(np.float64)), q,
                                 ftype="fir", zero_phase=True)
            tpl = wd[(i_ct - a0) // q:(i_ct - a0) // q + m]
            if len(tpl) < m:
                break
            tpl = tpl - tpl.mean()
            rr = signal.fftconvolve(vd, tpl[::-1], mode="valid") / (chuan * np.sqrt(tpl @ tpl) + 1e-12)
            r = rr if r is None else np.maximum(r, rr)
        if r is None or len(tpl) < m:
            continue
        du = [_vi_tri_video(d, ct) for d in doan_clip if d["clip_tu"] <= ct <= d["clip_den"] - 4.0]
        tai_du = []
        for t in du:
            j = int(round(t * sr4))
            vung = r[max(0, j - int(0.05 * sr4)): j + int(0.05 * sr4) + 1]
            tai_du.append(round(float(vung.max()), 3) if len(vung) else None)
        xa = [{"giay_video": round(p / sr4, 2), "ncc": round(float(r[p]), 3), "giay_clip": round(ct, 2)}
              for p in signal.find_peaks(r, height=0.3, distance=int(sr4))[0]
              if all(abs(p / sr4 - t) > 1.0 for t in du)]
        trong = [x for x in xa if any(d["video_tu"] <= x["giay_video"] <= d["video_den"] for d in moi_doan)]
        la = [x for x in xa if x not in trong]
        dinh_la += la
        bong += trong
        ket.append({"giay_clip": round(ct, 2), "trong_doan_khai": bool(du), "ncc_tai_cho_khai": tai_du,
                    "so_dinh_la": len(la), "so_bong": len(trong)})
    return {"moc": ket, "dinh_la": sorted(dinh_la, key=lambda x: -x["ncc"])[:20],
            "ncc_dinh_la_lon_nhat": max((x["ncc"] for x in dinh_la), default=None),
            "bong_trong_doan": sorted(bong, key=lambda x: -x["ncc"])[:10],
            "ncc_bong_lon_nhat": max((x["ncc"] for x in bong), default=None)}


def _la_mep_mo(st: dict, e: float):
    return next((m for m in st.get("mep_mo", []) if abs(m["t"] - e) < 1e-6), None)


def kiem(thu_muc: str) -> dict:
    with open(os.path.join(thu_muc, "su_that.json"), encoding="utf-8") as f:
        st = json.load(f)
    v_path = os.path.join(thu_muc, st["video"])
    v = doc_am(v_path)
    v16 = doc_i16(v_path)
    ra: dict = {"cach": "ánh xạ tương quan + biên độ + mép CUSUM/tương quan + bản sao nguyên mẫu + dò toàn video",
                "dung_sai": DUNG_SAI, "do_dai_video_giai_ma_s": round(len(v) / SR, 6), "doan": []}
    ly_do: list = []
    am_clip, c16_clip = {}, {}
    for ten in sorted({d["clip"] for d in st["doan"]}):
        p = os.path.join(thu_muc, "kho", ten)
        am_clip[ten], c16_clip[ten] = doc_am(p), doc_i16(p)
    for n, d in enumerate(st["doan"]):
        c, k = am_clip[d["clip"]], d["he_so"]
        pcm = v16 is not None and c16_clip[d["clip"]] is not None
        r: dict = {"doan_so": n, "clip": d["clip"], "anh_xa": kiem_anh_xa(c, v, d)}
        an = r["anh_xa"]
        lech_s = an.get("lech_trung_vi_ms", 0.0) / 1000.0
        if an["so_moc"] < 5:
            ly_do.append(f"đoạn {n}: chỉ {an['so_moc']} mốc ánh xạ")
        else:
            tol = DUNG_SAI["lech_ms_toc"] if k != 1.0 else DUNG_SAI["lech_ms_wav" if pcm else "lech_ms_nen"]
            if abs(an["lech_trung_vi_ms"]) > tol:
                ly_do.append(f"đoạn {n}: lệch ánh xạ {an['lech_trung_vi_ms']} ms > {tol}")
            if an["ncc_trung_vi"] < DUNG_SAI["ncc_toi_thieu"]:
                ly_do.append(f"đoạn {n}: tương quan trung vị {an['ncc_trung_vi']} thấp")
            if abs(an.get("doc_ms_moi_100s", 0.0)) > DUNG_SAI["doc_ms_100s"]:
                ly_do.append(f"đoạn {n}: độ lệch trôi {an['doc_ms_moi_100s']} ms/100 s")
        mep, khoang = [], [None, None]
        if k == 1.0:
            delta = _i(d["video_tu"] - d["clip_tu"]) + int(round(lech_s * SR))
            G = bien_do(c, v, delta, d["video_tu"] + 1.0, d["video_den"] - 1.0) or 0.0
            r["bien_do_G"] = G
            dai = d["video_den"] - d["video_tu"]
            if dai >= 12.0:
                ba = [bien_do(c, v, delta, d["video_tu"] + 1.0 + x * (dai - 2.0) / 3,
                              d["video_tu"] + 1.0 + (x + 1) * (dai - 2.0) / 3) for x in range(3)]
                r["bien_do_theo_phan_ba"] = ba
                if None not in ba and max(ba) > 0 and min(ba) < DUNG_SAI["bien_do_phan_ba"] * max(ba):
                    ly_do.append(f"đoạn {n}: biên độ clip theo phần ba không đều {ba}")
            if G > 0:
                kq_mep = [mep_cusum(c, v, delta, d["video_tu"], "dau", G),
                          mep_cusum(c, v, delta, d["video_den"], "cuoi", G)]
                mep = [round(x[0], 5) for x in kq_mep]
                khoang = [(x[1], x[2]) for x in kq_mep]
                r["mep_khoang_mo_ho_s"] = [[round(x[1], 5), round(x[2], 5)] for x in kq_mep]
            tol_sac = DUNG_SAI["mep_s_wav" if pcm else "mep_s_nen"]
        else:
            muc = an.get("ncc_trung_vi", 0.0)
            mep = [mep_ncc(c, v, d, d["video_tu"], "dau", lech_s, muc),
                   mep_ncc(c, v, d, d["video_den"], "cuoi", lech_s, muc)]
            tol_sac = DUNG_SAI["mep_s_toc"]
        r["mep_do_duoc_s"] = mep
        r["lech_mep_s"] = []
        for e, m_e, kh in zip((d["video_tu"], d["video_den"]), mep or (None, None), khoang):
            mo = _la_mep_mo(st, e)
            lech_mep = None if m_e is None else round(m_e - e, 5)
            r["lech_mep_s"].append(lech_mep)
            tol_e = DUNG_SAI["mep_mo_s"] if mo else tol_sac
            lo, hi = kh if kh else (m_e, m_e)
            if m_e is None or not (lo - tol_e <= e <= hi + tol_e):
                ly_do.append(f"đoạn {n}: mép {e} đo được {m_e} khoảng {kh} (dung sai {tol_e} s{', mép mờ' if mo else ''})")
        ra["doan"].append(r)

    if v16 is not None:                      # (4) bản sao nguyên mẫu
        ra["ban_sao_nguyen_mau"] = {}
        for ten, c16 in c16_clip.items():
            if c16 is None:
                continue
            runs = ban_sao_nguyen_mau(c16, v16, 2.0 if len(c16) <= 600 * SR else 10.0)
            ra["ban_sao_nguyen_mau"][ten] = runs
            khai = [d for d in st["doan"] if d["clip"] == ten and d["he_so"] == 1.0]
            for x in runs:
                cung = [d for d in khai if x["video_tu"] < d["video_den"] and d["video_tu"] < x["video_den"]]
                if not cung:
                    ly_do.append(f"bản sao nguyên mẫu ngoài mọi đoạn khai: {x}")
                    continue
                for d in cung:
                    if x["delta_mau"] != _i(d["video_tu"] - d["clip_tu"]):
                        ly_do.append(f"bản sao nguyên mẫu lệch căn chỉnh so với đoạn khai: {x}")
                    # mép mờ: trong dốc clip có mặt một phần, mẫu sát đầu trong của dốc có thể trùng sau lượng tử
                    # int16 → chỉ cấm tràn qua mép NGOÀI của vùng mờ
                    mo_dau, mo_cuoi = _la_mep_mo(st, d["video_tu"]), _la_mep_mo(st, d["video_den"])
                    du_dau = d["video_tu"] - (mo_dau["nua_rong"] if mo_dau else 0.0)
                    du_cuoi = d["video_den"] + (mo_cuoi["nua_rong"] if mo_cuoi else 0.0)
                    if x["video_tu"] < du_dau - 1.5 / SR or x["video_den"] > du_cuoi + 1.5 / SR:
                        ly_do.append(f"bản sao nguyên mẫu tràn ra ngoài đoạn khai: {x}")
        for r in ra["doan"]:                 # mép theo mẫu trùng (nếu có) cho từng đoạn khai
            d = st["doan"][r["doan_so"]]
            runs = [x for x in ra["ban_sao_nguyen_mau"].get(d["clip"], [])
                    if x["delta_mau"] == _i(d["video_tu"] - d["clip_tu"]) and x["video_tu"] < d["video_den"]
                    and d["video_tu"] < x["video_den"]]
            if runs:
                r["mau_trung"] = {"tu_s": min(x["video_tu"] for x in runs), "den_s": max(x["video_den"] for x in runs),
                                  "phu": round(sum(min(x["video_den"], d["video_den"]) - max(x["video_tu"], d["video_tu"])
                                                   for x in runs) / (d["video_den"] - d["video_tu"]), 6)}

    if st.get("vung_im_lang"):
        if v16 is None:
            ly_do.append("vùng im lặng khai nhưng video không phải WAV")
        else:
            ra["vung_im_lang_toan_mau_0"] = all(not v16[_i(a):_i(b)].any() for a, b in st["vung_im_lang"])
            if not ra["vung_im_lang_toan_mau_0"]:
                ly_do.append("vùng im lặng khai có mẫu khác 0")

    ra["do_toan_video"] = {}                 # (5)
    for ten, c in am_clip.items():
        dt = do_toan_video(c, v, [d for d in st["doan"] if d["clip"] == ten], st["doan"])
        ra["do_toan_video"][ten] = dt
        if dt["ncc_dinh_la_lon_nhat"] is not None and dt["ncc_dinh_la_lon_nhat"] >= DUNG_SAI["dinh_la_toi_da"]:
            mien = st.get("mien_dinh_la_ngoai_doan", "")
            if mien:                         # nền khai là GIỐNG clip (vd. cùng mẫu trống): chỉ báo, kèm lý do khai
                ra.setdefault("dinh_la_duoc_mien", []).append({"clip": ten, "ly_do": mien,
                                                               "ncc": dt["ncc_dinh_la_lon_nhat"]})
            else:
                ly_do.append(f"clip {ten}: đỉnh tương quan lạ {dt['ncc_dinh_la_lon_nhat']} ngoài mọi đoạn khai")
    ra["ly_do_xem_lai"] = ly_do
    ra["ket_luan"] = "khop" if not ly_do else "XEM LAI"
    return ra


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
    """Ca nhỏ dựng tại chỗ: khai đúng → khop (cả bản trộn ồn); khai lệch 0,2 s → XEM LAI."""
    rng = np.random.default_rng(5999)

    def giai(n_not):                          # chuỗi nốt sin 0,4 s bao Hanning (cùng kiểu _giai_dieu)
        t = np.arange(int(0.4 * SR)) / SR
        return np.concatenate([np.sin(2 * np.pi * f * t) * np.hanning(len(t)) for f in rng.uniform(200, 4000, n_not)])

    clip, nen = 0.6 * giai(150), 0.6 * giai(400)          # 60 s, 160 s
    with tempfile.TemporaryDirectory() as tam:
        os.makedirs(os.path.join(tam, "kho"))

        def ghi(p, x):
            with wave.open(p, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes((np.clip(x, -1, 1) * 32000).astype(np.int16).tobytes())

        ghi(os.path.join(tam, "kho", "c.wav"), clip)
        v = nen.copy()
        v[_i(40.0):_i(40.0) + _i(45.0)] = clip[_i(5.0):_i(50.0)]
        d = {"clip": "c.wav", "video_tu": 40.0, "video_den": 85.0, "clip_tu": 5.0, "clip_den": 50.0, "he_so": 1.0}
        for ten_ca, video, khai, mong in (
                ("dung", v, d, "khop"),
                ("tron_on", 0.8 * v + 0.05 * rng.standard_normal(len(v)), d, "khop"),
                ("khai_lech_0_2s", v, dict(d, video_tu=40.2, video_den=85.2), "XEM LAI"),
                ("khai_thua_cuoi_0_2s", v, dict(d, video_den=85.2, clip_den=50.2), "XEM LAI")):
            ghi(os.path.join(tam, "video.wav"), video)
            with open(os.path.join(tam, "su_that.json"), "w", encoding="utf-8") as f:
                json.dump({"video": "video.wav", "doan": [khai], "mep_mo": []}, f)
            kq = kiem(tam)
            print(f"tự kiểm {ten_ca}: {kq['ket_luan']} — mép {kq['doan'][0].get('mep_do_duoc_s')} "
                  f"lệch ánh xạ {kq['doan'][0]['anh_xa'].get('lech_trung_vi_ms')} ms {kq['ly_do_xem_lai'][:2]}")
            assert kq["ket_luan"] == mong, (ten_ca, kq["ly_do_xem_lai"])
    print("tự kiểm: ĐẠT")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--tu-kiem" in sys.argv:
        tu_kiem()
        return
    ds = [x for x in sys.argv[1:] if not x.startswith("--")] or sorted(
        x for x in os.listdir(RA) if os.path.isfile(os.path.join(RA, x, "su_that.json")))
    for ten in ds:
        kq = ghi_vao_su_that(os.path.join(RA, ten))
        print(f"[{ten}] {kq['ket_luan']} {kq['ly_do_xem_lai']}", flush=True)


if __name__ == "__main__":
    main()
