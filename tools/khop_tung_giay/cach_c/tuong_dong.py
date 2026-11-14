# -*- coding: utf-8 -*-
"""Cách C — «độ tương đồng phổ từng giây»: bước TINH CHỈNH độc lập với audfprint (nghiên cứu 14/11/2026).

Đầu vào: MỘT kết quả engine ĐÃ chấp nhận (các trường engine.Match: start_s, vung_khop_s, end_s, clip_offset_s) + file
clip gốc + file video. Bước này KHÔNG tạo, KHÔNG bỏ kết quả: chỉ đo lại trên căn chỉnh engine đưa và trả hồ sơ từng
giây; độ tương phản thấp thì trả «không tinh chỉnh» (nơi gọi giữ nguyên kết quả engine).

Cách làm (không gọi audfprint, không gọi mã sản phẩm):
1. FFmpeg → mono 11025 Hz; log-mel 40 dải 300–5000 Hz, khung 512 mẫu (46,4 ms), bước 128 (11,6 ms), sàn -60 dB.
2. Độ tương đồng của giây clip n = hệ số tương quan (Pearson) giữa miếng 3 s của clip đặt giữa giây n và miếng cùng
   cỡ của video, sau khi trừ trung bình TỪNG DẢI trong từng miếng (bù âm lượng, EQ; không phụ thuộc nội dung quanh
   clip); lấy đỉnh trong ±W (0,1 s) quanh vị trí dự đoán, nội suy parabol.
3. Neo = (clip_offset_s ↔ vung_khop_s) của chính kết quả. k ban đầu = clip_offset_s / (vung_khop_s − start_s) khi
   clip_offset_s ≥ 30 s (dấu của lượt bù tốc độ), không thì 1. Bắt nhịp: giây đầu tiên trong ±10 s quanh neo có đỉnh
   ≥ ngưỡng bám với cửa sổ rộng W0 (0,5 s). Từ đó đi từng giây, tiến rồi lùi; giây có đỉnh ≥ ngưỡng bám thì dời vị
   trí theo đỉnh và ước lại tốc độ (bình phương tối thiểu 30 giây bám gần nhất) → theo độ trôi.
4. Ngưỡng THEO TỪNG KẾT QUẢ (vì nhạc có nhịp/vòng lặp tự giống mình ở chỗ lệch, còn nhạc đè hạ mức «trong»):
   đường nền tại chỗ = độ tương đồng dọc đường căn chỉnh của engine LỆCH 6 khoảng (±7,3 … ±41,7 s) trên cùng cặp
   clip–video. Ngưỡng bám = max(nền) + 0,02. Mức trong = trung vị các giây thuộc lõi engine [vung_khop_s, end_s].
   Ngưỡng dùng = (mức trong + p99 nền)/2; mức trong − p99 nền < 0,15 → «tương phản thấp», không tinh chỉnh.
5. Đoạn dùng thật = các giây ≥ ngưỡng dùng, lấp lỗ ≤ 2 s, bỏ chạy < 3 s. Mép tới khung: trong ±1,5 s quanh mép thô,
   tương quan từng khung dọc đường căn chỉnh rồi khớp hàm bậc thang; mép trùng đầu/cuối clip thì lấy đầu/cuối clip.
Tự kiểm (audio tổng hợp của repo, mép lẻ giữa nốt; sạch, tăng tốc 2%, nhạc đè 0 dB): ``python tuong_dong.py``.
"""
from __future__ import annotations

import os

for _bien in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_bien, "2")        # máy đang chạy DEV 8502: không chiếm hết CPU

import subprocess  # noqa: E402

import numpy as np  # noqa: E402

SR = 11025
N_FFT = 512
HOP = 128
FPS = SR / HOP                  # 86,13 khung/giây
FMIN, FMAX, N_MEL = 300.0, 5000.0, 40
SAN_DB = -60.0

