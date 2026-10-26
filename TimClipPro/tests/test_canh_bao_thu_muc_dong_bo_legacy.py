# -*- coding: utf-8 -*-
"""Audit C-8: chế độ legacy/DEV — cảnh báo «thư mục dữ liệu nằm trong OneDrive/thư mục đồng bộ/ổ mạng»
do ``runtime_paths.resolve()`` tính ra phải TỚI được người dùng.

Thiết kế (docs/MANAGED_RUNTIME_DESIGN.md §4): state root dưới OneDrive/Dropbox/ổ mạng → ``managed`` từ chối,
``legacy`` CHỈ CẢNH BÁO. Kênh duy nhất được vẽ ra là ``Engine.canh_bao_khoi_dong`` (app.py thanh bên,
cli.py stderr). Dữ liệu synthetic, thư mục tạm, không mạng.
"""

import os
from pathlib import Path

import runtime_paths

GOC = str(Path(__file__).resolve().parents[1])
APP_PY = Path(GOC) / "app.py"


def _moi_truong_onedrive(tmp_path, monkeypatch):
    """Giống PC2 DEV-only: launcher đặt TIMCLIP_DATA_DIR, và thư mục đó nằm trong OneDrive."""
    od = tmp_path / "OneDrive"
    data_dir = od / "TimClipPro_DevState" / "data"
    out_dir = tmp_path / "ketqua"
    data_dir.mkdir(parents=True)
    for bien in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_INSTALLATION_ID",
                 "OneDriveConsumer", "OneDriveCommercial"):
        monkeypatch.delenv(bien, raising=False)
    monkeypatch.setenv("OneDrive", str(od))
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(out_dir))
    return data_dir, out_dir


def test_canh_bao_onedrive_cua_runtime_toi_canh_bao_khoi_dong(tmp_path, monkeypatch):
    from engine import Engine

    data_dir, out_dir = _moi_truong_onedrive(tmp_path, monkeypatch)

    # Tiền đề: bộ phân giải ĐÃ nhận ra vấn đề (không phải lỗi thiết lập test).
    rp = runtime_paths.resolve(ma_nguon=GOC)
    assert rp.che_do == runtime_paths.LEGACY
    assert rp.canh_bao, "tiền đề hỏng: resolve() không cảnh báo thư mục OneDrive"

    # Cách app.py dựng Engine (data_dir/out_dir từ biến môi trường).
    eng = Engine(root=GOC, data_dir=os.environ["TIMCLIP_DATA_DIR"],
                 out_dir=os.environ["TIMCLIP_OUTPUT_DIR"])
    assert os.path.normcase(eng.data_dir) == os.path.normcase(str(data_dir))
    assert eng.runtime.canh_bao == rp.canh_bao

    hien_ra = " | ".join(eng.canh_bao_khoi_dong)
    for canh in rp.canh_bao:
        assert canh in eng.canh_bao_khoi_dong, (
            "Cảnh báo đường dẫn của runtime_paths bị bỏ rơi — người dùng không được báo dữ liệu "
            f"(lichsu.db/outbox) nằm trong thư mục đồng bộ. runtime.canh_bao={rp.canh_bao!r}; "
            f"canh_bao_khoi_dong={eng.canh_bao_khoi_dong!r} ({hien_ra})")


def test_thanh_ben_app_hien_canh_bao_onedrive(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    _moi_truong_onedrive(tmp_path, monkeypatch)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    canh_bao_thanh_ben = [w.value for w in at.sidebar.warning]
    assert any("OneDrive" in c or "đồng bộ" in c for c in canh_bao_thanh_ben), (
        f"Thanh bên không có cảnh báo OneDrive/đồng bộ; thanh bên hiện: {canh_bao_thanh_ben!r}")


def test_data_dir_truyen_tay_ngoai_onedrive_khong_muon_canh_bao(tmp_path, monkeypatch):
    """Cảnh báo theo ĐÚNG thư mục Engine dùng: runtime phân giải ra thư mục OneDrive nhưng Engine được
    truyền data_dir cục bộ → không cảnh báo nhầm."""
    from engine import Engine

    _moi_truong_onedrive(tmp_path, monkeypatch)
    cuc_bo = tmp_path / "cuc_bo" / "data"
    eng = Engine(root=GOC, data_dir=str(cuc_bo), out_dir=str(tmp_path / "ketqua"))
    assert not any("OneDrive" in c or "đồng bộ" in c for c in eng.canh_bao_khoi_dong), (
        eng.canh_bao_khoi_dong)


def test_data_dir_truyen_tay_trong_onedrive_van_canh_bao(tmp_path, monkeypatch):
    """Ngược lại: biến môi trường trỏ chỗ an toàn, data_dir truyền tay nằm trong OneDrive → vẫn cảnh báo."""
    from engine import Engine

    _moi_truong_onedrive(tmp_path, monkeypatch)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "cuc_bo" / "data"))
    trong_od = tmp_path / "OneDrive" / "khac" / "data"
    eng = Engine(root=GOC, data_dir=str(trong_od), out_dir=str(tmp_path / "ketqua"))
    assert not eng.runtime.canh_bao
    assert any("OneDrive" in c for c in eng.canh_bao_khoi_dong), eng.canh_bao_khoi_dong
