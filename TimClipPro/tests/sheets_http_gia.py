# -*- coding: utf-8 -*-
"""Máy chủ Google Sheets GIẢ ở tầng HTTP — thay ``requests.Session`` cho gspread THẬT:
``gspread.Client(auth=None, session=MayChuSheetsGia(...))``. Không mạng, không khoá thật.

Mô hình theo ngữ nghĩa CÔNG KHAI của Sheets API v4 mà transport của outbox dựa vào (MR-R2-P1-01, tái audit
78ba20c — gspread 6.2.1 ``Worksheet.append_rows`` dựng range A1 từ ``self.title``):

* ``GET spreadsheets/{id}`` (metadata): danh sách tab ``sheetId``/``title``/``gridProperties``.
* ``values.get`` / ``values.append``: định tuyến theo A1 — TÊN tab tại thời điểm request TỚI. Tab đổi tên rồi tab
  khác mang tên cũ giữa hai request thì request sau rơi vào tab mang tên đó lúc ấy. Tên không có → 400.
* ``values:batchGetByDataFilter`` với ``gridRange.sheetId``: định tuyến theo MÃ tab; mã không có → 400.
* ``spreadsheets.batchUpdate``: NGUYÊN TỬ ("If any request is not valid then the entire request will fail and
  nothing will be applied"), áp theo thứ tự, ``replies`` 1:1 (AppendCells/AppendDimension: reply rỗng).
  AppendCells: "after the last row with data in a sheet, inserting new rows" — tài liệu KHÔNG hứa nới cột, nên mô
  hình bảo thủ: ghi quá số cột → 400.
* RAW (``values.append``): chuỗi → chuỗi (không phân tích công thức), số → số, bool → bool, ``""`` → ô trống,
  ``null`` → bỏ qua. Đọc FORMATTED_VALUE: số nguyên không có ".0", bool → TRUE/FALSE; bỏ ô/dòng trống ở cuối.

Móc ``moc(su_kien, yc)``: ``"den"`` (request tới, CHƯA xử lý) và ``"xong"`` (đã áp dụng, CHƯA trả phản hồi) — test
chen thao tác quản trị (đổi tên/tạo/xoá tab) hoặc ném lỗi mạng đúng thời điểm (ném ở "xong" = máy chủ ĐÃ ghi rồi
phản hồi mất). ``nhat_ky``: mọi request đã tới (kể cả request bị móc chặn), theo thứ tự.
"""
import copy
import json as jsonlib
import re
from typing import Callable, Optional
from urllib.parse import unquote, urlsplit

import requests

GOC = "https://sheets.googleapis.com/v4/spreadsheets/"
_LY_DO = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found", 408: "Request Timeout",
          429: "Too Many Requests", 500: "Internal Server Error", 502: "Bad Gateway",
          503: "Service Unavailable"}
_TRANG_THAI = {400: "INVALID_ARGUMENT", 403: "PERMISSION_DENIED", 404: "NOT_FOUND", 429: "RESOURCE_EXHAUSTED",
               500: "INTERNAL", 503: "UNAVAILABLE"}


class LoiHttp(Exception):
    """Máy chủ trả lỗi HTTP (``ma``) — thành ``requests.Response`` lỗi, gspread tự ném ``APIError``."""

    def __init__(self, ma: int, thong_diep: str):
        super().__init__(thong_diep)
        self.ma, self.thong_diep = ma, thong_diep


def phan_hoi(ma: int, du_lieu: dict, url: str = GOC) -> requests.Response:
    r = requests.models.Response()
    r.status_code = ma
    r._content = jsonlib.dumps(du_lieu, ensure_ascii=False).encode("utf-8")
    r.headers["Content-Type"] = "application/json; charset=UTF-8"
    r.encoding = "utf-8"
    r.url = url
    r.reason = _LY_DO.get(ma, "")
    return r


def phan_hoi_loi(ma: int, thong_diep: str, url: str = GOC) -> requests.Response:
    return phan_hoi(ma, {"error": {"code": ma, "message": thong_diep,
                                   "status": _TRANG_THAI.get(ma, "UNKNOWN")}}, url)


