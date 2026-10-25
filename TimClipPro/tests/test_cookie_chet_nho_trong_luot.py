# -*- coding: utf-8 -*-
"""Audit D-12 — cookie bị YouTube từ chối (cookie «chết» nhưng VẪN mang tên LOGIN_INFO/SAPISID) không được nhớ ở
mức lượt chạy: MỖI video lại thử đủ 5 player client có cookie rồi mới lùi không cookie (~6 phiên yt-dlp/video) suốt
cả lượt đồng bộ kênh, không có cầu dao.

Đúng (CLAUDE.md mục 6c — khuếch đại request là thứ kích bot-check; docstring ``PhienYouTube``: «một lượt chạy»): khi
lượt đồng bộ đã biết YouTube từ chối cookie (``cookie_bi_tu_choi``), các video sau KHÔNG được lặp lại cả chuỗi thử có
cookie — hoặc lượt tự chạy không cookie (đã báo rõ), hoặc dừng lô; số phiên tải phải xấp xỉ số video, không phải ×6.

Hoàn toàn synthetic: yt-dlp giả theo kịch bản (`tests/ytdlp_gia.py`), file cookie GIẢ trong tmp_path, máy giả lập đủ
Node + EJS, FFmpeg/ffprobe giả. Không mạng.

Sửa (``ytdlp_chung.chay_kem_duong_lui_cookie`` bước 5): lượt tải lùi không cookie THÀNH CÔNG sau dấu hiệu cookie chết là
đối chứng, ghi vào ``PhienYouTube`` của lượt; thao tác sau của lượt chạy thẳng không cookie và vẫn báo rõ. Các test sau
test repro khoá phần không được sửa quá tay: không đối chứng thì không nhớ, lấy thông tin chỉ đọc ghi nhớ, chỉ sống trong
một lượt, video đòi đăng nhập vẫn thử cookie, bot-check không kéo thêm request có cookie, đường quét lô (engine) cũng hết
khuếch đại mà kết quả nào cũng ghi rõ.
"""

import shutil

import pytest
import yt_dlp

import channel
import truy_cap_youtube as t
import ytdlp_chung as y
from channel import ChannelSync
from engine import Engine, Match, ScanResult, chu_ky_chinh_sach
from kho_gia import ghi_kho
from ytdlp_gia import AUTH, BOT, GO, YdlKichBan, info_mau

SAN_SANG = y.KhaNangJs(True, node=r"C:\gia\nodejs\node.exe", node_phien_ban="24.21.0", ejs_phien_ban="0.8.0")
LOI_COOKIE_CHET = "ERROR: [youtube] {id}: Requested format is not available"
DAI = 600.0
SO_VIDEO = 20
URL_KENH = "https://www.youtube.com/@KenhThuCookieChet"


def _ma(i: int) -> str:
    return f"k{i:010d}"                 # 11 ký tự như mã YouTube


def _danh_sach(ids):
    return {"_type": "playlist", "id": "UCkenh_d12", "entries": [
        {"id": m, "title": f"Video {m}", "url": f"https://www.youtube.com/watch?v={m}", "duration": DAI}
        for m in ids]}


def _cookie_gia(p) -> str:
    """Cookie GIẢ đúng định dạng Netscape, mang TÊN cookie tài khoản (yt-dlp coi là đã đăng nhập) — giá trị vô nghĩa."""
    p.write_text("# Netscape HTTP Cookie File\n"
                 ".youtube.com\tTRUE\t/\tTRUE\t4102444800\tLOGIN_INFO\tgia-d12-a\n"
                 ".youtube.com\tTRUE\t/\tTRUE\t4102444800\tSAPISID\tgia-d12-b\n"
                 ".youtube.com\tTRUE\t/\tTRUE\t4102444800\t__Secure-3PSID\tgia-d12-c\n", encoding="utf-8")
    return str(p)


@pytest.fixture()
def may(monkeypatch):
    monkeypatch.setattr(y, "kha_nang_js", lambda: SAN_SANG)
    for k in ("metadata", "listing"):
        monkeypatch.setitem(t.NGAN_SACH, k, t.NganSach(cho_tam_thoi=(0.01,), cho_429=(0.01,)))
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    monkeypatch.setattr(channel, "do_dai_luong_tieng", lambda p: DAI)


