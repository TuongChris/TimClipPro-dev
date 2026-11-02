"""CHỈ cho lần chạy test (đặt PYTHONPATH trỏ tới thư mục này): chặn mọi kết nối mạng ra ngoài, chỉ cho loopback.

Python tự nạp file này khi PYTHONPATH trỏ tới thư mục chứa nó; tiến trình con thừa hưởng PYTHONPATH.
"""
import socket

_GOC_CONNECT = socket.socket.connect
_GOC_CONNECT_EX = socket.socket.connect_ex
_GOC_GETADDRINFO = socket.getaddrinfo


def _la_noi_bo(host) -> bool:
    if host is None:
        return True
    if isinstance(host, (bytes, bytearray)):
        host = host.decode("ascii", "ignore")
    if not isinstance(host, str):
        return False
    host = host.strip("[]").lower()
    return host in ("", "localhost", "::1", "0.0.0.0", "::") or host.startswith("127.") or host.endswith(".localhost")


def _kiem(address) -> None:
    if isinstance(address, tuple) and address and not _la_noi_bo(address[0]):
        raise OSError(f"[PC2 test] network blocked: {address!r}")  # ASCII: console cp1252


def _connect(self, address):
    _kiem(address)
    return _GOC_CONNECT(self, address)


def _connect_ex(self, address):
    _kiem(address)
    return _GOC_CONNECT_EX(self, address)


def _getaddrinfo(host, *args, **kwargs):
    if not _la_noi_bo(host):
        raise socket.gaierror(f"[PC2 test] DNS blocked: {host!r}")
    return _GOC_GETADDRINFO(host, *args, **kwargs)


socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex
socket.getaddrinfo = _getaddrinfo
