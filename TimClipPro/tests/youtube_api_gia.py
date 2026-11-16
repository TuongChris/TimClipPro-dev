# -*- coding: utf-8 -*-
"""YouTube Data API GIẢ ở tầng ``urllib.request.urlopen`` cho test đường API (D-51) — không mạng, không khoá thật.

Mặc định (fixture autouse ``_khong_co_khoa_api_gia`` trong tests/conftest.py) mọi test chạy như máy CHƯA CÓ KHOÁ:
``youtube_api.lay_video`` trả ``thieu`` = mọi mã, 0 yêu cầu — đường yt-dlp cũ y nguyên. Test về đường API xin fixture
``api_youtube_gia`` (khoá GIẢ trong file tạm + transport giả thay ``urllib.request.urlopen``), nhận ``TransportGia``::

    def test_x(api_youtube_gia, tmp_path):
        api_youtube_gia.video["abcdefghijk"] = video_gia("abcdefghijk", title="Tiêu đề")
        phien = truy_cap_youtube.PhienYouTube(ham_cho=lambda giay, ev=None: False)
        kq = youtube_api.lay_video(phien, str(tmp_path / "data"), ["abcdefghijk"])
        assert kq.thong_tin["abcdefghijk"]["title"] == "Tiêu đề" and api_youtube_gia.dem() == 1

* Bảng ``video`` (mã -> mục ``items`` của ``videos.list``, dựng bằng ``video_gia``): phản hồi mặc định trả đúng các mã
  có trong bảng (mã vắng = video riêng tư / đã gỡ); ``liveStreamingDetails`` / ``status`` chỉ có khi ``part`` xin.
* ``kich_ban``: phần tử thứ n quyết định yêu cầu thứ n — ``None`` = trả theo bảng; hằng lỗi ``QUOTA``,
  ``KEY_INVALID``, ``API_DISABLED``, ``SERVER``, ``TIMEOUT``, ``THAN_CUT``, ``CHUYEN_HUONG``; ``dict`` = thân JSON 200
  nguyên văn;
  ``bytes`` = thân 200 thô. Hết kịch bản → trả theo bảng.
* ``yeu_cau``: mỗi yêu cầu một ``YeuCauGhi`` — KHÔNG BAO GIỜ ghi khoá: ``key_in_header`` chỉ là đúng/sai (header
  ``X-Goog-Api-Key`` không đi theo chuyển hướng mang đúng khoá giả); ``url``/``params`` ghi nguyên văn để test kiểm khoá
  không lọt vào URL. ``dem()`` = số yêu cầu đã tới.
* Chỉ transport, không khoá: ``lap_transport(monkeypatch)`` (đếm yêu cầu khi máy «chưa có khoá»).
"""

import io
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import NamedTuple, Optional

KHOA_GIA = "AIza" + "GiaKhongBiMat" + "0" * 22  # gia-khong-bi-mat: đúng dạng, rõ là giả
KENH_GIA = "UC" + "kenhGia" + "0" * 15  # mã kênh 24 ký tự
SO_DU_AN_GIA = "projects/000000000000"  # Google đặt số dự án trong thân lỗi — không được lưu hay hiện

QUOTA = "QUOTA"
KEY_INVALID = "KEY_INVALID"
API_DISABLED = "API_DISABLED"
SERVER = "SERVER"
TIMEOUT = "TIMEOUT"
THAN_CUT = "THAN_CUT"
CHUYEN_HUONG = "CHUYEN_HUONG"  # urllib đã theo chuyển hướng sang máy khác (header khoá không đi theo)

_HEADER_KHOA = "X-goog-api-key"  # urllib.request.Request viết hoa kiểu str.capitalize()


def _loi_google(ma: int, ly_do: str, trang_thai: str, chi_tiet: str = "", thong_diep: str = "x") -> dict:
    loi = {"code": ma, "message": thong_diep, "status": trang_thai,
           "errors": [{"message": thong_diep, "domain": "global", "reason": ly_do}]}
    if chi_tiet:
        loi["details"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": chi_tiet,
                           "domain": "googleapis.com", "metadata": {"consumer": SO_DU_AN_GIA}}]
    return {"error": loi}


# Thân lỗi theo khuôn công khai của Google (YouTube Data API v3).
_LOI_HTTP = {
    QUOTA: (403, _loi_google(403, "quotaExceeded", "PERMISSION_DENIED",
                             thong_diep="The request cannot be completed because you have exceeded your quota.")),
    KEY_INVALID: (400, _loi_google(400, "badRequest", "INVALID_ARGUMENT", "API_KEY_INVALID",
                                   thong_diep="API key not valid. Please pass a valid API key.")),
    API_DISABLED: (403, _loi_google(403, "accessNotConfigured", "PERMISSION_DENIED", "SERVICE_DISABLED",
                                    thong_diep=f"YouTube Data API v3 has not been used in {SO_DU_AN_GIA} before.")),
    SERVER: (503, _loi_google(503, "backendError", "UNAVAILABLE", thong_diep="Backend Error")),
}


