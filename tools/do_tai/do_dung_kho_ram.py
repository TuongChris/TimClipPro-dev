# -*- coding: utf-8 -*-
"""Nghiệm thu D-31 (06/11/2026): dựng Kho_Joe_Games thật bằng lịch RAM, so với sự cố sáng cùng ngày.

a) Cùng 32 clip, mã cũ và mã mới phải ra số hash giống hệt nhau từng clip (không đổi vân tay).
b) Dựng trọn kho 8 worker, ghi từng 2 giây RAM/commit/đĩa. Chốt an toàn: commit 88% trần, 3 giờ, hoặc DEV bật lên.
c) Cắt đoạn 60 giây từ vài clip thật rồi tìm lại trong bảng vừa dựng.

Audio chỉ đọc; bảng hash ở thư mục tạm, xoá khi xong; không đụng kho thật hay dữ liệu DEV. Dừng ngay nếu DEV đang chạy.
Chạy: python -B do_dung_kho_ram.py <thư mục ra> [a] [b] [c]
"""
import contextlib
import csv
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

import psutil

from do_o_cung import FF, KHO, chan_neu_dev, dev_dang_chay
from do_sup import BO_DEM, commit

MOI = r"C:\Dev\TimClipPro_NgayChu\TimClipPro"
CU = r"C:\Dev\TimClipPro_VanHanh\TimClipPro"
PREFIX = b"TIMCLIP_FINGERPRINT_EVENT "
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def lenh(ma: str, ds: str, db: str) -> list:
    return [sys.executable, "-B", "-u", os.path.join(ma, "audfprint_progress_runner.py"),
            os.path.join(ma, "audfprint-master", "audfprint.py"), "new", "--dbase", db,
            "--ncores", "8", "--continue-on-error", "--maxtimebits", "16", "--shifts", "4", "--list", ds]


def ghi_ds(tam: str, files: list) -> str:
    ds = os.path.join(tam, "list.txt")
    with open(ds, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(files))
    return ds


def so_hash(db: str) -> dict:
    sys.path.insert(0, os.path.join(MOI, "audfprint-master"))
    import hash_table

    ht = hash_table.HashTable(db)
    return {n: int(h) for n, h in zip(ht.names, ht.hashesperid) if n}


def phan_a(ra: str, tat: list) -> dict:
    ung = [f for f in tat if 10e6 <= os.path.getsize(f) <= 40e6]
    files = sorted(random.Random(20261106).sample(ung, 32))
    tam = tempfile.mkdtemp(prefix="do_d31_a_", dir=ra)
    try:
        ds = ghi_ds(tam, files)
        kq = {}
        for ten, ma in (("cu", CU), ("moi", MOI)):
            chan_neu_dev()
            db = os.path.join(tam, ten + ".pklz")
            t0 = time.monotonic()
            r = subprocess.run(lenh(ma, ds, db), capture_output=True, cwd=ma, env=ENV, check=False)
            kq[ten] = {"giay": round(time.monotonic() - t0, 1), "ma_thoat": r.returncode, "hash": so_hash(db)}
        lech = {f: (kq["cu"]["hash"].get(f), kq["moi"]["hash"].get(f)) for f in files
                if kq["cu"]["hash"].get(f) != kq["moi"]["hash"].get(f)}
        out = {"so_clip": len(files), "tong_hash": sum(kq["moi"]["hash"].values()), "so_clip_lech": len(lech),
               "lech": dict(list(lech.items())[:5]), "giay_cu": kq["cu"]["giay"], "giay_moi": kq["moi"]["giay"],
               "ma_thoat": [kq["cu"]["ma_thoat"], kq["moi"]["ma_thoat"]]}
    finally:
        shutil.rmtree(tam, ignore_errors=True)
    print(json.dumps({"a": out}, ensure_ascii=False), flush=True)
    return out


