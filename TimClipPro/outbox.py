# -*- coding: utf-8 -*-
"""Outbox gửi Google Sheets lưu bền — thay hàng đợi trong RAM (docs/MANAGED_RUNTIME_DESIGN.md §5).

Vì sao
======
Hàng đợi cũ (``sheet_delivery``) sống trong RAM: tắt app là mất việc chưa gửi, và mọi lỗi "có vẻ tạm"
(timeout, 5xx, reset…) đều được gửi lại — kể cả khi Google ĐÃ ghi mà phản hồi mất → trùng dòng
(tái hiện: ``repro/test_tai_hien_hang_doi_ram.py`` của vòng 07/10).

Hợp đồng
========
* Việc gửi (đích ĐÃ GHIM + payload đã dựng RAW) được chèn trong CÙNG giao dịch với lần quét
  (``Engine.save_job``) — commit xong mới gọi là "đã xếp hàng". Ý định trùng (cùng khoá) không tạo dòng.
* MỘT người gửi mỗi state root, giữ khoá HĐH ``data/hang_doi_gui.lock``. Claim là một ``UPDATE`` có
  điều kiện trạng thái, kèm ``claim_token`` làm fencing cho mọi lần cập nhật sau đó.
* ``SENDING`` được COMMIT ngay TRƯỚC request ghi. Lỗi chỉ được coi là "chắc chắn chưa ghi" khi xảy ra
  trước điểm đó, hoặc khi kiểu lỗi chứng minh request không tới/bị Google từ chối (transport phân loại
  theo KIỂU ngoại lệ, không theo chuỗi). Còn lại → ``UNKNOWN_DELIVERY``: không bao giờ gửi lại mù.
* Mã tab (gid) của revision được CHỐT — lần đầu thắng — trong CÙNG giao dịch với ``SENDING``, trước request
  ghi đầu tiên; chốt không được / mã đã chốt khác tab vừa tìm / mất claim → không gửi. Mọi lần gửi sau (thử
  lại, gửi lại sau UNKNOWN, khởi động lại, việc khác cùng revision) theo MÃ đó, không tìm lại theo tên; tab đã
  bị xoá → chặn, không bao giờ nhận tab mới cùng tên (MR-P1-02, audit độc lập f4d3cb7).
* Mã tab của TỪNG LẦN PHÁT (``gui_worksheet_id``) ghi cùng giao dịch đó. Việc đã phát mà không có mã của chính nó
  (bản cũ phát theo TÊN) không bao giờ được gửi lại: mã chốt của revision — có thể do việc KHÁC tạo SAU — không nói
  việc đó đã ghi vào đâu (MR-R2-P2-01, tái audit 78ba20c). Hồ sơ có mã: mã của hồ sơ.
* MỌI request chạm NỘI DUNG tab định tuyến bằng mã tab (``sheetId``), không theo tên: đọc hàng tiêu đề qua
  ``values:batchGetByDataFilter`` (``gridRange.sheetId``), ghi bằng MỘT ``spreadsheets.batchUpdate``
  ``AppendCells{sheetId}``. ``Worksheet.get_values``/``append_rows`` của gspread dựng range A1 từ TÊN tab, nên đổi
  tên/tạo tab trùng tên giữa lúc kiểm và lúc ghi từng làm dòng rơi sang tab khác mà vẫn SENT (MR-R2-P1-01, tái
  audit 78ba20c).
* Khởi động người gửi: ``CLAIMED`` (chưa dispatch) → ``PENDING``; ``SENDING`` của chủ cũ →
  ``UNKNOWN_DELIVERY`` (KHÔNG suy "chưa ghi" từ việc tiến trình đã chết).
* Lần ghi trạng thái SAU claim gặp lỗi DB (khoá quá hạn chờ, đĩa đầy…) trong tiến trình CÒN SỐNG: người gửi nhớ
  đúng lần ghi đó (``SENT`` với biên nhận đã kiểm, ``RETRY_WAIT``…; lỗi ngoài dự kiến trước dispatch → trả claim
  theo luật lỗi tạm) và ghi lại ở đầu vòng sau / trước khi nhả quyền, có fencing — không để việc kẹt ``CLAIMED`` /
  ``SENDING`` tới lần khởi động lại rồi biến lần ghi Google ĐÃ xác nhận thành ``UNKNOWN_DELIVERY`` (audit B-1).
* ``SENT`` chỉ khi biên nhận khớp: ``spreadsheetId`` máy chủ trả đúng bảng, ``replies`` đúng số request của lô
  NGUYÊN TỬ, và ``sheetId`` TRONG THÂN REQUEST đã phát = mã vừa chốt, dòng trong request = payload. Bất thường →
  ``UNKNOWN_DELIVERY``.
* Không mạng khi đang mở giao dịch; không khoá DB trong lúc chờ Google.

Không có exactly-once phía Google: ``UNKNOWN_DELIVERY`` là cơ chế xử lý mơ hồ — người dùng đối soát rồi
"Đã kiểm: đã có trên Sheet" hoặc "Gửi lại (có thể trùng)".
"""

from __future__ import annotations

import atexit
import contextlib
import hashlib
import json
import logging
import math
import os
import threading
import time
import uuid
from dataclasses import dataclass, replace
from typing import Callable, Optional

import maintenance_gate
import sheet_destinations as sd
from khoa import DangChayRoi, KhoaTienTrinh

LOGGER = logging.getLogger("scan.sheet.outbox")

PENDING = "PENDING"
RETRY_WAIT = "RETRY_WAIT"
CLAIMED = "CLAIMED"
SENDING = "SENDING"
SENT = "SENT"
BLOCKED_CONFIG = "BLOCKED_CONFIG"
BLOCKED_REPORT = "BLOCKED_REPORT"
UNKNOWN = "UNKNOWN_DELIVERY"
CANCELLED = "CANCELLED"
TAT_CA_TRANG_THAI = (PENDING, RETRY_WAIT, CLAIMED, SENDING, SENT, BLOCKED_CONFIG,
                     BLOCKED_REPORT, UNKNOWN, CANCELLED)
CO_THE_CLAIM = (PENDING, RETRY_WAIT)
DANG_BAY = (CLAIMED, SENDING)                    # đang trong tay một người gửi
NHAN_TRANG_THAI = {
    PENDING: "⏳ Chờ gửi", RETRY_WAIT: "🔁 Chờ thử lại", CLAIMED: "📤 Đang chuẩn bị",
    SENDING: "📤 Đang gửi", SENT: "✅ Đã gửi", BLOCKED_CONFIG: "⛔ Bị chặn (cấu hình)",
    BLOCKED_REPORT: "⛔ Bị chặn (báo cáo)", UNKNOWN: "❓ Không rõ đã gửi chưa",
    CANCELLED: "✖ Đã huỷ",
}

NGUON_AUTO = "auto"
NGUON_THU_CONG = "thu_cong"
SO_LAN_THU_TOI_DA = 8
TEN_KHOA_NGUOI_GUI = "hang_doi_gui.lock"
_KHOA_TAM_DUNG = "tam_dung_gui"


class LoiHangDoi(ValueError):
    """Thao tác của người dùng không hợp lệ với trạng thái hiện tại (thông báo tiếng Việt)."""


class ChuaGui(Exception):
    """CHẮC CHẮN Google chưa ghi. ``tam_thoi`` → thử lại có hạn mức; không → chặn tới khi sửa. ``chi_revision``:
    lỗi thuộc NHÃN của revision hồ sơ (tên đối chiếu), không thuộc bảng + tab + khoá + lược đồ → chỉ chặn việc chờ
    CÙNG revision; việc của revision khác cùng nhóm (người dùng đã sửa hồ sơ) không bị kéo theo (audit B-3)."""

    def __init__(self, ly_do: str, *, tam_thoi: bool, chi_revision: bool = False):
        super().__init__(ly_do)
        self.ly_do = ly_do
        self.tam_thoi = tam_thoi
        self.chi_revision = chi_revision


class KhongRo(Exception):
    """Request có thể đã tới Google mà kết quả không rõ — KHÔNG được gửi lại tự động."""

    def __init__(self, ly_do: str):
        super().__init__(ly_do)
        self.ly_do = ly_do


class MatQuyen(Exception):
    """Claim đã bị người khác lấy trước dispatch — bỏ lần gửi này, không ghi gì."""


@dataclass(frozen=True)
class KetQuaGui:
    """Transport trả về: phản hồi THÔ của ``spreadsheets.batchUpdate`` + ĐÚNG thân request ghi đã phát + tên tab lúc
    tìm. Mã tab và các dòng được đọc TỪ THÂN REQUEST (``appendCells.sheetId``/``rows``), không từ object local — mã
    cũ lấy ``ws.id`` local trong khi request ghi định tuyến theo TÊN (MR-R2-P1-01)."""

    phan_hoi: object
    yeu_cau: dict
    worksheet_ten: str


@dataclass(frozen=True)
class ViecGui:
    id: str
    job_id: Optional[int]
    lo_id: str
    nguon: str
    dich_id: str
    dich_phien_ban: int
    dich_json: str
    schema_id: str
    header_json: Optional[str]
    rows_json: Optional[str]
    so_dong: int
    payload_sha256: str
    trang_thai: str
    so_lan_thu: int
    thu_lai_sau: float
    loi: str
    bien_nhan: str
    da_xoa_job: int
    tao_luc: float
    sua_luc: float
    gui_luc: Optional[float]
    gui_worksheet_id: Optional[int]          # mã tab của LẦN PHÁT (v4); NULL + gui_luc = bản cũ phát, không ghi mã

    @property
    def dich(self) -> sd.DichGuiChot:
        return sd.DichGuiChot.from_json(self.dich_json)

    @property
    def header(self) -> Optional[list]:
        return None if self.header_json is None else json.loads(self.header_json)

    @property
    def rows(self) -> Optional[list]:
        return None if self.rows_json is None else json.loads(self.rows_json)


_COT_VIEC = ("id", "job_id", "lo_id", "nguon", "dich_id", "dich_phien_ban", "dich_json",
             "schema_id", "header_json", "rows_json", "so_dong", "payload_sha256", "trang_thai",
             "so_lan_thu", "thu_lai_sau", "loi", "bien_nhan", "da_xoa_job", "tao_luc", "sua_luc",
             "gui_luc", "gui_worksheet_id")


def _viec_tu_hang(h) -> ViecGui:
    return ViecGui(*[h[c] for c in _COT_VIEC])


def _bam_payload(header_json: str, rows_json: str) -> str:
    return hashlib.sha256((header_json + "\n" + rows_json).encode("utf-8")).hexdigest()


def khoa_trung(chot: sd.DichGuiChot, job_id: Optional[int], nguon: str, rieng: str = "") -> str:
    """Khoá chống trùng ỔN ĐỊNH qua khởi động lại: không gian cài đặt/workspace/job/đích/lược đồ."""
    tho = "|".join([nguon, chot.installation_id, chot.workspace, str(job_id), chot.dich_id,
                    str(chot.phien_ban), chot.schema_id, rieng])
    return hashlib.sha256(tho.encode("utf-8")).hexdigest()


def them_viec(con, y_dinh: sd.YDinhGui, *, job_id: Optional[int], chinh_sach: str,
              header: Optional[list], rows: Optional[list], trang_thai: str = PENDING,
              loi: str = "", nguon: str = NGUON_AUTO, khoa_rieng: str = "") -> Optional[str]:
    """Chèn một việc gửi bằng ``con`` của NGƯỜI GỌI (cùng giao dịch với lần quét). Payload được tuần
    tự hoá ngay — list của người gọi sửa sau đó không ảnh hưởng. Trùng khoá → ``None``."""
    from sheets import _o_sheets

    chot = y_dinh.dich
    header_json = rows_json = None
    so_dong, bam = 0, ""
    if header is not None and rows is not None:
        header_json = json.dumps([_o_sheets(v) for v in header], ensure_ascii=False,
                                 separators=(",", ":"))
        rows_json = json.dumps([[_o_sheets(v) for v in dong] for dong in rows],
                               ensure_ascii=False, separators=(",", ":"))
        so_dong, bam = len(rows), _bam_payload(header_json, rows_json)
    vid, luc = uuid.uuid4().hex, time.time()
    cur = con.execute(
        "INSERT INTO hang_doi_gui(id, dedupe_key, installation_id, workspace, job_id, lo_id, nguon,"
        " dich_id, dich_phien_ban, dich_json, schema_id, chinh_sach, header_json, rows_json,"
        " so_dong, payload_sha256, trang_thai, loi, tao_luc, sua_luc)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(dedupe_key) DO NOTHING",
        (vid, khoa_trung(chot, job_id, nguon, khoa_rieng), chot.installation_id, chot.workspace,
         job_id, y_dinh.lo_id, nguon, chot.dich_id, chot.phien_ban, chot.to_json(), chot.schema_id,
         chinh_sach, header_json, rows_json, so_dong, bam, trang_thai, loi, luc, luc))
    return vid if cur.rowcount == 1 else None


