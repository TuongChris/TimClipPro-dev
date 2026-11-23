# -*- coding: utf-8 -*-
"""Chạy ``audfprint match`` với hai thay đổi, KHÔNG sửa source vendored, KHÔNG đổi kết quả:

1. In MỘT dòng khi một khúc đã tra kho xong. audfprint in ``Analyzed <khúc>`` ngay sau khi tính hash,
   TRƯỚC bước tra kho; đếm ``Analyzed`` thì màn hình báo «xong 4/4 khúc» khi việc thật còn nguyên
   (23/11/2026: khúc 57 phút, kho 612 clip).
2. Tra kho nhanh: ``Matcher._exact_match_counts`` gốc quét lại TOÀN BỘ hits cho mỗi (clip, mode) — kho
   dày, khúc dài thì số mode bùng lên. ``_exact_cat_lat`` cho kết quả y hệt từng phần tử (test
   ``tests/test_tra_kho_nhanh.py``; đo thật 23/11 trên khúc 29 phút × kho Mr Ballen: 53 s → 0,9 s).

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


def _exact_cat_lat(self, hits, ids, rawcounts, hashesfor=None):
    """Thay ``Matcher._exact_match_counts``: cùng mode, cùng số đếm, cùng khoảng thời gian, cùng thứ tự.

    Gom hits theo clip (sắp ỔN ĐỊNH nên giữ thứ tự thời gian-trong-truy-vấn của bản gốc), trong clip
    sắp theo độ lệch; mỗi mode chỉ đọc lát |lệch − mode| ≤ window thay vì quét lại mọi hits.
    """
    import numpy as np
    from audfprint_match import find_modes

    sorted_hits = hits[hits[:, 3].argsort()]  # y hệt bản gốc (kể cả cách xếp các otime bằng nhau)
    theo_clip = np.argsort(sorted_hits[:, 0], kind="stable")
    clip_sap = sorted_hits[theo_clip, 0]
    maxnresults = len(ids) * 4
    results = np.zeros((maxnresults, 7), np.int32)
    nresults = 0
    min_time = max_time = 0
    for urank, (id, rawcount) in enumerate(zip(ids, rawcounts)):
        tu = np.searchsorted(clip_sap, id, "left")
        den = np.searchsorted(clip_sap, id, "right")
        cua_clip = sorted_hits[theo_clip[tu:den]]
        theo_lech = np.argsort(cua_clip[:, 1], kind="stable")
        lech = cua_clip[theo_lech, 1]
        modes, _counts = find_modes(cua_clip[:, 1], window=self.window, threshold=self.threshcount)
        for mode in modes:
            a = np.searchsorted(lech, mode - self.window, "left")
            b = np.searchsorted(lech, mode + self.window, "right")
            lat = cua_clip[np.sort(theo_lech[a:b])]  # đúng các hàng bản gốc lọc ra, đúng thứ tự
            filtcount = len(self._unique_match_hashes(id, lat, mode))
            if filtcount >= self.threshcount:
                if nresults == maxnresults:
                    maxnresults *= 2
                    results.resize((maxnresults, results.shape[1]))
                if self.find_time_range:
                    min_time, max_time = self._calculate_time_ranges(lat, id, mode)
                results[nresults, :] = [id, filtcount, mode, rawcount, urank, min_time, max_time]
                nresults += 1
    return results[:nresults, :]


def _khop_mot_khuc(matcher, analyzer, hash_tab, filename):
    """Thay ``audfprint.matcher_file_match_to_msgs`` (nhánh ncores > 1, chạy trong worker joblib)."""
    # Worker nạp lớp Matcher mới tinh, nên phải gắn bản nhanh ngay tại đây.
    type(matcher)._exact_match_counts = _exact_cat_lat
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
    audfprint_match.Matcher._exact_match_counts = _exact_cat_lat
    goc = audfprint_match.Matcher.file_match_to_msgs

    def mot_nhan(self, analyzer, ht, qry, number=None):
        msgs = goc(self, analyzer, ht, qry, number)
        _bao_xong(qry)
        return msgs

    audfprint_match.Matcher.file_match_to_msgs = mot_nhan
    audfprint.main([audfprint_py, *argv[2:]])


if __name__ == "__main__":
    main(sys.argv)
