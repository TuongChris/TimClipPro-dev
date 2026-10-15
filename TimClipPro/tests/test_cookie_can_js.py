# -*- coding: utf-8 -*-
"""Cookie đăng nhập YouTube: DÙNG ĐƯỢC khi máy giải được thử thách JavaScript (Node.js ≥ 22 + gói yt-dlp-ejs), và MINH
BẠCH khi không — không bao giờ để người dùng tưởng đã đăng nhập khi thật ra đang chạy không cookie.

Ca thật 14/10/2026, Stable 1.1.0 trên PC2 sau khi đặt `ytdlp_cookies_browser = firefox`: MỌI video lỗi

    ERROR: [youtube] <id>: The page needs to be reloaded

rồi cầu dao «lỗi trích xuất» dừng cả lô với lời khuyên «có thể yt-dlp cần cập nhật» — sai hướng.

Cơ chế (yt-dlp 2026.08.19 — đúng bản trong lock; đo NGOẠI TUYẾN trên PC2, cookie GIẢ, chặn mạng:
`C:\\Dev\\pc2_test_tools\\cookie_js\\kiem_node_ejs.py`):

* không cookie → client `visionos` (KHÔNG cần JavaScript) — đường đã nghiệm thu;
* có cookie đăng nhập → `web_embedded, tv_downgraded, web`, cả ba phải giải thử thách JavaScript; `visionos` không
  nhận cookie;
* giải thử thách cần Node.js ≥ 22 (yt-dlp chỉ tự bật deno → phải truyền `js_runtimes`) + gói `yt-dlp-ejs` ĐÚNG bản
  yt-dlp ghim (0.8.0). Stable 1.1.0 không có gói đó → không client nào lấy được định dạng → yt-dlp nêu lý do
  playability ĐẦU TIÊN, của `tv_downgraded` (yt-dlp issue 17389).

Chính sách (`ytdlp_chung.chay_kem_duong_lui_cookie`): hỏi TRẠNG THÁI MÁY ở mỗi lượt — không nhớ lỗi cũ, không bộ nhớ
dùng chung giữa các cấu hình/tài khoản; máy chưa sẵn sàng → KHÔNG gửi request đăng nhập nào, chạy không cookie và nói
rõ «KHÔNG đăng nhập» trong MỌI kết quả; máy sẵn sàng → cookie + Node ở mọi đường gọi, mỗi lỗi giữ đúng loại của nó
(xác minh bot, cần đăng nhập, player client, bộ giải JS) — không tự bỏ đăng nhập, không thành kết quả âm tính.
"""

import pytest
import yt_dlp

import giam_sat_tai
import scan_ui
import truy_cap_youtube as t
import ytdlp_chung as y
from engine import Cancelled, Engine, Match, ScanResult, TaiAudioDungHinh, chu_ky_chinh_sach
from kho_gia import ghi_kho
from ytdlp_gia import AUTH, BOT, DANG_NHAP, YdlKichBan, info_mau

LOI_RELOAD = "ERROR: [youtube] {id}: The page needs to be reloaded."
LOI_COOKIE_CHET = "ERROR: [youtube] {id}: Requested format is not available"
HOI_VIEN = "ERROR: [youtube] {id}: Join this channel to get access to members-only content like this video."
CANH_BAO_N = ("[youtube] {id}: n challenge solving failed: Some formats may be missing. Ensure you have a supported "
              "JavaScript runtime and challenge solver script distribution installed.")
CANH_BAO_KHONG_JS_BINH_THUONG = (
    "[youtube] No supported JavaScript runtime could be found. Only deno is enabled by default; to use another "
    "runtime add  --js-runtimes RUNTIME[:PATH]  to your command/config.")

CO_COOKIE = y.CauHinhMang(cookies_browser="firefox")
KHONG_COOKIE = y.CauHinhMang()

SAN_SANG = y.KhaNangJs(True, node=r"C:\gia\nodejs\node.exe", node_phien_ban="24.21.0", ejs_phien_ban="0.8.0")
THIEU_EJS = y.KhaNangJs(False, node=r"C:\gia\nodejs\node.exe", node_phien_ban="24.21.0",
                        ly_do="máy thiếu gói yt-dlp-ejs 0.8.0 (bản yt-dlp này cần đúng bản đó)")
THIEU_NODE = y.KhaNangJs(False, ejs_phien_ban="0.8.0",
                         ly_do="máy thiếu Node.js ≥ 22 (không thấy node trên PATH)")


@pytest.fixture
def may(monkeypatch):
    """Đặt trạng thái máy (``ytdlp_chung.kha_nang_js``); đổi được giữa chừng như khi người dùng cài/gỡ Node."""
    hien = {"kn": SAN_SANG}
    monkeypatch.setattr(y, "kha_nang_js", lambda: hien["kn"])

    def dat(kn):
        hien["kn"] = kn

    return dat


def _loi(mau, ma="OPgD5wl0fAY"):
    return RuntimeError(mau.format(id=ma))


def _ghi_cookie(da_goi, loi_khi_co=None, ket="ok"):
    """``chay(cau_hinh)`` giả: ghi lại có cookie hay không; có cookie thì ném ``loi_khi_co`` (nếu có)."""
    def chay(ch):
        da_goi.append(ch.co_cookie)
        if ch.co_cookie and loi_khi_co:
            raise _loi(loi_khi_co)
        return ket
    return chay


