# -*- coding: utf-8 -*-
"""«Bóng» của âm thanh lặp trong ``Engine._merge`` (P0, 10/10/2026) — test nhanh mức mảnh, không audio.

Nhạc có nhịp trống đều / vòng hợp âm / vòng lặp làm audfprint trả thêm các căn chỉnh «bóng» của CÙNG clip: lệch
bội số nửa ô nhịp so với căn chỉnh thật, phủ CÙNG vùng video, yếu hơn hẳn (8–30% số hash). Trên mã trước khi sửa
chúng (1) kéo lệch mốc đầu clip tới ±dedup_s (``_merge`` neo vào mảnh có vùng SỚM NHẤT của nhóm), (2) tự gộp thành
ứng viên riêng ≥ 1.000 hash → «đạt chuẩn», thành dòng báo cáo thừa và làm phồng «Tổng số đoạn phát hiện».

Ba nhóm test:
* Tái hiện lỗi: ĐỎ trên mã trước khi sửa (commit đưa test vào đánh dấu chúng ``xfail(strict=True)``),
  XANH sau khi sửa.
* Khoá hành vi cũ hợp lệ: xanh trước VÀ sau khi sửa — chặn sửa quá tay (clip cắt giữa, dùng hai lần, phát lại liền
  nhau, khúc gối, trôi tốc độ, nhạc hiệu chung, hai nguồn chồng tiếng, sát ngưỡng 1.000 hash, khác hệ số tốc độ,
  các chốt của gộp cùng vị trí: không tạo dương tính mới, không làm loãng, không dẫm lên đường bù tốc độ).
* Bằng chứng mốc (cờ mơ hồ, mốc thay thế, tỷ số đối thủ) tách khỏi độ chắc chắn của NGUỒN (``confidence``).

Dữ liệu ``golden/bong_lap/*.json``: mảnh thô audfprint thật của video tổng hợp (README cùng thư mục: seed, ground
truth, cách sinh lại). Mảnh dựng tay: lấy theo số đo thật của bộ điều tra P0 (làm tròn).
"""
from __future__ import annotations

import json
import os

import pytest

from chan_doan_quet import ChanDoanQuet
from chap_nhan_khop import loc_chap_nhan
from engine import Config, Engine, Match, danh_gia

DU_LIEU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden", "bong_lap")
CLIP = "nhac_lap [AAAAAAAAAAA].opus"
VLOG = "vlog [BBBBBBBBBBB].opus"


def _engine(tong_hash: dict) -> Engine:
    """Engine tối thiểu, không __init__, không chạm đĩa; Config MẶC ĐỊNH (ngưỡng thật của sản phẩm)."""
    eng = Engine.__new__(Engine)
    eng.config = Config()
    eng.canh_bao_gop = []
    eng.chan_doan_quet = ChanDoanQuet()
    ds = [{"ten": t, "so_hash": n} for t, n in tong_hash.items()]
    eng.db_clips = lambda bo_cache=False: ds
    return eng


def _manh(align: float, bat_dau: float, ket_thuc: float, so_hash: int, clip: str = CLIP,
          he_so: float = 1.0) -> dict:
    """Mảnh thô như parser của engine trả: vùng video [bat_dau, ket_thuc), t_clip = bat_dau − align (k = 1)."""
    return {"clip": clip, "bat_dau": bat_dau, "khop": ket_thuc - bat_dau, "t_clip": (bat_dau - align) / he_so,
            "hash": so_hash, "he_so": he_so, "align": align}


def _chuoi(eng: Engine, tho: list, duration: float, pham_vi: float = 0.0) -> tuple:
    """Đúng thứ tự ``Engine.scan_media`` sau khi khớp: gộp → chỉ số → chấp nhận → chọn Top-N."""
    ds = eng._merge(tho)
    eng._gan_chi_so(ds, duration)
    dat, _, _ = loc_chap_nhan(ds, eng.config)
    chon, _ = eng._chon_loc(ds, pham_vi or duration)
    return ds, dat, chon


