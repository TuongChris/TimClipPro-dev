# -*- coding: utf-8 -*-
"""Audit A-1: hai bản ghi kho CÙNG basename (khác thư mục) bị gộp làm một ``Match.clip``.

Dữ liệu hoàn toàn synthetic: đường dẫn chỉ là chuỗi, không đọc kho thật, không mạng.
Chuỗi xử lý đúng thứ tự ``Engine.scan_media`` sau khi khớp: ``_merge`` → ``_gan_chi_so`` →
``loc_chap_nhan`` (→ ``so_dat_nguong``) → ``_chon_loc`` (Top-N vào báo cáo).

Hành vi ĐÚNG được khẳng định:
  1. Tỷ lệ phủ vân tay và cận trên hash của một kết quả phải tính theo ĐÚNG bản ghi kho đã
     khớp (đường dẫn đầy đủ), không theo bản ghi cùng tên nằm ở thư mục khác.
  2. Hai bản sao giống hệt của cùng một clip (vd. thư mục ``backup/``) khớp cùng một vùng video
     không được thành HAI dòng báo cáo giống hệt nhau, và không được đếm đôi ``so_dat_nguong``.
"""
from chan_doan_quet import ChanDoanQuet
from chap_nhan_khop import loc_chap_nhan
from engine import Config, Engine, liet_ke_media

KHO = "C:/kho_gia_audit_a1"   # chỉ là chuỗi — không có I/O tới đường dẫn này


def _engine(ban_ghi: list) -> Engine:
    """Engine tối thiểu, không __init__; Config MẶC ĐỊNH (ngưỡng thật của sản phẩm)."""
    eng = Engine.__new__(Engine)
    eng.config = Config()
    eng.canh_bao_gop = []
    eng.chan_doan_quet = ChanDoanQuet()
    # Đúng hình dạng `_doc_danh_sach_clip`: ten = basename, duong_dan = đường dẫn trong kho.
    ds = [{"ten": p.rsplit("/", 1)[-1], "duong_dan": p, "so_hash": n} for p, n in ban_ghi]
    eng.db_clips = lambda bo_cache=False: ds
    return eng


def _manh(clip: str, bat_dau: float, khop: float, so_hash: int, t_clip: float = 0.0) -> dict:
    """Mảnh thô như parser trả (k = 1): `clip` là đường dẫn ĐẦY ĐỦ trong kho audfprint."""
    return {"clip": clip, "bat_dau": bat_dau, "khop": khop, "t_clip": t_clip,
            "hash": so_hash, "he_so": 1.0, "align": bat_dau - t_clip}


def _chuoi(eng: Engine, tho: list, duration: float) -> tuple:
    ds = eng._merge(tho)
    eng._gan_chi_so(ds, duration)
    dat, _, _ = loc_chap_nhan(ds, eng.config)
    so_dat_nguong = len(dat)
    chon, _ = eng._chon_loc(ds, duration)
    return ds, so_dat_nguong, chon


def test_tien_de_liet_ke_media_tra_ca_hai_file_cung_ten(tmp_path):
    """Tiền đề thực tế: bước tạo kho liệt kê ĐỆ QUY nên hai file cùng tên đều vào kho."""
    for mua in ("Season 1", "Season 2"):
        (tmp_path / mua).mkdir()
        (tmp_path / mua / "Episode 1.opus").write_bytes(b"\0")
    ds = liet_ke_media(str(tmp_path), bo_thu_muc_lam_viec=True)
    assert sorted(p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in ds) == [
        "Episode 1.opus", "Episode 1.opus"]


def test_ty_le_phai_theo_dung_ban_ghi_da_khop_khong_theo_ban_cung_ten():
    """Khớp 900 hash / 60 s với bản A (20000 hash) = 4,5 % — KHÔNG được nhận bằng bậc phủ cao.

    Bản B cùng tên (1000 hash) đứng sau trong kho: dict theo basename lấy 1000 làm mẫu số
    → 90 % → bậc B (≥ 60 %, ≥ 20 s, ≥ 3 hash/s) chấp nhận nhầm một kết quả sai.
    """
    a = f"{KHO}/Season 1/same.opus"
    b = f"{KHO}/Season 2/same.opus"
    eng = _engine([(a, 20000), (b, 1000)])
    tho = [_manh(a, bat_dau=100.0, khop=60.0, so_hash=900)]

    ds, so_dat_nguong, chon = _chuoi(eng, tho, 3600.0)

    assert len(ds) == 1
    m = ds[0]
    print(f"\n[A-1/a] clip={m.clip} hashes={m.hashes} ty_le={m.ty_le} "
          f"so_dat_nguong={so_dat_nguong} chon={len(chon)}")
    assert m.ty_le == 4.5, f"ty_le tính theo bản ghi cùng tên khác: {m.ty_le}% (đúng: 4.5%)"
    assert so_dat_nguong == 0
    assert chon == []


