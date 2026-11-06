# -*- coding: utf-8 -*-
"""Clip dài hơn ``channel.GIAY_CLIP_TOI_DA`` (2 giờ, D-31): không tải khi đồng bộ, không tạo vân tay.

Người dùng chốt 06/11/2026. Clip dài không phải lỗi: không đếm vào lỗi, không làm trạng thái thành «một phần», không
vào sổ đã tải (nới ngưỡng sau này thì tải được), và không bao giờ làm mất vân tay hay file đang có.
Không mạng: danh sách kênh, bước tải và ffprobe được thay bằng bản giả.
"""
from __future__ import annotations

import gzip
import json
import os
import pickle
import sys
from pathlib import Path

import channel
from channel import DONG_BO_DAY_DU, ChannelSync, VideoInfo
from engine import Engine
from scan_ui import tom_tat_dong_bo_kenh

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audfprint-master"))
import hash_table  # noqa: E402

GIO = 3600.0


def _video(vid: str, giay: float) -> VideoInfo:
    return VideoInfo(vid, f"Video {vid}", "20260101", giay, f"https://youtu.be/{vid}")


def _kenh(tmp_path, *ds) -> ChannelSync:
    cs = ChannelSync(str(tmp_path / "kho"))
    cs.list_channel = lambda *a, **k: list(ds)
    return cs


def test_dong_bo_khong_tai_video_dai_hon_nguong(tmp_path):
    cs = _kenh(tmp_path, _video("ngan0000000", 600), _video("dungnguong0", 2 * GIO), _video("dai00000000", 2 * GIO + 1),
               _video("khongro0000", 0))
    da_thu = []

    def tai_gia(v):
        da_thu.append(v.id)
        raise RuntimeError("synthetic: không tải thật")

    cs._tai_va_nen = tai_gia
    kq = cs.sync("kenh")

    assert da_thu == ["ngan0000000", "dungnguong0", "khongro0000"], "đúng 2 giờ vẫn tải; chưa rõ thời lượng thì tải"
    assert kq["qua_dai"] == 1
    assert kq["can_tai"] == 3


def test_kenh_chi_con_video_dai_van_bao_dong_bo_xong_va_khong_ghi_so(tmp_path):
    cs = _kenh(tmp_path, _video("dai00000000", 3 * GIO))
    cs._tai_va_nen = lambda v: (_ for _ in ()).throw(AssertionError("không được tải video quá dài"))
    kq = cs.sync("kenh")

    assert (kq["trang_thai"], kq["so_loi"], kq["chua_thu"], kq["bo_qua"]) == (DONG_BO_DAY_DU, 0, 0, 0)
    assert "dai00000000" not in cs.done_ids(), "không vào sổ đã tải: nới ngưỡng sau này còn tải được"
    dong = tom_tat_dong_bo_kenh(kq)
    assert dong[0][0] == "success"
    assert any("1 video dài hơn 2 giờ" in cau for _, cau in dong), dong


def test_kiem_tra_con_thieu_khong_hua_tai_video_dai(tmp_path):
    cs = _kenh(tmp_path, _video("ngan0000000", 600), _video("dai00000000", 3 * GIO))
    kq = cs.kiem_tra_thieu("kenh")
    assert [v.id for v in kq["thieu"]] == ["ngan0000000"]
    assert [v.id for v in kq["qua_dai"]] == ["dai00000000"]
    assert kq["co_roi"] == 0, "video dài chưa tải không được tính là đã có"


# ---------------------------------------------------------------------------
#  Tạo vân tay
# ---------------------------------------------------------------------------

def _file(path: Path, byte: int = 20 * 10**6) -> str:
    with open(path, "wb") as f:
        f.truncate(byte)                 # file thưa: không tốn đĩa thật
    return str(path)


def _do_dai_gia(monkeypatch, gio_theo_ten: dict) -> list:
    da_do = []

    def do(path):
        da_do.append(os.path.basename(path))
        return gio_theo_ten.get(os.path.basename(path), 0.5) * GIO

    monkeypatch.setattr(channel, "do_dai_media", do)
    return da_do


def _cap(n: int) -> list:
    return [(t % 16, t % 16) for t in range(n)]


def _ghi_bang(path: str, ten_clip: list) -> None:
    ht = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
    for ten in ten_clip:
        ht.store(ten, _cap(5))
    with gzip.open(path, "wb") as f:
        pickle.dump(ht, f)


def _engine(tmp_path) -> Engine:
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e._cap_nhat_snapshot_sau_build = lambda *a: []
    e._day_kho_tam_xuong_dia = lambda *a: None
    e.config.ncores = 2
    e.audfprint = str(Path(__file__).resolve().parents[1] / "audfprint-master" / "audfprint.py")
    return e


def _gia_audfprint(da_chay: list):
    """Giả bước audfprint: ghi lại danh sách clip được đưa vào, thêm chúng vào bảng tạm."""
    def chay(lenh, on_line=None, **kw):
        ds = [p for p in Path(lenh[lenh.index("--list") + 1]).read_text(encoding="utf-8").splitlines() if p]
        da_chay.append(ds)
        db = lenh[lenh.index("--dbase") + 1]
        if os.path.exists(db):
            with gzip.open(db, "rb") as f:
                ht = pickle.load(f)
        else:
            ht = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
        for p in ds:
            ht.store(p, _cap(5))
            on_line("TIMCLIP_FINGERPRINT_EVENT "
                    + json.dumps({"event": "clip_finished", "file": p, "status": "success"}))
        with gzip.open(db, "wb") as f:
            pickle.dump(ht, f)
        return 0, []
    return chay


