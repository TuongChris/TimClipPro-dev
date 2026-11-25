# -*- coding: utf-8 -*-
"""Luật giữ đệm audio D-66: dọn đệm KHÔNG xoá trắng audio của video vi phạm — cắt giữ đoạn quanh mốc rồi mới bỏ bản
đầy đủ; video sạch bỏ; file không có trong lịch sử giữ. Chạy FFmpeg thật trên audio tổng hợp (tiếng «chirp»: tần số
tăng theo thời gian, nên đọc tần số ở đầu đoạn trích biết đoạn đó bắt đầu ở giây nào của file gốc)."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import threading
import time

import numpy as np
import pytest

import don_dep
import trich_doan_dem as td
from khoa import KhoaTienTrinh
from lich_su_dem_gia import ghi_lich_su

NGAY = 24 * 3600
DAI_S = 600
can_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg trên PATH")


# ------------------------------------------------------------------ hàm thuần

def test_gop_doan_noi_cat_va_gop():
    assert td.gop_doan([(100, 130), (300, 320)], 60) == [(40, 190), (240, 380)]
    assert td.gop_doan([(100, 130), (200, 220)], 60) == [(40, 280)]           # chồng nhau → một đoạn
    assert td.gop_doan([(10, 20), (590, 700)], 60, tran=600) == [(0, 80), (530, 600)]
    assert td.gop_doan([(700, 720)], 60, tran=600) == []                      # nằm ngoài file
    assert td.gop_doan([(130, 100)], 0) == [(100, 130)]                       # đầu/cuối đảo vẫn đúng


def test_ma_video_va_gioi_han_ban_mot_phan():
    assert td.ma_video("AbCdEfGhIjK.webm") == "AbCdEfGhIjK"
    assert td.ma_video("AbCdEfGhIjK__p10800.webm") == "AbCdEfGhIjK"
    assert td.gioi_han_ten("AbCdEfGhIjK__p10800.webm") == 10800
    assert td.gioi_han_ten("AbCdEfGhIjK.webm") == math.inf
    # Mã YouTube hợp lệ có thể chứa «__p<số>»: mã có trong lịch sử thì nhận nguyên, không coi là bản một phần.
    assert td.ma_video("ab__p123456.webm", {"ab__p123456"}) == "ab__p123456"
    assert td.gioi_han_ten("ab__p123456.webm", {"ab__p123456"}) == math.inf


def test_uoc_giu_byte_theo_ti_le_thoi_luong():
    ls = td.LichSuDem(doan={"A": [(100, 130)]}, da_quet={"A", "B"}, thoi_luong={"A": 600, "B": 0})
    assert td.uoc_giu_byte("A.webm", 6000, ls, 60) == 1500                     # 150 / 600 giây
    assert td.uoc_giu_byte("B.webm", 6000, ls, 60) == 0                        # không vi phạm
    ls.thoi_luong["A"] = 0
    assert td.uoc_giu_byte("A.webm", 6000, ls, 60) == 6000                     # không rõ thời lượng → ước giữ cả


# ------------------------------------------------------------------ FFmpeg thật

@pytest.fixture(scope="module")
def chirp(tmp_path_factory):
    d = tmp_path_factory.mktemp("chirp")
    goc = d / "goc.webm"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"aevalsrc=sin(2*PI*(200+t)*t):s=16000:d={DAI_S}", "-ac", "1", "-c:a", "libopus", "-b:a",
                        "24k", str(goc)], capture_output=True, timeout=120)
    if r.returncode != 0 or not goc.exists():
        pytest.skip("ffmpeg không mã hoá được opus/webm trên máy này")
    return goc


def _giay_goc_o_dau(path) -> float:
    """Giây trên file gốc ứng với 0,5 giây đầu của ``path`` (tần số chirp = 200 + 2t Hz)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-t", "0.5", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar",
                          "16000", "-"], capture_output=True, timeout=60).stdout
    x = np.frombuffer(raw, np.int16).astype(float)
    pho = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return (np.fft.rfftfreq(len(x), 1 / 16000)[pho.argmax()] - 200) / 2


def _dat(dl, ten, nguon, tuoi_ngay=9):
    p = os.path.join(dl, ten)
    shutil.copyfile(nguon, p)
    moc = time.time() - tuoi_ngay * NGAY
    os.utime(p, (moc, moc))
    return p


def _so(dl, ma):
    with open(os.path.join(dl, td.THU_MUC_BANG_CHUNG, ma, td.TEN_SO), encoding="utf-8") as f:
        return json.load(f)


