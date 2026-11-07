# -*- coding: utf-8 -*-
"""Đồng bộ kênh: nén video vừa tải cùng lúc với tải video kế tiếp (D-35).

Bất biến: tải vẫn đúng MỘT luồng, nén đúng MỘT luồng, metadata + sổ đã tải ghi đúng thứ tự, lỗi hay Dừng không treo.
Không mạng: lớp yt-dlp và FFmpeg được thay bằng bản giả có đo chồng thời gian.
"""
from __future__ import annotations

import os
import threading
import time

import pytest

import channel
from channel import ChannelSync, VideoInfo
from conftest import _ghi_wav, _giai_dieu
from tien_do_dong_bo import GD_NEN, GD_TAI, SoDongBo
from truy_cap_youtube import PhienYouTube
from ui_tien_do_dong_bo import dong_video

CHO = 10.0


class Gia:
    """Tải + nén giả, đếm số luồng chạy đồng thời."""

    def __init__(self, cs: ChannelSync):
        self.cs = cs
        self.khoa = threading.Lock()
        self.tai, self.nen = 0, 0
        self.tai_max, self.nen_max = 0, 0
        self.lan_tai: list = []
        self.lan_nen: list = []
        self.bat_dau_tai: dict = {}
        self.hook_lan_hai: list = []
        self.khi_tai = lambda vid: None
        self.khi_nen = lambda vid: ""
        cs._tai_thu_tung_client = self.tai_gia
        cs._nen_va_kiem = self.nen_gia
        cs._do_dai_file_vua_dat = lambda f: 100.0

    def tai_gia(self, url, opts):
        vid = url.rsplit("/", 1)[-1]
        if vid in self.lan_tai:
            self.hook_lan_hai = opts["progress_hooks"]
        with self.khoa:
            self.tai += 1
            self.tai_max = max(self.tai_max, self.tai)
            self.lan_tai.append(vid)
        self.bat_dau_tai.setdefault(vid, threading.Event()).set()
        try:
            self.khi_tai(vid)
            with open(opts["outtmpl"].replace("%(id)s.%(ext)s", f"{vid}.webm"), "wb") as f:
                f.write(b"x")
            return {"id": vid, "title": vid, "duration": 100, "upload_date": "20260101"}
        finally:
            with self.khoa:
                self.tai -= 1

    def nen_gia(self, nguon, tam, tham_chieu, huy):
        vid = os.path.basename(nguon).split(".")[0]
        with self.khoa:
            self.nen += 1
            self.nen_max = max(self.nen_max, self.nen)
            self.lan_nen.append(vid)
        try:
            ly_do = self.khi_nen(vid)
            with open(tam, "wb") as f:
                f.write(b"y" * 10)
            return ly_do
        finally:
            with self.khoa:
                self.nen -= 1


def _kenh(tmp_path, n=3):
    ds = [VideoInfo(f"v{i}", f"Video {i}", "20260101", 100.0, f"https://youtu.be/v{i}") for i in range(1, n + 1)]
    cs = ChannelSync(str(tmp_path / "kho"))
    cs.list_channel = lambda *a, **k: list(ds)
    return cs, Gia(cs)


def _chay(cs, **k) -> dict:
    """Chạy trên luồng riêng để lỗi treo thành test đỏ, không làm treo cả bộ test."""
    ra: dict = {}
    t = threading.Thread(target=lambda: ra.update(cs.sync("kenh", **k)), daemon=True)
    t.start()
    t.join(CHO * 3)
    assert not t.is_alive(), "lượt đồng bộ bị treo"
    return ra


def _so_da_tai(cs) -> list:
    with open(cs.archive, encoding="utf-8") as f:
        return [d.split()[-1] for d in f.read().splitlines()]


