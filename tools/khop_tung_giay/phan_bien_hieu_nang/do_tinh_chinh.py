# -*- coding: utf-8 -*-
"""Phản biện HIỆU NĂNG (14/11/2026): đo thời gian + RAM của bước tinh chỉnh Cách C (cach_c/tuong_dong.py) trên audio
giả lập DÀI. Chỉ import tuong_dong (không sửa), không gọi engine, không đụng mã sản phẩm.

Ba biến thể, CÙNG thuật toán tinh_chinh:
  V0  nguyên bản như cach_c/chay_cach_c.py: giải mã CẢ clip + đoạn video dài bằng cả clip (biên 2 + 4,5%·L + 42 s).
  V1  cửa sổ: chỉ giải mã clip[lõi engine ± (30 s + 10%)] và đoạn video tương ứng (± 2 + 4,5%·cửa sổ + 42 s).
      Đoạn tìm được chạm mép cửa sổ (không phải mép clip thật) → nới đệm ×3, làm lại MỘT lần.
  V2  như V1 nhưng đoạn video ĐỌC từ khúc WAV mono 11025 Hz engine đã cắt (chunk_<giây>.wav) thay vì FFmpeg giải mã.
  V1t như V1 nhưng giải mã DÒNG CHẢY + log-mel float32 (không giữ cả PCM): kiểm xem RAM chặn được không.
Mỗi lần đo một kết quả chạy trong TIẾN TRÌNH RIÊNG (đỉnh RAM = peak working set / peak commit của chính nó).

  mot  --video V --clip C --match JSON --bien-the V0|V1|V2 [--khuc DIR] [--su-that JSON]   (in JSON một dòng)
  lo   <thư mục quét> [--tat-ca-dat] [--bien-the V0,V1,V2]   — mọi kết quả của một lượt quét engine (chay_engine.py)
  cuon <thư mục quét>                                           — kho 16 bit: thử neo off + j·1521,8 s
  thang-do                                                      — clip 10/30/60/119 phút dùng trọn + 5 phút giữa clip 2 giờ
  tu-kiem                                                       — kiểm đọc khúc WAV ≡ FFmpeg, V1 ≡ V0 trên ca nhỏ
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
for _bien in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_bien, "2")        # như tuong_dong, nhưng TRƯỚC khi numpy nạp OpenBLAS
import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import wave  # noqa: E402

import numpy as np  # noqa: E402
import psutil  # noqa: E402

THU_MUC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(THU_MUC), "cach_c"))
sys.path.insert(0, os.path.join(os.path.dirname(THU_MUC), "bo_thu"))
import danh_gia  # noqa: E402  (hàm thuần: hop/giao/do_dai/precision_recall)
import tuong_dong as td  # noqa: E402

GOC = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_hieu_nang"
DU_LIEU = os.path.join(GOC, "du_lieu")
PY = sys.executable
RE_KHUC = re.compile(r"chunk_(\d{7})\.wav")


def _mb(x: int) -> float:
    return round(x / 2**20, 1)


def _bo_nho() -> dict:
    mi = psutil.Process().memory_info()
    return {"peak_wset_mb": _mb(getattr(mi, "peak_wset", mi.rss)), "peak_commit_mb": _mb(getattr(mi, "peak_pagefile", 0)),
            "rss_mb": _mb(mi.rss)}


def ffprobe_dai(p: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def doc_khuc(khuc_dir: str, tu: float, dai: float) -> tuple:
    """Đoạn [tu, tu+dai) mono float32 11025 Hz ghép từ các khúc WAV gối nhau của engine (mốc khúc = giây trong tên)."""
    a = int(round(max(0.0, tu) * td.SR))
    b = a + int(round(dai * td.SR))
    ra, pos = [], a
    for ten in sorted(os.listdir(khuc_dir)):
        mk = RE_KHUC.fullmatch(ten)
        if not mk or pos >= b:
            continue
        s0 = int(mk.group(1)) * td.SR
        with wave.open(os.path.join(khuc_dir, ten), "rb") as w:
            assert w.getframerate() == td.SR and w.getnchannels() == 1 and w.getsampwidth() == 2, ten
            s1 = s0 + w.getnframes()
            if s1 <= pos or s0 > pos:
                continue                      # khúc không chứa mẫu kế tiếp (khúc gối: khúc sau bắt đầu trước s1)
            hi = min(b, s1)
            w.setpos(pos - s0)
            ra.append(np.frombuffer(w.readframes(hi - pos), dtype="<i2").astype(np.float32) / 32768.0)
            pos = hi
    return (np.concatenate(ra) if ra else np.zeros(0, np.float32)), a / td.SR


def log_mel_dong(duong: str, tu: float, dai: float) -> tuple:
    """V1t: FFmpeg → log-mel float32 KHÔNG giữ cả PCM (đọc ống từng khối, giữ phần đuôi N_FFT − HOP mẫu). Cùng bộ lọc,
    cửa sổ, bước như td.log_mel; sàn = p99 trên mẫu thưa (1/8 khung) — khác td.log_mel không đáng kể (tự kiểm)."""
    tu = max(0.0, round(tu * td.SR) / td.SR)
    lenh = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"] + (["-ss", f"{tu:.6f}"] if tu > 0 else []) +         ["-i", duong, "-t", f"{dai:.6f}", "-map", "0:a:0", "-ac", "1", "-ar", str(td.SR), "-f", "f32le", "-"]
    tran = 1 + int(dai * td.SR) // td.HOP + 2
    ra = np.empty((tran, td.N_MEL), dtype=np.float32)
    fb, cs = td._FB.T.astype(np.float32), td._CUA_SO.astype(np.float32)
    du, n_khung, n_mau = np.zeros(0, np.float32), 0, 0
    p = subprocess.Popen(lenh, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        while True:
            b = p.stdout.read(4 * td.HOP * 4096)
            if not b:
                break
            x = np.concatenate([du, np.frombuffer(b, np.float32)])
            n_mau += len(b) // 4
            n = 1 + (len(x) - td.N_FFT) // td.HOP if len(x) >= td.N_FFT else 0
            if n:
                k = np.lib.stride_tricks.sliding_window_view(x, td.N_FFT)[::td.HOP][:n]
                ra[n_khung:n_khung + n] = (np.abs(np.fft.rfft(k * cs, axis=1)) ** 2).astype(np.float32) @ fb
                n_khung += n
                du = x[n * td.HOP:]
            else:
                du = x
        loi = p.stderr.read()
    finally:
        p.stdout.close()
        p.stderr.close()
        p.wait(timeout=60)
    if p.returncode != 0:
        raise RuntimeError(f"FFmpeg lỗi với {duong}: {loi.decode('utf-8', 'replace')[-300:]}")
    ra = ra[:n_khung]
    if n_khung:
        san = max(float(np.percentile(ra[::8], 99)) * 10 ** (td.SAN_DB / 10), 1e-20)
        np.maximum(ra, san, out=ra)
        np.log10(ra, out=ra)
    return ra, tu, n_mau


def cua_so_clip(m: dict, L: float, k0: float, he_so_dem: float = 1.0) -> tuple:
    c_a = float(m["clip_offset_s"])
    c_b = c_a + (float(m["end_s"]) - float(m["vung_khop_s"])) * k0
    dem = he_so_dem * (30.0 + 0.10 * max(0.0, c_b - c_a))
    return max(0.0, c_a - dem), min(L, c_b + dem)


def cua_so_video(m: dict, c0: float, c1: float, k0: float, dur: float) -> tuple:
    t = lambda c: float(m["vung_khop_s"]) + (c - float(m["clip_offset_s"])) / k0  # noqa: E731
    bien = 2.0 + 0.045 * (c1 - c0) + td.BIEN_NEN_S
    tu = max(0.0, t(c0) - bien)
    return tu, min(dur, t(c1) + bien) - tu


def vung_video_v0(m: dict, L: float, dur: float) -> tuple:
    """Y hệt chay_cach_c.vung_video (biên theo độ dài CẢ clip)."""
    k0 = td.he_so_tu_engine(m)
    t0 = float(m["vung_khop_s"]) - float(m["clip_offset_s"]) / k0
    bien = 2.0 + 0.045 * L + td.BIEN_NEN_S
    tu = max(0.0, t0 - bien)
    return tu, min(dur, t0 + L / k0 + bien) - tu


def _tinh_chinh_lech(C, V, T0, L_cs, m, c0, k0, dur) -> dict:
    """tinh_chinh trên clip CẮT từ giây c0: neo dời về toạ độ cửa sổ, k0 giữ theo kết quả gốc, kết quả dời lại."""
    m2 = dict(m, clip_offset_s=float(m["clip_offset_s"]) - c0)
    goc = td.he_so_tu_engine
    # shortcut: tinh_chinh đọc k0 qua hàm toàn cục của tuong_dong — công cụ đo thay tạm; tích hợp thật thì truyền k0 vào.
    td.he_so_tu_engine = lambda _m: k0
    try:
        kq = td.tinh_chinh(C, V, T0, L_cs, m2, video_den=dur)
    finally:
        td.he_so_tu_engine = goc
    for d in kq["doan"]:
        d["clip_tu"] = round(d["clip_tu"] + c0, 3)
        d["clip_den"] = round(d["clip_den"] + c0, 3)
        if d["moc_giay0_clip_tren_video"] is not None:
            d["moc_giay0_clip_tren_video"] = round(d["moc_giay0_clip_tren_video"] - c0 / d["k_uoc_luong"], 3)
    return kq


def mot(video: str, clip: str, m: dict, bien_the: str, khuc: str | None) -> dict:
    tg: dict = {}
    nho0 = _bo_nho()
    L = ffprobe_dai(clip)
    dur = ffprobe_dai(video)
    k0 = td.he_so_tu_engine(m)
    ra = {"bien_the": bien_the, "L_clip_s": round(L, 3), "k0": round(k0, 5), "mo_rong": 0}
    t = time.perf_counter()
    if bien_the == "V0":
        xc, _ = td.doc_pcm(clip)
        c0, c1 = 0.0, L
        tg["giai_ma_clip_s"] = time.perf_counter() - t
        t = time.perf_counter()
        C = td.log_mel(xc)
        L_cs = len(xc) / td.SR
        del xc
        tg["dac_trung_clip_s"] = time.perf_counter() - t
        tu, dai = vung_video_v0(m, L, dur)
        t = time.perf_counter()
        xv, T0 = td.doc_pcm(video, tu, dai)
        tg["giai_ma_video_s"] = time.perf_counter() - t
        t = time.perf_counter()
        V = td.log_mel(xv)
        n_video = len(xv)
        del xv
        tg["dac_trung_video_s"] = time.perf_counter() - t
        t = time.perf_counter()
        kq = td.tinh_chinh(C, V, T0, L_cs, m, video_den=dur)
        tg["tinh_chinh_s"] = time.perf_counter() - t
    else:
        he_so_dem = 1.0
        while True:
            c0, c1 = cua_so_clip(m, L, k0, he_so_dem)
            if bien_the == "V1t":              # giải mã + đặc trưng liền một bước (dòng chảy, float32)
                t = time.perf_counter()
                C, c0, n_c = log_mel_dong(clip, c0, c1 - c0)
                L_cs = n_c / td.SR
                tg["giai_ma_va_dac_trung_clip_s"] = tg.get("giai_ma_va_dac_trung_clip_s", 0.0) + time.perf_counter() - t
                tu, dai = cua_so_video(m, c0, c0 + L_cs, k0, dur)
                t = time.perf_counter()
                V, T0, n_video = log_mel_dong(video, tu, dai)
                tg["giai_ma_va_dac_trung_video_s"] = (tg.get("giai_ma_va_dac_trung_video_s", 0.0)
                                                      + time.perf_counter() - t)
            else:
                t = time.perf_counter()
                xc, c0 = td.doc_pcm(clip, c0, c1 - c0)
                tg["giai_ma_clip_s"] = tg.get("giai_ma_clip_s", 0.0) + time.perf_counter() - t
                t = time.perf_counter()
                C = td.log_mel(xc)
                L_cs = len(xc) / td.SR
                del xc
                tg["dac_trung_clip_s"] = tg.get("dac_trung_clip_s", 0.0) + time.perf_counter() - t
                tu, dai = cua_so_video(m, c0, c0 + L_cs, k0, dur)
                t = time.perf_counter()
                xv, T0 = doc_khuc(khuc, tu, dai) if bien_the == "V2" else td.doc_pcm(video, tu, dai)
                tg["giai_ma_video_s"] = tg.get("giai_ma_video_s", 0.0) + time.perf_counter() - t
                t = time.perf_counter()
                V = td.log_mel(xv)
                n_video = len(xv)
                del xv
                tg["dac_trung_video_s"] = tg.get("dac_trung_video_s", 0.0) + time.perf_counter() - t
            t = time.perf_counter()
            kq = _tinh_chinh_lech(C, V, T0, L_cs, m, c0, k0, dur)
            tg["tinh_chinh_s"] = tg.get("tinh_chinh_s", 0.0) + time.perf_counter() - t
            cham = any((d["cach_tim_mep"][0] == "dau_clip" and c0 > 0.05)
                       or (d["cach_tim_mep"][1] == "cuoi_clip" and c0 + L_cs < L - 0.05) for d in kq["doan"])
            if not cham or ra["mo_rong"] >= 1:
                ra["cham_mep_cua_so_sau_cung"] = bool(cham)
                break
            ra["mo_rong"] += 1
            he_so_dem = 3.0
    tg = {k: round(v, 3) for k, v in tg.items()}
    tg["tong_s"] = round(sum(tg.values()), 3)
    ra.update({"thoi_gian": tg, "cpu_s": round(sum(psutil.Process().cpu_times()[:2]), 2),
               "cua_so_clip_s": [round(c0, 3), round(c0 + L_cs, 3)], "giay_clip_xu_ly": round(L_cs, 1),
               "giay_video_xu_ly": round(n_video / td.SR, 1), "cua_so_video_tu": round(T0, 3),
               "bo_nho_truoc": nho0, "bo_nho_sau": _bo_nho(),
               "C_mb": _mb(C.nbytes), "V_mb": _mb(V.nbytes),
               "tuong_phan_thap": kq["tuong_phan_thap"], "so_giay_bam": kq["so_giay_bam"],
               "muc_trong": kq["muc_trong"], "nguong_dung": kq["nguong_dung"],
               "doan": [{k: d[k] for k in ("video_tu", "video_den", "clip_tu", "clip_den", "cach_tim_mep",
                                           "tuong_dong_tb", "k_uoc_luong", "moc_giay0_clip_tren_video")}
                        for d in kq["doan"]]})
    return ra


def cham_diem(ra: dict, su_that: dict, clip_ten: str, m: dict) -> dict:
    """Sai mép so với đoạn thật cùng clip gần nhất; P/R theo giây trong vùng lõi engine nới ±60 s."""
    that = [d for d in su_that["doan"] if d["clip"] == clip_ten]
    lo, hi = float(m["vung_khop_s"]) - 60, float(m["end_s"]) + 60
    that_vung = danh_gia.giao([(d["video_tu"], d["video_den"]) for d in that], [(lo, hi)])
    bao = [(d["video_tu"], d["video_den"]) for d in ra["doan"]]
    kq = {"that_trong_vung": that_vung, "precision_giay": None, "recall_giay": None, "loi_mep": []}
    if bao and that_vung:
        kq["precision_giay"], kq["recall_giay"] = danh_gia.precision_recall(bao, that_vung)
    for d in ra["doan"]:
        gan = max(that, key=lambda x: danh_gia.do_dai(danh_gia.giao([(d["video_tu"], d["video_den"])],
                                                                    [(x["video_tu"], x["video_den"])])), default=None)
        if gan:
            kq["loi_mep"].append([round(d["video_tu"] - gan["video_tu"], 3), round(d["video_den"] - gan["video_den"], 3)])
    return kq


def _chay_con(video, clip, m, bien_the, khuc=None) -> dict:
    lenh = [PY, "-B", "-X", "utf8", os.path.abspath(__file__), "mot", "--video", video, "--clip", clip,
            "--match", json.dumps(m), "--bien-the", bien_the] + (["--khuc", khuc] if khuc else [])
    t = time.perf_counter()
    r = subprocess.run(lenh, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    if r.returncode != 0:
        return {"bien_the": bien_the, "loi": r.stderr[-1500:]}
    ra = json.loads(r.stdout.strip().splitlines()[-1])
    ra["wall_ca_tien_trinh_s"] = round(time.perf_counter() - t, 2)
    return ra


def _match_gon(m: dict) -> dict:
    return {k: m[k] for k in ("clip", "start_s", "vung_khop_s", "end_s", "clip_offset_s", "matched_s", "hashes",
                              "duong_dan_kho", "moc_mo_ho") if k in m}


def lo(thu_muc: str, tat_ca_dat: bool, bien_the: list) -> None:
    with open(os.path.join(thu_muc, "ket_qua.json"), encoding="utf-8") as f:
        ket = json.load(f)
    with open(os.path.join(DU_LIEU, f"su_that_{ket['video']}.json"), encoding="utf-8") as f:
        su_that = json.load(f)
    video = os.path.join(DU_LIEU, f"video_{ket['video']}.webm")
    nguon = ket["ung_vien_dat"] if tat_ca_dat else ket["matches"]
    chon = {(m["clip"], m["start_s"], m["vung_khop_s"]) for m in ket["matches"]}
    ra = {"thu_muc": thu_muc, "tap": "ung_vien_dat" if tat_ca_dat else "matches", "so_ket_qua": len(nguon),
          "thoi_gian_quet_engine_s": ket["thoi_gian_quet_s"], "ket_qua": []}
    for i, m in enumerate(nguon):
        thu_muc_kho = {"thuong": "kho", "dai": "kho_dai", "w40": "kho_w40"}[ket["kho"]]
        clip = m["duong_dan_kho"] if os.path.isfile(m["duong_dan_kho"]) else os.path.join(DU_LIEU, thu_muc_kho, m["clip"])
        mg = _match_gon(m)
        dong = {"i": i, "match": mg, "trong_top_n": (m["clip"], m["start_s"], m["vung_khop_s"]) in chon, "do": {}}
        for bt in bien_the:
            r = _chay_con(video, clip, mg, bt, os.path.join(thu_muc, "khuc"))
            if "loi" not in r:
                r["cham_diem"] = cham_diem(r, su_that, m["clip"], m)
            dong["do"][bt] = r
            tt = r.get("thoi_gian", {})
            print(f"[{i}] {m['clip']} vung {m['vung_khop_s']}..{m['end_s']} off {m['clip_offset_s']} {bt}: "
                  f"{tt.get('tong_s')} s, đỉnh {r.get('bo_nho_sau', {}).get('peak_commit_mb')} MB, "
                  f"đoạn {[(d['video_tu'], d['video_den']) for d in r.get('doan', [])]} "
                  f"lỗi mép {r.get('cham_diem', {}).get('loi_mep')} {r.get('loi', '')[-300:]}", flush=True)
        ra["ket_qua"].append(dong)
    ten = "tinh_chinh_" + ("ung_vien_dat" if tat_ca_dat else "matches") + ".json"
    with open(os.path.join(thu_muc, ten), "w", encoding="utf-8") as f:
        json.dump(ra, f, ensure_ascii=False, indent=1)


def thang_do(bien_the: list) -> None:
    """Clip = L giây đầu của goc_2h (cắt sẵn, -c copy); video_B có goc_2h trọn ở 1800 s → đoạn thật [1800, 1800+L].
    Kết quả engine giả như tự kiểm của tuong_dong: lõi cắt 5% hai đầu, k = 1. Thêm ca «5 phút giữa clip 2 giờ»."""
    d = os.path.join(GOC, "thang_do")
    os.makedirs(d, exist_ok=True)
    video = os.path.join(DU_LIEU, "video_B.webm")
    goc = os.path.join(DU_LIEU, "kho_dai", "goc_2h.opus")
    khuc = os.path.join(GOC, "khuc_B")   # cắt bằng đúng lệnh FFmpeg của _cut_chunks
    ca = []
    for L in (600, 1800, 3600, 7140):
        clip = goc if L == 7140 else os.path.join(d, f"goc_dau_{L}.opus")
        if not os.path.exists(clip):
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", goc, "-t", str(L), "-c", "copy",
                            clip], check=True)
        ca.append((f"tron_{L}s", clip, {"start_s": 1800.0, "vung_khop_s": 1800 + 0.05 * L, "clip_offset_s": 0.05 * L,
                                         "end_s": 1800 + 0.95 * L}, [(1800.0, 1800.0 + L)]))
    ca.append(("5phut_giua_clip_2h", goc, {"start_s": 6600.0, "vung_khop_s": 9615.0, "clip_offset_s": 3015.0,
                                           "end_s": 9885.0}, [(9600.0, 9900.0)]))
    ra = []
    for ten, clip, m, that in ca:
        for bt in bien_the:
            if bt == "V2" and not os.path.isdir(khuc):
                continue
            r = _chay_con(video, clip, m, bt, khuc)
            if "loi" not in r:
                bao = [(x["video_tu"], x["video_den"]) for x in r["doan"]]
                r["precision_recall"] = danh_gia.precision_recall(bao, that) if bao else None
                r["loi_mep"] = [[round(x["video_tu"] - that[0][0], 3), round(x["video_den"] - that[0][1], 3)]
                                for x in r["doan"]]
            r["ca"] = ten
            ra.append(r)
            print(f"{ten} {bt}: {r.get('thoi_gian')} | đỉnh commit {r.get('bo_nho_sau', {}).get('peak_commit_mb')} MB "
                  f"wset {r.get('bo_nho_sau', {}).get('peak_wset_mb')} MB | clip {r.get('giay_clip_xu_ly')} s video "
                  f"{r.get('giay_video_xu_ly')} s | lỗi mép {r.get('loi_mep')} PR {r.get('precision_recall')} "
                  f"{r.get('loi', '')[-300:]}", flush=True)
    with open(os.path.join(d, f"thang_do_{'_'.join(bien_the)}.json"), "w", encoding="utf-8") as f:
        json.dump(ra, f, ensure_ascii=False, indent=1)


def _ncc_lag(a: np.ndarray, b: np.ndarray, o: int, n: int = 22050, M: int = 600) -> tuple:
    """Độ trễ nguyên (mẫu) và NCC lớn nhất của b so với a quanh mẫu o (cửa sổ 2 s)."""
    x, y = a[o:o + n].astype(np.float64), b[o - M:o + n + M].astype(np.float64)
    r = np.correlate(y, x, "valid") / np.sqrt(np.convolve(y * y, np.ones(n), "valid") * np.dot(x, x))
    j = int(np.argmax(r))
    return j - M, float(r[j])


CHU_KY_16BIT = 65536 * 256 / 11025          # mốc 16 bit của kho thường cuộn sau 1521,8 s (channel.MAXTIMEBITS_MAC_DINH)


def cuon(thu_muc: str, bien_the: str = "V1") -> None:
    """Kho THƯỜNG (16 bit) + clip > 25,4 phút: clip_offset_s engine báo có thể đã cuộn. Với mỗi kết quả, thử neo
    clip_offset_s + j·1521,8 s (j = 0 … còn trong clip), mỗi neo một tiến trình V1 — đo neo nào bắt nhịp và tốn bao nhiêu."""
    with open(os.path.join(thu_muc, "ket_qua.json"), encoding="utf-8") as f:
        ket = json.load(f)
    with open(os.path.join(DU_LIEU, f"su_that_{ket['video']}.json"), encoding="utf-8") as f:
        su_that = json.load(f)
    video = os.path.join(DU_LIEU, f"video_{ket['video']}.webm")
    ra = []
    for i, m in enumerate(ket["matches"] + ket["matches_loai"]):
        clip = m["duong_dan_kho"]
        L = ffprobe_dai(clip)
        dong = {"i": i, "chon": i < len(ket["matches"]), "match": _match_gon(m), "neo": []}
        j = 0
        while float(m["clip_offset_s"]) + j * CHU_KY_16BIT < L:
            off = float(m["clip_offset_s"]) + j * CHU_KY_16BIT
            mg = dict(_match_gon(m), clip_offset_s=off, start_s=float(m["vung_khop_s"]) - off)
            r = _chay_con(video, clip, mg, bien_the)
            r["j"] = j
            if "loi" not in r:
                r["cham_diem"] = cham_diem(r, su_that, m["clip"], m)
            dong["neo"].append({k: r.get(k) for k in ("j", "thoi_gian", "tuong_phan_thap", "so_giay_bam", "muc_trong",
                                                      "nguong_dung", "doan", "cham_diem", "bo_nho_sau", "loi")})
            print(f"[{i}] {m['clip']} vung {m['vung_khop_s']}..{m['end_s']} off {m['clip_offset_s']} j={j} → "
                  f"{r.get('thoi_gian', {}).get('tong_s')} s, tương phản thấp {r.get('tuong_phan_thap')}, "
                  f"trong {r.get('muc_trong')} ngưỡng {r.get('nguong_dung')}, đoạn "
                  f"{[(d['video_tu'], d['video_den'], d['clip_tu'], d['clip_den']) for d in r.get('doan', [])]}",
                  flush=True)
            j += 1
        ra.append(dong)
    with open(os.path.join(thu_muc, "cuon_moc.json"), "w", encoding="utf-8") as f:
        json.dump(ra, f, ensure_ascii=False, indent=1)


def tu_kiem() -> None:
    """(1) BỘ ĐỌC: doc_khuc lấy đúng chỉ số mẫu và ghép đúng qua chỗ gối (so với cắt thẳng từ file khúc); hai khúc
    liền nhau trùng khít trong vùng gối. (2) GHI LẠI (không assert): nội dung khúc so với FFmpeg ``-ss`` cùng đoạn —
    FFmpeg 9.0.1 với webm/Opus có lúc lệch vài chục ms trong vài chục giây đầu sau điểm seek; mức khúc s16 = f32/√2."""
    khuc = os.path.join(GOC, "khuc_B")   # cắt bằng đúng lệnh FFmpeg của _cut_chunks
    video = os.path.join(DU_LIEU, "video_B.webm")

    def khuc_np(s0: int) -> np.ndarray:
        with wave.open(os.path.join(khuc, f"chunk_{s0:07d}.wav"), "rb") as w:
            return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768.0
    k0, k3420, k6840 = khuc_np(0), khuc_np(3420), khuc_np(6840)
    SR = td.SR
    # quy tắc của doc_khuc: mỗi mẫu lấy từ khúc bắt đầu SỚM NHẤT còn phủ nó (mẫu ở sâu trong khúc nhất)
    a, ta = doc_khuc(khuc, 100.0, 120.0)
    assert ta == 100.0 and np.array_equal(a, k0[100 * SR: 220 * SR]), "đọc trong một khúc sai"
    a, ta = doc_khuc(khuc, 3500.0, 120.0)                       # đuôi khúc 0 rồi sang khúc 3420
    mong = np.concatenate([k0[3500 * SR:], k3420[len(k0) - 3420 * SR: 200 * SR]])
    assert ta == 3500.0 and np.array_equal(a, mong), "ghép khúc 0 → 3420 sai"
    a, ta = doc_khuc(khuc, 6990.0, 120.0)                       # đuôi khúc 3420 (hết ở 7020) rồi sang khúc 6840
    het = 3420 * SR + len(k3420)
    mong = np.concatenate([k3420[6990 * SR - 3420 * SR:], k6840[het - 6840 * SR: 7110 * SR - 6840 * SR]])
    assert ta == 6990.0 and np.array_equal(a, mong), "ghép khúc 3420 → 6840 sai"
    print(f"số mẫu khúc: 0 → {len(k0)}, 3420 → {len(k3420)}, 6840 → {len(k6840)} (danh định {3600 * SR})")
    gối = [(t, *_ncc_lag(k3420[3420 * SR:], k6840, t * SR)) for t in (5, 60, 170)]
    print(f"vùng gối 6840..7020: khúc 3420 vs khúc 6840 (giây, trễ, NCC) {gối}")
    assert all(lag == 0 and r > 0.9999 for _, lag, r in gối), gối
    for tu in (3500.0, 6800.0, 9000.0):
        a, _ = doc_khuc(khuc, tu, 120.0)
        b, _ = td.doc_pcm(video, tu, 120.0)
        n = min(len(a), len(b))
        do = [(t, *[round(x, 4) for x in _ncc_lag(a[:n], b[:n], t * SR)]) for t in (2, 20, 60, 100)]
        print(f"[ghi lại] khúc vs FFmpeg -ss {tu}: (giây sau seek, trễ mẫu, NCC) {do}; "
              f"mức f32/s16 {float(np.sqrt(np.mean(b[:n] ** 2) / np.mean(a[:n] ** 2))):.4f}")
    clip10 = os.path.join(DU_LIEU, "kho", "k01.opus")
    A = td.log_mel(td.doc_pcm(clip10, 120.0, 300.0)[0])
    B, _, _ = log_mel_dong(clip10, 120.0, 300.0)
    n = min(len(A), len(B))
    lech, tb = float(np.max(np.abs(A[:n] - B[:n]))), float(np.mean(np.abs(A[:n] - B[:n])))
    print(f"log_mel_dong vs td.log_mel: {len(A)}/{len(B)} khung, lệch log10 max {lech:.2e} (= {10 * lech:.3f} dB), "
          f"trung bình {tb:.2e}")
    assert abs(len(A) - len(B)) <= 1 and lech < 0.01, (len(A), len(B), lech)      # < 0,1 dB
    print("do_tinh_chinh: tự kiểm ĐẠT")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=("mot", "lo", "thang-do", "tu-kiem", "cuon"))
    ap.add_argument("thu_muc", nargs="?")
    ap.add_argument("--video")
    ap.add_argument("--clip")
    ap.add_argument("--match")
    ap.add_argument("--bien-the", default="V0,V1,V2")
    ap.add_argument("--khuc")
    ap.add_argument("--tat-ca-dat", action="store_true")
    a = ap.parse_args()
    if a.lenh == "mot":
        print(json.dumps(mot(a.video, a.clip, json.loads(a.match), a.bien_the, a.khuc), ensure_ascii=False))
    elif a.lenh == "lo":
        lo(a.thu_muc, a.tat_ca_dat, a.bien_the.split(","))
    elif a.lenh == "cuon":
        cuon(a.thu_muc)
    elif a.lenh == "thang-do":
        thang_do(a.bien_the.split(","))
    else:
        tu_kiem()


if __name__ == "__main__":
    main()
