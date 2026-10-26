# -*- coding: utf-8 -*-
"""Audit C-1: công bố kho vân tay phải BỀN (flush + fsync TRƯỚC os.replace).

Chuẩn của dự án (``luu_tru.ghi_json_an_toan``; ``docs/MANAGED_RUNTIME_DESIGN.md`` §7):
ghi nguyên tử = file tạm + flush + ``os.fsync`` + ``os.replace``. Kho ``.pklz`` là dữ liệu
tốn hàng giờ để dựng; nếu ``database.pklz`` tạm (do tiến trình con audfprint ghi qua
``gzip.open`` + ``pickle.dump``, KHÔNG fsync) được ``os.replace`` đè lên kho cũ khi dữ liệu
còn nằm trong cache, mất điện ngay sau đó để lại kho cụt/toàn số 0 trong khi kho cũ đã bị
thay.

Mô hình trong test (synthetic, không audfprint, không mạng):
- ``os.fsync`` được bọc để ghi nhận DANH TÍNH file (st_dev, st_ino) đã được đẩy xuống đĩa.
- Bộ chạy giả (mô phỏng tiến trình con audfprint) ghi ``--dbase`` rồi đánh dấu file đó
  là "bẩn" (bỏ danh tính khỏi tập đã fsync) — đúng như audfprint thật: không fsync.
- ``os.replace`` được bọc: khi nguồn là ``database.pklz`` thì ghi lại nguồn đó đã bền chưa.
Hành vi ĐÚNG: mọi lần công bố ``database.pklz`` phải xảy ra sau một ``os.fsync`` của chính
file đó (sau lần ghi cuối).
"""

import os
from pathlib import Path

import pytest

from test_kho_build_an_toan import _eng, _kho, doc_ht, runner_gia


def _danh_tinh_fd(fd):
    st = os.fstat(fd)
    return (st.st_dev, st.st_ino)


def _danh_tinh_path(path):
    st = os.stat(path)
    return (st.st_dev, st.st_ino)


@pytest.fixture
def theo_doi_ben(monkeypatch):
    """Theo dõi fsync / replace theo danh tính file."""
    ben = set()          # danh tính file đã fsync sau lần ghi cuối
    cong_bo = []         # [(src, dst, da_fsync)]
    fsync_goc = os.fsync
    replace_goc = os.replace

    def fsync(fd):
        try:
            ben.add(_danh_tinh_fd(fd))
        except OSError:
            pass
        return fsync_goc(fd)

    def replace(src, dst, *a, **kw):
        s = os.fspath(src)
        if s.endswith("database.pklz"):
            cong_bo.append((s, os.fspath(dst), _danh_tinh_path(s) in ben))
        return replace_goc(src, dst, *a, **kw)

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "replace", replace)

    def danh_dau_ban(path):
        ben.discard(_danh_tinh_path(path))

    return ben, cong_bo, danh_dau_ban


def _runner_khong_fsync(e, so_hash, danh_dau_ban):
    """Bộ chạy giả như audfprint thật: ghi --dbase bằng gzip+pickle, KHÔNG fsync."""
    goc = runner_gia(e, so_hash)

    def chay(lenh, on_line=None, **kw):
        rc, duoi = goc(lenh, on_line, **kw)
        db = lenh[lenh.index("--dbase") + 1]
        if os.path.exists(db):
            danh_dau_ban(db)   # trang bẩn do tiến trình con ghi, chưa xuống đĩa
        return rc, duoi
    return chay


@pytest.mark.parametrize("mode", ["new", "add"])
def test_cong_bo_kho_phai_fsync_truoc_replace(tmp_path, theo_doi_ben, mode):
    _ben, cong_bo, danh_dau_ban = theo_doi_ben
    e = _eng(tmp_path)
    nguon, db = _kho(e, tmp_path, "A", ["a.opus"], [("cu.opus", 9)])
    e._run_stream = _runner_khong_fsync(e, {"a.opus": 7}, danh_dau_ban)

    e.build_database(str(nguon), mode=mode)

    # Công bố đã thật sự xảy ra (không phải test hỏng vì không công bố gì).
    assert "a.opus" in doc_ht(e.db_file)
    assert cong_bo, "không thấy os.replace(database.pklz, kho) — test chưa chạm đường công bố"
    for src, dst, da_fsync in cong_bo:
        assert da_fsync, (
            f"[{mode}] os.replace công bố {Path(src).name} -> {Path(dst).name} khi file tạm "
            "CHƯA fsync: mất điện ngay sau đó có thể để lại kho cụt và kho cũ đã bị thay")


def test_cong_bo_nhanh_permissionerror_cung_phai_fsync(tmp_path, theo_doi_ben, monkeypatch):
    _ben, cong_bo, danh_dau_ban = theo_doi_ben
    e = _eng(tmp_path)
    nguon, db = _kho(e, tmp_path, "A", ["a.opus"], [("cu.opus", 9)])
    e._run_stream = _runner_khong_fsync(e, {"a.opus": 7}, danh_dau_ban)

    replace_dang_boc = os.replace
    da_nem = []

    def replace_khoa_kho_cu(src, dst, *a, **kw):
        if (not da_nem and os.fspath(src).endswith("database.pklz")
                and os.path.normcase(os.fspath(dst)) == os.path.normcase(str(db))):
            da_nem.append(1)
            # ghi nhận lần thử công bố, rồi giả lập file cũ bị khoá
            cong_bo.append((os.fspath(src), os.fspath(dst),
                            _danh_tinh_path(os.fspath(src)) in _ben))
            raise PermissionError(13, "file đang bị khoá (giả lập)", os.fspath(dst))
        return replace_dang_boc(src, dst, *a, **kw)

    monkeypatch.setattr(os, "replace", replace_khoa_kho_cu)

    r = e.build_database(str(nguon), mode="new")

    assert da_nem, "không vào được nhánh PermissionError"
    assert any("bị khóa" in c for c in r.get("canh_bao", []))
    assert os.path.normcase(e.db_file) != os.path.normcase(str(db))
    assert "a.opus" in doc_ht(e.db_file)
    assert len(cong_bo) == 2, cong_bo
    for src, dst, da_fsync in cong_bo:
        assert da_fsync, (
            f"[PermissionError] os.replace công bố {Path(src).name} -> {Path(dst).name} khi "
            "file tạm CHƯA fsync, trong khi sổ đăng ký (đã fsync) trỏ sang file mới không bền")
