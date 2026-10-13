# -*- coding: utf-8 -*-
"""Màn hình tiến độ khi ĐANG quét (Streamlit) — chỉ ĐỌC ảnh chụp ``scan_jobs.BatchSnapshot``.

Nguyên tắc (PC2 12/10/2026, «0/5 — 1%» suốt 24 phút): chỉ hiện số liệu có NGUỒN từ pipeline
(``tien_do_quet``). Chưa đo được thì nói «chưa biết»/«chưa đủ dữ liệu» — không phần trăm giả,
không ETA bịa, không tự tăng số theo đồng hồ. Phần định dạng là hàm thuần để test không cần Streamlit.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import tien_do_quet as tdq
from engine import hhmmss

CHUA_DU_ETA = "Chưa đủ dữ liệu để ước tính"


def thoi_luong(giay: Optional[float]) -> str:
    """Thời gian VẬN HÀNH (đã chạy, ETA) — HH:MM:SS; ``None`` → «—»."""
    if giay is None:
        return "—"
    giay = max(0, int(giay))
    return f"{giay // 3600:02d}:{(giay % 3600) // 60:02d}:{giay % 60:02d}"


def mb(byte: Optional[float]) -> str:
    if byte is None:
        return "—"
    return f"{byte / 1024 / 1024:,.1f} MB"


def cung_video(anh) -> bool:
    """Số đo trong sổ có thuộc ĐÚNG video đang hiện không (tránh số của video trước)."""
    td = anh.tien_do
    return td.index > 0 and td.index == anh.current_index and td.batch_id in ("", anh.batch_id)


def dong_chi_tiet(anh, v, ten_phase: dict, bay_gio: Optional[float] = None) -> list:
    """Các dòng markdown mô tả video đang chạy — chỉ từ số đo thật."""
    bay_gio = time.time() if bay_gio is None else bay_gio
    td = anh.tien_do
    co_so_do = cung_video(anh)
    tieu_de = (td.tieu_de if co_so_do and td.tieu_de else v.title) or v.nguon[:90]
    dong = [f"**Video {v.index}/{anh.total}:** {tieu_de}"]
    if not co_so_do:
        dong.append(f"**Giai đoạn hiện tại:** {ten_phase.get(v.phase, v.phase)}")
        return dong
    dong.append("**Thời lượng nguồn:** " + (hhmmss(td.thoi_luong_nguon_s) if td.thoi_luong_nguon_s
                                             else "chưa biết"))
    if td.pham_vi_den_s is not None:
        dong.append(f"**Phạm vi quét:** {hhmmss(td.pham_vi_tu_s or 0)} → {hhmmss(td.pham_vi_den_s)}")
    elif td.giai_doan not in (tdq.GD_CHO, tdq.GD_METADATA):
        dong.append("**Phạm vi quét:** chưa xác nhận")
    if td.che_do:
        dong.append(f"**Chế độ:** {td.che_do}")
    dong.append(f"**Giai đoạn hiện tại:** {td.ten_giai_doan}")
    if td.giai_doan == tdq.GD_TAI:
        phan = []
        if td.byte_da_nhan:
            phan.append(f"đã nhận {mb(td.byte_da_nhan)}" + (f" / {mb(td.byte_tong)}" if td.byte_tong else ""))
        if td.audio_da_nhan_s is not None and td.audio_can_s:
            phan.append(f"{hhmmss(td.audio_da_nhan_s)} / {hhmmss(td.audio_can_s)} âm thanh")
        elif td.audio_can_s:
            phan.append(f"tối đa {hhmmss(td.audio_can_s)} âm thanh")
        if td.toc_do_x:
            phan.append(f"tốc độ {td.toc_do_x:.1f}× thời gian thực")
        elif td.toc_do_byte_s:
            phan.append(f"tốc độ {td.toc_do_byte_s / 1024:,.0f} KB/s")
        if not td.byte_da_nhan:
            phan.append(f"đang chờ dữ liệu đầu tiên (đã chờ {int(bay_gio - td.giai_doan_luc)} giây)")
        dong.append("**Tải audio:** " + " · ".join(phan))
    elif td.giai_doan == tdq.GD_CAT and td.khuc_tong:
        dong.append(f"**Cắt khúc:** {td.khuc_xong or 0}/{td.khuc_tong}"
                    + (f" — đang cắt {td.khuc_hien_tai}" if td.khuc_hien_tai else ""))
    elif td.giai_doan == tdq.GD_KHOP and td.khop_tong:
        dong.append(f"**So khớp:** đã xong {td.khop_xong or 0}/{td.khop_tong} khúc")
    if td.so_dat_chuan is not None:
        dong.append(f"**Ứng viên đạt chuẩn:** {td.so_dat_chuan}")
    return dong


def dong_nhip(anh, bay_gio: Optional[float] = None) -> str:
    """Nhịp sống (tiến trình còn chạy) TÁCH KHỎI lần cuối có tiến triển thật."""
    bay_gio = time.time() if bay_gio is None else bay_gio
    td = anh.tien_do
    phan = ["Luồng quét: " + ("đang chạy" if anh.worker_alive else "đã dừng")]
    if cung_video(anh):
        nhip = td.nhip_cach(bay_gio)
        if nhip is not None:
            phan.append(f"nhịp tiến trình {int(nhip)} giây trước")
        phan.append(f"lần cuối có tiến triển {int(td.cham(bay_gio))} giây trước")
        phan.append(f"bước này đã chạy {thoi_luong(bay_gio - td.giai_doan_luc)}")
    return " · ".join(phan)


def dong_eta_buoc(anh) -> str:
    td = anh.tien_do
    if not cung_video(anh) or td.eta_buoc_s is None:
        return f"ETA bước hiện tại: {CHUA_DU_ETA.lower()}"
    return f"ETA bước hiện tại: ~{thoi_luong(td.eta_buoc_s)} (theo tốc độ đo được, có thể thay đổi)"


def dong_nhat_ky(anh, gio: Callable[[float], str]) -> list:
    """``gio``: đổi epoch → «HH:MM:SS» — do tầng app truyền vào (module này không tự đổi epoch)."""
    return [f"{gio(s.luc)} — {s.noi_dung}" for s in anh.nhat_ky]


def ve_tien_do_lo(st, anh, ten_phase: dict, gio: Callable[[float], str]) -> None:
    """Vẽ phần tiến độ của lô quét (tổng quan, video hiện tại, nhịp, cảnh báo, nhật ký)."""
    xong = anh.completed + anh.failed
    st.progress(xong / anh.total if anh.total else 0.0,
                text=f"{xong}/{anh.total} video đã xong"
                     + (f" — đang ở video {anh.current_index}/{anh.total}" if anh.running else ""))
    b0, b1, b2, b3, b4 = st.columns(5)
    b0.metric("Video hiện tại", f"{anh.current_index}/{anh.total}" if anh.total else "—")
    b1.metric("Hoàn tất", anh.completed)
    b2.metric("Lỗi", anh.failed)
    b3.metric("Đã chạy", thoi_luong(anh.elapsed_seconds))
    b4.metric("ETA cả lô", thoi_luong(anh.eta_seconds) if anh.eta_seconds is not None else CHUA_DU_ETA)
    if not (0 < anh.current_index <= len(anh.videos)):
        return
    v = anh.videos[anh.current_index - 1]
    bay_gio = time.time()
    with st.container(border=True):
        st.markdown("  \n".join(dong_chi_tiet(anh, v, ten_phase, bay_gio)))
        ty_le = anh.tien_do.ty_le_buoc if cung_video(anh) else None
        if ty_le is not None:
            st.progress(ty_le, text=f"{anh.tien_do.ten_giai_doan}: {ty_le * 100:.0f}% của bước này")
        st.caption(dong_nhip(anh, bay_gio) + "  \n" + dong_eta_buoc(anh))
        if v.message:
            st.caption(f"Thông báo gần nhất: {v.message}")
        canh_bao = anh.tien_do.canh_bao(bay_gio) if cung_video(anh) else ""
        if canh_bao:
            st.warning(canh_bao)
    with st.expander("📜 Nhật ký quét trực tiếp (20 sự kiện mới nhất)", expanded=True):
        nhat_ky = dong_nhat_ky(anh, gio)
        if nhat_ky:
            st.code("\n".join(nhat_ky), language=None)
        else:
            st.caption("Chưa có sự kiện nào.")
