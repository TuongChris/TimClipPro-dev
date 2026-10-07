# -*- coding: utf-8 -*-
"""Bộ phân giải đường dẫn runtime (docs/MANAGED_RUNTIME_DESIGN.md §4).

* ``legacy`` (mặc định) giữ NGUYÊN công thức cũ: ``TIMCLIP_DATA_DIR or <mã>/data``,
  ``TIMCLIP_OUTPUT_DIR or <mã>/ketqua`` — không di chuyển dữ liệu của ai.
* ``managed`` không bao giờ rơi về ``<release>/data`` hay thư mục hiện hành: thiếu state root,
  thiếu/hỏng ``installation.json``, tham số mâu thuẫn, state root trong OneDrive/ổ mạng → dừng.
* Mã của một release có dấu ``MANAGED_RELEASE.json`` chạy kiểu legacy → dừng (chặn ``.bat`` cũ).
Dữ liệu tổng hợp trong thư mục tạm.
"""
import json
import os

import pytest

import runtime_paths as rp


def _ma(tmp_path, release=False):
    goc = tmp_path / ("rel" if release else "wt")
    ma = goc / "TimClipPro"
    ma.mkdir(parents=True)
    if release:
        (goc / rp.TEN_DAU_RELEASE).write_text(json.dumps({"phien_ban": "2026.10.1"}),
                                              encoding="utf-8")
    return str(ma)


def _state(tmp_path, ten="state"):
    st = tmp_path / ten
    st.mkdir()
    rp.tao_dinh_danh(str(st), installation_root=str(tmp_path / "inst"), workspace="van_phong")
    return str(st)


def test_legacy_mac_dinh_giu_cong_thuc_cu(tmp_path):
    ma = _ma(tmp_path)
    p = rp.resolve({}, ma_nguon=ma)
    assert p.che_do == rp.LEGACY
    assert p.data_dir == os.path.join(ma, "data")
    assert p.out_dir == os.path.join(ma, "ketqua")
    assert p.installation_id == "" and p.state_root == ma


def test_legacy_ton_trong_bien_moi_truong_cu(tmp_path):
    ma = _ma(tmp_path)
    p = rp.resolve({"TIMCLIP_DATA_DIR": str(tmp_path / "d"),
                    "TIMCLIP_OUTPUT_DIR": str(tmp_path / "o")}, ma_nguon=ma)
    assert p.data_dir == str(tmp_path / "d") and p.out_dir == str(tmp_path / "o")


def test_legacy_khong_tao_thu_muc_nao(tmp_path):
    ma = _ma(tmp_path)
    rp.resolve({}, ma_nguon=ma)
    assert os.listdir(ma) == []


def test_managed_lay_moi_thu_tu_state_root(tmp_path):
    ma = _ma(tmp_path, release=True)
    st = _state(tmp_path)
    p = rp.resolve({"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": st}, ma_nguon=ma)
    assert p.che_do == rp.MANAGED and p.state_root == st
    assert p.data_dir == os.path.join(st, "data") and p.out_dir == os.path.join(st, "output")
    dd = rp.doc_dinh_danh(st)
    assert p.installation_id == dd["installation_id"] and len(p.installation_id) == 32
    assert p.workspace == "van_phong"


@pytest.mark.parametrize("env", [
    {"TIMCLIP_RUNTIME_MODE": "managed"},                                   # thiếu state root
    {"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": "tuong_doi"},  # không tuyệt đối
])
def test_managed_thieu_state_root_la_dung(tmp_path, env):
    ma = _ma(tmp_path, release=True)
    with pytest.raises(rp.LoiRuntime):
        rp.resolve(env, ma_nguon=ma)
    assert sorted(os.listdir(os.path.dirname(ma))) == ["MANAGED_RELEASE.json", "TimClipPro"]
    assert os.listdir(ma) == []          # không rơi về <release>/data


def test_managed_thieu_dinh_danh_la_dung(tmp_path):
    ma = _ma(tmp_path, release=True)
    st = tmp_path / "trong"
    st.mkdir()
    with pytest.raises(rp.LoiRuntime, match="installation.json"):
        rp.resolve({"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": str(st)},
                   ma_nguon=ma)
    assert os.listdir(st) == []


