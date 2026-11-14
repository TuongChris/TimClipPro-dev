# -*- coding: utf-8 -*-
"""Cách B — «dòng thời gian hash»: tinh chỉnh mốc của MỘT kết quả ĐÃ được engine chấp nhận (nghiên cứu 14/11/2026).

Không tạo, không bỏ kết quả. Với một dòng kết quả (clip, căn chỉnh, hệ số tốc độ), đo lại TỪNG GIÂY của video:
bao nhiêu phần vân tay của clip ở giây tương ứng có mặt trong video ở ĐÚNG căn chỉnh đó.

Vân tay tính bằng CHÍNH ``audfprint_analyze.Analyzer`` (tham số = giá trị mặc định CLI audfprint mà engine dùng:
density 20, fanout 3, pks-per-frame 5, freq-sd 30, 11025 Hz, n_fft 512, hop 256; shifts = ``shifts_kho`` cho clip,
``shifts_quet`` cho video). Audio cửa sổ cắt bằng ĐÚNG lệnh FFmpeg của ``Engine._cut_chunks``; kết quả của lượt bù tốc
độ được đổi tốc độ bằng ĐÚNG ``toc_do_khop.bo_loc_ffmpeg`` như ``Engine._bien_doi_khuc``.

Mô hình thời gian (khung audfprint T = 256/11025 s): khung g của clip ↔ khung f của cửa sổ khi
``g − f = d0 + s·(f − f_ref)``; giây video của khung f = ``W0 + sigma·T·f`` (sigma = hệ số đã áp lên cửa sổ, 1 nếu không
đổi tốc độ). Hash clip «khớp» khi có hash video cùng giá trị lệch ≤ 2 khung khỏi đường đó (= ``--match-win`` 2 của
audfprint, engine không truyền -w).

Tự kiểm (không cần audio): ``python -B dong_thoi_gian_hash.py``
"""
from __future__ import annotations

import os
import subprocess
import sys
import warnings

import numpy as np

MA = r"C:\Dev\Tool_Quet\TimClipPro"
AUDFPRINT = os.path.join(MA, "audfprint-master")
SR = 11025
HOP = 256
T = HOP / SR
CUA_SO_KHOP = 2            # --match-win mặc định của audfprint
DT_MASK = (1 << 6) - 1     # audfprint_analyze.DT_BITS = 6: 6 bit thấp của hash là dt (khung)
N_MIN = 5                  # giây có < N_MIN hash clip: tỉ lệ không đủ tin (NaN), không mở/cắt đoạn


def tao_analyzer(shifts: int, la_kho: bool):
    """Analyzer như ``audfprint.setup_analyzer`` với giá trị mặc định của CLI; shifts 0 → mặc định audfprint."""
    if AUDFPRINT not in sys.path:
        sys.path.insert(0, AUDFPRINT)
    import audfprint_analyze

    an = audfprint_analyze.Analyzer()
    an.density, an.maxpksperframe, an.maxpairsperpeak, an.f_sd = 20.0, 5, 3, 30.0
    an.shifts = int(shifts) or (1 if la_kho else 4)
    an.target_sr, an.n_fft, an.n_hop = SR, 512, HOP
    an.fail_on_error = False            # engine luôn truyền --continue-on-error
    return an


def hash_file(path: str, shifts: int, la_kho: bool) -> np.ndarray:
    """Mảng (n, 2) int64 [khung, hash] — đúng ``Analyzer.wavfile2hashes`` (đã khử trùng (khung, hash))."""
    h = tao_analyzer(shifts, la_kho).wavfile2hashes(path)
    return np.asarray(h, dtype=np.int64).reshape(-1, 2)


