# -*- coding: utf-8 -*-
"""DT-03 — đọc CHỈ ĐỌC ảnh chụp báo cáo V2 trong lichsu.db thật của DEV (người dùng duyệt 25/11). Không ghi gì.

Đo: số lượt/dòng, nhãn độ tin cậy, phân bố hash và độ dài khớp, tỉ lệ dòng ĐÃ tinh chỉnh, và tinh chỉnh dời mốc bao xa so
với mốc lượt quét (đầu: start_s ảnh chụp − vung_khop_s; cuối: end_s ảnh chụp − end_s bảng matches cùng clip). Không in
tiêu đề, link hay tên kênh — chỉ số đếm.
  <python> -I -X utf8 doc_anh_chup_lich_su.py [đường_dẫn_lichsu.db] > ra.json
"""
import json
import sqlite3
import statistics
import sys
from collections import Counter

DB = sys.argv[1] if len(sys.argv) > 1 else r"C:\Dev\TimClipPro_DevState\data\lichsu.db"


def _tk(xs):
    xs = sorted(abs(x) for x in xs)
    if not xs:
        return None
    q = lambda p: round(xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))], 2)  # noqa: E731
    return {"n": len(xs), "trung_vi": q(0.5), "p90": q(0.9), "p99": q(0.99), "lon_nhat": round(xs[-1], 2),
            "tren_5s": sum(x > 5 for x in xs), "tren_30s": sum(x > 30 for x in xs)}


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=1")
    jobs = con.execute("SELECT COUNT(*), SUM(n_matches) FROM jobs").fetchone()
    anh = con.execute("SELECT job_id, du_lieu FROM bao_cao_job").fetchall()
    tin, nguon, hash_ds, khop_ds = Counter(), Counter(), [], []
    so_dong = da_tc = loi = 0
    doi_dau, doi_cuoi, lech_bang_engine = [], [], []
    for job_id, dl in anh:
        try:
            d = json.loads(dl)
        except ValueError:
            loi += 1
            continue
        nguon[d.get("nguon_loai")] += 1
        bang = con.execute("SELECT clip, start_s, end_s FROM matches WHERE job_id=? ORDER BY id", (job_id,)).fetchall()
        theo_clip = {}
        for c, s, e in bang:
            theo_clip.setdefault(c, []).append((s, e))
        for x in d.get("doan") or []:
            so_dong += 1
            tin[x.get("confidence")] += 1
            hash_ds.append(int(x.get("hashes") or 0))
            khop_ds.append(float(x.get("matched_s") or 0))
            ung = theo_clip.get((x.get("goc") or {}).get("clip"), [])
            if x.get("da_tinh_chinh"):
                da_tc += 1
                if x.get("start_s") is not None and x.get("vung_khop_s") is not None:
                    doi_dau.append(x["start_s"] - x["vung_khop_s"])
                if x.get("end_s") is not None and ung:
                    doi_cuoi.append(min((x["end_s"] - e for _, e in ung), key=abs))
            elif x.get("end_s") is not None and ung:
                lech_bang_engine.append(min((x["end_s"] - e for _, e in ung), key=abs))
    ra = {"db": DB, "so_luot": jobs[0], "tong_n_matches": jobs[1], "so_anh_chup": len(anh), "anh_chup_hong": loi,
          "nguon": dict(nguon), "so_dong_bao_cao": so_dong, "da_tinh_chinh": da_tc,
          "nhan_tin_cay": dict(tin.most_common()),
          "hash": {"trung_vi": statistics.median(hash_ds) if hash_ds else None,
                   "duoi_2000": sum(h < 2000 for h in hash_ds), "duoi_5000": sum(h < 5000 for h in hash_ds)},
          "giay_khop": {"trung_vi": statistics.median(khop_ds) if khop_ds else None,
                        "duoi_30s": sum(k < 30 for k in khop_ds), "duoi_60s": sum(k < 60 for k in khop_ds)},
          "tinh_chinh_doi_dau_s": _tk(doi_dau), "tinh_chinh_doi_cuoi_s": _tk(doi_cuoi),
          "dong_chua_tinh_chinh_lech_bang_matches_s": _tk(lech_bang_engine)}
    print(json.dumps(ra, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
