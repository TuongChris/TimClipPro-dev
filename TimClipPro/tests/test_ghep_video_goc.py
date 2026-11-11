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
        "lech60": ("Bản 60 hình", _tao(d / "e.mp4", 2, 1320, hinh_giay=60)),
    }


def _gia_tai(monkeypatch, nguon, loi=(), lech=""):
    goi = {}

    def tai_nhieu(
        links, thu_muc, cau_hinh_mang=None, *, progress=None, cancel_check=None, **kw
    ):
        goi.update(kw)
        os.makedirs(thu_muc, exist_ok=True)
        ra = []
        for url in links:
            ma = tv.ma_link(url) or url.rsplit("/", 1)[-1]  # như yt-dlp: [mã YouTube] / [v<số> Twitch] / mã riêng
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
                ten, src = nguon[lech if (lech and url == URL[2]) else url]
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


def _probe(path):
    return json.loads(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
            capture_output=True,
            check=True,
        ).stdout
    )


@can_ffmpeg
@pytest.mark.parametrize("khoa, hz", [("lech", 440), ("lech60", 1320)])
def test_video_lech_thong_so_tu_chuyen_cho_khop_video_1(
    nguon, tmp_path, monkeypatch, khoa, hz
):
    """Người dùng 09/11: video 2 chạy 60 hình/giây, video 1 29,97 → trước đây dừng. Nay chỉ video lệch được nén lại cho
    khớp video 1 (độ phân giải, số hình/giây), tiếng giữ nguyên nên mốc vẫn đúng tiếng thật."""
    _gia_tai(monkeypatch, nguon, lech=khoa)
    kq = gv.ghep(URL[:3], str(tmp_path), ten_file="ghep")
    cuoi = kq[-1]
    assert cuoi["trang_thai"] == "xong", cuoi
    assert "Video 3" in cuoi["ghi_chu"]  # báo rõ video nào đã chuyển
    ra = _probe(cuoi["duong_dan"])
    hinh = next(x for x in ra["streams"] if x["codec_type"] == "video")
    assert (hinh["width"], hinh["height"], hinh["r_frame_rate"]) == (320, 240, "30/1")
    assert float(ra["format"]["duration"]) == pytest.approx(7.0, abs=0.2)
    with open(tmp_path / "ghep.moc.csv", encoding="utf-8-sig") as f:
        bat_dau = [float(d["Bắt đầu (giây)"]) for d in csv.DictReader(f)]
    assert bat_dau == pytest.approx([0, 2, 5], abs=0.05)
    for giay, tan_so in zip(bat_dau, (440, 880, hz)):
        assert _tan_so_tai(cuoi["duong_dan"], giay + 0.1) == pytest.approx(
            tan_so, abs=25
        ), giay
    assert not os.path.exists(tmp_path / gv.THU_MUC_PHAN)


@can_ffmpeg
def test_chuyen_xong_van_lech_thi_dung_giu_file(nguon, tmp_path, monkeypatch):
    """Lớp chặn cuối: bản chuyển vẫn khác video 1 (lỗi chuyển) thì KHÔNG nối ra file hỏng ở chỗ nối."""
    from types import SimpleNamespace

    _gia_tai(monkeypatch, nguon, lech="lech60")

    def chuyen_hong(nguon_file, dich, *_a, **_k):
        shutil.copy(nguon_file, dich)
        return SimpleNamespace(cancelled=False, returncode=0, stderr="", ly_do="")

    monkeypatch.setattr(gv, "_chuyen_khop", chuyen_hong)
    kq = gv.ghep(URL[:3], str(tmp_path))
    cuoi = kq[-1]
    assert cuoi["trang_thai"] == "loi"
    assert "số hình/giây 60/1 (video 1: 30/1)" in cuoi["ghi_chu"]
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


