# -*- coding: utf-8 -*-
"""Audit D-3: hai lượt quét ĐỒNG THỜI cùng một video (Watch giữ tool.lock + tab «Quét YouTube» của GUI
không lấy tool.lock) dùng chung ``data/downloads/<id>.webm.part`` với ``continuedl=True``.

Hành vi ĐÚNG: dù hai lượt chạy chồng nhau, file audio nằm lại trong bộ đệm (và được mọi lượt quét sau
dùng lại với câu «Đã có sẵn audio») phải trùng TỪNG BYTE với luồng máy chủ trả — không bao giờ là bản
trộn của hai lượt tải.

Không mạng: ``yt_dlp.YoutubeDL`` được thay bằng bản giả làm ĐÚNG như ``yt_dlp/downloader/http.py``
(bản trong venv): có ``.part`` và ``continuedl`` → ``resume_len = getsize(.part)``, xin
``Range: bytes=resume_len-`` rồi mở ``'ab'``; không có → ``'wb'``; xong thì ``os.replace(.part, đích)``
(``FileDownloader.try_rename``); file đích đã có → «has already been downloaded», không tải.
Cả hai lượt tải CÙNG một format (cùng luồng byte) — trường hợp lành nhất; vẫn phải ra đúng luồng đó.
Thứ tự xen kẽ được ép bằng Event (chờ có hạn, hết hạn thì đi tiếp — không treo test).
"""

import os
import random
import threading
import time

from engine import Config, Engine

VID = "aaaaaaaaaaa"
URL = f"https://www.youtube.com/watch?v={VID}"
KHOI = 4096
# Luồng audio (một format) máy chủ trả cho video này — 4 khối khác nhau để thấy rõ khối bị lặp.
LUONG = random.Random(20261025).randbytes(4 * KHOI)
CHO_S = 5.0


class _Nhip:
    def __init__(self):
        self.a_ghi_dau = threading.Event()   # lượt A đã mở .part 'wb' và ghi khối 0
        self.b_mo = threading.Event()        # lượt B đã thấy .part, mở 'ab' (nối tiếp)
        self.a_ghi_hai = threading.Event()   # A ghi xong khối 1
        self.b_ghi_mot = threading.Event()   # B nối xong khối đầu của nó
        self.a_dong = threading.Event()      # A ghi hết, đã đóng file
        self.het_gio = []

    def cho(self, ev, ten):
        if not ev.wait(CHO_S):
            self.het_gio.append(ten)


def _lam_gia(nhip, so_lan_goi, cam_goi):
    class _YoutubeDLGia:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            if cam_goi.is_set():
                raise AssertionError("lượt quét sau phải dùng lại bộ đệm, không được tải lại")
            so_lan_goi.append(threading.current_thread().name)
            dich = self.opts["outtmpl"].replace("%(ext)s", "webm")
            tam = dich + ".part"
            if os.path.exists(dich):            # yt-dlp: "has already been downloaded"
                return 0
            resume = (os.path.getsize(tam)
                      if self.opts.get("continuedl", True) and os.path.exists(tam) else 0)
            if resume:
                # Máy chủ trả từ byte `resume` (Range), yt-dlp nối vào cuối .part bằng 'ab'.
                du_lieu = LUONG[resume:]
                with open(tam, "ab") as f:
                    nhip.b_mo.set()
                    nhip.cho(nhip.a_ghi_hai, "a_ghi_hai")
                    f.write(du_lieu[:KHOI])
                    f.flush()
                    nhip.b_ghi_mot.set()
                    nhip.cho(nhip.a_dong, "a_dong")
                    f.write(du_lieu[KHOI:])
                    f.flush()
            else:
                with open(tam, "wb") as f:
                    f.write(LUONG[:KHOI])
                    f.flush()
                    nhip.a_ghi_dau.set()
                    nhip.cho(nhip.b_mo, "b_mo")
                    f.write(LUONG[KHOI:2 * KHOI])
                    f.flush()
                    nhip.a_ghi_hai.set()
                    nhip.cho(nhip.b_ghi_mot, "b_ghi_mot")
                    f.write(LUONG[2 * KHOI:])
                    f.flush()
                nhip.a_dong.set()
            os.replace(tam, dich)               # FileDownloader.try_rename
            return 0

    return _YoutubeDLGia


def _engine(tmp_path, data):
    e = Engine(root=str(tmp_path), data_dir=str(data), out_dir=str(tmp_path / "ra"))
    e.config = Config(ytdlp_player_clients=[""])
    return e


