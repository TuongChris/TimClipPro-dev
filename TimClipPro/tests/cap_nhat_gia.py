# -*- coding: utf-8 -*-
"""Bản phát hành TỔNG HỢP cho kiểm thử bộ cập nhật: khoá Ed25519 sinh lúc chạy (không lưu khoá thật),
gói ZIP + RELEASE_FILES.json + manifest ký, nguồn là một thư mục. Không mạng."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import sqlite3
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

import managed_update as mu

LOCK = "c" * 64


class KhoaThu:
    """Một cặp khoá thử + file khoá tin cậy tương ứng."""

    def __init__(self):
        self.rieng = Ed25519PrivateKey.generate()
        self.raw = self.rieng.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.key_id = mu.tao_key_id(self.raw)

    def ghi_tin_cay(self, path: str) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"khoa": [{"key_id": self.key_id,
                                 "ed25519_pub_b64": base64.b64encode(self.raw).decode()}]}, f)
        return path

    def ky(self, raw: bytes) -> bytes:
        return json.dumps({"thuat_toan": "ed25519", "key_id": self.key_id,
                           "chu_ky_b64": base64.b64encode(self.rieng.sign(raw)).decode()}).encode()


def cay_mac_dinh(phien_ban: str) -> dict:
    return {
        "MANAGED_RELEASE.json": json.dumps({"phien_ban": phien_ban}).encode(),
        "TimClipPro/app.py": f"# app {phien_ban}\n".encode(),
        "TimClipPro/health_check.py": b"# health\n",
        "TimClipPro/requirements-lock.txt": b"# lock\n",
    }


def dong_goi(cay: dict, *, them_muc=None, ds_file=None) -> tuple:
    """``(zip_bytes, ds_file_bytes)``. ``them_muc``: [(ZipInfo|tên, bytes)] chèn THÊM (ca độc hại)."""
    ds = ds_file if ds_file is not None else json.dumps({"files": [
        {"path": p, "size": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        for p, b in sorted(cay.items())]}, sort_keys=True).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p, b in sorted(cay.items()):
            z.writestr(p, b)
        z.writestr(mu.TEN_DS_FILE, ds)
        for muc, b in them_muc or []:
            z.writestr(muc, b)
    return buf.getvalue(), ds


def manifest_dict(phien_ban: str, zip_bytes: bytes, ds_bytes: bytes, sua=None) -> dict:
    d = {
        "dinh_dang": 1, "ung_dung": "TimClipPro", "kenh": "stable", "phien_ban": phien_ban,
        "commit": "a" * 40, "tree": "b" * 40, "tao_luc": "2026-10-07 22:00:00",
        "goi": {"ten": f"TimClipPro-{phien_ban}-win_amd64.zip", "kich_thuoc": len(zip_bytes),
                "sha256": hashlib.sha256(zip_bytes).hexdigest(),
                "ds_file_sha256": hashlib.sha256(ds_bytes).hexdigest()},
        "nen_tang": "win_amd64", "python": "3.12",
        "runtime": {"runtime_id": "py312-thu", "lock_sha256": LOCK},
        "du_lieu": {"lich_su": 3, "tuong_thich_nguoc": True},
        "migration": {"tu_dong_an_toan": True},
        "launcher_toi_thieu": 1, "kho_dinh_dang": 1,
    }
    for k, v in (sua or {}).items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k] = {**d[k], **v}
        else:
            d[k] = v
    return d


def phat_hanh(nguon_dir: str, phien_ban: str, khoa: KhoaThu, *, tag=None, draft=False,
              prerelease=False, cay=None, them_muc=None, ds_file=None, sua_manifest=None,
              ky_bang=None, sua_sau_ky=None, sua_zip_sau=None) -> str:
    """Ghi một bản phát hành vào nguồn thư mục; trả thư mục của tag."""
    tag = tag or f"stable-{phien_ban}"
    zb, ds = dong_goi(cay if cay is not None else cay_mac_dinh(phien_ban), them_muc=them_muc,
                      ds_file=ds_file)
    md = manifest_dict(phien_ban, zb, ds, sua_manifest)
    raw_m = json.dumps(md, sort_keys=True, ensure_ascii=False).encode("utf-8")
    sig = (ky_bang or khoa).ky(raw_m)
    if sua_sau_ky is not None:
        raw_m = sua_sau_ky(raw_m)
    if sua_zip_sau is not None:
        zb = sua_zip_sau(zb)
    goc = os.path.join(nguon_dir, tag)
    os.makedirs(goc, exist_ok=True)
    with open(os.path.join(goc, "release.json"), "w", encoding="utf-8") as f:
        json.dump({"draft": draft, "prerelease": prerelease}, f)
    with open(os.path.join(goc, mu.TEN_MANIFEST), "wb") as f:
        f.write(raw_m)
    with open(os.path.join(goc, mu.TEN_CHU_KY), "wb") as f:
        f.write(sig)
    with open(os.path.join(goc, md["goi"]["ten"]), "wb") as f:
        f.write(zb)
    return goc


class MoiTruongGia:
    """Phụ thuộc giả của ``CapNhat``: runtime, health, migration, backup, phiên bản DB (SQLite thật)."""

    def __init__(self, state_root: str):
        self.db = os.path.join(state_root, "data", "lichsu.db")
        os.makedirs(os.path.dirname(self.db), exist_ok=True)
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE IF NOT EXISTS viec(id INTEGER PRIMARY KEY, trang_thai TEXT)")
        con.execute("PRAGMA user_version=3")
        con.commit()
        con.close()
        self.suc_khoe = {"staging": True, "kich_hoat": True}
        self.goi = []

    def tao_moi_truong(self, m, rel, rt):
        self.goi.append(("tao_moi_truong", m.phien_ban))
        os.makedirs(os.path.join(rt, "Scripts"))
        with open(os.path.join(rt, "Scripts", "python.exe"), "w", encoding="utf-8") as f:
            f.write(m.runtime_id)                  # chỗ giữ: launcher chỉ kiểm tồn tại

    def kiem_suc_khoe(self, m, rel, rt, che_do):
        self.goi.append(("kiem_suc_khoe", m.phien_ban, che_do))
        assert os.path.isfile(os.path.join(rel, "TimClipPro", "app.py"))
        return (True, "ok") if self.suc_khoe[che_do] else (False, f"{che_do} lỗi giả")

    def di_chuyen(self, m, rel, rt):
        self.goi.append(("di_chuyen", m.phien_ban))
        con = sqlite3.connect(self.db)
        con.execute(f"PRAGMA user_version={int(m.lich_su)}")
        con.commit()
        con.close()

    def sao_luu(self, m):
        self.goi.append(("sao_luu", m.phien_ban))
        dich = self.db + f".bk_{m.phien_ban}"
        src, dst = sqlite3.connect(self.db), sqlite3.connect(dich)
        src.backup(dst)
        src.close()
        dst.close()
        return dich

    def phien_ban_db(self):
        con = sqlite3.connect(self.db)
        try:
            return con.execute("PRAGMA user_version").fetchone()[0]
        finally:
            con.close()

    def them_viec(self, trang_thai: str) -> int:
        con = sqlite3.connect(self.db)
        cur = con.execute("INSERT INTO viec(trang_thai) VALUES(?)", (trang_thai,))
        con.commit()
        con.close()
        return cur.lastrowid

    def ds_viec(self) -> list:
        con = sqlite3.connect(self.db)
        try:
            return con.execute("SELECT id, trang_thai FROM viec ORDER BY id").fetchall()
        finally:
            con.close()