def _nap(ten: str) -> dict:
    with open(os.path.join(DU_LIEU, ten), encoding="utf-8") as f:
        return json.load(f)


def _quet_golden(ten: str) -> tuple:
    d = _nap(ten)
    eng = _engine(d["tong_hash_kho"])
    return (d, *_chuoi(eng, d["tho"], d["duration_s"], d["pham_vi_quet_s"]))


# Mảnh theo số đo thật của E2E V1 (làm tròn): căn chỉnh thật 360,0 + bóng ở bội số nửa ô nhịp (1,06 s).
THAT = _manh(360.0, 434.9, 705.7, 12668)
BONG_GAN = [
    _manh(349.4, 428.5, 690.0, 745),      # bóng có vùng SỚM NHẤT — mã cũ neo mốc vào đây (−10,6 s)
    _manh(358.9, 431.2, 706.4, 1647),
    _manh(361.1, 435.5, 706.4, 1614),
    _manh(362.1, 435.5, 707.5, 1274),
    _manh(357.8, 434.4, 708.5, 1244),
    _manh(364.2, 436.5, 705.3, 1034),
]
BONG_XA = [                                # bóng lệch ~−60 s (cùng mẫu hợp âm/trống ở đoạn khác của bản nhạc)
    _manh(299.5, 457.8, 700.6, 1022),
    _manh(300.4, 458.8, 701.0, 1078),
    _manh(301.6, 461.0, 702.2, 1012),
]


# ------------------------------------------------------------------ tái hiện lỗi (đỏ trên mã trước khi sửa)
def test_bong_khong_keo_lech_moc_dau_clip():
    ds = _engine({CLIP: 36981})._merge([THAT] + BONG_GAN)
    assert len(ds) == 1
    assert ds[0].start_s == pytest.approx(360.0, abs=0.5)          # trước khi sửa: 349,4 (−10,6 s)
    assert ds[0].hashes >= THAT["hash"]


def test_nhom_bong_khong_thanh_ung_vien_dat_chuan():
    ds, dat, chon = _chuoi(_engine({CLIP: 36981}), [THAT] + BONG_GAN + BONG_XA, duration=2100.0)
    assert len(dat) == 1                                            # trước khi sửa: 2 (nhóm bóng 1.078 hash qua bậc A)
    assert len(chon) == 1 and chon[0].start_s == pytest.approx(360.0, abs=0.5)


def test_golden_trich_giua_mot_dong_dung_moc_va_dem_nhat_quan():
    """Nhạc có trống lặp, trích giữa — MỘT lần dùng. «Tổng số đoạn phát hiện» (= số ứng viên đạt chuẩn trước
    Top-N, hợp đồng giữ nguyên) phải bằng số lần dùng thật khi không còn ứng viên bóng."""
    d, _, dat, chon = _quet_golden("trich_giua.json")
    assert len(chon) == 1, [(round(m.start_s, 1), m.hashes) for m in chon]    # trước khi sửa: 5 dòng
    assert len(dat) == 1                                                        # trước khi sửa: 11
    assert chon[0].start_s == pytest.approx(d["moc_that_s"], abs=1.0)          # trước khi sửa: +7,4 s
    assert not chon[0].moc_mo_ho and chon[0].confidence == "Rất chắc chắn"


def test_golden_cat_giua_moi_moc_la_moc_that_cua_mot_phan():
    """Bản reup cắt bỏ 12 s giữa clip. Hai phần có vị trí đặt khác nhau (120 và 108) và khe giữa hai vùng khớp có
    thể > dedup_s, nên một hay hai dòng đều đúng — nhưng MỖI mốc phải là mốc thật của đúng một phần."""
    d, _, dat, chon = _quet_golden("cat_giua.json")
    assert 1 <= len(chon) <= 2 and len(dat) == len(chon), [(round(m.start_s, 1), m.hashes) for m in chon]
    phan = sorted(min(range(2), key=lambda i: abs(m.start_s - d["moc_phan_s"][i])) for m in chon)
    assert phan == sorted(set(phan))                                            # không hai dòng cho cùng một phần
    for m in chon:                                                              # trước khi sửa: 99,5 (bóng −8,5 s)
        assert min(abs(m.start_s - t) for t in d["moc_phan_s"]) <= 1.0, m.start_s


