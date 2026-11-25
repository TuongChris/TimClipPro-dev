"""DT-03 GĐ2: dòng bị ngưỡng loại — đúng (cứu được) vs nhầm (sẽ thành báo nhầm) nếu hạ sàn; ca tinh chỉnh lệch > 1 s.
Chỉ đọc kết quả trong RA. Chạy: python -X utf8 phan_tich_san_gd2.py"""
import glob
import json
import os

RA = r"C:\Dev\pc2_test_runs\2026-11-25_dt03_gd2"
DUNG_SAI = 3.0


def _doc(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    dap = {c["ca"]: c for c in _doc(os.path.join(RA, "dap_an.json"))["ca"]}
    dung, nham = [], []  # (hash, ty_le, matched_s, ca, clip)
    for p in sorted(glob.glob(os.path.join(RA, "ket_qua", "*.json"))):
        k = _doc(p)
        chen = dap.get(k["ca"], {}).get("chen", [])
        for m in k["matches_loai"]:
            trung = any(c["clip"] == m["clip"] and m["start_s"] < c["video_den"] + DUNG_SAI
                        and m["end_s"] > c["video_tu"] - DUNG_SAI for c in chen)
            (dung if trung else nham).append((m["hashes"], m.get("ty_le"), m.get("matched_s"), k["ca"], m["clip"]))
    print(f"Dòng bị loại: đúng clip+vùng {len(dung)}, sai {len(nham)}")
    nham.sort(reverse=True)
    print("Dòng sai bị loại, hash cao nhất (hash, tỉ lệ, giây khớp, ca):")
    for r in nham[:15]:
        print("  ", r[:4])
    am = [r for r in nham if r[3].startswith("am_")]
    print(f"Trong đối chứng âm: {len(am)} dòng bị loại, hash lớn nhất {max((r[0] for r in am), default=0)}")
    for san in (500, 600, 700, 800, 900, 1000):
        print(f"sàn {san}: cứu thêm ≤{sum(r[0] >= san for r in dung)} dòng đúng, thêm {sum(r[0] >= san for r in nham)} dòng nhầm")
    print("Ca tinh chỉnh lệch > 1 s:")
    for t in _doc(os.path.join(RA, "cham_diem.json"))["tung_ca"]:
        for c in t["chen"]:
            a, b = c.get("sai_dau_tc_s"), c.get("sai_cuoi_tc_s")
            if a is not None and (abs(a) > 1 or abs(b or 0) > 1):
                print(f"   {t['ca']} dài {c['dai_s']} s hash {c['hashes']} quét {c['sai_dau_s']}/{c['sai_cuoi_s']} tc {a}/{b}")


if __name__ == "__main__":
    main()
