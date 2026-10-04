# -*- coding: utf-8 -*-
"""Clip MỚI tải vào kho sau bản này lưu thêm ``upload_date_raw`` (ngày NGUYÊN BẢN của yt-dlp)
cạnh các trường cũ — báo cáo V2 khỏi phải hỏi lại YouTube. Trường cũ, tên file, mã lưu trữ và
khoá vân tay KHÔNG đổi; entry cũ trong ``clips_meta.json`` không bị viết lại.
"""
from __future__ import annotations

import channel
from channel import ChannelSync, VideoInfo, bo_sung_video_info
from clip_metadata import ClipMetadataResolver

# 2024-01-15 20:00:00 UTC = 2024-01-16 03:00 giờ Việt Nam: ngày quy đổi KHÁC ngày nguyên bản.
INFO_TRE = {"id": "aaaaaaaaaaa", "title": "Tên chính thức", "upload_date": "20240115",
            "timestamp": 1705348800, "duration": 612.0}


def test_bo_sung_video_info_giu_ngay_nguyen_ban_rieng():
    v = bo_sung_video_info(VideoInfo("aaaaaaaaaaa", "flat", "", 0.0, "u"), INFO_TRE)
    assert v.upload_date == "20240116"            # trường cũ: ngày quy đổi như trước
    assert v.upload_date_raw == "20240115"         # trường mới: nguyên bản


def test_bo_sung_video_info_khong_doan_ngay_nguyen_ban():
    v = bo_sung_video_info(VideoInfo("aaaaaaaaaaa", "flat", "", 0.0, "u"),
                           {"timestamp": 1705348800})
    assert v.upload_date == "20240116" and v.upload_date_raw == ""
    v2 = bo_sung_video_info(VideoInfo("aaaaaaaaaaa", "flat", "", 0.0, "u"),
                            {"upload_date": "20241332"})
    assert v2.upload_date_raw == ""


def _sync_mot_video(tmp_path, monkeypatch, info):
    cs = ChannelSync(str(tmp_path))
    videos = [VideoInfo("aaaaaaaaaaa", "Tên từ flat", "", 0.0, "https://youtu.be/aaaaaaaaaaa")]
    monkeypatch.setattr(ChannelSync, "list_channel",
                        staticmethod(lambda url, limit=None, **kw: videos))
    monkeypatch.setattr(cs, "done_ids", lambda: set())
    monkeypatch.setattr(cs, "quet_id_tren_dia", lambda: {})
    monkeypatch.setattr(cs, "_mark_done", lambda vid: None)

    def tai_va_nen(v):
        v = channel.bo_sung_video_info(v, info)
        duong_dan = tmp_path / cs._ten_file(v)
        duong_dan.write_bytes(b"opus")
        return str(duong_dan), v

    monkeypatch.setattr(cs, "_tai_va_nen", tai_va_nen)
    assert cs.sync("https://youtube.com/@kenh")["moi"] == 1
    return cs


def test_sync_luu_upload_date_raw_canh_truong_cu(tmp_path, monkeypatch):
    cs = _sync_mot_video(tmp_path, monkeypatch, INFO_TRE)
    ten_file = "20240116 - Tên chính thức [aaaaaaaaaaa].opus"   # tên file theo luật cũ
    muc = cs.load_meta()[ten_file]
    assert (muc["upload_date"], muc["publication_date"], muc["publication_date_source"]) == (
        "20240116", "20240116", "timestamp")
    assert muc["upload_date_raw"] == "20240115"
    assert muc["url"] == "https://youtu.be/aaaaaaaaaaa"            # trường cũ không đổi
    meta = ClipMetadataResolver.from_mapping(cs.load_meta()).resolve(ten_file)
    assert (meta.ngay_raw, meta.nguon_ngay_raw) == ("20240115", "clips_meta.upload_date_raw")
    assert meta.upload_date == "20240116"                           # luật cũ y nguyên


def test_sync_khong_co_ngay_nguyen_ban_thi_khong_ghi_khoa(tmp_path, monkeypatch):
    cs = _sync_mot_video(tmp_path, monkeypatch, {"timestamp": 1705348800, "title": "T"})
    muc = next(iter(cs.load_meta().values()))
    assert "upload_date_raw" not in muc
