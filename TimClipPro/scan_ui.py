# -*- coding: utf-8 -*-
"""Dựng dữ liệu bảng trạng thái quét. **Không import streamlit.**

Vì sao tách ra
==============
Bảng trạng thái trước đây được dựng thẳng trong ``app.py`` bằng dict lồng biểu thức
điều kiện::

    "Đoạn": "—" if v.matches is None else v.matches

pandas suy ra dtype ``object`` vì cột trộn ``int`` và ``str``. Mỗi lần Streamlit vẽ
lại (0,75 giây một lần) PyArrow ném ``ArrowInvalid`` rồi Streamlit mới chạy nhánh
sửa dtype tự động — tức là **một exception cho mỗi lần render**, lặp suốt lượt quét.

Gốc rễ không phải "PyArrow khó tính" mà là **bảng UI không có schema**. Tách builder
ra đây để dtype được khai báo tường minh một chỗ và kiểm thử được mà không cần chạy
Streamlit.

Quyết định kiểu cho cột "Đoạn"
==============================
Ba trạng thái cần phân biệt: chưa quét, quét xong không có đoạn nào (0), quét xong
có N đoạn. Nếu dùng ``Int64`` + ``pd.NA`` thì "chưa quét" hiển thị thành ô trống —
dễ bị nhìn nhầm thành dữ liệu lỗi và khó phân biệt với 0.

Đây là bảng **trạng thái tạm thời** trong lúc quét, không phải bảng dữ liệu để sắp
xếp hay tính toán, nên ưu tiên đọc hiểu: toàn cột là ``string``, "chưa có" hiển thị
là ``—``. Kiểu tường minh nên Arrow chuyển đổi thành công ngay từ đầu.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

import pandas as pd

import outbox
import truy_cap_youtube as _tc
from common_original import (
    COT_SO_NGUON_CHUNG,
    HEADER_NGUON_CHUNG,
    TEN_TRANG_THAI_CAP,
    dong_bao_cao,
)


def dong_trang_thai_youtube(cd: Any, phien: Any = None, js: Any = None) -> list:
    """Các dòng ``(mức, câu)`` cho mục «Trạng thái YouTube» ở thanh bên.

    ``mức`` ∈ success/info/warning/error. ``cd``: ``truy_cap_youtube.ChanDoanCookie`` (chỉ số
    đếm — không giá trị, không tên cookie). ``phien``: phiên YouTube của lượt chạy gần nhất
    (``Engine.phien_youtube_cuoi``) hoặc ``None``. ``js``: ``ytdlp_chung.KhaNangJs`` (máy có giải
    được thử thách JavaScript — điều kiện để cookie dùng được) hoặc ``None``. Không đọc file, không
    gọi mạng.
    """
    ra: list = []
    if phien is not None and getattr(phien, "mo", False) is True:
        ra.append(("error", phien.thong_bao_dung()))
    elif phien is not None and getattr(phien, "cookie_bi_tu_choi", False):
        ra.append(("warning", "Cookie cấu hình không được YouTube chấp nhận ở lượt gần nhất — "
                              "tool đã tự chạy lại không cookie. Hãy xuất lại file cookie, hoặc "
                              "xoá trống ô cookie."))
    elif phien is not None and getattr(phien, "khong_dang_nhap_ly_do", ""):
        # Không phải YouTube từ chối cookie: máy chưa giải được thử thách JavaScript — đừng bảo xuất lại cookie.
        ra.append(("warning", "Lượt gần nhất quét KHÔNG đăng nhập: cookie đã cấu hình nhưng "
                              f"{phien.khong_dang_nhap_ly_do}."))
    elif phien is not None:
        # «Bình thường» chỉ khi có thao tác THÀNH CÔNG và không lỗi nào: ``youtube_operations`` đếm lượt thử (tăng trước
        # khi chạy), lỗi dưới ngưỡng cầu dao không mở cầu dao (audit D-10: lô hỏng hết vẫn báo xanh).
        so = phien.tom_tat()
        thanh_cong = int(so.get("successes") or 0)
        loi = {k: int(so.get(k) or 0) for k in _tc.NHAN_TRUONG_THAT_BAI if so.get(k)}
        tong_loi = sum(loi.values())
        chi_tiet = ", ".join(f"{_tc.NHAN_TRUONG_THAT_BAI[k]}: {n}" for k, n in loi.items())
        if tong_loi and not thanh_cong:
            ra.append(("warning", f"Lượt gần nhất: KHÔNG thao tác YouTube nào thành công — {tong_loi} lỗi ({chi_tiet}), "
                                  "chưa tới ngưỡng dừng cả lượt. Xem lỗi của từng video trong kết quả."))
        elif tong_loi:
            ra.append(("info", f"Lượt gần nhất: {thanh_cong} thao tác YouTube thành công, {tong_loi} lỗi ({chi_tiet}) "
                               "— chưa tới ngưỡng dừng cả lượt. Xem lỗi của từng video trong kết quả."))
        elif thanh_cong:
            ra.append(("success", "Lượt gần nhất: truy cập YouTube bình thường."))
        elif so.get("youtube_operations"):
            ra.append(("info", "Lượt gần nhất: chưa thao tác YouTube nào chạy xong (có thể đã bấm Dừng)."))
    if getattr(cd, "hai_nguon", False):
        ra.append(("warning", "Đang cấu hình CẢ file cookie lẫn «Lấy thẳng từ trình duyệt» — tool CHỈ dùng file "
                              "cookie, ô trình duyệt bị bỏ qua. Xoá trống một trong hai ô để hết cảnh báo này."))
    if not cd.cau_hinh:
        ra.append(("info", "Cookie: chưa cấu hình."))
    elif cd.trang_thai == _tc.COOKIE_TU_TRINH_DUYET:
        ra.append(("info", "Cookie lấy từ trình duyệt (bạn tự cấu hình) — tool không mở profile "
                           "trình duyệt để kiểm."))
    elif cd.trang_thai == _tc.COOKIE_KHONG_TON_TAI:
        ra.append(("warning", "Không thấy file cookie ở đường dẫn đã nhập."))
    elif cd.trang_thai == _tc.COOKIE_FILE_STRUCTURALLY_VALID:
        ra.append(("success",
                   f"File cookie đúng cấu trúc: {cd.so_ban_ghi} bản ghi "
                   f"({cd.so_ban_ghi_youtube} của YouTube, {cd.so_het_han} đã hết hạn), "
                   f"{'có' if cd.co_cookie_dang_nhap else 'KHÔNG có'} cookie đăng nhập. Đúng cấu "
                   "trúc chưa chắc YouTube còn chấp nhận phiên — chỉ lượt quét mới biết."))
    else:
        dong = ", ".join(str(x) for x in cd.dong_hong_dau)
        ra.append(("error",
                   f"File cookie sai cấu trúc (định dạng {cd.dinh_dang or '?'}, "
                   f"{cd.so_dong_hong} dòng hỏng{f' ở dòng {dong}' if dong else ''}"
                   f"{'' if cd.co_tieu_de else ', thiếu dòng tiêu đề Netscape'}) — yt-dlp sẽ "
                   "từ chối; hãy xuất lại bằng tiện ích trình duyệt."))
    if cd.cau_hinh and js is not None:
        # Nguồn FILE thì tool đọc được nội dung: chỉ nói «DÙNG cookie đăng nhập» khi file qua được cổng cấu trúc VÀ có
        # cookie tài khoản (sự cố 15/10/2026: file không có LOGIN_INFO/SAPISID mà vẫn nói dùng đăng nhập). Trình duyệt:
        # tool không mở profile để kiểm, giữ câu cũ.
        la_file = getattr(cd, "nguon", "") == "file"
        if not getattr(js, "san_sang", False):
            ra.append(("warning", f"Cookie đăng nhập CHƯA dùng được trên máy này: {js.ly_do}. Lượt quét sẽ chạy "
                                  "KHÔNG đăng nhập và ghi rõ điều đó trong kết quả. Muốn dùng cookie: cài Node.js ≥ 22 "
                                  "và dùng bản Tool có gói yt-dlp-ejs; muốn hết cảnh báo: xoá trống ô cookie."))
        elif la_file and cd.trang_thai != _tc.COOKIE_FILE_STRUCTURALLY_VALID:
            # Thiếu / không đọc được / sai cấu trúc: cổng `ytdlp_chung.kiem_tra_file_cookie` ném LoiFileCookie trước
            # request đầu → COOKIE_INVALID_OR_EXPIRED, cầu dao ngưỡng 1.
            ra.append(("warning", "Khi quét: KHÔNG đăng nhập được bằng file cookie này (xem dòng trên) — lượt quét sẽ "
                                  f"dừng với lỗi cookie, dù máy đã sẵn sàng giải thử thách JavaScript bằng {js.mo_ta()}. "
                                  "Hãy xuất lại cookies.txt từ trình duyệt đang đăng nhập YouTube, hoặc xoá trống ô "
                                  "cookie để quét không đăng nhập."))
        elif la_file and not cd.co_cookie_dang_nhap:
            ra.append(("warning", "Khi quét: KHÔNG đăng nhập — file cookie nạp được và máy đã sẵn sàng giải thử thách "
                                  f"JavaScript bằng {js.mo_ta()}, nhưng file KHÔNG có cookie đăng nhập YouTube (thiếu "
                                  "LOGIN_INFO / SAPISID) nên lượt quét chạy như CHƯA đăng nhập. Muốn quét có đăng nhập: "
                                  "xuất lại cookies.txt từ trình duyệt đang đăng nhập YouTube."))
        else:
            ra.append(("info", "Khi quét: DÙNG cookie đăng nhập — yt-dlp giải thử thách JavaScript bằng "
                               f"{js.mo_ta()}. Đã CẤU HÌNH chưa có nghĩa là YouTube CHẤP NHẬN phiên đăng nhập — kết "
                               "quả mỗi lượt đồng bộ ghi rõ đã xác minh hay chưa."))
    return ra


_MUC_DANG_NHAP = {"DA_XAC_MINH": "success", "CHUA_XAC_MINH": "info", "KHONG_COOKIE": "info",
                  "BI_TU_CHOI": "warning", "KHONG_DANG_NHAP": "warning", "KHONG_CO_COOKIE_DANG_NHAP": "warning"}


# Mã có trong `downloaded.txt` mà gốc kho không có file (audit D-7): đồng bộ CỐ Ý không tải lại — dùng chung cho kết quả
# đồng bộ và «Kiểm tra còn thiếu» để hai màn hình nói cùng một điều.
CAU_TRONG_SO_KHONG_FILE = (
    "{n} video có trong sổ đã tải (`downloaded.txt`) nhưng KHÔNG thấy file ở thư mục kho — đồng bộ KHÔNG tải lại "
    "(có thể bạn đã chủ ý xoá) và KHÔNG tính là «có sẵn». File đã mất thật thì kho thiếu vân tay của chúng — muốn tải "
    "lại: bấm «Dựng lại danh sách đã tải» rồi «Bắt đầu đồng bộ kênh». Nếu bạn chỉ chuyển file vào thư mục con thì "
    "đừng dựng lại (sẽ tải trùng).")


def tom_tat_dong_bo_kenh(r: Mapping[str, Any]) -> list:
    """Các dòng ``(mức, câu)`` cho kết quả một lượt đồng bộ kênh (``ChannelSync.sync``). Dòng đầu là tiêu đề:
    CHỈ «✅ Đồng bộ xong» màu xanh khi mọi video cần tải đã tải xong (sự cố 15/10/2026: cầu dao đã mở, 1.189 video
    chưa thử mà vẫn báo xong màu xanh). Không đọc file, không gọi mạng; kết quả đồng bộ không mang cookie."""
    tt = r.get("trang_thai") or ("DA_HUY" if r.get("da_huy") else "BI_CHAN" if r.get("chan_youtube") else "DAY_DU")
    moi, co_san = int(r.get("moi") or 0), int(r.get("bo_qua") or 0)
    so_loi, chua_thu = int(r.get("so_loi") or 0), int(r.get("chua_thu") or 0)
    han_che = int(r.get("han_che_bo_qua") or 0)
    trong_so = int(r.get("trong_so_khong_file") or 0)
    so = (f"có sẵn **{co_san}** (giữ nguyên), tải mới **{moi}**, lỗi **{so_loi}**, chưa thử **{chua_thu}**"
          + (f", bị hạn chế (chưa tải) **{han_che}**" if han_che else "")
          + (f", trong sổ đã tải nhưng không có file **{trong_so}**" if trong_so else "")
          + f". Thư mục: `{r.get('thu_muc', '')}`")
    if tt == "DAY_DU":
        ra = [("success", f"✅ Đồng bộ xong: {so}")]
    elif tt == "MOT_PHAN":
        ra = [("warning", f"⚠️ Đồng bộ xong MỘT PHẦN — còn video chưa tải được: {so}")]
    elif tt == "DA_HUY":
        ra = [("warning", f"⏹️ Đã dừng đồng bộ theo yêu cầu: {so}")]
    else:
        ra = [("error", f"🚫 Đồng bộ DỪNG giữa chừng — chưa xong: {so}")]
    if r.get("chan_youtube"):
        ra.append(("error", f"Lý do dừng: {r['chan_youtube']}"))
    tuoi, hoi_vien = int(r.get("gioi_han_tuoi") or 0), int(r.get("chi_hoi_vien") or 0)
    if tuoi:
        ra.append(("warning", f"{tuoi} video giới hạn độ tuổi bị bỏ qua — chỉ tài khoản đã đăng nhập (và đã xác minh "
                              "tuổi) xem được; tool không vượt giới hạn này."))
    if hoi_vien:
        ra.append(("warning", f"{hoi_vien} video chỉ dành cho hội viên kênh / phải trả phí bị bỏ qua."))
    if han_che:
        ra.append(("warning", f"{han_che} video bị hạn chế (giới hạn tuổi / chỉ hội viên) từ lượt trước — CHƯA tải; lượt "
                              "này không gửi lại request vô ích cho chúng. Tool tự thử lại khi cách đăng nhập đổi "
                              "(thêm/đổi nguồn cookie, cài Node.js + yt-dlp-ejs); muốn thử lại ngay: bật «Thử lại cả "
                              "video bị hạn chế»."))
    if trong_so:
        ra.append(("warning", CAU_TRONG_SO_KHONG_FILE.format(n=trong_so)))
    xt = r.get("xac_thuc") or {}
    if xt.get("cau"):
        ra.append((_MUC_DANG_NHAP.get(xt.get("trang_thai", ""), "info"), f"Đăng nhập YouTube: {xt['cau']}"))
    if r.get("canh_bao_cookie"):
        ra.append(("warning", str(r["canh_bao_cookie"])))
    if tt != "DAY_DU" and (so_loi or chua_thu or han_che):
        ra.append(("info", "Video lỗi / chưa thử / bị hạn chế KHÔNG được ghi là đã tải: bấm «Bắt đầu đồng bộ kênh» lần "
                           "nữa để tải tiếp phần còn thiếu — file đã có được giữ nguyên, không tải trùng."))
    return ra


def _cung_thu_muc(a: str, b: str) -> bool:
    import os

    def chuan(p: str) -> str:
        # abspath tự bỏ dấu gạch cuối; KHÔNG rstrip («D:\» → «D:» = thư mục hiện hành của ổ D).
        return os.path.normcase(os.path.normpath(os.path.abspath((p or "").strip().strip('"'))))
    return bool((a or "").strip() and (b or "").strip()) and chuan(a) == chuan(b)


def canh_bao_nguon_kho(thu_muc_chon: str, kho_dang_dung: str, thu_muc_kho: str, so_clip_kho: int,
                       thu_muc_suy_tu_van_tay: str = "") -> Optional[tuple]:
    """``(mức, câu, cần_xác_nhận_tạo_lại)`` khi thư mục đang chọn KHÔNG phải nguồn đã biết của một kho ĐÃ có vân tay:
    «Bổ sung» sẽ bị engine từ chối (không trộn nguồn), còn «Tạo lại kho từ đầu» sẽ THAY toàn bộ vân tay hiện có — phải
    xác nhận trước. ``None`` khi không có gì để mất (chưa chọn thư mục / kho, kho chưa có clip, cùng nguồn đã gắn).
    Kho cũ chưa ghi thư mục nguồn: chỉ coi là cùng nguồn khi trùng ``thu_muc_suy_tu_van_tay``
    (``Engine.thu_muc_nguon_tu_van_tay``)."""
    if not (thu_muc_chon or "").strip() or not kho_dang_dung or not so_clip_kho:
        return None
    thay = (f"«Tạo lại kho từ đầu» sẽ THAY TOÀN BỘ {so_clip_kho} clip đang có vân tay của kho «{kho_dang_dung}» bằng "
            "thư mục này. Thư mục của nguồn khác thì «Tạo kho mới».")
    if (thu_muc_kho or "").strip():
        if _cung_thu_muc(thu_muc_chon, thu_muc_kho):
            return None
        return ("warning", f"Thư mục này KHÁC thư mục nguồn của kho «{kho_dang_dung}» (`{thu_muc_kho}`). «Bổ sung» sẽ bị "
                           f"từ chối để không trộn clip của nguồn khác vào kho này. {thay}", True)
    if _cung_thu_muc(thu_muc_chon, thu_muc_suy_tu_van_tay):
        return ("info", f"Kho «{kho_dang_dung}» là kho cũ chưa ghi thư mục nguồn; thư mục này TRÙNG nguồn suy từ vân tay "
                        "của kho — «Bổ sung» sẽ ghi thư mục này vào sổ kho.", False)
    return ("warning", f"Kho «{kho_dang_dung}» là kho cũ chưa ghi thư mục nguồn, và thư mục này không phải nguồn của các "
                       "clip đã có vân tay"
            + (f" (nguồn suy từ vân tay: `{thu_muc_suy_tu_van_tay}`)" if thu_muc_suy_tu_van_tay else "")
            + f". «Bổ sung» sẽ bị từ chối. {thay}", True)


def huong_dan_kho_sau_dong_bo(thu_muc_dong_bo: str, kho_dang_dung: str, thu_muc_kho: str) -> tuple:
    """``(mức, câu)`` — bước tiếp theo sau đồng bộ: KHÔNG xui nạp audio của nguồn này vào kho vân tay của nguồn khác
    (sự cố 15/10/2026: thư mục audio của kênh vừa đồng bộ ≠ kho «SML» đang chọn)."""
    if kho_dang_dung and _cung_thu_muc(thu_muc_dong_bo, thu_muc_kho):
        return ("info", f"Bước tiếp theo: tab «Kho clip gốc» → «Bổ sung clip mới vào kho» cho kho «{kho_dang_dung}» "
                        "(đúng kho của thư mục vừa đồng bộ) để tạo vân tay các video vừa tải.")
    hien = (f"Kho vân tay đang chọn là «{kho_dang_dung}» (thư mục `{thu_muc_kho or '(chưa đặt)'}`) — KHÁC thư mục vừa "
            "đồng bộ. Đừng nạp audio này vào kho đó." if kho_dang_dung else "Chưa chọn kho vân tay nào.")
    return ("warning", f"{hien} Tạo kho riêng cho nguồn này: tab «Kho clip gốc» → «Tạo kho mới» (ví dụ theo tên kênh), "
                       f"chọn kho đó ở thanh bên, đặt thư mục `{thu_muc_dong_bo}`, rồi «Bổ sung clip mới vào kho».")


def thong_bao_youtube_chan(ket_qua: Sequence[Any]) -> str:
    """Lý do cầu dao YouTube đã mở trong batch (rỗng nếu không): lấy từ chính kết quả "chưa
    quét" để không phụ thuộc trạng thái engine sau này."""
    for x in ket_qua:
        f = getattr(x, "loi_truy_cap", None)
        if getattr(f, "category", "") == _tc.BLOCKED_BY_BREAKER:
            cau = getattr(f, "human_message_vi", "") or ""
            return cau.split("Chưa quét — ", 1)[-1]
    return ""

