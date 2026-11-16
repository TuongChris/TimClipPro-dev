# -*- coding: utf-8 -*-
"""YouTube Data API v3 — lấy thông tin video (tiêu đề, kênh, thời lượng, ngày đăng); yt-dlp chỉ còn tải (D-51).

Hợp đồng: ``docs/YOUTUBE_DATA_API.md``. Có khoá thì ``videos.list`` (tối đa 50 mã một lượt, 1 đơn vị hạn mức). Không
khoá, khoá sai dạng, API tắt hay lỗi: nơi gọi lấy các mã trong ``KetQuaApi.thieu`` bằng đường yt-dlp CŨ, không đổi gì.
Lỗi API là GIÁ TRỊ trả về (không ném ra nơi gọi) và chỉ ghi vào phiên con ``PhienYouTube.api`` — không bao giờ qua cầu
dao / bộ đếm / phân loại của yt-dlp (chính sách thuần ở ``truy_cap_youtube``).

Khoá: file cố định ``<thư mục cha của data_dir>/secrets/youtube_api_key.txt`` — không ô nhập, không biến môi trường.
Không bao giờ in, ghi log hay hiện bất kỳ phần nào của khoá; gửi bằng header ``X-Goog-Api-Key`` không đi theo chuyển
hướng, không đặt trong URL. Mạng: stdlib ``urllib`` (không thêm thư viện), timeout = ``CauHinhMang.network_timeout_s``,
không giãn nhịp ``sleep_requests_s`` (dành cho bot-check youtube.com), proxy hệ thống như yt-dlp.
"""

from __future__ import annotations

import html
import http.client
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

import truy_cap_youtube as tc
from ytdlp_chung import CauHinhMang

LOGGER = logging.getLogger("youtube.api")

GOC_API = "https://www.googleapis.com/youtube/v3/"
TEN_FILE_KHOA = "youtube_api_key.txt"
GIOI_HAN_FILE_KHOA = 4 * 1024
GIOI_HAN_THAN = 4 * 1024 * 1024
LO_TOI_DA = 50

_RE_KHOA = re.compile(r"AIza[0-9A-Za-z_-]{35}")
_RE_MA = re.compile(r"[A-Za-z0-9_-]{11}")
_RE_THOI_LUONG = re.compile(r"P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)(?:\.\d+)?S)?)?")
_HOST_API = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be",
                       "youtube-nocookie.com", "www.youtube-nocookie.com"})

_PART = "snippet,contentDetails,liveStreamingDetails"
_FIELDS = ("items(id,snippet(title,channelId,channelTitle,publishedAt,liveBroadcastContent),"
           "contentDetails(duration),liveStreamingDetails(actualStartTime)")
_TRUONG_SNIPPET = ("title", "channelId", "channelTitle", "publishedAt", "liveBroadcastContent")

# Lý do một mã nằm trong ``thieu`` (ngoài ``truy_cap_youtube.THONG_BAO_API`` khi API đã tắt).
LY_DO_SAI_KHOA = "Khoá YouTube Data API sai dạng"
LY_DO_CHUA_CO_KHOA = "Chưa có khoá YouTube Data API"   # chỉ nơi gọi ``_goi`` thấy; ``lay_video`` trả lý do rỗng
LY_DO_CAU_DAO = "Đã dừng yêu cầu mới tới YouTube (cầu dao của lượt đang mở)"
LY_DO_DA_HUY = "Đã dừng theo yêu cầu"
LY_DO_TAM_THOI = "YouTube Data API lỗi mạng / máy chủ tạm thời (đã thử lại một lần)"
LY_DO_VANG = "YouTube Data API không trả thông tin (video riêng tư, đã gỡ hoặc sai mã)"
LY_DO_SAP_PHAT = "Video sắp công chiếu / đang phát trực tiếp"
LY_DO_MA_SAI = "Mã video không hợp lệ"


# =====================================================================
#  Khoá
# =====================================================================

