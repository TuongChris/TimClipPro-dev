# -*- coding: utf-8 -*-
"""Audit D-11: mọi phiên yt-dlp GHI LẠI file cookie dùng chung tại chỗ (mở 'w' = cắt cụt rồi ghi), không khoá,
không thay thế nguyên tử. Phiên chồng nhau (GUI, Watch, CLI, luồng đồng bộ + luồng quét) có thể:

1. ĐỌC file đúng lúc nó vừa bị cắt cụt → cổng ``kiem_tra_file_cookie`` ném ``LoiFileCookie`` →
   ``COOKIE_INVALID_OR_EXPIRED`` (ngưỡng 1) → cầu dao mở, cả lượt chạy dừng, bảo người dùng xuất lại cookie;
2. hai lần lưu đan nhau để lại file HỎNG VĨNH VIỄN (file cookie duy nhất của người dùng);
3. phiên lưu sau đè cookie YouTube vừa xoay bằng giá trị cũ (mất cập nhật).

Test dùng ĐÚNG mã lưu cookie của yt-dlp ghim trong lock (``YoutubeDL.close → save_cookies →
YoutubeDLCookieJar.save``) và tuỳ chọn THẬT do ``CauHinhMang.tuy_chon`` dựng; chỉ chèn một điểm dừng tất định vào
giữa ``save`` (sau khi file đã mở 'w', trước khi ghi bản ghi) để thay cho việc chờ một cuộc đua thời gian thật.
Không mạng, không cookie thật (60 bản ghi giả), không ngủ.

Ba test đầu là bản sao test tái hiện của audit (giữ nguyên khẳng định). Các test sau chặn sửa quá tay: cơ chế ghi lại
của yt-dlp vẫn có về nghĩa (cookie YouTube đặt/xoay trong phiên về file của người dùng — chỉ những cookie phiên đổi, gộp
vào bản mới nhất, thay nguyên tử), không đổi gì thì không ghi, không đè file người dùng vừa đổi, không làm hỏng phiên đã
xong, và một lượt chồng nhau theo thời gian THẬT (không điểm dừng chèn) không còn lỗi.
"""

import contextlib
import http.cookiejar
import threading
import time

import pytest
import yt_dlp
import ytdlp_chung as y
from luu_tru import LoiKhoaDuLieu
from truy_cap_youtube import COOKIE_INVALID_OR_EXPIRED, PhienYouTube
from yt_dlp import cookies as ytc
from yt_dlp.utils import is_path_like

SO_BAN_GHI = 60


def _tao_cookie(tmp_path):
    """File Netscape hợp lệ, 60 bản ghi GIẢ, giá trị cùng độ dài."""
    p = tmp_path / "cookies.txt"
    dong = ["# Netscape HTTP Cookie File", ""]
    for i in range(SO_BAN_GHI):
        dong.append("\t".join([".youtube.com", "TRUE", "/", "TRUE", "9999999999",
                               f"CK_{i:02d}", f"gia_tri_gia_{i:02d}_" + "x" * 24]))
    p.write_text("\n".join(dong) + "\n", encoding="utf-8")
    return p


def _opts(cfg):
    # Đúng tuỳ chọn production dựng cho một lượt tải có cookie; bỏ `js_runtimes` (node giả của conftest) — không liên
    # quan tới việc lưu cookie.
    opts = cfg.tuy_chon("download")
    opts.pop("js_runtimes", None)
    return opts


def _cookie(jar, ten):
    return next(c for c in jar if c.name == ten)


@pytest.fixture(autouse=True)
def _xoa_cache_cookie():
    y._CACHE_COOKIE.clear()
    yield
    y._CACHE_COOKIE.clear()


