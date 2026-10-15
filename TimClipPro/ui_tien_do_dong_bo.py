# -*- coding: utf-8 -*-
"""Màn tiến độ ĐỒNG BỘ KÊNH — chỉ ĐỌC ảnh chụp ``tien_do_dong_bo.AnhDongBo`` (không sửa, không gọi worker).

Hàm thuần (định dạng chữ/số, dựng bảng) tách khỏi hàm vẽ ``ve_tien_do_dong_bo(st, anh)`` nhận ``st`` từ ngoài, để test
không cần Streamlit chạy thật. Không hiện cookie/URL/đường dẫn — ảnh chụp vốn không chứa.
"""

from __future__ import annotations

from typing import Any, Optional

from tien_do_dong_bo import (
    GD_CHO,
    GD_KIEM,
    GD_LIET_KE,
    GD_NEN,
    GD_TAI,
    GD_THEO_VIDEO,
    TEN_GIAI_DOAN,
    TT_BI_CHAN,
    TT_DA_HUY,
    TT_DANG_CHAY,
    TT_MOT_PHAN,
    TT_XONG,
    AnhDongBo,
)

SO_SU_KIEN_HIEN = 30
TEN_TRANG_THAI = {TT_DANG_CHAY: "Đang chạy", TT_MOT_PHAN: "Xong một phần", TT_BI_CHAN: "Dừng giữa chừng (bị chặn)",
                  TT_DA_HUY: "Đã dừng theo yêu cầu", TT_XONG: "Hoàn tất"}


def thoi_luong(giay: Optional[float]) -> str:
    if giay is None:
        return "—"
    giay = max(0, int(round(giay)))
    g, du = divmod(giay, 3600)
    p, s = divmod(du, 60)
    return f"{g} giờ {p:02d} phút" if g else (f"{p} phút {s:02d} giây" if p else f"{s} giây")


def mb(so_byte: Optional[float]) -> str:
    return "—" if so_byte is None else f"{so_byte / 1e6:,.1f} MB"


def toc_do_mb(byte_giay: Optional[float]) -> str:
    return "—" if not byte_giay else f"{byte_giay / 1e6:,.1f} MB/s"


def chu_eta(anh: AnhDongBo) -> str:
    if anh.eta_s is None:
        return "Đang ước tính"
    return thoi_luong(anh.eta_s) + (f" (độ tin cậy {anh.eta_tin_cay})" if anh.eta_tin_cay else "")


def dong_tong(anh: AnhDongBo) -> str:
    """Chữ trên thanh tiến độ tổng."""
    if anh.giai_doan_luot == GD_LIET_KE and anh.tong_kenh is None:
        return "Đang lấy danh sách video của kênh…"
    if anh.se_thu is None:
        return f"Đang kiểm file đã có {anh.kiem_da}/{anh.kiem_tong}…" if anh.kiem_tong else "Đang chuẩn bị…"
    return (f"Đã xét {anh.da_xet}/{anh.se_thu} video cần tải • tải mới {anh.moi} • lỗi {anh.loi}"
            + (f" • chưa thử {anh.chua_thu}" if anh.chua_thu else ""))


def the_kpi(anh: AnhDongBo) -> list:
    """``[(nhãn, giá trị, ghi chú)]`` cho hàng thẻ KPI."""
    han_che = anh.gioi_han_tuoi + anh.chi_hoi_vien + anh.han_che_bo_qua
    vmg = anh.video_moi_gio
    return [
        ("Đã có (giữ nguyên)", "—" if anh.da_co is None else str(anh.da_co), ""),
        ("Tải mới", str(anh.moi), ""),
        ("Lỗi", str(anh.loi), ""),
        ("Bị hạn chế", str(han_che), f"tuổi {anh.gioi_han_tuoi} • hội viên {anh.chi_hoi_vien} • bỏ qua theo sổ "
                                     f"{anh.han_che_bo_qua}"),
        ("Chưa thử", "—" if anh.chua_thu is None else str(anh.chua_thu), ""),
        ("Thời gian chạy", thoi_luong(anh.chay_s), ""),
        ("Tốc độ thực", "—" if vmg is None else f"{vmg:,.1f} video/giờ",
         "" if anh.media_gio_moi_gio is None else f"{anh.media_gio_moi_gio:,.1f} giờ audio/giờ"),
        ("Còn lại (ETA)", chu_eta(anh), anh.eta_ly_do),
    ]