def test_nen_chong_thoi_gian_voi_tai_video_ke_tiep(tmp_path):
    cs, gia = _kenh(tmp_path)
    thay: list = []

    def khi_nen(vid):
        if vid == "v1":
            sau = gia.bat_dau_tai.setdefault("v2", threading.Event())
            thay.append(sau.wait(CHO))
        return ""

    gia.khi_nen = khi_nen
    kq = _chay(cs)

    assert thay == [True], "video 2 phải bắt đầu tải trong lúc video 1 đang nén"
    assert kq["moi"] == 3 and not kq["loi"]


def test_tai_va_nen_moi_viec_mot_luong_va_ghi_so_dung_thu_tu(tmp_path):
    cs, gia = _kenh(tmp_path, 6)
    gia.khi_tai = lambda vid: time.sleep(0.03)
    gia.khi_nen = lambda vid: time.sleep({"v1": 0.2, "v2": 0.01}.get(vid, 0.05)) or ""

    kq = _chay(cs)

    assert (gia.tai_max, gia.nen_max) == (1, 1)
    assert gia.lan_tai == gia.lan_nen == [f"v{i}" for i in range(1, 7)]
    assert _so_da_tai(cs) == [f"v{i}" for i in range(1, 7)]
    assert kq["moi"] == 6
    assert sorted(cs.load_meta()) == sorted(os.listdir(cs.dest)[i] for i in range(len(os.listdir(cs.dest)))
                                            if os.listdir(cs.dest)[i].endswith(".opus"))


def test_khong_tich_qua_mot_video_cho_nen(tmp_path):
    """Giới hạn đĩa tạm: nén chậm thì không tải dồn."""
    cs, gia = _kenh(tmp_path, 5)
    tha = threading.Event()
    gia.khi_nen = lambda vid: tha.wait(CHO) and ""

    t = threading.Thread(target=lambda: cs.sync("kenh"), daemon=True)
    t.start()
    gia.bat_dau_tai.setdefault("v2", threading.Event()).wait(CHO)
    time.sleep(0.5)
    da_tai = list(gia.lan_tai)
    tha.set()
    t.join(CHO * 2)

    assert da_tai == ["v1", "v2"]
    assert not t.is_alive()


def test_nen_loi_khong_chan_video_sau(tmp_path):
    cs, gia = _kenh(tmp_path)

    def khi_nen(vid):
        if vid == "v1":
            raise RuntimeError("Nén audio thất bại: giả")
        return ""

    gia.khi_nen = khi_nen
    kq = _chay(cs)

    assert kq["so_loi"] == 1 and kq["moi"] == 2
    assert _so_da_tai(cs) == ["v2", "v3"]


def test_tai_loi_khong_chan_video_sau_va_giu_thu_tu(tmp_path):
    cs, gia = _kenh(tmp_path)

    def khi_tai(vid):
        if vid == "v2":
            raise RuntimeError("synthetic: mạng đứt")

    gia.khi_tai = khi_tai
    gia.khi_nen = lambda vid: time.sleep(0.1) or ""
    kq = _chay(cs)

    assert kq["so_loi"] == 1 and kq["moi"] == 2
    assert _so_da_tai(cs) == ["v1", "v3"]


def test_tai_loi_khong_lam_du_mot_cong_nen(tmp_path):
    """Video tải hỏng chưa giữ cổng nén: nhả cổng cho nó sẽ cho hai video nén cùng lúc ở phần còn lại của lượt."""
    cs, gia = _kenh(tmp_path, 5)

    def khi_tai(vid):
        if vid == "v2":
            raise RuntimeError("synthetic: mạng đứt")

    gia.khi_tai = khi_tai
    gia.khi_nen = lambda vid: time.sleep(0.2) or ""
    _chay(cs)

    assert gia.nen_max == 1


