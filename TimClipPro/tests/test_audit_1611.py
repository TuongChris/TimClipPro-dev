# -*- coding: utf-8 -*-
"""Audit 16/11: các lỗi tìm được trong lượt audit toàn repo (mục 1–3). Dữ liệu giả, không mạng."""

from types import SimpleNamespace

import cli


class _EngineGia:
    def __init__(self):
        self.config = SimpleNamespace(ncores=1, ytdlp_player_clients=())

    def cau_hinh_mang(self):
        return None


def _chay_kenh(monkeypatch, ket_qua):
    class _SyncGia:
        def __init__(self, kho, **kw):
            pass

        def sync(self, *a, **kw):
            return ket_qua

    monkeypatch.setattr(
        "sys.argv",
        ["cli.py", "kenh", "https://youtube.com/@Kenh", "--kho", "D:/KhoGia"],
    )
    monkeypatch.setattr(cli, "Engine", _EngineGia)
    monkeypatch.setattr(cli, "ChannelSync", _SyncGia)
    cli.main()


def test_cli_kenh_co_video_qua_dai_in_tom_tat_khong_do_loi(monkeypatch, capsys):
    """Mục 1: câu «video quá dài» cần {gio}; CLI chỉ truyền n → KeyError 'gio' sau khi đồng bộ đã chạy xong."""
    _chay_kenh(
        monkeypatch,
        {
            "trang_thai": "DAY_DU",
            "bo_qua": 3,
            "moi": 2,
            "qua_dai": 4,
            "gio_toi_da": 2,
            "loi": [],
        },
    )
    ra = capsys.readouterr().out
    assert "4 video dài hơn 2 giờ được bỏ qua" in ra
    assert "Tiếp theo: python cli.py themclip" in ra


# ---- Mục 2: đọc kho lỗi lúc gộp kết quả không được thành «âm tính, đã quét trọn» ----

def _engine_clip_ngan(tmp_path):
    from engine import Engine

    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *a, **k: None
    cfg = e.config
    cfg.chunk_s = 3600
    cfg.quet_da_toc_do = False
    e._overlap_thuc_te = lambda *a, **k: 0
    # Clip gốc NGẮN: 750 hash < sàn 1000 → chỉ nhận được qua bậc phủ cao (cần tổng hash trong kho).
    e.db_clips = lambda **k: [{"ten": f"goc{i}.opus", "duong_dan": f"goc{i}.opus", "so_hash": 750} for i in range(3)]
    e.youtube_info = lambda url: {"title": "Video", "id": "abcdefghijk", "channel": "", "channel_id": "",
                                  "channel_url": "", "upload_date": "", "duration": 3 * 3600.0}
    tep = tmp_path / "abcdefghijk.opus"
    tep.write_bytes(b"x")
    e.download_audio = lambda url, vid, progress=None, gioi_han_giay=None: str(tep)
    e.duration_of = lambda p: 3 * 3600.0
    e.do_dai_am_thanh = lambda p: 3 * 3600.0
    e._cut_chunks = lambda *a, **k: ([str(tmp_path / f"chunk_{n:07d}.wav") for n in (0, 3600, 7200)], 3 * 3600.0)
    e._match_chunks = lambda chunks, *a, **k: [
        {"clip": f"goc{i}.opus", "bat_dau": 100.0 + 1000 * i, "khop": 200.0, "t_clip": 0.0, "hash": 700,
         "align": 100.0 + 1000 * i} for i in range(3)]
    return e


def test_doi_chung_kho_doc_duoc_thi_clip_ngan_duoc_nhan(tmp_path):
    kq = _engine_clip_ngan(tmp_path).scan_youtube("https://youtu.be/abcdefghijk", luu_lich_su=False)
    assert kq.status == "ok" and len(kq.matches) == 3, kq.note


