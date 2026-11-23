# -*- coding: utf-8 -*-
"""Cắt / chỉnh âm lượng video ĐÃ CÓ trong máy (D-46): file tổng hợp THẬT bằng FFmpeg. Bất biến: file gốc không bao giờ
bị sửa — so băm trước/sau."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess

import pytest

import video_trong_may as vm

can_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="cần FFmpeg"
)


def _tao(path, giay=6, bien_do=0.05):
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
            f"testsrc=size=160x120:rate=25:duration={giay}",
            "-f",
            "lavfi",
            "-i",
            f"aevalsrc={bien_do}*sin(2*PI*440*t)*(0.6+0.4*sin(2*PI*0.5*t)):s=44100:d={giay}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
    )
    return str(path)


def _bam(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _dai(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-of", "json", path],
        capture_output=True,
        text=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def _lufs(path):
    r = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            path,
            "-vn",
            "-af",
            "ebur128",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])


# ---------------------------------------------------------------- tách danh sách file
def test_tach_file_file_thu_muc_va_loi(tmp_path):
    a = tmp_path / "b.mp4"
    a.write_bytes(b"x")
    tm = tmp_path / "tm"
    (tm / "con").mkdir(parents=True)
    for ten in ("2.mkv", "1.MP4", "ghi_chu.txt"):
        (tm / ten).write_bytes(b"x")
    (tm / "con" / "3.mp4").write_bytes(
        b"x"
    )  # thư mục con không lấy: kết quả lưu vào thư mục con thì bấm lại không xử lý lại
    files, loi = vm.tach_file(
        f'"{a}"\n\n{tm}\n{a}\n{tmp_path / "khong_co.mp4"}\n{tm / "ghi_chu.txt"}\n'
    )
    assert files == [str(a), str(tm / "1.MP4"), str(tm / "2.mkv")]
    assert len(loi) == 2 and "Không tìm thấy" in loi[0] and "không phải video" in loi[1]


def test_khong_chon_viec_nao_bao_loi(tmp_path):
    with pytest.raises(ValueError, match="ít nhất một việc"):
        vm.xu_ly([str(tmp_path / "a.mp4")], str(tmp_path))


# ---------------------------------------------------------------- cắt / chỉnh âm
@can_ffmpeg
def test_cat_file_trong_may_giu_nguyen_file_goc(tmp_path):
    goc = _tao(tmp_path / "Phim của tôi.mp4")
    bam = _bam(goc)
    k = vm.xu_ly([goc], str(tmp_path / "ra"), tu_s=1, den_s=3)[0]
    assert k["trang_thai"] == "xong", k
    assert k["duong_dan"].endswith("Phim_cua_toi_00-00-01_00-00-03.mp4")
    assert _dai(k["duong_dan"]) == pytest.approx(2, abs=0.06)
    assert _bam(goc) == bam and k["la_file_may"] is True


@can_ffmpeg
def test_cat_va_chinh_am_cung_thu_muc_khong_ghi_de(tmp_path):
    goc = _tao(tmp_path / "a.mp4")
    bam = _bam(goc)
    k = vm.xu_ly([goc], str(tmp_path), tu_s=0, den_s=4, chuan_hoa_am=True)[
        0
    ]  # lưu ngay cạnh file gốc
    assert k["trang_thai"] == "xong", k
    assert (
        _lufs(k["duong_dan"]) == pytest.approx(-14, abs=1.0) and "LUFS" in k["ghi_chu"]
    )
    assert _bam(goc) == bam


@can_ffmpeg
def test_chi_chinh_am_ra_file_moi(tmp_path):
    goc = _tao(tmp_path / "nho.mp4")
    bam = _bam(goc)
    k = vm.xu_ly([goc], str(tmp_path / "ra"), chuan_hoa_am=True)[0]
    assert k["trang_thai"] == "xong", k
    assert k["duong_dan"].endswith("nho_am_luong_YouTube.mp4")
    assert _lufs(k["duong_dan"]) == pytest.approx(-14, abs=1.0)
    assert _dai(k["duong_dan"]) == pytest.approx(_dai(goc), abs=0.1)
    assert _bam(goc) == bam
    # Bản vừa ra đã ở mức YouTube: chỉnh lần nữa không tạo file mới.
    k2 = vm.xu_ly([k["duong_dan"]], str(tmp_path / "ra2"), chuan_hoa_am=True)[0]
    assert k2["trang_thai"] == "bo_qua" and "giữ nguyên" in k2["ghi_chu"]
    assert not (tmp_path / "ra2").exists() or not list((tmp_path / "ra2").iterdir())


@can_ffmpeg
def test_doan_vuot_do_dai_bao_loi_file_goc_giu_nguyen(tmp_path):
    goc = _tao(tmp_path / "a.mp4")
    k = vm.xu_ly([goc], str(tmp_path / "ra"), tu_s=2, den_s=60)[0]
    assert (
        k["trang_thai"] == "loi"
        and "chỉ dài" in k["ghi_chu"]
        and "File gốc giữ nguyên" in k["ghi_chu"]
    )


@can_ffmpeg
def test_dung_giua_chung(tmp_path, monkeypatch):
    a, b = _tao(tmp_path / "a.mp4"), _tao(tmp_path / "b.mp4")
    ra = tmp_path / "ra"
    da_xong = []
    cat_that = vm.cv.cat_hoac_bo

    def cat_dem(*args, **kw):
        k = cat_that(*args, **kw)
        da_xong.append(k)
        return k

    monkeypatch.setattr(vm.cv, "cat_hoac_bo", cat_dem)

    # bấm Dừng ngay khi file đầu cắt xong — đợi hàm cắt TRẢ VỀ, không nhìn file .mp4 (FFmpeg ghi file
    # khi còn đang chạy: máy bận thì file 1 bị huỷ giữa chừng, 23/11/2026)
    def huy():
        return bool(da_xong)

    kq = vm.xu_ly([a, b], str(ra), tu_s=0, den_s=2, cancel_check=huy)
    assert [k["trang_thai"] for k in kq] == ["xong", "bo_qua"]


# ---------------------------------------------------------------- giao diện
def test_tab_video_trong_may_goi_xu_ly(tmp_path, monkeypatch):
    import time
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    goi = {}

    def xu_ly_gia(
        files,
        thu_muc,
        cau_hinh_mang=None,
        *,
        tu_s,
        den_s,
        chuan_hoa_am,
        progress,
        cancel_check,
        **kw,
    ):
        goi.update(
            files=files,
            thu_muc=thu_muc,
            tu_s=tu_s,
            den_s=den_s,
            chuan_hoa_am=chuan_hoa_am,
        )
        return [
            {
                "url": files[0],
                "trang_thai": "xong",
                "duong_dan": thu_muc + "/a (cắt).mp4",
                "tieu_de": "a",
                "chat_luong": "file trong máy",
                "ghi_chu": "",
                "la_file_may": True,
            }
        ]

    monkeypatch.setattr(vm, "xu_ly", xu_ly_gia)
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120
    ).run()
    assert not at.exception
    next(
        t for t in at.text_area if t.label.startswith("Đường dẫn video trong máy")
    ).input(str(f)).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu kết quả").input(
        str(tmp_path / "ra")
    ).run()
    at.text_input(key="tu_may").input("0:01").run()
    at.text_input(key="den_may").input("0:03.5").run()
    at.button(key="bat_dau_xu_ly_may").click().run()
    for _ in range(50):
        if goi and not at.session_state.job["running"]:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert goi == {
        "files": [str(f)],
        "thu_muc": str(tmp_path / "ra"),
        "tu_s": 1.0,
        "den_s": 3.5,
        "chuan_hoa_am": True,
    }
    chu = " ".join(e.value for e in [*at.markdown, *at.warning, *at.success])
    assert "Đã xử lý 1/1" in chu


# ---------------------------------------------------------------- bỏ các đoạn (D-59, 17/11)
@can_ffmpeg
def test_bo_doan_file_trong_may_giu_nguyen_file_goc(tmp_path):
    goc = _tao(tmp_path / "Phim hay.mp4", giay=10)
    bam = _bam(goc)
    k = vm.xu_ly([goc], str(tmp_path / "ra"), ds_bo=[(1.0, 2.5), (6.0, 7.0)])[0]
    assert k["trang_thai"] == "xong", k
    assert k["duong_dan"].endswith("Phim_hay_bo_2_doan.mp4")
    assert _dai(k["duong_dan"]) == pytest.approx(7.5, abs=0.1)
    assert _bam(goc) == bam


def test_bo_doan_va_tu_den_cung_luc_bao_loi(tmp_path):
    with pytest.raises(ValueError, match="Chỉ chọn một việc"):
        vm.xu_ly([str(tmp_path / "a.mp4")], str(tmp_path), tu_s=1, den_s=2, ds_bo=[(3.0, 4.0)])


def test_tab_video_trong_may_bo_cac_doan(tmp_path, monkeypatch):
    import time
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    goi = {}

    def xu_ly_gia(files, thu_muc, cau_hinh_mang=None, *, tu_s, den_s, ds_bo, chuan_hoa_am, progress, cancel_check,
                  **kw):
        goi.update(tu_s=tu_s, ds_bo=ds_bo, chuan_hoa_am=chuan_hoa_am)
        return [{"url": files[0], "trang_thai": "xong", "duong_dan": thu_muc + "/a_bo_1_doan.mp4", "tieu_de": "a",
                 "chat_luong": "file trong máy", "ghi_chu": "", "la_file_may": True}]

    monkeypatch.setattr(vm, "xu_ly", xu_ly_gia)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    next(t for t in at.text_area if t.label.startswith("Đường dẫn video trong máy")).input(str(f)).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu kết quả").input(str(tmp_path / "ra")).run()
    at.checkbox(key="am_may").uncheck().run()
    at.text_area(key="bo_may").input("0:04:12 0:05:24 xx").run()
    assert at.button(key="bat_dau_xu_ly_may").disabled
    assert any("Không đọc được «xx»" in e.value for e in at.error)
    at.text_area(key="bo_may").input("1:01:02 - 1:01:11").run()
    at.button(key="bat_dau_xu_ly_may").click().run()
    for _ in range(50):
        if goi and not at.session_state.job["running"]:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert goi == {"tu_s": None, "ds_bo": [(3662.0, 3671.0)], "chuan_hoa_am": False}


@can_ffmpeg
def test_xu_ly_chup_anh_khong_dung_file_goc(tmp_path):
    """Chụp ảnh file trong máy (18/11): ra PNG, bỏ qua ô chỉnh âm lượng, file gốc giữ nguyên từng byte."""
    goc = _tao(tmp_path / "a.mp4")
    bam = _bam(goc)
    k = vm.xu_ly([goc], str(tmp_path / "ra"), ds_moc=[1.0, 3.5], chuan_hoa_am=True)[0]
    assert k["trang_thai"] == "xong", k
    assert sorted(p.name for p in (tmp_path / "ra").iterdir()) == ["a_00-00-01.png", "a_00-00-03-5.png"]
    assert _bam(goc) == bam
    with pytest.raises(ValueError, match="Chỉ chọn một việc"):
        vm.xu_ly([goc], str(tmp_path), tu_s=0, den_s=2, ds_moc=[1.0])


def test_tab_video_trong_may_chup_anh_goi_xu_ly(tmp_path, monkeypatch):
    """AppTest: điền mốc chụp ảnh → nút «📸 Chụp ảnh», xu_ly nhận ds_moc đã đọc; điền thêm «Từ»/«Đến» → nút tắt."""
    import time
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    goi = []

    def xu_ly_gia(files, thu_muc, cau_hinh_mang=None, *, progress=None, cancel_check=None, **kw):
        goi.append({k: kw.get(k) for k in ("tu_s", "ds_bo", "ds_moc")})
        return [{"url": files[0], "trang_thai": "xong", "duong_dan": thu_muc, "tieu_de": "a",
                 "chat_luong": "file trong máy", "ghi_chu": "2 ảnh PNG", "la_file_may": True}]

    monkeypatch.setattr(vm, "xu_ly", xu_ly_gia)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    next(t for t in at.text_area if t.label.startswith("Đường dẫn video trong máy")).input(str(f)).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu kết quả").input(str(tmp_path / "ra")).run()
    at.text_input(key="anh_may").input("0:03.5, 0:01").run()
    assert any("Chụp 2 ảnh PNG ở 00:00:01, 00:00:03,5 mỗi file" in c.value for c in at.caption)
    assert at.button(key="bat_dau_xu_ly_may").label == "📸 Chụp ảnh 1 file"
    at.text_input(key="tu_may").input("0:01").run()
    at.text_input(key="den_may").input("0:02").run()
    assert at.button(key="bat_dau_xu_ly_may").disabled
    assert any("Chỉ chọn một việc" in e.value for e in at.error)
    at.text_input(key="tu_may").input("").run()
    at.text_input(key="den_may").input("").run()
    at.button(key="bat_dau_xu_ly_may").click().run()
    for _ in range(50):
        if goi and not at.session_state.job["running"]:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert goi == [{"tu_s": None, "ds_bo": None, "ds_moc": [1.0, 3.5]}]


# ---------------------------------------------------------------- file kiểm claim (D-64)
def _luong(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    hinh = next(x for x in d["streams"] if x["codec_type"] == "video")
    tieng = next(x for x in d["streams"] if x["codec_type"] == "audio")
    return hinh, tieng, float(d["format"]["duration"])


def _md5_tieng(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:a:0", "-c", "copy", "-f", "md5", "-"],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


@can_ffmpeg
def test_kiem_claim_giu_nguyen_tieng_aac_khung_den_dung_do_dai(tmp_path):
    """Tiếng AAC → chép nguyên (giống từng byte), khung đen 256×144 1 hình/giây dài ĐÚNG bằng file gốc (``-shortest``
    thừa 5–10 giây), ô chỉnh âm lượng bị bỏ qua, file gốc giữ nguyên."""
    goc = _tao(tmp_path / "Phim của tôi.mp4")
    bam = _bam(goc)
    k = vm.xu_ly([goc], str(tmp_path / "ra"), kiem_claim="goc", chuan_hoa_am=True)[0]
    assert k["trang_thai"] == "xong", k
    assert k["duong_dan"].endswith("Phim_cua_toi_kiem_claim.mp4")
    assert "tiếng giữ nguyên" in k["ghi_chu"]
    hinh, tieng, dai = _luong(k["duong_dan"])
    assert (hinh["codec_name"], hinh["width"], hinh["height"], hinh["r_frame_rate"]) == ("h264", 256, 144, "1/1")
    assert tieng["codec_name"] == "aac"
    assert _md5_tieng(k["duong_dan"]) == _md5_tieng(goc)
    assert dai == pytest.approx(_dai(goc), abs=0.05)
    assert _bam(goc) == bam
    assert sorted(x.name for x in (tmp_path / "ra").iterdir()) == ["Phim_cua_toi_kiem_claim.mp4"]


@can_ffmpeg
def test_kiem_claim_giu_do_tre_cua_tieng(tmp_path):
    """Tiếng vào trễ 1 giây so với hình → file kiểm claim giữ đúng độ trễ: mốc claim khớp bản gốc."""
    tam = _tao(tmp_path / "tam.mp4")
    goc = str(tmp_path / "tre.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tam, "-itsoffset", "1", "-i", tam, "-map", "0:v", "-map",
                    "1:a", "-c", "copy", goc], check=True)
    k = vm.tao_file_kiem_claim(goc, str(tmp_path / "ra"))
    assert k["trang_thai"] == "xong", k
    assert float(_luong(k["duong_dan"])[1]["start_time"]) == pytest.approx(float(_luong(goc)[1]["start_time"]), abs=0.001)
    assert float(_luong(goc)[1]["start_time"]) > 0.9


@can_ffmpeg
@pytest.mark.parametrize("muc", ["goc", "96k"])
def test_kiem_claim_nen_aac_khi_tieng_goc_khong_phai_aac_hoac_chon_nhe(tmp_path, muc):
    """Tiếng gốc MP3 (MP4 cần AAC) → nén AAC 320k dù chọn «giữ nguyên»; chọn «nhẹ» → nén AAC 96k."""
    goc = str(tmp_path / "bai.mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                    "-c:a", "libmp3lame", goc], check=True)
    k = vm.tao_file_kiem_claim(goc, str(tmp_path), muc)
    assert k["trang_thai"] == "xong", k
    assert ("nén AAC 320k" if muc == "goc" else "nén AAC 96k") in k["ghi_chu"]
    hinh, tieng, dai = _luong(k["duong_dan"])
    assert tieng["codec_name"] == "aac" and hinh["width"] == 256
    assert dai == pytest.approx(4, abs=0.1)


@can_ffmpeg
def test_kiem_claim_file_khong_co_tieng_bao_loi(tmp_path):
    goc = str(tmp_path / "cam.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=5:duration=2",
                    "-c:v", "libx264", "-preset", "ultrafast", goc], check=True)
    k = vm.tao_file_kiem_claim(goc, str(tmp_path / "ra"))
    assert k["trang_thai"] == "loi" and "không có tiếng" in k["ghi_chu"]


def test_kiem_claim_cung_cat_doan_bao_loi(tmp_path):
    with pytest.raises(ValueError, match="Chỉ chọn một việc"):
        vm.xu_ly([str(tmp_path / "a.mp4")], str(tmp_path), kiem_claim="goc", tu_s=0, den_s=2)
    with pytest.raises(ValueError, match="Mức tiếng"):
        vm.tao_file_kiem_claim(str(tmp_path / "a.mp4"), str(tmp_path), "320k")


def test_tab_video_trong_may_tao_file_kiem_claim(tmp_path, monkeypatch):
    """AppTest: tick «🎧 Tạo file kiểm claim» → nút đổi nhãn, ô chỉnh âm lượng ẩn, xu_ly nhận kiem_claim theo lựa chọn
    (mặc định «goc») và chuan_hoa_am=False; điền thêm «Từ»/«Đến» → báo lỗi, nút tắt."""
    import time
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    goi = []

    def xu_ly_gia(files, thu_muc, cau_hinh_mang=None, *, progress=None, cancel_check=None, **kw):
        goi.append({k: kw.get(k) for k in ("kiem_claim", "chuan_hoa_am", "tu_s")})
        return [{"url": files[0], "trang_thai": "xong", "duong_dan": thu_muc, "tieu_de": "a",
                 "chat_luong": "file trong máy", "ghi_chu": "File kiểm claim", "la_file_may": True}]

    monkeypatch.setattr(vm, "xu_ly", xu_ly_gia)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    next(t for t in at.text_area if t.label.startswith("Đường dẫn video trong máy")).input(str(f)).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu kết quả").input(str(tmp_path / "ra")).run()
    at.checkbox(key="kiem_claim_may").check().run()
    assert at.button(key="bat_dau_xu_ly_may").label == "🎧 Tạo file kiểm claim 1 file"
    assert not [c for c in at.checkbox if c.key == "am_may"]
    assert at.radio(key="muc_kiem_claim_may").value == "goc"
    at.text_input(key="tu_may").input("0:01").run()
    at.text_input(key="den_may").input("0:02").run()
    assert at.button(key="bat_dau_xu_ly_may").disabled
    assert any("Chỉ chọn một việc" in e.value for e in at.error)
    at.text_input(key="tu_may").input("").run()
    at.text_input(key="den_may").input("").run()
    at.radio(key="muc_kiem_claim_may").set_value("96k").run()
    at.button(key="bat_dau_xu_ly_may").click().run()
    for _ in range(50):
        if goi and not at.session_state.job["running"]:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert goi == [{"kiem_claim": "96k", "chuan_hoa_am": False, "tu_s": None}]
