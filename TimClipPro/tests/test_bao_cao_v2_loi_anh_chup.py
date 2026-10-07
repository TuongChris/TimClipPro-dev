# -*- coding: utf-8 -*-
"""Báo cáo V2 lỗi/hỏng KHÔNG BAO GIỜ lùi về luật cũ (audit P1-02).

Trước bản sửa, ``None`` mang hai nghĩa: «lượt quét cũ thật» và «lượt quét V2 mà ảnh chụp không
dựng/đọc được». Tái hiện: bộ dựng ảnh chụp ném lỗi → ``bao_cao=None`` → tên lại nối hậu tố cũ,
gửi Sheets KHÔNG nghiêm ngặt; dòng ``bao_cao_job`` có JSON hỏng → bộ đọc trả ``None`` → lịch sử
hiểu là lượt quét cũ. Hợp đồng mới:

* luật cũ thật (không có chính sách V2 / không có dòng ảnh chụp) → luật cũ y nguyên;
* V2 bình thường → V2;
* V2 dựng ảnh chụp lỗi → ``LoiBaoCaoV2(LOI_TAO)`` tường minh, kết quả khớp + lịch sử giữ
  nguyên, dấu lỗi lưu vào ``bao_cao_job``, mọi exporter / Sheets CHẶN;
* V2 ảnh chụp đã lưu hỏng → ``LoiBaoCaoV2(LOI_HONG)``, vẫn hỏng sau khi khởi động lại.

Dữ liệu tổng hợp; không mạng (yt-dlp/gspread giả).
"""
import dataclasses
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import bang_ngang
import bao_cao_v2 as v2
import cli
import common_original as co
import dossier
from engine import Engine
from golden_quet import Dat
from test_bao_cao_v2 import _bc, _kq_ca_that
from test_bao_cao_v2_quet import URL, _B, _the_gioi
from test_truy_cap_youtube_lo import LINK_GIA, _chay_lo, _cong_dem, _eng, _ma, _quet_gia, _url
from watch import MucTheoDoi, WatchList, chay_giam_sat
from ytdlp_gia import YdlKichBan

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
# Thông điệp lỗi giả mang dáng bí mật/URL ký (tên miền .invalid — không bao giờ tồn tại): KHÔNG
# được lọt vào dấu lỗi đã lưu, ghi chú hay nhật ký.
BI_MAT_GIA = "SID=gia-bi-mat-0000 https://media-gia.invalid/videoplayback?sig=GIA"


def _hong_dung(monkeypatch, *, chi_ma=None):
    """Bộ dựng ảnh chụp V2 ném lỗi (cho mọi lượt, hoặc chỉ video ``chi_ma``)."""
    goc = v2.dung_bao_cao

    def gia(kq, **kw):
        if chi_ma is None or kq.source_id == chi_ma:
            raise RuntimeError(BI_MAT_GIA)
        return goc(kq, **kw)

    monkeypatch.setattr(v2, "dung_bao_cao", gia)


def _dem(e, job_id):
    con = sqlite3.connect(e.sqlite_file)
    try:
        return tuple(con.execute(sql, (job_id,)).fetchone()[0] for sql in (
            "SELECT COUNT(*) FROM jobs WHERE id=?",
            "SELECT COUNT(*) FROM matches WHERE job_id=?",
            "SELECT COUNT(*) FROM bao_cao_job WHERE job_id=?"))
    finally:
        con.close()


def _quet_loi(tmp_path, monkeypatch):
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)])
    _hong_dung(monkeypatch)
    return e, e.scan_youtube(URL), hop


def _luu_roi_sua(e, du_lieu, chinh_sach="v2"):
    """Một lượt quét V2 đã lưu, rồi dòng ảnh chụp bị sửa hỏng trực tiếp trong DB."""
    kq = _kq_ca_that()
    kq.bao_cao = _bc(kq)
    job_id = e.save_job(kq, "youtube")
    con = sqlite3.connect(e.sqlite_file)
    try:
        with con:
            con.execute("UPDATE bao_cao_job SET du_lieu=?, chinh_sach=? WHERE job_id=?",
                        (du_lieu, chinh_sach, job_id))
    finally:
        con.close()
    return job_id


