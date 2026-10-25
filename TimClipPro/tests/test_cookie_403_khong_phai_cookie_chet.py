# -*- coding: utf-8 -*-
"""Audit D-2 (P1): cookie đăng nhập CÒN SỐNG bị báo «hết hiệu lực» khi mọi client nhận cookie hỏng vì lý do KHÁC (403).

Cơ chế (yt-dlp 2026.08.19, `extractor/youtube/_video.py` ~3009-3019): phiên có cookie đăng nhập (LOGIN_INFO + SAPISID →
`is_authenticated`) thì yt-dlp GỠ mọi client không `SUPPORTS_COOKIES` (android, ios…). `sap_xep_player_clients` đẩy chính
các client đó xuống CUỐI danh sách, nên lượt cuối của `thu_tung_client` luôn là một client bị gỡ → yt-dlp chỉ còn
`initial_pr` đã bóc `streamingData` → «No video formats found!». `thu_tung_client` chỉ mang «Lỗi cuối» → khớp
`DAU_HIEU_COOKIE_CHET` → đường lui cookie gán nhãn «cookie hết hiệu lực», dù nguyên nhân thật là HTTP 403 ở khâu tải.

Hành vi ĐÚNG mà test này đòi: cookie không bị gán nhãn chết/bị từ chối khi các client nhận cookie hỏng vì 403.
yt-dlp GIẢ theo kịch bản (`tests/ytdlp_gia.py`), cookie GIẢ trong tmp_path, không mạng.
"""

import shutil
from pathlib import Path

import pytest
import yt_dlp

import channel
import truy_cap_youtube as t
import ytdlp_chung as y
from channel import ChannelSync
from engine import Engine, Match, ScanResult, chu_ky_chinh_sach
from kho_gia import ghi_kho
from ytdlp_gia import BOT, C403, YdlKichBan

SAN_SANG = y.KhaNangJs(True, node=r"C:\gia\nodejs\node.exe", node_phien_ban="24.21.0", ejs_phien_ban="0.8.0")
KHONG_DINH_DANG = ("ERROR: [youtube] {id}: No video formats found!; please report this issue on "
                   "https://github.com/yt-dlp/yt-dlp/issues")
BI_MAT = "GIA-BI-MAT-D2-KHONG-DUOC-LO"


def _cookie_gia(p: Path) -> str:
    p.write_text("# Netscape HTTP Cookie File\n"
                 f".youtube.com\tTRUE\t/\tTRUE\t4102444800\tLOGIN_INFO\t{BI_MAT}a\n"
                 f".youtube.com\tTRUE\t/\tTRUE\t4102444800\tSAPISID\t{BI_MAT}b\n"
                 f".youtube.com\tTRUE\t/\tTRUE\t4102444800\t__Secure-3PSID\t{BI_MAT}c\n", encoding="utf-8")
    return str(p)


def _co_cookie(opts) -> bool:
    return bool(opts.get("cookiefile") or opts.get("cookiesfrombrowser"))


def _tai_403_khi_co_cookie(phien, ma):
    """Đúng yt-dlp thật với cookie đăng nhập: client không hỗ trợ cookie bị gỡ → không định dạng; client nhận cookie →
    tải bị 403 (googlevideo); không cookie → tải được."""
    if _co_cookie(phien.opts):
        if phien.client in y.client_khong_ho_tro_cookie():
            return KHONG_DINH_DANG
        return C403
    return None


@pytest.fixture
def may(monkeypatch):
    monkeypatch.setattr(y, "kha_nang_js", lambda: SAN_SANG)
    for k in ("metadata", "listing", "download"):
        if k in t.NGAN_SACH:
            monkeypatch.setitem(t.NGAN_SACH, k, t.NganSach(cho_tam_thoi=(0.01,), cho_429=(0.01,)))
    monkeypatch.setattr(channel, "do_dai_media", lambda p: 600.0)
    monkeypatch.setattr(channel, "do_dai_luong_tieng", lambda p: 600.0)


