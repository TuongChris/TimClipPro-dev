# -*- coding: utf-8 -*-
"""Phản biện HIỆU NĂNG (14/11/2026): engine THẬT trên audio giả lập dài — mốc thời gian của MỘT lượt quét để so với
chi phí tinh chỉnh. Không sửa mã sản phẩm: bọc ``_cut_chunks``/``_match_chunks``/``_merge`` ngay trong tiến trình này
(đo giờ; khúc WAV được HARDLINK ra ngoài trước khi engine xoá workspace — tức thì, không cộng vào thời gian quét).

Engine dựng như fixture ``engine`` của tests/conftest.py, data_dir/out_dir TẠM trong thư mục bằng chứng; ncores 2.
  dung_kho [w40]                 dựng «PB kho thuong» (16 bit: k01..k14 + goc_2h) và «PB kho dai» (D-34, 21 bit: goc_2h)
  quet <A|B> <thuong|dai> [top_n] quét video_<A|B>.webm, ghi quet_<A|B>_<kho>/ket_qua.json + khuc/chunk_*.wav
Chạy: PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B chay_engine.py <lệnh>
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import dataclasses  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402

MA = r"C:\Dev\Tool_Quet\TimClipPro"
GOC = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_hieu_nang"
DU_LIEU = os.path.join(GOC, "du_lieu")
CHAN_MANG = r"C:\Dev\Tool_Quet\tools\test\chan_mang"
KHO = {"thuong": ("PB kho thuong", os.path.join(DU_LIEU, "kho")),
       "dai": ("PB kho dai", os.path.join(DU_LIEU, "kho_dai")),
       "w40": ("PB kho w40", os.path.join(DU_LIEU, "kho_w40"))}         # kho THƯỜNG 16 bit, clip 40 phút (cuộn mốc)

sc = sys.modules.get("sitecustomize")
if sc is None or os.path.normcase(os.path.dirname(os.path.abspath(sc.__file__))) != os.path.normcase(CHAN_MANG):
    raise SystemExit(f"Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH={CHAN_MANG}")
for _b in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_INSTALLATION_ID"):
    if os.environ.get(_b):
        raise SystemExit(f"Bỏ biến {_b}: chỉ chạy legacy trên thư mục tạm.")
DATA, KETQUA = os.path.join(GOC, "_engine", "data"), os.path.join(GOC, "_engine", "ketqua")
os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = DATA, KETQUA
sys.path.insert(0, MA)
import engine as eng  # noqa: E402

_DO: dict = {"khuc_ra": None, "cat_s": 0.0, "khop_s": 0.0, "merge_s": 0.0, "goi_khop": []}
_GOC_CAT, _GOC_KHOP, _GOC_MERGE = eng.Engine._cut_chunks, eng.Engine._match_chunks, eng.Engine._merge


def _cat(self, *a, **kw):
    t = time.perf_counter()
    try:
        return _GOC_CAT(self, *a, **kw)
    finally:
        _DO["cat_s"] += time.perf_counter() - t


def _khop(self, chunks, *a, **kw):
    t = time.perf_counter()
    try:
        return _GOC_KHOP(self, chunks, *a, **kw)
    finally:
        _DO["khop_s"] += time.perf_counter() - t
        _DO["goi_khop"].append({"khuc": [os.path.basename(c) for c in chunks], "luot_bu": kw.get("luot_bu", ""),
                                "giay": round(time.perf_counter() - t, 2)})
        d = _DO["khuc_ra"]
        for c in chunks:                                  # hardlink: tức thì, sống sót khi engine xoá workspace
            dich = os.path.join(d, os.path.basename(c)) if d else None
            if dich and os.path.exists(c) and not os.path.exists(dich):
                os.link(c, dich)


def _merge(self, tho):
    t = time.perf_counter()
    try:
        return _GOC_MERGE(self, tho)
    finally:
        _DO["merge_s"] += time.perf_counter() - t


eng.Engine._cut_chunks, eng.Engine._match_chunks, eng.Engine._merge = _cat, _khop, _merge


def _engine() -> "eng.Engine":
    e = eng.Engine(root=MA, data_dir=DATA, out_dir=KETQUA)
    assert os.path.normcase(e.data_dir) == os.path.normcase(os.path.abspath(DATA)), e.data_dir
    e.config.ncores = 2           # máy đang chạy DEV 8502: không chiếm hết CPU
    return e


def dung_kho(chi: str | None = None) -> None:
    if chi is None and os.path.isdir(os.path.join(GOC, "_engine")):
        shutil.rmtree(os.path.join(GOC, "_engine"))
    e = _engine()
    ra = {}
    for k, (ten, thu_muc) in KHO.items():
        if (chi is None and k == "w40") or (chi is not None and k != chi):
            continue
        e.add_kho(ten, thu_muc)
        t = time.perf_counter()
        kq = e.build_database(thu_muc, "new")
        ra[k] = {"ten": ten, "giay": round(time.perf_counter() - t, 1), "ket_qua": kq,
                 "maxtimebits": e._bits_kho_dang_dung()}
        print(k, ra[k]["giay"], "s", kq, "bits", ra[k]["maxtimebits"], flush=True)
    with open(os.path.join(GOC, f"dung_kho{'_' + chi if chi else ''}.json"), "w", encoding="utf-8") as f:
        json.dump(ra, f, ensure_ascii=False, indent=1, default=str)


def quet(video: str, kho: str, top_n: int | None) -> None:
    ra_dir = os.path.join(GOC, f"quet_{video}_{kho}" + (f"_top{top_n}" if top_n else ""))
    if os.path.isdir(ra_dir):
        shutil.rmtree(ra_dir)
    os.makedirs(os.path.join(ra_dir, "khuc"))
    e = _engine()
    e.use_kho(KHO[kho][0])
    if top_n:
        e.config.top_n = top_n
    e.config.validate()
    _DO.update(khuc_ra=os.path.join(ra_dir, "khuc"), cat_s=0.0, khop_s=0.0, merge_s=0.0, goi_khop=[])
    tien_do: list = []
    t0 = time.perf_counter()
    kq = e.scan_media(os.path.join(DU_LIEU, f"video_{video}.webm"),
                      progress=lambda p, m: tien_do.append(f"{time.perf_counter() - t0:8.2f}\t{p:.3f}\t{m}"))
    t_quet = time.perf_counter() - t0
    asdict = dataclasses.asdict
    ket = {"video": video, "kho": kho, "trang_thai": kq.status, "ghi_chu": kq.note,
           "thoi_gian_quet_s": round(t_quet, 2), "cat_khuc_s": round(_DO["cat_s"], 2),
           "khop_s": round(_DO["khop_s"], 2), "merge_s": round(_DO["merge_s"], 3), "goi_khop": _DO["goi_khop"],
           "cau_hinh": {k: getattr(e.config, k) for k in ("chunk_s", "overlap_s", "overlap_max_s", "top_n", "ncores",
                                                          "max_matches", "dedup_s", "quet_da_toc_do", "phan_bo_deu")},
           "duration_s": kq.duration_s, "so_dat_nguong": kq.so_dat_nguong,
           "matches": [asdict(m) for m in kq.matches], "matches_loai": [asdict(m) for m in kq.matches_loai],
           "ung_vien_dat": [asdict(m) for m in (getattr(kq, "ung_vien_dat", None) or [])],
           "khuc": sorted(os.listdir(os.path.join(ra_dir, "khuc"))),
           "chan_doan": asdict(kq.chan_doan) if dataclasses.is_dataclass(kq.chan_doan) else str(kq.chan_doan)}
    with open(os.path.join(ra_dir, "ket_qua.json"), "w", encoding="utf-8") as f:
        json.dump(ket, f, ensure_ascii=False, indent=1, default=str)
    with open(os.path.join(ra_dir, "tien_do.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(tien_do) + "\n")
    print(f"quét {video}/{kho}: {t_quet:.1f} s (cắt {_DO['cat_s']:.1f}, khớp {_DO['khop_s']:.1f}, merge "
          f"{_DO['merge_s']:.2f}); {len(kq.matches)} chọn, {kq.so_dat_nguong} đạt, {len(kq.matches_loai)} loại; "
          f"{kq.status} {kq.note[:200]!r}", flush=True)
    for m in kq.matches:
        print(f"  {m.clip} start {m.start_s} vung {m.vung_khop_s} end {m.end_s} off {m.clip_offset_s} "
              f"matched {m.matched_s} hash {m.hashes}", flush=True)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    if a[:1] == ["dung_kho"]:
        dung_kho(a[1] if len(a) > 1 else None)
    elif a[:1] == ["quet"] and len(a) in (3, 4):
        quet(a[1], a[2], int(a[3]) if len(a) == 4 else None)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
