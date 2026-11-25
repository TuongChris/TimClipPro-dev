"""DT-03 áp dụng: lượt bù đổi cao độ giữ tốc độ, nhãn trạng thái mốc (P-6), «Các clip khác tìm thấy»."""
import dataclasses
import json
from types import SimpleNamespace

import pytest

import bao_cao_v2 as v2
import engine
from engine import TRUONG_CHINH_SACH, Engine, Match
from tests.test_bao_cao_v2 import _bc, _kq_ca_that
from toc_do_khop import HO_CAO_DO, HO_RESAMPLE, bo_loc_ffmpeg


def test_bo_loc_cao_do_giu_do_dai():
    # asetrate×k đổi cao độ VÀ độ dài k lần; atempo 1/k kéo độ dài về như cũ.
    k = 2 ** (1 / 12)
    loc = bo_loc_ffmpeg(k, HO_CAO_DO)
    assert f"asetrate={round(11025 * k)}" in loc and f"atempo={1 / k:.6f}" in loc
    assert "atempo" not in bo_loc_ffmpeg(k, HO_RESAMPLE)


def test_ke_hoach_co_luoi_cao_do_sau_luoi_resample():
    cfg = engine.Config()
    ke = Engine._ke_hoach_toc_do(SimpleNamespace(config=cfg), [])
    ho = [h for _, h, _ in ke]
    assert ho == [HO_RESAMPLE] * 4 + [HO_CAO_DO] * 4
    # Video bị nâng +1 bán cung → hạ khúc xuống đúng 1 bán cung.
    assert dict(((m, h) for h, _, m in ke))[f"lưới đổi cao độ giữ tốc độ {+1.0:+g} bán cung"] == pytest.approx(
        2 ** (-1 / 12))
    assert "luoi_cao_do" in TRUONG_CHINH_SACH


@pytest.mark.parametrize("sai", [[0], [4.0], [True], ["1"]])
def test_luoi_cao_do_kiem_dau_vao(sai):
    with pytest.raises(ValueError, match="luoi_cao_do"):
        engine.Config(luoi_cao_do=sai).validate()


def test_dong_luot_cao_do_khong_doi_moc_thoi_gian():
    """Lượt bù cao độ: hệ số trong tên khúc là tỉ lệ CAO ĐỘ — mốc phải giữ nguyên, không nhân hệ số."""
    import inspect
    nguon = inspect.getsource(Engine)
    assert "he_so = 1.0 if ho_bu == HO_CAO_DO else giai_ma_he_so(" in nguon


def _m(clip="a.opus", s=100.0, e=200.0, h=3000, mo_ho=False):
    return Match(clip=clip, start_s=s, end_s=e, matched_s=e - s, clip_offset_s=0.0, hashes=h,
                 confidence="Rất chắc chắn", moc_mo_ho=mo_ho)


@pytest.mark.parametrize("tc, moc, mo_ho, mong", [
    (None, (1.0, 2.0), False, "Mốc đã tinh chỉnh"),
    (None, None, False, "Mốc ước lượng"),
    (None, None, True, "Kiểm lại mốc — âm thanh lặp, có nhiều mốc đúng như nhau"),
    ({"trang_thai": "chua_tinh_chinh", "ly_do": "Không đo được mép."}, None, False, "Kiểm lại mốc — Không đo được mép."),
    ({"trang_thai": "chua_tinh_chinh", "ly_do": ""}, None, False, "Kiểm lại mốc — chưa tinh chỉnh được"),
    ({"trang_thai": "da_tinh_chinh"}, None, False, "Kiểm lại mốc — số đo tinh chỉnh không dùng được"),
])
def test_nhan_moc(tc, moc, mo_ho, mong):
    assert v2.nhan_moc(tc, _m(mo_ho=mo_ho), moc) == mong


