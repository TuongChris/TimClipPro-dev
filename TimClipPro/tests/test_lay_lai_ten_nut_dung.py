# -*- coding: utf-8 -*-
"""Audit D-9: «🌐 Lấy lại tên video thật» (ChannelSync.va_metadata, lay_title=True) phải DỪNG khi bấm Dừng.

Quy ước dự án: tác vụ dài nhận callback tiến độ VÀ kiểm cờ huỷ. Nút «⏹️ Dừng lại» của app chỉ gọi
``eng.cancel()`` (đặt ``eng.cancel_event``); đồng bộ kênh nhận cờ đó qua ``cancel_check=lambda:
eng.cancel_event.is_set()`` (app.py), nhưng đường vá tên/metadata kho thì không.

Test chạy ĐÚNG đường app: kho tạm 30 file ``20250101 - t [<id>].opus`` chưa có clips_meta.json,
``ChannelSync.va_metadata(progress=..., lay_title=True)``; yt-dlp là bản giả (``tests/ytdlp_gia.py``),
không mạng. Nếu hàm có tham số huỷ (``cancel_check`` như ``sync`` hoặc ``cancel_event``) thì test
nối nó vào cờ Dừng; không có thì cờ Dừng không có đường nào tới vòng lặp — đúng như app hôm nay.
"""

import inspect
import threading

import yt_dlp

import truy_cap_youtube as t
from channel import ChannelSync
from ytdlp_gia import TAM, YdlKichBan, info_mau

SO_CLIP = 30


def _kho(tmp_path):
    kho = tmp_path / "kho"
    kho.mkdir()
    for i in range(SO_CLIP):
        (kho / f"20250101 - t [vid{i:08d}].opus").write_bytes(b"opus gia")
    return kho


def _goi_nhu_app(cs, dung: threading.Event, **kw):
    """Như ``chay_nen("va_title", cs.va_metadata, lay_title=True)`` + nối cờ Dừng nếu hàm nhận."""
    tham_so = inspect.signature(cs.va_metadata).parameters
    if "cancel_check" in tham_so:
        kw["cancel_check"] = dung.is_set
    elif "cancel_event" in tham_so:
        kw["cancel_event"] = dung
    try:
        return cs.va_metadata(progress=lambda pct, msg: None, lay_title=True, **kw)
    except BaseException as e:  # noqa: BLE001 — cách dừng (ném lỗi huỷ / trả kết quả) do bản sửa chọn
        return e


def test_bam_dung_sau_video_dau_thi_khong_hoi_youtube_tiep(tmp_path, monkeypatch):
    kho = _kho(tmp_path)
    dung = threading.Event()          # = eng.cancel_event; nút Dừng gọi eng.cancel() -> set()
    so_lan = []

    def info(_phien, ma):
        so_lan.append(ma)
        dung.set()                    # người dùng bấm Dừng ngay sau request đầu tiên
        return info_mau(ma)

    ydl = YdlKichBan(info={"*": info})
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)

    _goi_nhu_app(ChannelSync(str(kho)), dung)

    assert ydl.dem("info") <= 2, (
        f"đã bấm Dừng sau request đầu, vẫn gửi {ydl.dem('info')}/{SO_CLIP} request metadata "
        "tới YouTube — va_metadata không kiểm cờ huỷ")


def test_dung_trong_luc_nghi_thu_lai_thi_thoat_ngay(tmp_path, monkeypatch):
    kho = _kho(tmp_path)
    dung = threading.Event()
    cho_da_nhan = []

    def cho(giay, cancel_event=None):
        # Thay cho_huy_duoc: ghi lại cờ huỷ mà bộ thử lại được trao; người dùng bấm Dừng
        # đúng lúc đang nghỉ 3 s (mạng chập chờn) / 30 s (HTTP 429).
        cho_da_nhan.append(cancel_event)
        dung.set()
        return t.cho_huy_duoc(0, cancel_event)

    lan_dau = []

    def info(_phien, ma):
        if not lan_dau:
            lan_dau.append(ma)
            raise RuntimeError(TAM.format(id=ma))   # lỗi mạng tạm thời -> nghỉ rồi thử lại
        return info_mau(ma)

    ydl = YdlKichBan(info={"*": info})
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    phien = t.PhienYouTube(ham_cho=cho)

    _goi_nhu_app(ChannelSync(str(kho), phien_youtube=phien), dung)

    assert cho_da_nhan, "kịch bản phải đi qua một lần nghỉ thử lại"
    assert cho_da_nhan[0] is not None, (
        "lần nghỉ thử lại của lay_info_video nhận cancel_event=None — bấm Dừng không cắt được "
        "lúc nghỉ 3 s/30 s")
    assert ydl.dem("info") <= 2, (
        f"bấm Dừng trong lúc nghỉ thử lại, vẫn gửi {ydl.dem('info')}/{SO_CLIP + 1} request")


def test_app_noi_co_dung_vao_nut_lay_lai_ten():
    """Đối chiếu: đồng bộ kênh truyền ``cancel_check=lambda: eng.cancel_event.is_set()``;
    nút «Lấy lại tên video thật» phải truyền cờ huỷ tương tự. (Tĩnh, chỉ đọc app.py.)"""
    import ast
    import os

    nguon = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"),
                 encoding="utf-8").read()
    goi = [n for n in ast.walk(ast.parse(nguon))
           if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "chay_nen"
           and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == "va_title"]
    assert len(goi) == 1
    tu = {k.arg for k in goi[0].keywords}
    assert tu & {"cancel_check", "cancel_event"}, (
        f"chay_nen('va_title', cs_title.va_metadata, ...) chỉ truyền {sorted(tu)} — không có cờ huỷ")
