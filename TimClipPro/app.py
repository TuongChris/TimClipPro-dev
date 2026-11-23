# -*- coding: utf-8 -*-
"""
app.py — GIAO DIỆN của TimClip Pro (Streamlit, chạy 100% trên máy bạn).

Đây chỉ là lớp áo mỏng: mọi xử lý thật đều nằm trong engine.py.
Muốn đổi sang giao diện khác (CLI, desktop, API) thì thay file này, engine giữ nguyên.

Chạy: double-click ChayTool.bat  (hoặc: streamlit run app.py)
Dữ liệu KHÔNG đi đâu cả — server chỉ lắng nghe ở localhost trên máy bạn.
"""

import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st

import bang_ngang
import bao_cao_v2
import common_original as nguon_chung
import danh_sach_video
import kiem_video_con
import lich_su
import luu_tru
import maintenance_gate
import outbox
import runtime_paths
import sheet_destinations
import tac_vu_nen
import thong_ke
import ui_cap_nhat
import ui_gui_sheets as ui_gui
from cau_hinh import GIA_TRI_GIAO_DIEN_MAC_DINH
from clip_metadata import configure_metadata_logging
import tim_nghi_van
import truy_cap_youtube
import youtube_api
import ytdlp_chung
from common_original_jobs import TEN_PHA as TEN_PHA_NGUON_CHUNG
from common_original_jobs import CommonOriginalJobController, xuat_csv
from engine import Engine, LoiXoaJob, ScanResult, hhmmss, hhmmss_tp, mo_ta_pham_vi, o_bang_tinh_an_toan
from engine import GHVD_TOAN_BO, GHVD_TU_DONG, NHAN_GHVD
from fingerprint_progress import FingerprintJobController
from khoa import DangChayRoi
from publication_date import format_publication_date
from scan_jobs import ScanJobController
import ui_tien_do_quet
from scan_ui import (
    CAU_QUA_DAI,
    CAU_TRONG_SO_KHONG_FILE,
    build_nguon_chung_status_dataframe,
    build_scan_status_dataframe,
    canh_bao_nguon_kho,
    chua_quet_cua_lo,
    csv_nguon_chung,
    dem_cau_tom_tat,
    df_nguon_chung,
    dong_trang_thai_api_youtube,
    dong_trang_thai_youtube,
    goi_y_quet_mot_phan,
    huong_dan_kho_sau_dong_bo,
    thoat_markdown,
    thong_bao_lo_da_dung,
    thong_bao_youtube_chan,
    tien_do_nguon_chung,
    tom_tat_dong_bo_kenh,
    tom_tat_tao_van_tay,
)
import channel
import cat_video_goc
import ghep_video_goc
import tai_video_goc
import video_trong_may
import ui_thao_tac
from channel import ChannelSync
from tien_do_dong_bo import SoDongBo
from ui_tien_do_dong_bo import dong_ho, dong_hieu_suat, ve_tien_do_dong_bo
from sheets import SheetsExporter

st.set_page_config(page_title="TimClip Pro — Tìm video gốc trong video dài",
                   page_icon="🔎", layout="wide")
configure_metadata_logging()

# =====================================================================
#  Khởi tạo (giữ nguyên giữa các lần Streamlit vẽ lại màn hình)
# =====================================================================

if "eng" not in st.session_state:
    try:
        st.session_state.eng = Engine(
            data_dir=os.environ.get("TIMCLIP_DATA_DIR") or None,
            out_dir=os.environ.get("TIMCLIP_OUTPUT_DIR") or None,
        )
    except (runtime_paths.LoiRuntime, sheet_destinations.LoiDichGui, lich_su.LoiLichSuHong) as e:
        # Cấu hình runtime sai (bản managed thiếu state root, lịch sử của máy khác…) hoặc lichsu.db
        # hỏng (audit B-8): dừng rõ ràng — không đoán thư mục dữ liệu, không tạo DB ở chỗ đoán.
        st.error(f"Không khởi động được TimClip Pro: {e}")
        st.stop()
du_lieu_giao_dien = st.session_state.eng.cau_hinh_da_luu
for khoa, mac_dinh in GIA_TRI_GIAO_DIEN_MAC_DINH.items():
    if khoa not in st.session_state:
        gia_tri = du_lieu_giao_dien.get(khoa, mac_dinh)
        st.session_state[khoa] = (
            gia_tri if type(gia_tri) is type(mac_dinh) else mac_dinh
        )
if "job" not in st.session_state:
    st.session_state.job = {"running": False, "pct": 0.0, "msg": "", "results": [],
                            "error": "", "kind": ""}
# Làn RIÊNG của đồng bộ kênh (``tac_vu_nen.LOAI_SONG_SONG``): chạy song song với việc của ``job`` (quét, dựng vân tay,
# lô «Một video gốc chung», …) — có cờ huỷ riêng, các tab vẫn hiện trong lúc đồng bộ (người dùng duyệt 27/10/2026).
if "job_dong_bo" not in st.session_state:
    st.session_state.job_dong_bo = {"running": False, "pct": 0.0, "msg": "", "results": [],
                                    "error": "", "kind": ""}

eng: Engine = st.session_state.eng
job = st.session_state.job
job_dong_bo = st.session_state.job_dong_bo
# Dựng kho vân tay / lô «Một video gốc chung» chạy hàng giờ. Tải lại trang, tab thứ hai = phiên MỚI: phiên rảnh NHẬN
# LẠI việc đang chạy trên cùng thư mục dữ liệu (tiến độ, nút Dừng tới đúng worker, «đang bận», kết quả cuối) qua sổ
# mức tiến trình như tác vụ nền (``tac_vu_nen.SoViecDai``, audit D-13/F-2); phiên mới chưa làm gì còn nhận việc đã xong
# mà chưa ai xem. Việc mượn giữ Engine của phiên đã bấm: xong + chép kết quả → controller của chính phiên.
fingerprint_controller: FingerprintJobController = FingerprintJobController.cua_phien(
    eng, st.session_state.get("fingerprint_controller"), dang_hien=bool(job.get("running")),
    phien_moi=not job.get("kind"))
st.session_state.fingerprint_controller = fingerprint_controller
if fingerprint_controller.engine is not eng and not job.get("running"):
    job.update({"running": True, "pct": 0.0, "msg": "", "results": [], "error": "", "kind": "db",
                "da_day_sheet": False, "fingerprint_job_id": fingerprint_controller.snapshot().job_id})
common_controller: CommonOriginalJobController = CommonOriginalJobController.cua_phien(
    eng, st.session_state.get("common_controller"), dang_hien=bool(job.get("running")),
    phien_moi=not job.get("kind"))
st.session_state.common_controller = common_controller
if common_controller.engine is not eng and not job.get("running"):
    job.update({"running": True, "pct": 0.0, "msg": "", "results": [], "error": "", "kind": "nguon_chung",
                "da_day_sheet": True, "ma_lo": common_controller.snapshot().ma_lo})


def _dong_bo_job_van_tay() -> None:
    """Chỉ main Streamlit thread đọc controller và cập nhật session_state."""
    if job.get("kind") != "db" or not job.get("fingerprint_job_id"):
        return
    if job.get("running") and not fingerprint_controller.running:
        job["running"] = False
        job["results"] = fingerprint_controller.result or []
        job["error"] = fingerprint_controller.error
        FingerprintJobController.da_nhan(eng, fingerprint_controller)   # phiên mở sau không hiện lại


_dong_bo_job_van_tay()


# Tải lại trang = phiên MỚI: lô của phiên trước còn chạy thì NHẬN LẠI nó (xem tiến độ, bấm Dừng),
# không tạo controller trống cho phép bấm «Bắt đầu quét» lần nữa. Lô mượn xong + đã chép kết quả →
# controller của CHÍNH phiên này (Engine của phiên), không quét mãi trên Engine phiên cũ (audit F-1).
st.session_state.scan_controller = ScanJobController.cua_phien(
    eng, st.session_state.get("scan_controller"), dang_hien_lo=bool(job.get("running")))
scan_controller: ScanJobController = st.session_state.scan_controller
if scan_controller.running and not job.get("running"):
    job.update({"running": True, "pct": 0.0, "msg": "", "results": [], "error": "",
                "kind": "scan", "da_day_sheet": True,
                "scan_batch_id": scan_controller.snapshot().batch_id})


def _dong_bo_tac_vu_nen(chi_dong_bo: bool = False) -> None:
    """Tác vụ nền (đồng bộ kênh, lấy lại tên, vá metadata) sống ở mức TIẾN TRÌNH (``tac_vu_nen``). Tải lại trang
    giữa lượt = phiên MỚI: NHẬN LẠI tác vụ đang chạy (tiến độ, nút Dừng, kết quả cuối) thay vì coi như không có gì
    chạy (audit D-13). Chỉ main thread chép ảnh chụp vào ``job`` của phiên; thread nền không đọc session_state.
    Tác vụ đã XONG khi không phiên nào vẽ (tab bị dỡ, chạy qua đêm): phiên MỚI (chưa làm gì — ``job`` chưa có loại)
    nhận kết quả cuối đúng một lần; phiên đang hiện kết quả việc khác không bị đè (review audit D).
    Hai làn: đồng bộ kênh (``tac_vu_nen.la_song_song``) vào ``job_dong_bo``; việc khác vào ``job``. ``chi_dong_bo``:
    chỉ làn đồng bộ (khung tiến độ đồng bộ tự làm mới riêng, không đụng ``job`` của trang)."""
    lan = ((True, "tac_vu_dong_bo", job_dong_bo),)
    if not chi_dong_bo:
        lan = ((False, "tac_vu_nen", job),) + lan
    for song_song, khoa_tv, j in lan:
        tv = st.session_state.get(khoa_tv)
        # Làn đồng bộ: cú bấm thứ hai có thể cắt ``chay_dong_bo`` trước khi ghi ``tac_vu_dong_bo``. Khi đó ``running`` đã
        # True mà phiên chưa giữ lượt: vẫn phải nhận lại, nếu không nút Dừng không còn gì để huỷ.
        if tv is None and (song_song or not j.get("running")):
            tv = tac_vu_nen.dang_chay_cua(eng)
            if tv is not None and tac_vu_nen.la_song_song(tv.kind) != song_song:
                tv = None
            if tv is None and not j.get("kind"):
                tv = tac_vu_nen.nhan_vua_xong(eng, lambda v, s=song_song: tac_vu_nen.la_song_song(v.kind) == s)
            if tv is None:
                continue
            st.session_state[khoa_tv] = tv
            if tv.so_dong_bo is not None:
                st.session_state.so_dong_bo = tv.so_dong_bo
        if tv is None:
            continue
        j.update(tv.anh())
        if not j["running"]:
            if tv.phien_youtube is not None:         # «Trạng thái YouTube» = lượt vừa xong này (audit D-14)
                eng.phien_youtube_cuoi = tv.phien_youtube
            st.session_state.pop(khoa_tv, None)      # xong: kết quả đã chép, thôi theo dõi
            tac_vu_nen.da_nhan(eng, tv)              # phiên mở sau không nhận lại


_dong_bo_tac_vu_nen()
# MỌI thứ vẽ ở thân trang phía trên hàng tab nằm trong khung này: số dòng trong khung đổi (đang chạy → kết quả →
# trống) thì hàng tab vẫn ở cùng vị trí, trình duyệt không dựng lại nó → giữ nguyên tab đang mở (trước đây xong
# việc là nhảy về tab đầu — người dùng báo 17/11).
_khu_tren = st.container()
# Bản cài managed: bản mới đã kích hoạt mà cửa sổ này còn chạy bản cũ → cảnh báo nổi ở đầu trang.
with _khu_tren:
    ui_cap_nhat.canh_bao_ban_cu()
# Gửi Google Sheets: hàng đợi BỀN trong lichsu.db + MỘT người gửi nền mỗi tiến trình (không đọc
# st.session_state). Còn việc chờ từ lần chạy trước (tắt app, mất điện) thì gửi tiếp ngay.
ui_gui.dam_bao_nguoi_gui(eng)


def dang_co_tac_vu() -> bool:
    """Có tác vụ nào đang chạy không. Mọi controller dùng chung cờ huỷ của Engine: khởi
    động cái này khi cái kia còn chạy là xoá mất một cú bấm Dừng đang chờ (TCP-13)."""
    return bool(job.get("running") or scan_controller.running
                or common_controller.running or fingerprint_controller.running)


def chay_quet(nguon: list, source_type: str, *, dich_id: str = "", tu_dong: bool = False,
              tab_key: str = "", gioi_han_video_dai: str | None = None) -> None:
    """Khởi động batch quét. Kết quả hiện ngay từng video; việc gửi Sheets xếp hàng bền song song.
    ``gioi_han_video_dai``: chế độ giới hạn video dài của lô YouTube (``engine.GHVD_*``)."""
    if dang_co_tac_vu():
        st.warning("Đang có tác vụ chạy; không tạo job trùng.")
        return
    # Đích gửi CHỤP + GHIM ngay tại đây (main thread): thread nền không có ScriptRunContext, và
    # đổi lựa chọn giữa lô không được làm lô đang chạy bắn sang bảng khác. Preflight cục bộ (hồ sơ,
    # khoá) lỗi thì báo TRƯỚC khi quét.
    lo_id = uuid.uuid4().hex
    y_dinh, loi = ui_gui.chot_cho_lo(eng, dich_id, tu_dong, lo_id)
    if loi:
        st.error(loi)
        return
    if y_dinh is not None:
        ui_gui.dam_bao_nguoi_gui(eng, bat_buoc=True)
        st.session_state.dich_gui_gan_nhat = dich_id
    db = eng.sqlite_file

    def sau_moi_video(index: int, tong: int, ket_qua) -> None:
        """Chạy trong SCAN WORKER — không chạm Streamlit. Việc gửi đã được `save_job` xếp hàng
        trong CÙNG giao dịch với lịch sử; ở đây chỉ gắn mã việc vào dòng trạng thái."""
        if y_dinh is None or not getattr(ket_qua, "job_id", None):
            return
        viec = outbox.ds_viec(db, job_id=ket_qua.job_id, lo_id=y_dinh.lo_id)
        if viec:
            scan_controller.ghi_nhan_giao_hang(index, viec[0].id)

    them = {"gioi_han_video_dai": gioi_han_video_dai} if gioi_han_video_dai else {}
    try:
        batch_id = scan_controller.start(nguon, source_type, on_result=sau_moi_video,
                                         y_dinh_gui=y_dinh, **them)
    except DangChayRoi as e:                   # đang cập nhật / bản cũ: chưa bắt đầu gì
        st.error(f"Chưa bắt đầu: {e}")
        return
    except RuntimeError as e:                  # lô khác (phiên khác) đang chạy: không tạo lô trùng
        st.warning(str(e))
        return
    job.update({
        "running": True, "pct": 0.0, "msg": "Đang chuẩn bị...", "results": [],
        "error": "", "kind": "scan", "da_day_sheet": True, "scan_batch_id": batch_id,
        "tab_quet": tab_key,
    })
    st.rerun()


def chay_nguon_chung(nguon: list) -> None:
    """Khởi động lô «Một video gốc chung cho cả lô».

    Bản đầu không đẩy Google Sheets và không ghi lịch sử quét (xem
    ``docs/COMMON_ORIGINAL_DESIGN.md``); kết quả xuất CSV.
    """
    if dang_co_tac_vu():
        st.warning("Đang có tác vụ chạy; không tạo job trùng.")
        return
    try:
        ma_lo = common_controller.start(nguon, "youtube")
    except RuntimeError as e:                  # lô khác (phiên khác) vừa bắt đầu: không tạo lô trùng
        st.warning(str(e))
        return
    job.update({
        "running": True, "pct": 0.0, "msg": "Đang chuẩn bị...", "results": [],
        "error": "", "kind": "nguon_chung", "da_day_sheet": True, "ma_lo": ma_lo,
    })
    st.rerun()


def dang_dong_bo() -> bool:
    """Làn đồng bộ kênh đang có lượt chạy (của phiên này hoặc nhận lại từ phiên khác)."""
    return bool(job_dong_bo.get("running"))


def _thu_muc_dang_dong_bo() -> str:
    """Thư mục đích của lượt đồng bộ đang chạy trong tiến trình ("" nếu không có). Hỏi SỔ tác vụ nền (không chỉ lượt
    phiên này đã nhận): tab khác vừa bắt đầu đồng bộ mà phiên này chưa vẽ lại cũng tính."""
    tv = tac_vu_nen.dang_chay_cua(eng)
    return tv.thu_muc if tv is not None and tac_vu_nen.la_song_song(tv.kind) else ""


@st.fragment(run_every=2)
def _khung_dong_bo_khac(thu_muc: str, viec: str, chu_luot_trang: list) -> None:
    """Cảnh báo của ``_canh_bao_dong_bo_khac``: chỉ được gọi khi thư mục đang bị giữ, rồi tự dò lại mỗi 2 giây (phép dò
    chỉ hỏi, không chờ) mà không vẽ lại cả trang; bên kia xong → vẽ lại cả trang để mở khoá các nút. Lượt vẽ cả trang
    dùng kết quả dò của trang (``chu_luot_trang``, lấy MỘT lần — mỗi nhịp sau Streamlit gọi lại với chính danh sách đó,
    đã rỗng): dò lại ngay mà thấy rảnh thì st.rerun giữa lượt làm mất giá trị các ô chưa vẽ tới."""
    chu = chu_luot_trang.pop() if chu_luot_trang else channel.dang_dong_bo_khac(thu_muc)
    if chu:
        st.warning(f"Thư mục này đang được đồng bộ kênh ở một tiến trình KHÁC (cửa sổ Tool khác hoặc lệnh "
                   f"`cli.py kenh`) — chờ lượt đó xong rồi {viec}. Thông tin khoá: {'; '.join(chu.splitlines())}")
    else:
        st.rerun(scope="app")


def _canh_bao_dong_bo_khac(thu_muc: str, viec: str) -> bool:
    """Tiến trình KHÁC (cửa sổ Tool khác, ``cli.py kenh``) đang đồng bộ kênh vào ``thu_muc``: cảnh báo kèm thông tin
    chủ khoá, trả True để khoá các nút ghi vào thư mục đó. Lượt của chính tiến trình này (làn D-29) không báo ở đây —
    ``_thu_muc_dang_dong_bo`` lo."""
    chu = channel.dang_dong_bo_khac(thu_muc)
    if chu:
        _khung_dong_bo_khac(thu_muc, viec, [chu])
    return bool(chu)


def chay_dong_bo(kenh_url: str, kho_dir: str, gioi_han: int | None, thu_lai_han_che: bool,
                 giu_thong_bao: bool = False) -> None:
    """Khởi động đồng bộ kênh ở làn RIÊNG: chạy song song với quét / dựng vân tay. Cờ huỷ RIÊNG của lượt (không phải
    ``eng.cancel_event``): Dừng hay bắt đầu lô quét không đụng lượt đồng bộ và ngược lại (TCP-13). Truyền cả
    player_clients lẫn cấu hình mạng (cookie, giãn nhịp) để mọi mẹo trong data\\cau_hinh.json có tác dụng cho cả đồng
    bộ kênh; cấu hình + thư mục đích GHIM lúc bấm — đổi kho / lưu cấu hình giữa lượt không ảnh hưởng lượt này.
    ``giu_thong_bao``: gọi từ màn tiến độ (tự vẽ lại 0,75 giây) — lời từ chối giữ trong ``thong_bao_dong_bo`` tới lần
    bấm kế, không chỉ nháy một khung (review độc lập P2-2)."""
    def bao(muc: str, chu: str) -> None:
        if giu_thong_bao:
            st.session_state.thong_bao_dong_bo = (muc, chu)
        else:
            getattr(st, muc)(chu)

    dich = kho_dir.strip('" ')
    tv_khac = tac_vu_nen.dang_chay_cua(eng)
    if dang_dong_bo() or (tv_khac is not None and tac_vu_nen.la_song_song(tv_khac.kind)):
        bao("warning", "Đang có một lượt đồng bộ kênh chạy — chờ lượt đó xong rồi đồng bộ tiếp. Hai lượt cùng lúc "
                       "dùng chung cookie YouTube nên dễ bị YouTube chặn.")
        return
    if tv_khac is not None:
        ten_viec = {"va_title": "«Lấy lại tên video»", "metadata_network": "«Vá metadata»",
                    "tai_video": "«Tải video gốc / thumbnail / cả kênh / ghép video»"}.get(tv_khac.kind, "một việc nền khác")
        bao("warning", f"Đang chạy {ten_viec} (cũng hỏi YouTube) — chờ việc đó xong rồi đồng bộ.")
        return
    dung_kho = FingerprintJobController.dang_chay_cua(eng)
    if dung_kho is not None and tac_vu_nen.thu_muc_chong_nhau(dung_kho.thu_muc, dich):
        bao("warning", "Thư mục này đang được tạo vân tay — chờ tạo vân tay xong rồi đồng bộ vào đây, để vân tay không "
                       "nạp file đang tải dở.")
        return
    # Dựng mọi thứ có thể ném lỗi (thư mục kho không tạo được, ổ đĩa rút ra, cấu hình mạng sai) TRƯỚC khi nhận lease
    # cổng bảo trì — lỗi ở đây mà đã giữ lease thì bộ cập nhật thấy «đang có việc» tới khi tắt Tool (review P2-1).
    # Sổ tiến độ MỚI cho mỗi lượt: worker ghi, khung tiến độ chỉ đọc ảnh chụp (ui_tien_do_dong_bo).
    so = SoDongBo()
    try:
        cs = ChannelSync(dich, player_clients=list(eng.config.ytdlp_player_clients),
                         cau_hinh_mang=eng.cau_hinh_mang(), theo_doi=so, data_dir=eng.data_dir)
    except Exception as e:  # noqa: BLE001
        bao("error", f"Chưa đồng bộ được: {e}")
        return
    try:
        lease = maintenance_gate.nhan_viec_cua(eng, "tác vụ nền «channel»")
    except DangChayRoi as e:
        bao("error", f"Chưa chạy được: {e}")
        return
    huy = threading.Event()
    tv = tac_vu_nen.TacVuNen("channel", huy=huy.set, so_dong_bo=so, phien_youtube=cs.phien, thu_muc=dich)
    job_dong_bo.update({"running": True, "pct": 0.0, "msg": "Đang khởi động...",
                        "results": [], "error": "", "kind": "channel", "da_day_sheet": False})
    try:
        tv.bat_dau(eng, cs.sync, (kenh_url.strip(), gioi_han), {"cancel_check": huy.is_set,
                                                               "thu_lai_han_che": thu_lai_han_che},
                   job=job_dong_bo, lease=lease)
    except tac_vu_nen.DangCoTacVuKhac as e:   # phiên khác vừa khởi động trước: chưa chạy gì
        if lease is not None:
            lease.tra()
        job_dong_bo.update({"running": False, "msg": "", "kind": ""})
        bao("warning", str(e))
        return
    st.session_state.pop("thong_bao_dong_bo", None)
    st.session_state.so_dong_bo = so
    st.session_state.tac_vu_dong_bo = tv
    st.rerun()


def chay_nen(kind: str, ham, *args, phien_youtube=None, **kwargs):
    """Chạy một tác vụ dài trong luồng nền để giao diện không bị đơ và nút Dừng vẫn bấm được.
    Vào cổng bảo trì TRƯỚC (đang cập nhật → báo, không chạy); lease trả khi tác vụ xong. Tác vụ ghi sổ mức tiến
    trình (``tac_vu_nen``) để phiên mới (tải lại trang) nhận lại được; ``phien_youtube``: phiên YouTube của lượt
    (``ChannelSync.phien``) — xong thì thanh bên báo theo nó. Đồng bộ kênh KHÔNG đi đường này (``chay_dong_bo``)."""
    if dang_co_tac_vu():
        st.warning("Đang có tác vụ chạy; không tạo job trùng.")
        return
    if dang_dong_bo():
        st.warning("Đang đồng bộ kênh — việc này cũng hỏi YouTube và ghi metadata kho; chờ lượt đồng bộ xong rồi chạy.")
        return
    try:
        lease = maintenance_gate.nhan_viec_cua(eng, f"tác vụ nền «{kind}»")
    except DangChayRoi as e:
        st.error(f"Chưa chạy được: {e}")
        return
    tv = tac_vu_nen.TacVuNen(kind, huy=eng.cancel, phien_youtube=phien_youtube)
    job.update({"running": True, "pct": 0.0, "msg": "Đang khởi động...",
                "results": [], "error": "", "kind": kind, "da_day_sheet": False})
    eng.cancel_event.clear()
    try:
        tv.bat_dau(eng, ham, args, kwargs, job=job, lease=lease)
    except tac_vu_nen.DangCoTacVuKhac as e:   # phiên khác vừa khởi động trước: chưa chạy gì
        if lease is not None:
            lease.tra()
        job.update({"running": False, "msg": ""})
        st.warning(str(e))
        return
    st.session_state.tac_vu_nen = tv
    st.rerun()


