# -*- coding: utf-8 -*-
"""Tải video gốc (hình + tiếng, chất lượng cao nhất) theo link vào thư mục người dùng chọn.

Khác đồng bộ kênh: không nén, không đưa vào kho vân tay, không ghi ``downloaded.txt``/``clips_meta.json`` — chỉ là file
video để người dùng giữ. Mọi tuỳ chọn yt-dlp vẫn đi qua ``CauHinhMang.tuy_chon`` và mọi request qua ``PhienYouTube.chay``
với cùng hai lớp đường lui (cookie ngoài, player client trong) như ``ChannelSync._tai_thu_tung_client``.
"""

from __future__ import annotations

import contextlib
import csv
import gc
import io
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid
from dataclasses import asdict, dataclass
from typing import Callable, Optional

import am_luong
from channel import HAN_DON_TAM_CU_S, ChannelSync, _CoHuyTuHam
from kiem_thoi_luong import hhmmss
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
    LoiMoKhoaTwitch,
    MoKhoaTwitch,
    chay_kem_duong_lui_cookie,
    dung_ban_khuc,
    la_link_twitch,
    tai_song_song,
    thu_tung_client,
)

# Hình tốt nhất + tiếng tốt nhất, ghép bằng FFmpeg; không có cặp thì một luồng có sẵn cả hai.
DINH_DANG = "bv*+ba/b"
# MP4 khi mã hoá hợp (H.264/AV1 + AAC), không thì MKV (VP9/AV1 + Opus — thường là bản 4K của YouTube): không chuyển mã.
VO_GHEP = "mp4/mkv"
THU_MUC_TAM = ".timclip_tai_do"
_RE_FILE_DO = re.compile(r"\.(?:part(?:-Frag\d+)?|ytdl|temp)$|\.temp\.[^.]+$")
# Mức TỐI ĐA (chiều cao khung hình): video gốc thấp hơn thì lấy bản cao nhất có. 0 = chỉ tiếng.
CHAT_LUONG = {
    "Cao nhất": None,
    "4K (2160p)": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "Chỉ tiếng": 0,
}
CHAT_LUONG_MAC_DINH = "Cao nhất"
# Ghép video (D-39): MỌI video cùng một kiểu H.264 ≤ 1080p + AAC trong MP4 để nối bằng `-c copy` (không nén lại). Video
# không có cặp đó thì lấy bản ≤ 1080p bất kỳ — bước kiểm thông số trước khi ghép sẽ báo nó lệch.
DINH_DANG_GHEP = {
    "format": "bv*[vcodec^=avc1][height<=1080]+ba[acodec^=mp4a]/b[vcodec^=avc1][height<=1080][acodec^=mp4a]"
              "/bv*[height<=1080]+ba/b[height<=1080]",
    "merge_output_format": "mp4",
}
# Ảnh lớn nhất YouTube có, đổi sang JPG; không tải video. Không cần định dạng video nào nên không báo lỗi khi thiếu.
TUY_CHON_THUMBNAIL = {
    "skip_download": True,
    "writethumbnail": True,
    "ignore_no_formats_error": True,
    "postprocessors": [
        {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"}
    ],
}
_DUOI_ANH = (".jpg", ".jpeg", ".png", ".webp")
_RE_MA_CUOI_TEN = re.compile(r"\[([A-Za-z0-9_-]{11})\]\.[^.]+$")
# File chỉ-tiếng mang thêm «.audio» trước đuôi: «đã có» của video và của chỉ-tiếng không lẫn nhau.
_RE_MA_CUOI_TEN_TIENG = re.compile(r"\[([A-Za-z0-9_-]{11})\]\.audio\.[^.]+$")
# Dưới mức trống này thì không tải video kế: một lượt tải cả kênh qua đêm không được làm đầy ổ.
TRONG_TOI_THIEU_BYTE = 5 * 10**9


def tuy_chon_dinh_dang(chat_luong: str = CHAT_LUONG_MAC_DINH) -> dict:
    """Phần tuỳ chọn yt-dlp chọn định dạng theo mức chất lượng (khoá của :data:`CHAT_LUONG`)."""
    if chat_luong not in CHAT_LUONG:
        raise ValueError(f"Mức chất lượng không hợp lệ: {chat_luong!r}")
    cao = CHAT_LUONG[chat_luong]
    if cao == 0:
        return {"format": "ba/b"}
    if cao is None:
        return {"format": DINH_DANG, "merge_output_format": VO_GHEP}
    return {
        "format": f"bv*[height<={cao}]+ba/b[height<={cao}]",
        "merge_output_format": VO_GHEP,
    }


def ma_da_co(thu_muc: str, chi_tieng: bool = False) -> set:
    """Mã video đã có file trong ``thu_muc``: video = «[mã].đuôi», chỉ-tiếng = «[mã].audio.đuôi» (ảnh không tính).
    Hai loại tách riêng: có bản chỉ-tiếng không có nghĩa là đã có video, và ngược lại."""
    mau = _RE_MA_CUOI_TEN_TIENG if chi_tieng else _RE_MA_CUOI_TEN
    try:
        ten = os.listdir(thu_muc)
    except OSError:
        return set()
    return {
        m.group(1)
        for t in ten
        if not t.lower().endswith(_DUOI_ANH) and (m := mau.search(t))
    }


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
    # Chỉ ĐUÔI tên đánh dấu file dở (x.part, x.part-Frag3, x.ytdl, x.temp, x.temp.mkv của bộ ghép): tiêu đề có
    # «.part»/«.temp.» ở giữa vẫn là video đã xong.
    return sorted(
        os.path.join(thu_muc, f)
        for f in os.listdir(thu_muc)
        if not _RE_FILE_DO.search(f) and os.path.isfile(os.path.join(thu_muc, f))
    )


def _don_tam_cu(thu_muc: str) -> None:
    """Dọn thư mục tạm của lượt tải đã chết từ lâu (app bị tắt, mất điện giữa lượt) — có thể vài GB «.part».
    Cùng hạn với đồng bộ kênh (``ChannelSync._don_tam_cu``): thư mục tạm còn mới có thể là của lượt khác đang chạy."""
    goc = os.path.join(thu_muc, THU_MUC_TAM)
    han = time.time() - HAN_DON_TAM_CU_S
    with contextlib.suppress(OSError):
        for ten in os.listdir(goc):
            p = os.path.join(goc, ten)
            with contextlib.suppress(OSError):
                if os.path.getmtime(p) < han:
                    shutil.rmtree(p, ignore_errors=True) if os.path.isdir(
                        p
                    ) else os.remove(p)
        os.rmdir(goc)  # chỉ xoá khi rỗng


def tai_nhieu(
    links: list,
    thu_muc: str,
    cau_hinh_mang: Optional[CauHinhMang] = None,
    *,
    player_clients: Optional[list] = None,
    phien: Optional[PhienYouTube] = None,
    progress: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    chat_luong: str = CHAT_LUONG_MAC_DINH,
    thumbnail: bool = False,
    bo_qua_da_co: bool = False,
    dinh_dang: Optional[dict] = None,
    chuan_hoa_am: bool = False,
    mo_khoa_twitch: Optional[MoKhoaTwitch] = None,
) -> list:
    """Tải lần lượt từng link vào ``thu_muc``; trả list dict (:class:`KetQuaTaiVideo`) theo đúng thứ tự link.

    Mỗi video tải vào thư mục tạm riêng trong ``thu_muc`` rồi mới chuyển ra tên cuối (không ghi đè file có sẵn); lỗi,
    Dừng hay đổi player client đều dọn sạch phần dở. Một video lỗi không dừng cả lô — trừ khi cầu dao của phiên mở
    (YouTube chặn bot, 429…): các link còn lại «bỏ qua», không gửi thêm request.

    ``chat_luong``: khoá của :data:`CHAT_LUONG`. ``thumbnail``: chỉ lấy ảnh thumbnail (JPG), không tải video.
    ``bo_qua_da_co``: video đã có file trong ``thu_muc`` (theo «[mã]» ở tên) thì bỏ qua — bấm lại là tải tiếp phần thiếu.
    ``dinh_dang``: tuỳ chọn định dạng yt-dlp thay cho ``chat_luong`` (vd. :data:`DINH_DANG_GHEP`).
    ``chuan_hoa_am``: đưa âm lượng file vừa tải về mức YouTube (:func:`am_luong.chuan_hoa`, D-43).
    ``mo_khoa_twitch``: link Twitch xin danh sách chất lượng qua proxy + cookie twitch.tv rồi tải thẳng (D-44).
    """
    import yt_dlp

    rieng_dinh_dang = (
        dict(TUY_CHON_THUMBNAIL) if thumbnail else dict(dinh_dang) if dinh_dang else tuy_chon_dinh_dang(chat_luong)
    )
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "Máy chưa có FFmpeg — cần FFmpeg để ghép hình và tiếng chất lượng cao. Cài FFmpeg rồi thử lại."
        )
    thu_muc = os.path.abspath(str(thu_muc or "").strip().strip('"'))
    os.makedirs(thu_muc, exist_ok=True)
    _don_tam_cu(thu_muc)
    cau_hinh = cau_hinh_mang or CauHinhMang()
    phien = phien or PhienYouTube()
    clients = list(player_clients or PLAYER_CLIENTS_MAC_DINH)
    bao = progress or (lambda _p, _m: None)
    huy = cancel_check or (lambda: False)
    n = len(links)
    ket_qua: list = []
    chi_tieng = not thumbnail and CHAT_LUONG[chat_luong] == 0
    da_co = ma_da_co(thu_muc, chi_tieng) if bo_qua_da_co else set()
    da_tai: set = set()
    ten_mau = (
        "%(title).150B [%(id)s].audio.%(ext)s"
        if chi_tieng
        else "%(title).150B [%(id)s].%(ext)s"
    )

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
        if ma_tu_url(url) in da_co:
            kq.trang_thai, kq.ghi_chu = "bo_qua", "Đã có trong thư mục."
            continue
        if ma_tu_url(url) in da_tai:
            # Danh sách phát lặp cùng video, hay hai dạng link của một video: tải một lần là đủ.
            kq.trang_thai, kq.ghi_chu = (
                "bo_qua",
                "Trùng video đã tải ở trên trong lượt này.",
            )
            continue
        if not thumbnail and shutil.disk_usage(thu_muc).free < TRONG_TOI_THIEU_BYTE:
            kq.trang_thai = "bo_qua"
            kq.ghi_chu = (
                f"Ổ đĩa chứa thư mục lưu còn dưới {TRONG_TOI_THIEU_BYTE // 10**9} GB trống — "
                "không tải tiếp để khỏi làm đầy ổ. Giải phóng chỗ rồi bấm lại."
            )
            continue
        twitch = None  # (proxy, cookie) khi mở khoá bản cao của Twitch
        if mo_khoa_twitch and mo_khoa_twitch.co() and la_link_twitch(url):
            try:
                twitch = (mo_khoa_twitch.doc_proxy(), mo_khoa_twitch.cookie_twitch())
            except LoiMoKhoaTwitch as e:
                kq.ghi_chu = str(e)
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
        vo_danh: list = []  # client không-cookie đã cứu video này sau khi mọi client có cookie bị 403

        def chay(rieng: dict, url=url, tam=tam, twitch=twitch):
            # Mỗi lần thử (client khác, thử lại khi đứt mạng) bắt đầu từ thư mục rỗng: luồng dở của lần trước có thể
            # là định dạng khác, để lại thì ghép nhầm hoặc thành hai file (xem ChannelSync._tai_thu_tung_client).
            for f in os.listdir(tam):
                with contextlib.suppress(OSError):
                    os.remove(os.path.join(tam, f))
            phien.dem_yeu_cau("download")
            ie = MoKhoaTwitch.trich_qua_proxy(rieng, url, *twitch) if twitch else None
            with yt_dlp.YoutubeDL(rieng) as ydl:
                dung_ban_khuc(ydl)
                return ydl.process_ie_result(ie, download=True) if ie else ydl.extract_info(url, download=True)

        def tai_voi(ch: CauHinhMang, tam=tam, hook=hook, chay=chay, bo_ghi=bo_ghi):
            return thu_tung_client(
                ch.player_clients(clients),
                chay,
                ch.tuy_chon(
                    "download",
                    logger=bo_ghi,
                    **tai_song_song(),
                    **rieng_dinh_dang,
                    outtmpl=os.path.join(tam, ten_mau),
                    noplaylist=True,
                    playlist_items="1",
                    continuedl=False,
                    progress_hooks=[hook],
                ),
                bo_qua=(DaHuyTaiVideo, LoiMoKhoaTwitch),
                khi_that_bai=lambda _ten, _loi: phien.ghi_doi_client(),
                dung_ngay=phien.nen_dung_doi_client,
                khi_lui_khong_cookie=lambda ten, _loi: (
                    vo_danh.append(ten),
                    phien.ghi_tai_khong_dang_nhap_403(ten),
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
                    bo_qua=(DaHuyTaiVideo, LoiMoKhoaTwitch),
                    phien=phien,
                ),
                video_id=ma_tu_url(url),
                cancel_event=_CoHuyTuHam(huy),
                loi_huy=DaHuyTaiVideo,
                bo_qua=(DaHuyTaiVideo, LoiMoKhoaTwitch),
            )
            xong = _file_xong(tam)
            if thumbnail:
                # Bộ chuyển đổi đã thay ảnh gốc (.webp) bằng .jpg; còn lại gì khác thì không phải ảnh cần lấy.
                xong = [f for f in xong if f.lower().endswith(".jpg")]
            if not xong:
                raise RuntimeError(
                    "YouTube không trả ảnh thumbnail cho video này."
                    if thumbnail
                    else "Tải xong nhưng không thấy file video."
                )
            if len(xong) > 1:
                raise RuntimeError(
                    "yt-dlp để lại hình và tiếng thành hai file riêng (chưa ghép được)."
                )
            ghi_am = ""
            if chuan_hoa_am and not thumbnail:
                bao(min((i + 0.97) / n, 1.0), f"{dau}: đang chỉnh âm lượng về mức YouTube...")
                try:
                    ghi_am = am_luong.chuan_hoa(xong[0], huy=huy)
                except am_luong.DaHuyChinhAmLuong as e:
                    raise DaHuyTaiVideo(str(e)) from e
                except RuntimeError as e:
                    ghi_am = f"Chưa chỉnh được âm lượng ({e}) — giữ âm lượng gốc."
            dich = _ten_trong(thu_muc, os.path.basename(xong[0]))
            os.rename(xong[0], dich)
            kq.trang_thai, kq.duong_dan = "xong", dich
            if ma_tu_url(url):
                da_tai.add(ma_tu_url(url))
            kq.tieu_de = str((info or {}).get("title") or "")
            kq.chat_luong = "ảnh JPG" if thumbnail else mo_ta_chat_luong(info or {})
            if cau_hinh.co_cookie and (
                phien.khong_dang_nhap_ly_do or phien.cookie_bi_tu_choi
            ):
                kq.ghi_chu = "Tải KHÔNG đăng nhập: cookie đã cấu hình nhưng chưa dùng được (xem «Trạng thái YouTube»)."
            elif vo_danh:
                kq.ghi_chu = (
                    "Tải KHÔNG đăng nhập: mọi cách có đăng nhập bị YouTube từ chối (HTTP 403), bản này tải bằng "
                    f"client «{vo_danh[-1]}» không cookie — chất lượng có thể thấp hơn."
                )
            ghi_tw = (
                "Twitch: danh sách chất lượng lấy qua "
                + " + ".join(x for x, co in (("proxy", twitch[0]), ("đăng nhập", twitch[1])) if co)
                + ", video tải thẳng."
                if twitch
                else ""
            )
            kq.ghi_chu = " ".join(x for x in (kq.ghi_chu, ghi_tw, ghi_am) if x)
        except LoiMoKhoaTwitch as e:  # đi thẳng ra (bo_qua): không thử client khác, không phân loại như lỗi YouTube
            kq.ghi_chu = str(e)
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
            if os.path.exists(tam):
                # Dừng giữa lúc tải song song: yt-dlp không đóng file .part, handle nằm trong vòng tham chiếu
                # frame ↔ traceback — chỉ gc mới đóng, mà Windows không cho xoá file đang mở (đo thật 09/11).
                gc.collect()
                shutil.rmtree(tam, ignore_errors=True)
            with contextlib.suppress(OSError):
                os.rmdir(os.path.join(thu_muc, THU_MUC_TAM))  # chỉ xoá khi rỗng
    bao(1.0, "Xong.")
    return [asdict(k) for k in ket_qua]


