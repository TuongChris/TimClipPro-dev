# -*- coding: utf-8 -*-
"""Phản biện HIỆU NĂNG của TimClipPro/tinh_chinh_moc.py (P-8, 14/11/2026): thời gian + RAM đỉnh ở tải thật.

Không sửa mã sản phẩm. Mỗi lần đo chạy trong TIẾN TRÌNH RIÊNG: RAM đỉnh = peak working set / peak commit của chính
tiến trình đó (kèm mốc ngay trước lời gọi). ``doc_pcm`` = bọc ``tcm._doc_pcm_ffmpeg`` (FFmpeg thật, nhưng MỘT tiến
trình mỗi KHỐI — đường engine dùng một tiến trình mỗi CỬA SỔ, nhanh hơn ~15–20 %: số đo ở đây là cận trên), để ghi lại
từng khối giải mã; ``kiem_huy`` ghi mốc từng lời gọi (khe dài nhất giữa hai lần kiểm = độ trễ huỷ / vượt hạn chót xấu
nhất). Tuỳ chọn ``pha``: bọc các hàm nội bộ để tách thời gian (chỉ đo giờ).

Dữ liệu: audio GIẢ LẬP định dạng thật của phản biện hiệu năng 14/11 (``tools/khop_tung_giay/phan_bien_hieu_nang/
tao_du_lieu.py``: ghép nốt ngẫu nhiên ``_giai_dieu`` / nhạc có nhịp theo khối 600 s, mỗi khối một seed):
video_B.webm (webm/opus ~100 kbps stereo 48 kHz, 3 giờ; clip 2 giờ dùng TRỌN ở giây 1800), clip opus 64 kbps mono
16 kHz goc_dau_600 / goc_dau_3600 (10 / 60 phút đầu của clip 2 giờ) và goc_2h (7140 s).
  mot            một lần đo: đọc JSON tham số từ stdin, in một dòng JSON
  bo [nhóm ...]  chạy các nhóm đo (mặc định tất cả), ghi <RA>/<nhóm>.json
Chạy (từ TimClipPro/): PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B -X utf8 \\
      ../tools/khop_tung_giay/san_pham/phan_bien/hieu_nang.py bo
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
import psutil  # noqa: E402

MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "TimClipPro"))  # checkout chứa file này
CHAN_MANG = os.path.join(os.path.dirname(MA), "tools", "test", "chan_mang")
DU = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_hieu_nang\du_lieu"
TD = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay\phan_bien_hieu_nang\thang_do"
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\phan_bien\hieu_nang"
VIDEO = os.path.join(DU, "video_B.webm")
DAI_VIDEO = 10800.008
CLIP = {10: (os.path.join(TD, "goc_dau_600.opus"), 600.02), 60: (os.path.join(TD, "goc_dau_3600.opus"), 3600.02),
        120: (os.path.join(DU, "kho", "goc_2h.opus"), 7140.0065)}
P = 1800.0                                  # sự thật: giây 0 của clip ở giây 1800 của video, k = 1
SR = 11025


def ca(phut: int, **them) -> dict:
    """Một dòng engine giả lập: lõi trễ/sớm vài giây như audfprint (time-quantile 5 %), neo lệch 0,04 s (1 số lẻ)."""
    clip, L = CLIP[phut]
    ts = {"clip": clip, "video": VIDEO, "neo": [[P + 0.04, 1.0]], "vung": P + 12.3, "end": P + L - 9.7,
          "pham_vi": [0.0, DAI_VIDEO], "su_that": [P, P + L, 0.0, L]}
    ts.update(them)
    return ts


def _mb(x: int) -> float:
    return round(x / 2**20, 1)


def _bo_nho() -> dict:
    mi = psutil.Process().memory_info()
    return {"wset_dinh": _mb(mi.peak_wset), "commit_dinh": _mb(mi.peak_pagefile), "rss": _mb(mi.rss)}


def mot(ts: dict) -> dict:
    sc = sys.modules.get("sitecustomize")
    if sc is None or os.path.normcase(os.path.dirname(os.path.abspath(sc.__file__))) != os.path.normcase(CHAN_MANG):
        raise SystemExit(f"Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH={CHAN_MANG}")
    sys.path.insert(0, MA)
    import numpy as np  # noqa: F401  (nạp trước để mốc RAM gồm numpy như tiến trình engine)
    import tinh_chinh_moc as tcm

    T0 = [0.0]
    goi: list = []
    goc_doc = tcm._doc_pcm_ffmpeg

    def doc(duong, tu_s, dai_s):
        t = time.perf_counter()
        x, tu = goc_doc(duong, tu_s, dai_s)
        goi.append([os.path.basename(duong), round(tu_s, 3), round(dai_s, 3), round(float(tu), 3), int(len(x)),
                    round(time.perf_counter() - t, 3), round(t - T0[0], 3)])
        return x, tu

    pha: dict = {}
    if ts.get("pha"):
        for ten in ("_dac_trung", "_nen_p99", "_can_chinh", "_do_duong", "_mep", "_khoang_im", "_cac_doan_tho",
                    "_mo_ho", "_ho_so", "_doan_ra"):
            def boc(*a, _f=getattr(tcm, ten), _ten=ten, **k):
                t = time.perf_counter()
                try:
                    return _f(*a, **k)
                finally:
                    d = pha.setdefault(_ten, [0, 0.0])
                    d[0] += 1
                    d[1] += time.perf_counter() - t
            setattr(tcm, ten, boc)

    class Huy(Exception):
        pass

    moc: list = []
    co_huy = threading.Event()
    t_huy: list = [None]
    huy_sau = ts.get("huy_sau")

    def kiem_huy():
        moc.append(time.perf_counter())
        if co_huy.is_set() or (huy_sau is not None and len(moc) > huy_sau):
            raise Huy

    dung = threading.Event()
    con_dinh = [0]

    def lay_mau():                                   # RAM của tiến trình con FFmpeg (không nằm trong wset của ta)
        p = psutil.Process()
        while not dung.wait(0.05):
            try:
                con_dinh[0] = max(con_dinh[0], sum(c.memory_info().rss for c in p.children()))
            except psutil.Error:
                pass

    threading.Thread(target=lay_mau, daemon=True).start()
    psutil.cpu_percent(None)
    truoc = _bo_nho()
    han = time.monotonic() + ts["han_s"] if ts.get("han_s") is not None else None
    T0[0] = time.perf_counter()
    if ts.get("huy_luc") is not None:
        def bat():
            t_huy[0] = time.perf_counter()
            co_huy.set()
        threading.Timer(ts["huy_luc"], bat).start()
    try:
        kq = tcm.tinh_chinh_dong(ts["clip"], ts["video"], [tuple(x) for x in ts["neo"]], ts["vung"], ts["end"],
                                 pham_vi_s=tuple(ts["pham_vi"]) if ts.get("pham_vi") else None, kiem_huy=kiem_huy,
                                 han_chot=han, doc_pcm=doc)
        ket = "tra_ve"
    except Huy:
        kq, ket = None, "huy"
    t1 = time.perf_counter()
    m_ra = time.monotonic()
    dung.set()
    sau = _bo_nho()
    cpu_he_thong = psutil.cpu_percent(None)

    moc_tg = [T0[0], *moc, t1]
    khe = sorted(((b - a, a - T0[0]) for a, b in zip(moc_tg, moc_tg[1:])), reverse=True)
    giai_ma: dict = {}
    for ten, tu, dai, tu_thuc, mau, s, _ in goi:
        g = giai_ma.setdefault(ten, {"so_lan": 0, "giay_xin": 0.0, "giay_giai_ma": 0.0, "ffmpeg_s": 0.0,
                                     "tu": tu, "den": tu + dai, "khoi_dai_nhat_s": 0.0})
        g["so_lan"] += 1
        g["giay_xin"] = round(g["giay_xin"] + dai, 3)
        g["giay_giai_ma"] = round(g["giay_giai_ma"] + mau / SR, 3)
        g["ffmpeg_s"] = round(g["ffmpeg_s"] + s, 3)
        g["tu"], g["den"] = min(g["tu"], tu), round(max(g["den"], tu + dai), 3)
        g["khoi_dai_nhat_s"] = max(g["khoi_dai_nhat_s"], dai)
    ra = {"ket": ket, "wall_s": round(t1 - T0[0], 3), "so_lan_kiem_huy": len(moc),
          "khe_kiem_dai_nhat": [[round(a, 3), round(b, 3)] for a, b in khe[:6]],   # [độ dài khe, lúc bắt đầu]
          "bo_nho_truoc": truoc, "bo_nho_sau": sau,
          "tang_wset_mb": round(sau["wset_dinh"] - truoc["rss"], 1),
          "ffmpeg_con_dinh_mb": _mb(con_dinh[0]), "cpu_he_thong_pct": cpu_he_thong,
          "giai_ma": giai_ma, "goi": goi if ts.get("ghi_goi") else len(goi),
          "pha": {k: [v[0], round(v[1], 3)] for k, v in pha.items()}}
    if t_huy[0] is not None:
        ra["huy_luc_thuc_s"] = round(t_huy[0] - T0[0], 3)
        ra["tre_huy_s"] = round(t1 - t_huy[0], 3)
    if han is not None:
        ra["vuot_han_s"] = round(m_ra - han, 3)
    if kq is not None:
        ra["kq"] = {k: kq[k] for k in ("trang_thai", "ly_do", "doan", "cho_cat", "cham_gioi_han", "nguong_pct",
                                       "nen_p99_pct", "thoi_gian_s")}
        ra["kq"]["so_diem_ho_so"] = len(kq["ho_so"])
        ra["json_ho_so_kb"] = round(len(json.dumps(kq["ho_so"])) / 1024, 1)
    return ra


# ---------------------------------------------------------------------------------------------- bộ đo

_NHOM: dict = {"ten": None, "ds": []}         # nhóm đang chạy: ghi JSON sau MỖI lần đo (lần sau có treo cũng không mất)


def _luu(kq: dict) -> dict:
    if _NHOM["ten"]:
        _NHOM["ds"].append(kq)
        _ghi(_NHOM["ten"], _NHOM["ds"])
    return kq


def chay(ts: dict, nhan: str, han_tien_trinh_s: float = 900.0) -> dict:
    lenh = [sys.executable, "-B", "-X", "utf8", os.path.abspath(__file__), "mot"]
    t = time.perf_counter()
    try:
        r = subprocess.run(lenh, input=json.dumps(ts), capture_output=True, text=True, encoding="utf-8",
                           timeout=han_tien_trinh_s, cwd=MA)
    except subprocess.TimeoutExpired:
        print(f"{nhan}: KHÔNG TRẢ VỀ sau {han_tien_trinh_s:g} s — đã giết tiến trình đo", flush=True)
        return _luu({"nhan": nhan, "tham_so": ts, "ket": "khong_tra_ve", "han_tien_trinh_s": han_tien_trinh_s,
                     "wall_tien_trinh_s": round(time.perf_counter() - t, 2)})
    if r.returncode != 0:
        raise RuntimeError(f"{nhan}: {r.stderr[-3000:]}")
    kq = json.loads(r.stdout.strip().splitlines()[-1])
    kq["nhan"], kq["tham_so"], kq["wall_tien_trinh_s"] = nhan, ts, round(time.perf_counter() - t, 2)
    tom = kq.get("kq") or {}
    doan = [[d["video_tu"], d["video_den"], d["clip_tu"], d["clip_den"]] for d in tom.get("doan", [])]
    print(f"{nhan}: {kq['ket']} {tom.get('trang_thai', '')} {tom.get('ly_do', '')[:60]!r} wall {kq['wall_s']} s, "
          f"wset +{kq['tang_wset_mb']} MB (đỉnh {kq['bo_nho_sau']['wset_dinh']}), khe kiểm dài nhất "
          f"{kq['khe_kiem_dai_nhat'][0]}, cpu {kq['cpu_he_thong_pct']} %, đoạn {doan}"
          + (f", trễ huỷ {kq['tre_huy_s']}" if "tre_huy_s" in kq else "")
          + (f", vượt hạn {kq['vuot_han_s']}" if "vuot_han_s" in kq else ""), flush=True)
    return _luu(kq)


def _ghi(ten: str, ds: list) -> None:
    with open(os.path.join(RA, f"{ten}.json"), "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=1)


def _doc(ten: str) -> list:
    with open(os.path.join(RA, f"{ten}.json"), encoding="utf-8") as f:
        return json.load(f)


def nhom_loi() -> list:
    """Lõi 10 / 60 / 120 phút, 3 lần mỗi cỡ, ghi đủ lời gọi giải mã."""
    ds = []
    for lan in range(3):
        for phut in (10, 60, 120):
            ds.append(chay(ca(phut, ghi_goi=True), f"loi_{phut}p_lan{lan + 1}"))
    return ds


def nhom_lon_nhat() -> list:
    """Lõi 8999 s (cỡ lớn nhất còn nhận). pham_vi None: cửa sổ video vượt cuối file ~970 s (không chạm lỗi EOF ở
    nhóm «eof»); kết quả CHUA là đúng (lõi dài hơn đoạn thật 7140 s) — ở đây chỉ đo thời gian + RAM."""
    return [chay(ca(120, vung=P, end=P + 8999.0, pham_vi=None, ghi_goi=True), "lon_nhat_8999s")]


VIDEO_E = os.path.join(RA, "du_lieu", "video_E.webm")
P_E = 300.0


def tao_e() -> None:
    """video_E.webm: nền video_B[0, 300) + clip goc_dau_600 + nền video_B[900, 940) — clip 10 phút dùng trọn, video hết
    40 s sau đó (webm/opus 96 kbps stereo 48 kHz, như bản tải YouTube)."""
    os.makedirs(os.path.dirname(VIDEO_E), exist_ok=True)
    fmt = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    loc = (f"[0:a]atrim=0:300,asetpts=PTS-STARTPTS,{fmt}[a0];[1:a]pan=stereo|c0=c0|c1=c0,{fmt}[a1];"
           f"[0:a]atrim=900:940,asetpts=PTS-STARTPTS,{fmt}[a2];[a0][a1][a2]concat=n=3:v=0:a=1[o]")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", VIDEO, "-i", CLIP[10][0],
                        "-filter_complex", loc, "-map", "[o]", "-c:a", "libopus", "-b:a", "96k", VIDEO_E],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    print("video_E:", ffprobe_dai(VIDEO_E), "s")


def ffprobe_dai(p: str) -> float:
    """Thời lượng như ``Engine.duration_of`` (ffprobe format=duration) — engine truyền (0, số này) làm pham_vi_s."""
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True, check=True).stdout.strip())


def nhom_eof() -> list:
    """Cửa sổ video chạm cuối phạm vi đã quét = thời lượng ffprobe (đúng giá trị engine truyền). Opus giải mã hụt
    ~6,5–7 ms so với thời lượng khai báo → khối cuối xin < 0,05 s, FFmpeg trả 0 mẫu, ``het`` không bật (ngưỡng
    ``len(x) < (dai − 0,05)·SR`` âm), vị trí không tiến: lặp gọi FFmpeg tới hạn chót — không hạn chót thì mãi mãi."""
    sys.path.insert(0, MA)
    import tinh_chinh_moc as tcm
    dur = ffprobe_dai(VIDEO_E)
    x, tu = tcm._doc_pcm_ffmpeg(VIDEO_E, dur - 20.0, 30.0)        # mốc mẫu cuối FFmpeg giải mã được (bộ đọc của module)
    het_that = round(tu + len(x) / SR, 6)
    print(f"video_E: ffprobe {dur} s, giải mã hết ở {het_that} s (hụt {1000 * (dur - het_that):.3f} ms)", flush=True)
    goc = {"clip": CLIP[10][0], "video": VIDEO_E, "neo": [[P_E + 0.04, 1.0]], "vung": P_E + 12.3,
           "end": P_E + 600.02 - 9.7, "ghi_goi": True, "su_that": [P_E, P_E + 600.0135, 0.0, 600.0135],
           "ffprobe_s": dur, "giai_ma_het_s": het_that}
    return [chay(dict(goc, pham_vi=None), "eof_E_pham_vi_None_doi_chung"),
            chay(dict(goc, pham_vi=[0.0, dur], han_s=30.0), "eof_E_pham_vi_ffprobe_han_30s"),
            chay(dict(goc, pham_vi=[0.0, dur]), "eof_E_pham_vi_ffprobe_khong_han", han_tien_trinh_s=120.0),
            chay(dict(goc, pham_vi=[0.0, het_that]), "eof_E_pham_vi_dung_moc_giai_ma"),
            chay(dict(goc, pham_vi=[0.0, dur + 0.05]), "eof_E_pham_vi_ffprobe_cong_50ms")]


def nhom_pha() -> list:
    return [chay(ca(phut, pha=True), f"pha_{phut}p") for phut in (10, 60, 120)]


def nhom_tu_choi() -> list:
    # lõi đúng 9000 s vẫn được nhận (có giải mã); hạn 5 s cho khỏi đo trọn, pham_vi None tránh lỗi EOF (nhóm «eof»)
    return [chay(ca(120, vung=P, end=P + 9000.5, ghi_goi=True), "tu_choi_9000.5s"),
            chay(ca(120, vung=0.0, end=10800.0, ghi_goi=True), "tu_choi_10800s"),
            chay(ca(120, vung=P, end=P + 9000.0, pham_vi=None, han_s=5.0, ghi_goi=True), "nhan_9000.0s_dung_bien")]


def nhom_huy() -> list:
    """Huỷ ở giữa khe kiểm dài nhất của lõi 120 phút (đo ở nhóm «loi») + rải đều; và huỷ ngay ở lời gọi thứ N."""
    loi = [x for x in _doc("loi") if x["nhan"].startswith("loi_120p")]
    wall = max(x["wall_s"] for x in loi)
    diem = sorted({round(b + 0.05, 2) for x in loi for _, b in x["khe_kiem_dai_nhat"][:2]}
                  | {round(wall * f, 2) for f in (0.1, 0.3, 0.5, 0.7, 0.9)})
    ds = [chay(ca(120, huy_luc=t), f"huy_luc_{t}s") for t in diem]
    ds += [chay(ca(120, huy_sau=n), f"huy_sau_{n}_lan") for n in (0, 5, 20, 60)]
    return ds


def nhom_han() -> list:
    ds = [chay(ca(120, han_s=h), f"han_{h}s_120p") for h in (5.0, 15.0, 30.0)]
    ds.append(chay(ca(60, han_s=30.0), "han_30s_60p"))
    return ds


def nhom_nhieu_neo() -> list:
    """Cùng lõi 120 phút, 6 neo (trần NEO_TOI_DA của engine): 1 neo đúng + 5 neo lệch > 1 s (không trôi)."""
    neo = [[P + 0.04, 1.0], [P + 1.3, 1.0], [P - 1.4, 1.0], [P + 2.6, 1.0], [P - 2.8, 1.0], [P + 3.9, 1.0]]
    return [chay(ca(120, neo=neo, pha=True), "sau_neo_120p")]


NHOM = {"loi": nhom_loi, "eof": nhom_eof, "lon_nhat": nhom_lon_nhat, "pha": nhom_pha, "tu_choi": nhom_tu_choi,
        "huy": nhom_huy, "han": nhom_han, "nhieu_neo": nhom_nhieu_neo}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1:2] == ["mot"]:
        print(json.dumps(mot(json.loads(sys.stdin.read())), ensure_ascii=False))
        return
    if sys.argv[1:2] == ["tao_e"]:
        tao_e()
        return
    if sys.argv[1:2] != ["bo"]:
        raise SystemExit(__doc__)
    os.makedirs(RA, exist_ok=True)
    for ten in sys.argv[2:] or list(NHOM):
        t = time.perf_counter()
        _NHOM["ten"], _NHOM["ds"] = ten, []
        _ghi(ten, NHOM[ten]())
        print(f"== nhóm {ten} xong {time.perf_counter() - t:.1f} s", flush=True)


if __name__ == "__main__":
    main()
