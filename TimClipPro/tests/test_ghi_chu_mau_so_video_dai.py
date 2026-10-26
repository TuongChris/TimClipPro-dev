# -*- coding: utf-8 -*-
"""Ghi chú phạm vi của video dài tải MỘT PHẦN phải dùng thời lượng VIDEO làm mẫu số (audit A-12).

Video 66 giờ chỉ tải 3 giờ đầu (``_gioi_han_tai``); lượt ``scan_media`` lồng chỉ thấy file 3 giờ
nên từng ghi «Đã dừng sớm sau khi so khớp 01:00:00/03:00:00», rồi nơi gọi sửa ``duration_s``
thành 66 giờ và nối thêm câu «…/66:00:00» — ghi chú cuối (hộp «Chưa quét trọn», ``ghi_chu`` V2,
lịch sử) mang hai mẫu số mâu thuẫn. CLAUDE.md «Lỗi đã gặp» 13/16: đổi ``duration_s`` từ độ dài
file sang độ dài VIDEO thì mọi thứ suy từ nó phải tính lại.

Dữ liệu synthetic, không mạng, không FFmpeg: thông tin video, tải, cắt khúc và so khớp đều giả.
"""
from __future__ import annotations

import os

from engine import RE_TEN_KHUC, Engine

DAI_VIDEO = 66 * 3600.0
DAI_FILE = 3 * 3600.0


def _engine_video_66_gio(tmp_path):
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"),
               out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    cfg = e.config
    cfg.chunk_s = 3600
    cfg.quet_da_toc_do = False
    cfg.top_n = 1
    assert cfg.quet_tang_dan and cfg.tai_mot_phan       # mặc định sản phẩm
    e._overlap_thuc_te = lambda *a, **k: 0
    e.db_clips = lambda **k: [{"ten": "goc.opus", "duong_dan": "goc.opus", "so_hash": 20000}]
    e.youtube_info = lambda url: {"title": "Video 66 giờ", "id": "abcdefghijk", "channel": "",
                                  "channel_id": "", "channel_url": "", "upload_date": "",
                                  "duration": DAI_VIDEO}
    tep = tmp_path / "abcdefghijk__p10800.opus"
    tep.write_bytes(b"x")
    da_tai = []

    def tai(url, vid, progress=None, gioi_han_giay=None):
        da_tai.append(gioi_han_giay)
        return str(tep)

    e.download_audio = tai
    e.duration_of = lambda p: DAI_FILE
    e.do_dai_am_thanh = lambda p: DAI_FILE
    e._cut_chunks = lambda *a, **k: (
        [str(tmp_path / f"chunk_{n:07d}.wav") for n in (0, 3600, 7200)], DAI_FILE)
    return e, da_tai


def _khop_manh():
    return [{"clip": "goc.opus", "bat_dau": 10.0, "khop": 200.0, "t_clip": 0.0,
             "hash": 9000, "align": 10.0}]


def test_dung_som_ghi_mau_so_thoi_luong_video(tmp_path):
    e, da_tai = _engine_video_66_gio(tmp_path)
    e.config.top1_tim_nhanh = True
    e.config.top1_khuc_toi_thieu = 3
    da_hoi = []

    def khop(chunks, *a, **k):
        da_hoi.extend(chunks)
        return _khop_manh()

    e._match_chunks = khop

    kq = e.scan_youtube("https://youtu.be/abcdefghijk", luu_lich_su=False)

    assert da_tai == [DAI_FILE], f"điều kiện test: chỉ tải 3 giờ đầu ({da_tai})"
    assert len(da_hoi) == 1, "điều kiện test: Top-1 dừng sau khúc đầu"
    assert kq.status == "ok" and len(kq.matches) == 1 and kq.duration_s == DAI_VIDEO
    assert "Đã dừng sớm sau khi so khớp 01:00:00/66:00:00" in kq.note, kq.note
    assert "/03:00:00" not in kq.note, kq.note


def test_vung_loi_ghi_mau_so_thoi_luong_video(tmp_path, monkeypatch):
    """Câu «Chưa quét trọn video: lỗi xử lý …; đã so khớp X/Y» cũng theo thời lượng VIDEO."""
    e, da_tai = _engine_video_66_gio(tmp_path)
    e.config.top1_tim_nhanh = False
    # Top-1 tìm nhanh tắt: cả 3 khúc của file 3 giờ (một đoạn, dưới ngưỡng tăng dần) đều gửi đi.

    def khop(self, chunks, *a, **k):
        # audfprint không báo về khúc thứ hai → vùng 01:00:00–02:00:00 chưa kiểm.
        for c in chunks:
            ten = os.path.basename(c)
            if RE_TEN_KHUC.fullmatch(ten) and ten.startswith("chunk_0003600"):
                self._pham_vi.khong_phan_tich.add(ten)
        return _khop_manh()

    monkeypatch.setattr(Engine, "_match_chunks", khop)

    kq = e.scan_youtube("https://youtu.be/abcdefghijk", luu_lich_su=False)

    assert da_tai == [DAI_FILE], f"điều kiện test: chỉ tải 3 giờ đầu ({da_tai})"
    assert kq.status == "ok" and kq.duration_s == DAI_VIDEO
    assert kq.vung_loi == [(3600.0, 7200.0)], kq.vung_loi
    assert "Chưa quét trọn video: lỗi xử lý 1 vùng" in kq.note, kq.note
    assert "/66:00:00" in kq.note.splitlines()[0], kq.note
    assert "/03:00:00" not in kq.note, kq.note


def test_quet_file_trong_may_giu_mau_so_cua_file(tmp_path):
    """Không phải YouTube: mẫu số vẫn là độ dài file, kể cả khi lượt YouTube trước đã ghim số khác."""
    e, _ = _engine_video_66_gio(tmp_path)
    e.config.top1_tim_nhanh = True
    e.config.top1_khuc_toi_thieu = 3
    e._match_chunks = lambda chunks, *a, **k: _khop_manh()
    e._thoi_luong_video_nguon = DAI_VIDEO     # dư lại từ lượt YouTube trước trên cùng bản ghim
    tep = tmp_path / "video_trong_may.opus"
    tep.write_bytes(b"x")

    kq = e.scan_media(str(tep), luu_lich_su=False)

    assert kq.status == "ok" and kq.duration_s == DAI_FILE
    assert "Đã dừng sớm sau khi so khớp 01:00:00/03:00:00" in kq.note, kq.note