# ---------------------------------------------------------------------------
#  Đọc + thao tác người dùng
# ---------------------------------------------------------------------------

def lay_viec(db_path: str, viec_id: str) -> Optional[ViecGui]:
    with sd.ket_noi(db_path) as con:
        h = con.execute("SELECT * FROM hang_doi_gui WHERE id=?", (viec_id,)).fetchone()
    return None if h is None else _viec_tu_hang(h)


def ds_viec(db_path: str, *, trang_thai: Optional[tuple] = None, job_id: Optional[int] = None,
            lo_id: Optional[str] = None, gioi_han: int = 500) -> list:
    sql, tham = "SELECT * FROM hang_doi_gui WHERE 1=1", []
    if trang_thai:
        sql += f" AND trang_thai IN ({','.join('?' * len(trang_thai))})"
        tham += list(trang_thai)
    if job_id is not None:
        sql += " AND job_id=?"
        tham.append(job_id)
    if lo_id is not None:
        sql += " AND lo_id=?"
        tham.append(lo_id)
    with sd.ket_noi(db_path) as con:
        return [_viec_tu_hang(h) for h in con.execute(
            sql + " ORDER BY tao_luc DESC, id LIMIT ?", (*tham, int(gioi_han)))]


def tom_tat(db_path: str, *, lo_id: Optional[str] = None) -> dict:
    sql, tham = "SELECT trang_thai, COUNT(*) FROM hang_doi_gui", ()
    if lo_id is not None:
        sql, tham = sql + " WHERE lo_id=?", (lo_id,)
    kq = dict.fromkeys(TAT_CA_TRANG_THAI, 0)
    with sd.ket_noi(db_path) as con:
        for tt, n in con.execute(sql + " GROUP BY trang_thai", tham):
            kq[tt] = n
    return kq


def _doi_trang_thai_tay(db_path: str, viec_id: str, tu: tuple, den: str, *,
                        kiem: Optional[Callable] = None, **them) -> None:
    with sd.ket_noi(db_path, ghi=True) as con:
        h = con.execute("SELECT * FROM hang_doi_gui WHERE id=?", (viec_id,)).fetchone()
        if h is None:
            raise LoiHangDoi("Không thấy việc gửi này.")
        if h["trang_thai"] not in tu:
            raise LoiHangDoi(f"Việc đang ở trạng thái «{NHAN_TRANG_THAI.get(h['trang_thai'])}» — "
                             "không làm được thao tác này.")
        if kiem is not None:
            kiem(con, _viec_tu_hang(h))
        cot = {"trang_thai": den, "sua_luc": time.time(), "claim_token": "", "chu_so_huu": "",
               **them}
        con.execute(f"UPDATE hang_doi_gui SET {', '.join(f'{k}=?' for k in cot)} WHERE id=?",
                    (*cot.values(), viec_id))


def thu_lai(db_path: str, viec_id: str) -> None:
    """Sau khi đã sửa bảng/khoá: đưa việc bị chặn (cấu hình) hoặc đang chờ về hàng đợi ngay."""
    _doi_trang_thai_tay(db_path, viec_id, (BLOCKED_CONFIG, RETRY_WAIT), PENDING,
                        so_lan_thu=0, thu_lai_sau=0.0, loi="")


def xac_nhan_da_gui(db_path: str, viec_id: str, ghi_chu: str = "") -> None:
    """UNKNOWN → SENT do người dùng đã đối soát thấy dòng trên Sheet."""
    _doi_trang_thai_tay(db_path, viec_id, (UNKNOWN,), SENT, bien_nhan=json.dumps(
        {"xac_nhan_tay": True, "ghi_chu": str(ghi_chu)[:300], "luc": time.time()},
        ensure_ascii=False))


def gui_lai_co_the_trung(db_path: str, viec_id: str) -> None:
    """UNKNOWN → PENDING theo xác nhận của người dùng: chấp nhận khả năng TRÙNG dòng — không phải ĐỔI tab: gửi lại
    luôn vào mã tab đã chốt; việc của bản cũ đã phát mà chưa có mã tab thì từ chối (``ly_do_khong_gui_lai``)."""
    _doi_trang_thai_tay(db_path, viec_id, (UNKNOWN,), PENDING, kiem=_kiem_gui_lai, so_lan_thu=0,
                        thu_lai_sau=0.0, loi="Gửi lại theo xác nhận của người dùng (có thể trùng dòng).")


LY_DO_BAN_CU_CHUA_CO_MA_TAB = (
    "Việc này đã được phát đi (bởi bản cũ) mà chưa ghi mã tab của chính lần phát — mã tab hồ sơ chốt SAU đó (có "
    "thể do việc khác) không cho biết việc này đã ghi vào đâu, còn gửi lại theo TÊN tab có thể rơi vào tab khác "
    "cùng tên, nên tool không gửi lại. Mở Sheet kiểm: đã có dòng thì bấm «Đã có trên Sheet»; chưa có thì huỷ "
    "việc này rồi dùng «Gửi thêm (thủ công)».")


def _ma_tab_da_phat(v: ViecGui, chot: sd.DichGuiChot) -> Optional[int]:
    """Mã tab mà việc ĐÃ phát request tới: mã ghi theo việc (cùng giao dịch SENDING, lược đồ v4); việc của bản cũ
    theo hồ sơ CÓ MÃ thì là mã hồ sơ (bản cũ cũng tìm tab theo mã đó). ``None`` = chưa phát, hoặc bản cũ phát theo
    TÊN mà không ghi mã — không biết đã ghi vào tab nào."""
    if v.gui_luc is None:
        return None
    return v.gui_worksheet_id if v.gui_worksheet_id is not None else chot.worksheet_id


def _ly_do_chan_tab(v: ViecGui, chot: sd.DichGuiChot, da_chot: Optional[sd.TabDaChot]) -> str:
    """Lý do KHÔNG được phát request cho việc này theo đích đã ghim (rỗng = được). Việc đã từng phát (``gui_luc``)
    chỉ được gửi lại vào ĐÚNG mã tab của lần phát đó — không bao giờ đoán mã từ tên, và mã chốt của revision (có
    thể do việc KHÁC tạo SAU) không thay được mã của chính việc (MR-P1-02, MR-R2-P2-01)."""
    if chot.worksheet_id is not None and da_chot is not None and da_chot.worksheet_id != chot.worksheet_id:
        return (f"Mã tab đã chốt ({da_chot.worksheet_id}) khác mã tab của hồ sơ đã ghim ({chot.worksheet_id}) — "
                "không gửi; kiểm lại hồ sơ.")
    if v.gui_luc is not None:
        da_phat = _ma_tab_da_phat(v, chot)
        if da_phat is None:
            return LY_DO_BAN_CU_CHUA_CO_MA_TAB
        if da_chot is not None and da_chot.worksheet_id != da_phat:
            return (f"Việc này đã phát tới tab mã {da_phat}, khác mã tab đã chốt của hồ sơ ({da_chot.worksheet_id}) "
                    "— không gửi lại; đối soát trên Sheet.")
    return ""


def _kiem_gui_lai(con, v: ViecGui) -> None:
    try:
        chot = v.dich
    except sd.LoiDichGui:
        return                       # đích ghim hỏng: người gửi tự chặn việc đó (không đoán lại đích)
    ly_do = _ly_do_chan_tab(v, chot, sd._tab_da_chot(con, chot.dich_id, chot.phien_ban))
    if ly_do:
        raise LoiHangDoi(ly_do)


def tab_da_ghim(db_path: str, v: ViecGui) -> Optional[sd.TabDaChot]:
    """Tab việc này ĐÃ/SẼ ghi vào — để đối soát việc KHÔNG RÕ. Đã phát: mã của CHÍNH lần phát (không phải mã chốt
    của revision — có thể do việc khác chốt sau); ``None`` = bản cũ phát theo tên, không biết tab nào. Chưa phát:
    mã chốt của revision, không thì mã của hồ sơ; ``None`` = hồ sơ theo tên chưa từng phát (hoặc đích ghim hỏng)."""
    try:
        chot = v.dich
    except sd.LoiDichGui:
        return None
    tc = sd.tab_da_chot(db_path, chot.dich_id, chot.phien_ban)
    if v.gui_luc is not None:
        da_phat = _ma_tab_da_phat(v, chot)
        if da_phat is None:
            return None
        return tc if tc is not None and tc.worksheet_id == da_phat else sd.TabDaChot(da_phat, chot.worksheet_ten)
    if tc is not None:
        return tc
    return None if chot.worksheet_id is None else sd.TabDaChot(chot.worksheet_id, chot.worksheet_ten)


def ly_do_khong_gui_lai(db_path: str, v: ViecGui) -> str:
    """Rỗng = được «Gửi lại (có thể trùng)» (giao diện khoá nút theo đây; thao tác gửi lại kiểm lại trong giao
    dịch)."""
    try:
        chot = v.dich
    except sd.LoiDichGui:
        return ""
    return _ly_do_chan_tab(v, chot, sd.tab_da_chot(db_path, chot.dich_id, chot.phien_ban))


def huy(db_path: str, viec_id: str) -> None:
    """Huỷ việc CHƯA phát request (thiết kế §5: CANCELLED = chưa SENDING). Đang gửi/đã gửi thì không huỷ được.
    ``CLAIMED`` huỷ được (audit B-1): huỷ xoá ``claim_token`` nên người gửi đang cầm việc không qua được bước
    CLAIMED→SENDING có fencing (``_bat_dau_gui`` → ``MatQuyen``, rollback) — không request nào được phát."""
    _doi_trang_thai_tay(db_path, viec_id,
                        (PENDING, RETRY_WAIT, CLAIMED, BLOCKED_CONFIG, BLOCKED_REPORT, UNKNOWN), CANCELLED)


def kiem_khoa_cuc_bo(db_path: str, chot: sd.DichGuiChot) -> str:
    """Lý do KHÔNG dùng được binding khoá của đích (rỗng = ổn). Chỉ đọc file khoá local — dùng ở
    preflight lúc bấm Bắt đầu (báo trước khi quét) và ngay trước mỗi lần gửi."""
    xt = sd.lay_xac_thuc(db_path, chot.xac_thuc_ref)
    if xt is None or xt.trang_thai != sd.TT_HOAT_DONG:
        return f"Binding khoá «{chot.xac_thuc_ref}» không còn hoạt động."
    try:
        principal, kid = sd.doc_khoa_dich_vu(xt.duong_dan)
    except sd.LoiDichGui as e:
        return str(e)
    if principal != chot.principal:
        return ("File khoá hiện tại thuộc một tài khoản dịch vụ khác với lúc ghim — không gửi "
                "bằng tài khoản khác; kiểm lại khoá.")
    if kid != chot.key_id and not chot.cho_xoay_khoa:
        return "Khoá đã được xoay nhưng hồ sơ không cho phép dùng khoá mới."
    return ""


def tao_viec_thu_cong(db_path: str, y_dinh: sd.YDinhGui, job_id: int, header: list, rows: list,
                      *, chinh_sach: str, cho_phep_trung: bool = False) -> str:
    """«Gửi thêm một bản» do người dùng chủ động: ý định MỚI (khoá riêng), không thay việc cũ.
    Lần quét đã có việc gửi (chưa huỷ) tới cùng hồ sơ → phải xác nhận ``cho_phep_trung``."""
    with sd.ket_noi(db_path, ghi=True) as con:
        da_co = con.execute("SELECT * FROM hang_doi_gui WHERE job_id=? AND trang_thai != ?",
                            (job_id, CANCELLED)).fetchall()
        if not cho_phep_trung and any(_co_the_cung_tab(con, _viec_tu_hang(h), y_dinh.dich) for h in da_co):
            raise LoiHangDoi(f"Lần quét #{job_id} đã có việc gửi tới cùng bảng/tab với «{y_dinh.dich.ten}» "
                             "— gửi thêm sẽ tạo dòng TRÙNG trên Sheet; hãy xác nhận nếu vẫn muốn gửi.")
        vid = them_viec(con, y_dinh, job_id=job_id, chinh_sach=chinh_sach, header=header,
                        rows=rows, nguon=NGUON_THU_CONG, khoa_rieng=uuid.uuid4().hex)
    danh_thuc(db_path)
    return vid


