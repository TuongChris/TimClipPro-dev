# -*- coding: utf-8 -*-
"""Tải video theo link rồi cắt CHÍNH XÁC một đoạn «từ … đến …» (D-42, người dùng chọn 09/11).

Tải trọn qua :func:`tai_video_goc.tai_nhieu` (4 kết nối, cùng đường mạng/cookie/cầu dao) vào thư mục tạm
:data:`THU_MUC_TAM`, rồi cắt bằng FFmpeg có NÉN LẠI đoạn cắt (``-ss`` trước ``-i`` + mã hoá lại = đúng từng khung hình;
cắt ``-c copy`` chỉ dừng được ở khung hình chính, lệch vài giây). Đoạn ra được kiểm độ dài; đúng thì xoá video trọn
(người dùng chọn chỉ giữ đoạn cắt), sai/lỗi thì giữ video trọn trong thư mục tạm để bấm lại khỏi tải lại.
"""

from __future__ import annotations

import contextlib
import os
import re
from typing import Callable, Optional

import am_luong
import tai_video_goc as tv
from channel import _CoHuyTuHam
from kiem_thoi_luong import hhmmss
from process_runner import IM_LANG_FFMPEG_S, chay_lenh_media
from ytdlp_chung import CauHinhMang

THU_MUC_TAM = ".timclip_cat"
# Đoạn ra lệch độ dài yêu cầu quá mức này thì không tin (≈ 1 khung hình 30 fps + làm tròn khung tiếng).
LECH_DO_DAI_TOI_DA_S = 0.06
_SO = re.compile(r"\d+(\.\d+)?")


def doc_moc(van_ban: str) -> Optional[float]:
    """«83», «1:23», «01:02:03», «1:23.5» (hoặc «,5») → giây; rỗng → ``None``; sai → ``ValueError`` (câu tiếng Việt)."""
    s = str(van_ban or "").strip().replace(",", ".")
    if not s:
        return None
    phan = s.split(":")
    sai = ValueError(
        f"Mốc «{s}» không hợp lệ — gõ phút:giây (vd. 1:23) hoặc giờ:phút:giây (vd. 1:02:03)."
    )
    if (
        len(phan) > 3
        or not all(_SO.fullmatch(p) for p in phan)
        or any("." in p for p in phan[:-1])
    ):
        raise sai
    if any(float(p) >= 60 for p in phan[1:]):
        raise sai
    giay = 0.0
    for p in phan:
        giay = giay * 60 + float(p)
    return giay


def moc_hien(giay: float, cach: str = ":") -> str:
    """00:01:23 hoặc 00:01:23,5 — giữ phần lẻ của giây (``hhmmss`` bỏ mất); ``cach="."`` cho tên file Windows."""
    giay = round(giay, 3)  # làm tròn MỘT lần: 59,9996 → 60 (không thành «00:00:59,»)
    phan_le = round(giay % 1, 3)
    return hhmmss(giay).replace(":", cach) + (
        f",{f'{phan_le:.3f}'[2:].rstrip('0')}" if phan_le else ""
    )


def _do(path: str) -> tuple:
    """(độ dài giây, có luồng hình không — ảnh bìa đính kèm không tính)."""
    d = am_luong.doc_ffprobe(path)
    hinh = next(
        (
            s
            for s in d.get("streams", [])
            if s.get("codec_type") == "video"
            and not (s.get("disposition") or {}).get("attached_pic")
        ),
        None,
    )
    return float((d.get("format") or {}).get("duration") or 0), hinh is not None


def _cat(
    nguon: str, dich: str, tu: float, den: float, co_hinh: bool, *, huy, khi_tien_do
):
    """Cắt [tu, den) có nén lại (H.264 crf 18 + AAC; chỉ tiếng thì AAC). Ghi file tạm rồi mới đổi tên."""
    dang = dich + ".dang" + os.path.splitext(dich)[1]
    hinh = (
        [
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
        ]
        if co_hinh
        else ["-vn"]
    )
    r = chay_lenh_media(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{tu:.3f}",
            "-i",
            nguon,
            "-t",
            f"{den - tu:.3f}",
            *hinh,
            "-map",
            "0:a:0?",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-sn",
            "-dn",
            "-map_chapters",
            "-1",
            "-movflags",
            "+faststart",
            dang,
        ],
        cancel_event=_CoHuyTuHam(huy),
        im_lang_toi_da_s=IM_LANG_FFMPEG_S,
        theo_doi_tien_do=True,
        khi_tien_do=khi_tien_do,
    )
    if not r.cancelled and r.returncode == 0 and os.path.isfile(dang):
        os.replace(dang, dich)
    elif os.path.exists(dang):
        os.remove(dang)
    return r


