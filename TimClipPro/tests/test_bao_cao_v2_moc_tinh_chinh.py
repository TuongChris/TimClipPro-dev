# -*- coding: utf-8 -*-
"""D-50 — «Đoạn vi phạm» của báo cáo V2 dùng mốc ĐÃ TINH CHỈNH (P-8, ``ScanResult.tinh_chinh``) khi dòng đó tinh chỉnh
được; dòng «chưa tinh chỉnh», lượt không bật tinh chỉnh hay dữ liệu tinh chỉnh hỏng giữ nguyên mốc của lượt quét.

Ca thật 15/11 (video 3:15:16, hai video gốc 10:59 và 11:16): lượt quét báo 00:00:00 – 00:10:23 và 01:46:12 – 01:57:20 — hụt 36 s và 8 s cuối
video gốc (10:59, 11:16); bước tinh chỉnh đo đúng cả hai trọn video gốc (kiểm độc lập bằng đường bao năng lượng).
"""

import dataclasses
import json
import math

import pytest

import bao_cao_v2 as v2
from bang_ngang import HEADER_NGANG
from engine import Match
from test_bao_cao_v2 import _bc, _goc_ca_that, _kq_ca_that

CLIP = "20250312 - Clip gốc thử [goc00000001].opus"


def _tc(doan, trang_thai="da_tinh_chinh", clip=CLIP, start_s=915.5, cham=False):
    return {
        "clip": clip,
        "start_s": start_s,
        "trang_thai": trang_thai,
        "cham_gioi_han": cham,
        "ly_do": "",
        "doan": [
            {"video_tu": a, "video_den": b, "clip_tu": 0.0, "clip_den": b - a, "k": 1.0}
            for a, b in doan
        ],
    }


def _o(bc, cot="Đoạn vi phạm 1 trong video vi phạm"):
    return dict(zip(HEADER_NGANG, v2.dong_ngang(bc)))[cot]


def test_ca_that_hai_doan_hut_cuoi_video_goc_nay_tron_video_goc():
    m1 = Match(
        clip="a [goc0000000a].opus",
        start_s=0.0,
        end_s=623.3,
        matched_s=584.8,
        clip_offset_s=38.5,
        hashes=24724,
        confidence="Rất chắc chắn",
        vung="Đầu",
        clip_bat_dau_s=0.0,
        vung_khop_s=38.5,
    )
    m2 = Match(
        clip="b [goc0000000b].opus",
        start_s=6372.8,
        end_s=7040.9,
        matched_s=630.9,
        clip_offset_s=37.2,
        hashes=29198,
        confidence="Rất chắc chắn",
        vung="Giữa",
        clip_bat_dau_s=6372.8,
        vung_khop_s=6410.0,
    )
    kq = _kq_ca_that(
        matches=[m1, m2],
        tinh_chinh=[
            _tc([(0.059, 659.889)], clip=m1.clip, start_s=0.0, cham=True),
            _tc([(6372.846, 7048.941)], clip=m2.clip, start_s=6372.8),
        ],
    )
    bc = _bc(
        kq,
        goc_theo_clip={
            m.clip: dataclasses.replace(_goc_ca_that(), clip=m.clip) for m in kq.matches
        },
    )
    assert (
        _o(bc)
        == "00:00:00 – 00:10:59 · https://www.youtube.com/watch?v=vidvipham01&t=0"
    )
    assert (
        _o(bc, "Đoạn vi phạm 2 trong video vi phạm")
        == "01:46:12 – 01:57:28 · https://www.youtube.com/watch?v=vidvipham01&t=6372"
    )
    # bảng 16 cột (bảng kết quả trên giao diện, CSV): «Bắt đầu», «Kết thúc» cùng mốc; số chẩn đoán của engine giữ nguyên
    dong = v2.dong_doc(bc)
    assert [(r[7], r[9]) for r in dong] == [
        ("00:00:00", "00:10:59"),
        ("01:46:12", "01:57:28"),
    ]
    assert [r[8] for r in dong] == [
        "00:00:38",
        "01:46:50",
    ]  # «Vùng khớp» = lõi vân tay (chẩn đoán)
    assert [(d.matched_s, d.clip_offset_s, d.hashes) for d in bc.doan] == [
        (584.8, 38.5, 24724),
        (630.9, 37.2, 29198),
    ]
    # ảnh chụp lưu lịch sử đọc lại đúng mốc đã dùng
    doc = v2.doc_anh_chup_da_luu(v2.CHINH_SACH_V2, json.dumps(bc.to_dict(), ensure_ascii=False))
    assert [(d.giay_bat_dau, d.giay_ket_thuc) for d in doc.doan] == [(0, 659), (6372, 7048)]



