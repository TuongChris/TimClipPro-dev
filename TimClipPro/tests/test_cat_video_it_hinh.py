# -*- coding: utf-8 -*-
"""Cắt / bỏ đoạn video ÍT hình mỗi giây không bị «Không tin được» oan (việc nhỏ #40, thử thật 24/11 với nguồn
1 hình/giây), và lỗi FFmpeg bị canh dừng nói bằng câu tiếng Việt thay mã nội bộ «im_lang» (việc nhỏ #37).

Video tổng hợp THẬT bằng FFmpeg (1 hình/giây), không mạng.
"""

import shutil
import subprocess

import pytest

import cat_video_goc as cv
from process_runner import KetQuaLenh

can_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="cần FFmpeg")


def _tao_1_hinh_giay(path, co_tieng=True):
    tieng = ["-f", "lavfi", "-i", "sine=frequency=440:duration=10"] if co_tieng else []
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         "testsrc=size=160x120:rate=1:duration=10", *tieng, "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", *(["-c:a", "aac", "-shortest"] if co_tieng else []), str(path)],
        check=True,
    )
    return str(path)


@can_ffmpeg
@pytest.mark.parametrize("co_tieng", [True, False])
def test_nguon_1_hinh_giay_cat_va_bo_doan_khong_bao_oan(tmp_path, co_tieng):
    src = _tao_1_hinh_giay(tmp_path / "nguon.mp4", co_tieng)
    assert cv._do(src)[3] == pytest.approx(1.0)  # một khung hình dài 1 giây
    k = cv.cat_mot(src, str(tmp_path / "ra"), 2.5, 6.2)  # mốc rơi giữa hai khung hình
    assert k["trang_thai"] == "xong", k
    assert not str(k["duong_dan"]).endswith(".loi.mp4")
    k = cv.bo_doan(src, str(tmp_path / "bo"), [(1.3, 2.6), (5.5, 7.2)])
    assert k["trang_thai"] == "xong", k


@can_ffmpeg
def test_nguon_1_hinh_giay_lech_qua_mot_khung_van_bi_bat(tmp_path, monkeypatch):
    """Nới theo độ dài khung hình, không phải bỏ kiểm: file ra lệch hơn một khung hình vẫn «Không tin được»."""
    src = _tao_1_hinh_giay(tmp_path / "nguon.mp4")
    goc = cv._do
    monkeypatch.setattr(cv, "_do", lambda p: goc(p) if p == src else (3.7 + 1.5, True, True, 1.0))
    k = cv.cat_mot(src, str(tmp_path / "ra"), 2.5, 6.2)
    assert k["trang_thai"] == "loi" and "Không tin được" in k["ghi_chu"]


@can_ffmpeg
def test_file_chi_co_tieng_khong_co_khung_hinh(tmp_path):
    p = tmp_path / "tieng.m4a"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=3", "-c:a", "aac", str(p)], check=True)
    assert cv._do(str(p))[1:] == (False, True, 0.0)  # chỉ có tiếng → giữ ngưỡng 0,06 giây


def test_ffmpeg_bi_canh_dung_noi_cau_tieng_viet(tmp_path):
    r = KetQuaLenh(returncode=1, stdout="", stderr="", timed_out=True, ly_do="im_lang")
    k = cv._kiem_va_chinh_am(r, str(tmp_path / "ra.mp4"), str(tmp_path), 2.0, 0.06, chuan_hoa_am=False,
                             huy=lambda: False, bao=lambda *_: None, nhan="", giu="", ghi_xong="")
    assert k["trang_thai"] == "loi"
    assert "im_lang" not in k["ghi_chu"] and "đứng im" in k["ghi_chu"]


def test_mo_ta_loi_lenh_media():
    assert "im_lang" not in KetQuaLenh(1, "", "", timed_out=True, ly_do="im_lang").mo_ta_loi()
    r = KetQuaLenh(1, "", "Invalid data found when processing input", timed_out=True, ly_do="im_lang")
    assert "đứng im" in r.mo_ta_loi() and "Invalid data" in r.mo_ta_loi()
    assert "tran_tong" not in KetQuaLenh(-1, "", "", timed_out=True, ly_do="tran_tong").mo_ta_loi()
    assert KetQuaLenh(1, "", "x" * 500).mo_ta_loi(300) == "x" * 300
    assert KetQuaLenh(3, "", "").mo_ta_loi() == "mã thoát 3"
    assert KetQuaLenh(0, "", "").mo_ta_loi() == "không có thông báo lỗi"  # thoát 0 mà không ghi ra file
