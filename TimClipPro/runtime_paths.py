# -*- coding: utf-8 -*-
"""Bộ phân giải đường dẫn runtime — MỘT nơi quyết định dữ liệu của máy nằm ở đâu.

Hai chế độ (docs/MANAGED_RUNTIME_DESIGN.md §4):

* ``legacy`` (mặc định — PC1, mọi cài đặt cũ, test): giữ NGUYÊN công thức đã có
  ``TIMCLIP_DATA_DIR or <mã>/data`` và ``TIMCLIP_OUTPUT_DIR or <mã>/ketqua``. Không di chuyển dữ
  liệu của ai. Thư mục đồng bộ đám mây / ổ mạng chỉ thành CẢNH BÁO.
* ``managed`` (``TIMCLIP_RUNTIME_MODE=managed`` — cài đặt do launcher quản lý, ví dụ PC2): mã nằm
  trong ``releases/<bản>`` BẤT BIẾN, mọi trạng thái nằm ở ``TIMCLIP_STATE_ROOT``. Thiếu state root,
  thiếu/hỏng ``installation.json``, tham số mâu thuẫn, state root trên OneDrive/ổ mạng → ``LoiRuntime``.
  Không bao giờ rơi về ``<release>/data`` hay thư mục hiện hành.

Mã của một release mang dấu ``MANAGED_RELEASE.json`` ở thư mục cha của ``TimClipPro`` — chạy nó theo
kiểu legacy (``.bat`` cũ, ``python app.py`` bấm tay) cũng là ``LoiRuntime``: release không được tự
tạo ``data/`` bên trong mình.

Không I/O lúc import; ``resolve`` chỉ ĐỌC (không tạo thư mục nào).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional

LEGACY = "legacy"
MANAGED = "managed"
TEN_DINH_DANH = "installation.json"
TEN_DAU_RELEASE = "MANAGED_RELEASE.json"
WORKSPACE_MAC_DINH = "mac_dinh"
_DINH_DANG_DINH_DANH = 1

# Tên thư mục của các dịch vụ đồng bộ đám mây hay gặp trên Windows. SQLite đang hoạt động KHÔNG
# được nằm ở đó: dịch vụ đồng bộ chép file DB và file journal ở hai thời điểm khác nhau.
_TEN_DAM_MAY = ("onedrive", "dropbox", "google drive", "googledrive", "icloud drive",
                "iclouddrive", "box sync", "mega")
_BIEN_DAM_MAY = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")


class LoiRuntime(RuntimeError):
    """Cấu hình runtime sai — dừng rõ ràng thay vì đoán đường dẫn."""


@dataclass(frozen=True)
class RuntimePaths:
    che_do: str
    ma_nguon: str             # thư mục TimClipPro (của worktree hoặc của release)
    state_root: str           # legacy: = ma_nguon; managed: TIMCLIP_STATE_ROOT
    data_dir: str
    out_dir: str
    installation_root: str = ""
    installation_id: str = ""
    workspace: str = WORKSPACE_MAC_DINH
    canh_bao: tuple = ()      # chỉ legacy — managed gặp vấn đề là dừng

    @property
    def khoa_google_mac_dinh(self) -> str:
        """Chỗ mặc định của khoá Google: legacy cạnh mã như xưa; managed trong state root (khoá
        là dữ liệu riêng của máy, không bao giờ nằm trong release)."""
        if self.che_do == MANAGED:
            return os.path.join(self.state_root, "secrets", "google_key.json")
        return os.path.join(self.ma_nguon, "google_key.json")


def _ma_nguon_mac_dinh() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def la_release_managed(ma_nguon: str) -> bool:
    """Mã này nằm trong một release do launcher cài (có dấu ở thư mục cha)?"""
    return os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(ma_nguon)),
                                       TEN_DAU_RELEASE))


def _o_dia_mang(duong_dan: str) -> bool:
    """Ổ đĩa map tới máy khác (DRIVE_REMOTE). Chỉ Windows; nơi khác coi như không."""
    if os.name != "nt":
        return False
    o, _ = os.path.splitdrive(os.path.abspath(duong_dan))
    if not o or not o.endswith(":"):
        return False
    try:
        import ctypes
        return ctypes.windll.kernel32.GetDriveTypeW(o + "\\") == 4   # DRIVE_REMOTE
    except Exception:  # noqa: BLE001 — không xác định được thì không suy diễn
        return False


def kiem_duong_dan_trang_thai(duong_dan: str, environ: Optional[Mapping] = None) -> list:
    """Lý do một thư mục KHÔNG nên chứa SQLite đang hoạt động (rỗng = ổn). Chỉ đọc."""
    environ = os.environ if environ is None else environ
    ly_do = []
    tho = str(duong_dan)
    if tho.startswith(("\\\\", "//")) or _o_dia_mang(tho):
        ly_do.append(f"«{tho}» nằm trên ổ mạng — SQLite không an toàn khi dùng qua mạng.")
    chuan = os.path.normcase(os.path.abspath(tho))
    for bien in _BIEN_DAM_MAY:
        goc = environ.get(bien)
        if goc:
            goc_chuan = os.path.normcase(os.path.abspath(goc))
            if chuan == goc_chuan or chuan.startswith(goc_chuan.rstrip("\\/") + os.sep):
                ly_do.append(f"«{tho}» nằm trong thư mục OneDrive đang đồng bộ.")
                return ly_do
    for phan in chuan.replace("\\", "/").split("/"):
        if any(phan == t or phan.startswith(t + " - ") or phan.startswith(t + "-")
               for t in _TEN_DAM_MAY):
            ly_do.append(f"«{tho}» nằm trong thư mục đồng bộ đám mây («{phan}»).")
            break
    return ly_do


def _hai_dang(duong_dan: str) -> tuple:
    """Hai dạng của một đường dẫn để so cha/con: CHỮ (abspath; Windows không phân biệt hoa/thường) và THẬT
    (realpath — giải junction/symlink/tên 8.3; phần chưa tồn tại giữ nguyên)."""
    chu = os.path.normcase(os.path.abspath(duong_dan))
    try:
        that = os.path.normcase(os.path.realpath(duong_dan))
    except (OSError, ValueError):
        that = chu
    return chu, that


def nam_trong(con: str, cha: str) -> bool:
    """``con`` là ``cha`` hoặc nằm BÊN TRONG ``cha`` — theo dạng chữ HOẶC dạng thật (một dạng là đủ: junction
    trỏ vào trong, hay đường dẫn khai báo nằm trong mà junction trỏ ra ngoài, đều nguy hiểm như nhau). So bằng
    ``commonpath`` theo từng thành phần, không theo tiền tố chuỗi (``D:\\TimClipPro_State`` không nằm trong
    ``D:\\TimClipPro``). Chỉ đọc."""
    for a, b in zip(_hai_dang(con), _hai_dang(cha)):
        try:
            if os.path.commonpath([a, b]) == b:
                return True
        except ValueError:                           # khác ổ đĩa
            continue
    return False


def chong_lan(a: str, b: str) -> bool:
    """Hai thư mục trùng nhau hoặc một cái nằm trong cái kia (xoá một cái là chạm vào cái còn lại)."""
    return nam_trong(a, b) or nam_trong(b, a)


def ly_do_bo_cuc(installation_root: str, state_root: str) -> str:
    """Lý do bố cục KHÔNG an toàn (rỗng = an toàn). Bộ cập nhật được quyền xoá/thay các thư mục con của cài đặt
    (``staging``, ``releases``, ``environments``, ``update_state``) — state root (lịch sử, kho, khoá, sao lưu)
    nằm bên trong là có thể mất sạch (audit độc lập f4d3cb7, MR-P1-01). Hai thư mục phải TÁCH BIỆT: không trùng,
    không thư mục nào nằm trong thư mục kia. Chỉ đọc."""
    if nam_trong(state_root, installation_root):
        return (f"state root «{state_root}» trùng hoặc nằm BÊN TRONG thư mục cài đặt «{installation_root}» — vùng "
                "bộ cập nhật được quyền xoá/thay.")
    if nam_trong(installation_root, state_root):
        return f"thư mục cài đặt «{installation_root}» nằm BÊN TRONG state root «{state_root}»."
    return ""


def doc_dinh_danh(state_root: str) -> dict:
    """Đọc ``installation.json`` của một state root; thiếu/hỏng → ``LoiRuntime``."""
    duong_dan = os.path.join(state_root, TEN_DINH_DANH)
    try:
        with open(duong_dan, encoding="utf-8") as f:
            du_lieu = json.load(f)
    except FileNotFoundError:
        raise LoiRuntime(f"State root «{state_root}» chưa có {TEN_DINH_DANH} — hãy chạy bootstrap "
                         "của launcher; không tự tạo.") from None
    except (OSError, ValueError) as e:
        raise LoiRuntime(f"Không đọc được {TEN_DINH_DANH} ở «{state_root}»: "
                         f"{type(e).__name__}") from None
    iid = du_lieu.get("installation_id") if isinstance(du_lieu, dict) else None
    if (not isinstance(iid, str) or len(iid) != 32
            or any(c not in "0123456789abcdef" for c in iid)
            or du_lieu.get("dinh_dang") != _DINH_DANG_DINH_DANH):
        raise LoiRuntime(f"{TEN_DINH_DANH} ở «{state_root}» không hợp lệ.")
    return du_lieu


def tao_dinh_danh(state_root: str, *, installation_root: str,
                  workspace: str = WORKSPACE_MAC_DINH) -> dict:
    """Bootstrap: tạo ``installation.json`` với UUID MỚI. Đã có → ``LoiRuntime`` (không ghi đè).

    Mỗi máy một UUID: gói cài đặt không bao giờ mang UUID của máy khác, nên PC2 không thể vô tình
    kế thừa định danh (và khoá chống trùng việc gửi) của PC1.
    """
    if not workspace or any(c in workspace for c in "\\/:*?\"<>|"):
        raise LoiRuntime("Tên workspace không hợp lệ.")
    du_lieu = {
        "dinh_dang": _DINH_DANG_DINH_DANH,
        "installation_id": uuid.uuid4().hex,
        "workspace": workspace,
        "installation_root": os.path.abspath(installation_root),
        "tao_luc": datetime.now().isoformat(timespec="seconds"),
    }
    duong_dan = os.path.join(state_root, TEN_DINH_DANH)
    try:
        with open(duong_dan, "x", encoding="utf-8", newline="\n") as f:
            json.dump(du_lieu, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
    except FileExistsError:
        raise LoiRuntime(f"State root «{state_root}» đã có {TEN_DINH_DANH} — không ghi đè định "
                         "danh của một cài đặt.") from None
    return du_lieu


def resolve(environ: Optional[Mapping] = None, *, ma_nguon: Optional[str] = None) -> RuntimePaths:
    """Phân giải đường dẫn của tiến trình này. CHỈ ĐỌC — không tạo thư mục nào."""
    environ = os.environ if environ is None else environ
    ma = os.path.abspath(ma_nguon or _ma_nguon_mac_dinh())
    che_do = (environ.get("TIMCLIP_RUNTIME_MODE") or LEGACY).strip()
    if che_do not in (LEGACY, MANAGED):
        raise LoiRuntime(f"TIMCLIP_RUNTIME_MODE «{che_do}» không hợp lệ (legacy | managed).")

    if che_do == LEGACY:
        if la_release_managed(ma):
            raise LoiRuntime("Đây là bản cài do launcher quản lý — hãy mở bằng TimClipPro.bat của "
                             "launcher, không chạy trực tiếp trong thư mục release.")
        data_dir = os.path.abspath(environ.get("TIMCLIP_DATA_DIR") or os.path.join(ma, "data"))
        out_dir = os.path.abspath(environ.get("TIMCLIP_OUTPUT_DIR")
                                  or os.path.join(ma, "ketqua"))
        return RuntimePaths(LEGACY, ma, ma, data_dir, out_dir,
                            canh_bao=tuple(kiem_duong_dan_trang_thai(data_dir, environ)))

    state = environ.get("TIMCLIP_STATE_ROOT") or ""
    if not state or not os.path.isabs(state):
        raise LoiRuntime("Chế độ managed cần TIMCLIP_STATE_ROOT là đường dẫn tuyệt đối "
                         "(launcher đặt biến này) — không đoán thư mục dữ liệu.")
    state = os.path.abspath(state)
    ly_do = kiem_duong_dan_trang_thai(state, environ)
    if ly_do:
        raise LoiRuntime("State root không an toàn: " + " ".join(ly_do))
    dd = doc_dinh_danh(state)
    iid = environ.get("TIMCLIP_INSTALLATION_ID")
    if iid and iid != dd["installation_id"]:
        raise LoiRuntime("TIMCLIP_INSTALLATION_ID khác định danh trong state root — state root "
                         "này thuộc một cài đặt khác.")
    data_dir = os.path.join(state, "data")
    out_dir = os.path.join(state, "output")
    for bien, mong in (("TIMCLIP_DATA_DIR", data_dir), ("TIMCLIP_OUTPUT_DIR", out_dir)):
        gia_tri = environ.get(bien)
        if gia_tri and os.path.normcase(os.path.abspath(gia_tri)) != os.path.normcase(mong):
            raise LoiRuntime(f"{bien} mâu thuẫn với TIMCLIP_STATE_ROOT ở chế độ managed.")
    return RuntimePaths(MANAGED, ma, state, data_dir, out_dir,
                        installation_root=str(dd.get("installation_root") or ""),
                        installation_id=dd["installation_id"],
                        workspace=str(dd.get("workspace") or WORKSPACE_MAC_DINH))
