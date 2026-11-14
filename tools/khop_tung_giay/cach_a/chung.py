# -*- coding: utf-8 -*-
"""Dùng chung cho bộ đo «Cách A — chỉ đổi --time-quantile (-Q) của audfprint» (14/11/2026).

Chỉ ĐỌC mã sản phẩm (C:\\Dev\\Tool_Quet\\TimClipPro) và bộ thử bước trước (bo_thu); mọi thứ ghi ra nằm trong KET_QUA.
Không sửa engine.py: -Q được chèn bằng cách bọc ``Engine._audfprint_cmd`` NGAY TRONG tiến trình đo (quet_voi_q.py).
Tự kiểm phần thuần: ``python chung.py``.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import wave  # noqa: E402

MA = r"C:\Dev\Tool_Quet\TimClipPro"
AUDFPRINT = os.path.join(MA, "audfprint-master", "audfprint.py")
BO_THU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"
CONG_CU_BO_THU = r"C:\Dev\pc2_test_tools\khop_tung_giay\bo_thu"
KET_QUA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_a"
CHAN_MANG = r"C:\Dev\Tool_Quet\tools\test\chan_mang"
CAC_Q = (None, 0.02, 0.01, 0.0)     # None = KHÔNG truyền -Q → mặc định CLI 0.05 = hành vi hiện tại
KICH_BAN = ["S1", "S2", "S3", "S4", "S4b", "S5", "S5b", "S6", "S6b", "S7", "S7b", "S7c", "S8", "S9", "S0"]
MIN_HASH, MIN_MATCH_S, DEDUP_S = 15, 5.0, 20.0     # Config mặc định của engine (đọc lại ở quet_voi_q.py)


def ten_q(q) -> str:
    return "Q0.05" if q is None else f"Q{q:g}"


def kiem_moi_truong() -> None:
    sc = sys.modules.get("sitecustomize")
    if sc is None or os.path.normcase(os.path.dirname(os.path.abspath(sc.__file__))) != os.path.normcase(CHAN_MANG):
        raise SystemExit(f"Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH={CHAN_MANG}")
    for bien in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_INSTALLATION_ID"):
        if os.environ.get(bien):
            raise SystemExit(f"Bỏ biến {bien}: bộ đo chỉ chạy legacy trên thư mục tạm.")
    for lenh in ("ffmpeg", "ffprobe"):
        if shutil.which(lenh) is None:
            raise SystemExit(f"Cần {lenh} trong PATH.")


def ghi_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


def doc_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def do_dai_wav(path: str) -> float:
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


# ---------------------------------------------------------------- parser (giống Engine._match_chunks)
RE_MATCH = re.compile(
    r"Matched\s+([\d.]+)\s+s\s+starting\s+at\s+([\d.]+)\s+s\s+in\s+(.+?)"
    r"\s+to\s+time\s+(-?[\d.]+)\s+s\s+in\s+(.+?)\s+with\s+(\d+)\s+of\s+(\d+)\s+common\s+hashes"
    r"(?:\s+at\s+rank\s+(\d+))?")
RE_TEN_KHUC = re.compile(r"chunk_(\d+)(?:_k(\d+))?\.wav")


def doc_dong(dong: str):
    """Một dòng «Matched …» → mảnh thô ĐÚNG công thức của ``Engine._match_chunks`` (+ tổng hash, hạng).

    RE_MATCH/RE_TEN_KHUC chép từ engine.py (dòng ~1000) — ``kiem_parser_giong_engine`` so lại khi chạy."""
    m = RE_MATCH.search(dong)
    if not m:
        return None
    khop, t_khuc, file_khuc, t_clip, file_clip, n, tong, hang = m.groups()
    ten_khuc = os.path.basename(file_khuc.strip())
    mk = RE_TEN_KHUC.search(ten_khuc)
    k = int(mk.group(2)) / 100000.0 if mk and mk.group(2) else 1.0
    bat_dau = (int(mk.group(1)) if mk else 0) + float(t_khuc) * k
    tc = max(0.0, float(t_clip))
    return {"khuc": ten_khuc, "clip": os.path.basename(file_clip.strip()), "bat_dau": round(bat_dau, 4),
            "khop": round(float(khop) * k, 4), "t_clip": tc, "hash": int(n), "tong": int(tong),
            "hang": int(hang) if hang is not None else None, "he_so": k, "align": round(bat_dau - k * tc, 4)}


def kiem_parser_giong_engine() -> None:
    """Regex chép tay phải trùng engine (đổi định dạng ở engine thì dừng, không đo nhầm)."""
    sys.path.insert(0, MA)
    import engine as eng
    assert RE_MATCH.pattern.startswith(eng.RE_MATCH.pattern), "RE_MATCH của engine đã đổi"
    assert RE_TEN_KHUC.pattern == eng.RE_TEN_KHUC.pattern, "RE_TEN_KHUC của engine đã đổi"


def doc_raw(path: str) -> list:
    ra = []
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            for dong in f:
                x = doc_dong(dong) if "Matched" in dong else None
                if x:
                    ra.append(x)
    return ra


# ---------------------------------------------------------------- so mảnh thô với sự thật
def vi_tri_that(d: dict, t_clip: float) -> float:
    """Mốc trên trục video của giây ``t_clip`` của clip theo đoạn sự thật ``d`` (kéo dài tuyến tính ra ngoài đoạn)."""
    return d["video_tu"] + (t_clip - d["clip_tu"]) / d["he_so"]


def phan_loai(x: dict, doan: list, ten_clip: str, dung_sai: float = 1.0) -> tuple:
    """('that', i): đúng clip và cặp (bat_dau, t_clip) nằm trên đường ánh xạ thật của đoạn i (± dung_sai);
    ('bong', i): đúng clip nhưng căn chỉnh khác (bóng/tình cờ); ('khac', None): clip khác."""
    if x["clip"] != ten_clip or not doan:
        return "khac", None
    lech = [x["bat_dau"] - vi_tri_that(d, x["t_clip"]) for d in doan]
    i = min(range(len(doan)), key=lambda j: abs(lech[j]))
    return ("that" if abs(lech[i]) <= dung_sai else "bong"), i


def _hop(ds: list) -> tuple:
    return min(x["bat_dau"] for x in ds), max(x["bat_dau"] + x["khop"] for x in ds)


def danh_gia_manh(manh: list, su_that: dict, khoang_khuc: dict) -> dict:
    """Mức MẢNH THÔ (trước _merge): mép của căn chỉnh thật so với sự thật, bóng gần, mảnh clip khác.

    ``khoang_khuc``: tên khúc → (đầu, cuối) trên trục video. Sai số «theo khúc» so hợp các mảnh thật trong MỘT khúc
    với phần sự thật nằm trong khúc đó (mảnh của audfprint không bao giờ vượt ra ngoài khúc)."""
    ten = su_that.get("ten_clip") or ""
    doan = sorted(su_that["doan"], key=lambda d: d["video_tu"])
    loai = {"that": [], "bong": [], "khac": []}
    theo_doan: dict = {i: [] for i in range(len(doan))}
    bong_doan: dict = {i: [] for i in range(len(doan))}
    for x in manh:
        lo, i = phan_loai(x, doan, ten)
        loai[lo].append(x)
        if lo == "that":
            theo_doan[i].append(x)
        elif lo == "bong":
            bong_doan[i].append(x)
    ra_doan = []
    for i, d in enumerate(doan):
        ds, align_that = theo_doan[i], d["video_tu"] - d["clip_tu"] / d["he_so"]
        muc = {"doan": i, "so_manh_that": len(ds)}
        if ds:
            a, b = _hop(ds)
            muc.update(tong_hash_that=sum(x["hash"] for x in ds), dau=round(a, 3), cuoi=round(b, 3),
                       sai_so_dau_s=round(a - d["video_tu"], 3), sai_so_cuoi_s=round(b - d["video_den"], 3))
            theo_khuc = []
            for khuc in sorted({x["khuc"] for x in ds}):
                c0, c1 = khoang_khuc.get(khuc, (float("-inf"), float("inf")))
                t0, t1 = max(d["video_tu"], c0), min(d["video_den"], c1)
                a, b = _hop([x for x in ds if x["khuc"] == khuc])
                theo_khuc.append({"khuc": khuc, "that_tu": round(t0, 3), "that_den": round(t1, 3), "dau": round(a, 3),
                                  "cuoi": round(b, 3), "sai_dau": round(a - t0, 3), "sai_cuoi": round(b - t1, 3),
                                  "hash": sum(x["hash"] for x in ds if x["khuc"] == khuc)})
            muc["theo_khuc"] = theo_khuc
        # Bóng mà _merge sẽ gom cùng nhóm (|align − align thật| ≤ dedup_s): chúng kéo vung_khop_s/end_s ra đâu?
        gan = [x for x in bong_doan[i] if abs(x["align"] - align_that) <= DEDUP_S
               and x["hash"] >= MIN_HASH and x["khop"] >= MIN_MATCH_S]
        muc["bong_gan_qua_loc"] = len(gan)
        if gan:
            a, b = _hop(gan)
            muc["bong_gan_vuot_dau_s"] = round(d["video_tu"] - a, 3)    # dương = bóng bắt đầu SỚM hơn sự thật
            muc["bong_gan_vuot_cuoi_s"] = round(b - d["video_den"], 3)  # dương = bóng kết thúc MUỘN hơn sự thật
        ra_doan.append(muc)
    khac = loai["khac"]
    qua = [x for x in khac if x["hash"] >= MIN_HASH and x["khop"] >= MIN_MATCH_S]
    return {
        "so_manh": len(manh), "so_manh_that": len(loai["that"]), "so_manh_bong": len(loai["bong"]),
        "so_manh_clip_khac": len(khac),
        "bong_qua_loc_min_hash_min_match": sum(1 for x in loai["bong"] if x["hash"] >= MIN_HASH and x["khop"] >= MIN_MATCH_S),
        "clip_khac_qua_loc_min_hash_min_match": len(qua),
        "clip_khac_khop_dai_nhat_s": round(max((x["khop"] for x in khac), default=0.0), 2),
        "clip_khac_hash_lon_nhat": max((x["hash"] for x in khac), default=0),
        "doan": ra_doan,
    }


def so_bat_bien(goc: list, moi: list) -> dict:
    """-Q chỉ được đổi mốc thời gian: cùng tập (khúc, clip, n hash, tổng, hạng); căn chỉnh lệch ≤ làm tròn 0,1 s."""
    def khoa(x):
        return (x["khuc"], x["clip"], x["hash"], x["tong"], x["hang"])
    a, b = sorted(goc, key=lambda x: (khoa(x), x["align"])), sorted(moi, key=lambda x: (khoa(x), x["align"]))
    cung = [khoa(x) for x in a] == [khoa(x) for x in b]
    lech = [abs(x["align"] - y["align"]) for x, y in zip(a, b)] if cung else []
    dkhop = [y["khop"] - x["khop"] for x, y in zip(a, b)] if cung else []
    dbd = [y["bat_dau"] - x["bat_dau"] for x, y in zip(a, b)] if cung else []
    return {"cung_tap_dong": cung, "so_dong_goc": len(a), "so_dong_moi": len(b),
            "align_lech_toi_da_s": round(max(lech, default=0.0), 3),
            "khop_tang_min_s": round(min(dkhop, default=0.0), 2), "khop_tang_max_s": round(max(dkhop, default=0.0), 2),
            "bat_dau_doi_min_s": round(min(dbd, default=0.0), 2), "bat_dau_doi_max_s": round(max(dbd, default=0.0), 2),
            "so_dong_khop_tang": sum(1 for v in dkhop if v > 1e-9)}


def _tu_kiem() -> None:
    x = doc_dong(r"Matched  374.6 s starting at  323.2 s in C:\a\chunk_0000000.wav to time   23.2 s in "
                 r"C:\k\goc_S1.wav with 10267 of 19655 common hashes at rank  0")
    assert x["bat_dau"] == 323.2 and x["khop"] == 374.6 and x["align"] == 300.0 and x["hang"] == 0, x
    y = doc_dong("Matched 10.0 s starting at 100.0 s in D:/w/chunk_0000240_k098048.wav to time 5.0 s in D:/k/c.wav "
                 "with 50 of 90 common hashes at rank 3")
    assert abs(y["bat_dau"] - (240 + 98.048)) < 1e-9 and abs(y["khop"] - 9.8048) < 1e-9 and y["he_so"] == 0.98048
    st = {"ten_clip": "goc_S1.wav", "doan": [{"video_tu": 300.0, "video_den": 720.0, "clip_tu": 0.0, "clip_den": 420.0,
                                              "he_so": 1.0}]}
    assert phan_loai(x, st["doan"], "goc_S1.wav") == ("that", 0)
    bong = dict(x, bat_dau=320.0, t_clip=23.2 + 2.124, align=320.0 - 25.324)
    assert phan_loai(bong, st["doan"], "goc_S1.wav")[0] == "bong"
    assert phan_loai(x, st["doan"], "khac.wav") == ("khac", None)
    # Đoạn trích (S3): mảnh trên đường thật nhưng t_clip < clip_tu vẫn là «thật» (vùng ảo của căn chỉnh đó).
    s3 = [{"video_tu": 400.0, "video_den": 700.0, "clip_tu": 120.0, "clip_den": 420.0, "he_so": 1.0}]
    assert phan_loai({"clip": "c", "bat_dau": 350.0, "t_clip": 70.0}, s3, "c") == ("that", 0)
    # Tốc độ 1,02: điểm (bat_dau, t_clip) phải nằm trên v(t) = 300 + t/1,02.
    s7 = [{"video_tu": 300.0, "video_den": 300 + 480 / 1.02, "clip_tu": 0.0, "clip_den": 480.0, "he_so": 1.02}]
    assert phan_loai({"clip": "c", "bat_dau": 300 + 204 / 1.02, "t_clip": 204.0}, s7, "c") == ("that", 0)
    kq = danh_gia_manh([x, bong], st, {"chunk_0000000.wav": (0.0, 1080.0)})
    d0 = kq["doan"][0]
    assert d0["sai_so_dau_s"] == 23.2 and d0["sai_so_cuoi_s"] == round(697.8 - 720.0, 3) and kq["so_manh_bong"] == 1
    assert d0["bong_gan_qua_loc"] == 1 and d0["bong_gan_vuot_dau_s"] == -20.0
    sb = so_bat_bien([x], [dict(x, khop=400.0, bat_dau=301.0, t_clip=1.0, align=300.0)])
    assert sb["cung_tap_dong"] and sb["khop_tang_max_s"] == 25.4 and sb["align_lech_toi_da_s"] == 0.0
    assert not so_bat_bien([x], [dict(x, hash=1)])["cung_tap_dong"]
    print("chung: tự kiểm ĐẠT")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _tu_kiem()
