# -*- coding: utf-8 -*-
"""`python cli.py youtube-doctor` — chẩn đoán chỉ đọc; mặc định KHÔNG gọi mạng, không in cookie."""

import json
import sys

import pytest
import yt_dlp

import cli
import youtube_doctor
from ytdlp_gia import BOT, YdlKichBan, info_mau

BI_MAT = "GIA_TRI_BI_MAT_GIA_d0c7"


def _data(tmp_path, cookie_noi_dung=None):
    data = tmp_path / "data"
    data.mkdir()
    cfg = {"network_timeout_s": 45, "ytdlp_sleep_requests_s": 1.0,
           "ytdlp_player_clients": ["", "android", "tv"]}
    if cookie_noi_dung is not None:
        p = tmp_path / "cookies.txt"
        p.write_text(cookie_noi_dung, encoding="utf-8")
        cfg["ytdlp_cookiefile"] = str(p)
    (data / "cau_hinh.json").write_text(json.dumps(cfg), encoding="utf-8")
    return str(data)


_COOKIE = ("# Netscape HTTP Cookie File\n"
           + "\t".join([".youtube.com", "TRUE", "/", "TRUE", "9999999999", "LOGIN_INFO",
                        BI_MAT]) + "\n"
           + "\t".join([".youtube.com", "TRUE", "/", "TRUE", "9999999999", "SAPISID",
                        BI_MAT]) + "\n")


def test_mac_dinh_khong_goi_mang_va_khong_lo_cookie(tmp_path, monkeypatch, capsys):
    ydl = YdlKichBan()
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    data = _data(tmp_path, _COOKIE)
    kq = youtube_doctor.chan_doan(data)
    assert ydl.goi == [] and ydl.opts == [], "mặc định không mở phiên yt-dlp nào"
    assert kq["mang"]["da_goi"] is False and kq["google"] == "không gọi"
    assert kq["yt_dlp"]["phien_ban"] and "js_runtime" in kq
    assert kq["cookie"]["cau_truc_hop_le"] and kq["cookie"]["co_cookie_dang_nhap"]
    assert kq["cau_hinh_mang"]["network_timeout_s"] == 45
    ma = youtube_doctor.chay(data)
    ra = capsys.readouterr().out
    assert ma == 0 and BI_MAT not in ra and BI_MAT not in json.dumps(kq, ensure_ascii=False)
    for ten in ("LOGIN_INFO", "SAPISID"):
        assert ten not in ra


def test_kiem_mang_chi_khi_nguoi_dung_yeu_cau_va_chi_mot_request(tmp_path, monkeypatch):
    ydl = YdlKichBan(info={"*": lambda _p, m: info_mau(m)})
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    kq = youtube_doctor.chan_doan(_data(tmp_path), url_mang="https://youtu.be/vid00000001")
    assert ydl.dem("info") == 1
    assert kq["mang"]["da_goi"] is True and kq["mang"]["ket_qua"] == "OK"


def test_kiem_mang_video_cong_khai_khong_ket_luan_cookie_duoc_chap_nhan(tmp_path, monkeypatch):
    """Cookie có TÊN đăng nhập + một video công khai lấy được: video công khai không cần đăng nhập, nên chưa chứng
    minh YouTube nhận tài khoản (PR #8 vòng 2)."""
    import truy_cap_youtube as t
    import ytdlp_chung

    monkeypatch.setattr(ytdlp_chung, "kha_nang_js", lambda: ytdlp_chung.KhaNangJs(
        True, node=r"C:\gia\nodejs\node.exe", node_phien_ban="24.21.0", ejs_phien_ban="0.8.0"))
    ydl = YdlKichBan(info={"*": lambda _p, m: {**info_mau(m), "availability": "public"}})
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    kq = youtube_doctor.chan_doan(_data(tmp_path, _COOKIE), url_mang="https://youtu.be/vid00000001")
    assert kq["mang"]["ket_qua"] == "OK" and ydl.dem("info") == 1
    assert kq["mang"]["cookie_duoc_chap_nhan"] == t.COOKIE_PHIEN_CHUA_RO
    assert BI_MAT not in json.dumps(kq, ensure_ascii=False, default=str)


def test_kiem_mang_bi_bot_check_bao_dung_loai_va_ma_3(tmp_path, monkeypatch, capsys):
    ydl = YdlKichBan(info={"*": BOT})
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    data = _data(tmp_path)
    ma = youtube_doctor.chay(data, url_mang="https://youtu.be/vid00000001")
    assert ma == 3 and ydl.dem("info") == 1
    assert "BOT_CHALLENGE" in capsys.readouterr().out


def test_cli_goi_youtube_doctor_khong_dung_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", _data(tmp_path))
    monkeypatch.setattr(cli, "Engine", lambda: pytest.fail("không được dựng Engine"))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", YdlKichBan())
    monkeypatch.setattr(sys, "argv", ["cli.py", "youtube-doctor"])
    with pytest.raises(SystemExit) as ei:
        cli.main()
    assert ei.value.code == 0


def test_khoa_api_youtube_ngoai_tuyen_che_thu_muc_nguoi_dung(tmp_path, monkeypatch, capsys):
    """D-51: khối khoá YouTube Data API chỉ đọc file (mặc định của test = chưa có khoá), không gọi Google; đường dẫn
    che tên người dùng Windows như ghi chú."""
    import youtube_api

    monkeypatch.setattr(youtube_api, "duong_dan_khoa_api",
                        lambda d: r"C:\Users\TenRieng\TimClip\secrets\youtube_api_key.txt")
    data = _data(tmp_path)
    kq = youtube_doctor.chan_doan(data)
    assert kq["google"] == "không gọi" and kq["mang"]["da_goi"] is False
    assert kq["khoa_api_youtube"] == {"duong_dan": r"~\TimClip\secrets\youtube_api_key.txt",
                                      "co_file": False, "dung_dang": False, "ly_do": ""}
    assert youtube_doctor.chay(data) == 0
    ra = capsys.readouterr().out
    assert "Khoá YouTube Data API: CHƯA có file" in ra and "TenRieng" not in ra


@pytest.mark.parametrize("noi_dung, co_file, dung_dang", [
    ("# chỉ có chú thích\n", True, False),
    ("AIza" + "GiaKhongBiMat" + "0" * 22 + "\n", True, True),  # gia-khong-bi-mat: đúng dạng, rõ là giả
])
def test_khoa_api_youtube_co_file_sai_dang_hay_dung_dang_khong_lo_khoa(tmp_path, monkeypatch, capsys,
                                                                     khoa_api_that, noi_dung, co_file, dung_dang):
    import youtube_api

    f = tmp_path / "khoa_thu" / youtube_api.TEN_FILE_KHOA
    f.parent.mkdir()
    f.write_text(noi_dung, encoding="utf-8")
    monkeypatch.setattr(youtube_api, "duong_dan_khoa_api", lambda d: str(f))
    data = _data(tmp_path)
    kq = youtube_doctor.chan_doan(data)
    k = kq["khoa_api_youtube"]
    assert (k["co_file"], k["dung_dang"], bool(k["ly_do"])) == (co_file, dung_dang, not dung_dang)
    youtube_doctor.chay(data)
    ra = capsys.readouterr().out
    assert ("đúng dạng" if dung_dang else "SAI dạng") in ra
    assert "GiaKhongBiMat" not in ra + json.dumps(kq, ensure_ascii=False)