def cat_cua_so(video: str, tu_s: float, den_s: float, ra_wav: str, he_so: float = 1.0, ho: str = "tempo") -> str:
    """Cắt [tu_s, den_s) thành WAV mono 11025 Hz như ``_cut_chunks``; he_so ≠ 1: đổi tốc độ như ``_bien_doi_khuc``."""
    goc = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    subprocess.run(goc + ["-ss", f"{tu_s:.6f}", "-t", f"{den_s - tu_s:.6f}", "-i", video,
                          "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SR), ra_wav], check=True)
    if abs(he_so - 1.0) > 1e-9:
        if MA not in sys.path:
            sys.path.insert(0, MA)
        from toc_do_khop import bo_loc_ffmpeg

        tam = ra_wav[:-4] + "_k.wav"
        subprocess.run(goc + ["-i", ra_wav, "-vn", "-ac", "1", "-ar", str(SR), "-af", bo_loc_ffmpeg(he_so, ho), tam],
                       check=True)
        os.replace(tam, ra_wav)
    return ra_wav


def cap_hash(clip_h: np.ndarray, win_h: np.ndarray) -> tuple:
    """Mọi cặp (chỉ số hash clip, chỉ số hash cửa sổ) có CÙNG giá trị hash."""
    thu_tu = np.argsort(clip_h[:, 1], kind="stable")
    hc = clip_h[thu_tu, 1]
    lo = np.searchsorted(hc, win_h[:, 1], "left")
    dem = np.searchsorted(hc, win_h[:, 1], "right") - lo
    j = np.repeat(np.arange(len(win_h)), dem)
    bu = np.arange(int(dem.sum())) - np.repeat(np.cumsum(dem) - dem, dem)
    return thu_tu[np.repeat(lo, dem) + bu], j


def chon_can_chinh(dtime: np.ndarray, f: np.ndarray, d_exp: float, s_prior: float, f_ref: float,
                   tim_d: int, s_luoi, hon_toi_thieu: float = 0.01) -> tuple:
    """(d0, s, số cặp) có nhiều cặp nằm trong ±CUA_SO_KHOP khung nhất; d0 ∈ d_exp ± tim_d (dưới-khung), s ∈ s_prior + s_luoi.

    Duyệt |ds| tăng dần; một độ dốc xa s_prior hơn chỉ thắng khi NHIỀU hơn hẳn (> hon_toi_thieu, mặc định 1 %) — độ dốc
    lệch vô cớ làm trôi mép ở hai đầu đoạn. Không có cặp nào → (d_exp, s_prior, 0).
    """
    w = tim_d + CUA_SO_KHOP
    tot = (d_exp, s_prior, 0)
    for ds in sorted(s_luoi, key=abs):
        s = s_prior + ds
        q = np.rint(dtime - s * (f - f_ref) - d_exp).astype(np.int64)
        q = q[np.abs(q) <= w]
        if not len(q):
            continue
        tong = np.convolve(np.bincount(q + w, minlength=2 * w + 1), np.ones(2 * CUA_SO_KHOP + 1, np.int64), "valid")
        i = int(np.argmax(tong))
        if tong[i] > tot[2] * (1.0 + (hon_toi_thieu if tot[2] else 0.0)):
            tot = (i - tim_d, s, int(tong[i]))
    if not tot[2]:
        return tot
    # Nhiều tâm cửa sổ thường HOÀ nhau (phân bố hẹp hơn 5 khung) và argmax lấy tâm ĐẦU — lệch hệ thống −1 khung (đo:
    # A_moi = 300,023 thay vì 300,000). Lấy trung bình phần dư của các cặp trong cửa sổ thắng: d0 dưới-khung.
    tam, s, n = tot
    r = dtime - s * (f - f_ref) - d_exp
    trong = np.abs(np.rint(r).astype(np.int64) - tam) <= CUA_SO_KHOP
    return d_exp + float(np.mean(r[trong])), s, n


def ho_so(clip_h: np.ndarray, win_h: np.ndarray, cap: tuple, W0: float, W1: float, sigma: float, A: float,
          k_tong: float, f_ref: float, tim_d: int = 15, s_luoi=(0.0,)) -> dict:
    """Hồ sơ từng giây của một căn chỉnh.

    Căn chỉnh tiên nghiệm: giây c của clip ở giây v = A + k_tong·c của video; cửa sổ [W0, W1) đã đổi tốc độ sigma lần.
    Tìm (d0, s) quanh tiên nghiệm rồi đánh dấu hash clip nào có mặt. Trả hash-level (giây video của neo ``v``, của đỉnh
    thứ hai ``e``, cờ ``khop``) và mức giây (``giay0`` + mảng ``n_clip``, ``n_khop``, ``sim`` = n_khop / n_clip).
    """
    i, j = cap
    g = clip_h[i, 0].astype(np.float64)
    f = win_h[j, 0].astype(np.float64)
    dtime = g - f
    s_prior = sigma / k_tong - 1.0
    d_exp = (W0 - A) / (k_tong * T) + s_prior * f_ref
    # Lọc thô MỘT lần cho cả lưới độ dốc — còn lại vài nghìn cặp thay vì hàng triệu.
    rong = tim_d + CUA_SO_KHOP + 1 + max(abs(x) for x in s_luoi) * np.abs(f - f_ref)
    giu = np.abs(dtime - s_prior * (f - f_ref) - d_exp) <= rong
    d0, s, so_cap = chon_can_chinh(dtime[giu], f[giu], d_exp, s_prior, f_ref, tim_d, s_luoi)
    ok = np.abs(dtime[giu] - s * (f[giu] - f_ref) - d0) <= CUA_SO_KHOP + 0.5
    khop = np.zeros(len(clip_h), bool)
    khop[i[giu][ok]] = True
    win_khop = np.zeros(len(win_h), bool)
    win_khop[j[giu][ok]] = True

    def giay_video(khung_clip):
        return W0 + sigma * T * (khung_clip - d0 + s * f_ref) / (1.0 + s)

    gc = clip_h[:, 0].astype(np.float64)
    v = giay_video(gc)
    e = giay_video(gc + (clip_h[:, 1] & DT_MASK))
    giay0 = int(np.floor(W0))
    nb = int(np.ceil(W1)) - giay0
    trong = (v >= W0) & (v < W1)
    b = np.floor(v[trong]).astype(np.int64) - giay0
    n_clip = np.bincount(b, minlength=nb)[:nb]
    n_khop = np.bincount(b, weights=khop[trong], minlength=nb)[:nb]
    vw = W0 + sigma * T * win_h[:, 0]
    bw = np.clip(np.floor(vw).astype(np.int64) - giay0, 0, nb - 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sim = np.where(n_clip >= N_MIN, n_khop / n_clip, np.nan)
    return {
        "d0": float(d0), "s": float(s), "so_cap": so_cap, "d_exp": float(d_exp), "s_prior": float(s_prior),
        "A_moi": float(giay_video(0.0)), "k_moi": float(sigma / (1.0 + s)),
        "so_hash_clip_trong_cua_so": int(trong.sum()), "so_hash_clip_khop": int(khop[trong].sum()),
        "so_hash_cua_so": int(len(win_h)), "so_hash_cua_so_khop": int(win_khop.sum()),
        "v": v, "e": e, "khop": khop, "trong": trong, "giay0": giay0,
        "n_clip": n_clip, "n_khop": n_khop.astype(np.int64), "sim": sim,
        "n_cua_so": np.bincount(bw, minlength=nb)[:nb],
        "n_cua_so_khop": np.bincount(bw, weights=win_khop, minlength=nb)[:nb].astype(np.int64),
    }


def ty_le_truot(n_clip: np.ndarray, n_khop: np.ndarray, w: int) -> np.ndarray:
    """Tỉ lệ GỘP trong cửa sổ w giây (lẻ) quanh mỗi giây: Σ hash clip khớp / Σ hash clip — bền hơn trung bình/trung vị
    các tỉ lệ từng giây khi mỗi giây chỉ có vài hash khớp (nhiễu đè, nén mạnh). Giây có < N_MIN hash clip → NaN."""
    ker = np.ones(int(w) | 1)
    sn = np.convolve(np.asarray(n_clip, float), ker, "same")
    sk = np.convolve(np.asarray(n_khop, float), ker, "same")
    with np.errstate(invalid="ignore", divide="ignore"):
        r = sk / sn
    r[np.asarray(n_clip) < N_MIN] = np.nan
    return r


def trung_vi_truot(x: np.ndarray, w: int) -> np.ndarray:
    """Trung vị trượt cửa sổ w (lẻ), bỏ qua NaN; toàn NaN → NaN."""
    p = int(w) // 2
    xp = np.concatenate([np.full(p, np.nan), np.asarray(x, float), np.full(p, np.nan)])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(np.lib.stride_tricks.sliding_window_view(xp, 2 * p + 1), axis=1)


def tim_doan(n_clip: np.ndarray, n_khop: np.ndarray, nguong_cao: float, nguong_thap: float, w: int = 5,
             min_dai: int = 3, noi_ho: int = 2) -> list:
    """Đoạn THÔ [a, b) (chỉ số giây) bằng trễ hai ngưỡng; mép thô lệch tới ~w/2 giây, ``mep_tinh`` gọt lại.

    Hạt nhân: trung vị trượt ``w`` giây của tỉ lệ từng giây ≥ nguong_cao (trung vị: một giây trùng khớp ngẫu nhiên lẻ loi
    không mở được đoạn). Kéo dài: tỉ lệ GỘP ``w`` giây ≥ nguong_thap (bền khi mỗi giây chỉ có vài hash khớp). Giây NaN
    (clip < N_MIN hash, hoặc ngoài phạm vi clip) không mở đoạn, không cắt đoạn đang mở, bị gọt khỏi hai đầu. Hai đoạn
    cách nhau < ``noi_ho`` giây được nối; cuối cùng bỏ đoạn ngắn hơn ``min_dai`` giây.
    """
    n_clip = np.asarray(n_clip)
    nan = n_clip < N_MIN
    with np.errstate(invalid="ignore", divide="ignore"):
        tung_giay = np.where(nan, np.nan, np.asarray(n_khop, float) / n_clip)
    tv = trung_vi_truot(tung_giay, w)
    tv[nan] = np.nan
    gop = ty_le_truot(n_clip, n_khop, w)
    duoc = nan | (np.nan_to_num(gop, nan=-1.0) >= nguong_thap)
    cao = np.nan_to_num(tv, nan=-1.0) >= nguong_cao
    bien = np.diff(np.concatenate([[0], duoc.astype(np.int8), [0]]))
    chay = []
    for a, b in zip(np.nonzero(bien == 1)[0], np.nonzero(bien == -1)[0]):
        if not cao[a:b].any():
            continue
        while a < b and nan[a]:
            a += 1
        while b > a and nan[b - 1]:
            b -= 1
        if b > a:
            if chay and a - chay[-1][1] < noi_ho:
                chay[-1] = (chay[-1][0], int(b))
            else:
                chay.append((int(a), int(b)))
    return [(a, b) for a, b in chay if b - a >= min_dai]


def mep_tinh(v: np.ndarray, e: np.ndarray, khop: np.ndarray, tu: float, den: float, gioi_trai: float,
             gioi_phai: float, moc_dau_clip: float, moc_cuoi_clip: float, khung_s: float,
             le: float = 5.0, rong: float = 1.0, m_min: int = 2) -> dict:
    """Mép tới phần mười giây của đoạn thô [tu, den) từ dòng thời gian hash của CLIP (khớp lẫn không khớp).

    ``v``/``e``: giây video của điểm neo / đỉnh thứ hai (neo + dt) của MỌI hash clip theo căn chỉnh đã chọn; ``khop``:
    hash đó có mặt trong video. Hash khớp «hợp lệ» khi có ≥ m_min hash khớp trong ``rong`` giây (bỏ khớp lẻ ngẫu nhiên).

    Đầu: hash khớp hợp lệ sớm nhất có neo trong [tu − le, tu + le]. Nếu nó là hash ĐẦU TIÊN của clip (≤ 1,5 khung) thì
    video chứa clip từ đầu: chốt ``moc_dau_clip``. Không thì mép nằm giữa neo đó và neo của hash clip liền trước (hash
    đó vắng mặt) — lấy điểm giữa.
    Cuối: đỉnh thứ hai muộn nhất ``ef`` của hash khớp hợp lệ có neo trong [den − le, den + le]. Chạm đỉnh cuối cùng của
    clip → chốt ``moc_cuoi_clip``; không thì điểm giữa ``ef`` và đỉnh thứ hai kế tiếp của clip (vắng mặt).
    Không vượt ``gioi_trai``/``gioi_phai``. Không tìm được → mép thô, ``cach_*`` = "tho".
    """
    thu_tu = np.argsort(v, kind="stable")
    vs, es, ks = v[thu_tu], e[thu_tu], khop[thu_tu]
    ik = np.nonzero(ks)[0]
    vk, ek = vs[ik], es[ik]
    ra = {"tu": float(tu), "den": float(den), "cach_dau": "tho", "cach_cuoi": "tho"}
    for x in np.nonzero((vk >= max(tu - le, gioi_trai)) & (vk <= min(tu + le, den)))[0]:
        if np.searchsorted(vk, vk[x] + rong, "right") - x >= m_min:
            p = ik[x]
            if vs[p] - vs[0] <= 1.5 * khung_s:
                ra.update(tu=max(float(moc_dau_clip), gioi_trai), cach_dau="dau_clip")
            else:
                ra.update(tu=float((vs[vs < vs[p]].max() + vs[p]) / 2), cach_dau="giua")
            break
    hop = [x for x in np.nonzero((vk >= max(den - le, tu)) & (vk <= min(den + le, gioi_phai)))[0]
           if x + 1 - np.searchsorted(vk, vk[x] - rong, "left") >= m_min]
    if hop:
        ef = float(np.max(ek[hop]))
        if es.max() - ef <= 1.5 * khung_s:
            ra.update(den=min(float(moc_cuoi_clip), gioi_phai), cach_cuoi="cuoi_clip")
        else:
            sau = es[es > ef]
            ra.update(den=min(float((ef + sau.min()) / 2), gioi_phai), cach_cuoi="giua")
    if ra["den"] <= ra["tu"]:
        ra.update(tu=float(tu), den=float(den), cach_dau="tho", cach_cuoi="tho")
    return ra


def _tu_kiem() -> None:
    rng = np.random.default_rng(7)
    # cap_hash: đủ mọi cặp cùng giá trị, không thừa
    c = np.array([[0, 5], [1, 7], [2, 5], [3, 9]])
    w = np.array([[10, 5], [11, 9], [12, 4]])
    i, j = cap_hash(c, w)
    assert sorted(zip(i.tolist(), j.tolist())) == [(0, 0), (2, 0), (3, 1)]
    # chon_can_chinh: đường thật d = 120 + 0,001·(f − 10000) (lệch tới 10 khung ở hai đầu) giữa 2 000 cặp nhiễu → phải
    # tìm ra độ dốc; đường thật dốc 0 → giữ đúng 0 (độ dốc khác không thắng nếu không nhiều hơn hẳn).
    f = rng.uniform(0, 20000, 3000)
    fn = rng.uniform(0, 20000, 2000)
    dn = rng.uniform(60, 180, len(fn))
    luoi = [k * 5e-5 for k in range(-30, 31)]
    for doc in (0.001, 0.0):
        d = 120 + doc * (f - 10000) + rng.integers(-1, 2, len(f))
        d0, s, n = chon_can_chinh(np.r_[d, dn], np.r_[f, fn], 117.0, 0.0, 10000.0, 15, luoi)
        assert abs(d0 - 120) <= 1 and abs(s - doc) <= 2e-4 and n >= 2950, (doc, d0, s, n)   # ≤ 2 khung ở hai đầu
    assert s == 0.0
    # ty_le_truot + tim_doan (40 hash clip/giây): hai đoạn; giữa đoạn đầu có 2 giây NaN và 1 giây tụt (không cắt); một giây
    # nhiễu lẻ không mở đoạn; khoảng hở 1 s được nối, 4 s thì không; ngoài phạm vi clip (NaN) đoạn không loang ra.
    n = np.full(100, 40)
    k = np.zeros(100)
    k[10:40] = 20
    k[30] = 0
    n[20:22] = 0
    k[20:22] = 0
    k[60:80] = 8
    k[90] = 24
    assert tim_doan(n, k, 0.1, 0.05) == [(8, 42), (59, 81)], tim_doan(n, k, 0.1, 0.05)   # mép thô ±w/2
    k2 = k.copy()
    k2[70] = 0                                     # hở 1 s trong đoạn hai: tỉ lệ gộp 5 s vẫn trên ngưỡng
    k2[50:54] = 20                                 # đoạn nhỏ 4 s cách đoạn hai 6 s: giữ riêng
    assert tim_doan(n, k2, 0.1, 0.05, w=1, noi_ho=2) == [(10, 40), (50, 54), (60, 80)],         tim_doan(n, k2, 0.1, 0.05, w=1, noi_ho=2)
    n3 = np.zeros(30, int)
    n3[10:20] = 40
    assert tim_doan(n3, np.where(n3 > 0, 24, 0), 0.1, 0.05) == [(10, 20)]
    # mep_tinh trên dòng thời gian hash clip: clip có hash mỗi 0,05 s từ 0,16 tới 59,8 (khung 0,02 s); video chứa
    # clip[20..40] → khớp đúng các hash có neo ≥ 20 và đỉnh thứ hai ≤ 40; một khớp lẻ ngẫu nhiên ở giây 5.
    v = np.arange(0.16, 59.8, 0.05) + 100.0      # căn chỉnh A = 100
    e = v + 0.12
    khop = (v >= 120.0) & (e <= 140.0)
    khop[np.argmin(np.abs(v - 105.0))] = True
    r = mep_tinh(v, e, khop, 119.0, 141.0, 100.0, 160.0, 100.0, 160.0, 0.02)
    assert r["cach_dau"] == "giua" and abs(r["tu"] - 120.0) <= 0.03, r
    assert r["cach_cuoi"] == "giua" and abs(r["den"] - 140.0) <= 0.03, r
    # video chứa TRỌN clip: chạm hash đầu và đỉnh cuối của clip → chốt đúng đầu/cuối clip
    r = mep_tinh(v, e, np.ones(len(v), bool), 99.0, 161.0, 90.0, 170.0, 100.0, 160.0, 0.02)
    assert (r["tu"], r["den"], r["cach_dau"], r["cach_cuoi"]) == (100.0, 160.0, "dau_clip", "cuoi_clip"), r
    r = mep_tinh(v, e, np.zeros(len(v), bool), 110.0, 130.0, 90.0, 170.0, 100.0, 160.0, 0.02)
    assert (r["tu"], r["den"], r["cach_dau"]) == (110.0, 130.0, "tho"), r
    print("dong_thoi_gian_hash: tự kiểm ĐẠT")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _tu_kiem()
