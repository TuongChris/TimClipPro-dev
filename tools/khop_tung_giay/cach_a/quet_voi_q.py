# -*- coding: utf-8 -*-
"""Cách A, phần 2 — TÁC DỤNG PHỤ của -Q lên NHẬN DIỆN: ``engine.scan_media`` THẬT, chỉ khác là lệnh
``audfprint match`` được thêm ``--time-quantile <Q>`` bằng cách bọc ``Engine._audfprint_cmd`` NGAY TRONG tiến trình đo
(như monkeypatch của pytest) — không sửa engine.py, không sửa audfprint-master.

Mỗi kịch bản: chép clip gốc sang thư mục kết quả, dựng kho MỘT lần (engine.build_database), rồi quét 4 lần (Q mặc định
0.05, 0.02, 0.01, 0) bằng 4 Engine mới trên CÙNG data_dir tạm ⇒ mọi so sánh giữa các Q dùng CÙNG một kho (bảng hash
audfprint bỏ ngẫu nhiên phần tràn của ô quá đầy khi DỰNG — kho dựng lại có thể lệch bo_thu chút ít ở âm thanh lặp).

Kịch bản: mọi tên của bo_thu (S0…S9, chỉ đọc), thêm video DÀI 60 phút (tự dựng, audio giả lập của repo; kho = 9 clip S0):
  L0 — 3600 s TOÀN nốt ngẫu nhiên (seed 2101), không có clip (đối chứng âm dài);
  L1 — nền nốt ngẫu nhiên + nhạc có nhịp cùng mẫu kick với goc_S6/S6b; goc_S6 trọn ở 960 s (CÙNG PHA nhịp), goc_S1 trọn
       ở 1700 s, goc_S6b[40..200] ở 2560 s (cùng pha phía trước) — ca xấu nhất cho «hash tình cờ kéo mốc» (quét rất chậm,
       ~9 phút/lượt, nên chỉ chạy Q 0.05 và 0);
  L2 — nền của L0 + goc_S1 trọn ở 600 s và 3 đoạn trích (goc_S3[200..320], goc_S9[360..420], goc_S7[0..60]).
Chạy (Git Bash, mỗi lệnh < 10 phút):
  cd /c/Dev/pc2_test_tools/khop_tung_giay/cach_a
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \
      -B quet_voi_q.py S0 S5 S6 [--q 0.05 0]     |    quet_voi_q.py --tong-hop
"""
from __future__ import annotations

import argparse
import dataclasses
import glob
import inspect
import os
import shutil
import sqlite3
import sys
import time

import chung as c

THU_MUC = os.path.join(c.KET_QUA, "quet")
KB_DAI = ("L0", "L1", "L2")
TAT_CA = [*c.KICH_BAN, *KB_DAI]

_GHI: dict = {"thu_muc": None, "merge": [], "lenh": [], "q": None}


def _cai_boc(eng) -> None:
    """Bọc 3 phương thức của lớp Engine trong tiến trình này (bản ghim của job dùng chung lớp nên cũng đi qua)."""
    goc_cmd, goc_match, goc_merge = eng.Engine._audfprint_cmd, eng.Engine._match_chunks, eng.Engine._merge
    ky_match = inspect.signature(goc_match)

    def cmd(self, sub, *them, db_file=None):
        lenh = goc_cmd(self, sub, *them, db_file=db_file)
        if sub == "match":
            if _GHI["q"] is not None:
                lenh = [*lenh, "--time-quantile", repr(_GHI["q"])]
            _GHI["lenh"].append([str(x) for x in lenh[3:]])
        return lenh

    def match(self, chunks, *a, **kw):
        try:
            return goc_match(self, chunks, *a, **kw)
        finally:
            d = _GHI["thu_muc"]
            if d:
                ts = ky_match.bind(self, chunks, *a, **kw).arguments
                op = os.path.join(ts.get("workspace") or self.data_dir, f"_raw_match{ts.get('hau_to', '')}.txt")
                if os.path.exists(op):          # chép TRƯỚC khi engine xoá workspace
                    os.makedirs(os.path.join(d, "raw"), exist_ok=True)
                    shutil.copy2(op, os.path.join(d, "raw", os.path.basename(op)))

    def merge(self, tho):
        ra = goc_merge(self, tho)
        _GHI["merge"].append({"tho": [dict(x) for x in tho], "ra": [dataclasses.asdict(m) for m in ra]})
        return ra

    eng.Engine._audfprint_cmd, eng.Engine._match_chunks, eng.Engine._merge = cmd, match, merge


