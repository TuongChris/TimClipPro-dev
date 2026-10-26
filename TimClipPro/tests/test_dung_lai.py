# -*- coding: utf-8 -*-
"""Test tín hiệu dừng và khả năng giữ kết quả quét dở dang."""

import signal
import threading
from types import SimpleNamespace

import pytest

import dung_lai
from dung_lai import YeuCauDung
from engine import ScanResult
from watch import MucTheoDoi, WatchList, chay_giam_sat


def test_file_dung_kich_hoat(tmp_path):
    path = tmp_path / "DUNG"
    path.write_text("", encoding="utf-8")

    assert YeuCauDung(file_dung=str(path)).can_dung() is True


def test_engine_cancel_event_kich_hoat():
    engine = SimpleNamespace(cancel_event=threading.Event())
    yeu_cau = YeuCauDung(engine)
    engine.cancel_event.set()

    assert yeu_cau.can_dung() is True


def test_dat_truyen_yeu_cau_xuong_engine():
    engine = SimpleNamespace(cancel_event=threading.Event())

    YeuCauDung(engine).dat()

    assert engine.cancel_event.is_set()


def test_co_noi_bo_duoc_kiem_truoc_file(monkeypatch):
    yeu_cau = YeuCauDung(file_dung="không được kiểm tra")
    yeu_cau.dat()
    monkeypatch.setattr(
        dung_lai.os.path,
        "exists",
        lambda path: pytest.fail("Không được chạm file khi cờ đã bật"),
    )

    assert yeu_cau.can_dung() is True


def test_ctrl_c_lan_dau_dat_co_lan_hai_thoat_ngay(monkeypatch):
    handlers = {}
    monkeypatch.setattr(
        dung_lai.signal,
        "signal",
        lambda sig, handler: handlers.setdefault(sig, handler),
    )
    yeu_cau = YeuCauDung()
    yeu_cau.bat_tin_hieu()

    handlers[signal.SIGINT](signal.SIGINT, None)
    assert yeu_cau.can_dung() is True
    with pytest.raises(KeyboardInterrupt):
        handlers[signal.SIGINT](signal.SIGINT, None)


def test_bat_tin_hieu_khong_co_sigterm_van_chay(monkeypatch):
    da_dang_ky = []
    monkeypatch.delattr(dung_lai.signal, "SIGTERM", raising=False)
    monkeypatch.setattr(
        dung_lai.signal,
        "signal",
        lambda sig, handler: da_dang_ky.append(sig),
    )

    YeuCauDung().bat_tin_hieu()

    assert da_dang_ky == [signal.SIGINT]


def test_don_file_dung_sau_khi_xong(tmp_path):
    path = tmp_path / "DUNG"
    path.write_text("", encoding="utf-8")
    yeu_cau = YeuCauDung(file_dung=str(path))

    yeu_cau.don_file_dung()
    yeu_cau.don_file_dung()

    assert not path.exists()


def test_dung_giua_chung_van_xuat_ket_qua(engine, monkeypatch, tmp_path):
    videos = [
        SimpleNamespace(id=f"x{i}", title=f"Video {i}", url=f"u{i}")
        for i in range(1, 4)
    ]
    da_quet = []
    da_xuat = []

    class DungSauVideoDau:
        def __init__(self):
            self.so_lan = 0

        def can_dung(self):
            self.so_lan += 1
            return self.so_lan >= 2

    monkeypatch.setattr(engine, "list_jobs", lambda limit: [])
    monkeypatch.setattr(
        engine,
        "scan_youtube",
        lambda url, progress=None: (
            da_quet.append(url)
            or ScanResult(source_name=url, matches=[object()])
        ),
    )
    csv_path = str(tmp_path / "mot-phan.csv")
    monkeypatch.setattr(
        engine,
        "export_csv_ngang",
        lambda ket: da_xuat.extend(ket) or csv_path,
    )

    bao_cao = chay_giam_sat(
        engine,
        WatchList(muc=[MucTheoDoi("kenh", "kenh-1")]),
        lister=lambda url, limit: videos,
        dung_lai=DungSauVideoDau(),
    )

    assert da_quet == ["u1"]
    assert len(da_xuat) == 1
    assert bao_cao.csv_path == csv_path
    assert any("còn 2 video chưa quét" in dong for dong in bao_cao.loi)


