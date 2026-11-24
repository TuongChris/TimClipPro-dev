# -*- coding: utf-8 -*-
"""Báo cáo V2 đã lưu từ trước vẫn đọc được (việc nhỏ #47).

``bao_cao_v2.doc_anh_chup_da_luu`` coi ảnh chụp THIẾU bất kỳ trường cấp trên nào của ``BaoCaoV2`` là «hỏng»
(``_TRUONG_ANH_CHUP`` = mọi trường của dataclass). Thêm một trường vào ``BaoCaoV2`` — kể cả có giá trị mặc định — là
mọi báo cáo đã lưu trong ``lichsu.db`` của người dùng thành «hỏng»: không xuất lại, không gửi Google Sheets được nữa.
Các test khác dựng ảnh chụp từ dataclass HIỆN TẠI nên không bao giờ thấy.

``anh_chup_bao_cao_v2_cu.json``: ảnh chụp CỐ ĐỊNH, dữ liệu TỔNG HỢP, đúng dạng engine lưu (``bc.to_dict()`` qua
``json.dumps``) từ khi có báo cáo V2 (35c7fc1, 04/10/2026) tới trước D-50 — đoạn khớp CHƯA có ``da_tinh_chinh``.
Đừng sinh lại file này cho test xanh: test đỏ nghĩa là báo cáo cũ của người dùng sẽ hỏng.
"""
import json
from pathlib import Path

import bao_cao_v2 as v2
from bang_ngang import HEADER_NGANG
from engine import Engine

ANH_CHUP_CU = Path(__file__).with_name("anh_chup_bao_cao_v2_cu.json")


def _gia_tri_lech(cu, moi, duong="") -> list:
    """Chỗ mà giá trị đã lưu KHÔNG còn y nguyên sau khi đọc lại (trường thêm về sau thì bỏ qua)."""
    if isinstance(cu, dict):
        return [x for k, v in cu.items()
                for x in (_gia_tri_lech(v, moi[k], f"{duong}{k}.") if k in moi else [f"{duong}{k} (mất)"])]
    if isinstance(cu, list):
        if not isinstance(moi, list) or len(moi) != len(cu):
            return [f"{duong[:-1]} (số phần tử)"]
        return [x for i, (a, b) in enumerate(zip(cu, moi)) for x in _gia_tri_lech(a, b, f"{duong}{i}.")]
    return [] if cu == moi else [f"{duong[:-1]}: {cu!r} → {moi!r}"]


def test_anh_chup_bao_cao_v2_luu_tu_truoc_van_doc_duoc():
    du_lieu = ANH_CHUP_CU.read_text(encoding="utf-8")
    bc = v2.doc_anh_chup_da_luu(v2.CHINH_SACH_V2, du_lieu)
    assert isinstance(bc, v2.BaoCaoV2), (
        f"Báo cáo V2 lưu từ trước nay đọc thành {bc!r}: mọi báo cáo cũ trong lịch sử của người dùng sẽ không xuất / "
        "gửi Google Sheets được nữa. Có lẽ vừa thêm trường vào BaoCaoV2 mà doc_anh_chup_da_luu đòi đủ mọi trường "
        "(_TRUONG_ANH_CHUP) — cho ảnh chụp cũ thiếu trường mới đọc bằng giá trị mặc định; ĐỪNG sửa file mẫu.")
    lech = _gia_tri_lech(json.loads(du_lieu), json.loads(json.dumps(bc.to_dict())))
    assert not lech, f"Đọc lại ảnh chụp cũ làm mất/đổi giá trị đã lưu: {lech}"
    assert [d.da_tinh_chinh for d in bc.doan] == [False, False]      # trường của D-50 vắng → mặc định

    # Xuất lại đúng như lúc chụp: mốc và link lấy từ ảnh chụp, không tính lại.
    ngang = dict(zip(HEADER_NGANG, v2.dong_ngang(bc)))
    assert ngang["Đoạn vi phạm 1 trong video vi phạm"] == (
        "00:15:15 – 00:39:10 · https://www.youtube.com/watch?v=vidthu00003&t=915")
    doc = [dict(zip(Engine.HEADER, d)) for d in v2.dong_doc(bc)]
    assert [d["🔗 Nhảy tới đúng mốc vi phạm"] for d in doc] == [
        "https://www.youtube.com/watch?v=vidthu00003&t=915", "https://www.youtube.com/watch?v=vidthu00003&t=7322"]
    assert v2.dong_pham_vi(bc)[2:6] == ["Một phần", "đã quét 03:00:00 đầu của video dài 05:12:40 (giới hạn video dài)",
                                        "chỉ tải phần đầu video", "01:30:00–01:31:00"]
