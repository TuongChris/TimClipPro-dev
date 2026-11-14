# -*- coding: utf-8 -*-
"""Bộ CA ẨN (held-out) cho tinh_chinh_moc.py (P-8 «tinh chỉnh mốc từng giây») — dựng audio + sự thật (14/11/2026).

Độc lập với bộ trong mẫu mà module được chỉnh theo (S0–S9, S4b, S5b, S6b, S7b, S7c, X1–X3, H1a–H4): seed ≥ 5000, kiểu
mới. Người dựng KHÔNG đọc tinh_chinh_moc.py hay test của nó. Audio 100 % giả lập từ bộ sinh của repo
(tests/conftest.py ``_giai_dieu``/``_ghi_wav``, tests/am_thanh_lap.py ``nhac_co_nhip``) + FFmpeg; không dữ liệu thật,
không mạng.

Mỗi ca một thư mục ``<RA>/<ten>/``: ``kho/`` (clip gốc), video vi phạm, ``su_that.json``:
  ten, loai, mo_ta, seed, ky_vong («da» = phải tinh chỉnh và ĐÚNG; «chua_hoac_da» = CHƯA cũng được, ĐÃ thì phải đúng),
  doan [{clip, video_tu, video_den, clip_tu, clip_den, he_so}] — đoạn dùng THẬT của TỪNG clip (he_so = tốc độ video so
  với clip: video_den − video_tu = (clip_den − clip_tu)/he_so); mep_mo [{t, nua_rong}] — mép mờ thật (tâm chuyển mờ ±
  nửa bề rộng); kiem_su_that — đo lại từ audio bằng kiem_su_that.py (mẫu trùng khớp + tương quan dạng sóng).
Mốc sự thật tính từ CHỈ SỐ MẪU lúc dựng (``_doan``), không lấy số danh nghĩa.

Chạy (Git Bash, từ thư mục này; không đối số = dựng mọi ca):
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \
      -B -X utf8 dung_ca.py [A01 A02 ...]
Rồi ``chay_engine.py`` (engine THẬT, từng ca một).
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
import wave

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import numpy as np  # noqa: E402

MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "TimClipPro"))  # checkout chứa file này
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\ca_an"
sys.path.insert(0, os.path.join(MA, "tests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import am_thanh_lap  # noqa: E402
import kiem_su_that  # noqa: E402
from am_thanh_lap import SR, nhac_co_nhip  # noqa: E402
from conftest import _ghi_wav, _giai_dieu  # noqa: E402

TEN_VIDEO = "video_vi_pham"
OPUS_KHO = ("-vn", "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "64k")   # = channel.py (kho thật)
DD_WAV = "WAV s16 22050 Hz mono"
QUY_UOC_HE_SO = ("he_so = tốc độ video so với clip: video_den − video_tu = (clip_den − clip_tu)/he_so; giây 0 clip ở "
                 "video_tu − clip_tu/he_so. NGƯỢC với Match.he_so của engine (giây video / giây clip = 1/he_so): "
                 "video chậm 0,98 → engine he_so ≈ 1,0204.")
DD_OPUS = "Opus 64 kbps mono 16 kHz (.opus) — đúng định dạng kho thật của channel.py"


# ---------------------------------------------------------------- tiện ích
def _i(giay: float) -> int:
    return int(round(giay * SR))


def _ffmpeg(*ts: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *ts], check=True)


def _doc_wav(path: str) -> np.ndarray:
    """WAV s16 do _ghi_wav/FFmpeg ghi → float cùng thang 32000 của _ghi_wav."""
    with wave.open(path, "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, SR), path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32000.0


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def _giai(dai_s: float, seed: int) -> np.ndarray:
    return _giai_dieu(dai_s, seed=seed, sr=SR)


@contextlib.contextmanager
def _nhip(bpm: float):
    """nhac_co_nhip ở nhịp ``bpm``: hàm đọc ô nhịp ``am_thanh_lap.O_NHIP`` lúc chạy → đổi tạm trong tiến trình này."""
    cu = am_thanh_lap.O_NHIP
    am_thanh_lap.O_NHIP = 240.0 / bpm
    try:
        yield
    finally:
        am_thanh_lap.O_NHIP = cu


def _chu_ky_phach(sig: np.ndarray) -> float:
    """Chu kỳ phách đo từ tự tương quan đường bao năng lượng (khung 10 ms), tìm trong 0,3–0,8 s."""
    k = SR // 100
    bao = np.sqrt(np.mean(np.square(sig[:len(sig) // k * k].reshape(-1, k)), axis=1))
    bao = np.diff(bao, prepend=bao[0]).clip(0)            # chỉ sườn lên (tiếng đánh)
    bao -= bao.mean()
    r = np.correlate(bao, bao, "full")[len(bao) - 1:]
    return (30 + int(np.argmax(r[30:81]))) / 100.0


def _chen(nen: np.ndarray, doan: np.ndarray, i0: int) -> np.ndarray:
    """THAY nền bằng đoạn chèn từ mẫu ``i0`` (cắt cứng)."""
    assert 0 <= i0 and i0 + len(doan) <= len(nen), "đoạn chèn vượt quá video"
    nen = nen.copy()
    nen[i0:i0 + len(doan)] = doan
    return nen


def _doan(clip: str, i0: int, j0: int, j1: int, he_so: float = 1.0) -> dict:
    """Đoạn sự thật từ CHỈ SỐ MẪU: clip[j0:j1] bắt đầu ở mẫu i0 của video."""
    vt, ct, cd = i0 / SR, j0 / SR, j1 / SR
    return {"clip": clip, "video_tu": round(vt, 6), "video_den": round(vt + (cd - ct) / he_so, 6),
            "clip_tu": round(ct, 6), "clip_den": round(cd, 6), "he_so": he_so}


def _doi_toc(sig: np.ndarray, k: float, d: str) -> np.ndarray:
    """Đổi tốc độ GIỮ cao độ bằng FFmpeg atempo (k > 1 = nhanh hơn)."""
    vao, ra = os.path.join(d, "_tam_vao.wav"), os.path.join(d, "_tam_ra.wav")
    _ghi_wav(vao, sig, SR)
    _ffmpeg("-i", vao, "-filter:a", f"atempo={k}", "-ar", str(SR), "-ac", "1", ra)
    out = _doc_wav(ra)
    os.remove(vao)
    os.remove(ra)
    return out


def _giong_noi(n: int, seed: int) -> np.ndarray:
    """Âm «giống giọng nói»: ồn dải 300–3400 Hz, biên độ điều chế theo âm tiết 3–5 Hz, thỉnh thoảng ngắt hơi."""
    rng = np.random.default_rng(seed)
    F = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    F[(f < 300.0) | (f > 3400.0)] = 0.0
    on = np.fft.irfft(F, n)
    bao = np.zeros(n)
    t = 0.0
    while t < n / SR:
        if rng.random() < 0.1:
            t += rng.uniform(0.25, 0.6)                   # ngắt hơi giữa câu
        dai = 1.0 / rng.uniform(3.0, 5.0)                 # một âm tiết
        a, b = _i(t), min(n, _i(t + dai))
        if b > a:
            bao[a:b] = np.hanning(b - a) * rng.uniform(0.4, 1.0)
        t += dai
    return on * bao


def _on_trang(n: int, seed: int, tran_hz: float = 5500.0) -> np.ndarray:
    """Ồn trắng cắt trên ``tran_hz`` (audfprint và bước tinh chỉnh chỉ nhìn tới ~5,5 kHz): SNR khai = SNR chúng thấy."""
    rng = np.random.default_rng(seed)
    F = np.fft.rfft(rng.standard_normal(n))
    F[np.fft.rfftfreq(n, 1.0 / SR) > tran_hz] = 0.0
    return np.fft.irfft(F, n)


def _kho(d: str, ten: str, sig: np.ndarray, opus: bool = False) -> dict:
    kho = os.path.join(d, "kho")
    os.makedirs(kho, exist_ok=True)
    if not opus:
        _ghi_wav(os.path.join(kho, ten), sig, SR)
        return {"clip": ten, "do_dai_nguon_s": round(len(sig) / SR, 6), "dinh_dang": DD_WAV}
    tam = os.path.join(d, "_tam_clip.wav")
    _ghi_wav(tam, sig, SR)
    _ffmpeg("-i", tam, *OPUS_KHO, os.path.join(kho, ten))
    os.remove(tam)
    return {"clip": ten, "do_dai_nguon_s": round(len(sig) / SR, 6), "dinh_dang": DD_OPUS}


def _video(d: str, sig: np.ndarray, ma_hoa: tuple = (), duoi: str = ".wav", dinh_dang: str = DD_WAV) -> dict:
    ten = TEN_VIDEO + duoi
    if not ma_hoa:
        _ghi_wav(os.path.join(d, ten), sig, SR)
    else:
        tam = os.path.join(d, "_tam_video.wav")
        _ghi_wav(tam, sig, SR)
        _ffmpeg("-i", tam, *ma_hoa, os.path.join(d, ten))
        os.remove(tam)
    return {"video": ten, "do_dai_video_nguon_s": round(len(sig) / SR, 6), "dinh_dang_video": dinh_dang}


def _st(ten: str, loai: str, mo_ta: str, seed: dict, video: dict, kho: list, doan: list, ky_vong: str, ly_do: str,
        mep_mo: tuple = (), **them) -> dict:
    return {"ten": ten, "loai": loai, "mo_ta": mo_ta, "seed": seed, "sr": SR, **video, "kho": kho, "doan": doan,
            "quy_uoc_he_so": QUY_UOC_HE_SO, "mep_mo": list(mep_mo), "ky_vong": ky_vong, "ly_do_ky_vong": ly_do, **them}


def _chuan_hoa(x: np.ndarray) -> tuple:
    """Hạ cả video một hệ số khi đỉnh > 0,95 (không cắt đỉnh, không đổi SNR); trả (tín hiệu, hệ số)."""
    s = min(1.0, 0.95 / float(np.abs(x).max()))
    return x * s, s


# ---------------------------------------------------------------- các ca
def ca_a01(d: str) -> dict:
    with _nhip(120.0):
        clip = nhac_co_nhip(270, seed=5011)
    kho = [_kho(d, "goc_A01.wav", clip)]
    i0 = _i(333.3)
    v = _video(d, _chen(_giai(900, 5012), clip, i0))
    return _st("A01_nhip120_tron", "nhip_120bpm_dung_tron",
               "Clip nhạc có nhịp 120 BPM (am_thanh_lap.nhac_co_nhip với ô nhịp 2,0 s thay 2,124 s; trống mẫu cố định "
               "mỗi 8 ô nhịp) dài 270 s, dùng TRỌN, sạch, chèn cắt cứng ở 333,3 s của video 900 s nền nốt ngẫu nhiên.",
               {"clip_nhac_co_nhip_120bpm": 5011, "nen_giai_dieu": 5012}, v, kho,
               [_doan("goc_A01.wav", i0, 0, len(clip))], "da",
               "Sạch, dùng trọn, tương phản cao; chỉ khác bộ trong mẫu ở nhịp (đường nền tự giống ở bội ô nhịp 2,0 s).",
               nhip_clip_bpm=120.0, chu_ky_phach_do_s=_chu_ky_phach(clip))


def ca_a02(d: str) -> dict:
    clip = nhac_co_nhip(360, seed=5021)
    kho = [_kho(d, "goc_A02.wav", clip)]
    j0, j1, i0 = _i(47.77), _i(271.31), _i(412.6)
    doan = clip[j0:j1]
    nen = nhac_co_nhip(1000, seed=5022)
    vung = slice(i0, i0 + len(doan))
    nen = nen * (_rms(doan) / _rms(nen[vung]) * 10 ** (-6 / 20))
    tron = nen.copy()
    tron[vung] += doan
    tron, s = _chuan_hoa(tron)
    v = _video(d, tron)
    return _st("A02_nhip_mot_phan_tren_nen_nhip", "nhip_mot_phan_tren_nen_nhip",
               "Clip nhạc có nhịp 113 BPM 360 s, dùng MỘT PHẦN clip[47,77..271,31] (mép giữa ô nhịp), TRỘN lên một nền nhạc "
               "có nhịp 113 BPM seed khác (cùng mẫu kick tất định) chạy suốt video 1000 s; trong vùng clip nền thấp hơn "
               "clip 6 dB. Clip vào/ra cắt cứng trên nền liên tục, từ 412,6 s.",
               {"clip_nhac_co_nhip": 5021, "nen_nhac_co_nhip": 5022}, v, kho,
               [_doan("goc_A02.wav", i0, j0, j1)], "chua_hoac_da",
               "Engine (16332aa) bật moc_mo_ho cho dòng này — báo nhầm vì nền nhịp dùng chung mẫu kick — nên nơi gọi "
               "(Engine._ly_do_khong_tinh_chinh) không tinh chỉnh: CHƯA là đúng hợp đồng. Gọi thẳng module (hay engine sau "
               "này không bật cờ) mà ĐÃ thì phải ra MỘT đoạn [412,6; 636,14] (clip trội nền 6 dB, mép cắt cứng).",
               snr_clip_tren_nen_db=round(20 * np.log10(_rms(doan) / _rms(nen[vung])), 3), he_so_chuan_hoa=round(s, 6))


def ca_a03(d: str) -> dict:
    clip = _giai(360, 5031)
    kho = [_kho(d, "goc_A03.wav", clip)]
    j0, j1, i0 = _i(18.2), _i(348.2), _i(250.0)
    video = _chen(_giai(900, 5032), clip[j0:j1], i0)
    n3 = (j1 - j0) // 3
    a, b = i0 + n3, i0 + 2 * n3
    g = _giong_noi(b - a, 5033)
    g *= _rms(video[a:b]) / _rms(g)                       # 0 dB so với tiếng clip trong vùng đè
    video[a:b] += g
    video, s = _chuan_hoa(video)
    v = _video(d, video)
    return _st("A03_giong_noi_giua", "giong_noi_0db_mot_phan_ba_giua",
               "Clip nốt ngẫu nhiên 360 s, dùng clip[18,2..348,2] (330 s) ở 250 s của video 900 s; âm GIỐNG GIỌNG NÓI "
               "(ồn dải 300–3400 Hz điều chế âm tiết 3–5 Hz, có ngắt hơi) ĐÈ 0 dB CHỈ trong một phần ba giữa "
               "(video 360–470 s); hai phần ba còn lại sạch. Clip vẫn nguyên bên dưới lớp đè.",
               {"clip": 5031, "nen": 5032, "giong_noi": 5033}, v, kho, [_doan("goc_A03.wav", i0, j0, j1)], "da",
               "Một đoạn liền: clip có mặt suốt (2/3 sạch, 1/3 dưới giọng 0 dB). Báo «chỗ cắt» trong vùng đè là SAI.",
               vung_de_giong_noi=[round(a / SR, 6), round(b / SR, 6)],
               snr_vung_de_db=round(20 * np.log10(_rms(clip[j0 + n3:j0 + 2 * n3]) / _rms(g)), 3),
               he_so_chuan_hoa=round(s, 6))


def ca_a04(d: str) -> dict:
    clip = _giai(300, 5041)
    kho = [_kho(d, "goc_A04.wav", clip)]
    j0, j1, i0 = _i(52.6), _i(251.8), _i(287.35)
    m, L = _i(1.0), j1 - j0
    video = _giai(800, 5042)
    video[i0 + m:i0 + L - m] = clip[j0 + m:j1 - m]
    g = (np.arange(2 * m) + 0.5) / (2 * m)                # dốc tuyến tính 0 → 1 trong 2 s, 0,5 ở mép khai
    video[i0 - m:i0 + m] = (1 - g) * video[i0 - m:i0 + m] + g * clip[j0 - m:j0 + m]
    video[i0 + L - m:i0 + L + m] = g[::-1] * clip[j1 - m:j1 + m] + (1 - g[::-1]) * video[i0 + L - m:i0 + L + m]
    v = _video(d, video)
    dn = _doan("goc_A04.wav", i0, j0, j1)
    return _st("A04_chuyen_mo_2s", "chuyen_mo_2s_vao_ra",
               "Clip nốt ngẫu nhiên 300 s, dùng clip[52,6..251,8] ở 287,35 s của video 800 s, CHUYỂN MỜ tuyến tính 2 s "
               "khi vào và khi ra (tâm dốc = mép khai; trong dốc clip và nền trộn theo tỉ lệ, ngoài dốc thuần một bên).",
               {"clip": 5041, "nen": 5042}, v, kho, [dn], "da",
               "Mép mờ ±1 s quanh tâm dốc (mep_mo); phần giữa là bản sao nguyên mẫu.",
               mep_mo=({"t": dn["video_tu"], "nua_rong": 1.0}, {"t": dn["video_den"], "nua_rong": 1.0}))


def ca_a05(d: str) -> dict:
    clip = _giai(360, 5051)
    kho = [_kho(d, "goc_A05.wav", clip)]
    j0, j1, i0 = _i(21.0), _i(343.0), _i(198.4)
    video = _chen(_giai(900, 5052), clip[j0:j1], i0)
    a = i0 + (_i(161.4) - j0)                         # lặng từ giây clip 161,4
    b = a + _i(4.0)
    video[a:b] = 0.0
    v = _video(d, video)
    return _st("A05_im_lang_4s", "im_lang_4s_trong_doan",
               "Clip nốt ngẫu nhiên 360 s, dùng clip[21,0..343,0] ở 198,4 s của video 900 s; 4 s IM LẶNG TUYỆT ĐỐI (mẫu "
               "0) thay tiếng clip ở giây clip 161,40–165,40 (video 338,8–342,8), trục clip vẫn chạy (sau khoảng lặng "
               "căn chỉnh không đổi). Mép khoảng lặng giữa nốt.",
               {"clip": 5051, "nen": 5052}, v, kho,
               [_doan("goc_A05.wav", i0, j0, j0 + (a - i0)), _doan("goc_A05.wav", b, j0 + (b - i0), j1)], "da",
               "4 s không có tiếng clip → hai đoạn; gộp qua khoảng lặng là báo thừa 4 s.",
               vung_im_lang=[[round(a / SR, 6), round(b / SR, 6)]])


def ca_a06(d: str) -> dict:
    clip = _giai(420, 5061)
    kho = [_kho(d, "goc_A06.wav", clip)]
    j0, x, j1, i0 = _i(8.6), _i(203.3), _i(395.0), _i(301.7)    # cắt 3 s = 7,5 nốt: hai mép ở 1/4 và 3/4 nốt
    cat = _i(3.0)
    video = _chen(_giai(1000, 5062), np.concatenate([clip[j0:x], clip[x + cat:j1]]), i0)
    v = _video(d, video)
    return _st("A06_cat_3s", "cat_nho_3s_khong_chen",
               "Clip nốt ngẫu nhiên 420 s; video 1000 s phát clip[8,6..203,3] từ 301,7 s rồi NỐI THẲNG clip[206,3..395,0] "
               "(bỏ 3 s clip, không chèn gì) — hai căn chỉnh lệch 3 s < dedup_s 20 s.",
               {"clip": 5061, "nen": 5062}, v, kho,
               [_doan("goc_A06.wav", i0, j0, x), _doan("goc_A06.wav", i0 + (x - j0), x + cat, j1)], "da",
               "Hai đoạn nối nhau trên video, nhảy 3 s trên trục clip ở video 496,4 s.")


def ca_a07(d: str) -> dict:
    clip = _giai(300, 5071)
    kho = [_kho(d, "goc_A07.opus", clip, opus=True)]
    j0, x, j1, i0 = _i(30.2), _i(177.0), _i(288.6), _i(401.15)
    lui = _i(10.0)
    video = _chen(_giai(1000, 5072), np.concatenate([clip[j0:x], clip[x - lui:j1]]), i0)
    v = _video(d, video)
    return _st("A07_tua_lui_10s", "tua_lui_10s_phat_lai",
               "Clip nốt ngẫu nhiên 300 s (kho .opus 64 kbps như kho thật); video 1000 s phát clip[30,2..177,0] từ 401,15 s "
               "rồi TUA LÙI 10 s phát lại clip[167,0..288,6] liền sau (547,95 s) — giây clip 167,0–177,0 xuất hiện hai lần.",
               {"clip": 5071, "nen": 5072}, v, kho,
               [_doan("goc_A07.opus", i0, j0, x), _doan("goc_A07.opus", i0 + (x - j0), x - lui, j1)], "da",
               "Hai căn chỉnh lệch 10 s trong cùng dòng engine; phải báo cả phần phát lại.")


def _khuc_40p(n: int) -> np.ndarray:
    """Khúc n (0–9) của clip 40 phút: _giai_dieu 240 s seed 5081 + n, lưới nốt lệch 0,2 s (mép 25:00 và 30:00 rơi giữa
    nốt, không rơi vào đuôi bao Hanning gần im)."""
    x = _giai(240.2, 5081 + n)[_i(0.2):]
    assert len(x) == _i(240.0), len(x)                    # khúc đúng 240 s: giây clip của khúc n bắt đầu ở 240·n
    return x


def _ghi_clip_40p(path: str) -> None:
    """Clip 40 phút = 10 khúc ``_khuc_40p`` 240 s (seed 5081–5090) ghi nối tiếp — không giữ cả 2400 s trong RAM."""
    with wave.open(path, "wb") as ra:
        ra.setnchannels(1)
        ra.setsampwidth(2)
        ra.setframerate(SR)
        for n in range(10):
            tam = f"{path}.khuc{n}.wav"
            _ghi_wav(tam, _khuc_40p(n), SR)
            with wave.open(tam, "rb") as w:
                ra.writeframes(w.readframes(w.getnframes()))
            os.remove(tam)


def _clip_40p_25_30() -> np.ndarray:
    """clip[1500..1800] của clip 40 phút: khúc 6 (1440–1680 s) từ giây 60 + khúc 7 (1680–1920 s) tới giây 120."""
    return np.concatenate([_khuc_40p(6)[_i(60):], _khuc_40p(7)[:_i(120)]])


def _ca_40p(d: str, ten: str, kho_dai: bool, seed_nen: int, P: float) -> dict:
    os.makedirs(os.path.join(d, "kho"))
    if kho_dai:
        tam = os.path.join(d, "_tam_clip40.wav")
        _ghi_clip_40p(tam)
        _ffmpeg("-i", tam, *OPUS_KHO, os.path.join(d, "kho", "goc_A09.opus"))
        os.remove(tam)
        with open(os.path.join(d, "kho", ".kho_video_dai"), "a", encoding="utf-8"):
            pass                                          # = channel.dat_kho_video_dai: kho video dài D-34, mốc 21 bit
        kho = [{"clip": "goc_A09.opus", "do_dai_nguon_s": 2400.0, "dinh_dang": DD_OPUS}]
    else:
        _ghi_clip_40p(os.path.join(d, "kho", "goc_A08.wav"))
        kho = [{"clip": "goc_A08.wav", "do_dai_nguon_s": 2400.0, "dinh_dang": DD_WAV}]
    i0 = _i(P)
    v = _video(d, _chen(_giai(900, seed_nen), _clip_40p_25_30(), i0))
    dn = _doan(kho[0]["clip"], i0, _i(1500), _i(1800))
    seed = {"clip_10_khuc_240s": list(range(5081, 5091)), "nen": seed_nen}
    if not kho_dai:
        return _st(ten, "clip_dai_40p_dung_25_30_kho_thuong_16bit",
                   "Clip 40 phút (10 khúc nốt ngẫu nhiên 240 s), chỉ dùng 25:00–30:00 (clip[1500..1800]) ở 311,11 s của "
                   "video 900 s. Kho THƯỜNG (mốc 16 bit, cuộn sau 65536 khung ≈ 1521,7 s = 25:21,7): phần clip sau "
                   "25:21,7 mang giây clip cuộn về 0 → engine báo căn chỉnh lệch ~1521,7 s (giới hạn đã biết, "
                   "FINGERPRINT_RECOVERY_ARCHITECTURE.md §6.1).", seed, v, kho, [dn], "chua_hoac_da",
                   "Neo engine sai do mốc cuộn; tinh chỉnh không cứu được → CHƯA là đúng; nếu ĐÃ thì phải đúng giây clip "
                   "1500–1800 (không phải giây clip cuộn).")
    return _st(ten, "clip_dai_40p_dung_25_30_kho_video_dai",
               "Cùng clip 40 phút nhưng kho .opus 64 kbps (như kho thật) có dấu «.kho_video_dai» (D-34, mốc 21 bit, không "
               "cuộn); chỉ dùng 25:00–30:00 ở 287,9 s của video 900 s nền khác. Engine đặt start_s = vung_khop_s (kho "
               "video dài); neo = giây video của giây 0 clip = 287,9 − 1500 (ÂM, chưa kẹp).", seed, v, kho, [dn], "da",
               "Neo đúng; clip dài phải đọc theo cửa sổ quanh 25:00–30:00 (tua vào giữa file opus 40 phút).")


def ca_a08(d: str) -> dict:
    return _ca_40p(d, "A08_clip40p_25_30_kho_thuong", False, 5091, 311.11)


def ca_a09(d: str) -> dict:
    return _ca_40p(d, "A09_clip40p_25_30_kho_video_dai", True, 5092, 287.9)


def ca_a10(d: str) -> dict:
    clip = _giai(390, 5101)
    kho = [_kho(d, "goc_A10.opus", clip, opus=True)]
    j0, j1, i0 = _i(44.2), _i(357.0), _i(222.2)
    video = _chen(_giai(900, 5102), clip[j0:j1], i0)
    on = _on_trang(len(video), 5103)
    on *= _rms(clip[j0:j1]) / _rms(on) * 10 ** (-10 / 20)
    video, s = _chuan_hoa(video + on)
    v = _video(d, video)
    return _st("A10_on_10db", "on_trang_snr_10db_ca_video",
               "Clip nốt ngẫu nhiên 390 s (kho .opus 64 kbps), dùng clip[44,2..357,0] ở 222,2 s của video 900 s; ỒN TRẮNG "
               "(cắt trên 5,5 kHz) phủ TOÀN video, SNR 10 dB so với tiếng clip.",
               {"clip": 5101, "nen": 5102, "on": 5103}, v, kho, [_doan("goc_A10.opus", i0, j0, j1)], "da",
               "SNR 10 dB còn rõ (mỗi nốt nằm gọn một dải mel); mép cắt cứng.",
               snr_db=round(20 * np.log10(_rms(clip[j0:j1]) / _rms(on)), 3), he_so_chuan_hoa=round(s, 6))


def ca_a11(d: str) -> dict:
    clip = _giai(480, 5111)
    kho = [_kho(d, "goc_A11.wav", clip)]
    j0, j1, i0 = _i(96.6), _i(401.8), _i(250.5)
    cham = _doi_toc(clip[j0:j1], 0.97, d)
    v = _video(d, _chen(_giai(1000, 5112), cham, i0))
    return _st("A11_cham_097_mot_phan", "toc_do_097_mot_phan",
               "Clip nốt ngẫu nhiên 480 s, đoạn clip[96,6..401,8] phát CHẬM lại 0,97 lần (FFmpeg atempo=0,97, giữ cao độ) "
               "chèn cắt cứng ở 250,5 s của video 1000 s (video_den = 250,5 + 305,2/0,97).",
               {"clip": 5111, "nen": 5112}, v, kho, [_doan("goc_A11.wav", i0, j0, j1, 0.97)], "da",
               "Một đoạn, he_so 0,97 (video chậm hơn); phải bám độ trôi 3 %.",
               do_dai_chen_thuc_te_s=round(len(cham) / SR, 6), ly_thuyet_s=round((j1 - j0) / SR / 0.97, 6))


def ca_a12(d: str) -> dict:
    clip = _giai(300, 5121)
    kho = [_kho(d, "goc_A12.wav", clip)]
    (a0, a1, p1), (b0, b1, p2) = (_i(18.6), _i(211.4), _i(140.0)), (_i(95.8), _i(284.2), _i(1012.45))
    video = _chen(_chen(_giai(1500, 5122), clip[a0:a1], p1), clip[b0:b1], p2)
    v = _video(d, video)
    return _st("A12_hai_lan_xa", "mot_clip_hai_lan_xa_nhau",
               "Clip nốt ngẫu nhiên 300 s dùng HAI lần cách xa trong video 1500 s: clip[18,6..211,4] ở 140 s và "
               "clip[95,8..284,2] ở 1012,45 s (giây clip 95,8–211,4 có trong cả hai lần).",
               {"clip": 5121, "nen": 5122}, v, kho,
               [_doan("goc_A12.wav", p1, a0, a1), _doan("goc_A12.wav", p2, b0, b1)], "da",
               "Mỗi dòng engine (một lần dùng) phải ra đúng đoạn của nó, không lấn sang lần kia.")


def ca_a13(d: str) -> dict:
    clip = _giai(240.5, 5131)[_i(0.2):]                  # lưới nốt lệch 0,2 s → mép 0,4 s và L − 0,7 s rơi GIỮA nốt
    kho = [_kho(d, "goc_A13.wav", clip)]
    j0, j1, i0 = _i(0.4), len(clip) - _i(0.7), _i(377.77)
    v = _video(d, _chen(_giai(800, 5132), clip[j0:j1], i0))
    return _st("A13_cat_mep_04_07", "cat_mep_dau_0_4_cuoi_0_7",
               "Clip 240,3 s (_giai_dieu seed 5131 bỏ 0,2 s đầu để mép rơi giữa nốt), video 800 s dùng clip[0,4..239,6] — "
               "bỏ 0,4 s ĐẦU và 0,7 s CUỐI clip — ở 377,77 s, cắt cứng.",
               {"clip": 5131, "nen": 5132}, v, kho, [_doan("goc_A13.wav", i0, j0, j1)], "da",
               "Mép đo được phải là giây clip 0,4 và 239,6 — chốt về đầu/cuối clip (0 / 240,3) là sai 0,4 / 0,7 s.")


def ca_a14(d: str) -> dict:
    a, b = _giai(260, 5141), nhac_co_nhip(240, seed=5142)
    kho = [_kho(d, "goc_A14_a.wav", a), _kho(d, "goc_A14_b.opus", b, opus=True)]
    ja0, ja1, jb0, jb1, i0 = _i(31.8), _i(228.2), _i(12.9), _i(198.4), _i(270.0)
    video = _chen(_giai(1000, 5143), np.concatenate([a[ja0:ja1], b[jb0:jb1]]), i0)
    v = _video(d, video)
    return _st("A14_hai_clip_noi_nhau", "hai_clip_khac_noi_tiep",
               "Hai clip KHÁC nhau phát nối tiếp không khe trong video 1000 s: clip A (nốt ngẫu nhiên 260 s, WAV) "
               "a[31,8..228,2] từ 270 s, rồi clip B (nhạc có nhịp 113 BPM 240 s, kho .opus) b[12,9..198,4] từ 466,4 s.",
               {"clip_a": 5141, "clip_b_nhac_co_nhip": 5142, "nen": 5143}, v, kho,
               [_doan("goc_A14_a.wav", i0, ja0, ja1), _doan("goc_A14_b.opus", i0 + (ja1 - ja0), jb0, jb1)], "da",
               "Mỗi clip một dòng; đoạn của dòng này phải dừng đúng chỗ nối, không lấn sang clip kia.")


def ca_a15(d: str) -> dict:
    clip = _giai(450, 5151)
    kho = [_kho(d, "goc_A15.wav", clip)]
    j0, j1, i0 = _i(63.4), _i(388.6), _i(199.9)
    nhanh = _doi_toc(clip[j0:j1], 1.03, d)
    v = _video(d, _chen(_giai(900, 5152), nhanh, i0), ("-ac", "1", "-c:a", "libopus", "-b:a", "48k"), ".webm",
               "WebM/Opus 48 kbps mono (giải mã bằng FFmpeg)")
    return _st("A15_nhanh_103_opus48", "toc_do_103_mot_phan_opus48",
               "Clip nốt ngẫu nhiên 450 s, đoạn clip[63,4..388,6] phát NHANH 1,03 lần (atempo=1,03) chèn ở 199,9 s của "
               "video 900 s, rồi CẢ video nén Opus 48 kbps mono trong WebM.",
               {"clip": 5151, "nen": 5152}, v, kho, [_doan("goc_A15.wav", i0, j0, j1, 1.03)], "da",
               "Một đoạn he_so 1,03 qua nén Opus 48 kbps (chất lượng khá); mép cắt cứng.",
               do_dai_chen_thuc_te_s=round(len(nhanh) / SR, 6), ly_thuyet_s=round((j1 - j0) / SR / 1.03, 6))


def ca_a16(d: str) -> dict:
    clip = _giai(330, 5161)
    kho = [_kho(d, "goc_A16.wav", clip)]
    j0, j1, i0 = _i(27.4), _i(301.8), _i(333.33)
    v = _video(d, _chen(_giai(900, 5162), clip[j0:j1], i0), ("-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "128k"),
               ".m4a", "M4A/AAC 128 kbps stereo 44,1 kHz (hai kênh như nhau; giải mã bằng FFmpeg)")
    return _st("A16_aac_m4a_stereo", "aac_m4a_44k_stereo",
               "Clip nốt ngẫu nhiên 330 s, dùng clip[27,4..301,8] ở 333,33 s của video 900 s; video nén AAC 128 kbps "
               "stereo 44,1 kHz trong M4A (độ trễ mồi của AAC phải được bù khi giải mã).",
               {"clip": 5161, "nen": 5162}, v, kho, [_doan("goc_A16.wav", i0, j0, j1)], "da",
               "Sạch, chỉ khác định dạng video (M4A/AAC 44,1 kHz stereo, kiểu file tải YouTube).")


def ca_a17(d: str) -> dict:
    # Thêm sau lượt engine đầu: A11 (0,97) và A15 (1,03) engine KHÔNG thấy (bộ dò độ trôi không chạy, chỉ lưới cao độ)
    # → biến thể ±2 % để nhánh he_so ≠ 1 của module vẫn có ca ẩn đi qua đường sản phẩm.
    clip = _giai(420, 5171)
    kho = [_kho(d, "goc_A17.wav", clip)]
    j0, j1, i0 = _i(70.2), _i(381.0), _i(233.3)
    cham = _doi_toc(clip[j0:j1], 0.98, d)
    v = _video(d, _chen(_giai(900, 5172), cham, i0))
    return _st("A17_cham_098_mot_phan", "toc_do_098_mot_phan",
               "(Biến thể của A11 mà engine thấy được) clip nốt ngẫu nhiên 420 s, đoạn clip[70,2..381,0] phát CHẬM 0,98 "
               "lần (atempo=0,98, giữ cao độ) chèn cắt cứng ở 233,3 s của video 900 s.",
               {"clip": 5171, "nen": 5172}, v, kho, [_doan("goc_A17.wav", i0, j0, j1, 0.98)], "da",
               "Một đoạn he_so 0,98 (video chậm hơn); phải bám độ trôi 2 %.",
               do_dai_chen_thuc_te_s=round(len(cham) / SR, 6), ly_thuyet_s=round((j1 - j0) / SR / 0.98, 6))


def ca_a18(d: str) -> dict:
    clip = _giai(450, 5181)
    kho = [_kho(d, "goc_A18.wav", clip)]
    j0, j1, i0 = _i(41.0), _i(377.4), _i(260.6)
    nhanh = _doi_toc(clip[j0:j1], 1.02, d)
    v = _video(d, _chen(_giai(900, 5182), nhanh, i0), ("-ac", "1", "-c:a", "libopus", "-b:a", "48k"), ".webm",
               "WebM/Opus 48 kbps mono (giải mã bằng FFmpeg)")
    return _st("A18_nhanh_102_opus48", "toc_do_102_mot_phan_opus48",
               "(Biến thể của A15 mà engine thấy được) clip nốt ngẫu nhiên 450 s, đoạn clip[41,0..377,4] phát NHANH 1,02 "
               "lần (atempo=1,02) chèn ở 260,6 s của video 900 s, rồi CẢ video nén Opus 48 kbps mono trong WebM.",
               {"clip": 5181, "nen": 5182}, v, kho, [_doan("goc_A18.wav", i0, j0, j1, 1.02)], "da",
               "Một đoạn he_so 1,02 qua nén Opus 48 kbps; mép cắt cứng.",
               do_dai_chen_thuc_te_s=round(len(nhanh) / SR, 6), ly_thuyet_s=round((j1 - j0) / SR / 1.02, 6))


CA = {"A01": ca_a01, "A02": ca_a02, "A03": ca_a03, "A04": ca_a04, "A05": ca_a05, "A06": ca_a06, "A07": ca_a07,
      "A08": ca_a08, "A09": ca_a09, "A10": ca_a10, "A11": ca_a11, "A12": ca_a12, "A13": ca_a13, "A14": ca_a14,
      "A15": ca_a15, "A16": ca_a16, "A17": ca_a17, "A18": ca_a18}


def dung(ma: str) -> dict:
    """Dựng một ca vào thư mục tạm rồi đổi tên thành ``<RA>/<ten>`` (xoá bản cũ cùng mã)."""
    for cu in [x for x in os.listdir(RA) if x.split("_")[0] == ma]:
        shutil.rmtree(os.path.join(RA, cu))
    tam = os.path.join(RA, f"_dang_dung_{ma}")
    if os.path.isdir(tam):
        shutil.rmtree(tam)
    os.makedirs(tam)
    t0 = time.perf_counter()
    st = CA[ma](tam)
    seeds =[s for v in st["seed"].values() for s in (v if isinstance(v, list) else [v])]
    assert min(seeds) >= 5000, f"seed < 5000: {st['seed']}"
    assert not [x for x in os.listdir(tam) if x.startswith("_tam")], "còn file tạm"
    st["thoi_gian_dung_s"] = round(time.perf_counter() - t0, 1)
    with open(os.path.join(tam, "su_that.json"), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    d = os.path.join(RA, st["ten"])
    os.rename(tam, d)
    return kiem_su_that.ghi_vao_su_that(d)


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
              f"{kq['ly_do_xem_lai']}", flush=True)
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
