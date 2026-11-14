# -*- coding: utf-8 -*-
"""Tái hiện TỐI THIỂU (không FFmpeg, ~1 s) lỗi lặp vô hạn ở cuối file của tinh_chinh_moc._dac_trung (phản biện hiệu
năng P-8, 14/11/2026). Mẫu cho test đỏ: cùng ``_doc_gia`` của tests/test_tinh_chinh_moc.py.

Video 150 s, clip 60 s dùng trọn ở giây 85 (hết 5 s trước cuối video); pham_vi_s = (0, 150,007) — thời lượng KHAI BÁO
dài hơn âm thanh giải mã được 7 ms, đúng như mọi file opus (pre-skip 312 mẫu / 48 kHz = 6,5 ms) và MP4 có luồng hình
dài hơn tiếng dưới một khung (engine truyền pham_vi = (0, duration_of) khi do_dai_am_thanh < duration_of). Khối cuối
xin 0,007 s, bộ đọc trả 0 mẫu, ``len(x) < (dai − 0,05)·SR`` có vế phải ÂM nên ``het`` không bật, vị trí không tiến.
Chạy: cd TimClipPro && PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B -X utf8 \\
      ../tools/khop_tung_giay/san_pham/phan_bien/eof_tai_hien.py
"""
from __future__ import annotations

import os
import sys
import time

sys.dont_write_bytecode = True
MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "TimClipPro"))  # checkout chứa file này
sys.path[:0] = [MA, os.path.join(MA, "tests")]

import numpy as np  # noqa: E402

import tinh_chinh_moc as tcm  # noqa: E402
from conftest import _giai_dieu  # noqa: E402

SR = tcm.SR


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    clip = _giai_dieu(60, seed=9901, sr=SR).astype(np.float32)
    video = _giai_dieu(150, seed=9902, sr=SR).astype(np.float32)
    P = 85.0
    video[int(P * SR): int(P * SR) + len(clip)] = clip
    tin_hieu, goi = {"clip": clip, "video": video}, []

    def doc(duong, tu_s, dai_s):
        goi.append((duong, round(tu_s, 4), round(dai_s, 4)))
        i0 = int(round(tu_s * SR))
        return tin_hieu[duong][i0: i0 + int(round(dai_s * SR))], i0 / SR

    for pham_vi in ((0.0, 150.0), (0.0, 150.007)):
        goi.clear()
        t = time.monotonic()
        kq = tcm.tinh_chinh_dong("clip", "video", [(P, 1.0)], P + 3.0, P + 57.0, pham_vi_s=pham_vi, doc_pcm=doc,
                                 han_chot=t + 5.0)
        lap = [g for g in goi if g[0] == "video" and g[2] < 0.05]
        print(f"pham_vi {pham_vi}: {kq['trang_thai']} «{kq['ly_do']}» sau {time.monotonic() - t:.2f} s, "
              f"{len(goi)} lần đọc ({len(lap)} lần xin < 0,05 s, vd {lap[:1]}), đoạn "
              f"{[(d['video_tu'], d['video_den']) for d in kq['doan']]}")


if __name__ == "__main__":
    main()
