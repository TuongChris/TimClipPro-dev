# -*- coding: utf-8 -*-
"""Tiếng báo khi việc dài kết thúc + giữ máy không ngủ trong lúc chạy (``bao_viec``, việc nhỏ #12/#13).

Lô quét / dựng kho / tác vụ nền chạy hàng giờ, người dùng làm việc ở ứng dụng khác: luồng NỀN của việc phát tiếng lúc
kết thúc (xong ≠ lỗi / bị YouTube chặn; bấm Dừng thì im) và giữ máy thức bằng ``SetThreadExecutionState`` — đặt và trả
trên CHÍNH luồng đó (yêu cầu của API gắn với luồng gọi).

Synthetic: phát tiếng / ``SetThreadExecutionState`` thay bằng bản ghi; engine giả hoặc Engine trên thư mục tạm; không
mạng, không âm thanh thật.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
import types
from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import bao_viec
import common_original as co
import common_original_jobs
import tac_vu_nen
from common_original_jobs import CommonOriginalJobController
from fingerprint_progress import FingerprintJobController, progress_ban_dau
from scan_jobs import ScanJobController

GIU = bao_viec.ES_CONTINUOUS | bao_viec.ES_SYSTEM_REQUIRED
APP_PY = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture()
def ghi(monkeypatch):
    """Ghi mọi lần đặt trạng thái luồng + phát tiếng, kèm luồng gọi."""
    so = types.SimpleNamespace(co=[], tieng=[], da_keu=threading.Event())
    monkeypatch.setattr(bao_viec, "_dat_trang_thai_luong", lambda c: so.co.append((threading.get_ident(), c)))

    def phat(kieu):
        so.tieng.append((threading.get_ident(), kieu))
        so.da_keu.set()

    monkeypatch.setattr(bao_viec, "phat_tieng", phat)
    monkeypatch.setattr(bao_viec, "bat_tieng", True)
    return so


def test_ket_thuc_tra_yeu_cau_giu_may_roi_keu_o_luong_rieng(ghi):
    bao_viec.bat_dau()
    bao_viec.ket_thuc(bao_viec.XONG)
    assert ghi.da_keu.wait(5)
    toi = threading.get_ident()
    assert ghi.co == [(toi, GIU), (toi, bao_viec.ES_CONTINUOUS)]
    assert [k for _, k in ghi.tieng] == [bao_viec.XONG]
    assert ghi.tieng[0][0] != toi, "phát tiếng không được giữ luồng của việc"


@pytest.mark.parametrize("kieu, bat", [(None, True), (bao_viec.LOI, False)])
def test_bam_dung_hoac_tat_o_tieng_thi_khong_keu(ghi, monkeypatch, kieu, bat):
    monkeypatch.setattr(bao_viec, "bat_tieng", bat)
    bao_viec.ket_thuc(kieu)
    time.sleep(0.2)
    assert ghi.tieng == []
    assert ghi.co == [(threading.get_ident(), bao_viec.ES_CONTINUOUS)], "vẫn phải trả yêu cầu giữ máy"


@pytest.mark.parametrize("loi, phien, ket_qua, kieu", [
    ("", None, [{"trang_thai": "xong"}], bao_viec.XONG),
    ("", types.SimpleNamespace(mo=False), {"trang_thai": "MOT_PHAN", "chan_youtube": ""}, bao_viec.XONG),
    ("Ổ đĩa chứa «D:\\kho» đã hết chỗ trống", None, [], bao_viec.LOI),
    ("", types.SimpleNamespace(mo=True), [], bao_viec.LOI),
    ("", None, {"trang_thai": "BI_CHAN", "chan_youtube": "YouTube nghi là bot"}, bao_viec.LOI),
])
def test_kieu_ket_thuc(loi, phien, ket_qua, kieu):
    assert bao_viec.kieu_ket_thuc(loi, phien, ket_qua) == kieu


def test_xong_va_loi_la_hai_kieu_tieng_khac_nhau_may_khong_phat_duoc_thi_im(monkeypatch, bao_viec_that):
    PHAT_THAT = bao_viec_that[0]
    nghe = []
    monkeypatch.setattr(bao_viec, "winsound", types.SimpleNamespace(Beep=lambda f, ms: nghe.append(f)))
    PHAT_THAT(bao_viec.XONG)
    xong, nghe[:] = list(nghe), []
    PHAT_THAT(bao_viec.LOI)
    assert xong and nghe and xong != nghe
    assert xong[0] < xong[-1] and nghe[0] > nghe[-1], "xong: nốt đi lên; lỗi: nốt đi xuống"

    def hong(f, ms):
        raise RuntimeError("Failed to beep")

    monkeypatch.setattr(bao_viec, "winsound", types.SimpleNamespace(Beep=hong))
    PHAT_THAT(bao_viec.LOI)                     # máy không có thiết bị âm thanh: không ném lỗi
    monkeypatch.setattr(bao_viec, "winsound", None)
    PHAT_THAT(bao_viec.XONG)                    # không phải Windows: im lặng


# ---------------------------------------------------------------- mọi chỗ việc dài kết thúc

@pytest.fixture()
def viec(monkeypatch):
    """``bat_dau`` / ``ket_thuc`` của bao_viec thay bằng bản ghi (luồng gọi + kiểu)."""
    so = types.SimpleNamespace(goi=[], xong=threading.Event())
    monkeypatch.setattr(bao_viec, "bat_dau", lambda: so.goi.append(("bat_dau", threading.get_ident())))

    def ket_thuc(kieu):
        so.goi.append(("ket_thuc", threading.get_ident(), kieu))
        so.xong.set()

    monkeypatch.setattr(bao_viec, "ket_thuc", ket_thuc)
    return so


def _kiem(so, kieu):
    assert so.xong.wait(15), "việc kết thúc mà không gọi bao_viec.ket_thuc"
    assert [g[0] for g in so.goi] == ["bat_dau", "ket_thuc"], so.goi
    assert so.goi[1][2] == kieu
    assert so.goi[0][1] == so.goi[1][1] != threading.get_ident(), \
        "giữ máy phải đặt và trả trên CHÍNH luồng nền của việc (yêu cầu gắn với luồng gọi)"


@pytest.fixture()
def so_tac_vu():
    yield
    with tac_vu_nen.SO_TAC_VU_NEN._khoa:
        tac_vu_nen.SO_TAC_VU_NEN._dang_chay.clear()
        tac_vu_nen.SO_TAC_VU_NEN._vua_xong.clear()


@pytest.mark.parametrize("cach, kieu", [
    ("xong", bao_viec.XONG), ("loi", bao_viec.LOI), ("cau_dao", bao_viec.LOI), ("chan_youtube", bao_viec.LOI),
    ("dung", None),
])
def test_tac_vu_nen_tai_cat_ghep_dong_bo(tmp_path, so_tac_vu, viec, cach, kieu):
    eng = types.SimpleNamespace(data_dir=str(tmp_path / "data"))
    co_huy = threading.Event()

    def ham(progress):
        if cach == "loi":
            raise OSError(28, "No space left on device")
        if cach == "dung":
            co_huy.wait(10)
        if cach == "chan_youtube":
            return {"trang_thai": "BI_CHAN", "chan_youtube": "YouTube nghi là bot"}
        return [{"trang_thai": "xong"}]

    tv = tac_vu_nen.TacVuNen("tai_video", huy=co_huy.set,
                             phien_youtube=types.SimpleNamespace(mo=cach == "cau_dao"))
    tv.bat_dau(eng, ham, (), {}, job={}, lease=None)
    if cach == "dung":
        tv.huy()
    _kiem(viec, kieu)


@pytest.mark.parametrize("cach, kieu", [
    ("xong", bao_viec.XONG), ("loi", bao_viec.LOI), ("cau_dao", bao_viec.LOI), ("dung", None),
])
def test_lo_quet(engine, monkeypatch, viec, cach, kieu):
    def scan_iter(nguon, source_type, progress, on_video=None, **_k):
        if cach == "loi":
            raise RuntimeError("Lô hỏng giữa chừng")
        if cach == "cau_dao":
            engine.phien_youtube_cuoi = types.SimpleNamespace(mo=True, thong_bao_dung=lambda: "YouTube chặn")
        if cach == "dung":
            engine.cancel_event.wait(10)
        return iter(())

    monkeypatch.setattr(engine, "scan_iter", scan_iter)
    ctl = ScanJobController(engine)
    ctl.start(["https://youtu.be/aaaaaaaaaaa"], "youtube")
    if cach == "dung":
        ctl.cancel()
    _kiem(viec, kieu)


@pytest.mark.parametrize("cach, kieu", [("xong", bao_viec.XONG), ("loi", bao_viec.LOI), ("dung", None)])
def test_dung_kho_van_tay(tmp_path, viec, cach, kieu):
    class EngineGia:
        data_dir = str(tmp_path / "data")

        def build_database(self, folder, mode, progress_event, job_id):
            if cach == "loi":
                raise RuntimeError("audfprint hỏng")
            if cach == "dung":
                progress_event(replace(progress_ban_dau(job_id), phase="cancelled", status="cancelled"))
            return {"thanh_cong": 1, "da_ghi_kho": True}

        def cancel(self):
            pass

    FingerprintJobController(EngineGia()).start(str(tmp_path / "kho"), "new")
    _kiem(viec, kieu)


@pytest.mark.parametrize("cach, kieu", [
    ("xong", bao_viec.XONG), ("loi", bao_viec.LOI), ("cau_dao", bao_viec.LOI), ("dung", None),
])
def test_lo_mot_video_goc_chung(tmp_path, monkeypatch, viec, cach, kieu):
    eng = types.SimpleNamespace(data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ketqua"),
                                cancel_event=threading.Event(), phien_job=contextlib.nullcontext)
    eng.cancel = eng.cancel_event.set
    os.makedirs(eng.data_dir)
    ctl = CommonOriginalJobController(eng)
    monkeypatch.setattr(common_original_jobs, "xuat_csv", lambda ket, thu_muc: "")

    def chay_da_khoa(job, ma_lo, nguon, source_type):
        if cach == "loi":
            raise RuntimeError("Lô hỏng giữa chừng")
        if cach == "cau_dao":
            ctl._phien = types.SimpleNamespace(mo=True)
        if cach == "dung":
            ctl.cancel()
        return co.KetQuaLo(ma_lo=ma_lo, trang_thai=co.DA_HUY if cach == "dung" else co.TIM_THAY, ly_do="",
                           kho_id="k", kho_ten="Kho", goc=None, la_nguon_chung=False, so_co_mat=0, tong=2)

    monkeypatch.setattr(ctl, "_chay_da_khoa", chay_da_khoa)
    ctl.start(["https://youtu.be/aaaaaaaaaaa", "https://youtu.be/bbbbbbbbbbb"])
    _kiem(viec, kieu)


# ---------------------------------------------------------------- ô ở thanh bên

def test_o_tieng_thanh_ben_mac_dinh_bat_tat_ngay_va_luu_vao_cau_hinh(tmp_path, monkeypatch):
    monkeypatch.delenv("TIMCLIP_UI_VE_MOI_TRANG", raising=False)   # chỉ trang mặc định: thanh bên vẫn vẽ đủ
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.setattr(bao_viec, "bat_tieng", True)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.toggle(key="bao_tieng_xong").value is True and bao_viec.bat_tieng is True

    at.toggle(key="bao_tieng_xong").set_value(False).run()
    assert bao_viec.bat_tieng is False, "tắt là có hiệu lực ngay cho việc đang chạy"
    next(b for b in at.button if b.label == "💾 Lưu cấu hình").click().run()
    assert not at.exception, [e.value for e in at.exception]
    luu = json.loads((tmp_path / "data" / "cau_hinh.json").read_text(encoding="utf-8"))
    assert luu["bao_tieng_xong"] is False