# Ký hiệu "chưa có dữ liệu". Dùng chung để UI và test không lệch nhau.
CHUA_CO = "—"

COT = ("#", "Video", "Quét", "Đoạn", "Sheets")

TEN_TRANG_THAI_QUET = {
    "completed": "✅ Xong",
    "failed": "❌ Lỗi",
    "running": "⏳ Đang chạy",
    "queued": "Chờ",
}
# Trạng thái việc gửi Google Sheets (outbox lưu bền) — cùng nhãn với tab «📤 Gửi Google Sheets».
TEN_TRANG_THAI_SHEET = dict(outbox.NHAN_TRANG_THAI)


GOI_Y_VUNG_LOI = "Nguồn có vùng lỗi hoặc file tải về thiếu: quét lại nguồn đó."
GOI_Y_TOP1 = ("Kết quả Top-1 lấy từ phần đầu video (tìm nhanh): cần quét trọn thì đặt "
              "Top-N lớn hơn 1, hoặc tắt `top1_tim_nhanh` trong `data/cau_hinh.json`.")
GOI_Y_TANG_DAN = ("Quét tăng dần đã dừng sớm hoặc chỉ tải phần đầu: tắt «Quét tăng dần "
                  "cho video rất dài» ở thanh bên → «⚙️ Tham số» → «Mở để tinh chỉnh».")
