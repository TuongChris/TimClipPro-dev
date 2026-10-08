# -*- coding: utf-8 -*-
"""Cập nhật Stable có quản lý cho cài đặt managed (PC2) — docs/MANAGED_UPDATE.md.

Luồng: PC1 chuẩn bị + test → chủ dự án DUYỆT phát hành → PC2 kiểm/tải/xác minh/stage → chờ rảnh → kích hoạt.

Bất biến
========
* Chỉ nhận bản do khoá tin cậy ký: chữ ký Ed25519 trên ĐÚNG các byte của ``manifest.json``; khoá công
  khai tin cậy cài lúc bootstrap (ngoài luồng tải) — không bao giờ lấy khoá từ manifest chưa xác minh,
  không có nhánh "bỏ chữ ký khi lỗi". Nguồn thư mục cục bộ (test/offline) cũng phải qua chữ ký.
* Chính sách Stable tường minh: tag ``stable-X.Y.Z``, không draft/pre-release, manifest ký nói đúng kênh,
  đúng phiên bản của tag, đúng ứng dụng/nền tảng; chỉ TIẾN (không hạ bản); bản bị cách ly bị bỏ qua.
* Kiểm gói TRƯỚC khi chạy bất kỳ mã nào: kích thước + SHA-256 gói; giải nén an toàn (Zip Slip, đường dẫn
  tuyệt đối/ổ đĩa, symlink, tên trùng, tên thiết bị DOS, số file, tổng dung lượng, tỉ lệ nén) rồi đối
  chiếu TỪNG file với danh sách đã ký gián tiếp (``RELEASE_FILES.json`` có SHA-256 trong manifest).
* Release cài vào ``releases/<phiên bản>`` BẤT BIẾN; runtime tạo TẠI ĐƯỜNG DẪN CUỐI và chỉ đánh dấu sẵn
  sàng sau khi kiểm xong; không chạy pip vào môi trường đang dùng.
* Kích hoạt chỉ khi cổng bảo trì rút xong (không việc nào chạy); không giết việc — quá hạn thì hoãn.
* Nhật ký + con trỏ ``current``/``last_good`` ghi nguyên tử (file tạm + flush + fsync + replace). Mất điện
  ở bước nào cũng khôi phục theo nhật ký — không đoán "có bản mới" vì thấy thư mục.
* Migration tự động chỉ khi manifest khai ``tu_dong_an_toan`` — điều kiện đó BẮT BUỘC kèm
  ``tuong_thich_nguoc`` (bản trước chạy được trên DB đã nâng). Nhờ vậy quay mã về bản cũ KHÔNG cần khôi
  phục DB: không bao giờ tự khôi phục DB (không bao giờ làm việc đã gửi quay về chờ gửi).
* Bản lỗi bị CÁCH LY: không cài đi cài lại mỗi lần mở.

Mã của module này không gọi mạng ở thời điểm import; mạng chỉ qua ``NguonGitHub`` (production, chưa chạy
thật trong vòng phát triển — NOT_RUN) với timeout và danh sách host được phép.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import runtime_paths

UNG_DUNG = "TimClipPro"
DINH_DANG_MANIFEST = 1
KENH_STABLE = "stable"
NEN_TANG = "win_amd64"
TIEN_TO_TAG = "stable-"
PHIEN_BAN_LAUNCHER = 1
TEN_MANIFEST = "manifest.json"
TEN_CHU_KY = "manifest.json.sig"
TEN_DS_FILE = "RELEASE_FILES.json"
TEN_DAU_RELEASE = "MANAGED_RELEASE.json"      # = runtime_paths.TEN_DAU_RELEASE
TEN_SAN_SANG = ".san_sang.json"               # dấu release/runtime đã kiểm xong
TEN_HOAN = "hoan.json"                        # người dùng hoãn ÁP DỤNG (tải/stage vẫn làm)

GIOI_HAN_MANIFEST = 64 * 1024
GIOI_HAN_CHU_KY = 4 * 1024
GIOI_HAN_GOI = 400 * 1024 * 1024
GIOI_HAN_GIAI_NEN = 1536 * 1024 * 1024
GIOI_HAN_SO_FILE = 30000
GIOI_HAN_TI_LE_NEN = 250
SO_LAN_LOI_TOI_DA = 3                         # tải hỏng (hash) quá số lần → cách ly

# Trạng thái nhật ký
CHECKED = "CHECKED"
DOWNLOADING = "DOWNLOADING"
VERIFIED = "VERIFIED"
STAGED = "STAGED"
WAITING_IDLE = "WAITING_IDLE"
QUIESCED = "QUIESCED"
BACKED_UP = "BACKED_UP"
MIGRATING = "MIGRATING"
ACTIVATING = "ACTIVATING"
HEALTHCHECK = "HEALTHCHECK"
ACTIVE = "ACTIVE"
ROLLBACK = "ROLLBACK"
BLOCKED = "BLOCKED"
WAITING_APPROVAL = "WAITING_APPROVAL"
QUARANTINED = "QUARANTINED"
KET_THUC = (ACTIVE, BLOCKED, WAITING_APPROVAL, QUARANTINED)

_PB = re.compile(r"^(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_KEY_ID = re.compile(r"^[0-9a-f]{16}$")
_TEN_THIET_BI = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                 *(f"lpt{i}" for i in range(1, 10))}


class LoiCapNhat(RuntimeError):
    """Lỗi cập nhật đã phân loại; ``ma`` cho nhật ký/kiểm thử, thông điệp tiếng Việt."""

    def __init__(self, ma: str, thong_diep: str):
        super().__init__(thong_diep)
        self.ma = ma


class TuChoiGoi(LoiCapNhat):
    """Bản phát hành/gói bị TỪ CHỐI (chữ ký, nội dung, chính sách) — không chạy mã nào của nó."""


class LoiTamThoi(LoiCapNhat):
    """Lỗi CÓ THỂ chỉ tạm thời: health/migration không chạy được, quá hạn, CSDL đang bị khoá. Bộ cập nhật
    đếm lần theo phiên bản, chỉ cách ly sau ``SO_LAN_LOI_TOI_DA`` lần (máy chậm lúc 3 giờ sáng không được chặn
    vĩnh viễn một bản tốt)."""


class MatDien(BaseException):
    """CHỈ dùng trong kiểm thử: mô phỏng tiến trình chết ở một điểm (không bị ``except Exception`` bắt)."""


# ---------------------------------------------------------------------------
#  Phiên bản, manifest, chữ ký
# ---------------------------------------------------------------------------

def phan_tich_phien_ban(s: str) -> tuple:
    m = _PB.match(str(s or ""))
    if not m:
        raise LoiCapNhat("phien_ban", f"Phiên bản «{s}» không đúng dạng X.Y.Z.")
    return tuple(int(x) for x in m.groups())


@dataclass(frozen=True)
class Manifest:
    phien_ban: str
    kenh: str
    commit: str
    tree: str
    tao_luc: str
    goi_ten: str
    goi_kich_thuoc: int
    goi_sha256: str
    ds_file_sha256: str
    nen_tang: str
    python: str
    runtime_id: str
    lock_sha256: str
    lich_su: int
    tuong_thich_nguoc: bool
    tu_dong_an_toan: bool
    launcher_toi_thieu: int
    kho_dinh_dang: int
    sha256: str                     # của chính các byte manifest — định danh bản phát hành


def _lay(d: dict, khoa: str, kieu, *, ma="manifest"):
    if khoa not in d or not isinstance(d[khoa], kieu) or isinstance(d[khoa], bool) and kieu is int:
        raise TuChoiGoi(ma, f"Manifest thiếu hoặc sai kiểu trường «{khoa}».")
    return d[khoa]


def doc_manifest(raw: bytes) -> Manifest:
    if len(raw) > GIOI_HAN_MANIFEST:
        raise TuChoiGoi("manifest", "Manifest quá lớn.")
    try:
        d = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise TuChoiGoi("manifest", "Manifest không phải JSON UTF-8 hợp lệ.") from None
    if not isinstance(d, dict):
        raise TuChoiGoi("manifest", "Manifest phải là đối tượng JSON.")
    if _lay(d, "dinh_dang", int) != DINH_DANG_MANIFEST:
        raise TuChoiGoi("manifest", "Định dạng manifest không được hỗ trợ — cần launcher mới hơn.")
    if _lay(d, "ung_dung", str) != UNG_DUNG:
        raise TuChoiGoi("sai_ung_dung", "Manifest không phải của TimClipPro.")
    goi = _lay(d, "goi", dict)
    runtime = _lay(d, "runtime", dict)
    du_lieu = _lay(d, "du_lieu", dict)
    mig = _lay(d, "migration", dict)
    m = Manifest(
        phien_ban=_lay(d, "phien_ban", str), kenh=_lay(d, "kenh", str),
        commit=_lay(d, "commit", str), tree=_lay(d, "tree", str), tao_luc=_lay(d, "tao_luc", str),
        goi_ten=_lay(goi, "ten", str), goi_kich_thuoc=_lay(goi, "kich_thuoc", int),
        goi_sha256=_lay(goi, "sha256", str), ds_file_sha256=_lay(goi, "ds_file_sha256", str),
        nen_tang=_lay(d, "nen_tang", str), python=_lay(d, "python", str),
        runtime_id=_lay(runtime, "runtime_id", str), lock_sha256=_lay(runtime, "lock_sha256", str),
        lich_su=_lay(du_lieu, "lich_su", int), tuong_thich_nguoc=_lay(du_lieu, "tuong_thich_nguoc", bool),
        tu_dong_an_toan=_lay(mig, "tu_dong_an_toan", bool),
        launcher_toi_thieu=_lay(d, "launcher_toi_thieu", int),
        kho_dinh_dang=_lay(d, "kho_dinh_dang", int),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    phan_tich_phien_ban(m.phien_ban)
    if not (_HEX40.match(m.commit) and _HEX40.match(m.tree)):
        raise TuChoiGoi("manifest", "Manifest có commit/tree không hợp lệ.")
    if not (_HEX64.match(m.goi_sha256) and _HEX64.match(m.ds_file_sha256)
            and _HEX64.match(m.lock_sha256)):
        raise TuChoiGoi("manifest", "Manifest có mã băm không hợp lệ.")
    if m.goi_ten != f"{UNG_DUNG}-{m.phien_ban}-{m.nen_tang}.zip":
        raise TuChoiGoi("manifest", "Tên gói không khớp phiên bản/nền tảng.")
    if not 0 < m.goi_kich_thuoc <= GIOI_HAN_GOI:
        raise TuChoiGoi("manifest", "Kích thước gói khai báo vượt giới hạn.")
    if not _RUNTIME_ID.match(m.runtime_id):
        raise TuChoiGoi("manifest", "Mã runtime không hợp lệ.")
    if m.tu_dong_an_toan and not m.tuong_thich_nguoc:
        raise TuChoiGoi("manifest", "Migration «tự động an toàn» phải giữ tương thích ngược.")
    return m


def tao_key_id(khoa_cong_khai_raw: bytes) -> str:
    return hashlib.sha256(khoa_cong_khai_raw).hexdigest()[:16]


def doc_khoa_tin_cay(path: str) -> dict:
    """``{key_id: Ed25519PublicKey}`` từ file khoá tin cậy của cài đặt (cài lúc bootstrap)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        raise LoiCapNhat("khoa_tin_cay", "Không đọc được file khoá tin cậy — cần bootstrap lại."
                         ) from None
    kq = {}
    for k in (d.get("khoa") if isinstance(d, dict) else None) or []:
        try:
            raw = base64.b64decode(k["ed25519_pub_b64"], validate=True)
            pub = Ed25519PublicKey.from_public_bytes(raw)
        except (KeyError, TypeError, ValueError):
            raise LoiCapNhat("khoa_tin_cay", "File khoá tin cậy có khoá hỏng.") from None
        if k.get("key_id") != tao_key_id(raw):
            raise LoiCapNhat("khoa_tin_cay", "File khoá tin cậy có key_id không khớp khoá.")
        kq[k["key_id"]] = pub
    if not kq:
        raise LoiCapNhat("khoa_tin_cay", "Chưa có khoá tin cậy nào — tự cập nhật bị chặn.")
    return kq


