# -*- coding: utf-8 -*-
"""Ghép nhiều video gốc YouTube thành một video dài + file mốc thời gian (D-39).

Dùng để có video dài mà ĐÁP ÁN đã biết: video gốc nào bắt đầu ở giây thứ mấy — đem quét rồi so với file mốc là đo
được tool lệch bao nhiêu giây ở từng chỗ.

* Tải bằng :func:`tai_video_goc.tai_nhieu` (cùng đường mạng/cookie/cầu dao) với :data:`tai_video_goc.DINH_DANG_GHEP`:
  mọi video cùng kiểu H.264 ≤ 1080p + AAC trong MP4, vào thư mục tạm :data:`THU_MUC_PHAN` trong thư mục lưu.
* Nối bằng ``ffmpeg -f concat -c copy`` — KHÔNG nén lại, chất lượng giữ nguyên. Nối thẳng chỉ đúng khi mọi file cùng
  thông số (mã hoá, độ phân giải, số hình/giây, tiếng). Video lệch video 1 (vd. 60 hình/giây giữa các video 29,97 — người
  dùng chọn 09/11) được nén lại RIÊNG nó cho khớp video 1; tiếng chép nguyên khi đã khớp nên mốc vẫn đúng tiếng thật.
  Chuyển xong vẫn lệch thì DỪNG, báo rõ, giữ các file đã tải — không ghép ra file hỏng ở chỗ nối.
* Độ dài từng phần ghi thẳng vào danh sách nối (``duration``) nên mốc trong file CSV và mốc chương trong video khớp
  đúng chỗ FFmpeg đặt từng phần. Ghép xong và độ dài file ra khớp tổng thì mới xoá thư mục tạm.
* Ghép CHỈ AUDIO (20/11, ``chi_audio``): tải phần tiếng (M4A/AAC) vào :data:`THU_MUC_PHAN_AUDIO`; file trong máy nhận
  mọi file có tiếng (mp3, wav, flac, cả file video — chỉ lấy tiếng). Mọi phần phải là MỘT luồng AAC-LC cùng tần số/số
  kênh với file 1 (:data:`THONG_SO_AUDIO`) — phần lệch, KỂ CẢ file 1 (vd. MP3), được chuyển riêng rồi nối ``-c copy``
  ra một file ``.m4a`` + ``.moc.csv``.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import os
import re
import shutil
from datetime import datetime
from typing import Callable, Optional

import tai_video_goc as tv
from am_luong import DaHuyChinhAmLuong, chuan_hoa, doc_ffprobe
from channel import _CoHuyTuHam
from kiem_thoi_luong import hhmmss
from process_runner import IM_LANG_FFMPEG_S, chay_lenh_media
from ytdlp_chung import CauHinhMang

THU_MUC_PHAN = ".timclip_ghep"
# Ghép chỉ audio: thư mục tạm RIÊNG — ghép audio xong (xoá thư mục tạm) không xoá file lẻ của lượt ghép video còn dở.
THU_MUC_PHAN_AUDIO = ".timclip_ghep_audio"
THU_MUC_KHOP = "khop"  # trong THU_MUC_PHAN: bản đã chuyển cho khớp video 1 (dùng lại khi bấm ghép lại)
THU_MUC_AM = "am"  # trong THU_MUC_PHAN: bản đã chỉnh âm lượng của FILE TRONG MÁY (file gốc không bị sửa — D-46)
# Dòng trông như đường dẫn file Windows («D:\…», «\\máy\…»): không có file thì báo «không tìm thấy», không đem đi tải.
_RE_DUONG_DAN = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


def _dong_file_may(duong: str) -> dict:
    """Dòng kết quả cho một FILE có sẵn trong máy (không tải; ghép xong vẫn giữ nguyên — D-46)."""
    if not os.path.isfile(duong):
        return {"url": duong, "trang_thai": "loi", "duong_dan": "", "tieu_de": "", "chat_luong": "",
                "ghi_chu": f"Không tìm thấy file trong máy: {duong}", "la_file_may": True}
    return {"url": duong, "trang_thai": "xong", "duong_dan": os.path.abspath(duong),
            "tieu_de": os.path.splitext(os.path.basename(duong))[0], "chat_luong": "file trong máy", "ghi_chu": "",
            "la_file_may": True}
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
    # Đo thật (audit tổng 11/11): hai MP4 H.264 2 giây nhịp 1/15360 và 1/90000 nối -c copy ra file 23 giây, mốc hình nhảy.
    "nhip_hinh": "nhịp thời gian hình",
}
_THONG_SO_TIENG = ("ma_tieng", "tan_so_tieng", "kenh_tieng")
# Ghép chỉ audio: concat lấy luồng theo SỐ THỨ TỰ — file video hay MP3 có ảnh bìa đặt tiếng ở luồng 1, nên mỗi phần
# phải chỉ có MỘT luồng tiếng; nhịp thời gian khác nhau nối -c copy cũng lệch mốc như nhịp hình.
THONG_SO_AUDIO = {
    "ma_tieng": "mã hoá tiếng",
    "profile_tieng": "kiểu AAC",
    "tan_so_tieng": "tần số tiếng",
    "kenh_tieng": "số kênh tiếng",
    "nhip_tieng": "nhịp thời gian tiếng",
    "chi_tieng": "chỉ có một luồng tiếng",
}
# File ra lệch tổng độ dài các phần quá mức này thì không tin mốc — giữ file tạm, báo.
LECH_DO_DAI_TOI_DA_S = 1.0
_DU_PHONG_O_DIA = 10**9


def tach_link(van_ban: str) -> list:
    """Mỗi dòng một link, GIỮ thứ tự và link lặp lại (khác :func:`tai_video_goc.tach_link`): lặp = video xuất hiện lặp."""
    return [d.strip().strip('"') for d in str(van_ban or "").splitlines() if d.strip().strip('"')]


def thong_so(path: str) -> dict:
    """Thông số cần trùng để nối + ``do_dai`` (giây, của format — đúng độ dài FFmpeg dùng khi nối)."""
    d = doc_ffprobe(path)
    hinh = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    tieng = next(
        (s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {}
    )
    do_dai = float((d.get("format") or {}).get("duration") or 0)
    tb = str(hinh.get("time_base") or "")
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
        "nhip_hinh": int(tb.split("/")[1]) if re.fullmatch(r"1/\d+", tb) else 0,
    }


def thong_so_audio(path: str) -> dict:
    """Như :func:`thong_so` cho ghép chỉ audio: thông số luồng tiếng ĐẦU TIÊN (:data:`THONG_SO_AUDIO`) + ``do_dai``."""
    d = doc_ffprobe(path)
    luong = d.get("streams", [])
    tieng = next((s for s in luong if s.get("codec_type") == "audio"), {})
    do_dai = float((d.get("format") or {}).get("duration") or 0)
    if not tieng or do_dai <= 0:
        raise RuntimeError(f"File «{os.path.basename(path)}» không có tiếng hoặc không đo được độ dài.")
    return {
        "ma_tieng": tieng.get("codec_name"),
        "profile_tieng": tieng.get("profile"),
        "tan_so_tieng": tieng.get("sample_rate"),
        "kenh_tieng": tieng.get("channels"),
        "nhip_tieng": tieng.get("time_base"),
        "chi_tieng": len(luong) == 1,
        "do_dai": do_dai,
        "bit_rate": int(tieng.get("bit_rate") or 0) if str(tieng.get("bit_rate") or "").isdigit() else 0,
    }


def chuan_audio(t1: dict) -> dict:
    """Đích chung khi ghép chỉ audio: AAC-LC, tần số + số kênh của file 1, một luồng, nhịp = tần số (muxer MP4 tự đặt
    như vậy) — file 1 không phải AAC (MP3, WAV…) cũng được chuyển."""
    return {"ma_tieng": "aac", "profile_tieng": "LC", "tan_so_tieng": t1["tan_so_tieng"],
            "kenh_tieng": t1["kenh_tieng"], "nhip_tieng": f"1/{t1['tan_so_tieng']}", "chi_tieng": True}


def cac_cho_lech(ts: list, chuan: Optional[dict] = None, khoa: dict = THONG_SO, ten_phan: str = "Video") -> list:
    """Câu báo cho từng phần lệch phần đầu tiên (rỗng = nối thẳng được). ``ts``: list (tiêu đề, thông số).
    Có ``chuan`` (ghép chỉ audio): so MỌI phần, kể cả phần 1, với đích đó."""
    if not ts:
        return []
    nhan_chuan = "cần" if chuan is not None else "video 1"
    chuan = chuan if chuan is not None else ts[0][1]
    bao = []
    for i, (ten, t) in enumerate(ts, start=1):
        if i == 1 and nhan_chuan == "video 1":
            continue
        khac = [f"{nhan} {t[k]} ({nhan_chuan}: {chuan[k]})" for k, nhan in khoa.items() if t[k] != chuan[k]]
        if khac:
            bao.append(f"{ten_phan} {i} «{ten}»: " + "; ".join(khac))
    return bao


_PROFILE_X264 = {"High": "high", "Main": "main", "Constrained Baseline": "baseline"}


def _ten_khop(nguon: str, chuan: dict, khoa: dict = THONG_SO, duoi: str = ".mp4") -> str:
    """Tên bản chuyển: theo file nguồn + thông số đích — ghép lại cùng danh sách thì dùng lại, không nén lại lần nữa.
    Đường dẫn ĐẦY ĐỦ + cỡ + giờ sửa (audit 11/11): file trong máy cùng tên khác thư mục, hay sửa file rồi ghép lại, không
    được dùng chung bản chuyển."""
    st = os.stat(nguon)
    khoa_bam = (os.path.normcase(os.path.abspath(nguon)) + f"|{st.st_size}|{st.st_mtime_ns}"
                + json.dumps({k: chuan[k] for k in khoa}, sort_keys=True))
    return hashlib.sha1(khoa_bam.encode("utf-8")).hexdigest()[:16] + duoi


def _chuyen_khop(nguon: str, dich: str, chuan: dict, ts_nguon: dict, *, huy, khi_tien_do):
    """Nén lại hình của ``nguon`` cho trùng ``chuan`` (độ phân giải — thu nhỏ giữ tỉ lệ + viền đen, số hình/giây,
    profile, kiểu điểm ảnh, nhịp thời gian); tiếng chép nguyên nếu đã khớp, không thì đổi sang AAC đúng tần số/số kênh.
    Ghi ra file tạm rồi mới đổi tên — bị Dừng/lỗi không để lại bản dở bị tưởng là xong. Trả kết quả ``chay_lenh_media``."""
    w, h = chuan["do_phan_giai"].split("x")
    tieng_khop = all(ts_nguon[k] == chuan[k] for k in _THONG_SO_TIENG)
    # Hình chỉ lệch nhịp thời gian: chép nguyên hình, muxer đổi nhịp — vài giây thay vì nén lại cả video.
    chi_lech_nhip = all(ts_nguon[k] == chuan[k] for k in THONG_SO if k not in (*_THONG_SO_TIENG, "nhip_hinh"))
    dang = dich + ".dang.mp4"
    lenh = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", nguon, "-map", "0:v:0", "-map", "0:a:0"]
    if chi_lech_nhip:
        lenh += ["-c:v", "copy"]
    else:
        lenh += [
            "-vf", f"fps={chuan['hinh_giay']},scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", chuan["pix_fmt"],
        ]
        if chuan["profile"] in _PROFILE_X264:
            lenh += ["-profile:v", _PROFILE_X264[chuan["profile"]]]
    if chuan.get("nhip_hinh"):
        lenh += ["-video_track_timescale", str(chuan["nhip_hinh"])]
    lenh += (["-c:a", "copy"] if tieng_khop else
             ["-c:a", "aac", "-b:a", "192k", "-ar", str(chuan["tan_so_tieng"]), "-ac", str(chuan["kenh_tieng"])])
    return _chay_chuyen(lenh, dang, dich, huy=huy, khi_tien_do=khi_tien_do)


def _chuyen_audio(nguon: str, dich: str, chuan: dict, ts_nguon: dict, *, huy, khi_tien_do):
    """Ghép chỉ audio: lấy luồng tiếng đầu của ``nguon`` ra M4A đúng ``chuan`` — đã là AAC-LC đúng tần số/số kênh thì
    chép nguyên (chỉ bỏ hình/ảnh bìa, đổi nhịp), không thì đổi sang AAC 192 kbps."""
    giu_ma = all(ts_nguon[k] == chuan[k] for k in ("ma_tieng", "profile_tieng", "tan_so_tieng", "kenh_tieng"))
    dang = dich + ".dang.m4a"
    lenh = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", nguon, "-map", "0:a:0",
            "-map_metadata", "-1", "-map_chapters", "-1"]
    lenh += (["-c:a", "copy"] if giu_ma else
             ["-c:a", "aac", "-b:a", "192k", "-ar", str(chuan["tan_so_tieng"]), "-ac", str(chuan["kenh_tieng"])])
    return _chay_chuyen(lenh, dang, dich, huy=huy, khi_tien_do=khi_tien_do)


def _chay_chuyen(lenh: list, dang: str, dich: str, *, huy, khi_tien_do):
    """Chạy lệnh chuyển ghi ra ``dang`` (MP4) rồi mới đổi tên thành ``dich`` — Dừng/lỗi thì xoá bản dở."""
    lenh = [*lenh, "-movflags", "+faststart", "-f", "mp4", dang]
    r = chay_lenh_media(lenh, cancel_event=_CoHuyTuHam(huy), im_lang_toi_da_s=IM_LANG_FFMPEG_S,
                        theo_doi_tien_do=True, khi_tien_do=khi_tien_do)
    if not r.cancelled and r.returncode == 0 and os.path.isfile(dang):
        os.replace(dang, dich)
    elif os.path.exists(dang):
        os.remove(dang)
    return r


def _nhip_file(ts: list) -> list:
    """``-movie_timescale`` cho track chương QuickTime (xem chỗ gọi): tần số tiếng, trừ khi MỘT phần dài tới mức tràn
    32-bit ở nhịp đó (≈ 13,5 giờ với 44,1 kHz) → 1000 (mốc chương làm tròn 1 ms)."""
    tan_so = str(ts[0][1]["tan_so_tieng"] or "")
    if not tan_so.isdigit():
        return []
    dai_nhat = max(t["do_dai"] for _, t in ts)
    return ["-movie_timescale", tan_so if dai_nhat * int(tan_so) < 2**31 else "1000"]


def _ten_ra(thu_muc: str, ten: str, duoi: str = ".mp4") -> str:
    """Đường dẫn ``<tên>.mp4`` mà CẢ ``.mp4`` lẫn ``.moc.csv`` cùng tên đều chưa có — không ghi đè file đáp án cũ của một
    video đã chuyển đi chỗ khác."""
    goc, i = ten, 2
    while any(os.path.exists(os.path.join(thu_muc, goc + d)) for d in (duoi, ".moc.csv")):
        goc, i = f"{ten}_{i}", i + 1
    return os.path.join(thu_muc, goc + duoi)


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


def ten_file_ra(ten: str, goc: str = "Video_ghep") -> str:
    """Tên file video ghép (không đuôi): không dấu cách/ký tự đặc biệt/dấu tiếng Việt (12/11); rỗng →
    «<goc>_<ngày giờ>» (``goc`` = «Video_ghep» hoặc «Audio_ghep»)."""
    return tv.ten_khong_dau(ten, 150) or datetime.now().strftime(goc + "_%Y-%m-%d_%H%M%S")


def _ten_tu_file(path: str) -> str:
    return re.sub(r"(?:\s*\[[A-Za-z0-9_-]{11}\]|_[A-Za-z0-9_-]{11})\.[^.]+$", "", os.path.basename(path))


def ghep(
    links: list,
    thu_muc: str,
    cau_hinh_mang: Optional[CauHinhMang] = None,
    *,
    ten_file: str = "",
    chuan_hoa_am: bool = False,
    chi_audio: bool = False,
    progress: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    **kw,
) -> list:
    """Tải ``links`` (theo đúng thứ tự, link lặp lại thì video xuất hiện lặp lại) rồi ghép thành MỘT video MP4 trong
    ``thu_muc`` + file mốc ``<tên>.moc.csv``. Trả list dict như :func:`tai_video_goc.tai_nhieu` (một dòng mỗi link) và
    một dòng cuối cho video ghép. ``kw`` chuyển cho ``tai_nhieu`` (player_clients, phien…). ``chi_audio``: chỉ tải/lấy
    phần tiếng, ghép ra một file ``.m4a`` (AAC)."""
    bao = progress or (lambda _p, _m: None)
    huy = cancel_check or (lambda: False)
    thu_muc = os.path.abspath(str(thu_muc or "").strip().strip('"'))
    tam = os.path.join(thu_muc, THU_MUC_PHAN_AUDIO if chi_audio else THU_MUC_PHAN)
    vat = "audio" if chi_audio else "video"
    nhan_ghep = "🎵 Audio ghép" if chi_audio else "🎞️ Video ghép"
    # Dòng là FILE trong máy (D-46) thì dùng thẳng; còn lại mới tải. File không có → dừng TRƯỚC khi tải gì.
    sach = [str(x).strip().strip('"').strip() for x in links]
    la_may = [os.path.isfile(x) or bool(_RE_DUONG_DAN.match(x)) for x in sach]
    dong_may = {i: _dong_file_may(x) for i, (x, m) in enumerate(zip(sach, la_may)) if m}
    # Thư mục tạm ghép xong bị xoá: file người dùng chọn từ đó (phần lẻ của lượt hỏng) sẽ mất ở lượt ghép này hay lượt sau.
    tam_tool = tuple(os.path.normcase(os.path.join(thu_muc, t)) + os.sep for t in (THU_MUC_PHAN, THU_MUC_PHAN_AUDIO))
    for d in dong_may.values():
        if d["trang_thai"] == "xong" and os.path.normcase(d["duong_dan"]).startswith(tam_tool):
            d.update(trang_thai="loi", ghi_chu="File nằm trong thư mục tạm của tool (bị xoá khi ghép xong) — chép ra "
                                                "chỗ khác rồi ghép lại.")
    thieu = [d for d in dong_may.values() if d["trang_thai"] == "loi"]
    if thieu:
        ket_qua = [dong_may.get(i) or {"url": x, "trang_thai": "bo_qua", "duong_dan": "", "tieu_de": "", "chat_luong": "",
                                       "ghi_chu": "Chưa tải: có file trong máy không dùng được."}
                   for i, x in enumerate(sach)]
        ket_qua.append({"url": nhan_ghep, "trang_thai": "loi", "duong_dan": "", "tieu_de": "", "chat_luong": "",
                        "ghi_chu": "Chưa ghép: có file trong máy không dùng được (xem các dòng ở trên).",
                        "la_dong_ghep": True})
        return ket_qua
    can_tai = [x for x, m in zip(links, la_may) if not m]
    os.makedirs(tam, exist_ok=True)
    da_tai = iter(
        tv.tai_nhieu(
            can_tai,
            tam,
            cau_hinh_mang,
            progress=lambda p, m: bao(0.7 * p, m),
            cancel_check=huy,
            bo_qua_da_co=True,
            **({"chat_luong": "Chỉ tiếng"} if chi_audio else {"dinh_dang": tv.DINH_DANG_GHEP}),
            **kw,
        )
        if can_tai
        else []
    )
    ket_qua = [dong_may[i] if i in dong_may else next(da_tai) for i in range(len(sach))]
    dong_ghep = {
        "url": nhan_ghep,
        "trang_thai": "loi",
        "duong_dan": "",
        "tieu_de": "",
        "chat_luong": "",
        "ghi_chu": "",
        "la_dong_ghep": True,
    }
    ket_qua.append(dong_ghep)

    def that_bai(ly_do: str) -> list:
        dong_ghep["ghi_chu"] = (
            ly_do
            + f" Các {vat} đã tải vẫn giữ ở «{tam}» — bấm lại thì không phải tải lại."
        )
        return ket_qua

    # Đường dẫn từng link theo đúng thứ tự: tải mới → đường dẫn tải; «đã có»/«trùng» → file «[mã].mp4» trong thư mục tạm.
    co_san = {}
    re_ma = tv._RE_MA_CUOI_TEN_TIENG if chi_audio else tv._RE_MA_CUOI_TEN
    for f in os.listdir(tam) if os.path.isdir(tam) else []:
        m = re_ma.search(f)
        if m:
            co_san.setdefault(m.group(1), os.path.join(tam, f))
    phan, ten_theo_ma = [], {}
    for k in ket_qua[:-1]:
        ma = tv.ma_link(k["url"])
        duong = k["duong_dan"] if k["trang_thai"] == "xong" else co_san.get(ma)
        if k["trang_thai"] == "loi" or not duong or not os.path.isfile(duong):
            return that_bai(f"Chưa ghép: có {vat} chưa tải được (xem các dòng ở trên).")
        # Link lặp lại: lượt tải báo «trùng», không trả tiêu đề — dùng tiêu đề của lần đầu.
        ten = ten_theo_ma.setdefault(ma or k["url"], k["tieu_de"] or _ten_tu_file(duong))
        phan.append((ten, k["url"], duong))
    if huy():
        return that_bai("Đã dừng theo yêu cầu trước khi ghép.")
    # File trong máy luôn chỉnh âm lượng ra BẢN trong thư mục tạm; file tải về (của tool) chỉnh tại chỗ.
    file_may = {os.path.normcase(k["duong_dan"]) for k in ket_qua[:-1] if k.get("la_file_may")}
    ghi_am = []
    if chuan_hoa_am:
        # Từng video riêng (như YouTube), TRƯỚC khi kiểm thông số/nối; video đã ở mức thì giữ nguyên — bấm lại với file lẻ
        # còn giữ từ lượt trước không nén lại lần nữa.
        thay: dict = {}
        for so, duong in enumerate(dict.fromkeys(d for *_x, d in phan), start=1):
            bao(0.70, f"Đang chỉnh âm lượng {vat} {so} về mức YouTube...")
            ban = (os.path.join(tam, THU_MUC_AM, f"{so}_{os.path.basename(duong)}")
                   if os.path.normcase(duong) in file_may else None)
            if ban:
                os.makedirs(os.path.dirname(ban), exist_ok=True)
                # Bản cũ của lượt hỏng trước (có thể của file KHÁC): file đã đủ to thì chuan_hoa không ghi đè nó.
                with contextlib.suppress(FileNotFoundError):
                    os.remove(ban)
            try:
                chuan_hoa(duong, huy=huy, dich=ban)
            except DaHuyChinhAmLuong:
                return that_bai("Đã dừng theo yêu cầu trong lúc chỉnh âm lượng.")
            except RuntimeError as e:
                ghi_am.append(f"{vat.capitalize()} {so}: chưa chỉnh được âm lượng ({e}).")
            if ban and os.path.isfile(ban):
                thay[duong] = ban
        phan = [(ten, link, thay.get(d, d)) for ten, link, d in phan]

    bao(0.71, f"Đang kiểm thông số các {vat}...")
    do_ts, khoa, duoi = (thong_so_audio, THONG_SO_AUDIO, ".m4a") if chi_audio else (thong_so, THONG_SO, ".mp4")
    try:
        ts = [(ten, do_ts(duong)) for ten, _l, duong in phan]
    except RuntimeError as e:
        return that_bai(f"Chưa ghép: {e}")
    chuan = chuan_audio(ts[0][1]) if chi_audio else ts[0][1]
    # Ghép video: video 1 là chuẩn, không chuyển; ghép audio: so cả file 1 với đích AAC chung.
    can_chuyen = [i for i, (_t, t) in enumerate(ts) if (i or chi_audio) and any(t[k] != chuan[k] for k in khoa)]
    if can_chuyen and not chi_audio and (chuan["ma_hinh"] != "h264" or chuan["ma_tieng"] != "aac"):
        # shortcut: chỉ chuyển về H.264 + AAC (định dạng tải chung); video 1 khác kiểu đó thì dừng như trước.
        return that_bai(
            "Chưa ghép: các video khác thông số và video 1 không phải H.264 + AAC nên tool không tự chuyển được. "
            "Bỏ các video lệch khỏi danh sách rồi ghép lại. " + " | ".join(cac_cho_lech(ts)) + "."
        )

    def dung_luong_chuyen(cac_vi_tri) -> float:
        if not chi_audio:
            return _DU_PHONG_O_DIA + sum(os.path.getsize(phan[i][2]) for i in cac_vi_tri)
        # Chỉ ghi phần TIẾNG (chép nguyên hoặc AAC 192 kbps): ước theo thời lượng × tốc độ bit, mỗi nguồn một lần.
        uoc = {phan[i][2]: ts[i][1]["do_dai"] * max(192_000, ts[i][1]["bit_rate"]) / 8 for i in cac_vi_tri}
        return _DU_PHONG_O_DIA + sum(min(os.path.getsize(d), b) for d, b in uoc.items())

    if can_chuyen:
        thu_muc_khop = os.path.join(tam, THU_MUC_KHOP)
        ban_khop = {d: os.path.join(thu_muc_khop, _ten_khop(d, chuan, khoa, duoi))
                    for d in {phan[i][2] for i in can_chuyen}}
        can = dung_luong_chuyen(i for i in can_chuyen if not chi_audio or not os.path.isfile(ban_khop[phan[i][2]]))
        if shutil.disk_usage(thu_muc).free < can:
            return that_bai(f"Chưa ghép: cần chuyển {vat} lệch, ổ đĩa cần còn trống khoảng {can / 1e9:,.1f} GB.")
        os.makedirs(thu_muc_khop, exist_ok=True)
    da_chuyen: dict = {}
    for so, i in enumerate(can_chuyen, start=1):
        ten, link, duong = phan[i]
        if duong not in da_chuyen:
            dich_khop = ban_khop[duong]
            if not os.path.isfile(dich_khop):
                do_dai_i = ts[i][1]["do_dai"]
                nhan = (f"Đang chuyển {vat} {i + 1} «{ten}» cho khớp "
                        f"{'kiểu AAC chung' if chi_audio else 'video 1'} ({so}/{len(can_chuyen)})")
                bao(0.71 + 0.14 * (so - 1) / len(can_chuyen), nhan + "...")

                def tien_do_chuyen(d: dict, so=so, nhan=nhan, do_dai_i=do_dai_i) -> None:
                    giay = int(d.get("out_time_us") or d.get("out_time_ms") or 0) / 1e6
                    bao(0.71 + 0.14 * (so - 1 + min(giay / do_dai_i, 1.0)) / len(can_chuyen),
                        f"{nhan}: {hhmmss(giay)} / {hhmmss(do_dai_i)}")

                chuyen = _chuyen_audio if chi_audio else _chuyen_khop
                r = chuyen(duong, dich_khop, chuan, ts[i][1], huy=huy, khi_tien_do=tien_do_chuyen)
                if r.cancelled:
                    return that_bai(f"Đã dừng theo yêu cầu trong lúc chuyển {vat} lệch; phần chuyển dở đã xoá.")
                if r.returncode != 0 or not os.path.isfile(dich_khop):
                    return that_bai(f"Chưa ghép: chuyển {vat} {i + 1} «{ten}» cho khớp bị lỗi: "
                                    f"{(r.stderr or r.ly_do or '').strip()[-300:]}")
            da_chuyen[duong] = dich_khop
        phan[i] = (ten, link, da_chuyen[duong])
    if can_chuyen:
        try:
            ts = [(ten, do_ts(duong)) for ten, _l, duong in phan]
        except RuntimeError as e:
            return that_bai(f"Chưa ghép: {e}")
    lech = (cac_cho_lech(ts, chuan, THONG_SO_AUDIO, "Audio") if chi_audio else cac_cho_lech(ts))
    if lech:
        return that_bai(
            f"Chưa ghép: đã chuyển các {vat} lệch nhưng vẫn khác thông số chung nên không nối thẳng được (nối vẫn "
            f"ra file nhưng hỏng ở chỗ nối). Bỏ các {vat} lệch khỏi danh sách rồi ghép lại. "
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
    ten = ten_file_ra(ten_file, "Audio_ghep" if chi_audio else "Video_ghep")
    dich = _ten_ra(thu_muc, ten, duoi)
    dang_ghi = os.path.join(tam, "dang_ghep" + duoi)
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

    # Track chương QuickTime đo bằng nhịp của CẢ FILE; không đặt thì FFmpeg 9 lấy BCNN nhịp hình và tiếng (15360 với
    # 44,1 kHz → 11.289.600/giây): chương > ~190 s tràn 32-bit bị bỏ, hết chương thì mất track (cảnh báo «Referenced QT
    # chapter track not found», trình phát Apple không thấy mốc). Nhịp file = tần số tiếng (:func:`_nhip_file`); nhịp
    # của track hình/tiếng không đổi (đo 09/11).
    nhip_chuong = _nhip_file(ts)
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
            "0:a:0" if chi_audio else "0",
            "-map_metadata",
            "1",
            "-map_chapters",
            "1",
            "-c",
            "copy",
            *nhip_chuong,
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

    try:
        do_dai_ra = do_ts(dich)["do_dai"]
    except RuntimeError as e:
        do_dai_ra, loi_do = None, str(e)
    t0 = ts[0][1]
    kieu = (f"AAC {t0['tan_so_tieng']} Hz {t0['kenh_tieng']} kênh" if chi_audio
            else f"{t0['do_phan_giai']} {t0['ma_hinh']} {t0['hinh_giay']} hình/giây")
    dong_ghep.update(
        trang_thai="xong",
        duong_dan=dich,
        tieu_de=f"{vat.capitalize()} ghép {len(phan)} {vat} — {hhmmss(do_dai_ra if do_dai_ra is not None else tong)}",
        chat_luong=f"{kieu}, "
        + (f"{len(can_chuyen)} {vat} chuyển cho khớp" if can_chuyen else "không nén lại"),
        ghi_chu=f"Mốc thời gian từng {vat} gốc: {duong_moc}"
        + (f" — Âm lượng từng {vat} đã đưa về mức YouTube (-14 LUFS)." if chuan_hoa_am and not ghi_am else "")
        + "".join(f" — {x}" for x in ghi_am),
    )
    if can_chuyen:
        dong_ghep["ghi_chu"] += (" — Đã chuyển sang AAC cho khớp: " if chi_audio
                                 else " — Đã chuyển cho khớp video 1 (tiếng giữ nguyên): ") + ", ".join(
            f"{vat.capitalize()} {i + 1} «{phan[i][0]}»" for i in can_chuyen
        )
    if do_dai_ra is None:
        dong_ghep["ghi_chu"] += (
            f" — CẢNH BÁO: không đo lại được độ dài {vat} ghép ({loi_do}); chưa chắc mốc đúng. Giữ các {vat} đã tải ở "
            f"«{tam}»."
        )
    elif abs(do_dai_ra - tong) > LECH_DO_DAI_TOI_DA_S:
        dong_ghep["ghi_chu"] += (
            f" — CẢNH BÁO: {vat} ghép dài {do_dai_ra:.2f} s, tổng các phần {tong:.2f} s; mốc có thể "
            f"lệch. Giữ các {vat} đã tải ở «{tam}»."
        )
    else:
        shutil.rmtree(tam, ignore_errors=True)
        for k in ket_qua[:-1]:  # file lẻ vừa xoá: đừng để dòng từng link trỏ vào đó
            if k.get("la_file_may"):
                k["ghi_chu"] = f"Đã nối vào {vat} ghép bên dưới; file trong máy giữ nguyên."
            elif k["trang_thai"] in ("xong", "bo_qua"):
                k.update(trang_thai="xong", duong_dan="", ghi_chu=f"Đã nối vào {vat} ghép bên dưới; file lẻ đã xoá.")
    bao(1.0, "Xong.")
    return ket_qua
