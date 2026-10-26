# -*- coding: utf-8 -*-
"""Audit E-3: tiêu đề video YouTube (dữ liệu NGOÀI — do bên bị khiếu nại đặt) không được diễn giải
Markdown/LaTeX ở màn tiến độ quét, các thông báo kết quả và file hồ sơ khiếu nại .md.

Streamlit diễn giải GitHub-flavored Markdown + LaTeX trong ``st.markdown``, ``st.caption``, ``st.info``,
``st.warning``, ``st.error``, ``st.success``: ``![](url)`` thành ``<img>`` do trình duyệt của người vận hành
tự tải từ máy chủ của bên vi phạm (lộ IP + giờ quét), ``[chữ](url)`` thành link bấm được giống chữ của
tool, ``$..$`` thành công thức. Màn đồng bộ kênh đã có quy tắc đúng (``ui_tien_do_dong_bo``: ``st.text`` —
«tiêu đề video là dữ liệu ngoài — không diễn giải markdown/LaTeX»). File hồ sơ .md cũng là Markdown: trình
xem Markdown nào mở nó cũng tải ảnh/hiện link y như vậy.

Bất biến kiểm ở đây: tiêu đề ngoài chỉ tới phần tử/file diễn giải Markdown khi ĐÃ thoát (``\\!``/``\\[``/
``\\]``/``\\(``, ``\\$``) — hoặc đi qua phần tử không diễn giải (``st.text``, ``st.code``) — và vẫn phải hiện
cho người dùng đọc được.

Dữ liệu tổng hợp, không mạng (URL trỏ 127.0.0.1:9), không dữ liệu thật.
"""

from __future__ import annotations

import re
from pathlib import Path

import dossier
import tien_do_quet as tdq
import ui_tien_do_quet as ui
from engine import ScanResult

APP_PY = Path(__file__).resolve().parents[1] / "app.py"

DAU = "TieuDeGiaE3"   # mốc để tìm tiêu đề trong đầu ra, kể cả sau khi thoát
TIEU_DE_DOC = (f"{DAU} ![x](https://127.0.0.1:9/p.gif) "
               "[Cấp lại quyền Google Sheets](https://127.0.0.1:9/login) $c$ *SML*")

PHAN_TU_MARKDOWN = ("markdown", "caption", "warning", "info", "error", "success")

# Ảnh: «!» chưa thoát ngay trước «[» chưa thoát … «](».
_ANH_THO = re.compile(r"(?<!\\)!(?<!\\)\[[^\]\n]*(?<!\\)\]\(")
# Link: «[» chưa thoát … «]» chưa thoát ngay trước «(».
_LINK_THO = re.compile(r"(?<!\\)\[[^\]\n]*(?<!\\)\]\(")
_DOLLAR_THO = re.compile(r"(?<!\\)\$")


def _loi_dien_giai(chu: str) -> list:
    """Các mẩu Markdown/LaTeX mà Streamlit / trình xem .md sẽ diễn giải."""
    loi = []
    if _ANH_THO.search(chu):
        loi.append("ẢNH Markdown chưa thoát ![..](https://127.0.0.1:9/p.gif) -> <img> tải từ máy ngoài")
    if _LINK_THO.search(chu):
        loi.append("LINK Markdown chưa thoát [..](https://127.0.0.1:9/...) -> link bấm được")
    if _DOLLAR_THO.search(chu):
        loi.append("dấu $ chưa thoát -> LaTeX")
    return loi


def _bao(vi_pham) -> str:
    return "\n".join(f"  st.{t}: {c[:160]!r}\n      -> {loi}" for t, c, loi in vi_pham)


# ------------------------------------------------------------------ (1) màn tiến độ quét: dong_chi_tiet

def _anh_tien_do():
    from scan_jobs import BatchSnapshot, VideoState
    v = VideoState(index=1, nguon="https://youtu.be/x", scan_status="running", phase="downloading",
                   title=TIEU_DE_DOC)
    td = tdq.AnhTienDo(batch_id="b", index=1, tong=1, tieu_de=TIEU_DE_DOC, giai_doan=tdq.GD_TAI,
                       giai_doan_luc=1.0, byte_da_nhan=1024 * 1024, byte_tong=4 * 1024 * 1024)
    anh = BatchSnapshot(batch_id="b", total=1, current_index=1, completed=0, failed=0, running=True,
                        cancelled=False, elapsed_seconds=5.0, eta_seconds=None, message="",
                        videos=(v,), tien_do=td, worker_alive=True)
    return anh, v