def _huy_tac_vu_nen() -> None:
    """Nút Dừng của tác vụ nền: tác vụ nhận lại từ phiên khác → cờ huỷ của Engine đã khởi động nó."""
    tv = st.session_state.get("tac_vu_nen")
    if tv is not None:
        tv.huy()
    else:
        eng.cancel()


def chay_van_tay(thumuc: str, mode: str) -> None:
    """Khởi động đúng một controller; worker không gọi API Streamlit."""
    if dang_co_tac_vu():
        st.warning("Đang có tác vụ chạy; không tạo thêm job trùng.")
        return
    if tac_vu_nen.thu_muc_chong_nhau(_thu_muc_dang_dong_bo(), thumuc):
        st.warning("Thư mục này đang đồng bộ kênh (đang tải file vào) — chờ lượt đồng bộ xong rồi tạo/bổ sung vân tay, "
                   "để không nạp file đang tải dở. Tạo vân tay cho kho KHÁC thì làm ngay được.")
        return
    eng.cancel_event.clear()
    try:
        job_id = fingerprint_controller.start(thumuc, mode)
    except RuntimeError as e:                  # phiên khác vừa bắt đầu dựng kho: không tạo job trùng
        st.warning(str(e))
        return
    job.update({
        "running": True,
        "pct": 0.0,
        "msg": "Đang chuẩn bị danh sách clip...",
        "results": [],
        "error": "",
        "kind": "db",
        "da_day_sheet": False,
        "fingerprint_job_id": job_id,
    })
    st.rerun()


def _thoi_luong(giay: float | None) -> str:
    return "Đang tính..." if giay is None else dong_ho(giay)


TEN_PHASE = {
    "discovering": "Đang chuẩn bị danh sách clip",
    "validating": "Đang kiểm tra kho hiện có",
    "probing": "Đang đọc thông tin media",
    "decoding": "Đang giải mã bằng FFmpeg",
    "fingerprinting": "Đang chạy audfprint",
    "saving": "Đang ghi database vân tay",
    "completed": "Hoàn tất",
    "cancelled": "Đã dừng",
    "failed": "Thất bại",
}

TEN_PHASE_QUET = {
    "queued": "Đang chờ",
    "fetching_metadata": "Đang lấy thông tin video",
    "downloading": "Đang tải audio",
    "chunking": "Đang cắt khúc",
    "matching": "Đang so khớp vân tay",
    "merging": "Đang tổng hợp kết quả",
    "completed": "Hoàn tất",
    "failed": "Lỗi",
    "cancelled": "Đã dừng",
}
# Tên hiển thị của trạng thái quét/Sheets nằm trong scan_ui.py, cạnh builder
# DataFrame, để bảng và schema không bao giờ lệch nhau.


def bao_cao_khong_co_ket_qua(results: list[ScanResult]) -> None:
    """Giải thích một lượt quét 0 kết quả MẤT Ở TẦNG NÀO, thay vì chỉ nói không thấy.

    Năm tình huống dưới đây trước kia hiện ra y hệt nhau nên người dùng không phân
    biệt được âm tính đúng với lỗi phần mềm: audfprint không ra dòng nào; ra dòng
    nhưng parser đọc không được; bằng chứng quá yếu; không đạt tiêu chí chấp nhận;
    chọn lọc bỏ hết. Giờ mỗi tình huống có câu trả lời riêng.
    """
    ok = [x for x in results if x.status == "ok"]
    if not ok:
        return

    for x in ok:
        cd = getattr(x, "chan_doan", None)
        tieu_de = thoat_markdown(x.source_name or x.source_ref)   # tiêu đề YouTube = chữ ngoài (audit D-8)
        # Quét MỘT PHẦN: câu kết luận tự nói phạm vi, không khẳng định cho cả video (audit F-3).
        pham_vi = thoat_markdown(mo_ta_pham_vi(x)) if x.quet_mot_phan else ""
        if cd is None:
            them = (f" (CHỈ QUÉT MỘT PHẦN: {pham_vi} — đây KHÔNG phải kết luận cho toàn "
                    "video)" if pham_vi else "")
            st.warning(f"**{tieu_de}** — không tìm thấy clip gốc nào{them}.")
            continue

        st.warning(f"**{tieu_de}** — không có đoạn nào đạt tiêu chí.\n\n"
                   f"{cd.mat_o_dau(pham_vi)}")
        with st.expander("🔎 Chi tiết chẩn đoán"):
            st.markdown(
                f"- Số khúc đã cắt: **{cd.so_khuc}**\n"
                f"- Dòng khớp thô từ audfprint: **{cd.dong_co_matched}**\n"
                f"- Đọc ra được: **{cd.parse_duoc}**\n"
                f"- Qua lọc số hash tối thiểu: **{cd.qua_min_hash}**\n"
                f"- Qua lọc độ dài tối thiểu: **{cd.qua_min_match_s}**\n"
                f"- Ứng viên sau khi gộp: **{cd.gop_lai}**\n"
                f"- Đạt tiêu chí chấp nhận: **{cd.duoc_chap_nhan}**\n"
                f"- Bằng chứng thô mạnh nhất: **{cd.hash_tho_lon_nhat} hash**, "
                f"đoạn dài nhất **{cd.khop_tho_dai_nhat:.1f}s**"
            )
            u = cd.manh_nhat_bi_loai
            if u is not None:
                st.markdown("**Ứng viên mạnh nhất đã bị loại**")
                st.code(u.mo_ta(), language=None)
                # Giúp người dùng tự phân biệt reup thật với nhạc hiệu dùng chung.
                if u.ty_le < 5 and u.matched_s < 30:
                    st.caption(
                        "Dấu hiệu này (phủ vân tay rất thấp, đoạn khớp chỉ vài giây) "
                        "thường là nhạc hiệu/nhạc nền dùng chung giữa nhiều clip gốc, "
                        "không phải một bản reup. Hạ ngưỡng lúc này sẽ tạo báo cáo sai."
                    )
            # Giữ khả năng soi toàn bộ ứng viên bị loại như bản cũ, chỉ đổi chỗ đặt
            # và bổ sung cột mật độ — cột này mới là thứ phân biệt reup với nhiễu.
            bi_loai = sorted(getattr(x, "matches_loai", []),
                             key=lambda z: -z.hashes)[:30]
            if bi_loai:
                st.markdown(f"**{len(bi_loai)} ứng viên bị loại mạnh nhất**")
                st.dataframe(pd.DataFrame([{
                    "Clip gốc": m.clip,
                    "Xuất hiện từ": m.start_hhmmss,
                    "Số hash": m.hashes,
                    "Phủ (%)": m.ty_le,
                    "Khớp (giây)": round(m.matched_s, 1),
                    "Mật độ (hash/giây)": round(m.hashes / m.matched_s, 1)
                    if m.matched_s else 0.0,
                } for m in bi_loai]), width="stretch", hide_index=True)
            if cd.da_thu_toc_do:
                st.markdown(
                    f"**Đã thử bù tốc độ {len(cd.da_thu_toc_do)} lượt** "
                    "(phòng trường hợp video bị tăng/giảm tốc để né nhận dạng)")
                for mo_ta_toc_do in cd.da_thu_toc_do:
                    st.caption(f"• {mo_ta_toc_do}")
            elif cd.ly_do_khong_bu_toc_do:
                # Không nói ra thì «Bù tốc độ» bật trên giấy vẫn trông như đã chạy.
                st.markdown("**Bù tốc độ: chưa chạy lượt nào**")
                st.caption(cd.ly_do_khong_bu_toc_do)
            for canh in cd.canh_bao:
                st.caption(f"⚠️ {canh}")
            st.caption(cd.tom_tat())


def df_ket_qua(rows: list) -> pd.DataFrame:
    """Dựng DataFrame kết quả quét với các cột số ĐÚNG KIỂU.

    Dòng của nguồn bị lỗi hoặc không có kết quả điền chuỗi rỗng vào đúng các cột số.
    Khi một lượt quét trộn cả hai loại, cột thành dtype `object` lẫn số với chuỗi, và
    PyArrow — thứ Streamlit dùng để vẽ bảng — ném ArrowInvalid, làm sập cả trang kết
    quả chỉ vì một nguồn hỏng.

    `to_numeric(errors="coerce")` biến chuỗi rỗng thành NaN (Streamlit hiện ô trống)
    và cho cột kiểu số thật, nên bảng sắp xếp theo giá trị chứ không theo thứ tự chữ.
    Ép theo `Engine.COT_SO` chứ không liệt kê tay, để thêm cột số mới sau này không
    phải nhớ sửa chỗ này.
    """
    df = pd.DataFrame(rows, columns=eng.HEADER)
    for cot in eng.COT_SO:
        if cot not in df.columns:
            continue
        so = pd.to_numeric(df[cot], errors="coerce")
        # Cột đếm (số hash, số giây) phải hiện là 1234 chứ không phải 1234.0. float64
        # không có giá trị rỗng nên NaN kéo cả cột lên float; kiểu "Int64" của pandas
        # có NA thật nên giữ được nguyên. Cột tỉ lệ vốn là số thực thì để nguyên.
        khong_rong = so.dropna()
        if not khong_rong.empty and (khong_rong % 1 == 0).all():
            so = so.astype("Int64")
        df[cot] = so
    return df


def hien_tinh_chinh(results: list) -> None:
    """P-8: đoạn dùng thật, chỗ cắt và biểu đồ % giống từng giây của các kết quả đã chọn — chỉ khi lượt quét bật tinh
    chỉnh (``ScanResult.tinh_chinh``). «Đoạn vi phạm» của báo cáo/Sheets/lịch sử dùng mốc này cho dòng tinh chỉnh
    được (D-50, ``bao_cao_v2.dung_bao_cao``)."""
    co = [(r, tc) for r in results if r.status == "ok" for tc in (getattr(r, "tinh_chinh", None) or ())]
    if not co:
        return
    with st.expander("🎯 Mốc tinh chỉnh từng giây (thử nghiệm)", expanded=False):
        st.caption("Đo độ giống âm thanh từng giây giữa clip gốc và video quanh mỗi kết quả. Mốc là ƯỚC LƯỢNG PHÍA "
                   "TRONG, tới khoảng 0,1 giây trên dữ liệu thử. «% giống» chỉ có nghĩa khi so với nền của chính kết "
                   "quả đó: nhạc đè to có thể chỉ khoảng 50 % dù khớp chắc. «Đoạn vi phạm» trong bảng kết quả, báo cáo, "
                   "Google Sheets và lịch sử dùng mốc đã tinh chỉnh; dòng «chưa tinh chỉnh» giữ mốc của lượt quét. "
                   "Khớp vân tay không phải xác nhận quyền sở hữu.")
        for r, tc in co:
            ten = (f"**{thoat_markdown(tc.get('clip', ''))}** — {thoat_markdown(r.source_name[:60])} "
                   f"(mốc lượt quét {hhmmss(tc.get('start_s') or 0.0)})")
            if tc.get("trang_thai") != "da_tinh_chinh":
                st.markdown(f"{ten}: chưa tinh chỉnh — {thoat_markdown(tc.get('ly_do', ''))}")
                continue
            dong = [f"Đoạn dùng thật {hhmmss_tp(d['video_tu'])} → {hhmmss_tp(d['video_den'])} "
                    f"(clip {hhmmss_tp(d['clip_tu'])} → {hhmmss_tp(d['clip_den'])}), "
                    f"giống trung bình {float(d.get('tuong_dong_tb') or 0):.0f} %"
                    for d in tc.get("doan") or ()]
            dong += [f"Chỗ cắt / chèn {hhmmss_tp(c['video_tu'])} → {hhmmss_tp(c['video_den'])} "
                     f"(clip nhảy {hhmmss_tp(c['clip_bo_tu'])} → {hhmmss_tp(c['clip_bo_den'])})"
                     for c in tc.get("cho_cat") or ()]
            st.markdown(ten + "\n" + "\n".join(f"- {x}" for x in dong))
            if tc.get("cham_gioi_han"):
                st.caption("⚠️ Một mép chạm giới hạn đo được (cuối phần đã quét, rìa khung phân tích quanh kết quả, "
                           "hoặc đoạn im lặng của chính clip) — mép thật có thể nằm ngoài.")
            ho_so = tc.get("ho_so") or []
            if ho_so:
                st.line_chart(pd.DataFrame({"% giống": [p for _, p in ho_so]},
                                           index=pd.Index([t for t, _ in ho_so], name="Giây trong video")),
                              height=160)
        doan, giay = eng.dong_tinh_chinh(results)
        t1, t2 = st.columns(2)
        for cot, ten_file, header, dong, khoa in ((t1, "tinh_chinh", eng.HEADER_TINH_CHINH, doan, "tai_tinh_chinh"),
                                                 (t2, "tung_giay", eng.HEADER_TUNG_GIAY, giay, "tai_tung_giay")):
            if dong:
                with cot:
                    st.download_button(
                        f"⬇️ Tải {'đoạn tinh chỉnh' if ten_file == 'tinh_chinh' else '% giống từng giây'} (CSV)",
                        pd.DataFrame([[o_bang_tinh_an_toan(o) for o in d] for d in dong], columns=header)
                        .to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"ketqua_{time.strftime('%Y%m%d_%H%M%S')}.{ten_file}.csv",
                        mime="text/csv", width="stretch", key=khoa)


def bang_ket_qua(results: list[ScanResult]) -> None:
    """Vẽ bảng kết quả + các nút xuất báo cáo và đẩy lên Google Sheets."""
    # Báo cáo V2 lỗi/hỏng (audit P1-02): kết quả khớp đã lưu lịch sử nhưng KHÔNG được xuất hay
    # gửi theo bất kỳ luật nào — báo rõ ở đây, rồi bảng/CSV/Sheets/hồ sơ chỉ dùng phần hợp lệ.
    results, loi_bao_cao = bao_cao_v2.tach_loi_bao_cao(results)
    if loi_bao_cao:
        st.error("⛔ " + bao_cao_v2.thong_bao_ket_qua_loi(loi_bao_cao))
    matches = [
        match
        for result in results
        if result.status == "ok"
        for match in result.matches
    ]
    if matches:
        coverage = eng.metadata_coverage(matches)
        if coverage.resolved_complete == 0:
            st.warning(
                "⚠️ Đã phát hiện đoạn vi phạm nhưng không clip gốc nào có đủ "
                "metadata chính thức (ID, tên, link, ngày đăng và thời lượng). "
                "Báo cáo vẫn hiển thị dữ liệu phục hồi an toàn và đánh dấu phần thiếu."
            )
        if coverage.filename_fallbacks:
            st.warning(
                f"⚠️ {coverage.filename_fallbacks}/{coverage.selected_matches} video gốc "
                "được phục hồi từ filename. Tiêu đề có thể đã được rút gọn; "
                "ngày đăng/thời lượng chỉ hiện khi có bằng chứng. Link video gốc của các "
                "clip này lấy từ mã trong tên file, chưa đối chiếu YouTube: với file bạn tự "
                "đặt tên hoặc tự chép vào kho, hãy mở link kiểm tra trước khi dùng hồ sơ."
            )
        if coverage.unresolved or coverage.ambiguous:
            st.error(
                f"Metadata chưa ánh xạ: {coverage.unresolved}; "
                f"mơ hồ (không tự chọn): {coverage.ambiguous}."
            )
        tong_dat_nguong = sum(
            result.so_dat_nguong for result in results if result.status == "ok"
        )
        if tong_dat_nguong != len(matches):
            st.caption(
                f"Có {tong_dat_nguong} đoạn đạt ngưỡng trước bước chọn lọc; "
                f"{len(matches)} đoạn được chọn để xuất. Hai số này có chủ đích khác nhau."
            )
    # Quét tăng dần dừng sớm khi đã đủ bằng chứng. PHẢI nói ra: `note` chỉ được hiển
    # thị khi nguồn bị LỖI, nên nếu không báo ở đây thì người dùng tưởng đã quét trọn
    # video — và sẽ hiểu sai cột «Vùng» lẫn số đoạn tìm được.
    mot_phan = [r for r in results
                if r.status == "ok" and getattr(r, "quet_mot_phan", False)]
    if mot_phan:
        # Lời khuyên theo ĐÚNG lý do (phản biện TCP-06 + vòng 2) — xem goi_y_quet_mot_phan.
        goi_y = goi_y_quet_mot_phan(mot_phan, eng.config)
        st.info(
            "ℹ️ **Chưa quét trọn {} nguồn**.\n\n{}\n\nBằng chứng chỉ nằm trong phần "
            "đã so khớp, nên số đoạn tìm được và cột «Vùng» phản ánh phần đó, không phải "
            "cả video.{}".format(
                len(mot_phan),
                "\n".join(
                    f"- {thoat_markdown(r.source_name[:60])}: {mo_ta_pham_vi(r)}"
                    for r in mot_phan[:8]),
                "".join(f"\n\n{x}" for x in goi_y)))
    # Báo cáo V2: ngày đăng NGUYÊN BẢN của video gốc. Kho chỉ lưu ngày đã quy đổi thì ô ngày
    # để trống — phải nói rõ vì sao, và cách lấy (không tự hỏi YouTube khi chưa được bật).
    thieu_ngay = [x for r in results if getattr(r, "bao_cao", None) is not None
                  for x in bao_cao_v2.ngay_goc_thieu(r.bao_cao)]
    if thieu_ngay:
        st.caption(
            f"📅 {len(thieu_ngay)} video gốc chưa có ngày đăng nguyên bản (ô ngày để trống) — "
            f"{thieu_ngay[0][1]}. Bật «Bổ sung ngày đăng gốc từ YouTube» ở thanh bên "
            "(mục 🔐 Kết nối YouTube) để lượt quét sau tự lấy.")
    rows = eng.to_rows(results)
    st.dataframe(df_ket_qua(rows), width="stretch", hide_index=True)
    df_csv = pd.DataFrame(
        [[o_bang_tinh_an_toan(o) for o in dong] for dong in rows],
        columns=eng.HEADER,
    )
    csv_bytes = df_csv.to_csv(index=False).encode("utf-8-sig")
    # Phạm vi quét của báo cáo V2: tên video đã sạch nên phạm vi đi kèm ở file riêng.
    bcs = [r.bao_cao for r in results if getattr(r, "bao_cao", None) is not None]
    pham_vi_bytes = b""
    if bcs and any(not bc.pham_vi.quet_day_du for bc in bcs):
        pham_vi_bytes = pd.DataFrame(
            [[o_bang_tinh_an_toan(o) for o in bao_cao_v2.dong_pham_vi(bc)] for bc in bcs],
            columns=bao_cao_v2.HEADER_PHAM_VI,
        ).to_csv(index=False).encode("utf-8-sig")

    c1, c2, c3, c4 = st.columns(4)
    with c3:
        st.caption("📤 Gửi Google Sheets: chọn «Đích gửi» trước khi bấm Bắt đầu (tự động, lưu bền), "
                   "hoặc gửi thêm thủ công ở mục bên dưới.")
    with c1:
        st.download_button("⬇️ Tải báo cáo CSV", csv_bytes,
                           file_name=f"ketqua_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                           mime="text/csv", width="stretch")
        if pham_vi_bytes:
            st.download_button(
                "⬇️ Tải phạm vi quét (CSV)", pham_vi_bytes,
                file_name=f"ketqua_{time.strftime('%Y%m%d_%H%M%S')}.pham_vi.csv",
                mime="text/csv", width="stretch", key="tai_pham_vi_quet",
                help="Tên video trong báo cáo không còn kèm «quét một phần» — phạm vi "
                     "thật của từng video nằm ở file này.")
    with c2:
        if st.button("💾 Lưu CSV vào thư mục ketqua\\", width="stretch"):
            st.success(f"Đã lưu: {eng.export_csv(results)}")
    with c4:
        if st.button("📄 Xuất hồ sơ khiếu nại", width="stretch"):
            try:
                fs = eng.export_ho_so(results)
                if not fs:
                    st.info("Không có kết quả nào đủ điều kiện lập hồ sơ.")
                else:
                    st.success(f"Đã tạo {len(fs)} hồ sơ trong ketqua\\")
                    st.code("\n".join(fs))
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
    ui_gui.nut_gui_thu_cong(eng, results, key="gui_thu_cong_lo")


def hien_ket_qua_nguon_chung(kql: nguon_chung.KetQuaLo) -> None:
    """Kết quả lô «Một video gốc chung»: KHÔNG âm thầm chuyển về «mỗi video một nguồn»."""
    n = kql.tong
    if kql.trang_thai == nguon_chung.TIM_THAY:
        st.success(f"✅ Tìm thấy video gốc chung khớp vân tay ở cả **{n}/{n}** video.")
    elif kql.trang_thai == nguon_chung.KHONG_TIM_THAY:
        st.warning("Không xác minh được một video gốc chung cho toàn bộ lô.")
    elif kql.trang_thai == nguon_chung.DA_HUY:
        st.info("⏹️ Đã dừng theo yêu cầu — chưa kết luận cho cả lô.")
    else:
        st.warning("Chưa kết luận được cho cả lô.")
    if kql.gioi_han:
        # «Không tìm thấy» chưa loại trừ tuyệt đối: giới hạn phải nổi rõ, không chìm trong
        # một dòng chú thích.
        st.info(kql.ly_do)
    elif kql.ly_do:
        st.caption(kql.ly_do)

    goc = kql.goc
    if goc is not None:
        tt_goc = kql.thong_tin_goc or {}
        dai = tt_goc.get("duration")
        nhan = ("VIDEO GỐC CHUNG" if kql.la_nguon_chung
                else f"ỨNG VIÊN TỐT NHẤT — có mặt {kql.so_co_mat}/{n} video "
                     "(KHÔNG phải nguồn chung)")
        with st.container(border=True):
            st.markdown(f"**{nhan}**")
            # Tiêu đề/tên file từ metadata kho — chữ ngoài, thoát trước khi vào Markdown (audit E-3).
            st.markdown(f"### {thoat_markdown(tt_goc.get('title') or goc.clip)}")
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"🔗 {tt_goc.get('url') or '—'}")
            if kql.chinh_sach_bao_cao == bao_cao_v2.CHINH_SACH_V2:
                # Ngày NGUYÊN BẢN (upload_date của YouTube); thiếu thì nói vì sao.
                ngay_goc = bao_cao_v2.NgayNguon(
                    gia_tri=str(tt_goc.get("ngay_dang") or "")).hien_thi()
                c2.markdown("📅 Ngày đăng: " + (
                    ngay_goc or f"— ({tt_goc.get('ly_do_thieu_ngay') or 'chưa có'})"))
            else:
                c2.markdown(
                    "📅 Ngày đăng: "
                    f"{format_publication_date(tt_goc.get('upload_date') or '') or '—'}")
            c3.markdown("⏱️ Thời lượng: "
                        + (hhmmss(dai) if isinstance(dai, (int, float)) and dai > 0 else "—"))
            st.caption(f"Clip trong kho: {thoat_markdown(goc.clip)} · Kho: {thoat_markdown(kql.kho_ten or kql.kho_id)}")
    for canh_bao in kql.canh_bao:
        st.warning(f"⚠️ {canh_bao}")
    if kql.goc_khac:
        st.caption("Các video gốc khác cũng có ở mọi video: "
                   + ", ".join(thoat_markdown(k.clip) for k in kql.goc_khac[:10]))

    st.dataframe(df_nguon_chung(kql), width="stretch", hide_index=True)
    so_lieu = kql.so_lieu or {}
    if so_lieu:
        st.caption(
            f"{so_lieu.get('so_luot', 0)} lượt quét ({so_lieu.get('luot_tron', 0)} trọn, "
            f"{so_lieu.get('luot_mot_phan', 0)} dừng sớm vì đã thấy video gốc cần xác minh)"
            f" trong {_thoi_luong(so_lieu.get('thoi_gian_s'))}.")
    st.caption(
        "Khớp vân tay âm thanh là bằng chứng kỹ thuật, không phải xác nhận quyền sở hữu — "
        "hãy xem lại từng mốc trước khi gửi khiếu nại. Chế độ này không ghi vào «Lịch sử "
        "quét» và chưa đẩy Google Sheets. "
        + (f"Kết quả đã tự lưu: {thoat_markdown(kql.csv_tu_luu)}" if kql.csv_tu_luu
           else "Chưa tự lưu được, hãy tải CSV để lưu."))
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇️ Tải báo cáo CSV", csv_nguon_chung(kql),
                           file_name=f"nguonchung_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                           mime="text/csv", width="stretch", key="tai_csv_nguon_chung")
    with c2:
        if st.button("💾 Lưu CSV vào thư mục ketqua\\", width="stretch",
                     key="luu_csv_nguon_chung"):
            st.success(f"Đã lưu: {xuat_csv(kql, eng.out_dir)}")


