# -*- coding: utf-8 -*-
"""Cứng hoá ĐƯỜNG CŨ (máy legacy, PC1) trước khi có bản Stable managed (brief §15, H10/H15/H16):

* updater cũ (`cap_nhat.py`) chỉ xét tag ``v<số>`` (so theo SỐ) — tag ``stable-…`` của kênh managed, RC,
  "latest" không bao giờ bị nó chọn; máy dev (dấu ``data/dev_mode`` hoặc ``TIMCLIP_DEV_MODE=1``) không tự
  cập nhật; bản cài managed từ chối updater cũ (cập nhật bằng launcher);
* ``.bat``: mã 11 (đổi bản + cần cài lại thư viện) — sau ``pip`` vẫn khởi động lại / bỏ lượt như tài liệu
  (trước đây ``pip`` thành công xoá ERRORLEVEL nên ``if errorlevel 10`` không chạy);
* ``kiemtra.bat`` chạy AppTest trên thư mục dữ liệu TẠM (trước đây trên ``data/`` thật — có thể nâng cấp
  lịch sử thật và khởi động người gửi Sheets thật).
"""
import os
import re

import pytest

import cap_nhat

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git_gia(tags):
    def git(lenh, repo, timeout=None):
        if lenh[:1] == ["tag"]:
            return True, "\n".join(tags)
        raise AssertionError(f"không được gọi git {lenh}")
    return git


def test_ban_moi_nhat_chi_xet_tag_v_so_va_so_theo_so(monkeypatch):
    monkeypatch.setattr(cap_nhat, "_git", _git_gia(
        ["stable-9.9.9", "v2.10", "v2.9", "v3.0-rc1", "latest", "v10", "vx", "v2.6"]))
    assert cap_nhat.ban_moi_nhat("repo") == "v10"
    monkeypatch.setattr(cap_nhat, "_git", _git_gia(["stable-1.0.0", "v3.0-rc1", "latest"]))
    assert cap_nhat.ban_moi_nhat("repo") == ""


def _cam_git(*a, **k):
    raise AssertionError("updater cũ không được chạy git trong trường hợp này")


def _repo_that(tmp_path):
    """Repo git THẬT, cục bộ (không remote, không mạng): ``Tool_Quet/TimClipPro/app.py``, một commit."""
    import subprocess

    goc = tmp_path / "Tool_Quet" / "TimClipPro"
    goc.mkdir(parents=True)
    (goc / "app.py").write_text("# app\n", encoding="utf-8")
    repo = str(tmp_path / "Tool_Quet")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.invalid"}

    def git(*a):
        subprocess.run(["git", "-C", repo, *a], check=True, env=env, capture_output=True)

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "ban dau")
    return goc, git


def test_cung_commit_co_ca_tag_v_va_stable_khong_cap_nhat_gia(tmp_path, monkeypatch):
    """Rà soát M3+M4 (P2-G): commit mang CẢ ``v2.7`` và ``stable-1.0.0`` (đều tag nhẹ — ``gh release create``
    tạo tag nhẹ) → ``git describe`` trả ``stable-1.0.0`` → so TÊN thấy khác ``v2.7`` → «cập nhật» lặp mỗi lần
    chạy (checkout không đổi gì, mã 10: ChayMayPhu.bat bỏ mọi lượt Watch). Nay so theo tag ``v<số>`` + commit."""
    goc, git = _repo_that(tmp_path)
    git("tag", "v2.7")
    git("tag", "stable-1.0.0")
    monkeypatch.setattr(cap_nhat, "lay_tag_moi", lambda repo: (True, ""))      # không mạng
    for bien in ("TIMCLIP_DEV_MODE", "TIMCLIP_RUNTIME_MODE", "TIMCLIP_DATA_DIR"):
        monkeypatch.delenv(bien, raising=False)
    assert cap_nhat.ban_hien_tai(os.path.dirname(str(goc))) == "v2.7"
    kq = cap_nhat.cap_nhat(goc=str(goc))
    assert not kq.ok and cap_nhat.ma_thoat(kq) == 0
    assert any("mới nhất" in x for x in kq.thong_bao), kq.thong_bao