def test_kho_loi_luc_gop_khong_luu_thanh_am_tinh(tmp_path):
    e = _engine_clip_ngan(tmp_path)

    def hong():
        raise RuntimeError("file kho đang bị khoá")

    e._bang_tong_hash = hong
    kq = e.scan_youtube("https://youtu.be/abcdefghijk", luu_lich_su=False)
    assert not kq.matches
    assert kq.status == "error", f"0 kết quả vì không đọc được kho KHÔNG phải âm tính: {kq.status} / {kq.note}"
    assert "quét lại" in kq.note
    assert "Không tra được tổng hash của clip" not in kq.note, "không lặp một cảnh báo cho từng clip"



def test_kho_loi_luc_gop_van_giu_ket_qua_manh(tmp_path):
    """Clip đủ mạnh (bậc tuyệt đối, không cần tổng hash) vẫn là bằng chứng: không biến thành lỗi."""
    e = _engine_clip_ngan(tmp_path)
    tho = e._match_chunks([])
    for x in tho:
        x["hash"] = 9000
    e._match_chunks = lambda chunks, *a, **k: [dict(x) for x in tho]

    def hong():
        raise RuntimeError("file kho đang bị khoá")

    e._bang_tong_hash = hong
    kq = e.scan_youtube("https://youtu.be/abcdefghijk", luu_lich_su=False)
    assert kq.status == "ok" and kq.matches, kq.note
    assert "Không đọc được tổng hash" in kq.note

# ---- Mục 3: hồ sơ khiếu nại của dòng đã tinh chỉnh không được tự mâu thuẫn (D-50) ----

def test_ho_so_dong_tinh_chinh_do_dai_theo_khoang_hien_thi():
    import dataclasses
    import json

    import bao_cao_v2 as v2
    import dossier
    from engine import Match
    from test_bao_cao_v2 import _bc, _goc_ca_that, _kq_ca_that
    from test_bao_cao_v2_moc_tinh_chinh import _tc

    m1 = Match(clip="a [goc0000000a].opus", start_s=0.0, end_s=623.3, matched_s=584.8, clip_offset_s=38.5,
               hashes=24724, confidence="Rất chắc chắn", vung="Đầu", clip_bat_dau_s=0.0, vung_khop_s=38.5)
    m2 = Match(clip="b [goc0000000b].opus", start_s=6372.8, end_s=7040.9, matched_s=630.9, clip_offset_s=37.2,
               hashes=29198, confidence="Rất chắc chắn", vung="Giữa", clip_bat_dau_s=6372.8, vung_khop_s=6410.0)
    kq = _kq_ca_that(matches=[m1, m2], tinh_chinh=[
        _tc([(0.059, 659.889)], clip=m1.clip, start_s=0.0, cham=True),
        {"clip": m2.clip, "start_s": 6372.8, "trang_thai": "chua_tinh_chinh", "ly_do": "thử", "doan": []},
    ])
    bc = _bc(kq, goc_theo_clip={m.clip: dataclasses.replace(_goc_ca_that(), clip=m.clip) for m in kq.matches})
    doc_lai = v2.doc_anh_chup_da_luu(v2.CHINH_SACH_V2, json.dumps(bc.to_dict(), ensure_ascii=False))
    for anh in (bc, doc_lai):
        hs = dossier.dung_ho_so_v2(anh)
        assert [(m.tu_hhmmss, m.den_hhmmss) for m in hs.muc] == [("00:00:00", "00:10:59"), ("01:46:12", "01:57:20")]
        # dòng tinh chỉnh: độ dài = khoảng đang ghi (659,8 s), không phải 584,8 s đo vân tay; dòng chưa tinh chỉnh giữ cũ
        assert [m.do_dai_giay for m in hs.muc] == [660, 631]
        assert hs.tong_giay_vi_pham == 660 + 631


# ---- Mục 4: --repair-network phải lưu ngày NGUYÊN BẢN cho cột ngày của báo cáo V2 ----