def _kq_loi(**them):
    kq = _kq_ca_that(source_name="Video lỗi báo cáo", source_id="vidloi00001",
                     source_ref="https://www.youtube.com/watch?v=vidloi00001", **them)
    kq.bao_cao = v2.LoiBaoCaoV2(v2.LOI_TAO, ngoai_le="RuntimeError")
    return kq


# ---------------------------------------------------------------------------
#  Dựng ảnh chụp lỗi → LỖI V2 tường minh, bằng chứng khớp giữ nguyên
# ---------------------------------------------------------------------------

def test_dung_anh_chup_loi_thanh_loi_v2_tuong_minh(tmp_path, monkeypatch):
    e, kq, _ = _quet_loi(tmp_path, monkeypatch)
    assert kq.status == "ok" and len(kq.matches) == 1          # quét/khớp KHÔNG thành âm tính
    assert kq.bao_cao is not None, "None = luật cũ: lỗi V2 không được mang nghĩa đó"
    assert isinstance(kq.bao_cao, v2.LoiBaoCaoV2)
    assert kq.bao_cao.loai == v2.LOI_TAO and kq.bao_cao.chinh_sach == v2.CHINH_SACH_V2
    assert kq.bao_cao.ngoai_le == "RuntimeError"
    assert "luật cũ" not in kq.note and "báo cáo v2" in kq.note.lower()


def test_loi_dung_van_luu_job_matches_va_dau_loi_v2(tmp_path, monkeypatch):
    e, kq, _ = _quet_loi(tmp_path, monkeypatch)
    assert _dem(e, kq.job_id) == (1, 1, 1)
    doc = e.bao_cao_cua_job(kq.job_id)
    assert isinstance(doc, v2.LoiBaoCaoV2) and doc.loai == v2.LOI_TAO
    assert doc.ngoai_le == "RuntimeError"


def test_dau_loi_da_luu_khong_chua_thong_diep_tho(tmp_path, monkeypatch):
    e, kq, _ = _quet_loi(tmp_path, monkeypatch)
    con = sqlite3.connect(e.sqlite_file)
    try:
        du_lieu = con.execute("SELECT du_lieu FROM bao_cao_job WHERE job_id=?",
                              (kq.job_id,)).fetchone()[0]
        ghi_chu = con.execute("SELECT note FROM jobs WHERE id=?", (kq.job_id,)).fetchone()[0]
    finally:
        con.close()
    lot = [s for s in ("gia-bi-mat", "media-gia", "sig=") for o in (du_lieu, ghi_chu, kq.note)
           if s in (o or "")]
    assert not lot, "dấu lỗi/ghi chú chỉ mang tên lớp ngoại lệ"
    assert json.loads(du_lieu) == {"loi_bao_cao": {"loai": v2.LOI_TAO, "ngoai_le": "RuntimeError"}}


def test_nhat_ky_loi_bao_cao_chi_ghi_ten_loi_va_vi_tri(tmp_path, monkeypatch, caplog):
    import logging

    with caplog.at_level(logging.DEBUG):
        _quet_loi(tmp_path, monkeypatch)
    lot = [r for r in caplog.records
           if any(s in r.getMessage() for s in ("gia-bi-mat", "media-gia", "sig="))
           or (r.exc_info and any(s in str(r.exc_info[1]) for s in ("gia-bi-mat", "sig=")))]
    assert not lot, "nhật ký không được mang thông điệp thô của lỗi"
    assert any("event=report_v2.snapshot_failed" in r.getMessage()
               and "err=RuntimeError" in r.getMessage() for r in caplog.records)


