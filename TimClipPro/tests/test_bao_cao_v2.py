# -*- coding: utf-8 -*-
"""Chính sách báo cáo V2 — phần THUẦN: mốc/link, URL gốc, ngày nguyên bản, ảnh chụp, dòng xuất.

Số liệu dựng theo ca người dùng nêu, nhưng mọi mã video/tiêu đề ở đây là GIẢ: clip gốc bắt
đầu ở 915,5 s → hiển thị 00:15:15 và link phải là ``t=915`` (bản cũ ở bảng ngang ra 912).
"""
import json
import math
from urllib.parse import parse_qs, urlsplit

import pytest

import bao_cao_v2 as v2
from bang_ngang import HEADER_NGANG
from clip_metadata import ClipMetadataResolver
from engine import Engine, Match, ScanResult


# ---------------------------------------------------------------------------
#  Mốc giây dùng chung cho hiển thị và link
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("giay, mong", [
    (915.0, 915), (915.8, 915), (915.999999, 915), (0, 0), (0.0, 0), (0.4, 0),
    (59.99, 59), (60.0, 60), (3599.9, 3599), (3600.0, 3600),
    (86399.5, 86399), (90061.2, 90061), (360000.0, 360000),
])
def test_giay_moc_cat_phan_le_giong_hhmmss(giay, mong):
    assert v2.giay_moc(giay) == mong


@pytest.mark.parametrize("xau", [float("nan"), float("inf"), -float("inf"), -0.5, -1,
                                 None, "915", True, False, [915]])
def test_giay_moc_khong_bien_du_lieu_hong_thanh_moc_hop_le(xau):
    assert v2.giay_moc(xau) is None


@pytest.mark.parametrize("giay, mong", [
    (0, "00:00:00"), (59, "00:00:59"), (60, "00:01:00"), (3599, "00:59:59"),
    (3600, "01:00:00"), (86399, "23:59:59"), (90061, "25:01:01"), (360000, "100:00:00"),
])
def test_hien_thi_moc_vuot_24_gio(giay, mong):
    assert v2.hien_thi_moc(giay) == mong


def test_hien_thi_moc_khong_hop_le_la_dau_hoi():
    assert v2.hien_thi_moc(None) == "?"


@pytest.mark.parametrize("start", [915.0, 915.5, 915.8])
def test_link_trung_dung_giay_hien_thi(start):
    g = v2.giay_moc(start)
    assert v2.hien_thi_moc(g) == "00:15:15"
    assert v2.link_nhay("vidvipham01", "", g) == "https://www.youtube.com/watch?v=vidvipham01&t=915"


def test_link_khong_co_mot_mot_tham_so_t_khi_dung_tu_source_ref():
    ref = "https://www.youtube.com/watch?v=vidvipham01&t=10s&start=5#t=3"
    link = v2.link_nhay("", ref, 915)
    assert link == "https://www.youtube.com/watch?v=vidvipham01&t=915"
    assert link.count("t=") == 1 and "start" not in link and "#" not in link


@pytest.mark.parametrize("ref", [
    "https://youtube.com.evil.example/watch?v=vidvipham01",
    "https://evil.example/?v=vidvipham01",
    "D:/video/tai_ve [vidvipham01].mp4",
    "vidvipham01",
    "https://www.youtube.com/watch?v=khong_hop_le",
    "",
])
def test_link_khong_suy_ma_tu_host_gia_ten_file_hay_ma_tran(ref):
    assert v2.link_nhay("", ref, 915) == ""


def test_link_nhay_dang_watch_tach_dung_ma_va_giay():
    """``t`` là tham số RIÊNG sau ``&``; ``watch?v=<ID>?t=…`` sẽ dính giây vào mã video."""
    link = v2.link_nhay("vidvipham01", "", 915)
    u = urlsplit(link)
    assert (u.scheme, u.netloc, u.path) == ("https", "www.youtube.com", "/watch")
    assert parse_qs(u.query) == {"v": ["vidvipham01"], "t": ["915"]}
    assert link.count("?") == 1 and u.fragment == ""


def test_link_khong_co_khi_moc_khong_hop_le():
    assert v2.link_nhay("vidvipham01", "", None) == ""
    assert v2.link_nhay("vidvipham01", "", v2.giay_moc(float("nan"))) == ""


