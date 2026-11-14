# -*- coding: utf-8 -*-
"""Xác nhận ca đối kháng bằng ENGINE THẬT (audfprint + FFmpeg, ``ncores = 2``, chặn mạng) — neo và lõi do engine tự
tính, không dựng tay. Audio = đúng tín hiệu của ``ca_doi_khang.py`` (ghi WAV 11025 Hz vào thư mục TẠM: kho 1 clip +
video). ``config.tinh_chinh_moc = True`` → đọc ``kq.tinh_chinh`` (engine tự gọi tinh_chinh_moc) và chấm bằng ``cham``
của ``ca_doi_khang`` với sự thật của ca. Một engine một lúc. Không đụng dữ liệu thật, không mạng.

Chạy (Git Bash):
  cd /c/Dev/Tool_Quet/TimClipPro
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \\
      -B -X utf8 ../tools/khop_tung_giay/san_pham/phan_bien/chay_engine_doi_khang.py N21 N22 ...
Ghi ``<RA>\\engine_<ca>.json``.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import json  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ca_doi_khang as h  # noqa: E402  (đặt sẵn sys.path tới TimClipPro + tests)


def chay(ma: str) -> dict:
    import engine as eng
    tam = tempfile.mkdtemp(prefix=f"p8_pb_{ma}_")
    try:
        kho = os.path.join(tam, "kho")
        os.makedirs(kho)
        if h.CA[ma].__code__.co_argcount:          # ca đường FFmpeg: file đã dựng sẵn (định dạng thật)
            os.makedirs(os.path.join(tam, "nguon"))
            c = h.CA[ma](os.path.join(tam, "nguon"))
            shutil.copy2(c["clip"], os.path.join(kho, f"goc_{ma}{os.path.splitext(c['clip'])[1]}"))
            video = c["video"]
        else:
            c = h.CA[ma]()
            h._ghi_wav(os.path.join(kho, f"goc_{ma}.wav"), c["clip"], sr=h.SR)
            video = os.path.join(tam, f"video_{ma}.wav")
            h._ghi_wav(video, c["video"], sr=h.SR)
        data, out = os.path.join(tam, "data"), os.path.join(tam, "out")
        os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = data, out
        e = eng.Engine(root=h.MA, data_dir=data, out_dir=out)
        assert os.path.normcase(e.data_dir) == os.path.normcase(os.path.abspath(data)), e.data_dir
        e.config.ncores = 2
        e.config.tinh_chinh_moc = True
        e.config.validate()
        e.add_kho(f"Phan bien {ma}", kho)
        kb = e.build_database(kho, "new")
        if kb.get("thanh_cong") != 1:
            raise RuntimeError(f"Dựng kho không trọn: {kb}")
        t = time.perf_counter()
        kq = e.scan_media(video)
        t_quet = time.perf_counter() - t
        if kq.status != "ok":
            raise RuntimeError(f"Quét lỗi: {kq.note}")
        dong = []
        for m, tc in zip(kq.matches, kq.tinh_chinh or [None] * len(kq.matches)):
            x = {"clip": m.clip, "start_s": m.start_s, "vung_khop_s": m.vung_khop_s, "end_s": m.end_s,
                 "clip_offset_s": m.clip_offset_s, "hashes": m.hashes, "confidence": m.confidence,
                 "he_so": m.he_so, "ho": m.ho, "neo": [list(n) for n in m.neo], "moc_mo_ho": m.moc_mo_ho,
                 "tinh_chinh": tc}
            if tc and "doan" in tc:
                x["cham"] = h.cham(tc, c)
            dong.append(x)
        return {"ma": ma, "mo_ta": (h.CA[ma].__doc__ or "").strip(), "su_that": c["su_that"],
                "duration_s": kq.duration_s, "pham_vi_quet_s": kq.pham_vi_quet_s, "thoi_gian_quet_s": round(t_quet, 1),
                "dong": dong}
    finally:
        shutil.rmtree(tam, ignore_errors=True)


def main() -> int:
    for ma in sys.argv[1:]:
        r = chay(ma)
        with open(os.path.join(h.RA, f"engine_{ma}.json"), "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
        print(f"== {ma}: {len(r['dong'])} dòng engine, quét {r['thoi_gian_quet_s']} s", flush=True)
        for x in r["dong"]:
            tc = x["tinh_chinh"] or {}
            print(f"   engine: start {x['start_s']:.2f} lõi [{x['vung_khop_s']:.2f}, {x['end_s']:.2f}] neo {x['neo']} "
                  f"k {x['he_so']} hash {x['hashes']} mơ hồ {x['moc_mo_ho']}")
            if tc.get("trang_thai") == h.tcm.DA:
                print("   tinh chỉnh ĐÃ:", "; ".join(
                    f"[{d['video_tu']:.3f},{d['video_den']:.3f}]←clip[{d['clip_tu']:.3f},{d['clip_den']:.3f}] "
                    f"{d['cach_tim_mep'][0]}/{d['cach_tim_mep'][1]} min{d['tuong_dong_min']}" for d in tc["doan"]),
                    "| cắt", [(c_["video_tu"], c_["video_den"], c_["clip_bo_tu"], c_["clip_bo_den"])
                              for c_ in tc["cho_cat"]], "| chạm", tc["cham_gioi_han"])
                ch = x["cham"]
                print(f"   chấm: {ch['ket_luan']} bịa {ch['bia_s']} sai ánh xạ {ch['sai_anh_xa_s']} hụt {ch['hut_s']}"
                      f" mép {ch['mep']}")
            else:
                print(f"   tinh chỉnh CHƯA: «{tc.get('ly_do')}»")
    return 0


if __name__ == "__main__":
    sys.exit(main())
