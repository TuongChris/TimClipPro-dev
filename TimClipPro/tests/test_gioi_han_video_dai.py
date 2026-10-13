# -*- coding: utf-8 -*-
"""Giới hạn quét VIDEO DÀI chọn theo lô (PC2 12/10/2026: video 65:01:54).

Ràng buộc nghiệm thu:
* video > 6 giờ, chế độ «Tự động» → chỉ TẢI 3 giờ đầu (giới hạn truyền xuống ĐƯỜNG TẢI);
  «6 giờ đầu» → 6 giờ; không quá 6 giờ → như cũ; «toàn bộ» và lô KHÔNG ghim (Watch/CLI) → như cũ;
* phần đầu không thấy gì thì KHÔNG BAO GIỜ tự tải trọn;
* file tải về thiếu (ffmpeg thoát 0 với file cụt) → vùng chưa kiểm; không bằng chứng = LỖI;
* mốc thời gian giữ nguyên (file bắt đầu từ giây 0 của video);
* kết quả ghi rõ ĐÃ quét một phần; «không thấy» không bao giờ thành kết luận cho cả video.
"""

from __future__ import annotations

import json
import os

import pytest

import bao_cao_v2
import lich_su
from engine import (GHVD_6_GIO, GHVD_TOAN_BO, GHVD_TU_DONG, Config, Engine, Match, ScanResult,
                    mo_ta_pham_vi, nhan_pham_vi)
from scan_ui import GOI_Y_VIDEO_DAI, goi_y_quet_mot_phan

DAI_65H = 65 * 3600 + 1 * 60 + 54            # 65:01:54
BA_GIO, SAU_GIO = 3 * 3600, 6 * 3600


def _eng(tmp_path, **cfg):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    e.config = Config(**cfg)
    return e


def _gia_lap(tmp_path, monkeypatch, *, dai=DAI_65H, che_do=GHVD_TU_DONG, matches=(),
             do_dai_file=None, cfg=None):
    """Video giả dài ``dai``; tải giả ghi file vào thư mục tải; quét giả trả đúng thứ bản thật trả
    cho FILE phần đầu (thời lượng = độ dài file, phạm vi đã khớp = cả file)."""
    e = _eng(tmp_path, **(cfg or {"tai_mot_phan": True, "quet_tang_dan_tu_gio": 10.0,
                                  "quet_tang_dan_buoc_gio": 3.0}))
    if che_do is not None:
        e._gioi_han_video_dai = che_do
    monkeypatch.setattr(e, "require", lambda **k: None)
    monkeypatch.setattr(e, "youtube_info", lambda url: {
        "id": "vid65hxxxxx", "title": "65 Hours of SML MOVIE Marathon", "duration": dai,
        "channel": "", "channel_id": "", "channel_url": "", "upload_date": ""})
    lan_tai = []

    def tai(url, vid, progress=None, gioi_han_giay=None):
        lan_tai.append(gioi_han_giay)
        ten = f"{vid}__p{int(gioi_han_giay)}" if gioi_han_giay else vid
        p = os.path.join(e.dl_dir, ten + ".webm")
        with open(p, "wb") as f:
            f.write(b"x")
        return p

    monkeypatch.setattr(e, "download_audio", tai)
    do = {"lan": 0}

    def duration_of(p):
        do["lan"] += 1
        if callable(do_dai_file):
            return do_dai_file(do["lan"])
        if do_dai_file is not None:
            return do_dai_file
        return float(lan_tai[-1] or dai)

    monkeypatch.setattr(e, "duration_of", duration_of)
    # Kiểm toàn vẹn đo ÂM THANH THẬT (``do_dai_audio_that``), không đọc metadata — giả cùng một nguồn số đo.
    monkeypatch.setattr(e, "do_dai_audio_that", duration_of)

    def quet(path, **k):
        dai_file = duration_of(path)
        r = ScanResult(source_name="65 Hours of SML MOVIE Marathon", duration_s=dai_file,
                       pham_vi_quet_s=dai_file, vung_da_khop=[(0.0, dai_file)])
        r.matches = [Match(**{**m.__dict__}) for m in matches]
        return r

    monkeypatch.setattr(e, "scan_media", quet)
    return e, lan_tai


def _m(start):
    return Match(clip="clipA [aaaaaaaaaaa].opus", start_s=float(start), end_s=float(start) + 120,
                 matched_s=110.0, clip_offset_s=0.0, hashes=9000, confidence="chac")


# ---------------------------------------------------------------- chính sách

