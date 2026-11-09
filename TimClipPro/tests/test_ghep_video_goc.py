# -*- coding: utf-8 -*-
"""Ghép video gốc (D-39): video tổng hợp THẬT tạo bằng FFmpeg, tải YouTube là giả (``tai_nhieu`` thay bằng chép file).

Mỗi phần mang một tiếng bíp tần số riêng — kiểm được ở đúng mốc ghi trong file CSV là tiếng của video gốc nào (đáp án
của file mốc phải đúng, đó là toàn bộ giá trị của tính năng).
"""

import csv
import json
import os
import shutil
import subprocess

import numpy as np
import pytest

import ghep_video_goc as gv
import tai_video_goc as tv

can_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="cần FFmpeg"
)
URL = [f"https://www.youtube.com/watch?v=abcdefghij{i}" for i in range(4)]


def _tao(path, giay, tan_so, kich_thuoc="320x240", hinh_giay=30):
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={kich_thuoc}:rate={hinh_giay}:duration={giay}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={tan_so}:sample_rate=44100:duration={giay}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-g",
            str(hinh_giay),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ac",
            "2",
            "-shortest",
            str(path),
        ],
        check=True,
    )
    return str(path)


@pytest.fixture(scope="module")
def nguon(tmp_path_factory):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("cần FFmpeg")
    d = tmp_path_factory.mktemp("nguon")
    return {
        URL[0]: ("Tập 1: Mở đầu", _tao(d / "a.mp4", 2, 440)),
        URL[1]: ("Tập 2 = «bí ẩn»; #1", _tao(d / "b.mp4", 3, 880)),
        URL[2]: ("Tập 3 của Joe's", _tao(d / "c.mp4", 2.5, 1320)),
        "lech": ("Bản 360p", _tao(d / "d.mp4", 2, 440, kich_thuoc="640x360")),
    }


def _gia_tai(monkeypatch, nguon, loi=(), lech=False):
    goi = {}

    def tai_nhieu(
        links, thu_muc, cau_hinh_mang=None, *, progress=None, cancel_check=None, **kw
    ):
        goi.update(kw)
        os.makedirs(thu_muc, exist_ok=True)
        ra = []
        for url in links:
            ma = tv.ma_tu_url(url)
            dich = os.path.join(thu_muc, f"x [{ma}].mp4")
            if url in loi:
                ra.append(
                    {
                        "url": url,
                        "trang_thai": "loi",
                        "duong_dan": "",
                        "tieu_de": "",
                        "chat_luong": "",
                        "ghi_chu": "YouTube từ chối",
                    }
                )
            elif os.path.exists(dich):
                ra.append(
                    {
                        "url": url,
                        "trang_thai": "bo_qua",
                        "duong_dan": "",
                        "tieu_de": "",
                        "chat_luong": "",
                        "ghi_chu": "Trùng video đã tải ở trên trong lượt này.",
                    }
                )
            else:
                ten, src = nguon["lech" if (lech and url == URL[2]) else url]
                shutil.copy(src, dich)
                ra.append(
                    {
                        "url": url,
                        "trang_thai": "xong",
                        "duong_dan": dich,
                        "tieu_de": ten,
                        "chat_luong": "x",
                        "ghi_chu": "",
                    }
                )
        return ra

    monkeypatch.setattr(tv, "tai_nhieu", tai_nhieu)
    return goi


def _tan_so_tai(path, giay):
    """Tần số trội của 0,4 giây tiếng bắt đầu ở ``giay`` trong ``path``."""
    raw = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{giay:.3f}",
            "-t",
            "0.4",
            "-i",
            path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(float)
    pho = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.fft.rfftfreq(len(x), 1 / 8000)[int(np.argmax(pho))]


@can_ffmpeg
def test_ghep_dung_thu_tu_moc_khop_tieng_that_va_xoa_file_le(
    nguon, tmp_path, monkeypatch
):
    goi = _gia_tai(monkeypatch, nguon)
    links = [URL[0], URL[1], URL[2], URL[0]]  # link lặp lại → video lặp lại
    kq = gv.ghep(links, str(tmp_path), ten_file="Thử: ghép/1")
    assert goi["dinh_dang"] == tv.DINH_DANG_GHEP and goi["bo_qua_da_co"] is True
    cuoi = kq[-1]
    assert cuoi["trang_thai"] == "xong", cuoi
    assert os.path.basename(cuoi["duong_dan"]) == "Thử_ ghép_1.mp4"
    assert not os.path.exists(
        tmp_path / gv.THU_MUC_PHAN
    )  # file lẻ đã xoá sau khi ghép thành công

    with open(tmp_path / "Thử_ ghép_1.moc.csv", encoding="utf-8-sig") as f:
        moc = list(csv.DictReader(f))
    assert [d["Tiêu đề"] for d in moc] == [
        "Tập 1: Mở đầu",
        "Tập 2 = «bí ẩn»; #1",
        "Tập 3 của Joe's",
        "Tập 1: Mở đầu",
    ]
    bat_dau = [float(d["Bắt đầu (giây)"]) for d in moc]
    assert bat_dau == pytest.approx([0, 2, 5, 7.5], abs=0.05)
    for giay, hz in zip(bat_dau, (440, 880, 1320, 440)):
        assert _tan_so_tai(cuoi["duong_dan"], giay + 0.1) == pytest.approx(
            hz, abs=25
        ), giay

    ra = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_chapters",
                "-show_format",
                "-of",
                "json",
                cuoi["duong_dan"],
            ],
            capture_output=True,
            check=True,
        ).stdout
    )
    assert float(ra["format"]["duration"]) == pytest.approx(9.5, abs=0.2)
    assert [c["tags"]["title"] for c in ra["chapters"]] == [d["Tiêu đề"] for d in moc]
    assert [float(c["start_time"]) for c in ra["chapters"]] == pytest.approx(
        bat_dau, abs=0.01
    )