def duong_dan_khoa_api(data_dir: str) -> str:
    """Đường dẫn CỐ ĐỊNH của file khoá: DEV PC2 = ``C:\\Dev\\TimClipPro_DevState\\secrets\\…``; managed =
    ``<state_root>\\secrets\\…``; legacy = ``<thư mục mã>\\secrets\\…`` (đã gitignore)."""
    return os.path.join(os.path.dirname(os.path.abspath(data_dir)), "secrets", TEN_FILE_KHOA)


class LoiKhoaApi(ValueError):
    """File khoá sai dạng. Thông điệp chỉ nêu TÊN file — không thư mục, không gì của khoá."""


_BO_NHO_KHOA: dict = {}  # đường dẫn -> ((mtime_ns, cỡ), khoá, lỗi)


def doc_khoa_api(path: str) -> str:
    """Khoá trong file ``path``; "" khi chưa có file. Sai dạng → ``LoiKhoaApi``. Nhớ theo (đường dẫn, giờ sửa, cỡ)."""
    ten = os.path.basename(path)
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return ""
    except OSError:
        st = None
    if st is None:
        raise LoiKhoaApi(f"Không đọc được file {ten}.")
    dau = (st.st_mtime_ns, st.st_size)
    cu = _BO_NHO_KHOA.get(path)
    if cu is None or cu[0] != dau:
        cu = _BO_NHO_KHOA[path] = (dau, *_doc_file_khoa(path, ten))
    if cu[2]:
        raise LoiKhoaApi(cu[2])
    return cu[1]


