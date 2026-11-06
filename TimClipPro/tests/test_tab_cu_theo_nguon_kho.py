# -*- coding: utf-8 -*-
"""Audit 06/11: tab mở trước phải thấy thư mục nguồn MỚI của kho, nếu không chốt chống trộn nguồn của «Bổ sung» cho qua."""

import os

import pytest

from engine import Engine


@pytest.fixture()
def hai_tab(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    cu, moi = str(tmp_path / "NguonCu"), str(tmp_path / "NguonMoi")
    os.makedirs(cu)
    os.makedirs(moi)
    a = Engine(root=str(tmp_path))
    a.add_kho("K", cu)
    b = Engine(root=str(tmp_path))
    assert b.kho_thu_muc == cu
    a._ghi_phien_ban_sau_cong_bo(shifts_kho=0, cap_nhat_shifts=False, thu_muc=moi)
    return b, cu, moi


def test_tab_cu_thay_thu_muc_nguon_moi_khi_ve_lai(hai_tab):
    b, _, moi = hai_tab
    b.list_khos()
    assert b.kho_thu_muc == moi


def test_bo_sung_tu_thu_muc_cu_bi_chan_o_tab_cu(hai_tab):
    b, cu, moi = hai_tab
    job = b._ban_sao_cho_job()
    with pytest.raises(RuntimeError, match="TRỘN clip"):
        job._kiem_nguon_bo_sung(cu, [{"duong_dan": os.path.join(moi, "c1.opus"), "so_hash": 100}])