def doc_csv(csv_ra: str) -> dict:
    with open(csv_ra, encoding="utf-8", errors="replace", newline="") as f:
        h = list(csv.reader(f))

    def cot(i):
        ra = []
        for r in h[1:]:
            with contextlib.suppress(ValueError, IndexError):
                ra.append(float(r[i]))
        return ra

    def ban(i):
        x = cot(i)
        return {"tb_pct": round(100 - sum(x) / max(1, len(x)), 1), "giay_tren_90pct": 2 * sum(1 for v in x if v < 10)}

    return {"so_mau": len(h) - 1, "hdd_ban": ban(1), "hdd_hang_doi_max": max(cot(2), default=0),
            "ssd_ban": ban(8), "ssd_hang_doi_max": max(cot(9), default=0),
            "cpu_tb_pct": round(sum(cot(11)) / max(1, len(cot(11))), 1),
            "ram_trong_min_GB": round(min(cot(12), default=0) / 1024, 2),
            "trang_ra_max_moi_giay": round(max(cot(14), default=0))}


def tom_tat_su_kien(out_txt: str) -> dict:
    tt, loai, loi, ram, thu_lai, xong_luc = {}, {}, [], [], [], []
    with open(out_txt, "rb") as fh:
        for dong in fh:
            if not dong.startswith(PREFIX):
                continue
            e = json.loads(dong[len(PREFIX):].decode("utf-8", "replace"))
            if e["event"] == "clip_finished":
                tt[e["status"]] = tt.get(e["status"], 0) + 1
                if e["status"] != "success":
                    loai[e.get("category")] = loai.get(e.get("category"), 0) + 1
                    loi.append(e.get("message", "")[:220])
            elif e["event"] == "thong_bao_ram":
                ram.append(e["message"])
            elif e["event"] == "clip_cho_thu_lai":
                thu_lai.append(os.path.basename(e["file"])[:60] + " :: " + e["message"][:160])
    return {"trang_thai": tt, "loai_loi": loai, "loi": loi[:12], "thong_bao_ram": ram, "cho_thu_lai": thu_lai[:12],
            "so_cho_thu_lai": len(thu_lai), "xong_luc": xong_luc}


