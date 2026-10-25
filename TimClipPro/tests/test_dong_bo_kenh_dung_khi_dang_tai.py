# -*- coding: utf-8 -*-
"""Audit D-6 — bấm «Dừng lại» trong lúc ĐỒNG BỘ KÊNH đang TẢI một video phải dừng lượt tải đó.

Tình huống: client `android` (đường lui) tải video tiến trình trọn vẹn — video vài giờ là hàng GB. Người dùng bấm Dừng
giữa chừng. Đúng (giống `Engine.download_audio`, hook gọi `_check_cancel()`): lượt tải bị cắt ở nhịp tiến độ kế tiếp,
không tải nốt phần còn lại, không đổi sang client khác, không bước sang nén. Sai (khiếm khuyết): hook `hook_tai` chỉ đo,
cờ huỷ chỉ được xem giữa các video / lúc nghỉ thử lại → tải HẾT rồi mới ném `DaHuyDongBo` ở khâu nén.

Hoàn toàn tổng hợp: yt-dlp giả (không mạng), FFmpeg giả (không tiến trình), thư mục tạm.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yt_dlp

import channel
from channel import ChannelSync, VideoInfo
from engine import Cancelled, Engine
from process_runner import KetQuaLenh

VID = "abcdefghijk"
N_NHIP = 40                 # số nhịp tiến độ của một lượt tải «dài» (mỗi nhịp ~ một khúc vài chục MB ngoài đời)
DAI_S = 6 * 3600.0          # video 6 giờ


class _YdlTaiDai:
    """Giả `yt_dlp.YoutubeDL`: một lượt tải = N_NHIP lần gọi `progress_hooks` ("downloading"), rồi đổi .part → file thật.

    Như yt-dlp thật: ngoại lệ do progress hook ném ra đi thẳng ra khỏi `extract_info` / `download` (đó là cách
    `Engine.download_audio` huỷ được giữa chừng)."""

    def __init__(self, n_nhip: int, sau_nhip=None):
        self.n_nhip = n_nhip
        self.sau_nhip = sau_nhip     # gọi sau mỗi nhịp đã giao xong (mô phỏng người dùng bấm Dừng)
        self.so_nhip = 0             # nhịp "downloading" ĐÃ giao cho mọi hook mà không bị ngắt
        self.so_lan_tai = 0          # số lượt tải bắt đầu (kể cả đổi client)
        self.tai_xong = 0            # số lượt tải chạy tới tận cùng

    def __call__(self, opts):
        cha = self

        class _Phien:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def _tai(self, vid: str) -> dict:
                cha.so_lan_tai += 1
                dich = opts["outtmpl"].replace("%(id)s", vid).replace("%(ext)s", "mp4")
                os.makedirs(os.path.dirname(dich), exist_ok=True)
                part = dich + ".part"
                info_dict = {"id": vid, "ext": "mp4", "format_id": "18", "acodec": "mp4a.40.2",
                             "vcodec": "avc1", "abr": 96.0}
                tong = cha.n_nhip * 1024
                for i in range(cha.n_nhip):
                    with open(part, "ab") as f:
                        f.write(b"\0" * 1024)
                    d = {"status": "downloading", "downloaded_bytes": (i + 1) * 1024, "total_bytes": tong,
                         "speed": 1.0e6, "filename": part, "info_dict": info_dict}
                    for h in opts.get("progress_hooks") or []:
                        h(d)
                    cha.so_nhip += 1
                    if cha.sau_nhip:
                        cha.sau_nhip(cha.so_nhip)
                os.replace(part, dich)
                cha.tai_xong += 1
                for h in opts.get("progress_hooks") or []:
                    h({"status": "finished", "downloaded_bytes": tong, "total_bytes": tong,
                       "filename": dich, "info_dict": info_dict})
                return {"id": vid, "title": "Video dai", "upload_date": "20260101", "duration": DAI_S}

            def extract_info(self, url, download=False):
                assert download, "đồng bộ kênh tải bằng extract_info(download=True)"
                return self._tai(url.rsplit("/", 1)[-1])

            def download(self, urls):
                self._tai(urls[0].rsplit("/", 1)[-1])
                return 0

        return _Phien()


def test_dong_bo_kenh_bam_dung_khi_dang_tai_thi_cat_luot_tai_ngay(tmp_path, monkeypatch):
    """RED trên mã có khiếm khuyết: tải hết N_NHIP nhịp, rồi mới huỷ ở khâu nén."""
    bam_dung = {"co": False}

    def nguoi_dung_bam_dung(k):
        if k == 1:                   # ngay sau nhịp tiến độ đầu tiên: người dùng bấm «Dừng lại»
            bam_dung["co"] = True

    ydl = _YdlTaiDai(N_NHIP, sau_nhip=nguoi_dung_bam_dung)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)

    lenh_nen: list = []

    def ffmpeg_gia(lenh, cancel_event=None, **kw):
        # Như process_runner thật: cờ huỷ đã bật thì lệnh trả về cancelled ngay.
        lenh_nen.append(list(lenh))
        if cancel_event is not None and cancel_event.is_set():
            return KetQuaLenh(returncode=-1, stdout="", stderr="", cancelled=True)
        Path(lenh[-1]).write_bytes(b"")
        return KetQuaLenh(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(channel, "chay_lenh_media", ffmpeg_gia)

    cs = ChannelSync(str(tmp_path / "kho"))          # danh sách client MẶC ĐỊNH (có đường lui)
    cs.list_channel = lambda *a, **k: [VideoInfo(VID, "Video dai", "20260101", DAI_S, f"https://youtu.be/{VID}")]

    r = cs.sync("kenh", cancel_check=lambda: bam_dung["co"])

    # Bằng chứng chính của khiếm khuyết: sau khi bấm Dừng, lượt tải vẫn chạy hết.
    assert ydl.tai_xong == 0 and ydl.so_nhip < N_NHIP, (
        f"Đã bấm Dừng sau nhịp 1 nhưng yt-dlp vẫn tải {ydl.so_nhip}/{N_NHIP} nhịp "
        f"(tải xong {ydl.tai_xong} lần) — cờ huỷ không được kiểm trong lúc tải; "
        f"lệnh nén đã chạy={len(lenh_nen)}, da_huy={r['da_huy']}, moi={r['moi']}, loi={r['loi']}")
    assert ydl.so_lan_tai == 1, f"bấm Dừng thì không được đổi sang client khác (đã bắt đầu {ydl.so_lan_tai} lượt)"
    assert lenh_nen == [], "đã bấm Dừng trong lúc tải thì không được bước sang khâu nén"
    assert r["da_huy"] is True and r["moi"] == 0, r
    tam = Path(cs.tmp_dir)
    tho = [p.name for p in tam.rglob(f"{VID}.*") if not p.name.endswith((".part", ".ytdl"))] if tam.exists() else []
    assert tho == [], f"không được còn file tải TRỌN trong _tam sau khi bấm Dừng: {tho}"


def test_doi_chung_engine_download_audio_huy_o_nhip_tien_do_ke_tiep(tmp_path, monkeypatch):
    """Đối chứng (XANH): đường quét dùng hook gọi `_check_cancel()` — huỷ ngay ở nhịp kế tiếp."""
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "ra"))
    e.config.ytdlp_player_clients = [""]
    e.config.ytdlp_sleep_requests_s = 0.0
    e.config.ytdlp_cookies_browser = ""

    def nguoi_dung_bam_dung(k):
        if k == 1:
            e.cancel_event.set()

    ydl = _YdlTaiDai(N_NHIP, sau_nhip=nguoi_dung_bam_dung)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)

    with pytest.raises(Cancelled):
        e.download_audio(f"https://youtu.be/{VID}", VID)
    assert ydl.so_nhip == 1 and ydl.tai_xong == 0 and ydl.so_lan_tai == 1
