# -*- coding: utf-8 -*-
"""Launcher ổn định của một cài đặt managed (PC2) — docs/MANAGED_UPDATE.md.

Nằm NGOÀI mọi release: ``<installation_root>/launcher/`` (bootstrap chép vào cùng ``managed_update.py``,
``maintenance_gate.py``, ``khoa.py``, ``launcher.json``, ``trusted_keys.json``). Không bao giờ gọi
``cap_nhat.py`` hay ``git``; không chạy pip vào môi trường đang dùng.

    launcher.py app                    — khôi phục cập nhật dở (nếu có) rồi mở giao diện bằng bản ĐANG KÍCH HOẠT
    launcher.py watch [đối số cli]     — như trên, chạy ``cli.py watch --log …`` (cho lịch Windows)
    launcher.py cli <đối số cli>       — chạy ``cli.py`` bất kỳ (dich, gui, youtube…)
    launcher.py update status|check|prepare|apply|recover

Mã thoát: của tiến trình con (app/watch/cli); ``update``: 0 xong/không có gì, 1 lỗi, 2 bận/hoãn.
Không mạng khi mở app/Watch: kiểm bản mới chỉ qua ``update check|prepare`` (lịch riêng, opt-in).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from typing import Optional

import maintenance_gate as mg
import managed_update as mu

TEN_CAU_HINH = "launcher.json"
TEN_KHOA_TIN_CAY = "trusted_keys.json"
CONG_STREAMLIT = 8501
_BIEN_BO = ("TIMCLIP_DATA_DIR", "TIMCLIP_OUTPUT_DIR", "SHEET_LINK", "PYTHONPATH", "PYTHONHOME",
            "VIRTUAL_ENV")


class LoiLauncher(RuntimeError):
    """Cài đặt/cấu hình launcher sai — thông báo tiếng Việt, không traceback."""


def goc_cai_dat(thu_muc_launcher: Optional[str] = None) -> str:
    return os.path.dirname(os.path.abspath(thu_muc_launcher or os.path.dirname(os.path.abspath(__file__))))


def doc_cau_hinh(goc: str) -> dict:
    path = os.path.join(goc, "launcher", TEN_CAU_HINH)
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise LoiLauncher("Chưa có launcher.json — cài đặt này chưa được bootstrap.") from None
    except (OSError, ValueError):
        raise LoiLauncher("launcher.json hỏng — cần kiểm tay (không tự đặt lại).") from None
    state = cfg.get("state_root") if isinstance(cfg, dict) else None
    if not isinstance(state, str) or not os.path.isabs(state):
        raise LoiLauncher("launcher.json thiếu state_root tuyệt đối.")
    return cfg


def cai_dat(goc: str, cfg: dict) -> mu.CaiDat:
    return mu.CaiDat(goc=goc, state_root=os.path.abspath(cfg["state_root"]))


def moi_truong_con(cd: mu.CaiDat, con_tro: dict, *, environ=None) -> dict:
    """Biến môi trường cho tiến trình con: managed + state root + PATH ffmpeg; bỏ biến legacy; bytecode
    ghi ra state root (release BẤT BIẾN — không có __pycache__ trong cây đã ký)."""
    env = {k: v for k, v in (os.environ if environ is None else environ).items() if k not in _BIEN_BO}
    env.update({
        "TIMCLIP_RUNTIME_MODE": "managed",
        "TIMCLIP_STATE_ROOT": cd.state_root,
        "TIMCLIP_INSTALLATION_ROOT": cd.goc,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPYCACHEPREFIX": os.path.join(cd.state_root, "cache", "pycache"),
        "TIMCLIP_RELEASE": con_tro.get("phien_ban", ""),
    })
    ff = os.path.join(cd.goc, "tools", "ffmpeg", "bin")
    if os.path.isdir(ff):
        env["PATH"] = ff + os.pathsep + env.get("PATH", "")
    return env


def python_runtime(con_tro: dict) -> str:
    return os.path.join(con_tro["runtime"], "Scripts", "python.exe") if os.name == "nt" else \
        os.path.join(con_tro["runtime"], "bin", "python")


def ma_nguon(con_tro: dict) -> str:
    return os.path.join(con_tro["release"], "TimClipPro")


def lenh_app(con_tro: dict) -> list:
    return [python_runtime(con_tro), "-m", "streamlit", "run", os.path.join(ma_nguon(con_tro), "app.py"),
            "--browser.gatherUsageStats=false", f"--server.port={CONG_STREAMLIT}",
            "--server.address=127.0.0.1"]


def lenh_cli(con_tro: dict, doi_so: list) -> list:
    return [python_runtime(con_tro), os.path.join(ma_nguon(con_tro), "cli.py"), *doi_so]


# ---------------------------------------------------------------------------
#  Phụ thuộc production của CapNhat (tiến trình con, chặn mạng trong health/migration)
# ---------------------------------------------------------------------------

def _chay_health(cd: mu.CaiDat, rel: str, rt: str, doi_so: list, han_s: float) -> tuple:
    con_tro = {"release": rel, "runtime": rt}
    env = moi_truong_con(cd, con_tro)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run([python_runtime(con_tro), os.path.join(ma_nguon(con_tro), "health_check.py"),
                        *doi_so, "--data-dir", cd.data_dir], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=han_s, env=env,
                       cwd=ma_nguon(con_tro))
    dong = [x for x in p.stdout.splitlines() if x.strip()]
    try:
        kq = json.loads(dong[-1]) if dong else {}
    except ValueError:
        kq = {}
    ok = p.returncode == 0 and bool(kq.get("ok"))
    return ok, kq if kq else {"loi": [f"health_check thoát mã {p.returncode}"]}


def kiem_suc_khoe_tien_trinh(cd: mu.CaiDat, *, han_s: float = 600.0):
    def kiem(m, rel, rt, che_do):
        ok, kq = _chay_health(cd, rel, rt, ["kiem", "--che-do", che_do], han_s)
        return ok, "; ".join(kq.get("loi") or []) or "ok"
    return kiem


def di_chuyen_tien_trinh(cd: mu.CaiDat, *, han_s: float = 1800.0):
    def di_chuyen(m, rel, rt):
        ok, kq = _chay_health(cd, rel, rt, ["migrate"], han_s)
        if not ok:
            raise mu.LoiCapNhat("migration", "Migration lỗi: " + "; ".join(kq.get("loi") or []))
    return di_chuyen


def tao_moi_truong_pip(python_goc: str, *, han_s: float = 3600.0):
    """Runtime TẠI ĐƯỜNG DẪN CUỐI: venv từ Python gốc đã ghi lúc bootstrap, pip ``--require-hashes``
    ``--no-deps`` theo lock ĐÃ KÝ (băm lock nằm trong manifest). Lock thiếu băm → từ chối."""
    def tao(m, rel, rt):
        lock = os.path.join(rel, "TimClipPro", "requirements-lock.txt")
        if mu._sha256_file(lock) != m.lock_sha256:
            raise mu.TuChoiGoi("lock", "requirements-lock.txt không khớp manifest đã ký.")
        with open(lock, encoding="utf-8") as f:
            noi_dung = f.read()
        if "--hash=sha256:" not in noi_dung:
            raise mu.LoiCapNhat("lock", "Lock chưa có băm gói — không cài runtime chưa xác minh.")
        if not (os.path.isabs(python_goc) and os.path.isfile(python_goc)):
            raise mu.LoiCapNhat("python_goc", "Không thấy Python gốc đã ghi lúc bootstrap.")
        subprocess.run([python_goc, "-m", "venv", rt], check=True, timeout=600)
        py = python_runtime({"runtime": rt})
        subprocess.run([py, "-m", "pip", "install", "--no-input", "--disable-pip-version-check",
                        "--require-hashes", "--no-deps", "--only-binary=:all:", "-r", lock],
                       check=True, timeout=han_s)
        subprocess.run([py, "-m", "pip", "check"], check=True, timeout=300)
    return tao


def sao_luu_sqlite(cd: mu.CaiDat):
    """Bản sao NHẤT QUÁN bằng backup API của SQLite (không chép thô file đang mở) + cấu hình nhỏ.
    Không sao lưu kho vân tay (bản phát hành không chạm kho)."""
    def sao_luu(m):
        dich = os.path.join(cd.backups, f"{datetime.now():%Y%m%d_%H%M%S}_truoc_{m.phien_ban}")
        os.makedirs(dich)
        db = os.path.join(cd.data_dir, "lichsu.db")
        if os.path.isfile(db):
            src = sqlite3.connect(db, timeout=30)
            dst = sqlite3.connect(os.path.join(dich, "lichsu.db"))
            try:
                src.backup(dst)
                if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise mu.LoiCapNhat("sao_luu", "Bản sao lưu lịch sử không toàn vẹn.")
            finally:
                src.close()
                dst.close()
        for ten in ("khos.json", "cau_hinh.json"):
            p = os.path.join(cd.data_dir, ten)
            if os.path.isfile(p):
                with open(p, "rb") as fi, open(os.path.join(dich, ten), "wb") as fo:
                    fo.write(fi.read())
        return dich
    return sao_luu


def phien_ban_db(cd: mu.CaiDat):
    def doc() -> int:
        db = os.path.join(cd.data_dir, "lichsu.db")
        if not os.path.isfile(db):
            return 0
        from urllib.parse import quote

        con = sqlite3.connect("file:" + quote(os.path.abspath(db).replace("\\", "/")) + "?mode=ro",
                              uri=True, timeout=30)
        try:
            return int(con.execute("PRAGMA user_version").fetchone()[0])
        finally:
            con.close()
    return doc


def tao_nguon(cfg: dict):
    n = cfg.get("nguon") or {}
    if n.get("loai") == "github":
        return mu.NguonGitHub(str(n.get("repo") or ""))
    if n.get("loai") == "thu_muc":
        return mu.NguonThuMuc(str(n.get("duong_dan") or ""))
    raise LoiLauncher("Chưa cấu hình nguồn phát hành (launcher.json → nguon).")


def tao_cap_nhat(goc: str, cfg: dict, **thay) -> mu.CapNhat:
    cd = cai_dat(goc, cfg)
    tham = dict(
        nguon=None, khoa_tin_cay=None, cong=mg.CongBaoTri(cd.data_dir),
        tao_moi_truong=tao_moi_truong_pip(str(cfg.get("python_goc") or "")),
        kiem_suc_khoe=kiem_suc_khoe_tien_trinh(cd), di_chuyen=di_chuyen_tien_trinh(cd),
        sao_luu=sao_luu_sqlite(cd), phien_ban_db=phien_ban_db(cd),
        han_cho_ranh_s=float(cfg.get("han_cho_ranh_s", 600)))
    tham.update(thay)
    if tham["nguon"] is None:
        tham["nguon"] = tao_nguon(cfg)
    if tham["khoa_tin_cay"] is None:
        tham["khoa_tin_cay"] = mu.doc_khoa_tin_cay(os.path.join(goc, "launcher", TEN_KHOA_TIN_CAY))
    return mu.CapNhat(cd, **tham)


# ---------------------------------------------------------------------------
#  Chọn bản chạy + lệnh
# ---------------------------------------------------------------------------

def ban_dang_kich_hoat(cn: mu.CapNhat) -> dict:
    """Khôi phục cập nhật dở rồi trả con trỏ ``current``. Nhật ký hỏng không chặn chạy bản hiện tại."""
    try:
        cn.phuc_hoi()
    except mu.LoiCapNhat as e:
        print(f"[CẢNH BÁO] {e}", file=sys.stderr)
    con_tro = cn.hien_tai()
    if not con_tro:
        raise LoiLauncher("Chưa có bản nào được kích hoạt — chạy bootstrap trước.")
    if not os.path.isfile(os.path.join(con_tro.get("release", ""), mu.TEN_DAU_RELEASE)):
        raise LoiLauncher("Bản đang kích hoạt thiếu dấu release managed — cần kiểm tay.")
    if not os.path.isfile(python_runtime(con_tro)):
        raise LoiLauncher("Runtime của bản đang kích hoạt không còn — cần kiểm tay.")
    return con_tro


def _in(kq: mu.KetQua) -> int:
    print(f"[{kq.trang_thai}] {kq.thong_diep}")
    for x in kq.chi_tiet:
        print(f"  - {x}")
    if kq.trang_thai in (mu.LOI, mu.TU_CHOI, mu.BLOCKED, mu.QUARANTINED):
        return 1
    if kq.trang_thai in (mu.BAN,) or (kq.trang_thai == mu.STAGED and "hoãn" in kq.thong_diep):
        return 2
    return 0


def main(argv=None, *, goc: Optional[str] = None, chay=subprocess.call, **thay) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 1
    goc = goc or goc_cai_dat()
    try:
        cfg = doc_cau_hinh(goc)
        cn = tao_cap_nhat(goc, cfg, **thay)
        lenh = argv[0]
        if lenh == "update":
            con = argv[1] if len(argv) > 1 else "status"
            if con == "status":
                print(json.dumps(cn.trang_thai(), ensure_ascii=False, indent=1, default=str))
                return 0
            if con == "recover":
                print(f"[{cn.phuc_hoi()}] đã khôi phục theo nhật ký.")
                return 0
            ham = {"check": cn.kiem_tra, "prepare": cn.chuan_bi, "apply": cn.ap_dung}.get(con)
            if ham is None:
                raise LoiLauncher(f"Lệnh update «{con}» không có (status|check|prepare|apply|recover).")
            return _in(ham())
        con_tro = ban_dang_kich_hoat(cn)
        env = moi_truong_con(cn.cd, con_tro)
        os.makedirs(cn.cd.state_root, exist_ok=True)
        if lenh == "app":
            return chay(lenh_app(con_tro), env=env, cwd=cn.cd.state_root)
        if lenh == "watch":
            return chay(lenh_cli(con_tro, ["watch", "--log", *argv[1:]]), env=env, cwd=cn.cd.state_root)
        if lenh == "cli":
            return chay(lenh_cli(con_tro, argv[1:]), env=env, cwd=cn.cd.state_root)
        raise LoiLauncher(f"Lệnh «{lenh}» không có (app | watch | cli | update).")
    except (LoiLauncher, mu.LoiCapNhat) as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
