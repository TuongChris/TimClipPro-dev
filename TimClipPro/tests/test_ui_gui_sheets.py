# -*- coding: utf-8 -*-
"""Giao diện gửi Google Sheets (AppTest + hàm của ``ui_gui_sheets``).

* Tab Lịch sử: ô xác nhận xoá gắn ĐÚNG lần quét đang chọn và tự bỏ tick sau khi xoá — một tick không
  còn xoá luôn lần quét kế tiếp (nợ cũ ghi trong tái audit 05/10). Việc gửi đang bay/không rõ → xoá
  bị chặn, báo lỗi, lần quét còn nguyên.
* Tab «📤 Gửi Google Sheets»: việc KHÔNG RÕ chỉ đổi trạng thái khi người dùng đối soát/xác nhận.
* Bắt đầu lô có tự động gửi: preflight cục bộ lỗi → không bắt đầu, báo lý do.
Dữ liệu tổng hợp; không gọi Google (không bấm nút kiểm chỉ đọc).
"""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

import outbox as ob
import sheet_destinations as sd
from outbox_gia import dich_gia, khoa_gia
from test_bao_cao_v2 import _bc, _kq_ca_that

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    return at


def _luu_hai_lan_quet(eng):
    ids = []
    for i in (1, 2):
        kq = _kq_ca_that(source_name=f"Video thử {i}", source_id=f"vidthu0000{i}")
        kq.bao_cao = _bc(kq)
        ids.append(eng.save_job(kq, "youtube"))
    return ids


def _nut(at, nhan):
    return next(b for b in at.button if b.label == nhan)