# ---------------------------------------------------------------- tuỳ chọn yt-dlp (mọi đường gọi)

@pytest.mark.parametrize("thao_tac", ["metadata", "download", "listing", ""])
def test_co_cookie_may_san_sang_bat_node_o_moi_thao_tac(may, thao_tac):
    opts = CO_COOKIE.tuy_chon(thao_tac)
    assert opts["js_runtimes"] == {"node": {"path": SAN_SANG.node}}
    assert opts["cookiesfrombrowser"] == ("firefox", None, None, None)
    assert "remote_components" not in opts, "không tải script giải từ GitHub/npm lúc chạy — chỉ gói trong lock"


@pytest.mark.parametrize("kn", [SAN_SANG, THIEU_EJS, THIEU_NODE])
def test_khong_cookie_tuy_chon_giu_nguyen_tung_khoa(may, kn):
    """Đường không-cookie đã nghiệm thu (visionos, không JS): không thêm js_runtimes/player_client/extractor_args."""
    may(kn)
    assert KHONG_COOKIE.tuy_chon("metadata", noplaylist=True) == {
        "quiet": True, "no_warnings": True, "no_color": True, "socket_timeout": 30,
        **t.NGAN_SACH["metadata"].tuy_chon_yt_dlp(), "sleep_interval_requests": 1.0, "noplaylist": True}


@pytest.mark.parametrize("thao_tac", ["metadata", "download"])
def test_co_cookie_may_chua_san_sang_chan_truoc_moi_request(may, thao_tac):
    """Đường không có lùi không-cookie (vd. chi tiết kênh, vá metadata, youtube-doctor): báo đúng lý do, chưa gửi gì."""
    may(THIEU_EJS)
    with pytest.raises(y.CookieCanJs) as ei:
        CO_COOKIE.tuy_chon(thao_tac)
    f = t.phan_loai_loi(ei.value)
    assert f.category == t.JS_CHALLENGE_ERROR, "câu có chữ «cookie» vẫn không được thành lỗi cookie"
    assert "thiếu gói yt-dlp-ejs 0.8.0" in f.human_message_vi and "Chưa gửi request" in f.human_message_vi


def test_liet_ke_kenh_khong_can_js_nen_giu_cookie(may):
    may(THIEU_NODE)
    opts = CO_COOKIE.tuy_chon("listing")
    assert opts["cookiesfrombrowser"][0] == "firefox" and "js_runtimes" not in opts


# ---------------------------------------------------------------- chính sách cookie

def test_may_chua_san_sang_chay_khong_cookie_va_noi_ro(may):
    may(THIEU_EJS)
    da_goi, nhan = [], []
    assert y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie(da_goi), khi_bo_cookie=nhan.append) == "ok"
    assert da_goi == [False], "không gửi request đăng nhập chắc chắn hỏng"
    assert len(nhan) == 1 and isinstance(nhan[0], y.CookieCanJs)
    assert "KHÔNG đăng nhập" in str(nhan[0]) and THIEU_EJS.ly_do in str(nhan[0])
    assert nhan[0].ly_do == THIEU_EJS.ly_do


def test_may_san_sang_dung_cookie(may):
    da_goi, nhan = [], []
    assert y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie(da_goi), khi_bo_cookie=nhan.append) == "ok"
    assert da_goi == [True] and nhan == []


def test_js_hoat_dong_tro_lai_thi_dung_cookie_ngay_khong_nho_loi_cu(may):
    da_goi = []
    may(THIEU_NODE)
    y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie(da_goi))
    may(SAN_SANG)                       # người dùng vừa cài Node.js
    y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie(da_goi))
    may(THIEU_NODE)                     # gỡ Node
    y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie(da_goi))
    assert da_goi == [False, True, False]


def test_khong_con_bo_nho_dung_chung_giua_cau_hinh_hay_tai_khoan(may):
    """Bản trước nhớ «bỏ cookie» 30 phút ở mức tiến trình: một lỗi cũ làm mọi phiên/tài khoản cùng cấu hình chạy không
    cookie. Nay quyết định chỉ theo trạng thái máy LÚC ĐÓ."""
    assert not hasattr(y, "NhoBoCookie") and not hasattr(y, "NHO_BO_COOKIE")
    with pytest.raises(RuntimeError, match="reloaded"):
        y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie([], LOI_RELOAD))
    for cau_hinh in (CO_COOKIE, y.CauHinhMang(cookies_browser="chrome"), y.CauHinhMang(cookiefile="khac.txt")):
        da_goi = []
        y.chay_kem_duong_lui_cookie(cau_hinh, _ghi_cookie(da_goi))
        assert da_goi == [True]


def test_reload_khi_may_san_sang_la_loi_player_client_khong_tu_bo_dang_nhap(may):
    da_goi, nhan = [], []
    with pytest.raises(RuntimeError, match="reloaded") as ei:
        y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie(da_goi, LOI_RELOAD), khi_bo_cookie=nhan.append)
    assert da_goi == [True] and nhan == []
    assert t.phan_loai_loi(ei.value).category == t.PLAYER_CLIENT_ERROR


@pytest.mark.parametrize("mau,loai", [(BOT, t.BOT_CHALLENGE), (DANG_NHAP, t.AUTH_REQUIRED),
                                      (AUTH, t.AGE_RESTRICTED), (HOI_VIEN, t.MEMBERS_ONLY)])
