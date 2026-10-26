# -*- coding: utf-8 -*-
"""Gom tín hiệu dừng từ hệ điều hành, Engine và file điều khiển."""

from __future__ import annotations

import os
import signal
from typing import Any

# Dung sai so mtime file dừng với mốc time.time(): mtime do hệ thống file đóng dấu theo đồng hồ
# thô (Windows ~15,6 ms/nhịp, FAT/exFAT làm tròn 2 s), nên file ghi CÙNG lúc mốc có thể mang mtime
# nhỏ hơn mốc. Chỉ file cũ hơn mốc QUÁ dung sai mới là yêu cầu cũ; file sót từ lượt trước luôn cũ
# hơn nhiều (lượt chạy theo lịch cách nhau hàng phút trở lên).
DUNG_SAI_MTIME_S = 2.0


def mtime_file_dung_cu(file_dung: str, moc_bat_dau: float | None) -> float | None:
    """mtime của file dừng có từ TRƯỚC mốc bắt đầu lượt (yêu cầu cũ, bị bỏ qua); None nếu không có.

    «Trước» = cũ hơn mốc quá `DUNG_SAI_MTIME_S`; file ghi sát mốc vẫn là yêu cầu cho lượt này.
    """
    if not file_dung or moc_bat_dau is None:
        return None
    try:
        mtime = os.path.getmtime(file_dung)
    except OSError:
        return None
    return mtime if mtime < moc_bat_dau - DUNG_SAI_MTIME_S else None


class YeuCauDung:
    """Gom mọi nguồn tín hiệu dừng về một chỗ."""

    def __init__(self, engine: Any = None, file_dung: str = "",
                 moc_bat_dau: float | None = None) -> None:
        self.engine = engine
        self.file_dung = file_dung
        # Mốc (time.time()) lượt bắt đầu: file dừng sửa TRƯỚC mốc là yêu cầu cũ (lượt trước bị
        # kill trước `finally`, hay `cli.py dung` khi không có lượt nào chạy) — không dừng lượt này.
        # Không xoá file đó: `cli.py dung` mới ghi đè file → mtime mới → vẫn dừng được (audit C-12).
        self.moc_bat_dau = moc_bat_dau
        self._da_dat = False
        self._so_tin_hieu = 0

    def bat_tin_hieu(self) -> None:
        """Đăng ký Ctrl+C và SIGTERM; tín hiệu đầu chỉ đặt cờ dừng."""
        def handler(signum, frame):
            self._so_tin_hieu += 1
            if self._so_tin_hieu >= 2:
                raise KeyboardInterrupt
            self.dat()

        signal.signal(signal.SIGINT, handler)
        sigterm = getattr(signal, "SIGTERM", None)
        if sigterm is not None:
            signal.signal(sigterm, handler)

    def can_dung(self) -> bool:
        """Kiểm cờ nội bộ, cờ Engine, rồi file dừng theo thứ tự chi phí."""
        if self._da_dat:
            return True
        cancel_event = getattr(self.engine, "cancel_event", None)
        if cancel_event is not None and cancel_event.is_set():
            return True
        if not (self.file_dung and os.path.exists(self.file_dung)):
            return False
        return mtime_file_dung_cu(self.file_dung, self.moc_bat_dau) is None

    def dat(self) -> None:
        """Đặt cờ nội bộ và chuyển yêu cầu xuống Engine nếu có."""
        self._da_dat = True
        cancel_event = getattr(self.engine, "cancel_event", None)
        if cancel_event is not None:
            cancel_event.set()

    def don_file_dung(self) -> None:
        """Xóa file dừng nếu có để lượt sau không bị dừng oan."""
        if not self.file_dung:
            return
        try:
            os.remove(self.file_dung)
        except FileNotFoundError:
            pass
