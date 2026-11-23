"""Nút bớt thao tác tay dùng chung cho các trang: chọn thư mục/file bằng hộp thoại của Windows, mở thư mục kết quả."""

import os

import streamlit as st

import tai_video_goc


def nut_chon(khoa: str, ban_dau: str = "", loai: str = "thu_muc", nhan: str = "📂 Chọn…", tieu_de: str = "") -> list:
    """Nút mở hộp thoại chọn ``loai`` = "thu_muc" | "file" | "nhieu_file". Trả danh sách đường dẫn đã chọn — rỗng khi
    không bấm, bấm Huỷ, hoặc không mở được hộp thoại (báo lỗi ngay dưới nút)."""
    if not st.button(nhan, key=khoa, width="stretch", help="Mở hộp thoại chọn của Windows"):
        return []
    # Ô nhiều dòng (danh sách file, link): mở ở chỗ của dòng cuối còn có trên đĩa.
    ban_dau = next((d for d in reversed([x.strip('" ') for x in (ban_dau or "").splitlines()]) if d and os.path.exists(d)), "")
    try:
        if loai == "thu_muc":
            p = tai_video_goc.chon_thu_muc(ban_dau, tieu_de or "Chọn thư mục")
            return [p] if p else []
        return tai_video_goc.chon_file(ban_dau, nhieu=loai == "nhieu_file", tieu_de=tieu_de or "Chọn file")
    except RuntimeError as e:
        st.error(str(e))
        return []


def noi_dong(van_ban: str, moi: list) -> str:
    """Thêm vào ô «mỗi dòng một đường dẫn» các dòng CHƯA có, giữ nguyên các dòng đã gõ."""
    dong = [d for d in (van_ban or "").splitlines() if d.strip()]
    # So như Windows so đường dẫn: bỏ ngoặc kép của «Copy as path», không phân biệt chữ hoa/thường.
    da_co = {os.path.normcase(d.strip().strip('"').strip()) for d in dong}
    return "\n".join(dong + [x for x in dict.fromkeys(moi) if os.path.normcase(x) not in da_co])


def thu_muc_ket_qua(ket_qua: list) -> list:
    """Thư mục chứa file kết quả của một lượt tải / cắt / ghép / chụp ảnh (``tai_video_goc.tai_nhieu`` và họ hàng).
    Lượt ghép chỉ lấy file ghép — phần lẻ nằm ở thư mục tạm đã xoá, dòng file trong máy là file NGUỒN của người dùng."""
    ghep = [k for k in ket_qua if k.get("la_dong_ghep")]
    ds: list = []
    for k in ghep or ket_qua:
        d = k.get("duong_dan") or ""
        if k.get("trang_thai") != "xong" or not d or not os.path.exists(d):
            continue
        d = d if os.path.isdir(d) else os.path.dirname(d)
        if d not in ds:
            ds.append(d)
    return ds


def nut_mo_thu_muc(thu_muc: str, khoa: str, nhan: str = "📂 Mở thư mục") -> None:
    """Mở ``thu_muc`` trong File Explorer (máy đang chạy Tool)."""
    if st.button(nhan, key=khoa, help=thu_muc, disabled=not os.path.isdir(thu_muc)):
        try:
            os.startfile(thu_muc)  # chỉ có trên Windows — Tool chạy trên Windows
        except (OSError, AttributeError) as e:
            st.error(f"Không mở được thư mục «{thu_muc}»: {e}")
