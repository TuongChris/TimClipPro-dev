# -*- coding: utf-8 -*-
"""Audit C-2: «Tạo lại kho từ đầu» (mode="new") với thư mục KHÁC mà KHÔNG công bố được (Dừng / audfprint lỗi)
không được đổi thư mục nguồn của kho trong sổ đăng ký.

Bất biến: kho .pklz vẫn chứa vân tay của nguồn A (job không công bố) thì ``khos.json`` phải vẫn nói ``thu_muc = A``;
nếu không, lớp chống trộn nguồn (``_kiem_nguon_bo_sung``) so B với B và cho «Bổ sung» clip của B vào kho đang chứa A
— đúng sự cố trộn nguồn 15/10.

Dữ liệu TỔNG HỢP trong ``tmp_path``; subprocess audfprint được thay bằng hàm giả (mẫu của
``tests/test_kho_build_an_toan.py``). ``pickle`` chỉ đọc file ``.pklz`` do chính test này ghi.
"""

import gzip
import json
import os
import pickle
import sys
from pathlib import Path

import pytest

import engine
from engine import Engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audfprint-master"))
import hash_table  # noqa: E402

PREFIX = "TIMCLIP_FINGERPRINT_EVENT "


def ghi_ht(path, muc) -> None:
    ht = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
    for ten, so in muc:
        ht.store(str(ten), [(t % 16, t % 16) for t in range(so)])
    with gzip.open(path, "wb") as f:
        pickle.dump(ht, f)


def doc_ht(path) -> dict:
    with gzip.open(path, "rb") as f:
        ht = pickle.load(f)
    return {os.path.basename(n): int(h) for n, h in zip(ht.names, ht.hashesperid)}


def _eng(tmp_path) -> Engine:
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e._cap_nhat_snapshot_sau_build = lambda *a: []
    return e


def _thu_muc(tmp_path, ten, files) -> Path:
    d = tmp_path / ten
    d.mkdir(exist_ok=True)
    for f in files:
        (d / f).write_bytes(b"audio")
    return d


def runner_gia(so_hash: dict):
    """Giả lập audfprint build thành công: ``so_hash[tên file] = số hash``."""
    def chay(lenh, on_line=None, **kw):
        sub = lenh[4]
        db = lenh[lenh.index("--dbase") + 1]
        ds = [p for p in Path(lenh[lenh.index("--list") + 1]).read_text(encoding="utf-8").split("\n") if p]
        muc = []
        if sub == "add":
            with gzip.open(db, "rb") as f:
                cu = pickle.load(f)
            muc = [(n, int(h)) for n, h in zip(cu.names, cu.hashesperid)]
        for p in ds:
            n = so_hash.get(os.path.basename(p), 0)
            on_line(PREFIX + json.dumps({"event": "clip_started", "file": p}))
            on_line(PREFIX + json.dumps({"event": "clip_finished", "file": p,
                                         "status": "success" if n else "failed",
                                         "category": "" if n else "zero_hashes"}))
            muc.append((p, n))
        ghi_ht(db, muc)
        return 0, []
    return chay


def runner_huy(lenh, on_line=None, **kw):
    """Người dùng bấm «Dừng» khi audfprint đang chạy."""
    raise engine.Cancelled()


def runner_rc1(lenh, on_line=None, **kw):
    """audfprint thoát mã lỗi (ổ đầy, ffmpeg hỏng...)."""
    return 1, ["Traceback: OSError: [Errno 28] No space left on device"]


def _kho_A_da_dung(tmp_path):
    """Kho «SML» gắn thư mục A, đã có vân tay của a.opus (dựng thật qua build_database)."""
    a = _thu_muc(tmp_path, "nguon_A", ["a.opus"])
    b = _thu_muc(tmp_path, "nguon_B", ["b.opus"])
    e = _eng(tmp_path)
    e.add_kho("SML", str(a))
    e._run_stream = runner_gia({"a.opus": 9, "b.opus": 9})
    r = e.build_database(str(a), mode="new")
    assert not r.get("da_huy")
    assert doc_ht(e.db_file) == {"a.opus": 9}
    return e, a, b


