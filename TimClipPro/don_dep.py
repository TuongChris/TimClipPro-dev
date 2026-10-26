# -*- coding: utf-8 -*-
"""Quản lý vòng đời kho đệm và thư mục job quét theo tuổi/ngân sách dung lượng."""

from __future__ import annotations

import contextlib
import glob
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from khoa import DangChayRoi, KhoaTienTrinh


_BYTE_MOI_GB = 1024 ** 3
_GIAY_MOI_NGAY = 24 * 60 * 60
_DUOI_DANG_TAI = (".part", ".ytdl")

# Kho đệm là ``<data>/downloads``; hai thư mục khoá dưới đây nằm cạnh nó, NGOÀI ``downloads/`` để bộ
# đệm (``glob(<tên>.*)``) và chính việc dọn đệm không bao giờ thấy chúng.
# - ``khoa_tai/<tên>.lock``: khoá tải MỘT mục đệm của engine (``Engine._khoa_tai_audio``) — dọn đệm
#   cũng xoá file dưới khoá này nên không lọt giữa lúc một lượt quét nhận file và lúc nó đặt dấu.
# - ``dem_dang_dung/<tên file>~<mã>.lock``: dấu «lượt quét đang dùng file đệm» (audit C-9). Mỗi lượt
#   một file khoá HĐH riêng — nhiều lượt cùng dùng một file được; khoá HĐH tự nhả khi tiến trình chết,
#   nên dấu của lượt bị kill/crash không giữ file mãi (dọn đệm lấy được khoá = dấu mồ côi, bỏ dấu).
THU_MUC_KHOA_TAI = "khoa_tai"
THU_MUC_DANG_DUNG = "dem_dang_dung"


@dataclass
class MucDem:
    path: str
    kich_thuoc: int
    lan_dung_cuoi: float


def chon_can_xoa(
    muc: list,
    max_byte: int,
    max_giay: float,
    bay_gio: Optional[float] = None,
) -> list:
    """Chọn các mục quá tuổi, rồi chọn mục cũ nhất tới khi lọt ngân sách."""
    moc_hien_tai = time.time() if bay_gio is None else bay_gio
    can_xoa = []
    con_lai = []

    for item in muc:
        if (
            max_giay > 0
            and moc_hien_tai - item.lan_dung_cuoi > max_giay
        ):
            can_xoa.append(item)
        else:
            con_lai.append(item)

    if max_byte <= 0:
        return can_xoa

    tong_con_lai = sum(item.kich_thuoc for item in con_lai)
    if tong_con_lai <= max_byte:
        return can_xoa

    for item in sorted(con_lai, key=lambda x: x.lan_dung_cuoi):
        can_xoa.append(item)
        tong_con_lai -= item.kich_thuoc
        if tong_con_lai <= max_byte:
            break
    return can_xoa


def ten_muc_dem(ten_file: str) -> str:
    """Tên lượt tải (``<id>`` / ``<id>__p<giây>``) của file đệm ``<tên>.<đuôi>`` — khoá tải của
    engine đặt theo tên này, bộ đệm tìm file bằng ``glob(<tên>.*)``."""
    return ten_file.split(".", 1)[0]


def _goc_du_lieu(thu_muc_dem: str) -> str:
    return os.path.dirname(os.path.abspath(thu_muc_dem))


def duong_khoa_tai(thu_muc_dem: str, ten: str) -> str:
    """File khoá tải của mục đệm ``ten`` (``Engine._khoa_tai_audio`` dùng đúng đường này)."""
    return os.path.join(_goc_du_lieu(thu_muc_dem), THU_MUC_KHOA_TAI, ten + ".lock")


def dat_dau_dang_dung(thu_muc_dem: str, ten_file: str, ten_viec: str = "") -> KhoaTienTrinh:
    """Đặt dấu «đang dùng» (đã giữ khoá) cho file đệm ``ten_file``; nhả bằng ``nha_dau_dang_dung``.

    Người gọi phải đang giữ khoá tải của mục đó (``duong_khoa_tai``): dọn đệm kiểm dấu và xoá file
    dưới CÙNG khoá. Từ lúc ``download_audio`` trả file tới lúc dấu được đặt, file chỉ được bảo vệ
    bằng mtime vừa làm mới: dọn đệm stat lại dưới khoá và bỏ file đã đổi kể từ lúc liệt kê (WR-4).
    """
    duong = os.path.join(_goc_du_lieu(thu_muc_dem), THU_MUC_DANG_DUNG,
                         f"{ten_file}~{os.getpid()}_{uuid.uuid4().hex[:12]}.lock")
    dau = KhoaTienTrinh(duong, ten_viec or f"Lượt quét đang dùng file đệm {ten_file}")
    dau.__enter__()
    return dau