def _tai_cookie_chet(phien, ma):
    """YouTube xoay vòng phiên: có cookie (SID chết) → chỉ còn storyboard → «Requested format is not available»;
    không cookie → tải được bình thường."""
    if "cookiefile" in phien.opts or "cookiesfrombrowser" in phien.opts:
        return LOI_COOKIE_CHET
    return None


def test_cookie_bi_tu_choi_khong_thu_lai_ca_chuoi_client_co_cookie_cho_moi_video(tmp_path, monkeypatch, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    ids = [_ma(i) for i in range(SO_VIDEO)]
    ydl = YdlKichBan(tai={"*": _tai_cookie_chet}, liet_ke=lambda _p, _u: _danh_sach(ids))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)

    cs = ChannelSync(str(tmp_path / "Kenh"), cau_hinh_mang=ch)

    def nen(nguon, tam, _tham_chieu, _huy):
        shutil.copyfile(nguon, tam)
        return ""
    cs._nen_va_kiem = nen

    r = cs.sync(URL_KENH)

    tai = [i for i, g in enumerate(ydl.goi) if g[0] == "tai"]
    co_cookie = [i for i in tai if "cookiefile" in ydl.opts[i] or "cookiesfrombrowser" in ydl.opts[i]]
    so_tai, so_co_cookie = len(tai), len(co_cookie)
    yt = r.get("youtube") or {}
    tom_tat = (f"tai={so_tai} (co_cookie={so_co_cookie}) cho {SO_VIDEO} video; moi={r.get('moi')}; "
               f"cookie_fallbacks={yt.get('cookie_fallbacks')}; client_fallbacks={yt.get('client_fallbacks')}; "
               f"download_attempts={yt.get('download_attempts')}; trang_thai={r.get('trang_thai')}; "
               f"video dau: {[(ydl.goi[i][2] or 'mac_dinh', i in co_cookie) for i in tai[:6]]}")
    print(tom_tat)

    # Cookie đã bị từ chối ngay ở video đầu (lượt có cookie hỏng hết client, lùi không cookie thì được).
    assert so_co_cookie >= 1, "thiết lập sai: lượt có cookie phải được thử ít nhất một lần"

    # ĐÚNG: biết cookie bị từ chối rồi thì không lặp lại chuỗi 5 client có cookie cho từng video. Cho phép video đầu
    # (≤ 5 lượt có cookie) + vài lượt dò lại; KHÔNG được ~5 lượt có cookie × mỗi video.
    assert so_co_cookie <= 10, (
        "cookie bị YouTube từ chối không được nhớ ở mức lượt chạy — mỗi video lại thử đủ chuỗi client có cookie: "
        + tom_tat)
    assert so_tai <= SO_VIDEO + 10, "khuếch đại request (CLAUDE.md 6c): " + tom_tat


# ---------------------------------------------------------------- 2. đường lui cookie + phiên (đơn vị)

def _co_cookie(opts) -> bool:
    return bool(opts.get("cookiefile") or opts.get("cookiesfrombrowser"))


class _TaiGia:
    """``chay`` giả cho ``chay_kem_duong_lui_cookie``: đường lui client thật, mỗi lượt client ghi ``(client, có cookie)``.
    ``co_cookie``/``khong_cookie``: khuôn lỗi yt-dlp (chuỗi) hoặc ``None`` = tải được."""

    def __init__(self, phien, co_cookie=LOI_COOKIE_CHET, khong_cookie=None):
        self.phien, self.co_cookie, self.khong_cookie = phien, co_cookie, khong_cookie
        self.goi: list = []

    def __call__(self, cau_hinh):
        return y.thu_tung_client(cau_hinh.player_clients(list(y.PLAYER_CLIENTS_MAC_DINH)), self._chay,
                                 cau_hinh.tuy_chon("download"), dung_ngay=self.phien.nen_dung_doi_client)

    def _chay(self, rieng):
        client = ((rieng.get("extractor_args") or {}).get("youtube", {}).get("player_client") or [""])[0]
        co = _co_cookie(rieng)
        self.goi.append((client, co))
        loi = self.co_cookie if co else self.khong_cookie
        if loi:
            raise RuntimeError(loi.format(id="abcdefghijk"))
        return "co_cookie" if co else "khong_cookie"


def _bao_vao(phien, nhan):
    def bao(loi):
        nhan.append(loi)
        phien.ghi_lui_cookie(loi)
    return bao


