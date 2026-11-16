# -*- coding: utf-8 -*-
"""Tìm video nghi vấn theo tiêu đề clip gốc (D-51, docs/YOUTUBE_DATA_API.md, nhánh tim-video-nghi-van):
``youtube_api.tim_video`` (``search.list``, hạn mức RIÊNG 100 lượt/ngày, 1 lượt mỗi lần gọi) + ``tim_nghi_van``. Tab giao
diện: tests/test_tim_nghi_van_app.py. Không mạng thật: transport giả ``tests/youtube_api_gia.py`` (mặc định mọi test
«chưa có khoá»)."""

import datetime
import inspect
import json
import os
import unicodedata

import pytest

import tim_nghi_van as tn
import truy_cap_youtube as t
import youtube_api as ya
import youtube_api_gia as gia

KENH_KHAC = "UC" + "kenhKhac" + "0" * 14  # mã kênh 24 ký tự, khác kênh gốc gia.KENH_GIA


def _phien():
    return t.PhienYouTube(ham_cho=lambda giay, ev=None: False)


def _ma(i):
    return f"vid{i:08d}"


def _muc(ma, title="", kenh=KENH_KHAC, ten_kenh="Kênh lạ", published_at="2026-08-01T03:00:00Z"):
    """Một mục ``items`` của ``search.list`` (type=video)."""
    return {"kind": "youtube#searchResult", "id": {"kind": "youtube#video", "videoId": ma},
            "snippet": {"publishedAt": published_at, "channelId": kenh, "title": title or f"Tổng hợp {ma}",
                        "channelTitle": ten_kenh, "liveBroadcastContent": "none"}}


def _tim(*muc):
    return {"items": list(muc)}


def _khong_nhac_yt_dlp(ghi_chu):
    """Tính năng này không có đường yt-dlp nào: lý do hiện ra không được hứa «lấy bằng yt-dlp như cũ»."""
    assert all("yt-dlp" not in g for g in ghi_chu), ghi_chu


# ---------------------------------------------------------------- youtube_api.tim_video (search.list)

def test_tim_video_search_list_dung_tham_so_moi_lan_goi_mot_luot(api_youtube_gia, tmp_path):
    api_youtube_gia.kich_ban = [_tim(_muc(_ma(1), title="Jeffy &amp; Friends &#39;10 giờ&#39;",
                                          ten_kenh="A &quot;B&quot;"))]
    phien = _phien()
    data = str(tmp_path / "data")
    ds, ly_do = ya.tim_video(phien, data, "SML Movie: Jeffy's Bad Word!")
    # search.list trả tiêu đề / tên kênh đã mã hoá HTML — giải mã như videos.list.
    assert ly_do == "" and ds == [{"id": _ma(1), "title": "Jeffy & Friends '10 giờ'", "channel": 'A "B"',
                                   "channel_id": KENH_KHAC, "published_at": "2026-08-01T03:00:00Z"}]
    yc = api_youtube_gia.yeu_cau
    assert len(yc) == 1 and yc[0].endpoint == "search" and yc[0].key_in_header
    assert gia.KHOA_GIA not in yc[0].url
    p = yc[0].params
    assert {k: p.get(k) for k in ("part", "type", "q", "maxResults", "videoDuration", "order")} == {
        "part": "snippet", "type": "video", "q": "SML Movie: Jeffy's Bad Word!", "maxResults": "50",
        "videoDuration": "long", "order": "relevance"}
    assert "publishedAfter" not in p and p["fields"].startswith("items(")
    so = phien.tom_tat()["api"]
    assert (so["yeu_cau"], so["don_vi"], so["tat"]) == (1, 1, False), "search.list: 1 lượt trong hạn mức riêng"

    ya.tim_video(phien, data, "x", thoi_luong="medium", sau="2026-01-01T00:00:00Z")
    p = api_youtube_gia.yeu_cau[1].params
    assert (p["videoDuration"], p["publishedAfter"]) == ("medium", "2026-01-01T00:00:00Z")


