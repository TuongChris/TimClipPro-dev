# -*- coding: utf-8 -*-
"""Phản biện THUẬT TOÁN bước «tinh chỉnh mốc từng giây» (TimClipPro/tinh_chinh_moc.py, P-8) — ca đối kháng MỚI.

Ca nhỏ, audio TỔNG HỢP có sự thật biết trước (không dữ liệu thật, không mạng, không sửa mã sản phẩm). Phần lớn gọi
thẳng ``tinh_chinh_dong`` với ``doc_pcm`` giả (mảng 11025 Hz trong bộ nhớ) và neo/lõi dựng như engine (neo lệch
≤ 0,1 s; lõi = phần đoạn thật engine thấy, cắt ~5 % mỗi đầu); vài ca đi đường FFmpeg thật (file WAV 8 kHz, atempo).

Chấm trên trục video, lưới 10 ms:
  «bịa»       giây có đoạn tinh chỉnh mà sự thật KHÔNG dùng clip ở đó;
  «sai ánh xạ» giây có cả hai mà giây clip lệch > dung sai (mọi bản sao hợp lệ của sự thật đều được nhận);
  «hụt»       giây BẮT BUỘC của sự thật không đoạn nào phủ (phần «tuỳ chọn» — im lặng không đo được, đuôi vọng — bỏ qua);
  «cắt 0 s bịa» hai đoạn liền nhau cùng ánh xạ (ranh giới không có thật).
Kiểm cả hợp đồng kết quả: JSON chặt (không NaN/inf), kiểu Python thuần, doan sắp theo video_tu, video_tu ≤ video_den,
cho_cat khớp doan, ho_so sắp xếp, % trong [0, 100].
Kết luận một lượt: SAI_TU_TIN (ĐÃ mà bịa/sai ánh xạ > 0,3 s hoặc cắt bịa) | HUT (ĐÃ mà hụt > 1 s) | CHUA_KHI_PHAI_DA |
DAT. ``--lap N``: chạy N lần mỗi ca (xê dịch bộ nhớ giữa các lần) và so kết quả (trừ thoi_gian_s) — kiểm tất định.

Chạy (Git Bash):
  cd /c/Dev/Tool_Quet/TimClipPro
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \\
      -B -X utf8 ../tools/khop_tung_giay/san_pham/phan_bien/ca_doi_khang.py [--tat-ca | N01 N02 ...] [--lap 2]
  Tự kiểm phần chấm: ``ca_doi_khang.py --tu-kiem``.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "TimClipPro"))  # checkout chứa file này
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\phan_bien"
sys.path[:0] = [MA, os.path.join(MA, "tests")]

import numpy as np  # noqa: E402
import tinh_chinh_moc as tcm  # noqa: E402
from am_thanh_lap import O_NHIP, nhac_co_nhip  # noqa: E402
from conftest import _ghi_wav, _giai_dieu  # noqa: E402

SR = tcm.SR
CA: dict = {}


def ca(ma: str):
    def dk(f):
        CA[ma] = f
        return f
    return dk


# ---------------------------------------------------------------------------------------------- tín hiệu

def am(dai: float, seed: int, sr: int = SR) -> np.ndarray:
    return _giai_dieu(dai, seed=seed, sr=sr).astype(np.float32)


def nhac(dai: float, seed: int, sr: int = SR) -> np.ndarray:
    return nhac_co_nhip(dai, seed=seed, sr=sr).astype(np.float32)


def i_(t: float, sr: int = SR) -> int:
    return int(round(t * sr))


def chen(nen: np.ndarray, doan: np.ndarray, P: float, sr: int = SR) -> np.ndarray:
    ra = nen.copy()
    ra[i_(P, sr): i_(P, sr) + len(doan)] = doan[: len(ra) - i_(P, sr)]
    return ra


def cat(x: np.ndarray, tu: float, den: float, sr: int = SR) -> np.ndarray:
    return x[i_(tu, sr): i_(den, sr)].copy()


def im(x: np.ndarray, tu: float, den: float) -> np.ndarray:
    ra = x.copy()
    ra[i_(tu): i_(den)] = 0.0
    return ra


def giong_noi(dai_s: float, seed: int, sr: int = SR) -> np.ndarray:
    """Âm giống giọng nói (chép cách dựng của test_tinh_chinh_moc._giong_noi): ồn 300–3400 Hz, âm tiết 3–5 Hz,
    câu 1,5–4 s, ngắt 0,2–0,7 s."""
    rng = np.random.default_rng(seed)
    n = int(dai_s * sr)
    pho = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / sr)
    pho[(f < 300) | (f > 3400)] = 0
    bao, t = np.zeros(n), 0.0
    while t < dai_s:
        cau, toc = rng.uniform(1.5, 4.0), rng.uniform(3.0, 5.0)
        i0, i1 = int(t * sr), min(int((t + cau) * sr), n)
        pha = np.arange(i1 - i0) / sr * toc
        bao[i0:i1] = np.sin(np.pi * pha) ** 2 * rng.uniform(0.4, 1.0, int(pha[-1]) + 1)[pha.astype(int)]
        t += cau + rng.uniform(0.2, 0.7)
    return (np.fft.irfft(pho, n) * bao).astype(np.float32)


def de(video: np.ndarray, tu: float, den: float, snr_db: float, seed: int, nguon=giong_noi) -> np.ndarray:
    """Cộng tiếng đè trong [tu, den): RMS(video đoạn đó) / RMS(tiếng đè) = snr_db. Chuẩn hoá đỉnh về 0,95."""
    n0, n1 = i_(tu), i_(den)
    d = nguon(den - tu + 1.0, seed)[: n1 - n0].astype(np.float64)
    ra = video.astype(np.float64).copy()
    ra[n0:n1] += d * math.sqrt(np.mean(ra[n0:n1] ** 2) / np.mean(d ** 2)) * 10 ** (-snr_db / 20)
    return (ra * (0.95 / np.abs(ra).max())).astype(np.float32)


def gian_giai_dieu(seed: int, k: float, tu: float, den: float, dai_goc: float, sr: int = SR) -> np.ndarray:
    """Bản «đổi nhịp giữ cao độ» CHÍNH XÁC của ``_giai_dieu(dai_goc, seed)``[tu, den): cùng các nốt (cùng tần số),
    mỗi nốt dài 0,4·k giây. ``tu``, ``den`` là bội của 0,4 s (biên nốt)."""
    rng = np.random.default_rng(seed)
    n = int(dai_goc / 0.4) + 1
    freqs = rng.uniform(200, 4000, n)
    t = np.arange(int(round(0.4 * k * sr))) / sr
    env = np.hanning(len(t))
    i0, i1 = int(round(tu / 0.4)), int(round(den / 0.4))
    sig = np.concatenate([np.sin(2 * np.pi * f * t) * env for f in freqs[i0:i1]])
    nhieu = np.random.default_rng(seed + 99991).standard_normal(len(sig))
    return ((sig + 0.02 * nhieu) * 0.7).astype(np.float32)


def gioi_han_dinh(x: np.ndarray, nguong: float = 0.95) -> np.ndarray:
    """Bộ giới hạn đỉnh đơn giản: đường bao đỉnh 5 ms, hệ số ≤ nguong/đỉnh, giữ 20 ms + làm mượt 10 ms, rồi kẹp ±1."""
    from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d
    bao = maximum_filter1d(np.abs(x.astype(np.float64)), size=max(1, int(0.005 * SR)))
    g = np.minimum(1.0, nguong / np.maximum(bao, 1e-9))
    g = uniform_filter1d(minimum_filter1d(g, size=int(0.020 * SR)), size=int(0.010 * SR))
    return np.clip(x * g, -1.0, 1.0).astype(np.float32)


def doc_gia(tin_hieu: dict, goi: list | None = None):
    def doc(duong, tu_s, dai_s):
        if goi is not None:
            goi.append((duong, tu_s, dai_s))
        i0 = int(round(tu_s * SR))
        return tin_hieu[duong][i0: i0 + int(round(dai_s * SR))], i0 / SR
    return doc


def seg(vt, vd, ct, cd, k=1.0, tuy_chon=False) -> dict:
    return {"video_tu": vt, "video_den": vd, "clip_tu": ct, "clip_den": cd, "k": k, "tuy_chon": tuy_chon}


# ---------------------------------------------------------------------------------------------- ca (≥ 10 ca MỚI)

@ca("N01")
def n01():
    """Clip có 20 s im lặng tuyệt đối ở ĐẦU; video dùng trọn clip (cả phần im lặng, video im lặng theo)."""
    clip, P = im(am(80, 9701), 0.0, 20.0), 50.37
    video = chen(am(220, 9702), clip, P)
    return dict(clip=clip, video=video, neo=[(P + 0.05, 1.0)], vung=P + 23.0, end=P + 77.0,
                su_that=[seg(P, P + 20, 0, 20, tuy_chon=True), seg(P + 20, P + 80, 20, 80)], ky_vong="da")


@ca("N02")
def n02():
    """Video phát clip HAI LẦN chồng nhau: bản chính + tiếng vọng 0,6× trễ 0,3 s."""
    clip, P = am(60, 9711), 40.37
    v = np.zeros(i_(60.3) + 1, np.float32)
    v[: len(clip)] += clip
    v[i_(0.3): i_(0.3) + len(clip)] += 0.6 * clip
    video = chen(am(160, 9712), v / np.abs(v).max() * 0.8, P)
    return dict(clip=clip, video=video, neo=[(P + 0.05, 1.0)], vung=P + 3.0, end=P + 57.0,
                su_that=[seg(P, P + 60, 0, 60), seg(P + 60, P + 60.3, 60, 60.3, tuy_chon=True)], ky_vong="da")


@ca("N03")
def n03():
    """Video bị khuếch đại ×6 rồi CẮT CỨNG ở ±0,6 (méo nặng) + lệch DC +0,25."""
    clip, P = am(60, 9721), 41.13
    video = np.clip(chen(am(160, 9722), clip, P) * 6.0, -0.6, 0.6) + 0.25
    return dict(clip=clip, video=video.astype(np.float32), neo=[(P - 0.04, 1.0)], vung=P + 3.0, end=P + 57.0,
                su_that=[seg(P, P + 60, 0, 60)], ky_vong="da")


@ca("N04")
def n04(thu_muc: str):
    """Đường FFmpeg THẬT: video là WAV 8 kHz (dải tới 4 kHz), clip WAV 22050 Hz."""
    from scipy.signal import resample_poly
    P = 37.71
    clip = _giai_dieu(60, seed=9731)
    video = _giai_dieu(160, seed=9732)
    video[i_(P, 22050): i_(P, 22050) + len(clip)] = clip
    _ghi_wav(os.path.join(thu_muc, "clip.wav"), clip)
    _ghi_wav(os.path.join(thu_muc, "video_8k.wav"), resample_poly(video, 160, 441), sr=8000)
    return dict(clip=os.path.join(thu_muc, "clip.wav"), video=os.path.join(thu_muc, "video_8k.wav"),
                neo=[(P + 0.07, 1.0)], vung=P + 3.0, end=P + 57.0, pham_vi=(0.0, 160.0),
                su_that=[seg(P, P + 60, 0, 60)], ky_vong="da")


@ca("N05")
def n05():
    """Lõi RẤT NGẮN: video dùng 8,3 s của clip (40,3–48,6), lõi engine 7,5 s."""
    clip, P = am(120, 9741), 70.21
    video = chen(am(180, 9742), cat(clip, 40.3, 48.6), P)
    return dict(clip=clip, video=video, neo=[(P - 40.3 + 0.04, 1.0)], vung=P + 0.4, end=P + 7.9,
                su_that=[seg(P, P + 8.3, 40.3, 48.6)], ky_vong="chua_hoac_da")


@ca("N05b")
def n05b():
    """Lõi 6 s nằm ở NỬA ĐẦU của 12 s dùng thật (engine chỉ thấy nửa đầu)."""
    clip, P = am(120, 9743), 55.55
    video = chen(am(180, 9744), cat(clip, 61.1, 73.1), P)
    return dict(clip=clip, video=video, neo=[(P - 61.1 - 0.06, 1.0)], vung=P + 2.9, end=P + 8.9,
                su_that=[seg(P, P + 12, 61.1, 73.1)], ky_vong="chua_hoac_da")


@ca("N06")
def n06():
    """Neo THỪA SAI đứng ĐẦU (mạnh nhất): (P + 13, 1) không có lần dùng nào; neo đúng đứng sau."""
    clip, P = am(90, 9751), 40.0
    video = chen(am(200, 9752), clip, P)
    return dict(clip=clip, video=video, neo=[(P + 13.0, 1.0), (P + 0.06, 1.0)], vung=P + 4.5, end=P + 85.5,
                su_that=[seg(P, P + 90, 0, 90)], ky_vong="chua_hoac_da")


@ca("N06b")
def n06b():
    """Nhạc có nhịp: neo đúng + neo thừa lệch ĐÚNG 4 ô nhịp (cùng vòng hợp âm, cùng mẫu trống)."""
    clip, P = nhac(90, 9753), 40.0
    video = chen(am(200, 9754), clip, P)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0), (P + 4 * O_NHIP, 1.0)], vung=P + 4.5, end=P + 85.5,
                su_that=[seg(P, P + 90, 0, 90)], ky_vong="chua_hoac_da")


def _neo_lech_nhip(so_o: float, seed: int):
    clip, P = nhac(90, seed), 40.0
    video = chen(am(200, seed + 1), clip, P)
    return dict(clip=clip, video=video, neo=[(P + so_o * O_NHIP + 0.03, 1.0)], vung=P + 4.5, end=P + 85.5,
                su_that=[seg(P, P + 90, 0, 90)], ky_vong="chua")


@ca("N06c")
def n06c():
    """Nhạc có nhịp, CHỈ có neo lệch 4 ô nhịp (8,50 s) — không có ánh xạ đúng nào trong tầm tìm ±0,5 s: phải CHƯA."""
    return _neo_lech_nhip(4, 9755)


@ca("N06d")
def n06d():
    """Như N06c, neo lệch 1 ô nhịp (2,12 s)."""
    return _neo_lech_nhip(1, 9757)


@ca("N06e")
def n06e():
    """Như N06c, neo lệch nửa ô nhịp (1,06 s)."""
    return _neo_lech_nhip(0.5, 9759)


def _doi_nhip(k: float, P: float, seed: int, lech_k: float = 0.0):
    clip = am(90, seed)
    v = gian_giai_dieu(seed, k, 10.0, 80.0, 90)
    video = chen(am(170, seed + 1), v, P)
    dai = 70.0 * k
    k_engine = k * (1.0 + lech_k)
    tam = 45.0                                    # neo engine đúng ở giữa đoạn, trôi ra hai đầu khi k lệch
    dau = P + (tam - 10.0) * k - k_engine * tam + 0.05
    return dict(clip=clip, video=video, neo=[(dau, k_engine)], vung=P + 0.05 * dai, end=P + 0.95 * dai,
                su_that=[seg(P, P + dai, 10, 80, k=k)], ky_vong="da")


@ca("N07")
def n07():
    """Đổi nhịp GIỮ cao độ, k = 0,9 (video nhanh 1,11×) — dựng lại nốt chính xác."""
    return _doi_nhip(0.9, 33.31, 9761)


@ca("N07b")
def n07b():
    """k = 0,9, k của engine lệch +0,3 %."""
    return _doi_nhip(0.9, 33.31, 9763, lech_k=0.003)


@ca("N08")
def n08():
    """Đổi nhịp GIỮ cao độ, k = 1,1 (video chậm)."""
    return _doi_nhip(1.1, 29.87, 9765)


@ca("N08b")
def n08b():
    """k = 1,1, k của engine lệch −0,3 %."""
    return _doi_nhip(1.1, 29.87, 9767, lech_k=-0.003)


@ca("N07f")
def n07f(thu_muc: str):
    """Đường FFmpeg THẬT: đoạn clip[10, 80] qua bộ lọc atempo=1/0,9 (k = 0,9) của FFmpeg, chèn vào video WAV."""
    from scipy.io import wavfile
    P = 31.17
    clip = _giai_dieu(90, seed=9769)
    _ghi_wav(os.path.join(thu_muc, "clip.wav"), clip)
    _ghi_wav(os.path.join(thu_muc, "doan.wav"), clip[i_(10.0, 22050): i_(80.0, 22050)])
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(thu_muc, "doan.wav"),
                    "-filter:a", f"atempo={1 / 0.9:.6f}", os.path.join(thu_muc, "doan_atempo.wav")], check=True)
    sr_d, d = wavfile.read(os.path.join(thu_muc, "doan_atempo.wav"))
    d = d.astype(np.float64) / 32000.0
    video = _giai_dieu(170, seed=9770)
    video[i_(P, 22050): i_(P, 22050) + len(d)] = d
    _ghi_wav(os.path.join(thu_muc, "video.wav"), video)
    dai = len(d) / sr_d
    return dict(clip=os.path.join(thu_muc, "clip.wav"), video=os.path.join(thu_muc, "video.wav"),
                neo=[(P - 0.9 * 10.0 + 0.05, 0.9)], vung=P + 0.05 * dai, end=P + 0.95 * dai, pham_vi=(0.0, 170.0),
                su_that=[seg(P, P + dai, 10, 80, k=dai / 70.0)], ky_vong="da", dung_sai=0.2)


@ca("N09")
def n09():
    """Clip bắt đầu TRƯỚC giây 0 của video: video mất 3 s đầu clip (neo âm)."""
    clip = am(60, 9771)
    video = np.concatenate([cat(clip, 3.0, 60.0), am(100, 9772)])
    return dict(clip=clip, video=video, neo=[(-3.0 + 0.04, 1.0)], vung=2.0, end=54.5, pham_vi=(0.0, 157.0),
                su_that=[seg(0, 57, 3, 60)], ky_vong="da", phai_cham_gioi_han=True)


@ca("N10")
def n10():
    """pham_vi_s NGẮN hơn file: đã quét tới 90 s, clip dùng 60–120 s (phần sau 90 s chưa quét)."""
    clip, P = am(60, 9781), 60.0
    video = chen(am(200, 9782), clip, P)
    return dict(clip=clip, video=video, neo=[(P + 0.05, 1.0)], vung=63.0, end=88.6, pham_vi=(0.0, 90.0),
                su_that=[seg(P, 90, 0, 30), seg(90, 120, 30, 60, tuy_chon=True)], ky_vong="da",
                phai_cham_gioi_han=True)


@ca("N11")
def n11():
    """Đoạn kết thúc ĐÚNG ở cuối file video (clip là thứ cuối cùng của video)."""
    clip, P = am(60, 9791), 100.43
    video = np.concatenate([am(P, 9792)[: i_(P)], clip])
    return dict(clip=clip, video=video, neo=[(P + 0.03, 1.0)], vung=P + 3.0, end=P + 57.0, pham_vi=(0.0, P + 60),
                su_that=[seg(P, P + 60, 0, 60)], ky_vong="da", phai_cham_gioi_han=True)


@ca("N12a")
def n12a():
    """Hai neo cách 1,5 s — tua lùi THẬT 1,5 s: clip[0, 50] rồi clip[48,5, 100]."""
    clip, P = am(100, 9801), 30.0
    video = chen(am(200, 9802), np.concatenate([cat(clip, 0, 50), cat(clip, 48.5, 100)]), P)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0), (P + 1.5 - 0.03, 1.0)], vung=P + 3.0, end=P + 98.5,
                su_that=[seg(P, P + 50, 0, 50), seg(P + 50, P + 101.5, 48.5, 100)], ky_vong="da")


@ca("N12b")
def n12b():
    """Hai neo cách 1,5 s — nhảy TỚI 1,5 s (cắt mất clip[50, 51,5])."""
    clip, P = am(100, 9803), 30.0
    video = chen(am(200, 9804), np.concatenate([cat(clip, 0, 50), cat(clip, 51.5, 100)]), P)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0), (P - 1.5 + 0.05, 1.0)], vung=P + 3.0, end=P + 95.5,
                su_that=[seg(P, P + 50, 0, 50), seg(P + 50, P + 98.5, 51.5, 100)], ky_vong="da")


@ca("N12c")
def n12c():
    """Hai neo cách 1,5 s nhưng neo thứ hai GIẢ (video dùng liền clip)."""
    clip, P = am(100, 9805), 30.0
    video = chen(am(200, 9806), clip, P)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0), (P + 1.54, 1.0)], vung=P + 5.0, end=P + 95.0,
                su_that=[seg(P, P + 100, 0, 100)], ky_vong="chua_hoac_da")


@ca("N13")
def n13():
    """Video to hơn +12 dB rồi qua bộ giới hạn đỉnh (nén dải động)."""
    clip, P = am(60, 9811), 44.44
    video = gioi_han_dinh(chen(am(160, 9812), clip, P) * 4.0)
    return dict(clip=clip, video=video, neo=[(P - 0.06, 1.0)], vung=P + 3.0, end=P + 57.0,
                su_that=[seg(P, P + 60, 0, 60)], ky_vong="da")


def _thay(dai_thay: float, seed: int, nguon=am):
    clip, P, a = am(120, seed), 40.0, 50.2
    video = chen(chen(am(220, seed + 1), clip, P), nguon(dai_thay, seed + 2), P + a)
    return dict(clip=clip, video=video, neo=[(P + 0.05, 1.0)], vung=P + 6.0, end=P + 114.0,
                su_that=[seg(P, P + a, 0, a), seg(P + a + dai_thay, P + 120, a + dai_thay, 120)],
                ky_vong="chua_hoac_da")


@ca("N14")
def n14():
    """4 s tiếng clip bị THAY bằng âm khác giữa đoạn (trục clip vẫn chạy, cùng neo) — có chỗ vắng clip 4 s thật."""
    return _thay(4.0, 9821)


@ca("N14b")
def n14b():
    """Như N14, thay 3 s."""
    return _thay(3.0, 9824)


@ca("N14c")
def n14c():
    """Như N14, thay 5 s."""
    return _thay(5.0, 9827)


@ca("N14d")
def n14d():
    """Như N14, thay 6 s."""
    return _thay(6.0, 9831)


@ca("N14e")
def n14e():
    """Như N14, thay 8 s."""
    return _thay(8.0, 9834)


@ca("N14f")
def n14f():
    """Như N14, thay 10 s."""
    return _thay(10.0, 9837)


def _de_mep(tu_rel: float, den_rel: float, loi: tuple, snr: float, seed: int, nguon=giong_noi):
    clip, P = am(120, seed), 40.0
    video = de(chen(am(240, seed + 1), clip, P), P + tu_rel, P + den_rel, snr, seed + 2, nguon=nguon)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0)], vung=P + loi[0], end=P + loi[1],
                su_that=[seg(P, P + 120, 0, 120)], ky_vong="chua_hoac_da")


@ca("N15")
def n15():
    """Giọng nói đè 0 dB lên 40 s ĐẦU của đoạn dùng; lõi engine chỉ phần sạch (engine không thấy hash dưới lớp đè)."""
    return _de_mep(0.0, 40.0, (42.0, 114.0), 0.0, 9831)


@ca("N15b")
def n15b():
    """Giọng nói đè 0 dB lên 30 s CUỐI; lõi chỉ phần sạch."""
    return _de_mep(90.0, 120.0, (6.0, 88.0), 0.0, 9834)


@ca("N15c")
def n15c():
    """Như N15 nhưng lõi engine PHỦ cả phần bị đè (engine vẫn thấy hash dưới lớp đè)."""
    return _de_mep(0.0, 40.0, (2.0, 114.0), 0.0, 9837)


@ca("N15d")
def n15d():
    """Nhạc có nhịp đè 0 dB lên 40 s đầu; lõi chỉ phần sạch."""
    return _de_mep(0.0, 40.0, (42.0, 114.0), 0.0, 9839, nguon=lambda d, s: nhac(d, s))


@ca("N16")
def n16():
    """Clip TỰ có 10 s im lặng tuyệt đối giữa bài; video dùng nguyên clip (một lần dùng liền)."""
    clip, P = im(am(120, 9841), 50.4, 60.4), 40.0
    video = chen(am(220, 9842), clip, P)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0)], vung=P + 6.0, end=P + 114.0,
                su_that=[seg(P, P + 120, 0, 120)], ky_vong="da")


@ca("N16b")
def n16b():
    """Như N16, khoảng lặng của chính clip 6 s."""
    clip, P = im(am(120, 9843), 50.4, 56.4), 40.0
    video = chen(am(220, 9844), clip, P)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0)], vung=P + 6.0, end=P + 114.0,
                su_that=[seg(P, P + 120, 0, 120)], ky_vong="da")


def _clip_nho(giam_doan_db: float, muc_clip_db: float, seed: int):
    clip, P = am(60, seed).copy(), 70.0
    clip[i_(30.0): i_(31.5)] *= 10 ** (-giam_doan_db / 20)
    video = chen(am(200, seed + 1), clip * 10 ** (-muc_clip_db / 20), P)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0)], vung=P + 3.0, end=P + 57.0,
                su_that=[seg(P, P + 60, 0, 60)], ky_vong="chua_hoac_da")


@ca("N17")
def n17():
    """Clip chèn NHỎ (−30 dB) giữa nội dung to; clip có 1,5 s đoạn khẽ −28 dB (vẫn là tiếng clip, liền mạch)."""
    return _clip_nho(28.0, 30.0, 9851)


@ca("N17b")
def n17b():
    """Như N17: đoạn khẽ −25 dB, clip −33 dB."""
    return _clip_nho(25.0, 33.0, 9853)


@ca("N17c")
def n17c():
    """Như N17: đoạn khẽ −22 dB, clip −36 dB."""
    return _clip_nho(22.0, 36.0, 9855)


@ca("N17d")
def n17d():
    """Như N17: đoạn khẽ −27 dB, clip −33 dB (đoạn khẽ ở sàn −60 dB của video, vẫn ≥ sàn + 30 dB của clip)."""
    return _clip_nho(27.0, 33.0, 9857)


@ca("N17e")
def n17e():
    """Như N17: đoạn khẽ −26 dB, clip −36 dB."""
    return _clip_nho(26.0, 36.0, 9859)


@ca("N17f")
def n17f():
    """Như N17: đoạn khẽ −24 dB, clip −40 dB."""
    return _clip_nho(24.0, 40.0, 9861)


@ca("N17g")
def n17g():
    """Đoạn dùng NGẮN 20 s: clip chèn −36 dB giữa nội dung to (to chiếm > 1 % mức p99 của ±10 s quanh đoạn), clip có
    1,5 s đoạn khẽ −25 dB giữa bài. Clip vẫn phát liền — không có chỗ cắt."""
    clip, P = am(20, 9873).copy(), 70.0
    clip[i_(9.25): i_(10.75)] *= 10 ** (-25.0 / 20)
    video = chen(am(200, 9874), clip * 10 ** (-36.0 / 20), P)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0)], vung=P + 1.0, end=P + 19.0,
                su_that=[seg(P, P + 20, 0, 20)], ky_vong="chua_hoac_da")


@ca("N18")
def n18():
    """DJ lặp 2 ô nhịp ×4 thay 8 ô nhịp giữa bài (trục clip vẫn liền, cùng neo) — nhạc có nhịp."""
    clip, P, a = nhac(120, 9861), 40.0, 50.0
    lap = np.tile(cat(clip, a, a + 2 * O_NHIP), 4)
    sau = a + 8 * O_NHIP
    video = chen(am(220, 9862), np.concatenate([cat(clip, 0, a), lap, cat(clip, sau, 120)]), P)
    st = [seg(P, P + a, 0, a)] + [seg(P + a + 2 * O_NHIP * j, P + a + 2 * O_NHIP * (j + 1), a, a + 2 * O_NHIP)
                                  for j in range(4)] + [seg(P + sau, P + 120, sau, 120)]
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0)], vung=P + 6.0, end=P + 114.0,
                su_that=st, ky_vong="chua_hoac_da")


@ca("N19")
def n19():
    """Hai bản clip CHỒNG nhau 40 s (bản 2 bắt đầu sau 20 s, cộng đè); engine đưa hai neo."""
    clip, P = am(60, 9871), 50.0
    v = np.zeros(i_(80.0) + 1)
    v[: len(clip)] += clip
    v[i_(20.0): i_(20.0) + len(clip)] += clip
    video = chen(am(200, 9872), (v / np.abs(v).max() * 0.8).astype(np.float32), P)
    return dict(clip=clip, video=video, neo=[(P + 0.03, 1.0), (P + 20.0 - 0.04, 1.0)], vung=P + 3.0, end=P + 77.0,
                su_that=[seg(P, P + 60, 0, 60), seg(P + 20, P + 80, 0, 60)], ky_vong="chua_hoac_da")


@ca("N20")
def n20():
    """Nhạc có nhịp: 4 s clip bị thay bằng nhạc KHÁC cùng nhịp, cùng pha ô nhịp (cùng neo)."""
    clip, P, a = nhac(120, 9881), 40.0, 50.0
    video = chen(chen(nhac(220, 9882), clip, P), cat(nhac(120, 9883), a, a + 4.0), P + a)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0)], vung=P + 6.0, end=P + 114.0,
                su_that=[seg(P, P + a, 0, a), seg(P + a + 4, P + 120, a + 4, 120)], ky_vong="chua_hoac_da")


def _tua_lui_de(snr: float, de_tu: float, de_den: float, seed: int, nguon=giong_noi):
    """clip[0, 60] rồi tua lùi 12 s phát clip[48, 100] (engine: một dòng hai neo); tiếng đè quanh chỗ nối."""
    clip, P = am(100, seed), 30.0
    v = chen(am(200, seed + 1), np.concatenate([cat(clip, 0, 60), cat(clip, 48, 100)]), P)
    video = de(v, P + de_tu, P + de_den, snr, seed + 2, nguon=nguon)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0), (P + 12.0 - 0.05, 1.0)], vung=P + 3.0, end=P + 109.0,
                su_that=[seg(P, P + 60, 0, 60), seg(P + 60, P + 112, 48, 100)], ky_vong="chua_hoac_da")


@ca("N21")
def n21():
    """Tua lùi 12 s (hai neo); giọng nói đè 0 dB phủ [52, 68] s quanh chỗ nối 60 s (clip vẫn phát liền dưới lớp đè)."""
    return _tua_lui_de(0.0, 52.0, 68.0, 9891)


@ca("N21b")
def n21b():
    """Như N21, nhạc có nhịp đè 0 dB."""
    return _tua_lui_de(0.0, 52.0, 68.0, 9894, nguon=lambda d, s: nhac(d, s))


@ca("N22")
def n22():
    """Cắt giữa + chèn 6 s âm khác (hai neo cách 6 s); giọng nói đè 0 dB phủ 8 s TRƯỚC chỗ cắt."""
    clip, P = am(120, 9901), 30.0
    v = chen(am(220, 9902), np.concatenate([cat(clip, 0, 60), am(6, 9903), cat(clip, 60, 120)]), P)
    video = de(v, P + 52.0, P + 60.0, 0.0, 9904)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0), (P + 6.0 - 0.05, 1.0)], vung=P + 3.0, end=P + 123.0,
                su_that=[seg(P, P + 60, 0, 60), seg(P + 66, P + 126, 60, 120)], ky_vong="chua_hoac_da")


@ca("N22b")
def n22b():
    """Kiểu video reaction: người nói đè lên clip 6 s rồi DỪNG clip 8 s (chỉ còn giọng nói) rồi phát tiếp (hai neo cách
    8 s). Chỗ vắng clip thật = 8 s lúc dừng."""
    clip, P = am(120, 9921), 30.0
    v = chen(am(220, 9922), np.concatenate([cat(clip, 0, 60), np.zeros(i_(8.0), np.float32), cat(clip, 60, 120)]), P)
    n0, n1 = i_(P + 54.0), i_(P + 68.0)
    noi = giong_noi(15.0, 9923)[: n1 - n0].astype(np.float64)
    ra = v.astype(np.float64).copy()
    ra[n0:n1] += noi * math.sqrt(np.mean(ra[n0: i_(P + 60.0)] ** 2) / np.mean(noi ** 2))   # 0 dB so với tiếng clip
    video = (ra * (0.95 / np.abs(ra).max())).astype(np.float32)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0), (P + 8.0 - 0.05, 1.0)], vung=P + 3.0, end=P + 125.0,
                su_that=[seg(P, P + 60, 0, 60), seg(P + 68, P + 128, 60, 120)], ky_vong="chua_hoac_da")


@ca("N15e")
def n15e():
    """Giọng nói đè 0 dB lên 25 s ĐẦU (hạt giống khác); lõi = phần sạch + 3 s (như engine thấy vài hash dưới lớp đè)."""
    return _de_mep(0.0, 25.0, (22.0, 114.0), 0.0, 9925)


@ca("N24")
def n24(thu_muc: str, P: float = 150.37):
    """Đường FFmpeg THẬT: video M4A (AAC 128 kbps, bộ mã aac của FFmpeg — như .m4a/.mp4 thường gặp), clip WAV.
    Cùng audio dạng WAV thì tinh chỉnh đúng trong < 1 s."""
    clip = _giai_dieu(60, seed=9941)
    video = _giai_dieu(400, seed=9942)
    video[i_(P, 22050): i_(P, 22050) + len(clip)] = clip
    _ghi_wav(os.path.join(thu_muc, "clip.wav"), clip)
    _ghi_wav(os.path.join(thu_muc, "video.wav"), video)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(thu_muc, "video.wav"),
                    "-c:a", "aac", "-b:a", "128k", os.path.join(thu_muc, "video.m4a")], check=True)
    return dict(clip=os.path.join(thu_muc, "clip.wav"), video=os.path.join(thu_muc, "video.m4a"),
                neo=[(P + 0.04, 1.0)], vung=P + 3.0, end=P + 57.0, pham_vi=(0.0, 400.0), han_chot_s=20.0,
                su_that=[seg(P, P + 60, 0, 60)], ky_vong="da")


@ca("N24b")
def n24b(thu_muc: str):
    """Như N24, clip ở 151,83 s."""
    return n24(thu_muc, 151.83)


@ca("N24c")
def n24c(thu_muc: str):
    """Như N24, clip ở 149,21 s."""
    return n24(thu_muc, 149.21)


@ca("N24d")
def n24d(thu_muc: str):
    """Như N24, clip ở 173,66 s."""
    return n24(thu_muc, 173.66)


@ca("N23")
def n23():
    """Clip kết thúc bằng fade-out tuyến tính biên độ 4 s; video dùng tới hết clip rồi sang nội dung khác."""
    clip, P = am(60, 9911).copy(), 45.5
    n0 = i_(56.0)
    clip[n0:] *= np.linspace(1.0, 0.0, len(clip) - n0).astype(np.float32)
    video = chen(am(170, 9912), clip, P)
    return dict(clip=clip, video=video, neo=[(P + 0.04, 1.0)], vung=P + 3.0, end=P + 57.0,
                su_that=[seg(P, P + 60, 0, 60)], ky_vong="da")


# ---------------------------------------------------------------------------------------------- chấm

def kiem_hop_dong(kq: dict) -> list:
    loi = []
    try:
        if json.loads(json.dumps(kq, allow_nan=False)) != kq:
            loi.append("JSON khứ hồi khác")
    except ValueError as e:
        loi.append(f"JSON chặt hỏng: {e}")

    def duyet(x, duong="kq"):
        if isinstance(x, dict):
            for k, v in x.items():
                duyet(v, f"{duong}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                duyet(v, f"{duong}[{i}]")
        elif type(x) not in (str, int, float, bool):
            loi.append(f"kiểu {type(x).__name__} ở {duong}")
        elif type(x) is float and not math.isfinite(x):
            loi.append(f"không hữu hạn ở {duong}")
    duyet(kq)
    for k in ("phien_ban", "trang_thai", "ly_do", "doan", "cho_cat", "ho_so", "nguong_pct", "nen_p99_pct",
              "cham_gioi_han", "thoi_gian_s"):
        if k not in kq:
            loi.append(f"thiếu khoá {k}")
    doan = kq.get("doan", [])
    if [d["video_tu"] for d in doan] != sorted(d["video_tu"] for d in doan):
        loi.append("doan không sắp theo video_tu")
    for i, d in enumerate(doan):
        if d["video_den"] < d["video_tu"]:
            loi.append(f"doan[{i}] video_den < video_tu")
        if d["clip_den"] < d["clip_tu"]:
            loi.append(f"doan[{i}] clip_den < clip_tu")
        for t in ("tuong_dong_tb", "tuong_dong_min"):
            if not 0.0 <= d[t] <= 100.0:
                loi.append(f"doan[{i}].{t} ngoài [0, 100]")
    for a, b in zip(doan, doan[1:]):
        if a["video_den"] > b["video_tu"] + 1e-9:
            loi.append("hai đoạn chồng nhau")
    if len(kq.get("cho_cat", [])) != max(0, len(doan) - 1):
        loi.append("số cho_cat ≠ số đoạn − 1")
    for c, a, b in zip(kq.get("cho_cat", []), doan, doan[1:]):
        if (c["video_tu"], c["video_den"], c["clip_bo_tu"], c["clip_bo_den"]) != \
                (a["video_den"], b["video_tu"], a["clip_den"], b["clip_tu"]):
            loi.append("cho_cat không khớp doan")
    hs = [t for t, _ in kq.get("ho_so", [])]
    if hs != sorted(hs):
        loi.append("ho_so không sắp xếp")
    if any(not 0.0 <= p <= 100.0 for _, p in kq.get("ho_so", [])):
        loi.append("ho_so % ngoài [0, 100]")
    if kq.get("trang_thai") == tcm.DA and (not doan or kq.get("ly_do")):
        loi.append("ĐÃ mà không có đoạn hoặc có lý do")
    if kq.get("trang_thai") == tcm.CHUA and not kq.get("ly_do"):
        loi.append("CHƯA mà không có lý do")
    return loi


def cham(kq: dict, c: dict, buoc: float = 0.01) -> dict:
    st, tol = c["su_that"], c.get("dung_sai", 0.15)
    ra = {"trang_thai": kq["trang_thai"], "ly_do": kq.get("ly_do", ""), "hop_dong": kiem_hop_dong(kq)}
    if kq["trang_thai"] != tcm.DA:
        ra["ket_luan"] = "CHUA_KHI_PHAI_DA" if c["ky_vong"] == "da" else "DAT"
        return ra
    doan = kq["doan"]
    lo = min([s["video_tu"] for s in st] + [d["video_tu"] for d in doan]) - 1.0
    hi = max([s["video_den"] for s in st] + [d["video_den"] for d in doan]) + 1.0
    t = np.arange(lo, hi, buoc) + buoc / 2
    co_that = np.zeros(len(t), bool)
    bat_buoc = np.zeros(len(t), bool)
    c_that = []
    for s in st:
        m = (t >= s["video_tu"]) & (t < s["video_den"])
        co_that |= m
        if not s.get("tuy_chon"):
            bat_buoc |= m
        c_that.append(np.where(m, s["clip_tu"] + (t - s["video_tu"]) / s.get("k", 1.0), np.nan))
    c_that = np.vstack(c_that)
    co_ra = np.zeros(len(t), bool)
    c_ra = np.full(len(t), np.nan)
    for d in doan:
        m = (t >= d["video_tu"]) & (t < d["video_den"])
        co_ra |= m
        c_ra = np.where(m, d["clip_tu"] + (t - d["video_tu"]) / d["k"], c_ra)
    lech = np.nanmin(np.abs(c_that - c_ra[None, :]), axis=0, initial=np.inf) if len(st) else np.full(len(t), np.inf)
    ra["bia_s"] = round(float(np.sum(co_ra & ~co_that)) * buoc, 3)
    ra["sai_anh_xa_s"] = round(float(np.sum(co_ra & co_that & (lech > tol))) * buoc, 3)
    ra["hut_s"] = round(float(np.sum(bat_buoc & ~co_ra)) * buoc, 3)
    cat_bia = 0
    for a, b in zip(doan, doan[1:]):
        lien = abs(b["video_tu"] - a["video_den"]) < 0.05 and abs(b["clip_tu"] - a["clip_den"]) < 0.15
        ranh_that = any(abs(s["video_tu"] - b["video_tu"]) <= 0.5 for s in st[1:]) or \
            any(abs(s["video_den"] - a["video_den"]) <= 0.5 for s in st[:-1])
        if lien and not ranh_that:
            cat_bia += 1
    ra["cat_0s_bia"] = cat_bia
    # sai số mép của từng đoạn thật bắt buộc (đoạn ra phủ nó nhiều nhất)
    mep = []
    for s in st:
        if s.get("tuy_chon"):
            continue
        phu = [(min(d["video_den"], s["video_den"]) - max(d["video_tu"], s["video_tu"]), d) for d in doan]
        phu = [x for x in phu if x[0] > 0]
        if not phu:
            mep.append({"that": [s["video_tu"], s["video_den"]], "ra": None})
            continue
        ds = [d for _, d in phu]
        mep.append({"that": [s["video_tu"], s["video_den"]],
                    "d_tu": round(min(d["video_tu"] for d in ds) - s["video_tu"], 3),
                    "d_den": round(max(d["video_den"] for d in ds) - s["video_den"], 3)})
    ra["mep"] = mep
    ra["cach"] = [d["cach_tim_mep"] for d in doan]
    if c["ky_vong"] == "chua":
        ra["ket_luan"] = "SAI_TU_TIN"
    elif ra["bia_s"] > 0.3 or ra["sai_anh_xa_s"] > 0.3 or cat_bia:
        ra["ket_luan"] = "SAI_TU_TIN"
    elif ra["hut_s"] > 1.0:
        ra["ket_luan"] = "HUT"
    else:
        ra["ket_luan"] = "DAT"
    if c.get("phai_cham_gioi_han") and not kq["cham_gioi_han"]:
        ra["ket_luan"] += "+THIEU_CHAM_GIOI_HAN"
    return ra


def tu_kiem() -> int:
    st = [seg(10, 20, 0, 10)]
    c = {"su_that": st, "ky_vong": "da"}
    gia = {"phien_ban": 1, "trang_thai": tcm.DA, "ly_do": "", "cho_cat": [], "ho_so": [[10.5, 99.0]],
           "nguong_pct": 30.0, "nen_p99_pct": 15.0, "cham_gioi_han": False, "thoi_gian_s": 0.1,
           "doan": [{"video_tu": 10.0, "video_den": 20.0, "clip_tu": 0.0, "clip_den": 10.0, "k": 1.0,
                     "tuong_dong_tb": 99.0, "tuong_dong_min": 98.0, "cach_tim_mep": ["dau_clip", "bac_thang"]}]}
    r = cham(gia, c)
    assert r["ket_luan"] == "DAT" and r["bia_s"] == 0 and r["hut_s"] == 0 and not r["hop_dong"], r
    gia2 = json.loads(json.dumps(gia))
    gia2["doan"][0]["video_den"] = 23.0                  # lấn 3 s ra ngoài
    gia2["doan"][0]["clip_den"] = 13.0
    assert cham(gia2, c)["ket_luan"] == "SAI_TU_TIN"
    gia3 = json.loads(json.dumps(gia))
    gia3["doan"][0]["clip_tu"] = 1.0                     # ánh xạ lệch 1 s
    gia3["doan"][0]["clip_den"] = 11.0
    assert cham(gia3, c)["sai_anh_xa_s"] > 9.0
    gia4 = json.loads(json.dumps(gia))
    gia4["doan"][0]["video_tu"] = 13.0                   # hụt 3 s
    gia4["doan"][0]["clip_tu"] = 3.0
    assert cham(gia4, c)["ket_luan"] == "HUT"
    gia5 = json.loads(json.dumps(gia))
    gia5["doan"][0]["tuong_dong_tb"] = float("nan")
    assert any("JSON chặt" in x for x in cham(gia5, c)["hop_dong"])
    print("tự kiểm phần chấm: ĐẠT 5/5")
    return 0


# ---------------------------------------------------------------------------------------------- chạy

def chay_ca(ma: str, lap: int) -> dict:
    f = CA[ma]
    thu_muc = os.path.join(RA, "tmp", ma)
    if f.__code__.co_argcount:
        shutil.rmtree(thu_muc, ignore_errors=True)
        os.makedirs(thu_muc, exist_ok=True)
        c = f(thu_muc)
    else:
        c = f()
    goi: list = []
    if isinstance(c["clip"], np.ndarray):
        doc = doc_gia({"clip": c["clip"], "video": c["video"]}, goi)
        duong = ("clip", "video")
    else:
        doc, duong = None, (c["clip"], c["video"])
    lan = []
    giu = []
    for j in range(lap):
        giu.append(np.empty(int(np.random.default_rng(j).integers(1, 4097)), np.uint8))   # xê dịch đống bộ nhớ
        t0 = time.monotonic()
        han = time.monotonic() + c["han_chot_s"] if c.get("han_chot_s") else None    # như engine: có hạn chót
        kq = tcm.tinh_chinh_dong(*duong, c["neo"], c["vung"], c["end"], pham_vi_s=c.get("pham_vi"), doc_pcm=doc,
                                 han_chot=han)
        lan.append((kq, time.monotonic() - t0))
    kq = lan[0][0]
    ra = {"ma": ma, "mo_ta": (f.__doc__ or "").strip(), "neo": c["neo"], "vung": c["vung"], "end": c["end"],
          "pham_vi": c.get("pham_vi"), "ky_vong": c["ky_vong"], "su_that": c["su_that"], "ket_qua": kq,
          "cham": cham(kq, c), "giay": [round(x[1], 2) for x in lan]}
    bo = {k: v for k, v in kq.items() if k != "thoi_gian_s"}
    ra["tat_dinh"] = all({k: v for k, v in x[0].items() if k != "thoi_gian_s"} == bo for x in lan[1:])
    if goi:
        ra["giai_ma_s"] = {ten: round(sum(d for t, _, d in goi if t == ten) / lap, 1) for ten in ("clip", "video")}
    return ra


def tom_tat(r: dict) -> str:
    kq, ch = r["ket_qua"], r["cham"]
    if kq["trang_thai"] == tcm.DA:
        dd = "; ".join(f"[{d['video_tu']:.3f},{d['video_den']:.3f}]←clip[{d['clip_tu']:.3f},{d['clip_den']:.3f}]"
                       f" k{d['k']:.4f} {d['cach_tim_mep'][0]}/{d['cach_tim_mep'][1]} tb{d['tuong_dong_tb']}"
                       for d in kq["doan"])
        so = f"bịa {ch['bia_s']} s, sai ánh xạ {ch['sai_anh_xa_s']} s, hụt {ch['hut_s']} s, cắt 0 s bịa {ch['cat_0s_bia']}"
        return f"ĐÃ {dd} | {so} | chạm giới hạn {kq['cham_gioi_han']} | T {kq['nguong_pct']} nền {kq['nen_p99_pct']}"
    return f"CHƯA «{kq['ly_do']}» | T {kq['nguong_pct']} nền {kq['nen_p99_pct']}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ca", nargs="*")
    ap.add_argument("--tat-ca", action="store_true")
    ap.add_argument("--lap", type=int, default=1)
    ap.add_argument("--tu-kiem", action="store_true")
    a = ap.parse_args()
    if a.tu_kiem:
        return tu_kiem()
    ds = list(CA) if a.tat_ca else a.ca
    os.makedirs(RA, exist_ok=True)
    tong = []
    for ma in ds:
        r = chay_ca(ma, max(1, a.lap))
        with open(os.path.join(RA, f"{ma}.json"), "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
        dong = (f"{ma}: {r['cham']['ket_luan']} | {tom_tat(r)} | tất định {r['tat_dinh']} | {r['giay']} s"
                + (f" | hợp đồng: {r['cham']['hop_dong']}" if r["cham"]["hop_dong"] else ""))
        print(dong, flush=True)
        tong.append({"ma": ma, "mo_ta": r["mo_ta"], "ket_luan": r["cham"]["ket_luan"], "dong": dong})
    if a.tat_ca:
        with open(os.path.join(RA, "tong_hop.json"), "w", encoding="utf-8") as fh:
            json.dump({"luc": time.strftime("%Y-%m-%d %H:%M:%S"), "ca": tong}, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
