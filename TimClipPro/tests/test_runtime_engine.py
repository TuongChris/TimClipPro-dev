# -*- coding: utf-8 -*-
"""Engine/CLI/Sheets đi qua bộ phân giải đường dẫn runtime (docs/MANAGED_RUNTIME_DESIGN.md §4).

* legacy: không đổi gì so với trước (mặc định ``<mã>/data``); ``TIMCLIP_DATA_DIR`` nay được CLI tôn
  trọng như app (trước đây ``Engine()`` của CLI bỏ qua biến này — AUD-004 — nên app và Watch dùng
  hai ``tool.lock`` khác nhau).
* managed: Engine lấy dữ liệu ở state root, không tạo gì trong thư mục release; cấu hình sai thì
  Engine KHÔNG dựng được (không migrate, không tạo DB ở chỗ đoán).
Dữ liệu tổng hợp.
"""
import json
import os

import pytest

import runtime_paths as rp

GOC_MA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _release(tmp_path):
    goc = tmp_path / "releases" / "2026.10.1"
    ma = goc / "TimClipPro"
    ma.mkdir(parents=True)
    (goc / rp.TEN_DAU_RELEASE).write_text(json.dumps({"phien_ban": "2026.10.1"}),
                                          encoding="utf-8")
    return str(ma)


def _state(tmp_path):
    st = tmp_path / "state"
    st.mkdir()
    rp.tao_dinh_danh(str(st), installation_root=str(tmp_path / "inst"))
    return str(st)


def _xoa_env(monkeypatch):
    for bien in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_DATA_DIR",
                 "TIMCLIP_OUTPUT_DIR", "TIMCLIP_INSTALLATION_ID"):
        monkeypatch.delenv(bien, raising=False)


def test_engine_legacy_ton_trong_timclip_data_dir_khi_khong_truyen_tham_so(tmp_path, monkeypatch):
    from engine import Engine
    _xoa_env(monkeypatch)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "o"))
    eng = Engine(root=GOC_MA)
    assert eng.data_dir == str(tmp_path / "d") and eng.out_dir == str(tmp_path / "o")
    assert eng.runtime.che_do == rp.LEGACY


def test_engine_tham_so_tuong_minh_van_thang(tmp_path, monkeypatch):
    from engine import Engine
    _xoa_env(monkeypatch)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "env"))
    eng = Engine(root=GOC_MA, data_dir=str(tmp_path / "ro"), out_dir=str(tmp_path / "out"))
    assert eng.data_dir == str(tmp_path / "ro")


def test_engine_managed_du_lieu_o_state_root_release_khong_bi_ghi(tmp_path, monkeypatch):
    from engine import Engine
    _xoa_env(monkeypatch)
    ma, st = _release(tmp_path), _state(tmp_path)
    monkeypatch.setenv("TIMCLIP_RUNTIME_MODE", "managed")
    monkeypatch.setenv("TIMCLIP_STATE_ROOT", st)
    eng = Engine(root=ma)
    assert eng.data_dir == os.path.join(st, "data") and eng.out_dir == os.path.join(st, "output")
    assert os.path.isfile(os.path.join(st, "data", "lichsu.db"))
    assert os.listdir(ma) == []
    # Định danh máy trong lịch sử = installation.json (đối chiếu ngay khi dựng Engine).
    assert eng.installation_id() == rp.doc_dinh_danh(st)["installation_id"]


def test_engine_managed_thieu_state_root_khong_dung_va_khong_tao_gi(tmp_path, monkeypatch):
    from engine import Engine
    _xoa_env(monkeypatch)
    ma = _release(tmp_path)
    monkeypatch.setenv("TIMCLIP_RUNTIME_MODE", "managed")
    with pytest.raises(rp.LoiRuntime):
        Engine(root=ma)
    assert os.listdir(ma) == []


def test_engine_managed_lich_su_cua_may_khac_bi_chan(tmp_path, monkeypatch):
    """State root bị chép từ máy khác (lịch sử mang installation_id khác) → không dựng Engine."""
    import sheet_destinations as sd
    from engine import Engine
    _xoa_env(monkeypatch)
    ma, st = _release(tmp_path), _state(tmp_path)
    monkeypatch.setenv("TIMCLIP_RUNTIME_MODE", "managed")
    monkeypatch.setenv("TIMCLIP_STATE_ROOT", st)
    import lich_su
    os.makedirs(os.path.join(st, "data"))
    db = os.path.join(st, "data", "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi="0" * 32)
    with pytest.raises(sd.LoiDichGui, match="cài đặt khác"):
        Engine(root=ma)


def test_engine_release_chay_kieu_legacy_bi_tu_choi(tmp_path, monkeypatch):
    from engine import Engine
    _xoa_env(monkeypatch)
    ma = _release(tmp_path)
    with pytest.raises(rp.LoiRuntime, match="launcher"):
        Engine(root=ma)
    assert os.listdir(ma) == []


def test_cli_file_dung_theo_bo_phan_giai(tmp_path, monkeypatch):
    import cli
    _xoa_env(monkeypatch)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "d"))
    assert cli._file_dung_mac_dinh() == os.path.join(str(tmp_path / "d"), "DUNG")


def test_khoa_google_mac_dinh_legacy_canh_ma_managed_trong_state(tmp_path, monkeypatch):
    import sheets
    _xoa_env(monkeypatch)
    assert sheets.SheetsExporter().key_path == os.path.join(GOC_MA, "google_key.json")
    st = _state(tmp_path)
    p = rp.resolve({"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": st},
                   ma_nguon=_release(tmp_path))
    assert p.khoa_google_mac_dinh == os.path.join(st, "secrets", "google_key.json")


def test_thu_muc_data_mac_dinh_dung_chung_cong_thuc(tmp_path, monkeypatch):
    from engine import thu_muc_data_mac_dinh
    _xoa_env(monkeypatch)
    assert thu_muc_data_mac_dinh() == rp.resolve().data_dir
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "x"))
    assert thu_muc_data_mac_dinh() == str(tmp_path / "x")


def test_app_managed_cau_hinh_sai_bao_loi_ro_va_khong_tao_du_lieu(tmp_path, monkeypatch):
    """Giao diện: managed thiếu state root → trang báo lỗi tiếng Việt, không có ``data/`` nào."""
    from streamlit.testing.v1 import AppTest
    _xoa_env(monkeypatch)
    monkeypatch.setenv("TIMCLIP_RUNTIME_MODE", "managed")
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(os.path.join(GOC_MA, "app.py"), default_timeout=120).run()
    assert not at.exception
    assert any("Không khởi động được TimClip Pro" in e.value for e in at.error)
    assert not os.path.exists(os.path.join(tmp_path, "data"))