class YeuCauGhi(NamedTuple):
    endpoint: str
    ids: tuple
    part: str
    key_in_header: bool
    timeout: Optional[float]
    url: str
    params: dict


def video_gia(ma: str, *, title: str = "", duration: str = "PT10M", published_at: str = "2026-07-31T20:00:34Z",
              ten_kenh: str = "Kênh giả", live: str = "none", actual_start: str = "", privacy: str = "public",
              upload: str = "processed") -> dict:
    """Một mục ``items`` của ``videos.list`` (đủ các trường youtube_api xin qua ``fields``)."""
    muc = {"id": ma,
           "snippet": {"title": title or f"Video {ma}", "channelId": KENH_GIA, "channelTitle": ten_kenh,
                       "publishedAt": published_at, "liveBroadcastContent": live},
           "contentDetails": {"duration": duration},
           "status": {"privacyStatus": privacy, "uploadStatus": upload}}
    if actual_start:
        muc["liveStreamingDetails"] = {"actualStartTime": actual_start}
    return muc


class _PhanHoiGia(io.BytesIO):
    """Đủ phần ``http.client.HTTPResponse`` mà youtube_api dùng: ``read``, ``headers``, ``geturl``, ``with``."""

    def __init__(self, than: bytes, url: str, do_dai: Optional[int] = None):
        super().__init__(than)
        self.status = 200
        self.headers = {"Content-Type": "application/json; charset=UTF-8",
                        "Content-Length": str(len(than) if do_dai is None else do_dai)}
        self._url = url

    def geturl(self) -> str:
        return self._url


class TransportGia:
    """Thay ``urllib.request.urlopen``; xem docstring module."""

    def __init__(self):
        self.video: dict = {}
        self.kich_ban: list = []
        self.yeu_cau: list = []
        self._lock = threading.Lock()

    def dem(self) -> int:
        return len(self.yeu_cau)

    def __call__(self, req, data=None, timeout=None, **_kw):
        url = req.full_url
        p = urllib.parse.urlsplit(url)
        params = dict(urllib.parse.parse_qsl(p.query))
        ids = tuple(params["id"].split(",")) if params.get("id") else ()
        part = params.get("part", "")
        dung_khoa = (req.unredirected_hdrs.get(_HEADER_KHOA) == KHOA_GIA and _HEADER_KHOA not in req.headers)
        with self._lock:
            self.yeu_cau.append(YeuCauGhi(p.path.rsplit("/", 1)[-1], ids, part, dung_khoa, timeout, url, params))
            buoc = self.kich_ban.pop(0) if self.kich_ban else None
        if isinstance(buoc, bytes):
            return _PhanHoiGia(buoc, url)
        if isinstance(buoc, dict):
            return _PhanHoiGia(json.dumps(buoc).encode("utf-8"), url)
        if buoc in _LOI_HTTP:
            ma, than = _LOI_HTTP[buoc]
            raise urllib.error.HTTPError(url, ma, "loi gia", {}, io.BytesIO(json.dumps(than).encode("utf-8")))
        if buoc == TIMEOUT:
            raise TimeoutError("The read operation timed out")
        items = [self._loc_part(self.video[m], part) for m in ids if m in self.video]
        than = json.dumps({"items": items}).encode("utf-8")
        if buoc == THAN_CUT:
            return _PhanHoiGia(than[: len(than) // 2], url, len(than))
        return _PhanHoiGia(than, "https://www.google.com/sorry/index" if buoc == CHUYEN_HUONG else url)

    @staticmethod
    def _loc_part(muc: dict, part: str) -> dict:
        co = set(part.split(",")) | {"id"}
        return {k: v for k, v in muc.items() if k in co}


def lap_transport(monkeypatch) -> TransportGia:
    tp = TransportGia()
    monkeypatch.setattr(urllib.request, "urlopen", tp)
    return tp


def lap_api_gia(tmp_path, monkeypatch) -> TransportGia:
    """Khoá GIẢ trong file tạm (đọc qua ``youtube_api.doc_khoa_api`` thật) cho MỌI ``data_dir`` + transport giả."""
    import youtube_api

    f = tmp_path / "khoa_api_gia" / youtube_api.TEN_FILE_KHOA
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# khoá GIẢ của test\n" + KHOA_GIA + "\n", encoding="utf-8")
    monkeypatch.setattr(youtube_api, "_doc_khoa_cho", lambda data_dir: youtube_api.doc_khoa_api(str(f)))
    return lap_transport(monkeypatch)
