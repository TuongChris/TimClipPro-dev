# -*- coding: utf-8 -*-
"""Cắt đoạn / chỉnh âm lượng / chụp ảnh / tạo file kiểm claim cho video ĐÃ CÓ trong máy (D-46, người dùng yêu cầu 11/11;
chụp ảnh 18/11; file kiểm claim D-64, 23/11).

Dùng lại đúng phần cắt (:func:`cat_video_goc.cat_mot`, cắt chính xác từng khung hình + kiểm độ dài) và phần chỉnh âm
lượng (:func:`am_luong.chuan_hoa`, mức YouTube -14 LUFS) của luồng tải theo link. Bất biến: file GỐC không bao giờ bị sửa,
đổi tên hay xoá — mọi kết quả ra file MỚI trong thư mục lưu (trùng tên thì thêm «_2»). Ghép file trong máy: tab
«🎞️ Ghép video gốc» nhận cả đường dẫn file (:func:`ghep_video_goc.ghep`).
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import am_luong
import cat_video_goc as cv
import tai_video_goc as tv
from kiem_thoi_luong import hhmmss

# Như engine.MEDIA_EXTS (không import engine: module này chỉ cần FFmpeg).
DUOI_MEDIA = (
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".ts",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".mp3",
    ".m4a",
    ".aac",
    ".wav",
    ".ogg",
    ".opus",
    ".flac",
)


def tach_file(van_ban: str) -> tuple:
    """Mỗi dòng một FILE hoặc THƯ MỤC (lấy các file media ngay trong thư mục, theo tên — không vào thư mục con: kết quả
    lưu vào thư mục con thì bấm lại không xử lý lại). Trả ``(danh sách file, danh sách câu lỗi)``; bỏ dòng trống/trùng."""
    files: list = []
    loi: list = []
    for dong in (van_ban or "").splitlines():
        d = dong.strip().strip('"').strip()
        if not d:
            continue
        if os.path.isdir(d):
            moi = sorted(
                (
                    os.path.join(d, f)
                    for f in os.listdir(d)
                    if f.lower().endswith(DUOI_MEDIA)
                    and os.path.isfile(os.path.join(d, f))
                ),
                key=lambda x: os.path.basename(x).lower(),
            )
            if not moi:
                loi.append(f"Thư mục không có video/tiếng nào: {d}")
        elif os.path.isfile(d):
            if not d.lower().endswith(DUOI_MEDIA):
                loi.append(f"File không phải video/tiếng: {d}")
                continue
            moi = [d]
        else:
            loi.append(f"Không tìm thấy file/thư mục: {d}")
            continue
        files.extend(f for f in moi if f not in files)
    return files, loi


# D-64: mức tiếng của file kiểm claim. «goc» = giữ nguyên luồng tiếng (giống từng byte) khi tiếng gốc là AAC — kênh phụ
# «nghe» đúng thứ kênh chính sẽ nghe; tiếng gốc không phải AAC (MP4 cần AAC) thì nén AAC ở mức cao TIENG_KHI_NEN_LAI.
MUC_TIENG_KIEM_CLAIM = {
    "goc": "Giữ nguyên tiếng gốc (đề xuất)",
    "96k": "Nhẹ — AAC 96 kbps (~130 MB / 3 giờ)",
    "48k": "Rất nhẹ — AAC 48 kbps (~68 MB / 3 giờ)",
}
TIENG_KHI_NEN_LAI = "320k"


def tao_file_kiem_claim(
    nguon: str,
    thu_muc: str,
    muc_tieng: str = "goc",
    *,
    huy: Callable[[], bool] = lambda: False,
    bao: Callable[[float, str], None] = lambda _f, _m: None,
    nhan: str = "",
) -> dict:
    """Ghép TIẾNG của ``nguon`` (luồng tiếng đầu tiên) vào khung hình đen 256×144, 1 hình/giây, ra ``<tên>_kiem_claim.mp4``
    trong ``thu_muc`` — file nhẹ để tải lên kênh phụ cho YouTube Checks quét claim về tiếng. Khung đen dài ĐÚNG bằng file
    gốc (``-shortest`` thừa 5–10 giây), độ trễ của luồng tiếng giữ nguyên nên mốc claim khớp bản gốc. ``nguon`` KHÔNG bị
    sửa/xoá. Trả ``{trang_thai, duong_dan, ghi_chu}``."""
    if muc_tieng not in MUC_TIENG_KIEM_CLAIM:
        raise ValueError(f"Mức tiếng không hợp lệ: {muc_tieng!r}.")
    try:
        d = am_luong.doc_ffprobe(nguon)
    except RuntimeError as e:
        return {"trang_thai": "loi", "duong_dan": "", "ghi_chu": str(e)}
    tieng = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    do_dai = float((d.get("format") or {}).get("duration") or 0)
    if tieng is None:
        return {"trang_thai": "loi", "duong_dan": "", "ghi_chu": "File không có tiếng — không tạo được file kiểm claim."}
    if do_dai <= 0:
        return {"trang_thai": "loi", "duong_dan": "", "ghi_chu": "Không đo được độ dài file."}
    ma_goc = tieng.get("codec_name") or "?"
    giu_nguyen = muc_tieng == "goc" and ma_goc == "aac"
    muc = TIENG_KHI_NEN_LAI if muc_tieng == "goc" else muc_tieng
    goc = tv.ten_khong_dau(os.path.splitext(os.path.basename(nguon))[0]) or "video"
    os.makedirs(thu_muc, exist_ok=True)
    dich = tv._ten_trong(thu_muc, f"{goc}_kiem_claim.mp4")
    dang = dich + ".dang.mp4"
    nhan = f"{nhan}: đang tạo file kiểm claim" if nhan else "Đang tạo file kiểm claim"

    def tien_do(p: dict) -> None:
        giay = int(p.get("out_time_us") or p.get("out_time_ms") or 0) / 1e6
        bao(min(giay / do_dai, 1.0), f"{nhan} ({hhmmss(giay)})")

    bao(0.0, nhan + "...")
    r = cv._chay_ra_file(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", f"color=c=black:s=256x144:r=1:d={do_dai:.3f}", "-i", nguon,
         "-map", "0:v", "-map", "1:a:0",
         "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         *(["-c:a", "copy"] if giu_nguyen else ["-c:a", "aac", "-b:a", muc]), "-sn", "-dn", dang],
        dang,
        dich,
        huy=huy,
        khi_tien_do=tien_do,
    )
    if r.cancelled:
        return {"trang_thai": "bo_qua", "duong_dan": "", "ghi_chu": "Đã dừng theo yêu cầu; file gốc giữ nguyên."}
    if r.returncode != 0 or not os.path.isfile(dich):
        return {"trang_thai": "loi", "duong_dan": "",
                "ghi_chu": f"Không tạo được file kiểm claim: {r.mo_ta_loi()}"}
    if giu_nguyen:
        cach = "tiếng giữ nguyên (không nén lại)"
    elif muc_tieng == "goc":
        cach = f"tiếng gốc là {ma_goc}, MP4 cần AAC nên đã nén AAC {muc}"
    else:
        cach = f"tiếng nén AAC {muc}"
    return {
        "trang_thai": "xong",
        "duong_dan": dich,
        "ghi_chu": f"File kiểm claim {os.path.getsize(dich) / 1e6:.1f} MB, dài {hhmmss(do_dai)}: khung đen 256×144, "
                   f"1 hình/giây, {cach}. Chỉ kiểm được claim về TIẾNG, không kiểm được claim về hình.",
    }


def xu_ly(
    files: list,
    thu_muc: str,
    _cau_hinh_mang=None,
    *,
    tu_s: Optional[float] = None,
    den_s: Optional[float] = None,
    ds_bo: Optional[list] = None,
    ds_moc: Optional[list] = None,
    chuan_hoa_am: bool = False,
    kiem_claim: Optional[str] = None,
    progress: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    **_kw,
) -> list:
    """Cắt đoạn [``tu_s``, ``den_s``) — hoặc bỏ các đoạn ``ds_bo`` rồi nối phần còn lại — và/hoặc chỉnh âm lượng từng file
    vào ``thu_muc`` — hoặc chụp ảnh ở các mốc ``ds_moc`` (bỏ qua ``chuan_hoa_am``) — hoặc tạo file kiểm claim với mức tiếng
    ``kiem_claim`` (:func:`tao_file_kiem_claim`, bỏ qua ``chuan_hoa_am``: tiếng phải giống bản đăng thật). Trả list dict như
    :func:`tai_video_goc.tai_nhieu` (thêm ``la_file_may``). Tham số thứ ba + ``_kw`` (mạng, phiên…) bỏ qua: không dùng
    mạng."""
    if tu_s is None and not ds_bo and not ds_moc and not chuan_hoa_am and not kiem_claim:
        raise ValueError(
            "Chọn ít nhất một việc: cắt đoạn («Từ»/«Đến»), bỏ các đoạn, chụp ảnh, chỉnh âm lượng hoặc tạo file kiểm claim."
        )
    if kiem_claim and (tu_s is not None or ds_bo or ds_moc):
        raise ValueError("Chỉ chọn một việc: tạo file kiểm claim, hoặc cắt / bỏ đoạn / chụp ảnh.")
    if ds_moc and (tu_s is not None or ds_bo):
        raise ValueError("Chỉ chọn một việc: cắt một đoạn, bỏ các đoạn hoặc chụp ảnh.")
    if ds_bo and tu_s is not None:
        raise ValueError("Chỉ chọn một việc: cắt lấy một đoạn («Từ»/«Đến») hoặc bỏ các đoạn.")
    if tu_s is not None and not (den_s is not None and 0 <= tu_s < den_s):
        raise ValueError("Mốc «Đến» phải sau mốc «Từ» (và «Từ» không âm).")
    bao = progress or (lambda _p, _m: None)
    huy = cancel_check or (lambda: False)
    thu_muc = os.path.abspath(str(thu_muc or "").strip().strip('"'))
    n = len(files)
    ket_qua: list = []
    for i, f in enumerate(files):
        goc, duoi = os.path.splitext(os.path.basename(f))
        k = {
            "url": f,
            "trang_thai": "loi",
            "duong_dan": "",
            "tieu_de": goc,
            "chat_luong": "file trong máy",
            "ghi_chu": "",
            "la_file_may": True,
        }
        ket_qua.append(k)
        if huy():
            k.update(
                trang_thai="bo_qua",
                ghi_chu="Đã dừng theo yêu cầu trước khi xử lý file này.",
            )
            continue
        nhan = f"File {i + 1}/{n}"

        def bao_i(phan: float, cau: str, i=i) -> None:
            bao(min((i + phan) / n, 1.0), cau)

        if kiem_claim:
            k.update(tao_file_kiem_claim(f, thu_muc, kiem_claim, huy=huy, bao=bao_i, nhan=nhan))
            continue
        if ds_moc:
            k.update(cv.chup_anh(f, thu_muc, ds_moc, huy=huy, bao=bao_i, nhan=nhan, giu="File gốc giữ nguyên."))
            continue
        if tu_s is not None or ds_bo:
            k.update(
                cv.cat_hoac_bo(
                    f,
                    thu_muc,
                    tu_s,
                    den_s,
                    ds_bo,
                    chuan_hoa_am=chuan_hoa_am,
                    huy=huy,
                    bao=bao_i,
                    nhan=nhan,
                    giu="File gốc giữ nguyên.",
                )
            )
            continue
        os.makedirs(thu_muc, exist_ok=True)
        dich = tv._ten_trong(thu_muc, f"{tv.ten_khong_dau(goc) or 'video'}_am_luong_YouTube{duoi}")  # tên không dấu cách (12/11)
        bao_i(0.0, f"{nhan}: đang chỉnh âm lượng «{goc}»...")
        try:
            ghi = am_luong.chuan_hoa(f, huy=huy, dich=dich)
        except am_luong.DaHuyChinhAmLuong:
            k.update(
                trang_thai="bo_qua",
                ghi_chu="Đã dừng theo yêu cầu trong lúc chỉnh âm lượng; file gốc giữ nguyên.",
            )
            continue
        except RuntimeError as e:
            k["ghi_chu"] = f"{e} — file gốc giữ nguyên."
            continue
        if os.path.isfile(dich):
            k.update(trang_thai="xong", duong_dan=dich, ghi_chu=ghi)
        else:  # đã ở mức / không có tiếng: không tạo bản sao giống hệt
            k.update(trang_thai="bo_qua", ghi_chu=f"{ghi} Không tạo file mới.")
    bao(1.0, "Xong.")
    return ket_qua
