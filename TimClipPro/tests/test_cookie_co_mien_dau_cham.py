# -*- coding: utf-8 -*-
"""Audit D-1: cổng cookie bỏ lọt luật «cờ miền ↔ dấu chấm đầu» của yt-dlp; lỗi
«invalid Netscape format cookies file» của yt-dlp mang NGUYÊN dòng cookie (repr) + đường dẫn
đầy đủ, không bị che, bị xếp UNKNOWN thay vì COOKIE_INVALID.

`http.cookiejar.MozillaCookieJar._really_load` (yt-dlp nạp file cookie qua đó) còn
``assert domain_specified == initial_dot``: cột 2 == "TRUE" phải khớp miền có dấu chấm đầu. Lệch
MỘT dòng là LoadError cho CẢ file, câu lỗi = đường dẫn + repr nguyên dòng (TAB thành chữ «\\t»,
nên các mẫu che dòng Netscape không bắt được).

Hai lớp, test cả hai (đúng mục 8 của docs/LOI_DA_GAP.md): cổng chặn từ đầu nguồn (ba test đầu
— bản sao của test tái hiện audit, giữ nguyên khẳng định); và khi cổng bị vượt (file đổi giữa
chừng, yt-dlp thêm luật mới) thì câu lỗi thật của yt-dlp vẫn bị che ở mọi đầu ra và xếp đúng
loại cookie hỏng.

Hoàn toàn ngoại tuyến: yt-dlp chỉ nạp file cookie tổng hợp trong tmp_path, không request nào.
Giá trị cookie là chuỗi GIẢ.
"""

import warnings

import pytest
import yt_dlp
from yt_dlp.cookies import YoutubeDLCookieJar

import nhat_ky
import truy_cap_youtube as t
import ytdlp_chung as y

BI_MAT = "FAKEVALUE_AUDIT_D1_KHONG_CO_THAT_9q8w7e6r"
_DAU = "# Netscape HTTP Cookie File\n"
# Miền có dấu chấm đầu nhưng cờ include-subdomains = FALSE: 7 trường TAB, hạn dùng là số.
_DONG_LECH = "\t".join([".youtube.com", "FALSE", "/", "TRUE", "1790000000", "__Secure-1PSID", BI_MAT])


def _ghi_cookie(tmp_path):
    thu_muc = tmp_path / "Users" / "nguoi_dung_gia" / "Downloads"
    thu_muc.mkdir(parents=True)
    p = thu_muc / "cookies.txt"
    p.write_text(_DAU + _DONG_LECH + "\n", encoding="utf-8")
    return str(p)


def _loi_that_cua_ytdlp(p):
    """Đúng đường thật: tuỳ chọn đi qua cổng của tool, rồi yt-dlp tự nạp cookie (không mạng)."""
    y._CACHE_COOKIE.clear()
    try:
        opts = y.CauHinhMang(cookiefile=p).tuy_chon("listing")
    except y.LoiFileCookie:
        return None, None  # cổng đã chặn — hành vi đúng
    bo_ghi = y.BoGhiYtdlp()
    opts = {**opts, "logger": bo_ghi}
    with pytest.raises(Exception) as ei:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.cookiejar  # noqa: B018 — chính yt-dlp nạp file cookie ở đây
    return ei.value, bo_ghi


def test_cong_cookie_chan_dong_co_mien_lech(tmp_path):
    """yt-dlp (MozillaCookieJar._really_load) từ chối cả file này → cổng phải chặn trước."""
    p = _ghi_cookie(tmp_path)
    y._CACHE_COOKIE.clear()
    cd = t.chan_doan_cookie(p)
    assert cd.cau_truc_hop_le is False, "chẩn đoán báo file cookie HỢP LỆ trong khi yt-dlp sẽ từ chối"
    with pytest.raises(y.LoiFileCookie):
        y.kiem_tra_file_cookie(p)


