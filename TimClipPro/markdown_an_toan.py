# -*- coding: utf-8 -*-
"""Thoát chữ NGOÀI trước khi chèn vào Markdown — hàm thuần, không phụ thuộc Streamlit/engine.

Dùng chung cho giao diện (``scan_ui`` xuất lại, ``ui_tien_do_quet``, ``app``) và cho file hồ sơ khiếu nại
``.md`` (``dossier`` — engine nhập dossier nên hàm không thể nằm trong ``scan_ui``: vòng nhập
scan_ui → common_original → engine → dossier). Audit D-8 (màn quét/kết quả), E-3 (hồ sơ .md).
"""

from __future__ import annotations

from typing import Any

# Dấu câu ASCII — CommonMark cho phép thoát MỌI ký tự này bằng «\» (hiện ra đúng ký tự, không còn cú pháp).
_DAU_CAU_ASCII = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


def thoat_markdown(chu: Any) -> str:
    """Chữ NGOÀI (tiêu đề video YouTube, tên file, câu lỗi có tiêu đề) → chữ thường an toàn cho phần tử Streamlit
    diễn giải Markdown + LaTeX (``st.markdown/caption/info/warning/error/success``) — audit D-8 — và cho file
    hồ sơ ``.md`` (trình xem Markdown nào mở nó cũng diễn giải như vậy) — audit E-3.

    Tiêu đề do người đăng lại đặt: ``![](url)`` thành ảnh do trình duyệt/trình xem tự tải từ máy ngoài (lộ IP +
    giờ xem), ``[chữ](url)`` thành link bấm được trông như chữ của tool, ``$500 … $5000`` thành công thức LaTeX
    (mất chữ), ``# * _`` đổi định dạng dòng; URL trần cũng tự thành link (GFM). Thoát mọi dấu câu ASCII
    (``\\$`` cả cho LaTeX của Streamlit) — người dùng vẫn đọc đúng từng ký tự; xuống dòng gộp thành dấu cách để chữ
    ngoài không mở khối Markdown mới. Chỉ dùng cho HIỂN THỊ Markdown — CSV/Sheets/lịch sử vẫn nhận tiêu đề gốc.
    """
    chu = " ".join(str(chu or "").splitlines())
    return "".join("\\" + k if k in _DAU_CAU_ASCII else k for k in chu)
