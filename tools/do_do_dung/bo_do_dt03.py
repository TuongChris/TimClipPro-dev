# -*- coding: utf-8 -*-
"""DT-03 giai đoạn 1 — bộ đo ĐỘ ĐÚNG có đáp án trên audio kho THẬT (chỉ đọc), engine + audfprint THẬT (25/11/2026).

  dung   : chọn clip kho (SML) + nền từ kênh khác (đọc E: chỉ đọc, chép ra thư mục chạy), ghép ca có đáp án, biến đổi FFmpeg.
  chay   : dựng kho vân tay RIÊNG (thư mục tạm) từ clip đã chép, quét từng ca bằng Engine.scan_media (cấu hình khớp của
           DEV, tinh chỉnh mốc BẬT — một lượt cho cả mốc lượt quét lẫn mốc tinh chỉnh). Chạy lại = bỏ qua ca đã có kết quả.
  cham   : chấm điểm → cham_diem.json + BAO_CAO_DO_DUNG.md.

Không ghi gì vào E:, DEV DevState, lichsu.db thật. Chạy (Git Bash):
  PYTHONPATH=C:/Dev/pc2_test_tools/chan_mang <venv>/python.exe -B -X utf8 bo_do_dt03.py dung|chay|cham
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import dataclasses  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import statistics  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

MA = r"C:\Dev\TimClipPro_YtDlp\TimClipPro"
RA = r"C:\Dev\pc2_test_runs\2026-11-25_dt03"
CAU_HINH_DEV = r"C:\Dev\TimClipPro_DevState\data\cau_hinh.json"
KHO_DO = r"E:\Kho_Tool_Quet\Kho_SML"
NEN = [r"E:\Kho_Tool_Quet\Kho_Ms_Rachel", r"E:\Kho_Tool_Quet\Kho_Mr_Ballen", r"E:\Kho_Tool_Quet\Kho_Cory",
       r"E:\Kho_Tool_Quet\Kho_MSA"]
GIONG = r"E:\Kho_Tool_Quet\Kho_Mr_Ballen"      # tiếng nói đè
NHAC = r"E:\Kho_Tool_Quet\Kho_Ms_Rachel"        # nhạc/hát đè
SR = 48000
SO_CLIP_KHO = 60
DO_DAI_CHEN = [8, 15, 30, 60, 120]
NHOM_MOI_BIEN_DOI = 3
DAI_CA_S = 1200
SO_CA_AM, DAI_CA_AM_S = 4, 1800
SEED = 2511
# tên → (bộ lọc FFmpeg áp lên CẢ file, hệ số tốc độ «he_so», mã hoá, kiểu đè trong numpy)
BIEN_DOI = {
    "goc": ("", 1.0, ["-c:a", "aac", "-b:a", "128k"], None),
    "nen_24k": ("", 1.0, ["-ac", "1", "-c:a", "libopus", "-b:a", "24k"], None),
    "nhac_de": ("", 1.0, ["-c:a", "aac", "-b:a", "128k"], ("nhac", 0.0)),
    "giong_de": ("", 1.0, ["-c:a", "aac", "-b:a", "128k"], ("giong", -3.0)),
    "nhanh_3": ("atempo=1.03", 1.03, ["-c:a", "aac", "-b:a", "128k"], None),
    "nhanh_6": ("atempo=1.06", 1.06, ["-c:a", "aac", "-b:a", "128k"], None),
    "cao_do_1": (f"asetrate={SR * 1.059463:.0f},aresample={SR},atempo={1 / 1.059463:.6f}", 1.0,
                 ["-c:a", "aac", "-b:a", "128k"], None),
    "tua_5": (f"asetrate={SR * 1.05:.0f},aresample={SR}", 1.05, ["-c:a", "aac", "-b:a", "128k"], None),
}
DUOI = {"libopus": ".opus"}


def _ghi(p, o):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=str)


def _doc(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def do_dai(p: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def doc_pcm(p: str, tu: float, dai: float) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{tu:.3f}", "-t", f"{dai:.3f}", "-i", p, "-ac", "1", "-ar",
                        str(SR), "-f", "s16le", "-"], capture_output=True, timeout=300, check=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < int(dai * SR) - SR // 10:
        raise RuntimeError(f"đọc thiếu {os.path.basename(p)} {tu}+{dai}: {len(x) / SR:.2f}s")
    return x[: int(round(dai * SR))]


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) + 1e-9


def _chon(rng, thu_muc: str, so: int, tu: float, den: float) -> list:
    ds = sorted(f for f in os.listdir(thu_muc) if f.lower().endswith(".opus"))
    rng.shuffle(ds)
    ra = []
    for f in ds:
        d = do_dai(os.path.join(thu_muc, f))
        if tu <= d <= den:
            ra.append((os.path.join(thu_muc, f), d))
            if len(ra) >= so:
                break
    return ra


def ghep_nen(rng, nguon: list, dai_s: float) -> np.ndarray:
    phan, con = [], dai_s
    while con > 0.01:
        p, d = rng.choice(nguon)
        dai = min(con, rng.uniform(60, 300), d - 1)
        tu = rng.uniform(0, max(0.0, d - dai - 0.5))
        phan.append(doc_pcm(p, tu, dai))
        con -= dai
    x = np.concatenate(phan)
    n = int(round(dai_s * SR))
    return np.pad(x, (0, max(0, n - len(x))))[:n]


def ma_hoa(x: np.ndarray, loc: str, ma: list, dich: str) -> None:
    lenh = ["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-"]
    if loc:
        lenh += ["-af", loc]
    lenh += ma + [dich]
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(lenh, input=pcm, check=True, timeout=600)


def dung() -> None:
    rng = random.Random(SEED)
    if os.path.isdir(os.path.join(RA, "ca")):
        raise SystemExit(f"Đã có {RA}\\ca — xoá thư mục chạy trước khi dựng lại.")
    os.makedirs(os.path.join(RA, "kho"))
    os.makedirs(os.path.join(RA, "ca"))
    t0 = time.time()
    kho = _chon(rng, KHO_DO, SO_CLIP_KHO, 150, 1500)
    for p, _ in kho:
        shutil.copy2(p, os.path.join(RA, "kho", os.path.basename(p)))   # chỉ ĐỌC E:
    nen = [x for tm in NEN for x in _chon(rng, tm, 12, 120, 4000)]
    giong = _chon(rng, GIONG, 6, 300, 4000)
    nhac = _chon(rng, NHAC, 6, 300, 4000)
    print(f"kho {len(kho)} clip, nền {len(nen)}, giọng {len(giong)}, nhạc {len(nhac)} ({time.time() - t0:.0f}s)", flush=True)
    dai_clip = {os.path.basename(p): d for p, d in kho}
    ds_ca = []
    for bd, (loc, he_so, ma, de) in BIEN_DOI.items():
        for g in range(NHOM_MOI_BIEN_DOI):
            x = ghep_nen(rng, nen, DAI_CA_S)
            dai = DO_DAI_CHEN[:]
            rng.shuffle(dai)
            o = DAI_CA_S / len(dai)            # mỗi đoạn một ô, đặt ngẫu nhiên trong ô, cách mép ô ≥ 20 s
            chen = []
            for i, L in enumerate(dai):
                hop_le = [(p, d) for p, d in kho if d >= L + 2]
                p, d = rng.choice(hop_le)
                c_tu = round(rng.uniform(0, d - L - 1), 2)
                v_tu = round(rng.uniform(i * o + 20, (i + 1) * o - L - 20), 2)
                seg = doc_pcm(p, c_tu, L)
                a = int(round(v_tu * SR))
                x[a:a + len(seg)] = seg
                chen.append({"clip": os.path.basename(p), "clip_tu": c_tu, "clip_den": round(c_tu + L, 2),
                             "v_tu_goc": v_tu, "v_den_goc": round(v_tu + L, 2), "dai_s": L})
            if de:
                kieu, db = de
                ov = ghep_nen(rng, nhac if kieu == "nhac" else giong, DAI_CA_S)
                x = x + ov * (rms(x) / rms(ov)) * 10 ** (db / 20)
                x = x / max(1.0, float(np.max(np.abs(x))))
            ten = f"{bd}_{g}{DUOI.get(ma[ma.index('-c:a') + 1], '.m4a')}"
            ma_hoa(x, loc, ma, os.path.join(RA, "ca", ten))
            for c in chen:                      # trục video SAU biến đổi tốc độ
                c["video_tu"] = round(c["v_tu_goc"] / he_so, 3)
                c["video_den"] = round(c["v_den_goc"] / he_so, 3)
                c["he_so"] = he_so
            ds_ca.append({"ca": ten, "bien_doi": bd, "he_so": he_so, "chen": chen,
                          "do_dai_s": round(do_dai(os.path.join(RA, "ca", ten)), 2)})
            print(f"  {ten} ({time.time() - t0:.0f}s)", flush=True)
    for g in range(SO_CA_AM):
        x = ghep_nen(rng, nen, DAI_CA_AM_S)
        ten = f"am_{g}.m4a"
        ma_hoa(x, "", BIEN_DOI["goc"][2], os.path.join(RA, "ca", ten))
        ds_ca.append({"ca": ten, "bien_doi": "doi_chung_am", "he_so": 1.0, "chen": [],
                      "do_dai_s": round(do_dai(os.path.join(RA, "ca", ten)), 2)})
        print(f"  {ten}", flush=True)
    _ghi(os.path.join(RA, "dap_an.json"), {
        "seed": SEED, "kho_nguon": KHO_DO, "clip_kho": dai_clip, "nen_nguon": NEN, "giong": GIONG, "nhac": NHAC,
        "bien_doi": {k: {"loc": v[0], "he_so": v[1], "ma_hoa": v[2], "de": v[3]} for k, v in BIEN_DOI.items()},
        "ca": ds_ca})
    print(f"XONG dựng: {len(ds_ca)} ca ({time.time() - t0:.0f}s)")


def _engine():
    sc = sys.modules.get("sitecustomize")
    if sc is None or "chan_mang" not in os.path.abspath(sc.__file__):
        raise SystemExit("Chưa chặn mạng: PYTHONPATH=C:/Dev/pc2_test_tools/chan_mang")
    for bien in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_INSTALLATION_ID"):
        if os.environ.get(bien):
            raise SystemExit(f"Bỏ biến {bien}.")
    sys.path.insert(0, MA)
    import engine as eng
    tam = os.path.join(RA, "_engine")
    data, out = os.path.join(tam, "data"), os.path.join(tam, "ketqua")
    os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = data, out
    e = eng.Engine(root=MA, data_dir=data, out_dir=out)
    assert os.path.normcase(e.data_dir) == os.path.normcase(os.path.abspath(data)), e.data_dir
    dev = _doc(CAU_HINH_DEV)
    da_ap = {}
    for f in dataclasses.fields(e.config):
        if f.name in dev and f.name not in ("ncores",) and not f.name.startswith(("ytdlp", "dem_", "keep_")) \
                and isinstance(dev[f.name], (int, float, bool, list)) and not isinstance(getattr(e.config, f.name), str):
            if getattr(e.config, f.name) != dev[f.name]:
                da_ap[f.name] = dev[f.name]
            setattr(e.config, f.name, dev[f.name])
    e.config.ncores = 6
    e.config.tinh_chinh_moc = True
    e.config.validate()
    return eng, e, da_ap


def chay() -> None:
    dap_an = _doc(os.path.join(RA, "dap_an.json"))
    eng, e, da_ap = _engine()
    import bao_cao_v2
    kho = os.path.join(RA, "kho")
    kq_dir = os.path.join(RA, "ket_qua")
    os.makedirs(kq_dir, exist_ok=True)
    moc = os.path.join(RA, "_engine", "da_dung_kho.json")
    if not os.path.exists(moc):
        e.add_kho("Bo do DT03", kho)
        t0 = time.time()
        b = e.build_database(kho, "new")
        if b.get("thanh_cong") != len(os.listdir(kho)):
            raise RuntimeError(f"dựng kho không trọn: {b}")
        _ghi(moc, {"dung_kho": b, "giay": round(time.time() - t0, 1)})
        print(f"dựng kho {time.time() - t0:.0f}s", flush=True)
    _ghi(os.path.join(RA, "cau_hinh_da_dung.json"), {"khac_mac_dinh_lay_tu_DEV": da_ap, "ncores": e.config.ncores,
                                                     "tinh_chinh_moc": True,
                                                     "toan_bo": dataclasses.asdict(e.config)})
    for ca in dap_an["ca"]:
        dich = os.path.join(kq_dir, ca["ca"] + ".json")
        if os.path.exists(dich):
            continue
        t0 = time.time()
        kq = e.scan_media(os.path.join(RA, "ca", ca["ca"]))
        dong = []
        tc = list(getattr(kq, "tinh_chinh", []) or [])
        for i, m in enumerate(kq.matches):
            d = dataclasses.asdict(m)
            t = tc[i] if i < len(tc) else None
            d["tinh_chinh"] = t
            r = bao_cao_v2._moc_tinh_chinh(t, m)
            d["moc_tinh_chinh"] = list(r) if r else None
            dong.append(d)
        _ghi(dich, {"ca": ca["ca"], "trang_thai": kq.status, "ghi_chu": kq.note, "giay_quet": round(time.time() - t0, 1),
                    "duration_s": kq.duration_s, "matches": dong,
                    "matches_loai": [dataclasses.asdict(m) for m in kq.matches_loai]})
        print(f"{ca['ca']}: {kq.status}, {len(dong)} dòng, {time.time() - t0:.0f}s", flush=True)
    print("XONG chạy")


# ------------------------------------------------------------------------------------------------ chấm điểm
DUNG_SAI_S = 3.0


def _giao(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def cham_ca(ca: dict, kq: dict) -> dict:
    """Gán mỗi dòng cho đoạn chèn CÙNG clip giao nhiều nhất (vùng khớp nới DUNG_SAI_S); dòng không gán = báo nhầm."""
    dong = kq["matches"]
    gan = {}
    for j, m in enumerate(dong):
        best, bi = 0.0, None
        for i, c in enumerate(ca["chen"]):
            if m["clip"] != c["clip"]:
                continue
            g = _giao(m["vung_khop_s"] - DUNG_SAI_S, m["end_s"] + DUNG_SAI_S, c["video_tu"], c["video_den"])
            if g > best:
                best, bi = g, i
        if bi is not None:
            gan.setdefault(bi, []).append(j)
    ra = {"chen": [], "bao_nham": [dong[j] for j in range(len(dong)) if not any(j in v for v in gan.values())]}
    for i, c in enumerate(ca["chen"]):
        js = gan.get(i, [])
        r = {**{k: c[k] for k in ("clip", "dai_s", "video_tu", "video_den")}, "bat_duoc": bool(js), "so_dong": len(js)}
        if js:
            m = max((dong[j] for j in js), key=lambda m: _giao(m["vung_khop_s"], m["end_s"], c["video_tu"], c["video_den"]))
            r.update(sai_dau_s=round(m["vung_khop_s"] - c["video_tu"], 2), sai_cuoi_s=round(m["end_s"] - c["video_den"], 2),
                     hashes=m["hashes"], confidence=m["confidence"], moc_mo_ho=m.get("moc_mo_ho"),
                     tinh_chinh=(m.get("tinh_chinh") or {}).get("trang_thai"))
            if m.get("moc_tinh_chinh"):
                r["sai_dau_tc_s"] = round(m["moc_tinh_chinh"][0] - c["video_tu"], 2)
                r["sai_cuoi_tc_s"] = round(m["moc_tinh_chinh"][1] - c["video_den"], 2)
        ra["chen"].append(r)
    return ra


def _tk(xs: list) -> str:
    xs = [abs(x) for x in xs if x is not None]
    if not xs:
        return "—"
    xs.sort()
    p90 = xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))]
    return f"{statistics.median(xs):.1f} / {p90:.1f} / {xs[-1]:.1f}"


def cham() -> None:
    dap_an = _doc(os.path.join(RA, "dap_an.json"))
    tung_ca, thieu = [], []
    for ca in dap_an["ca"]:
        p = os.path.join(RA, "ket_qua", ca["ca"] + ".json")
        if not os.path.exists(p):
            thieu.append(ca["ca"])
            continue
        kq = _doc(p)
        tung_ca.append({"ca": ca["ca"], "bien_doi": ca["bien_doi"], "do_dai_s": ca["do_dai_s"],
                        "giay_quet": kq["giay_quet"], "trang_thai": kq["trang_thai"], **cham_ca(ca, kq)})
    _ghi(os.path.join(RA, "cham_diem.json"), {"tung_ca": tung_ca, "chua_chay": thieu})
    L = ["# DT-03 giai đoạn 1 — bộ đo độ đúng (audio kho thật, engine thật)", "",
         f"Kho đo: {len(dap_an['clip_kho'])} clip SML thật (chép, chỉ đọc E:). Mỗi ca: nền {DAI_CA_S} s ghép từ kênh khác "
         f"(Ms Rachel, Mr Ballen, Cory, MSA) + 5 đoạn clip chèn {DO_DAI_CHEN} s. Cấu hình khớp = DEV, tinh chỉnh BẬT. "
         f"«Bắt được» = có dòng đúng clip giao đoạn thật (nới {DUNG_SAI_S:g} s).", ""]
    if thieu:
        L += [f"**Chưa chạy {len(thieu)} ca:** {', '.join(thieu)}", ""]
    duong = [c for c in tung_ca if c["bien_doi"] != "doi_chung_am"]
    L += ["## Tỉ lệ bắt được theo biến đổi × độ dài đoạn chèn", "",
          "| Biến đổi | " + " | ".join(f"{x} s" for x in DO_DAI_CHEN) + " | Báo nhầm (dòng) | Giây quét TB |",
          "|---|" + "---|" * (len(DO_DAI_CHEN) + 2)]
    for bd in BIEN_DOI:
        cs = [c for c in duong if c["bien_doi"] == bd]
        if not cs:
            continue
        o = []
        for x in DO_DAI_CHEN:
            r = [h for c in cs for h in c["chen"] if h["dai_s"] == x]
            o.append(f"{sum(h['bat_duoc'] for h in r)}/{len(r)}")
        L.append(f"| {bd} | " + " | ".join(o) + f" | {sum(len(c['bao_nham']) for c in cs)} | "
                 f"{statistics.mean(c['giay_quet'] for c in cs):.0f} |")
    hs = [h for c in duong for h in c["chen"] if h["bat_duoc"]]
    L += ["", "## Lệch mốc «Đoạn vi phạm» (giây; trung vị / p90 / lớn nhất của |lệch|) trên các đoạn bắt được", "",
          "| Nhóm | Số đoạn | Đầu — lượt quét | Cuối — lượt quét | Số đã tinh chỉnh | Đầu — tinh chỉnh | Cuối — tinh chỉnh |",
          "|---|---|---|---|---|---|---|"]
    for bd in ["(tất cả)"] + list(BIEN_DOI):
        r = hs if bd == "(tất cả)" else [h for c in duong if c["bien_doi"] == bd for h in c["chen"] if h["bat_duoc"]]
        if not r:
            continue
        tc = [h for h in r if "sai_dau_tc_s" in h]
        L.append(f"| {bd} | {len(r)} | {_tk([h['sai_dau_s'] for h in r])} | {_tk([h['sai_cuoi_s'] for h in r])} | "
                 f"{len(tc)} | {_tk([h['sai_dau_tc_s'] for h in tc])} | {_tk([h['sai_cuoi_tc_s'] for h in tc])} |")
    am = [c for c in tung_ca if c["bien_doi"] == "doi_chung_am"]
    gio_am = sum(c["do_dai_s"] for c in am) / 3600
    gio_duong = sum(c["do_dai_s"] for c in duong) / 3600
    bn_am = sum(len(c["bao_nham"]) for c in am)
    bn_duong = sum(len(c["bao_nham"]) for c in duong)
    L += ["", "## Báo nhầm", "",
          f"- Đối chứng âm: {bn_am} dòng trên {gio_am:.1f} giờ (≈ {bn_am / gio_am * 100 if gio_am else 0:.0f} dòng / 100 giờ, "
          f"kho {len(dap_an['clip_kho'])} clip — kho thật lớn hơn 10–30 lần nên số thật có thể cao hơn).",
          f"- Trong ca có chèn: {bn_duong} dòng không thuộc đoạn chèn nào trên {gio_duong:.1f} giờ."]
    for c in am + duong:
        for m in c["bao_nham"]:
            L.append(f"  - {c['ca']}: {m['clip']} @ {m['vung_khop_s']:.0f}–{m['end_s']:.0f} s, {m['hashes']} hash, "
                     f"«{m['confidence']}»")
    mo_ho = [h for h in hs if h.get("moc_mo_ho")]
    trang = {}
    for h in hs:
        trang[h.get("tinh_chinh")] = trang.get(h.get("tinh_chinh"), 0) + 1
    tin = {}
    for h in hs:
        tin[h.get("confidence")] = tin.get(h.get("confidence"), 0) + 1
    L += ["", "## Cờ và nhãn", "", f"- Mốc mơ hồ: {len(mo_ho)}/{len(hs)} đoạn bắt được.",
          f"- Trạng thái tinh chỉnh: {trang}", f"- Nhãn độ tin cậy: {tin}"]
    with open(os.path.join(RA, "BAO_CAO_DO_DUNG.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    {"dung": dung, "chay": chay, "cham": cham}[sys.argv[1]]()