def test_phien_khac_dung_tuy_chon_trong_luc_mot_phien_dang_luu_cookie_khong_mo_cau_dao(tmp_path, monkeypatch):
    """Phiên A (vd. luồng đồng bộ kênh) vừa xong một video → ``with YoutubeDL`` thoát → lưu cookie. Cùng lúc phiên B
    (Watch / luồng quét / CLI) dựng tuỳ chọn cho video kế tiếp. File cookie của người dùng KHÔNG hỏng, nên B phải chạy
    bình thường — không được thấy file rỗng/dở dang và mở cầu dao «cookie hỏng» cho cả lượt."""
    p = _tao_cookie(tmp_path)
    cfg = y.CauHinhMang(cookiefile=str(p))
    _opts(cfg)  # file hợp lệ: cổng cho qua trước khi có phiên nào chạy

    loi_cua_b: list = []
    da_chen = threading.Event()
    goc = ytc.YoutubeDLCookieJar._really_save

    def phien_b_dung_tuy_chon():
        try:
            cfg.tuy_chon("download")          # cổng kiem_tra_file_cookie của phiên B
        except Exception as e:  # noqa: BLE001
            loi_cua_b.append(e)

    def luu_co_diem_dung(self, f, *a, **k):
        # Lúc này `save` đã `open(file, 'w')`: file trên đĩa đã bị cắt cụt, bản ghi chưa được ghi.
        if not da_chen.is_set():
            da_chen.set()
            t = threading.Thread(target=phien_b_dung_tuy_chon)
            t.start()
            t.join(10)
        return goc(self, f, *a, **k)

    monkeypatch.setattr(ytc.YoutubeDLCookieJar, "_really_save", luu_co_diem_dung)

    with yt_dlp.YoutubeDL(_opts(cfg)) as ydl_a:
        assert len(list(ydl_a.cookiejar)) == SO_BAN_GHI     # phiên A đã nạp cookie như một lượt tải thật
    assert da_chen.is_set(), "yt-dlp không lưu cookie khi đóng phiên — giả định của test sai"

    phien = PhienYouTube()
    loai = [phien.ghi_loi(e, thao_tac="download").category for e in loi_cua_b]

    # Sau cùng file vẫn hợp lệ (A ghi xong) — chỉ CỬA SỔ ghi là vấn đề.
    y._CACHE_COOKIE.clear()
    _opts(cfg)

    assert not loi_cua_b and not phien.mo, (
        f"Phiên B gặp {[type(e).__name__ + ': ' + str(e) for e in loi_cua_b]} → loại {loai}; "
        f"cầu dao mở={phien.mo} (COOKIE_INVALID_OR_EXPIRED mở ở ngưỡng {phien.nguong[COOKIE_INVALID_OR_EXPIRED]}). "
        "File cookie dùng chung bị đọc giữa lúc yt-dlp cắt cụt + ghi lại tại chỗ.")


def test_hai_phien_luu_cookie_dan_nhau_khong_lam_hong_file_cua_nguoi_dung(tmp_path, monkeypatch):
    """Hai phiên chồng nhau (A, B) cùng nạp file; YouTube xoay một cookie của B thành giá trị DÀI hơn. A mở file 'w'
    (cắt cụt), B lưu trọn rồi đóng, A ghi tiếp từ vị trí 0. File cookie duy nhất của người dùng phải còn là một file
    Netscape hợp lệ (bản của A hoặc của B), không phải ghép đè của hai bản."""
    p = _tao_cookie(tmp_path)
    cfg = y.CauHinhMang(cookiefile=str(p))
    opts = _opts(cfg)

    ydl_a = yt_dlp.YoutubeDL(opts)
    ydl_b = yt_dlp.YoutubeDL(opts)
    hu_a, hu_b = ydl_a.cookiejar, ydl_b.cookiejar         # cả hai phiên đã nạp file (như lúc bắt đầu tải)
    _cookie(hu_b, "CK_00").value += "_youtube_vua_xoay"   # Set-Cookie trong phiên B

    goc = ytc.YoutubeDLCookieJar._really_save
    da_chen = threading.Event()

    def luu_co_diem_dung(self, f, *a, **k):
        if self is hu_a and not da_chen.is_set():
            da_chen.set()
            ydl_b.close()                                  # B lưu trọn + đóng trong lúc A đang mở 'w'
        return goc(self, f, *a, **k)

    monkeypatch.setattr(ytc.YoutubeDLCookieJar, "_really_save", luu_co_diem_dung)
    ydl_a.close()
    assert da_chen.is_set()

    y._CACHE_COOKIE.clear()
    try:
        cfg.tuy_chon("download")
        loi = None
    except y.LoiFileCookie as e:
        loi = e
    assert loi is None, (
        f"File cookie của người dùng HỎNG sau hai lần lưu đan nhau: {loi} — mọi lượt sau (GUI/Watch/CLI) đều dừng "
        "vì «cookie hỏng» cho tới khi người dùng xuất lại cookie.")


