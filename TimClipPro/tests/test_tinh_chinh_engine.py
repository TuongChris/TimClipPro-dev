# -*- coding: utf-8 -*-
"""P-8 việc 1 — ỐNG NỐI của bước «tinh chỉnh mốc từng giây» trong engine (thuật toán ở tinh_chinh_moc.py, có test riêng).

Bước này chạy SAU khi đã chọn kết quả và KHÔNG được đổi bất cứ điều gì engine đã quyết: dòng, số, trạng thái, ghi chú,
chữ ký chính sách, lịch sử, lời gọi media. Lỗi/huỷ của nó chỉ thành «chưa tinh chỉnh» — một video đã tìm thấy không
được thành lỗi vì bước phụ. Module thật được thay bằng bản giả (không FFmpeg) để kiểm đúng phần ống nối.
"""

import dataclasses
import json
import os
import sys
import time
import types

import pytest

import engine
from engine import TRUONG_CHINH_SACH, Engine, Match, ScanResult, chu_ky_chinh_sach
from golden_quet import GOLDEN_DIR, KICH_BAN, chay, chuan_hoa_ket_qua
from toc_do_khop import ma_he_so

CHUA, DA = "chua_tinh_chinh", "da_tinh_chinh"


def _module_gia(goi: list, hanh_vi=None):
    """``tinh_chinh_moc`` giả: ghi lại lời gọi, trả một đoạn cố định (hoặc chạy ``hanh_vi``)."""
    mod = types.ModuleType("tinh_chinh_moc")
    mod.CHUA, mod.DA = CHUA, DA

    def tinh_chinh_dong(clip, video, neo, vung_khop_s, end_s, *, pham_vi_s=None, kiem_huy=None, han_chot=None):
        goi.append({"clip": clip, "video": video, "neo": tuple(neo), "vung": (vung_khop_s, end_s),
                    "pham_vi_s": pham_vi_s, "han_chot": han_chot})
        if hanh_vi is not None:
            return hanh_vi(kiem_huy)
        return {"phien_ban": 1, "trang_thai": DA, "ly_do": "",
                "doan": [{"video_tu": vung_khop_s, "video_den": end_s, "clip_tu": 0.0, "clip_den": end_s - vung_khop_s,
                          "k": 1.0, "tuong_dong_tb": 99.0, "tuong_dong_min": 90.0, "cach_tim_mep": ["bac_thang"] * 2}],
                "cho_cat": [], "ho_so": [[vung_khop_s, 99.0]], "nguong_pct": 50.0, "nen_p99_pct": 20.0,
                "cham_gioi_han": False, "thoi_gian_s": 0.0}

    mod.tinh_chinh_dong = tinh_chinh_dong
    return mod


def _bat(kb):
    return dataclasses.replace(kb, cau_hinh={**kb.cau_hinh, "tinh_chinh_moc": True})


def test_tuy_chon_tat_mac_dinh_va_khong_thuoc_chinh_sach_nhan_dien():
    assert engine.Config().tinh_chinh_moc is False
    assert "tinh_chinh_moc" not in TRUONG_CHINH_SACH
    assert chu_ky_chinh_sach(engine.Config()) == chu_ky_chinh_sach(engine.Config(tinh_chinh_moc=True))