def test_bot_hay_video_can_dang_nhap_khong_lui_khong_cookie(may, mau, loai):
    """Video cần đăng nhập (tuổi, hội viên) hay YouTube đòi xác minh: KHÔNG thử lại không cookie."""
    da_goi = []
    with pytest.raises(RuntimeError) as ei:
        y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie(da_goi, mau))
    assert da_goi == [True]
    assert t.phan_loai_loi(ei.value).category == loai


def test_bo_giai_js_hong_khong_do_cho_cookie(may):
    """Máy «sẵn sàng» nhưng bộ giải không giải được player hiện tại: lỗi cuối «Requested format is not available»
    trùng chữ ký cookie chết — cảnh báo n challenge cho biết đây là lỗi bộ giải, không phải cookie."""
    bo_ghi = y.BoGhiYtdlp(t.PhienYouTube())
    da_goi, nhan = [], []

    def chay(ch):
        da_goi.append(ch.co_cookie)
        if ch.co_cookie:
            bo_ghi.warning(CANH_BAO_N.format(id="OPgD5wl0fAY"))
            raise _loi(LOI_COOKIE_CHET)
        return "ok"

    with pytest.raises(y.LoiGiaiJs) as ei:
        y.chay_kem_duong_lui_cookie(CO_COOKIE, chay, khi_bo_cookie=nhan.append, bo_ghi=bo_ghi)
    assert da_goi == [True] and nhan == [], "không tự bỏ đăng nhập"
    f = t.phan_loai_loi(ei.value)
    assert f.category == t.JS_CHALLENGE_ERROR
    assert "KHÔNG bị coi là hỏng" in f.human_message_vi and "Node.js 24.21.0" in f.human_message_vi
    assert "n challenge solving failed" in f.technical_summary and "Requested format" in f.technical_summary
    assert bo_ghi.phien.tom_tat()["js_challenge_warnings"] == 1


def test_canh_bao_js_cua_luot_truoc_khong_tinh_cho_luot_nay(may):
    bo_ghi = y.BoGhiYtdlp()
    bo_ghi.warning(CANH_BAO_N.format(id="luotTruoc01"))
    da_goi = []
    assert y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie(da_goi, LOI_COOKIE_CHET), bo_ghi=bo_ghi) == "ok"
    assert da_goi == [True, False], "cookie chết: vẫn lùi như trước"


def test_canh_bao_js_kem_loi_bot_van_la_bot(may):
    bo_ghi = y.BoGhiYtdlp()

    def chay(ch):
        bo_ghi.warning(CANH_BAO_N.format(id="OPgD5wl0fAY"))
        raise _loi(BOT)

    with pytest.raises(RuntimeError) as ei:
        y.chay_kem_duong_lui_cookie(CO_COOKIE, chay, bo_ghi=bo_ghi)
    assert not isinstance(ei.value, y.LoiGiaiJs)
    assert t.phan_loai_loi(ei.value).category == t.BOT_CHALLENGE


def test_canh_bao_khong_js_cua_duong_khong_cookie_khong_phai_bo_giai_hong():
    assert not y.la_canh_bao_js_hong(CANH_BAO_KHONG_JS_BINH_THUONG)
    assert y.la_canh_bao_js_hong(CANH_BAO_N)
    assert y.la_canh_bao_js_hong("[youtube] [jsc] Remote component challenge solver script (node) was skipped.")
    assert y.la_canh_bao_js_hong('[youtube] [jsc:node] Error solving n challenge request using "node" provider')


def test_cookie_chet_giu_nguyen_hanh_vi_cu(may):
    for _ in range(2):
        da_goi = []
        assert y.chay_kem_duong_lui_cookie(CO_COOKIE, _ghi_cookie(da_goi, LOI_COOKIE_CHET)) == "ok"
        assert da_goi == [True, False]


@pytest.mark.parametrize("kn", [SAN_SANG, THIEU_EJS])
def test_khong_cookie_loi_di_thang_ra_mot_lan(may, kn):
    may(kn)
    da_goi, nhan = [], []

    def chay(ch):
        da_goi.append(ch.co_cookie)
        raise _loi(LOI_RELOAD)

    with pytest.raises(RuntimeError, match="reloaded"):
        y.chay_kem_duong_lui_cookie(KHONG_COOKIE, chay, khi_bo_cookie=nhan.append)
    assert da_goi == [False] and nhan == []


# ---------------------------------------------------------------- Dừng / mạng đứng / lỗi máy KHÔNG thành «lỗi JavaScript»
# Review F1 (PC1 14/10/2026): bộ giải JS hỏng MỘT PHẦN (một client cảnh báo, client khác vẫn tải) rồi người dùng bấm Dừng,
# ffmpeg đứng hay đĩa đầy — lỗi đó bị đổi thành LoiGiaiJs: phiên ghi JS_CHALLENGE_ERROR (cầu dao ngưỡng 2: hai lần Dừng
# là dừng cả lô), bỏ qua nhánh dọn file dở của Dừng, lịch sử ghi «bộ giải JS hỏng» thay vì «đã huỷ».

LOI_DUNG = (Cancelled, TaiAudioDungHinh)       # đúng `bo_qua` của Engine.download_audio
MANG_DUNG = ("Mạng đứng: 180 giây ffmpeg không ghi thêm dữ liệu audio nào (file đã có 12,0 MB) — đã dừng lượt tải. "
             "Kiểm kết nối mạng rồi quét lại.")


