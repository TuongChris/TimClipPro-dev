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
    assert k["duong_dan"].endswith("Phim của tôi (00.00.01-00.00.03).mp4")
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
    assert k["duong_dan"].endswith("nho (-14 LUFS).mp4")
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
def test_dung_giua_chung(tmp_path):
    a, b = _tao(tmp_path / "a.mp4"), _tao(tmp_path / "b.mp4")
    ra = tmp_path / "ra"

    def huy():  # bấm Dừng ngay khi file đầu cắt xong
        return ra.is_dir() and any(f.suffix == ".mp4" for f in ra.iterdir())

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