def _o_raw(v):
    """Ô ghi bằng ``values.append`` RAW → ô lưu: ``None`` (trống) | ``("s"|"n"|"b", giá trị)``."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return ("b", v)
    if isinstance(v, (int, float)):
        return ("n", float(v))
    if isinstance(v, str):
        return ("s", v)
    raise LoiHttp(400, f"Invalid values: kiểu {type(v).__name__}")


def _o_cell_data(cd, i: int):
    """``CellData`` của AppendCells (``fields: userEnteredValue``) → ô lưu."""
    if not isinstance(cd, dict):
        raise LoiHttp(400, f"Invalid requests[{i}].appendCells: CellData không phải đối tượng")
    uev = cd.get("userEnteredValue")
    if uev is None:
        return None
    if not isinstance(uev, dict) or len(uev) != 1:
        raise LoiHttp(400, f"Invalid requests[{i}].appendCells: ExtendedValue phải có đúng một kiểu")
    (kieu, gt), = uev.items()
    if kieu == "stringValue" and isinstance(gt, str):
        return None if gt == "" else ("s", gt)
    if kieu == "numberValue" and isinstance(gt, (int, float)) and not isinstance(gt, bool):
        return ("n", float(gt))
    if kieu == "boolValue" and isinstance(gt, bool):
        return ("b", gt)
    if kieu == "formulaValue" and isinstance(gt, str):
        return ("f", gt)
    raise LoiHttp(400, f"Invalid requests[{i}].appendCells: ExtendedValue {kieu} không hợp lệ")


def dinh_dang(o) -> str:
    """FORMATTED_VALUE của một ô lưu (mô hình định dạng «Tự động»)."""
    kieu, gt = o
    if kieu == "n":
        return str(int(gt)) if gt == int(gt) else repr(gt)
    if kieu == "b":
        return "TRUE" if gt else "FALSE"
    return gt


def _cot_a1(so: int) -> str:
    chu = ""
    while so > 0:
        so, du = divmod(so - 1, 26)
        chu = chr(65 + du) + chu
    return chu


def _so_cot(chu: str) -> int:
    so = 0
    for ch in chu:
        so = so * 26 + ord(ch) - 64
    return so


def tach_a1(rng: str) -> tuple:
    """``'Tên ''x'''!A1:AH1`` → ``("Tên 'x'", "A1:AH1")``; ``'Tên'`` → ``("Tên", None)``."""
    if not rng.startswith("'"):
        ten, _, phan = rng.partition("!")
        return ten, (phan or None)
    i, ten = 1, ""
    while True:
        j = rng.index("'", i)
        if rng.startswith("''", j):
            ten, i = ten + rng[i:j] + "'", j + 2
        else:
            ten, i = ten + rng[i:j], j + 1
            break
    return ten, (rng[i + 1:] if rng.startswith("!", i) else None)


def _vung_a1(phan: Optional[str]) -> dict:
    """``A1:AH1`` → gridRange (chỉ số 0, đầu-mở-cuối-đóng); ``None`` → cả trang tính."""
    if phan is None:
        return {}
    m = re.fullmatch(r"([A-Z]+)(\d*)(?::([A-Z]+)(\d*))?", phan)
    if m is None:
        raise LoiHttp(400, f"Unable to parse range: {phan}")
    c0, r0, c1, r1 = m.groups()
    vung = {"startColumnIndex": _so_cot(c0) - 1, "endColumnIndex": _so_cot(c1 or c0)}
    if r0:
        vung["startRowIndex"] = int(r0) - 1
    if r1 or r0:
        vung["endRowIndex"] = int(r1 or r0)
    return vung


class TabGia:
    def __init__(self, gid: int, ten: str, hang=None, so_cot: int = 26, so_dong: int = 1000):
        self.gid, self.ten, self.so_cot, self.so_dong = gid, ten, so_cot, so_dong
        self.o: dict = {}                                    # (dòng, cột) -> ô lưu
        for r, dong in enumerate(hang or []):
            for c, v in enumerate(dong):
                cell = _o_raw(v)
                if cell is not None:
                    self.o[(r, c)] = cell
        self.so_cot = max(self.so_cot, max((c + 1 for _, c in self.o), default=0))

    def dong_cuoi(self) -> int:
        """Số dòng tính tới dòng CUỐI có dữ liệu (AppendCells/values.append ghi ngay sau đó)."""
        return max((r for r, _ in self.o), default=-1) + 1

    def ghi_hang(self, tu_dong: int, hang: list) -> None:
        for k, dong in enumerate(hang):
            for c, cell in enumerate(dong):
                if cell is None:
                    self.o.pop((tu_dong + k, c), None)
                else:
                    self.o[(tu_dong + k, c)] = cell
        self.so_dong = max(self.so_dong, tu_dong + len(hang))

    def doc(self, vung: dict) -> list:
        r0, r1 = vung.get("startRowIndex", 0), vung.get("endRowIndex", self.so_dong)
        c0, c1 = vung.get("startColumnIndex", 0), vung.get("endColumnIndex", self.so_cot)
        bang = []
        for r in range(r0, min(r1, self.so_dong)):
            dong = [dinh_dang(self.o[(r, c)]) if (r, c) in self.o else "" for c in range(c0, min(c1, self.so_cot))]
            while dong and dong[-1] == "":
                dong.pop()
            bang.append(dong)
        while bang and not bang[-1]:
            bang.pop()
        return bang

    def a1(self, vung: dict) -> str:
        ten = "'" + self.ten.replace("'", "''") + "'"
        r0, r1 = vung.get("startRowIndex", 0), vung.get("endRowIndex", self.so_dong)
        c0, c1 = vung.get("startColumnIndex", 0), vung.get("endColumnIndex", self.so_cot)
        return f"{ten}!{_cot_a1(c0 + 1)}{r0 + 1}:{_cot_a1(c1)}{r1}"

    def du_lieu(self) -> list:
        """Mọi dòng (giá trị đã định dạng) — để test so nội dung."""
        return self.doc({})

    def hang_kieu(self) -> list:
        """Mọi dòng dạng ô lưu có KIỂU — để test so kiểu giá trị (RAW ↔ AppendCells)."""
        n = self.dong_cuoi()
        so_c = max((c + 1 for _, c in self.o), default=0)
        return [[self.o.get((r, c)) for c in range(so_c)] for r in range(n)]


class MayChuSheetsGia:
    """Một ``requests.Session`` giả: mọi request của gspread đi vào ``request()`` (không có socket nào)."""

    def __init__(self, spreadsheet_id: str, tabs=(), *, ten_bang: str = "Bảng giả"):
        self.spreadsheet_id = spreadsheet_id
        self.ten_bang = ten_bang
        self.tabs: dict = {}                       # gid -> TabGia (giữ thứ tự tạo = thứ tự tab)
        for t in tabs:
            self.tabs[t.gid] = t
        self.nhat_ky: list = []
        self.timeouts: list = []
        self.headers: dict = {}
        self.moc: Optional[Callable] = None
        self.loi_mo: Optional[LoiHttp] = None      # lỗi HTTP cho mọi request (vd. 403 bảng chưa chia sẻ)
        # Tài liệu không nói batchGetByDataFilter trả gì khi bộ lọc không khớp: bật để thử ca "không trả vùng nào".
        self.khong_tra_vung = False

    # ---------- thao tác quản trị của người dùng (giữa hai request) ----------

    def tab(self, gid: int) -> TabGia:
        return self.tabs[gid]

    def theo_ten(self, ten: str) -> Optional[TabGia]:
        return next((t for t in self.tabs.values() if t.ten == ten), None)

    def doi_ten(self, gid: int, ten: str) -> None:
        if self.theo_ten(ten) is not None:
            raise AssertionError(f"tên tab «{ten}» đã có")
        self.tabs[gid].ten = ten

    def them_tab(self, gid: int, ten: str, hang=None, so_cot: int = 26) -> TabGia:
        if gid in self.tabs or self.theo_ten(ten) is not None:
            raise AssertionError("mã/tên tab đã có")
        self.tabs[gid] = TabGia(gid, ten, hang, so_cot=so_cot)
        return self.tabs[gid]

    def xoa_tab(self, gid: int) -> None:
        del self.tabs[gid]

    # ---------- giao diện requests.Session ----------

    def request(self, method, url, json=None, params=None, data=None, files=None, headers=None,
                timeout=None, **kw):
        self.timeouts.append(timeout)
        method = method.upper()
        if json is not None:
            # Như ``requests``: thân request đi qua dây là JSON CHUẨN (``allow_nan=False`` — NaN/vô cực ném
            # ValueError ngay ở phía client, trước khi có byte nào được gửi).
            json = jsonlib.loads(jsonlib.dumps(json, allow_nan=False))
        yc = self._phan_loai(method, url, json, params)
        self.nhat_ky.append(yc)
        try:
            if self.moc is not None:
                self.moc("den", yc)              # móc ném LoiHttp = máy chủ trả lỗi HTTP; ném lỗi khác = lỗi mạng
            if self.loi_mo is not None:
                raise self.loi_mo
            du_lieu = self._xu_ly(yc)
        except LoiHttp as e:
            return phan_hoi_loi(e.ma, e.thong_diep, url)
        if self.moc is not None:
            self.moc("xong", yc)
        return phan_hoi(200, du_lieu, url)

    def close(self):
        pass

    # ---------- định tuyến ----------

    def _phan_loai(self, method, url, body, params) -> dict:
        duong = urlsplit(url).path
        assert duong.startswith("/v4/spreadsheets/"), url
        sau = duong[len("/v4/spreadsheets/"):]
        yc = {"method": method, "url": url, "body": copy.deepcopy(body),
              "params": {k: v for k, v in (params or {}).items() if v is not None}}
        if method == "POST" and sau.endswith(":batchUpdate"):
            return {**yc, "loai": "batchUpdate", "sid": sau[:-len(":batchUpdate")]}
        sid, _, phan = sau.partition("/")
        yc["sid"] = sid
        if method == "GET" and phan == "":
            return {**yc, "loai": "metadata"}
        if method == "POST" and phan == "values:batchGetByDataFilter":
            return {**yc, "loai": "batchGetByDataFilter"}
        if phan.startswith("values/"):
            rng = phan[len("values/"):]
            if method == "POST" and rng.endswith(":append"):
                return {**yc, "loai": "values_append", "range": unquote(rng[:-len(":append")])}
            if method == "GET":
                return {**yc, "loai": "values_get", "range": unquote(rng)}
        raise AssertionError(f"endpoint ngoài mô hình: {method} {url}")

    def _xu_ly(self, yc: dict) -> dict:
        if yc["sid"] != self.spreadsheet_id:
            raise LoiHttp(404, "Requested entity was not found.")
        return getattr(self, "_" + yc["loai"])(yc)

    def _tab_theo_ten(self, rng: str) -> tuple:
        ten, phan = tach_a1(rng)
        t = self.theo_ten(ten)
        if t is None:
            raise LoiHttp(400, f"Unable to parse range: {rng}")
        return t, _vung_a1(phan)

    def _metadata(self, yc):
        return {"spreadsheetId": self.spreadsheet_id,
                "properties": {"title": self.ten_bang, "locale": "vi_VN", "timeZone": "Asia/Ho_Chi_Minh"},
                "sheets": [{"properties": {"sheetId": t.gid, "title": t.ten, "index": i, "sheetType": "GRID",
                                           "gridProperties": {"rowCount": t.so_dong, "columnCount": t.so_cot}}}
                           for i, t in enumerate(self.tabs.values())]}

    def _values_get(self, yc):
        t, vung = self._tab_theo_ten(yc["range"])
        kq = {"range": t.a1(vung), "majorDimension": "ROWS"}
        bang = t.doc(vung)
        if bang:
            kq["values"] = bang
        return kq

    def _values_append(self, yc):
        t, _ = self._tab_theo_ten(yc["range"])
        if yc["params"].get("valueInputOption") != "RAW":
            raise AssertionError("mô hình chỉ có values.append RAW")
        hang = [[_o_raw(v) for v in dong] for dong in (yc["body"] or {}).get("values", [])]
        tu = t.dong_cuoi()
        rong = max((len(d) for d in hang), default=0)
        t.so_cot = max(t.so_cot, rong)                       # values.append tự nới cột
        t.ghi_hang(tu, hang)
        vung = {"startRowIndex": tu, "endRowIndex": tu + len(hang), "startColumnIndex": 0, "endColumnIndex": rong}
        return {"spreadsheetId": self.spreadsheet_id, "tableRange": t.a1({"endRowIndex": max(tu, 1)}),
                "updates": {"spreadsheetId": self.spreadsheet_id, "updatedRange": t.a1(vung),
                            "updatedRows": len(hang), "updatedColumns": rong,
                            "updatedCells": sum(len(d) for d in hang)}}

    def _batchGetByDataFilter(self, yc):
        ket = []
        for i, df in enumerate((yc["body"] or {}).get("dataFilters", [])):
            vung = dict((df or {}).get("gridRange") or {})
            gid = vung.pop("sheetId", None)
            if gid not in self.tabs or self.khong_tra_vung:
                if self.khong_tra_vung:
                    continue
                raise LoiHttp(400, f"Invalid dataFilters[{i}]: No grid with id: {gid}")
            t = self.tabs[gid]
            vr = {"range": t.a1(vung), "majorDimension": "ROWS"}
            bang = t.doc(vung)
            if bang:
                vr["values"] = bang
            ket.append({"valueRange": vr, "dataFilters": [df]})
        return {"spreadsheetId": self.spreadsheet_id, "valueRanges": ket}

    def _batchUpdate(self, yc):
        requests_ = (yc["body"] or {}).get("requests")
        if not isinstance(requests_, list) or not requests_:
            raise LoiHttp(400, "Invalid requests: rỗng")
        nhap = copy.deepcopy(self.tabs)                      # NGUYÊN TỬ: áp lên bản nháp, lỗi → bỏ cả bản nháp
        for i, r in enumerate(requests_):
            (loai, tham), = r.items()
            if loai == "appendDimension":
                t = nhap.get(tham.get("sheetId"))
                if t is None:
                    raise LoiHttp(400, f"Invalid requests[{i}].appendDimension: No grid with id: "
                                       f"{tham.get('sheetId')}")
                if tham.get("dimension") == "COLUMNS":
                    t.so_cot += int(tham["length"])
                elif tham.get("dimension") == "ROWS":
                    t.so_dong += int(tham["length"])
                else:
                    raise LoiHttp(400, f"Invalid requests[{i}].appendDimension: dimension")
            elif loai == "appendCells":
                if not tham.get("fields"):
                    raise LoiHttp(400, f"Invalid requests[{i}].appendCells: At least one field must be specified.")
                if "tableId" in tham:
                    raise AssertionError("mô hình không có tableId")
                t = nhap.get(tham.get("sheetId"))
                if t is None:
                    raise LoiHttp(400, f"Invalid requests[{i}].appendCells: No grid with id: "
                                       f"{tham.get('sheetId')}")
                hang = [[_o_cell_data(cd, i) for cd in (rd or {}).get("values", [])]
                        for rd in tham.get("rows", [])]
                if any(len(d) > t.so_cot for d in hang):
                    raise LoiHttp(400, f"Invalid requests[{i}].appendCells: vượt quá {t.so_cot} cột của lưới")
                t.ghi_hang(t.dong_cuoi(), hang)
            else:
                raise AssertionError(f"request batchUpdate ngoài mô hình: {loai}")
        self.tabs = nhap
        return {"spreadsheetId": self.spreadsheet_id, "replies": [{} for _ in requests_]}


def moc_mot_lan(dieu_kien: Callable, viec: Callable) -> Callable:
    """Móc chạy ``viec(su_kien, yc)`` đúng MỘT lần, ở request đầu tiên thoả ``dieu_kien(su_kien, yc)``."""
    da = {"chay": False}

    def moc(su_kien, yc):
        if not da["chay"] and dieu_kien(su_kien, yc):
            da["chay"] = True
            viec(su_kien, yc)
    return moc


DOC = ("values_get", "batchGetByDataFilter")         # request ĐỌC nội dung tab (mã cũ: theo tên; mã mới: theo mã)
GHI = ("values_append", "batchUpdate")               # request GHI (mã cũ: values.append theo tên; mã mới: theo mã)
