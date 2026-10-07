# -*- coding: utf-8 -*-
"""Launcher ổn định của một cài đặt managed (PC2) — docs/MANAGED_UPDATE.md.

Nằm NGOÀI mọi release: ``<installation_root>/launcher/`` (bootstrap chép vào cùng ``managed_update.py``,
``maintenance_gate.py``, ``khoa.py``, ``launcher.json``, ``trusted_keys.json``). Không bao giờ gọi
``cap_nhat.py`` hay ``git``; không chạy pip vào môi trường đang dùng.

    launcher.py app                    — khôi phục cập nhật dở (nếu có) rồi mở giao diện bằng bản ĐANG KÍCH HOẠT
    launcher.py watch [đối số cli]     — như trên, chạy ``cli.py watch --log …`` (cho lịch Windows)
    launcher.py cli <đối số cli>       — chạy ``cli.py`` bất kỳ (dich, gui, youtube…)
    launcher.py update status|check|prepare|apply|recover
    launcher.py update bo-cach-ly X.Y.Z  — bỏ cách ly một phiên bản sau khi đã khắc phục nguyên nhân
    launcher.py doctor                 — chẩn đoán cài đặt này (không mạng; không đổi dữ liệu/cấu hình/bản cài)

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
# Biến của máy/người dùng KHÔNG được chảy vào tiến trình của release: đường dẫn legacy, nơi tìm module, và
# biến đổi hành vi trình thông dịch (PYTHONINSPECT treo ở dấu nhắc sau khi thoát, PYTHONOPTIMIZE bỏ assert,
# PYTHONWARNINGS=error làm sập, PYTHONSAFEPATH làm cli.py không thấy module cùng thư mục…).
_BIEN_BO = ("TIMCLIP_DATA_DIR", "TIMCLIP_OUTPUT_DIR", "SHEET_LINK", "PYTHONPATH", "PYTHONHOME",
            "VIRTUAL_ENV", "PYTHONINSPECT", "PYTHONWARNINGS", "PYTHONOPTIMIZE", "PYTHONSTARTUP",
            "PYTHONBREAKPOINT", "PYTHONDEVMODE", "PYTHONUSERBASE", "PYTHONEXECUTABLE", "PYTHONSAFEPATH",
            "PYTHONCASEOK", "PYTHONVERBOSE", "PYTHONDEBUG", "PYTHONPLATLIBDIR")
# health_check.py (trong release) in kết quả trên MỘT dòng mở đầu bằng dấu này — dòng khác (thư viện in khi
# thoát…) không làm hỏng việc đọc kết quả. Giữ đúng giá trị ở health_check.DAU_KET_QUA.
DAU_KET_QUA_HEALTH = "TIMCLIP_HEALTH_KET_QUA"


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
    # ``-P``: ``-m`` không chèn thư mục hiện tại (state root) vào sys.path — file lạ ở đó không che được
    # module thật; Streamlit tự thêm thư mục của app.py.
    return [python_runtime(con_tro), "-P", "-m", "streamlit", "run", os.path.join(ma_nguon(con_tro), "app.py"),
            "--browser.gatherUsageStats=false", f"--server.port={CONG_STREAMLIT}",
            "--server.address=127.0.0.1"]


def lenh_cli(con_tro: dict, doi_so: list) -> list:
    return [python_runtime(con_tro), os.path.join(ma_nguon(con_tro), "cli.py"), *doi_so]


# ---------------------------------------------------------------------------
#  Phụ thuộc production của CapNhat (tiến trình con, chặn mạng trong health/migration)
# ---------------------------------------------------------------------------

def _chay_health(cd: mu.CaiDat, rel: str, rt: str, doi_so: list, han_s: float) -> tuple:
    """Chạy ``health_check.py`` của release trong tiến trình riêng. Quá hạn / không chạy được = KHÔNG ĐẠT
    (không bao giờ ném ra ngoài bộ cập nhật). cwd ở state root (cây release đã ký là bất biến)."""
    con_tro = {"release": rel, "runtime": rt}
    env = moi_truong_con(cd, con_tro)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cwd = os.path.join(cd.state_root, "cache", "health")
    try:
        os.makedirs(cwd, exist_ok=True)
        p = subprocess.run([python_runtime(con_tro), os.path.join(ma_nguon(con_tro), "health_check.py"),
                            *doi_so, "--data-dir", cd.data_dir], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=han_s, env=env, cwd=cwd)
    except subprocess.TimeoutExpired:
        return False, {"loi": [f"health_check quá {han_s:.0f} s (TimeoutExpired)"]}
    except (OSError, subprocess.SubprocessError) as e:
        return False, {"loi": [f"không chạy được health_check ({type(e).__name__})"]}
    kq = {}
    for dong in reversed((p.stdout or "").splitlines()):
        if dong.startswith(DAU_KET_QUA_HEALTH + " "):
            try:
                kq = json.loads(dong[len(DAU_KET_QUA_HEALTH) + 1:])
            except ValueError:
                kq = {}
            break
    if not isinstance(kq, dict):
        kq = {}
    ok = p.returncode == 0 and kq.get("ok") is True
    return ok, kq if kq else {"loi": [f"health_check thoát mã {p.returncode}, không có dòng kết quả"]}


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
    ``--no-deps --only-binary=:all:`` theo lock ĐÃ KÝ (băm lock nằm trong manifest). Lock thiếu băm → từ chối
    gói (cách ly — tải lại cũng y hệt). Gói KHÔNG có wheel trên PyPI (vd. docopt 0.6.2 chỉ có sdist) đi kèm
    release ở ``TimClipPro/wheels/`` (file đã ký, băm có trong lock) → ``--find-links``."""
    def tao(m, rel, rt):
        lock = os.path.join(rel, "TimClipPro", "requirements-lock.txt")
        if mu._sha256_file(lock) != m.lock_sha256:
            raise mu.TuChoiGoi("lock", "requirements-lock.txt không khớp manifest đã ký.")
        with open(lock, encoding="utf-8") as f:
            noi_dung = f.read()
        if "--hash=sha256:" not in noi_dung:
            raise mu.TuChoiGoi("lock_chua_bam", "Lock chưa có băm gói — không cài runtime chưa xác minh.")
        if not (os.path.isabs(python_goc) and os.path.isfile(python_goc)):
            raise mu.LoiCapNhat("python_goc", "Không thấy Python gốc đã ghi lúc bootstrap.")
        subprocess.run([python_goc, "-P", "-m", "venv", rt], check=True, timeout=600)
        py = python_runtime({"runtime": rt})
        pip = [py, "-P", "-m", "pip", "install", "--no-input", "--disable-pip-version-check",
               "--require-hashes", "--no-deps", "--only-binary=:all:"]
        wheels = os.path.join(rel, "TimClipPro", "wheels")
        if os.path.isdir(wheels):
            pip += ["--find-links", wheels]
        subprocess.run([*pip, "-r", lock], check=True, timeout=han_s)
        subprocess.run([py, "-P", "-m", "pip", "check"], check=True, timeout=300)
    return tao


