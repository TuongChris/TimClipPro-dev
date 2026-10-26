# -*- coding: utf-8 -*-
"""Audit A-2 (P1): ``kiem_ngay_dang --repair-offline --apply`` đóng dấu
``publication_date_source="upload_date"`` lên entry mà ``va_metadata`` / seed tên file đã ghi
ngày ĐÃ QUY ĐỔI (UTC+7). ``clip_metadata`` coi dấu đó là nguồn gốc rõ ràng và nâng
``publication_date`` thành ``ngay_raw`` → báo cáo V2 in ngày quy đổi như ``upload_date``
nguyên bản của yt-dlp (lệch 1 ngày, không cảnh báo).

Bất biến (TimClipPro/CLAUDE.md, docs/REPORT_POLICY_V2.md §4): ngày V2 = ``upload_date`` NGUYÊN
BẢN; kho cũ chỉ có ngày quy đổi → để TRỐNG kèm lý do, không đoán từ timestamp/tên file.

Hoàn toàn offline: ``lay_info_video`` bị thay bằng bản giả trả info dạng yt-dlp.
"""
from __future__ import annotations

import json

import bao_cao_v2 as v2
import kiem_ngay_dang
from channel import ChannelSync
from clip_metadata import ClipMetadataResolver

VN = "Asia/Ho_Chi_Minh"
VID = "T_mKh8IUpWw"
# 2025-06-20 18:45:39 UTC = 2025-06-21 01:45 giờ Việt Nam.
INFO_YTDLP = {"id": VID, "title": "Clip goc", "upload_date": "20250620",
              "timestamp": 1750445139, "duration": 955.0}
NGAY_RAW_DUNG = "20250620"
NGAY_QUY_DOI = "20250621"


def _goc(kho, ten):
    meta = json.loads((kho / "clips_meta.json").read_text(encoding="utf-8"))
    resolved = ClipMetadataResolver.from_mapping(meta).resolve(ten)
    return resolved, v2.goc_tu_metadata(ten, resolved)


def _kiem_ngay_v2(resolved, goc):
    # Đúng: hoặc để trống kèm lý do, hoặc đúng ngày NGUYÊN BẢN — không bao giờ ngày quy đổi.
    assert resolved.ngay_raw in ("", NGAY_RAW_DUNG), (
        f"ngay_raw={resolved.ngay_raw!r} (nguồn {resolved.nguon_ngay_raw!r}) — ngày ĐÃ quy "
        f"đổi bị coi là upload_date nguyên bản (đúng: {NGAY_RAW_DUNG} hoặc trống)")
    assert goc.ngay_dang.gia_tri in ("", NGAY_RAW_DUNG), (
        f"V2 hiển thị {goc.ngay_dang.hien_thi()} (nguồn {goc.ngay_dang.nguon!r}) là ngày đăng "
        f"nguyên bản; ngày thật trên yt-dlp là 20/06/2025")
    if not goc.ngay_dang.gia_tri:
        assert goc.ngay_dang.ly_do_thieu


def test_vameta_roi_repair_offline_khong_bien_ngay_quy_doi_thanh_ngay_nguyen_ban(
        tmp_path, monkeypatch):
    ten = f"00000000 - Clip goc [{VID}].opus"      # tải lúc chưa biết ngày
    (tmp_path / ten).write_bytes(b"opus")
    monkeypatch.setattr(ChannelSync, "lay_info_video",
                        staticmethod(lambda video_id, *a, **kw: dict(INFO_YTDLP)))

    # 1) Kho cũ thiếu ngày → người dùng chạy `cli.py vameta` (fetcher MẶC ĐỊNH).
    cs = ChannelSync(str(tmp_path))
    kq = cs.va_metadata()
    assert kq["da_va"] == 1 and kq["loi"] == [], kq
    muc = cs.load_meta()[ten]
    assert muc["upload_date"] == NGAY_QUY_DOI          # vameta lưu ngày ĐÃ quy đổi
    # Mốc: ngay sau vameta, V2 để trống đúng luật (chưa có ngày nguyên bản).
    resolved, goc = _goc(tmp_path, ten)
    assert resolved.ngay_raw == "" and goc.ngay_dang.gia_tri == ""

    # 2) Lượt sửa offline theo tài liệu: kiem_ngay_dang.py --repair-offline --apply.
    kiem_ngay_dang.repair(str(tmp_path), VN, dung_mang=False, apply=True, gioi_han=0)
    sau = json.loads((tmp_path / "clips_meta.json").read_text(encoding="utf-8"))[ten]
    print("entry sau repair offline:", {k: sau.get(k) for k in (
        "upload_date", "publication_date", "publication_date_source", "upload_date_raw")})

    # 3) Báo cáo V2 không được biến ngày quy đổi thành ngày nguyên bản.
    resolved, goc = _goc(tmp_path, ten)
    _kiem_ngay_v2(resolved, goc)


def test_seed_ten_file_roi_repair_offline_khong_bien_ngay_ten_file_thanh_ngay_nguyen_ban(
        tmp_path):
    # Tên file theo luật cũ mang ngày ĐÃ quy đổi (giờ VN), như clip tải trước bản V2.
    ten = f"{NGAY_QUY_DOI} - Clip goc [{VID}].opus"
    (tmp_path / ten).write_bytes(b"opus")
    cs = ChannelSync(str(tmp_path))
    meta, them = cs.seed_meta_tu_dia()
    assert them == 1 and meta[ten]["upload_date"] == NGAY_QUY_DOI
    cs.save_meta(meta)
    resolved, goc = _goc(tmp_path, ten)
    assert resolved.ngay_raw == ""                     # mốc: chưa có nguồn nguyên bản

    kiem_ngay_dang.repair(str(tmp_path), VN, dung_mang=False, apply=True, gioi_han=0)

    resolved, goc = _goc(tmp_path, ten)
    _kiem_ngay_v2(resolved, goc)
