# -*- coding: utf-8 -*-
"""Bấm Dừng giữa lúc dựng kho vân tay vẫn giữ phần ĐÃ xong (16/11/2026; D-31 «Chưa làm: lưu theo lô»).

Kho lớn dựng qua đêm: trước đây Dừng là mất SẠCH phần đã tính (LOI_DA_GAP mục 38 — 353 clip). Bốn tính chất phải giữ:

1. Dừng khi «Tạo kho» (kho chưa có vân tay dùng được) hoặc «Bổ sung»: mọi clip đã tạo XONG vân tay được lưu qua CÙNG đường
   kiểm + công bố của lúc xong bình thường (kho tạm → ``_kiem_kho_tam`` → ``channel._dat_vao_kho`` → sổ kho, snapshot);
   «Bổ sung» sau chỉ làm phần còn lại.
2. Dừng «Tạo lại từ đầu» một kho đang có vân tay (hay không đọc được): kho cũ giữ nguyên từng byte, câu dừng nói rõ vì sao.
3. Clip đang làm dở lúc Dừng không bao giờ được lưu nửa chừng, không được tính là xong.
4. Lưu phần đã xong mà lỗi: kho cũ nguyên vẹn, báo lỗi rõ.

Audfprint giả phát đúng event của runner thật và làm như ``process_runner`` khi cờ huỷ bật: gọi ``khi_huy``; không có
(hoặc trả False) là bị giết → ``Cancelled``. Runner + worker chạy bằng tiến trình con THẬT, chỉ thay phân tích audio.
Chỉ dữ liệu tổng hợp trong thư mục tạm; ``pickle`` chỉ chạm file ``.pklz`` do chính test ghi.
"""

import gzip
import json
import os
import pickle
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

import audfprint_progress_runner as runner
import channel
from engine import Cancelled, Engine
from kho_gia import ma_ghi_kho_cho_process_con
from scan_ui import tom_tat_tao_van_tay
from test_kho_build_an_toan import ghi_ht

GOC = Path(__file__).resolve().parents[1]
VENDOR = GOC / "audfprint-master"
PREFIX = runner.PREFIX