def test_hai_luot_quet_dong_thoi_cung_video_khong_lam_hong_audio_dem(tmp_path, monkeypatch):
    import yt_dlp

    nhip, so_lan_goi, cam_goi = _Nhip(), [], threading.Event()
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _lam_gia(nhip, so_lan_goi, cam_goi))
    data = tmp_path / "data"
    watch, gui = _engine(tmp_path, data), _engine(tmp_path, data)   # hai lượt, chung data/

    ket_qua = {}

    def chay(ten, eng):
        try:
            ket_qua[ten] = "trả " + os.path.basename(eng.download_audio(URL, VID))
        except BaseException as e:  # noqa: BLE001 — ghi lại để in khi test hỏng
            ket_qua[ten] = f"lỗi {type(e).__name__}: {str(e)[:160]}"

    t_watch = threading.Thread(target=chay, args=("watch", watch), name="watch")
    t_watch.start()
    assert nhip.a_ghi_dau.wait(CHO_S), "lượt Watch chưa bắt đầu tải"
    # Người dùng dán đúng video đó vào «Quét YouTube» khi Watch đang tải dở.
    t_gui = threading.Thread(target=chay, args=("gui", gui), name="gui")
    t_gui.start()
    t_watch.join(30)
    t_gui.join(30)
    assert not t_watch.is_alive() and not t_gui.is_alive()

    # Lượt quét SAU (ngày mai Watch quét lại / người dùng quét lại): dùng bộ đệm, không tải lại.
    cam_goi.set()
    tin = []
    duong = _engine(tmp_path, data).download_audio(URL, VID, progress=lambda p, m: tin.append(m))
    assert any("Đã có sẵn audio" in m for m in tin)
    with open(duong, "rb") as f:
        dem = f.read()

    so_khoi = [dem[i:i + KHOI] for i in range(0, len(dem), KHOI)]
    goc = [LUONG[i:i + KHOI] for i in range(0, len(LUONG), KHOI)]
    thu_tu = [goc.index(k) if k in goc else "?" for k in so_khoi]
    assert dem == LUONG, (
        f"Audio đệm {os.path.basename(duong)} bị HỎNG sau hai lượt tải đồng thời: {len(dem)} byte "
        f"thay vì {len(LUONG)}; thứ tự khối trong file = {thu_tu} (đúng phải là [0, 1, 2, 3]). "
        f"Kết quả hai lượt: {ket_qua}; số lần gọi yt-dlp: {so_lan_goi}; chờ hết giờ: {nhip.het_gio}. "
        "Mọi lượt quét sau dùng lại file này («Đã có sẵn audio») mà không báo gì."
    )


# ---------------------------------------------------------------------------------------------------------
# Chặn sửa quá tay: khoá tải chỉ theo đúng tên file, chờ thì Dừng được, lượt giữ khoá hỏng thì lượt chờ tự tải.
# ---------------------------------------------------------------------------------------------------------

def _gia_don_gian(cho_truoc_khi_xong=None, hong_lan_dau=False, goi=None):
    """yt-dlp giả: ghi .part theo ``continuedl`` như bản thật; tuỳ chọn chờ Event giữa chừng; ``hong_lan_dau``:
    lần gọi ĐẦU ghi một khối rồi đứt (để lại .part), các lần sau tải bình thường."""
    class _Gia:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            dich = self.opts["outtmpl"].replace("%(ext)s", "webm")
            tam = dich + ".part"
            if goi is not None:
                goi.append(os.path.basename(dich))
            if os.path.exists(dich):
                return 0
            resume = os.path.getsize(tam) if os.path.exists(tam) else 0
            with open(tam, "ab" if resume else "wb") as f:
                f.write(LUONG[resume:resume + KHOI])
                f.flush()
                if cho_truoc_khi_xong is not None:
                    cho_truoc_khi_xong.wait(CHO_S)
                if hong_lan_dau and goi is not None and len(goi) == 1:
                    raise OSError("mạng đứt giữa chừng (giả)")
                f.write(LUONG[resume + KHOI:])
            os.replace(tam, dich)
            return 0

    return _Gia


def _chay_nen(ten, ham, ket_qua):
    def chay():
        try:
            ket_qua[ten] = ham()
        except BaseException as e:  # noqa: BLE001 — ghi lại để khẳng định
            ket_qua[ten] = e

    t = threading.Thread(target=chay, name=ten)
    t.start()
    return t


