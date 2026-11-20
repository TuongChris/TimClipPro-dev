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
                f"Tieu_de_{ma}_{ma}" + (".m4a" if chi_tieng else ".mp4"),  # tên tai_nhieu đặt từ 12/11
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
    ten = os.path.basename(k["duong_dan"])  # 12/11: không dấu cách, không ngoặc
    assert ten.startswith("Tieu_de_abcdefghij0_abcdefghij0_00-00-0") and ten.endswith(".mp4") and " " not in ten


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
    assert os.path.basename(k["duong_dan"]) == "Tieu_de_abcdefghij0_abcdefghij0_00-00-03-5_00-00-06.m4a"
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


@can_ffmpeg
def test_cat_chuan_hoa_am_luong(tmp_path, monkeypatch):
    """D-43: tiếng nguồn biên độ tối đa (to hơn mức YouTube) → đoạn cắt đưa về ~-14 LUFS."""
    import re

    _gia_tai(monkeypatch, _tao(tmp_path / "nguon.mp4"))
    k = cv.tai_doan([URL[0]], str(tmp_path / "ra"), tu_s=1, den_s=7, chuan_hoa_am=True)[0]
    assert k["trang_thai"] == "xong", k
    assert "LUFS" in k["ghi_chu"]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", k["duong_dan"], "-vn", "-af", "ebur128", "-f",
                        "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1]) == pytest.approx(-14, abs=1.0)



@can_ffmpeg
def test_cat_lai_video_twitch_khong_tai_lai(tmp_path, monkeypatch):
    """Audit 11/11: video Twitch đã tải còn trong thư mục tạm (lượt trước mốc sai) → bấm lại cắt từ file đó, không tải lại."""
    tw = "https://www.twitch.tv/videos/12345678901"
    tam = tmp_path / "ra" / cv.THU_MUC_TAM / f"cl_{tv.CHAT_LUONG[tv.CHAT_LUONG_MAC_DINH]}"
    tam.mkdir(parents=True)
    _tao(tam / "Phat lai [v12345678901].mp4")

    def tai_nhieu(links, thu_muc, cau_hinh_mang=None, **kw):  # như tai_nhieu thật với bo_qua_da_co: «Đã có»
        return [{"url": tw, "trang_thai": "bo_qua", "duong_dan": "", "tieu_de": "", "chat_luong": "",
                 "ghi_chu": "Đã có trong thư mục."}]

    monkeypatch.setattr(tv, "tai_nhieu", tai_nhieu)
    k = cv.tai_doan([tw], str(tmp_path / "ra"), tu_s=1, den_s=3)[0]
    assert k["trang_thai"] == "xong", k
    assert os.path.basename(k["duong_dan"]).startswith("Phat_lai_v12345678901_")  # tên cũ «[mã]» vẫn nhận ra


# ---------------------------------------------------------------- bỏ các đoạn rồi nối phần còn lại (D-59, 17/11)
@pytest.mark.parametrize(
    "vb, ds",
    [
        # đúng kiểu người dùng gõ 17/11
        ("0:04:12 - 0:05:24, 0:07:11 - 0:09:01, 0:30:11 - 0:31:18, 0:45:12 - 0:45:21, 1:01:02 - 1:01:11",
         [(252, 324), (431, 541), (1811, 1878), (2712, 2721), (3662, 3671)]),
        ("1:01:02-1:01:11\n0:04:12 – 0:05:24\n", [(252, 324), (3662, 3671)]),  # mỗi dòng một đoạn, lộn thứ tự
        ("0:05:24,0:07:11; 1:00,5 - 1:02", [(324, 431), (60.5, 62)][::-1]),  # phẩy liền: hai mốc; «1:00,5» = 60,5 s
        ("10 - 20, 15 - 30, 30 - 31, 40 - 41", [(10, 31), (40, 41)]),  # chồng/chạm nhau → gộp
        ("", []),
        ("  \n ", []),
    ],
)
def test_doc_ds_doan(vb, ds):
    assert cv.doc_ds_doan(vb) == [(float(a), float(b)) for a, b in ds]


@pytest.mark.parametrize(
    "vb, loi",
    [
        ("0:04:12 - 0:05:24, 0:07:11", "3 mốc"),
        ("0:05:24 - 0:04:12", "phải sau"),
        ("0:04:12 đến 0:05:24", "Không đọc được «đến»"),
        ("0:75 - 0:80", "không hợp lệ"),
        ("1:2:3:4 - 2:00:00", "Không đọc được"),
    ],
)
def test_doc_ds_doan_sai_bao_loi(vb, loi):
    with pytest.raises(ValueError, match=loi):
        cv.doc_ds_doan(vb)


