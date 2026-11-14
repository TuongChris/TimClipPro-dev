# -*- coding: utf-8 -*-
"""Kịch bản audio GIẢ LẬP có sự thật biết trước — bộ thử sai số mốc của Tool Quét (14/11/2026).

100% tín hiệu tổng hợp, seed cố định, chỉ lấy từ bộ sinh của repo: ``tests/conftest.py`` (``_giai_dieu``,
``_ghi_wav``) và ``tests/am_thanh_lap.py`` (nhạc có nhịp, vòng lặp y hệt). Không dùng audio thật.

Sự thật ghi theo đoạn ``{video_tu, video_den, clip_tu, clip_den, he_so}``: ``he_so`` = tốc độ video so với clip
(1.02 = video phát nhanh hơn 2%), nên ``video_den − video_tu = (clip_den − clip_tu) / he_so`` và giây 0 của clip
nằm ở ``video_tu − clip_tu / he_so`` trên trục video. Mọi mốc tính TỪ CÁCH DỰNG, không gọi mã sản phẩm.
"""
from __future__ import annotations

import os
import subprocess
import sys
import wave

import numpy as np

MA = r"C:\Dev\Tool_Quet\TimClipPro"
sys.path.insert(0, os.path.join(MA, "tests"))
from am_thanh_lap import SR, nhac_co_nhip, vong_lap_y_het  # noqa: E402
from conftest import _ghi_wav, _giai_dieu  # noqa: E402

TEN_VIDEO = "video_vi_pham.wav"


def _doc_wav(path) -> np.ndarray:
    """Đọc lại WAV 16 bit đã ghi bằng ``_ghi_wav`` / FFmpeg (cùng thang 32000 như tests/test_toa_do_audio_that.py)."""
    with wave.open(str(path), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == SR, path
        du_lieu = w.readframes(w.getnframes())
    return np.frombuffer(du_lieu, dtype=np.int16).astype(np.float64) / 32000.0


def _ffmpeg(*tham_so: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *tham_so], check=True)


def _i(giay: float) -> int:
    return int(round(giay * SR))


def _doan(video_tu: float, clip_tu: float, clip_den: float, he_so: float = 1.0) -> dict:
    return {"video_tu": float(video_tu), "video_den": round(video_tu + (clip_den - clip_tu) / he_so, 6),
            "clip_tu": float(clip_tu), "clip_den": float(clip_den), "he_so": float(he_so)}


def _chen(nen: np.ndarray, doan: np.ndarray, P: float) -> np.ndarray:
    """THAY nền bằng đoạn chèn từ mốc P (cắt cứng, như tests/conftest.py ``bo_clip``)."""
    i0 = _i(P)
    assert i0 + len(doan) <= len(nen), "đoạn chèn vượt quá video"
    nen = nen.copy()
    nen[i0:i0 + len(doan)] = doan
    return nen


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def _do_lech_mau(goc: np.ndarray, sau: np.ndarray, tu_s: float, dai_s: float = 20.0, tran_s: float = 0.5) -> float:
    """Độ lệch (giây) của ``sau`` so với ``goc`` quanh ``tu_s``, bằng tương quan chéo FFT (dương = ``sau`` trễ)."""
    a = goc[_i(tu_s): _i(tu_s + dai_s)]
    b = sau[_i(tu_s): _i(tu_s + dai_s)]
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    r = np.fft.irfft(np.fft.rfft(b, n) * np.conj(np.fft.rfft(a, n)), n)
    tran = _i(tran_s)
    cua_so = np.concatenate([r[-tran:], r[:tran + 1]])   # trễ −tran … +tran
    return round((int(np.argmax(cua_so)) - tran) / SR, 5)


def _kho(thu_muc: str, ten: str, sig: np.ndarray) -> str:
    kho = os.path.join(thu_muc, "kho")
    os.makedirs(kho, exist_ok=True)
    _ghi_wav(os.path.join(kho, ten), sig, SR)
    return ten


