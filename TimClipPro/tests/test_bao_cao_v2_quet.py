# -*- coding: utf-8 -*-
"""Báo cáo V2 qua đường quét THẬT của engine (thế giới giả của golden: chỉ giả FFmpeg,
audfprint, yt-dlp) — ảnh chụp, exporter, lịch sử, vòng đời.

Ca dựng lại theo số liệu ca người dùng nêu (mã/tiêu đề GIẢ): clip gốc bắt đầu ở 915,5 s, lượt quét DỪNG SỚM nên
quét một phần. Bản cũ: tên có hậu tố «[QUÉT MỘT PHẦN — …]», link bảng ngang lùi 3 giây,
ngày đăng đã quy đổi, link gốc youtu.be. V2: không còn cả bốn, phạm vi vẫn còn nguyên.
"""
import csv
import dataclasses
import os

import bao_cao_v2 as v2
import bang_ngang
import golden_quet as gq
from clip_metadata import ClipMetadataResolver
from engine import Engine, ScanResult
from golden_quet import Dat, KichBan

_B = "B [bbbbbbbbbbb].opus"
_C = "C [ccccccccccc].opus"

META = {
    # Ngày kho ĐÃ quy đổi múi giờ (nguồn timestamp) — không phải ngày nguyên bản.
    _B: {"id": "bbbbbbbbbbb", "title": "Clip B gốc", "upload_date": "20250102",
         "publication_date": "20250102", "publication_date_source": "timestamp",
         "duration": 300.4, "url": "https://youtu.be/bbbbbbbbbbb"},
    # Ngày kho lấy thẳng từ upload_date (không quy đổi) — tương đương nguyên bản.
    _C: {"id": "ccccccccccc", "title": "Clip C gốc", "upload_date": "20250203",
         "publication_date": "20250203", "publication_date_source": "upload_date",
         "duration": 100.0, "url": "https://youtu.be/ccccccccccc"},
}
TIEU_DE = "Video [thật] có ngoặc vuông"
INFO = {
    "id": "vidvipham01", "title": TIEU_DE, "title_raw": TIEU_DE, "duration": 3000,
    "uploader": "Kênh thử", "channel": "Kênh thử", "channel_id": "UCthu",
    "channel_url": "https://www.youtube.com/channel/UCthu",
    # wrapper `youtube_info`: `upload_date` đã quy đổi, `upload_date_raw` là của yt-dlp
    "upload_date": "20260316", "upload_date_raw": "20260315",
    "publication_date_source": "timestamp", "publication_date_confidence": "high",
}
URL = "https://youtu.be/vidvipham01"


def _the_gioi(tmp_path, monkeypatch, dat, *, tong_s=3000, nguon="youtube", cau_hinh=None,
              meta=None, info=None):
    kb = KichBan("v2", nguon, tong_s,
                 {"top_n": 1, "quet_da_toc_do": False, **(cau_hinh or {})}, tuple(dat))
    e = gq.tao_engine(kb, tmp_path)
    mt = gq.MoiTruongGia(kb, e, str(tmp_path))
    mt.lap(monkeypatch)
    hop = {"resolver": ClipMetadataResolver.from_mapping(META if meta is None else meta),
           "info": [], "info_tra": dict(INFO if info is None else info)}
    e.clip_metadata_resolver = lambda bo_cache=False: hop["resolver"]

    def youtube_info(url):
        hop["info"].append(url)
        if isinstance(hop["info_tra"], Exception):
            raise hop["info_tra"]
        return dict(hop["info_tra"])

    e.youtube_info = youtube_info
    return e, mt, hop, kb


def _quet_ca_that(tmp_path, monkeypatch, **kw):
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)], **kw)
    kq = e.scan_youtube(URL)
    return e, kq, hop


def _o(dong):
    return dict(zip(bang_ngang.HEADER_NGANG, dong))


# ---------------------------------------------------------------------------
#  Lượt quét mới mang ảnh chụp V2; dòng xuất sạch
# ---------------------------------------------------------------------------