def test_phien_luu_sau_khong_de_cookie_vua_xoay_bang_gia_tri_cu(tmp_path):
    """A và B chồng nhau; trong A YouTube xoay CK_00 (như __Secure-1PSIDTS/SIDCC). A đóng trước, B đóng sau.
    Nếu file đã nhận giá trị mới từ A thì B (không hề đổi CK_00) không được ghi lại giá trị CŨ lên trên."""
    p = _tao_cookie(tmp_path)
    cfg = y.CauHinhMang(cookiefile=str(p))
    opts = _opts(cfg)

    ydl_a = yt_dlp.YoutubeDL(opts)
    ydl_b = yt_dlp.YoutubeDL(opts)
    _ = ydl_a.cookiejar, ydl_b.cookiejar
    _cookie(ydl_a.cookiejar, "CK_00").value = "gia_tri_moi_youtube_vua_xoay"

    ydl_a.close()
    sau_a = p.read_text(encoding="utf-8")
    ydl_b.close()
    sau_b = p.read_text(encoding="utf-8")

    if "gia_tri_moi_youtube_vua_xoay" in sau_a:
        assert "gia_tri_moi_youtube_vua_xoay" in sau_b, (
            "Phiên B (nạp file TRƯỚC khi A lưu) ghi đè cả file khi đóng: cookie YouTube vừa xoay trong phiên A bị "
            "thay bằng giá trị cũ.")


# ------------------------------------------------ chặn sửa quá tay

def _cookie_moi(ten, gia_tri):
    """Cookie YouTube vừa đặt trong phiên (như ``Set-Cookie`` — hũ tạo đối tượng MỚI)."""
    return http.cookiejar.Cookie(0, ten, gia_tri, None, False, ".youtube.com", True, True, "/", True, True,
                                 9999999999, False, None, None, {})


def _dong_cua(van_ban, ten):
    return [d for d in van_ban.splitlines() if f"\t{ten}\t" in d]


def test_ytdlp_nhan_ban_chup_da_kiem_chu_khong_nhan_duong_dan(tmp_path):
    """Có đường dẫn là yt-dlp tự mở 'w' tại chỗ khi đóng phiên. Bản chụp: phiên nạp ĐÚNG văn bản cổng vừa kiểm (file đổi
    sau đó không lọt vào), câu lỗi nạp cookie của yt-dlp giữ nguyên chữ (repr = đường dẫn), không lộ giá trị."""
    p = _tao_cookie(tmp_path)
    tep = _opts(y.CauHinhMang(cookiefile=str(p)))["cookiefile"]
    assert isinstance(tep, y.LuongCookieFile) and not is_path_like(tep)
    assert repr(tep) == repr(str(p)) and str(tep) == repr(str(p))
    assert "gia_tri_gia" not in repr(tep)
    p.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    with yt_dlp.YoutubeDL({"cookiefile": tep, "quiet": True}) as ydl:
        assert len(list(ydl.cookiejar)) == SO_BAN_GHI


def test_phien_khong_doi_cookie_thi_khong_ghi_file(tmp_path):
    """Trước đây MỌI phiên ghi lại cả file (hàng trăm lần mỗi lượt đồng bộ). Nay phiên không đổi cookie nào thì file giữ
    nguyên từng byte — cả dòng ``#HttpOnly_``, chú thích, CRLF, cookie phiên (hạn 0) của bản người dùng xuất."""
    p = tmp_path / "cookies.txt"
    goc = ("# Netscape HTTP Cookie File\r\n# xuat tu trinh duyet\r\n\r\n"
           + "#HttpOnly_" + "\t".join([".youtube.com", "TRUE", "/", "TRUE", "9999999999", "SID", "gia_sid"]) + "\r\n"
           + "\t".join(["www.youtube.com", "FALSE", "/", "FALSE", "0", "PHIEN", "gia_phien"]) + "\r\n").encode("utf-8")
    p.write_bytes(goc)
    truoc = p.stat().st_mtime_ns
    with yt_dlp.YoutubeDL(_opts(y.CauHinhMang(cookiefile=str(p)))) as ydl:
        assert len(list(ydl.cookiejar)) == 2
    assert p.read_bytes() == goc and p.stat().st_mtime_ns == truoc
    assert sorted(x.name for x in tmp_path.iterdir()) == ["cookies.txt"]