def test_nhat_ky_ghi_loi_dung_video_tai_hong(tmp_path):
    """Video hỏng phải được chốt trước khi video kế tiếp chiếm chỗ trong sổ tiến độ."""
    cs, gia = _kenh(tmp_path)

    def khi_tai(vid):
        if vid == "v2":
            raise RuntimeError("synthetic: mạng đứt")

    gia.khi_tai = khi_tai
    gia.khi_nen = lambda vid: time.sleep(0.1) or ""
    _chay(cs)

    cau = [k.noi_dung for k in cs.theo_doi.anh().su_kien if "Không tải được" in k.noi_dung]
    assert len(cau) == 1 and "Video 2" in cau[0], cau


def test_dung_trong_luc_nen_khong_treo_va_don_tam(tmp_path):
    cs, gia = _kenh(tmp_path, 4)
    huy = threading.Event()

    def khi_nen(vid):
        if vid == "v1":
            gia.bat_dau_tai.setdefault("v2", threading.Event()).wait(CHO)
            huy.set()
            raise channel.DaHuyDongBo("giả: Dừng trong lúc nén")
        return ""

    gia.khi_nen = khi_nen
    kq = _chay(cs, cancel_check=huy.is_set)

    assert kq["da_huy"] is True
    assert "v3" not in gia.lan_tai
    assert not os.path.exists(cs.tmp_dir)
    assert not os.path.exists(cs.archive) or "v1" not in _so_da_tai(cs)


def test_cau_dao_mo_van_hoan_tat_video_da_tai_va_khong_tai_tiep(tmp_path, monkeypatch):
    cs, gia = _kenh(tmp_path, 4)
    mo = {"co": False}
    monkeypatch.setattr(PhienYouTube, "mo", property(lambda s: mo["co"]))

    def khi_tai(vid):
        if vid == "v2":
            mo["co"] = True

    gia.khi_tai = khi_tai
    kq = _chay(cs)

    assert gia.lan_tai == ["v1", "v2"]
    assert _so_da_tai(cs) == ["v1", "v2"]
    assert kq["moi"] == 2


def test_tai_lai_vi_nguon_ngan_khong_chong_len_luot_tai_khac(tmp_path, monkeypatch):
    """Lần tải thứ hai xảy ra ở bước nén: vẫn phải chờ, không thành hai luồng tải cùng cookie."""
    cs, gia = _kenh(tmp_path)
    gia.khi_tai = lambda vid: time.sleep(0.05)
    monkeypatch.setattr(channel, "do_dai_luong_tieng", lambda p: 10.0)
    lan = {"v1": 0}

    def khi_nen(vid):
        if vid == "v1":
            lan["v1"] += 1
            if lan["v1"] == 1:
                return "ngắn hơn nguồn"
        return ""

    gia.khi_nen = khi_nen
    _chay(cs)

    assert gia.lan_tai.count("v1") == 2
    assert gia.tai_max == 1
    assert all(hook.__name__ == "hook_huy" for hook in gia.hook_lan_hai), "lần tải lại không ghi vào thẻ video khác"


def test_ctrl_c_luc_cho_tai_khong_lam_video_cho_nen_treo(tmp_path):
    """Video 1 giữ cổng nén chờ vòng chính nhả; vòng chính chết thì video 2 chờ cổng mãi nếu không ai nhả hộ."""
    cs, gia = _kenh(tmp_path, 4)
    goc = cs._chay_viec

    class Ngat(threading.Event):
        def wait(self, timeout=None):
            time.sleep(0.2)
            raise KeyboardInterrupt("giả: Ctrl+C ở CLI")

    def boc(viec):
        if viec.v.id == "v2":
            viec.tai_xong = Ngat()
        return goc(viec)

    cs._chay_viec = boc
    ket: dict = {}

    def chay():
        try:
            cs.sync("kenh")
        except KeyboardInterrupt as e:
            ket["loi"] = str(e)

    t = threading.Thread(target=chay, daemon=True)
    t.start()
    t.join(CHO * 2)

    assert not t.is_alive(), "lượt bị treo"
    assert "giả" in ket["loi"]
    assert not os.path.exists(cs.tmp_dir)