def test_managed_dinh_danh_hong_la_dung(tmp_path):
    ma = _ma(tmp_path, release=True)
    st = tmp_path / "hong"
    st.mkdir()
    (st / rp.TEN_DINH_DANH).write_text("{khong phai json", encoding="utf-8")
    with pytest.raises(rp.LoiRuntime):
        rp.resolve({"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": str(st)},
                   ma_nguon=ma)


def test_managed_id_truyen_vao_lech_dinh_danh_la_dung(tmp_path):
    ma = _ma(tmp_path, release=True)
    st = _state(tmp_path)
    with pytest.raises(rp.LoiRuntime, match="khác"):
        rp.resolve({"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": st,
                    "TIMCLIP_INSTALLATION_ID": "0" * 32}, ma_nguon=ma)


def test_managed_bien_data_cu_mau_thuan_la_dung(tmp_path):
    ma = _ma(tmp_path, release=True)
    st = _state(tmp_path)
    with pytest.raises(rp.LoiRuntime, match="mâu thuẫn"):
        rp.resolve({"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": st,
                    "TIMCLIP_DATA_DIR": str(tmp_path / "khac")}, ma_nguon=ma)


def test_che_do_la_bi_tu_choi(tmp_path):
    with pytest.raises(rp.LoiRuntime):
        rp.resolve({"TIMCLIP_RUNTIME_MODE": "ManagedX"}, ma_nguon=_ma(tmp_path))


def test_release_managed_chay_kieu_legacy_la_dung(tmp_path):
    """`.bat` cũ hay `python app.py` bấm tay trong thư mục release: không được tạo `<release>/data`."""
    ma = _ma(tmp_path, release=True)
    with pytest.raises(rp.LoiRuntime, match="launcher"):
        rp.resolve({}, ma_nguon=ma)
    assert os.listdir(ma) == []


def test_state_root_trong_onedrive_bi_chan_o_managed_canh_bao_o_legacy(tmp_path):
    od = tmp_path / "OneDrive"
    od.mkdir()
    st = od / "state"
    st.mkdir()
    rp.tao_dinh_danh(str(st), installation_root=str(tmp_path / "inst"))
    env = {"OneDrive": str(od)}
    with pytest.raises(rp.LoiRuntime, match="OneDrive"):
        rp.resolve({**env, "TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": str(st)},
                   ma_nguon=_ma(tmp_path, release=True))
    ma = od / "repo" / "TimClipPro"
    ma.mkdir(parents=True)
    p = rp.resolve(env, ma_nguon=str(ma))
    assert p.che_do == rp.LEGACY and any("OneDrive" in c for c in p.canh_bao)


@pytest.mark.parametrize("duong_dan", [r"\\may-chu\chia-se\state", "//may-chu/chia-se/state"])
def test_duong_dan_mang_bi_nhan_dien(duong_dan):
    assert any("mạng" in c for c in rp.kiem_duong_dan_trang_thai(duong_dan, {}))


def test_ten_thu_muc_dong_bo_dam_may_bi_nhan_dien(tmp_path):
    for ten in ("Dropbox", "Google Drive", "OneDrive - Cong Ty"):
        assert rp.kiem_duong_dan_trang_thai(str(tmp_path / ten / "x"), {}), ten
    assert rp.kiem_duong_dan_trang_thai(str(tmp_path / "TimClipProData"), {}) == []


def test_tao_dinh_danh_khong_ghi_de_va_moi_lan_mot_id_moi(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    da = rp.tao_dinh_danh(str(a), installation_root="C:/x")
    db = rp.tao_dinh_danh(str(b), installation_root="C:/x")
    assert da["installation_id"] != db["installation_id"]
    with pytest.raises(rp.LoiRuntime, match="đã có"):
        rp.tao_dinh_danh(str(a), installation_root="C:/x")
    assert rp.doc_dinh_danh(str(a)) == da


def test_resolve_khong_doc_moi_truong_luc_import():
    """Không có I/O lúc import: hằng số module không phụ thuộc biến môi trường."""
    import importlib
    import sys
    cu = sys.modules.pop("runtime_paths")
    try:
        os.environ["TIMCLIP_RUNTIME_MODE"] = "managed"
        moi = importlib.import_module("runtime_paths")
        assert moi.LEGACY == "legacy"
    finally:
        os.environ.pop("TIMCLIP_RUNTIME_MODE", None)
        sys.modules["runtime_paths"] = cu
