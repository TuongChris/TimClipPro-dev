# -*- coding: utf-8 -*-
"""Cookie đăng nhập trên máy KHÔNG có bộ chạy JavaScript không được làm hỏng cả lô quét.

Ca thật 14/10/2026, Stable 1.1.0 trên PC2 sau khi đặt `ytdlp_cookies_browser = firefox`: MỌI video lỗi

    ERROR: [youtube] <id>: The page needs to be reloaded

rồi cầu dao «lỗi trích xuất» dừng cả lô với lời khuyên «có thể yt-dlp cần cập nhật» — sai hướng.

Cơ chế (yt-dlp 2026.08.19 — đúng bản trong lock; đo NGOẠI TUYẾN trên PC2, cookie GIẢ, chặn mạng:
`C:\\Dev\\pc2_test_tools\\cookie_js\\kiem_client_cookie.py`):

* không cookie → client `visionos` (KHÔNG cần JavaScript) — đường đã nghiệm thu;
* có cookie đăng nhập → `web_embedded, tv_downgraded, web`, cả ba CẦN bộ chạy JavaScript; `visionos` bị yt-dlp
  LOẠI vì không hỗ trợ cookie — không client nào vừa nhận cookie vừa không cần JS;
* PC2 không có bộ chạy JS yt-dlp dùng được (không deno, node chưa bật, không gói yt-dlp-ejs) → không client nào
  lấy được định dạng → yt-dlp nêu lý do playability ĐẦU TIÊN: của `tv_downgraded` (yt-dlp issue 17389).
  Cấu hình maintainer gợi ý (`player_client=default,web_embedded`) cho ĐÚNG danh sách trên → không cứu được.

Nên: có cookie mà gặp lỗi này thì lùi về không-cookie như cookie chết, và NHỚ một lúc để không gửi lại bộ request
đăng nhập chắc chắn hỏng cho từng video — khâu tải còn không mang câu gốc (lỗi cuối của vòng player client).
"""

import pytest
import yt_dlp

import truy_cap_youtube as t
import ytdlp_chung as y
from engine import Engine, Match, ScanResult, chu_ky_chinh_sach
from kho_gia import ghi_kho
from ytdlp_gia import YdlKichBan, info_mau

LOI_RELOAD = "ERROR: [youtube] {id}: The page needs to be reloaded."
# Khâu tải có cookie: vòng player client hỏng hết, lỗi cuối KHÔNG mang câu gốc và không phải dấu hiệu cookie chết.
LOI_TAI_CO_COOKIE = "ERROR: [youtube] {id}: Failed to extract any player response"
LOI_COOKIE_CHET = "ERROR: [youtube] {id}: Requested format is not available"

CO_COOKIE = y.CauHinhMang(cookies_browser="firefox")
KHONG_COOKIE = y.CauHinhMang()
# Bộ nhớ «bỏ cookie» (y.NHO_BO_COOKIE) sống ở mức module: conftest quên nó sau MỖI test.


def _loi(mau, ma="OPgD5wl0fAY"):
    return RuntimeError(mau.format(id=ma))


# ---------------------------------------------------------------- nhận dạng

def test_nhan_dien_loi_cookie_can_js():
    assert y.la_dau_hieu_cookie_can_js(_loi(LOI_RELOAD))
    assert y.la_dau_hieu_cookie_can_js("the page needs to be reloaded")


@pytest.mark.parametrize("tin", [
    LOI_COOKIE_CHET,
    "ERROR: [youtube] {id}: Sign in to confirm you're not a bot.",
    "ERROR: unable to download video data: HTTP Error 403: Forbidden",
    "ERROR: [youtube] {id}: Video unavailable",
    LOI_TAI_CO_COOKIE,
])
def test_khong_nham_loi_khac(tin):
    assert not y.la_dau_hieu_cookie_can_js(_loi(tin))


# ---------------------------------------------------------------- đường lui

def test_co_cookie_gap_reload_thi_lui_ve_khong_cookie():
    da_goi = []

    def chay(ch):
        da_goi.append(ch.co_cookie)
        if ch.co_cookie:
            raise _loi(LOI_RELOAD)
        return "visionos"

    assert y.chay_kem_duong_lui_cookie(CO_COOKIE, chay) == "visionos"
    assert da_goi == [True, False]


def test_bao_ben_tren_dung_nguyen_nhan():
    nhan = []

    def chay(ch):
        if ch.co_cookie:
            raise _loi(LOI_RELOAD)
        return "ok"

    y.chay_kem_duong_lui_cookie(CO_COOKIE, chay, khi_bo_cookie=nhan.append)
    assert len(nhan) == 1 and y.la_dau_hieu_cookie_can_js(nhan[0])


