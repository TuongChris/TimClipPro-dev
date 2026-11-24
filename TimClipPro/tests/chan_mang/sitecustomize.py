# -*- coding: utf-8 -*-
"""Chặn mạng cho bộ test TimClipPro (việc nhỏ #60): chỉ cho loopback — localhost, 127.0.0.0/8, ::1.

Hai lối nạp, cùng một mã:
* ``tests/conftest.py`` nạp file này cho tiến trình pytest, rồi thêm thư mục này vào ``PYTHONPATH``;
* tiến trình con Python (subprocess, multiprocessing spawn, worker joblib) thừa hưởng ``PYTHONPATH`` nên Python tự
  nạp file này dưới tên ``sitecustomize`` lúc khởi động — như bộ chặn ngoài ``C:/Dev/pc2_test_tools/chan_mang``.

Không cài chồng: ``socket.socket.connect`` đã bị thay (bộ chặn ngoài qua PYTHONPATH, PC1/PC2) thì để nguyên.
Tắt khi THẬT cần mạng: ``TIMCLIP_TEST_CHO_MANG=1``. Không in gì, không bao giờ ném lỗi lúc nạp; thông báo chặn viết
ASCII (tiến trình con có thể in ra console cp1252).
"""
import os
import socket

BIEN_TAT = "TIMCLIP_TEST_CHO_MANG"
_GOC_CONNECT = socket.socket.connect
_GOC_CONNECT_EX = socket.socket.connect_ex
_GOC_GETADDRINFO = socket.getaddrinfo
_GOI_Y = f"(can mang that: dat {BIEN_TAT}=1)"


def la_loopback(host) -> bool:
    """``None``/rỗng (không chỉ máy nào: bind, AI_PASSIVE), ``localhost``, IP loopback. Tên miền khác — kể cả
    «127.x.vi-du.com» — đều KHÔNG, vì phải hỏi DNS ra ngoài mới biết nó trỏ đâu."""
    if host is None:
        return True
    if isinstance(host, (bytes, bytearray)):
        host = host.decode("ascii", "ignore")
    if not isinstance(host, str):
        return False
    host = host.strip("[]").lower()
    if host in ("", "localhost"):
        return True
    import ipaddress

    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _kiem(address) -> None:
    if isinstance(address, tuple) and address and not la_loopback(address[0]):
        raise OSError(f"[test TimClipPro] chan mang: {address!r} {_GOI_Y}")


def _connect(self, address):
    _kiem(address)
    return _GOC_CONNECT(self, address)


def _connect_ex(self, address):
    _kiem(address)
    return _GOC_CONNECT_EX(self, address)


def _getaddrinfo(host, *args, **kwargs):
    if not la_loopback(host):
        raise socket.gaierror(f"[test TimClipPro] chan DNS: {host!r} {_GOI_Y}")
    return _GOC_GETADDRINFO(host, *args, **kwargs)


def cai_dat() -> str:
    """``"tat"`` (biến tắt), ``"da_co"`` (đã có bộ chặn khác — không cài chồng) hoặc ``"cai"`` (vừa cài)."""
    if os.environ.get(BIEN_TAT) == "1":
        return "tat"
    if "connect" in vars(socket.socket):
        return "da_co"
    socket.socket.connect = _connect
    socket.socket.connect_ex = _connect_ex
    socket.getaddrinfo = _getaddrinfo
    return "cai"


TRANG_THAI = cai_dat()