def test_golden_troi_nho_mot_dong_dung_moc():
    d, _, dat, chon = _quet_golden("troi_nho.json")
    assert len(chon) == 1 and len(dat) == 1, [(round(m.start_s, 1), m.hashes) for m in chon]   # trước: 5 / 12
    assert chon[0].start_s == pytest.approx(d["moc_that_s"], abs=1.0)                           # trước: −2,1 s


# Theo số đo thật của B13 (nhạc lặp dài chậm 0,12%, làm tròn): căn chỉnh thật trôi 120,0 → 120,5 vỡ thành 6 mảnh có
# «lỗ» > dedup_s giữa chúng; bóng 129,2 nằm một nửa trong lỗ [326,6; 371,6] nên không mảnh thật NÀO phủ ≥ 50% nó.
B13_THAT = [
    _manh(120.0, 122.2, 188.8, 1920), _manh(120.2, 235.6, 326.6, 4437), _manh(120.4, 371.6, 462.4, 4045),
    _manh(120.4, 427.8, 519.5, 4387), _manh(120.5, 463.9, 559.5, 4401), _manh(120.5, 523.4, 595.5, 3275),
]
B13_BONG = [
    _manh(110.0, 230.9, 326.5, 523), _manh(108.9, 271.4, 332.2, 521), _manh(119.2, 404.2, 455.9, 440),
    _manh(125.8, 289.4, 367.0, 652), _manh(129.2, 286.1, 369.3, 843), _manh(129.2, 281.6, 344.6, 861),
    _manh(131.4, 287.2, 372.6, 544),
]


def test_bong_trong_lo_cua_can_chinh_troi_khong_thanh_dong_va_mot_lan_dung_mot_dong():
    """Trước khi sửa: 3 dòng — 110,0 (neo vào bóng), 120,0 và 129,2 (nhóm do bóng mở đầu). Đúng: MỘT dòng ở 120,0.
    Cần cả hai: bóng được xét theo PHẠM VI của vị trí đặt (không theo từng mảnh — lỗ không có mảnh thật nào), và
    gộp các nhóm cùng vị trí đặt (trôi < ngưỡng bù tốc độ) thành một lần dùng."""
    ds, dat, chon = _chuoi(_engine({CLIP: 36981}), B13_THAT + B13_BONG, duration=720.0)
    assert len(dat) == 1, [(round(m.start_s, 1), m.hashes) for m in dat]
    assert len(chon) == 1 and chon[0].start_s == pytest.approx(120.0, abs=0.3)
    assert not chon[0].moc_mo_ho


def test_vi_tri_that_vo_nhieu_manh_van_thang_mot_bong_manh_hon_tung_manh():
    """Vị trí đặt được so bằng TỔNG bằng chứng, không bằng mảnh mạnh nhất: căn chỉnh thật vỡ 4 mảnh × 2.000 hash vẫn
    là mốc, dù một căn chỉnh khác có MỘT mảnh 2.600 hash. Căn chỉnh đó lớn hơn từng mảnh thật nên dòng được đánh dấu
    mơ hồ (thận trọng) — nhưng nó không bao giờ làm mốc."""
    that = [_manh(50.0, 100.0 + 60.0 * i, 160.0 + 60.0 * i, 2000) for i in range(4)]
    khac = _manh(60.0, 130.0, 310.0, 2600)
    ds = _engine({CLIP: 36981})._merge(that + [khac])
    assert len(ds) == 1 and ds[0].start_s == pytest.approx(50.0, abs=0.01)
    assert ds[0].moc_mo_ho and ds[0].moc_thay_the == (60.0,)


