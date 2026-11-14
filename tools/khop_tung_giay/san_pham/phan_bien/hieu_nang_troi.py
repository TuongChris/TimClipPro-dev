# -*- coding: utf-8 -*-
"""Phản biện HIỆU NĂNG (P-8) — dòng NHIỀU NEO ở tải thật: video chậm 0,1 % (đổi 30 ↔ 29,97 hình/giây kéo tiếng theo).

0,1 % < ngưỡng trôi 0,15 % (``toc_do_lech_toi_thieu``) nên engine giữ k = 1; trên một lần dùng 2 giờ các mảnh chính trôi
~7 s → một dòng mang tới NEO_TOI_DA = 6 neo cách nhau > NEO_GOP_S. Không sửa mã sản phẩm, không audio thật.
  tao      dựng <RA>/du_lieu/video_D.webm (webm/opus 96 kbps stereo 48 kHz) bằng FFmpeg từ dữ liệu giả lập 14/11:
           video_B[0, 1800) + goc_2h.opus chậm 0,1 % (asetrate) + video_B[9900, 10800) (nền, không có clip)
  engine   engine THẬT (cấu hình mặc định, ncores 2, tinh_chinh_moc BẬT = đường engine với ngân sách thật) trên kho tạm
           chỉ có goc_2h.opus; ghi matches (neo, lõi) + kq.tinh_chinh + từng lời gọi module (thời gian, ngân sách còn)
  do       đo riêng module trên đúng dòng engine (tiến trình riêng như hieu_nang.mot): đủ neo, và chỉ neo mạnh nhất
Chạy (từ TimClipPro/): PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang <venv python> -B -X utf8 \\
      ../tools/khop_tung_giay/san_pham/phan_bien/hieu_nang_troi.py tao|engine|do
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hieu_nang as hn  # noqa: E402

DL = os.path.join(hn.RA, "du_lieu")
VIDEO_D = os.path.join(DL, "video_D.webm")
GOC_2H = hn.CLIP[120][0]
K_THAT = 1.001                                     # giây video mỗi giây clip
DAU_THAT = 1800.0
DAI_CLIP = 7140.0065
# engine D = video chậm 0,1 % + clip 2 giờ; engine E = clip 10 phút dùng trọn, video hết 40 s sau đó (lỗi EOF, nhóm «eof»)
# engine F = cùng tiếng của video_E trong MP4 có luồng HÌNH dài hơn tiếng 26,5 ms (lệch dưới một khung hình — file
# trong máy thường gặp): do_dai_am_thanh < duration_of → pham_vi_quet_s = thời lượng cả file (ffprobe) → chạm lỗi EOF.
# Dựng: ffmpeg -i video_E.webm -f lavfi -i color=c=gray:s=64x36:r=25:d=940.04 -map 1:v -map 0:a -c:v libx264
#       -preset ultrafast -crf 45 -pix_fmt yuv420p -c:a aac -b:a 128k video_F.mp4
CA_ENGINE = {"D": (VIDEO_D, GOC_2H, os.path.join(hn.RA, "troi_engine.json")),
             "E": (hn.VIDEO_E, hn.CLIP[10][0], os.path.join(hn.RA, "eof_engine.json")),
             "F": (os.path.join(DL, "video_F.mp4"), hn.CLIP[10][0], os.path.join(hn.RA, "eof_engine_mp4.json"))}
ENGINE_JSON = CA_ENGINE["D"][2]


def tao() -> None:
    os.makedirs(DL, exist_ok=True)
    fmt = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    loc = (f"[0:a]atrim=0:1800,asetpts=PTS-STARTPTS,{fmt}[a0];"
           f"[1:a]asetrate={48000 / K_THAT:.6f},aresample=48000,pan=stereo|c0=c0|c1=c0,{fmt}[a1];"
           f"[0:a]atrim=9900:10800,asetpts=PTS-STARTPTS,{fmt}[a2];[a0][a1][a2]concat=n=3:v=0:a=1[o]")
    t = time.perf_counter()
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", hn.VIDEO, "-i", GOC_2H,
                        "-filter_complex", loc, "-map", "[o]", "-c:a", "libopus", "-b:a", "96k", VIDEO_D],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    dai = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                VIDEO_D], capture_output=True, text=True, check=True).stdout)
    st = {"video": "video_D.webm", "do_dai_video_s": dai, "k_that": K_THAT,
          "doan": [{"clip": "goc_2h.opus", "video_tu": DAU_THAT, "video_den": DAU_THAT + K_THAT * DAI_CLIP,
                    "clip_tu": 0.0, "clip_den": DAI_CLIP}],
          "ghi_chu": "video_B[0,1800) + goc_2h chậm 0,1 % (asetrate, như đổi 30→29,97 hình/giây) + video_B[9900,10800)"}
    with open(os.path.join(DL, "su_that_D.json"), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    print(f"video_D: {dai:.3f} s, dựng {time.perf_counter() - t:.1f} s")


def engine(ca: str = "D") -> None:
    video, clip_kho, ra_json = CA_ENGINE[ca]
    sc = sys.modules.get("sitecustomize")
    if sc is None or os.path.normcase(os.path.dirname(os.path.abspath(sc.__file__))) != os.path.normcase(hn.CHAN_MANG):
        raise SystemExit(f"Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH={hn.CHAN_MANG}")
    for bien in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_INSTALLATION_ID"):
        if os.environ.get(bien):
            raise SystemExit(f"Bỏ biến {bien}: chỉ chạy legacy trên thư mục tạm.")
    tam = tempfile.mkdtemp(prefix="p8_hn_troi_")
    data, ketqua, kho = (os.path.join(tam, x) for x in ("data", "ketqua", "kho"))
    os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = data, ketqua
    sys.path.insert(0, hn.MA)
    import engine as eng
    import tinh_chinh_moc as tcm

    goc, goi = tcm.tinh_chinh_dong, []
    goc_khoi, dem_doc = tcm._khoi_ffmpeg, []           # bộ giải mã của đường engine (MỘT FFmpeg mỗi cửa sổ): chỉ đếm

    def khoi(duong, tu_s, den_s, *a, **kw):
        so = 0
        try:
            for x, t in goc_khoi(duong, tu_s, den_s, *a, **kw):
                so += len(x)
                yield x, t
        finally:
            dem_doc.append((os.path.basename(duong), round(tu_s, 3), round(den_s - tu_s, 3), int(so)))

    def boc(clip, video, neo, vung, end, **kw):
        t, con = time.perf_counter(), (kw["han_chot"] - time.monotonic() if kw.get("han_chot") else None)
        n0 = len(dem_doc)
        try:
            r = goc(clip, video, neo, vung, end, **kw)
        except BaseException as e:
            goi.append({"neo": [list(x) for x in neo], "vung": vung, "end": end, "loi": repr(e)})
            raise
        cac_doc = dem_doc[n0:]
        goi.append({"neo": [list(x) for x in neo], "vung": vung, "end": end, "pham_vi": kw.get("pham_vi_s"),
                    "ngan_sach_con_s": None if con is None else round(con, 2), "s": round(time.perf_counter() - t, 2),
                    "trang_thai": r["trang_thai"], "ly_do": r["ly_do"],
                    "doan": [[d["video_tu"], d["video_den"], d["clip_tu"], d["clip_den"], d["k"]] for d in r["doan"]],
                    "so_lan_ffmpeg": len(cac_doc), "so_lan_ffmpeg_0_mau": sum(1 for x in cac_doc if x[3] == 0),
                    "vai_lan_ffmpeg_cuoi": cac_doc[-3:]})
        return r

    tcm.tinh_chinh_dong = boc
    tcm._khoi_ffmpeg = khoi
    try:
        os.makedirs(kho)
        shutil.copy2(clip_kho, kho)
        e = eng.Engine(root=hn.MA, data_dir=data, out_dir=ketqua)
        e.config.ncores = 2
        e.config.tinh_chinh_moc = True
        e.add_kho(f"PB hieu nang {ca}", kho)
        t = time.perf_counter()
        kb = e.build_database(kho, "new")
        t_kho = time.perf_counter() - t
        t = time.perf_counter()
        kq = e.scan_media(video)
        t_quet = time.perf_counter() - t
        ra = {"ca": ca, "video": video, "status": kq.status, "note": kq.note, "thoi_gian_dung_kho_s": round(t_kho, 1),
              "thoi_gian_quet_ca_tinh_chinh_s": round(t_quet, 1), "duration_s": kq.duration_s,
              "pham_vi_quet_s": kq.pham_vi_quet_s,
              "matches": [{k: getattr(m, k) for k in ("clip", "start_s", "vung_khop_s", "end_s", "clip_offset_s",
                                                      "hashes", "he_so", "ho", "neo", "moc_mo_ho")}
                          for m in kq.matches],
              "tinh_chinh": kq.tinh_chinh, "goi_module": goi, "dung_kho": kb}
        with open(ra_json, "w", encoding="utf-8") as f:
            json.dump(ra, f, ensure_ascii=False, indent=1, default=str)
        print(json.dumps({k: ra[k] for k in ("status", "thoi_gian_dung_kho_s", "thoi_gian_quet_ca_tinh_chinh_s",
                                             "duration_s", "pham_vi_quet_s", "matches", "goi_module")},
                         ensure_ascii=False, default=str))
    finally:
        shutil.rmtree(tam, ignore_errors=True)


def do() -> None:
    with open(ENGINE_JSON, encoding="utf-8") as f:
        ke = json.load(f)
    ds = []
    for i, m in enumerate(ke["matches"]):
        if m["clip"] != "goc_2h.opus" or not m["neo"]:
            continue
        ts = {"clip": GOC_2H, "video": VIDEO_D, "neo": m["neo"], "vung": m["vung_khop_s"], "end": m["end_s"],
              "pham_vi": [0.0, ke["pham_vi_quet_s"]], "pha": True}
        ds.append(hn.chay(ts, f"troi_dong{i}_{len(m['neo'])}_neo"))
        ds.append(hn.chay(dict(ts, neo=m["neo"][:1]), f"troi_dong{i}_chi_neo_manh_nhat"))
    with open(os.path.join(hn.RA, "troi_do.json"), "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=1)


def do_gia() -> None:
    """Không chờ engine: neo DỰNG theo đúng cách engine tính (a = bat_dau − 1·t_clip của mảnh chính ở giây clip t, làm
    tròn 0,1 s như audfprint; mạnh nhất = mảnh giữa), 5 neo cách nhau > NEO_GOP_S; lõi trễ/sớm 30 s."""
    neo = [[round(DAU_THAT + (K_THAT - 1.0) * t, 1), 1.0] for t in (3570.0, 600.0, 6540.0, 1800.0, 5300.0)]
    ts = {"clip": GOC_2H, "video": VIDEO_D, "neo": neo, "vung": DAU_THAT + 30.0,
          "end": DAU_THAT + K_THAT * DAI_CLIP - 30.0, "pham_vi": [0.0, 9847.155], "pha": True,
          "su_that": [DAU_THAT, DAU_THAT + K_THAT * DAI_CLIP, 0.0, DAI_CLIP, K_THAT]}
    ds = [hn.chay(ts, "troi_gia_5_neo"), hn.chay(dict(ts, neo=neo[:1]), "troi_gia_chi_neo_manh_nhat")]
    with open(os.path.join(hn.RA, "troi_gia.json"), "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=1)


def do_hai_neo() -> None:
    """Dạng neo engine THẬT đã sinh (troi_engine.json, dòng 4: hai neo cách đúng 1,0 s vì trôi trong một dòng) nhưng trên
    lõi KHÔNG cuộn mốc 16 bit (giây clip 8–1500 < 1521,8): lõi [1808,1; 3300], neo (1800,4; 1) và (1801,4; 1) — đúng
    a = bat_dau − t_clip của mảnh chính ở giây clip ~400 và ~1400. Đối chứng: chỉ neo đầu."""
    ts = {"clip": GOC_2H, "video": VIDEO_D, "neo": [[1800.4, 1.0], [1801.4, 1.0]], "vung": 1808.1, "end": 3300.0,
          "pham_vi": [0.0, 9847.147], "pha": True}
    ds = [hn.chay(ts, "troi_2_neo_cach_1s"), hn.chay(dict(ts, neo=ts["neo"][:1]), "troi_2_neo_doi_chung_1_neo")]
    with open(os.path.join(hn.RA, "troi_hai_neo.json"), "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=1)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    {"tao": tao, "engine": engine, "do": do, "do_gia": do_gia, "do_hai_neo": do_hai_neo}[sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    main()
