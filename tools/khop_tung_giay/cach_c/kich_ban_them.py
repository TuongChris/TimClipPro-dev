# -*- coding: utf-8 -*-
"""Ba kịch bản THÊM cho Cách C — chỗ bộ thử 15 kịch bản còn thiếu (14/11/2026). Audio 100% giả lập (bộ sinh của repo).

  X1  dùng MỘT PHẦN clip (mép lẻ, giữa nốt) + nhạc có nhịp đè 0 dB suốt video  → mép giữa clip dưới nhạc đè
  X2  dùng một phần clip, mép lẻ, rồi -6 dB + nén Opus 32 kbps                 → mép lẻ + nén lại
  X3  clip nhạc có nhịp (= goc_S6) dùng một phần, NỀN cũng là nhạc có nhịp 113 BPM → nền tự giống clip
Chạy engine THẬT + audfprint THẬT qua ``chay_bo_thu.chay_mot`` của bước trước (import, KHÔNG sửa file đó): đổi
``KET_QUA`` sang thư mục riêng và thêm kịch bản vào ``kich_ban.KICH_BAN`` ngay trong bộ nhớ. ncores 2, lần lượt.
  cd /c/Dev/pc2_test_tools/khop_tung_giay/cach_c
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \
      -B -X utf8 kich_ban_them.py X1 [X2 X3]
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bo_thu"))

import numpy as np  # noqa: E402

import chay_bo_thu as cb  # noqa: E402  (kiểm môi trường + bọc Engine trong tiến trình, như bước trước)
import kich_ban as kb  # noqa: E402

THEM = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_c\them"


def tao_x1(d: str) -> dict:
    clip = kb.CLIP_THEO_KICH_BAN["goc_S3.wav"]()                # 540 s, seed 1301
    ten = kb._kho(d, "goc_X1.wav", clip)
    c_tu, c_den, P = 60.37, 480.81, 300.53
    doan = clip[kb._i(c_tu):kb._i(c_den)]
    video = kb._chen(kb._giai_dieu(1000, seed=1302, sr=kb.SR), doan, P)
    de = kb.nhac_co_nhip(1000, seed=1503)
    vung = slice(kb._i(P), kb._i(P) + len(doan))
    de = de * (kb._rms(doan) / kb._rms(de[vung]))               # SNR 0 dB trong vùng clip
    tron = video + de
    tron = tron * (0.95 / np.abs(tron).max())
    v = kb._ghi_video(d, tron)
    return kb._su_that("X1", "(Cách C thêm) clip[60,37..480,81] của clip 540 s chèn ở P = 300,53 s (mép giữa nốt), "
                       "nhạc có nhịp đè SNR 0 dB suốt video 1000 s.", {"clip": 1301, "nen": 1302, "nhac_de": 1503},
                       ten, 540, v, 1000, [kb._doan(P, c_tu, c_den)],
                       kiem_su_that={"snr_do_lai_db": round(20 * np.log10(kb._rms(doan) / kb._rms(de[vung])), 3)})


def tao_x2(d: str) -> dict:
    clip = kb._giai_dieu(480, seed=2201, sr=kb.SR)
    ten = kb._kho(d, "goc_X2.wav", clip)
    c_tu, c_den, P = 37.37, 311.81, 123.45
    goc = kb._chen(kb._giai_dieu(800, seed=2202, sr=kb.SR), clip[kb._i(c_tu):kb._i(c_den)], P)
    tam = os.path.join(d, "_video_truoc_nen.wav")
    kb._ghi_wav(tam, goc, kb.SR)
    v = "video_vi_pham.opus"
    kb._ffmpeg("-i", tam, "-af", "volume=-6dB", "-ac", "1", "-c:a", "libopus", "-b:a", "32k", os.path.join(d, v))
    giai = os.path.join(d, "_video_giai_lai.wav")
    kb._ffmpeg("-i", os.path.join(d, v), "-ac", "1", "-ar", str(kb.SR), giai)
    sau = kb._doc_wav(giai)
    kiem = {"do_dai_giai_lai_s": round(len(sau) / kb.SR, 4),
            "lech_mau_quanh_P_s": kb._do_lech_mau(goc, sau, P - 5.0),
            "lech_mau_quanh_cuoi_s": kb._do_lech_mau(goc, sau, P + (c_den - c_tu) - 15.0)}
    os.remove(tam)
    os.remove(giai)
    return kb._su_that("X2", "(Cách C thêm) clip[37,37..311,81] của clip 480 s chèn ở P = 123,45 s (mép lẻ) trong video "
                       "800 s, rồi -6 dB + nén Opus 32 kbps mono.", {"clip": 2201, "nen": 2202}, ten, 480, v, 800,
                       [kb._doan(P, c_tu, c_den)], kiem_su_that=kiem)


def tao_x3(d: str) -> dict:
    clip = kb.CLIP_THEO_KICH_BAN["goc_S6.wav"]()                # nhạc có nhịp 113 BPM, 360 s, seed 1601
    ten = kb._kho(d, "goc_X3.wav", clip)
    c_tu, c_den, P = 60.5, 300.25, 200.7
    v = kb._ghi_video(d, kb._chen(kb.nhac_co_nhip(800, seed=2302), clip[kb._i(c_tu):kb._i(c_den)], P))
    return kb._su_that("X3", "(Cách C thêm) clip nhạc có nhịp (= goc_S6) dùng clip[60,5..300,25] ở P = 200,7 s; NỀN "
                       "video 800 s cũng là nhạc có nhịp 113 BPM (seed khác, cùng mẫu kick).",
                       {"clip": 1601, "nen_nhac_co_nhip": 2302}, ten, 360, v, 800, [kb._doan(P, c_tu, c_den)])


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    them = {"X1": tao_x1, "X2": tao_x2, "X3": tao_x3}
    kb.KICH_BAN.update(them)            # chỉ trong bộ nhớ của tiến trình này
    cb.KET_QUA = THEM                   # chay_mot ghi vào thư mục riêng của Cách C, không đụng bo_thu
    os.makedirs(THEM, exist_ok=True)
    for ten in sys.argv[1:] or list(them):
        s = cb.chay_mot(ten)
        print(f"[{ten}] tìm thấy={s['tim_thay']} dòng={s['so_dong']} đầu clip={s['sai_so_dau_clip_s']} "
              f"đầu vùng={s['sai_so_dau_vung_s']} cuối={s['sai_so_cuoi_s']} P={s['precision_giay']} "
              f"R={s['recall_giay']} bị loại={s['so_dong_bi_loai_cua_clip']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
