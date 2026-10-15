# -*- coding: utf-8 -*-
"""Chẩn đoán truy cập YouTube — ``python cli.py youtube-doctor [--network URL]``.

Mặc định CHỈ ĐỌC và KHÔNG gọi mạng: phiên bản yt-dlp, bộ giải JS đi kèm, JS runtime có trên
máy, cấu hình mạng thật (``data/cau_hinh.json``), cấu trúc file cookie (chỉ số đếm — không giá
trị, không tên cookie), bảng thử lại và ngưỡng cầu dao. Không bao giờ gọi Google.

``--network URL`` (người dùng TỰ chạy): hỏi thông tin đúng MỘT video công khai, qua đúng đường
tuỳ chọn và phân loại lỗi mà tool dùng khi quét — để biết YouTube có đang chặn và cookie có còn
được chấp nhận hay không. Như mọi lượt quét, yt-dlp có thể ghi lại file cookie sau request.
"""

from __future__ import annotations

import importlib.metadata as _md
import os
import platform
import shutil
import sys

import truy_cap_youtube as t
import ytdlp_chung
from ytdlp_chung import BoGhiYtdlp, CauHinhMang

MA_THOAT_YOUTUBE_CHAN = 3


def _phien_ban(goi: str) -> str:
    try:
        return _md.version(goi)
    except Exception:  # noqa: BLE001
        return ""


def _yt_dlp() -> dict:
    try:
        import yt_dlp
    except Exception as e:  # noqa: BLE001
        return {"phien_ban": "", "loi": type(e).__name__}
    goc = os.path.dirname(yt_dlp.__file__)
    ejs = os.path.join(goc, "extractor", "youtube", "jsc", "_builtin", "vendor",
                       "yt.solver.core.js")
    return {"phien_ban": getattr(yt_dlp.version, "__version__", ""),
            "git": getattr(yt_dlp.version, "RELEASE_GIT_HEAD", "")[:12],
            "bo_giai_js_di_kem": os.path.isfile(ejs),
            "goi_yt_dlp_ejs": _phien_ban("yt-dlp-ejs") or "không cài riêng"}


def _js_runtime() -> dict:
    # Chỉ dò có/không bằng PATH — không chạy chương trình nào.
    return {ten: bool(shutil.which(ten)) for ten in ("deno", "node", "bun", "qjs")}


def _kha_nang_js() -> dict:
    """Cookie đăng nhập dùng được không: Node.js ≥ 22 + gói yt-dlp-ejs đúng bản (``ytdlp_chung.kha_nang_js`` — chạy
    ``node --version`` trên máy, không gọi mạng; đúng phép kiểm yt-dlp làm trước khi dùng node)."""
    kn = ytdlp_chung.kha_nang_js()
    return {"san_sang": kn.san_sang, "node": kn.node, "node_phien_ban": kn.node_phien_ban,
            "ejs_phien_ban": kn.ejs_phien_ban, "ly_do": kn.ly_do}


def chan_doan(data_dir: str, url_mang: str = "") -> dict:
    """Bản chẩn đoán dạng dict (không bí mật). Chỉ gọi mạng khi có ``url_mang``."""
    ch = CauHinhMang.tu_file_cau_hinh(data_dir)
    try:
        import json

        with open(os.path.join(data_dir, "cau_hinh.json"), encoding="utf-8") as f:
            tho = json.load(f)
        clients = tho.get("ytdlp_player_clients") if isinstance(tho, dict) else None
    except Exception:  # noqa: BLE001
        clients = None
    clients = clients if isinstance(clients, list) else None
    cd = t.chan_doan_cookie(ch.cookiefile, cookies_browser=ch.cookies_browser)
    kq = {
        "python": sys.version.split()[0],
        "he_dieu_hanh": platform.platform(terse=True),
        "yt_dlp": _yt_dlp(),
        "js_runtime": _js_runtime(),
        "kha_nang_js": _kha_nang_js(),
        "ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe")),
        "cau_hinh_mang": {
            "network_timeout_s": ch.network_timeout_s,
            "sleep_requests_s": ch.sleep_requests_s,
            "sleep_min_s": ch.sleep_min_s, "sleep_max_s": ch.sleep_max_s,
            "cookie_cau_hinh": ch.co_cookie,
            "player_clients_thu_tu_thuc": ch.player_clients(clients) if clients else None,
        },
        "cookie": {k: v for k, v in cd.thanh_dict().items() if k != "ten_file"},
        "ngan_sach_thu_lai": {k: {"thu_lai_mang": len(v.cho_tam_thoi),
                                  "thu_lai_429": len(v.cho_429),
                                  "yt_dlp_retries": v.yt_dlp_retries}
                              for k, v in t.NGAN_SACH.items()},
        "nguong_cau_dao": dict(t.NGUONG_MO),
        "google": "không gọi",
        "mang": {"da_goi": False},
    }
    if url_mang:
        kq["mang"] = _kiem_mang(ch, url_mang, cd)
    return kq


