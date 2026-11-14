# -*- coding: utf-8 -*-
"""Phản biện đo lường — CA KHÓ cho cách tinh chỉnh tốt nhất (Cách C, tuong_dong.py), engine THẬT + audfprint THẬT.

Audio 100 % giả lập từ bộ sinh của repo (kich_ban.py → tests/conftest.py, tests/am_thanh_lap.py). Engine chạy qua
``chay_bo_thu.chay_mot`` (import, không sửa; KET_QUA đổi sang thư mục của tôi; ncores 2; lần lượt). Cách C chạy qua
``chay_cach_c.kich_ban`` (BO_THU đổi sang thư mục của tôi). Chấm bằng ``cham_doc_lap`` (lưới 1 ms, không danh_gia.py).

  H1a  clip 240 s dùng HAI lần, cách xa nhau (150 s và 700 s)
  H1b  clip 300 s phát tới giây 200 rồi TUA LÙI 15 s phát lại tới hết (kiểu video reaction «xem lại đoạn này»):
       hai lần dùng ở hai căn chỉnh lệch 15 s < dedup_s 20 s; phần phát lại 115 s (ít hơn nửa)
  H1c  như H1b nhưng tua lùi ở giây 150: phần phát lại 165 s (nhiều hơn nửa)
  H2a  âm thanh lặp: clip = 60 s nhạc + 200 s vòng 8 ô nhịp lặp Y HỆT (chu kỳ ≈ 17 s) + 60 s nhạc; video chỉ dùng
       clip[100..220] (nằm trọn trong vòng lặp) → giây clip KHÔNG xác định duy nhất (±k·chu kỳ), mép video thì có
  H2b  như H2a nhưng dùng clip[55..215]: 5 s nhạc duy nhất + 155 s vòng lặp → căn chỉnh thật chỉ hơn «bóng» ~3 %
  H3   clip 360 s dùng trọn, nhạc có nhịp ĐÈ 0 dB CHỈ trong 120 s giữa (giây clip 120–240; kiểu bình luận/nhạc nền to
       giữa chừng) — cùng SNR với S5 mà Cách C đã qua, nhưng chỉ một phần
  H4   clip 300 s bị cắt SÁT MÉP: dùng clip[0,6..299,0] (bỏ 0,6 s đầu, 1,0 s cuối — mép giữa nốt) → thử luật «mép
       trùng đầu/cuối clip thì lấy đầu/cuối clip»
  cd /c/Dev/pc2_test_tools/khop_tung_giay/phan_bien_do_luong
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B -X utf8 ca_kho.py [H1a H1b ...] [--chi-cach-c]
"""
from __future__ import annotations

