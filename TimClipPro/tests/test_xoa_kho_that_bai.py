# -*- coding: utf-8 -*-
"""Audit C-4 — xoá kho khi file vân tay KHÔNG xoá được; tạo lại kho cùng tên.

Kỳ vọng ĐÚNG (phán quyết tranh cãi C-4):
* ``delete_kho`` KHÔNG BAO GIỜ báo thành công khi file vân tay còn trên đĩa: ``_xoa_an_toan``
  trả False (file đang bị tiến trình khác / diệt virus giữ) thì ném ``RuntimeError`` và KHÔNG
  sửa ``khos.json`` (mục kho còn, ``dang_dung`` không đổi, file nguyên byte). Giao diện hiện
  ``st.error`` thay vì ``st.rerun()`` lặng lẽ.
* Tạo lại kho CÙNG TÊN là một kho MỚI (id mới — chú thích trong ``add_kho``): tên file suy ra
  đã có sẵn trên đĩa (mồ côi) thì kho mới nhận tên file KHÁC, không thừa hưởng vân tay cũ và
  không xoá/ghi đè file mồ côi.

Dữ liệu hoàn toàn tổng hợp (HashTable audfprint nhỏ trong thư mục tạm), không mạng.
"""

import gzip
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import engine as engine_mod
from engine import Engine

GOC = Path(__file__).resolve().parents[1]
APP_PY = GOC / "app.py"
sys.path.insert(0, str(GOC / "audfprint-master"))
import hash_table  # noqa: E402

# `pickle` chỉ dùng trên file `.pklz` do CHÍNH test này vừa ghi trong thư mục tạm.


def ghi_ht(path, muc) -> None:
    ht = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
    for ten, so in muc:
        ht.store(str(ten), [(t % 16, t % 16) for t in range(so)])
    with gzip.open(path, "wb") as f:
        pickle.dump(ht, f)


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _eng(tmp_path) -> Engine:
    # root = thư mục TimClipPro để Engine tìm thấy audfprint-master (db_clips cần).
    return Engine(root=str(GOC), data_dir=str(tmp_path / "data"),
                  out_dir=str(tmp_path / "out"))


def _kho_co_van_tay(e, tmp_path, ten="A"):
    nguon = tmp_path / f"nguon_{ten}"
    nguon.mkdir()
    (nguon / "a1.opus").write_bytes(b"audio")
    e.add_kho(ten, str(nguon))
    ghi_ht(e.db_file, [(str(nguon / "a1.opus"), 5)])
    assert [c["ten"] for c in e.db_clips(bo_cache=True)] == ["a1.opus"]
    return Path(e.db_file)


def _kiem_kho_con_nguyen(e, db, sha_truoc, so_truoc) -> None:
    kho = next((k for k in e.list_khos() if k["ten"] == "A"), None)
    assert kho is not None, "mục kho «A» đã bị bỏ khỏi khos.json trong khi file vân tay còn"
    assert kho["co_van_tay"] is True
    assert db.exists() and _sha(db) == sha_truoc, "file vân tay phải còn nguyên byte"
    assert e._doc_khos() == so_truoc, "khos.json phải không đổi khi chưa xoá được"
    assert os.path.normcase(e.db_file) == os.path.normcase(str(db))


@pytest.mark.skipif(sys.platform != "win32", reason="khoá file kiểu Windows")
def test_xoa_kho_khi_file_van_tay_dang_bi_giu_thi_khong_bao_thanh_cong(tmp_path, monkeypatch):
    """Tình huống thật: một handle khác đang mở file .pklz (WinError 32)."""
    e = _eng(tmp_path)
    db = _kho_co_van_tay(e, tmp_path)
    sha_truoc, so_truoc = _sha(db), e._doc_khos()
    monkeypatch.setattr(engine_mod.time, "sleep", lambda s: None)  # bỏ ~8,4 s chờ thử lại

    giu = open(db, "rb")  # handle thứ hai, như audfprint match / diệt virus giữ file
    try:
        with pytest.raises(RuntimeError, match="Chưa xoá được kho «A»"):
            e.delete_kho("A")
    finally:
        giu.close()

    _kiem_kho_con_nguyen(e, db, sha_truoc, so_truoc)