def test_cookie_youtube_dat_trong_phien_van_ve_file_nguoi_dung(tmp_path):
    """Cơ chế ghi lại của yt-dlp giữ nguyên về nghĩa (YOUTUBE_ACCESS_RELIABILITY §5): cookie đổi/đặt mới trong phiên về
    file; dòng phiên không đụng giữ nguyên văn; file vẫn qua cổng; không còn file tạm (mang giá trị cookie)."""
    p = _tao_cookie(tmp_path)
    cfg = y.CauHinhMang(cookiefile=str(p))
    dong_cu = _dong_cua(p.read_text(encoding="utf-8"), "CK_04")
    with yt_dlp.YoutubeDL(_opts(cfg)) as ydl:
        _cookie(ydl.cookiejar, "CK_03").value = "xoay_trong_phien"
        ydl.cookiejar.set_cookie(_cookie_moi("VISITOR_MOI", "gia_moi"))
    sau = p.read_text(encoding="utf-8")
    assert _dong_cua(sau, "CK_03") == [".youtube.com\tTRUE\t/\tTRUE\t9999999999\tCK_03\txoay_trong_phien"]
    assert _dong_cua(sau, "VISITOR_MOI") == [".youtube.com\tTRUE\t/\tTRUE\t9999999999\tVISITOR_MOI\tgia_moi"]
    assert _dong_cua(sau, "CK_04") == dong_cu
    assert sum(1 for d in sau.splitlines() if "\tCK_" in d) == SO_BAN_GHI
    y._CACHE_COOKIE.clear()
    _opts(cfg)
    assert not list(tmp_path.glob("*.tmp"))


def test_hai_phien_doi_hai_cookie_khac_nhau_ca_hai_deu_con(tmp_path):
    """Không mất cập nhật theo chiều nào: A xoay CK_01, B xoay CK_02, cùng nạp một bản → file có cả hai."""
    p = _tao_cookie(tmp_path)
    opts = _opts(y.CauHinhMang(cookiefile=str(p)))
    a, b = yt_dlp.YoutubeDL(opts), yt_dlp.YoutubeDL(opts)
    _cookie(a.cookiejar, "CK_01").value = "moi_cua_a"
    _cookie(b.cookiejar, "CK_02").value = "moi_cua_b"
    a.close()
    b.close()
    sau = p.read_text(encoding="utf-8")
    assert _dong_cua(sau, "CK_01")[0].endswith("\tmoi_cua_a") and _dong_cua(sau, "CK_02")[0].endswith("\tmoi_cua_b")


def test_cookie_phien_bo_chi_xoa_khi_tren_dia_chua_ai_doi(tmp_path):
    """Hũ bỏ cookie (hết hạn, YouTube xoá) → bỏ khỏi file như yt-dlp vẫn làm. Nhưng phiên khác vừa ghi giá trị MỚI cho
    chính cookie đó thì giữ: xoá theo bản đã nạp từ trước là mất cập nhật."""
    p = _tao_cookie(tmp_path)
    opts = _opts(y.CauHinhMang(cookiefile=str(p)))
    a, b = yt_dlp.YoutubeDL(opts), yt_dlp.YoutubeDL(opts)
    a.cookiejar.clear(".youtube.com", "/", "CK_05")
    a.cookiejar.clear(".youtube.com", "/", "CK_06")
    _cookie(b.cookiejar, "CK_06").value = "b_vua_xoay"
    b.close()
    a.close()
    sau = p.read_text(encoding="utf-8")
    assert not _dong_cua(sau, "CK_05")
    assert _dong_cua(sau, "CK_06")[0].endswith("\tb_vua_xoay")


def test_file_tren_dia_khong_hop_le_thi_khong_ghi_de_va_phien_khong_hong(tmp_path, caplog):
    """File bị đổi giữa phiên thành thứ cổng không nhận (người dùng sửa tay, công cụ khác): đóng phiên KHÔNG đè lên (lượt
    sau cổng tự báo rõ), không ném lỗi ra ``YoutubeDL.close`` (lượt tải đã xong), log không mang tên/giá trị cookie."""
    p = _tao_cookie(tmp_path)
    hong = "# Netscape HTTP Cookie File\n.youtube.com TRUE / TRUE 0 SID gia_tri_bi_mat_gia\n"
    with yt_dlp.YoutubeDL(_opts(y.CauHinhMang(cookiefile=str(p)))) as ydl:
        _cookie(ydl.cookiejar, "CK_00").value = "xoay_trong_phien"
        p.write_text(hong, encoding="utf-8")
    assert p.read_text(encoding="utf-8") == hong
    assert "write_back_skipped" in caplog.text and "invalid_on_disk" in caplog.text
    assert "gia_tri" not in caplog.text and "xoay_trong_phien" not in caplog.text and "CK_00" not in caplog.text


