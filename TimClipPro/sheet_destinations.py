# -*- coding: utf-8 -*-
"""Hồ sơ đích Google Sheets, credential binding và ảnh chụp đích GHIM theo job.

Thiết kế: docs/MANAGED_RUNTIME_DESIGN.md §2, §5. Lưu trong ``lichsu.db`` (lược đồ v3) để kiểm "còn
được tham chiếu" trong cùng giao dịch với outbox.

* Hồ sơ (``dich_gui``) trỏ tới revision hiện hành; mỗi lần sửa thêm MỘT revision bất biến
  (``dich_gui_phien_ban``). Việc gửi đã ghim mang theo cả ảnh chụp revision của nó.
* Tab định danh bằng ``worksheet_id`` (gid). Hồ sơ có gid: tên tab là nhãn ĐỐI CHIẾU — lần gửi đầu
  của một revision mà tab mang tên khác thì chặn. Hồ sơ không gid (link cũ, luôn là «KetQuaQuet» như
  bản cũ — gid trong link cũ bị BỎ QUA): tìm theo TÊN ở lần gửi đầu. Gid thật được CHỐT cho revision
  (``dich_gui_tab_chot``) NGAY TRƯỚC request ghi đầu tiên, trong cùng giao dịch với ``SENDING`` (không chờ
  SENT — MR-P1-02) — từ đó mọi lần gửi (thử lại, gửi lại sau UNKNOWN, việc khác cùng revision) theo mã đó, dù
  tab đổi tên hay có tab cùng tên được tạo lại.
* Credential binding (``xac_thuc_gui``) = đường dẫn file khoá + tài khoản dịch vụ MONG ĐỢI
  (``client_email``) + ``private_key_id`` lúc đăng ký. KHÔNG lưu khoá riêng hay token. Đổi file khoá
  sang tài khoản khác không bao giờ được chấp nhận âm thầm.
* Ảnh chụp ghim (``DichGuiChot``) chỉ gồm giá trị vô hướng và được tuần tự hoá thành chuỗi JSON chuẩn —
  không có cấu trúc lồng nào sửa được sau khi chụp.

Module THUẦN (không Streamlit, không mạng). Mọi chuỗi cho người dùng bằng tiếng Việt.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import Optional

SCHEMA_NGANG = "ngang34"
SCHEMA_DOC = "doc16"
SO_COT = {SCHEMA_NGANG: 34, SCHEMA_DOC: 16}
SCHEMA_NHAN = {SCHEMA_NGANG: "Ngang 34 cột", SCHEMA_DOC: "Dọc 16 cột"}

TT_HOAT_DONG = "hoat_dong"
TT_TAM_DUNG = "tam_dung"
TT_LUU_TRU = "luu_tru"
_TRANG_THAI = (TT_HOAT_DONG, TT_TAM_DUNG, TT_LUU_TRU)

NGUON_TAY = "tay"
NGUON_LINK_CU = "link_cu"
REF_MAC_DINH = "mac_dinh"
TAB_MAC_DINH = "KetQuaQuet"
WORKSPACE_MAC_DINH = "mac_dinh"

THOI_GIAN_CHO_KHOA_S = 30.0
_TRUONG_SUA = frozenset({"ten", "spreadsheet_id", "worksheet_id", "worksheet_ten", "schema_id",
                         "xac_thuc_ref"})
_ID_BANG = re.compile(r"[A-Za-z0-9_-]{20,}")
_REF = re.compile(r"[a-z0-9_]{1,40}")


class LoiDichGui(ValueError):
    """Hồ sơ/binding sai hoặc không dùng được — thông báo tiếng Việt, không chứa bí mật."""


# ---------------------------------------------------------------------------
#  Kết nối — giao dịch ngắn, KHÔNG gọi mạng khi đang mở giao dịch
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def ket_noi(db_path: str, *, ghi: bool = False):
    """Kết nối ngắn hạn. ``ghi=True``: ``BEGIN IMMEDIATE`` (giữ khoá ghi từ đầu nên đọc-rồi-ghi
    trong cùng khối là nguyên tử với tiến trình khác), lỗi thì ROLLBACK."""
    con = sqlite3.connect(db_path, timeout=THOI_GIAN_CHO_KHOA_S, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        if ghi:
            con.execute("BEGIN IMMEDIATE")
        yield con
        if ghi:
            con.execute("COMMIT")
    except BaseException:
        if ghi and con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def _bay_gio() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
#  Định danh máy
# ---------------------------------------------------------------------------

def dinh_danh_may(db_path: str, *, mong_doi: str = "") -> str:
    """``installation_id`` gắn với lịch sử này. Chưa có → ghi ``mong_doi`` (managed: lấy từ
    ``installation.json``) hoặc một UUID mới (legacy). Đã có mà khác ``mong_doi`` → lịch sử của máy
    khác (bị chép sang) → dừng."""
    with ket_noi(db_path, ghi=True) as con:
        hang = con.execute("SELECT gia_tri FROM cai_dat_may WHERE khoa='installation_id'").fetchone()
        if hang is not None:
            if mong_doi and hang["gia_tri"] != mong_doi:
                raise LoiDichGui("Lịch sử này thuộc một cài đặt khác (định danh máy không khớp) — "
                                 "không dùng chung lịch sử/outbox giữa hai máy.")
            return hang["gia_tri"]
        iid = mong_doi or uuid.uuid4().hex
        con.execute("INSERT INTO cai_dat_may(khoa, gia_tri) VALUES('installation_id', ?)", (iid,))
        return iid


# ---------------------------------------------------------------------------
#  Link Google Sheet
# ---------------------------------------------------------------------------

def phan_tich_link(link: str) -> tuple:
    """``(spreadsheet_id, gid | None)`` từ link Google Sheet hoặc một ID trần."""
    s = (link or "").strip()
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", s)
    if m and _ID_BANG.fullmatch(m.group(1)):
        sid = m.group(1)
    elif _ID_BANG.fullmatch(s):
        sid = s
    else:
        raise LoiDichGui("Link Google Sheet không hợp lệ — cần dạng "
                         "https://docs.google.com/spreadsheets/d/<mã bảng>/edit#gid=<mã tab>.")
    g = re.search(r"[#?&]gid=(\d+)", s)
    return sid, (int(g.group(1)) if g else None)


# ---------------------------------------------------------------------------
#  Credential binding
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class XacThucGui:
    ref: str
    duong_dan: str
    principal: str
    key_id: str
    cho_xoay_khoa: bool
    trang_thai: str


def doc_khoa_dich_vu(duong_dan: str) -> tuple:
    """``(client_email, private_key_id)`` của file khoá tài khoản dịch vụ. Chỉ đọc file local;
    không trả, không ghi, không đưa vào thông báo bất cứ phần nào khác của file."""
    try:
        with open(duong_dan, encoding="utf-8") as f:
            du_lieu = json.load(f)
    except FileNotFoundError:
        raise LoiDichGui(f"Không thấy file khoá «{os.path.basename(duong_dan)}».") from None
    except (OSError, ValueError):
        raise LoiDichGui("File khoá không đọc được hoặc không phải JSON hợp lệ.") from None
    if not isinstance(du_lieu, dict) or du_lieu.get("type") != "service_account":
        raise LoiDichGui("File này không phải khoá tài khoản dịch vụ (service account) của Google.")
    email, kid = du_lieu.get("client_email"), du_lieu.get("private_key_id")
    if not (isinstance(email, str) and "@" in email and isinstance(kid, str) and kid.strip()):
        raise LoiDichGui("File khoá thiếu client_email hoặc private_key_id.")
    return email.strip(), kid.strip()


def _xac_thuc_tu_hang(h) -> XacThucGui:
    return XacThucGui(h["ref"], h["duong_dan"], h["principal"], h["key_id"],
                      bool(h["cho_xoay_khoa"]), h["trang_thai"])


def _lay_xac_thuc(con, ref: str) -> Optional[XacThucGui]:
    h = con.execute("SELECT * FROM xac_thuc_gui WHERE ref=?", (ref,)).fetchone()
    return None if h is None else _xac_thuc_tu_hang(h)


def lay_xac_thuc(db_path: str, ref: str) -> Optional[XacThucGui]:
    with ket_noi(db_path) as con:
        return _lay_xac_thuc(con, ref)


def ds_xac_thuc(db_path: str) -> list:
    with ket_noi(db_path) as con:
        return [_xac_thuc_tu_hang(h)
                for h in con.execute("SELECT * FROM xac_thuc_gui ORDER BY ref")]


def _dang_ky_xac_thuc(con, ref: str, duong_dan: str, cho_xoay_khoa: bool) -> XacThucGui:
    if not _REF.fullmatch(ref or ""):
        raise LoiDichGui("Tên binding chỉ gồm chữ thường không dấu, số và «_» (tối đa 40 ký tự).")
    principal, kid = doc_khoa_dich_vu(duong_dan)
    duong_dan = os.path.abspath(duong_dan)
    cu = _lay_xac_thuc(con, ref)
    if cu is not None and cu.principal != principal:
        raise LoiDichGui(f"Binding «{ref}» đang gắn với một tài khoản dịch vụ khác — không đổi "
                         "tài khoản âm thầm; hãy tạo binding mới rồi chọn nó cho hồ sơ.")
    if cu is None:
        con.execute("INSERT INTO xac_thuc_gui(ref, duong_dan, principal, key_id, cho_xoay_khoa,"
                    " trang_thai, tao_luc, sua_luc) VALUES(?,?,?,?,?,?,?,?)",
                    (ref, duong_dan, principal, kid, int(cho_xoay_khoa), TT_HOAT_DONG,
                     _bay_gio(), _bay_gio()))
    else:
        con.execute("UPDATE xac_thuc_gui SET duong_dan=?, key_id=?, sua_luc=? WHERE ref=?",
                    (duong_dan, kid, _bay_gio(), ref))
    return _lay_xac_thuc(con, ref)


def dang_ky_xac_thuc(db_path: str, ref: str, duong_dan: str, *,
                     cho_xoay_khoa: bool = True) -> XacThucGui:
    """Đăng ký/cập nhật một binding. Cùng tài khoản dịch vụ → cập nhật đường dẫn/key id (xoay
    khoá, chuyển file); tài khoản KHÁC → từ chối."""
    with ket_noi(db_path, ghi=True) as con:
        return _dang_ky_xac_thuc(con, ref, duong_dan, cho_xoay_khoa)


def xoa_xac_thuc(db_path: str, ref: str) -> None:
    with ket_noi(db_path, ghi=True) as con:
        if con.execute("SELECT 1 FROM dich_gui_phien_ban WHERE xac_thuc_ref=? LIMIT 1",
                       (ref,)).fetchone():
            raise LoiDichGui(f"Binding «{ref}» đang được hồ sơ đích dùng — đổi hồ sơ sang binding "
                             "khác hoặc lưu trữ hồ sơ trước.")
        for (dich_json,) in con.execute(
                "SELECT dich_json FROM hang_doi_gui WHERE trang_thai NOT IN ('SENT','CANCELLED')"):
            try:
                ref_viec = json.loads(dich_json).get("xac_thuc_ref")
            except (ValueError, TypeError, AttributeError):
                ref_viec = None                  # đích ghim hỏng: người gửi tự chặn việc đó
            if ref_viec == ref:
                raise LoiDichGui(f"Binding «{ref}» đang được việc gửi chưa xong tham chiếu.")
        con.execute("DELETE FROM xac_thuc_gui WHERE ref=?", (ref,))


# ---------------------------------------------------------------------------
#  Hồ sơ đích
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DichGui:
    id: str
    workspace: str
    phien_ban: int
    trang_thai: str
    nguon: str
    ten: str
    spreadsheet_id: str
    worksheet_id: Optional[int]
    worksheet_ten: str
    schema_id: str
    xac_thuc_ref: str
    gid_da_chot: Optional[int] = None        # mã tab chốt ở request ghi đầu của revision này (nếu có)

    @property
    def nhan(self) -> str:
        return f"{self.ten} — {self.worksheet_ten} — {SCHEMA_NHAN.get(self.schema_id, '?')}"


_SQL_DICH = ("SELECT d.id, d.workspace, r.phien_ban, d.trang_thai, d.nguon, r.ten,"
             " r.spreadsheet_id, r.worksheet_id, r.worksheet_ten, r.schema_id, r.xac_thuc_ref,"
             " c.worksheet_id AS gid_da_chot"
             " FROM dich_gui d JOIN dich_gui_phien_ban r ON r.dich_id = d.id"
             " LEFT JOIN dich_gui_tab_chot c ON c.dich_id = r.dich_id AND c.phien_ban = r.phien_ban"
             " WHERE 1=1")
_HIEN_HANH = " AND r.phien_ban = d.phien_ban"


def _dich_tu_hang(h) -> DichGui:
    return DichGui(*[h[f.name] for f in fields(DichGui)])


def _lay_dich(con, dich_id: str, phien_ban: Optional[int] = None) -> Optional[DichGui]:
    if phien_ban is None:
        h = con.execute(_SQL_DICH + _HIEN_HANH + " AND d.id=?",
                        (dich_id,)).fetchone()
    else:
        h = con.execute(_SQL_DICH + " AND d.id=? AND r.phien_ban=?",
                        (dich_id, int(phien_ban))).fetchone()
    return None if h is None else _dich_tu_hang(h)


def lay_dich(db_path: str, dich_id: str, *, phien_ban: Optional[int] = None) -> Optional[DichGui]:
    with ket_noi(db_path) as con:
        return _lay_dich(con, dich_id, phien_ban)


def ds_dich(db_path: str, *, chi_hoat_dong: bool = False, bo_luu_tru: bool = False,
            workspace: Optional[str] = None) -> list:
    """``chi_hoat_dong``: chỉ hồ sơ đang gửi; ``bo_luu_tru``: mọi hồ sơ còn dùng được cho lượt MỚI
    (hoạt động + tạm dừng gửi — việc của hồ sơ tạm dừng vẫn xếp hàng, chỉ chưa gửi)."""
    sql = _SQL_DICH + _HIEN_HANH
    tham = []
    if chi_hoat_dong:
        sql += " AND d.trang_thai=?"
        tham.append(TT_HOAT_DONG)
    elif bo_luu_tru:
        sql += " AND d.trang_thai!=?"
        tham.append(TT_LUU_TRU)
    if workspace is not None:
        sql += " AND d.workspace=?"
        tham.append(workspace)
    with ket_noi(db_path) as con:
        return [_dich_tu_hang(h) for h in con.execute(sql + " ORDER BY r.ten, d.id", tham)]


def _kiem_gia_tri(con, gt: dict) -> None:
    ten = str(gt.get("ten") or "").strip()
    if not ten or len(ten) > 120:
        raise LoiDichGui("Tên hồ sơ không được trống (tối đa 120 ký tự).")
    if not _ID_BANG.fullmatch(str(gt.get("spreadsheet_id") or "")):
        raise LoiDichGui("Mã bảng tính (spreadsheet id) không hợp lệ.")
    wid = gt.get("worksheet_id")
    if wid is not None and (isinstance(wid, bool) or not isinstance(wid, int) or wid < 0):
        raise LoiDichGui("Mã tab (gid) phải là số nguyên không âm.")
    tab = str(gt.get("worksheet_ten") or "").strip()
    if not tab or len(tab) > 100:
        raise LoiDichGui("Tên tab không được trống (tối đa 100 ký tự).")
    if gt.get("schema_id") not in SO_COT:
        raise LoiDichGui("Định dạng báo cáo phải là Ngang 34 cột hoặc Dọc 16 cột.")
    xt = _lay_xac_thuc(con, str(gt.get("xac_thuc_ref") or ""))
    if xt is None or xt.trang_thai != TT_HOAT_DONG:
        raise LoiDichGui("Chưa có binding khoá Google đang hoạt động với tên đã chọn.")


def _tao_dich(con, gt: dict, workspace: str, nguon: str) -> DichGui:
    if not workspace:
        raise LoiDichGui("Thiếu workspace.")
    _kiem_gia_tri(con, gt)
    dich_id = uuid.uuid4().hex
    luc = _bay_gio()
    con.execute("INSERT INTO dich_gui(id, workspace, phien_ban, trang_thai, nguon, tao_luc,"
                " sua_luc) VALUES(?,?,?,?,?,?,?)",
                (dich_id, workspace, 1, TT_HOAT_DONG, nguon, luc, luc))
    _ghi_revision(con, dich_id, 1, gt, luc)
    return _lay_dich(con, dich_id)


def _ghi_revision(con, dich_id: str, phien_ban: int, gt: dict, luc: str) -> None:
    con.execute("INSERT INTO dich_gui_phien_ban(dich_id, phien_ban, ten, spreadsheet_id,"
                " worksheet_id, worksheet_ten, schema_id, xac_thuc_ref, tao_luc)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (dich_id, phien_ban, str(gt["ten"]).strip(), gt["spreadsheet_id"],
                 gt.get("worksheet_id"), str(gt["worksheet_ten"]).strip(), gt["schema_id"],
                 gt["xac_thuc_ref"], luc))


def tao_dich(db_path: str, *, ten: str, spreadsheet_id: str, worksheet_id: Optional[int],
             worksheet_ten: str, schema_id: str, xac_thuc_ref: str, workspace: str,
             nguon: str = NGUON_TAY) -> DichGui:
    gt = dict(ten=ten, spreadsheet_id=spreadsheet_id, worksheet_id=worksheet_id,
              worksheet_ten=worksheet_ten, schema_id=schema_id, xac_thuc_ref=xac_thuc_ref)
    with ket_noi(db_path, ghi=True) as con:
        return _tao_dich(con, gt, workspace, nguon)


def sua_dich(db_path: str, dich_id: str, **thay_doi) -> DichGui:
    """Sửa = thêm revision MỚI (revision cũ giữ nguyên cho các việc đã ghim)."""
    la = set(thay_doi) - _TRUONG_SUA
    if la:
        raise LoiDichGui("Không sửa được trường: " + ", ".join(sorted(la)))
    with ket_noi(db_path, ghi=True) as con:
        hien = _lay_dich(con, dich_id)
        if hien is None:
            raise LoiDichGui("Không thấy hồ sơ đích.")
        gt = {k: getattr(hien, k) for k in _TRUONG_SUA}
        gt.update(thay_doi)
        _kiem_gia_tri(con, gt)
        moi = hien.phien_ban + 1
        luc = _bay_gio()
        _ghi_revision(con, dich_id, moi, gt, luc)
        cung_tab = all(gt[k] == getattr(hien, k)
                       for k in ("spreadsheet_id", "worksheet_id", "worksheet_ten"))
        if cung_tab:
            # Cùng bảng + cùng tab: revision mới KẾ THỪA mã tab đã chốt (không tìm lại theo tên —
            # tab cùng tên tạo lại sau đó không được coi là tab cũ).
            con.execute("INSERT OR IGNORE INTO dich_gui_tab_chot(dich_id, phien_ban, worksheet_id,"
                        " worksheet_ten, luc) SELECT dich_id, ?, worksheet_id, worksheet_ten, ?"
                        " FROM dich_gui_tab_chot WHERE dich_id=? AND phien_ban=?",
                        (moi, luc, dich_id, hien.phien_ban))
        con.execute("UPDATE dich_gui SET phien_ban=?, sua_luc=? WHERE id=?", (moi, luc, dich_id))
        return _lay_dich(con, dich_id)


def doi_trang_thai(db_path: str, dich_id: str, trang_thai: str) -> DichGui:
    """Hoạt động / tạm dừng gửi / lưu trữ. KHÔNG đổi đích của việc đã ghim."""
    if trang_thai not in _TRANG_THAI:
        raise LoiDichGui("Trạng thái hồ sơ không hợp lệ.")
    with ket_noi(db_path, ghi=True) as con:
        if con.execute("UPDATE dich_gui SET trang_thai=?, sua_luc=? WHERE id=?",
                       (trang_thai, _bay_gio(), dich_id)).rowcount != 1:
            raise LoiDichGui("Không thấy hồ sơ đích.")
        return _lay_dich(con, dich_id)


@dataclass(frozen=True)
class TabDaChot:
    worksheet_id: int
    worksheet_ten: str              # tên tab LÚC chốt (để hiển thị/đối soát)


def _tab_da_chot(con, dich_id: str, phien_ban: int) -> Optional[TabDaChot]:
    h = con.execute("SELECT worksheet_id, worksheet_ten FROM dich_gui_tab_chot WHERE dich_id=?"
                    " AND phien_ban=?", (dich_id, int(phien_ban))).fetchone()
    return None if h is None else TabDaChot(int(h["worksheet_id"]), h["worksheet_ten"])


def tab_da_chot(db_path: str, dich_id: str, phien_ban: int) -> Optional[TabDaChot]:
    """Mã tab đã chốt của một revision (``None`` = revision chưa từng phát request ghi nào)."""
    with ket_noi(db_path) as con:
        return _tab_da_chot(con, dich_id, phien_ban)


def _chot_tab(con, dich_id: str, phien_ban: int, *, worksheet_id: int, worksheet_ten: str) -> TabDaChot:
    """Chốt mã tab thật cho revision TRONG giao dịch của người gọi — lần đầu thắng (đã có thì giữ nguyên), KHÔNG
    tạo revision, không đổi nhãn hồ sơ. Trả mã ĐÃ chốt (có thể của lần trước — người gọi so với tab vừa tìm).
    Người gửi gọi nó trong CÙNG giao dịch CLAIMED→SENDING, ngay TRƯỚC request ghi đầu tiên (MR-P1-02)."""
    con.execute("INSERT OR IGNORE INTO dich_gui_tab_chot(dich_id, phien_ban, worksheet_id,"
                " worksheet_ten, luc) VALUES(?,?,?,?,?)",
                (dich_id, int(phien_ban), int(worksheet_id), str(worksheet_ten)[:100], _bay_gio()))
    return _tab_da_chot(con, dich_id, phien_ban)


def xoa_dich(db_path: str, dich_id: str) -> None:
    """Chỉ xoá được hồ sơ CHƯA có việc gửi nào; đã có thì lưu trữ (giữ lịch sử đối soát)."""
    with ket_noi(db_path, ghi=True) as con:
        if con.execute("SELECT 1 FROM hang_doi_gui WHERE dich_id=? LIMIT 1", (dich_id,)).fetchone():
            raise LoiDichGui("Hồ sơ này đã có việc gửi — hãy lưu trữ thay vì xoá.")
        con.execute("DELETE FROM dich_gui_tab_chot WHERE dich_id=?", (dich_id,))
        con.execute("DELETE FROM dich_gui_phien_ban WHERE dich_id=?", (dich_id,))
        con.execute("DELETE FROM dich_gui WHERE id=?", (dich_id,))


# ---------------------------------------------------------------------------
#  Ảnh chụp ghim theo job
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DichGuiChot:
    """Đích ĐÃ CHỐT cho một lượt: chỉ giá trị vô hướng; chuỗi JSON chuẩn là dạng lưu bền."""

    dich_id: str
    phien_ban: int
    workspace: str
    installation_id: str
    ten: str
    spreadsheet_id: str
    worksheet_id: Optional[int]
    worksheet_ten: str
    schema_id: str
    xac_thuc_ref: str
    principal: str
    key_id: str
    cho_xoay_khoa: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, s: str) -> "DichGuiChot":
        try:
            d = json.loads(s)
            kieu = {"phien_ban": int, "cho_xoay_khoa": bool}
            gia_tri = {}
            for f in fields(cls):
                v = d[f.name]
                if f.name == "worksheet_id":
                    if v is not None and (isinstance(v, bool) or not isinstance(v, int)):
                        raise TypeError(f.name)
                elif not isinstance(v, kieu.get(f.name, str)) or (
                        f.name == "phien_ban" and isinstance(v, bool)):
                    raise TypeError(f.name)
                gia_tri[f.name] = v
        except (ValueError, TypeError, KeyError, AttributeError):
            raise LoiDichGui("Đích đã ghim của việc gửi bị hỏng — không đoán lại đích.") from None
        if gia_tri["schema_id"] not in SO_COT or not _ID_BANG.fullmatch(gia_tri["spreadsheet_id"]):
            raise LoiDichGui("Đích đã ghim của việc gửi bị hỏng — không đoán lại đích.")
        return cls(**gia_tri)

    @property
    def nhan(self) -> str:
        return f"{self.ten} — {self.worksheet_ten} — {SCHEMA_NHAN.get(self.schema_id, '?')}"


@dataclass(frozen=True)
class YDinhGui:
    """Ý định gửi của MỘT lượt (lô app, lượt Watch, lệnh CLI) — chụp lúc bấm Bắt đầu."""

    dich: DichGuiChot
    lo_id: str = ""


def chot_y_dinh(db_path: str, dich_id: str, *, installation_id: str, lo_id: str = "") -> YDinhGui:
    """Chụp revision HIỆN HÀNH của hồ sơ + binding khoá cho một lượt mới. Không đọc file khoá,
    không gọi mạng (kiểm khoá/tab làm ở người gửi, ngay trước khi gửi)."""
    with ket_noi(db_path) as con:
        d = _lay_dich(con, dich_id)
        if d is None:
            raise LoiDichGui("Không thấy hồ sơ đích đã chọn.")
        # Tạm dừng GỬI không chặn quét: việc của lượt mới vẫn xếp hàng bền, gửi khi bật lại.
        if d.trang_thai == TT_LUU_TRU:
            raise LoiDichGui(f"Hồ sơ «{d.ten}» đã lưu trữ — không dùng cho lượt mới.")
        xt = _lay_xac_thuc(con, d.xac_thuc_ref)
        if xt is None or xt.trang_thai != TT_HOAT_DONG:
            raise LoiDichGui(f"Hồ sơ «{d.ten}» không còn binding khoá Google hoạt động.")
    return YDinhGui(DichGuiChot(
        dich_id=d.id, phien_ban=d.phien_ban, workspace=d.workspace,
        installation_id=installation_id, ten=d.ten, spreadsheet_id=d.spreadsheet_id,
        worksheet_id=d.worksheet_id, worksheet_ten=d.worksheet_ten, schema_id=d.schema_id,
        xac_thuc_ref=d.xac_thuc_ref, principal=xt.principal, key_id=xt.key_id,
        cho_xoay_khoa=xt.cho_xoay_khoa), lo_id=lo_id)


def y_dinh_cho_luot(db_path: str, *, installation_id: str, workspace: str, khoa_mac_dinh: str,
                    dich_id: str = "", sheet_link: str = "", schema_id: str = SCHEMA_NGANG,
                    lo_id: str = "") -> Optional[YDinhGui]:
    """Đích của một lượt CLI/Watch: ``--destination`` (hồ sơ), hoặc ``--sheet`` / SHEET_LINK /
    ``data\\giam_sat_sheet.txt`` qua nhập link cũ có kiểm soát. Cả hai cùng có mà chỉ hai nơi khác
    nhau → lỗi rõ (không chọn ngẫu nhiên). Không có gì → ``None`` (chỉ lưu cục bộ)."""
    if dich_id and sheet_link:
        # Link cũ luôn nghĩa là tab «KetQuaQuet» của bảng đó (như bản cũ). Chỉ coi là CÙNG đích khi hồ
        # sơ trỏ đúng bảng đó và đúng tab «KetQuaQuet»; còn lại là mâu thuẫn → lỗi rõ.
        d = lay_dich(db_path, dich_id)
        sid, _gid = phan_tich_link(sheet_link)
        if d is None or d.spreadsheet_id != sid or d.worksheet_ten != TAB_MAC_DINH:
            raise LoiDichGui("--destination và --sheet/SHEET_LINK chỉ tới hai đích khác nhau — "
                             "hãy dùng một trong hai.")
    if dich_id:
        return chot_y_dinh(db_path, dich_id, installation_id=installation_id, lo_id=lo_id)
    if sheet_link:
        d = nhap_link_cu(db_path, sheet_link, schema_id=schema_id, duong_dan_khoa=khoa_mac_dinh,
                         workspace=workspace)
        return chot_y_dinh(db_path, d.id, installation_id=installation_id, lo_id=lo_id)
    return None


# ---------------------------------------------------------------------------
#  Tương thích: --sheet / SHEET_LINK / data\giam_sat_sheet.txt
# ---------------------------------------------------------------------------

def nhap_link_cu(db_path: str, link: str, *, schema_id: str, duong_dan_khoa: str,
                 workspace: str, worksheet_ten: str = TAB_MAC_DINH,
                 xac_thuc_ref: str = REF_MAC_DINH) -> DichGui:
    """Nhập một link Sheet kiểu cũ thành hồ sơ — idempotent (cùng bảng + định dạng + binding → cùng
    hồ sơ), trong MỘT giao dịch. Không lưu nguyên URL, tên hồ sơ không chứa mã bảng.

    Bản cũ LUÔN ghi vào tab tên «KetQuaQuet» (bỏ qua ``#gid=`` của link — gid đó thường là tab đầu
    "Sheet1"). Giữ đúng nghĩa đó: hồ sơ ghim theo TÊN, gid của link bị bỏ qua; mã tab thật được chốt ngay
    trước request ghi đầu tiên (``_chot_tab`` trong giao dịch SENDING của người gửi)."""
    sid, _gid_bo_qua = phan_tich_link(link)
    if schema_id not in SO_COT:
        raise LoiDichGui("Định dạng báo cáo phải là Ngang 34 cột hoặc Dọc 16 cột.")
    with ket_noi(db_path, ghi=True) as con:
        _dang_ky_xac_thuc(con, xac_thuc_ref, duong_dan_khoa, True)
        h = con.execute(
            _SQL_DICH + _HIEN_HANH + " AND d.nguon=? AND d.workspace=?"
            " AND d.trang_thai != ? AND r.spreadsheet_id=? AND r.worksheet_id IS NULL"
            " AND r.worksheet_ten=? AND r.schema_id=? AND r.xac_thuc_ref=?"
            " ORDER BY d.tao_luc LIMIT 1",
            (NGUON_LINK_CU, workspace, TT_LUU_TRU, sid, worksheet_ten, schema_id,
             xac_thuc_ref)).fetchone()
        if h is not None:
            return _dich_tu_hang(h)
        gt = dict(ten=f"Link cũ — {worksheet_ten} — {SCHEMA_NHAN[schema_id]}", spreadsheet_id=sid,
                  worksheet_id=None, worksheet_ten=worksheet_ten, schema_id=schema_id,
                  xac_thuc_ref=xac_thuc_ref)
        return _tao_dich(con, gt, workspace, NGUON_LINK_CU)
