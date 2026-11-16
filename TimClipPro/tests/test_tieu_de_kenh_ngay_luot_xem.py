# -*- coding: utf-8 -*-
"""Tab «📝 Tiêu đề kênh» + YouTube Data API (D-38 + D-51): có khoá → thêm «Ngày đăng», «Lượt xem» bằng ``videos.list``
(50 video một yêu cầu, không thêm lượt yt-dlp nào); không khoá → bảng / CSV / TXT y như trước. Không mạng: lượt liệt kê
giả, API giả (``tests/youtube_api_gia.py``)."""

from __future__ import annotations

import csv
import io

import pytest
import yt_dlp

import channel
import tai_video_goc as tv
import truy_cap_youtube as tc
import youtube_api as ya
from youtube_api_gia import KEY_INVALID, QUOTA, SERVER, TIMEOUT, lap_transport, video_gia

URL_KENH = "https://www.youtube.com/@Kenh"
_DS = [("abcdefghij1", 'Tập 1: Mở đầu, "có nháy"', 3725.9), ("abcdefghij2", "=Live", 0.0)]

# Đầu ra của csv_tieu_de / txt_tieu_de TRƯỚC thay đổi này (91e2da6) cho _DS: không khoá phải giữ nguyên từng byte.
CSV_HOM_NAY = ("﻿STT,Tiêu đề,Link,Thời lượng\r\n"
               '1,"Tập 1: Mở đầu, ""có nháy""",https://www.youtube.com/watch?v=abcdefghij1,01:02:05\r\n'
               "2,'=Live,https://www.youtube.com/watch?v=abcdefghij2,\r\n").encode("utf-8")
TXT_HOM_NAY = 'Tập 1: Mở đầu, "có nháy"\r\n=Live\r\n'.encode("utf-8")
COT_DU = ["STT", "Tiêu đề", "Link", "Thời lượng", "Ngày đăng", "Lượt xem"]


def _phien():
    return tc.PhienYouTube(ham_cho=lambda giay, ev=None: False)


def _kenh_gia(monkeypatch, ds):
    """``ChannelSync.list_channel`` giả: MỘT lượt liệt kê, đếm vào phiên như bản thật."""

    def liet_ke(url, limit=None, **kw):
        kw["phien_youtube"].dem_yeu_cau("listing")
        return [channel.VideoInfo(id=m, title=t, upload_date="", duration=d, url="") for m, t, d in ds]

    monkeypatch.setattr(channel.ChannelSync, "list_channel", staticmethod(liet_ke))


def _video_api(ma, published_at="2026-07-31T20:00:34Z", luot_xem="1234"):
    """Mục ``items`` của ``videos.list`` kèm ``statistics``; ``luot_xem=None`` = YouTube không trả lượt xem (ẩn)."""
    muc = video_gia(ma, published_at=published_at)
    muc["statistics"] = {} if luot_xem is None else {"viewCount": luot_xem}
    return muc


def _bang_csv(dong):
    raw = tv.csv_tieu_de(dong)
    assert raw.startswith(b"\xef\xbb\xbf")                     # BOM: Excel đọc đúng tiếng Việt
    return list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))


# ---------------------------------------------------------------- youtube_api.lay_ngay_luot_xem

def test_lay_ngay_luot_xem_theo_lo_50_part_snippet_statistics(api_youtube_gia, tmp_path):
    ids = [f"vid{i:08d}" for i in range(120)]
    for i, m in enumerate(ids):
        api_youtube_gia.video[m] = _video_api(m, luot_xem=str(i))
    api_youtube_gia.video[ids[1]] = _video_api(ids[1], luot_xem=None)
    api_youtube_gia.video[ids[2]] = _video_api(ids[2], luot_xem="abc")
    api_youtube_gia.video[ids[3]] = _video_api(ids[3], luot_xem="9" * 400)
    del api_youtube_gia.video[ids[4]]                                     # riêng tư / đã gỡ: API không trả
    phien = _phien()
    ket, ly_do = ya.lay_ngay_luot_xem(phien, str(tmp_path / "data"), ids + ids[:5] + ["sai,ma"])
    yc = api_youtube_gia.yeu_cau
    assert [len(y.ids) for y in yc] == [50, 50, 20] and [m for y in yc for m in y.ids] == ids
    assert all(y.endpoint == "videos" and y.key_in_header and y.part == "snippet,statistics"
               and y.params["fields"] == "items(id,snippet(publishedAt),statistics(viewCount))" for y in yc)
    assert ly_do == "" and list(ket) == [m for m in ids if m != ids[4]]
    assert ket[ids[0]] == {"published_at": "2026-07-31T20:00:34Z", "view_count": 0}
    assert ket[ids[119]]["view_count"] == 119
    assert [ket[m]["view_count"] for m in ids[1:4]] == [None, None, None]   # ẩn / lạ → trống, không bao giờ 0
    so = phien.tom_tat()
    assert (so["api"]["yeu_cau"], so["api"]["don_vi"], so["api"]["video_api"], so["api"]["video_lui"],
            so["api"]["tat"]) == (3, 3, 119, 0, False), "không có đường lùi yt-dlp: không đếm «video lùi»"
    assert (so["listing_requests"], so["metadata_requests"], so["download_attempts"], so["breaker_open"]) == (
        0, 0, 0, False)


