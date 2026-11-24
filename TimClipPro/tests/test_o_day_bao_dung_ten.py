# -*- coding: utf-8 -*-
"""Ổ đầy / không ghi được file: lỗi của MÁY, báo đúng tên (đề tài DT-02/DT-14; đề xuất antoan-05, youtube-06).

Trước bản sửa: «[Errno 28] No space left on device» (và «unable to open for writing … Permission denied» ở thư mục tải)
bị xếp UNKNOWN_YOUTUBE_ERROR → tool đổi lần lượt các player client (tải lại từ đầu mỗi lần), rồi sau 5 lần cầu dao dừng lô
với câu «YouTube trả lỗi chưa phân loại được» — người dùng tưởng YouTube chặn, trong khi chỉ cần dọn ổ.

Sau: loại lỗi riêng (DISK_FULL / WRITE_DENIED) → không đổi client, không vào cầu dao YouTube, không gửi thêm request nào
trong lượt, việc dừng ngay với câu nêu thư mục đang ghi.

Synthetic: chuỗi lỗi theo khuôn yt-dlp 2026.08.19 (downloader/http.py), yt-dlp giả (tests/ytdlp_gia.py), Engine trên thư
mục tạm. Không mạng, không ghi đầy ổ thật.
"""

from __future__ import annotations

import shutil

import pytest
import yt_dlp

import channel
import truy_cap_youtube as t
import ytdlp_chung as y
from channel import ChannelSync
from ytdlp_gia import YdlKichBan

DAY = "ERROR: unable to write data: [Errno 28] No space left on device"


@pytest.mark.parametrize("loi, loai", [
    (OSError(28, "No space left on device"), t.DISK_FULL),
    (RuntimeError("Không tải được audio. Đã thử: tv. Lỗi cuối: " + DAY), t.DISK_FULL),
    (OSError(28, "Ổ chỉ còn 1.0 GB trống"), t.DISK_FULL),                       # câu không tiếng Anh: nhận theo mã
    (RuntimeError("ERROR: unable to write data: [WinError 112] Không đủ dung lượng trên đĩa"), t.DISK_FULL),
    (RuntimeError("Nén audio thất bại: av_interleaved_write_frame(): No space left on device"), t.DISK_FULL),
    (RuntimeError("ERROR: unable to open for writing: [Errno 13] Permission denied: 'D:\\dl\\x.m4a.part'"),
     t.WRITE_DENIED),
    (RuntimeError("ERROR: unable to write data: [Errno 5] Input/output error"), t.WRITE_DENIED),
    (RuntimeError("ERROR: Unable to create directory: [WinError 5] Access is denied: 'E:\\Kho'"), t.WRITE_DENIED),
])
def test_loi_ghi_cua_may_co_loai_rieng_khong_phai_youtube(loi, loai):
    f = t.phan_loai_loi(loi, thao_tac="download")
    assert f.category == loai and loai in t.LOAI_MAY
    assert not f.retryable and not f.la_loi_truy_cap and not f.auth_related
    assert f.human_message_vi == t.THONG_BAO[loai] and "không phải YouTube chặn" in f.human_message_vi


def test_permission_denied_tran_khong_bi_doc_thanh_thu_muc_khong_ghi_duoc():
    """Chép cơ sở dữ liệu cookie của Chrome đang mở: yt-dlp (cookies.py) ném «Could not copy Chrome cookie database»
    bên trong ``except PermissionError`` — không phải thư mục tải không ghi được."""
    try:
        try:
            raise PermissionError(13, "Permission denied", r"C:\Users\x\AppData\Local\Google\Chrome\Network\Cookies")
        except PermissionError:
            raise RuntimeError("ERROR: Could not copy Chrome cookie database. See  https://github.com/yt-dlp/yt-dlp/"
                               "issues/7271  for more info")
    except RuntimeError as e:
        assert t.phan_loai_loi(e).category not in t.LOAI_MAY


def test_loi_ghi_khong_doi_player_client():
    phien = t.PhienYouTube()
    thu = []

    def chay(rieng):
        thu.append(rieng)
        raise RuntimeError(DAY)

    with pytest.raises(RuntimeError):
        y.thu_tung_client(["tv", "web_safari", "android"], chay, {}, dung_ngay=phien.nen_dung_doi_client)
    assert len(thu) == 1, "đổi client không cứu được ổ đầy — mỗi lần đổi là tải lại từ đầu"


