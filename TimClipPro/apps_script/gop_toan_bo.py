# -*- coding: utf-8 -*-
"""Sinh TOAN_BO_AppsScript.gs từ 7 tệp File0N_*.gs (README «Cách cài»). Chạy: python gop_toan_bo.py

Phần đầu (hướng dẫn cài + ghi chú «bản này sửa gì») giữ nguyên từ bản gộp hiện có; mỗi phần sau = khối tiêu đề
«PHẦN 0N (nguồn: …)» + nội dung tệp gốc, dòng «FILE 0N —» đổi thành «PHẦN 0N —». Test kiểm hai bên không lệch.
"""

import pathlib
import re

THU_MUC = pathlib.Path(__file__).resolve().parent
TOAN_BO = THU_MUC / "TOAN_BO_AppsScript.gs"
VACH = "// " + "=" * 74


def _doc(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def gop() -> str:
    dau = _doc(TOAN_BO).split("\n" + VACH + "\n// PHẦN 01  ", 1)[0]
    phan = [dau]
    for p in sorted(THU_MUC.glob("File0[1-7]_*.gs")):
        so = p.name[4:6]
        noi = re.sub(
            r"^( \* )FILE " + so + " —",
            r"\1PHẦN " + so + " —",
            _doc(p).strip("\n"),
            count=1,
            flags=re.M,
        )
        phan.append(f"{VACH}\n// PHẦN {so}  (nguồn: {p.name})\n{VACH}\n\n{noi}\n")
    return "\n".join(phan)


if __name__ == "__main__":
    TOAN_BO.write_bytes(gop().encode("utf-8"))
    print(f"Đã sinh {TOAN_BO.name} từ 7 tệp.")
