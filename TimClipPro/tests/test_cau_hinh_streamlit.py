# -*- coding: utf-8 -*-
"""`.streamlit/config.toml` cạnh app.py ẩn nút Deploy + menu lập trình viên cho người dùng cuối, trên CẢ hai đường chạy:
DEV (cwd = thư mục mã) và managed (launcher chạy ở state root). Streamlit 1.62 đọc file cạnh script chính
(``streamlit.config.get_config_files``), và file phải nằm trong gói phát hành."""
import os
import tomllib

import dong_goi
import streamlit.config as cfg

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_toolbar_viewer_doc_duoc_khi_cwd_o_noi_khac(tmp_path, monkeypatch):
    with open(os.path.join(GOC, ".streamlit", "config.toml"), "rb") as f:
        assert tomllib.load(f)["client"]["toolbarMode"] == "viewer"
    monkeypatch.chdir(tmp_path)  # như launcher managed: cwd = state root, không phải thư mục mã
    monkeypatch.setattr(cfg, "_main_script_path", os.path.join(GOC, "app.py"))
    assert os.path.join(GOC, ".streamlit", "config.toml") in cfg.get_config_files("config.toml")


def test_config_toml_vao_goi_phat_hanh():
    assert dong_goi.nen_lay(".streamlit/config.toml")