# =====================================================================
#  Thanh bên: tình trạng hệ thống + tham số
# =====================================================================

with st.sidebar:
    st.title("🔎 TimClip Pro")
    st.caption("Tìm video gốc bên trong video dài — chạy hoàn toàn trên máy bạn.")
    thong_bao_cau_hinh = st.session_state.pop("thong_bao_cau_hinh", "")
    if thong_bao_cau_hinh:
        st.success(thong_bao_cau_hinh)
    for canh_bao in eng.canh_bao_khoi_dong:
        st.warning(canh_bao)

    with st.expander("ℹ️ Phiên bản và cập nhật", expanded=False):
        ui_cap_nhat.ve_phien_ban(eng)

    st.subheader("Tình trạng hệ thống")
    env = eng.check_env()
    dong = {"ffmpeg": "FFmpeg", "ffprobe": "FFprobe", "yt_dlp": "yt-dlp",
            "audfprint": "audfprint", "database": "Kho vân tay clip gốc"}
    for k, ten in dong.items():
        st.write(("✅ " if env[k] else "❌ ") + ten +
                 (f" `{env['yt_dlp_version']}`" if k == "yt_dlp" and env[k] else ""))
    if not all(env[k] for k in ("ffmpeg", "ffprobe", "audfprint")):
        st.error("Thiếu công cụ — hãy chạy lại `cai_dat.bat`.")

    # «🗄️ Kho đang dùng» chỉ vẽ ở trang dùng kho vân tay (_ve_o_kho, gọi trước trang); chỗ giữ sẵn giữ đúng vị trí.
    _cho_kho = st.container()
    khos = eng.list_khos()
    clips = eng.db_clips()

    st.divider()
    st.subheader("⚙️ Tham số")

    def _khung(lo, hi, v):
        """Khung ô số luôn chứa giá trị đang có: ``cau_hinh.json`` sửa tay (hợp lệ theo ``Config.validate``, CLI vẫn
        dùng) mà nằm ngoài khung thì Streamlit ném lỗi và trang dừng ngay ở thanh bên (audit 16/11)."""
        return min(lo, v), max(hi, v)

    with st.expander("Mở để tinh chỉnh", expanded=False):
        c = eng.config
        c.chunk_s = st.number_input("Độ dài mỗi khúc (giây)", *_khung(300, 7200, c.chunk_s), c.chunk_s, 300,
                                    help="Máy yếu RAM thì giảm xuống 1800.")
        c.overlap_s = st.number_input("Khúc gối nhau (giây)", *_khung(60, 3600, c.overlap_s), c.overlap_s, 60,
                                      help="Giá trị đề xuất khi thiếu metadata. Giá trị hiệu lực "
                                           "luôn bị giới hạn bởi trần khúc gối "
                                           f"({c.overlap_max_s} giây).")
        c.min_hash = st.slider("Số hash tối thiểu", *_khung(5, 100, c.min_hash), c.min_hash,
                               help="Bị báo nhầm → tăng lên. Bỏ sót → giảm xuống.")
        c.min_match_s = st.slider("Đoạn khớp tối thiểu (giây)", *_khung(1.0, 60.0, float(c.min_match_s)),
                                  float(c.min_match_s), 1.0)
        c.ncores = st.slider(
            "Số nhân CPU", *_khung(0, 8, c.ncores), c.ncores,
            help="Đặt 0 để tự dò, chừa một nhân cho hệ thống và dùng tối đa 8 nhân.")
        c.shifts_kho = st.number_input(
            "Subframe shifts khi tạo kho", 0, 8, max(0, c.shifts_kho), 1,
            help="Cao hơn giúp bắt vân tay chính xác hơn nhưng tạo kho chậm và tốn "
                 "dung lượng hơn. Đặt 0 để dùng hành vi cũ.")
        c.shifts_quet = st.number_input(
            "Subframe shifts khi quét", 0, 8, max(0, c.shifts_quet), 1,
            help="Cao hơn giúp chịu nén và lệch pha tốt hơn nhưng quét chậm hơn. "
                 "Đặt 0 để dùng hành vi cũ.")

        st.markdown("**Chọn lọc kết quả**")
        c.top_n = st.number_input("Chỉ lấy bao nhiêu kết quả tốt nhất", *_khung(1, 50, c.top_n), c.top_n)
        c.min_hash_floor = st.number_input(
            "Loại hẳn nếu dưới (hash)", *_khung(0, 100000, c.min_hash_floor), c.min_hash_floor, 100,
            help="Kết quả yếu hơn ngưỡng này bị vứt bỏ, không đưa vào báo cáo.")
        c.min_hash_strong = st.number_input(
            "Coi là bằng chứng mạnh từ (hash)", *_khung(0, 200000, c.min_hash_strong), c.min_hash_strong, 500,
            help="Những kết quả đạt ngưỡng này được ưu tiên chọn trước.")
        c.phan_bo_deu = st.checkbox(
            "Phân bổ đều đầu / giữa / cuối video", c.phan_bo_deu,
            help="Chia video vi phạm thành N vùng, mỗi vùng lấy 1 bằng chứng mạnh nhất — "
                 "hồ sơ khiếu nại chứng minh được vi phạm trải dài cả video.")
        c.uu_tien_clip_khac_nhau = st.checkbox(
            "Ưu tiên các clip gốc khác nhau", c.uu_tien_clip_khac_nhau)
        c.tinh_chinh_moc = st.checkbox(
            "🎯 Tinh chỉnh mốc từng giây (thử nghiệm)", c.tinh_chinh_moc,
            help="Sau khi tìm thấy, đo độ giống âm thanh TỪNG GIÂY quanh mỗi kết quả đã chọn: ra đoạn dùng thật tới "
                 "khoảng 0,1 giây, chỗ bị cắt ghép, và biểu đồ % giống. «Đoạn vi phạm» trong báo cáo, Google Sheets "
                 "và lịch sử dùng mốc đã tinh chỉnh (không tinh chỉnh được thì giữ mốc của lượt quét); kết quả tìm "
                 "thấy không đổi; mỗi kết quả tốn thêm vài giây. Chi tiết ở mục «🎯 Mốc tinh chỉnh từng giây» dưới "
                 "bảng kết quả và 2 file CSV phụ.")
        c.keep_downloads = st.checkbox("Giữ lại audio đã tải", c.keep_downloads,
                                       help="Bỏ tick để tiết kiệm ổ cứng (lần sau phải tải lại).")
        c.quet_tang_dan = st.checkbox(
            "Quét tăng dần cho video rất dài", c.quet_tang_dan,
            help="Quét từng đoạn từ đầu; thấy đủ bằng chứng thì dừng, không thấy thì "
                 "quét tiếp cho hết. KHÔNG bỏ sót video nào — chỉ đổi thứ tự làm việc. "
                 "Đo trên video 35 tiếng: 40 phút xuống 5,5 phút, bằng chứng tương đương.")
        if c.quet_tang_dan:
            ct1, ct2 = st.columns(2)
            with ct1:
                c.quet_tang_dan_tu_gio = st.number_input(
                    "Chỉ áp dụng cho video dài hơn (giờ)", *_khung(0.0, 100.0, float(c.quet_tang_dan_tu_gio)),
                    float(c.quet_tang_dan_tu_gio), 1.0,
                    help="Video ngắn hơn mốc này vẫn quét trọn một lượt như cũ.")
            with ct2:
                c.quet_tang_dan_buoc_gio = st.number_input(
                    "Mỗi lượt quét thêm (giờ)", *_khung(0.5, 24.0, float(c.quet_tang_dan_buoc_gio)),
                    float(c.quet_tang_dan_buoc_gio), 0.5,
                    help="Phải DÀI HƠN clip gốc dài nhất trong kho đang dùng.")
            # Đặt LỒNG trong «Quét tăng dần» là có chủ đích: tải một phần mà không
            # quét tăng dần là tổ hợp vô nghĩa (tải 3 tiếng rồi vẫn tự nhận đã quét
            # trọn video 40 tiếng). Trước đây trường này không có ô nào nên bỏ tick
            # ô cha vẫn không tắt được nó — xem Engine._gioi_han_tai.
            c.tai_mot_phan = st.checkbox(
                "Chỉ TẢI phần cần quét trước", c.tai_mot_phan,
                help="Tiết kiệm băng thông: tải đúng đoạn đầu cần quét, không thấy gì "
                     "mới tải nốt phần còn lại. Đo trên video 66 tiếng: 18,4 GB xuống "
                     "841 MB. Bỏ tick để tải trọn ngay từ đầu.")
        st.caption(
            f"Khúc gối hiệu lực tối đa hiện tại: {c.overlap_max_s} giây; "
            "clip dài có thể được ghép lại từ nhiều mảnh ở ranh giới."
        )

    st.divider()
    st.subheader("🔐 Kết nối YouTube")
    with st.expander("Cookie và nhịp tải (mở khi bị báo «nghi là bot»)", expanded=False):
        st.caption(
            "YouTube chặn theo ĐỊA CHỈ MẠNG khi thấy tải quá nhanh hoặc quá nhiều. "
            "Lúc đó mọi cách tải đều hỏng, kể cả video hôm qua vừa tải được. "
            "Hai cách xử lý: giãn nhịp cho đỡ bị để ý, và nạp cookie để YouTube "
            "coi bạn là người dùng đã đăng nhập."
        )
        c.ytdlp_sleep_requests_s = st.number_input(
            "Nghỉ giữa các lượt hỏi YouTube (giây)", 0.0, 60.0,
            float(c.ytdlp_sleep_requests_s), 0.5,
            help="Áp cho khâu LẤY THÔNG TIN video — đúng chỗ YouTube chặn bot. "
                 "0 = tắt (dễ bị chặn). 1 giây là mức an toàn mà gần như không chậm thêm.")
        c1_ns, c2_ns = st.columns(2)
        with c1_ns:
            c.ytdlp_sleep_min_s = st.number_input(
                "Nghỉ trước mỗi lượt TẢI, tối thiểu (giây)", 0.0, 60.0,
                float(c.ytdlp_sleep_min_s), 1.0)
        with c2_ns:
            c.ytdlp_sleep_max_s = st.number_input(
                "…tối đa (giây)", 0.0, 60.0, float(c.ytdlp_sleep_max_s), 1.0,
                help="Nghỉ ngẫu nhiên trong khoảng này. Để 0 cả hai là tắt.")
        c.bo_sung_ngay_goc = st.checkbox(
            "Bổ sung ngày đăng gốc từ YouTube", c.bo_sung_ngay_goc,
            help="Báo cáo ghi ngày đăng NGUYÊN BẢN (upload_date của YouTube, không đổi múi "
                 "giờ). Kho tạo trước bản này chỉ lưu ngày đã quy đổi nên ô ngày video gốc "
                 "để trống. Đã có khoá YouTube Data API thì lượt QUÉT YOUTUBE TỰ bổ sung qua "
                 "API cho các video gốc được chọn còn thiếu ngày (một yêu cầu cho tới 50 video, "
                 "không dùng yt-dlp) — không cần bật ô này. Ô này = hỏi thêm bằng yt-dlp khi "
                 "chưa có khoá, hoặc khi API không trả được: mỗi video gốc tối đa một lần mỗi "
                 "lượt, dừng ngay khi YouTube chặn. Thêm request yt-dlp là thêm nguy cơ bị coi "
                 "là bot, nên mặc định tắt.")
        st.markdown("**Cookie** — chỉ cần một trong hai cách:")
        c.ytdlp_cookies_browser = st.text_input(
            "Lấy thẳng từ trình duyệt", c.ytdlp_cookies_browser,
            placeholder="chrome",
            help="Gõ tên trình duyệt bạn đang đăng nhập YouTube: "
                 + ", ".join(ytdlp_chung.TRINH_DUYET_HO_TRO)
                 + ". Có nhiều profile thì thêm dấu hai chấm, ví dụ «edge:Profile 1». "
                   "Đóng hẳn trình duyệt trước khi quét, nếu không nó khoá file cookie.")
        c.ytdlp_cookiefile = st.text_input(
            "Hoặc đường dẫn file cookies.txt", c.ytdlp_cookiefile,
            placeholder=r"D:\cookies.txt",
            help="File xuất từ tiện ích «Get cookies.txt». Tool chỉ lưu ĐƯỜNG DẪN, "
                 "không bao giờ đọc hay lưu lại nội dung cookie vào cấu hình.")
        duong_dan = (c.ytdlp_cookiefile or "").strip()
        if duong_dan and not os.path.isfile(duong_dan):
            st.warning("Chưa thấy file cookie ở đường dẫn này — kiểm tra lại.")
        elif duong_dan or (c.ytdlp_cookies_browser or "").strip():
            st.success(
                "Đã cấu hình cookie (dùng được trên máy này hay không: xem «Trạng thái YouTube» "
                "bên dưới). Các cách tải không dùng được cookie (android, ios) sẽ tự động lùi "
                "xuống cuối danh sách."
            )
        st.caption(
            "⚠️ Cookie là chìa khoá vào tài khoản của bạn — đừng chia sẻ file đó, "
            "và nên dùng tài khoản phụ. Cookie có thể hết hạn sau vài tuần."
        )
        # Chỉ số đếm và trạng thái — không bao giờ hiện giá trị hay tên cookie, không gọi mạng.
        # Có cookie thì nói rõ nó DÙNG được hay lượt quét sẽ chạy KHÔNG đăng nhập (máy thiếu Node.js/EJS).
        cd_cookie = truy_cap_youtube.chan_doan_cookie(
            c.ytdlp_cookiefile, cookies_browser=c.ytdlp_cookies_browser)
        st.markdown("**Trạng thái YouTube**")
        for muc_tt, cau_tt in dong_trang_thai_youtube(
                cd_cookie, getattr(eng, "phien_youtube_cuoi", None),
                ytdlp_chung.kha_nang_js() if cd_cookie.cau_hinh else None):
            getattr(st, muc_tt)(cau_tt)
        # Khoá YouTube Data API (D-51): đọc file khoá mỗi lần vẽ lại — không gọi mạng.
        for muc_tt, cau_tt in dong_trang_thai_api_youtube(
                youtube_api.trang_thai_khoa(eng.data_dir), getattr(eng, "phien_youtube_cuoi", None)):
            getattr(st, muc_tt)(cau_tt)
        st.caption("Kiểm sâu hơn (một request tới YouTube): `python cli.py youtube-doctor "
                   "--network <link video công khai>`.")

    st.divider()
    st.subheader("📊 Google Sheets")
    with st.expander("Cấu hình", expanded=False):
        st.caption("Đích gửi kết quả quét chọn theo từng lượt (hồ sơ đích) ở tab «📤 Gửi Google "
                   "Sheets». Link dưới đây chỉ dùng cho «Danh sách video» và để nhập hồ sơ từ link cũ.")
        st.session_state.sheet_link = st.text_input(
            "Link Google Sheet", st.session_state.sheet_link,
            placeholder="https://docs.google.com/spreadsheets/d/...")
        sx_tmp = SheetsExporter(sheet=st.session_state.sheet_link)
        em = sx_tmp.email_service_account()
        if em:
            st.caption("Nhớ chia sẻ Sheet (quyền Người chỉnh sửa) cho:")
            st.code(em, language=None)
        if st.button("🔌 Kiểm tra kết nối", width="stretch"):
            ok, tb = sx_tmp.kiem_tra()
            (st.success if ok else st.error)(tb)
        if not sx_tmp.co_key():
            st.caption("Chưa có `google_key.json` — xem hướng dẫn ở đầu file `sheets.py`.")

    st.divider()
    c_luu, c_mac_dinh = st.columns(2)
    with c_luu:
        if st.button(
            "💾 Lưu cấu hình",
            width="stretch",
            disabled=job["running"],
        ):
            try:
                eng.luu_cau_hinh({
                    khoa: st.session_state[khoa]
                    for khoa in GIA_TRI_GIAO_DIEN_MAC_DINH
                })
                st.success("Đã lưu cấu hình.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Không lưu được cấu hình: {e}")
    with c_mac_dinh:
        xac_nhan_mac_dinh = st.checkbox(
            "Chắc chắn khôi phục", key="xac_nhan_khoi_phuc_mac_dinh",
            help="Bỏ toàn bộ cấu hình đã lưu (cookie, kho, link Sheet…). Bản cũ được giữ ở "
                 "data\\cau_hinh.json.truoc_khoi_phuc.")
        if st.button(
            "↩️ Khôi phục mặc định",
            width="stretch",
            disabled=job["running"] or not xac_nhan_mac_dinh,
        ):
            try:
                eng.khoi_phuc_cau_hinh_mac_dinh()
            except Exception as e:  # noqa: BLE001
                st.error(f"Không khôi phục được cấu hình: {e}")
            else:
                st.session_state.clear()
                st.session_state.thong_bao_cau_hinh = (
                    "Đã khôi phục cấu hình mặc định."
                )
                st.rerun()

    st.divider()
    st.caption(f"📂 Dữ liệu: `{eng.data_dir}`")


# =====================================================================
#  Làn đồng bộ kênh: khung riêng ở đầu trang, chạy song song với việc khác
# =====================================================================

_kho_da_ve = False


def _ve_o_kho() -> None:
    """Ô «🗄️ Kho đang dùng» ở thanh bên — trang quét / kho / tìm nghi vấn (_TRANG_CAN_KHO), và lúc có việc đang chạy
    (vòng tự vẽ lại của việc đó chạy TRƯỚC menu — trước đây thanh bên luôn cho thấy kho đang quét). Mỗi lượt vẽ một lần."""
    global _kho_da_ve
    if _kho_da_ve:
        return
    _kho_da_ve = True
    with _cho_kho:
        st.subheader("🗄️ Kho đang dùng")
        if khos:
            tens = [k["ten"] for k in khos]
            hien_tai = eng.kho_dang_dung if eng.kho_dang_dung in tens else tens[0]
            # Job đang chạy đã GHIM kho lúc bắt đầu nên đổi kho không làm hỏng job, nhưng
            # vẫn khoá ô này cho khỏi hiểu nhầm là job đã chuyển sang kho mới (TCP-01).
            chon = st.selectbox("Chọn kho để quét", tens, index=tens.index(hien_tai),
                                label_visibility="collapsed", disabled=job["running"])
            if job["running"]:
                st.caption("Đang có tác vụ chạy — đổi kho được sau khi tác vụ xong.")
            if chon != eng.kho_dang_dung and not job["running"]:
                eng.use_kho(chon)
                st.rerun()
        else:
            st.warning("Chưa có kho nào — tạo ở tab «Kho clip gốc».")

        if clips:
            st.info(f"Kho «{eng.kho_dang_dung}» có **{len(clips)}** clip gốc.")
        elif khos:
            st.warning(f"Kho «{eng.kho_dang_dung}» chưa có vân tay.")


if job["running"]:
    _ve_o_kho()


def _huy_dong_bo() -> None:
    """Nút Dừng của khung đồng bộ: cờ huỷ RIÊNG của lượt đồng bộ (kể cả lượt nhận lại từ phiên khác)."""
    tv = st.session_state.get("tac_vu_dong_bo")
    if tv is not None:
        tv.huy()


def _ve_ket_qua_dong_bo(r: dict) -> None:
    """Kết quả cuối của một lượt đồng bộ kênh."""
    # Tiêu đề + số đếm theo TRẠNG THÁI THẬT của lượt (scan_ui.tom_tat_dong_bo_kenh): chỉ xanh khi đã tải đủ.
    for muc_dbk, cau_dbk in tom_tat_dong_bo_kenh(r) + dong_hieu_suat(r.get("hieu_suat")):
        getattr(st, muc_dbk)(cau_dbk)
    if r["loi"]:
        # Mỗi dòng lỗi mở đầu bằng tiêu đề video (channel.py) — chữ ngoài, thoát trước khi vào Markdown (audit D-8).
        st.warning(f"Video lỗi ({len(r['loi'])}, hiện tối đa 10):\n\n- "
                   + "\n- ".join(thoat_markdown(d) for d in r["loi"][:10]))
    if r.get("nghi_hong"):
        st.warning(
            f"Phát hiện {len(r['nghi_hong'])} file audio nghi hỏng/nén dở trong kho "
            "— đã đưa vào danh sách tải lại. Bản cũ chỉ được chuyển vào thư mục "
            "`_hong` sau khi tải lại thành công, không bị xoá:\n\n- "
            + "\n- ".join(thoat_markdown(d) for d in r["nghi_hong"][:10]))
    if r.get("da_doi_soat"):
        st.info(f"Đã bổ sung metadata tại chỗ cho {r['da_doi_soat']} file có sẵn "
                "trên đĩa (không gọi lại YouTube).")
    # Thư mục audio vừa đồng bộ có thể KHÁC kho vân tay đang chọn (vd. audio kênh mới, kho đang chọn là kho «SML»):
    # không xui người dùng nạp nhầm kho.
    muc_kho, cau_kho = huong_dan_kho_sau_dong_bo(r.get("thu_muc", ""), eng.kho_dang_dung or "",
                                                  eng.kho_thu_muc or "")
    getattr(st, muc_kho)(cau_kho)


@st.fragment(run_every=1.0)
def _khung_dong_bo_dang_chay() -> None:
    """Khung tiến độ đồng bộ tự làm mới mỗi giây mà KHÔNG vẽ lại cả trang — các tab bên dưới vẫn dùng bình thường.
    Sổ tiến độ đã gộp nhịp (byte 4 lần/giây, FFmpeg 2 lần/giây) nên 1 lần/giây là đủ. Lượt xong → vẽ lại cả trang để
    hiện kết quả. Chỉ ĐỌC ảnh chụp của sổ tiến độ (worker ghi) — không đụng thread, cờ huỷ hay khoá."""
    _dong_bo_tac_vu_nen(chi_dong_bo=True)
    if not dang_dong_bo():
        st.rerun(scope="app")
        return
    with st.container(border=True):
        so = st.session_state.get("so_dong_bo")
        try:
            ve_tien_do_dong_bo(st, so.anh())
        except Exception:  # noqa: BLE001 — vẽ lỗi thì lùi về khung chung: nút Dừng không bao giờ mất vì lỗi hiển thị
            st.header("⏳ Đang đồng bộ kênh")
            st.progress(job_dong_bo["pct"], text=f"{job_dong_bo['pct']*100:.0f}%")
            st.info(job_dong_bo["msg"] or "Đang khởi động...")
        if st.button("⏹️ Dừng đồng bộ", type="secondary", key="dung_dong_bo"):
            _huy_dong_bo()
            st.warning("Đã gửi yêu cầu dừng đồng bộ, chờ một chút... Việc quét (nếu có) vẫn chạy tiếp.")
        st.caption("Lượt đồng bộ chạy riêng: các tab bên dưới vẫn dùng bình thường. Quét file trong máy chạy song song "
                   "thoải mái; quét link YouTube cùng lúc thì dùng chung cookie và mạng với lượt đồng bộ — nếu YouTube "
                   "báo chặn, hãy dừng bớt một việc. Đừng đóng cửa sổ đen phía sau.")