def test_source_id_sai_dinh_dang_thi_lui_ve_url_hop_le():
    assert v2.link_nhay("abc", "https://youtu.be/vidvipham01?si=x", 7) == \
        "https://www.youtube.com/watch?v=vidvipham01&t=7"


# ---------------------------------------------------------------------------
#  URL video gốc
# ---------------------------------------------------------------------------

def test_url_goc_dang_watch():
    assert v2.url_goc_chuan("goc00000001") == "https://www.youtube.com/watch?v=goc00000001"


@pytest.mark.parametrize("ma", ["", None, "goc0000000", "goc000000011", "goc0000 001",
                                "https://youtu.be/goc00000001", 12345678901])
def test_url_goc_khong_bia_khi_ma_sai(ma):
    assert v2.url_goc_chuan(ma) == ""


# ---------------------------------------------------------------------------
#  Ngày đăng nguyên bản
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tz", ["Asia/Ho_Chi_Minh", "UTC", "America/Los_Angeles",
                                "Pacific/Kiritimati"])
def test_ngay_nguyen_ban_giu_ngay_lich_o_moi_mui_gio(monkeypatch, tz):
    monkeypatch.setenv("TZ", tz)
    ngay = v2.ngay_tu_info({"upload_date_raw": "20260315", "upload_date": "20260316"})
    assert ngay.gia_tri == "20260315"
    assert ngay.nguon == v2.NGUON_UPLOAD_DATE
    assert ngay.hien_thi() == "15/03/2026"


def test_ngay_khong_doc_khoa_upload_date_da_quy_doi_cua_wrapper():
    """`Engine.youtube_info()['upload_date']` là ngày đã quy đổi — không phải raw."""
    ngay = v2.ngay_tu_info({"upload_date": "20260316", "timestamp": 1773604800})
    assert ngay.gia_tri == ""
    assert "upload_date gốc" in ngay.ly_do_thieu


@pytest.mark.parametrize("tho, ly_do", [
    ("", "không trả upload_date"), (None, "không trả upload_date"),
    ("20260231", "không phải ngày hợp lệ"), ("2026-03-15", "không phải ngày hợp lệ"),
    ("00000000", "không phải ngày hợp lệ"), ("2026031", "không phải ngày hợp lệ"),
])
def test_ngay_hong_hoac_thieu_khong_doan(tho, ly_do):
    ngay = v2.ngay_tu_info({"upload_date_raw": tho})
    assert ngay.gia_tri == "" and ngay.hien_thi() == ""
    assert ly_do in ngay.ly_do_thieu


# ---------------------------------------------------------------------------
#  Tiêu đề nguồn
# ---------------------------------------------------------------------------

def test_tieu_de_that_co_ngoac_vuong_giu_nguyen():
    t = "Tên [QUÉT MỘT PHẦN — thử] (Phần 2) [4K]"
    assert v2.tieu_de_tu_info({"title_raw": t}, "https://youtu.be/x") == (
        t, v2.NGUON_TIEU_DE_YTDLP, "")


def test_tieu_de_thieu_khong_lay_url_lam_ten():
    url = "https://www.youtube.com/watch?v=vidvipham01"
    assert v2.tieu_de_tu_info({"title_raw": ""}, url)[0] == ""
    # dict kiểu cũ: youtube_info() lùi `title` về URL khi yt-dlp không trả tiêu đề
    tieu_de, nguon, ly_do = v2.tieu_de_tu_info({"title": url}, url)
    assert tieu_de == "" and nguon == "" and ly_do
    assert v2.tieu_de_tu_info(None, url)[2] == "chưa lấy được thông tin video"


# ---------------------------------------------------------------------------
#  Video gốc từ metadata kho
# ---------------------------------------------------------------------------

def _resolver(entry: dict, ten="20250312 - Clip gốc thử [goc00000001].opus"):
    return ClipMetadataResolver.from_mapping({ten: entry}).resolve(ten), ten


