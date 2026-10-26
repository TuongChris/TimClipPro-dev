# -*- coding: utf-8 -*-
"""Audit A-5 [P2] — GHVD (giới hạn video dài) khi YouTube KHÔNG cho biết thời lượng (duration 0).

Synthetic, không mạng: video giả, tải giả, quét giả trả đúng thứ ``scan_media`` thật trả cho FILE
phần đầu (``duration_s`` = độ dài file, nhãn vùng ``_gan_chi_so`` tính theo file).

Hành vi ĐÚNG (theo docs/LOI_DA_GAP.md mục 16 «Đổi duration_s ở đâu thì gọi _dan_lai_nhan_vung ngay
sau đó», hợp đồng ``Engine._nhan_vung``: thời lượng không dương → nhãn rỗng, và
``bao_cao_v2.hien_thi_thoi_luong``: không có thời lượng → ô trống):
* thời lượng video chưa rõ → không khẳng định video dài 00:00:00 (Sheets cột 7, hồ sơ);
* nhãn Đầu/Giữa/Cuối không được tính theo FILE 3 giờ phần đầu (khi chưa biết video dài bao nhiêu);
* bản đệm phần đầu của một video ngắn (đã đọc trọn) không bị xoá + tải lại ở MỌI lượt quét;
* nhưng lượt KHÔNG có bằng chứng với file ngắn hơn giới hạn (có thể là bản cụt) thì bỏ bản đệm:
  lượt sau tải lại, không bao giờ bị giam vào một bản cụt.
"""

from __future__ import annotations

import os

import bao_cao_v2
import dossier
from engine import GHVD_TU_DONG, Config, Engine, Match, ScanResult

BA_GIO = 3 * 3600
VID = "vidunknownx"            # 11 ký tự


