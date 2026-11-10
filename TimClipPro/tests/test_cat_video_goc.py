# -*- coding: utf-8 -*-
"""Tải rồi cắt một đoạn chính xác (D-42): video tổng hợp THẬT bằng FFmpeg, tải YouTube là giả (chép file).

Tiếng nguồn đổi tần số đúng ở giây 4 (440 Hz → 880 Hz): cắt đúng thì đầu/cuối đoạn nghe đúng tần số ở hai phía mốc.
"""

import json
import os
import shutil
import subprocess

import numpy as np
import pytest

import cat_video_goc as cv
import tai_video_goc as tv

can_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="cần FFmpeg"
)
URL = [f"https://www.youtube.com/watch?v=abcdefghij{i}" for i in range(3)]
TIENG = "aevalsrc=sin(2*PI*if(lt(t\\,4)\\,440\\,880)*t):s=44100:d=10"


def _tao(path, chi_tieng=False):
    vao = (
        []
        if chi_tieng
        else ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=10"]
    )
    ma = (
        ["-c:a", "aac"]
        if chi_tieng
        else [
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
        ]
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *vao,
            "-f",
            "lavfi",
            "-i",
            TIENG,
            *ma,
            str(path),
        ],
        check=True,
    )
    return str(path)


def _gia_tai(monkeypatch, src, chi_tieng=False, loi=()):
    goi = {}

    def tai_nhieu(
        links, thu_muc, cau_hinh_mang=None, *, progress=None, cancel_check=None, **kw
    ):
        goi.update(kw)
        goi.setdefault("thu_muc", []).append(thu_muc)
        os.makedirs(thu_muc, exist_ok=True)
        ra = []
        for url in links:
            if url in loi:
                ra.append(
                    {
                        "url": url,
                        "trang_thai": "loi",
                        "duong_dan": "",
                        "tieu_de": "",
                        "chat_luong": "",
                        "ghi_chu": "Video đã bị gỡ.",
                    }
                )
                continue
            ma = tv.ma_tu_url(url)
            dich = os.path.join(
                thu_muc,
                f"Tiêu đề {ma} [{ma}]" + (".audio.m4a" if chi_tieng else ".mp4"),
            )
            shutil.copy(src, dich)
            ra.append(
                {
                    "url": url,
                    "trang_thai": "xong",
                    "duong_dan": dich,
                    "tieu_de": f"Tiêu đề {ma}",
                    "chat_luong": "x",
                    "ghi_chu": "",
                }
            )
        return ra

    monkeypatch.setattr(tv, "tai_nhieu", tai_nhieu)
    return goi


def _tan_so(path, giay, dai=0.2):
    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{giay:.3f}",
            "-t",
            str(dai),
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
    return np.fft.rfftfreq(len(x), 1 / 8000)[
        int(np.argmax(np.abs(np.fft.rfft(x * np.hanning(len(x))))))
    ]


def _probe(path):
    return json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                path,
            ],
            capture_output=True,
            check=True,
        ).stdout
    )


@pytest.mark.parametrize(
    "vb, giay",
    [
        ("83", 83.0),
        ("1:23", 83.0),
        ("01:02:03", 3723.0),
        ("1:23.5", 83.5),
        ("1:23,5", 83.5),
        ("  0:05 ", 5.0),
        ("", None),
        ("   ", None),
    ],
)
def test_doc_moc(vb, giay):
    assert cv.doc_moc(vb) == giay


@pytest.mark.parametrize("vb", ["1:75", "abc", "1::2", "-5", "1:2:3:4", "1.5:20"])
def test_doc_moc_sai_thi_bao_loi(vb):
    with pytest.raises(ValueError):
        cv.doc_moc(vb)