def test_nho_de_luot_sau_khong_gui_lai_request_dang_nhap():
    """Lượt sau (vd. khâu tải của chính video đó) có cookie sẽ hỏng với câu KHÁC — vẫn phải đi thẳng không-cookie."""
    y.chay_kem_duong_lui_cookie(
        CO_COOKIE, lambda ch: (_ for _ in ()).throw(_loi(LOI_RELOAD)) if ch.co_cookie else "ok")
    da_goi = []

    def tai(ch):
        da_goi.append(ch.co_cookie)
        if ch.co_cookie:
            raise _loi(LOI_TAI_CO_COOKIE)
        return "đã tải"

    assert y.chay_kem_duong_lui_cookie(CO_COOKIE, tai) == "đã tải"
    assert da_goi == [False], "không gửi lại bộ request đăng nhập chắc chắn hỏng"


def test_luot_nho_van_bao_ben_tren():
    """Lô sau (phiên mới) đi thẳng không-cookie vẫn phải hiện cảnh báo vì sao bỏ cookie."""
    y.chay_kem_duong_lui_cookie(
        CO_COOKIE, lambda ch: (_ for _ in ()).throw(_loi(LOI_RELOAD)) if ch.co_cookie else "ok")
    nhan = []
    y.chay_kem_duong_lui_cookie(CO_COOKIE, lambda ch: "ok", khi_bo_cookie=nhan.append)
    assert len(nhan) == 1 and y.la_dau_hieu_cookie_can_js(nhan[0])


def test_nho_het_han_thi_do_lai():
    gio = [1000.0]
    nho = y.NhoBoCookie(song_giay=60.0, dong_ho=lambda: gio[0])

    def chay(ch):
        if ch.co_cookie:
            raise _loi(LOI_RELOAD)
        return "ok"

    y.chay_kem_duong_lui_cookie(CO_COOKIE, chay, nho=nho)
    da_goi = []
    y.chay_kem_duong_lui_cookie(CO_COOKIE, lambda ch: da_goi.append(ch.co_cookie) or "ok", nho=nho)
    assert da_goi == [False]
    gio[0] += 61.0
    da_goi.clear()
    y.chay_kem_duong_lui_cookie(CO_COOKIE, lambda ch: da_goi.append(ch.co_cookie) or "ok", nho=nho)
    assert da_goi == [True], "hết hạn nhớ thì dò lại cookie (vd. máy vừa cài bộ chạy JavaScript)"


def test_nho_theo_dung_cau_hinh_cookie():
    y.chay_kem_duong_lui_cookie(
        CO_COOKIE, lambda ch: (_ for _ in ()).throw(_loi(LOI_RELOAD)) if ch.co_cookie else "ok")
    for khac in (y.CauHinhMang(cookies_browser="chrome"), y.CauHinhMang(cookiefile="khac.txt")):
        da_goi = []
        y.chay_kem_duong_lui_cookie(khac, lambda ch: da_goi.append(ch.co_cookie) or "ok")
        assert da_goi == [True], "cấu hình cookie khác chưa bị chứng minh là hỏng"


def test_khong_nho_khi_bo_cookie_van_hong():
    """Bỏ cookie vẫn hỏng => cookie không phải nguyên nhân: báo lỗi GỐC, không nhớ gì."""
    def chay(ch):
        if ch.co_cookie:
            raise _loi(LOI_RELOAD)
        raise _loi("ERROR: [youtube] {id}: Video unavailable")

    with pytest.raises(RuntimeError, match="reloaded"):
        y.chay_kem_duong_lui_cookie(CO_COOKIE, chay)
    da_goi = []
    y.chay_kem_duong_lui_cookie(CO_COOKIE, lambda ch: da_goi.append(ch.co_cookie) or "ok")
    assert da_goi == [True]


# ---------------------------------------------------------------- không đổi hành vi cũ

def test_cookie_chet_giu_nguyen_hanh_vi_cu():
    """Cookie chết: vẫn lùi TỪNG lượt như trước (không nhớ) — ngoài phạm vi bản sửa này."""
    for _ in range(2):
        da_goi = []

        def chay(ch):
            da_goi.append(ch.co_cookie)
            if ch.co_cookie:
                raise _loi(LOI_COOKIE_CHET)
            return "ok"

        assert y.chay_kem_duong_lui_cookie(CO_COOKIE, chay) == "ok"
        assert da_goi == [True, False]


def test_khong_cookie_gap_reload_thi_bao_nguyen_loi():
    """Đường không-cookie đã nghiệm thu: lỗi đi thẳng ra, một lần gọi, không nhớ gì."""
    dem = []

    def chay(ch):
        dem.append(ch.co_cookie)
        raise _loi(LOI_RELOAD)

    with pytest.raises(RuntimeError, match="reloaded"):
        y.chay_kem_duong_lui_cookie(KHONG_COOKIE, chay)
    assert dem == [False]