def test_can_tren_hash_phai_theo_dung_ban_ghi_da_khop():
    """1500 hash khớp bản A (20000 hash) là hợp lệ — không được kẹp về 1000 của bản B cùng tên
    và không được cảnh báo «đếm trùng» sai."""
    a = f"{KHO}/Season 1/same.opus"
    b = f"{KHO}/Season 2/same.opus"
    eng = _engine([(a, 20000), (b, 1000)])
    tho = [_manh(a, bat_dau=100.0, khop=100.0, so_hash=1500)]

    ds = eng._merge(tho)

    print(f"\n[A-1/cap] hashes={ds[0].hashes} canh_bao={eng.canh_bao_gop}")
    assert ds[0].hashes == 1500
    assert not any("đếm trùng" in c for c in eng.canh_bao_gop)


def test_hai_ban_sao_giong_het_khong_thanh_hai_dong_bao_cao():
    """x.opus và backup/x.opus (cùng nội dung) khớp cùng một vùng: một lần dùng = một dòng."""
    x = f"{KHO}/x.opus"
    x_bk = f"{KHO}/backup/x.opus"
    eng = _engine([(x, 10000), (x_bk, 10000)])
    tho = [_manh(x, bat_dau=500.0, khop=300.0, so_hash=6000),
           _manh(x_bk, bat_dau=500.0, khop=300.0, so_hash=6000)]

    ds, so_dat_nguong, chon = _chuoi(eng, tho, 7200.0)

    dong = [(m.clip, round(m.start_s, 1), m.hashes) for m in chon]
    print(f"\n[A-1/b] chon={dong} so_dat_nguong={so_dat_nguong}")
    assert len(dong) == len(set((c, s) for c, s, _ in dong)), (
        f"báo cáo có dòng trùng (clip, mốc): {dong}")
    assert so_dat_nguong == 1, f"so_dat_nguong đếm đôi: {so_dat_nguong}"


def test_hai_ban_cung_ten_khop_hai_cho_khac_nhau_van_la_hai_lan_dung():
    """Chặn sửa quá tay: hai bản ghi cùng tên khớp HAI vị trí khác nhau là hai lần dùng thật —
    không được bỏ bản nào; mỗi dòng mang tỷ lệ theo đúng bản ghi của nó."""
    a = f"{KHO}/Season 1/same.opus"
    b = f"{KHO}/Season 2/same.opus"
    eng = _engine([(a, 20000), (b, 2000)])
    tho = [_manh(a, bat_dau=100.0, khop=300.0, so_hash=6000),
           _manh(b, bat_dau=3000.0, khop=60.0, so_hash=900)]

    ds, _, _ = _chuoi(eng, tho, 7200.0)

    assert [(m.duong_dan_kho, m.ty_le) for m in ds] == [(a, 30.0), (b, 45.0)]
    assert not any("cùng tên" in c for c in eng.canh_bao_gop)


def test_ban_sao_bi_bo_co_canh_bao_cho_nguoi_dung():
    x = f"{KHO}/x.opus"
    x_bk = f"{KHO}/backup/x.opus"
    eng = _engine([(x, 10000), (x_bk, 10000)])
    tho = [_manh(x, bat_dau=500.0, khop=300.0, so_hash=6000),
           _manh(x_bk, bat_dau=500.0, khop=300.0, so_hash=6000)]

    ds = eng._merge(tho)

    assert len(ds) == 1
    assert any("2 bản ghi cùng tên «x.opus»" in c for c in eng.canh_bao_gop)


def test_khong_tra_duoc_duong_dan_thi_lui_ve_ten_lay_tong_lon_nhat():
    """Đường dẫn audfprint báo không khớp chuỗi nào trong kho: lùi về tên; tên trùng thì lấy tổng
    LỚN NHẤT — tỷ lệ thấp (không nhận nhầm qua bậc phủ cao), cận trên rộng (không kẹp oan)."""
    eng = _engine([(f"{KHO}/Season 1/same.opus", 20000), (f"{KHO}/Season 2/same.opus", 1000)])
    tho = [_manh("khac/same.opus", bat_dau=100.0, khop=100.0, so_hash=1500)]

    ds = eng._merge(tho)
    eng._gan_chi_so(ds, 3600.0)

    assert ds[0].hashes == 1500 and ds[0].ty_le == 7.5
    assert not any("đếm trùng" in c for c in eng.canh_bao_gop)
