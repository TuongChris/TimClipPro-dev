# -*- coding: utf-8 -*-
"""Ghi danh thêm MỘT khoá ký phát hành vào trust store của MỘT cài đặt managed — docs/UY_QUYEN_KHOA.md.

Chạy trên máy có cài đặt (PC2), do CHỦ MÁY gõ trong cửa sổ console của mình (Claude không đọc/ghi ``C:\\TimClipPro*``):

    <python có cryptography> -I -B uy_quyen_khoa.py xem      --goc C:\\TimClipPro
    <python>                 -I -B uy_quyen_khoa.py yeu-cau  --goc C:\\TimClipPro --khoa-rieng <pem> --ten-may PC2
                                                             --ra <file yêu cầu .json>
    <python>                 -I -B uy_quyen_khoa.py ghi-danh --goc C:\\TimClipPro --uy-quyen <file uỷ quyền .json>
    <python>                 -I -B uy_quyen_khoa.py hoan-tac --goc C:\\TimClipPro --sao-luu <file sao lưu>

Phía máy đang được tin (PC1): ``release_tool.py ky-uy-quyen`` (ký) và ``release_tool.py kiem-uy-quyen`` (kiểm).

Vì sao không cần đổi launcher: launcher (ngoài release, cố định từ lúc bootstrap) đọc ``launcher/trusted_keys.json``
mỗi lần chạy và ĐÃ tin nhiều khoá — ``managed_update.kiem_chu_ky`` chọn khoá theo ``key_id`` trong chữ ký. Thêm một
khoá chỉ đổi FILE DỮ LIỆU đó: không đổi launcher, không đổi release đã ký, không bootstrap lại, không đổi định danh.

Bất biến
========
* Chỉ THÊM đúng một khoá; mọi mục khoá cũ giữ nguyên. Không tắt hay nới kiểm chữ ký/chống hạ bản nào.
* Uỷ quyền phải do một khoá ĐANG được chính trust store này tin ký (xác minh bằng parser của launcher ĐÃ CÀI), ràng
  buộc: khoá mới (key_id + khoá công khai), băm định danh cài đặt ĐÍCH, băm trust store KỲ VỌNG, danh sách khoá hiện
  có, mã uỷ quyền, hạn dùng. Sai bất kỳ → từ chối, không ghi gì. Đã ghi danh → trust store đổi băm → không dùng lại được.
* Yêu cầu do chính khoá mới TỰ KÝ (chứng minh giữ khoá riêng); không chứa định danh cài đặt (chỉ băm có tiền tố miền),
  đường dẫn, tên người dùng hay bí mật — đưa lên repo công khai được.
* Chữ ký yêu cầu/uỷ quyền ký trên ``MIỀN + nội dung chuẩn hoá`` → không bao giờ là chữ ký hợp lệ của một manifest.
* Ghi: giữ khoá ``update_state/updater.lock`` (không chạy song song bộ cập nhật) → chủ máy gõ xác nhận → sao lưu byte cũ
  (fsync) → file tạm + fsync + ``os.replace`` → đọc lại bằng parser của launcher + chữ ký bản đang chạy; lỗi → trả lại
  byte cũ. Mất điện ở bất kỳ điểm nào: file là bản cũ HOẶC bản mới hoàn chỉnh.
* Chạy bằng ``-I -B``: không thư mục hiện hành/script trên ``sys.path``; không sinh ``__pycache__`` (cây release đã ký
  và thư mục launcher không đổi).
"""

import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True       # TRƯỚC mọi import khác: không sinh __pycache__ ở bất kỳ đâu

import base64  # noqa: E402
import binascii  # noqa: E402
import contextlib  # noqa: E402
import hashlib  # noqa: E402
import importlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from typing import Callable, Optional  # noqa: E402

DINH_DANG = 1
UNG_DUNG = "TimClipPro"
LOAI_YEU_CAU = "yeu_cau_them_khoa_tin_cay"
LOAI_UY_QUYEN = "uy_quyen_them_khoa_tin_cay"
MIEN_YEU_CAU = b"TimClipPro/yeu-cau-them-khoa-tin-cay/v1\n"
MIEN_UY_QUYEN = b"TimClipPro/uy-quyen-them-khoa-tin-cay/v1\n"
MIEN_CAI_DAT = b"TimClipPro/dinh-danh-cai-dat/v1\n"
MIEN_TU_KIEM = b"TimClipPro/tu-kiem-khoa/v1\n"
GIOI_HAN_FILE = 16 * 1024
GIOI_HAN_TIN_CAY = 64 * 1024
HAN_MAC_DINH_NGAY = 30
HAN_TOI_DA_NGAY = 90
TUOI_YEU_CAU_TOI_DA = timedelta(days=30)
LECH_GIO = timedelta(days=1)
TEN_TIN_CAY = "trusted_keys.json"
THU_MUC_SAO_LUU = "trust_backups"
MODULE_LAUNCHER = ("runtime_paths", "khoa", "managed_update")
# Trạng thái nhật ký cập nhật GIỮA lúc làm — không đổi trust store khi đó (launcher sẽ khôi phục ở lần chạy kế).
_DANG_DO = ("DOWNLOADING", "VERIFIED", "WAITING_IDLE", "QUIESCED", "BACKED_UP", "MIGRATING", "ACTIVATING",
            "HEALTHCHECK", "ROLLBACK")
TRUONG_YEU_CAU = frozenset({"dinh_dang", "loai", "ung_dung", "khoa_moi", "ten_may", "cai_dat_sha256",
                            "trust_store_sha256", "khoa_hien_co", "phien_ban_launcher", "ban_dang_chay", "tao_luc",
                            "ma_yeu_cau"})
TRUONG_UY_QUYEN = frozenset({"dinh_dang", "loai", "ung_dung", "khoa_moi", "ten_may", "cai_dat_sha256",
                             "trust_store_sha256", "khoa_hien_co", "ma_yeu_cau", "yeu_cau_sha256", "ma_uy_quyen",
                             "tao_luc", "het_han", "ky_boi"})
_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TEN_MAY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$")
_PB = re.compile(r"^(?:|\d{1,6}\.\d{1,6}\.\d{1,6})$")
_THOI_DIEM = "%Y-%m-%dT%H:%M:%SZ"


class LoiUyQuyen(RuntimeError):
    """Từ chối / không làm được — thông điệp tiếng Việt, không chứa bí mật. Trust store KHÔNG đổi (trừ khi thông
    điệp nói rõ đã trả lại bản cũ)."""

    def __init__(self, ma: str, thong_diep: str):
        super().__init__(thong_diep)
        self.ma = ma