@can_ffmpeg
def test_don_dem_giu_doan_vi_pham_bo_video_sach_giu_file_chua_ro(tmp_path, chirp):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    # Mốc lẻ (103, 302): FFmpeg nhảy theo chỉ mục nên đoạn trích BẮT ĐẦU SỚM hơn mốc yêu cầu (file webm thật của
    # YouTube: sớm 1,8 giây, đo 25/11) — sổ phải ghi mốc đầu THẬT, không phải mốc yêu cầu.
    ghi_lich_su(data, sach=["BBBBBBBBBBB"], vi_pham={"AAAAAAAAAAA": [(103, 130), (302, 320)]},
                thoi_luong={"AAAAAAAAAAA": DAI_S})
    a = _dat(dl, "AAAAAAAAAAA.webm", chirp)
    b = _dat(dl, "BBBBBBBBBBB.webm", chirp)
    c = _dat(dl, "CCCCCCCCCCC.webm", chirp)            # không có trong lịch sử (vd. lô «video gốc chung»)
    kich = os.path.getsize(a)

    xem = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7, thuc_hien=False)
    assert (xem["xoa_file"], xem["trich_file"], xem["giu_chua_ro"]) == (1, 1, 1), xem
    assert xem["uoc_giu_gb"] == pytest.approx(kich * 285 / DAI_S / 1024 ** 3, rel=0.01)
    assert os.path.exists(a) and os.path.exists(b) and not os.path.isdir(dl / td.THU_MUC_BANG_CHUNG)

    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7)
    assert not kq["loi"], kq["loi"]
    assert (kq["xoa_file"], kq["trich_file"], kq["giu_chua_ro"]) == (1, 1, 1), kq
    assert not os.path.exists(a) and not os.path.exists(b) and os.path.exists(c)
    so = _so(dl, "AAAAAAAAAAA")
    assert so["ma_video"] == "AAAAAAAAAAA" and so["link"].endswith("AAAAAAAAAAA") and so["dem_giay"] == 60
    assert [round(d["ket_thuc_s"]) for d in so["doan"]] == [190, 380]
    assert so["doan"][0]["bat_dau_s"] <= 43.05 and so["doan"][1]["bat_dau_s"] <= 242.05     # phủ trọn đoạn yêu cầu
    for d in so["doan"]:
        p = dl / td.THU_MUC_BANG_CHUNG / "AAAAAAAAAAA" / d["file"]
        assert p.is_file() and d["tu_file"] == "AAAAAAAAAAA.webm"
        assert _giay_goc_o_dau(p) == pytest.approx(d["bat_dau_s"], abs=1.0)    # sổ ghi đúng giây đầu THẬT trên video gốc
    assert kq["trich_gb_giu"] * 1024 ** 3 == pytest.approx(sum(d["byte"] for d in so["doan"]))
    assert kq["trich_gb_giu"] < kq["trich_gb_nguon"] * 0.6
    dong = [json.loads(x) for x in (data / don_dep.TEN_NHAT_KY_DON_DEM).read_text(encoding="utf-8").splitlines()]
    assert sorted((x["file"], x["hanh_dong"]) for x in dong) == [("AAAAAAAAAAA.webm", "cat_giu"),
                                                                 ("BBBBBBBBBBB.webm", "bo")]
    # Đoạn trích không bao giờ là «bản đệm» và không bị dọn ở lượt sau.
    kq2 = don_dep.don_kho_dem(str(dl), max_gb=0.000001, max_ngay=7)
    assert kq2["tong_file"] == 1 and all((dl / td.THU_MUC_BANG_CHUNG / "AAAAAAAAAAA" / d["file"]).is_file()
                                         for d in so["doan"])


@can_ffmpeg
def test_ban_mot_phan_va_ban_day_du_cung_video_khong_cat_trung(tmp_path, chirp):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, vi_pham={"AAAAAAAAAAA": [(100, 130), (300, 320)]}, thoi_luong={"AAAAAAAAAAA": DAI_S})
    _dat(dl, "AAAAAAAAAAA__p200.webm", chirp, tuoi_ngay=10)    # bản «200 giây đầu» (file thử dài hơn — chỉ tên nói)
    _dat(dl, "AAAAAAAAAAA.webm", chirp, tuoi_ngay=9)
    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7)
    assert not kq["loi"] and kq["trich_file"] == 2, kq
    so = _so(dl, "AAAAAAAAAAA")
    assert [(round(d["bat_dau_s"]), round(d["ket_thuc_s"])) for d in so["doan"]] == [(40, 190), (240, 380)]
    assert len(os.listdir(dl / td.THU_MUC_BANG_CHUNG / "AAAAAAAAAAA")) == 3          # 2 đoạn + sổ
    assert not any(f.endswith(".webm") for f in os.listdir(dl))