def _ve_lan_dong_bo() -> None:
    """Đầu trang: khung tiến độ của lượt đồng bộ đang chạy, hoặc kết quả lượt vừa xong (tới khi người dùng đóng)."""
    if dang_dong_bo():
        _khung_dong_bo_dang_chay()
    elif job_dong_bo.get("kind") == "channel" and (job_dong_bo.get("results") or job_dong_bo.get("error")):
        with st.container(border=True):
            if job_dong_bo["error"]:
                st.error(f"Lỗi: {job_dong_bo['error']}")
            else:
                _ve_ket_qua_dong_bo(job_dong_bo["results"])
            if st.button("Đóng kết quả đồng bộ", key="dong_kq_dong_bo"):
                job_dong_bo.update({"results": [], "error": "", "kind": ""})
                st.rerun()


def _form_dong_bo_song_song() -> None:
    """Trên màn tiến độ quét / dựng vân tay: bắt đầu đồng bộ kênh song song, không phải chờ việc đang chạy xong.
    Form: giá trị gõ dở không bị lượt vẽ lại tự động (0,75 giây) của màn tiến độ làm mất."""
    thong_bao = st.session_state.get("thong_bao_dong_bo")
    with st.expander("📥 Đồng bộ kênh gốc song song — không cần chờ việc này xong", expanded=bool(thong_bao)):
        if thong_bao:
            getattr(st, thong_bao[0])(thong_bao[1])
        with st.form("form_dong_bo_song_song"):
            kenh = st.text_input("Link kênh YouTube của bạn", placeholder="https://www.youtube.com/@TenKenh",
                                 key="ss_kenh_url", persist_state="session")
            kho = st.text_input("Thư mục kho clip gốc (ổ D, E... tùy bạn)", st.session_state.kho_dir,
                                placeholder=r"D:\KhoClipGoc", key="ss_kho_dir", persist_state="session")
            gioi = st.number_input("Chỉ lấy N video mới nhất (0 = toàn bộ kênh)", 0, 5000, 0, 10, key="ss_gioi_han", persist_state="session")
            thu_lai = st.checkbox("Thử lại cả video bị hạn chế (giới hạn tuổi / chỉ hội viên) đã gặp ở lượt trước",
                                  value=False, key="ss_thu_lai_han_che", persist_state="session")
            bam = st.form_submit_button("⬇️ Bắt đầu đồng bộ kênh", type="primary")
        st.caption("Xem trước danh sách video, kiểm tra còn thiếu: tab «📥 Đồng bộ kênh gốc» (khi việc này xong).")
    if bam:
        st.session_state.pop("thong_bao_dong_bo", None)
        if not (kenh.strip() and kho.strip('" ')):
            st.session_state.thong_bao_dong_bo = ("warning", "Nhập link kênh và thư mục kho rồi bấm lại.")
        else:
            st.session_state.kho_dir = kho
            chay_dong_bo(kenh, kho, gioi or None, thu_lai, giu_thong_bao=True)
        st.rerun()                             # vẽ lại ngay: lời từ chối hiện trong ô đồng bộ


with _khu_tren:
    _ve_lan_dong_bo()


    # =====================================================================
    #  Khi có tác vụ đang chạy: chỉ hiện màn hình tiến độ
    # =====================================================================

    if job["running"]:
        if job.get("kind") == "db":
            fp = fingerprint_controller.snapshot()
            now = time.time()
            progress_slot = st.empty()
            status_slot = st.empty()
            metrics_slot = st.empty()
            file_slot = st.empty()
            heartbeat_slot = st.empty()
            log_slot = st.empty()

            st.header("🔊 Đang tạo vân tay clip gốc")
            progress_slot.progress(
                fp.percent,
                text=(
                    f"Đã hoàn tất {fp.processed_count} / {fp.total} — "
                    f"{fp.percent * 100:.1f}%"
                    if fp.total
                    else "Đang chuẩn bị danh sách clip..."
                ),
            )
            status_slot.info(
                f"**Công đoạn:** {TEN_PHASE.get(fp.phase, fp.phase)}  \n"
                f"{thoat_markdown(fp.message)}"   # tên clip = chữ ngoài (audit 09/11)
            )
            if fp.file_name:
                file_slot.markdown(
                    f"**Clip hiện tại ({fp.current}/{fp.total}):** {thoat_markdown(fp.file_name)}"
                )
            else:
                file_slot.markdown("**Clip hiện tại:** đang xác định...")

            with metrics_slot.container():
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Đã tính xong", fp.success_count)
                m2.metric("Đã tồn tại", fp.skipped_count)
                m3.metric("Lỗi", fp.failed_count)
                m4.metric("Đã xử lý", f"{fp.processed_count}/{fp.total}")
                t1, t2, t3, t4 = st.columns(4)
                t1.metric("Đã chạy", _thoi_luong(fp.elapsed_seconds))
                t2.metric(
                    "Tốc độ trung bình",
                    f"{fp.rate_per_minute:.1f} clip/phút"
                    if fp.rate_per_minute is not None
                    else "Đang tính...",
                )
                t3.metric("ETA", _thoi_luong(fp.eta_seconds))
                t4.metric(
                    "Worker",
                    "Đang hoạt động" if fp.worker_alive else "Đã dừng",
                )

            cap_nhat = datetime.fromtimestamp(fp.updated_at).strftime("%H:%M:%S")
            clip_elapsed = (
                now - fp.current_clip_started_at
                if fp.current_clip_started_at is not None
                else None
            )
            pid = fp.active_subprocess_pid or "—"
            heartbeat_slot.caption(
                f"Cập nhật gần nhất: {cap_nhat} · PID audfprint: {pid} · "
                f"Clip hiện tại đã chạy: {_thoi_luong(clip_elapsed)}"
            )
            if clip_elapsed is not None and clip_elapsed >= 120:
                st.warning(
                    "Clip hiện tại đang xử lý lâu hơn bình thường. "
                    "Worker/subprocess vẫn hoạt động; phần trăm không được tăng giả."
                )
            elif now - fp.last_progress_at >= 15 and fp.worker_alive:
                st.warning(
                    "Chưa có event mới trong 15 giây, nhưng worker vẫn sống. "
                    "Đang chờ subprocess hoặc thao tác ghi file."
                )

            recent = fingerprint_controller.recent()[-20:]
            if recent:
                log_slot.code("\n".join(
                    f"{datetime.fromtimestamp(event.updated_at):%H:%M:%S} "
                    f"{event.status:<16} {event.message}"
                    for event in recent
                ))

            if st.button(
                "⏹️ Dừng lại",
                type="secondary",
                disabled=fp.status == "cancel_requested",
            ):
                fingerprint_controller.cancel()
                st.warning("Đang yêu cầu dừng; chưa đánh dấu đã dừng cho tới khi worker xác nhận.")
            st.caption(
                "Trang tự làm mới từ ảnh chụp tiến độ; worker không gọi Streamlit trực tiếp. "
                "Log kỹ thuật: `ketqua/fingerprint.log`."
            )
        elif job.get("kind") == "scan":
            anh = scan_controller.snapshot()
            if not scan_controller.running:
                job["running"] = False
                job["results"] = scan_controller.results()
                job["error"] = scan_controller.error
                # Bấm Dừng: engine không nhận video kế → các nguồn sau KHÔNG có kết quả nào. Chép cờ dừng + danh
                # sách chưa quét vào job NGAY lúc chép kết quả (ảnh chụp SAU khi lô đã dừng): màn kết quả phải nói
                # lô đã dừng và video nào chưa quét, kể cả ở tab nhận lại lô (audit F-5).
                anh_cuoi = scan_controller.snapshot()
                job["lo_da_dung"] = anh_cuoi.cancelled
                job["chua_quet"] = chua_quet_cua_lo(anh_cuoi, len(job["results"]))

            st.header("🔍 Đang quét video")
            # Chỉ số đo THẬT (ui_tien_do_quet): thanh lô đếm video đã xong; bước hiện tại chỉ có thanh
            # khi có mẫu số đo được; nhịp sống tách khỏi tiến triển; nhật ký ngắn ngay trên trang.
            ui_tien_do_quet.ve_tien_do_lo(
                st, anh, TEN_PHASE_QUET,
                gio=lambda t: datetime.fromtimestamp(t).strftime("%H:%M:%S"))

            st.dataframe(
                build_scan_status_dataframe(anh.videos, ui_gui.trang_thai_viec_lo(eng, anh.lo_id)),
                width="stretch", hide_index=True, height=260,
            )
            if anh.lo_id:
                st.caption(ui_gui.mo_ta_lo(eng, anh.dich_gui, anh.lo_id))
            ui_gui.banner_lo_dang_chay(eng, anh.dich_id, anh.dich_gui, job.get("tab_quet", ""))
            if st.button("⏹️ Dừng lại", type="secondary", disabled=anh.cancelled):
                scan_controller.cancel()
                st.warning("Đã gửi yêu cầu dừng; kết quả đã xong vẫn được giữ.")
        elif job.get("kind") == "nguon_chung":
            anh = common_controller.snapshot()
            if not common_controller.running:
                job["running"] = False
                job["results"] = [common_controller.result] if common_controller.result else []
                job["error"] = common_controller.error
                CommonOriginalJobController.da_nhan(eng, common_controller)   # phiên mở sau không hiện lại

            st.header("🧩 Đang tìm video gốc chung cho cả lô")
            # Đếm theo LƯỢT: lượt bổ sung chạy trên video đã có lượt — đếm video thì N/N = 100% (audit F-6).
            gia_tri, chu = tien_do_nguon_chung(anh)
            st.progress(gia_tri, text=chu)
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Giai đoạn", TEN_PHA_NGUON_CHUNG.get(anh.pha, anh.pha))
            b2.metric("Đã xác minh", f"{anh.so_xac_minh}/{anh.tong}" if anh.ung_vien else "—")
            b3.metric("Đang quét", f"Video {anh.video_dang_quet}" if anh.video_dang_quet else "—")
            b4.metric("Đã chạy", _thoi_luong(anh.elapsed_seconds))
            if anh.ung_vien:
                st.info(f"**Video gốc đang xét:** {thoat_markdown(anh.ung_vien_tieu_de)}  \n`{anh.ung_vien}`")
            if anh.message:
                st.caption(thoat_markdown(anh.message))   # có tiêu đề YouTube (audit 09/11)
            st.dataframe(build_nguon_chung_status_dataframe(anh.videos), width="stretch",
                         hide_index=True, height=260)
            st.caption("Trong lúc lô chạy, Giám sát tự động và tạo kho phải chờ — kho vân tay "
                       "phải giữ nguyên suốt lô thì kết luận «không có» mới có nghĩa.")
            if st.button("⏹️ Dừng lại", type="secondary", disabled=anh.cancelled,
                         key="dung_nguon_chung"):
                common_controller.cancel()
                st.warning("Đã gửi yêu cầu dừng; bằng chứng đã có vẫn được giữ.")
        else:
            st.header("⏳ Đang xử lý...")
            st.progress(job["pct"], text=f"{job['pct']*100:.0f}%")
            st.info(job["msg"] or "Đang khởi động...")
            if st.button("⏹️ Dừng lại", type="secondary"):
                _huy_tac_vu_nen()
                st.warning("Đã gửi yêu cầu dừng, chờ một chút...")
            st.caption("Cửa sổ này tự cập nhật. Bạn có thể để yên và làm việc khác, "
                       "nhưng đừng đóng cửa sổ đen phía sau.")
        if job.get("kind") in ("scan", "db", "nguon_chung") and not dang_dong_bo():
            _form_dong_bo_song_song()
        time.sleep(0.75)
        st.rerun()

    # Tác vụ vừa xong → hiện kết quả
    if not job["running"] and (job["results"] or job["error"]):
        # Lô quét lỗi CẤP LÔ giữa chừng (vd. ``LoiLuuBen``: đĩa đầy, ``lichsu.db`` bị khoá) vẫn giữ kết quả các video
        # đã xong trước đó (đã lưu lịch sử/xếp hàng gửi): báo lỗi NHƯNG vẫn hiện chúng — MANAGED_RUNTIME_DESIGN §3
        # «kết quả vẫn trả về UI» (audit F-9). Tác vụ khác lỗi thì chỉ báo lỗi như cũ.
        loi_lo_quet_co_ket_qua = bool(job["error"]) and job["kind"] == "scan" and bool(job["results"])
        if job["error"] and not loi_lo_quet_co_ket_qua:
            st.error(f"Lỗi: {job['error']}")
        elif job["kind"] == "db":
            r = job["results"]
            # Tiêu đề theo KẾT QUẢ THẬT (scan_ui.tom_tat_tao_van_tay, audit F-4): bổ sung mà mọi clip mới đều lỗi → kho
            # không ghi → đỏ, không «✅ Hoàn tất».
            for muc_vt, cau_vt in tom_tat_tao_van_tay(r):
                getattr(st, muc_vt)(cau_vt)
            m1, m2, m3 = st.columns(3)
            m1.metric("Tạo mới", r.get("thanh_cong", r.get("da_xu_ly", 0)))
            m2.metric("Đã tồn tại", r.get("bo_qua", 0))
            m3.metric("Lỗi", r.get("that_bai", len(r.get("loi_file", []))))
            if r.get("canh_bao"):
                st.warning("\n\n".join(r["canh_bao"]))
            if r.get("loi_file"):
                with st.expander(f"⚠️ {len(r['loi_file'])} file có vấn đề — bấm xem"):
                    st.code("\n".join(r["loi_file"][:50]))
        elif job["kind"] == "metadata_network":
            r = job["results"]
            # YouTube chặn giữa chừng / có clip lỗi: chưa vá xong — không báo xanh (audit 16/11; CLI vốn đã đọc ``chan_youtube``).
            if r.get("chan_youtube"):
                st.error(f"🚫 YouTube chặn giữa chừng nên đã dừng: {r['chan_youtube']}")
            (st.warning if r["loi"] or r.get("chan_youtube") else st.success)(
                f"Đã vá metadata snapshot cho {r['da_va']}/{r['tong']} clip; "
                f"không đổi {r['bo_qua']}, lỗi {len(r['loi'])}."
            )
            if r["loi"]:
                with st.expander(f"⚠️ {len(r['loi'])} clip chưa vá được"):
                    st.code("\n".join(r["loi"][:50]))
            st.caption(f"Snapshot: `{r['snapshot_path']}`")
        elif job["kind"] == "va_title":
            r = job["results"]
            if r.get("da_huy"):
                st.warning(
                    f"⏹️ Đã dừng theo yêu cầu: đã hỏi YouTube tên thật cho {r['da_va']}/{r['tong']} "
                    f"video, lỗi {len(r['loi'])}. Phần đã lấy được đã lưu; bấm lại nút để chạy tiếp "
                    "những video còn lại."
                )
            else:
                st.success(
                    f"✅ Đã hỏi YouTube tên thật cho {r['da_va']}/{r['tong']} video; "
                    f"bỏ qua {r['bo_qua']} video đã có tên đúng, lỗi {len(r['loi'])}."
                )
            if r.get("da_them_tu_dia"):
                st.caption(f"Bổ sung {r['da_them_tu_dia']} mục mới vào `clips_meta.json` "
                           "từ các file có sẵn trên đĩa.")
            if r["loi"]:
                with st.expander(f"⚠️ {len(r['loi'])} video chưa lấy được tên"):
                    st.code("\n".join(r["loi"][:50]))
                st.caption("Những video này giữ tên suy từ tên file và vẫn bị đánh dấu "
                           "«cần kiểm tra» ở tab «Danh sách video trong kho».")
            st.info("Mở tab «📋 Danh sách video trong kho» và bấm xem lại để thấy tên mới.")
        elif job["kind"] == "nguon_chung":
            hien_ket_qua_nguon_chung(job["results"][0])
        elif job["kind"] == "tai_video":
            r = job["results"]
            _r_tai = [k for k in r if not k.get("la_dong_ghep")]  # dòng «🎞️ Video ghép» không phải một video tải
            _dem = {t: sum(1 for k in _r_tai if k["trang_thai"] == t) for t in ("xong", "bo_qua", "loi")}
            _viec = "xử lý" if _r_tai and all(k.get("la_file_may") for k in _r_tai) else "tải"  # tab «Video trong máy»
            (st.success if not (_dem["loi"] or any(k["trang_thai"] == "loi" for k in r)) else st.warning)(
                f"Đã {_viec} {_dem['xong']}/{len(_r_tai)} — bỏ qua {_dem['bo_qua']}, lỗi {_dem['loi']}.")

            def _dong_tai(k: dict) -> str:
                if k["trang_thai"] == "xong":
                    return (f"✅ **{thoat_markdown(k['tieu_de'] or k['url'])}** — {thoat_markdown(k['chat_luong'])}"
                            + (f"  \n{thoat_markdown(k['duong_dan'])}" if k["duong_dan"] else "")
                            + (f"  \n⚠️ {thoat_markdown(k['ghi_chu'])}" if k["ghi_chu"] else ""))
                return (f"{'⏭️' if k['trang_thai'] == 'bo_qua' else '❌'} {thoat_markdown(k['url'])}  \n"
                        f"{thoat_markdown(k['ghi_chu'])}")

            # Cả kênh có thể hàng trăm dòng: lỗi luôn hiện, phần còn lại gom vào ô mở rộng.
            for k in r:
                if k["trang_thai"] == "loi" or len(r) <= 20:
                    st.markdown(_dong_tai(k))
            if len(r) > 20:
                with st.expander(f"Xem {_dem['xong'] + _dem['bo_qua']} video đã tải / bỏ qua"):
                    st.markdown("\n\n".join(_dong_tai(k) for k in r if k["trang_thai"] != "loi"))
            for _i, _tm in enumerate(ui_thao_tac.thu_muc_ket_qua(r)[:3]):
                ui_thao_tac.nut_mo_thu_muc(_tm, f"mo_tm_tai_{_i}", f"📂 Mở thư mục «{os.path.basename(_tm) or _tm}»")
        elif job["kind"] == "sua":
            r = job["results"]
            st.success(f"✅ Đã dựng lại danh sách: {r['tren_dia']} video thực có trên đĩa "
                       f"(trước đó archive ghi {r['archive_cu']}).")
            if r["ma_bi_thieu"]:
                st.info(f"Bổ sung {len(r['ma_bi_thieu'])} video có file nhưng archive quên ghi.")
            if r["ma_bi_ghi_thua"]:
                st.warning(f"Có {len(r['ma_bi_ghi_thua'])} mã trong archive nhưng KHÔNG thấy file "
                           "— chúng sẽ được tải lại ở lần đồng bộ tới.")
        else:
            res = job["results"]
            if loi_lo_quet_co_ket_qua:
                st.error(f"Lỗi: {job['error']}")
                st.info(f"Lô dừng giữa chừng vì lỗi trên. Kết quả của {len(res)} video đã quét xong TRƯỚC lỗi vẫn ở "
                        "bên dưới; các video còn lại chưa có kết quả — quét lại chúng sau khi xử lý lỗi.")
            tong_match = sum(len(x.matches) for x in res)
            tong_loai = sum(len(getattr(x, "matches_loai", [])) for x in res)
            loi = [x for x in res if x.status != "ok"]
            # Batch bị dừng vì YouTube chặn (bot-check, 429…): nói to, trước mọi thứ khác — các
            # video «Chưa quét» KHÔNG phải âm tính và không được tính là đã quét.
            bi_chan = thong_bao_youtube_chan(res)
            if bi_chan:
                st.error("🚫 " + bi_chan)
            # Người dùng bấm Dừng: nói ở cấp LÔ, trước mọi con số — video chưa quét không được lẫn vào
            # «… nguồn đã quét» như một lô đã chạy hết (audit F-5).
            da_dung = thong_bao_lo_da_dung(bool(job.get("lo_da_dung")), job.get("chua_quet") or ())
            if da_dung:
                st.warning(da_dung)

            # Không có kết quả thì PHẢI nói mất ở tầng nào. Trước đây chỗ này chỉ nói
            # "không tìm thấy" và khuyên hạ ngưỡng xuống 60% của kết quả mạnh nhất —
            # lời khuyên đó tạo dương tính giả: với video chỉ chứa nhạc hiệu dùng chung
            # của kênh, hạ ngưỡng sẽ biến một đoạn 9 giây thành "bằng chứng vi phạm".
            if tong_match == 0:
                bao_cao_khong_co_ket_qua(res)
            elif tong_loai:
                st.caption(f"ℹ️ Đã loại {tong_loai} ứng viên chưa đạt tiêu chí chấp nhận "
                           "khỏi báo cáo.")

            if tong_match:
                # Đếm theo đúng bảng/CSV bên dưới; «nguồn đã quét» chỉ gồm nguồn quét ra kết quả — cầu dao,
                # huỷ, tải hỏng đã nằm ở dòng «Có nguồn bị lỗi» (audit F-10, review P3); toàn bộ
                # bằng chứng nằm trong kết quả báo cáo V2 lỗi thì không có câu xanh — banner ⛔ của bảng giải thích.
                so_bang_chung, so_da_quet = dem_cau_tom_tat(res)
                if so_bang_chung:
                    st.success(f"✅ Đã chọn **{so_bang_chung}** bằng chứng tốt nhất "
                               f"từ {so_da_quet} nguồn đã quét.")
                # Bị đổi tốc độ là dấu hiệu né nhận dạng có chủ ý — người dùng cần biết
                # để đưa vào hồ sơ khiếu nại, và để hiểu vì sao mốc thời gian hơi lệch.
                for x in res:
                    cd = getattr(x, "chan_doan", None)
                    if cd is not None and cd.toc_do_tim_duoc:
                        st.info(
                            f"🔎 **{thoat_markdown(x.source_name)}** chỉ khớp sau khi bù tốc độ — "
                            f"{cd.toc_do_tim_duoc}. Video này nhiều khả năng đã bị "
                            "chỉnh tốc độ để né nhận dạng bản quyền.")
            if loi:
                st.error("Có nguồn bị lỗi: " + "; ".join(f"{thoat_markdown(x.source_name)} ({thoat_markdown(x.note)})"
                                                          for x in loi))
            bang_ket_qua(res)
            # Báo cáo V2 lỗi không được xuất theo bất kỳ đường nào — kể cả CSV tinh chỉnh (audit 16/11).
            hien_tinh_chinh(bao_cao_v2.tach_loi_bao_cao(res)[0])
        if st.button("🧹 Xóa kết quả, làm việc khác"):
            job.update({"results": [], "error": "", "kind": ""})
            st.rerun()
        st.divider()


# =====================================================================
#  Các trang chức năng (st.navigation) — mỗi lần vẽ lại chỉ chạy TRANG ĐANG MỞ
# =====================================================================


def _link_trang(ten: str, nhan: str) -> None:
    """Lối tắt sang trang ``ten`` của menu (``_TRANG``). Bộ test vẽ mọi trang trong tab (không có menu) → không vẽ."""
    if os.environ.get("TIMCLIP_UI_VE_MOI_TRANG") != "1":
        st.page_link(next(p for ds in _TRANG.values() for p in ds if p.title == ten), label=nhan)


# ---------------------------------------------------------------- TẢI VIDEO GỐC / THUMBNAIL / CẢ KÊNH
def _o_thu_muc_tai(nhan: str, khoa: str) -> str:
    """Ô thư mục lưu + nút «Chọn…» dùng chung cho ba tab tải (một thư mục nhớ chung). Trả đường dẫn đã bỏ ngoặc."""
    c_tm, c_chon = st.columns([5, 1], vertical_alignment="bottom")
    with c_tm:
        st.session_state.thu_muc_tai_video = st.text_input(
            nhan, st.session_state.thu_muc_tai_video, placeholder=r"D:\VideoGoc")
    with c_chon:
        if st.button("📂 Chọn…", width="stretch", key=f"chon_{khoa}", help="Mở hộp thoại chọn thư mục của Windows"):
            try:
                _chon = tai_video_goc.chon_thu_muc(st.session_state.thu_muc_tai_video.strip('" '))
            except RuntimeError as e:
                st.error(str(e))
            else:
                if _chon:
                    st.session_state.thu_muc_tai_video = _chon
                    st.rerun()
    st.caption("Thư mục được nhớ khi bấm «💾 Lưu cấu hình» ở thanh bên (dùng chung cho các tab tải).")
    return st.session_state.thu_muc_tai_video.strip('" ')


