# -*- coding: utf-8 -*-
"""Audit B-2: Watch/CLI với --destination phải preflight file khoá TRƯỚC khi quét.

Đường --sheet (nhap_link_cu đọc khoá) và giao diện (chot_cho_lo -> outbox.kiem_khoa_cuc_bo) đều dừng
trước khi quét khi khoá Google không dùng được. Đường hồ sơ đích (--destination / y_dinh_gui) thì
không: lượt vẫn quét, lịch sử ghi video là đã quét (lượt Watch sau bỏ qua), mỗi việc gửi rơi vào
BLOCKED_CONFIG và phải bấm «Thử gửi lại» từng việc. Chính chú thích ở watch.py (đích phải chốt trước
khi liệt kê/quét) đòi hỏi điều ngược lại.

Dữ liệu tổng hợp hoàn toàn: khoá GIẢ trong tmp_path, quét giả (không mạng, không audio thật).
"""

from types import SimpleNamespace

import pytest

import outbox
from outbox_gia import CongGia, dich_gia, khoa_gia
from watch import MucTheoDoi, WatchList, chay_giam_sat, id_da_quet


def _lam_hong_khoa(tmp_path, kieu):
    """Khoá của binding «mac_dinh» (tmp_path/khoa.json) không còn dùng được."""
    p = tmp_path / "khoa.json"
    if kieu == "mat_file":
        p.unlink()
    else:   # file khoá bị thay bằng khoá của một tài khoản dịch vụ KHÁC
        khoa_gia(tmp_path, email="khac@du-an-khac.invalid", kid="k9")
    return str(p)


def _quet_ghi_lai(engine, da_quet):
    """Quét giả nhưng LƯU như quét thật (save_job xếp việc gửi cùng giao dịch)."""
    from test_watch import _quet_luu
    return _quet_luu(engine, da_quet=da_quet)


@pytest.mark.parametrize("kieu", ["mat_file", "khac_tai_khoan"])
def test_watch_y_dinh_gui_khoa_hong_thi_dung_truoc_khi_quet(engine, monkeypatch, tmp_path, kieu):
    _d, y = dich_gia(engine.sqlite_file, tmp_path, installation_id=engine.installation_id())
    _lam_hong_khoa(tmp_path, kieu)
    ly_do_khoa = outbox.kiem_khoa_cuc_bo(engine.sqlite_file, y.dich)
    assert ly_do_khoa, "setup: khoá phải đang hỏng"

    da_quet = []
    monkeypatch.setattr(engine, "scan_youtube", _quet_ghi_lai(engine, da_quet))
    monkeypatch.setattr(engine, "export_csv_ngang", lambda ket: str(tmp_path / "kq.csv"))
    cong = CongGia()
    bc = chay_giam_sat(
        engine,
        WatchList(muc=[MucTheoDoi("kenh", "kenh-1")]),
        lister=lambda url, limit: [SimpleNamespace(id="x1", title="Một", url="u1")],
        y_dinh_gui=y,
        tao_cong=lambda: cong,
        cho_gui_s=3,
    )

    viec = outbox.ds_viec(engine.sqlite_file)
    hau_qua = (f"preflight khoá báo «{ly_do_khoa}» nhưng lượt vẫn quét {da_quet}; "
               f"quet_moi={bc.quet_moi}; lịch sử đã quét={sorted(id_da_quet(engine))}; "
               f"việc gửi={[(v.trang_thai, v.loi) for v in viec]}; loi={bc.loi}")
    # Hành vi đúng: dừng lượt TRƯỚC khi liệt kê/quét như đường --sheet và giao diện.
    assert da_quet == [], hau_qua
    assert bc.quet_moi == 0, hau_qua
    assert bc.sheets_ok is False and bc.loi, hau_qua
    assert not id_da_quet(engine), hau_qua   # lịch sử không được ghi video là đã quét
    assert viec == [], hau_qua


def test_cli_watch_destination_khoa_mat_thi_khong_quet(engine, monkeypatch, tmp_path):
    """`cli.py watch --destination <id>` (đường Task Scheduler) với file khoá đã mất."""
    import cli
    import watch

    d, _y = dich_gia(engine.sqlite_file, tmp_path, installation_id=engine.installation_id())
    _lam_hong_khoa(tmp_path, "mat_file")

    class _DungGia:
        def __init__(self, *a, **k):
            pass

        def bat_tin_hieu(self):
            pass

        def don_file_dung(self):
            pass

        def can_dung(self):
            return False

    wl = WatchList(muc=[MucTheoDoi("link", "https://youtu.be/dQw4w9WgXcQ")])
    da_quet = []
    monkeypatch.setattr(cli, "YeuCauDung", _DungGia)
    monkeypatch.setattr(cli.watch, "doc_watchlist", lambda path: wl)
    monkeypatch.setattr(engine, "scan_youtube", _quet_ghi_lai(engine, da_quet))
    monkeypatch.setattr(engine, "export_csv_ngang", lambda ket: str(tmp_path / "kq.csv"))
    goc = watch.chay_giam_sat
    cong = CongGia()
    # Chỉ rút ngắn thời gian chờ người gửi và thay cổng Google bằng cổng giả (không mạng).
    monkeypatch.setattr(watch, "chay_giam_sat",
                        lambda *a, **k: goc(*a, **{**k, "cho_gui_s": 3, "tao_cong": lambda: cong}))
    a = SimpleNamespace(file="watchlist.json", destination=d.id, sheet="", dang_doc=False,
                        gioi_han=0, quet_lai=False)

    with pytest.raises(SystemExit):
        cli._chay_lenh_watch(a, engine)

    viec = outbox.ds_viec(engine.sqlite_file)
    hau_qua = (f"lượt CLI vẫn quét {da_quet}; lịch sử đã quét={sorted(id_da_quet(engine))}; "
               f"việc gửi={[(v.trang_thai, v.loi) for v in viec]}")
    assert da_quet == [], hau_qua
    assert not id_da_quet(engine), hau_qua   # lịch sử không được ghi video là đã quét
    assert viec == [], hau_qua


@pytest.mark.parametrize("kieu", ["mat_file", "khac_tai_khoan"])
def test_cli_youtube_destination_khoa_hong_thi_khong_quet(engine, monkeypatch, tmp_path, capsys, kieu):
    """`cli.py youtube <link> --destination <id>`: cùng lỗ hổng — phải báo LỖI CẤU HÌNH trước khi quét."""
    import cli

    d, _y = dich_gia(engine.sqlite_file, tmp_path, installation_id=engine.installation_id())
    _lam_hong_khoa(tmp_path, kieu)
    monkeypatch.setattr(cli, "Engine", lambda: engine)
    monkeypatch.setattr(engine, "scan_many",
                        lambda *a, **k: pytest.fail("Không được quét khi khoá của đích hỏng"))
    monkeypatch.setattr("sys.argv", ["cli.py", "youtube", "https://youtu.be/dQw4w9WgXcQ",
                                     "--destination", d.id])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1
    assert "LỖI CẤU HÌNH" in capsys.readouterr().err
    assert not id_da_quet(engine)
    assert outbox.ds_viec(engine.sqlite_file) == []
