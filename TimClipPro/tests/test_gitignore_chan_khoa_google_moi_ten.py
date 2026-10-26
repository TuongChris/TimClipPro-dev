# -*- coding: utf-8 -*-
"""Audit E-1: .gitignore dùng chung chỉ chặn đúng tên `google_key.json`.

Repo TimClipPro-dev là PUBLIC. Ở chế độ legacy/Development, khoá Google mặc định nằm CẠNH MÃ
(`runtime_paths.khoa_google_mac_dinh` = <thư mục mã>/google_key.json); hướng dẫn trong `sheets.py`
bảo người dùng tải file JSON của service account (Google đặt tên `<project>-<12 hex>.json`) vào thư
mục TimClipPro rồi tự đổi tên; ô đường dẫn ở `ui_gui_sheets._ve_khoa` nhận đường dẫn bất kỳ. Vì vậy
các biến thể (khoá thứ hai, bản .bak, file chưa đổi tên, cookie ở gốc repo...) có thể nằm trong cây
làm việc. `git add -A` không được đưa chúng vào lịch sử.

Test dựng một repo git TẠM, chép đúng hai file `.gitignore` dùng chung của commit đang kiểm (KHÔNG có
`.git/info/exclude` riêng máy, KHÔNG có cấu hình git toàn cục) — đúng tình huống của PC1, clone mới,
worktree khác. Dữ liệu khoá là GIẢ.
"""
import fnmatch
import json
import os
import shutil
import subprocess

import pytest

_TESTS = os.path.dirname(os.path.abspath(__file__))
_MA = os.path.dirname(_TESTS)                 # TimClipPro/
_REPO = os.path.dirname(_MA)                  # gốc repo

_KHOA_GIA = json.dumps({
    "type": "service_account",                                                    # gia-khong-bi-mat
    "project_id": "du-an-gia",
    "client_email": "x@y.iam.gserviceaccount.com",                                # gia-khong-bi-mat
    "private_key": "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n",  # gia-khong-bi-mat
})
_COOKIE_GIA = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tGIA\n"

# Đường dẫn bí mật thực tế có thể xuất hiện trong cây làm việc.
BIEN_THE_BI_MAT = [
    "TimClipPro/google_key_client02.json",            # khoá thứ hai (ca thật trên PC2)
    "TimClipPro/google_key.json.bak",                  # bản sao lưu tay
    "TimClipPro/khoa_google.json",                     # tên tiếng Việt
    "TimClipPro/service_account.json",
    "TimClipPro/my-project-123456-a1b2c3d4e5f6.json",  # file tải về từ Google, chưa đổi tên
    "google_key.json",                                 # khoá ở gốc repo
    "release/google_key.json",
    "cookies.txt",                                     # cookie ở gốc repo
    "docs/cookies.txt",
]


def _git_env():
    env = dict(os.environ)
    # Cô lập khỏi cấu hình toàn cục/hệ thống của máy (core.excludesFile...).
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        env.pop(k, None)
    return env


def _git(goc, *args):
    return subprocess.run(["git", "-C", str(goc), *args], capture_output=True, text=True,
                          env=_git_env())


@pytest.fixture
def repo_tam(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("máy không có git")
    if not os.path.isfile(os.path.join(_REPO, ".gitignore")):
        pytest.skip("không chạy trong repo (bản sao chỉ có cây TimClipPro/)")
    goc = tmp_path / "repo"
    goc.mkdir()
    r = _git(goc, "init", "-q")
    assert r.returncode == 0, r.stderr
    # info/exclude do git init sinh ra chỉ có chú thích; làm rỗng hẳn để chắc chắn.
    (goc / ".git" / "info").mkdir(exist_ok=True)
    (goc / ".git" / "info" / "exclude").write_text("", encoding="utf-8")
    (goc / "TimClipPro").mkdir()
    shutil.copyfile(os.path.join(_REPO, ".gitignore"), goc / ".gitignore")
    shutil.copyfile(os.path.join(_MA, ".gitignore"), goc / "TimClipPro" / ".gitignore")
    return goc


def _ghi_bi_mat(goc, rel):
    p = goc / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_COOKIE_GIA if rel.endswith(".txt") else _KHOA_GIA, encoding="utf-8")
    return p


def test_doi_chung_bo_tri_dung(repo_tam):
    """Đối chứng: thiết lập đọc đúng luật — tên chuẩn bị chặn, mã nguồn thường KHÔNG bị chặn."""
    _ghi_bi_mat(repo_tam, "TimClipPro/google_key.json")
    _ghi_bi_mat(repo_tam, "TimClipPro/cookies.txt")
    (repo_tam / "TimClipPro" / "engine_moi.py").write_text("x = 1\n", encoding="utf-8")
    assert _git(repo_tam, "check-ignore", "-q", "TimClipPro/google_key.json").returncode == 0
    assert _git(repo_tam, "check-ignore", "-q", "TimClipPro/cookies.txt").returncode == 0
    assert _git(repo_tam, "check-ignore", "-q", "TimClipPro/engine_moi.py").returncode == 1


@pytest.mark.parametrize("rel", BIEN_THE_BI_MAT)
def test_git_add_khong_dua_khoa_hay_cookie_vao_repo(repo_tam, rel):
    _ghi_bi_mat(repo_tam, rel)
    ci = _git(repo_tam, "check-ignore", "-v", rel)
    assert ci.returncode in (0, 1), ci.stderr          # 128 = lỗi thiết lập, không phải khuyết tật
    _git(repo_tam, "add", "-A")
    da_dua_vao = [d[3:] for d in _git(repo_tam, "status", "--porcelain").stdout.splitlines()
                  if not d[3:].endswith(".gitignore")]
    assert ci.returncode == 0 and not da_dua_vao, (
        f"{rel}: .gitignore dùng chung KHÔNG chặn; `git add -A` đưa vào index: {da_dua_vao}")


@pytest.mark.xfail(strict=True, reason=(
    "`.claude/settings.json` là cấu hình QUYỀN của Claude: chỉ sửa khi người dùng duyệt rõ (đề xuất "
    "thêm `Read(**/google_key*)`). Luật chặn đọc không đưa gì lên Git — lớp chặn công khai là .gitignore."))
@pytest.mark.parametrize("ten", ["google_key_client02.json", "google_key.json.bak"])
def test_claude_settings_chan_doc_bien_the_khoa_google(ten):
    """Luật chặn Read của Claude cũng chỉ khớp đúng tên `google_key.json`."""
    with open(os.path.join(_REPO, ".claude", "settings.json"), encoding="utf-8") as f:
        deny = json.load(f)["permissions"]["deny"]
    mau_doc = [m[len("Read(**/"):-1] for m in deny if m.startswith("Read(**/")]
    assert any(fnmatch.fnmatchcase(ten, m) for m in mau_doc), (
        f"không luật Read(**/...) nào chặn {ten}; có: {mau_doc}")
