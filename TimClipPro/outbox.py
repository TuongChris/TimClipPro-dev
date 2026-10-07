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
* Khởi động người gửi: ``CLAIMED`` (chưa dispatch) → ``PENDING``; ``SENDING`` của chủ cũ →
  ``UNKNOWN_DELIVERY`` (KHÔNG suy "chưa ghi" từ việc tiến trình đã chết).
* ``SENT`` chỉ khi biên nhận khớp: ``spreadsheetId`` đúng, số dòng đúng, ``updatedRange`` thuộc đúng tab
  vừa kiểm theo ID. Bất thường → ``UNKNOWN_DELIVERY``.
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
    """CHẮC CHẮN Google chưa ghi. ``tam_thoi`` → thử lại có hạn mức; không → chặn tới khi sửa."""

    def __init__(self, ly_do: str, *, tam_thoi: bool):
        super().__init__(ly_do)
        self.ly_do = ly_do
        self.tam_thoi = tam_thoi


class KhongRo(Exception):
    """Request có thể đã tới Google mà kết quả không rõ — KHÔNG được gửi lại tự động."""

    def __init__(self, ly_do: str):
        super().__init__(ly_do)
        self.ly_do = ly_do


class MatQuyen(Exception):
    """Claim đã bị người khác lấy trước dispatch — bỏ lần gửi này, không ghi gì."""


@dataclass(frozen=True)
class KetQuaGui:
    """Transport trả về: phản hồi THÔ của Sheets API + tab thật đã ghi + số dòng đã gửi."""

    phan_hoi: object
    worksheet_id: int
    worksheet_ten: str
    so_dong_gui: int


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
             "gui_luc")


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


def _doi_trang_thai_tay(db_path: str, viec_id: str, tu: tuple, den: str, **them) -> None:
    with sd.ket_noi(db_path, ghi=True) as con:
        h = con.execute("SELECT trang_thai FROM hang_doi_gui WHERE id=?", (viec_id,)).fetchone()
        if h is None:
            raise LoiHangDoi("Không thấy việc gửi này.")
        if h["trang_thai"] not in tu:
            raise LoiHangDoi(f"Việc đang ở trạng thái «{NHAN_TRANG_THAI.get(h['trang_thai'])}» — "
                             "không làm được thao tác này.")
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
    """UNKNOWN → PENDING theo xác nhận của người dùng: chấp nhận khả năng trùng dòng."""
    _doi_trang_thai_tay(db_path, viec_id, (UNKNOWN,), PENDING, so_lan_thu=0, thu_lai_sau=0.0,
                        loi="Gửi lại theo xác nhận của người dùng (có thể trùng dòng).")


def huy(db_path: str, viec_id: str) -> None:
    """Huỷ việc chưa ở trong tay người gửi. Đang gửi/đã gửi thì không huỷ được."""
    _doi_trang_thai_tay(db_path, viec_id,
                        (PENDING, RETRY_WAIT, BLOCKED_CONFIG, BLOCKED_REPORT, UNKNOWN), CANCELLED)


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
        da_co = [h["dich_json"] for h in con.execute(
            "SELECT dich_json FROM hang_doi_gui WHERE job_id=? AND trang_thai != ?",
            (job_id, CANCELLED))]
        if not cho_phep_trung and any(_co_the_cung_tab(con, x, y_dinh.dich) for x in da_co):
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


def _co_the_cung_tab(con, dich_json: str, moi: sd.DichGuiChot) -> bool:
    """Việc đã có (``dich_json``) CÓ THỂ ghi vào cùng tab với đích ``moi``? Không chắc → coi là có."""
    try:
        cu = sd.DichGuiChot.from_json(dich_json)
    except sd.LoiDichGui:
        return True
    if cu.spreadsheet_id != moi.spreadsheet_id:
        return False
    a, b = _khoa_tab(con, cu), _khoa_tab(con, moi)
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


# ---------------------------------------------------------------------------
#  Người gửi
# ---------------------------------------------------------------------------

def _thoi_gian_cho(so_lan: int) -> float:
    return float(min(60 * 2 ** max(0, so_lan - 1), 3600))