def sao_luu_sqlite(cd: mu.CaiDat):
    """Bản sao NHẤT QUÁN bằng backup API của SQLite (không chép thô file đang mở) + cấu hình nhỏ.
    Không sao lưu kho vân tay (bản phát hành không chạm kho)."""
    def sao_luu(m):
        dich = os.path.join(cd.backups, f"{datetime.now():%Y%m%d_%H%M%S}_truoc_{m.phien_ban}")
        os.makedirs(dich)
        db = os.path.join(cd.data_dir, "lichsu.db")
        if os.path.isfile(db):
            try:
                src = sqlite3.connect(db, timeout=30)
                try:
                    dst = sqlite3.connect(os.path.join(dich, "lichsu.db"))
                    try:
                        src.backup(dst)
                        ok = dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                    finally:
                        dst.close()
                finally:
                    src.close()
            except sqlite3.Error as e:
                raise mu.LoiCapNhat("sao_luu", f"Không sao lưu được lịch sử ({type(e).__name__}) — chưa đổi "
                                    "gì, giữ bản hiện tại.") from e
            if not ok:
                raise mu.LoiCapNhat("sao_luu", "Bản sao lưu lịch sử không toàn vẹn.")
        for ten in ("khos.json", "cau_hinh.json"):
            p = os.path.join(cd.data_dir, ten)
            if os.path.isfile(p):
                with open(p, "rb") as fi, open(os.path.join(dich, ten), "wb") as fo:
                    fo.write(fi.read())
        return dich
    return sao_luu


