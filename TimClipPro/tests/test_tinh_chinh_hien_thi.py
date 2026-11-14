# -*- coding: utf-8 -*-
"""P-8 việc 1 — phần HIỂN THỊ của «tinh chỉnh mốc từng giây»: mốc tới phần mười giây, CSV phụ cạnh báo cáo, mục kết
quả và ô bật ở thanh bên. Dữ liệu tinh chỉnh dựng tay (đúng dạng tinh_chinh_moc trả) — không chạy thuật toán."""

from __future__ import annotations

import csv
import os

import pytest

from engine import Engine, ScanResult, hhmmss_tp

DA, CHUA = "da_tinh_chinh", "chua_tinh_chinh"


def _tc_da():
    return {"clip": "Clip_A.opus", "start_s": 280.0, "trang_thai": DA, "ly_do": "",
            "doan": [{"video_tu": 480.087, "video_den": 700.0, "clip_tu": 260.087, "clip_den": 480.0, "k": 1.0,
                      "tuong_dong_tb": 99.4, "tuong_dong_min": 61.2, "cach_tim_mep": ["bac_thang", "cuoi_clip"]},
                     {"video_tu": 250.105, "video_den": 450.006, "clip_tu": 0.104, "clip_den": 200.005, "k": 1.0,
                      "tuong_dong_tb": 99.6, "tuong_dong_min": 70.0, "cach_tim_mep": ["bac_thang", "bac_thang"]}],
            "cho_cat": [{"video_tu": 450.006, "video_den": 480.087, "clip_bo_tu": 200.005, "clip_bo_den": 260.087}],
            "ho_so": [[250.6, 98.5], [251.6, 99.1], [700.0, 97.0]], "nguong_pct": 45.0, "nen_p99_pct": 21.0,
            "cham_gioi_han": False, "thoi_gian_s": 4.1}


def _tc_chua():
    return {"clip": "Clip_B.opus", "start_s": 900.0, "trang_thai": CHUA,
            "ly_do": "Âm thanh lặp y hệt — có nhiều mốc đúng như nhau."}


def _kq(ten="Video vi phạm"):
    return ScanResult(source_name=ten, duration_s=3600.0, tinh_chinh=[_tc_da(), _tc_chua()])


@pytest.mark.parametrize("giay,chu", [(0, "00:00:00.0"), (59.96, "00:01:00.0"), (3661.26, "01:01:01.3"),
                                      (-4.0, "00:00:00.0"), (450.006, "00:07:30.0")])
def test_moc_toi_phan_muoi_giay(giay, chu):
    assert hhmmss_tp(giay) == chu


def test_dong_csv_xep_theo_giay_video_va_noi_ro_dong_chua_tinh_chinh():
    doan, giay = Engine.dong_tinh_chinh([_kq()])
    assert [d[5] for d in doan] == ["Đoạn dùng thật", "Chỗ cắt / chèn", "Đoạn dùng thật", ""]
    assert doan[0][6:10] == ["00:04:10.1", "00:07:30.0", "00:00:00.1", "00:03:20.0"]
    assert doan[1][6:10] == ["00:07:30.0", "00:08:00.1", "00:03:20.0", "00:04:20.1"]
    assert doan[3][3:5] == ["Chưa tinh chỉnh", "Âm thanh lặp y hệt — có nhiều mốc đúng như nhau."]
    assert all(len(d) == len(Engine.HEADER_TINH_CHINH) for d in doan)
    assert giay[0] == ["Video vi phạm", "Clip_A.opus", "00:04:40", 250.6, "00:04:10.6", 98.5]
    assert all(len(g) == len(Engine.HEADER_TUNG_GIAY) for g in giay)


def test_csv_phu_ghi_canh_bao_cao_va_an_toan_bang_tinh(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    bao_cao = tmp_path / "ketqua_1.csv"
    ra = e._ghi_tinh_chinh_canh(str(bao_cao), [_kq(ten="=HYPERLINK(1)")])
    assert [os.path.basename(p) for p in ra] == ["ketqua_1.tinh_chinh.csv", "ketqua_1.tung_giay.csv"]
    with open(ra[0], encoding="utf-8-sig", newline="") as f:
        dong = list(csv.reader(f))
    assert dong[0] == Engine.HEADER_TINH_CHINH and len(dong) == 5
    assert not dong[1][0].startswith("="), "ô bắt đầu bằng «=» phải được vô hiệu hoá (CSV injection)"


def test_khong_bat_tinh_chinh_thi_khong_ghi_csv_phu(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    assert e._ghi_tinh_chinh_canh(str(tmp_path / "ketqua_2.csv"), [ScanResult(source_name="v")]) == []
    assert not any(x.endswith((".tinh_chinh.csv", ".tung_giay.csv")) for x in os.listdir(tmp_path))


def test_man_ket_qua_hien_doan_cho_cat_va_ly_do(tmp_path, monkeypatch):
    from test_app_cau_tom_tat_ket_qua import _man_ket_qua, _ok

    kq = _ok("Video vi phạm thử", "aaaaaaaaaaa")
    kq.tinh_chinh = [dict(_tc_da(), clip=kq.matches[0].clip), dict(_tc_chua(), clip=kq.matches[0].clip)]
    at = _man_ket_qua(tmp_path, monkeypatch, [kq])
    assert any(x.label == "🎯 Mốc tinh chỉnh từng giây (thử nghiệm)" for x in at.expander)
    chu = "\n".join(m.value for m in at.markdown)
    assert "Đoạn dùng thật 00:04:10.1 → 00:07:30.0" in chu
    assert "Chỗ cắt / chèn 00:07:30.0 → 00:08:00.1" in chu
    assert "chưa tinh chỉnh — Âm thanh lặp y hệt" in chu


def test_man_ket_qua_khong_co_tinh_chinh_thi_khong_hien_muc(tmp_path, monkeypatch):
    from test_app_cau_tom_tat_ket_qua import _man_ket_qua, _ok

    at = _man_ket_qua(tmp_path, monkeypatch, [_ok("Video vi phạm thử", "aaaaaaaaaaa")])
    assert not any("Mốc tinh chỉnh" in x.label for x in at.expander)


def test_o_bat_tinh_chinh_o_thanh_ben_mac_dinh_tat(tmp_path, monkeypatch):
    from test_app_cau_tom_tat_ket_qua import _man_ket_qua

    at = _man_ket_qua(tmp_path, monkeypatch, [])
    o = [c for c in at.sidebar.checkbox if c.label == "🎯 Tinh chỉnh mốc từng giây (thử nghiệm)"]
    assert len(o) == 1 and o[0].value is False