# ---------------------------------------------------------------- dữ liệu kịch bản
def _tao_dai(d: str, ten: str) -> dict:
    """Video 3600 s (L0/L1/L2) + kho = 9 clip của bo_thu/S0 (chép). Mọi mốc sự thật tính từ cách dựng."""
    import numpy as np

    import kich_ban as kb                         # bo_thu: bộ sinh của repo (chỉ import, không ghi gì)
    from am_thanh_lap import O_NHIP, SR, nhac_co_nhip
    from conftest import _giai_dieu

    nua_o = O_NHIP / 2                            # 120/113 s: 113 nửa ô nhịp = đúng 120 s ⇒ mốc «cùng pha nhịp»
    if ten == "L1":
        khoi = [(0, _giai_dieu(600, seed=2001, sr=SR)), (600, nhac_co_nhip(900, seed=2002)),
                (1500, _giai_dieu(900, seed=2003, sr=SR)), (2400, nhac_co_nhip(600, seed=2004)),
                (3000, _giai_dieu(600, seed=2005, sr=SR))]
    else:                                         # L0/L2: TOÀN nốt ngẫu nhiên (đúng «nền ngẫu nhiên» của đề bài)
        khoi = [(0, _giai_dieu(3600, seed=2101, sr=SR))]
    nen = np.concatenate([x for _, x in khoi])
    assert len(nen) == 3600 * SR
    kho = os.path.join(d, "kho")
    os.makedirs(kho, exist_ok=True)
    for f in sorted(glob.glob(os.path.join(c.BO_THU, "S0", "kho", "*.wav"))):
        shutil.copy2(f, kho)
    doan: dict = {}
    chen: list = []
    if ten == "L1":
        s6b = kb.CLIP_THEO_KICH_BAN["goc_S6b.wav"]()
        chen = [("goc_S6.wav", kb.CLIP_THEO_KICH_BAN["goc_S6.wav"](), 960, 0, 360),
                ("goc_S1.wav", kb.CLIP_THEO_KICH_BAN["goc_S1.wav"](), 1700, 0, 420),
                ("goc_S6b.wav", s6b[kb._i(40):kb._i(200)], 2560, 40, 200)]
        for ten_clip, sig, P, c0, c1 in chen:
            nen = kb._chen(nen, sig, P)
            doan[ten_clip] = [kb._doan(P, c0, c1)]
        # Cùng pha nhịp: (mốc ảo giây 0 của clip − đầu khối nhạc nền) là bội số nửa ô nhịp.
        for P0, khoi_tu in ((960 - 0, 600), (2560 - 40, 2400)):
            so_nua_o = (P0 - khoi_tu) / nua_o
            assert abs(so_nua_o - round(so_nua_o)) < 1e-6, so_nua_o
    elif ten == "L2":
        # 1 clip trọn + 3 đoạn trích: «vùng ảo» (chỗ clip lẽ ra nằm nếu dùng trọn) rơi vào nền ngẫu nhiên.
        lay = kb.CLIP_THEO_KICH_BAN
        chen = [("goc_S1.wav", lay["goc_S1.wav"](), 600, 0, 420),
                ("goc_S3.wav", lay["goc_S3.wav"]()[kb._i(200):kb._i(320)], 1800, 200, 320),
                ("goc_S9.wav", lay["goc_S9.wav"]()[kb._i(360):kb._i(420)], 2400, 360, 420),
                ("goc_S7.wav", lay["goc_S7.wav"]()[kb._i(0):kb._i(60)], 3000, 0, 60)]
        for ten_clip, sig, P, c0, c1 in chen:
            nen = kb._chen(nen, sig, P)
            doan[ten_clip] = [kb._doan(P, c0, c1)]
    v = kb._ghi_video(d, nen)
    # Kiểm sự thật: vùng chèn trong video (int16 sau khi ghi) trùng TỪNG MẪU với clip trong kho.
    kiem = {}
    if chen:
        vid = kb._doc_wav(os.path.join(d, v))
        for ten_clip, _, P, c0, c1 in chen:
            goc = kb._doc_wav(os.path.join(kho, ten_clip))
            a = vid[kb._i(P): kb._i(P) + kb._i(c1 - c0)]
            kiem[ten_clip] = bool(np.array_equal(a, goc[kb._i(c0): kb._i(c0) + len(a)]))
        assert all(kiem.values()), kiem
    mo_ta = {"L0": "Video DÀI 3600 s TOÀN nền nốt ngẫu nhiên (seed 2101), KHÔNG chứa clip nào; kho = 9 clip của S0.",
             "L1": "Nền 3600 s: nốt ngẫu nhiên 2001/2003/2005 + nhạc có nhịp 2002/2004 (cùng mẫu kick với goc_S6/S6b); "
                   "goc_S6 trọn ở 960 s (giữa nhạc có nhịp, cùng pha), goc_S1 trọn ở 1700 s (giữa nốt ngẫu nhiên), "
                   "goc_S6b[40..200] ở 2560 s (giữa nhạc có nhịp, cùng pha phía trước); kho = 9 clip của S0.",
             "L2": "Nền của L0 (3600 s nốt ngẫu nhiên 2101) + goc_S1 trọn ở 600 s, goc_S3[200..320] ở 1800 s, "
                   "goc_S9[360..420] ở 2400 s, goc_S7[0..60] ở 3000 s; kho = 9 clip của S0."}
    return {"kich_ban": ten, "mo_ta": mo_ta[ten], "video": v, "do_dai_video_s": 3600.0, "ten_clip": "", "doan": [],
            "doan_theo_clip": doan, "khoi_nen": [(t, len(x) / SR) for t, x in khoi], "cau_hinh_engine_doi": {},
            "kiem_su_that_trung_tung_mau": kiem}


