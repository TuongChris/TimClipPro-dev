# -*- coding: utf-8 -*-
"""Audit E-7: file Git ĐANG theo dõi phải khớp luật của repo công khai.

Luật ``.gitignore`` KHÔNG áp cho file đã track, nên một file lọt vào trước khi có luật sẽ ở lại mãi
mà không ai thấy. ``docs/ai/GIT_WORKFLOW.md`` cấm «đường dẫn riêng máy, tên người dùng Windows»
(câu quét bí mật của nó có ``[A-Z]:\\\\Users\\\\``) — ba tài liệu cũ từng mang ``C:\\Users\\Admin…``.

Chỉ đọc cây Git của mã đang thử (``git ls-files``); không sửa, không mạng. Không có git/không phải
repo (vd. cây mã trong gói phát hành) -> bỏ qua.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess

import pytest

GOC_MA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../TimClipPro

# Đã biết, CHỜ chủ dự án quyết (AUD-229/AUD-274; docs/AUDIT_REPORT.md: «Quyết định untrack
# `session.log` vẫn để chủ sở hữu duyệt»). Untrack rồi thì xoá khỏi đây — test dưới nhắc.
TRACK_TRUNG_IGNORE_DA_BIET = {"TimClipPro/session.log"}

# X:\Users\<tên thật>; chỗ giữ chỗ «<tên>» / «...» / «…» được phép.
RE_USERS = re.compile(r"\b[A-Z]:\\{1,2}Users\\{1,2}(?![<.…])[^\\\s`'\"]+")


def _env_git():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # Cô lập khỏi cấu hình toàn cục/hệ thống của máy (core.excludesFile...).
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _git(*tham_so: str) -> str:
    return subprocess.run(["git", "-C", GOC_REPO, *tham_so], capture_output=True, env=_env_git(),
                          check=True).stdout.decode("utf-8")


def _goc_repo():
    if not shutil.which("git"):
        return None
    kq = subprocess.run(["git", "-C", GOC_MA, "rev-parse", "--show-toplevel"], capture_output=True,
                        text=True, env=_env_git())
    return kq.stdout.strip() if kq.returncode == 0 else None


GOC_REPO = _goc_repo()
pytestmark = pytest.mark.skipif(GOC_REPO is None, reason="cây mã không nằm trong repo git")


def _track_trung_ignore():
    # Chỉ luật .gitignore DÙNG CHUNG (bỏ .git/info/exclude riêng máy).
    ra = _git("ls-files", "-z", "-i", "-c", "--exclude-per-directory=.gitignore")
    return {d for d in ra.split("\0") if d}


def test_khong_file_track_moi_nao_trung_luat_ignore():
    moi = sorted(_track_trung_ignore() - TRACK_TRUNG_IGNORE_DA_BIET)
    assert moi == [], f"file đang track trùng luật .gitignore (luật không còn bảo vệ): {moi}"


def test_danh_sach_da_biet_con_dung():
    het = sorted(TRACK_TRUNG_IGNORE_DA_BIET - _track_trung_ignore())
    assert het == [], f"đã untrack/không còn trùng luật — xoá khỏi TRACK_TRUNG_IGNORE_DA_BIET: {het}"


def test_file_track_khong_mang_thu_muc_nguoi_dung_windows():
    lo = []
    for duong in _git("ls-files", "-z").split("\0"):
        # tests/: dữ liệu giả có chủ đích; audfprint-master: mã bên thứ ba.
        if not duong or "audfprint-master/" in duong or "/tests/" in duong:
            continue
        try:
            with open(os.path.join(GOC_REPO, duong), encoding="utf-8") as f:
                noi_dung = f.read()
        except (UnicodeDecodeError, OSError):
            continue
        for so, dong in enumerate(noi_dung.splitlines(), 1):
            gap = RE_USERS.search(dong)
            if gap:
                lo.append(f"{duong}:{so}: {gap.group(0)}")
    assert lo == [], "file track mang thư mục người dùng Windows:\n" + "\n".join(lo)