@pytest.mark.parametrize("kb", KICH_BAN, ids=[k.ten for k in KICH_BAN])
def test_bat_tinh_chinh_khong_doi_ket_qua_lich_su_hay_loi_goi_media(kb, tmp_path, monkeypatch):
    """Cả 28 kịch bản golden: bật tinh chỉnh (module giả luôn được gọi) thì kết quả, lịch sử và CHUỖI LỜI GỌI media y
    hệt golden; chỉ tiến độ có thêm dòng «Tinh chỉnh…». Mỗi dòng đã chọn của lượt «ok» có đúng một mục tinh chỉnh."""
    goi: list = []
    monkeypatch.setitem(sys.modules, "tinh_chinh_moc", _module_gia(goi))
    monkeypatch.setattr(Engine, "_ly_do_khong_tinh_chinh", lambda self, m: "")
    kq, e, mt, _ = chay(_bat(kb), tmp_path, monkeypatch)
    with open(os.path.join(GOLDEN_DIR, f"{kb.ten}.json"), encoding="utf-8") as f:
        golden = json.load(f)
    with e._db() as c:
        jobs = [dict(r) for r in c.execute("SELECT * FROM jobs ORDER BY id").fetchall()]
        rows = [dict(r) for r in c.execute("SELECT * FROM matches ORDER BY job_id, id").fetchall()]
    for j in jobs:
        j.pop("created_at", None)
        j["note"] = mt._rut_gon(j.get("note"))
        j["source_ref"] = mt._rut_gon(j.get("source_ref"))
    ghi = json.loads(json.dumps({"nhat_ky": mt.nhat_ky, "ket_qua": chuan_hoa_ket_qua(kq, mt._rut_gon),
                                 "lich_su": {"jobs": jobs, "matches": rows}}, default=str))
    from golden_quet import _lam_tron
    ghi = _lam_tron(ghi)
    for phan in ("nhat_ky", "ket_qua", "lich_su"):
        assert ghi[phan] == golden[phan], phan
    if kq.status == "ok" and kq.matches:
        assert [x["clip"] for x in kq.tinh_chinh] == [m.clip for m in kq.matches]
        # YouTube tải một phần rồi tải nốt: lượt đầu cũng tinh chỉnh (shortcut ghi ở engine) — các lời gọi CUỐI
        # phải đúng các dòng cuối cùng, theo thứ tự.
        assert [g["clip"] for g in goi[-len(kq.matches):]] == [m.duong_dan_kho for m in kq.matches]
    else:
        assert kq.tinh_chinh == [] and goi == []


def _mot_kich_ban(ten="file_ngan_top5"):
    return next(k for k in KICH_BAN if k.ten == ten)


def test_loi_trong_buoc_tinh_chinh_chi_thanh_chua_tinh_chinh(tmp_path, monkeypatch):
    kb = _mot_kich_ban()
    kq0, *_ = chay(kb, tmp_path / "tat", monkeypatch)

    def no(_kiem_huy):
        raise RuntimeError("FFmpeg giả hỏng")

    monkeypatch.setitem(sys.modules, "tinh_chinh_moc", _module_gia([], no))
    monkeypatch.setattr(Engine, "_ly_do_khong_tinh_chinh", lambda self, m: "")
    kq, *_ = chay(_bat(kb), tmp_path / "bat", monkeypatch)
    assert kq.status == kq0.status == "ok"
    assert kq.note == kq0.note and kq.matches == kq0.matches and kq.matches_loai == kq0.matches_loai
    assert kq.tinh_chinh and all(x["trang_thai"] == CHUA and "FFmpeg giả hỏng" in x["ly_do"] for x in kq.tinh_chinh)


def test_huy_giua_buoc_tinh_chinh_giu_ket_qua_va_co_huy(tmp_path, monkeypatch):
    """Bấm Dừng lúc đang tinh chỉnh: kết quả đã chọn GIỮ NGUYÊN (không thành «Đã hủy» như lỗi quét), các dòng còn lại
    «chưa tinh chỉnh», và cờ huỷ VẪN bật để lô dừng ở video kế tiếp."""
    kb = _mot_kich_ban()
    holder = {}

    def huy(kiem_huy):
        holder["e"].cancel_event.set()
        kiem_huy()
        raise AssertionError("kiem_huy phải ném Cancelled")

    monkeypatch.setitem(sys.modules, "tinh_chinh_moc", _module_gia([], huy))
    monkeypatch.setattr(Engine, "_ly_do_khong_tinh_chinh", lambda self, m: "")
    goc_tao = engine.Engine._tinh_chinh_ket_qua

    def ghi_engine(self, *a, **k):
        holder["e"] = self
        return goc_tao(self, *a, **k)

    monkeypatch.setattr(Engine, "_tinh_chinh_ket_qua", ghi_engine)
    kq, e, *_ = chay(_bat(kb), tmp_path, monkeypatch)
    assert kq.status == "ok" and kq.matches
    assert e.cancel_event.is_set()
    assert [x["trang_thai"] for x in kq.tinh_chinh] == [CHUA] * len(kq.matches)
    assert all("huỷ" in x["ly_do"] for x in kq.tinh_chinh)


