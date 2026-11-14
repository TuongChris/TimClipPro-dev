# -*- coding: utf-8 -*-
"""Phản biện đo lường (14/11/2026) — TỰ TÍNH LẠI sự thật của bộ thử TỪ AUDIO, rồi so với su_that.json.

Không gọi engine, không gọi audfprint, không dùng tuong_dong.py (Cách C) hay danh_gia.py (bo_thu): phép đo phải độc
lập với mọi thứ đang được kiểm.

Hai cách đo, tuỳ kịch bản:
  * «mau_trung_khop» (bản sao NGUYÊN MẪU, he_so 1, không trộn): tìm mẫu int16 của clip trong video bằng bytes.find
    (64 mẫu một mẫu dò, mỗi 2 s), gom các độ lệch (delta), rồi so TỪNG MẪU clip[j] == video[j + delta] trên toàn clip
    → các đoạn trùng khớp tuyệt đối, mép chính xác tới 1 mẫu (45 µs). Không cần biết trước sự thật. Âm thanh lặp
    y hệt (S6b) sinh thêm các đoạn «bóng» (cùng âm thanh, khác giây clip) — báo riêng.
  * «tuong_quan» (Opus, nhạc đè, atempo): dùng sự thật làm GIẢ THUYẾT vị trí (±0,05 s), đo lại bằng tương quan chuẩn
    hoá dạng sóng: (a) độ lệch ánh xạ ở từng mốc bên trong đoạn (atempo: kiểm ánh xạ từng điểm, chưa ai kiểm),
    (b) mép đoạn bằng cửa sổ 0,1 s trượt 5 ms quanh mép, (c) dò toàn video (hạ mẫu ×4) xem còn chỗ nào khác chứa clip.

Chạy:  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B -X utf8 su_that_doc_lap.py [S1 S4 ...]
Ghi:   C:\\Dev\\pc2_test_runs\\2026-11-14_khop_tung_giay\\phan_bien_do_luong\\su_that_doc_lap.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import wave

import numpy as np
from scipy import signal

sys.dont_write_bytecode = True
SR = 22050
BO_THU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\bo_thu"
THEM = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\cach_c\them"
RA = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_do_luong"
THU_TU = ["S0", "S1", "S2", "S3", "S4", "S4b", "S5", "S5b", "S6", "S6b", "S7", "S7b", "S7c", "S8", "S9",
          "X1", "X2", "X3"]


def thu_muc(S: str, goc: dict | None = None) -> str:
    if goc and S in goc:
        return goc[S]
    return os.path.join(THEM if S.startswith("X") else BO_THU, S)


def doc_i16(path: str) -> np.ndarray | None:
    if not path.lower().endswith(".wav"):
        return None
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == SR, path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def doc_f(path: str) -> np.ndarray:
    """Mọi định dạng → float64 22050 Hz mono qua FFmpeg (như engine giải mã)."""
    i16 = doc_i16(path)
    if i16 is not None:
        return i16.astype(np.float64) / 32000.0
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", path, "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)


def chay_true(mask: np.ndarray) -> list:
    if not mask.any():
        return []
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


# ---------------------------------------------------------------- bản sao nguyên mẫu
def ban_sao_chinh_xac(c16: np.ndarray, v16: np.ndarray, buoc_s: float = 2.0, mau: int = 64,
                      toi_thieu_s: float = 0.5) -> list:
    vb = v16.tobytes()
    dem: dict = {}
    for j in range(0, len(c16) - mau, int(buoc_s * SR)):
        pat = c16[j:j + mau].tobytes()
        pos, n = vb.find(pat), 0
        while pos != -1 and n < 200:
            if pos % 2 == 0:
                dem[pos // 2 - j] = dem.get(pos // 2 - j, 0) + 1
            pos, n = vb.find(pat, pos + 1), n + 1
    doan = []
    for d, so in sorted(dem.items()):
        j0, j1 = max(0, -d), min(len(c16), len(v16) - d)
        if j1 <= j0:
            continue
        eq = c16[j0:j1] == v16[j0 + d:j1 + d]
        for a, b in chay_true(eq):
            if b - a >= toi_thieu_s * SR:
                doan.append({"video_tu": (j0 + a + d) / SR, "video_den": (j0 + b + d) / SR,
                             "clip_tu": (j0 + a) / SR, "clip_den": (j0 + b) / SR, "he_so": 1.0,
                             "delta_mau": int(d), "so_mau_do_trung": so})
    # đoạn «bóng»: nằm TRỌN trong (trục video) một đoạn dài hơn ở delta khác → cùng âm thanh, khác giây clip
    for x in doan:
        x["bong"] = any(y is not x and y["video_tu"] <= x["video_tu"] and x["video_den"] <= y["video_den"]
                        and (y["video_den"] - y["video_tu"]) > (x["video_den"] - x["video_tu"]) for y in doan)
    return doan


# ---------------------------------------------------------------- tương quan dạng sóng
def ncc_tim(cw: np.ndarray, v: np.ndarray, i_du: int, tim: int) -> tuple | None:
    """Đỉnh tương quan chuẩn hoá của ``cw`` quanh vị trí ``i_du`` (±``tim`` mẫu). Trả (lệch mẫu, ncc)."""
    m = len(cw)
    lo, hi = i_du - tim, i_du + tim + m
    if lo < 0 or hi > len(v):
        return None
    seg = v[lo:hi]
    a = cw - cw.mean()
    r = np.correlate(seg, a, "valid")
    c1 = np.concatenate([[0.0], np.cumsum(seg)])
    c2 = np.concatenate([[0.0], np.cumsum(seg * seg)])
    s1, s2 = c1[m:] - c1[:-m], c2[m:] - c2[:-m]
    nr = r / (np.sqrt(np.maximum(s2 - s1 * s1 / m, 1e-12)) * np.sqrt(a @ a) + 1e-12)
    j = int(np.argmax(nr))
    dj = 0.0
    if 0 < j < len(nr) - 1:
        mau = nr[j - 1] - 2 * nr[j] + nr[j + 1]
        if mau < 0:
            dj = 0.5 * (nr[j - 1] - nr[j + 1]) / mau
    return lo + j + dj - i_du, float(nr[j])


def ncc_co_dinh(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a - a.mean(), b - b.mean()
    return float(a @ b / (np.sqrt((a @ a) * (b @ b)) + 1e-12))


def kiem_doan_tuong_quan(c: np.ndarray, v: np.ndarray, d: dict, tron: bool = False) -> dict:
    """Đo lại một đoạn giả thuyết {video_tu, video_den, clip_tu, clip_den, he_so} bằng tương quan dạng sóng.
    ``tron``: video đã trộn nhạc đè → cửa sổ dài hơn (một nốt _giai_dieu là MỘT sin: cửa sổ ngắn có đỉnh tương quan
    lặp theo chu kỳ sin, nhiễu chọn nhầm đỉnh)."""
    k = d["he_so"]
    w_mep = 0.4 if tron else 0.1

    def t_video(ct: float) -> float:
        return d["video_tu"] + (ct - d["clip_tu"]) / k

    # (a) ánh xạ bên trong: cửa sổ ngắn khi có atempo (WSOLA chép từng khung, không co giãn dạng sóng); không
    # atempo thì 1,2 s (≥ 3 nốt khác tần số → một đỉnh duy nhất)
    w = 0.05 if k != 1.0 else 1.2
    lech, nccs, moc = [], [], []
    for ct in np.arange(d["clip_tu"] + 1.0, d["clip_den"] - 1.0, 2.0):
        cw = c[int(round(ct * SR)): int(round((ct + w) * SR))]
        kq = ncc_tim(cw, v, int(round(t_video(ct) * SR)), int(0.05 * SR))
        if kq:
            moc.append(round(float(ct), 2))
            lech.append(kq[0] / SR)
            nccs.append(kq[1])
    lech, nccs = np.array(lech), np.array(nccs)
    tot = nccs > 0.5 * np.median(nccs) if len(nccs) else np.array([], bool)
    trong = float(np.median(nccs)) if len(nccs) else 0.0
    ra = {"so_moc": int(len(lech)), "ncc_trung_vi": round(trong, 3),
          "lech_trung_vi_ms": round(1000 * float(np.median(lech[tot])), 2) if tot.any() else None,
          "lech_p5_ms": round(1000 * float(np.percentile(lech[tot], 5)), 2) if tot.any() else None,
          "lech_p95_ms": round(1000 * float(np.percentile(lech[tot], 95)), 2) if tot.any() else None,
          "lech_max_tuyet_doi_ms": round(1000 * float(np.max(np.abs(lech[tot]))), 2) if tot.any() else None}
    if k != 1.0 and tot.sum() >= 10:      # độ lệch có trôi theo giây clip không (atempo không tuyến tính?)
        p = np.polyfit(np.array(moc)[tot], lech[tot], 1)
        ra["lech_hoi_quy"] = {"doc_ms_moi_100s": round(1e5 * p[0], 3), "chan_ms": round(1000 * p[1], 3)}
        ra["lech_dau_10_moc_ms"] = [round(1000 * x, 2) for x in lech[:10]]
        ra["lech_cuoi_10_moc_ms"] = [round(1000 * x, 2) for x in lech[-10:]]
    off = float(np.median(lech[tot])) if tot.any() else 0.0

    # (b) mép: cửa sổ 0,1 s trượt 5 ms, ánh xạ cố định (+ độ lệch trung vị), tìm chỗ ncc cắt nửa mức trong đoạn
    def ncc_tai(ct: float) -> float:
        i_c, i_v = int(round(ct * SR)), int(round((t_video(ct) + off) * SR))
        n = int(w_mep * SR)
        if i_c < 0 or i_c + n > len(c) or i_v < 0 or i_v + n > len(v):
            return float("nan")
        if k != 1.0:                       # atempo: cho phép ±3 ms
            kq = ncc_tim(c[i_c:i_c + n], v, i_v, int(0.003 * SR))
            return kq[1] if kq else float("nan")
        return ncc_co_dinh(c[i_c:i_c + n], v[i_v:i_v + n])

    def mep(ct0: float, phia: str) -> float | None:
        luoi = np.arange(ct0 - 1.5, ct0 + 1.5, 0.005)
        x = np.array([ncc_tai(t) for t in luoi])
        if np.isnan(x).all():
            return None
        nguong = 0.5 * np.nanmedian(np.array([ncc_tai(t) for t in
                                              np.arange(d["clip_tu"] + 2, d["clip_den"] - 2, 7.3)]))
        tren = np.nan_to_num(x, nan=-1) >= nguong
        # mép đầu: ô đầu tiên mà 0,2 s kế tiếp ≥ 90 % ở trên ngưỡng; báo TÂM cửa sổ (nửa chồng lấn ≈ mép)
        if phia == "dau":
            for i in range(len(luoi)):
                if tren[i:i + 40].mean() > 0.9:
                    return float(luoi[i] + w_mep / 2)
        else:
            for i in range(len(luoi) - 1, -1, -1):
                if tren[max(0, i - 39):i + 1].mean() > 0.9:
                    return float(luoi[i] + w_mep / 2)
        return None

    m_dau, m_cuoi = mep(d["clip_tu"], "dau"), mep(d["clip_den"], "cuoi")
    ra["mep_clip_do_duoc"] = [None if m_dau is None else round(m_dau, 3), None if m_cuoi is None else round(m_cuoi, 3)]
    ra["mep_video_do_duoc"] = [None if m_dau is None else round(t_video(m_dau) + off, 3),
                               None if m_cuoi is None else round(t_video(m_cuoi) + off, 3)]
    ra["lech_mep_video_so_su_that_s"] = [None if m_dau is None else round(t_video(m_dau) + off - d["video_tu"], 3),
                                         None if m_cuoi is None else round(t_video(m_cuoi) + off - d["video_den"], 3)]
    return ra


def do_toan_video(c: np.ndarray, v: np.ndarray, gia_thuyet: list, so_mau_do: int = 6) -> dict:
    """Hạ mẫu ×4, tương quan 4 s của clip với TOÀN video; báo mọi đỉnh ncc ≥ 0,3 xa giả thuyết > 1 s."""
    cd = signal.decimate(c, 4, ftype="fir", zero_phase=True)
    vd = signal.decimate(v, 4, ftype="fir", zero_phase=True)
    sr4 = SR / 4
    m = int(4 * sr4)
    c1 = np.concatenate([[0.0], np.cumsum(vd)])
    c2 = np.concatenate([[0.0], np.cumsum(vd * vd)])
    s1, s2 = c1[m:] - c1[:-m], c2[m:] - c2[:-m]
    chuan_v = np.sqrt(np.maximum(s2 - s1 * s1 / m, 1e-12))
    la = []
    for ct in np.linspace(1.0, len(c) / SR - 5.0, so_mau_do):
        a = cd[int(ct * sr4): int(ct * sr4) + m]
        a = a - a.mean()
        r = signal.fftconvolve(vd, a[::-1], mode="valid") / (chuan_v * np.sqrt(a @ a) + 1e-12)
        dinh = signal.find_peaks(r, height=0.3, distance=int(sr4))[0]
        du = [g["video_tu"] + (ct - g["clip_tu"]) / g["he_so"] for g in gia_thuyet
              if g["clip_tu"] <= ct <= g["clip_den"]]
        for p in dinh:
            t = p / sr4
            if not du or min(abs(t - x) for x in du) > 1.0:
                la.append({"giay_clip": round(float(ct), 1), "giay_video": round(t, 2), "ncc": round(float(r[p]), 3)})
        if du:
            j = int(round(du[0] * sr4))
            vung = r[max(0, j - 50): j + 51]
            la_ok = float(vung.max()) if len(vung) else float("nan")
            la.append({"giay_clip": round(float(ct), 1), "dinh_tai_gia_thuyet_ncc": round(la_ok, 3)})
    return {"so_mau_do": so_mau_do, "ket_qua": la,
            "so_dinh_la_xa_gia_thuyet": sum(1 for x in la if "ncc" in x)}


# ---------------------------------------------------------------- mỗi kịch bản
def kiem_kich_ban(S: str, goc: dict | None = None) -> dict:
    d = thu_muc(S, goc)
    with open(os.path.join(d, "su_that.json"), encoding="utf-8") as f:
        st = json.load(f)
    t0 = time.perf_counter()
    v_path = os.path.join(d, st["video"])
    v16 = doc_i16(v_path)
    ra = {"kich_ban": S, "su_that_json": st["doan"], "clip": st["ten_clip"]}
    clips = sorted(os.listdir(os.path.join(d, "kho")))
    if S == "S0":                      # đối chứng âm: không clip nào được có bản sao
        ra["ban_sao_moi_clip"] = {}
        for ten in clips:
            c16 = doc_i16(os.path.join(d, "kho", ten))
            ra["ban_sao_moi_clip"][ten] = ban_sao_chinh_xac(c16, v16, buoc_s=5.0)
        ra["ket_luan"] = "khop" if not any(ra["ban_sao_moi_clip"].values()) else "LECH"
        ra["thoi_gian_s"] = round(time.perf_counter() - t0, 1)
        return ra
    c_path = os.path.join(d, "kho", st["ten_clip"])
    c16 = doc_i16(c_path)
    nguyen_mau = v16 is not None and all(x["he_so"] == 1.0 for x in st["doan"])
    if nguyen_mau:
        doan = ban_sao_chinh_xac(c16, v16)
        that = sorted([x for x in doan if not x["bong"]], key=lambda x: x["video_tu"])
        ra["cach"] = "mau_trung_khop"
        ra["doan_do_duoc"] = that
        ra["doan_bong_cung_am_thanh"] = [x for x in doan if x["bong"]]
        # so với su_that.json: cùng số đoạn, mép lệch (giây)
        sj = sorted(st["doan"], key=lambda x: x["video_tu"])
        if len(that) == len(sj):
            ra["lech_so_su_that_s"] = [{k: round(a[k] - b[k], 6) for k in ("video_tu", "video_den", "clip_tu",
                                                                              "clip_den")} for a, b in zip(that, sj)]
            ra["lech_lon_nhat_s"] = max(abs(x) for y in ra["lech_so_su_that_s"] for x in y.values())
            ra["ket_luan"] = "khop" if ra["lech_lon_nhat_s"] <= 1.0 / SR + 1e-9 else "LECH"
        else:
            ra["ket_luan"] = f"LECH: {len(that)} đoạn đo được, su_that.json có {len(sj)}"
        if v16 is not None and len(v16) > 0:
            ra["do_dai_video_s"] = round(len(v16) / SR, 6)
        if not doan:                       # WAV nhưng đã TRỘN (nhạc đè): không có mẫu trùng → đo bằng tương quan
            ra["ghi_chu_mau_trung"] = "0 đoạn nguyên mẫu (video đã trộn nhạc đè) — chuyển sang tương quan"
            nguyen_mau = False
    if not nguyen_mau:
        c = c16.astype(np.float64) / 32000.0
        v = doc_f(v_path)
        ra["cach"] = "tuong_quan"
        ra["do_dai_video_giai_ma_s"] = round(len(v) / SR, 4)
        tron = v16 is not None          # WAV mà không có mẫu trùng = đã trộn nhạc đè
        ra["kiem_doan"] = [kiem_doan_tuong_quan(c, v, x, tron=tron) for x in st["doan"]]
        ra["do_toan_video"] = do_toan_video(c, v, st["doan"])
        lech = [abs(y) for x in ra["kiem_doan"] for y in x["lech_mep_video_so_su_that_s"] if y is not None]
        ra["lech_mep_lon_nhat_s"] = max(lech) if lech else None
        # ±0,06 s: nốt _giai_dieu có bao Hanning (biên độ ~0 ở mép nốt) nên mép NĂNG LƯỢNG lệch vào trong ~0,045 s
        ra["ket_luan"] = ("khop (±0,06 s)" if lech and max(lech) <= 0.06
                          and ra["do_toan_video"]["so_dinh_la_xa_gia_thuyet"] == 0 else "XEM LAI")
    ra["thoi_gian_s"] = round(time.perf_counter() - t0, 1)
    return ra


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ds = sys.argv[1:] or THU_TU
    kq = {}
    for S in ds:
        r = kiem_kich_ban(S)
        kq[S] = r
        tom = {k: r.get(k) for k in ("cach", "ket_luan", "lech_lon_nhat_s", "lech_mep_lon_nhat_s", "thoi_gian_s")}
        if r.get("doan_bong_cung_am_thanh"):
            tom["so_doan_bong"] = len(r["doan_bong_cung_am_thanh"])
        if r.get("kiem_doan"):
            tom["anh_xa"] = [{k: x.get(k) for k in ("ncc_trung_vi", "lech_trung_vi_ms", "lech_p5_ms", "lech_p95_ms",
                                                     "lech_hoi_quy", "lech_mep_video_so_su_that_s")}
                             for x in r["kiem_doan"]]
            tom["dinh_la"] = r["do_toan_video"]["so_dinh_la_xa_gia_thuyet"]
        print(S, json.dumps(tom, ensure_ascii=False), flush=True)
    ten = "su_that_doc_lap.json" if not sys.argv[1:] else "su_that_doc_lap_mot_phan.json"
    with open(os.path.join(RA, ten), "w", encoding="utf-8") as f:
        json.dump(kq, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
