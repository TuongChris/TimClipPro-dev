# -*- coding: utf-8 -*-
"""Kiểm tra sức khoẻ của MỘT release — updater chạy bằng runtime của chính release đó, tiến trình riêng.

    python health_check.py kiem --che-do staging|kich_hoat --data-dir <data của state root>
    python health_check.py migrate --data-dir <data của state root>

* Chặn mạng ra ngoài TRƯỚC khi import mã dự án: không gọi Google/YouTube, không gửi outbox thật.
* ``staging``: Engine mới trên state root TẠM (DB tạm được tạo/nâng cấp ở đó); DB thật chỉ mở READ-ONLY
  (URI ``mode=ro``) để kiểm phiên bản lược đồ và đọc thử ảnh chụp báo cáo V2. Không init/migrate DB thật.
* ``kich_hoat``: như trên + DB thật phải đã ở đúng phiên bản lược đồ của release (migration đã chạy).
* ``migrate``: nâng cấp lược đồ DB thật bằng MÃ CỦA RELEASE NÀY (``lich_su.dam_bao_luoc_do`` — một giao
  dịch, có sao lưu, idempotent). Updater chỉ gọi khi cổng bảo trì đã rút xong.

"Cổng trả 200" không đủ: kiểm phiên bản Python, import lõi, phiên bản thư viện thật, lược đồ, ảnh chụp V2.
Kết quả: MỘT dòng JSON ở stdout; mã thoát 0 = đạt.
"""

from __future__ import annotations

import json
import os
import socket
import sys

MAU_ANH_CHUP = 50
# Kết quả in trên MỘT dòng mở đầu bằng dấu này (launcher đọc đúng dòng đó, bỏ qua dòng thư viện in thêm khi
# thoát). Giữ đúng giá trị ở launcher.DAU_KET_QUA_HEALTH — launcher nằm NGOÀI release, đổi là vỡ hợp đồng.
DAU_KET_QUA = "TIMCLIP_HEALTH_KET_QUA"


def chan_mang() -> None:
    """Mọi kết nối ra ngoài loopback → lỗi. Đặt TRƯỚC khi import mã dự án/thư viện."""
    goc = socket.socket.connect

    def connect(self, dia_chi):
        host = dia_chi[0] if isinstance(dia_chi, tuple) else dia_chi
        if str(host) not in ("127.0.0.1", "::1", "localhost"):
            raise OSError("health_check: mạng bị chặn")
        return goc(self, dia_chi)

    def create_connection(dia_chi, *a, **k):
        if str(dia_chi[0]) not in ("127.0.0.1", "::1", "localhost"):
            raise OSError("health_check: mạng bị chặn")
        return goc_tao(dia_chi, *a, **k)

    goc_tao = socket.create_connection
    socket.socket.connect = connect
    socket.create_connection = create_connection


def _phien_ban_thu_vien() -> dict:
    from importlib import metadata

    kq = {}
    for ten in ("streamlit", "gspread", "google-auth", "requests", "yt-dlp", "cryptography", "numpy",
                "scipy", "pandas"):
        try:
            kq[ten] = metadata.version(ten)
        except metadata.PackageNotFoundError:
            kq[ten] = None
    return kq


def _ffmpeg() -> dict:
    import shutil
    import subprocess

    kq = {}
    for ten in ("ffmpeg", "ffprobe"):
        duong = shutil.which(ten)
        if not duong:
            kq[ten] = None
            continue
        try:
            dau = subprocess.run([duong, "-version"], capture_output=True, text=True, timeout=20,
                                 encoding="utf-8", errors="replace").stdout.splitlines()[:1]
        except (OSError, subprocess.SubprocessError):
            dau = []
        kq[ten] = dau[0] if dau else "không đọc được phiên bản"
    return kq


