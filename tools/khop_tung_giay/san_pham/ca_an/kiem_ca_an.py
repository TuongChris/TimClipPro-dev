# -*- coding: utf-8 -*-
"""Kiểm CA ẨN (held-out) bước «tinh chỉnh mốc từng giây» (TimClipPro/tinh_chinh_moc.py, P-8) — theo vòng kiểm.

Bộ ca ``--bo`` (mặc định ``ca_an``): A01–A18 của vòng 1 dựng bởi ``dung_ca.py`` (sự thật đo lại từ audio:
``kiem_su_that.py``), dòng engine THẬT của ``chay_engine.py``; ``ca_an_2`` = B01–B19 của vòng 2 (``dung_ca_2.py``,
``kiem_su_that_2.py``, ``chay_engine_2.py`` — ky_vong đã hạ theo hợp đồng nơi gọi, bản thiết kế giữ ở
``ky_vong_thiet_ke``). Dòng engine lưu ở ``ket_qua_engine.json`` (tinh chỉnh TẮT). Chỉ ĐỌC thư mục ca; ghi ra
``<GOC_RA>\\kiem_ca_an_<vòng>\\`` (có ``--bo``: thêm thư mục con cùng tên bộ): ``<ca>\\ket_qua.json``,
``tong_hop.{json,md}`` (``tong_hop_mot_phan`` khi chỉ chạy vài ca), ``dau_cuoi.{json,md}``.

1. Phát lại (mặc định): từng dòng ``matches`` — dòng engine tự bỏ qua (``Engine._ly_do_khong_tinh_chinh``: mốc mơ hồ,
   lưới cao độ, thiếu file clip) mang đúng lý do của engine; dòng còn lại gọi ``tinh_chinh_moc.tinh_chinh_dong`` y như
   ``Engine._tinh_chinh_ket_qua`` (neo, hoặc neo dự phòng vung_khop_s − he_so·clip_offset_s; lõi [vung_khop_s, end_s];
   phạm vi (0, pham_vi_quet_s or duration_s)); file clip = file CÙNG TÊN trong ``kho\\`` của ca. Không hạn giờ — thời
   gian ghi lại (engine cho CẢ video tối thiểu 30 s). Dòng engine bỏ qua còn được gọi thẳng để THAM KHẢO (ngoài hợp
   đồng, không vào kết luận).
2. Chấm từng dòng với các đoạn thật CÙNG clip gán cho dòng (đoạn thật giao lõi nới biên 30 s + 10 % của dòng nhiều nhất):
   mép video (mép mờ: khoảng cách tới tâm trừ nửa bề rộng), mép clip, lệch ánh xạ (giây clip báo − giây clip thật tại
   CÙNG giây video, lớn nhất trên phần giao — tách khỏi lỗi mép), đúng/đủ theo giây trên trục video (bỏ vùng mép mờ),
   chỗ cắt bịa / bỏ sót (cắt thật ≥ 2 s = max(khe video, |bước nhảy clip|); trùng khi video_tu, video_den, clip_bo_tu,
   clip_bo_den lệch ≤ 1 s), đoạn bịa, đoạn thật bỏ sót, hợp đồng kiểu JSON.
   ĐẠT: mọi dòng ĐÃ với mép ≤ 0,5 s, ánh xạ ≤ 0,5 s, đúng/đủ ≥ 0,98, không cắt bịa/sót, không đoạn bịa/sót — hoặc CHƯA
   kèm lý do là phán đoán về dữ liệu (không phải lỗi/hết giờ) khi ky_vong = «chua_hoac_da». NGHIÊM TRỌNG (dòng ĐÃ sai
   mà tự tin): cắt bịa, sót cắt, mép lệch > 2 s, đoạn bịa/sót > 2 s, ánh xạ lệch > 0,5 s. Ca engine không ra dòng nào:
   «không áp dụng» (bước tinh chỉnh không chạy).
3. ``--dau-cuoi A02 A07 ...``: engine THẬT (thư mục tạm, kho chép sang, ncores 2) dựng kho MỘT lần rồi scan_media HAI
   lần — tinh_chinh_moc TẮT rồi BẬT: kq.tinh_chinh đủ một mục mỗi dòng (cùng clip, start_s, thứ tự); matches,
   matches_loai, ung_vien_dat (mọi trường kể cả compare=False), so_dat_nguong, status, note, chinh_sach trùng từng
   trường; mục tinh chỉnh của engine so với phát lại vòng này (bỏ thoi_gian_s); dòng engine so với dòng đã lưu. Dòng
   engine xê dịch giữa các lần dựng kho (vòng 2: B07 có lần ra HAI dòng thay một dòng hai neo) nên mục tinh chỉnh CỦA
   ENGINE cũng được chấm với sự thật như phần 2 (``ket_luan_tinh_chinh_engine``, lưu kèm ``dong_engine``).
Chạy (Git Bash; máy dùng chung — một engine một lúc):
  cd /c/Dev/Tool_Quet/TimClipPro
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \\
      -B -X utf8 ../tools/khop_tung_giay/san_pham/ca_an/kiem_ca_an.py [--vong 1] [A01 ...] [--dau-cuoi A02 A07 ...]
  Vòng 2: ``kiem_ca_an.py --vong 2 --bo ca_an_2 [--dau-cuoi B05 B07 ...]`` (kiểm chính) và
  ``kiem_ca_an.py --vong 2 --bo ca_an`` (kiểm lại vòng 1) — ra ``kiem_ca_an_2\\ca_an_2\\``, ``kiem_ca_an_2\\ca_an\\``.
  Tự kiểm phần chấm (không cần audio): ``kiem_ca_an.py --tu-kiem``.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from types import SimpleNamespace  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chay_engine_2 import NEO_TRUNG_S, _lech_neo  # noqa: E402
from kiem_trong_mau import _dai, _ghi, _giao, _hop, _json, _kiem_moi_truong  # noqa: E402

MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "TimClipPro"))  # checkout chứa file này
CA_AN = r"C:\Dev\pc2_test_runs\2026-11-14_p8\ca_an"
GOC_RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8"
DA, CHUA = "da_tinh_chinh", "chua_tinh_chinh"       # = tinh_chinh_moc.DA / CHUA (phần chấm không nạp module)
DUNG_SAI_MEP_S = 0.5            # mép video, mép clip, ánh xạ — để ĐẠT
NGUONG_PR = 0.98
DUNG_SAI_CAT_S = 1.0            # chỗ cắt báo trùng chỗ cắt thật (độ chính xác mép chấm riêng qua lỗi mép)
CAT_TOI_THIEU_S = 2.0           # chỗ cắt thật nhỏ hơn thế không bắt buộc phải thấy
NGHIEM_TRONG_S = 2.0
NGAN_SACH_ENGINE_S = 30.0       # ngân sách tối thiểu của Engine._tinh_chinh_ket_qua cho CẢ video
TRUONG_SO = ("matches", "matches_loai", "ung_vien_dat", "so_dat_nguong", "status", "note", "chinh_sach")
TRUONG_DONG = ("clip", "start_s", "vung_khop_s", "end_s", "clip_offset_s", "hashes", "he_so", "ho", "neo", "moc_mo_ho")


# ---------------------------------------------------------------------------------------------- chấm (hàm thuần)

def _tru(x, y) -> list:
    """Hiệu tập khoảng x \\ y."""
    ra = []
    for a, b in _hop(x):
        for c, d in _hop(y):
            if c < b and d > a:
                if c > a:
                    ra.append((a, c))
                a = d
        if b > a:
            ra.append((a, b))
    return ra


def _giao_dai(a, b) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def _nua_rong(mep_mo: list, t: float) -> float:
    return next((float(m["nua_rong"]) for m in mep_mo if abs(m["t"] - t) < 1e-6), 0.0)


def _loi(bao: float, that: float, h: float = 0.0) -> float:
    """bao − that; mép mờ ± h: khoảng cách tới tâm trừ nửa bề rộng (rơi trong vùng mờ = 0), giữ dấu."""
    e = bao - that
    return round(math.copysign(max(0.0, abs(e) - h), e), 3)


def _ly_do_hop_ly(ly_do: str) -> bool:
    """Lý do CHƯA là một phán đoán về dữ liệu — không phải lỗi chạy hay hết giờ."""
    return bool(ly_do) and not ly_do.startswith("Lỗi") and not ly_do.startswith("Hết thời gian")


def _vt(x: dict) -> tuple:
    return x["video_tu"], x["video_den"]


def vi_pham_hop_dong(kq: dict) -> list:
    """Kiểu JSON thuần (không numpy/tuple/NaN), khoá bắt buộc, thứ tự, làm tròn — theo hợp đồng của module."""
    loi: list = []

    def duyet(x, p):
        if x is None or type(x) in (bool, int, str):
            return
        if type(x) is float:
            if not math.isfinite(x):
                loi.append(f"{p} = {x}")
        elif type(x) is list:
            for i, v in enumerate(x):
                duyet(v, f"{p}[{i}]")
        elif type(x) is dict:
            for k, v in x.items():
                duyet(v, f"{p}.{k}")
        else:
            loi.append(f"{p}: kiểu {type(x).__name__}")
    duyet(kq, "kq")
    thieu = {"phien_ban", "trang_thai", "ly_do", "doan", "cho_cat", "ho_so", "nguong_pct", "nen_p99_pct",
             "cham_gioi_han", "thoi_gian_s"} - set(kq)
    if thieu:
        loi.append(f"thiếu khoá {sorted(thieu)}")
        return loi
    if kq["trang_thai"] == DA:
        doan = kq["doan"]
        if not doan:
            loi.append("ĐÃ mà không có đoạn")
        if [d["video_tu"] for d in doan] != sorted(d["video_tu"] for d in doan):
            loi.append("doan chưa xếp theo video_tu")
        if len(kq["cho_cat"]) != max(0, len(doan) - 1):
            loi.append("cho_cat không đúng một mục mỗi ranh giới")
        if [p[0] for p in kq["ho_so"]] != sorted(p[0] for p in kq["ho_so"]):
            loi.append("ho_so chưa xếp theo giây video")
        so = [d[k] for d in doan for k in ("video_tu", "video_den", "clip_tu", "clip_den")]
        if any(round(x, 3) != x for x in so):
            loi.append("giây chưa làm tròn 3 số lẻ")
        pct = [d[k] for d in doan for k in ("tuong_dong_tb", "tuong_dong_min")] + [p[1] for p in kq["ho_so"]]
        if any(not 0.0 <= x <= 100.0 or round(x, 1) != x for x in pct):
            loi.append("phần trăm ngoài 0–100 hoặc chưa làm tròn 1 số lẻ")
    elif kq["trang_thai"] != CHUA or not kq["ly_do"]:
        loi.append(f"trạng thái lạ hoặc CHƯA không có lý do: {kq['trang_thai']!r}")
    return loi


def cham_dong(that: list, tc: dict, mep_mo: list, ky_vong: str) -> dict:
    """Chấm MỘT dòng engine. ``that``: đoạn thật (cùng clip) gán cho dòng; ``tc``: kết quả tinh_chinh_moc (hoặc mục
    «chưa» engine tự đặt khi bỏ qua dòng). Trả số liệu + «dat» + «nghiem_trong» + «loi» (câu ngắn)."""
    that = sorted(that, key=lambda t: t["video_tu"])
    if tc.get("trang_thai") != DA:
        ly_do = tc.get("ly_do", "")
        if not that:                                    # dòng không có đoạn thật nào: CHƯA là đúng
            return {"trang_thai": "chua", "ly_do": ly_do, "dat": True, "nghiem_trong": False, "loi": []}
        hop_ly = _ly_do_hop_ly(ly_do)
        loi = [] if ky_vong == "chua_hoac_da" and hop_ly else [
            "CHƯA tinh chỉnh dù ca phải ĐÃ" if ky_vong == "da" else f"CHƯA với lý do không phải phán đoán: {ly_do!r}"]
        return {"trang_thai": "chua", "ly_do": ly_do, "ly_do_hop_ly": hop_ly, "dat": not loi, "nghiem_trong": False,
                "loi": loi}
    doan = sorted(tc["doan"], key=lambda d: d["video_tu"])
    vung_mo = [(m["t"] - m["nua_rong"], m["t"] + m["nua_rong"]) for m in mep_mo]
    kb = _tru([_vt(d) for d in doan], vung_mo)
    kt = _tru([_vt(t) for t in that], vung_mo)
    g = _dai(_giao(kb, kt))
    p = round(g / _dai(kb), 4) if _dai(kb) else 0.0
    r = round(g / _dai(kt), 4) if _dai(kt) else None
    tung = []
    for t in that:
        phu = [d for d in doan if _giao_dai(_vt(d), _vt(t)) > 0]
        if not phu:
            tung.append({"that": [t["video_tu"], t["video_den"], t["clip_tu"], t["clip_den"]], "bo_sot": True,
                         "dai_s": round(t["video_den"] - t["video_tu"], 3)})
            continue
        d = max(phu, key=lambda d: _giao_dai(_vt(d), _vt(t)))
        h0, h1 = _nua_rong(mep_mo, t["video_tu"]), _nua_rong(mep_mo, t["video_den"])
        lo, hi = max(d["video_tu"], t["video_tu"]), min(d["video_den"], t["video_den"])
        lech = [d["clip_tu"] + (x - d["video_tu"]) / d["k"] - (t["clip_tu"] + (x - t["video_tu"]) * t["he_so"])
                for x in (lo, hi)]
        tung.append({"that": [t["video_tu"], t["video_den"], t["clip_tu"], t["clip_den"]],
                     "tim": [d["video_tu"], d["video_den"], d["clip_tu"], d["clip_den"]], "bo_sot": False,
                     "loi_video_tu": _loi(d["video_tu"], t["video_tu"], h0),
                     "loi_video_den": _loi(d["video_den"], t["video_den"], h1),
                     "loi_clip_tu": _loi(d["clip_tu"], t["clip_tu"], h0 * t["he_so"]),
                     "loi_clip_den": _loi(d["clip_den"], t["clip_den"], h1 * t["he_so"]),
                     "lech_anh_xa_s": round(max(abs(x) for x in lech), 3),
                     "k_that": round(1.0 / t["he_so"], 6), "k_tim": d["k"], "cach_tim_mep": d.get("cach_tim_mep")})
    doan_bia = [[d["video_tu"], d["video_den"]] for d in doan
                if not any(_giao_dai(_vt(d), _vt(t)) > 0 for t in that)]
    cat_that = [{"video_tu": a["video_den"], "video_den": b["video_tu"], "clip_bo_tu": a["clip_den"],
                 "clip_bo_den": b["clip_tu"],
                 "co_s": round(max(b["video_tu"] - a["video_den"], abs(b["clip_tu"] - a["clip_den"])), 3)}
                for a, b in zip(that, that[1:])]
    cat_bao = tc.get("cho_cat", [])

    def trung(x, y) -> bool:
        return all(abs(x[k] - y[k]) <= DUNG_SAI_CAT_S for k in ("video_tu", "video_den", "clip_bo_tu", "clip_bo_den"))
    cat_bia = [x for x in cat_bao if not any(trung(x, y) for y in cat_that)]
    cat_sot = [y for y in cat_that if y["co_s"] >= CAT_TOI_THIEU_S and not any(trung(x, y) for x in cat_bao)]
    tim = [e for e in tung if not e["bo_sot"]]
    mep = max((abs(e[k]) for e in tim for k in ("loi_video_tu", "loi_video_den")), default=None)
    mep_clip = max((abs(e[k]) for e in tim for k in ("loi_clip_tu", "loi_clip_den")), default=None)
    anh_xa = max((e["lech_anh_xa_s"] for e in tim), default=None)
    bo_sot = [e["dai_s"] for e in tung if e["bo_sot"]]
    loi, nt = [], []

    def them(dk, cau, nghiem_trong=False):
        if dk:
            loi.append(cau)
            if nghiem_trong:
                nt.append(cau)
    them(mep is not None and mep > DUNG_SAI_MEP_S, f"mép video lệch {mep} s", mep is not None and mep > NGHIEM_TRONG_S)
    them(mep_clip is not None and mep_clip > DUNG_SAI_MEP_S, f"mép clip lệch {mep_clip} s")
    them(anh_xa is not None and anh_xa > DUNG_SAI_MEP_S, f"ánh xạ giây clip lệch {anh_xa} s", True)
    them(p < NGUONG_PR or r is None or r < NGUONG_PR, f"đúng/đủ theo giây {p}/{r}")
    them(bool(cat_bia), f"bịa {len(cat_bia)} chỗ cắt {[[x['video_tu'], x['video_den']] for x in cat_bia]}", True)
    them(bool(cat_sot), f"sót {len(cat_sot)} chỗ cắt {[[y['video_tu'], y['video_den']] for y in cat_sot]}", True)
    them(bool(bo_sot), f"bỏ sót đoạn thật {bo_sot} s", any(x > NGHIEM_TRONG_S for x in bo_sot))
    them(bool(doan_bia), f"đoạn bịa {doan_bia}", any(b - a > NGHIEM_TRONG_S for a, b in doan_bia))
    return {"trang_thai": "da", "dung_du": [p, r], "loi_mep_video_max_s": mep, "loi_mep_clip_max_s": mep_clip,
            "lech_anh_xa_max_s": anh_xa, "tung_doan_that": tung, "cat_that": cat_that, "cat_bia": cat_bia,
            "cat_sot": cat_sot, "doan_bia": doan_bia, "cham_gioi_han": tc.get("cham_gioi_han"),
            "dat": not loi, "nghiem_trong": bool(nt), "loi": loi}


def gan_doan_that(doan_that: list, matches: list) -> tuple:
    """Mỗi đoạn thật → dòng CÙNG clip có lõi nới biên (30 s + 10 % lõi, như cửa sổ của module) giao nó nhiều nhất,
    ưu tiên dòng có neo đi qua ánh xạ thật của đoạn (≤ NEO_TRUNG_S, luật của ``chay_engine_2``): engine có lúc tách MỘT
    lần dùng thành nhiều dòng theo căn chỉnh mà lõi chồng nhau (vòng 2: B07) — module chỉ đo dọc neo của dòng.
    Trả ({chỉ số dòng: [đoạn thật]}, [đoạn thật không dòng nào giao])."""
    gan: dict = {i: [] for i in range(len(matches))}
    ngoai = []
    for t in doan_that:
        tot = (False, 0.0, None)
        for i, m in enumerate(matches):
            if m["clip"] != t["clip"]:
                continue
            bien = 30.0 + 0.10 * (m["end_s"] - m["vung_khop_s"])
            giao = _giao_dai((m["vung_khop_s"] - bien, m["end_s"] + bien), _vt(t))
            neo = m.get("neo") or ([(m["vung_khop_s"] - m["he_so"] * m["clip_offset_s"], m["he_so"])]
                                   if "clip_offset_s" in m else [])
            qua = any(_lech_neo(a, k, t) <= NEO_TRUNG_S for a, k in neo)
            if giao > 0 and (qua, giao) > tot[:2]:
                tot = (qua, giao, i)
        (gan[tot[2]] if tot[2] is not None else ngoai).append(t)
    return gan, ngoai


def ket_luan_ca(dong: list) -> tuple:
    """(«DAT» | «HONG» | «KHONG_AP_DUNG», nghiêm trọng?)."""
    if not dong:
        return "KHONG_AP_DUNG", False
    return ("DAT" if all(x["cham"]["dat"] for x in dong) else "HONG"), any(x["cham"]["nghiem_trong"] for x in dong)


def _tu_kiem() -> None:
    def t(vt, vd, ct, cd, hs=1.0):
        return {"clip": "c", "video_tu": vt, "video_den": vd, "clip_tu": ct, "clip_den": cd, "he_so": hs}

    def d(vt, vd, ct, cd, k=1.0):
        return {"video_tu": vt, "video_den": vd, "clip_tu": ct, "clip_den": cd, "k": k, "cach_tim_mep": ["x", "x"]}

    def da(doan, cho_cat=()):
        return {"trang_thai": DA, "doan": doan, "cho_cat": list(cho_cat)}
    assert _tru([(0, 10)], [(2, 3), (5, 12)]) == [(0, 2), (3, 5)]
    # đúng, k ≠ 1 (video chậm 0,98 → k = 1/0,98), sai số mép 0,1 s
    kq = cham_dong([t(100.0, 200.0, 50.0, 148.0, 0.98)], da([d(100.1, 199.95, 50.098, 147.951, 1 / 0.98)]), [], "da")
    assert kq["dat"] and not kq["nghiem_trong"] and kq["lech_anh_xa_max_s"] < 0.01, kq
    # mép mờ ±1 s: lệch 0,8 s trong vùng mờ = 0
    kq = cham_dong([t(100.0, 200.0, 0.0, 100.0)], da([d(100.8, 199.3, 0.8, 99.3)]),
                   [{"t": 100.0, "nua_rong": 1.0}, {"t": 200.0, "nua_rong": 1.0}], "da")
    assert kq["dat"] and kq["loi_mep_video_max_s"] == 0.0 and kq["dung_du"] == [1.0, 1.0], kq
    # im lặng 4 s (hai đoạn thật cùng căn chỉnh) mà báo MỘT đoạn: sót cắt → nghiêm trọng
    hai = [t(100.0, 200.0, 0.0, 100.0), t(204.0, 300.0, 104.0, 200.0)]
    kq = cham_dong(hai, da([d(100.0, 300.0, 0.0, 200.0)]), [], "da")
    assert kq["nghiem_trong"] and len(kq["cat_sot"]) == 1 and kq["loi_mep_video_max_s"] == 104.0, kq
    # tua lùi 10 s: hai đoạn, chỗ cắt khe 0, clip lùi — báo đúng thì ĐẠT
    lui = [t(100.0, 200.0, 50.0, 150.0), t(200.0, 300.0, 140.0, 240.0)]
    kq = cham_dong(lui, da([d(100.0, 200.05, 50.0, 150.05), d(200.05, 300.0, 140.05, 240.0)],
                           [{"video_tu": 200.05, "video_den": 200.05, "clip_bo_tu": 150.05, "clip_bo_den": 140.05}]),
                   [], "da")
    assert kq["dat"] and not kq["cat_bia"] and not kq["cat_sot"], kq
    # chỗ cắt bịa giữa một đoạn liền → nghiêm trọng
    kq = cham_dong([t(100.0, 300.0, 0.0, 200.0)], da([d(100.0, 180.0, 0.0, 80.0), d(185.0, 300.0, 85.0, 200.0)],
                                                     [{"video_tu": 180.0, "video_den": 185.0, "clip_bo_tu": 80.0,
                                                       "clip_bo_den": 85.0}]), [], "da")
    assert kq["nghiem_trong"] and len(kq["cat_bia"]) == 1, kq
    # mép video đúng nhưng giây clip lệch 1 s → ánh xạ sai, nghiêm trọng
    kq = cham_dong([t(100.0, 200.0, 0.0, 100.0)], da([d(100.0, 200.0, 1.0, 101.0)]), [], "da")
    assert kq["nghiem_trong"] and kq["lech_anh_xa_max_s"] == 1.0, kq
    # CHƯA: hợp lệ khi «chua_hoac_da» + lý do phán đoán; lỗi chạy không hợp lệ; ca «da» thì hỏng (không nghiêm trọng)
    assert cham_dong(hai, {"trang_thai": CHUA, "ly_do": "Không đo được đoạn giống"}, [], "chua_hoac_da")["dat"]
    assert not cham_dong(hai, {"trang_thai": CHUA, "ly_do": "Lỗi khi tinh chỉnh: x"}, [], "chua_hoac_da")["dat"]
    kq = cham_dong(hai, {"trang_thai": CHUA, "ly_do": "x"}, [], "da")
    assert not kq["dat"] and not kq["nghiem_trong"], kq
    # gán đoạn thật: hai lần dùng xa nhau → mỗi dòng một đoạn
    m = [{"clip": "c", "vung_khop_s": 150.0, "end_s": 320.0}, {"clip": "c", "vung_khop_s": 1020.0, "end_s": 1190.0}]
    gan, ngoai = gan_doan_that([t(140.0, 330.0, 0.0, 190.0), t(1010.0, 1200.0, 90.0, 280.0)], m)
    assert [len(gan[0]), len(gan[1]), len(ngoai)] == [1, 1, 0] and gan[1][0]["video_tu"] == 1010.0, gan
    # B07 vòng 2: tua lùi 10 s mà engine tách HAI dòng, lõi dòng đầu phủ cả phần phát lại → đoạn theo neo của dòng
    lui = [t(280.6, 335.1, 18.4, 72.9), t(335.4, 573.7, 62.9, 301.2)]
    m = [{"clip": "c", "vung_khop_s": 285.0, "end_s": 566.2, "neo": [[262.2, 1.0]]},
         {"clip": "c", "vung_khop_s": 347.4, "end_s": 565.1, "neo": [[272.6, 1.0]]}]
    gan, _ = gan_doan_that(lui, m)
    assert [g[0]["video_tu"] for g in gan.values()] == [280.6, 335.4], gan
    assert vi_pham_hop_dong({"trang_thai": DA}) and not vi_pham_hop_dong(
        {"phien_ban": 1, "trang_thai": CHUA, "ly_do": "x", "doan": [], "cho_cat": [], "ho_so": [], "nguong_pct": 0.0,
         "nen_p99_pct": 0.0, "cham_gioi_han": False, "thoi_gian_s": 0.1})
    print("kiem_ca_an: tự kiểm phần chấm ĐẠT")


# ---------------------------------------------------------------------------------------------- phát lại

def _ds_ca(bo: str, chon: list) -> list:
    tat_ca = sorted(x for x in os.listdir(bo) if os.path.isfile(os.path.join(bo, x, "su_that.json")))
    ds = [x for x in tat_ca if not chon or x in chon or x.split("_")[0] in chon]
    sai = [c for c in chon if not any(c in (x, x.split("_")[0]) for x in tat_ca)]
    if sai:
        raise SystemExit(f"Không có ca {sai}")
    return ds


def _sha(p: str) -> str:
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _phien_ban() -> dict:
    def git(*ts):
        return subprocess.run(["git", "-C", MA, *ts], capture_output=True, text=True, encoding="utf-8",
                              errors="replace").stdout.strip()
    return {"head": git("rev-parse", "HEAD"), "sha256_tinh_chinh_moc_py": _sha(os.path.join(MA, "tinh_chinh_moc.py")),
            "sha256_engine_py": _sha(os.path.join(MA, "engine.py")),
            "git_status": git("status", "--porcelain", "--", "tinh_chinh_moc.py", "engine.py"),
            "luc": time.strftime("%Y-%m-%d %H:%M:%S")}


def _goi(tcm, clip: str, video: str, neo: list, m: dict, pham_vi) -> tuple:
    """Gọi module như engine (lỗi → CHƯA «Lỗi khi tinh chỉnh»), kèm số lần kiem_huy được gọi và giây đo ngoài."""
    dem = [0]

    def kiem_huy() -> None:
        dem[0] += 1
    t = time.perf_counter()
    try:
        kq = tcm.tinh_chinh_dong(clip, video, neo, m["vung_khop_s"], m["end_s"], pham_vi_s=pham_vi, kiem_huy=kiem_huy)
    except Exception as e:  # noqa: BLE001 — như Engine._tinh_chinh_ket_qua
        kq = {"trang_thai": tcm.CHUA, "ly_do": f"Lỗi khi tinh chỉnh: {e}"}
    return kq, {"so_lan_kiem_huy": dem[0], "giay": round(time.perf_counter() - t, 3)}


def phat_lai_ca(eng, tcm, bo: str, ten: str) -> dict:
    d = os.path.join(bo, ten)
    st = _json(os.path.join(d, "su_that.json"))
    ke = _json(os.path.join(d, "ket_qua_engine.json"))
    video = os.path.join(d, st["video"])
    den = float(ke["pham_vi_quet_s"] or ke["duration_s"] or 0.0)
    pham_vi = (0.0, den) if den > 0 else None
    gan, ngoai = gan_doan_that(st["doan"], ke["matches"])
    dong = []
    for i, m in enumerate(ke["matches"]):
        clip = os.path.join(d, "kho", os.path.basename(m["duong_dan_kho"] or m["clip"]))
        ly_do = eng.Engine._ly_do_khong_tinh_chinh(None, SimpleNamespace(moc_mo_ho=m["moc_mo_ho"], ho=m["ho"],
                                                                          duong_dan_kho=clip))
        neo = [tuple(a) for a in m["neo"]] or [(m["vung_khop_s"] - m["he_so"] * m["clip_offset_s"], m["he_so"])]
        x = {**{k: m[k] for k in TRUONG_DONG}, "neo": [list(a) for a in neo], "that": gan[i],
             "engine_bo_qua": bool(ly_do)}
        if ly_do:
            x["tinh_chinh"] = {"trang_thai": tcm.CHUA, "ly_do": ly_do}
            x["tham_khao_goi_thang"], x["do_tham_khao"] = _goi(tcm, clip, video, neo, m, pham_vi)
            x["cham_tham_khao"] = cham_dong(gan[i], x["tham_khao_goi_thang"], st["mep_mo"], "chua_hoac_da")
            x["hop_dong_tham_khao"] = vi_pham_hop_dong(x["tham_khao_goi_thang"])
        else:
            x["tinh_chinh"], x["do"] = _goi(tcm, clip, video, neo, m, pham_vi)
            x["hop_dong"] = vi_pham_hop_dong(x["tinh_chinh"])
        x["cham"] = cham_dong(gan[i], x["tinh_chinh"], st["mep_mo"], st["ky_vong"])
        dong.append(x)
    kl, nt = ket_luan_ca(dong)
    return {"ten": ten, "loai": st["loai"], "ky_vong": st["ky_vong"],
            "ky_vong_thiet_ke": st.get("ky_vong_thiet_ke", st["ky_vong"]), "su_that": st["doan"],
            "mep_mo": st["mep_mo"],
            "doan_that_ngoai_moi_dong": ngoai, "engine_ket_luan": ke["ket_luan_engine"], "pham_vi_s": pham_vi,
            "dong": dong, "ket_luan": kl, "nghiem_trong": nt}


def _o(x) -> str:
    return "—" if x is None else (f"{x:g}" if isinstance(x, float) else str(x))


def bang(hang: list) -> str:
    dong = ["| Ca | Kỳ vọng | Dòng | Trạng thái từng dòng | Mép video Δtu/Δden mỗi đoạn thật (s) | Ánh xạ max (s) | "
            "Đúng/đủ | Cắt bịa/sót | Kết luận | Ghi chú | TC (s) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for h in hang:
        if "loi_chay" in h:
            dong.append(f"| {h['ten']} | | | LỖI CHẠY | | | | | HONG | {h['loi_chay'][-150:]!r} | |")
            continue
        tt, mep, ax, pr, cat, ghi, tg = [], [], [], [], [], [], []
        for x in h["dong"]:
            c = x["cham"]
            tt.append(("ĐÃ" if c["trang_thai"] == "da" else "CHƯA") + (" (engine bỏ qua)" if x["engine_bo_qua"] else ""))
            if c["trang_thai"] == "da":
                mep.append(", ".join("bỏ sót" if e["bo_sot"] else f"{e['loi_video_tu']:+.3f}/{e['loi_video_den']:+.3f}"
                                     for e in c["tung_doan_that"]) or "không có đoạn thật")
                ax.append(_o(c["lech_anh_xa_max_s"]))
                pr.append(f"{_o(c['dung_du'][0])}/{_o(c['dung_du'][1])}")
                cat.append(f"{len(c['cat_bia'])}/{len(c['cat_sot'])}")
            else:
                ghi.append(f"«{c['ly_do']}»")
            ghi += c["loi"] + [f"hợp đồng: {v}" for v in x.get("hop_dong", [])]
            if x.get("cham_tham_khao"):
                ct = x["cham_tham_khao"]
                ghi.append("tham khảo gọi thẳng: " + (
                    f"ĐÃ {'đúng' if ct['dat'] else 'SAI: ' + '; '.join(ct['loi'])}" if ct["trang_thai"] == "da"
                    else f"CHƯA «{ct['ly_do']}»"))
            if x.get("do"):
                tg.append(_o(x["tinh_chinh"].get("thoi_gian_s")))
        kl = {"DAT": "ĐẠT", "HONG": "HỎNG", "KHONG_AP_DUNG": "không áp dụng (engine không ra dòng)"}[h["ket_luan"]]
        kl += " — NGHIÊM TRỌNG" if h["nghiem_trong"] else ""
        kv = h["ky_vong"] + (f" (thiết kế {h['ky_vong_thiet_ke']})"
                             if h.get("ky_vong_thiet_ke", h["ky_vong"]) != h["ky_vong"] else "")
        dong.append(f"| {h['ten']} | {kv} | {len(h['dong'])} | {'; '.join(tt)} | {'; '.join(mep)} | "
                    f"{'; '.join(ax)} | {'; '.join(pr)} | {'; '.join(cat)} | {kl} | {' · '.join(ghi)} | "
                    f"{', '.join(tg)} |")
    return "\n".join(dong)


# ---------------------------------------------------------------------------------------------- đầu-cuối (engine)

def _nhu(x):
    if dataclasses.is_dataclass(x):
        return dataclasses.asdict(x)
    return [_nhu(v) for v in x] if isinstance(x, list) else x


def _khac(a, b, p: str = "") -> list:
    """Các đường dẫn a ≠ b (so sâu; NaN = NaN; tuple khác list)."""
    if isinstance(a, float) and isinstance(b, float):
        return [] if a == b or (math.isnan(a) and math.isnan(b)) else [f"{p}: {a!r} ≠ {b!r}"]
    if type(a) is not type(b):
        return [f"{p}: kiểu {type(a).__name__} ≠ {type(b).__name__}"]
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return [f"{p}: khoá {sorted(set(a) ^ set(b))}"]
        return [x for k in a for x in _khac(a[k], b[k], f"{p}.{k}")]
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return [f"{p}: độ dài {len(a)} ≠ {len(b)}"]
        return [x for i, (u, v) in enumerate(zip(a, b)) for x in _khac(u, v, f"{p}[{i}]")]
    return [] if a == b else [f"{p}: {a!r} ≠ {b!r}"]


def _bo_thoi_gian(x: dict) -> dict:
    return json.loads(json.dumps({k: v for k, v in x.items() if k not in ("thoi_gian_s", "clip", "start_s")}))


def dau_cuoi_ca(eng, bo: str, ten: str, ra: str) -> dict:
    d = os.path.join(bo, ten)
    st = _json(os.path.join(d, "su_that.json"))
    tam = tempfile.mkdtemp(prefix=f"p8_kca_{ten.split('_')[0]}_")
    try:
        kho = os.path.join(tam, "kho")
        shutil.copytree(os.path.join(d, "kho"), kho)
        data, out = os.path.join(tam, "data"), os.path.join(tam, "out")
        os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = data, out
        e = eng.Engine(root=MA, data_dir=data, out_dir=out)
        for x in (e.data_dir, e.runtime.data_dir):
            assert os.path.normcase(x) == os.path.normcase(os.path.abspath(data)), x
        e.config.ncores = 2
        e.add_kho(f"Kiem ca an {ten}", kho)
        so_clip = sum(os.path.splitext(x)[1].lower() in eng.MEDIA_EXTS for x in os.listdir(kho))
        kb = e.build_database(kho, "new")
        if kb.get("thanh_cong") != so_clip:
            raise RuntimeError(f"Dựng kho không trọn: {kb}")
        kq, tg = {}, {}
        for bat in (False, True):
            e.config.tinh_chinh_moc = bat
            e.config.validate()
            t = time.perf_counter()
            kq[bat] = e.scan_media(os.path.join(d, st["video"]))
            tg[bat] = round(time.perf_counter() - t, 1)
        tat, bat = kq[False], kq[True]
        khac = {f: _khac(_nhu(getattr(tat, f)), _nhu(getattr(bat, f)), f) for f in TRUONG_SO}
        tc = bat.tinh_chinh
        du_muc = (len(tc) == len(bat.matches) and [x.get("clip") for x in tc] == [m.clip for m in bat.matches]
                  and [x.get("start_s") for x in tc] == [m.start_s for m in bat.matches])
        p = os.path.join(ra, ten, "ket_qua.json")
        so_phat_lai = None
        if os.path.exists(p):
            pl = _json(p)["dong"]
            so_phat_lai = ([x for i, (u, v) in enumerate(zip(pl, tc))
                            for x in _khac(_bo_thoi_gian(u["tinh_chinh"]), _bo_thoi_gian(v), f"dong[{i}]")]
                           if len(pl) == len(tc) else [f"số dòng phát lại {len(pl)} ≠ engine {len(tc)}"])
        luu = _json(os.path.join(d, "ket_qua_engine.json"))["matches"]
        moi = [{k: (v if k != "neo" else [list(a) for a in v]) for k, v in _nhu(m).items() if k in TRUONG_DONG}
               for m in bat.matches]
        so_dong_luu = _khac([{k: m[k] for k in TRUONG_DONG} for m in luu], moi, "matches")
        # dòng engine xê dịch giữa hai lần dựng kho (số dòng cũng có thể đổi): chấm cả kết quả tinh chỉnh CỦA ENGINE
        gan, _ = gan_doan_that(st["doan"], moi)
        cham = [cham_dong(gan[i], x, st["mep_mo"], st["ky_vong"]) for i, x in enumerate(tc)] if du_muc else []
        kl_engine = ket_luan_ca([{"cham": c} for c in cham]) if du_muc else ("HONG", False)
        return {"ten": ten, "status": [tat.status, bat.status], "so_dong": len(bat.matches), "dong_engine": moi,
                "cham_tinh_chinh_engine": cham, "ket_luan_tinh_chinh_engine": list(kl_engine),
                "thoi_gian_quet_s": {"tat": tg[False], "bat": tg[True]},
                "tinh_chinh_khi_tat": tat.tinh_chinh, "tinh_chinh_du_moi_dong": du_muc,
                "truong_khac": khac, "trung_tung_truong": not any(khac.values()) and tat.tinh_chinh == [] and du_muc,
                "tinh_chinh_engine": tc, "khac_phat_lai": so_phat_lai, "dong_engine_khac_ban_luu": so_dong_luu}
    finally:
        shutil.rmtree(tam, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- main

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ca", nargs="*", help="mã ca (A01 …) hoặc tên thư mục; trống = mọi ca")
    ap.add_argument("--vong", type=int, default=1)
    ap.add_argument("--bo", help="bộ ca: tên thư mục trong GOC_RA (ca_an_2 …) hoặc đường dẫn; trống = ca_an, ra thẳng "
                                 "kiem_ca_an_<vòng> như vòng 1")
    ap.add_argument("--dau-cuoi", nargs="+", metavar="CA", help="engine thật quét tắt/bật cho các ca này")
    ap.add_argument("--tu-kiem", action="store_true")
    a = ap.parse_args()
    if a.tu_kiem:
        _tu_kiem()
        return 0
    _kiem_moi_truong()
    sys.path.insert(0, MA)
    import engine as eng
    import tinh_chinh_moc as tcm
    ra = os.path.join(GOC_RA, f"kiem_ca_an_{a.vong}")
    bo = CA_AN
    if a.bo:
        bo = os.path.normpath(os.path.join(GOC_RA, a.bo))       # đường dẫn tuyệt đối thì join giữ nguyên nó
        if not os.path.isdir(bo):
            raise SystemExit(f"Không có bộ ca {bo}")
        ra = os.path.join(ra, os.path.basename(bo))
    os.makedirs(ra, exist_ok=True)
    pb = _phien_ban()
    loi = 0
    if a.dau_cuoi:
        hang = []
        for ten in _ds_ca(bo, a.dau_cuoi):
            t = time.perf_counter()
            try:
                h = dau_cuoi_ca(eng, bo, ten, ra)
            except Exception:  # noqa: BLE001 — một ca hỏng không chặn ca khác
                h = {"ten": ten, "loi_chay": traceback.format_exc(), "trung_tung_truong": False}
            loi += not h["trung_tung_truong"]
            hang.append(h)
            print(f"[đầu-cuối {ten}] {time.perf_counter() - t:.0f} s — trùng từng trường: {h['trung_tung_truong']} "
                  f"khác: {h.get('truong_khac')} đủ mục: {h.get('tinh_chinh_du_moi_dong')} "
                  f"khác phát lại: {h.get('khac_phat_lai')} dòng khác bản lưu: {h.get('dong_engine_khac_ban_luu')} "
                  f"chấm tinh chỉnh của engine: {h.get('ket_luan_tinh_chinh_engine')} "
                  f"{[c['loi'] for c in h.get('cham_tinh_chinh_engine', [])]} "
                  f"{h.get('loi_chay', '')[-600:]}", flush=True)
        _ghi(os.path.join(ra, "dau_cuoi.json"), {"phien_ban": pb, "hang": hang})
        with open(os.path.join(ra, "dau_cuoi.md"), "w", encoding="utf-8") as f:
            f.write("| Ca | Dòng | Quét tắt/bật (s) | matches…chinh_sach trùng | tinh_chinh đủ mục | Khớp phát lại | "
                    "Chấm tinh chỉnh của engine |\n|---|---|---|---|---|---|---|\n")
            for h in hang:
                kl = h.get("ket_luan_tinh_chinh_engine") or ["—", False]
                f.write(f"| {h['ten']} | {h.get('so_dong', '—')} | {h.get('thoi_gian_quet_s', {}).get('tat', '—')}/"
                        f"{h.get('thoi_gian_quet_s', {}).get('bat', '—')} | "
                        f"{'có' if h['trung_tung_truong'] else 'KHÔNG ' + str(h.get('truong_khac') or h.get('loi_chay', '')[-200:])} | "
                        f"{h.get('tinh_chinh_du_moi_dong')} | "
                        f"{'có' if h.get('khac_phat_lai') == [] else h.get('khac_phat_lai')} | "
                        f"{kl[0]}{' NGHIÊM TRỌNG' if kl[1] else ''} "
                        f"{[c['loi'] for c in h.get('cham_tinh_chinh_engine', []) if c['loi']] or ''} |\n")
        return 1 if loi else 0
    hang = []
    for ten in _ds_ca(bo, a.ca):
        t = time.perf_counter()
        try:
            h = phat_lai_ca(eng, tcm, bo, ten)
            _ghi(os.path.join(ra, ten, "ket_qua.json"), {"phien_ban": pb, **h})
        except Exception:  # noqa: BLE001
            h = {"ten": ten, "loi_chay": traceback.format_exc(), "ket_luan": "HONG", "nghiem_trong": False}
            loi += 1
        hang.append(h)
        print(f"[{ten}] {time.perf_counter() - t:.1f} s — {h['ket_luan']}{' NGHIÊM TRỌNG' if h['nghiem_trong'] else ''} "
              + json.dumps([{"tt": x["tinh_chinh"].get("trang_thai"), "ly_do": x["tinh_chinh"].get("ly_do"),
                             "doan": [[s["video_tu"], s["video_den"], s["clip_tu"], s["clip_den"], s["k"]]
                                      for s in x["tinh_chinh"].get("doan", [])], "loi": x["cham"]["loi"]}
                            for x in h.get("dong", [])], ensure_ascii=False)[:1500] + h.get("loi_chay", "")[-800:],
              flush=True)
    dem = {k: sum(h["ket_luan"] == k for h in hang) for k in ("DAT", "HONG", "KHONG_AP_DUNG")}
    dem["NGHIEM_TRONG"] = sum(bool(h["nghiem_trong"]) for h in hang)
    ten_th = "tong_hop" if not a.ca else "tong_hop_mot_phan"
    _ghi(os.path.join(ra, f"{ten_th}.json"), {"phien_ban": pb, "dem": dem, "hang": [
        {k: v for k, v in h.items() if k != "dong"} | {"dong": [{k: x[k] for k in ("clip", "neo", "engine_bo_qua",
                                                                               "tinh_chinh", "cham")}
                                                          for x in h.get("dong", [])]} for h in hang]})
    with open(os.path.join(ra, f"{ten_th}.md"), "w", encoding="utf-8") as f:
        f.write(f"Vòng {a.vong}, bộ {os.path.basename(bo)} — tinh_chinh_moc.py sha256 "
                f"{pb['sha256_tinh_chinh_moc_py'][:16]}…, HEAD "
                f"{pb['head'][:8]}, {pb['luc']}. Đếm: {dem}\n\n{bang(hang)}\n")
    print(bang(hang))
    print(dem)
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
