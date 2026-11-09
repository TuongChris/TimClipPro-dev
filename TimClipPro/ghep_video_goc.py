# -*- coding: utf-8 -*-
"""Ghép nhiều video gốc YouTube thành một video dài + file mốc thời gian (D-39).

Dùng để có video dài mà ĐÁP ÁN đã biết: video gốc nào bắt đầu ở giây thứ mấy — đem quét rồi so với file mốc là đo
được tool lệch bao nhiêu giây ở từng chỗ.

* Tải bằng :func:`tai_video_goc.tai_nhieu` (cùng đường mạng/cookie/cầu dao) với :data:`tai_video_goc.DINH_DANG_GHEP`:
  mọi video cùng kiểu H.264 ≤ 1080p + AAC trong MP4, vào thư mục tạm :data:`THU_MUC_PHAN` trong thư mục lưu.
* Nối bằng ``ffmpeg -f concat -c copy`` — KHÔNG nén lại, chất lượng giữ nguyên. Nối thẳng chỉ đúng khi mọi file cùng
  thông số (mã hoá, độ phân giải, số hình/giây, tiếng): lệch thì DỪNG và báo rõ video nào lệch, giữ các file đã tải để
  lần sau khỏi tải lại — không ghép ra file hỏng ở chỗ nối, không tự nén lại hàng giờ.
* Độ dài từng phần ghi thẳng vào danh sách nối (``duration``) nên mốc trong file CSV và mốc chương trong video khớp
  đúng chỗ FFmpeg đặt từng phần. Ghép xong và độ dài file ra khớp tổng thì mới xoá thư mục tạm.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
from datetime import datetime
from typing import Callable, Optional

import tai_video_goc as tv
from channel import _CoHuyTuHam
from kiem_thoi_luong import hhmmss
from process_runner import IM_LANG_FFMPEG_S, TRAN_FFPROBE_S, chay_lenh_media
from ytdlp_chung import CauHinhMang

THU_MUC_PHAN = ".timclip_ghep"
# Thông số phải TRÙNG giữa các phần để nối bằng -c copy (tên hiển thị cho câu báo lệch).
THONG_SO = {
    "ma_hinh": "mã hoá hình",
    "profile": "profile H.264",
    "do_phan_giai": "độ phân giải",
    "hinh_giay": "số hình/giây",
    "pix_fmt": "kiểu điểm ảnh",
    "ma_tieng": "mã hoá tiếng",
    "tan_so_tieng": "tần số tiếng",
    "kenh_tieng": "số kênh tiếng",
}
# File ra lệch tổng độ dài các phần quá mức này thì không tin mốc — giữ file tạm, báo.
LECH_DO_DAI_TOI_DA_S = 1.0
_DU_PHONG_O_DIA = 10**9
_KY_TU_CAM = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def tach_link(van_ban: str) -> list:
    """Mỗi dòng một link, GIỮ thứ tự và link lặp lại (khác :func:`tai_video_goc.tach_link`): lặp = video xuất hiện lặp."""
    return [d.strip() for d in str(van_ban or "").splitlines() if d.strip()]


def thong_so(path: str) -> dict:
    """Thông số cần trùng để nối + ``do_dai`` (giây, của format — đúng độ dài FFmpeg dùng khi nối)."""
    r = chay_lenh_media(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            path,
        ],
        tran_tong_s=TRAN_FFPROBE_S,
    )
    if r.returncode != 0 or r.timed_out:
        raise RuntimeError(
            f"Không đọc được thông số file «{os.path.basename(path)}» bằng ffprobe."
        )
    d = json.loads(r.stdout or "{}")
    hinh = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    tieng = next(
        (s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {}
    )
    do_dai = float((d.get("format") or {}).get("duration") or 0)
    if not hinh or not tieng or do_dai <= 0:
        raise RuntimeError(
            f"File «{os.path.basename(path)}» thiếu hình, thiếu tiếng hoặc không đo được độ dài."
        )
    return {
        "ma_hinh": hinh.get("codec_name"),
        "profile": hinh.get("profile"),
        "do_phan_giai": f"{hinh.get('width')}x{hinh.get('height')}",
        "hinh_giay": hinh.get("r_frame_rate"),
        "pix_fmt": hinh.get("pix_fmt"),
        "ma_tieng": tieng.get("codec_name"),
        "tan_so_tieng": tieng.get("sample_rate"),
        "kenh_tieng": tieng.get("channels"),
        "do_dai": do_dai,
    }


def cac_cho_lech(ts: list) -> list:
    """Câu báo cho từng phần lệch phần đầu tiên (rỗng = nối thẳng được). ``ts``: list (tiêu đề, thông số)."""
    if not ts:
        return []
    _, chuan = ts[0]
    bao = []
    for i, (ten, t) in enumerate(ts[1:], start=2):
        khac = [
            f"{nhan} {t[k]} (video 1: {chuan[k]})"
            for k, nhan in THONG_SO.items()
            if t[k] != chuan[k]
        ]
        if khac:
            bao.append(f"Video {i} «{ten}»: " + "; ".join(khac))
    return bao


def _nhay_concat(path: str) -> str:
    return "'" + path.replace("\\", "/").replace("'", "'\\''") + "'"


def _thoat_meta(s: str) -> str:
    return re.sub(r"([=;#\\\n])", r"\\\1", s)


def danh_sach_noi(phan: list) -> str:
    """Nội dung file danh sách cho ``-f concat``; ``phan``: list (đường dẫn, độ dài giây)."""
    return "ffconcat version 1.0\n" + "".join(
        f"file {_nhay_concat(p)}\nduration {d:.6f}\n" for p, d in phan
    )


def moc_thoi_gian(phan: list) -> list:
    """``phan``: list (tiêu đề, link, độ dài). Trả list dict mốc: bắt đầu/kết thúc (giây) của từng video trong video ghép."""
    dong, t = [], 0.0
    for i, (ten, link, do_dai) in enumerate(phan, start=1):
        dong.append(
            {
                "STT": i,
                "Tiêu đề": ten,
                "Link": link,
                "Bắt đầu (giây)": round(t, 3),
                "Kết thúc (giây)": round(t + do_dai, 3),
                "Bắt đầu": hhmmss(t),
                "Thời lượng": hhmmss(do_dai),
            }
        )
        t += do_dai
    return dong


def chuong_ffmetadata(dong: list) -> str:
    """Mốc chương (ffmetadata) — trình phát (VLC, Phim & TV) hiện tên từng video gốc trên thanh thời gian."""
    ra = [";FFMETADATA1"]
    for d in dong:
        ra += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={round(d['Bắt đầu (giây)'] * 1000)}",
            f"END={round(d['Kết thúc (giây)'] * 1000)}",
            f"title={_thoat_meta(d['Tiêu đề'])}",
        ]
    return "\n".join(ra) + "\n"


def csv_moc(dong: list) -> bytes:
    from engine import o_bang_tinh_an_toan  # engine nặng: chỉ nạp khi xuất file

    buf = io.StringIO()
    w = csv.writer(buf)
    cot = list(dong[0]) if dong else []
    w.writerow(cot)
    w.writerows([o_bang_tinh_an_toan(d[c]) for c in cot] for d in dong)
    return buf.getvalue().encode("utf-8-sig")


def ten_file_ra(ten: str) -> str:
    """Tên file video ghép (không đuôi) an toàn cho Windows; rỗng → «Video ghép <ngày giờ>»."""
    ten = _KY_TU_CAM.sub("_", str(ten or "")).strip(" .")
    return ten[:150] or datetime.now().strftime("Video ghép %Y-%m-%d %H%M%S")


def _ten_tu_file(path: str) -> str:
    return re.sub(r"\s*\[[A-Za-z0-9_-]{11}\]\.[^.]+$", "", os.path.basename(path))


def ghep(
    links: list,
    thu_muc: str,
    cau_hinh_mang: Optional[CauHinhMang] = None,
    *,
    ten_file: str = "",
    progress: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    **kw,
) -> list:
    """Tải ``links`` (theo đúng thứ tự, link lặp lại thì video xuất hiện lặp lại) rồi ghép thành MỘT video MP4 trong
    ``thu_muc`` + file mốc ``<tên>.moc.csv``. Trả list dict như :func:`tai_video_goc.tai_nhieu` (một dòng mỗi link) và
    một dòng cuối cho video ghép. ``kw`` chuyển cho ``tai_nhieu`` (player_clients, phien…)."""
    bao = progress or (lambda _p, _m: None)
    huy = cancel_check or (lambda: False)
    thu_muc = os.path.abspath(str(thu_muc or "").strip().strip('"'))
    tam = os.path.join(thu_muc, THU_MUC_PHAN)
    ket_qua = tv.tai_nhieu(
        list(links),
        tam,
        cau_hinh_mang,
        progress=lambda p, m: bao(0.8 * p, m),
        cancel_check=huy,
        bo_qua_da_co=True,
        dinh_dang=tv.DINH_DANG_GHEP,
        **kw,
    )
    dong_ghep = {
        "url": "🎞️ Video ghép",
        "trang_thai": "loi",
        "duong_dan": "",
        "tieu_de": "",
        "chat_luong": "",
        "ghi_chu": "",
    }
    ket_qua.append(dong_ghep)

    def that_bai(ly_do: str) -> list:
        dong_ghep["ghi_chu"] = (
            ly_do
            + f" Các video đã tải vẫn giữ ở «{tam}» — bấm lại thì không phải tải lại."
        )
        return ket_qua

    # Đường dẫn từng link theo đúng thứ tự: tải mới → đường dẫn tải; «đã có»/«trùng» → file «[mã].mp4» trong thư mục tạm.
    co_san = {}
    for f in os.listdir(tam) if os.path.isdir(tam) else []:
        m = tv._RE_MA_CUOI_TEN.search(f)
        if m:
            co_san.setdefault(m.group(1), os.path.join(tam, f))
    phan, ten_theo_ma = [], {}
    for k in ket_qua[:-1]:
        ma = tv.ma_tu_url(k["url"]) or ""
        duong = k["duong_dan"] if k["trang_thai"] == "xong" else co_san.get(ma)
        if k["trang_thai"] == "loi" or not duong or not os.path.isfile(duong):
            return that_bai("Chưa ghép: có video chưa tải được (xem các dòng ở trên).")
        # Link lặp lại: lượt tải báo «trùng», không trả tiêu đề — dùng tiêu đề của lần đầu.
        ten = ten_theo_ma.setdefault(ma, k["tieu_de"] or _ten_tu_file(duong))
        phan.append((ten, k["url"], duong))
    if huy():
        return that_bai("Đã dừng theo yêu cầu trước khi ghép.")

    bao(0.82, "Đang kiểm thông số các video...")
    try:
        ts = [(ten, thong_so(duong)) for ten, _l, duong in phan]
    except RuntimeError as e:
        return that_bai(f"Chưa ghép: {e}")
    lech = cac_cho_lech(ts)
    if lech:
        return that_bai(
            "Chưa ghép: các video khác thông số nên không nối thẳng được (nối vẫn ra file nhưng hỏng ở chỗ "
            "nối). Bỏ các video lệch khỏi danh sách rồi ghép lại. "
            + " | ".join(lech)
            + "."
        )
    tong = sum(t["do_dai"] for _, t in ts)
    can = sum(os.path.getsize(d) for *_x, d in phan) + _DU_PHONG_O_DIA
    if shutil.disk_usage(thu_muc).free < can:
        return that_bai(f"Chưa ghép: ổ đĩa cần còn trống khoảng {can / 1e9:,.1f} GB.")

    dong = moc_thoi_gian(
        [(ten, link, t["do_dai"]) for (ten, link, _d), (_t, t) in zip(phan, ts)]
    )
    ten = ten_file_ra(ten_file)
    dich = tv._ten_trong(thu_muc, f"{ten}.mp4")
    dang_ghi = os.path.join(tam, "dang_ghep.mp4")
    ds_noi, meta = (
        os.path.join(tam, "danh_sach_noi.txt"),
        os.path.join(tam, "chuong.txt"),
    )
    with open(ds_noi, "w", encoding="utf-8", newline="\n") as f:
        f.write(
            danh_sach_noi([(d, t["do_dai"]) for (_a, _b, d), (_t, t) in zip(phan, ts)])
        )
    with open(meta, "w", encoding="utf-8", newline="\n") as f:
        f.write(chuong_ffmetadata(dong))

    def tien_do(d: dict) -> None:
        giay_ra = int(d.get("out_time_us") or d.get("out_time_ms") or 0) / 1e6
        bao(
            min(0.85 + 0.15 * giay_ra / tong, 0.99),
            f"Đang ghép: {hhmmss(giay_ra)} / {hhmmss(tong)}",
        )

    r = chay_lenh_media(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            ds_noi,
            "-i",
            meta,
            "-map",
            "0",
            "-map_metadata",
            "1",
            "-map_chapters",
            "1",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
            dang_ghi,
        ],
        cancel_event=_CoHuyTuHam(huy),
        im_lang_toi_da_s=IM_LANG_FFMPEG_S,
        theo_doi_tien_do=True,
        khi_tien_do=tien_do,
    )
    if r.cancelled or r.returncode != 0 or not os.path.isfile(dang_ghi):
        if os.path.exists(dang_ghi):
            os.remove(dang_ghi)
        if r.cancelled:
            return that_bai("Đã dừng theo yêu cầu trong lúc ghép; phần ghép dở đã xoá.")
        return that_bai(
            f"FFmpeg ghép lỗi: {(r.stderr or r.ly_do or '').strip()[-300:]}"
        )
    os.replace(dang_ghi, dich)
    duong_moc = os.path.splitext(dich)[0] + ".moc.csv"
    with open(duong_moc, "wb") as f:
        f.write(csv_moc(dong))

    do_dai_ra = thong_so(dich)["do_dai"]
    t0 = ts[0][1]
    dong_ghep.update(
        trang_thai="xong",
        duong_dan=dich,
        tieu_de=f"Video ghép {len(phan)} video — {hhmmss(do_dai_ra)}",
        chat_luong=f"{t0['do_phan_giai']} {t0['ma_hinh']} {t0['hinh_giay']} hình/giây, không nén lại",
        ghi_chu=f"Mốc thời gian từng video gốc: {duong_moc}",
    )
    if abs(do_dai_ra - tong) > LECH_DO_DAI_TOI_DA_S:
        dong_ghep["ghi_chu"] += (
            f" — CẢNH BÁO: video ghép dài {do_dai_ra:.2f} s, tổng các phần {tong:.2f} s; mốc có thể "
            f"lệch. Giữ các video đã tải ở «{tam}»."
        )
    else:
        shutil.rmtree(tam, ignore_errors=True)
    bao(1.0, "Xong.")
    return ket_qua
