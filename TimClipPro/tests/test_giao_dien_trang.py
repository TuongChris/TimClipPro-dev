"""Menu 5 nhóm / 15 trang (st.navigation, người dùng duyệt 23/11): mỗi lần vẽ lại CHỈ chạy trang đang mở; ô nhập giữ
giá trị khi chuyển trang. Bộ test khác vẽ mọi trang (TIMCLIP_UI_VE_MOI_TRANG, conftest) — test ở đây bỏ biến đó."""

import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest

GOC = Path(__file__).resolve().parents[1]
APP_PY = GOC / "app.py"
WIDGET = {
    "text_input",
    "text_area",
    "selectbox",
    "multiselect",
    "checkbox",
    "toggle",
    "radio",
    "number_input",
    "date_input",
    "slider",
    "select_slider",
    "pills",
    "segmented_control",
    "time_input",
}


def _mo_app(tmp_path, monkeypatch):
    monkeypatch.delenv("TIMCLIP_UI_VE_MOI_TRANG", raising=False)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _co_khoa(at, khoa: str) -> bool:
    try:
        at.text_area(key=khoa)
    except KeyError:
        try:
            at.text_input(key=khoa)
        except KeyError:
            return False
    return True


def test_mac_dinh_chi_chay_trang_quet_youtube(tmp_path, monkeypatch):
    """Không còn 15 tab vẽ cùng lúc: trang mặc định «Quét YouTube» có ô dán link; ô của trang khác (Tải video gốc,
    Đồng bộ kênh, Ghép) KHÔNG được tạo trong lượt này. Trang quét cần kho → ô «Kho đang dùng» hiện ở thanh bên."""
    at = _mo_app(tmp_path, monkeypatch)
    assert len(at.tabs) == 0
    assert _co_khoa(at, "quet_yt_links")
    for khoa in ("o_links_tai", "o_url_dong_bo", "o_links_ghep", "o_url_tieu_de"):
        assert not _co_khoa(at, khoa), khoa
    assert any("Chưa có kho nào" in (w.value or "") for w in at.sidebar.warning)


def test_che_do_bo_test_van_ve_du_15_tab_nhu_cu(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_UI_VE_MOI_TRANG", "1")
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    assert [t.label for t in at.tabs][:3] == [
        "📥 Đồng bộ kênh gốc",
        "⬇️ Tải video gốc",
        "🖼️ Tải thumbnail",
    ]
    assert len(at.tabs) == 15
    assert _co_khoa(at, "o_links_tai") and _co_khoa(at, "quet_yt_links")


def _cay_app():
    return ast.parse(APP_PY.read_text(encoding="utf-8"))


def test_menu_du_15_trang_moi_trang_mot_lan_5_nhom():
    cay = _cay_app()
    ham_trang = {
        n.name
        for n in cay.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("_trang_")
    }
    gan = next(
        n
        for n in cay.body
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_TRANG"
    )
    nhom = gan.value
    assert isinstance(nhom, ast.Dict) and len(nhom.keys) == 5
    trang = [c for ds in nhom.values for c in ds.elts]
    dung = [c.args[0].id for c in trang]
    duong = [
        next(k.value.value for k in c.keywords if k.arg == "url_path") for c in trang
    ]
    assert sorted(dung) == sorted(ham_trang) and len(dung) == 15
    assert len(set(duong)) == 15 and all(d.isascii() and " " not in d for d in duong)
    mac_dinh = [c for c in trang if any(k.arg == "default" for k in c.keywords)]
    assert len(mac_dinh) == 1 and mac_dinh[0].args[0].id == "_trang_quet_youtube"


def test_moi_o_nhap_co_key_deu_giu_gia_tri_khi_chuyen_trang():
    """st.navigation XOÁ giá trị của widget không được vẽ ở lượt này (chuyển trang) — nút «💾 Lưu cấu hình» đọc lại các
    ô đó. Mọi ô nhập có key (app.py, ui_gui_sheets.py) phải có persist_state="session"."""
    thieu = []
    for f in (APP_PY, GOC / "ui_gui_sheets.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in WIDGET
            ):
                kw = {k.arg: k.value for k in n.keywords}
                if (
                    "key" in kw
                    and getattr(kw.get("persist_state"), "value", None) != "session"
                ):
                    thieu.append(f"{f.name}:{n.lineno}")
    assert not thieu
