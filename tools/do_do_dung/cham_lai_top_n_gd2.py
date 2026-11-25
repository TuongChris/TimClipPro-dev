"""DT-03 GĐ2: chấm lại từng đoạn chèn theo 4 trạng thái — tách «đạt ngưỡng nhưng bị top_n cắt» khỏi «sót thật».
Dùng đúng luật chấp nhận của mã DEV (chap_nhan_khop.danh_gia_chap_nhan). Chỉ đọc. Chạy: python -X utf8 cham_lai_top_n_gd2.py"""
import collections
import json
import os
import sys
from types import SimpleNamespace

RA = r"C:\Dev\pc2_test_runs\2026-11-25_dt03_gd2"
sys.path.insert(0, r"C:\Dev\TimClipPro_VanHanh\TimClipPro")
from chap_nhan_khop import danh_gia_chap_nhan  # noqa: E402

DUNG_SAI = 3.0


def _doc(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def trang_thai(c, kq, cfg):
    def trung(m):
        return m["clip"] == c["clip"] and m["start_s"] < c["video_den"] + DUNG_SAI and m["end_s"] > c["video_tu"] - DUNG_SAI
    if c["bat_duoc"]:
        return "bat"
    loai = [m for m in kq["matches_loai"] if trung(m)]
    if any(danh_gia_chap_nhan(SimpleNamespace(**m), cfg).chap_nhan for m in loai):
        return "cat_top_n"
    return "duoi_nguong" if loai else "khong_ung_vien"


def main():
    cfg = SimpleNamespace(**_doc(os.path.join(RA, "cau_hinh_da_dung.json"))["toan_bo"])
    bang = collections.defaultdict(collections.Counter)
    for t in _doc(os.path.join(RA, "cham_diem.json"))["tung_ca"]:
        kq = _doc(os.path.join(RA, "ket_qua", t["ca"] + ".json"))
        for c in t["chen"]:
            bang[(t["nhom"], t["bien_doi"], c["dai_s"])][trang_thai(c, kq, cfg)] += 1
    print("nhóm | biến đổi | dài | bắt / cắt top_n / dưới ngưỡng / không ứng viên")
    for k in sorted(bang):
        b = bang[k]
        print(f"{k[0]} | {k[1]} | {k[2]} | {b['bat']} / {b['cat_top_n']} / {b['duoi_nguong']} / {b['khong_ung_vien']}")
    tong = sum(bang.values(), collections.Counter())
    print("TỔNG:", dict(tong))


if __name__ == "__main__":
    main()
