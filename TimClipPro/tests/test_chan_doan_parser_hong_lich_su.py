# -*- coding: utf-8 -*-
"""Parser audfprint hỏng (PARSER_HONG) không được thành «âm tính đầy đủ» (audit A-3).

Kịch bản synthetic, không mạng: audfprint (giả) thoát rc 0 và ghi một dòng ``Matched …``
cho MỖI khúc, nhưng định dạng đã trôi (thiếu ``of N``) nên ``RE_MATCH`` không đọc được
dòng nào. Tên khúc vẫn đọc được nên độ phủ = cả video.

Hành vi ĐÚNG (chan_doan_quet.MO_TA_GIAI_DOAN[PARSER_HONG] tự gọi đây là «lỗi code, phải
sửa»; ids_da_quet chỉ được chốt âm tính đã kiểm TRỌN; common_original chỉ loại một video
gốc bằng bằng chứng âm ĐẦY ĐỦ):

* lượt quét không được lưu là ``ok`` + ``day_du=1`` với ghi chú rỗng;
* video KHÔNG được nằm trong ``ids_da_quet()`` (Watch phải quét lại sau khi sửa parser);
* ghi chú phải nói về lỗi đọc output;
* ở chế độ nguồn chung (collect), lượt đó KHÔNG được tính là lượt TRỌN → không ra
  «Không có (đã quét trọn)»;
* file chẩn đoán JSON (data/chan_doan/) vẫn được ghi để soi bệnh.
Đối chứng: cùng bộ giả nhưng dòng có «of N» thì hành vi y như cũ (ok, quét trọn).
"""

import glob
import json
import os
import sqlite3
import wave
from types import SimpleNamespace

import engine as engine_module
from chan_doan_quet import MO_TA_GIAI_DOAN, PARSER_HONG
from engine import Engine, ScanObjective
from kho_gia import ghi_kho

SR = 11025
TONG = 300.0


def _ghi_wav(path, giay: float) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"\x00\x00" * int(giay * SR))


def _eng(tmp_path) -> Engine:
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"),
               out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e.config.chunk_s = 100
    e.config.quet_da_toc_do = False
    e.config.top1_tim_nhanh = False
    e.config.top_n = 1
    e._overlap_thuc_te = lambda *a, **k: 0
    e.db_clips = lambda **k: [{"ten": "goc.opus", "duong_dan": "goc.opus",
                               "so_hash": 20000}]
    thu_muc = tmp_path / "nguon_A"
    thu_muc.mkdir(exist_ok=True)
    e.add_kho("A", str(thu_muc))
    ghi_kho(e.db_file, [(str(thu_muc / "goc.opus"), 9)])
    e.use_kho("A")
    return e


def _ffmpeg(lenh, **kw):
    bat_dau = int(float(lenh[lenh.index("-ss") + 1]))
    _ghi_wav(lenh[-1], min(100.0, TONG - bat_dau))
    return SimpleNamespace(returncode=0, stdout="", stderr="", cancelled=False,
                           timed_out=False, ly_do="")


def _audfprint_gia(co_of_n: bool):
    """Giả ``_run_stream`` của audfprint match: rc 0, một dòng Matched mỗi khúc."""
    def run_stream(lenh, on_line=None, **kw):
        ds = [x for x in open(lenh[lenh.index("--list") + 1],
                              encoding="utf-8").read().split("\n") if x]
        op = lenh[lenh.index("--opfile") + 1]
        duoi = " of 20000" if co_of_n else ""   # định dạng trôi: mất token «of N»
        with open(op, "w", encoding="utf-8") as f:
            for khuc in ds:
                f.write(f"Matched   60.0 s starting at   40.0 s in {khuc} to time"
                        f"    0.0 s in goc.opus with  9000{duoi} common hashes at rank  0\n")
        return 0, []
    return run_stream


def _chuan_bi(e, tmp_path, monkeypatch, vid, co_of_n=False):
    media = tmp_path / f"{vid}.wav"
    media.write_bytes(b"x")
    e.youtube_info = lambda url: {
        "title": f"Video {vid}", "id": vid, "channel": "", "channel_id": "",
        "channel_url": "", "upload_date": "", "duration": TONG}
    e.download_audio = lambda url, video_id, progress=None, gioi_han_giay=None: str(media)
    e.duration_of = lambda p: TONG
    monkeypatch.setattr(engine_module, "chay_lenh_media", _ffmpeg)
    e._run_stream = _audfprint_gia(co_of_n)
    return media


def _hang(e, vid) -> dict:
    con = sqlite3.connect(e.sqlite_file)
    con.row_factory = sqlite3.Row
    try:
        return dict(con.execute("SELECT * FROM jobs WHERE source_id=? ORDER BY id DESC",
                                (vid,)).fetchone())
    finally:
        con.close()


