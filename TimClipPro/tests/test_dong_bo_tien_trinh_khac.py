# -*- coding: utf-8 -*-
"""Lượt đồng bộ kênh của tiến trình KHÁC (``cli.py kenh``, cửa sổ Tool khác) trên một thư mục kho (P3 handoff PC2).

``ChannelSync.sync`` giữ khoá HĐH ``<kho>/.dong_bo_kenh.lock`` suốt lượt. Giao diện chỉ biết lượt đồng bộ của CHÍNH tiến
trình (làn D-29, sổ tác vụ nền): lượt của tiến trình khác chỉ lộ ra sau khi bấm, còn dựng vân tay / dựng lại danh sách vẫn
chạy được trong lúc nó ghi file. Bất biến:
- Thăm dò chỉ HỎI: không chờ, không tạo/xoá/ghi file, không lấy khoá (Windows: chỉ đọc byte 0 — vùng đang bị khoá báo lỗi
  ngay) nên lượt đồng bộ thật bắt đầu đúng lúc đó không bao giờ bị từ chối vì nó. File khoá mồ côi (chủ đã chết) = rảnh.
- Lượt của chính tiến trình này không phải «khác» (làn D-29 do sổ tác vụ nền lo).

Mọi thứ synthetic: thư mục tạm, tiến trình con chỉ giữ khoá thật, không mạng.
"""

from __future__ import annotations

import contextlib
import errno
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import channel
import khoa
from khoa import KhoaTienTrinh

GOC = Path(__file__).resolve().parents[1]
TEN_DONG_BO = "đồng bộ kênh vào kho này"        # tên tác vụ ``ChannelSync.sync`` ghi vào file khoá

_MA_GIU_KHOA = (
    "import os, time\n"
    "from khoa import KhoaTienTrinh\n"
    "with KhoaTienTrinh(os.environ['TIMCLIP_TEST_LOCK'], os.environ['TIMCLIP_TEST_TEN']):\n"
    "    print('READY', os.getpid(), flush=True)\n"
    "    time.sleep(120)\n"
)