def _thu_muc_so_dang_ky(e) -> str:
    return next(k for k in e._doc_khos()["danh_sach"] if k["ten"] == "SML")["thu_muc"]


def _cung(p, q) -> bool:
    return os.path.normcase(os.path.abspath(str(p))) == os.path.normcase(os.path.abspath(str(q)))


def test_tao_lai_tu_dau_bi_dung_thi_so_dang_ky_van_tro_nguon_cu(tmp_path):
    e, a, b = _kho_A_da_dung(tmp_path)
    db = Path(e.db_file)
    truoc = db.read_bytes()

    e._run_stream = runner_huy
    r = e.build_database(str(b), mode="new")

    assert r["da_huy"] is True
    assert db.read_bytes() == truoc, "kho .pklz phải nguyên (vẫn chỉ có vân tay của A)"
    assert _cung(_thu_muc_so_dang_ky(e), a), (
        f"khos.json đổi thu_muc sang «{_thu_muc_so_dang_ky(e)}» dù job bị huỷ và kho vẫn chứa A")
    assert _cung(e.kho_thu_muc, a), f"Engine giao diện thấy kho_thu_muc = «{e.kho_thu_muc}»"


def test_tao_lai_tu_dau_audfprint_loi_thi_so_dang_ky_van_tro_nguon_cu(tmp_path):
    e, a, b = _kho_A_da_dung(tmp_path)
    db = Path(e.db_file)
    truoc = db.read_bytes()

    e._run_stream = runner_rc1
    with pytest.raises(RuntimeError, match="mã lỗi 1"):
        e.build_database(str(b), mode="new")

    assert db.read_bytes() == truoc
    assert _cung(_thu_muc_so_dang_ky(e), a), (
        f"khos.json đổi thu_muc sang «{_thu_muc_so_dang_ky(e)}» dù build lỗi và kho vẫn chứa A")
    assert _cung(e.kho_thu_muc, a)


def test_sau_tao_lai_bi_dung_bo_sung_tu_nguon_moi_van_bi_chan(tmp_path):
    """Hệ quả người dùng thấy: sau lần «Tạo lại» bị Dừng, «Bổ sung» từ B KHÔNG được trộn B vào kho đang chứa A."""
    e, a, b = _kho_A_da_dung(tmp_path)
    db = Path(e.db_file)
    truoc = db.read_bytes()

    e._run_stream = runner_huy
    assert e.build_database(str(b), mode="new")["da_huy"] is True

    e._run_stream = runner_gia({"a.opus": 9, "b.opus": 9})
    try:
        e.build_database(str(b), mode="add")
    except RuntimeError as exc:
        assert "Không bổ sung" in str(exc)
    sau = doc_ht(db)
    assert db.read_bytes() == truoc, f"kho A bị trộn clip của nguồn B: {sorted(sau)}"


def test_tao_lai_tu_dau_khong_clip_nao_co_hash_thi_so_dang_ky_van_tro_nguon_cu(tmp_path):
    """Build xong nhưng KHÔNG công bố (mọi clip 0 hash → «kho hiện tại giữ nguyên»): nguồn trong sổ cũng giữ nguyên."""
    e, a, b = _kho_A_da_dung(tmp_path)
    db = Path(e.db_file)
    truoc = db.read_bytes()

    e._run_stream = runner_gia({"a.opus": 9, "b.opus": 0})
    try:
        r = e.build_database(str(b), mode="new")
        assert r.get("da_ghi_kho") is False
    except RuntimeError as exc:
        assert "Giữ nguyên kho cũ" in str(exc)

    assert db.read_bytes() == truoc
    assert _cung(_thu_muc_so_dang_ky(e), a)
    assert _cung(e.kho_thu_muc, a)