def _nhom(chot: sd.DichGuiChot) -> tuple:
    """Các việc cùng bảng + tab + khoá + lược đồ: lỗi cấu hình của một việc là của cả nhóm."""
    return (chot.spreadsheet_id, chot.worksheet_id if chot.worksheet_id is not None
            else "ten:" + chot.worksheet_ten, chot.xac_thuc_ref, chot.schema_id)


def _ten_tab_trong_range(rng: str) -> Optional[str]:
    if "!" not in rng:
        return None
    ten = rng.rsplit("!", 1)[0]
    if len(ten) >= 2 and ten[0] == "'" and ten[-1] == "'":
        ten = ten[1:-1].replace("''", "'")
    return ten


def kiem_bien_nhan(kq: KetQuaGui, chot: sd.DichGuiChot) -> tuple:
    """``(hợp_lệ, lý_do, biên_nhận_dict)`` — chỉ hợp lệ khi phản hồi chứng minh đúng bảng, đúng tab,
    đúng số dòng đã gửi."""
    ph = kq.phan_hoi
    if not isinstance(ph, dict):
        return False, "phản hồi không phải đối tượng JSON", {}
    up = ph.get("updates") if isinstance(ph.get("updates"), dict) else {}
    sid = ph.get("spreadsheetId")
    if sid != chot.spreadsheet_id or up.get("spreadsheetId", sid) != chot.spreadsheet_id:
        return False, "phản hồi mang mã bảng khác", {}
    if up.get("updatedRows") != kq.so_dong_gui:
        return False, (f"phản hồi báo {up.get('updatedRows')} dòng, đã gửi "
                       f"{kq.so_dong_gui}"), {}
    rng = up.get("updatedRange")
    if not isinstance(rng, str) or _ten_tab_trong_range(rng) != kq.worksheet_ten:
        return False, "vùng ghi không thuộc tab đã kiểm", {}
    if chot.worksheet_id is not None and kq.worksheet_id != chot.worksheet_id:
        return False, "đã ghi vào tab khác mã đã ghim", {}
    return True, "", {"spreadsheet_id": sid, "worksheet_id": kq.worksheet_id,
                      "worksheet_ten": kq.worksheet_ten, "updated_range": rng,
                      "updated_rows": up.get("updatedRows"), "luc": time.time()}


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
            self.phuc_hoi()
        except BaseException:
            self.tha_quyen()
            raise
        return True

    def tha_quyen(self) -> None:
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

    # ---------- vòng gửi ----------

    def chay_mot_vong(self) -> dict:
        if self._khoa is None:
            raise RuntimeError("Chưa giữ quyền người gửi — không được gửi.")
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
            dem[ket] = dem.get(ket, 0) + 1
            if ket == "bi_chan" and nhom is not None:
                bi_chan_vong.add(nhom)
        return dem

    def _claim(self, viec_id: str, bay_gio: float) -> Optional[str]:
        token = uuid.uuid4().hex
        with sd.ket_noi(self.db_path, ghi=True) as con:
            n = con.execute(
                "UPDATE hang_doi_gui SET trang_thai=?, claim_token=?, chu_so_huu=?, claim_luc=?,"
                " so_lan_thu=so_lan_thu+1, sua_luc=? WHERE id=? AND trang_thai IN (?,?)"
                " AND thu_lai_sau <= ?",
                (CLAIMED, token, self.chu, bay_gio, time.time(), viec_id, *CO_THE_CLAIM,
                 bay_gio)).rowcount
        return token if n == 1 else None

    def _chot(self, viec_id: str, token: str, trang_thai: str, **cot) -> bool:
        """Cập nhật cuối có fencing: chỉ khi claim vẫn là của mình."""
        gia_tri = {"trang_thai": trang_thai, "sua_luc": time.time(), **cot}
        if trang_thai not in DANG_BAY:
            gia_tri.update(claim_token="", chu_so_huu="")
        with sd.ket_noi(self.db_path, ghi=True) as con:
            n = con.execute(
                f"UPDATE hang_doi_gui SET {', '.join(f'{k}=?' for k in gia_tri)}"
                " WHERE id=? AND claim_token=?", (*gia_tri.values(), viec_id, token)).rowcount
        if n != 1:
            LOGGER.error("event=outbox.fencing_lost id=%s state=%s", viec_id[:12], trang_thai)
        return n == 1

    def _bat_dau_gui(self, viec_id: str, token: str) -> None:
        """Điểm không quay lại: COMMIT ``SENDING`` rồi transport mới được phát request ghi."""
        with sd.ket_noi(self.db_path, ghi=True) as con:
            n = con.execute(
                "UPDATE hang_doi_gui SET trang_thai=?, gui_luc=?, sua_luc=? WHERE id=?"
                " AND claim_token=? AND trang_thai=?",
                (SENDING, time.time(), time.time(), viec_id, token, CLAIMED)).rowcount
        if n != 1:
            raise MatQuyen(viec_id)

    @staticmethod
    def _viec_cung_nhom(con, nhom: tuple, tru_id: str) -> list:
        ids = []
        for h in con.execute("SELECT id, dich_json FROM hang_doi_gui WHERE trang_thai IN (?,?)"
                             " AND id != ?", (*CO_THE_CLAIM, tru_id)):
            with contextlib.suppress(sd.LoiDichGui):
                if _nhom(sd.DichGuiChot.from_json(h["dich_json"])) == nhom:
                    ids.append(h["id"])
        return ids

    def _chan_nhom(self, nhom: tuple, ly_do: str, tru_id: str) -> None:
        """Lỗi cấu hình: chặn luôn các việc CHỜ khác cùng nhóm — không đập vào bảng lỗi từng việc."""
        with sd.ket_noi(self.db_path, ghi=True) as con:
            for vid in self._viec_cung_nhom(con, nhom, tru_id):
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
            return "bo_qua"
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
        ly_do_khoa, duong_dan_khoa = self._kiem_khoa(chot)
        if ly_do_khoa:
            self._chot(viec_id, token, BLOCKED_CONFIG, loi=ly_do_khoa)
            if nhom is not None:
                self._chan_nhom(nhom, ly_do_khoa, viec_id)
            return "bi_chan"
        chot_gui, da_chot = self._tab_gui(chot)
        da_phat = {"co": False}

        def truoc_khi_gui(gid: int, ten: str) -> None:
            # Transport đã tìm được tab (theo mã/tên) và kiểm tiêu đề, CHƯA ghi gì. Revision chưa từng
            # gửi thành công + hồ sơ có mã tab → tên tab phải khớp tên đối chiếu (dán nhầm link tab).
            if da_chot is None and chot.worksheet_id is not None and ten != chot.worksheet_ten:
                raise ChuaGui(f"Tab mã {gid} hiện tên «{ten}», khác tên đối chiếu «{chot.worksheet_ten}» "
                              "của hồ sơ — kiểm lại link/tên tab trong hồ sơ (chưa ghi gì).",
                              tam_thoi=False)
            self._bat_dau_gui(viec_id, token)
            da_phat["co"] = True

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
        hop_le, ly_do, bien_nhan = kiem_bien_nhan(kq, chot_gui)
        if not hop_le:
            self._chot(viec_id, token, UNKNOWN, loi=f"Biên nhận bất thường: {ly_do}.")
            return "khong_ro"
        self._chot(viec_id, token, SENT, loi="", bien_nhan=json.dumps(bien_nhan, ensure_ascii=False))
        if da_chot is None:
            # Chốt mã tab thật cho revision (lần đầu thắng) — mọi việc sau của revision gửi theo mã này.
            # Lỗi ghi ở đây không ảnh hưởng việc đã gửi; lần gửi sau sẽ chốt lại.
            with contextlib.suppress(Exception):
                sd.chot_tab(self.db_path, chot.dich_id, chot.phien_ban,
                            worksheet_id=kq.worksheet_id, worksheet_ten=kq.worksheet_ten)
        return "da_gui"

    def _xu_ly_chua_gui(self, v: ViecGui, token: str, nhom, e: ChuaGui, bay_gio: float) -> str:
        if not e.tam_thoi:
            self._chot(v.id, token, BLOCKED_CONFIG, loi=e.ly_do)
            if nhom is not None:
                self._chan_nhom(nhom, e.ly_do, v.id)
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

    def _tab_gui(self, chot: sd.DichGuiChot) -> tuple:
        """``(đích để gửi, tab đã chốt | None)``: revision đã gửi thành công → gửi theo MÃ đã chốt của
        chính revision đó (không đọc hồ sơ hiện tại, không tìm lại theo tên — tab đổi tên vẫn đúng chỗ,
        tab cùng tên tạo lại không bao giờ được coi là tab cũ)."""
        da_chot = sd.tab_da_chot(self.db_path, chot.dich_id, chot.phien_ban)
        if da_chot is None:
            return chot, None
        return replace(chot, worksheet_id=da_chot.worksheet_id), da_chot


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

    def start(self) -> None:
        with self._khoa_luong:
            if self._thread is not None and self._thread.is_alive():
                return
            if self.ban_cu:
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
                if self.nguoi_gui is None:
                    self.nguoi_gui = NguoiGui(self.db_path, self.data_dir, self._tao_cong(),
                                              dung=self._dung)
                cho = self.chu_ky_gianh_s
                # Bản mới đã kích hoạt mà tiến trình (app cũ) còn mở: NHƯỜNG quyền người gửi cho bản mới
                # và dừng hẳn — giữ quyền mà từ chối mọi việc thì Watch/CLI của bản mới không gửi được gì.
                ly_do = self.nguoi_gui.cong_bao_tri.ly_do_ban_cu() if isinstance(
                    self.nguoi_gui.cong_bao_tri, maintenance_gate.CongBaoTri) else ""
                if ly_do:
                    self._nhuong_cho_ban_moi(ly_do)
                    break
                try:
                    if self.nguoi_gui.co_quyen or self.nguoi_gui.nhan_quyen():
                        dem = self.nguoi_gui.chay_mot_vong()
                        if dem.get("ban_cu"):
                            self._nhuong_cho_ban_moi("cổng báo bản cũ")
                            break
                        # Còn việc vừa xử lý → vòng tiếp ngay; không thì chờ chu kỳ/đánh thức.
                        cho = 0.2 if (dem["da_gui"] or dem["thu_lai"]) else self.chu_ky_s
                    self.loi_cuoi = ""
                except Exception as e:  # noqa: BLE001 — luồng không được chết vì một vòng lỗi
                    self.loi_cuoi = f"{type(e).__name__}"
                    LOGGER.exception("event=outbox.round_failed")
                    cho = self.chu_ky_s
                self._thuc.wait(cho)
                self._thuc.clear()
        finally:
            if self.nguoi_gui is not None:
                self.nguoi_gui.tha_quyen()

    def _nhuong_cho_ban_moi(self, ly_do: str) -> None:
        self.ban_cu = ly_do or "bản cũ"
        self.loi_cuoi = "BanCu"
        LOGGER.warning("event=outbox.yield_to_active_release — tiến trình chạy bản đã bị thay, nhường quyền gửi")
        if self.nguoi_gui is not None:
            self.nguoi_gui.tha_quyen()
        self._dung.set()