def chuan_bi(ten: str) -> tuple:
    """(thư mục kịch bản, su_that, đường dẫn video). bo_thu chỉ ĐỌC: clip gốc được chép, video đọc tại chỗ."""
    d = os.path.join(THU_MUC, ten)
    os.makedirs(d, exist_ok=True)
    p_st = os.path.join(d, "su_that.json")
    if ten in KB_DAI:
        if not os.path.exists(p_st):
            c.ghi_json(p_st, _tao_dai(d, ten))
        st = c.doc_json(p_st)
        return d, st, os.path.join(d, st["video"])
    bt = os.path.join(c.BO_THU, ten)
    st = c.doc_json(os.path.join(bt, "su_that.json"))
    st["doan_theo_clip"] = {st["ten_clip"]: st["doan"]} if st["ten_clip"] else {}
    kho = os.path.join(d, "kho")
    if not os.path.isdir(kho):
        shutil.copytree(os.path.join(bt, "kho"), kho)
    c.ghi_json(p_st, st)
    return d, st, os.path.join(bt, st["video"])


def _engine(eng, d: str, st: dict):
    data, ketqua = os.path.join(d, "_engine", "data"), os.path.join(d, "_engine", "ketqua")
    os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = data, ketqua
    e = eng.Engine(root=c.MA, data_dir=data, out_dir=ketqua)
    assert os.path.normcase(e.data_dir) == os.path.normcase(os.path.abspath(data)), e.data_dir
    assert os.path.normcase(e.runtime.data_dir) == os.path.normcase(os.path.abspath(data)), e.runtime.data_dir
    e.config.ncores = 2           # máy đang chạy DEV 8502: không chiếm hết CPU
    for k, v in st.get("cau_hinh_engine_doi", {}).items():
        setattr(e.config, k, v)
    e.config.validate()
    return e


