# -*- coding: utf-8 -*-
"""Sai số mốc của Tool Quét so với SỰ THẬT dựng sẵn — hàm thuần, KHÔNG gọi mã sản phẩm (tự kiểm: ``python danh_gia.py``).

Sự thật: đoạn ``{video_tu, video_den, clip_tu, clip_den, he_so}`` (xem kich_ban.py). Một dòng kết quả là dict các
trường ``engine.Match`` (``start_s`` = mốc đầu clip, ``vung_khop_s``, ``end_s``, ``clip_offset_s``, ``hashes``…).
Precision/recall theo giây = độ dài giao (giây) chia độ dài khoảng báo cáo / khoảng thật — phép đo liên tục, tương
đương lưới từng giây nhưng không cần ngưỡng «nửa giây».
"""
from __future__ import annotations


def hop(khoang) -> list:
    """Hợp các khoảng [a, b] (bỏ khoảng rỗng), trả danh sách rời nhau đã sắp."""
    ra: list = []
    for a, b in sorted((float(a), float(b)) for a, b in khoang if b > a):
        if ra and a <= ra[-1][1]:
            ra[-1][1] = max(ra[-1][1], b)
        else:
            ra.append([a, b])
    return [tuple(x) for x in ra]


def do_dai(khoang) -> float:
    return sum(b - a for a, b in hop(khoang))


def giao(x, y) -> list:
    return hop([(max(a, c), min(b, d)) for a, b in hop(x) for c, d in hop(y) if min(b, d) > max(a, c)])


def precision_recall(bao, that) -> tuple:
    """(|báo ∩ thật| / |báo|, |báo ∩ thật| / |thật|); mẫu số 0 → None."""
    g, db, dt = do_dai(giao(bao, that)), do_dai(bao), do_dai(that)
    return (round(g / db, 4) if db else None, round(g / dt, 4) if dt else None)


def dau_clip(d: dict) -> float:
    """Giây 0 của clip trên trục video theo đoạn ``d`` (có thể là mốc ảo khi đầu clip không được dùng)."""
    return d["video_tu"] - d["clip_tu"] / d["he_so"]


def gan_doan(m: dict, doan: list) -> int:
    """Chỉ số đoạn sự thật của dòng ``m``: giao [vung_khop_s, end_s] dài nhất; hoà thì mép gần nhất."""
    def diem(i: int) -> tuple:
        d = doan[i]
        g = do_dai(giao([(m["vung_khop_s"], m["end_s"])], [(d["video_tu"], d["video_den"])]))
        return g, -min(abs(m["vung_khop_s"] - d["video_tu"]), abs(m["end_s"] - d["video_den"]))
    return max(range(len(doan)), key=diem)


def danh_gia(su_that: dict, dong: list) -> dict:
    """``dong``: các dòng CỦA ĐÚNG clip sự thật mà báo cáo hiển thị (``ScanResult.matches``)."""
    doan = sorted(su_that["doan"], key=lambda d: d["video_tu"])
    that = [(d["video_tu"], d["video_den"]) for d in doan]
    ra: dict = {"so_dong": len(dong), "tim_thay": bool(dong and doan), "tung_dong": [],
                "sai_so_dau_clip_s": None, "sai_so_dau_vung_s": None, "sai_so_cuoi_s": None,
                "precision_giay": None, "recall_giay": None,
                "precision_giay_tu_vung_khop": None, "recall_giay_tu_vung_khop": None}
    if not dong or not doan:
        return ra
    gan = []
    for m in sorted(dong, key=lambda m: m["vung_khop_s"]):
        i = gan_doan(m, doan)
        d = doan[i]
        gan.append((i, m))
        ra["tung_dong"].append({
            "doan_su_that": i,
            "start_s": m["start_s"], "vung_khop_s": m["vung_khop_s"], "end_s": m["end_s"],
            "sai_so_dau_clip_s": round(m["start_s"] - dau_clip(d), 3),
            "sai_so_dau_vung_s": round(m["vung_khop_s"] - d["video_tu"], 3),
            "sai_so_cuoi_s": round(m["end_s"] - d["video_den"], 3),
            "sai_so_offset_clip_s": round(m["clip_offset_s"] - d["clip_tu"], 3),
        })
    # Dòng CHÍNH: dòng gán cho đoạn sớm nhất (nhiều hash nhất); không có thì dòng có vùng khớp sớm nhất.
    cua_dau = [m for i, m in gan if i == 0]
    chinh = max(cua_dau, key=lambda m: m["hashes"]) if cua_dau else gan[0][1]
    ra["sai_so_dau_clip_s"] = round(chinh["start_s"] - dau_clip(doan[0]), 3)
    ra["sai_so_dau_vung_s"] = round(chinh["vung_khop_s"] - doan[0]["video_tu"], 3)
    ra["sai_so_cuoi_s"] = round(max(m["end_s"] for m in dong) - max(d["video_den"] for d in doan), 3)
    ra["precision_giay"], ra["recall_giay"] = precision_recall([(m["start_s"], m["end_s"]) for m in dong], that)
    ra["precision_giay_tu_vung_khop"], ra["recall_giay_tu_vung_khop"] = precision_recall(
        [(m["vung_khop_s"], m["end_s"]) for m in dong], that)
    ra["giay_bao_cao"] = round(do_dai([(m["start_s"], m["end_s"]) for m in dong]), 3)
    ra["giay_that"] = round(do_dai(that), 3)
    return ra