def test_e3_dong_chi_tiet_tien_do_quet_khong_dien_giai_tieu_de():
    # ve_tien_do_lo: st.markdown("  \n".join(dong_chi_tiet(...)))
    anh, v = _anh_tien_do()
    dong_dau = ui.dong_chi_tiet(anh, v, {}, 10.0)[0]
    assert DAU in dong_dau, "tiêu đề vẫn phải hiện cho người dùng"
    assert _loi_dien_giai(dong_dau) == [], (
        f"st.markdown sẽ diễn giải tiêu đề ngoài: {dong_dau!r} -> {_loi_dien_giai(dong_dau)}")


# ------------------------------------------------------------------ (2) app thật (AppTest): kết quả sau lượt

def _phan_tu(at) -> list:
    ra = []
    for ten in PHAN_TU_MARKDOWN + ("text", "code"):
        try:
            nhom = getattr(at, ten)
        except Exception:   # noqa: BLE001 — loại phần tử không có trong bản Streamlit này
            continue
        ra.extend((ten, str(i.value)) for i in nhom)
    return ra


def _chay_app(tmp_path, monkeypatch, results: list):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, at.exception
    at.session_state.job.update({"running": False, "results": results, "error": "",
                                 "kind": "scan", "da_day_sheet": True})
    at.run()
    assert not at.exception, at.exception
    return at


def _kiem_app(at, can_co: str):
    tat_ca = _phan_tu(at)
    co = [(t, c) for t, c in tat_ca if DAU in c]
    assert co, f"{can_co} phải nêu tên video"
    vi_pham = [(t, c, _loi_dien_giai(c)) for t, c in co
               if t in PHAN_TU_MARKDOWN and _loi_dien_giai(c)]
    assert vi_pham == [], "tiêu đề ngoài vào phần tử diễn giải Markdown/LaTeX:\n" + _bao(vi_pham)


def test_e3_app_ket_qua_ok_0_doan_va_quet_mot_phan_khong_dien_giai_tieu_de(tmp_path, monkeypatch):
    # app.py: bao_cao_khong_co_ket_qua -> st.warning(f"**{tieu_de}** — ...");
    # bang_ket_qua -> st.info("Chưa quét trọn ... - {r.source_name[:60]}: ...").
    kq = ScanResult(source_name=TIEU_DE_DOC, source_ref="https://youtu.be/x", source_id="x",
                    status="ok", duration_s=600.0, pham_vi_quet_s=120.0,
                    ly_do_pham_vi="gioi_han_tai")
    at = _chay_app(tmp_path, monkeypatch, [kq])
    _kiem_app(at, "báo cáo 0 kết quả / chưa quét trọn")


def test_e3_app_nguon_loi_khong_dien_giai_tieu_de(tmp_path, monkeypatch):
    # app.py: st.error("Có nguồn bị lỗi: " + "; ".join(f"{x.source_name} ({x.note})" ...))
    kq = ScanResult(source_name=TIEU_DE_DOC, source_ref="https://youtu.be/x", source_id="x",
                    status="error", note="lỗi tải giả")
    at = _chay_app(tmp_path, monkeypatch, [kq])
    _kiem_app(at, "danh sách nguồn lỗi")


# ------------------------------------------------------------------ (3) hồ sơ khiếu nại .md

def test_e3_ho_so_md_thoat_tieu_de_video_vi_pham():
    ho_so = dossier.HoSo(tieu_de_vi_pham=TIEU_DE_DOC, link_vi_pham="https://youtu.be/x",
                         thoi_luong_hhmmss="00:10:00", ngay_lap="2026-10-25",
                         tong_giay_vi_pham=30, ty_le_video=5.0,
                         muc=[dossier.MucViPham(
                             ten_clip_goc="clip_a", tieu_de_goc="Clip A", link_goc="https://youtu.be/a",
                             tu_hhmmss="00:01:00", den_hhmmss="00:01:30",
                             link_moc="https://youtu.be/x?t=60", do_dai_giay=30, ty_le=90.0,
                             hashes=100)])
    md = dossier.render_markdown(ho_so)
    dong = [d for d in md.splitlines() if DAU in d]
    assert dong, "hồ sơ phải nêu tiêu đề video vi phạm"
    vi_pham = [(d, _loi_dien_giai(d)) for d in dong if _loi_dien_giai(d)]
    assert vi_pham == [], "file hồ sơ .md chứa tiêu đề ngoài chưa thoát:\n" + "\n".join(
        f"  {d!r}\n      -> {loi}" for d, loi in vi_pham)