def test_nhieu_manh_lay_tu_dau_manh_dau_toi_cuoi_manh_cuoi():
    bc = _bc(
        _kq_ca_that(
            tinh_chinh=[_tc([(1000.2, 1500.0), (912.7, 990.0), (1510.0, 2400.9)])]
        )
    )
    assert _o(bc).startswith("00:15:12 – 00:40:00 · ")
    assert bc.doan[0].start_s == 912.7 and bc.doan[0].end_s == 2400.9


def test_khong_bat_tinh_chinh_bao_cao_y_nguyen():
    goc = _o(_bc())
    assert (
        goc == "00:15:15 – 00:39:10 · https://www.youtube.com/watch?v=vidvipham01&t=915"
    )
    assert _o(_bc(_kq_ca_that(tinh_chinh=[]))) == goc
    assert v2.dong_doc(_bc(_kq_ca_that(tinh_chinh=[]))) == v2.dong_doc(_bc())


@pytest.mark.parametrize(
    "tc",
    [
        _tc([(900.0, 2400.0)], trang_thai="chua_tinh_chinh"),
        _tc(
            [(900.0, 2400.0)], clip="clip khác.opus"
        ),  # lệch dòng: không bao giờ gán mốc của clip khác
        _tc([(900.0, 2400.0)], start_s=100.0),  # cùng clip, LẦN DÙNG khác (dòng khác)
        _tc([]),
        _tc([(math.nan, 2400.0)]),
        _tc([(900.0, math.inf)]),
        _tc([(-1.0, 2400.0)]),
        _tc([(2400.0, 2400.0)]),
        {
            "clip": CLIP,
            "start_s": 915.5,
            "trang_thai": "da_tinh_chinh",
            "doan": [{"video_tu": 900.0}],
        },
        {
            "clip": CLIP,
            "start_s": 915.5,
            "trang_thai": "da_tinh_chinh",
            "doan": [{"video_tu": "9", "video_den": True}],
        },
        {"clip": CLIP, "start_s": 915.5, "trang_thai": "da_tinh_chinh", "doan": "hỏng"},
        None,
        "hỏng",
    ],
    ids=[
        "chua",
        "clip_khac",
        "lan_dung_khac",
        "rong",
        "nan",
        "vo_cuc",
        "am",
        "dau_bang_cuoi",
        "thieu_khoa",
        "sai_kieu",
        "doan_khong_phai_danh_sach",
        "none",
        "chuoi",
    ],
)
def test_dong_khong_tinh_chinh_duoc_giu_moc_luot_quet(tc):
    assert (
        _o(_bc(_kq_ca_that(tinh_chinh=[tc])))
        == "00:15:15 – 00:39:10 · https://www.youtube.com/watch?v=vidvipham01&t=915"
    )


def test_danh_sach_tinh_chinh_ngan_hon_so_dong_thi_dong_thieu_giu_moc():
    m2 = dataclasses.replace(
        _kq_ca_that().matches[0],
        clip="x [goc00000002].opus",
        start_s=5000.0,
        end_s=5600.0,
    )
    kq = _kq_ca_that(tinh_chinh=[_tc([(912.0, 2400.0)])])
    kq.matches.append(m2)
    bc = _bc(
        kq,
        goc_theo_clip={
            m.clip: dataclasses.replace(_goc_ca_that(), clip=m.clip) for m in kq.matches
        },
    )
    assert [(d.giay_bat_dau, d.giay_ket_thuc) for d in bc.doan] == [
        (912, 2400),
        (5000, 5600),
    ]