def test_doi_chung_cookie_chet_ghi_vao_phien_thao_tac_sau_chay_thang_khong_cookie(tmp_path, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    phien, nhan = t.PhienYouTube(), []
    tai = _TaiGia(phien)
    assert y.chay_kem_duong_lui_cookie(ch, tai, khi_bo_cookie=_bao_vao(phien, nhan), phien=phien) == "khong_cookie"
    assert phien.cookie_chet_trong_luot is True, "lùi không cookie thành công = đối chứng cookie chết"
    n = len(tai.goi)
    assert y.chay_kem_duong_lui_cookie(ch, tai, khi_bo_cookie=_bao_vao(phien, nhan), phien=phien) == "khong_cookie"
    assert tai.goi[n:] == [("", False)], f"đã biết cookie chết: đúng MỘT phiên không cookie, không gửi cookie: {tai.goi}"
    assert len(nhan) == 2 and isinstance(nhan[1], y.CookieChetTrongLuot), "thao tác chạy không cookie vẫn được BÁO"
    so = phien.tom_tat()
    assert so["cookie_dead_for_run"] is True and so["cookie_fallbacks"] == 2
    assert phien.trang_thai_dang_nhap(True)[0] == "BI_TU_CHOI"


def test_bo_cookie_van_hong_thi_khong_co_doi_chung_va_khong_nho(tmp_path, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    phien = t.PhienYouTube()
    tai = _TaiGia(phien, khong_cookie=GO)
    with pytest.raises(RuntimeError) as ei:
        y.chay_kem_duong_lui_cookie(ch, tai, phien=phien)
    assert y.la_dau_hieu_cookie_chet(ei.value), "bỏ cookie vẫn hỏng: ném lỗi GỐC như cũ"
    assert phien.cookie_chet_trong_luot is False, "không có đối chứng thì không được nhớ cookie chết"
    n = len(tai.goi)
    tai.khong_cookie = None
    y.chay_kem_duong_lui_cookie(ch, tai, phien=phien)
    assert tai.goi[n] == ("", True), f"chưa có đối chứng: thao tác sau vẫn thử cookie trước: {tai.goi[n:]}"


def test_lay_thong_tin_chi_doc_ghi_nho_khong_tu_ghi_doi_chung(tmp_path, may):
    """Lấy thông tin chỉ thử client mặc định: hỏng «không định dạng» ở đó chưa chứng minh tv/web_safari có cookie cũng
    hỏng — không ghi đối chứng (``ghi_doi_chung=False``); phiên đã nhớ thì vẫn khỏi gửi cookie."""
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    phien, goi = t.PhienYouTube(), []

    def lay(cau_hinh):
        co = cau_hinh.co_cookie
        goi.append(co)
        if co:
            raise RuntimeError(LOI_COOKIE_CHET.format(id="abcdefghijk"))
        return {"id": "abcdefghijk"}

    y.chay_kem_duong_lui_cookie(ch, lay, phien=phien, ghi_doi_chung=False)
    assert goi == [True, False] and phien.cookie_chet_trong_luot is False
    phien.ghi_cookie_chet_trong_luot(True)
    y.chay_kem_duong_lui_cookie(ch, lay, phien=phien, ghi_doi_chung=False)
    assert goi[2:] == [False], "phiên đã có đối chứng (từ lượt tải): lấy thông tin chạy thẳng không cookie"


def test_ghi_nho_chi_song_trong_mot_luot_va_khong_phien_thi_nhu_cu(tmp_path, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    luot_1 = t.PhienYouTube()
    y.chay_kem_duong_lui_cookie(ch, _TaiGia(luot_1), phien=luot_1)
    assert luot_1.cookie_chet_trong_luot is True
    luot_2 = t.PhienYouTube()
    tai = _TaiGia(luot_2)
    y.chay_kem_duong_lui_cookie(ch, tai, phien=luot_2)
    assert tai.goi[0] == ("", True), "lượt mới thử lại cookie từ đầu (người dùng có thể đã xuất lại cookie)"
    khong_phien = _TaiGia(t.PhienYouTube())
    for _ in range(2):
        y.chay_kem_duong_lui_cookie(ch, khong_phien)
    assert sum(1 for _c, co in khong_phien.goi if co) == 10, "không truyền phiên: mỗi lần gọi y như cũ"


def test_video_doi_dang_nhap_van_thu_cookie_thanh_cong_thi_bo_ghi_nho(tmp_path, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    phien, nhan = t.PhienYouTube(), []
    phien.ghi_cookie_chet_trong_luot(True)
    tai = _TaiGia(phien, co_cookie=None, khong_cookie=AUTH)
    assert y.chay_kem_duong_lui_cookie(ch, tai, khi_bo_cookie=_bao_vao(phien, nhan), phien=phien) == "co_cookie"
    assert tai.goi == [("", False), ("", True)], "video giới hạn tuổi: không cookie hỏng thì vẫn thử cookie"
    assert phien.cookie_chet_trong_luot is False, "có cookie tải được: đối chứng cũ sai, thao tác sau thử cookie lại"


def test_video_doi_dang_nhap_cookie_chet_khong_thu_lai_khong_cookie_lan_hai(tmp_path, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    phien = t.PhienYouTube()
    phien.ghi_cookie_chet_trong_luot(True)
    tai = _TaiGia(phien, co_cookie=LOI_COOKIE_CHET, khong_cookie=AUTH)
    with pytest.raises(RuntimeError) as ei:
        y.chay_kem_duong_lui_cookie(ch, tai, khi_bo_cookie=phien.ghi_lui_cookie, phien=phien)
    assert sum(1 for _c, co in tai.goi if not co) == 1, f"đúng một lượt không cookie: {tai.goi}"
    assert y.la_dau_hieu_cookie_chet(ei.value), "lỗi ném ra là lỗi của lượt có cookie, như đường lui cũ"
    assert phien.cookie_chet_trong_luot is True


def test_bot_check_khi_chay_khong_cookie_khong_keo_them_request_co_cookie(tmp_path, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    phien = t.PhienYouTube()
    phien.ghi_cookie_chet_trong_luot(True)
    tai = _TaiGia(phien, co_cookie=None, khong_cookie=BOT)
    with pytest.raises(RuntimeError) as ei:
        y.chay_kem_duong_lui_cookie(ch, tai, phien=phien)
    assert tai.goi == [("", False)], f"bot-check: dừng, không gửi thêm request nào: {tai.goi}"
    assert t.phan_loai_loi(ei.value).category == t.BOT_CHALLENGE


# ---------------------------------------------------------------- 3. lô quét Engine (giao diện «Quét YouTube», Watch)

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
        kq = ScanResult(source_name=label or path, source_ref=ref, duration_s=DAI,
                        vung_da_khop=[(0.0, DAI)], kho_id=dt["kho_id"], kho_ten=dt["kho_ten"],
                        kho_phien_ban=dt["kho_phien_ban"], chinh_sach=chu_ky_chinh_sach(e.config))
        kq.matches = [m]
        kq.ung_vien_dat = [m]
        kq.so_dat_nguong = 1
        return kq

    monkeypatch.setattr(e, "scan_media", quet)
    return e


def test_lo_quet_cookie_chet_chi_gui_cookie_o_video_dau_va_ket_qua_nao_cung_ghi_ro(tmp_path, monkeypatch, may):
    ids = [_ma(i) for i in range(4)]
    ydl = YdlKichBan(info={"*": lambda p, ma: LOI_COOKIE_CHET if _co_cookie(p.opts) else info_mau(ma, DAI)},
                     tai={"*": _tai_cookie_chet})
    e = _eng(tmp_path, monkeypatch, ydl)
    ket = list(e.scan_iter([f"https://youtu.be/{m}" for m in ids]))
    co_cookie = [(g[0], g[1]) for g, o in zip(ydl.goi, ydl.opts) if _co_cookie(o)]
    assert [k.status for k in ket] == ["ok"] * len(ids), [(k.status, k.note) for k in ket]
    assert {ma for _l, ma in co_cookie} == {ids[0]}, f"chỉ video ĐẦU gửi cookie: {co_cookie}"
    # Video đầu: lấy thông tin 1 + 1, tải 5 client có cookie + 1 (đối chứng); mỗi video sau: 1 + 1, không cookie.
    assert ydl.dem("info") == len(ids) + 1 and ydl.dem("tai") == len(ids) + 5, ydl.goi
    assert all("hết hiệu lực" in (k.note or "") for k in ket), "kết quả nào cũng ghi rõ chạy KHÔNG cookie"
    phien = e.phien_youtube_cuoi
    assert phien.tom_tat()["cookie_dead_for_run"] is True
    assert phien.trang_thai_dang_nhap(True)[0] == "BI_TU_CHOI"