@can_ffmpeg
def test_moc_sau_cho_het_am_thanh_giu_toi_cuoi_file(tmp_path, chirp):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, vi_pham={"AAAAAAAAAAA": [(590, 700)]})     # thời lượng không rõ, mốc vượt cuối file
    _dat(dl, "AAAAAAAAAAA.webm", chirp)
    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7)
    assert not kq["loi"] and kq["trich_file"] == 1, kq
    (d,) = _so(dl, "AAAAAAAAAAA")["doan"]
    assert d["bat_dau_s"] == pytest.approx(530, abs=0.5) and d["ket_thuc_s"] == pytest.approx(DAI_S, abs=0.5)


def test_cat_hong_thi_giu_nguyen_ban_day_du(tmp_path):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, vi_pham={"AAAAAAAAAAA": [(100, 130)]}, thoi_luong={"AAAAAAAAAAA": DAI_S})
    hong = dl / "AAAAAAAAAAA.webm"
    hong.write_bytes(b"khong phai media" * 100)
    moc = time.time() - 9 * NGAY
    os.utime(hong, (moc, moc))
    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7)
    assert hong.exists() and kq["trich_file"] == 0 and not kq["loi"] and len(kq["canh_bao"]) == 1, kq
    assert "giữ nguyên bản đầy đủ" in kq["canh_bao"][0]
    thu_muc = dl / td.THU_MUC_BANG_CHUNG / "AAAAAAAAAAA"
    assert not thu_muc.exists() or not os.listdir(thu_muc)                        # không để lại đoạn dở / sổ


def test_lich_su_doc_loi_thi_khong_don_gi(tmp_path):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    (data / "lichsu.db").write_bytes(b"day khong phai sqlite" * 50)
    f = dl / "AAAAAAAAAAA.webm"
    f.write_bytes(b"x" * 100)
    moc = time.time() - 9 * NGAY
    os.utime(f, (moc, moc))
    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7)
    assert f.exists() and kq["xoa_file"] == 0 and "lichsu.db" in kq["loi"][0]


def test_mot_luot_don_tai_mot_thoi_diem_va_nut_dung(tmp_path):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, sach=["BBBBBBBBBBB"])
    f = dl / "BBBBBBBBBBB.webm"
    f.write_bytes(b"x" * 100)
    moc = time.time() - 9 * NGAY
    os.utime(f, (moc, moc))
    with KhoaTienTrinh(str(data / don_dep.TEN_KHOA_DON_DEM), "lượt dọn khác"):
        kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7)
    assert kq["dang_chay_noi_khac"] and f.exists() and not kq["loi"] and kq["canh_bao"]     # bận ≠ lỗi
    dung = threading.Event()
    dung.set()
    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7, cancel_event=dung)
    assert kq["da_dung"] and f.exists()
    tien_do = []
    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7, progress=lambda pct, cau: tien_do.append(pct))
    assert not f.exists() and tien_do[-1] == 1.0


def test_chua_co_lich_su_thi_giu_moi_file(tmp_path):
    dl = tmp_path / "data" / "downloads"
    dl.mkdir(parents=True)
    f = dl / "AAAAAAAAAAA.webm"
    f.write_bytes(b"x" * 100)
    moc = time.time() - 30 * NGAY
    os.utime(f, (moc, moc))
    kq = don_dep.don_kho_dem(str(dl), max_gb=0.000001, max_ngay=7)
    assert f.exists() and kq["giu_chua_ro"] == 1 and kq["xoa_file"] == 0


# ------------------------------------------------------------------ nơi gọi: lô quét, Giám sát, dòng lệnh, giao diện

def test_tu_don_dem_sau_lo_chi_khi_bat(tmp_path):
    import types

    from engine import Config
    from scan_jobs import tu_don_dem
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, sach=["BBBBBBBBBBB"])
    f = dl / "BBBBBBBBBBB.webm"
    f.write_bytes(b"x" * 100)
    moc = time.time() - 9 * NGAY
    os.utime(f, (moc, moc))
    eng = types.SimpleNamespace(config=Config(), dl_dir=str(dl))
    assert tu_don_dem(eng) is None and f.exists()                 # mặc định TẮT
    eng.config.dem_tu_dong = True
    luong = tu_don_dem(eng)
    luong.join(30)
    assert not luong.is_alive() and not f.exists()