def test_lay_ngay_luot_xem_khong_co_khoa_khong_gui(monkeypatch, tmp_path):
    tp = lap_transport(monkeypatch)
    assert ya.lay_ngay_luot_xem(_phien(), str(tmp_path / "data"), ["abcdefghij1"]) == ({}, ya.LY_DO_CHUA_CO_KHOA)
    assert tp.dem() == 0


def test_lay_ngay_luot_xem_het_han_muc_giu_lo_da_lay(api_youtube_gia, tmp_path):
    ids = [f"vid{i:08d}" for i in range(120)]
    for m in ids:
        api_youtube_gia.video[m] = _video_api(m)
    api_youtube_gia.kich_ban = [None, QUOTA]
    phien = _phien()
    ket, ly_do = ya.lay_ngay_luot_xem(phien, str(tmp_path / "data"), ids)
    assert list(ket) == ids[:50] and ly_do == tc.THONG_BAO_API[tc.API_HET_HAN_MUC]
    assert api_youtube_gia.dem() == 2 and phien.api.tat, "đã tắt tới hết lượt: lô thứ ba không gửi"
    assert not phien.mo, "lỗi API không chạm cầu dao yt-dlp"


def test_lay_ngay_luot_xem_loi_tam_thoi_mot_lo_cac_lo_khac_van_chay(api_youtube_gia, tmp_path):
    ids = [f"vid{i:08d}" for i in range(120)]
    for m in ids:
        api_youtube_gia.video[m] = _video_api(m)
    api_youtube_gia.kich_ban = [SERVER, SERVER]                           # lô 1 hỏng cả lần thử lại
    phien = _phien()
    ket, ly_do = ya.lay_ngay_luot_xem(phien, str(tmp_path / "data"), ids)
    assert list(ket) == ids[50:] and ly_do == ya.LY_DO_TAM_THOI
    assert api_youtube_gia.dem() == 4 and not phien.api.tat


def test_lay_ngay_luot_xem_ma_la_trong_items_bi_bo_qua(api_youtube_gia, tmp_path):
    api_youtube_gia.kich_ban = [{"items": [{"id": "zzzzzzzzzzz"},           # mã không hỏi: bỏ qua, không xét dạng
                                           {"id": "abcdefghij1", "snippet": {"publishedAt": "2026-01-02T03:04:05Z"},
                                            "statistics": {"viewCount": "7"}}]}]
    phien = _phien()
    assert ya.lay_ngay_luot_xem(phien, str(tmp_path / "data"), ["abcdefghij1"]) == (
        {"abcdefghij1": {"published_at": "2026-01-02T03:04:05Z", "view_count": 7}}, "")
    assert not phien.api.tat


@pytest.mark.parametrize("than", [{"items": "x"}, {"items": [{"id": "abcdefghij1", "snippet": {}}]},
                                  {"items": [{"id": "abcdefghij1", "snippet": {"publishedAt": "x"},
                                              "statistics": "x"}]},
                                  {"items": [{"snippet": {"publishedAt": "x"}}]}])
def test_lay_ngay_luot_xem_phan_hoi_sai_dang_tat_api(api_youtube_gia, tmp_path, than):
    api_youtube_gia.kich_ban = [than]
    phien = _phien()
    assert ya.lay_ngay_luot_xem(phien, str(tmp_path / "data"), ["abcdefghij1"]) == (
        {}, tc.THONG_BAO_API[tc.API_PHAN_HOI_LA])
    assert phien.api.loai_tat == tc.API_PHAN_HOI_LA


# ---------------------------------------------------------------- tai_video_goc.tieu_de_kenh / csv / txt