def _cho_den(dieu_kien, giay=CHO_S):
    het = time.monotonic() + giay
    while not dieu_kien():
        if time.monotonic() > het:
            return False
        time.sleep(0.02)
    return True


def test_luot_dang_cho_khoa_tai_bam_dung_thi_thoi_cho_ngay(tmp_path, monkeypatch):
    import yt_dlp

    from engine import Cancelled

    tha = threading.Event()
    goi: list = []
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _gia_don_gian(cho_truoc_khi_xong=tha, goi=goi))
    data = tmp_path / "data"
    giu, cho = _engine(tmp_path, data), _engine(tmp_path, data)
    ket_qua: dict = {}
    t_giu = _chay_nen("giu", lambda: giu.download_audio(URL, VID), ket_qua)
    assert _cho_den(lambda: len(goi) == 1), "lượt giữ khoá chưa bắt đầu tải"
    tin: list = []
    t_cho = _chay_nen("cho", lambda: cho.download_audio(URL, VID, progress=lambda p, m: tin.append(m)), ket_qua)
    assert _cho_den(lambda: any("Một lượt quét khác đang tải audio" in m for m in tin)), tin
    cho.cancel_event.set()                          # người dùng bấm Dừng lượt đang chờ
    t_cho.join(CHO_S)
    assert not t_cho.is_alive() and isinstance(ket_qua["cho"], Cancelled), ket_qua
    assert len(goi) == 1, "lượt đã Dừng không được gọi yt-dlp"
    tha.set()
    t_giu.join(CHO_S)
    with open(ket_qua["giu"], "rb") as f:
        assert f.read() == LUONG


def test_luot_giu_khoa_hong_giua_chung_thi_luot_cho_tu_tai_tiep_mot_minh(tmp_path, monkeypatch):
    import yt_dlp

    tha = threading.Event()
    goi: list = []
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _gia_don_gian(cho_truoc_khi_xong=tha, hong_lan_dau=True, goi=goi))
    data = tmp_path / "data"
    giu, cho = _engine(tmp_path, data), _engine(tmp_path, data)
    ket_qua: dict = {}
    t_giu = _chay_nen("giu", lambda: giu.download_audio(URL, VID), ket_qua)
    assert _cho_den(lambda: len(goi) == 1)
    tin: list = []
    t_cho = _chay_nen("cho", lambda: cho.download_audio(URL, VID, progress=lambda p, m: tin.append(m)), ket_qua)
    assert _cho_den(lambda: any("Một lượt quét khác đang tải audio" in m for m in tin)), tin
    assert len(goi) == 1, "lượt chờ không được gọi yt-dlp khi lượt kia còn đang tải"
    tha.set()                                       # lượt giữ khoá đứt mạng, để lại .part, nhả khoá
    t_giu.join(CHO_S)
    t_cho.join(CHO_S)
    assert not t_cho.is_alive() and isinstance(ket_qua["giu"], Exception), ket_qua
    assert len(goi) == 2, goi
    assert isinstance(ket_qua["cho"], str), ket_qua   # lượt chờ tải nốt một mình (nối .part = tiếp tục hợp lệ)
    with open(ket_qua["cho"], "rb") as f:
        assert f.read() == LUONG
    # File khoá nằm NGOÀI thư mục tải: bộ đệm chỉ có đúng file audio.
    assert sorted(os.listdir(data / "downloads")) == [f"{VID}.webm"]


def test_khoa_tai_chi_theo_dung_ten_file_video_khac_va_ban_mot_phan_khong_phai_cho(tmp_path):
    data = tmp_path / "data"
    a, b = _engine(tmp_path, data), _engine(tmp_path, data)
    with a._khoa_tai_audio(VID, VID):
        cho_xong = threading.Event()

        def lay_khac():
            with b._khoa_tai_audio("bbbbbbbbbbb", "bbbbbbbbbbb"), \
                    b._khoa_tai_audio(b._ten_phan_dau(VID, 10800), VID):
                cho_xong.set()

        t = threading.Thread(target=lay_khac)
        t.start()
        assert cho_xong.wait(CHO_S), "video khác / bản một phần không được chờ khoá của bản đầy đủ"
        t.join(CHO_S)
    # Nhả rồi thì lấy lại được ngay.
    with b._khoa_tai_audio(VID, VID):
        pass