def _ghi_video(thu_muc: str, sig: np.ndarray, ten: str = TEN_VIDEO) -> str:
    _ghi_wav(os.path.join(thu_muc, ten), sig, SR)
    return ten


def _su_that(ten: str, mo_ta: str, seed: dict, ten_clip: str, do_dai_clip: float, video: str,
             do_dai_video: float, doan: list, **them) -> dict:
    return {"kich_ban": ten, "mo_ta": mo_ta, "seed": seed, "sr": SR, "ten_clip": ten_clip,
            "do_dai_clip_s": float(do_dai_clip), "video": video, "do_dai_video_s": float(do_dai_video),
            "doan": doan, "cau_hinh_engine_doi": {}, **them}


# ---------------------------------------------------------------- tín hiệu dùng lại

def _clip_s1() -> np.ndarray:
    return _giai_dieu(420, seed=1101, sr=SR)


def _video_s1() -> np.ndarray:
    return _chen(_giai_dieu(1080, seed=1102, sr=SR), _clip_s1(), 300)


def _clip_s4() -> np.ndarray:
    return _giai_dieu(480, seed=1401, sr=SR)


def _clip_s5() -> np.ndarray:
    return _giai_dieu(360, seed=1501, sr=SR)


def _clip_s6b() -> np.ndarray:
    lap, _ = vong_lap_y_het(160, seed=1612)
    return np.concatenate([nhac_co_nhip(100, seed=1611), lap, nhac_co_nhip(100, seed=1613)])


CLIP_THEO_KICH_BAN = {      # dùng lại cho kho NHIỀU clip của S0 (cùng seed ⇒ cùng tín hiệu từng mẫu)
    "goc_S1.wav": _clip_s1,
    "goc_S3.wav": lambda: _giai_dieu(540, seed=1301, sr=SR),
    "goc_S4.wav": _clip_s4,
    "goc_S5.wav": _clip_s5,
    "goc_S6.wav": lambda: nhac_co_nhip(360, seed=1601),
    "goc_S6b.wav": _clip_s6b,
    "goc_S7.wav": lambda: _giai_dieu(480, seed=1701, sr=SR),
    "goc_S8.wav": lambda: _giai_dieu(60, seed=1801, sr=SR),
    "goc_S9.wav": lambda: _giai_dieu(420, seed=1901, sr=SR),
}


# ---------------------------------------------------------------- các kịch bản

def tao_s0(d: str) -> dict:
    for ten, ham in CLIP_THEO_KICH_BAN.items():
        _kho(d, ten, ham())
    video = np.concatenate([_giai_dieu(600, seed=1001, sr=SR), nhac_co_nhip(400, seed=1002)])
    v = _ghi_video(d, video)
    return _su_that("S0", "ĐỐI CHỨNG ÂM: video 1000 s không chứa clip nào (600 s nốt ngẫu nhiên + 400 s nhạc có nhịp "
                    "seed khác — cùng mẫu kick tất định với goc_S6/S6b); kho = 9 clip của S1, S3–S9.",
                    {"nen_giai_dieu": 1001, "nen_nhac_co_nhip": 1002, "clip": "như từng kịch bản"},
                    "", 0.0, v, 1000.0, [], kho_nhieu_clip=sorted(CLIP_THEO_KICH_BAN))


def tao_s1(d: str) -> dict:
    ten = _kho(d, "goc_S1.wav", _clip_s1())
    v = _ghi_video(d, _video_s1())
    return _su_that("S1", "Dùng TRỌN clip 420 s, sạch, chèn ở P = 300 s của video 1080 s.",
                    {"clip": 1101, "nen": 1102}, ten, 420, v, 1080, [_doan(300, 0, 420)])


