# -*- coding: utf-8 -*-
"""Cách A — điểm đo BỔ SUNG ngoài bộ Q được giao (0.05/0.02/0.01/0): Q rất nhỏ (vd. 0.005, 0.002) chạy audfprint
TRỰC TIẾP như do_truc_tiep.py (cùng lệnh, cùng khúc + kho chép từ bo_thu), để xem có Q nào vừa chính xác vừa bền
với hash tình cờ không. Ghi KET_QUA/truc_tiep/<S>/Q<q>/ và KET_QUA/truc_tiep/bo_sung_Q<q>.json (không đụng ket_qua.json).

Chạy: PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B bo_sung_q.py 0.002 S1 S4 S4b
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import chung as c
import do_truc_tiep as dt


def chay(q: float, ten: str) -> dict:
    d = os.path.join(c.BO_THU, ten)
    st = c.doc_json(os.path.join(d, "su_that.json"))
    ket = c.doc_json(os.path.join(d, "ket_qua_engine.json"))
    ra = os.path.join(dt.THU_MUC, ten)
    db = os.path.join(ra, "kho_chep_tu_bo_thu.pklz")
    if not os.path.exists(db):
        raise SystemExit(f"{ten}: chạy do_truc_tiep.py trước (cần kho đã chép)")
    kq_cu = c.doc_json(os.path.join(ra, "ket_qua.json"))
    khoang = {k: tuple(v) for k, v in kq_cu["khoang_khuc_truc_video"].items()}
    dq = os.path.join(ra, c.ten_q(q))
    os.makedirs(dq, exist_ok=True)
    theo_luot: dict = {}
    t0 = time.perf_counter()
    for g in ket["goi_audfprint_match"]:
        ds = os.path.join(dq, "_ds" + g["raw"][len("_raw_match"):])
        with open(ds, "w", encoding="utf-8") as f:
            f.write("\n".join(os.path.join(d, "khuc", k) for k in g["khuc"]))
        op = os.path.join(dq, g["raw"])
        if os.path.exists(op):
            os.remove(op)
        r = subprocess.run(dt.lenh(db, ds, op, q, ket["cau_hinh"]), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=dt._env(), timeout=540)
        if r.returncode != 0 or not os.path.exists(op):
            raise RuntimeError(f"{ten} Q={q}: audfprint rc={r.returncode}\n{r.stderr[-1500:]}")
        theo_luot.setdefault(g["luot_bu"] or "thuong", []).extend(c.doc_raw(op))
    dg = {lu: c.danh_gia_manh(m, st, khoang) for lu, m in theo_luot.items()}
    lu = dt._luot_chinh(dg)
    return {"kich_ban": ten, "q": q, "thoi_gian_s": round(time.perf_counter() - t0, 1), "luot": lu,
            "doan": [{k: x.get(k) for k in ("sai_so_dau_s", "sai_so_cuoi_s", "tong_hash_that", "bong_gan_qua_loc",
                                            "bong_gan_vuot_dau_s", "bong_gan_vuot_cuoi_s")} for x in dg[lu]["doan"]],
            "theo_luot": dg}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c.kiem_moi_truong()
    q = float(sys.argv[1])
    out = {}
    for ten in sys.argv[2:]:
        k = chay(q, ten)
        out[ten] = k
        print(ten, c.ten_q(q), k["thoi_gian_s"], "s", k["luot"], k["doan"], flush=True)
    p = os.path.join(dt.THU_MUC, f"bo_sung_{c.ten_q(q)}.json")
    cu = c.doc_json(p) if os.path.exists(p) else {}
    cu.update(out)
    c.ghi_json(p, cu)
    return 0


if __name__ == "__main__":
    sys.exit(main())