def nha_dau_dang_dung(dau: KhoaTienTrinh) -> None:
    dau.__exit__()
    with contextlib.suppress(OSError):
        os.remove(dau.path)


def _dang_duoc_dung(thu_muc_dem: str, ten_file: str, bo_dau_mo_coi: bool) -> bool:
    """Còn lượt quét nào (tiến trình còn sống) giữ dấu «đang dùng» của ``ten_file`` không?

    Lấy được khoá của một dấu = chủ của nó đã chết: dấu mồ côi, bỏ đi khi ``bo_dau_mo_coi`` (chỉ
    bật khi đang giữ khoá tải của mục — xem ``dat_dau_dang_dung``).
    """
    mau = os.path.join(glob.escape(os.path.join(_goc_du_lieu(thu_muc_dem), THU_MUC_DANG_DUNG)),
                       glob.escape(ten_file) + "~*.lock")
    dang_dung = False
    for duong in glob.glob(mau):
        dau = KhoaTienTrinh(duong, "Dọn kho đệm: kiểm dấu đang dùng")
        try:
            dau.__enter__()
        except (DangChayRoi, OSError):
            # Không lấy được khoá (hay không mở được dấu): coi là ĐANG dùng — thận trọng.
            dang_dung = True
            continue
        dau.__exit__()
        if bo_dau_mo_coi:
            with contextlib.suppress(OSError):
                os.remove(duong)
    return dang_dung


def xoa_file_dem_neu_ranh(thu_muc_dem: str, ten_file: str) -> bool:
    """Xoá file đệm ``ten_file`` CHỈ khi không lượt nào khác đang tải / nhận / dùng nó.

    Cùng giao thức với vòng xoá của ``don_kho_dem``: lấy khoá tải của mục (không chờ — đang bị giữ =
    lượt khác đang tải hay nhận file) rồi kiểm dấu «đang dùng» dưới khoá đó. Engine bỏ bản đệm cụt /
    bản không giữ đệm qua đây chứ không ``os.remove`` trần (audit WR-5). True = đã xoá (hoặc không còn
    file); False = có lượt khác đang dùng, để nguyên.
    """
    khoa = KhoaTienTrinh(duong_khoa_tai(thu_muc_dem, ten_muc_dem(ten_file)), f"Bỏ file đệm: {ten_file}")
    try:
        khoa.__enter__()
    except DangChayRoi:
        return False
    try:
        if _dang_duoc_dung(thu_muc_dem, ten_file, bo_dau_mo_coi=True):
            return False
        with contextlib.suppress(FileNotFoundError):
            os.remove(os.path.join(thu_muc_dem, ten_file))
        return True
    finally:
        khoa.__exit__()