class MatDien(BaseException):
    """CHỈ dùng trong kiểm thử: mô phỏng tiến trình chết ở một điểm (không bị ``except Exception`` bắt)."""


# ---------------------------------------------------------------------------
#  Định dạng chung: nội dung chuẩn hoá + chữ ký Ed25519 có tiền tố miền
# ---------------------------------------------------------------------------

def chuan_hoa(obj) -> bytes:
    """Byte được ký: JSON sắp khoá, không khoảng trắng, chỉ ASCII — cùng nội dung → cùng byte trên mọi máy."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def tao_key_id(khoa_cong_khai_raw: bytes) -> str:
    """Như ``managed_update.tao_key_id`` (test khoá hai bên luôn bằng nhau)."""
    return hashlib.sha256(khoa_cong_khai_raw).hexdigest()[:16]


def bam_cai_dat(installation_id: str) -> str:
    """Băm (có tiền tố miền) định danh cài đặt — ràng buộc uỷ quyền vào ĐÚNG một cài đặt mà không công bố định danh."""
    return hashlib.sha256(MIEN_CAI_DAT + str(installation_id).encode("utf-8")).hexdigest()


def _raw_cong_khai(khoa_rieng) -> bytes:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    return khoa_rieng.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _thoi_diem(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(_THOI_DIEM)


def _doc_thoi_diem(s, ten: str) -> datetime:
    try:
        return datetime.strptime(str(s), _THOI_DIEM).replace(tzinfo=timezone.utc)
    except ValueError:
        raise LoiUyQuyen("dinh_dang", f"Trường {ten} không đúng dạng thời điểm UTC.") from None


def _bay_gio(bay_gio: Optional[datetime]) -> datetime:
    return (bay_gio or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _khong_trung_khoa(cap: list) -> dict:
    d = {}
    for k, v in cap:
        if k in d:
            raise ValueError(f"trùng khoá JSON «{k}»")
        d[k] = v
    return d


def _doc_json_chat(raw: bytes, ten: str, gioi_han: int = GIOI_HAN_FILE) -> dict:
    if len(raw) > gioi_han:
        raise LoiUyQuyen("kich_thuoc", f"File {ten} quá lớn.")
    try:
        d = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_khong_trung_khoa)
    except (UnicodeDecodeError, ValueError) as e:
        raise LoiUyQuyen("dinh_dang", f"File {ten} hỏng ({e.__class__.__name__}: {str(e)[:80]}).") from None
    if not isinstance(d, dict):
        raise LoiUyQuyen("dinh_dang", f"File {ten} không đúng cấu trúc.")
    return d


def doc_khoa_cong_khai(muc) -> tuple:
    """``{"key_id", "ed25519_pub_b64"}`` → ``(key_id, raw 32 byte)``; khoá phải là điểm Ed25519 hợp lệ."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        key_id = str(muc["key_id"])
        raw = base64.b64decode(muc["ed25519_pub_b64"], validate=True)
        Ed25519PublicKey.from_public_bytes(raw)
    except (KeyError, TypeError, ValueError, binascii.Error):
        raise LoiUyQuyen("khoa_moi", "Khoá công khai hỏng (không phải khoá Ed25519 32 byte).") from None
    if len(raw) != 32 or not _HEX16.match(key_id) or key_id != tao_key_id(raw):
        raise LoiUyQuyen("khoa_moi", "key_id không khớp khoá công khai.")
    return key_id, raw


def _ky(noi_dung: dict, khoa_rieng, mien: bytes) -> bytes:
    chu_ky = {"thuat_toan": "ed25519", "key_id": tao_key_id(_raw_cong_khai(khoa_rieng)),
              "chu_ky_b64": base64.b64encode(khoa_rieng.sign(mien + chuan_hoa(noi_dung))).decode()}
    return (json.dumps({"noi_dung": noi_dung, "chu_ky": chu_ky}, ensure_ascii=False, indent=1, sort_keys=True)
            + "\n").encode("utf-8")


def _tach(raw: bytes, ten: str) -> tuple:
    d = _doc_json_chat(raw, ten)
    if set(d) != {"noi_dung", "chu_ky"} or not isinstance(d["noi_dung"], dict) or not isinstance(d["chu_ky"], dict):
        raise LoiUyQuyen("dinh_dang", f"File {ten} không đúng cấu trúc (cần đúng «noi_dung» + «chu_ky»).")
    ck = d["chu_ky"]
    try:
        if set(ck) != {"thuat_toan", "key_id", "chu_ky_b64"} or ck["thuat_toan"] != "ed25519" \
                or not _HEX16.match(str(ck["key_id"])):
            raise ValueError
        sig = base64.b64decode(ck["chu_ky_b64"], validate=True)
    except (ValueError, TypeError, binascii.Error):
        raise LoiUyQuyen("chu_ky", f"Chữ ký của {ten} hỏng.") from None
    if len(sig) != 64:
        raise LoiUyQuyen("chu_ky", f"Chữ ký của {ten} sai độ dài.")
    return d["noi_dung"], {"key_id": str(ck["key_id"]), "sig": sig}


def _xac_minh(noi_dung: dict, ck: dict, khoa: dict, mien: bytes, ten: str) -> str:
    from cryptography.exceptions import InvalidSignature

    pub = khoa.get(ck["key_id"])
    if pub is None:
        raise LoiUyQuyen("khoa_la", f"{ten} được ký bằng khoá KHÔNG được tin ({ck['key_id']}).")
    try:
        pub.verify(ck["sig"], mien + chuan_hoa(noi_dung))
    except InvalidSignature:
        raise LoiUyQuyen("chu_ky", f"Chữ ký {ten} KHÔNG hợp lệ (nội dung bị sửa hoặc ký sai).") from None
    return ck["key_id"]


