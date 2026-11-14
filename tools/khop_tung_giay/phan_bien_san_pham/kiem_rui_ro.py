# -*- coding: utf-8 -*-
"""Kiểm rủi ro TÍCH HỢP «khớp từng giây» vào sản phẩm — chỉ import mã sản phẩm, không sửa file nào (14/11/2026).

P1 chữ ký chính sách nhận diện: trường Config mới NGOÀI TRUONG_CHINH_SACH không đổi chữ ký; thêm -Q vào thì đổi.
P2 bẫy ảnh chụp báo cáo V2: thêm TRƯỜNG vào BaoCaoV2 làm mọi ảnh chụp cũ thành «hỏng»; khoá phụ trong «doan» thì đọc được.
P3 bẫy tiêu đề Sheets nghiêm ngặt: thêm một cột vào HEADER/HEADER_NGANG làm mọi bảng đang dùng bị chặn gửi.
P4 hệ số tốc độ k: Match không mang k; suy k từ start_s/vung_khop_s/clip_offset_s sai ở ca kẹp mốc / kho video dài.
P5 dòng thời gian một lượt quét THẬT (FFmpeg + audfprint thật, audio giả lập của bộ thử S8): lúc có kết quả cuối
   (`_chon_loc`) khúc WAV còn không, dấu «đang dùng» file đệm còn không, file media còn không.

Chạy (Git Bash):
  cd /c/Dev/pc2_test_tools/khop_tung_giay/phan_bien_san_pham
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang PYTHONDONTWRITEBYTECODE=1 \
    C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe -B kiem_rui_ro.py
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import dataclasses  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import sqlite3  # noqa: E402
import time  # noqa: E402
from types import SimpleNamespace  # noqa: E402

MA = r"C:\Dev\Tool_Quet\TimClipPro"
BO_THU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"
RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_san_pham"

sc = sys.modules.get("sitecustomize")
if sc is None or "chan_mang" not in (getattr(sc, "__file__", "") or ""):
    raise SystemExit("Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang")
for bien in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_INSTALLATION_ID"):
    if os.environ.get(bien):
        raise SystemExit(f"Biến {bien} đang đặt — không chạy để khỏi đụng dữ liệu managed.")
sys.path.insert(0, MA)

import bao_cao_v2 as v2  # noqa: E402
import bang_ngang  # noqa: E402
import don_dep  # noqa: E402
import engine as eng_mod  # noqa: E402
import sheets  # noqa: E402
from engine import Config, Engine, Match, ScanResult, chu_ky_chinh_sach  # noqa: E402

ket: dict = {}
loi: list = []


def ky_vong(ten: str, dieu_kien: bool, chi_tiet=None) -> None:
    ket.setdefault("kiem", []).append({"ten": ten, "dat": bool(dieu_kien), "chi_tiet": chi_tiet})
    if not dieu_kien:
        loi.append(ten)


# ---------------- P1 ----------------
def p1() -> None:
    def tim(x):
        if isinstance(x, dict):
            if isinstance(x.get("chinh_sach"), str) and x["chinh_sach"].startswith("v1:"):
                return x["chinh_sach"]
            for v in x.values():
                r = tim(v)
                if r:
                    return r
        if isinstance(x, list):
            for v in x:
                r = tim(v)
                if r:
                    return r
        return None

    with open(os.path.join(MA, "tests", "golden", "file_ngan_top5.json"), encoding="utf-8") as f:
        golden_quet = tim(json.load(f))
    with open(os.path.join(MA, "tests", "golden", "bong_lap", "trich_giua.json"), encoding="utf-8") as f:
        golden = json.load(f)["chinh_sach_nhan_dien"]           # sinh bằng chu_ky_chinh_sach(Config())
    # Golden đường quét cũ dùng cấu hình thu nhỏ CAU_HINH_GOC (tests/golden_quet.py:58-65) — chữ ký nằm trong golden.
    c_goc = Config()
    for khoa, gia_tri in {"chunk_s": 200, "overlap_s": 60, "overlap_max_s": 60, "quet_tang_dan_tu_gio": 0.25,
                          "quet_tang_dan_buoc_gio": 0.2, "ncores": 1, "top_n": 5}.items():
        setattr(c_goc, khoa, gia_tri)
    ky_vong("P1 golden đường quét cũ chứa đúng chữ ký của cấu hình harness", chu_ky_chinh_sach(c_goc) == golden_quet,
            [chu_ky_chinh_sach(c_goc), golden_quet])
    hien = chu_ky_chinh_sach(Config())

    @dataclasses.dataclass
    class ConfigThem(Config):
        tinh_chinh_moc: bool = True

    them = chu_ky_chinh_sach(ConfigThem())
    cu = eng_mod.TRUONG_CHINH_SACH
    c = Config()
    c.time_quantile = 0.0
    try:
        eng_mod.TRUONG_CHINH_SACH = cu + ("time_quantile",)
        voi_q = chu_ky_chinh_sach(c)
    finally:
        eng_mod.TRUONG_CHINH_SACH = cu
    ket["P1"] = {"golden_bong_lap": golden, "golden_quet_cu_file_ngan_top5": golden_quet, "hien_tai": hien, "them_truong_ngoai_danh_sach": them, "them_Q_vao_danh_sach": voi_q,
                 "so_truong_chinh_sach": len(cu), "Q_co_trong_danh_sach": "time_quantile" in cu}
    ky_vong("P1 chữ ký hiện tại = golden", hien == golden, [hien, golden])
    ky_vong("P1 trường Config mới ngoài danh sách không đổi chữ ký", them == hien)
    ky_vong("P1 thêm -Q vào danh sách thì chữ ký đổi", voi_q != hien)


# ---------------- P2 ----------------
def _bao_cao_mau() -> "v2.BaoCaoV2":
    m = Match(clip="goc [aaaaaaaaaaa].opus", start_s=300.0, end_s=697.8, matched_s=374.6, clip_offset_s=23.2,
              hashes=10267, confidence="Rất chắc chắn", ty_le=61.7, vung="Giữa", clip_bat_dau_s=300.0,
              vung_khop_s=323.2)
    kq = ScanResult(source_name="Video thử", source_ref="https://www.youtube.com/watch?v=vidvipham01",
                    source_id="vidvipham01", duration_s=1080.0, matches=[m], so_dat_nguong=1)
    return v2.dung_bao_cao(kq, thoi_diem_quet="2026-11-14 10:00:00", nguon_loai="youtube", tieu_de="Video thử",
                           nguon_tieu_de=v2.NGUON_TIEU_DE_YTDLP, ly_do_thieu_tieu_de="",
                           ngay_dang=v2.NgayNguon(gia_tri="20261101", nguon=v2.NGUON_UPLOAD_DATE),
                           goc_theo_clip={}, mo_ta_pham_vi="")


def p2() -> None:
    bc = _bao_cao_mau()
    s = json.dumps(bc.to_dict(), ensure_ascii=False)
    r0 = v2.doc_anh_chup_da_luu("v2", s)
    o = dict(zip(bang_ngang.HEADER_NGANG, v2.dong_ngang(r0)))
    cu = v2._TRUONG_ANH_CHUP
    try:   # giả lập «thêm một trường vào dataclass BaoCaoV2» (tập khoá bắt buộc của bộ đọc lớn thêm)
        v2._TRUONG_ANH_CHUP = cu | {"tinh_chinh"}
        r1 = v2.doc_anh_chup_da_luu("v2", s)
    finally:
        v2._TRUONG_ANH_CHUP = cu
    d = json.loads(s)
    d["doan"][0]["moc_tinh_chinh"] = [300.0, 720.0]
    r2 = v2.doc_anh_chup_da_luu("v2", json.dumps(d, ensure_ascii=False))
    d = json.loads(s)
    d["phien_ban_anh_chup"] = 2
    r3 = v2.doc_anh_chup_da_luu("v2", json.dumps(d, ensure_ascii=False))
    r4 = v2.doc_anh_chup_da_luu("v3", s)
    ten = lambda r: type(r).__name__ + (f"({r.loai})" if v2.la_loi_bao_cao(r) else "")  # noqa: E731
    ket["P2"] = {"o_doan_1_hien_tai": o["Đoạn vi phạm 1 trong video vi phạm"],
                 "doc_anh_chup_cu": ten(r0), "them_truong_dataclass_roi_doc_anh_chup_cu": ten(r1),
                 "khoa_phu_trong_doan": ten(r2), "giay_ket_thuc_khi_co_khoa_phu": r2.doan[0].giay_ket_thuc,
                 "phien_ban_anh_chup_2_doc_bang_ban_hien_tai": ten(r3), "chinh_sach_v3_doc_bang_ban_hien_tai": ten(r4)}
    ky_vong("P2 ảnh chụp mẫu đọc được", isinstance(r0, v2.BaoCaoV2))
    ky_vong("P2 thêm trường BaoCaoV2 → ảnh chụp cũ thành hỏng", v2.la_loi_bao_cao(r1) and r1.loai == v2.LOI_HONG)
    ky_vong("P2 khoá phụ trong doan vẫn đọc được", isinstance(r2, v2.BaoCaoV2))
    ky_vong("P2 phiên bản ảnh chụp 2 → bản hiện tại chặn", v2.la_loi_bao_cao(r3))
    ky_vong("P2 chính sách v3 → bản hiện tại chặn", v2.la_loi_bao_cao(r4))


# ---------------- P3 ----------------
class _TabGia:
    def __init__(self, hang1):
        self.hang1 = hang1

    def get_values(self, _vung):
        return [list(self.hang1)]

    def get_all_values(self):
        return [list(self.hang1)]


def p3() -> None:
    ra = {}
    for ten, header in (("doc_16", list(Engine.HEADER)), ("ngang_34", list(bang_ngang.HEADER_NGANG))):
        tab = _TabGia(header)                       # bảng của người dùng: tiêu đề HIỆN HÀNH
        dung = sheets.kiem_tieu_de_nghiem_ngat(tab, header, "KetQuaQuet")
        try:
            sheets.kiem_tieu_de_nghiem_ngat(tab, header + ["Mốc tinh chỉnh"], "KetQuaQuet")
            them = "khong_chan"
        except sheets.LoiHeaderSheet as e:
            them = "LoiHeaderSheet: " + str(e)[:120]
        ra[ten] = {"so_cot": len(header), "tieu_de_hien_hanh": dung, "them_1_cot": them}
        ky_vong(f"P3 {ten}: tiêu đề hiện hành qua kiểm", dung is False)
        ky_vong(f"P3 {ten}: thêm 1 cột → bảng cũ bị chặn gửi", them.startswith("LoiHeaderSheet"))
    ket["P3"] = ra


# ---------------- P4 ----------------
def _k_cach_c(m) -> float:
    """Chép NGUYÊN logic `he_so_tu_engine` của Cách C (cach_c/tuong_dong.py:111) để soi ca biên."""
    off, d = float(m.clip_offset_s), float(m.vung_khop_s) - float(m.start_s)
    if off >= 30.0 and d > 0:
        k = off / d
        if 0.9 <= k <= 1.1:
            return k
    return 1.0


def p4(goc_tam: str) -> None:
    e = Engine(root=MA, data_dir=os.path.join(goc_tam, "data"), out_dir=os.path.join(goc_tam, "ketqua"))

    def manh(bat_dau, khop, t_clip, so_hash, he_so=1.0, clip="a.wav"):
        return {"clip": clip, "bat_dau": bat_dau, "khop": khop, "t_clip": t_clip, "hash": so_hash, "he_so": he_so,
                "align": bat_dau - he_so * t_clip}

    ca = {
        "binh_thuong_k1": ([manh(323.2, 374.6, 23.2, 10267)], 1.0),
        "kep_moc_dau_video_bat_dau_giua_clip": ([manh(300.0, 380.0, 303.0, 9000)], 1.0),
        "lượt_bù_tempo_k0.98048": ([manh(405.4, 278.6, 305.6, 3373, he_so=0.98048)], 1 / 0.98048),
        "clip_offset_0": ([manh(200.0, 52.4, 0.0, 1634)], 1.0),
    }
    ra = {}
    for ten, (tho, k_that_video) in ca.items():
        m = e._merge(tho)[0]
        ra[ten] = {"start_s": round(m.start_s, 3), "vung_khop_s": round(m.vung_khop_s, 3),
                   "clip_offset_s": round(m.clip_offset_s, 3), "k_that(video/clip)": round(k_that_video, 5),
                   "k_cach_c_suy_tu_Match": round(_k_cach_c(m), 5)}
    # Kho video dài (D-34): `_gan_chi_so` ghi đè start_s = clip_bat_dau_s = vung_khop_s (engine.py:4818-4820).
    m = e._merge([manh(5000.0, 300.0, 9000.0, 6000, he_so=0.98048)])[0]
    m.start_s = m.clip_bat_dau_s = m.vung_khop_s
    ra["kho_video_dai_D34_tempo"] = {"start_s": m.start_s, "vung_khop_s": m.vung_khop_s,
                                      "clip_offset_s": round(m.clip_offset_s, 3), "k_that(video/clip)": round(1 / 0.98048, 5),
                                      "k_cach_c_suy_tu_Match": _k_cach_c(m)}
    truong = [f.name for f in dataclasses.fields(Match)]
    ket["P4"] = {"truong_Match": truong, "ca": ra}
    ky_vong("P4 Match không có trường hệ số/họ biến đổi", not ({"he_so", "ho", "k"} & set(truong)), truong)
    ky_vong("P4 ca kẹp mốc: k suy từ Match SAI (≠ 1)",
            abs(ra["kep_moc_dau_video_bat_dau_giua_clip"]["k_cach_c_suy_tu_Match"] - 1.0) > 0.005,
            ra["kep_moc_dau_video_bat_dau_giua_clip"])
    ky_vong("P4 kho video dài + tempo: k suy từ Match rơi về 1,0",
            ra["kho_video_dai_D34_tempo"]["k_cach_c_suy_tu_Match"] == 1.0)


# ---------------- P5 ----------------
def p5(goc_tam: str) -> None:
    kho = os.path.join(goc_tam, "kho")
    os.makedirs(kho, exist_ok=True)
    shutil.copy2(os.path.join(BO_THU, "S8", "kho", "goc_S8.wav"), kho)
    e = Engine(root=MA, data_dir=os.path.join(goc_tam, "data"), out_dir=os.path.join(goc_tam, "ketqua"))
    e.config.ncores = 2
    e.add_kho("P5", kho)
    t0 = time.monotonic()
    e.build_database(kho, "new")
    t_dung = time.monotonic() - t0
    os.makedirs(e.dl_dir, exist_ok=True)
    media = os.path.join(e.dl_dir, "vidthu00001.wav")    # đặt trong kho đệm → _giu_file_dem có hiệu lực
    shutil.copy2(os.path.join(BO_THU, "S8", "video_vi_pham.wav"), media)
    ten_file = os.path.basename(media)
    nhat_ky: list = []

    def chup(diem: str, may: Engine) -> None:
        nhat_ky.append({
            "diem": diem,
            "khuc_wav_con": len(glob.glob(os.path.join(may.data_dir, "scan_jobs", "*", "chunks", "*.wav"))),
            "thu_muc_scan_jobs": len(glob.glob(os.path.join(may.data_dir, "scan_jobs", "*"))),
            "dau_dang_dung": len(glob.glob(os.path.join(may.data_dir, don_dep.THU_MUC_DANG_DUNG, "*.lock"))),
            "file_media_con": os.path.exists(media),
            "don_dem_se_coi_la_dang_dung": don_dep._dang_duoc_dung(may.dl_dir, ten_file, bo_dau_mo_coi=False),
        })

    goc_merge, goc_chon, goc_luu = Engine._merge, Engine._chon_loc, Engine.save_job

    def merge_ghi(self, tho):
        chup("_merge", self)
        return goc_merge(self, tho)

    def chon_ghi(self, ds, duration):
        chup("_chon_loc (kết quả cuối đã biết)", self)
        return goc_chon(self, ds, duration)

    def luu_ghi(self, kq, source_type):
        chup("save_job", self)
        return goc_luu(self, kq, source_type)

    Engine._merge, Engine._chon_loc, Engine.save_job = merge_ghi, chon_ghi, luu_ghi
    try:
        t0 = time.monotonic()
        kq = e.scan_media(media)
        t_quet = time.monotonic() - t0
    finally:
        Engine._merge, Engine._chon_loc, Engine.save_job = goc_merge, goc_chon, goc_luu
    chup("sau scan_media", e)
    with sqlite3.connect(e.sqlite_file) as c:
        cot_matches = [r[1] for r in c.execute("PRAGMA table_info(matches)")]
        co_bao_cao = c.execute("SELECT COUNT(*) FROM bao_cao_job").fetchone()[0]
    m = kq.matches[0] if kq.matches else None
    ket["P5"] = {
        "thoi_gian_dung_kho_s": round(t_dung, 1), "thoi_gian_quet_s": round(t_quet, 1), "status": kq.status,
        "matches": [{"start_s": x.start_s, "vung_khop_s": x.vung_khop_s, "end_s": x.end_s, "clip_offset_s": x.clip_offset_s,
                     "hashes": x.hashes, "duong_dan_kho_ton_tai": os.path.exists(x.duong_dan_kho)} for x in kq.matches],
        "nhat_ky": nhat_ky, "cot_bang_matches": cot_matches, "so_dong_bao_cao_job": co_bao_cao,
        "bao_cao_la_v2": isinstance(kq.bao_cao, v2.BaoCaoV2),
    }
    cuoi = [x for x in nhat_ky if x["diem"].startswith("_chon_loc")]
    ky_vong("P5 lượt quét ra đúng 1 dòng", kq.status == "ok" and len(kq.matches) == 1)
    ky_vong("P5 lúc có kết quả cuối: khúc WAV đã bị xoá", bool(cuoi) and cuoi[-1]["khuc_wav_con"] == 0, cuoi)
    ky_vong("P5 lúc có kết quả cuối: dấu đang dùng file đệm đã nhả", bool(cuoi) and cuoi[-1]["dau_dang_dung"] == 0)
    ky_vong("P5 lúc có kết quả cuối: file media vẫn còn", bool(cuoi) and cuoi[-1]["file_media_con"])
    ky_vong("P5 có lần _merge chạy khi khúc WAV còn (dừng sớm/kiểm bù)",
            any(x["diem"] == "_merge" and x["khuc_wav_con"] > 0 for x in nhat_ky))
    ky_vong("P5 bảng matches không lưu vung_khop_s / đường dẫn kho / hệ số",
            not ({"vung_khop_s", "duong_dan_kho", "he_so"} & set(cot_matches)), cot_matches)
    ky_vong("P5 Match.duong_dan_kho trỏ tới file clip còn trên đĩa", bool(m) and os.path.exists(m.duong_dan_kho))


if __name__ == "__main__":
    goc = os.path.join(RA, "_tam")
    shutil.rmtree(goc, ignore_errors=True)
    os.makedirs(goc)
    p1()
    p2()
    p3()
    p4(os.path.join(goc, "p4"))
    p5(os.path.join(goc, "p5"))
    ket["loi"] = loi
    with open(os.path.join(RA, "kiem_rui_ro.json"), "w", encoding="utf-8") as f:
        json.dump(ket, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: v for k, v in ket.items() if k != "kiem"}, ensure_ascii=False, indent=1, default=str)[:6000])
    print(f"KIỂM: {sum(x['dat'] for x in ket['kiem'])}/{len(ket['kiem'])} đạt; lỗi: {loi}")
    sys.exit(1 if loi else 0)
