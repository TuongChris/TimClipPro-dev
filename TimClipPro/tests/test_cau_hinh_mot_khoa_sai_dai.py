# -*- coding: utf-8 -*-
"""Audit C-5 (tổng hợp, không mạng, không dữ liệu thật).

MỘT giá trị sai dải trong ``data/cau_hinh.json`` (JSON hợp lệ, đúng kiểu, chỉ trượt
``Config.validate``) từng làm ``Engine._nap_cau_hinh`` vứt TOÀN BỘ cấu hình người dùng:
đường dẫn cookie, top_n, các ô giao diện (sheet_link, kho_dir...) đều về mặc định, và lần
«Lưu cấu hình» kế tiếp ghi đè mặc định lên file của người dùng.

Hành vi ĐÚNG (phán quyết tranh cãi C-5): hạ cấp theo TỪNG khoá — chỉ khoá sai về mặc định
và được nêu tên (kèm lý do) trong MỘT cảnh báo nói rõ các thiết lập khác vẫn giữ; các khoá
hợp lệ khác giữ nguyên; lưu lại không làm mất giá trị của người dùng.
"""

import json
import os

import pytest

from cau_hinh import GIA_TRI_GIAO_DIEN_MAC_DINH, TEN_FILE
from engine import Config, Engine

# Đường dẫn cookie GIẢ — không tạo file, không đọc gì; chỉ là một chuỗi trong cấu hình.
COOKIE_GIA = "C:/khong_ton_tai/cookies_gia_audit_c5.txt"
SHEET_GIA = "https://docs.google.com/spreadsheets/d/GIA_AUDIT_C5"
KHO_GIA = "C:/khong_ton_tai/kho_gia_audit_c5"


@pytest.fixture
def thu_muc(tmp_path, monkeypatch):
    for bien in list(os.environ):
        if bien.startswith("TIMCLIP_"):
            monkeypatch.delenv(bien, raising=False)
    data = tmp_path / "data"
    out = tmp_path / "out"
    data.mkdir()
    return tmp_path, data, out


def _ghi_cau_hinh_nguoi_dung(data_dir, chunk_s):
    du_lieu = {
        # Người dùng sửa tay một con số (RUNBOOK cho phép) -> sai dải validate.
        "chunk_s": chunk_s,
        # Các giá trị HỢP LỆ khác của người dùng.
        "ytdlp_cookiefile": COOKIE_GIA,
        "ytdlp_cookies_browser": "firefox",
        "top_n": 3,
        "sheet_link": SHEET_GIA,
        "kho_dir": KHO_GIA,
    }
    (data_dir / TEN_FILE).write_text(json.dumps(du_lieu, ensure_ascii=False), encoding="utf-8")


def _dung_engine(goc, data, out):
    return Engine(root=str(goc), data_dir=str(data), out_dir=str(out))


def test_mot_khoa_sai_khong_xoa_cac_khoa_hop_le_khac(thu_muc):
    goc, data, out = thu_muc
    _ghi_cau_hinh_nguoi_dung(data, chunk_s=50)  # chunk_s phải > 60

    eng = _dung_engine(goc, data, out)

    # Cảnh báo phải có (và nêu đúng khoá sai).
    assert any("chunk_s" in msg for msg in eng.canh_bao_khoi_dong), eng.canh_bao_khoi_dong
    # Chỉ khoá sai về mặc định.
    assert eng.config.chunk_s == Config().chunk_s
    # Các khoá hợp lệ của người dùng phải còn nguyên — đặc biệt cookie (quét YouTube cần nó).
    assert eng.config.ytdlp_cookiefile == COOKIE_GIA
    assert eng.config.ytdlp_cookies_browser == "firefox"
    assert eng.config.top_n == 3
    # Các ô giao diện app.py gieo từ cau_hinh_da_luu cũng phải còn.
    assert eng.cau_hinh_da_luu.get("sheet_link") == SHEET_GIA
    assert eng.cau_hinh_da_luu.get("kho_dir") == KHO_GIA