def test_dung_truoc_video_dau_khong_tao_csv(engine, monkeypatch):
    class DungNgay:
        @staticmethod
        def can_dung():
            return True

    monkeypatch.setattr(engine, "list_jobs", lambda limit: [])
    monkeypatch.setattr(
        engine,
        "scan_youtube",
        lambda *args, **kwargs: pytest.fail("Không được quét"),
    )
    monkeypatch.setattr(
        engine,
        "export_csv_ngang",
        lambda ket: pytest.fail("Không được tạo CSV"),
    )
    video = SimpleNamespace(id="x1", title="Video", url="u1")

    bao_cao = chay_giam_sat(
        engine,
        WatchList(muc=[MucTheoDoi("kenh", "kenh-1")]),
        lister=lambda url, limit: [video],
        dung_lai=DungNgay(),
    )

    assert bao_cao.quet_moi == 0
    assert bao_cao.csv_path == ""


def test_dung_lai_none_van_chay_binh_thuong(engine, monkeypatch, tmp_path):
    videos = [
        SimpleNamespace(id=f"x{i}", title=f"Video {i}", url=f"u{i}")
        for i in range(1, 3)
    ]
    da_quet = []
    monkeypatch.setattr(engine, "list_jobs", lambda limit: [])
    monkeypatch.setattr(
        engine,
        "scan_youtube",
        lambda url, progress=None: (
            da_quet.append(url)
            or ScanResult(source_name=url)
        ),
    )
    monkeypatch.setattr(
        engine,
        "export_csv_ngang",
        lambda ket: str(tmp_path / "ket-qua.csv"),
    )

    bao_cao = chay_giam_sat(
        engine,
        WatchList(muc=[MucTheoDoi("kenh", "kenh-1")]),
        lister=lambda url, limit: videos,
        dung_lai=None,
    )

    assert da_quet == ["u1", "u2"]
    assert bao_cao.quet_moi == 2


def test_cli_dung_tao_file_ma_khong_khoi_tao_engine(
    tmp_path,
    monkeypatch,
    capsys,
):
    import cli

    path = tmp_path / "data" / "DUNG"
    monkeypatch.setattr("sys.argv", ["cli.py", "dung"])
    monkeypatch.setattr(cli, "_file_dung_mac_dinh", lambda: str(path))
    monkeypatch.setattr(
        cli,
        "Engine",
        lambda: pytest.fail("Lệnh dung không cần khởi tạo Engine"),
    )

    cli.main()

    assert path.is_file()
    assert "Đã gửi yêu cầu dừng" in capsys.readouterr().out


def test_cli_watch_luon_don_file_dung_sau_khi_xong(
    tmp_path,
    monkeypatch,
):
    import cli

    da_don = []

    class DungGia:
        def __init__(self, engine=None, file_dung="", moc_bat_dau=None):
            self.file_dung = file_dung

        def bat_tin_hieu(self):
            pass

        def don_file_dung(self):
            da_don.append(self.file_dung)

    engine_gia = SimpleNamespace(
        data_dir=str(tmp_path),
        config=SimpleNamespace(ncores=1),
    )
    wl = WatchList(muc=[MucTheoDoi("link", "https://youtu.be/dQw4w9WgXcQ")])
    monkeypatch.setattr("sys.argv", ["cli.py", "watch"])
    monkeypatch.setattr(cli, "Engine", lambda: engine_gia)
    monkeypatch.setattr(cli, "YeuCauDung", DungGia)
    monkeypatch.setattr(cli.watch, "doc_watchlist", lambda path: wl)
    monkeypatch.setattr(
        cli.watch,
        "chay_giam_sat",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("lỗi bất ngờ")
        ),
    )

    with pytest.raises(RuntimeError, match="lỗi bất ngờ"):
        cli.main()

    assert da_don == [str(tmp_path / "DUNG")]


