# -*- coding: utf-8 -*-
"""Audit C-16: file JSON hỏng → tự phục hồi từ ``.bak`` (chậm MỘT lần ghi) mà KHÔNG báo gì.

``ghi_json_an_toan`` làm mới ``.bak`` từ file chính TRƯỚC khi ghi bản mới, nên ``.bak`` luôn là
bản liền trước. Người dùng tạo kho «A» rồi kho «B»; ``khos.json`` sau đó hỏng (lỗi đĩa, phần mềm
diệt virus, sửa tay). Lần mở sau ``doc_json_an_toan`` đổi tên bản hỏng thành ``khos.json.hong.*``,
ghi lại sổ từ ``.bak`` (chưa có «B») và trả về như không có gì: kho «B» biến khỏi danh sách,
không nhật ký, không cảnh báo khởi động (``_dau_vet_so_kho_hong`` chỉ được xét khi sổ RỖNG).
Cùng đường im lặng đó với ``cau_hinh.json``.

Hành vi ĐÚNG: chính sách phục hồi giữ nguyên, nhưng phục hồi về bản CŨ HƠN phải để lại tín hiệu —
một dòng nhật ký ở lớp lưu trữ và một cảnh báo khởi động của Engine nêu file, bản sao ``.bak`` và
bản hỏng được giữ. Dữ liệu tổng hợp hoàn toàn trong ``tmp_path``; không kho thật, không mạng.
"""
import glob
import json
import logging
import os

import cau_hinh
import luu_tru
from engine import Engine


def _eng(tmp_path) -> Engine:
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"),
               out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    return e


def _canh_bao(e: Engine) -> str:
    return "\n".join(str(x) for x in e.canh_bao_khoi_dong)


def test_so_kho_hong_phuc_hoi_tu_bak_phai_co_canh_bao_khoi_dong(tmp_path, monkeypatch):
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    e1 = _eng(tmp_path)
    e1.add_kho("A")
    e1.add_kho("B")
    assert [k["ten"] for k in e1.list_khos()] == ["A", "B"]

    # Tiền đề: .bak đúng là bản liền trước (chưa có «B»).
    kho_file = e1.kho_file
    with open(kho_file + ".bak", encoding="utf-8") as f:
        assert '"B"' not in f.read()

    # khos.json hỏng giữa hai phiên.
    with open(kho_file, "wb") as f:
        f.write(b"{rac")

    e2 = _eng(tmp_path)

    # Chính sách phục hồi không đổi: quay về bản liền trước, bản hỏng được giữ.
    assert [k["ten"] for k in e2.list_khos()] == ["A"]
    ban_hong = glob.glob(glob.escape(kho_file) + ".hong.*")
    assert len(ban_hong) == 1

    canh_bao = _canh_bao(e2)
    assert "khos.json" in canh_bao and "khos.json.bak" in canh_bao, (
        "Sổ kho vừa bị phục hồi về bản sao cũ hơn (kho «B» biến mất) nhưng không có cảnh báo "
        f"khởi động nào: canh_bao_khoi_dong={e2.canh_bao_khoi_dong!r}")
    assert os.path.basename(ban_hong[0]) in canh_bao

    # Lần mở kế tiếp: sổ đã lành (ghi lại từ .bak) — không báo lại mãi.
    e3 = _eng(tmp_path)
    assert "khos.json.bak" not in _canh_bao(e3)


def test_so_kho_nguyen_ven_khong_canh_bao_phuc_hoi(tmp_path, monkeypatch):
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    e1 = _eng(tmp_path)
    e1.add_kho("A")
    e1.add_kho("B")

    e2 = _eng(tmp_path)
    assert [k["ten"] for k in e2.list_khos()] == ["A", "B"]
    assert e2.canh_bao_khoi_dong == []


def test_cau_hinh_hong_phuc_hoi_tu_bak_phai_co_canh_bao_khoi_dong(tmp_path, monkeypatch):
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    cau_hinh.ghi_cau_hinh(str(data_dir), {"thu_muc_quet_gan_nhat": "lan_1"})
    cau_hinh.ghi_cau_hinh(str(data_dir), {"thu_muc_quet_gan_nhat": "lan_2"})
    (data_dir / "cau_hinh.json").write_bytes(b"{rac")

    e = _eng(tmp_path)

    assert e.cau_hinh_da_luu.get("thu_muc_quet_gan_nhat") == "lan_1"
    canh_bao = _canh_bao(e)
    assert "cau_hinh.json" in canh_bao and "cau_hinh.json.bak" in canh_bao, (
        f"cau_hinh.json vừa quay về bản sao cũ hơn mà không báo: {e.canh_bao_khoi_dong!r}")


def test_doc_json_an_toan_bao_phuc_hoi_qua_nhat_ky_va_ham_goi_lai(tmp_path, caplog):
    path = tmp_path / "du_lieu.json"
    luu_tru.ghi_json_an_toan(str(path), {"lan": 1})
    luu_tru.ghi_json_an_toan(str(path), {"lan": 2})

    da_bao = []
    # Đọc bình thường: không gọi lại, không nhật ký cảnh báo.
    assert luu_tru.doc_json_an_toan(str(path), khi_phuc_hoi=da_bao.append) == {"lan": 2}
    assert da_bao == []

    path.write_text("{hỏng", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="luu_tru"):
        assert luu_tru.doc_json_an_toan(str(path), khi_phuc_hoi=da_bao.append) == {"lan": 1}

    ban_hong = glob.glob(glob.escape(str(path)) + ".hong.*")
    assert da_bao == ban_hong and len(ban_hong) == 1
    assert json.loads(path.read_text(encoding="utf-8")) == {"lan": 1}
    assert any("json.recovered_from_bak" in r.getMessage() for r in caplog.records)