@pytest.mark.parametrize("dung", [False, True])
def test_lo_quet_xong_goi_tu_don_dem_tru_khi_bam_dung(engine, monkeypatch, dung):
    import scan_jobs
    goi = []
    monkeypatch.setattr(scan_jobs, "tu_don_dem", lambda eng: goi.append(eng))

    def scan_iter(nguon, source_type, progress, on_video=None, **_k):
        if dung:
            engine.cancel_event.wait(10)
        return iter(())

    monkeypatch.setattr(engine, "scan_iter", scan_iter)
    ctl = scan_jobs.ScanJobController(engine)
    ctl.start(["https://youtu.be/aaaaaaaaaaa"], "youtube")
    if dung:
        ctl.cancel()
    han = time.monotonic() + 30
    while ctl.running and time.monotonic() < han:
        time.sleep(0.05)
    time.sleep(0.2)
    assert goi == ([] if dung else [engine])


def test_khong_giu_dem_van_giu_audio_video_co_ket_qua(tmp_path):
    """«Giữ lại audio đã tải» tắt: trước đây bỏ audio ngay cả khi video vi phạm — mất bằng chứng. Giờ video có kết quả
    giữ audio tới lần dọn đệm (dọn đệm cắt giữ đoạn quanh mốc); video không có kết quả vẫn bỏ ngay như cũ."""
    from engine import Engine, Match, ScanResult
    ket = {}
    for ma, co_khop in (("AAAAAAAAAAA", True), ("BBBBBBBBBBB", False)):
        e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
        e.require = lambda *a, **k: None
        e.config.keep_downloads = False
        e.youtube_info = lambda url, ma=ma: {"title": "V", "id": ma, "channel": "", "channel_id": "",
                                             "channel_url": "", "upload_date": "", "duration": 600.0}

        def tai(url, vid, progress=None, gioi_han_giay=None, e=e):
            tep = os.path.join(e.dl_dir, f"{vid}.webm")
            with open(tep, "wb") as fh:
                fh.write(b"x")
            return tep

        def quet(path, co_khop=co_khop, **kw):
            m = [Match(clip="clip.opus", start_s=100.0, end_s=130.0, matched_s=30.0, clip_offset_s=0.0, hashes=5000,
                       confidence="cao")] if co_khop else []
            return ScanResult(source_name="V", duration_s=600.0, vung_da_khop=[(0.0, 600.0)], matches=m)

        e.download_audio = tai
        e.scan_media = quet
        e.scan_youtube(f"https://youtu.be/{ma}")
        ket[ma] = os.path.exists(os.path.join(e.dl_dir, f"{ma}.webm"))
    assert ket == {"AAAAAAAAAAA": True, "BBBBBBBBBBB": False}


def test_giam_sat_va_dong_lenh_bao_doan_trich(engine, monkeypatch, capsys, tmp_path):
    import types

    import cli
    from watch import MucTheoDoi, WatchList, chay_giam_sat
    kq = {"tong_file": 3, "tong_gb": 3.0, "xoa_file": 1, "xoa_gb": 0.5, "trich_file": 2, "trich_gb_nguon": 2.0,
          "trich_gb_giu": 0.25, "uoc_giu_gb": 0.25, "giu_chua_ro": 1, "giu_chua_ro_gb": 0.1, "bo_qua_dang_dung": 0,
          "loi": [], "thu_muc_bang_chung": "X:/bang_chung"}
    monkeypatch.setattr("watch.don_kho_dem", lambda *a, **k: dict(kq))
    monkeypatch.setattr(engine, "list_jobs", lambda limit: [])
    bao_cao = chay_giam_sat(engine, WatchList(muc=[MucTheoDoi("kenh", "kenh-1")]), lister=lambda url, limit: [])
    assert bao_cao.da_don_file == 3 and bao_cao.da_don_gb == pytest.approx(2.25)
    assert "2 file video vi phạm chỉ giữ đoạn quanh mốc" in bao_cao.tom_tat()

    eng = types.SimpleNamespace(dl_dir=str(tmp_path), data_dir=str(tmp_path),
                                config=types.SimpleNamespace(ncores=1, dem_max_gb=20.0, dem_max_ngay=7))
    monkeypatch.setattr("sys.argv", ["cli.py", "dondep", "--xem-truoc"])
    monkeypatch.setattr(cli, "Engine", lambda: eng)
    monkeypatch.setattr(cli.don_dep, "don_kho_dem", lambda *a, **k: dict(kq))
    cli.main()
    ra = capsys.readouterr().out
    assert "Sẽ cắt giữ đoạn quanh mốc vi phạm của 2 file" in ra and "khoảng 0.250 GB" in ra
    assert "Giữ nguyên 1 file" in ra


