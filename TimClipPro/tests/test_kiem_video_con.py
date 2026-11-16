# -*- coding: utf-8 -*-
"""Kiểm video vi phạm đã tìm thấy còn trên YouTube hay đã gỡ — theo dõi kết quả khiếu nại (D-51).

``Engine.video_vi_pham`` (chọn mã, chỉ đọc lịch sử) + ``kiem_video_con`` (đổi trạng thái Data API ra kết quả, sổ JSON).
YouTube Data API GIẢ (tests/youtube_api_gia.py), dữ liệu tổng hợp trong thư mục tạm — không mạng, không khoá thật,
không dữ liệu thật.
"""

import contextlib
import json
import os
import sqlite3

import pytest

import bao_cao_v2
import kiem_video_con as kv
import luu_tru
import truy_cap_youtube as t
import youtube_api as ya
import youtube_api_gia as gia
from conftest import M
from engine import ScanResult

CON = "Còn (công khai)"
KHONG_CON = "Không còn xem được (đã gỡ hoặc riêng tư)"


def _luu(eng, ma, *, ten="Video vi phạm", status="ok", so_khop=1, kenh=None, luc=""):
    """Một lần quét đã lưu; ``kenh=(tên, link)`` → kèm ảnh chụp báo cáo V2 (kênh chỉ nằm trong ảnh chụp)."""
    kq = ScanResult(source_name=ten, source_ref=f"https://www.youtube.com/watch?v={ma}", source_id=ma,
                    duration_s=600.0, status=status, matches=[M() for _ in range(so_khop)])
    if kenh:
        kq.channel_name, kq.channel_url = kenh
        kq.bao_cao = bao_cao_v2.dung_bao_cao(
            kq, thoi_diem_quet="2026-11-01 10:00:00", nguon_loai="youtube", tieu_de=ten, nguon_tieu_de="",
            ly_do_thieu_tieu_de="", ngay_dang=bao_cao_v2.NgayNguon(), goc_theo_clip={}, mo_ta_pham_vi="")
    job_id = eng.save_job(kq, "youtube")
    if luc:
        _sql(eng, "UPDATE jobs SET created_at=? WHERE id=?", luc, job_id)
    return job_id


def _sql(eng, lenh, *tham_so):
    with contextlib.closing(sqlite3.connect(eng.sqlite_file)) as cx, cx:
        cx.execute(lenh, tham_so)


def test_video_vi_pham_toan_lich_su_moi_ma_mot_dong_theo_lan_quet_moi_nhat(engine):
    a, d, c = "vidvipham0A", "vidvipham0D", "vidvipham0C"
    _luu(engine, a, ten="A lần đầu", luc="2026-09-01 08:00:00")
    _luu(engine, "vidloi0000B", status="error")                     # lỗi: không tính dù có dòng khớp
    _luu(engine, "vidamtinh0C", so_khop=0)                          # âm tính
    _luu(engine, "ngan", ten="mã sai")                              # không phải mã YouTube hợp lệ
    _luu(engine, "", ten="file trong máy")                          # không có mã
    _luu(engine, d, ten="D", kenh=("Kênh D", "https://www.youtube.com/channel/UCd"), luc="2026-10-05 09:00:00")
    _luu(engine, c, ten="C luật cũ")                                # không có ảnh chụp V2 → kênh trống
    _luu(engine, a, ten="A mới", kenh=("Kênh A", "https://www.youtube.com/@a"), luc="2026-11-02 10:00:00")
    _luu(engine, a, ten="A lỗi sau đó", status="error")             # lần lỗi mới hơn không đổi dòng của A
    ds = engine.video_vi_pham()
    assert [v["ma"] for v in ds] == [a, c, d], "mỗi mã một dòng, lần quét mới nhất trước"
    assert ds[0] == {"ma": a, "tieu_de": "A mới", "lan_quet_cuoi": "2026-11-02 10:00:00", "so_lan_quet": 2,
                     "kenh_ten": "Kênh A", "kenh_link": "https://www.youtube.com/@a"}
    assert (ds[1]["tieu_de"], ds[1]["so_lan_quet"], ds[1]["kenh_ten"], ds[1]["kenh_link"]) == ("C luật cũ", 1, "", "")
    assert (ds[2]["kenh_ten"], ds[2]["lan_quet_cuoi"]) == ("Kênh D", "2026-10-05 09:00:00")