O_AM_LUONG = "🔊 Đưa âm lượng về mức YouTube (-14 LUFS)"
CAN_BO = ("Nối lại bằng cách nén lại cả phần còn lại một lần (đúng từng khung hình, hình–tiếng khớp ở chỗ nối): video 1080p dài 1 giờ mất khoảng 8–12 phút. File chỉ có tiếng thì nhanh hơn nhiều.")
GIAI_THICH_AM_LUONG = ("Nhiều video gốc được thu rất nhỏ; xem trên YouTube nghe to là nhờ «Âm lượng ổn định». Tick ô này thì "
                       "tải xong tool đo độ to và chỉnh về mức YouTube (có giới hạn đỉnh, không rè); hình giữ nguyên. "
                       "Video vốn đã đủ to thì giữ nguyên. Bỏ tick = giữ đúng âm lượng gốc.")


def _bat_dau_tai(ham, *args, **kwargs) -> None:
    _phien_tai = truy_cap_youtube.PhienYouTube()
    chay_nen("tai_video", ham, *args, eng.cau_hinh_mang(), player_clients=list(eng.config.ytdlp_player_clients),
             phien=_phien_tai, cancel_check=eng.cancel_event.is_set, phien_youtube=_phien_tai, **kwargs)


def _chua_tai_duoc() -> bool:
    if dang_dong_bo():
        st.caption("Đang đồng bộ kênh — chờ lượt đó xong rồi tải, để hai việc không cùng hỏi YouTube một lúc.")
    return bool(job["running"]) or dang_dong_bo()


def _trang_tai_video() -> None:
    st.subheader("Tải video / audio gốc theo link")
    st.caption("Tải file video (hình + tiếng) hoặc chỉ audio — không đưa vào kho vân tay. Bản 4K thường ra file .mkv (mở "
               "bằng VLC hoặc ứng dụng Phim & TV của Windows); bản thấp hơn ra .mp4; chỉ audio ra .m4a. Tên file = tiêu đề "
               "không dấu + mã video, không dấu cách (vd. Ten_video_RMpCKfipD-Y.mp4).")
    _loai_tai = st.radio("Tải về", tai_video_goc.LOAI_TAI, horizontal=True, key="loai_tai", persist_state="session")
    _chi_audio = _loai_tai == tai_video_goc.LOAI_TAI[1]
    links_tai = st.text_area("Link video (mỗi dòng một link)", height=120,
                             placeholder="https://www.youtube.com/watch?v=...\nhttps://youtu.be/...", key="o_links_tai", persist_state="session")
    _thu_muc_tai = _o_thu_muc_tai("Thư mục lưu video", "tai")
    _cl_tai = "Chỉ tiếng" if _chi_audio else st.selectbox(
        "Chất lượng tối đa", [m for m in tai_video_goc.CHAT_LUONG if tai_video_goc.CHAT_LUONG[m] != 0], key="cl_tai",
        help="Video gốc thấp hơn mức chọn thì lấy bản cao nhất có.", persist_state="session")
    _ds_link = tai_video_goc.tach_link(links_tai)
    c_tu, c_den = st.columns(2)
    with c_tu:
        _tu_tai = st.text_input("Từ (chỉ lấy một đoạn — để trống = cả video)", key="tu_tai", placeholder="vd. 1:23", persist_state="session")
    with c_den:
        _den_tai = st.text_input("Đến (phút:giây hoặc giờ:phút:giây)", key="den_tai", placeholder="vd. 2:45.5", persist_state="session")
    _bo_tai = st.text_area(
        "✂️ Bỏ các đoạn rồi nối phần còn lại (để trống = không bỏ)", key="bo_tai", height=80,
        placeholder="vd. 0:04:12 - 0:05:24, 0:07:11 - 0:09:01\n(mỗi đoạn «Từ - Đến», cách nhau dấu phẩy hoặc xuống dòng)", persist_state="session")
    _anh_tai = st.text_input("📸 Chụp ảnh ở các mốc (để trống = không chụp)", key="anh_tai", placeholder="vd. 7:23 hoặc 7:23, 12:05, 1:01:10 (mỗi mốc một ảnh PNG)", persist_state="session")
    _tu_s = _den_s = None
    _ds_bo_tai: list = []
    _ds_moc_tai: list = []
    _loi_doan = ""
    try:
        _tu_s, _den_s = cat_video_goc.doc_moc(_tu_tai), cat_video_goc.doc_moc(_den_tai)
        _ds_bo_tai = cat_video_goc.doc_ds_doan(_bo_tai)
        _ds_moc_tai = cat_video_goc.doc_ds_moc(_anh_tai)
        if (_tu_s is None) != (_den_s is None):
            _loi_doan = "Điền cả «Từ» lẫn «Đến» — hoặc để trống cả hai để tải cả video."
        elif _tu_s is not None and _den_s <= _tu_s:
            _loi_doan = "Mốc «Đến» phải sau mốc «Từ»."
        elif sum((_tu_s is not None, bool(_ds_bo_tai), bool(_ds_moc_tai))) > 1:
            _loi_doan = "Chỉ chọn một việc: cắt một đoạn («Từ»/«Đến»), bỏ các đoạn hoặc chụp ảnh — xoá bớt ô."
        elif _ds_moc_tai and _chi_audio:
            _loi_doan = "Chụp ảnh cần video có hình — chọn «🎬 Video», không chọn «Chỉ audio»."
    except ValueError as e:
        _loi_doan = str(e)
    if _loi_doan:
        st.error(_loi_doan)
    elif _ds_moc_tai:
        st.caption(f"Chụp {len(_ds_moc_tai)} ảnh PNG ở {', '.join(map(cat_video_goc.moc_hien, _ds_moc_tai))} — khung hình "
                   "đúng mốc, độ phân giải gốc của video (theo «Chất lượng tối đa»). Tải trọn từng video (chỉ phần hình, "
                   "không tiếng) rồi chụp; xong thì xoá video. Ô âm lượng không áp dụng khi chụp ảnh.")
    elif _ds_bo_tai:
        st.caption(f"{cat_video_goc.mo_ta_ds_doan(_ds_bo_tai)}. Tải trọn từng video rồi bỏ các đoạn đó, nối phần còn lại "
                   f"thành video mới; xong thì xoá video trọn. {CAN_BO}")
    elif _tu_s is not None:
        st.caption(f"Tải trọn từng video rồi cắt CHÍNH XÁC đoạn {cat_video_goc.moc_hien(_tu_s)}–{cat_video_goc.moc_hien(_den_s)} "
                   f"({_den_s - _tu_s:g} giây; đúng từng khung hình vì nén lại đoạn cắt). Cắt xong thì xoá video trọn.")
    st.caption("Link kênh/danh sách phát bị bỏ qua — tải cả kênh dùng tab «📺 Tải cả kênh».")
    _am_tai = st.checkbox(O_AM_LUONG, value=True, key="am_tai", help=GIAI_THICH_AM_LUONG, persist_state="session")
    with st.expander("🟣 Twitch: mở khoá bản 1440p (tuỳ chọn)"):
        st.caption("Twitch chỉ cho bản 1440p khi xem từ nước được mở VÀ có đăng nhập. Điền hai file dưới đây thì với link "
                   "Twitch, tool xin danh sách chất lượng qua proxy (Windscribe, nút nguồn ON + Proxy Gateway bật) kèm cookie "
                   "twitch.tv; video vẫn tải thẳng bằng mạng thường. Để trống = bản Twitch cho Việt Nam (thường tối đa 720p). "
                   "Link YouTube không bị ảnh hưởng.")
        c_px, c_chon_px = st.columns([5, 1], vertical_alignment="bottom")
        with c_chon_px:
            _chon_px = ui_thao_tac.nut_chon("chon_twitch_proxy", st.session_state.twitch_proxy_file, "file",
                                            tieu_de="Chọn file proxy Twitch")
        if _chon_px:
            st.session_state.twitch_proxy_file = _chon_px[0]
        st.session_state.twitch_proxy_file = c_px.text_input(
            "File proxy (một dòng http://tên:mật_khẩu@máy:cổng)", st.session_state.twitch_proxy_file,
            placeholder=r"vd. C:\...\secrets\proxy_twitch.txt")
        c_ck, c_chon_ck = st.columns([5, 1], vertical_alignment="bottom")
        with c_chon_ck:
            _chon_ck = ui_thao_tac.nut_chon("chon_twitch_cookie", st.session_state.twitch_cookie_file, "file",
                                            tieu_de="Chọn file cookie Twitch")
        if _chon_ck:
            st.session_state.twitch_cookie_file = _chon_ck[0]
        st.session_state.twitch_cookie_file = c_ck.text_input(
            "File cookie Twitch (cookies.txt có đăng nhập twitch.tv)", st.session_state.twitch_cookie_file,
            placeholder=r"vd. C:\...\secrets\twitch_cookies.txt")
        st.caption("Hai đường dẫn được nhớ khi bấm «💾 Lưu cấu hình» ở thanh bên. Nội dung file không được lưu vào cấu hình.")
    _mo_khoa_tw = ytdlp_chung.MoKhoaTwitch(st.session_state.twitch_proxy_file, st.session_state.twitch_cookie_file)
    _co_doan = (_tu_s is not None or bool(_ds_bo_tai) or bool(_ds_moc_tai)) and not _loi_doan
    _nhan_tai = "📸 Tải và chụp" if _ds_moc_tai else "✂️ Tải và cắt" if _co_doan else "🎵 Tải audio" if _chi_audio else "⬇️ Tải"
    if st.button(f"{_nhan_tai} {len(_ds_link)} video" if _ds_link else f"{_nhan_tai} video", type="primary",
                 disabled=not (_ds_link and _thu_muc_tai) or bool(_loi_doan) or _chua_tai_duoc(),
                 key="bat_dau_tai_video"):
        if _co_doan:
            _bat_dau_tai(cat_video_goc.tai_doan, _ds_link, _thu_muc_tai, tu_s=_tu_s, den_s=_den_s,
                         ds_bo=_ds_bo_tai or None, ds_moc=_ds_moc_tai or None, chat_luong=_cl_tai, chuan_hoa_am=_am_tai, mo_khoa_twitch=_mo_khoa_tw)
        else:
            _bat_dau_tai(tai_video_goc.tai_nhieu, _ds_link, _thu_muc_tai, chat_luong=_cl_tai, chuan_hoa_am=_am_tai,
                         mo_khoa_twitch=_mo_khoa_tw)

def _trang_thumbnail() -> None:
    st.subheader("Tải thumbnail của video YouTube")
    st.caption("Lấy ảnh thumbnail lớn nhất YouTube có (thường 1280×720), lưu dạng .jpg, tên file = mã video "
               "(vd. RMpCKfipD-Y.jpg).")
    links_anh = st.text_area("Link video cần lấy thumbnail (mỗi dòng một link)", height=120,
                             placeholder="https://www.youtube.com/watch?v=...\nhttps://youtu.be/...", key="o_links_anh", persist_state="session")
    _thu_muc_anh = _o_thu_muc_tai("Thư mục lưu thumbnail", "anh")
    _ds_anh = tai_video_goc.tach_link(links_anh)
    if st.button(f"🖼️ Tải {len(_ds_anh)} thumbnail" if _ds_anh else "🖼️ Tải thumbnail", type="primary",
                 disabled=not (_ds_anh and _thu_muc_anh) or _chua_tai_duoc(), key="bat_dau_tai_anh"):
        _bat_dau_tai(tai_video_goc.tai_nhieu, _ds_anh, _thu_muc_anh, thumbnail=True)
    st.divider()
    st.markdown("**Hoặc lấy thumbnail của cả kênh**")
    url_kenh_anh = st.text_input("Link kênh YouTube cần lấy thumbnail", key="kenh_anh",
                                 placeholder="https://www.youtube.com/@TenKenh", persist_state="session")
    _so_kenh_anh = st.number_input("Số thumbnail mới nhất (0 = cả kênh)", min_value=0, value=0, step=10,
                                   key="so_kenh_anh", persist_state="session")
    st.caption("Lấy thumbnail các video ở tab Videos của kênh (không lấy Shorts/Live), lưu vào thư mục ở trên — tải thẳng "
               "ảnh lớn nhất YouTube có (1280×720; video cũ 640×480), không phải hỏi từng video nên nhanh. Ảnh đã có trong "
               "thư mục (theo [mã video]) được bỏ qua: YouTube chặn giữa chừng thì bấm lại sau là lấy tiếp phần còn thiếu.")
    if st.button("🖼️ Tải thumbnail của kênh", type="primary", key="bat_dau_tai_anh_kenh",
                 disabled=not (url_kenh_anh.strip() and _thu_muc_anh) or _chua_tai_duoc()):
        _bat_dau_tai(tai_video_goc.tai_kenh, url_kenh_anh.strip(), _thu_muc_anh, gioi_han=int(_so_kenh_anh) or None,
                     thumbnail=True)

def _trang_tai_ca_kenh() -> None:
    st.subheader("Tải video gốc của cả kênh")
    st.caption("Tải file video ở tab Videos của kênh (không lấy Shorts/Live) — không nén, không đưa vào kho vân tay. "
               "Video đã có trong thư mục (theo mã video ở cuối tên file) được bỏ qua: bấm lại là tải tiếp phần còn thiếu.")
    url_kenh_tai = st.text_input("Link kênh YouTube cần tải", placeholder="https://www.youtube.com/@TenKenh", key="o_url_kenh_tai", persist_state="session")
    _thu_muc_kenh = _o_thu_muc_tai("Thư mục lưu video của kênh", "kenh")
    c_so, c_cl = st.columns(2)
    with c_so:
        _so_kenh = st.number_input("Số video mới nhất (0 = cả kênh)", min_value=0, value=10, step=10, key="o_so_kenh", persist_state="session")
    with c_cl:
        _cl_kenh = st.selectbox("Chất lượng tối đa", list(tai_video_goc.CHAT_LUONG), key="cl_kenh",
                                help="Video gốc thấp hơn mức chọn thì lấy bản cao nhất có. «Chỉ tiếng» ra file nhạc.", persist_state="session")
    st.warning("Video 4K dài có thể nặng hàng chục GB mỗi video — chọn mức chất lượng và số video hợp với ổ đĩa còn trống.")
    if st.button("📺 Tải video của kênh", type="primary", key="bat_dau_tai_kenh",
                 disabled=not (url_kenh_tai.strip() and _thu_muc_kenh) or _chua_tai_duoc()):
        _bat_dau_tai(tai_video_goc.tai_kenh, url_kenh_tai.strip(), _thu_muc_kenh, gioi_han=int(_so_kenh) or None,
                     chat_luong=_cl_kenh)

def _trang_ghep() -> None:
    st.subheader("Ghép nhiều video / audio gốc thành một file dài")
    _loai_ghep = st.radio("Ghép", tai_video_goc.LOAI_TAI, horizontal=True, key="loai_ghep", persist_state="session")
    _audio_ghep = _loai_ghep == tai_video_goc.LOAI_TAI[1]
    if _audio_ghep:
        st.caption("Chỉ tải phần tiếng của từng video (AAC, file M4A) rồi ghép theo đúng thứ tự link; link lặp lại thì "
                   "đoạn đó lặp lại. File trong máy: .m4a, .mp3, .wav, .flac… hoặc cả file video (chỉ lấy tiếng). File "
                   "khác kiểu file 1 được chuyển sang AAC cho khớp trước khi nối. Ra một file .m4a + file «.moc.csv» ghi "
                   "mỗi đoạn bắt đầu ở giây nào (và mốc chương ngay trong file). Ghép xong thì xoá các file lẻ.")
    else:
        st.caption("Tải từng video (H.264 tối đa 1080p + tiếng AAC, file MP4 — cùng một kiểu để nối mà KHÔNG nén lại) rồi "
                   "ghép theo đúng thứ tự link; link lặp lại thì video lặp lại. Kèm file «.moc.csv» ghi video gốc nào bắt "
                   "đầu ở giây nào (và mốc chương ngay trong video) — đem video dài đi quét rồi so với file mốc để đo độ "
                   "chính xác. Ghép xong thì xoá các file lẻ.")
    c_vb_ghep, c_chon_ghep = st.columns([5, 1], vertical_alignment="bottom")
    with c_chon_ghep:
        _chon_ghep = ui_thao_tac.nut_chon("chon_file_ghep", st.session_state.get("o_links_ghep", ""), "nhieu_file",
                                          "📄 Chọn file…", tieu_de="Chọn file trong máy để ghép")
    if _chon_ghep:
        st.session_state["o_links_ghep"] = ui_thao_tac.noi_dong(st.session_state.get("o_links_ghep", ""), _chon_ghep)
    links_ghep = c_vb_ghep.text_area("Link video hoặc đường dẫn file trong máy cần ghép (mỗi dòng một, theo thứ tự ghép)",
                              height=140,
                              placeholder="https://www.youtube.com/watch?v=...\nD:\\Video\\intro.mp4\nhttps://youtu.be/...", key="o_links_ghep", persist_state="session")
    st.caption("Trộn được link YouTube với file có sẵn trong máy. File trong máy không bị sửa hay xoá (chỉnh âm lượng làm "
               "trên bản sao tạm).")
    _thu_muc_ghep = _o_thu_muc_tai("Thư mục lưu video ghép", "ghep")
    _ten_ghep = st.text_input("Tên file video ghép (để trống = «Video_ghep_<ngày giờ>», chỉ audio = «Audio_ghep_<ngày "
                              "giờ>»; dấu cách, dấu tiếng Việt, ký tự đặc biệt được đổi thành chữ không dấu và «_»)", key="o_ten_ghep", persist_state="session")
    _ds_ghep = ghep_video_goc.tach_link(links_ghep)
    _am_ghep = st.checkbox(O_AM_LUONG, value=True, key="am_ghep", help=GIAI_THICH_AM_LUONG, persist_state="session")
    if not _audio_ghep:
        st.caption("Video khác độ phân giải hay số hình/giây video 1 (vd. một video 60 hình/giây giữa các video 30) thì "
                   "tool tự nén lại RIÊNG video đó cho khớp — lâu hơn vài phút cho mỗi video lệch; tiếng giữ nguyên nên "
                   "mốc vẫn đúng. Video đã tải được giữ lại tới khi ghép xong, bấm lại thì không phải tải lại.")
    _bieu_ghep, _vat_ghep = ("🎵", "audio") if _audio_ghep else ("🎞️", "video")
    if st.button(f"{_bieu_ghep} Tải và ghép {len(_ds_ghep)} {_vat_ghep}" if _ds_ghep else f"{_bieu_ghep} Tải và ghép",
                 type="primary", key="bat_dau_ghep_video",
                 disabled=len(_ds_ghep) < 2 or not _thu_muc_ghep or _chua_tai_duoc()):
        _bat_dau_tai(ghep_video_goc.ghep, _ds_ghep, _thu_muc_ghep, ten_file=_ten_ghep, chuan_hoa_am=_am_ghep,
                     chi_audio=_audio_ghep)

def _trang_video_trong_may() -> None:
    st.subheader("Cắt đoạn / bỏ đoạn / chụp ảnh / chỉnh âm lượng video có sẵn trong máy")
    st.caption("File gốc KHÔNG bị sửa, đổi tên hay xoá — kết quả ra file MỚI trong thư mục lưu (trùng tên thì thêm « (2)»). "
               "Muốn GHÉP các file trong máy: dán đường dẫn file vào tab «🎞️ Ghép video gốc» (trộn được với link YouTube).")
    c_vb_may, c_chon_may = st.columns([5, 1], vertical_alignment="bottom")
    with c_chon_may:
        _chon_may = ui_thao_tac.nut_chon("chon_file_may", st.session_state.get("file_may", ""), "nhieu_file",
                                         "📄 Chọn file…", tieu_de="Chọn video trong máy")
    if _chon_may:
        st.session_state["file_may"] = ui_thao_tac.noi_dong(st.session_state.get("file_may", ""), _chon_may)
    may_vb = c_vb_may.text_area("Đường dẫn video trong máy (mỗi dòng một file, hoặc một thư mục)", height=120, key="file_may",
                          placeholder="D:\\Video\\phim.mp4\nD:\\Video\\ThuMuc", persist_state="session")
    _ds_may, _loi_may = video_trong_may.tach_file(may_vb)
    for _l in _loi_may:
        st.error(_l)
    if _ds_may:
        st.caption(f"{len(_ds_may)} file: " + ", ".join(os.path.basename(f) for f in _ds_may[:8])
                   + (f"… (+{len(_ds_may) - 8})" if len(_ds_may) > 8 else ""))
    _thu_muc_may = _o_thu_muc_tai("Thư mục lưu kết quả", "may")
    c_tu_m, c_den_m = st.columns(2)
    with c_tu_m:
        _tu_may = st.text_input("Từ (cắt một đoạn — để trống = không cắt)", key="tu_may", placeholder="vd. 1:23", persist_state="session")
    with c_den_m:
        _den_may = st.text_input("Đến (phút:giây hoặc giờ:phút:giây)", key="den_may", placeholder="vd. 2:45.5", persist_state="session")
    _bo_may = st.text_area(
        "✂️ Bỏ các đoạn rồi nối phần còn lại (để trống = không bỏ)", key="bo_may", height=80,
        placeholder="vd. 0:04:12 - 0:05:24, 0:07:11 - 0:09:01\n(mỗi đoạn «Từ - Đến», cách nhau dấu phẩy hoặc xuống dòng)", persist_state="session")
    _anh_may = st.text_input("📸 Chụp ảnh ở các mốc (để trống = không chụp)", key="anh_may", placeholder="vd. 7:23 hoặc 7:23, 12:05, 1:01:10 (mỗi mốc một ảnh PNG)", persist_state="session")
    _tu_m = _den_m = None
    _ds_bo_may: list = []
    _ds_moc_may: list = []
    _loi_doan_m = ""
    try:
        _tu_m, _den_m = cat_video_goc.doc_moc(_tu_may), cat_video_goc.doc_moc(_den_may)
        _ds_bo_may = cat_video_goc.doc_ds_doan(_bo_may)
        _ds_moc_may = cat_video_goc.doc_ds_moc(_anh_may)
        if (_tu_m is None) != (_den_m is None):
            _loi_doan_m = "Điền cả «Từ» lẫn «Đến» — hoặc để trống cả hai nếu chỉ chỉnh âm lượng."
        elif _tu_m is not None and _den_m <= _tu_m:
            _loi_doan_m = "Mốc «Đến» phải sau mốc «Từ»."
        elif sum((_tu_m is not None, bool(_ds_bo_may), bool(_ds_moc_may))) > 1:
            _loi_doan_m = "Chỉ chọn một việc: cắt một đoạn («Từ»/«Đến»), bỏ các đoạn hoặc chụp ảnh — xoá bớt ô."
    except ValueError as e:
        _loi_doan_m = str(e)
    if _loi_doan_m:
        st.error(_loi_doan_m)
    elif _ds_moc_may:
        st.caption(f"Chụp {len(_ds_moc_may)} ảnh PNG ở {', '.join(map(cat_video_goc.moc_hien, _ds_moc_may))} mỗi file — "
                   "khung hình đúng mốc, độ phân giải gốc; file gốc giữ nguyên. Ô âm lượng không áp dụng khi chụp ảnh.")
    elif _ds_bo_may:
        st.caption(f"{cat_video_goc.mo_ta_ds_doan(_ds_bo_may)}. Phần còn lại nối thành file MỚI. {CAN_BO}")
    _am_may = st.checkbox(O_AM_LUONG, value=True, key="am_may", help=GIAI_THICH_AM_LUONG, persist_state="session")
    _chua_chon_m = _tu_m is None and not _ds_bo_may and not _ds_moc_may and not _am_may
    if _chua_chon_m:
        st.caption("Chọn ít nhất một việc: điền «Từ»/«Đến» để cắt, điền các đoạn cần bỏ, điền mốc chụp ảnh, hoặc tick "
                   "chỉnh âm lượng.")
    _nhan_may = "📸 Chụp ảnh" if _ds_moc_may and not _loi_doan_m else "🛠️ Xử lý"
    if st.button(f"{_nhan_may} {len(_ds_may)} file" if _ds_may else _nhan_may, type="primary", key="bat_dau_xu_ly_may",
                 disabled=not (_ds_may and _thu_muc_may) or bool(_loi_doan_m) or _chua_chon_m or _chua_tai_duoc()):
        _bat_dau_tai(video_trong_may.xu_ly, _ds_may, _thu_muc_may, tu_s=_tu_m, den_s=_den_m, ds_bo=_ds_bo_may or None,
                     ds_moc=_ds_moc_may or None, chuan_hoa_am=_am_may)