THAM_SO_MAC_DINH = {"W": 0.1, "W0": 0.5, "cua_so_s": 3.0, "lech_nen_s": (7.3, -11.9, 19.1, -23.7, 31.3, -41.7),
                    "le_bam": 0.02, "tuong_phan_toi_thieu": 0.15, "lap_lo": 2, "chay_toi_thieu": 3,
                    "nua_cua_so_bien_s": 1.5, "chenh_bien_toi_thieu": 0.15,
                    "nguong_bam": None, "nguong_dung": None}        # None = theo đường nền tại chỗ (mặc định)
BIEN_NEN_S = 42.0               # đoạn video giải mã phải phủ cả các đường lệch của đường nền


def doc_pcm(duong: str, tu: float = 0.0, dai: float | None = None) -> tuple:
    """FFmpeg → mono float32 11025 Hz. Trả (mẫu, mốc đầu thật = ``tu`` làm tròn theo lưới mẫu)."""
    tu = max(0.0, round(tu * SR) / SR)
    lenh = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]
    if tu > 0:
        lenh += ["-ss", f"{tu:.6f}"]
    lenh += ["-i", duong]
    if dai is not None:
        lenh += ["-t", f"{dai:.6f}"]
    lenh += ["-map", "0:a:0", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(lenh, capture_output=True, timeout=600, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg lỗi với {duong}: {r.stderr.decode('utf-8', 'replace')[-300:]}")
    return np.frombuffer(r.stdout, dtype=np.float32), tu


def _bo_loc_mel() -> np.ndarray:
    f = np.fft.rfftfreq(N_FFT, 1.0 / SR)

    def mel(hz):
        return 2595.0 * np.log10(1.0 + hz / 700.0)
    diem = 700.0 * (10 ** (np.linspace(mel(FMIN), mel(FMAX), N_MEL + 2) / 2595.0) - 1.0)
    fb = np.zeros((N_MEL, len(f)))
    for i in range(N_MEL):
        a, b, c = diem[i: i + 3]
        fb[i] = np.clip(np.minimum((f - a) / (b - a), (c - f) / (c - b)), 0.0, None)
    return fb


_FB = _bo_loc_mel()
_CUA_SO = np.hanning(N_FFT)


def log_mel(x: np.ndarray) -> np.ndarray:
    """Log10 năng lượng mel (khung × dải). Khung f phủ mẫu [f·HOP, f·HOP + N_FFT)."""
    n = 1 + (len(x) - N_FFT) // HOP if len(x) >= N_FFT else 0
    ra = np.empty((n, N_MEL), dtype=np.float64)
    khung = np.lib.stride_tricks.sliding_window_view(x, N_FFT)[::HOP]
    for i in range(0, n, 4096):
        p = np.abs(np.fft.rfft(khung[i:i + 4096] * _CUA_SO, axis=1)) ** 2
        ra[i:i + 4096] = p @ _FB.T
    if n == 0:
        return ra
    san = max(np.percentile(ra, 99) * 10 ** (SAN_DB / 10), 1e-20)
    return np.log10(np.maximum(ra, san))


def _ncc_mieng(a: np.ndarray, vung: np.ndarray) -> np.ndarray:
    """``a`` (F × B, đã trừ trung bình từng dải) so với mọi cửa sổ F khung của ``vung`` → Pearson theo từng độ trễ,
    sau khi trừ trung bình TỪNG DẢI của chính cửa sổ video."""
    F, B = a.shape
    na = np.sqrt(float(np.dot(a.ravel(), a.ravel())))
    cs = np.lib.stride_tricks.sliding_window_view(vung.ravel(), F * B)[::B]        # (2L+1, F·B)
    tu = cs @ a.ravel()             # a có trung bình từng dải = 0 nên trung bình của cửa sổ video tự triệt tiêu
    c1 = np.vstack([np.zeros((1, B)), np.cumsum(vung, axis=0)])
    c2 = np.concatenate([[0.0], np.cumsum(np.einsum("fb,fb->f", vung, vung))])
    s1 = c1[F:] - c1[:-F]
    nang = (c2[F:] - c2[:-F]) - np.einsum("lb,lb->l", s1, s1) / F
    return tu / (na * np.sqrt(np.maximum(nang, 1e-12)) + 1e-12)


def he_so_tu_engine(m: dict) -> float:
    """k ban đầu từ các trường Match: lượt bù tốc độ làm vung_khop_s − start_s ≠ clip_offset_s."""
    off, d = float(m["clip_offset_s"]), float(m["vung_khop_s"]) - float(m["start_s"])
    if off >= 30.0 and d > 0:
        k = off / d
        if 0.9 <= k <= 1.1:
            return k
    return 1.0


class _Do:
    """Đo độ tương đồng của MỘT giây clip quanh một vị trí video dự đoán."""

    def __init__(self, C: np.ndarray, V: np.ndarray, T0: float, cua_so_s: float):
        self.C, self.V, self.T0 = C, V, T0
        self.F = min(int(round(cua_so_s * FPS)), len(C))

    def __call__(self, n: int, t_du: float, w_s: float, toc: float):
        """``t_du`` = giây video của giây clip n. Trả (tương đồng, giây video đo được của giây clip n, chạm mép)."""
        F, C, V = self.F, self.C, self.V
        fc = min(max(int(round((n + 0.5) * FPS)) - F // 2, 0), len(C) - F)    # miếng đặt giữa giây n, kẹp trong clip
        if fc < 0 or F < 16:
            return None
        a = C[fc: fc + F] - C[fc: fc + F].mean(axis=0)
        p = (t_du + (fc / FPS - n) * toc - self.T0) * FPS
        L = int(round(w_s * FPS))
        lo, hi = max(0, int(round(p)) - L), min(len(V) - F, int(round(p)) + L)
        if hi < lo:
            return None
        r = _ncc_mieng(a, V[lo: hi + F])
        j = int(np.argmax(r))
        d = 0.0
        if 0 < j < len(r) - 1:
            mau = r[j - 1] - 2 * r[j] + r[j + 1]
            if mau < 0:
                d = 0.5 * (r[j - 1] - r[j + 1]) / mau
        o_mep = (j == 0 and lo > 0) or (j == len(r) - 1 and hi < len(V) - F) or len(r) < 3
        return float(r[j]), self.T0 + (lo + j + d) / FPS - (fc / FPS - n) * toc, o_mep


def duong_nen_tai_cho(do: _Do, so_giay: int, duong, toc: float, ts: dict) -> np.ndarray:
    """Độ tương đồng dọc đường căn chỉnh ``duong(n)`` LỆCH từng khoảng trong ts['lech_nen_s'] (không bám)."""
    ra = []
    for dl in ts["lech_nen_s"]:
        for n in range(so_giay):
            m = do(n, duong(n) + dl, ts["W"], toc)
            if m is not None:
                ra.append(m[0])
    return np.array(ra)


def ho_so_tung_giay(do: _Do, so_giay: int, neo_c: float, neo_t: float, toc0: float, nguong_bam: float,
                    ts: dict) -> tuple:
    """Bám từng giây từ neo (tiến rồi lùi). Trả (hồ sơ, các điểm đã bám (n, t) sắp theo n)."""
    hs: list = [None] * so_giay
    if so_giay == 0:
        return hs, []
    n0 = min(max(int(np.ceil(neo_c)), 0), so_giay - 1)
    # bắt nhịp: giây bám được đầu tiên trong ±10 s quanh neo, cửa sổ rộng W0 (neo engine lệch tới ~0,5 s vẫn bắt)
    bat = None
    for n in sorted(range(max(0, n0 - 10), min(so_giay, n0 + 11)), key=lambda x: (abs(x - n0), x)):
        m = do(n, neo_t + (n - neo_c) * toc0, ts["W0"], toc0)
        if m is not None and m[0] >= nguong_bam and not m[2]:
            bat = (n, m[1])
            break

    def chay(day_n, n_ref: float, t_ref: float, toc: float, diem: list, cho_bam: bool) -> list:
        for n in day_n:
            t_du = t_ref + (n - n_ref) * toc
            m = do(n, t_du, ts["W"], toc)
            if m is None:
                continue
            s, t_do, o_mep = m
            bam = cho_bam and s >= nguong_bam and not o_mep
            if bam:
                n_ref, t_ref = n, t_do
                diem.append((n, t_do))
                q = diem[-30:]
                if len(q) >= 10 and abs(q[-1][0] - q[0][0]) >= 10:
                    toc = float(np.clip(np.polyfit([x[0] for x in q], [x[1] for x in q], 1)[0], 0.9, 1.1))
            hs[n] = {"giay": n, "tuong_dong": s, "t_video": t_do if bam else t_du, "bam": bam, "mep_cua_so": o_mep}
        return diem

    if bat is None:                           # không bắt được: chỉ đo dọc đường của engine (để có hồ sơ), không bám
        chay(range(n0, so_giay), neo_c, neo_t, toc0, [], False)
        chay(range(n0 - 1, -1, -1), neo_c, neo_t, toc0, [], False)
        return hs, []
    tien = chay(range(bat[0], so_giay), bat[0], bat[1], toc0, [], True)
    q = tien[:30]                             # chiều lùi: từ điểm bắt nhịp, tốc độ của 30 giây bám đầu
    toc_lui = toc0
    if len(q) >= 10 and abs(q[-1][0] - q[0][0]) >= 10:
        toc_lui = float(np.clip(np.polyfit([x[0] for x in q], [x[1] for x in q], 1)[0], 0.9, 1.1))
    lui = chay(range(bat[0] - 1, -1, -1), bat[0], bat[1], toc_lui, [], True)
    return hs, sorted(lui + tien)


def cac_chay(hs: list, nguong: float, lap_lo: int, toi_thieu: int) -> list:
    """Các đoạn giây ≥ ngưỡng [n_dau, n_cuoi] (gồm cả hai đầu); lấp lỗ ≤ ``lap_lo`` giây; bỏ chạy < ``toi_thieu``."""
    chay: list = []
    for n, h in enumerate(hs):
        if h is not None and h["tuong_dong"] >= nguong:
            if chay and n - chay[-1][1] - 1 <= lap_lo:
                chay[-1][1] = n
            else:
                chay.append([n, n])
    return [c for c in chay if c[1] - c[0] + 1 >= toi_thieu]


def _anh_xa(diem: list, c: float, toc: float, trong: tuple) -> float:
    """Giây video của giây clip ``c``: điểm bám gần nhất NẰM TRONG đoạn ``trong`` + tốc độ cục bộ."""
    ung = [p for p in diem if trong[0] <= p[0] <= trong[1]] or diem
    n_r, t_r = min(ung, key=lambda p: abs(p[0] - c))
    return t_r + (c - n_r) * toc


def _toc_cuc_bo(diem: list, trong: tuple, toc_mac_dinh: float) -> float:
    q = [p for p in diem if trong[0] <= p[0] <= trong[1]]
    if len(q) >= 10 and q[-1][0] - q[0][0] >= 10:
        return float(np.polyfit([p[0] for p in q], [p[1] for p in q], 1)[0])
    return toc_mac_dinh


def buoc_thang(x: np.ndarray, trong_ben_phai: bool) -> tuple | None:
    """Khớp hàm bậc thang 2 mức: trả (j, mức trái, mức phải) — j = khung đầu của phần phải; None nếu không có."""
    n = len(x)
    if n < 8:
        return None
    c1 = np.concatenate([[0.0], np.cumsum(x)])
    c2 = np.concatenate([[0.0], np.cumsum(x * x)])
    j = np.arange(3, n - 2)
    tb_t, tb_p = c1[j] / j, (c1[n] - c1[j]) / (n - j)
    sse = (c2[j] - j * tb_t ** 2) + (c2[n] - c2[j] - (n - j) * tb_p ** 2)
    dung = tb_p > tb_t if trong_ben_phai else tb_t > tb_p
    if not dung.any():
        return None
    k = int(np.argmin(np.where(dung, sse, np.inf)))
    return int(j[k]), float(tb_t[k]), float(tb_p[k])


def mep_tinh(C: np.ndarray, V: np.ndarray, T0: float, diem: list, toc: float, c_tho: float, phia: str,
             do_dai_clip: float, trong: tuple, ts: dict) -> tuple:
    """Mép đoạn tới khung (11,6 ms): bậc thang trên tương quan TỪNG KHUNG dọc đường căn chỉnh quanh ``c_tho``
    (trừ trung bình từng dải trong cửa sổ, riêng clip và video). Trả (giây clip của mép, cách tìm)."""
    tu, den = max(0.0, c_tho - ts["nua_cua_so_bien_s"]), min(do_dai_clip, c_tho + ts["nua_cua_so_bien_s"])
    f_lo, f_hi = int(np.ceil(tu * FPS)), min(int(den * FPS) - N_FFT // HOP, len(C))
    if f_hi - f_lo < 8:
        return c_tho, "tho"
    fs = np.arange(f_lo, f_hi)
    pv = np.round((np.array([_anh_xa(diem, f / FPS, toc, trong) for f in fs]) - T0) * FPS).astype(int)
    hop_le = (pv >= 0) & (pv < len(V))
    if hop_le.sum() < 8:
        return c_tho, "tho"
    fs, pv = fs[hop_le], pv[hop_le]
    a, v = C[fs] - C[fs].mean(axis=0), V[pv] - V[pv].mean(axis=0)
    a, v = a - a.mean(axis=1, keepdims=True), v - v.mean(axis=1, keepdims=True)
    x = (a * v).sum(axis=1) / np.sqrt((a * a).sum(axis=1) * (v * v).sum(axis=1) + 1e-12)
    kq = buoc_thang(x, trong_ben_phai=(phia == "dau"))
    if kq is None or abs(kq[2] - kq[1]) < ts["chenh_bien_toi_thieu"]:
        return c_tho, "tho"
    j = kq[0]
    return ((fs[j - 1] + fs[j]) / 2 * HOP + N_FFT / 2) / SR, "bac_thang"


def tinh_chinh(C: np.ndarray, V: np.ndarray, T0: float, do_dai_clip: float, m: dict, ts: dict | None = None,
               video_den: float | None = None) -> dict:
    """Một kết quả engine (dict trường Match) → hồ sơ từng giây + các đoạn dùng thật với mép tới khung.
    ``C``, ``V``: log_mel của clip (cả clip) và của đoạn video bắt đầu ở giây ``T0``."""
    ts = {**THAM_SO_MAC_DINH, **(ts or {})}
    k0 = he_so_tu_engine(m)
    neo_c, neo_t = float(m["clip_offset_s"]), float(m["vung_khop_s"])
    so_giay = int(np.floor(do_dai_clip + 1e-6))
    do = _Do(C, V, T0, ts["cua_so_s"])
    ra = {"k_engine": round(k0, 5), "neo": [round(neo_c, 3), round(neo_t, 3)], "tham_so": ts}
    # đường nền tại chỗ: dọc đường căn chỉnh của engine, lệch các khoảng cố định
    nen = duong_nen_tai_cho(do, so_giay, lambda n: neo_t + (n - neo_c) / k0, 1.0 / k0, ts)
    nen_p99 = float(np.percentile(nen, 99)) if len(nen) else 1.0
    nen_max = float(nen.max()) if len(nen) else 1.0
    nguong_bam = ts["nguong_bam"] if ts["nguong_bam"] is not None else min(nen_max + ts["le_bam"], 0.95)
    hs, diem = ho_so_tung_giay(do, so_giay, neo_c, neo_t, 1.0 / k0, nguong_bam, ts)
    # mức «trong» = trung vị trên lõi engine [vung_khop_s, end_s] đổi sang giây clip
    loi_den = neo_c + (float(m.get("end_s", neo_t)) - neo_t) * k0
    trong = [h["tuong_dong"] for h in hs if h is not None and neo_c <= h["giay"] <= loi_den]
    muc_trong = float(np.median(trong)) if trong else 0.0
    nguong_dung = ts["nguong_dung"] if ts["nguong_dung"] is not None else (muc_trong + nen_p99) / 2
    ra.update({"duong_nen": {"so_giay": int(len(nen)), "p50": round(100 * float(np.median(nen)), 1) if len(nen) else None,
                             "p99": round(100 * nen_p99, 1), "max": round(100 * nen_max, 1)},
               "muc_trong": round(100 * muc_trong, 1), "nguong_bam": round(100 * nguong_bam, 1),
               "nguong_dung": round(100 * nguong_dung, 1), "so_giay_bam": len(diem),
               "ho_so": [None if h is None else [h["giay"], round(max(0.0, 100 * h["tuong_dong"]), 1),
                                                 round(h["t_video"], 3), int(h["bam"])] for h in hs]})
    ra["tuong_phan_thap"] = muc_trong - nen_p99 < ts["tuong_phan_toi_thieu"]
    doan = []
    if ra["tuong_phan_thap"] or not diem:
        ra["doan"] = doan
        return ra
    for n_a, n_b in cac_chay(hs, nguong_dung, ts["lap_lo"], ts["chay_toi_thieu"]):
        trong_n = (n_a, n_b)
        toc = _toc_cuc_bo(diem, trong_n, 1.0 / k0)
        if n_a == 0:
            c_dau, cach_dau = 0.0, "dau_clip"
        else:
            c_dau, cach_dau = mep_tinh(C, V, T0, diem, toc, float(n_a), "dau", do_dai_clip, trong_n, ts)
        if n_b == so_giay - 1:
            c_cuoi, cach_cuoi = float(do_dai_clip), "cuoi_clip"
        else:
            c_cuoi, cach_cuoi = mep_tinh(C, V, T0, diem, toc, float(n_b + 1), "cuoi", do_dai_clip, trong_n, ts)
        v_dau, v_cuoi = max(_anh_xa(diem, c_dau, toc, trong_n), 0.0), _anh_xa(diem, c_cuoi, toc, trong_n)
        if video_den is not None:
            v_cuoi = min(v_cuoi, video_den)
        q = [p for p in diem if n_a <= p[0] <= n_b]
        moc_ao = None
        if len(q) >= 10 and q[-1][0] - q[0][0] >= 10:
            moc_ao = float(np.polyfit([p[0] for p in q], [p[1] for p in q], 1)[1])
        gia_tri = [hs[n]["tuong_dong"] for n in range(n_a, n_b + 1) if hs[n] is not None]
        doan.append({"clip_tu": round(float(c_dau), 3), "clip_den": round(float(c_cuoi), 3),
                     "video_tu": round(float(v_dau), 3), "video_den": round(float(v_cuoi), 3),
                     "cach_tim_mep": [cach_dau, cach_cuoi], "so_giay": n_b - n_a + 1,
                     "tuong_dong_tb": round(100 * float(np.mean(gia_tri)), 1),
                     "tuong_dong_min": round(100 * float(np.min(gia_tri)), 1),
                     "k_uoc_luong": round(1.0 / toc, 5),
                     "moc_giay0_clip_tren_video": None if moc_ao is None else round(moc_ao, 3)})
    ra["doan"] = doan
    return ra


# ---------------------------------------------------------------- tự kiểm trên audio tổng hợp của repo

def _tu_kiem() -> None:
    import sys
    import tempfile
    sys.path.insert(0, r"C:\Dev\Tool_Quet\TimClipPro\tests")
    from am_thanh_lap import doi_toc_do, nhac_co_nhip
    from conftest import _ghi_wav, _giai_dieu

    assert buoc_thang(np.r_[np.zeros(20), np.ones(30)], True)[0] == 20
    assert buoc_thang(np.r_[np.ones(20), np.zeros(30)], False)[0] == 20
    assert buoc_thang(np.r_[np.ones(20), np.zeros(30)], True) is None
    ch = cac_chay([{"tuong_dong": x} for x in (0, .9, .9, .9, 0, .9, .9, .9, .9, 0, 0, 0, .9, .9)], 0.5, 1, 3)
    assert ch == [[1, 8]], ch
    assert he_so_tu_engine({"clip_offset_s": 305.6, "vung_khop_s": 405.4, "start_s": 105.772}) != 1.0
    assert he_so_tu_engine({"clip_offset_s": 4.3, "vung_khop_s": 304.2, "start_s": 299.9}) == 1.0
    a = np.random.default_rng(1).standard_normal((50, 40))       # _ncc_mieng: bất biến với cộng hằng từng dải
    v = np.vstack([np.zeros((5, 40)), a + np.arange(40) * 3.0, np.zeros((5, 40))])
    assert abs(_ncc_mieng(a - a.mean(axis=0), v)[5] - 1.0) < 1e-9

    sr = 22050
    clip = _giai_dieu(90, seed=4242, sr=sr)
    for ten, he_so, de_db in (("sạch", 1.0, None), ("tăng tốc 2%", 1.02, None), ("nhạc đè 0 dB", 1.0, 0.0)):
        c_tu, c_den, P = 12.37, 71.81, 33.13          # mép lẻ, giữa nốt
        doan = clip[int(c_tu * sr): int(c_den * sr)]
        if he_so != 1.0:
            doan = doi_toc_do(doan, 1.0 / he_so)
        video = _giai_dieu(150, seed=4343, sr=sr)
        video[int(P * sr): int(P * sr) + len(doan)] = doan
        if de_db is not None:
            de = nhac_co_nhip(150, seed=4444)
            vung = slice(int(P * sr), int(P * sr) + len(doan))
            de *= np.sqrt(np.mean(doan ** 2) / np.mean(de[vung] ** 2)) * 10 ** (-de_db / 20)
            video = (video + de) * (0.95 / np.abs(video + de).max())
        v_den = P + (c_den - c_tu) / he_so
        with tempfile.TemporaryDirectory() as d:
            pc, pv = os.path.join(d, "clip.wav"), os.path.join(d, "video.wav")
            _ghi_wav(pc, clip, sr)
            _ghi_wav(pv, video, sr)
            xc, _ = doc_pcm(pc)
            xv, t0 = doc_pcm(pv, 0.0, 150.0)
        C, V = log_mel(xc), log_mel(xv)
        # «kết quả engine» giả: lõi engine cắt 5% hai đầu, start_s tính với k = 1 (như lượt thường)
        dai = (c_den - c_tu) / he_so
        m = {"start_s": P - c_tu, "vung_khop_s": P + 0.05 * dai, "clip_offset_s": c_tu + 0.05 * dai * he_so,
             "end_s": v_den - 0.05 * dai}
        kq = tinh_chinh(C, V, t0, 90.0, m)
        assert len(kq["doan"]) == 1, (ten, kq["doan"], kq["duong_nen"], kq["muc_trong"])
        d0 = kq["doan"][0]
        loi = (d0["video_tu"] - P, d0["video_den"] - v_den, d0["clip_tu"] - c_tu, d0["clip_den"] - c_den)
        print(f"tự kiểm {ten}: video [{d0['video_tu']}, {d0['video_den']}] thật [{P}, {v_den:.3f}]; "
              f"clip [{d0['clip_tu']}, {d0['clip_den']}] thật [{c_tu}, {c_den}]; k {d0['k_uoc_luong']}; "
              f"trong {kq['muc_trong']}%, nền p99 {kq['duong_nen']['p99']}% → ngưỡng {kq['nguong_dung']}%")
        assert max(abs(x) for x in loi) < 0.1, (ten, loi)
        assert abs(d0["k_uoc_luong"] - he_so) < 0.003, (ten, d0["k_uoc_luong"])
    print("tuong_dong: tự kiểm ĐẠT")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _tu_kiem()
