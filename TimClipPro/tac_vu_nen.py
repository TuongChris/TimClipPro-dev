# -*- coding: utf-8 -*-
"""Tác vụ nền dài của giao diện (đồng bộ kênh, lấy lại tên video, vá metadata) ở mức TIẾN TRÌNH.

Mỗi phiên trình duyệt có ``job`` riêng trong ``st.session_state``; tải lại trang (F5, tab thứ hai, tab bị trình duyệt
dỡ) = phiên MỚI. Không có sổ chung thì lượt đồng bộ kênh nhiều giờ vẫn chạy nhưng phiên mới thấy «không có gì chạy»:
không tiến độ, không nút Dừng tới được lượt đó, kết quả cuối (trạng thái, video lỗi, file nghi hỏng, đăng nhập) rơi vào
``job`` của phiên đã chết (audit D-13). Lô quét đã có sổ tương tự (``scan_jobs._DANG_CHAY``). Cùng cơ chế (sổ
:class:`SoViecDai`) dùng cho dựng kho vân tay và lô «Một video gốc chung» (audit F-2).

Thread nền KHÔNG chạm Streamlit: nó chỉ ghi vào đối tượng ``TacVuNen`` (có khoá) và ``job`` của phiên đã bấm (như
trước); phiên khác NHẬN LẠI tác vụ thì chép ``anh()`` vào ``job`` của mình ở main thread. Nút Dừng của phiên nhận lại
gọi ``huy()`` = cờ huỷ của Engine đã khởi động tác vụ (cờ mà ``cancel_check`` của tác vụ đang đọc), không phải Engine
riêng của phiên mới.

Tác vụ XONG khi không phiên nào đang vẽ (lượt chạy qua đêm, tab bị trình duyệt dỡ — chính tác nhân của D-13) thì kết quả
chỉ nằm trong ``job`` của phiên đã chết: giữ tác vụ trong ô «vừa xong» của thư mục dữ liệu tới khi MỘT phiên nhận
(:func:`nhan_vua_xong`), phiên đã theo dõi tới lúc xong báo đã nhận (:func:`da_nhan`), hoặc tác vụ mới bắt đầu (review
audit D). Chỉ trong bộ nhớ tiến trình: tắt Tool thì mất — như sổ lô quét.
"""

from __future__ import annotations

import os
import threading
import uuid
from typing import Callable, Optional


class DangCoTacVuKhac(RuntimeError):
    """Một phiên khác của Tool vừa khởi động tác vụ nền trên cùng thư mục dữ liệu."""


def _khoa(engine) -> str:
    thu_muc = getattr(engine, "data_dir", None)
    return os.path.normcase(os.path.abspath(thu_muc)) if thu_muc else f"id:{id(engine)}"


class SoViecDai:
    """Sổ mức TIẾN TRÌNH của MỘT loại việc dài, theo thư mục dữ liệu: việc ĐANG CHẠY (một việc mỗi thư mục) + việc
    vừa XONG mà chưa phiên nào chép kết quả. Việc = đối tượng có ``running`` và ``engine`` (``TacVuNen``, controller
    dựng kho vân tay, controller lô «Một video gốc chung» — audit D-13, F-2). Thread nền chỉ gọi ``ghi``/``xong``;
    phiên trình duyệt (main thread) gọi ``cua_phien``/``da_nhan``. Tắt Tool thì mất — như sổ lô quét.

    Thứ tự khoá: khoá của sổ luôn ở NGOÀI khoá riêng của việc (``ghi`` đọc ``running`` của việc khác dưới khoá sổ),
    nên việc không được gọi sổ khi đang giữ khoá riêng của nó."""

    def __init__(self):
        self._dang_chay: dict = {}
        self._vua_xong: dict = {}
        self._khoa = threading.Lock()

    def dang_chay_cua(self, engine):
        """Việc đang chạy trên CÙNG thư mục dữ liệu (có thể của phiên khác), nếu có."""
        with self._khoa:
            viec = self._dang_chay.get(_khoa(engine))
        return viec if viec is not None and viec.running else None

    def ghi(self, engine, viec, thong_bao_trung: str, danh_dau: Optional[Callable[[], None]] = None) -> None:
        """Ghi ``viec`` là việc đang chạy của thư mục dữ liệu. Việc KHÁC còn chạy → ``DangCoTacVuKhac`` (chưa đổi gì).
        ``danh_dau``: đặt cờ đang chạy của ``viec`` dưới khoá sổ — phiên khác không lọt vào khe giữa kiểm và ghi."""
        k = _khoa(engine)
        with self._khoa:
            khac = self._dang_chay.get(k)
            if khac is not None and khac is not viec and khac.running:
                raise DangCoTacVuKhac(thong_bao_trung)
            if danh_dau is not None:
                danh_dau()
            self._dang_chay[k] = viec
            self._vua_xong.pop(k, None)        # kết quả cũ chưa ai nhận: việc mới thay chỗ

    def xong(self, engine, viec) -> None:
        """Thread nền: ``viec`` vừa kết thúc → giữ trong ô «vừa xong» tới khi một phiên nhận (phiên đã bấm có thể đã
        chết: tab bị dỡ, chạy qua đêm)."""
        k = _khoa(engine)
        with self._khoa:
            if self._dang_chay.get(k) is viec:
                del self._dang_chay[k]
                self._vua_xong[k] = viec

    def nhan_vua_xong(self, engine):
        """Lấy (và bỏ khỏi sổ) việc đã XONG mà chưa phiên nào chép kết quả — đúng một phiên nhận được."""
        with self._khoa:
            return self._vua_xong.pop(_khoa(engine), None)

    def da_nhan(self, engine, viec) -> None:
        """Phiên đã chép kết quả cuối của ``viec``: phiên mở sau không nhận lại."""
        with self._khoa:
            k = _khoa(engine)
            if self._vua_xong.get(k) is viec:
                del self._vua_xong[k]

    def cua_phien(self, engine, hien_tai, tao: Callable, *, dang_hien: bool = False, phien_moi: bool = False):
        """Việc (controller) của phiên trình duyệt sở hữu ``engine`` — gọi MỖI lần vẽ lại; ``hien_tai`` = cái phiên
        đang giữ. Đang chạy, hoặc phiên còn đang hiện nó (``dang_hien``: chưa chép kết quả) → giữ. Rảnh → NHẬN LẠI
        việc đang chạy trên cùng thư mục dữ liệu (tải lại trang, tab thứ hai mở TRƯỚC khi việc bắt đầu); phiên mới
        chưa làm gì (``phien_moi``) còn nhận việc vừa xong chưa ai xem. Việc mượn GIỮ Engine của phiên đã bấm nên chỉ
        mượn tới khi chép xong kết quả; sau đó → của chính phiên (``tao(engine)``), việc sau dùng đúng Engine phiên."""
        if hien_tai is not None and (hien_tai.running or dang_hien):
            return hien_tai
        viec = self.dang_chay_cua(engine) or (self.nhan_vua_xong(engine) if phien_moi else None)
        if viec is not None:
            return viec
        if hien_tai is not None and hien_tai.engine is engine:
            return hien_tai
        return tao(engine)


