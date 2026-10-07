# -*- coding: utf-8 -*-
"""Công cụ phát hành Stable — chạy trên PC1 (máy dev). docs/MANAGED_UPDATE.md §1.

    release_tool.py khoa-thu --out <thư mục>                  cặp khoá Ed25519 THỬ (vòng dev — không phát hành thật)
    release_tool.py lock --python <python.exe đã nghiệm thu> --out <file> [--wheelhouse <thư mục wheel>]
    release_tool.py build --commit <sha> --phien-ban X.Y.Z --lock <file> --out <thư mục nguồn>
                          [--tu-dong-an-toan --tuong-thich-nguoc] [--wheel-kem <file.whl> ...]
    release_tool.py sign --dir <thư mục tag> --khoa <khoá riêng PEM> [--hoi-mat-khau]
    release_tool.py verify --dir <thư mục tag> --tin-cay <trusted_keys.json>
    release_tool.py publish --dir <thư mục tag> --repo <owner/name>   CHỈ IN lệnh + checklist (không có chế độ chạy thật)

Gói lấy ĐÚNG cây git của commit (``git archive``, ``core.autocrlf=false``) — không lấy cây làm việc. Loại
test, ``.bat`` cũ, updater cũ (``cap_nhat.py``), công cụ đóng gói cũ, dữ liệu/khoá/cookie (luật ``dong_goi``)
và CHẶN nếu bất kỳ file nào chứa mẫu bí mật (khoá API, token, khoá riêng, service account, link Sheet thật).
ZIP tất định (thứ tự, thời điểm, quyền cố định) → cùng commit + cùng lock = cùng băm.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone

import managed_update as mu

THU_MUC_MA = "TimClipPro"
LOAI_KHOI_RELEASE = {
    "cap_nhat.py", "dong_goi.py", "dong_goi_may_chay.py", "thiet_lap_may_phu.py", "Dockerfile",
    "docker-compose.yml", "session.log", "requirements-lock.txt", "CLAUDE.md",
}
# Gói TRIỂN KHAI tối giản: runtime không đọc tài liệu/test/Apps Script — chúng đi theo gói audit nguồn
# và bootstrap kit. (Tài liệu còn chứa chính các mẫu bí mật mà bộ quét tìm → dương tính giả.)
THU_MUC_KHONG_PHAT_HANH = ("tests/", "docs/", "apps_script/")
MAU_BI_MAT = (
    ("khoá API Google", re.compile(rb"AIza[0-9A-Za-z_\-]{35}")),
    ("token OAuth Google", re.compile(rb"ya29\.[0-9A-Za-z_\-]{20,}")),
    ("token GitHub", re.compile(rb"gh[pousr]_[0-9A-Za-z]{30,}")),
    ("cookie phiên YouTube", re.compile(rb"__Secure-[0-9A-Z]*PSID[A-Z]*\s*[=\t]\s*[^\s;]{10,}")),
    ("khoá riêng PEM", re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("service account Google", re.compile(rb'["\']type["\']\s*:\s*["\']service' + rb'_account["\']')),
    ("client secret OAuth Google", re.compile(rb"GOCSPX-[0-9A-Za-z_\-]{20,}")),
    ("refresh token Google", re.compile(rb"1//0[0-9A-Za-z_\-]{30,}")),
    ("link Google Sheet thật", re.compile(rb"docs\.google\.com/spreadsheets/d/[A-Za-z0-9_\-]{20,}")),
)
_BO_QUA_LOCK = {"pip", "setuptools", "wheel"}


class LoiPhatHanh(RuntimeError):
    """Không phát hành được — thông báo tiếng Việt, KHÔNG chứa nội dung bí mật."""


def _git(repo: str, *a) -> bytes:
    return subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false", *a], capture_output=True,
                          check=True).stdout


def thu_thap_tu_git(repo: str, commit: str) -> tuple:
    """``({đường_dẫn: byte}, commit_đầy_đủ, tree)`` của ``TimClipPro/`` trong commit — đọc từ object git."""
    commit_day_du = _git(repo, "rev-parse", f"{commit}^{{commit}}").decode().strip()
    tree = _git(repo, "rev-parse", f"{commit_day_du}^{{tree}}").decode().strip()
    tar = _git(repo, "archive", "--format=tar", commit_day_du, THU_MUC_MA)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
        for m in tf.getmembers():
            if m.isdir() or m.name == "pax_global_header":
                continue
            if not m.isfile():
                raise LoiPhatHanh(f"Cây commit có liên kết/kiểu file đặc biệt: {m.name}")
            files[m.name] = tf.extractfile(m).read()
    return files, commit_day_du, tree


def chon_file_phat_hanh(files: dict) -> dict:
    """Lọc file vào release + quét bí mật TOÀN BỘ file được chọn. Có bí mật → ``LoiPhatHanh`` (chỉ nêu
    đường dẫn + loại, không nêu nội dung)."""
    import dong_goi

    chon, loi, bo_py = {}, [], []
    for p, data in sorted(files.items()):
        if not p.startswith(THU_MUC_MA + "/"):
            continue
        rel = p[len(THU_MUC_MA) + 1:]
        ten = rel.rsplit("/", 1)[-1]
        if (rel.startswith(THU_MUC_KHONG_PHAT_HANH) or ten.lower().endswith(".bat")
                or rel in LOAI_KHOI_RELEASE):
            continue
        if not dong_goi.nen_lay(rel):
            if ten.lower().endswith(".py"):
                bo_py.append(p)
            continue
        for loai, mau in MAU_BI_MAT:
            if mau.search(data):
                loi.append(f"{p}: {loai}")
                break
        else:
            ly_do = dong_goi.ly_do_noi_dung_nhay_cam(data) if os.path.splitext(ten)[1].lower() in \
                dong_goi.DUOI_DU_LIEU else ""
            if ly_do:
                loi.append(f"{p}: {ly_do}")
            else:
                chon[p] = data
    if loi:
        raise LoiPhatHanh("Commit chứa nội dung nhạy cảm — không phát hành: " + "; ".join(loi))
    if bo_py:
        # Gói thiếu module thì PC2 chỉ phát hiện ở health check (rồi cách ly) — chặn ngay lúc build.
        raise LoiPhatHanh("Luật đóng gói loại file mã Python — gói sẽ thiếu module: " + ", ".join(bo_py))
    if f"{THU_MUC_MA}/app.py" not in chon or f"{THU_MUC_MA}/engine.py" not in chon:
        raise LoiPhatHanh("Commit thiếu mã lõi (app.py/engine.py).")
    return chon


def _zip_tat_dinh(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for p in sorted(files):
            zi = zipfile.ZipInfo(p, date_time=(1980, 1, 1, 0, 0, 0))
            zi.external_attr = (0o100644 << 16)
            zi.create_system = 0
            z.writestr(zi, files[p], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buf.getvalue()


_TEN_WHEEL = re.compile(r"[A-Za-z0-9_.]+-[A-Za-z0-9_.+!]+(?:-[0-9][A-Za-z0-9_.]*)?"
                        r"-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+\.whl")


def _wheel_kem(ds: tuple, lock: bytes) -> dict:
    kq = {}
    for w in ds or ():
        ten = os.path.basename(w)
        if not _TEN_WHEEL.fullmatch(ten):
            raise LoiPhatHanh(f"Tên wheel kèm không hợp lệ: {ten}")
        with open(w, "rb") as f:
            du = f.read()
        if f"--hash=sha256:{hashlib.sha256(du).hexdigest()}".encode() not in lock:
            raise LoiPhatHanh(f"Lock không có băm của wheel kèm {ten} — PC2 sẽ từ chối cài.")
        kq[f"{THU_MUC_MA}/wheels/{ten}"] = du
    return kq


def _phien_ban_lich_su(files: dict) -> int:
    m = re.search(rb"^PHIEN_BAN\s*=\s*(\d+)", files.get(f"{THU_MUC_MA}/lich_su.py", b""), re.M)
    if not m:
        raise LoiPhatHanh("Không đọc được phiên bản lược đồ lịch sử của commit.")
    return int(m.group(1))


def build(repo: str, commit: str, phien_ban: str, lock: bytes, out: str, *, python: str = "3.12",
          tuong_thich_nguoc: bool = False, tu_dong_an_toan: bool = False,
          tao_luc: str = "", wheel_kem=()) -> str:
    """Dựng ``<out>/stable-X.Y.Z/{release.json, manifest.json, TimClipPro-X.Y.Z-win_amd64.zip}`` từ ĐÚNG
    cây git của ``commit`` (không bao giờ từ cây làm việc)."""
    files, commit_day_du, tree = thu_thap_tu_git(repo, commit)
    return dong_goi_tu_files(files, commit_day_du, tree, phien_ban, lock, out, python=python,
                             tuong_thich_nguoc=tuong_thich_nguoc, tu_dong_an_toan=tu_dong_an_toan,
                             tao_luc=tao_luc, wheel_kem=wheel_kem)


def dong_goi_tu_files(files: dict, commit_day_du: str, tree: str, phien_ban: str, lock: bytes, out: str,
                      *, python: str = "3.12", tuong_thich_nguoc: bool = False,
                      tu_dong_an_toan: bool = False, tao_luc: str = "", wheel_kem=()) -> str:
    """Lõi đóng gói (lọc + quét bí mật + ZIP tất định + manifest). ``build`` cấp file từ object git;
    kiểm thử mô phỏng hai máy cấp file từ mã đang test (commit/tree giả) — cùng một đường đóng gói.

    Cờ migration MẶC ĐỊNH TẮT: «tự động an toàn» + «tương thích ngược» là QUYẾT ĐỊNH của người phát hành
    cho bản có nâng lịch sử (PC2 có lịch sử cũ hơn sẽ chờ duyệt nếu không khai); máy mới chưa có lịch sử
    không cần cờ. ``wheel_kem``: wheel của gói KHÔNG có wheel trên PyPI (vd. docopt 0.6.2 chỉ có sdist) —
    đi kèm release ở ``TimClipPro/wheels/``, băm của ĐÚNG file phải có trong lock."""
    mu.phan_tich_phien_ban(phien_ban)
    for loai, mau in MAU_BI_MAT:
        if mau.search(lock):
            raise LoiPhatHanh(f"Lock chứa nội dung nhạy cảm ({loai}) — không phát hành.")
    if b"--hash=sha256:" not in lock:
        print("[CẢNH BÁO] Lock chưa có băm gói — PC2 sẽ TỪ CHỐI tạo runtime từ bản này (chỉ dùng để thử).",
              file=sys.stderr)
    chon = chon_file_phat_hanh(files)
    chon.update(_wheel_kem(wheel_kem, lock))
    lich_su = _phien_ban_lich_su(chon)
    chon[f"{THU_MUC_MA}/requirements-lock.txt"] = lock
    chon[mu.TEN_DAU_RELEASE] = json.dumps(
        {"dinh_dang": 1, "ung_dung": mu.UNG_DUNG, "phien_ban": phien_ban, "commit": commit_day_du,
         "tree": tree}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ds = json.dumps({"files": [{"path": p, "size": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                               for p, b in sorted(chon.items())]}, sort_keys=True).encode("utf-8")
    zb = _zip_tat_dinh({**chon, mu.TEN_DS_FILE: ds})
    lock_sha = hashlib.sha256(lock).hexdigest()
    md = {
        "dinh_dang": mu.DINH_DANG_MANIFEST, "ung_dung": mu.UNG_DUNG, "kenh": mu.KENH_STABLE,
        "phien_ban": phien_ban, "commit": commit_day_du, "tree": tree,
        "tao_luc": tao_luc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "goi": {"ten": f"{mu.UNG_DUNG}-{phien_ban}-{mu.NEN_TANG}.zip", "kich_thuoc": len(zb),
                "sha256": hashlib.sha256(zb).hexdigest(), "ds_file_sha256": hashlib.sha256(ds).hexdigest()},
        "nen_tang": mu.NEN_TANG, "python": python,
        "runtime": {"runtime_id": f"py{python.replace('.', '')}-{lock_sha[:12]}", "lock_sha256": lock_sha},
        "du_lieu": {"lich_su": lich_su, "tuong_thich_nguoc": tuong_thich_nguoc},
        "migration": {"tu_dong_an_toan": tu_dong_an_toan},
        "launcher_toi_thieu": mu.PHIEN_BAN_LAUNCHER, "kho_dinh_dang": 1,
    }
    raw_m = json.dumps(md, sort_keys=True, ensure_ascii=False, indent=1).encode("utf-8")
    mu.doc_manifest(raw_m)                                   # tự kiểm theo đúng luật của PC2
    goc = os.path.join(out, mu.TIEN_TO_TAG + phien_ban)
    os.makedirs(goc, exist_ok=False)
    for ten, b in ((mu.TEN_MANIFEST, raw_m), (md["goi"]["ten"], zb),
                   ("release.json", b'{"draft": false, "prerelease": false}')):
        with open(os.path.join(goc, ten), "wb") as f:
            f.write(b)
    return goc


def tao_khoa_thu(out: str) -> tuple:
    """Cặp khoá THỬ: ``khoa_rieng_THU.pem`` (không mã hoá — CHỈ cho sandbox) + ``trusted_keys.json``."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    os.makedirs(out, exist_ok=True)
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                          serialization.NoEncryption())
    raw = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    p_rieng = os.path.join(out, "khoa_rieng_THU.pem")
    with open(p_rieng, "xb") as f:
        f.write(pem)
    p_tin = os.path.join(out, "trusted_keys.json")
    with open(p_tin, "x", encoding="utf-8") as f:
        json.dump({"khoa": [{"key_id": mu.tao_key_id(raw), "ed25519_pub_b64": base64.b64encode(raw).decode(),
                             "ghi_chu": "KHOÁ THỬ — không dùng cho phát hành thật"}]}, f, indent=1)
    return p_rieng, p_tin