def _eng(tmp_path) -> Engine:
    e = Engine(root=str(GOC), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    goi = []

    def snapshot(*a):
        goi.append(a)
        return []

    e._cap_nhat_snapshot_sau_build = snapshot
    e.snapshot_goi = goi
    return e


def _nguon(tmp_path, n: int) -> Path:
    d = tmp_path / "nguon"
    d.mkdir()
    for i in range(n):
        (d / f"clip_{i}.opus").write_bytes(b"audio")
    return d


def doc_ht(path) -> dict:
    with gzip.open(path, "rb") as f:
        ht = pickle.load(f)
    return {os.path.basename(n): int(h) for n, h in zip(ht.names, ht.hashesperid) if n}   # n None = đã gỡ


def _so(e) -> dict:
    return next(k for k in e._doc_khos()["danh_sach"] if k["ten"] == "A")


def audfprint_gia(e, xong=None):
    """Clip thứ ``i`` của danh sách xong khi ``i in xong``; clip chưa xong đầu tiên đang làm dở thì người dùng bấm Dừng.

    ``xong=None``: chạy hết, không ai bấm Dừng. ``remove`` gỡ bằng ``HashTable.remove`` thật."""
    da_chay = []

    def chay(lenh, on_line=None, khi_huy=None, **kw):
        db = lenh[lenh.index("--dbase") + 1]
        ds = [p for p in Path(lenh[lenh.index("--list") + 1]).read_text(encoding="utf-8").splitlines() if p]
        ht = None
        if os.path.exists(db):
            with gzip.open(db, "rb") as f:
                ht = pickle.load(f)
        if "remove" in lenh:
            if e.cancel_event.is_set() and (khi_huy is None or not khi_huy()):
                raise Cancelled()                       # như process_runner: cờ huỷ còn bật là giết lệnh gỡ
            for ten in ds:
                ht.remove(ten)
            with gzip.open(db, "wb") as f:
                pickle.dump(ht, f)
            return 0, []
        da_chay.append(ds)
        muc = [] if ht is None else [(n, int(h)) for n, h in zip(ht.names, ht.hashesperid) if n]
        lam_do = None
        for i, p in enumerate(ds):
            if xong is not None and i not in xong:
                lam_do = lam_do or p
                continue
            on_line(PREFIX + json.dumps({"event": "clip_started", "file": p}))
            on_line(PREFIX + json.dumps({"event": "clip_finished", "file": p, "status": "success"}))
            muc.append((p, 7))
        if xong is not None:
            if lam_do:
                on_line(PREFIX + json.dumps({"event": "clip_started", "file": lam_do}))
            e.cancel_event.set()                        # người dùng bấm Dừng
            if khi_huy is None or not khi_huy():
                raise Cancelled()                       # process_runner giết cả cây tiến trình
            assert os.path.isfile(os.path.join(os.path.dirname(db), runner.TEN_CO_DUNG)), "runner phải được nhờ dừng"
        ghi_ht(db, muc)
        return 0, []

    chay.da_chay = da_chay
    return chay


# ---------------------------------------------------------------------------
#  1) «Tạo kho» / «Bổ sung» bị Dừng: lưu đúng phần đã xong, «Bổ sung» sau làm tiếp
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["new", "add"])
def test_dung_kho_moi_luu_dung_cac_clip_da_xong_qua_duong_kiem_va_cong_bo(tmp_path, monkeypatch, mode):
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 5)
    e.add_kho("A", str(nguon))
    so_truoc = _so(e)
    kiem = []
    kiem_goc = Engine._kiem_kho_tam

    def kiem_that(self, *a, **k):
        kiem.append(kiem_goc(self, *a, **k))
        return kiem[-1]

    monkeypatch.setattr(Engine, "_kiem_kho_tam", kiem_that)
    e._run_stream = audfprint_gia(e, xong={0, 1})
    su_kien = []

    r = e.build_database(str(nguon), mode=mode, progress_event=su_kien.append)

    assert doc_ht(e.db_file) == {"clip_0.opus": 7, "clip_1.opus": 7}, "clip đang làm dở (clip_2) không được lưu"
    # Kiểm như lúc xong; clip chưa tới lượt không bị kể là «không tạo được vân tay».
    assert kiem == [(True, [])]
    assert (r["da_huy"], r["da_ghi_kho"], r["thanh_cong"], r["da_xu_ly"], r["so_clip"]) == (True, True, 2, 2, 5)
    cau = " ".join(r["canh_bao"])
    assert "đã lưu 2 clip" in cau and "«Bổ sung»" in cau and "3 clip" in cau, cau
    so_sau = _so(e)
    assert so_sau["revision"] != so_truoc.get("revision") and so_sau["moc_build"] > 0
    assert so_sau["maxtimebits"] == channel.MAXTIMEBITS_MAC_DINH
    assert e.snapshot_goi == [(mode, str(nguon) if mode == "new" else None)]
    assert su_kien[-1].status == "cancelled" and "đã lưu 2 clip" in su_kien[-1].message
    assert not any((Path(e.data_dir) / "fingerprint_jobs").iterdir()), "bản làm việc phải được dọn"


def test_bo_sung_sau_khi_dung_chi_lam_phan_con_lai_ke_ca_clip_dang_lam_do(tmp_path):
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 5)
    e.add_kho("A", str(nguon))
    e._run_stream = audfprint_gia(e, xong={0, 1})
    e.build_database(str(nguon), mode="new")

    tiep = audfprint_gia(e)
    e._run_stream = tiep
    r = e.build_database(str(nguon), mode="add")

    assert [os.path.basename(p) for p in tiep.da_chay[0]] == ["clip_2.opus", "clip_3.opus", "clip_4.opus"]
    assert (r["da_huy"], r["bo_qua"], r["thanh_cong"]) == (False, 2, 3)
    assert doc_ht(e.db_file) == {f"clip_{i}.opus": 7 for i in range(5)}


def test_dung_khi_bo_sung_giu_moi_clip_cu_va_them_dung_phan_da_xong(tmp_path):
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 3)
    e.add_kho("A", str(nguon))
    (nguon / "cu.opus").write_bytes(b"audio")
    ghi_ht(e.db_file, [(str(nguon / "cu.opus"), 9)])
    e._run_stream = audfprint_gia(e, xong={0})

    r = e.build_database(str(nguon), mode="add")

    assert doc_ht(e.db_file) == {"cu.opus": 9, "clip_0.opus": 7}
    assert (r["da_huy"], r["da_ghi_kho"], r["thanh_cong"], r["bo_qua"]) == (True, True, 1, 1)