def phan_b(ra: str, tat: list) -> tuple:
    chan_neu_dev()
    tam = tempfile.mkdtemp(prefix="do_d31_b_", dir=ra)
    db = os.path.join(tam, "db.pklz")
    ds = ghi_ds(tam, tat)
    csv_ra = os.path.join(ra, "b_dia_ram.csv")
    tp = subprocess.Popen(["typeperf", *BO_DEM, "-si", "2", "-sc", "5500", "-f", "CSV", "-o", csv_ra, "-y"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    out_txt = os.path.join(ra, "b_out.txt")
    log = open(out_txt, "wb")
    p = subprocess.Popen(lenh(MOI, ds, db), stdout=log, stderr=subprocess.STDOUT, cwd=MOI, env=ENV)
    ps = psutil.Process(p.pid)
    t0 = time.monotonic()
    ly_do, dinh_cm, dinh_rss, uu_tien = "xong", 0.0, 0.0, set()
    nk = open(os.path.join(ra, "b_tien_trinh.log"), "w", encoding="utf-8")
    try:
        while True:
            if p.poll() is not None:
                ly_do = f"tien trinh thoat {p.returncode}"
                break
            cm, han = commit()
            dinh_cm = max(dinh_cm, cm)
            if cm >= 0.88 * han:
                ly_do = f"cham chot commit {cm:.1f}/{han:.1f} GB"
                break
            if time.monotonic() - t0 > 3 * 3600:
                ly_do = "het 3 gio"
                break
            if dev_dang_chay():
                ly_do = "DEV bat len, dung de nhuong may"
                break
            rss = []
            with contextlib.suppress(psutil.Error):
                for c in ps.children(recursive=True):
                    with contextlib.suppress(psutil.Error):
                        rss.append(c.memory_info().rss / 2**30)
                        uu_tien.add((c.name(), int(c.nice())))
            dinh_rss = max(dinh_rss, sum(rss))
            nk.write(f"{time.monotonic() - t0:6.0f}s commit {cm:5.1f}/{han:.0f} trong "
                     f"{psutil.virtual_memory().available / 2**30:5.1f} tien_trinh {len(rss)} "
                     f"lon_nhat {max(rss, default=0):5.1f}G tong {sum(rss):5.1f}G\n")
            nk.flush()
            time.sleep(2)
    finally:
        if p.poll() is None:
            with contextlib.suppress(psutil.Error):
                for c in ps.children(recursive=True):
                    with contextlib.suppress(psutil.Error):
                        c.kill()
                ps.kill()
        p.wait(60)
        log.close()
        nk.close()
        tp.terminate()
        tp.wait(10)
    out = {"ly_do_dung": ly_do, "giay": round(time.monotonic() - t0), "dinh_commit_may_GB": round(dinh_cm, 1),
           "dinh_rss_tool_GB": round(dinh_rss, 1), "uu_tien_tien_trinh": sorted(uu_tien),
           **tom_tat_su_kien(out_txt), **doc_csv(csv_ra)}
    print(json.dumps({"b": out}, ensure_ascii=False), flush=True)
    return out, tam, db


def phan_c(ra: str, db: str, tat: list) -> dict:
    theo_co = sorted(tat, key=os.path.getsize)
    chon = [theo_co[20], theo_co[len(theo_co) // 2], theo_co[-8], theo_co[-3]]
    tam = tempfile.mkdtemp(prefix="do_d31_c_", dir=ra)
    kq = []
    try:
        for i, f in enumerate(chon):
            cat = os.path.join(tam, f"cat{i}.wav")
            subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-ss", "240", "-t", "60", "-i", f,
                            "-ac", "1", "-ar", "16000", cat], check=False)
            r = subprocess.run([sys.executable, "-B", os.path.join(MOI, "audfprint-master", "audfprint.py"), "match",
                                "--dbase", db, "--find-time-range", cat], capture_output=True, cwd=MOI, env=ENV,
                               check=False)
            dong = [d for d in r.stdout.decode("utf-8", "replace").splitlines() if "Matched" in d]
            kq.append({"clip": os.path.basename(f)[:50], "MB": round(os.path.getsize(f) / 1e6),
                       "dung": bool(dong) and os.path.basename(f) in dong[0],
                       "dong": (dong[0][:60] + " ... " + dong[0][-40:]) if dong else "KHONG KHOP"})
    finally:
        shutil.rmtree(tam, ignore_errors=True)
    print(json.dumps({"c": kq}, ensure_ascii=False), flush=True)
    return {"mau": kq}


if __name__ == "__main__":
    chan_neu_dev()
    ra = os.path.abspath(sys.argv[1])
    phan = sys.argv[2:] or ["a", "b", "c"]
    tat = sorted(os.path.join(KHO, f) for f in os.listdir(KHO) if f.endswith(".opus"))
    kq: dict = {"so_clip_kho": len(tat), "ram_tong_GB": round(psutil.virtual_memory().total / 2**30, 1),
                "ram_trong_luc_dau_GB": round(psutil.virtual_memory().available / 2**30, 1)}
    if "a" in phan:
        print("=== phan a", time.strftime("%H:%M:%S"), flush=True)
        kq["a"] = phan_a(ra, tat)
    if "b" in phan:
        print("=== phan b", time.strftime("%H:%M:%S"), flush=True)
        kq["b"], tam, db = phan_b(ra, tat)
        if "c" in phan and os.path.isfile(db):
            print("=== phan c", time.strftime("%H:%M:%S"), flush=True)
            kq["c"] = phan_c(ra, db, tat)
        shutil.rmtree(tam, ignore_errors=True)
    with open(os.path.join(ra, "ket_qua_" + "".join(phan) + ".json"), "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)
    print("XONG", time.strftime("%H:%M:%S"), flush=True)