def test_moi_exporter_chan_va_khong_dung_luat_cu(tmp_path, monkeypatch):
    e, kq, hop = _quet_loi(tmp_path, monkeypatch)
    hoi = []

    def resolver(bo_cache=False):
        hoi.append(1)
        return hop["resolver"]

    e.clip_metadata_resolver = resolver
    xuat = {
        "doc": lambda: e.to_rows([kq]),
        "ngang": lambda: e.to_rows_ngang([kq]),
        "csv": lambda: e.export_csv([kq]),
        "csv_ngang": lambda: e.export_csv_ngang([kq]),
        "ho_so": lambda: e.export_ho_so([kq]),
        "sheets_ngang": lambda: e.dong_gui_sheets([kq], dang_ngang=True, an_toan_cu=False),
        "sheets_doc": lambda: e.dong_gui_sheets([kq], dang_ngang=False, an_toan_cu=True),
        "bang_ngang": lambda: bang_ngang.dung_dong_ngang(kq, resolver=hop["resolver"]),
        "dossier": lambda: dossier.dung_ho_so(kq, resolver=hop["resolver"]),
    }
    khong_chan = []
    for ten, f in xuat.items():
        try:
            f()
        except v2.LoiXuatBaoCaoV2:
            continue
        khong_chan.append(ten)
    assert khong_chan == [], "mọi exporter phải chặn (không lùi về luật cũ)"
    assert hoi == [], "resolver hiện tại (luật cũ) không được hỏi cho kết quả V2"
    sinh = os.listdir(e.out_dir) if os.path.isdir(e.out_dir) else []
    assert sinh == [], "không để lại file CSV/MD dở dang"


def test_loi_khi_chuan_bi_video_goc_cung_la_loi_v2_khong_mat_ket_qua(tmp_path, monkeypatch):
    def no(*a, **k):
        raise KeyError("metadata hỏng (giả lập)")

    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)])
    monkeypatch.setattr(v2, "goc_tu_metadata", no)
    kq = e.scan_youtube(URL)
    assert kq.status == "ok" and kq.matches
    assert isinstance(kq.bao_cao, v2.LoiBaoCaoV2) and kq.bao_cao.ngoai_le == "KeyError"
    assert _dem(e, kq.job_id) == (1, 1, 1)


# ---------------------------------------------------------------------------
#  Ảnh chụp đã lưu bị hỏng → V2 HỎNG (không phải luật cũ), kể cả sau khởi động lại
# ---------------------------------------------------------------------------

def _anh_chup_hop_le(**sua):
    d = _bc().to_dict()
    d.update(sua)
    return json.dumps(d, ensure_ascii=False)


@pytest.mark.parametrize("du_lieu, chinh_sach", [
    ("{hỏng", "v2"),                                                   # JSON hỏng
    ("[]", "v2"),                                                      # không phải object
    ('{"chinh_sach": "v2", "phien_ban_anh_chup": 1}', "v2"),           # cụt — thiếu trường
    (_anh_chup_hop_le(phien_ban_anh_chup=99), "v2"),                   # phiên bản lạ
    (_anh_chup_hop_le(), "v9"),                                        # chính sách lạ ở cột
    ('{"loi_bao_cao": "x"}', "v2"),                                    # dấu lỗi sai dạng
], ids=["json_hong", "mang", "cut", "phien_ban_la", "chinh_sach_la", "dau_loi_sai_dang"])
def test_anh_chup_luu_hong_la_v2_hong_khong_phai_luat_cu(engine, du_lieu, chinh_sach):
    job_id = _luu_roi_sua(engine, du_lieu, chinh_sach)
    bc = engine.bao_cao_cua_job(job_id)
    assert bc is not None, "có dòng ảnh chụp = lượt quét V2, không bao giờ là luật cũ"
    assert isinstance(bc, v2.LoiBaoCaoV2) and bc.loai == v2.LOI_HONG
    for ngang in (True, False):
        with pytest.raises(v2.LoiXuatBaoCaoV2):
            engine.dong_bao_cao_job(job_id, dang_ngang=ngang)


def test_khoi_dong_lai_van_la_loi_v2(tmp_path, monkeypatch):
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)])
    hong = _luu_roi_sua(e, "{hỏng")
    _hong_dung(monkeypatch)
    kq = e.scan_youtube(URL)
    e2 = Engine(root=e.root, data_dir=e.data_dir, out_dir=e.out_dir)
    assert e2.bao_cao_cua_job(kq.job_id) == v2.LoiBaoCaoV2(v2.LOI_TAO, ngoai_le="RuntimeError")
    assert e2.bao_cao_cua_job(hong) == v2.LoiBaoCaoV2(v2.LOI_HONG)


# ---------------------------------------------------------------------------
#  Luật cũ thật và V2 bình thường giữ nguyên
# ---------------------------------------------------------------------------