def test_ctrl_c_dung_ngay_luot_tai_dang_chay(tmp_path):
    """Không có nút Dừng ở CLI: Ctrl+C phải dừng video đang tải, không chờ tải hết hàng GB."""
    cs, gia = _kenh(tmp_path, 4)
    goc = cs._chay_viec
    thay_huy: list = []

    class Ngat(threading.Event):
        def wait(self, timeout=None):
            time.sleep(0.2)
            raise KeyboardInterrupt("giả: Ctrl+C ở CLI")

    def boc(viec):
        if viec.v.id == "v1":
            viec.tai_xong = Ngat()
        return goc(viec)

    def khi_tai(vid):
        het = time.monotonic() + CHO
        while time.monotonic() < het:
            if cs._huy_luot_sync.is_set():
                thay_huy.append(vid)
                raise channel.DaHuyDongBo("giả: hook huỷ")
            time.sleep(0.02)

    cs._chay_viec = boc
    gia.khi_tai = khi_tai
    t0 = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        cs.sync("kenh")

    assert thay_huy == ["v1"]
    assert time.monotonic() - t0 < CHO / 2


def test_video_sau_khong_duoc_vuot_len_giu_cong_nen(tmp_path):
    """Video 1 chững ngay sau khi báo tải xong: video 2 không được lấy cổng trước, vì sổ chỉ ghi được theo thứ tự."""
    cs, gia = _kenh(tmp_path, 2)
    goc = cs._chay_viec
    v2_dang_nen = threading.Event()
    huy = threading.Event()

    class Chung(threading.Event):
        def set(self):
            super().set()
            v2_dang_nen.wait(1.0)

    def boc(viec):
        if viec.v.id == "v1":
            viec.tai_xong = Chung()
        return goc(viec)

    def khi_nen(vid):
        if vid == "v2":
            v2_dang_nen.set()
        return ""

    cs._chay_viec = boc
    gia.khi_nen = khi_nen
    ra: dict = {}
    t = threading.Thread(target=lambda: ra.update(cs.sync("kenh", cancel_check=huy.is_set)), daemon=True)
    t.start()
    t.join(CHO)
    treo = t.is_alive()
    huy.set()
    t.join(CHO)

    assert not treo, "video 2 giữ cổng chờ ghi sổ, video 1 chờ cổng: treo"
    assert ra["moi"] == 2
    assert _so_da_tai(cs) == ["v1", "v2"]


def test_ctrl_c_luc_cho_video_cuoi_van_huy_viec_dang_nen(tmp_path, monkeypatch):
    """Video cuối đã rời hàng chờ, chỉ còn đợi kết quả: Ctrl+C vẫn phải huỷ, không chờ nén hết."""
    cs, gia = _kenh(tmp_path, 1)
    thay_huy: list = []

    class Tho(channel.ThreadPoolExecutor):
        def submit(self, *a, **k):
            f = super().submit(*a, **k)

            def result(timeout=None):
                time.sleep(0.2)
                raise KeyboardInterrupt("giả: Ctrl+C ở CLI")

            f.result = result
            return f

    def khi_nen(vid):
        het = time.monotonic() + CHO
        while time.monotonic() < het:
            if cs._huy_luot_sync.is_set():
                thay_huy.append(vid)
                return ""
            time.sleep(0.02)
        return ""

    monkeypatch.setattr(channel, "ThreadPoolExecutor", Tho)
    gia.khi_nen = khi_nen
    t0 = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        cs.sync("kenh")

    assert thay_huy == ["v1"]
    assert time.monotonic() - t0 < CHO / 2


MA_THAT = "abcdefghij1"  # RE_ID_TEN_FILE chỉ nhận mã từ 6 ký tự