# --- Audit C-12: file DUNG CŨ (có từ TRƯỚC khi lượt bắt đầu) không được dừng oan lượt mới. ---
# `cli.py dung` khi không có lượt nào chạy, hay lượt bị kill trước `finally: don_file_dung()`,
# để lại file; lượt Watch theo lịch kế tiếp từng quét 0 video, ghi «Đã dừng theo yêu cầu», mã 1.


def _file_dung_cu(tmp_path, tuoi_s=3600):
    import os
    import time

    path = tmp_path / "DUNG"
    path.write_text("Yêu cầu dừng từ CLI.\n", encoding="utf-8")
    cu = time.time() - tuoi_s
    os.utime(path, (cu, cu))
    return path


def test_file_dung_cu_hon_moc_bat_dau_bi_bo_qua(tmp_path):
    import time

    path = _file_dung_cu(tmp_path)
    yeu_cau = YeuCauDung(file_dung=str(path), moc_bat_dau=time.time())

    assert yeu_cau.can_dung() is False
    assert dung_lai.mtime_file_dung_cu(str(path), yeu_cau.moc_bat_dau) is not None
    # Không xoá file lúc bắt đầu: `finally` cuối lượt mới dọn.
    assert path.exists()


def test_dung_moi_sau_moc_ghi_de_file_cu_van_dung(tmp_path):
    import time

    path = _file_dung_cu(tmp_path)
    yeu_cau = YeuCauDung(file_dung=str(path), moc_bat_dau=time.time() - 60)
    assert yeu_cau.can_dung() is False

    # `cli.py dung` trong lúc lượt chạy ghi đè file → mtime mới → dừng.
    path.write_text("Yêu cầu dừng từ CLI.\n", encoding="utf-8")

    assert yeu_cau.can_dung() is True
    assert dung_lai.mtime_file_dung_cu(str(path), yeu_cau.moc_bat_dau) is None


# Review audit P3: mtime file (đồng hồ hệ thống theo nhịp ~15,6 ms trên Windows, FAT 2 s) và
# time.time() không cùng độ phân giải. File dừng ghi CÙNG nhịp với mốc bắt đầu có thể mang mtime
# nhỏ hơn mốc vài ms → từng bị xếp là «yêu cầu cũ» (test đầu-cuối dưới đây chập chờn ~7–10%).
# Mốc cố định + os.utime: không dựa vào may rủi thời gian.
_MOC_CO_DINH = 1_700_000_000.0