def test_tim_video_khong_co_ket_qua(api_youtube_gia, tmp_path):
    """Có ``fields=items(...)`` mà không khớp gì, Google bỏ hẳn khoá ``items``: đó là 0 kết quả, không phải lỗi."""
    api_youtube_gia.kich_ban = [{}]
    phien = _phien()
    assert ya.tim_video(phien, str(tmp_path / "data"), "q") == ([], "") and not phien.api.tat


@pytest.mark.parametrize("than", [
    {"items": {}},
    {"items": [{"id": {"videoId": "ngan"}, "snippet": _muc(_ma(1))["snippet"]}]},
    {"items": [{"id": {"kind": "youtube#channel", "channelId": KENH_KHAC}, "snippet": _muc(_ma(1))["snippet"]}]},
    {"items": [{"id": {"videoId": _ma(1)}, "snippet": {"title": "x"}}]},
    {"items": ["chuoi"]},
])
def test_tim_video_phan_hoi_sai_dang_tat_tim_kiem_toi_het_luot(api_youtube_gia, tmp_path, than):
    api_youtube_gia.kich_ban = [than]
    phien = _phien()
    data = str(tmp_path / "data")
    assert ya.tim_video(phien, data, "q") == ([], t.THONG_BAO_API[t.API_PHAN_HOI_LA])
    assert phien.api.loai_tat == t.API_PHAN_HOI_LA
    assert ya.tim_video(phien, data, "q2")[0] == [] and api_youtube_gia.dem() == 1


# ---------------------------------------------------------------- truy vấn từ tiêu đề clip

def test_tao_truy_van_bo_ma_cua_clip_emoji_va_trung_giu_thu_tu():
    nfd = unicodedata.normalize("NFD", "Tiếng Việt có dấu")
    clips = [
        tn.ClipKho("a.opus", "🔥 SML Movie: Jeffy's Bad Word! 😂😂 [abcdefghijk]", "abcdefghijk"),
        tn.ClipKho("b.opus", "sml movie: jeffy's   bad word!", "bcdefghijkl"),       # trùng sau làm sạch
        tn.ClipKho("c.opus", "Funny Moments [Compilation]", "cdefghijklm"),         # 11 chữ KHÔNG phải mã của clip
        tn.ClipKho("d.opus", "😂🔥 ❤️", "defghijklmn"),                               # chỉ có emoji: bỏ
        tn.ClipKho("e.opus", "Cười ❤️ 👍🏽 1️⃣ 🇻🇳 " + nfd, "efghijklmno"),               # dấu tiếng Việt (NFD) giữ nguyên
    ]
    them = "  SML compilation 10 hours \n\n#SML\nsml COMPILATION 10 hours\nFunny moments [compilation]"
    assert tn.tao_truy_van(clips, them) == [
        "SML compilation 10 hours", "#SML", "Funny moments [compilation]",
        "SML Movie: Jeffy's Bad Word!", "Cười 1 " + nfd]
    assert tn.tao_truy_van([], "") == [] and tn.tao_truy_van(clips[3:4]) == []


# ---------------------------------------------------------------- tìm, gộp, loại kênh gốc, xếp hạng

