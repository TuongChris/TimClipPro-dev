# -*- coding: utf-8 -*-
"""Kho có clip CHƯA có vân tay (DT-05) + tên kho khi quét (#25).

Đồng bộ kênh xong mà quên «Bổ sung» thì các lượt quét sau vẫn dùng kho cũ: video dùng clip mới ra «không tìm thấy»
mà không có cảnh báo nào (âm tính sai, lại được ghi lịch sử như đã kiểm). Thanh bên + hai trang quét phải báo; so tên
file theo ĐÚNG luật «Bổ sung» dùng để chọn file mới, để không cảnh báo oan. Dữ liệu tổng hợp, thư mục tạm.
"""

import os
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

import channel
from engine import Engine, ScanResult
from kho_gia import ghi_kho
from scan_ui import thoat_markdown
from test_bo_sung_lam_moi_van_tay import _runner

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
TEP = ("a.opus", "b.opus", "c.opus", os.path.join("sub", "d.m4a"), os.path.join("_tam", "dang_tai.opus"),
       os.path.join("_hong", "260101-000000_x.opus"), "e.opus.part", "ghi_chu.txt", "dai.opus")


def _thu_muc(tmp_path) -> Path:
    nguon = tmp_path / "nguon"
    for ten in TEP:
        f = nguon / ten
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"audio")
    return nguon


def _dai_3_gio(monkeypatch) -> None:
    """«dai.opus» dài 3 giờ (> trần D-31): «Bổ sung» bỏ qua, nên cũng không được cảnh báo."""
    monkeypatch.setattr(channel, "BYTE_CHAC_CHAN_NGAN", 0)
    monkeypatch.setattr(channel, "do_dai_media", lambda p: 3 * 3600.0 if p.endswith("dai.opus") else 60.0)


def test_file_chua_van_tay_theo_dung_luat_bo_sung(tmp_path, monkeypatch):
    nguon = _thu_muc(tmp_path)
    _dai_3_gio(monkeypatch)
    clips = [{"duong_dan": str(nguon / "a.opus"), "so_hash": 9},
             {"duong_dan": str(nguon / "c.opus"), "so_hash": 0}]      # 0 hash = chưa có vân tay dùng được
    ra = Engine.file_chua_van_tay(str(nguon), clips)
    assert sorted(os.path.relpath(p, nguon) for p in ra) == ["b.opus", "c.opus", os.path.join("sub", "d.m4a")]


def test_kho_chep_tu_thu_muc_khac_khong_bao_oan(tmp_path):
    """Kho chép sang máy/ổ khác (trang «Danh sách video trong kho» cho sửa thư mục): vân tay mang đường dẫn cũ, «Bổ sung»
    sẽ nạp trùng MỌI clip — không được xui bấm «Bổ sung»."""
    nguon = _thu_muc(tmp_path)
    clips = [{"duong_dan": str(tmp_path / "o_cu" / "a.opus"), "so_hash": 9}]
    assert Engine.file_chua_van_tay(str(nguon), clips) == []


def test_canh_bao_trung_dung_danh_sach_bo_sung_se_tao_van_tay(tmp_path, monkeypatch):
    nguon = _thu_muc(tmp_path)
    _dai_3_gio(monkeypatch)
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e._cap_nhat_snapshot_sau_build = lambda *a: []
    e.add_kho("A", str(nguon))
    ghi_kho(e.db_file, [(str(nguon / "a.opus"), 9), (str(nguon / "c.opus"), 0)])
    moc = time.time() - 100
    os.utime(e.db_file, (moc, moc))
    os.utime(nguon / "a.opus", (moc - 50, moc - 50))    # file không đổi sau lần tạo kho: không «làm mới»
    canh_bao = Engine.file_chua_van_tay(str(nguon), e._doc_danh_sach_clip(e.db_file))
    lenh = []
    e._run_stream = _runner({"b.opus": 5, "c.opus": 5, "d.m4a": 5}, lenh)

    kq = e.build_database(str(nguon), "add")

    assert kq.get("da_ghi_kho") is True
    assert sorted(canh_bao) == sorted(lenh[-1][1])


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _tab(at, nhan: str):
    return next(t for t in at.tabs if t.label == nhan)


def _canh_bao(nhom) -> list:
    return [w.value for w in nhom.warning if "chưa có vân tay" in w.value]


def test_thanh_ben_va_hai_trang_quet_bao_clip_chua_co_van_tay(tmp_path, monkeypatch):
    nguon = tmp_path / "Kho SML"
    nguon.mkdir()
    for ten in ("a.opus", "b.opus"):
        (nguon / ten).write_bytes(b"audio")
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    eng.add_kho("SML", str(nguon))
    ghi_kho(eng.db_file, [(str(nguon / "a.opus"), 9)])
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    o_kho = _canh_bao(at.sidebar)
    assert len(o_kho) == 1 and "**1**" in o_kho[0] and thoat_markdown("b.opus") in o_kho[0], o_kho
    assert "Bổ sung" in o_kho[0]
    for nhan in ("▶️ Quét YouTube", "📁 Quét file trong máy"):
        tab = _tab(at, nhan)
        assert _canh_bao(tab) == o_kho, nhan
        assert any("Quét với kho «SML»" in c.value for c in tab.caption), nhan    # #25

    ghi_kho(eng.db_file, [(str(nguon / "a.opus"), 9), (str(nguon / "b.opus"), 5)])    # đã «Bổ sung»
    at.run()
    assert not _canh_bao(at.sidebar) and not _canh_bao(at.main)

    (nguon / "c.opus").write_bytes(b"audio")                                     # đồng bộ thêm một clip
    at.run()
    assert "**1**" in _canh_bao(at.sidebar)[0] and thoat_markdown("c.opus") in _canh_bao(at.sidebar)[0]

    eng.update_kho("SML", str(tmp_path / "khong_co"))                             # thư mục không tồn tại: câu cũ
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not _canh_bao(at.sidebar) and not _canh_bao(at.main)
    assert any("có **2** clip gốc" in i.value for i in at.sidebar.info)


def test_man_ket_qua_ghi_kho_da_dung_va_cau_khong_tim_thay_neu_ten_kho(tmp_path, monkeypatch):
    kq = ScanResult(source_name="Video thử", source_ref="https://youtu.be/vid00000001", kho_ten="SML")
    at = _app(tmp_path, monkeypatch)
    at.session_state.job.update({"running": False, "kind": "scan", "results": [kq], "error": "",
                                 "da_day_sheet": True})
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Quét với kho «SML»" in c.value for c in at.main.caption)
    assert any("không tìm thấy clip gốc nào trong kho «SML»" in w.value for w in at.main.warning)
