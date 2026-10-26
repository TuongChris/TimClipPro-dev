# -*- coding: utf-8 -*-
"""Audit P3 C-10: ``kiem_metadata_kho.py`` phải dùng ĐÚNG thư mục dữ liệu của bộ phân giải chung.

Dữ liệu synthetic: ``khos.json`` một kho trong thư mục tạm; không đọc/ghi dữ liệu thật, không mạng.
Chế độ legacy/DEV (D-26): launcher đặt ``TIMCLIP_DATA_DIR`` trỏ ra ngoài cây mã. Engine, ``cli.py``
và ``thu_muc_data_mac_dinh`` đều đi qua ``runtime_paths.resolve(ma_nguon=...)``
(docs/MANAGED_RUNTIME_DESIGN.md §4 — «Đường dẫn trạng thái đi qua MỘT bộ phân giải»).

Hành vi ĐÚNG được khẳng định: ``main()`` dựng Engine chỉ-đọc trên thư mục dữ liệu mà
``runtime_paths`` phân giải (= ``TIMCLIP_DATA_DIR``), KHÔNG trên ``<mã>/data`` — nếu không, công cụ
báo cáo về sổ kho SAI (hoặc lỗi FileNotFoundError), và ``--repair-offline --apply`` giành
``tool.lock`` + ghi snapshot trong cây mã thay vì thư mục dữ liệu thật.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

import engine
import kiem_metadata_kho


class _DungLai(Exception):
    """Chặn ``main()`` ngay sau khi chọn thư mục dữ liệu — không làm gì thêm."""


def test_main_dung_thu_muc_data_cua_runtime_paths(tmp_path, monkeypatch):
    data = tmp_path / "DevState" / "data"
    data.mkdir(parents=True)
    (data / "khos.json").write_text(json.dumps(
        {"dang_dung": "SML", "danh_sach": [{"ten": "SML", "thu_muc": "", "db": "kho_sml.pklz"}]},
        ensure_ascii=False), encoding="utf-8")
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data))

    da_chon = []

    def ghi_lai(root, data_dir, kho_name):
        da_chon.append(os.path.abspath(data_dir))
        raise _DungLai()

    monkeypatch.setattr(kiem_metadata_kho, "_engine_chi_doc", ghi_lai)
    monkeypatch.setattr(sys, "argv", ["kiem_metadata_kho.py", "--json"])

    with pytest.raises(_DungLai):
        kiem_metadata_kho.main()

    goc = os.path.dirname(os.path.abspath(kiem_metadata_kho.__file__))
    mong = engine.thu_muc_data_mac_dinh(goc)              # bộ phân giải chung của Engine/cli
    assert os.path.normcase(mong) == os.path.normcase(str(data))   # tiền đề: env được tôn trọng
    assert os.path.normcase(da_chon[0]) == os.path.normcase(mong), (
        f"kiem_metadata_kho dùng {da_chon[0]!r} thay vì thư mục dữ liệu thật {mong!r}")


def test_main_bao_loi_cau_hinh_runtime_ro_rang(tmp_path, monkeypatch, capsys):
    """Managed thiếu TIMCLIP_STATE_ROOT: dừng mã 1 với câu rõ, KHÔNG đoán ``<mã>/data``."""
    monkeypatch.setenv("TIMCLIP_RUNTIME_MODE", "managed")
    monkeypatch.delenv("TIMCLIP_STATE_ROOT", raising=False)

    def khong_duoc_goi(*_a, **_k):
        raise AssertionError("không được dựng Engine khi runtime cấu hình sai")

    monkeypatch.setattr(kiem_metadata_kho, "_engine_chi_doc", khong_duoc_goi)
    monkeypatch.setattr(sys, "argv", ["kiem_metadata_kho.py", "--json"])

    assert kiem_metadata_kho.main() == 1
    loi = capsys.readouterr().err
    assert "LỖI CẤU HÌNH" in loi and "TIMCLIP_STATE_ROOT" in loi