def _doc_db_that(data_dir: str, phien_ban_code: int) -> dict:
    """Mở lichsu.db THẬT ở chế độ chỉ đọc: phiên bản lược đồ, đọc thử ảnh chụp V2, đếm outbox."""
    import sqlite3
    from urllib.parse import quote

    import bao_cao_v2

    db = os.path.join(data_dir, "lichsu.db")
    if not os.path.isfile(db):
        return {"co_db": False}
    uri = "file:" + quote(os.path.abspath(db).replace("\\", "/")) + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=30)
    try:
        con.row_factory = sqlite3.Row
        pb = con.execute("PRAGMA user_version").fetchone()[0]
        bang = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        ok = hong = 0
        if "bao_cao_job" in bang:
            for h in con.execute("SELECT chinh_sach, du_lieu FROM bao_cao_job ORDER BY job_id DESC "
                                 "LIMIT ?", (MAU_ANH_CHUP,)):
                bc = bao_cao_v2.doc_anh_chup_da_luu(h["chinh_sach"], h["du_lieu"])
                if bao_cao_v2.la_loi_bao_cao(bc) and bc.loai == bao_cao_v2.LOI_HONG:
                    hong += 1
                else:
                    ok += 1
        outbox = {}
        if "hang_doi_gui" in bang:
            outbox = {r[0]: r[1] for r in con.execute(
                "SELECT trang_thai, COUNT(*) FROM hang_doi_gui GROUP BY trang_thai")}
    finally:
        con.close()
    return {"co_db": True, "phien_ban_db": pb, "phien_ban_code": phien_ban_code,
            "anh_chup_doc_duoc": ok, "anh_chup_hong": hong, "outbox": outbox}


def _engine_tam() -> dict:
    """Engine thật trên state root TẠM (chế độ managed, định danh tạm): tạo DB tạm, đọc lịch sử, outbox."""
    import shutil
    import tempfile

    import outbox
    import runtime_paths
    from engine import Engine

    goc = tempfile.mkdtemp(prefix="timclip_health_")
    try:
        state = os.path.join(goc, "state")
        os.makedirs(state)
        runtime_paths.tao_dinh_danh(state, installation_root=os.path.join(goc, "cai_dat"))
        rt = runtime_paths.resolve({"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": state})
        eng = Engine(runtime=rt)
        return {"lich_su_tam": len(eng.list_jobs(5)), "outbox_tam": sum(
            outbox.tom_tat(eng.sqlite_file).values())}
    finally:
        shutil.rmtree(goc, ignore_errors=True)