@can_ffmpeg
@pytest.mark.parametrize(
    "tu, den, dau, cuoi",
    [(4.0, 6.0, 880, 880), (2.0, 4.0, 440, 440), (3.5, 6.0, 440, 880)],
)
def test_cat_dung_tung_khung_hinh_va_xoa_video_tron(
    tmp_path, monkeypatch, tu, den, dau, cuoi
):
    src = _tao(tmp_path / "nguon.mp4")
    goi = _gia_tai(monkeypatch, src)
    ra_dir = tmp_path / "ra"
    kq = cv.tai_doan([URL[0]], str(ra_dir), tu_s=tu, den_s=den, chat_luong="1080p")
    assert goi["chat_luong"] == "1080p" and goi["bo_qua_da_co"] is True
    k = kq[0]
    assert k["trang_thai"] == "xong", k
    p = _probe(k["duong_dan"])
    assert float(p["format"]["duration"]) == pytest.approx(den - tu, abs=0.05)
    hinh = next(s for s in p["streams"] if s["codec_type"] == "video")
    assert int(hinh["nb_frames"]) == round((den - tu) * 30)
    # Mốc đổi tiếng ở giây 4 của nguồn: 0,15 s đầu/cuối đoạn phải đúng phía của mốc.
    assert _tan_so(k["duong_dan"], 0.0, 0.15) == pytest.approx(dau, abs=40)
    assert _tan_so(k["duong_dan"], den - tu - 0.15, 0.15) == pytest.approx(cuoi, abs=40)
    assert os.listdir(ra_dir) == [
        os.path.basename(k["duong_dan"])
    ]  # video trọn + thư mục tạm đã xoá
    assert "[abcdefghij0]" in k["duong_dan"] and k["duong_dan"].endswith(".mp4")


@can_ffmpeg
def test_doan_vuot_do_dai_video_thi_bao_loi_giu_video_tai(tmp_path, monkeypatch):
    _gia_tai(monkeypatch, _tao(tmp_path / "nguon.mp4"), loi=(URL[1],))
    kq = cv.tai_doan([URL[0], URL[1]], str(tmp_path / "ra"), tu_s=5, den_s=12)
    assert [k["trang_thai"] for k in kq] == ["loi", "loi"]
    assert "chỉ dài 00:00:10" in kq[0]["ghi_chu"]
    assert kq[1]["ghi_chu"] == "Video đã bị gỡ."
    assert os.listdir(
        tmp_path / "ra" / cv.THU_MUC_TAM
    )  # bấm lại với mốc đúng không phải tải lại


@can_ffmpeg
def test_chi_tieng_cat_ra_m4a(tmp_path, monkeypatch):
    _gia_tai(monkeypatch, _tao(tmp_path / "nguon.m4a", chi_tieng=True), chi_tieng=True)
    k = cv.tai_doan(
        [URL[0]], str(tmp_path / "ra"), tu_s=3.5, den_s=6, chat_luong="Chỉ tiếng"
    )[0]
    assert k["trang_thai"] == "xong", k
    assert k["duong_dan"].endswith(".m4a")
    p = _probe(k["duong_dan"])
    assert [s["codec_type"] for s in p["streams"]] == ["audio"]
    assert float(p["format"]["duration"]) == pytest.approx(2.5, abs=0.05)
    assert _tan_so(k["duong_dan"], 0.0, 0.15) == pytest.approx(440, abs=40)


def test_moc_hien_giu_phan_le():
    assert cv.moc_hien(60.5) == "00:01:00,5"
    assert cv.moc_hien(3723.25, ".") == "01.02.03,25"
    assert cv.moc_hien(83) == "00:01:23"


def test_moc_sai_thu_tu_bao_loi_truoc_khi_tai(tmp_path, monkeypatch):
    goi = _gia_tai(monkeypatch, "khong_dung")
    with pytest.raises(ValueError, match="sau"):
        cv.tai_doan([URL[0]], str(tmp_path), tu_s=10, den_s=5)
    assert goi == {}