def kiem_chu_ky(raw_manifest: bytes, raw_chu_ky: bytes, khoa_tin_cay: dict) -> str:
    """Xác minh chữ ký tách rời trên ĐÚNG các byte manifest. Trả key_id; sai → ``TuChoiGoi``."""
    from cryptography.exceptions import InvalidSignature

    if len(raw_chu_ky) > GIOI_HAN_CHU_KY:
        raise TuChoiGoi("chu_ky", "File chữ ký quá lớn.")
    try:
        env = json.loads(raw_chu_ky.decode("utf-8"))
        if env.get("thuat_toan") != "ed25519":
            raise ValueError
        key_id = str(env["key_id"])
        sig = base64.b64decode(env["chu_ky_b64"], validate=True)
    except (UnicodeDecodeError, ValueError, KeyError, TypeError, AttributeError):
        raise TuChoiGoi("chu_ky", "File chữ ký hỏng.") from None
    if not _KEY_ID.match(key_id) or key_id not in khoa_tin_cay:
        raise TuChoiGoi("chu_ky", "Manifest được ký bằng khoá KHÔNG tin cậy.")
    if len(sig) != 64:
        raise TuChoiGoi("chu_ky", "Chữ ký sai độ dài.")
    try:
        khoa_tin_cay[key_id].verify(sig, raw_manifest)
    except InvalidSignature:
        raise TuChoiGoi("chu_ky", "Chữ ký manifest KHÔNG hợp lệ.") from None
    return key_id


# ---------------------------------------------------------------------------
#  Nguồn phát hành
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BanPhatHanh:
    tag: str
    draft: bool
    prerelease: bool
    assets: tuple                  # tên asset (để biết có đủ hay không)
    tham_chieu: str = ""           # url/đường dẫn nội bộ của nguồn


class NguonThuMuc:
    """Nguồn là MỘT THƯ MỤC (USB, thư mục chia sẻ chỉ đọc, kiểm thử): ``<gốc>/<tag>/release.json`` +
    asset. Không phải đường tắt bảo mật: chữ ký + băm vẫn bắt buộc như nguồn GitHub."""

    def __init__(self, thu_muc: str):
        self.thu_muc = thu_muc

    def ds(self) -> list:
        kq = []
        if not os.path.isdir(self.thu_muc):
            return kq
        for tag in sorted(os.listdir(self.thu_muc)):
            goc = os.path.join(self.thu_muc, tag)
            meta = os.path.join(goc, "release.json")
            if not os.path.isfile(meta):
                continue
            try:
                with open(meta, encoding="utf-8") as f:
                    d = json.load(f)
            except (OSError, ValueError):
                continue
            kq.append(BanPhatHanh(tag=tag, draft=bool(d.get("draft")),
                                  prerelease=bool(d.get("prerelease")),
                                  assets=tuple(sorted(x for x in os.listdir(goc) if x != "release.json")),
                                  tham_chieu=goc))
        return kq

    def tai(self, ban: BanPhatHanh, ten: str, dich: str, gioi_han: int) -> None:
        if ten not in ban.assets or os.path.basename(ten) != ten:
            raise LoiCapNhat("tai", f"Bản phát hành thiếu asset «{ten}».")
        _chep_co_gioi_han(os.path.join(ban.tham_chieu, ten), dich, gioi_han)


def _chep_co_gioi_han(nguon: str, dich: str, gioi_han: int) -> None:
    da = 0
    with open(nguon, "rb") as fi, open(dich, "wb") as fo:
        while True:
            khoi = fi.read(1024 * 1024)
            if not khoi:
                break
            da += len(khoi)
            if da > gioi_han:
                raise TuChoiGoi("qua_lon", "Asset lớn hơn giới hạn — đã dừng tải.")
            fo.write(khoi)
        fo.flush()
        os.fsync(fo.fileno())


class NguonGitHub:
    """Nguồn production: GitHub Releases của MỘT repo cố định. HTTPS, timeout, chỉ theo redirect tới
    host được phép, giới hạn kích thước. CHƯA gọi thật trong vòng phát triển (NOT_RUN — cần pilot)."""

    HOST_DUOC_PHEP = ("api.github.com", "github.com", "objects.githubusercontent.com",
                      "release-assets.githubusercontent.com")
    THOI_GIAN_CHO = (10, 60)

    def __init__(self, repo: str, *, http=None):
        if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", repo or ""):
            raise LoiCapNhat("nguon", "Tên repo phát hành không hợp lệ.")
        self.repo = repo
        self._http = http

    def _phien(self):
        if self._http is None:
            import requests

            self._http = requests.Session()
        return self._http

    def _kiem_host(self, url: str) -> None:
        from urllib.parse import urlparse

        u = urlparse(url)
        if u.scheme != "https" or (u.hostname or "") not in self.HOST_DUOC_PHEP:
            raise TuChoiGoi("nguon", "URL phát hành ngoài danh sách host được phép.")

    def ds(self) -> list:
        url = f"https://api.github.com/repos/{self.repo}/releases?per_page=30"
        r = self._phien().get(url, timeout=self.THOI_GIAN_CHO,
                              headers={"Accept": "application/vnd.github+json"})
        self._kiem_host(getattr(r, "url", url) or url)
        r.raise_for_status()
        kq = []
        for x in r.json() if isinstance(r.json(), list) else []:
            assets = {a.get("name"): a.get("browser_download_url") for a in x.get("assets") or []
                      if isinstance(a, dict)}
            kq.append(BanPhatHanh(tag=str(x.get("tag_name") or ""), draft=bool(x.get("draft")),
                                  prerelease=bool(x.get("prerelease")),
                                  assets=tuple(sorted(k for k in assets if k)),
                                  tham_chieu=json.dumps(assets)))
        return kq

    SO_LAN_CHUYEN_HUONG = 5

    def tai(self, ban: BanPhatHanh, ten: str, dich: str, gioi_han: int) -> None:
        """Tải một asset, TỰ theo chuyển hướng: kiểm host TRƯỚC mỗi request (để requests tự theo thì request
        tới host lạ đã đi rồi mới biết)."""
        from urllib.parse import urljoin

        url = json.loads(ban.tham_chieu or "{}").get(ten)
        if not url:
            raise LoiCapNhat("tai", f"Bản phát hành thiếu asset «{ten}».")
        hien = url
        for _ in range(self.SO_LAN_CHUYEN_HUONG + 1):
            self._kiem_host(hien)
            r = self._phien().get(hien, timeout=self.THOI_GIAN_CHO, stream=True, allow_redirects=False)
            if getattr(r, "status_code", 200) in (301, 302, 303, 307, 308):
                hien = urljoin(hien, (getattr(r, "headers", None) or {}).get("Location", ""))
                with contextlib.suppress(Exception):
                    r.close()
                continue
            break
        else:
            raise LoiCapNhat("tai", "Quá nhiều lần chuyển hướng khi tải bản phát hành.")
        with r:
            for h in [*getattr(r, "history", []), r]:
                self._kiem_host(getattr(h, "url", hien))
            r.raise_for_status()
            da = 0
            with open(dich, "wb") as fo:
                for khoi in r.iter_content(1024 * 1024):
                    da += len(khoi)
                    if da > gioi_han:
                        raise TuChoiGoi("qua_lon", "Asset lớn hơn giới hạn — đã dừng tải.")
                    fo.write(khoi)
                fo.flush()
                os.fsync(fo.fileno())