def _doc_file_khoa(path: str, ten: str) -> tuple:
    """``(khoá, "")`` hoặc ``("", lý do)``. Không ném: lỗi gốc (có thể mang byte của khoá) không được bám theo lỗi khoá."""
    try:
        with open(path, "rb") as f:
            tho = f.read(GIOI_HAN_FILE_KHOA + 1)
    except OSError:
        return "", f"Không đọc được file {ten}."
    if len(tho) > GIOI_HAN_FILE_KHOA:
        return "", f"File {ten} lớn hơn 4 KB — file chỉ chứa đúng một dòng khoá."
    if tho[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in tho:
        return "", (f"File {ten} đang lưu dạng UTF-16 («Unicode») — lưu lại dạng UTF-8 (Notepad: «Lưu thành…», "
                    "mục mã hoá chọn UTF-8).")
    try:
        van_ban = tho.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "", f"File {ten} không phải văn bản UTF-8 — lưu lại dạng UTF-8."
    dong = [d for d in (x.strip() for x in van_ban.splitlines()) if d and not d.startswith("#")]
    if not dong:
        return "", f"File {ten} không có dòng khoá nào (dòng trống và dòng bắt đầu bằng # bị bỏ qua)."
    if len(dong) > 1:
        return "", f"File {ten} có nhiều hơn một dòng khoá — chỉ để đúng một dòng."
    if not _RE_KHOA.fullmatch(dong[0]):
        return "", (f"Dòng khoá trong file {ten} không đúng dạng khoá API của Google (bắt đầu bằng «AIza», 39 ký tự, "
                    "không dấu cách hay dấu nháy).")
    return dong[0], ""


def _doc_khoa_cho(data_dir: str) -> str:
    """Khoá của ``data_dir`` ("" = chưa có; sai dạng → ``LoiKhoaApi``). MỌI phép đọc khoá theo ``data_dir`` đi qua đây —
    tests/conftest.py thay hàm này bằng «chưa có khoá» cho mọi test (máy có khoá thật không gửi yêu cầu nào)."""
    return doc_khoa_api(duong_dan_khoa_api(data_dir))


CHUA_CO, SAI_DANG, CO_KHOA = "CHUA_CO", "SAI_DANG", "CO_KHOA"


@dataclass(frozen=True)
class TrangThaiKhoaApi:
    """Trạng thái khoá cho thanh bên «🔐 Kết nối YouTube» / ``cli.py youtube-doctor`` — KHÔNG mang khoá (repr an toàn)."""

    ma: str                 # CHUA_CO | SAI_DANG | CO_KHOA
    ly_do: str = ""         # SAI_DANG: vì sao (tiếng Việt, chỉ nêu tên file)
    duong_dan: str = ""     # nơi đặt file khoá

    @property
    def cau(self) -> str:
        if self.ma == CO_KHOA:
            return "Đã có khoá YouTube Data API — tiêu đề, kênh, thời lượng, ngày đăng lấy bằng API; yt-dlp chỉ còn tải."
        if self.ma == SAI_DANG:
            return f"Khoá YouTube Data API không dùng được: {self.ly_do} Thông tin video lấy bằng yt-dlp như cũ."
        return (f"Chưa có khoá YouTube Data API — thông tin video lấy bằng yt-dlp như cũ. Muốn dùng API: đặt file khoá "
                f"ở {self.duong_dan}.")


def trang_thai_khoa(data_dir: str) -> TrangThaiKhoaApi:
    """Chỉ đọc file khoá (không gọi mạng)."""
    duong_dan = duong_dan_khoa_api(data_dir)
    try:
        khoa = _doc_khoa_cho(data_dir)
    except LoiKhoaApi as e:
        return TrangThaiKhoaApi(SAI_DANG, str(e), duong_dan)
    return TrangThaiKhoaApi(CO_KHOA if khoa else CHUA_CO, "", duong_dan)


# =====================================================================
#  Link, thời lượng
# =====================================================================

def ma_video_cho_api(url: Any) -> str:
    """Mã video (đúng 11 ký tự) của link dùng được API: chỉ host YouTube, dạng ``watch?v=``, ``youtu.be/``, ``/shorts/``,
    ``/live/``, ``/embed/``. Khác (Twitch, kênh, danh sách phát, trang khác, host giả dạng) → "" = đường yt-dlp như cũ."""
    try:
        p = urllib.parse.urlsplit(str(url or "").strip())
    except ValueError:
        return ""
    host = p.hostname or ""
    if p.scheme not in ("http", "https") or host not in _HOST_API:
        return ""
    phan = [x for x in p.path.split("/") if x]
    if host == "youtu.be":
        ma = phan[0] if len(phan) == 1 else ""
    elif phan == ["watch"]:
        ma = (urllib.parse.parse_qs(p.query).get("v") or [""])[0]
    elif len(phan) == 2 and phan[0] in ("shorts", "live", "embed"):
        ma = phan[1]
    else:
        ma = ""
    # «/embed/videoseries?list=…» là danh sách phát nhúng — chữ «videoseries» tình cờ đủ 11 ký tự.
    return ma if _RE_MA.fullmatch(ma) and ma != "videoseries" else ""


def thoi_luong_giay(gia_tri: Any) -> int:
    """Giây từ ISO 8601 ``contentDetails.duration`` (PT1H2M3S = 3723, P1DT2H = 93600); P0D / thiếu / lạ → 0 = chưa biết."""
    m = _RE_THOI_LUONG.fullmatch(gia_tri) if isinstance(gia_tri, str) else None
    if not m:
        return 0
    tuan, ngay, gio, phut, giay = (int(x or 0) for x in m.groups())
    return (((tuan * 7 + ngay) * 24 + gio) * 60 + phut) * 60 + giay


# =====================================================================
#  Truyền tải
# =====================================================================

class _LoiApi(Exception):
    """Một yêu cầu hỏng, đã phân loại (``truy_cap_youtube.API_*``) — chỉ sống trong module này."""

    def __init__(self, loai: str):
        super().__init__(loai)
        self.loai = loai


def _json_loi(e: urllib.error.HTTPError) -> Any:
    """Thân lỗi JSON của Google — chỉ để đọc ``reason``, không giữ lại (có thể chứa số dự án)."""
    try:
        with e:
            return json.loads(e.read(GIOI_HAN_THAN))
    except (ValueError, OSError, http.client.HTTPException):
        return None


def _gui(url: str, khoa: str, timeout: float) -> dict:
    """Một yêu cầu HTTP qua ``urllib.request.urlopen`` (thuộc tính module: fixture chặn mạng của test bắt được). Chỉ bắt
    đúng lỗi truyền tải — AssertionError của test và lỗi lập trình nổi lên."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    req.add_unredirected_header("X-Goog-Api-Key", khoa)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            than = resp.read(GIOI_HAN_THAN + 1)
            dai = str(resp.headers.get("Content-Length") or "")
            chuyen_huong = resp.geturl() != url
    except urllib.error.HTTPError as e:
        raise _LoiApi(tc.phan_loai_loi_api(e.code, _json_loi(e))) from None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
        raise _LoiApi(tc.API_TAM_THOI) from None
    if chuyen_huong or len(than) > GIOI_HAN_THAN:
        raise _LoiApi(tc.API_PHAN_HOI_LA)
    if dai.isdigit() and len(than) < int(dai):
        raise _LoiApi(tc.API_TAM_THOI)  # thân cụt
    try:
        du_lieu = json.loads(than)
    except ValueError:
        du_lieu = None
    if not isinstance(du_lieu, dict):
        raise _LoiApi(tc.API_PHAN_HOI_LA)
    return du_lieu


def _goi(phien: tc.PhienYouTube, data_dir: str, endpoint: str, params: dict, *, cancel_event: Any = None,
         don_vi: int = 1, doc: Optional[Callable[[dict], Any]] = None) -> tuple:
    """MỘT yêu cầu API của lượt ``phien`` — dùng chung cho mọi endpoint (``videos``, ``search``…). Khoá đọc Ở ĐÂY (nơi
    gọi không bao giờ cầm khoá); chưa có / sai dạng, cầu dao yt-dlp đang mở hay API đã tắt → không gửi; đếm ``don_vi``;
    lỗi tạm thời thử lại MỘT lần sau 3 s qua hàm chờ huỷ được của phiên. ``doc(du_lieu)`` đọc phản hồi 2xx, ném
    ``_LoiApi(API_PHAN_HOI_LA)`` khi sai dạng. Trả ``(kết quả, "")`` hoặc ``(None, lý do tiếng Việt)``; lỗi chỉ ghi vào
    ``phien.api`` — không bao giờ ném lỗi mạng ra nơi gọi."""
    try:
        khoa = _doc_khoa_cho(data_dir)
    except LoiKhoaApi as e:
        return None, f"{LY_DO_SAI_KHOA}: {e}"
    if not khoa:
        return None, LY_DO_CHUA_CO_KHOA
    timeout = CauHinhMang.tu_file_cau_hinh(data_dir).network_timeout_s
    api = phien.api
    url = GOC_API + endpoint + "?" + urllib.parse.urlencode(params)
    lan = 0
    while True:
        lan += 1
        if cancel_event is not None and cancel_event.is_set():
            return None, LY_DO_DA_HUY
        if phien.mo:
            return None, LY_DO_CAU_DAO
        if api.tat:
            return None, api.ly_do_tat
        api.ghi_yeu_cau(don_vi)
        try:
            ket_qua = _gui(url, khoa, timeout)
            if doc is not None:
                ket_qua = doc(ket_qua)
        except _LoiApi as e:
            loai = e.loai
        else:
            api.ghi_thanh_cong()
            return ket_qua, ""
        LOGGER.info("event=youtube.api.error endpoint=%s category=%s attempt=%d", endpoint, loai, lan)
        if api.ghi_loi(loai):
            return None, api.ly_do_tat
        if loai != tc.API_TAM_THOI:
            return None, tc.THONG_BAO_API[loai]
        if lan > 1:
            return None, LY_DO_TAM_THOI
        if api.cho_thu_lai(cancel_event):
            return None, LY_DO_DA_HUY


# =====================================================================
#  videos.list
# =====================================================================

@dataclass(frozen=True)
class KetQuaApi:
    """``thong_tin``: mã -> dict chuẩn (theo thứ tự hỏi). ``thieu``: mã nơi gọi phải lấy bằng đường yt-dlp CŨ (giữ thứ
    tự, không trùng). ``ly_do_lui``: vì sao có ``thieu`` (tiếng Việt; rỗng khi không có khoá — trạng thái bình thường,
    không ghi vào ghi chú kết quả). ``ly_do_tung_ma``: lý do của TỪNG mã trong ``thieu`` (rỗng khi không có khoá) — nơi
    gọi không lùi về yt-dlp (kiểm video còn trên YouTube) tách mã vắng trong phản hồi 200 khỏi lô lỗi."""

    thong_tin: dict
    thieu: tuple
    ly_do_lui: str
    ly_do_tung_ma: dict = field(default_factory=dict)


def _video_chuan(muc: dict, can_trang_thai: bool) -> dict:
    sn, cd = muc.get("snippet"), muc.get("contentDetails")
    ls, st = muc.get("liveStreamingDetails", {}), muc.get("status")
    if not (isinstance(sn, dict) and isinstance(cd, dict) and isinstance(ls, dict)
            and all(isinstance(sn.get(k), str) for k in _TRUONG_SNIPPET)
            and (isinstance(st, dict) or not can_trang_thai)):
        raise _LoiApi(tc.API_PHAN_HOI_LA)
    kenh = sn["channelId"]
    video = {"id": muc["id"], "title": sn["title"], "duration": thoi_luong_giay(cd.get("duration")),
             "channel": sn["channelTitle"], "uploader": sn["channelTitle"], "channel_id": kenh,
             "channel_url": f"https://www.youtube.com/channel/{kenh}" if kenh else "",
             "published_at": sn["publishedAt"], "live_broadcast_content": sn["liveBroadcastContent"]}
    if isinstance(ls.get("actualStartTime"), str):
        video["actual_start_time"] = ls["actualStartTime"]
    if can_trang_thai:
        video["privacy_status"] = str(st.get("privacyStatus") or "")
        video["upload_status"] = str(st.get("uploadStatus") or "")
    return video


def _doc_lo(du_lieu: dict, lo: list, can_trang_thai: bool) -> dict:
    """Phản hồi ``videos.list`` -> {mã: dict chuẩn} cho đúng các mã đã hỏi (mã lạ bị bỏ qua); sai dạng → ``_LoiApi``."""
    items = du_lieu.get("items", [])
    if not isinstance(items, list):
        raise _LoiApi(tc.API_PHAN_HOI_LA)
    can = set(lo)
    ra = {}
    for muc in items:
        ma = muc.get("id") if isinstance(muc, dict) else None
        if not isinstance(ma, str):
            raise _LoiApi(tc.API_PHAN_HOI_LA)
        if ma in can:
            ra[ma] = _video_chuan(muc, can_trang_thai)
    return ra


def lay_video(phien: tc.PhienYouTube, data_dir: str, ids: Iterable[str], *, cancel_event: Any = None,
              can_trang_thai: bool = False) -> KetQuaApi:
    """Thông tin video bằng ``videos.list`` (tối đa 50 mã một lượt; bỏ trùng, giữ thứ tự). Mã trong ``thieu`` nơi gọi lấy
    bằng đường yt-dlp CŨ: không có khoá (0 yêu cầu, ``ly_do_lui`` rỗng), khoá sai dạng (0 yêu cầu), cầu dao yt-dlp đang mở
    (0 yêu cầu), API đã tắt, lô lỗi, mã vắng trong phản hồi 200, video ``upcoming``/``live``, mã sai dạng (không gửi).
    ``can_trang_thai``: thêm ``part=status`` (``privacy_status``/``upload_status``)."""
    ma = list(dict.fromkeys(ids))
    if not ma:
        return KetQuaApi({}, (), "")
    try:
        co_khoa = bool(_doc_khoa_cho(data_dir))
    except LoiKhoaApi as e:
        ly_do = f"{LY_DO_SAI_KHOA}: {e}"
        phien.api.ghi_video(0, [ly_do] * len(ma))
        return KetQuaApi({}, tuple(ma), ly_do, dict.fromkeys(ma, ly_do))
    if not co_khoa:
        return KetQuaApi({}, tuple(ma), "")
    hop_le = [m for m in ma if isinstance(m, str) and _RE_MA.fullmatch(m)]
    lui = dict.fromkeys(set(ma) - set(hop_le), LY_DO_MA_SAI)
    params = {"part": _PART + (",status" if can_trang_thai else ""),
              "fields": _FIELDS + (",status(privacyStatus,uploadStatus)" if can_trang_thai else "") + ")"}
    thong_tin: dict = {}
    for i in range(0, len(hop_le), LO_TOI_DA):
        lo = hop_le[i:i + LO_TOI_DA]
        ket, ly_do = _goi(phien, data_dir, "videos", {**params, "id": ",".join(lo)}, cancel_event=cancel_event,
                          doc=lambda du_lieu, lo=lo: _doc_lo(du_lieu, lo, can_trang_thai))
        for m in lo:
            video = None if ket is None else ket.get(m)
            if ket is None:
                lui[m] = ly_do
            elif video is None:
                lui[m] = LY_DO_VANG
            elif video["live_broadcast_content"] in ("upcoming", "live", "active"):  # Google gửi "live"; "active" vô hại
                lui[m] = LY_DO_SAP_PHAT
            else:
                thong_tin[m] = video
    thieu = tuple(m for m in ma if m not in thong_tin)
    # Dừng / cầu dao mở: nơi gọi cũng không chạy yt-dlp cho các mã đó — không đếm là «lùi về yt-dlp».
    phien.api.ghi_video(len(thong_tin), [lui[m] for m in thieu if lui[m] not in (LY_DO_DA_HUY, LY_DO_CAU_DAO)])
    return KetQuaApi(thong_tin, thieu, "; ".join(dict.fromkeys(lui[m] for m in thieu)), {m: lui[m] for m in thieu})


# =====================================================================
#  search.list
# =====================================================================

_FIELDS_TIM = "items(id/videoId,snippet(title,channelId,channelTitle,publishedAt))"
_TRUONG_TIM = ("title", "channelId", "channelTitle", "publishedAt")


def _doc_tim(du_lieu: dict) -> list:
    """Phản hồi ``search.list`` -> [dict] theo thứ tự liên quan; sai dạng → ``_LoiApi``. Tiêu đề / tên kênh của
    ``search.list`` đã mã hoá HTML (``&amp;``, ``&#39;``), khác ``videos.list`` — giải mã ở đây."""
    items = du_lieu.get("items", [])
    if not isinstance(items, list):
        raise _LoiApi(tc.API_PHAN_HOI_LA)
    ra = []
    for muc in items:
        id_ = muc.get("id") if isinstance(muc, dict) else None
        ma = id_.get("videoId") if isinstance(id_, dict) else None
        sn = muc.get("snippet") if isinstance(muc, dict) else None
        if not (isinstance(ma, str) and _RE_MA.fullmatch(ma) and isinstance(sn, dict)
                and all(isinstance(sn.get(k), str) for k in _TRUONG_TIM)):
            raise _LoiApi(tc.API_PHAN_HOI_LA)
        ra.append({"id": ma, "title": html.unescape(sn["title"]), "channel": html.unescape(sn["channelTitle"]),
                   "channel_id": sn["channelId"], "published_at": sn["publishedAt"]})
    return ra


def tim_video(phien: tc.PhienYouTube, data_dir: str, q: str, *, thoi_luong: str = "long", sau: str = "") -> tuple:
    """Video khớp ``q`` bằng ``search.list`` (type=video, order=relevance, tối đa 50 kết quả) — hạn mức RIÊNG 100
    lượt/ngày, mỗi lần gọi 1 lượt (developers.google.com, 16/11). ``thoi_luong``: ``long`` (trên 20 phút) | ``medium``
    (4–20 phút) | ``any``; ``sau``: chỉ video đăng từ mốc RFC 3339 này. Trả ``([dict], "")`` hoặc ``([], lý do)``. Lỗi
    chỉ ghi vào ``phien.api``: nơi gọi dùng phiên RIÊNG cho tìm kiếm, để hết hạn mức tìm kiếm không tắt ``videos.list``
    (hạn mức khác) của cùng lượt."""
    params = {"part": "snippet", "type": "video", "q": q, "maxResults": LO_TOI_DA, "videoDuration": thoi_luong,
              "order": "relevance", "fields": _FIELDS_TIM}
    if sau:
        params["publishedAfter"] = sau
    ket, ly_do = _goi(phien, data_dir, "search", params, doc=_doc_tim)
    return ket or [], ly_do


def lay_ngay_luot_xem(phien: tc.PhienYouTube, data_dir: str, ids: Iterable[str], *,
                      cancel_event: Any = None) -> tuple:
    """Ngày đăng + lượt xem cho tab «📝 Tiêu đề kênh» (D-38): ``videos.list`` ``part=snippet,statistics``, 50 mã một
    lượt (1 đơn vị) qua :func:`_goi` — cùng phân loại lỗi, chốt tắt, bộ đếm của ``phien.api``. Trả ``({mã:
    {"published_at": chuỗi ISO nguyên văn, "view_count": int | None}}, lý do)``: ``view_count`` None = YouTube không trả
    (ẩn) hay giá trị lạ — không bao giờ 0; mã API không trả thì vắng. Lý do rỗng khi mọi lô xong; không khoá →
    ``LY_DO_CHUA_CO_KHOA`` (0 yêu cầu); lô hỏng → lý do tiếng Việt của lõi, các lô khác vẫn chạy. Không lùi về yt-dlp."""

    def doc(du_lieu: dict, lo: list) -> dict:
        items = du_lieu.get("items", [])
        if not (isinstance(items, list) and all(isinstance(x, dict) and isinstance(x.get("id"), str) for x in items)):
            raise _LoiApi(tc.API_PHAN_HOI_LA)
        ra = {}
        for x in items:
            if x["id"] not in lo:
                continue
            sn, tk = x.get("snippet"), x.get("statistics", {})
            if not (isinstance(sn, dict) and isinstance(sn.get("publishedAt"), str) and isinstance(tk, dict)):
                raise _LoiApi(tc.API_PHAN_HOI_LA)
            xem = tk.get("viewCount")  # Google trả chuỗi; quá 18 chữ số là lạ (int64 của bảng, giới hạn int())
            ra[x["id"]] = {"published_at": sn["publishedAt"],
                           "view_count": int(xem) if isinstance(xem, str) and re.fullmatch(r"[0-9]{1,18}", xem)
                           else None}
        return ra

    ma = [m for m in dict.fromkeys(ids) if isinstance(m, str) and _RE_MA.fullmatch(m)]  # mã lạ không gửi đi
    ket_qua: dict = {}
    ly_do: dict = {}
    for i in range(0, len(ma), LO_TOI_DA):
        lo = ma[i:i + LO_TOI_DA]
        ket, loi = _goi(phien, data_dir, "videos",
                        {"part": "snippet,statistics", "fields": "items(id,snippet(publishedAt),statistics(viewCount))",
                         "id": ",".join(lo)}, cancel_event=cancel_event, doc=lambda du_lieu, lo=lo: doc(du_lieu, lo))
        ket_qua.update(ket or {})
        ly_do[loi] = None
    phien.api.ghi_video(len(ket_qua))
    return ket_qua, "; ".join(x for x in ly_do if x)
