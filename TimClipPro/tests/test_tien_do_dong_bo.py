# -*- coding: utf-8 -*-
"""Tiến độ + hiệu suất có cấu trúc của lượt ĐỒNG BỘ KÊNH (`tien_do_dong_bo`, `ui_tien_do_dong_bo`, móc vào `channel`).

Không mạng: yt-dlp giả (`tests/ytdlp_gia.py`) mở rộng để gọi `progress_hooks` + `logger.debug` như yt-dlp thật; FFmpeg
nén thay bằng hàm giả. Đồng hồ giả để ETA/tốc độ tất định. Cookie GIẢ chỉ để kiểm không rò rỉ.
"""

import json
import shutil
import sys
import threading

import pytest
import yt_dlp

import channel
import process_runner
import tien_do_dong_bo as td
import truy_cap_youtube as t
import ui_tien_do_dong_bo as ui
import ytdlp_chung as y
from channel import ChannelSync
from ytdlp_gia import AUTH, BOT, YdlKichBan, ma_video

DAI = 600.0
BI_MAT = "GIA-BI-MAT-TELEMETRY-9d41"
SAN_SANG = y.KhaNangJs(True, node=r"C:\gia\nodejs\node.exe", node_phien_ban="24.21.0", ejs_phien_ban="0.8.0")


class DongHo:
    """Đồng hồ giả (cả wall lẫn đơn điệu) — test điều khiển thời gian."""

    def __init__(self, t0=1_000_000.0):
        self.t = t0

    def __call__(self):
        return self.t

    def tien(self, s):
        self.t += s


def _so(dh=None):
    dh = dh or DongHo()
    return td.SoDongBo(dong_ho=dh, dong_ho_don_dieu=dh), dh


def _ma(i):
    return f"p{i:010d}"


def _danh_sach(ids):
    return {"_type": "playlist", "id": "UCthu", "entries": [
        {"id": m, "title": f"Video {m}", "url": f"https://www.youtube.com/watch?v={m}", "duration": DAI} for m in ids]}


# ---------------------------------------------------------------- 1. sổ tiến độ: giai đoạn, số đếm, thống kê

