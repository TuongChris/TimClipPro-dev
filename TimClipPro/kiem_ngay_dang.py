# -*- coding: utf-8 -*-
"""Audit và sửa ngày đăng trong clips_meta.json của một kho clip gốc.

Mặc định **chỉ đọc**. Chỉ ghi khi có ``--apply``.

Vì sao cần công cụ này
======================
Metadata cũ được ghi bằng ``upload_date`` của yt-dlp — là ngày theo lịch **UTC**.
Với người dùng ở ``Asia/Ho_Chi_Minh``, video phát hành từ 17:00 UTC trở đi đã
sang ngày hôm sau, nên ngày lưu bị lệch một ngày. Xem
``docs/PUBLICATION_DATE_ARCHITECTURE.md``.

Giới hạn quan trọng của repair offline
=====================================
Entry cũ **chỉ lưu chuỗi ``YYYYMMDD``**, không lưu epoch. Không có giờ thì
không thể biết video phát hành lúc 09:00 hay 20:00 UTC, tức **không thể** biết
ngày giờ Việt Nam có lệch hay không. Vì vậy ``--repair-offline`` chỉ sửa được
entry đã lưu sẵn ``timestamp``/``release_timestamp``; phần còn lại bắt buộc
``--repair-network``. Công cụ này tuyệt đối không đoán.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field

import youtube_api
from channel import ChannelSync, info_tu_api, truong_ngay_tu_api
from clip_metadata import extract_youtube_id, filename_fallback_parts, valid_upload_date
from luu_tru import LoiDuLieu, cap_nhat_json
from truy_cap_youtube import PhienYouTube, che_bi_mat, dong_trang_thai_api
from publication_date import (
    MUI_GIO_MAC_DINH,
    TRUONG_EPOCH,
    epoch_tu_published_at,
    format_publication_date,
    ngay_tu_chuoi,
    resolve_publication_date,
)

# Chỉ nguồn suy từ epoch mới đủ chắc để khỏi hỏi lại YouTube.
TRUONG_DO_TIN_CAY_CAO = frozenset(TRUONG_EPOCH)


def _da_chac_chan(entry: dict) -> bool:
    """Ngày đã có nguồn ĐỘ TIN CẬY CAO: suy từ epoch, hoặc ``published_at`` của YouTube Data API (có giờ, D-51)."""
    return (entry.get("publication_date_source") in TRUONG_DO_TIN_CAY_CAO
            or epoch_tu_published_at(entry.get("published_at")) is not None)


def _ma_video(ten: str, entry: dict) -> str:
    return str(entry.get("id") or "") or (extract_youtube_id(ten) or "")

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


@dataclass
class ThongKe:
    tong: int = 0
    co_provenance: int = 0          # đã có publication_date + nguồn
    chi_upload_date: int = 0        # schema cũ, không biết giờ
    co_epoch_luu_san: int = 0       # sửa được offline
    thieu_ngay: int = 0
    can_xem_lai: list = field(default_factory=list)
    se_doi: list = field(default_factory=list)
    mo_ho: list = field(default_factory=list)


def _doc_meta(kho: str, *, chi_doc: bool = True) -> tuple[ChannelSync, dict]:
    """``chi_doc`` (audit, dry-run): đọc NGHIÊM NGẶT — file hỏng → ``LoiDuLieu``, không đổi tên, không chép .bak đè, không
    tạo khoá trong kho (audit 09/11: ``load_meta`` tự phục hồi nên chế độ «chỉ đọc» từng ghi vào clips_meta.json)."""
    cs = ChannelSync(kho)
    if not chi_doc:
        return cs, cs.load_meta()
    if not os.path.isfile(cs.meta_file):
        return cs, {}
    try:
        with open(cs.meta_file, encoding="utf-8-sig") as f:
            meta = json.load(f)
    except (OSError, ValueError) as e:
        raise LoiDuLieu(f"Không đọc được {cs.meta_file} ({type(e).__name__}) — chế độ chỉ đọc nên KHÔNG sửa gì; mở "
                        "kho trong ứng dụng (tự phục hồi từ .bak) hoặc kiểm file rồi chạy lại.") from e
    if not isinstance(meta, dict):
        raise LoiDuLieu(f"{cs.meta_file} không phải object JSON — chế độ chỉ đọc nên KHÔNG sửa gì.")
    return cs, meta


def audit(kho: str, mui_gio: str) -> ThongKe:
    _cs, meta = _doc_meta(kho)
    tk = ThongKe(tong=len(meta))

    for ten, entry in meta.items():
        if not isinstance(entry, dict):
            tk.mo_ho.append((ten, "entry không phải object"))
            continue

        co_epoch = any(
            isinstance(entry.get(k), (int, float)) and entry.get(k)
            for k in ("release_timestamp", "timestamp")
        )
        if co_epoch:
            tk.co_epoch_luu_san += 1
        co_nguon = bool(entry.get("publication_date_source")) or _da_chac_chan(entry)
        if co_nguon:
            tk.co_provenance += 1

        ngay_luu = ngay_tu_chuoi(entry.get("publication_date") or entry.get("upload_date"))
        if ngay_luu is None:
            tk.thieu_ngay += 1
            continue
        if not co_epoch and not co_nguon:
            tk.chi_upload_date += 1

        ket_qua = resolve_publication_date(entry, mui_gio)
        if ket_qua.date and ket_qua.date != ngay_luu:
            tk.se_doi.append((ten, ngay_luu, ket_qua.date, ket_qua.source_field))

        ngay_ten_file = ngay_tu_chuoi(str(filename_fallback_parts(ten).get("upload_date") or ""))
        if ngay_ten_file and ngay_ten_file != ngay_luu:
            tk.can_xem_lai.append((ten, "ngày trong tên file khác ngày metadata"))

    return tk


def in_audit(kho: str, tk: ThongKe, mui_gio: str) -> None:
    print(f"Kho:                          {kho}")
    print(f"Múi giờ hiển thị:             {mui_gio}")
    print(f"Tổng clip:                    {tk.tong}")
    print(f"Đã có nguồn gốc ngày:         {tk.co_provenance}")
    print(f"Chỉ có upload_date (cũ):      {tk.chi_upload_date}")
    print(f"Có epoch lưu sẵn:             {tk.co_epoch_luu_san}")
    print(f"Thiếu ngày:                   {tk.thieu_ngay}")
    print(f"Sẽ đổi nếu repair:            {len(tk.se_doi)}")
    print(f"Cần xem lại:                  {len(tk.can_xem_lai)}")
    print(f"Mơ hồ:                        {len(tk.mo_ho)}")

    if tk.se_doi:
        print("\nVí dụ record sẽ đổi:")
        for ten, cu, moi, nguon in tk.se_doi[:10]:
            print(f"  {format_publication_date(cu)} -> {format_publication_date(moi)}"
                  f"  [{nguon}]  {ten[:58]}")

    if tk.chi_upload_date:
        print(
            f"\nLƯU Ý: {tk.chi_upload_date} clip chỉ có upload_date (không có giờ) nên "
            "KHÔNG thể biết ngày giờ Việt Nam có lệch hay không nếu chỉ dùng dữ liệu "
            "đã lưu. Muốn chắc chắn phải chạy --repair-network."
        )


def _cau_hinh_mang_mac_dinh():
    """Cookie + nhịp tải người dùng đã đặt trong ``data/cau_hinh.json`` (CLAUDE.md mục 9: tham
    số mạng có giá trị mặc định là bẫy — thiếu thì lặng lẽ mất cookie và mất nhịp)."""
    from engine import thu_muc_data_mac_dinh
    from ytdlp_chung import CauHinhMang

    return CauHinhMang.tu_file_cau_hinh(thu_muc_data_mac_dinh())


def repair(
    kho: str,
    mui_gio: str,
    dung_mang: bool,
    apply: bool,
    gioi_han: int,
    fetcher=None,
    nghi_giay: float = 0.0,
    progress=None,
    dung_sau_n_loi: int = 25,
) -> dict:
    """Sửa ngày đăng. ``nghi_giay`` giãn nhịp gọi mạng để tránh bị chặn bot.

    ``dung_sau_n_loi``: gặp bấy nhiêu lỗi LIÊN TIẾP thì dừng sớm. YouTube chặn
    chống bot sẽ làm mọi request sau đó đều hỏng; cố chạy tiếp chỉ tốn thời gian
    và khiến bị chặn nặng hơn. Entry lỗi không bị ghi gì nên lần chạy sau tiếp
    tục được từ chỗ dở.
    """
    cs, meta = _doc_meta(kho, chi_doc=not apply)
    # Một lượt sửa = một phiên YouTube: bị nghi là bot/429 ở clip đầu thì dừng NGAY — trước đây
    # phải đợi đủ ``dung_sau_n_loi`` (25) request hỏng liên tiếp mới dừng.
    phien = PhienYouTube()
    api: dict = {}      # mã -> dict chuẩn YouTube Data API (D-51); fetcher tiêm vào (test) thì không bao giờ gọi API
    if fetcher is None:
        cau_hinh = _cau_hinh_mang_mac_dinh()

        def fetcher(video_id: str) -> dict:
            return ChannelSync.lay_info_video(video_id, cau_hinh.network_timeout_s,
                                              cau_hinh_mang=cau_hinh, phien_youtube=phien)

        if dung_mang:
            from engine import thu_muc_data_mac_dinh

            # Một yêu cầu API cho 50 mã. --limit đếm cả mục không cần hỏi, nên cắt theo nó chỉ có thể hỏi THỪA vài mã.
            ma = [_ma_video(ten, e) for ten, e in meta.items() if isinstance(e, dict) and not _da_chac_chan(e)]
            ma = [m for m in ma if m]
            api = youtube_api.lay_video(phien, thu_muc_data_mac_dinh(),
                                        ma[:max(gioi_han, 0)] if gioi_han else ma).thong_tin

    khong_doi = da_doi = bo_qua = that_bai = 0
    loi_lien_tiep = 0
    dung_som = False
    loi: list[str] = []
    thay_doi: list[tuple] = []
    # Trường đã sửa của từng entry — khi ghi chỉ gộp đúng những trường này vào bản
    # clips_meta.json MỚI NHẤT, không ghi đè cả file bằng bản đọc từ đầu lượt.
    cap_nhat: dict[str, dict] = {}
    da_xu_ly = 0

    for ten, entry in list(meta.items()):
        if gioi_han and da_xu_ly >= gioi_han:
            break
        if not isinstance(entry, dict):
            bo_qua += 1
            continue

        nguon_du_lieu = dict(entry)
        tu_youtube = False      # True khi nguon_du_lieu là info vừa hỏi lại YouTube (yt-dlp hoặc Data API)
        video = None            # dict chuẩn YouTube Data API của mục này (đã lấy theo lô ở trên)
        # Chỉ bỏ qua khi đã có nguồn ĐỘ TIN CẬY CAO (suy từ epoch / published_at). Nếu chỉ dựa
        # trên upload_date thì vẫn phải hỏi lại: chuỗi YYYYMMDD không có giờ nên
        # không thể biết ngày giờ Việt Nam có lệch hay không. Nếu không, một lượt
        # repair offline chạy trước sẽ vô tình khoá luôn những entry cần sửa nhất.
        da_chac_chan = _da_chac_chan(entry)
        if dung_mang and not da_chac_chan:
            video_id = _ma_video(ten, entry)
            if not video_id:
                bo_qua += 1
                continue
            video = api.get(video_id)
            if video is None and phien.mo:
                dung_som = True
                break
            da_xu_ly += 1
            if video is None and nghi_giay > 0 and da_xu_ly > 1:
                time.sleep(nghi_giay)
            if progress:
                progress(da_xu_ly, ten)
            if video is not None:
                nguon_du_lieu = info_tu_api(video)      # đã có từ API: không hỏi yt-dlp, không nghỉ
            else:
                try:
                    nguon_du_lieu = fetcher(video_id)
                except Exception as e:  # noqa: BLE001
                    that_bai += 1
                    loi_lien_tiep += 1
                    phien.ghi_loi(e, "metadata", video_id)
                    loi.append(f"{ten}: {type(e).__name__}: {che_bi_mat(str(e))[:160]}")
                    if loi_lien_tiep >= dung_sau_n_loi:
                        dung_som = True
                        break
                    continue
                phien.ghi_thanh_cong("metadata")
                loi_lien_tiep = 0
            tu_youtube = True
        else:
            da_xu_ly += 1

        ket_qua = resolve_publication_date(nguon_du_lieu, mui_gio)
        if ket_qua.date is None:
            bo_qua += 1
            continue
        if not tu_youtube and ket_qua.source_field not in TRUONG_DO_TIN_CAY_CAO:
            # Dữ liệu ĐÃ LƯU không có epoch: chuỗi YYYYMMDD trong kho không rõ gốc
            # (va_metadata/seed tên file ghi ngày ĐÃ quy đổi), nên không được đóng dấu
            # nguồn ``upload_date`` — báo cáo V2 coi dấu đó là upload_date NGUYÊN BẢN
            # của yt-dlp (audit A-2). Offline không sửa được entry này: cần --repair-network.
            bo_qua += 1
            continue

        ngay_cu = ngay_tu_chuoi(entry.get("publication_date") or entry.get("upload_date"))
        if ngay_cu == ket_qua.date and da_chac_chan:
            khong_doi += 1
            continue

        # Nguồn API: nhãn riêng — không gắn timestamp/upload_date (nghĩa «trường của yt-dlp»), không lưu epoch (D-51).
        nguon_ngay = "published_at" if video is not None else ket_qua.source_field
        if ngay_cu != ket_qua.date:
            thay_doi.append((ten, ngay_cu, ket_qua.date, nguon_ngay))
            da_doi += 1
        else:
            khong_doi += 1

        truong = {
            "publication_date": ket_qua.yyyymmdd,
            "publication_date_source": nguon_ngay or "",
            "upload_date": ket_qua.yyyymmdd,     # tương thích bản đọc cũ
        }
        if video is not None:
            truong.update(truong_ngay_tu_api(entry, ket_qua.yyyymmdd), published_at=video["published_at"])
        for k in ("timestamp", "release_timestamp"):
            if video is None and isinstance(nguon_du_lieu.get(k), (int, float)) and nguon_du_lieu.get(k):
                truong[k] = nguon_du_lieu[k]
        # Ngày NGUYÊN BẢN của yt-dlp (cột ngày báo cáo V2): chỉ khi vừa hỏi YouTube — ``upload_date`` đã lưu là ngày đã quy đổi.
        if tu_youtube and valid_upload_date(str(nguon_du_lieu.get("upload_date") or "")):
            truong["upload_date_raw"] = valid_upload_date(str(nguon_du_lieu["upload_date"]))
        cap_nhat[ten] = truong

    if apply and cap_nhat:
        goc = os.path.join(kho, "clips_meta.json")
        doi_ma: set[str] = set()

        def gop(du_lieu: dict) -> None:
            # Sao lưu ĐÚNG bản sắp bị sửa, trong lúc đang giữ khoá.
            if os.path.isfile(goc):
                bk = f"{goc}.truoc_ngay_dang_{time.strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(goc, bk)
                print(f"Đã sao lưu -> {bk}")
            for ten_entry, cac_truong in cap_nhat.items():
                # Entry bị writer khác xoá giữa chừng thì không hồi sinh nó.
                hien_tai = du_lieu.get(ten_entry)
                if not isinstance(hien_tai, dict):
                    continue
                if _ma_video(ten_entry, hien_tai) != _ma_video(ten_entry, meta[ten_entry]):
                    doi_ma.add(ten_entry)
                    continue
                hien_tai.update(cac_truong)

        cap_nhat_json(goc, gop, mac_dinh={})
        if doi_ma:
            ten_doi_ngay = {muc[0] for muc in thay_doi}
            da_doi -= len(doi_ma & ten_doi_ngay)
            khong_doi -= len(doi_ma - ten_doi_ngay)
            bo_qua += len(doi_ma)
            thay_doi = [muc for muc in thay_doi if muc[0] not in doi_ma]

    return {
        "khong_doi": khong_doi,
        "da_doi": da_doi,
        "bo_qua": bo_qua,
        "that_bai": that_bai,
        "loi": loi,
        "thay_doi": thay_doi,
        "da_ghi": bool(apply),
        "dung_som": dung_som,
        "con_lai": max(0, len(meta) - da_xu_ly),
        "chan_youtube": phien.thong_bao_dung(),
        "youtube": phien.tom_tat(),
    }


def main() -> int:
    try:
        return _main()
    except LoiDuLieu as e:
        print(f"LỖI DỮ LIỆU: {e}", file=sys.stderr)
        return 1


def _main() -> int:
    p = argparse.ArgumentParser(
        description="Audit/sửa ngày đăng trong clips_meta.json (mặc định chỉ đọc)."
    )
    p.add_argument("--kho", required=True, help="Thư mục kho clip gốc.")
    p.add_argument("--mui-gio", default=MUI_GIO_MAC_DINH)
    p.add_argument("--audit", action="store_true", help="Chỉ thống kê, không ghi.")
    p.add_argument("--repair-offline", action="store_true",
                   help="Chỉ dùng dữ liệu đã lưu, không gọi mạng.")
    p.add_argument("--repair-network", action="store_true",
                   help="Hỏi lại YouTube cho clip chưa có nguồn gốc ngày.")
    p.add_argument("--apply", action="store_true",
                   help="Thực sự ghi. Thiếu cờ này là dry-run.")
    p.add_argument("--limit", type=int, default=0, help="Chỉ xử lý N clip đầu (0 = tất cả).")
    p.add_argument("--nghi", type=float, default=1.5,
                   help="Giây nghỉ giữa hai lần gọi mạng. Quá nhanh sẽ bị YouTube "
                        "chặn chống bot. Mặc định 1.5.")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    if not os.path.isdir(a.kho):
        p.error(f"Không thấy thư mục kho: {a.kho}")
    if a.repair_offline and a.repair_network:
        p.error("Chọn một trong --repair-offline hoặc --repair-network.")
    if a.apply and not (a.repair_offline or a.repair_network):
        p.error("--apply chỉ hợp lệ cùng một chế độ repair.")
    if not (a.audit or a.repair_offline or a.repair_network):
        a.audit = True

    if a.audit:
        tk = audit(a.kho, a.mui_gio)
        if a.json:
            print(json.dumps({
                "tong": tk.tong, "co_provenance": tk.co_provenance,
                "chi_upload_date": tk.chi_upload_date,
                "co_epoch_luu_san": tk.co_epoch_luu_san,
                "thieu_ngay": tk.thieu_ngay, "se_doi": len(tk.se_doi),
                "can_xem_lai": len(tk.can_xem_lai), "mo_ho": len(tk.mo_ho),
            }, ensure_ascii=False, indent=2))
        else:
            in_audit(a.kho, tk, a.mui_gio)
        return 0

    che_do = "APPLY" if a.apply else "DRY-RUN"
    mang = "CÓ gọi mạng" if a.repair_network else "KHÔNG gọi mạng"
    print(f"Chế độ: {che_do} | {mang} | kho: {a.kho}")

    def bao(so, ten):
        if so % 25 == 0 or so == 1:
            print(f"  [{so}] {ten[:60]}", flush=True)

    kq = repair(
        a.kho, a.mui_gio, a.repair_network, a.apply, a.limit,
        nghi_giay=a.nghi if a.repair_network else 0.0,
        progress=bao if a.repair_network else None,
    )
    print(f"\nKhông đổi:  {kq['khong_doi']}")
    print(f"Sẽ đổi/đã đổi: {kq['da_doi']}")
    print(f"Bỏ qua:     {kq['bo_qua']}")
    print(f"Thất bại:   {kq['that_bai']}")
    print(f"Đã ghi:     {kq['da_ghi']}")
    dong_api = dong_trang_thai_api(kq["youtube"].get("api"))     # rỗng khi lượt không đụng tới API (không có khoá)
    if dong_api:
        print(dong_api)
    if kq.get("chan_youtube"):
        print(f"\nDỪNG SỚM: {kq['chan_youtube']} Còn {kq['con_lai']} clip chưa xử lý; chạy lại "
              "đúng lệnh này sau đó — clip đã sửa sẽ được bỏ qua.")
    elif kq["dung_som"]:
        print(
            f"\nDỪNG SỚM: quá nhiều lỗi liên tiếp — nhiều khả năng YouTube đang chặn "
            f"chống bot. Còn {kq['con_lai']} clip chưa xử lý.\n"
            f"Hãy chờ 30–60 phút rồi chạy lại đúng lệnh này: clip đã sửa sẽ được bỏ "
            f"qua, chạy tiếp từ chỗ dở. Cân nhắc tăng --nghi."
        )
    for ten, cu, moi, nguon in kq["thay_doi"][:15]:
        print(f"  {format_publication_date(cu) or '(trống)'} -> "
              f"{format_publication_date(moi)}  [{nguon}]  {ten[:56]}")
    for e in kq["loi"][:10]:
        print(f"  LỖI: {e}")
    if not a.apply:
        print("\nDry-run: chưa ghi gì. Thêm --apply để thực sự cập nhật.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
