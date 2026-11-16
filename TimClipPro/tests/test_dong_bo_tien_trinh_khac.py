# -*- coding: utf-8 -*-
"""Lượt đồng bộ kênh của tiến trình KHÁC (``cli.py kenh``, cửa sổ Tool khác) trên một thư mục kho (P3 handoff PC2).

``ChannelSync.sync`` giữ khoá HĐH ``<kho>/.dong_bo_kenh.lock`` suốt lượt. Giao diện chỉ biết lượt đồng bộ của CHÍNH tiến
trình (làn D-29, sổ tác vụ nền): lượt của tiến trình khác chỉ lộ ra sau khi bấm, còn dựng vân tay / dựng lại danh sách vẫn
chạy được trong lúc nó ghi file. Bất biến:
- Thăm dò chỉ HỎI: không chờ, không tạo/xoá/ghi file, không lấy khoá (Windows: chỉ đọc byte 0 — vùng đang bị khoá báo lỗi
  ngay) nên lượt đồng bộ thật bắt đầu đúng lúc đó không bao giờ bị từ chối vì nó. File khoá mồ côi (chủ đã chết) = rảnh.
- Lượt của chính tiến trình này không phải «khác» (làn D-29 do sổ tác vụ nền lo).
- Dựng vân tay trên thư mục đang bị tiến trình khác đồng bộ dừng TRƯỚC mọi ghi.
- Giao diện cảnh báo kèm thông tin chủ khoá và khoá các nút ghi vào thư mục đó.

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
from khoa import DangChayRoi, KhoaTienTrinh

GOC = Path(__file__).resolve().parents[1]
APP_PY = GOC / "app.py"
TEN_DONG_BO = "đồng bộ kênh vào kho này"        # tên tác vụ ``ChannelSync.sync`` ghi vào file khoá
NHAN_KENH = "Link kênh YouTube của bạn"
NHAN_KHO = "Thư mục kho clip gốc (ổ D, E... tùy bạn)"
NHAN_THU_MUC_KHO = "Đường dẫn thư mục chứa video gốc của kho này"
NUT_GHI_VAO_THU_MUC = ("⬇️ Bắt đầu đồng bộ kênh", "🛠️ Dựng lại danh sách đã tải",
                       "🌐 Lấy lại tên video thật cho kho này", "🔄 Tạo lại kho từ đầu", "➕ Bổ sung clip mới vào kho")
CHU_CANH_BAO = "tiến trình KHÁC"

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


# ---------------------------------------------------------------------------------------------------- engine

@pytest.mark.parametrize("mode", ["new", "add"])
def test_dung_van_tay_dung_truoc_moi_ghi_khi_tien_trinh_khac_dong_bo(engine, tmp_path, mode):
    kho = tmp_path / "Kho"
    kho.mkdir()
    data = Path(engine.data_dir)

    def anh() -> list:
        return sorted((str(p.relative_to(data)), p.stat().st_size, p.stat().st_mtime_ns)
                      for p in data.rglob("*") if p.is_file())

    truoc = anh()
    with _tien_trinh_khac_giu(kho):
        with pytest.raises(DangChayRoi, match="đang được đồng bộ kênh") as loi:
            engine.build_database(str(kho), mode)
    assert TEN_DONG_BO in str(loi.value), "phải kèm thông tin tiến trình đang đồng bộ"
    assert anh() == truoc, "phải dừng TRƯỚC mọi ghi (lease cổng bảo trì, tool.lock, sổ kho, vân tay)"


# ---------------------------------------------------------------------------------------------------- giao diện

def _o(at, nhan):
    return next(x for x in at.text_input if x.label == nhan)


def _nut(at, nhan):
    return next(b for b in at.button if b.label == nhan)


def _canh_bao(at) -> list:
    return [str(w.value) for w in at.warning if CHU_CANH_BAO in str(w.value)]


def _o_kho_dai(at):
    return next(c for c in at.checkbox if c.label.startswith("Kho video dài"))


def test_giao_dien_canh_bao_va_khoa_nut_khi_tien_trinh_khac_dong_bo(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    kho = tmp_path / "Kho"
    kho.mkdir()
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, at.exception
    at.session_state.eng.add_kho("Kho A")
    at.run()
    _o(at, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
    _o(at, NHAN_KHO).set_value(str(kho))
    _o(at, NHAN_THU_MUC_KHO).set_value(str(kho))
    at.run()
    assert not _canh_bao(at)
    assert not _nut(at, "🛠️ Dựng lại danh sách đã tải").disabled

    with _tien_trinh_khac_giu(kho) as pid_con:
        # Bấm lúc nút còn bật, tiến trình kia bắt đầu đồng bộ ngay trước lượt vẽ: lượt vẽ đó khoá nút nên Streamlit bỏ
        # cú bấm (chặn ``disabled`` phía máy chủ) — không dựng lại danh sách giữa lúc nó ghi.
        _nut(at, "🛠️ Dựng lại danh sách đã tải").click().run()
        assert not at.exception, at.exception
        assert at.session_state.job.get("kind") != "sua", "đã dựng lại danh sách giữa lúc tiến trình khác đồng bộ"
        canh_bao = _canh_bao(at)
        assert len(canh_bao) == 2, canh_bao          # tab đồng bộ kênh + tab quản lý kho
        assert all(f"PID: {pid_con}" in c and TEN_DONG_BO in c for c in canh_bao), canh_bao
        for nhan in NUT_GHI_VAO_THU_MUC:
            assert _nut(at, nhan).disabled, f"«{nhan}» phải bị khoá khi tiến trình khác đang đồng bộ thư mục này"
        assert _o_kho_dai(at).disabled

    assert _cho(lambda: channel.dang_dong_bo_khac(str(kho)) == "")
    at.run()
    assert not _canh_bao(at)
    for nhan in NUT_GHI_VAO_THU_MUC:
        assert not _nut(at, nhan).disabled, f"«{nhan}» phải bấm được lại khi lượt kia đã thoát"

    # Khoá do CHÍNH tiến trình này giữ (làn đồng bộ D-29 của giao diện): không báo «tiến trình khác».
    with KhoaTienTrinh(str(kho / channel.TEN_KHOA_DONG_BO), TEN_DONG_BO):
        at.run()
        assert not _canh_bao(at)
