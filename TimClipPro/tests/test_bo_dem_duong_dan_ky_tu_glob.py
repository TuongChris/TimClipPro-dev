# -*- coding: utf-8 -*-
"""Bộ đệm audio tra bằng glob phải đúng cả khi thư mục dữ liệu có ký tự đặc biệt của glob (audit C-13).

Dữ liệu hoàn toàn synthetic trong ``tmp_path``: không mạng, yt-dlp bị thay bằng bản giả cấm gọi.

Thư mục chứa ``[`` / ``]`` là hợp lệ trên Windows (vd. ``TIMCLIP_DATA_DIR=C:\\Dev\\[PC2]\\data``,
hay thư mục mã ``Tool [moi]`` ở chế độ legacy). Mẫu ``os.path.join(self.dl_dir, ten + ".*")``
không ``glob.escape`` phần thư mục: ``[dev]`` thành lớp ký tự nên glob luôn rỗng → bộ đệm không
bao giờ trúng, sau khi tải cũng «không thấy file sau khi tải», ``_bo_ban_dem`` báo đã bỏ hết
trong khi file vẫn nằm đó. Ca đối chứng (thư mục không có ngoặc) chứng minh lỗi chỉ do ngoặc.
"""
import pytest

from engine import Engine

THU_MUC = ["binh_thuong", "[dev]"]


class _KhongDuocTai(BaseException):
    """Thoát thẳng khỏi chuỗi thử client/cookie (bắt Exception) — không mạng, không chờ."""


def _engine(tmp_path, monkeypatch, ten_thu_muc):
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    goc = tmp_path / ten_thu_muc
    return goc, Engine(root=str(goc), data_dir=str(goc / "data"), out_dir=str(goc / "out"))


@pytest.mark.parametrize("ten_thu_muc", THU_MUC)
def test_audio_da_tai_duoc_dung_lai_ke_ca_khi_thu_muc_du_lieu_co_ngoac_vuong(
        tmp_path, monkeypatch, ten_thu_muc):
    import yt_dlp

    goc, e = _engine(tmp_path, monkeypatch, ten_thu_muc)
    video_id = "abcDEF12345"
    da_co = goc / "data" / "downloads" / f"{video_id}.opus"
    da_co.parent.mkdir(parents=True, exist_ok=True)
    da_co.write_bytes(b"OggS" + b"\0" * 64)

    def cam_tai(*a, **k):
        raise _KhongDuocTai("yt-dlp bị gọi dù audio đã có sẵn trong bộ đệm")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", cam_tai)

    try:
        duong = e.download_audio(f"https://youtu.be/{video_id}", video_id)
    except _KhongDuocTai as loi:
        pytest.fail(f"[{ten_thu_muc}] tra bộ đệm bỏ sót {da_co.name} (glob không escape thư mục "
                    f"dữ liệu) → tải lại: {loi}")

    assert str(duong) == str(da_co)


@pytest.mark.parametrize("ten_thu_muc", THU_MUC)
def test_bo_ban_dem_xoa_that_ke_ca_khi_thu_muc_du_lieu_co_ngoac_vuong(
        tmp_path, monkeypatch, ten_thu_muc):
    goc, e = _engine(tmp_path, monkeypatch, ten_thu_muc)
    video_id = "abcDEF12345"
    ban_dem = goc / "data" / "downloads" / f"{video_id}.m4a"
    ban_dem.parent.mkdir(parents=True, exist_ok=True)
    ban_dem.write_bytes(b"\0" * 32)

    assert e._bo_ban_dem(video_id) is True
    # «True = không còn bản nào»: lời hứa đó chỉ đúng nếu file thật sự đã bị xoá.
    assert not ban_dem.exists(), f"[{ten_thu_muc}] _bo_ban_dem báo đã bỏ nhưng bản đệm vẫn còn"


@pytest.mark.parametrize("ten_thu_muc", THU_MUC)
def test_chan_doan_van_giu_tran_200_file_khi_thu_muc_du_lieu_co_ngoac_vuong(tmp_path, ten_thu_muc):
    """Vòng dọn giữ 200 bản ghi chẩn đoán cũng đi theo glob: không escape thì không bao giờ dọn."""
    from chan_doan_quet import ChanDoanQuet
    from engine import Config, ScanResult

    goc = tmp_path / ten_thu_muc
    thu_muc = goc / "chan_doan"
    thu_muc.mkdir(parents=True)
    for i in range(205):
        (thu_muc / f"cu_{i:03d}.json").write_text("{}", encoding="utf-8")

    e = Engine.__new__(Engine)
    e.data_dir = str(goc)
    e.kho_dang_dung = "SML"
    e.db_file = str(goc / "kho.pklz")
    e.config = Config()
    cd = ChanDoanQuet(so_khuc=1, dong_co_matched=0, ten_kho="SML", so_clip_kho=3)
    cd.chot_giai_doan()
    e._luu_chan_doan(ScanResult(source_name="Video thu", duration_s=60.0), cd)

    assert len(list(thu_muc.glob("*.json"))) == 200, f"[{ten_thu_muc}] vòng dọn chẩn đoán không chạy"
