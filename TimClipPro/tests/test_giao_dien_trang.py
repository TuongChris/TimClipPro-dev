"""Menu 5 nhóm / 15 trang (st.navigation, người dùng duyệt 23/11): mỗi lần vẽ lại CHỈ chạy trang đang mở; ô nhập giữ
giá trị khi chuyển trang. Bộ test khác vẽ mọi trang (TIMCLIP_UI_VE_MOI_TRANG, conftest) — test ở đây bỏ biến đó."""

import ast
import re
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


# Ô KHÔNG được giữ giá trị khi khuất: ô xác nhận thao tác nguy hiểm (key gắn lựa chọn — đổi lựa chọn / rời trang là
# phải tick lại) và ô vẽ lại từ trạng thái trên đĩa / DB (giữ bản cũ của phiên sẽ hiện ngược trạng thái thật, rồi ghi
# ngược vào đĩa). Review 23/11 tái hiện: nút tạm dừng gửi Sheets hiện ngược; ô xác nhận xoá kho đã tick sẵn.
KHONG_GIU = re.compile(
    r"xac_nhan|confirm_|gui_dong_y_|gui_huy_xn_|khoa_tam_dung|kho_video_dai_|_trung'|khoa_xn"
)


def test_o_nhap_co_key_giu_gia_tri_tru_o_xac_nhan_va_o_doc_lai_trang_thai():
    """st.navigation XOÁ giá trị của widget không được vẽ ở lượt này (chuyển trang). Ô nhập có key (app.py,
    ui_gui_sheets.py) phải có persist_state="session" — trừ ô xác nhận / ô đọc lại trạng thái (KHONG_GIU), phải KHÔNG có."""
    sai = []
    so_khong_giu = 0
    for f in (APP_PY, GOC / "ui_gui_sheets.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in WIDGET
            ):
                kw = {k.arg: k.value for k in n.keywords}
                if "key" not in kw:
                    continue
                giu = getattr(kw.get("persist_state"), "value", None) == "session"
                khong_giu = bool(KHONG_GIU.search(ast.unparse(kw["key"])))
                so_khong_giu += khong_giu
                if giu == khong_giu:
                    sai.append(f"{f.name}:{n.lineno} {ast.unparse(kw['key'])}")
    assert not sai
    assert so_khong_giu >= 12  # 8 ở app.py + 4 ở ui_gui_sheets.py (23/11)
