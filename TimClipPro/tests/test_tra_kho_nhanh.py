# -*- coding: utf-8 -*-
"""Tra kho nhanh (bản «cắt lát» của ``Matcher._exact_match_counts``) phải cho KẾT QUẢ Y HỆT bản gốc.

Bản gốc của audfprint quét lại TOÀN BỘ hits cho mỗi (clip, mode) — kho dày, khúc dài thì số mode bùng
lên và tra kho mất hàng chục phút (23/11/2026). Bản nhanh gom hits theo clip, sắp theo độ lệch, mỗi
mode chỉ đọc đúng lát của nó. Không đổi thuật toán: cùng mode, cùng số đếm, cùng khoảng thời gian.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import audfprint_match_runner as runner
from conftest import _ghi_wav, _giai_dieu
from engine import Config, Engine

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "audfprint-master"))
import audfprint_match as am  # noqa: E402


def _hits(seed, n=120_000, n_clip=40, phut=0.5):
    """Hits tổng hợp: trùng ngẫu nhiên dồn vào vài clip (nhiều mode) + đoạn khớp thật."""
    rng = np.random.default_rng(seed)
    khung = int(phut * 60 * 43)
    h = np.empty((n, 4), np.int32)
    h[:, 0] = (rng.zipf(1.4, n) - 1) % n_clip
    h[:, 3] = rng.integers(0, khung, n)
    h[:, 1] = rng.integers(0, 3 * khung, n) - h[:, 3]
    h[:, 2] = rng.integers(0, 1 << 20, n)
    them = []
    for _ in range(6):
        k = int(rng.integers(50, 400))
        d = np.empty((k, 4), np.int32)
        d[:, 0] = rng.integers(0, n_clip)
        d[:, 1] = int(rng.integers(-khung, khung)) + rng.integers(-2, 3, k)
        d[:, 2] = rng.integers(0, 1 << 20, k)
        d[:, 3] = rng.integers(0, khung, k)
        them.append(d)
    return np.vstack([h, *them])


class _Kho:
    def __init__(self, n_clip=40):
        self.hashesperid = np.full(n_clip, 5000, np.int64)


@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("window,khoang", [(2, True), (1, False), (0, True)])
def test_cat_lat_trung_tung_phan_tu_voi_ban_goc(seed, window, khoang):
    m = am.Matcher()
    m.window, m.threshcount, m.find_time_range, m.exact_count = window, 10, khoang, True
    hits = _hits(seed)
    ids, raw = m._best_count_ids(hits, _Kho())
    goc = m._exact_match_counts(hits, ids, raw)
    assert len(goc) > 20, "dữ liệu thử phải có nhiều mode thì mới chứng minh được gì"
    assert np.array_equal(runner._exact_cat_lat(m, hits, ids, raw), goc)


def test_hits_rong_khong_loi():
    m = am.Matcher()
    m.exact_count = True
    rong = np.zeros((0, 4), np.int32)
    assert runner._exact_cat_lat(m, rong, np.zeros(0, np.int64), np.zeros(0, np.int64)).shape == (0, 7)


@pytest.mark.slow
def test_bo_boc_cho_ket_qua_y_het_audfprint_goc_khi_da_nhan(tmp_path):
    """Đường production (ncores > 1, worker joblib): opfile của bộ bọc = opfile của audfprint gốc."""
    kho = tmp_path / "kho"
    kho.mkdir()
    for i in range(3):
        _ghi_wav(kho / f"clip{i}.wav", _giai_dieu(20, seed=4600 + i))
    e = Engine(root=str(REPO), config=Config(ncores=2), data_dir=str(tmp_path / "data"),
               out_dir=str(tmp_path / "out"))
    assert e.build_database(str(kho), "new")["thanh_cong"] == 3
    khuc = tmp_path / "chunk_0000000.wav"
    _ghi_wav(khuc, np.concatenate([_giai_dieu(15, seed=1), _giai_dieu(20, seed=4601),
                                   _giai_dieu(10, seed=2), _giai_dieu(20, seed=4602)]))
    tham = ["--dbase", e.db_file, "--ncores", "2", "--continue-on-error", "--find-time-range",
            "--exact-count", "--min-count", "10", "--max-matches", "200", "--shifts", "4"]
    ra = {}
    for ten, dau in (("goc", [e.audfprint]), ("boc", [str(REPO / "audfprint_match_runner.py"),
                                                      e.audfprint])):
        op = tmp_path / f"{ten}.txt"
        subprocess.run([sys.executable, "-u", *dau, "match", *tham, "--opfile", str(op), str(khuc)],
                       check=True, capture_output=True, cwd=str(tmp_path))
        # Bỏ dòng «<giờ> Reading hash table …»: chỉ so các dòng kết quả.
        ra[ten] = [d for d in op.read_text(encoding="utf-8").splitlines() if "Reading hash table" not in d]
    assert sum("Matched" in d for d in ra["goc"]) >= 2
    assert ra["boc"] == ra["goc"]