def _trang_tieu_de_kenh() -> None:
    st.subheader("Tải danh sách tiêu đề của kênh")
    st.caption("Lấy tiêu đề, link và thời lượng mọi video ở tab Videos của kênh (không lấy Shorts/Live) — không tải video "
               "nào; kênh vài nghìn video thường xong trong khoảng một phút.")
    url_td = st.text_input("Link kênh YouTube cần lấy tiêu đề", placeholder="https://www.youtube.com/@TenKenh", key="o_url_tieu_de", persist_state="session")
    if st.button("📝 Lấy danh sách tiêu đề", type="primary", key="lay_tieu_de",
                 disabled=not url_td.strip() or _chua_tai_duoc()):
        st.session_state.tieu_de_kenh = None
        with st.spinner("Đang lấy danh sách (không tải gì cả)..."):
            try:
                st.session_state.tieu_de_kenh = (url_td.strip(), *tai_video_goc.tieu_de_kenh(
                    url_td.strip(), eng.cau_hinh_mang(), data_dir=eng.data_dir))
            except Exception as e:  # noqa: BLE001 — lỗi YouTube đã phân loại sẵn câu tiếng Việt
                st.error(f"Lỗi: {e}")
    if st.session_state.get("tieu_de_kenh"):
        _url_td, _dong_td, _ly_do_td = st.session_state.tieu_de_kenh
        st.success(f"Kênh có {len(_dong_td)} video.")
        if _ly_do_td:
            st.warning(f"Chưa lấy đủ «Ngày đăng» và «Lượt xem» (ô để trống): {_ly_do_td}")
        st.dataframe(pd.DataFrame(_dong_td), width="stretch", hide_index=True, height=320,
                     column_config={"Link": st.column_config.LinkColumn(),
                                    "Lượt xem": st.column_config.NumberColumn(format="localized")})
        if tai_video_goc.COT_API[0] not in _dong_td[0]:
            st.caption("Muốn có thêm cột «Ngày đăng» và «Lượt xem»: đặt khoá YouTube Data API vào "
                       f"`{youtube_api.duong_dan_khoa_api(eng.data_dir)}` rồi lấy lại danh sách.")
        _ten_td = tai_video_goc.ten_file_kenh(_url_td)
        c_csv, c_txt = st.columns(2)
        c_csv.download_button("⬇️ Tải file CSV (mở bằng Excel)", tai_video_goc.csv_tieu_de(_dong_td),
                              file_name=f"{_ten_td}.csv", mime="text/csv", on_click="ignore", width="stretch")
        c_txt.download_button("⬇️ Tải file TXT (chỉ tiêu đề)", tai_video_goc.txt_tieu_de(_dong_td),
                              file_name=f"{_ten_td}.txt", mime="text/plain", on_click="ignore", width="stretch")

# ---------------------------------------------------------------- TAB 0
def _trang_dong_bo() -> None:
    st.subheader("Tự động tải toàn bộ video từ kênh YouTube gốc của bạn")
    st.caption("Chỉ tải phần tiếng, nén còn opus mono 64 kbps — đã đo thực nghiệm là "
               "cho độ chính xác đối chiếu NGANG BẰNG video gốc, nhưng nhẹ hơn ~100 lần.")

    kenh_url = st.text_input("Link kênh YouTube của bạn",
                             placeholder="https://www.youtube.com/@TenKenh", key="o_url_dong_bo", persist_state="session")
    if not st.session_state.kho_dir and eng.kho_thu_muc:   # ô trống → thư mục của kho đang dùng; gõ/chọn khác vẫn giữ
        st.session_state.kho_dir = eng.kho_thu_muc
    c_kho_dir, c_chon_kho_dir = st.columns([5, 1], vertical_alignment="bottom")
    with c_chon_kho_dir:
        _chon_kd = ui_thao_tac.nut_chon("chon_kho_dir", st.session_state.kho_dir, tieu_de="Chọn thư mục kho clip gốc")
    if _chon_kd:
        st.session_state.kho_dir = _chon_kd[0]
    st.session_state.kho_dir = c_kho_dir.text_input(
        "Thư mục kho clip gốc (ổ D, E... tùy bạn)", st.session_state.kho_dir,
        placeholder=r"D:\KhoClipGoc")
    _thu_muc_dong_bo = st.session_state.kho_dir.strip('" ')
    _dong_bo_khac = _canh_bao_dong_bo_khac(_thu_muc_dong_bo,
                                           "đồng bộ, dựng lại danh sách hay lấy lại tên cho thư mục này")
    if _thu_muc_dong_bo and os.path.isdir(_thu_muc_dong_bo):
        _kho_dai = channel.la_kho_video_dai(_thu_muc_dong_bo)
        _bat_dai = st.checkbox(
            f"Kho video dài (nhận video tới {channel.GIAY_CLIP_TOI_DA_KHO_DAI // 3600} giờ)",
            value=_kho_dai, key=f"kho_video_dai_{_thu_muc_dong_bo}", disabled=dang_dong_bo() or _dong_bo_khac,
            help=f"Áp dụng riêng cho thư mục này; thư mục khác vẫn giới hạn {channel.GIO_CLIP_TOI_DA} giờ. Kho video dài "
                 "báo đúng vị trí trong video gốc dài, tối đa 2.047 clip, RAM khoảng 1,5 GB mỗi giờ âm thanh. Kho đã có "
                 "vân tay trước khi bật phải «Tạo lại từ đầu».")
        if _bat_dai != _kho_dai:
            try:
                channel.dat_kho_video_dai(_thu_muc_dong_bo, _bat_dai)
            except OSError as e:
                st.error(f"Không đổi được thiết lập kho video dài: {e}")

    c1, c2 = st.columns([1, 1])
    with c1:
        gioi_han = st.number_input("Chỉ lấy N video mới nhất (0 = toàn bộ kênh)",
                                   0, 5000, 0, 10, key="o_gioi_han_dong_bo", persist_state="session")
    with c2:
        st.write("")
        st.write("")
        xem_truoc = st.button("👀 Xem danh sách video của kênh", width="stretch",
                              disabled=not kenh_url or dang_dong_bo())

    lay_ngay = st.checkbox(
        "Lấy cả ngày đăng chính xác (có khoá YouTube Data API: 1 lượt hỏi mỗi 50 video; không có: chậm, 1 lượt mỗi video)",
        value=False,
        help="YouTube không trả ngày đăng ở chế độ liệt kê nhanh. Bật khi bạn cần "
             "xem ngày đăng ngay tại đây. Việc đồng bộ kho KHÔNG cần bật: ngày đăng "
             "thật được lấy sẵn trong lượt tải của từng video.",
     key="o_lay_ngay_dong_bo", persist_state="session")
    thu_lai_han_che = st.checkbox(
        "Thử lại cả video bị hạn chế (giới hạn tuổi / chỉ hội viên) đã gặp ở lượt trước",
        value=False,
        help="Mặc định tool KHÔNG gửi lại request cho video đã biết bị hạn chế khi cách đăng nhập không đổi, để lượt "
             "sau tiến tới các video còn lại. Tool tự thử lại khi bạn thêm/đổi nguồn cookie. Bật khi vừa xuất lại "
             "cookie tài khoản đã xác minh tuổi (cùng file). Vẫn dừng nếu YouTube từ chối hàng loạt.",
     key="o_thu_lai_han_che", persist_state="session")

    if xem_truoc:
        with st.spinner("Đang lấy danh sách (không tải gì cả)..."):
            try:
                ds = ChannelSync.list_channel(
                    kenh_url.strip(), gioi_han or None, lay_ngay_dang=lay_ngay,
                    cau_hinh_mang=eng.cau_hinh_mang(), data_dir=eng.data_dir,
                )
                st.success(f"Kênh có {len(ds)} video.")
                thieu_ngay = sum(1 for v in ds if not v.upload_date)
                if thieu_ngay:
                    st.caption(
                        f"{thieu_ngay}/{len(ds)} video chưa có ngày đăng trong danh "
                        "sách nhanh. Ngày đăng thật vẫn được ghi đúng khi đồng bộ kho."
                    )
                st.dataframe(pd.DataFrame([{
                    "Ngày đăng": v.upload_date, "Tiêu đề": v.title,
                    "Thời lượng": hhmmss(v.duration), "ID": v.id} for v in ds]),
                    width="stretch", hide_index=True, height=280)
                tong_phut = sum(v.duration for v in ds) / 60
                st.caption(f"Tổng {tong_phut:,.0f} phút → ước tính kho audio khoảng "
                           f"**{tong_phut * 0.48:,.0f} MB** "
                           f"(nếu tải cả video sẽ là ~{tong_phut * 30:,.0f} MB).")
            except Exception as e:  # noqa: BLE001
                st.error(f"Lỗi: {e}")

    if st.button("⬇️ Bắt đầu đồng bộ kênh", type="primary",
                 disabled=not (kenh_url and st.session_state.kho_dir) or dang_dong_bo() or _dong_bo_khac):
        chay_dong_bo(kenh_url, st.session_state.kho_dir, gioi_han or None, thu_lai_han_che)
    if dang_dong_bo():
        st.caption("Đang có một lượt đồng bộ chạy (khung ở đầu trang) — chờ lượt đó xong rồi đồng bộ kênh khác. "
                   "Trong lúc chờ vẫn quét được ở tab «▶️ Quét YouTube» / «📁 Quét file trong máy».")

    if st.session_state.kho_dir and os.path.isdir(st.session_state.kho_dir.strip('" ')):
        tk = ChannelSync(st.session_state.kho_dir.strip('" ')).thong_ke()
        st.info(f"Kho hiện có **{tk['so_file']}** file audio gốc "
                f"({tk['dung_luong_mb']:,.0f} MB).")
        c_mo_kho, c_nap_kho = st.columns(2)
        with c_mo_kho:
            ui_thao_tac.nut_mo_thu_muc(st.session_state.kho_dir.strip('" '), "mo_tm_kho_dong_bo", "📂 Mở thư mục kho")
        with c_nap_kho:
            _link_trang("Kho clip gốc", "🎬 Sang trang Kho clip gốc để nạp clip mới vào vân tay")

    st.caption("Chạy lại bất cứ lúc nào — hệ thống ghi nhớ trong `downloaded.txt` "
               "nên chỉ tải video MỚI, không tải trùng.")

    st.divider()
    st.markdown("#### 🔧 Bị mất mạng giữa chừng? Xử lý ở đây")
    st.caption("Không cần tải lại từ đầu. Hệ thống đối chiếu file THỰC TẾ trên đĩa "
               "(đọc mã ID trong tên file; file chưa xác nhận được kiểm bằng ffprobe) "
               "nên không tải trùng, và file nén dở sẽ được tải lại.")
    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("🔍 Kiểm tra còn thiếu video nào", width="stretch",
                     disabled=not (kenh_url and st.session_state.kho_dir) or dang_dong_bo()):
            with st.spinner("Đang đối chiếu kênh với thư mục kho..."):
                try:
                    cs = ChannelSync(st.session_state.kho_dir.strip('" '),
                                     cau_hinh_mang=eng.cau_hinh_mang())
                    try:
                        r = cs.kiem_tra_thieu(kenh_url.strip(), gioi_han or None)
                    finally:   # thanh bên (lần vẽ sau) báo theo lượt đọc danh sách này (audit D-14)
                        eng.phien_youtube_cuoi = cs.phien
                    trong_so = r.get("trong_so_khong_file") or []
                    st.success(f"Kênh có {r['tong_kenh']} video — đã có **{r['co_roi']}**, "
                               f"còn thiếu **{len(r['thieu'])}**"
                               + (f", trong sổ đã tải nhưng không có file **{len(trong_so)}**" if trong_so else "")
                               + ".")
                    if trong_so:
                        # Đồng bộ KHÔNG tải các video này — không liệt kê chúng là «còn thiếu» (audit D-7).
                        st.warning(CAU_TRONG_SO_KHONG_FILE.format(n=len(trong_so)) + "\n\n- "
                                   + "\n- ".join(f"{thoat_markdown(v.title[:60])} ({v.id})"
                                                       for v in trong_so[:10]))
                    if r.get("qua_dai"):
                        st.info(CAU_QUA_DAI.format(n=len(r["qua_dai"]), gio=r["gio_toi_da"]))
                    if r.get("nghi_hong"):
                        st.warning(
                            f"{len(r['nghi_hong'])} file nghi hỏng/nén dở được tính là còn "
                            "thiếu (đồng bộ sẽ tải lại):\n\n- "
                            + "\n- ".join(thoat_markdown(d) for d in r["nghi_hong"][:10]))
                    if r["thieu"]:
                        st.dataframe(pd.DataFrame([{
                            "Ngày đăng": v.upload_date, "Tiêu đề": v.title,
                            "Thời lượng": hhmmss(v.duration), "ID": v.id}
                            for v in r["thieu"]]), width="stretch", hide_index=True)
                        st.info("Bấm «Bắt đầu đồng bộ kênh» ở trên — chỉ những video này "
                                "được tải, các video đã có sẽ bỏ qua.")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Lỗi: {e}")
    with cc2:
        if st.button("🛠️ Dựng lại danh sách đã tải", width="stretch",
                     disabled=not st.session_state.kho_dir or _dong_bo_khac,
                     help="Dùng khi downloaded.txt bị mất/hỏng, hoặc bạn tự chép file vào kho. "
                          "Chỉ ghi lại file text, KHÔNG đụng vào file audio. File tự chép nên "
                          "đặt tên «YYYYMMDD - Tiêu đề [mã YouTube 11 ký tự].đuôi» hoặc không "
                          "có ngoặc vuông ở cuối — đừng kết thúc tên bằng một chữ 11 ký tự "
                          "trong ngoặc (vd. [Compilation]): tool sẽ đọc nó như mã video."):
            if tac_vu_nen.thu_muc_chong_nhau(_thu_muc_dang_dong_bo(), st.session_state.kho_dir.strip('" ')):
                st.warning("Thư mục này đang đồng bộ kênh (đang ghi danh sách đã tải) — chờ lượt đồng bộ xong rồi "
                           "dựng lại danh sách.")
            else:
                try:
                    cs = ChannelSync(st.session_state.kho_dir.strip('" '))
                    job.update({"kind": "sua", "results": cs.sua_archive(),
                                "error": "", "running": False, "da_day_sheet": True})
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Lỗi: {e}")

    st.divider()
    st.markdown("#### 🏷️ Tên video hiển thị sai? Lấy lại tên thật ở đây")
    st.caption(
        "Tên file trên đĩa bị Windows bắt thay các ký tự `: / \\ | ? * \" < >` bằng "
        "`_` và cắt còn 80 ký tự. Nút này hỏi YouTube tiêu đề ĐÚNG cho từng video "
        "rồi ghi vào `clips_meta.json` — sau đó tab «Danh sách video trong kho» và "
        "báo cáo sẽ hiện tên thật. Đây là tác vụ MẠNG: một lượt hỏi mỗi video."
    )
    if st.button("🌐 Lấy lại tên video thật cho kho này", width="stretch",
                 disabled=not st.session_state.kho_dir or job["running"] or dang_dong_bo() or _dong_bo_khac,
                 help="Chỉ lấy thông tin, KHÔNG tải lại video. Chạy lại được bất cứ "
                      "lúc nào; video nào đã có tên thật thì bỏ qua."):
        cs_title = ChannelSync(st.session_state.kho_dir.strip('" '),
                               player_clients=list(eng.config.ytdlp_player_clients),
                               cau_hinh_mang=eng.cau_hinh_mang(), data_dir=eng.data_dir)
        # Nút Dừng chỉ đặt eng.cancel_event — phải nối vào đây như đồng bộ kênh, không thì
        # bấm Dừng vẫn hỏi YouTube hết kho (audit D-9).
        chay_nen("va_title", cs_title.va_metadata, lay_title=True, phien_youtube=cs_title.phien,
                 cancel_check=lambda: eng.cancel_event.is_set())

# ---------------------------------------------------------------- TAB 1
def _trang_kho() -> None:
    st.subheader("Quản lý các kho clip gốc")
    st.caption("Mỗi kho là một bộ vân tay RIÊNG (ví dụ: Ẩm thực, Du lịch, Review). "
               "Khi quét video vi phạm, chọn đúng kho tương ứng — vừa nhanh vừa ít báo nhầm.")

    with st.expander("➕ Tạo kho mới", expanded=not khos):
        n1, n2 = st.columns([2, 1])
        with n1:
            ten_moi = st.text_input("Tên kho", placeholder="Ví dụ: Ẩm thực", key="o_ten_kho_moi", persist_state="session")
        with n2:
            st.write("")
            st.write("")
            # Tạo kho = chuyển kho đang dùng của Engine này; tác vụ đang chạy (vá metadata) đọc kho từ đó (audit tổng 11/11).
            if st.button("Tạo kho", width="stretch", disabled=not ten_moi or job["running"]):
                try:
                    eng.add_kho(ten_moi)
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))

    if khos:
        st.dataframe(pd.DataFrame([{
            "Đang dùng": "✅" if k["dang_dung"] else "",
            "Tên kho": k["ten"],
            "Thư mục": k["thu_muc"] or "(chưa đặt)",
            "Đã có vân tay": "✅" if k["co_van_tay"] else "—",
        } for k in khos]), width="stretch", hide_index=True)

        xoa = st.selectbox("Xoá kho (chỉ xoá vân tay, KHÔNG xoá file video của bạn)",
                           ["— chọn —"] + [k["ten"] for k in khos])
        # Ô xác nhận gắn ĐÚNG kho đang chọn, bỏ tick sau khi xoá (audit 09/11 — như tab Lịch sử): ô dùng chung còn
        # tick thì chọn kho khác là nút xoá đã bật sẵn.
        khoa_xn_kho = f"xac_nhan_xoa_kho_{xoa}"
        xac_nhan_xoa_kho = st.checkbox(
            "Tôi xác nhận muốn xóa vân tay của kho đã chọn",
            disabled=xoa == "— chọn —", key=khoa_xn_kho)
        if xoa != "— chọn —" and st.button(
            f"🗑️ Xoá kho «{xoa}»",
            disabled=not xac_nhan_xoa_kho or job["running"],
        ):
            try:
                eng.delete_kho(xoa)
            except DangChayRoi as e:
                # Build/Watch/sửa metadata đang giữ khoá kho: không xoá gì cả.
                st.error(f"Chưa xoá được kho «{xoa}» vì đang có tác vụ khác dùng kho. {e}")
            except RuntimeError as e:
                # File vân tay đang bị tiến trình khác giữ: kho còn nguyên (audit C-4).
                st.error(str(e))
            else:
                st.session_state.pop(khoa_xn_kho, None)
                st.rerun()

    st.divider()
    st.markdown(f"#### Nạp clip vào kho đang dùng: **{eng.kho_dang_dung or '(chưa có kho)'}**")

    _khoa_o_kho = f"o_thu_muc_kho_{eng.kho_dang_dung}"
    st.session_state.setdefault(_khoa_o_kho, eng.kho_thu_muc or "")
    c_tm_kho, c_chon_kho = st.columns([5, 1], vertical_alignment="bottom")
    with c_chon_kho:
        _chon_tm = ui_thao_tac.nut_chon("chon_thu_muc_kho", st.session_state.get(_khoa_o_kho) or eng.kho_thu_muc,
                                        tieu_de="Chọn thư mục chứa video gốc của kho")
    if _chon_tm:
        st.session_state[_khoa_o_kho] = _chon_tm[0]
    thumuc = c_tm_kho.text_input("Đường dẫn thư mục chứa video gốc của kho này",
                           key=_khoa_o_kho, persist_state="session",
                           placeholder=r"D:\ClipGocSML",
                           help="Copy đường dẫn từ thanh địa chỉ của File Explorer.")
    _kho_dong_bo_khac = _canh_bao_dong_bo_khac(thumuc.strip('" '), "tạo lại / bổ sung vân tay cho thư mục này, để "
                                                                   "không nạp file đang tải dở")
    # Thư mục khác nguồn của kho đã có vân tay: engine từ chối «Bổ sung»; «Tạo lại» THAY toàn bộ vân tay → phải xác
    # nhận. Kho cũ chưa ghi thư mục nguồn: nguồn suy từ đường dẫn lưu trong vân tay (không giả định).
    nguon_kho = canh_bao_nguon_kho(
        thumuc, eng.kho_dang_dung or "", eng.kho_thu_muc or "", len(clips),
        "" if (eng.kho_thu_muc or "").strip() else eng.thu_muc_nguon_tu_van_tay(clips))
    da_xac_nhan_thay = True
    if nguon_kho:
        getattr(st, nguon_kho[0])(nguon_kho[1])
        if nguon_kho[2]:
            da_xac_nhan_thay = st.checkbox(
                f"Tôi hiểu: «Tạo lại kho từ đầu» sẽ THAY toàn bộ {len(clips)} clip của kho «{eng.kho_dang_dung}» bằng "
                "thư mục này", value=False, key=f"xac_nhan_thay_kho::{eng.kho_dang_dung}::{thumuc}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Tạo lại kho từ đầu", type="primary", width="stretch",
                     disabled=not (thumuc and eng.kho_dang_dung and da_xac_nhan_thay) or _kho_dong_bo_khac):
            chay_van_tay(thumuc.strip('" '), "new")
    with c2:
        if st.button("➕ Bổ sung clip mới vào kho", width="stretch",
                     disabled=not (thumuc and eng.kho_dang_dung) or _kho_dong_bo_khac):
            chay_van_tay(thumuc.strip('" '), "add")

    st.divider()
    st.markdown("#### Tình trạng metadata báo cáo")
    st.caption(
        "Kiểm tra chỉ đọc mối liên hệ giữa clip trong fingerprint DB và metadata. "
        "Khôi phục offline chỉ tạo/cập nhật snapshot riêng của kho; không sửa "
        "`clips_meta.json`, không gọi mạng và không tạo lại fingerprint."
    )
    mc1, mc2 = st.columns(2)
    with mc1:
        if st.button(
            "🔍 Kiểm tra metadata báo cáo",
            width="stretch",
            disabled=not bool(clips),
        ):
            try:
                audit = eng.kiem_tra_metadata_kho()
                st.session_state.metadata_audit = audit.to_dict()
                st.session_state.metadata_audit_kho = eng.kho_dang_dung
            except Exception as e:  # noqa: BLE001
                st.error(f"Không kiểm tra được metadata: {e}")
    with mc2:
        if st.button(
            "🧪 Xem trước khôi phục offline",
            width="stretch",
            disabled=not bool(clips),
        ):
            try:
                preview = eng.khoi_phuc_metadata_offline(dry_run=True)
                st.session_state.metadata_repair_preview = preview.to_dict()
                st.session_state.metadata_repair_preview_kho = eng.kho_dang_dung
                st.session_state.metadata_audit = preview.audit.to_dict()
                st.session_state.metadata_audit_kho = eng.kho_dang_dung
            except Exception as e:  # noqa: BLE001
                st.error(f"Không lập được dry-run: {e}")

    audit_data = st.session_state.get("metadata_audit")
    if (
        audit_data
        and st.session_state.get("metadata_audit_kho") == eng.kho_dang_dung
    ):
        a1, a2, a3 = st.columns(3)
        a1.metric("Clip trong fingerprint DB", audit_data["total_db_clips"])
        a2.metric("Metadata đầy đủ", audit_data["complete"])
        a3.metric("Metadata một phần", audit_data["partial"])
        a4, a5, a6 = st.columns(3)
        a4.metric("Phục hồi từ filename", audit_data["filename_fallbacks"])
        a5.metric("Chưa ánh xạ", audit_data["missing"])
        a6.metric("Mơ hồ / xung đột", audit_data["ambiguous"])
        st.caption(
            "Nguồn đang dùng: "
            + (", ".join(audit_data.get("source_files") or []) or "chưa có")
            + f" · Snapshot cập nhật: {audit_data.get('updated_at') or 'chưa có'}"
        )
        if audit_data.get("complete", 0) == 0 and audit_data.get("total_db_clips", 0):
            st.warning(
                "Kho có fingerprint nhưng chưa clip nào có đủ toàn bộ metadata báo cáo. "
                "Có thể xuất dữ liệu fallback, nhưng báo cáo chưa được xem là đầy đủ."
            )
        if audit_data.get("samples"):
            with st.expander("Mẫu metadata thiếu/mơ hồ (tối đa 20)"):
                st.dataframe(
                    pd.DataFrame(audit_data["samples"]),
                    width="stretch",
                    hide_index=True,
                )

    preview_data = st.session_state.get("metadata_repair_preview")
    if (
        preview_data
        and st.session_state.get("metadata_repair_preview_kho") == eng.kho_dang_dung
    ):
        st.info(
            f"Dry-run: {preview_data['updated']} entry sẽ được cập nhật, "
            f"{preview_data['unchanged']} không đổi, "
            f"{preview_data['skipped_ambiguous']} mơ hồ bị bỏ qua."
        )
    confirm_offline = st.checkbox(
        "Tôi xác nhận chỉ tạo/cập nhật snapshot metadata offline của kho đang dùng",
        key=f"confirm_metadata_offline_{eng.kho_dang_dung}",   # đổi kho → hỏi lại
    )
    if st.button(
        "🛠️ Khôi phục metadata offline",
        disabled=not (confirm_offline and bool(clips)),
    ):
        try:
            repaired = eng.khoi_phuc_metadata_offline(dry_run=False)
            if repaired.errors:
                st.error("; ".join(repaired.errors))
            else:
                st.success(
                    f"Đã cập nhật snapshot: {repaired.updated} entry; "
                    f"không đổi {repaired.unchanged}."
                )
                st.caption(f"Snapshot: `{repaired.snapshot_path}`")
                st.session_state.metadata_audit = eng.kiem_tra_metadata_kho().to_dict()
                st.session_state.metadata_audit_kho = eng.kho_dang_dung
        except Exception as e:  # noqa: BLE001
            st.error(f"Không khôi phục được metadata: {e}")

    with st.expander("🌐 Vá metadata thiếu từ YouTube (tác vụ mạng riêng)"):
        st.warning(
            "Chỉ dùng khi bạn chủ động cần ngày đăng/thời lượng chính thức. "
            "Tác vụ không tải audio/video, có timeout và retry hữu hạn, nhưng có thể "
            "mất nhiều thời gian với kho lớn."
        )
        confirm_network = st.checkbox(
            "Tôi xác nhận cho phép gọi YouTube để vá các entry còn thiếu",
            key=f"confirm_metadata_network_{eng.kho_dang_dung}")
        if st.button(
            "Bắt đầu vá metadata thiếu",
            disabled=not (
                confirm_network
                and bool(clips)
                and eng.kho_thu_muc
                and not job.get("running")
                and not dang_dong_bo()
            ),
        ):
            chay_nen("metadata_network", eng.va_metadata_thieu)

    if clips:
        st.divider()
        st.write(f"**Kho «{eng.kho_dang_dung}» hiện có {len(clips)} clip:**")
        st.dataframe(pd.DataFrame(
            [{"Tên clip": x["ten"], "Số hash": x["so_hash"], "Đường dẫn": x["duong_dan"]}
             for x in clips]), width="stretch", hide_index=True, height=300)
    elif eng.kho_dang_dung:
        st.info("Kho này đang trống. Nhập đường dẫn thư mục rồi bấm «Tạo lại kho từ đầu».")