def _hong_sau_canh_bao_js(bo_ghi, loi, khi_dang_xu_ly=None):
    """``chay(cau_hinh)`` giả: yt-dlp đã cảnh báo giải JS hỏng trong lượt này, rồi lượt dừng vì ``loi`` (không do JS).

    ``khi_dang_xu_ly``: lỗi yt-dlp đang được xử lý khi ``loi`` nổ ra (thành ``__context__``) — Engine đổi lỗi tải thành
    ``Cancelled`` khi người dùng đã bấm Dừng, dù yt-dlp lúc đó báo gì (kể cả «không còn định dạng»)."""
    def chay(_ch):
        bo_ghi.warning(CANH_BAO_N.format(id="OPgD5wl0fAY"))
        if khi_dang_xu_ly is None:
            raise loi
        try:
            raise _loi(khi_dang_xu_ly)
        except RuntimeError:
            raise loi
    return chay


@pytest.mark.parametrize("loi", [Cancelled(), TaiAudioDungHinh(MANG_DUNG)], ids=["dung", "mang_dung"])
def test_dung_sau_canh_bao_js_di_thang_ra_dung_doi_tuong(may, loi):
    bo_ghi = y.BoGhiYtdlp(t.PhienYouTube())
    nhan = []
    with pytest.raises(type(loi)) as ei:
        y.chay_kem_duong_lui_cookie(CO_COOKIE, _hong_sau_canh_bao_js(bo_ghi, loi, LOI_COOKIE_CHET),
                                    khi_bo_cookie=nhan.append, bo_ghi=bo_ghi, bo_qua=LOI_DUNG)
    assert ei.value is loi, "lớp bo_qua đi thẳng ra, không bị đổi thành LoiGiaiJs"
    assert nhan == [], "Dừng không phải lý do bỏ đăng nhập"


def _mot_lan_dung(phien):
    bo_ghi = y.BoGhiYtdlp(phien)
    chay = _hong_sau_canh_bao_js(bo_ghi, Cancelled(), LOI_COOKIE_CHET)
    with pytest.raises(Cancelled):
        phien.chay("download",
                   lambda: y.chay_kem_duong_lui_cookie(CO_COOKIE, chay, bo_ghi=bo_ghi, bo_qua=LOI_DUNG),
                   video_id="OPgD5wl0fAY", loi_huy=Cancelled, bo_qua=LOI_DUNG)


def test_hai_lan_dung_lien_tiep_sau_canh_bao_js_khong_mo_cau_dao(may):
    phien = t.PhienYouTube()
    _mot_lan_dung(phien)
    _mot_lan_dung(phien)
    so = phien.tom_tat()
    assert not phien.mo and so["breaker_open"] is False
    assert so["js_challenge_errors"] == 0 and so["breaker_events"] == []
    assert so["js_challenge_warnings"] == 2, "cảnh báo JS vẫn được đếm — chỉ lỗi cuối không bị đổ cho JS"


def test_loi_chua_phan_loai_sau_canh_bao_js_giu_nguyen_loi_goc(may):
    """Đĩa đầy (hay lỗi máy chưa phân loại — UNKNOWN) sau cảnh báo JS: không có bằng chứng là do JS → giữ lỗi gốc, đúng
    loại của nó, như đường không-cookie."""
    bo_ghi = y.BoGhiYtdlp(t.PhienYouTube())
    loi = OSError(28, "No space left on device")
    with pytest.raises(OSError) as ei:
        y.chay_kem_duong_lui_cookie(CO_COOKIE, _hong_sau_canh_bao_js(bo_ghi, loi), bo_ghi=bo_ghi)
    assert ei.value is loi
    assert t.phan_loai_loi(ei.value).category == t.UNKNOWN_YOUTUBE_ERROR


def test_dung_trong_luot_lui_khong_cookie_van_la_dung(may):
    """Cookie chết → lùi không cookie; bấm Dừng trong lượt lùi: không được ném lỗi GỐC (cookie chết) thay cho Dừng."""
    da_goi, loi = [], Cancelled()

    def chay(ch):
        da_goi.append(ch.co_cookie)
        if ch.co_cookie:
            raise _loi(LOI_COOKIE_CHET)
        raise loi

    with pytest.raises(Cancelled) as ei:
        y.chay_kem_duong_lui_cookie(CO_COOKIE, chay, bo_qua=LOI_DUNG)
    assert ei.value is loi and da_goi == [True, False]


# ---------------------------------------------------------------- phân loại: không gộp tất cả thành lỗi cookie

def test_bon_loai_loi_tach_rieng():
    loai = {
        "js": t.phan_loai_loi(y.CookieCanJs(y.thong_bao_cookie_can_js(THIEU_EJS), THIEU_EJS.ly_do)).category,
        "client": t.phan_loai_loi(_loi(LOI_RELOAD)).category,
        "cookie": t.phan_loai_loi(RuntimeError("The provided YouTube account cookies are no longer valid.")).category,
        "bot": t.phan_loai_loi(_loi(BOT)).category,
    }
    assert loai == {"js": t.JS_CHALLENGE_ERROR, "client": t.PLAYER_CLIENT_ERROR,
                    "cookie": t.COOKIE_INVALID_OR_EXPIRED, "bot": t.BOT_CHALLENGE}


