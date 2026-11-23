# -*- coding: utf-8 -*-
"""Bớt việc lặp mỗi lần vẽ lại (giai đoạn 2 giao diện, 23/11): các chỗ nhớ đệm vẫn phải thấy dữ liệu MỚI — kho thêm/bớt
file, sổ kho đổi ở tiến trình khác — và chữ «Đang khởi động» không đọng lại. Dữ liệu tổng hợp, thư mục tạm, không mạng."""

from __future__ import annotations

import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

import runtime_paths
from engine import Engine

APP_PY = str(Path(__file__).resolve().parents[1] / "app.py")


def _moi_truong(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_UI_VE_MOI_TRANG", "1")
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    return Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ketqua"))


def _mo(at=None):
    at = (at or AppTest.from_file(APP_PY, default_timeout=120)).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


# ---------------------------------------------------------------- sổ kho (thanh bên đọc mỗi lượt)
def test_list_khos_nho_nhung_thay_kho_tien_trinh_khac_vua_them(tmp_path, monkeypatch):
    e = _moi_truong(tmp_path, monkeypatch)
    e.add_kho("A")
    assert [k["ten"] for k in e.list_khos()] == ["A"]
    doc = []
    goc = Engine._doc_khos
    monkeypatch.setattr(Engine, "_doc_khos", lambda self: doc.append(1) or goc(self))
    e.list_khos()[0]["ten"] = "bị sửa"          # người gọi sửa bản trả về không làm hỏng bản nhớ
    assert [k["ten"] for k in e.list_khos()] == ["A"]
    assert doc == [], "khos.json không đổi mà vẫn đọc lại (giữ khoá liên tiến trình mỗi lần vẽ)"
    # Engine khác (= tiến trình/cửa sổ khác) sửa sổ: lượt sau phải thấy ngay.
    Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ketqua")).add_kho("B")
    assert sorted(k["ten"] for k in e.list_khos()) == ["A", "B"]
    assert doc, "khos.json đã đổi mà không đọc lại"


# ---------------------------------------------------------------- sổ «video còn trên YouTube» (tab Lịch sử)
def test_doc_so_kiem_video_con_nho_nhung_thay_lan_kiem_moi(tmp_path, monkeypatch):
    import kiem_video_con as kv
    import luu_tru

    data = str(tmp_path / "data")
    assert kv.doc_so(data) == {}
    so = os.path.join(data, kv.TEN_FILE)
    luu_tru.ghi_json_an_toan(so, {"phien_ban": 1, "video": {"AAAAAAAAAAA": {"ket_qua": kv.CON_CONG_KHAI}}})
    assert list(kv.doc_so(data)) == ["AAAAAAAAAAA"]
    doc = []
    goc = luu_tru.doc_json_an_toan
    monkeypatch.setattr(luu_tru, "doc_json_an_toan", lambda *a, **k: doc.append(1) or goc(*a, **k))
    kv.doc_so(data)["AAAAAAAAAAA"]["ket_qua"] = "bị sửa"      # sửa bản trả về không làm hỏng bản nhớ
    assert kv.doc_so(data)["AAAAAAAAAAA"]["ket_qua"] == kv.CON_CONG_KHAI
    assert doc == [], "sổ không đổi mà vẫn đọc lại"
    luu_tru.ghi_json_an_toan(so, {"phien_ban": 1, "video": {"AAAAAAAAAAA": {"ket_qua": kv.KHONG_CON},
                                                            "BBBBBBBBBBB": {"ket_qua": kv.CON_CONG_KHAI}}})
    moi = kv.doc_so(data)
    assert moi["AAAAAAAAAAA"]["ket_qua"] == kv.KHONG_CON and "BBBBBBBBBBB" in moi
    os.remove(so)
    assert kv.doc_so(data) == {}


# ---------------------------------------------------------------- thống kê kho ở trang «Đồng bộ kênh gốc»
def _so_file_kho(at) -> str:
    cau = [i.value for i in at.info if "Kho hiện có" in (i.value or "")]
    assert len(cau) == 1, cau
    return cau[0].split("**")[1]


def test_thong_ke_kho_nho_theo_thu_muc_van_thay_file_moi_va_file_xoa(tmp_path, monkeypatch):
    e = _moi_truong(tmp_path, monkeypatch)
    kho = tmp_path / "kho"
    kho.mkdir()
    for i in range(3):
        (kho / f"clip {i} [AAAAAAAAAA{i}].opus").write_bytes(b"x" * 100)
    e.luu_cau_hinh({"kho_dir": str(kho)})
    import channel

    dem = []
    goc = channel.ChannelSync.thong_ke
    monkeypatch.setattr(channel.ChannelSync, "thong_ke", lambda self: dem.append(1) or goc(self))
    at = _mo()
    assert _so_file_kho(at) == "3"
    at = _mo(at)
    assert _so_file_kho(at) == "3"
    assert len(dem) == 1, "kho không đổi mà vẫn liệt kê lại cả thư mục ở mỗi lần vẽ"
    (kho / "clip moi [BBBBBBBBBBB].opus").write_bytes(b"y" * 100)
    assert _so_file_kho(_mo(at)) == "4"
    (kho / "clip 0 [AAAAAAAAAA0].opus").unlink()
    (kho / "clip 1 [AAAAAAAAAA1].opus").unlink()
    assert _so_file_kho(_mo(at)) == "2"


# ---------------------------------------------------------------- «Tình trạng hệ thống» ở thanh bên
def _env(self, ffmpeg=True):
    """check_env giả: công cụ theo tham số, «Kho vân tay» như thật (có file vân tay của kho đang chọn hay không)."""
    return {"ffmpeg": ffmpeg, "ffprobe": True, "yt_dlp": True, "yt_dlp_version": "2026.01.01",
            "audfprint": True, "database": os.path.exists(self.db_file)}


def test_du_cong_cu_gon_mot_dong_va_do_mot_lan_moi_phien(tmp_path, monkeypatch):
    e = _moi_truong(tmp_path, monkeypatch)
    Path(e.db_file).write_bytes(b"gia")             # chỉ cần có file: «Kho vân tay» kiểm bằng os.path.exists
    goi = []
    monkeypatch.setattr(Engine, "check_env", lambda self: goi.append(1) or _env(self))
    at = _mo()
    at = _mo(at)
    assert len(goi) == 1, "dò công cụ (which + nạp yt_dlp) chạy lại ở mỗi lần vẽ"
    nhan = [x.label for x in at.sidebar.expander]
    assert "✅ Đủ công cụ" in nhan, nhan
    chu = " ".join(m.value for m in at.sidebar.markdown)
    assert "✅ FFmpeg" in chu and "2026.01.01" in chu      # chi tiết vẫn có trong ô mở rộng
    assert not at.sidebar.error
    # Phiên mới (tải lại trang) dò lại: vừa cài/gỡ FFmpeg là thấy.
    monkeypatch.setattr(Engine, "check_env", lambda self: goi.append(1) or _env(self, ffmpeg=False))
    at2 = _mo()
    assert len(goi) == 2
    assert "✅ Đủ công cụ" not in [x.label for x in at2.sidebar.expander]
    assert any("❌ FFmpeg" in m.value for m in at2.sidebar.markdown)
    assert any("Thiếu công cụ" in x.value for x in at2.sidebar.error)


def test_kho_van_tay_xoa_thi_hien_lai_danh_sach_du(tmp_path, monkeypatch):
    """File vân tay mất (đổi kho, xoá kho) → dò lại ngay, lượt sau hiện đủ danh sách có ❌."""
    e = _moi_truong(tmp_path, monkeypatch)
    Path(e.db_file).write_bytes(b"gia")
    monkeypatch.setattr(Engine, "check_env", lambda self: _env(self))
    at = _mo()
    assert "✅ Đủ công cụ" in [x.label for x in at.sidebar.expander]
    os.remove(e.db_file)
    at = _mo(at)
    assert any("❌ Kho vân tay clip gốc" in m.value for m in at.sidebar.markdown)


# ---------------------------------------------------------------- chữ «Đang khởi động»
def test_chu_dang_khoi_dong_khong_dong_lai(tmp_path, monkeypatch):
    _moi_truong(tmp_path, monkeypatch)
    at = _mo()
    assert not [i.value for i in at.info if "Đang khởi động" in (i.value or "")]


def test_khoi_dong_loi_van_bao_loi_ro_khong_con_chu_cho(tmp_path, monkeypatch):
    _moi_truong(tmp_path, monkeypatch)

    def hong(self, *a, **k):
        raise runtime_paths.LoiRuntime("thiếu thư mục trạng thái (giả)")

    monkeypatch.setattr(Engine, "__init__", hong)
    at = AppTest.from_file(APP_PY, default_timeout=120).run()
    assert not at.exception
    assert any("Không khởi động được TimClip Pro" in x.value for x in at.error)
    assert not [i.value for i in at.info if "Đang khởi động" in (i.value or "")]


def test_magic_tat_trong_cau_hinh_script():
    """Magic tắt (``.streamlit/config.toml`` cạnh app.py) chỉ an toàn khi app.py không có biểu thức trần nào ngoài
    docstring — biểu thức như vậy trước đây được st.write, nay sẽ im lặng."""
    import ast
    import tomllib

    goc = Path(APP_PY).parent
    assert tomllib.loads((goc / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["runner"]["magicEnabled"] is False
    cay = ast.parse((goc / "app.py").read_text(encoding="utf-8"))
    tran = [n.lineno for n in ast.walk(cay) if isinstance(n, ast.Expr)
            and not isinstance(n.value, (ast.Call, ast.Await, ast.Yield, ast.YieldFrom))
            and not (isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
    assert not tran, f"biểu thức trần (magic đã tắt nên KHÔNG hiện) ở dòng {tran}"
