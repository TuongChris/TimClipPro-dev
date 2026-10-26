# -*- coding: utf-8 -*-
"""Audit C-3: «Bổ sung» đa nhân nhân đôi tên clip 0 hash trong kho `.pklz`.

Clip 0 hash (file hỏng/im lặng, ``--continue-on-error``) vẫn được ghi TÊN vào bảng và
được thử lại ở lần «Bổ sung» sau (engine chỉ bỏ qua clip CÓ hash). Nhánh một nhân dùng
``HashTable.store`` → ``name_to_id(add_if_missing=True)`` nên tái dùng đúng id cũ. Nhánh
đa nhân (GUI: ``ncores=0`` → tự dò > 1) chạy ``instrumented_multiproc_add``: worker tạo
bảng MỚI rồi cha ``hash_tab.merge`` — ``self.names += ht.names`` không khử trùng, nên
clip thành ra có HAI bản ghi (X(0) + X(N)).

Hành vi ĐÚNG: mỗi file clip có đúng MỘT bản ghi trong kho, bất kể số nhân.

Chỉ dữ liệu tổng hợp trong thư mục tạm; phân tích audio được thay bằng analyzer giả
(cấp module vì Windows dùng spawn), còn ``instrumented_multiproc_add``, tiến trình con,
``HashTable.merge/remove`` và ``Engine.build_database`` đều là mã THẬT.
"""

import gzip
import json
import os
import pickle
import sys
import time
from collections import Counter
from pathlib import Path

import audfprint_progress_runner as runner
import common_original as co
from engine import Engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audfprint-master"))
import hash_table  # noqa: E402

PREFIX = "TIMCLIP_FINGERPRINT_EVENT "


def _cap(n: int) -> list:
    return [(t % 16, t % 16) for t in range(n)]


class AnalyzerGia:
    """Thay ``audfprint_analyze.Analyzer`` trong worker: số hash theo tên file."""

    def __init__(self, so_hash: dict):
        self.so_hash = dict(so_hash)

    def wavfile2hashes(self, filename):
        return _cap(self.so_hash.get(os.path.basename(filename), 0))


# ---------------------------------------------------------------------------
#  1) Mức đơn vị: đúng đường merge của runner đa nhân
# ---------------------------------------------------------------------------

def test_multiproc_add_khong_nhan_doi_ten_clip_0_hash(tmp_path):
    x = str(tmp_path / "x.opus")
    y = str(tmp_path / "y.opus")

    # Đối chứng nhánh MỘT nhân: store() tái dùng id → 1 bản ghi.
    mot_nhan = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
    mot_nhan.store(x, [])
    mot_nhan.store(y, _cap(5))
    mot_nhan.store(x, _cap(6))
    assert mot_nhan.names.count(x) == 1

    # Nhánh ĐA nhân (runner thật, 2 tiến trình con thật).
    bang = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
    bang.store(x, [])          # lần build trước: x hỏng/im lặng → 0 hash
    bang.store(y, _cap(5))
    runner.instrumented_multiproc_add(AnalyzerGia({"x.opus": 6}), bang, [x],
                                      lambda msgs: None, 2)

    ban_ghi = [(n, int(h)) for n, h in zip(bang.names, bang.hashesperid) if n == x]
    assert len(ban_ghi) == 1, f"x có {len(ban_ghi)} bản ghi trong kho: {ban_ghi}"


# ---------------------------------------------------------------------------
#  2) Mức Engine: «Bổ sung» với ncores > 1 (như GUI trên máy nhiều nhân)
# ---------------------------------------------------------------------------

def _ghi(path, muc):
    ht = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
    for ten, so in muc:
        ht.store(str(ten), _cap(so))
    with gzip.open(path, "wb") as f:
        pickle.dump(ht, f)