def test_tao_lai_tu_dau_cong_bo_thanh_cong_thi_so_dang_ky_doi_sang_nguon_moi(tmp_path):
    """Đối chứng: «Tạo lại kho từ đầu» công bố được → sổ + Engine trỏ nguồn mới; «Bổ sung» từ nguồn cũ bị chặn."""
    e, a, b = _kho_A_da_dung(tmp_path)

    r = e.build_database(str(b), mode="new")

    assert r["da_ghi_kho"] is True
    assert doc_ht(e.db_file) == {"b.opus": 9}
    assert _cung(_thu_muc_so_dang_ky(e), b)
    assert _cung(e.kho_thu_muc, b)
    sau = Path(e.db_file).read_bytes()
    with pytest.raises(RuntimeError, match="Không bổ sung"):
        e.build_database(str(a), mode="add")
    assert Path(e.db_file).read_bytes() == sau


def test_tao_lai_sang_nguon_moi_ghi_so_loi_snapshot_metadata_van_theo_nguon_moi(tmp_path, monkeypatch):
    """Audit WR-3: công bố vân tay của B xong mà ghi sổ kho lỗi (khoá JSON, đĩa) → sổ + Engine còn trỏ A. Snapshot
    metadata (dựng lại từ đầu sau «Tạo lại kho») phải mô tả kho VỪA công bố — tên/link video gốc của B — chứ không lấy
    ``clips_meta.json`` của thư mục cũ A gắn cho vân tay của B.

    Tình huống thật: B là bản chép mới của cùng kênh (cùng tên file), đồng bộ kênh đã cập nhật tiêu đề trong B."""
    ten = "20260101 - Clip mau [abcdefghijk].opus"
    a = _thu_muc(tmp_path, "nguon_A", [ten])
    b = _thu_muc(tmp_path, "nguon_B", [ten])
    for thu_muc, tieu_de in ((a, "Tiêu đề cũ ở A"), (b, "Tiêu đề mới ở B")):
        (thu_muc / "clips_meta.json").write_text(json.dumps({ten: {
            "id": "abcdefghijk", "title": tieu_de, "url": "https://youtu.be/abcdefghijk",
            "upload_date": "20260101", "duration": 60.0}}, ensure_ascii=False), encoding="utf-8")
    e = _eng(tmp_path)
    del e._cap_nhat_snapshot_sau_build  # dùng bước snapshot THẬT
    e.audfprint = str(Path(engine.__file__).resolve().parent / "audfprint-master" / "audfprint.py")  # để db_clips đọc kho
    e.add_kho("SML", str(a))
    e._run_stream = runner_gia({ten: 9})
    assert e.build_database(str(a), mode="new")["da_ghi_kho"] is True
    snapshot = Path(e._metadata_snapshot_path())
    assert json.loads(snapshot.read_text(encoding="utf-8"))["clips"][ten]["title"] == "Tiêu đề cũ ở A"

    def so_loi(ham_sua):
        raise OSError("khos.json đang bị khoá (giả lập)")

    monkeypatch.setattr(e, "_sua_khos", so_loi)
    r = e.build_database(str(b), mode="new")

    assert r["da_ghi_kho"] is True
    assert any("chưa cập nhật được sổ đăng ký kho" in c for c in r["canh_bao"]), r["canh_bao"]
    assert _cung(_thu_muc_so_dang_ky(e), a)  # sổ không ghi được: vẫn A (đúng tình huống WR-3)
    assert [os.path.dirname(c["duong_dan"]) for c in e.db_clips(bo_cache=True)] == [str(b)]
    muc = json.loads(snapshot.read_text(encoding="utf-8"))["clips"][ten]
    assert muc["title"] == "Tiêu đề mới ở B", (
        f"snapshot của kho chứa vân tay B lấy metadata từ thư mục cũ A: {muc['title']!r}")