def _eng(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    e.config = Config(tai_mot_phan=True, quet_tang_dan_tu_gio=10.0, quet_tang_dan_buoc_gio=3.0,
                      keep_downloads=True)
    e._gioi_han_video_dai = GHVD_TU_DONG
    return e


def _gia_lap(tmp_path, monkeypatch, *, dai_audio, starts=()):
    """YouTube trả duration 0 (vd. livestream vừa kết thúc / premiere). Tải giả mô phỏng bộ đệm
    của ``download_audio`` thật: file đã có → trả lại (KHÔNG tải mạng); chưa có → «tải mạng»."""
    e = _eng(tmp_path)
    monkeypatch.setattr(e, "require", lambda **k: None)
    monkeypatch.setattr(e, "youtube_info", lambda url: {
        "id": VID, "title": "Live vua ket thuc", "duration": 0,
        "channel": "", "channel_id": "", "channel_url": "", "upload_date": ""})
    tai_mang = []

    def tai(url, vid, progress=None, gioi_han_giay=None):
        ten = f"{vid}__p{int(gioi_han_giay)}" if gioi_han_giay else vid
        p = os.path.join(e.dl_dir, ten + ".webm")
        if os.path.exists(p):
            return p                              # trúng bộ đệm: không có lượt tải mạng
        tai_mang.append(gioi_han_giay)
        with open(p, "wb") as f:
            f.write(b"x")
        return p

    monkeypatch.setattr(e, "download_audio", tai)
    monkeypatch.setattr(e, "do_dai_audio_that", lambda p: float(dai_audio))
    monkeypatch.setattr(e, "duration_of", lambda p: float(dai_audio))

    def quet(path, **k):
        # Như scan_media thật: duration_s = độ dài FILE, nhãn vùng theo FILE (_gan_chi_so).
        r = ScanResult(source_name="Live vua ket thuc", duration_s=float(dai_audio),
                       pham_vi_quet_s=float(dai_audio), vung_da_khop=[(0.0, float(dai_audio))])
        r.matches = [Match(clip="clipA [aaaaaaaaaaa].opus", start_s=float(s), end_s=float(s) + 120,
                           matched_s=110.0, clip_offset_s=0.0, hashes=9000, confidence="chac",
                           vung=Engine._nhan_vung(float(s), float(dai_audio)))
                     for s in starts]
        return r

    monkeypatch.setattr(e, "scan_media", quet)
    return e, tai_mang


def test_thoi_luong_chua_ro_khong_thanh_00_00_00_va_khong_dan_nhan_theo_file(tmp_path, monkeypatch):
    # Phần đầu 3 giờ tải đủ; bằng chứng ở 2 giờ 40 phút (9600 s).
    e, tai_mang = _gia_lap(tmp_path, monkeypatch, dai_audio=float(BA_GIO), starts=[9600])
    kq = e.scan_youtube(f"https://youtu.be/{VID}", luu_lich_su=False)

    assert tai_mang == [BA_GIO]
    assert kq.status == "ok" and kq.ly_do_pham_vi == "thoi_luong_chua_ro"
    loi = []
    # 1) Nhãn vùng: thời lượng video thật CHƯA RÕ -> không được tính «Cuối» theo file 3 giờ.
    if kq.matches[0].vung != "":
        loi.append(f"Match.vung={kq.matches[0].vung!r} (tinh theo FILE 3h, video that chua ro)")
    bc = kq.bao_cao
    assert bc is not None and not bao_cao_v2.la_loi_bao_cao(bc)
    if bc.doan and bc.doan[0].vung != "":
        loi.append(f"bao_cao.doan[0].vung={bc.doan[0].vung!r}")
    # 2) Sheets cột 7 «Thời lượng video vi phạm»: không khẳng định video dài 00:00:00.
    o7 = bao_cao_v2.dong_ngang(bc)[6]
    if o7 == "00:00:00":
        loi.append(f"dong_ngang[6]={o7!r} (video bi ghi la dai 0 giay)")
    # 3) Hồ sơ khiếu nại: không ghi «Thời lượng: 00:00:00» / «Tỷ lệ video bị chiếm: 0.0%».
    hs = dossier.dung_ho_so_v2(bc)
    if hs.thoi_luong_hhmmss == "00:00:00":
        loi.append(f"ho_so.thoi_luong_hhmmss={hs.thoi_luong_hhmmss!r}, ty_le_video={hs.ty_le_video}")
    assert not loi, "A-5: " + " | ".join(loi)


def test_video_ngan_thoi_luong_chua_ro_khong_tai_lai_moi_luot(tmp_path, monkeypatch):
    """Video thật 20 phút, YouTube không cho thời lượng: bản đệm phần đầu (đọc trọn 1200 s âm thanh)
    phải được dùng lại ở lượt sau, không bị xoá rồi tải mạng lại ở MỌI lượt quét."""
    e, tai_mang = _gia_lap(tmp_path, monkeypatch, dai_audio=1200.0, starts=[300])
    kq1 = e.scan_youtube(f"https://youtu.be/{VID}", luu_lich_su=False)
    assert kq1.status == "ok" and tai_mang == [BA_GIO]
    assert os.path.exists(os.path.join(e.dl_dir, f"{VID}__p{BA_GIO}.webm")), "keep_downloads: giữ đệm"
    kq2 = e.scan_youtube(f"https://youtu.be/{VID}", luu_lich_su=False)
    assert kq2.status == "ok"
    assert tai_mang == [BA_GIO], (
        f"A-5: lượt 2 xoá bản đệm 1200 s rồi tải mạng lại (số lượt tải mạng = {len(tai_mang)}; "
        "đúng = 1)")


def test_khong_bang_chung_file_ngan_hon_gioi_han_thi_bo_dem_de_tai_lai(tmp_path, monkeypatch):
    """Không thấy gì + file ngắn hơn giới hạn (video ngắn HAY bản cụt — không phân biệt được):
    kết quả là LỖI (không bao giờ âm tính) và bản đệm bị bỏ để lượt sau tải lại."""
    e, tai_mang = _gia_lap(tmp_path, monkeypatch, dai_audio=1200.0, starts=())
    kq = e.scan_youtube(f"https://youtu.be/{VID}", luu_lich_su=False)
    assert kq.status == "error" and kq.ly_do_pham_vi == "thoi_luong_chua_ro"
    assert not os.path.exists(os.path.join(e.dl_dir, f"{VID}__p{BA_GIO}.webm"))
    e.scan_youtube(f"https://youtu.be/{VID}", luu_lich_su=False)
    assert tai_mang == [BA_GIO, BA_GIO]


def test_ho_so_markdown_thoi_luong_chua_ro_khong_ghi_0_phan_tram(tmp_path, monkeypatch):
    e, _ = _gia_lap(tmp_path, monkeypatch, dai_audio=float(BA_GIO), starts=[9600])
    kq = e.scan_youtube(f"https://youtu.be/{VID}", luu_lich_su=False)
    md = dossier.render_markdown(dossier.dung_ho_so_v2(kq.bao_cao))
    assert "- **Thời lượng:** —" in md
    assert "- **Tỷ lệ video bị chiếm:** —" in md
    # Đường cũ (không ảnh chụp V2) cùng quy tắc.
    assert dossier.dung_ho_so(kq).thoi_luong_hhmmss == ""