def tao_s2(d: str) -> dict:
    ten = _kho(d, "goc_S1.wav", _clip_s1())
    goc = _video_s1()
    tam = os.path.join(d, "_video_truoc_nen.wav")
    _ghi_wav(tam, goc, SR)
    v = "video_vi_pham.opus"
    _ffmpeg("-i", tam, "-af", "volume=-6dB", "-ac", "1", "-c:a", "libopus", "-b:a", "32k", os.path.join(d, v))
    giai = os.path.join(d, "_video_giai_lai.wav")
    _ffmpeg("-i", os.path.join(d, v), "-ac", "1", "-ar", str(SR), giai)
    sau = _doc_wav(giai)
    kiem = {"do_dai_giai_lai_s": round(len(sau) / SR, 4),
            "lech_mau_quanh_P_s": _do_lech_mau(goc, sau, 295.0),
            "lech_mau_quanh_cuoi_s": _do_lech_mau(goc, sau, 700.0),
            "ti_le_rms_sau_truoc_db": round(20 * np.log10(_rms(sau[_i(300):_i(720)]) / _rms(goc[_i(300):_i(720)])), 2)}
    os.remove(tam)
    os.remove(giai)
    return _su_that("S2", "Như S1 nhưng video giảm 6 dB rồi nén Opus 32 kbps mono (.opus).",
                    {"clip": 1101, "nen": 1102}, ten, 420, v, 1080, [_doan(300, 0, 420)],
                    kiem_su_that=kiem)


def tao_s3(d: str) -> dict:
    clip = CLIP_THEO_KICH_BAN["goc_S3.wav"]()
    ten = _kho(d, "goc_S3.wav", clip)
    v = _ghi_video(d, _chen(_giai_dieu(1000, seed=1302, sr=SR), clip[_i(120):_i(420)], 400))
    return _su_that("S3", "Chỉ dùng một phần GIỮA clip 540 s: clip[120..420] chèn ở P = 400 s (giây 0 của clip ở 280 s "
                    "trên trục video — chỉ là mốc ảo).", {"clip": 1301, "nen": 1302}, ten, 540, v, 1000,
                    [_doan(400, 120, 420)])


def tao_s4(d: str) -> dict:
    clip = _clip_s4()
    ten = _kho(d, "goc_S4.wav", clip)
    chen = np.concatenate([clip[:_i(200)], _giai_dieu(30, seed=1403, sr=SR), clip[_i(260):]])
    v = _ghi_video(d, _chen(_giai_dieu(1100, seed=1402, sr=SR), chen, 250))
    return _su_that("S4", "Clip 480 s bị CẮT giữa: clip[0..200] + 30 s audio khác + clip[260..480] chèn từ P = 250 s "
                    "(bỏ 60 s, chèn 30 s ⇒ hai căn chỉnh lệch nhau 30 s > dedup_s 20 s).",
                    {"clip": 1401, "nen": 1402, "chen_khac": 1403}, ten, 480, v, 1100,
                    [_doan(250, 0, 200), _doan(480, 260, 480)])


def tao_s4b(d: str) -> dict:
    clip = _clip_s4()
    ten = _kho(d, "goc_S4.wav", clip)
    chen = np.concatenate([clip[:_i(200)], _giai_dieu(5, seed=1404, sr=SR), clip[_i(215):]])
    v = _ghi_video(d, _chen(_giai_dieu(1100, seed=1402, sr=SR), chen, 250))
    return _su_that("S4b", "(Thêm) Vết cắt NHỎ: clip[0..200] + 5 s audio khác + clip[215..480] từ P = 250 s (bỏ 15 s, "
                    "chèn 5 s ⇒ hai căn chỉnh lệch 10 s < dedup_s 20 s).",
                    {"clip": 1401, "nen": 1402, "chen_khac": 1404}, ten, 480, v, 1100,
                    [_doan(250, 0, 200), _doan(455, 215, 480)])