_NEN: dict = {}
_NEN_KHOA = threading.RLock()
_DA_DANG_KY_THOAT = False


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
    ``RETRY_WAIT`` không bị chờ (đã hẹn giờ thử lại). ``han_s <= 0``: không khởi động người gửi, chỉ
    đếm. ``dung()`` trả True (yêu cầu dừng / Ctrl+C) → thôi chờ."""
    if han_s <= 0:
        return tom_tat(db_path, lo_id=lo_id)
    tu_tao = nen is None
    if tu_tao:
        nen = NguoiGuiNen(db_path, data_dir, tao_cong or CongGspread, chu_ky_s=2.0,
                          chu_ky_gianh_s=2.0)
        nen.start()
    bat_dau = time.monotonic()
    try:
        nen.danh_thuc()
        while True:
            tt = tom_tat(db_path, lo_id=lo_id)
            if tt[PENDING] + tt[CLAIMED] + tt[SENDING] == 0:
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


def _ma_http(e: BaseException) -> int:
    for ung_vien in (getattr(e, "code", None),
                     getattr(getattr(e, "response", None), "status_code", None)):
        if isinstance(ung_vien, int) and not isinstance(ung_vien, bool):
            return ung_vien
    return -1


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
        return ChuaGui("Tài khoản dịch vụ không có quyền mở bảng — chia sẻ bảng (Người chỉnh sửa) cho "
                       "địa chỉ của binding khoá.", tam_thoi=False)
    if isinstance(e, gspread.exceptions.WorksheetNotFound):
        return ChuaGui("Không thấy tab đã ghim (theo mã tab) — tab có thể đã bị xoá hoặc tạo lại; "
                       "không tự chọn tab khác.", tam_thoi=False)
    if isinstance(e, gspread.exceptions.SpreadsheetNotFound):
        return ChuaGui("Không mở được bảng tính — kiểm quyền chia sẻ cho tài khoản dịch vụ.",
                       tam_thoi=False)
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
            trang_thai = str(e.error.get("status") or "")[:40]
        mo_ta = f"Google trả lỗi HTTP {ma}{(' ' + trang_thai) if trang_thai else ''}"
        if ma == 429:
            return ChuaGui(mo_ta + " (quá hạn mức) — thử lại sau.", tam_thoi=True)
        if da_phat and (ma == 408 or ma < 400 or ma >= 500):
            return KhongRo(mo_ta + " sau khi gửi — không rõ Google đã ghi chưa.")
        if 400 <= ma < 500 and ma != 408:
            return ChuaGui(mo_ta + " — kiểm quyền/tab/cấu hình.", tam_thoi=False)
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


class CongGspread:
    """Transport thật. Mỗi lần gửi: mở bảng (metadata) → tab theo ID (hoặc theo tên khi chưa có mã) →
    kiểm tiêu đề NGHIÊM NGẶT → ``truoc_khi_gui(mã_tab, tên_tab)`` (người gửi đối chiếu rồi commit SENDING;
    ném lỗi = huỷ, chưa ghi gì) → MỘT ``append_rows`` RAW. Timeout (kết nối 10 s, đọc 60 s); không thử lại
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
            ws = (sh.get_worksheet_by_id(chot.worksheet_id) if chot.worksheet_id is not None
                  else sh.worksheet(chot.worksheet_ten))
            if ten_doi_chieu and ws.title != ten_doi_chieu:
                return False, (f"Tab mã {ws.id} hiện tên «{ws.title}», khác tên đối chiếu "
                               f"«{ten_doi_chieu}» của hồ sơ — kiểm lại link/tên tab.")
            trong = sheets.kiem_tieu_de_nghiem_ngat(ws, header, ws.title)
        except Exception as e:  # noqa: BLE001 — chỉ đọc: mọi lỗi là "chưa gửi"
            loi = phan_loai_loi(e, da_phat=False)
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
            ws = (sh.get_worksheet_by_id(chot.worksheet_id) if chot.worksheet_id is not None
                  else sh.worksheet(chot.worksheet_ten))
            can_tieu_de = sheets.kiem_tieu_de_nghiem_ngat(ws, header, ws.title)
        except Exception as e:  # noqa: BLE001 — trước dispatch: chưa có request ghi nào
            raise phan_loai_loi(e, da_phat=False) from None
        gia_tri = ([list(header)] if can_tieu_de else []) + [list(r) for r in rows]
        truoc_khi_gui(int(ws.id), str(ws.title))     # có thể ném ChuaGui/MatQuyen — chưa ghi gì
        try:
            phan_hoi = ws.append_rows(gia_tri, value_input_option="RAW")
        except Exception as e:  # noqa: BLE001
            raise phan_loai_loi(e, da_phat=True) from None
        return KetQuaGui(phan_hoi, int(ws.id), str(ws.title), len(gia_tri))
