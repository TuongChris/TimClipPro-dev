# -*- coding: utf-8 -*-
"""Độ dài âm thanh THẬT của file tải về — không tin ``format.duration`` (metadata) của ffprobe.

Tái hiện (người dùng, 13/10/2026): WebM nguồn 30 giây bị cắt đuôi còn ~7,8 giây âm thanh, ffprobe vẫn
báo ``format.duration = 30.008`` — độ dài ghi ở ĐẦU file. ``_quet_video_dai_gioi_han`` dùng số đó để
kiểm «tải đủ phạm vi» nên file cụt lọt qua như file hoàn chỉnh, và bản đệm cụt được dùng lại.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from engine import Config, Engine, ScanResult

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                reason="cần ffmpeg/ffprobe trên PATH")

DAI_GOC_S = 30.0


@pytest.fixture(scope="module")
def webm(tmp_path_factory):
    d = tmp_path_factory.mktemp("webm_cut")
    goc = d / "goc.webm"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=440:sample_rate=16000:duration={int(DAI_GOC_S)}", "-ac", "1",
                        "-c:a", "libopus", "-b:a", "24k", str(goc)], capture_output=True, timeout=60)
    if r.returncode != 0 or not goc.exists():
        pytest.skip("ffmpeg không mã hoá được opus/webm trên máy này")
    du = goc.read_bytes()
    cut = d / "cut.webm"
    cut.write_bytes(du[: int(len(du) * 0.26)])            # ~7,8 giây âm thanh, đầu file còn nguyên
    return goc, cut


def test_bay_metadata_ffprobe_van_bao_do_dai_goc(webm):
    """Đúng hiện tượng tái hiện: file đã cụt mà ffprobe vẫn báo độ dài gốc."""
    _goc, cut = webm
    assert Engine.duration_of(str(cut)) == pytest.approx(DAI_GOC_S, abs=0.5)


def test_do_dai_audio_that_doc_den_goi_cuoi(webm):
    goc, cut = webm
    assert Engine.do_dai_audio_that(str(goc)) == pytest.approx(DAI_GOC_S, abs=0.5)
    that = Engine.do_dai_audio_that(str(cut))
    assert that is not None and 4.0 < that < 12.0, that


def test_khong_doc_duoc_thi_none(tmp_path):
    hong = tmp_path / "hong.webm"
    hong.write_bytes(b"khong phai media")
    assert Engine.do_dai_audio_that(str(hong)) is None


def _engine(tmp_path, monkeypatch, nguon_tai):
    """Engine với tải giả: có bản đệm thì trả bản đệm (như ``download_audio`` thật), không có thì
    «tải» bằng cách chép ``nguon_tai()`` vào thư mục đệm. Quét giả: không đụng kho vân tay."""
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    e.config = Config()
    lan = []

    def tai(url, vid, progress=None, gioi_han_giay=None):
        p = os.path.join(e.dl_dir, f"{vid}__p{int(gioi_han_giay)}.webm")
        lan.append(os.path.exists(p))                      # True = dùng lại bản đệm
        if not os.path.exists(p):
            os.makedirs(e.dl_dir, exist_ok=True)
            shutil.copyfile(nguon_tai(), p)
        return p

    monkeypatch.setattr(e, "download_audio", tai)
    monkeypatch.setattr(e, "scan_media", lambda path, **k: ScanResult(
        source_name="v", duration_s=DAI_GOC_S, pham_vi_quet_s=DAI_GOC_S,
        vung_da_khop=[(0.0, DAI_GOC_S)]))
    return e, lan


INFO = {"id": "vidcutxxxxx", "title": "v", "duration": 65 * 3600.0, "channel": "", "channel_id": "",
        "channel_url": "", "upload_date": ""}


def test_ban_dem_cut_giu_metadata_goc_bi_bo_va_tai_lai(tmp_path, monkeypatch, webm):
    goc, cut = webm
    e, lan = _engine(tmp_path, monkeypatch, nguon_tai=lambda: str(goc))
    p = os.path.join(e.dl_dir, f"{INFO['id']}__p{int(DAI_GOC_S)}.webm")
    os.makedirs(e.dl_dir, exist_ok=True)
    shutil.copyfile(cut, p)                                # bản đệm CỤT của lượt trước
    r, f = e._quet_video_dai_gioi_han("https://youtu.be/x", INFO, "v", DAI_GOC_S, None)
    assert lan == [True, False], "bản đệm cụt phải bị bỏ và tải lại MỘT lần, không dùng lại"
    assert r.status == "ok" and r.ly_do_pham_vi == "gioi_han_video_dai" and not r.vung_loi


def test_tai_moi_bi_cut_giu_metadata_goc_la_vung_chua_kiem(tmp_path, monkeypatch, webm):
    _goc, cut = webm
    e, lan = _engine(tmp_path, monkeypatch, nguon_tai=lambda: str(cut))
    r, f = e._quet_video_dai_gioi_han("https://youtu.be/x", INFO, "v", DAI_GOC_S, None)
    assert lan == [False], "file MỚI tải bị cụt: không tự tải lại vòng vòng"
    assert r.ly_do_pham_vi == "tai_thieu" and r.status == "error"
    (a, b), = r.vung_loi
    assert 4.0 < a < 12.0 and b == DAI_GOC_S, r.vung_loi
    assert not os.path.exists(f), "bản cụt không được nằm lại trong bộ đệm để lượt sau dùng như file đủ"