def test_video_vi_pham_anh_chup_hong_thi_kenh_trong_van_co_dong(engine):
    job_id = _luu(engine, "vidvipham0E", ten="E", kenh=("Kênh E", "https://www.youtube.com/@e"))
    _sql(engine, "UPDATE bao_cao_job SET du_lieu='{hỏng' WHERE job_id=?", job_id)
    assert engine.video_vi_pham() == [{"ma": "vidvipham0E", "tieu_de": "E", "lan_quet_cuoi": engine.list_jobs()[0][
        "created_at"], "so_lan_quet": 1, "kenh_ten": "", "kenh_link": ""}]


# ---------------------------------------------------------------- kiem_video_con: kiểm qua Data API, sổ JSON

def _phien():
    return t.PhienYouTube(ham_cho=lambda giay, ev=None: False)


def test_moi_trang_thai_youtube_doi_ra_ket_qua_dung_nhan(api_youtube_gia, tmp_path):
    cong, an, go, xoa, vang, sap, rieng, la = (f"vidkiemtra{i}" for i in range(8))
    api_youtube_gia.video.update({
        cong: gia.video_gia(cong), an: gia.video_gia(an, privacy="unlisted"),
        go: gia.video_gia(go, upload="rejected"), xoa: gia.video_gia(xoa, privacy="private", upload="deleted"),
        sap: gia.video_gia(sap, live="upcoming"), rieng: gia.video_gia(rieng, privacy="private"),
        la: gia.video_gia(la, privacy="")})
    ids = [cong, an, go, xoa, vang, sap, rieng, la]
    ket = kv.kiem_tra(_phien(), str(tmp_path / "data"), ids)
    assert ket == {cong: CON, an: "Còn (không công khai — ai có link vẫn xem được)",
                   go: "Đã bị gỡ (YouTube từ chối video)", xoa: "Đã bị gỡ (video đã bị xoá)",
                   vang: KHONG_CON, sap: "Còn (đang phát trực tiếp hoặc sắp công chiếu)", rieng: KHONG_CON,
                   la: "Chưa kiểm được — YouTube không cho biết video công khai hay riêng tư"}
    yc = api_youtube_gia.yeu_cau
    assert len(yc) == 1 and yc[0].ids == tuple(ids) and yc[0].part.split(",")[-1] == "status"


def test_lan_dau_khong_con_ghi_mot_lan_roi_giu_lan_cuoi_con_cap_nhat(api_youtube_gia, tmp_path, monkeypatch):
    a, data = "vidkiemtraA", str(tmp_path / "data")
    for luc, con in (("2026-11-01T08:00:00", True), ("2026-11-02T08:00:00", False),
                     ("2026-11-03T08:00:00", False), ("2026-11-04T08:00:00", True)):
        api_youtube_gia.video.clear()
        if con:
            api_youtube_gia.video[a] = gia.video_gia(a)
        monkeypatch.setattr(kv, "_bay_gio", lambda luc=luc: luc)
        kv.kiem_tra(_phien(), data, [a])
    assert kv.doc_so(data) == {a: {"ket_qua": CON, "kiem_luc": "2026-11-04T08:00:00",
                                   "lan_dau_khong_con": "2026-11-02T08:00:00", "lan_cuoi_con": "2026-11-04T08:00:00"}}


def test_het_han_muc_la_chua_kiem_duoc_va_giu_ket_qua_kiem_truoc(api_youtube_gia, tmp_path, monkeypatch):
    a, b, data = "vidkiemtraA", "vidkiemtraB", str(tmp_path / "data")
    api_youtube_gia.video[a] = gia.video_gia(a)
    monkeypatch.setattr(kv, "_bay_gio", lambda: "2026-11-16T10:00:00")
    kv.kiem_tra(_phien(), data, [a])
    api_youtube_gia.kich_ban = [gia.QUOTA]
    monkeypatch.setattr(kv, "_bay_gio", lambda: "2026-11-16T11:00:00")
    ket = kv.kiem_tra(_phien(), data, [a, b])
    het = "Chưa kiểm được — " + t.THONG_BAO_API[t.API_HET_HAN_MUC]
    assert ket == {a: het, b: het} and api_youtube_gia.dem() == 2
    assert kv.doc_so(data) == {
        a: {"ket_qua": CON, "kiem_luc": "2026-11-16T10:00:00", "lan_dau_khong_con": "",
            "lan_cuoi_con": "2026-11-16T10:00:00"},
        b: {"ket_qua": het, "kiem_luc": "2026-11-16T11:00:00", "lan_dau_khong_con": "", "lan_cuoi_con": ""}}


