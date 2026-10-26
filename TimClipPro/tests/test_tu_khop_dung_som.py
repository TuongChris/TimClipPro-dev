# -*- coding: utf-8 -*-
"""Khoá hồi quy audit A-7 (P3): mảnh TỰ KHỚP không được làm dừng sớm lượt quét file trong máy.

Kịch bản synthetic, không mạng, không FFmpeg/audfprint thật: người dùng quét một file trong máy dài 4 giờ
(4 khúc × 3.600 s) mà chính file đó cũng nằm trong kho vân tay (cùng tên ``goc.opus`` — «lỡ để chung thư
mục», ca mà ``_scan_media`` tự chặn). Khúc đầu tự khớp 9.000 hash / 200 s; một clip KHÁC của kho
(``khac.opus``) nằm ở phần SAU của file. ``top_n = 1`` (người dùng chọn), các cấu hình khác mặc định.

Hành vi ĐÚNG (``_scan_media``: tự khớp «vô nghĩa» và bị bỏ khỏi kết quả; chế độ nguồn chung đã bỏ tự khớp
TRƯỚC khi xét dừng — ``_dat_cho_muc_tieu``; ghi chú dừng sớm chỉ đúng khi «đã đủ bằng chứng»):

* tự khớp không phải bằng chứng, nên không được làm dừng sớm: phần còn lại của file vẫn được so khớp và
  clip ``khac.opus`` được tìm thấy (quét tăng dần được dừng SAU khi thấy nó — đó là bằng chứng thật);
* không bao giờ có lượt ``ok`` + 0 kết quả + ``dung_som`` + ghi chú «đã đủ bằng chứng».

Hai đường dừng sớm của nhánh thường đều bị xét: Top-1 tìm nhanh (``_du_manh_de_dung_som``) và quét tăng dần
(``_du_de_dung_som``, video > ``quet_tang_dan_tu_gio``).
"""

from engine import Engine


def _eng(tmp_path) -> Engine:
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"),
               out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    e.config.top_n = 1
    e.config.quet_da_toc_do = False
    e._overlap_thuc_te = lambda *a, **k: 0
    e.do_dai_am_thanh = lambda p: None
    e.db_clips = lambda **k: [
        {"ten": "goc.opus", "duong_dan": "goc.opus", "so_hash": 20000},
        {"ten": "khac.opus", "duong_dan": "khac.opus", "so_hash": 20000},
    ]
    return e


def _manh(clip, bat_dau, khop=200.0, so_hash=9000):
    return {"clip": clip, "bat_dau": bat_dau, "khop": khop, "t_clip": 0.0,
            "hash": so_hash, "align": bat_dau}


def _khop_gia(da_hoi: list, khuc_khac: int):
    """Giả ``_match_chunks``: khúc 0 tự khớp, khúc ``khuc_khac`` có clip khác của kho."""
    def khop(chunks, *a, **k):
        da_hoi.extend(chunks)
        ra = []
        for c in chunks:
            if c.endswith("chunk_0000000.wav"):
                ra.append(_manh("goc.opus", 10.0))
            if c.endswith(f"chunk_{khuc_khac:07d}.wav"):
                ra.append(_manh("khac.opus", khuc_khac + 100.0))
        return ra
    return khop


def _kiem(kq, da_hoi, so_khuc):
    """``so_khuc`` = số khúc phải được so khớp: tới hết đoạn chứa ``khac.opus``."""
    sai = (kq.status == "ok" and not kq.matches and kq.ly_do_pham_vi == "dung_som")
    assert not sai, (
        f"tự khớp làm dừng sớm: status={kq.status!r}, matches={kq.matches}, "
        f"ly_do_pham_vi={kq.ly_do_pham_vi!r}, đã khớp {len(da_hoi)}/{so_khuc} khúc, note={kq.note!r}")
    assert len(da_hoi) == so_khuc
    assert [m.clip for m in kq.matches] == ["khac.opus"]


def test_top1_tim_nhanh_khong_dung_som_vi_tu_khop(tmp_path):
    e = _eng(tmp_path)
    e.config.chunk_s = 3600
    e.config.top1_tim_nhanh = True       # mặc định
    e.config.top1_khuc_toi_thieu = 3     # mặc định
    e.duration_of = lambda p: 14400.0
    e._cut_chunks = lambda *a, **k: (
        [str(tmp_path / f"chunk_{n:07d}.wav") for n in (0, 3600, 7200, 10800)], 14400.0)
    da_hoi: list = []
    e._match_chunks = _khop_gia(da_hoi, 7200)          # khúc thứ ba
    media = tmp_path / "goc.opus"
    media.write_bytes(b"x")

    kq = e.scan_media(str(media))

    _kiem(kq, da_hoi, 4)


def test_quet_tang_dan_khong_dung_som_vi_tu_khop(tmp_path):
    e = _eng(tmp_path)
    e.config.chunk_s = 3600
    e.config.top1_tim_nhanh = False      # cô lập đường quét tăng dần
    e.config.quet_tang_dan = True        # mặc định: video > 10 giờ, bước 3 giờ
    tong = 12 * 3600.0
    e.duration_of = lambda p: tong

    def cat(path, progress, a, b, workspace=None, tu_giay=0.0, den_giay=None, **k):
        den = tong if den_giay is None else den_giay
        moc = range(int(tu_giay), int(den), 3600)
        return [str(tmp_path / f"chunk_{n:07d}.wav") for n in moc], den

    e._cut_chunks = cat
    da_hoi: list = []
    e._match_chunks = _khop_gia(da_hoi, 7 * 3600)      # đoạn quét thứ ba (6–9 giờ)
    media = tmp_path / "goc.opus"
    media.write_bytes(b"x")

    kq = e.scan_media(str(media))

    # Dừng sau đoạn 6–9 giờ là ĐÚNG (top_n = 1, đã thấy clip khác); trước đó thì sai.
    _kiem(kq, da_hoi, 9)
