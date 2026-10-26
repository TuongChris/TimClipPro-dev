# -*- coding: utf-8 -*-
"""Parser dòng audfprint: «to time -0.0 s» vẫn là dòng khớp hợp lệ (audit A-16).

audfprint in ``to time {:6.1f}`` = ``(min_time + aligntime) * t_hop``. ``min_time`` là hash
(phân vị) nằm trong cửa sổ ``mode ± --match-win`` (mặc định 2 khung), nên khi hash đó nằm ở
1–2 khung đầu clip và lệch +1/+2 khung so với mode, giá trị âm nhỏ (−0,023 s) được in thành
``  -0.0``. Trước đây ``RE_MATCH`` chỉ nhận số KHÔNG dấu ở nhóm «to time» nên dòng bị đếm vào «dòng khớp thô»
rồi bỏ qua lặng lẽ (đọc được < dòng khớp, mất một mảnh yếu).

Dữ liệu synthetic, không mạng, không chạy audfprint: phần 1 dùng CHÍNH hàm định dạng của
audfprint (``Matcher.file_match_to_msgs``, ``match_file`` thay bằng kết quả dựng sẵn); phần 2
đưa dòng đó qua parser thật của ``Engine._match_chunks`` (``_run_stream`` giả ghi opfile).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

from engine import RE_MATCH, Engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audfprint-master"))
import audfprint_match  # noqa: E402


class _Analyzer:
    n_hop = 256
    target_sr = 11025


class _Ht:
    names = [r"C:\kho\20240101 - Clip [abcdefghijk].opus"]


def _dong_audfprint(min_time, aligntime, max_time, nhash=18):
    """Dòng do CHÍNH audfprint định dạng cho một kết quả (id, nhash, mode, raw, rank, min, max)."""
    mt = audfprint_match.Matcher()
    mt.verbose = True
    mt.find_time_range = True
    mt.match_file = lambda analyzer, ht, qry, number=None: (
        np.array([[0, nhash, aligntime, nhash * 3, 0, min_time, max_time]]), 60.0, 900)
    return mt.file_match_to_msgs(_Analyzer(), _Ht(), r"C:\ws\chunk_0000000.wav")[0]


def test_audfprint_that_su_in_to_time_am_va_RE_MATCH_doc_duoc():
    # Clip gốc bắt đầu ở khung 500 (11,6 s) của khúc → mode (tham chiếu − truy vấn) ≈ −500.
    # Hash sớm nhất (phân vị 5 % của < 20 hash = hash đầu) ở khung truy vấn 500, khung tham
    # chiếu 1, tức độ lệch −499 = mode + 2 với mode = −501 (vẫn trong cửa sổ ±2).
    dong = _dong_audfprint(min_time=500, aligntime=-501, max_time=540)
    assert "starting at   11.6 s" in dong
    assert "to time   -0.0 s" in dong   # tiền đề: audfprint in đúng như vậy
    m = RE_MATCH.search(dong)
    assert m is not None, f"RE_MATCH bỏ qua dòng khớp hợp lệ của audfprint: {dong!r}"
    assert m.group(5).endswith("[abcdefghijk].opus")
    assert int(m.group(6)) == 18


def test_match_chunks_doc_du_dong_khop_va_t_clip_am_ve_0(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"),
               out_dir=str(tmp_path / "out"))
    khuc = str(tmp_path / "chunk_0000000.wav")
    dong_am = ("Matched    0.9 s starting at   12.0 s in " + khuc + " to time   -0.0 s in "
               r"C:\kho\a.opus with    18 of    40 common hashes at rank  0")
    dong_thuong = ("Matched   30.0 s starting at   50.0 s in " + khuc + " to time   10.0 s in "
                   r"C:\kho\b.opus with   900 of  1200 common hashes at rank  1")

    def chay(lenh, on_line=None, **kw):
        with open(lenh[lenh.index("--opfile") + 1], "w", encoding="utf-8") as f:
            f.write(dong_am + "\n" + dong_thuong + "\n")
        return 0, []

    e._run_stream = chay
    tho = e._match_chunks([khuc], workspace=str(tmp_path))
    cd = e.chan_doan_quet
    assert cd.dong_co_matched == 2
    assert cd.parse_duoc == 2, (
        f"đọc được {cd.parse_duoc}/{cd.dong_co_matched} dòng khớp — dòng «to time -0.0» bị bỏ")
    am = [x for x in tho if x["clip"].endswith("a.opus")]
    assert am and am[0]["t_clip"] == 0.0
    # −0,0 do làm tròn là đầu clip: không được mang dấu âm sang mốc/căn chỉnh.
    assert str(am[0]["t_clip"]) == "0.0"
    assert am[0]["align"] == pytest.approx(12.0)
