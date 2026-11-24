# -*- coding: utf-8 -*-
"""Lọc theo kho (trang Lịch sử, Thống kê, bảng video vi phạm), cột «Kho» và cảnh báo việc kẹt của hàng đợi gửi Sheets.

Lịch sử tổng hợp trong thư mục tạm (Engine thật, ``save_job`` thật). Không mạng, không gọi Google: việc gửi chèn thẳng
vào outbox ở trạng thái không ai gửi (bị chặn / không rõ), hoặc tạm dừng gửi toàn bộ.
"""

from __future__ import annotations

import contextlib
import sqlite3
import time
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

import lich_su
import outbox as ob
import sheet_destinations as sd
import thong_ke
import ui_gui_sheets
from conftest import M
from engine import Engine, ScanResult
from outbox_gia import dich_gia

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
SML = ("kSML1", "kSML2")  # kho «SML» xoá rồi tạo lại cùng tên = hai mã kho
A, B, C, D = "vidAAAAAAAA", "vidBBBBBBBB", "vidCCCCCCCC", "vidDDDDDDDD"


def _luu(eng, ma, kho_id, kho_ten, luc, *, so_khop=1) -> int:
    """Một lần quét YouTube ``ok`` đã lưu, gắn kho ``(kho_id, kho_ten)`` và ngày quét ``luc``; ``so_khop=0`` = âm tính."""
    kq = ScanResult(
        source_name=f"Video {ma}",
        source_ref=f"https://www.youtube.com/watch?v={ma}",
        source_id=ma,
        duration_s=600.0,
        matches=[M(clip="goc.opus") for _ in range(so_khop)],
    )
    job_id = eng.save_job(kq, "youtube")
    with contextlib.closing(sqlite3.connect(eng.sqlite_file)) as cx, cx:
        cx.execute(
            "UPDATE jobs SET kho_id=?, kho_ten=?, created_at=? WHERE id=?",
            (kho_id, kho_ten, luc, job_id),
        )
    return job_id


def _kich_ban(eng) -> list:
    """Lịch sử cũ chưa rõ kho, kho «SML» (hai mã), kho «Joe»; video B vi phạm ở cả Joe lẫn SML."""
    return [
        _luu(eng, A, "", "", "2026-09-01 08:00:00"),
        _luu(eng, A, "kSML1", "SML", "2026-10-01 08:00:00"),
        _luu(eng, B, "kJoe", "Joe", "2026-10-10 08:00:00"),
        _luu(eng, C, "kSML2", "SML", "2026-11-01 08:00:00", so_khop=0),
        _luu(eng, B, "kSML2", "SML", "2026-11-05 08:00:00"),
        _luu(eng, D, "kJoe", "Joe", "2026-11-06 08:00:00"),
    ]


def _eng(tmp_path) -> Engine:
    return Engine(
        root=str(tmp_path),
        data_dir=str(tmp_path / "data"),
        out_dir=str(tmp_path / "ketqua"),
    )


# ---------------------------------------------------------------- truy vấn (chỉ đọc)


def test_kho_trong_lich_su_gop_theo_ten_kho_quet_gan_nhat_truoc(tmp_path):
    eng = _eng(tmp_path)
    assert lich_su.kho_trong_lich_su(eng.sqlite_file) == {}
    _kich_ban(eng)
    assert list(lich_su.kho_trong_lich_su(eng.sqlite_file).items()) == [
        ("Joe", ("kJoe",)),
        ("SML", SML),
        (lich_su.CHUA_RO, ("",)),
    ]


def test_list_jobs_va_video_vi_pham_loc_trong_truy_van(tmp_path):
    eng = _eng(tmp_path)
    j1, j2, j3, j4, j5, j6 = _kich_ban(eng)
    assert [j["id"] for j in eng.list_jobs()] == [j6, j5, j4, j3, j2, j1]  # mặc định: như cũ
    assert [j["id"] for j in eng.list_jobs(kho_ids=("kJoe",))] == [j6, j3]
    # Giới hạn tính SAU khi lọc: kho ít quét không bị lần quét của kho khác đẩy ra ngoài.
    assert [j["id"] for j in eng.list_jobs(1, kho_ids=("",))] == [j1]

    assert [(v["ma"], v["so_lan_quet"]) for v in eng.video_vi_pham()] == [(D, 1), (B, 2), (A, 2)]
    sml = eng.video_vi_pham(SML)
    assert [(v["ma"], v["so_lan_quet"], v["lan_quet_cuoi"]) for v in sml] == [
        (B, 1, "2026-11-05 08:00:00"),
        (A, 1, "2026-10-01 08:00:00"),
    ]
    assert [v["ma"] for v in eng.video_vi_pham(("",))] == [A]


