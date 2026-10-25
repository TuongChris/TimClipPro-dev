# -*- coding: utf-8 -*-
"""Tác vụ nền dài của giao diện (đồng bộ kênh, lấy lại tên video, vá metadata) ở mức TIẾN TRÌNH.

Mỗi phiên trình duyệt có ``job`` riêng trong ``st.session_state``; tải lại trang (F5, tab thứ hai, tab bị trình duyệt
dỡ) = phiên MỚI. Không có sổ chung thì lượt đồng bộ kênh nhiều giờ vẫn chạy nhưng phiên mới thấy «không có gì chạy»:
không tiến độ, không nút Dừng tới được lượt đó, kết quả cuối (trạng thái, video lỗi, file nghi hỏng, đăng nhập) rơi vào
``job`` của phiên đã chết (audit D-13). Lô quét đã có sổ tương tự (``scan_jobs._DANG_CHAY``).

Thread nền KHÔNG chạm Streamlit: nó chỉ ghi vào đối tượng ``TacVuNen`` (có khoá) và ``job`` của phiên đã bấm (như
trước); phiên khác NHẬN LẠI tác vụ thì chép ``anh()`` vào ``job`` của mình ở main thread. Nút Dừng của phiên nhận lại
gọi ``huy()`` = cờ huỷ của Engine đã khởi động tác vụ (cờ mà ``cancel_check`` của tác vụ đang đọc), không phải Engine
riêng của phiên mới.
"""

from __future__ import annotations

import os
import threading
import uuid
from typing import Callable, Optional

# Tác vụ nền ĐANG CHẠY của tiến trình, theo thư mục dữ liệu (một tác vụ mỗi thư mục, như lô quét).
_DANG_CHAY: dict = {}
_KHOA_DANG_CHAY = threading.Lock()


class DangCoTacVuKhac(RuntimeError):
    """Một phiên khác của Tool vừa khởi động tác vụ nền trên cùng thư mục dữ liệu."""


def _khoa(engine) -> str:
    thu_muc = getattr(engine, "data_dir", None)
    return os.path.normcase(os.path.abspath(thu_muc)) if thu_muc else f"id:{id(engine)}"


def dang_chay_cua(engine) -> Optional["TacVuNen"]:
    """Tác vụ nền đang chạy trên CÙNG thư mục dữ liệu (có thể của phiên khác), nếu có."""
    with _KHOA_DANG_CHAY:
        tv = _DANG_CHAY.get(_khoa(engine))
    return tv if tv is not None and tv.running else None


class TacVuNen:
    """Một tác vụ nền: một thread, trạng thái đọc qua ảnh chụp (``anh``) — không đối tượng nào của Streamlit."""

    def __init__(self, kind: str, huy: Callable[[], None], so_dong_bo=None):
        self.id = uuid.uuid4().hex
        self.kind = kind
        self.so_dong_bo = so_dong_bo          # sổ tiến độ đồng bộ kênh (chỉ đọc ảnh chụp ở giao diện)
        self._huy = huy
        self._khoa = threading.Lock()
        self._pct = 0.0
        self._msg = "Đang khởi động..."
        self._results = []
        self._error = ""
        self._running = False

    @property
    def running(self) -> bool:
        with self._khoa:
            return self._running

    def huy(self) -> None:
        """Nút Dừng (phiên nào cũng được): đặt cờ huỷ mà tác vụ đang đọc."""
        self._huy()

    def anh(self) -> dict:
        """Các trường của ``job`` giao diện, chụp dưới khoá."""
        with self._khoa:
            return {"running": self._running, "pct": self._pct, "msg": self._msg, "results": self._results,
                    "error": self._error, "kind": self.kind, "da_day_sheet": False}

    def bat_dau(self, engine, ham, args: tuple, kwargs: dict, *, job: dict, lease=None) -> None:
        """Ghi sổ rồi chạy ``ham(*args, progress=..., **kwargs)`` trong thread nền. ``job``: dict của phiên đã bấm —
        vẫn được ghi như trước. Phiên khác đã có tác vụ chạy trên cùng thư mục dữ liệu → ``DangCoTacVuKhac``
        (chưa chạy gì; người gọi tự trả ``lease``)."""
        k = _khoa(engine)
        with _KHOA_DANG_CHAY:
            khac = _DANG_CHAY.get(k)
            if khac is not None and khac is not self and khac.running:
                raise DangCoTacVuKhac("Đang có tác vụ nền chạy ở một cửa sổ/phiên khác của Tool — tải lại trang để "
                                      "xem tiến độ; không tạo tác vụ trùng.")
            with self._khoa:
                self._running = True
            _DANG_CHAY[k] = self

        def bao_tien_do(pct, msg):
            with self._khoa:
                self._pct, self._msg = pct, msg
            job["pct"], job["msg"] = pct, msg

        def target():
            ket_qua, loi = [], ""
            try:
                ket_qua = ham(*args, progress=bao_tien_do, **kwargs)
            except Exception as e:  # noqa: BLE001
                loi = str(e)
            finally:
                if lease is not None:
                    lease.tra()
                with self._khoa:
                    self._results, self._error = ket_qua, loi
                    self._running = False
                with _KHOA_DANG_CHAY:
                    if _DANG_CHAY.get(k) is self:
                        del _DANG_CHAY[k]
                job["results"], job["error"] = ket_qua, loi
                job["running"] = False

        threading.Thread(target=target, daemon=True, name=f"tac-vu-nen-{self.kind}").start()
