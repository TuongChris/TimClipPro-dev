# -*- coding: utf-8 -*-
"""Giai đoạn 3 giao diện «bớt thao tác tay»: nút «📂 Chọn…» cho mọi ô đường dẫn, «📂 Mở thư mục» sau khi tải/cắt/ghép,
ô thư mục kho tự điền theo kho đang dùng, lối tắt sang trang kế tiếp. Không mở hộp thoại thật: hàm chọn bị thay."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import tai_video_goc
import ui_thao_tac

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def _app(tmp_path, monkeypatch, moi_trang=True):
    import streamlit

    if not moi_trang:
        monkeypatch.delenv("TIMCLIP_UI_VE_MOI_TRANG", raising=False)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _o(at, nhan_dau: str):
    return next(t for t in at.text_input if t.label.startswith(nhan_dau))


def _bam(at, khoa: str):
    at.button(key=khoa).click().run()
    assert not at.exception, [e.value for e in at.exception]


def _thay_chon(monkeypatch, thu_muc: str = "", files: list | None = None):
    goi = []
    monkeypatch.setattr(tai_video_goc, "chon_thu_muc", lambda ban_dau="", tieu_de="": goi.append(ban_dau) or thu_muc)
    monkeypatch.setattr(tai_video_goc, "chon_file",
                        lambda ban_dau="", nhieu=False, tieu_de="": goi.append((ban_dau, nhieu)) or list(files or []))
    return goi


def test_dong_bo_chon_thu_muc_kho(tmp_path, monkeypatch):
    chon = str(tmp_path / "Kho đã chọn")
    _thay_chon(monkeypatch, thu_muc=chon)
    at = _app(tmp_path, monkeypatch)
    _bam(at, "chon_kho_dir")
    assert at.session_state.kho_dir == chon
    assert _o(at, "Thư mục kho clip gốc").value == chon


def test_dong_bo_o_kho_trong_tu_dien_thu_muc_kho_dang_dung_nhung_giu_gia_tri_go(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    assert at.session_state.kho_dir == ""
    goc = tmp_path / "ClipGoc"
    goc.mkdir()
    at.session_state.eng.add_kho("Kho A", str(goc))
    at.run()
    assert at.session_state.kho_dir == str(goc)
    _o(at, "Thư mục kho clip gốc").set_value(str(tmp_path / "Khac"))
    at.run()
    assert at.session_state.kho_dir == str(tmp_path / "Khac")


def test_dong_bo_doi_kho_thi_o_tu_dien_theo_kho_moi(tmp_path, monkeypatch):
    """Review 23/11 số 2: ô đã tự điền thư mục kho A, đổi sang kho B → ô hiện thư mục kho B (trước đây giữ A và
    «Bắt đầu đồng bộ» tải kênh B vào kho A). Kho chưa có thư mục thì ô trống."""
    a, b = tmp_path / "A", tmp_path / "B"
    a.mkdir()
    b.mkdir()
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    eng.add_kho("Kho A", str(a))
    eng.use_kho("Kho A")
    at.run()
    assert _o(at, "Thư mục kho clip gốc").value == str(a)
    eng.add_kho("Kho B", str(b))
    eng.use_kho("Kho B")
    at.run()
    assert _o(at, "Thư mục kho clip gốc").value == str(b)
    eng.add_kho("Kho C", "")
    eng.use_kho("Kho C")
    at.run()
    assert _o(at, "Thư mục kho clip gốc").value == ""


def test_dong_bo_chon_lai_dung_duong_dan_cu_van_an(tmp_path, monkeypatch):
    """Review 23/11 số 5: chọn X, gõ đè, rồi chọn lại X → ô hiện X (ô không key bỏ qua lựa chọn trùng giá trị cũ)."""
    chon = str(tmp_path / "Kho X")
    _thay_chon(monkeypatch, thu_muc=chon)
    at = _app(tmp_path, monkeypatch)
    _bam(at, "chon_kho_dir")
    _o(at, "Thư mục kho clip gốc").set_value("gõ dở").run()
    assert at.session_state.kho_dir == "gõ dở"
    _bam(at, "chon_kho_dir")
    assert _o(at, "Thư mục kho clip gốc").value == chon
    assert at.session_state.kho_dir == chon


def test_dong_bo_co_nut_mo_thu_muc_kho(tmp_path, monkeypatch):
    goi = []
    monkeypatch.setattr(os, "startfile", goi.append, raising=False)
    kho = tmp_path / "kho"
    kho.mkdir()
    at = _app(tmp_path, monkeypatch)
    _o(at, "Thư mục kho clip gốc").set_value(str(kho))
    at.run()
    _bam(at, "mo_tm_kho_dong_bo")
    assert goi == [str(kho)]


def test_kho_clip_goc_chon_thu_muc_nguon(tmp_path, monkeypatch):
    chon = str(tmp_path / "Nguon")
    _thay_chon(monkeypatch, thu_muc=chon)
    at = _app(tmp_path, monkeypatch)
    _bam(at, "chon_thu_muc_kho")
    assert _o(at, "Đường dẫn thư mục chứa video gốc").value == chon


def test_kho_clip_goc_o_thu_muc_theo_thu_muc_kho_vua_doi(tmp_path, monkeypatch):
    """Review 23/11 số 1: thư mục kho đổi ở trang khác (hay kho xoá rồi tạo lại cùng tên) → ô hiện thư mục mới, không
    giữ thư mục cũ cho «Tạo lại» / «Bổ sung»."""
    a, b = tmp_path / "A", tmp_path / "B"
    a.mkdir()
    b.mkdir()
    at = _app(tmp_path, monkeypatch)
    at.session_state.eng.add_kho("Kho", str(a))
    at.session_state.eng.use_kho("Kho")
    at.run()
    assert _o(at, "Đường dẫn thư mục chứa video gốc").value == str(a)
    at.session_state.eng.update_kho("Kho", str(b))
    at.run()
    assert _o(at, "Đường dẫn thư mục chứa video gốc").value == str(b)


def test_danh_sach_kho_chon_thu_muc_moi(tmp_path, monkeypatch):
    chon = str(tmp_path / "Audio")
    _thay_chon(monkeypatch, thu_muc=chon)
    at = _app(tmp_path, monkeypatch)
    at.session_state.eng.add_kho("Kho B", "")
    at.run()
    _bam(at, "chon_dsv_thu_muc")
    assert at.text_input(key="dsv_thu_muc_moi::Kho B").value == chon


def test_danh_sach_kho_o_sua_thu_muc_rieng_tung_kho(tmp_path, monkeypatch):
    """Review 23/11 số 3: đường dẫn gõ cho kho A không sang ô của kho B (một cú «Lưu» là B trỏ vào audio của A)."""
    at = _app(tmp_path, monkeypatch)
    at.session_state.eng.add_kho("Kho A", "")
    at.session_state.eng.add_kho("Kho B", "")
    at.run()
    at.selectbox(key="dsv_kho").set_value("Kho A").run()
    at.text_input(key="dsv_thu_muc_moi::Kho A").set_value(str(tmp_path / "AudioA")).run()
    at.selectbox(key="dsv_kho").set_value("Kho B").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.text_input(key="dsv_thu_muc_moi::Kho B").value == ""


def test_quet_file_chon_thu_muc_hoac_file(tmp_path, monkeypatch):
    f = tmp_path / "video.mp4"
    f.write_bytes(b"x")
    _thay_chon(monkeypatch, thu_muc=str(tmp_path), files=[str(f)])
    at = _app(tmp_path, monkeypatch)
    _bam(at, "chon_file_quet")
    assert at.session_state.thu_muc_quet_gan_nhat == str(f)
    assert _o(at, "Đường dẫn file hoặc thư mục").value == str(f)
    _bam(at, "chon_thu_muc_quet")
    assert at.session_state.thu_muc_quet_gan_nhat == str(tmp_path)


def test_twitch_chon_file_proxy_va_cookie(tmp_path, monkeypatch):
    _thay_chon(monkeypatch, files=[str(tmp_path / "proxy.txt")])
    at = _app(tmp_path, monkeypatch)
    _bam(at, "chon_twitch_proxy")
    assert at.session_state.twitch_proxy_file == str(tmp_path / "proxy.txt")
    _thay_chon(monkeypatch, files=[str(tmp_path / "ck.txt")])
    _bam(at, "chon_twitch_cookie")
    assert at.session_state.twitch_cookie_file == str(tmp_path / "ck.txt")
    assert at.session_state.twitch_proxy_file == str(tmp_path / "proxy.txt")


@pytest.mark.parametrize("khoa_o,khoa_nut", [("file_may", "chon_file_may"), ("o_links_ghep", "chon_file_ghep")])
def test_chon_nhieu_file_them_vao_cuoi_khong_trung(tmp_path, monkeypatch, khoa_o, khoa_nut):
    a, b = str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")
    goi = _thay_chon(monkeypatch, files=[a, b])
    at = _app(tmp_path, monkeypatch)
    at.text_area(key=khoa_o).set_value(f"https://youtu.be/abcdefghij1\n{a}").run()
    _bam(at, khoa_nut)
    assert at.text_area(key=khoa_o).value == f"https://youtu.be/abcdefghij1\n{a}\n{b}"
    assert goi[-1][1] is True   # được chọn nhiều file


def test_ket_qua_tai_co_nut_mo_thu_muc(tmp_path, monkeypatch):
    goi = []
    monkeypatch.setattr(os, "startfile", goi.append, raising=False)
    ra = tmp_path / "VideoGoc"
    ra.mkdir()
    (ra / "v.mp4").write_bytes(b"x")
    at = _app(tmp_path, monkeypatch)
    at.session_state.job.update({"running": False, "kind": "tai_video", "error": "", "results": [
        {"url": "https://youtu.be/abcdefghij1", "trang_thai": "xong", "duong_dan": str(ra / "v.mp4"),
         "tieu_de": "T", "chat_luong": "720p", "ghi_chu": ""}]})
    at.run()
    _bam(at, "mo_tm_tai_0")
    assert goi == [str(ra)]


def test_thu_muc_ket_qua_ghep_chi_lay_file_ghep(tmp_path):
    ra, nguon, anh = tmp_path / "ra", tmp_path / "nguon", tmp_path / "anh"
    for d in (ra, nguon, anh):
        d.mkdir()
    (ra / "Video_ghep.mp4").write_bytes(b"x")
    (nguon / "intro.mp4").write_bytes(b"x")
    ghep = [
        {"trang_thai": "xong", "duong_dan": str(nguon / "intro.mp4"), "la_file_may": True},
        {"trang_thai": "xong", "duong_dan": str(tmp_path / "tam" / "phan.mp4")},   # phần lẻ đã xoá
        {"trang_thai": "xong", "duong_dan": str(ra / "Video_ghep.mp4"), "la_dong_ghep": True},
    ]
    assert ui_thao_tac.thu_muc_ket_qua(ghep) == [str(ra)]
    # chụp nhiều mốc: duong_dan là thư mục ảnh; dòng lỗi / file không còn bị bỏ
    assert ui_thao_tac.thu_muc_ket_qua([
        {"trang_thai": "xong", "duong_dan": str(anh)},
        {"trang_thai": "loi", "duong_dan": str(ra / "Video_ghep.mp4")},
        {"trang_thai": "xong", "duong_dan": str(tmp_path / "mat.mp4")},
    ]) == [str(anh)]


def test_noi_dong_giu_dong_cu_bo_trung():
    assert ui_thao_tac.noi_dong("a\n\nb", ["b", "c", "c"]) == "a\nb\nc"
    assert ui_thao_tac.noi_dong("", ["x"]) == "x"
    # Review 23/11 số 6: dòng có ngoặc kép («Copy as path») hoặc khác chữ hoa/thường vẫn là cùng một file.
    assert ui_thao_tac.noi_dong('"C:\\Video\\Intro.mp4"', ["c:\\video\\INTRO.mp4", "C:\\b.mp4"]) == (
        '"C:\\Video\\Intro.mp4"\nC:\\b.mp4')


def test_chon_file_tach_nhieu_dong_va_mo_o_thu_muc_cua_file(tmp_path, monkeypatch):
    f = tmp_path / "cu.txt"
    f.write_bytes(b"x")
    ra = {}

    def chay(lenh, **kw):
        ra["lenh"] = lenh
        return tai_video_goc.subprocess.CompletedProcess(lenh, 0, "D:/a b.mp4\nD:/Phim gốc.mkv\n".encode("utf-8"), b"")

    monkeypatch.setattr(tai_video_goc.subprocess, "run", chay)
    assert tai_video_goc.chon_file(str(f), nhieu=True) == [os.path.normpath("D:/a b.mp4"),
                                                          os.path.normpath("D:/Phim gốc.mkv")]
    assert ra["lenh"][-3] == "nhieu_file" and ra["lenh"][-1] == str(tmp_path)
    compile(tai_video_goc._HOP_THOAI, "hop_thoai", "exec")


def test_menu_that_chua_co_kho_co_loi_tat_sang_trang_kho(tmp_path, monkeypatch):
    """Menu thật (không phải chế độ 15 tab của bộ test): trang mặc định «Quét YouTube» chưa có kho → lối tắt sang
    trang «Kho clip gốc»."""
    at = _app(tmp_path, monkeypatch, moi_trang=False)
    links = [e.proto for e in at.get("page_link")]
    assert any("Kho clip gốc" in p.label and p.page.endswith("kho-clip-goc") for p in links), links