def dong_video(anh: AnhDongBo) -> list:
    """``[(loại, chữ, tỷ lệ | None)]`` của video đang xử lý — loại ∈ {"tieu_de","giai_doan","tai","nen","chu","canh_bao"}."""
    v = anh.video
    if v is None:
        return []
    ra = [("tieu_de", f"Video {v.chi_so}/{v.tong}: {v.tieu_de} ({v.video_id})", None)]
    troi = max(0.0, anh.luc_anh - v.giai_doan_bat_dau) if anh.luc_anh else 0.0
    gd = TEN_GIAI_DOAN.get(v.giai_doan, v.giai_doan)
    ra.append(("giai_doan", f"Giai đoạn: {gd} — {thoi_luong(troi)} • cả video {thoi_luong(anh.luc_anh - v.bat_dau)}",
               None))
    if v.giai_doan == GD_CHO and v.nghi_du_kien_s:
        ra.append(("chu", f"Nghỉ giãn nhịp {v.nghi_du_kien_s:.1f} giây theo cấu hình (giảm nguy cơ bị nghi là bot).", None))
    if v.byte_tai is not None or v.giai_doan == GD_TAI:
        chu = f"Tải {mb(v.byte_tai)}" + (f" / {mb(v.byte_tong)}" if v.byte_tong else "") + \
            f" • {toc_do_mb(v.toc_do_tai)}" + (f" • còn {thoi_luong(v.eta_tai_s)}" if v.eta_tai_s else "")
        ra.append(("tai", chu, v.ty_le_tai))
    if v.dinh_dang:
        ra.append(("chu", f"Định dạng: {v.dinh_dang}" + (f" • client {v.client}" if v.client else "")
                   + (f" • đã đổi client {v.so_doi_client} lần" if v.so_doi_client else ""), None))
    if v.chi_audio is False:
        ra.append(("canh_bao", "Video này chỉ có định dạng CÓ HÌNH ở client đang dùng — tải nhiều byte hơn bản chỉ có "
                               "tiếng (vân tay vẫn chỉ dùng phần tiếng).", None))
    if v.giai_doan == GD_NEN:
        if v.ffmpeg_da_s is not None:
            chu = f"Nén {thoi_luong(v.ffmpeg_da_s)}" + (f" / {thoi_luong(v.ffmpeg_tong_s)}" if v.ffmpeg_tong_s else "") + \
                (f" • {v.ffmpeg_toc_do_x:,.0f}× thời gian thực" if v.ffmpeg_toc_do_x else "")
            ra.append(("nen", chu, v.ty_le_nen))
        else:
            ra.append(("nen", "Đang khởi động FFmpeg…", None))
    return ra


def bang_cong_doan(anh: AnhDongBo) -> list:
    """Bảng thời gian các công đoạn trên các video đã xét (dict thuần cho ``st.dataframe``)."""
    tk = anh.thong_ke or {}
    tong_all = sum(tk[g].tong for g in GD_THEO_VIDEO if g in tk) or 0.0
    ds = []
    for g in (*GD_THEO_VIDEO, "VIDEO"):
        t = tk.get(g)
        if not t or not t.so_mau:
            continue
        ds.append({"Công đoạn": "Cả video (thành công)" if g == "VIDEO" else TEN_GIAI_DOAN.get(g, g),
                   "Số video": t.so_mau,
                   "Trung vị": thoi_luong(t.trung_vi), "p95": thoi_luong(t.p95), "Tổng": thoi_luong(t.tong),
                   "Tỷ lệ": "" if g == "VIDEO" or not tong_all else f"{100 * t.tong / tong_all:.0f}%"})
    return ds