def sign(thu_muc_tag: str, khoa_rieng_pem: str, *, mat_khau: bytes = None) -> str:
    """Ký manifest. Khoá phát hành THẬT nên được mã hoá — ``mat_khau`` (CLI: ``--hoi-mat-khau``)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    with open(khoa_rieng_pem, "rb") as f:
        du = f.read()
    try:
        k = serialization.load_pem_private_key(du, password=mat_khau)
    except TypeError:
        raise LoiPhatHanh("Khoá ký được mã hoá — chạy lại với --hoi-mat-khau." if mat_khau is None else
                          "Khoá ký KHÔNG mã hoá — bỏ --hoi-mat-khau.") from None
    except ValueError:
        raise LoiPhatHanh("Không mở được khoá ký (sai mật khẩu hoặc file hỏng).") from None
    if not isinstance(k, Ed25519PrivateKey):
        raise LoiPhatHanh("Khoá ký phải là Ed25519.")
    with open(os.path.join(thu_muc_tag, mu.TEN_MANIFEST), "rb") as f:
        raw_m = f.read()
    raw_pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    sig = {"thuat_toan": "ed25519", "key_id": mu.tao_key_id(raw_pub),
           "chu_ky_b64": base64.b64encode(k.sign(raw_m)).decode()}
    p = os.path.join(thu_muc_tag, mu.TEN_CHU_KY)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(sig, f)
    return p


def verify(thu_muc_tag: str, tin_cay: str) -> mu.Manifest:
    """Kiểm Y HỆT PC2: chữ ký (khoá tin cậy) → manifest → băm gói → giải nén an toàn → cây đúng danh sách."""
    with open(os.path.join(thu_muc_tag, mu.TEN_MANIFEST), "rb") as f:
        raw_m = f.read()
    with open(os.path.join(thu_muc_tag, mu.TEN_CHU_KY), "rb") as f:
        raw_s = f.read()
    mu.kiem_chu_ky(raw_m, raw_s, mu.doc_khoa_tin_cay(tin_cay))
    m = mu.doc_manifest(raw_m)
    if os.path.basename(os.path.normpath(thu_muc_tag)) != mu.TIEN_TO_TAG + m.phien_ban:
        raise LoiPhatHanh("Tên thư mục tag không khớp phiên bản trong manifest.")
    goi = os.path.join(thu_muc_tag, m.goi_ten)
    if os.path.getsize(goi) != m.goi_kich_thuoc or mu._sha256_file(goi) != m.goi_sha256:
        raise LoiPhatHanh("Gói không khớp kích thước/băm trong manifest.")
    with tempfile.TemporaryDirectory(prefix="timclip_verify_") as tam:
        cay = os.path.join(tam, "cay")
        mu.giai_nen_an_toan(goi, cay)
        mu.kiem_cay_release(cay, m)
    return m


def lenh_publish(thu_muc_tag: str, repo: str) -> list:
    """Lệnh ``gh`` SẼ dùng khi chủ dự án duyệt phát hành — chỉ trả về để in, không chạy."""
    with open(os.path.join(thu_muc_tag, mu.TEN_MANIFEST), "rb") as f:
        m = mu.doc_manifest(f.read())
    tag = mu.TIEN_TO_TAG + m.phien_ban
    return ["gh", "release", "create", tag,
            os.path.join(thu_muc_tag, mu.TEN_MANIFEST), os.path.join(thu_muc_tag, mu.TEN_CHU_KY),
            os.path.join(thu_muc_tag, m.goi_ten), "--repo", repo, "--target", m.commit,
            "--title", f"TimClipPro {m.phien_ban} (Stable)", "--notes", f"Stable {m.phien_ban} — commit {m.commit}"]


def tao_lock(python_exe: str, *, wheelhouse: str = "") -> str:
    """Lock từ MÔI TRƯỜNG ĐÃ NGHIỆM THU (đọc ``importlib.metadata`` của chính python đó). Có ``wheelhouse``
    (thư mục wheel đã tải) → thêm ``--hash=sha256`` của wheel khớp tên + phiên bản; không có thì lock
    CHƯA BĂM (PC2 sẽ từ chối — cần bước tải wheel có duyệt)."""
    ma = ("import json, importlib.metadata as m, sys; print(json.dumps({'py': '.'.join(map(str, "
          "sys.version_info[:3])), 'ds': sorted({(d.metadata['Name'], d.version) for d in m.distributions()})}))")
    kq = json.loads(subprocess.run([python_exe, "-c", ma], capture_output=True, check=True, text=True,
                                   encoding="utf-8").stdout)
    dong = [f"# TimClipPro runtime lock — sinh từ môi trường đã nghiệm thu (python {kq['py']})",
            "# KHÔNG sửa tay. PC2 cài bằng: pip install --require-hashes --no-deps -r <file>"]
    wheel = os.listdir(wheelhouse) if wheelhouse else []
    for ten, ver in kq["ds"]:
        if ten.lower() in _BO_QUA_LOCK:
            continue
        chuan = re.sub(r"[-_.]+", "_", ten).lower()
        bam = [hashlib.sha256(open(os.path.join(wheelhouse, w), "rb").read()).hexdigest()
               for w in sorted(wheel) if w.endswith(".whl")
               and re.sub(r"[-_.]+", "_", w.split("-")[0]).lower() == chuan and w.split("-")[1] == ver]
        dong.append(f"{ten}=={ver}" + "".join(f" \\\n    --hash=sha256:{b}" for b in bam))
    return "\n".join(dong) + "\n"


def _utf8_dau_ra() -> None:
    """stdout/stderr bị chuyển hướng (log Task Scheduler, ống dẫn) mặc định là mã ANSI (cp1252/cp1258) —
    in tiếng Việt / ✅ sẽ sập. Chuyển sang UTF-8, lỗi thì thay ký tự (không bao giờ sập vì in)."""
    for luong in (sys.stdout, sys.stderr):
        try:
            if (luong.encoding or "").lower().replace("-", "") != "utf8":
                luong.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_dau_ra()
    import argparse

    ap = argparse.ArgumentParser(description="Phát hành Stable TimClipPro (PC1)")
    sub = ap.add_subparsers(dest="lenh", required=True)
    a = sub.add_parser("khoa-thu")
    a.add_argument("--out", required=True)
    a = sub.add_parser("lock")
    a.add_argument("--python", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--wheelhouse", default="")
    a = sub.add_parser("build")
    a.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a.add_argument("--commit", required=True)
    a.add_argument("--phien-ban", required=True)
    a.add_argument("--lock", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--tu-dong-an-toan", action="store_true",
                   help="bản này nâng lịch sử bằng migration ĐÃ ĐÁNH GIÁ tự động an toàn (cần kèm "
                        "--tuong-thich-nguoc)")
    a.add_argument("--tuong-thich-nguoc", action="store_true",
                   help="bản TRƯỚC chạy được trên lịch sử đã nâng (điều kiện để quay lại không khôi phục DB)")
    a.add_argument("--wheel-kem", action="append", default=[],
                   help="wheel kèm release cho gói không có wheel trên PyPI (băm phải có trong lock)")
    a = sub.add_parser("sign")
    a.add_argument("--dir", required=True)
    a.add_argument("--khoa", required=True)
    a.add_argument("--hoi-mat-khau", action="store_true")
    a = sub.add_parser("verify")
    a.add_argument("--dir", required=True)
    a.add_argument("--tin-cay", required=True)
    a = sub.add_parser("publish")
    a.add_argument("--dir", required=True)
    a.add_argument("--repo", required=True)
    ns = ap.parse_args(argv)
    try:
        if ns.lenh == "khoa-thu":
            print("\n".join(tao_khoa_thu(ns.out)))
        elif ns.lenh == "lock":
            with open(ns.out, "x", encoding="utf-8", newline="\n") as f:
                f.write(tao_lock(ns.python, wheelhouse=ns.wheelhouse))
        elif ns.lenh == "build":
            with open(ns.lock, "rb") as f:
                print(build(ns.repo, ns.commit, ns.phien_ban, f.read(), ns.out,
                            tuong_thich_nguoc=ns.tuong_thich_nguoc, tu_dong_an_toan=ns.tu_dong_an_toan,
                            wheel_kem=tuple(ns.wheel_kem)))
        elif ns.lenh == "sign":
            mk = None
            if ns.hoi_mat_khau:
                import getpass

                mk = getpass.getpass("Mật khẩu khoá ký: ").encode("utf-8")
            print(sign(ns.dir, ns.khoa, mat_khau=mk))
        elif ns.lenh == "verify":
            m = verify(ns.dir, ns.tin_cay)
            print(f"ĐẠT: {m.phien_ban} commit {m.commit} gói {m.goi_sha256}")
        else:
            # Trích dẫn kiểu Windows: dán nguyên văn vào Command Prompt/PowerShell vẫn đúng từng đối số.
            print("CHƯA PHÁT HÀNH. Khi chủ dự án DUYỆT, lệnh sẽ là:\n  "
                  + subprocess.list2cmdline(lenh_publish(ns.dir, ns.repo)))
            print("Checklist: (1) duyệt bằng văn bản; (2) tag chưa tồn tại — KHÔNG bao giờ gắn lại tag cũ; "
                  "(3) không draft, không pre-release; (4) verify lại bằng trusted_keys.json của PC2.")
    except (LoiPhatHanh, mu.LoiCapNhat, OSError, subprocess.CalledProcessError) as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