def test_goc_ngay_kho_da_quy_doi_khong_bi_goi_la_nguyen_ban():
    meta, ten = _resolver({"id": "goc00000001", "title": "Clip gốc thử",
                           "upload_date": "20250312", "publication_date": "20250312",
                           "publication_date_source": "timestamp", "duration": 1500.0,
                           "url": "https://youtu.be/goc00000001"})
    g = v2.goc_tu_metadata(ten, meta)
    assert g.url == "https://www.youtube.com/watch?v=goc00000001"
    assert g.ngay_dang.gia_tri == "" and g.ngay_dang.hien_thi() == ""
    assert "đã quy đổi" in g.ngay_dang.ly_do_thieu and "timestamp" in g.ngay_dang.ly_do_thieu
    assert g.ngay_kho_quy_doi == "20250312"          # giữ để chẩn đoán, không hiển thị


def test_goc_ngay_kho_co_nguon_upload_date_la_nguyen_ban():
    meta, ten = _resolver({"id": "goc00000001", "title": "T", "upload_date": "20250312",
                           "publication_date": "20250312",
                           "publication_date_source": "upload_date", "duration": 10.0})
    g = v2.goc_tu_metadata(ten, meta)
    assert g.ngay_dang.gia_tri == "20250312"
    assert g.ngay_dang.nguon == "clips_meta.publication_date(nguon=upload_date)"


def test_goc_upload_date_raw_moi_thang():
    meta, ten = _resolver({"id": "goc00000001", "title": "T", "upload_date": "20250313",
                           "publication_date": "20250313",
                           "publication_date_source": "timestamp",
                           "upload_date_raw": "20250312", "duration": 10.0})
    g = v2.goc_tu_metadata(ten, meta)
    assert (g.ngay_dang.gia_tri, g.ngay_dang.nguon) == ("20250312", "clips_meta.upload_date_raw")


def test_goc_schema_cu_chi_co_upload_date_khong_coi_la_nguyen_ban():
    meta, ten = _resolver({"id": "goc00000001", "title": "T", "upload_date": "20250312"})
    g = v2.goc_tu_metadata(ten, meta)
    assert g.ngay_dang.gia_tri == ""


def test_goc_ngay_ten_file_khong_bao_gio_la_nguyen_ban():
    ten = "20250312 - Clip gốc thử [goc00000001].opus"
    meta = ClipMetadataResolver.from_mapping({}).resolve(ten)      # filename_fallback
    g = v2.goc_tu_metadata(ten, meta)
    assert g.ngay_dang.gia_tri == ""
    assert g.nguon_tieu_de == v2.NGUON_TIEU_DE_TEN_FILE_KHO


def test_goc_ngay_bo_sung_chi_dung_khi_kho_thieu():
    meta, ten = _resolver({"id": "goc00000001", "title": "T", "upload_date": "20250313",
                           "publication_date": "20250313",
                           "publication_date_source": "timestamp", "duration": 1.0})
    bo_sung = v2.NgayNguon(gia_tri="20250312", nguon=v2.NGUON_UPLOAD_DATE)
    assert v2.goc_tu_metadata(ten, meta, bo_sung).ngay_dang == bo_sung


def test_goc_mo_ho_khong_bia_url():
    ten = "x [goc00000001].opus"
    meta = ClipMetadataResolver.from_mapping({
        ten: {"id": "AAAAAAAAAAA", "url": "https://youtu.be/BBBBBBBBBBB"}}).resolve(ten)
    g = v2.goc_tu_metadata(ten, meta)
    assert g.video_id == "" and g.url == ""


# ---------------------------------------------------------------------------
#  Ảnh chụp + dòng xuất
# ---------------------------------------------------------------------------

def _kq_ca_that(**them) -> ScanResult:
    m = Match(clip="20250312 - Clip gốc thử [goc00000001].opus",
              start_s=915.5, end_s=2350.0, matched_s=1300.5, clip_offset_s=55.5,
              hashes=20000, confidence="Rất chắc chắn", ty_le=70.0, vung="Đầu",
              clip_bat_dau_s=915.5, vung_khop_s=971.0)
    kq = ScanResult(
        source_name="Video tổng hợp thử (Phần 2)",
        source_ref="https://www.youtube.com/watch?v=vidvipham01", source_id="vidvipham01",
        duration_s=14523.4, matches=[m], channel_name="Kênh", channel_id="UCx",
        channel_url="https://www.youtube.com/channel/UCx", upload_date="20260316",
        so_dat_nguong=1, vung_da_khop=[(0.0, 3599.5)], ly_do_pham_vi="dung_som",
        pham_vi_quet_s=3599.5, dat_muc_tieu=True)
    for k, v in them.items():
        setattr(kq, k, v)
    return kq