def dong_su_kien(anh: AnhDongBo, so: int = SO_SU_KIEN_HIEN) -> list:
    import time as _t
    return [f"{_t.strftime('%H:%M:%S', _t.localtime(e.luc))}  {e.noi_dung}" for e in list(anh.su_kien)[-so:]]


def dong_hieu_suat(hs: Optional[dict]) -> list:
    """``[(mức, câu)]`` tổng kết hiệu suất SAU lượt (``kq["hieu_suat"]`` = ``SoDongBo.tom_tat``)."""
    if not hs:
        return []
    gd = hs.get("giai_doan") or {}

    def tv(g):
        x = (gd.get(g) or {}).get("trung_vi_s")
        return thoi_luong(x) if x is not None else "—"

    cau = (f"Hiệu suất: {hs.get('video_moi_gio') or '—'} video/giờ"
           + (f", {hs['media_gio_moi_gio']} giờ audio/giờ" if hs.get("media_gio_moi_gio") else "")
           + f"; tải {mb(hs.get('byte_tai'))}, sau nén {mb(hs.get('byte_nen'))}; trung vị mỗi video: tải {tv(GD_TAI)}, "
             f"nén {tv(GD_NEN)}, kiểm {tv('VERIFYING')}, hỏi YouTube {tv('EXTRACTING')}, nghỉ {tv(GD_CHO)}.")
    ra = [("info", cau)]
    ng = hs.get("diem_nghen")
    if ng:
        ra.append(("info", f"Công đoạn tốn thời gian nhất: {TEN_GIAI_DOAN.get(ng['giai_doan'], ng['giai_doan'])} — "
                           f"{thoi_luong(ng['tong_s'])} ({100 * ng['ty_le']:.0f}% thời gian xử lý video)."))
    if hs.get("tai_co_hinh"):
        ra.append(("warning", f"{hs['tai_co_hinh']} video chỉ tải được định dạng CÓ HÌNH (không có audio-only ở client "
                              "đang dùng) — tốn băng thông hơn; vân tay không đổi."))
    return ra


def ve_tien_do_dong_bo(st: Any, anh: AnhDongBo) -> None:
    """Vẽ màn tiến độ (gọi mỗi lần trang chạy lại khi job đồng bộ đang chạy)."""
    st.header("⏳ Đang đồng bộ kênh")
    ty_le = anh.ty_le if anh.ty_le is not None else (
        (anh.kiem_da / anh.kiem_tong) * 0.02 if anh.giai_doan_luot == GD_KIEM and anh.kiem_tong else 0.0)
    st.progress(float(max(0.0, min(1.0, ty_le))), text=dong_tong(anh))
    kpi = the_kpi(anh)
    for hang in (kpi[:4], kpi[4:]):
        cot = st.columns(len(hang))
        for c, (nhan, gia_tri, ghi_chu) in zip(cot, hang):
            c.metric(nhan, gia_tri, help=ghi_chu or None)
    for loai, chu, ty in dong_video(anh):
        if loai == "tieu_de":
            st.markdown(f"**{chu}**")
        elif loai in ("tai", "nen") and ty is not None:
            st.progress(float(ty), text=chu)
        elif loai == "canh_bao":
            st.warning(chu)
        else:
            st.caption(chu)
    if anh.ly_do_dung:
        st.error(f"Lý do dừng: {anh.ly_do_dung}")
    bang = bang_cong_doan(anh)
    if bang:
        st.caption("Thời gian các công đoạn trên những video đã xét:")
        st.dataframe(bang, hide_index=True, width="stretch")
    su = dong_su_kien(anh)
    if su:
        with st.expander(f"Nhật ký gần nhất ({len(su)})", expanded=False):
            st.code("\n".join(su), language=None)