def _kq_mot_dong(tmp_path, **truong_match):
    clip = tmp_path / "clip.wav"
    clip.write_bytes(b"x")
    m = Match(clip="clip.wav", start_s=10.0, end_s=70.0, matched_s=60.0, clip_offset_s=0.0, hashes=5000,
              confidence="", vung_khop_s=10.0, duong_dan_kho=str(clip), neo=((10.0, 1.0),), **truong_match)
    return ScanResult(source_name="v", duration_s=100.0, matches=[m], pham_vi_quet_s=100.0)


def _eng(tmp_path):
    return Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))


@pytest.mark.parametrize("truong,chua_trong_ly_do", [
    ({"moc_mo_ho": True}, "Âm thanh lặp"),
    ({"ho": "resample"}, "cao độ"),
])
def test_dong_khong_tinh_chinh_duoc_noi_ro_ly_do(tmp_path, monkeypatch, truong, chua_trong_ly_do):
    goi: list = []
    monkeypatch.setitem(sys.modules, "tinh_chinh_moc", _module_gia(goi))
    e = _eng(tmp_path)
    kq = _kq_mot_dong(tmp_path, **truong)
    video = tmp_path / "video.wav"
    video.write_bytes(b"x")
    e._tinh_chinh_ket_qua(kq, str(video), None, time.monotonic())
    assert goi == []
    assert kq.tinh_chinh[0]["trang_thai"] == CHUA and chua_trong_ly_do in kq.tinh_chinh[0]["ly_do"]


def test_khong_co_file_clip_trong_kho_thi_khong_tinh_chinh(tmp_path, monkeypatch):
    goi: list = []
    monkeypatch.setitem(sys.modules, "tinh_chinh_moc", _module_gia(goi))
    e = _eng(tmp_path)
    kq = _kq_mot_dong(tmp_path)
    os.remove(kq.matches[0].duong_dan_kho)
    e._tinh_chinh_ket_qua(kq, str(tmp_path / "video.wav"), None, time.monotonic())
    assert goi == [] and "clip gốc" in kq.tinh_chinh[0]["ly_do"]


def test_tham_so_goi_module_dung_hop_dong(tmp_path, monkeypatch):
    goi: list = []
    monkeypatch.setitem(sys.modules, "tinh_chinh_moc", _module_gia(goi))
    e = _eng(tmp_path)
    kq = _kq_mot_dong(tmp_path)
    e._tinh_chinh_ket_qua(kq, "video.wav", None, time.monotonic())
    assert goi[0]["neo"] == ((10.0, 1.0),) and goi[0]["vung"] == (10.0, 70.0)
    assert goi[0]["pham_vi_s"] == (0.0, 100.0) and goi[0]["han_chot"] >= time.monotonic() + 25
    assert kq.tinh_chinh[0]["trang_thai"] == DA and kq.tinh_chinh[0]["clip"] == "clip.wav"


def test_het_ngan_sach_thoi_gian_cac_dong_con_lai_chua_tinh_chinh(tmp_path, monkeypatch):
    goi: list = []
    gio = {"t": 1000.0}

    def tre(_kiem_huy):
        gio["t"] += 10_000.0                 # một dòng ăn hết ngân sách
        return {"trang_thai": DA, "ly_do": "", "doan": []}

    monkeypatch.setitem(sys.modules, "tinh_chinh_moc", _module_gia(goi, tre))
    monkeypatch.setattr(engine, "time", types.SimpleNamespace(monotonic=lambda: gio["t"], time=time.time,
                                                              sleep=time.sleep))
    e = _eng(tmp_path)
    kq = _kq_mot_dong(tmp_path)
    kq.matches = kq.matches * 3
    e._tinh_chinh_ket_qua(kq, "video.wav", None, gio["t"])
    assert len(goi) == 1
    assert [x["trang_thai"] for x in kq.tinh_chinh] == [DA, CHUA, CHUA]
    assert "Hết thời gian" in kq.tinh_chinh[1]["ly_do"]