def test_vong_lap_y_het_mot_dong_danh_dau_mo_ho_va_giu_moc_thay_the():
    """Đoạn nằm TRỌN trong vùng lặp y hệt (chu kỳ 17 s): mọi mốc 140 ± 17k giải thích video NHƯ NHAU — không thể
    xác định mốc duy nhất. Đúng: MỘT dòng; mốc thuộc tập tương đương; cờ mơ hồ + các mốc thay thế + tỷ số đối thủ;
    độ chắc chắn của NGUỒN không đổi (nguồn thì chắc chắn, chỉ mốc là không)."""
    tuong_duong = [140.0 + 17.0 * k for k in range(-3, 4)]
    tho = [_manh(a, 242.0, 298.0, 1450 + (7 * i) % 23) for i, a in enumerate(tuong_duong)]
    _, dat, chon = _chuoi(_engine({CLIP: 28800}), tho, duration=420.0)
    assert len(chon) == 1 and len(dat) == 1                         # trước khi sửa: 4 dòng «Rất chắc chắn»
    m = chon[0]
    assert m.moc_mo_ho
    assert min(abs(m.start_s - t) for t in tuong_duong) <= 0.5
    assert sorted(set(m.moc_thay_the) | {round(m.start_s, 1)}) == pytest.approx(tuong_duong, abs=0.15)
    assert m.ty_so_doi_thu >= 0.9
    assert m.confidence == danh_gia(m.hashes) == "Rất chắc chắn"


# ------------------------------------------------------------------ KHOÁ HÀNH VI CŨ (xanh trước và sau khi sửa)
def test_clip_cat_giua_khong_bong_van_gop_va_neo_phan_dau():
    """Phần A (align 120) rồi phần B (align 108, mạnh hơn) NỐI TIẾP, khe ≤ dedup_s: gộp một dòng, mốc = đầu
    phần A. Chặn phương án «neo vào mảnh mạnh nhất» (sẽ ra 108)."""
    a = _manh(120.0, 128.9, 215.0, 4057, clip=VLOG)
    b = _manh(108.0, 225.0, 396.5, 6090, clip=VLOG)                 # khe 10 s ≤ dedup_s
    ds = _engine({VLOG: 18447})._merge([a, b])
    assert len(ds) == 1
    assert ds[0].start_s == pytest.approx(120.0, abs=0.01)
    assert ds[0].hashes == a["hash"] + b["hash"]


def test_cung_clip_hai_lan_dung_van_hai_dong():
    tho = [_manh(60.0, 74.4, 346.6, 11533, VLOG), _manh(430.0, 486.2, 673.0, 7080, VLOG)]
    _, dat, chon = _chuoi(_engine({VLOG: 18447}), tho, duration=740.0)
    assert [round(m.start_s, 1) for m in chon] == [60.0, 430.0]


def test_cung_clip_dung_lai_lien_nhau_co_chong_cheo_ngan_van_hai_dong():
    """Phát lại clip từ đầu ngay sau lần một, chuyển cảnh chồng 5 s: hai lần dùng THẬT dù vùng chạm nhau."""
    tho = [_manh(100.0, 110.0, 400.0, 9000, VLOG), _manh(395.0, 395.0, 690.0, 8800, VLOG)]
    _, dat, chon = _chuoi(_engine({VLOG: 18447}), tho, duration=800.0)
    assert [round(m.start_s, 1) for m in chon] == [100.0, 395.0] and len(dat) == 2


def test_khuc_goi_cung_align_khong_bi_coi_la_bong():
    """Cùng lần xuất hiện bị cắt qua hai khúc gối nhau: align gần như trùng (±0,1 s), vùng chồng, một mảnh
    yếu hơn hẳn — PHẢI gộp như cũ (tích phân mật độ), không được loại."""
    yeu = _manh(500.0, 3560.0, 3600.0, 1500)
    manh = _manh(500.05, 3540.0, 3700.0, 7500)
    ds = _engine({CLIP: 36981})._merge([yeu, manh])
    assert len(ds) == 1 and ds[0].start_s == pytest.approx(500.0, abs=0.06)
    assert ds[0].hashes == 7500