def test_tuy_chon_khong_cookie_khong_doi():
    """Không cookie: tuỳ chọn yt-dlp giữ nguyên từng khoá (không thêm player_client/extractor_args)."""
    assert KHONG_COOKIE.tuy_chon("metadata", noplaylist=True) == {
        "quiet": True, "no_warnings": True, "no_color": True, "socket_timeout": 30,
        **t.NGAN_SACH["metadata"].tuy_chon_yt_dlp(), "sleep_interval_requests": 1.0, "noplaylist": True}


# ---------------------------------------------------------------- cả lô quét thật (Engine + phiên + cầu dao)

def _eng(tmp_path, monkeypatch, ydl) -> Engine:
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    thu_muc = tmp_path / "kho"
    thu_muc.mkdir(exist_ok=True)
    e.add_kho("A", str(thu_muc))
    ghi_kho(e.db_file, [(str(thu_muc / "goc [ggggggggggg].opus"), 9)])
    e.use_kho("A")
    e.config.ytdlp_sleep_requests_s = 0.0
    e.config.ytdlp_cookies_browser = "firefox"
    monkeypatch.setattr(Engine, "require", lambda self, **k: None)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)

    def cam_doc_cookie_that(*a, **k):
        raise AssertionError("test không bao giờ được đọc cookie trình duyệt thật")

    monkeypatch.setattr(yt_dlp.cookies, "extract_cookies_from_browser", cam_doc_cookie_that)
    dt = e.danh_tinh_kho()

    def quet(path, label=None, ref="", source_type="file", progress=None, luu_lich_su=True,
             pct_start=0.0, *, muc_tieu=None):
        m = Match(clip="goc [ggggggggggg].opus", start_s=60.0, end_s=360.0, matched_s=300.0,
                  clip_offset_s=0.0, hashes=6000, confidence="x", ty_le=50.0, clip_bat_dau_s=60.0,
                  vung_khop_s=60.0)
        kq = ScanResult(source_name=label or path, source_ref=ref, duration_s=600.0,
                        vung_da_khop=[(0.0, 600.0)], kho_id=dt["kho_id"], kho_ten=dt["kho_ten"],
                        kho_phien_ban=dt["kho_phien_ban"], chinh_sach=chu_ky_chinh_sach(e.config))
        kq.matches = [m]
        kq.ung_vien_dat = [m]
        kq.so_dat_nguong = 1
        return kq

    monkeypatch.setattr(e, "scan_media", quet)
    return e


def _theo_cookie(loi_khi_co_cookie, ket_khi_khong):
    def hanh_vi(phien, ma):
        co = bool(phien.opts.get("cookiesfrombrowser") or phien.opts.get("cookiefile"))
        return loi_khi_co_cookie if co else ket_khi_khong(ma)
    return hanh_vi


def test_lo_6_video_co_cookie_firefox_khong_con_hong_hang_loat(tmp_path, monkeypatch):
    ma = [f"vid{i:08d}" for i in range(6)]
    ydl = YdlKichBan(info={"*": _theo_cookie(LOI_RELOAD, info_mau)},
                     tai={"*": _theo_cookie(LOI_TAI_CO_COOKIE, lambda _m: None)})
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert [k.status for k in ket].count("error") == 0, [k.note for k in ket]
    assert all(k.matches for k in ket)
    phien_co_cookie = [bool(o.get("cookiesfrombrowser")) for o in ydl.opts]
    assert phien_co_cookie.count(True) == 1, "chỉ MỘT lượt đăng nhập chắc chắn hỏng cho cả lô"
    assert ydl.dem("info") == 7 and ydl.dem("tai") == 6
    assert any("JavaScript" in c for c in e.canh_bao_mang), e.canh_bao_mang
    assert not any("hết hiệu lực" in c for c in e.canh_bao_mang), "cookie không chết — đừng dẫn sai hướng"


def test_lo_khong_cookie_giu_nguyen_so_request(tmp_path, monkeypatch):
    """Đường không-cookie đã nghiệm thu: mỗi video đúng một lần lấy thông tin + một lần tải, không cảnh báo."""
    ma = [f"vid{i:08d}" for i in range(3)]
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    e.config.ytdlp_cookies_browser = ""
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert [k.status for k in ket].count("error") == 0
    assert ydl.dem("info") == 3 and ydl.dem("tai") == 3
    assert not any(o.get("cookiesfrombrowser") or o.get("cookiefile") for o in ydl.opts)
    assert e.canh_bao_mang == []


def test_engine_canh_bao_cookie_can_js(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    e.canh_bao_mang = []
    e._canh_bao_cookie_chet(_loi(LOI_RELOAD))
    assert len(e.canh_bao_mang) == 1
    assert "JavaScript" in e.canh_bao_mang[0] and "hết hiệu lực" not in e.canh_bao_mang[0]
    e._canh_bao_cookie_chet(_loi(LOI_RELOAD))
    assert len(e.canh_bao_mang) == 1, "không lặp lại cùng một cảnh báo cho mỗi video"
