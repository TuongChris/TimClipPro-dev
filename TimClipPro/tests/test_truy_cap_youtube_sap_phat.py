# -*- coding: utf-8 -*-
"""Audit D-4 — premiere / livestream SẮP diễn ra ở đầu tab Videos làm hỏng cả lượt đồng bộ kênh.

Kênh hay đặt lịch premiere/live: tab Videos (mới nhất trước) có vài mục ``live_status="is_upcoming"``, chưa có thời
lượng. yt-dlp ném «This live event will begin in …» / «Premieres in …» cho từng mục. Đúng: đó là chuyện của TỪNG video
(chưa phát — chưa tải được, lượt sau thử lại khi đã phát), KHÔNG phải YouTube chặn cả phiên: video thường phía sau vẫn
phải được tải, lượt không được báo «BI_CHAN», và không đốt hết các player client cho mỗi mục chưa phát.

yt-dlp giả theo kịch bản (`tests/ytdlp_gia.py`), FFmpeg/ffprobe giả. Không mạng, dữ liệu tổng hợp.
"""

import shutil

import pytest
import yt_dlp

import channel
import truy_cap_youtube as t
import ytdlp_chung as y
from channel import ChannelSync
from ytdlp_gia import YdlKichBan

SAN_SANG = y.KhaNangJs(True, node=r"C:\gia\nodejs\node.exe", node_phien_ban="24.21.0", ejs_phien_ban="0.8.0")
DAI = 600.0
SAP_LIVE = "ERROR: [youtube] {id}: This live event will begin in 2 days."
SAP_PREMIERE = "ERROR: [youtube] {id}: Premieres in 7 hours"


def _ma(i: int) -> str:
    return f"p{i:010d}"                 # 11 ký tự như mã YouTube


SAP = [_ma(i) for i in range(5)]        # 5 mục sắp phát ở ĐẦU kênh (mới nhất trước)
THUONG = [_ma(i) for i in range(5, 7)]  # 2 video thường đã đăng


def _danh_sach():
    entries = []
    for m in SAP:
        entries.append({"id": m, "title": f"Sắp phát {m}", "url": f"https://www.youtube.com/watch?v={m}",
                        "duration": None, "live_status": "is_upcoming", "release_timestamp": 4102444800})
    for m in THUONG:
        entries.append({"id": m, "title": f"Video {m}", "url": f"https://www.youtube.com/watch?v={m}",
                        "duration": DAI, "live_status": "not_live"})
    return {"_type": "playlist", "id": "UCkenh_premiere", "entries": entries}


@pytest.fixture()
def may(monkeypatch):
    monkeypatch.setattr(y, "kha_nang_js", lambda: SAN_SANG)
    for k in ("metadata", "listing"):
        monkeypatch.setitem(t.NGAN_SACH, k, t.NganSach(cho_tam_thoi=(0.01,), cho_429=(0.01,)))
    monkeypatch.setattr(channel, "do_dai_media", lambda p: DAI)
    monkeypatch.setattr(channel, "do_dai_luong_tieng", lambda p: DAI)


def _cs(kho) -> ChannelSync:
    cs = ChannelSync(str(kho))

    def nen(nguon, tam, _tham_chieu, _huy):
        shutil.copyfile(nguon, tam)
        return ""
    cs._nen_va_kiem = nen
    return cs


@pytest.mark.parametrize("tin", [SAP_LIVE, SAP_PREMIERE])
def test_loi_chua_phat_la_loi_tung_video_khong_phai_chua_phan_loai(tin):
    f = t.phan_loai_loi(RuntimeError(tin.format(id="abcdefghijk")), thao_tac="download")
    assert f.category != t.UNKNOWN_YOUTUBE_ERROR, (
        f"«{tin}» bị xếp {f.category}: 5 mục sắp phát liên tiếp sẽ mở cầu dao cả phiên")
    assert f.category in t.DUNG_DOI_CLIENT, "đổi player client không làm premiere phát sớm hơn"


def test_dong_bo_kenh_co_5_premiere_dau_kenh_van_tai_video_thuong(tmp_path, monkeypatch, may):
    tai = {m: (SAP_LIVE if i % 2 == 0 else SAP_PREMIERE) for i, m in enumerate(SAP)}
    ydl = YdlKichBan(tai=tai, liet_ke=lambda _p, _u: _danh_sach())
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)

    r = _cs(tmp_path / "KenhPremiere").sync("https://www.youtube.com/@KenhThuPremiere")

    lan_tai = [g[1] for g in ydl.goi if g[0] == "tai"]
    so_lan_moi_sap = {m: lan_tai.count(m) for m in SAP}
    print("trang_thai=", r["trang_thai"], "moi=", r["moi"], "so_loi=", r["so_loi"], "chua_thu=", r["chua_thu"],
          "chan_youtube=", r["chan_youtube"])
    print("lan_tai=", lan_tai)

    assert all(lan_tai.count(m) == 1 for m in THUONG), (
        f"video thường phía sau không được thử: {[(m, lan_tai.count(m)) for m in THUONG]}")
    assert r["moi"] == 2, "2 video thường phải được tải"
    assert r["trang_thai"] != channel.DONG_BO_BI_CHAN and not r["chan_youtube"], (
        f"premiere chưa phát không phải YouTube chặn phiên: {r['chan_youtube']!r}")
    assert all(n <= 1 for n in so_lan_moi_sap.values()), (
        f"mục chưa phát bị thử qua nhiều player client: {so_lan_moi_sap}")


def test_doi_chung_cung_kich_ban_khong_premiere_thi_tai_du(tmp_path, monkeypatch, may):
    """Đối chứng: cùng bộ dựng, mục đầu kênh tải được → 7/7 tải, DAY_DU (bộ dựng không hỏng)."""
    ydl = YdlKichBan(liet_ke=lambda _p, _u: _danh_sach())
    monkeypatch.setattr(yt_dlp, "YoutubeDL", ydl)
    r = _cs(tmp_path / "KenhDoiChung").sync("https://www.youtube.com/@KenhThuPremiere")
    assert r["moi"] == 7 and r["trang_thai"] != channel.DONG_BO_BI_CHAN


def test_phien_khong_mo_cau_dao_vi_mot_day_muc_chua_phat():
    """Chặn sửa quá tay: mục chưa phát là lỗi của TỪNG video — không mở cầu dao dù bao nhiêu mục liền nhau, không tính
    là «YouTube chặn truy cập» (CLI mã 3), và không cắt ngang chuỗi «liên tiếp» của lỗi truy cập thật."""
    phien = t.PhienYouTube()
    for i in range(30):
        f = phien.ghi_loi(RuntimeError(SAP_PREMIERE.format(id=_ma(i))), "download", _ma(i))
        assert f.category == t.UPCOMING_NOT_STARTED and not f.retryable and not f.la_loi_truy_cap
    assert not phien.mo
    assert t.UPCOMING_NOT_STARTED not in t.NGUONG_MO
    # Bot-check vẫn được ưu tiên, kể cả khi câu lỗi có cụm của mục sắp phát.
    assert t.phan_loai_loi(RuntimeError(
        "ERROR: [youtube] abcdefghijk: Premieres in 7 hours. Sign in to confirm you're not a bot")
    ).category == t.BOT_CHALLENGE