def test_lich_su_cu_khong_co_dong_anh_chup_van_la_luat_cu(engine):
    job_id = engine.save_job(dataclasses.replace(_kq_ca_that(), bao_cao=None), "youtube")
    assert engine.bao_cao_cua_job(job_id) is None
    assert engine.dong_bao_cao_job(job_id, dang_ngang=True) is None
    assert engine.dong_bao_cao_job(job_id, dang_ngang=False) is None


def test_ket_qua_cu_van_xuat_luat_cu_va_tach_khoi_ket_qua_loi(tmp_path, monkeypatch):
    e, mt, hop, kb = _the_gioi(tmp_path, monkeypatch, [Dat(_B, 915.5, 300)])
    moi = e.scan_youtube(URL)
    cu = dataclasses.replace(moi, bao_cao=None)
    loi = dataclasses.replace(moi, bao_cao=v2.LoiBaoCaoV2(v2.LOI_TAO))
    assert "QUÉT MỘT PHẦN" in e.to_rows([cu])[0][1]          # luật cũ y nguyên
    assert v2.tach_loi_bao_cao([cu, loi, moi]) == ([cu, moi], [loi])
    with pytest.raises(v2.LoiXuatBaoCaoV2):
        e.to_rows([cu, loi])                                 # không xuất lẫn một nửa


# ---------------------------------------------------------------------------
#  Watch, CLI, lô nguồn chung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dang_ngang", [True, False])
def test_watch_khong_xuat_khong_gui_ket_qua_loi_bao_cao(tmp_path, monkeypatch, dang_ngang):
    cong = _cong_dem(monkeypatch, tmp_path)
    e = _eng(tmp_path, monkeypatch, YdlKichBan())
    monkeypatch.setattr(e, "scan_media", _quet_gia(e))
    _hong_dung(monkeypatch, chi_ma=_ma(2))
    wl = WatchList(muc=[MucTheoDoi("link", _url(_ma(i))) for i in (1, 2)], kho="A")
    bc = chay_giam_sat(e, wl, sheet_link=LINK_GIA, dang_ngang=dang_ngang)
    chu = [" ".join(map(str, r)) for _, _, rows in cong.bang for r in rows]
    assert any(_ma(1) in c for c in chu), "video hợp lệ vẫn lên Sheets"
    assert not any(_ma(2) in c for c in chu), "video lỗi báo cáo V2 không lên Sheets"
    import outbox
    assert bc.gui[outbox.BLOCKED_REPORT] == 1                # lỗi V2: có trong hàng đợi, KHÔNG payload
    assert any("Báo cáo V2" in x for x in bc.loi)
    with open(bc.csv_path, encoding="utf-8-sig") as f:
        noi_dung = f.read()
    assert _ma(1) in noi_dung and _ma(2) not in noi_dung
    assert len(e.list_jobs()) == 2                           # lịch sử giữ cả hai lần quét


def test_cli_bao_ro_loi_bao_cao_v2_va_khong_xuat_dong_loi(tmp_path, monkeypatch, capsys):
    e = _eng(tmp_path, monkeypatch, YdlKichBan())
    monkeypatch.setattr(e, "scan_media", _quet_gia(e))
    _hong_dung(monkeypatch, chi_ma=_ma(2))
    monkeypatch.setattr(cli, "Engine", lambda: e)
    monkeypatch.setattr(sys, "argv", ["cli.py", "youtube", _url(_ma(1)), _url(_ma(2))])
    cli.main()
    ra = capsys.readouterr().out
    assert "Báo cáo V2" in ra and "Traceback" not in ra
    duong = ra.split("===> Báo cáo CSV:")[1].splitlines()[0].strip()
    with open(duong, encoding="utf-8-sig") as f:
        noi_dung = f.read()
    assert _ma(1) in noi_dung and _ma(2) not in noi_dung


def test_lo_nguon_chung_van_v2_khi_anh_chup_tung_luot_loi(tmp_path, monkeypatch):
    """Lô nguồn chung không dùng ảnh chụp từng lượt: dấu V2 của nó là chính sách ĐÃ GHIM."""
    e = _eng(tmp_path, monkeypatch, YdlKichBan())
    monkeypatch.setattr(e, "scan_media", _quet_gia(e))
    _hong_dung(monkeypatch)
    kq = _chay_lo(e, [_url(_ma(i)) for i in range(3)]).result
    assert kq.trang_thai == co.TIM_THAY
    assert kq.chinh_sach_bao_cao == v2.CHINH_SACH_V2
    assert len(co.dong_bao_cao(kq)) == 3