def _kho_mot_file_that(tmp_path):
    """Một video 3 giây đi qua FFmpeg + ffprobe thật, để file mang dấu xác nhận đúng như kho thật."""
    ds = [VideoInfo(MA_THAT, "v1", "20260101", 3.0, f"https://youtu.be/{MA_THAT}")]
    so_lan_tai: list = []

    def tao():
        cs = ChannelSync(str(tmp_path / "kho"))
        cs.list_channel = lambda *a, **k: list(ds)

        def tai_gia(url, opts):
            so_lan_tai.append(url)
            _ghi_wav(opts["outtmpl"].replace("%(id)s.%(ext)s", f"{MA_THAT}.wav"), _giai_dieu(3.0, seed=7), 22050)
            return {"id": MA_THAT, "title": "v1", "duration": 3.0, "upload_date": "20260101"}

        cs._tai_thu_tung_client = tai_gia
        return cs

    cs = tao()
    assert _chay(cs)["moi"] == 1
    so_lan_tai.clear()
    return cs, tao, so_lan_tai


def test_dut_giua_metadata_va_so_thi_luot_sau_bu_lai_so(tmp_path):
    cs, tao, so_lan_tai = _kho_mot_file_that(tmp_path)
    with open(cs.archive, "w", encoding="utf-8"):
        pass

    kq = _chay(tao())

    assert kq["trang_thai"] == channel.DONG_BO_DAY_DU
    assert so_lan_tai == []
    assert _so_da_tai(cs) == [MA_THAT]


def test_doi_soat_hong_khong_duoc_bao_day_du(tmp_path):
    cs, tao, so_lan_tai = _kho_mot_file_that(tmp_path)
    with open(cs.meta_file, "w", encoding="utf-8") as f:
        f.write("{}")
    moi = tao()

    def hong(_):
        raise OSError("giả: đĩa đầy")

    moi._doi_soat = hong
    bao: list = []
    kq = _chay(moi, progress=lambda p, m: bao.append(m))

    assert kq["trang_thai"] == channel.DONG_BO_MOT_PHAN
    assert so_lan_tai == [], "file âm thanh vẫn tốt, chỉ cần đối soát lại ở lượt sau"
    assert any("metadata" in d for d in kq["loi"])
    assert "1 file chưa ghi được metadata" in bao[-1]


def test_chay_lai_tren_cung_doi_tuong_van_nen_mot_luong(tmp_path):
    cs, gia = _kenh(tmp_path)
    gia.khi_tai = lambda vid: (_ for _ in ()).throw(RuntimeError("giả")) if vid == "v3" else None
    _chay(cs)
    gia.khi_tai = lambda vid: time.sleep(0.02)
    gia.khi_nen = lambda vid: time.sleep(0.05) or ""
    cs.list_channel = lambda *a, **k: [VideoInfo(f"w{i}", f"W{i}", "20260101", 100.0, f"https://youtu.be/w{i}")
                                       for i in range(1, 5)]
    gia.nen_max = 0

    _chay(cs)

    assert gia.nen_max == 1


@pytest.mark.slow
def test_ffmpeg_that_moi_file_mang_dau_xac_nhan_cua_chinh_no(tmp_path):
    """FFmpeg + ffprobe thật: số đo của bước kiểm không được lẫn giữa hai video chồng thời gian."""
    dai = {"v1": 6.0, "v2": 3.0, "v3": 9.0}
    ds = [VideoInfo(k, k, "20260101", s, f"https://youtu.be/{k}") for k, s in dai.items()]
    cs = ChannelSync(str(tmp_path / "kho"))
    cs.list_channel = lambda *a, **k: list(ds)

    def tai_gia(url, opts):
        vid = url.rsplit("/", 1)[-1]
        _ghi_wav(opts["outtmpl"].replace("%(id)s.%(ext)s", f"{vid}.wav"), _giai_dieu(dai[vid], seed=7), 22050)
        return {"id": vid, "title": vid, "duration": dai[vid], "upload_date": "20260101"}

    cs._tai_thu_tung_client = tai_gia
    dung_so_vua_kiem: list = []
    goc = cs._do_dai_file_vua_dat

    def theo_doi(f):
        nho = cs._do_dai_vua_kiem
        dung_so_vua_kiem.append(bool(nho) and nho[0] == os.path.normcase(os.path.abspath(f)))
        return goc(f)

    cs._do_dai_file_vua_dat = theo_doi
    kq = _chay(cs)

    assert dung_so_vua_kiem == [True] * 3, "số đo phải đúng của file đó, không đo lại lần hai"
    assert kq["moi"] == 3 and not kq["loi"], kq["loi"]
    meta = {m["id"]: m for m in cs.load_meta().values()}
    for vid, giay in dai.items():
        assert meta[vid]["xac_nhan_tep"]["do_dai"] == pytest.approx(giay, abs=0.1), vid