def test_nguong_cau_dao_va_doi_client_cho_loai_moi():
    assert t.NGUONG_MO[t.JS_CHALLENGE_ERROR] == 2 and t.NGUONG_MO[t.PLAYER_CLIENT_ERROR] == 5
    assert t.JS_CHALLENGE_ERROR in t.DUNG_DOI_CLIENT, "có cookie thì mọi client nhận cookie đều cần JS"
    assert t.PLAYER_CLIENT_ERROR not in t.DUNG_DOI_CLIENT, "client khác có thể được"
    # cli.py / youtube-doctor in «YouTube chặn truy cập» + mã 3 cho LOAI_TRUY_CAP — máy thiếu JS không phải YouTube chặn.
    assert not ({t.JS_CHALLENGE_ERROR, t.PLAYER_CLIENT_ERROR} & t.LOAI_TRUY_CAP)


# ---------------------------------------------------------------- phiên + giao diện: nói đúng chế độ

def test_phien_ghi_khong_dang_nhap_khac_cookie_bi_tu_choi():
    p = t.PhienYouTube()
    p.ghi_lui_cookie(y.CookieCanJs(y.thong_bao_khong_dang_nhap(THIEU_EJS), THIEU_EJS.ly_do))
    assert p.cookie_bi_tu_choi is False, "YouTube KHÔNG từ chối cookie — máy thiếu bộ giải"
    so = p.tom_tat()
    assert so["cookie_unusable_no_js"] == 1 and so["cookie_fallbacks"] == 0
    assert so["cookie_unusable_reason"] == THIEU_EJS.ly_do
    dong = scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie("", cookies_browser="firefox"), p)
    assert dong[0][0] == "warning" and "KHÔNG đăng nhập" in dong[0][1] and "xuất lại" not in dong[0][1]


def test_cau_dao_mo_khi_dang_khong_dang_nhap_noi_ro():
    p = t.PhienYouTube()
    p.ghi_lui_cookie(y.CookieCanJs("x", THIEU_EJS.ly_do))
    p.ghi_loi(_loi(BOT))
    assert p.mo and "KHÔNG đăng nhập" in p.thong_bao_dung() and THIEU_EJS.ly_do in p.thong_bao_dung()


def test_trang_thai_ui_noi_ro_dung_cookie_hay_khong():
    cd = t.chan_doan_cookie("", cookies_browser="firefox")
    dung = scan_ui.dong_trang_thai_youtube(cd, None, SAN_SANG)
    assert dung[-1][0] == "info" and dung[-1][1].startswith(
        "Khi quét: DÙNG cookie đăng nhập — yt-dlp giải thử thách JavaScript bằng Node.js 24.21.0 + yt-dlp-ejs 0.8.0.")
    assert "CẤU HÌNH chưa có nghĩa là YouTube CHẤP NHẬN" in dung[-1][1]
    khong = scan_ui.dong_trang_thai_youtube(cd, None, THIEU_EJS)
    assert khong[-1][0] == "warning" and "CHƯA dùng được" in khong[-1][1] and "KHÔNG đăng nhập" in khong[-1][1]
    assert scan_ui.dong_trang_thai_youtube(t.chan_doan_cookie(""), None, THIEU_EJS) == [
        ("info", "Cookie: chưa cấu hình.")], "không cấu hình cookie thì không nói gì về JS"