def don_kho_dem(
    thu_muc: str,
    max_gb: float = 20.0,
    max_ngay: int = 7,
    thuc_hien: bool = True,
) -> dict:
    """Quét và dọn các file trực tiếp trong kho đệm, không đi vào thư mục con.

    File một lượt quét ĐANG dùng (dấu ``dem_dang_dung``, audit C-9) không bao giờ bị chọn: GUI, CLI và
    Watch dùng chung ``data/``, lượt quét chỉ giữ lease cổng bảo trì (không giữ ``tool.lock``) và cắt
    khúc bằng từng lệnh FFmpeg riêng — giữa hai lệnh không ai mở file, nên xoá vẫn thành công và lượt
    quét hỏng giữa chừng với câu lỗi đổ cho file. File đang dùng vẫn tính vào ngân sách dung lượng
    (nó chiếm ổ thật): vượt ngân sách thì bỏ file nhàn rỗi thay vì file đang quét.
    """
    ket_qua = {
        "tong_file": 0,
        "tong_gb": 0.0,
        "xoa_file": 0,
        "xoa_gb": 0.0,
        "bo_qua_dang_dung": 0,
        "loi": [],
    }
    if not os.path.isdir(thu_muc):
        return ket_qua

    tat_ca = []
    co_the_xoa = []
    dang_dung = []
    try:
        cac_muc = list(os.scandir(thu_muc))
    except OSError as e:
        ket_qua["loi"].append(f"Không quét được kho đệm {thu_muc}: {e}")
        return ket_qua

    for entry in cac_muc:
        try:
            if not entry.is_file(follow_symlinks=False):
                continue
            stat = entry.stat(follow_symlinks=False)
        except OSError as e:
            ket_qua["loi"].append(f"{entry.path}: {e}")
            continue
        item = MucDem(
            path=entry.path,
            kich_thuoc=stat.st_size,
            lan_dung_cuoi=stat.st_mtime,
        )
        tat_ca.append(item)
        if entry.name.lower().endswith(_DUOI_DANG_TAI):
            continue
        if _dang_duoc_dung(thu_muc, entry.name, bo_dau_mo_coi=False):
            dang_dung.append(item)
        else:
            co_the_xoa.append(item)

    ket_qua["tong_file"] = len(tat_ca)
    ket_qua["tong_gb"] = (
        sum(item.kich_thuoc for item in tat_ca) / _BYTE_MOI_GB
    )
    ket_qua["bo_qua_dang_dung"] = len(dang_dung)
    ngan_sach = int(max_gb * _BYTE_MOI_GB)
    if ngan_sach > 0 and dang_dung:
        # Phần ngân sách còn lại cho file nhàn rỗi; file đang dùng một mình đã vượt thì bỏ mọi
        # file nhàn rỗi (``chon_can_xoa`` hiểu ngân sách <= 0 là «không giới hạn» nên giữ >= 1).
        ngan_sach = max(1, ngan_sach - sum(item.kich_thuoc for item in dang_dung))
    can_xoa = chon_can_xoa(
        co_the_xoa,
        ngan_sach,
        max_ngay * _GIAY_MOI_NGAY,
    )

    if not thuc_hien:
        ket_qua["xoa_file"] = len(can_xoa)
        ket_qua["xoa_gb"] = (
            sum(item.kich_thuoc for item in can_xoa) / _BYTE_MOI_GB
        )
        return ket_qua

    da_xoa_byte = 0
    for item in can_xoa:
        ten_file = os.path.basename(item.path)
        # Kiểm lại dấu và xoá DƯỚI khoá tải của mục: lượt quét nhận file đệm và đặt dấu dưới cùng
        # khoá này, nên không lọt vào giữa lần kiểm ở trên và lúc xoá.
        khoa = KhoaTienTrinh(duong_khoa_tai(thu_muc, ten_muc_dem(ten_file)),
                             f"Dọn kho đệm: {ten_file}")
        try:
            khoa.__enter__()
        except DangChayRoi:
            # Đang có lượt tải / nhận đúng mục này: để lần dọn sau.
            ket_qua["bo_qua_dang_dung"] += 1
            continue
        except OSError as e:
            ket_qua["loi"].append(f"{item.path}: {e}")
            continue
        try:
            if _dang_duoc_dung(thu_muc, ten_file, bo_dau_mo_coi=True):
                ket_qua["bo_qua_dang_dung"] += 1
                continue
            # Lựa chọn ở trên dựa trên ảnh chụp mtime lúc LIỆT KÊ. Lượt quét nhận lại bản đệm làm mới
            # mtime dưới cùng khoá này rồi nhả khoá, và chỉ đặt dấu sau khi đo xong độ dài file (có
            # thể hàng chục giây): file đổi kể từ lúc liệt kê = vừa được dùng/tải lại → không xoá
            # theo lựa chọn cũ, để lần dọn sau (audit WR-4).
            st = os.stat(item.path, follow_symlinks=False)
            if st.st_mtime != item.lan_dung_cuoi or st.st_size != item.kich_thuoc:
                ket_qua["bo_qua_dang_dung"] += 1
                continue
            os.remove(item.path)
        except OSError as e:
            ket_qua["loi"].append(f"{item.path}: {e}")
            continue
        finally:
            khoa.__exit__()
        ket_qua["xoa_file"] += 1
        da_xoa_byte += item.kich_thuoc
    ket_qua["xoa_gb"] = da_xoa_byte / _BYTE_MOI_GB
    return ket_qua