def test_luot_quet_moi_co_anh_chup_v2(tmp_path, monkeypatch):
    e, kq, _ = _quet_ca_that(tmp_path, monkeypatch)
    assert kq.status == "ok" and kq.matches
    assert isinstance(kq.bao_cao, v2.BaoCaoV2)
    assert kq.bao_cao.chinh_sach == "v2"


def test_ban_ngang_v2_ten_sach_link_dung_moc_ngay_nguyen_ban_url_watch(tmp_path, monkeypatch):
    e, kq, _ = _quet_ca_that(tmp_path, monkeypatch)
    assert kq.quet_mot_phan and kq.ly_do_pham_vi == "dung_som"      # quét một phần thật
    o = _o(e.to_rows_ngang([kq])[0])
    assert o["Tên video vi phạm"] == TIEU_DE
    assert o["Đoạn vi phạm 1 trong video vi phạm"] == \
        "00:15:15 – 00:20:15 · https://youtu.be/vidvipham01?t=915"
    assert o["Ngày đăng video vi phạm"] == "15/03/2026"
    assert o["Link video gốc 1"] == "https://www.youtube.com/watch?v=bbbbbbbbbbb"
    assert o["Ngày đăng video gốc 1"] == ""          # kho chỉ có ngày đã quy đổi
    assert o["Tên video gốc 1"] == "Clip B gốc"
    assert o["Thời lượng video gốc 1"] == "00:05:00"


def test_cu_va_moi_canh_nhau_cung_mot_ban_build(tmp_path, monkeypatch):
    """Cùng một kết quả: không có ảnh chụp → luật CŨ nguyên vẹn; có → V2."""
    e, kq, _ = _quet_ca_that(tmp_path, monkeypatch)
    cu = dataclasses.replace(kq, bao_cao=None)
    o_cu, o_moi = _o(e.to_rows_ngang([cu])[0]), _o(e.to_rows_ngang([kq])[0])
    assert o_cu["Tên video vi phạm"].startswith(TIEU_DE + " [QUÉT MỘT PHẦN — ")
    assert o_cu["Đoạn vi phạm 1 trong video vi phạm"].endswith("?t=912")
    assert o_cu["Ngày đăng video vi phạm"] == "16/03/2026"
    assert o_cu["Link video gốc 1"] == "https://youtu.be/bbbbbbbbbbb"
    assert o_cu["Ngày đăng video gốc 1"] == "02/01/2025"
    assert o_moi["Tên video vi phạm"] == TIEU_DE
    doc_cu, doc_moi = e.to_rows([cu])[0], e.to_rows([kq])[0]
    assert "QUÉT MỘT PHẦN" in doc_cu[1] and doc_moi[1] == TIEU_DE
    assert doc_cu[5] == "https://youtu.be/bbbbbbbbbbb"
    assert doc_moi[5] == "https://www.youtube.com/watch?v=bbbbbbbbbbb"


def test_ket_qua_cu_khong_tu_nang_len_v2():
    assert ScanResult(source_name="x").bao_cao is None


def test_engine_chua_ghim_job_thi_khong_chup_v2(tmp_path, monkeypatch):
    """Chính sách ghim ở ranh giới job — gọi thẳng thân hàm trên Engine gốc = luật cũ."""
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)])
    kq = e._scan_youtube(URL, luu_lich_su=False)
    assert kq.matches and kq.bao_cao is None


def test_pham_vi_khong_mat_khi_ten_sach(tmp_path, monkeypatch):
    e, kq, _ = _quet_ca_that(tmp_path, monkeypatch)
    pv = kq.bao_cao.pham_vi
    assert pv.quet_mot_phan and not pv.quet_day_du and pv.ly_do == "dung_som"
    assert pv.mo_ta and pv.vung_da_khop
    assert kq.quet_mot_phan and kq.ly_do_pham_vi == "dung_som"     # trường cũ còn nguyên