def _tao_s5(d: str, ten_kb: str, snr_db: float) -> dict:
    clip = _clip_s5()
    ten = _kho(d, "goc_S5.wav", clip)
    video = _chen(_giai_dieu(900, seed=1502, sr=SR), clip, 270)
    de = nhac_co_nhip(900, seed=1503)
    vung = slice(_i(270), _i(630))
    de = de * (_rms(clip) / _rms(de[vung]) * 10 ** (-snr_db / 20))
    tron = video + de
    tron = tron * (0.95 / np.abs(tron).max())       # chuẩn hoá chung: không đổi SNR, không bị cắt đỉnh
    snr_that = 20 * np.log10(_rms(clip) / _rms(de[vung]))
    v = _ghi_video(d, tron)
    return _su_that(ten_kb, f"Clip 360 s ở P = 270 s bị ĐÈ nhạc có nhịp to suốt video, SNR = {snr_db:g} dB "
                    "(RMS clip / RMS nhạc đè trong vùng clip).",
                    {"clip": 1501, "nen": 1502, "nhac_de": 1503}, ten, 360, v, 900, [_doan(270, 0, 360)],
                    kiem_su_that={"snr_do_lai_db": round(float(snr_that), 3)})


def tao_s5(d: str) -> dict:
    return _tao_s5(d, "S5", 0.0)


def tao_s5b(d: str) -> dict:
    return _tao_s5(d, "S5b", -5.0)


def tao_s6(d: str) -> dict:
    clip = CLIP_THEO_KICH_BAN["goc_S6.wav"]()
    ten = _kho(d, "goc_S6.wav", clip)
    v = _ghi_video(d, _chen(_giai_dieu(960, seed=1602, sr=SR), clip, 300))
    return _su_that("S6", "Clip là âm thanh LẶP (am_thanh_lap.nhac_co_nhip 113 BPM, 360 s), dùng trọn, P = 300 s.",
                    {"clip_nhac_co_nhip": 1601, "nen": 1602}, ten, 360, v, 960, [_doan(300, 0, 360)])


def tao_s6b(d: str) -> dict:
    clip = _clip_s6b()
    ten = _kho(d, "goc_S6b.wav", clip)
    v = _ghi_video(d, _chen(_giai_dieu(960, seed=1614, sr=SR), clip, 300))
    _, chu_ky = vong_lap_y_het(1, seed=1612)
    return _su_that("S6b", "(Thêm) Clip 360 s = nhạc có nhịp 100 s + vòng 8 ô nhịp lặp Y HỆT 160 s + nhạc có nhịp 100 s, "
                    "dùng trọn, P = 300 s.", {"nhac_dau": 1611, "vong_lap": 1612, "nhac_cuoi": 1613, "nen": 1614},
                    ten, 360, v, 960, [_doan(300, 0, 360)], chu_ky_vong_lap_s=round(chu_ky, 5))


def tao_s7(d: str) -> dict:
    clip = CLIP_THEO_KICH_BAN["goc_S7.wav"]()
    ten = _kho(d, "goc_S7.wav", clip)
    tam_vao, tam_ra = os.path.join(d, "_clip_goc.wav"), os.path.join(d, "_clip_nhanh.wav")
    _ghi_wav(tam_vao, clip, SR)
    _ffmpeg("-i", tam_vao, "-filter:a", "atempo=1.02", "-ar", str(SR), "-ac", "1", tam_ra)
    nhanh = _doc_wav(tam_ra)
    os.remove(tam_vao)
    os.remove(tam_ra)
    v = _ghi_video(d, _chen(_giai_dieu(1000, seed=1702, sr=SR), nhanh, 300))
    return _su_that("S7", "Clip 480 s tăng tốc 2% (FFmpeg atempo=1.02, giữ cao độ) dùng trọn ở P = 300 s; bật "
                    "quet_da_toc_do.", {"clip": 1701, "nen": 1702}, ten, 480, v, 1000, [_doan(300, 0, 480, 1.02)],
                    cau_hinh_engine_doi={"quet_da_toc_do": True},
                    kiem_su_that={"do_dai_sau_atempo_s": round(len(nhanh) / SR, 4),
                                  "ly_thuyet_480_chia_1_02_s": round(480 / 1.02, 4)})