def test_thong_ke_loc_kho_lan_dau_tinh_trong_lich_su_cua_kho(tmp_path):
    eng = _eng(tmp_path)
    _kich_ban(eng)
    db = eng.sqlite_file

    tk = thong_ke.tinh(db)
    assert (tk.so_lan_quet, tk.so_video_vi_pham) == (6, 3)
    assert tk.theo_thang == [("2026-09", 1), ("2026-10", 1), ("2026-11", 1)]

    tk = thong_ke.tinh(db, kho_ids=SML)
    assert (tk.so_lan_quet, tk.so_video_vi_pham, tk.so_doan_khop) == (3, 2, 2)
    # A vi phạm ở SML lần đầu 01/10 (lần 01/09 thuộc lịch sử chưa rõ kho), B lần đầu ở SML 05/11.
    assert tk.theo_thang == [("2026-10", 1), ("2026-11", 1)]

    tk = thong_ke.tinh(db, tu_ngay=date(2026, 10, 5), kho_ids=SML)
    assert (tk.so_lan_quet, tk.so_video_vi_pham, tk.theo_thang) == (2, 1, [("2026-11", 1)])
    assert thong_ke.tinh(db, kho_ids=("",)).so_lan_quet == 1
    assert thong_ke.tinh(db, kho_ids=("khong_co",)) == thong_ke.ThongKe()


def test_thong_ke_loc_kho_tren_luoc_do_rat_cu_khong_cot_kho(tmp_path):
    path = str(tmp_path / "lichsu.db")
    with contextlib.closing(sqlite3.connect(path)) as con, con:
        con.execute(
            "CREATE TABLE jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, source_type TEXT,"
            " source_name TEXT, source_ref TEXT, duration_s REAL, status TEXT, n_matches INTEGER, note TEXT)"
        )
        con.execute(
            "INSERT INTO jobs(created_at, source_name, status) VALUES('2026-12-30 08:00:00', 'a.mp4', 'ok')"
        )
    assert thong_ke.tinh(path, kho_ids=("",)).so_lan_quet == 1  # chưa có cột kho = chưa rõ kho
    assert thong_ke.tinh(path, kho_ids=("kJoe",)).so_lan_quet == 0


# ---------------------------------------------------------------- trang Lịch sử / Thống kê (AppTest)


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _tab(at, nhan):
    return next(t for t in at.tabs if t.label == nhan)


def _bang(tab, cot):
    return next(d.value for d in tab.dataframe if cot in d.value.columns)


def test_o_chon_kho_loc_trang_lich_su_va_thong_ke(tmp_path, monkeypatch):
    _kich_ban(_eng(tmp_path))
    at = _app(tmp_path, monkeypatch)
    o = at.selectbox(key="ls_kho")
    assert o.options == ["Tất cả kho", "Joe", "SML", lich_su.CHUA_RO]
    assert o.value == "Tất cả kho"
    ls = _tab(at, "📜 Lịch sử")
    assert len(_bang(ls, "Phạm vi")) == 6 and len(_bang(ls, "Trên YouTube")) == 3

    at = o.set_value("SML").run()
    assert not at.exception
    ls = _tab(at, "📜 Lịch sử")
    assert list(_bang(ls, "Phạm vi")["Kho"]) == ["SML"] * 3
    assert list(_bang(ls, "Trên YouTube")["Video vi phạm"]) == [f"Video {B}", f"Video {A}"]
    # Trang Thống kê có ô riêng: chưa chọn gì thì vẫn tính mọi kho.
    so = {m.label: m.value for m in _tab(at, "📊 Thống kê").metric}
    assert so["Số lần quét"] == "6"

    at = at.selectbox(key="tk_kho").set_value("Joe").run()
    assert not at.exception
    so = {m.label: m.value for m in _tab(at, "📊 Thống kê").metric}
    assert (so["Số lần quét"], so["Video vi phạm"]) == ("2", "2")


# ---------------------------------------------------------------- hàng đợi gửi: cột «Kho», cảnh báo việc kẹt


def _viec(eng, y, job_id, trang_thai) -> str:
    with sd.ket_noi(eng.sqlite_file, ghi=True) as con:
        vid = ob.them_viec(
            con,
            y,
            job_id=job_id,
            chinh_sach="v2",
            header=["h"] * 34,
            rows=[["r"] * 34],
        )
        con.execute("UPDATE hang_doi_gui SET trang_thai=? WHERE id=?", (trang_thai, vid))
    return vid


def test_canh_bao_viec_ket_mot_cau():
    tt = dict.fromkeys(ob.TAT_CA_TRANG_THAI, 0)
    assert ui_gui_sheets.canh_bao_viec_ket(tt) == ""
    tt.update({ob.PENDING: 3, ob.RETRY_WAIT: 1, ob.SENT: 9, ob.CANCELLED: 2})
    assert ui_gui_sheets.canh_bao_viec_ket(tt) == ""  # đang chờ / đã xong: không phải kẹt
    tt.update({ob.BLOCKED_CONFIG: 1, ob.BLOCKED_REPORT: 1, ob.UNKNOWN: 1})
    assert ui_gui_sheets.canh_bao_viec_ket(tt) == (
        "📤 Gửi Google Sheets: 2 việc bị chặn, 1 việc không rõ đã gửi chưa — cần bạn xem."
    )
    tt.update({ob.BLOCKED_CONFIG: 0, ob.BLOCKED_REPORT: 0})
    assert ui_gui_sheets.canh_bao_viec_ket(tt) == (
        "📤 Gửi Google Sheets: 1 việc không rõ đã gửi chưa — cần bạn xem."
    )