def dung_kho(eng, ten: str, d: str, st: dict) -> dict:
    p = os.path.join(d, "kho_da_dung.json")
    if os.path.exists(p):
        return c.doc_json(p)
    e = _engine(eng, d, st)
    kho = os.path.join(d, "kho")
    e.add_kho(f"Cach A {ten}", kho)
    t0 = time.perf_counter()
    kq = e.build_database(kho, "new")
    so_clip = len(os.listdir(kho))
    if kq.get("thanh_cong") != so_clip:
        raise RuntimeError(f"Dựng kho không trọn: {kq}")
    ra = {"thoi_gian_s": round(time.perf_counter() - t0, 1), "so_clip": so_clip, "db_file": e.db_file}
    c.ghi_json(p, ra)
    return ra


# ---------------------------------------------------------------- một lượt quét
TRUONG_DONG = ("clip", "start_s", "vung_khop_s", "end_s", "matched_s", "clip_offset_s", "hashes", "ty_le", "confidence",
               "moc_mo_ho", "ty_so_doi_thu")
TRUONG_CD = ("so_khuc", "dong_tho", "parse_duoc", "qua_min_hash", "qua_min_match_s", "gop_lai", "duoc_chap_nhan",
             "da_chon", "hash_tho_lon_nhat", "khop_tho_dai_nhat", "so_khuc_cham_tran", "giai_doan_mat", "duong_di",
             "da_thu_toc_do", "toc_do_tim_duoc", "ly_do_khong_bu_toc_do", "manh_nhat_bi_loai")


def _dong(m) -> dict:
    x = dataclasses.asdict(m)
    return {k: (round(x[k], 3) if isinstance(x.get(k), float) else x.get(k)) for k in TRUONG_DONG}


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
    return [{"clip": x.goc.clip, "giay_bat_dau": x.giay_bat_dau, "giay_ket_thuc": x.giay_ket_thuc}
            for x in getattr(bc, "doan", ()) or ()]


def quet_mot(eng, d: str, st: dict, video: str, q) -> dict:
    import danh_gia
    tq = c.ten_q(q)
    dq = os.path.join(d, tq)
    if os.path.isdir(dq):
        shutil.rmtree(dq)
    os.makedirs(dq)
    e = _engine(eng, d, st)
    _GHI.update(thu_muc=dq, merge=[], lenh=[], q=q)
    tien_do: list = []
    t0 = time.perf_counter()
    try:
        kq = e.scan_media(video, progress=lambda p, m: tien_do.append(f"{p:.3f}\t{m}"))
    finally:
        _GHI["thu_muc"] = None
    t_quet = time.perf_counter() - t0
    with open(os.path.join(dq, "nhat_ky_tien_do.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(tien_do) + "\n")
    # Bằng chứng -Q đã vào ĐÚNG mọi lệnh match (và không có ở Q mặc định).
    for lenh in _GHI["lenh"]:
        co = "--time-quantile" in lenh
        if co != (q is not None) or (co and lenh[lenh.index("--time-quantile") + 1] != repr(q)):
            raise RuntimeError(f"Lệnh match không mang đúng -Q={q}: {lenh}")
    cd = dataclasses.asdict(kq.chan_doan) if dataclasses.is_dataclass(kq.chan_doan) else {}
    cuoi = _GHI["merge"][-1] if _GHI["merge"] else {"tho": [], "ra": []}
    theo_clip = {}
    for ten_clip, doan in st["doan_theo_clip"].items():
        dong = [dataclasses.asdict(m) for m in kq.matches if m.clip == ten_clip]
        loai = [dataclasses.asdict(m) for m in kq.matches_loai if m.clip == ten_clip]
        theo_clip[ten_clip] = {"bao_cao": danh_gia.danh_gia({"doan": doan}, dong),
                               "dong_bi_loai": danh_gia.danh_gia({"doan": doan}, loai) if loai else None}
    clip_that = set(st["doan_theo_clip"])
    ket = {
        "kich_ban": st["kich_ban"], "q": 0.05 if q is None else q, "truyen_tham_so_Q": q is not None,
        "trang_thai": kq.status, "ghi_chu_engine": kq.note, "thoi_gian_quet_s": round(t_quet, 1),
        "lenh_match": _GHI["lenh"],
        "so_dong_bao_cao": len(kq.matches), "so_dat_nguong": kq.so_dat_nguong,
        "dong_bao_cao": [_dong(m) for m in kq.matches],
        "ung_vien_dat": [_dong(m) for m in (getattr(kq, "ung_vien_dat", None) or [])],
        "dong_bi_loai": [_dong(m) for m in kq.matches_loai],
        "duong_tinh_gia": [_dong(m) for m in kq.matches if m.clip not in clip_that],
        "chan_doan": {k: cd.get(k) for k in TRUONG_CD},
        "merge_cuoi": {"so_lan_goi_merge": len(_GHI["merge"]), "so_manh_vao": len(cuoi["tho"]),
                       "so_nhom_ra": len(cuoi["ra"]),
                       "nhom_ra": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in g.items()
                                    if k in TRUONG_DONG} for g in cuoi["ra"]]},
        "theo_clip_su_that": theo_clip,
        "bao_cao_v2_doan": _bao_cao_v2(kq),
        "lich_su_matches": _lich_su(e.sqlite_file, kq.job_id),
    }
    c.ghi_json(os.path.join(dq, "ket_qua.json"), ket)
    c.ghi_json(os.path.join(dq, "merge_day_du.json"), _GHI["merge"])
    return ket


