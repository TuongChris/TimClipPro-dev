# -*- coding: utf-8 -*-
"""Bootstrap MỘT LẦN cho máy vận hành (PC2) — docs/HUONG_DAN_PC2.md, docs/MANAGED_UPDATE.md §2.

    python bootstrap.py --goc D:\\TimClipPro --state D:\\TimClipPro_State --python-goc "C:\\...\\python.exe"
                        --tin-cay trusted_keys.json (--nguon-thu-muc E:\\phat_hanh | --repo chu/du-an)
                        [--workspace mac_dinh] [--python-launcher <python có cryptography>]

Chạy được bằng Python 3.12 GỐC (chỉ thư viện chuẩn): giai đoạn 1 kiểm đường dẫn + khoá tin cậy rồi tạo môi
trường RIÊNG của launcher (pip ``--require-hashes`` theo ``launcher-lock.txt``), giai đoạn 2 chạy lại CHÍNH file
này bằng Python của môi trường đó.

Làm: kiểm đường dẫn (không OneDrive/ổ mạng, không đè cài đặt/định danh có sẵn, không nằm trong bản clone git,
không có dữ liệu cập nhật cũ) → chép launcher + khoá tin cậy → ``TimClipPro.bat``/``GiamSat.bat``/``CapNhat.bat``
(CHỈ ASCII: ``%~dp0`` cho đường dẫn trong thư mục cài đặt) → XML lịch Windows để XEM TRƯỚC (KHÔNG đăng ký) →
``installation.json`` với UUID MỚI (PC2 không bao giờ kế thừa định danh của PC1) → ``launcher.json`` GHI CUỐI
(đánh dấu đã bootstrap) → cài bản Stable đầu tiên qua ĐÚNG bộ cập nhật (chữ ký, băm, health).

Dừng giữa chừng TRƯỚC launcher.json → chạy lại đúng lệnh đó để làm tiếp (định danh đã tạo cho CHÍNH thư mục cài
đặt này được giữ). Cài bản đầu lỗi → cài đặt vẫn dùng được, chạy ``CapNhat.bat`` sau khi khắc phục.
PC2 bắt đầu với kho RỖNG và tự dựng; không chép kho, lịch sử, outbox, cookie hay khoá từ PC1.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

import managed_update as mu
import runtime_paths

FILE_LAUNCHER = ("launcher.py", "managed_update.py", "maintenance_gate.py", "khoa.py",
                 "runtime_paths.py")
THU_MUC_LICH = "lich_xem_truoc"
# Thư mục do bộ cập nhật sở hữu — có sẵn trong thư mục cài đặt MỚI nghĩa là dữ liệu cũ của cài đặt khác.
THU_MUC_CAP_NHAT = ("releases", "environments", "update_state", "staging")


class LoiBootstrap(RuntimeError):
    """Không bootstrap được — thông báo tiếng Việt, chưa ghi gì (hoặc chỉ những gì đã liệt kê)."""


def _kiem_goc(ten: str, p: str) -> str:
    if not p or not os.path.isabs(p):
        raise LoiBootstrap(f"{ten} phải là đường dẫn tuyệt đối.")
    p = os.path.abspath(p)
    ly_do = runtime_paths.kiem_duong_dan_trang_thai(p)
    if ly_do:
        raise LoiBootstrap(f"{ten} không an toàn: " + " ".join(ly_do))
    return p


def _trong_ban_clone_git(p: str) -> bool:
    """``p`` hoặc một thư mục CHA của nó có ``.git`` (bản clone đang dùng cho phát triển/legacy)."""
    hien = os.path.abspath(p)
    while True:
        if os.path.exists(os.path.join(hien, ".git")):
            return True
        cha = os.path.dirname(hien)
        if cha == hien:
            return False
        hien = cha


def kiem_truoc(goc: str, state: str, python_goc: str) -> tuple:
    """Kiểm MỌI điều kiện trước khi ghi byte nào. Trả ``(goc, state, tiep_tuc)`` đã chuẩn hoá — ``tiep_tuc``:
    lần trước dừng SAU khi tạo định danh cho CHÍNH thư mục cài đặt này (chưa có launcher.json) → làm tiếp."""
    goc, state = _kiem_goc("Thư mục cài đặt", goc), _kiem_goc("State root", state)
    if os.path.normcase(goc) == os.path.normcase(state):
        raise LoiBootstrap("Thư mục cài đặt và state root phải khác nhau.")
    if os.path.exists(os.path.join(goc, "launcher", "launcher.json")):
        raise LoiBootstrap("Thư mục cài đặt đã được bootstrap — không làm lại đè lên.")
    if _trong_ban_clone_git(goc) or _trong_ban_clone_git(state):
        raise LoiBootstrap("Không cài vào (hoặc bên trong) thư mục bản clone git — chọn thư mục MỚI.")
    cu = [t for t in THU_MUC_CAP_NHAT
          if os.path.isdir(os.path.join(goc, t)) and os.listdir(os.path.join(goc, t))]
    if cu:
        raise LoiBootstrap("Thư mục cài đặt đã có dữ liệu cập nhật cũ (" + ", ".join(cu) + ") — chọn thư mục "
                           "MỚI.")
    tiep_tuc = False
    if os.path.exists(os.path.join(state, runtime_paths.TEN_DINH_DANH)):
        try:
            dd = runtime_paths.doc_dinh_danh(state)
        except runtime_paths.LoiRuntime:
            raise LoiBootstrap("State root có định danh hỏng — không ghi đè; chọn state root MỚI.") from None
        if os.path.normcase(os.path.abspath(str(dd.get("installation_root") or ""))) != os.path.normcase(goc):
            raise LoiBootstrap("State root đã thuộc một cài đặt khác — không ghi đè định danh.")
        tiep_tuc = True
    if not (os.path.isabs(python_goc) and os.path.isfile(python_goc)):
        raise LoiBootstrap("Không thấy Python gốc (cần đường dẫn tuyệt đối tới python.exe 3.12).")
    return goc, state, tiep_tuc


def _kiem_khoa_tin_cay_tho(tin_cay: str) -> int:
    """Kiểm CẤU TRÚC file khoá tin cậy chỉ bằng thư viện chuẩn (trước khi ghi gì): JSON, mỗi khoá là 32 byte
    Ed25519 thô, ``key_id`` khớp khoá. Dựng khoá thật (``cryptography``) ở giai đoạn 2."""
    try:
        with open(tin_cay, encoding="utf-8") as f:
            d = json.load(f)
        khoa = d.get("khoa") if isinstance(d, dict) else None
        if not khoa:
            raise ValueError
        for k in khoa:
            raw = base64.b64decode(k["ed25519_pub_b64"], validate=True)
            if len(raw) != 32 or k.get("key_id") != mu.tao_key_id(raw):
                raise ValueError
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise LoiBootstrap("File khoá tin cậy không hợp lệ — dùng đúng trusted_keys.json của bộ kit.") from None
    return len(khoa)


def _thieu_goi(nguon: dict) -> list:
    """Gói mà giai đoạn 2 cần nhưng Python ĐANG CHẠY không có (Python gốc thường thiếu cả hai)."""
    import importlib.util

    can = ["cryptography"] + (["requests"] if (nguon or {}).get("loai") == "github" else [])
    return [g for g in can if importlib.util.find_spec(g) is None]


def _duong_dan_bat(goc: str, p: str) -> str:
    """Đường dẫn viết vào ``.bat`` — cmd.exe đọc file .bat theo trang mã OEM nên CHỈ dùng ASCII: không dấu →
    TUYỆT ĐỐI (chép file .bat ra Desktop vẫn chạy); có dấu mà nằm trong thư mục cài đặt → ``%~dp0…`` (cmd tự
    mở rộng đúng — khi đó dùng LỐI TẮT thay vì chép file); có dấu mà ngoài thư mục cài đặt → từ chối."""
    p = os.path.abspath(p)
    if p.isascii():
        return p
    try:
        rel = os.path.relpath(p, goc)
    except ValueError:                               # khác ổ đĩa
        rel = ""
    if rel and not rel.startswith("..") and not os.path.isabs(rel):
        return "%~dp0" + rel
    raise LoiBootstrap("Python của launcher nằm NGOÀI thư mục cài đặt và đường dẫn có ký tự có dấu — bỏ "
                       "--python-launcher (bootstrap tự tạo trong thư mục cài đặt) hoặc chọn đường dẫn không dấu.")


def _bat(duong_dan: str, dong: list) -> None:
    with open(duong_dan, "w", encoding="ascii", newline="\r\n") as f:
        f.write("\n".join(dong) + "\n")


def tao_bat(goc: str, py_launcher: str) -> list:
    """Ba file chạy cho người vận hành. ``-E -s``: biến PYTHON* và site của người dùng không chen vào bộ
    xác minh chữ ký của launcher."""
    lc = _duong_dan_bat(goc, os.path.join(goc, "launcher", "launcher.py"))
    py = _duong_dan_bat(goc, py_launcher)
    tep = []
    for ten, lenh, cho in (("TimClipPro.bat", "app", True), ("GiamSat.bat", "watch %*", False),
                           ("CapNhat.bat", "update prepare", True)):
        dong = ["@echo off", "REM Ban cai TimClip Pro co quan ly (launcher). KHONG dung updater cu.",
                f'"{py}" -E -s "{lc}" {lenh}', 'set "MA=%errorlevel%"']
        if ten == "CapNhat.bat":
            dong += ['if not "%MA%"=="0" goto :xong', f'"{py}" -E -s "{lc}" update apply',
                     'set "MA=%errorlevel%"', ":xong"]
        if cho:
            dong += ['if not "%MA%"=="0" pause']
        dong += ["exit /b %MA%"]
        p = os.path.join(goc, ten)
        _bat(p, dong)
        tep.append(p)
    return tep


def xml_lich(ten: str, lenh: str, doi_so: str, thu_muc: str, *, gio: str = "08:00",
             lap_lai_gio: int = 0, mo_ta: str = "") -> str:
    """XML Task Scheduler 1.2 để XEM TRƯỚC: chạy KHÔNG quyền admin, không chạy chồng (IgnoreNew), giới hạn
    thời gian, đường dẫn tuyệt đối. Bootstrap KHÔNG đăng ký — người vận hành tự import khi pilot được duyệt."""
    lap = (f"<Repetition><Interval>PT{int(lap_lai_gio)}H</Interval><Duration>P1D</Duration>"
           "<StopAtDurationEnd>false</StopAtDurationEnd></Repetition>") if lap_lai_gio else ""
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>{escape(mo_ta)}</Description><URI>\\TimClipPro\\{escape(ten)}</URI></RegistrationInfo>
  <Triggers><CalendarTrigger><StartBoundary>2026-01-01T{gio}:00</StartBoundary>{lap}<Enabled>true</Enabled><ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger></Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT6H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author"><Exec><Command>{escape(lenh)}</Command><Arguments>{escape(doi_so)}</Arguments><WorkingDirectory>{escape(thu_muc)}</WorkingDirectory></Exec></Actions>
</Task>
"""