def test_ngay_goc_co_nguon_upload_date_hien_ra(tmp_path, monkeypatch):
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_C, 100, 300)], tong_s=600,
                               cau_hinh={"quet_tang_dan": False})
    kq = e.scan_youtube(URL)
    o = _o(e.to_rows_ngang([kq])[0])
    assert o["Ngày đăng video gốc 1"] == "03/02/2025"
    g = kq.bao_cao.doan[0].goc
    assert g.ngay_dang.nguon == "clips_meta.publication_date(nguon=upload_date)"


def test_moc_ket_thuc_va_so_thuc_matching_giu_nguyen(tmp_path, monkeypatch):
    e, kq, _ = _quet_ca_that(tmp_path, monkeypatch)
    m, d = kq.matches[0], kq.bao_cao.doan[0]
    assert (d.start_s, d.end_s, d.matched_s, d.hashes) == (m.start_s, m.end_s, m.matched_s,
                                                           m.hashes)
    assert d.giay_ket_thuc == int(m.end_s)


# ---------------------------------------------------------------------------
#  Lỗi / file / tên thiếu
# ---------------------------------------------------------------------------

def test_loi_lay_thong_tin_khong_bien_url_thanh_ten(tmp_path, monkeypatch):
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)])
    hop["info_tra"] = RuntimeError("ERROR: Video unavailable")
    kq = e.scan_youtube(URL)
    assert kq.status == "error"
    bc = kq.bao_cao
    assert bc.trang_thai == "error" and bc.tieu_de == "" and bc.ly_do_thieu_tieu_de
    hang = e.to_rows([kq])[0]
    assert hang[1] == "" and hang[3].startswith("(LỖI: ")
    assert kq.source_name == URL                 # trường cũ giữ nguyên hành vi cũ


def test_youtube_khong_tra_tieu_de_thi_de_trong(tmp_path, monkeypatch):
    info = {**INFO, "title": URL, "title_raw": ""}
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)], info=info)
    kq = e.scan_youtube(URL)
    assert kq.bao_cao.tieu_de == "" and kq.bao_cao.ly_do_thieu_tieu_de
    assert _o(e.to_rows_ngang([kq])[0])["Tên video vi phạm"] == ""


def test_quet_file_ten_file_va_khong_ngay(tmp_path, monkeypatch):
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 10, 180, mat_do=30.0)],
                               tong_s=600, nguon="file")
    media = tmp_path / "video_vi_pham.mp4"
    media.write_bytes(b"x")
    mt.thoi_luong[mt._khoa(str(media))] = 600.0
    kq = e.scan_media(str(media))
    bc = kq.bao_cao
    assert bc.nguon_loai == "file" and bc.tieu_de == "video_vi_pham.mp4"
    assert bc.nguon_tieu_de == v2.NGUON_TIEU_DE_TEN_FILE
    assert bc.ngay_dang.gia_tri == "" and "quét file" in bc.ngay_dang.ly_do_thieu
    assert bc.doan[0].link == ""                 # file trên máy: không bịa link YouTube
    assert hop["info"] == []                     # quét file không hỏi YouTube


# ---------------------------------------------------------------------------
#  Lịch sử: lưu ảnh chụp, đọc lại không qua resolver, sau khởi động lại
# ---------------------------------------------------------------------------

def test_luu_va_doc_lai_anh_chup_khong_hoi_resolver_hien_tai(tmp_path, monkeypatch):
    e, kq, hop = _quet_ca_that(tmp_path, monkeypatch)
    assert kq.job_id
    truoc = e.to_rows_ngang([kq])
    # Kho bị sửa metadata SAU lần quét: tên, URL, ngày đều đổi.
    hop["resolver"] = ClipMetadataResolver.from_mapping({_B: {
        "id": "bbbbbbbbbbb", "title": "TÊN MỚI", "upload_date": "20991231",
        "upload_date_raw": "20991231", "duration": 1.0}})
    assert e.to_rows_ngang([kq]) == truoc
    doc_lai = e.bao_cao_cua_job(kq.job_id)
    assert doc_lai == kq.bao_cao
    assert v2.dong_ngang(doc_lai) == truoc[0]


