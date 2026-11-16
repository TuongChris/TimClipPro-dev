# -*- coding: utf-8 -*-
"""Báo cáo V2 — ngày đăng NGUYÊN BẢN của video gốc và lượt bổ sung qua YouTube (giả).

Kho thật (đo 04/10/2026, chỉ đọc; số liệu ngoài repo): đa số clip chỉ có ngày ĐÃ quy đổi múi
giờ (nguồn ``timestamp``/``release_timestamp``) — không suy ngược được ``upload_date``. V2 để
trống kèm lý do; người dùng BẬT ``bo_sung_ngay_goc`` thì lượt quét YouTube hỏi thêm đúng các
video gốc ĐÃ CHỌN, mỗi mã một lần trong job / lượt Watch, có trần, qua cầu dao, huỷ được.
Mọi test ở đây offline: ``youtube_info`` là bản giả đếm lời gọi.
"""
import os

import bao_cao_v2 as v2
from clip_metadata import ClipMetadataResolver
from test_bao_cao_v2_quet import INFO, META, URL, _B, _the_gioi
from golden_quet import Dat

URL_GOC_B = "https://www.youtube.com/watch?v=bbbbbbbbbbb"
INFO_GOC_B = {"id": "bbbbbbbbbbb", "title": "Clip B gốc", "title_raw": "Clip B gốc",
              # wrapper: `upload_date` đã quy đổi (kho cũng lưu 20250102), raw là 20250101
              "upload_date": "20250102", "upload_date_raw": "20250101", "duration": 300}


def _the_gioi_bo_sung(tmp_path, monkeypatch, *, bat=True, tra_goc=None, **kw):
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)], **kw)
    e.config.bo_sung_ngay_goc = bat
    e.config.ytdlp_sleep_requests_s = 0.0

    def youtube_info(url):
        hop["info"].append(url)
        if "bbbbbbbbbbb" in url:
            if isinstance(tra_goc, Exception):
                raise tra_goc
            return dict(tra_goc if tra_goc is not None else INFO_GOC_B)
        return dict(INFO)

    e.youtube_info = youtube_info
    hop["mt"] = mt
    return e, hop


def _hoi_goc(hop):
    return [u for u in hop["info"] if "bbbbbbbbbbb" in u]


def test_mac_dinh_tat_khong_hoi_them_va_de_trong_co_ly_do(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=False)
    kq = e.scan_youtube(URL)
    g = kq.bao_cao.doan[0].goc
    assert _hoi_goc(hop) == [] and len(hop["info"]) == 1      # chỉ hỏi video được quét
    assert g.ngay_dang.gia_tri == "" and "đã quy đổi" in g.ngay_dang.ly_do_thieu
    assert g.ngay_kho_quy_doi == "20250102"


def test_bat_thi_hoi_dung_video_goc_da_chon_mot_lan(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    kq = e.scan_youtube(URL)
    g = kq.bao_cao.doan[0].goc
    assert _hoi_goc(hop) == [URL_GOC_B]
    assert (g.ngay_dang.gia_tri, g.ngay_dang.nguon) == ("20250101", v2.NGUON_UPLOAD_DATE)
    assert g.ngay_dang.hien_thi() == "January 1, 2025"             # ngày nguyên bản, không phải 02/01
    assert kq.bao_cao.bo_sung_ngay == (("bbbbbbbbbbb", "co_ngay"),)
    assert kq.status == "ok" and kq.loi_truy_cap is None


def test_kho_da_co_ngay_nguyen_ban_thi_khong_hoi(tmp_path, monkeypatch):
    meta = {_B: {**META[_B], "upload_date_raw": "20250101"}}
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, meta=meta)
    kq = e.scan_youtube(URL)
    assert _hoi_goc(hop) == []
    assert kq.bao_cao.doan[0].goc.ngay_dang.nguon == "clips_meta.upload_date_raw"