# ---------------------------------------------------------------- 0. tiền đề: thứ tự client có cookie

def test_tien_de_client_bi_go_dung_cuoi_khi_co_cookie():
    ds = y.sap_xep_player_clients(list(y.PLAYER_CLIENTS_MAC_DINH), co_cookie=True)
    assert ds[-1] in y.client_khong_ho_tro_cookie(), ds


# ---------------------------------------------------------------- 1. chuỗi thu_tung_client + đường lui cookie

def test_403_o_moi_client_nhan_cookie_khong_bi_gan_nhan_cookie_chet(tmp_path, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    nhan, goi = [], []

    def chay(rieng):
        client = ((rieng.get("extractor_args") or {}).get("youtube", {}).get("player_client") or [""])[0]
        goi.append((client, _co_cookie(rieng)))
        if _co_cookie(rieng):
            raise RuntimeError((KHONG_DINH_DANG if client in y.client_khong_ho_tro_cookie() else C403)
                               .format(id="abcdefghijk"))
        return "ok"

    def tai_voi(cau_hinh):
        return y.thu_tung_client(cau_hinh.player_clients(list(y.PLAYER_CLIENTS_MAC_DINH)), chay,
                                 cau_hinh.tuy_chon("download"))

    try:
        y.chay_kem_duong_lui_cookie(ch, tai_voi, khi_bo_cookie=nhan.append)
    except Exception as e:  # noqa: BLE001 — hành vi đúng có thể là ném lỗi 403
        assert "403" in str(e), f"lỗi phải nói đúng nguyên nhân thật (403): {e}"
    gan_nhan_chet = [n for n in nhan if y.la_dau_hieu_cookie_chet(n)]
    assert not gan_nhan_chet, (
        "cookie còn sống, mọi client nhận cookie hỏng vì HTTP 403 — không được coi là dấu hiệu cookie chết; "
        f"khi_bo_cookie nhận: {[str(n)[:220] for n in nhan]}; các lượt: {goi}")


# ---------------------------------------------------------------- 2. lô quét Engine: ghi chú kết quả + phiên

def _eng(tmp_path, monkeypatch, ydl) -> Engine:
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    thu_muc = tmp_path / "kho"
    thu_muc.mkdir(exist_ok=True)
    e.add_kho("A", str(thu_muc))
    ghi_kho(e.db_file, [(str(thu_muc / "goc [ggggggggggg].opus"), 9)])
    e.use_kho("A")
    e.config.ytdlp_sleep_requests_s = 0.0
    e.config.ytdlp_cookiefile = _cookie_gia(tmp_path / "cookies.txt")
    e.config.ytdlp_cookies_browser = ""
    monkeypatch.setattr(Engine, "require", lambda self, **k: None)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
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


def test_lo_quet_403_khong_bao_cookie_het_hieu_luc(tmp_path, monkeypatch, may):
    ydl = YdlKichBan(tai={"*": _tai_403_khi_co_cookie})
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter(["https://youtu.be/abcdefghijk"]))
    assert len(ket) == 1
    lan_tai = [(g[2] or "mặc định", _co_cookie(o)) for g, o in zip(ydl.goi, ydl.opts) if g[0] == "tai"]
    phien = e.phien_youtube_cuoi
    ghi_chu = ket[0].note or ""
    assert "hết hiệu lực" not in ghi_chu and not any("hết hiệu lực" in c for c in e.canh_bao_mang), (
        f"cookie còn sống (403 ở khâu tải) mà ghi chú kết quả bảo «hết hiệu lực»: {ghi_chu!r}; lượt tải: {lan_tai}")
    assert phien is not None and phien.cookie_bi_tu_choi is False, "phiên ghi cookie bị YouTube từ chối — sai"


# ---------------------------------------------------------------- 3. đồng bộ kênh: trạng thái xác thực