def test_tab_tai_video_co_doan_goi_tai_doan(tmp_path, monkeypatch):
    """AppTest: điền «Từ»/«Đến» → gọi cat_video_goc.tai_doan; mốc sai → nút tắt + báo lỗi."""
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
        tu_s,
        den_s,
        chat_luong,
        progress=None,
        cancel_check=None,
        **kw,
    ):
        goi.append((links, thu_muc, tu_s, den_s, chat_luong))
        return [
            {
                "url": links[0],
                "trang_thai": "xong",
                "duong_dan": "x.mp4",
                "tieu_de": "Đoạn cắt A",
                "chat_luong": "",
                "ghi_chu": "",
            }
        ]

    monkeypatch.setattr(cv, "tai_doan", gia)
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120
    ).run()
    next(t for t in at.text_area if t.label.startswith("Link video")).input(
        URL[0]
    ).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu video").input(
        str(tmp_path / "v")
    ).run()
    o_tu = next(t for t in at.text_input if t.label.startswith("Từ"))
    o_den = next(t for t in at.text_input if t.label.startswith("Đến"))
    o_tu.input("2:00").run()
    next(t for t in at.text_input if t.label.startswith("Đến")).input("1:00").run()
    assert at.button(key="bat_dau_tai_video").disabled
    assert any("sau" in e.value for e in at.error)
    next(t for t in at.text_input if t.label.startswith("Đến")).input("2:30.5").run()
    assert o_den is not None
    at.button(key="bat_dau_tai_video").click().run()
    for _ in range(50):
        if not at.session_state.job["running"]:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert goi == [
        ([URL[0]], str(tmp_path / "v"), 120.0, 150.5, tv.CHAT_LUONG_MAC_DINH)
    ]
    assert any("Đoạn cắt A" in m.value for m in at.markdown)


def test_moc_hien_lam_tron_khong_cut_duoi():
    """Audit 10/11 mục 11: 59,9996 → phần lẻ làm tròn thành 1 nhưng giây không cộng → «00:00:59,»."""
    assert cv.moc_hien(59.9996) == "00:01:00"
    assert cv.moc_hien(59.9996, ".") == "00.01.00"


@can_ffmpeg
def test_chat_luong_khac_khong_cat_tu_video_cu(tmp_path, monkeypatch):
    """Audit 10/11 mục 2: lượt 720p hỏng để lại video trọn; lượt «Cao nhất» nhận ra theo mã video và cắt từ bản 720p."""
    goi = _gia_tai(monkeypatch, _tao(tmp_path / "nguon.mp4"))
    ra = tmp_path / "ra"
    assert cv.tai_doan([URL[0]], str(ra), tu_s=5, den_s=12, chat_luong="720p")[0]["trang_thai"] == "loi"
    assert cv.tai_doan([URL[0]], str(ra), tu_s=5, den_s=7, chat_luong="Cao nhất")[0]["trang_thai"] == "xong"
    assert goi["thu_muc"][0] != goi["thu_muc"][1]


@can_ffmpeg
@pytest.mark.parametrize("hong", ["lech", "ffprobe"])
def test_doan_ra_khong_tin_duoc_doi_ten_loi_va_giu_video_tron(tmp_path, monkeypatch, hong):
    """Audit 10/11 mục 5 + 6: đoạn lệch độ dài giữ TÊN ĐẸP (dễ dùng nhầm), ghi chú không nêu file; ffprobe hỏng ở lần đo
    đoạn ra thì lỗi bay ra tác vụ nền, mất hết dòng kết quả."""
    _gia_tai(monkeypatch, _tao(tmp_path / "nguon.mp4"))
    goc = cv._do

    def do(path):
        if cv.THU_MUC_TAM in path:
            return goc(path)
        if hong == "ffprobe":
            raise RuntimeError("Không đọc được file bằng ffprobe.")
        return 99.0, True

    monkeypatch.setattr(cv, "_do", do)
    ra = tmp_path / "ra"
    k = cv.tai_doan([URL[0]], str(ra), tu_s=2, den_s=4)[0]
    assert k["trang_thai"] == "loi"
    assert k["duong_dan"].endswith(".loi.mp4") and os.path.isfile(k["duong_dan"])
    assert k["duong_dan"] in k["ghi_chu"]
    assert [f for f in os.listdir(ra) if f.endswith(".mp4")] == [os.path.basename(k["duong_dan"])]
    assert os.listdir(ra / cv.THU_MUC_TAM)  # video trọn giữ lại