def _app(tmp_path, monkeypatch, job=None):
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv("TIMCLIP_UI_VE_MOI_TRANG", raising=False)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py"), default_timeout=120)
    if job is not None:
        at.session_state["job"] = job
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_hop_don_dem_xem_truoc_dung_so_va_phai_tick_moi_don(tmp_path, monkeypatch):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, sach=["BBBBBBBBBBB"], vi_pham={"AAAAAAAAAAA": [(100, 130)]}, thoi_luong={"AAAAAAAAAAA": 600})
    for ten in ("AAAAAAAAAAA.webm", "BBBBBBBBBBB.webm"):
        (dl / ten).write_bytes(b"x" * 6000)
        moc = time.time() - 9 * NGAY
        os.utime(dl / ten, (moc, moc))
    at = _app(tmp_path, monkeypatch)
    at.button(key="mo_don_dem").click().run()
    assert [m.value for m in at.metric][:2] == ["1 file", "1 file"]
    assert at.button(key="don_dem_chay").disabled and not _o_xac_nhan(at).value
    assert (dl / "AAAAAAAAAAA.webm").exists() and (dl / "BBBBBBBBBBB.webm").exists()   # xem trước không xoá gì


def test_ket_qua_don_dem_hien_dung_so_giai_phong(tmp_path, monkeypatch):
    r = {"tong_file": 3, "tong_gb": 3.0, "xoa_file": 1, "xoa_gb": 0.5, "trich_file": 2, "trich_gb_nguon": 2.0,
         "trich_gb_giu": 0.25, "uoc_giu_gb": 0.0, "giu_chua_ro": 0, "giu_chua_ro_gb": 0.0, "bo_qua_dang_dung": 0,
         "loi": [], "da_dung": False, "dang_chay_noi_khac": False, "thu_muc_bang_chung": str(tmp_path / "khong_co")}
    at = _app(tmp_path, monkeypatch, job={"running": False, "pct": 1.0, "msg": "", "results": r, "error": "",
                                          "kind": "don_dem", "da_day_sheet": False})
    cau = [s.value for s in at.success]
    assert any("giải phóng 2.2 GB" in c and "2 file video vi phạm" in c for c in cau), cau


# ------------------------------------------------------------------ review 25/11: các ca đã xác nhận

def _o_xac_nhan(at):
    return next(c for c in at.checkbox if (c.key or "").startswith("don_dem_xac_nhan"))


def _dl_hai_file(tmp_path, tuoi_ngay=9):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, sach=["BBBBBBBBBBB"], vi_pham={"AAAAAAAAAAA": [(100, 130)]}, thoi_luong={"AAAAAAAAAAA": 600})
    for ten in ("AAAAAAAAAAA.webm", "BBBBBBBBBBB.webm"):
        (dl / ten).write_bytes(b"x" * 6000)
        moc = time.time() - tuoi_ngay * NGAY
        os.utime(dl / ten, (moc, moc))
    return data, dl


def test_hop_don_dem_luu_chi_ghi_truong_don_dem_giu_cai_dat_khac(tmp_path, monkeypatch):
    """Hộp dọn đệm từng gọi ``luu_cau_hinh()`` không ``them`` → ghi lại cả file chỉ với trường Config: link Sheet, thư
    mục kho, đường dẫn Twitch… biến mất ở lần mở app sau, và ô thanh bên chưa bấm «Lưu» bị ghi luôn (review 25/11)."""
    data, _dl = _dl_hai_file(tmp_path)
    goc = {"sheet_link": "https://example.invalid/sheet-gia", "kho_dir": "D:/KhoThu", "twitch_proxy_file": "D:/p.txt",
           "bao_tieng_xong": False, "min_hash": 20}
    (data / "cau_hinh.json").write_text(json.dumps(goc), encoding="utf-8")
    at = _app(tmp_path, monkeypatch)
    at.button(key="mo_don_dem").click().run()
    # AppTest không chạy lại riêng hộp: bấm lại nút mở trong CÙNG lượt để hộp còn trên trang khi bấm nút bên trong.
    at.button(key="mo_don_dem").click()
    at.button(key="don_dem_luu").click().run()
    assert not at.exception, [e.value for e in at.exception]
    so = json.loads((data / "cau_hinh.json").read_text(encoding="utf-8"))
    assert {k: so.get(k) for k in goc} == goc, so
    assert so["dem_max_ngay"] == 7 and so["dem_tu_dong"] is False


