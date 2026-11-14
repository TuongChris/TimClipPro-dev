# -*- coding: utf-8 -*-
"""Bộ thử sai số mốc của Tool Quét HIỆN TẠI — engine THẬT + audfprint THẬT trên audio giả lập (14/11/2026).

Mỗi kịch bản (kich_ban.py) một thư mục trong KET_QUA: ``kho/`` (clip gốc), video vi phạm, ``su_that.json``,
``ket_qua_engine.json`` (mọi trường Match + chẩn đoán), ``sai_so.json`` (so với sự thật), ``raw/`` (dòng thô audfprint
``_raw_match*.txt`` chép ra TRƯỚC khi engine xoá workspace), ``khuc/`` (chunk_*.wav đã đưa audfprint, để bước sau
dùng lại), ``nhat_ky_tien_do.txt`` và ``_engine/`` (data_dir/out_dir TẠM của Engine: kho vân tay db, lichsu.db tạm).

Bắt dữ liệu bằng cách bọc ``Engine._match_chunks`` / ``Engine._merge`` NGAY TRONG tiến trình này (như monkeypatch của
pytest) — không sửa file mã nào. Không ghi .pyc vào repo (``-B`` + PYTHONDONTWRITEBYTECODE cho tiến trình con).

Chạy (Git Bash; một kịch bản ~1–3 phút, S0 lâu hơn vì kho 9 clip):
  cd /c/Dev/pc2_test_tools/khop_tung_giay/bo_thu
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \
      -B chay_bo_thu.py --tat-ca            # hoặc: chay_bo_thu.py S1 S4  |  chay_bo_thu.py --tong-hop
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import sqlite3  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

THU_MUC_CONG_CU = os.path.dirname(os.path.abspath(__file__))
MA = r"C:\Dev\Tool_Quet\TimClipPro"
KET_QUA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"
CHAN_MANG = r"C:\Dev\Tool_Quet\tools\test\chan_mang"
THU_TU = ["S1", "S2", "S3", "S4", "S4b", "S5", "S5b", "S6", "S6b", "S7", "S7b", "S7c", "S8", "S9", "S0"]
CAU_HINH_GHI = ("chunk_s", "overlap_s", "overlap_max_s", "overlap_tu_dong", "min_hash", "min_match_s", "max_matches",
                "dedup_s", "shifts_kho", "shifts_quet", "ncores", "top_n", "min_hash_floor", "min_hash_strong",
                "quet_da_toc_do", "luoi_resample", "luoi_tempo", "phan_bo_deu", "uu_tien_clip_khac_nhau",
                "top1_tim_nhanh", "quet_tang_dan")


def _kiem_moi_truong() -> None:
    sc = sys.modules.get("sitecustomize")
    if sc is None or os.path.normcase(os.path.dirname(os.path.abspath(sc.__file__))) != os.path.normcase(CHAN_MANG):
        raise SystemExit(f"Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH={CHAN_MANG}")
    for bien in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_INSTALLATION_ID"):
        if os.environ.get(bien):
            raise SystemExit(f"Bỏ biến {bien} trước khi chạy: bộ thử chỉ chạy legacy trên thư mục tạm.")
    for lenh in ("ffmpeg", "ffprobe"):
        if shutil.which(lenh) is None:
            raise SystemExit(f"Cần {lenh} trong PATH.")


_kiem_moi_truong()
sys.path.insert(0, THU_MUC_CONG_CU)
sys.path.insert(0, MA)
import danh_gia  # noqa: E402
import kich_ban  # noqa: E402

import engine as eng  # noqa: E402

# ---------------------------------------------------------------- bắt dữ liệu trước khi engine xoá workspace
_GHI: dict = {"thu_muc": None, "merge": [], "goi_khop": []}
_GOC_MATCH = eng.Engine._match_chunks
_GOC_MERGE = eng.Engine._merge


def _match_ghi(self, chunks, *a, **kw):
    try:
        return _GOC_MATCH(self, chunks, *a, **kw)
    finally:
        d = _GHI["thu_muc"]
        if d:
            op = os.path.join(kw.get("workspace") or self.data_dir, f"_raw_match{kw.get('hau_to', '')}.txt")
            os.makedirs(os.path.join(d, "raw"), exist_ok=True)
            os.makedirs(os.path.join(d, "khuc"), exist_ok=True)
            if os.path.exists(op):
                shutil.copy2(op, os.path.join(d, "raw", os.path.basename(op)))
            for c in chunks:
                dich = os.path.join(d, "khuc", os.path.basename(c))
                if os.path.exists(c) and not os.path.exists(dich):
                    shutil.copy2(c, dich)
            _GHI["goi_khop"].append({"raw": os.path.basename(op), "co_raw": os.path.exists(op),
                                     "khuc": [os.path.basename(c) for c in chunks],
                                     "luot_bu": kw.get("luot_bu", "")})


def _merge_ghi(self, tho):
    ra = _GOC_MERGE(self, tho)
    _GHI["merge"].append({"tho": [dict(x) for x in tho], "ra": [dataclasses.asdict(m) for m in ra]})
    return ra


eng.Engine._match_chunks = _match_ghi
eng.Engine._merge = _merge_ghi


# ---------------------------------------------------------------- tiện ích
def _ghi_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


def _doc_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dong(m) -> dict:
    return dataclasses.asdict(m)


def _lenh(*lenh: str) -> str:
    try:
        return subprocess.run(lenh, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=30).stdout.strip()
    except Exception as e:  # noqa: BLE001 — chỉ là thông tin môi trường
        return f"(lỗi: {e})"


def _dong_tho(d: str, ten_clip: str) -> list:
    """Mọi dòng «Matched …» trong raw/ (của clip ``ten_clip``; rỗng = mọi clip)."""
    ra = []
    for ten in sorted(os.listdir(os.path.join(d, "raw"))) if os.path.isdir(os.path.join(d, "raw")) else []:
        with open(os.path.join(d, "raw", ten), encoding="utf-8", errors="replace") as f:
            for dong in f:
                if "Matched" in dong and (not ten_clip or ten_clip in dong):
                    ra.append(f"{ten}: {dong.strip()}")
    return ra


def _lich_su(sqlite_file: str, job_id) -> list:
    if not job_id or not os.path.exists(sqlite_file):
        return []
    con = sqlite3.connect(f"file:{sqlite_file}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(
            "SELECT clip, start_s, end_s, matched_s, clip_offset_s, hashes, confidence FROM matches WHERE job_id=?",
            (job_id,))]
    finally:
        con.close()


def _bao_cao_v2(kq) -> list:
    bc = getattr(kq, "bao_cao", None)
    return [{"clip": d.goc.clip, "giay_bat_dau": d.giay_bat_dau, "giay_ket_thuc": d.giay_ket_thuc,
             "start_s": d.start_s, "end_s": d.end_s, "vung_khop_s": d.vung_khop_s, "matched_s": d.matched_s,
             "clip_offset_s": d.clip_offset_s, "hashes": d.hashes, "link": d.link}
            for d in getattr(bc, "doan", ()) or ()]


# ---------------------------------------------------------------- một kịch bản
def chay_mot(ten: str) -> dict:
    d = os.path.join(KET_QUA, ten)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    t0 = time.perf_counter()
    su_that = kich_ban.KICH_BAN[ten](d)
    su_that["thoi_gian_dung_du_lieu_s"] = round(time.perf_counter() - t0, 1)
    _ghi_json(os.path.join(d, "su_that.json"), su_that)

    tam = os.path.join(d, "_engine")
    data, ketqua = os.path.join(tam, "data"), os.path.join(tam, "ketqua")
    os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = data, ketqua
    e = eng.Engine(root=MA, data_dir=data, out_dir=ketqua)
    assert os.path.normcase(e.data_dir) == os.path.normcase(os.path.abspath(data)), e.data_dir
    assert os.path.normcase(e.runtime.data_dir) == os.path.normcase(os.path.abspath(data)), e.runtime.data_dir
    e.config.ncores = 2           # máy đang chạy DEV 8502: không chiếm hết CPU
    for k, v in su_that["cau_hinh_engine_doi"].items():
        setattr(e.config, k, v)
    e.config.validate()
    kho = os.path.join(d, "kho")
    e.add_kho(f"Bo thu {ten}", kho)
    t0 = time.perf_counter()
    kq_build = e.build_database(kho, "new")
    t_build = time.perf_counter() - t0
    so_clip = len(os.listdir(kho))
    if kq_build.get("thanh_cong") != so_clip:
        raise RuntimeError(f"Dựng kho không trọn: {kq_build}")

    tien_do: list = []
    _GHI.update(thu_muc=d, merge=[], goi_khop=[])
    t0 = time.perf_counter()
    try:
        kq = e.scan_media(os.path.join(d, su_that["video"]), progress=lambda p, m: tien_do.append(f"{p:.3f}\t{m}"))
    finally:
        _GHI["thu_muc"] = None
    t_quet = time.perf_counter() - t0
    with open(os.path.join(d, "nhat_ky_tien_do.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(tien_do) + "\n")

    ten_clip = su_that["ten_clip"]
    cua_clip = (lambda ds: [_dong(m) for m in ds if m.clip == ten_clip]) if ten_clip else (lambda ds: [])
    cuoi = _GHI["merge"][-1] if _GHI["merge"] else {"tho": [], "ra": []}
    goi = re.findall(r"Khúc gối thực tế: (\d+) giây", "\n".join(tien_do))
    ket = {
        "kich_ban": ten,
        "trang_thai": kq.status, "ghi_chu_engine": kq.note,
        "thoi_gian_dung_kho_s": round(t_build, 1), "thoi_gian_quet_s": round(t_quet, 1),
        "dung_kho": kq_build,
        "cau_hinh": {k: getattr(e.config, k) for k in CAU_HINH_GHI},
        "khuc_goi_thuc_te_s": int(goi[-1]) if goi else None,
        "duration_s": kq.duration_s, "so_dat_nguong": kq.so_dat_nguong, "pham_vi_quet_s": kq.pham_vi_quet_s,
        "vung_da_khop": kq.vung_da_khop, "vung_loi": kq.vung_loi, "chinh_sach": getattr(kq, "chinh_sach", ""),
        "ten_clip_su_that": ten_clip,
        "dong_cho_clip": {"matches": cua_clip(kq.matches), "matches_loai": cua_clip(kq.matches_loai),
                          "ung_vien_dat": cua_clip(getattr(kq, "ung_vien_dat", []) or [])},
        "dong_clip_khac": {"matches": [_dong(m) for m in kq.matches if m.clip != ten_clip],
                           "matches_loai": [_dong(m) for m in kq.matches_loai if m.clip != ten_clip]},
        "merge_cuoi": {
            "so_lan_goi_merge": len(_GHI["merge"]),
            "so_manh_tho": len(cuoi["tho"]),
            "manh_tho_cua_clip": [x for x in cuoi["tho"] if not ten_clip or os.path.basename(x["clip"]) == ten_clip],
            "tat_ca_nhom_sau_merge": cuoi["ra"],
        },
        "goi_audfprint_match": _GHI["goi_khop"],
        "dong_tho_matched": _dong_tho(d, ten_clip),
        "chan_doan": dataclasses.asdict(kq.chan_doan) if dataclasses.is_dataclass(kq.chan_doan) else str(kq.chan_doan),
        "bao_cao_v2_doan": _bao_cao_v2(kq),
        "lich_su_matches": _lich_su(e.sqlite_file, kq.job_id),
    }
    _ghi_json(os.path.join(d, "ket_qua_engine.json"), ket)

    sai = danh_gia.danh_gia(su_that, ket["dong_cho_clip"]["matches"])
    sai["kich_ban"] = ten
    sai["so_dong_moi_clip_trong_bao_cao"] = len(kq.matches)
    sai["so_dong_clip_khac"] = len(ket["dong_clip_khac"]["matches"])
    sai["so_dong_bi_loai_cua_clip"] = len(ket["dong_cho_clip"]["matches_loai"])
    sai["danh_gia_dong_bi_loai"] = (danh_gia.danh_gia(su_that, ket["dong_cho_clip"]["matches_loai"])
                                    if ket["dong_cho_clip"]["matches_loai"] else None)
    _ghi_json(os.path.join(d, "sai_so.json"), sai)
    return sai


def tong_hop() -> None:
    hang = []
    for ten in THU_TU:
        d = os.path.join(KET_QUA, ten)
        if not os.path.exists(os.path.join(d, "sai_so.json")):
            loi = ""
            if os.path.exists(os.path.join(d, "loi.txt")):
                with open(os.path.join(d, "loi.txt"), encoding="utf-8") as f:
                    loi = f.read()[-2000:]
            hang.append({"kich_ban": ten, "chua_chay": True, "loi": loi})
            continue
        sai, ket, st = (_doc_json(os.path.join(d, x)) for x in ("sai_so.json", "ket_qua_engine.json", "su_that.json"))
        hang.append({"kich_ban": ten, "mo_ta": st["mo_ta"], "doan_su_that": st["doan"],
                     "trang_thai": ket["trang_thai"], "thoi_gian_quet_s": ket["thoi_gian_quet_s"],
                     "khuc_goi_thuc_te_s": ket["khuc_goi_thuc_te_s"],
                     "dong": [{k: m[k] for k in ("start_s", "vung_khop_s", "end_s", "matched_s", "clip_offset_s",
                                                 "hashes", "ty_le", "confidence", "moc_mo_ho")}
                              for m in ket["dong_cho_clip"]["matches"]],
                     **{k: sai.get(k) for k in ("tim_thay", "so_dong", "sai_so_dau_clip_s", "sai_so_dau_vung_s",
                                                "sai_so_cuoi_s", "precision_giay", "recall_giay",
                                                "precision_giay_tu_vung_khop", "recall_giay_tu_vung_khop",
                                                "so_dong_clip_khac", "so_dong_bi_loai_cua_clip")}})
    moi_truong = {"python": sys.version.split()[0], "nen_tang": platform.platform(),
                  "ffmpeg": _lenh("ffmpeg", "-version").splitlines()[0] if shutil.which("ffmpeg") else "",
                  "ma_san_pham_head": _lenh("git", "-C", MA, "rev-parse", "HEAD"),
                  "ma_san_pham_sua_doi": _lenh("git", "-C", MA, "status", "--porcelain", "--", ".")}
    _ghi_json(os.path.join(KET_QUA, "tong_hop.json"), {"moi_truong": moi_truong, "kich_ban": hang})


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # bảng mã PC2 = cp1252
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kich_ban", nargs="*", help=" ".join(THU_TU))
    ap.add_argument("--tat-ca", action="store_true")
    ap.add_argument("--tong-hop", action="store_true", help="chỉ dựng lại tong_hop.json")
    a = ap.parse_args()
    ds = THU_TU if a.tat_ca else a.kich_ban
    sai_ten = [x for x in ds if x not in kich_ban.KICH_BAN]
    if sai_ten:
        ap.error(f"không có kịch bản {sai_ten}")
    os.makedirs(KET_QUA, exist_ok=True)
    loi = 0
    for ten in ds:
        t0 = time.perf_counter()
        try:
            s = chay_mot(ten)
            print(f"[{ten}] {time.perf_counter() - t0:.0f} s — tìm thấy={s['tim_thay']} dòng={s['so_dong']} "
                  f"đầu clip={s['sai_so_dau_clip_s']} đầu vùng={s['sai_so_dau_vung_s']} cuối={s['sai_so_cuoi_s']} "
                  f"P={s['precision_giay']} R={s['recall_giay']}", flush=True)
        except Exception:  # noqa: BLE001 — một kịch bản hỏng không chặn các kịch bản khác
            loi += 1
            os.makedirs(os.path.join(KET_QUA, ten), exist_ok=True)
            with open(os.path.join(KET_QUA, ten, "loi.txt"), "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            print(f"[{ten}] LỖI — xem {os.path.join(KET_QUA, ten, 'loi.txt')}", flush=True)
    tong_hop()
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
