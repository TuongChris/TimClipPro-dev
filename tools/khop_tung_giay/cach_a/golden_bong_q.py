# -*- coding: utf-8 -*-
"""Cách A, phần 3 — golden «bóng» của âm thanh lặp (tests/golden/bong_lap) dưới -Q mới.

Sinh lại 3 file mảnh thô bằng CHÍNH ``tests/tao_golden_bong_lap.py`` (hàm ``sinh``) vào thư mục KẾT QUẢ (không ghi
vào tests/golden), với lệnh audfprint mang ``--time-quantile`` (và ``--ncores 2``) — bọc ``Engine._audfprint_cmd``
trong tiến trình này. Rồi chạy NGUYÊN VĂN 3 test golden của ``tests/test_bong_am_thanh_lap.py`` trên dữ liệu đó
(đổi ``DU_LIEU`` của module test trong tiến trình) và đo mép vùng khớp của dòng được chọn so với sự thật dựng sẵn.

Chạy:  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B golden_bong_q.py 0.05 0
"""
from __future__ import annotations

import os
import sys
import time
import traceback

import chung as c

THU_MUC = os.path.join(c.KET_QUA, "golden_bong")
# Vùng video chứa clip (từ cách dựng trong tao_golden_bong_lap._kich_ban): [đầu, cuối] của từng phần.
VUNG_THAT = {"trich_giua.json": [(120.0, 420.0)], "cat_giua.json": [(120.0, 220.0), (220.0, 408.0)],
             "troi_nho.json": [(120.0, 120.0 + 480 * 1.0012)]}
TEST = ("test_golden_trich_giua_mot_dong_dung_moc_va_dem_nhat_quan",
        "test_golden_cat_giua_moi_moc_la_moc_that_cua_mot_phan", "test_golden_troi_nho_mot_dong_dung_moc")


def chay(cac_q: list) -> dict:
    c.kiem_moi_truong()
    c.kiem_parser_giong_engine()
    sys.path.insert(0, os.path.join(c.MA, "tests"))
    sys.path.insert(0, c.MA)
    import engine as eng
    goc = eng.Engine._audfprint_cmd
    hien = {"q": None}

    def cmd(self, sub, *them, db_file=None):
        lenh = goc(self, sub, *them, db_file=db_file)
        lenh[lenh.index("--ncores") + 1] = "2"          # máy đang chạy DEV 8502
        if sub == "match" and hien["q"] is not None:
            lenh = [*lenh, "--time-quantile", repr(hien["q"])]
        return lenh

    eng.Engine._audfprint_cmd = cmd
    import tao_golden_bong_lap as tg
    import test_bong_am_thanh_lap as tb

    ra = {}
    for q in cac_q:
        hien["q"] = q
        # Lần sinh lặp lại (bảng hash bỏ ngẫu nhiên phần tràn ⇒ mỗi lần sinh khác nhau): CACH_A_HAU_TO=_lan2 …
        dq = os.path.join(THU_MUC, c.ten_q(q) + os.environ.get("CACH_A_HAU_TO", ""))
        t0 = time.perf_counter()
        tg.sinh(dq)
        tb.DU_LIEU = dq
        ket = {"thoi_gian_sinh_s": round(time.perf_counter() - t0, 1), "test": {}, "dong": {}}
        for ten in TEST:
            try:
                getattr(tb, ten)()
                ket["test"][ten] = "ĐẠT"
            except AssertionError as e:
                ket["test"][ten] = f"HỎNG: {e!r}"[:400]
            except Exception:  # noqa: BLE001 — ghi lại, chạy tiếp các test khác
                ket["test"][ten] = "LỖI: " + traceback.format_exc()[-400:]
        for ten_json, vung in VUNG_THAT.items():
            d, ds, dat, chon = tb._quet_golden(ten_json)
            ket["dong"][ten_json] = {
                "so_manh_tho": len(d["tho"]), "so_nhom_sau_merge": len(ds), "so_dat": len(dat),
                "chon": [{"start_s": round(m.start_s, 2), "vung_khop_s": round(m.vung_khop_s, 2),
                          "end_s": round(m.end_s, 2), "matched_s": round(m.matched_s, 1), "hashes": m.hashes,
                          "moc_mo_ho": m.moc_mo_ho} for m in chon],
                "vung_that": vung,
                "sai_so_dau_vung_s": round(min(m.vung_khop_s for m in chon) - vung[0][0], 2) if chon else None,
                "sai_so_cuoi_s": round(max(m.end_s for m in chon) - vung[-1][1], 2) if chon else None,
            }
        ra[c.ten_q(q)] = ket
        c.ghi_json(os.path.join(dq, "ket_qua_test.json"), ket)
        print(c.ten_q(q), ket["thoi_gian_sinh_s"], "s", ket["test"], flush=True)
    return ra


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    vao = [float(x) for x in sys.argv[1:]] or [0.05, 0.0]
    chay([None if q == 0.05 else q for q in vao])