def _kiem_chung(nd: dict, loai: str, truong: frozenset) -> tuple:
    if set(nd) != set(truong):
        thua_thieu = sorted(set(truong) ^ set(nd))
        raise LoiUyQuyen("dinh_dang", f"Nội dung thiếu/thừa trường: {', '.join(thua_thieu)}.")
    if nd["dinh_dang"] != DINH_DANG or nd["loai"] != loai or nd["ung_dung"] != UNG_DUNG:
        raise LoiUyQuyen("dinh_dang", "Sai loại tài liệu (định dạng / loại / ứng dụng).")
    if not isinstance(nd["khoa_moi"], dict) or set(nd["khoa_moi"]) != {"key_id", "ed25519_pub_b64"}:
        raise LoiUyQuyen("khoa_moi", "Mục khoá mới không đúng cấu trúc.")
    key_id, raw = doc_khoa_cong_khai(nd["khoa_moi"])
    if not (isinstance(nd["ten_may"], str) and _TEN_MAY.match(nd["ten_may"])):
        raise LoiUyQuyen("dinh_dang", "Tên máy không hợp lệ (chữ không dấu, số, «_.-»; ≤ 32 ký tự).")
    for t in ("cai_dat_sha256", "trust_store_sha256"):
        if not (isinstance(nd[t], str) and _HEX64.match(nd[t])):
            raise LoiUyQuyen("dinh_dang", f"Trường {t} không phải SHA-256.")
    hien = nd["khoa_hien_co"]
    if not (isinstance(hien, list) and hien and all(isinstance(x, str) and _HEX16.match(x) for x in hien)
            and hien == sorted(set(hien))):
        raise LoiUyQuyen("dinh_dang", "Danh sách khoá hiện có không hợp lệ.")
    if key_id in hien:
        raise LoiUyQuyen("da_co", f"Khoá {key_id} ĐÃ được tin trên máy đích.")
    if not (isinstance(nd["ma_yeu_cau"], str) and _HEX32.match(nd["ma_yeu_cau"])):
        raise LoiUyQuyen("dinh_dang", "Mã yêu cầu không hợp lệ.")
    _doc_thoi_diem(nd["tao_luc"], "tao_luc")
    return key_id, raw


# ---------------------------------------------------------------------------
#  Yêu cầu (máy mới) — uỷ quyền (máy đang được tin)
# ---------------------------------------------------------------------------

def tao_yeu_cau(khoa_rieng, *, ten_may: str, cai_dat: "CaiDatDich", bay_gio: Optional[datetime] = None,
                ma: str = "") -> bytes:
    """Yêu cầu TỰ KÝ bằng khoá mới, ràng buộc vào cài đặt ``cai_dat`` (đọc bằng ``doc_cai_dat``)."""
    raw = _raw_cong_khai(khoa_rieng)
    nd = {"dinh_dang": DINH_DANG, "loai": LOAI_YEU_CAU, "ung_dung": UNG_DUNG,
          "khoa_moi": {"key_id": tao_key_id(raw), "ed25519_pub_b64": base64.b64encode(raw).decode()},
          "ten_may": ten_may, "cai_dat_sha256": cai_dat.cai_dat_sha256,
          "trust_store_sha256": cai_dat.sha_tin_cay, "khoa_hien_co": sorted(cai_dat.khoa),
          "phien_ban_launcher": int(cai_dat.phien_ban_launcher), "ban_dang_chay": cai_dat.ban_dang_chay,
          "tao_luc": _thoi_diem(_bay_gio(bay_gio)), "ma_yeu_cau": ma or uuid.uuid4().hex}
    _kiem_chung(nd, LOAI_YEU_CAU, TRUONG_YEU_CAU)
    return _ky(nd, khoa_rieng, MIEN_YEU_CAU)


def doc_yeu_cau(raw: bytes) -> dict:
    """Cấu trúc + chữ ký TỰ KÝ của khoá mới (chứng minh giữ khoá riêng). Trả nội dung."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    nd, ck = _tach(raw, "yêu cầu")
    key_id, raw_pub = _kiem_chung(nd, LOAI_YEU_CAU, TRUONG_YEU_CAU)
    if not (isinstance(nd["phien_ban_launcher"], int) and nd["phien_ban_launcher"] >= 1
            and isinstance(nd["ban_dang_chay"], str) and _PB.match(nd["ban_dang_chay"])):
        raise LoiUyQuyen("dinh_dang", "Phiên bản launcher / bản đang chạy không hợp lệ.")
    if ck["key_id"] != key_id:
        raise LoiUyQuyen("yeu_cau", "Yêu cầu không do chính khoá mới ký (thiếu chứng minh giữ khoá riêng).")
    _xac_minh(nd, ck, {key_id: Ed25519PublicKey.from_public_bytes(raw_pub)}, MIEN_YEU_CAU, "yêu cầu")
    return nd


def tao_uy_quyen(raw_yeu_cau: bytes, khoa_rieng_ky, *, khoa_tin_cay: dict, bay_gio: Optional[datetime] = None,
                 han_ngay: int = HAN_MAC_DINH_NGAY, ma: str = "") -> bytes:
    """Máy đang được tin: uỷ quyền cho ĐÚNG yêu cầu đã kiểm. ``khoa_tin_cay``: khoá CÔNG KHAI đang tin
    (``managed_update.doc_khoa_tin_cay``) — khoá ký phải nằm trong đó VÀ trong danh sách khoá của máy đích."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    yc = doc_yeu_cau(raw_yeu_cau)
    raw_ky = _raw_cong_khai(khoa_rieng_ky)
    ky_boi = tao_key_id(raw_ky)
    pub = khoa_tin_cay.get(ky_boi)
    if pub is None or pub.public_bytes(Encoding.Raw, PublicFormat.Raw) != raw_ky:
        raise LoiUyQuyen("khoa_ky", "Khoá ký không nằm trong danh sách khoá công khai đang tin (--tin-cay).")
    if ky_boi not in yc["khoa_hien_co"]:
        raise LoiUyQuyen("khoa_ky", "Máy đích KHÔNG tin khoá ký này — uỷ quyền sẽ bị máy đích từ chối.")
    if not (isinstance(han_ngay, int) and 1 <= han_ngay <= HAN_TOI_DA_NGAY):
        raise LoiUyQuyen("han", f"Hạn uỷ quyền phải từ 1 đến {HAN_TOI_DA_NGAY} ngày.")
    now = _bay_gio(bay_gio)
    luc_yc = _doc_thoi_diem(yc["tao_luc"], "tao_luc")
    if luc_yc > now + LECH_GIO:
        raise LoiUyQuyen("han", "Yêu cầu ghi thời điểm ở tương lai — kiểm đồng hồ máy.")
    if now - luc_yc > TUOI_YEU_CAU_TOI_DA:
        raise LoiUyQuyen("han", "Yêu cầu quá cũ (> 30 ngày) — tạo yêu cầu mới trên máy đích.")
    nd = {k: yc[k] for k in ("dinh_dang", "ung_dung", "khoa_moi", "ten_may", "cai_dat_sha256",
                             "trust_store_sha256", "khoa_hien_co", "ma_yeu_cau")}
    nd.update({"loai": LOAI_UY_QUYEN, "yeu_cau_sha256": hashlib.sha256(chuan_hoa(yc)).hexdigest(),
               "ma_uy_quyen": ma or uuid.uuid4().hex, "tao_luc": _thoi_diem(now),
               "het_han": _thoi_diem(now + timedelta(days=han_ngay)), "ky_boi": ky_boi})
    _kiem_chung(nd, LOAI_UY_QUYEN, TRUONG_UY_QUYEN)
    return _ky(nd, khoa_rieng_ky, MIEN_UY_QUYEN)