def phien_ban_db(cd: mu.CaiDat):
    """Phiên bản lược đồ ``lichsu.db``; ``None`` = máy mới chưa có lịch sử (tạo mới, KHÔNG phải migration).
    Đọc lỗi → ``LoiCapNhat`` (không đoán)."""
    def doc() -> Optional[int]:
        db = os.path.join(cd.data_dir, "lichsu.db")
        if not os.path.isfile(db):
            return None
        from urllib.parse import quote

        try:
            con = sqlite3.connect("file:" + quote(os.path.abspath(db).replace("\\", "/")) + "?mode=ro",
                                  uri=True, timeout=30)
            try:
                return int(con.execute("PRAGMA user_version").fetchone()[0])
            finally:
                con.close()
        except sqlite3.Error as e:
            raise mu.LoiCapNhat("lich_su", f"Không đọc được phiên bản lịch sử ({type(e).__name__}) — chưa "
                                "đổi gì.") from e
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
    except Exception as e:  # noqa: BLE001 — khôi phục lỗi lạ không được chặn mở bản đang kích hoạt
        print(f"[CẢNH BÁO] Khôi phục cập nhật lỗi không lường trước ({type(e).__name__}) — mở bản đang kích "
              "hoạt; chạy «launcher.py doctor».", file=sys.stderr)
    return _kiem_con_tro(cn.hien_tai())


def _kiem_con_tro(con_tro) -> dict:
    if not con_tro:
        raise LoiLauncher("Chưa có bản nào được kích hoạt — chạy bootstrap trước.")
    if not os.path.isfile(os.path.join(con_tro.get("release", ""), mu.TEN_DAU_RELEASE)):
        raise LoiLauncher("Bản đang kích hoạt thiếu dấu release managed — cần kiểm tay.")
    if not os.path.isfile(python_runtime(con_tro)):
        raise LoiLauncher("Runtime của bản đang kích hoạt không còn — cần kiểm tay.")
    return con_tro


def con_tro_khong_khoi_phuc(cd: mu.CaiDat) -> dict:
    """Bộ cập nhật KHÔNG dựng được (khoá tin cậy hỏng, thiếu thư viện, chưa cấu hình nguồn): dùng con trỏ
    ``current`` NGUYÊN TRẠNG — chỉ khi nhật ký không dừng giữa một lần kích hoạt (khi đó không khôi phục được
    thì không đoán bản nào chạy được)."""
    nk = mu.doc_json(cd.file_trang_thai("journal.json")) or {}
    if nk.get("trang_thai") in (mu.ACTIVATING, mu.HEALTHCHECK, mu.ROLLBACK):
        raise LoiLauncher("Lần cập nhật trước dừng giữa lúc kích hoạt mà bộ cập nhật không dựng được — chạy "
                          "«launcher.py doctor» và báo chủ dự án.")
    return _kiem_con_tro(mu.doc_json(cd.file_trang_thai("current.json")))


DAT, CANH_BAO, LOI = "✅", "⚠️", "❌"