def test_dung_khi_moi_clip_da_xong_thi_luu_du_va_bao_hoan_tat(tmp_path):
    """Dừng tới lúc runner đã gộp bảng (mọi clip đã xong): không có gì «còn lại», kết quả là hoàn tất bình thường."""
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 3)
    e.add_kho("A", str(nguon))
    e._run_stream = audfprint_gia(e, xong={0, 1, 2})

    r = e.build_database(str(nguon), mode="new")

    assert doc_ht(e.db_file) == {f"clip_{i}.opus": 7 for i in range(3)}
    assert (r["da_huy"], r["da_ghi_kho"], r["thanh_cong"]) == (False, True, 3)


def test_dung_khi_bo_sung_de_viec_go_clip_da_cach_ly_cho_lan_sau(tmp_path):
    """Lệnh gỡ vân tay clip đã cách ly chạy SAU bước thêm: cờ huỷ còn bật thì nó bị giết và mất cả phần đã xong.
    Dừng thì chưa gỡ (kho không tệ hơn trước); «Bổ sung» lần sau gỡ như thường."""
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 2)
    e.add_kho("A", str(nguon))
    cu = nguon / "Ten cu [abcdefghijk].opus"
    ghi_ht(e.db_file, [(str(cu), 9)])
    (nguon / channel.THU_MUC_HONG).mkdir()
    (nguon / channel.THU_MUC_HONG / f"261116-120000_{cu.name}").write_bytes(b"audio hong")
    (nguon / "Ten moi [abcdefghijk].opus").write_bytes(b"audio")     # bản thay thế cùng mã video, chạy đầu tiên
    e._run_stream = audfprint_gia(e, xong={0})

    r = e.build_database(str(nguon), mode="add")

    assert doc_ht(e.db_file) == {cu.name: 9, "Ten moi [abcdefghijk].opus": 7}
    assert (r["da_huy"], r["da_ghi_kho"], r["thanh_cong"]) == (True, True, 1)

    e._run_stream = audfprint_gia(e)
    r = e.build_database(str(nguon), mode="add")

    assert doc_ht(e.db_file) == {"Ten moi [abcdefghijk].opus": 7, "clip_0.opus": 7, "clip_1.opus": 7}
    assert any("Gỡ vân tay 1 clip đã bị cách ly" in c for c in r["canh_bao"]), r["canh_bao"]


def test_dung_truoc_khi_clip_nao_xong_khong_ghi_kho(tmp_path):
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 3)
    e.add_kho("A", str(nguon))
    e._run_stream = audfprint_gia(e, xong=set())

    r = e.build_database(str(nguon), mode="new")

    assert not Path(e.db_file).exists()
    assert (r["da_huy"], r.get("da_ghi_kho"), r["thanh_cong"]) == (True, None, 0)


# ---------------------------------------------------------------------------
#  2) «Tạo lại từ đầu»: không bao giờ thay một kho đang có vân tay bằng một phần
# ---------------------------------------------------------------------------

def test_dung_tao_lai_tu_dau_kho_dang_co_van_tay_giu_nguyen_tung_byte(tmp_path):
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 4)
    e.add_kho("A", str(nguon))
    ghi_ht(e.db_file, [(str(nguon / "clip_0.opus"), 9)])
    db, so = Path(e.db_file), Path(e.kho_file)
    truoc = (db.read_bytes(), so.read_bytes())
    e._run_stream = audfprint_gia(e, xong={0, 1})

    r = e.build_database(str(nguon), mode="new")

    assert (db.read_bytes(), so.read_bytes()) == truoc, "kho đầy đủ không được thay bằng một phần"
    assert (r["da_huy"], r.get("da_ghi_kho"), r["thanh_cong"]) == (True, None, 0)
    cau = " ".join(r["canh_bao"])
    assert "«Tạo lại từ đầu»" in cau and "giữ nguyên" in cau and "2 clip" in cau, cau


@pytest.mark.parametrize("kho_cu, luu", [("chi_ban_ghi_0_hash", True), ("khong_doc_duoc", False)])
def test_tao_lai_tu_dau_chi_luu_phan_xong_khi_kho_cu_khong_co_van_tay_dung_duoc(tmp_path, kho_cu, luu):
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 3)
    e.add_kho("A", str(nguon))
    if kho_cu == "chi_ban_ghi_0_hash":
        ghi_ht(e.db_file, [(str(nguon / "clip_2.opus"), 0)])
    else:
        Path(e.db_file).write_bytes(b"kho bi khoa hay hong")     # có thể là kho đầy đủ đọc lỗi tạm: không thay
    truoc = Path(e.db_file).read_bytes()
    e._run_stream = audfprint_gia(e, xong={0})

    r = e.build_database(str(nguon), mode="new")

    assert r["da_huy"] is True
    if luu:
        assert doc_ht(e.db_file) == {"clip_0.opus": 7} and r["da_ghi_kho"] is True
    else:
        assert Path(e.db_file).read_bytes() == truoc and not r.get("da_ghi_kho")


