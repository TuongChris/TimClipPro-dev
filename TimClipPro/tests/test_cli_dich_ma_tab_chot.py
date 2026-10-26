# -*- coding: utf-8 -*-
"""``cli.py dich`` hiện mã tab ĐÃ CHỐT của hồ sơ theo tên — giống giao diện (audit B-10).

Dữ liệu synthetic: ``lichsu.db`` tạm (TIMCLIP_DATA_DIR), khoá dịch vụ GIẢ. Hồ sơ «P» tạo theo tên
(``worksheet_id=None``, tab «KetQuaQuet»). Người gửi chốt mã tab ở request ghi đầu của revision
(``dich_gui_tab_chot``, MR-P1-02) rồi gửi vào ĐÚNG tab đó kể cả khi tab đổi tên — CLI phải nói như
giao diện (``ui_gui_sheets._ve_ho_so`` dùng ``gid_da_chot``), không in «chưa chốt».
"""
from __future__ import annotations

import argparse
import os
import sys

import cli
import lich_su
import sheet_destinations as sd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from outbox_gia import khoa_gia  # noqa: E402  (đồ giả dùng chung của dự án)

ID_A = "1" + "a" * 43


def _dong_dich(tmp_path, monkeypatch, capsys, chot: bool) -> str:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("TIMCLIP_STATE_ROOT", raising=False)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "out"))
    db = str(data / "lichsu.db")
    lich_su.dam_bao_luoc_do(db)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    d = sd.tao_dich(db, ten="P", spreadsheet_id=ID_A, worksheet_id=None, worksheet_ten="KetQuaQuet",
                    schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    if chot:
        with sd.ket_noi(db, ghi=True) as con:
            sd._chot_tab(con, d.id, d.phien_ban, worksheet_id=555, worksheet_ten="KetQuaQuet")
        assert sd.lay_dich(db, d.id).gid_da_chot == 555          # tiền đề: giao diện hiện 555
    cli._lenh_dich_va_gui(argparse.Namespace(lenh="dich"))
    ra = capsys.readouterr().out
    dong = [x for x in ra.splitlines() if x.startswith(d.id)]
    assert len(dong) == 1, ra
    return dong[0]


def test_cli_dich_hien_ma_tab_da_chot_cua_ho_so_theo_ten(tmp_path, monkeypatch, capsys):
    dong = _dong_dich(tmp_path, monkeypatch, capsys, chot=True)
    assert "chưa chốt" not in dong, f"CLI nói chưa chốt dù đã chốt 555: {dong!r}"
    assert "555" in dong, dong


def test_cli_dich_ho_so_theo_ten_chua_gui_noi_chot_o_lan_gui_dau(tmp_path, monkeypatch, capsys):
    dong = _dong_dich(tmp_path, monkeypatch, capsys, chot=False)
    assert "chốt ở lần gửi đầu" in dong, dong