def test_engine_canh_bao_khong_dang_nhap(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    e.canh_bao_mang = []
    loi = y.CookieCanJs(y.thong_bao_khong_dang_nhap(THIEU_EJS), THIEU_EJS.ly_do)
    e._canh_bao_cookie_chet(loi)
    e._canh_bao_cookie_chet(loi)
    assert len(e.canh_bao_mang) == 1, "không lặp lại cùng một cảnh báo cho mỗi lượt"
    assert "KHÔNG đăng nhập" in e.canh_bao_mang[0] and "hết hiệu lực" not in e.canh_bao_mang[0]


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


def _co_cookie(opts) -> bool:
    return bool(opts.get("cookiesfrombrowser") or opts.get("cookiefile"))


def _theo_cookie(loi_khi_co_cookie, ket_khi_khong):
    def hanh_vi(phien, ma):
        return loi_khi_co_cookie if _co_cookie(phien.opts) else ket_khi_khong(ma)
    return hanh_vi


def test_lo_may_chua_san_sang_khong_gui_request_dang_nhap_va_noi_ro(tmp_path, monkeypatch, may):
    """Đúng ca Stable 1.1.0 (thiếu gói yt-dlp-ejs): có cookie thì yt-dlp chắc chắn hỏng — không gửi request nào có
    cookie, mỗi video đúng một lần lấy thông tin + một lần tải, MỌI kết quả ghi rõ «KHÔNG đăng nhập»."""
    may(THIEU_EJS)
    ma = [f"vid{i:08d}" for i in range(6)]
    ydl = YdlKichBan(info={"*": _theo_cookie(LOI_RELOAD, info_mau)},
                     tai={"*": _theo_cookie(LOI_RELOAD, lambda _m: None)})
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert [k.status for k in ket].count("error") == 0, [k.note for k in ket]
    assert all(k.matches for k in ket)
    assert not any(_co_cookie(o) for o in ydl.opts), "không một request đăng nhập chắc chắn hỏng nào"
    assert ydl.dem("info") == 6 and ydl.dem("tai") == 6
    assert all("KHÔNG đăng nhập" in (k.note or "") and "yt-dlp-ejs" in (k.note or "") for k in ket)
    assert not any("hết hiệu lực" in (k.note or "") for k in ket), "cookie không chết — đừng dẫn sai hướng"
    phien = e.phien_youtube_cuoi
    assert phien is not None and phien.cookie_bi_tu_choi is False and phien.khong_dang_nhap_ly_do


def test_lo_may_san_sang_dung_cookie_va_node_moi_luot(tmp_path, monkeypatch, may):
    ma = [f"vid{i:08d}" for i in range(3)]
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert [k.status for k in ket].count("error") == 0
    assert ydl.dem("info") == 3 and ydl.dem("tai") == 3
    assert all(_co_cookie(o) and o.get("js_runtimes") == {"node": {"path": SAN_SANG.node}} for o in ydl.opts)
    assert not any("remote_components" in o for o in ydl.opts)
    assert not any("KHÔNG đăng nhập" in (k.note or "") for k in ket)


def test_lo_reload_mot_video_la_loi_truy_cap_khong_phai_am_tinh(tmp_path, monkeypatch, may):
    ma = [f"vid{i:08d}" for i in range(3)]
    ydl = YdlKichBan(info={ma[1]: LOI_RELOAD})
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert [k.status for k in ket] == ["ok", "error", "ok"], [k.note for k in ket]
    assert ket[1].loi_truy_cap is not None and ket[1].loi_truy_cap.category == t.PLAYER_CLIENT_ERROR
    assert not ket[1].matches
    lan_hoi = [(g, _co_cookie(o)) for g, o in zip(ydl.goi, ydl.opts) if g[1] == ma[1]]
    assert lan_hoi == [(("info", ma[1], ""), True)], "một lần, có cookie — không tự thử lại không đăng nhập"
    assert ma[1] not in e.ids_da_quet(), "video chưa quét không được tính là đã quét"


def test_lo_bot_dung_ca_lo_khong_lui_khong_cookie(tmp_path, monkeypatch, may):
    ma = [f"vid{i:08d}" for i in range(4)]
    ydl = YdlKichBan(info={"*": BOT})
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert len(ydl.goi) == 1 and _co_cookie(ydl.opts[0]), "một request rồi dừng — không thử lại không cookie"
    assert ket[0].loi_truy_cap.category == t.BOT_CHALLENGE
    assert all(k.loi_truy_cap.category == t.BLOCKED_BY_BREAKER for k in ket[1:])


def test_lo_bo_giai_js_hong_dung_sau_hai_video_khong_bo_dang_nhap(tmp_path, monkeypatch, may):
    def hong(phien, ma):
        phien.opts["logger"].warning(CANH_BAO_N.format(id=ma))
        return LOI_COOKIE_CHET

    ma = [f"vid{i:08d}" for i in range(4)]
    ydl = YdlKichBan(info={"*": hong})
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert all(_co_cookie(o) for o in ydl.opts), "không tự bỏ đăng nhập"
    assert ydl.dem("info") == 2, "cầu dao «JavaScript» mở sau hai video"
    assert [k.loi_truy_cap.category for k in ket] == [t.JS_CHALLENGE_ERROR] * 2 + [t.BLOCKED_BY_BREAKER] * 2
    assert not any("hết hiệu lực" in (k.note or "") for k in ket)


@pytest.mark.parametrize("kn", [SAN_SANG, THIEU_EJS])
def test_lo_khong_cookie_giu_nguyen_so_request(tmp_path, monkeypatch, may, kn):
    """Đường không-cookie đã nghiệm thu: mỗi video đúng một lần lấy thông tin + một lần tải, không cảnh báo, không JS
    — dù máy có sẵn Node/EJS hay không."""
    may(kn)
    ma = [f"vid{i:08d}" for i in range(3)]
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    e.config.ytdlp_cookies_browser = ""
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert [k.status for k in ket].count("error") == 0
    assert ydl.dem("info") == 3 and ydl.dem("tai") == 3
    assert not any(_co_cookie(o) or "js_runtimes" in o for o in ydl.opts)
    assert e.canh_bao_mang == []


@pytest.mark.parametrize("loi_ytdlp", ["ERROR: ffmpeg exited with code 1", LOI_COOKIE_CHET],
                         ids=["ffmpeg_bi_giet", "khong_con_dinh_dang"])
def test_lo_bam_dung_sau_canh_bao_js_ghi_da_huy_khong_ghi_loi_js(tmp_path, monkeypatch, may, loi_ytdlp):
    """Review F1 cả lô: bấm Dừng khi video đang tải (sau cảnh báo JS) → kết quả «Đã hủy theo yêu cầu.», không phải lỗi
    truy cập «JavaScript» — dù yt-dlp lúc đó báo gì; cầu dao không ghi lỗi nào; lô dừng như mọi lần bấm Dừng."""
    giu = {}

    def dung(phien, ma):
        phien.opts["logger"].warning(CANH_BAO_N.format(id=ma))
        giu["e"].cancel()                       # người dùng bấm Dừng → luồng giám sát giết ffmpeg → yt-dlp báo lỗi
        return loi_ytdlp

    ma = [f"vid{i:08d}" for i in range(3)]
    ydl = YdlKichBan(tai={"*": dung})
    e = giu["e"] = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert len(ket) == 1 and ydl.dem("tai") == 1, "Dừng: không thử client khác, không sang video sau"
    assert ket[0].note == "Đã hủy theo yêu cầu." and ket[0].ly_do_pham_vi == "huy"
    assert ket[0].loi_truy_cap is None
    so = e.phien_youtube_cuoi.tom_tat()
    assert so["js_challenge_errors"] == 0 and so["breaker_open"] is False


class _YdlDungSauCanhBaoJs:
    """yt-dlp giả cho ``Engine.download_audio`` tải PHẦN ĐẦU (qua ffmpeg): cảnh báo giải JS hỏng, ghi ``.part``, rồi
    người dùng bấm Dừng — luồng giám sát giết ffmpeg nên yt-dlp ném lỗi ``loi_ytdlp``."""

    def __init__(self, eng, loi_ytdlp):
        self.eng, self.loi_ytdlp = eng, loi_ytdlp

    def __call__(self, opts):
        eng, loi_ytdlp = self.eng, self.loi_ytdlp

        class _Phien:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def download(self, urls):
                opts["logger"].warning(CANH_BAO_N.format(id="v1"))
                with open(opts["outtmpl"].replace("%(ext)s", "webm") + ".part", "wb") as f:
                    f.write(b"audio do dang")
                eng.cancel()
                raise yt_dlp.utils.DownloadError(loi_ytdlp)

        return _Phien()


@pytest.mark.parametrize("loi_ytdlp", ["ERROR: ffmpeg exited with code 1", LOI_COOKIE_CHET.format(id="v1")],
                         ids=["ffmpeg_bi_giet", "khong_con_dinh_dang"])
def test_tai_phan_dau_bam_dung_sau_canh_bao_js_la_huy_va_don_file_do(tmp_path, monkeypatch, may, loi_ytdlp):
    """Ngữ nghĩa Dừng giữ nguyên: ``Cancelled`` ra khỏi ``download_audio`` (dù yt-dlp lúc đó báo gì) và nhánh dọn file
    dở của bản tải một phần vẫn chạy (lỗi JS ném ra trước đây đi vòng qua nhánh đó)."""
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ra"))
    e.config.ytdlp_sleep_requests_s = 0.0
    e.config.ytdlp_cookies_browser = "firefox"
    phien = t.PhienYouTube()
    monkeypatch.setattr(e, "phien_youtube_hien_tai", lambda: phien)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _YdlDungSauCanhBaoJs(e, loi_ytdlp))
    monkeypatch.setattr(giam_sat_tai, "ffmpeg_chia_khoi_duoc", lambda: True, raising=False)
    with pytest.raises(Cancelled):
        e.download_audio("https://youtu.be/v1", "v1", gioi_han_giay=10800)
    assert not list((tmp_path / "data").rglob("*.part")), "Dừng: file dở của bản tải một phần phải được dọn"
    so = phien.tom_tat()
    assert so["js_challenge_errors"] == 0 and not phien.mo