def test_doi_chung_dinh_dang_dung_thi_parser_doc_duoc(tmp_path, monkeypatch):
    """Đối chứng: cùng bộ giả, CÓ «of N» thì parser đọc được — bộ giả hợp lệ."""
    e = _eng(tmp_path)
    _chuan_bi(e, tmp_path, monkeypatch, "doichung000", co_of_n=True)
    kq = e.scan_youtube("https://youtu.be/doichung000")
    assert kq.chan_doan.parse_duoc == 3
    assert kq.chan_doan.giai_doan_mat != PARSER_HONG
    assert kq.status == "ok" and kq.quet_day_du


def test_parser_hong_khong_duoc_chot_am_tinh_day_du(tmp_path, monkeypatch):
    e = _eng(tmp_path)
    vid = "parserHong1"
    _chuan_bi(e, tmp_path, monkeypatch, vid)

    kq = e.scan_youtube(f"https://youtu.be/{vid}")

    # Tiền đề: đúng ca PARSER_HONG (3 dòng Matched, 0 đọc được), không phải lỗi dựng test.
    cd = kq.chan_doan
    assert cd.dong_co_matched == 3 and cd.parse_duoc == 0, cd
    assert cd.giai_doan_mat == PARSER_HONG
    assert not kq.matches

    hang = _hang(e, vid)
    print("KQ:", kq.status, "quet_day_du=", kq.quet_day_du, "note=", repr(kq.note))
    print("HANG:", {k: hang[k] for k in ("status", "n_matches", "day_du", "note")})
    print("ids_da_quet:", e.ids_da_quet())

    assert vid not in e.ids_da_quet(), (
        "parser hỏng (lỗi code) bị chốt là âm tính đã kiểm trọn — Watch bỏ qua video "
        "này mãi mãi, kể cả sau khi sửa parser")
    assert not (hang["status"] == "ok" and hang["day_du"] == 1), hang
    assert kq.status == "error", "PARSER_HONG phải là lỗi, không phải 'ok' 0 kết quả"
    ghi_chu = (kq.note or "").lower()
    assert any(t in ghi_chu for t in ("định dạng", "parser", "đọc ra", "không đọc")), \
        f"ghi chú phải nói về lỗi đọc output audfprint, đang là {kq.note!r}"
    assert MO_TA_GIAI_DOAN[PARSER_HONG] in kq.note
    assert "chưa thể kết luận video này không chứa clip gốc" in ghi_chu
    assert hang["status"] != "ok" and hang["day_du"] == 0 and hang["n_matches"] == 0, hang
    # Bản ghi chẩn đoán vẫn phải có để soi bệnh (trước đây chỉ ghi khi status "ok").
    ban_ghi = [json.load(open(p, encoding="utf-8"))
               for p in glob.glob(os.path.join(e.data_dir, "chan_doan", "*.json"))]
    assert any(b["phieu_phat_hien"].get("giai_doan_mat") == PARSER_HONG for b in ban_ghi), \
        ban_ghi


def test_parser_hong_o_che_do_collect_khong_thanh_vang_mat_du(tmp_path, monkeypatch):
    import common_original as co

    e = _eng(tmp_path)
    media = _chuan_bi(e, tmp_path, monkeypatch, "collect0001")
    kq = e.scan_media(str(media), luu_lich_su=False, muc_tieu=ScanObjective("collect"))
    assert kq.chan_doan.giai_doan_mat == PARSER_HONG

    dd = (kq.kho_id, kq.kho_phien_ban, kq.chinh_sach)
    lq = co.luot_tu_ket_qua(kq, "collect", dd)
    v = co.VideoTrongLo(thu_tu=1, nguon="v1", luot=[lq])
    trang_thai = v.trang_thai(co.khoa_goc(kq.kho_id, "goc.opus"), kq.kho_id)
    # Lô hai video: video mốc là lượt parser hỏng ở trên, video thứ hai chưa quét.
    tt = co.TrangThaiLo(kho_id=kq.kho_id, cfg=e.config,
                        videos=[v, co.VideoTrongLo(thu_tu=2, nguon="v2")])
    kl = co.ket_luan(tt)
    print("LuotQuet:", lq.hop_le, lq.tron, "trang_thai=", trang_thai,
          "| ket_luan lo:", kl.trang_thai, repr(kl.ly_do))

    assert kl.trang_thai != co.KHONG_TIM_THAY, \
        f"lô kết luận «Không tìm thấy» chỉ dựa trên một lượt parser hỏng: {kl.ly_do!r}"
    assert lq.tron is False, "lượt parser hỏng bị tính là lượt quét TRỌN hợp lệ"
    assert lq.hop_le is False and lq.ly_do == kq.note
    assert trang_thai != co.VANG_MAT_DU, \
        "video gốc bị loại bằng «Không có (đã quét trọn)» dù parser không đọc được gì"
    assert os.path.exists(str(media))