def test_repair_network_luu_upload_date_raw(tmp_path):
    import json

    import kiem_ngay_dang

    ten = "00000000 - Clip cu [T_mKh8IUpWw].opus"
    (tmp_path / ten).write_bytes(b"opus")
    (tmp_path / "clips_meta.json").write_text(json.dumps({ten: {
        "id": "T_mKh8IUpWw", "title": "Clip cu", "upload_date": "20250620", "duration": 955.0}}), encoding="utf-8")

    def fetcher(video_id):
        return {"id": video_id, "upload_date": "20250620", "timestamp": 1750445139}   # VN 21/06

    kiem_ngay_dang.repair(str(tmp_path), "Asia/Ho_Chi_Minh", dung_mang=True, apply=True, gioi_han=0, fetcher=fetcher)
    meta = json.loads((tmp_path / "clips_meta.json").read_text(encoding="utf-8"))[ten]
    assert meta["publication_date"] == "20250621"
    assert meta["upload_date_raw"] == "20250620", "báo cáo V2 chỉ đọc ngày nguyên bản của yt-dlp"


# ---- Mục 5: tiêu đề toàn chữ Nhật/Hàn/emoji → tên file chỉ còn «<mã>.đuôi»; vẫn phải nhận là «đã có» ----

def test_ten_file_chi_co_ma_van_la_da_co(tmp_path):
    from tai_video_goc import ma_da_co

    for ten in ("dQw4w9WgXcQ.mp4", "AbCdEfGhIjK.m4a", "v123456789.mkv", "Tieu_de_ZZZZZZZZZZZ.mp4"):
        (tmp_path / ten).write_bytes(b"x")
    assert ma_da_co(str(tmp_path)) == {"dQw4w9WgXcQ", "v123456789", "ZZZZZZZZZZZ"}
    assert ma_da_co(str(tmp_path), chi_tieng=True) == {"AbCdEfGhIjK"}


# ---- Mục 9: cau_hinh.json sửa tay (hợp lệ theo Config.validate) ngoài khung ô số không được khoá giao diện ----

def test_cau_hinh_sua_tay_ngoai_khung_o_so_van_mo_duoc_app(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    sua_tay = {"top_n": 60, "chunk_s": 10800, "overlap_s": 4000, "min_hash": 3, "ncores": 12,
               "quet_tang_dan_buoc_gio": 30.0, "quet_tang_dan_tu_gio": 0.0, "min_match_s": 0}
    (data / "cau_hinh.json").write_text(json.dumps(sua_tay), encoding="utf-8")
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    c = at.session_state.eng.config
    assert (c.top_n, c.chunk_s, c.overlap_s, c.min_hash, c.ncores, c.quet_tang_dan_buoc_gio) == (60, 10800, 4000, 3, 12, 30.0), \
        "giá trị người dùng đặt phải giữ nguyên, không bị kẹp lại"


# ---- Mục 10: «Vá metadata thiếu từ YouTube» bị YouTube chặn giữa chừng không được báo xanh ----

def _ket_qua_va_metadata(tmp_path, monkeypatch, r):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    at.session_state.job.update({"running": False, "pct": 1.0, "msg": "", "error": "", "kind": "metadata_network",
                                 "results": {"snapshot_path": "snap.json", "bo_qua": 0, **r}})
    at.run()
    assert not at.exception
    return at


def test_va_metadata_bi_chan_khong_bao_xanh(tmp_path, monkeypatch):
    at = _ket_qua_va_metadata(tmp_path, monkeypatch, {
        "da_va": 3, "tong": 500, "loi": [], "chan_youtube": "YouTube nghi là bot — dừng để tránh bị chặn nặng hơn."})
    assert not any("Đã vá metadata" in (x.value or "") for x in at.success)
    assert any("Đã vá metadata snapshot cho 3/500" in (x.value or "") for x in at.warning)
    assert any("nghi là bot" in (x.value or "") for x in at.error)


def test_va_metadata_xong_sach_van_xanh(tmp_path, monkeypatch):
    at = _ket_qua_va_metadata(tmp_path, monkeypatch, {"da_va": 5, "tong": 5, "loi": [], "chan_youtube": ""})
    assert any("Đã vá metadata snapshot cho 5/5" in (x.value or "") for x in at.success)