def test_phan_giu():
    assert cv._phan_giu([(10.0, 20.0), (30.0, 40.0)], 60.0) == [(0.0, 10.0), (20.0, 30.0), (40.0, None)]
    assert cv._phan_giu([(0.0, 5.0), (5.02, 9.0)], 9.03) == []  # mẩu < 1 khung hình không giữ; bỏ tới hết
    assert cv._phan_giu([(0.0, 60.0)], 60.0) == []


def _tao_danh_dau(path, giay=20, chi_hinh=False):
    """Hình: độ sáng khung N = 8·(N mod 32), nén KHÔNG mất dữ liệu; tiếng: giây k của gốc là âm 300 + 20k Hz."""
    tieng = [] if chi_hinh else ["-f", "lavfi", "-i", f"aevalsrc=0.5*sin(2*PI*(300+20*floor(t))*t):s=48000:d={giay}"]
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         f"color=c=black:s=64x48:r=30:d={giay},geq=lum='8*mod(N,32)':cb=128:cr=128", *tieng,
         "-c:v", "libx264", "-preset", "veryfast", "-qp", "0", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)],
        check=True,
    )
    return str(path)


def _khung_ra(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v", "-f", "rawvideo", "-pix_fmt", "yuv420p",
                          "-"], capture_output=True, check=True).stdout
    sang = np.frombuffer(raw, np.uint8).reshape(-1, 64 * 48 * 3 // 2)[:, : 64 * 48].mean(axis=1)
    return np.round(sang / 8).astype(int) % 32


@can_ffmpeg
def test_bo_doan_dung_tung_khung_hinh_va_tieng_xoa_video_tron(tmp_path, monkeypatch):
    """Bỏ 3 đoạn (mốc lẻ, lệch lưới khung) qua đường tải theo link: MỌI khung hình của video ra là đúng khung gốc dự kiến,
    tiếng mỗi khúc đúng giây gốc → không thừa/thiếu khung, hình–tiếng khớp ở chỗ nối; video trọn bị xoá."""
    _gia_tai(monkeypatch, _tao_danh_dau(tmp_path / "nguon.mp4"))
    ds = cv.doc_ds_doan("0:02 - 0:04.4, 0:07.1 - 0:09, 0:15.25 - 0:15.5")
    ra = tmp_path / "ra"
    k = cv.tai_doan([URL[0]], str(ra), ds_bo=ds)[0]
    assert k["trang_thai"] == "xong", k
    assert os.path.basename(k["duong_dan"]) == "Tieu_de_abcdefghij0_abcdefghij0_bo_3_doan.mp4"
    assert "Đã bỏ 3 đoạn" in k["ghi_chu"] and "nối 4 phần" in k["ghi_chu"]
    assert os.listdir(ra) == [os.path.basename(k["duong_dan"])]  # video trọn + thư mục tạm đã xoá
    giu = [(0, 2), (4.4, 7.1), (9, 15.25), (15.5, 20)]
    ky_vong = [n for a, b in giu for n in range(600) if a <= n / 30 < b]
    khung = _khung_ra(k["duong_dan"])
    assert len(khung) == len(ky_vong)
    assert (khung == np.array(ky_vong) % 32).all()
    moc_ra = 0.0
    for a, b in giu:
        for t in np.arange(a, b - 0.2, 0.25):
            if abs(t + 0.1 - round(t + 0.1)) > 0.15:  # không sát chỗ đổi tần số của gốc
                assert _tan_so(k["duong_dan"], moc_ra + t - a, 0.2) == pytest.approx(300 + 20 * int(t + 0.1), abs=8)
        moc_ra += b - a
    assert float(_probe(k["duong_dan"])["format"]["duration"]) == pytest.approx(moc_ra, abs=0.06)


@can_ffmpeg
def test_bo_doan_chi_tieng_va_chi_hinh(tmp_path):
    k = cv.bo_doan(_tao(tmp_path / "a.m4a", chi_tieng=True), str(tmp_path / "ra"), [(3.0, 5.0)])
    assert k["trang_thai"] == "xong", k
    assert k["duong_dan"].endswith("a_bo_1_doan.m4a")
    p = _probe(k["duong_dan"])
    assert [s["codec_type"] for s in p["streams"]] == ["audio"]
    assert float(p["format"]["duration"]) == pytest.approx(8.0, abs=0.06)
    assert _tan_so(k["duong_dan"], 3.05, 0.15) == pytest.approx(880, abs=40)  # nối 0–3 (440 Hz) với 5–10 (880 Hz)
    k = cv.bo_doan(_tao_danh_dau(tmp_path / "h.mp4", giay=6, chi_hinh=True), str(tmp_path / "ra"), [(1.0, 2.0)])
    assert k["trang_thai"] == "xong", k
    assert [s["codec_type"] for s in _probe(k["duong_dan"])["streams"]] == ["video"]
    assert len(_khung_ra(k["duong_dan"])) == 150


@can_ffmpeg
def test_bo_doan_vuot_do_dai_hoac_phu_kin_thi_bao_loi(tmp_path):
    src = _tao(tmp_path / "nguon.mp4")
    k = cv.bo_doan(src, str(tmp_path / "ra"), [(2.0, 3.0), (8.0, 12.0)], giu="File gốc giữ nguyên.")
    assert k["trang_thai"] == "loi" and "chỉ dài 00:00:10" in k["ghi_chu"] and "00:00:08–00:00:12" in k["ghi_chu"]
    k = cv.bo_doan(src, str(tmp_path / "ra"), [(0.0, 10.0)])
    assert k["trang_thai"] == "loi" and "phủ kín" in k["ghi_chu"]
    assert not (tmp_path / "ra").exists() or not os.listdir(tmp_path / "ra")


def test_bo_doan_va_cat_mot_cung_luc_bao_loi_truoc_khi_tai(tmp_path, monkeypatch):
    goi = _gia_tai(monkeypatch, "khong_dung")
    with pytest.raises(ValueError, match="Chỉ chọn một việc"):
        cv.tai_doan([URL[0]], str(tmp_path), tu_s=1, den_s=5, ds_bo=[(2.0, 3.0)])
    assert goi == {}


def test_tab_tai_video_bo_cac_doan_goi_tai_doan(tmp_path, monkeypatch):
    """AppTest: điền «Bỏ các đoạn» → tai_doan nhận ds_bo đã đọc; điền thêm «Từ»/«Đến» → nút tắt + báo chỉ chọn một."""
    import time
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    goi = []

    def gia(links, thu_muc, cau_hinh_mang=None, *, tu_s, den_s, ds_bo, progress=None, cancel_check=None, **kw):
        goi.append((tu_s, den_s, ds_bo))
        return [{"url": links[0], "trang_thai": "xong", "duong_dan": "x.mp4", "tieu_de": "Video đã bỏ đoạn",
                 "chat_luong": "", "ghi_chu": ""}]

    monkeypatch.setattr(cv, "tai_doan", gia)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    next(t for t in at.text_area if t.label.startswith("Link video")).input(URL[0]).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu video").input(str(tmp_path / "v")).run()
    at.text_area(key="bo_tai").input("0:04:12 - 0:05:24, 0:07:11 - 0:09:01").run()
    assert any("Bỏ 2 đoạn (tổng 00:03:02)" in c.value for c in at.caption)
    at.text_input(key="tu_tai").input("1:00").run()
    at.text_input(key="den_tai").input("2:00").run()
    assert at.button(key="bat_dau_tai_video").disabled
    assert any("Chỉ chọn một việc" in e.value for e in at.error)
    at.text_input(key="tu_tai").input("").run()
    at.text_input(key="den_tai").input("").run()
    at.button(key="bat_dau_tai_video").click().run()
    for _ in range(50):
        if goi and not at.session_state.job["running"]:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert goi == [(None, None, [(252.0, 324.0), (431.0, 541.0)])]


# ---------------------------------------------------------------- chụp ảnh ở các mốc (18/11)
def _sang_anh(path):
    """Số khung (mod 32) của ảnh chụp từ video :func:`_tao_danh_dau` — đọc độ sáng trung bình của PNG."""
    # Đổi PNG (RGB) về yuv420p — cùng thang độ sáng «TV» với video nguồn; «gray» là thang đầy đủ, lệch số.
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"],
                         capture_output=True, check=True).stdout
    return int(round(np.frombuffer(raw, np.uint8)[: 64 * 48].mean() / 8)) % 32


