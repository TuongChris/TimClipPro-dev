# -*- coding: utf-8 -*-
"""Xác nhận qua ENGINE THẬT (audfprint thật, cấu hình mặc định, ncores 2, tinh_chinh_moc BẬT) hai ca SAI của do_bien.py.

  nhay_0_3        P1: video = clip[0, 60) + clip[60,3; 120) tại 40 s (nhảy 0,3 s, k thật = 1)
  de_truoc_tua_lui P2: tua lùi H1b + giọng nói đè 0 dB trên video [80, 100) (clip vẫn ở dưới lớp đè)
Audio dựng bằng chính hàm của tests/test_tinh_chinh_moc.py (11025 Hz), ghi WAV vào thư mục tạm; kho + data + out tạm,
xoá sau lượt. Một engine một lúc. Ghi ``<RA>\\engine_<ca>.json`` (dòng engine: neo, lõi, mốc; kết quả tinh chỉnh).
Chạy (Git Bash): cd /c/Dev/Tool_Quet/TimClipPro && PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang \\
  C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe -B -X utf8 \\
  ../tools/khop_tung_giay/san_pham/phan_bien/xac_nhan_engine_ma_test.py [nhay_0_3 de_truoc_tua_lui]
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import json  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "TimClipPro"))  # checkout chứa file này
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\phan_bien\ma_va_test"
sys.path[:0] = [MA, os.path.join(MA, "tests")]

import numpy as np  # noqa: E402

import test_tinh_chinh_moc as ttm  # noqa: E402
from conftest import _ghi_wav  # noqa: E402

SR = ttm.SR


def _ca(ten: str) -> tuple:
    if ten == "nhay_0_3":
        clip = ttm._am(120, 7301)
        video = ttm._chen(ttm._am(220, 7302), np.concatenate([ttm._cat(clip, 0, 60), ttm._cat(clip, 60.3, 120)]), 40.0)
        return clip, video, {"doan": [[40, 100, 0, 60], [100, 159.7, 60.3, 120]], "cho_cat": [[100, 100, 60, 60.3]]}
    clip = ttm._am(100, 7801)
    chen = np.concatenate([ttm._cat(clip, 0, 70), ttm._cat(clip, 58, 100)])
    video = ttm._de(ttm._chen(ttm._am(170, 7802), chen, 30.0), 80.0, 100.0, 0.0, 7803, chi_vung=(80.0, 100.0),
                    nguon=ttm._giong_noi)
    return clip, video, {"doan": [[30, 100, 0, 70], [100, 142, 58, 100]], "cho_cat": [[100, 100, 70, 58]]}


def chay(ten: str) -> dict:
    import engine as eng
    clip, video, that = _ca(ten)
    tam = tempfile.mkdtemp(prefix=f"p8_mt_{ten}_")
    try:
        kho = os.path.join(tam, "kho")
        os.makedirs(kho)
        _ghi_wav(os.path.join(kho, "clip_goc.wav"), clip, sr=SR)
        _ghi_wav(os.path.join(tam, "video.wav"), video, sr=SR)
        data, out = os.path.join(tam, "data"), os.path.join(tam, "out")
        os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = data, out
        e = eng.Engine(root=MA, data_dir=data, out_dir=out)
        e.config.ncores = 2
        e.config.tinh_chinh_moc = True
        e.config.validate()
        e.add_kho("Phan bien ma test", kho)
        kb = e.build_database(kho, "new")
        kq = e.scan_media(os.path.join(tam, "video.wav"))
        dong = [{"clip": m.clip, "start_s": m.start_s, "vung_khop_s": m.vung_khop_s, "end_s": m.end_s,
                 "he_so": m.he_so, "moc_mo_ho": m.moc_mo_ho, "neo": [list(a) for a in m.neo]} for m in kq.matches]
        return {"ca": ten, "dung_kho": kb, "status": kq.status, "note": kq.note, "that": that, "dong_engine": dong,
                "tinh_chinh": kq.tinh_chinh}
    finally:
        shutil.rmtree(tam, ignore_errors=True)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(RA, exist_ok=True)
    for ten in sys.argv[1:] or ["nhay_0_3", "de_truoc_tua_lui"]:
        r = chay(ten)
        with open(os.path.join(RA, f"engine_{ten}.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=1, default=str)
        print(ten, json.dumps({k: r[k] for k in ("status", "dong_engine", "tinh_chinh")}, ensure_ascii=False,
                              default=str)[:2500], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
