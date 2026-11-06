# -*- coding: utf-8 -*-
"""Audit 06/11: tab mở trước phải thấy thư mục nguồn MỚI của kho, nếu không chốt chống trộn nguồn của «Bổ sung» cho qua."""

import json
import os

import pytest

import luu_tru
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


def _giu_file(monkeypatch, duoi):
    """Phần mềm khác giữ file quá thời gian thử lại: mọi lần đọc file chính đều bị từ chối."""
    def mo(path, *a, **k):
        if str(path).endswith(duoi):
            raise PermissionError("file đang bị giữ")
        return open(path, *a, **k)

    monkeypatch.setattr(luu_tru, "open", mo, raising=False)
    monkeypatch.setattr(luu_tru.time, "sleep", lambda s: None)


def test_so_kho_bi_giu_luc_mo_phien_khong_chuyen_nham_sang_kho_dau(tmp_path, monkeypatch):
    """Review 06/11: phiên mở lúc ``khos.json`` bị giữ có kho rỗng; lần vẽ kế giao diện chọn kho ĐẦU và ghi vào sổ, người
    dùng quét nhầm kho. Đọc lại được thì phải về đúng kho của sổ."""
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    dau = Engine(root=str(tmp_path))
    for ten in ("KhoA", "KhoB"):
        os.makedirs(tmp_path / ten)
        dau.add_kho(ten, str(tmp_path / ten))
    dau.use_kho("KhoB")
    with monkeypatch.context() as m:
        _giu_file(m, "khos.json")
        moi = Engine(root=str(tmp_path))
    assert moi.kho_dang_dung == "", "thiết lập: sổ bị giữ thì chưa có kho"
    moi.list_khos()
    assert moi.kho_dang_dung == "KhoB" and not moi._so_kho_vua_hong()
    with open(moi.kho_file, encoding="utf-8") as f:
        assert json.load(f)["dang_dung"] == "KhoB"