def doctor(goc: str) -> list:
    """Chẩn đoán: ``[(mức, mục, ghi chú)]``. Không gọi mạng, không đổi dữ liệu/cấu hình/bản cài, không khôi
    phục gì. Ngoại lệ duy nhất: kiểm cổng bảo trì dọn dấu của việc/updater ĐÃ CHẾT (lease, cờ rút mồ côi) —
    như mọi lần kiểm cổng khác."""
    kq = []

    def them(muc, ten, ghi_chu=""):
        kq.append((muc, ten, ghi_chu))

    try:
        cfg = doc_cau_hinh(goc)
        them(DAT, "launcher.json")
    except LoiLauncher as e:
        them(LOI, "launcher.json", str(e))
        return kq
    cd = cai_dat(goc, cfg)
    if os.path.exists(os.path.join(goc, ".git")):
        them(LOI, "Thư mục cài đặt", "là bản clone git — cài đặt managed phải là thư mục riêng")
    try:
        khoa = mu.doc_khoa_tin_cay(os.path.join(goc, "launcher", TEN_KHOA_TIN_CAY))
        them(DAT, "Khoá tin cậy", f"{len(khoa)} khoá")
    except mu.LoiCapNhat as e:
        khoa = None
        them(LOI, "Khoá tin cậy", str(e))
    import runtime_paths

    ly_do = runtime_paths.kiem_duong_dan_trang_thai(cd.state_root)
    them(LOI if ly_do else DAT, "State root", " ".join(ly_do) or cd.state_root)
    try:
        dd = runtime_paths.doc_dinh_danh(cd.state_root)
        dung_goc = os.path.normcase(os.path.abspath(dd.get("installation_root", ""))) == os.path.normcase(goc)
        them(DAT if dung_goc else LOI, "Định danh cài đặt",
             dd["installation_id"][:8] + ("" if dung_goc else " — trỏ installation root KHÁC"))
    except runtime_paths.LoiRuntime as e:
        them(LOI, "Định danh cài đặt", str(e))
    py_goc = str(cfg.get("python_goc") or "")
    them(DAT if os.path.isfile(py_goc) else CANH_BAO, "Python gốc (tạo runtime khi cập nhật)",
         py_goc or "chưa cấu hình")
    try:
        cur = mu.doc_json(cd.file_trang_thai("current.json"))
    except mu.LoiCapNhat as e:
        cur = None
        them(LOI, "Con trỏ bản đang kích hoạt", str(e))
    if not cur:
        them(LOI, "Bản đang kích hoạt", "chưa có — chạy bootstrap / update")
    else:
        rel = cur.get("release", "")
        try:
            if khoa is None:
                raise mu.LoiCapNhat("khoa", "không kiểm được chữ ký (khoá tin cậy hỏng)")
            with open(os.path.join(rel, mu.TEN_MANIFEST), "rb") as f:
                raw_m = f.read()
            with open(os.path.join(rel, mu.TEN_CHU_KY), "rb") as f:
                mu.kiem_chu_ky(raw_m, f.read(), khoa)
            m = mu.doc_manifest(raw_m)
            if cur.get("manifest_sha256") != m.sha256:
                raise mu.LoiCapNhat("con_tro", "con trỏ không khớp manifest đã ký của release")
            mu.kiem_cay_release(rel, m)
            them(DAT, "Bản đang kích hoạt", f"{m.phien_ban} — chữ ký + cây file đúng")
        except (OSError, mu.LoiCapNhat) as e:
            them(LOI, "Bản đang kích hoạt", f"{cur.get('phien_ban', '?')} — {e}")
        them(DAT if os.path.isfile(python_runtime(cur)) else LOI, "Runtime", python_runtime(cur))
    try:
        nk = mu.doc_json(cd.file_trang_thai("journal.json")) or {}
        tt, loi = nk.get("trang_thai", ""), str(nk.get("loi") or "")
        # Trạng thái trung gian = lượt cập nhật bị cắt ngang (mất điện/bị giết): launcher sẽ khôi phục ở lần
        # chạy kế; doctor không khôi phục nên chỉ báo. Có lỗi ở lượt gần nhất → cũng cần người xem.
        dang_do = tt in (mu.DOWNLOADING, mu.VERIFIED, mu.QUIESCED, mu.BACKED_UP, mu.MIGRATING,
                         mu.ACTIVATING, mu.HEALTHCHECK, mu.ROLLBACK)
        them(CANH_BAO if (tt in (mu.BLOCKED, mu.WAITING_APPROVAL, mu.QUARANTINED) or dang_do or loi)
             else DAT, "Nhật ký cập nhật",
             " ".join(x for x in (tt or "trống", "— dở dang, lần chạy launcher kế sẽ tự khôi phục"
                                  if dang_do else "", loi) if x))
    except mu.LoiCapNhat as e:
        them(LOI, "Nhật ký cập nhật", str(e))
    try:
        cong = mg.CongBaoTri(cd.data_dir)
        rut, dang = cong.trang_thai_rut(), cong.viec_dang_chay()
        them(CANH_BAO if rut else DAT, "Cổng bảo trì",
             (f"đang rút ({rut.get('chu', '')}); " if rut else "mở; ") + f"{len(dang)} việc đang chạy")
    except Exception as e:  # noqa: BLE001 — chẩn đoán không được dừng giữa chừng
        them(CANH_BAO, "Cổng bảo trì", type(e).__name__)
    import shutil

    ff = os.path.join(goc, "tools", "ffmpeg", "bin", "ffmpeg.exe")
    them(DAT if (os.path.isfile(ff) or shutil.which("ffmpeg")) else CANH_BAO, "FFmpeg",
         ff if os.path.isfile(ff) else (shutil.which("ffmpeg") or "không thấy — quét sẽ lỗi"))
    with __import__("contextlib").suppress(OSError):
        trong = shutil.disk_usage(cd.state_root).free / 1024 ** 3
        them(DAT if trong >= 5 else CANH_BAO, "Dung lượng trống (ổ state)", f"{trong:.1f} GB")
    db = os.path.join(cd.data_dir, "lichsu.db")
    if os.path.isfile(db):
        from urllib.parse import quote

        try:
            con = sqlite3.connect("file:" + quote(os.path.abspath(db).replace("\\", "/")) + "?mode=ro",
                                  uri=True, timeout=10)
            try:
                bang = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                tt = dict(con.execute("SELECT trang_thai, COUNT(*) FROM hang_doi_gui GROUP BY trang_thai")
                          .fetchall()) if "hang_doi_gui" in bang else {}
            finally:
                con.close()
            can = tt.get("UNKNOWN_DELIVERY", 0) + tt.get("BLOCKED_CONFIG", 0)   # cần người xử lý
            them(CANH_BAO if can else DAT, "Hàng đợi gửi Sheets",
                 ", ".join(f"{k}: {v}" for k, v in sorted(tt.items())) or "trống")
        except sqlite3.Error as e:
            them(CANH_BAO, "Lịch sử", f"không đọc được ({type(e).__name__})")
    return kq