# ---------------------------------------------------------------- tổng hợp + so với Q mặc định
def _tap_chap_nhan(ket: dict) -> list:
    return sorted((m["clip"], round(m["start_s"], 1)) for m in ket["ung_vien_dat"])


def so_voi_goc(goc: dict, moi: dict) -> dict:
    """Những gì -Q mới làm ĐỔI so với Q mặc định — thứ golden/chính sách nhận diện quan tâm."""
    def gan_bang(a, b, tol=1.0):
        return len(a) == len(b) and all(x[0] == y[0] and abs(x[1] - y[1]) <= tol for x, y in zip(a, b))
    a, b = _tap_chap_nhan(goc), _tap_chap_nhan(moi)
    bc_a = sorted((m["clip"], m["start_s"]) for m in goc["dong_bao_cao"])
    bc_b = sorted((m["clip"], m["start_s"]) for m in moi["dong_bao_cao"])
    moc = []
    if len(bc_a) == len(bc_b):
        moc = [{"clip": x[0], "start_goc": x[1], "start_moi": y[1]} for x, y in zip(bc_a, bc_b)
               if x[0] != y[0] or abs(x[1] - y[1]) > 0.15]
    cda, cdb = goc["chan_doan"], moi["chan_doan"]
    return {
        "doi_tap_ung_vien_dat": not gan_bang(a, b),
        "ung_vien_dat_goc": a if not gan_bang(a, b) else None, "ung_vien_dat_moi": b if not gan_bang(a, b) else None,
        "doi_so_dong_bao_cao": len(goc["dong_bao_cao"]) != len(moi["dong_bao_cao"]),
        "doi_clip_bao_cao": sorted(m["clip"] for m in goc["dong_bao_cao"]) != sorted(m["clip"] for m in moi["dong_bao_cao"]),
        "doi_moc_dau_clip_tren_0_15s": moc,
        "doi_moc_mo_ho": sorted((m["clip"], m["moc_mo_ho"]) for m in goc["dong_bao_cao"])
        != sorted((m["clip"], m["moc_mo_ho"]) for m in moi["dong_bao_cao"]),
        "doi_luot_bu_toc_do": cda.get("da_thu_toc_do") != cdb.get("da_thu_toc_do"),
        "qua_min_match_s": [cda.get("qua_min_match_s"), cdb.get("qua_min_match_s")],
        "gop_lai": [cda.get("gop_lai"), cdb.get("gop_lai")],
        "so_dong_bi_loai": [len(goc["dong_bi_loai"]), len(moi["dong_bi_loai"])],
        "so_nhom_sau_merge": [goc["merge_cuoi"]["so_nhom_ra"], moi["merge_cuoi"]["so_nhom_ra"]],
        "duong_tinh_gia": [len(goc["duong_tinh_gia"]), len(moi["duong_tinh_gia"])],
    }