def test_khoi_dong_lai_van_xuat_tu_anh_chup(tmp_path, monkeypatch):
    e, kq, _ = _quet_ca_that(tmp_path, monkeypatch)
    e2 = Engine(root=e.root, data_dir=e.data_dir, out_dir=e.out_dir)
    lai = e2.bao_cao_cua_job(kq.job_id)
    assert lai == kq.bao_cao
    assert e2.dong_bao_cao_job(kq.job_id, dang_ngang=True) == e.to_rows_ngang([kq])


def test_ban_ghi_lich_su_khong_co_anh_chup_la_ban_cu(engine):
    job_id = engine.save_job(ScanResult(source_name="x", source_ref="u"), "youtube")
    assert engine.bao_cao_cua_job(job_id) is None
    assert engine.dong_bao_cao_job(job_id, dang_ngang=True) is None


def test_bang_jobs_giu_nguyen_cot(tmp_path, monkeypatch):
    """Ảnh chụp nằm ở bảng riêng: dòng `jobs` y hệt bản cũ (golden lịch sử không đổi)."""
    e, kq, _ = _quet_ca_that(tmp_path, monkeypatch)
    with e._db() as c:
        cot = [r[1] for r in c.execute("PRAGMA table_info(jobs)")]
        assert "bao_cao" not in cot
        so = c.execute("SELECT COUNT(*) FROM bao_cao_job WHERE job_id=?",
                       (kq.job_id,)).fetchone()[0]
    assert so == 1


# ---------------------------------------------------------------------------
#  Đồng nhất giữa các exporter + an toàn công thức
# ---------------------------------------------------------------------------

def test_moi_exporter_cung_ten_link_url_ngay(tmp_path, monkeypatch):
    e, kq, hop = _quet_ca_that(tmp_path, monkeypatch)
    so_lan_hoi_youtube = len(hop["info"])
    link = "https://youtu.be/vidvipham01?t=915"
    goc = "https://www.youtube.com/watch?v=bbbbbbbbbbb"
    ngang = e.to_rows_ngang([kq])[0]
    doc = e.to_rows([kq])[0]
    f = e.export_csv_ngang([kq])
    with open(f, encoding="utf-8-sig", newline="") as fh:
        csv_ngang = list(csv.reader(fh))[1]
    md = open(e.export_ho_so([kq])[0], encoding="utf-8").read()
    header, sheets, nghiem_ngat = e.dong_gui_sheets([kq], dang_ngang=True, an_toan_cu=True)
    for dong in (ngang, csv_ngang, sheets[0]):
        assert dong[5] == TIEU_DE and link in dong[8] and dong[13] == goc
        assert dong[7] == "15/03/2026"
    assert doc[1] == TIEU_DE and doc[10] == link and doc[5] == goc
    assert f"**Tiêu đề video vi phạm:** {TIEU_DE}" in md and link in md and goc in md
    assert "QUÉT MỘT PHẦN" not in md.split("Phạm vi đã quét")[0]
    assert "Phạm vi đã quét" in md
    assert nghiem_ngat is True and header == bang_ngang.HEADER_NGANG
    assert len(hop["info"]) == so_lan_hoi_youtube, "exporter/formatter không bao giờ gọi mạng"


def test_csv_van_chan_cong_thuc_sheets_khong_them_nhay(tmp_path, monkeypatch):
    info = {**INFO, "title": "=HYPERLINK(\"http://x\")", "title_raw": "=HYPERLINK(\"http://x\")"}
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)], info=info)
    kq = e.scan_youtube(URL)
    assert kq.bao_cao.tieu_de == "=HYPERLINK(\"http://x\")"         # ảnh chụp nguyên văn
    with open(e.export_csv_ngang([kq]), encoding="utf-8-sig", newline="") as fh:
        assert list(csv.reader(fh))[1][5] == "'=HYPERLINK(\"http://x\")"
    _, rows, _ = e.dong_gui_sheets([kq], dang_ngang=True, an_toan_cu=True)
    assert rows[0][5] == "=HYPERLINK(\"http://x\")"        # RAW: Sheets không hiểu là công thức


