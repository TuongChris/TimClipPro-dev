# -*- coding: utf-8 -*-
"""Công cụ phát hành Stable — chạy trên PC1 hoặc PC2 (hai máy ngang quyền). docs/MANAGED_UPDATE.md §1.

    release_tool.py khoa-thu --out <thư mục>                  cặp khoá Ed25519 THỬ (vòng dev — không phát hành thật)
    release_tool.py lock --python <python.exe đã nghiệm thu> --out <file> [--wheelhouse <thư mục wheel>]
    release_tool.py build --commit <sha> --phien-ban X.Y.Z --lock <file> --out <thư mục nguồn>
                          [--tu-dong-an-toan --tuong-thich-nguoc] [--wheel-kem <file.whl> ...]
    release_tool.py sign --dir <thư mục tag> --khoa <khoá riêng PEM> [--hoi-mat-khau]
    release_tool.py verify --dir <thư mục tag> --tin-cay <trusted_keys.json>
    release_tool.py publish --dir <thư mục tag> --repo <owner/name>   CHỈ IN lệnh + checklist (không có chế độ chạy thật)
    release_tool.py tao-khoa --thu-muc <thư mục MỚI ngoài repo> --ten-may PC2      khoá phát hành THẬT của máy này
    release_tool.py ky-uy-quyen --yeu-cau <file> --khoa <khoá riêng> --tin-cay <trusted_keys.json> --ra <file>
    release_tool.py kiem-uy-quyen --uy-quyen <file> --tin-cay <trusted_keys.json> [--yeu-cau <file>]
    release_tool.py them-khoa-danh-sach --uy-quyen <file> --tin-cay release/trusted_keys.json   (sau khi ghi danh)
    (tao-khoa / ky-uy-quyen: NGƯỜI DÙNG tự gõ mật khẩu trong console — docs/UY_QUYEN_KHOA.md)
    release_tool.py kiem-sau-ky --dir <thư mục tag đã ký> --tin-cay <trusted_keys.json> [--key-id <id>] [--commit <sha>]
    release_tool.py feed --dir <thư mục tag đã ký> --tin-cay <trusted_keys.json> --out <thư mục>   ZIP phân phối + SHA256SUMS
    release_tool.py kit --commit <sha> --lock-launcher <file có băm> --tin-cay <trusted_keys.json> --out <file.zip>
    (quy trình đủ trên PC1 hoặc PC2: docs/PHAT_HANH_HAI_MAY.md)

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


# ---------------------------------------------------------------------------
#  Khoá phát hành của MỖI máy + uỷ quyền ghi danh khoá mới (docs/UY_QUYEN_KHOA.md)
# ---------------------------------------------------------------------------

def ly_do_mat_khau_yeu(mk: str) -> str:
    """Rỗng = đạt. Chỉ ASCII in được: mật khẩu có dấu gõ bằng Unikey/Telex dễ sai byte giữa các lần gõ."""
    if len(mk) < 16:
        return "Quá ngắn (cần ≥ 16 ký tự)."
    if not (mk.isascii() and mk.isprintable()):
        return "Có ký tự có dấu/đặc biệt — chỉ dùng chữ không dấu, số, ký hiệu bàn phím (tắt Unikey khi gõ)."
    if len(set(mk)) < 6:
        return "Quá ít ký tự khác nhau."
    return ""


def _trong_ban_clone_git(p: str) -> bool:
    hien = os.path.abspath(p)
    while True:
        if os.path.exists(os.path.join(hien, ".git")):
            return True
        cha = os.path.dirname(hien)
        if cha == hien:
            return False
        hien = cha


def tao_khoa_phat_hanh(thu_muc: str, *, mat_khau: bytes, ten_may: str) -> dict:
    """Cặp khoá phát hành THẬT của MỘT máy: khoá riêng PKCS8 MÃ HOÁ bằng mật khẩu người dùng gõ
    (``khoa_rieng_phat_hanh_<key_id>.pem``), khoá công khai đúng định dạng trust store (``khoa_cong_khai_<key_id>.json``),
    ``VAN_TAY_KHOA.txt``. Thư mục MỚI, ngoài repo git, ngoài OneDrive/ổ mạng; không ghi đè. Tự kiểm: mở lại bằng đúng
    mật khẩu, sai/thiếu mật khẩu bị từ chối, ký thử (miền tự kiểm — không phải manifest) xác minh đúng."""
    import runtime_paths
    import uy_quyen_khoa as uq
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    thu_muc = os.path.abspath(thu_muc)
    ly_do = runtime_paths.kiem_duong_dan_trang_thai(thu_muc)
    if ly_do:
        raise LoiPhatHanh("Thư mục khoá không an toàn: " + " ".join(ly_do))
    if _trong_ban_clone_git(thu_muc):
        raise LoiPhatHanh("Thư mục khoá nằm trong một bản clone git — khoá riêng không bao giờ vào repo; chọn thư mục "
                          "NGOÀI repo.")
    if os.path.exists(thu_muc) and os.listdir(thu_muc):
        raise LoiPhatHanh("Thư mục khoá đã có file — KHÔNG ghi đè khoá cũ.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}", ten_may or ""):
        raise LoiPhatHanh("Tên máy chỉ gồm chữ không dấu, số, «_.-» (vd. PC2).")
    ly_do = ly_do_mat_khau_yeu(mat_khau.decode("utf-8", "replace"))
    if ly_do:
        raise LoiPhatHanh("Mật khẩu chưa đạt: " + ly_do)
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                          serialization.BestAvailableEncryption(mat_khau))
    raw = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    del k
    key_id = mu.tao_key_id(raw)
    luc = datetime.now().astimezone().isoformat(timespec="seconds")
    cong_khai = json.dumps({"khoa": [{"key_id": key_id, "ed25519_pub_b64": base64.b64encode(raw).decode(),
                                      "ghi_chu": f"Khoá phát hành TimClipPro kênh Stable — tạo {luc[:10]} trên {ten_may}"}]},
                           ensure_ascii=False, indent=1).encode("utf-8")
    os.makedirs(thu_muc, exist_ok=True)
    p_rieng = os.path.join(thu_muc, f"khoa_rieng_phat_hanh_{key_id}.pem")
    p_cong = os.path.join(thu_muc, f"khoa_cong_khai_{key_id}.json")
    for p, du in ((p_rieng, pem), (p_cong, cong_khai)):
        with open(p, "xb") as f:
            f.write(du)
            f.flush()
            os.fsync(f.fileno())
    # ---- tự kiểm (đúng đường ký + đúng parser của launcher) ----
    kiem = {}
    with open(p_rieng, "rb") as f:
        pem_doc = f.read()
    kiem["khoa_rieng_ma_hoa"] = pem_doc.startswith(b"-----BEGIN ENCRYPTED ")       # PKCS8 đã mã hoá
    k2 = serialization.load_pem_private_key(pem_doc, password=mat_khau)
    kiem["mo_dung_mat_khau_ra_cung_khoa"] = k2.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw) == raw
    for ten, mk in (("sai_mat_khau_bi_tu_choi", mat_khau + b"x"), ("khong_mat_khau_bi_tu_choi", None)):
        try:
            serialization.load_pem_private_key(pem_doc, password=mk)
            kiem[ten] = False
        except (TypeError, ValueError):
            kiem[ten] = True
    tin_cay = mu.doc_khoa_tin_cay(p_cong)
    kiem["khoa_cong_khai_doc_duoc_bang_parser_launcher"] = list(tin_cay) == [key_id]
    file_ky = uq._ky({"tu_kiem": key_id, "luc": luc}, k2, uq.MIEN_TU_KIEM)
    del k2
    nd, ck = uq._tach(file_ky, "tự kiểm")
    kiem["ky_thu_xac_minh_dat"] = uq._xac_minh(nd, ck, tin_cay, uq.MIEN_TU_KIEM, "tự kiểm") == key_id
    with open(os.path.join(thu_muc, "VAN_TAY_KHOA.txt"), "x", encoding="utf-8", newline="\r\n") as f:
        f.write(f"""KHOÁ PHÁT HÀNH TimClipPro (kênh Stable) — máy {ten_may}
