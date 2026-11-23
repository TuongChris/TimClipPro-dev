# -*- coding: utf-8 -*-
"""Khóa liên tiến trình dựa trên cơ chế khóa file của hệ điều hành."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import IO, Optional


class DangChayRoi(Exception):
    """Đã có tiến trình khác đang giữ khóa."""


def khoa_byte0(f: IO[str]) -> None:
    """Khoá byte 0 của file đang mở, KHÔNG chờ: người khác giữ thì ném ``OSError``."""
    if sys.platform.startswith("win"):
        import msvcrt

        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def nha_byte0(f: IO[str]) -> None:
    if sys.platform.startswith("win"):
        import msvcrt

        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class KhoaTienTrinh:
    """Context manager giữ khóa độc quyền giữa các tiến trình."""

    def __init__(self, path: str, ten: str = ""):
        self.path = os.path.abspath(path)
        self.ten = ten
        self._file: Optional[IO[str]] = None
        self._thong_tin = ""

    @property
    def thong_tin_chu_khoa(self) -> str:
        """Mô tả tiến trình đang giữ khóa để đưa vào thông báo lỗi."""
        if self._thong_tin.strip():
            return self._thong_tin.strip()
        try:
            with open(self.path, encoding="utf-8", errors="replace") as f:
                f.seek(1)
                thong_tin = f.read().strip()
        except OSError:
            return "Không đọc được thông tin tiến trình đang giữ khóa."
        return thong_tin or "Không có thông tin tiến trình đang giữ khóa."

    def __enter__(self) -> "KhoaTienTrinh":
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        f = open(self.path, "a+", encoding="utf-8")
        self._file = f
        try:
            f.seek(0, os.SEEK_END)
            if f.tell() == 0:
                f.write("\n")
                f.flush()
            f.seek(1)
            thong_tin_truoc_khi_khoa = f.read().strip()
        except BaseException:
            f.close()
            self._file = None
            raise
        try:
            khoa_byte0(f)
        except OSError as e:
            self._thong_tin = thong_tin_truoc_khi_khoa
            f.close()
            self._file = None
            raise DangChayRoi(
                "Đã có tiến trình khác đang chạy. "
                f"Thông tin khóa: {self.thong_tin_chu_khoa}"
            ) from e

        try:
            self._thong_tin = (
                f"PID: {os.getpid()}\n"
                f"Thời điểm: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Tác vụ: {self.ten or 'không ghi tên'}"
            )
            f.seek(1)
            f.truncate(1)
            f.write(self._thong_tin + "\n")
            # Không fsync (23/11): ổ bận ghi → 0,1-1,4 s MỖI lần lấy khoá. Nội dung chỉ để báo «ai đang giữ» — tiến
            # trình khác đọc qua cache HĐH vẫn thấy; loại trừ là khoá vùng byte, mất điện thì khoá cũng đã nhả.
            f.flush()
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *a) -> None:
        f = self._file
        self._file = None
        if f is None:
            return
        try:
            try:
                nha_byte0(f)
            except OSError:
                pass
        finally:
            f.close()


def chu_khoa_dang_giu(path: str) -> str:
    """Thông tin chủ khoá (``KhoaTienTrinh.thong_tin_chu_khoa``) nếu có handle đang giữ khoá byte 0 của ``path`` — kể cả
    handle khác của chính tiến trình này; "" nếu rảnh hoặc chưa có file. Chỉ HỎI: không chờ, không tạo/ghi/xoá file.
    File khoá mồ côi (chủ đã chết, HĐH đã nhả khoá) = rảnh."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError:
        return ""
    try:
        if sys.platform.startswith("win"):
            # Vùng byte 0 đang bị khoá: đọc báo lỗi quyền NGAY. Không lấy khoá → lượt lấy khoá thật đúng lúc đó không
            # bao giờ bị từ chối vì phép hỏi này.
            os.read(fd, 1)
        else:
            import fcntl

            # shortcut: flock không hỏi được mà không lấy — khoá CHUNG rồi nhả ngay; lượt lấy khoá thật rơi đúng khe vài
            # micro-giây đó bị DangChayRoi. Chỉ ngoài Windows (Tool chạy trên Windows); cần thì đọc /proc/locks.
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
        return ""
    except (PermissionError, BlockingIOError):
        if sys.platform.startswith("win"):
            # CRT cũng đổi lỗi I/O (Win32 19–36, 65: ổ chưa sẵn sàng, CRC, lỗi đọc…) thành EACCES như vùng bị khoá.
            # Khoá chỉ phủ byte 0: đọc được byte 1 mới là khoá; byte 1 cũng lỗi = lỗi đọc, không kết luận «đang bị giữ».
            try:
                os.lseek(fd, 1, os.SEEK_SET)
                os.read(fd, 1)
            except OSError:
                return ""
    except OSError:
        return ""                           # lỗi đọc khác (ổ mạng rớt…): không kết luận «đang bị giữ»
    finally:
        os.close(fd)
    return KhoaTienTrinh(path).thong_tin_chu_khoa