def tao_lich_xem_truoc(goc: str, state: str, py_launcher: str) -> list:
    thu_muc = os.path.join(goc, "launcher", THU_MUC_LICH)
    os.makedirs(thu_muc, exist_ok=True)
    lc = os.path.join(goc, "launcher", "launcher.py")
    tep = []
    for ten, doi_so, gio, lap, mo_ta in (
            ("GiamSat", f'-E -s "{lc}" watch --destination <MÃ_HỒ_SƠ_ĐÍCH>', "08:00", 3,
             "Giám sát kênh theo watchlist; gửi Google Sheets theo hồ sơ đích chỉ định."),
            ("CapNhat", f'-E -s "{lc}" update prepare', "03:00", 0,
             "Tải + kiểm bản Stable mới (chưa áp dụng). Áp dụng khi rảnh: thêm lệnh update apply SAU "
             "khi pilot được duyệt.")):
        p = os.path.join(thu_muc, f"TimClipPro_{ten}.xml")
        with open(p, "w", encoding="utf-16") as f:
            f.write(xml_lich(ten, py_launcher, doi_so, state, gio=gio, lap_lai_gio=lap, mo_ta=mo_ta))
        tep.append(p)
    with open(os.path.join(thu_muc, "DOC_TRUOC.txt"), "w", encoding="utf-8") as f:
        f.write("Các file XML này CHƯA được đăng ký vào Task Scheduler. Chỉ import (schtasks /create /xml …)\n"
                "sau khi pilot PC2 được duyệt; thay <MÃ_HỒ_SƠ_ĐÍCH> bằng mã hồ sơ đích tạo trong ứng dụng.\n")
    return tep