@pytest.mark.parametrize("che_do,dai,mong", [
    (GHVD_TU_DONG, DAI_65H, BA_GIO),
    (GHVD_6_GIO, DAI_65H, SAU_GIO),
    (GHVD_TU_DONG, 6 * 3600, None),          # đúng ngưỡng 6 giờ: quét như hiện tại
    (GHVD_TU_DONG, 5 * 3600, None),
    (GHVD_6_GIO, 6.5 * 3600, SAU_GIO),
    (GHVD_TU_DONG, 0, BA_GIO),               # không rõ thời lượng: vẫn giới hạn, không tải trọn
    (GHVD_TOAN_BO, DAI_65H, None),
    (None, DAI_65H, None),
])
def test_chinh_sach_gioi_han(che_do, dai, mong):
    assert Engine._gioi_han_video_dai_s(che_do, dai) == mong


# ---------------------------------------------------------------- video 65 giờ

def test_65h_mac_dinh_chi_tai_3h_dau_va_KHONG_tu_tai_tron(tmp_path, monkeypatch):
    e, lan_tai = _gia_lap(tmp_path, monkeypatch)
    kq = e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)

    assert lan_tai == [BA_GIO], "chỉ một lần tải, đúng 3 giờ đầu — không tự nâng lên tải trọn"
    assert kq.status == "ok"
    assert kq.duration_s == DAI_65H, "thời lượng là của VIDEO THẬT"
    assert kq.pham_vi_quet_s == BA_GIO
    assert kq.quet_mot_phan is True and kq.quet_day_du is False
    assert kq.ly_do_pham_vi == "gioi_han_video_dai"
    assert "Không phát hiện kết quả phù hợp trong phạm vi 3 giờ đầu" in kq.note
    assert "03:00:00 → 65:01:54" in kq.note and "KHÔNG phải kết luận cho toàn video" in kq.note


def test_che_do_6_gio(tmp_path, monkeypatch):
    e, lan_tai = _gia_lap(tmp_path, monkeypatch, che_do=GHVD_6_GIO)
    kq = e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)
    assert lan_tai == [SAU_GIO]
    assert kq.pham_vi_quet_s == SAU_GIO and "6 giờ đầu" in kq.note


def test_co_bang_chung_giu_nguyen_moc_tuyet_doi(tmp_path, monkeypatch):
    """File phần đầu bắt đầu từ giây 0 của video: mốc trong file = mốc trên video 65 giờ."""
    e, lan_tai = _gia_lap(tmp_path, monkeypatch, matches=[_m(5000), _m(9000)])
    kq = e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)
    assert lan_tai == [BA_GIO]
    assert sorted(m.start_s for m in kq.matches) == [5000.0, 9000.0]
    assert kq.status == "ok" and kq.quet_mot_phan
    assert "Bằng chứng chỉ nằm trong phần đã quét" in kq.note
    # Nhãn vùng theo VIDEO THẬT: giờ 1,4 và 2,5 của video 65 giờ đều là «Đầu».
    assert {m.vung for m in kq.matches} == {"Đầu"}


def test_bao_cao_va_ten_video_ghi_ro_quet_mot_phan(tmp_path, monkeypatch):
    e, _ = _gia_lap(tmp_path, monkeypatch)
    kq = e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)
    mo_ta = mo_ta_pham_vi(kq)
    assert "03:00:00/65:01:54" in mo_ta and "chưa quét" in mo_ta
    assert nhan_pham_vi(kq).startswith(" [QUÉT MỘT PHẦN")
    assert "gioi_han_video_dai" in bao_cao_v2._LY_DO_PHAM_VI
    assert goi_y_quet_mot_phan([kq]) == [GOI_Y_VIDEO_DAI]


def test_lich_su_khong_ghi_nham_la_tron_video():
    hang = {"day_du": 0, "duration_s": DAI_65H,
            "pham_vi": json.dumps({"ly_do": "gioi_han_video_dai",
                                   "vung_da_khop": [[0, BA_GIO]]})}
    mo_ta = lich_su.mo_ta_pham_vi(hang)
    assert mo_ta.startswith("Một phần") and "giới hạn quét video dài" in mo_ta


# ---------------------------------------------------------------- toàn vẹn audio

def test_file_tai_ve_bi_cut_KHONG_thanh_am_tinh(tmp_path, monkeypatch):
    """ffmpeg có thể thoát 0 với file cụt (G3-A: 86/600 s) — không bao giờ coi là đã quét 3 giờ."""
    e, lan_tai = _gia_lap(tmp_path, monkeypatch, do_dai_file=86.0)
    kq = e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)
    assert lan_tai == [BA_GIO], "file MỚI tải bị cụt: không tự tải lại vòng vòng"
    assert kq.status == "error", "không có bằng chứng + thiếu dữ liệu = chưa kết luận được"
    assert kq.ly_do_pham_vi == "tai_thieu"
    assert kq.vung_loi == [(86.0, float(BA_GIO))]
    assert "chưa được quét" in kq.note and "hãy quét lại" in kq.note
    assert not os.path.exists(os.path.join(e.dl_dir, f"vid65hxxxxx__p{BA_GIO}.webm")), \
        "bản cụt phải bị bỏ khỏi bộ đệm để lần sau tải lại"