# ---------------------------------------------------------------- TAB 2
def _trang_ds_kho() -> None:
    st.subheader("Danh sách tên video đã tải về trong kho")
    st.caption("Đọc thẳng file trên đĩa và `clips_meta.json` của kho — không tải gì "
               "từ mạng, không sửa file nào. Tên video lấy từ metadata nên là tên "
               "THẬT trên YouTube, không phải tên file đã bị làm sạch ký tự.")

    if not khos:
        st.warning("Chưa có kho nào — tạo ở tab «Kho clip gốc».")
    else:
        # Mở sẵn ĐÚNG kho đang dùng ở thanh bên. Không có `index`, Streamlit lấy
        # phần tử số 0 — người dùng dễ quét kho này rồi đẩy đè lên trang tính kho kia.
        tens_dsv = [k["ten"] for k in khos]
        mac_dinh_dsv = (eng.kho_dang_dung if eng.kho_dang_dung in tens_dsv
                        else tens_dsv[0])
        ten_chon = st.selectbox("Chọn kho muốn liệt kê", tens_dsv,
                                index=tens_dsv.index(mac_dinh_dsv), key="dsv_kho", persist_state="session")
        thu_muc_dsv = next((k.get("thu_muc") or "" for k in khos
                            if k["ten"] == ten_chon), "")

        if thu_muc_dsv and os.path.isdir(thu_muc_dsv):
            st.caption(f"Thư mục: `{thu_muc_dsv}`")
        else:
            # Hai ca cùng cần một ô nhập, và ca THỨ HAI mới là ca hay gặp:
            #  (a) kho chưa gán thư mục;
            #  (b) kho có gán nhưng thư mục KHÔNG tồn tại trên máy này — chép kho
            #      sang máy khác hay đổi ổ đĩa là dính ngay, vì khos.json lưu đường
            #      dẫn TUYỆT ĐỐI (D:\ClipGocSML).
            # Bản đầu chỉ bắt ca (a) nên ca (b) thành ngõ cụt: người dùng thấy báo
            # đỏ «không tìm thấy thư mục» mà không có chỗ nào sửa ngay tại đây.
            if thu_muc_dsv:
                st.warning(
                    f"Kho «{ten_chon}» đang trỏ tới `{thu_muc_dsv}` nhưng máy này "
                    "không có thư mục đó. Thường gặp khi chép kho sang máy khác "
                    "hoặc đổi ổ đĩa. Nhập đường dẫn đúng bên dưới rồi bấm lưu.")
            c_dm, c_chon_dm = st.columns([5, 1], vertical_alignment="bottom")
            with c_chon_dm:
                _chon_dm = ui_thao_tac.nut_chon("chon_dsv_thu_muc", st.session_state.get("dsv_thu_muc_moi", ""),
                                                tieu_de=f"Chọn thư mục audio của kho «{ten_chon}»")
            if _chon_dm:
                st.session_state["dsv_thu_muc_moi"] = _chon_dm[0]
            duong_moi = c_dm.text_input(
                f"Đường dẫn thư mục audio của kho «{ten_chon}» trên máy này",
                key="dsv_thu_muc_moi", placeholder=r"D:\ClipGocDanny", persist_state="session")
            if st.button("💾 Lưu thư mục cho kho này", key="dsv_luu_thu_muc",
                         disabled=not duong_moi):
                d_moi = (duong_moi or "").strip().strip('"')
                if not os.path.isdir(d_moi):
                    st.error(f"Không tìm thấy thư mục «{d_moi}». Kiểm tra lại đường "
                             "dẫn hoặc cắm ổ đĩa rồi bấm lại.")
                else:
                    # `ten_chon` chứ KHÔNG phải `eng.kho_dang_dung`: dropdown ở đây
                    # độc lập với kho đang dùng ở thanh bên.
                    eng.update_kho(ten_chon, d_moi)
                    st.rerun()

        st.caption(f"Sẽ ghi vào trang tính «{danh_sach_video.ten_trang_tinh(ten_chon)}» "
                   "— mỗi lần đẩy là VIẾT LẠI TOÀN BỘ trang tính đó (kể cả cột bạn "
                   "tự thêm). Muốn ghi chú riêng thì để ở một trang tính khác.")

        if st.button("📋 Xem danh sách video trong kho", key="dsv_quet",
                     type="primary", width="stretch"):
            st.session_state.pop("dsv_ket_qua", None)
            st.session_state.pop("dsv_kho_da_quet", None)
            with st.spinner(f"Đang đọc tên file trong kho «{ten_chon}» — chỉ đọc, "
                            "không tải và không sửa gì."):
                try:
                    st.session_state.dsv_ket_qua = danh_sach_video.liet_ke_theo_ten_kho(
                        khos, ten_chon)
                    st.session_state.dsv_kho_da_quet = ten_chon
                except danh_sach_video.LoiKho as e:
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Không đọc được kho «{ten_chon}»: {e}")

        kq = st.session_state.get("dsv_ket_qua")
        kho_da_quet = st.session_state.get("dsv_kho_da_quet")
        sx_dsv = SheetsExporter(sheet=st.session_state.sheet_link)
        # So khớp tên kho: KHÔNG bao giờ hiện danh sách kho A dưới nhãn kho B rồi
        # đẩy nhầm lên trang tính của B (cùng cách chặn với `metadata_audit_kho`).
        if kq is not None and kho_da_quet != ten_chon:
            st.info(f"Bạn vừa đổi sang kho «{ten_chon}». Bấm «📋 Xem danh sách video "
                    f"trong kho» để xem kho này. Danh sách của kho «{kho_da_quet}» "
                    f"vẫn còn — chọn lại kho đó là hiện ra ngay.")
        elif kq is not None:
            for cb in kq.canh_bao:
                st.warning(cb)
            st.success(kq.tom_tat())
            if not kq.dong:
                if kq.so_media_khac:
                    st.info("Kho này chứa video gốc (.mp4, .mkv…) chứ không phải "
                            "audio đã tải bằng «Đồng bộ kênh gốc». Vân tay của kho "
                            "vẫn dùng quét bình thường — chỉ tab này chưa liệt kê "
                            "được tên video cho loại kho đó.")
                else:
                    st.info("Kho này chưa có file audio nào (.opus). Hãy đồng bộ kênh "
                            "ở tab «Đồng bộ kênh gốc» trước.")
            else:
                st.caption(f"Danh sách chụp lúc {kq.thoi_diem}. "
                           "Kho vừa đổi thì bấm quét lại. Di chuột lên bảng để hiện "
                           "nút 🔍 tìm kiếm, ⬇️ tải CSV và ⛶ phóng to.")
                # Chia lại bề ngang: STT chỉ cần vài ký tự, phần còn lại nhường hết
                # cho tiêu đề — kho Cory có tiêu đề dài tới 95 ký tự.
                st.dataframe(pd.DataFrame([{"STT": d.stt, "Tên video": d.ten_video}
                                           for d in kq.dong]),
                             width="stretch", hide_index=True, height=420,
                             column_config={
                                 "STT": st.column_config.NumberColumn(width="small"),
                                 "Tên video": st.column_config.TextColumn(width="large"),
                             })

                can_kiem = kq.dong_can_kiem_tra()
                if can_kiem:
                    with st.expander(
                            f"⚠️ {len(can_kiem)} video chưa lấy được tên chính xác"):
                        st.caption(
                            f"{len(can_kiem)} dòng này VẪN được đẩy lên Google "
                            "Sheets bình thường, chỉ là tên có thể thiếu dấu câu "
                            "hoặc bị cắt ở 80 ký tự — không dòng nào bị bỏ ra. "
                            "Muốn có tên đúng: bấm «🌐 Lấy lại tên video thật cho "
                            "kho này» ở tab «Đồng bộ kênh gốc».")
                        st.dataframe(pd.DataFrame([{
                            "STT": d.stt, "Tên đang dùng": d.ten_video,
                            "Tên file": d.ten_file, "Lý do": d.ghi_chu}
                            for d in can_kiem]), width="stretch", hide_index=True)

                if not sx_dsv.san_sang():
                    st.caption("Chưa kết nối được Google Sheets — mở «📊 Google "
                               "Sheets» ở thanh bên: dán link bảng tính, bấm «🔌 "
                               "Kiểm tra kết nối», và chia sẻ quyền «Người chỉnh "
                               "sửa» cho địa chỉ email hiện ở đó.")
                if st.button(f"📤 Đẩy {len(kq.dong)} video lên Google Sheets (ghi đè)",
                             key="dsv_day_sheet", width="stretch",
                             disabled=not sx_dsv.san_sang()):
                    with st.spinner("Đang ghi đè trang tính..."):
                        ok, tb = danh_sach_video.day_len_sheet(
                            kq, st.session_state.sheet_link)
                    (st.success if ok else st.error)("📊 " + tb)
                    if ok:
                        st.link_button("🔗 Mở Google Sheet",
                                       st.session_state.sheet_link, width="stretch")

                if len(khos) > 1 and st.button(
                        f"📤 Đẩy TẤT CẢ {len(khos)} kho lên Google Sheets "
                        "(mỗi kho một trang tính riêng)",
                        key="dsv_day_tat_ca", width="stretch",
                        disabled=not sx_dsv.san_sang()):
                    bao_cao = []
                    with st.spinner("Đang đẩy từng kho..."):
                        for k in khos:
                            ten_k = k["ten"]
                            try:
                                kq_k = danh_sach_video.liet_ke_theo_ten_kho(khos, ten_k)
                                ok_k, tb_k = danh_sach_video.day_len_sheet(
                                    kq_k, st.session_state.sheet_link)
                                so_k = kq_k.so_video
                            except Exception as e:  # noqa: BLE001
                                # Kho lỗi (chưa gán thư mục, ổ chưa cắm) KHÔNG được
                                # làm dừng cả lượt — các kho còn lại vẫn phải chạy.
                                ok_k, tb_k, so_k = False, str(e), 0
                            bao_cao.append({
                                "Kho": ten_k, "Số video": so_k,
                                "Kết quả": ("✅ " if ok_k else "❌ ") + tb_k})
                    st.dataframe(pd.DataFrame(bao_cao), width="stretch",
                                 hide_index=True)
                    st.link_button("🔗 Mở Google Sheet",
                                   st.session_state.sheet_link, width="stretch")

# ---------------------------------------------------------------- TAB 3
O_LINK_QUET_YT = "quet_yt_links"  # tab «🔎 Tìm video nghi vấn» ghi link vào ô này
def _trang_quet_youtube() -> None:
    st.subheader("Quét video YouTube dài")
    st.caption("Hệ thống chỉ tải RIÊNG phần audio (video 30 tiếng ≈ 1–2 GB thay vì vài chục GB). "
               "Đứt mạng cứ chạy lại — sẽ tải tiếp từ chỗ dừng.")

    links_text = st.text_area("Dán link YouTube — mỗi dòng một link", height=160, key=O_LINK_QUET_YT,
                              placeholder="https://www.youtube.com/watch?v=xxxxxxxxxxx\n"
                                          "https://youtu.be/yyyyyyyyyyy", persist_state="session")
    links = [x.strip() for x in links_text.splitlines()
             if x.strip() and not x.strip().startswith("#")]
    if links:
        st.caption(f"Đã nhận {len(links)} link.")
    che_do = st.radio(
        "Cách chọn kết quả",
        ["Mỗi video tự chọn kết quả", "Một video gốc chung cho cả lô"],
        index=0, horizontal=True, key="che_do_chon_ket_qua",
        help="«Một video gốc chung cho cả lô»: tìm MỘT clip gốc trong kho có mặt ở TẤT CẢ "
             "các link (để gom một khiếu nại), kèm một đoạn bằng chứng cho từng video.",
     persist_state="session")
    nguon_chung_bat = che_do == "Một video gốc chung cho cả lô"
    thieu_link = nguon_chung_bat and len(set(links)) < 2
    if nguon_chung_bat:
        st.caption(
            "Tool lấy thông tin cả lô trước, quét TRỌN video ngắn nhất làm mốc, rồi xác minh "
            "ứng viên mạnh nhất trên các video còn lại; cần thì quét bổ sung (tối đa 2 lượt "
            "mỗi video). Trong lúc chạy, Giám sát tự động và tạo kho phải chờ. Không ghi "
            "lịch sử, chưa có đích gửi Google Sheets — tải CSV ở cuối."
            + ("" if eng.config.keep_downloads else
               " ⚠️ «Giữ lại audio đã tải» đang tắt nên lượt quét lại sẽ phải tải lại."))
        if links and thieu_link:
            st.warning("Cần ít nhất 2 link khác nhau để tìm video gốc chung.")
    ghvd, chua_xac_nhan_toan_bo = GHVD_TU_DONG, False
    if not nguon_chung_bat:
        ghvd = st.radio(
            "Giới hạn quét video dài", list(NHAN_GHVD), format_func=NHAN_GHVD.get, index=0,
            horizontal=True, key="gioi_han_video_dai",
            help="Video dài hơn 6 giờ chỉ được TẢI và quét phần đầu — giới hạn đặt ngay ở đường tải, "
                 "không tải trọn rồi cắt; phần đầu không thấy gì cũng KHÔNG tự tải tiếp. Video không "
                 "quá 6 giờ quét như bình thường. Kết quả ghi rõ phần đã quét và phần chưa quét.", persist_state="session")
        if ghvd == GHVD_TOAN_BO:
            st.warning("«Quét toàn bộ video» tải trọn rồi quét hết, không dừng sớm: video rất dài có thể "
                       "phải tải hàng chục GB (video 66 giờ ≈ 18 GB) và chạy nhiều giờ.")
            chua_xac_nhan_toan_bo = not st.checkbox(
                "Tôi chủ động chọn quét toàn bộ video dài", key="xac_nhan_quet_toan_bo")
    dich_yt, tu_dong_yt = ui_gui.chon_dich(eng, key="quet_yt", nguon_chung=nguon_chung_bat)
    if st.button("🚀 Bắt đầu quét", type="primary",
                 disabled=(not links or not env["database"] or thieu_link
                           or chua_xac_nhan_toan_bo)):
        if nguon_chung_bat:
            chay_nguon_chung(links)
        else:
            chay_quet(links, "youtube", dich_id=dich_yt, tu_dong=tu_dong_yt, tab_key="quet_yt",
                      gioi_han_video_dai=ghvd)
    if not env["database"]:
        st.warning("Chưa có kho vân tay — hãy làm tab «Kho clip gốc» trước.")
        _link_trang("Kho clip gốc", "🎬 Sang trang Kho clip gốc")

# ---------------------------------------------------------------- TAB 4
def _trang_quet_file() -> None:
    st.subheader("Quét video/audio dài có sẵn trong máy")
    st.caption("Nhập đường dẫn FILE hoặc THƯ MỤC. Không dùng nút upload để tránh "
               "phải copy file hàng chục GB.")

    c_dd, c_chon_tm_q, c_chon_f_q = st.columns([4, 1, 1], vertical_alignment="bottom")
    with c_chon_tm_q:
        _chon_q = ui_thao_tac.nut_chon("chon_thu_muc_quet", st.session_state.thu_muc_quet_gan_nhat,
                                       nhan="📂 Thư mục…", tieu_de="Chọn thư mục video cần quét")
    with c_chon_f_q:
        _chon_q += ui_thao_tac.nut_chon("chon_file_quet", st.session_state.thu_muc_quet_gan_nhat, "file",
                                        "📄 File…", tieu_de="Chọn file video/audio cần quét")
    if _chon_q:
        st.session_state.thu_muc_quet_gan_nhat = _chon_q[0]
    st.session_state.thu_muc_quet_gan_nhat = c_dd.text_input(
        "Đường dẫn file hoặc thư mục",
        st.session_state.thu_muc_quet_gan_nhat,
        placeholder=r"D:\VideoDai  hoặc  D:\VideoDai\video30h.mp4",
    )
    duong_dan = st.session_state.thu_muc_quet_gan_nhat
    ds_file = []
    if duong_dan:
        dd = duong_dan.strip('" ')
        if os.path.isdir(dd):
            from engine import liet_ke_media
            ds_file = liet_ke_media(dd)
            st.caption(f"Tìm thấy {len(ds_file)} file media trong thư mục.")
        elif os.path.isfile(dd):
            ds_file = [dd]
        else:
            st.error("Không tìm thấy đường dẫn này.")
    dich_file, tu_dong_file = ui_gui.chon_dich(eng, key="quet_file")
    if st.button("🚀 Bắt đầu quét", key="quet_file", type="primary",
                 disabled=not ds_file or not env["database"]):
        chay_quet(ds_file, "file", dich_id=dich_file, tu_dong=tu_dong_file, tab_key="quet_file")

