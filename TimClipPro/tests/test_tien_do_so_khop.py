# -*- coding: utf-8 -*-
"""«Đã phân tích khúc» KHÁC «đã so khớp xong khúc».

audfprint in ``Analyzed <khúc>`` NGAY sau khi tính hash của khúc, TRƯỚC bước tra kho
(``Matcher.match_hashes``) — bước chiếm gần hết thời gian khi khúc dài và kho dày. Sự cố 23/11/2026
(DEV, video 03:20:10, kho 612 clip, 4 khúc 57 phút): màn hình báo «So khớp: đã xong 4/4 khúc», 99%,
rồi đứng ~15 phút vì tra kho vẫn đang chạy. Tín hiệu «xong khúc» thật đến từ
``audfprint_match_runner`` (in một dòng sau khi khúc tra kho xong).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import tien_do_quet as tdq
import ui_tien_do_quet as ui
from audfprint_match_runner import PREFIX
from conftest import _ghi_wav, _giai_dieu
from engine import Config, Engine

REPO = Path(__file__).resolve().parents[1]


def _eng(tmp_path, **cfg):
    e = Engine(root=str(REPO), config=Config(**cfg), data_dir=str(tmp_path / "data"),
               out_dir=str(tmp_path / "out"))
    e._so_tien_do = tdq.SoTienDo()
    return e


def test_analyzed_chi_la_da_phan_tich_dong_xong_moi_la_da_khop(tmp_path):
    e = _eng(tmp_path)
    khuc = [str(tmp_path / f"chunk_{i * 3420:07d}.wav") for i in range(3)]
    ghi_lai = {}

    def audfprint_gia(lenh, on_line=None, **_kw):
        ghi_lai["lenh"] = [str(x) for x in lenh]
        for k in khuc:  # ncores > 1: không có «#N»
            on_line(f"Mon Nov 23 16:04:00 2026 Analyzed  {k} of 3420.000 s to 812000 hashes")
        ghi_lai["sau_phan_tich"] = e._so_tien_do.anh()
        for k in khuc + khuc[:1]:  # một dòng lặp lại không được đếm hai lần
            on_line(PREFIX + k)
        Path(lenh[lenh.index("--opfile") + 1]).write_text(
            "".join(f"NOMATCH {k} 99.9 sec 812 raw hashes\n" for k in khuc), encoding="utf-8")
        return 0, []

    e._run_stream = audfprint_gia
    e._match_chunks(khuc, workspace=str(tmp_path))

    giua = ghi_lai["sau_phan_tich"]
    assert (giua.khop_phan_tich, giua.khop_xong) == (3, 0), "Analyzed KHÔNG có nghĩa là đã tra kho xong"
    assert giua.ty_le_buoc == 0.0
    cuoi = e._so_tien_do.anh()
    assert (cuoi.khop_phan_tich, cuoi.khop_xong) == (3, 3)
    assert os.path.basename(ghi_lai["lenh"][2]) == "audfprint_match_runner.py"


def _anh_khop(**td):
    from scan_jobs import BatchSnapshot, VideoState
    v = VideoState(index=1, nguon="https://youtu.be/x", scan_status="running", phase="matching",
                   message="")
    return BatchSnapshot(batch_id="b", total=3, current_index=1, completed=0, failed=0, running=True,
                         cancelled=False, elapsed_seconds=999.0, eta_seconds=None, message="",
                         videos=(v,), tien_do=tdq.AnhTienDo(batch_id="b", index=1, tong=3,
                                                            giai_doan=tdq.GD_KHOP, **td),
                         worker_alive=True), v


def test_man_hinh_noi_ro_dang_tra_kho_khi_moi_phan_tich_xong():
    anh, v = _anh_khop(khop_tong=4, khop_phan_tich=4, khop_xong=0)
    dong = "\n".join(ui.dong_chi_tiet(anh, v, {}, 10.0))
    assert "đã xong 4/4" not in dong
    assert "tra kho xong 0/4 khúc" in dong and "phân tích 4/4" in dong
    assert "đang tra kho vân tay" in dong


def test_man_hinh_ghi_luot_bu_toc_do():
    anh, v = _anh_khop(khop_tong=4, khop_phan_tich=1, khop_xong=0, khop_luot="lượt bù tốc độ 1, tối đa 6")
    dong = "\n".join(ui.dong_chi_tiet(anh, v, {}, 10.0))
    assert "**So khớp (lượt bù tốc độ 1, tối đa 6):**" in dong


@pytest.mark.slow
@pytest.mark.parametrize("ncores", [1, 2])
def test_audfprint_that_bao_xong_tung_khuc_ca_mot_nhan_va_da_nhan(tmp_path, ncores):
    """Dòng «xong khúc» phải đến từ CẢ nhánh một nhân và nhánh joblib (worker riêng)."""
    kho = tmp_path / "kho"
    kho.mkdir()
    clip = _giai_dieu(20, seed=4401)
    _ghi_wav(kho / "clip.wav", clip)
    e = _eng(tmp_path, ncores=ncores)
    assert e.build_database(str(kho), "new")["thanh_cong"] == 1
    khuc = []
    for i in range(3):
        p = tmp_path / f"chunk_{i * 100:07d}.wav"
        _ghi_wav(p, clip if i == 1 else _giai_dieu(20, seed=4500 + i))
        khuc.append(str(p))

    tho = e._match_chunks(khuc, workspace=str(tmp_path))

    cuoi = e._so_tien_do.anh()
    assert (cuoi.khop_phan_tich, cuoi.khop_xong) == (3, 3)
    assert {os.path.basename(m["clip"]) for m in tho} == {"clip.wav"}