def test_co_khoa_them_ngay_dang_luot_xem_khong_them_luot_yt_dlp(api_youtube_gia, tmp_path, monkeypatch):
    ds = [(f"v{i:010d}", f"Tập {i}", 60.0) for i in range(120)]
    _kenh_gia(monkeypatch, ds)

    def cam(*a, **k):
        raise AssertionError("ngoài lượt liệt kê không được gọi yt-dlp")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", cam)
    for i, (m, _t, _d) in enumerate(ds):
        api_youtube_gia.video[m] = _video_api(m, luot_xem=str(i * 1000))
    m0, m1, m2 = ds[0][0], ds[1][0], ds[2][0]
    # 17:00 UTC: giờ VN đã là 02/07 — ngày đăng là ngày lịch UTC của publishedAt (D-51), định dạng D-30.
    api_youtube_gia.video[m0] = _video_api(m0, published_at="2024-07-01T17:00:00Z", luot_xem="1234567")
    api_youtube_gia.video[m1] = _video_api(m1, luot_xem=None)
    del api_youtube_gia.video[m2]
    phien = _phien()
    dong, ly_do = tv.tieu_de_kenh(URL_KENH, phien=phien, data_dir=str(tmp_path / "data"))
    assert ly_do == "" and len(dong) == 120
    assert [len(y.ids) for y in api_youtube_gia.yeu_cau] == [50, 50, 20], "ceil(120/50) yêu cầu API"
    so = phien.tom_tat()
    assert (so["listing_requests"], so["metadata_requests"], so["download_attempts"]) == (1, 0, 0)
    assert dong[0] == {"STT": 1, "Tiêu đề": "Tập 0", "Link": "https://www.youtube.com/watch?v=" + m0,
                       "Thời lượng": "00:01:00", "Ngày đăng": "July 1, 2024", "Lượt xem": 1234567}
    assert [list(d) for d in dong] == [COT_DU] * 120
    assert (dong[1]["Ngày đăng"], dong[1]["Lượt xem"]) == ("July 31, 2026", None)
    assert (dong[2]["Ngày đăng"], dong[2]["Lượt xem"]) == ("", None)
    assert dong[3]["Lượt xem"] == 3000
    bang = _bang_csv(dong)
    assert bang[0] == COT_DU
    assert [r[4:] for r in bang[1:5]] == [["July 1, 2024", "1234567"], ["July 31, 2026", ""], ["", ""],
                                          ["July 31, 2026", "3000"]]
    assert tv.txt_tieu_de(dong) == "".join(f"Tập {i}\r\n" for i in range(120)).encode("utf-8")


def test_khong_khoa_bang_csv_txt_giu_nguyen_tung_byte(monkeypatch, tmp_path):
    tp = lap_transport(monkeypatch)
    _kenh_gia(monkeypatch, _DS)
    dong, ly_do = tv.tieu_de_kenh(URL_KENH, phien=_phien(), data_dir=str(tmp_path / "data"))
    assert ly_do == "" and tp.dem() == 0
    assert [list(d) for d in dong] == [list(tv.COT_TIEU_DE)] * 2
    assert tv.csv_tieu_de(dong) == CSV_HOM_NAY and tv.txt_tieu_de(dong) == TXT_HOM_NAY
    assert tv.tieu_de_kenh(URL_KENH) == (dong, "") and tp.dem() == 0


@pytest.mark.parametrize("kich_ban, ly_do", [
    ([QUOTA], tc.THONG_BAO_API[tc.API_HET_HAN_MUC]),
    ([KEY_INVALID], tc.THONG_BAO_API[tc.API_KHOA_HONG]),
    ([SERVER, TIMEOUT], ya.LY_DO_TAM_THOI),
])
def test_api_hong_hai_cot_trong_kem_ly_do_danh_sach_van_con(api_youtube_gia, tmp_path, monkeypatch, kich_ban, ly_do):
    _kenh_gia(monkeypatch, _DS)
    for m, _t, _d in _DS:
        api_youtube_gia.video[m] = _video_api(m)
    api_youtube_gia.kich_ban = list(kich_ban)
    dong, ly = tv.tieu_de_kenh(URL_KENH, phien=_phien(), data_dir=str(tmp_path / "data"))
    assert ly == tv.ly_do_cot_api(ly_do) and tc._LUOT_NAY_YT_DLP not in ly
    assert [(d["Tiêu đề"], d["Ngày đăng"], d["Lượt xem"]) for d in dong] == [(t, "", None) for _m, t, _d in _DS]
    bang = _bang_csv(dong)
    assert bang[0] == COT_DU and [r[4:] for r in bang[1:]] == [["", ""], ["", ""]]