def _in(kq: mu.KetQua) -> int:
    print(f"[{kq.trang_thai}] {kq.thong_diep}")
    for x in kq.chi_tiet:
        print(f"  - {x}")
    if kq.trang_thai in (mu.LOI, mu.TU_CHOI, mu.BLOCKED, mu.QUARANTINED):
        return 1
    if kq.trang_thai in (mu.BAN,) or (kq.trang_thai == mu.STAGED and "hoãn" in kq.thong_diep):
        return 2
    return 0


def _utf8_dau_ra() -> None:
    """stdout/stderr bị chuyển hướng (log Task Scheduler, ống dẫn) mặc định là mã ANSI (cp1252/cp1258) —
    in tiếng Việt / ✅ sẽ sập. Chuyển sang UTF-8, lỗi thì thay ký tự (không bao giờ sập vì in)."""
    for luong in (sys.stdout, sys.stderr):
        try:
            if (luong.encoding or "").lower().replace("-", "") != "utf8":
                luong.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _chay_cho_con(argv: list, **kw) -> int:
    """Chạy tiến trình con và CHỜ tới khi nó tự thoát. Ctrl+C ở cửa sổ console tới CẢ tiến trình con (app
    tự tắt êm: người gửi Sheets chờ việc đang bay ≤ 90 s); launcher không bao giờ ``kill`` nó —
    ``subprocess.call`` giết con sau 0,25 s, biến việc đang gửi thành KHÔNG RÕ."""
    p = subprocess.Popen(argv, **kw)
    while True:
        try:
            return p.wait()
        except KeyboardInterrupt:
            continue