def test_khoa_ban_thi_bo_luot_ghi_lai_phien_khong_hong(tmp_path, monkeypatch, caplog):
    """Process khác giữ khoá thư mục quá hạn: bỏ lượt ghi lại (file giữ nguyên, hợp lệ), phiên đóng bình thường."""

    @contextlib.contextmanager
    def khoa_ban(*_a, **_k):
        raise LoiKhoaDuLieu("process khác đang giữ khoá")
        yield  # pragma: no cover

    monkeypatch.setattr(y, "khoa_json", khoa_ban)
    p = _tao_cookie(tmp_path)
    truoc = p.read_bytes()
    with yt_dlp.YoutubeDL(_opts(y.CauHinhMang(cookiefile=str(p)))) as ydl:
        _cookie(ydl.cookiejar, "CK_00").value = "xoay_trong_phien"
    assert p.read_bytes() == truoc
    assert "reason=LoiKhoaDuLieu" in caplog.text


def test_don_file_tam_mo_coi_cua_tool_khong_dung_file_tam_khac(tmp_path):
    """File tạm của lượt ghi bị chết giữa chừng mang giá trị cookie → dọn (dưới khoá). File ``.tmp`` khác của người dùng
    cạnh file cookie thì không đụng."""
    p = _tao_cookie(tmp_path)
    mo_coi = tmp_path / "cookies.txt.timclip-99999-deadbeef.tmp"
    mo_coi.write_text("ban ghi do dang", encoding="utf-8")
    cua_nguoi_dung = tmp_path / "cookies.txt.ban_cu.tmp"
    cua_nguoi_dung.write_text("cua nguoi dung", encoding="utf-8")
    with yt_dlp.YoutubeDL(_opts(y.CauHinhMang(cookiefile=str(p)))) as ydl:
        _cookie(ydl.cookiejar, "CK_00").value = "xoay_trong_phien"
    assert not mo_coi.exists() and cua_nguoi_dung.read_text(encoding="utf-8") == "cua nguoi dung"


def test_hu_khong_nap_tu_ban_chup_luu_y_nguyen_ytdlp(tmp_path):
    """Đường lưu khác của yt-dlp (``save(đường_dẫn)`` — vd. file tạm cho bộ tải ngoài) không bị đổi."""
    _opts(y.CauHinhMang(cookiefile=str(_tao_cookie(tmp_path))))   # đã cài đường lưu riêng
    dich = tmp_path / "khac.txt"
    hu = ytc.YoutubeDLCookieJar(str(dich))
    hu.set_cookie(_cookie_moi("X", "gia_x"))
    hu.save()
    assert _dong_cua(dich.read_text(encoding="utf-8"), "X") == [".youtube.com\tTRUE\t/\tTRUE\t9999999999\tX\tgia_x"]


def test_cong_thu_lai_khi_windows_tu_choi_doc_luc_file_dang_bi_thay(tmp_path, monkeypatch):
    """Windows từ chối mở file (PermissionError) trong tích tắc nó bị ``os.replace`` thay: cổng thử lại thay vì báo «không
    đọc được file cookie» (mở cầu dao cookie). Bị từ chối mãi (quyền thật) thì vẫn báo như cũ."""
    p = _tao_cookie(tmp_path)
    goc = y._doc_van_ban_cookie
    lan: list = []

    def doc(duong_dan):
        lan.append(1)
        if len(lan) <= 2:
            raise PermissionError(13, "Permission denied")
        return goc(duong_dan)

    monkeypatch.setattr(y, "_doc_van_ban_cookie", doc)
    assert isinstance(_opts(y.CauHinhMang(cookiefile=str(p)))["cookiefile"], y.LuongCookieFile)
    assert len(lan) == 4, "cổng: 2 lần bị từ chối + 1 lần đọc được; bản chụp: 1 lần"

    def luon_tu_choi(_duong_dan):
        raise PermissionError(13, "Permission denied")

    y._CACHE_COOKIE.clear()
    monkeypatch.setattr(y, "THU_LAI_DOC_COOKIE_S", 0.05)
    monkeypatch.setattr(y, "_doc_van_ban_cookie", luon_tu_choi)
    with pytest.raises(y.LoiFileCookie, match="Không đọc được file cookie"):
        _opts(y.CauHinhMang(cookiefile=str(p)))