@can_ffmpeg
def test_chuong_dai_hon_3_phut_van_con_track_chuong_quicktime(tmp_path, monkeypatch):
    """Thật 09/11: mọi video ghép báo «Referenced QT chapter track not found». FFmpeg đặt nhịp track chương = BCNN nhịp
    hình (15360) và tiếng 44,1 kHz = 11.289.600/giây → chương > ~190 s tràn 32-bit, bị bỏ; hết chương thì mất track,
    trình phát chỉ đọc chương QuickTime (Apple) không thấy mốc nào."""
    d = tmp_path / "nguon"
    d.mkdir()
    nguon = {
        URL[0]: ("Dài A", _tao(d / "a.mp4", 200, 440, kich_thuoc="64x64")),
        URL[1]: ("Dài B", _tao(d / "b.mp4", 200, 880, kich_thuoc="64x64")),
    }
    _gia_tai(monkeypatch, nguon)
    cuoi = gv.ghep(URL[:2], str(tmp_path / "ra"), ten_file="dai")[-1]
    assert cuoi["trang_thai"] == "xong", cuoi
    r = subprocess.run(
        ["ffprobe", "-v", "warning", "-show_streams", "-show_chapters", "-of", "json", cuoi["duong_dan"]],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "chapter track not found" not in r.stderr
    ra = json.loads(r.stdout)
    assert [s["codec_type"] for s in ra["streams"]] == ["video", "audio", "data"]  # data = track chương QuickTime
    assert [float(c["start_time"]) for c in ra["chapters"]] == pytest.approx([0, 200], abs=0.05)


def test_tach_link_bo_dau_nhay():
    """Audit 10/11 mục 10: dán từ Excel ra «"https://…"» — tab Tải bỏ dấu nháy, tab Ghép thì báo «không phải link»."""
    assert gv.tach_link(f'"{URL[0]}"\n {URL[1]} ') == [URL[0], URL[1]]


def test_nhip_file_chuong_video_rat_dai_dung_1000():
    """Audit 10/11 mục 9: nhịp file = 44100 thì MỘT chương > 2^31/44100 ≈ 13,5 giờ tràn → mất chương QuickTime."""
    ts = [("a", {"tan_so_tieng": "44100", "do_dai": 3600.0}), ("b", {"tan_so_tieng": "44100", "do_dai": 50000.0})]
    assert gv._nhip_file(ts[:1]) == ["-movie_timescale", "44100"]
    assert gv._nhip_file(ts) == ["-movie_timescale", "1000"]
    assert gv._nhip_file([("a", {"tan_so_tieng": None, "do_dai": 1.0})]) == []


@can_ffmpeg
def test_ten_ra_khong_de_file_moc_cu_va_dong_link_khong_tro_file_da_xoa(nguon, tmp_path, monkeypatch):
    """Audit 10/11 mục 1 + 7: tên chỉ kiểm «.mp4» trống rồi GHI ĐÈ «.moc.csv» cũ (đáp án của video đã chuyển đi);
    sau khi ghép, dòng từng link vẫn trỏ file lẻ trong thư mục tạm vừa xoá."""
    _gia_tai(monkeypatch, nguon)
    (tmp_path / "Thu.moc.csv").write_bytes(b"dap an cu")
    kq = gv.ghep(URL[:2], str(tmp_path), ten_file="Thu")
    assert kq[-1]["trang_thai"] == "xong", kq[-1]
    assert os.path.basename(kq[-1]["duong_dan"]) == "Thu (2).mp4"
    assert (tmp_path / "Thu.moc.csv").read_bytes() == b"dap an cu"
    assert (tmp_path / "Thu (2).moc.csv").is_file()
    assert kq[-1]["la_dong_ghep"] is True
    for k in kq[:-1]:
        assert k["duong_dan"] == "" and "ghép" in k["ghi_chu"]


@can_ffmpeg
def test_link_khong_phai_youtube_giu_tieu_de_rieng(nguon, tmp_path, monkeypatch):
    """Audit 10/11 mục 8: link không có mã YouTube → mọi link dùng chung tiêu đề link đầu trong CSV và chương."""
    vimeo = ["https://vimeo.com/111", "https://vimeo.com/222"]
    nguon2 = {vimeo[0]: nguon[URL[0]], vimeo[1]: nguon[URL[1]]}
    _gia_tai(monkeypatch, nguon2)
    kq = gv.ghep(vimeo, str(tmp_path), ten_file="vm")
    assert kq[-1]["trang_thai"] == "xong", kq[-1]
    with open(tmp_path / "vm.moc.csv", encoding="utf-8-sig") as f:
        assert [d["Tiêu đề"] for d in csv.DictReader(f)] == ["Tập 1: Mở đầu", "Tập 2 = «bí ẩn»; #1"]


@can_ffmpeg
def test_do_lai_video_ghep_hong_khong_mat_ket_qua(nguon, tmp_path, monkeypatch):
    """Audit 10/11 mục 5: ffprobe hỏng ở lần đo video ghép → lỗi bay ra tác vụ nền, mất hết các dòng kết quả."""
    _gia_tai(monkeypatch, nguon)
    goc = gv.thong_so

    def thong_so(path):
        if gv.THU_MUC_PHAN not in path:
            raise RuntimeError("Không đọc được file bằng ffprobe.")
        return goc(path)

    monkeypatch.setattr(gv, "thong_so", thong_so)
    kq = gv.ghep(URL[:2], str(tmp_path), ten_file="hong")
    assert kq[-1]["trang_thai"] == "xong" and "không đo lại được" in kq[-1]["ghi_chu"]
    assert os.path.isdir(tmp_path / gv.THU_MUC_PHAN)  # chưa kiểm được thì giữ file lẻ


def _lufs(path):
    import re

    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])