def test_doc_ds_moc():
    assert cv.doc_ds_moc("7:23, 12:05\n1:01:10") == [443.0, 725.0, 3670.0]
    assert cv.doc_ds_moc("12:05; 7:23 7:23") == [443.0, 725.0]  # xếp theo thời gian, bỏ trùng
    assert cv.doc_ds_moc("7:23.5") == [443.5]
    assert cv.doc_ds_moc("  ") == []
    with pytest.raises(ValueError, match="không hợp lệ"):
        cv.doc_ds_moc("7:75")
    with pytest.raises(ValueError, match="Không đọc được «abc»"):
        cv.doc_ds_moc("7:23, abc")


@can_ffmpeg
def test_chup_anh_dung_khung_hinh_o_moc(tmp_path):
    """Video 30 hình/giây, chỉ một khung hình chính ở đầu (phải giải mã từ đầu tới mốc): ảnh ở mốc t là ĐÚNG khung
    t·30 — không phải khung hình chính gần nhất. File gốc không bị sửa."""
    src = _tao_danh_dau(tmp_path / "Phim thu.mp4")
    truoc = os.path.getsize(src), os.path.getmtime(src)
    ra = tmp_path / "ra"
    k = cv.chup_anh(src, str(ra), [0.1, 2.5, 7.1, 19.5])
    assert k["trang_thai"] == "xong", k
    anh = sorted(os.listdir(ra))
    assert anh == ["Phim_thu_00-00-00-1.png", "Phim_thu_00-00-02-5.png", "Phim_thu_00-00-07-1.png",
                   "Phim_thu_00-00-19-5.png"]
    # Khung 0–1 và 30–31 (độ sáng < 16 hay > 235) nằm ngoài thang TV, đổi qua RGB bị cắt → mốc chọn tránh chúng.
    assert [_sang_anh(str(ra / a)) for a in anh] == [3, 75 % 32, 213 % 32, 585 % 32]
    p = _probe(str(ra / anh[0]))["streams"][0]
    assert (p["codec_name"], p["width"], p["height"]) == ("png", 64, 48)
    assert "4 ảnh PNG 64×48" in k["ghi_chu"]
    assert (os.path.getsize(src), os.path.getmtime(src)) == truoc
    # Bấm lại: không ghi đè ảnh cũ.
    assert cv.chup_anh(src, str(ra), [2.5])["duong_dan"].endswith("Phim_thu_00-00-02-5_2.png")


