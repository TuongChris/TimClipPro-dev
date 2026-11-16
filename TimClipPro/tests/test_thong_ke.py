# -*- coding: utf-8 -*-
"""Tab «📊 Thống kê»: số liệu vi phạm đọc CHỈ ĐỌC từ ``lichsu.db`` (``thong_ke.py``).

Lịch sử tổng hợp trong thư mục tạm; lược đồ dựng bằng chính ``lich_su.dam_bao_luoc_do``, ảnh chụp V2 bằng chính
``bao_cao_v2.dung_bao_cao``. Không mạng, không dữ liệu thật.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import date
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

import bao_cao_v2 as v2
import engine as engine_mod
import lich_su
import thong_ke

APP_PY = os.path.join(os.path.dirname(os.path.abspath(engine_mod.__file__)), "app.py")


def _anh_chup(kenh_ten: str = "", kenh_id: str = "", tieu_de_clip: dict | None = None) -> str:
    """``du_lieu`` hợp lệ của một dòng ``bao_cao_job`` (kênh vi phạm + tên video gốc lúc quét)."""
    tieu_de_clip = tieu_de_clip or {}
    kq = SimpleNamespace(
        status="ok", source_id="", source_ref="", duration_s=600.0,
        matches=[SimpleNamespace(clip=c, start_s=1.0, end_s=2.0) for c in tieu_de_clip],
        channel_name=kenh_ten, channel_id=kenh_id,
        channel_url=f"https://www.youtube.com/channel/{kenh_id}" if kenh_id else "")
    bc = v2.dung_bao_cao(
        kq, thoi_diem_quet="2026-11-01 00:00:00", nguon_loai="youtube", tieu_de="Video",
        nguon_tieu_de=v2.NGUON_TIEU_DE_YTDLP, ly_do_thieu_tieu_de="", ngay_dang=v2.NgayNguon(),
        goc_theo_clip={c: v2.GocV2(clip=c, tieu_de=t) for c, t in tieu_de_clip.items()}, mo_ta_pham_vi="")
    return json.dumps(bc.to_dict(), ensure_ascii=False)


def _job(path, luc, ma, *, status="ok", khop=(), anh_chup=None):
    """Một lần quét: ``khop`` = [(clip, giây khớp)]; ``anh_chup`` = ``du_lieu`` V2 (None = lần quét luật cũ)."""
    con = sqlite3.connect(path)
    try:
        with con:
            cur = con.execute(
                "INSERT INTO jobs(created_at, source_type, source_name, source_ref, duration_s, status, n_matches,"
                " note, source_id) VALUES(?,?,?,?,?,?,?,?,?)",
                (luc, "youtube", f"Video {ma}", f"https://www.youtube.com/watch?v={ma}", 600.0, status, len(khop),
                 "", ma))
            for clip, giay in khop:
                con.execute("INSERT INTO matches(job_id, clip, start_s, end_s, matched_s, clip_offset_s, hashes,"
                            " confidence) VALUES(?,?,?,?,?,?,?,?)",
                            (cur.lastrowid, clip, 0.0, giay, giay, 0.0, 100, "Chắc chắn"))
            if anh_chup is not None:
                con.execute("INSERT INTO bao_cao_job(job_id, chinh_sach, du_lieu, created_at) VALUES(?,?,?,?)",
                            (cur.lastrowid, "v2", anh_chup, luc))
    finally:
        con.close()


def _kich_ban(path) -> None:
    """Đủ loại lần quét: quét lại, hai đoạn cùng clip, luật cũ, lỗi, không thấy, ảnh chụp hỏng / dấu lỗi V2."""
    lich_su.dam_bao_luoc_do(path)
    k1 = _anh_chup("Kênh Một", "UCmot", {"X.opus": "Tiêu đề X"})
    _job(path, "2026-08-20 10:00:00", "vidCCCCCCCC", khop=[("Z.opus", 10.0)])                   # luật cũ
    _job(path, "2026-10-05 09:00:00", "vidAAAAAAAA", khop=[("X.opus", 100.0), ("Y.opus", 50.0)], anh_chup=k1)
    _job(path, "2026-11-02 09:00:00", "vidAAAAAAAA", khop=[("X.opus", 120.0)], anh_chup=k1)     # quét lại A
    _job(path, "2026-11-10 09:00:00", "vidBBBBBBBB", khop=[("X.opus", 30.0), ("X.opus", 20.0)],
         anh_chup=_anh_chup("Kênh Một (tên mới)", "UCmot"))
    # Ảnh chụp hỏng của lần quét lỗi / không thấy gì: không phải vi phạm nên không đọc, không đếm.
    _job(path, "2026-11-11 09:00:00", "vidDDDDDDDD", status="error", khop=[("X.opus", 999.0)], anh_chup="{hong")
    _job(path, "2026-11-12 09:00:00", "vidEEEEEEEE", anh_chup="{hong")
    _job(path, "2026-11-13 09:00:00", "vidFFFFFFFF", khop=[("Y.opus", 40.0)], anh_chup="{hong")
    _job(path, "2026-11-14 09:00:00", "vidGGGGGGGG", khop=[("Z.opus", 5.0)],
         anh_chup=json.dumps(v2.LoiBaoCaoV2(v2.LOI_TAO, ngoai_le="RuntimeError").to_dict()))


def _sha(path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_db_chua_co_rong_hoac_trong_tra_so_0_va_khong_tao_file(tmp_path):
    thieu = str(tmp_path / "chua_co" / "lichsu.db")
    assert thong_ke.tinh(thieu) == thong_ke.ThongKe()
    assert not os.path.exists(thieu) and not os.path.exists(os.path.dirname(thieu))

    rong = tmp_path / "rong.db"
    rong.write_bytes(b"")
    assert thong_ke.tinh(str(rong)) == thong_ke.ThongKe()
    assert rong.read_bytes() == b""

    moi = str(tmp_path / "moi.db")
    lich_su.dam_bao_luoc_do(moi)
    assert thong_ke.tinh(moi) == thong_ke.ThongKe()


def test_tong_kenh_clip_va_theo_thang(tmp_path):
    path = str(tmp_path / "lichsu.db")
    _kich_ban(path)
    truoc = _sha(path)
    tk = thong_ke.tinh(path)

    assert _sha(path) == truoc, "thống kê không được ghi gì vào lichsu.db"
    assert not os.path.exists(path + "-journal")
    assert (tk.so_lan_quet, tk.so_lan_loi) == (8, 1)        # lần quét lỗi vẫn là một lần quét
    # A, B, C, F, G — lần quét lỗi (D) và lần không thấy (E) không phải vi phạm.
    assert tk.so_video_vi_pham == 5
    # (A,X) lấy lần quét khớp nhiều nhất = 120 s, KHÔNG cộng 100 + 120; (B,X) hai đoạn của cùng clip = 2 đoạn.
    assert tk.so_doan_khop == 7
    assert tk.tong_giay_khop == 120.0 + 50.0 + 50.0 + 10.0 + 40.0 + 5.0
    assert (tk.ngay_dau, tk.ngay_cuoi) == ("20260820", "20261114")

    assert tk.clip == [
        {"clip": "X.opus", "tieu_de": "Tiêu đề X", "so_video": 2, "so_doan": 3, "tong_giay": 170.0},
        {"clip": "Y.opus", "tieu_de": "", "so_video": 2, "so_doan": 2, "tong_giay": 90.0},
        {"clip": "Z.opus", "tieu_de": "", "so_video": 2, "so_doan": 2, "tong_giay": 15.0},
    ]
    # Kênh chỉ có trong ảnh chụp V2; tên hiển thị là tên ở lần quét MỚI nhất.
    assert tk.kenh == [{"ten": "Kênh Một (tên mới)", "link": "https://www.youtube.com/channel/UCmot",
                        "so_video": 2, "so_doan": 4, "tong_giay": 220.0}]
    # C: lần quét luật cũ (không lưu kênh); F: ảnh chụp hỏng; G: dấu lỗi V2 — không đoán kênh, đếm riêng.
    assert tk.video_chua_ro_kenh == 3
    assert tk.anh_chup_khong_doc_duoc == 2
    # Tháng phát hiện LẦN ĐẦU (A tính ở tháng 10, không tính lại ở tháng 11); tháng trống vẫn có số 0.
    assert tk.theo_thang == [("2026-08", 1), ("2026-09", 0), ("2026-10", 1), ("2026-11", 3)]


def test_loc_theo_ngay_quet_tinh_ca_hai_dau(tmp_path):
    path = str(tmp_path / "lichsu.db")
    _kich_ban(path)

    tk = thong_ke.tinh(path, date(2026, 11, 2), date(2026, 11, 13))
    assert (tk.so_lan_quet, tk.so_lan_loi, tk.so_video_vi_pham) == (5, 1, 3)       # A (quét lại), B, F
    assert (tk.so_doan_khop, tk.tong_giay_khop) == (4, 120.0 + 50.0 + 40.0)
    assert tk.theo_thang == [("2026-11", 3)]
    assert [k["so_video"] for k in tk.kenh] == [2] and tk.video_chua_ro_kenh == 1
    assert tk.anh_chup_khong_doc_duoc == 1

    tk = thong_ke.tinh(path, den_ngay=date(2026, 10, 31))
    assert (tk.so_lan_quet, tk.so_video_vi_pham) == (2, 2)
    assert tk.theo_thang == [("2026-08", 1), ("2026-09", 0), ("2026-10", 1)]

    tk = thong_ke.tinh(path, tu_ngay=date(2026, 11, 14))
    assert (tk.so_lan_quet, tk.so_video_vi_pham, tk.kenh) == (1, 1, [])
    assert (tk.video_chua_ro_kenh, tk.anh_chup_khong_doc_duoc) == (1, 1)


def test_luoc_do_rat_cu_khong_source_id_khong_bang_bao_cao(tmp_path):
    path = str(tmp_path / "lichsu.db")
    con = sqlite3.connect(path)
    with con:
        con.execute("CREATE TABLE jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, source_type TEXT,"
                    " source_name TEXT, source_ref TEXT, duration_s REAL, status TEXT, n_matches INTEGER, note TEXT)")
        con.execute("CREATE TABLE matches(id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, clip TEXT,"
                    " start_s REAL, end_s REAL, matched_s REAL, clip_offset_s REAL, hashes INTEGER, confidence TEXT)")
        for i, luc in enumerate(("2026-12-30 08:00:00", "2027-01-02 08:00:00"), start=1):   # cùng một file quét 2 lần
            con.execute("INSERT INTO jobs(created_at, source_type, source_name, source_ref, status) VALUES(?,?,?,?,?)",
                        (luc, "file", "vi_pham.mp4", r"D:\vi_pham.mp4", "ok"))
            con.execute("INSERT INTO matches(job_id, clip, matched_s) VALUES(?,?,?)", (i, "X.opus", 60.0))
    con.close()

    tk = thong_ke.tinh(path)
    assert (tk.so_lan_quet, tk.so_video_vi_pham, tk.so_doan_khop, tk.tong_giay_khop) == (2, 1, 1, 60.0)
    assert (tk.kenh, tk.video_chua_ro_kenh, tk.anh_chup_khong_doc_duoc) == ([], 1, 0)
    assert tk.theo_thang == [("2026-12", 1)]


def test_nhan_thang_va_du_thang_qua_nam():
    assert thong_ke.nhan_thang("2026-11") == "Tháng 11/2026"
    assert thong_ke.nhan_thang("") == thong_ke.nhan_thang("2026-13") == "Không rõ thời điểm"
    # Ngày quét hỏng ("") không làm mất video khỏi biểu đồ: đứng cuối, nhãn «Không rõ thời điểm».
    assert thong_ke._du_thang({"2027-02": 2, "": 1, "2026-12": 1}) == [
        ("2026-12", 1), ("2027-01", 0), ("2027-02", 2), ("", 1)]


def test_tab_thong_ke_hien_so_lieu_va_cap_nhat_sau_lan_quet_moi(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    db = str(data / "lichsu.db")
    _kich_ban(db)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)

    at = AppTest.from_file(APP_PY, default_timeout=120).run()
    assert not at.exception
    tab = next(t for t in at.tabs if t.label == "📊 Thống kê")
    so = {m.label: m.value for m in tab.metric}
    assert so["Số lần quét"] == "8" and so["Video vi phạm"] == "5" and so["Đoạn khớp"] == "7"
    assert so["Tổng thời lượng khớp"] == "00:04:35"
    assert len(tab.dataframe) == 2                      # kênh + clip gốc
    assert any("không đọc được" in w.value for w in tab.warning)

    # Số liệu được nhớ giữa các lần vẽ lại trang, nhưng lần quét mới lưu vào lịch sử phải hiện ngay.
    _job(db, "2026-11-15 09:00:00", "vidHHHHHHHH", khop=[("X.opus", 1.0)])
    at.run()
    tab = next(t for t in at.tabs if t.label == "📊 Thống kê")
    so = {m.label: m.value for m in tab.metric}
    assert so["Số lần quét"] == "9" and so["Video vi phạm"] == "6"
