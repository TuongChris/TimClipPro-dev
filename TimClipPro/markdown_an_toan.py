# -*- coding: utf-8 -*-
"""Thoát chữ NGOÀI trước khi chèn vào Markdown — hàm thuần, không phụ thuộc Streamlit/engine.

Dùng chung cho giao diện (``scan_ui`` xuất lại, ``ui_tien_do_quet``, ``app``) và cho file hồ sơ khiếu nại
``.md`` (``dossier`` — engine nhập dossier nên hàm không thể nằm trong ``scan_ui``: vòng nhập
scan_ui → common_original → engine → dossier). Audit D-8 (màn quét/kết quả), E-3 (hồ sơ .md).
"""

from __future__ import annotations

import re
from typing import Any

# Dấu câu ASCII — CommonMark cho phép thoát MỌI ký tự này bằng «\» (hiện ra đúng ký tự, không còn cú pháp).
_DAU_CAU_ASCII = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")

# Hồ sơ .md (FILE trên đĩa): chỉ ký tự mở cú pháp Markdown/GFM/LaTeX ở GIỮA dòng — chữ ngoài luôn đứng sau
# «- **Nhãn:** », nên cú pháp đầu dòng («#» tiêu đề, «>», «-»/«+»/«1.» danh sách) không áp dụng. «[ ]» chặn link
# và ảnh («![» không còn «[» để mở), «< >» chặn thẻ HTML + autolink «<url>», «* _ ~ `» chặn nhấn mạnh/gạch/mã,
# «$» chặn công thức, «\» để chữ ngoài không tự thoát ký tự kế tiếp.
_CU_PHAP_GIUA_DONG = frozenset("\\`*_~[]<>$")
# URL trần (GFM extended autolink chỉ dựng link khi thấy «scheme://» hoặc «www.»).
_URL_TRAN = re.compile(r"(?i)\b(https?|ftp)(:)(?=//)|\b(www)(\.)")


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


def thoat_markdown_ho_so(chu: Any) -> str:
    """Chữ NGOÀI → chữ an toàn trong FILE hồ sơ khiếu nại ``.md`` (audit E-3; review audit đợt 2).

    Hồ sơ là file trên đĩa: người dùng mở bằng Notepad và chép tiêu đề vào form khiếu nại YouTube, nên KHÔNG thoát
    mọi dấu câu như ``thoat_markdown`` (phần tử Streamlit) — «Jeffy's Big Day - Part 2!» phải còn nguyên văn. Chỉ
    thoát ký tự mở cú pháp giữa dòng (``_CU_PHAP_GIUA_DONG``), trừ «_» nằm giữa hai chữ/số (CommonMark không mở nhấn
    mạnh ở đó: tên file ``video_thu_2h`` giữ nguyên), và phá URL trần («https\\://», «www\\.»). Trình xem Markdown
    hiện lại đúng từng ký tự; ảnh, link, HTML, công thức không còn. Xuống dòng gộp thành dấu cách như ``thoat_markdown``.
    """
    chu = " ".join(str(chu or "").splitlines())
    ra = []
    for i, k in enumerate(chu):
        giua_chu = k == "_" and 0 < i < len(chu) - 1 and chu[i - 1].isalnum() and chu[i + 1].isalnum()
        ra.append("\\" + k if k in _CU_PHAP_GIUA_DONG and not giua_chu else k)
    return _URL_TRAN.sub(lambda m: (m.group(1) or m.group(3)) + "\\" + (m.group(2) or m.group(4)), "".join(ra))
