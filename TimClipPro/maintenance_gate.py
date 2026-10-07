# -*- coding: utf-8 -*-
"""Cổng bảo trì — admission control giữa việc nghiệp vụ và updater (docs/MANAGED_RUNTIME_DESIGN.md §6-§7).

Vì sao
======
Updater chỉ được đổi mã khi KHÔNG việc nào đang chạy. "Không thấy Streamlit" hay đọc một PID cũ không đủ:
một lô quét có thể bắt đầu đúng giữa lúc updater kiểm rảnh và lúc kích hoạt. Cổng giải quyết bằng một
mutex ngắn chung cho cả hai phía:

* Việc (lô quét, lượt Watch, dựng kho, đồng bộ kênh, một lần gửi Sheets…) vào cổng: dưới mutex, kiểm cờ
  RÚT rồi tạo LEASE (file ``viec_<uuid>.lock`` giữ khoá HĐH) — giữ suốt việc, nhả khi xong/lỗi.
* Updater bật cờ rút DƯỚI CÙNG mutex → mọi việc vào cổng sau đó bị từ chối; việc đã vào thì lease đã có
  sẵn trên đĩa nên updater thấy. Rồi CHỜ CÓ HẠN cho hết lease; quá hạn thì huỷ rút, giữ bản cũ — không
  bao giờ giết việc.
* Khoá HĐH tự nhả khi tiến trình chết: lease/cờ rút mồ côi không chặn ai (cờ rút chỉ có hiệu lực khi
  updater còn giữ ``rut.lock``).

Thứ tự khoá: mutex của cổng chỉ giữ vài mili-giây và KHÔNG chờ khoá nào khi đang giữ; lease là file mới
(không ai tranh) — nên lấy được ở bất kỳ đâu mà không tạo vòng kẹt (§6).
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Callable, Optional

from khoa import DangChayRoi, KhoaTienTrinh

THU_MUC = "bao_tri"
TEN_MUTEX = "cong.lock"
TEN_CO_RUT = "rut.json"
TEN_KHOA_RUT = "rut.lock"
TIEN_TO_VIEC = "viec_"


class DangBaoTri(DangChayRoi):
    """Cổng đang đóng (chuẩn bị/áp dụng cập nhật, hoặc bản này đã bị thay) — việc mới không được nhận.
    Là một dạng "bận" (``DangChayRoi``): mọi chỗ đã báo "đang bận" cũ (CLI mã 2, Watch bỏ lượt, giao diện)
    báo đúng mà không phải sửa từng nơi. Thông báo tiếng Việt."""


class BanCu(DangBaoTri):
    """Tiến trình này chạy mã của release ĐÃ BỊ THAY (con trỏ ``current`` sang bản khác, hoặc con trỏ hỏng).
    Khác «đang rút cổng» (tạm thời): bản cũ không bao giờ nhận việc mới nữa — việc nền nên NHƯỜNG tài nguyên
    (vd. quyền người gửi Sheets) cho bản đang kích hoạt."""


class LoiCong(RuntimeError):
    """Không vào được mutex của cổng trong thời gian chờ (bất thường — mutex chỉ giữ vài mili-giây)."""


def ly_do_ban_cu(environ=None, *, rel_cua_toi: Optional[str] = None) -> str:
    """Managed: tiến trình này chạy mã của release X mà con trỏ ``current`` đã sang release khác → lý do
    từ chối việc MỚI (việc đang chạy vẫn chạy xong). Không phải managed / không chạy từ release → "".
    Con trỏ hỏng → từ chối (không đoán)."""
    environ = os.environ if environ is None else environ
    goc = environ.get("TIMCLIP_INSTALLATION_ROOT") or ""
    if environ.get("TIMCLIP_RUNTIME_MODE") != "managed" or not goc:
        return ""
    rel = os.path.abspath(rel_cua_toi or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not os.path.isfile(os.path.join(rel, "MANAGED_RELEASE.json")):
        return ""
    try:
        with open(os.path.join(goc, "update_state", "current.json"), encoding="utf-8") as f:
            cur = json.load(f)
    except FileNotFoundError:
        return ""
    except (OSError, ValueError):
        return ("Không đọc được con trỏ bản đang kích hoạt — chưa nhận việc mới; hãy mở lại ứng dụng bằng "
                "launcher.")
    kich_hoat = cur.get("release") if isinstance(cur, dict) else ""
    if kich_hoat and os.path.normcase(os.path.abspath(kich_hoat)) != os.path.normcase(rel):
        return ("Bản mới đã được kích hoạt — đóng và mở lại ứng dụng bằng launcher để dùng bản mới; bản "
                "đang mở không nhận việc mới (việc đang chạy vẫn chạy xong).")
    return ""


def _khoa_byte0(f) -> None:
    if sys.platform.startswith("win"):
        import msvcrt

        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _nha_byte0(f) -> None:
    if sys.platform.startswith("win"):
        import msvcrt

        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _thu_khoa(path: str):
    """Mở + khoá byte 0 KHÔNG chờ. Trả file đang giữ khoá, hoặc ``None`` nếu người khác giữ."""
    f = open(path, "a+", encoding="utf-8")
    try:
        f.seek(0, os.SEEK_END)
        if f.tell() == 0:
            f.write("\n")
            f.flush()
        _khoa_byte0(f)
    except OSError:
        f.close()
        return None
    except BaseException:
        f.close()
        raise
    return f


def _nha(f) -> None:
    try:
        with contextlib.suppress(OSError):
            _nha_byte0(f)
    finally:
        f.close()


def _doc_thong_tin(path: str) -> dict:
    """Thông tin chủ lease (dòng ``khoá: giá trị`` từ byte 1 — byte 0 là byte bị khoá)."""
    tt: dict = {}
    with contextlib.suppress(OSError), open(path, encoding="utf-8", errors="replace") as f:
        f.seek(1)
        for dong in f.read().splitlines():
            if ":" in dong:
                k, v = dong.split(":", 1)
                tt[k.strip()] = v.strip()
    return {"ten": tt.get("Tác vụ", ""), "pid": tt.get("PID", ""), "luc": tt.get("Thời điểm", "")}


class LeaseViec:
    """Lease của một việc: khoá HĐH trên file riêng; ``tra()`` nhả + xoá file (gọi nhiều lần vô hại)."""

    def __init__(self, khoa: KhoaTienTrinh):
        self._khoa = khoa

    def tra(self) -> None:
        khoa, self._khoa = self._khoa, None
        if khoa is None:
            return
        khoa.__exit__(None, None, None)
        with contextlib.suppress(OSError):
            os.remove(khoa.path)


def nhan_viec_cua(engine, ten: str) -> Optional[LeaseViec]:
    """Lease qua cổng của ``engine`` (``Engine.cong_bao_tri``); engine giả không có cổng → ``None``."""
    cong = getattr(engine, "cong_bao_tri", None)
    return cong.nhan_viec(ten) if isinstance(cong, CongBaoTri) else None


def vao_cong_cua(engine, ten: str):
    """Như ``nhan_viec_cua`` nhưng dạng khối ``with``."""
    cong = getattr(engine, "cong_bao_tri", None)
    return cong.viec(ten) if isinstance(cong, CongBaoTri) else contextlib.nullcontext()


class PhienRut:
    """Một lần rút của updater: giữ ``rut.lock`` cho tới ``ket_thuc()``."""

    def __init__(self, cong: "CongBaoTri", khoa_rut, chu: str):
        self.cong = cong
        self.chu = chu
        self._khoa_rut = khoa_rut

    def cho_ranh(self, han_s: float, chu_ky_s: float = 1.0) -> bool:
        """Chờ CÓ HẠN tới khi không còn lease nào. ``False`` = còn việc chạy (nơi gọi hoãn cập nhật)."""
        het = self.cong.dong_ho() + max(0.0, han_s)
        while True:
            if not self.cong.viec_dang_chay():
                return True
            if self.cong.dong_ho() >= het:
                return False
            self.cong.ngu(chu_ky_s)

    def ket_thuc(self) -> None:
        """Mở lại cổng (dù cập nhật xong hay hoãn)."""
        if self._khoa_rut is None:
            return
        with self.cong._mutex():
            with contextlib.suppress(FileNotFoundError):
                os.remove(self.cong._duong(TEN_CO_RUT))
        khoa, self._khoa_rut = self._khoa_rut, None
        _nha(khoa)


class CongBaoTri:
    """Cổng bảo trì của MỘT state root (``<data_dir>/bao_tri``)."""

    def __init__(self, data_dir: str, *, cho_mutex_s: float = 10.0,
                 kiem_them: Optional[Callable[[], str]] = None,
                 ngu: Callable[[float], None] = time.sleep, dong_ho: Callable[[], float] = time.monotonic):
        self.data_dir = data_dir
        self.thu_muc = os.path.join(data_dir, THU_MUC)
        self.cho_mutex_s = cho_mutex_s
        # Mặc định: bản CŨ (managed) không nhận việc mới sau khi bản mới đã kích hoạt.
        self.kiem_them = ly_do_ban_cu if kiem_them is None else kiem_them
        self.ngu = ngu
        self.dong_ho = dong_ho

    def _duong(self, ten: str) -> str:
        return os.path.join(self.thu_muc, ten)

    @contextlib.contextmanager
    def _mutex(self):
        os.makedirs(self.thu_muc, exist_ok=True)
        het = self.dong_ho() + self.cho_mutex_s
        while True:
            f = _thu_khoa(self._duong(TEN_MUTEX))
            if f is not None:
                break
            if self.dong_ho() >= het:
                raise LoiCong("Cổng bảo trì đang bị giữ quá lâu — thử lại sau.")
            self.ngu(0.02)
        try:
            yield
        finally:
            _nha(f)

    # ---------- cờ rút ----------

    def _co_rut_hieu_luc(self) -> Optional[dict]:
        """Đọc cờ rút; cờ mồ côi (updater đã chết → ``rut.lock`` không ai giữ) bị gỡ. Gọi dưới mutex."""
        co = self._duong(TEN_CO_RUT)
        if not os.path.exists(co):
            return None
        f = _thu_khoa(self._duong(TEN_KHOA_RUT))
        if f is not None:                        # không ai giữ khoá rút → cờ mồ côi
            _nha(f)
            with contextlib.suppress(FileNotFoundError):
                os.remove(co)
            return None
        try:
            with open(co, encoding="utf-8") as fh:
                tt = json.load(fh)
        except (OSError, ValueError):
            tt = {}
        return tt if isinstance(tt, dict) else {}

    def trang_thai_rut(self) -> Optional[dict]:
        """``None`` = cổng mở; dict (``chu``, ``luc``…) = updater đang rút."""
        with self._mutex():
            return self._co_rut_hieu_luc()

    def bat_dau_rut(self, chu: str) -> PhienRut:
        """Đóng cổng cho việc MỚI. Một updater một lúc; trả ``PhienRut`` để chờ rảnh và mở lại."""
        os.makedirs(self.thu_muc, exist_ok=True)
        khoa = _thu_khoa(self._duong(TEN_KHOA_RUT))
        if khoa is None:
            raise DangBaoTri("Đang có một lượt cập nhật khác chuẩn bị — không chạy hai lượt cùng lúc.")
        try:
            with self._mutex():
                tam = self._duong(TEN_CO_RUT + ".tmp")
                with open(tam, "w", encoding="utf-8") as fh:
                    json.dump({"chu": chu, "pid": os.getpid(),
                               "luc": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                              fh, ensure_ascii=False)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tam, self._duong(TEN_CO_RUT))
        except BaseException:
            _nha(khoa)
            raise
        return PhienRut(self, khoa, chu)

    # ---------- lease ----------

    def _tao_lease(self, ten: str) -> KhoaTienTrinh:
        lease = KhoaTienTrinh(self._duong(f"{TIEN_TO_VIEC}{uuid.uuid4().hex}.lock"), ten)
        lease.__enter__()
        return lease

    def nhan_viec(self, ten: str) -> "LeaseViec":
        """Vào cổng cho MỘT việc; trả lease phải ``tra()`` khi xong (giữ được qua luồng khác — lô quét
        nhận ở luồng giao diện, trả ở luồng nền). Cổng đang đóng → ``DangBaoTri`` (chưa bắt đầu gì)."""
        with self._mutex():
            co = self._co_rut_hieu_luc()
            if co is not None:
                raise DangBaoTri(f"Đang chuẩn bị cập nhật ({co.get('chu') or 'không rõ'}) — chưa nhận "
                                 "việc mới; việc đang chạy vẫn chạy tiếp. Thử lại sau ít phút.")
            ly_do = self.kiem_them() if self.kiem_them is not None else ""
            if ly_do:
                raise BanCu(ly_do)
            return LeaseViec(self._tao_lease(ten))

    def ly_do_ban_cu(self) -> str:
        """Lý do tiến trình này là bản cũ (rỗng nếu không) — kiểm nhanh, không qua mutex, không ghi gì."""
        try:
            return self.kiem_them() if self.kiem_them is not None else ""
        except Exception:  # noqa: BLE001 — kiểm phụ không được làm hỏng người gọi
            return ""

    @contextlib.contextmanager
    def viec(self, ten: str):
        """Lease cho MỘT việc trong một khối ``with``."""
        lease = self.nhan_viec(ten)
        try:
            yield lease
        finally:
            lease.tra()

    def viec_dang_chay(self) -> list:
        """Lease còn sống (khoá HĐH đang bị giữ). Lease mồ côi (chủ đã chết) bị dọn. Dưới mutex để
        không đụng lease đang được tạo."""
        if not os.path.isdir(self.thu_muc):
            return []
        con_song = []
        with self._mutex():
            for ten in sorted(os.listdir(self.thu_muc)):
                if not (ten.startswith(TIEN_TO_VIEC) and ten.endswith(".lock")):
                    continue
                duong = self._duong(ten)
                f = _thu_khoa(duong)
                if f is None:
                    con_song.append(_doc_thong_tin(duong))
                    continue
                _nha(f)
                with contextlib.suppress(OSError):
                    os.remove(duong)
        return con_song


def vao_cong(cong: Optional[CongBaoTri], ten: str):
    """Tiện ích cho nơi gọi có thể không có cổng (test cũ, engine giả): ``None`` → không làm gì."""
    return cong.viec(ten) if cong is not None else contextlib.nullcontext()


__all__ = ["CongBaoTri", "DangBaoTri", "DangChayRoi", "LeaseViec", "LoiCong", "PhienRut",
           "nhan_viec_cua", "vao_cong", "vao_cong_cua"]