# ---------------------------------------------------------------- TAB 5
def _trang_lich_su() -> None:
    st.subheader("Lịch sử các lần quét")
    # Video vi phạm còn trên YouTube? (D-51) — CHỈ YouTube Data API, mạng chỉ trong nhánh nút; không tool.lock, outbox,
    # Google Sheets. Vẽ bảng chỉ đọc lịch sử + sổ kiem_video_con.json.
    _vi_pham = eng.video_vi_pham()
    if _vi_pham:
        _khoa_api = youtube_api.trang_thai_khoa(eng.data_dir)
        _co_khoa_api = _khoa_api.ma == youtube_api.CO_KHOA
        if st.button("🔎 Kiểm tra video vi phạm còn trên YouTube", key="kiem_video_con", disabled=not _co_khoa_api):
            with st.spinner(f"Đang hỏi YouTube Data API về {len(_vi_pham)} video..."):
                try:
                    _ket_kv = kiem_video_con.kiem_tra(truy_cap_youtube.PhienYouTube(), eng.data_dir,
                                                      [v["ma"] for v in _vi_pham])
                except (luu_tru.LoiDuLieu, OSError) as e:
                    st.error(f"Không ghi được sổ kết quả kiểm: {thoat_markdown(e)}")
                else:
                    _chua_kv = [k for k in _ket_kv.values() if kiem_video_con.nhom(k) == "chua"]
                    if _chua_kv:
                        st.warning(f"{len(_chua_kv)}/{len(_ket_kv)} video chưa kiểm được lần này (kết quả kiểm trước "
                                   "đó vẫn giữ): " + thoat_markdown(" · ".join(dict.fromkeys(_chua_kv))))
                    else:
                        st.success(f"Đã kiểm {len(_ket_kv)} video.")
        if _co_khoa_api:
            st.caption(f"Mỗi lần kiểm {len(_vi_pham)} video tốn khoảng {kiem_video_con.so_don_vi(len(_vi_pham))} đơn "
                       "vị hạn mức YouTube Data API (10.000 đơn vị mỗi ngày) — không dùng yt-dlp.")
        else:
            st.caption("Nút kiểm cần khoá YouTube Data API — không kiểm bằng yt-dlp. " + thoat_markdown(
                _khoa_api.ly_do if _khoa_api.ma == youtube_api.SAI_DANG else f"Đặt file khoá ở {_khoa_api.duong_dan}."))
        try:
            _so_kv = kiem_video_con.doc_so(eng.data_dir)
        except luu_tru.LoiDuLieu as e:
            st.warning(thoat_markdown(e))
            _so_kv = {}
        _bang_kv = kiem_video_con.dong_bang(_vi_pham, _so_kv)
        _dem_kv = kiem_video_con.dem(_bang_kv)
        _c1, _c2, _c3 = st.columns(3)
        _c1.metric("Còn trên YouTube", _dem_kv["con"])
        _c2.metric("Đã gỡ hoặc không còn", _dem_kv["khong_con"])
        _c3.metric("Chưa kiểm được", _dem_kv["chua"])
        st.dataframe(pd.DataFrame(_bang_kv), width="stretch", hide_index=True,
                     column_config={"Link": st.column_config.LinkColumn()})
        st.caption("Google Sheets không bị đổi — muốn ghi vào cột «Trạng thái» của Sheet thì tự chép.")
        st.divider()
    jobs = eng.list_jobs(200)
    if len(jobs) >= 200:   # audit 09/11: trước đây lặng lẽ cắt
        st.caption("Chỉ hiện 200 lần quét gần nhất. Các lần cũ hơn vẫn được lưu trong lịch sử, chỉ không hiện ở bảng này.")
    if not jobs:
        st.info("Chưa có lần quét nào.")
    else:
        # Kho và phạm vi của từng lần quét (audit TCP-07): lịch sử cũ không biết kho
        # nên ghi rõ "chưa rõ — cần rà soát", không đoán là kho đang dùng.
        st.dataframe(pd.DataFrame([{
            "ID": j["id"], "Thời điểm": j["created_at"], "Loại": j["source_type"],
            "Nguồn": j["source_name"], "Thời lượng": hhmmss(j["duration_s"] or 0),
            "Kết quả": j["n_matches"], "Trạng thái": j["status"],
            "Kho": lich_su.mo_ta_kho(j), "Phạm vi": lich_su.mo_ta_pham_vi(j),
        } for j in jobs]), width="stretch", hide_index=True)

        chon = st.selectbox("Xem chi tiết lần quét số",
                            [j["id"] for j in jobs],
                            format_func=lambda i: f"#{i} — " +
                            next(j["source_name"] for j in jobs if j["id"] == i))
        job_chon = next(j for j in jobs if j["id"] == chon)
        pham_vi_chon = lich_su.mo_ta_pham_vi(job_chon)
        # Cảnh báo theo DỮ LIỆU phạm vi, không so chữ nhãn (audit F-12): lượt trọn có lý do kèm
        # theo (vd. âm thanh YouTube ngắn hơn) vẫn là trọn; 0 = một phần, NULL = lịch sử cũ chưa rõ.
        if job_chon.get("day_du") != 1:
            st.warning(f"Kho: {lich_su.mo_ta_kho(job_chon)} · Phạm vi: {pham_vi_chon}. "
                       "Kết quả bên dưới chỉ nói về phần đã quét.")
        # Báo cáo của lần quét: dựng lại TỪ ẢNH CHỤP lúc quét (báo cáo V2), không tra metadata
        # kho hiện tại. Lần quét cũ không có ảnh chụp: lịch sử chỉ còn dữ liệu khớp.
        bc_chon = eng.bao_cao_cua_job(chon)
        loi_bc_chon = bao_cao_v2.la_loi_bao_cao(bc_chon)
        if loi_bc_chon:
            # Lần quét V2 mà báo cáo lỗi/hỏng: KHÔNG phải lần quét cũ, không có nút tải nào
            # (audit P1-02) — dữ liệu khớp bên dưới vẫn xem được.
            st.error("⛔ " + bc_chon.thong_bao())
        elif bc_chon is not None:
            st.caption("📄 Báo cáo của lần quét này được chụp lúc quét (chính sách báo cáo "
                       "V2) — tải lại luôn ra đúng tên, ngày, link như lúc quét.")
            ngang_chon = eng.dong_bao_cao_job(chon, dang_ngang=True) or []
            doc_chon = eng.dong_bao_cao_job(chon, dang_ngang=False) or []
            ch1, ch2 = st.columns(2)
            with ch1:
                if ngang_chon:
                    st.download_button(
                        "⬇️ Tải báo cáo ngang (34 cột)",
                        pd.DataFrame([[o_bang_tinh_an_toan(o) for o in d] for d in ngang_chon],
                                     columns=bang_ngang.HEADER_NGANG)
                        .to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"baocao_ngang_job{chon}.csv", mime="text/csv",
                        key=f"ls_ngang_{chon}")
            with ch2:
                st.download_button(
                    "⬇️ Tải báo cáo dọc (16 cột)",
                    pd.DataFrame([[o_bang_tinh_an_toan(o) for o in d] for d in doc_chon],
                                 columns=eng.HEADER).to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"baocao_doc_job{chon}.csv", mime="text/csv",
                    key=f"ls_doc_{chon}")
        else:
            st.caption("Lần quét cũ (trước báo cáo V2): lịch sử không lưu tên, ngày đăng hay "
                       "link video gốc nên không dựng lại được báo cáo đã xuất lúc đó — bên "
                       "dưới chỉ là dữ liệu khớp.")
        ms = eng.job_matches(chon)
        if ms:
            df = pd.DataFrame([{
                "Clip gốc": m["clip"], "Xuất hiện từ (lượt quét)": hhmmss(m["start_s"]),
                "Đến (lượt quét)": hhmmss(m["end_s"]), "Đoạn khớp (giây)": round(m["matched_s"]),
                "Khớp từ giây thứ (của clip)": round(m["clip_offset_s"]),
                "Số hash": m["hashes"], "Đánh giá": m["confidence"],
                "Phạm vi quét": pham_vi_chon,
            } for m in ms])
            st.dataframe(df, width="stretch", hide_index=True)
            if bc_chon is not None and not loi_bc_chon:
                st.caption("Bảng trên là số đo vân tay của lượt quét (chẩn đoán). «Đoạn vi phạm» để khiếu nại nằm "
                           "trong 2 báo cáo tải ở trên — lượt quét bật ô «🎯 Tinh chỉnh mốc từng giây» thì dòng nào "
                           "tinh chỉnh được dùng mốc từng giây, dòng không tinh chỉnh được giữ mốc của lượt quét.")
            if not loi_bc_chon:
                # Bảng hiển thị giữ nguyên; chỉ bản CSV tải về chặn công thức ở tầng ghi như
                # mọi đường xuất CSV khác (tên clip kho máy có thể bắt đầu bằng = + - @).
                st.download_button("⬇️ Tải CSV lần quét này",
                                   df.map(o_bang_tinh_an_toan).to_csv(index=False)
                                   .encode("utf-8-sig"),
                                   file_name=f"ketqua_job{chon}.csv", mime="text/csv")
        else:
            st.info("Lần quét này không có kết quả nào.")
        viec_job = outbox.ds_viec(eng.sqlite_file, job_id=chon)
        if viec_job:
            st.caption("📤 Gửi Google Sheets của lần quét này: " + "; ".join(
                f"{outbox.NHAN_TRANG_THAI[v.trang_thai]} ({v.so_dong} dòng)" for v in viec_job))
        if not loi_bc_chon and bc_chon is not None:
            ui_gui.nut_gui_cho_job(eng, [chon], key=f"gui_ls_{chon}")
        # Ô xác nhận gắn ĐÚNG job đang chọn và tự bỏ tick sau khi xoá: trước đây một ô dùng chung
        # vẫn tick sau khi xoá, chọn lần quét kế tiếp rồi bấm nữa là xoá luôn — không hỏi lại.
        khoa_xn = f"xac_nhan_xoa_ls_{chon}"
        xac_nhan_xoa_lich_su = st.checkbox(
            "Tôi xác nhận muốn xóa lần quét đã chọn khỏi lịch sử", key=khoa_xn
        )
        if st.button(
            "🗑️ Xóa lần quét này khỏi lịch sử",
            disabled=not xac_nhan_xoa_lich_su,
        ):
            try:
                eng.delete_job(chon)
                st.session_state.pop(khoa_xn, None)
                st.rerun()
            except LoiXoaJob as e:
                st.error(str(e))

# ---------------------------------------------------------------- TAB 6
def _trang_gui_sheets() -> None:
    ui_gui.ve_tab(eng)


# ---------------------------------------------------------------- TÌM VIDEO NGHI VẤN (D-51)
def _dua_vao_o_quet(links: list) -> None:
    # Callback chạy TRƯỚC lượt vẽ lại, lúc ô link của tab «▶️ Quét YouTube» chưa được tạo — ghi session_state được.
    st.session_state[O_LINK_QUET_YT] = tim_nghi_van.noi_link(st.session_state.get(O_LINK_QUET_YT, ""), links)
    st.session_state.tim_da_dua = True


def _trang_tim_nghi_van() -> None:
    st.subheader("Tìm video nghi vấn theo tiêu đề clip gốc")
    st.caption("Tìm trên YouTube (YouTube Data API) các video có tiêu đề giống tiêu đề clip gốc của kho — chỉ TÌM, không "
               "tải, không quét. Chọn video muốn kiểm rồi đưa sang tab «▶️ Quét YouTube».")
    tt_khoa = youtube_api.trang_thai_khoa(eng.data_dir)
    if tt_khoa.ma == youtube_api.SAI_DANG:
        st.error(f"Khoá YouTube Data API không dùng được: {tt_khoa.ly_do} (file ở `{tt_khoa.duong_dan}`)")
    elif tt_khoa.ma != youtube_api.CO_KHOA:
        st.warning("Tìm video nghi vấn cần khoá YouTube Data API: đặt file khoá (một dòng, bắt đầu bằng «AIza») ở "
                   f"`{tt_khoa.duong_dan}` rồi tải lại trang (F5).")
    if not khos:
        st.warning("Chưa có kho nào — tạo ở tab «Kho clip gốc».")
    else:
        tens_tim = [k["ten"] for k in khos]
        ten_tim = st.selectbox("Kho", tens_tim, key="tim_kho",
                               index=tens_tim.index(eng.kho_dang_dung) if eng.kho_dang_dung in tens_tim else 0, persist_state="session")
        if ten_tim != eng.kho_dang_dung:
            st.info(f"Tab «▶️ Quét YouTube» quét bằng kho đang dùng ở thanh bên («{eng.kho_dang_dung}»), cột «Đã quét "
                    f"chưa» cũng tính theo kho đó — muốn quét với kho «{ten_tim}», đổi kho ở thanh bên.")
        clips_tim = tim_nghi_van.clip_cua_kho(next(k.get("thu_muc") or "" for k in khos if k["ten"] == ten_tim))
        theo_khoa = {c.khoa: c for c in clips_tim}
        if not clips_tim:
            st.caption(f"Kho «{ten_tim}» chưa có tiêu đề clip nào trong `clips_meta.json` — vẫn tìm được bằng ô «Truy vấn "
                       "thêm» bên dưới.")
        chon_tim = st.multiselect(f"Clip lấy tiêu đề để tìm ({len(clips_tim)} clip, mới nhất trước)", list(theo_khoa),
                                  default=list(theo_khoa)[:tim_nghi_van.TOI_DA_MAC_DINH],
                                  format_func=lambda k: theo_khoa[k].tieu_de, key=f"tim_clip::{ten_tim}", persist_state="session")
        them_tim = st.text_area("Truy vấn thêm (tuỳ chọn) — mỗi dòng một truy vấn", key="tim_them", height=80,
                                placeholder="SML compilation 10 hours", persist_state="session")
        c_tl, c_td, c_ng = st.columns(3)
        with c_tl:
            thoi_luong_tim = st.radio("Thời lượng video", list(tim_nghi_van.NHAN_THOI_LUONG),
                                      format_func=tim_nghi_van.NHAN_THOI_LUONG.get, key="tim_thoi_luong", persist_state="session")
        with c_td:
            toi_da_tim = st.number_input("Tối đa số truy vấn mỗi lần bấm", 1, tim_nghi_van.TOI_DA,
                                         tim_nghi_van.TOI_DA_MAC_DINH, key="tim_toi_da", persist_state="session")
        with c_ng:
            sau_tim = st.date_input("Chỉ video đăng từ ngày (bỏ trống = mọi lúc)", value=None, format="DD/MM/YYYY",
                                    key="tim_sau", persist_state="session")
        clip_chon = [theo_khoa[k] for k in chon_tim]
        ds_tv = tim_nghi_van.tao_truy_van(clip_chon, them_tim)
        chay_tv = ds_tv[:int(toi_da_tim)]
        if len(ds_tv) > len(chay_tv):
            st.caption(f"Có {len(ds_tv)} truy vấn — chỉ chạy {len(chay_tv)} truy vấn đầu (tăng «Tối đa số truy vấn» hoặc "
                       "bỏ bớt clip).")
        st.caption("Mỗi truy vấn = 1 lượt trong hạn mức tìm kiếm 100 lượt/ngày (đặt lại khoảng 14–15 giờ chiều giờ Việt "
                   "Nam). Thời lượng và kênh gốc lấy thêm bằng videos.list — hạn mức riêng 10.000 đơn vị, khoảng 1 đơn vị "
                   "cho 50 video.")
        # Đọc/ghi st.session_state cũng là điểm nhường: thao tác của người dùng lúc đang tìm chen lượt chạy lại ở điểm
        # nhường đầu tiên sau tim(). Lấy sẵn dict lưu kết quả ở đây, sau tim() chỉ ghi dict thường — không mất kết quả đã
        # tốn hạn mức.
        luu_tim = st.session_state.setdefault("tim_luu", {})
        if st.button(f"🔎 Tìm ({len(chay_tv)} lượt)", key="tim_nut", type="primary",
                     disabled=not (tt_khoa.ma == youtube_api.CO_KHOA and chay_tv)):
            phien_api = truy_cap_youtube.PhienYouTube()   # videos.list; tìm kiếm có phiên riêng (hạn mức riêng)
            with st.spinner(f"Đang tìm {len(chay_tv)} truy vấn trên YouTube..."):
                kenh_goc, ly_do_kenh = st.session_state.setdefault("tim_kenh_goc", {}).get(ten_tim), ""
                if kenh_goc is None:
                    kenh_goc, ly_do_kenh = tim_nghi_van.kenh_cua_kho(
                        phien_api, eng.data_dir, [c.ma for c in clip_chon + list(clips_tim)])
                    if kenh_goc:
                        st.session_state.tim_kenh_goc[ten_tim] = kenh_goc
                kq_tim = tim_nghi_van.tim(phien_api, eng.data_dir, chay_tv, phien_tim=truy_cap_youtube.PhienYouTube(),
                                          kenh_goc=kenh_goc, thoi_luong=thoi_luong_tim, sau=sau_tim)
                if kenh_goc:
                    canh_bao_kenh = (f"Đã loại video của kênh gốc, nhưng {ly_do_kenh}.",) if ly_do_kenh else ()
                else:
                    canh_bao_kenh = ("Không loại được video của chính kênh gốc"
                                     + (f" — {ly_do_kenh}" if ly_do_kenh else "") + ". Kết quả có thể gồm video của bạn.",)
                luu_tim["lan"] = luu_tim.get("lan", 0) + 1
                luu_tim["ket_qua"] = (ten_tim, kq_tim, canh_bao_kenh + kq_tim.ghi_chu)
        if luu_tim.get("ket_qua"):
            kho_kq, kq_tim, ghi_chu_tim = luu_tim["ket_qua"]
            (st.success if kq_tim.da_tim == kq_tim.tong else st.warning)(
                f"Kho «{kho_kq}»: tìm được {kq_tim.da_tim}/{kq_tim.tong} truy vấn (đã dùng {kq_tim.luot_tim} lượt tìm "
                f"kiếm) — {len(kq_tim.video)} video"
                + (f", đã bỏ {kq_tim.bo_kenh_goc} video của kênh gốc" if kq_tim.bo_kenh_goc else "") + ".")
            for g in ghi_chu_tim:
                st.warning(g)
            if kq_tim.video:
                dong_tim = tim_nghi_van.bang(kq_tim.video, eng.ids_da_quet())
                su_kien = st.dataframe(
                    pd.DataFrame(dong_tim, columns=tim_nghi_van.COT), key=f"tim_bang_{luu_tim['lan']}",
                    on_select="rerun", selection_mode="multi-row", hide_index=True,
                    column_config={"Tiêu đề": st.column_config.TextColumn(width="large"),
                                   "Link": st.column_config.LinkColumn()})
                st.caption("Bấm ô đầu dòng để chọn video. «Đã quét chưa» = đã kiểm xong với kho đang dùng (có kết quả, "
                           "hoặc đã quét trọn mà không thấy) — cùng cách tính với Giám sát.")
                links_tim = [dong_tim[i]["Link"] for i in su_kien.selection.rows]
                st.button(f"➡️ Đưa {len(links_tim)} video đã chọn vào ô quét YouTube", key="tim_dua",
                          on_click=_dua_vao_o_quet, args=(links_tim,), disabled=not links_tim)
                if st.session_state.get(O_LINK_QUET_YT, "").strip():
                    _link_trang("Quét YouTube", "▶️ Sang trang Quét YouTube để quét các link trong ô")
                if st.session_state.pop("tim_da_dua", 0):
                    st.success("Đã đưa link vào ô «Dán link YouTube» — mở tab «▶️ Quét YouTube» để quét (tool không tự "
                               "quét). Link đã có sẵn trong ô thì không thêm lại.")

# ---------------------------------------------------------------- THỐNG KÊ (chỉ đọc lịch sử)
@st.cache_data(max_entries=16, show_spinner=False)
def _thong_ke(duong_dan: str, chu_ky: tuple, tu_ngay, den_ngay) -> thong_ke.ThongKe:
    """Mọi tab vẽ lại sau MỖI cú bấm: chỉ tính lại khi lichsu.db đổi hoặc đổi khoảng ngày. ``chu_ky`` = (mtime, cỡ)
    của file — journal mặc định của SQLite (không WAL) ghi thẳng vào file DB mỗi lần commit."""
    return thong_ke.tinh(duong_dan, tu_ngay, den_ngay)


def _trang_thong_ke() -> None:
    st.subheader("Thống kê vi phạm")
    st.caption("Chỉ đọc lịch sử quét trên máy này — không quét lại, không hỏi YouTube.")
    c_tu, c_den = st.columns(2)
    tk_tu = c_tu.date_input("Từ ngày quét", value=None, format="DD/MM/YYYY", key="tk_tu_ngay", persist_state="session")
    tk_den = c_den.date_input("Đến ngày quét", value=None, format="DD/MM/YYYY", key="tk_den_ngay", persist_state="session")
    try:
        tk_file = os.stat(eng.sqlite_file)
        tke = _thong_ke(eng.sqlite_file, (tk_file.st_mtime_ns, tk_file.st_size), tk_tu, tk_den)
    except (OSError, sqlite3.Error) as e:   # vd. lịch sử đang bị khoá lâu: báo gọn thay vì traceback
        tke = None
        st.error(f"Chưa đọc được lịch sử để thống kê ({type(e).__name__}: {e}). Thử lại sau ít phút.")
    if tke is not None and not tke.so_lan_quet:
        st.info("Chưa có lần quét nào" + (" trong khoảng ngày đã chọn." if tk_tu or tk_den else "."))
    elif tke is not None:
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Số lần quét", tke.so_lan_quet, help="Tính cả lần quét lỗi / đã huỷ.")
        m2.metric("Lỗi / đã huỷ", tke.so_lan_loi)
        m3.metric("Video vi phạm", tke.so_video_vi_pham, help="Video có ít nhất một đoạn khớp clip gốc.")
        m4.metric("Đoạn khớp", tke.so_doan_khop)
        m5.metric("Tổng thời lượng khớp", hhmmss(tke.tong_giay_khop))
        st.caption(f"Lần quét đầu: {format_publication_date(tke.ngay_dau) or '—'} · gần nhất: "
                   f"{format_publication_date(tke.ngay_cuoi) or '—'}. Quét lại một video không làm tăng số liệu: mỗi "
                   "cặp video vi phạm – clip gốc tính một lần (số đoạn và số giây lớn nhất trong các lần quét). Lần "
                   "quét lỗi / đã huỷ không tính vào vi phạm.")
        if tke.so_video_vi_pham:
            st.markdown("**📺 Kênh vi phạm nhiều nhất**")
            if tke.kenh:
                st.dataframe(pd.DataFrame([{
                    "Kênh": k["ten"], "Link kênh": k["link"], "Video vi phạm": k["so_video"],
                    "Đoạn khớp": k["so_doan"], "Thời lượng khớp": hhmmss(k["tong_giay"]),
                } for k in tke.kenh]), width="stretch", hide_index=True,
                    column_config={"Link kênh": st.column_config.LinkColumn()})
            if tke.video_chua_ro_kenh:
                st.caption(f"{tke.video_chua_ro_kenh} video vi phạm chưa rõ kênh: lần quét trước báo cáo V2 (lịch sử "
                           "cũ không lưu kênh), quét file trong máy, YouTube không trả tên kênh, hoặc báo cáo V2 "
                           "không đọc được.")
            if tke.anh_chup_khong_doc_duoc:
                st.warning(f"⚠️ {tke.anh_chup_khong_doc_duoc} video vi phạm chỉ có báo cáo V2 không đọc được — chưa "
                           "rõ kênh (đoạn khớp của chúng vẫn được tính). Quét lại các video đó để có báo cáo mới.")
            st.markdown("**🎬 Clip gốc bị dùng nhiều nhất**")
            st.dataframe(pd.DataFrame([{
                "Clip gốc": c["clip"], "Tên video gốc (lúc quét)": c["tieu_de"], "Video vi phạm": c["so_video"],
                "Đoạn khớp": c["so_doan"], "Thời lượng khớp": hhmmss(c["tong_giay"]),
            } for c in tke.clip]), width="stretch", hide_index=True)
            st.markdown("**📈 Video vi phạm phát hiện lần đầu theo tháng**")
            if tke.theo_thang:
                st.bar_chart(pd.DataFrame({"Tháng": [thong_ke.nhan_thang(t) for t, _ in tke.theo_thang],
                                           "Video vi phạm mới": [n for _, n in tke.theo_thang]}),
                             x="Tháng", y="Video vi phạm mới", sort=False)
            else:
                st.caption("Không có video vi phạm mới trong khoảng ngày đã chọn: các video trên đã được phát hiện "
                           "từ trước «Từ ngày quét».")
        else:
            st.info("Chưa thấy video vi phạm nào" + (" trong khoảng ngày đã chọn." if tk_tu or tk_den else "."))


# ---------------------------------------------------------------- MENU: 5 NHÓM, 15 TRANG (người dùng duyệt 23/11)
_TRANG = {
    "🔎 Quét vi phạm": [
        st.Page(_trang_quet_youtube, title="Quét YouTube", icon="▶️", url_path="quet-youtube", default=True),
        st.Page(_trang_quet_file, title="Quét file trong máy", icon="📁", url_path="quet-file"),
        st.Page(_trang_tim_nghi_van, title="Tìm video nghi vấn", icon="🔎", url_path="tim-nghi-van"),
    ],
    "📜 Kết quả": [
        st.Page(_trang_lich_su, title="Lịch sử", icon="📜", url_path="lich-su"),
        st.Page(_trang_gui_sheets, title="Gửi Google Sheets", icon="📤", url_path="gui-sheets"),
        st.Page(_trang_thong_ke, title="Thống kê", icon="📊", url_path="thong-ke"),
    ],
    "🗄️ Kho clip gốc": [
        st.Page(_trang_dong_bo, title="Đồng bộ kênh gốc", icon="📥", url_path="dong-bo-kenh"),
        st.Page(_trang_kho, title="Kho clip gốc", icon="🎬", url_path="kho-clip-goc"),
        st.Page(_trang_ds_kho, title="Danh sách video trong kho", icon="📋", url_path="danh-sach-kho"),
    ],
    "⬇️ Tải về": [
        st.Page(_trang_tai_video, title="Tải video gốc", icon="⬇️", url_path="tai-video"),
        st.Page(_trang_tai_ca_kenh, title="Tải cả kênh", icon="📺", url_path="tai-ca-kenh"),
        st.Page(_trang_thumbnail, title="Tải thumbnail", icon="🖼️", url_path="tai-thumbnail"),
        st.Page(_trang_tieu_de_kenh, title="Tiêu đề kênh", icon="📝", url_path="tieu-de-kenh"),
    ],
    "🛠️ Xử lý video": [
        st.Page(_trang_ghep, title="Ghép video gốc", icon="🎞️", url_path="ghep-video"),
        st.Page(_trang_video_trong_may, title="Video trong máy", icon="🛠️", url_path="video-trong-may"),
    ],
}
# Theo TÊN trang: trang mặc định có url_path rỗng.
_TRANG_CAN_KHO = {"Quét YouTube", "Quét file trong máy", "Tìm video nghi vấn", "Kho clip gốc",
                  "Danh sách video trong kho"}

if os.environ.get("TIMCLIP_UI_VE_MOI_TRANG") == "1":
    # shortcut: AppTest.switch_page chỉ nhận trang dạng FILE nên bộ test vẽ MỌI trang trong 15 tab như trước 23/11;
    # khi AppTest chuyển được trang dạng hàm thì bỏ nhánh này.
    _ve_o_kho()
    for _tab, _ham in zip(st.tabs(
        ["📥 Đồng bộ kênh gốc", "⬇️ Tải video gốc", "🖼️ Tải thumbnail", "📺 Tải cả kênh", "🎞️ Ghép video gốc",
         "🛠️ Video trong máy", "📝 Tiêu đề kênh", "🎬 Kho clip gốc", "📋 Danh sách video trong kho",
         "▶️ Quét YouTube", "📁 Quét file trong máy", "📜 Lịch sử", "📤 Gửi Google Sheets", "🔎 Tìm video nghi vấn", "📊 Thống kê"],
    ), [_trang_dong_bo, _trang_tai_video, _trang_thumbnail, _trang_tai_ca_kenh, _trang_ghep, _trang_video_trong_may, _trang_tieu_de_kenh, _trang_kho, _trang_ds_kho, _trang_quet_youtube, _trang_quet_file, _trang_lich_su, _trang_gui_sheets, _trang_tim_nghi_van, _trang_thong_ke], strict=True):
        with _tab:
            _ham()
else:
    _trang = st.navigation(_TRANG, position="top")
    if _trang.title in _TRANG_CAN_KHO:
        _ve_o_kho()
    _trang.run()
