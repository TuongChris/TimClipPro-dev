# -*- coding: utf-8 -*-
"""Giữ bằng chứng khi dọn đệm audio (D-66 — người dùng chọn «chỉ giữ đoạn quanh mốc vi phạm» ngày 25/11).

Video có kết quả vi phạm trong lịch sử (bảng ``matches``) không bị xoá trắng audio khi dọn đệm: trước khi bỏ bản đệm
đầy đủ, ``giu_doan`` chép nguyên luồng tiếng (``-c copy``, không mã hoá lại) của các đoạn quanh mốc khớp — thêm
``DEM_GIAY`` mỗi bên — vào ``downloads/bang_chung/<mã video>/``, kèm sổ ``trich_doan.json`` ghi mốc của từng đoạn trên
video gốc. Đo 25/11 trên đệm DEV: 94,6 GB audio của video vi phạm còn khoảng 12,2 GB đoạn trích.

Đoạn trích nằm TRONG ``downloads/``: bộ đệm chỉ nhận ``downloads/<tên>.*`` và ``don_kho_dem`` không vào thư mục con,
nên đoạn trích không bao giờ bị lấy làm bản đệm hay bị dọn; sao lưu DEV bỏ qua cả ``downloads/`` như với đệm.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import lich_su
from luu_tru import day_xuong_dia
from process_runner import chay_lenh_media

THU_MUC_BANG_CHUNG = "bang_chung"
TEN_SO = "trich_doan.json"
DEM_GIAY = 60.0          # giữ thêm trước và sau mỗi đoạn khớp
DUNG_SAI_S = 1.0         # đoạn cắt ra ngắn hơn yêu cầu quá chừng này = hỏng
TRAN_CAT_S = 600         # một lệnh cắt chỉ chép gói, không giải mã: quá lâu thế này là FFmpeg treo
_DUOI_THEO_NGUON = {".mp4": ".m4a"}   # nguồn mp4 (client android có thể kèm hình) → đoạn chỉ có tiếng


class LoiTrichDoan(RuntimeError):
    """Không cắt / kiểm được đoạn trích — bên gọi GIỮ NGUYÊN bản đệm đầy đủ."""


class DaDungTrichDoan(RuntimeError):
    """Người dùng bấm Dừng giữa lúc cắt."""


@dataclass
class LichSuDem:
    doan: dict = field(default_factory=dict)        # mã video → [(bắt đầu, kết thúc)] giây trên video gốc
    da_quet: set = field(default_factory=set)       # mã video có trong lịch sử (mọi kết quả, kể cả lượt lỗi)
    thoi_luong: dict = field(default_factory=dict)  # mã video → thời lượng lớn nhất đã ghi (0 = không rõ)
    thong_tin: dict = field(default_factory=dict)   # mã video → (tiêu đề, link) của lượt quét gần nhất


def doc_lich_su(duong_db: str) -> LichSuDem:
    """Đọc CHỈ ĐỌC ``lichsu.db``. Chưa có file → lịch sử rỗng: mọi file đệm là «chưa rõ» và không bị dọn.
    DB có mà đọc lỗi → ném ``sqlite3.Error`` — bên gọi không được dọn theo một lịch sử đọc dở."""
    ls = LichSuDem()
    if not os.path.exists(duong_db):
        return ls
    con = lich_su._mo_chi_doc(duong_db)
    try:
        for ma, dai in con.execute("SELECT source_id, MAX(COALESCE(duration_s, 0)) FROM jobs"
                                   " WHERE COALESCE(source_id, '') != '' GROUP BY source_id"):
            ls.da_quet.add(ma)
            ls.thoi_luong[ma] = float(dai or 0)
        for ma, a, b in con.execute("SELECT j.source_id, m.start_s, m.end_s FROM matches m JOIN jobs j ON j.id = m.job_id"
                                    " WHERE COALESCE(j.source_id, '') != ''"
                                    " AND m.start_s IS NOT NULL AND m.end_s IS NOT NULL"):
            ls.doan.setdefault(ma, []).append((float(a), float(b)))
        for ma, ten, link in con.execute(
                "SELECT source_id, source_name, source_ref FROM jobs WHERE id IN"
                " (SELECT MAX(id) FROM jobs WHERE COALESCE(source_id, '') != '' GROUP BY source_id)"):
            ls.thong_tin[ma] = (ten or "", link or "")
    finally:
        con.close()
    return ls


def ma_video(ten_file: str, da_biet=()) -> str:
    """Mã video của file đệm ``<mã>.<đuôi>`` hay ``<mã>__p<giây>.<đuôi>`` (bản tải một phần — ``Engine._ten_phan_dau``).
    Mã có trong lịch sử thì nhận nguyên: mã YouTube hợp lệ cũng có thể chứa ``__p<số>``."""
    goc = ten_file.split(".", 1)[0]
    if goc in da_biet:
        return goc
    m = re.fullmatch(r"(.+)__p\d+", goc)
    return m.group(1) if m else goc


def gioi_han_ten(ten_file: str, da_biet=()) -> float:
    """Bản tải một phần ``<mã>__p<giây>`` chỉ chứa bấy nhiêu giây ĐẦU video; bản đầy đủ: vô hạn."""
    goc = ten_file.split(".", 1)[0]
    m = None if goc in da_biet else re.fullmatch(r".+__p(\d+)", goc)
    return float(m.group(1)) if m else math.inf


def gop_doan(doan, dem: float, tran: float = math.inf) -> list:
    """Nới mỗi đoạn ``dem`` giây hai bên, cắt trong [0, tran], gộp các đoạn chồng / chạm nhau."""
    ra: list = []
    for a, b in sorted((max(0.0, min(a, b) - dem), min(tran, max(a, b) + dem)) for a, b in doan):
        if b <= a:
            continue
        if ra and a <= ra[-1][1]:
            ra[-1][1] = max(ra[-1][1], b)
        else:
            ra.append([a, b])
    return [(a, b) for a, b in ra]


def uoc_giu_byte(ten_file: str, kich_thuoc: int, ls: LichSuDem, dem: float = DEM_GIAY) -> int:
    """Ước số byte đoạn trích sẽ giữ (xem trước, không cắt): tỉ lệ thời lượng giữ / thời lượng file. Không rõ thời
    lượng → cả file (ước lệch về phía giữ nhiều)."""
    ma = ma_video(ten_file, ls.da_quet)
    dai = min(gioi_han_ten(ten_file, ls.da_quet), ls.thoi_luong.get(ma) or math.inf)
    if not ls.doan.get(ma):
        return 0
    if not math.isfinite(dai) or dai <= 0:
        return kich_thuoc
    giu = sum(b - a for a, b in gop_doan(ls.doan[ma], dem, dai))
    return int(kich_thuoc * min(1.0, giu / dai))


def _hms(giay: float) -> str:
    g = int(giay)
    return f"{g // 3600:02d}h{g % 3600 // 60:02d}m{g % 60:02d}s"


def _do_dai(path: str) -> Optional[float]:
    from engine import Engine   # nạp muộn: engine nạp don_dep, don_dep nạp module này
    return Engine.do_dai_audio_that(path)


def _doc_so(thu_muc_video: str) -> dict:
    try:
        with open(os.path.join(thu_muc_video, TEN_SO), encoding="utf-8") as f:
            so = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise LoiTrichDoan(f"Sổ đoạn trích {os.path.join(thu_muc_video, TEN_SO)} hỏng hoặc không đọc được: {e}") from e
    if not isinstance(so, dict):
        raise LoiTrichDoan(f"Sổ đoạn trích {os.path.join(thu_muc_video, TEN_SO)} không đúng dạng.")
    return so


def _ghi_so(thu_muc_video: str, so: dict) -> None:
    """Ghi nguyên tử và BỀN (file tạm + fsync + đổi tên): bên gọi bỏ bản đầy đủ ngay sau đó — mất điện lúc dữ liệu còn
    trong bộ đệm của Windows thì lệnh xoá có thể còn mà sổ thành file rỗng / toàn số 0 (review 25/11). Một lượt dọn
    đệm tại một thời điểm (khoá chung ``don_dep``) nên không cần khoá riêng cho sổ."""
    duong = os.path.join(thu_muc_video, TEN_SO)
    tam = duong + ".tmp"
    with open(tam, "w", encoding="utf-8") as f:
        json.dump(so, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tam, duong)


def _da_co(so: dict, thu_muc_video: str, a: float, b: float) -> bool:
    """Một đoạn trích đã có (file còn trên đĩa) phủ trọn [a, b]."""
    return any(float(d.get("bat_dau_s", math.inf)) <= a + DUNG_SAI_S
               and float(d.get("ket_thuc_s", -math.inf)) >= b - DUNG_SAI_S
               and os.path.isfile(os.path.join(thu_muc_video, str(d.get("file", ""))))
               for d in so.get("doan", []) if isinstance(d, dict))


def cat_doan(nguon: str, a: float, b: float, dich: str, cancel_event=None) -> Optional[float]:
    """Chép luồng tiếng đầu tiên của ``nguon`` trong [a, b] (giây) ra ``dich`` — không mã hoá lại. Trả độ dài âm thanh
    thật của file ra (``None``: không đọc được). FFmpeg lỗi → ``LoiTrichDoan``; Dừng → ``DaDungTrichDoan``.

    ``-ss``/``-to`` đặt TRƯỚC ``-i`` (mốc trên file nguồn, nhảy theo chỉ mục — không phải đọc từ đầu file): điểm CUỐI dừng
    đúng ``b``; điểm ĐẦU là chỉ mục gần nhất ở TRƯỚC ``a`` — đo 25/11 bằng tương quan âm thanh trên file webm thật của
    YouTube: sớm 1,8 giây, cuối lệch 0,01 giây. Đoạn vì thế luôn phủ trọn [a, b]; ``giu_doan`` ghi mốc đầu thật."""
    r = chay_lenh_media(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                         "-i", nguon, "-map", "0:a:0", "-c", "copy", "-y", dich],
                        cancel_event=cancel_event, tran_tong_s=TRAN_CAT_S)
    if r.cancelled:
        raise DaDungTrichDoan("Đã dừng theo yêu cầu.")
    if r.returncode != 0 or r.timed_out or not os.path.isfile(dich):
        raise LoiTrichDoan(f"FFmpeg không cắt được đoạn {_hms(a)}–{_hms(b)}: {r.mo_ta_loi()}")
    return _do_dai(dich)


def giu_doan(thu_muc_dem: str, ten_file: str, ls: LichSuDem, dem: float = DEM_GIAY, cancel_event=None,
             luc: str = "") -> dict:
    """Cắt giữ các đoạn quanh mốc vi phạm của file đệm ``ten_file`` vào ``bang_chung/<mã video>/``.

    KHÔNG xoá bản đệm: ``don_dep.don_kho_dem`` xoá nó dưới khoá tải SAU khi hàm này trả về. Cửa sổ được cắt theo mốc
    hết âm thanh THẬT của nguồn (đo trước khi cắt); mọi đoạn phải cắt, kiểm độ dài và đẩy xuống đĩa; hỏng →
    ``LoiTrichDoan`` (đoạn đã cắt trong lần gọi này được gỡ, sổ không đổi) để bản đệm còn nguyên. Đoạn đã có (lần dọn
    trước, hay từ bản tải khác của cùng video) không cắt lại. Trả ``{"so_doan", "byte", "doan"}`` của các đoạn MỚI.
    """
    nguon = os.path.join(thu_muc_dem, ten_file)
    ma = ma_video(ten_file, ls.da_quet)
    thu_muc_video = os.path.join(thu_muc_dem, THU_MUC_BANG_CHUNG, ma)
    so = _doc_so(thu_muc_video)
    duoi = os.path.splitext(ten_file)[1]
    duoi = _DUOI_THEO_NGUON.get(duoi.lower(), duoi)
    moi: list = []
    tam = os.path.join(thu_muc_video, f".dang_cat{duoi}")
    try:
        cua_so = [(a, b) for a, b in gop_doan(ls.doan.get(ma, ()), dem, gioi_han_ten(ten_file, ls.da_quet))
                  if not _da_co(so, thu_muc_video, a, b)]
        # Mốc hết âm thanh THẬT (đọc gói, ~1 giây cho 3 giờ opus), đo TRƯỚC khi cắt: cửa sổ vượt cuối file mà không cắt
        # theo nó thì điểm đầu sớm (nhảy theo chỉ mục) che mất phần hụt ở cuối, sổ ghi lệch cả hai mốc (review 25/11).
        het_nguon = _do_dai(nguon) if cua_so else None
        if cua_so and het_nguon is None:
            raise LoiTrichDoan("không đọc được độ dài âm thanh của bản đệm")
        for a, b in cua_so:
            b = min(b, het_nguon)
            if b - a <= DUNG_SAI_S or _da_co(so, thu_muc_video, a, b):
                continue        # cửa sổ nằm sau chỗ âm thanh kết thúc / đoạn giữ tới cuối file đã có
            os.makedirs(thu_muc_video, exist_ok=True)
            dai = cat_doan(nguon, a, b, tam, cancel_event)
            if dai is None or dai < b - a - DUNG_SAI_S:
                raise LoiTrichDoan(f"đoạn {_hms(a)}–{_hms(b)} cắt ra chỉ được "
                                   f"{0 if dai is None else dai:.1f}/{b - a:.1f} giây")
            dau = max(0.0, b - dai)             # điểm cuối đúng mốc, điểm đầu sớm hơn (xem ``cat_doan``)
            day_xuong_dia(tam)                  # bền TRƯỚC khi công bố — bên gọi bỏ bản đầy đủ ngay sau đó
            dich = os.path.join(thu_muc_video, f"{ma}_{_hms(dau)}-{_hms(b)}{duoi}")
            os.replace(tam, dich)
            moi.append({"file": os.path.basename(dich), "bat_dau_s": round(dau, 3), "ket_thuc_s": round(b, 3),
                        "byte": os.path.getsize(dich), "tu_file": ten_file, "luc": luc})
        if moi:
            tieu_de, link = ls.thong_tin.get(ma, ("", ""))
            so.update({"ma_video": ma, "tieu_de": tieu_de, "link": link, "dem_giay": dem})
            so["doan"] = sorted([*[d for d in so.get("doan", []) if isinstance(d, dict)], *moi],
                                key=lambda d: float(d.get("bat_dau_s", 0)))
            _ghi_so(thu_muc_video, so)
    except BaseException:
        for d in moi:
            with contextlib.suppress(OSError):
                os.remove(os.path.join(thu_muc_video, d["file"]))
        raise
    finally:
        with contextlib.suppress(OSError):
            os.remove(tam)
    return {"so_doan": len(moi), "byte": sum(d["byte"] for d in moi), "doan": moi}