def tong_hop() -> dict:
    hang = []
    for ten in TAT_CA:
        theo_q = {}
        for q in c.CAC_Q:
            p = os.path.join(THU_MUC, ten, c.ten_q(q), "ket_qua.json")
            if os.path.exists(p):
                theo_q[c.ten_q(q)] = c.doc_json(p)
        if not theo_q:
            continue
        muc = {"kich_ban": ten, "theo_q": {}}
        for tq, k in theo_q.items():
            muc["theo_q"][tq] = {
                "thoi_gian_quet_s": k["thoi_gian_quet_s"], "so_dong_bao_cao": k["so_dong_bao_cao"],
                "so_dat_nguong": k["so_dat_nguong"], "duong_tinh_gia": len(k["duong_tinh_gia"]),
                "theo_clip": {tc: {kk: v["bao_cao"].get(kk) for kk in (
                    "so_dong", "sai_so_dau_clip_s", "sai_so_dau_vung_s", "sai_so_cuoi_s", "precision_giay",
                    "recall_giay", "precision_giay_tu_vung_khop", "recall_giay_tu_vung_khop")}
                    | {"tung_dong": v["bao_cao"].get("tung_dong"),
                       "dong_bi_loai": (v["dong_bi_loai"] or {}).get("tung_dong")}
                    for tc, v in k["theo_clip_su_that"].items()},
                "chan_doan": {kk: k["chan_doan"].get(kk) for kk in ("qua_min_hash", "qua_min_match_s", "gop_lai",
                                                                     "duoc_chap_nhan", "da_chon", "giai_doan_mat",
                                                                     "da_thu_toc_do")},
            }
            if tq != "Q0.05" and "Q0.05" in theo_q:
                muc["theo_q"][tq]["so_voi_Q0.05"] = so_voi_goc(theo_q["Q0.05"], k)
        hang.append(muc)
    out = {"ghi_chu": "engine.scan_media THẬT, -Q chèn vào mọi lệnh audfprint match (lenh_match trong từng ket_qua.json "
                      "là bằng chứng). Sai số theo danh_gia.py của bo_thu: đầu vùng dương = trễ, cuối âm = sớm.",
           "kich_ban": hang}
    c.ghi_json(os.path.join(THU_MUC, "tong_hop.json"), out)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c.kiem_moi_truong()
    c.kiem_parser_giong_engine()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kich_ban", nargs="*")
    ap.add_argument("--q", nargs="*", type=float, help="tập con của 0.05 0.02 0.01 0 (mặc định: cả bốn)")
    ap.add_argument("--tong-hop", action="store_true")
    a = ap.parse_args()
    for ten in a.kich_ban:
        if ten not in TAT_CA:
            ap.error(f"không có kịch bản {ten}")
    cac_q = [q for q in c.CAC_Q if a.q is None or (0.05 if q is None else q) in a.q]
    if a.kich_ban:
        sys.path.insert(0, c.CONG_CU_BO_THU)
        sys.path.insert(0, c.MA)
        import engine as eng
        _cai_boc(eng)
        for ten in a.kich_ban:
            d, st, video = chuan_bi(ten)
            kd = dung_kho(eng, ten, d, st)
            for q in cac_q:
                k = quet_mot(eng, d, st, video, q)
                tc = {x: (v["bao_cao"]["sai_so_dau_vung_s"], v["bao_cao"]["sai_so_cuoi_s"], v["bao_cao"]["so_dong"])
                      for x, v in k["theo_clip_su_that"].items()}
                print(f"[{ten}] {c.ten_q(q)}: {k['thoi_gian_quet_s']} s (kho {kd['thoi_gian_s']} s) dòng={k['so_dong_bao_cao']}"
                      f" đạt={k['so_dat_nguong']} dương giả={len(k['duong_tinh_gia'])} lệnh={len(k['lenh_match'])}"
                      f" (đầu vùng, cuối, số dòng)={tc}", flush=True)
    tong_hop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