def _canh_bao(at) -> list:
    # Streamlit tách biểu tượng đầu câu («📤») của st.warning thành icon: giá trị còn lại bắt đầu bằng chữ.
    return [w.value for w in at.warning if w.value.startswith("Gửi Google Sheets:")]


def test_hang_doi_co_cot_kho_va_canh_bao_viec_ket_dau_trang(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    assert not _canh_bao(at)
    assert not [s for s in at.selectbox if s.key == "ls_kho"]  # lịch sử chưa có hai kho: không vẽ ô lọc
    eng = at.session_state.eng
    _, y = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    job = _luu(eng, A, "kSML2", "SML", "2026-11-05 08:00:00")
    _viec(eng, y, job, ob.BLOCKED_CONFIG)
    _viec(eng, y, None, ob.UNKNOWN)  # việc không gắn lần quét
    _viec(eng, y, 999, ob.SENT)  # lần quét đã xoá
    at = at.run()
    assert not at.exception
    # Một dòng ở khu đầu trang (ngoài mọi trang), đếm việc bị chặn + không rõ của CẢ hàng đợi.
    assert _canh_bao(at) == [
        "Gửi Google Sheets: 1 việc bị chặn, 1 việc không rõ đã gửi chưa — cần bạn xem."
    ]
    assert not any(w.value.startswith("Gửi Google Sheets:") for t in at.tabs for w in t.warning)

    at = at.radio(key="gui_loc").set_value("Tất cả (gần nhất)").run()
    bang = _bang(_tab(at, "📤 Gửi Google Sheets"), "Vì sao chưa gửi")
    assert list(bang.columns[:3]) == ["Mã", "Lần quét", "Kho"]
    assert dict(zip(bang["Lần quét"], bang["Kho"])) == {f"#{job}": "SML", "—": "—", "#999": "—"}


def test_che_do_menu_canh_bao_kem_loi_tat_sang_trang_gui(tmp_path, monkeypatch):
    monkeypatch.delenv("TIMCLIP_UI_VE_MOI_TRANG", raising=False)
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    _, y = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    _viec(eng, y, 1, ob.UNKNOWN)
    at = at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(_canh_bao(at)) == 1
    assert "📤 Sang trang Gửi Google Sheets để xử lý" in [
        p.proto.label for p in at.get("page_link")
    ]


def test_man_ket_qua_lo_quet_co_tom_tat_gui_cua_lo(tmp_path, monkeypatch):
    import streamlit

    import engine as engine_mod
    from test_bao_cao_v2 import _bc, _kq_ca_that

    at = _app(tmp_path, monkeypatch)
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)  # tự điều khiển từng khung hình
    eng = at.session_state.eng
    ob.dat_tam_dung(eng.sqlite_file, True)  # người gửi nền không gửi gì
    _, y = dich_gia(
        eng.sqlite_file, tmp_path, installation_id=eng.installation_id(), lo_id="lo-thu"
    )

    def scan_youtube(self, url, progress=None, **kw):
        kq = _kq_ca_that(source_name="Video 1", source_ref=url, source_id="vidthu00000")
        kq.bao_cao = _bc(kq)
        kq.job_id = self.save_job(kq, "youtube")
        return kq

    monkeypatch.setattr(engine_mod.Engine, "scan_youtube", scan_youtube)
    ctl = at.session_state.scan_controller
    ctl.start(["https://www.youtube.com/watch?v=vidthu00000"], "youtube", y_dinh_gui=y)
    at.session_state.job.update(
        {"running": True, "pct": 0.0, "msg": "", "results": [], "error": "", "kind": "scan",
         "da_day_sheet": True, "scan_batch_id": "test"}
    )
    han = time.monotonic() + 30
    while ctl.running and time.monotonic() < han:
        time.sleep(0.02)
    assert not ctl.running
    at.run()  # màn tiến độ thấy lô đã xong → chép kết quả
    at.run()  # màn kết quả
    assert not at.exception and not at.session_state.job["running"]
    tom_tat = [c.value for c in at.caption if c.value.startswith("📤 «")]
    assert len(tom_tat) == 1 and "đã gửi 0, đang chờ 1, bị chặn 0, không rõ 0" in tom_tat[0], tom_tat
    nen = ob._NEN.get(ob._khoa_db(eng.sqlite_file))
    if nen is not None:
        nen.stop(cho_s=5)