def test_loi_nap_cookie_cua_ytdlp_khong_lo_gia_tri_va_xep_dung_loai(tmp_path):
    p = _ghi_cookie(tmp_path)
    loi, bo_ghi = _loi_that_cua_ytdlp(p)
    if loi is None:
        return  # cổng đã chặn: không có lỗi yt-dlp nào để rò
    f = t.phan_loai_loi(loi)
    sai = []
    # Không nơi nào được giữ giá trị cookie phiên.
    if BI_MAT in t.che_bi_mat(str(loi)):
        sai.append("che_bi_mat de lot gia tri cookie")
    if BI_MAT in f.technical_summary:
        sai.append("technical_summary (luu lich su) chua gia tri cookie")
    if BI_MAT in y.giai_thich_loi(loi, co_cookie=True):
        sai.append("giai_thich_loi (ScanResult.note/CSV) chua gia tri cookie")
    if any(BI_MAT in d for d in bo_ghi.loi):
        sai.append("BoGhiYtdlp.error ghi log gia tri cookie")
    # File cookie hỏng là lỗi cấu hình cookie, không phải «YouTube lỗi chưa rõ».
    if f.category != t.COOKIE_INVALID_OR_EXPIRED:
        sai.append(f"category={f.category} (can COOKIE_INVALID_OR_EXPIRED)")
    assert not sai, sai


def test_thu_tung_client_dung_ngay_va_khong_lo(tmp_path):
    p = _ghi_cookie(tmp_path)
    loi, _ = _loi_that_cua_ytdlp(p)
    if loi is None:
        return
    so_lan = []

    def chay(_opts):
        so_lan.append(1)
        raise loi

    phien = t.PhienYouTube()
    with pytest.raises(RuntimeError) as ei:
        y.thu_tung_client(["a", "b", "c", "d", "e"], chay, {}, dung_ngay=phien.nen_dung_doi_client)
    sai = []
    if BI_MAT in str(ei.value):
        sai.append("RuntimeError (UI/CLI) chua gia tri cookie")
    if len(so_lan) != 1:
        sai.append(f"file cookie hong ma van thu {len(so_lan)} client")
    assert not sai, sai


# ------------------------------------------------ cổng == luật nạp thật của yt-dlp