def test_troi_toc_do_noi_tiep_khong_bi_coi_la_bong():
    """Video đổi tốc độ nhẹ chưa bù: align trôi đều 0,6 s/mảnh, vùng NỐI TIẾP (chồng 2 s) — giữ nguyên."""
    tho = [_manh(100.0 + 0.6 * i, 130.0 + 27.0 * i, 159.0 + 27.0 * i, 1200 + 10 * i) for i in range(10)]
    ds = _engine({CLIP: 36981})._merge(tho)
    assert len(ds) == 1
    assert ds[0].start_s == pytest.approx(100.0, abs=0.01)
    assert ds[0].hashes >= 10 * 1200 * 27 // 29


def test_hai_nguon_co_nhac_hieu_chung_khong_an_nhau():
    """Hai clip gốc KHÁC NHAU cùng có nhạc hiệu: mảnh nhạc hiệu của clip này phủ vùng của clip kia. Bóng chỉ xét
    trong CÙNG clip — nguồn khác không bao giờ bị coi là bóng của nhau."""
    x, y = "kenh_x [XXXXXXXXXXX].opus", "kenh_y [YYYYYYYYYYY].opus"
    tho = [_manh(100.0, 110.0, 400.0, 9000, x), _manh(560.0, 560.0, 860.0, 8000, y),
           _manh(205.0, 390.0, 398.8, 133, y),            # nhạc hiệu của y nghe thấy ở cuối đoạn x
           _manh(455.0, 851.0, 859.8, 140, x)]            # nhạc hiệu của x nghe thấy ở cuối đoạn y
    _, dat, chon = _chuoi(_engine({x: 20000, y: 20000}), tho, duration=900.0)
    assert sorted((m.clip, round(m.start_s, 1)) for m in dat) == [(x, 100.0), (y, 560.0)]


def test_hai_nguon_phat_chong_cung_luc_van_hai_dong():
    """Âm thanh chồng (mashup, chuyển cảnh trộn tiếng): đoạn của clip Y nằm TRỌN trong vùng của clip X và yếu hơn
    hẳn — vẫn là nguồn thật thứ hai. «Một giây video chỉ là một vị trí» chỉ đúng trong CÙNG một clip."""
    x, y = "kenh_x [XXXXXXXXXXX].opus", "kenh_y [YYYYYYYYYYY].opus"
    tho = [_manh(100.0, 110.0, 400.0, 9000, x), _manh(560.0, 300.0, 400.0, 1500, y)]
    _, dat, chon = _chuoi(_engine({x: 20000, y: 20000}), tho, duration=900.0)
    assert sorted((m.clip, round(m.start_s, 1)) for m in dat) == [(x, 100.0), (y, 560.0)]


def test_sat_nguong_1000_hash_bong_van_gop_bang_chung_nhu_cu():
    """Nhóm thật ngay trên ngưỡng 1.000: một bóng yếu kéo dài vùng khớp thêm 5 s. Gom nhóm và tích phân hash phải
    Y HỆT trước khi sửa (bóng không được làm mốc, nhưng bằng chứng nguồn không được mất) — xoá bóng trước khi gộp
    sẽ đẩy nhóm xuống 990 hash và đánh rơi một ứng viên đạt chuẩn."""
    that = _manh(40.0, 100.0, 160.0, 990)
    bong = _manh(41.06, 105.0, 165.0, 120)          # phủ [160; 165) mà mảnh thật không phủ: +5 s × 2 hash/s
    _, dat, chon = _chuoi(_engine({CLIP: 5000}), [that, bong], duration=400.0)
    assert len(dat) == 1 and chon[0].hashes == 1000
    assert chon[0].start_s == pytest.approx(40.0, abs=0.01)


