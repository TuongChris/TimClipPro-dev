# -*- coding: utf-8 -*-
"""Lưu tùy chọn người dùng; không lưu khóa API, mật khẩu hay nội dung google_key.json."""

from __future__ import annotations

import copy
import os
from dataclasses import fields
from typing import Any

from luu_tru import LoiDuLieu, doc_json_an_toan, ghi_json_an_toan


TEN_FILE = "cau_hinh.json"

# Chỉ các tùy chọn giao diện không bí mật này được phép ghi cùng Config.
GIA_TRI_GIAO_DIEN_MAC_DINH = {
    "sheet_link": "",
    "sheet_auto": True,
    "sheet_dang_ngang": True,
    "kho_dir": "",
    "thu_muc_quet_gan_nhat": "",
}


def _duong_dan(data_dir: str) -> str:
    return os.path.join(data_dir, TEN_FILE)


def doc_cau_hinh(data_dir: str) -> dict:
    """Đọc cấu hình người dùng. Chưa có file thì trả về dict rỗng."""
    du_lieu = doc_json_an_toan(_duong_dan(data_dir), {})
    if not isinstance(du_lieu, dict):
        raise LoiDuLieu(
            f"Cấu hình tại {_duong_dan(data_dir)} phải là một đối tượng JSON."
        )
    return du_lieu


def ghi_cau_hinh(data_dir: str, du_lieu: dict) -> None:
    """Ghi cấu hình nguyên tử bằng lớp lưu trữ dùng chung."""
    ghi_json_an_toan(_duong_dan(data_dir), du_lieu)


def ap_vao_config(cfg: Any, du_lieu: dict) -> list:
    """
    Áp các khóa hợp lệ, đúng kiểu vào Config và trả lại danh sách khóa bị bỏ qua.
    """
    bi_bo_qua = []
    cac_khoa_config = {truong.name for truong in fields(cfg)}
    for khoa, gia_tri in du_lieu.items():
        if khoa not in cac_khoa_config:
            bi_bo_qua.append(khoa)
            continue
        gia_tri_hien_tai = getattr(cfg, khoa)
        # Số nguyên vào trường số thực là hợp lệ: JSON không phân biệt 2 với 2.0, và
        # RUNBOOK hướng dẫn người dùng sửa tay data/cau_hinh.json. Nếu so kiểu cứng
        # thì họ gõ `"ytdlp_sleep_requests_s": 2` và giá trị bị bỏ qua âm thầm.
        # `bool` là lớp con của `int` nên phải loại riêng, kẻo True thành 1.0.
        if (isinstance(gia_tri_hien_tai, float)
                and isinstance(gia_tri, int)
                and not isinstance(gia_tri, bool)):
            gia_tri = float(gia_tri)
        if type(gia_tri) is not type(gia_tri_hien_tai):
            bi_bo_qua.append(khoa)
            continue
        setattr(cfg, khoa, gia_tri)
    return bi_bo_qua


def ap_tung_khoa_co_kiem(cfg: Any, du_lieu: dict) -> tuple[Any, list, list]:
    """
    Áp ``du_lieu`` lên BẢN SAO của ``cfg`` sao cho kết quả qua ``validate()``, hạ cấp theo
    TỪNG khoá chứ không theo cả file (audit C-5).

    Trả về ``(cfg_moi, bi_bo_qua, bi_tu_choi)``: ``bi_bo_qua`` = khoá lạ/sai kiểu như
    ``ap_vao_config``; ``bi_tu_choi`` = danh sách ``(khoa, ly_do)`` của các khoá đúng kiểu nhưng
    làm ``validate()`` trượt — chúng giữ giá trị của ``cfg`` gốc, mọi khoá khác của người dùng
    vẫn được áp. Một giá trị gõ tay ngoài dải không được kéo theo cookie, top_n... về mặc định.

    Thứ tự xét: (1) áp hết, qua validate thì xong; (2) bỏ đúng MỘT khoá (theo thứ tự trường
    dataclass, như ``lay_tu_config``) mà qua validate thì khoá đó là thủ phạm duy nhất;
    (3) áp lần lượt theo thứ tự trường, khoá nào làm validate trượt thì trả lại, lặp tới khi
    không khoá bị trả nào áp lại được. Kết quả xác định với cùng một file. Chính ``cfg`` gốc
    không qua validate thì ném ``ValueError`` (người gọi quay về mặc định cả file).
    """
    cfg_moi = copy.deepcopy(cfg)
    bi_bo_qua = ap_vao_config(cfg_moi, du_lieu)
    try:
        cfg_moi.validate()
        return cfg_moi, bi_bo_qua, []
    except ValueError as e:
        ly_do_chung = str(e)

    # Chỉ các khoá đã áp thật và khác giá trị gốc mới có thể là thủ phạm.
    da_ap = [
        truong.name for truong in fields(cfg)
        if truong.name in du_lieu and truong.name not in bi_bo_qua
        and getattr(cfg_moi, truong.name) != getattr(cfg, truong.name)
    ]
    for khoa in da_ap:
        thu = copy.deepcopy(cfg)
        ap_vao_config(thu, {k: du_lieu[k] for k in da_ap if k != khoa})
        try:
            thu.validate()
        except ValueError:
            continue
        return thu, bi_bo_qua, [(khoa, ly_do_chung)]

    cfg_moi = copy.deepcopy(cfg)
    cfg_moi.validate()  # gốc hỏng -> ValueError cho người gọi
    ly_do: dict = {}
    cho = list(da_ap)
    while cho:
        con_lai = []
        for khoa in cho:
            thu = copy.deepcopy(cfg_moi)
            ap_vao_config(thu, {khoa: du_lieu[khoa]})
            try:
                thu.validate()
            except ValueError as e:
                ly_do[khoa] = str(e)
                con_lai.append(khoa)
                continue
            cfg_moi = thu
            ly_do.pop(khoa, None)
        if len(con_lai) == len(cho):
            break
        cho = con_lai
    return cfg_moi, bi_bo_qua, [(khoa, ly_do[khoa]) for khoa in cho]


def lay_tu_config(cfg: Any) -> dict:
    """Trích toàn bộ trường dataclass Config thành dict để lưu."""
    return {truong.name: getattr(cfg, truong.name) for truong in fields(cfg)}
