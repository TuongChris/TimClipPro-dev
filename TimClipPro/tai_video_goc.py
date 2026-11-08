# -*- coding: utf-8 -*-
"""Tải video gốc (hình + tiếng, chất lượng cao nhất) theo link vào thư mục người dùng chọn.

Khác đồng bộ kênh: không nén, không đưa vào kho vân tay, không ghi ``downloaded.txt``/``clips_meta.json`` — chỉ là file
video để người dùng giữ. Mọi tuỳ chọn yt-dlp vẫn đi qua ``CauHinhMang.tuy_chon`` và mọi request qua ``PhienYouTube.chay``
với cùng hai lớp đường lui (cookie ngoài, player client trong) như ``ChannelSync._tai_thu_tung_client``.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import urllib.parse
import uuid
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from truy_cap_youtube import (
    PhienYouTube,
    che_bi_mat,
    ma_tu_url,
    phan_loai_loi,
    tom_tat_ky_thuat,
)
from ytdlp_chung import (
    PLAYER_CLIENTS_MAC_DINH,
    BoGhiYtdlp,
    CauHinhMang,
    chay_kem_duong_lui_cookie,
    thu_tung_client,
)

# Hình tốt nhất + tiếng tốt nhất, ghép bằng FFmpeg; không có cặp thì một luồng có sẵn cả hai.
DINH_DANG = "bv*+ba/b"
# MP4 khi mã hoá hợp (H.264/AV1 + AAC), không thì MKV (VP9/AV1 + Opus — thường là bản 4K của YouTube): không chuyển mã.
VO_GHEP = "mp4/mkv"
THU_MUC_TAM = ".timclip_tai_do"
_DUOI_DO_DANG = (".part", ".ytdl", ".temp")


class DaHuyTaiVideo(RuntimeError):
    """Người dùng bấm Dừng giữa lượt tải."""


@dataclass
class KetQuaTaiVideo:
    url: str
    trang_thai: str  # "xong" | "loi" | "bo_qua"
    duong_dan: str = ""
    tieu_de: str = ""
    chat_luong: str = ""
    ghi_chu: str = ""


def tach_link(van_ban: str) -> list:
    """Mỗi dòng một link; bỏ dòng trống và link lặp lại (giữ thứ tự)."""
    ra: list = []
    for dong in (van_ban or "").splitlines():
        dong = dong.strip().strip('"')
        if dong and dong not in ra:
            ra.append(dong)
    return ra


def kiem_link(url: str) -> str:
    """Lý do link KHÔNG tải được (rỗng = được). Link kênh/playlist YouTube bị từ chối: tải cả kênh là việc của
    «Đồng bộ kênh gốc», không được lặng lẽ kéo về hàng trăm video."""
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        return "Không phải link (phải bắt đầu bằng http:// hoặc https://)."
    host = p.netloc.lower().split(":")[0]
    if (
        host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")
    ) and not ma_tu_url(url):
        return "Đây là link kênh/danh sách phát, không phải một video — dán link của từng video."
    return ""


def mo_ta_chat_luong(info: dict) -> str:
    """«2160p60 · vp9 + opus» từ info của yt-dlp (rỗng nếu không đọc được)."""
    if not isinstance(info, dict):
        return ""
    cao, fps = info.get("height"), info.get("fps")
    phan = []
    if cao:
        phan.append(
            f"{cao}p"
            + (f"{int(fps)}" if isinstance(fps, (int, float)) and fps > 30 else "")
        )
    ma = [
        str(info.get(k)).split(".")[0]
        for k in ("vcodec", "acodec")
        if info.get(k) not in (None, "none")
    ]
    if ma:
        phan.append(" + ".join(ma))
    return " · ".join(phan)


def _ten_trong(thu_muc: str, ten: str) -> str:
    """Đường dẫn chưa có file trong ``thu_muc``: trùng tên thì thêm « (2)», « (3)»… — không bao giờ ghi đè."""
    goc, duoi = os.path.splitext(ten)
    dich, i = os.path.join(thu_muc, ten), 2
    while os.path.lexists(dich):
        dich, i = os.path.join(thu_muc, f"{goc} ({i}){duoi}"), i + 1
    return dich


def _file_xong(thu_muc: str) -> list:
    return sorted(
        os.path.join(thu_muc, f)
        for f in os.listdir(thu_muc)
        if not f.endswith(_DUOI_DO_DANG)
        and ".temp." not in f
        and ".part" not in f
        and os.path.isfile(os.path.join(thu_muc, f))
    )


def tai_nhieu(
    links: list,
    thu_muc: str,
    cau_hinh_mang: Optional[CauHinhMang] = None,
    *,
    player_clients: Optional[list] = None,
    phien: Optional[PhienYouTube] = None,
    progress: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> list:
    """Tải lần lượt từng link vào ``thu_muc``; trả list dict (:class:`KetQuaTaiVideo`) theo đúng thứ tự link.

    Mỗi video tải vào thư mục tạm riêng trong ``thu_muc`` rồi mới chuyển ra tên cuối (không ghi đè file có sẵn); lỗi,
    Dừng hay đổi player client đều dọn sạch phần dở. Một video lỗi không dừng cả lô — trừ khi cầu dao của phiên mở
    (YouTube chặn bot, 429…): các link còn lại «bỏ qua», không gửi thêm request.
    """
    import yt_dlp

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "Máy chưa có FFmpeg — cần FFmpeg để ghép hình và tiếng chất lượng cao. Cài FFmpeg rồi thử lại."
        )
    thu_muc = os.path.abspath(str(thu_muc or "").strip().strip('"'))
    os.makedirs(thu_muc, exist_ok=True)
    cau_hinh = cau_hinh_mang or CauHinhMang()
    phien = phien or PhienYouTube()
    clients = list(player_clients or PLAYER_CLIENTS_MAC_DINH)
    bao = progress or (lambda _p, _m: None)
    huy = cancel_check or (lambda: False)
    n = len(links)
    ket_qua: list = []

    for i, url in enumerate(links):
        kq = KetQuaTaiVideo(url=url, trang_thai="loi")
        ket_qua.append(kq)
        if huy():
            kq.trang_thai, kq.ghi_chu = (
                "bo_qua",
                "Đã dừng theo yêu cầu trước khi tải video này.",
            )
            continue
        if phien.mo:
            kq.trang_thai, kq.ghi_chu = "bo_qua", phien.thong_bao_dung()
            continue
        ly_do = kiem_link(url)
        if ly_do:
            kq.ghi_chu = ly_do
            continue
        tam = os.path.join(thu_muc, THU_MUC_TAM, uuid.uuid4().hex[:12])
        os.makedirs(tam, exist_ok=True)
        dau = f"Video {i + 1}/{n}"
        bao(i / n, f"{dau}: đang lấy thông tin...")

        def hook(d: dict, i=i, dau=dau) -> None:
            if huy():
                raise DaHuyTaiVideo("Đã dừng theo yêu cầu trong lúc tải.")
            if d.get("status") != "downloading":
                if d.get("status") == "finished":
                    bao(
                        min((i + 0.95) / n, 1.0),
                        f"{dau}: tải xong một luồng, đang xử lý tiếp...",
                    )
                return
            tong = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            da = d.get("downloaded_bytes") or 0
            p = min(da / tong, 1.0) if tong else 0.0
            la_hinh = (d.get("info_dict") or {}).get("vcodec") not in (None, "none")
            # Hình chiếm gần hết dung lượng: 0–90% là hình, 90–100% là tiếng.
            phan = 0.9 * p if la_hinh else 0.9 + 0.1 * p
            mb = (
                f"{da / 1e6:,.0f}/{tong / 1e6:,.0f} MB"
                if tong
                else f"{da / 1e6:,.0f} MB"
            )
            bao(
                min((i + phan) / n, 1.0),
                f"{dau}: đang tải {'hình' if la_hinh else 'tiếng'} {p * 100:.0f}% ({mb})",
            )

        bo_ghi = BoGhiYtdlp(phien)

        def chay(rieng: dict, url=url, tam=tam):
            # Mỗi lần thử (client khác, thử lại khi đứt mạng) bắt đầu từ thư mục rỗng: luồng dở của lần trước có thể
            # là định dạng khác, để lại thì ghép nhầm hoặc thành hai file (xem ChannelSync._tai_thu_tung_client).
            for f in os.listdir(tam):
                with contextlib.suppress(OSError):
                    os.remove(os.path.join(tam, f))
            phien.dem_yeu_cau("download")
            with yt_dlp.YoutubeDL(rieng) as ydl:
                return ydl.extract_info(url, download=True)

        def tai_voi(ch: CauHinhMang, tam=tam, hook=hook, chay=chay, bo_ghi=bo_ghi):
            return thu_tung_client(
                ch.player_clients(clients),
                chay,
                ch.tuy_chon(
                    "download",
                    logger=bo_ghi,
                    format=DINH_DANG,
                    merge_output_format=VO_GHEP,
                    outtmpl=os.path.join(tam, "%(title).150B [%(id)s].%(ext)s"),
                    noplaylist=True,
                    playlist_items="1",
                    continuedl=False,
                    progress_hooks=[hook],
                ),
                bo_qua=(DaHuyTaiVideo,),
                khi_that_bai=lambda _ten, _loi: phien.ghi_doi_client(),
                dung_ngay=phien.nen_dung_doi_client,
                khi_lui_khong_cookie=lambda ten, _loi: (
                    phien.ghi_tai_khong_dang_nhap_403(ten)
                ),
            )

        try:
            info = phien.chay(
                "download",
                lambda tai_voi=tai_voi, bo_ghi=bo_ghi: chay_kem_duong_lui_cookie(
                    cau_hinh,
                    tai_voi,
                    khi_bo_cookie=phien.ghi_lui_cookie,
                    bo_ghi=bo_ghi,
                    bo_qua=(DaHuyTaiVideo,),
                    phien=phien,
                ),
                video_id=ma_tu_url(url),
                cancel_event=_CoHuy(huy),
                loi_huy=DaHuyTaiVideo,
                bo_qua=(DaHuyTaiVideo,),
            )
            xong = _file_xong(tam)
            if not xong:
                raise RuntimeError("Tải xong nhưng không thấy file video.")
            if len(xong) > 1:
                raise RuntimeError(
                    "yt-dlp để lại hình và tiếng thành hai file riêng (chưa ghép được)."
                )
            dich = _ten_trong(thu_muc, os.path.basename(xong[0]))
            os.rename(xong[0], dich)
            kq.trang_thai, kq.duong_dan = "xong", dich
            kq.tieu_de = str((info or {}).get("title") or "")
            kq.chat_luong = mo_ta_chat_luong(info or {})
            if cau_hinh.co_cookie and (
                phien.khong_dang_nhap_ly_do or phien.cookie_bi_tu_choi
            ):
                kq.ghi_chu = "Tải KHÔNG đăng nhập: cookie đã cấu hình nhưng chưa dùng được (xem «Trạng thái YouTube»)."
        except DaHuyTaiVideo:
            kq.trang_thai, kq.ghi_chu = (
                "bo_qua",
                "Đã dừng theo yêu cầu; phần tải dở đã xoá.",
            )
        except Exception as e:  # noqa: BLE001 — một video lỗi không làm đứt cả lô
            f = phan_loai_loi(e, thao_tac="download", video_id=ma_tu_url(url))
            kq.ghi_chu = che_bi_mat(f.human_message_vi or tom_tat_ky_thuat(e))
        finally:
            shutil.rmtree(tam, ignore_errors=True)
            with contextlib.suppress(OSError):
                os.rmdir(os.path.join(thu_muc, THU_MUC_TAM))  # chỉ xoá khi rỗng
    bao(1.0, "Xong.")
    return [asdict(k) for k in ket_qua]


# Chạy ở tiến trình con: tkinter không chạy được trong luồng của Streamlit. Ghi UTF-8 thẳng ra stdout (đường dẫn tiếng Việt).
_HOP_THOAI = """
import sys, tkinter
from tkinter import filedialog
r = tkinter.Tk(); r.withdraw(); r.attributes('-topmost', True)
p = filedialog.askdirectory(initialdir=sys.argv[1] or None, title='Chọn thư mục lưu video', mustexist=False)
sys.stdout.buffer.write((p or '').encode('utf-8'))
"""


def chon_thu_muc(ban_dau: str = "") -> str:
    """Mở hộp thoại chọn thư mục của Windows trên máy đang chạy Tool; rỗng = người dùng bấm Huỷ.
    Không mở được (máy thiếu tkinter, quá 10 phút không chọn) → ``RuntimeError`` kèm cách làm tay."""
    try:
        r = subprocess.run(
            [sys.executable, "-I", "-c", _HOP_THOAI, ban_dau or ""],
            capture_output=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(
            f"Không mở được hộp thoại chọn thư mục ({e}) — hãy dán đường dẫn vào ô."
        ) from e
    if r.returncode != 0:
        raise RuntimeError(
            "Không mở được hộp thoại chọn thư mục — hãy dán đường dẫn vào ô."
        )
    p = r.stdout.decode("utf-8", "replace").strip()
    return os.path.normpath(p) if p else ""


class _CoHuy:
    """Bọc ``cancel_check`` thành đối tượng có ``is_set()`` cho ``PhienYouTube.chay`` (huỷ được trong lúc nghỉ thử lại)."""

    def __init__(self, ham: Callable[[], bool]):
        self._ham = ham

    def is_set(self) -> bool:
        return bool(self._ham())