key_id            : {key_id}
khoá công khai    : {base64.b64encode(raw).decode()}  (Ed25519, 32 byte, base64)
tạo lúc           : {luc}
khoá riêng        : {os.path.basename(p_rieng)} — PKCS8 MÃ HOÁ bằng mật khẩu (không lưu ở đâu khác)
khoá công khai    : {os.path.basename(p_cong)} — đưa lên repo được (không bí mật)
SHA-256           : {hashlib.sha256(pem).hexdigest()}  {os.path.basename(p_rieng)}
                    {hashlib.sha256(cong_khai).hexdigest()}  {os.path.basename(p_cong)}

QUY TẮC
- Khoá riêng KHÔNG rời máy này: không OneDrive, GitHub, email, chat, USB không mã hoá. Claude không đọc thư mục này.
- Mật khẩu cất riêng (trình quản lý mật khẩu / giấy trong két). Mất khoá hoặc mật khẩu: máy kia vẫn ký được (hai khoá
  cùng được tin) — tạo khoá mới cho máy này rồi ghi danh lại theo docs/UY_QUYEN_KHOA.md.
- Lộ khoá riêng + mật khẩu: dừng phát hành bằng khoá này, báo chủ dự án (gỡ khoá khỏi trust store).
- Ký: release_tool.py sign --dir <thư mục stable-X.Y.Z> --khoa <khoá riêng> --hoi-mat-khau (tự gõ mật khẩu).
""")
    return {"key_id": key_id, "khoa_rieng": p_rieng, "khoa_cong_khai": p_cong, "tu_kiem": kiem}


def _mo_khoa_ky(khoa_rieng_pem: str, mat_khau):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    with open(khoa_rieng_pem, "rb") as f:
        du = f.read()
    try:
        k = serialization.load_pem_private_key(du, password=mat_khau)
    except (TypeError, ValueError):
        raise LoiPhatHanh("Không mở được khoá ký (sai mật khẩu hoặc file hỏng).") from None
    if not isinstance(k, Ed25519PrivateKey):
        raise LoiPhatHanh("Khoá ký phải là Ed25519.")
    return k


def ky_uy_quyen(raw_yeu_cau: bytes, khoa_rieng_pem: str, tin_cay: str, *, mat_khau: bytes, bay_gio=None,
                han_ngay: int = 30) -> bytes:
    """Máy ĐANG được tin ký uỷ quyền ghi danh khoá mới cho ĐÚNG yêu cầu (đã tự ký bằng khoá mới). ``tin_cay``: file
    khoá CÔNG KHAI đang tin (định dạng trust store) — khoá ký phải nằm trong đó. Tự kiểm lại uỷ quyền vừa ký."""
    import uy_quyen_khoa as uq

    tin = mu.doc_khoa_tin_cay(tin_cay)
    k = _mo_khoa_ky(khoa_rieng_pem, mat_khau)
    try:
        raw = uq.tao_uy_quyen(raw_yeu_cau, k, khoa_tin_cay=tin, bay_gio=bay_gio, han_ngay=han_ngay)
        uq.doc_uy_quyen(raw, tin, bay_gio=bay_gio)
    except uq.LoiUyQuyen as e:
        raise LoiPhatHanh(str(e)) from None
    finally:
        del k
    return raw


def kiem_uy_quyen(raw_uy_quyen: bytes, tin_cay: str, *, raw_yeu_cau: bytes = None, bay_gio=None) -> dict:
    """Kiểm NGOẠI TUYẾN (review PR, máy nào cũng chạy được): chữ ký bằng khoá công khai đang tin + cấu trúc + hạn;
    có ``raw_yeu_cau`` → phải đúng yêu cầu đó. Ràng buộc cài đặt (định danh, trust store) chỉ kiểm được ở máy đích."""
    import uy_quyen_khoa as uq

    tin = mu.doc_khoa_tin_cay(tin_cay)
    try:
        nd = uq.doc_uy_quyen(raw_uy_quyen, tin, bay_gio=bay_gio)
        if raw_yeu_cau is not None:
            yc = uq.doc_yeu_cau(raw_yeu_cau)
            if (hashlib.sha256(uq.chuan_hoa(yc)).hexdigest() != nd["yeu_cau_sha256"]
                    or any(yc[t] != nd[t] for t in ("khoa_moi", "cai_dat_sha256", "trust_store_sha256",
                                                     "khoa_hien_co", "ma_yeu_cau", "ten_may"))):
                raise LoiPhatHanh("Uỷ quyền không khớp yêu cầu đã gửi.")
    except uq.LoiUyQuyen as e:
        raise LoiPhatHanh(str(e)) from None
    return {"khoa_moi": nd["khoa_moi"]["key_id"], "ten_may": nd["ten_may"], "ky_boi": nd["ky_boi"],
            "het_han": nd["het_han"], "ma_uy_quyen": nd["ma_uy_quyen"], "khoa_hien_co": nd["khoa_hien_co"]}


def them_khoa_danh_sach(raw_uy_quyen: bytes, tin_cay: str) -> dict:
    """Cập nhật danh sách khoá công khai CỦA REPO (``release/trusted_keys.json``) theo một uỷ quyền ĐÃ dùng để ghi danh:
    chữ ký phải của một khoá trong chính danh sách đó, mọi khoá máy đích tin lúc đó phải có trong danh sách. Chỉ THÊM
    một mục, mục cũ giữ nguyên; ghi nguyên tử. (Hạn uỷ quyền không xét ở đây — máy đích đã kiểm lúc ghi danh.)"""
    import uy_quyen_khoa as uq

    tin = mu.doc_khoa_tin_cay(tin_cay)
    try:
        nd = uq.doc_uy_quyen(raw_uy_quyen, tin, bay_gio=datetime.strptime(
            json.loads(raw_uy_quyen.decode("utf-8-sig"))["noi_dung"]["tao_luc"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc))
    except (uq.LoiUyQuyen, ValueError, KeyError, TypeError) as e:
        raise LoiPhatHanh(f"Uỷ quyền không hợp lệ với danh sách này: {e}") from None
    if nd["khoa_moi"]["key_id"] in tin:
        raise LoiPhatHanh(f"Khoá {nd['khoa_moi']['key_id']} đã có trong danh sách.")
    if not set(nd["khoa_hien_co"]) <= set(tin):
        raise LoiPhatHanh("Danh sách thiếu khoá mà máy đích đang tin — không phải danh sách của bản cài này.")
    with open(tin_cay, "rb") as f:
        d = json.loads(f.read().decode("utf-8-sig"))
    d["khoa"] = list(d["khoa"]) + [{
        "key_id": nd["khoa_moi"]["key_id"], "ed25519_pub_b64": nd["khoa_moi"]["ed25519_pub_b64"],
        "ghi_chu": f"Khoá phát hành TimClipPro kênh Stable — máy {nd['ten_may']}; ghi danh theo uỷ quyền "
                   f"{nd['ma_uy_quyen'][:8]} của khoá {nd['ky_boi']} ({nd['tao_luc'][:10]})"}]
    tam = f"{tin_cay}.tmp-{os.getpid()}"
    with open(tam, "x", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tam, tin_cay)
    return {"khoa": sorted(mu.doc_khoa_tin_cay(tin_cay)), "them": nd["khoa_moi"]["key_id"]}


def _co_console() -> bool:
    import uy_quyen_khoa

    return uy_quyen_khoa.co_console()


def _hoi_mat_khau_moi() -> bytes:
    import getpass

    print("=" * 72)
    print(" Mật khẩu khoá ký: ÍT NHẤT 16 ký tự, CHỈ chữ KHÔNG DẤU / số / ký hiệu bàn phím (tắt Unikey khi gõ).")
    print(" Chữ KHÔNG hiện lên màn hình — bình thường. Cất mật khẩu nơi an toàn: MẤT mật khẩu = khoá này hết dùng.")
    print("=" * 72)
    for _ in range(3):
        a = getpass.getpass("Mật khẩu khoá ký: ")
        ly_do = ly_do_mat_khau_yeu(a)
        if ly_do:
            print(f"  → {ly_do} Thử lại.")
            continue
        if getpass.getpass("Gõ LẠI mật khẩu: ") != a:
            print("  → Hai lần gõ KHÁC nhau. Thử lại từ đầu.")
            continue
        return a.encode("utf-8")
    raise LoiPhatHanh("Chưa có mật khẩu hợp lệ — chưa tạo gì.")


# ---------------------------------------------------------------------------
#  Sau khi ký: kiểm, ZIP phân phối, bộ bootstrap — chạy được trên MỌI máy phát hành
# ---------------------------------------------------------------------------

TEN_RELEASE_JSON = "release.json"


def kiem_sau_ky(thu_muc_tag: str, tin_cay: str, *, key_id: str = "", commit: str = "") -> dict:
    """SAU khi người dùng ký, TRƯỚC khi phân phối — y hệt PC2 + thử phá trên BẢN SAO tạm (không sửa bản đã ký):
    verify bằng danh sách khoá công khai đang tin; đúng khoá ký / commit (nếu khai); đúng 4 file, release.json không
    draft/pre-release; khoá lạ bị từ chối «KHÔNG tin cậy»; manifest / chữ ký / gói sửa 1 byte bị từ chối."""
    import shutil

    k = {}
    m = verify(thu_muc_tag, tin_cay)
    with open(os.path.join(thu_muc_tag, mu.TEN_MANIFEST), "rb") as f:
        raw_m = f.read()
    with open(os.path.join(thu_muc_tag, mu.TEN_CHU_KY), "rb") as f:
        raw_s = f.read()
    kid = mu.kiem_chu_ky(raw_m, raw_s, mu.doc_khoa_tin_cay(tin_cay))
    sig = json.loads(raw_s)
    k["chu_ky_dinh_dang"] = (set(sig) == {"thuat_toan", "key_id", "chu_ky_b64"} and sig["thuat_toan"] == "ed25519"
                             and len(base64.b64decode(sig["chu_ky_b64"], validate=True)) == 64)
    if key_id:
        k["ky_bang_khoa_mong_doi"] = kid == key_id
    if commit:
        k["dung_commit"] = m.commit == commit
    ten = sorted([m.goi_ten, mu.TEN_MANIFEST, mu.TEN_CHU_KY, TEN_RELEASE_JSON])
    k["thu_muc_dung_4_file"] = sorted(os.listdir(thu_muc_tag)) == ten
    try:
        with open(os.path.join(thu_muc_tag, TEN_RELEASE_JSON), encoding="utf-8") as f:
            rj = json.load(f)
        k["khong_draft_khong_prerelease"] = rj == {"draft": False, "prerelease": False}
    except (OSError, ValueError):
        k["khong_draft_khong_prerelease"] = False
    with tempfile.TemporaryDirectory(prefix="timclip_sau_ky_") as tam:
        _, tc_la = tao_khoa_thu(os.path.join(tam, "khoa_la"))
        try:
            verify(thu_muc_tag, tc_la)
            k["khoa_la_bi_tu_choi"] = False
        except mu.TuChoiGoi as e:
            k["khoa_la_bi_tu_choi"] = "KHÔNG tin cậy" in str(e)
        for nhan, file in (("manifest", mu.TEN_MANIFEST), ("chu_ky", mu.TEN_CHU_KY), ("goi", m.goi_ten)):
            ban = os.path.join(tam, nhan, os.path.basename(os.path.normpath(thu_muc_tag)))
            shutil.copytree(thu_muc_tag, ban)
            p = os.path.join(ban, file)
            with open(p, "rb") as f:
                b = bytearray(f.read())
            if file == mu.TEN_CHU_KY:                 # đổi 1 ký tự base64 (file vẫn là JSON hợp lệ)
                s = json.loads(bytes(b))
                c = s["chu_ky_b64"]
                s["chu_ky_b64"] = c[:10] + ("A" if c[10] != "A" else "B") + c[11:]
                b = bytearray(json.dumps(s).encode())
            else:
                b[len(b) // 2] ^= 0x01
            with open(p, "wb") as f:
                f.write(bytes(b))
            try:
                verify(ban, tin_cay)
                k[f"{nhan}_sua_1_byte_bi_tu_choi"] = False
            except (mu.LoiCapNhat, LoiPhatHanh, OSError):
                k[f"{nhan}_sua_1_byte_bi_tu_choi"] = True
    return {"kiem": k, "dat": all(k.values()), "phien_ban": m.phien_ban, "commit": m.commit, "key_id": kid,
            "manifest_sha256": m.sha256, "goi_sha256": m.goi_sha256}


def khoi_powershell(phien_ban: str, bam: dict, zip_sha: str) -> str:
    """Khối PowerShell (CHỈ ASCII) cho máy nhận: kiểm băm ZIP tải về → giải nén vào ``C:\\TimClipPro_Feed`` → kiểm
    từng file đã ký → «SAN SANG». Không ghi đè thư mục đã có."""
    tag = mu.TIEN_TO_TAG + phien_ban
    dong = ["& {", f"  $zip  = Join-Path $env:USERPROFILE 'Downloads\\TimClipPro_Feed_{tag}.zip'",
            "  $feed = 'C:\\TimClipPro_Feed'", "  $mong = @{"]
    dong += [f"    '{t}' = '{bam[t]}'" for t in sorted(bam)]
    dong += [
        "  }",
        "  if (-not (Test-Path -LiteralPath $zip)) { \"KHONG THAY $zip - sua duong dan `$zip roi chay lai\"; return }",
        f"  if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower() -ne '{zip_sha}') "
        "{ 'ZIP SAI MA BAM - tai lai tu GitHub, KHONG cap nhat'; return }",
        f"  $dich = Join-Path $feed '{tag}'",
        "  if (Test-Path -LiteralPath $dich) { \"DA CO $dich - khong giai nen de len (kiem hoac xoa thu muc do truoc)\"; "
        "return }",
        "  Expand-Archive -LiteralPath $zip -DestinationPath $feed",
        "  $sai = 0",
        "  foreach ($t in $mong.Keys) { $p = Join-Path $dich $t; $h = if (Test-Path -LiteralPath $p) "
        "{ (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() } else { '' }; $ok = $h -eq $mong[$t]; "
        "if (-not $ok) { $sai++ }; '{0,-32} {1}' -f $t, $(if ($ok) {'KHOP'} else {'SAI'}) }",
        "  $n = @(Get-ChildItem -LiteralPath $dich -File).Count",
        f"  if ($sai -eq 0 -and $n -eq {len(bam)}) {{ 'SAN SANG: chay C:\\TimClipPro\\CapNhat.bat' }} "
        "else { \"LOI: $sai file sai, $n file trong thu muc - KHONG cap nhat\" }",
        "}"]
    kq = "\n".join(dong)
    if not kq.isascii():
        raise LoiPhatHanh("Khối PowerShell phải chỉ có ASCII.")
    return kq


def dong_feed(thu_muc_tag: str, tin_cay: str, out: str) -> dict:
    """ZIP phân phối (asset GitHub Release): ``stable-X.Y.Z/<4 file ĐÃ KÝ, nguyên byte>``, STORED, tất định (giờ =
    ``tao_luc`` của manifest) + ``SHA256SUMS_X.Y.Z.txt`` + ``KHOI_POWERSHELL_X.Y.Z.txt``. Không ghi đè. Chỉ dùng SAU
    ``kiem_sau_ky`` đạt (ở đây verify lại)."""
    m = verify(thu_muc_tag, tin_cay)
    tag = mu.TIEN_TO_TAG + m.phien_ban
    ten = sorted([m.goi_ten, mu.TEN_MANIFEST, mu.TEN_CHU_KY, TEN_RELEASE_JSON])
    if sorted(os.listdir(thu_muc_tag)) != ten:
        raise LoiPhatHanh(f"Thư mục bản ký phải có ĐÚNG 4 file {ten}.")
    du = {}
    for t in ten:
        with open(os.path.join(thu_muc_tag, t), "rb") as f:
            du[t] = f.read()
    bam = {t: hashlib.sha256(b).hexdigest() for t, b in du.items()}
    try:
        lt = datetime.strptime(m.tao_luc, "%Y-%m-%dT%H:%M:%SZ")
        gio = (lt.year, lt.month, lt.day, lt.hour, lt.minute, lt.second - lt.second % 2)
    except ValueError:
        gio = (1980, 1, 1, 0, 0, 0)
    os.makedirs(out, exist_ok=True)
    p_zip = os.path.join(out, f"TimClipPro_Feed_{tag}.zip")
    p_sum = os.path.join(out, f"SHA256SUMS_{m.phien_ban}.txt")
    p_ps = os.path.join(out, f"KHOI_POWERSHELL_{m.phien_ban}.txt")
    for p in (p_zip, p_sum, p_ps):
        if os.path.exists(p):
            raise LoiPhatHanh(f"Đã có {p} — không ghi đè.")
    with zipfile.ZipFile(p_zip, "x") as z:
        for t in ten:
            zi = zipfile.ZipInfo(f"{tag}/{t}", date_time=gio)
            zi.external_attr = 0o100644 << 16
            zi.create_system = 0
            z.writestr(zi, du[t], compress_type=zipfile.ZIP_STORED)
    with zipfile.ZipFile(p_zip) as z:                            # tự kiểm: đọc lại ZIP vừa ghi
        if [i.filename for i in z.infolist()] != [f"{tag}/{t}" for t in ten] or z.testzip() is not None \
                or any(hashlib.sha256(z.read(f"{tag}/{t}")).hexdigest() != bam[t] for t in ten):
            raise LoiPhatHanh("ZIP phân phối đọc lại không khớp bản ký.")
    with open(p_zip, "rb") as f:
        zip_sha = hashlib.sha256(f.read()).hexdigest()
    with open(p_sum, "x", encoding="ascii", newline="\n") as f:
        f.write(f"{zip_sha}  {os.path.basename(p_zip)}\n")
        for t in [m.goi_ten, mu.TEN_MANIFEST, mu.TEN_CHU_KY, TEN_RELEASE_JSON]:
            f.write(f"{bam[t]}  {tag}/{t}\n")
    ps = khoi_powershell(m.phien_ban, bam, zip_sha)
    with open(p_ps, "x", encoding="ascii", newline="\n") as f:
        f.write(ps + "\n")
    return {"zip": p_zip, "zip_sha256": zip_sha, "zip_byte": os.path.getsize(p_zip), "sha256sums": p_sum,
            "khoi_powershell": p_ps, "bam": bam, "phien_ban": m.phien_ban, "commit": m.commit}


FILE_KIT = ("bootstrap.py", "launcher.py", "managed_update.py", "maintenance_gate.py", "khoa.py", "runtime_paths.py")
TAI_LIEU_KIT = ("docs/HUONG_DAN_PC2.md", "docs/KE_HOACH_PILOT_PC2.md")
_PIN = re.compile(r"^([A-Za-z0-9_.\-]+==[^\s\\]+)", re.M)


def dung_kit(repo: str, commit: str, lock_launcher: bytes, tin_cay: str, out_zip: str, *,
             cho_khoa_thu: bool = False) -> dict:
    """Bộ bootstrap (cài MỚI một máy managed): 6 file mã + 2 tài liệu = ĐÚNG blob git của ``commit``,
    ``launcher-lock.txt`` CÓ BĂM (pin = lock trong commit), ``trusted_keys.json`` (CHỈ khoá công khai; khoá THỬ bị từ
    chối trừ khi ``cho_khoa_thu`` — kit diễn tập). ZIP tất định (giờ = giờ commit). Không ghi đè."""
    import bootstrap

    if os.path.exists(out_zip):
        raise LoiPhatHanh(f"Đã có {out_zip} — không ghi đè.")
    commit_day_du = _git(repo, "rev-parse", f"{commit}^{{commit}}").decode().strip()
    gio = tuple(int(x) for x in _git(repo, "log", "-1", "--format=%cd", "--date=format:%Y,%m,%d,%H,%M,%S",
                                     commit_day_du).decode().strip().split(","))
    tep = {f: _git(repo, "show", f"{commit_day_du}:{THU_MUC_MA}/{f}") for f in FILE_KIT}
    for p in TAI_LIEU_KIT:
        tep["tai_lieu/" + os.path.basename(p)] = _git(repo, "show", f"{commit_day_du}:{THU_MUC_MA}/{p}")
    with open(tin_cay, "rb") as f:
        tc = f.read()
    try:
        so_khoa = bootstrap._kiem_khoa_tin_cay_tho(tin_cay)
    except bootstrap.LoiBootstrap as e:
        raise LoiPhatHanh(str(e)) from None
    khoa = mu.doc_khoa_tin_cay(tin_cay)
    if not cho_khoa_thu and any("THỬ" in str(k.get("ghi_chu") or "").upper()
                                for k in json.loads(tc.decode("utf-8-sig")).get("khoa", [])):
        raise LoiPhatHanh("trusted_keys.json có KHOÁ THỬ — không dựng kit thật (diễn tập: cho_khoa_thu).")
    tep["trusted_keys.json"] = tc
    pin_lock = sorted(_PIN.findall(lock_launcher.decode("utf-8")))
    pin_commit = sorted(_PIN.findall(_git(repo, "show", f"{commit_day_du}:{THU_MUC_MA}/launcher-lock.txt")
                                     .decode("utf-8")))
    if not pin_lock or pin_lock != pin_commit:
        raise LoiPhatHanh("launcher-lock có băm KHÁC pin của launcher-lock.txt trong commit.")
    if lock_launcher.count(b"--hash=sha256:") < len(pin_lock):
        raise LoiPhatHanh("launcher-lock thiếu băm (mỗi gói cần ít nhất một --hash=sha256).")
    tep["launcher-lock.txt"] = lock_launcher
    bi_mat = [f"{p}: {loai}" for p, b in tep.items() for loai, mau in MAU_BI_MAT if mau.search(b)]
    if bi_mat:
        raise LoiPhatHanh("Mẫu bí mật trong kit: " + "; ".join(bi_mat))
    tep["DOC_TRUOC_KIT.txt"] = (
        f"BỘ BOOTSTRAP TimClipPro managed — cài MỚI một máy\r\n"
        f"Dựng từ commit {commit_day_du}\r\n"
        f"Khoá phát hành tin cậy: {', '.join(sorted(khoa))} ({so_khoa} khoá công khai)"
        + (" — KIT DIỄN TẬP (có khoá THỬ)" if cho_khoa_thu else "") + "\r\n"
        f"launcher-lock.txt sha256 {hashlib.sha256(lock_launcher).hexdigest()} ({len(pin_lock)} gói, có băm)\r\n"
        "Không có: khoá riêng, wheelhouse, kho vân tay, lịch sử, hàng đợi gửi, cookie, khoá Google, link Sheet.\r\n"
        "Cài: tai_lieu/HUONG_DAN_PC2.md (bootstrap.py --goc … --state … --python-goc … --tin-cay trusted_keys.json\r\n"
        "     --repo TuongChris/TimClipPro-dev | --nguon-thu-muc <thư mục feed>).\r\n").encode("utf-8")
    thu_tu = ["DOC_TRUOC_KIT.txt"] + sorted((p for p in tep if p != "DOC_TRUOC_KIT.txt"), key=lambda x: x.encode())
    os.makedirs(os.path.dirname(os.path.abspath(out_zip)), exist_ok=True)
    with zipfile.ZipFile(out_zip, "x") as z:
        for p in thu_tu:
            zi = zipfile.ZipInfo(p, date_time=gio)
            zi.create_system = 0
            zi.external_attr = 0o100644 << 16
            z.writestr(zi, tep[p], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        z.comment = commit_day_du.encode("ascii")
    with open(out_zip, "rb") as f:
        s = hashlib.sha256(f.read()).hexdigest()
    return {"zip": out_zip, "zip_sha256": s, "commit": commit_day_du, "khoa": sorted(khoa),
            "file": {p: hashlib.sha256(b).hexdigest() for p, b in sorted(tep.items())}}


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
    a = sub.add_parser("tao-khoa", help="tạo khoá phát hành THẬT của máy này (người dùng tự gõ mật khẩu)")
    a.add_argument("--thu-muc", required=True)
    a.add_argument("--ten-may", required=True)
    a = sub.add_parser("ky-uy-quyen", help="máy đang được tin ký uỷ quyền ghi danh khoá mới (tự gõ mật khẩu)")
    a.add_argument("--yeu-cau", required=True)
    a.add_argument("--khoa", required=True)
    a.add_argument("--tin-cay", required=True)
    a.add_argument("--ra", required=True)
    a.add_argument("--han-ngay", type=int, default=30)
    a = sub.add_parser("kiem-uy-quyen", help="kiểm ngoại tuyến một uỷ quyền (review PR)")
    a.add_argument("--uy-quyen", required=True)
    a.add_argument("--tin-cay", required=True)
    a.add_argument("--yeu-cau", default="")
    a = sub.add_parser("them-khoa-danh-sach", help="thêm khoá vào release/trusted_keys.json theo uỷ quyền đã ký")
    a.add_argument("--uy-quyen", required=True)
    a.add_argument("--tin-cay", required=True)
    a = sub.add_parser("kiem-sau-ky", help="kiểm bản vừa ký (y hệt PC2 + thử phá trên bản sao)")
    a.add_argument("--dir", required=True)
    a.add_argument("--tin-cay", required=True)
    a.add_argument("--key-id", default="")
    a.add_argument("--commit", default="")
    a.add_argument("--json", default="")
    a = sub.add_parser("feed", help="ZIP phân phối + SHA256SUMS + khối PowerShell từ bản ĐÃ ký")
    a.add_argument("--dir", required=True)
    a.add_argument("--tin-cay", required=True)
    a.add_argument("--out", required=True)
    a = sub.add_parser("kit", help="bộ bootstrap cài MỚI một máy managed")
    a.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a.add_argument("--commit", required=True)
    a.add_argument("--lock-launcher", required=True)
    a.add_argument("--tin-cay", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--dien-tap", action="store_true", help="cho phép khoá THỬ (kit diễn tập, không giao máy thật)")
    ns = ap.parse_args(argv)
    try:
        if ns.lenh in ("tao-khoa", "ky-uy-quyen") and not _co_console():
            print("[DỪNG] Lệnh này cần NGƯỜI DÙNG gõ mật khẩu trong cửa sổ console riêng (chạy file .bat theo hướng "
                  "dẫn) — không chạy qua ống dẫn/tự động.", file=sys.stderr)
            return 2
        if ns.lenh == "tao-khoa":
            kq = tao_khoa_phat_hanh(ns.thu_muc, mat_khau=_hoi_mat_khau_moi(), ten_may=ns.ten_may)
            for t, v in kq["tu_kiem"].items():
                print(f"  {'ĐẠT' if v else 'LỖI'}  {t}")
            print(f"key_id: {kq['key_id']}   (ghi lại 8 ký tự cuối: {kq['key_id'][-8:]})")
            print(f"khoá công khai: {kq['khoa_cong_khai']}")
            dat = all(kq["tu_kiem"].values())
            print("KẾT QUẢ:", "ĐẠT — khoá đã tạo và tự kiểm." if dat else "CÓ LỖI — chưa dùng khoá này, báo Claude.")
            return 0 if dat else 1
        if ns.lenh == "ky-uy-quyen":
            import getpass

            import uy_quyen_khoa as uq

            if os.path.exists(ns.ra):
                raise LoiPhatHanh(f"Đã có {ns.ra} — không ghi đè.")
            with open(ns.yeu_cau, "rb") as f:
                raw_yc = f.read(uq.GIOI_HAN_FILE + 1)
            with open(ns.tin_cay, "rb") as f:
                sha_tc = hashlib.sha256(f.read()).hexdigest()
            try:
                yc = uq.doc_yeu_cau(raw_yc)
            except uq.LoiUyQuyen as e:
                raise LoiPhatHanh(f"Yêu cầu không hợp lệ: {e}") from None
            print("=" * 72)
            print(" KÝ UỶ QUYỀN ghi danh khoá phát hành mới")
            print(f"   khoá mới      : {yc['khoa_moi']['key_id']}   (máy {yc['ten_may']}, tự ký hợp lệ)")
            print(f"   máy đích tin  : {', '.join(yc['khoa_hien_co'])}; đang chạy {yc['ban_dang_chay'] or '(chưa có)'}")
            print(f"   trust store máy đích {'TRÙNG' if yc['trust_store_sha256'] == sha_tc else 'KHÁC'} file "
                  f"--tin-cay ({yc['trust_store_sha256'][:12]}…)")
            print("=" * 72)
            try:
                go = input(f"Gõ 8 ký tự CUỐI của khoá mới ({yc['khoa_moi']['key_id'][:8]}…) — so với số máy kia báo: ")
            except EOFError:
                go = ""
            if go.strip().lower() != yc["khoa_moi"]["key_id"][-8:]:
                raise LoiPhatHanh("Không khớp — chưa ký gì.")
            mk = getpass.getpass("Mật khẩu khoá ký: ").encode("utf-8")
            try:
                raw = ky_uy_quyen(raw_yc, ns.khoa, ns.tin_cay, mat_khau=mk, han_ngay=ns.han_ngay)
            finally:
                del mk
            with open(ns.ra, "xb") as f:
                f.write(raw)
            t = kiem_uy_quyen(raw, ns.tin_cay, raw_yeu_cau=raw_yc)
            print(f"ĐÃ KÝ: {ns.ra} — khoá {t['khoa_moi']} ({t['ten_may']}), ký bởi {t['ky_boi']}, hết hạn {t['het_han']}")
            return 0
        if ns.lenh == "kiem-uy-quyen":
            with open(ns.uy_quyen, "rb") as f:
                raw = f.read()
            raw_yc = None
            if ns.yeu_cau:
                with open(ns.yeu_cau, "rb") as f:
                    raw_yc = f.read()
            t = kiem_uy_quyen(raw, ns.tin_cay, raw_yeu_cau=raw_yc)
            print(f"ĐẠT: uỷ quyền {t['ma_uy_quyen']} — khoá {t['khoa_moi']} ({t['ten_may']}), ký bởi {t['ky_boi']} "
                  f"(đang tin), hết hạn {t['het_han']}" + ("; khớp yêu cầu" if raw_yc is not None else ""))
            return 0
        if ns.lenh == "them-khoa-danh-sach":
            with open(ns.uy_quyen, "rb") as f:
                kq = them_khoa_danh_sach(f.read(), ns.tin_cay)
            print(f"ĐÃ THÊM {kq['them']} — danh sách giờ tin: {', '.join(kq['khoa'])}")
            return 0
        if ns.lenh == "kiem-sau-ky":
            kq = kiem_sau_ky(ns.dir, ns.tin_cay, key_id=ns.key_id, commit=ns.commit)
            for t, v in kq["kiem"].items():
                print(f"  {'ĐẠT' if v else 'LỖI'}  {t}")
            print(f"{kq['phien_ban']} commit {kq['commit']} ký bởi {kq['key_id']} — manifest {kq['manifest_sha256']}")
            if ns.json:
                with open(ns.json, "x", encoding="utf-8") as f:
                    json.dump(kq, f, ensure_ascii=False, indent=1)
            print("KẾT QUẢ:", "ĐẠT" if kq["dat"] else "KHÔNG ĐẠT — DỪNG trước phân phối")
            return 0 if kq["dat"] else 1
        if ns.lenh == "feed":
            kq = dong_feed(ns.dir, ns.tin_cay, ns.out)
            print(f"ZIP: {kq['zip']} — {kq['zip_byte']} byte, sha256 {kq['zip_sha256']}")
            print(f"SHA256SUMS: {kq['sha256sums']}\nKhối PowerShell: {kq['khoi_powershell']}")
            return 0
        if ns.lenh == "kit":
            with open(ns.lock_launcher, "rb") as f:
                lk = f.read()
            kq = dung_kit(ns.repo, ns.commit, lk, ns.tin_cay, ns.out, cho_khoa_thu=ns.dien_tap)
            print(f"KIT: {kq['zip']} sha256 {kq['zip_sha256']} — commit {kq['commit']}, khoá {', '.join(kq['khoa'])}")
            return 0
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