GOI_Y_VIDEO_DAI = ("Video dài chỉ được quét phần đầu theo «Giới hạn quét video dài»: phần sau CHƯA "
                   "quét. Muốn quét thêm, chọn «6 giờ đầu» hoặc «Quét toàn bộ video» rồi quét lại.")


def goi_y_quet_mot_phan(ket_qua: Sequence[Any], cau_hinh: Any = None) -> list:
    """Lời khuyên cho các nguồn CHƯA quét trọn, theo ĐÚNG lý do (phản biện TCP-06).

    Tắt «Quét tăng dần» không giúp gì cho kết quả Top-1 tìm nhanh trên video ngắn hay cho
    vùng lỗi. Ngược lại, Top-1 dừng sớm BÊN TRONG một lượt tải một phần / quét tăng dần
    thì phải nói cả hai: chỉ tắt tìm nhanh, video dài vẫn dừng ở đoạn đầu (phản biện
    vòng 2).
    """
    def duong_di(r) -> str:
        return getattr(getattr(r, "chan_doan", None), "duong_di", "") or ""

    def do_tang_dan(r) -> bool:
        ly_do = getattr(r, "ly_do_pham_vi", "") or ""
        if ly_do == "gioi_han_tai":
            return True
        if ly_do != "dung_som":
            return False
        if duong_di(r) != "dung_som_vung_dau":
            return True
        # Top-1 tìm nhanh đã dừng: quét tăng dần CŨNG góp phần khi video vượt ngưỡng.
        nguong = float(getattr(cau_hinh, "quet_tang_dan_tu_gio", 0) or 0) * 3600
        return (bool(getattr(cau_hinh, "quet_tang_dan", False))
                and float(getattr(r, "duration_s", 0) or 0) > nguong)

    goi_y = []
    if any(getattr(r, "vung_loi", None) for r in ket_qua):
        goi_y.append(GOI_Y_VUNG_LOI)
    if any(duong_di(r) == "dung_som_vung_dau" for r in ket_qua):
        goi_y.append(GOI_Y_TOP1)
    if any(do_tang_dan(r) for r in ket_qua):
        goi_y.append(GOI_Y_TANG_DAN)
    if any((getattr(r, "ly_do_pham_vi", "") or "") == "gioi_han_video_dai" for r in ket_qua):
        goi_y.append(GOI_Y_VIDEO_DAI)
    return goi_y


