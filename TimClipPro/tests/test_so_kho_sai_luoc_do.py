# -*- coding: utf-8 -*-
"""Audit C-6: sổ đăng ký kho (khos.json) đúng cú pháp JSON nhưng SAI lược đồ.

docs/DATA_MIGRATION_AND_RECOVERY.md §4.9 bảo người dùng (không lập trình) tự sửa khos.json khi sổ
hỏng. Sửa tay dễ ra JSON hợp lệ nhưng sai lược đồ: ``{}``, ``null``, mục thiếu ``db`` / ``ten``.
Hành vi ĐÚNG: giống sổ hỏng — Engine vẫn dựng được, có cảnh báo khởi động nêu rõ khos.json,
không kho nào đang dùng; CLI báo gọn (không traceback); giao diện hiện cảnh báo, không vỡ.
Mã hiện tại: KeyError/TypeError thô ngay trong Engine.__init__ (engine.py _init_kho/_ap_dung_kho).

Dữ liệu tổng hợp hoàn toàn, chỉ trong tmp_path; không mạng.
"""

import json
from pathlib import Path

import pytest

SAI_LUOC_DO = {
    "doi_tuong_rong": {},
    "null": None,
    "muc_thieu_db": {"dang_dung": "A", "danh_sach": [{"ten": "A", "thu_muc": ""}]},
    "muc_thieu_ten": {"dang_dung": "A", "danh_sach": [{"thu_muc": "", "db": "kho_a.pklz"}]},
}

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def _ghi_so(data_dir: Path, noi_dung) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "khos.json").write_text(json.dumps(noi_dung, ensure_ascii=False),
                                        encoding="utf-8")


def _moi_truong(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "ketqua"
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(out_dir))
    return data_dir, out_dir


@pytest.mark.parametrize("ten_ca", sorted(SAI_LUOC_DO))
def test_engine_khoi_dong_duoc_va_canh_bao_khi_khos_sai_luoc_do(tmp_path, monkeypatch, ten_ca):
    from engine import Engine

    data_dir, out_dir = _moi_truong(tmp_path, monkeypatch)
    _ghi_so(data_dir, SAI_LUOC_DO[ten_ca])

    try:
        eng = Engine(root=str(tmp_path), data_dir=str(data_dir), out_dir=str(out_dir))
    except (KeyError, TypeError, AttributeError) as e:
        pytest.fail(f"[{ten_ca}] Engine() vỡ với lỗi thô {type(e).__name__}: {e!r} — "
                    "phải đi đường cảnh báo khởi động / SoKhoHong như sổ hỏng")

    assert any("khos.json" in c for c in eng.canh_bao_khoi_dong), (
        f"[{ten_ca}] không có cảnh báo khởi động nào nêu khos.json: {eng.canh_bao_khoi_dong!r}")
    assert eng.kho_dang_dung == ""
    # Thanh bên gọi list_khos() mỗi lần vẽ lại: cũng không được vỡ.
    eng.list_khos()


@pytest.mark.parametrize("ten_ca", ["doi_tuong_rong", "muc_thieu_db"])
def test_cli_bao_gon_khi_khos_sai_luoc_do(tmp_path, monkeypatch, capsys, ten_ca):
    import cli

    data_dir, _ = _moi_truong(tmp_path, monkeypatch)
    _ghi_so(data_dir, SAI_LUOC_DO[ten_ca])
    monkeypatch.setattr("sys.argv", ["cli.py", "dondep", "--xem-truoc"])

    try:
        cli.main()
    except SystemExit:
        pass  # thoát có kiểm soát (vd. «LỖI SỔ ĐĂNG KÝ KHO», mã 1) là chấp nhận được
    except (KeyError, TypeError, AttributeError) as e:
        pytest.fail(f"[{ten_ca}] cli.main() để lọt lỗi thô {type(e).__name__}: {e!r} "
                    "(người dùng thấy traceback, không biết là do sổ đăng ký kho)")

    loi = capsys.readouterr().err
    assert "khos.json" in loi or "SỔ ĐĂNG KÝ KHO" in loi, loi


