# -*- coding: utf-8 -*-
"""Bootstrap MỘT LẦN cho máy vận hành (PC2) — docs/HUONG_DAN_PC2.md, docs/MANAGED_UPDATE.md §2.

    python bootstrap.py --goc D:\\TimClipPro --state D:\\TimClipPro_State --python-goc "C:\\...\\python.exe"
                        --tin-cay trusted_keys.json (--nguon-thu-muc E:\\phat_hanh | --repo chu/du-an)
                        [--workspace mac_dinh] [--python-launcher <python có cryptography>]

Làm: kiểm đường dẫn (không OneDrive/ổ mạng, không đè cài đặt/định danh có sẵn, không đè bản clone git cũ)
→ tạo ``installation.json`` với UUID MỚI (PC2 không bao giờ kế thừa định danh của PC1) → chép launcher +
khoá tin cậy → ``launcher.json`` → ``TimClipPro.bat``/``GiamSat.bat``/``CapNhat.bat`` → XML lịch Windows
để XEM TRƯỚC (KHÔNG đăng ký) → cài bản Stable đầu tiên qua ĐÚNG bộ cập nhật (chữ ký, băm, health).
PC2 bắt đầu với kho RỖNG và tự dựng; không chép kho, lịch sử, outbox, cookie hay khoá từ PC1.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from xml.sax.saxutils import escape

import managed_update as mu
import runtime_paths

FILE_LAUNCHER = ("launcher.py", "managed_update.py", "maintenance_gate.py", "khoa.py",
                 "runtime_paths.py")
THU_MUC_LICH = "lich_xem_truoc"


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


def kiem_truoc(goc: str, state: str, python_goc: str) -> tuple:
    """Kiểm MỌI điều kiện trước khi ghi byte nào. Trả ``(goc, state)`` đã chuẩn hoá."""
    goc, state = _kiem_goc("Thư mục cài đặt", goc), _kiem_goc("State root", state)
    if os.path.normcase(goc) == os.path.normcase(state):
        raise LoiBootstrap("Thư mục cài đặt và state root phải khác nhau.")
    if os.path.exists(os.path.join(goc, "launcher", "launcher.json")):
        raise LoiBootstrap("Thư mục cài đặt đã được bootstrap — không làm lại đè lên.")
    if os.path.exists(os.path.join(goc, ".git")) or os.path.exists(os.path.join(state, ".git")):
        raise LoiBootstrap("Không cài vào thư mục là bản clone git cũ — chọn thư mục MỚI.")
    if os.path.exists(os.path.join(state, runtime_paths.TEN_DINH_DANH)):
        raise LoiBootstrap("State root đã thuộc một cài đặt khác — không ghi đè định danh.")
    if not (os.path.isabs(python_goc) and os.path.isfile(python_goc)):
        raise LoiBootstrap("Không thấy Python gốc (cần đường dẫn tuyệt đối tới python.exe 3.12).")
    return goc, state


def _bat(duong_dan: str, dong: list) -> None:
    with open(duong_dan, "w", encoding="ascii", newline="\r\n") as f:
        f.write("\n".join(dong) + "\n")


def tao_bat(goc: str, py_launcher: str) -> list:
    """Ba file chạy cho người vận hành — gọi launcher bằng đường dẫn TUYỆT ĐỐI (không phụ thuộc PATH)."""
    lc = os.path.join(goc, "launcher", "launcher.py")
    tep = []
    for ten, lenh, cho in (("TimClipPro.bat", "app", True), ("GiamSat.bat", "watch %*", False),
                           ("CapNhat.bat", "update prepare", True)):
        dong = ["@echo off", "REM Ban cai TimClip Pro co quan ly (launcher). KHONG dung updater cu.",
                f'"{py_launcher}" "{lc}" {lenh}', 'set "MA=%errorlevel%"']
        if ten == "CapNhat.bat":
            dong += ['if not "%MA%"=="0" goto :xong', f'"{py_launcher}" "{lc}" update apply',
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
            ("GiamSat", f'"{lc}" watch --destination <MÃ_HỒ_SƠ_ĐÍCH>', "08:00", 3,
             "Giám sát kênh theo watchlist; gửi Google Sheets theo hồ sơ đích chỉ định."),
            ("CapNhat", f'"{lc}" update prepare', "03:00", 0,
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
    """Môi trường RIÊNG của launcher (chỉ ``cryptography`` để xác minh chữ ký), tạo tại đường dẫn cuối từ
    Python gốc + ``launcher-lock.txt`` CÓ BĂM trong bộ bootstrap. Cần mạng (PyPI) — bước pilot có duyệt."""
    import subprocess

    chay = chay or subprocess.run
    lock = os.path.join(kit_dir, "launcher-lock.txt")
    with open(lock, encoding="utf-8") as f:
        if "--hash=sha256:" not in f.read():
            raise LoiBootstrap("launcher-lock.txt chưa có băm gói — không cài gói chưa xác minh.")
    env = os.path.join(goc, "launcher", "env")
    chay([python_goc, "-m", "venv", env], check=True, timeout=600)
    py = os.path.join(env, "Scripts", "python.exe")
    chay([py, "-m", "pip", "install", "--no-input", "--disable-pip-version-check", "--require-hashes",
          "--only-binary=:all:", "-r", lock], check=True, timeout=1800)
    return py


def bootstrap(goc: str, state: str, *, kit_dir: str, python_goc: str, tin_cay: str, nguon: dict,
              workspace: str = runtime_paths.WORKSPACE_MAC_DINH, py_launcher: str = "",
              cai_ban_dau: bool = True, **thay) -> dict:
    """Dựng một cài đặt managed mới. ``thay``: phụ thuộc của bộ cập nhật (kiểm thử tiêm runtime/health)."""
    goc, state = kiem_truoc(goc, state, python_goc)
    khoa = mu.doc_khoa_tin_cay(tin_cay)                       # kiểm khoá tin cậy TRƯỚC khi ghi
    thieu = [f for f in FILE_LAUNCHER if not os.path.isfile(os.path.join(kit_dir, f))]
    if thieu:
        raise LoiBootstrap("Bộ bootstrap thiếu file: " + ", ".join(thieu))
    thu_muc_lc = os.path.join(goc, "launcher")
    os.makedirs(thu_muc_lc, exist_ok=True)
    if not py_launcher:
        py_launcher = tao_moi_truong_launcher(goc, python_goc, kit_dir)
    for f in FILE_LAUNCHER:
        shutil.copy2(os.path.join(kit_dir, f), os.path.join(thu_muc_lc, f))
    shutil.copy2(tin_cay, os.path.join(thu_muc_lc, "trusted_keys.json"))
    for con in ("data", "output", "secrets", "backups", "logs"):
        os.makedirs(os.path.join(state, con), exist_ok=True)
    dd = runtime_paths.tao_dinh_danh(state, installation_root=goc, workspace=workspace)
    cfg = {"dinh_dang": 1, "state_root": state, "nguon": nguon, "python_goc": os.path.abspath(python_goc),
           "python_launcher": py_launcher, "han_cho_ranh_s": 600, "tu_ap_dung": False}
    mu.ghi_json_nguyen_tu(os.path.join(thu_muc_lc, "launcher.json"), cfg)
    bat = tao_bat(goc, py_launcher)
    lich = tao_lich_xem_truoc(goc, state, py_launcher)
    kq = {"goc": goc, "state": state, "installation_id": dd["installation_id"], "bat": bat, "lich": lich,
          "khoa_tin_cay": sorted(khoa), "cai_dat": None}
    if cai_ban_dau:
        sys.path.insert(0, thu_muc_lc)
        import launcher

        cn = launcher.tao_cap_nhat(goc, cfg, **thay)
        bc = cn.chuan_bi()
        kq["cai_dat"] = (bc if bc.trang_thai != mu.STAGED else cn.ap_dung()).__dict__
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
    try:
        kq = bootstrap(a.goc, a.state, kit_dir=os.path.dirname(os.path.abspath(__file__)),
                       python_goc=a.python_goc, tin_cay=a.tin_cay, nguon=cfg_nguon,
                       workspace=a.workspace, py_launcher=a.python_launcher)
    except (LoiBootstrap, runtime_paths.LoiRuntime, mu.LoiCapNhat, OSError) as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        return 1
    print(json.dumps(kq, ensure_ascii=False, indent=1, default=str))
    cai = kq.get("cai_dat") or {}
    return 0 if cai.get("trang_thai") == mu.ACTIVE else 1


if __name__ == "__main__":
    raise SystemExit(main())
