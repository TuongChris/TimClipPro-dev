# -*- coding: utf-8 -*-
"""Bộ sinh âm thanh TỔNG HỢP có cấu trúc lặp — dữ liệu cho test «bóng» của âm thanh lặp (P0, 10/10/2026).

Không dữ liệu thật/khách hàng. Mọi tín hiệu tất định theo ``seed`` (numpy ``default_rng``).

Vì sao cần: nhạc có nhịp trống đều, vòng hợp âm, hay một đoạn lặp y hệt từng mẫu làm audfprint trả thêm các
căn chỉnh «bóng» của CÙNG clip — lệch bội số nửa ô nhịp so với căn chỉnh thật, phủ cùng vùng video, yếu hơn hẳn.
``_giai_dieu`` (conftest) là chuỗi nốt ngẫu nhiên không lặp nên KHÔNG sinh ra hiện tượng này.

Dùng bởi ``test_bong_am_thanh_lap_audio_that.py`` (test chậm) và ``tao_golden_bong_lap.py`` (sinh lại dữ liệu
golden mức mảnh trong ``tests/golden/bong_lap/``).
"""
from __future__ import annotations

import numpy as np

SR = 22050
BPM = 113.0
O_NHIP = 240.0 / BPM            # một ô nhịp 4/4 ≈ 2,124 s; nửa ô nhịp ≈ 1,06 s


def nhac_co_nhip(dur_s: float, seed: int, sr: int = SR, co_trong: bool = True) -> np.ndarray:
    """Nhạc nhịp đều 113 BPM. Mỗi đoạn 8 ô nhịp giữ CỐ ĐỊNH một mẫu trống (kick phách 1 & 3, snare 2 & 4,
    hi-hat ngẫu nhiên — cùng một mẫu âm mỗi lần đánh, như nhạc làm từ sample), hợp âm theo vòng 4 ô nhịp,
    giai điệu ngẫu nhiên. ``co_trong=False``: bỏ chèn trống nhưng vẫn rút số ngẫu nhiên y hệt."""
    rng = np.random.default_rng(seed)
    n = int(dur_s * sr)
    y = np.zeros(n)
    buoc = O_NHIP / 16
    t = np.arange(int(0.3 * sr)) / sr
    kick = np.sin(2 * np.pi * (50 * t + 1.8 * (1 - np.exp(-t / 0.03)))) * np.exp(-t / 0.18)
    t = np.arange(int(0.2 * sr)) / sr
    snare = (0.6 * rng.standard_normal(len(t)) * np.exp(-t / 0.08)
             + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.06))
    t = np.arange(int(0.06 * sr)) / sr
    hat = np.diff(rng.standard_normal(len(t)) * np.exp(-t / 0.02), prepend=0.0)

    def not_nhac(midi: float, dai: float, bien_do: float) -> np.ndarray:
        tt = np.arange(int(dai * sr)) / sr
        f = 440.0 * 2 ** ((midi - 69) / 12)
        bao = np.minimum(1.0, tt / 0.01) * np.exp(-tt / (0.6 * dai + 1e-3))
        return bien_do * bao * sum(np.sin(2 * np.pi * f * k * tt + rng.uniform(0, 2 * np.pi)) / k
                                   for k in (1, 2, 3, 4))

    def cong(i0: int, x: np.ndarray) -> None:
        if i0 < n:
            i1 = min(n, i0 + len(x))
            y[i0:i1] += x[: i1 - i0]

    tg = 0.0
    while tg < dur_s:                                   # một đoạn = 8 ô nhịp, mẫu trống cố định
        mau_kick = rng.random(16) < 0.12
        mau_kick[[0, 8]] = True
        mau_hat = rng.random(16) < 0.65
        goc = int(rng.integers(45, 57))
        vong = [0] + [int(x) for x in rng.integers(0, 7, 3)]
        for o in range(8):
            if tg >= dur_s:
                break
            i0 = int(tg * sr)
            for k in (0, 4, 7):
                cong(i0, not_nhac(goc + 12 + vong[o % 4] + k, O_NHIP, 0.06))
            for s in range(16):
                j = i0 + int(s * buoc * sr)
                if rng.random() < 0.4:
                    cong(j, not_nhac(goc + 24 + int(rng.integers(0, 12)), buoc * int(rng.integers(1, 3)), 0.08))
                if co_trong:
                    if mau_kick[s]:
                        cong(j, 0.5 * kick)
                    if s in (4, 12):
                        cong(j, 0.35 * snare)
                    if mau_hat[s]:
                        cong(j, 0.10 * hat)
            tg += O_NHIP
    return 0.9 * y / (np.abs(y).max() + 1e-9)


def vong_lap_y_het(dur_s: float, seed: int, so_o_nhip: int = 8, sr: int = SR) -> tuple:
    """Một đoạn ``so_o_nhip`` ô nhịp của ``nhac_co_nhip`` lặp Y HỆT TỪNG MẪU tới ``dur_s`` giây.
    Trả (tín hiệu, chu kỳ giây). Một đoạn trích nằm trọn trong vùng này KHÔNG có mốc duy nhất."""
    nhac = nhac_co_nhip(4 * O_NHIP + so_o_nhip * O_NHIP + 1.0, seed=seed, sr=sr)
    vong = nhac[int(4 * O_NHIP * sr): int((4 + so_o_nhip) * O_NHIP * sr)]
    than = np.tile(vong, int(np.ceil(dur_s * sr / len(vong))))[: int(dur_s * sr)]
    return than, len(vong) / sr


def doi_toc_do(sig: np.ndarray, he_so_cham: float) -> np.ndarray:
    """Phát chậm ``he_so_cham`` lần (> 1 = dài hơn) bằng nội suy tuyến tính. Dùng cho độ lệch rất nhỏ
    (≤ 0,2%): cao độ lệch theo cùng tỷ lệ (≈ 2 cent) — nhỏ hơn hẳn một ô tần số của audfprint (≈ 21,5 Hz)."""
    n_ra = int(round(len(sig) * he_so_cham))
    return np.interp(np.arange(n_ra) / he_so_cham, np.arange(len(sig)), sig)