def tao_s7b(d: str, ten_kb: str = "S7b", seed_clip: int = 1711, seed_nen: int = 1712) -> dict:
    """Bố cục của tests/test_toa_do_audio_that.py: clip[300..600] tăng tốc 2% ở P = 400, khúc 300/60, top_n 1."""
    clip = _giai_dieu(600, seed=seed_clip, sr=SR)
    ten = _kho(d, f"goc_{ten_kb}.wav", clip)
    tam_vao, tam_ra = os.path.join(d, "_doan_goc.wav"), os.path.join(d, "_doan_nhanh.wav")
    _ghi_wav(tam_vao, clip[_i(300):], SR)
    _ffmpeg("-i", tam_vao, "-filter:a", "atempo=1.02", "-ar", str(SR), "-ac", "1", tam_ra)
    nhanh = _doc_wav(tam_ra)
    os.remove(tam_vao)
    os.remove(tam_ra)
    v = _ghi_video(d, _chen(_giai_dieu(900, seed=seed_nen, sr=SR), nhanh, 400))
    return _su_that(ten_kb, f"(Thêm) Bố cục của tests/test_toa_do_audio_that.py, seed {seed_clip}/{seed_nen}: clip[300..600] "
                    "của clip 600 s tăng tốc 2% chèn ở P = 400 s (video 900 s), chunk_s 300 / overlap_s 60, top_n 1, "
                    "quet_da_toc_do — giây 0 của clip ở 400 − 300/1,02 ≈ 105,88 s (mốc ảo).",
                    {"clip": seed_clip, "nen": seed_nen}, ten, 600, v, 900, [_doan(400, 300, 600, 1.02)],
                    cau_hinh_engine_doi={"chunk_s": 300, "overlap_s": 60, "top_n": 1, "quet_da_toc_do": True},
                    kiem_su_that={"do_dai_sau_atempo_s": round(len(nhanh) / SR, 4),
                                  "ly_thuyet_300_chia_1_02_s": round(300 / 1.02, 4)})


def tao_s8(d: str) -> dict:
    clip = CLIP_THEO_KICH_BAN["goc_S8.wav"]()
    ten = _kho(d, "goc_S8.wav", clip)
    v = _ghi_video(d, _chen(_giai_dieu(600, seed=1802, sr=SR), clip, 200))
    return _su_that("S8", "Clip NGẮN 60 s, sạch, dùng trọn ở P = 200 s của video 600 s.",
                    {"clip": 1801, "nen": 1802}, ten, 60, v, 600, [_doan(200, 0, 60)])


def tao_s9(d: str) -> dict:
    clip = CLIP_THEO_KICH_BAN["goc_S9.wav"]()
    ten = _kho(d, "goc_S9.wav", clip)
    v = _ghi_video(d, _chen(_giai_dieu(1100, seed=1902, sr=SR), clip, 400))
    return _su_that("S9", "Clip 420 s ở P = 400 s VẮT QUA ranh giới khúc: chunk_s = 300, overlap_s = 60 (kho không có "
                    "metadata thời lượng ⇒ gối thực tế 60 s, bước 240 s: khúc bắt đầu 0, 240, 480, 720, 960).",
                    {"clip": 1901, "nen": 1902}, ten, 420, v, 1100, [_doan(400, 0, 420)],
                    cau_hinh_engine_doi={"chunk_s": 300, "overlap_s": 60})


KICH_BAN = {"S0": tao_s0, "S1": tao_s1, "S2": tao_s2, "S3": tao_s3, "S4": tao_s4, "S4b": tao_s4b,
            "S5": tao_s5, "S5b": tao_s5b, "S6": tao_s6, "S6b": tao_s6b, "S7": tao_s7, "S7b": tao_s7b,
            "S7c": lambda d: tao_s7b(d, "S7c", 9101, 9102),      # đúng seed của test repo
            "S8": tao_s8, "S9": tao_s9}
