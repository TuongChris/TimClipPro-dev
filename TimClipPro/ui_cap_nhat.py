# -*- coding: utf-8 -*-
"""Bảng «ℹ️ Phiên bản và cập nhật» (brief §15) — tầng GIAO DIỆN, CHỈ ĐỌC trạng thái của launcher/updater.

Không gọi mạng, không chạy updater trong tiến trình app (updater là tiến trình NGOÀI — launcher). Thao tác
duy nhất: hoãn / bỏ hoãn (file ``update_state/hoan.json`` của cài đặt).
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import streamlit as st

import managed_update as mu


def _doc(path: str):
    return mu.doc_json(path, bat_buoc_hop_le=False)


def _ban_dang_chay() -> str:
    pb = os.environ.get("TIMCLIP_RELEASE", "")
    if pb:
        return pb
    dau = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), mu.TEN_DAU_RELEASE)
    try:
        with open(dau, encoding="utf-8") as f:
            return str(json.load(f).get("phien_ban") or "")
    except (OSError, ValueError):
        return ""


def ve_phien_ban(eng) -> None:
    goc = os.environ.get("TIMCLIP_INSTALLATION_ROOT", "")
    if os.environ.get("TIMCLIP_RUNTIME_MODE") != "managed" or not goc:
        st.caption("Bản phát triển (chế độ legacy) — không tự cập nhật; cập nhật mã do người phát triển "
                   "quản lý.")
        return
    cd = mu.CaiDat(goc=goc, state_root=os.path.dirname(eng.data_dir))
    dang_chay = _ban_dang_chay() or "?"
    cur = _doc(cd.file_trang_thai("current.json")) or {}
    kich_hoat = cur.get("phien_ban", "") if isinstance(cur, dict) else ""
    st.markdown(f"**Đang chạy:** {dang_chay} · **Đang kích hoạt:** {kich_hoat or '(chưa có)'}")
    if kich_hoat and kich_hoat != dang_chay:
        st.warning(f"Bản {kich_hoat} đã được kích hoạt — đóng và mở lại ứng dụng bằng launcher để dùng "
                   "bản mới; bản đang mở không nhận việc mới.")
    nk = _doc(cd.file_trang_thai("journal.json"))
    if isinstance(nk, dict) and nk.get("trang_thai"):
        tt, uv = nk.get("trang_thai"), nk.get("ung_vien", "")
        ls = nk.get("lich_su") or []
        luc = ls[-1].get("luc", "") if ls and isinstance(ls[-1], dict) else ""
        mo_ta = {mu.STAGED: "đã tải + kiểm xong, chờ lúc rảnh để áp dụng",
                 mu.ACTIVE: "đã áp dụng", mu.WAITING_APPROVAL: "chờ duyệt migration",
                 mu.BLOCKED: "bị chặn — cần kiểm tay", mu.QUARANTINED: "bị cách ly"}.get(tt, tt)
        st.caption(f"Lượt cập nhật gần nhất: {uv or '—'} — {mo_ta} (lúc {luc or '?'}).")
        if nk.get("loi"):
            st.caption(f"Ghi chú: {str(nk['loi'])[:200]}")
    cach_ly = _doc(cd.file_trang_thai("quarantine.json"))
    if isinstance(cach_ly, dict) and cach_ly:
        st.caption("Bản bị cách ly (không cài lại tự động): " + ", ".join(sorted(cach_ly)))
    try:
        rut = eng.cong_bao_tri.trang_thai_rut()
        dang = eng.cong_bao_tri.viec_dang_chay()
    except Exception:  # noqa: BLE001 — bảng thông tin không được làm hỏng trang
        rut, dang = None, []
    if rut:
        st.info(f"Đang chuẩn bị cập nhật ({rut.get('chu', '')}) — tạm không nhận việc mới.")
    st.caption(f"Việc đang chạy: {len(dang)}" + (" — " + ", ".join(v["ten"] for v in dang) if dang else ""))
    den = mu.doc_hoan(goc)
    if den:
        st.caption(f"Đã hoãn áp dụng cập nhật tới {datetime.fromtimestamp(den):%H:%M %d/%m}.")
        if st.button("▶ Bỏ hoãn cập nhật", key="cap_nhat_bo_hoan"):
            mu.bo_hoan(goc)
            st.rerun()
    elif st.button("⏸ Hoãn cập nhật 24 giờ", key="cap_nhat_hoan"):
        mu.dat_hoan(goc, 24)
        st.rerun()
