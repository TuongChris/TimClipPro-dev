# -*- coding: utf-8 -*-
"""Twitch 1440p (D-44): danh sách chất lượng xin QUA proxy + cookie twitch.tv, video tải THẲNG. Không mạng — proxy là
socket nghe trên 127.0.0.1, yt-dlp là bản giả."""

from __future__ import annotations

import os
import socket

import pytest
import yt_dlp

import tai_video_goc as tv
import ytdlp_chung as yc

TWITCH = "https://www.twitch.tv/videos/12345678901"
YOUTUBE = "https://www.youtube.com/watch?v=abcdefghij1"
MAT_KHAU = "MatKhauBiMat123"

_COOKIE = (
    "# Netscape HTTP Cookie File\n"
    ".twitch.tv\tTRUE\t/\tTRUE\t4102444800\tauth-token\ttoken-gia\n"
    ".twitch.tv\tTRUE\t/\tTRUE\t4102444800\tunique_id\tabc\n"
    ".youtube.com\tTRUE\t/\tTRUE\t4102444800\tSID\tkhong-duoc-dung\n"
    ".google.com\tTRUE\t/\tTRUE\t4102444800\tHSID\tkhong-duoc-dung\n"
)


@pytest.fixture
def proxy_nghe():
    """Cổng proxy giả đang nghe (chỉ cần nhận kết nối TCP)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(5)
    yield s.getsockname()[1]
    s.close()


def _cong_dong() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    cong = s.getsockname()[1]
    s.close()
    return cong


def _file(tmp_path, ten, noi_dung):
    p = tmp_path / ten
    p.write_text(noi_dung, encoding="utf-8")
    return str(p)


@pytest.mark.parametrize(
    "url, la",
    [
        (TWITCH, True),
        ("https://twitch.tv/videos/1", True),
        ("https://clips.twitch.tv/TenClip", True),
        ("https://m.twitch.tv/videos/1", True),
        ("https://eviltwitch.tv/videos/1", False),
        ("https://twitch.tv.evil.com/videos/1", False),
        (YOUTUBE, False),
        ("khong phai link", False),
    ],
)
def test_la_link_twitch(url, la):
    assert yc.la_link_twitch(url) is la


def test_doc_proxy_dang_nghe(tmp_path, proxy_nghe):
    url = f"http://windscribe:{MAT_KHAU}@127.0.0.1:{proxy_nghe}"
    mk = yc.MoKhoaTwitch(file_proxy=_file(tmp_path, "p.txt", "\ufeff" + url + "\r\n"))
    assert mk.co() and mk.doc_proxy() == url


def test_proxy_tat_bao_ro_khong_lo_mat_khau(tmp_path):
    cong = _cong_dong()
    mk = yc.MoKhoaTwitch(
        file_proxy=_file(
            tmp_path, "p.txt", f"http://windscribe:{MAT_KHAU}@127.0.0.1:{cong}"
        )
    )
    with pytest.raises(yc.LoiMoKhoaTwitch) as e:
        mk.doc_proxy()
    assert "Windscribe" in str(e.value) and f"127.0.0.1:{cong}" in str(e.value)
    assert MAT_KHAU not in str(e.value) and "windscribe:" not in str(e.value)


@pytest.mark.parametrize(
    "noi_dung",
    [
        "",
        "10.0.0.1:8080",
        "ftp://a:b@1.2.3.4:5",
        "http://khong-co-cong",
        "http://:8080",
    ],
)
def test_file_proxy_sai_dang(tmp_path, noi_dung):
    with pytest.raises(yc.LoiMoKhoaTwitch) as e:
        yc.MoKhoaTwitch(file_proxy=_file(tmp_path, "p.txt", noi_dung)).doc_proxy()
    assert "proxy" in str(e.value)


def test_file_proxy_khong_co(tmp_path):
    with pytest.raises(yc.LoiMoKhoaTwitch, match="Không đọc được file proxy"):
        yc.MoKhoaTwitch(file_proxy=str(tmp_path / "khong_co.txt")).doc_proxy()


def test_khong_cau_hinh_thi_khong_lam_gi():
    mk = yc.MoKhoaTwitch()
    assert not mk.co() and mk.doc_proxy() == "" and mk.cookie_twitch() == []
    assert not yc.MoKhoaTwitch(file_proxy="  ", file_cookie='""').co()


def test_cookie_chi_lay_twitch(tmp_path):
    ds = yc.MoKhoaTwitch(
        file_cookie='"' + _file(tmp_path, "c.txt", _COOKIE) + '"'
    ).cookie_twitch()
    assert sorted(c.name for c in ds) == ["auth-token", "unique_id"]


def test_cookie_khong_dang_nhap_bao_ro(tmp_path):
    chi_khach = "".join(d for d in _COOKIE.splitlines(True) if "auth-token" not in d)
    with pytest.raises(yc.LoiMoKhoaTwitch, match="auth-token") as e:
        yc.MoKhoaTwitch(file_cookie=_file(tmp_path, "c.txt", chi_khach)).cookie_twitch()
    assert "token-gia" not in str(e.value) and "abc" not in str(e.value)


def test_cookie_file_hong(tmp_path):
    with pytest.raises(yc.LoiMoKhoaTwitch, match="Không đọc được file cookie Twitch"):
        yc.MoKhoaTwitch(
            file_cookie=_file(tmp_path, "c.txt", "khong phai cookies.txt\n")
        ).cookie_twitch()


# ---------------------------------------------------------------- tải hai bước trong tai_nhieu
class _Hu(list):
    def set_cookie(self, c):
        self.append(c)


class YdlGia:
    """``yt_dlp.YoutubeDL`` giả: ghi lại tuỳ chọn + cách gọi từng đối tượng; tải = ghi file theo ``outtmpl``."""

    doi_tuong: list = []

    def __init__(self, opts):
        self.opts, self.cookiejar, self.goi = opts, _Hu(), []
        YdlGia.doi_tuong.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def _tai(self, ma):
        ten = (
            self.opts["outtmpl"]
            .replace("%(title).150B", "Phat lai")
            .replace("%(id)s", ma)
            .replace("%(ext)s", "mp4")
        )
        with open(ten, "wb") as f:
            f.write(b"video")
        return {
            "id": ma,
            "title": "Phat lai",
            "height": 1440,
            "fps": 60,
            "vcodec": "avc1.640033",
            "acodec": "mp4a",
        }

    def extract_info(self, url, download=True, process=True):
        self.goi.append(("extract_info", download, process))
        if not download:
            return {
                "id": url[-11:],
                "title": "Phat lai",
                "formats": [{"format_id": "1440p60"}],
            }
        return self._tai(url[-11:])

    def process_ie_result(self, ie, download=True):
        self.goi.append(("process_ie_result", ie["id"], download))
        return self._tai(ie["id"])


@pytest.fixture
def gia(monkeypatch):
    YdlGia.doi_tuong = []
    monkeypatch.setattr(yt_dlp, "YoutubeDL", YdlGia)
    monkeypatch.setattr(tv.shutil, "which", lambda ten: "C:/ffmpeg.exe")
    return YdlGia


def _mo_khoa(tmp_path, cong):
    return yc.MoKhoaTwitch(
        file_proxy=_file(
            tmp_path, "p.txt", f"http://windscribe:{MAT_KHAU}@127.0.0.1:{cong}"
        ),
        file_cookie=_file(tmp_path, "c.txt", _COOKIE),
    )


def test_twitch_xin_danh_sach_qua_proxy_tai_thang(gia, tmp_path, proxy_nghe):
    kq = tv.tai_nhieu(
        [TWITCH], str(tmp_path / "ra"), mo_khoa_twitch=_mo_khoa(tmp_path, proxy_nghe)
    )
    assert kq[0]["trang_thai"] == "xong", kq
    assert os.path.isfile(kq[0]["duong_dan"]) and kq[0]["chat_luong"].startswith(
        "1440p60"
    )
    trich, tai = gia.doi_tuong
    # Bước 1: qua proxy, chỉ cookie twitch.tv, không cookie YouTube, không tải.
    assert trich.opts["proxy"] == f"http://windscribe:{MAT_KHAU}@127.0.0.1:{proxy_nghe}"
    assert trich.goi == [("extract_info", False, False)]
    assert sorted(c.name for c in trich.cookiejar) == ["auth-token", "unique_id"]
    assert not {"cookiefile", "cookiesfrombrowser"} & set(trich.opts)
    # Bước 2: tải THẲNG (không proxy) từ đúng kết quả bước 1.
    assert "proxy" not in tai.opts and tai.goi == [
        ("process_ie_result", "12345678901", True)
    ]
    assert "proxy + đăng nhập" in kq[0]["ghi_chu"]


def test_youtube_khong_doi_du_co_mo_khoa(gia, tmp_path, proxy_nghe):
    kq = tv.tai_nhieu(
        [YOUTUBE], str(tmp_path / "ra"), mo_khoa_twitch=_mo_khoa(tmp_path, proxy_nghe)
    )
    assert kq[0]["trang_thai"] == "xong"
    (ydl,) = gia.doi_tuong
    assert (
        "proxy" not in ydl.opts
        and ydl.goi == [("extract_info", True, True)]
        and not ydl.cookiejar
    )


def test_twitch_khong_cau_hinh_tai_nhu_cu(gia, tmp_path):
    kq = tv.tai_nhieu([TWITCH], str(tmp_path / "ra"), mo_khoa_twitch=yc.MoKhoaTwitch())
    assert kq[0]["trang_thai"] == "xong"
    (ydl,) = gia.doi_tuong
    assert "proxy" not in ydl.opts and ydl.goi == [("extract_info", True, True)]


def test_twitch_proxy_tat_bao_loi_khong_tai_lang_le(gia, tmp_path):
    kq = tv.tai_nhieu(
        [TWITCH, YOUTUBE],
        str(tmp_path / "ra"),
        mo_khoa_twitch=_mo_khoa(tmp_path, _cong_dong()),
    )
    assert (
        kq[0]["trang_thai"] == "loi"
        and "Windscribe" in kq[0]["ghi_chu"]
        and MAT_KHAU not in kq[0]["ghi_chu"]
    )
    assert kq[1]["trang_thai"] == "xong"  # link khác vẫn tải
    assert len(gia.doi_tuong) == 1  # không có lượt tải Twitch nào (kể cả bản thấp)