def _do_thu_muc(duong_dan: str) -> tuple:
    """Trả ``(tổng byte, mtime mới nhất, lỗi)`` của một thư mục job.

    Lấy mtime MỚI NHẤT trong các file con chứ không lấy mtime của chính thư mục:
    trên Windows, mtime thư mục chỉ đổi khi thêm/bớt mục trực tiếp bên trong, nên
    một lượt quét đang ghi liên tục vào ``chunks`` có thể để thư mục cha trông như
    đã cũ hàng giờ — đúng thứ khiến ta xoá nhầm job đang chạy.
    """
    tong = 0
    moi_nhat = 0.0
    loi = []
    for goc, _thu_muc_con, files in os.walk(duong_dan):
        for ten in files:
            duong = os.path.join(goc, ten)
            try:
                st = os.stat(duong)
            except OSError as e:
                loi.append(f"{duong}: {e}")
                continue
            tong += st.st_size
            moi_nhat = max(moi_nhat, st.st_mtime)
    if moi_nhat == 0.0:
        # Thư mục rỗng (hoặc không đọc được file nào) — dùng mtime của chính nó.
        try:
            moi_nhat = os.stat(duong_dan).st_mtime
        except OSError as e:
            loi.append(f"{duong_dan}: {e}")
    return tong, moi_nhat, loi


def don_job_quet(
    thu_muc: str,
    max_ngay: int = 7,
    thuc_hien: bool = True,
    bay_gio: Optional[float] = None,
) -> dict:
    """Xoá các thư mục job quét MỒ CÔI trong ``data/scan_jobs``.

    Bình thường không có gì để dọn: ``Engine._thu_muc_job()`` tạo thư mục trong một
    context manager có ``finally: shutil.rmtree(goc)``, nên quét xong là tự sạch.
    Thư mục còn sót lại chỉ sinh ra khi tiến trình CHẾT BẤT THƯỜNG — tắt máy, kill,
    hay crash. Mỗi thư mục như vậy giữ nguyên các chunk WAV đã giải mã, thực đo
    246 MB đến 3,2 GB một cái, và không bao giờ được dùng lại: tên thư mục là
    ``uuid.uuid4().hex`` nên mỗi lượt quét là một tên mới tinh.

    Trước bản này, ``don_kho_dem`` chỉ dọn kho đệm tải và bỏ qua hoàn toàn
    ``scan_jobs``, nên rác tích luỹ âm thầm cho tới khi đầy ổ.

    ``max_ngay <= 0`` nghĩa là KHÔNG có tiêu chí tuổi nên không xoá gì — giữ đúng
    quy ước của ``don_kho_dem``.

    Job ĐANG CHẠY được bảo vệ bằng cách tính tuổi theo file MỚI NHẤT bên trong
    (xem ``_do_thu_muc``): một lượt quét đang chạy ghi chunk liên tục nên tuổi của
    nó luôn tính bằng giây, không đời nào vượt ngưỡng tính bằng ngày.
    """
    ket_qua = {
        "tong_job": 0,
        "tong_gb": 0.0,
        "xoa_job": 0,
        "xoa_gb": 0.0,
        "bo_qua_dang_chay": 0,
        "loi": [],
    }
    if not os.path.isdir(thu_muc):
        return ket_qua

    try:
        cac_muc = list(os.scandir(thu_muc))
    except OSError as e:
        ket_qua["loi"].append(f"Không quét được thư mục job {thu_muc}: {e}")
        return ket_qua

    muc = []
    for entry in cac_muc:
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError as e:
            ket_qua["loi"].append(f"{entry.path}: {e}")
            continue
        tong, moi_nhat, loi = _do_thu_muc(entry.path)
        ket_qua["loi"].extend(loi)
        muc.append(MucDem(path=entry.path, kich_thuoc=tong, lan_dung_cuoi=moi_nhat))

    ket_qua["tong_job"] = len(muc)
    ket_qua["tong_gb"] = sum(x.kich_thuoc for x in muc) / _BYTE_MOI_GB

    gioi_han = max_ngay * _GIAY_MOI_NGAY
    if gioi_han <= 0:
        return ket_qua

    # Chỉ lọc theo TUỔI, không theo ngân sách dung lượng: xoá thư mục job mới nhất
    # chỉ vì tổng dung lượng vượt ngưỡng thì rất dễ trúng job đang chạy.
    can_xoa = chon_can_xoa(muc, 0, gioi_han, bay_gio)
    ket_qua["bo_qua_dang_chay"] = len(muc) - len(can_xoa)

    if not thuc_hien:
        ket_qua["xoa_job"] = len(can_xoa)
        ket_qua["xoa_gb"] = sum(x.kich_thuoc for x in can_xoa) / _BYTE_MOI_GB
        return ket_qua

    da_xoa_byte = 0
    for item in can_xoa:
        try:
            shutil.rmtree(item.path)
        except OSError as e:
            ket_qua["loi"].append(f"{item.path}: {e}")
            continue
        ket_qua["xoa_job"] += 1
        da_xoa_byte += item.kich_thuoc
    ket_qua["xoa_gb"] = da_xoa_byte / _BYTE_MOI_GB
    return ket_qua