# ---------------------------------------------------------------------------
#  3) Lỗi giữa lúc lưu phần đã xong; clip làm mới chưa xong
# ---------------------------------------------------------------------------

def test_loi_khi_luu_phan_da_xong_giu_kho_cu_va_bao_ro(tmp_path, monkeypatch):
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 3)
    e.add_kho("A", str(nguon))
    (nguon / "cu.opus").write_bytes(b"audio")
    ghi_ht(e.db_file, [(str(nguon / "cu.opus"), 9)])
    truoc, rev = Path(e.db_file).read_bytes(), _so(e).get("revision")

    def dia_day(src, dst):
        raise OSError(28, "đĩa đầy (giả lập)")

    monkeypatch.setattr(channel, "_dat_vao_kho", dia_day)
    e._run_stream = audfprint_gia(e, xong={0, 1})

    with pytest.raises(RuntimeError) as loi:
        e.build_database(str(nguon), mode="add")

    assert Path(e.db_file).read_bytes() == truoc and _so(e).get("revision") == rev
    cau = str(loi.value)
    assert "Đã dừng" in cau and "2 clip" in cau and "vẫn nguyên" in cau and "đĩa đầy" in cau, cau


def test_clip_lam_moi_chay_truoc_va_chua_xong_luc_dung_thi_khong_luu_gi(tmp_path):
    """Vân tay cũ của clip làm mới đã gỡ khỏi kho tạm: lưu khi nó chưa xong là mất clip đó."""
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 3)
    e.add_kho("A", str(nguon))
    ghi_ht(e.db_file, [(str(nguon / "clip_2.opus"), 9)])
    sau = time.time() + 60
    os.utime(nguon / "clip_2.opus", (sau, sau))             # đồng bộ vừa thay file → làm mới vân tay
    truoc = Path(e.db_file).read_bytes()
    chay = audfprint_gia(e, xong={1, 2})                     # clip mới xong, clip làm mới đang làm dở
    e._run_stream = chay

    with pytest.raises(RuntimeError) as loi:
        e.build_database(str(nguon), mode="add")

    assert [os.path.basename(p) for p in chay.da_chay[0]] == ["clip_2.opus", "clip_0.opus", "clip_1.opus"], (
        "clip làm mới phải chạy trước: Dừng sau đó mới lưu được phần đã xong")
    assert Path(e.db_file).read_bytes() == truoc
    cau = str(loi.value)
    assert "Đã dừng" in cau and "vẫn nguyên" in cau and "thiếu 1 clip" in cau, cau


# ---------------------------------------------------------------------------
#  4) Đường thật: Engine → process_runner → tiến trình con; runner + worker thật
# ---------------------------------------------------------------------------

RUNNER_GIA = textwrap.dedent(
    """
    import json, os, sys, time
    {ma_ghi_kho}
    tham_so = sys.argv[1:]
    db = tham_so[tham_so.index("--dbase") + 1]
    ds = [p for p in open(tham_so[tham_so.index("--list") + 1], encoding="utf-8").read().splitlines() if p]
    co = os.path.join(os.path.dirname(db), {ten_co!r})


    def phat(su_kien, **kw):
        print({prefix!r} + json.dumps(dict(event=su_kien, **kw)), flush=True)


    for p in ds[:2]:
        phat("clip_started", file=p)
        phat("clip_finished", file=p, status="success")
    phat("clip_started", file=ds[2])
    het_han = time.monotonic() + 60
    while not os.path.exists(co) and time.monotonic() < het_han:
        time.sleep(0.05)
    _ghi_kho_hop_le(db, ds[:2] if os.path.exists(co) else ds)
    """
)


