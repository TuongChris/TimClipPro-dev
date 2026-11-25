"""Canh khi nâng yt-dlp (DT-04): hai file lock ghim cùng bản, client mặc định còn trong yt-dlp đang cài,
health_check báo cả yt-dlp-ejs."""
import pathlib
import re

import health_check
import ytdlp_chung

GOC = pathlib.Path(__file__).resolve().parents[2]


def _ghim(duong_dan: pathlib.Path) -> dict:
    return dict(re.findall(r"^([A-Za-z0-9_.\-]+)==([^\s\\]+)", duong_dan.read_text(encoding="utf-8"), re.M))


def test_hai_file_lock_ghim_cung_phien_ban():
    co_bam = _ghim(GOC / "release" / "locks" / "requirements-lock.txt")
    khong_bam = _ghim(GOC / "TimClipPro" / "requirements-lock.txt")
    assert len(co_bam) > 50
    assert co_bam == khong_bam


def test_client_mac_dinh_con_trong_yt_dlp():
    from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS

    thieu = [c for c in ytdlp_chung.PLAYER_CLIENTS_MAC_DINH if c and c not in INNERTUBE_CLIENTS]
    assert thieu == []


def test_health_check_bao_ban_yt_dlp_ejs():
    kq = health_check._phien_ban_thu_vien()
    assert kq.get("yt-dlp-ejs")