def test_khac_he_so_toc_do_khong_xet_bong_cua_nhau():
    """Mảnh của lượt bù tốc độ (k = 1,03) và lượt thường (k = 1) không cùng trục — như ``_merge`` cũ không gộp
    chúng, cũng không bao giờ coi mảnh này là bóng của mảnh kia."""
    thuong = _manh(100.0, 130.0, 400.0, 9000)
    bu = _manh(100.0, 140.0, 300.0, 1500, he_so=1.03)
    ds = _engine({CLIP: 36981})._merge([thuong, bu])
    assert len(ds) == 2


# ------------------------------------------------------------------ gộp cùng vị trí đặt (C') và chốt an toàn
def test_cung_vi_tri_khe_lon_hon_dedup_va_mot_phan_dat_chuan_gop_mot_dong():
    """Cùng vị trí đặt (align trùng), vùng khớp cách nhau 40 s > dedup_s (tiếng nói đè lên giữa clip): MỘT lần dùng.
    Một phần đã đạt bậc A và nhóm gộp vẫn đạt bậc A ⇒ gộp, không đổi kết luận."""
    tho = [_manh(50.0, 60.0, 200.0, 4200), _manh(50.0, 240.0, 380.0, 3900)]
    _, dat, chon = _chuoi(_engine({CLIP: 36981}), tho, duration=600.0)
    assert len(dat) == 1 and len(chon) == 1
    assert chon[0].start_s == pytest.approx(50.0, abs=0.01) and chon[0].hashes == 8100


def test_cung_vi_tri_lech_align_vai_khung_qua_khe_ngan_van_gop():
    """Hai mảnh của cùng một lần dùng hiếm khi có align TRÙNG từng mili-giây: lượng tử hoá khung 23 ms của audfprint
    và ranh giới khúc làm lệch vài khung. Lệch 0,08 s qua khoảng cách tâm 41 s (trôi 0,2% — vượt ngưỡng bù nếu coi
    là trôi) vẫn là cùng vị trí nhờ phần lệch gốc 0,1 s."""
    tho = [_manh(50.0, 60.0, 80.0, 1500), _manh(50.08, 101.0, 121.0, 1500)]
    ds = _engine({CLIP: 36981})._merge(tho)
    assert len(ds) == 1 and ds[0].start_s == pytest.approx(50.0, abs=0.01) and ds[0].hashes == 3000


def test_cung_vi_tri_khong_tao_duong_tinh_moi_tu_hai_phan_deu_duoi_nguong():
    """Hai phần cùng vị trí đặt, mỗi phần dưới ngưỡng 1.000: gộp sẽ thành 1.200 hash «đạt chuẩn» — một dương tính
    MỚI mà mã cũ không có. Đổi kết luận nhận diện là thay đổi chính sách (chữ ký chính sách, Watch), nằm ngoài P0:
    giữ hai nhóm riêng, cùng bị loại như trước."""
    tho = [_manh(50.0, 60.0, 100.0, 600), _manh(50.0, 140.0, 180.0, 600)]
    ds, dat, _ = _chuoi(_engine({CLIP: 36981}), tho, duration=600.0)
    assert len(ds) == 2 and dat == []


def test_cung_vi_tri_khong_gop_neu_lam_loang_mat_dong_dat_chuan():
    """Phần dày (1.100 hash / 300 s) + phần thưa cùng vị trí đặt (300 hash / 300 s) cách 40 s: gộp thì mật độ
    1.400 / 600 s < 3 hash/s ⇒ rớt bậc A — mất một dòng đạt chuẩn. Giữ riêng như cũ."""
    tho = [_manh(50.0, 60.0, 360.0, 1100), _manh(50.0, 400.0, 700.0, 300)]
    _, dat, chon = _chuoi(_engine({CLIP: 36981}), tho, duration=900.0)
    assert len(dat) == 1 and chon[0].hashes == 1100


def test_cung_vi_tri_khong_dam_len_duong_bu_toc_do():
    """Trôi 2% (align lệch 0,8 s qua 40 s tâm) là việc của lượt BÙ tốc độ, không phải «cùng vị trí đặt»: dưới trần
    1 s nhưng vượt ngưỡng trôi 0,15% ⇒ không gộp (giữ golden bù tốc độ). Khe 21 s > dedup_s nên mã cũ cũng tách."""
    tho = [_manh(50.0, 60.0, 80.0, 1500), _manh(50.8, 101.0, 121.0, 1500)]
    ds = _engine({CLIP: 36981})._merge(tho)
    assert len(ds) == 2


