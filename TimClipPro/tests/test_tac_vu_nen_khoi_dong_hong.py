# -*- coding: utf-8 -*-
"""Audit DR-6: ``TacVuNen.bat_dau`` khi ``threading.Thread.start()`` ném lỗi («can't start new thread» — tiến
trình hết tài nguyên luồng; lỗi có ghi trong tài liệu của ``start()``).

``bat_dau`` ghi sổ tiến trình + ``running=True`` dưới khoá rồi mới ``start()``. Tác vụ chưa từng chạy thì không được
để lại dấu «đang chạy»: sổ trống (lần bấm sau khởi động được, không bị ``DangCoTacVuKhac`` tới khi tắt Tool), tác vụ
và ``job`` của phiên báo không chạy, lease cổng bảo trì đã trả (updater không chờ một việc ma), lỗi gốc vẫn bay ra.

Synthetic: thư mục tạm, Engine giả, không mạng, không thread thật nào của tác vụ chạy.
"""

from __future__ import annotations

import threading
import types

import pytest

import tac_vu_nen


class _LeaseGia:
    def __init__(self):
        self.da_tra = 0

    def tra(self):
        self.da_tra += 1


@pytest.fixture()
def so_sach():
    yield
    with tac_vu_nen.SO_TAC_VU_NEN._khoa:
        tac_vu_nen.SO_TAC_VU_NEN._dang_chay.clear()
        tac_vu_nen.SO_TAC_VU_NEN._vua_xong.clear()


def test_start_hong_khong_de_lai_tac_vu_ma(tmp_path, monkeypatch, so_sach):
    eng = types.SimpleNamespace(data_dir=str(tmp_path / "data"))
    lease = _LeaseGia()
    job = {"running": True}
    tv = tac_vu_nen.TacVuNen("dong_bo", huy=lambda: None)

    def start_hong(self):
        raise RuntimeError("can't start new thread")

    with monkeypatch.context() as m:
        m.setattr(threading.Thread, "start", start_hong)
        with pytest.raises(RuntimeError, match="can't start new thread"):
            tv.bat_dau(eng, lambda progress: [], (), {}, job=job, lease=lease)

    loi = []
    if tac_vu_nen.dang_chay_cua(eng) is not None:
        loi.append("sổ còn tác vụ «đang chạy» dù thread chưa từng khởi động")
    if tv.running:
        loi.append("tv.running vẫn True")
    if job.get("running"):
        loi.append("job của phiên vẫn running=True")
    if lease.da_tra != 1:
        loi.append(f"lease cổng bảo trì trả {lease.da_tra} lần (cần đúng 1)")
    if tac_vu_nen.nhan_vua_xong(eng) is not None:
        loi.append("tác vụ chưa chạy lại nằm trong ô «vừa xong»")

    # Lần bấm sau (tác vụ mới) phải khởi động được và chạy xong bình thường.
    xong = threading.Event()
    tv2 = tac_vu_nen.TacVuNen("dong_bo", huy=lambda: None)
    try:
        tv2.bat_dau(eng, lambda progress: (xong.set(), [])[1], (), {}, job={}, lease=None)
    except tac_vu_nen.DangCoTacVuKhac as e:
        loi.append(f"lần bấm sau bị chặn: {e}")
    else:
        assert xong.wait(10)
    assert not loi, "; ".join(loi)
