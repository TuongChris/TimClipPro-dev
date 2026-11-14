# -*- coding: utf-8 -*-
"""Cách A, phần 1 — chạy audfprint match TRỰC TIẾP (đúng lệnh ``Engine._match_chunks`` dựng) với
-Q ∈ {mặc định 0.05, 0.02, 0.01, 0} trên CÙNG khúc WAV + kho vân tay của bộ thử bước trước (bo_thu: chỉ đọc; kho
được chép sang thư mục kết quả trước khi dùng).

Mỗi lượt gọi audfprint của bước trước (``goi_audfprint_match`` trong ket_qua_engine.json: lượt thường, _uu_tien/
_con_lai, lượt bù tốc độ) được chạy lại y hệt danh sách khúc, chỉ thêm ``--time-quantile``. Với Q mặc định, kết quả
phải TRÙNG từng mảnh với raw/ của bo_thu (kiểm tái lập).

Đầu ra: KET_QUA/truc_tiep/<S>/<Q>/_raw_match*.txt, KET_QUA/truc_tiep/<S>/ket_qua.json, KET_QUA/truc_tiep/tong_hop.json
Chạy (Git Bash):
  cd /c/Dev/pc2_test_tools/khop_tung_giay/cach_a
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \
      -B do_truc_tiep.py S1 S3 …   |   --tat-ca   |   --tong-hop
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time

import chung as c

THU_MUC = os.path.join(c.KET_QUA, "truc_tiep")


def _env() -> dict:
    env = dict(os.environ)                   # như Engine._run_stream
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1")
    return env


def lenh(db: str, ds: str, op: str, q, cfg: dict) -> list:
    """Đúng tham số của Engine._match_chunks + _audfprint_cmd (ncores 2); ``-B`` chỉ để không ghi .pyc vào repo."""
    tham = [sys.executable, "-B", "-u", c.AUDFPRINT, "match", "--dbase", db, "--ncores", "2", "--continue-on-error",
            "--find-time-range", "--exact-count", "--min-count", "10", "--max-matches", str(cfg["max_matches"])]
    if int(cfg["shifts_quet"]) > 0:
        tham += ["--shifts", str(int(cfg["shifts_quet"]))]
    tham += ["--opfile", op, "--list", ds]
    if q is not None:
        tham += ["--time-quantile", repr(q)]
    return tham


def _khoa_manh(x: dict) -> tuple:
    return (x["khuc"], x["clip"], x["bat_dau"], x["khop"], x["t_clip"], x["hash"], x["tong"], x["hang"])


def chay(ten: str) -> dict:
    d = os.path.join(c.BO_THU, ten)
    st = c.doc_json(os.path.join(d, "su_that.json"))
    ket = c.doc_json(os.path.join(d, "ket_qua_engine.json"))
    ra = os.path.join(THU_MUC, ten)
    os.makedirs(ra, exist_ok=True)
    db_goc = glob.glob(os.path.join(d, "_engine", "data", "kho_*.pklz"))
    if len(db_goc) != 1:
        raise RuntimeError(f"{ten}: cần đúng 1 kho .pklz, thấy {db_goc}")
    db = os.path.join(ra, "kho_chep_tu_bo_thu.pklz")
    if not os.path.exists(db):
        shutil.copy2(db_goc[0], db)
    khoang = {}
    for g in ket["goi_audfprint_match"]:
        for k in g["khuc"]:
            mk = c.RE_TEN_KHUC.search(k)
            he = int(mk.group(2)) / 100000.0 if mk.group(2) else 1.0
            khoang[k] = (float(mk.group(1)), float(mk.group(1)) + c.do_dai_wav(os.path.join(d, "khuc", k)) * he)

    theo_q: dict = {}
    goc_theo_goi: dict = {}
    vi_du_lenh: dict = {}
    for q in c.CAC_Q:
        tq = c.ten_q(q)
        dq = os.path.join(ra, tq)
        os.makedirs(dq, exist_ok=True)
        t0 = time.perf_counter()
        theo_luot: dict = {}
        bat_bien: dict = {}
        tai_lap: dict = {}
        for g in ket["goi_audfprint_match"]:
            ds = os.path.join(dq, "_ds" + g["raw"][len("_raw_match"):])
            with open(ds, "w", encoding="utf-8") as f:
                f.write("\n".join(os.path.join(d, "khuc", k) for k in g["khuc"]))
            op = os.path.join(dq, g["raw"])
            if os.path.exists(op):
                os.remove(op)
            cmd = lenh(db, ds, op, q, ket["cau_hinh"])
            vi_du_lenh.setdefault(tq, cmd[1:])
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=_env(),
                               timeout=540)
            if r.returncode != 0 or not os.path.exists(op):
                raise RuntimeError(f"{ten} {tq} {g['raw']}: audfprint rc={r.returncode}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
            manh = c.doc_raw(op)
            theo_luot.setdefault(g["luot_bu"] or "thuong", []).extend(manh)
            if q is None:
                goc_theo_goi[g["raw"]] = manh
                cu = c.doc_raw(os.path.join(d, "raw", g["raw"]))
                tai_lap[g["raw"]] = {"trung_tung_manh_voi_bo_thu": sorted(map(_khoa_manh, cu)) == sorted(map(_khoa_manh, manh)),
                                     "so_manh_bo_thu": len(cu), "so_manh_lan_nay": len(manh)}
            else:
                bat_bien[g["raw"]] = c.so_bat_bien(goc_theo_goi[g["raw"]], manh)
        theo_q[tq] = {"q": 0.05 if q is None else q, "truyen_tham_so_Q": q is not None,
                      "thoi_gian_s": round(time.perf_counter() - t0, 1),
                      "theo_luot": {lu: c.danh_gia_manh(m, st, khoang) for lu, m in theo_luot.items()},
                      **({"tai_lap_voi_bo_thu": tai_lap} if q is None else {"bat_bien_so_voi_Q0.05": bat_bien})}
        print(f"  [{ten}] {tq}: {theo_q[tq]['thoi_gian_s']} s", flush=True)
    kq = {"kich_ban": ten, "mo_ta": st["mo_ta"], "ten_clip": st["ten_clip"], "doan_su_that": st["doan"],
          "cau_hinh_khop": {k: ket["cau_hinh"][k] for k in ("max_matches", "shifts_quet", "chunk_s", "overlap_s")},
          "khoang_khuc_truc_video": khoang, "lenh_vi_du": vi_du_lenh, "theo_q": theo_q}
    c.ghi_json(os.path.join(ra, "ket_qua.json"), kq)
    return kq


def _luot_chinh(theo_luot: dict) -> str:
    """Lượt mang nhiều hash THẬT nhất (S7c: lượt bù tốc độ; còn lại: lượt thường)."""
    return max(theo_luot, key=lambda lu: (sum(dd.get("tong_hash_that", 0) for dd in theo_luot[lu]["doan"]),
                                          lu == "thuong"))


def tong_hop() -> dict:
    hang = []
    for ten in c.KICH_BAN:
        p = os.path.join(THU_MUC, ten, "ket_qua.json")
        if not os.path.exists(p):
            hang.append({"kich_ban": ten, "chua_chay": True})
            continue
        kq = c.doc_json(p)
        muc = {"kich_ban": ten, "doan_su_that": [(dd["video_tu"], dd["video_den"]) for dd in kq["doan_su_that"]]}
        tl = kq["theo_q"]["Q0.05"].get("tai_lap_voi_bo_thu", {})
        muc["tai_lap_Q0.05_trung_bo_thu"] = all(v["trung_tung_manh_voi_bo_thu"] for v in tl.values()) if tl else None
        for tq, v in kq["theo_q"].items():
            lu = _luot_chinh(v["theo_luot"]) if kq["doan_su_that"] else "thuong"
            dg = v["theo_luot"].get(lu, {})
            muc[tq] = {
                "luot": lu,
                "doan": [{k: dd.get(k) for k in ("so_manh_that", "dau", "cuoi", "sai_so_dau_s", "sai_so_cuoi_s",
                                                 "tong_hash_that", "bong_gan_qua_loc", "bong_gan_vuot_dau_s",
                                                 "bong_gan_vuot_cuoi_s")} for dd in dg.get("doan", [])],
                "theo_khuc": [kh for dd in dg.get("doan", []) for kh in dd.get("theo_khuc", [])]
                if len({kh["khuc"] for dd in dg.get("doan", []) for kh in dd.get("theo_khuc", [])}) > 1 else None,
                "manh_qua_loc_tat_ca_luot": {
                    "bong": sum(x["bong_qua_loc_min_hash_min_match"] for x in v["theo_luot"].values()),
                    "clip_khac": sum(x["clip_khac_qua_loc_min_hash_min_match"] for x in v["theo_luot"].values()),
                    "clip_khac_khop_dai_nhat_s": max(x["clip_khac_khop_dai_nhat_s"] for x in v["theo_luot"].values()),
                    "clip_khac_hash_lon_nhat": max(x["clip_khac_hash_lon_nhat"] for x in v["theo_luot"].values())},
            }
            if "bat_bien_so_voi_Q0.05" in v:
                bb = v["bat_bien_so_voi_Q0.05"].values()
                muc[tq]["bat_bien"] = {"cung_tap_dong_moi_luot": all(x["cung_tap_dong"] for x in bb),
                                       "align_lech_toi_da_s": max(x["align_lech_toi_da_s"] for x in bb),
                                       "khop_tang_max_s": max(x["khop_tang_max_s"] for x in bb),
                                       "khop_tang_min_s": min(x["khop_tang_min_s"] for x in bb)}
        hang.append(muc)
    out = {"ghi_chu": "Mức MẢNH THÔ của audfprint (trước _merge). sai_so_dau/cuoi = hợp các mảnh nằm đúng đường ánh xạ "
                      "thật (±1 s) so với [video_tu, video_den]; dương ở đầu = trễ, âm ở cuối = sớm.",
           "kich_ban": hang}
    c.ghi_json(os.path.join(THU_MUC, "tong_hop.json"), out)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c.kiem_moi_truong()
    c.kiem_parser_giong_engine()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kich_ban", nargs="*")
    ap.add_argument("--tat-ca", action="store_true")
    ap.add_argument("--tong-hop", action="store_true")
    a = ap.parse_args()
    ds = c.KICH_BAN if a.tat_ca else a.kich_ban
    for ten in ds:
        if ten not in c.KICH_BAN:
            ap.error(f"không có kịch bản {ten}")
    for ten in ds:
        t0 = time.perf_counter()
        chay(ten)
        print(f"[{ten}] xong {time.perf_counter() - t0:.0f} s", flush=True)
    tong_hop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