def doc_uy_quyen(raw: bytes, khoa_tin_cay: dict, *, bay_gio: Optional[datetime] = None) -> dict:
    """Cấu trúc + chữ ký (bằng khoá ĐANG tin) + hạn. Ràng buộc cài đặt kiểm ở ``kiem_rang_buoc``."""
    nd, ck = _tach(raw, "uỷ quyền")
    key_id, _ = _kiem_chung(nd, LOAI_UY_QUYEN, TRUONG_UY_QUYEN)
    for t in ("yeu_cau_sha256",):
        if not (isinstance(nd[t], str) and _HEX64.match(nd[t])):
            raise LoiUyQuyen("dinh_dang", f"Trường {t} không phải SHA-256.")
    if not (isinstance(nd["ma_uy_quyen"], str) and _HEX32.match(nd["ma_uy_quyen"])):
        raise LoiUyQuyen("dinh_dang", "Mã uỷ quyền không hợp lệ.")
    if not (isinstance(nd["ky_boi"], str) and _HEX16.match(nd["ky_boi"])) or ck["key_id"] != nd["ky_boi"]:
        raise LoiUyQuyen("chu_ky", "Khoá ký không khớp trường «ky_boi».")
    if nd["ky_boi"] == key_id:
        raise LoiUyQuyen("chu_ky", "Khoá mới không được tự uỷ quyền cho chính nó.")
    _xac_minh(nd, ck, khoa_tin_cay, MIEN_UY_QUYEN, "uỷ quyền")
    now = _bay_gio(bay_gio)
    tao, het = _doc_thoi_diem(nd["tao_luc"], "tao_luc"), _doc_thoi_diem(nd["het_han"], "het_han")
    if tao > now + LECH_GIO:
        raise LoiUyQuyen("han", "Uỷ quyền ghi thời điểm tạo ở tương lai — kiểm đồng hồ máy.")
    if het <= tao or het - tao > timedelta(days=HAN_TOI_DA_NGAY):
        raise LoiUyQuyen("han", "Hạn uỷ quyền không hợp lệ.")
    if now > het:
        raise LoiUyQuyen("han", "Uỷ quyền đã hết hạn — xin uỷ quyền mới.")
    return nd


def kiem_rang_buoc(nd: dict, *, cai_dat_sha256: str, trust_store_sha256: str, khoa_hien_co) -> None:
    if nd["cai_dat_sha256"] != cai_dat_sha256:
        raise LoiUyQuyen("cai_dat", "Uỷ quyền dành cho cài đặt KHÁC — không dùng được ở máy này.")
    if nd["khoa_moi"]["key_id"] in set(khoa_hien_co):
        raise LoiUyQuyen("da_co", f"Khoá {nd['khoa_moi']['key_id']} ĐÃ được tin trên máy này — không ghi lại.")
    if nd["trust_store_sha256"] != trust_store_sha256 or nd["khoa_hien_co"] != sorted(khoa_hien_co):
        raise LoiUyQuyen("trust_store", "Trust store đã đổi kể từ lúc tạo yêu cầu — uỷ quyền này không còn dùng "
                                        "được (tạo yêu cầu mới).")


# ---------------------------------------------------------------------------
#  Cài đặt đích: nạp launcher ĐÃ CÀI, đọc trust store + định danh + bản đang chạy
# ---------------------------------------------------------------------------

def nap_launcher(goc: str) -> SimpleNamespace:
    """``managed_update`` / ``runtime_paths`` / ``khoa`` ĐÃ CÀI ở ``<goc>/launcher`` — đúng parser launcher dùng.
    Không sinh ``__pycache__``; module cùng tên đã nạp trước đó (vd. của repo) được trả lại nguyên vẹn."""
    thu_muc = os.path.join(os.path.abspath(goc), "launcher")
    thieu = [t for t in MODULE_LAUNCHER if not os.path.isfile(os.path.join(thu_muc, t + ".py"))]
    if thieu:
        raise LoiUyQuyen("launcher", f"Thư mục cài đặt thiếu launcher ({', '.join(thieu)}) — sai --goc?")
    cu = {t: sys.modules.pop(t) for t in MODULE_LAUNCHER if t in sys.modules}
    khong_ghi = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, thu_muc)
    nap = {}
    try:
        for t in MODULE_LAUNCHER:
            m = importlib.import_module(t)
            if os.path.normcase(os.path.dirname(os.path.realpath(m.__file__))) != \
                    os.path.normcase(os.path.realpath(thu_muc)):
                raise LoiUyQuyen("launcher", f"Module {t} không nạp từ launcher của cài đặt.")
            nap[t] = m
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(thu_muc)
        for t in MODULE_LAUNCHER:
            sys.modules.pop(t, None)
        sys.modules.update(cu)
        sys.dont_write_bytecode = khong_ghi
    return SimpleNamespace(mu=nap["managed_update"], rp=nap["runtime_paths"], khoa=nap["khoa"], thu_muc=thu_muc)


@dataclass
class CaiDatDich:
    goc: str
    cd: object                          # managed_update.CaiDat (của launcher đã cài)
    duong_dan_tin_cay: str
    byte_tin_cay: bytes
    sha_tin_cay: str
    khoa: dict                          # {key_id: Ed25519PublicKey} — đọc bằng parser của launcher đã cài
    cai_dat_sha256: str
    phien_ban_launcher: int
    ban_dang_chay: str                  # "" = chưa có bản nào được kích hoạt
    ban_dang_chay_ky_boi: str


def _doc_cau_hinh(goc: str) -> dict:
    p = os.path.join(goc, "launcher", "launcher.json")
    try:
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise LoiUyQuyen("cai_dat", "Không thấy launcher/launcher.json — --goc không phải cài đặt managed.") from None
    except (OSError, ValueError):
        raise LoiUyQuyen("cai_dat", "launcher.json hỏng — chạy «launcher.py doctor».") from None
    state = cfg.get("state_root") if isinstance(cfg, dict) else None
    if not (isinstance(state, str) and os.path.isabs(state)):
        raise LoiUyQuyen("cai_dat", "launcher.json thiếu state_root tuyệt đối.")
    return cfg