def test_dung_lai_trong_cung_mot_batch(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    ket = e.scan_many([URL, URL + "?x=2"])
    assert len(ket) == 2 and all(k.bao_cao.doan[0].goc.ngay_dang.gia_tri == "20250101"
                                 for k in ket)
    assert _hoi_goc(hop) == [URL_GOC_B], "mỗi mã video gốc chỉ hỏi một lần trong batch"


def test_dung_lai_trong_mot_luot_watch_nhieu_job(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    with e.mo_phien_youtube():
        a = e.scan_youtube(URL)
        b = e.scan_youtube(URL)
    assert _hoi_goc(hop) == [URL_GOC_B]
    assert a.bao_cao.doan[0].goc.ngay_dang == b.bao_cao.doan[0].goc.ngay_dang
    # Lượt Watch đã đóng: lượt sau là một lượt mới, không mang bộ nhớ cũ.
    e.scan_youtube(URL)
    assert len(_hoi_goc(hop)) == 2


def test_tran_so_lan_hoi(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    e.config.bo_sung_ngay_goc_toi_da = 0
    kq = e.scan_youtube(URL)
    assert _hoi_goc(hop) == []
    assert "hết lượt" in kq.bao_cao.doan[0].goc.ngay_dang.ly_do_thieu


def test_cau_dao_mo_thi_khong_gui_request(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    with e.mo_phien_youtube() as phien:
        phien.ghi_loi(RuntimeError("Sign in to confirm you're not a bot"), "metadata")
        assert phien.mo
        kq = e.scan_youtube(URL)
    assert _hoi_goc(hop) == []
    assert "chặn" in kq.bao_cao.doan[0].goc.ngay_dang.ly_do_thieu
    assert kq.matches and kq.status == "ok"


def test_da_bam_dung_thi_khong_hoi(tmp_path, monkeypatch):
    from engine import Engine

    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    goc = Engine._chuan_bi_goc_bao_cao

    def chuan_bi(self, kq, *, cho_bo_sung):
        # Bấm Dừng ngay SAU khi lượt quét xong, TRƯỚC lần hỏi bổ sung (chạy trên bản ghim).
        self.cancel_event.set()
        return goc(self, kq, cho_bo_sung=cho_bo_sung)

    monkeypatch.setattr(Engine, "_chuan_bi_goc_bao_cao", chuan_bi)
    kq = e.scan_youtube(URL)
    assert _hoi_goc(hop) == []
    assert "dừng" in kq.bao_cao.doan[0].goc.ngay_dang.ly_do_thieu
    assert kq.matches, "kết quả khớp giữ nguyên"


def test_video_goc_bi_go_van_giu_ket_qua_khop(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(
        tmp_path, monkeypatch,
        tra_goc=RuntimeError("ERROR: [youtube] bbbbbbbbbbb: Video unavailable. This video has "
                             "been removed by the uploader"))
    kq = e.scan_youtube(URL)
    g = kq.bao_cao.doan[0].goc
    assert kq.status == "ok" and kq.matches and kq.loi_truy_cap is None
    assert g.ngay_dang.gia_tri == "" and "không lấy được" in g.ngay_dang.ly_do_thieu
    assert g.url == URL_GOC_B                            # link gốc vẫn có


def test_youtube_tra_sai_ma_khong_nhan_ngay(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, tra_goc={**INFO_GOC_B, "id": "ccccccccccc"})
    kq = e.scan_youtube(URL)
    assert kq.bao_cao.doan[0].goc.ngay_dang.gia_tri == ""


def test_quet_file_khong_bao_gio_hoi_mang(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, nguon="file", tong_s=1800)
    media = tmp_path / "v.mp4"
    media.write_bytes(b"x")
    mt = hop["mt"]
    mt.thoi_luong[mt._khoa(str(media))] = 1800.0
    kq = e.scan_media(str(media))
    assert kq.matches
    assert hop["info"] == []
    assert kq.bao_cao.doan[0].goc.ngay_dang.gia_tri == ""


def test_khong_ghi_nguoc_vao_clips_meta(tmp_path, monkeypatch):
    """Ngày bổ sung chỉ nằm ở ảnh chụp; file metadata của kho giữ nguyên từng byte."""
    import json
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    duong = os.path.join(e.data_dir, "clips_meta.json")
    with open(duong, "w", encoding="utf-8") as f:
        json.dump(META, f, ensure_ascii=False)
    with open(duong, "rb") as f:
        truoc = f.read()
    del e.clip_metadata_resolver           # dùng resolver THẬT đọc file (kho mặc định cũ)
    kq = e.scan_youtube(URL)
    assert kq.bao_cao.doan[0].goc.ngay_dang.gia_tri == "20250101"
    assert kq.bao_cao.doan[0].goc.tieu_de == "Clip B gốc"
    with open(duong, "rb") as f:
        assert f.read() == truoc


def test_lo_nguon_chung_chi_hoi_mot_video_goc(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    with e.phien_job() as job:
        g = job.goc_bao_cao_v2(_B, cho_bo_sung=True)
        g2 = job.goc_bao_cao_v2(_B, cho_bo_sung=True)
    assert g.ngay_dang.gia_tri == "20250101" and g2 == g
    assert _hoi_goc(hop) == [URL_GOC_B]
    with e.phien_job() as job:
        job.config.bo_sung_ngay_goc = False
        assert job.goc_bao_cao_v2(_B, cho_bo_sung=True).ngay_dang.gia_tri == ""


def test_resolver_ambiguous_khong_hoi_va_khong_bia_url(tmp_path, monkeypatch):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    hop["resolver"] = ClipMetadataResolver.from_mapping({
        _B: {"id": "ccccccccccc", "url": "https://youtu.be/ddddddddddd"}})
    kq = e.scan_youtube(URL)
    g = kq.bao_cao.doan[0].goc
    assert _hoi_goc(hop) == [] and g.url == "" and g.video_id == ""


def test_chi_hoi_video_goc_duoc_chon_khong_hoi_ung_vien_khac(tmp_path, monkeypatch):
    """E đạt chuẩn nhưng không được chọn (Top-1 là B): không bao giờ hỏi ngày của E."""
    _E = "E [eeeeeeeeeee].opus"
    meta = {**META, _E: {"id": "eeeeeeeeeee", "title": "Clip E", "upload_date": "20250105",
                         "publication_date": "20250105", "publication_date_source": "timestamp",
                         "duration": 100.0, "url": "https://youtu.be/eeeeeeeeeee"}}
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300), Dat(_E, 1300, 100)],
                               meta=meta)
    e.config.bo_sung_ngay_goc = True
    e.config.ytdlp_sleep_requests_s = 0.0

    def youtube_info(url):
        hop["info"].append(url)
        if "bbbbbbbbbbb" in url:
            return dict(INFO_GOC_B)
        if "eeeeeeeeeee" in url:
            return {"id": "eeeeeeeeeee", "upload_date_raw": "20250104"}
        return dict(INFO)

    e.youtube_info = youtube_info
    kq = e.scan_youtube(URL)
    assert [m.clip for m in kq.matches] == [_B]
    assert {m.clip for m in kq.ung_vien_dat} == {_B, _E}
    assert [u for u in hop["info"] if "eeeeeeeeeee" in u] == []
    assert _hoi_goc(hop) == [URL_GOC_B]


# ---------------------------------------------------------------------------
#  D-58: có khoá YouTube Data API → bổ sung TỰ BẬT, một yêu cầu cho cả lô (tests/youtube_api_gia.py, khoá GIẢ)
# ---------------------------------------------------------------------------

def _metas_goc(n):
    """``{clip: meta}`` cho n video gốc chỉ có ngày ĐÃ quy đổi (như kho cũ) — mã ``g0000000000``…"""
    ma = [f"g{i:010d}" for i in range(n)]
    tho = {f"G{i} [{m}].opus": {**META[_B], "id": m, "url": f"https://youtu.be/{m}"} for i, m in enumerate(ma)}
    r = ClipMetadataResolver.from_mapping(tho)
    return ma, {clip: r.resolve(clip) for clip in tho}


def test_co_khoa_tat_tuy_chon_van_bo_sung_qua_api_mot_yeu_cau(tmp_path, monkeypatch, api_youtube_gia):
    import youtube_api_gia as gia
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=False)
    api_youtube_gia.video["bbbbbbbbbbb"] = gia.video_gia("bbbbbbbbbbb", published_at="2025-01-01T20:00:00Z")
    kq = e.scan_youtube(URL)
    g = kq.bao_cao.doan[0].goc
    assert api_youtube_gia.dem() == 1 and api_youtube_gia.yeu_cau[0].ids == ("bbbbbbbbbbb",)
    assert _hoi_goc(hop) == [], "API trả lời thì không hỏi yt-dlp"
    assert (g.ngay_dang.gia_tri, g.ngay_dang.nguon) == ("20250101", v2.NGUON_PUBLISHED_AT)
    assert g.ngay_dang.hien_thi() == "January 1, 2025"            # ngày lịch UTC, không đổi giờ VN
    assert kq.bao_cao.bo_sung_ngay == (("bbbbbbbbbbb", "co_ngay"),)
    assert kq.status == "ok" and kq.matches


def test_co_khoa_50_video_goc_mot_yeu_cau_khong_gian_nhip(tmp_path, monkeypatch, api_youtube_gia):
    import youtube_api_gia as gia
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=False)
    e.config.ytdlp_sleep_requests_s = 30.0          # giãn nhịp chỉ cho yt-dlp — có ngủ thì test treo
    ma, metas = _metas_goc(50)
    for m in ma:
        api_youtube_gia.video[m] = gia.video_gia(m, published_at="2024-03-05T01:02:03Z")
    with e.phien_job() as job:
        ket = job._bo_sung_ngay_goc(metas, cho_phep=True, nhat_ky=[])
        lai = job._bo_sung_ngay_goc(metas, cho_phep=True, nhat_ky=[])   # cùng job: nhớ, không hỏi lại
        assert job._bo_nho_ngay_goc.so_lan_hoi == 0, "trần 20 chỉ đếm lượt hỏi yt-dlp"
    assert api_youtube_gia.dem() == 1 and len(api_youtube_gia.yeu_cau[0].ids) == 50
    assert hop["info"] == []
    assert len(ket) == 50 and lai == ket
    assert {(n.gia_tri, n.nguon) for n in ket.values()} == {("20240305", v2.NGUON_PUBLISHED_AT)}


def test_khong_khoa_tat_tuy_chon_khong_gui_yeu_cau_nao(tmp_path, monkeypatch):
    import youtube_api_gia as gia
    tp = gia.lap_transport(monkeypatch)
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=False)
    kq = e.scan_youtube(URL)
    assert tp.dem() == 0 and _hoi_goc(hop) == []
    assert "đã quy đổi" in kq.bao_cao.doan[0].goc.ngay_dang.ly_do_thieu