def _eng(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"),
               out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e._cap_nhat_snapshot_sau_build = lambda *a: []
    e.config.ncores = 2
    # db_clips() trả [] khi không có audfprint; trỏ tới bản vendored THẬT (chỉ để đọc kho —
    # mọi lệnh audfprint vẫn đi qua `_run_stream` giả bên dưới).
    e.audfprint = str(Path(__file__).resolve().parents[1] / "audfprint-master" / "audfprint.py")
    return e


def _runner_da_nhan(so_hash: dict, lenh_da_chay: list):
    """audfprint giả bám đúng audfprint.main: ``--ncores`` > 1 → ``multiproc_add`` (bản
    runner THẬT); ``remove`` → ``HashTable.remove`` THẬT. Chỉ thay phần giải mã audio."""
    def chay(lenh, on_line=None, **kw):
        db = lenh[lenh.index("--dbase") + 1]
        ncores = int(lenh[lenh.index("--ncores") + 1])
        ds = [p for p in Path(lenh[lenh.index("--list") + 1])
              .read_text(encoding="utf-8").splitlines() if p]
        lenh_da_chay.append((list(lenh), ds))
        with gzip.open(db, "rb") as f:
            ht = pickle.load(f)
        if "remove" in lenh[:5]:
            for ten in ds:
                ht.remove(ten)
        else:
            for p in ds:
                n = so_hash.get(os.path.basename(p), 0)
                on_line(PREFIX + json.dumps({"event": "clip_started", "file": p}))
                on_line(PREFIX + json.dumps({
                    "event": "clip_finished", "file": p,
                    "status": "success" if n else "failed",
                    "category": "" if n else "zero_hashes"}))
            assert ncores > 1
            runner.instrumented_multiproc_add(AnalyzerGia(so_hash), ht, ds,
                                              lambda msgs: None, ncores)
        with gzip.open(db, "wb") as f:
            pickle.dump(ht, f)
        return 0, []
    return chay


def _kho(e, tmp_path, muc):
    nguon = tmp_path / "nguon"
    nguon.mkdir()
    for ten, _ in muc:
        (nguon / ten).write_bytes(b"audio")
    e.add_kho("A", str(nguon))
    _ghi(e.db_file, [(str(nguon / ten), so) for ten, so in muc])
    moc = time.time() - 100
    os.utime(e.db_file, (moc, moc))
    for ten, _ in muc:
        os.utime(nguon / ten, (moc - 50, moc - 50))
    return nguon


def _dem(e) -> Counter:
    return Counter(c["ten"] for c in e.db_clips(bo_cache=True))


def test_bo_sung_da_nhan_clip_0_hash_duoc_sua_chi_con_mot_ban_ghi(tmp_path):
    """Build #1: x hỏng → x(0). Đồng bộ kênh sửa x. «Bổ sung» đa nhân → x phải có 1 bản ghi."""
    e = _eng(tmp_path)
    nguon = _kho(e, tmp_path, [("x.opus", 0), ("y.opus", 5)])
    lenh = []
    e._run_stream = _runner_da_nhan({"x.opus": 6, "y.opus": 5}, lenh)

    kq = e.build_database(str(nguon), "add")

    assert kq.get("da_ghi_kho") is True, kq
    assert [ds for _, ds in lenh] == [[str(nguon / "x.opus")]], "chỉ thử lại x (0 hash)"
    ds = e.db_clips(bo_cache=True)
    so_ban_ghi_kho = _dem(e)["x.opus"]
    so_ban_ghi_nguon_chung = co.dem_ten_kho(ds).get("x.opus", 0)
    assert (so_ban_ghi_kho, so_ban_ghi_nguon_chung, len(ds)) == (1, 1, 2), (
        f"db_clips có {len(ds)} bản ghi: {ds}; x đếm {so_ban_ghi_kho} lần "
        f"(dem_ten_kho → {so_ban_ghi_nguon_chung}, >1 = 'ten_trung', không bao giờ "
        "xác nhận được nguồn chung)")


def test_bo_sung_da_nhan_clip_van_hong_khong_tich_them_ban_ghi_rong(tmp_path):
    """x vẫn hỏng; mỗi lần «Bổ sung» có clip mới khác (kho được công bố) → x không được
    tích thêm bản ghi 0 hash."""
    e = _eng(tmp_path)
    nguon = _kho(e, tmp_path, [("x.opus", 0), ("y.opus", 5)])
    so_hash = {"x.opus": 0, "y.opus": 5, "z1.opus": 4, "z2.opus": 7}
    e._run_stream = _runner_da_nhan(so_hash, [])

    dem_x = []
    for ten in ("z1.opus", "z2.opus"):
        (nguon / ten).write_bytes(b"audio")
        kq = e.build_database(str(nguon), "add")
        assert kq.get("da_ghi_kho") is True, kq
        dem_x.append(_dem(e)["x.opus"])

    assert dem_x == [1, 1], f"số bản ghi x sau mỗi lần bổ sung: {dem_x}"


def test_lam_moi_sau_khi_da_trung_ten_chi_con_van_tay_moi(tmp_path):
    """Phần (c) của phát hiện: sau khi đã có x(0)+x(6), file x lại bị thay → «Bổ sung»
    phải để lại ĐÚNG một bản ghi x mang vân tay MỚI (không còn x(6) cũ).

    Kết quả kiểm chứng trên 6ee8f43: test này XANH — `_go_van_tay_cu` liệt kê MỌI bản ghi
    của x trong `ds_cu` (x xuất hiện 2 lần) nên `audfprint remove` chạy 2 lần: lần 1 gỡ
    ô rỗng (0 hash), lần 2 gỡ x(6). Phần (c) của phát hiện KHÔNG tái hiện được."""
    e = _eng(tmp_path)
    nguon = _kho(e, tmp_path, [("x.opus", 0), ("y.opus", 5)])
    so_hash = {"x.opus": 6, "y.opus": 5}
    lenh = []
    e._run_stream = _runner_da_nhan(so_hash, lenh)
    e.build_database(str(nguon), "add")
    truoc = [(c["ten"], c["so_hash"]) for c in e.db_clips(bo_cache=True)]

    sau_kho = os.path.getmtime(e.db_file) + 10
    (nguon / "x.opus").write_bytes(b"audio moi")
    os.utime(nguon / "x.opus", (sau_kho, sau_kho))
    so_hash["x.opus"] = 8
    lenh.clear()
    kq = e.build_database(str(nguon), "add")

    sau = [(c["ten"], c["so_hash"]) for c in e.db_clips(bo_cache=True)]
    assert kq.get("da_ghi_kho") is True, kq
    assert sorted(sau) == [("x.opus", 8), ("y.opus", 5)], (
        f"trước làm mới: {truoc}; sau: {sau}; lệnh: {[(cmd[3:5], ds) for cmd, ds in lenh]}")
