# -*- coding: utf-8 -*-
"""Hook ``pre-push`` dùng chung PC1/PC2 (``release/git-hooks/pre-push``, docs/ai/GIT_WORKFLOW.md): thử thật bằng git
trên repo TẠM (remote bare cục bộ) — cho nhánh việc, cho integration/current CHỈ fast-forward tới đầu một nhánh việc
đã đẩy; chặn tag, xoá, force-push, nhánh lạ, tạo mới integration/current. Không mạng."""
import os
import shutil
import subprocess

import pytest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "release", "git-hooks", "pre-push")

pytestmark = pytest.mark.skipif(not (shutil.which("git") and os.path.isfile(HOOK)), reason="cần git + hook trong repo")


def _git(cwd, *a, ok=True):
    r = subprocess.run(["git", "-c", "user.name=thu", "-c", "user.email=thu@vi-du.invalid", "-c", "commit.gpgsign=false",
                        "-c", "init.defaultBranch=integration/current", *a], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if ok and r.returncode != 0:
        raise AssertionError(f"git {a}: {r.stderr}")
    return r


def _commit(cwd, ten):
    with open(os.path.join(cwd, ten), "w", encoding="utf-8") as f:
        f.write(ten)
    _git(cwd, "add", ten)
    _git(cwd, "commit", "-q", "-m", ten)
    return _git(cwd, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture()
def may(tmp_path):
    remote = str(tmp_path / "remote.git")
    _git(str(tmp_path), "init", "-q", "--bare", remote)
    goc = str(tmp_path / "goc")
    _git(str(tmp_path), "clone", "-q", remote, goc)
    _commit(goc, "dau.txt")
    _git(goc, "push", "-q", "origin", "HEAD:refs/heads/integration/current")      # trước khi cài hook
    clone = str(tmp_path / "may")
    _git(str(tmp_path), "clone", "-q", "--origin", "private", "--branch", "integration/current", remote, clone)
    hooks = os.path.join(clone, ".git", "hooks")
    os.makedirs(hooks, exist_ok=True)
    shutil.copyfile(HOOK, os.path.join(hooks, "pre-push"))
    return clone


def _day(clone, *ref):
    r = _git(clone, "-c", f"core.hooksPath={os.path.join(clone, '.git', 'hooks')}", "push", "private", *ref, ok=False)
    return r.returncode, r.stdout + r.stderr


def test_hook_luu_lf_bat_dau_bang_shebang():
    b = open(HOOK, "rb").read()
    assert b.startswith(b"#!/bin/sh\n") and b"\r" not in b and not b.startswith(b"\xef\xbb\xbf")


def test_cho_nhanh_viec_hai_may(may):
    _git(may, "switch", "-q", "-c", "feature/pc2/a")
    _commit(may, "a.txt")
    assert _day(may, "feature/pc2/a:feature/pc2/a")[0] == 0
    _git(may, "switch", "-q", "-c", "fix/pc1/b")
    _commit(may, "b.txt")
    assert _day(may, "fix/pc1/b:fix/pc1/b")[0] == 0


@pytest.mark.parametrize("ref", ["HEAD:refs/heads/main", "HEAD:refs/heads/feature/khac/x", "HEAD:refs/tags/stable-9.9.9",
                                 "HEAD:refs/tags/v1"])
def test_chan_nhanh_la_va_moi_tag(may, ref):
    _commit(may, "x.txt")
    rc, o = _day(may, ref)
    assert rc != 0 and "pre-push: CHẶN" in o


def test_chan_xoa_va_force_push(may):
    _git(may, "switch", "-q", "-c", "feature/pc1/c")
    _commit(may, "c.txt")
    assert _day(may, "feature/pc1/c:feature/pc1/c")[0] == 0
    rc, o = _day(may, ":refs/heads/feature/pc1/c")
    assert rc != 0 and "CHẶN xoá" in o
    _git(may, "reset", "-q", "--hard", "HEAD~1")
    _commit(may, "c2.txt")
    rc, o = _day(may, "+feature/pc1/c:feature/pc1/c")
    assert rc != 0 and "CHẶN force-push" in o


def test_integration_current_chi_fast_forward_toi_dau_nhanh_viec_da_day(may):
    _git(may, "switch", "-q", "-c", "feature/pc2/d")
    dau = _commit(may, "d.txt")
    rc, o = _day(may, f"{dau}:refs/heads/integration/current")
    assert rc != 0 and "không phải ĐẦU một nhánh việc" in o                # chưa đẩy nhánh việc
    assert _day(may, "feature/pc2/d:feature/pc2/d")[0] == 0
    _git(may, "fetch", "-q", "private")
    giua = _commit(may, "d2.txt")                                          # commit chưa đẩy → không phải đầu nhánh
    rc, o = _day(may, f"{giua}:refs/heads/integration/current")
    assert rc != 0 and "không phải ĐẦU" in o
    assert _day(may, f"{dau}:refs/heads/integration/current")[0] == 0     # đúng đầu nhánh đã đẩy → cho
    _git(may, "switch", "-q", "--detach", "private/integration/current")
    _git(may, "switch", "-q", "-c", "feature/pc2/e", "HEAD~1")
    lech = _commit(may, "e.txt")
    assert _day(may, "feature/pc2/e:feature/pc2/e")[0] == 0
    _git(may, "fetch", "-q", "private")
    rc, o = _day(may, f"+{lech}:refs/heads/integration/current")         # không fast-forward
    assert rc != 0 and "CHẶN force-push" in o


def test_chan_tao_moi_integration_current(may, tmp_path):
    remote2 = str(tmp_path / "rong.git")
    _git(str(tmp_path), "init", "-q", "--bare", remote2)
    _git(may, "remote", "add", "rong", remote2)
    r = _git(may, "-c", f"core.hooksPath={os.path.join(may, '.git', 'hooks')}", "push", "rong",
             "HEAD:refs/heads/integration/current", ok=False)
    assert r.returncode != 0 and "CHẶN tạo mới integration/current" in r.stdout + r.stderr
