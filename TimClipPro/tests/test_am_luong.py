# -*- coding: utf-8 -*-
"""Chuẩn hoá âm lượng về mức YouTube (D-43): file tổng hợp THẬT bằng FFmpeg, đo độ to bằng ebur128 thật.

Bối cảnh 10/11: video Joe Bartolozzi tải về đo -28,5 LUFS, video SSS -14; xem trên YouTube nghe to vì «Âm lượng ổn định»
— tắt đi thì nhỏ y như file tải (người dùng tự thử)."""

import os
import re
import shutil
import subprocess

import pytest

import am_luong as al

can_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="cần FFmpeg"
)


def _tao(path, bien_do, giay=8, chi_tieng=False):
    vao = (
        []
        if chi_tieng
        else ["-f", "lavfi", "-i", f"testsrc=size=160x120:rate=25:duration={giay}"]
    )
    ma = (["-c:a", "libopus"] if str(path).endswith(".webm") else ["-c:a", "aac"]) + (
        []
        if chi_tieng
        else [
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
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
            f"aevalsrc={bien_do}*sin(2*PI*440*t)*(0.6+0.4*sin(2*PI*0.5*t)):s=44100:d={giay}",
            *ma,
            str(path),
        ],
        check=True,
    )
    return str(path)


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


def _md5_hinh(path):
    return subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            path,
            "-map",
            "0:v",
            "-c",
            "copy",
            "-f",
            "md5",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@can_ffmpeg
def test_video_nho_duoc_keo_len_muc_youtube_hinh_giu_nguyen(tmp_path):
    f = _tao(tmp_path / "nho.mp4", 0.01)
    assert _lufs(f) < -30
    hinh = _md5_hinh(f)
    ghi_chu = al.chuan_hoa(f)
    assert "→ -14 LUFS" in ghi_chu
    assert _lufs(f) == pytest.approx(al.MUC_LUFS, abs=1.0)
    assert _md5_hinh(f) == hinh  # hình chép nguyên từng byte
    p = al.doc_ffprobe(f)
    tieng = next(s for s in p["streams"] if s["codec_type"] == "audio")
    assert (
        tieng["sample_rate"] == "44100"
    )  # loudnorm tự đẩy lên 192 kHz nếu không ép lại
    assert float(p["format"]["duration"]) == pytest.approx(8.0, abs=0.1)
    assert sorted(os.listdir(tmp_path)) == ["nho.mp4"]  # không để lại file tạm


@can_ffmpeg
def test_da_o_muc_youtube_thi_giu_nguyen_tung_byte(tmp_path):
    f = _tao(tmp_path / "to.mp4", 0.01)
    al.chuan_hoa(f)
    truoc = open(f, "rb").read()
    assert "giữ nguyên" in al.chuan_hoa(f)  # gọi lần hai: không nén lại lần nữa
    assert open(f, "rb").read() == truoc


@can_ffmpeg
def test_chi_tieng_webm_giu_opus(tmp_path):
    f = _tao(tmp_path / "nho [abcdefghij1].audio.webm", 0.01, chi_tieng=True)
    al.chuan_hoa(f)
    assert _lufs(f) == pytest.approx(al.MUC_LUFS, abs=1.0)
    assert [s["codec_name"] for s in al.doc_ffprobe(f)["streams"]] == ["opus"]


@can_ffmpeg
def test_im_lang_hoan_toan_khong_loi(tmp_path):
    f = _tao(tmp_path / "lang.mp4", 0)
    truoc = open(f, "rb").read()
    assert "không có tiếng" in al.chuan_hoa(f)
    assert open(f, "rb").read() == truoc


def test_ffmpeg_loi_thi_bao_loi_va_giu_file(tmp_path):
    f = tmp_path / "hong.mp4"
    f.write_bytes(b"khong phai video")
    with pytest.raises(RuntimeError):
        al.chuan_hoa(str(f))
    assert f.read_bytes() == b"khong phai video"