def test_luu_sau_khi_nap_loi_khong_ghi_de_gia_tri_nguoi_dung(thu_muc):
    goc, data, out = thu_muc
    _ghi_cau_hinh_nguoi_dung(data, chunk_s=50)

    eng = _dung_engine(goc, data, out)
    # Mô phỏng app.py:81-87 (gieo session_state từ cau_hinh_da_luu) + app.py «Lưu cấu hình».
    giao_dien = {
        khoa: (eng.cau_hinh_da_luu.get(khoa, md)
               if type(eng.cau_hinh_da_luu.get(khoa, md)) is type(md) else md)
        for khoa, md in GIA_TRI_GIAO_DIEN_MAC_DINH.items()
    }
    try:
        eng.luu_cau_hinh(giao_dien)
    except Exception:  # noqa: BLE001 — chặn lưu khi cấu hình khởi động lỗi cũng là hành vi đúng
        pass

    sau = json.loads((data / TEN_FILE).read_text(encoding="utf-8"))
    assert sau.get("ytdlp_cookiefile") == COOKIE_GIA, sau.get("ytdlp_cookiefile")
    assert sau.get("ytdlp_cookies_browser") == "firefox"
    assert sau.get("top_n") == 3
    assert sau.get("sheet_link") == SHEET_GIA
    assert sau.get("kho_dir") == KHO_GIA


def test_cau_hinh_sau_khi_nap_van_qua_validate_va_canh_bao_noi_ro_phan_giu(thu_muc):
    goc, data, out = thu_muc
    _ghi_cau_hinh_nguoi_dung(data, chunk_s=50)

    eng = _dung_engine(goc, data, out)

    eng.config.validate()
    canh_bao = [msg for msg in eng.canh_bao_khoi_dong if "chunk_s" in msg]
    assert len(canh_bao) == 1, eng.canh_bao_khoi_dong
    assert "chunk_s phải lớn hơn 60 giây" in canh_bao[0]  # lý do của validate
    assert "giữ nguyên" in canh_bao[0]
    assert not any("đang dùng mặc định" in msg for msg in eng.canh_bao_khoi_dong)
    # Khoá bị trả về mặc định không còn trong cau_hinh_da_luu (ô giao diện vẫn còn).
    assert "chunk_s" not in eng.cau_hinh_da_luu


def test_nhieu_khoa_sai_doc_lap_deu_duoc_neu_ten_khoa_khac_van_giu(thu_muc):
    goc, data, out = thu_muc
    du_lieu = {
        "chunk_s": 50,                    # phải > 60
        "ytdlp_sleep_requests_s": 90.0,   # phải 0..60
        "luoi_resample": [95.0],          # gõ kiểu phần trăm, phải 0.5..2.0
        "ytdlp_cookiefile": COOKIE_GIA,
        "ytdlp_player_clients": ["tv", "web"],
        "top_n": 2,
        "kho_dir": KHO_GIA,
    }
    (data / TEN_FILE).write_text(json.dumps(du_lieu), encoding="utf-8")

    eng = _dung_engine(goc, data, out)

    eng.config.validate()
    mac_dinh = Config()
    assert eng.config.chunk_s == mac_dinh.chunk_s
    assert eng.config.ytdlp_sleep_requests_s == mac_dinh.ytdlp_sleep_requests_s
    assert eng.config.luoi_resample == mac_dinh.luoi_resample
    assert eng.config.ytdlp_cookiefile == COOKIE_GIA
    assert eng.config.ytdlp_player_clients == ["tv", "web"]
    assert eng.config.top_n == 2
    assert eng.cau_hinh_da_luu.get("kho_dir") == KHO_GIA
    canh_bao = [msg for msg in eng.canh_bao_khoi_dong if "giữ nguyên" in msg]
    assert len(canh_bao) == 1, eng.canh_bao_khoi_dong
    for khoa in ("chunk_s", "ytdlp_sleep_requests_s", "luoi_resample"):
        assert khoa in canh_bao[0]


def test_luu_sau_khi_nap_mot_phan_giu_ban_goc_trong_bak(thu_muc):
    goc, data, out = thu_muc
    _ghi_cau_hinh_nguoi_dung(data, chunk_s=50)
    goc_file = json.loads((data / TEN_FILE).read_text(encoding="utf-8"))

    eng = _dung_engine(goc, data, out)
    eng.luu_cau_hinh({"sheet_link": eng.cau_hinh_da_luu["sheet_link"],
                      "kho_dir": eng.cau_hinh_da_luu["kho_dir"]})

    sau = json.loads((data / TEN_FILE).read_text(encoding="utf-8"))
    assert sau["chunk_s"] == Config().chunk_s  # chỉ khoá sai được ghi mặc định
    assert sau["ytdlp_cookiefile"] == COOKIE_GIA
    bak = json.loads((data / (TEN_FILE + ".bak")).read_text(encoding="utf-8"))
    assert bak == goc_file
