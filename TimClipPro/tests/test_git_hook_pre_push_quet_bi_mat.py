# -*- coding: utf-8 -*-
"""Audit E-4 (tái hiện, dữ liệu GIẢ): repo công khai, nên một commit trên nhánh việc mang dữ liệu nhạy cảm phải bị
CHẶN bởi hook ``pre-push`` HOẶC bị bộ quét thủ công của docs/ai/GIT_WORKFLOW.md «Quét trước MỖI lần đẩy» phát hiện.

Mô hình hoá ĐÚNG những gì tài liệu đòi (rộng tay cho phía tài liệu):
- lệnh ``git log -p --text --format=%B private/integration/current..HEAD | grep -n -i -E "<mẫu>"`` — mẫu đọc NGUYÊN
  VĂN từ GIT_WORKFLOW.md (không chép tay), chạy cả bằng ``sh`` thật (nếu có) lẫn ``re`` của Python;
- luật tên file «không file .pem/.key/google_key.json».
Hook chạy thật trên repo TẠM (remote bare cục bộ, helper của test_git_hook_pre_push.py). Không mạng, không dữ liệu thật.

Bốn ca (a)–(d) của phát hiện: phải bị bắt bởi ít nhất một lớp. Trước sửa (6ee8f43 … 97527ae) cả hai lớp đều để lọt
(hook chỉ xét tên ref, grep tài liệu thiếu mẫu) → test ĐỎ. Sửa: hook quét NỘI DUNG dòng thêm của commit chưa có trên
remote + grep tài liệu đủ mẫu. Ca đối chứng (khoá API giả ``AIza…``) phải bị bộ quét bắt — chứng minh khung thử hoạt
động. Phần sau: hook không chặn nhầm mã thường, không in nội dung, chỉ quét commit mới, dấu/duyệt mẫu GIẢ."""
import json
import os
import re
import shlex
import shutil
import subprocess

import pytest

from test_git_hook_pre_push import HOOK, _day, _git, _tao_may

GOC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC = os.path.join(GOC, "docs", "ai", "GIT_WORKFLOW.md")

pytestmark = pytest.mark.skipif(not (shutil.which("git") and os.path.isfile(HOOK) and os.path.isfile(DOC)),
                                reason="cần git + hook + GIT_WORKFLOW.md")

PHAM_VI = "private/integration/current..HEAD"


@pytest.fixture()
def may(tmp_path):
    """Repo tạm có hook dùng chung (dựng như test_git_hook_pre_push.py)."""
    return _tao_may(tmp_path)


def _lenh_quet_trong_tai_lieu():
    van_ban = open(DOC, encoding="utf-8").read()
    m = re.search(r"`(git log -p --text[^`]*\| *grep [^`]*)`", van_ban)
    assert m, "GIT_WORKFLOW.md không còn lệnh quét git log -p | grep"
    return m.group(1)


def _mau_grep(lenh):
    t = shlex.split(lenh, posix=True)                  # bỏ lớp nháy kép như sh làm
    return t[t.index("-E") + 1]


