# -*- coding: utf-8 -*-
"""Engine THẬT trên từng CA ẨN (P-8) → ``ket_qua_engine.json`` — cấu hình MẶC ĐỊNH, ncores 2, tinh_chinh_moc TẮT.

Mỗi lượt: Engine(root = mã sản phẩm để tìm audfprint, data_dir/out_dir = thư mục TẠM xoá sau lượt), add_kho(kho/ của
ca), build_database(kho, "new"), scan_media(video). Ghi mọi Match của ``kq.matches`` và ``kq.matches_loai`` (clip,
duong_dan_kho, start_s, vung_khop_s, end_s, clip_offset_s, matched_s, hashes, moc_mo_ho, he_so, ho, neo, rồi các trường
còn lại) cùng so_dat_nguong, pham_vi_quet_s, duration_s, status, note. ``kq.matches`` rỗng → «engine_khong_thay» (giữ
ca). Một lượt engine một lúc (máy dùng chung). Không ghi .pyc (``-B`` + PYTHONDONTWRITEBYTECODE cho tiến trình con).

Chạy (Git Bash, từ thư mục này):
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \
      -B -X utf8 chay_engine.py [A01 A02 ...]      # không đối số = mọi ca; xong tự dựng tong_hop.json
  ... chay_engine.py --tong-hop                     # chỉ dựng lại <RA>/tong_hop.json từ các file đã có
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import dataclasses  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "TimClipPro"))  # checkout chứa file này
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\ca_an"
CHAN_MANG = os.path.join(os.path.dirname(MA), "tools", "test", "chan_mang")
TRUONG = ("clip", "duong_dan_kho", "start_s", "vung_khop_s", "end_s", "clip_offset_s", "matched_s", "hashes",
          "moc_mo_ho", "he_so", "ho", "neo")
CAU_HINH_GHI = ("chunk_s", "overlap_s", "overlap_max_s", "overlap_tu_dong", "min_hash", "min_match_s", "max_matches",
                "dedup_s", "shifts_kho", "shifts_quet", "ncores", "top_n", "min_hash_floor", "min_hash_strong",
                "quet_da_toc_do", "luoi_resample", "luoi_tempo", "phan_bo_deu", "uu_tien_clip_khac_nhau",
                "top1_tim_nhanh", "quet_tang_dan", "tinh_chinh_moc")


def _ds_ca() -> list:
    return sorted(x for x in os.listdir(RA) if os.path.isfile(os.path.join(RA, x, "su_that.json")))


def _doc(p: str):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _ghi(p: str, obj) -> None:
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


def _kiem_moi_truong() -> None:
    sc = sys.modules.get("sitecustomize")
    if sc is None or os.path.normcase(os.path.dirname(os.path.abspath(sc.__file__))) != os.path.normcase(CHAN_MANG):
        raise SystemExit(f"Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH={CHAN_MANG}")
    for bien in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_INSTALLATION_ID"):
        if os.environ.get(bien):
            raise SystemExit(f"Bỏ biến {bien} trước khi chạy: chỉ chạy legacy trên thư mục tạm.")
    for lenh in ("ffmpeg", "ffprobe"):
        if shutil.which(lenh) is None:
            raise SystemExit(f"Cần {lenh} trong PATH.")


def _dong(m) -> dict:
    x = dataclasses.asdict(m)
    return {**{k: x[k] for k in TRUONG}, **{k: v for k, v in x.items() if k not in TRUONG}}


def _git(*ts: str) -> str:
    return subprocess.run(["git", "-C", MA, *ts], capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout.strip()


def chay_mot(eng, ten: str) -> dict:
    d = os.path.join(RA, ten)
    st = _doc(os.path.join(d, "su_that.json"))
    tam = tempfile.mkdtemp(prefix=f"p8_ca_an_{ten.split('_')[0]}_")
    data, ra = os.path.join(tam, "data"), os.path.join(tam, "ketqua")
    os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = data, ra
    tien_do: list = []
    try:
        e = eng.Engine(root=MA, data_dir=data, out_dir=ra)
        for x in (e.data_dir, e.runtime.data_dir):
            assert os.path.normcase(x) == os.path.normcase(os.path.abspath(data)), x
        e.config.ncores = 2               # máy dùng chung (DEV 8502 đang chạy)
        assert e.config.tinh_chinh_moc is False
        kho = os.path.join(d, "kho")
        so_clip = sum(os.path.splitext(x)[1].lower() in eng.MEDIA_EXTS for x in os.listdir(kho))
        e.add_kho(f"Ca an {ten}", kho)
        t0 = time.perf_counter()
        kq_build = e.build_database(kho, "new")
        t_build = time.perf_counter() - t0
        if kq_build.get("thanh_cong") != so_clip:
            raise RuntimeError(f"Dựng kho không trọn: {kq_build}")
        t0 = time.perf_counter()
        kq = e.scan_media(os.path.join(d, st["video"]), progress=lambda p, m: tien_do.append(f"{p:.3f}\t{m}"))
        t_quet = time.perf_counter() - t0
        with open(os.path.join(MA, "engine.py"), "rb") as f:
            sha_engine = hashlib.sha256(f.read()).hexdigest()
        ket = {
            "ten": ten, "loai_ca": st["loai"],
            "ket_luan_engine": "co_ket_qua" if kq.matches else "engine_khong_thay",
            "status": kq.status, "note": kq.note, "so_dat_nguong": kq.so_dat_nguong,
            "pham_vi_quet_s": kq.pham_vi_quet_s, "duration_s": kq.duration_s,
            "matches": [_dong(m) for m in kq.matches],
            "matches_loai": [_dong(m) for m in kq.matches_loai],
            "tinh_chinh": getattr(kq, "tinh_chinh", None),
            "maxtimebits_kho": e._bits_kho_dang_dung(),
            "dung_kho": kq_build, "thoi_gian_dung_kho_s": round(t_build, 1), "thoi_gian_quet_s": round(t_quet, 1),
            "cau_hinh": {k: getattr(e.config, k, None) for k in CAU_HINH_GHI},
            "chinh_sach": getattr(kq, "chinh_sach", ""),
            "ma_san_pham": {"head": _git("rev-parse", "HEAD"), "sha256_engine_py": sha_engine,
                            "sua_doi_chua_commit": _git("status", "--porcelain", "--", ".")},
            "chay_luc": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _ghi(os.path.join(d, "ket_qua_engine.json"), ket)
        return ket
    finally:
        with open(os.path.join(d, "nhat_ky_tien_do.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(tien_do) + "\n")
        shutil.rmtree(tam, ignore_errors=True)


def _gon(m: dict) -> dict:
    return {"clip": m["clip"], "start_s": round(m["start_s"], 3), "vung_khop_s": round(m["vung_khop_s"], 3),
            "end_s": round(m["end_s"], 3), "clip_offset_s": round(m["clip_offset_s"], 3), "hashes": m["hashes"],
            "he_so": m["he_so"], "ho": m["ho"], "neo": m["neo"], "moc_mo_ho": m["moc_mo_ho"]}


def tong_hop() -> list:
    hang = []
    for ten in _ds_ca():
        d = os.path.join(RA, ten)
        st = _doc(os.path.join(d, "su_that.json"))
        h = {"ten": ten, "loai": st["loai"], "ky_vong": st["ky_vong"],
             "su_that": [{k: x[k] for k in ("clip", "video_tu", "video_den", "clip_tu", "clip_den", "he_so")}
                         for x in st["doan"]],
             "mep_mo": st["mep_mo"], "kiem_su_that": st.get("kiem_su_that", {}).get("ket_luan")}
        p = os.path.join(d, "ket_qua_engine.json")
        if os.path.exists(p):
            ke = _doc(p)
            h["engine"] = {"ket_luan": ke["ket_luan_engine"], "status": ke["status"],
                           "so_dat_nguong": ke["so_dat_nguong"], "maxtimebits_kho": ke["maxtimebits_kho"],
                           "thoi_gian_quet_s": ke["thoi_gian_quet_s"],
                           "matches": [_gon(m) for m in ke["matches"]],
                           "matches_loai": [_gon(m) for m in ke["matches_loai"]]}
        elif os.path.exists(os.path.join(d, "loi_engine.txt")):
            h["engine"] = {"ket_luan": "loi_khi_chay", "loi": open(os.path.join(d, "loi_engine.txt"),
                                                                   encoding="utf-8").read()[-1500:]}
        hang.append(h)
    _ghi(os.path.join(RA, "tong_hop.json"), {"ca": hang, "dung_luc": time.strftime("%Y-%m-%d %H:%M:%S")})
    return hang


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--tong-hop" in sys.argv:
        tong_hop()
        return 0
    _kiem_moi_truong()
    sys.path.insert(0, MA)
    import engine as eng

    tat_ca = _ds_ca()
    chon = [x for x in sys.argv[1:] if not x.startswith("--")]
    ds = [t for t in tat_ca if not chon or t in chon or t.split("_")[0] in chon]
    loi = 0
    for ten in ds:
        t0 = time.perf_counter()
        p_loi = os.path.join(RA, ten, "loi_engine.txt")
        try:
            ket = chay_mot(eng, ten)
            if os.path.exists(p_loi):
                os.remove(p_loi)
            print(f"[{ten}] {time.perf_counter() - t0:.0f} s — {ket['ket_luan_engine']} status={ket['status']} "
                  f"dòng={[(m['clip'], round(m['start_s'], 2), round(m['vung_khop_s'], 2), round(m['end_s'], 2), m['hashes'], m['he_so'], m['neo']) for m in ket['matches']]} "
                  f"loại={[(m['clip'], round(m['start_s'], 2), m['hashes']) for m in ket['matches_loai']]}", flush=True)
        except Exception:  # noqa: BLE001 — một ca hỏng không chặn ca khác
            loi += 1
            with open(p_loi, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            print(f"[{ten}] LỖI — xem {p_loi}", flush=True)
    tong_hop()
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
