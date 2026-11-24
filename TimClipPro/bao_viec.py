# -*- coding: utf-8 -*-
"""Việc dài của giao diện (lô quét, dựng kho vân tay, tác vụ nền tải / cắt / ghép / đồng bộ kênh…, lô «Một video gốc
chung»): giữ máy không ngủ trong lúc chạy và phát tiếng khi việc kết thúc. Lô chạy hàng giờ, người dùng làm việc ở ứng
dụng khác — tiếng phát từ LUỒNG NỀN của việc nên vẫn kêu khi tab trình duyệt đang ngủ.

Luồng nền của mỗi việc gọi ``bat_dau()`` ở đầu và ``ket_thuc(kieu)`` trong ``finally``. Không phải Windows (thiếu
``winsound`` / ``ctypes.windll``) thì im lặng, không lỗi.

Vì sao gọi trong chính luồng của việc: ``SetThreadExecutionState`` đặt yêu cầu của LUỒNG gọi (tài liệu Microsoft: tham số
là «the thread's execution requirements», giá trị trả về là «the previous thread execution state»). Mỗi việc chạy trong
MỘT luồng riêng sống đúng bằng việc đó, nên luồng ấy tự đặt rồi tự trả, và Windows gộp yêu cầu của mọi luồng: lô quét xong
(luồng quét trả yêu cầu của nó) mà đồng bộ kênh còn chạy thì máy vẫn thức nhờ yêu cầu của luồng đồng bộ — việc CUỐI xong
thì hết yêu cầu, không cần bộ đếm. Gọi từ luồng Streamlit thì sai: luồng đó không sống bằng việc, và trả ở luồng khác
không gỡ được yêu cầu của luồng việc. Không đổi cài đặt nguồn điện; người dùng vẫn tự cho máy ngủ / gập máy được.
"""

from __future__ import annotations

import ctypes
import logging
import threading

try:
    import winsound
except ImportError:  # không phải Windows
    winsound = None

LOGGER = logging.getLogger("bao_viec")

XONG = "xong"
LOI = "loi"

# Ô «🔔 Kêu khi việc dài xong hoặc lỗi» ở thanh bên — app.py chép giá trị vào đây mỗi lượt vẽ (mặc định BẬT như
# cau_hinh.GIA_TRI_GIAO_DIEN_MAC_DINH). Một giá trị cho cả tiến trình: các tab đều của cùng một người dùng.
bat_tieng = True

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

# (tần số Hz, độ dài ms). Xong: hai nốt đi lên. Lỗi / bị chặn: ba nốt đi xuống, trầm hơn — nghe là phân biệt được.
NOT = {XONG: ((880, 150), (1320, 300)), LOI: ((660, 250), (440, 250), (330, 450))}


def _dat_trang_thai_luong(co: int) -> None:
    """``SetThreadExecutionState(co)`` cho luồng ĐANG GỌI; không phải Windows thì bỏ qua."""
    windll = getattr(ctypes, "windll", None)
    if windll is not None:
        windll.kernel32.SetThreadExecutionState(ctypes.c_uint(co))


def phat_tieng(kieu: str) -> None:
    """Phát chuỗi nốt của ``kieu`` — chặn tới khi phát xong nên chạy ở luồng riêng."""
    if winsound is None:
        return
    try:
        for tan_so, ms in NOT[kieu]:
            winsound.Beep(tan_so, ms)
    except RuntimeError as e:  # máy không phát được tiếng (không có thiết bị âm thanh)
        LOGGER.info("event=bao_viec.khong_phat_duoc_tieng err=%s", e)


def kieu_ket_thuc(loi: str = "", phien=None, ket_qua=None) -> str:
    """``LOI`` khi việc ném lỗi hoặc bị YouTube chặn (cầu dao của ``phien`` mở, hay kết quả mang ``chan_youtube``);
    còn lại ``XONG`` — kể cả xong một phần: chi tiết ở màn kết quả."""
    bi_chan = getattr(phien, "mo", False) is True or (isinstance(ket_qua, dict) and bool(ket_qua.get("chan_youtube")))
    return LOI if loi or bi_chan else XONG


def bat_dau() -> None:
    """Đầu luồng nền của một việc dài: giữ máy không ngủ tới khi CHÍNH luồng này gọi ``ket_thuc``."""
    _dat_trang_thai_luong(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def ket_thuc(kieu: str | None) -> None:
    """Cuối (``finally``) CHÍNH luồng đã gọi ``bat_dau``: trả yêu cầu giữ máy; ``kieu`` ``XONG`` / ``LOI`` → phát tiếng ở
    luồng riêng (luồng việc không phải chờ); ``None`` = người dùng bấm Dừng — đang nhìn màn hình, không kêu."""
    _dat_trang_thai_luong(ES_CONTINUOUS)
    if kieu in NOT and bat_tieng:
        try:
            threading.Thread(target=phat_tieng, args=(kieu,), daemon=True, name="bao-tieng").start()
        except RuntimeError:  # hết tài nguyên luồng: bỏ tiếng, không làm hỏng phần dọn của việc
            LOGGER.info("event=bao_viec.khong_tao_duoc_luong_tieng")