# ------------------------------------------------------------------ bằng chứng mốc (B)
def test_bong_yeu_khong_gan_co_mo_ho_nhung_ghi_ty_so_doi_thu():
    ds = _engine({CLIP: 36981})._merge([THAT] + BONG_GAN)
    assert not ds[0].moc_mo_ho and ds[0].moc_thay_the == ()
    assert ds[0].ty_so_doi_thu == pytest.approx(1647 / 12668, abs=0.01)


def test_mo_ho_xet_theo_vi_tri_lam_moc_cua_dong():
    """Một dòng gồm hai phần (bản cắt giữa): mốc lấy từ phần ĐẦU. Đối thủ ngang ngửa của phần đầu làm mốc mơ hồ;
    đối thủ của phần sau thì không (mốc không lấy từ đó)."""
    a = _manh(120.0, 128.9, 215.0, 4057, clip=VLOG)
    b = _manh(108.0, 225.0, 396.5, 6090, clip=VLOG)
    doi_a = _manh(137.0, 130.0, 214.0, 3900, clip=VLOG)             # lặp y hệt trong vùng phần đầu
    doi_b = _manh(125.0, 226.0, 395.0, 5900, clip=VLOG)             # lặp y hệt trong vùng phần sau
    ds = _engine({VLOG: 30000})._merge([a, b, doi_a])
    assert len(ds) == 1 and ds[0].start_s == pytest.approx(120.0, abs=0.01)
    assert ds[0].moc_mo_ho and ds[0].moc_thay_the == (137.0,)
    ds = _engine({VLOG: 30000})._merge([a, b, doi_b])
    assert len(ds) == 1 and ds[0].start_s == pytest.approx(120.0, abs=0.01)
    assert not ds[0].moc_mo_ho


def test_doi_thu_o_vung_cua_dong_khac_khong_lam_dong_nay_mo_ho():
    """Cùng một vị trí đặt tách hai dòng (phần sau quá thưa nên không gộp — chốt C'). Đối thủ ngang ngửa chỉ nằm
    trong vùng phần SAU: chỉ dòng đó mơ hồ, dòng phần đầu thì không."""
    dau = _manh(50.0, 60.0, 200.0, 4200)
    sau = _manh(50.0, 400.0, 2400.0, 1500)                          # 0,75 hash/s: gộp sẽ loãng dưới bậc A
    doi = _manh(80.0, 1000.0, 1100.0, 2500)                         # > 50% mảnh mạnh nhất của vị trí: ngang ngửa
    ds = sorted(_engine({CLIP: 36981})._merge([dau, sau, doi]), key=lambda m: m.vung_khop_s)
    assert [round(m.start_s, 1) for m in ds] == [50.0, 50.0]
    assert not ds[0].moc_mo_ho
    assert ds[1].moc_mo_ho and ds[1].moc_thay_the == (80.0,)


def test_truong_moc_moi_tuong_thich_ket_qua_cu():
    """Kết quả dựng theo kiểu cũ (lịch sử, test, exporter) không có trường mới: mặc định = mốc chắc chắn; trường mới
    không tham gia phép so sánh ``==``."""
    m = Match(clip="a.opus", start_s=1.0, end_s=2.0, matched_s=1.0, clip_offset_s=0.0, hashes=5, confidence="x")
    assert (m.moc_mo_ho, m.moc_thay_the, m.ty_so_doi_thu) == (False, (), 0.0)
    m2 = Match(clip="a.opus", start_s=1.0, end_s=2.0, matched_s=1.0, clip_offset_s=0.0, hashes=5, confidence="x")
    m2.moc_mo_ho, m2.moc_thay_the, m2.ty_so_doi_thu = True, (9.0,), 0.97
    assert m == m2