def test_khoa_sai_dang_giu_nguyen_nhu_khong_khoa(tmp_path, monkeypatch):
    import youtube_api
    import youtube_api_gia as gia
    tp = gia.lap_transport(monkeypatch)

    def sai(data_dir):
        raise youtube_api.LoiKhoaApi("khoá giả sai dạng")

    monkeypatch.setattr(youtube_api, "_doc_khoa_cho", sai)
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=False)
    kq = e.scan_youtube(URL)
    assert tp.dem() == 0 and _hoi_goc(hop) == []
    assert kq.bao_cao.bo_sung_ngay == ()
    e2, hop2 = _the_gioi_bo_sung(tmp_path / "b", monkeypatch, bat=True)
    e2.scan_youtube(URL)
    assert tp.dem() == 0 and _hoi_goc(hop2) == [URL_GOC_B], "bật tuỳ chọn: đường yt-dlp như hôm nay"


def test_khong_khoa_bat_tuy_chon_van_duong_ytdlp_va_tran(tmp_path, monkeypatch):
    import youtube_api_gia as gia
    tp = gia.lap_transport(monkeypatch)
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch)
    e.config.ytdlp_sleep_requests_s = 0.0
    ma, metas = _metas_goc(3)
    e.config.bo_sung_ngay_goc_toi_da = 2
    with e.phien_job() as job:
        ket = job._bo_sung_ngay_goc(metas, cho_phep=True, nhat_ky=[])
    assert tp.dem() == 0
    assert len(hop["info"]) == 2, "trần 20 (ở đây 2) vẫn áp cho yt-dlp"
    assert sum("hết lượt" in n.ly_do_thieu for n in ket.values()) == 1