def test_xoa_lich_su_o_xac_nhan_gan_job_va_tu_bo_tick(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    a, b = _luu_hai_lan_quet(eng)
    at.run()
    chon = next(sb for sb in at.selectbox if sb.label == "Xem chi tiết lần quét số")
    chon.set_value(b).run()
    next(c for c in at.checkbox if c.key == f"xac_nhan_xoa_ls_{b}").check().run()
    _nut(at, "🗑️ Xóa lần quét này khỏi lịch sử").click().run()
    assert [j["id"] for j in eng.list_jobs()] == [a]
    # Lần quét còn lại: ô xác nhận của NÓ chưa tick → nút xoá vẫn khoá.
    assert next(c for c in at.checkbox if c.key == f"xac_nhan_xoa_ls_{a}").value is False
    assert _nut(at, "🗑️ Xóa lần quét này khỏi lịch sử").disabled is True


def test_xoa_lich_su_bi_chan_khi_viec_gui_khong_ro(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    _, y = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    kq = _kq_ca_that()
    kq.bao_cao = _bc(kq)
    with eng.ghim_y_dinh_gui(y):
        job_id = eng.save_job(kq, "youtube")
    con = sqlite3.connect(eng.sqlite_file)
    con.execute("UPDATE hang_doi_gui SET trang_thai=?", (ob.UNKNOWN,))
    con.commit()
    con.close()
    at.run()
    next(c for c in at.checkbox if c.key == f"xac_nhan_xoa_ls_{job_id}").check().run()
    _nut(at, "🗑️ Xóa lần quét này khỏi lịch sử").click().run()
    assert [j["id"] for j in eng.list_jobs()] == [job_id]
    assert any("chưa rõ đã gửi" in e.value for e in at.error)


def test_tab_gui_doi_soat_viec_khong_ro(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    _, y = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    kq = _kq_ca_that()
    kq.bao_cao = _bc(kq)
    with eng.ghim_y_dinh_gui(y):
        eng.save_job(kq, "youtube")
    (v,) = ob.ds_viec(eng.sqlite_file)
    con = sqlite3.connect(eng.sqlite_file)
    con.execute("UPDATE hang_doi_gui SET trang_thai=?, loi='mất phản hồi'", (ob.UNKNOWN,))
    con.commit()
    con.close()
    at.run()
    assert any("tool KHÔNG tự gửi lại" in w.value for w in at.warning)
    nut_gui_lai = _nut(at, "⚠️ Gửi lại")
    assert nut_gui_lai.disabled is True                   # chưa xác nhận chấp nhận trùng
    _nut(at, "✅ Đã kiểm: dòng đã có trên Sheet").click().run()
    v2 = ob.lay_viec(eng.sqlite_file, v.id)
    assert v2.trang_thai == ob.SENT and json.loads(v2.bien_nhan)["xac_nhan_tay"] is True
    nen = ob._NEN.get(ob._khoa_db(eng.sqlite_file))
    if nen is not None:
        nen.stop()


def test_chon_dich_hien_tu_dong_gui_khi_co_ho_so(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    d, _ = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    at.run()
    chon = next(sb for sb in at.selectbox if sb.key == "quet_yt_dich_gui")
    assert chon.value == ""                                  # mặc định: chỉ lưu cục bộ
    chon.set_value(d.id).run()
    # Lựa chọn RIÊNG từng tab: chọn ở tab YouTube không bị ô của tab file (vẽ sau) đè mất.
    assert at.session_state["quet_yt_dich_chon"] == d.id
    assert at.session_state["quet_file_dich_chon"] == ""
    assert any(c.key == "quet_yt_tu_dong_gui" for c in at.checkbox)


def test_chot_cho_lo_preflight_khoa_sai_khong_bat_dau(tmp_path, monkeypatch):
    import ui_gui_sheets
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    d, _ = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    khoa_gia(tmp_path, email="ke-khac@x.invalid")         # file khoá đổi sang tài khoản khác
    y, loi = ui_gui_sheets.chot_cho_lo(eng, d.id, True, "lo")
    assert y is None and "Chưa bắt đầu" in loi and "Chỉ lưu cục bộ" in loi
    y, loi = ui_gui_sheets.chot_cho_lo(eng, d.id, False, "lo")      # không tự gửi → không chặn
    assert y is None and loi == ""
    sd.doi_trang_thai(eng.sqlite_file, d.id, sd.TT_LUU_TRU)
    y, loi = ui_gui_sheets.chot_cho_lo(eng, d.id, True, "lo")
    assert y is None and "lưu trữ" in loi


# ---------------------------------------------------------------- lượt rà soát độc lập M2


def _hai_viec_khong_ro(eng, tmp_path):
    _, y = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    ids = []
    for j in (1, 2):
        with sd.ket_noi(eng.sqlite_file, ghi=True) as con:
            ids.append(ob.them_viec(con, y, job_id=j, chinh_sach="v2", header=["h"] * 34,
                                    rows=[["r"] * 34]))
    con = sqlite3.connect(eng.sqlite_file)
    con.execute("UPDATE hang_doi_gui SET trang_thai=?", (ob.UNKNOWN,))
    con.commit()
    con.close()
    return ids


def _dung_nen(eng):
    nen = ob._NEN.get(ob._khoa_db(eng.sqlite_file))
    if nen is not None:
        nen.stop(cho_s=5)


def test_tam_dung_toan_bo_khong_bi_phien_khac_dao_nguoc(tmp_path, monkeypatch):
    """P2-F: phiên trình duyệt vẽ LÚC CHƯA tạm dừng, chạy lại sau khi phiên khác tạm dừng → giữ tạm dừng."""
    at1 = _app(tmp_path, monkeypatch)
    at2 = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    eng = at1.session_state.eng
    next(t for t in at1.toggle if t.label.startswith("⏸ Tạm dừng toàn bộ")).set_value(True).run()
    assert ob.dang_tam_dung(eng.sqlite_file) is True
    at2.run()
    assert ob.dang_tam_dung(eng.sqlite_file) is True
    assert next(t for t in at2.toggle if t.label.startswith("⏸ Tạm dừng toàn bộ")).value is True


def test_viec_khong_ro_cu_van_xu_ly_duoc_khi_hang_doi_dai(tmp_path, monkeypatch):
    """P2-G: việc KHÔNG RÕ cũ không bị đẩy khỏi danh sách bởi hàng trăm việc đã gửi mới hơn."""
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    _, y = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    with sd.ket_noi(eng.sqlite_file, ghi=True) as con:
        cu = ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=["h"] * 34, rows=[["r"] * 34])
        for j in range(2, 330):
            ob.them_viec(con, y, job_id=j, chinh_sach="v2", header=["h"] * 34, rows=[["r"] * 34])
        con.execute("UPDATE hang_doi_gui SET trang_thai=?", (ob.SENT,))
        con.execute("UPDATE hang_doi_gui SET trang_thai=? WHERE id=?", (ob.UNKNOWN, cu))
    at.run()
    chon = next(sb for sb in at.selectbox if sb.key == "gui_chon_viec")
    assert any(o.startswith(cu[:8]) for o in chon.options)


def test_o_dong_y_trung_gan_theo_tung_viec(tmp_path, monkeypatch):
    """P2/P3-I: tick «chấp nhận trùng» cho việc X rồi chọn việc Y → nút «Gửi lại» của Y vẫn khoá."""
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    x, y = _hai_viec_khong_ro(eng, tmp_path)
    at.run()
    next(sb for sb in at.selectbox if sb.key == "gui_chon_viec").set_value(x).run()
    next(c for c in at.checkbox if c.key == f"gui_dong_y_trung_{x}").check().run()
    next(sb for sb in at.selectbox if sb.key == "gui_chon_viec").set_value(y).run()
    assert _nut(at, "⚠️ Gửi lại").disabled is True
    assert ob.lay_viec(eng.sqlite_file, y).trang_thai == ob.UNKNOWN


def test_thao_tac_tren_viec_vua_doi_trang_thai_bao_loi_khong_vo_trang(tmp_path, monkeypatch):
    """P3-6: người gửi nền vừa claim việc ĐÚNG lúc người dùng bấm huỷ (giữa lúc đọc danh sách và lúc xử
    lý nút trong cùng một lượt vẽ) → báo lỗi, không traceback Streamlit."""
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    x, _ = _hai_viec_khong_ro(eng, tmp_path)
    at.run()
    next(sb for sb in at.selectbox if sb.key == "gui_chon_viec").set_value(x).run()
    next(c for c in at.checkbox if c.key == f"gui_huy_xn_{x}").check().run()

    def huy_bi_tranh(db, viec_id):
        raise ob.LoiHangDoi("Việc đang ở trạng thái «📤 Đang chuẩn bị» — không làm được thao tác này.")

    monkeypatch.setattr(ob, "huy", huy_bi_tranh)
    _nut(at, "✖ Huỷ việc gửi").click().run()
    assert not at.exception
    assert any("không làm được" in e.value for e in at.error)


def _kich_ban_chon_dich():
    import streamlit as st

    import ui_gui_sheets

    if st.session_state.get("hien_o_chon", True):
        st.session_state["ket_qua_chon"] = ui_gui_sheets.chon_dich(st.session_state["eng_gia"],
                                                                   key="k")


def test_tu_dong_gui_giu_lua_chon_khi_tab_bi_an_trong_luc_quet(tmp_path):
    """P3-4: bỏ tick «Tự động gửi», ô bị ẩn một lượt (đang quét) → hiện lại vẫn KHÔNG tick."""
    import lich_su

    db = str(tmp_path / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    d, _ = dich_gia(db, tmp_path)
    at = AppTest.from_function(_kich_ban_chon_dich, default_timeout=60)
    at.session_state["eng_gia"] = SimpleNamespace(sqlite_file=db)
    at.run()
    next(sb for sb in at.selectbox if sb.key == "k_dich_gui").set_value(d.id).run()
    next(c for c in at.checkbox if c.key == "k_tu_dong_gui").uncheck().run()
    at.session_state["hien_o_chon"] = False
    at.run()
    at.session_state["hien_o_chon"] = True
    at.run()
    assert at.session_state["ket_qua_chon"] == (d.id, False)


def _kich_ban_banner():
    import streamlit as st

    import ui_gui_sheets

    ui_gui_sheets.banner_lo_dang_chay(st.session_state["eng_gia"], st.session_state["dich_lo"],
                                      "Tên CŨ — KetQuaQuet — Ngang 34 cột", "k")


def test_banner_so_theo_ma_ho_so_khong_theo_nhan(tmp_path):
    """P3-5: hồ sơ đổi tên giữa lô — cùng hồ sơ thì không báo «lựa chọn khác»."""
    import lich_su

    db = str(tmp_path / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    d, _ = dich_gia(db, tmp_path)
    sd.sua_dich(db, d.id, ten="Tên MỚI")
    at = AppTest.from_function(_kich_ban_banner, default_timeout=60)
    at.session_state["eng_gia"] = SimpleNamespace(sqlite_file=db)
    at.session_state["dich_lo"] = d.id
    at.session_state["k_dich_chon"] = d.id
    at.run()
    assert not at.exception and not at.info


def test_gui_thu_cong_tu_lich_su_bo_qua_lan_quet_loi(tmp_path, monkeypatch):
    """P3-7: lần quét LỖI (ảnh chụp V2 trạng thái error) không bao giờ thành dòng gửi Sheets."""
    import ui_gui_sheets

    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    d, _ = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id(),
                    schema=sd.SCHEMA_DOC)
    kq = _kq_ca_that(status="error", note="YouTube chặn truy cập", matches=[])
    kq.bao_cao = _bc(kq)
    job_id = eng.save_job(kq, "youtube")
    tao, bo_qua, _ = ui_gui_sheets.gui_thu_cong(eng, [job_id], d.id, cho_phep_trung=False)
    assert tao == 0 and bo_qua and "lỗi" in bo_qua[0]
    assert ob.ds_viec(eng.sqlite_file) == []
    _dung_nen(eng)


def test_sua_ho_so_doi_khoa_va_link_tao_revision_moi_viec_cu_giu_ghim(tmp_path, monkeypatch):
    """Brief §6: sửa hồ sơ (khoá Google, link/tab) = revision MỚI; việc đã ghim giữ revision cũ."""
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    d, y = dich_gia(eng.sqlite_file, tmp_path, installation_id=eng.installation_id())
    sd.dang_ky_xac_thuc(eng.sqlite_file, "khoa_phu", khoa_gia(tmp_path, ten="phu.json"))
    with sd.ket_noi(eng.sqlite_file, ghi=True) as con:
        vid = ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=["h"] * 34, rows=[["r"] * 34])
    at.run()
    next(sb for sb in at.selectbox if sb.key == f"hs_khoa_moi_{d.id}").set_value("khoa_phu").run()
    _nut(at, "Lưu khoá (revision mới)").click().run()
    assert not at.exception
    d2 = sd.lay_dich(eng.sqlite_file, d.id)
    assert d2.phien_ban == 2 and d2.xac_thuc_ref == "khoa_phu"
    moi = "https://docs.google.com/spreadsheets/d/" + "1" + "m" * 43 + "/edit#gid=77"
    next(ti for ti in at.text_input if ti.key == f"hs_link_moi_{d.id}").set_value(moi).run()
    next(ti for ti in at.text_input if ti.key == f"hs_tab_moi_{d.id}").set_value("Tab mới").run()
    _nut(at, "Lưu link/tab (revision mới)").click().run()
    assert not at.exception
    d3 = sd.lay_dich(eng.sqlite_file, d.id)
    assert (d3.phien_ban, d3.spreadsheet_id, d3.worksheet_id, d3.worksheet_ten) == (
        3, "1" + "m" * 43, 77, "Tab mới")
    v = ob.lay_viec(eng.sqlite_file, vid)
    assert v.dich.phien_ban == 1 and v.dich.xac_thuc_ref == "mac_dinh"   # việc cũ giữ ghim
