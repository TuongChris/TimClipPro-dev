# -*- coding: utf-8 -*-
"""Bộ CA ẨN VÒNG 2 (held-out) cho tinh_chinh_moc.py (P-8 «tinh chỉnh mốc từng giây») — dựng audio + sự thật (14/11/2026).

Độc lập với bộ trong mẫu mà module được chỉnh theo (S0–S9, S4b, S5b, S6b, S7b, S7c, X1–X3, H1a–H4) VÀ với vòng 1 (A01–A18,
seed 5011–5182): seed ≥ 7000, mỗi kiểu đổi chi tiết so với vòng 1 (nhịp, loại nền, dạng chuyển mờ, kiểu khoảng lặng, cắt
đúng phách, khe khi tua, nội dung clip dài xen kẽ, màu ồn, vùng chứa video...). Người dựng KHÔNG đọc tinh_chinh_moc.py, test
của nó hay dữ liệu vòng 1. Audio 100 % giả lập từ bộ sinh của repo (tests/conftest.py ``_giai_dieu``/``_ghi_wav``,
tests/am_thanh_lap.py ``nhac_co_nhip``) + ồn/giọng tổng hợp bằng numpy + FFmpeg; không dữ liệu thật, không mạng.

Dùng lại tiện ích của vòng 1 bằng import (``dung_ca.py`` không sửa, kết quả vòng 1 không đổi). Mỗi ca một thư mục
``<RA>/<ten>/``: ``kho/`` (clip gốc), video vi phạm, ``su_that.json`` cùng khuôn vòng 1:
  ten, loai, mo_ta, seed, ky_vong («da» = phải tinh chỉnh và ĐÚNG; «chua_hoac_da» = CHƯA cũng được, ĐÃ thì phải đúng),
  doan [{clip, video_tu, video_den, clip_tu, clip_den, he_so}] — đoạn dùng THẬT của TỪNG clip (he_so = tốc độ video so
  với clip: video_den − video_tu = (clip_den − clip_tu)/he_so); mep_mo [{t, nua_rong}] — mép mờ thật (tâm dốc ± nửa bề
  rộng); doan_ban_sao_nguyen_mau — chỉ số các đoạn là bản sao TỪNG MẪU trong file video (để kiểm tới 1 mẫu);
  kiem_su_that — đo lại từ audio bằng kiem_su_that_2.py (= kiem_su_that.py vòng 1 + phép thêm cho kiểu mới).
Mốc sự thật tính từ CHỈ SỐ MẪU lúc dựng (``dung_ca._doan``), không lấy số danh nghĩa.

Chạy (Git Bash; không đối số = dựng mọi ca):
  cd /c/Dev/Tool_Quet/TimClipPro
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \\
      -B -X utf8 ../tools/khop_tung_giay/san_pham/ca_an/dung_ca_2.py [B01 B02 ...]
Rồi ``chay_engine_2.py`` (engine THẬT, từng ca một).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import wave

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import dung_ca as dc  # noqa: E402  (tiện ích vòng 1 — chỉ import)
import kiem_su_that_2  # noqa: E402
from dung_ca import SR, _doan, _i, nhac_co_nhip  # noqa: E402

RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\ca_an_2"
SEED_TOI_THIEU = 7000


# ---------------------------------------------------------------- tiện ích riêng vòng 2
def _nhac(dai_s: float, seed: int, bpm: float = 113.0) -> np.ndarray:
    """nhac_co_nhip ở nhịp ``bpm`` (113 = mặc định của am_thanh_lap)."""
    if bpm == 113.0:
        return nhac_co_nhip(dai_s, seed=seed)
    with dc._nhip(bpm):
        return nhac_co_nhip(dai_s, seed=seed)


def _giua_not(*giay: float) -> None:
    """Mép trên clip ``_giai_dieu`` phải rơi GIỮA nốt (bao Hanning ≥ 0,5): giây mod 0,4 trong [0,1; 0,3]."""
    for t in giay:
        r = round(t % 0.4, 6)
        assert 0.1 - 1e-6 <= r <= 0.3 + 1e-6, f"mép {t} rơi sát ranh giới nốt (mod 0,4 = {r})"


def _giong_noi_2(n: int, seed: int) -> np.ndarray:
    """Âm «giống giọng nói» kiểu KHÁC vòng 1: mỗi âm tiết (3–5 Hz) là ồn dải 150–4000 Hz nghiêng −6 dB/quãng tám trên
    500 Hz (phổ dài hạn của tiếng nói) có hai «formant» ngẫu nhiên (F1 300–850 Hz, F2 900–2500 Hz), bao Hanning, biên độ
    0,4–1; 6–12 âm tiết một cụm rồi ngắt hơi 0,3–0,8 s."""
    rng = np.random.default_rng(seed)
    ra = np.zeros(n)
    t, con = 0, int(rng.integers(6, 13))
    while t < n:
        if con == 0:
            t += _i(rng.uniform(0.3, 0.8))
            con = int(rng.integers(6, 13))
            continue
        L = _i(1.0 / rng.uniform(3.0, 5.0))
        m = min(L, n - t)
        if m < 64:
            break
        f = np.fft.rfftfreq(m, 1.0 / SR)
        H = ((f >= 150.0) & (f <= 4000.0)) * np.minimum(1.0, 500.0 / np.maximum(f, 1.0))
        f1, f2 = rng.uniform(300.0, 850.0), rng.uniform(900.0, 2500.0)
        H = H * (1.0 + 3.0 * np.exp(-0.5 * ((f - f1) / 80.0) ** 2) + 2.0 * np.exp(-0.5 * ((f - f2) / 120.0) ** 2))
        x = np.fft.irfft(np.fft.rfft(rng.standard_normal(m)) * H, m)
        ra[t:t + m] += x / (np.sqrt(np.mean(x * x)) + 1e-12) * rng.uniform(0.4, 1.0) * np.hanning(m)
        t += L
        con -= 1
    return ra


def _on_hong(n: int, seed: int, f_lo: float = 80.0, f_hi: float = 5500.0) -> np.ndarray:
    """Ồn hồng (công suất ∝ 1/f) trong dải [f_lo, f_hi] — ồn nền kiểu tiếng ù/đám đông, khác ồn trắng của vòng 1."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    H = np.where((f >= f_lo) & (f <= f_hi), 1.0 / np.sqrt(np.maximum(f, 1.0)), 0.0)
    return np.fft.irfft(np.fft.rfft(rng.standard_normal(n)) * H, n)