def test_co_khoa_het_han_muc_tat_tuy_chon_khong_lui_ytdlp(tmp_path, monkeypatch, api_youtube_gia):
    import youtube_api_gia as gia
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=False)
    api_youtube_gia.video["bbbbbbbbbbb"] = gia.video_gia("bbbbbbbbbbb")
    api_youtube_gia.kich_ban = [gia.QUOTA]
    kq = e.scan_youtube(URL)
    g = kq.bao_cao.doan[0].goc
    assert api_youtube_gia.dem() == 1 and _hoi_goc(hop) == []
    assert g.ngay_dang.gia_tri == "" and "đã quy đổi" in g.ngay_dang.ly_do_thieu
    assert kq.status == "ok" and kq.matches and kq.loi_truy_cap is None


def test_co_khoa_het_han_muc_bat_tuy_chon_lui_ytdlp(tmp_path, monkeypatch, api_youtube_gia):
    import youtube_api_gia as gia
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=True)
    api_youtube_gia.kich_ban = [gia.QUOTA]
    kq = e.scan_youtube(URL)
    g = kq.bao_cao.doan[0].goc
    assert api_youtube_gia.dem() == 1 and _hoi_goc(hop) == [URL_GOC_B]
    assert (g.ngay_dang.gia_tri, g.ngay_dang.nguon) == ("20250101", v2.NGUON_UPLOAD_DATE)