def _goc_ca_that(ngay="20250312", nguon=v2.NGUON_UPLOAD_DATE):
    return v2.GocV2(
        clip="20250312 - Clip gốc thử [goc00000001].opus",
        video_id="goc00000001", url=v2.url_goc_chuan("goc00000001"),
        tieu_de="Clip gốc thử.", nguon_tieu_de="clips_meta",
        ngay_dang=v2.NgayNguon(gia_tri=ngay, nguon=nguon), thoi_luong_s=1500.25)


def _bc(kq=None, **them) -> v2.BaoCaoV2:
    kq = kq or _kq_ca_that()
    tham = dict(
        thoi_diem_quet="2026-01-02 03:04:05", nguon_loai="youtube",
        tieu_de=kq.source_name, nguon_tieu_de=v2.NGUON_TIEU_DE_YTDLP, ly_do_thieu_tieu_de="",
        ngay_dang=v2.NgayNguon(gia_tri="20260315", nguon=v2.NGUON_UPLOAD_DATE),
        goc_theo_clip={m.clip: _goc_ca_that() for m in kq.matches},
        mo_ta_pham_vi="đã đủ bằng chứng sau khi so khớp 00:59:59/04:02:03, phần còn lại chưa quét")
    tham.update(them)
    return v2.dung_bao_cao(kq, **tham)


def test_dong_ngang_ca_that_dung_hop_dong_34_cot():
    dong = v2.dong_ngang(_bc())
    assert len(dong) == len(HEADER_NGANG) == 34
    o = dict(zip(HEADER_NGANG, dong))
    assert o["Tên video vi phạm"] == \
        "Video tổng hợp thử (Phần 2)"
    assert "QUÉT MỘT PHẦN" not in o["Tên video vi phạm"]
    assert o["Đoạn vi phạm 1 trong video vi phạm"] == \
        "00:15:15 – 00:39:10 · https://www.youtube.com/watch?v=vidvipham01&t=915"
    assert o["Ngày đăng video vi phạm"] == "15/03/2026"
    assert o["Link video gốc 1"] == "https://www.youtube.com/watch?v=goc00000001"
    assert o["Ngày đăng video gốc 1"] == "12/03/2025"
    assert o["Thời lượng video gốc 1"] == "00:25:00"
    assert o["Thời lượng video vi phạm"] == "04:02:03"
    assert o["Thời gian quét"] == "2026-01-02 03:04:05"
    assert o["Tổng số đoạn phát hiện"] == 1 and isinstance(o["Tổng số đoạn phát hiện"], int)


def test_mot_phan_van_giu_pham_vi_trong_anh_chup():
    bc = _bc()
    assert bc.pham_vi.quet_mot_phan and not bc.pham_vi.quet_day_du
    assert bc.pham_vi.ly_do == "dung_som" and bc.pham_vi.dat_muc_tieu
    assert "00:59:59/04:02:03" in bc.pham_vi.mo_ta
    hang = v2.dong_pham_vi(bc)
    assert hang[2] == "Một phần" and "00:59:59/04:02:03" in hang[3]
    assert hang[4] == "dừng sớm vì đã đủ bằng chứng"
    assert hang[1] == bc.tieu_de                     # tiêu đề vẫn sạch ở sidecar


def test_moc_ket_thuc_giu_nguyen_khong_cong_thoi_luong_goc():
    bc = _bc()
    d = bc.doan[0]
    assert d.end_s == 2350.0 and d.giay_ket_thuc == 2350
    assert d.matched_s == 1300.5 and d.start_s == 915.5
    assert "00:40:15" not in v2.doan_hien_thi(d)