def test_giao_dien_hien_canh_bao_khi_khos_sai_luoc_do(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    data_dir, _ = _moi_truong(tmp_path, monkeypatch)
    _ghi_so(data_dir, SAI_LUOC_DO["doi_tuong_rong"])

    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()

    assert not at.exception, [getattr(x, "value", x) for x in at.exception]
    assert any("khos.json" in (w.value or "") for w in at.warning), \
        [w.value for w in at.warning]


@pytest.mark.parametrize("ten_ca", ["doi_tuong_rong", "muc_thieu_db", "muc_thieu_ten"])
def test_so_sai_luoc_do_chan_quet_va_khong_bi_ghi_de(tmp_path, monkeypatch, ten_ca):
    """Như sổ hỏng: không tự dựng «Kho mặc định» từ data/db.pklz, không quét (SoKhoHong),
    không ghi đè file người dùng đang sửa tay — kể cả khi bấm «Tạo kho»."""
    from engine import Engine, SoKhoHong
    from luu_tru import LoiDuLieu

    data_dir, out_dir = _moi_truong(tmp_path, monkeypatch)
    _ghi_so(data_dir, SAI_LUOC_DO[ten_ca])
    (data_dir / "db.pklz").write_bytes(b"kho cu gia")
    truoc = (data_dir / "khos.json").read_bytes()

    eng = Engine(root=str(tmp_path), data_dir=str(data_dir), out_dir=str(out_dir))

    assert eng.kho_dang_dung == ""
    with pytest.raises(SoKhoHong):
        eng.require(can_db=True)
    with pytest.raises(LoiDuLieu):
        eng.add_kho("Kho mới")
    assert (data_dir / "khos.json").read_bytes() == truoc


def test_dang_dung_tro_kho_khong_con_trong_so_thi_canh_bao_khoi_dong(tmp_path, monkeypatch):
    """Audit C-15: sổ ĐÚNG lược đồ nhưng lệch nội dung — sửa tay xoá bớt một kho mà quên sửa
    «dang_dung». Engine vẫn lùi về kho đầu danh sách (giao diện còn chọn lại được), nhưng phải
    để lại cảnh báo khởi động nêu cả kho trong sổ lẫn kho thật đang mở — trước đây im lặng,
    ``cli.py youtube/file`` quét bằng kho khác mà không ai biết. Sổ KHÔNG được tự sửa: Watch
    dựa vào chính độ lệch sổ↔Engine để từ chối quét nhầm kho (TCP-08)."""
    from engine import Engine

    data_dir, out_dir = _moi_truong(tmp_path, monkeypatch)
    _ghi_so(data_dir, {
        "dang_dung": "DaXoa",
        "danh_sach": [
            {"ten": "A", "thu_muc": "", "db": "kho_a.pklz", "id": "a" * 32},
            {"ten": "B", "thu_muc": "", "db": "kho_b.pklz", "id": "b" * 32},
        ],
    })
    truoc = (data_dir / "khos.json").read_bytes()

    eng = Engine(root=str(tmp_path), data_dir=str(data_dir), out_dir=str(out_dir))

    assert eng.kho_dang_dung == "A"
    assert any("DaXoa" in c and "«A»" in c for c in eng.canh_bao_khoi_dong), (
        "sổ chọn kho «DaXoa» (không còn trong danh sách) mà Engine lặng lẽ dùng «A»: "
        f"{eng.canh_bao_khoi_dong!r}")
    assert (data_dir / "khos.json").read_bytes() == truoc


def test_so_nhat_quan_khong_co_canh_bao_kho(tmp_path, monkeypatch):
    """Đối chứng C-15: «dang_dung» trỏ đúng một kho trong sổ → không cảnh báo nào về kho."""
    from engine import Engine

    data_dir, out_dir = _moi_truong(tmp_path, monkeypatch)
    _ghi_so(data_dir, {
        "dang_dung": "B",
        "danh_sach": [
            {"ten": "A", "thu_muc": "", "db": "kho_a.pklz", "id": "a" * 32},
            {"ten": "B", "thu_muc": "", "db": "kho_b.pklz", "id": "b" * 32},
        ],
    })

    eng = Engine(root=str(tmp_path), data_dir=str(data_dir), out_dir=str(out_dir))

    assert eng.kho_dang_dung == "B"
    assert not any("khos.json" in c for c in eng.canh_bao_khoi_dong), eng.canh_bao_khoi_dong