def _db_dai(a: np.ndarray, b: np.ndarray, lo: float, hi: float) -> float:
    """10·log10(năng lượng a / năng lượng b) chỉ trong dải [lo, hi] Hz (SNR như phổ mà bước so khớp nhìn thấy)."""
    def nl(x):
        f = np.fft.rfftfreq(len(x), 1.0 / SR)
        p = np.abs(np.fft.rfft(x)) ** 2
        return float(p[(f >= lo) & (f <= hi)].sum())
    return round(10.0 * np.log10(nl(a) / nl(b)), 3)


def _chen_chuyen_mo_cong_suat(nen: np.ndarray, clip: np.ndarray, i0: int, j0: int, j1: int, m: int) -> np.ndarray:
    """Đặt clip[j0:j1] ở mẫu i0 với chuyển mờ CÔNG SUẤT KHÔNG ĐỔI (sin/cos — mặc định «Constant Power» của trình dựng
    phim) dài 2m mẫu, TÂM dốc ở mép khai; trong dốc clip ×sin, nền ×cos (vào) và ngược lại (ra)."""
    L = j1 - j0
    assert j0 >= m and j1 + m <= len(clip) and i0 >= m and i0 + L + m <= len(nen)
    v = nen.copy()
    u = (np.arange(2 * m) + 0.5) / (2 * m)
    len_, xuong = np.sin(0.5 * np.pi * u), np.cos(0.5 * np.pi * u)
    v[i0 - m:i0 + m] = xuong * nen[i0 - m:i0 + m] + len_ * clip[j0 - m:j0 + m]
    v[i0 + m:i0 + L - m] = clip[j0 + m:j1 - m]
    v[i0 + L - m:i0 + L + m] = xuong * clip[j1 - m:j1 + m] + len_ * nen[i0 + L - m:i0 + L + m]
    return v


def _khuc_40p(n: int, seed: int, not_khi_chan: bool) -> np.ndarray:
    """Khúc n (0–9) 240 s của clip 40 phút XEN KẼ nội dung: nốt ngẫu nhiên / nhạc có nhịp 113 BPM luân phiên."""
    la_not = (n % 2 == 0) == not_khi_chan
    x = dc._giai(240.0, seed) if la_not else nhac_co_nhip(240.0, seed=seed)
    assert len(x) == _i(240.0), len(x)
    return x


