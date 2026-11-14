# -*- coding: utf-8 -*-
"""Dò BIÊN bước «tinh chỉnh mốc từng giây» (TimClipPro/tinh_chinh_moc.py, P-8) — phản biện mã + test, audio GIẢ LẬP.

Gọi thẳng ``tinh_chinh_dong`` như ``Engine._tinh_chinh_ket_qua`` (neo, lõi, phạm vi) với ``doc_pcm`` giả trong bộ nhớ
(mẫu dựng bằng chính hàm của tests/test_tinh_chinh_moc.py), trừ mục FFmpeg. Không dữ liệu thật, không mạng, không ghi
gì vào repo; file tạm trong thư mục tạm. Mỗi mục ghi: đầu vào, kỳ vọng, kết quả thật, kết luận.
  P1 nhảy/tua lùi NHỎ hơn 1 s (engine gộp chung MỘT neo vì NEO_GOP_S = 1 s)
  P2 tiếng đè ngay trước/sau chỗ tua lùi (dòng HAI neo)
  P3 clip TỰ có khoảng lặng dài, video dùng trọn clip
  P4 bất biến đầu ra trên đầu vào ngẫu nhiên (kiểu JSON thuần, xếp thứ tự, %)
  P6 chỗ nối khối FFmpeg với file nén (m4a, webm): độ lệch tua của từng lần gọi
Chạy (Git Bash, ~3 phút):
  cd /c/Dev/Tool_Quet/TimClipPro
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \\
      -B -X utf8 ../tools/khop_tung_giay/san_pham/phan_bien/do_bien.py [P1 P2 ...]
Kết quả: ``<RA>\\do_bien.json``.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile

MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "TimClipPro"))  # checkout chứa file này
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\phan_bien\ma_va_test"
sys.dont_write_bytecode = True
sys.path[:0] = [MA, os.path.join(MA, "tests")]

import numpy as np  # noqa: E402

import test_tinh_chinh_moc as ttm  # noqa: E402 — dùng lại cách dựng mẫu của bộ test (không chạy test)
import tinh_chinh_moc as tcm  # noqa: E402
from am_thanh_lap import doi_toc_do, nhac_co_nhip  # noqa: E402
from conftest import _ghi_wav, _giai_dieu  # noqa: E402

SR = tcm.SR


def _gon(kq: dict) -> dict:
    return {"trang_thai": kq["trang_thai"], "ly_do": kq["ly_do"],
            "doan": [[d["video_tu"], d["video_den"], d["clip_tu"], d["clip_den"], d["k"], d["tuong_dong_tb"],
                      d["tuong_dong_min"], d["cach_tim_mep"]] for d in kq["doan"]],
            "cho_cat": [[c["video_tu"], c["video_den"], c["clip_bo_tu"], c["clip_bo_den"]] for c in kq["cho_cat"]],
            "nguong_pct": kq["nguong_pct"], "nen_p99_pct": kq["nen_p99_pct"], "cham_gioi_han": kq["cham_gioi_han"]}


def p1_nhay_nho() -> list:
    """Video = clip[0, 60) rồi clip[60 + δ, 120) liền nhau tại P = 40 (δ < 0: lặp lại |δ| giây). Hai căn chỉnh lệch
    |δ| < NEO_GOP_S nên engine chỉ đưa MỘT neo (40, 1.0) — y như dưới đây."""
    ra = []
    for delta in (0.3, 0.45, -0.3, -0.45):
        clip, P, cat = ttm._am(120, 7301), 40.0, 60.0
        chen = np.concatenate([ttm._cat(clip, 0, cat), ttm._cat(clip, cat + delta, 120)])
        video = ttm._chen(ttm._am(220, 7302), chen, P)
        kq = ttm._chay(clip, video, [(P, 1.0)], P + 3.0, P + len(chen) / SR - 3.0)
        sai = kq["trang_thai"] == tcm.DA and (len(kq["doan"]) == 1 or any(abs(d["k"] - 1.0) > 1e-3 for d in kq["doan"]))
        ra.append({"delta_s": delta, "that": {"doan": [[P, P + cat, 0, cat], [P + cat, P + len(chen) / SR, cat + delta,
                                                                              120]],
                                              "cho_cat": [[P + cat, P + cat, cat, cat + delta]], "k": 1.0},
                   "ky_vong": "2 đoạn k = 1 + 1 chỗ cắt dài 0 (clip nhảy δ), hoặc CHUA",
                   "kq": _gon(kq), "ket_luan": "SAI: một đoạn, k giả, mất chỗ nhảy" if sai else "đạt"})
    return ra


def p2_de_quanh_tua_lui() -> list:
    """Tua lùi H1b (video [30, 100) = clip[0, 70), [100, 142) = clip[58, 100); neo (30, 1), (42, 1)) + giọng nói đè
    0 dB ngay TRƯỚC hoặc ngay SAU chỗ tua lùi. Clip vẫn ở dưới lớp đè (luật A03 của module), ranh giới thật ở 100 s
    không có khe video."""
    ra = []
    clip = ttm._am(100, 7801)
    chen = np.concatenate([ttm._cat(clip, 0, 70), ttm._cat(clip, 58, 100)])
    for nguon, ten in ((ttm._giong_noi, "giong_noi"), (nhac_co_nhip, "nhac")):
        for snr in (0.0, -6.0):
            for de in ((80.0, 100.0), (88.0, 100.0), (100.0, 120.0)):
                video = ttm._de(ttm._chen(ttm._am(170, 7802), chen, 30.0), de[0], de[1], snr, 7803, chi_vung=de,
                                nguon=nguon)
                kq = ttm._chay(clip, video, [(30.0, 1.0), (42.0, 1.0)], 33.0, 139.0)
                bia = [c for c in kq["cho_cat"] if c["video_den"] - c["video_tu"] > 1.0]
                sai = kq["trang_thai"] == tcm.DA and bool(bia)
                ra.append({"tieng_de": ten, "snr_db": snr, "de_video": list(de),
                           "that": {"doan": [[30, 100, 0, 70], [100, 142, 58, 100]], "cho_cat": [[100, 100, 70, 58]]},
                           "ky_vong": "không có chỗ cắt nào có khe video > 1 s (ranh giới thật dài 0 ở 100 s), hoặc CHUA",
                           "kq": _gon(kq), "ket_luan": "SAI: chỗ cắt bịa trong vùng bị đè" if sai else "đạt"})
    return ra


def p3_clip_tu_im_lang() -> list:
    """Clip TỰ im lặng tuyệt đối D giây ở 50,4 s (nghỉ giữa bài), video dùng nguyên clip tại 40 s."""
    ra = []
    for D in (8.0, 9.0, 12.0):
        clip, P = ttm._im(ttm._am(120, 9401), 50.4, 50.4 + D), 40.0
        video = ttm._chen(ttm._am(220, 9402), clip, P)
        kq = ttm._chay(clip, video, [(P, 1.0)], P + 6.0, P + 114.0)
        ra.append({"im_lang_s": D, "ky_vong": "DA một đoạn [40, 160] ↔ [0, 120], không chỗ cắt",
                   "kq": _gon(kq), "ket_luan": "đạt" if kq["trang_thai"] == tcm.DA and len(kq["doan"]) == 1 else
                   ("CHUA (bảo thủ, không sai)" if kq["trang_thai"] == tcm.CHUA else "SAI")})
    return ra


def _vi_pham(kq: dict) -> list:
    loi = []

    def kieu(x, duong):
        if isinstance(x, dict):
            for k, v in x.items():
                kieu(v, f"{duong}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                kieu(v, f"{duong}[{i}]")
        elif type(x) not in (str, int, float, bool) or (isinstance(x, float) and not math.isfinite(x)):
            loi.append(f"{duong}: {type(x).__name__} {x!r}")
    kieu(kq, "kq")
    d = kq["doan"]
    if kq["trang_thai"] == tcm.DA:
        if not d or len(kq["cho_cat"]) != len(d) - 1:
            loi.append("số đoạn / chỗ cắt")
        if [x["video_tu"] for x in d] != sorted(x["video_tu"] for x in d):
            loi.append("doan không xếp theo video_tu")
        if any(x["video_den"] < x["video_tu"] or not 0 <= x["tuong_dong_min"] <= x["tuong_dong_tb"] <= 100 for x in d):
            loi.append("đoạn ngược hoặc % ngoài 0–100")
        if [p[0] for p in kq["ho_so"]] != sorted(p[0] for p in kq["ho_so"]):
            loi.append("ho_so không xếp")
    elif not kq["ly_do"]:
        loi.append("CHUA không có lý do")
    return loi


def p4_bat_bien(so_lan: int = 40) -> dict:
    """Đầu vào ngẫu nhiên (tất định theo seed): giai điệu/nhạc có nhịp, tốc độ 0,97–1,02, neo lệch ~0,15 s, đôi khi
    neo thứ hai, lõi ngắn/sai, phạm vi cắt — đếm ngoại lệ và vi phạm bất biến đầu ra."""
    rng = np.random.default_rng(20261114)
    ngoai_le, vi_pham, dem = [], [], {tcm.DA: 0, tcm.CHUA: 0}
    for lan in range(so_lan):
        dai = float(rng.choice([20, 45, 90]))
        clip = (ttm._am(dai, 100 + lan) if rng.random() < 0.5 else nhac_co_nhip(dai, seed=100 + lan, sr=SR)).astype(
            np.float32)
        dai_v = dai + float(rng.uniform(10, 120))
        P = float(rng.uniform(-dai * 0.5, dai_v - dai * 0.5))
        toc = float(rng.choice([1.0, 1.0, 1.02, 0.97]))
        phan = clip if toc == 1.0 else doi_toc_do(clip, 1.0 / toc).astype(np.float32)
        video = ttm._am(dai_v, 900 + lan)
        i0 = int(round(P * SR))
        a, b = max(i0, 0), min(i0 + len(phan), len(video))
        if b > a:
            video[a:b] = phan[a - i0: b - i0]
        neo = [(P + float(rng.normal(0, 0.15)), (1.0 / toc) * float(rng.choice([1.0, 1.004])))]
        if rng.random() < 0.3:
            neo.append((neo[0][0] + float(rng.choice([-12.0, 7.3, 19.1, 3.0])), neo[0][1]))
        v0 = max(P, 0.0) + float(rng.uniform(0, 3))
        v1 = min(P + len(phan) / SR, dai_v) - float(rng.uniform(0, 3))
        pv = None if rng.random() < 0.5 else (0.0, float(rng.uniform(v1 - 5, dai_v + 5)))
        try:
            kq = ttm._chay(clip, video, neo, v0, v1, pham_vi_s=pv)
            json.dumps(kq, allow_nan=False)
            dem[kq["trang_thai"]] += 1
            if _vi_pham(kq):
                vi_pham.append({"lan": lan, "loi": _vi_pham(kq)})
        except Exception as e:  # noqa: BLE001 — ghi lại, không dừng
            ngoai_le.append({"lan": lan, "loi": repr(e)[:300]})
    return {"so_lan": so_lan, "dem": dem, "ngoai_le": ngoai_le, "vi_pham": vi_pham}


def p6_noi_khoi_ffmpeg(thu_muc: str) -> dict:
    """Cùng file, giải mã [13,37; 380) một khối vs khối 97,3 s; và độ lệch (mẫu 11025 Hz) của từng lần tua so với WAV
    gốc (tương quan chéo). Module coi các khối liền nhau từng mẫu."""
    sig = _giai_dieu(400, seed=4242)
    wav = os.path.join(thu_muc, "x.wav")
    _ghi_wav(wav, sig)
    ref, _ = tcm._doc_pcm_ffmpeg(wav, 0.0, 400.0)
    ra = {}
    for duoi, ma in (("opus", ["-c:a", "libopus", "-b:a", "64k"]), ("mp3", ["-c:a", "libmp3lame", "-b:a", "128k"]),
                     ("m4a", ["-c:a", "aac", "-b:a", "128k"]), ("webm", ["-c:a", "libopus", "-b:a", "64k"])):
        p = os.path.join(thu_muc, "x." + duoi)
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", wav, *ma, p], check=True)
        lech = {}
        for tu in (13.37, 110.67, 207.97, 305.27):
            x, t = tcm._doc_pcm_ffmpeg(p, tu, 5.0)
            a = x[1103: 1103 + 2 * SR].astype(np.float64)
            i0 = int(round(t * SR)) + 1103
            L = max(range(-2000, 2001), key=lambda L: float(np.dot(a, ref[i0 + L: i0 + L + len(a)])))
            b = ref[i0 + L: i0 + L + len(a)]
            # [độ lệch mẫu, tương quan chuẩn hoá ở đỉnh] — tương quan < 0,95: đỉnh không tin được, bỏ
            lech[f"{tu:g}"] = [L, round(float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)), 3)]
        cu = tcm.KHOI_GIAI_MA_S
        try:
            tcm.KHOI_GIAI_MA_S = 1000.0
            mot = tcm._dac_trung(tcm._doc_pcm_ffmpeg, p, 13.37, 380.0, lambda: None)
            tcm.KHOI_GIAI_MA_S = 97.3
            nhieu = tcm._dac_trung(tcm._doc_pcm_ffmpeg, p, 13.37, 380.0, lambda: None)
        finally:
            tcm.KHOI_GIAI_MA_S = cu
        n = min(len(mot.X), len(nhieu.X))
        d = np.abs(mot.X[:n] - nhieu.X[:n]).max(axis=1)
        ra[duoi] = {"lech_tua_mau": lech, "khung_lech_hon_5dB": int((d > 0.5).sum()), "tong_khung": n}
    return ra


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(RA, exist_ok=True)
    chon = set(sys.argv[1:])
    p_ra = os.path.join(RA, "do_bien.json")
    ra = {}
    if chon and os.path.exists(p_ra):                   # chạy một phần: giữ kết quả các mục khác
        with open(p_ra, encoding="utf-8") as f:
            ra = json.load(f)
    with tempfile.TemporaryDirectory(prefix="p8_do_bien_") as tam:
        for ten, f in (("P1", p1_nhay_nho), ("P2", p2_de_quanh_tua_lui), ("P3", p3_clip_tu_im_lang),
                       ("P4", p4_bat_bien), ("P6", lambda: p6_noi_khoi_ffmpeg(tam))):
            if chon and ten not in chon:
                continue
            ra[ten] = f()
            print(ten, json.dumps(ra[ten], ensure_ascii=False)[:1500], flush=True)
    with open(p_ra, "w", encoding="utf-8") as f:
        json.dump(ra, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