def test_luu_cau_hinh_mot_phan_khong_ghi_o_thanh_ben_chua_luu(engine):
    import cau_hinh
    engine.luu_cau_hinh({"sheet_link": "https://example.invalid/a", "kho_dir": "D:/K"})
    engine.config.min_hash = 8                      # sửa ở thanh bên, CHƯA bấm «💾 Lưu cấu hình»
    engine.luu_cau_hinh_mot_phan({"dem_tu_dong": True, "dem_max_ngay": 3, "dem_max_gb": 10.0})
    so = cau_hinh.doc_cau_hinh(engine.data_dir)
    assert so["sheet_link"] == "https://example.invalid/a" and so["kho_dir"] == "D:/K"
    assert so["dem_tu_dong"] is True and so["dem_max_ngay"] == 3 and so["min_hash"] != 8
    assert engine.config.dem_tu_dong is True
    with pytest.raises(ValueError):
        engine.luu_cau_hinh_mot_phan({"dem_max_ngay": -1})


def test_hop_don_dem_doi_luat_phai_tick_lai_va_bat_tu_don_phai_dong_y(tmp_path, monkeypatch):
    _data, _dl = _dl_hai_file(tmp_path)
    at = _app(tmp_path, monkeypatch)
    at.button(key="mo_don_dem").click().run()
    _o_xac_nhan(at).check()
    at.button(key="mo_don_dem").click().run()
    assert _o_xac_nhan(at).value and not at.button(key="don_dem_chay").disabled
    # Đổi luật (7 → 3 ngày): danh sách file có thể khác → ô đồng ý phải trống lại.
    next(n for n in at.number_input if n.label.startswith("Giữ trọn audio")).set_value(3)
    at.button(key="mo_don_dem").click().run()
    assert not _o_xac_nhan(at).value and at.button(key="don_dem_chay").disabled
    # Bật «tự dọn» lúc đang có file tới hạn: «Lưu lựa chọn» khoá — phải qua ô đồng ý + «Dọn ngay».
    next(c for c in at.checkbox if c.label.startswith("Từ nay tự dọn")).check()
    at.button(key="mo_don_dem").click().run()
    assert at.button(key="don_dem_luu").disabled


def test_doan_cat_ra_hut_thi_giu_nguyen_ban_day_du(tmp_path, monkeypatch):
    """Chốt an toàn chính: đoạn trích ngắn hơn cửa sổ (FFmpeg cụt, ổ đầy giữa chừng…) → KHÔNG bỏ bản đầy đủ."""
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, vi_pham={"AAAAAAAAAAA": [(100, 130)]}, thoi_luong={"AAAAAAAAAAA": 600})
    f = dl / "AAAAAAAAAAA.webm"
    f.write_bytes(b"x" * 6000)
    moc = time.time() - 9 * NGAY
    os.utime(f, (moc, moc))
    monkeypatch.setattr(td, "_do_dai", lambda p: 600.0 if p.endswith("AAAAAAAAAAA.webm") else 5.0)

    def cat_gia(nguon, a, b, dich, cancel_event=None):
        with open(dich, "wb") as fh:
            fh.write(b"y" * 100)
        return 5.0

    monkeypatch.setattr(td, "cat_doan", cat_gia)
    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7)
    assert f.exists() and kq["trich_file"] == 0 and not kq["loi"] and len(kq["canh_bao"]) == 1, kq
    assert "5.0/150.0 giây" in kq["canh_bao"][0]
    thu_muc = dl / td.THU_MUC_BANG_CHUNG / "AAAAAAAAAAA"
    assert not (thu_muc / td.TEN_SO).exists() and not os.listdir(thu_muc)


@can_ffmpeg
def test_cua_so_vuot_cuoi_file_so_ghi_dung_moc_that(tmp_path, chirp):
    """Cửa sổ [479,5; 604,5] vượt cuối file 600 s: điểm đầu nhảy về chỉ mục (sớm hơn 479,5) che phần hụt ở cuối — trước
    đây sổ ghi 479,5–604,5 trong khi đoạn thật là ~475–600 (review 25/11)."""
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, vi_pham={"AAAAAAAAAAA": [(539.5, 544.5)]}, thoi_luong={"AAAAAAAAAAA": DAI_S})
    _dat(dl, "AAAAAAAAAAA.webm", chirp)
    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7)
    assert not kq["loi"] and not kq["canh_bao"] and kq["trich_file"] == 1, kq
    (d,) = _so(dl, "AAAAAAAAAAA")["doan"]
    assert d["ket_thuc_s"] == pytest.approx(DAI_S, abs=0.1) and d["bat_dau_s"] <= 479.55
    p = dl / td.THU_MUC_BANG_CHUNG / "AAAAAAAAAAA" / d["file"]
    assert _giay_goc_o_dau(p) == pytest.approx(d["bat_dau_s"], abs=1.0)