def test_dong_gui_sheets_ban_cu_giu_nguyen_luat_cu(tmp_path, monkeypatch):
    info = {**INFO, "title": "-tên bắt đầu bằng gạch", "title_raw": "-tên bắt đầu bằng gạch"}
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)], info=info)
    kq = e.scan_youtube(URL)
    cu = dataclasses.replace(kq, bao_cao=None)
    _, rows, nghiem_ngat = e.dong_gui_sheets([cu], dang_ngang=True, an_toan_cu=True)
    assert rows[0][5].startswith("'-tên") and nghiem_ngat is False
    _, rows, _ = e.dong_gui_sheets([cu], dang_ngang=True, an_toan_cu=False)
    assert rows[0][5].startswith("-tên")


def test_csv_v2_kem_file_pham_vi(tmp_path, monkeypatch):
    e, kq, _ = _quet_ca_that(tmp_path, monkeypatch)
    f = e.export_csv_ngang([kq])
    phu = os.path.splitext(f)[0] + ".pham_vi.csv"
    with open(phu, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == v2.HEADER_PHAM_VI
    assert rows[1][1] == TIEU_DE and rows[1][2] == "Một phần"
    assert "dừng sớm" in rows[1][4]
    # CSV dọc cũng có sidecar
    f2 = e.export_csv([kq])
    assert os.path.isfile(os.path.splitext(f2)[0] + ".pham_vi.csv")


def test_csv_ban_cu_khong_sinh_file_phu(tmp_path, monkeypatch):
    e, kq, _ = _quet_ca_that(tmp_path, monkeypatch)
    f = e.export_csv_ngang([dataclasses.replace(kq, bao_cao=None)])
    assert not os.path.exists(os.path.splitext(f)[0] + ".pham_vi.csv")


def test_giao_hang_sheets_v2_chot_dong_nguyen_van_nghiem_ngat(tmp_path, monkeypatch):
    """Việc gửi Sheets của giao diện (scan_ui.giao_hang_sheets): dòng chốt lúc xếp hàng."""
    from scan_ui import giao_hang_sheets

    info = {**INFO, "title": "-tên bắt đầu bằng gạch", "title_raw": "-tên bắt đầu bằng gạch"}
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)], info=info)
    kq = e.scan_youtube(URL)
    viec = giao_hang_sheets(e, kq, sheet_id="abc", sheet_link="s", dang_ngang=True)
    assert viec.nghiem_ngat is True and viec.header == bang_ngang.HEADER_NGANG
    assert viec.rows[0][5] == "-tên bắt đầu bằng gạch"          # RAW: không thêm dấu '
    assert viec.rows[0][8].endswith("?t=915")
    da_chot = [list(r) for r in viec.rows]
    hop["resolver"] = ClipMetadataResolver.from_mapping({})      # kho đổi sau khi xếp hàng
    assert viec.rows == da_chot
    cu = giao_hang_sheets(e, dataclasses.replace(kq, bao_cao=None), sheet_id="abc",
                          sheet_link="s", dang_ngang=True)
    assert cu.nghiem_ngat is False and cu.rows[0][5].startswith("'-tên")
    assert giao_hang_sheets(e, dataclasses.replace(kq, status="error"), sheet_id="abc",
                            sheet_link="s", dang_ngang=True) is None


def test_youtube_info_khong_co_tieu_de_thi_title_raw_rong(engine, monkeypatch):
    import yt_dlp
    from test_engine_meta import _YoutubeDLGia

    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: _YoutubeDLGia({"id": "abc12345678"}))
    info = engine.youtube_info("https://youtu.be/abc12345678")
    assert info["title"] == "https://youtu.be/abc12345678"      # luật cũ: lùi về URL
    assert info["title_raw"] == ""                               # V2: không lấy URL làm tên