# Rác tạm của job dựng kho / tải mà chỉ ``finally`` của chính job dọn — crash, kill, mất
# điện, đóng cửa sổ console bỏ qua ``finally`` nên phần còn sót không ai thu hồi (audit C-7).
THU_MUC_JOB_VAN_TAY = "fingerprint_jobs"   # mỗi job một thư mục: BẢN SAO cả kho + clips.txt
THU_MUC_TIEN_DO_TAI = "tien_do_tai"        # file -progress nhỏ của ffmpeg khi tải một phần


def don_rac_job_tam(
    data_dir: str,
    max_ngay: int = 7,
    thuc_hien: bool = True,
    bay_gio: Optional[float] = None,
) -> dict:
    """Thu hồi bản làm việc vân tay mồ côi (``data/fingerprint_jobs/<job>``) và file tiến độ
    tải mồ côi (``data/tien_do_tai/*``) đã quá ``max_ngay`` ngày.

    Cùng quy ước với ``don_job_quet``: chỉ lọc theo TUỔI (không theo dung lượng — dễ trúng job
    đang chạy), tuổi tính theo file MỚI NHẤT bên trong; ``max_ngay <= 0`` = không xoá gì. Job
    dựng kho đang chạy chạm ``clips.txt`` mỗi nhịp tim, ffmpeg ghi file tiến độ liên tục — nên
    việc đang chạy luôn «mới» tính bằng giây.
    """
    job = don_job_quet(
        os.path.join(data_dir, THU_MUC_JOB_VAN_TAY),
        max_ngay=max_ngay,
        thuc_hien=thuc_hien,
        bay_gio=bay_gio,
    )
    ket_qua = {
        "tong_muc": job["tong_job"],
        "tong_gb": job["tong_gb"],
        "xoa_muc": job["xoa_job"],
        "xoa_gb": job["xoa_gb"],
        "bo_qua_dang_chay": job["bo_qua_dang_chay"],
        "loi": list(job["loi"]),
    }

    thu_muc_td = os.path.join(data_dir, THU_MUC_TIEN_DO_TAI)
    gioi_han = max_ngay * _GIAY_MOI_NGAY
    if not os.path.isdir(thu_muc_td):
        return ket_qua
    try:
        cac_muc = list(os.scandir(thu_muc_td))
    except OSError as e:
        ket_qua["loi"].append(f"Không quét được {thu_muc_td}: {e}")
        return ket_qua
    muc = []
    for entry in cac_muc:
        try:
            if not entry.is_file(follow_symlinks=False):
                continue
            st = entry.stat(follow_symlinks=False)
        except OSError as e:
            ket_qua["loi"].append(f"{entry.path}: {e}")
            continue
        muc.append(MucDem(path=entry.path, kich_thuoc=st.st_size, lan_dung_cuoi=st.st_mtime))
    ket_qua["tong_muc"] += len(muc)
    ket_qua["tong_gb"] += sum(x.kich_thuoc for x in muc) / _BYTE_MOI_GB
    if gioi_han <= 0:
        return ket_qua

    can_xoa = chon_can_xoa(muc, 0, gioi_han, bay_gio)
    ket_qua["bo_qua_dang_chay"] += len(muc) - len(can_xoa)
    for item in can_xoa:
        if thuc_hien:
            try:
                os.remove(item.path)
            except OSError as e:
                ket_qua["loi"].append(f"{item.path}: {e}")
                continue
        ket_qua["xoa_muc"] += 1
        ket_qua["xoa_gb"] += item.kich_thuoc / _BYTE_MOI_GB
    return ket_qua