def loc_ung_vien(ds_ban: list, *, hien_tai: str, cach_ly: dict) -> tuple:
    """Lọc theo SIÊU DỮ LIỆU (trước khi tải gì): ``(danh sách giảm dần theo phiên bản, lý do bỏ)``.
    Manifest ký sẽ được kiểm lại khớp tag sau khi tải."""
    hien = phan_tich_phien_ban(hien_tai) if hien_tai else (0, 0, 0)
    tot, bo = [], []
    for b in ds_ban:
        if b.draft or b.prerelease:
            bo.append(f"{b.tag}: bản nháp/pre-release")
            continue
        if not b.tag.startswith(TIEN_TO_TAG):
            bo.append(f"{b.tag}: không phải tag Stable")
            continue
        try:
            pb = phan_tich_phien_ban(b.tag[len(TIEN_TO_TAG):])
        except LoiCapNhat:
            bo.append(f"{b.tag}: phiên bản sai dạng")
            continue
        if pb <= hien:
            continue                                   # không hạ bản, không cài lại bản đang chạy
        ver = b.tag[len(TIEN_TO_TAG):]
        if ver in cach_ly:
            bo.append(f"{b.tag}: đang bị cách ly ({cach_ly[ver].get('ly_do', '')})")
            continue
        if not {TEN_MANIFEST, TEN_CHU_KY} <= set(b.assets):
            bo.append(f"{b.tag}: thiếu manifest/chữ ký")
            continue
        tot.append((pb, b))
    tot.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in tot], bo


# ---------------------------------------------------------------------------
#  Giải nén an toàn + kiểm file
# ---------------------------------------------------------------------------

def _ten_hop_le(ten: str) -> bool:
    if not ten or ten.startswith(("/", "\\")) or "\\" in ten or ":" in ten or "\x00" in ten:
        return False
    for phan in ten.rstrip("/").split("/"):
        if phan in ("", ".", "..") or phan != phan.rstrip(" ."):
            return False
        if phan.split(".")[0].lower() in _TEN_THIET_BI:
            return False
        if any(c in phan for c in '<>"|?*') or any(ord(c) < 32 for c in phan):
            return False
    return True


def giai_nen_an_toan(zip_path: str, dich: str, *, gioi_han_tong: int = GIOI_HAN_GIAI_NEN,
                     gioi_han_so_file: int = GIOI_HAN_SO_FILE, ghi=None) -> list:
    """Giải nén vào ``dich`` (CHƯA tồn tại). Mọi mục được kiểm TRƯỚC khi ghi byte nào; dung lượng đếm
    theo byte THẬT khi ghi (không tin header). Lỗi → xoá ``dich``. Trả danh sách file (posix)."""
    if os.path.exists(dich):
        raise LoiCapNhat("giai_nen", "Thư mục giải nén đã tồn tại.")
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        raise TuChoiGoi("zip", "Gói không phải ZIP hợp lệ.") from None
    with zf:
        muc = zf.infolist()
        if len(muc) > gioi_han_so_file:
            raise TuChoiGoi("zip", "Gói có quá nhiều file.")
        da_thay, ds = set(), []
        tong_khai = 0
        for i in muc:
            ten = i.filename
            if not _ten_hop_le(ten):
                raise TuChoiGoi("zip_slip", "Gói chứa đường dẫn không an toàn.")
            loai = (i.external_attr >> 16) & 0o170000
            if loai == stat.S_IFLNK or (loai and loai not in (stat.S_IFREG, stat.S_IFDIR)):
                raise TuChoiGoi("zip_symlink", "Gói chứa liên kết/kiểu file đặc biệt.")
            if i.flag_bits & 0x1:
                raise TuChoiGoi("zip", "Gói có mục bị mã hoá.")
            khoa = ten.rstrip("/").lower()
            if khoa in da_thay:
                raise TuChoiGoi("zip", "Gói có hai mục trùng tên.")
            da_thay.add(khoa)
            if not ten.endswith("/"):
                if i.file_size > 0 and i.compress_size == 0 or (
                        i.compress_size and i.file_size / i.compress_size > GIOI_HAN_TI_LE_NEN):
                    raise TuChoiGoi("zip_bom", "Gói có tỉ lệ nén bất thường.")
                tong_khai += i.file_size
                ds.append(ten)
        if tong_khai > gioi_han_tong:
            raise TuChoiGoi("zip_bom", "Gói giải nén vượt giới hạn dung lượng.")
        os.makedirs(dich)
        try:
            da_ghi = 0
            for i in muc:
                dich_file = os.path.join(dich, *i.filename.rstrip("/").split("/"))
                if not os.path.abspath(dich_file).startswith(os.path.abspath(dich) + os.sep):
                    raise TuChoiGoi("zip_slip", "Gói chứa đường dẫn không an toàn.")
                if i.filename.endswith("/"):
                    os.makedirs(dich_file, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(dich_file), exist_ok=True)
                with zf.open(i) as fi, open(dich_file, "xb") as fo:
                    while True:
                        khoi = fi.read(1024 * 1024)
                        if not khoi:
                            break
                        da_ghi += len(khoi)
                        if da_ghi > gioi_han_tong:
                            raise TuChoiGoi("zip_bom", "Gói giải nén vượt giới hạn dung lượng.")
                        if ghi is None:
                            fo.write(khoi)
                        else:
                            ghi(fo, khoi)
                    fo.flush()
                    os.fsync(fo.fileno())                # file bền TRƯỚC dấu sẵn sàng (fsync) của release
        except BaseException:
            shutil.rmtree(dich, ignore_errors=True)
            raise
    return sorted(ds)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for khoi in iter(lambda: f.read(1024 * 1024), b""):
            h.update(khoi)
    return h.hexdigest()


def _la_lien_ket(path: str) -> bool:
    st = os.lstat(path)
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def kiem_cay_release(thu_muc: str, m: Manifest) -> None:
    """Đối chiếu cây đã giải nén với ``RELEASE_FILES.json`` (băm của danh sách nằm trong manifest ĐÃ KÝ):
    đủ file, đúng băm, không thừa, không liên kết/reparse point."""
    ds_path = os.path.join(thu_muc, TEN_DS_FILE)
    try:
        with open(ds_path, "rb") as f:
            raw = f.read()
    except OSError:
        raise TuChoiGoi("ds_file", "Gói thiếu danh sách file.") from None
    if hashlib.sha256(raw).hexdigest() != m.ds_file_sha256:
        raise TuChoiGoi("ds_file", "Danh sách file không khớp manifest đã ký.")
    try:
        ds = json.loads(raw.decode("utf-8"))["files"]
        mong = {str(x["path"]): (int(x["size"]), str(x["sha256"])) for x in ds}
    except (ValueError, KeyError, TypeError):
        raise TuChoiGoi("ds_file", "Danh sách file hỏng.") from None
    thuc = {}
    for goc, thu_muc_con, files in os.walk(thu_muc):
        for ten in thu_muc_con + files:
            if _la_lien_ket(os.path.join(goc, ten)):
                raise TuChoiGoi("zip_symlink", "Cây release chứa liên kết/reparse point.")
        for ten in files:
            p = os.path.join(goc, ten)
            rel = os.path.relpath(p, thu_muc).replace(os.sep, "/")
            if rel in (TEN_DS_FILE, TEN_SAN_SANG, TEN_MANIFEST, TEN_CHU_KY):
                continue                 # manifest + chữ ký: kiểm bằng chữ ký, không bằng danh sách
            thuc[rel] = p
    if set(thuc) != set(mong):
        raise TuChoiGoi("ds_file", "Cây release thừa/thiếu file so với danh sách đã ký.")
    for rel, p in thuc.items():
        kt, bam = mong[rel]
        if os.path.getsize(p) != kt or _sha256_file(p) != bam:
            raise TuChoiGoi("ds_file", f"File «{rel}» không khớp băm đã ký.")


# ---------------------------------------------------------------------------
#  Ghi nguyên tử, bố cục cài đặt, nhật ký
# ---------------------------------------------------------------------------

SO_LAN_THU_THAY_FILE = 10


def ghi_json_nguyen_tu(path: str, obj) -> None:
    """File tạm CÙNG thư mục → flush → fsync → os.replace (MoveFileEx thay thế nguyên tử trên NTFS).
    Windows không fsync được thư mục — giới hạn đã ghi trong tài liệu.

    Windows: ``os.replace`` bị từ chối (``PermissionError``) khi tiến trình khác ĐANG MỞ file đích để đọc
    (Python mở file không kèm FILE_SHARE_DELETE) — giao diện/doctor/``update status`` đọc các file này vài
    mili-giây mỗi lần. Thử lại có hạn (~2,75 s) thay vì để lỗi cắt ngang một bước cập nhật."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tam = f"{path}.tmp-{uuid.uuid4().hex[:8]}"
    try:
        with open(tam, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        for lan in range(SO_LAN_THU_THAY_FILE):
            try:
                os.replace(tam, path)
                break
            except PermissionError:
                if lan == SO_LAN_THU_THAY_FILE - 1:
                    raise
                time.sleep(0.05 * (lan + 1))
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tam)
        raise


def doc_json(path: str, *, mac_dinh=None, bat_buoc_hop_le: bool = True):
    """Thiếu file → ``mac_dinh``. File HỎNG → lỗi (không "reset về mặc định" — brief §16)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return mac_dinh
    except (OSError, ValueError):
        if not bat_buoc_hop_le:
            return mac_dinh
        raise LoiCapNhat("trang_thai_hong", f"File trạng thái cập nhật hỏng: {os.path.basename(path)}"
                         " — cần kiểm tay (không tự đặt lại).") from None


# Thư mục con của cài đặt mà bộ cập nhật SỞ HỮU — được quyền xoá/thay toàn bộ (MR-P1-01: không gì khác được nằm
# trong đó, nhất là state root và thư mục nguồn phát hành).
VUNG_UPDATER = ("releases", "environments", "update_state", "staging")


def thong_diep_bo_cuc(ly_do: str) -> str:
    return ("Bố cục thư mục không an toàn — thư mục cài đặt và state root phải TÁCH BIỆT (không trùng, không thư "
            f"mục nào nằm trong thư mục kia): {ly_do} Không chạy để tránh mất dữ liệu; KHÔNG tự di chuyển hay xoá "
            "gì — sao lưu rồi làm theo HUONG_DAN_PC2 mục «Bố cục thư mục».")