def _mo_ta_sheet(delivery_key: str, trang_thai_sheet: Mapping[str, Any]) -> str:
    if not delivery_key:
        return CHUA_CO
    muc = trang_thai_sheet.get(delivery_key)
    if muc is None:
        return CHUA_CO
    trang_thai = getattr(muc, "trang_thai", "")
    return TEN_TRANG_THAI_SHEET.get(trang_thai, str(trang_thai) or CHUA_CO)


def build_scan_status_dataframe(
    videos: Sequence[Any],
    trang_thai_sheet: Optional[Mapping[str, Any]] = None,
) -> pd.DataFrame:
    """Bảng trạng thái từng video, dtype tường minh nên Arrow không phải đoán.

    ``videos``: các ``scan_jobs.VideoState``.
    ``trang_thai_sheet``: map ``mã việc gửi -> outbox.ViecGui`` (có thể rỗng).
    """
    trang_thai_sheet = trang_thai_sheet or {}
    dong = []
    for v in videos:
        so_doan = getattr(v, "matches", None)
        dong.append({
            "#": str(getattr(v, "index", "")),
            "Video": str(getattr(v, "title", "") or getattr(v, "nguon", ""))[:60],
            "Quét": TEN_TRANG_THAI_QUET.get(
                getattr(v, "scan_status", ""), str(getattr(v, "scan_status", ""))
            ),
            # 0 và "chưa quét" là hai chuyện khác nhau — phải phân biệt được.
            "Đoạn": CHUA_CO if so_doan is None else str(so_doan),
            "Sheets": _mo_ta_sheet(str(getattr(v, "delivery_key", "") or ""),
                                   trang_thai_sheet),
        })

    khung = pd.DataFrame(dong, columns=list(COT))
    # Khai báo dtype cho CẢ khung rỗng: bảng lúc mới bắt đầu quét cũng phải có
    # schema ổn định, nếu không lần render đầu vẫn rơi vào nhánh sửa dtype.
    return khung.astype({cot: "string" for cot in COT})