# ---------------------------------------------------------------- ghi chú kết quả không mang đường dẫn máy (review F3)

NODE_NGUOI_DUNG = r"C:\Users\Ten Nguoi Dung\AppData\Roaming\nvm\v22.12.0\node.exe"


def _chu_trong_db(duong_db) -> str:
    import contextlib
    import sqlite3

    with contextlib.closing(sqlite3.connect(duong_db)) as db:
        bang = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return "\n".join(str(o) for b in bang for dong in db.execute(f'SELECT * FROM "{b}"') for o in dong)


def test_lo_node_khong_chay_duoc_ghi_chu_lich_su_csv_khong_mang_duong_dan(tmp_path, monkeypatch, kha_nang_js_that):
    """Node có nhưng ``--version`` hỏng (hết giờ, file hỏng): câu «KHÔNG đăng nhập» đi vào GHI CHÚ mọi kết quả → lịch sử,
    CSV dọc/ngang, cột ghi chú của Google Sheets. Đường dẫn node thường nằm trong thư mục người dùng Windows (nvm,
    %APPDATA%) — câu chỉ được nói «node --version», không đường dẫn, không tên người dùng."""
    monkeypatch.setattr(y, "_tim_node", lambda: NODE_NGUOI_DUNG)
    monkeypatch.setattr(y, "_phien_ban_node", lambda _p: "")
    monkeypatch.setattr(y, "_kiem_ejs", lambda: ("0.8.0", "0.8.0", ""))
    ma = [f"vid{i:08d}" for i in range(2)]
    ydl = YdlKichBan()
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    assert len(ket) == 2 and not any(_co_cookie(o) for o in ydl.opts), "máy chưa sẵn sàng: không gửi cookie"
    assert all("KHÔNG đăng nhập" in (k.note or "") and "node --version" in k.note for k in ket), [k.note for k in ket]
    noi = [*(k.note for k in ket), str(e.to_rows(ket)), str(e.to_rows_ngang(ket)), _chu_trong_db(e.sqlite_file),
           str(e.phien_youtube_cuoi.tom_tat()), e.phien_youtube_cuoi.thong_bao_dung()]
    for chu in noi:
        assert "Ten Nguoi Dung" not in chu and "AppData" not in chu and NODE_NGUOI_DUNG not in chu


