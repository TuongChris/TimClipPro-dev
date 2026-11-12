# -*- coding: utf-8 -*-
"""Cắt đoạn / chỉnh âm lượng video ĐÃ CÓ trong máy (D-46, người dùng yêu cầu 11/11).

Dùng lại đúng phần cắt (:func:`cat_video_goc.cat_mot`, cắt chính xác từng khung hình + kiểm độ dài) và phần chỉnh âm
lượng (:func:`am_luong.chuan_hoa`, mức YouTube -14 LUFS) của luồng tải theo link. Bất biến: file GỐC không bao giờ bị sửa,
đổi tên hay xoá — mọi kết quả ra file MỚI trong thư mục lưu (trùng tên thì thêm « (2)»). Ghép file trong máy: tab
«🎞️ Ghép video gốc» nhận cả đường dẫn file (:func:`ghep_video_goc.ghep`).
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import am_luong
import cat_video_goc as cv
import tai_video_goc as tv

# Như engine.MEDIA_EXTS (không import engine: module này chỉ cần FFmpeg).
DUOI_MEDIA = (
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".ts",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".mp3",
    ".m4a",
    ".aac",
    ".wav",
    ".ogg",
    ".opus",
    ".flac",
)


def tach_file(van_ban: str) -> tuple:
    """Mỗi dòng một FILE hoặc THƯ MỤC (lấy các file media ngay trong thư mục, theo tên — không vào thư mục con: kết quả
    lưu vào thư mục con thì bấm lại không xử lý lại). Trả ``(danh sách file, danh sách câu lỗi)``; bỏ dòng trống/trùng."""
    files: list = []
    loi: list = []
    for dong in (van_ban or "").splitlines():
        d = dong.strip().strip('"').strip()
        if not d:
            continue
        if os.path.isdir(d):
            moi = sorted(
                (
                    os.path.join(d, f)
                    for f in os.listdir(d)
                    if f.lower().endswith(DUOI_MEDIA)
                    and os.path.isfile(os.path.join(d, f))
                ),
                key=lambda x: os.path.basename(x).lower(),
            )
            if not moi:
                loi.append(f"Thư mục không có video/tiếng nào: {d}")
        elif os.path.isfile(d):
            if not d.lower().endswith(DUOI_MEDIA):
                loi.append(f"File không phải video/tiếng: {d}")
                continue
            moi = [d]
        else:
            loi.append(f"Không tìm thấy file/thư mục: {d}")
            continue
        files.extend(f for f in moi if f not in files)
    return files, loi


def xu_ly(
    files: list,
    thu_muc: str,
    _cau_hinh_mang=None,
    *,
    tu_s: Optional[float] = None,
    den_s: Optional[float] = None,
    chuan_hoa_am: bool = False,
    progress: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    **_kw,
) -> list:
    """Cắt đoạn [``tu_s``, ``den_s``) và/hoặc chỉnh âm lượng từng file vào ``thu_muc``. Trả list dict như
    :func:`tai_video_goc.tai_nhieu` (thêm ``la_file_may``). Tham số thứ ba + ``_kw`` (mạng, phiên…) bỏ qua: không dùng mạng."""
    if tu_s is None and not chuan_hoa_am:
        raise ValueError(
            "Chọn ít nhất một việc: cắt đoạn («Từ»/«Đến») hoặc chỉnh âm lượng."
        )
    if tu_s is not None and not (den_s is not None and 0 <= tu_s < den_s):
        raise ValueError("Mốc «Đến» phải sau mốc «Từ» (và «Từ» không âm).")
    bao = progress or (lambda _p, _m: None)
    huy = cancel_check or (lambda: False)
    thu_muc = os.path.abspath(str(thu_muc or "").strip().strip('"'))
    n = len(files)
    ket_qua: list = []
    for i, f in enumerate(files):
        goc, duoi = os.path.splitext(os.path.basename(f))
        k = {
            "url": f,
            "trang_thai": "loi",
            "duong_dan": "",
            "tieu_de": goc,
            "chat_luong": "file trong máy",
            "ghi_chu": "",
            "la_file_may": True,
        }
        ket_qua.append(k)
        if huy():
            k.update(
                trang_thai="bo_qua",
                ghi_chu="Đã dừng theo yêu cầu trước khi xử lý file này.",
            )
            continue
        nhan = f"File {i + 1}/{n}"

        def bao_i(phan: float, cau: str, i=i) -> None:
            bao(min((i + phan) / n, 1.0), cau)

        if tu_s is not None:
            k.update(
                cv.cat_mot(
                    f,
                    thu_muc,
                    tu_s,
                    den_s,
                    chuan_hoa_am=chuan_hoa_am,
                    huy=huy,
                    bao=bao_i,
                    nhan=nhan,
                    giu="File gốc giữ nguyên.",
                )
            )
            continue
        os.makedirs(thu_muc, exist_ok=True)
        dich = tv._ten_trong(thu_muc, f"{tv.ten_khong_dau(goc) or 'video'}_am_luong_YouTube{duoi}")  # tên không dấu cách (12/11)
        bao_i(0.0, f"{nhan}: đang chỉnh âm lượng «{goc}»...")
        try:
            ghi = am_luong.chuan_hoa(f, huy=huy, dich=dich)
        except am_luong.DaHuyChinhAmLuong:
            k.update(
                trang_thai="bo_qua",
                ghi_chu="Đã dừng theo yêu cầu trong lúc chỉnh âm lượng; file gốc giữ nguyên.",
            )
            continue
        except RuntimeError as e:
            k["ghi_chu"] = f"{e} — file gốc giữ nguyên."
            continue
        if os.path.isfile(dich):
            k.update(trang_thai="xong", duong_dan=dich, ghi_chu=ghi)
        else:  # đã ở mức / không có tiếng: không tạo bản sao giống hệt
            k.update(trang_thai="bo_qua", ghi_chu=f"{ghi} Không tạo file mới.")
    bao(1.0, "Xong.")
    return ket_qua