def test_khong_co_khoa_khong_gui_yeu_cau_nao(monkeypatch, tmp_path):
    tp = gia.lap_transport(monkeypatch)
    ket = kv.kiem_tra(_phien(), str(tmp_path / "data"), ["vidkiemtraA"])
    assert ket == {"vidkiemtraA": "Chưa kiểm được — " + ya.LY_DO_CHUA_CO_KHOA} and tp.dem() == 0


def test_ghi_so_nguyen_tu_ghi_hong_thi_ban_cu_con_nguyen(api_youtube_gia, tmp_path, monkeypatch):
    a, data = "vidkiemtraA", tmp_path / "data"
    api_youtube_gia.video[a] = gia.video_gia(a)
    kv.kiem_tra(_phien(), str(data), [a])
    so = data / kv.TEN_FILE
    truoc = so.read_bytes()
    api_youtube_gia.video.clear()                  # lượt sau: video không còn → phải ghi đè sổ
    thay_that = os.replace

    def thay_hong(nguon, dich):
        if os.path.abspath(dich) == str(so):
            raise OSError("ổ đĩa đầy (giả)")
        return thay_that(nguon, dich)

    monkeypatch.setattr(luu_tru.os, "replace", thay_hong)
    with pytest.raises(OSError):
        kv.kiem_tra(_phien(), str(data), [a])
    assert so.read_bytes() == truoc and json.loads(truoc)["video"][a]["ket_qua"] == CON
    assert (data / (kv.TEN_FILE + ".bak")).read_bytes() == truoc and not list(data.glob("*.tmp"))


def test_so_sai_cau_truc_khong_bi_ghi_de(api_youtube_gia, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / kv.TEN_FILE).write_text("[1, 2]", encoding="utf-8")
    api_youtube_gia.video["vidkiemtraA"] = gia.video_gia("vidkiemtraA")
    with pytest.raises(luu_tru.LoiDuLieu):
        kv.kiem_tra(_phien(), str(data), ["vidkiemtraA"])
    assert (data / kv.TEN_FILE).read_text(encoding="utf-8") == "[1, 2]"
    assert kv.doc_so(str(data)) == {} and kv.doc_so(str(tmp_path / "chua_co")) == {}


def test_dong_bang_mot_dong_moi_video_va_dem_ba_nhom():
    def vp(ma, **them):
        return {"ma": ma, "tieu_de": ma, "lan_quet_cuoi": "2026-11-02 10:00:00", "so_lan_quet": 1, "kenh_ten": "",
                "kenh_link": "", **them}

    a, b, c, d = (f"vidkiemtra{x}" for x in "ABCD")
    so = {a: {"ket_qua": CON, "kiem_luc": "2026-11-16T10:00:00", "lan_dau_khong_con": "",
              "lan_cuoi_con": "2026-11-16T10:00:00"},
          b: {"ket_qua": "Đã bị gỡ (video đã bị xoá)", "kiem_luc": "2026-11-16T10:00:00",
              "lan_dau_khong_con": "2026-11-10T09:00:00", "lan_cuoi_con": ""},
          c: {"ket_qua": "Chưa kiểm được — x", "kiem_luc": "2026-11-16T10:00:00", "lan_dau_khong_con": "",
              "lan_cuoi_con": ""}}
    bang = kv.dong_bang([vp(a, tieu_de="A", so_lan_quet=2, kenh_ten="Kênh A", kenh_link="https://www.youtube.com/@a"),
                         vp(b, kenh_link="https://www.youtube.com/channel/UCb"), vp(c), vp(d)], so)
    assert list(bang[0].items()) == [
        ("Video vi phạm", "A"), ("Link", f"https://www.youtube.com/watch?v={a}"), ("Kênh", "Kênh A"),
        ("Lần quét gần nhất", "2026-11-02 10:00:00"), ("Số lần quét", 2), ("Trên YouTube", CON),
        ("Kiểm lúc", "2026-11-16 10:00:00"), ("Lần đầu thấy không còn", "")]
    assert (bang[1]["Kênh"], bang[1]["Lần đầu thấy không còn"]) == ("https://www.youtube.com/channel/UCb",
                                                                    "2026-11-10 09:00:00")
    assert (bang[3]["Trên YouTube"], bang[3]["Kiểm lúc"]) == ("Chưa kiểm", "")
    assert kv.dem(bang) == {"con": 1, "khong_con": 1, "chua": 2}