import json
import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
GOC_CC = r"C:\Dev\pc2_test_tools\khop_tung_giay"
sys.path.insert(0, os.path.join(GOC_CC, "bo_thu"))
sys.path.insert(0, os.path.join(GOC_CC, "cach_c"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import chay_bo_thu as cb  # noqa: E402  (kiểm môi trường chặn mạng + bọc Engine trong tiến trình)
import chay_cach_c as cc  # noqa: E402
import cham_doc_lap as ch  # noqa: E402
import kich_ban as kb  # noqa: E402
import su_that_doc_lap as sd  # noqa: E402
import tuong_dong as td  # noqa: E402

RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_do_luong\ca_kho"
SR = kb.SR


def tao_h1a(d: str) -> dict:
    clip = kb._giai_dieu(240, seed=3101, sr=SR)
    ten = kb._kho(d, "goc_H1a.wav", clip)
    v = kb._chen(kb._chen(kb._giai_dieu(1100, seed=3102, sr=SR), clip, 150), clip, 700)
    return kb._su_that("H1a", "(Phản biện) clip 240 s dùng TRỌN hai lần ở 150 s và 700 s của video 1100 s.",
                       {"clip": 3101, "nen": 3102}, ten, 240, kb._ghi_video(d, v), 1100,
                       [kb._doan(150, 0, 240), kb._doan(700, 0, 240)])


def _tao_tua_lui(d: str, ten_kb: str, cat_s: float) -> dict:
    """Phát clip[0..cat_s] ở 300 s rồi TUA LÙI 15 s, phát lại clip[cat_s−15..300] liền sau."""
    clip = kb._giai_dieu(300, seed=3201, sr=SR)
    ten = kb._kho(d, f"goc_{ten_kb}.wav", clip)
    chen = np.concatenate([clip[:kb._i(cat_s)], clip[kb._i(cat_s - 15):]])
    v = kb._chen(kb._giai_dieu(1000, seed=3202, sr=SR), chen, 300)
    return kb._su_that(ten_kb, f"(Phản biện) clip 300 s phát clip[0..{cat_s:g}] ở 300 s rồi TUA LÙI 15 s phát lại "
                       f"clip[{cat_s - 15:g}..300] liền sau ({300 + cat_s:g} s) — hai căn chỉnh 300 và 315 lệch 15 s < "
                       "dedup_s 20 s.", {"clip": 3201, "nen": 3202}, ten, 300, kb._ghi_video(d, v), 1000,
                       [kb._doan(300, 0, cat_s), kb._doan(300 + cat_s, cat_s - 15, 300)])


def tao_h1b(d: str) -> dict:          # phần phát lại NGẮN hơn nửa (115 s / 315 s)
    return _tao_tua_lui(d, "H1b", 200.0)


def tao_h1c(d: str) -> dict:          # phần phát lại DÀI hơn nửa (165 s / 315 s)
    return _tao_tua_lui(d, "H1c", 150.0)


def _clip_h2() -> tuple:
    lap, chu_ky = kb.vong_lap_y_het(200, seed=3302)
    return np.concatenate([kb.nhac_co_nhip(60, seed=3301), lap, kb.nhac_co_nhip(60, seed=3303)]), chu_ky


def tao_h2a(d: str) -> dict:
    clip, T = _clip_h2()
    ten = kb._kho(d, "goc_H2.wav", clip)
    v = kb._chen(kb._giai_dieu(900, seed=3304, sr=SR), clip[kb._i(100):kb._i(220)], 300)
    return kb._su_that("H2a", "(Phản biện) clip 320 s = 60 s nhạc có nhịp + 200 s vòng 8 ô nhịp lặp Y HỆT (chu kỳ "
                       f"{T:.3f} s, giây clip 60–260) + 60 s nhạc; video 900 s chỉ dùng clip[100..220] (trọn trong vòng "
                       "lặp) ở 300 s → giây clip đúng chỉ xác định tới ±k·chu kỳ.",
                       {"nhac_dau": 3301, "vong_lap": 3302, "nhac_cuoi": 3303, "nen": 3304}, ten, 320,
                       kb._ghi_video(d, v), 900, [kb._doan(300, 100, 220)], chu_ky_vong_lap_s=round(T, 6),
                       vung_lap_trong_clip=[60.0, 260.0])


def tao_h2b(d: str) -> dict:
    clip, T = _clip_h2()
    ten = kb._kho(d, "goc_H2.wav", clip)
    v = kb._chen(kb._giai_dieu(900, seed=3305, sr=SR), clip[kb._i(55):kb._i(215)], 300)
    return kb._su_that("H2b", "(Phản biện) cùng clip H2a; video dùng clip[55..215] = 5 s nhạc duy nhất + 155 s vòng lặp, "
                       "ở 300 s → căn chỉnh thật chỉ nhiều bằng chứng hơn «bóng» +1 chu kỳ khoảng 3 %.",
                       {"nhac_dau": 3301, "vong_lap": 3302, "nhac_cuoi": 3303, "nen": 3305}, ten, 320,
                       kb._ghi_video(d, v), 900, [kb._doan(300, 55, 215)], chu_ky_vong_lap_s=round(T, 6),
                       vung_lap_trong_clip=[60.0, 260.0])


def tao_h3(d: str) -> dict:
    clip = kb._giai_dieu(360, seed=3401, sr=SR)
    ten = kb._kho(d, "goc_H3.wav", clip)
    video = kb._chen(kb._giai_dieu(1000, seed=3402, sr=SR), clip, 300)
    de = kb.nhac_co_nhip(1000, seed=3403)
    vung = slice(kb._i(420), kb._i(540))
    mat_na = np.zeros(len(video))
    mat_na[vung] = 1.0
    de = de * mat_na * (kb._rms(clip[kb._i(120):kb._i(240)]) / kb._rms(de[vung]))
    tron = video + de
    tron = tron * (0.95 / np.abs(tron).max())
    snr = 20 * np.log10(kb._rms(clip[kb._i(120):kb._i(240)]) / kb._rms(de[vung]))
    return kb._su_that("H3", "(Phản biện) clip 360 s dùng trọn ở 300 s (video 1000 s); nhạc có nhịp ĐÈ SNR 0 dB CHỈ trong "
                       "video 420–540 s (giây clip 120–240), hai phần còn lại sạch.",
                       {"clip": 3401, "nen": 3402, "nhac_de": 3403}, ten, 360, kb._ghi_video(d, tron), 1000,
                       [kb._doan(300, 0, 360)], kiem_su_that={"snr_vung_de_db": round(float(snr), 3)},
                       vung_de_video=[420.0, 540.0])


def tao_h4(d: str) -> dict:
    clip = kb._giai_dieu(300, seed=3501, sr=SR)
    ten = kb._kho(d, "goc_H4.wav", clip)
    v = kb._chen(kb._giai_dieu(1000, seed=3502, sr=SR), clip[kb._i(0.6):kb._i(299.0)], 400)
    return kb._su_that("H4", "(Phản biện) clip 300 s; video dùng clip[0,6..299,0] (bỏ 0,6 s đầu và 1,0 s cuối, mép giữa "
                       "nốt) ở 400 s của video 1000 s.", {"clip": 3501, "nen": 3502}, ten, 300, kb._ghi_video(d, v),
                       1000, [kb._doan(400, 0.6, 299.0)])


CA = {"H1a": tao_h1a, "H1b": tao_h1b, "H1c": tao_h1c, "H2a": tao_h2a, "H2b": tao_h2b, "H3": tao_h3, "H4": tao_h4}
TRUONG = ("start_s", "vung_khop_s", "end_s", "matched_s", "clip_offset_s", "hashes", "ty_le", "confidence",
          "moc_mo_ho", "moc_thay_the", "ty_so_doi_thu")


def _json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def cham_ca(S: str, kq_c: dict) -> dict:
    d = os.path.join(RA, S)
    st, ke = _json(os.path.join(d, "su_that.json")), _json(os.path.join(d, "ket_qua_engine.json"))
    dur = float(ke["duration_s"])
    that = sorted(st["doan"], key=lambda x: x["video_tu"])
    tk = [(x["video_tu"], x["video_den"]) for x in that]
    dong = ke["dong_cho_clip"]["matches"]
    ra = {"su_that": that,
          "engine": {"so_dong": len(dong), "dong": [{k: m.get(k) for k in TRUONG} for m in dong],
                     "dong_bi_loai": [{k: m.get(k) for k in TRUONG} for m in ke["dong_cho_clip"]["matches_loai"]],
                     "pr_start_end": ch.pr([(m["start_s"], m["end_s"]) for m in dong], tk, dur),
                     "pr_vung_end": ch.pr([(m["vung_khop_s"], m["end_s"]) for m in dong], tk, dur),
                     "bao_cao_v2": [[x["giay_bat_dau"], x["giay_ket_thuc"]] for x in ke["bao_cao_v2_doan"]],
                     "thoi_gian_quet_s": ke["thoi_gian_quet_s"],
                     "so_nhom_sau_merge_cua_clip": sum(1 for g in ke["merge_cuoi"]["tat_ca_nhom_sau_merge"]
                                                       if g["clip"] == st["ten_clip"])}}
    doan = [x for dg in kq_c["dong"] if dg["loai"] == "chap_nhan" for x in dg["doan"]]
    ra["cach_c"] = {"doan": [[x["video_tu"], x["video_den"], x["clip_tu"], x["clip_den"], x["tuong_dong_tb"],
                              x["tuong_dong_min"], x["cach_tim_mep"]] for x in doan],
                    "pr": ch.pr([(x["video_tu"], x["video_den"]) for x in doan], tk, dur),
                    "mep": ch.mep(doan, that),
                    "tung_dong": [{"engine_start_s": dg["engine"]["start_s"], "muc_trong": dg["muc_trong"],
                                   "nen_p99": dg["duong_nen"]["p99"], "nen_max": dg["duong_nen"]["max"],
                                   "nguong_bam": dg["nguong_bam"], "nguong_dung": dg["nguong_dung"],
                                   "tuong_phan_thap": dg["tuong_phan_thap"], "so_doan": len(dg["doan"]),
                                   "thoi_gian_s": dg["thoi_gian"]["tong_s"]} for dg in kq_c["dong"]]}
    if "chu_ky_vong_lap_s" in st:            # H2: giây clip chỉ xác định tới ±k·T → chấm thêm theo modulo
        T = st["chu_ky_vong_lap_s"]
        ra["cach_c"]["lech_clip_theo_chu_ky"] = [
            None if e is None else round(e["clip_dau"] / T, 3) for e in ra["cach_c"]["mep"]]
    return ra


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    chi_c = "--chi-cach-c" in sys.argv
    ds = [x for x in sys.argv[1:] if not x.startswith("--")] or list(CA)
    os.makedirs(RA, exist_ok=True)
    kb.KICH_BAN.update(CA)                 # chỉ trong bộ nhớ tiến trình này
    cb.KET_QUA = RA                        # chay_mot ghi vào thư mục của tôi
    cc.BO_THU = RA                         # Cách C đọc thư mục của tôi
    ts = dict(td.THAM_SO_MAC_DINH)
    tong_p = os.path.join(RA, "tong_hop_ca_kho.json")
    tong = _json(tong_p) if os.path.exists(tong_p) else {}
    for S in ds:
        if not chi_c:
            s = cb.chay_mot(S)
            print(f"[{S}] engine: dòng={s['so_dong']} đầu clip={s['sai_so_dau_clip_s']} đầu vùng={s['sai_so_dau_vung_s']} "
                  f"cuối={s['sai_so_cuoi_s']} P={s['precision_giay']} R={s['recall_giay']} "
                  f"bị loại={s['so_dong_bi_loai_cua_clip']}", flush=True)
        kq_c = cc.kich_ban(S, ts, os.path.join(RA, "_cach_c"), {"duong": {}, "ngoai_doan_that": {}})
        r = cham_ca(S, kq_c)
        do = sd.kiem_kich_ban(S, {S: os.path.join(RA, S)})
        r["su_that_do_tu_audio"] = {k: v for k, v in do.items()
                                    if k in ("cach", "ket_luan", "doan_do_duoc", "lech_lon_nhat_s", "kiem_doan",
                                             "lech_mep_lon_nhat_s")}
        if do.get("doan_bong_cung_am_thanh") is not None:
            r["su_that_do_tu_audio"]["so_doan_bong_cung_am_thanh"] = len(do["doan_bong_cung_am_thanh"])
        tong[S] = r
        print(f"[{S}] engine dòng {[(m['start_s'], m['vung_khop_s'], m['end_s'], m['clip_offset_s'], m['hashes'], m['moc_mo_ho'], m['ty_so_doi_thu']) for m in r['engine']['dong']]}"
              f" loại {[(m['start_s'], m['hashes']) for m in r['engine']['dong_bi_loai']]}", flush=True)
        print(f"[{S}] Cách C đoạn {r['cach_c']['doan']} | P/R {r['cach_c']['pr']} | mép {r['cach_c']['mep']} | "
              f"{r['cach_c']['tung_dong']}", flush=True)
        print(f"[{S}] sự thật đo từ audio: {r['su_that_do_tu_audio'].get('ket_luan')}", flush=True)
        with open(tong_p, "w", encoding="utf-8") as f:
            json.dump(tong, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
