# -*- coding: utf-8 -*-
"""Tải video theo link rồi cắt CHÍNH XÁC một đoạn «từ … đến …» (D-42, người dùng chọn 09/11).

Tải trọn qua :func:`tai_video_goc.tai_nhieu` (4 kết nối, cùng đường mạng/cookie/cầu dao) vào thư mục tạm
:data:`THU_MUC_TAM`, rồi cắt bằng FFmpeg có NÉN LẠI đoạn cắt (``-ss`` trước ``-i`` + mã hoá lại = đúng từng khung hình;
cắt ``-c copy`` chỉ dừng được ở khung hình chính, lệch vài giây). Đoạn ra được kiểm độ dài; đúng thì xoá video trọn
(người dùng chọn chỉ giữ đoạn cắt), sai/lỗi thì giữ video trọn trong thư mục tạm để bấm lại khỏi tải lại.

«Bỏ các đoạn» (D-59, 17/11): ngược lại với cắt một đoạn — bỏ NHIỀU đoạn rồi nối phần còn lại thành video mới, MỘT lượt
FFmpeg (``trim``/``atrim`` + ``concat``, nén lại một lần như cắt) → đúng từng khung hình, hình–tiếng khớp ở mọi chỗ nối.

«Chụp ảnh» (18/11): ảnh PNG đúng khung hình ở từng mốc người dùng gõ (``-ss`` trước ``-i`` + giải mã = khung hình ĐẦU
TIÊN từ mốc trở đi, không phải khung hình chính gần nhất), độ phân giải gốc. Video theo link chỉ tải phần HÌNH.
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
# Chỉ mốc có «:» mới dùng phẩy thập phân. Trong «0:05:24,0:07:11», dấu phẩy ngăn hai mốc.
_MOC_TRONG_DS = re.compile(r"\d+(?::\d+){1,2}(?:[.,]\d+(?![\d:.]))?|\d+(?:\.\d+)?")
_PHAN_CACH_DS = re.compile(r"[\s,;\-–—]*")
# Phần giữ lại ngắn hơn mức này (dưới ~1 khung hình) coi như bỏ luôn: không có khung hình nào để nối.
DOAN_GIU_TOI_THIEU_S = 0.05
# Mốc chụp ảnh cách nhau bằng phẩy, chấm phẩy, dấu cách hoặc xuống dòng — không có «-» («7:23 - 8:00» là một đoạn).
_PHAN_CACH_MOC = re.compile(r"[\s,;]*")


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


def doc_ds_doan(van_ban: str) -> list:
    """«0:04:12 - 0:05:24, 0:07:11 - 0:09:01» (phẩy, chấm phẩy hoặc mỗi dòng một đoạn) → ``[(252.0, 324.0), …]`` xếp
    theo thời gian, đoạn chồng/chạm nhau gộp làm một; rỗng → ``[]``; sai → ``ValueError`` (câu tiếng Việt)."""
    s = str(van_ban or "")
    moc = [m.group() for m in _MOC_TRONG_DS.finditer(s)]
    thua = _MOC_TRONG_DS.sub(" ", s)
    if not _PHAN_CACH_DS.fullmatch(thua):
        la = re.sub(r"[\s,;\-–—]+", " ", thua).strip()
        raise ValueError(
            f"Không đọc được «{la}» trong danh sách đoạn — mỗi đoạn gõ «Từ - Đến» (vd. 0:04:12 - 0:05:24), các đoạn "
            "cách nhau bằng dấu phẩy hoặc xuống dòng."
        )
    if len(moc) % 2:
        raise ValueError(f"Danh sách có {len(moc)} mốc — mỗi đoạn cần đủ hai mốc «Từ - Đến».")
    ds = []
    for tu_vb, den_vb in zip(moc[::2], moc[1::2]):
        tu, den = doc_moc(tu_vb), doc_moc(den_vb)
        if den <= tu:
            raise ValueError(f"Đoạn {tu_vb} - {den_vb}: mốc «Đến» phải sau mốc «Từ».")
        ds.append((tu, den))
    gop: list = []
    for tu, den in sorted(ds):
        if gop and tu <= gop[-1][1]:
            gop[-1] = (gop[-1][0], max(gop[-1][1], den))
        else:
            gop.append((tu, den))
    return gop


def mo_ta_ds_doan(ds_bo: list) -> str:
    """«Bỏ 2 đoạn (tổng 00:03:02): 00:04:12–00:05:24, 00:07:11–00:09:01» — câu xác nhận cho giao diện."""
    tong = sum(b - a for a, b in ds_bo)
    return (f"Bỏ {len(ds_bo)} đoạn (tổng {moc_hien(tong)}): "
            + ", ".join(f"{moc_hien(a)}–{moc_hien(b)}" for a, b in ds_bo))


def doc_ds_moc(van_ban: str) -> list:
    """«7:23, 12:05» (phẩy, chấm phẩy, dấu cách hoặc mỗi dòng một mốc) → ``[443.0, 725.0]`` xếp theo thời gian, bỏ
    trùng; rỗng → ``[]``; sai → ``ValueError`` (câu tiếng Việt)."""
    s = str(van_ban or "")
    thua = _MOC_TRONG_DS.sub(" ", s)
    if not _PHAN_CACH_MOC.fullmatch(thua):
        la = re.sub(r"[\s,;]+", " ", thua).strip()
        raise ValueError(
            f"Không đọc được «{la}» trong danh sách mốc — gõ phút:giây (vd. 7:23) hoặc giờ:phút:giây, các mốc cách "
            "nhau bằng dấu phẩy."
        )
    return sorted({doc_moc(m.group()) for m in _MOC_TRONG_DS.finditer(s)})


def moc_hien(giay: float, cach: str = ":") -> str:
    """00:01:23 hoặc 00:01:23,5 — giữ phần lẻ của giây (``hhmmss`` bỏ mất); ``cach="."`` cho tên file Windows."""
    giay = round(giay, 3)  # làm tròn MỘT lần: 59,9996 → 60 (không thành «00:00:59,»)
    phan_le = round(giay % 1, 3)
    return hhmmss(giay).replace(":", cach) + (
        f",{f'{phan_le:.3f}'[2:].rstrip('0')}" if phan_le else ""
    )


def _do(path: str) -> tuple:
    """(độ dài giây, có luồng hình không — ảnh bìa đính kèm không tính, có luồng tiếng không)."""
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
    tieng = any(s.get("codec_type") == "audio" for s in d.get("streams", []))
    return float((d.get("format") or {}).get("duration") or 0), hinh is not None, tieng


_MA_HOA = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
_MA_HOA_TIENG = ["-c:a", "aac", "-b:a", "192k", "-sn", "-dn", "-map_chapters", "-1", "-movflags", "+faststart"]


def _chay_ra_file(lenh: list, dang: str, dich: str, *, huy, khi_tien_do):
    """Chạy FFmpeg ghi ``dang`` rồi mới đổi tên thành ``dich``; hỏng/dừng thì xoá file dở."""
    r = chay_lenh_media(
        lenh,
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


def _cat(
    nguon: str, dich: str, tu: float, den: float, co_hinh: bool, *, huy, khi_tien_do
):
    """Cắt [tu, den) có nén lại (H.264 crf 18 + AAC; chỉ tiếng thì AAC). Ghi file tạm rồi mới đổi tên."""
    dang = dich + ".dang" + os.path.splitext(dich)[1]
    hinh = ["-map", "0:v:0", *_MA_HOA] if co_hinh else ["-vn"]
    return _chay_ra_file(
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
            *_MA_HOA_TIENG,
            dang,
        ],
        dang,
        dich,
        huy=huy,
        khi_tien_do=khi_tien_do,
    )


def _phan_giu(ds_bo: list, do_dai: float) -> list:
    """Các phần GIỮ lại khi bỏ ``ds_bo`` (đã xếp, đã gộp): ``[(từ, đến | None = tới hết video)]``."""
    giu, t = [], 0.0
    for tu, den in ds_bo:
        if tu - t >= DOAN_GIU_TOI_THIEU_S:
            giu.append((t, tu))
        t = max(t, den)
    if do_dai - t >= DOAN_GIU_TOI_THIEU_S:
        giu.append((t, None))
    return giu


def _bo(nguon: str, dich: str, giu: list, co_hinh: bool, co_tieng: bool, *, huy, khi_tien_do):
    """Nối các phần ``giu`` của ``nguon`` thành ``dich`` trong MỘT lượt FFmpeg (nén lại một lần). Tua đầu vào tới phần giữ
    đầu tiên (không giải mã phần bỏ phía trước); hình và tiếng của mỗi phần cùng lấy mốc ``a`` làm 0 — tiếng bắt đầu
    trễ hơn hình được đệm im lặng, không bị kéo sớm lên."""
    dang = dich + ".dang" + os.path.splitext(dich)[1]
    moc_dau = round(giu[0][0], 3)
    tua = ["-ss", f"{moc_dau:.3f}"] if moc_dau > 0 else []
    # shortcut: đồ thị lọc nằm trên dòng lệnh (~150 ký tự/phần, Windows tối đa 32.767) → khoảng 200 đoạn; cần hơn thì
    # chuyển sang file đồ thị lọc.
    do_thi, vao = [], ""
    for i, (a, b) in enumerate(giu):
        a = round(a, 3) - moc_dau
        het = f":end={round(b, 3) - moc_dau:.3f}" if b is not None else ""
        if co_hinh:
            do_thi.append(f"[0:v:0]trim=start={a:.3f}{het},setpts=PTS-{a:.3f}/TB[v{i}]")
            vao += f"[v{i}]"
        if co_tieng:
            do_thi.append(
                f"[0:a:0]atrim=start={a:.3f}{het},asetpts=PTS-{a:.3f}/TB,aresample=async=1:first_pts=0[a{i}]"
            )
            vao += f"[a{i}]"
    ra = ("[v]" if co_hinh else "") + ("[a]" if co_tieng else "")
    do_thi.append(f"{vao}concat=n={len(giu)}:v={int(co_hinh)}:a={int(co_tieng)}{ra}")
    return _chay_ra_file(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *tua, "-i", nguon,
            "-filter_complex", ";".join(do_thi),
            *(["-map", "[v]", *_MA_HOA] if co_hinh else []),
            *(["-map", "[a]"] if co_tieng else []),
            *_MA_HOA_TIENG,
            dang,
        ],
        dang,
        dich,
        huy=huy,
        khi_tien_do=khi_tien_do,
    )


def tai_doan(
    links: list,
    thu_muc: str,
    cau_hinh_mang: Optional[CauHinhMang] = None,
    *,
    tu_s: Optional[float] = None,
    den_s: Optional[float] = None,
    ds_bo: Optional[list] = None,
    ds_moc: Optional[list] = None,
    chat_luong: str = tv.CHAT_LUONG_MAC_DINH,
    chuan_hoa_am: bool = False,
    progress: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    **kw,
) -> list:
    """Tải từng link rồi cắt đoạn [``tu_s``, ``den_s``) — hoặc bỏ các đoạn ``ds_bo`` rồi nối phần còn lại — vào
    ``thu_muc`` — hoặc chụp ảnh ở các mốc ``ds_moc`` (:func:`chup_anh`). Trả list dict như ``tai_nhieu`` (một dòng mỗi
    link; ``duong_dan`` = file kết quả). ``kw`` chuyển cho ``tai_nhieu`` (player_clients, phien…)."""
    if ds_moc:
        if tu_s is not None or ds_bo:
            raise ValueError("Chỉ chọn một việc: cắt một đoạn, bỏ các đoạn hoặc chụp ảnh.")
        if tv.CHAT_LUONG.get(chat_luong) == 0:
            raise ValueError("Chụp ảnh cần video có hình — chọn «Video», không chọn «Chỉ audio».")
    elif ds_bo:
        if tu_s is not None:
            raise ValueError("Chỉ chọn một việc: cắt lấy một đoạn («Từ»/«Đến») hoặc bỏ các đoạn.")
    elif not (tu_s is not None and den_s is not None and 0 <= tu_s < den_s):
        raise ValueError("Mốc «Đến» phải sau mốc «Từ» (và «Từ» không âm).")
    bao = progress or (lambda _p, _m: None)
    huy = cancel_check or (lambda: False)
    thu_muc = os.path.abspath(str(thu_muc or "").strip().strip('"'))
    # Một thư mục tạm cho mỗi mức chất lượng: video trọn giữ lại từ lượt trước (nhận ra theo [mã video]) chỉ được dùng
    # lại khi cùng mức — khác mức thì tải lại, không cắt từ bản 720p cũ khi người dùng chọn «Cao nhất». Chụp ảnh tải video
    # KHÔNG tiếng → thư mục riêng, không bao giờ bị lấy để cắt.
    tam = os.path.join(thu_muc, THU_MUC_TAM, f"{'anh' if ds_moc else 'cl'}_{tv.CHAT_LUONG.get(chat_luong)}")
    chi_tieng = tv.CHAT_LUONG.get(chat_luong) == 0
    ket_qua = tv.tai_nhieu(
        list(links),
        tam,
        cau_hinh_mang,
        progress=lambda p, m: bao(0.7 * p, m),
        cancel_check=huy,
        bo_qua_da_co=True,
        chat_luong=chat_luong,
        **({"dinh_dang": _dinh_dang_anh(chat_luong)} if ds_moc else {}),
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
        chung = dict(
            huy=huy,
            bao=lambda f, m, i=i: bao(0.7 + 0.3 * (i + f) / len(ket_qua), m),
            nhan=f"Video {i + 1}/{len(ket_qua)}",
            giu=f"Video đã tải vẫn giữ ở «{tam}», sửa mốc rồi bấm lại thì không phải tải lại.",
        )
        k.update(
            chup_anh(nguon, thu_muc, ds_moc, **chung) if ds_moc
            else cat_hoac_bo(nguon, thu_muc, tu_s, den_s, ds_bo, chuan_hoa_am=chuan_hoa_am, **chung)
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
        do_dai, co_hinh = _do(nguon)[:2]
    except RuntimeError as e:
        return {"trang_thai": "loi", "duong_dan": "", "ghi_chu": str(e)}
    if den_s > do_dai + LECH_DO_DAI_TOI_DA_S:
        return {"trang_thai": "loi", "duong_dan": "",
                "ghi_chu": f"Video chỉ dài {hhmmss(do_dai)} — đoạn {doan} vượt quá. {giu}".strip()}
    # Tên không dấu cách/ký tự đặc biệt (12/11): «Tieu_de_<mã>_00-01-23_00-02-45,5» → «…_00-02-45-5».
    goc = tv.ten_khong_dau(re.sub(r"\.audio$", "", os.path.splitext(os.path.basename(nguon))[0])) or "doan_cat"
    os.makedirs(thu_muc, exist_ok=True)
    moc = "_".join(moc_hien(g, "-").replace(",", "-") for g in (tu_s, den_s))
    dich = tv._ten_trong(thu_muc, f"{goc}_{moc}" + (".mp4" if co_hinh else ".m4a"))
    nhan = f"{nhan}: đang cắt đoạn {doan}" if nhan else f"Đang cắt đoạn {doan}"

    def tien_do(d: dict) -> None:
        giay = int(d.get("out_time_us") or d.get("out_time_ms") or 0) / 1e6
        bao(min(giay / (den_s - tu_s), 1.0), f"{nhan} ({hhmmss(giay)})")

    bao(0.0, nhan + "...")
    r = _cat(nguon, dich, tu_s, den_s, co_hinh, huy=huy, khi_tien_do=tien_do)
    return _kiem_va_chinh_am(
        r, dich, thu_muc, den_s - tu_s, LECH_DO_DAI_TOI_DA_S, chuan_hoa_am=chuan_hoa_am, huy=huy, bao=bao, nhan=nhan,
        giu=giu, ghi_xong=f"Đoạn {doan} ({den_s - tu_s:.3f} s), cắt đúng từng khung hình (nén lại đoạn cắt).",
    )


def _kiem_va_chinh_am(
    r, dich: str, thu_muc: str, dai_yeu_cau: float, lech_toi_da: float, *, chuan_hoa_am: bool, huy, bao, nhan: str,
    giu: str, ghi_xong: str,
) -> dict:
    """Phần chung sau FFmpeg của cắt/bỏ đoạn: dừng/lỗi → dòng kết quả; độ dài ra lệch ``dai_yeu_cau`` quá ``lech_toi_da``
    → đổi tên «.loi», không tin; đúng → tuỳ chọn chỉnh âm lượng."""
    if r.cancelled:
        return {"trang_thai": "bo_qua", "duong_dan": "", "ghi_chu": "Đã dừng theo yêu cầu trong lúc cắt; phần cắt dở đã xoá."}
    if r.returncode != 0 or not os.path.isfile(dich):
        return {"trang_thai": "loi", "duong_dan": "",
                "ghi_chu": f"FFmpeg cắt lỗi: {(r.stderr or r.ly_do or '').strip()[-300:]}"}
    try:
        dai_ra = _do(dich)[0]
        ly_do = (f"file ra dài {dai_ra:.3f} s, yêu cầu {dai_yeu_cau:.3f} s"
                 if abs(dai_ra - dai_yeu_cau) > lech_toi_da else "")
    except RuntimeError as e:
        ly_do = f"không đo lại được file ra ({e})"
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
    return {"trang_thai": "xong", "duong_dan": dich, "ghi_chu": ghi_xong + ghi_am}


def bo_doan(
    nguon: str,
    thu_muc: str,
    ds_bo: list,
    *,
    chuan_hoa_am: bool = False,
    huy: Callable[[], bool] = lambda: False,
    bao: Callable[[float, str], None] = lambda _f, _m: None,
    nhan: str = "",
    giu: str = "",
) -> dict:
    """BỎ các đoạn ``ds_bo`` (từ :func:`doc_ds_doan`: đã xếp, đã gộp) của ``nguon`` rồi nối phần còn lại thành file MỚI
    trong ``thu_muc`` — đúng từng khung hình, kiểm độ dài như :func:`cat_mot`. ``nguon`` KHÔNG bị sửa/xoá ở đây."""
    try:
        do_dai, co_hinh, co_tieng = _do(nguon)
    except RuntimeError as e:
        return {"trang_thai": "loi", "duong_dan": "", "ghi_chu": str(e)}
    vuot = [(a, b) for a, b in ds_bo if b > do_dai + LECH_DO_DAI_TOI_DA_S]
    if vuot:
        return {"trang_thai": "loi", "duong_dan": "",
                "ghi_chu": f"Video chỉ dài {hhmmss(do_dai)} — đoạn {moc_hien(vuot[0][0])}–{moc_hien(vuot[0][1])} vượt "
                           f"quá. {giu}".strip()}
    giu_lai = _phan_giu(ds_bo, do_dai)
    if not giu_lai:
        return {"trang_thai": "loi", "duong_dan": "",
                "ghi_chu": f"Các đoạn bỏ phủ kín cả video — không còn gì để nối. {giu}".strip()}
    if not (co_hinh or co_tieng):
        return {"trang_thai": "loi", "duong_dan": "", "ghi_chu": "File không có hình lẫn tiếng."}
    con_lai = sum((do_dai if b is None else b) - a for a, b in giu_lai)
    goc = tv.ten_khong_dau(re.sub(r"\.audio$", "", os.path.splitext(os.path.basename(nguon))[0])) or "video"
    os.makedirs(thu_muc, exist_ok=True)
    dich = tv._ten_trong(thu_muc, f"{goc}_bo_{len(ds_bo)}_doan" + (".mp4" if co_hinh else ".m4a"))
    nhan = f"{nhan}: đang bỏ {len(ds_bo)} đoạn" if nhan else f"Đang bỏ {len(ds_bo)} đoạn"

    def tien_do(d: dict) -> None:
        giay = int(d.get("out_time_us") or d.get("out_time_ms") or 0) / 1e6
        bao(min(giay / con_lai, 1.0), f"{nhan} ({hhmmss(giay)}/{hhmmss(con_lai)})")

    bao(0.0, nhan + "...")
    r = _bo(nguon, dich, giu_lai, co_hinh, co_tieng, huy=huy, khi_tien_do=tien_do)
    # Mỗi chỗ nối hình/tiếng có thể lệch tối đa ~1 khung hình (mốc rơi giữa hai khung) → nới theo số phần.
    return _kiem_va_chinh_am(
        r, dich, thu_muc, con_lai, LECH_DO_DAI_TOI_DA_S + 0.05 * len(giu_lai), chuan_hoa_am=chuan_hoa_am, huy=huy,
        bao=bao, nhan=nhan, giu=giu,
        ghi_xong=f"Đã bỏ {len(ds_bo)} đoạn ({hhmmss(do_dai - con_lai)}), nối {len(giu_lai)} phần còn lại thành video "
                 f"dài {hhmmss(con_lai)}, đúng từng khung hình (nén lại).",
    )


def _dinh_dang_anh(chat_luong: str) -> dict:
    """yt-dlp cho chụp ảnh: chỉ phần HÌNH (không tải/ghép tiếng), ưu tiên bản SDR — ảnh chụp từ bản HDR ra màu nhạt."""
    cao = tv.CHAT_LUONG[chat_luong]
    loc = f"[height<={cao}]" if cao else ""
    return {"format": f"bv*{loc}[dynamic_range=SDR]/bv*{loc}/b{loc}"}


def chup_anh(
    nguon: str,
    thu_muc: str,
    ds_moc: list,
    *,
    huy: Callable[[], bool] = lambda: False,
    bao: Callable[[float, str], None] = lambda _f, _m: None,
    nhan: str = "",
    giu: str = "",
) -> dict:
    """Chụp ảnh PNG ở từng mốc ``ds_moc`` (giây, từ :func:`doc_ds_moc`) của ``nguon`` vào ``thu_muc``: khung hình ĐẦU
    TIÊN từ mốc trở đi, độ phân giải gốc, không bao giờ ghi đè. ``nguon`` KHÔNG bị sửa/xoá ở đây. Trả
    ``{trang_thai, duong_dan, ghi_chu}`` — ``duong_dan`` = ảnh (một mốc) hoặc ``thu_muc`` (nhiều mốc)."""
    try:
        do_dai, co_hinh = _do(nguon)[:2]
    except RuntimeError as e:
        return {"trang_thai": "loi", "duong_dan": "", "ghi_chu": str(e)}
    if not co_hinh:
        return {"trang_thai": "loi", "duong_dan": "",
                "ghi_chu": "File chỉ có tiếng, không có hình — không chụp ảnh được."}
    vuot = [g for g in ds_moc if g >= do_dai]
    if vuot:
        return {"trang_thai": "loi", "duong_dan": "",
                "ghi_chu": f"Video chỉ dài {hhmmss(do_dai)} — mốc {moc_hien(vuot[0])} vượt quá. {giu}".strip()}
    goc = tv.ten_khong_dau(re.sub(r"\.audio$", "", os.path.splitext(os.path.basename(nguon))[0])) or "anh"
    os.makedirs(thu_muc, exist_ok=True)
    anh: list = []

    def da_chup() -> str:
        return f" Đã chụp {len(anh)} ảnh trước đó: {', '.join(os.path.basename(a) for a in anh)}." if anh else ""

    for j, g in enumerate(ds_moc):
        if huy():
            return {"trang_thai": "bo_qua", "duong_dan": "", "ghi_chu": "Đã dừng theo yêu cầu." + da_chup()}
        bao(j / len(ds_moc), f"{nhan + ': đ' if nhan else 'Đ'}ang chụp ảnh ở {moc_hien(g)}")
        dich = tv._ten_trong(thu_muc, f"{goc}_{moc_hien(g, '-').replace(',', '-')}.png")
        dang = dich + ".dang.png"
        # «-update 1»: tên file là tên thật, không phải mẫu «%d» — thư mục có «%» vẫn đúng.
        r = _chay_ra_file(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{g:.3f}", "-i", nguon,
             "-map", "0:v:0", "-frames:v", "1", "-update", "1", dang],
            dang,
            dich,
            huy=huy,
            khi_tien_do=lambda _d: None,
        )
        if r.cancelled:
            return {"trang_thai": "bo_qua", "duong_dan": "", "ghi_chu": "Đã dừng theo yêu cầu." + da_chup()}
        if r.returncode != 0 or not os.path.isfile(dich):
            # FFmpeg thoát 0 mà không ghi ảnh = mốc nằm sau khung hình cuối (giữa khung cuối và hết video).
            ly_do = ((r.stderr or r.ly_do or "").strip()[-300:] if r.returncode else
                     "không có khung hình nào từ mốc này tới hết video — chọn mốc sớm hơn một chút")
            return {"trang_thai": "loi", "duong_dan": "",
                    "ghi_chu": f"Không chụp được ảnh ở {moc_hien(g)}: {ly_do}.{da_chup()} {giu}".strip()}
        anh.append(dich)
    try:
        s = am_luong.doc_ffprobe(anh[0])["streams"][0]
        co = f" {s['width']}×{s['height']}"
    except (RuntimeError, LookupError):
        co = ""
    return {
        "trang_thai": "xong",
        "duong_dan": anh[0] if len(anh) == 1 else thu_muc,
        "ghi_chu": f"{len(anh)} ảnh PNG{co} (khung hình đúng mốc, độ phân giải gốc): "
                   + ", ".join(os.path.basename(a) for a in anh),
    }


def cat_hoac_bo(nguon: str, thu_muc: str, tu_s, den_s, ds_bo, **kw) -> dict:
    """Có ``ds_bo`` → :func:`bo_doan`; không → :func:`cat_mot` (dùng chung cho tab tải theo link và tab video trong máy)."""
    return bo_doan(nguon, thu_muc, ds_bo, **kw) if ds_bo else cat_mot(nguon, thu_muc, tu_s, den_s, **kw)