# =====================================================================
#  Chế độ «Một video gốc chung cho cả lô»
# =====================================================================

COT_NGUON_CHUNG = ("#", "Video", "Lượt quét", "Video gốc đang xét", "Phạm vi đã quét",
                   "Ghi chú")


def build_nguon_chung_status_dataframe(videos: Sequence[Any]) -> pd.DataFrame:
    """Bảng trạng thái lúc chạy (``common_original_jobs.VideoNguonChung``); toàn chuỗi."""
    dong = []
    for v in videos:
        trang_thai = str(getattr(v, "trang_thai", "") or "")
        loi = str(getattr(v, "loi", "") or "")
        dong.append({
            "#": str(getattr(v, "thu_tu", "")),
            "Video": ("⏳ " if getattr(v, "dang_quet", False) else "")
            + str(getattr(v, "tieu_de", "") or getattr(v, "nguon", ""))[:60],
            "Lượt quét": str(getattr(v, "so_luot", 0)),
            "Video gốc đang xét": TEN_TRANG_THAI_CAP.get(trang_thai, trang_thai or CHUA_CO),
            "Phạm vi đã quét": str(getattr(v, "pham_vi", "") or CHUA_CO),
            "Ghi chú": loi.splitlines()[0][:80] if loi else "",
        })
    khung = pd.DataFrame(dong, columns=list(COT_NGUON_CHUNG))
    return khung.astype({cot: "string" for cot in COT_NGUON_CHUNG})


def df_nguon_chung(kql: Any) -> pd.DataFrame:
    """Bảng kết quả lô (một dòng mỗi video) với cột số ĐÚNG KIỂU (xem CLAUDE.md mục 7)."""
    df = pd.DataFrame(dong_bao_cao(kql, an_toan=False), columns=HEADER_NGUON_CHUNG)
    for cot in COT_SO_NGUON_CHUNG:
        so = pd.to_numeric(df[cot], errors="coerce")
        khong_rong = so.dropna()
        if not khong_rong.empty and (khong_rong % 1 == 0).all():
            so = so.astype("Int64")
        df[cot] = so
    return df


def csv_nguon_chung(kql: Any) -> bytes:
    """CSV utf-8-sig của kết quả lô, ô đã chặn công thức bảng tính."""
    df = pd.DataFrame(dong_bao_cao(kql), columns=HEADER_NGUON_CHUNG)
    return df.to_csv(index=False).encode("utf-8-sig")