def test_may_dev_co_dau_dev_mode_khong_tu_cap_nhat(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "dev_mode").write_text("", encoding="utf-8")
    monkeypatch.setattr(cap_nhat, "_git", _cam_git)
    monkeypatch.delenv("TIMCLIP_DEV_MODE", raising=False)
    kq = cap_nhat.cap_nhat(goc=str(tmp_path))
    assert not kq.ok and any("máy phát triển" in x for x in kq.thong_bao)
    assert cap_nhat.ma_thoat(kq) == 0


def test_bien_moi_truong_dev_mode_cung_tat_updater(tmp_path, monkeypatch):
    monkeypatch.setattr(cap_nhat, "_git", _cam_git)
    monkeypatch.setenv("TIMCLIP_DEV_MODE", "1")
    kq = cap_nhat.cap_nhat(goc=str(tmp_path))
    assert not kq.ok and any("máy phát triển" in x for x in kq.thong_bao)


@pytest.mark.parametrize("cach", ["dau_release", "bien_managed"])
def test_ban_cai_managed_tu_choi_updater_cu(tmp_path, monkeypatch, cach):
    ma = tmp_path / "releases" / "1.0.0" / "TimClipPro"
    ma.mkdir(parents=True)
    monkeypatch.setattr(cap_nhat, "_git", _cam_git)
    monkeypatch.delenv("TIMCLIP_DEV_MODE", raising=False)
    if cach == "dau_release":
        (ma.parent / "MANAGED_RELEASE.json").write_text("{}", encoding="utf-8")
    else:
        monkeypatch.setenv("TIMCLIP_RUNTIME_MODE", "managed")
    kq = cap_nhat.cap_nhat(goc=str(ma))
    assert not kq.ok and any("launcher" in x for x in kq.thong_bao)


def _dong(ten):
    with open(os.path.join(GOC, ten), encoding="utf-8", errors="replace") as f:
        return [x.strip() for x in f.read().splitlines()]


@pytest.mark.parametrize("ten", ["ChayTool.bat", "ChayMayPhu.bat"])
def test_bat_ma_11_khong_bi_pip_xoa_errorlevel(ten):
    """Chuỗi cập nhật nằm TRỌN trong một khối ngoặc (cmd nạp cả khối vào bộ nhớ trước khi chạy — updater
    đổi chính file .bat giữa chừng không làm cmd đọc nhầm byte của file mới). Trong khối: mã ≥ 10 rồi mới
    xét mã 11 → pip → pip lỗi thì dừng; sau đó LUÔN tới hành động của mã 10 (không kiểm errorlevel của pip
    như thể nó là mã của updater — lỗi H15 cũ)."""
    d = _dong(ten)
    i = next(i for i, x in enumerate(d) if re.search(r"cap_nhat\.py\s*$", x) and x.startswith("%PY%"))
    sau_rem = [x for x in d[:i] if not x.upper().startswith("REM")]
    do_sau = sum(1 for x in sau_rem if x.endswith("(")) - sum(1 for x in sau_rem if x == ")")
    assert do_sau >= 1, "lệnh updater phải nằm trong một khối ( … )"
    assert d[i + 1].lower() == "if errorlevel 10 (" and d[i + 2].lower() == "if errorlevel 11 ("
    assert "pip install" in d[i + 3] and d[i + 4].lower() == "if errorlevel 1 ("
    khoi = d[i + 5:i + 14]
    assert any(x.lower().startswith("exit /b 1") for x in khoi)
    assert any(x.lower().startswith("exit /b 0") for x in khoi)


def test_kiemtra_bat_chay_apptest_tren_du_lieu_tam():
    d = _dong("kiemtra.bat")
    k = next(i for i, x in enumerate(d) if "AppTest.from_file" in x and not x.upper().startswith("REM"))
    truoc = "\n".join(d[:k])
    assert re.search(r'set "KIEMTRA_TAM=%TEMP%\\[^"]+"', truoc)
    assert re.search(r'set "TIMCLIP_DATA_DIR=%KIEMTRA_TAM%\\data"', truoc)
    assert re.search(r'set "TIMCLIP_OUTPUT_DIR=%KIEMTRA_TAM%\\ketqua"', truoc)