# ---------------------------------------------------------------------------
#  Giao diện (AppTest): bảng kết quả, gửi Sheets tay, tab Lịch sử
# ---------------------------------------------------------------------------

def _app(tmp_path, monkeypatch):
    data_dir, out_dir = tmp_path / "data", tmp_path / "ketqua"
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(out_dir))
    return Engine(data_dir=str(data_dir), out_dir=str(out_dir))


def _chu(at):
    return "\n".join(str(x.value) for loai in ("error", "warning", "info", "success", "caption")
                     for x in getattr(at, loai))


def test_giao_dien_bao_loi_v2_va_chi_gui_sheets_ket_qua_hop_le(tmp_path, monkeypatch):
    """Gửi thêm (thủ công) qua outbox: chỉ kết quả hợp lệ thành việc gửi; payload dựng lại TỪ ẢNH
    CHỤP đã lưu; kết quả V2 lỗi được báo, không bao giờ thành dòng gửi."""
    import outbox
    from outbox_gia import dich_gia
    _app(tmp_path, monkeypatch)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    eng = at.session_state.eng
    dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    tot = _kq_ca_that()
    tot.bao_cao = _bc(tot)
    tot.job_id = eng.save_job(tot, "youtube")
    at.session_state.job.update({"running": False, "kind": "scan", "results": [tot, _kq_loi()],
                                 "error": "", "da_day_sheet": True})
    at.run()
    assert not at.exception
    loi = " ".join(str(x.value) for x in at.error)
    assert "Báo cáo V2" in loi and "Video lỗi báo cáo" in loi
    bang = next(d.value for d in at.dataframe if "Nguồn video dài" in d.value.columns)
    assert list(bang["Nguồn video dài"]) == ["Video tổng hợp thử (Phần 2)"]
    at = next(b for b in at.button if b.label == "📤 Tạo việc gửi").click().run()
    assert not at.exception
    (viec,) = outbox.ds_viec(eng.sqlite_file)
    assert viec.job_id == tot.job_id and viec.nguon == outbox.NGUON_THU_CONG
    da_gui = " ".join(str(o) for dong in viec.rows for o in dong)
    assert "vidvipham01" in da_gui and "vidloi00001" not in da_gui
    nen = outbox._NEN.get(outbox._khoa_db(eng.sqlite_file))
    if nen is not None:
        nen.stop()


def test_giao_dien_lo_chi_co_ket_qua_loi_thi_khong_gui_gi(tmp_path, monkeypatch):
    import outbox
    from outbox_gia import dich_gia
    _app(tmp_path, monkeypatch)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    eng = at.session_state.eng
    dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    at.session_state.job.update({"running": False, "kind": "scan", "results": [_kq_loi()],
                                 "error": "", "da_day_sheet": True})
    at.run()
    assert not at.exception
    assert not any(b.label == "📤 Tạo việc gửi" for b in at.button)
    assert outbox.ds_viec(eng.sqlite_file) == []
    assert "Báo cáo V2" in " ".join(str(x.value) for x in at.error)


@pytest.mark.parametrize("hong", [True, False], ids=["anh_chup_hong", "loi_khi_tao"])
def test_lich_su_bao_ro_v2_loi_khong_cho_tai_khong_noi_la_ban_cu(tmp_path, monkeypatch, hong):
    e = _app(tmp_path, monkeypatch)
    if hong:
        job_id = _luu_roi_sua(e, "{hỏng")
    else:
        job_id = e.save_job(_kq_loi(), "youtube")
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    chon = next(sb for sb in at.selectbox if sb.label == "Xem chi tiết lần quét số")
    assert chon.value == job_id
    chu = _chu(at)
    assert "Báo cáo V2" in " ".join(str(x.value) for x in at.error)
    assert "Lần quét cũ (trước báo cáo V2)" not in chu
    assert [el.proto.label for el in at.get("download_button")] == []
    assert any("Clip gốc" in d.value.columns for d in at.dataframe)   # dữ liệu khớp vẫn xem được
