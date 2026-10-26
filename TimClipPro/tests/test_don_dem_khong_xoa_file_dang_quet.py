# -*- coding: utf-8 -*-
"""Audit C-9 (tái hiện, dữ liệu TỔNG HỢP): dọn kho đệm không được xoá audio mà một lượt quét
KHÁC đang dùng.

Bối cảnh (D-26): giao diện 8502, CLI và Watch theo lịch dùng CHUNG một thư mục data. Lượt quét
giao diện dùng lại audio đã tải từ trước (``download_audio`` → «Đã có sẵn audio») và cắt từng
khúc bằng một lệnh FFmpeg riêng — giữa hai lệnh (và suốt lúc so khớp một đoạn quét tăng dần)
không ai mở file. Lượt quét chỉ giữ lease cổng bảo trì (không giữ ``tool.lock``), nên một lượt
Watch kết thúc (``finally`` → ``don_kho_dem``) hay ``cli dondep`` chạy đúng lúc đó vẫn được vào
cổng và chọn file theo ``st_mtime`` = lúc TẢI, không phải lúc dùng gần nhất.

Hành vi ĐÚNG (người dùng mong đợi): dọn đệm không bao giờ xoá file đang được một lượt quét dùng;
lượt quét đang chạy hoàn tất trọn video, không thành «lỗi — hãy quét lại».

Không mạng, không FFmpeg thật: FFmpeg/ffprobe được giả lập, nhưng giả lập ĐÚNG như thật ở điểm
mấu chốt — file đầu vào không còn thì ffprobe không đọc được thời lượng, ffmpeg thoát mã lỗi.
"""

import os
import time
from types import SimpleNamespace

import pytest

import cli
import engine as engine_module
from engine import Config, Engine
from watch import WatchList, chay_giam_sat

VID = "AbCdEfGhIjK"
URL = f"https://www.youtube.com/watch?v={VID}"
NGAY = 24 * 3600
MB = 1024 * 1024
DAI_VIDEO_S = 12 * 3600.0     # > quet_tang_dan_tu_gio (10 giờ) → quét tăng dần 4 đoạn × 3 giờ


def _engine_cung_data(data_dir: str, out_dir: str) -> Engine:
    """Một tiến trình KHÁC (Watch theo lịch / CLI) trên CÙNG thư mục data."""
    goc = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return Engine(root=goc, data_dir=data_dir, out_dir=out_dir)


def _ffmpeg_gia(cmd, **kw):
    """ffmpeg cắt khúc: đầu vào phải còn trên đĩa, nếu không thoát mã lỗi như thật."""
    dau_vao = cmd[cmd.index("-i") + 1]
    if not os.path.exists(dau_vao):
        return SimpleNamespace(returncode=1, cancelled=False, timed_out=False, stdout="",
                               stderr=f"{dau_vao}: No such file or directory", ly_do="")
    with open(cmd[-1], "wb") as fh:
        fh.write(b"\0" * 4096)
    return SimpleNamespace(returncode=0, cancelled=False, timed_out=False, stdout="",
                           stderr="", ly_do="")