@can_ffmpeg
def test_doan_trich_va_so_ben_tren_dia_truoc_khi_bo_ban_day_du(tmp_path, chirp, monkeypatch):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, vi_pham={"AAAAAAAAAAA": [(100, 130), (300, 320)]}, thoi_luong={"AAAAAAAAAAA": DAI_S})
    _dat(dl, "AAAAAAAAAAA.webm", chirp)
    su_kien = []
    fsync_that, remove_that = os.fsync, os.remove
    monkeypatch.setattr(os, "fsync", lambda fd: (su_kien.append("fsync"), fsync_that(fd))[1])
    monkeypatch.setattr(os, "remove", lambda p: (su_kien.append(("bo", os.path.basename(p))), remove_that(p))[1])
    kq = don_dep.don_kho_dem(str(dl), max_gb=20, max_ngay=7)
    assert kq["trich_file"] == 1, kq
    bo = su_kien.index(("bo", "AAAAAAAAAAA.webm"))
    assert su_kien[:bo].count("fsync") >= 3       # 2 đoạn trích + sổ, đều TRƯỚC lúc bỏ bản đầy đủ


def test_file_vua_dung_trong_1_gio_khong_bi_xu_ly_du_vuot_ngan_sach(tmp_path):
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, sach=["BBBBBBBBBBB", "CCCCCCCCCCC"])
    vua, cu = dl / "BBBBBBBBBBB.webm", dl / "CCCCCCCCCCC.webm"
    for p, tuoi_s in ((vua, 30 * 60), (cu, 2 * 3600)):
        p.write_bytes(b"x" * 3000)
        os.utime(p, (time.time() - tuoi_s, time.time() - tuoi_s))
    kq = don_dep.don_kho_dem(str(dl), max_gb=1000 / 1024 ** 3, max_ngay=7)
    assert vua.exists() and not cu.exists() and kq["bo_qua_dang_dung"] == 1, kq


def test_file_chua_ro_khong_an_ngan_sach(tmp_path):
    """File không có trong lịch sử vượt ngân sách từng làm ngân sách sập về 1 byte → audio vừa quét bị bỏ (review 25/11)."""
    data = tmp_path / "data"
    dl = data / "downloads"
    dl.mkdir(parents=True)
    ghi_lich_su(data, sach=["BBBBBBBBBBB"])
    la, quen = dl / "ZZZZZZZZZZZ.webm", dl / "BBBBBBBBBBB.webm"
    la.write_bytes(b"x" * 30_000)
    os.utime(la, (time.time() - 30 * NGAY,) * 2)
    quen.write_bytes(b"x" * 1000)
    os.utime(quen, (time.time() - 2 * 3600,) * 2)
    kq = don_dep.don_kho_dem(str(dl), max_gb=20_000 / 1024 ** 3, max_ngay=7)
    assert la.exists() and quen.exists() and kq["giu_chua_ro"] == 1 and kq["xoa_file"] == 0, kq


def test_ban_cut_co_ket_qua_doi_ten_giu_bang_chung(engine):
    from engine import Match, ScanResult
    e = engine
    os.makedirs(e.dl_dir, exist_ok=True)
    co_kq = ScanResult(source_name="V", matches=[Match(clip="c.opus", start_s=100.0, end_s=130.0, matched_s=30.0, clip_offset_s=0.0,
                                      hashes=5000, confidence="cao")])

    def tao(ten):
        p = os.path.join(e.dl_dir, ten)
        with open(p, "wb") as fh:
            fh.write(b"x")
        return p

    e._bo_ban_cut(tao("AAAAAAAAAAA.webm"), co_kq, 1234.5)
    e._bo_ban_cut(tao("CCCCCCCCCCC__p10800.webm"), co_kq, 5000.2)
    e._bo_ban_cut(tao("BBBBBBBBBBB.webm"), ScanResult(source_name="V"), 100.0)            # không có kết quả: bỏ như cũ
    d = tao("DDDDDDDDDDD.webm")
    dau = don_dep.dat_dau_dang_dung(e.dl_dir, "DDDDDDDDDDD.webm")
    try:
        e._bo_ban_cut(d, co_kq, 100.0)                                     # lượt khác đang dùng: giữ nguyên
    finally:
        don_dep.nha_dau_dang_dung(dau)
    assert sorted(f for f in os.listdir(e.dl_dir) if os.path.isfile(os.path.join(e.dl_dir, f))) == [
        "AAAAAAAAAAA__p1234.webm", "CCCCCCCCCCC__p5000.webm", "DDDDDDDDDDD.webm"]


