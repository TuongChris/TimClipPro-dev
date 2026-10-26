# -*- coding: utf-8 -*-
"""Audit F-3: câu chẩn đoán «0 kết quả» không được KẾT LUẬN cho cả video khi chỉ quét một phần.

Kịch bản (dữ liệu tổng hợp, không mạng): video 40 giờ, lô «Quét YouTube» để mặc định
«Tự động — video trên 6 giờ chỉ quét 3 giờ đầu». Engine chỉ tải + so khớp 00:00:00 → 03:00:00,
không thấy gì, giữ status «ok» và ghi đúng vào ``note`` rằng đây KHÔNG phải kết luận cho toàn
video. Nhưng ``note`` chỉ hiện cho kết quả LỖI; thứ người dùng đọc đầu tiên là cảnh báo
«— không có đoạn nào đạt tiêu chí.» kèm ``cd.mat_o_dau()``:

* «Video không chứa đoạn tiếng nào của kho «SML» …» (audfprint không ra dòng khớp), hoặc
* «… Nhiều khả năng video này không chứa clip gốc nào trong kho.» (bằng chứng quá yếu).

Bất biến dự án (tests/test_gioi_han_video_dai.py, docstring): «không thấy» không bao giờ thành
kết luận cho cả video. Cảnh báo kết luận 0 kết quả của một nguồn quét MỘT PHẦN phải tự nói
phạm vi (03:00:00 / «chưa quét» / «một phần») — không được khẳng định tuyệt đối.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import chan_doan_quet as cd_mod
from chan_doan_quet import ChanDoanQuet
from engine import GHVD_TU_DONG, Config, Engine, ScanResult

DAI_40H = 40 * 3600.0
BA_GIO = 3 * 3600.0
TIEU_DE = "40 Hours Compilation (synthetic)"


def _chan_doan(giai_doan: str) -> ChanDoanQuet:
    """Phễu đúng như ``Engine._chot_chan_doan`` chốt cho file 3 giờ đầu, 0 kết quả."""
    if giai_doan == cd_mod.AUDFPRINT_KHONG_RA_MATCH:
        cd = ChanDoanQuet(so_khuc=36, dong_tho=36, dong_co_matched=0)
    else:  # BANG_CHUNG_QUA_YEU: có dòng khớp nhưng quá ngắn/ít hash
        cd = ChanDoanQuet(so_khuc=36, dong_tho=50, dong_co_matched=14, parse_duoc=14,
                          qua_min_hash=3, qua_min_match_s=0, gop_lai=0,
                          hash_tho_lon_nhat=40, khop_tho_dai_nhat=4.0)
    cd.da_chon = 0
    cd.chot_giai_doan()
    assert cd.giai_doan_mat == giai_doan
    if giai_doan == cd_mod.AUDFPRINT_KHONG_RA_MATCH:
        cd.ten_kho, cd.so_clip_kho = "SML", 779      # như _chot_chan_doan điền vào
    return cd


def _ket_qua_40h(tmp_path, monkeypatch, giai_doan: str) -> ScanResult:
    """Đi đúng đường thật ``scan_youtube`` → ``_quet_video_dai_gioi_han`` với tải/quét giả."""
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "d"), out_dir=str(tmp_path / "r"))
    e.config = Config(tai_mot_phan=True, quet_tang_dan_tu_gio=10.0, quet_tang_dan_buoc_gio=3.0)
    e._gioi_han_video_dai = GHVD_TU_DONG          # radio mặc định của trang «Quét YouTube»
    monkeypatch.setattr(e, "require", lambda **k: None)
    monkeypatch.setattr(e, "youtube_info", lambda url: {
        "id": "vid40hxxxxx", "title": TIEU_DE, "duration": DAI_40H,
        "channel": "", "channel_id": "", "channel_url": "", "upload_date": ""})
    lan_tai = []

    def tai(url, vid, progress=None, gioi_han_giay=None):
        lan_tai.append(gioi_han_giay)
        p = os.path.join(e.dl_dir, f"{vid}__p{int(gioi_han_giay or 0)}.webm")
        with open(p, "wb") as f:
            f.write(b"x")
        return p

    monkeypatch.setattr(e, "download_audio", tai)
    monkeypatch.setattr(e, "duration_of", lambda p: float(lan_tai[-1] or DAI_40H))
    monkeypatch.setattr(e, "do_dai_audio_that", lambda p: float(lan_tai[-1] or DAI_40H))

    def quet(path, **k):
        dai = float(lan_tai[-1] or DAI_40H)
        r = ScanResult(source_name=TIEU_DE, duration_s=dai, pham_vi_quet_s=dai,
                       vung_da_khop=[(0.0, dai)])
        r.chan_doan = _chan_doan(giai_doan)       # scan_media thật gắn phễu đã chốt
        return r

    monkeypatch.setattr(e, "scan_media", quet)
    kq = e.scan_youtube("https://youtu.be/vid40hxxxxx", luu_lich_su=False)

    # Tiền đề — engine đã biết đây là quét MỘT PHẦN và không phải kết luận cho cả video.
    assert lan_tai == [BA_GIO]
    assert kq.status == "ok" and not kq.matches
    assert kq.quet_mot_phan is True and kq.ly_do_pham_vi == "gioi_han_video_dai"
    assert "KHÔNG phải kết luận cho toàn video" in kq.note
    assert kq.chan_doan is not None and kq.chan_doan.giai_doan_mat == giai_doan
    return kq


def _co_pham_vi(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ("03:00:00", "chưa quét", "một phần", "3 giờ đầu"))


@pytest.mark.parametrize("giai_doan", [cd_mod.AUDFPRINT_KHONG_RA_MATCH,
                                       cd_mod.BANG_CHUNG_QUA_YEU])
def test_canh_bao_0_ket_qua_cua_quet_mot_phan_phai_noi_pham_vi(tmp_path, monkeypatch, giai_doan):
    from streamlit.testing.v1 import AppTest

    kq = _ket_qua_40h(tmp_path / "quet", monkeypatch, giai_doan)

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    app = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=120).run()
    assert not at.exception
    at.session_state.job.update({"running": False, "kind": "scan", "results": [kq],
                                 "error": "", "da_day_sheet": True})
    at.run()
    assert not at.exception

    ket_luan = [w.value for w in at.warning if "không có đoạn nào đạt tiêu chí" in w.value]
    assert len(ket_luan) == 1, [w.value for w in at.warning]
    cau = ket_luan[0]
    # Tiền đề: hộp «Chưa quét trọn» có tồn tại — nhưng nằm SAU, tách khỏi câu kết luận.
    assert any("Chưa quét trọn" in i.value for i in at.info)

    # Hành vi ĐÚNG: câu kết luận của nguồn quét một phần tự nói phạm vi đã quét,
    # không khẳng định tuyệt đối «video không chứa …» cho 37 giờ chưa quét.
    assert _co_pham_vi(cau), (
        "Cảnh báo 0 kết quả của video chỉ quét 3/40 giờ không nói phạm vi:\n" + cau)


# --- Mức đơn vị: câu của ChanDoanQuet khi biết phạm vi (không cần giao diện) ----------------

@pytest.mark.parametrize("giai_doan", [cd_mod.AUDFPRINT_KHONG_RA_MATCH,
                                       cd_mod.BANG_CHUNG_QUA_YEU])
def test_mat_o_dau_quet_mot_phan_khong_ket_luan_cho_ca_video(giai_doan):
    cd = _chan_doan(giai_doan)
    pham_vi = "giới hạn video dài: chỉ tải và so khớp 03:00:00/40:00:00 đầu"
    cau = cd.mat_o_dau(pham_vi)
    assert pham_vi in cau and "KHÔNG phải kết luận cho toàn video" in cau
    assert "Video không chứa" not in cau and "video này không chứa" not in cau
    # Lời khuyên «clip gốc chưa có trong kho» chỉ nhầm chỗ khi còn phần chưa quét.
    assert "chưa có trong kho" not in cau


@pytest.mark.parametrize("giai_doan", [cd_mod.AUDFPRINT_KHONG_RA_MATCH,
                                       cd_mod.BANG_CHUNG_QUA_YEU])
def test_mat_o_dau_quet_tron_giu_nguyen_cau_cu(giai_doan):
    cd = _chan_doan(giai_doan)
    assert cd.mat_o_dau() == cd.mat_o_dau("")
    assert "CHỈ QUÉT MỘT PHẦN" not in cd.mat_o_dau()
    if giai_doan == cd_mod.BANG_CHUNG_QUA_YEU:
        assert cd.mat_o_dau() == cd_mod.MO_TA_GIAI_DOAN[giai_doan]
    else:
        assert cd.mat_o_dau().startswith("Video không chứa đoạn tiếng nào của kho «SML»")


def test_ket_qua_co_ma_cd_none_quet_mot_phan_van_noi_pham_vi(tmp_path, monkeypatch):
    """Nhánh không có phễu (``chan_doan is None``) cũng không được nói tuyệt đối."""
    from streamlit.testing.v1 import AppTest

    kq = ScanResult(source_name=TIEU_DE, source_ref="https://youtu.be/vid40hxxxxx",
                    duration_s=DAI_40H, pham_vi_quet_s=BA_GIO,
                    vung_da_khop=[(0.0, BA_GIO)], ly_do_pham_vi="gioi_han_video_dai")
    assert kq.quet_mot_phan and kq.chan_doan is None
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    app = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=120).run()
    at.session_state.job.update({"running": False, "kind": "scan", "results": [kq],
                                 "error": "", "da_day_sheet": True})
    at.run()
    assert not at.exception
    cau = [w.value for w in at.warning if "không tìm thấy clip gốc nào" in w.value]
    assert len(cau) == 1 and _co_pham_vi(cau[0]), [w.value for w in at.warning]