def test_khoa_sai_dang_hai_cot_trong_noi_ro_khong_gui(monkeypatch, tmp_path):
    tp = lap_transport(monkeypatch)
    _kenh_gia(monkeypatch, _DS)

    def sai_dang(data_dir):
        raise ya.LoiKhoaApi(f"File {ya.TEN_FILE_KHOA} có nhiều hơn một dòng khoá — chỉ để đúng một dòng.")

    monkeypatch.setattr(ya, "_doc_khoa_cho", sai_dang)
    dong, ly_do = tv.tieu_de_kenh(URL_KENH, phien=_phien(), data_dir=str(tmp_path / "data"))
    assert ly_do.startswith(ya.LY_DO_SAI_KHOA) and "nhiều hơn một dòng" in ly_do and tp.dem() == 0
    assert [(d["Ngày đăng"], d["Lượt xem"]) for d in dong] == [("", None)] * 2


def test_csv_chan_cong_thuc_ca_o_hai_cot_moi():
    dong = [{"STT": 1, "Tiêu đề": "a", "Link": "l", "Thời lượng": "", "Ngày đăng": "=1+1", "Lượt xem": "@SUM(A1)"},
            {"STT": 2, "Tiêu đề": "b", "Link": "l", "Thời lượng": "", "Ngày đăng": "", "Lượt xem": None}]
    assert _bang_csv(dong) == [COT_DU, ["1", "a", "l", "", "'=1+1", "'@SUM(A1)"], ["2", "b", "l", "", "", ""]]


# ---------------------------------------------------------------- giao diện (AppTest)

def test_tab_co_khoa_hien_hai_cot_api_hong_thi_canh_bao(api_youtube_gia, tmp_path, monkeypatch):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    _kenh_gia(monkeypatch, _DS)
    for m, _t, _d in _DS:
        api_youtube_gia.video[m] = _video_api(m, luot_xem="42")

    def bang(at):
        return next(d.value for d in at.dataframe if "Thời lượng" in d.value.columns)

    def canh_bao(at):
        return [w.value for w in at.warning if "Ngày đăng" in w.value]

    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    next(t for t in at.text_input if t.label == "Link kênh YouTube cần lấy tiêu đề").input(URL_KENH).run()
    at.button(key="lay_tieu_de").click().run()
    assert not at.exception and canh_bao(at) == []
    df = bang(at)
    assert list(df.columns) == COT_DU and list(df["Ngày đăng"]) == ["July 31, 2026"] * 2
    assert list(df["Lượt xem"]) == [42, 42]
    assert not any(ya.TEN_FILE_KHOA in c.value for c in at.caption), "có khoá: không nhắc đặt khoá"
    assert api_youtube_gia.dem() == 1

    api_youtube_gia.kich_ban = [QUOTA]
    at.button(key="lay_tieu_de").click().run()
    assert not at.exception
    cb = canh_bao(at)
    assert len(cb) == 1 and tv.ly_do_cot_api(tc.THONG_BAO_API[tc.API_HET_HAN_MUC]) in cb[0]
    assert tc._LUOT_NAY_YT_DLP not in cb[0]
    df = bang(at)
    assert list(df.columns) == COT_DU and list(df["Tiêu đề"]) == [t for _m, t, _d in _DS]
    assert list(df["Ngày đăng"]) == ["", ""] and df["Lượt xem"].isna().all()
    assert sorted(e.label for e in at.get("download_button")) == [
        "⬇️ Tải file CSV (mở bằng Excel)", "⬇️ Tải file TXT (chỉ tiêu đề)"]


def test_ly_do_loi_api_khong_noi_lay_bang_yt_dlp(api_youtube_gia):
    """Review P3 16/11: câu chung của lõi («Lượt này lấy thông tin video bằng yt-dlp như cũ») sai với tab này."""
    import truy_cap_youtube
    import tai_video_goc

    assert truy_cap_youtube._LUOT_NAY_YT_DLP not in tai_video_goc.ly_do_cot_api(
        truy_cap_youtube.THONG_BAO_API[truy_cap_youtube.API_HET_HAN_MUC])
    assert tai_video_goc.ly_do_cot_api(truy_cap_youtube.THONG_BAO_API[truy_cap_youtube.API_HET_HAN_MUC])