@pytest.mark.parametrize("doan,cham,mong", [
    ([(930.0, 2300.0)], True, (915, 2350)),      # mép đo chạm giới hạn, hẹp hơn lượt quét → không bao giờ làm hẹp đi
    ([(930.0, 2390.0)], True, (915, 2390)),      # từng mép: phía nào đo rộng hơn thì lấy phía đó
    ([(900.0, 2390.0)], True, (900, 2390)),
    ([(930.0, 2300.0)], False, (930, 2300)),     # không chạm giới hạn: mép đo được là mép thật (lượt quét lố)
    ([(930.0, 2300.0)], None, (915, 2350)),      # thiếu cờ (dữ liệu lạ): coi như chạm giới hạn
])
def test_mep_cham_gioi_han_do_khong_lam_hep_doan(doan, cham, mong):
    tc = _tc(doan, cham=cham)
    if cham is None:
        del tc["cham_gioi_han"]
    bc = _bc(_kq_ca_that(tinh_chinh=[tc]))
    assert (bc.doan[0].giay_bat_dau, bc.doan[0].giay_ket_thuc) == mong


def test_doan_tinh_chinh_suy_bien_khong_duoc_cuu_bang_moc_luot_quet():
    for doan in ([(2400.0, 2400.0)], [(2400.0, 2000.0)]):
        bc = _bc(_kq_ca_that(tinh_chinh=[_tc(doan, cham=True)]))
        assert (bc.doan[0].start_s, bc.doan[0].end_s) == (915.5, 2350.0)


@pytest.mark.parametrize("dau,cuoi,mong", [
    (False, True, (3600, 3829)),     # mép đầu ĐO ĐƯỢC giữ nguyên dù mép cuối chạm giới hạn (review D-50)
    (True, False, (3570, 3829)),
    (True, True, (3570, 3829)),
    (False, False, (3600, 3829)),
])
def test_moi_mep_chi_noi_khi_chinh_mep_do_cham_gioi_han(dau, cuoi, mong):
    """Lượt quét: mốc đầu = vị trí ngoại suy của giây 0 clip (3570, video cắt 30 s đầu clip), mốc cuối 3800 (phân vị
    95 %). Tinh chỉnh: 3600,2 → 3829,9 (mép cuối chạm cuối phần đã quét)."""
    kq = _kq_ca_that(duration_s=10800.0)
    kq.matches[0].start_s, kq.matches[0].end_s = 3570.0, 3800.0
    tc = _tc([(3600.2, 3829.9)], start_s=3570.0, cham=dau or cuoi)
    tc.update(cham_dau=dau, cham_cuoi=cuoi)
    bc = _bc(_kq_ca_that(duration_s=10800.0, matches=kq.matches, tinh_chinh=[tc]))
    assert (bc.doan[0].giay_bat_dau, bc.doan[0].giay_ket_thuc) == mong


def test_nhan_vung_theo_moc_hien_thi():
    kq = _kq_ca_that(duration_s=10800.0)
    kq.matches[0].start_s, kq.matches[0].end_s, kq.matches[0].vung = 3570.0, 3800.0, "Đầu"
    kq.tinh_chinh = [_tc([(3600.2, 3829.9)], start_s=3570.0)]
    (d,) = _bc(kq).doan
    assert (d.vung, d.giay_bat_dau) == ("Giữa", 3600)
    kq.tinh_chinh = [_tc([(3600.2, 3829.9)], start_s=3570.0, trang_thai="chua_tinh_chinh")]
    assert _bc(kq).doan[0].vung == "Đầu"            # không tinh chỉnh: nhãn của engine y nguyên


def test_doan_xep_theo_moc_hien_thi():
    """Engine xếp theo mốc của nó (A: giây 0 clip ngoại suy 700, dùng thật từ 1000; B: 800). «Đoạn vi phạm 1, 2» theo
    mốc hiển thị: B trước A."""
    a = dataclasses.replace(_kq_ca_that().matches[0], clip="a [goc0000000a].opus", start_s=700.0, end_s=1300.0)
    b = dataclasses.replace(a, clip="b [goc0000000b].opus", start_s=800.0, end_s=1200.0)
    kq = _kq_ca_that(matches=[a, b], tinh_chinh=[
        _tc([(1000.0, 1300.0)], clip=a.clip, start_s=700.0),
        _tc([(800.0, 1200.0)], clip=b.clip, start_s=800.0, trang_thai="chua_tinh_chinh")])
    bc = _bc(kq, goc_theo_clip={m.clip: dataclasses.replace(_goc_ca_that(), clip=m.clip) for m in kq.matches})
    assert [(d.goc.clip, d.giay_bat_dau) for d in bc.doan] == [(b.clip, 800), (a.clip, 1000)]
    assert _o(bc).startswith("00:13:20 – 00:20:00") and _o(bc, "Đoạn vi phạm 2 trong video vi phạm").startswith("00:16:40")