def _khoa_tab(con, chot: sd.DichGuiChot):
    """Định danh tab của một đích ghim: mã đã chốt của revision, mã ghim, hoặc ``None`` (theo tên)."""
    if chot.worksheet_id is not None:
        return chot.worksheet_id
    h = con.execute("SELECT worksheet_id FROM dich_gui_tab_chot WHERE dich_id=? AND phien_ban=?",
                    (chot.dich_id, chot.phien_ban)).fetchone()
    return None if h is None else int(h["worksheet_id"])


def _co_the_cung_tab(con, v: ViecGui, moi: sd.DichGuiChot) -> bool:
    """Việc đã có ``v`` CÓ THỂ ghi vào cùng tab với đích ``moi``? Không chắc → coi là có. Việc đã phát: theo mã của
    CHÍNH lần phát; bản cũ phát theo tên (không mã) → không biết → có thể."""
    try:
        cu = v.dich
    except sd.LoiDichGui:
        return True
    if cu.spreadsheet_id != moi.spreadsheet_id:
        return False
    if v.gui_luc is not None and _ma_tab_da_phat(v, cu) is None:
        return True
    a = _ma_tab_da_phat(v, cu) if v.gui_luc is not None else _khoa_tab(con, cu)
    b = _khoa_tab(con, moi)
    if a is not None and b is not None:
        return a == b
    if a is None and b is None:
        return cu.worksheet_ten == moi.worksheet_ten
    return True              # một bên theo mã, một bên theo tên chưa chốt: có thể là cùng tab


def dat_tam_dung(db_path: str, bat: bool) -> None:
    """Tạm dừng TOÀN BỘ việc gửi (quét vẫn chạy, việc vẫn xếp hàng, không đổi đích)."""
    with sd.ket_noi(db_path, ghi=True) as con:
        con.execute("INSERT INTO cai_dat_may(khoa, gia_tri) VALUES(?, ?) ON CONFLICT(khoa)"
                    " DO UPDATE SET gia_tri=excluded.gia_tri", (_KHOA_TAM_DUNG, "1" if bat else "0"))


def dang_tam_dung(db_path: str) -> bool:
    with sd.ket_noi(db_path) as con:
        h = con.execute("SELECT gia_tri FROM cai_dat_may WHERE khoa=?", (_KHOA_TAM_DUNG,)).fetchone()
    return h is not None and h["gia_tri"] == "1"


def ly_do_tam_dung(db_path: str, lo_id: str) -> str:
    """Việc còn chờ của lượt ``lo_id`` chỉ chờ vì TẠM DỪNG — người gửi chắc chắn không nhận cho tới
    khi người dùng bật lại (audit B-5): ``"toan_bo"`` (tạm dừng toàn bộ), ``"ho_so"`` (mọi việc chờ
    thuộc hồ sơ đang tạm dừng); ``""`` khi không có việc chờ, còn việc đang bay (CLAIMED/SENDING —
    vẫn đi tới kết cục) hoặc còn việc người gửi sẽ nhận."""
    with sd.ket_noi(db_path) as con:
        dem = dict(con.execute(
            "SELECT trang_thai, COUNT(*) FROM hang_doi_gui WHERE lo_id=? AND trang_thai IN (?,?,?,?)"
            " GROUP BY trang_thai", (lo_id, CLAIMED, SENDING, *CO_THE_CLAIM)).fetchall())
        if dem.get(CLAIMED, 0) + dem.get(SENDING, 0) or not any(dem.get(t, 0) for t in CO_THE_CLAIM):
            return ""
        con_nhan = con.execute(
            "SELECT 1 FROM hang_doi_gui WHERE lo_id=? AND trang_thai IN (?,?)"
            " AND dich_id NOT IN (SELECT id FROM dich_gui WHERE trang_thai=?) LIMIT 1",
            (lo_id, *CO_THE_CLAIM, sd.TT_TAM_DUNG)).fetchone()
    if dang_tam_dung(db_path):
        return "toan_bo"
    return "" if con_nhan else "ho_so"


# ---------------------------------------------------------------------------
#  Người gửi
# ---------------------------------------------------------------------------

def _thoi_gian_cho(so_lan: int) -> float:
    return float(min(60 * 2 ** max(0, so_lan - 1), 3600))


def _nhom(chot: sd.DichGuiChot) -> tuple:
    """Các việc cùng bảng + tab + khoá + lược đồ: lỗi cấu hình của một việc là của cả nhóm."""
    return (chot.spreadsheet_id, chot.worksheet_id if chot.worksheet_id is not None
            else "ten:" + chot.worksheet_ten, chot.xac_thuc_ref, chot.schema_id)


def dung_o(gia_tri) -> dict:
    """MỘT ô của ``AppendCells`` (``fields: userEnteredValue``) tương đương ``values.append`` RAW: chuỗi →
    ``stringValue`` (KHÔNG BAO GIỜ phân tích công thức, kể cả chuỗi bắt đầu bằng ``=``), số → ``numberValue``,
    bool → ``boolValue``, ``""``/``None`` → ô trống (RAW: chuỗi rỗng đặt ô trống, null bỏ qua). Số không hữu hạn
    (JSON không có NaN/vô cực) → ``ValueError``; kiểu khác → ``TypeError``."""
    if gia_tri is None or (isinstance(gia_tri, str) and gia_tri == ""):
        return {}
    if isinstance(gia_tri, bool):
        return {"userEnteredValue": {"boolValue": gia_tri}}
    if isinstance(gia_tri, (int, float)):
        if isinstance(gia_tri, float) and not math.isfinite(gia_tri):
            raise ValueError("ô số không hữu hạn (NaN/vô cực)")
        return {"userEnteredValue": {"numberValue": gia_tri}}
    if isinstance(gia_tri, str):
        return {"userEnteredValue": {"stringValue": gia_tri}}
    raise TypeError(f"kiểu ô không gửi được: {type(gia_tri).__name__}")


def dung_yeu_cau_ghi(gid: int, gia_tri: list, so_cot_hien_co: Optional[int] = None) -> dict:
    """Thân ``spreadsheets.batchUpdate`` DUY NHẤT của một lần gửi — định tuyến bằng MÃ tab, không mang tên tab nào:
    [``AppendDimension`` cột khi tab hẹp hơn dòng dài nhất — tài liệu AppendCells không hứa tự nới cột như
    ``values.append``] + ``AppendCells`` (thêm sau dòng cuối có dữ liệu). Cả lô nguyên tử: hoặc áp hết, hoặc không."""
    yeu_cau = []
    rong = max((len(dong) for dong in gia_tri), default=0)
    if so_cot_hien_co is not None and rong > so_cot_hien_co:
        yeu_cau.append({"appendDimension": {"sheetId": gid, "dimension": "COLUMNS",
                                            "length": rong - so_cot_hien_co}})
    yeu_cau.append({"appendCells": {"sheetId": gid, "fields": "userEnteredValue",
                                    "rows": [{"values": [dung_o(x) for x in dong]} for dong in gia_tri]}})
    return {"requests": yeu_cau}


def _phan_tich_yeu_cau(yeu_cau) -> tuple:
    """``(mã_tab, các_dòng, số_request)`` của thân request ghi — CHỈ nhận đúng dạng ``dung_yeu_cau_ghi`` dựng:
    [AppendDimension(COLUMNS) cùng mã] + MỘT AppendCells{sheetId, userEnteredValue} cuối. Khác → ``ValueError``."""
    ds = yeu_cau.get("requests") if isinstance(yeu_cau, dict) else None
    if not isinstance(ds, list) or not ds or not all(isinstance(r, dict) and len(r) == 1 for r in ds):
        raise ValueError("thân request ghi không đúng dạng batchUpdate")
    ac = ds[-1].get("appendCells")
    gid = ac.get("sheetId") if isinstance(ac, dict) else None
    if (not isinstance(gid, int) or isinstance(gid, bool) or set(ac) != {"sheetId", "fields", "rows"}
            or ac["fields"] != "userEnteredValue" or not isinstance(ac["rows"], list)):
        raise ValueError("request ghi cuối không phải AppendCells theo mã tab")
    for r in ds[:-1]:
        ad = r.get("appendDimension")
        if not (isinstance(ad, dict) and set(ad) == {"sheetId", "dimension", "length"} and ad["sheetId"] == gid
                and ad["dimension"] == "COLUMNS" and isinstance(ad["length"], int) and ad["length"] > 0):
            raise ValueError("thân request ghi có request ngoài hợp đồng")
    return gid, ac["rows"], len(ds)


def _dong_khop_payload(dong: list, header: Optional[list], rows: list) -> bool:
    """Các dòng trong request = đúng payload của việc (có thể kèm hàng tiêu đề đầu khi trang tính trống)."""
    try:
        than = [{"values": [dung_o(x) for x in r]} for r in rows]
        return dong == than or (header is not None and dong == [{"values": [dung_o(x) for x in header]}] + than)
    except (TypeError, ValueError):
        return False


def kiem_bien_nhan(kq: KetQuaGui, chot: sd.DichGuiChot, *, header: Optional[list] = None,
                   rows: Optional[list] = None) -> tuple:
    """``(hợp_lệ, lý_do, biên_nhận_dict)``.

    ``spreadsheets.batchUpdate`` là NGUYÊN TỬ: phản hồi THÀNH CÔNG mang đúng ``spreadsheetId`` và đúng số
    ``replies`` = Google đã áp dụng TOÀN BỘ thân request — mà thân request định tuyến bằng ``appendCells.sheetId``.
    Hợp lệ chỉ khi mã tab TRONG THÂN REQUEST = mã đã chốt (``chot.worksheet_id``) và dòng trong request đúng payload.
    Google KHÔNG trả vùng ghi/số dòng cho AppendCells: biên nhận ghi rõ phần nào máy chủ xác nhận, phần nào lấy từ
    request — không dựng ``updatedRange``/``updatedRows`` giả."""
    try:
        gid, dong, so_yeu_cau = _phan_tich_yeu_cau(kq.yeu_cau)
    except ValueError as e:
        return False, str(e), {}
    ph = kq.phan_hoi
    if not isinstance(ph, dict):
        return False, "phản hồi không phải đối tượng JSON", {}
    if ph.get("spreadsheetId") != chot.spreadsheet_id:
        return False, "phản hồi mang mã bảng khác", {}
    tra_loi = ph.get("replies")
    if not isinstance(tra_loi, list) or len(tra_loi) != so_yeu_cau:
        return False, (f"phản hồi có {len(tra_loi) if isinstance(tra_loi, list) else 'không có'} reply, đã gửi "
                       f"{so_yeu_cau} request"), {}
    if chot.worksheet_id is None or gid != chot.worksheet_id:
        return False, "request đã ghi vào mã tab khác mã đã chốt", {}
    if rows is not None and not _dong_khop_payload(dong, header, rows):
        return False, "dòng trong request khác dữ liệu của việc", {}
    return True, "", {"kieu": "batchUpdate.appendCells", "spreadsheet_id": ph["spreadsheetId"],
                      "so_reply": len(tra_loi), "worksheet_id": gid, "worksheet_ten": kq.worksheet_ten,
                      "so_dong_gui": len(dong), "luc": time.time(),
                      "may_chu_xac_nhan": "spreadsheetId + replies của batchUpdate nguyên tử; mã tab và số dòng "
                                          "lấy từ thân request đã phát (AppendCells không trả vùng ghi)"}