@dataclass(frozen=True)
class CaiDat:
    """Bố cục MỘT cài đặt managed. Dựng là kiểm: thư mục cài đặt và state root chồng nhau → ``LoiCapNhat`` mã
    ``bo_cuc`` (launcher, giao diện, bootstrap đều dựng qua đây — không có đường nào chạy với bố cục lồng nhau)."""

    goc: str                         # installation root
    state_root: str

    def __post_init__(self):
        self.kiem_bo_cuc()

    def kiem_bo_cuc(self) -> None:
        ly_do = runtime_paths.ly_do_bo_cuc(self.goc, self.state_root)
        if ly_do:
            raise LoiCapNhat("bo_cuc", thong_diep_bo_cuc(ly_do))

    @property
    def vung_updater(self) -> tuple:
        return tuple(os.path.join(self.goc, t) for t in VUNG_UPDATER)

    def kiem_xoa(self, path: str, bao_ve: tuple = ()) -> None:
        """Chốt NGAY TRƯỚC khi updater xoá/thay một cây thư mục: ``path`` phải thuộc vùng updater sở hữu, không
        chồng lên state root, không chứa thư mục được bảo vệ (``bao_ve`` — nguồn phát hành) — so cả qua
        junction/symlink. Sai → ``LoiCapNhat("bo_cuc")``, không xoá gì."""
        if not any(runtime_paths.nam_trong(path, v) for v in self.vung_updater):
            raise LoiCapNhat("bo_cuc", thong_diep_bo_cuc(f"«{path}» không thuộc vùng bộ cập nhật sở hữu."))
        if runtime_paths.chong_lan(path, self.state_root):
            raise LoiCapNhat("bo_cuc", thong_diep_bo_cuc(f"xoá «{path}» sẽ chạm vào state root «{self.state_root}»."))
        for p in bao_ve:
            if p and runtime_paths.nam_trong(p, path):
                raise LoiCapNhat("bo_cuc", thong_diep_bo_cuc(f"xoá «{path}» sẽ xoá cả «{p}»."))

    @property
    def releases(self) -> str:
        return os.path.join(self.goc, "releases")

    @property
    def environments(self) -> str:
        return os.path.join(self.goc, "environments")

    @property
    def staging(self) -> str:
        return os.path.join(self.goc, "staging")

    @property
    def update_state(self) -> str:
        return os.path.join(self.goc, "update_state")

    @property
    def data_dir(self) -> str:
        return os.path.join(self.state_root, "data")

    @property
    def backups(self) -> str:
        return os.path.join(self.state_root, "backups")

    def file_trang_thai(self, ten: str) -> str:
        return os.path.join(self.update_state, ten)

    def release_dir(self, phien_ban: str) -> str:
        return os.path.join(self.releases, phien_ban)

    def runtime_dir(self, runtime_id: str) -> str:
        return os.path.join(self.environments, runtime_id)


def _bay_gio() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def dat_hoan(goc_cai_dat: str, gio: float) -> dict:
    """Người dùng hoãn áp dụng cập nhật ``gio`` giờ (UI «Phiên bản và cập nhật»)."""
    d = {"den": time.time() + max(0.0, float(gio)) * 3600, "luc": _bay_gio()}
    ghi_json_nguyen_tu(os.path.join(goc_cai_dat, "update_state", TEN_HOAN), d)
    return d