def test_luot_chong_nhau_theo_thoi_gian_that_khong_loi(tmp_path):
    """Không điểm dừng chèn: hai luồng mở/đóng phiên có xoay cookie liên tục, một luồng khác dựng tuỳ chọn liên tục (cache
    cổng xoá mỗi lần — như file vừa đổi). Mã cũ: phiên đọc phải file cụt/ghép đè («does not look like a Netscape format
    cookies file», «sai định dạng ở dòng 64»). Nay không luồng nào lỗi và file cuối vẫn hợp lệ."""
    p = _tao_cookie(tmp_path)
    cfg = y.CauHinhMang(cookiefile=str(p))
    loi: list = []
    xong = threading.Event()

    def ghi(so):
        try:
            for n in range(15):
                with yt_dlp.YoutubeDL(_opts(cfg)) as ydl:
                    _cookie(ydl.cookiejar, f"CK_{so:02d}").value = f"luong{so}_lan{n:02d}" + "z" * (n % 7)
        except Exception as e:  # noqa: BLE001
            loi.append(f"ghi: {type(e).__name__}: {e}")

    def doc():
        while not xong.is_set():
            y._CACHE_COOKIE.clear()
            try:
                cfg.tuy_chon("download")
            except Exception as e:  # noqa: BLE001
                loi.append(f"doc: {type(e).__name__}: {e}")
            time.sleep(0.001)

    luong_doc = threading.Thread(target=doc)
    luong_ghi = [threading.Thread(target=ghi, args=(so,)) for so in (1, 2)]
    luong_doc.start()
    for t in luong_ghi:
        t.start()
    for t in luong_ghi:
        t.join(60)
    xong.set()
    luong_doc.join(10)
    assert not loi, loi[:3]
    y._CACHE_COOKIE.clear()
    _opts(cfg)


# ------------------------------------------------ review audit D: cả hai phiên cùng xoay MỘT cookie

def _xoay(jar, ten, gia_tri, han):
    """YouTube xoay cookie (``Set-Cookie`` mới): giá trị mới, hạn dùng tính từ LÚC cấp (Max-Age cố định)."""
    c = _cookie(jar, ten)
    c.value, c.expires = gia_tri, han


def test_hai_phien_cung_xoay_mot_cookie_phien_dong_sau_khong_de_gia_tri_moi_hon(tmp_path):
    """Lượt quét A nạp v0, YouTube xoay CK_00 → vA ngay đầu phiên (rồi A tải ffmpeg 60 phút). Đồng bộ kênh B nạp v0
    (đĩa chưa đổi), YouTube xoay → vB (cấp SAU vA), B đóng → đĩa vB. A đóng sau: không được đè vB bằng vA cũ hơn."""
    p = _tao_cookie(tmp_path)
    cfg = y.CauHinhMang(cookiefile=str(p))
    a = yt_dlp.YoutubeDL(_opts(cfg))
    _ = a.cookiejar
    _xoay(a.cookiejar, "CK_00", "gia_tri_A_xoay_luc_T0", 4102444800)
    b = yt_dlp.YoutubeDL(_opts(cfg))
    _xoay(b.cookiejar, "CK_00", "gia_tri_B_xoay_luc_T30", 4102444800 + 1800)
    b.close()
    a.close()
    sau = p.read_text(encoding="utf-8")
    assert _dong_cua(sau, "CK_00")[0].endswith("\tgia_tri_B_xoay_luc_T30"), _dong_cua(sau, "CK_00")
    assert sum(1 for d in sau.splitlines() if "\tCK_" in d) == SO_BAN_GHI