def _kiem_mang(ch: CauHinhMang, url: str, cd: t.ChanDoanCookie) -> dict:
    """ĐÚNG MỘT lần lấy thông tin video (không tải), qua đúng phiên/phân loại của tool."""
    import yt_dlp

    phien = t.PhienYouTube(ngan_sach={**t.NGAN_SACH, "metadata": t.NganSach()})
    bo_ghi = BoGhiYtdlp(phien)

    def lay() -> dict:
        opts = ch.tuy_chon("metadata", noplaylist=True, skip_download=True,
                           extract_flat="in_playlist", logger=bo_ghi)
        phien.dem_yeu_cau("metadata")
        co_cookie = "cookiefile" in opts or "cookiesfrombrowser" in opts
        with yt_dlp.YoutubeDL(opts) as ydl:
            if co_cookie:
                phien.ghi_cookie_tai_khoan(ytdlp_chung.co_cookie_tai_khoan(ydl))   # chỉ TÊN cookie
            info = ydl.extract_info(url, download=False) or {}
        if co_cookie:
            phien.ghi_ket_qua_co_cookie(info)
        return info

    ra: dict = {"da_goi": True, "url_ma_video": t.ma_tu_url(url)}
    try:
        info = phien.chay("metadata", lay, video_id=t.ma_tu_url(url))
        ra["ket_qua"] = "OK"
        ra["thoi_luong_s"] = info.get("duration")
    except t.LoiTruyCapYouTube as e:
        ra["ket_qua"] = e.that_bai.category
        ra["thong_bao"] = e.that_bai.human_message_vi
        ra["chi_tiet"] = e.that_bai.technical_summary
    if not cd.cau_hinh:
        ra["cookie_duoc_chap_nhan"] = "không cấu hình cookie"
    elif phien.cookie_bi_tu_choi:
        ra["cookie_duoc_chap_nhan"] = t.COOKIE_PHIEN_BI_TU_CHOI
    elif ra["ket_qua"] == "OK" and phien.trang_thai_dang_nhap(True)[0] == "DA_XAC_MINH":
        # Chỉ khi YouTube trả nội dung CHỈ tài khoản có quyền mới xem (PhienYouTube.trang_thai_dang_nhap). Video công
        # khai lấy được + cookie đúng tên KHÔNG chứng minh YouTube nhận tài khoản (cookie có thể chỉ trùng tên).
        ra["cookie_duoc_chap_nhan"] = t.COOKIE_SESSION_ACCEPTED_BY_YOUTUBE
    else:
        ra["cookie_duoc_chap_nhan"] = t.COOKIE_PHIEN_CHUA_RO
    ra["bang_chung_dang_nhap"] = phien.bang_chung_dang_nhap()
    ra["so_do"] = phien.tom_tat()
    return ra


