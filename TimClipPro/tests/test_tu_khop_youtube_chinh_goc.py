# -*- coding: utf-8 -*-
"""Khoá hồi quy audit A-14 (P3): quét link YouTube của CHÍNH video gốc trong kho không được báo «tự vi phạm».

Kịch bản synthetic, không mạng: kho là kênh gốc (tên file chuẩn ``YYYYMMDD - Tiêu đề [ID].opus``);
người dùng quét link của CHÍNH video gốc ``dQw4w9WgXcQ``. Quét đi qua ``scan_youtube`` thật;
chỉ thay các điểm chạm bên ngoài (thông tin video, tải audio → ``<ID>.webm`` như
``download_audio``, FFmpeg, audfprint trả về mảnh khớp gần trọn của chính clip đó).

Hành vi ĐÚNG được khẳng định (HUONG_DAN.md «D. Chống tự khớp»: file đang quét nằm trong kho
«sẽ khớp 100% với chính nó» — hệ thống tự loại; engine.py «Chặn tự khớp … vô nghĩa»;
common_original.canh_bao_goc đã cảnh báo «Link video N có thể chính là video gốc» khi mã video
trùng): khi mã video đang quét TRÙNG mã ``[ID]`` của clip gốc khớp được, clip đó là TỰ KHỚP —
bị loại khỏi kết quả như tự khớp file trong máy, và ghi chú nói rõ mã video đó chính là video gốc.
Tự khớp không được chiếm suất Top-N của clip KHÁC có thật trong video; clip mang mã khác vẫn báo.
"""
import os
import sys
import wave
from types import SimpleNamespace

import engine as engine_module
from engine import Engine

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(engine_module.__file__)), "tests"))
from kho_gia import ghi_kho  # noqa: E402

SR = 11025
TONG = 300.0
VID = "dQw4w9WgXcQ"
TEN_GOC = f"20240101 - Clip goc [{VID}].opus"


def _ghi_wav(path, giay: float) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"\x00\x00" * int(giay * SR))


KHAC = "20230505 - Clip khac [aaaaaaaaaaa].opus"


def _eng(tmp_path) -> Engine:
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"),
               out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e.config.chunk_s = 100
    e.config.quet_da_toc_do = False
    e.config.top1_tim_nhanh = False
    e.config.top_n = 1
    e._overlap_thuc_te = lambda *a, **k: 0
    e.db_clips = lambda **k: [{"ten": TEN_GOC, "duong_dan": TEN_GOC, "so_hash": 20000},
                              {"ten": KHAC, "duong_dan": KHAC, "so_hash": 20000}]
    thu_muc = tmp_path / "kenh_goc"
    thu_muc.mkdir()
    e.add_kho("KenhGoc", str(thu_muc))
    ghi_kho(e.db_file, [(str(thu_muc / TEN_GOC), 9), (str(thu_muc / KHAC), 9)])
    e.use_kho("KenhGoc")
    return e


def _quet(tmp_path, monkeypatch, manh):
    e = _eng(tmp_path)
    dl = tmp_path / "dl"
    dl.mkdir()
    media = dl / f"{VID}.webm"          # download_audio đặt tên theo mã video
    media.write_bytes(b"x")
    e.youtube_info = lambda url: {
        "title": "Clip goc", "id": VID, "channel": "Kenh goc", "channel_id": "UCgoc",
        "channel_url": "", "upload_date": "20240101", "duration": TONG}
    e.download_audio = lambda url, video_id, progress=None, gioi_han_giay=None: str(media)
    e.duration_of = lambda p: TONG

    def ffmpeg(lenh, **kw):
        bat_dau = int(float(lenh[lenh.index("-ss") + 1]))
        _ghi_wav(lenh[-1], min(100.0, TONG - bat_dau))
        return SimpleNamespace(returncode=0, stdout="", stderr="", cancelled=False,
                               timed_out=False, ly_do="")

    monkeypatch.setattr(engine_module, "chay_lenh_media", ffmpeg)
    e._match_chunks = lambda chunks, *a, **k: list(manh)
    kq = e.scan_youtube(f"https://www.youtube.com/watch?v={VID}")
    assert kq.status == "ok" and kq.source_id == VID
    return kq


def _manh(clip, bat_dau, khop, so_hash):
    return {"clip": clip, "bat_dau": bat_dau, "khop": khop, "t_clip": 0.0,
            "hash": so_hash, "he_so": 1.0, "align": bat_dau}


def test_quet_chinh_video_goc_khong_bao_tu_vi_pham(tmp_path, monkeypatch):
    kq = _quet(tmp_path, monkeypatch, [_manh(TEN_GOC, 0.0, 295.0, 19000)])
    tu_khop = [m for m in kq.matches if m.clip == TEN_GOC]
    assert not tu_khop, (
        f"video {VID} được báo là chứa CHÍNH clip gốc của nó ({len(tu_khop)} dòng, "
        f"{tu_khop[0].hashes if tu_khop else 0} hash); note={kq.note!r}")
    assert kq.so_dat_nguong == 0 and not kq.ung_vien_dat
    assert VID in (kq.note or "") and TEN_GOC in (kq.note or "")


def test_tu_khop_theo_ma_khong_chiem_suat_clip_khac(tmp_path, monkeypatch):
    # top_n = 1: tự khớp (gần trọn video) không được chiếm suất duy nhất của clip KHÁC.
    kq = _quet(tmp_path, monkeypatch, [_manh(TEN_GOC, 0.0, 295.0, 19000),
                                       _manh(KHAC, 120.0, 60.0, 4000)])
    assert [m.clip for m in kq.matches] == [KHAC]
    assert [m.clip for m in kq.ung_vien_dat] == [KHAC]


def test_clip_ma_khac_van_bao(tmp_path, monkeypatch):
    kq = _quet(tmp_path, monkeypatch, [_manh(KHAC, 120.0, 60.0, 4000)])
    assert [m.clip for m in kq.matches] == [KHAC]
    assert VID not in (kq.note or "")