def tao_moi_truong_launcher(goc: str, python_goc: str, kit_dir: str, *, chay=None) -> str:
    """Môi trường RIÊNG của launcher (``cryptography`` để xác minh chữ ký, ``requests`` cho nguồn GitHub), tạo
    tại đường dẫn cuối từ Python gốc + ``launcher-lock.txt`` CÓ BĂM trong bộ bootstrap. Cần mạng (PyPI) — bước
    pilot có duyệt. ``--clear``: lần trước dừng giữa chừng thì tạo lại sạch."""
    chay = chay or subprocess.run
    lock = os.path.join(kit_dir, "launcher-lock.txt")
    with open(lock, encoding="utf-8") as f:
        if "--hash=sha256:" not in f.read():
            raise LoiBootstrap("launcher-lock.txt chưa có băm gói — không cài gói chưa xác minh.")
    env = os.path.join(goc, "launcher", "env")
    chay([python_goc, "-P", "-m", "venv", "--clear", env], check=True, timeout=600)
    py = os.path.join(env, "Scripts", "python.exe")
    chay([py, "-P", "-m", "pip", "install", "--no-input", "--disable-pip-version-check", "--require-hashes",
          "--only-binary=:all:", "-r", lock], check=True, timeout=1800)
    return py


def bootstrap(goc: str, state: str, *, kit_dir: str, python_goc: str, tin_cay: str, nguon: dict,
              workspace: str = runtime_paths.WORKSPACE_MAC_DINH, py_launcher: str = "",
              cai_ban_dau: bool = True, **thay) -> dict:
    """Dựng một cài đặt managed mới (hoặc làm TIẾP lần trước dừng trước launcher.json). ``thay``: phụ thuộc
    của bộ cập nhật (kiểm thử tiêm runtime/health). Python đang chạy phải có ``cryptography`` (``main`` lo
    việc này khi chạy bằng Python gốc)."""
    goc, state, tiep_tuc = kiem_truoc(goc, state, python_goc)
    _kiem_khoa_tin_cay_tho(tin_cay)
    thieu = [f for f in FILE_LAUNCHER if not os.path.isfile(os.path.join(kit_dir, f))]
    if thieu:
        raise LoiBootstrap("Bộ bootstrap thiếu file: " + ", ".join(thieu))
    if py_launcher:
        py_launcher = os.path.abspath(py_launcher)
        _duong_dan_bat(goc, py_launcher)                 # đường dẫn viết được vào .bat — kiểm TRƯỚC khi ghi
    else:
        py_launcher = tao_moi_truong_launcher(goc, python_goc, kit_dir)
    khoa = mu.doc_khoa_tin_cay(tin_cay)                   # dựng khoá thật TRƯỚC khi ghi file cài đặt
    thu_muc_lc = os.path.join(goc, "launcher")
    os.makedirs(thu_muc_lc, exist_ok=True)
    for f in FILE_LAUNCHER:
        shutil.copy2(os.path.join(kit_dir, f), os.path.join(thu_muc_lc, f))
    shutil.copy2(tin_cay, os.path.join(thu_muc_lc, "trusted_keys.json"))
    for con in ("data", "output", "secrets", "backups", "logs"):
        os.makedirs(os.path.join(state, con), exist_ok=True)
    bat = tao_bat(goc, py_launcher)
    lich = tao_lich_xem_truoc(goc, state, py_launcher)
    dd = (runtime_paths.doc_dinh_danh(state) if tiep_tuc
          else runtime_paths.tao_dinh_danh(state, installation_root=goc, workspace=workspace))
    cfg = {"dinh_dang": 1, "state_root": state, "nguon": nguon, "python_goc": os.path.abspath(python_goc),
           "python_launcher": py_launcher, "han_cho_ranh_s": 600}
    mu.ghi_json_nguyen_tu(os.path.join(thu_muc_lc, "launcher.json"), cfg)     # CUỐI: đánh dấu đã bootstrap
    kq = {"goc": goc, "state": state, "installation_id": dd["installation_id"], "tiep_tuc": tiep_tuc,
          "bat": bat, "lich": lich, "khoa_tin_cay": sorted(khoa), "cai_dat": None}
    if cai_ban_dau:
        try:
            sys.path.insert(0, thu_muc_lc)
            import launcher

            cn = launcher.tao_cap_nhat(goc, cfg, **thay)
            bc = cn.chuan_bi()
            kq["cai_dat"] = (bc if bc.trang_thai != mu.STAGED else cn.ap_dung()).__dict__
        except Exception as e:  # noqa: BLE001 — cài đặt đã dựng xong; bản đầu cài lại bằng CapNhat.bat
            kq["cai_dat"] = {"trang_thai": mu.LOI, "phien_ban": "", "chi_tiet": [],
                             "thong_diep": f"Cài bản đầu chưa xong ({type(e).__name__}: {e}) — cài đặt đã tạo; "
                                           "khắc phục rồi chạy CapNhat.bat."}
    return kq


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

    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description="Bootstrap cài đặt managed TimClipPro (PC2)")
    ap.add_argument("--goc", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--python-goc", required=True)
    ap.add_argument("--python-launcher", default="")
    ap.add_argument("--tin-cay", required=True)
    ap.add_argument("--workspace", default=runtime_paths.WORKSPACE_MAC_DINH)
    nguon = ap.add_mutually_exclusive_group(required=True)
    nguon.add_argument("--nguon-thu-muc")
    nguon.add_argument("--repo")
    a = ap.parse_args(argv)
    cfg_nguon = ({"loai": "thu_muc", "duong_dan": os.path.abspath(a.nguon_thu_muc)} if a.nguon_thu_muc
                 else {"loai": "github", "repo": a.repo})
    kit = os.path.dirname(os.path.abspath(__file__))
    try:
        if not a.python_launcher and _thieu_goi(cfg_nguon):
            # Giai đoạn 1 (Python gốc, chỉ thư viện chuẩn): kiểm trước khi ghi, tạo môi trường launcher (pip có
            # băm), rồi chạy lại CHÍNH file này bằng Python của môi trường đó (có cryptography/requests).
            goc, _, _ = kiem_truoc(a.goc, a.state, a.python_goc)
            _kiem_khoa_tin_cay_tho(a.tin_cay)
            py = tao_moi_truong_launcher(goc, a.python_goc, kit)
            return subprocess.run([py, "-E", "-s", os.path.abspath(__file__), *argv,
                                   "--python-launcher", py]).returncode
        kq = bootstrap(a.goc, a.state, kit_dir=kit, python_goc=a.python_goc, tin_cay=a.tin_cay,
                       nguon=cfg_nguon, workspace=a.workspace, py_launcher=a.python_launcher)
    except (LoiBootstrap, runtime_paths.LoiRuntime, mu.LoiCapNhat, OSError) as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — người vận hành không lập trình: không traceback
        print(f"[LỖI] {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str))
    cai = kq.get("cai_dat") or {}
    return 0 if cai.get("trang_thai") == mu.ACTIVE else 1


if __name__ == "__main__":
    raise SystemExit(main())
