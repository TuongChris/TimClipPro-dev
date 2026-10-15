# -*- coding: utf-8 -*-
"""Đồng bộ kênh — sự cố Stable 1.1.1 với kênh có video giới hạn tuổi (PC2, 15/10/2026).

Triệu chứng: ba video «Sign in to confirm your age» liên tiếp mở cầu dao AUTH_REQUIRED (ngưỡng 3) → 0 video tải mới,
1.189 video chưa thử, nhưng giao diện vẫn «✅ Đồng bộ xong». Cấu hình có CẢ file cookie lẫn trình duyệt → yt-dlp gộp hai
hũ cookie và lúc đóng phiên ghi hũ đã gộp vào file cookie. Kho vân tay đang chọn (SML) khác thư mục audio vừa đồng bộ.

yt-dlp là bản giả theo kịch bản (`tests/ytdlp_gia.py`); FFmpeg/ffprobe thay bằng hàm giả (chép file, độ dài cố định).
Không mạng, không cookie thật (file cookie GIẢ chỉ để kiểm không rò rỉ).
"""

import gzip
import hashlib
import json
import os
import pickle
import shutil
import sys
import time
from pathlib import Path

import pytest
import yt_dlp
from streamlit.testing.v1 import AppTest

import channel
import scan_ui
import truy_cap_youtube as t
import ytdlp_chung as y
from channel import ChannelSync
from engine import Engine
from ytdlp_gia import AUTH, BOT, R429, YdlKichBan

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audfprint-master"))
import hash_table  # noqa: E402

SAN_SANG = y.KhaNangJs(True, node=r"C:\gia\nodejs\node.exe", node_phien_ban="24.21.0", ejs_phien_ban="0.8.0")
HOI_VIEN = "ERROR: [youtube] {id}: Join this channel to get access to members-only content like this video."
DANG_NHAP = "ERROR: [youtube:tab] {id}: Login details are needed to download this content."
BI_MAT = "GIA-BI-MAT-KHONG-DUOC-LO-7f3a9c"
DAI = 600.0


def _ma(i: int) -> str:
    return f"j{i:010d}"                 # 11 ký tự như mã YouTube


def _danh_sach(ids):
    return {"_type": "playlist", "id": "UCkenh_b", "entries": [
        {"id": m, "title": f"Video {m}", "url": f"https://www.youtube.com/watch?v={m}", "duration": DAI}
        for m in ids]}


def _sha(p) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


@pytest.fixture()
def may(monkeypatch):
    """Máy giả lập đủ Node.js + EJS; nghỉ thử lại ngắn; FFmpeg/ffprobe giả."""
    monkeypatch.setattr(y, "kha_nang_js", lambda: SAN_SANG)
    for k in ("metadata", "listing"):
        monkeypatch.setitem(t.NGAN_SACH, k, t.NganSach(cho_tam_thoi=(0.01,), cho_429=(0.01,)))
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    monkeypatch.setattr(channel, "do_dai_luong_tieng", lambda p: DAI)


def _cs(kho, cau_hinh=None) -> ChannelSync:
    cs = ChannelSync(str(kho), cau_hinh_mang=cau_hinh)

    def nen(nguon, tam, _tham_chieu, _huy):
        shutil.copyfile(nguon, tam)
        return ""
    cs._nen_va_kiem = nen
    return cs


def _vá(monkeypatch, ydl):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    return ydl