@pytest.mark.parametrize("ly_do_chon", ["qua_tuoi", "qua_ngan_sach"])
# "doi_chung" = đối chứng: không ai dọn đệm → lượt quét phải XANH (chứng minh giả lập đúng,
# thất bại ở hai ca kia là do dọn đệm đồng thời chứ không do thiết lập).
@pytest.mark.parametrize("ben_don", ["doi_chung", "watch_ket_thuc", "cli_dondep"])
def test_don_dem_dong_thoi_khong_xoa_audio_luot_quet_dang_cat(
        engine, tmp_path, monkeypatch, ben_don, ly_do_chon):
    e = engine
    e.config = Config(quet_tang_dan=True, quet_tang_dan_tu_gio=10.0,
                      quet_tang_dan_buoc_gio=3.0, quet_da_toc_do=False)
    os.makedirs(e.dl_dir, exist_ok=True)
    bay_gio = time.time()

    # Audio đệm của video 12 giờ, tải từ trước (keep_downloads=True mặc định).
    dem = os.path.join(e.dl_dir, f"{VID}.webm")
    with open(dem, "wb") as fh:
        fh.write(b"\1" * (3 * MB))
    if ly_do_chon == "qua_tuoi":
        # Tải 9 ngày trước, giờ người dùng quét lại (vd. sau khi dựng lại kho).
        os.utime(dem, (bay_gio - 9 * NGAY, bay_gio - 9 * NGAY))
    else:
        # Tải 2 ngày trước (CHƯA quá 7 ngày) nhưng kho đệm vượt ngân sách: còn một file đệm
        # KHÔNG ai dùng, tải 1 ngày trước. Đúng: bỏ file nhàn rỗi, giữ file đang quét.
        os.utime(dem, (bay_gio - 2 * NGAY, bay_gio - 2 * NGAY))
        nhan_roi = os.path.join(e.dl_dir, "ZzZzZzZzZzZ.webm")
        with open(nhan_roi, "wb") as fh:
            fh.write(b"\2" * (3 * MB))
        os.utime(nhan_roi, (bay_gio - 1 * NGAY, bay_gio - 1 * NGAY))

    # --- giả lập công cụ media (không FFmpeg thật) ---
    monkeypatch.setattr(engine_module, "chay_lenh_media", _ffmpeg_gia)
    monkeypatch.setattr(engine_module, "do_dai_wav", lambda p: float(e.config.chunk_s))
    # ffprobe: file không còn thì không đọc được thời lượng (trả None) — đúng như thật.
    monkeypatch.setattr(e, "duration_of", lambda p: DAI_VIDEO_S if os.path.exists(p) else None)
    monkeypatch.setattr(e, "do_dai_am_thanh", lambda p: None)
    monkeypatch.setattr(e, "_overlap_thuc_te", lambda *a, **k: 60)
    monkeypatch.setattr(e, "require", lambda **k: None)

    # --- tiến trình kia: Watch theo lịch kết thúc / người dùng gõ `cli dondep` ---
    khac = _engine_cung_data(e.data_dir, str(tmp_path / "ketqua_khac"))
    if ly_do_chon == "qua_ngan_sach":
        khac.config.dem_max_gb = 4 * MB / 1024 ** 3   # ngân sách 4 MB < 6 MB đang có
    da_don = []

    def don_dem_dong_thoi():
        if ben_don == "doi_chung":
            pass
        elif ben_don == "watch_ket_thuc":
            # Lượt Watch rỗng: finally của nó LUÔN gọi don_kho_dem (watch.py:431).
            chay_giam_sat(khac, WatchList(muc=[]), lister=lambda url, limit: [], cho_gui_s=0)
        else:
            monkeypatch.setattr("sys.argv", ["cli.py", "dondep"])
            monkeypatch.setattr(cli, "Engine", lambda *a, **k: khac)
            cli.main()
        da_don.append(True)

    # So khớp đoạn đầu (3 giờ) mất vài phút ngoài đời: lúc đó KHÔNG ai mở file đệm.
    def quet_tho_gia(chunks, duration, *a, **k):
        if not da_don:
            don_dem_dong_thoi()
        return []

    monkeypatch.setattr(e, "_quet_tho", quet_tho_gia)

    # --- lượt quét giao diện: giữ lease cổng bảo trì như lô quét app (scan_jobs) ---
    with e.cong_bao_tri.viec("lô quét (youtube)"):
        f = e.download_audio(URL, VID)                    # «Đã có sẵn audio» — dùng lại đệm
        assert os.path.normcase(f) == os.path.normcase(dem)
        kq = e.scan_media(f, label="Video 12 giờ (tổng hợp)", ref=URL, source_type="youtube",
                          luu_lich_su=False, pct_start=0.40)

    assert da_don, "thiết lập sai: dọn đệm đồng thời chưa chạy"
    assert os.path.exists(dem), (
        f"[{ben_don}/{ly_do_chon}] dọn kho đệm đã XOÁ audio mà lượt quét đang cắt "
        f"(status={kq.status!r}, note={kq.note!r})")
    assert kq.status != "error", f"lượt quét hỏng giữa chừng: {kq.note!r}"
    assert not kq.vung_loi, f"vùng chưa kiểm do mất file đệm: {kq.vung_loi!r}"