@can_ffmpeg
def test_chup_anh_bao_loi_khi_khong_chup_duoc(tmp_path):
    src = _tao_danh_dau(tmp_path / "v.mp4", giay=6)
    k = cv.chup_anh(src, str(tmp_path / "ra"), [2.0, 7.0], giu="File gốc giữ nguyên.")
    assert k["trang_thai"] == "loi" and "chỉ dài 00:00:06" in k["ghi_chu"] and "00:00:07" in k["ghi_chu"]
    assert "File gốc giữ nguyên." in k["ghi_chu"]
    assert not (tmp_path / "ra").exists()  # kiểm mốc TRƯỚC khi chụp ảnh nào
    k = cv.chup_anh(src, str(tmp_path / "ra"), [5.99])  # sau khung cuối (5,967 s), trước hết video
    assert k["trang_thai"] == "loi" and "không có khung hình" in k["ghi_chu"], k
    k = cv.chup_anh(_tao(tmp_path / "t.m4a", chi_tieng=True), str(tmp_path / "ra"), [1.0])
    assert k["trang_thai"] == "loi" and "chỉ có tiếng" in k["ghi_chu"]


@can_ffmpeg
def test_tai_doan_chup_anh_tai_chi_hinh_sdr_roi_xoa_video(tmp_path, monkeypatch):
    goi = _gia_tai(monkeypatch, _tao_danh_dau(tmp_path / "nguon.mp4"))
    ra = tmp_path / "ra"
    k = cv.tai_doan([URL[0]], str(ra), ds_moc=[2.5, 7.1], chat_luong="1080p", chuan_hoa_am=True)[0]
    assert k["trang_thai"] == "xong", k
    ma = tv.ma_tu_url(URL[0])
    assert sorted(os.listdir(ra)) == [f"Tieu_de_{ma}_{ma}_00-00-02-5.png", f"Tieu_de_{ma}_{ma}_00-00-07-1.png"]
    assert k["duong_dan"] == str(ra) and "2 ảnh PNG" in k["ghi_chu"]
    # Chỉ phần hình, ưu tiên bản SDR (bản HDR chụp ra màu nhạt), không ghép tiếng; thư mục tạm riêng với cắt đoạn.
    assert goi["dinh_dang"] == {"format": "bv*[height<=1080][dynamic_range=SDR]/bv*[height<=1080]/b[height<=1080]"}
    assert goi["thu_muc"] == [str(ra / cv.THU_MUC_TAM / "anh_1080")]
    assert "chuan_hoa_am" not in goi