class NguoiGui:
    """Người gửi DUY NHẤT của một state root (giữ ``data/hang_doi_gui.lock``)."""

    def __init__(self, db_path: str, data_dir: str, cong, *, dong_ho: Callable = time.time,
                 so_lan_toi_da: int = SO_LAN_THU_TOI_DA, moi_vong: int = 20,
                 dung: Optional[threading.Event] = None, cong_bao_tri=None):
        self.db_path = db_path
        self.data_dir = data_dir
        self.cong = cong
        # Mỗi lần gửi giữ một lease của cổng bảo trì: updater đang rút → không claim việc mới; việc đang
        # bay → updater chờ nó xong (không đổi mã giữa một request).
        self.cong_bao_tri = (cong_bao_tri if cong_bao_tri is not None
                             else maintenance_gate.CongBaoTri(data_dir))
        self.dong_ho = dong_ho
        self.so_lan_toi_da = max(1, int(so_lan_toi_da))
        self.moi_vong = max(1, int(moi_vong))
        self.dung = dung or threading.Event()
        self.chu = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._khoa: Optional[KhoaTienTrinh] = None
        # Lần ghi trạng thái sau claim chưa vào được DB (lỗi DB) — {viec_id: hàm ghi lại có fencing} (audit B-1).
        self._ghi_treo: dict = {}

    # ---------- quyền ----------

    def nhan_quyen(self) -> bool:
        """Giành quyền người gửi (không chờ). Được quyền → phục hồi các việc dở của chủ cũ."""
        if self._khoa is not None:
            return True
        khoa = KhoaTienTrinh(os.path.join(self.data_dir, TEN_KHOA_NGUOI_GUI),
                             "người gửi Google Sheets")
        try:
            khoa.__enter__()
        except DangChayRoi:
            return False
        self._khoa = khoa
        try:
            self.ghi_lai_treo()       # lần ghi dở của CHÍNH người gửi này trước phục hồi (SENT không thành KHÔNG RÕ)
            self.phuc_hoi()
        except BaseException:
            self.tha_quyen()
            raise
        return True

    def tha_quyen(self) -> None:
        if self._khoa is not None and self._ghi_treo:
            try:
                self.ghi_lai_treo()
            except Exception:  # noqa: BLE001 — vẫn nhả quyền; người giành quyền kế phục hồi như cũ
                LOGGER.exception("event=outbox.pending_final_write_failed")
        khoa, self._khoa = self._khoa, None
        if khoa is not None:
            khoa.__exit__(None, None, None)

    @property
    def co_quyen(self) -> bool:
        return self._khoa is not None

    def phuc_hoi(self) -> dict:
        """Chỉ chạy khi đang giữ khoá (không người gửi nào khác còn sống)."""
        luc = time.time()
        with sd.ket_noi(self.db_path, ghi=True) as con:
            ve_cho = con.execute(
                "UPDATE hang_doi_gui SET trang_thai=?, claim_token='', chu_so_huu='', sua_luc=?"
                " WHERE trang_thai=?", (PENDING, luc, CLAIMED)).rowcount
            khong_ro = con.execute(
                "UPDATE hang_doi_gui SET trang_thai=?, loi=?, sua_luc=? WHERE trang_thai=?",
                (UNKNOWN, "Tiến trình gửi trước đã dừng (khởi động lại/mất điện) khi request đang đi"
                 " — không rõ Google đã ghi chưa; hãy đối soát trên Sheet.", luc, SENDING)).rowcount
        if ve_cho or khong_ro:
            LOGGER.warning("event=outbox.recovered claimed_to_pending=%d sending_to_unknown=%d",
                           ve_cho, khong_ro)
        return {"ve_cho": ve_cho, "khong_ro": khong_ro}

    def ghi_lai_treo(self) -> None:
        """Ghi lại các lần chốt trạng thái sau claim từng gặp lỗi DB (khoá quá hạn chờ, đĩa đầy…) — có fencing
        ``claim_token`` + trạng thái đang bay, nên việc đã bị huỷ / đã được phục hồi thì không đụng. Lỗi DB lần
        nữa → ngoại lệ thoát ra (vòng gửi log ``round_failed``), giữ lại để lần sau thử tiếp."""
        for viec_id, ghi in list(self._ghi_treo.items()):
            n = ghi()
            del self._ghi_treo[viec_id]
            LOGGER.warning("event=outbox.pending_final_write id=%s applied=%d", viec_id[:12], n)

    # ---------- vòng gửi ----------

    def chay_mot_vong(self) -> dict:
        if self._khoa is None:
            raise RuntimeError("Chưa giữ quyền người gửi — không được gửi.")
        self.ghi_lai_treo()
        dem = dict(da_gui=0, thu_lai=0, bi_chan=0, khong_ro=0, bo_qua=0, tam_dung=0)
        if dang_tam_dung(self.db_path):
            dem["tam_dung"] = 1
            return dem
        bay_gio = self.dong_ho()
        # Hồ sơ tạm dừng bị loại NGAY trong truy vấn, nhóm đang hoãn đã có `thu_lai_sau` ở tương lai:
        # một hồ sơ/nhóm có hàng trăm việc chờ không chiếm hết suất của vòng (không bỏ đói hồ sơ khác).
        with sd.ket_noi(self.db_path) as con:
            ung_vien = con.execute(
                "SELECT id, dich_id, dich_json FROM hang_doi_gui WHERE trang_thai IN (?,?)"
                " AND thu_lai_sau <= ? AND dich_id NOT IN (SELECT id FROM dich_gui WHERE trang_thai=?)"
                " ORDER BY thu_lai_sau, tao_luc LIMIT ?",
                (*CO_THE_CLAIM, bay_gio, sd.TT_TAM_DUNG, self.moi_vong)).fetchall()
        bi_chan_vong: set = set()
        for h in ung_vien:
            if self.dung.is_set():
                break
            try:
                nhom = _nhom(sd.DichGuiChot.from_json(h["dich_json"]))
            except sd.LoiDichGui:
                nhom = None
            if nhom is not None and nhom in bi_chan_vong:
                dem["bo_qua"] += 1
                continue
            try:
                lease = self.cong_bao_tri.nhan_viec("gửi Google Sheets")
            except maintenance_gate.BanCu:
                dem["ban_cu"] = 1                    # bản này đã bị thay: chưa claim gì, nhường quyền
                break
            except (DangChayRoi, maintenance_gate.LoiCong):
                dem["tam_dung"] = 1                  # đang rút cổng (cập nhật): chưa claim gì, chờ
                break
            try:
                ket = self._xu_ly(h["id"], nhom, bay_gio)
            finally:
                lease.tra()
            if ket == "tam_dung":
                dem["tam_dung"] = 1                  # tạm dừng toàn bộ giữa vòng: dừng vòng, không claim thêm
                break
            dem[ket] = dem.get(ket, 0) + 1
            if ket == "bi_chan" and nhom is not None:
                bi_chan_vong.add(nhom)
        return dem

    def _claim(self, viec_id: str, bay_gio: float) -> Optional[str]:
        """Tạm dừng (toàn bộ / hồ sơ) được kiểm NGAY trong lệnh claim, không chỉ lúc chọn ứng viên đầu vòng: tạm dừng
        đã ghi trước lần claim thì việc chưa claim ở nguyên chờ gửi (audit F-15). Việc đã claim vẫn đi tới kết cục."""
        token = uuid.uuid4().hex
        with sd.ket_noi(self.db_path, ghi=True) as con:
            n = con.execute(
                "UPDATE hang_doi_gui SET trang_thai=?, claim_token=?, chu_so_huu=?, claim_luc=?,"
                " so_lan_thu=so_lan_thu+1, sua_luc=? WHERE id=? AND trang_thai IN (?,?)"
                " AND thu_lai_sau <= ?"
                " AND NOT EXISTS (SELECT 1 FROM cai_dat_may WHERE khoa=? AND gia_tri='1')"
                " AND dich_id NOT IN (SELECT id FROM dich_gui WHERE trang_thai=?)",
                (CLAIMED, token, self.chu, bay_gio, time.time(), viec_id, *CO_THE_CLAIM,
                 bay_gio, _KHOA_TAM_DUNG, sd.TT_TAM_DUNG)).rowcount
        return token if n == 1 else None

    def _chot(self, viec_id: str, token: str, trang_thai: str, **cot) -> bool:
        """Cập nhật cuối có fencing: chỉ khi claim vẫn là của mình. Lỗi DB → nhớ lần ghi này để ghi lại
        (``ghi_lai_treo``) rồi ném tiếp."""
        try:
            n = self._ghi_chot(viec_id, token, trang_thai, cot)
        except Exception:
            self._ghi_treo[viec_id] = lambda: self._ghi_chot(viec_id, token, trang_thai, cot)
            raise
        if n != 1:
            LOGGER.error("event=outbox.fencing_lost id=%s state=%s", viec_id[:12], trang_thai)
        return n == 1

    def _ghi_chot(self, viec_id: str, token: str, trang_thai: str, cot: dict) -> int:
        gia_tri = {"trang_thai": trang_thai, "sua_luc": time.time(), **cot}
        if trang_thai not in DANG_BAY:
            gia_tri.update(claim_token="", chu_so_huu="")
        with sd.ket_noi(self.db_path, ghi=True) as con:
            return con.execute(
                f"UPDATE hang_doi_gui SET {', '.join(f'{k}=?' for k in gia_tri)}"
                " WHERE id=? AND claim_token=? AND trang_thai IN (?,?)",
                (*gia_tri.values(), viec_id, token, *DANG_BAY)).rowcount

    def _tra_claim(self, viec_id: str, token: str, ly_do: str, bay_gio: float) -> int:
        """Lỗi ngoài dự kiến TRƯỚC dispatch (việc vẫn ``CLAIMED``): trả claim theo luật lỗi tạm — ``RETRY_WAIT``
        có hạn chờ, quá số lần → ``BLOCKED_CONFIG``. Chỉ từ ``CLAIMED`` của chính mình: không bao giờ
        ``SENDING`` → chờ gửi."""
        with sd.ket_noi(self.db_path, ghi=True) as con:
            h = con.execute("SELECT so_lan_thu FROM hang_doi_gui WHERE id=? AND claim_token=? AND trang_thai=?",
                            (viec_id, token, CLAIMED)).fetchone()
            if h is None:
                return 0
            so_lan = int(h["so_lan_thu"])
            if so_lan >= self.so_lan_toi_da:
                tt, loi, sau = (BLOCKED_CONFIG,
                                f"{ly_do} — quá số lần thử ({so_lan}); bấm «Thử gửi lại» khi đã ổn.", bay_gio)
            else:
                tt, loi, sau = RETRY_WAIT, ly_do, bay_gio + _thoi_gian_cho(so_lan)
            return con.execute(
                "UPDATE hang_doi_gui SET trang_thai=?, loi=?, thu_lai_sau=?, claim_token='', chu_so_huu='',"
                " sua_luc=? WHERE id=? AND claim_token=? AND trang_thai=?",
                (tt, loi, sau, time.time(), viec_id, token, CLAIMED)).rowcount

    def _bat_dau_gui(self, viec_id: str, token: str, chot: sd.DichGuiChot, gid: int, ten: str) -> None:
        """Điểm không quay lại — MỘT giao dịch: chốt mã tab ``gid`` cho revision (lần đầu thắng) rồi COMMIT
        ``SENDING`` + ``gui_worksheet_id`` = ``gid`` của CHÍNH việc (fencing ``claim_token``); xong transport mới
        được phát request ghi. Tab vừa tìm khác mã đã ghim / đã chốt / mã của lần phát trước, chốt lỗi, hay mất
        claim → rollback cả giao dịch, KHÔNG phát request (MR-P1-02: chốt sau SENT thì UNKNOWN/lỗi chốt làm lần
        gửi sau tìm lại theo TÊN và có thể rơi vào tab mới cùng tên; MR-R2-P2-01: mã của lần phát là bất biến)."""
        if chot.worksheet_id is not None and gid != chot.worksheet_id:
            raise ChuaGui(f"Tab tìm được (mã {gid}) khác mã tab đã ghim ({chot.worksheet_id}) — chưa ghi gì.",
                          tam_thoi=False)
        with sd.ket_noi(self.db_path, ghi=True) as con:
            h = con.execute("SELECT gui_worksheet_id FROM hang_doi_gui WHERE id=?", (viec_id,)).fetchone()
            if h is not None and h["gui_worksheet_id"] is not None and int(h["gui_worksheet_id"]) != gid:
                # Mã của LẦN PHÁT TRƯỚC là bất biến — kể cả khi mã chốt của revision đã mất (DB sửa/khôi phục lệch).
                raise ChuaGui(f"Tab tìm được (mã {gid}) khác mã tab lần phát trước của việc này "
                              f"({h['gui_worksheet_id']}) — chưa ghi gì.", tam_thoi=False)
            tc = sd._chot_tab(con, chot.dich_id, chot.phien_ban, worksheet_id=gid, worksheet_ten=ten)
            if tc.worksheet_id != gid:
                raise ChuaGui(f"Tab tìm được (mã {gid}) khác mã tab đã chốt của hồ sơ ({tc.worksheet_id}) — chưa ghi "
                              "gì; lần sau gửi theo mã đã chốt.", tam_thoi=True)
            n = con.execute(
                "UPDATE hang_doi_gui SET trang_thai=?, gui_luc=?, gui_worksheet_id=?, sua_luc=? WHERE id=?"
                " AND claim_token=? AND trang_thai=?",
                (SENDING, time.time(), gid, time.time(), viec_id, token, CLAIMED)).rowcount
            if n != 1:
                raise MatQuyen(viec_id)            # rollback: không để lại mã tab của người gửi đã mất claim

    @staticmethod
    def _viec_cung_nhom(con, nhom: tuple, tru_id: str, revision: Optional[tuple] = None) -> list:
        """Việc CHỜ khác cùng nhóm; ``revision`` = ``(dich_id, phien_ban)`` → chỉ việc của đúng revision đó."""
        ids = []
        for h in con.execute("SELECT id, dich_json FROM hang_doi_gui WHERE trang_thai IN (?,?)"
                             " AND id != ?", (*CO_THE_CLAIM, tru_id)):
            with contextlib.suppress(sd.LoiDichGui):
                c = sd.DichGuiChot.from_json(h["dich_json"])
                if _nhom(c) == nhom and (revision is None or (c.dich_id, c.phien_ban) == revision):
                    ids.append(h["id"])
        return ids

    def _chan_nhom(self, nhom: tuple, ly_do: str, tru_id: str, revision: Optional[tuple] = None) -> None:
        """Lỗi cấu hình: chặn luôn các việc CHỜ khác cùng nhóm — không đập vào bảng lỗi từng việc. Lỗi thuộc nhãn
        của MỘT revision (``revision``) chỉ chặn việc của revision đó (audit B-3)."""
        with sd.ket_noi(self.db_path, ghi=True) as con:
            for vid in self._viec_cung_nhom(con, nhom, tru_id, revision):
                con.execute("UPDATE hang_doi_gui SET trang_thai=?, loi=?, sua_luc=? WHERE id=?",
                            (BLOCKED_CONFIG, ly_do, time.time(), vid))

    def _hoan_nhom(self, nhom: tuple, den_luc: float, tru_id: str) -> None:
        """Lỗi tạm: hoãn các việc CHỜ khác cùng nhóm tới ``den_luc`` — LƯU BỀN (``thu_lai_sau``) nên
        không chiếm suất vòng sau, kể cả sau khi khởi động lại. Không đổi trạng thái, không tính lần thử."""
        with sd.ket_noi(self.db_path, ghi=True) as con:
            for vid in self._viec_cung_nhom(con, nhom, tru_id):
                con.execute("UPDATE hang_doi_gui SET thu_lai_sau=? WHERE id=? AND thu_lai_sau < ?",
                            (den_luc, vid, den_luc))

    def _xu_ly(self, viec_id: str, nhom: Optional[tuple], bay_gio: float) -> str:
        token = self._claim(viec_id, bay_gio)
        if token is None:
            return "tam_dung" if dang_tam_dung(self.db_path) else "bo_qua"
        da_phat = {"co": False, "gid": None}
        try:
            return self._xu_ly_da_claim(viec_id, token, nhom, bay_gio, da_phat)
        except Exception as e:
            # Ngoại lệ thoát khỏi việc đã claim (lỗi DB khi đọc/ghi…): KHÔNG để việc kẹt trong tay người gửi còn
            # sống tới lần khởi động lại (audit B-1). Lần chốt lỗi đã tự nhớ (``_chot``); còn lại: chưa phát → trả
            # claim theo luật lỗi tạm, đã phát → KHÔNG RÕ (như lỗi sau dispatch của transport).
            if viec_id not in self._ghi_treo:
                ten = type(e).__name__
                if da_phat["co"]:
                    cot = {"loi": f"{ten} sau khi gửi — không rõ Google đã ghi chưa."}
                    self._ghi_treo[viec_id] = lambda: self._ghi_chot(viec_id, token, UNKNOWN, cot)
                else:
                    self._ghi_treo[viec_id] = lambda: self._tra_claim(
                        viec_id, token, f"Lỗi trước khi gửi: {ten}", bay_gio)
            raise

    def _xu_ly_da_claim(self, viec_id: str, token: str, nhom: Optional[tuple], bay_gio: float,
                        da_phat: dict) -> str:
        v = lay_viec(self.db_path, viec_id)
        try:
            chot = v.dich
        except sd.LoiDichGui as e:
            self._chot(viec_id, token, BLOCKED_CONFIG, loi=str(e))
            return "bi_chan"
        header, rows = v.header, v.rows
        if (header is None or rows is None
                or _bam_payload(v.header_json, v.rows_json) != v.payload_sha256
                or len(header) != sd.SO_COT.get(chot.schema_id)):
            self._chot(viec_id, token, BLOCKED_REPORT,
                       loi="Dữ liệu cần gửi bị thiếu hoặc đã bị thay đổi — không gửi; hãy quét lại.")
            return "bi_chan"
        try:
            dung_yeu_cau_ghi(0, [header, *rows])      # mọi ô gửi được (số hữu hạn, đúng kiểu) — trước mọi request
        except (TypeError, ValueError):
            self._chot(viec_id, token, BLOCKED_REPORT,
                       loi="Dữ liệu cần gửi có ô không gửi được lên Sheets (số NaN/vô cực) — không gửi; hãy quét lại.")
            return "bi_chan"
        ly_do_khoa, duong_dan_khoa = self._kiem_khoa(chot)
        if ly_do_khoa:
            self._chot(viec_id, token, BLOCKED_CONFIG, loi=ly_do_khoa)
            if nhom is not None:
                self._chan_nhom(nhom, ly_do_khoa, viec_id)
            return "bi_chan"
        chot_gui, da_chot = self._tab_gui(v, chot)
        ly_do_tab = _ly_do_chan_tab(v, chot, da_chot)
        if ly_do_tab:
            self._chot(viec_id, token, BLOCKED_CONFIG, loi=ly_do_tab)
            return "bi_chan"

        def truoc_khi_gui(gid: int, ten: str) -> None:
            # Transport đã tìm được tab (theo mã/tên) và kiểm tiêu đề, CHƯA ghi gì. Revision chưa từng phát
            # request + hồ sơ có mã tab → tên tab phải khớp tên đối chiếu (dán nhầm link tab).
            if da_chot is None and chot.worksheet_id is not None and ten != chot.worksheet_ten:
                raise ChuaGui(f"Tab mã {gid} hiện tên «{ten}», khác tên đối chiếu «{chot.worksheet_ten}» "
                              "của hồ sơ — kiểm lại link/tên tab trong hồ sơ (chưa ghi gì).",
                              tam_thoi=False, chi_revision=True)
            self._bat_dau_gui(viec_id, token, chot, gid, ten)      # chốt mã tab + SENDING: MỘT giao dịch
            da_phat["co"], da_phat["gid"] = True, gid

        try:
            kq = self.cong.gui(chot_gui, duong_dan_khoa, header, rows, truoc_khi_gui)
        except MatQuyen:
            return "bo_qua"
        except ChuaGui as e:
            return self._xu_ly_chua_gui(v, token, nhom, e, bay_gio)
        except KhongRo as e:
            self._chot(viec_id, token, UNKNOWN, loi=e.ly_do)
            return "khong_ro"
        except Exception as e:  # noqa: BLE001 — phân loại theo việc đã dispatch hay chưa
            ten = type(e).__name__
            if da_phat["co"]:
                self._chot(viec_id, token, UNKNOWN,
                           loi=f"{ten} sau khi gửi — không rõ Google đã ghi chưa.")
                return "khong_ro"
            return self._xu_ly_chua_gui(v, token, nhom,
                                        ChuaGui(f"Lỗi trước khi gửi: {ten}", tam_thoi=True), bay_gio)
        if not da_phat["co"]:
            # Transport trả kết quả mà không qua bước chốt trước khi gửi (vi phạm hợp đồng): không biết đã ghi đâu.
            self._chot(viec_id, token, UNKNOWN, loi="Transport trả kết quả mà chưa qua bước chốt trước khi gửi — "
                       "không rõ đã ghi chưa.")
            return "khong_ro"
        # Biên nhận phải khớp ĐÚNG mã tab vừa chốt — đọc từ THÂN REQUEST đã phát (hồ sơ theo tên cũng vậy).
        hop_le, ly_do, bien_nhan = kiem_bien_nhan(kq, replace(chot_gui, worksheet_id=da_phat["gid"]),
                                                  header=header, rows=rows)
        if not hop_le:
            self._chot(viec_id, token, UNKNOWN, loi=f"Biên nhận bất thường: {ly_do}.")
            return "khong_ro"
        self._chot(viec_id, token, SENT, loi="", bien_nhan=json.dumps(bien_nhan, ensure_ascii=False))
        return "da_gui"

    def _xu_ly_chua_gui(self, v: ViecGui, token: str, nhom, e: ChuaGui, bay_gio: float) -> str:
        if not e.tam_thoi:
            self._chot(v.id, token, BLOCKED_CONFIG, loi=e.ly_do)
            if nhom is not None:
                revision = (v.dich.dich_id, v.dich.phien_ban) if e.chi_revision else None
                self._chan_nhom(nhom, e.ly_do, v.id, revision)
            return "bi_chan"
        so_lan = lay_viec(self.db_path, v.id).so_lan_thu
        if so_lan >= self.so_lan_toi_da:
            self._chot(v.id, token, BLOCKED_CONFIG,
                       loi=f"{e.ly_do} — quá số lần thử ({so_lan}); bấm «Thử gửi lại» khi đã ổn.")
            return "bi_chan"
        cho = _thoi_gian_cho(so_lan)
        self._chot(v.id, token, RETRY_WAIT, loi=e.ly_do, thu_lai_sau=bay_gio + cho)
        if nhom is not None:
            self._hoan_nhom(nhom, bay_gio + cho, v.id)
        return "thu_lai"

    def _kiem_khoa(self, chot: sd.DichGuiChot) -> tuple:
        """``(lý_do_chặn, đường_dẫn_khoá)``. Đọc file khoá local; không gọi mạng."""
        ly_do = kiem_khoa_cuc_bo(self.db_path, chot)
        if ly_do:
            return ly_do, ""
        return "", sd.lay_xac_thuc(self.db_path, chot.xac_thuc_ref).duong_dan

    def _tab_gui(self, v: ViecGui, chot: sd.DichGuiChot) -> tuple:
        """``(đích để gửi, tab đã chốt | None)``: việc đã phát → MÃ của chính lần phát đó; không thì revision đã
        phát request (mã chốt trong giao dịch SENDING) → MÃ đã chốt của revision (không đọc hồ sơ hiện tại, không tìm
        lại theo tên — tab đổi tên vẫn đúng chỗ, tab cùng tên tạo lại không bao giờ được coi là tab cũ). Hai mã
        lệch nhau thì ``_ly_do_chan_tab`` đã chặn trước."""
        da_chot = sd.tab_da_chot(self.db_path, chot.dich_id, chot.phien_ban)
        ma = _ma_tab_da_phat(v, chot)
        if ma is None and da_chot is not None:
            ma = da_chot.worksheet_id
        return (chot if ma is None else replace(chot, worksheet_id=ma)), da_chot