def test_giai_doan_va_thoi_gian_tung_cong_doan():
    so, dh = _so()
    so.liet_ke()
    assert so.anh().giai_doan_luot == td.GD_LIET_KE
    so.liet_ke_xong(80)
    so.kiem(10, 80)
    assert so.anh().giai_doan_luot == td.GD_KIEM and so.anh().kiem_da == 10
    so.ke_hoach(da_co=74, can_tai=6, han_che_bo_qua=1, se_thu=5)
    so.video_bat_dau(1, 5, "abc", "Tiêu đề")
    dh.tien(2)                                            # hỏi YouTube 2 s
    so.thong_diep_ytdlp("[download] Sleeping 3.50 seconds as required by the site...")
    a = so.anh()
    assert a.video.giai_doan == td.GD_CHO and a.video.nghi_du_kien_s == 3.5
    dh.tien(3.5)
    so.hook_tai({"status": "downloading", "downloaded_bytes": 1_000_000, "total_bytes": 4_000_000, "speed": 2e6,
                 "eta": 1.5, "info_dict": {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus"}})
    a = so.anh()
    assert a.video.giai_doan == td.GD_TAI and a.video.ty_le_tai == 0.25 and a.video.toc_do_tai == 2e6
    assert a.video.chi_audio is True and "251 webm opus (audio)" == a.video.dinh_dang
    dh.tien(2)
    so.hook_tai({"status": "finished", "downloaded_bytes": 4_000_000, "total_bytes": 4_000_000})
    so.giai_doan(td.GD_NEN, ffmpeg_tong_s=DAI)
    dh.tien(1)
    so.tien_do_ffmpeg({"out_time_us": str(300 * 10**6), "progress": "continue"})
    a = so.anh()
    assert a.video.ty_le_nen == 0.5 and a.video.ffmpeg_toc_do_x == pytest.approx(300.0)
    dh.tien(1)
    so.giai_doan(td.GD_XAC_MINH)
    dh.tien(0.2)
    so.giai_doan(td.GD_LUU)
    dh.tien(0.1)
    so.video_xong("moi", media_s=DAI, byte_nen=4_800_000)
    a = so.anh()
    assert a.moi == 1 and a.video is None and a.byte_tai_tong == 4_000_000 and a.byte_nen_tong == 4_800_000
    tk = a.thong_ke
    assert tk[td.GD_TRICH_XUAT].tong == pytest.approx(2) and tk[td.GD_CHO].tong == pytest.approx(3.5)
    assert tk[td.GD_TAI].tong == pytest.approx(2) and tk[td.GD_NEN].tong == pytest.approx(2)
    assert tk[td.GD_XAC_MINH].tong == pytest.approx(0.2) and tk[td.GD_LUU].tong == pytest.approx(0.1)
    assert tk["VIDEO"].trung_vi == pytest.approx(9.8)
    assert a.nghi_tong_s == pytest.approx(3.5)
    assert a.diem_nghen[0] == td.GD_CHO
    assert a.chua_thu == 4 and a.ty_le == pytest.approx(0.2)


def test_dem_loi_tuoi_hoi_vien_va_doi_client():
    so, dh = _so()
    so.ke_hoach(da_co=0, can_tai=3, han_che_bo_qua=0, se_thu=3)
    for i, loai in enumerate(("AGE_RESTRICTED", "MEMBERS_ONLY", "HTTP_FORBIDDEN"), start=1):
        so.video_bat_dau(i, 3, _ma(i), "x")
        so.doi_client("android")
        dh.tien(1)
        so.video_xong("loi", loai=loai, ly_do="lý do")
    a = so.anh()
    assert (a.loi, a.gioi_han_tuoi, a.chi_hoi_vien, a.doi_client_tong, a.moi) == (3, 1, 1, 3, 0)
    assert a.chua_thu == 0


def test_hook_tai_gop_nhip_va_khong_bao_gio_nem_loi():
    so, dh = _so()
    so.ke_hoach(da_co=0, can_tai=1, han_che_bo_qua=0, se_thu=1)
    so.video_bat_dau(1, 1, "a", "x")
    so.hook_tai({"status": "downloading", "downloaded_bytes": 1, "total_bytes": 100})
    for i in range(500):                                   # 500 lần gọi cùng một thời điểm → gộp
        so.hook_tai({"status": "downloading", "downloaded_bytes": 2 + i, "total_bytes": 100})
    assert so.anh().video.byte_tai == 1, "trong 0,25 s chỉ nhận 1 cập nhật"
    dh.tien(td.NHIP_TAI_S)
    so.hook_tai({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100})
    assert so.anh().video.byte_tai == 50
    so.hook_tai({"status": "finished", "downloaded_bytes": 100, "total_bytes": 100})
    assert so.anh().video.byte_tai == 100, "«finished» luôn được nhận"
    so.hook_tai({"status": "downloading", "downloaded_bytes": object()})   # dữ liệu hỏng: không ném
    so.hook_tai(None)
    so.tien_do_ffmpeg({"out_time_us": "rác"})
    so.thong_diep_ytdlp(None)


def test_eta_khong_bia_so_khi_thieu_du_lieu_hoac_toc_do_doi_manh():
    so, dh = _so()
    so.ke_hoach(da_co=0, can_tai=100, han_che_bo_qua=0, se_thu=100)
    a = so.anh()
    assert a.eta_s is None and "Đang ước tính" in a.eta_ly_do and ui.chu_eta(a) == "Đang ước tính"
    for i in range(td.ETA_TOI_THIEU_VIDEO - 1):
        so.video_bat_dau(i + 1, 100, _ma(i), "x")
        dh.tien(20)
        so.video_xong("moi", media_s=DAI)
    assert so.anh().eta_s is None, "chưa đủ số video"
    for i in range(td.ETA_TOI_THIEU_VIDEO, 20):
        so.video_bat_dau(i + 1, 100, _ma(i), "x")
        dh.tien(20)
        so.video_xong("moi", media_s=DAI)
    a = so.anh()
    assert a.eta_s == pytest.approx(20 * (100 - 19), rel=1e-6) and a.eta_tin_cay == "cao"
    assert a.video_moi_gio == pytest.approx(180.0)
    # Một dãy video hạn chế lỗi NHANH (1 s/video) làm tốc độ đổi mạnh → không hiện ETA giả.
    for i in range(20, 30):
        so.video_bat_dau(i + 1, 100, _ma(i), "x")
        dh.tien(1)
        so.video_xong("loi", loai="AGE_RESTRICTED")
    a = so.anh()
    assert a.eta_s is None and "thay đổi" in a.eta_ly_do


def test_ket_thuc_trang_thai_va_tom_tat():
    so, dh = _so()
    so.ke_hoach(da_co=2, can_tai=2, han_che_bo_qua=0, se_thu=2)
    so.video_bat_dau(1, 2, "a", "x")
    dh.tien(5)
    so.ket_thuc("BI_CHAN", "YouTube yêu cầu xác minh không phải bot")
    a = so.anh()
    assert a.trang_thai == td.TT_BI_CHAN and a.video is None and a.eta_s is None and "bot" in a.ly_do_dung
    hs = so.tom_tat()
    assert hs["moi"] == 0 and "giai_doan" in hs and json.dumps(hs)
    for dong, tt in (("DAY_DU", td.TT_XONG), ("MOT_PHAN", td.TT_MOT_PHAN), ("DA_HUY", td.TT_DA_HUY)):
        s2, _ = _so()
        s2.ket_thuc(dong)
        assert s2.anh().trang_thai == tt


def test_an_toan_luong_va_co_tran():
    """Một worker (như lượt đồng bộ thật) + luồng hook tải + luồng FFmpeg + giao diện đọc cùng lúc."""
    so = td.SoDongBo()
    so.ke_hoach(da_co=0, can_tai=10_000, han_che_bo_qua=0, se_thu=10_000)
    loi, xong = [], threading.Event()

    def worker():
        try:
            for i in range(1200):
                so.video_bat_dau(i + 1, 10_000, f"v{i}", "x")
                so.giai_doan(td.GD_NEN, ffmpeg_tong_s=10.0)
                so.ghi(f"sự kiện {i}")
                so.video_xong("moi", media_s=1.0)
        except Exception as e:  # noqa: BLE001
            loi.append(e)
        finally:
            xong.set()

    def hook():
        while not xong.is_set():
            so.hook_tai({"status": "downloading", "downloaded_bytes": 10, "total_bytes": 100})
            so.tien_do_ffmpeg({"out_time_us": "1000000", "progress": "continue"})

    def doc():
        while not xong.is_set():
            a = so.anh()
            assert a.moi <= 1200

    ls = [threading.Thread(target=worker), threading.Thread(target=hook), threading.Thread(target=doc)]
    for x in ls:
        x.start()
    for x in ls:
        x.join()
    a = so.anh()
    assert not loi and a.moi == 1200 and a.video is None
    assert len(a.su_kien) <= td.TRAN_SU_KIEN
    assert a.thong_ke["VIDEO"].so_mau == td.TRAN_MAU < 1200, "mẫu thống kê có trần"


# ---------------------------------------------------------------- 2. FFmpeg -progress: callback trực tiếp

def test_chay_lenh_media_goi_callback_tien_do_va_nuot_loi_callback():
    kich_ban = ("import sys\n"
                "for us in (1000000, 2000000, 3000000):\n"
                "    print(f'out_time_us={us}'); print('progress=continue'); sys.stdout.flush()\n"
                "print('out_time_us=4000000'); print('progress=end')\n")
    nhan = []
    r = process_runner.chay_lenh_media([sys.executable, "-c", kich_ban], theo_doi_tien_do=True,
                                       them_co_tien_do=False, khi_tien_do=nhan.append, tran_tong_s=30)
    assert r.returncode == 0
    assert [x["out_time_us"] for x in nhan] == ["1000000", "2000000", "3000000", "4000000"]
    assert nhan[-1]["progress"] == "end"

    def hong(_):
        raise RuntimeError("callback hỏng")
    r2 = process_runner.chay_lenh_media([sys.executable, "-c", kich_ban], theo_doi_tien_do=True,
                                        them_co_tien_do=False, khi_tien_do=hong, tran_tong_s=30)
    assert r2.returncode == 0 and r2.tien_do_cuoi.get("out_time_us") == "4000000"


# ---------------------------------------------------------------- 3. móc vào ChannelSync (yt-dlp giả gọi hook thật)

class _YdlCoHook(YdlKichBan):
    """yt-dlp giả gọi `progress_hooks` và `logger.debug` (nghỉ giãn nhịp) giống yt-dlp thật khi tải."""

    def __init__(self, *a, dinh_dang=None, **k):
        super().__init__(*a, **k)
        self.dinh_dang = dinh_dang or {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus"}

    def __call__(self, opts):
        s = super().__call__(opts)
        goc = s.extract_info
        hooks = list(opts.get("progress_hooks") or [])
        logger = opts.get("logger")
        cha = self

        def extract_info(url, download=False):
            loi = cha.tai.get(ma_video(url), cha.tai.get("*"))
            if download and isinstance(loi, str):
                return goc(url, download=download)   # yt-dlp thật lỗi ở khâu trích xuất: không nghỉ, không hook tải
            if download:
                if logger is not None:
                    logger.debug("[download] Sleeping 2.50 seconds as required by the site...")
                info_dict = dict(cha.dinh_dang, id=url[-11:])
                for h in hooks:
                    h({"status": "downloading", "downloaded_bytes": 5_000, "total_bytes": 10_000, "speed": 1e6,
                       "eta": 0, "info_dict": info_dict})
            info = goc(url, download=download)
            if download:
                for h in hooks:
                    h({"status": "finished", "downloaded_bytes": 10_000, "total_bytes": 10_000, "info_dict": {}})
            return info
        s.extract_info = extract_info
        return s


@pytest.fixture()
def may(monkeypatch):
    monkeypatch.setattr(y, "kha_nang_js", lambda: SAN_SANG)
    for k in ("metadata", "listing"):
        monkeypatch.setitem(t.NGAN_SACH, k, t.NganSach(cho_tam_thoi=(0.01,), cho_429=(0.01,)))
    monkeypatch.setattr(channel, "do_dai_luong_tieng", lambda p: DAI)


def _cs(kho, so=None, cau_hinh=None):
    cs = ChannelSync(str(kho), cau_hinh_mang=cau_hinh, theo_doi=so)

    def nen(nguon, tam, _tham_chieu, _huy):
        shutil.copyfile(nguon, tam)
        return ""
    cs._nen_va_kiem = nen
    return cs


def test_dong_bo_ghi_tien_do_co_cau_truc_va_tom_tat_hieu_suat(tmp_path, monkeypatch, may):
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    ids = [_ma(i) for i in range(4)]
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _YdlCoHook(tai={_ma(1): AUTH}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    so = td.SoDongBo()
    anh_trong_luc = []

    def tien_do(_pct, _msg):
        anh_trong_luc.append(so.anh())
    r = _cs(tmp_path / "kho", so).sync("https://www.youtube.com/@KenhThu", progress=tien_do)
    a = so.anh()
    assert r["moi"] == 3 and a.moi == 3 and a.loi == 1 and a.gioi_han_tuoi == 1
    assert a.tong_kenh == 4 and a.can_tai == 4 and a.se_thu == 4 and a.chua_thu == 0
    assert a.trang_thai == td.TT_MOT_PHAN and a.ket_thuc is not None
    assert a.byte_tai_tong == 30_000, "3 video tải xong × 10 000 byte (video lỗi không tải byte nào)"
    assert a.thong_ke[td.GD_CHO].so_mau == 3 and a.nghi_tong_s >= 0
    assert a.thong_ke[td.GD_TAI].so_mau == 3 and a.thong_ke[td.GD_LUU].so_mau == 3
    assert {x.giai_doan_luot for x in anh_trong_luc} >= {td.GD_LIET_KE, td.GD_KIEM}
    hs = r["hieu_suat"]
    assert hs["moi"] == 3 and hs["byte_tai"] == 30_000 and hs["giai_doan"]["DOWNLOADING"]["n"] == 3
    assert any("[2/4]" in e.noi_dung and "AGE_RESTRICTED" in e.noi_dung for e in a.su_kien)
    assert all("youtube.com" not in e.noi_dung for e in a.su_kien), "nhật ký không chứa URL"


def test_dinh_dang_co_hinh_duoc_dem_va_canh_bao(tmp_path, monkeypatch, may):
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    ids = [_ma(i) for i in range(2)]
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _YdlCoHook(
        liet_ke=lambda _p, _u: _danh_sach(ids),
        dinh_dang={"format_id": "18", "ext": "mp4", "vcodec": "avc1.42001E", "acodec": "mp4a.40.2",
                   "formats": [{"format_id": "18", "vcodec": "avc1", "acodec": "mp4a"},
                               {"format_id": "sb0", "vcodec": "none", "acodec": "none"}]}))
    so = td.SoDongBo()
    r = _cs(tmp_path / "kho", so).sync("https://www.youtube.com/@KenhThu")
    assert r["hieu_suat"]["tai_co_hinh"] == 2 and so.anh().tai_co_hinh == 2
    assert sum("có 0 định dạng chỉ-tiếng / 2" in e.noi_dung for e in so.anh().su_kien) == 2, \
        "bằng chứng: client đã dùng không cung cấp định dạng chỉ-tiếng nào"
    assert any(m == "warning" and "CÓ HÌNH" in c for m, c in ui.dong_hieu_suat(r["hieu_suat"]))


def test_bot_check_van_dung_ngay_va_tien_do_bao_bi_chan(tmp_path, monkeypatch, may):
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    ids = [_ma(i) for i in range(5)]
    ydl = _YdlCoHook(tai={_ma(1): BOT}, liet_ke=lambda _p, _u: _danh_sach(ids))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    so = td.SoDongBo()
    r = _cs(tmp_path / "kho", so).sync("https://www.youtube.com/@KenhThu")
    assert ydl.dem("tai") == 2 and r["trang_thai"] == "BI_CHAN"
    a = so.anh()
    assert a.trang_thai == td.TT_BI_CHAN and a.chua_thu == 3 and a.ly_do_dung


def test_resume_khong_tai_lai_file_da_xac_nhan_va_tien_do_dem_da_co(tmp_path, monkeypatch, may):
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    kho = tmp_path / "kho"
    kho.mkdir()
    meta, archive = {}, []
    for i in range(74):
        ten = f"20240101 - cu {i} [{_ma(i)}].opus"
        (kho / ten).write_bytes(b"opus " + str(i).encode())
        meta[ten] = {"id": _ma(i), "title": f"cu {i}", "duration": DAI,
                     "xac_nhan_tep": {"kich_thuoc": (kho / ten).stat().st_size, "do_dai": DAI}}
        archive.append(f"youtube {_ma(i)}\n")
    (kho / "clips_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (kho / "downloaded.txt").write_text("".join(archive), encoding="utf-8")
    ids = [_ma(i) for i in range(76)]
    ydl = _YdlCoHook(liet_ke=lambda _p, _u: _danh_sach(ids))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    so = td.SoDongBo()
    r = _cs(kho, so).sync("https://www.youtube.com/@KenhThu")
    assert ydl.dem("tai") == 2 and r["moi"] == 2
    a = so.anh()
    assert a.da_co == 74 and a.can_tai == 2 and a.trang_thai == td.TT_XONG


def test_khong_ro_ri_cookie_vao_tien_do(tmp_path, monkeypatch, may):
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    c = tmp_path / "c.txt"
    c.write_text("# Netscape HTTP Cookie File\n"
                 f".youtube.com\tTRUE\t/\tTRUE\t4102444800\tLOGIN_INFO\t{BI_MAT}\n", encoding="utf-8")
    ch = y.CauHinhMang(cookiefile=str(c))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _YdlCoHook(liet_ke=lambda _p, _u: _danh_sach([_ma(0)])))
    so = td.SoDongBo()
    r = _cs(tmp_path / "kho", so, ch).sync("https://www.youtube.com/@KenhThu")
    a = so.anh()
    toan_bo = repr(a) + json.dumps(r["hieu_suat"], default=str) + repr(ui.the_kpi(a)) + repr(ui.dong_su_kien(a))
    assert BI_MAT not in toan_bo and str(c) not in toan_bo


# ---------------------------------------------------------------- 4. bỏ FFprobe đo lặp trên cùng file

def test_moi_video_chi_mot_lan_ffprobe_tren_file_da_nen(tmp_path, monkeypatch, may):
    """Trước: kiem_file_audio (sau nén) + do_dai_media trong vòng lặp = 2 lần FFprobe CÙNG một file đã đặt vào kho."""
    dem = []

    def ffprobe_gia(p):
        dem.append(str(p))
        return DAI
    monkeypatch.setattr(channel, "do_dai_media", ffprobe_gia)

    def ffmpeg_gia(lenh, **k):
        with open(lenh[-1], "wb") as f:
            f.write(b"opus gia " + lenh[-1].encode()[-20:])
        if k.get("khi_tien_do"):
            k["khi_tien_do"]({"out_time_us": str(int(DAI * 1e6)), "progress": "end"})
        return process_runner.KetQuaLenh(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(channel, "chay_lenh_media", ffmpeg_gia)
    ids = [_ma(i) for i in range(3)]
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _YdlCoHook(liet_ke=lambda _p, _u: _danh_sach(ids)))
    so = td.SoDongBo()
    cs = ChannelSync(str(tmp_path / "kho"), theo_doi=so)            # _nen_va_kiem THẬT (FFmpeg giả)
    r = cs.sync("https://www.youtube.com/@KenhThu")
    assert r["moi"] == 3
    tren_kho = [p for p in dem if "_tam" not in p]
    assert len(dem) == 3 and tren_kho == [], f"mỗi video đúng 1 FFprobe (trên file tạm khi kiểm), không đo lại: {dem}"
    meta = json.loads((tmp_path / "kho" / "clips_meta.json").read_text(encoding="utf-8"))
    assert all(m["duration_media"] == DAI and m["xac_nhan_tep"] for m in meta.values()), "metadata giữ nguyên ý nghĩa"
    assert so.anh().thong_ke[td.GD_NEN].so_mau == 3 and so.anh().thong_ke[td.GD_XAC_MINH].so_mau == 3


def test_file_doi_sau_khi_kiem_thi_van_do_lai(tmp_path, monkeypatch):
    """Dùng lại chỉ khi CHÍNH file đó (đường dẫn + kích thước + mtime) — khác là đo lại như trước."""
    dem = []
    monkeypatch.setattr(channel, "do_dai_media", lambda p: dem.append(p) or 123.0)
    cs = ChannelSync(str(tmp_path / "kho"))
    f = tmp_path / "kho" / "a.opus"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"12345")
    st = f.stat()
    cs._lan_kiem_cuoi = ("tam", DAI, st.st_size, st.st_mtime_ns)
    cs._ghi_do_dai_vua_kiem("tam", str(f))
    assert cs._do_dai_file_vua_dat(str(f)) == DAI and dem == []
    cs._lan_kiem_cuoi = ("tam", DAI, st.st_size, st.st_mtime_ns)
    cs._ghi_do_dai_vua_kiem("tam", str(f))
    f.write_bytes(b"1234567")                                    # bị thay sau khi kiểm
    assert cs._do_dai_file_vua_dat(str(f)) == 123.0 and len(dem) == 1
    assert cs._do_dai_file_vua_dat(str(f)) == 123.0, "không có bản nhớ → đo lại"


# ---------------------------------------------------------------- 5. giao diện: chỉ đọc ảnh chụp, không bịa số

def test_ui_hien_kpi_tien_do_tai_va_nen():
    so, dh = _so()
    so.liet_ke_xong(1263)
    so.ke_hoach(da_co=74, can_tai=1189, han_che_bo_qua=0, se_thu=1189)
    so.video_bat_dau(5, 1189, "abc", "Một video")
    so.hook_tai({"status": "downloading", "downloaded_bytes": 30_000_000, "total_bytes": 75_000_000, "speed": 1.05e7,
                 "eta": 4, "info_dict": {"format_id": "18", "ext": "mp4", "vcodec": "avc1", "acodec": "mp4a"}})
    a = so.anh()
    kpi = {n: (v, phu) for n, v, _, phu in ui.the_kpi(a)}
    assert kpi["Đã có (giữ nguyên)"][0] == "74" and kpi["Còn lại (ETA)"] == ("—", "Đang ước tính")
    dong = ui.dong_video(a)
    tai = [x for x in dong if x[0] == "tai"][0]
    assert tai[2] == pytest.approx(0.4) and "10.5 MB/s" in tai[1] and "30.0 MB / 75.0 MB" in tai[1]
    assert any(x[0] == "canh_bao" and "CÓ HÌNH" in x[1] for x in dong)
    so.hook_tai({"status": "finished", "downloaded_bytes": 75_000_000, "total_bytes": 75_000_000})
    so.giai_doan(td.GD_NEN, ffmpeg_tong_s=1800.0)
    dh.tien(2)
    so.tien_do_ffmpeg({"out_time_us": str(900 * 10**6), "progress": "continue"})
    nen = [x for x in ui.dong_video(so.anh()) if x[0] == "nen"][0]
    assert nen[2] == pytest.approx(0.5) and "450×" in nen[1]
    assert "Đã xét 0/1189" in ui.dong_tong(so.anh())


def test_ui_kpi_gia_tri_ngan_khong_bi_cat_va_dang_uoc_tinh_van_hien():
    """Nghiệm thu trên 8502 (15/10): `st.metric` cắt chữ dài ở cửa sổ 1280 px — «Đang ước …», «226.6 vide…»,
    «1 phút 20 …», «20 giây (đ…». Giá trị thẻ phải ngắn; chữ phụ («Đang ước tính», độ tin cậy, giờ audio) nằm ở dòng
    nhỏ bên dưới (delta không mũi tên), đơn vị nằm ở nhãn."""
    so, dh = _so()
    so.liet_ke_xong(1263)
    so.ke_hoach(da_co=74, can_tai=1189, han_che_bo_qua=0, se_thu=1189)
    kpi = {n: (v, phu) for n, v, _, phu in ui.the_kpi(so.anh())}
    assert kpi["Còn lại (ETA)"] == ("—", "Đang ước tính")
    for i in range(40):                                    # lượt dài: 40 video × 1000 s ≈ 11 giờ
        so.video_bat_dau(i + 1, 1189, _ma(i), f"Video {i}")
        dh.tien(1000)
        so.video_xong("moi", media_s=DAI, byte_nen=4_800_000)
    the = ui.the_kpi(so.anh())
    assert all(len(v) <= 9 for _, v, _, _ in the), the
    kpi = {n: (v, phu) for n, v, _, phu in the}
    assert kpi["Thời gian chạy"][0] == "11:06:40"
    assert kpi["Tốc độ (video/giờ)"] == ("3.6", "0.6 giờ audio/giờ")
    eta, phu = kpi["Còn lại (ETA)"]
    assert eta.count(":") == 2 and "tin cậy" in phu

    class StGhi:
        def __init__(self):
            self.metric_kw = []

        def __getattr__(self, ten):
            def ham(*a, **k):
                if ten == "metric":
                    self.metric_kw.append((a, k))
                return [self for _ in range(a[0])] if ten == "columns" else self
            return ham

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    st = StGhi()
    ui.ve_tien_do_dong_bo(st, so.anh())
    assert len(st.metric_kw) == 8
    assert all(k.get("delta_arrow") == "off" and k.get("delta_color") == "off" for _a, k in st.metric_kw)
    assert any(k.get("delta") == "0.6 giờ audio/giờ" for _a, k in st.metric_kw)


def test_ui_ve_bang_streamlit_gia_khong_loi_va_khong_sua_anh():
    class StGia:
        def __init__(self):
            self.goi = []

        def __getattr__(self, ten):
            def ham(*a, **k):
                self.goi.append(ten)
                return [StGia() for _ in range(a[0])] if ten == "columns" else self
            return ham

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    so, dh = _so()
    so.ke_hoach(da_co=1, can_tai=2, han_che_bo_qua=0, se_thu=2)
    so.video_bat_dau(1, 2, "a", "x")
    dh.tien(3)
    so.video_xong("moi", media_s=DAI)
    a = so.anh()
    st = StGia()
    ui.ve_tien_do_dong_bo(st, a)
    assert "progress" in st.goi and "dataframe" in st.goi
    assert so.anh().moi == a.moi == 1


# ---------------------------------------------------------------- 6. màn tiến độ thật trong app (AppTest, không server)

def test_app_man_dong_bo_dang_chay_ve_tu_anh_chup_va_nut_dung_giu_nghia_cu(tmp_path, monkeypatch):
    import time as _time
    from pathlib import Path

    import streamlit
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    assert not at.exception
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)     # chụp đúng một khung hình
    nghi = []
    goc_sleep = _time.sleep
    monkeypatch.setattr(_time, "sleep", lambda s: nghi.append(s) if s in (0.75, 1.0) else goc_sleep(s))

    so, dh = _so(DongHo(_time.time()))
    so.liet_ke_xong(1263)
    so.ke_hoach(da_co=74, can_tai=1189, han_che_bo_qua=0, se_thu=1189)
    for i in range(6):
        so.video_bat_dau(i + 1, 1189, _ma(i), f"Video {i}")
        dh.tien(25)
        so.video_xong("moi", media_s=DAI, byte_nen=4_800_000)
    so.video_bat_dau(7, 1189, _ma(7), "Video đang tải")
    so.hook_tai({"status": "downloading", "downloaded_bytes": 30_000_000, "total_bytes": 75_000_000, "speed": 1e7,
                 "eta": 4, "info_dict": {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus"}})
    # Đồng bộ kênh = làn RIÊNG (D-29): tác vụ nền thật chặn tới khi bị huỷ, cờ huỷ RIÊNG của lượt.
    import threading as _threading

    import tac_vu_nen

    huy = _threading.Event()
    tv = tac_vu_nen.TacVuNen("channel", huy=huy.set, so_dong_bo=so)
    tv.bat_dau(at.session_state.eng, lambda progress: huy.wait(30) and {}, (), {},
               job=at.session_state.job_dong_bo)
    at.session_state.so_dong_bo = so
    at.session_state.tac_vu_dong_bo = tv
    try:
        t0 = _time.perf_counter()
        at.run()
        khung_s = _time.perf_counter() - t0
        # Khung đồng bộ tự làm mới bằng fragment (run_every 1 giây) — KHÔNG ngủ chặn cả trang như màn tiến độ cũ.
        assert nghi == [], "khung đồng bộ không được time.sleep chặn cả trang"
        assert not at.exception
        _kiem_khung_dong_bo(at, khung_s, huy)
    finally:
        huy.set()


def _kiem_khung_dong_bo(at, khung_s, huy):
    chu = " ".join(str(getattr(x, "value", "")) for x in [*at.markdown, *at.caption, *at.header, *at.warning,
                                                           *at.text])
    assert "Đang đồng bộ kênh" in chu and "Video 7/1189: Video đang tải" in chu
    nhan = {m.label for m in at.metric}
    assert {"Đã có (giữ nguyên)", "Tải mới", "Lỗi", "Bị hạn chế", "Chưa thử", "Thời gian chạy", "Tốc độ (video/giờ)",
            "Còn lại (ETA)"} <= nhan
    assert any(m.label == "Đã có (giữ nguyên)" and m.value == "74" for m in at.metric)
    assert len(at.dataframe) >= 1
    assert khung_s < 2.0, f"một khung hình tiến độ mất {khung_s:.2f} s"
    # Nút Dừng: chỉ gửi yêu cầu huỷ (cờ huỷ RIÊNG của lượt đồng bộ, không phải cờ của Engine — D-29) — KHÔNG đánh
    # dấu xong trước khi worker xác nhận.
    nut = next(b for b in at.button if b.label == "⏹️ Dừng đồng bộ" and b.key == "dung_dong_bo")
    nut.click().run()
    assert huy.is_set()
    assert not at.session_state.eng.cancel_event.is_set()
    assert not at.session_state.job_dong_bo["results"]


def test_so_tien_do_hong_khong_lam_hong_luot_dong_bo(tmp_path, monkeypatch, may):
    """Đo đạc là phụ: mọi phương thức ghi của sổ đều nuốt lỗi — lượt đồng bộ vẫn tải đủ, kết quả vẫn đúng."""
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    ids = [_ma(i) for i in range(3)]
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _YdlCoHook(liet_ke=lambda _p, _u: _danh_sach(ids)))
    so = td.SoDongBo()

    def hong():
        raise RuntimeError("đồng hồ hỏng")
    so._now = hong
    so._mono = hong
    so.ke_hoach(da_co="không phải số", can_tai=1, han_che_bo_qua=0, se_thu=1)   # không ném
    so.video_bat_dau(None, 1, "a", "x")                                         # không ném
    r = _cs(tmp_path / "kho", so).sync("https://www.youtube.com/@KenhThu")
    assert r["moi"] == 3 and r["trang_thai"] == "DAY_DU" and r["hieu_suat"] == {}
    archive = (tmp_path / "kho" / "downloaded.txt").read_text(encoding="utf-8")
    assert all(f"youtube {m}" in archive for m in ids)


# ---------------------------------------------------------------- 7. review độc lập (711f0f8): sửa P2 + P3

def test_nghi_giua_request_tinh_vao_cho_khong_tinh_vao_hoi_youtube():
    so, dh = _so()
    so.ke_hoach(da_co=0, can_tai=1, han_che_bo_qua=0, se_thu=1)
    so.video_bat_dau(1, 1, "a", "x")
    so.thong_diep_ytdlp("[youtube] Sleeping 1.00 seconds ...")            # sleep_interval_requests của yt-dlp
    so.thong_diep_ytdlp("Sleeping 2.00 seconds ...")                       # chờ thử lại HTTP (không tiền tố)
    dh.tien(5)                                                             # 2 s hỏi YouTube thật + 3 s nghỉ
    assert so.anh().video.giai_doan == td.GD_TRICH_XUAT, "nghỉ giữa request không đổi giai đoạn"
    so.thong_diep_ytdlp("[download] Sleeping 3.50 seconds as required by the site...")
    a = so.anh()
    assert a.video.giai_doan == td.GD_CHO and a.video.nghi_ly_do == "theo yêu cầu của trang"
    dh.tien(3.5)
    so.hook_tai({"status": "finished", "downloaded_bytes": 1, "total_bytes": 1})
    so.video_xong("moi", media_s=1.0)
    tk = so.anh().thong_ke
    assert tk[td.GD_TRICH_XUAT].tong == pytest.approx(2.0) and tk[td.GD_CHO].tong == pytest.approx(6.5)
    assert any("theo yêu cầu của trang" in c for loai, c, _ in ui.dong_video(a) if loai == "chu")
    so.thong_diep_ytdlp("[download]  42.0% of 10.00MiB at 1.00MiB/s ETA 00:05")   # dòng tiến trình: bỏ qua


def test_doi_client_chi_dem_khi_that_su_thu_client_ke(tmp_path, monkeypatch, may):
    from ytdlp_gia import C403
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    ids = [_ma(i) for i in range(3)]

    def tai(phien, ma):
        if ma == _ma(2):
            return AUTH                                    # dừng đổi client ngay (lỗi của video)
        return C403 if phien.client == "" else None        # client mặc định 403, client kế tải được
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _YdlCoHook(tai={"*": tai}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    so = td.SoDongBo()
    r = _cs(tmp_path / "kho", so).sync("https://www.youtube.com/@KenhThu")
    assert r["moi"] == 2 and r["gioi_han_tuoi"] == 1
    assert so.anh().doi_client_tong == 1, "chỉ video đầu thật sự đổi client (video sau nhớ client tốt; video 18+ dừng)"


def test_eta_dem_lui_trong_luc_xu_ly_mot_video():
    so, dh = _so()
    so.ke_hoach(da_co=0, can_tai=100, han_che_bo_qua=0, se_thu=100)
    for i in range(19):
        so.video_bat_dau(i + 1, 100, _ma(i), "x")
        dh.tien(20)
        so.video_xong("moi", media_s=DAI)
    so.video_bat_dau(20, 100, _ma(20), "x")
    dh.tien(15)
    assert so.anh().eta_s == pytest.approx(20 * 81 - 15)


def test_dung_lai_do_dai_chi_khi_file_trong_kho_trung_ban_tam_da_kiem(tmp_path, monkeypatch):
    dem = []
    monkeypatch.setattr(channel, "do_dai_media", lambda p: dem.append(p) or 123.0)
    cs = ChannelSync(str(tmp_path / "kho"))
    tam = tmp_path / "kho" / "_tam" / "a.tmp.opus"
    tam.parent.mkdir(parents=True)
    tam.write_bytes(b"12345")
    st = tam.stat()
    cs._lan_kiem_cuoi = (str(tam), DAI, st.st_size, st.st_mtime_ns)
    dich = tmp_path / "kho" / "a.opus"
    dich.write_bytes(b"123456789")                         # KHÔNG phải bản đã kiểm (khác kích thước)
    cs._ghi_do_dai_vua_kiem(str(tam), str(dich))
    assert cs._do_dai_file_vua_dat(str(dich)) == 123.0 and len(dem) == 1
    import os as _os
    _os.replace(tam, dich)                                 # đúng bản đã kiểm (os.replace giữ kích thước + mtime)
    cs._lan_kiem_cuoi = (str(tam), DAI, st.st_size, st.st_mtime_ns)
    cs._ghi_do_dai_vua_kiem(str(tam), str(dich))
    assert cs._do_dai_file_vua_dat(str(dich)) == DAI and len(dem) == 1


def test_luot_loi_truoc_vong_lap_dong_so_tien_do(tmp_path, monkeypatch, may):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _YdlCoHook(liet_ke=lambda _p, _u: None))
    so = td.SoDongBo()
    with pytest.raises(RuntimeError):
        _cs(tmp_path / "kho", so).sync("https://www.youtube.com/@KenhThu")
    a = so.anh()
    assert a.trang_thai != td.TT_DANG_CHAY and a.ket_thuc is not None and a.ly_do_dung


def test_app_ve_tien_do_loi_thi_lui_ve_man_chung(tmp_path, monkeypatch):
    import time as _time
    from pathlib import Path

    import streamlit
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)
    goc_sleep = _time.sleep
    monkeypatch.setattr(_time, "sleep", lambda s: None if s in (0.75, 1.0) else goc_sleep(s))

    class SoHong:
        def anh(self):
            raise RuntimeError("ảnh chụp hỏng")
    at.session_state.so_dong_bo = SoHong()
    at.session_state.job.update({"running": True, "pct": 0.3, "msg": "[3/10] Video", "results": [], "error": "",
                                 "kind": "channel"})
    at.run()
    assert not at.exception
    assert any(b.label == "⏹️ Dừng lại" for b in at.button), "nút Dừng vẫn còn"
    assert any("[3/10] Video" in str(x.value) for x in at.info)
