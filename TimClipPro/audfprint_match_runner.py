# -*- coding: utf-8 -*-
"""Chạy ``audfprint match`` y nguyên, chỉ in thêm MỘT dòng khi một khúc đã tra kho xong.

Vì sao: audfprint in ``Analyzed <khúc>`` ngay sau khi tính hash, TRƯỚC bước tra kho — bước chiếm gần
hết thời gian với khúc dài (23/11/2026: khúc 57 phút, kho 612 clip, ~19 phút). Đếm ``Analyzed`` thì
màn hình báo «xong 4/4 khúc» trong khi việc thật còn nguyên. Thuật toán, tham số, ``--opfile`` vẫn do
audfprint vendored làm; không sửa source vendored.

Cách dùng: ``python -u audfprint_match_runner.py <đường dẫn audfprint.py> match <tham số audfprint>``.
"""

from __future__ import annotations

import os
import sys

PREFIX = "TIMCLIP_MATCH_DONE "


def _bao_xong(ten: str) -> None:
    # Một lần ghi cả dòng: worker khác khó chen vào giữa.
    sys.stdout.write(PREFIX + ten + "\n")
    sys.stdout.flush()


def _khop_mot_khuc(matcher, analyzer, hash_tab, filename):
    """Thay ``audfprint.matcher_file_match_to_msgs`` (nhánh ncores > 1, chạy trong worker joblib)."""
    msgs = matcher.file_match_to_msgs(analyzer, hash_tab, filename)
    _bao_xong(filename)
    return msgs


def main(argv: list) -> None:
    audfprint_py = os.path.abspath(argv[1])
    sys.path.insert(0, os.path.dirname(audfprint_py))
    import audfprint
    import audfprint_match

    # Nhánh ncores > 1: hàm này chạy trong worker (joblib pickle hàm của __main__ theo giá trị).
    audfprint.matcher_file_match_to_msgs = _khop_mot_khuc
    # Nhánh một nhân (``do_cmd``) gọi thẳng phương thức. Joblib có lùi về chạy trong tiến trình
    # này thì một khúc có thể báo hai lần — engine đếm theo tên khúc nên không sao.
    goc = audfprint_match.Matcher.file_match_to_msgs

    def mot_nhan(self, analyzer, ht, qry, number=None):
        msgs = goc(self, analyzer, ht, qry, number)
        _bao_xong(qry)
        return msgs

    audfprint_match.Matcher.file_match_to_msgs = mot_nhan
    audfprint.main([audfprint_py, *argv[2:]])


if __name__ == "__main__":
    main(sys.argv)