@can_ffmpeg
def test_video_lech_thong_so_thi_khong_ghep_giu_file_da_tai(
    nguon, tmp_path, monkeypatch
):
    _gia_tai(monkeypatch, nguon, lech=True)
    kq = gv.ghep(URL[:3], str(tmp_path))
    cuoi = kq[-1]
    assert cuoi["trang_thai"] == "loi"
    assert (
        "Video 3" in cuoi["ghi_chu"]
        and "độ phân giải 640x360 (video 1: 320x240)" in cuoi["ghi_chu"]
    )
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".mp4")]
    assert (
        len([f for f in os.listdir(tmp_path / gv.THU_MUC_PHAN) if f.endswith(".mp4")])
        == 3
    )


@can_ffmpeg
def test_mot_video_tai_loi_thi_khong_ghep(nguon, tmp_path, monkeypatch):
    _gia_tai(monkeypatch, nguon, loi=(URL[1],))
    kq = gv.ghep(URL[:3], str(tmp_path))
    assert [k["trang_thai"] for k in kq] == ["xong", "loi", "xong", "loi"]
    assert "chưa tải được" in kq[-1]["ghi_chu"]
    assert os.path.isdir(tmp_path / gv.THU_MUC_PHAN)


def test_cac_cho_lech_bao_tung_thong_so():
    a = {
        "ma_hinh": "h264",
        "profile": "High",
        "do_phan_giai": "1920x1080",
        "hinh_giay": "30/1",
        "pix_fmt": "yuv420p",
        "ma_tieng": "aac",
        "tan_so_tieng": "44100",
        "kenh_tieng": 2,
        "do_dai": 10.0,
    }
    b = {**a, "hinh_giay": "60/1", "do_dai": 3.0}
    assert gv.cac_cho_lech([("A", a), ("B", dict(a)), ("C", b)]) == [
        "Video 3 «C»: số hình/giây 60/1 (video 1: 30/1)"
    ]


def test_danh_sach_noi_va_chuong_thoat_ky_tu():
    ds = gv.danh_sach_noi([("C:\\Kho\\Joe's [abcdefghij1].mp4", 12.5)])
    assert "file 'C:/Kho/Joe'\\''s [abcdefghij1].mp4'\nduration 12.500000\n" in ds
    meta = gv.chuong_ffmetadata(gv.moc_thoi_gian([("a=b;c#d", "l", 1.0)]))
    assert "title=a\\=b\\;c\\#d" in meta and "START=0" in meta and "END=1000" in meta


def test_ten_file_ra():
    assert gv.ten_file_ra('a<b>:c"/d\\e|f?g*') == "a_b__c__d_e_f_g_"
    assert gv.ten_file_ra("  ").startswith("Video ghép ")


def test_csv_moc_chan_cong_thuc():
    raw = gv.csv_moc(gv.moc_thoi_gian([("=SUM(A1)", "l", 2.0)]))
    assert raw.startswith(b"\xef\xbb\xbf") and "'=SUM(A1)" in raw.decode("utf-8-sig")


def test_tab_ghep_video_goi_dung_ham(tmp_path, monkeypatch):
    import time
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    goi = []

    def gia(
        links,
        thu_muc,
        cau_hinh_mang=None,
        *,
        ten_file="",
        progress=None,
        cancel_check=None,
        **kw,
    ):
        goi.append((links, thu_muc, ten_file))
        return [
            {
                "url": "🎞️ Video ghép",
                "trang_thai": "xong",
                "duong_dan": "x.mp4",
                "tieu_de": "Video ghép 2 video",
                "chat_luong": "",
                "ghi_chu": "Mốc thời gian từng video gốc: x.moc.csv",
            }
        ]

    monkeypatch.setattr(gv, "ghep", gia)
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120
    ).run()
    next(t for t in at.text_area if t.label.startswith("Link video cần ghép")).input(
        f"{URL[0]}\n{URL[1]}"
    ).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu video ghép").input(
        str(tmp_path / "ra")
    ).run()
    next(t for t in at.text_input if t.label.startswith("Tên file video ghép")).input(
        "Joe dài"
    ).run()
    at.button(key="bat_dau_ghep_video").click().run()
    for _ in range(50):
        if not at.session_state.job["running"]:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert goi == [([URL[0], URL[1]], str(tmp_path / "ra"), "Joe dài")]
    assert any("Video ghép 2 video" in m.value for m in at.markdown)


def test_tach_link_giu_thu_tu_va_link_lap():
    assert gv.tach_link(f" {URL[0]} \n\n{URL[1]}\n{URL[0]}\n") == [URL[0], URL[1], URL[0]]