def test_bao_cao_dung_nhan_moc_thay_nhan_tin_cay():
    bc = _bc()
    assert [d.confidence for d in bc.doan] == ["Mốc ước lượng"]      # lượt quét không tinh chỉnh
    assert bc.doan[0].confidence in v2.dong_doc(bc)[0]


def test_clip_khac_bo_dong_da_chon_va_doan_trung():
    kq = _kq_ca_that()
    chon = kq.matches[0]
    cung_doan = dataclasses.replace(chon, start_s=chon.start_s + 10, hashes=1500)   # cùng clip, giao đoạn → bỏ
    cung_clip_khac_doan = dataclasses.replace(chon, start_s=9000.0, end_s=9100.0, hashes=1200)
    khac = _m(clip="b.opus", s=50.0, e=120.0, h=2000)
    kq.ung_vien_dat = [chon, cung_doan, cung_clip_khac_doan, khac]
    bc = _bc(kq)
    assert bc.clip_khac == (("b.opus", 50.0, 120.0, 2000), (chon.clip, 9000.0, 9100.0, 1200))
    assert v2.dong_clip_khac(bc)[0] == "b.opus | 00:00:50 → 00:02:00 | 2000 hash"
    # Lưu → đọc lại ảnh chụp giữ nguyên; ảnh chụp cũ (không có khoá) đọc ra rỗng.
    d = json.loads(json.dumps(bc.to_dict()))
    assert v2.BaoCaoV2.from_dict(d) == bc
    d.pop("clip_khac")
    assert v2.BaoCaoV2.from_dict(d).clip_khac == ()
    # Không vào bảng 34 cột Sheets.
    assert len(v2.dong_ngang(bc)) == 34


def test_luoi_cao_do_rong_giu_chu_ky_chinh_sach_cu():
    """Lưới rỗng → đúng chữ ký thuật toán trước D-67 (không có khoá luoi_cao_do) — Giám sát không quét lại âm tính cũ."""
    import hashlib
    cu = engine.Config(luoi_cao_do=[], toc_do_toi_da_thu=6)
    gia_tri = {k: getattr(cu, k) for k in TRUONG_CHINH_SACH if k != "luoi_cao_do"}
    ky_cu = "v1:" + hashlib.sha256(json.dumps(gia_tri, sort_keys=True, ensure_ascii=False,
                                              default=str).encode("utf-8")).hexdigest()[:16]
    assert engine.chu_ky_chinh_sach(cu) == ky_cu
    assert engine.chu_ky_chinh_sach(engine.Config(toc_do_toi_da_thu=6)) != ky_cu


def test_doc_duoc_do_troi_van_xep_luoi_cao_do(monkeypatch):
    gia = SimpleNamespace(he_so_bu=1 / 1.03, mo_ta=lambda: "nhanh 3%")
    monkeypatch.setattr(engine, "uoc_luong_toc_do", lambda *a, **k: [gia])
    ke = Engine._ke_hoach_toc_do(SimpleNamespace(config=engine.Config()), [])
    assert [h for _, h, _ in ke] == ["tempo"] + [HO_CAO_DO] * 4


def test_nhan_moc_khong_lo_chu_ngoai_le():
    tc = {"trang_thai": "chua_tinh_chinh", "ly_do": r"Lỗi khi tinh chỉnh: [Errno 13] C:\Kho\a.opus"}
    assert v2.nhan_moc(tc, _m(), None) == "Kiểm lại mốc — lỗi khi tinh chỉnh"


@pytest.mark.parametrize("hong", [[["a.opus", 10, 20]], [5], [["a.opus", 10, 20, "x"]]])
def test_clip_khac_sai_cau_truc_la_anh_chup_hong(hong):
    d = json.loads(json.dumps(_bc().to_dict()))
    d["clip_khac"] = hong
    assert v2.la_loi_bao_cao(v2.doc_anh_chup_da_luu(v2.CHINH_SACH_V2, json.dumps(d)))