@pytest.mark.parametrize("loi_ytdlp,canh_bao,dau_hieu", [
    (LOI_COOKIE_CHET,
     '[youtube] [jsc:node] Error solving n challenge request using "node" provider: Error running node process '
     r"(returncode: 1): Error: EPERM: operation not permitted, open 'C:\Users\Ten Nguoi Dung\AppData\Local\Temp\jsc.js'.",
     "Error solving n challenge request"),
    # thư mục người dùng ở CUỐI lỗi yt-dlp, không dấu phân cách theo sau: không được nuốt cả cảnh báo JS phía sau « | »
    (LOI_COOKIE_CHET + r" (cwd C:\Users\Ten Nguoi Dung", CANH_BAO_N, "n challenge solving failed"),
], ids=["duong_dan_trong_canh_bao", "duong_dan_cuoi_loi_ytdlp"])
def test_bo_giai_js_hong_chi_tiet_che_thu_muc_nguoi_dung(may, loi_ytdlp, canh_bao, dau_hieu):
    """Chi tiết kỹ thuật của LoiGiaiJs (lỗi yt-dlp + cảnh báo giải JS) cũng đi vào ghi chú kết quả; chữ của yt-dlp/Node có
    thể mang đường dẫn trong thư mục người dùng → che thành «~», giữ phần còn lại để chẩn đoán."""
    bo_ghi = y.BoGhiYtdlp(t.PhienYouTube())

    def chay(_ch):
        bo_ghi.warning(canh_bao.format(id="OPgD5wl0fAY"))
        raise _loi(loi_ytdlp)

    with pytest.raises(y.LoiGiaiJs) as ei:
        y.chay_kem_duong_lui_cookie(CO_COOKIE, chay, bo_ghi=bo_ghi)
    f = t.phan_loai_loi(ei.value)
    assert dau_hieu in f.technical_summary and "~" in f.technical_summary, f.technical_summary
    for chu in (f.technical_summary, str(t.LoiTruyCapYouTube(f)), y.giai_thich_loi(t.LoiTruyCapYouTube(f), True)):
        assert "Ten Nguoi Dung" not in chu and "Users" not in chu


@pytest.mark.parametrize("vao,ra", [
    (r"open 'C:\Users\Ten Nguoi Dung\AppData\x.js'", r"open '~\AppData\x.js'"),
    (r"open 'C:\\Users\\Ten\\AppData\\x.js'", r"open '~\\AppData\\x.js'"),
    ("file:///C:/Users/Ten/AppData/x.js", "file:///~/AppData/x.js"),
    (r"D:\Documents and Settings\Ten\x", r"~\x"),
    ("https://github.com/yt-dlp/yt-dlp/wiki/EJS", "https://github.com/yt-dlp/yt-dlp/wiki/EJS"),
    (r"C:\TimClipPro\runtimes\py312\x.js", r"C:\TimClipPro\runtimes\py312\x.js"),
    # review (P3): không nuốt phần chẩn đoán sau tên; tên có dấu nháy không lộ đuôi; tên bị cắt «…»; nháy đóng ngay sau tên
    (r"cwd C:\Users\Admin | [youtube] Error solving n challenge request", r"cwd ~ | [youtube] Error solving n challenge request"),
    (r"open 'C:\Users\O'Brien\AppData\x.js'", r"open '~\AppData\x.js'"),
    (r"open 'C:\Users\O'Đức\AppData\x.js'", r"open '~\AppData\x.js'"),
    ("C:\\Users\\Ten'2", "~"),
    ("lỗi C:\\Users\\Ten Ngu… | [youtube] x", "lỗi ~… | [youtube] x"),
    ("open 'C:\\\\Users\\\\Admin'. Next", "open '~'. Next"),
])
def test_che_thu_muc_nguoi_dung(vao, ra):
    assert y.an_thu_muc_nguoi_dung(vao) == ra
    assert y.an_thu_muc_nguoi_dung(ra) == ra, "luỹ đẳng"


# ---------------------------------------------------------------- tải phần đầu (Marathon): Range khối 10 MiB giữ nguyên

class _YdlGhi:
    def __init__(self):
        self.opts: list = []

    def __call__(self, opts):
        self.opts.append(opts)

        class _Phien:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def download(self, urls):
                with open(opts["outtmpl"].replace("%(ext)s", "webm"), "wb") as f:
                    f.write(b"audio gia")

        return _Phien()


@pytest.mark.parametrize("cookie", ["firefox", ""])
def test_tai_phan_dau_giu_request_size_va_chi_bat_node_khi_co_cookie(tmp_path, monkeypatch, may, cookie):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ra"))
    e.config.ytdlp_player_clients = [""]
    e.config.ytdlp_sleep_requests_s = 0.0
    e.config.ytdlp_cookies_browser = cookie
    ghi = _YdlGhi()
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ghi)
    monkeypatch.setattr(giam_sat_tai, "ffmpeg_chia_khoi_duoc", lambda: True, raising=False)
    e.download_audio("https://youtu.be/v1", "v1", gioi_han_giay=10800)
    opts = ghi.opts[-1]
    assert opts["external_downloader_args"]["ffmpeg_i"] == ["-request_size", str(giam_sat_tai.KHOI_YEU_CAU_TAI)]
    assert opts["external_downloader_args"]["ffmpeg_o"][0] == "-progress"
    assert callable(opts["download_ranges"]) and opts["force_keyframes_at_cuts"] is False
    if cookie:
        assert opts["js_runtimes"] == {"node": {"path": SAN_SANG.node}}
    else:
        assert "js_runtimes" not in opts and not _co_cookie(opts)