def test_tim_gop_theo_ma_bo_kenh_goc_xep_theo_so_truy_van_roi_thoi_luong(api_youtube_gia, tmp_path):
    a, b, c, d, cua_toi = (_ma(i) for i in range(1, 6))
    api_youtube_gia.kich_ban = [
        _tim(_muc(a), _muc(cua_toi, kenh=gia.KENH_GIA), _muc(b)),
        _tim(_muc(b), _muc(c), _muc(b)),                  # b lặp trong CÙNG một phản hồi: vẫn là một truy vấn
        _tim(_muc(c), _muc(d, title="Tên &amp; lạ"), _muc(cua_toi, kenh=gia.KENH_GIA)),
    ]
    for m, dai in ((a, "PT3H"), (b, "PT1H"), (c, "PT10H"), (d, "PT25M")):
        api_youtube_gia.video[m] = gia.video_gia(m, title=f"Tiêu đề {m}", duration=dai, ten_kenh="Kênh vi phạm",
                                                 published_at="2026-07-31T20:00:34Z")
    phien, phien_tim = _phien(), _phien()
    kq = tn.tim(phien, str(tmp_path / "data"), ["q1", "q2", "q3"], phien_tim=phien_tim,
                kenh_goc=frozenset({gia.KENH_GIA}))
    # c: 2 truy vấn, 10 giờ; b: 2 truy vấn, 1 giờ; a: 1 truy vấn, 3 giờ; d: 1 truy vấn, 25 phút.
    assert [(v["id"], v["khop"], v["duration"]) for v in kq.video] == [
        (c, 2, 36000), (b, 2, 3600), (a, 1, 10800), (d, 1, 1500)]
    assert kq.video[0] == {"id": c, "title": f"Tiêu đề {c}", "channel": "Kênh vi phạm", "duration": 36000,
                           "published_at": "2026-07-31T20:00:34Z", "khop": 2}
    assert (kq.da_tim, kq.tong, kq.luot_tim, kq.bo_kenh_goc, kq.ghi_chu) == (3, 3, 3, 1, ())
    yc = api_youtube_gia.yeu_cau
    assert [y.endpoint for y in yc] == ["search"] * 3 + ["videos"]
    assert [y.params["q"] for y in yc[:3]] == ["q1", "q2", "q3"]
    assert yc[3].ids == (a, b, c, d), "video của kênh gốc không hỏi thêm; thứ tự gặp đầu"
    assert phien_tim.tom_tat()["api"]["yeu_cau"] == 3 and phien.tom_tat()["api"]["yeu_cau"] == 1


def test_video_khong_lay_duoc_thoi_luong_van_hien_bang_du_lieu_tim_kiem(api_youtube_gia, tmp_path):
    a, b = _ma(1), _ma(2)
    api_youtube_gia.kich_ban = [_tim(_muc(a, title="Ph&#7847;n 1"), _muc(b))]
    api_youtube_gia.video[b] = gia.video_gia(b, duration="PT5H")
    kq = tn.tim(_phien(), str(tmp_path / "data"), ["q"], phien_tim=_phien())
    assert [v["id"] for v in kq.video] == [b, a], "thời lượng chưa biết (0) xếp sau trong cùng số truy vấn"
    assert kq.video[1] == {"id": a, "title": "Phần 1", "channel": "Kênh lạ", "duration": 0,
                           "published_at": "2026-08-01T03:00:00Z", "khop": 1}
    assert len(kq.ghi_chu) == 1 and kq.ghi_chu[0].startswith("1 video chưa lấy được thời lượng — ")
    assert ya.LY_DO_VANG in kq.ghi_chu[0]


def test_het_han_muc_tim_kiem_giua_chung_tra_ket_qua_mot_phan_va_ly_do(api_youtube_gia, tmp_path):
    a = _ma(1)
    api_youtube_gia.kich_ban = [_tim(_muc(a)), gia.QUOTA]
    api_youtube_gia.video[a] = gia.video_gia(a, duration="PT4H")
    phien, phien_tim = _phien(), _phien()
    kq = tn.tim(phien, str(tmp_path / "data"), ["q1", "q2", "q3", "q4"], phien_tim=phien_tim)
    assert [v["id"] for v in kq.video] == [a] and kq.video[0]["duration"] == 14400
    assert (kq.da_tim, kq.tong, kq.luot_tim) == (1, 4, 2)
    assert [y.endpoint for y in api_youtube_gia.yeu_cau] == ["search", "search", "videos"], (
        "đã hết hạn mức tìm kiếm: không gửi thêm truy vấn nào; videos.list (hạn mức khác) vẫn chạy")
    assert phien_tim.api.loai_tat == t.API_HET_HAN_MUC and not phien.api.tat
    assert kq.ghi_chu == ("Chỉ tìm được 1/4 truy vấn — " + tn.HET_HAN_MUC_TIM,)
    assert "100 lượt" in tn.HET_HAN_MUC_TIM and "Thái Bình Dương" in tn.HET_HAN_MUC_TIM
    _khong_nhac_yt_dlp(kq.ghi_chu)