def test_tai_thieu_co_ket_qua_doi_ten_ban_cut_lan_sau_van_tai_lai(tmp_path):
    """Tải về ngắn hơn video mà vẫn thấy vi phạm: trước đây bản audio duy nhất bị xoá ngay. Giờ đổi tên thành bản «N giây
    đầu» (dọn đệm cắt giữ đoạn sau); bộ đệm không nhận nó là bản đầy đủ nên lượt sau vẫn tải lại (review 25/11)."""
    from engine import Engine, Match, ScanResult
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e.youtube_info = lambda url: {"title": "V", "id": "AAAAAAAAAAA", "channel": "", "channel_id": "",
                                  "channel_url": "", "upload_date": "", "duration": 600.0}
    tai = []

    def tai_gia(url, vid, progress=None, gioi_han_giay=None):
        tai.append(vid)
        p = os.path.join(e.dl_dir, f"{vid}.webm")
        with open(p, "wb") as fh:
            fh.write(b"x")
        return p

    m = Match(clip="c.opus", start_s=100.0, end_s=130.0, matched_s=30.0, clip_offset_s=0.0, hashes=5000,
              confidence="cao")
    e.download_audio = tai_gia
    e.scan_media = lambda path, **kw: ScanResult(source_name="V", duration_s=300.0, vung_da_khop=[(0.0, 300.0)],
                                                 matches=[m])
    kq = e.scan_youtube("https://youtu.be/AAAAAAAAAAA")
    assert kq.matches and sorted(os.listdir(e.dl_dir)) == ["AAAAAAAAAAA__p300.webm"]
    assert e._file_trong_dem("AAAAAAAAAAA") == []                       # lượt sau không dùng lại bản cụt


def test_khong_giu_dem_lo_khong_ghi_lich_su_van_bo_ngay(tmp_path):
    """Lô «video gốc chung» (luu_lich_su=False) không ghi lịch sử: dọn đệm không bao giờ nhận ra file → bỏ ngay như cũ."""
    from engine import Engine, Match, ScanResult
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e.config.keep_downloads = False
    e.youtube_info = lambda url: {"title": "V", "id": "AAAAAAAAAAA", "channel": "", "channel_id": "",
                                  "channel_url": "", "upload_date": "", "duration": 600.0}

    def tai_gia(url, vid, progress=None, gioi_han_giay=None):
        p = os.path.join(e.dl_dir, f"{vid}.webm")
        with open(p, "wb") as fh:
            fh.write(b"x")
        return p

    m = Match(clip="c.opus", start_s=100.0, end_s=130.0, matched_s=30.0, clip_offset_s=0.0, hashes=5000,
              confidence="cao")
    e.download_audio = tai_gia
    e.scan_media = lambda path, **kw: ScanResult(source_name="V", duration_s=600.0, vung_da_khop=[(0.0, 600.0)],
                                                 matches=[m])
    e.scan_youtube("https://youtu.be/AAAAAAAAAAA", luu_lich_su=False)
    assert not os.path.exists(os.path.join(e.dl_dir, "AAAAAAAAAAA.webm"))


def test_don_dem_ban_khong_lam_giam_sat_bao_loi_va_dong_lenh_thoat_ma_2(engine, monkeypatch, tmp_path):
    import types

    import cli
    from watch import MucTheoDoi, WatchList, chay_giam_sat
    ban = {"tong_file": 0, "tong_gb": 0.0, "xoa_file": 0, "xoa_gb": 0.0, "trich_file": 0, "trich_gb_nguon": 0.0,
           "trich_gb_giu": 0.0, "uoc_giu_gb": 0.0, "giu_chua_ro": 0, "giu_chua_ro_gb": 0.0, "bo_qua_dang_dung": 0,
           "loi": [], "canh_bao": ["Một lượt dọn đệm khác đang chạy — để lần sau."], "dang_chay_noi_khac": True,
           "thu_muc_bang_chung": "X:/bang_chung"}
    monkeypatch.setattr("watch.don_kho_dem", lambda *a, **k: dict(ban))
    monkeypatch.setattr(engine, "list_jobs", lambda limit: [])
    bc = chay_giam_sat(engine, WatchList(muc=[MucTheoDoi("kenh", "kenh-1")]), lister=lambda url, limit: [])
    assert bc.loi == [] and "Lưu ý dọn đệm: Một lượt dọn đệm khác" in bc.tom_tat()
    eng = types.SimpleNamespace(dl_dir=str(tmp_path), data_dir=str(tmp_path),
                                config=types.SimpleNamespace(ncores=1, dem_max_gb=20.0, dem_max_ngay=7))
    monkeypatch.setattr("sys.argv", ["cli.py", "dondep"])
    monkeypatch.setattr(cli, "Engine", lambda: eng)
    monkeypatch.setattr(cli.don_dep, "don_kho_dem", lambda *a, **k: dict(ban))
    with pytest.raises(SystemExit) as thoat:
        cli.main()
    assert thoat.value.code == 2