def test_loi_ghi_khong_vao_cau_dao_youtube_va_khong_gui_them_request():
    phien = t.PhienYouTube()
    goi = []

    def tai():
        goi.append(1)
        raise RuntimeError(DAY)

    for _ in range(t.NGUONG_MO[t.UNKNOWN_YOUTUBE_ERROR] + 1):
        with pytest.raises(t.LoiTruyCapYouTube) as ei:
            phien.chay("download", tai, video_id="aaaaaaaaaaa")
        assert ei.value.that_bai.category == t.DISK_FULL
    so = phien.tom_tat()
    assert goi == [1], "sau lỗi ghi của máy, video nào cũng hỏng y hệt — không gửi thêm request nào"
    assert not phien.mo and not so["breaker_open"] and so["breaker_events"] == []
    assert so["other_failures"] == 0 and so["skipped_by_breaker"] == 0
    assert phien.thong_bao_dung() == "", "không được thành câu «Đã dừng yêu cầu mới tới YouTube…»"


def test_ghi_loi_o_tang_dieu_phoi_cung_khong_vao_cau_dao():
    """Đồng bộ kênh / Watch ghi lỗi qua ``ghi_loi`` — vd. FFmpeg nén hỏng vì ổ kho đầy (câu do tool viết)."""
    phien = t.PhienYouTube()
    f = phien.ghi_loi(RuntimeError("Nén audio thất bại: av_interleaved_write_frame(): No space left on device"),
                      "download", "aaaaaaaaaaa")
    assert f.category == t.DISK_FULL and not phien.mo
    with pytest.raises(t.LoiTruyCapYouTube) as ei:
        phien.chay("metadata", lambda: pytest.fail("không được gửi request"), video_id="bbbbbbbbbbb")
    assert ei.value.that_bai.category == t.DISK_FULL


def test_lo_quet_dung_ngay_khi_o_day_cau_neu_thu_muc(engine, monkeypatch):
    bat_dau = []

    def info(url):
        bat_dau.append(url)
        return {"id": url[-11:], "title": "Video thử", "duration": 600, "channel": "Kênh", "channel_id": "UCx",
                "channel_url": "", "upload_date": "20260101"}

    def tai(url, video_id, progress=None, gioi_han_giay=None):
        raise RuntimeError("Không tải được audio. Đã thử: tv. Lỗi cuối: " + DAY)

    monkeypatch.setattr(engine, "require", lambda **k: None)
    monkeypatch.setattr(engine, "youtube_info", info)
    monkeypatch.setattr(engine, "download_audio", tai)
    with pytest.raises(t.LoiTruyCapYouTube) as ei:
        list(engine.scan_iter(["https://youtu.be/aaaaaaaaaaa", "https://youtu.be/bbbbbbbbbbb"], "youtube"))
    assert ei.value.that_bai.category == t.DISK_FULL
    assert engine.dl_dir in str(ei.value) and "dọn bớt" in str(ei.value)
    assert len(bat_dau) == 1, "video thứ hai không được bắt đầu"


def test_kiem_cho_trong_truoc_khi_tai_audio_cua_luot_quet(engine, monkeypatch):
    that = shutil.disk_usage
    monkeypatch.setattr(shutil, "disk_usage", lambda p: that(p)._replace(free=1024 ** 3))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda *a, **k: pytest.fail("ổ gần đầy: không được bắt đầu tải"))
    with pytest.raises(OSError) as ei:
        engine.download_audio("https://youtu.be/aaaaaaaaaaa", "aaaaaaaaaaa")
    assert t.phan_loai_loi(ei.value).category == t.DISK_FULL and "1.0 GB" in str(ei.value)


def test_dong_bo_kenh_dung_ngay_khi_o_kho_day(tmp_path, monkeypatch):
    monkeypatch.setattr(channel, "do_dai_media", lambda p: 600.0)
    monkeypatch.setattr(channel, "do_dai_luong_tieng", lambda p: 600.0)
    ids = [f"j{i:010d}" for i in range(6)]
    ydl = YdlKichBan(tai={"*": DAY}, liet_ke=lambda _p, _u: {"_type": "playlist", "id": "UCkenh", "entries": [
        {"id": m, "title": f"Video {m}", "url": f"https://www.youtube.com/watch?v={m}", "duration": 600.0}
        for m in ids]})
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    kho = tmp_path / "Kho"
    cs = ChannelSync(str(kho))
    with pytest.raises(t.LoiTruyCapYouTube) as ei:
        cs.sync("https://www.youtube.com/@KenhThu")
    assert ei.value.that_bai.category == t.DISK_FULL
    assert str(kho) in str(ei.value) and "dọn bớt" in str(ei.value)
    assert ydl.dem("tai") == 1, "không đổi player client, không sang video kế"
    assert not cs.phien.mo and cs.phien.tom_tat()["other_failures"] == 0
