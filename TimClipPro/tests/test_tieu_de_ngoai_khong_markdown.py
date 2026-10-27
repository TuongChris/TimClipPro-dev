# -*- coding: utf-8 -*-
"""Audit D-8 (bản sao bộ tái hiện): tiêu đề video YouTube (dữ liệu NGOÀI, do người đăng lại đặt) không được diễn giải
Markdown/LaTeX trên màn hình quét và danh sách kết quả/lỗi.

Streamlit diễn giải Markdown (GitHub) + LaTeX trong ``st.markdown``, ``st.caption``, ``st.warning``,
``st.info``, ``st.error``, ``st.success``: ``[chữ](url)`` thành link bấm được, ``$...$`` thành công thức.
Màn đồng bộ kênh đã tránh bằng ``st.text`` (``ui_tien_do_dong_bo.ve_tien_do_dong_bo``: «tiêu đề video là dữ
liệu ngoài — không diễn giải markdown/LaTeX»). Bất biến kiểm ở đây: tiêu đề chỉ được tới phần tử diễn giải
Markdown khi ĐÃ thoát (``\\[``, ``\\$``), hoặc đi qua phần tử không diễn giải (``st.text``, ``st.code``).

Dữ liệu tổng hợp, không mạng, không dữ liệu thật.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path

import tien_do_quet as tdq
import ui_tien_do_quet as ui

APP_PY = Path(__file__).resolve().parents[1] / "app.py"

# Tiêu đề kiểu người đăng lại có thể đặt (tổng hợp).
TIEU_DE_DOC = "Tôi mất $500 rồi lại kiếm $5000 [Nhấn để nhận quà](https://evil.example) # Full"

# Phần tử Streamlit diễn giải Markdown/LaTeX.
PHAN_TU_MARKDOWN = {"markdown", "caption", "warning", "info", "error", "success", "write"}

_LINK_THO = re.compile(r"(?<!\\)\[[^\]]*(?<!\\)\]\(https://evil\.example\)")
_DOLLAR_THO = re.compile(r"(?<!\\)\$")


def _loi_dien_giai(chu: str) -> list:
    """Những mẩu sẽ bị Streamlit diễn giải: link Markdown chưa thoát, dấu ``$`` chưa thoát (LaTeX)."""
    loi = []
    if _LINK_THO.search(chu):
        loi.append("link Markdown thô [..](https://evil.example)")
    if _DOLLAR_THO.search(chu):
        loi.append("dấu $ chưa thoát (LaTeX)")
    return loi


# ------------------------------------------------------------------ hàm thuần: dòng chi tiết (→ st.markdown)

def _anh(tieu_de_so: str = "", message: str = ""):
    from scan_jobs import BatchSnapshot, VideoState
    v = VideoState(index=1, nguon="https://youtu.be/x", scan_status="running", phase="downloading",
                   title=TIEU_DE_DOC, message=message)
    td = tdq.AnhTienDo(batch_id="b", index=1, tong=1, tieu_de=tieu_de_so, giai_doan=tdq.GD_TAI,
                       giai_doan_luc=1.0, byte_da_nhan=1024 * 1024, byte_tong=4 * 1024 * 1024)
    anh = BatchSnapshot(batch_id="b", total=1, current_index=1, completed=0, failed=0, running=True,
                        cancelled=False, elapsed_seconds=5.0, eta_seconds=None, message="",
                        videos=(v,), tien_do=td, worker_alive=True)
    return anh, v


def test_dong_chi_tiet_khong_de_tieu_de_dien_giai_markdown():
    # dong_chi_tiet trả về «các dòng markdown» — app ghép rồi đưa thẳng vào st.markdown.
    anh, v = _anh(tieu_de_so=TIEU_DE_DOC)
    dong = "  \n".join(ui.dong_chi_tiet(anh, v, {}, 10.0))
    assert "Tôi mất" in dong, "tiêu đề vẫn phải hiện cho người dùng"
    assert _loi_dien_giai(dong) == [], f"st.markdown sẽ diễn giải tiêu đề ngoài: {dong!r}"


# ------------------------------------------------------------------ ve_tien_do_lo với st giả (ghi lại lệnh vẽ)

class _StGia:
    def __init__(self):
        self.goi = []

    def _ghi(self, ten):
        def f(*a, **k):
            chu = a[0] if a else k.get("body", k.get("text", ""))
            self.goi.append((ten, str(chu)))
            if ten == "columns":
                n = a[0] if isinstance(a[0], int) else len(a[0])
                return [self for _ in range(n)]
            if ten in ("container", "expander"):
                return contextlib.nullcontext()
            return None
        return f

    def __getattr__(self, ten):
        return self._ghi(ten)


def test_ve_tien_do_lo_khong_dua_tieu_de_tho_vao_phan_tu_markdown():
    # message thật của engine: f"{kq.source_name} ({hhmmss(...)}) — chuẩn bị tải audio..."
    anh, _ = _anh(tieu_de_so=TIEU_DE_DOC,
                  message=f"{TIEU_DE_DOC} (01:00:00) — chuẩn bị tải audio...")
    st = _StGia()
    ui.ve_tien_do_lo(st, anh, {}, lambda s: "00:00:00")
    co_tieu_de = [(ten, chu) for ten, chu in st.goi if "Tôi mất" in chu]
    assert co_tieu_de, "tiêu đề phải hiện ở đâu đó trên màn tiến độ"
    vi_pham = [(ten, chu, _loi_dien_giai(chu)) for ten, chu in co_tieu_de
               if ten in PHAN_TU_MARKDOWN and _loi_dien_giai(chu)]
    assert vi_pham == [], "tiêu đề ngoài đi vào phần tử diễn giải Markdown/LaTeX:\n" + "\n".join(
        f"  st.{t}: {c!r} -> {ly_do}" for t, c, ly_do in vi_pham)


# ------------------------------------------------------------------ Streamlit thật (AppTest): kết quả sau lượt

def _phan_tu_markdown(at) -> list:
    ra = []
    for ten, nhom in (("markdown", at.markdown), ("caption", at.caption), ("warning", at.warning),
                      ("info", at.info), ("error", at.error), ("success", at.success)):
        ra.extend((ten, str(i.value)) for i in nhom)
    return ra


def _chay_app(tmp_path, monkeypatch, job: dict, lan: str = "job"):
    """``lan``: ``job`` (làn chính) hoặc ``job_dong_bo`` (làn đồng bộ kênh chạy song song)."""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    at.session_state[lan].update(job)
    at.run()
    assert not at.exception, at.exception
    return at


def test_app_bao_cao_0_ket_qua_khong_dien_giai_tieu_de(tmp_path, monkeypatch):
    from engine import ScanResult
    kq = ScanResult(source_name=TIEU_DE_DOC, source_ref="https://youtu.be/x", source_id="x",
                    status="ok")
    at = _chay_app(tmp_path, monkeypatch, {"running": False, "results": [kq], "error": "",
                                           "kind": "scan", "da_day_sheet": True})
    co = [(t, c) for t, c in _phan_tu_markdown(at) if "Tôi mất" in c]
    assert co, "báo cáo 0 kết quả phải nêu tên video"
    vi_pham = [(t, c, _loi_dien_giai(c)) for t, c in co if _loi_dien_giai(c)]
    assert vi_pham == [], "tiêu đề ngoài vào phần tử Markdown:\n" + "\n".join(
        f"  st.{t}: {c!r} -> {ly_do}" for t, c, ly_do in vi_pham)


def test_app_danh_sach_loi_dong_bo_kenh_khong_dien_giai_tieu_de(tmp_path, monkeypatch):
    # channel.py: loi.append(f"{v.title[:40]}: {giai_thich_loi(...)}")
    tieu_de_40 = "Mất $5 [quà](https://evil.example) $9"
    r = {"trang_thai": "MOT_PHAN", "moi": 0, "bo_qua": 0, "so_loi": 1, "chua_thu": 0,
         "thu_muc": str(tmp_path / "kenh"), "loi": [f"{tieu_de_40}: Video không tải được"]}
    at = _chay_app(tmp_path, monkeypatch, {"running": False, "results": r, "error": "",
                                           "kind": "channel"}, lan="job_dong_bo")
    co = [(t, c) for t, c in _phan_tu_markdown(at) if "Mất" in c and "quà" in c]
    assert co, "danh sách video lỗi phải hiện tên video"
    vi_pham = [(t, c, _loi_dien_giai(c)) for t, c in co if _loi_dien_giai(c)]
    assert vi_pham == [], "tiêu đề ngoài vào phần tử Markdown:\n" + "\n".join(
        f"  st.{t}: {c!r} -> {ly_do}" for t, c, ly_do in vi_pham)


# ------------------------------------------------------------------ hàm thoát dùng chung (scan_ui.thoat_markdown)

def test_thoat_markdown_giu_chu_bo_cu_phap():
    from scan_ui import thoat_markdown
    ra = thoat_markdown(TIEU_DE_DOC + "\n# Tập 2 https://evil.example")
    assert _loi_dien_giai(ra) == []
    assert "\n" not in ra, "xuống dòng trong chữ ngoài không được mở khối Markdown mới"
    assert "https://" not in ra, "URL trần không được tự thành link (GFM)"
    # Bỏ dấu «\» thoát thì người dùng đọc lại đúng từng ký tự của tiêu đề.
    assert ra.replace("\\", "") == (TIEU_DE_DOC + " # Tập 2 https://evil.example")
    assert thoat_markdown(None) == "" and thoat_markdown("Tôi mất") == "Tôi mất"
