# -*- coding: utf-8 -*-
"""Giao diện gửi Google Sheets: chọn đích cho từng lượt, hàng đợi lưu bền, hồ sơ đích, binding khoá.

Tầng GIAO DIỆN (Streamlit) — logic nằm ở ``sheet_destinations`` (hồ sơ, ảnh chụp ghim) và ``outbox``
(hàng đợi, người gửi). Hàm nào chạy trong luồng nền (callback của lô quét) KHÔNG đọc
``st.session_state``. Thiết kế: docs/MANAGED_RUNTIME_DESIGN.md.
"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

import bang_ngang
import bao_cao_v2
import outbox
import sheet_destinations as sd

CHI_LUU = ""          # giá trị lựa chọn «Chỉ lưu cục bộ»
_VIEC_DANG_CHO = (outbox.PENDING, outbox.RETRY_WAIT, outbox.CLAIMED, outbox.SENDING)
# Việc cần người dùng để ý: luôn liệt kê ĐỦ (không bị việc đã gửi mới hơn đẩy khỏi danh sách).
_VIEC_CAN_XEM = (outbox.UNKNOWN, outbox.BLOCKED_CONFIG, outbox.BLOCKED_REPORT, *_VIEC_DANG_CHO)
_VIEC_XONG = (outbox.SENT, outbox.CANCELLED)


def _thu(ham, *a, **k) -> bool:
    """Chạy một thao tác của người dùng; lỗi nghiệp vụ (trạng thái vừa đổi, hồ sơ không hợp lệ) →
    ``st.error``, không để traceback lên giao diện."""
    try:
        ham(*a, **k)
        return True
    except (outbox.LoiHangDoi, sd.LoiDichGui) as e:
        st.error(str(e))
        return False


def _db(eng) -> str:
    return eng.sqlite_file


def _header(eng, schema_id: str) -> list:
    return list(bang_ngang.HEADER_NGANG) if schema_id == sd.SCHEMA_NGANG else list(eng.HEADER)


def dam_bao_nguoi_gui(eng, *, bat_buoc: bool = False) -> None:
    """Người gửi nền của tiến trình app: chạy khi có việc chờ (hoặc khi bắt đầu lô có đích).
    Một luồng mỗi DB cho mọi phiên trình duyệt; Watch đang giữ quyền thì luồng này tự chờ."""
    tt = outbox.tom_tat(_db(eng))
    if bat_buoc or any(tt[t] for t in _VIEC_DANG_CHO):
        outbox.dam_bao_chay_nen(_db(eng), eng.data_dir)


# ---------------------------------------------------------------------------
#  Chọn đích cho lượt quét (gần nút Bắt đầu)
# ---------------------------------------------------------------------------

def chon_dich(eng, *, key: str, nguon_chung: bool = False) -> tuple:
    """Hộp chọn «Đích gửi» + «Tự động gửi khi từng video hoàn tất». Trả ``(dich_id, tu_dong)``."""
    if nguon_chung:
        st.caption("📤 Chế độ «Một video gốc chung cho cả lô» chưa có hợp đồng Google Sheets riêng — "
                   "chưa hỗ trợ đích gửi; kết quả chỉ xuất CSV.")
        return CHI_LUU, False
    ds = sd.ds_dich(_db(eng), bo_luu_tru=True)
    lua_chon = [CHI_LUU] + [d.id for d in ds]
    nhan = {CHI_LUU: "Chỉ lưu cục bộ (không gửi Google Sheets)",
            **{d.id: d.nhan + (" — ⏸ đang tạm dừng gửi (việc vẫn xếp hàng)"
                               if d.trang_thai == sd.TT_TAM_DUNG else "") for d in ds}}
    # Mỗi tab quét giữ lựa chọn RIÊNG (hai ô cùng ghi một biến thì ô vẽ sau đè ô trước); mặc định là
    # đích của lượt bắt đầu gần nhất.
    hien = st.session_state.get(f"{key}_dich_chon",
                                st.session_state.get("dich_gui_gan_nhat", CHI_LUU))
    if hien not in lua_chon:
        hien = CHI_LUU
    chon = st.selectbox("Đích gửi", lua_chon, index=lua_chon.index(hien),
                        format_func=lambda x: nhan.get(x, x), key=f"{key}_dich_gui")
    st.session_state[f"{key}_dich_chon"] = chon
    tu_dong = False
    if chon:
        # Lựa chọn lưu ở khoá KHÔNG phải widget: lúc quét các tab bị ẩn, Streamlit dọn state của widget
        # — người dùng đã bỏ tick không được tự bật lại sau lô.
        khoa_chon = f"{key}_tu_dong_chon"
        tu_dong = st.checkbox("Tự động gửi khi từng video hoàn tất",
                              value=st.session_state.get(khoa_chon, True), key=f"{key}_tu_dong_gui")
        st.session_state[khoa_chon] = tu_dong
        st.caption("Đích được GHIM lúc bấm Bắt đầu: đổi lựa chọn giữa chừng chỉ áp dụng cho lượt sau.")
    elif not ds:
        st.caption("Chưa có hồ sơ đích nào — tạo ở tab «📤 Gửi Google Sheets».")
    return chon, tu_dong


def chot_cho_lo(eng, dich_id: str, tu_dong: bool, lo_id: str) -> tuple:
    """``(y_dinh | None, lỗi)`` cho lô sắp chạy. Preflight CỤC BỘ (hồ sơ còn hoạt động, file khoá
    đúng tài khoản dịch vụ) — báo TRƯỚC khi quét, không gọi Google."""
    if not dich_id or not tu_dong:
        return None, ""
    try:
        y = sd.chot_y_dinh(_db(eng), dich_id, installation_id=eng.installation_id(), lo_id=lo_id)
    except sd.LoiDichGui as e:
        return None, str(e)
    ly_do = outbox.kiem_khoa_cuc_bo(_db(eng), y.dich)
    if ly_do:
        return None, (f"Chưa bắt đầu: đích «{y.dich.ten}» chưa dùng được — {ly_do} "
                      "(muốn quét ngay thì chọn «Chỉ lưu cục bộ»).")
    return y, ""


def trang_thai_viec_lo(eng, lo_id: str) -> dict:
    """``{mã việc: ViecGui}`` của một lô — cho cột «Sheets» của bảng trạng thái."""
    if not lo_id:
        return {}
    return {v.id: v for v in outbox.ds_viec(_db(eng), lo_id=lo_id)}


def mo_ta_lo(eng, dich_nhan: str, lo_id: str) -> str:
    if not lo_id:
        return ""
    tt = outbox.tom_tat(_db(eng), lo_id=lo_id)
    cho = sum(tt[t] for t in _VIEC_DANG_CHO)
    return (f"📤 «{dich_nhan}» — đã gửi {tt[outbox.SENT]}, đang chờ {cho}, "
            f"bị chặn {tt[outbox.BLOCKED_CONFIG] + tt[outbox.BLOCKED_REPORT]}, "
            f"không rõ {tt[outbox.UNKNOWN]}. Quét không chờ Google; việc chờ đã lưu bền.")


def banner_lo_dang_chay(eng, dich_id: str, dich_nhan: str, tab_key: str) -> None:
    """Lượt đang chạy gửi A; lựa chọn B (hồ sơ KHÁC, ở tab đã bắt đầu lượt) chỉ dùng cho lượt tiếp theo.
    So theo MÃ hồ sơ — hồ sơ đổi tên giữa lô không phải "lựa chọn khác". Không biết tab đã bắt đầu lượt
    (phiên NHẬN LẠI lô của phiên khác) → không có lựa chọn nào để so, không báo (audit F-1)."""
    if not tab_key:
        return
    chon = st.session_state.get(f"{tab_key}_dich_chon", CHI_LUU)
    if chon == (dich_id or CHI_LUU):
        return
    nhan_chon = "Chỉ lưu cục bộ"
    if chon:
        d = sd.lay_dich(_db(eng), chon)
        nhan_chon = d.nhan if d is not None else chon
    st.info(f"Lượt đang chạy gửi «{dich_nhan or 'Chỉ lưu cục bộ'}»; lựa chọn «{nhan_chon}» dùng cho "
            "lượt tiếp theo.")


# ---------------------------------------------------------------------------
#  Gửi thủ công (gửi thêm một bản) — payload dựng lại TỪ ẢNH CHỤP đã lưu, không quét lại
# ---------------------------------------------------------------------------

def _payload_tu_lich_su(eng, job_id: int, schema_id: str) -> tuple:
    """``(rows | None, lý_do)``: dựng lại dòng của một lần quét từ ảnh chụp V2 đã lưu."""
    bc = eng.bao_cao_cua_job(job_id)
    if bc is None:
        return None, "Lần quét theo luật báo cáo cũ — hàng đợi gửi chỉ nhận báo cáo V2."
    if not bao_cao_v2.la_loi_bao_cao(bc) and bc.trang_thai != "ok":
        # Như đường tự động: chỉ kết quả QUÉT XONG mới gửi — dòng «(LỖI: …)» không bao giờ lên Sheets.
        return None, "Lần quét lỗi — không gửi Google Sheets."
    try:
        rows = eng.dong_bao_cao_job(job_id, dang_ngang=schema_id == sd.SCHEMA_NGANG)
    except bao_cao_v2.LoiXuatBaoCaoV2 as e:
        return None, str(e)
    if rows is None:
        return None, "Lần quét theo luật báo cáo cũ — hàng đợi gửi chỉ nhận báo cáo V2."
    if not rows:
        return None, "Lần quét này không có dòng nào để gửi."
    return rows, ""


def gui_thu_cong(eng, job_ids: list, dich_id: str, *, cho_phep_trung: bool) -> tuple:
    """Tạo việc gửi THỦ CÔNG cho các lần quét → ``(số_việc_tạo, [lý do bỏ qua], cần_xác_nhận)``."""
    try:
        y = sd.chot_y_dinh(_db(eng), dich_id, installation_id=eng.installation_id())
    except sd.LoiDichGui as e:
        return 0, [str(e)], False
    tao, bo_qua, can_xac_nhan = 0, [], False
    for job_id in job_ids:
        rows, ly_do = _payload_tu_lich_su(eng, job_id, y.dich.schema_id)
        if rows is None:
            bo_qua.append(f"#{job_id}: {ly_do}")
            continue
        bc = eng.bao_cao_cua_job(job_id)
        try:
            outbox.tao_viec_thu_cong(_db(eng), y, job_id, _header(eng, y.dich.schema_id), rows,
                                     chinh_sach=getattr(bc, "chinh_sach", ""),
                                     cho_phep_trung=cho_phep_trung)
            tao += 1
        except outbox.LoiHangDoi as e:
            bo_qua.append(f"#{job_id}: {e}")
            can_xac_nhan = True
    if tao:
        dam_bao_nguoi_gui(eng, bat_buoc=True)
    return tao, bo_qua, can_xac_nhan


def nut_gui_thu_cong(eng, results: list, *, key: str) -> None:
    """Nút «Gửi thêm (thủ công)» cho các kết quả của lô vừa quét."""
    nut_gui_cho_job(eng, [r.job_id for r in results
                          if getattr(r, "job_id", None) and r.status == "ok"], key=key)


def nut_gui_cho_job(eng, job_ids: list, *, key: str) -> None:
    """Nút «Gửi thêm (thủ công)» cho các lần quét đã lưu (lô vừa xong, hoặc tab Lịch sử)."""
    ds = sd.ds_dich(_db(eng), bo_luu_tru=True)
    if not job_ids or not ds:
        return
    with st.expander("📤 Gửi thêm (thủ công) tới Google Sheets", expanded=False):
        st.caption("Dùng khi lượt quét chỉ lưu cục bộ, hoặc muốn gửi thêm một bản sang bảng khác. "
                   "Dòng dựng lại từ ảnh chụp báo cáo đã lưu — không quét lại.")
        nhan = {d.id: d.nhan for d in ds}
        dich = st.selectbox("Gửi tới", list(nhan), format_func=nhan.get, key=f"{key}_dich")
        trung = st.checkbox("Tôi hiểu có thể tạo dòng TRÙNG nếu đã gửi trước đó",
                            key=f"{key}_trung")
        if st.button("📤 Tạo việc gửi", key=f"{key}_nut"):
            tao, bo_qua, can = gui_thu_cong(eng, job_ids, dich, cho_phep_trung=trung)
            if tao:
                st.success(f"Đã xếp {tao} việc gửi (lưu bền) — xem tab «📤 Gửi Google Sheets».")
            for x in bo_qua:
                st.warning(x)
            if can and not trung:
                st.info("Có lần quét đã gửi tới bảng này: tick ô xác nhận nếu vẫn muốn gửi thêm.")


# ---------------------------------------------------------------------------
#  Tab «📤 Gửi Google Sheets»
# ---------------------------------------------------------------------------

def _doi_tam_dung(db: str, khoa: str) -> None:
    outbox.dat_tam_dung(db, bool(st.session_state.get(khoa)))


def _ve_hang_doi(eng) -> None:
    db = _db(eng)
    tam_dung = outbox.dang_tam_dung(db)
    # Khoá widget mang TRẠNG THÁI TRONG DB: phiên trình duyệt khác đổi trạng thái thì phiên này vẽ một
    # widget mới đúng trạng thái — không bao giờ ghi ngược giá trị cũ của riêng phiên này vào DB.
    khoa = f"gui_tam_dung_{int(tam_dung)}"
    st.toggle("⏸ Tạm dừng toàn bộ việc gửi (quét vẫn chạy, việc vẫn xếp hàng)", value=tam_dung,
              key=khoa, on_change=_doi_tam_dung, args=(db, khoa))
    tt = outbox.tom_tat(db)
    st.caption(" · ".join(f"{outbox.NHAN_TRANG_THAI[k]}: {v}" for k, v in tt.items() if v)
               or "Hàng đợi trống.")
    loc = st.radio("Hiện", ["Cần xử lý / đang chờ", "Đã xong (gần nhất)", "Tất cả (gần nhất)"],
                   horizontal=True, key="gui_loc")
    if loc.startswith("Cần"):
        ds = outbox.ds_viec(db, trang_thai=_VIEC_CAN_XEM, gioi_han=100_000)
    elif loc.startswith("Đã xong"):
        ds = outbox.ds_viec(db, trang_thai=_VIEC_XONG, gioi_han=300)
    else:
        ds = (outbox.ds_viec(db, trang_thai=_VIEC_CAN_XEM, gioi_han=100_000)
              + outbox.ds_viec(db, trang_thai=_VIEC_XONG, gioi_han=300))
    if not ds:
        st.caption("Không có việc nào ở mục này.")
        return

    def nhan_dich(v) -> str:
        try:
            return v.dich.nhan
        except sd.LoiDichGui:
            return "(đích đã ghim bị hỏng)"

    st.dataframe(pd.DataFrame([{
        "Mã": v.id[:8], "Lần quét": f"#{v.job_id}" if v.job_id else "—",
        "Nguồn": "tự động" if v.nguon == outbox.NGUON_AUTO else "thủ công",
        "Đích (đã ghim)": nhan_dich(v), "Trạng thái": outbox.NHAN_TRANG_THAI.get(v.trang_thai),
        "Lần thử": v.so_lan_thu, "Dòng": v.so_dong,
        "Lý do / ghi chú": (v.loi or ("đã xoá lần quét — chỉ giữ biên nhận" if v.da_xoa_job
                                      else ""))[:160],
        "Cập nhật": datetime.fromtimestamp(v.sua_luc).strftime("%d/%m %H:%M:%S"),
    } for v in ds]), width="stretch", hide_index=True)
    with st.expander("Xử lý một việc gửi", expanded=False):
        chon = st.selectbox("Việc", [v.id for v in ds],
                            format_func=lambda i: next(
                                f"{v.id[:8]} — #{v.job_id} — {outbox.NHAN_TRANG_THAI[v.trang_thai]}"
                                for v in ds if v.id == i), key="gui_chon_viec")
        v = next(x for x in ds if x.id == chon)
        st.caption(f"Mã việc {v.id} · lần quét #{v.job_id} · máy {v.dich.installation_id[:8] if _dich_doc_duoc(v) else '?'}")
        if v.trang_thai == outbox.UNKNOWN:
            st.warning("Request có thể đã tới Google mà phản hồi bị mất — tool KHÔNG tự gửi lại. Mở "
                       "Sheet, tìm dòng của lần quét này: có rồi thì bấm «Đã có trên Sheet»; chưa "
                       "có thì «Gửi lại» (chấp nhận khả năng trùng).")
            tab = outbox.tab_da_ghim(_db(eng), v)
            if tab is not None:
                st.caption(f"Tab đích đã ghim: mã {tab.worksheet_id} (tên lúc ghim «{tab.worksheet_ten}») — tìm "
                           "dòng ở ĐÚNG tab này (tab có thể đã đổi tên); «Gửi lại» cũng chỉ ghi vào tab này.")
            khong_gui_lai = outbox.ly_do_khong_gui_lai(_db(eng), v)
            if khong_gui_lai:
                st.error(khong_gui_lai)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Đã kiểm: dòng đã có trên Sheet", key="gui_xac_nhan"):
                    if _thu(outbox.xac_nhan_da_gui, _db(eng), v.id, "người dùng đối soát trên giao diện"):
                        st.rerun()
            with c2:
                # Ô đồng ý gắn ĐÚNG việc đang chọn: đổi sang việc khác thì phải đồng ý lại.
                dong_y = st.checkbox("Tôi chấp nhận có thể trùng dòng", key=f"gui_dong_y_trung_{v.id}")
                if st.button("⚠️ Gửi lại", key="gui_lai_unknown", disabled=not dong_y or bool(khong_gui_lai)):
                    if _thu(outbox.gui_lai_co_the_trung, _db(eng), v.id):
                        dam_bao_nguoi_gui(eng, bat_buoc=True)
                        st.rerun()
        if v.trang_thai in (outbox.BLOCKED_CONFIG, outbox.RETRY_WAIT):
            if st.button("🔁 Thử gửi lại (sau khi đã sửa bảng/khoá)", key="gui_thu_lai"):
                if _thu(outbox.thu_lai, _db(eng), v.id):
                    dam_bao_nguoi_gui(eng, bat_buoc=True)
                    st.rerun()
        if v.trang_thai in (outbox.PENDING, outbox.RETRY_WAIT, outbox.BLOCKED_CONFIG,
                            outbox.BLOCKED_REPORT, outbox.UNKNOWN):
            huy = st.checkbox("Tôi muốn huỷ việc gửi này", key=f"gui_huy_xn_{v.id}")
            if st.button("✖ Huỷ việc gửi", key="gui_huy", disabled=not huy):
                if _thu(outbox.huy, _db(eng), v.id):
                    st.rerun()


def _dich_doc_duoc(v) -> bool:
    try:
        v.dich
        return True
    except sd.LoiDichGui:
        return False


def _ve_ho_so(eng) -> None:
    db = _db(eng)
    ds = sd.ds_dich(db)
    if ds:
        st.dataframe(pd.DataFrame([{
            "Tên": d.ten, "Tab": d.worksheet_ten,
            # Cột trộn số (mã tab) với chữ làm Arrow không chuyển được («Could not convert 'theo tên
            # …' … int64», PC2 12/10/2026): hiển thị TOÀN CHUỖI — giá trị lưu trong DB không đổi.
            "Mã tab": (str(d.worksheet_id) if d.worksheet_id is not None
                       else str(d.gid_da_chot) if d.gid_da_chot is not None
                       else "theo tên — chốt ở lần gửi đầu"),
            "Định dạng": sd.SCHEMA_NHAN.get(d.schema_id), "Trạng thái": d.trang_thai,
            "Revision": d.phien_ban, "Khoá": d.xac_thuc_ref,
        } for d in ds]), width="stretch", hide_index=True)
    xt = sd.ds_xac_thuc(db)
    with st.expander("➕ Thêm hồ sơ đích", expanded=not ds):
        if not xt:
            st.info("Cần đăng ký khoá Google (binding) trước — mục bên dưới.")
        else:
            ten = st.text_input("Tên hồ sơ (để không gửi nhầm)", key="hs_ten")
            link = st.text_input("Link Google Sheet (mở đúng TAB rồi chép link — có «#gid=…»)",
                                 key="hs_link")
            tab = st.text_input("Tên tab (đối chiếu ở lần gửi đầu — tab mang tên khác thì chặn)",
                                value=sd.TAB_MAC_DINH, key="hs_tab")
            dang = st.radio("Định dạng", list(sd.SCHEMA_NHAN), format_func=sd.SCHEMA_NHAN.get,
                            horizontal=True, key="hs_dang")
            ref = st.selectbox("Khoá Google", [x.ref for x in xt], key="hs_ref")
            if st.button("Lưu hồ sơ", key="hs_luu"):
                try:
                    sid, gid = sd.phan_tich_link(link)
                    d = sd.tao_dich(db, ten=ten, spreadsheet_id=sid, worksheet_id=gid,
                                    worksheet_ten=tab, schema_id=dang, xac_thuc_ref=ref,
                                    workspace=eng.runtime.workspace)
                    st.success(f"Đã tạo hồ sơ «{d.ten}».")
                    if gid is None:
                        st.warning("Link chưa có mã tab (gid) — tab sẽ được chốt theo TÊN ở lần gửi "
                                   "đầu; từ đó gửi theo mã. Nên chép link khi đang mở đúng tab.")
                except sd.LoiDichGui as e:
                    st.error(str(e))
    if ds:
        with st.expander("✏️ Sửa / tạm dừng / lưu trữ một hồ sơ", expanded=False):
            chon = st.selectbox("Hồ sơ", [d.id for d in ds],
                                format_func=lambda i: next(d.nhan for d in ds if d.id == i),
                                key="hs_chon")
            d = next(x for x in ds if x.id == chon)
            ten_moi = st.text_input("Đổi tên", value=d.ten, key=f"hs_ten_moi_{d.id}")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Lưu tên (revision mới)", key="hs_doi_ten") and ten_moi != d.ten:
                    if _thu(sd.sua_dich, db, d.id, ten=ten_moi):
                        st.rerun()
            with c2:
                if d.trang_thai == sd.TT_HOAT_DONG:
                    if st.button("⏸ Tạm dừng gửi", key="hs_tam_dung"):
                        if _thu(sd.doi_trang_thai, db, d.id, sd.TT_TAM_DUNG):
                            st.rerun()
                elif st.button("▶ Bật lại", key="hs_bat"):
                    if _thu(sd.doi_trang_thai, db, d.id, sd.TT_HOAT_DONG):
                        st.rerun()
            with c3:
                if d.trang_thai != sd.TT_LUU_TRU and st.button("🗄 Lưu trữ", key="hs_luu_tru"):
                    if _thu(sd.doi_trang_thai, db, d.id, sd.TT_LUU_TRU):
                        st.rerun()
            with c4:
                if st.button("🗑 Xoá (chỉ khi chưa có việc gửi)", key="hs_xoa"):
                    if _thu(sd.xoa_dich, db, d.id):
                        st.rerun()
            st.caption("Sửa = revision MỚI: lượt quét đang chạy và việc đã xếp hàng vẫn gửi theo đích cũ đã "
                       "ghim; chỉ lượt sau dùng revision mới.")
            khoa_ds = [x.ref for x in sd.ds_xac_thuc(db) if x.trang_thai == sd.TT_HOAT_DONG]
            if khoa_ds:
                k1, k2 = st.columns([3, 2])
                with k1:
                    khoa_moi = st.selectbox(
                        "Khoá Google của hồ sơ", khoa_ds,
                        index=khoa_ds.index(d.xac_thuc_ref) if d.xac_thuc_ref in khoa_ds else 0,
                        key=f"hs_khoa_moi_{d.id}")
                with k2:
                    if st.button("Lưu khoá (revision mới)", key="hs_luu_khoa") and khoa_moi != d.xac_thuc_ref:
                        if _thu(sd.sua_dich, db, d.id, xac_thuc_ref=khoa_moi):
                            st.rerun()
            link_moi = st.text_input("Link Google Sheet mới (để trống = giữ bảng/tab hiện tại)",
                                     key=f"hs_link_moi_{d.id}")
            tab_moi = st.text_input("Tên tab (đối chiếu ở lần gửi đầu của revision mới)",
                                    value=d.worksheet_ten, key=f"hs_tab_moi_{d.id}")
            if st.button("Lưu link/tab (revision mới)", key="hs_luu_dich"):
                try:
                    sid, gid = (sd.phan_tich_link(link_moi) if link_moi.strip()
                                else (d.spreadsheet_id, d.worksheet_id))
                except sd.LoiDichGui as e:
                    st.error(str(e))
                else:
                    if _thu(sd.sua_dich, db, d.id, spreadsheet_id=sid, worksheet_id=gid,
                            worksheet_ten=tab_moi.strip()):
                        st.rerun()
            if st.button("🔎 Kiểm cấu hình (chỉ đọc — có gọi Google)", key="hs_kiem"):
                if d.trang_thai == sd.TT_LUU_TRU:
                    st.warning("Hồ sơ đã lưu trữ.")
                else:
                    try:
                        y = sd.chot_y_dinh(db, d.id, installation_id=eng.installation_id())
                        ok, tb = outbox.kiem_cau_hinh(db, y.dich, _header(eng, y.dich.schema_id))
                    except sd.LoiDichGui as e:
                        ok, tb = False, str(e)
                    (st.success if ok else st.error)(tb)


def _ve_khoa(eng) -> None:
    db = _db(eng)
    for x in sd.ds_xac_thuc(db):
        st.caption(f"🔑 «{x.ref}» → {x.principal} · file {os.path.basename(x.duong_dan)} "
                   f"[{x.trang_thai}] — chia sẻ Sheet (Người chỉnh sửa) cho địa chỉ này.")
    with st.expander("➕ Đăng ký / cập nhật khoá Google (binding)", expanded=False):
        ref = st.text_input("Tên binding (chữ thường không dấu)", value=sd.REF_MAC_DINH,
                            key="xt_ref")
        duong = st.text_input("Đường dẫn file khoá JSON trên máy này",
                              value=eng.runtime.khoa_google_mac_dinh, key="xt_duong")
        if st.button("Đăng ký khoá", key="xt_luu"):
            try:
                x = sd.dang_ky_xac_thuc(db, ref, duong)
                st.success(f"Binding «{x.ref}» → {x.principal}.")
            except sd.LoiDichGui as e:
                st.error(str(e))


def _ve_nhap_link_cu(eng) -> None:
    """Link Sheet trong cấu hình cũ → hồ sơ (CHỈ khi người dùng bấm; không tự bật gửi)."""
    link = str(st.session_state.get("sheet_link") or "").strip()
    if not link:
        return
    if any(d.nguon == sd.NGUON_LINK_CU for d in sd.ds_dich(_db(eng))):
        return
    st.info("Cấu hình cũ có link Google Sheet. Bấm để tạo hồ sơ đích từ link đó — giống bản cũ: luôn "
            "tab tên «KetQuaQuet» (mã tab trong link được bỏ qua; mã thật chốt ở lần gửi đầu), khoá mặc "
            "định — sau đó chọn hồ sơ này ở ô «Đích gửi» khi quét.")
    if st.button("Tạo hồ sơ từ link cũ", key="nhap_link_cu"):
        try:
            dang = (sd.SCHEMA_NGANG if st.session_state.get("sheet_dang_ngang", True)
                    else sd.SCHEMA_DOC)
            d = sd.nhap_link_cu(_db(eng), link, schema_id=dang,
                                duong_dan_khoa=eng.runtime.khoa_google_mac_dinh,
                                workspace=eng.runtime.workspace)
            st.success(f"Đã có hồ sơ «{d.nhan}».")
        except sd.LoiDichGui as e:
            st.error(str(e))


def ve_tab(eng) -> None:
    st.subheader("📤 Gửi Google Sheets")
    st.caption("Mỗi lượt quét chọn một đích; kết quả từng video được XẾP HÀNG BỀN cùng lúc lưu lịch "
               "sử rồi gửi ngay. Tắt app / mất điện không làm mất việc đã xếp. Việc không rõ đã gửi "
               "chưa được giữ lại để bạn đối soát — tool không tự gửi lại mù.")
    _ve_nhap_link_cu(eng)
    st.markdown("**Hàng đợi gửi**")
    _ve_hang_doi(eng)
    st.markdown("**Hồ sơ đích**")
    _ve_ho_so(eng)
    st.markdown("**Khoá Google trên máy này**")
    _ve_khoa(eng)