def test_runner_main_dat_file_co_canh_dbase(tmp_path):
    """Thiếu dòng này thì cờ Dừng không bao giờ tới worker: bấm Dừng mà build vẫn chạy hết."""
    gia = tmp_path / "gia"
    gia.mkdir()
    (gia / "audfprint.py").write_text(
        "import sys\ndo_cmd = None\n\n\ndef main(argv):\n"
        "    print('CO_DUNG ' + str(sys.modules['__main__']._CO_DUNG), flush=True)\n", encoding="utf-8")
    db = tmp_path / "job" / "database.pklz"

    kq = subprocess.run([sys.executable, "-u", str(GOC / "audfprint_progress_runner.py"), str(gia / "audfprint.py"),
                         "new", "--dbase", str(db)], capture_output=True, text=True, timeout=60)

    assert kq.returncode == 0, kq.stdout[-800:] + kq.stderr[-800:]
    assert f"CO_DUNG {db.parent / runner.TEN_CO_DUNG}" in kq.stdout, kq.stdout


def test_dung_qua_process_runner_that_nho_tien_trinh_con_tu_dung_khong_giet(tmp_path):
    e = _eng(tmp_path)
    nguon = _nguon(tmp_path, 4)
    e.add_kho("A", str(nguon))
    script = tmp_path / "runner_gia.py"
    script.write_text(RUNNER_GIA.format(ma_ghi_kho=ma_ghi_kho_cho_process_con(), ten_co=runner.TEN_CO_DUNG,
                                        prefix=PREFIX), encoding="utf-8")
    e._audfprint_build_cmd = lambda sub, *them, db_file: [sys.executable, "-u", str(script), sub,
                                                          "--dbase", db_file, *them]

    def bam_dung_khi_xong_hai(su_kien):
        if su_kien.success_count == 2 and not e.cancel_event.is_set():
            e.cancel()

    r = e.build_database(str(nguon), mode="new", progress_event=bam_dung_khi_xong_hai)

    assert doc_ht(e.db_file) == {"clip_0.opus": 5, "clip_1.opus": 5}
    assert (r["da_huy"], r["da_ghi_kho"], r["thanh_cong"]) == (True, True, 2)


KICH_BAN_RUNNER = textwrap.dedent(
    """
    import json, os, pathlib, sys, threading, time
    sys.path[:0] = [{repo!r}, {vendor!r}]
    import audfprint_progress_runner as runner
    import hash_table

    THU_MUC = pathlib.Path({thu_muc!r})


    def da_bat_dau(*ten):
        return all((THU_MUC / (t + ".bat_dau")).exists() for t in ten)


    _store_goc = hash_table.HashTable.store


    def _store_nua_chung(self, name, pairs):
        \"\"\"``nua_*``: store dừng 3 giây ở giữa (đã ghi tên + nửa số hash). Cấp module nên có cả trong worker (spawn).\"\"\"
        if not os.path.basename(str(name)).startswith("nua_"):
            return _store_goc(self, name, pairs)
        _store_goc(self, name, pairs[:5])
        (THU_MUC / (os.path.basename(name) + ".dang_store")).write_text("1")
        time.sleep(3)
        _store_goc(self, name, pairs[5:])


    hash_table.HashTable.store = _store_nua_chung


    class Analyzer:
        \"\"\"``cho_*`` tính rất lâu (đang làm dở lúc Dừng); ``doi_*`` xong khi ``cho_1`` đã chạy; còn lại xong ngay.
        Dấu bắt đầu ghi ra file vì worker là tiến trình khác.\"\"\"

        def wavfile2hashes(self, filename):
            ten = os.path.basename(filename)
            (THU_MUC / (ten + ".bat_dau")).write_text("1")
            if ten.startswith("cho_"):
                time.sleep(60)
            while ten.startswith("doi_") and not da_bat_dau("cho_1.opus"):
                time.sleep(0.02)
            return [(t % 16, t % 16) for t in range(10)]


    def bam_dung():
        \"\"\"Như Engine bấm Dừng: tạo file cờ khi đủ các file dấu đã định.\"\"\"
        while not all((THU_MUC / d).exists() for d in {cho!r}):
            time.sleep(0.05)
        time.sleep({tre})
        pathlib.Path(runner._CO_DUNG).write_text("")


    if __name__ == "__main__":
        runner._ram_trong_gb = {ram}
        runner._du_phong_ram_gb = lambda: 2.0
        runner._CO_DUNG = str(THU_MUC / runner.TEN_CO_DUNG)
        threading.Thread(target=bam_dung, daemon=True).start()
        ht = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
        bat_dau = time.monotonic()
        runner.instrumented_multiproc_add(Analyzer(), ht, sys.argv[1:], lambda m: None, 2)
        print("KET_QUA " + json.dumps({{"names": ht.names, "giay": time.monotonic() - bat_dau}}), flush=True)
    """
)