# Sổ của tác vụ nền giao diện (đồng bộ kênh, lấy lại tên, vá metadata).
SO_TAC_VU_NEN = SoViecDai()


def dang_chay_cua(engine) -> Optional["TacVuNen"]:
    """Tác vụ nền đang chạy trên CÙNG thư mục dữ liệu (có thể của phiên khác), nếu có."""
    return SO_TAC_VU_NEN.dang_chay_cua(engine)


def nhan_vua_xong(engine) -> Optional["TacVuNen"]:
    """Lấy (và bỏ khỏi sổ) tác vụ đã XONG trên cùng thư mục dữ liệu mà chưa phiên nào chép kết quả — đúng một phiên
    nhận được."""
    return SO_TAC_VU_NEN.nhan_vua_xong(engine)


def da_nhan(engine, tv: "TacVuNen") -> None:
    """Phiên đã chép kết quả cuối của ``tv`` vào ``job``: phiên mở sau không nhận lại."""
    SO_TAC_VU_NEN.da_nhan(engine, tv)


class TacVuNen:
    """Một tác vụ nền: một thread, trạng thái đọc qua ảnh chụp (``anh``) — không đối tượng nào của Streamlit."""

    def __init__(self, kind: str, huy: Callable[[], None], so_dong_bo=None):
        self.id = uuid.uuid4().hex
        self.kind = kind
        self.so_dong_bo = so_dong_bo          # sổ tiến độ đồng bộ kênh (chỉ đọc ảnh chụp ở giao diện)
        self._huy = huy
        self._khoa = threading.Lock()
        self._pct = 0.0
        self._msg = "Đang khởi động..."
        self._results = []
        self._error = ""
        self._running = False

    @property
    def running(self) -> bool:
        with self._khoa:
            return self._running

    def huy(self) -> None:
        """Nút Dừng (phiên nào cũng được): đặt cờ huỷ mà tác vụ đang đọc."""
        self._huy()

    def anh(self) -> dict:
        """Các trường của ``job`` giao diện, chụp dưới khoá."""
        with self._khoa:
            return {"running": self._running, "pct": self._pct, "msg": self._msg, "results": self._results,
                    "error": self._error, "kind": self.kind, "da_day_sheet": False}

    def bat_dau(self, engine, ham, args: tuple, kwargs: dict, *, job: dict, lease=None) -> None:
        """Ghi sổ rồi chạy ``ham(*args, progress=..., **kwargs)`` trong thread nền. ``job``: dict của phiên đã bấm —
        vẫn được ghi như trước. Phiên khác đã có tác vụ chạy trên cùng thư mục dữ liệu → ``DangCoTacVuKhac``
        (chưa chạy gì; người gọi tự trả ``lease``)."""
        def danh_dau():
            with self._khoa:
                self._running = True

        SO_TAC_VU_NEN.ghi(engine, self, "Đang có tác vụ nền chạy ở một cửa sổ/phiên khác của Tool — tải lại trang "
                          "để xem tiến độ; không tạo tác vụ trùng.", danh_dau=danh_dau)

        def bao_tien_do(pct, msg):
            with self._khoa:
                self._pct, self._msg = pct, msg
            job["pct"], job["msg"] = pct, msg

        def target():
            ket_qua, loi = [], ""
            try:
                ket_qua = ham(*args, progress=bao_tien_do, **kwargs)
            except Exception as e:  # noqa: BLE001
                loi = str(e)
            finally:
                if lease is not None:
                    lease.tra()
                with self._khoa:
                    self._results, self._error = ket_qua, loi
                    self._running = False
                SO_TAC_VU_NEN.xong(engine, self)   # tới khi một phiên nhận (phiên đã bấm có thể đã chết)
                job["results"], job["error"] = ket_qua, loi
                job["running"] = False

        threading.Thread(target=target, daemon=True, name=f"tac-vu-nen-{self.kind}").start()