def test_file_bi_cut_nhung_co_bang_chung_thi_giu_bang_chung(tmp_path, monkeypatch):
    e, _ = _gia_lap(tmp_path, monkeypatch, do_dai_file=4000.0, matches=[_m(1000)])
    kq = e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)
    assert kq.status == "ok" and [m.start_s for m in kq.matches] == [1000.0]
    assert kq.vung_loi == [(4000.0, float(BA_GIO))] and kq.ly_do_pham_vi == "tai_thieu"


def test_ban_dem_cu_bi_cut_thi_bo_va_tai_lai_mot_lan(tmp_path, monkeypatch):
    e, lan_tai = _gia_lap(tmp_path, monkeypatch,
                          do_dai_file=lambda lan: 86.0 if lan == 1 else float(BA_GIO))
    cu = os.path.join(e.dl_dir, f"vid65hxxxxx__p{BA_GIO}.webm")
    os.makedirs(e.dl_dir, exist_ok=True)
    with open(cu, "wb") as f:
        f.write(b"cu")
    kq = e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)
    assert lan_tai == [BA_GIO, BA_GIO], "bản đệm cụt: bỏ rồi tải lại ĐÚNG một lần"
    assert kq.status == "ok" and kq.ly_do_pham_vi == "gioi_han_video_dai"


def test_khong_ro_thoi_luong_thi_pham_vi_chua_xac_nhan(tmp_path, monkeypatch):
    e, lan_tai = _gia_lap(tmp_path, monkeypatch, dai=0, do_dai_file=float(BA_GIO))
    kq = e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)
    assert lan_tai == [BA_GIO], "không rõ thời lượng: vẫn giới hạn, không tải trọn"
    assert kq.vung_da_khop is None and not kq.quet_day_du, "không được khẳng định đã quét trọn"
    assert kq.ly_do_pham_vi == "thoi_luong_chua_ro"
    assert kq.status == "error", "không có bằng chứng thì không thành âm tính"


# ---------------------------------------------------------------- hành vi cũ giữ nguyên

def test_video_khong_qua_6_gio_quet_nhu_cu(tmp_path, monkeypatch):
    e, lan_tai = _gia_lap(tmp_path, monkeypatch, dai=5 * 3600)
    kq = e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)
    assert lan_tai == [None], "video 5 giờ: tải trọn như hiện tại"
    assert kq.ly_do_pham_vi != "gioi_han_video_dai"


@pytest.mark.parametrize("che_do", [GHVD_TOAN_BO, None])
def test_toan_bo_va_lo_khong_ghim_giu_hanh_vi_cu(tmp_path, monkeypatch, che_do):
    """«Quét toàn bộ» (người dùng chủ động) và Watch/CLI (không ghim): 3 giờ đầu rồi tải trọn
    khi chưa đủ bằng chứng — đúng hành vi cũ, kể cả cho video 65 giờ."""
    e, lan_tai = _gia_lap(tmp_path, monkeypatch, che_do=che_do)
    e.scan_youtube("https://youtu.be/vid65hxxxxx", luu_lich_su=False)
    assert lan_tai == [BA_GIO, None]


def test_scan_iter_ghim_che_do_tren_ban_sao_va_go_sau_lo(tmp_path, monkeypatch):
    e, lan_tai = _gia_lap(tmp_path, monkeypatch, che_do=None)
    ket = list(e.scan_iter(["https://youtu.be/vid65hxxxxx"], "youtube",
                           gioi_han_video_dai=GHVD_TU_DONG))
    assert lan_tai == [BA_GIO] and ket[0].ly_do_pham_vi == "gioi_han_video_dai"
    assert getattr(e, "_gioi_han_video_dai", None) is None, "Engine gốc không mang chế độ của lô"
    lan_tai.clear()
    list(e.scan_iter(["https://youtu.be/vid65hxxxxx"], "youtube"))
    assert lan_tai == [BA_GIO, None], "lô sau không ghim → hành vi cũ"


def test_scan_iter_tu_choi_che_do_la(tmp_path):
    e = _eng(tmp_path)
    with pytest.raises(ValueError):
        list(e.scan_iter(["u"], "youtube", gioi_han_video_dai="10h"))