def tai_doan(
    links: list,
    thu_muc: str,
    cau_hinh_mang: Optional[CauHinhMang] = None,
    *,
    tu_s: float,
    den_s: float,
    chat_luong: str = tv.CHAT_LUONG_MAC_DINH,
    chuan_hoa_am: bool = False,
    progress: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    **kw,
) -> list:
    """Tải từng link rồi cắt đoạn [``tu_s``, ``den_s``) vào ``thu_muc``. Trả list dict như ``tai_nhieu`` (một dòng mỗi
    link; ``duong_dan`` = file đoạn cắt). ``kw`` chuyển cho ``tai_nhieu`` (player_clients, phien…)."""
    if not 0 <= tu_s < den_s:
        raise ValueError("Mốc «Đến» phải sau mốc «Từ» (và «Từ» không âm).")
    bao = progress or (lambda _p, _m: None)
    huy = cancel_check or (lambda: False)
    thu_muc = os.path.abspath(str(thu_muc or "").strip().strip('"'))
    # Một thư mục tạm cho mỗi mức chất lượng: video trọn giữ lại từ lượt trước (nhận ra theo [mã video]) chỉ được dùng
    # lại khi cùng mức — khác mức thì tải lại, không cắt từ bản 720p cũ khi người dùng chọn «Cao nhất».
    tam = os.path.join(thu_muc, THU_MUC_TAM, f"cl_{tv.CHAT_LUONG.get(chat_luong)}")
    chi_tieng = tv.CHAT_LUONG.get(chat_luong) == 0
    ket_qua = tv.tai_nhieu(
        list(links),
        tam,
        cau_hinh_mang,
        progress=lambda p, m: bao(0.7 * p, m),
        cancel_check=huy,
        bo_qua_da_co=True,
        chat_luong=chat_luong,
        **kw,
    )
    # Video đã có trong thư mục tạm (lượt trước cắt hỏng/mốc sai): tai_nhieu báo «bỏ qua» không kèm đường dẫn.
    mau = tv._RE_MA_CUOI_TEN_TIENG if chi_tieng else tv._RE_MA_CUOI_TEN
    co_san = {}
    for f in os.listdir(tam) if os.path.isdir(tam) else []:
        m = mau.search(f)
        if m and not f.lower().endswith(tv._DUOI_ANH):
            co_san.setdefault(m.group(1), os.path.join(tam, f))
    for i, k in enumerate(ket_qua):
        nguon = (
            k["duong_dan"]
            if k["trang_thai"] == "xong"
            else co_san.get(tv.ma_link(k["url"]) or "")
        )
        if k["trang_thai"] == "loi" or not nguon or not os.path.isfile(nguon):
            continue
        if huy():
            k.update(
                trang_thai="bo_qua",
                duong_dan="",
                ghi_chu="Đã dừng theo yêu cầu trước khi cắt.",
            )
            continue
        k.update(
            cat_mot(
                nguon, thu_muc, tu_s, den_s, chuan_hoa_am=chuan_hoa_am, huy=huy,
                bao=lambda f, m, i=i: bao(0.7 + 0.3 * (i + f) / len(ket_qua), m),
                nhan=f"Video {i + 1}/{len(ket_qua)}",
                giu=f"Video đã tải vẫn giữ ở «{tam}», sửa mốc rồi bấm lại thì không phải tải lại.",
            )
        )
        if k["trang_thai"] == "xong":
            with contextlib.suppress(OSError):
                os.remove(nguon)
    for d in (tam, os.path.dirname(tam)):  # chỉ xoá khi rỗng: còn video giữ lại để bấm lại thì để nguyên
        with contextlib.suppress(OSError):
            os.rmdir(d)
    bao(1.0, "Xong.")
    return ket_qua