# --- Mức đơn vị: dấu «đang dùng» của don_dep (khoá HĐH, tự nhả khi tiến trình chết) ---

def _tao_dem(thu_muc, ten, tuoi_ngay, kich_thuoc=MB):
    duong = os.path.join(thu_muc, ten)
    with open(duong, "wb") as fh:
        fh.write(b"\1" * kich_thuoc)
    moc = time.time() - tuoi_ngay * NGAY
    os.utime(duong, (moc, moc))
    return duong


def test_dau_dang_dung_giu_file_qua_tuoi_nha_dau_thi_xoa(tmp_path):
    import don_dep
    dl = str(tmp_path / "data" / "downloads")
    os.makedirs(dl)
    dem = _tao_dem(dl, f"{VID}.webm", 9)
    dau = don_dep.dat_dau_dang_dung(dl, f"{VID}.webm")
    try:
        kq = don_dep.don_kho_dem(dl, max_gb=20, max_ngay=7)
        assert os.path.exists(dem)
        assert kq["xoa_file"] == 0 and kq["bo_qua_dang_dung"] == 1 and not kq["loi"]
    finally:
        don_dep.nha_dau_dang_dung(dau)
    assert not os.listdir(tmp_path / "data" / don_dep.THU_MUC_DANG_DUNG)
    kq = don_dep.don_kho_dem(dl, max_gb=20, max_ngay=7)
    assert not os.path.exists(dem) and kq["xoa_file"] == 1


def test_dau_mo_coi_cua_tien_trinh_chet_khong_giu_file_mai(tmp_path):
    """Dấu còn trên đĩa nhưng KHÔNG ai giữ khoá (tiến trình đã chết): file vẫn dọn được, dấu bị bỏ.
    Xem trước (thuc_hien=False) không đụng vào dấu."""
    import don_dep
    dl = str(tmp_path / "data" / "downloads")
    os.makedirs(dl)
    dem = _tao_dem(dl, f"{VID}.webm", 9)
    thu_muc_dau = tmp_path / "data" / don_dep.THU_MUC_DANG_DUNG
    os.makedirs(thu_muc_dau)
    mo_coi = thu_muc_dau / f"{VID}.webm~99999_deadbeef0000.lock"
    mo_coi.write_text("\nPID: 99999\n", encoding="utf-8")
    xem = don_dep.don_kho_dem(dl, max_gb=20, max_ngay=7, thuc_hien=False)
    assert xem["xoa_file"] == 1 and mo_coi.exists() and os.path.exists(dem)
    kq = don_dep.don_kho_dem(dl, max_gb=20, max_ngay=7)
    assert kq["xoa_file"] == 1 and kq["bo_qua_dang_dung"] == 0
    assert not os.path.exists(dem) and not mo_coi.exists()


def test_vuot_ngan_sach_bo_file_nhan_roi_giu_file_dang_dung(tmp_path):
    """File đang dùng là file CŨ nhất nhưng vẫn tính vào ngân sách: bỏ file nhàn rỗi thay nó."""
    import don_dep
    dl = str(tmp_path / "data" / "downloads")
    os.makedirs(dl)
    dang_quet = _tao_dem(dl, f"{VID}.webm", 3, 3 * MB)
    nhan_roi = _tao_dem(dl, "ZzZzZzZzZzZ.webm", 1, 3 * MB)
    dau = don_dep.dat_dau_dang_dung(dl, f"{VID}.webm")
    try:
        kq = don_dep.don_kho_dem(dl, max_gb=4 * MB / 1024 ** 3, max_ngay=7)
    finally:
        don_dep.nha_dau_dang_dung(dau)
    assert os.path.exists(dang_quet) and not os.path.exists(nhan_roi)
    assert kq["xoa_file"] == 1 and kq["bo_qua_dang_dung"] == 1


