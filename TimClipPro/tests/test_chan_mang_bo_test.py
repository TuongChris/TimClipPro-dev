# -*- coding: utf-8 -*-
"""Bộ test tự chặn mạng (việc nhỏ #60): ``tests/conftest.py`` nạp ``tests/chan_mang/sitecustomize.py``.

Trước đây chỉ chặn khi người chạy nhớ đặt PYTHONPATH tới bộ chặn ngoài (``C:/Dev/pc2_test_tools/chan_mang``); quên là
test có thể gọi YouTube/Google thật. Kiểm: luật loopback, chặn TRƯỚC khi hàm gốc chạy, máy chủ giả trên 127.0.0.1 vẫn
dùng được, tiến trình con Python cũng bị chặn, biến tắt, không cài chồng bộ chặn có sẵn. Không phép thử nào mở kết nối
ra ngoài: chỗ cần địa chỉ ngoài thì hàm gốc là bản giả, hoặc tiến trình con thoát trước nếu chưa có bộ chặn.
"""
import importlib.util
import os
import socket
import subprocess
import sys
import threading

import pytest

import conftest

CHAN_MANG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chan_mang")
DA_TAT = os.environ.get("TIMCLIP_TEST_CHO_MANG") == "1"


def _nap():
    """Nạp thêm một bản module chặn (tên riêng) để thử hàm. Tiến trình này đã có bộ chặn nên bản mới không cài chồng."""
    spec = importlib.util.spec_from_file_location("chan_mang_thu", os.path.join(CHAN_MANG, "sitecustomize.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _con(ma: str, **env) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", ma], capture_output=True, text=True, timeout=120,
                          env={**os.environ, **env})


@pytest.mark.parametrize("host", [None, "", "localhost", "LocalHost", "127.0.0.1", "127.8.9.10", "::1", "[::1]",
                                  "::1%1", b"127.0.0.1"])
def test_loopback_duoc_phep(host):
    assert _nap().la_loopback(host)


@pytest.mark.parametrize("host", ["192.0.2.1", "8.8.8.8", "www.youtube.com", "sheets.googleapis.com", "127.vi-du.com",
                                  "127.0.0.1.vi-du.com", "0.0.0.0", "::", "::ffff:8.8.8.8", 12345])
def test_ngoai_loopback_bi_chan(host):
    assert not _nap().la_loopback(host)


def test_chan_truoc_khi_ham_goc_chay(monkeypatch):
    mod = _nap()
    goi = []
    monkeypatch.setattr(mod, "_GOC_CONNECT", lambda s, a: goi.append(a))
    monkeypatch.setattr(mod, "_GOC_CONNECT_EX", lambda s, a: goi.append(a))
    monkeypatch.setattr(mod, "_GOC_GETADDRINFO", lambda h, *a, **k: goi.append(h))
    for ham in (mod._connect, mod._connect_ex):
        with pytest.raises(OSError, match="chan mang.*TIMCLIP_TEST_CHO_MANG=1"):
            ham(None, ("192.0.2.1", 443))
    with pytest.raises(socket.gaierror, match="chan DNS"):
        mod._getaddrinfo("www.youtube.com", 443)
    assert goi == [], "đã gọi tới hàm mạng gốc dù địa chỉ ngoài loopback"
    mod._connect(None, ("127.0.0.1", 9))
    mod._connect_ex(None, ("::1", 9, 0, 0))
    mod._getaddrinfo("localhost", 9)
    assert goi == [("127.0.0.1", 9), ("::1", 9, 0, 0), "localhost"]


def test_khong_cai_chong_bo_chan_co_san(monkeypatch):
    monkeypatch.delenv("TIMCLIP_TEST_CHO_MANG", raising=False)
    for ten in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, ten, getattr(socket.socket, ten))
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)

    def co_san(self, address):
        raise OSError("bộ chặn có sẵn")

    monkeypatch.setattr(socket.socket, "connect", co_san)
    mod = _nap()
    assert mod.TRANG_THAI == "da_co" and socket.socket.connect is co_san


@pytest.mark.skipif(DA_TAT, reason="người chạy tắt chặn mạng (TIMCLIP_TEST_CHO_MANG=1)")
def test_bo_test_dang_chay_co_chan_mang_ca_tien_trinh_con():
    assert "connect" in vars(socket.socket) and conftest.chan_mang.TRANG_THAI in ("cai", "da_co"), (
        "bộ test đang chạy KHÔNG chặn mạng — tests/conftest.py phải tự cài tests/chan_mang/sitecustomize.py")
    if conftest.CHAN_CA_TIEN_TRINH_CON:
        assert os.environ["PYTHONPATH"].split(os.pathsep)[0] == CHAN_MANG
    r = _con("import socket; print('connect' in vars(socket.socket))")
    assert r.stdout.strip() == "True", f"tiến trình con Python KHÔNG bị chặn mạng: {r.stdout!r} {r.stderr[-500:]!r}"


def test_bo_chan_cua_repo_tu_nap_trong_tien_trinh_con():
    """Chỉ bộ chặn của repo trên PYTHONPATH (không bộ chặn ngoài): Python tự nạp nó, kết nối ngoài bị từ chối."""
    ma = ("import socket, sys\n"
          "if 'connect' not in vars(socket.socket):\n    sys.exit(3)\n"      # chưa cài: KHÔNG thử kết nối thật
          "try:\n    socket.socket().connect(('192.0.2.1', 9))\nexcept OSError as e:\n    print(e)\n")
    r = _con(ma, PYTHONPATH=CHAN_MANG, TIMCLIP_TEST_CHO_MANG="")
    assert r.returncode == 0 and "[test TimClipPro] chan mang" in r.stdout, (r.returncode, r.stdout, r.stderr[-500:])
    r = _con("import socket; print('connect' in vars(socket.socket))", PYTHONPATH=CHAN_MANG, TIMCLIP_TEST_CHO_MANG="1")
    assert r.stdout.strip() == "False", "TIMCLIP_TEST_CHO_MANG=1 vẫn cài bộ chặn"


def test_may_chu_gia_tren_loopback_van_dung_duoc():
    with socket.create_server(("127.0.0.1", 0)) as srv:
        cong = srv.getsockname()[1]

        def phuc_vu():
            for _ in range(2):
                c, _ = srv.accept()
                with c:
                    c.sendall(b"ok")

        luong = threading.Thread(target=phuc_vu, daemon=True)
        luong.start()
        for may in ("127.0.0.1", "localhost"):
            with socket.create_connection((may, cong), timeout=10) as c:
                assert c.recv(2) == b"ok"
        luong.join(10)