def _ytdlp_nhan(p) -> bool:
    """yt-dlp (bộ nạp thật, không mạng) có nạp được file này không."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")      # «http.cookiejar bug!» của stdlib khi assert hỏng
            YoutubeDLCookieJar(p).load()
    except Exception:  # noqa: BLE001 — LoadError
        return False
    return True


@pytest.mark.parametrize("mien,co,hop_le", [
    (".youtube.com", "TRUE", True),
    ("www.youtube.com", "FALSE", True),       # cookie chỉ-host: không chấm, cờ FALSE
    (".youtube.com", "FALSE", False),         # đúng ca của audit
    ("www.youtube.com", "TRUE", False),       # bộ chuyển đổi tự viết ghi TRUE cho mọi dòng
    (".youtube.com", "true", False),          # stdlib so đúng chữ "TRUE"
])
def test_cong_khop_luat_nap_that_cua_ytdlp(tmp_path, mien, co, hop_le):
    p = tmp_path / "cookies.txt"
    p.write_text(_DAU + "\t".join([".youtube.com", "TRUE", "/", "TRUE", "1790000000", "PREF", "x"]) + "\n"
                 + "#HttpOnly_" + "\t".join([mien, co, "/", "TRUE", "1790000000", "SID", BI_MAT]) + "\n",
                 encoding="utf-8")
    assert _ytdlp_nhan(str(p)) is hop_le, "giả định về luật nạp của yt-dlp đã đổi"
    y._CACHE_COOKIE.clear()
    cd = t.chan_doan_cookie(str(p))
    assert cd.cau_truc_hop_le is hop_le
    if hop_le:
        y.kiem_tra_file_cookie(str(p))
        assert cd.so_ban_ghi == 2
        return
    assert cd.so_dong_hong == 1 and cd.dong_hong_dau == (3,)
    with pytest.raises(y.LoiFileCookie) as ei:
        y.kiem_tra_file_cookie(str(p))
    tin = str(ei.value)
    assert "dòng 3" in tin and "Cột 2 (TRUE/FALSE)" in tin
    assert "Notepad" not in tin, "không phải lỗi TAB — đừng dẫn người dùng đi sửa nhầm chỗ"
    assert BI_MAT not in tin and "SID" not in tin


def test_cong_dong_tab_hong_lan_dong_lech_mien_van_neu_nguyen_nhan_tab(tmp_path):
    p = tmp_path / "cookies.txt"
    p.write_text(_DAU + _DONG_LECH + "\n" + f".youtube.com TRUE / TRUE 0 SID {BI_MAT}\n", encoding="utf-8")
    with pytest.raises(y.LoiFileCookie) as ei:
        y.kiem_tra_file_cookie(str(p))
    tin = str(ei.value)
    assert "dòng 2, 3" in tin and "Notepad" in tin and BI_MAT not in tin


# ------------------------------------------------ lớp 2: cổng bị vượt thì câu lỗi thật vẫn bị che

@pytest.fixture
def loi_khi_vuot_cong(tmp_path, monkeypatch):
    """Câu lỗi THẬT của yt-dlp khi file lệch cờ miền tới được bộ nạp (file đổi sau khi cổng kiểm, hay yt-dlp thêm luật
    mà cổng chưa biết) — mô phỏng bằng cách tắt cổng."""
    monkeypatch.setattr(y, "kiem_tra_file_cookie", lambda _duong_dan: None)
    p = _ghi_cookie(tmp_path)
    bo_ghi = y.BoGhiYtdlp()
    opts = {**y.CauHinhMang(cookiefile=p).tuy_chon("listing"), "logger": bo_ghi}
    with warnings.catch_warnings(record=True) as canh_bao:
        warnings.simplefilter("always")
        with pytest.raises(Exception) as ei:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.cookiejar  # noqa: B018 — chính yt-dlp nạp file cookie ở đây
    loi = ei.value
    assert BI_MAT in str(loi), "giả định: câu lỗi gốc của yt-dlp mang giá trị cookie"
    return loi, bo_ghi, [str(w.message) for w in canh_bao]


def test_lop_hai_loi_nap_cookie_bi_che_va_xep_cookie_hong(loi_khi_vuot_cong):
    loi, bo_ghi, _ = loi_khi_vuot_cong
    sach = t.che_bi_mat(str(loi))
    assert BI_MAT not in sach
    assert "nguoi_dung_gia" not in sach, "đường dẫn đầy đủ mang tên người dùng Windows"
    assert "invalid Netscape format cookies file" in sach, "giữ cụm để còn chẩn đoán"
    assert t.che_bi_mat(sach) == sach, "luỹ đẳng"
    f = t.phan_loai_loi(loi)
    assert f.category == t.COOKIE_INVALID_OR_EXPIRED and f.auth_related
    assert BI_MAT not in f.technical_summary and BI_MAT not in f.human_message_vi
    assert BI_MAT not in y.giai_thich_loi(loi, co_cookie=True)
    assert bo_ghi.loi and not any(BI_MAT in d for d in bo_ghi.loi)
    # Phân loại lại từ CHỮ đã che (ghi chú lịch sử, câu của thu_tung_client) vẫn ra cookie hỏng.
    assert t.phan_loai_loi(RuntimeError(sach)).category == t.COOKIE_INVALID_OR_EXPIRED


def test_lop_hai_thu_tung_client_dung_ngay_cau_dao_mo_ngay(loi_khi_vuot_cong):
    loi, _, _ = loi_khi_vuot_cong
    so_lan = []

    def chay(_opts):
        so_lan.append(1)
        raise loi

    phien = t.PhienYouTube()
    with pytest.raises(RuntimeError) as ei:
        y.thu_tung_client(["a", "b", "c", "d", "e"], chay, {}, dung_ngay=phien.nen_dung_doi_client)
    assert len(so_lan) == 1, "file cookie hỏng: đổi client vô ích"
    assert BI_MAT not in str(ei.value)
    with pytest.raises(t.LoiTruyCapYouTube):
        phien.chay("download", lambda: (_ for _ in ()).throw(ei.value), video_id="abc")
    assert phien.mo, "cầu dao cookie hỏng mở sau MỘT lỗi (NGUONG_MO = 1), không đợi 5 lỗi «chưa rõ»"


def test_lop_hai_canh_bao_stdlib_vao_nhat_ky_bi_che(loi_khi_vuot_cong):
    """`_warn_unhandled_exception` của stdlib in traceback (cả chuỗi ngoại lệ, có câu lỗi mang giá trị) ra stderr —
    Watch đấu stderr vào file nhật ký qua ``nhat_ky.che_bi_mat``."""
    _, _, canh_bao = loi_khi_vuot_cong
    co_bi_mat = [c for c in canh_bao if BI_MAT in c]
    assert co_bi_mat, "giả định: cảnh báo «http.cookiejar bug!» mang câu lỗi có giá trị cookie"
    for c in co_bi_mat:
        assert BI_MAT not in nhat_ky.che_bi_mat(c)