def test_dong_doc_16_cot_dung_cung_gia_tri():
    rows = v2.dong_doc(_bc())
    assert len(rows) == 1 and len(rows[0]) == len(Engine.HEADER) == 16
    o = dict(zip(Engine.HEADER, rows[0]))
    assert o["Nguồn video dài"] == "Video tổng hợp thử (Phần 2)"
    assert o["Link video gốc"] == "https://www.youtube.com/watch?v=goc00000001"
    assert o["Clip bắt đầu từ"] == "00:15:15" and o["Đến"] == "00:39:10"
    assert o["Vùng khớp từ"] == "00:16:11"
    assert o["🔗 Nhảy tới đúng mốc vi phạm"] == "https://www.youtube.com/watch?v=vidvipham01&t=915"
    for cot in Engine.COT_SO:
        assert isinstance(o[cot], (int, float))


def test_dong_doc_loi_va_khong_ket_qua_khong_doi_ten():
    loi = _bc(_kq_ca_that(status="error", note="Bị chặn", matches=[]))
    assert v2.dong_doc(loi)[0][1] == loi.tieu_de
    assert v2.dong_doc(loi)[0][3] == "(LỖI: Bị chặn)"
    rong = _bc(_kq_ca_that(matches=[], matches_loai=[object()]))
    assert v2.dong_doc(rong)[0][3] == "(không có kết quả nào đạt ngưỡng)"
    # Bảng ngang của lượt lỗi: tên KHÔNG thành "(LỖI: …)"
    assert v2.dong_ngang(loi)[5] == loi.tieu_de


def test_moc_nan_khong_thanh_link():
    kq = _kq_ca_that()
    kq.matches[0].start_s = float("nan")
    bc = _bc(kq)
    assert bc.doan[0].giay_bat_dau is None and bc.doan[0].link == ""
    assert v2.doan_hien_thi(bc.doan[0]) == "? – 00:39:10"


def test_anh_chup_luu_doc_lai_y_het_va_khong_giu_tham_chieu():
    bc = _bc()
    chuoi = json.dumps(bc.to_dict(), ensure_ascii=False)
    lai = v2.BaoCaoV2.from_dict(json.loads(chuoi))
    assert lai == bc
    assert v2.dong_ngang(lai) == v2.dong_ngang(bc)
    assert v2.dong_doc(lai) == v2.dong_doc(bc)


def test_anh_chup_cu_giu_link_youtu_be_khong_hoi_to():
    """Ảnh chụp lưu trước khi đổi dạng link: xuất lại đúng link đã chụp (Sheet/CSV cũ khớp)."""
    d = _bc().to_dict()
    cu = "https://youtu.be/vidvipham01?t=915"
    d["doan"][0]["link"] = cu
    lai = v2.doc_anh_chup_da_luu(v2.CHINH_SACH_V2, json.dumps(d, ensure_ascii=False))
    assert isinstance(lai, v2.BaoCaoV2) and lai.doan[0].link == cu
    o = dict(zip(HEADER_NGANG, v2.dong_ngang(lai)))
    assert o["Đoạn vi phạm 1 trong video vi phạm"] == "00:15:15 – 00:39:10 · " + cu
    assert dict(zip(Engine.HEADER, v2.dong_doc(lai)[0]))["🔗 Nhảy tới đúng mốc vi phạm"] == cu


def test_doc_anh_chup_sai_chinh_sach_thi_tu_choi():
    d = _bc().to_dict()
    d["chinh_sach"] = ""
    with pytest.raises(ValueError):
        v2.BaoCaoV2.from_dict(d)
    d["chinh_sach"] = "v2"
    d["phien_ban_anh_chup"] = 99
    with pytest.raises(ValueError):
        v2.BaoCaoV2.from_dict(d)


def test_anh_chup_bat_bien():
    bc = _bc()
    with pytest.raises(Exception):
        bc.tieu_de = "khác"       # type: ignore[misc]
    with pytest.raises(Exception):
        bc.doan[0].goc.url = "x"  # type: ignore[misc]


def test_ngay_goc_thieu_liet_ke_ly_do():
    bc = _bc(goc_theo_clip={_kq_ca_that().matches[0].clip: _goc_ca_that(ngay="", nguon="")})
    assert v2.ngay_goc_thieu(bc)[0][0].endswith("[goc00000001].opus")


def test_so_thuc_ket_qua_khong_bi_lam_tron_trong_anh_chup():
    bc = _bc()
    d = bc.doan[0]
    assert d.start_s == 915.5 and d.vung_khop_s == 971.0
    assert math.isclose(d.clip_offset_s, 55.5) and d.hashes == 20000