def _ghi_clip_40p(path: str, seeds: list, not_khi_chan: bool) -> None:
    """Clip 40 phút = 10 khúc ``_khuc_40p`` ghi nối tiếp (cùng thang int16 của _ghi_wav) — không giữ 2400 s trong RAM."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        for n, s in enumerate(seeds):
            w.writeframes((np.clip(_khuc_40p(n, s, not_khi_chan), -1, 1) * 32000).astype(np.int16).tobytes())


def _trich_40p(seeds: list, not_khi_chan: bool) -> np.ndarray:
    """clip[1500..1800] (25:00–30:00): khúc 6 (1440–1680 s) từ giây 60 + khúc 7 (1680–1920 s) tới giây 120."""
    return np.concatenate([_khuc_40p(6, seeds[6], not_khi_chan)[_i(60.0):],
                           _khuc_40p(7, seeds[7], not_khi_chan)[:_i(120.0)]])


def _clip40_opus(d: str, ten: str, seeds: list, not_khi_chan: bool, kho_dai: bool) -> dict:
    kho = os.path.join(d, "kho")
    os.makedirs(kho, exist_ok=True)
    tam = os.path.join(d, "_tam_clip40.wav")
    _ghi_clip_40p(tam, seeds, not_khi_chan)
    dc._ffmpeg("-i", tam, *dc.OPUS_KHO, os.path.join(kho, ten))
    os.remove(tam)
    if kho_dai:
        with open(os.path.join(kho, ".kho_video_dai"), "a", encoding="utf-8"):
            pass                                          # = channel.dat_kho_video_dai: kho video dài D-34, mốc 21 bit
    return {"clip": ten, "do_dai_nguon_s": 2400.0, "dinh_dang": dc.DD_OPUS}


# ---------------------------------------------------------------- các ca
def ca_b01(d: str) -> dict:
    clip = _nhac(286.0, 7011, 140.0)
    kho = [dc._kho(d, "goc_B01.opus", clip, opus=True)]
    i0 = _i(401.23)
    v = dc._video(d, dc._chen(dc._giai(900, 7012), clip, i0))
    return dc._st("B01_nhip140_tron_opus", "nhip_140bpm_dung_tron_kho_opus",
                  "Clip nhạc có nhịp 140 BPM (am_thanh_lap.nhac_co_nhip với ô nhịp 1,714 s thay 2,124 s; trống mẫu cố định mỗi "
                  "8 ô nhịp) dài 286 s, kho .opus 64 kbps (như kho thật), dùng TRỌN, sạch, chèn cắt cứng ở 401,23 s của video "
                  "900 s nền nốt ngẫu nhiên.", {"clip_nhac_co_nhip_140bpm": 7011, "nen_giai_dieu": 7012}, v, kho,
                  [_doan("goc_B01.opus", i0, 0, len(clip))], "da",
                  "Sạch, dùng trọn, tương phản cao; khác bộ trong mẫu ở nhịp nhanh (một ô nhịp 1,714 s: cửa sổ 3 s chứa gần hai "
                  "ô nhịp tự giống nhau) và kho opus.", nhip_clip_bpm=140.0, chu_ky_phach_do_s=dc._chu_ky_phach(clip),
                  doan_ban_sao_nguyen_mau=[])


def ca_b02(d: str) -> dict:
    clip = _nhac(330.0, 7021, 96.0)
    kho = [dc._kho(d, "goc_B02.wav", clip)]
    j0, j1, i0 = _i(83.41), _i(291.77), _i(377.7)
    doan = clip[j0:j1]
    nen = _nhac(1000.0, 7022, 128.0)
    vung = slice(i0, i0 + len(doan))
    nen = nen * (dc._rms(doan) / dc._rms(nen[vung]) * 10 ** (-5 / 20))
    tron = nen.copy()
    tron[vung] += doan
    tron, s = dc._chuan_hoa(tron)
    v = dc._video(d, tron)
    return dc._st("B02_nhip96_tren_nen_nhip128", "nhip_mot_phan_tren_nen_nhip_khac_toc",
                  "Clip nhạc có nhịp 96 BPM dài 330 s, dùng MỘT PHẦN clip[83,41..291,77], TRỘN lên một nền nhạc có nhịp 128 BPM "
                  "seed khác (cùng mẫu kick tất định của am_thanh_lap, khác nhịp) chạy SUỐT video 1000 s; trong vùng clip nền "
                  "thấp hơn clip 5 dB. Clip vào/ra cắt cứng trên nền liên tục, từ 377,7 s.",
                  {"clip_nhac_co_nhip_96bpm": 7021, "nen_nhac_co_nhip_128bpm": 7022}, v, kho,
                  [_doan("goc_B02.wav", i0, j0, j1)], "da",
                  "Clip trội nền 5 dB, nền khác nhịp (không tự giống clip ở bội ô nhịp) → một đoạn [377,7; 586,06], mép cắt "
                  "cứng. (Nếu engine bật moc_mo_ho thì nơi gọi không tinh chỉnh — xem dieu_chinh_ky_vong sau lượt engine.)",
                  snr_clip_tren_nen_db=round(20 * np.log10(dc._rms(doan) / dc._rms(nen[vung])), 3),
                  he_so_chuan_hoa=round(s, 6), doan_ban_sao_nguyen_mau=[])


def ca_b03(d: str) -> dict:
    clip = _nhac(300.0, 7031)
    kho = [dc._kho(d, "goc_B03.wav", clip)]
    j0, j1, i0 = _i(24.6), _i(285.0), _i(300.9)
    video = dc._chen(dc._giai(900, 7032), clip[j0:j1], i0)
    n3 = (j1 - j0) // 3
    a, b = i0 + n3, i0 + 2 * n3
    g = _giong_noi_2(b - a, 7033)
    g *= dc._rms(video[a:b]) / dc._rms(g)                 # 0 dB so với tiếng clip trong vùng đè
    video[a:b] += g
    video, s = dc._chuan_hoa(video)
    v = dc._video(d, video)
    return dc._st("B03_giong_noi_giua_nhip", "giong_noi_0db_mot_phan_ba_giua_tren_nhip",
                  "Clip nhạc có nhịp 113 BPM dài 300 s, dùng clip[24,6..285,0] (260,4 s) ở 300,9 s của video 900 s nền nốt "
                  "ngẫu nhiên; âm GIỐNG GIỌNG NÓI kiểu khác vòng 1 (âm tiết 3–5 Hz, ồn 150–4000 Hz nghiêng −6 dB/quãng tám, hai "
                  "formant ngẫu nhiên mỗi âm tiết, cụm 6–12 âm tiết rồi ngắt hơi) ĐÈ 0 dB CHỈ trong một phần ba giữa (video "
                  "387,7–474,5 s); hai phần ba còn lại sạch. Clip vẫn nguyên bên dưới lớp đè.",
                  {"clip_nhac_co_nhip": 7031, "nen": 7032, "giong_noi": 7033}, v, kho,
                  [_doan("goc_B03.wav", i0, j0, j1)], "da",
                  "Một đoạn liền: clip có mặt suốt (2/3 sạch, 1/3 dưới giọng 0 dB). Báo «chỗ cắt» trong vùng đè là SAI.",
                  vung_de_giong_noi=[round(a / SR, 6), round(b / SR, 6)],
                  snr_vung_de_db=round(20 * np.log10(dc._rms(clip[j0 + n3:j0 + 2 * n3]) / dc._rms(g)), 3),
                  he_so_chuan_hoa=round(s, 6), doan_ban_sao_nguyen_mau=[])


def ca_b04(d: str) -> dict:
    clip = dc._giai(330, 7041)
    kho = [dc._kho(d, "goc_B04.wav", clip)]
    j0, j1, i0, m = _i(40.5), _i(287.7), _i(250.0), _i(1.0)
    nen = 0.5 * nhac_co_nhip(800, seed=7042)              # nền nhạc có nhịp, đỉnh 0,45: tổng trong dốc không cắt đỉnh
    video = _chen_chuyen_mo_cong_suat(nen, clip, i0, j0, j1, m)
    video, s = dc._chuan_hoa(video)
    assert s == 1.0, s                                    # không co cả video → phần giữa vẫn là bản sao từng mẫu
    v = dc._video(d, video)
    dn = _doan("goc_B04.wav", i0, j0, j1)
    return dc._st("B04_chuyen_mo_cong_suat_2s", "chuyen_mo_cong_suat_2s_vao_ra",
                  "Clip nốt ngẫu nhiên 330 s, dùng clip[40,5..287,7] ở 250,0 s của video 800 s NỀN NHẠC CÓ NHỊP 113 BPM (đỉnh "
                  "0,45); CHUYỂN MỜ 2 s công suất không đổi (clip ×sin, nền ×cos — «Constant Power» của trình dựng phim) khi "
                  "vào và khi ra; tâm dốc = mép khai, trong dốc hai bên trộn theo sin/cos, ngoài dốc thuần một bên.",
                  {"clip": 7041, "nen_nhac_co_nhip": 7042}, v, kho, [dn], "da",
                  "Mép mờ ±1 s quanh tâm dốc (mep_mo); phần giữa là bản sao nguyên mẫu. Ở dốc công suất không đổi clip đạt "
                  "nửa biên độ ở 1/3 dốc (0,33 s trước tâm) — mép báo trong ±1 s quanh tâm đều đúng.",
                  mep_mo=({"t": dn["video_tu"], "nua_rong": 1.0}, {"t": dn["video_den"], "nua_rong": 1.0}),
                  kieu_chuyen_mo="cong_suat_khong_doi", doan_ban_sao_nguyen_mau=[0])


def ca_b05(d: str) -> dict:
    clip = dc._giai(360, 7051)
    kho = [dc._kho(d, "goc_B05.wav", clip)]
    _giua_not(30.3, 176.9, 333.7)
    j0, x, j1, i0, g = _i(30.3), _i(176.9), _i(333.7), _i(211.11), _i(4.0)
    video = dc._giai(900, 7052)
    video[i0:i0 + (x - j0)] = clip[j0:x]
    a = i0 + (x - j0)
    nen_phong = _on_hong(g, 7053, 100.0, 5000.0)
    nen_phong *= dc._rms(clip[j0:j1]) / dc._rms(nen_phong) * 10 ** (-50 / 20)
    video[a:a + g] = nen_phong                            # «tạm dừng»: 4 s gần im (tiếng phòng −50 dB), trục clip ĐỨNG
    video[a + g:a + g + (j1 - x)] = clip[x:j1]
    v = dc._video(d, video)
    return dc._st("B05_tam_dung_4s_gan_im", "tam_dung_4s_gan_im_trong_doan",
                  "Clip nốt ngẫu nhiên 360 s, dùng clip[30,3..333,7] từ 211,11 s của video 900 s; ở giây clip 176,9 video TẠM "
                  "DỪNG 4 s (gần im: ồn hồng 100–5000 Hz thấp hơn tiếng clip 50 dB — không phải mẫu 0) rồi phát TIẾP từ đúng "
                  "giây clip 176,9 (khác vòng 1: ở đó trục clip vẫn chạy trong lúc lặng). Mép khoảng lặng giữa nốt.",
                  {"clip": 7051, "nen": 7052, "tieng_phong": 7053}, v, kho,
                  [_doan("goc_B05.wav", i0, j0, x), _doan("goc_B05.wav", a + g, x, j1)], "da",
                  "Hai đoạn, căn chỉnh lệch nhau 4 s (giây clip ở hai bên khe là MỘT): gộp qua khe là báo thừa 4 s và ánh xạ "
                  "đoạn sau lệch 4 s.",
                  vung_gan_im_lang=[[round(a / SR, 6), round((a + g) / SR, 6)]], muc_gan_im_lang_db=-50.0,
                  doan_ban_sao_nguyen_mau=[0, 1])


def ca_b06(d: str) -> dict:
    clip = _nhac(380.0, 7061, 120.0)
    kho = [dc._kho(d, "goc_B06.wav", clip)]
    j0, x, j1, i0, cat = _i(52.25), _i(201.75), _i(351.5), _i(333.0), _i(3.0)
    video = dc._chen(dc._giai(1000, 7062), np.concatenate([clip[j0:x], clip[x + cat:j1]]), i0)
    v = dc._video(d, video)
    return dc._st("B06_cat_3s_nhip120_dung_phach", "cat_nho_3s_nhip_dung_phach",
                  "Clip nhạc có nhịp 120 BPM (ô nhịp 2,0 s) dài 380 s; video 1000 s phát clip[52,25..201,75] từ 333,0 s rồi NỐI "
                  "THẲNG clip[204,75..351,5] (bỏ 3 s, không chèn gì). 3 s = 6 phách: lưới kick/snare liền mạch qua chỗ cắt "
                  "(cắt «đúng phách» như người dựng nhạc), cả hai mép trong cùng đoạn 8 ô nhịp 192–208 s nên mẫu trống trước và "
                  "sau chỗ cắt là MỘT; chỉ hi-hat, hợp âm (lệch nửa ô nhịp) và giai điệu khác.",
                  {"clip_nhac_co_nhip_120bpm": 7061, "nen": 7062}, v, kho,
                  [_doan("goc_B06.wav", i0, j0, x), _doan("goc_B06.wav", i0 + (x - j0), x + cat, j1)], "da",
                  "Hai đoạn nối nhau trên video, nhảy 3 s trên trục clip ở video 482,5 s; căn chỉnh cũ sau chỗ cắt chỉ giống MỘT "
                  "PHẦN (trống) — báo kéo dài căn chỉnh cũ là sai ánh xạ 3 s.", doan_ban_sao_nguyen_mau=[0, 1])


def ca_b07(d: str) -> dict:
    clip = _nhac(320.0, 7071)
    kho = [dc._kho(d, "goc_B07.wav", clip)]
    j0, x, j1, i0, lui, g = _i(18.4), _i(72.9), _i(301.2), _i(280.6), _i(10.0), _i(0.3)
    chen = np.concatenate([clip[j0:x], np.zeros(g), clip[x - lui:j1]])
    video = dc._chen(dc._giai(1000, 7072), chen, i0)
    v = dc._video(d, video)
    return dc._st("B07_tua_lui_10s_khe_0_3s", "tua_lui_10s_khe_0_3s_nhip",
                  "Clip nhạc có nhịp 113 BPM 320 s (kho WAV); video 1000 s phát clip[18,4..72,9] từ 280,6 s, IM 0,3 s (mẫu 0, "
                  "như lúc tua trình phát) rồi phát lại từ clip[62,9] tới 301,2 (tua lùi 10 s, 4,7 ô nhịp — không trùng lưới "
                  "trống). Phần đầu NGẮN (54,5 s), phần phát lại DÀI (238,3 s) — ngược tỉ lệ các ca tua lùi trước.",
                  {"clip_nhac_co_nhip": 7071, "nen": 7072}, v, kho,
                  [_doan("goc_B07.wav", i0, j0, x), _doan("goc_B07.wav", i0 + (x - j0) + g, x - lui, j1)], "da",
                  "Hai căn chỉnh lệch 10,3 s trong cùng một lần dùng; đoạn ngắn đầu cũng phải được báo (không chỉ phần phát "
                  "lại mạnh hơn).", vung_im_lang=[[round((i0 + x - j0) / SR, 6), round((i0 + x - j0 + g) / SR, 6)]],
                  doan_ban_sao_nguyen_mau=[0, 1])


def _ca_40p(d: str, ma: str, kho_dai: bool) -> dict:
    if kho_dai:
        ten, seeds, not_chan, seed_nen, P, dai_v = "goc_B08a.opus", list(range(7081, 7091)), True, 7099, 355.55, 900
    else:
        ten, seeds, not_chan, seed_nen, P, dai_v = "goc_B08b.opus", list(range(7101, 7111)), False, 7119, 487.7, 1000
    kho = [_clip40_opus(d, ten, seeds, not_chan, kho_dai)]
    i0 = _i(P)
    v = dc._video(d, dc._chen(dc._giai(dai_v, seed_nen), _trich_40p(seeds, not_chan), i0))
    dn = _doan(ten, i0, _i(1500.0), _i(1800.0))
    noi_dung = ("1500–1680 s nốt ngẫu nhiên rồi 1680–1800 s nhạc có nhịp" if not_chan
                else "1500–1680 s nhạc có nhịp rồi 1680–1800 s nốt ngẫu nhiên")
    seed = {"clip_10_khuc_240s": seeds, "khuc_chan": "giai_dieu" if not_chan else "nhac_co_nhip", "nen": seed_nen}
    if kho_dai:
        return dc._st(f"{ma}_clip40p_kho_dai_xen_ke", "clip_dai_40p_dung_25_30_kho_video_dai_xen_ke",
                      f"Clip 40 phút = 10 khúc 240 s XEN KẼ nốt ngẫu nhiên (khúc chẵn) và nhạc có nhịp 113 BPM (khúc lẻ), kho "
                      f".opus 64 kbps có dấu «.kho_video_dai» (D-34, mốc 21 bit, không cuộn); chỉ dùng 25:00–30:00 "
                      f"(clip[1500..1800]: {noi_dung} — đổi kiểu nội dung GIỮA đoạn) ở {P:g} s của video {dai_v} s nền nốt "
                      f"ngẫu nhiên. Engine đặt start_s = vung_khop_s (kho video dài); neo = {P:g} − 1500 (ÂM, chưa kẹp).",
                      seed, v, kho, [dn], "da",
                      "Neo đúng; clip dài phải đọc theo cửa sổ quanh 25:00–30:00 (tua vào giữa file opus 40 phút); nội dung đổi "
                      "kiểu ở 28:00 không phải chỗ cắt.", doan_ban_sao_nguyen_mau=[])
    return dc._st(f"{ma}_clip40p_kho_thuong_opus", "clip_dai_40p_dung_25_30_kho_thuong_opus",
                  f"Clip 40 phút = 10 khúc 240 s XEN KẼ nhạc có nhịp (khúc chẵn) và nốt ngẫu nhiên (khúc lẻ), kho THƯỜNG .opus "
                  f"64 kbps (mốc 16 bit, cuộn sau 65536 khung ≈ 1521,7 s = 25:21,7); chỉ dùng 25:00–30:00 (clip[1500..1800]: "
                  f"{noi_dung}) ở {P:g} s của video {dai_v} s. Phần clip sau 25:21,7 mang giây clip cuộn về 0 → engine báo căn "
                  "chỉnh lệch ~1521,7 s (giới hạn đã biết, FINGERPRINT_RECOVERY_ARCHITECTURE.md §6.1).",
                  seed, v, kho, [dn], "chua_hoac_da",
                  "Neo engine sai do mốc cuộn; tinh chỉnh không cứu được → CHƯA là đúng; nếu ĐÃ thì phải đúng giây clip "
                  "1500–1800 (không phải giây clip cuộn) và đủ cả 300 s.", doan_ban_sao_nguyen_mau=[])


def ca_b08a(d: str) -> dict:
    return _ca_40p(d, "B08a", True)


def ca_b08b(d: str) -> dict:
    return _ca_40p(d, "B08b", False)


def ca_b09(d: str) -> dict:
    clip = _nhac(390.0, 7111)
    kho = [dc._kho(d, "goc_B09.wav", clip)]
    j0, j1, i0 = _i(37.9), _i(351.2), _i(226.4)
    video = dc._chen(dc._giai(900, 7112), clip[j0:j1], i0)
    on = _on_hong(len(video), 7113)
    on *= dc._rms(clip[j0:j1]) / dc._rms(on) * 10 ** (-10 / 20)
    vung = slice(i0, i0 + (j1 - j0))
    snr_dai = _db_dai(clip[j0:j1], on[vung], 300.0, 5000.0)
    video, s = dc._chuan_hoa(video + on)
    v = dc._video(d, video)
    return dc._st("B09_on_hong_10db", "on_hong_snr_10db_ca_video_nhip",
                  "Clip nhạc có nhịp 113 BPM 390 s, dùng clip[37,9..351,2] ở 226,4 s của video 900 s nền nốt ngẫu nhiên; ỒN "
                  "HỒNG (1/f, 80–5500 Hz — khác ồn trắng của vòng 1) phủ TOÀN video, SNR 10 dB toàn dải so với tiếng clip.",
                  {"clip_nhac_co_nhip": 7111, "nen": 7112, "on_hong": 7113}, v, kho,
                  [_doan("goc_B09.wav", i0, j0, j1)], "da",
                  "SNR 10 dB toàn dải (ồn hồng dồn năng lượng xuống dải thấp: trong 300–5000 Hz SNR cao hơn, xem "
                  "snr_300_5000_db); mép cắt cứng.",
                  snr_db=round(20 * np.log10(dc._rms(clip[j0:j1]) / dc._rms(on)), 3), snr_300_5000_db=snr_dai,
                  he_so_chuan_hoa=round(s, 6), doan_ban_sao_nguyen_mau=[])


def ca_b10(d: str) -> dict:
    clip = _nhac(420.0, 7121, 104.0)
    kho = [dc._kho(d, "goc_B10.wav", clip)]
    j0, j1, i0 = _i(66.6), _i(377.3), _i(288.8)
    cham = dc._doi_toc(clip[j0:j1], 0.97, d)
    v = dc._video(d, dc._chen(dc._giai(1000, 7122), cham, i0))
    return dc._st("B10_cham_097_nhip104", "toc_do_097_mot_phan_nhip",
                  "Clip nhạc có nhịp 104 BPM 420 s, đoạn clip[66,6..377,3] phát CHẬM 0,97 lần (FFmpeg atempo=0,97, giữ cao độ) "
                  "chèn cắt cứng ở 288,8 s của video 1000 s nền nốt ngẫu nhiên (video_den = 288,8 + 310,7/0,97).",
                  {"clip_nhac_co_nhip_104bpm": 7121, "nen": 7122}, v, kho,
                  [_doan("goc_B10.wav", i0, j0, j1, 0.97)], "da",
                  "Một đoạn, he_so 0,97 (video chậm hơn); phải bám độ trôi 3 % trên nhạc có nhịp.",
                  do_dai_chen_thuc_te_s=round(len(cham) / SR, 6), ly_thuyet_s=round((j1 - j0) / SR / 0.97, 6),
                  doan_ban_sao_nguyen_mau=[])


def ca_b11(d: str) -> dict:
    clip = dc._giai(330, 7131)
    kho = [dc._kho(d, "goc_B11.opus", clip, opus=True)]
    _giua_not(12.3, 248.5, 150.1, 318.7)
    (a0, a1, p1), (b0, b1, p2) = (_i(12.3), _i(248.5), _i(180.4)), (_i(150.1), _i(318.7), _i(1240.6))
    nho = 10 ** (-8 / 20)
    video = dc._chen(dc._chen(dc._giai(1500, 7132), clip[a0:a1], p1), nho * clip[b0:b1], p2)
    v = dc._video(d, video)
    return dc._st("B11_hai_lan_xa_nguoc_nho", "mot_clip_hai_lan_xa_nguoc_thu_tu_lan_sau_nho",
                  "Clip nốt ngẫu nhiên 330 s (kho .opus) dùng HAI lần cách xa trong video 1500 s: clip[12,3..248,5] ở 180,4 s, "
                  "rồi clip[150,1..318,7] ở 1240,6 s NHỎ HƠN 8 dB (thay nền, cắt cứng). Giây clip 150,1–248,5 có trong cả hai "
                  "lần; lần sau dùng phần SAU của clip (khác vòng 1).", {"clip": 7131, "nen": 7132}, v, kho,
                  [_doan("goc_B11.opus", p1, a0, a1), _doan("goc_B11.opus", p2, b0, b1)], "da",
                  "Mỗi dòng engine (một lần dùng) phải ra đúng đoạn của nó, không lấn sang lần kia; âm lượng −8 dB không đổi "
                  "mép.", he_so_bien_do_lan_2=round(nho, 6), doan_ban_sao_nguyen_mau=[])


def ca_b12(d: str) -> dict:
    clip = _nhac(255.0, 7141)
    kho = [dc._kho(d, "goc_B12.opus", clip, opus=True)]
    j0, j1, i0 = _i(0.4), len(clip) - _i(0.7), _i(412.34)
    v = dc._video(d, dc._chen(dc._giai(900, 7142), clip[j0:j1], i0))
    return dc._st("B12_cat_mep_04_07_nhip_opus", "cat_mep_dau_0_4_cuoi_0_7_nhip_opus",
                  "Clip nhạc có nhịp 113 BPM 255 s (kho .opus 64 kbps), video 900 s dùng clip[0,4..254,3] — bỏ 0,4 s ĐẦU (ngay "
                  "sau tiếng kick đầu tiên của ô nhịp 1) và 0,7 s CUỐI — ở 412,34 s, cắt cứng, nền nốt ngẫu nhiên.",
                  {"clip_nhac_co_nhip": 7141, "nen": 7142}, v, kho, [_doan("goc_B12.opus", i0, j0, j1)], "da",
                  "Mép đo được phải là giây clip 0,4 và 254,3 — chốt về đầu/cuối clip (0 / 255) là sai 0,4 / 0,7 s.",
                  doan_ban_sao_nguyen_mau=[])


def ca_b13(d: str) -> dict:
    o = 240.0 / 113.0
    a, b = _nhac(280.0, 7151), _nhac(300.0, 7152)
    kho = [dc._kho(d, "goc_B13_a.wav", a), dc._kho(d, "goc_B13_b.wav", b)]
    ja0, ja1, jb0, jb1, i0 = _i(41.37), _i(64 * o), _i(8 * o), _i(231.7), _i(300.0)
    video = dc._chen(dc._giai(1000, 7153), np.concatenate([a[ja0:ja1], b[jb0:jb1]]), i0)
    v = dc._video(d, video)
    return dc._st("B13_hai_clip_noi_dj", "hai_clip_khac_noi_tiep_cung_nhip_dj",
                  "Hai clip nhạc có nhịp KHÁC nhau cùng 113 BPM (cùng mẫu kick tất định) phát nối tiếp không khe trong video "
                  "1000 s, nối ĐÚNG PHÁCH kiểu DJ: clip A a[41,37..135,93] (kết thúc đúng đầu ô nhịp 65) từ 300 s, rồi clip B "
                  "b[16,99..231,7] (bắt đầu đúng đầu ô nhịp 9) từ 394,56 s — lưới kick/snare liền mạch qua chỗ nối, chỉ hi-hat, "
                  "hợp âm, giai điệu đổi.", {"clip_a_nhac_co_nhip": 7151, "clip_b_nhac_co_nhip": 7152, "nen": 7153}, v, kho,
                  [_doan("goc_B13_a.wav", i0, ja0, ja1), _doan("goc_B13_b.wav", i0 + (ja1 - ja0), jb0, jb1)], "da",
                  "Mỗi clip một dòng; đoạn của dòng này phải dừng đúng chỗ nối, không lấn sang clip kia dù trống vẫn khớp nhịp.",
                  doan_ban_sao_nguyen_mau=[0, 1])


def ca_b14(d: str) -> dict:
    clip = dc._giai(450, 7161)
    kho = [dc._kho(d, "goc_B14.wav", clip)]
    _giua_not(58.5, 397.3)
    j0, j1, i0 = _i(58.5), _i(397.3), _i(241.7)
    nhanh = dc._doi_toc(clip[j0:j1], 1.03, d)
    v = dc._video(d, dc._chen(dc._giai(900, 7162), nhanh, i0), ("-ac", "2", "-c:a", "libopus", "-b:a", "48k"), ".ogg",
                  "Ogg/Opus 48 kbps STEREO (hai kênh như nhau; giải mã bằng FFmpeg)")
    return dc._st("B14_nhanh_103_opus48_ogg", "toc_do_103_mot_phan_opus48_ogg_stereo",
                  "Clip nốt ngẫu nhiên 450 s, đoạn clip[58,5..397,3] phát NHANH 1,03 lần (atempo=1,03) chèn ở 241,7 s của video "
                  "900 s, rồi CẢ video nén Opus 48 kbps STEREO trong Ogg (vòng 1: mono trong WebM).",
                  {"clip": 7161, "nen": 7162}, v, kho, [_doan("goc_B14.wav", i0, j0, j1, 1.03)], "da",
                  "Một đoạn he_so 1,03 qua nén Opus 48 kbps; mép cắt cứng.",
                  do_dai_chen_thuc_te_s=round(len(nhanh) / SR, 6), ly_thuyet_s=round((j1 - j0) / SR / 1.03, 6),
                  doan_ban_sao_nguyen_mau=[])


def ca_b15(d: str) -> dict:
    clip = dc._giai(300, 7171)
    kho = [dc._kho(d, "goc_B15.wav", clip)]
    _giua_not(20.1, 280.3)
    j0, j1, i0 = _i(20.1), _i(280.3), _i(310.5)
    video = dc._chen(dc._giai(900, 7172), clip[j0:j1], i0)
    g = _giong_noi_2(len(video), 7173)
    vung = slice(i0, i0 + (j1 - j0))
    g *= dc._rms(clip[j0:j1]) / dc._rms(g[vung])          # 0 dB so với tiếng clip, đo trong vùng clip
    video, s = dc._chuan_hoa(video + g)
    v = dc._video(d, video)
    return dc._st("B15_giong_noi_de_toan_bo", "giong_noi_0db_de_toan_bo_video",
                  "(Thêm) Clip nốt ngẫu nhiên 300 s, dùng clip[20,1..280,3] ở 310,5 s của video 900 s; âm giống giọng nói (như "
                  "B03) nói SUỐT video — bình luận liên tục kiểu video reaction — 0 dB so với tiếng clip trong vùng clip.",
                  {"clip": 7171, "nen": 7172, "giong_noi": 7173}, v, kho, [_doan("goc_B15.wav", i0, j0, j1)],
                  "chua_hoac_da",
                  "Clip có mặt suốt dưới giọng 0 dB: tương phản thấp nên CHƯA chấp nhận được; nếu ĐÃ thì phải MỘT đoạn đúng, "
                  "không bịa chỗ cắt ở các quãng giọng to.",
                  snr_db=round(20 * np.log10(dc._rms(clip[j0:j1]) / dc._rms(g[vung])), 3), he_so_chuan_hoa=round(s, 6),
                  doan_ban_sao_nguyen_mau=[])


def ca_b16(d: str) -> dict:
    clip = _nhac(400.0, 7181, 88.0)
    kho = [dc._kho(d, "goc_B16.wav", clip)]
    j0, j1, i0 = _i(47.2), _i(352.9), _i(273.3)
    nhanh = dc._doi_toc(clip[j0:j1], 1.02, d)
    v = dc._video(d, dc._chen(dc._giai(900, 7182), nhanh, i0), ("-ac", "1", "-c:a", "aac", "-b:a", "96k"), ".m4a",
                  "M4A/AAC 96 kbps mono 22,05 kHz (giải mã bằng FFmpeg)")
    return dc._st("B16_nhanh_102_nhip88_m4a", "toc_do_102_mot_phan_nhip_aac",
                  "(Thêm — nhánh he_so ≠ 1 mà engine thấy được) clip nhạc có nhịp 88 BPM 400 s, đoạn clip[47,2..352,9] phát "
                  "NHANH 1,02 lần (atempo=1,02, giữ cao độ) chèn ở 273,3 s của video 900 s, rồi CẢ video nén AAC 96 kbps mono "
                  "trong M4A.", {"clip_nhac_co_nhip_88bpm": 7181, "nen": 7182}, v, kho,
                  [_doan("goc_B16.wav", i0, j0, j1, 1.02)], "da",
                  "Một đoạn he_so 1,02 (video nhanh hơn) qua AAC; mép cắt cứng.",
                  do_dai_chen_thuc_te_s=round(len(nhanh) / SR, 6), ly_thuyet_s=round((j1 - j0) / SR / 1.02, 6),
                  doan_ban_sao_nguyen_mau=[])


def ca_b17(d: str) -> dict:
    clip = dc._giai(420, 7191)
    kho = [dc._kho(d, "goc_B17.opus", clip, opus=True)]
    _giua_not(33.7, 401.3)
    j0, j1, i0 = _i(33.7), _i(401.3), _i(300.3)
    cham = dc._doi_toc(clip[j0:j1], 0.98, d)
    v = dc._video(d, dc._chen(dc._giai(1100, 7192), cham, i0))
    return dc._st("B17_cham_098_kho_opus", "toc_do_098_mot_phan_kho_opus",
                  "(Thêm — nhánh he_so ≠ 1 mà engine thấy được) clip nốt ngẫu nhiên 420 s (kho .opus 64 kbps), đoạn "
                  "clip[33,7..401,3] phát CHẬM 0,98 lần (atempo=0,98) chèn cắt cứng ở 300,3 s của video 1100 s.",
                  {"clip": 7191, "nen": 7192}, v, kho, [_doan("goc_B17.opus", i0, j0, j1, 0.98)], "da",
                  "Một đoạn he_so 0,98 dài 375 s trên video (độ trôi tích luỹ 7,5 s); clip đọc từ opus.",
                  do_dai_chen_thuc_te_s=round(len(cham) / SR, 6), ly_thuyet_s=round((j1 - j0) / SR / 0.98, 6),
                  doan_ban_sao_nguyen_mau=[])


def ca_b18(d: str) -> dict:
    # Thêm sau lượt engine: B06 (cắt đúng phách) bị engine bật moc_mo_ho → nơi gọi không tinh chỉnh; biến thể cắt LỆCH
    # phách để kiểu «cắt nhỏ 3 s» có ca ẩn đi qua đường sản phẩm.
    clip = _nhac(360.0, 7201)
    kho = [dc._kho(d, "goc_B18.wav", clip)]
    j0, x, j1, i0, cat = _i(31.17), _i(141.9), _i(328.4), _i(355.5), _i(3.0)
    video = dc._chen(dc._giai(1000, 7202), np.concatenate([clip[j0:x], clip[x + cat:j1]]), i0)
    v = dc._video(d, video)
    return dc._st("B18_cat_3s_nhip113_lech_phach", "cat_nho_3s_nhip_lech_phach",
                  "(Thêm — biến thể B06 mà engine không bật moc_mo_ho) clip nhạc có nhịp 113 BPM 360 s; video 1000 s phát "
                  "clip[31,17..141,9] từ 355,5 s rồi NỐI THẲNG clip[144,9..328,4] (bỏ 3 s, không chèn gì). 3 s = 5,65 phách: "
                  "lưới trống sau chỗ cắt LỆCH 0,35 phách so với căn chỉnh cũ.", {"clip_nhac_co_nhip": 7201, "nen": 7202},
                  v, kho, [_doan("goc_B18.wav", i0, j0, x), _doan("goc_B18.wav", i0 + (x - j0), x + cat, j1)], "da",
                  "Hai đoạn nối nhau trên video (110,73 s + 183,5 s), nhảy 3 s trên trục clip ở video 466,23 s.",
                  doan_ban_sao_nguyen_mau=[0, 1])


def ca_b19(d: str) -> dict:
    # Thêm sau lượt engine: B09 (ồn hồng trên nhạc có nhịp) bị engine bật moc_mo_ho → biến thể clip nốt ngẫu nhiên.
    clip = dc._giai(380, 7211)
    kho = [dc._kho(d, "goc_B19.wav", clip)]
    _giua_not(55.3, 349.9)
    j0, j1, i0 = _i(55.3), _i(349.9), _i(300.7)
    video = dc._chen(dc._giai(1000, 7212), clip[j0:j1], i0)
    on = _on_hong(len(video), 7213)
    on *= dc._rms(clip[j0:j1]) / dc._rms(on) * 10 ** (-10 / 20)
    vung = slice(i0, i0 + (j1 - j0))
    snr_dai = _db_dai(clip[j0:j1], on[vung], 300.0, 5000.0)
    video, s = dc._chuan_hoa(video + on)
    v = dc._video(d, video)
    return dc._st("B19_on_hong_10db_giai_dieu", "on_hong_snr_10db_ca_video_giai_dieu",
                  "(Thêm — biến thể B09 mà engine không bật moc_mo_ho) clip nốt ngẫu nhiên 380 s (kho WAV), dùng "
                  "clip[55,3..349,9] ở 300,7 s của video 1000 s; ỒN HỒNG 80–5500 Hz phủ TOÀN video, SNR 10 dB toàn dải.",
                  {"clip": 7211, "nen": 7212, "on_hong": 7213}, v, kho, [_doan("goc_B19.wav", i0, j0, j1)], "da",
                  "SNR 10 dB toàn dải (trong 300–5000 Hz xem snr_300_5000_db); mép cắt cứng giữa nốt.",
                  snr_db=round(20 * np.log10(dc._rms(clip[j0:j1]) / dc._rms(on)), 3), snr_300_5000_db=snr_dai,
                  he_so_chuan_hoa=round(s, 6), doan_ban_sao_nguyen_mau=[])


CA = {"B01": ca_b01, "B02": ca_b02, "B03": ca_b03, "B04": ca_b04, "B05": ca_b05, "B06": ca_b06, "B07": ca_b07,
      "B08a": ca_b08a, "B08b": ca_b08b, "B09": ca_b09, "B10": ca_b10, "B11": ca_b11, "B12": ca_b12, "B13": ca_b13,
      "B14": ca_b14, "B15": ca_b15, "B16": ca_b16, "B17": ca_b17, "B18": ca_b18, "B19": ca_b19}


def dung(ma: str) -> dict:
    """Dựng một ca vào thư mục tạm rồi đổi tên thành ``<RA>/<ten>`` (xoá bản cũ cùng mã), rồi đo lại sự thật."""
    for cu in [x for x in os.listdir(RA) if x.split("_")[0] == ma]:
        shutil.rmtree(os.path.join(RA, cu))
    tam = os.path.join(RA, f"_dang_dung_{ma}")
    if os.path.isdir(tam):
        shutil.rmtree(tam)
    os.makedirs(tam)
    t0 = time.perf_counter()
    st = CA[ma](tam)
    seeds = [s for v in st["seed"].values() if not isinstance(v, str) for s in (v if isinstance(v, list) else [v])]
    assert min(seeds) >= SEED_TOI_THIEU, f"seed < {SEED_TOI_THIEU}: {st['seed']}"
    assert not [x for x in os.listdir(tam) if x.startswith("_tam")], "còn file tạm"
    st["vong"] = 2
    st["thoi_gian_dung_s"] = round(time.perf_counter() - t0, 1)
    with open(os.path.join(tam, "su_that.json"), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    d = os.path.join(RA, st["ten"])
    os.rename(tam, d)
    return kiem_su_that_2.ghi_vao_su_that(d)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ds = sys.argv[1:] or list(CA)
    sai = [x for x in ds if x not in CA]
    if sai:
        raise SystemExit(f"Không có ca {sai}; có: {' '.join(CA)}")
    os.makedirs(RA, exist_ok=True)
    loi = 0
    for ma in ds:
        t0 = time.perf_counter()
        kq = dung(ma)
        loi += kq["ket_luan"] != "khop"
        tom = [(r["anh_xa"].get("lech_trung_vi_ms"), r["anh_xa"].get("ncc_trung_vi"), r.get("lech_mep_s"),
                r.get("bien_do_G")) for r in kq["doan"]]
        print(f"[{ma}] {time.perf_counter() - t0:.0f} s — sự thật đo từ audio: {kq['ket_luan']} {tom} "
              f"đỉnh lạ max {[x['ncc_dinh_la_lon_nhat'] for x in kq['do_toan_video'].values()]} "
              f"miễn {len(kq['mien_tru_co_bang_chung'])} | còn: {kq['ly_do_xem_lai']}", flush=True)
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