def test_co_khoa_video_vang_bat_tuy_chon_lui_ytdlp_co_tran(tmp_path, monkeypatch, api_youtube_gia):
    """Mã vắng trong phản hồi (riêng tư / đã gỡ) đi đường yt-dlp cũ — vẫn trần + bộ nhớ."""
    import youtube_api_gia as gia
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=True)
    ma, metas = _metas_goc(3)
    api_youtube_gia.video[ma[0]] = gia.video_gia(ma[0], published_at="2024-03-05T01:02:03Z")
    e.config.bo_sung_ngay_goc_toi_da = 1
    with e.phien_job() as job:
        ket = job._bo_sung_ngay_goc(metas, cho_phep=True, nhat_ky=[])
    assert api_youtube_gia.dem() == 1
    assert len(hop["info"]) == 1
    nguon = sorted(n.nguon or n.ly_do_thieu[:13] for n in ket.values())
    assert v2.NGUON_PUBLISHED_AT in nguon and any("hết lượt" in n.ly_do_thieu for n in ket.values())


def test_co_khoa_cau_dao_mo_khong_gui_gi(tmp_path, monkeypatch, api_youtube_gia):
    import youtube_api_gia as gia
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=False)
    api_youtube_gia.video["bbbbbbbbbbb"] = gia.video_gia("bbbbbbbbbbb")
    with e.mo_phien_youtube() as phien:
        phien.ghi_loi(RuntimeError("Sign in to confirm you're not a bot"), "metadata")
        kq = e.scan_youtube(URL)
    assert api_youtube_gia.dem() == 0 and _hoi_goc(hop) == []
    assert kq.matches and kq.status == "ok"


def test_quet_file_co_khoa_khong_hoi_api(tmp_path, monkeypatch, api_youtube_gia):
    e, hop = _the_gioi_bo_sung(tmp_path, monkeypatch, bat=False, nguon="file", tong_s=1800)
    media = tmp_path / "v.mp4"
    media.write_bytes(b"x")
    mt = hop["mt"]
    mt.thoi_luong[mt._khoa(str(media))] = 1800.0
    kq = e.scan_media(str(media))
    assert kq.matches and api_youtube_gia.dem() == 0
