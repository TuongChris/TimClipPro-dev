# -*- coding: utf-8 -*-
"""Audit DR-8 (synthetic, không mạng): mục «Trạng thái YouTube» ở thanh bên sau một lượt có buổi công chiếu đã lên
lịch (premiere) chưa phát.

D-4 xếp lỗi «Premieres in …» vào ``UPCOMING_NOT_STARTED`` — câu của video nói «Không phải lỗi tool hay lỗi truy cập»,
và ``NGUONG_MO`` ghi rõ loại này «là chuyện của từng video, truy cập vẫn bình thường» (không có ngưỡng cầu dao). Trước
sửa: ``_DEM_THEO_LOAI`` thiếu loại này nên nó rơi vào ``other_failures`` và thanh bên báo VÀNG «KHÔNG thao tác YouTube
nào thành công — 1 lỗi (lỗi khác: 1), chưa tới ngưỡng dừng cả lượt».

``PhienYouTube`` thật + ``ham`` giả ném câu giống yt-dlp + ``scan_ui.dong_trang_thai_youtube`` thật.
"""
from __future__ import annotations

import pytest

import scan_ui
import truy_cap_youtube as t


def _chay_video_chua_phat(p: t.PhienYouTube, vid: str = "aaaaaaaaaaa") -> None:
    def ham():
        raise RuntimeError(f"ERROR: [youtube] {vid}: Premieres in 2 hours")

    with pytest.raises(t.LoiTruyCapYouTube) as ei:
        p.chay("metadata", ham, video_id=vid)
    # Tiền đề: D-4 phân loại đúng, cầu dao đóng — hỏng ở đây là lỗi dựng test.
    assert ei.value.that_bai.category == t.UPCOMING_NOT_STARTED
    assert p.tom_tat()["breaker_open"] is False


def _van_ban(dong: list) -> str:
    return " | ".join(f"{m}: {c}" for m, c in dong)


def test_video_chua_phat_khong_thanh_loi_khac_canh_bao_vang():
    p = t.PhienYouTube()
    _chay_video_chua_phat(p)
    so = p.tom_tat()
    assert so["upcoming_not_started"] == 1 and so["other_failures"] == 0

    dong = scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie(""), p, None)
    van_ban = _van_ban(dong)
    assert "lỗi khác" not in van_ban, f"video chưa phát bị đếm là «lỗi khác»: {van_ban}"
    assert not [c for m, c in dong if m == "warning" and "KHÔNG thao tác YouTube nào thành công" in c], (
        f"thanh bên báo động truy cập cho video chưa phát (loại không có ngưỡng): {van_ban}")
    # Không bỏ im: một dòng info nói rõ video chưa phát, không đoán «có thể đã bấm Dừng».
    assert ("info", "Lượt gần nhất: 1 video chưa phát (công chiếu / trực tiếp đã lên lịch) — chưa quét, lượt sau tự "
                    "thử lại. Không phải lỗi truy cập.") in dong, van_ban
    assert "bấm Dừng" not in van_ban


def test_co_thanh_cong_va_video_chua_phat_van_bao_truy_cap_binh_thuong():
    p = t.PhienYouTube()
    assert p.chay("metadata", lambda: {"id": "bbbbbbbbbbb"}, video_id="bbbbbbbbbbb")
    _chay_video_chua_phat(p)
    _chay_video_chua_phat(p, "ccccccccccc")
    dong = scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie(""), p, None)
    assert dong[0] == ("success", "Lượt gần nhất: truy cập YouTube bình thường."), _van_ban(dong)
    assert dong[1][0] == "info" and dong[1][1].startswith("Lượt gần nhất: 2 video chưa phát"), _van_ban(dong)


def test_loi_truy_cap_that_van_dem_rieng_khong_gop_video_chua_phat():
    p = t.PhienYouTube()
    _chay_video_chua_phat(p)
    with pytest.raises(t.LoiTruyCapYouTube):
        p.chay("download", lambda: (_ for _ in ()).throw(
            RuntimeError("ERROR: unable to download video data: HTTP Error 403: Forbidden")), video_id="ddddddddddd")
    dong = scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie(""), p, None)
    muc, cau = dong[0]
    assert muc == "warning" and "1 lỗi (HTTP 403: 1)" in cau, _van_ban(dong)
    assert any(m == "info" and "1 video chưa phát" in c for m, c in dong), _van_ban(dong)