def _tu_kiem() -> None:
    assert hop([(5, 7), (0, 2), (1, 3), (9, 9)]) == [(0, 3), (5, 7)]
    assert do_dai([(0, 10), (5, 15)]) == 15
    assert giao([(0, 10)], [(5, 15), (20, 30)]) == [(5, 10)]
    assert precision_recall([(0, 10)], [(5, 15)]) == (0.5, 0.5)
    assert precision_recall([], [(0, 1)]) == (None, 0.0)
    st = {"doan": [{"video_tu": 250.0, "video_den": 450.0, "clip_tu": 0.0, "clip_den": 200.0, "he_so": 1.0},
                   {"video_tu": 480.0, "video_den": 700.0, "clip_tu": 260.0, "clip_den": 480.0, "he_so": 1.0}]}

    def m(start, vung, end, off, h):
        return {"start_s": start, "vung_khop_s": vung, "end_s": end, "clip_offset_s": off, "hashes": h}
    kq = danh_gia(st, [m(220.0, 491.0, 689.0, 271.0, 900), m(250.0, 260.0, 440.0, 10.0, 1000)])
    assert [d["doan_su_that"] for d in kq["tung_dong"]] == [0, 1]
    assert kq["sai_so_dau_clip_s"] == 0.0 and kq["sai_so_dau_vung_s"] == 10.0 and kq["sai_so_cuoi_s"] == -11.0
    assert kq["tung_dong"][1]["sai_so_dau_clip_s"] == 0.0 and kq["tung_dong"][1]["sai_so_offset_clip_s"] == 11.0
    # [220..689] ∪ [250..440] = [220..689]: giao với thật = 200 + 209 = 409 trên 469 s báo cáo, 420 s thật.
    assert kq["precision_giay"] == round(409 / 469, 4) and kq["recall_giay"] == round(409 / 420, 4)
    assert kq["precision_giay_tu_vung_khop"] == 1.0 and kq["recall_giay_tu_vung_khop"] == round(378 / 420, 4)
    nhanh = {"doan": [{"video_tu": 300.0, "video_den": 300 + 480 / 1.02, "clip_tu": 0.0, "clip_den": 480.0,
                       "he_so": 1.02}]}
    k2 = danh_gia(nhanh, [m(300.1, 310.0, 760.0, 10.2, 5000)])
    assert k2["sai_so_dau_clip_s"] == 0.1 and k2["sai_so_cuoi_s"] == round(760 - (300 + 480 / 1.02), 3)
    assert danh_gia({"doan": []}, [m(1, 2, 3, 0, 9)])["tim_thay"] is False
    print("danh_gia: tự kiểm ĐẠT")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # bảng mã PC2 = cp1252
    _tu_kiem()
