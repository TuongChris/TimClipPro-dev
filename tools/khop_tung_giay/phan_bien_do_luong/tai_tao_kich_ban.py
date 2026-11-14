# -*- coding: utf-8 -*-
"""Phản biện đo lường — DỰNG LẠI audio của từng kịch bản bằng chính script dựng (kich_ban.py, kich_ban_them.py) vào
thư mục tạm của tôi, so từng byte với audio đã dùng (bo_thu, cach_c/them) và so su_that trả về với su_that.json.

Chứng minh: audio được đo đúng là audio script sinh ra (tất định), và su_that.json đúng là thứ script tính từ tham số
dựng — không phải sửa tay. Kết hợp su_that_doc_lap.py (đo từ audio) là kiểm sự thật hai chiều.
Ghi: phan_bien_do_luong\\tai_tao_kich_ban.json. Thư mục tạm bị xoá sau khi băm.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
GOC = r"C:\Dev\pc2_test_tools\khop_tung_giay"
sys.path.insert(0, os.path.join(GOC, "bo_thu"))
sys.path.insert(0, os.path.join(GOC, "cach_c"))
import kich_ban as kb  # noqa: E402

BO_THU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"
THEM = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_c\them"
RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_do_luong"
TAM = os.path.join(RA, "_tai_tao_tam")


def bam_am_thanh(path: str) -> str:
    """WAV: băm cả file (đầu WAV tất định). Khác (Opus/Ogg có số serial ngẫu nhiên): băm PCM giải mã."""
    if path.lower().endswith(".wav"):
        with open(path, "rb") as f:
            return "file:" + hashlib.sha256(f.read()).hexdigest()
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", path, "-f", "s16le",
                        "-ac", "1", "-"], capture_output=True, check=True)
    return "pcm:" + hashlib.sha256(r.stdout).hexdigest()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ham = dict(kb.KICH_BAN)
    ds = sys.argv[1:] or list(ham) + ["X1", "X2", "X3"]
    if any(S.startswith("X") for S in ds):
        import kich_ban_them as kt   # noqa: E402  (import chay_bo_thu: kiểm môi trường chặn mạng)
        ham.update({"X1": kt.tao_x1, "X2": kt.tao_x2, "X3": kt.tao_x3})
    kq = {}
    for S in ds:
        goc = os.path.join(THEM if S.startswith("X") else BO_THU, S)
        tam = os.path.join(TAM, S)
        if os.path.isdir(tam):
            shutil.rmtree(tam)
        os.makedirs(tam)
        st_moi = ham[S](tam)
        with open(os.path.join(goc, "su_that.json"), encoding="utf-8") as f:
            st_cu = json.load(f)
        st_cu.pop("thoi_gian_dung_du_lieu_s", None)
        st_moi = json.loads(json.dumps(st_moi, ensure_ascii=False, default=str))
        file_moi = sorted(os.path.relpath(os.path.join(r, x), tam) for r, _, fs in os.walk(tam) for x in fs)
        so = []
        for rel in file_moi:
            a, b = bam_am_thanh(os.path.join(tam, rel)), (bam_am_thanh(os.path.join(goc, rel))
                                                          if os.path.exists(os.path.join(goc, rel)) else None)
            so.append({"file": rel, "trung": a == b, "bam_moi": a[:22], "bam_cu": (b or "")[:22]})
        kq[S] = {"file": so, "moi_file_trung": all(x["trung"] for x in so),
                 "su_that_trung": st_moi == st_cu,
                 "khoa_khac": sorted(k for k in set(st_moi) | set(st_cu) if st_moi.get(k) != st_cu.get(k))}
        shutil.rmtree(tam)
        print(S, json.dumps({k: kq[S][k] for k in ("moi_file_trung", "su_that_trung", "khoa_khac")},
                            ensure_ascii=False), [x["file"] for x in so if not x["trung"]], flush=True)
    if os.path.isdir(TAM) and not os.listdir(TAM):
        os.rmdir(TAM)
    with open(os.path.join(RA, "tai_tao_kich_ban.json" if not sys.argv[1:] else "tai_tao_mot_phan.json"), "w",
              encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
