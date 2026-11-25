"""DT-03: đo lượt bù đổi cao độ (luoi_cao_do) bằng mã MỚI trên nhóm «cao» + 6 tệp đối chứng âm của GĐ2.
Dùng lại kho đã dựng của GĐ2 (chỉ quét, không dựng lại); kết quả ghi riêng vào ket_qua_caodo/.
Chạy: PYTHONPATH=C:/Dev/pc2_test_tools/chan_mang <venv>/python -B -X utf8 do_cao_do_moi.py <thư mục TimClipPro mã mới>"""
import collections
import dataclasses
import os
import sys
import time

import bo_do_dt03 as bo

bo.RA = r"C:\Dev\pc2_test_runs\2026-11-25_dt03_gd2"
AM = [f"am_{i}.m4a" for i in range(6)]


def main():
    bo.MA = sys.argv[1]
    eng, e, _ = bo._engine()
    e.config.top_n = 3                 # như GĐ2 (tệp «cao» có 2 đoạn chèn)
    e.config.toc_do_toi_da_thu = eng.Config().toc_do_toi_da_thu
    e.config.luoi_cao_do = list(eng.Config().luoi_cao_do)
    e.config.validate()
    print("cấu hình:", e.config.toc_do_toi_da_thu, e.config.luoi_cao_do, flush=True)
    import bao_cao_v2  # noqa: F401  (đường dẫn mã mới đã nạp)
    dap = {c["ca"]: c for c in bo._doc(os.path.join(bo.RA, "dap_an.json"))["ca"]}
    ra = os.path.join(bo.RA, "ket_qua_caodo")
    os.makedirs(ra, exist_ok=True)
    bang = collections.defaultdict(lambda: [0, 0])
    for ten in [c for c in dap if c.startswith("cao_")] + AM:
        t0 = time.time()
        kq = e.scan_media(os.path.join(bo.RA, "ca", ten))
        giay = round(time.time() - t0, 1)
        d = {"ca": ten, "trang_thai": kq.status, "ghi_chu": kq.note, "giay_quet": giay, "duration_s": kq.duration_s,
             "matches": [dict(dataclasses.asdict(m), tinh_chinh=None, moc_tinh_chinh=None) for m in kq.matches],
             "matches_loai": [dataclasses.asdict(m) for m in kq.matches_loai],
             "da_thu_toc_do": list(getattr(kq.chan_doan, "da_thu_toc_do", []) or []),
             "toc_do_tim_duoc": getattr(kq.chan_doan, "toc_do_tim_duoc", "")}
        bo._ghi(os.path.join(ra, ten + ".json"), d)
        c = bo.cham_ca(dap[ten], d)
        for x in c["chen"]:
            k = (dap[ten]["bien_doi"], x["dai_s"])
            bang[k][0] += x["bat_duoc"]
            bang[k][1] += 1
        print(f"{ten}: {len(kq.matches)} dòng, báo nhầm {len(c['bao_nham'])}, {giay}s, tìm bằng: {d['toc_do_tim_duoc']}",
              flush=True)
    print("KẾT QUẢ (bắt/tổng):")
    for k in sorted(bang):
        print(f"  {k[0]} {k[1]} s: {bang[k][0]}/{bang[k][1]}")
    print("XONG")


if __name__ == "__main__":
    main()