def test_so_tien_do_tach_lan_tai_va_lan_nen():
    so = SoDongBo()
    so.ke_hoach(0, 2, 0, 2)
    so.video_bat_dau(1, 2, "aaa", "Video A")
    the = so.tach_video()
    so.video_bat_dau(2, 2, "bbb", "Video B")
    so.vao_lan_nen(the)
    so.giai_doan(GD_NEN, ffmpeg_tong_s=100.0)
    so.tien_do_ffmpeg({"out_time_us": 50_000_000, "progress": "end"})
    so.giai_doan(GD_TAI)

    a = so.anh()
    assert a.video.video_id == "bbb" and a.video.giai_doan == GD_TAI
    assert a.nen.video_id == "aaa" and a.nen.giai_doan == GD_NEN and a.nen.ffmpeg_da_s == 50.0
    assert any("Video A" in chu for _, chu, _ in dong_video(a))
    assert any("Nén" in chu for loai, chu, _ in dong_video(a) if loai == "nen")

    so.video_xong("moi", media_s=100.0)

    a = so.anh()
    assert a.moi == 1 and a.nen is None and a.video.video_id == "bbb"


def test_toc_do_luc_dang_chay_khong_cong_doi_phan_chong_thoi_gian():
    gio = {"t": 1000.0}
    so = SoDongBo(dong_ho=lambda: gio["t"], dong_ho_don_dieu=lambda: gio["t"])
    so.ke_hoach(0, 3, 0, 3)
    so.video_bat_dau(1, 3, "a", "A")
    gio["t"] = 1060
    the_a = so.tach_video()
    so.video_bat_dau(2, 3, "b", "B")
    so.vao_lan_nen(the_a)
    gio["t"] = 1120
    so.video_xong("moi", media_s=100.0)
    gio["t"] = 1130

    assert so.anh().thong_ke["LUOT_VIDEO_S"].tong == pytest.approx(130)


def test_toc_do_khong_bi_giam_vi_hai_video_chong_thoi_gian():
    gio = {"t": 1000.0}
    so = SoDongBo(dong_ho=lambda: gio["t"], dong_ho_don_dieu=lambda: gio["t"])
    so.ke_hoach(0, 3, 0, 3)
    so.video_bat_dau(1, 3, "a", "A")
    gio["t"] = 1060
    the_a = so.tach_video()
    so.video_bat_dau(2, 3, "b", "B")
    so.vao_lan_nen(the_a)
    gio["t"] = 1120
    the_b = so.tach_video()
    so.video_xong("moi", media_s=100.0)      # A: 120 s
    so.video_bat_dau(3, 3, "c", "C")
    so.vao_lan_nen(the_b)
    gio["t"] = 1180
    the_c = so.tach_video()
    so.video_xong("moi", media_s=100.0)      # B: 120 s, nhưng chỉ sau A 60 s
    so.vao_lan_nen(the_c)
    gio["t"] = 1240
    so.video_xong("moi", media_s=100.0)

    assert so.anh().video_moi_gio == pytest.approx(3 / (240 / 3600))