# ---------------------------------------------------------------------------
#  Luồng nền (app / Watch): một người gửi mỗi tiến trình, giành quyền định kỳ
# ---------------------------------------------------------------------------

class NguoiGuiNen:
    """Luồng nền giữ một ``NguoiGui``: thử giành quyền, gửi theo vòng, thức dậy khi có việc mới.
    Không đọc ``st.session_state`` (chạy ngoài ScriptRunContext)."""

    # Dừng = không nhận việc mới + CHỜ việc đang bay xong (transport tự giới hạn: kết nối 10 s + đọc
    # 60 s). Thoát tiến trình giữa lúc request đang bay sẽ biến việc thành KHÔNG RÕ dù chẳng có sự cố.
    HAN_DUNG_S = 90.0

    def __init__(self, db_path: str, data_dir: str, tao_cong: Callable, *,
                 chu_ky_s: float = 15.0, chu_ky_gianh_s: float = 30.0):
        self.db_path, self.data_dir = db_path, data_dir
        self._tao_cong = tao_cong
        self.chu_ky_s, self.chu_ky_gianh_s = chu_ky_s, chu_ky_gianh_s
        self._thuc = threading.Event()
        self._dung = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._khoa_luong = threading.Lock()
        self.nguoi_gui: Optional[NguoiGui] = None
        self.loi_cuoi = ""
        # Lý do tiến trình này là BẢN CŨ (đã có bản mới kích hoạt) — đã nhường quyền, không chạy lại nữa.
        self.ban_cu = ""
        # Số lượt của vòng lặp đã BẮT ĐẦU / đã XONG (giành quyền + một vòng gửi, hoặc giành hụt):
        # ``cho_gui_xong`` đợi một lượt trọn vẹn bắt đầu sau khi nó được gọi (audit B-6).
        self.so_luot_bat_dau = 0
        self.so_luot_xong = 0

    def start(self) -> None:
        with self._khoa_luong:
            if self._thread is not None and self._thread.is_alive():
                return
            self._dung.clear()
            # Đăng ký để `danh_thuc(db)` (gọi sau mỗi lần `save_job` xếp hàng) đánh thức đúng luồng này.
            with _NEN_KHOA:
                _NEN.setdefault(_khoa_db(self.db_path), self)
            self._thread = threading.Thread(target=self._vong, name="outbox-sender", daemon=True)
            self._thread.start()

    def danh_thuc(self) -> None:
        self._thuc.set()

    @property
    def dang_chay(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self, cho_s: Optional[float] = None) -> None:
        """Không nhận việc mới; CHỜ việc đang bay xong (tối đa ``HAN_DUNG_S``) rồi nhả quyền."""
        self._dung.set()
        self._thuc.set()
        if self._thread is not None:
            self._thread.join(timeout=self.HAN_DUNG_S if cho_s is None else cho_s)
            if self._thread.is_alive():
                LOGGER.error("event=outbox.stop_timeout — luồng gửi vẫn chạy sau %.0f s",
                             self.HAN_DUNG_S if cho_s is None else cho_s)
        with _NEN_KHOA:
            if _NEN.get(_khoa_db(self.db_path)) is self:
                del _NEN[_khoa_db(self.db_path)]

    @property
    def co_quyen(self) -> bool:
        return self.nguoi_gui is not None and self.nguoi_gui.co_quyen

    def _vong(self) -> None:
        try:
            while not self._dung.is_set():
                self.so_luot_bat_dau += 1
                if self.nguoi_gui is None:
                    self.nguoi_gui = NguoiGui(self.db_path, self.data_dir, self._tao_cong(),
                                              dung=self._dung)
                cho = self.chu_ky_gianh_s
                # Bản mới đã kích hoạt mà tiến trình (app cũ) còn mở: NHƯỜNG quyền người gửi cho bản đang
                # kích hoạt (giữ quyền mà từ chối mọi việc thì Watch/CLI của bản mới không gửi được gì) — nhưng
                # KHÔNG khoá chết: bản mới hỏng health → quay về bản này thì lấy lại quyền và gửi tiếp.
                ly_do = self.nguoi_gui.cong_bao_tri.ly_do_ban_cu() if isinstance(
                    self.nguoi_gui.cong_bao_tri, maintenance_gate.CongBaoTri) else ""
                if ly_do:
                    self._nhuong_cho_ban_moi(ly_do)
                    self.so_luot_xong += 1
                    self._thuc.wait(self.chu_ky_gianh_s)
                    self._thuc.clear()
                    continue
                if self.ban_cu:
                    LOGGER.info("event=outbox.active_again — bản này lại là bản đang kích hoạt, gửi tiếp")
                    self.ban_cu = ""
                try:
                    if self.nguoi_gui.co_quyen or self.nguoi_gui.nhan_quyen():
                        dem = self.nguoi_gui.chay_mot_vong()
                        if dem.get("ban_cu"):
                            self._nhuong_cho_ban_moi("cổng báo bản cũ")
                        # Còn việc vừa xử lý → vòng tiếp ngay; không thì chờ chu kỳ/đánh thức.
                        cho = 0.2 if (dem["da_gui"] or dem["thu_lai"]) else self.chu_ky_s
                    self.loi_cuoi = ""
                except Exception as e:  # noqa: BLE001 — luồng không được chết vì một vòng lỗi
                    self.loi_cuoi = f"{type(e).__name__}"
                    LOGGER.exception("event=outbox.round_failed")
                    cho = self.chu_ky_s
                self.so_luot_xong += 1
                self._thuc.wait(cho)
                self._thuc.clear()
        finally:
            if self.nguoi_gui is not None:
                self.nguoi_gui.tha_quyen()

    def _nhuong_cho_ban_moi(self, ly_do: str) -> None:
        """Nhả quyền người gửi (giữa hai việc — không có việc nào đang bay) và đánh dấu; luồng vẫn chạy để
        lấy lại quyền nếu bản này lại thành bản đang kích hoạt (quay lại sau health hỏng)."""
        if not self.ban_cu:
            LOGGER.warning("event=outbox.yield_to_active_release — tiến trình chạy bản đã bị thay, nhường quyền")
        self.ban_cu = ly_do or "bản cũ"
        if self.nguoi_gui is not None:
            self.nguoi_gui.tha_quyen()