def _file_dung_mtime(tmp_path, mtime):
    import os

    path = tmp_path / "DUNG"
    path.write_text("Yêu cầu dừng từ CLI.\n", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


@pytest.mark.parametrize("lech_s", [0.0, 0.0156, 0.5, 1.9])
def test_file_dung_ghi_sat_moc_bat_dau_van_dung(tmp_path, lech_s):
    path = _file_dung_mtime(tmp_path, _MOC_CO_DINH - lech_s)
    yeu_cau = YeuCauDung(file_dung=str(path), moc_bat_dau=_MOC_CO_DINH)

    assert dung_lai.mtime_file_dung_cu(str(path), _MOC_CO_DINH) is None
    assert yeu_cau.can_dung() is True


@pytest.mark.parametrize("tuoi_s", [2.5, 60.0, 3600.0])
def test_file_dung_cu_hon_dung_sai_van_bi_bo_qua(tmp_path, tuoi_s):
    assert tuoi_s > dung_lai.DUNG_SAI_MTIME_S
    path = _file_dung_mtime(tmp_path, _MOC_CO_DINH - tuoi_s)
    yeu_cau = YeuCauDung(file_dung=str(path), moc_bat_dau=_MOC_CO_DINH)

    assert dung_lai.mtime_file_dung_cu(str(path), _MOC_CO_DINH) == pytest.approx(_MOC_CO_DINH - tuoi_s)
    assert yeu_cau.can_dung() is False


def test_cli_watch_bo_qua_file_dung_cu_tu_truoc_khi_bat_dau(tmp_path, monkeypatch, capsys):
    import cli
    from watch import MucTheoDoi as Muc, WatchList as DanhSach

    # Không đụng handler tín hiệu thật của tiến trình pytest.
    monkeypatch.setattr(dung_lai.signal, "signal", lambda *a, **k: None)
    _file_dung_cu(tmp_path)
    engine_gia = SimpleNamespace(
        data_dir=str(tmp_path),
        out_dir=str(tmp_path / "ketqua"),
        config=SimpleNamespace(ncores=1),
        cancel_event=None,
    )
    wl = DanhSach(muc=[Muc("link", "https://youtu.be/abcDEF12345")])
    monkeypatch.setattr("sys.argv", ["cli.py", "watch"])
    monkeypatch.setattr(cli, "Engine", lambda *a, **k: engine_gia)
    monkeypatch.setattr(cli.watch, "doc_watchlist", lambda path: wl)
    thay = {}

    def chay_gia(engine, wl, progress=None, **kw):
        # Điểm `_thuc_hien_giam_sat` hỏi can_dung() trước video đầu tiên.
        thay["can_dung_luc_bat_dau"] = kw["dung_lai"].can_dung()
        return SimpleNamespace(tom_tat=lambda: "tóm tắt giả", ban=False, chan_youtube="", loi=[])

    monkeypatch.setattr(cli.watch, "chay_giam_sat", chay_gia)

    cli.main()

    assert thay["can_dung_luc_bat_dau"] is False, (
        "file DUNG có từ 1 giờ TRƯỚC khi lượt Watch bắt đầu vẫn dừng lượt mới ngay trước video đầu"
    )
    assert "Bỏ qua yêu cầu dừng cũ" in capsys.readouterr().out
    assert not (tmp_path / "DUNG").exists()


def test_cli_watch_dung_gui_luc_dang_nap_engine_van_dung_luot(tmp_path, monkeypatch):
    import cli
    from watch import MucTheoDoi as Muc, WatchList as DanhSach

    monkeypatch.setattr(dung_lai.signal, "signal", lambda *a, **k: None)
    engine_gia = SimpleNamespace(
        data_dir=str(tmp_path),
        out_dir=str(tmp_path / "ketqua"),
        config=SimpleNamespace(ncores=1),
        cancel_event=None,
    )

    def engine_dang_nap(*a, **k):
        # `cli.py dung` gõ trong lúc lượt đang nạp kho (sau mốc bắt đầu của lượt).
        (tmp_path / "DUNG").write_text("Yêu cầu dừng từ CLI.\n", encoding="utf-8")
        return engine_gia

    wl = DanhSach(muc=[Muc("link", "https://youtu.be/abcDEF12345")])
    monkeypatch.setattr("sys.argv", ["cli.py", "watch"])
    monkeypatch.setattr(cli, "Engine", engine_dang_nap)
    monkeypatch.setattr(cli.watch, "doc_watchlist", lambda path: wl)
    thay = {}

    def chay_gia(engine, wl, progress=None, **kw):
        import os

        # Ca xấu nhất của đồng hồ Windows, ghim tất định: file ghi trong lúc nạp (CÙNG nhịp với
        # mốc) nhưng mtime ra trước mốc một nhịp 15,6 ms.
        moc = kw["dung_lai"].moc_bat_dau
        os.utime(tmp_path / "DUNG", (moc - 0.0156, moc - 0.0156))
        thay["can_dung"] = kw["dung_lai"].can_dung()
        return SimpleNamespace(tom_tat=lambda: "tóm tắt giả", ban=False, chan_youtube="", loi=[])

    monkeypatch.setattr(cli.watch, "chay_giam_sat", chay_gia)

    cli.main()

    assert thay["can_dung"] is True