def _in(kq: dict) -> None:
    yd = kq["yt_dlp"]
    print("=== Chẩn đoán truy cập YouTube (chỉ đọc) ===")
    print(f"Python: {kq['python']} | {kq['he_dieu_hanh']}")
    print(f"yt-dlp: {yd.get('phien_ban') or 'CHƯA CÀI'} ({yd.get('git', '')}) | bộ giải JS đi "
          f"kèm: {'có' if yd.get('bo_giai_js_di_kem') else 'KHÔNG'} | yt-dlp-ejs: "
          f"{yd.get('goi_yt_dlp_ejs', '')}")
    js = kq["js_runtime"]
    print("JS runtime: " + ", ".join(f"{k}={'có' if v else 'không'}" for k, v in js.items()))
    kn = kq["kha_nang_js"]
    print("Cookie đăng nhập (cần giải thử thách JavaScript): " + (
        f"DÙNG ĐƯỢC — Node.js {kn['node_phien_ban']} + yt-dlp-ejs {kn['ejs_phien_ban']}" if kn["san_sang"]
        else f"CHƯA dùng được — {kn['ly_do']}; có cookie thì lượt quét chạy KHÔNG đăng nhập"))
    print(f"FFmpeg: {'có' if kq['ffmpeg'] else 'KHÔNG'} | FFprobe: "
          f"{'có' if kq['ffprobe'] else 'KHÔNG'}")
    m = kq["cau_hinh_mang"]
    print(f"Mạng: timeout {m['network_timeout_s']} s, nghỉ giữa request "
          f"{m['sleep_requests_s']} s, nghỉ trước tải {m['sleep_min_s']}–{m['sleep_max_s']} s")
    if m.get("player_clients_thu_tu_thuc"):
        print("Thứ tự player client thực tế: "
              + ", ".join(c or "mặc định" for c in m["player_clients_thu_tu_thuc"]))
    c = kq["cookie"]
    if not c["cau_hinh"]:
        print("Cookie: CHƯA cấu hình")
    elif c["nguon"] == "trinh_duyet":
        print("Cookie: lấy từ trình duyệt (người dùng cấu hình) — không đọc profile ở đây")
    else:
        print(f"Cookie: {c['trang_thai']} | tồn tại {c['ton_tai']} | {c['kich_thuoc']} byte | "
              f"sửa lúc {c['sua_luc'] or '?'} | định dạng {c['dinh_dang'] or '?'} | "
              f"{c['so_ban_ghi']} bản ghi ({c['so_ban_ghi_youtube']} youtube, "
              f"{c['so_ban_ghi_google']} google, {c['so_het_han']} hết hạn) | dòng hỏng "
              f"{c['so_dong_hong']} | có cookie đăng nhập: "
              f"{'có' if c['co_cookie_dang_nhap'] else 'không'}")
        print("  (Cấu trúc đúng KHÔNG có nghĩa YouTube còn chấp nhận phiên — chạy thêm "
              "--network URL để kiểm.)")
    if c.get("hai_nguon"):
        print("  CẢNH BÁO: cấu hình CẢ file cookie lẫn trình duyệt — tool CHỈ dùng file cookie, ô trình duyệt bị bỏ qua.")
    print(f"Cầu dao mở sau: {kq['nguong_cau_dao']}")
    print(f"Google: {kq['google']}")
    mang = kq["mang"]
    if not mang.get("da_goi"):
        print("Mạng: KHÔNG gọi (thêm --network <link video công khai> để kiểm một request).")
        return
    print(f"Kiểm mạng ({mang.get('url_ma_video') or 'link'}): {mang['ket_qua']}")
    if mang.get("thong_bao"):
        print(f"  {mang['thong_bao']}")
        print(f"  {t.DAU_CHI_TIET} {mang.get('chi_tiet', '')}")
    print(f"Cookie được YouTube chấp nhận: {mang.get('cookie_duoc_chap_nhan')}")
    if mang.get("cookie_duoc_chap_nhan") == t.COOKIE_PHIEN_CHUA_RO and c["cau_hinh"]:
        print("  (Lấy được video công khai KHÔNG chứng minh YouTube nhận tài khoản — video đó không cần đăng nhập.)")


def chay(data_dir: str, url_mang: str = "") -> int:
    """In bản chẩn đoán. Mã thoát: 0 bình thường, 3 khi kiểm mạng thấy YouTube chặn truy cập,
    1 khi kiểm mạng lỗi vì lý do khác."""
    kq = chan_doan(data_dir, url_mang=url_mang)
    _in(kq)
    mang = kq["mang"]
    if not mang.get("da_goi") or mang.get("ket_qua") == "OK":
        return 0
    return MA_THOAT_YOUTUBE_CHAN if mang["ket_qua"] in t.LOAI_TRUY_CAP else 1
