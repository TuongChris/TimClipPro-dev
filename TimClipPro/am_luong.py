# -*- coding: utf-8 -*-
"""Đưa âm lượng video/tiếng đã tải về mức YouTube (D-43, người dùng chọn 10/11).

Đo thật 10/11: video Joe Bartolozzi tải về -28,5 LUFS, video SSS/TikTok -14. Xem trên YouTube nghe to vì «Âm lượng ổn định»
(luồng tiếng nén dải động) — tắt đi thì nhỏ y như file tải. Ở đây: ``loudnorm`` hai lượt của FFmpeg (đo rồi chỉnh) về
:data:`MUC_LUFS`, đỉnh ≤ :data:`TRAN_DINH_DBTP` (không rè); hình CHÉP NGUYÊN, chỉ tiếng nén lại. Đã gần mức (≤
:data:`DUNG_SAI_LU`) thì giữ nguyên từng byte — gọi lại nhiều lần không nén lại lần nữa.
"""

from __future__ import annotations

import json
import os
import re
from typing import Callable, Optional

from channel import _CoHuyTuHam
from process_runner import IM_LANG_FFMPEG_S, TRAN_FFPROBE_S, chay_lenh_media

MUC_LUFS = -14.0  # mức YouTube chuẩn hoá về
TRAN_DINH_DBTP = -1.0
DUNG_SAI_LU = 1.0
_LOC = f"loudnorm=I={MUC_LUFS:g}:TP={TRAN_DINH_DBTP:g}:LRA=20"
_DUOI_OPUS = (".webm", ".opus", ".ogg")  # vỏ chỉ nhận opus/vorbis


class DaHuyChinhAmLuong(RuntimeError):
    """Người dùng bấm Dừng trong lúc đo/chỉnh âm lượng (file gốc giữ nguyên)."""


def doc_ffprobe(path: str) -> dict:
    """``ffprobe -show_streams -show_format`` dạng dict; không đọc được → ``RuntimeError`` (câu tiếng Việt)."""
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
    return json.loads(r.stdout or "{}")


def _chay(lenh: list, huy, khi_tien_do):
    r = chay_lenh_media(
        lenh,
        cancel_event=_CoHuyTuHam(huy),
        im_lang_toi_da_s=IM_LANG_FFMPEG_S,
        theo_doi_tien_do=True,
        khi_tien_do=khi_tien_do,
    )
    if r.cancelled:
        raise DaHuyChinhAmLuong("Đã dừng theo yêu cầu trong lúc chỉnh âm lượng.")
    return r


def chuan_hoa(
    path: str,
    *,
    huy: Optional[Callable[[], bool]] = None,
    khi_tien_do: Optional[Callable[[dict], None]] = None,
) -> str:
    """Chuẩn hoá âm lượng ``path`` TẠI CHỖ (ghi file tạm rồi mới thay). Trả câu ghi chú; ffmpeg hỏng → ``RuntimeError``,
    bị Dừng → :class:`DaHuyChinhAmLuong` — cả hai đều giữ nguyên file gốc."""
    huy = huy or (lambda: False)
    r = _chay(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            path,
            "-vn",
            "-af",
            f"{_LOC}:print_format=json",
            "-f",
            "null",
            "-",
        ],
        huy,
        khi_tien_do,
    )
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr or "")
    if r.returncode != 0 or not m:
        raise RuntimeError(
            f"Không đo được âm lượng «{os.path.basename(path)}»: {(r.stderr or r.ly_do or '').strip()[-200:]}"
        )
    do = json.loads(m.group(0))
    try:
        vao = float(do["input_i"])
    except ValueError:  # «-inf»: cả file im lặng
        return "Âm lượng: file không có tiếng, giữ nguyên."
    if vao == float("-inf") or vao < -70:
        return "Âm lượng: file không có tiếng, giữ nguyên."
    if abs(vao - MUC_LUFS) <= DUNG_SAI_LU:
        return f"Âm lượng đã ở mức YouTube ({vao:.1f} LUFS), giữ nguyên."
    tieng = next(
        (
            s
            for s in doc_ffprobe(path).get("streams", [])
            if s.get("codec_type") == "audio"
        ),
        {},
    )
    goc, duoi = os.path.splitext(path)
    ma = (
        ["libopus", "-b:a", "160k"]
        if duoi.lower() in _DUOI_OPUS
        else ["aac", "-b:a", "192k"]
    )
    dang = f"{goc}.dang_am{duoi}"
    loc = (
        f"{_LOC}:measured_I={do['input_i']}:measured_TP={do['input_tp']}:measured_LRA={do['input_lra']}"
        f":measured_thresh={do['input_thresh']}:offset={do['target_offset']}:linear=true"
    )
    try:
        r = _chay(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                path,
                "-map",
                "0",
                "-c",
                "copy",
                "-c:a",
                *ma,
                "-ar",
                str(tieng.get("sample_rate") or 48000),
                "-af",
                loc,
                dang,
            ],
            huy,
            khi_tien_do,
        )
        if r.returncode != 0 or not os.path.isfile(dang):
            raise RuntimeError(
                f"FFmpeg chỉnh âm lượng lỗi: {(r.stderr or r.ly_do or '').strip()[-200:]}"
            )
        os.replace(dang, path)
    finally:
        if os.path.exists(dang):
            os.remove(dang)
    return f"Âm lượng {vao:.1f} → {MUC_LUFS:g} LUFS (mức YouTube)."
