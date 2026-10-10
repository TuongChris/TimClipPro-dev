# -*- coding: utf-8 -*-
"""Sinh lại dữ liệu golden MỨC MẢNH cho test «bóng» của âm thanh lặp (``tests/golden/bong_lap/*.json``).

Không phải test (pytest không thu thập file này). Chạy trong ``TimClipPro/``, cần ffmpeg trong PATH hoặc ``bin/``:

    python tests/tao_golden_bong_lap.py [thư_mục_ra]     # mặc định: tests/golden/bong_lap

Mỗi kịch bản: dựng clip gốc + video vi phạm 100% TỔNG HỢP (``am_thanh_lap``, seed cố định) trong thư mục tạm,
tạo kho vân tay, quét video bằng ``Engine.scan_media`` và ghi lại ĐÚNG danh sách mảnh thô mà ``Engine._merge``
nhận ở lần gộp cuối (đầu ra của audfprint qua parser của engine). Ground truth tính TRỰC TIẾP từ cách dựng.

Không ghi gì vào ``data/`` của thư mục mã: Engine dùng thư mục tạm, xoá khi xong.

Lưu ý tái lập: âm thanh tất định theo seed, nhưng bảng hash audfprint (depth 100) bỏ NGẪU NHIÊN phần tràn của
các ô hash quá đầy (``hash_table.py``, ``random.randint`` không seed) — nhạc có trống lặp làm tràn nhiều ô. Vì vậy
mỗi lần sinh lại, số mảnh/hash của bóng xê dịch chút ít; test chỉ khẳng định tính chất bền (một dòng, mốc ±1 s,
không dòng bóng), không so từng con số.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import date

import numpy as np

MA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MA)
sys.path.insert(0, os.path.join(MA, "tests"))

from am_thanh_lap import SR, doi_toc_do, nhac_co_nhip  # noqa: E402
from conftest import _ghi_wav, _giai_dieu  # noqa: E402

TRUONG_MANH = ("clip", "bat_dau", "khop", "t_clip", "hash", "he_so", "align")


def _kich_ban() -> list:
    """(tên file, mô tả, clip gốc, video, ground truth). Đệm trước/sau là nội dung KHÔNG có trong kho."""
    ra = []
    # 1) Nhạc có trống lặp, trích giữa (như E2E V4): clip[60 → 360] chèn ở giây 120 ⇒ đầu clip gốc ở 60,0 s.
    clip = np.concatenate([_giai_dieu(8, seed=9301, sr=SR), nhac_co_nhip(352, seed=9302)])
    video = np.concatenate([_giai_dieu(120, seed=9303, sr=SR), clip[60 * SR: 360 * SR],
                            _giai_dieu(120, seed=9304, sr=SR)])
    ra.append(("trich_giua.json", "nhac_trich_giua.wav",
               "Nhạc có trống lặp 113 BPM (360 s, 8 s mở đầu riêng). Video: đệm 120 s + đoạn clip[60 → 360 s] + "
               "đệm 120 s — MỘT lần dùng, đầu clip gốc trên video = 120 − 60 = 60,0 s.",
               clip, video, {"moc_that_s": 60.0, "so_lan_dung": 1}))
    # 2) Bản reup cắt bỏ 12 s giữa clip: [0, 100) + [112, 300) đặt liền nhau từ giây 120 (như B08).
    clip = np.concatenate([_giai_dieu(8, seed=9311, sr=SR), nhac_co_nhip(292, seed=9312)])
    video = np.concatenate([_giai_dieu(120, seed=9313, sr=SR), clip[: 100 * SR], clip[112 * SR:],
                            _giai_dieu(120, seed=9314, sr=SR)])
    ra.append(("cat_giua.json", "nhac_cat_giua.wav",
               "Nhạc có trống lặp (300 s). Video: đệm 120 s + clip[0 → 100) + clip[112 → 300) liền nhau + đệm 120 s "
               "— MỘT lần dùng, hai phần có vị trí đặt khác nhau: phần đầu 120,0 s, phần sau 120 + 100 − 112 = 108,0 s.",
               clip, video, {"moc_that_s": 120.0, "moc_phan_s": [120.0, 108.0], "so_lan_dung": 1}))
    # 3) Nhạc lặp dài phát chậm 0,12% (dưới ngưỡng bù tốc độ 0,15%), chèn NGUYÊN clip từ giây 120 (như B13).
    clip = np.concatenate([_giai_dieu(8, seed=9321, sr=SR), nhac_co_nhip(472, seed=9322)])
    video = np.concatenate([_giai_dieu(120, seed=9323, sr=SR), doi_toc_do(clip, 1.0012),
                            _giai_dieu(120, seed=9324, sr=SR)])
    ra.append(("troi_nho.json", "nhac_troi_nho.wav",
               "Nhạc có trống lặp dài 480 s, chèn NGUYÊN clip từ giây 120 nhưng phát chậm 0,12% (dưới ngưỡng bù "
               "tốc độ 0,15%) — MỘT lần dùng, đầu clip gốc 120,0 s. Trôi rất nhỏ tách căn chỉnh thật thành nhiều "
               "đỉnh lệch nhau vài phần mười giây, có khe > dedup_s giữa chúng.",
               clip, video, {"moc_that_s": 120.0, "so_lan_dung": 1}))
    return ra


def _so(x):
    return round(float(x), 3)


def ghi_json(duong: str, du_lieu: dict) -> None:
    """Phần đầu dàn trang, mỗi mảnh thô MỘT dòng — gọn, xem diff được."""
    dau = json.dumps({k: v for k, v in du_lieu.items() if k != "tho"}, ensure_ascii=False, indent=1)
    manh = ",\n".join("  " + json.dumps(x, ensure_ascii=False) for x in du_lieu["tho"])
    with open(duong, "w", encoding="utf-8", newline="\n") as f:
        f.write(dau[:-2] + ',\n "tho": [\n' + manh + "\n ]\n}\n")


def sinh(thu_muc_ra: str) -> None:
    from engine import Config, Engine, chu_ky_chinh_sach

    os.makedirs(thu_muc_ra, exist_ok=True)
    tam = tempfile.mkdtemp(prefix="p0_bong_lap_")
    try:
        for ten_json, ten_clip, mo_ta, clip, video, gt in _kich_ban():
            goc = os.path.join(tam, ten_json[:-5])
            kho = os.path.join(goc, "kho")
            os.makedirs(kho)
            _ghi_wav(os.path.join(kho, ten_clip), clip, SR)
            duong_video = os.path.join(goc, "vi_pham.wav")
            _ghi_wav(duong_video, video, SR)
            eng = Engine(root=MA, data_dir=os.path.join(goc, "data"), out_dir=os.path.join(goc, "ketqua"))
            eng.add_kho("P0", kho)
            eng.build_database(kho, "new")
            lan_gop: list = []
            goc_merge = eng._merge

            def ghi(tho, _goc=goc_merge, _lan=lan_gop):
                _lan.append([dict(x) for x in tho])
                return _goc(tho)

            eng._merge = ghi
            kq = eng.scan_media(duong_video)
            del eng._merge
            if kq.status != "ok" or not lan_gop:
                raise SystemExit(f"{ten_json}: quét lỗi ({kq.status}: {kq.note})")
            tong = {os.path.basename(c["ten"]): int(c["so_hash"]) for c in eng.db_clips(bo_cache=True)}
            tho = [{k: (os.path.basename(x[k]) if k == "clip" else _so(x[k]) if k != "hash" else int(x[k]))
                    for k in TRUONG_MANH} for x in lan_gop[-1]]
            du_lieu = {
                "mo_ta": mo_ta,
                "sinh_boi": "tests/tao_golden_bong_lap.py",
                "ngay_sinh": date.today().isoformat(),
                "chinh_sach_nhan_dien": chu_ky_chinh_sach(Config()),
                **gt,
                "duration_s": _so(kq.duration_s),
                "pham_vi_quet_s": _so(kq.pham_vi_quet_s),
                "tong_hash_kho": tong,
                "tho": tho,
            }
            ghi_json(os.path.join(thu_muc_ra, ten_json), du_lieu)
            print(f"{ten_json}: {len(tho)} mảnh thô; kết quả quét lúc sinh: "
                  f"{[(round(m.start_s, 2), m.hashes) for m in kq.matches]}")
    finally:
        shutil.rmtree(tam, ignore_errors=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sinh(sys.argv[1] if len(sys.argv) > 1 else os.path.join(MA, "tests", "golden", "bong_lap"))