def bo_hoan(goc_cai_dat: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.remove(os.path.join(goc_cai_dat, "update_state", TEN_HOAN))


def doc_hoan(goc_cai_dat: str) -> Optional[float]:
    """Thời điểm (epoch) hết hoãn nếu còn hiệu lực; hết hạn / không có / hỏng → ``None``."""
    d = doc_json(os.path.join(goc_cai_dat, "update_state", TEN_HOAN), bat_buoc_hop_le=False)
    den = d.get("den") if isinstance(d, dict) else None
    return float(den) if isinstance(den, (int, float)) and den > time.time() else None


class NhatKy:
    """``update_state/journal.json`` — trạng thái lượt cập nhật hiện tại + lịch sử chuyển trạng thái."""

    def __init__(self, cai_dat: CaiDat):
        self.path = cai_dat.file_trang_thai("journal.json")

    def doc(self) -> Optional[dict]:
        d = doc_json(self.path)
        if d is not None and not (isinstance(d, dict) and isinstance(d.get("trang_thai"), str)):
            raise LoiCapNhat("trang_thai_hong", "Nhật ký cập nhật hỏng — cần kiểm tay.")
        return d

    def ghi(self, trang_thai: str, **them) -> dict:
        d = self.doc() or {}
        d.update(them)
        d["trang_thai"] = trang_thai
        ls = list(d.get("lich_su") or [])[-49:]
        ls.append({"trang_thai": trang_thai, "luc": _bay_gio(),
                   **({"loi": them["loi"]} if them.get("loi") else {})})
        d["lich_su"] = ls
        ghi_json_nguyen_tu(self.path, d)
        return d


# ---------------------------------------------------------------------------
#  Điều phối
# ---------------------------------------------------------------------------

class KetQua:
    """Kết quả một thao tác cập nhật (cho launcher/UI)."""

    def __init__(self, trang_thai: str, phien_ban: str = "", thong_diep: str = "",
                 chi_tiet: Optional[list] = None):
        self.trang_thai = trang_thai
        self.phien_ban = phien_ban
        self.thong_diep = thong_diep
        self.chi_tiet = list(chi_tiet or [])

    def __repr__(self) -> str:
        return f"KetQua({self.trang_thai!r}, {self.phien_ban!r}, {self.thong_diep!r})"


BAN = "BAN"              # một lượt cập nhật khác đang chạy
KHONG_CO = "KHONG_CO"    # không có bản mới hợp lệ
LOI = "LOI"              # lỗi mạng/đĩa — giữ nguyên bản đang chạy
TU_CHOI = "TU_CHOI"      # gói bị từ chối (chữ ký/băm/nội dung)


class CapNhat:
    """Bộ cập nhật của MỘT cài đặt managed. Phụ thuộc nặng đều TIÊM VÀO để kiểm thử trong sandbox:
    ``nguon`` (thư mục/GitHub), ``tao_moi_truong(m, release, runtime)`` (tạo runtime TẠI ĐƯỜNG DẪN CUỐI),
    ``kiem_suc_khoe(m, release, runtime, che_do) -> (ok, chi_tiết)``, ``di_chuyen(m, release, runtime)``
    (migration bằng mã MỚI), ``sao_luu(m) -> đường_dẫn``, ``phien_ban_db() -> int``, ``cong``
    (``maintenance_gate.CongBaoTri`` của state root). ``diem_dung(tên)`` chỉ để kiểm thử mất điện."""

    def __init__(self, cai_dat: CaiDat, *, nguon, khoa_tin_cay: dict, cong,
                 tao_moi_truong: Callable, kiem_suc_khoe: Callable, di_chuyen: Callable,
                 sao_luu: Callable, phien_ban_db: Callable[[], int],
                 diem_dung: Optional[Callable[[str], None]] = None,
                 launcher: int = PHIEN_BAN_LAUNCHER, han_cho_ranh_s: float = 600.0,
                 chu_ky_cho_s: float = 2.0):
        self.cd = cai_dat
        self.nguon = nguon
        self.khoa_tin_cay = khoa_tin_cay
        self.cong = cong
        self.tao_moi_truong = tao_moi_truong
        self.kiem_suc_khoe = kiem_suc_khoe
        self.di_chuyen = di_chuyen
        self.sao_luu = sao_luu
        self.phien_ban_db = phien_ban_db
        self.diem_dung = diem_dung or (lambda _ten: None)
        self.launcher = launcher
        self.han_cho_ranh_s = han_cho_ranh_s
        self.chu_ky_cho_s = chu_ky_cho_s
        self.nk = NhatKy(cai_dat)
        self._quyen = None
        self._sau = 0
        # Thư mục nguồn phát hành (USB / thư mục chép tay) nằm trong vùng updater thì lần dọn staging xoá luôn nó.
        thu_muc_nguon = getattr(nguon, "thu_muc", None)
        self._bao_ve = (os.path.abspath(thu_muc_nguon),) if thu_muc_nguon else ()
        for p in self._bao_ve:
            if any(runtime_paths.nam_trong(p, v) for v in cai_dat.vung_updater):
                raise LoiCapNhat("bo_cuc", f"Bố cục thư mục không an toàn: thư mục nguồn phát hành «{p}» nằm trong "
                                 "vùng bộ cập nhật được quyền xoá — chọn thư mục nguồn NGOÀI thư mục cài đặt.")

    # ---------- quyền updater (một lượt mỗi cài đặt) ----------

    @contextlib.contextmanager
    def _giu_quyen(self):
        """Khoá HĐH ``update_state/updater.lock`` — reentrant trong cùng đối tượng. Bận → ``LoiCapNhat``. Mỗi
        lượt kiểm LẠI bố cục trước khi đụng gì (junction có thể đổi đích sau khi dựng ``CaiDat``)."""
        if self._sau:
            self._sau += 1
            try:
                yield
            finally:
                self._sau -= 1
            return
        from khoa import DangChayRoi, KhoaTienTrinh

        self.cd.kiem_bo_cuc()
        os.makedirs(self.cd.update_state, exist_ok=True)
        khoa = KhoaTienTrinh(self.cd.file_trang_thai("updater.lock"), "cập nhật TimClipPro")
        try:
            khoa.__enter__()
        except DangChayRoi:
            raise LoiCapNhat(BAN, "Một lượt cập nhật khác đang chạy trên máy này.") from None
        self._sau = 1
        try:
            yield
        finally:
            self._sau = 0
            khoa.__exit__(None, None, None)

    # ---------- con trỏ ----------

    def hien_tai(self) -> Optional[dict]:
        return doc_json(self.cd.file_trang_thai("current.json"))

    def last_good(self) -> Optional[dict]:
        return doc_json(self.cd.file_trang_thai("last_good.json"))

    def cach_ly(self) -> dict:
        d = doc_json(self.cd.file_trang_thai("quarantine.json"), mac_dinh={})
        return d if isinstance(d, dict) else {}

    def _cach_ly(self, phien_ban: str, ly_do: str) -> None:
        d = self.cach_ly()
        d[phien_ban] = {"ly_do": ly_do[:300], "luc": _bay_gio()}
        ghi_json_nguyen_tu(self.cd.file_trang_thai("quarantine.json"), d)

    def bo_cach_ly(self, phien_ban: str) -> bool:
        """Người vận hành đã khắc phục nguyên nhân (vd. mạng, Python gốc) → bỏ cách ly MỘT phiên bản và xoá
        bộ đếm lỗi của nó; lần chuẩn bị sau xét lại từ đầu (vẫn đủ chữ ký/băm/health). ``False``: không bị
        cách ly."""
        with self._giu_quyen():
            d = self.cach_ly()
            if phien_ban not in d:
                return False
            del d[phien_ban]
            ghi_json_nguyen_tu(self.cd.file_trang_thai("quarantine.json"), d)
            for ten in ("loi_tai.json", "loi_runtime.json", "loi_tam_thoi.json"):
                p = self.cd.file_trang_thai(ten)
                dem = doc_json(p, mac_dinh={}, bat_buoc_hop_le=False) or {}
                if isinstance(dem, dict) and dem.pop(phien_ban, None) is not None:
                    ghi_json_nguyen_tu(p, dem)
            return True

    def _dem_loi(self, ten_file: str, phien_ban: str) -> int:
        p = self.cd.file_trang_thai(ten_file)
        d = doc_json(p, mac_dinh={}, bat_buoc_hop_le=False) or {}
        d[phien_ban] = int(d.get(phien_ban, 0)) + 1
        ghi_json_nguyen_tu(p, d)
        return d[phien_ban]

    def _dem_loi_tai(self, phien_ban: str) -> int:
        return self._dem_loi("loi_tai.json", phien_ban)

    def _runtime_dang_dung(self, rt: str) -> bool:
        """Runtime đang được con trỏ ``current``/``last_good`` dùng (nhiều release cùng lock dùng CHUNG một
        runtime). Con trỏ hỏng → ``LoiCapNhat`` (không đoán, không xoá gì)."""
        p = os.path.normcase(os.path.abspath(rt))
        for con_tro in (self.hien_tai(), self.last_good()):
            if isinstance(con_tro, dict) and \
                    os.path.normcase(os.path.abspath(str(con_tro.get("runtime") or ""))) == p:
                return True
        return False

    def _con_tro_truoc(self, sha_ung_vien: str) -> Optional[dict]:
        """Con trỏ để QUAY VỀ khi ứng viên (manifest ``sha_ung_vien``) lỗi: con trỏ TRƯỚC kích hoạt ghi trong
        nhật ký, rồi mới tới last_good — KHÔNG BAO GIỜ là chính ứng viên (last_good có thể đã trỏ sang nó nếu
        lượt trước bị cắt ngang đúng lúc). ``None``: không có bản trước (cài lần đầu)."""
        nk = self.nk.doc() or {}
        for ung in (nk.get("con_tro_cu"), self.last_good()):
            if isinstance(ung, dict) and ung.get("manifest_sha256") and \
                    ung.get("manifest_sha256") != sha_ung_vien:
                return ung
        return None

    def _ve_con_tro_truoc(self, sha_ung_vien: str) -> Optional[dict]:
        """Đặt ``current`` (và sửa ``last_good``) về con trỏ trước; không có thì bỏ ``current``."""
        tot = self._con_tro_truoc(sha_ung_vien)
        if tot:
            ghi_json_nguyen_tu(self.cd.file_trang_thai("current.json"), tot)
            lg = self.last_good()
            if not isinstance(lg, dict) or lg.get("manifest_sha256") != tot.get("manifest_sha256"):
                ghi_json_nguyen_tu(self.cd.file_trang_thai("last_good.json"), tot)
        else:
            with contextlib.suppress(FileNotFoundError):
                os.remove(self.cd.file_trang_thai("current.json"))
            lg = self.last_good()
            if isinstance(lg, dict) and lg.get("manifest_sha256") == sha_ung_vien:
                with contextlib.suppress(FileNotFoundError):
                    os.remove(self.cd.file_trang_thai("last_good.json"))
        return tot

    def _con_tro(self, m: Manifest) -> dict:
        return {"phien_ban": m.phien_ban, "release": self.cd.release_dir(m.phien_ban),
                "runtime_id": m.runtime_id, "runtime": self.cd.runtime_dir(m.runtime_id),
                "manifest_sha256": m.sha256, "luc": _bay_gio()}

    # ---------- tìm ứng viên ----------

    def _manifest_ung_vien(self, ban: BanPhatHanh, tam: str) -> tuple:
        os.makedirs(tam, exist_ok=True)
        p_m, p_s = os.path.join(tam, TEN_MANIFEST), os.path.join(tam, TEN_CHU_KY)
        self.nguon.tai(ban, TEN_MANIFEST, p_m, GIOI_HAN_MANIFEST)
        self.nguon.tai(ban, TEN_CHU_KY, p_s, GIOI_HAN_CHU_KY)
        with open(p_m, "rb") as f:
            raw_m = f.read()
        with open(p_s, "rb") as f:
            raw_s = f.read()
        kiem_chu_ky(raw_m, raw_s, self.khoa_tin_cay)              # TRƯỚC khi tin nội dung
        m = doc_manifest(raw_m)
        if m.kenh != KENH_STABLE:
            raise TuChoiGoi("kenh", "Manifest không thuộc kênh Stable.")
        if ban.tag != TIEN_TO_TAG + m.phien_ban:
            raise TuChoiGoi("tag", "Phiên bản trong manifest không khớp tag.")
        if m.nen_tang != NEN_TANG:
            raise TuChoiGoi("nen_tang", "Bản phát hành không dành cho nền tảng này.")
        if m.goi_ten not in ban.assets:
            raise TuChoiGoi("thieu_goi", "Bản phát hành thiếu gói.")
        return m, raw_m, raw_s

    def _tim_ung_vien(self) -> tuple:
        """``(ban, manifest, raw_m, raw_s, lý_do_bỏ)`` của bản Stable hợp lệ CAO NHẤT, hoặc ``ban=None``.
        Manifest ĐÃ KÝ HỢP LỆ mà sai chính sách → cách ly đúng phiên bản đó. Chữ ký sai/thiếu gói chỉ BỎ QUA
        lần này: có thể là thư mục chép dở hoặc bản đang tải lên — cách ly theo SỐ phiên bản sẽ chặn vĩnh
        viễn bản đúng chép/tải lên sau đó (manifest nhỏ, kiểm lại mỗi lần rất rẻ)."""
        hien = (self.hien_tai() or {}).get("phien_ban", "")
        ds, bo = loc_ung_vien(self.nguon.ds(), hien_tai=hien, cach_ly=self.cach_ly())
        tam = os.path.join(self.cd.staging, "kiem-" + uuid.uuid4().hex[:8])
        try:
            for ban in ds:
                try:
                    m, raw_m, raw_s = self._manifest_ung_vien(ban, tam)
                except TuChoiGoi as e:
                    if e.ma not in ("chu_ky", "thieu_goi", "nguon", "qua_lon"):
                        self._cach_ly(ban.tag[len(TIEN_TO_TAG):], str(e))
                    bo.append(f"{ban.tag}: {e}")
                    continue
                if m.launcher_toi_thieu > self.launcher:
                    bo.append(f"{ban.tag}: cần launcher mới hơn (≥ {m.launcher_toi_thieu}) — cài lại "
                              "bootstrap kit mới")
                    continue
                return ban, m, raw_m, raw_s, bo
            return None, None, None, None, bo
        finally:
            self._xoa_cay(tam)

    def kiem_tra(self) -> KetQua:
        """CHỈ kiểm (tải + xác minh manifest, chưa tải gói, không đổi nhật ký). Lỗi mạng → ``LOI``:
        ứng dụng vẫn chạy bản đang có."""
        try:
            with self._giu_quyen():
                ban, m, _, _, bo = self._tim_ung_vien()
        except LoiCapNhat as e:
            return KetQua(e.ma if e.ma == BAN else LOI, "", str(e))
        except Exception as e:  # noqa: BLE001 — mạng/đĩa/thư viện thiếu: vẫn chạy bản hiện tại
            return KetQua(LOI, "", f"Không kiểm được bản mới ({type(e).__name__}) — vẫn chạy bản hiện tại.")
        if ban is None:
            return KetQua(KHONG_CO, "", "Không có bản Stable mới hợp lệ.", bo)
        return KetQua(CHECKED, m.phien_ban, f"Có bản Stable {m.phien_ban}.", bo)

    # ---------- chuẩn bị (tải + stage) ----------

    def chuan_bi(self) -> KetQua:
        """Tải + xác minh + giải nén + kiểm cây + runtime + health staging → STAGED. Không đụng bản
        đang chạy; mọi lỗi giữ nguyên bản hiện tại."""
        try:
            with self._giu_quyen():
                self._phuc_hoi()
                return self._chuan_bi()
        except LoiCapNhat as e:
            return KetQua(e.ma if e.ma == BAN else LOI, "", str(e))
        except Exception as e:  # noqa: BLE001 — lỗi lạ không được làm sập launcher; bản đang chạy giữ nguyên
            return KetQua(LOI, "", f"Lỗi không lường trước khi chuẩn bị ({type(e).__name__}) — giữ bản "
                          "hiện tại.")

    def _chan_theo_lich_su(self, m: Manifest) -> Optional[KetQua]:
        """Chính sách dữ liệu, kiểm TRƯỚC khi tải/rút cổng/sao lưu: schema trên máy mới hơn bản phát hành →
        BLOCKED; bản mới cần nâng lịch sử mà KHÔNG khai tự động an toàn → WAITING_APPROVAL (không tải, không
        sao lưu, không rút cổng — lặp lại mỗi lần chỉ tốn một lần đọc manifest). Máy mới chưa có lịch sử
        (``phien_ban_db() is None``) không phải migration."""
        db = self.phien_ban_db()
        if db is None:
            return None
        if db > m.lich_su:
            self.nk.ghi(BLOCKED, ung_vien=m.phien_ban, con_tro_moi=None,
                        loi="Lịch sử trên máy mới hơn bản phát hành (schema quá mới).")
            return KetQua(BLOCKED, m.phien_ban, "Schema dữ liệu mới hơn bản phát hành — chặn.")
        if db < m.lich_su and not m.tu_dong_an_toan:
            self.nk.ghi(WAITING_APPROVAL, ung_vien=m.phien_ban, con_tro_moi=None,
                        loi="Bản mới cần nâng lịch sử nhưng chưa được đánh giá tự động an toàn — chờ duyệt.")
            return KetQua(WAITING_APPROVAL, m.phien_ban, "Cần duyệt migration trước khi cập nhật.")
        return None

    def _chuan_bi(self) -> KetQua:
        nk = self.nk.doc() or {}
        try:
            ban, m, raw_m, raw_s, bo = self._tim_ung_vien()
        except (OSError, ValueError) as e:
            return KetQua(LOI, "", f"Không kiểm được bản mới ({type(e).__name__}) — vẫn chạy bản hiện tại.")
        if ban is None:
            return KetQua(KHONG_CO, "", "Không có bản Stable mới hợp lệ.", bo)
        if (nk.get("trang_thai") == STAGED and nk.get("ung_vien") == m.phien_ban
                and self._manifest_da_cai(nk.get("con_tro_moi") or {}) is not None):
            return KetQua(STAGED, m.phien_ban, f"Bản {m.phien_ban} đã sẵn sàng, chờ lúc rảnh để áp dụng.")
        chan = self._chan_theo_lich_su(m)
        if chan is not None:
            return chan
        phien = uuid.uuid4().hex[:12]
        tam = os.path.join(self.cd.staging, phien)
        self.nk.ghi(CHECKED, ung_vien=m.phien_ban, tag=ban.tag, phien=phien, con_tro_moi=None,
                    con_tro_cu=None, manifest_sha256=m.sha256, loi="")
        try:
            self.nk.ghi(DOWNLOADING)
            self.diem_dung(DOWNLOADING)
            os.makedirs(tam, exist_ok=True)
            goi = os.path.join(tam, m.goi_ten)
            self.nguon.tai(ban, m.goi_ten, goi, m.goi_kich_thuoc)
            if os.path.getsize(goi) != m.goi_kich_thuoc or _sha256_file(goi) != m.goi_sha256:
                if self._dem_loi_tai(m.phien_ban) >= SO_LAN_LOI_TOI_DA:
                    self._cach_ly(m.phien_ban, "gói tải về không khớp băm nhiều lần")
                raise TuChoiGoi("bam_goi", "Gói tải về không khớp kích thước/băm đã ký.")
            self.nk.ghi(VERIFIED)
            self.diem_dung(VERIFIED)
            rel = self.cd.release_dir(m.phien_ban)
            if not self._release_san_sang(rel, m):
                self._cai_release(goi, rel, m, raw_m, raw_s, phien)
            self.diem_dung("RELEASE_READY")
            rt = self.cd.runtime_dir(m.runtime_id)
            if not self._runtime_san_sang(rt, m):
                if os.path.exists(rt):
                    if self._runtime_dang_dung(rt):
                        # Runtime DÙNG CHUNG với bản đang chạy mà dấu sẵn sàng hỏng: xoá là phá bản đang
                        # chạy (Windows còn xoá dở vì file đang mở) — dừng, cần người kiểm.
                        raise LoiCapNhat("runtime_dang_dung", "Dấu sẵn sàng của runtime ĐANG DÙNG bị hỏng — "
                                         "không xoá/tạo lại; chạy «launcher.py doctor» và báo chủ dự án.")
                    self._xoa_cay(rt, bo_qua_loi=False)  # dở dang (chưa có dấu sẵn sàng)
                self._tao_runtime(m, rel, rt)            # tạo TẠI ĐƯỜNG DẪN CUỐI
                ghi_json_nguyen_tu(os.path.join(rt, TEN_SAN_SANG),
                                   {"lock_sha256": m.lock_sha256, "luc": _bay_gio()})
            self.diem_dung("RUNTIME_READY")
            ok, chi_tiet, tam_thoi = self._kiem(m, rel, rt, "staging")
            if not ok and tam_thoi and not self._het_luot_tam_thoi(m.phien_ban):
                self.nk.ghi(CHECKED, loi=f"Health check ở staging chưa chạy được: {chi_tiet} — sẽ thử lại.")
                return KetQua(LOI, m.phien_ban, f"Health check chưa chạy được ({chi_tiet}) — giữ bản hiện tại, "
                              "thử lại lần sau.")
            if not ok:
                self._cach_ly(m.phien_ban, f"health check staging: {chi_tiet}")
                self.nk.ghi(QUARANTINED, loi=f"Health check ở staging lỗi: {chi_tiet}")
                return KetQua(QUARANTINED, m.phien_ban, "Bản mới không qua kiểm tra — đã cách ly.")
            self.nk.ghi(STAGED, con_tro_moi=self._con_tro(m))
            self.diem_dung(STAGED)
            return KetQua(STAGED, m.phien_ban, f"Bản {m.phien_ban} đã sẵn sàng, chờ lúc rảnh để áp dụng.")
        except TuChoiGoi as e:
            # Nội dung ĐÃ KÝ sai một cách tất định (zip độc hại, danh sách file, lock chưa băm/không khớp)
            # → cách ly: tải lại cũng y hệt.
            if e.ma in ("zip_slip", "zip_symlink", "zip_bom", "zip", "ds_file", "lock", "lock_chua_bam"):
                self._cach_ly(m.phien_ban, str(e))
            self.nk.ghi(CHECKED, loi=str(e))
            return KetQua(TU_CHOI, m.phien_ban, str(e))
        except LoiCapNhat as e:
            self.nk.ghi(CHECKED, loi=str(e))
            return KetQua(LOI, m.phien_ban, str(e))
        except (OSError, ValueError) as e:
            self.nk.ghi(CHECKED, loi=f"Lỗi đĩa/mạng khi chuẩn bị ({type(e).__name__}).")
            return KetQua(LOI, m.phien_ban, f"Lỗi đĩa/mạng khi chuẩn bị ({type(e).__name__}) — giữ bản "
                          "hiện tại.")
        except Exception as e:  # noqa: BLE001 — lỗi lạ: ghi vào nhật ký, giữ bản hiện tại
            with contextlib.suppress(Exception):
                self.nk.ghi(CHECKED, loi=f"Lỗi không lường trước khi chuẩn bị ({type(e).__name__}).")
            return KetQua(LOI, m.phien_ban, f"Lỗi không lường trước khi chuẩn bị ({type(e).__name__}) — "
                          "giữ bản hiện tại.")
        finally:
            self._xoa_cay(tam)

    def _tao_runtime(self, m: Manifest, rel: str, rt: str) -> None:
        """Gọi ``tao_moi_truong``. Từ chối nội dung đã ký (``TuChoiGoi``, vd. lock chưa băm) → nguyên trạng
        (cách ly ngay). Lỗi khác (pip/venv/mạng/timeout) → ``LoiCapNhat``; lặp tới ``SO_LAN_LOI_TOI_DA`` lần
        cho cùng phiên bản → cách ly (không tải + dựng lại mãi mỗi lượt kiểm; ``update bo-cach-ly`` để thử
        lại sau khi khắc phục)."""
        try:
            self.tao_moi_truong(m, rel, rt)
        except TuChoiGoi:
            raise
        except Exception as e:  # noqa: BLE001
            with contextlib.suppress(OSError):
                self._xoa_cay(rt)                         # dở dang, chưa có dấu sẵn sàng, không ai dùng
            ly_do = str(e) if isinstance(e, LoiCapNhat) else type(e).__name__
            if self._dem_loi("loi_runtime.json", m.phien_ban) >= SO_LAN_LOI_TOI_DA:
                self._cach_ly(m.phien_ban, f"tạo runtime lỗi {SO_LAN_LOI_TOI_DA} lần: {ly_do}")
            raise LoiCapNhat("runtime", f"Tạo runtime lỗi ({ly_do}) — giữ bản hiện tại.") from e

    def _kiem(self, m: Manifest, rel: str, rt: str, che_do: str) -> tuple:
        """Health check → ``(ok, chi_tiết, tạm_thời)``. KHÔNG chạy được (timeout, thiếu python, CSDL bị khoá,
        lỗi lạ) = KHÔNG ĐẠT nhưng ``tạm_thời`` — không bao giờ thoát khỏi bộ cập nhật giữa chừng (con trỏ có
        thể đang ở bản chưa kiểm). Health CHẠY và báo lỗi = tất định."""
        try:
            ok, chi_tiet = self.kiem_suc_khoe(m, rel, rt, che_do)
            return ok, chi_tiet, False
        except Exception as e:  # noqa: BLE001
            chi_tiet = str(e) if isinstance(e, LoiCapNhat) else type(e).__name__
            return False, f"không chạy được health check ({chi_tiet})", True

    def _het_luot_tam_thoi(self, phien_ban: str) -> bool:
        """Đếm một lần lỗi tạm thời của ``phien_ban``; ``True`` khi đã tới ``SO_LAN_LOI_TOI_DA`` (→ cách ly)."""
        return self._dem_loi("loi_tam_thoi.json", phien_ban) >= SO_LAN_LOI_TOI_DA

    def _cai_release(self, goi: str, rel: str, m: Manifest, raw_m: bytes, raw_s: bytes,
                     phien: str) -> None:
        tam_rel = f"{rel}.tmp-{phien}"
        giai_nen_an_toan(goi, tam_rel)
        try:
            kiem_cay_release(tam_rel, m)
            for ten, du in ((TEN_MANIFEST, raw_m), (TEN_CHU_KY, raw_s)):
                with open(os.path.join(tam_rel, ten), "wb") as f:
                    f.write(du)
                    f.flush()
                    os.fsync(f.fileno())
            if os.path.exists(rel):                  # dở dang từ lần trước (chưa có dấu sẵn sàng)
                self._xoa_cay(rel, bo_qua_loi=False)
            os.replace(tam_rel, rel)
        except BaseException:
            self._xoa_cay(tam_rel)
            raise
        ghi_json_nguyen_tu(os.path.join(rel, TEN_SAN_SANG),
                           {"manifest_sha256": m.sha256, "luc": _bay_gio()})

    def _release_san_sang(self, rel: str, m: Manifest) -> bool:
        d = doc_json(os.path.join(rel, TEN_SAN_SANG), bat_buoc_hop_le=False)
        if not (isinstance(d, dict) and d.get("manifest_sha256") == m.sha256):
            return False
        try:
            kiem_cay_release(rel, m)                 # kiểm lại cả cây trước khi dùng
        except TuChoiGoi:
            return False
        return True

    def _runtime_san_sang(self, rt: str, m: Manifest) -> bool:
        d = doc_json(os.path.join(rt, TEN_SAN_SANG), bat_buoc_hop_le=False)
        return isinstance(d, dict) and d.get("lock_sha256") == m.lock_sha256

    def _manifest_da_cai(self, con_tro: dict) -> Optional[Manifest]:
        """Manifest của release ĐÃ CÀI theo con trỏ — kiểm lại chữ ký, cây, runtime. Hỏng → ``None``."""
        rel = con_tro.get("release", "")
        try:
            with open(os.path.join(rel, TEN_MANIFEST), "rb") as f:
                raw_m = f.read()
            with open(os.path.join(rel, TEN_CHU_KY), "rb") as f:
                raw_s = f.read()
            kiem_chu_ky(raw_m, raw_s, self.khoa_tin_cay)
            m = doc_manifest(raw_m)
        except (OSError, LoiCapNhat):
            return None
        if m.sha256 != con_tro.get("manifest_sha256") or not self._release_san_sang(rel, m):
            return None
        if not self._runtime_san_sang(con_tro.get("runtime", ""), m):
            return None
        return m

    # ---------- áp dụng ----------

    def ap_dung(self) -> KetQua:
        """STAGED → (rút cổng, chờ rảnh CÓ HẠN) → backup → migration tự động an toàn (nếu cần) → đổi con
        trỏ → health → ACTIVE. Không rảnh → hoãn, giữ STAGED; không giết việc nào."""
        try:
            with self._giu_quyen():
                self._phuc_hoi()
                return self._ap_dung()
        except LoiCapNhat as e:
            return KetQua(e.ma if e.ma == BAN else LOI, "", str(e))
        except Exception as e:  # noqa: BLE001 — lỗi lạ: nhật ký giữ trạng thái giữa chừng, lần chạy sau
            # khôi phục đúng như sau mất điện (cổng đã mở lại trong finally của _ap_dung).
            return KetQua(LOI, "", f"Lỗi không lường trước khi áp dụng ({type(e).__name__}) — lần mở sau sẽ "
                          "tự khôi phục.")

    @staticmethod
    def _ket_qua_hoan(phien_ban: str, den: float) -> KetQua:
        return KetQua(STAGED, phien_ban, "Người dùng đã hoãn áp dụng cập nhật tới "
                      f"{datetime.fromtimestamp(den):%H:%M %d/%m} — giữ bản hiện tại.")

    def _ap_dung(self) -> KetQua:
        nk = self.nk.doc()
        if not nk or nk.get("trang_thai") != STAGED:
            return KetQua(nk.get("trang_thai") if nk else KHONG_CO, "", "Không có bản nào đang chờ áp dụng.")
        den = doc_hoan(self.cd.goc)
        if den is not None:
            return self._ket_qua_hoan(nk.get("ung_vien", ""), den)
        con_tro_moi = nk.get("con_tro_moi") or {}
        m = self._manifest_da_cai(con_tro_moi)
        if m is None:
            self.nk.ghi(CHECKED, con_tro_moi=None, loi="Bản đã stage không còn nguyên vẹn — sẽ tải lại.")
            return KetQua(LOI, nk.get("ung_vien", ""), "Bản đã stage hỏng — sẽ tải lại ở lần kiểm sau.")
        chan = self._chan_theo_lich_su(m)                 # TRƯỚC rút cổng/sao lưu
        if chan is not None:
            return chan
        try:
            rut = self.cong.bat_dau_rut(f"cập nhật lên {m.phien_ban}")
        except Exception as e:  # noqa: BLE001 — cổng đang bị một lượt khác rút
            return KetQua(STAGED, m.phien_ban, str(e))
        try:
            self.nk.ghi(WAITING_IDLE)
            self.diem_dung(WAITING_IDLE)
            if not rut.cho_ranh(self.han_cho_ranh_s, self.chu_ky_cho_s):
                self.nk.ghi(STAGED, loi="Còn việc đang chạy — hoãn cập nhật, giữ bản hiện tại.")
                return KetQua(STAGED, m.phien_ban, "Còn việc đang chạy — đã hoãn cập nhật.")
            den = doc_hoan(self.cd.goc)                    # người dùng bấm «Hoãn» TRONG lúc chờ rảnh
            if den is not None:
                self.nk.ghi(STAGED, loi="")
                return self._ket_qua_hoan(m.phien_ban, den)
            return self._ap_dung_da_rut(m, con_tro_moi)
        finally:
            rut.ket_thuc()

    def _ap_dung_da_rut(self, m: Manifest, con_tro_moi: dict) -> KetQua:
        self.nk.ghi(QUIESCED)
        self.diem_dung(QUIESCED)
        bk = self.sao_luu(m)
        self.nk.ghi(BACKED_UP, sao_luu=bk)
        self.diem_dung(BACKED_UP)
        db = self.phien_ban_db()
        if db is not None and db > m.lich_su:
            self.nk.ghi(BLOCKED, loi="Lịch sử trên máy mới hơn bản phát hành (schema quá mới).")
            return KetQua(BLOCKED, m.phien_ban, "Schema dữ liệu mới hơn bản phát hành — chặn.")
        # Chưa có lịch sử (máy mới, hoặc app chưa mở lần nào): KHÔNG migration — app tạo lược đồ bằng chính mã
        # mới khi mở lần đầu (quay lại sau đó không để lại lược đồ "chưa khai tương thích ngược"). Có lịch sử cũ
        # hơn: chỉ khi bản phát hành khai tự động an toàn (⇒ tương thích ngược).
        if db is not None and db < m.lich_su:
            if not m.tu_dong_an_toan:
                self.nk.ghi(WAITING_APPROVAL, loi="Bản mới cần migration chưa được đánh giá tự động an "
                            "toàn — chờ duyệt.")
                return KetQua(WAITING_APPROVAL, m.phien_ban, "Cần duyệt migration trước khi cập nhật.")
            self.nk.ghi(MIGRATING)
            self.diem_dung(MIGRATING)
            try:
                self.di_chuyen(m, con_tro_moi["release"], con_tro_moi["runtime"])
            except Exception as e:  # noqa: BLE001 — mã chưa đổi; migration tự động luôn tương thích ngược nên
                # bản đang chạy dùng tiếp được dù migration đã đi một phần.
                ly_do = (f"migration lỗi: {e}" if isinstance(e, LoiCapNhat)
                         else f"migration lỗi ({type(e).__name__})")
                tam_thoi = isinstance(e, LoiTamThoi) or not isinstance(e, LoiCapNhat)
                if tam_thoi and not self._het_luot_tam_thoi(m.phien_ban):
                    self.nk.ghi(STAGED, loi=ly_do + " — có thể tạm thời; giữ bản hiện tại, áp dụng lại lần sau.")
                    return KetQua(LOI, m.phien_ban, f"{ly_do} — giữ bản hiện tại, thử lại lần sau.")
                # Tất định (hoặc tạm thời lặp quá số lần): cách ly — không lặp «sao lưu + rút cổng + migration».
                self._cach_ly(m.phien_ban, ly_do)
                self.nk.ghi(QUARANTINED, con_tro_moi=None, loi=ly_do + " — giữ bản hiện tại.")
                return KetQua(QUARANTINED, m.phien_ban, "Migration lỗi — đã cách ly bản mới, giữ bản hiện tại.")
            self.diem_dung("MIGRATED")
        return self._kich_hoat(m, con_tro_moi)

    def _kich_hoat(self, m: Manifest, con_tro_moi: dict) -> KetQua:
        cu = self.hien_tai()
        if cu and not self.last_good():
            ghi_json_nguyen_tu(self.cd.file_trang_thai("last_good.json"), cu)
        self.nk.ghi(ACTIVATING, con_tro_cu=cu)
        self.diem_dung(ACTIVATING)
        ghi_json_nguyen_tu(self.cd.file_trang_thai("current.json"), con_tro_moi)
        self.diem_dung("POINTER_SWITCHED")
        return self._kiem_sau_kich_hoat(m, con_tro_moi)

    def _kiem_sau_kich_hoat(self, m: Manifest, con_tro_moi: dict) -> KetQua:
        self.nk.ghi(HEALTHCHECK)
        self.diem_dung(HEALTHCHECK)
        ok, chi_tiet, tam_thoi = self._kiem(m, con_tro_moi["release"], con_tro_moi["runtime"], "kich_hoat")
        if not ok:
            # Luôn quay về NGAY (an toàn); chỉ cách ly khi lỗi tất định hoặc tạm thời đã lặp quá số lần.
            try:
                cach_ly = not tam_thoi or self._het_luot_tam_thoi(m.phien_ban)
            except Exception:  # noqa: BLE001 — không ghi được bộ đếm (đĩa…): vẫn QUAY VỀ, chưa cách ly
                cach_ly = False
            return self._quay_lai(m, f"health check sau kích hoạt lỗi: {chi_tiet}", cach_ly=cach_ly)
        # ACTIVE TRƯỚC last_good: last_good chỉ trỏ bản mà nhật ký ĐÃ ghi bền ACTIVE — chết giữa hai bước thì
        # khôi phục (nhánh ACTIVE) ghi bù last_good, không rút cổng kiểm lại health. Quay lại KHÔNG dựa vào thứ
        # tự này: ``_con_tro_truoc`` không bao giờ trả về chính ứng viên.
        self.nk.ghi(ACTIVE, loi="")
        self.diem_dung(ACTIVE)
        ghi_json_nguyen_tu(self.cd.file_trang_thai("last_good.json"), con_tro_moi)
        return KetQua(ACTIVE, m.phien_ban, f"Đã chuyển sang bản {m.phien_ban}.")

    def _quay_lai(self, m: Manifest, ly_do: str, *, cach_ly: bool = True) -> KetQua:
        """Quay MÃ về con trỏ TRƯỚC kích hoạt (không bao giờ về chính bản lỗi). DB KHÔNG BAO GIỜ tự khôi phục
        (migration tự động luôn tương thích ngược) — việc đã gửi không thể quay về chờ gửi. ``cach_ly``: cách ly
        bản lỗi (tất định); không thì nhật ký về CHECKED để lượt kiểm sau thử lại (lỗi có thể tạm thời)."""
        self.nk.ghi(ROLLBACK, loi=ly_do, cach_ly_khi_quay_lai=cach_ly)
        self.diem_dung(ROLLBACK)
        self._ve_con_tro_truoc(m.sha256)
        if not cach_ly:
            self.nk.ghi(CHECKED, con_tro_moi=None, loi=ly_do + " — đã quay về bản trước; chưa cách ly (có thể "
                        "tạm thời), lượt kiểm sau thử lại.")
            return KetQua(LOI, m.phien_ban, f"Bản {m.phien_ban}: {ly_do} — đã quay về bản trước, thử lại lần sau.")
        self._cach_ly(m.phien_ban, ly_do)
        self.nk.ghi(QUARANTINED, loi=ly_do)
        return KetQua(QUARANTINED, m.phien_ban,
                      f"Bản {m.phien_ban} lỗi sau kích hoạt — đã quay về bản trước và cách ly.")

    # ---------- khôi phục sau mất điện ----------

    def phuc_hoi(self) -> Optional[str]:
        """Chạy MỖI lần launcher khởi động, trước khi mở app/Watch. Xác định theo nhật ký + con trỏ,
        không đoán theo thư mục. Lỗi lạ → ``LoiCapNhat`` (launcher cảnh báo rồi chạy con trỏ hiện tại)."""
        with self._giu_quyen():
            try:
                return self._phuc_hoi()
            except LoiCapNhat:
                raise
            except Exception as e:  # noqa: BLE001
                raise LoiCapNhat("khoi_phuc", f"Khôi phục cập nhật lỗi không lường trước ({type(e).__name__})"
                                 " — giữ con trỏ hiện tại; chạy «launcher.py doctor».") from e

    def _phuc_hoi(self) -> Optional[str]:
        nk = self.nk.doc()
        if not nk:
            return None
        tt = nk["trang_thai"]
        if tt == ACTIVE:
            self._bu_last_good(nk)
        if tt in KET_THUC or tt in (CHECKED, STAGED):
            self._don_staging()
            return tt
        if tt in (DOWNLOADING, VERIFIED):
            self._don_staging()
            self.nk.ghi(CHECKED, loi="Lượt chuẩn bị trước bị gián đoạn — sẽ làm lại.")
            return CHECKED
        if tt in (WAITING_IDLE, QUIESCED, BACKED_UP, MIGRATING):
            # Cổng đã tự mở (khoá rút nhả theo tiến trình chết); con trỏ chưa đổi. Migration là giao dịch
            # SQLite (xong hoặc chưa) và tự động ⇒ tương thích ngược, nên bản cũ chạy tiếp được.
            self.nk.ghi(STAGED, loi="Lượt áp dụng trước bị gián đoạn trước khi đổi mã — sẽ áp dụng lại.")
            return STAGED
        if tt not in (ACTIVATING, HEALTHCHECK, ROLLBACK):
            return tt
        con_tro_moi = nk.get("con_tro_moi") or {}
        m = self._manifest_da_cai(con_tro_moi)
        if m is None:
            self._ve_con_tro_truoc(str(con_tro_moi.get("manifest_sha256") or nk.get("manifest_sha256") or ""))
            self.nk.ghi(BLOCKED, loi="Bản ứng viên hỏng sau gián đoạn — đã về bản trước, cần kiểm tay.")
            return BLOCKED
        if tt == ROLLBACK:
            return self._quay_lai(m, nk.get("loi") or "quay lại bị gián đoạn",
                                  cach_ly=bool(nk.get("cach_ly_khi_quay_lai", True))).trang_thai
        if (self.hien_tai() or {}).get("manifest_sha256") != m.sha256:
            self.nk.ghi(STAGED, loi="Kích hoạt trước bị gián đoạn trước khi đổi bản — sẽ áp dụng lại.")
            return STAGED
        if self._con_tro_truoc(m.sha256) is None:
            # Cài lần đầu: không có bản nào khác để bảo vệ và mã ĐÃ là bản này (việc đang chạy cũng chạy trên
            # nó) — kiểm health ngay, không chờ rảnh (chờ thì mỗi lần mở launcher lại chờ tới 600 s).
            return self._kiem_sau_kich_hoat(m, con_tro_moi).trang_thai
        # Con trỏ đã sang bản mới nhưng chưa qua health: kiểm lại DƯỚI cổng rút. Không rảnh được thì về
        # bản trước (KHÔNG cách ly — bản mới chưa hề lỗi) và giữ STAGED để thử lần sau.
        try:
            rut = self.cong.bat_dau_rut(f"hoàn tất cập nhật {m.phien_ban}")
        except Exception:  # noqa: BLE001
            rut = None
        try:
            if rut is not None and rut.cho_ranh(self.han_cho_ranh_s, self.chu_ky_cho_s):
                return self._kiem_sau_kich_hoat(m, con_tro_moi).trang_thai
            self._ve_con_tro_truoc(m.sha256)
            self.nk.ghi(STAGED, loi="Chưa kiểm được bản mới sau gián đoạn — tạm về bản trước.")
            return STAGED
        finally:
            if rut is not None:
                rut.ket_thuc()

    def _bu_last_good(self, nk: dict) -> None:
        """Nhật ký ACTIVE nhưng last_good chưa trỏ tới con trỏ đã chốt (chết giữa ``ACTIVE`` và ghi
        last_good) → ghi bù. Chỉ khi ``current`` đúng là con trỏ ACTIVE của nhật ký."""
        cur, moi = self.hien_tai(), nk.get("con_tro_moi")
        if not (isinstance(cur, dict) and isinstance(moi, dict)):
            return
        if cur.get("manifest_sha256") != moi.get("manifest_sha256"):
            return
        lg = self.last_good()
        if not isinstance(lg, dict) or lg.get("manifest_sha256") != cur.get("manifest_sha256"):
            ghi_json_nguyen_tu(self.cd.file_trang_thai("last_good.json"), cur)

    def _xoa_cay(self, path: str, *, bo_qua_loi: bool = True) -> None:
        """MỌI lần updater xoá một cây thư mục đi qua đây: chốt bố cục NGAY TRƯỚC khi xoá (``CaiDat.kiem_xoa`` —
        đích thuộc vùng updater, không chồng state root/nguồn phát hành). Sai → ``LoiCapNhat``, không xoá gì."""
        self.cd.kiem_xoa(path, self._bao_ve)
        shutil.rmtree(path, ignore_errors=bo_qua_loi)

    def _don_staging(self) -> None:
        """Chỉ dọn thư mục DO UPDATER SỞ HỮU: ``staging/`` và ``releases/*.tmp-*`` (giữ quyền updater
        nên không đụng lượt khác)."""
        self._xoa_cay(self.cd.staging)
        if os.path.isdir(self.cd.releases):
            for ten in os.listdir(self.cd.releases):
                if ".tmp-" in ten:
                    self._xoa_cay(os.path.join(self.cd.releases, ten))

    def trang_thai(self) -> dict:
        """Cho UI «Phiên bản và cập nhật» / ``launcher status`` — chỉ đọc."""
        return {"hien_tai": self.hien_tai(), "last_good": self.last_good(), "nhat_ky": self.nk.doc(),
                "cach_ly": self.cach_ly(), "cong": self.cong.trang_thai_rut(),
                "viec_dang_chay": self.cong.viec_dang_chay()}


# ---------------------------------------------------------------------------
#  Dọn bản cũ (chỉ thứ updater sở hữu, không active/không được tham chiếu)
# ---------------------------------------------------------------------------

def don_ban_cu(cai_dat: CaiDat, *, giu: int = 2) -> list:
    """Xoá release/runtime KHÔNG phải current/last_good/ứng viên trong nhật ký, giữ ``giu`` bản mới nhất.
    Không bao giờ chạm state root, kho hay thư mục ngoài installation root. Con trỏ/nhật ký HỎNG →
    ``LoiCapNhat``, không xoá gì (đọc lỏng sẽ coi bản đang chạy là "không ai dùng")."""
    tham_chieu = set()
    for ten in ("current.json", "last_good.json"):
        d = doc_json(cai_dat.file_trang_thai(ten))
        if isinstance(d, dict):
            tham_chieu.update({os.path.normcase(os.path.abspath(d.get("release", ""))),
                               os.path.normcase(os.path.abspath(d.get("runtime", "")))})
    nk = doc_json(cai_dat.file_trang_thai("journal.json"))
    if isinstance(nk, dict) and isinstance(nk.get("con_tro_moi"), dict):
        tham_chieu.update({os.path.normcase(os.path.abspath(nk["con_tro_moi"].get(k, "")))
                           for k in ("release", "runtime")})
    da_xoa = []
    if not os.path.isdir(cai_dat.releases):
        return da_xoa
    ban = []
    for ten in os.listdir(cai_dat.releases):
        with contextlib.suppress(LoiCapNhat):
            ban.append((phan_tich_phien_ban(ten), ten))
    ban.sort(reverse=True)
    for _, ten in ban[giu:]:
        p = os.path.normcase(os.path.abspath(cai_dat.release_dir(ten)))
        if p not in tham_chieu:
            cai_dat.kiem_xoa(cai_dat.release_dir(ten))      # MR-P1-01: không bao giờ xoá trúng state root
            shutil.rmtree(cai_dat.release_dir(ten), ignore_errors=True)
            da_xoa.append(cai_dat.release_dir(ten))
    return da_xoa


def bay_gio_epoch() -> float:
    return time.time()
