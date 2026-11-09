# -*- coding: utf-8 -*-
"""Mã thoát của `cli.py youtube|file` (audit 09/11): quét lỗi / việc gửi bị chặn vì báo cáo → mã 1, như Watch."""

import collections
import sys
import types

import pytest

import cli
import outbox


class _EngineGia:
    def __init__(self, status):
        self.status = status
        self.config = types.SimpleNamespace(ncores=1)
        self.canh_bao_khoi_dong = []
        self.phien_youtube_cuoi = None

    def scan_many(self, nguon, kieu, progress):
        return [
            types.SimpleNamespace(
                source_name=n,
                status=self.status,
                note="Không tải được audio",
                matches=[],
                chan_doan=None,
                quet_mot_phan=False,
                bao_cao=None,
            )
            for n in nguon
        ]

    def export_csv(self, ket):
        return "(không có)"


def _chay(monkeypatch, tmp_path, status):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"")
    monkeypatch.setattr(cli, "Engine", lambda: _EngineGia(status))
    monkeypatch.setattr(sys, "argv", ["cli.py", "file", str(f)])
    cli.main()


def test_quet_file_loi_thi_thoat_ma_1(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit) as ei:
        _chay(monkeypatch, tmp_path, "error")
    assert ei.value.code == 1
    assert "LỖI: Không tải được audio" in capsys.readouterr().out


def test_quet_file_xong_khong_khop_van_ma_0(monkeypatch, tmp_path):
    _chay(monkeypatch, tmp_path, "ok")  # âm tính hợp lệ không phải lỗi


def test_viec_gui_bi_chan_vi_bao_cao_la_loi():
    tt = collections.Counter({outbox.SENT: 1, outbox.BLOCKED_REPORT: 1})
    assert cli._in_tong_ket_gui(tt, 3) == 1
    assert cli._in_tong_ket_gui(collections.Counter({outbox.SENT: 2}), 3) == 0