def test_hai_phien_cung_xoay_cung_han_phien_ghi_truoc_thang(tmp_path, caplog):
    """Không phân biệt được bản nào mới hơn (cùng hạn dùng): giữ dòng trên đĩa — cùng phép so-rồi-đặt như khi xoá; log
    số dòng giữ lại, không tên hay giá trị cookie."""
    p = _tao_cookie(tmp_path)
    opts = _opts(y.CauHinhMang(cookiefile=str(p)))
    a, b = yt_dlp.YoutubeDL(opts), yt_dlp.YoutubeDL(opts)
    _cookie(a.cookiejar, "CK_00").value = "cua_a"
    _cookie(a.cookiejar, "CK_01").value = "cua_a_rieng"
    _cookie(b.cookiejar, "CK_00").value = "cua_b"
    b.close()
    with caplog.at_level("DEBUG", logger="youtube.ytdlp"):
        a.close()
    sau = p.read_text(encoding="utf-8")
    assert _dong_cua(sau, "CK_00")[0].endswith("\tcua_b")
    assert _dong_cua(sau, "CK_01")[0].endswith("\tcua_a_rieng"), "cookie chỉ A đổi vẫn về file"
    assert any("changed_kept=1" in r.getMessage() for r in caplog.records), [r.getMessage() for r in caplog.records]
    assert not any("cua_" in r.getMessage() or "CK_0" in r.getMessage() for r in caplog.records)


def test_phien_dong_sau_co_ban_xoay_moi_hon_van_ghi(tmp_path):
    """Chặn sửa quá tay: phiên đóng SAU mà YouTube cấp bản của nó SAU (hạn dùng muộn hơn) thì bản đó thắng."""
    p = _tao_cookie(tmp_path)
    opts = _opts(y.CauHinhMang(cookiefile=str(p)))
    a, b = yt_dlp.YoutubeDL(opts), yt_dlp.YoutubeDL(opts)
    _xoay(b.cookiejar, "CK_00", "cua_b_cap_truoc", 4102444800)
    _xoay(a.cookiejar, "CK_00", "cua_a_cap_sau", 4102444800 + 600)
    b.close()
    a.close()
    assert _dong_cua(p.read_text(encoding="utf-8"), "CK_00")[0].endswith("\tcua_a_cap_sau")


def test_byte_khong_utf8_o_dong_khac_khong_tat_vinh_vien_ghi_lai(tmp_path, caplog):
    """Audit DR-4: file có MỘT byte không phải UTF-8 (0xE9 Latin-1 — file sửa tay, lưu ANSI) ở dòng của cookie không liên
    quan. Cổng và bản chụp đọc ``errors='replace'`` nên NHẬN file (phiên có đăng nhập); bước ghi lại từng đọc lại đĩa
    bằng UTF-8 nghiêm → ``UnicodeDecodeError`` bị nuốt → mọi lượt ghi lại của file đó bị bỏ, mãi mãi. File cổng đã nhận
    thì cookie vừa xoay phải về file; dòng không đổi giữ NGUYÊN byte (không thay bằng U+FFFD)."""
    p = tmp_path / "cookies.txt"
    dong = [b"\t".join([b".youtube.com", b"TRUE", b"/", b"TRUE", b"9999999999", ten, gia_tri])
            for ten, gia_tri in ((b"SID", b"gia_tri_gia_sid_xxxxxxxx"), (b"SIDCC", b"gia_cu_gia"),
                                 (b"PREF", b"hl=fr&nom=caf\xe9"))]
    p.write_bytes(b"\n".join([b"# Netscape HTTP Cookie File", b"# ghi ch\xfa tay", b"", *dong]) + b"\n")
    with yt_dlp.YoutubeDL(_opts(y.CauHinhMang(cookiefile=str(p)))) as ydl:
        _cookie(ydl.cookiejar, "SIDCC").value = "vC_moi_xoay_trong_phien"
    sau = p.read_bytes().replace(b"\r\n", b"\n")  # Windows ghi văn bản bằng CRLF — không phải điều test khẳng định
    assert "write_back_skipped" not in caplog.text, caplog.text
    assert b"\tSIDCC\tvC_moi_xoay_trong_phien\n" in sau, "cookie YouTube vừa xoay không về file của người dùng"
    assert b"\tPREF\thl=fr&nom=caf\xe9\n" in sau and b"# ghi ch\xfa tay\n" in sau, "dòng không đổi phải giữ nguyên byte"
    assert b"\xef\xbf\xbd" not in sau, "không được thay byte của người dùng bằng U+FFFD"
