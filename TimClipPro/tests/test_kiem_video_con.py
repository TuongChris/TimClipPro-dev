# -*- coding: utf-8 -*-
"""Kiểm video vi phạm đã tìm thấy còn trên YouTube hay đã gỡ — theo dõi kết quả khiếu nại (D-51).

``Engine.video_vi_pham`` (chọn mã, chỉ đọc lịch sử). Dữ liệu tổng hợp trong thư mục tạm — không mạng, không khoá thật,
không dữ liệu thật.
"""

import contextlib
import sqlite3

import bao_cao_v2
from conftest import M
from engine import ScanResult


def _luu(eng, ma, *, ten="Video vi phạm", status="ok", so_khop=1, kenh=None, luc=""):
    """Một lần quét đã lưu; ``kenh=(tên, link)`` → kèm ảnh chụp báo cáo V2 (kênh chỉ nằm trong ảnh chụp)."""
    kq = ScanResult(source_name=ten, source_ref=f"https://www.youtube.com/watch?v={ma}", source_id=ma,
                    duration_s=600.0, status=status, matches=[M() for _ in range(so_khop)])
    if kenh:
        kq.channel_name, kq.channel_url = kenh
        kq.bao_cao = bao_cao_v2.dung_bao_cao(
            kq, thoi_diem_quet="2026-11-01 10:00:00", nguon_loai="youtube", tieu_de=ten, nguon_tieu_de="",
            ly_do_thieu_tieu_de="", ngay_dang=bao_cao_v2.NgayNguon(), goc_theo_clip={}, mo_ta_pham_vi="")
    job_id = eng.save_job(kq, "youtube")
    if luc:
        _sql(eng, "UPDATE jobs SET created_at=? WHERE id=?", luc, job_id)
    return job_id


def _sql(eng, lenh, *tham_so):
    with contextlib.closing(sqlite3.connect(eng.sqlite_file)) as cx, cx:
        cx.execute(lenh, tham_so)


def test_video_vi_pham_toan_lich_su_moi_ma_mot_dong_theo_lan_quet_moi_nhat(engine):
    a, d, c = "vidvipham0A", "vidvipham0D", "vidvipham0C"
    _luu(engine, a, ten="A lần đầu", luc="2026-09-01 08:00:00")
    _luu(engine, "vidloi0000B", status="error")                     # lỗi: không tính dù có dòng khớp
    _luu(engine, "vidamtinh0C", so_khop=0)                          # âm tính
    _luu(engine, "ngan", ten="mã sai")                              # không phải mã YouTube hợp lệ
    _luu(engine, "", ten="file trong máy")                          # không có mã
    _luu(engine, d, ten="D", kenh=("Kênh D", "https://www.youtube.com/channel/UCd"), luc="2026-10-05 09:00:00")
    _luu(engine, c, ten="C luật cũ")                                # không có ảnh chụp V2 → kênh trống
    _luu(engine, a, ten="A mới", kenh=("Kênh A", "https://www.youtube.com/@a"), luc="2026-11-02 10:00:00")
    _luu(engine, a, ten="A lỗi sau đó", status="error")             # lần lỗi mới hơn không đổi dòng của A
    ds = engine.video_vi_pham()
    assert [v["ma"] for v in ds] == [a, c, d], "mỗi mã một dòng, lần quét mới nhất trước"
    assert ds[0] == {"ma": a, "tieu_de": "A mới", "lan_quet_cuoi": "2026-11-02 10:00:00", "so_lan_quet": 2,
                     "kenh_ten": "Kênh A", "kenh_link": "https://www.youtube.com/@a"}
    assert (ds[1]["tieu_de"], ds[1]["so_lan_quet"], ds[1]["kenh_ten"], ds[1]["kenh_link"]) == ("C luật cũ", 1, "", "")
    assert (ds[2]["kenh_ten"], ds[2]["lan_quet_cuoi"]) == ("Kênh D", "2026-10-05 09:00:00")


def test_video_vi_pham_anh_chup_hong_thi_kenh_trong_van_co_dong(engine):
    job_id = _luu(engine, "vidvipham0E", ten="E", kenh=("Kênh E", "https://www.youtube.com/@e"))
    _sql(engine, "UPDATE bao_cao_job SET du_lieu='{hỏng' WHERE job_id=?", job_id)
    assert engine.video_vi_pham() == [{"ma": "vidvipham0E", "tieu_de": "E", "lan_quet_cuoi": engine.list_jobs()[0][
        "created_at"], "so_lan_quet": 1, "kenh_ten": "", "kenh_link": ""}]
