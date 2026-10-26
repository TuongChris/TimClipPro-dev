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
    assert rc != 0 and f"{dau} docs/x.md: khoá API / token" in out
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
    assert rc != 0 and f"{b} TimClipPro/tests/b.py" in out and "bỏ qua (người dùng duyệt là mẫu GIẢ)" in out
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


# --- Review audit đợt 2: hook không được chặn chính repo, và lời hướng dẫn của hook phải tự làm theo được ---

def _ham_quet_cua_hook() -> str:
    """Nguyên văn hàm ``quet_noi_dung`` của hook dùng chung (không chép tay mẫu)."""
    with open(HOOK, encoding="utf-8") as f:
        m = re.search(r"^quet_noi_dung\(\) \{\n.*?^\}\n", f.read(), re.S | re.M)
    assert m, "hook không còn hàm quet_noi_dung"
    return m.group(0)


def _quet_cay_lam_viec(tmp_path, cac_file) -> str:
    """Chạy ĐÚNG hàm quét của hook trên một patch giả «mọi dòng của mỗi file là dòng THÊM» — như khi một commit
    tạo hoặc sửa từng file đó. ``git`` trong hàm được thay bằng hàm sh đọc patch giả (không đụng repo thật)."""
    patch = tmp_path / "patch.txt"
    with open(patch, "w", encoding="utf-8", newline="\n") as f:
        for rel, noi_dung in cac_file:
            f.write("commit " + "0" * 40 + "\n+++ b/" + rel + "\n")
            f.writelines("+" + d + "\n" for d in noi_dung.splitlines())
    kich_ban = tmp_path / "quet.sh"
    with open(kich_ban, "w", encoding="utf-8", newline="\n") as f:
        f.write(_ham_quet_cua_hook() + 'git() { cat "$PATCH_GIA"; }\nquet_noi_dung private HEAD\n')
    r = subprocess.run(["sh", str(kich_ban)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PATCH_GIA": str(patch), "TIMCLIP_MAU_GIA_DA_DUYET": ""})
    assert r.returncode == 0, r.stderr
    return r.stdout


def _file_dang_theo_doi():
    r = subprocess.run(["git", "-C", _GOC_REPO, "ls-files", "-z"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        pytest.skip("không phải cây git (bản đóng gói) — không có danh sách file để tự quét")
    for rel in r.stdout.decode("utf-8").split("\0"):
        p = os.path.join(_GOC_REPO, *rel.split("/"))
        if not rel or not os.path.isfile(p):
            continue
        with open(p, "rb") as f:
            du_lieu = f.read()
        if b"\0" not in du_lieu:                                            # bỏ file nhị phân như git --text
            yield rel, du_lieu.decode("utf-8", errors="replace")


@pytest.mark.skipif(not shutil.which("sh"), reason="cần sh")
def test_khung_tu_quet_bat_mau_gia_thieu_dau(tmp_path):
    """Đối chứng cho test tự quét: cùng khung, một mẫu giả THIẾU dấu phải bị bắt, có dấu thì qua."""
    out = _quet_cay_lam_viec(tmp_path, [("TimClipPro/tests/a.py", "A = '" + _DONG_SA.strip() + "'\n"),
                                        ("TimClipPro/tests/b.py", "B = '" + _DONG_SA.strip() + "'  # gia-khong-bi-mat\n")])
    assert "TimClipPro/tests/a.py: metadata service account" in out and "b.py" not in out


# File đã lên remote TRƯỚC hook quét nội dung (E-4) mà có dòng khớp mẫu (mẫu giả trong test, câu hướng dẫn nêu dạng
# email service account). Hook chỉ quét dòng THÊM, nên chúng chỉ bị bắt khi chính dòng đó bị sửa
# hoặc file bị viết lại — khi đó thêm dấu và gỡ khỏi danh sách. KHÔNG thêm file mới vào đây: file mới mang dấu ngay.
_DA_CO_TRUOC_HOOK_E4 = frozenset({
    "TimClipPro/docs/HARDENING_PLAN.md", "TimClipPro/sheets.py", "TimClipPro/tests/dien_tap_phat_hanh.py",
    "TimClipPro/tests/outbox_gia.py", "TimClipPro/tests/test_bao_cao_v2_sheets.py",
    "TimClipPro/tests/test_bao_cao_v2_sheets_trong.py", "TimClipPro/tests/test_danh_sach_video.py",
    "TimClipPro/tests/test_dong_goi_bi_mat.py", "TimClipPro/tests/test_dong_goi_may_chay.py",
    "TimClipPro/tests/test_sheet_destinations.py", "TimClipPro/tests/test_sheets_session.py",
})


@pytest.mark.skipif(not shutil.which("sh"), reason="cần sh")
def test_moi_file_dang_theo_doi_cua_repo_tu_qua_quet_noi_dung_cua_hook(tmp_path):
    """Mọi file đang theo dõi (mã, test, tài liệu) đi qua đúng bộ quét của hook như thể vừa được thêm: mẫu GIẢ trong
    test phải mang dấu «gia-khong-bi-mat» trên cùng dòng (review audit đợt 2: test E-1 mang JSON service account giả
    không dấu → hook chặn chính nhánh sửa audit). Ngoại lệ duy nhất: ``_DA_CO_TRUOC_HOOK_E4`` — và mục nào đã sạch thì
    phải gỡ khỏi danh sách để danh sách không phình."""
    out = _quet_cay_lam_viec(tmp_path, list(_file_dang_theo_doi()))
    bi_bat = {d.strip().split(" ", 1)[1].rsplit(": ", 1)[0] for d in out.splitlines() if d.strip()}
    moi = sorted(bi_bat - _DA_CO_TRUOC_HOOK_E4)
    assert moi == [], ("file bị bộ quét của hook bắt — mẫu GIẢ thì ghi «gia-khong-bi-mat» trên cùng dòng, không thì gỡ "
                       "khỏi commit:\n" + "\n".join(d for d in out.splitlines() if any(f in d for f in moi)))
    assert sorted(_DA_CO_TRUOC_HOOK_E4 - bi_bat) == [], "đã sạch — gỡ khỏi _DA_CO_TRUOC_HOOK_E4"


def test_hook_in_sha_du_40_ky_tu_va_cach_duyet_mau_gia(may):
    """Hướng dẫn của hook (duyệt mẫu GIẢ qua TIMCLIP_MAU_GIA_DA_DUYET = SHA ĐỦ 40 ký tự) phải tự làm theo được từ chính
    thông báo chặn: in SHA đầy đủ, nêu tên biến — người dùng không lập trình không phải tự tra SHA."""
    _nhanh(may)
    _commit_file(may, "TimClipPro/tests/a.py", "A = '" + _DONG_SA.strip() + "'\n")
    a = _sha(may)
    rc, out = _day(may, "fix/pc2/thu:fix/pc2/thu")
    assert rc != 0 and f"  {a} TimClipPro/tests/a.py: metadata service account" in out, out
    assert "TIMCLIP_MAU_GIA_DA_DUYET" in out, out
    rc, out = _day_env(may, "fix/pc2/thu:fix/pc2/thu", TIMCLIP_MAU_GIA_DA_DUYET=a)
    assert rc == 0, out


# --- Review audit đợt 2 (WR-1): luật «ID bảng 44 ký tự TRẦN» không được bắt một đoạn nằm TRONG chuỗi base64 ---
# Chữ ký Ed25519 (64 byte → 88 ký tự base64 chuẩn, có «+», «/», «==») được commit trong release/trust/*.json. Một
# đoạn 44 ký tự giữa hai ký tự base64 «+»/«/»/«=» mở đầu bằng «1» (~1/2000 chữ ký) trông như ID bảng → hook chặn đẩy.
# Ba chữ ký GIẢ (byte ngẫu nhiên có seed, không ký gì), mỗi chữ ký có một dạng biên khác nhau của đoạn «1 + 43».
_CHU_KY_GIA = {
    "cong_truoc_bang_sau": "N+ErORitkaPbiYq16hgaTrwgc0B1kN9u/JFoQUit6+1xe4ecW5YJGP28Lni5uqFZXUFcmjixnsg7JouFMSm2Zw==",
    "dau_chuoi_cong_sau": "1FyVsAhBD8PYpCPhKP76y4Xn6pmqQge5tgVPYcOSXQEc+kqC7BlF/wC2pIN9ALGK0Sz1BVa/Tl9GSIaE+L/MJg==",
    "gach_hai_ben": "qKlQzkfvuNdU4Hm0Ls7fHZyzTg3/1HXMwkeQUWjw1ETQTUNtZYIwkbx6p9sdwgqnMLfmHxhO/FmaMR4j9NwJ3A==",
}


@pytest.mark.skipif(not shutil.which("sh"), reason="cần sh")
@pytest.mark.parametrize("ca", sorted(_CHU_KY_GIA))
def test_chu_ky_base64_chua_doan_giong_id_bang_khong_bi_chan(tmp_path, ca):
    chu_ky = _CHU_KY_GIA[ca]
    assert len(chu_ky) == 88 and re.search(r"(^|[^0-9a-z_-])1[0-9a-z_-]{43}([^0-9a-z_-]|$)", chu_ky.lower())
    noi_dung = json.dumps({"chu_ky": {"chu_ky_b64": chu_ky, "key_id": "8aa5baa6c8f225f9"},
                           "khoa_moi": {"ed25519_pub_b64": "1tXkLr8QOo1sp1YAPpsqheIcUlGl36b3f58Kfnd5dq4="}}, indent=1)
    out = _quet_cay_lam_viec(tmp_path, [("release/trust/uy_quyen_PC2_0123456789abcdef.json", noi_dung)])
    assert out.strip() == "", out


@pytest.mark.skipif(not shutil.which("sh"), reason="cần sh")
@pytest.mark.parametrize("dong", [
    f"ID bảng VanPhong: {_SHEET_ID}",
    f"SHEET_ID = \"{_SHEET_ID}\"",
    f"sheet_id={_SHEET_ID}",
    f"APIError: https://sheets.googleapis.com/v4/spreadsheets/{_SHEET_ID}/values/A1:append",
    f"GET https://sheets.googleapis.com/v4/spreadsheets/{_SHEET_ID}?fields=sheets",
    f"https://docs.google.com/spreadsheets/d/{_SHEET_ID}/edit#gid=0",
])
def test_id_bang_44_ky_tu_van_bi_bat_sau_khi_thu_hep_luat(tmp_path, dong):
    """Đối chứng WR-1: thu hẹp luật để bỏ đoạn trong base64 KHÔNG được để lọt ID bảng trần hay trong URL API."""
    out = _quet_cay_lam_viec(tmp_path, [("docs/ghi_chu.md", dong + "\n")])
    assert "docs/ghi_chu.md: link / ID bảng tính 44 ký tự" in out, out


# --- Review audit đợt 2 (WR-8): thông điệp commit cũng lên repo CÔNG KHAI — hook phải quét cả nó ---
# Thông điệp bàn giao dài của dự án hay dán link lỗi / ghi chú: một link bảng thật hay khoá API trong THÂN thông điệp
# trước đây đi qua hook (chỉ xét dòng «+» của diff). Thông điệp không thu hồi được nếu không viết lại lịch sử.

def _commit_thong_diep(clone, thong_diep, ten="docs/ghi_chu.md"):
    """Commit vô hại (một dòng ghi chú) với thông điệp nhiều dòng tuỳ ý."""
    p = os.path.join(clone, *ten.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write("ghi chú\n")
    _git(clone, "add", ten)
    _git(clone, "commit", "-q", "--cleanup=verbatim", "-m", thong_diep)
    return _sha(clone)


@pytest.mark.parametrize("dong, loai", [
    (f"Bảng lỗi: https://docs.google.com/spreadsheets/d/{_SHEET_ID}/edit#gid=0", "link / ID bảng tính 44 ký tự"),
    (f"gspread báo 403 với ID bảng {_SHEET_ID}", "link / ID bảng tính 44 ký tự"),
    (f"khoá thử = {_KHOA_API}", "khoá API / token"),
    ("+ email svc-thu@du-an-thu.iam.gserviceaccount.com", "metadata service account"),   # gia-khong-bi-mat
])
def test_bi_mat_trong_than_thong_diep_commit_bi_chan(may, dong, loai):
    _nhanh(may)
    sha = _commit_thong_diep(may, f"fix(sheets): sửa lỗi 403\n\nNguyên nhân: binding trỏ nhầm.\n{dong}\nTest: xanh.\n")
    rc, out = _day(may, "fix/pc2/thu:fix/pc2/thu")
    assert rc != 0 and f"  {sha} (thông điệp commit): {loai}" in out, out
    assert _SHEET_ID not in out and _KHOA_API not in out and "svc-thu" not in out          # không in nội dung
    assert _git(may, "ls-remote", "private", "refs/heads/fix/pc2/thu").stdout.strip() == ""


def test_thong_diep_commit_binh_thuong_va_mau_gia_co_dau_qua_hook(may):
    """Thông điệp kiểu dự án (mô tả luật, SHA, dòng giống diff) không bị chặn nhầm; mẫu GIẢ có dấu thì qua; duyệt SHA
    (TIMCLIP_MAU_GIA_DA_DUYET) áp cho cả thông điệp."""
    _nhanh(may)
    _commit_thong_diep(may, (
        "fix(hook): luật ID bảng 44 ký tự (audit WR-1)\n\n"
        "ID đứng sau «/» chỉ trong URL bảng: docs.google.com/spreadsheets/d/… và spreadsheets/(d/)?<id>.\n"
        "commit 2b1a1c47f313d1ce5d7f48215d6bc4d4549b4d04\n"
        "+++ b/TimClipPro/google_key.json\n"
        "diff --git a/x b/x\n"
        "+ email dạng <tên>@<dự án>.iam.gserviceaccount.com\n"
        f"mẫu giả {_KHOA_API}  gia-khong-bi-mat\n\n"
        "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"))
    assert _day(may, "fix/pc2/thu:fix/pc2/thu")[0] == 0
    sha = _commit_thong_diep(may, f"thu: mẫu giả không dấu\n\n{_KHOA_API}\n")
    assert _day(may, "fix/pc2/thu:fix/pc2/thu")[0] != 0
    rc, out = _day_env(may, "fix/pc2/thu:fix/pc2/thu", TIMCLIP_MAU_GIA_DA_DUYET=sha)
    assert rc == 0 and "bỏ qua (người dùng duyệt là mẫu GIẢ)" in out, out


def test_thong_diep_commit_khong_lam_lech_quet_diff_phia_sau(may):
    """Dòng trong thông điệp trông như «commit <sha>» / «+++ b/…» không được đổi commit hay file đang quét của diff."""
    _nhanh(may)
    _git(may, "switch", "-q", "fix/pc2/thu")
    p = os.path.join(may, "docs", "x.md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"khoa = {_KHOA_API}\n")
    _git(may, "add", "docs/x.md")
    _git(may, "commit", "-q", "--cleanup=verbatim", "-m",
         "thu: ghi chú\n\ncommit " + "a" * 40 + "\n+++ b/docs/khac.md\n")
    sha = _sha(may)
    rc, out = _day(may, "fix/pc2/thu:fix/pc2/thu")
    assert rc != 0 and f"  {sha} docs/x.md: khoá API / token" in out, out
    assert "a" * 40 not in out and "docs/khac.md" not in out, out