def test_tai_doan_chup_anh_tu_choi_chi_audio_hoac_hai_viec(tmp_path, monkeypatch):
    goi = _gia_tai(monkeypatch, "khong_dung")
    with pytest.raises(ValueError, match="Chụp ảnh cần video có hình"):
        cv.tai_doan([URL[0]], str(tmp_path), ds_moc=[1.0], chat_luong="Chỉ tiếng")
    with pytest.raises(ValueError, match="Chỉ chọn một việc"):
        cv.tai_doan([URL[0]], str(tmp_path), tu_s=1, den_s=5, ds_moc=[2.0])
    with pytest.raises(ValueError, match="Chỉ chọn một việc"):
        cv.tai_doan([URL[0]], str(tmp_path), ds_bo=[(2.0, 3.0)], ds_moc=[2.0])
    assert goi == {}


def test_tab_tai_video_chup_anh_goi_tai_doan(tmp_path, monkeypatch):
    """AppTest: điền «📸 Chụp ảnh» → tai_doan nhận ds_moc đã đọc; chọn «Chỉ audio» hay điền thêm «Từ»/«Đến» → nút tắt."""
    import time
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    goi = []

    def gia(links, thu_muc, cau_hinh_mang=None, *, progress=None, cancel_check=None, **kw):
        goi.append({k: kw.get(k) for k in ("tu_s", "ds_bo", "ds_moc", "chat_luong")})
        return [{"url": links[0], "trang_thai": "xong", "duong_dan": thu_muc, "tieu_de": "Video",
                 "chat_luong": "", "ghi_chu": "2 ảnh PNG"}]

    monkeypatch.setattr(cv, "tai_doan", gia)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    next(t for t in at.text_area if t.label.startswith("Link video")).input(URL[0]).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu video").input(str(tmp_path / "v")).run()
    at.text_input(key="anh_tai").input("12:05, 7:23").run()
    assert any("Chụp 2 ảnh PNG ở 00:07:23, 00:12:05" in c.value for c in at.caption)
    assert at.button(key="bat_dau_tai_video").label == "📸 Tải và chụp 1 video"
    at.text_input(key="tu_tai").input("1:00").run()
    at.text_input(key="den_tai").input("2:00").run()
    assert at.button(key="bat_dau_tai_video").disabled
    assert any("Chỉ chọn một việc" in e.value for e in at.error)
    at.text_input(key="tu_tai").input("").run()
    at.text_input(key="den_tai").input("").run()
    at.radio(key="loai_tai").set_value(tv.LOAI_TAI[1]).run()
    assert at.button(key="bat_dau_tai_video").disabled
    assert any("Chụp ảnh cần video có hình" in e.value for e in at.error)
    at.radio(key="loai_tai").set_value(tv.LOAI_TAI[0]).run()
    at.button(key="bat_dau_tai_video").click().run()
    for _ in range(50):
        if goi and not at.session_state.job["running"]:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert goi == [{"tu_s": None, "ds_bo": None, "ds_moc": [443.0, 725.0], "chat_luong": "Cao nhất"}]


def test_dau_phay_trong_danh_sach_giay():
    assert cv.doc_ds_doan("0-10,100-200,1000-2000") == [(0, 10), (100, 200), (1000, 2000)]
    assert cv.doc_ds_moc("10,20,30") == [10, 20, 30]
    assert cv.doc_ds_moc("1:23,83.5;1:24,5") == [83, 83.5, 84.5]


@can_ffmpeg
def test_bo_doan_giu_tieng_bat_dau_muon(tmp_path):
    nguon = str(tmp_path / "tieng_muon.mkv")
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=64x48:r=30:d=6",
            "-itsoffset", "2", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
            "-c:v", "ffv1", "-c:a", "pcm_s16le", nguon,
        ],
        check=True,
    )
    k = cv.bo_doan(nguon, str(tmp_path / "ra"), [(4.0, 5.0)])
    assert k["trang_thai"] == "xong", k
    assert _tan_so(k["duong_dan"], 3.0) == pytest.approx(440, abs=8)


def test_bo_doan_tua_dau_vao_va_dich_cac_moc(tmp_path, monkeypatch):
    monkeypatch.setattr(cv, "_chay_ra_file", lambda lenh, *args, **kw: lenh)
    giu = [(234000.25, 234002.75), (234005.0, None)]
    lenh = cv._bo(
        str(tmp_path / "nguon.mp4"), str(tmp_path / "ra.mp4"), giu, True, True, huy=None, khi_tien_do=None
    )
    truoc_vao = lenh[:lenh.index("-i")]
    assert "-ss" in truoc_vao
    assert float(truoc_vao[truoc_vao.index("-ss") + 1]) == giu[0][0]
    do_thi = lenh[lenh.index("-filter_complex") + 1]
    for loc in ("[0:v:0]trim", "[0:a:0]atrim"):
        assert f"{loc}=start=0.000:end=2.500," in do_thi
        assert f"{loc}=start=4.750," in do_thi