def main(argv=None, *, goc: Optional[str] = None, chay=_chay_cho_con, **thay) -> int:
    _utf8_dau_ra()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 1
    goc = goc or goc_cai_dat()
    if argv[0] == "doctor":
        ket = doctor(goc)
        for muc, ten, ghi_chu in ket:
            print(f"{muc} {ten}" + (f": {ghi_chu}" if ghi_chu else ""))
        return 1 if any(muc == LOI for muc, _, _ in ket) else 0
    try:
        cfg = doc_cau_hinh(goc)
        lenh = argv[0]
        if lenh not in ("app", "watch", "cli", "update"):
            raise LoiLauncher(f"Lệnh «{lenh}» không có (app | watch | cli | update | doctor).")
        try:
            cn = tao_cap_nhat(goc, cfg, **thay)
        except Exception as e:  # noqa: BLE001 — chỉ chặn CẬP NHẬT, không chặn mở bản đang kích hoạt
            if lenh == "update":
                if isinstance(e, (LoiLauncher, mu.LoiCapNhat)):
                    raise
                raise LoiLauncher(f"Bộ cập nhật không dựng được ({type(e).__name__}: {e}).") from e
            print(f"[CẢNH BÁO] Bộ cập nhật không dựng được ({type(e).__name__}: {e}) — mở bản đang kích hoạt, "
                  "KHÔNG khôi phục/cập nhật; chạy «launcher.py doctor».", file=sys.stderr)
            cn = None
        if lenh == "update":
            con = argv[1] if len(argv) > 1 else "status"
            if con == "status":
                print(json.dumps(cn.trang_thai(), ensure_ascii=False, indent=1, default=str))
                return 0
            if con == "recover":
                print(f"[{cn.phuc_hoi()}] đã khôi phục theo nhật ký.")
                return 0
            if con == "bo-cach-ly":
                if len(argv) < 3:
                    raise LoiLauncher("Cần phiên bản: update bo-cach-ly X.Y.Z")
                if cn.bo_cach_ly(argv[2]):
                    print(f"Đã bỏ cách ly {argv[2]} — lần «update prepare» sau sẽ xét lại (vẫn đủ chữ ký, "
                          "băm, health).")
                    return 0
                print(f"Phiên bản {argv[2]} không bị cách ly.", file=sys.stderr)
                return 1
            ham = {"check": cn.kiem_tra, "prepare": cn.chuan_bi, "apply": cn.ap_dung}.get(con)
            if ham is None:
                raise LoiLauncher(f"Lệnh update «{con}» không có "
                                  "(status|check|prepare|apply|recover|bo-cach-ly).")
            return _in(ham())
        cd = cn.cd if cn is not None else cai_dat(goc, cfg)
        con_tro = ban_dang_kich_hoat(cn) if cn is not None else con_tro_khong_khoi_phuc(cd)
        env = moi_truong_con(cd, con_tro)
        os.makedirs(cd.state_root, exist_ok=True)
        if lenh == "app":
            return chay(lenh_app(con_tro), env=env, cwd=cd.state_root)
        if lenh == "watch":
            return chay(lenh_cli(con_tro, ["watch", "--log", *argv[1:]]), env=env, cwd=cd.state_root)
        return chay(lenh_cli(con_tro, argv[1:]), env=env, cwd=cd.state_root)
    except (LoiLauncher, mu.LoiCapNhat) as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
