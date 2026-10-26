# -*- coding: utf-8 -*-
"""Audit F-6: thanh tiến độ «Một video gốc chung» báo 100% / «Đã quét N/N video» khi lượt
quét BỔ SUNG vẫn đang chạy.

Thế giới tổng hợp (engine GIẢ, không mạng, không audio):
* video 1 (ngắn nhất → mốc): A ở 50%, B ở 10% → ứng viên nhanh = A (hoà điểm, xếp theo tên);
* video 2: A ở 20%, B ở 80% → xác minh A thấy ở 20% và DỪNG SỚM (B chưa rõ);
* video 3: B ở 30%, C ở 10%, KHÔNG có A → quét trọn, A bị loại, tập khả dĩ = {B};
* lượt 4 = «Quét bổ sung để kết luận» trên video 2 tìm B.

Trong suốt lượt 4 lô CHƯA xong (đang tải + so khớp lại video 2), nên thanh tiến độ phải
< 100%. Mã ở 6ee8f43 đếm «video có so_luot > 0» = 3/3 → thanh 100%.
"""

from __future__ import annotations

import threading
import time

import pytest

import common_original as co
from common_original_jobs import (CommonOriginalJobController, NguonChungSnapshot,
                                  VideoNguonChung)
from scan_ui import tien_do_nguon_chung
from test_nguon_chung_jobs import EngineGia
from test_nguon_chung_ui import A, B, _app, _van_ban

C = "C [ccccccccccc].opus"


def _gia_chan_luot_thu(gia, thu: int):
    """Chặn đúng lượt quét thứ ``thu`` (đếm từ 1) cho tới khi ``mo`` được set."""
    goc = gia.job._quet
    dem = {"n": 0}
    dang = threading.Event()
    mo = threading.Event()

    def _quet(ma, muc_tieu, progress, nguon):
        dem["n"] += 1
        if dem["n"] == thu:
            dang.set()
            mo.wait(10)
        return goc(ma, muc_tieu, progress, nguon)

    gia.job._quet = _quet
    return dang, mo


def _thanh_tien_do(at):
    ds = at.get("progress")
    assert ds, "màn hình đang chạy phải có thanh tiến độ"
    p = ds[0].proto
    return float(p.value), str(p.text)


def test_thanh_tien_do_chua_100_khi_luot_bo_sung_dang_chay(tmp_path, monkeypatch):
    import streamlit

    at = _app(tmp_path, monkeypatch)
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)
    tg = {"v1aaaaaaaaa": {"dai": 1000, "clips": {A: 0.5, B: 0.1}},
          "v2aaaaaaaaa": {"dai": 2000, "clips": {A: 0.2, B: 0.8}},
          "v3aaaaaaaaa": {"dai": 3000, "clips": {B: 0.3, C: 0.1}}}
    gia = EngineGia(tmp_path / "gia", tg)
    dang, mo = _gia_chan_luot_thu(gia, 4)
    ctl = CommonOriginalJobController(gia)
    at.session_state.common_controller = ctl
    ctl.start([f"https://youtu.be/{v}" for v in tg])
    try:
        assert dang.wait(10), "lượt quét thứ 4 (bổ sung) phải xảy ra"
        # Worker đã gọi _sua(pha, video_dang_quet...) TRƯỚC khi vào engine giả.
        anh = ctl.snapshot()
        # --- Tiền đề: đúng kịch bản của F-6, không phải lỗi dựng test ---
        assert anh.running and not ctl.result
        assert anh.pha == co.PHA_BO_SUNG, anh.pha
        assert anh.video_dang_quet == 2, anh.video_dang_quet
        assert [v.so_luot for v in anh.videos] == [1, 1, 1]
        # Ba lượt đã xong (lượt 4 đang bị chặn TRƯỚC khi engine giả ghi nhật ký).
        assert [x[1:] for x in gia.nhat_ky if x[0] == "quet"] == [
            ("v1aaaaaaaaa", "collect"), ("v2aaaaaaaaa", "verify"),
            ("v3aaaaaaaaa", "verify")]

        at.session_state.job.update({"running": True, "kind": "nguon_chung",
                                     "results": [], "error": ""})
        at.run()
        assert not at.exception
        assert "Quét bổ sung để kết luận" in _van_ban(at)
        gia_tri, chu = _thanh_tien_do(at)
        # --- Hành vi ĐÚNG: lô còn đang quét thì thanh chưa được 100% ---
        assert gia_tri < 100, (
            f"thanh tiến độ = {gia_tri:.0f}% («{chu}») trong khi lượt bổ sung trên video 2 "
            "vẫn đang chạy")
    finally:
        mo.set()
        han = time.monotonic() + 15
        while ctl.running and time.monotonic() < han:
            time.sleep(0.02)
    assert ctl.result is not None and ctl.result.trang_thai == co.TIM_THAY
    assert ctl.result.goc.clip == B


# --- Hàm thuần của thanh tiến độ (scan_ui.tien_do_nguon_chung) ---


def _anh(so_luot, dang=None, tien_do=0.0, running=True):
    videos = tuple(VideoNguonChung(thu_tu=i + 1, nguon=f"v{i + 1}", so_luot=n,
                                   dang_quet=(dang == i)) for i, n in enumerate(so_luot))
    return NguonChungSnapshot(running=running, tien_do=tien_do, tong=len(videos),
                              videos=videos)


def test_luot_dau_giu_nguyen_cong_thuc_video():
    # Không có lượt bổ sung: giống hệt (video đã quét + tiến độ) / tổng như trước.
    gia_tri, chu = tien_do_nguon_chung(_anh([1, 0, 0], dang=1, tien_do=0.5))
    assert gia_tri == pytest.approx(1.5 / 3)
    assert chu == "Đã quét 1/3 video"


def test_luot_bo_sung_tinh_vao_mau_so():
    gia_tri, chu = tien_do_nguon_chung(_anh([1, 1, 1], dang=1, tien_do=0.5))
    assert gia_tri == pytest.approx(3.5 / 4)
    assert "Đã quét 3/3 video" in chu and "video 2" in chu and "lượt 4" in chu


def test_dang_chay_khong_bao_gio_100():
    # Giữa hai lượt (chưa lên lịch lượt kế) hay cuối lượt bổ sung: lô còn chạy → < 100%.
    assert tien_do_nguon_chung(_anh([1, 1, 1]))[0] < 1.0
    assert tien_do_nguon_chung(_anh([2, 1, 1], dang=0, tien_do=1.0))[0] < 1.0
    assert tien_do_nguon_chung(_anh([1, 1, 1], running=False))[0] == 1.0


def test_chua_co_video():
    assert tien_do_nguon_chung(NguonChungSnapshot()) == (0.0, "Đang chuẩn bị...")