def test_file_dem_duoc_giu_suot_luc_tinh_chinh(tmp_path, monkeypatch):
    """Dọn đệm của tiến trình khác không được xoá file video giữa lúc đang đọc (audit C-9)."""
    e = _eng(tmp_path)
    os.makedirs(e.dl_dir, exist_ok=True)
    video = os.path.join(e.dl_dir, "abcdefghijk.m4a")
    with open(video, "wb") as f:
        f.write(b"x" * 2048)
    thay = {}

    def thu_xoa(_kiem_huy):
        thay["bo_duoc"] = e._bo_file_dem(video)
        return {"trang_thai": DA, "ly_do": "", "doan": []}

    monkeypatch.setitem(sys.modules, "tinh_chinh_moc", _module_gia([], thu_xoa))
    e._tinh_chinh_ket_qua(_kq_mot_dong(tmp_path), video, None, time.monotonic())
    assert thay["bo_duoc"] is False and os.path.exists(video)


# ----------------------------------------------------------------------------------------------- neo / k / họ từ _merge

def _ten_khuc(tmp_path, offset: int, k: float) -> str:
    duoi = "" if k == 1.0 else f"_k{ma_he_so(k)}"
    return str(tmp_path / f"chunk_{offset:07d}{duoi}.wav")


def _khop_tho(e, tmp_path, dong: list, luot_bu: str = "") -> list:
    def chay_lenh(lenh, on_line=None, **kw):
        with open(lenh[lenh.index("--opfile") + 1], "w", encoding="utf-8") as f:
            for khuc, t_q, t_r, dai, so_hash in dong:
                f.write(f"Matched {dai:.1f} s starting at {t_q:.1f} s in {khuc} to time {t_r:.1f} s in reference.opus "
                        f"with {so_hash} of {so_hash * 2} common hashes at rank 0\n")
        return 0, []
    e._run_stream = chay_lenh
    return e._match_chunks(sorted({d[0] for d in dong}), workspace=str(tmp_path), luot_bu=luot_bu)


def _eng_kho(tmp_path):
    e = _eng(tmp_path)
    e.db_clips = lambda **k: [{"ten": "reference.opus", "duong_dan": "reference.opus", "so_hash": 100000}]
    return e


def test_ban_tua_lui_phat_lai_gop_mot_dong_mang_hai_neo(tmp_path):
    """Clip phát tới giây 200 rồi tua lùi 15 s phát tiếp (phản biện H1b): engine gộp MỘT dòng, nhưng bước tinh chỉnh
    phải biết cả hai căn chỉnh — dòng mang hai neo, neo mạnh trước."""
    e = _eng_kho(tmp_path)
    k0 = _ten_khuc(tmp_path, 0, 1.0)
    tho = _khop_tho(e, tmp_path, [(k0, 312.5, 12.5, 175.6, 4500), (k0, 505.7, 190.7, 102.1, 2700)])
    ket = e._merge(tho)
    assert len(ket) == 1
    assert ket[0].neo == ((300.0, 1.0), (315.0, 1.0))
    assert ket[0].he_so == 1.0 and ket[0].ho == ""


def test_nhom_troi_mang_mot_neo_voi_he_so_do_duoc(tmp_path):
    e = _eng_kho(tmp_path)
    toc = 1.02
    dau_clip = 400.0 - 300.0 / toc
    dong = [(_ten_khuc(tmp_path, 0, 1.0), dau_clip + (300.0 + 6.0 * i) / toc, 300.0 + 6.0 * i, 6.0, 60) for i in range(50)]
    m = e._merge(_khop_tho(e, tmp_path, dong))[0]
    assert m.he_so == pytest.approx(1.0 / toc, abs=0.002)
    assert len(m.neo) == 1 and m.neo[0][0] == pytest.approx(dau_clip, abs=0.2)


def test_dong_tu_luot_bu_mang_ho_bien_doi(tmp_path):
    e = _eng_kho(tmp_path)
    k = 0.98
    tho = _khop_tho(e, tmp_path, [(_ten_khuc(tmp_path, 0, k), 700.0, 600.0, 90.0, 3000)], luot_bu=f"k{ma_he_so(k)}_tempo")
    m = e._merge(tho)[0]
    assert m.ho == "tempo" and m.he_so == pytest.approx(k)
    assert m.neo == ((round(k * (700.0 - 600.0), 3), k),)