@pytest.mark.parametrize("ten_file, cho, tre, ram, mong_doi, chua_phat", [
    # Cả hai worker đang tính clip dài lúc Dừng; clip còn trong hàng không được phát nữa.
    (["xong_1.opus", "xong_2.opus", "cho_1.opus", "cho_2.opus", "xong_3.opus"],
     ("cho_1.opus.bat_dau", "cho_2.opus.bat_dau"), 0, "lambda: 20.0", ["xong_1.opus", "xong_2.opus"], "xong_3.opus"),
    # Một worker RẢNH chờ lệnh (RAM chưa đủ cho clip kế) lúc Dừng: luồng phụ gửi trong lúc luồng chính đang recv. RAM
    # trống lại ngay sau cờ: cha vẫn không được phát clip nào nữa.
    (["doi_xong.opus", "cho_1.opus", "xong_2.opus"], ("doi_xong.opus.bat_dau", "cho_1.opus.bat_dau"), 1.0,
     "lambda: 0.5 if da_bat_dau('cho_1.opus') and not os.path.exists(runner._CO_DUNG) else 20.0", ["doi_xong.opus"],
     "xong_2.opus"),
    # Một worker đã NGHỈ và thoát (hết hàng) trước lúc Dừng: tín hiệu Dừng không được chờ nó (multiprocessing.Event treo).
    (["xong_1.opus", "cho_1.opus"], ("xong_1.opus.bat_dau", "cho_1.opus.bat_dau"), 1.0, "lambda: 20.0", ["xong_1.opus"],
     ""),
    # Bấm Dừng đúng lúc worker đang store dở một clip: bảng chỉ được ghi sau khi store + báo xong (cùng một khoá).
    (["nua_store.opus"], ("nua_store.opus.dang_store",), 0, "lambda: 20.0", ["nua_store.opus"], ""),
])
def test_runner_that_dung_giua_chung_chi_ghi_clip_da_xong_khong_cho_clip_dang_tinh(
        tmp_path, ten_file, cho, tre, ram, mong_doi, chua_phat):
    files = [str(tmp_path / t) for t in ten_file]
    script = tmp_path / "kich_ban.py"
    script.write_text(KICH_BAN_RUNNER.format(repo=str(GOC), vendor=str(VENDOR), thu_muc=str(tmp_path), cho=cho,
                                             tre=tre, ram=ram), encoding="utf-8")

    kq = subprocess.run([sys.executable, "-u", str(script), *files], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=120, env={**os.environ, "PYTHONUTF8": "1"})

    assert kq.returncode == 0, kq.stdout[-800:] + kq.stderr[-800:]
    dong = kq.stdout.splitlines()
    su_kien = [json.loads(d[len(PREFIX):]) for d in dong if d.startswith(PREFIX)]
    ket_qua = next(json.loads(d[8:]) for d in dong if d.startswith("KET_QUA "))
    trong_bang = sorted(os.path.basename(n) for n in ket_qua["names"])
    xong = sorted(os.path.basename(s["file"]) for s in su_kien if s["event"] == "clip_finished")
    assert trong_bang == xong, "clip trong bảng phải đúng là các clip đã báo xong"
    assert trong_bang == mong_doi, "clip đang tính dở không được lưu"
    assert not chua_phat or not (tmp_path / (chua_phat + ".bat_dau")).exists(), "đã Dừng thì không phát clip mới"
    assert ket_qua["giay"] < 40, "không được chờ clip đang tính (60 giây) xong mới dừng"


# ---------------------------------------------------------------------------
#  5) Câu tiêu đề trên giao diện
# ---------------------------------------------------------------------------

def test_tieu_de_dung_da_luu_kho_noi_so_clip_da_luu():
    r = {"so_clip": 5, "da_xu_ly": 2, "thanh_cong": 2, "bo_qua": 0, "that_bai": 0, "da_huy": True,
         "da_ghi_kho": True, "giay": 12.0, "canh_bao": [], "loi_file": []}
    muc, cau = tom_tat_tao_van_tay(r)[0]
    assert muc == "warning" and "đã lưu 2 clip" in cau and "2/5" in cau, cau