@contextlib.contextmanager
def _tien_trinh_khac_giu(thu_muc: Path):
    """Tiến trình con THẬT giữ khoá đồng bộ của ``thu_muc`` (như ``cli.py kenh`` đang chạy); ra khỏi khối = giết nó.
    Trả PID tiến trình giữ khoá — ``python.exe`` của venv trên Windows là trình khởi chạy, ``Popen.pid`` là PID của nó."""
    env = {**os.environ, "TIMCLIP_TEST_LOCK": str(thu_muc / channel.TEN_KHOA_DONG_BO), "TIMCLIP_TEST_TEN": TEN_DONG_BO}
    con = subprocess.Popen([sys.executable, "-c", _MA_GIU_KHOA], cwd=str(GOC), env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        dong = con.stdout.readline().split()
        assert dong[:1] == ["READY"], con.stderr.read()
        yield int(dong[1])
    finally:
        con.kill()
        con.wait(timeout=10)


def _cho(dieu_kien, han_s: float = 10.0) -> bool:
    """Windows nhả khoá của tiến trình đã chết sau một nhịp ngắn, nhất là lúc máy bận (như ``test_khoa``)."""
    het = time.monotonic() + han_s
    while not dieu_kien():
        if time.monotonic() > het:
            return False
        time.sleep(0.05)
    return True


# ---------------------------------------------------------------------------------------------------- thăm dò

def test_tham_do_thay_tien_trinh_khac_dang_dong_bo_va_ranh_khi_no_chet(tmp_path, monkeypatch):
    kho = tmp_path / "Kho"
    kho.mkdir()
    duong = kho / channel.TEN_KHOA_DONG_BO
    assert channel.dang_dong_bo_khac(str(kho)) == ""
    assert not duong.exists(), "thăm dò không được tạo file khoá"

    with _tien_trinh_khac_giu(kho) as pid_con:
        chu = channel.dang_dong_bo_khac(str(kho))
        assert f"PID: {pid_con}" in chu and TEN_DONG_BO in chu, chu
        assert khoa.chu_khoa_dang_giu(str(duong)) == chu
        truoc = duong.stat()
        monkeypatch.chdir(kho)
        assert channel.dang_dong_bo_khac("") == "", "ô thư mục trống không được dò file khoá ở thư mục hiện hành"

    # Tiến trình chết (sập, đóng cửa sổ): HĐH nhả khoá, file khoá vẫn nằm đó nhưng phải đọc là RẢNH.
    assert _cho(lambda: channel.dang_dong_bo_khac(str(kho)) == ""), "file khoá mồ côi phải đọc là rảnh"
    sau = duong.stat()
    assert (sau.st_size, sau.st_mtime_ns) == (truoc.st_size, truoc.st_mtime_ns), "thăm dò không được sửa/xoá file khoá"


def test_file_khoa_mo_coi_khong_ai_giu_la_ranh_va_giu_nguyen(tmp_path):
    kho = tmp_path / "Kho"
    kho.mkdir()
    duong = kho / channel.TEN_KHOA_DONG_BO
    cu = f"\nPID: 4242\nThời điểm: 2026-11-01 08:00:00\nTác vụ: {TEN_DONG_BO}\n".encode("utf-8")
    duong.write_bytes(cu)

    assert channel.dang_dong_bo_khac(str(kho)) == ""
    assert khoa.chu_khoa_dang_giu(str(duong)) == ""
    assert duong.read_bytes() == cu


def test_luot_cua_chinh_tien_trinh_nay_khong_tinh_la_khac(tmp_path):
    kho = tmp_path / "Kho"
    kho.mkdir()
    duong = str(kho / channel.TEN_KHOA_DONG_BO)
    with KhoaTienTrinh(duong, TEN_DONG_BO):
        assert khoa.chu_khoa_dang_giu(duong).startswith(f"PID: {os.getpid()}\n"), "handle khác cùng tiến trình vẫn thấy"
        assert channel.dang_dong_bo_khac(str(kho)) == "", "làn đồng bộ của chính tiến trình không phải «khác»"
    assert khoa.chu_khoa_dang_giu(duong) == ""


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="thăm dò chỉ-đọc là của Windows")
def test_tham_do_khong_bao_gio_lay_khoa(tmp_path, monkeypatch):
    """Lượt đồng bộ thật bắt đầu ĐÚNG lúc giao diện đang hỏi không được bị ``DangChayRoi``: thăm dò không lấy khoá."""
    import msvcrt

    duong = str(tmp_path / channel.TEN_KHOA_DONG_BO)

    def cam(*_a):
        raise AssertionError("thăm dò đã gọi msvcrt.locking, tức là LẤY khoá")

    with KhoaTienTrinh(duong, TEN_DONG_BO):
        with monkeypatch.context() as m:
            m.setattr(msvcrt, "locking", cam)
            assert khoa.chu_khoa_dang_giu(duong)
    with monkeypatch.context() as m:
        m.setattr(msvcrt, "locking", cam)
        assert khoa.chu_khoa_dang_giu(duong) == ""


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="nhánh đọc byte 0 là của Windows")
def test_loi_doc_khac_khong_bi_coi_la_dang_bi_giu(tmp_path, monkeypatch):
    """Ổ mạng rớt giữa chừng: lỗi đọc KHÔNG phải «đang có tiến trình khác giữ» (không khoá nhầm nút, không làm sập trang)."""
    duong = tmp_path / channel.TEN_KHOA_DONG_BO
    duong.write_text(f"\nPID: 4242\nTác vụ: {TEN_DONG_BO}\n", encoding="utf-8")

    def doc_hong(*_a):
        raise OSError(errno.EIO, "ổ mạng rớt")

    with monkeypatch.context() as m:
        m.setattr(os, "read", doc_hong)
        ket_qua = khoa.chu_khoa_dang_giu(str(duong))
    assert ket_qua == ""