def _nguon(tmp_path, *ten) -> Path:
    nguon = tmp_path / "nguon"
    nguon.mkdir()
    for t in ten:
        _file(nguon / t)
    return nguon


def test_tao_van_tay_bo_clip_dai_khong_tinh_la_loi_va_giu_file(tmp_path, monkeypatch):
    nguon = _nguon(tmp_path, "ngan.opus", "dai.opus")
    _do_dai_gia(monkeypatch, {"dai.opus": 3})
    e = _engine(tmp_path)
    e.add_kho("A", str(nguon))
    da_chay: list = []
    e._run_stream = _gia_audfprint(da_chay)

    kq = e.build_database(str(nguon), "new")

    assert da_chay == [[str(nguon / "ngan.opus")]]
    assert (kq["so_clip"], kq["that_bai"]) == (1, 0)
    assert any("dai.opus" in c and "2 giờ" in c for c in kq["canh_bao"]), kq["canh_bao"]
    assert (nguon / "dai.opus").exists()


def test_clip_nho_khong_ton_ffprobe(tmp_path, monkeypatch):
    nguon = tmp_path / "nguon"
    nguon.mkdir()
    _file(nguon / "nho.opus", 10**6)
    _file(nguon / "lon.opus")
    da_do = _do_dai_gia(monkeypatch, {})
    e = _engine(tmp_path)
    e.add_kho("A", str(nguon))
    e._run_stream = _gia_audfprint([])
    e.build_database(str(nguon), "new")
    assert da_do == ["lon.opus"]


def test_bo_sung_giu_nguyen_clip_dai_da_co_van_tay_va_khong_do_lai(tmp_path, monkeypatch):
    nguon = _nguon(tmp_path, "dai_cu.opus", "moi.opus")
    da_do = _do_dai_gia(monkeypatch, {"dai_cu.opus": 5})
    e = _engine(tmp_path)
    e.add_kho("A", str(nguon))
    _ghi_bang(e.db_file, [str(nguon / "dai_cu.opus")])
    moc = os.path.getmtime(e.db_file) - 100
    os.utime(e.db_file, (moc + 50, moc + 50))
    os.utime(nguon / "dai_cu.opus", (moc, moc))
    da_chay: list = []
    e._run_stream = _gia_audfprint(da_chay)

    kq = e.build_database(str(nguon), "add")

    assert da_chay == [[str(nguon / "moi.opus")]]
    assert "dai_cu.opus" not in da_do
    assert kq.get("da_ghi_kho") is True, kq
    assert sorted(c["ten"] for c in e.db_clips(bo_cache=True)) == ["dai_cu.opus", "moi.opus"]


def test_clip_dang_lam_moi_khong_bi_bo_de_khong_mat_van_tay(tmp_path, monkeypatch):
    """File trong kho vừa được thay: bước làm mới gỡ vân tay cũ, bỏ qua nữa là mất luôn clip."""
    nguon = _nguon(tmp_path, "dai_cu.opus")
    _do_dai_gia(monkeypatch, {"dai_cu.opus": 5})
    e = _engine(tmp_path)
    e.add_kho("A", str(nguon))
    _ghi_bang(e.db_file, [str(nguon / "dai_cu.opus")])
    e._clip_doi_file_sau_cong_bo = lambda files, da_co: set(da_co)
    e._go_van_tay_cu = lambda *a, **k: None
    da_chay: list = []
    e._run_stream = _gia_audfprint(da_chay)

    e.build_database(str(nguon), "add")

    assert da_chay == [[str(nguon / "dai_cu.opus")]]


def test_tao_lai_kho_co_clip_dai_cu_van_cong_bo_va_noi_ro(tmp_path, monkeypatch):
    """Không bị chốt «clip từng có vân tay mà lần này thất bại»: đây là quy tắc, không phải lỗi."""
    nguon = _nguon(tmp_path, "dai_cu.opus", "ngan.opus")
    _do_dai_gia(monkeypatch, {"dai_cu.opus": 5})
    e = _engine(tmp_path)
    e.add_kho("A", str(nguon))
    _ghi_bang(e.db_file, [str(nguon / "dai_cu.opus"), str(nguon / "ngan.opus")])
    e._run_stream = _gia_audfprint([])

    kq = e.build_database(str(nguon), "new")

    assert kq.get("da_ghi_kho") is True, kq
    assert [c["ten"] for c in e.db_clips(bo_cache=True)] == ["ngan.opus"]
    assert any("dai_cu.opus" in c for c in kq["canh_bao"]), kq["canh_bao"]


def test_kho_chi_co_clip_dai_ket_thuc_gon_khong_noi_sai(tmp_path, monkeypatch):
    nguon = _nguon(tmp_path, "dai.opus")
    _do_dai_gia(monkeypatch, {"dai.opus": 5})
    e = _engine(tmp_path)
    e.add_kho("A", str(nguon))
    da_chay: list = []
    e._run_stream = _gia_audfprint(da_chay)
    su_kien: list = []

    kq = e.build_database(str(nguon), "new", progress_event=su_kien.append)

    assert da_chay == []
    assert kq["da_ghi_kho"] is False
    assert any("dai.opus" in c for c in kq["canh_bao"])
    assert "đã có vân tay;" not in su_kien[-1].message


def test_ffprobe_khong_doc_duoc_thi_khong_bo_clip(tmp_path, monkeypatch):
    nguon = _nguon(tmp_path, "la.opus")
    monkeypatch.setattr(channel, "do_dai_media", lambda path: None)
    e = _engine(tmp_path)
    e.add_kho("A", str(nguon))
    da_chay: list = []
    e._run_stream = _gia_audfprint(da_chay)
    e.build_database(str(nguon), "new")
    assert da_chay == [[str(nguon / "la.opus")]]