def _kho_74(kho: Path, so: int = 74) -> dict:
    """Kho kênh B đã có `so` audio ĐÃ XÁC NHẬN (dấu xac_nhan_tep) + downloaded.txt + clips_meta.json."""
    kho.mkdir(parents=True, exist_ok=True)
    meta, archive = {}, []
    for i in range(so):
        ten = f"20240101 - KenhB cu {i} [{_ma(i)}].opus"
        p = kho / ten
        p.write_bytes(b"opus da co " + str(i).encode())
        meta[ten] = {"id": _ma(i), "title": f"KenhB cu {i}", "duration": DAI,
                     "xac_nhan_tep": {"kich_thuoc": p.stat().st_size, "do_dai": DAI}}
        archive.append(f"youtube {_ma(i)}\n")
    (kho / "clips_meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (kho / "downloaded.txt").write_text("".join(archive), encoding="utf-8")
    return {p.name: (_sha(p), p.stat().st_mtime_ns) for p in kho.glob("*.opus")}


def _cookie_gia(p: Path) -> str:
    p.write_text("# Netscape HTTP Cookie File\n"
                 f".youtube.com\tTRUE\t/\tTRUE\t4102444800\tLOGIN_INFO\t{BI_MAT}a\n"
                 f".youtube.com\tTRUE\t/\tTRUE\t4102444800\tSAPISID\t{BI_MAT}b\n"
                 f".youtube.com\tTRUE\t/\tTRUE\t4102444800\t__Secure-3PSID\t{BI_MAT}c\n", encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------- 1. một nguồn cookie hiệu lực

def test_cau_hinh_ca_file_lan_trinh_duyet_chi_dung_file(tmp_path, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"), cookies_browser="chrome")
    opts = ch.tuy_chon("download")
    assert opts.get("cookiefile") == str(tmp_path / "c.txt")
    assert "cookiesfrombrowser" not in opts, "gộp hai nguồn: yt-dlp ghi cookie trình duyệt vào file lúc đóng phiên"
    assert ch.hai_nguon_cookie and ch.nguon_cookie_hieu_luc == "file"


def test_chi_trinh_duyet_thi_dung_trinh_duyet(may):
    ch = y.CauHinhMang(cookies_browser="firefox")
    opts = ch.tuy_chon("download")
    assert opts.get("cookiesfrombrowser") == ("firefox", None, None, None) and "cookiefile" not in opts
    assert not ch.hai_nguon_cookie and ch.nguon_cookie_hieu_luc == "trinh_duyet"


def test_chan_doan_va_thanh_ben_bao_ro_hai_nguon(tmp_path):
    cd = t.chan_doan_cookie(_cookie_gia(tmp_path / "c.txt"), cookies_browser="chrome")
    assert cd.hai_nguon
    dong = scan_ui.dong_trang_thai_youtube(cd, None, SAN_SANG)
    canh_bao = [c for m, c in dong if m == "warning" and "CẢ" in c]
    assert canh_bao and "file cookie" in canh_bao[0] and "bỏ qua" in canh_bao[0]
    assert BI_MAT not in repr(dong)


# ---------------------------------------------------------------- 2. phân loại: video riêng lẻ ≠ cả phiên

@pytest.mark.parametrize("tin,loai", [(AUTH, "AGE_RESTRICTED"), (HOI_VIEN, "MEMBERS_ONLY"),
                                      (DANG_NHAP, "AUTH_REQUIRED")])
def test_gioi_han_tuoi_va_hoi_vien_la_loi_tung_video(tin, loai):
    f = t.phan_loai_loi(RuntimeError(tin.format(id="abcdefghijk")))
    assert f.category == getattr(t, loai)
    assert f.auth_related


def test_ba_video_gioi_han_tuoi_lien_tiep_khong_mo_cau_dao_nhung_van_co_tran_hang_loat():
    p = t.PhienYouTube()
    for _ in range(3):
        p.ghi_loi(RuntimeError(AUTH.format(id="abcdefghijk")), "download")
    assert not p.mo, "ba video giới hạn tuổi liên tiếp là chuyện của từng video"
    for _ in range(t.NGUONG_MO[t.AGE_RESTRICTED] - 3):
        p.ghi_loi(RuntimeError(AUTH.format(id="abcdefghijk")), "download")
    assert p.mo and p.ly_do.category == t.AGE_RESTRICTED, "vẫn có trần hàng loạt"
    assert 10 <= t.NGUONG_MO[t.AGE_RESTRICTED] <= 30


def test_ba_loi_dang_nhap_toan_phien_van_mo_cau_dao_o_lan_3():
    p = t.PhienYouTube()
    for i in range(3):
        assert not p.mo, f"mở sớm ở lần {i}"
        p.ghi_loi(RuntimeError(DANG_NHAP.format(id="UCabc")), "listing")
    assert p.mo and p.ly_do.category == t.AUTH_REQUIRED


def test_bot_429_cookie_hong_van_mo_ngay():
    for tin, loai in ((BOT, t.BOT_CHALLENGE), (R429, t.RATE_LIMITED)):
        p = t.PhienYouTube()
        p.ghi_loi(RuntimeError(tin.format(id="abcdefghijk")), "download")
        assert p.mo and p.ly_do.category == loai
    p = t.PhienYouTube()
    p.ghi_loi(y.LoiFileCookie("File cookie «c.txt» sai định dạng Netscape ở dòng 2."), "download")
    assert p.mo and p.ly_do.category == t.COOKIE_INVALID_OR_EXPIRED


# ---------------------------------------------------------------- 3. đồng bộ: tải hết video công khai

def test_dong_bo_bo_qua_video_gioi_han_tuoi_tai_tiep_video_cong_khai(tmp_path, monkeypatch, may):
    kho = tmp_path / "KenhB"
    truoc = _kho_74(kho)
    ids = [_ma(i) for i in range(80)]                   # 74 đã có + 6 mới
    tuoi = {_ma(74), _ma(75), _ma(76)}                  # ba video mới đầu tiên giới hạn tuổi
    ydl = _vá(monkeypatch, YdlKichBan(tai={m: AUTH for m in tuoi}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r = _cs(kho).sync("https://www.youtube.com/@KenhThuGioiHanTuoi")
    assert r["moi"] == 3 and r["bo_qua"] == 74
    assert ydl.dem("tai") == 6, "không tải lại 74 file hợp lệ"
    assert r["trang_thai"] == "MOT_PHAN" and not r["chan_youtube"]
    assert r["so_loi"] == 3 and r["chua_thu"] == 0 and r["gioi_han_tuoi"] == 3
    archive = (kho / "downloaded.txt").read_text(encoding="utf-8")
    assert all(f"youtube {m}" not in archive for m in tuoi), "video lỗi không được ghi là đã tải"
    assert all(f"youtube {_ma(i)}" in archive for i in range(77, 80))
    assert {p.name: (_sha(p), p.stat().st_mtime_ns) for p in kho.glob("*KenhB cu*.opus")} == truoc


def test_bot_check_giua_chung_van_dung_ngay_va_bao_bi_chan(tmp_path, monkeypatch, may):
    kho = tmp_path / "KenhB"
    ids = [_ma(i) for i in range(10)]
    hanh_vi = {_ma(0): AUTH, _ma(1): None, _ma(2): BOT}
    ydl = _vá(monkeypatch, YdlKichBan(tai=hanh_vi, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r = _cs(kho).sync("https://www.youtube.com/@KenhThuGioiHanTuoi")
    assert ydl.dem("tai") == 3, "bot-check: không gửi thêm request"
    assert r["trang_thai"] == "BI_CHAN" and r["chan_youtube"]
    assert r["moi"] == 1 and r["so_loi"] == 2 and r["chua_thu"] == 7


def test_429_giua_chung_van_dung_ngay(tmp_path, monkeypatch, may):
    ids = [_ma(i) for i in range(6)]
    ydl = _vá(monkeypatch, YdlKichBan(tai={_ma(1): R429}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r = _cs(tmp_path / "KenhB").sync("https://www.youtube.com/@KenhThuGioiHanTuoi")
    assert ydl.dem("tai") == 2 and r["trang_thai"] == "BI_CHAN" and r["chua_thu"] == 4


def test_tron_hang_loat_gioi_han_tuoi_dung_va_bao_chua_thu(tmp_path, monkeypatch, may):
    n = t.NGUONG_MO[t.AGE_RESTRICTED] + 5
    ids = [_ma(i) for i in range(n)]
    ydl = _vá(monkeypatch, YdlKichBan(tai={"*": AUTH}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r = _cs(tmp_path / "KenhB").sync("https://www.youtube.com/@KenhThuGioiHanTuoi")
    assert ydl.dem("tai") == t.NGUONG_MO[t.AGE_RESTRICTED]
    assert r["trang_thai"] == "BI_CHAN" and r["chua_thu"] == 5 and r["moi"] == 0


def test_resume_luot_sau_chi_thu_lai_video_con_thieu(tmp_path, monkeypatch, may):
    kho = tmp_path / "KenhB"
    truoc = _kho_74(kho)
    ids = [_ma(i) for i in range(78)]
    _vá(monkeypatch, YdlKichBan(tai={_ma(74): AUTH}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r1 = _cs(kho).sync("https://www.youtube.com/@KenhThuGioiHanTuoi")
    assert r1["moi"] == 3 and r1["so_loi"] == 1
    meta1 = json.loads((kho / "clips_meta.json").read_text(encoding="utf-8"))
    ydl2 = _vá(monkeypatch, YdlKichBan(tai={_ma(74): AUTH}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r2 = _cs(kho).sync("https://www.youtube.com/@KenhThuGioiHanTuoi")
    # Video đã biết bị giới hạn tuổi với CÙNG cách đăng nhập: không gửi lại request vô ích (vẫn báo chưa tải).
    assert [g[1] for g in ydl2.goi if g[0] == "tai"] == []
    assert r2["bo_qua"] == 77 and r2["moi"] == 0 and r2["han_che_bo_qua"] == 1 and r2["trang_thai"] == "MOT_PHAN"
    ydl3 = _vá(monkeypatch, YdlKichBan(tai={_ma(74): AUTH}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r3 = _cs(kho).sync("https://www.youtube.com/@KenhThuGioiHanTuoi", thu_lai_han_che=True)
    assert [g[1] for g in ydl3.goi if g[0] == "tai"] == [_ma(74)], "thử lại: chỉ đúng video còn thiếu"
    assert r3["moi"] == 0 and r3["so_loi"] == 1
    assert {p.name: (_sha(p), p.stat().st_mtime_ns) for p in kho.glob("*KenhB cu*.opus")} == truoc
    meta2 = json.loads((kho / "clips_meta.json").read_text(encoding="utf-8"))
    assert meta2 == meta1, "metadata + dấu xác nhận giữ nguyên"


# ---------------------------------------------------------------- 4. giao diện không báo thành công giả

def _r(**kw):
    r = {"tong": 1263, "moi": 0, "bo_qua": 74, "loi": [], "thu_muc": r"D:\KenhB", "da_huy": False,
         "nghi_hong": [], "da_cach_ly": [], "da_doi_soat": 0, "chan_youtube": "", "youtube": {},
         "trang_thai": "DAY_DU", "so_loi": 0, "chua_thu": 0, "gioi_han_tuoi": 0, "chi_hoi_vien": 0,
         "can_tai": 0, "xac_thuc": {}, "canh_bao_cookie": ""}
    r.update(kw)
    return r


def test_ui_bi_chan_khong_bao_xong_mau_xanh():
    r = _r(trang_thai="BI_CHAN", so_loi=3, chua_thu=1186, can_tai=1189,
           chan_youtube="Đã dừng yêu cầu mới tới YouTube để tránh lặp lỗi đăng nhập (gặp 3 lần liên tiếp): …")
    dong = scan_ui.tom_tat_dong_bo_kenh(r)
    assert dong[0][0] == "error" and "✅" not in dong[0][1] and "Đồng bộ xong" not in dong[0][1]
    chu = " ".join(c for _, c in dong)
    for so in ("74", "0", "3", "1186"):
        assert so in chu
    assert "lặp lỗi đăng nhập" in chu


def test_ui_mot_phan_la_canh_bao_day_du_moi_xanh():
    assert scan_ui.tom_tat_dong_bo_kenh(_r(trang_thai="MOT_PHAN", moi=6, so_loi=3, can_tai=9,
                                           gioi_han_tuoi=3))[0][0] == "warning"
    dong = scan_ui.tom_tat_dong_bo_kenh(_r(trang_thai="DAY_DU", moi=5, can_tai=5))
    assert dong[0][0] == "success"


def test_ket_qua_dong_bo_co_trang_thai_va_luot_xong_khong_noi_xong_khi_bi_chan(tmp_path, monkeypatch, may):
    ids = [_ma(i) for i in range(5)]
    _vá(monkeypatch, YdlKichBan(tai={"*": BOT}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    tien_do = []
    r = _cs(tmp_path / "KenhB").sync("https://www.youtube.com/@KenhThuGioiHanTuoi",
                                   progress=lambda p, m: tien_do.append(m))
    assert r["trang_thai"] == "BI_CHAN"
    assert "Đồng bộ xong." not in tien_do[-1]


# ---------------------------------------------------------------- 5. trạng thái đăng nhập + không rò rỉ

def test_trang_thai_xac_thuc_phan_biet_cau_hinh_voi_da_xac_minh(tmp_path):
    p = t.PhienYouTube()
    assert p.trang_thai_dang_nhap(co_cookie=False)[0] == "KHONG_COOKIE"
    assert p.trang_thai_dang_nhap(co_cookie=True)[0] == "CHUA_XAC_MINH"
    p.ghi_cookie_tai_khoan(True)
    assert p.trang_thai_dang_nhap(co_cookie=True)[0] == "CHUA_XAC_MINH", "chưa có thao tác thành công"
    p.ghi_thanh_cong("download")
    p.ghi_ket_qua_co_cookie({"id": "x", "availability": "public"})
    assert p.trang_thai_dang_nhap(co_cookie=True)[0] == "CHUA_XAC_MINH", "video công khai không cần đăng nhập"
    p.ghi_ket_qua_co_cookie({"id": "y", "availability": "subscriber_only"})
    assert p.trang_thai_dang_nhap(co_cookie=True)[0] == "DA_XAC_MINH"
    p.ghi_cookie_khong_hop_le()
    assert p.trang_thai_dang_nhap(co_cookie=True)[0] == "BI_TU_CHOI"
    q = t.PhienYouTube()
    q.ghi_cookie_tai_khoan(False)
    q.ghi_thanh_cong("download")
    assert q.trang_thai_dang_nhap(co_cookie=True)[0] == "KHONG_CO_COOKIE_DANG_NHAP"


def test_nhan_dien_cookie_tai_khoan_chi_theo_ten():
    class Jar(list):
        pass

    class C:
        def __init__(self, name, domain=".youtube.com", value=BI_MAT):
            self.name, self.domain, self.value = name, domain, value

    class Ydl:
        def __init__(self, ten):
            self.cookiejar = Jar(C(n) for n in ten)
    assert y.co_cookie_tai_khoan(Ydl(["LOGIN_INFO", "SAPISID", "PREF"])) is True
    assert y.co_cookie_tai_khoan(Ydl(["PREF", "VISITOR_INFO1_LIVE"])) is False
    assert y.co_cookie_tai_khoan(object()) is None

    class YdlMien:
        def __init__(self, mien):
            self.cookiejar = Jar(C(n, mien) for n in ("LOGIN_INFO", "SAPISID"))
    # Miền phải THUỘC youtube.com — không chỉ trùng đuôi chuỗi của một miền khác.
    for mien in (".evilyoutube.com", "notyoutube.com", "youtube.com.evil.example", ".youtube.co"):
        assert y.co_cookie_tai_khoan(YdlMien(mien)) is False, mien
    for mien in (".youtube.com", "youtube.com", "www.youtube.com", ".M.YouTube.com"):
        assert y.co_cookie_tai_khoan(YdlMien(mien)) is True, mien


def test_dong_bo_co_cookie_khong_ro_ri_gia_tri(tmp_path, monkeypatch, may, caplog):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"), cookies_browser="chrome")
    ids = [_ma(i) for i in range(4)]
    _vá(monkeypatch, YdlKichBan(tai={_ma(0): AUTH, _ma(1): HOI_VIEN}, liet_ke=lambda _p, _u: _danh_sach(ids)))
    caplog.set_level("DEBUG")
    r = _cs(tmp_path / "KenhB", ch).sync("https://www.youtube.com/@KenhThuGioiHanTuoi")
    assert r["moi"] == 2 and r["gioi_han_tuoi"] == 1 and r["chi_hoi_vien"] == 1
    assert r["canh_bao_cookie"] and "file cookie" in r["canh_bao_cookie"]
    assert r["xac_thuc"].get("nguon") == "file"
    toan_bo = json.dumps(r, ensure_ascii=False, default=str) + caplog.text
    assert BI_MAT not in toan_bo
    assert BI_MAT not in " ".join(c for _, c in scan_ui.tom_tat_dong_bo_kenh(r))


# ---------------------------------------------------------------- 6. kho vân tay độc lập

def _ghi_kho(path, ten):
    ht = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
    for n in ten:
        ht.store(str(n), [(i % 16, i % 16) for i in range(5)])
    with gzip.open(path, "wb") as f:
        pickle.dump(ht, f)


def _eng(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e._cap_nhat_snapshot_sau_build = lambda *a: []
    return e


def test_bo_sung_thu_muc_khac_vao_kho_dang_co_van_tay_bi_chan(tmp_path):
    e = _eng(tmp_path)
    sml = tmp_path / "Kho_SML"
    sml.mkdir()
    (sml / "sml1.opus").write_bytes(b"audio sml")
    e.add_kho("SML", str(sml))
    _ghi_kho(e.db_file, [str(sml / "sml1.opus")])
    kenh_b = tmp_path / "KenhB"
    kenh_b.mkdir()
    (kenh_b / "20240101 - KenhB [j0000000001].opus").write_bytes(b"audio kenh_b")
    khos = Path(e.data_dir) / "khos.json"
    truoc = (_sha(khos), _sha(e.db_file))
    with pytest.raises(RuntimeError, match="SML") as ei:
        e.build_database(str(kenh_b), "add")
    assert "kho riêng" in str(ei.value) or "Tạo kho" in str(ei.value)
    assert (_sha(khos), _sha(e.db_file)) == truoc, "không ghi gì vào kho SML"


def test_dong_bo_kenh_khong_dung_kho_van_tay(tmp_path, monkeypatch, may):
    data = tmp_path / "data"
    data.mkdir()
    (data / "khos.json").write_text(json.dumps({"dang_dung": "SML", "danh_sach": [
        {"ten": "SML", "thu_muc": str(tmp_path / "Kho_SML"), "db": "kho_SML.pklz"}]}), encoding="utf-8")
    _ghi_kho(data / "kho_SML.pklz", ["sml1.opus"])
    truoc = {p.name: _sha(p) for p in data.iterdir()}
    ids = [_ma(i) for i in range(3)]
    _vá(monkeypatch, YdlKichBan(liet_ke=lambda _p, _u: _danh_sach(ids)))
    r = _cs(tmp_path / "KenhB").sync("https://www.youtube.com/@KenhThuGioiHanTuoi")
    assert r["moi"] == 3
    assert {p.name: _sha(p) for p in data.iterdir()} == truoc


def test_huong_dan_sau_dong_bo_khong_xui_nap_vao_kho_khac():
    dong = scan_ui.huong_dan_kho_sau_dong_bo(r"D:\KenhB", "SML", r"E:\KhoThu\SML")
    assert dong[0] == "warning" and "SML" in dong[1] and "Tạo kho" in dong[1]
    dung = scan_ui.huong_dan_kho_sau_dong_bo(r"D:\KenhB", "KenhB", "D:\\KenhB\\")
    assert dung[0] == "info" and "Bổ sung clip mới vào kho" in dung[1]


# ================================================================ PR #8 vòng 2 (review 15/10/2026)
# ---------------------------------------------------------------- 7. kho CŨ: sổ đăng ký chưa ghi thư mục nguồn

URL_KENH = "https://www.youtube.com/@KenhThuGioiHanTuoi"


def _anh_chup(*thu_muc) -> dict:
    """sha256 + mtime của MỌI file (đệ quy), trừ file khoá tác vụ — chứng minh không ghi gì."""
    ra = {}
    for goc in thu_muc:
        for p in sorted(Path(goc).rglob("*")):
            if p.is_file() and not p.name.endswith(".lock"):
                ra[str(p)] = (_sha(p), p.stat().st_mtime_ns)
    return ra


def _kho_cu_chua_ghi_thu_muc(tmp_path, so_clip: int = 300):
    """Kho «SML» kiểu cũ: `thu_muc` RỖNG trong sổ; vân tay hợp lệ `so_clip` clip (đường dẫn tuyệt đối) ở thư mục nguồn
    cũ. File nguồn có trước file kho (không bị coi là «file đã thay sau lần dựng»)."""
    nguon = tmp_path / "Nguon_SML_cu"
    nguon.mkdir()
    cu = time.time() - 3600
    for i in range(so_clip):
        p = nguon / f"sml{i:03d}.opus"
        p.write_bytes(b"audio sml " + str(i).encode())
        os.utime(p, (cu, cu))
    data = tmp_path / "data"
    data.mkdir()
    (data / "khos.json").write_text(json.dumps({"dang_dung": "SML", "danh_sach": [
        {"ten": "SML", "thu_muc": "", "db": "kho_SML.pklz"}]}), encoding="utf-8")
    _ghi_kho(data / "kho_SML.pklz", [str(nguon / f"sml{i:03d}.opus") for i in range(so_clip)])
    e = _eng(tmp_path)
    assert e.kho_dang_dung == "SML" and not (e.kho_thu_muc or "").strip()
    assert len(e._doc_danh_sach_clip(e.db_file)) == so_clip
    return e, nguon


def _thu_muc_kenh_b(tmp_path) -> Path:
    kenh_b = tmp_path / "KenhB"
    kenh_b.mkdir()
    for i in range(3):
        (kenh_b / f"20240101 - KenhB {i} [{_ma(i)}].opus").write_bytes(b"audio kenh b " + str(i).encode())
    return kenh_b


def test_kho_cu_chua_ghi_thu_muc_bo_sung_thu_muc_khac_bi_chan_truoc_moi_ghi(tmp_path):
    e, nguon = _kho_cu_chua_ghi_thu_muc(tmp_path, so_clip=300)
    kenh_b = _thu_muc_kenh_b(tmp_path)
    truoc = _anh_chup(tmp_path / "data", kenh_b, nguon)
    with pytest.raises(RuntimeError, match="SML") as ei:
        e.build_database(str(kenh_b), "add")
    assert "nguồn" in str(ei.value) and "Tạo kho mới" in str(ei.value)
    assert _anh_chup(tmp_path / "data", kenh_b, nguon) == truoc, "không đổi vân tay, sổ kho hay metadata"


def test_kho_cu_khong_nhan_thu_muc_cha_bao_ca_nguon_khac(tmp_path):
    """Thư mục CHA chứa cả nguồn cũ lẫn nguồn khác: không được coi là nguồn của kho (sẽ trộn KenhB vào SML)."""
    e, nguon = _kho_cu_chua_ghi_thu_muc(tmp_path, so_clip=5)
    kenh_b = _thu_muc_kenh_b(tmp_path)
    truoc = _anh_chup(tmp_path / "data", kenh_b, nguon)
    with pytest.raises(RuntimeError, match="nguồn"):
        e.build_database(str(tmp_path), "add")
    assert _anh_chup(tmp_path / "data", kenh_b, nguon) == truoc


def test_kho_cu_bo_sung_dung_thu_muc_nguon_suy_tu_van_tay_thi_gan_thu_muc(tmp_path):
    """Đối chứng dương: thư mục chứa ĐÚNG các clip đã có vân tay (đường dẫn lưu trong kho) = nguồn đã xác nhận."""
    e, nguon = _kho_cu_chua_ghi_thu_muc(tmp_path, so_clip=5)
    db_truoc = (_sha(e.db_file), Path(e.db_file).stat().st_mtime_ns)
    kq = e.build_database(str(nguon), "add")
    assert kq["thanh_cong"] == 0 and kq["bo_qua"] == 5
    assert (_sha(e.db_file), Path(e.db_file).stat().st_mtime_ns) == db_truoc, "vân tay không đổi"
    so = json.loads((tmp_path / "data" / "khos.json").read_text(encoding="utf-8"))
    assert so["danh_sach"][0]["thu_muc"] == str(nguon)


def test_canh_bao_tao_lai_kho_khi_thu_muc_khac_nguon_can_xac_nhan():
    khac = scan_ui.canh_bao_nguon_kho(r"D:\KenhB", "SML", r"E:\KhoThu\SML", 779)
    assert khac[0] == "warning" and khac[2] is True
    assert "Tạo lại kho từ đầu" in khac[1] and "779" in khac[1] and "THAY" in khac[1]
    cu = scan_ui.canh_bao_nguon_kho(r"D:\KenhB", "SML", "", 300, r"E:\Nguon_SML_cu")
    assert cu[0] == "warning" and cu[2] is True and "chưa ghi thư mục nguồn" in cu[1]
    dung_cu = scan_ui.canh_bao_nguon_kho("E:\\Nguon_SML_cu\\", "SML", "", 300, r"E:\Nguon_SML_cu")
    assert dung_cu[0] == "info" and dung_cu[2] is False
    assert scan_ui.canh_bao_nguon_kho("E:\\KhoThu\\SML\\", "SML", r"E:\KhoThu\SML", 779) is None
    assert scan_ui.canh_bao_nguon_kho(r"D:\KenhB", "SML", r"E:\KhoThu\SML", 0) is None, "kho chưa có vân tay"


def test_nut_tao_lai_kho_khoa_den_khi_xac_nhan_thay_vay_tay(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    sml = tmp_path / "Kho_SML"
    sml.mkdir()
    (data / "khos.json").write_text(json.dumps({"dang_dung": "SML", "danh_sach": [
        {"ten": "SML", "thu_muc": str(sml), "db": "kho_SML.pklz"}]}), encoding="utf-8")
    _ghi_kho(data / "kho_SML.pklz", [str(sml / f"sml{i}.opus") for i in range(4)])
    kenh_b = _thu_muc_kenh_b(tmp_path)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    assert not at.exception

    def nut_tao_lai():
        return next(b for b in at.button if b.label == "🔄 Tạo lại kho từ đầu")

    assert not nut_tao_lai().disabled, "cùng thư mục nguồn: không cần xác nhận thêm"
    o = next(x for x in at.text_input if x.label == "Đường dẫn thư mục chứa video gốc của kho này")
    o.set_value(str(kenh_b)).run()
    assert not at.exception
    assert nut_tao_lai().disabled, "thư mục khác nguồn: «Tạo lại» thay toàn bộ vân tay — phải xác nhận trước"
    assert any("THAY" in w.value and "Tạo lại kho từ đầu" in w.value for w in at.warning)
    xn = next(c for c in at.checkbox if c.label.startswith("Tôi hiểu"))
    xn.check().run()
    assert not nut_tao_lai().disabled


# ---------------------------------------------------------------- 8. bằng chứng đăng nhập: cookie đã nạp ≠ YouTube nhận
class _YdlCookieGia(YdlKichBan):
    """yt-dlp giả có hũ cookie (CHỈ tên + miền; giá trị giả) và trường `availability` của video tải được."""

    def __init__(self, *a, ten_cookie=("LOGIN_INFO", "SAPISID"), availability="public", **k):
        super().__init__(*a, **k)
        self.ten_cookie, self.availability = tuple(ten_cookie), availability

    def __call__(self, opts):
        s = super().__call__(opts)
        if "cookiefile" in opts or "cookiesfrombrowser" in opts:
            s.cookiejar = [type("C", (), {"name": n, "domain": ".youtube.com", "value": BI_MAT})()
                           for n in self.ten_cookie]
        goc = s.extract_info

        def extract_info(url, download=False):
            info = goc(url, download=download)
            if download and isinstance(info, dict):
                info = {**info, "availability": self.availability}
            return info
        s.extract_info = extract_info
        return s


def test_cookie_co_ten_dang_nhap_va_video_cong_khai_thanh_cong_van_chua_xac_minh(tmp_path, monkeypatch, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    ids = [_ma(i) for i in range(3)]
    _vá(monkeypatch, _YdlCookieGia(liet_ke=lambda _p, _u: _danh_sach(ids)))
    r = _cs(tmp_path / "KenhB", ch).sync(URL_KENH)
    assert r["moi"] == 3 and r["trang_thai"] == "DAY_DU"
    xt = r["xac_thuc"]
    assert xt["trang_thai"] == "CHUA_XAC_MINH", "tải được video công khai không chứng minh YouTube nhận tài khoản"
    assert xt["cookie_tai_khoan_da_nap"] is True and xt["thao_tac_thanh_cong"] >= 3
    assert xt["youtube_xac_nhan_tai_khoan"] is False
    assert BI_MAT not in json.dumps(r, ensure_ascii=False, default=str)


@pytest.mark.parametrize("availability,mong", [
    ("public", "CHUA_XAC_MINH"), ("unlisted", "CHUA_XAC_MINH"), (None, "CHUA_XAC_MINH"),
    # Giới hạn tuổi: yt-dlp tự thêm client web_embedded vượt được cổng tuổi của một số video KHÔNG cần đăng nhập
    # (`extractor/youtube/_video.py`) → tải được video 18+ chưa chứng minh đăng nhập.
    ("needs_auth", "CHUA_XAC_MINH"),
    ("subscriber_only", "DA_XAC_MINH"), ("premium_only", "DA_XAC_MINH")])
def test_chi_noi_dung_bat_buoc_tai_khoan_moi_la_bang_chung(tmp_path, monkeypatch, may, availability, mong):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    _vá(monkeypatch, _YdlCookieGia(availability=availability, liet_ke=lambda _p, _u: _danh_sach([_ma(0)])))
    r = _cs(tmp_path / "KenhB", ch).sync(URL_KENH)
    assert r["xac_thuc"]["trang_thai"] == mong


def test_noi_dung_hoi_vien_tai_duoc_nhung_khong_co_cookie_tai_khoan_thi_khong_xac_minh(tmp_path, monkeypatch, may):
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    _vá(monkeypatch, _YdlCookieGia(ten_cookie=("PREF",), availability="subscriber_only",
                                   liet_ke=lambda _p, _u: _danh_sach([_ma(0)])))
    r = _cs(tmp_path / "KenhB", ch).sync(URL_KENH)
    assert r["xac_thuc"]["trang_thai"] == "KHONG_CO_COOKIE_DANG_NHAP"


# ---------------------------------------------------------------- 9. tiếp tục có giới hạn sau video bị hạn chế

def test_25_video_gioi_han_tuoi_lien_tiep_luot_sau_tien_toi_video_cong_khai(tmp_path, monkeypatch, may):
    kho = tmp_path / "KenhB"
    ids = [_ma(i) for i in range(28)]                  # 25 giới hạn tuổi liên tiếp, rồi 3 công khai
    tuoi = {m: AUTH for m in ids[:25]}
    nguong = t.NGUONG_MO[t.AGE_RESTRICTED]
    assert nguong < 25

    ydl1 = _vá(monkeypatch, YdlKichBan(tai=tuoi, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r1 = _cs(kho).sync(URL_KENH)
    assert ydl1.dem("tai") == nguong and r1["trang_thai"] == "BI_CHAN" and r1["moi"] == 0

    ydl2 = _vá(monkeypatch, YdlKichBan(tai=tuoi, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r2 = _cs(kho).sync(URL_KENH)
    assert [g[1] for g in ydl2.goi if g[0] == "tai"] == ids[nguong:], \
        "lượt 2 không lặp lại đúng 20 lỗi đầu: bỏ qua video đã biết bị hạn chế, tiến tới phần còn lại"
    assert r2["moi"] == 3 and r2["trang_thai"] == "MOT_PHAN" and not r2["chan_youtube"]
    assert r2["han_che_bo_qua"] == nguong and r2["so_loi"] == 25 - nguong and r2["chua_thu"] == 0

    ydl3 = _vá(monkeypatch, YdlKichBan(tai=tuoi, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r3 = _cs(kho).sync(URL_KENH)
    assert ydl3.dem("tai") == 0, "lượt 3: không gửi request tải nào cho video đã biết bị hạn chế"
    assert r3["moi"] == 0 and r3["han_che_bo_qua"] == 25 and r3["trang_thai"] == "MOT_PHAN"
    dong = scan_ui.tom_tat_dong_bo_kenh(r3)
    assert dong[0][0] == "warning" and "bị hạn chế (chưa tải) **25**" in dong[0][1]
    assert any(m == "warning" and "25 video bị hạn chế" in c and "CHƯA tải" in c and "Thử lại cả video bị hạn chế" in c
               for m, c in dong[1:]), "video bị hạn chế vẫn được báo là CHƯA tải + cách thử lại"

    archive = (kho / "downloaded.txt").read_text(encoding="utf-8")
    assert all(f"youtube {m}" not in archive for m in ids[:25]), "không ghi giả video bị hạn chế vào downloaded.txt"
    assert all(f"youtube {m}" in archive for m in ids[25:])
    meta = json.loads((kho / "clips_meta.json").read_text(encoding="utf-8"))
    assert {v["id"] for v in meta.values()} == set(ids[25:])


def test_thu_lai_han_che_theo_yeu_cau_hoac_khi_doi_cach_dang_nhap_van_co_tran(tmp_path, monkeypatch, may):
    kho = tmp_path / "KenhB"
    ids = [_ma(i) for i in range(25)]
    tuoi = {m: AUTH for m in ids}
    nguong = t.NGUONG_MO[t.AGE_RESTRICTED]
    _vá(monkeypatch, YdlKichBan(tai=tuoi, liet_ke=lambda _p, _u: _danh_sach(ids)))
    _cs(kho).sync(URL_KENH)                                       # ghi sổ: 20 video đầu bị giới hạn tuổi

    ydl = _vá(monkeypatch, YdlKichBan(tai=tuoi, liet_ke=lambda _p, _u: _danh_sach(ids)))
    r = _cs(kho).sync(URL_KENH, thu_lai_han_che=True)
    tai = [g[1] for g in ydl.goi if g[0] == "tai"]
    assert tai[:5] == ids[nguong:], "video CHƯA biết bị hạn chế được thử trước"
    assert len(tai) == nguong and r["trang_thai"] == "BI_CHAN", "thử lại vẫn dừng ở trần hàng loạt"

    # Đổi cách đăng nhập (thêm cookie, máy có Node + EJS): tự thử lại, không cần đánh dấu.
    ch = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path / "c.txt"))
    ydl2 = _vá(monkeypatch, YdlKichBan(liet_ke=lambda _p, _u: _danh_sach(ids)))
    r2 = _cs(kho, ch).sync(URL_KENH)
    assert ydl2.dem("tai") == 25 and r2["moi"] == 25 and r2["han_che_bo_qua"] == 0 and r2["trang_thai"] == "DAY_DU"
    so = json.loads((kho / channel.TEP_HAN_CHE).read_text(encoding="utf-8"))
    assert so["video"] == {}, "video đã tải được thì gỡ khỏi sổ hạn chế"


def test_so_han_che_chi_ghi_tuoi_hoi_vien_khong_ghi_bot_check(tmp_path, monkeypatch, may):
    kho = tmp_path / "KenhB"
    ids = [_ma(i) for i in range(5)]
    _vá(monkeypatch, YdlKichBan(tai={_ma(0): AUTH, _ma(1): HOI_VIEN, _ma(2): BOT},
                                liet_ke=lambda _p, _u: _danh_sach(ids)))
    r = _cs(kho).sync(URL_KENH)
    assert r["trang_thai"] == "BI_CHAN" and r["chua_thu"] == 2, "bot-check vẫn dừng NGAY"
    so = json.loads((kho / channel.TEP_HAN_CHE).read_text(encoding="utf-8"))
    assert set(so["video"]) == {_ma(0), _ma(1)}
    assert {v["loai"] for v in so["video"].values()} == {"AGE_RESTRICTED", "MEMBERS_ONLY"}
    assert BI_MAT not in json.dumps(so, ensure_ascii=False)
    # Lượt sau: video bot-check (_ma(2)) và hai video chưa thử vẫn được thử; hai video hạn chế thì không.
    ydl = _vá(monkeypatch, YdlKichBan(liet_ke=lambda _p, _u: _danh_sach(ids)))
    r2 = _cs(kho).sync(URL_KENH)
    assert [g[1] for g in ydl.goi if g[0] == "tai"] == ids[2:] and r2["moi"] == 3 and r2["han_che_bo_qua"] == 2