def _danh_sach(ids):
    return {"_type": "playlist", "id": "UCkenh_d2", "entries": [
        {"id": m, "title": f"Video {m}", "url": f"https://www.youtube.com/watch?v={m}", "duration": 600.0}
        for m in ids]}


def test_dong_bo_kenh_403_khong_thanh_bi_tu_choi(tmp_path, monkeypatch, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    ydl = YdlKichBan(tai={"*": _tai_403_khi_co_cookie}, liet_ke=lambda _p, _u: _danh_sach(["d2abcdefghi"]))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    cs = ChannelSync(str(tmp_path / "KenhD2"), cau_hinh_mang=ch)

    def nen(nguon, tam, _tham_chieu, _huy):
        shutil.copyfile(nguon, tam)
        return ""
    cs._nen_va_kiem = nen
    r = cs.sync("https://www.youtube.com/@KenhThuD2")
    lan_tai = [(g[2] or "mặc định", _co_cookie(o)) for g, o in zip(ydl.goi, ydl.opts) if g[0] == "tai"]
    assert r["xac_thuc"]["trang_thai"] != "BI_TU_CHOI", (
        f"cookie còn sống (403 ở khâu tải) mà đồng bộ báo «{r['xac_thuc']['cau']}»; lượt tải: {lan_tai}")
    assert BI_MAT not in str(r)


# ---------------------------------------------------------------- 4. không sửa quá tay

def test_cookie_chet_that_van_lui_khong_cookie_qua_duong_lui_client(tmp_path, may):
    """Cookie chết thật (mọi client NHẬN cookie chỉ còn storyboard → «Requested format is not available»; client bị gỡ →
    «No video formats found!»): vẫn lùi không cookie như mục 10 LOI_DA_GAP, báo đúng một lần."""
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    nhan, goi = [], []

    def chay(rieng):
        client = ((rieng.get("extractor_args") or {}).get("youtube", {}).get("player_client") or [""])[0]
        goi.append((client, _co_cookie(rieng)))
        if _co_cookie(rieng):
            raise RuntimeError(KHONG_DINH_DANG.format(id="abcdefghijk") if client in y.client_khong_ho_tro_cookie()
                               else "ERROR: [youtube] abcdefghijk: Requested format is not available")
        return "ok"

    def tai_voi(cau_hinh):
        return y.thu_tung_client(cau_hinh.player_clients(list(y.PLAYER_CLIENTS_MAC_DINH)), chay,
                                 cau_hinh.tuy_chon("download"))

    assert y.chay_kem_duong_lui_cookie(ch, tai_voi, khi_bo_cookie=nhan.append) == "ok"
    assert len(nhan) == 1 and y.la_dau_hieu_cookie_chet(nhan[0])
    assert "Requested format is not available" in str(nhan[0]), "đại diện là lỗi của client NHẬN cookie"
    assert goi[-1] == ("", False) and BI_MAT not in str(nhan[0])


def test_loi_that_cua_client_khong_nhan_cookie_van_la_dai_dien():
    """Chỉ «không định dạng» của client không nhận cookie bị bỏ qua; lỗi thật của nó (bot-check làm dừng đổi client)
    vẫn là lỗi đại diện — cầu dao «xác minh» phải mở như cũ."""
    def chay(rieng):
        client = ((rieng.get("extractor_args") or {}).get("youtube", {}).get("player_client") or [""])[0]
        raise RuntimeError((BOT if client == "android" else C403).format(id="abcdefghijk"))

    with pytest.raises(RuntimeError) as ei:
        y.thu_tung_client(["", "tv", "android"], chay, {"cookiefile": "c.txt"},
                          dung_ngay=t.PhienYouTube().nen_dung_doi_client)
    assert "Lỗi cuối: " in str(ei.value)
    assert t.phan_loai_loi(ei.value).category == t.BOT_CHALLENGE


# ---------------------------------------------------------------- 5. review audit D: 403 ở mọi client nhận cookie không làm MẤT video
#
# Trước e23c71b, «không định dạng» của client bị gỡ làm đại diện → đường lui cookie lùi không cookie cả lượt → `android`
# KHÔNG cookie tải được (gán nhãn sai «cookie hết hiệu lực»). Sau e23c71b nhãn đúng (403) nhưng video hỏng hẳn, 3 video
# liền mở cầu dao HTTP_FORBIDDEN dừng cả lô (LOI_DA_GAP 6/6c: chế độ «chỉ android tải được» đã gặp thật). Hành vi đòi:
# thử CHÍNH các client đã bị yt-dlp gỡ vì cookie đăng nhập, KHÔNG cookie, báo rõ «KHÔNG đăng nhập» — không gọi là cookie
# chết, không ghi «bị từ chối», không nhớ cho cả lượt.

def _client(rieng) -> str:
    return ((rieng.get("extractor_args") or {}).get("youtube", {}).get("player_client") or [""])[0]


def _chay_403_khi_co_cookie(goi, khong_cookie=lambda _client: "ok"):
    def chay(rieng):
        client = _client(rieng)
        goi.append((client, _co_cookie(rieng)))
        if _co_cookie(rieng):
            raise RuntimeError((KHONG_DINH_DANG if client in y.client_khong_ho_tro_cookie() else C403)
                               .format(id="abcdefghijk"))
        kq = khong_cookie(client)
        if isinstance(kq, str) and kq.startswith("ERROR"):
            raise RuntimeError(kq.format(id="abcdefghijk"))
        return kq
    return chay


def test_403_o_moi_client_nhan_cookie_tai_bang_client_bi_go_khong_cookie_va_bao_ro(tmp_path, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    goi, nhan, lui, xong = [], [], [], []
    chay = _chay_403_khi_co_cookie(goi)

    def tai_voi(cau_hinh):
        return y.thu_tung_client(cau_hinh.player_clients(list(y.PLAYER_CLIENTS_MAC_DINH)), chay,
                                 cau_hinh.tuy_chon("download"),
                                 khi_thanh_cong=lambda ten, _d: xong.append(ten),
                                 khi_lui_khong_cookie=lambda ten, loi: lui.append((ten, loi)))

    assert y.chay_kem_duong_lui_cookie(ch, tai_voi, khi_bo_cookie=nhan.append) == "ok", goi
    assert nhan == [], "403 không phải cookie chết: đường lui COOKIE không được chạy"
    bi_go = [c for c, co in goi if co and c in y.client_khong_ho_tro_cookie()]
    assert len(lui) == 1 and lui[0][0] == bi_go[0], (lui, goi)
    assert "403" in str(lui[0][1]) and not y.la_dau_hieu_cookie_chet(lui[0][1]), "lý do báo phải là 403 thật"
    khong_cookie = [g for g in goi if not g[1]]
    assert khong_cookie == [(bi_go[0], False)], f"chỉ thử client bị gỡ, KHÔNG cookie, đúng một lần: {goi}"
    assert "không cookie" in xong[0], xong


def test_khong_truyen_khi_lui_khong_cookie_thi_khong_bao_gio_bo_cookie(tmp_path, may):
    """Bên gọi không cam kết báo «KHÔNG đăng nhập» thì không có lượt không cookie nào (no silent auth drop)."""
    goi = []
    opts = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt")).tuy_chon("download")
    with pytest.raises(RuntimeError, match="403"):
        y.thu_tung_client(y.sap_xep_player_clients(list(y.PLAYER_CLIENTS_MAC_DINH), True),
                          _chay_403_khi_co_cookie(goi), opts)
    assert all(co for _c, co in goi), goi


@pytest.mark.parametrize("loi_nhan_cookie", [
    "ERROR: [youtube] {id}: The page needs to be reloaded.",
    "ERROR: [youtube] abcdefghijk: Requested format is not available",
])
def test_dai_dien_khong_phai_403_thi_khong_lui_client_khong_cookie(tmp_path, may, loi_nhan_cookie):
    goi = []

    def chay(rieng):
        client = _client(rieng)
        goi.append((client, _co_cookie(rieng)))
        if _co_cookie(rieng) and client in y.client_khong_ho_tro_cookie():
            raise RuntimeError(KHONG_DINH_DANG.format(id="abcdefghijk"))
        raise RuntimeError(loi_nhan_cookie.format(id="abcdefghijk"))

    opts = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt")).tuy_chon("download")
    with pytest.raises(RuntimeError):
        y.thu_tung_client(y.sap_xep_player_clients(list(y.PLAYER_CLIENTS_MAC_DINH), True), chay, opts,
                          khi_lui_khong_cookie=lambda *_a: None)
    assert all(co for _c, co in goi), f"chỉ 403 mới lùi client không cookie: {goi}"


def test_client_khong_cookie_bi_bot_check_thi_dung_va_bot_la_dai_dien(tmp_path, may):
    """Lượt không cookie gặp bot-check: dừng ngay (không thử client bị gỡ kế), bot-check là đại diện để cầu dao «xác
    minh» mở — không lặp request ẩn danh vào bức tường (mục 6c)."""
    goi = []
    opts = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt")).tuy_chon("download")
    with pytest.raises(RuntimeError) as ei:
        y.thu_tung_client(y.sap_xep_player_clients(list(y.PLAYER_CLIENTS_MAC_DINH), True),
                          _chay_403_khi_co_cookie(goi, khong_cookie=lambda _c: BOT), opts,
                          dung_ngay=t.PhienYouTube().nen_dung_doi_client,
                          khi_lui_khong_cookie=lambda *_a: None)
    assert t.phan_loai_loi(ei.value).category == t.BOT_CHALLENGE
    assert len([g for g in goi if not g[1]]) == 1, goi


def test_lo_quet_403_moi_client_nhan_cookie_van_quet_xong_khong_mo_cau_dao(tmp_path, monkeypatch, may):
    ma = ["abcdefghij1", "abcdefghij2", "abcdefghij3", "abcdefghij4"]
    ydl = YdlKichBan(tai={"*": _tai_403_khi_co_cookie})
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ma]))
    phien = e.phien_youtube_cuoi
    assert [k.status for k in ket] == ["ok"] * len(ma), [(k.status, k.note) for k in ket]
    for k in ket:
        assert "KHÔNG đăng nhập" in k.note and "403" in k.note and "hết hiệu lực" not in k.note, k.note
        assert BI_MAT not in k.note
    assert phien is not None and not phien.mo and phien.cookie_bi_tu_choi is False
    assert phien.cookie_chet_trong_luot is False
    assert phien.tom_tat()["anonymous_client_downloads"] == len(ma)


def test_dong_bo_kenh_403_moi_client_nhan_cookie_van_tai_va_bao_khong_dang_nhap(tmp_path, monkeypatch, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    ma = ["d2abcdefgh1", "d2abcdefgh2", "d2abcdefgh3", "d2abcdefgh4"]
    ydl = YdlKichBan(tai={"*": _tai_403_khi_co_cookie}, liet_ke=lambda _p, _u: _danh_sach(ma))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    cs = ChannelSync(str(tmp_path / "KenhD2b"), cau_hinh_mang=ch)

    def nen(nguon, tam, _tham_chieu, _huy):
        shutil.copyfile(nguon, tam)
        return ""
    cs._nen_va_kiem = nen
    r = cs.sync("https://www.youtube.com/@KenhThuD2b")
    assert r["moi"] == len(ma) and not r["chan_youtube"], (r["moi"], r["loi"], r["chan_youtube"])
    assert r["xac_thuc"]["trang_thai"] != "BI_TU_CHOI"
    assert "KHÔNG đăng nhập" in r["xac_thuc"]["cau"] and "403" in r["xac_thuc"]["cau"], r["xac_thuc"]["cau"]
    assert r["youtube"]["anonymous_client_downloads"] == len(ma)
    assert BI_MAT not in str(r)
