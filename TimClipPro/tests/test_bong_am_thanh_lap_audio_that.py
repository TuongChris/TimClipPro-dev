# -*- coding: utf-8 -*-
"""«Bóng» của âm thanh lặp trên AUDIO THẬT (FFmpeg + audfprint thật) — P0, 10/10/2026.

Dựng dữ liệu (100% tổng hợp, ``am_thanh_lap``, seed cố định):
* nhạc nhịp đều ~113 BPM: mỗi đoạn 8 ô nhịp giữ CỐ ĐỊNH một mẫu trống (cùng một mẫu âm mỗi lần đánh, như nhạc làm từ
  sample), hợp âm theo vòng 4 ô nhịp, giai điệu ngẫu nhiên — làm audfprint thấy thêm căn chỉnh «bóng» lệch bội số
  nửa ô nhịp (≈ 1,06 s);
* clip gốc 300 s = 8 s mở đầu riêng + nhạc; video vi phạm = nền khác hẳn + đoạn clip chèn ở mốc đã biết.

Kỳ vọng tính TRỰC TIẾP từ cách dựng; dung sai 1 s (bước thời gian audfprint ≈ 23 ms) — lỗi cần bắt lớn hơn hẳn
(trước khi sửa: lệch tới ±dedup_s = 20 s, kèm dòng bóng «Rất chắc chắn»).
"""
from __future__ import annotations

import shutil

import numpy as np
import pytest

from am_thanh_lap import SR, nhac_co_nhip, vong_lap_y_het
from conftest import _ghi_wav, _giai_dieu

do_truoc_khi_sua = pytest.mark.xfail(
    strict=True, reason="P0: tái hiện lỗi bóng của âm thanh lặp trên mã trước khi sửa (e49340d/7a76e71)")



def _quet(engine, tmp_path, clip: np.ndarray, X: float, L: float, P: float, sau: float = 120.0):
    """Kho = một clip gốc; video = nền P giây + clip[X → X+L] + nền ``sau`` giây ⇒ đầu clip gốc ở P − X."""
    kho = tmp_path / "kho"
    kho.mkdir()
    _ghi_wav(kho / "goc.wav", clip, SR)
    nen = np.concatenate([_giai_dieu(P, seed=9201, sr=SR), clip[int(X * SR): int((X + L) * SR)],
                          _giai_dieu(sau, seed=9202, sr=SR)])
    video = tmp_path / "vi_pham.wav"
    _ghi_wav(video, nen, SR)
    engine.add_kho("Test", str(kho))
    engine.build_database(str(kho), "new")
    kq = engine.scan_media(str(video))
    assert kq.status == "ok", kq.note
    return kq, [m for m in kq.matches if m.clip == "goc.wav"]


@pytest.fixture(autouse=True)
def _can_ffmpeg():
    if shutil.which("ffmpeg") is None:
        pytest.skip("cần ffmpeg trong PATH")


@pytest.mark.slow
@do_truoc_khi_sua
def test_nhac_co_nhip_trich_giua_mot_dong_dung_moc(engine, tmp_path):
    clip = np.concatenate([_giai_dieu(8, seed=9203, sr=SR), nhac_co_nhip(292, seed=9204)])
    kq, dong = _quet(engine, tmp_path, clip, X=40.0, L=180.0, P=120.0)
    assert len(dong) == 1, [(round(m.start_s, 1), m.hashes) for m in dong]
    assert dong[0].start_s == pytest.approx(80.0, abs=1.0)
    assert kq.so_dat_nguong == 1                      # «Tổng số đoạn phát hiện» = số lần dùng thật
    assert dong[0].confidence == "Rất chắc chắn" and not dong[0].moc_mo_ho


@pytest.mark.slow
@do_truoc_khi_sua
def test_vong_lap_y_het_mot_dong_danh_dau_mo_ho(engine, tmp_path):
    """Đoạn chèn nằm TRỌN trong vùng lặp y hệt từng mẫu (vòng 8 ô nhịp): không thể biết đó là vòng thứ mấy.
    Đúng: MỘT dòng, cờ mơ hồ, mốc báo và các mốc thay thế đều thuộc tập tương đương 140 ± k·chu kỳ; độ chắc chắn
    của NGUỒN giữ nguyên."""
    than, chu_ky = vong_lap_y_het(292, seed=9205)
    clip = np.concatenate([_giai_dieu(8, seed=9206, sr=SR), than])
    kq, dong = _quet(engine, tmp_path, clip, X=100.0, L=60.0, P=240.0)
    tuong_duong = [140.0 + k * chu_ky for k in range(-8, 6)]          # 140 ± k·chu kỳ, còn trong vùng lặp
    assert len(dong) == 1 and kq.so_dat_nguong == 1, [(round(m.start_s, 1), m.hashes) for m in dong]
    m = dong[0]
    assert m.moc_mo_ho and m.ty_so_doi_thu > 0.5
    assert m.confidence == "Rất chắc chắn"
    assert min(abs(m.start_s - t) for t in tuong_duong) <= 1.0
    assert sum(min(abs(x - t) for t in tuong_duong) <= 1.0 for x in m.moc_thay_the) >= 3
    assert min(abs(x - 140.0) for x in (m.start_s, *m.moc_thay_the)) <= 1.0      # mốc thật nằm trong tập báo


@pytest.mark.slow
def test_doi_chung_khong_lap_dung_moc(engine, tmp_path):
    """Đối chứng: cùng bố cục, nội dung KHÔNG lặp — xanh trước và sau khi sửa."""
    clip = np.concatenate([_giai_dieu(8, seed=9207, sr=SR), _giai_dieu(292, seed=9208, sr=SR)])
    kq, dong = _quet(engine, tmp_path, clip, X=40.0, L=180.0, P=120.0)
    assert len(dong) == 1
    assert dong[0].start_s == pytest.approx(80.0, abs=1.0)
    assert kq.so_dat_nguong == 1 and dong[0].confidence == "Rất chắc chắn"
