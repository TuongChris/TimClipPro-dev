# -*- coding: utf-8 -*-
"""Plugin pytest của bộ đo Cách A: thêm ``--time-quantile $CACH_A_Q`` vào mọi lệnh ``audfprint match`` và ép
``--ncores 2`` (máy đang chạy DEV 8502) — bọc ``Engine._audfprint_cmd`` trong tiến trình pytest, KHÔNG sửa repo.

CACH_A_Q rỗng/không đặt = không thêm -Q (đối chứng). Dùng:
  PYTHONPATH="C:/Dev/Tool_Quet/tools/test/chan_mang;C:/Dev/pc2_test_tools/khop_tung_giay/cach_a" CACH_A_Q=0 \
    <venv python> -B -m pytest -p no:cacheprovider -p qpatch_pytest -m slow <test…>
"""
from __future__ import annotations

import os
import sys

MA = r"C:\Dev\Tool_Quet\TimClipPro"


def pytest_configure(config):
    sys.dont_write_bytecode = True
    if MA not in sys.path:
        sys.path.insert(0, MA)
    import engine
    q = os.environ.get("CACH_A_Q", "").strip()
    goc = engine.Engine._audfprint_cmd

    nhat_ky = os.environ.get("CACH_A_LOG", "").strip()     # bằng chứng: ghi mọi lệnh match thật sự chạy

    def cmd(self, sub, *them, db_file=None):
        lenh = goc(self, sub, *them, db_file=db_file)
        lenh[lenh.index("--ncores") + 1] = "2"
        if sub == "match" and q:
            lenh = [*lenh, "--time-quantile", q]
        if sub == "match" and nhat_ky:
            with open(nhat_ky, "a", encoding="utf-8") as f:
                f.write(" ".join(str(x) for x in lenh[3:]) + "\n")
        return lenh

    engine.Engine._audfprint_cmd = cmd
    config._cach_a_q = q or "mặc định 0.05"


def pytest_report_header(config):
    return f"Cách A: --time-quantile = {getattr(config, '_cach_a_q', '?')}, --ncores 2 (bọc Engine._audfprint_cmd)"
