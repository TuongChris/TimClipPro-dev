# -*- coding: utf-8 -*-
"""`GiamSat.bat` không mang link Google Sheet trong mã nguồn (repo công khai).

Link lấy theo thứ tự: biến môi trường ``SHEET_LINK`` (giống ``ChayMayPhu.bat``), rồi dòng đầu
của ``data\\giam_sat_sheet.txt`` (thư mục ``data/`` không vào git). Không có cả hai thì Giám sát
vẫn chạy (CSV) nhưng KHÔNG ghi Google Sheets. Test hành vi chạy file .bat thật bằng cmd.exe với
một ``cli.py`` GIẢ chỉ ghi lại tham số — không quét, không mạng.
"""
import json
import os
import shutil
import subprocess

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.path.join(GOC, "GiamSat.bat")


def test_khong_con_link_sheet_trong_ma_nguon():
    noi_dung = open(BAT, encoding="utf-8", errors="replace").read()
    # So bằng giá trị bool để pytest KHÔNG in nội dung file (link thật) ra log khi đỏ.
    con_link = "docs.google.com" in noi_dung or "spreadsheets/d/" in noi_dung
    assert not con_link, "GiamSat.bat còn link Google Sheet ghi cứng"
    assert "SHEET_LINK" in noi_dung and r"data\giam_sat_sheet.txt" in noi_dung


CLI_GIA = (
    "import json, os, sys\n"
    "with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'argv.json'), 'w',"
    " encoding='utf-8') as f:\n"
    "    json.dump(sys.argv[1:], f)\n"
)


def _chay(tmp_path, *, env_link=None, file_link=None):
    shutil.copyfile(BAT, tmp_path / "GiamSat.bat")
    (tmp_path / "cli.py").write_text(CLI_GIA, encoding="utf-8")
    if file_link is not None:
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "giam_sat_sheet.txt").write_text(file_link + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.pop("SHEET_LINK", None)
    # Thư mục tạm không có .venv nên file .bat lùi về `py`/`python` THẬT của máy — chúng chỉ
    # chạy `cli.py` giả ở trên (ghi tham số ra argv.json), không quét, không mạng.
    if env_link is not None:
        env["SHEET_LINK"] = env_link
    # Đường dẫn đầy đủ: môi trường có thể đặt NoDefaultCurrentDirectoryInExePath.
    r = subprocess.run(["cmd.exe", "/d", "/c", str(tmp_path / "GiamSat.bat")], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=60)
    return r, json.loads((tmp_path / "argv.json").read_text(encoding="utf-8"))


pytestmark_win = pytest.mark.skipif(
    os.name != "nt" or not (shutil.which("py") or shutil.which("python")),
    reason="file .bat chỉ chạy trên Windows có py/python")

LINK = "https://docs.google.com/spreadsheets/d/" + "Z" * 30 + "/edit?gid=0&x=1"


@pytestmark_win
def test_link_tu_bien_moi_truong(tmp_path):
    r, argv = _chay(tmp_path, env_link=LINK)
    assert argv == ["watch", "--log", "--sheet", LINK]


@pytestmark_win
def test_link_tu_file_rieng_tren_may(tmp_path):
    r, argv = _chay(tmp_path, file_link=LINK)
    assert argv == ["watch", "--log", "--sheet", LINK]


@pytestmark_win
def test_khong_cau_hinh_thi_khong_ghi_sheets(tmp_path):
    r, argv = _chay(tmp_path)
    assert argv == ["watch", "--log"]
    assert "Google Sheet" in r.stdout