@can_ffmpeg
def test_ghep_chuan_hoa_am_luong_tung_video_moc_van_dung(nguon, tmp_path, monkeypatch):
    """D-43: chỉnh âm lượng TỪNG video trước khi nối (như YouTube làm cho từng video) — mốc vẫn khớp tiếng thật."""
    _gia_tai(monkeypatch, nguon)
    nho = gv.ghep(URL[:3], str(tmp_path / "a"), ten_file="g")[-1]
    assert _lufs(nho["duong_dan"]) < -18  # tiếng bíp tổng hợp nhỏ hơn mức YouTube
    _gia_tai(monkeypatch, nguon)
    cuoi = gv.ghep(URL[:3], str(tmp_path / "b"), ten_file="g", chuan_hoa_am=True)[-1]
    assert cuoi["trang_thai"] == "xong", cuoi
    assert _lufs(cuoi["duong_dan"]) == pytest.approx(-14, abs=1.0)
    with open(tmp_path / "b" / "g.moc.csv", encoding="utf-8-sig") as f:
        bat_dau = [float(d["Bắt đầu (giây)"]) for d in csv.DictReader(f)]
    assert bat_dau == pytest.approx([0, 2, 5], abs=0.05)
    for giay, hz in zip(bat_dau, (440, 880, 1320)):
        assert _tan_so_tai(cuoi["duong_dan"], giay + 0.1) == pytest.approx(hz, abs=25), giay



@can_ffmpeg
def test_ghep_link_twitch_lap_lai(nguon, tmp_path, monkeypatch):
    """Audit 11/11: link Twitch lặp lại — lần sau «trùng», ghép phải tìm được file [v<số>] của lần đầu."""
    tw = "https://www.twitch.tv/videos/12345678901"
    _gia_tai(monkeypatch, {tw: nguon[URL[0]], URL[1]: nguon[URL[1]]})
    kq = gv.ghep([tw, URL[1], tw], str(tmp_path), ten_file="tw")
    assert kq[-1]["trang_thai"] == "xong", kq[-1]
    with open(tmp_path / "tw.moc.csv", encoding="utf-8-sig") as f:
        assert [d["Tiêu đề"] for d in csv.DictReader(f)] == ["Tập 1: Mở đầu", "Tập 2 = «bí ẩn»; #1", "Tập 1: Mở đầu"]