def tai_kenh(
    url_kenh: str,
    thu_muc: str,
    cau_hinh_mang: Optional[CauHinhMang] = None,
    *,
    gioi_han: Optional[int] = None,
    phien: Optional[PhienYouTube] = None,
    progress: Optional[Callable[[float, str], None]] = None,
    **kw,
) -> list:
    """Tải video ở tab Videos của kênh (``gioi_han`` video mới nhất; rỗng/0 = cả kênh) vào ``thu_muc``.

    Video đã có file trong thư mục thì bỏ qua: bấm lại là tải tiếp phần còn thiếu. ``kw`` chuyển cho :func:`tai_nhieu`.
    Kênh bị chặn/không đọc được thì ném lỗi đã phân loại — không coi là «kênh không có video»."""
    phien = phien or PhienYouTube()
    if progress:
        progress(0.0, "Đang lấy danh sách video của kênh...")
    ds = ChannelSync.list_channel(
        str(url_kenh or "").strip(),
        gioi_han or None,
        cau_hinh_mang=cau_hinh_mang,
        phien_youtube=phien,
    )
    if not ds:
        raise RuntimeError("Kênh không có video nào ở tab Videos.")
    return tai_nhieu(
        [v.url for v in ds],
        thu_muc,
        cau_hinh_mang,
        phien=phien,
        progress=progress,
        bo_qua_da_co=True,
        **kw,
    )