def test_xoa_kho_xoa_file_that_bai_thi_khong_bo_muc_lang_le(tmp_path, monkeypatch):
    """Cùng lỗi, độc lập nền tảng: ``_xoa_an_toan`` trả False (đúng hợp đồng «không ném lỗi»)."""
    e = _eng(tmp_path)
    db = _kho_co_van_tay(e, tmp_path)
    nguon_b = tmp_path / "nguon_B"
    nguon_b.mkdir()
    e.add_kho("B", str(nguon_b))
    e.use_kho("A")
    sha_truoc, so_truoc = _sha(db), e._doc_khos()
    assert so_truoc["dang_dung"] == "A"
    monkeypatch.setattr(Engine, "_xoa_an_toan", staticmethod(lambda p, so_lan=6: False))

    with pytest.raises(RuntimeError, match="Chưa xoá gì cả"):
        e.delete_kho("A")

    _kiem_kho_con_nguyen(e, db, sha_truoc, so_truoc)


def test_xoa_kho_xoa_duoc_file_thi_bo_muc_nhu_cu(tmp_path):
    """Hồi quy: xoá được file vân tay → bỏ mục, chuyển ``dang_dung`` như trước."""
    e = _eng(tmp_path)
    db = _kho_co_van_tay(e, tmp_path)
    nguon_b = tmp_path / "nguon_B"
    nguon_b.mkdir()
    e.add_kho("B", str(nguon_b))
    e.use_kho("A")

    e.delete_kho("A")

    assert not db.exists()
    assert [k["ten"] for k in e.list_khos()] == ["B"]
    assert e._doc_khos()["dang_dung"] == "B"


def test_tao_lai_kho_cung_ten_khong_thua_huong_file_van_tay_mo_coi(tmp_path):
    """File ``kho_<slug('A')>.pklz`` còn nằm lại (xoá dở/chép tay) khi sổ rỗng."""
    data = tmp_path / "data"
    data.mkdir()
    ten_suy_ra = f"kho_{Engine._slug('A')}.pklz"
    mo_coi = data / ten_suy_ra
    ghi_ht(mo_coi, [(str(tmp_path / "cu" / "a1.opus"), 5)])
    sha_mo_coi = _sha(mo_coi)

    nguon_moi = tmp_path / "nguon_moi"
    nguon_moi.mkdir()
    e = _eng(tmp_path)
    assert e.list_khos() == []
    kho_tra_ve = e.add_kho("A", str(nguon_moi))

    kho = next(k for k in e.list_khos() if k["ten"] == "A")
    assert kho["db"] == kho_tra_ve["db"]
    assert kho["db"] != ten_suy_ra, "kho mới dùng lại file vân tay mồ côi của kho đã xoá"
    assert kho["db"].startswith(f"kho_{Engine._slug('A')}_") and kho["db"].endswith(".pklz")
    assert kho["co_van_tay"] is False, (
        f"kho mới hiện «Đã có vân tay» vì dùng lại file {kho['db']}")
    assert e.db_clips(bo_cache=True) == [], "kho mới liệt kê clip CŨ của file mồ côi"
    assert mo_coi.exists() and _sha(mo_coi) == sha_mo_coi, "file mồ côi phải còn nguyên byte"


def test_tao_kho_moi_khong_co_file_san_thi_ten_file_nhu_cu(tmp_path):
    """Hợp đồng cũ giữ nguyên khi tên file suy ra chưa tồn tại."""
    e = _eng(tmp_path)
    kho = e.add_kho("A", "")
    assert kho["db"] == f"kho_{Engine._slug('A')}.pklz"


def test_giao_dien_xoa_kho_bi_giu_file_thi_bao_loi_khong_rerun_lang_le(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    kho_dir = tmp_path / "kho_gia"
    kho_dir.mkdir()
    (data_dir / "khos.json").write_text(json.dumps({
        "dang_dung": "KhoTest",
        "danh_sach": [{"ten": "KhoTest", "thu_muc": str(kho_dir), "db": "kho_test.pklz",
                       "id": "id_kho_test"}],
    }, ensure_ascii=False), encoding="utf-8")
    ghi_ht(data_dir / "kho_test.pklz", [(str(kho_dir / "a1.opus"), 5)])
    monkeypatch.setattr(Engine, "_xoa_an_toan", staticmethod(lambda p, so_lan=6: False))

    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    chon = next(s for s in at.selectbox if s.label.startswith("Xoá kho"))
    at = chon.set_value("KhoTest").run()
    at = next(c for c in at.checkbox
              if c.label.startswith("Tôi xác nhận muốn xóa vân tay")).check().run()
    at = next(b for b in at.button if b.label == "🗑️ Xoá kho «KhoTest»").click().run()

    assert not at.exception
    assert any("Chưa xoá được kho «KhoTest»" in x.value for x in at.error)
    ghi = json.loads((data_dir / "khos.json").read_text(encoding="utf-8"))
    assert [k["ten"] for k in ghi["danh_sach"]] == ["KhoTest"]
    assert (data_dir / "kho_test.pklz").exists()
