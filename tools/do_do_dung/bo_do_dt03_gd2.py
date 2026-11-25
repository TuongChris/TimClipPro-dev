# -*- coding: utf-8 -*-
"""DT-03 giai đoạn 2 — dùng lại bo_do_dt03 (helper, engine, chạy) với kho ĐỦ 779 clip SML và bộ ca mới:
  dai   : đoạn chèn 300/600/900 s × {goc, nen_24k, nhac_de, giong_de} × 3 (mỗi file 1 đoạn)
  bien  : vùng 30–60 s (30/40/45/50/60) × 4 biến đổi × 12 file (5 đoạn/file)
  cao   : chẩn đoán cao độ: {goc, cao_do_05, cao_do_1, ha_do_1, tua_5} × 3 file (đoạn 120 s + 300 s)
  am    : 60 file × 1200 s đối chứng âm từ 7 kênh khác
Chấm thêm: đoạn bị sót có dòng ĐÚNG clip trong matches_loai (bị ngưỡng loại) không, với bao nhiêu hash.
  PYTHONPATH=C:/Dev/pc2_test_tools/chan_mang <venv>/python.exe -B -X utf8 bo_do_dt03_gd2.py dung|chay|cham
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bo_do_dt03 as bo  # noqa: E402

import random  # noqa: E402
import shutil  # noqa: E402
import statistics  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

bo.RA = r"C:\Dev\pc2_test_runs\2026-11-25_dt03_gd2"
SR = bo.SR
NEN2 = bo.NEN + [r"E:\Kho_Tool_Quet\Kho_Layze", r"E:\Kho_Tool_Quet\Kho_Danny", r"E:\Kho_Tool_Quet\Kho_Papa_Meat"]
A = ["-c:a", "aac", "-b:a", "128k"]
bo.BIEN_DOI.update({
    "cao_do_05": (f"asetrate={SR * 1.029302:.0f},aresample={SR},atempo={1 / 1.029302:.6f}", 1.0, A, None),
    "ha_do_1": (f"asetrate={SR / 1.059463:.0f},aresample={SR},atempo={1.059463:.6f}", 1.0, A, None),
})
BON = ["goc", "nen_24k", "nhac_de", "giong_de"]
SEED2 = 2512


def _file(rng, ten, bd, nen, giong, nhac, kho, dai_ca, cac_L, ds_ca):
    loc, he_so, ma, de = bo.BIEN_DOI[bd]
    x = bo.ghep_nen(rng, nen, dai_ca)
    rng.shuffle(cac_L)
    o = dai_ca / len(cac_L)
    chen = []
    for i, L in enumerate(cac_L):
        hop_le = [(p, d) for p, d in kho if d >= L + 2]
        if not hop_le:
            continue
        p, d = rng.choice(hop_le)
        c_tu = round(rng.uniform(0, d - L - 1), 2)
        v_tu = round(rng.uniform(i * o + 20, (i + 1) * o - L - 20), 2)
        seg = bo.doc_pcm(p, c_tu, L)
        a = int(round(v_tu * SR))
        x[a:a + len(seg)] = seg
        chen.append({"clip": os.path.basename(p), "clip_tu": c_tu, "clip_den": round(c_tu + L, 2),
                     "v_tu_goc": v_tu, "v_den_goc": round(v_tu + L, 2), "dai_s": L})
    if de:
        kieu, db = de
        ov = bo.ghep_nen(rng, nhac if kieu == "nhac" else giong, dai_ca)
        x = x + ov * (bo.rms(x) / bo.rms(ov)) * 10 ** (db / 20)
        x = x / max(1.0, float(np.max(np.abs(x))))
    ten = ten + bo.DUOI.get(ma[ma.index("-c:a") + 1], ".m4a")
    bo.ma_hoa(x, loc, ma, os.path.join(bo.RA, "ca", ten))
    for c in chen:
        c["video_tu"] = round(c["v_tu_goc"] / he_so, 3)
        c["video_den"] = round(c["v_den_goc"] / he_so, 3)
        c["he_so"] = he_so
    ds_ca.append({"ca": ten, "bien_doi": bd, "he_so": he_so, "chen": chen,
                  "do_dai_s": round(bo.do_dai(os.path.join(bo.RA, "ca", ten)), 2)})


def dung():
    rng = random.Random(SEED2)
    RA = bo.RA
    if os.path.isdir(os.path.join(RA, "ca")):
        raise SystemExit("Đã có thư mục ca — xoá trước khi dựng lại.")
    os.makedirs(os.path.join(RA, "kho"))
    os.makedirs(os.path.join(RA, "ca"))
    t0 = time.time()
    kho = []
    for f in sorted(os.listdir(bo.KHO_DO)):
        if f.lower().endswith(".opus"):
            p = os.path.join(bo.KHO_DO, f)
            shutil.copy2(p, os.path.join(RA, "kho", f))           # chỉ ĐỌC E:
            kho.append((p, bo.do_dai(p)))
    print(f"kho {len(kho)} clip ({time.time() - t0:.0f}s); dài nhất {max(d for _, d in kho):.0f}s", flush=True)
    nen = [x for tm in NEN2 for x in bo._chon(rng, tm, 15, 120, 4000)]
    giong = bo._chon(rng, bo.GIONG, 8, 300, 4000)
    nhac = bo._chon(rng, bo.NHAC, 8, 300, 4000)
    ds = []
    for L in (300, 600, 900):
        for bd in BON:
            for g in range(3):
                _file(rng, f"dai_{L}_{bd}_{g}", bd, nen, giong, nhac, kho, 1200, [L], ds)
    print(f"xong dai ({time.time() - t0:.0f}s)", flush=True)
    for bd in BON:
        for g in range(12):
            _file(rng, f"bien_{bd}_{g}", bd, nen, giong, nhac, kho, 1200, [30, 40, 45, 50, 60], ds)
    print(f"xong bien ({time.time() - t0:.0f}s)", flush=True)
    for bd in ("goc", "cao_do_05", "cao_do_1", "ha_do_1", "tua_5"):
        for g in range(3):
            _file(rng, f"cao_{bd}_{g}", bd, nen, giong, nhac, kho, 1200, [120, 300], ds)
    print(f"xong cao ({time.time() - t0:.0f}s)", flush=True)
    for g in range(60):
        x = bo.ghep_nen(rng, nen, 1200)
        ten = f"am_{g}.m4a"
        bo.ma_hoa(x, "", A, os.path.join(RA, "ca", ten))
        ds.append({"ca": ten, "bien_doi": "doi_chung_am", "he_so": 1.0, "chen": [],
                   "do_dai_s": round(bo.do_dai(os.path.join(RA, "ca", ten)), 2)})
    bo._ghi(os.path.join(RA, "dap_an.json"), {
        "seed": SEED2, "kho_nguon": bo.KHO_DO, "clip_kho": {os.path.basename(p): d for p, d in kho}, "nen_nguon": NEN2,
        "bien_doi": {k: {"loc": v[0], "he_so": v[1], "ma_hoa": v[2], "de": v[3]} for k, v in bo.BIEN_DOI.items()},
        "ca": ds})
    print(f"XONG dựng: {len(ds)} ca ({time.time() - t0:.0f}s)")


def chay():
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)   # nhường DEV của người dùng
    except Exception:  # noqa: BLE001
        pass
    bo.chay()


def _cham_ca(ca, kq):
    r = bo.cham_ca(ca, kq)
    for h, c in zip(r["chen"], ca["chen"]):
        if h["bat_duoc"]:
            continue
        loai = [m for m in kq.get("matches_loai") or [] if m["clip"] == c["clip"]
                and bo._giao(m["vung_khop_s"] - 3, m["end_s"] + 3, c["video_tu"], c["video_den"]) > 0]
        if loai:
            h["bi_loai_hash"] = max(m["hashes"] for m in loai)
    return r


def _ty(rs):
    return f"{sum(h['bat_duoc'] for h in rs)}/{len(rs)}" if rs else "—"


def cham():
    RA = bo.RA
    da = bo._doc(os.path.join(RA, "dap_an.json"))
    tung, thieu = [], []
    for ca in da["ca"]:
        p = os.path.join(RA, "ket_qua", ca["ca"] + ".json")
        if not os.path.exists(p):
            thieu.append(ca["ca"])
            continue
        kq = bo._doc(p)
        tung.append({"ca": ca["ca"], "bien_doi": ca["bien_doi"], "do_dai_s": ca["do_dai_s"], "giay_quet": kq["giay_quet"],
                     "nhom": ca["ca"].split("_")[0], **_cham_ca(ca, kq)})
    bo._ghi(os.path.join(RA, "cham_diem.json"), {"tung_ca": tung, "chua_chay": thieu})
    L = ["# DT-03 giai đoạn 2 — bảng chấm tự động", "",
         f"Kho đo: {len(da['clip_kho'])} clip SML (đủ kho). Cấu hình khớp = DEV, tinh chỉnh BẬT. Đã chạy {len(tung)}/{len(da['ca'])} ca.",
         ""]
    if thieu:
        L += [f"Chưa chạy: {len(thieu)} ca.", ""]

    def bang(nhom, cac_bd, cac_L, tieu_de):
        L.extend([f"## {tieu_de}", "", "| Biến đổi | " + " | ".join(f"{x} s" for x in cac_L) +
                  " | Bị sàn loại (sót nhưng có dòng bị loại) | Báo nhầm | Giây quét TB |", "|---|" + "---|" * (len(cac_L) + 3)])
        for bd in cac_bd:
            cs = [c for c in tung if c["nhom"] == nhom and c["bien_doi"] == bd]
            if not cs:
                continue
            o = [_ty([h for c in cs for h in c["chen"] if h["dai_s"] == x]) for x in cac_L]
            bl = [h["bi_loai_hash"] for c in cs for h in c["chen"] if "bi_loai_hash" in h]
            L.append(f"| {bd} | " + " | ".join(o) + f" | {len(bl)} {sorted(bl)[:8] if bl else ''} | "
                     f"{sum(len(c['bao_nham']) for c in cs)} | {statistics.mean(c['giay_quet'] for c in cs):.0f} |")
        L.append("")

    bang("dai", BON, [300, 600, 900], "Đoạn dài")
    bang("bien", BON, [30, 40, 45, 50, 60], "Vùng ranh giới 30–60 s")
    bang("cao", ["goc", "cao_do_05", "cao_do_1", "ha_do_1", "tua_5"], [120, 300], "Chẩn đoán cao độ")
    hs = [h for c in tung if c["nhom"] != "am" for h in c["chen"] if h["bat_duoc"]]
    L += ["## Lệch mốc (giây; trung vị / p90 / lớn nhất |lệch|) trên đoạn bắt được", "",
          "| Nhóm | Số đoạn | Đầu lượt quét | Cuối lượt quét | Đã tinh chỉnh | Đầu tinh chỉnh | Cuối tinh chỉnh | Tinh chỉnh lệch > 1 s |",
          "|---|---|---|---|---|---|---|---|"]
    for nh in ("(tất cả)", "dai", "bien", "cao"):
        r = hs if nh == "(tất cả)" else [h for c in tung if c["nhom"] == nh for h in c["chen"] if h["bat_duoc"]]
        if not r:
            continue
        tc = [h for h in r if "sai_dau_tc_s" in h]
        xau = sum(abs(h["sai_dau_tc_s"]) > 1 or abs(h["sai_cuoi_tc_s"]) > 1 for h in tc)
        L.append(f"| {nh} | {len(r)} | {bo._tk([h['sai_dau_s'] for h in r])} | {bo._tk([h['sai_cuoi_s'] for h in r])} | "
                 f"{len(tc)} | {bo._tk([h['sai_dau_tc_s'] for h in tc])} | {bo._tk([h['sai_cuoi_tc_s'] for h in tc])} | {xau} |")
    am = [c for c in tung if c["nhom"] == "am"]
    gio = sum(c["do_dai_s"] for c in am) / 3600
    bn = [(c["ca"], m) for c in tung for m in c["bao_nham"]]
    L += ["", "## Báo nhầm", "", f"- Đối chứng âm: {sum(len(c['bao_nham']) for c in am)} dòng / {gio:.1f} giờ.",
          f"- Tổng dòng không thuộc đoạn chèn nào (mọi ca): {len(bn)}."]
    for ca, m in bn[:40]:
        L.append(f"  - {ca}: {m['clip']} @ {m['vung_khop_s']:.0f}–{m['end_s']:.0f} s, {m['hashes']} hash, khớp {m['matched_s']:.0f} s")
    trang, mo_ho = {}, 0
    for h in hs:
        trang[h.get("tinh_chinh")] = trang.get(h.get("tinh_chinh"), 0) + 1
        mo_ho += bool(h.get("moc_mo_ho"))
    L += ["", f"- Trạng thái tinh chỉnh: {trang}; mốc mơ hồ: {mo_ho}/{len(hs)}.", ""]
    with open(os.path.join(RA, "BANG_CHAM_GD2.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    {"dung": dung, "chay": chay, "cham": cham}[sys.argv[1]]()
