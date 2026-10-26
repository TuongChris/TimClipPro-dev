# -*- coding: utf-8 -*-
"""Audit E-5: bản dẫn xuất của watchlist (dữ liệu khách hàng = link vi phạm) sinh ra
NGAY CẠNH mã nguồn phải bị .gitignore chặn, để `git add -A` không đưa chúng lên repo.

Nguồn sinh file (đều ghi theo thư mục hiện hành / cạnh file gốc): `chia_watchlist.py --so-may N`
(TRIEN_KHAI_MAY_PHU.md) -> watchlist.<tiền tố>N.json; `luu_tru.ghi_json_an_toan` -> <file>.bak và
<file>.<pid>.<hex>.tmp mồ côi; `luu_tru.doc_json_an_toan` -> <file>.hong.<giờ>; `cli.py youtube
--file links.txt`. Repo TimClipPro-dev là PUBLIC.

Dữ liệu hoàn toàn synthetic (ID video giả). Repo git tạm trong tmp_path, chép đúng hai
file .gitignore của cây mã đang kiểm (gốc repo + TimClipPro/); cô lập khỏi cấu hình git
toàn cục/hệ thống và `.git/info/exclude` riêng máy. Không mạng.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

import chia_watchlist
import watch
from luu_tru import LoiDuLieu

GOC_MA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../TimClipPro
GOC_REPO = os.path.dirname(GOC_MA)

WATCHLIST_GIA = {
    "kho": "KHO_GIA",
    "gioi_han_moi_lan": 5,
    "muc": [
        {"loai": "link", "url": "https://youtu.be/AAAAAAAAAAA", "ghi_chu": "gia 1", "bat": True},
        {"loai": "link", "url": "https://youtu.be/BBBBBBBBBBB", "ghi_chu": "gia 2", "bat": True},
    ],
}


def _env_git():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # Cô lập khỏi cấu hình toàn cục/hệ thống của máy (core.excludesFile...).
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _git(repo, *args):
    try:
        return subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=repo,
                              capture_output=True, text=True, encoding="utf-8",
                              env=_env_git())
    except FileNotFoundError:
        pytest.skip("máy không có git")


@pytest.fixture
def repo_gia(tmp_path, monkeypatch):
    """Repo git tạm có đúng hai .gitignore của cây mã; cwd = repo/TimClipPro."""
    if not os.path.isfile(os.path.join(GOC_REPO, ".gitignore")):
        pytest.skip("không chạy trong repo (bản sao chỉ có cây TimClipPro/)")
    repo = tmp_path / "repo"
    ma = repo / "TimClipPro"
    ma.mkdir(parents=True)
    r = _git(repo, "init", "-q")
    assert r.returncode == 0, r.stderr
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "exclude").write_text("", encoding="utf-8")
    shutil.copyfile(os.path.join(GOC_REPO, ".gitignore"), repo / ".gitignore")
    shutil.copyfile(os.path.join(GOC_MA, ".gitignore"), ma / ".gitignore")
    monkeypatch.chdir(ma)
    return repo, ma


def _file_lo(repo):
    """File chưa track mà `git add -A` sẽ đưa vào (bỏ hai .gitignore)."""
    r = _git(repo, "ls-files", "--others", "--exclude-standard")
    assert r.returncode == 0, r.stderr
    return sorted(d for d in r.stdout.splitlines()
                  if d and os.path.basename(d) != ".gitignore")


def test_chia_watchlist_khong_de_lo_file_ra(repo_gia, monkeypatch, capsys):
    """Lệnh tài liệu ghi (TRIEN_KHAI_MAY_PHU.md): chia_watchlist.py --so-may N --that-su."""
    repo, ma = repo_gia
    (ma / "watchlist.json").write_text(json.dumps(WATCHLIST_GIA), encoding="utf-8")
    assert _file_lo(repo) == []          # chính watchlist.json đã được chặn

    monkeypatch.setattr(sys, "argv", ["chia_watchlist.py", "--so-may", "2", "--that-su"])
    assert chia_watchlist.main() == 0
    assert (ma / "watchlist.may1.json").is_file()
    assert (ma / "watchlist.may2.json").is_file()

    lo = _file_lo(repo)
    assert lo == [], f"git add -A sẽ đưa watchlist thật lên repo: {lo}"


def test_ban_sao_va_ban_hong_cua_watchlist_bi_chan(repo_gia):
    """ghi_watchlist tạo .bak; watchlist hỏng bị đổi tên thành .hong.<giờ> cạnh mã."""
    repo, ma = repo_gia
    duong = str(ma / "watchlist.json")
    wl = watch.doc_watchlist(duong)            # chưa có file -> rỗng
    wl.muc = [watch.MucTheoDoi(loai="link", url=m["url"], ghi_chu=m["ghi_chu"])
              for m in WATCHLIST_GIA["muc"]]
    watch.ghi_watchlist(wl, duong)
    watch.ghi_watchlist(wl, duong)             # lần 2 -> làm mới watchlist.json.bak
    assert (ma / "watchlist.json.bak").is_file()

    # Hỏng khi có .bak -> phục hồi, bản hỏng giữ ở watchlist.json.hong.<giờ>
    (ma / "watchlist.json").write_text("{hong", encoding="utf-8")
    assert len(watch.doc_watchlist(duong).muc) == 2

    # Hỏng khi không còn .bak -> LoiDuLieu, bản hỏng (vẫn chứa link) giữ lại
    os.remove(ma / "watchlist.json.bak")
    (ma / "watchlist.json").write_text(
        '{"muc": [{"loai": "link", "url": "https://youtu.be/CCCCCCCCCCC"', encoding="utf-8")
    with pytest.raises(LoiDuLieu):
        watch.doc_watchlist(duong)
    watch.ghi_watchlist(wl, duong)
    watch.ghi_watchlist(wl, duong)

    hong = [t for t in os.listdir(ma) if ".hong." in t]
    assert len(hong) >= 2, os.listdir(ma)
    lo = _file_lo(repo)
    assert lo == [], f"git add -A sẽ đưa bản sao/bản hỏng của watchlist lên repo: {lo}"


@pytest.mark.parametrize("ten", [
    "links.txt",                                   # cli.py: «--file links.txt»
    "watchlist.may2.json",                         # ChayMayPhu.bat watchlist.may2.json
    "watchlist.json.bak",
    "watchlist.json.hong.20261025_120000",
    "watchlist.json.1234.abcd1234.tmp",            # writer chết giữa chừng
])
def test_ten_file_du_lieu_watchlist_bi_gitignore_chan(repo_gia, ten):
    repo, ma = repo_gia
    (ma / ten).write_text("https://youtu.be/AAAAAAAAAAA\n", encoding="utf-8")
    r = _git(repo, "check-ignore", "-q", f"TimClipPro/{ten}")
    assert r.returncode == 0, f"TimClipPro/{ten} chưa được .gitignore chặn"


def test_doi_chung_ban_mau_va_ma_nguon_van_duoc_theo_doi(repo_gia):
    """Đối chứng: luật mới không được chặn bản mẫu watchlist hay mã nguồn chia_watchlist.py."""
    repo, ma = repo_gia
    for ten in ("watchlist.example.json", "chia_watchlist.py", "requirements-lock.txt"):
        (ma / ten).write_text("{}\n", encoding="utf-8")
        r = _git(repo, "check-ignore", "-q", f"TimClipPro/{ten}")
        assert r.returncode == 1, f"TimClipPro/{ten} bị .gitignore chặn nhầm (mã {r.returncode})"