def kiem(data_dir: str, che_do: str) -> dict:
    loi, canh_bao = [], []
    kq: dict = {"che_do": che_do, "python": ".".join(map(str, sys.version_info[:3]))}
    goc_release = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(goc_release, "manifest.json"), encoding="utf-8") as f:
            mong = str(json.load(f).get("python") or "")
        if mong and ".".join(map(str, sys.version_info[:2])) != mong:
            loi.append(f"Python {kq['python']} khác bản phát hành yêu cầu ({mong}).")
    except FileNotFoundError:
        canh_bao.append("Không thấy manifest.json cạnh mã (chạy ngoài release).")
    except (OSError, ValueError):
        loi.append("manifest.json của release hỏng.")
    try:
        import sqlite3

        import bao_cao_v2  # noqa: F401
        import cli  # noqa: F401
        import engine  # noqa: F401
        import lich_su
        import maintenance_gate  # noqa: F401
        import outbox  # noqa: F401
        import sheet_destinations  # noqa: F401
        import sheets  # noqa: F401
        import watch  # noqa: F401

        kq["sqlite"] = sqlite3.sqlite_version
        kq["lich_su_code"] = lich_su.PHIEN_BAN
    except Exception as e:  # noqa: BLE001 — health check báo lỗi, không ném
        loi.append(f"Không import được lõi: {type(e).__name__}: {e}")
        return {**kq, "ok": False, "loi": loi, "canh_bao": canh_bao}
    kq["thu_vien"] = _phien_ban_thu_vien()
    for ten in ("streamlit", "gspread", "cryptography"):
        if not kq["thu_vien"].get(ten):
            loi.append(f"Thiếu thư viện {ten}.")
    kq["ffmpeg"] = _ffmpeg()
    if not kq["ffmpeg"].get("ffmpeg"):
        canh_bao.append("Không thấy ffmpeg trong PATH (quét sẽ lỗi).")
    try:
        kq["engine_tam"] = _engine_tam()
    except Exception as e:  # noqa: BLE001
        loi.append(f"Engine trên state root tạm lỗi: {type(e).__name__}: {e}")
    try:
        db = _doc_db_that(data_dir, lich_su.PHIEN_BAN)
        kq["db"] = db
        if db.get("co_db"):
            if db["phien_ban_db"] > lich_su.PHIEN_BAN:
                loi.append(f"Lịch sử ở phiên bản {db['phien_ban_db']} mới hơn mã "
                           f"({lich_su.PHIEN_BAN}) — schema quá mới.")
            if che_do == "kich_hoat" and db["phien_ban_db"] < lich_su.PHIEN_BAN:
                loi.append("Lịch sử chưa được nâng cấp lên phiên bản của release.")
            if db["anh_chup_hong"] and not db["anh_chup_doc_duoc"]:
                loi.append("Không đọc được ảnh chụp báo cáo V2 nào bằng mã mới.")
    except Exception as e:  # noqa: BLE001
        loi.append(f"Không đọc được lịch sử (chỉ đọc): {type(e).__name__}")
        if la_loi_tam_thoi(e):
            kq["tam_thoi"] = True
    return {**kq, "ok": not loi, "loi": loi, "canh_bao": canh_bao}


def migrate(data_dir: str) -> dict:
    import lich_su

    db = os.path.join(data_dir, "lichsu.db")
    kq = lich_su.dam_bao_luoc_do(db)
    return {"ok": True, "phien_ban_cu": kq.get("phien_ban_cu"), "phien_ban": kq.get("phien_ban"),
            "da_nang_cap": kq.get("da_nang_cap"), "sao_luu": bool(kq.get("sao_luu"))}


def _utf8_dau_ra() -> None:
    """stdout/stderr bị chuyển hướng (log Task Scheduler, ống dẫn) mặc định là mã ANSI (cp1252/cp1258) —
    in tiếng Việt / ✅ sẽ sập. Chuyển sang UTF-8, lỗi thì thay ký tự (không bao giờ sập vì in)."""
    for luong in (sys.stdout, sys.stderr):
        try:
            if (luong.encoding or "").lower().replace("-", "") != "utf8":
                luong.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def la_loi_tam_thoi(e: BaseException) -> bool:
    """CSDL đang bị khoá/bận = có thể chỉ tạm thời (bộ cập nhật đếm lần, không cách ly ngay)."""
    import sqlite3

    return isinstance(e, sqlite3.OperationalError) and any(x in str(e).lower() for x in ("locked", "busy"))


def main(argv=None) -> int:
    _utf8_dau_ra()
    import argparse

    ap = argparse.ArgumentParser(description="Kiểm tra sức khoẻ release TimClipPro")
    ap.add_argument("lenh", choices=["kiem", "migrate"])
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--che-do", choices=["staging", "kich_hoat"], default="staging")
    a = ap.parse_args(argv)
    chan_mang()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        kq = kiem(a.data_dir, a.che_do) if a.lenh == "kiem" else migrate(a.data_dir)
    except Exception as e:  # noqa: BLE001
        kq = {"ok": False, "loi": [f"{type(e).__name__}: {e}"], "tam_thoi": la_loi_tam_thoi(e)}
    sys.stdout.write(f"{DAU_KET_QUA} {json.dumps(kq, ensure_ascii=False)}\n")
    sys.stdout.flush()
    return 0 if kq.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