_NEN: dict = {}
_NEN_KHOA = threading.RLock()
_DA_DANG_KY_THOAT = False

# CLAIMED lâu hơn mức này là bất thường: một lần xử lý tự giới hạn — trước SENDING có tới ~5 request (làm mới
# khoá, metadata, tìm tab, 1–2 lần đọc tiêu đề), mỗi request tối đa ``CongGspread.THOI_GIAN_CHO`` = 10 + 60 s
# (≈ 350 s khi mạng nghẽn). Ngưỡng CẢNH BÁO, đặt trên tổng đó để không báo nhầm lúc mạng chậm; ai đang cầm việc
# (tiến trình này hay tiến trình khác) xét theo ``chu_so_huu`` — xem ``_cau_giu_lau``.
HAN_GIU_VIEC_LAU_S = 420.0
_CHUA_TRUYEN = object()


def nguoi_gui_nen(db_path: str) -> Optional["NguoiGuiNen"]:
    """Luồng người gửi nền của DB này trong tiến trình này (``None`` = chưa khởi động)."""
    with _NEN_KHOA:
        return _NEN.get(_khoa_db(db_path))


def anh_chup_cho_gui(db_path: str) -> dict:
    """Ảnh chụp CHỈ ĐỌC (một kết nối) những gì ``ly_do_chua_gui`` cần: cờ tạm dừng toàn bộ, hồ sơ đang tạm dừng
    (đúng hai điều kiện lệnh claim xét — audit F-15), mốc nhận + chủ (``<pid>-<8 hex>``) của việc ``CLAIMED``.
    Giao diện chụp MỘT lần mỗi lần vẽ bảng thay vì mở DB cho từng dòng."""
    with sd.ket_noi(db_path) as con:
        h = con.execute("SELECT gia_tri FROM cai_dat_may WHERE khoa=?", (_KHOA_TAM_DUNG,)).fetchone()
        ho_so = {r["id"] for r in con.execute("SELECT id FROM dich_gui WHERE trang_thai=?", (sd.TT_TAM_DUNG,))}
        dang_cam = con.execute("SELECT id, claim_luc, chu_so_huu FROM hang_doi_gui WHERE trang_thai=?",
                               (CLAIMED,)).fetchall()
    return {"tam_dung": h is not None and h["gia_tri"] == "1", "ho_so_tam_dung": ho_so,
            "claim_luc": {r["id"]: float(r["claim_luc"] or 0) for r in dang_cam},
            "chu_so_huu": {r["id"]: str(r["chu_so_huu"] or "") for r in dang_cam}}


def _cau_giu_lau(chu: str, nen) -> str:
    """Việc CLAIMED quá ``HAN_GIU_VIEC_LAU_S``: lời khuyên theo AI đang cầm. Việc CHƯA tới bước gửi (chưa commit
    SENDING) nên chưa ghi gì; huỷ luôn an toàn (huỷ xoá ``claim_token`` — fencing, audit B-1)."""
    huy = "hoặc huỷ việc này (huỷ xoá quyền giữ việc, người gửi không phát được request nào)."
    pid = chu.split("-", 1)[0]
    if pid and pid != str(os.getpid()):
        # ``phuc_hoi`` chỉ chạy khi GIÀNH được khoá người gửi — tiến trình kia còn giữ thì khởi động lại Tool này
        # không trả việc về được.
        return (f" Giữ lâu bất thường — tiến trình khác (mã tiến trình {pid}: Watch/CLI hoặc cửa sổ Tool khác) đang "
                "cầm việc; khởi động lại Tool này không đổi gì. Việc CHƯA tới bước gửi nên chưa ghi gì: đợi tiến "
                f"trình đó, {huy}")
    if nen is not None and nen.dang_chay and nen.co_quyen:
        # Một người gửi mỗi state root: tiến trình này giữ quyền thì việc CLAIMED là của luồng còn sống của nó
        # (giành quyền đã ``phuc_hoi`` mọi CLAIMED của chủ cũ).
        return (" Người gửi của Tool này vẫn đang chờ Google trả lời (mỗi request tối đa 70 s, mạng chậm) — việc "
                f"CHƯA tới bước gửi nên chưa ghi gì; đợi thêm, {huy}")
    return (" Giữ lâu bất thường — người gửi có thể đã dừng giữa chừng. Việc CHƯA tới bước gửi nên chưa ghi gì; "
            f"khởi động lại Tool sẽ trả việc về «Chờ gửi» (không gửi trùng), {huy}")


def ly_do_chua_gui(db_path: str, v: ViecGui, *, bay_gio: Optional[float] = None, nen=_CHUA_TRUYEN,
                   gio: Optional[Callable[[float], str]] = None, anh: Optional[dict] = None) -> str:
    """VÌ SAO một việc «Chờ gửi / Chờ thử lại / Đang chuẩn bị» chưa đi — cho giao diện. CHỈ ĐỌC; rỗng với trạng
    thái khác. Theo đúng thứ tự người gửi xét: tạm dừng toàn bộ → hồ sơ tạm dừng (cả hai kiểm ngay trong lệnh
    claim) → hẹn giờ → người gửi nền. ``anh``: ``anh_chup_cho_gui`` chụp sẵn (không truyền thì tự chụp).
    ``gio``: hàm hiển thị một mốc epoch (tầng GIAO DIỆN truyền vào — module lõi không tự đổi epoch sang giờ,
    xem ``test_khong_module_nao_tu_doi_epoch_sang_ngay_dang``); không truyền thì câu không kèm giờ."""
    if v.trang_thai not in (PENDING, RETRY_WAIT, CLAIMED):
        return ""
    bay_gio = time.time() if bay_gio is None else bay_gio
    anh = anh_chup_cho_gui(db_path) if anh is None else anh

    def luc_(t: float) -> str:
        return f" lúc {gio(t)}" if gio is not None and t else ""

    if v.trang_thai == CLAIMED:
        # Đã claim thì đi tới kết cục kể cả khi vừa bật tạm dừng. CLAIMED = chưa commit SENDING = chưa phát request.
        luc = anh["claim_luc"].get(v.id, 0.0)
        cau = f"📤 Người gửi đang xử lý (nhận{luc_(luc)})." if luc else "📤 Người gửi đang xử lý."
        if luc and bay_gio - luc > HAN_GIU_VIEC_LAU_S:
            if nen is _CHUA_TRUYEN:
                nen = nguoi_gui_nen(db_path)
            cau += _cau_giu_lau(anh.get("chu_so_huu", {}).get(v.id, ""), nen)
        return cau
    if anh["tam_dung"]:
        return "⏸ Đang tạm dừng toàn bộ việc gửi — tắt công tắc tạm dừng để gửi."
    if v.dich_id in anh["ho_so_tam_dung"]:
        return "⏸ Hồ sơ đích đang tạm dừng gửi — bấm «▶ Bật lại» ở hồ sơ đó."
    if v.thu_lai_sau > bay_gio:
        if v.trang_thai == RETRY_WAIT:
            return f"⏳ Hẹn thử lại{luc_(v.thu_lai_sau)} sau lỗi tạm: {(v.loi or '')[:120]}"
        return f"⏳ Hẹn gửi{luc_(v.thu_lai_sau)} — hoãn theo việc cùng bảng/tab vừa gặp lỗi tạm."
    if nen is _CHUA_TRUYEN:
        nen = nguoi_gui_nen(db_path)
    if nen is None or not nen.dang_chay:
        return "Người gửi nền chưa chạy trong tiến trình này — tải lại trang để khởi động."
    if getattr(nen, "ban_cu", ""):
        return "Tiến trình này chạy bản đã bị thay — đã nhường quyền gửi cho bản đang kích hoạt."
    if not nen.co_quyen and nen.loi_cuoi:
        # Giành quyền LỖI (khoá file giành được nhưng phục hồi gặp lỗi DB → đã nhả; hoặc không tạo được file
        # khoá): không ai giữ quyền cả — chỉ ``DangChayRoi`` (``loi_cuoi`` rỗng) mới là «tiến trình khác đang giữ».
        return (f"Người gửi chưa giành được quyền gửi — lần thử gần nhất lỗi ({nen.loi_cuoi}); tự thử lại mỗi "
                "chu kỳ — xem nhật ký Tool.")
    if not nen.co_quyen:
        return ("Người gửi chưa giữ quyền gửi — một tiến trình khác (Watch/CLI hoặc cửa sổ Tool khác) đang giữ; "
                "việc sẽ được gửi khi quyền được nhả.")
    if nen.loi_cuoi:
        return f"Vòng gửi gần nhất lỗi ({nen.loi_cuoi}) — xem nhật ký Tool."
    return "Sắp gửi (vòng gửi kế tiếp)."