def test_videos_list_het_han_muc_khong_tat_tim_kiem(api_youtube_gia, tmp_path):
    """Hai hạn mức riêng: videos.list hết 10.000 đơn vị thì chỉ thiếu thời lượng; lý do không nói «yt-dlp»."""
    a = _ma(1)
    api_youtube_gia.kich_ban = [_tim(_muc(a)), gia.QUOTA]
    phien, phien_tim = _phien(), _phien()
    kq = tn.tim(phien, str(tmp_path / "data"), ["q"], phien_tim=phien_tim)
    assert [v["id"] for v in kq.video] == [a] and kq.video[0]["duration"] == 0
    assert phien.api.loai_tat == t.API_HET_HAN_MUC and not phien_tim.api.tat
    assert len(kq.ghi_chu) == 1 and kq.ghi_chu[0].startswith("1 video chưa lấy được thời lượng — Hết hạn mức")
    assert "10.000" in kq.ghi_chu[0]
    _khong_nhac_yt_dlp(kq.ghi_chu)


def test_khong_co_khoa_khong_gui_yeu_cau_nao(monkeypatch, tmp_path):
    tp = gia.lap_transport(monkeypatch)
    data = str(tmp_path / "data")
    kq = tn.tim(_phien(), data, ["a", "b"], phien_tim=_phien())
    assert tp.dem() == 0 and kq.video == () and (kq.da_tim, kq.tong, kq.luot_tim) == (0, 2, 0)
    assert kq.ghi_chu == ("Chỉ tìm được 0/2 truy vấn — " + ya.LY_DO_CHUA_CO_KHOA,)
    assert tn.kenh_cua_kho(_phien(), data, [_ma(1)]) == (frozenset(), "") and tp.dem() == 0


def test_moi_lan_bam_toi_da_50_truy_van(api_youtube_gia, tmp_path):
    kq = tn.tim(_phien(), str(tmp_path / "data"), [f"q{i}" for i in range(60)], phien_tim=_phien())
    assert api_youtube_gia.dem() == tn.TOI_DA == 50 and kq.tong == 50 and kq.da_tim == 50
    assert tn.TOI_DA_MAC_DINH == 10


def test_chi_video_dang_tu_ngay_va_bo_loc_thoi_luong(api_youtube_gia, tmp_path):
    tn.tim(_phien(), str(tmp_path / "data"), ["q"], phien_tim=_phien(), thoi_luong="any",
           sau=datetime.date(2026, 3, 1))
    p = api_youtube_gia.yeu_cau[0].params
    assert (p["videoDuration"], p["publishedAfter"]) == ("any", "2026-03-01T00:00:00Z")
    assert list(tn.NHAN_THOI_LUONG) == ["long", "medium", "any"]


# ---------------------------------------------------------------- kênh gốc của kho

def test_kenh_goc_mot_videos_list_toi_da_50_ma_clip_chon_truoc(api_youtube_gia, tmp_path):
    ids = [_ma(i) for i in range(80)]
    for m in ids:
        api_youtube_gia.video[m] = gia.video_gia(m)
    kenh, ly_do = tn.kenh_cua_kho(_phien(), str(tmp_path / "data"), [ids[70], "", ids[71]] + ids)
    assert (kenh, ly_do) == (frozenset({gia.KENH_GIA}), "")
    yc = api_youtube_gia.yeu_cau
    assert len(yc) == 1 and yc[0].endpoint == "videos" and len(yc[0].ids) == 50
    assert yc[0].ids[:3] == (ids[70], ids[71], ids[0])


def test_kenh_goc_loi_api_noi_ro_ly_do(api_youtube_gia, tmp_path):
    api_youtube_gia.kich_ban = [gia.KEY_INVALID]
    kenh, ly_do = tn.kenh_cua_kho(_phien(), str(tmp_path / "data"), [_ma(1)])
    assert kenh == frozenset() and ly_do.startswith("Khoá YouTube Data API không dùng được")
    _khong_nhac_yt_dlp([ly_do])


# ---------------------------------------------------------------- bảng, đánh dấu đã quét, ô quét