def _quet_theo_tai_lieu(clone):
    """Trả (dòng grep bắt được, file vi phạm luật tên) cho các commit sắp đẩy."""
    lenh = _lenh_quet_trong_tai_lieu()
    mau = re.compile(_mau_grep(lenh), re.I)
    log = _git(clone, "log", "-p", "--text", "--format=%B", PHAM_VI).stdout
    bat_py = [d for d in log.splitlines() if mau.search(d)]
    if shutil.which("sh"):                             # chạy NGUYÊN lệnh tài liệu bằng sh thật, đối chiếu
        r = subprocess.run(["sh", "-c", lenh], cwd=clone, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        bat_sh = [d for d in r.stdout.splitlines() if d.strip()]
        assert bool(bat_sh) == bool(bat_py), f"khung thử lệch: sh={bat_sh!r} py={bat_py!r}"
    ten = _git(clone, "log", "--name-only", "--format=", PHAM_VI).stdout.split()
    luat_ten = re.compile(r"\.(pem|key)$|(^|/)google_key\.json$", re.I)
    return bat_py, [f for f in ten if luat_ten.search(f)]


def _commit_file(clone, duong_dan, noi_dung):
    p = os.path.join(clone, *duong_dan.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(noi_dung)
    _git(clone, "add", duong_dan)
    _git(clone, "commit", "-q", "-m", "thu: them ghi chu")


# --- dữ liệu GIẢ (không khoá thật, không ID bảng thật, không cookie thật) ---
_SA = json.dumps({
    "type": "service_account", "project_id": "du-an-thu",   # gia-khong-bi-mat
    "private_key_id": "0123456789abcdef0123456789abcdef01234567",   # gia-khong-bi-mat
    "client_email": "svc-thu@du-an-thu.iam.gserviceaccount.com",   # gia-khong-bi-mat
    "client_id": "100000000000000000001",
}, indent=2) + "\n"                                    # private_key đã gỡ/xoay, metadata còn nguyên
_SHEET_ID = "1" + ("Qw3rTy_uI0-pAs9dFg7Hj" * 3)[:43]   # 44 ký tự, dạng ID Google Sheet, KHÔNG có tiền tố URL
_INSTALL = json.dumps({"installation_id": "3b9d2c1e-7a40-4f00-8000-00000000a0a0",  # gia-khong-bi-mat
                       "tao_luc": "2026-10-25T00:00:00Z"}) + "\n"
_COOKIE = ("# Netscape HTTP Cookie File\n"
           ".youtube.com\tTRUE\t/\tTRUE\t1798000000\tLOGIN_INFO\tAFmmF2swRQIhAthuGIAkhongthat0000\n"
           ".youtube.com\tTRUE\t/\tFALSE\t1798000000\tPREF\tf6=40000000&tz=Asia.Saigon\n"
           ".youtube.com\tTRUE\t/\tTRUE\t0\tYSC\tthuGIA12345\n")

CA_LOT = {
    "a_service_account_khong_private_key": ("TimClipPro/khoa_google.json", _SA),
    "b_sheet_id_44_ky_tu_tran": ("docs/ghi_chu_bang.md", f"# Bảng thử\nID bảng VanPhong: {_SHEET_ID}\n"),
    "c_installation_id": ("TimClipPro/installation.json", _INSTALL),
    "d_cookie_netscape_LOGIN_INFO_PREF_YSC": ("docs/phien_dang_nhap.txt", _COOKIE),
}


@pytest.mark.parametrize("ca", sorted(CA_LOT))
def test_du_lieu_nhay_cam_tren_nhanh_viec_phai_bi_chan_hoac_bi_quet_bat(may, ca):
    duong_dan, noi_dung = CA_LOT[ca]
    _git(may, "switch", "-q", "--no-track", "-c", "fix/pc2/thu", "private/integration/current")
    _commit_file(may, duong_dan, noi_dung)
    bat_grep, bat_ten = _quet_theo_tai_lieu(may)
    rc, out = _day(may, "fix/pc2/thu:fix/pc2/thu")
    da_len_remote = _git(may, "ls-remote", "private", "refs/heads/fix/pc2/thu").stdout.strip() != ""
    assert rc != 0 or bat_grep or bat_ten, (
        f"[{ca}] {duong_dan} LỌT cả hai lớp: hook rc={rc} (đã lên remote={da_len_remote}), "
        f"quét GIT_WORKFLOW.md grep=0 dòng, luật tên=0 file. Hook: {out.strip()!r}")


def test_doi_chung_khung_thu_bat_duoc_mau_da_liet_ke(may):
    """Đối chứng: một mẫu CÓ trong danh sách (khoá API giả) bị quét bắt → khung thử đúng; hook vẫn cho qua."""
    _git(may, "switch", "-q", "--no-track", "-c", "fix/pc2/doi-chung", "private/integration/current")
    _commit_file(may, "docs/x.md", "khoa = AIzaSyGIA_khong_that_0000000000000000\n")
    bat_grep, _ = _quet_theo_tai_lieu(may)
    assert bat_grep and "AIza" in bat_grep[0]
    assert _day(may, "fix/pc2/doi-chung:fix/pc2/doi-chung")[0] == 0     # 37 ký tự: chưa đủ dạng khoá API → hook cho


# --- Hook quét NỘI DUNG (sửa E-4): chặn đúng, không chặn nhầm mã thường, không in nội dung, chỉ quét commit mới ---
_GOC_REPO = GOC
_KHOA_API = "AI" + "za" + "Sy" + "Gia0" * 8 + "x"                  # 39 ký tự: đúng dạng khoá API Google, GIẢ
_DONG_SA = '{"type": "service_account"}\n'                          # gia-khong-bi-mat


def _day_env(clone, ref, **env):
    r = subprocess.run(["git", "-c", f"core.hooksPath={os.path.join(clone, '.git', 'hooks')}", "push", "private", ref],
                       cwd=clone, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **env})
    return r.returncode, r.stdout + r.stderr


def _nhanh(may, ten="fix/pc2/thu"):
    _git(may, "switch", "-q", "--no-track", "-c", ten, "private/integration/current")


def _sha(may):
    return _git(may, "rev-parse", "HEAD").stdout.strip()


def test_dau_gia_khong_bi_mat_cho_mau_gia_tren_cung_dong_qua(may):
    _nhanh(may)
    _commit_file(may, "TimClipPro/tests/mau.py", "MAU = '" + _DONG_SA.strip() + "'  # gia-khong-bi-mat\n")
    assert _day(may, "fix/pc2/thu:fix/pc2/thu")[0] == 0
    _commit_file(may, "TimClipPro/tests/mau2.py", "MAU = '" + _DONG_SA.strip() + "'\n")        # thiếu dấu
    rc, out = _day(may, "fix/pc2/thu:fix/pc2/thu")
    assert rc != 0 and "pre-push: CHẶN" in out and "TimClipPro/tests/mau2.py: metadata service account" in out


def test_them_roi_xoa_o_commit_sau_van_bi_chan_va_khong_in_noi_dung(may):
    _nhanh(may)
    _commit_file(may, "docs/x.md", f"khoa = {_KHOA_API}\n")
    dau = _sha(may)
    _commit_file(may, "docs/x.md", "khoa = (đã gỡ)\n")
    rc, out = _day(may, "fix/pc2/thu:fix/pc2/thu")
    assert rc != 0 and f"{dau[:10]} docs/x.md: khoá API / token" in out
    assert _KHOA_API not in out and "Gia0" not in out                     # chỉ commit + file + loại
    assert _git(may, "ls-remote", "private", "refs/heads/fix/pc2/thu").stdout.strip() == ""


@pytest.mark.parametrize("duong_dan", ["TimClipPro/google_key_client02.json", "docs/cookies.txt",
                                       "release/khoa_ky.pem", "TimClipPro/secrets/ghi_chu.txt",
                                       "TimClipPro/du-an-0123456789ab.json", "state/installation.json"])
def test_ten_file_nhay_cam_bi_chan_du_noi_dung_vo_hai(may, duong_dan):
    _nhanh(may)
    _commit_file(may, duong_dan, "{}\n")
    rc, out = _day(may, "fix/pc2/thu:fix/pc2/thu")
    assert rc != 0 and f" {duong_dan}: " in out


def test_ma_va_tai_lieu_binh_thuong_khong_bi_chan_nham(may):
    """Tên trường / tên file / băm dài xuất hiện hằng ngày trong mã và tài liệu: hook KHÔNG được chặn."""
    _nhanh(may)
    _commit_file(may, "TimClipPro/vi_du.py", (
        "installation_id = str(uuid.uuid4())\n"
        "client = gspread.service_account(filename=duong_dan_khoa)\n"
        "if du_lieu.get(\"type\") != \"service_account\":\n"
        "    raise ValueError(\"không phải khoá service account\")\n"
        "khoa = du_lieu.get(\"private_key\")\n"
        "SHA = \"1f0e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c4b5a69788796a5b4c3d2e1f0\"\n"
        "KHOA_CONG_KHAI = \"ZtXkLr8Qabcdefghijklmnopqrstuvwxyz0123456dq4=\"\n"
        "spreadsheet_id = phan_tich_link(o_nhap)\n"))
    _commit_file(may, "docs/huong_dan.md", (
        "Xuất cookie ra cookies.txt rồi chọn ô «File cookie»; cookie LOGIN_INFO + SAPISID = đã đăng nhập.\n"
        "Email service account dạng <tên>@<dự án>.iam.gserviceaccount.com; ID bảng = 44 ký tự sau /d/.\n"))
    rc, out = _day(may, "fix/pc2/thu:fix/pc2/thu")
    assert rc == 0, out


def test_file_cua_chinh_repo_qua_hook(may):
    """Hook, test hook và GIT_WORKFLOW.md (chứa mẫu regex + mẫu GIẢ có dấu) tự đi qua hook — không tự chặn mình."""
    _nhanh(may)
    for rel in ("release/git-hooks/pre-push", "docs/ai/GIT_WORKFLOW.md", "TimClipPro/tests/test_git_hook_pre_push.py",
                "TimClipPro/tests/test_git_hook_pre_push_quet_bi_mat.py"):
        with open(os.path.join(_GOC_REPO, *rel.split("/")), encoding="utf-8") as f:
            _commit_file(may, rel, f.read())
    rc, out = _day(may, "fix/pc2/thu:fix/pc2/thu")
    assert rc == 0, out


def test_nguoi_dung_duyet_dung_sha_day_du_chi_bo_qua_commit_do(may):
    _nhanh(may)
    _commit_file(may, "TimClipPro/tests/a.py", "A = '" + _DONG_SA.strip() + "'\n")
    a = _sha(may)
    _commit_file(may, "TimClipPro/tests/b.py", "B = '" + _DONG_SA.strip() + "'\n")
    b = _sha(may)
    rc, out = _day_env(may, "fix/pc2/thu:fix/pc2/thu", TIMCLIP_MAU_GIA_DA_DUYET=a)
    assert rc != 0 and f"{b[:10]} TimClipPro/tests/b.py" in out and "bỏ qua (người dùng duyệt là mẫu GIẢ)" in out
    rc, out = _day_env(may, "fix/pc2/thu:fix/pc2/thu", TIMCLIP_MAU_GIA_DA_DUYET=f"{a[:10]} {b[:10]}")
    assert rc != 0                                                          # SHA rút gọn không phải duyệt
    rc, out = _day_env(may, "fix/pc2/thu:fix/pc2/thu", TIMCLIP_MAU_GIA_DA_DUYET=f"{a.upper()}, {b}")
    assert rc == 0, out
    assert _git(may, "ls-remote", "private", "refs/heads/fix/pc2/thu").stdout.split()[0] == b


def test_commit_da_co_tren_remote_khong_quet_lai(may, tmp_path):
    """Chỉ commit CHƯA có trên remote bị quét: lịch sử cũ (mẫu giả không dấu) không chặn việc mới hay gộp FF."""
    goc = str(tmp_path / "goc")                                             # clone không hook của fixture
    _git(goc, "switch", "-q", "-c", "fix/pc1/cu")
    _commit_file(goc, "TimClipPro/tests/cu.py", "C = '" + _DONG_SA.strip() + "'\n")
    _git(goc, "push", "-q", "origin", "fix/pc1/cu:fix/pc1/cu")
    _git(may, "fetch", "-q", "private")
    _git(may, "switch", "-q", "--no-track", "-c", "fix/pc2/tiep", "private/fix/pc1/cu")
    _commit_file(may, "docs/moi.md", "ghi chú mới\n")
    assert _day(may, "fix/pc2/tiep:fix/pc2/tiep")[0] == 0
    _git(may, "fetch", "-q", "private")
    assert _day(may, f"{_sha(may)}:refs/heads/integration/current")[0] == 0