COT_TIEU_DE = ("STT", "Tiêu đề", "Link", "Thời lượng")


def tieu_de_kenh(url_kenh: str, cau_hinh_mang: Optional[CauHinhMang] = None, *,
                 phien: Optional[PhienYouTube] = None) -> list:
    """Tiêu đề + link + thời lượng mọi video ở tab Videos của kênh, mới nhất trước — MỘT lượt liệt kê nhanh, không tải
    gì (D-38). Mỗi dòng là dict theo :data:`COT_TIEU_DE`; thời lượng không biết (live) để trống. Kênh bị chặn/không đọc
    được thì ném lỗi đã phân loại; kênh rỗng → ``RuntimeError``."""
    ds = ChannelSync.list_channel(str(url_kenh or "").strip(), cau_hinh_mang=cau_hinh_mang,
                                  phien_youtube=phien or PhienYouTube())
    if not ds:
        raise RuntimeError("Kênh không có video nào ở tab Videos.")
    return [{"STT": i, "Tiêu đề": v.title, "Link": f"https://www.youtube.com/watch?v={v.id}",
             "Thời lượng": hhmmss(v.duration) if v.duration > 0 else ""} for i, v in enumerate(ds, 1)]


def csv_tieu_de(dong: list) -> bytes:
    """CSV có BOM (Excel đọc đúng tiếng Việt); ô có thể bị hiểu là công thức (``=`` ``+`` ``-`` ``@``) được chặn."""
    from engine import o_bang_tinh_an_toan        # engine nặng: chỉ nạp khi xuất file

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COT_TIEU_DE)
    w.writerows([o_bang_tinh_an_toan(d[c]) for c in COT_TIEU_DE] for d in dong)
    return buf.getvalue().encode("utf-8-sig")


def txt_tieu_de(dong: list) -> bytes:
    """Mỗi dòng một tiêu đề, nguyên văn (file chữ không có công thức)."""
    return "".join(d["Tiêu đề"] + "\r\n" for d in dong).encode("utf-8")


def ten_file_kenh(url_kenh: str) -> str:
    """Tên file (không đuôi) theo @tên hoặc mã UC… của kênh; không nhận ra thì ``tieu_de_kenh``."""
    m = re.search(r"/@([^/?#]+)", url_kenh or "") or re.search(r"/channel/(UC[\w-]+)", url_kenh or "")
    ten = re.sub(r'[\\/:*?"<>|\s]+', "_", urllib.parse.unquote(m.group(1))).strip("._") if m else ""
    return f"tieu_de_{ten or 'kenh'}"


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