def _dung_tat_ca_khi_thoat() -> None:
    """Hook thoát tiến trình (app tắt êm): dừng mọi người gửi nền — CHỜ việc đang bay xong để nó không
    thành KHÔNG RÕ. Tắt cứng (đóng cửa sổ console, mất điện) thì khôi phục lần sau xử lý như crash."""
    with _NEN_KHOA:
        ds = list(_NEN.values())
    for nen in ds:
        with contextlib.suppress(Exception):
            nen.stop()


def _khoa_db(db_path: str) -> str:
    return os.path.normcase(os.path.abspath(db_path))


def dam_bao_chay_nen(db_path: str, data_dir: str, tao_cong: Optional[Callable] = None) -> NguoiGuiNen:
    """MỘT luồng người gửi mỗi DB mỗi tiến trình (app có nhiều phiên trình duyệt dùng chung). Lấy-hoặc-tạo
    và khởi động trong CÙNG khoá: nhiều phiên gọi đồng thời không tạo hai luồng."""
    global _DA_DANG_KY_THOAT
    with _NEN_KHOA:
        nen = _NEN.get(_khoa_db(db_path))
        if nen is None:
            nen = NguoiGuiNen(db_path, data_dir, tao_cong or CongGspread)
        nen.start()
        if not _DA_DANG_KY_THOAT:
            atexit.register(_dung_tat_ca_khi_thoat)
            _DA_DANG_KY_THOAT = True
    return nen


def cho_gui_xong(db_path: str, data_dir: str, lo_id: str, *, han_s: float = 120.0,
                 tao_cong: Optional[Callable] = None, nen: Optional[NguoiGuiNen] = None,
                 ngu: Callable = time.sleep, dung: Optional[Callable[[], bool]] = None) -> dict:
    """Chờ CÓ HẠN tới khi việc gửi của lượt ``lo_id`` không còn chờ/đang gửi; trả số việc theo trạng
    thái. Người gửi khác (app) đang giữ quyền thì thôi chờ sớm — việc vẫn bền trong hàng đợi.
    ``RETRY_WAIT`` không bị chờ (đã hẹn giờ thử lại). Việc chỉ chờ vì TẠM DỪNG (``ly_do_tam_dung``)
    cũng không bị chờ: người gửi không nhận cho tới khi người dùng bật lại. Dù lượt không còn gì chờ,
    vẫn đợi người gửi chạy trọn MỘT lượt bắt đầu sau lời gọi: lượt Watch không có gì mới vẫn gửi việc
    đã tới hạn của lượt trước, thay vì dừng người gửi trước khi nó kịp giành quyền (audit B-6).
    ``han_s <= 0``: không khởi động người gửi, chỉ đếm. ``dung()`` trả True (yêu cầu dừng / Ctrl+C)
    → thôi chờ."""
    if han_s <= 0:
        return tom_tat(db_path, lo_id=lo_id)
    tu_tao = nen is None
    if tu_tao:
        nen = NguoiGuiNen(db_path, data_dir, tao_cong or CongGspread, chu_ky_s=2.0,
                          chu_ky_gianh_s=2.0)
        nen.start()
    bat_dau = time.monotonic()
    moc_luot = nen.so_luot_bat_dau
    try:
        nen.danh_thuc()
        while True:
            tt = tom_tat(db_path, lo_id=lo_id)
            da_chay_luot = nen.so_luot_xong > moc_luot or not nen.dang_chay
            if ((tt[PENDING] + tt[CLAIMED] + tt[SENDING] == 0 and da_chay_luot)
                    or ly_do_tam_dung(db_path, lo_id)):
                break
            da = time.monotonic() - bat_dau
            if da >= han_s or (not nen.co_quyen and da >= min(10.0, han_s)):
                break
            if dung is not None and dung():
                break
            ngu(0.2)
    finally:
        if tu_tao:
            nen.stop()
    return tom_tat(db_path, lo_id=lo_id)


def kiem_cau_hinh(db_path: str, chot: sd.DichGuiChot, header: list, cong=None) -> tuple:
    """«Kiểm cấu hình (chỉ đọc)» theo ĐÚNG cách người gửi sẽ gửi: khoá local → mã tab đã chốt của
    revision (nếu có) → đối chiếu tên khi revision chưa từng gửi. ``(ok, thông_báo)``; có gọi Google."""
    ly_do = kiem_khoa_cuc_bo(db_path, chot)
    if ly_do:
        return False, ly_do
    da_chot = sd.tab_da_chot(db_path, chot.dich_id, chot.phien_ban)
    chot_gui = chot if da_chot is None else replace(chot, worksheet_id=da_chot.worksheet_id)
    doi_chieu = chot.worksheet_ten if (da_chot is None and chot.worksheet_id is not None) else ""
    xt = sd.lay_xac_thuc(db_path, chot.xac_thuc_ref)
    return (cong or CongGspread()).kiem(chot_gui, xt.duong_dan, header, ten_doi_chieu=doi_chieu)


def danh_thuc(db_path: str) -> None:
    """Gọi sau khi xếp hàng trong tiến trình này: người gửi nền (nếu có) gửi ngay, khỏi chờ chu kỳ."""
    with _NEN_KHOA:
        nen = _NEN.get(_khoa_db(db_path))
    if nen is not None:
        nen.danh_thuc()


# ---------------------------------------------------------------------------
#  Transport Google Sheets thật (gspread) — phân loại lỗi theo KIỂU ngoại lệ
# ---------------------------------------------------------------------------

def _co_nguyen_nhan(e: BaseException, kieu: tuple) -> bool:
    """Ngoại lệ ``e`` BAO (qua ``args`` — cách requests bọc lỗi urllib3 — hoặc ``MaxRetryError.reason``)
    một lỗi kiểu ``kieu``? KHÔNG lần theo ``__cause__``/``__context__``: ngữ cảnh ngầm có thể là lỗi của
    một lần thử TRƯỚC, không chứng minh request cuối cùng chưa đi."""
    da_xem, ngan_xep = set(), [e]
    while ngan_xep:
        x = ngan_xep.pop()
        if x is None or id(x) in da_xem:
            continue
        da_xem.add(id(x))
        if isinstance(x, kieu):
            return True
        if isinstance(x, BaseException):
            ngan_xep.extend([getattr(x, "reason", None),
                             *[a for a in getattr(x, "args", ()) if isinstance(a, BaseException)]])
    return False


