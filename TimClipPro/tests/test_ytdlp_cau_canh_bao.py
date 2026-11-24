# -*- coding: utf-8 -*-
"""Câu cảnh báo của yt-dlp mà channel.py dựa vào vẫn còn trong bản yt-dlp đang cài (việc nhỏ #17).

``channel.py`` (đồng bộ kênh, hàm ``liet_ke`` khoảng dòng 952) chỉ biết danh sách video của kênh bị CẮT giữa chừng nhờ
cảnh báo «Incomplete data received»: yt-dlp hết lượt thử lật trang thì chỉ CẢNH BÁO rồi trả danh sách thiếu
(``yt_dlp/extractor/youtube/_base.py``, ``_extract_response``). yt-dlp đổi câu là danh sách thiếu bị coi là đủ — không
lỗi nào hiện ra. Test đọc mã nguồn .py của gói yt_dlp trong môi trường đang chạy: không import yt-dlp, không mạng.
"""
import importlib.util
import re
from pathlib import Path

CAU = "Incomplete data received"


def test_yt_dlp_dang_cai_van_bao_cau_danh_sach_bi_cat():
    assert CAU in (Path(__file__).resolve().parents[1] / "channel.py").read_text(encoding="utf-8"), (
        "channel.py không còn dựa vào câu này — sửa hoặc bỏ test này cho khớp.")
    spec = importlib.util.find_spec("yt_dlp")
    assert spec and spec.origin, "môi trường test không có gói yt_dlp"
    goc = Path(spec.origin).parent
    phien_ban = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", (goc / "version.py").read_text(encoding="utf-8"))
    loi = re.compile(r"ExtractorError\(\s*['\"]" + re.escape(CAU) + r"['\"]")
    co = [p.relative_to(goc).as_posix() for p in goc.rglob("*.py")
          if "youtube" in p.relative_to(goc).as_posix() and loi.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert co, (
        f"yt-dlp {phien_ban.group(1) if phien_ban else '(không rõ bản)'} đang cài không còn ExtractorError('{CAU}') "
        "ở extractor YouTube: channel.py sẽ không còn nhận ra danh sách kênh bị cắt khi lật trang (danh sách thiếu bị "
        "coi là đủ). Xem lại channel.py (hàm liet_ke, điều kiện «Incomplete data received»): tìm câu cảnh báo mới trong "
        "yt_dlp/extractor/youtube/_base.py (_extract_response) rồi sửa điều kiện và test test_truy_cap_youtube_kenh.")