def cat_mot(
    nguon: str,
    thu_muc: str,
    tu_s: float,
    den_s: float,
    *,
    chuan_hoa_am: bool = False,
    huy: Callable[[], bool] = lambda: False,
    bao: Callable[[float, str], None] = lambda _f, _m: None,
    nhan: str = "",
    giu: str = "",
) -> dict:
    """Cắt CHÍNH XÁC đoạn [``tu_s``, ``den_s``) của ``nguon`` ra file mới trong ``thu_muc`` (không bao giờ ghi đè), kiểm
    độ dài, tuỳ chọn chỉnh âm lượng đoạn cắt. ``nguon`` KHÔNG bị sửa/xoá ở đây. Trả ``{trang_thai, duong_dan, ghi_chu}``;
    ``giu``: câu nói ``nguon`` còn ở đâu (gắn vào lỗi), ``bao(phần 0–1 của file này, câu)``."""
    doan = f"{moc_hien(tu_s)}–{moc_hien(den_s)}"
    try:
        do_dai, co_hinh = _do(nguon)
    except RuntimeError as e:
        return {"trang_thai": "loi", "duong_dan": "", "ghi_chu": str(e)}
    if den_s > do_dai + LECH_DO_DAI_TOI_DA_S:
        return {"trang_thai": "loi", "duong_dan": "",
                "ghi_chu": f"Video chỉ dài {hhmmss(do_dai)} — đoạn {doan} vượt quá. {giu}".strip()}
    goc = re.sub(r"\.audio$", "", os.path.splitext(os.path.basename(nguon))[0])
    os.makedirs(thu_muc, exist_ok=True)
    dich = tv._ten_trong(
        thu_muc,
        f"{goc} ({moc_hien(tu_s, '.')}-{moc_hien(den_s, '.')})" + (".mp4" if co_hinh else ".m4a"),
    )
    nhan = f"{nhan}: đang cắt đoạn {doan}" if nhan else f"Đang cắt đoạn {doan}"

    def tien_do(d: dict) -> None:
        giay = int(d.get("out_time_us") or d.get("out_time_ms") or 0) / 1e6
        bao(min(giay / (den_s - tu_s), 1.0), f"{nhan} ({hhmmss(giay)})")

    bao(0.0, nhan + "...")
    r = _cat(nguon, dich, tu_s, den_s, co_hinh, huy=huy, khi_tien_do=tien_do)
    if r.cancelled:
        return {"trang_thai": "bo_qua", "duong_dan": "", "ghi_chu": "Đã dừng theo yêu cầu trong lúc cắt; phần cắt dở đã xoá."}
    if r.returncode != 0 or not os.path.isfile(dich):
        return {"trang_thai": "loi", "duong_dan": "",
                "ghi_chu": f"FFmpeg cắt lỗi: {(r.stderr or r.ly_do or '').strip()[-300:]}"}
    try:
        dai_ra = _do(dich)[0]
        ly_do = (f"đoạn cắt dài {dai_ra:.3f} s, yêu cầu {den_s - tu_s:.3f} s"
                 if abs(dai_ra - (den_s - tu_s)) > LECH_DO_DAI_TOI_DA_S else "")
    except RuntimeError as e:
        ly_do = f"không đo lại được đoạn cắt ({e})"
    if ly_do:
        # Đổi tên «.loi»: tên đẹp «… (00.01.23-00.02.45).mp4» dễ bị dùng nhầm như một đoạn cắt đúng.
        loi = tv._ten_trong(thu_muc, os.path.splitext(os.path.basename(dich))[0] + ".loi" + os.path.splitext(dich)[1])
        os.replace(dich, loi)
        return {"trang_thai": "loi", "duong_dan": loi,
                "ghi_chu": f"Không tin được: {ly_do}. File đoạn cắt để ở «{loi}». {giu}".strip()}
    ghi_am = ""
    if chuan_hoa_am:
        bao(1.0, f"{nhan}: đang chỉnh âm lượng...")
        try:
            ghi_am = " " + am_luong.chuan_hoa(dich, huy=huy)
        except am_luong.DaHuyChinhAmLuong:
            ghi_am = " Đã dừng lúc chỉnh âm lượng — đoạn cắt giữ âm lượng gốc."
        except RuntimeError as e:
            ghi_am = f" Chưa chỉnh được âm lượng ({e}) — đoạn cắt giữ âm lượng gốc."
    return {"trang_thai": "xong", "duong_dan": dich,
            "ghi_chu": f"Đoạn {doan} ({den_s - tu_s:.3f} s), cắt đúng từng khung hình (nén lại đoạn cắt)." + ghi_am}
