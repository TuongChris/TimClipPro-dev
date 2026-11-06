# -*- coding: utf-8 -*-
"""Audit 06/11: đọc kho lỗi một lần (file bị khoá, thiếu RAM) không được nhớ thành «kho rỗng».

``db_clips`` trả rỗng để giao diện vẫn vẽ được, nhưng kết quả rỗng đó từng bị cache theo (mtime, kích thước): mọi lượt
sau tới khi kho đổi đều thấy tổng hash = 0, tỷ lệ phủ = 0, clip ngắn rớt mà không có cảnh báo nào.
"""

import pytest

from engine import Config, Engine

CLIP = {"ten": "x.opus", "duong_dan": "D:/kho/x.opus", "so_hash": 800}


@pytest.fixture()
def e(tmp_path, monkeypatch):
    eng = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    eng.config = Config()
    eng.db_file = str(tmp_path / "db.pklz")
    (tmp_path / "db.pklz").write_bytes(b"gia")
    monkeypatch.setattr(eng, "audfprint", "audfprint.py")
    return eng


def test_doc_loi_mot_lan_lan_sau_doc_lai_duoc(e, monkeypatch):
    lan = []

    def doc(path):
        lan.append(path)
        if len(lan) == 1:
            raise MemoryError
        return [CLIP]

    monkeypatch.setattr(e, "_doc_danh_sach_clip", doc)
    assert e.db_clips() == []
    assert e.db_clips() == [CLIP]
    assert e.db_clips() == [CLIP] and len(lan) == 2, "đọc được rồi thì vẫn dùng cache"


def test_bang_tong_hash_bao_loi_khi_kho_khong_doc_duoc(e, monkeypatch):
    """Nơi gọi đã có cảnh báo «Không đọc được tổng hash»: kho lỗi phải tới được nhánh đó, không thành kho rỗng."""

    def doc(_path):
        raise RuntimeError("kho hỏng")

    monkeypatch.setattr(e, "_doc_danh_sach_clip", doc)
    with pytest.raises(RuntimeError):
        e._bang_tong_hash()


def test_kho_rong_that_khong_bao_loi(e, monkeypatch):
    monkeypatch.setattr(e, "_doc_danh_sach_clip", lambda _p: [])
    assert e._bang_tong_hash() == ({}, {}, {})


def test_so_kho_bi_giu_luc_cong_bo_khong_bo_ca_luot_dung_kho(e, monkeypatch):
    """Dựng kho nhiều giờ không được đổ vì ``khos.json`` bị giữ đúng lúc kiểm trước khi thay file."""
    import engine as eng_mod
    from luu_tru import LoiDuLieu

    e.kho_dang_dung = "K"
    lan = []

    def doc_so():
        lan.append(1)
        if len(lan) < 3:
            raise LoiDuLieu("Tạm thời không đọc được")
        return {"dang_dung": "K", "danh_sach": [{"ten": "K", "db": "db.pklz"}]}

    monkeypatch.setattr(e, "_doc_khos", doc_so)
    monkeypatch.setattr(e, "_duong_dan_db_kho", lambda db: e.db_file)
    monkeypatch.setattr(eng_mod.time, "sleep", lambda s: None)
    e._kiem_dich_cong_bo()
    assert len(lan) == 3


def test_so_kho_loi_keo_dai_luc_cong_bo_van_bao_loi(e, monkeypatch):
    import engine as eng_mod
    from luu_tru import LoiDuLieu

    e.kho_dang_dung = "K"

    def hong():
        raise LoiDuLieu("sổ sai cấu trúc")

    monkeypatch.setattr(e, "_doc_khos", hong)
    monkeypatch.setattr(eng_mod.time, "sleep", lambda s: None)
    with pytest.raises(LoiDuLieu):
        e._kiem_dich_cong_bo()