def _dung_cai_dat(goc: str, L) -> object:
    cfg = _doc_cau_hinh(goc)
    try:
        return L.mu.CaiDat(goc=goc, state_root=os.path.abspath(cfg["state_root"]))
    except L.mu.LoiCapNhat as e:
        raise LoiUyQuyen("bo_cuc", str(e)) from None


def kiem_ban_dang_chay(cd, khoa: dict, L) -> tuple:
    """Như ``launcher doctor``: chữ ký + manifest + con trỏ + cây file của bản ĐANG kích hoạt.
    Trả ``(phiên bản, key_id đã ký)``; chưa có bản nào → ``("", "")``."""
    try:
        cur = L.mu.doc_json(cd.file_trang_thai("current.json"))
        if not cur:
            return "", ""
        rel = str(cur.get("release") or "")
        with open(os.path.join(rel, L.mu.TEN_MANIFEST), "rb") as f:
            raw_m = f.read()
        with open(os.path.join(rel, L.mu.TEN_CHU_KY), "rb") as f:
            raw_s = f.read()
        key_id = L.mu.kiem_chu_ky(raw_m, raw_s, khoa)
        m = L.mu.doc_manifest(raw_m)
        if cur.get("manifest_sha256") != m.sha256:
            raise L.mu.LoiCapNhat("con_tro", "con trỏ không khớp manifest đã ký của release")
        L.mu.kiem_cay_release(rel, m)
    except (OSError, L.mu.LoiCapNhat) as e:
        raise LoiUyQuyen("ban_dang_chay", f"Bản đang chạy không xác minh được ({e}) — chạy «launcher.py doctor», "
                                          "không đổi trust store khi cài đặt chưa lành.") from None
    return m.phien_ban, key_id


def doc_cai_dat(goc: str, L, *, kiem_ban: bool = True) -> CaiDatDich:
    """Đọc (không ghi gì): bố cục, định danh (khớp thư mục cài đặt), trust store (byte + parser của launcher),
    bản đang chạy (chữ ký + cây file)."""
    goc = os.path.abspath(goc)
    cd = _dung_cai_dat(goc, L)
    try:
        dd = L.rp.doc_dinh_danh(cd.state_root)
    except L.rp.LoiRuntime as e:
        raise LoiUyQuyen("dinh_danh", str(e)) from None
    if os.path.normcase(os.path.abspath(str(dd.get("installation_root") or ""))) != os.path.normcase(goc):
        raise LoiUyQuyen("dinh_danh", "Định danh trong state root trỏ thư mục cài đặt KHÁC — chạy «launcher.py doctor».")
    p = os.path.join(goc, "launcher", TEN_TIN_CAY)
    try:
        with open(p, "rb") as f:
            b = f.read(GIOI_HAN_TIN_CAY + 1)
    except OSError:
        raise LoiUyQuyen("tin_cay", "Không đọc được launcher/trusted_keys.json.") from None
    if len(b) > GIOI_HAN_TIN_CAY:
        raise LoiUyQuyen("tin_cay", "trusted_keys.json quá lớn.")
    try:
        khoa = L.mu.doc_khoa_tin_cay(p)
    except L.mu.LoiCapNhat as e:
        raise LoiUyQuyen("tin_cay", str(e)) from None
    ban, ky_boi = kiem_ban_dang_chay(cd, khoa, L) if kiem_ban else ("", "")
    return CaiDatDich(goc=goc, cd=cd, duong_dan_tin_cay=p, byte_tin_cay=b, sha_tin_cay=hashlib.sha256(b).hexdigest(),
                      khoa=khoa, cai_dat_sha256=bam_cai_dat(dd["installation_id"]),
                      phien_ban_launcher=int(getattr(L.mu, "PHIEN_BAN_LAUNCHER", 1)), ban_dang_chay=ban,
                      ban_dang_chay_ky_boi=ky_boi)


@contextlib.contextmanager
def _giu_khoa_cap_nhat(cd, L, viec: str):
    """Cùng khoá HĐH với bộ cập nhật (``update_state/updater.lock``) — không đổi trust store khi đang cập nhật."""
    os.makedirs(cd.update_state, exist_ok=True)
    k = L.khoa.KhoaTienTrinh(cd.file_trang_thai("updater.lock"), viec)
    try:
        k.__enter__()
    except L.khoa.DangChayRoi:
        raise LoiUyQuyen("ban", "Bộ cập nhật đang chạy trên máy này — đợi xong rồi chạy lại.") from None
    try:
        nk = L.mu.doc_json(cd.file_trang_thai("journal.json"), bat_buoc_hop_le=False) or {}
        if isinstance(nk, dict) and nk.get("trang_thai") in _DANG_DO:
            raise LoiUyQuyen("dang_do", f"Lượt cập nhật trước còn dở ({nk.get('trang_thai')}) — mở TimClipPro.bat "
                                        "hoặc chạy CapNhat.bat để launcher khôi phục xong rồi chạy lại.")
        yield
    finally:
        k.__exit__(None, None, None)


def _ghi_nguyen_tu(path: str, du_lieu: bytes, diem_dung: Callable = lambda _t: None) -> None:
    """File tạm CÙNG thư mục → flush → fsync → ``os.replace`` (thử lại khi tiến trình khác đang mở đọc)."""
    tam = f"{path}.tmp-{uuid.uuid4().hex[:8]}"
    try:
        with open(tam, "xb") as f:
            f.write(du_lieu)
            f.flush()
            os.fsync(f.fileno())
        diem_dung("sau_ghi_tam")
        for lan in range(10):
            try:
                os.replace(tam, path)
                break
            except PermissionError:
                if lan == 9:
                    raise
                time.sleep(0.05 * (lan + 1))
    except Exception:                       # mất điện thật (MatDien trong test) không dọn được gì
        with contextlib.suppress(OSError):
            os.remove(tam)
        raise


def _don_tam(path: str) -> list:
    """File tạm sót của CHÍNH công cụ này (mất điện giữa lúc ghi) — chỉ đúng mẫu ``trusted_keys.json.tmp-*``."""
    thu_muc, ten = os.path.split(path)
    da = []
    for f in os.listdir(thu_muc):
        if f.startswith(ten + ".tmp-"):
            with contextlib.suppress(OSError):
                os.remove(os.path.join(thu_muc, f))
                da.append(f)
    return da


def _ghi_file_moi(path: str, du_lieu: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "xb") as f:
        f.write(du_lieu)
        f.flush()
        os.fsync(f.fileno())