def test_bang_danh_dau_da_quet_va_dinh_dang_cot():
    video = ({"id": _ma(1), "title": "A", "channel": "K", "duration": 3 * 3600 + 5,
              "published_at": "2026-07-31T20:00:34Z", "khop": 2},
             {"id": _ma(2), "title": "B", "channel": "K2", "duration": 0, "published_at": "", "khop": 1})
    dong = tn.bang(video, {_ma(1), _ma(9)})
    assert tuple(dong[0]) == tn.COT == ("Tiêu đề", "Kênh", "Thời lượng", "Ngày đăng", "Link",
                                        "Khớp bao nhiêu truy vấn", "Đã quét chưa")
    assert dong[0] == {"Tiêu đề": "A", "Kênh": "K", "Thời lượng": "03:00:05", "Ngày đăng": "July 31, 2026",
                       "Link": f"https://www.youtube.com/watch?v={_ma(1)}", "Khớp bao nhiêu truy vấn": 2,
                       "Đã quét chưa": "Rồi"}
    assert (dong[1]["Thời lượng"], dong[1]["Ngày đăng"], dong[1]["Đã quét chưa"]) == ("", "", "Chưa")


def test_noi_link_giu_noi_dung_cu_khong_them_trung():
    cu = "https://youtu.be/aaaaaaaaaaa\n# ghi chú của tôi\n"
    moi = tn.noi_link(cu, ["https://www.youtube.com/watch?v=aaaaaaaaaaa",
                           "https://www.youtube.com/watch?v=bbbbbbbbbbb",
                           "https://www.youtube.com/watch?v=bbbbbbbbbbb"])
    assert moi == "https://youtu.be/aaaaaaaaaaa\n# ghi chú của tôi\nhttps://www.youtube.com/watch?v=bbbbbbbbbbb"
    assert tn.noi_link("", ["https://www.youtube.com/watch?v=ccccccccccc"]) == (
        "https://www.youtube.com/watch?v=ccccccccccc")
    assert tn.noi_link(cu, []) == cu


# ---------------------------------------------------------------- clip của kho (chỉ đọc clips_meta.json)

def _ghi_meta(thu_muc, meta):
    thu_muc.mkdir(parents=True, exist_ok=True)
    (thu_muc / "clips_meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def test_clip_cua_kho_chi_doc_clips_meta_moi_nhat_truoc(tmp_path):
    kho = tmp_path / "kho"
    _ghi_meta(kho, {
        "20260101 - Cu [aaaaaaaaaaa].opus": {"id": "aaaaaaaaaaa", "title": "Clip cũ", "upload_date": "20260101"},
        "20260301 - Moi [bbbbbbbbbbb].opus": {"id": "bbbbbbbbbbb", "title": "Clip mới", "upload_date": "20260301"},
        "20260201 - X [ccccccccccc].opus": {"id": "ccccccccccc", "title": "  "},
    })
    truoc = {p.name: p.stat().st_mtime_ns for p in kho.iterdir()}
    assert [(c.tieu_de, c.ma) for c in tn.clip_cua_kho(str(kho))] == [
        ("Clip mới", "bbbbbbbbbbb"), ("Clip cũ", "aaaaaaaaaaa")]
    assert {p.name: p.stat().st_mtime_ns for p in kho.iterdir()} == truoc, "chỉ đọc: không ghi, không tạo file"
    assert tn.clip_cua_kho("") == () and tn.clip_cua_kho(str(tmp_path / "khong_co")) == ()

    _ghi_meta(kho, {"20260401 - Them [ddddddddddd].opus": {"id": "ddddddddddd", "title": "Clip vừa đồng bộ"}})
    os.utime(kho / "clips_meta.json", ns=(1, 1))
    assert [c.tieu_de for c in tn.clip_cua_kho(str(kho))] == ["Clip vừa đồng bộ"], "file đổi thì đọc lại"


def test_khong_co_yt_dlp_trong_tinh_nang():
    nguon = inspect.getsource(tn)
    assert "yt_dlp" not in nguon and "ytdlp" not in nguon and ".chay(" not in nguon
