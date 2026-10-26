# -*- coding: utf-8 -*-
"""Audit P3 F-14: hai phiên (hai tab / tải lại trang) bấm «Bắt đầu quét» cùng lúc trên CÙNG thư mục
dữ liệu thì chỉ được MỘT lô chạy.

Kịch bản tổng hợp (không mạng, thư mục tạm): hai Engine (hai phiên Streamlit trong cùng tiến trình)
trên một data_dir, mỗi phiên có ScanJobController riêng (mỗi cái một ``_lock`` riêng). Cả hai bấm
Start gần như cùng lúc: cả hai đều qua bước ``dang_chay_cua()`` trước khi phiên kia kịp ghi sổ
``_DANG_CHAY``. Barrier đặt trong ``maintenance_gate.nhan_viec_cua`` (bước I/O lease nằm đúng giữa
kiểm và ghi sổ) chỉ để ép thứ tự xen kẽ đó cho tất định — không đổi logic.

Hành vi ĐÚNG được khẳng định (chú thích ``scan_jobs.py`` ~138-141: sổ chung tồn tại để không có
«hai lô chạy song song trên cùng kho»): đúng MỘT lời gọi ``start`` thành công, lời gọi kia ném
``RuntimeError`` «Đang có lô quét chạy ở một cửa sổ/phiên khác…».
"""

from __future__ import annotations

import threading
import time

import maintenance_gate
from engine import Engine, ScanResult
import scan_jobs
from scan_jobs import ScanJobController


def test_hai_phien_bam_bat_dau_cung_luc_chi_mot_lo_chay(tmp_path, monkeypatch):
    def tao_engine():
        return Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))

    eng1, eng2 = tao_engine(), tao_engine()

    goc = maintenance_gate.nhan_viec_cua
    hang_rao = threading.Barrier(2, timeout=5)

    def nhan_viec_cho_nhau(engine, ten):
        lease = goc(engine, ten)
        try:
            hang_rao.wait()          # cả hai phiên đã qua bước kiểm «đang chạy?»
        except threading.BrokenBarrierError:
            pass                     # phiên kia bị chặn đúng: không đợi nữa
        return lease

    monkeypatch.setattr(maintenance_gate, "nhan_viec_cua", nhan_viec_cho_nhau)

    di_tiep = threading.Event()
    da_quet: list = []

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        da_quet.append(url)
        di_tiep.wait(10)
        r = ScanResult(source_name=url, source_ref=url)
        r.source_id = url
        return r

    monkeypatch.setattr(Engine, "scan_youtube", scan_youtube)

    ctl1, ctl2 = ScanJobController(eng1), ScanJobController(eng2)
    ket_qua: dict = {}

    def bam(ten, ctl, url):
        try:
            ctl.start([url], "youtube")
            ket_qua[ten] = "chay"
        except RuntimeError as exc:
            ket_qua[ten] = f"tu_choi: {exc}"
            hang_rao.abort()

    luong = [threading.Thread(target=bam, args=("tab1", ctl1, "u1")),
             threading.Thread(target=bam, args=("tab2", ctl2, "u2"))]
    for t in luong:
        t.start()
    for t in luong:
        t.join(15)
    time.sleep(0.2)
    so_lo_chay = sum(1 for v in ket_qua.values() if v == "chay")
    try:
        assert so_lo_chay == 1, (
            f"Hai lô quét cùng chạy trên một kho: {ket_qua}; video đang quét song song: {da_quet}")
    finally:
        di_tiep.set()
        for ctl in (ctl1, ctl2):
            het = time.monotonic() + 10
            while ctl.running and time.monotonic() < het:
                time.sleep(0.02)


def test_bat_dau_hong_tra_cho_cho_phien_khac(tmp_path, monkeypatch):
    """Giữ chỗ trong sổ chung rồi không bắt đầu được (đang bảo trì) → trả chỗ: phiên khác bấm sau vẫn chạy được."""
    def tao_engine():
        return Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))

    goc = maintenance_gate.nhan_viec_cua
    lan = {"n": 0}

    def nhan_viec_lan_dau_bao_tri(engine, ten):
        lan["n"] += 1
        if lan["n"] == 1:
            raise maintenance_gate.DangBaoTri("đang cập nhật (giả)")
        return goc(engine, ten)

    monkeypatch.setattr(maintenance_gate, "nhan_viec_cua", nhan_viec_lan_dau_bao_tri)

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        r = ScanResult(source_name=url, source_ref=url)
        r.source_id = url
        return r

    monkeypatch.setattr(Engine, "scan_youtube", scan_youtube)

    ctl1, ctl2 = ScanJobController(tao_engine()), ScanJobController(tao_engine())
    try:
        ctl1.start(["u1"], "youtube")
        raise AssertionError("phải ném DangBaoTri")
    except maintenance_gate.DangBaoTri:
        pass
    assert scan_jobs._khoa_lo(ctl1.engine) not in scan_jobs._DANG_CHAY
    assert not ctl1._giu_cho
    ctl2.start(["u2"], "youtube")
    het = time.monotonic() + 10
    while ctl2.running and time.monotonic() < het:
        time.sleep(0.02)
    assert not ctl2.running