def test_dang_co_luot_tai_cung_muc_thi_de_lan_don_sau(tmp_path):
    """Khoá tải của mục đang bị giữ (lượt khác đang tải / nhận file này): không xoá lúc đó."""
    import don_dep
    from khoa import KhoaTienTrinh
    dl = str(tmp_path / "data" / "downloads")
    os.makedirs(dl)
    dem = _tao_dem(dl, f"{VID}__p10800.webm", 9)
    with KhoaTienTrinh(don_dep.duong_khoa_tai(dl, f"{VID}__p10800"), "lượt tải khác"):
        kq = don_dep.don_kho_dem(dl, max_gb=20, max_ngay=7)
    assert os.path.exists(dem) and kq["xoa_file"] == 0 and kq["bo_qua_dang_dung"] == 1
    assert don_dep.don_kho_dem(dl, max_gb=20, max_ngay=7)["xoa_file"] == 1


def test_luot_quet_xong_nha_dau_va_dung_lai_lam_moi_lan_dung_cuoi(engine, tmp_path, monkeypatch):
    """Lượt quét xong (kể cả lỗi) không để lại dấu; dùng lại bản đệm làm mới mtime = lần dùng cuối."""
    import don_dep
    e = engine
    os.makedirs(e.dl_dir, exist_ok=True)
    dem = _tao_dem(e.dl_dir, f"{VID}.webm", 9)
    f = e.download_audio(URL, VID)
    assert time.time() - os.path.getmtime(f) < NGAY
    monkeypatch.setattr(e, "require", lambda **k: None)
    monkeypatch.setattr(e, "duration_of", lambda p: None)     # lượt quét hỏng ngay đoạn đầu
    kq = e.scan_media(dem, source_type="youtube", luu_lich_su=False)
    assert kq.status == "error"
    thu_muc_dau = os.path.join(e.data_dir, don_dep.THU_MUC_DANG_DUNG)
    assert not os.path.isdir(thu_muc_dau) or not os.listdir(thu_muc_dau)


def test_suot_luot_quet_file_dem_mang_dau_dang_dung_song(engine, monkeypatch):
    """Giữa hai đoạn (lúc so khớp, không ai mở file) file đệm vẫn mang dấu sống — kể cả khi tuổi
    file đã quá hạn (không dựa vào việc làm mới mtime)."""
    import don_dep
    e = engine
    e.config = Config(quet_tang_dan=True, quet_tang_dan_tu_gio=10.0,
                      quet_tang_dan_buoc_gio=3.0, quet_da_toc_do=False)
    os.makedirs(e.dl_dir, exist_ok=True)
    dem = _tao_dem(e.dl_dir, f"{VID}.webm", 9, 3 * MB)
    monkeypatch.setattr(engine_module, "chay_lenh_media", _ffmpeg_gia)
    monkeypatch.setattr(engine_module, "do_dai_wav", lambda p: float(e.config.chunk_s))
    monkeypatch.setattr(e, "duration_of", lambda p: DAI_VIDEO_S if os.path.exists(p) else None)
    monkeypatch.setattr(e, "do_dai_am_thanh", lambda p: None)
    monkeypatch.setattr(e, "_overlap_thuc_te", lambda *a, **k: 60)
    monkeypatch.setattr(e, "require", lambda **k: None)
    thay = []

    def quet_tho_gia(chunks, duration, *a, **k):
        cu = time.time() - 9 * NGAY
        os.utime(dem, (cu, cu))
        thay.append(don_dep._dang_duoc_dung(e.dl_dir, f"{VID}.webm", bo_dau_mo_coi=False))
        thay.append(don_dep.don_kho_dem(e.dl_dir, max_gb=20, max_ngay=7)["bo_qua_dang_dung"])
        return []

    monkeypatch.setattr(e, "_quet_tho", quet_tho_gia)
    kq = e.scan_media(dem, source_type="youtube", luu_lich_su=False)
    assert thay and thay[0] is True and thay[1] == 1, thay
    assert os.path.exists(dem) and kq.status != "error", kq.note
    assert not don_dep._dang_duoc_dung(e.dl_dir, f"{VID}.webm", bo_dau_mo_coi=False)