def _la_ma_http(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and 100 <= x <= 599


def _ma_http(e: BaseException) -> int:
    """Mã HTTP THẬT của phản hồi trước, ``e.code`` sau. Thân lỗi không phải JSON (trang lỗi HTML, proxy)
    thì gspread đặt ``code = -1`` — mã giả đó không được che mã thật (audit B-7)."""
    for ung_vien in (getattr(getattr(e, "response", None), "status_code", None),
                     getattr(e, "code", None)):
        if _la_ma_http(ung_vien):
            return ung_vien
    return -1


# Lỗi 401/403 của Google nói rõ nguyên nhân ở ``error.details[].reason`` (giá trị LIỆT KÊ, không chứa URL/mã).
# gspread ``open_by_key`` bọc MỌI 403 thành ``PermissionError`` trần (gspread 6.2.1 client.py:172) — reason chỉ
# còn ở ``__cause__``. Chỉ dùng nó để CHỌN CÂU; phân loại chưa gửi/mơ hồ vẫn theo KIỂU ngoại lệ + mã HTTP như cũ.
_CAU_API_CHUA_BAT = ("Google Sheets API chưa bật trong project Google Cloud của tài khoản dịch vụ — bật «Google "
                     "Sheets API» cho project đó (chia sẻ bảng thôi là chưa đủ).")
_CAU_THEO_REASON = {
    "SERVICE_DISABLED": _CAU_API_CHUA_BAT,
    "ACCESS_NOT_CONFIGURED": _CAU_API_CHUA_BAT,
    "ACCESS_TOKEN_SCOPE_INSUFFICIENT": ("Khoá được cấp thiếu phạm vi quyền (scope) Google Sheets — tool cần quyền "
                                        "đọc/ghi bảng tính."),
}


def _reason_google(e: BaseException) -> set:
    """``{reason}`` của ``APIError`` gốc — tự ``e`` hoặc chuỗi ``__cause__`` (``PermissionError`` /
    ``SpreadsheetNotFound`` của gspread). Không đọc ``message`` (có thể mang mã bảng/URL). Thân lỗi không phải
    JSON (audit B-7: ``code = -1``) không có ``details`` → rỗng."""
    import gspread

    x, da_xem = e, set()
    while x is not None and id(x) not in da_xem:
        da_xem.add(id(x))
        if isinstance(x, gspread.exceptions.APIError):
            loi = getattr(x, "error", None)
            chi_tiet = loi.get("details") if isinstance(loi, dict) else None
            if not isinstance(chi_tiet, list):
                return set()
            return {d["reason"] for d in chi_tiet if isinstance(d, dict) and isinstance(d.get("reason"), str)}
        x = x.__cause__
    return set()


def _cau_theo_reason(e: BaseException) -> str:
    ly_do = _reason_google(e)
    return next((_CAU_THEO_REASON[r] for r in sorted(ly_do) if r in _CAU_THEO_REASON), "")


def _la_loi_truy_cap(e: BaseException) -> bool:
    """Lỗi nằm ở QUYỀN TRUY CẬP (khoá/tài khoản/bảng), không phải ở tab, tiêu đề hay mạng."""
    import google.auth.exceptions as gae
    import gspread

    if isinstance(e, (PermissionError, gspread.exceptions.SpreadsheetNotFound)):
        return True
    if isinstance(e, gae.RefreshError):
        return not getattr(e, "retryable", False)
    return isinstance(e, gspread.exceptions.APIError) and _ma_http(e) in (401, 403, 404)


_MO_NGU_CANH = " [khoá «"


def tach_ngu_canh(ly_do: str) -> tuple:
    """``(câu, ngữ_cảnh)`` — tách phần ``_kem_ngu_canh`` gắn ở CUỐI (`` [khoá «…» → …; bảng xxxxxx…]``) để giao
    diện rút gọn câu mà không cắt mất ngữ cảnh. Không có ngữ cảnh → ``(ly_do, "")``."""
    i = ly_do.rfind(_MO_NGU_CANH)
    if i < 0 or not ly_do.endswith("…]"):
        return ly_do, ""
    return ly_do[:i], ly_do[i:]


def _kem_ngu_canh(loi: Exception, e: BaseException, chot: sd.DichGuiChot) -> Exception:
    """Lỗi TRUY CẬP vĩnh viễn: kèm binding + tài khoản dịch vụ + mã bảng RÚT GỌN của việc KÍCH HOẠT lỗi — thấy
    ngay lần gửi đó dùng khoá của tài khoản nào, mở bảng nào (khoá nhầm tài khoản, dán nhầm bảng). Email tài khoản
    dịch vụ là địa chỉ để chia sẻ (giao diện vẫn hiện), không phải bí mật; mã bảng chỉ 6 ký tự đầu. Giữ nguyên phân
    loại (``tam_thoi``) và phạm vi chặn (``chi_revision``, audit B-3) — chỉ đổi CÂU.

    ``_chan_nhom`` chép NGUYÊN câu này sang các việc chờ cùng nhóm (cùng bảng + tab + binding + lược đồ — ``_nhom``
    không gồm principal): binding đăng ký lại sang tài khoản khác thì việc cũ (``chot.principal`` cũ) hiện tài
    khoản của việc kích hoạt. Chấp nhận (review 26/10): chỉ là câu hiển thị; trạng thái và phạm vi chặn không đổi,
    và khi «Thử gửi lại» mỗi việc tự qua ``_kiem_khoa`` với principal của chính nó."""
    if not isinstance(loi, ChuaGui) or loi.tam_thoi or not _la_loi_truy_cap(e):
        return loi
    return ChuaGui(f"{loi.ly_do}{_MO_NGU_CANH}{chot.xac_thuc_ref}» → {chot.principal}; bảng "
                   f"{chot.spreadsheet_id[:6]}…]", tam_thoi=False, chi_revision=loi.chi_revision)


def phan_loai_loi(e: BaseException, *, da_phat: bool) -> Exception:
    """Đổi ngoại lệ của gspread/requests/google-auth thành ``ChuaGui``/``KhongRo``.

    Trước dispatch (``da_phat=False``): chưa có request ghi nào — mọi lỗi đều "chưa gửi" (tạm hay
    cấu hình). Sau dispatch: chỉ những KIỂU chứng minh request không tới (không kết nối được, phân
    giải tên lỗi, lấy token lỗi) hay Google trả lời từ chối (4xx) mới là "chưa gửi"; còn lại → mơ hồ.
    Lý do KHÔNG chứa message gốc (có thể mang mã bảng/URL) — chỉ kiểu + mã HTTP.
    """
    import google.auth.exceptions as gae
    import gspread
    import requests
    import urllib3.exceptions as u3

    from sheets import LoiHeaderSheet

    ten = type(e).__name__
    if isinstance(e, ChuaGui):
        return e
    if isinstance(e, (LoiHeaderSheet, sd.LoiDichGui)):
        return ChuaGui(str(e), tam_thoi=False)
    if isinstance(e, PermissionError):
        # gspread.open_by_key: HTTP 403 → PermissionError (built-in, là OSError) — PHẢI xét trước nhánh
        # OSError/mạng: bảng chưa chia sẻ cho tài khoản dịch vụ là lỗi CẤU HÌNH, thử lại không ích gì.
        # MỌI 403 đều thành PermissionError (cả «API chưa bật») — reason của Google chọn câu đúng.
        return ChuaGui(_cau_theo_reason(e) or (
            "Tài khoản dịch vụ không có quyền mở bảng — chia sẻ bảng (Người chỉnh sửa) cho địa chỉ của binding "
            "khoá; kiểm hồ sơ dùng ĐÚNG binding và ĐÚNG bảng."), tam_thoi=False)
    if isinstance(e, gspread.exceptions.WorksheetNotFound):
        return ChuaGui("Không thấy tab đã ghim (theo mã tab) — tab có thể đã bị xoá hoặc tạo lại; "
                       "không tự chọn tab khác.", tam_thoi=False)
    if isinstance(e, gspread.exceptions.SpreadsheetNotFound):
        # gspread: HTTP 404 khi mở bảng. Sheets API trả 403 (nhánh PermissionError) cho bảng CHƯA chia sẻ — 404 là
        # mã bảng sai hoặc bảng đã bị xoá; khuyên chia sẻ lại là sai hướng.
        return ChuaGui("Không thấy bảng tính với mã này (mã sai hoặc bảng đã bị xoá) — kiểm lại link trong hồ sơ "
                       "đích; bảng chưa chia sẻ sẽ báo lỗi quyền (403), không phải lỗi này.", tam_thoi=False)
    if isinstance(e, gae.RefreshError):
        if getattr(e, "retryable", False):
            return ChuaGui("Google tạm thời chưa cấp phiên đăng nhập — thử lại sau.", tam_thoi=True)
        return ChuaGui("Google từ chối khoá (khoá sai hoặc đã bị thu hồi).", tam_thoi=False)
    if isinstance(e, gae.TransportError):
        return ChuaGui("Không lấy được phiên đăng nhập Google (mạng).", tam_thoi=True)
    if isinstance(e, gspread.exceptions.APIError):
        ma = _ma_http(e)
        trang_thai = ""
        with contextlib.suppress(Exception):
            if _la_ma_http(e.error.get("code")):          # -1 = gspread không đọc được JSON: «status» là lỗi phân tích
                trang_thai = str(e.error.get("status") or "")[:40]
        mo_ta = f"Google trả lỗi HTTP {ma}{(' ' + trang_thai) if trang_thai else ''}"
        if ma == 429:
            return ChuaGui(mo_ta + " (quá hạn mức) — thử lại sau.", tam_thoi=True)
        if da_phat and (ma == 408 or ma < 400 or ma >= 500):
            return KhongRo(mo_ta + " sau khi gửi — không rõ Google đã ghi chưa.")
        if 400 <= ma < 500 and ma != 408:
            return ChuaGui(_cau_theo_reason(e) or (mo_ta + " — kiểm quyền/tab/cấu hình."), tam_thoi=False)
        return ChuaGui(mo_ta + " — thử lại sau.", tam_thoi=True)
    if not da_phat:
        if isinstance(e, (requests.exceptions.RequestException, OSError)):
            return ChuaGui(f"Lỗi mạng khi kiểm bảng ({ten}).", tam_thoi=True)
        if isinstance(e, ValueError):
            return ChuaGui(f"Khoá/bảng không hợp lệ ({ten}).", tam_thoi=False)
        return ChuaGui(f"Lỗi trước khi gửi ({ten}).", tam_thoi=True)
    if isinstance(e, requests.exceptions.ConnectTimeout) or _co_nguyen_nhan(
            e, (u3.ConnectTimeoutError,)):
        # Không mở được kết nối (gồm NewConnectionError, NameResolutionError) → request chưa đi.
        return ChuaGui(f"Không kết nối được Google ({ten}).", tam_thoi=True)
    return KhongRo(f"{ten} sau khi gửi — không rõ Google đã ghi chưa.")


class _TabTheoMa:
    """Một tab ĐỌC THEO MÃ cho ``sheets.kiem_tieu_de_nghiem_ngat`` (duck-type ``get_values``/``get_all_values`` của
    ``Worksheet``, luật kiểm giữ nguyên văn): ``values:batchGetByDataFilter`` với ``gridRange.sheetId``.
    ``Worksheet.get_values`` của gspread dựng range A1 từ TÊN — tab đổi tên + tab trống mới mang tên cũ ngay trước
    lần đọc từng làm kiểm nhầm tab khác ("trang tính trống") rồi chèn thêm hàng tiêu đề vào tab thật."""

    def __init__(self, sh, gid: int):
        self._sh, self._gid = sh, int(gid)

    def _doc(self, vung: dict) -> list:
        import gspread
        from gspread.urls import SPREADSHEETS_API_V4_BASE_URL

        url = f"{SPREADSHEETS_API_V4_BASE_URL}/{self._sh.id}/values:batchGetByDataFilter"
        ph = self._sh.client.request("post", url, json={
            "dataFilters": [{"gridRange": {"sheetId": self._gid, **vung}}],
            "majorDimension": "ROWS", "valueRenderOption": "FORMATTED_VALUE"}).json()
        khop = [m.get("valueRange") for m in ph.get("valueRanges") or [] if isinstance(m, dict)]
        if len(khop) != 1 or not isinstance(khop[0], dict):
            # Tài liệu không nói ca bộ lọc không khớp: không có đúng MỘT vùng = không đọc được tab THEO MÃ.
            raise gspread.exceptions.WorksheetNotFound(f"id {self._gid}")
        return khop[0].get("values") or []

    def get_values(self, a1: str) -> list:
        from gspread.utils import a1_to_rowcol

        dau, _, cuoi = a1.partition(":")
        hang, cot = a1_to_rowcol(cuoi or dau)
        if dau != "A1" or hang != 1:
            raise ValueError(f"vùng đọc ngoài hợp đồng: {a1}")
        return self._doc({"startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": cot})

    def get_all_values(self) -> list:
        return self._doc({})


def _tim_tab(sh, chot: sd.DichGuiChot):
    """Tab của đích: THEO MÃ khi đã ghim; chưa có mã (hồ sơ link cũ) thì theo TÊN — thiếu tab tên đó là lỗi cấu
    hình riêng, KHÔNG phải «tab đã ghim theo mã» của ``phan_loai_loi`` (audit B-9). Không tự tạo tab (M2)."""
    import gspread

    if chot.worksheet_id is not None:
        return sh.get_worksheet_by_id(chot.worksheet_id)
    try:
        return sh.worksheet(chot.worksheet_ten)
    except gspread.exceptions.WorksheetNotFound:
        raise ChuaGui(f"Bảng không có tab tên «{chot.worksheet_ten}» — tool không tự tạo tab: hãy tạo tab đó "
                      "(hoặc sửa hồ sơ sang tab khác).", tam_thoi=False) from None


class CongGspread:
    """Transport thật. Mỗi lần gửi: mở bảng (metadata) → tab THEO MÃ (theo tên chỉ khi revision chưa từng phát — để
    TÌM mã) → kiểm tiêu đề NGHIÊM NGẶT, đọc THEO MÃ → ``truoc_khi_gui(mã_tab, tên_tab)`` (người gửi đối chiếu rồi
    commit ghim + SENDING; ném lỗi = huỷ, chưa ghi gì) → MỘT ``spreadsheets.batchUpdate`` ``AppendCells{sheetId}``.
    Sau bước tìm tab, KHÔNG request nào mang tên tab (MR-R2-P1-01). Timeout (kết nối 10 s, đọc 60 s); không thử lại
    bên trong (HTTPClient mặc định của gspread không backoff)."""

    THOI_GIAN_CHO = (10, 60)

    def __init__(self):
        self._khach: dict = {}

    def _client(self, duong_dan_khoa: str):
        import gspread

        try:
            moc = os.stat(duong_dan_khoa).st_mtime_ns
        except OSError:
            moc = 0
        khoa = (os.path.normcase(os.path.abspath(duong_dan_khoa)), moc)
        client = self._khach.get(khoa)
        if client is None:
            client = gspread.service_account(filename=duong_dan_khoa)
            client.set_timeout(self.THOI_GIAN_CHO)
            self._khach = {khoa: client}
        return client

    def kiem(self, chot: sd.DichGuiChot, duong_dan_khoa: str, header: list, *,
             ten_doi_chieu: str = "") -> tuple:
        """«Kiểm cấu hình (chỉ đọc)»: mở bảng, tab THEO ID, hàng tiêu đề — KHÔNG tạo tab, không chèn
        tiêu đề, không ghi dòng thử. Đọc được chỉ chứng minh đọc được, chưa chứng minh quyền ghi.
        ``ten_doi_chieu``: tab tìm theo mã phải mang đúng tên này (hồ sơ chưa gửi thành công lần nào)."""
        import sheets

        try:
            sh = self._client(duong_dan_khoa).open_by_key(chot.spreadsheet_id)
            ws = _tim_tab(sh, chot)
            if ten_doi_chieu and ws.title != ten_doi_chieu:
                return False, (f"Tab mã {ws.id} hiện tên «{ws.title}», khác tên đối chiếu "
                               f"«{ten_doi_chieu}» của hồ sơ — kiểm lại link/tên tab.")
            trong = sheets.kiem_tieu_de_nghiem_ngat(_TabTheoMa(sh, ws.id), header, ws.title)
        except Exception as e:  # noqa: BLE001 — chỉ đọc: mọi lỗi là "chưa gửi"
            loi = _kem_ngu_canh(phan_loai_loi(e, da_phat=False), e, chot)
            return False, getattr(loi, "ly_do", str(loi))
        return True, (f"Đã đọc được tab «{ws.title}» (mã {ws.id}): "
                      + ("trang tính trống — lần gửi đầu sẽ ghi hàng tiêu đề." if trong
                         else "hàng tiêu đề đúng.")
                      + " Lưu ý: kiểm chỉ đọc KHÔNG xác minh quyền ghi.")

    def gui(self, chot: sd.DichGuiChot, duong_dan_khoa: str, header: list, rows: list,
            truoc_khi_gui: Callable[[], None]) -> KetQuaGui:
        import sheets

        try:
            sh = self._client(duong_dan_khoa).open_by_key(chot.spreadsheet_id)
            ws = _tim_tab(sh, chot)
            gid, ten = int(ws.id), str(ws.title)
            # Từ đây chỉ dùng MÃ tab; tên chỉ còn là nhãn (đối chiếu, hiển thị) — không request nào mang nó.
            can_tieu_de = sheets.kiem_tieu_de_nghiem_ngat(_TabTheoMa(sh, gid), header, ten)
            yeu_cau = dung_yeu_cau_ghi(gid, ([list(header)] if can_tieu_de else []) + [list(r) for r in rows],
                                       ws.col_count)
        except Exception as e:  # noqa: BLE001 — trước dispatch: chưa có request ghi nào
            raise _kem_ngu_canh(phan_loai_loi(e, da_phat=False), e, chot) from None
        truoc_khi_gui(gid, ten)                      # có thể ném ChuaGui/MatQuyen — chưa ghi gì
        try:
            phan_hoi = sh.batch_update(yeu_cau)
        except Exception as e:  # noqa: BLE001
            raise phan_loai_loi(e, da_phat=True) from None
        return KetQuaGui(phan_hoi, yeu_cau, ten)