def _sao_luu(tt: CaiDatDich, luc: datetime, loai: str, kem: Optional[tuple] = None) -> str:
    thu_muc = os.path.join(tt.goc, "launcher", THU_MUC_SAO_LUU)
    p = os.path.join(thu_muc, f"trusted_keys_{luc:%Y%m%d_%H%M%S}_{loai}_{tt.sha_tin_cay[:12]}_"
                              f"{uuid.uuid4().hex[:6]}.json")
    _ghi_file_moi(p, tt.byte_tin_cay)
    if kem:
        ten, du = kem
        p_kem = os.path.join(thu_muc, ten)
        try:
            _ghi_file_moi(p_kem, du)
        except FileExistsError:                 # lần trước dừng giữa chừng (mất điện) — cùng byte thì giữ
            with open(p_kem, "rb") as f:
                if f.read() != du:
                    raise LoiUyQuyen("sao_luu", f"Đã có {ten} với nội dung KHÁC — kiểm tay thư mục sao lưu.") from None
    return p


def _trust_store_moi(byte_cu: bytes, nd: dict, luc: datetime) -> bytes:
    d = json.loads(byte_cu.decode("utf-8-sig"))
    khoa = list(d.get("khoa") or [])
    khoa.append({"key_id": nd["khoa_moi"]["key_id"], "ed25519_pub_b64": nd["khoa_moi"]["ed25519_pub_b64"],
                 "ghi_chu": f"Khoá phát hành TimClipPro kênh Stable — máy {nd['ten_may']}; ghi danh {luc:%Y-%m-%d} "
                            f"theo uỷ quyền của khoá {nd['ky_boi']}",
                 "ghi_danh": {"ma_uy_quyen": nd["ma_uy_quyen"], "ky_boi": nd["ky_boi"], "luc": _thoi_diem(luc)}})
    d["khoa"] = khoa
    return (json.dumps(d, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def _kiem_sau_ghi(tt: CaiDatDich, L, mong: dict) -> None:
    """Đọc lại bằng ĐÚNG parser của launcher: tập khoá = ``mong`` (key_id → raw), khoá cũ cùng byte; bản đang chạy
    vẫn xác minh được."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    try:
        moi = L.mu.doc_khoa_tin_cay(tt.duong_dan_tin_cay)
    except L.mu.LoiCapNhat as e:
        raise LoiUyQuyen("kiem_sau_ghi", f"Parser của launcher không đọc được file vừa ghi ({e}).") from None
    thuc = {k: v.public_bytes(Encoding.Raw, PublicFormat.Raw) for k, v in moi.items()}
    if thuc != mong:
        raise LoiUyQuyen("kiem_sau_ghi", "Trust store đọc lại không đúng tập khoá mong đợi.")
    if tt.ban_dang_chay:
        ban, _ = kiem_ban_dang_chay(tt.cd, moi, L)
        if ban != tt.ban_dang_chay:
            raise LoiUyQuyen("kiem_sau_ghi", "Bản đang chạy đổi trong lúc ghi danh.")


def _raw_cac_khoa(khoa: dict) -> dict:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    return {k: v.public_bytes(Encoding.Raw, PublicFormat.Raw) for k, v in khoa.items()}


def ghi_danh(goc: str, raw_uy_quyen: bytes, *, xac_nhan: Callable[[dict], bool],
             bay_gio: Optional[datetime] = None, diem_dung: Optional[Callable[[str], None]] = None) -> dict:
    """Ghi danh khoá mới theo uỷ quyền. ``xac_nhan(tóm_tắt) -> bool``: chủ máy xác nhận (CLI: gõ trong console).
    Trả ``{"trang_thai": "DA_GHI_DANH", "khoa", "sao_luu", ...}``; mọi từ chối → ``LoiUyQuyen``, không đổi gì."""
    dung = diem_dung or (lambda _t: None)
    now = _bay_gio(bay_gio)
    goc = os.path.abspath(goc)
    L = nap_launcher(goc)
    cd = _dung_cai_dat(goc, L)
    with _giu_khoa_cap_nhat(cd, L, "ghi danh khoá tin cậy"):
        tt = doc_cai_dat(goc, L)
        nd = doc_uy_quyen(raw_uy_quyen, tt.khoa, bay_gio=now)
        kiem_rang_buoc(nd, cai_dat_sha256=tt.cai_dat_sha256, trust_store_sha256=tt.sha_tin_cay,
                       khoa_hien_co=list(tt.khoa))
        don = _don_tam(tt.duong_dan_tin_cay)
        tom_tat = {"khoa_moi": nd["khoa_moi"]["key_id"], "ten_may": nd["ten_may"], "ky_boi": nd["ky_boi"],
                   "khoa_hien_co": sorted(tt.khoa), "ban_dang_chay": tt.ban_dang_chay,
                   "ban_dang_chay_ky_boi": tt.ban_dang_chay_ky_boi, "het_han": nd["het_han"],
                   "ma_uy_quyen": nd["ma_uy_quyen"]}
        if not xac_nhan(dict(tom_tat)):
            raise LoiUyQuyen("huy", "Chủ máy không xác nhận — chưa đổi gì.")
        dung("truoc_sao_luu")
        sao_luu = _sao_luu(tt, now, "truoc_ghi_danh", (f"uy_quyen_{nd['ma_uy_quyen']}.json", raw_uy_quyen))
        dung("sau_sao_luu")
        mong = {**_raw_cac_khoa(tt.khoa), nd["khoa_moi"]["key_id"]: base64.b64decode(nd["khoa_moi"]["ed25519_pub_b64"])}
        try:
            _ghi_nguyen_tu(tt.duong_dan_tin_cay, _trust_store_moi(tt.byte_tin_cay, nd, now), dung)
            dung("sau_thay")
            _kiem_sau_ghi(tt, L, mong)
        except Exception as e:  # noqa: BLE001 — mọi lỗi sau khi bắt đầu ghi → trả lại byte cũ
            _ghi_nguyen_tu(tt.duong_dan_tin_cay, tt.byte_tin_cay)
            with open(tt.duong_dan_tin_cay, "rb") as f:
                tra_lai = f.read() == tt.byte_tin_cay
            raise LoiUyQuyen("kiem_sau_ghi", f"Ghi danh KHÔNG thành: {e} — "
                             + ("đã TRẢ LẠI trust store cũ (đúng từng byte)." if tra_lai
                                else f"KHÔNG trả lại được — chép tay {sao_luu} về launcher/trusted_keys.json.")
                             ) from None
    return {"trang_thai": "DA_GHI_DANH", "khoa": sorted(mong), "sao_luu": sao_luu, "don_file_tam": don, **tom_tat}


def hoan_tac(goc: str, duong_dan_sao_luu: str, *, xac_nhan: Callable[[dict], bool],
             bay_gio: Optional[datetime] = None, diem_dung: Optional[Callable[[str], None]] = None) -> dict:
    """Trả trust store về một bản sao lưu TRƯỚC đó (chỉ GỠ khoá, không thêm). Từ chối nếu bản đang chạy (hoặc
    bản đã chốt) do khoá sắp gỡ ký — gỡ khi đó làm launcher không còn xác minh được bản đang chạy."""
    dung = diem_dung or (lambda _t: None)
    now = _bay_gio(bay_gio)
    goc = os.path.abspath(goc)
    L = nap_launcher(goc)
    cd = _dung_cai_dat(goc, L)
    with _giu_khoa_cap_nhat(cd, L, "hoàn tác khoá tin cậy"):
        tt = doc_cai_dat(goc, L)
        try:
            with open(duong_dan_sao_luu, "rb") as f:
                b_sl = f.read(GIOI_HAN_TIN_CAY + 1)
            khoa_sl = L.mu.doc_khoa_tin_cay(duong_dan_sao_luu)
        except (OSError, L.mu.LoiCapNhat) as e:
            raise LoiUyQuyen("sao_luu", f"Không đọc được bản sao lưu ({e}).") from None
        raw_sl, raw_ht = _raw_cac_khoa(khoa_sl), _raw_cac_khoa(tt.khoa)
        if any(raw_ht.get(k) != v for k, v in raw_sl.items()):
            raise LoiUyQuyen("sao_luu", "Bản sao lưu có khoá không còn trong trust store hiện tại — không phải bản "
                                        "trước của file này.")
        go_bo = sorted(set(raw_ht) - set(raw_sl))
        if not go_bo:
            raise LoiUyQuyen("sao_luu", "Bản sao lưu trùng tập khoá hiện tại — không có gì để hoàn tác.")
        for ten in ("current.json", "last_good.json"):
            p = L.mu.doc_json(cd.file_trang_thai(ten), bat_buoc_hop_le=False) or {}
            rel = str(p.get("release") or "") if isinstance(p, dict) else ""
            if not rel:
                continue
            try:
                with open(os.path.join(rel, L.mu.TEN_MANIFEST), "rb") as f:
                    raw_m = f.read()
                with open(os.path.join(rel, L.mu.TEN_CHU_KY), "rb") as f:
                    L.mu.kiem_chu_ky(raw_m, f.read(), khoa_sl)
            except (OSError, L.mu.LoiCapNhat):
                raise LoiUyQuyen("dang_dung", f"Bản {p.get('phien_ban', '?')} ({ten}) do khoá sắp gỡ ký (hoặc không "
                                              "xác minh được bằng bản sao lưu) — cập nhật lên bản do khoá còn lại ký "
                                              "trước khi gỡ.") from None
        tom_tat = {"go_bo": go_bo, "con_lai": sorted(raw_sl), "sao_luu": duong_dan_sao_luu}
        if not xac_nhan(dict(tom_tat)):
            raise LoiUyQuyen("huy", "Chủ máy không xác nhận — chưa đổi gì.")
        _don_tam(tt.duong_dan_tin_cay)
        truoc = _sao_luu(tt, now, "truoc_hoan_tac")
        dung("sau_sao_luu")
        try:
            _ghi_nguyen_tu(tt.duong_dan_tin_cay, b_sl, dung)
            dung("sau_thay")
            _kiem_sau_ghi(tt, L, raw_sl)
        except Exception as e:  # noqa: BLE001
            _ghi_nguyen_tu(tt.duong_dan_tin_cay, tt.byte_tin_cay)
            raise LoiUyQuyen("kiem_sau_ghi", f"Hoàn tác KHÔNG thành: {e} — đã TRẢ LẠI trust store trước hoàn tác.") \
                from None
    return {"trang_thai": "DA_HOAN_TAC", "khoa": sorted(raw_sl), "sao_luu_truoc_hoan_tac": truoc, **tom_tat}


def xem(goc: str) -> dict:
    """Chỉ đọc: khoá đang tin, băm trust store/cài đặt, bản đang chạy + khoá đã ký, sao lưu, file tạm sót."""
    goc = os.path.abspath(goc)
    L = nap_launcher(goc)
    tt = doc_cai_dat(goc, L, kiem_ban=False)
    try:                                   # báo lỗi bản đang chạy (vd. cây release thừa __pycache__), không dừng
        ban, ky_boi = kiem_ban_dang_chay(tt.cd, tt.khoa, L)
        loi_ban = ""
    except LoiUyQuyen as e:
        ban, ky_boi, loi_ban = "", "", str(e)
    thu_muc_sl = os.path.join(goc, "launcher", THU_MUC_SAO_LUU)
    d = json.loads(tt.byte_tin_cay.decode("utf-8-sig"))
    return {"khoa": sorted(tt.khoa), "ghi_chu": {str(k.get("key_id")): str(k.get("ghi_chu") or "") for k in d["khoa"]},
            "trust_store_sha256": tt.sha_tin_cay, "cai_dat_sha256": tt.cai_dat_sha256,
            "ban_dang_chay": ban, "ban_dang_chay_ky_boi": ky_boi, "loi_ban_dang_chay": loi_ban,
            "sao_luu": sorted(os.listdir(thu_muc_sl)) if os.path.isdir(thu_muc_sl) else [],
            "file_tam_sot": sorted(f for f in os.listdir(os.path.join(goc, "launcher"))
                                   if f.startswith(TEN_TIN_CAY + ".tmp-"))}


# ---------------------------------------------------------------------------
#  CLI — chủ máy gõ trong console; KHÔNG có cờ bỏ qua xác nhận
# ---------------------------------------------------------------------------

def _utf8_dau_ra() -> None:
    for luong in (sys.stdout, sys.stderr):
        try:
            if (luong.encoding or "").lower().replace("-", "") != "utf8":
                luong.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def co_console() -> bool:
    """stdin là cửa sổ console THẬT (người gõ). Windows: ``isatty()`` cũng đúng với thiết bị NUL (``< nul``, stdin
    của tiến trình tự động) — hỏi thêm ``GetConsoleMode``, chỉ console thật mới trả thành công."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
        if os.name != "nt":
            return True
        import ctypes
        import msvcrt

        che_do = ctypes.c_uint32()
        return bool(ctypes.windll.kernel32.GetConsoleMode(ctypes.c_void_p(msvcrt.get_osfhandle(sys.stdin.fileno())),
                                                          ctypes.byref(che_do)))
    except (AttributeError, ValueError, OSError):
        return False


def _hoi_go(dong_hoi: str, mong: str) -> bool:
    try:
        return input(dong_hoi).strip().lower() == mong.lower()
    except EOFError:
        return False


def main(argv=None) -> int:
    sys.dont_write_bytecode = True
    _utf8_dau_ra()
    import argparse

    ap = argparse.ArgumentParser(description="Ghi danh khoá ký phát hành vào trust store của cài đặt managed")
    sub = ap.add_subparsers(dest="lenh", required=True)
    a = sub.add_parser("xem")
    a.add_argument("--goc", required=True)
    a = sub.add_parser("yeu-cau")
    a.add_argument("--goc", required=True)
    a.add_argument("--khoa-rieng", required=True)
    a.add_argument("--ten-may", required=True)
    a.add_argument("--ra", required=True)
    a = sub.add_parser("ghi-danh")
    a.add_argument("--goc", required=True)
    a.add_argument("--uy-quyen", required=True)
    a = sub.add_parser("hoan-tac")
    a.add_argument("--goc", required=True)
    a.add_argument("--sao-luu", required=True)
    ns = ap.parse_args(argv)
    if not sys.flags.isolated:
        print("[CẢNH BÁO] Nên chạy bằng «python -I -B» (không lấy module từ thư mục hiện hành).", file=sys.stderr)
    try:
        if ns.lenh == "xem":
            x = xem(ns.goc)
            print(f"Khoá đang tin ({len(x['khoa'])}):")
            for k in x["khoa"]:
                print(f"  - {k}  {x['ghi_chu'].get(k, '')}")
            if x["loi_ban_dang_chay"]:
                print(f"[LỖI] {x['loi_ban_dang_chay']}")
            else:
                print(f"Bản đang chạy: {x['ban_dang_chay'] or '(chưa có)'}"
                      + (f" — ký bởi {x['ban_dang_chay_ky_boi']}, chữ ký + cây file ĐẠT" if x["ban_dang_chay"] else ""))
            print(f"trust_store_sha256: {x['trust_store_sha256']}")
            print(f"Sao lưu: {len(x['sao_luu'])} file; file tạm sót: {len(x['file_tam_sot'])}")
            return 1 if x["loi_ban_dang_chay"] else 0
        if not co_console():
            print("[DỪNG] Lệnh này cần chủ máy gõ trong cửa sổ console (Command Prompt/PowerShell) — chạy file .bat "
                  "theo hướng dẫn, không chạy qua ống dẫn/tự động.", file=sys.stderr)
            return 2
        if ns.lenh == "yeu-cau":
            import getpass

            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            if os.path.exists(ns.ra):
                raise LoiUyQuyen("ra", f"Đã có {ns.ra} — không ghi đè.")
            L = nap_launcher(ns.goc)
            tt = doc_cai_dat(ns.goc, L)
            with open(ns.khoa_rieng, "rb") as f:
                pem = f.read()
            mk = getpass.getpass("Mật khẩu khoá ký của máy này (chữ không hiện): ").encode("utf-8")
            try:
                k = serialization.load_pem_private_key(pem, password=mk)
            except (TypeError, ValueError):
                raise LoiUyQuyen("khoa_rieng", "Không mở được khoá ký (sai mật khẩu hoặc file hỏng).") from None
            finally:
                del mk
            if not isinstance(k, Ed25519PrivateKey):
                raise LoiUyQuyen("khoa_rieng", "Khoá ký phải là Ed25519.")
            raw = tao_yeu_cau(k, ten_may=ns.ten_may, cai_dat=tt)
            del k
            _ghi_file_moi(os.path.abspath(ns.ra), raw)
            yc = doc_yeu_cau(raw)
            print(f"ĐÃ TẠO YÊU CẦU: {ns.ra}")
            print(f"  khoá mới : {yc['khoa_moi']['key_id']}   (máy {yc['ten_may']})")
            print(f"  khoá đang tin trên máy này: {', '.join(yc['khoa_hien_co'])}; bản đang chạy {yc['ban_dang_chay']}")
            print("Gửi file yêu cầu này cho máy đang được tin (qua GitHub) — file KHÔNG chứa bí mật.")
            return 0
        if ns.lenh == "ghi-danh":
            with open(ns.uy_quyen, "rb") as f:
                raw = f.read(GIOI_HAN_FILE + 1)

            def xac_nhan(t: dict) -> bool:
                print("=" * 72)
                print(" GHI DANH KHOÁ KÝ PHÁT HÀNH MỚI vào trust store của cài đặt này")
                print(f"   khoá mới   : {t['khoa_moi']}   (máy {t['ten_may']})")
                print(f"   uỷ quyền   : ký bởi khoá {t['ky_boi']} (đang được tin), hết hạn {t['het_han']}")
                print(f"   khoá đang tin: {', '.join(t['khoa_hien_co'])} — GIỮ NGUYÊN")
                print(f"   bản đang chạy: {t['ban_dang_chay'] or '(chưa có)'}")
                print("=" * 72)
                return _hoi_go(f"Gõ 8 ký tự CUỐI của khoá mới ({t['khoa_moi'][:8]}…) để xác nhận: ", t["khoa_moi"][-8:])
            kq = ghi_danh(ns.goc, raw, xac_nhan=xac_nhan)
            print(f"ĐÃ GHI DANH: trust store tin {len(kq['khoa'])} khoá: {', '.join(kq['khoa'])}")
            print(f"  sao lưu bản cũ: {kq['sao_luu']}")
            print("  Kiểm: chạy «launcher.py doctor» — mục «Khoá tin cậy» phải báo số khoá mới.")
            return 0
        if ns.lenh == "hoan-tac":
            def xac_nhan(t: dict) -> bool:
                print(f"HOÀN TÁC trust store về bản sao lưu: gỡ {', '.join(t['go_bo'])}; còn {', '.join(t['con_lai'])}")
                return _hoi_go(f"Gõ 8 ký tự CUỐI của khoá sẽ gỡ ({t['go_bo'][0][:8]}…) để xác nhận: ",
                               t["go_bo"][0][-8:])
            kq = hoan_tac(ns.goc, ns.sao_luu, xac_nhan=xac_nhan)
            print(f"ĐÃ HOÀN TÁC: trust store tin {', '.join(kq['khoa'])}; bản trước hoàn tác lưu ở "
                  f"{kq['sao_luu_truoc_hoan_tac']}")
            return 0
    except LoiUyQuyen as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"[LỖI] {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