def test_file_dem_vua_chon_tu_bo_dem_khong_bi_don_cuoi_luot_watch(engine):
    """Audit D-24 (cùng gốc C-9): lượt quét giao diện vừa nhận bản đệm 8 ngày tuổi («Đã có sẵn
    audio») thì lời gọi dọn y như cuối lượt Watch (cấu hình MẶC ĐỊNH) không được xoá nó trước khi
    lượt quét kịp mở file."""
    import don_dep
    e = engine
    os.makedirs(e.dl_dir, exist_ok=True)
    dem = _tao_dem(e.dl_dir, f"{VID}.webm", 8)
    duong = e.download_audio(URL, VID)
    assert os.path.normcase(duong) == os.path.normcase(dem)
    kq = don_dep.don_kho_dem(e.dl_dir, max_gb=e.config.dem_max_gb, max_ngay=e.config.dem_max_ngay)
    assert os.path.exists(duong) and kq["xoa_file"] == 0, kq


@pytest.mark.parametrize("ly_do_chon", ["qua_tuoi", "qua_ngan_sach"])
def test_dung_lai_ban_dem_giua_luc_don_dem_liet_ke_va_luc_xoa_thi_khong_xoa(
        engine, monkeypatch, ly_do_chon):
    """Audit WR-4 (cùng gốc C-9): dọn đệm (cuối lượt Watch) liệt kê kho đệm và chọn file theo mtime
    cũ, NGAY SAU đó lượt quét giao diện nhận lại bản đệm («Đã có sẵn audio» — làm mới mtime dưới khoá
    tải rồi nhả khoá) và còn đang đo độ dài thật trước khi đặt dấu «đang dùng». Dọn đệm lấy được khoá
    tải, không thấy dấu → trước đây xoá theo lựa chọn CŨ. Đúng: lần dùng mới hơn lúc liệt kê thì
    không xoá (file vừa được dùng lại, lượt quét sắp mở nó)."""
    import don_dep
    e = engine
    os.makedirs(e.dl_dir, exist_ok=True)
    if ly_do_chon == "qua_tuoi":
        dem = _tao_dem(e.dl_dir, f"{VID}.webm", 8)
        max_gb = 20
    else:
        # File cũ nhất (2 ngày) trong kho vượt ngân sách; file kia nhàn rỗi, mới hơn.
        dem = _tao_dem(e.dl_dir, f"{VID}.webm", 2, 3 * MB)
        _tao_dem(e.dl_dir, "ZzZzZzZzZzZ.webm", 1, 3 * MB)
        max_gb = 4 * MB / 1024 ** 3
    goc_chon = don_dep.chon_can_xoa
    nhan = []

    def chon_roi_luot_quet_nhan_file(*a, **k):
        chon = goc_chon(*a, **k)
        assert any(os.path.normcase(m.path) == os.path.normcase(dem) for m in chon), \
            "thiết lập sai: dọn đệm chưa chọn bản đệm"
        nhan.append(e.download_audio(URL, VID))          # khoá tải lấy rồi NHẢ ở đây
        return chon

    monkeypatch.setattr(don_dep, "chon_can_xoa", chon_roi_luot_quet_nhan_file)
    kq = don_dep.don_kho_dem(e.dl_dir, max_gb=max_gb, max_ngay=7)
    assert nhan and os.path.normcase(nhan[0]) == os.path.normcase(dem)
    assert os.path.exists(dem), (
        f"[{ly_do_chon}] dọn đệm xoá bản đệm vừa được lượt quét nhận lại: {kq!r}")
    assert kq["bo_qua_dang_dung"] >= 1 and not kq["loi"], kq
