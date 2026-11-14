# -*- coding: utf-8 -*-
"""Kiểm TRONG MẪU bước «tinh chỉnh mốc từng giây» (TimClipPro/tinh_chinh_moc.py, P-8) — engine THẬT + audfprint THẬT.

Dữ liệu: 27 tình huống audio GIẢ LẬP — 25 của nghiên cứu 14/11 (bộ thử S0–S9, S4b, S5b, S6b, S7b, S7c; X1–X3 của Cách
C; H1a–H4 của phản biện đo lường) + A03, A05 của bộ kiểm NGOÀI MẪU vòng 1 (hỏng ở vòng 1 nên thành trong mẫu: giọng nói
đè 0 dB một phần ba giữa; im lặng tuyệt đối 4 s giữa đoạn). Mỗi thư mục có ``su_that.json``, video vi phạm và ``kho\\``.
Chỉ ĐỌC các thư mục đó: kho được chép sang thư mục tạm rồi dựng vân tay ở đó; engine ghi data/out vào thư mục tạm.
Không dữ liệu thật, không mạng.

Mỗi tình huống, lần lượt (một engine một lúc): dựng kho → ``scan_media`` với ``config.tinh_chinh_moc = True`` (+ đổi
cấu hình của tình huống ``cau_hinh_engine_doi``) → đọc ``kq.tinh_chinh`` và chấm với sự thật:
  - từng đoạn thật: sai số mép video/clip của đoạn tinh chỉnh phủ nó nhiều nhất (bỏ sót nếu không đoạn nào phủ);
  - đúng/đủ theo giây trên trục video (độ dài giao, như ``bo_thu/danh_gia.py``) — so với khoảng của engine;
  - chỗ cắt bịa / bỏ sót (ranh giới giữa hai đoạn liên tiếp, lệch ≤ 1 s mỗi đầu là khớp); dòng «chưa tinh chỉnh» + lý do.
Ghi ``<RA>\\<S>\\ket_qua.json`` (dòng engine kèm neo + kết quả tinh chỉnh + chấm) và ``<RA>\\tong_hop.{json,md}``.

Chế độ:
  (mặc định)     engine bật tinh chỉnh — số liệu cuối cùng.
  --chi-engine   engine TẮT tinh chỉnh, chỉ lưu dòng engine (để phát lại khi hiệu chỉnh — kết quả quét không đổi theo cờ).
  --phat-lai     KHÔNG chạy engine: gọi tinh_chinh_moc trên dòng engine đã lưu (như engine gọi) rồi chấm.
  --ra THƯ_MỤC   ghi kết quả vào thư mục khác (dòng engine để phát lại vẫn đọc từ ``RA`` mặc định) — giữ nguyên bản lưu
                 của vòng trước để so.
Chạy (Git Bash, ~20–60 s mỗi tình huống):
  cd /c/Dev/Tool_Quet/TimClipPro
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \\
      -B -X utf8 ../tools/khop_tung_giay/san_pham/kiem_trong_mau.py [--tat-ca | S1 H3 ...] [--chi-engine | --phat-lai]
  Tự kiểm phần chấm (không cần audio): ``kiem_trong_mau.py --tu-kiem``.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "TimClipPro"))  # checkout chứa file này
CHAN_MANG = os.path.join(os.path.dirname(MA), "tools", "test", "chan_mang")
GOC = r"C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay"
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\trong_mau"
THU_MUC = {**{S: os.path.join(GOC, "bo_thu", S) for S in ("S1", "S2", "S3", "S4", "S4b", "S5", "S5b", "S6", "S6b",
                                                          "S7", "S7b", "S7c", "S8", "S9", "S0")},
           **{S: os.path.join(GOC, "cach_c", "them", S) for S in ("X1", "X2", "X3")},
           **{S: os.path.join(GOC, "phan_bien_do_luong", "ca_kho", S)
              for S in ("H1a", "H1b", "H1c", "H2a", "H2b", "H3", "H4")},
           "A03": r"C:\Dev\pc2_test_runs\2026-11-14_p8\ca_an\A03_giong_noi_giua",
           "A05": r"C:\Dev\pc2_test_runs\2026-11-14_p8\ca_an\A05_im_lang_4s"}
TRUONG_DONG = ("clip", "start_s", "end_s", "vung_khop_s", "clip_offset_s", "matched_s", "hashes", "confidence",
               "he_so", "ho", "neo", "moc_mo_ho")
DUNG_SAI_CAT_S = 1.0


# ---------------------------------------------------------------------------------------------- chấm (hàm thuần)

def _hop(khoang) -> list:
    ra: list = []
    for a, b in sorted((float(a), float(b)) for a, b in khoang if b > a):
        if ra and a <= ra[-1][1]:
            ra[-1][1] = max(ra[-1][1], b)
        else:
            ra.append([a, b])
    return [tuple(x) for x in ra]


def _dai(khoang) -> float:
    return sum(b - a for a, b in _hop(khoang))


def _giao(x, y) -> list:
    return _hop([(max(a, c), min(b, d)) for a, b in _hop(x) for c, d in _hop(y) if min(b, d) > max(a, c)])


def _pr(bao: list, that: list) -> tuple:
    g, db, dt = _dai(_giao(bao, that)), _dai(bao), _dai(that)
    return (round(g / db, 4) if db else None, round(g / dt, 4) if dt else None)


def cham(doan_that: list, dong: list) -> dict:
    """``doan_that``: đoạn sự thật {video_tu, video_den, clip_tu, clip_den, he_so}; ``dong``: dòng engine của ĐÚNG clip
    sự thật, mỗi dòng có ``tinh_chinh`` (dict của tinh_chinh_moc). Trả số liệu chấm (xem docstring module)."""
    that = sorted(doan_that, key=lambda d: d["video_tu"])
    kt = [(d["video_tu"], d["video_den"]) for d in that]
    da = [x for x in dong if x["tinh_chinh"].get("trang_thai") == "da_tinh_chinh"]
    doan = sorted((d for x in da for d in x["tinh_chinh"]["doan"]), key=lambda d: d["video_tu"])
    kb = [(d["video_tu"], d["video_den"]) for d in doan]
    ra = {"so_dong": len(dong), "so_dong_da": len(da),
          "chua": [x["tinh_chinh"].get("ly_do", "") for x in dong if x not in da],
          "pr_tinh_chinh": _pr(kb, kt) if kt else (None, None),
          "pr_engine_start_end": _pr([(x["start_s"], x["end_s"]) for x in dong], kt) if kt else (None, None),
          "pr_engine_vung_end": _pr([(x["vung_khop_s"], x["end_s"]) for x in dong], kt) if kt else (None, None),
          "giay_bao_ngoai_that": round(_dai(kb) - _dai(_giao(kb, kt)), 3),
          "doan_bia": sum(1 for a, b in kb if not _giao([(a, b)], kt)),
          "tung_doan_that": [], "cat_bia": [], "cat_sot": []}
    for t in that:
        phu = [d for d in doan if _giao([(d["video_tu"], d["video_den"])], [(t["video_tu"], t["video_den"])])]
        if not phu:
            ra["tung_doan_that"].append({"that": [t["video_tu"], t["video_den"], t["clip_tu"], t["clip_den"]],
                                         "bo_sot": True})
            continue
        g = max(phu, key=lambda d: _dai(_giao([(d["video_tu"], d["video_den"])], [(t["video_tu"], t["video_den"])])))
        ra["tung_doan_that"].append({
            "that": [t["video_tu"], t["video_den"], t["clip_tu"], t["clip_den"]],
            "tim": [g["video_tu"], g["video_den"], g["clip_tu"], g["clip_den"]], "bo_sot": False,
            "loi_video_tu": round(g["video_tu"] - t["video_tu"], 3), "loi_video_den": round(g["video_den"] - t["video_den"], 3),
            "loi_clip_tu": round(g["clip_tu"] - t["clip_tu"], 3), "loi_clip_den": round(g["clip_den"] - t["clip_den"], 3),
            "k_that": round(1.0 / t["he_so"], 5), "k_tim": g.get("k"), "cach_tim_mep": g.get("cach_tim_mep")})
    ranh_that = [(a["video_den"], b["video_tu"]) for a, b in zip(that, that[1:])]
    ranh_bao = [(a["video_den"], b["video_tu"]) for a, b in zip(doan, doan[1:])]

    def khop(r, s) -> bool:
        return abs(r[0] - s[0]) <= DUNG_SAI_CAT_S and abs(r[1] - s[1]) <= DUNG_SAI_CAT_S
    ra["cat_bia"] = [list(r) for r in ranh_bao if not any(khop(r, s) for s in ranh_that)]
    tim_ca_hai = [i for i in range(len(that) - 1)
                  if not ra["tung_doan_that"][i]["bo_sot"] and not ra["tung_doan_that"][i + 1]["bo_sot"]]
    ra["cat_sot"] = [list(ranh_that[i]) for i in tim_ca_hai if not any(khop(r, ranh_that[i]) for r in ranh_bao)]
    loi = [abs(e[k]) for e in ra["tung_doan_that"] if not e["bo_sot"]
           for k in ("loi_video_tu", "loi_video_den", "loi_clip_tu", "loi_clip_den")]
    ra["loi_mep_max_s"] = round(max(loi), 3) if loi else None
    return ra


def _tu_kiem() -> None:
    that = [{"video_tu": 250.0, "video_den": 450.0, "clip_tu": 0.0, "clip_den": 200.0, "he_so": 1.0},
            {"video_tu": 455.0, "video_den": 720.0, "clip_tu": 215.0, "clip_den": 480.0, "he_so": 1.0}]

    def d(vt, vd, ct, cd):
        return {"video_tu": vt, "video_den": vd, "clip_tu": ct, "clip_den": cd, "k": 1.0, "cach_tim_mep": ["x", "x"]}
    dong = [{"start_s": 250.0, "vung_khop_s": 260.0, "end_s": 700.0, "tinh_chinh": {
        "trang_thai": "da_tinh_chinh", "doan": [d(250.01, 449.99, 0.01, 199.99), d(455.02, 719.9, 215.02, 479.9)]}}]
    kq = cham(that, dong)
    assert kq["cat_bia"] == [] and kq["cat_sot"] == [] and kq["doan_bia"] == 0, kq
    assert kq["tung_doan_that"][1]["loi_video_tu"] == 0.02 and kq["loi_mep_max_s"] == 0.1, kq
    assert kq["pr_tinh_chinh"][0] == 1.0 and kq["pr_tinh_chinh"][1] == round((199.98 + 264.88) / 465.0, 4), kq
    # một đoạn duy nhất phủ cả hai đoạn thật: không có chỗ cắt nào được báo → bỏ sót chỗ cắt
    dong[0]["tinh_chinh"]["doan"] = [d(250.0, 720.0, 0.0, 470.0)]
    kq = cham(that, dong)
    assert kq["cat_sot"] == [[450.0, 455.0]] and kq["giay_bao_ngoai_that"] == 5.0, kq
    # chỗ cắt bịa giữa một đoạn thật + dòng chưa tinh chỉnh
    dong.append({"start_s": 0, "vung_khop_s": 0, "end_s": 1, "tinh_chinh": {"trang_thai": "chua_tinh_chinh",
                                                                            "ly_do": "x"}})
    dong[0]["tinh_chinh"]["doan"] = [d(250.0, 300.0, 0.0, 50.0), d(330.0, 450.0, 80.0, 200.0)]
    kq = cham(that, dong)
    assert kq["cat_bia"] == [[300.0, 330.0]] and kq["chua"] == ["x"] and kq["tung_doan_that"][1]["bo_sot"], kq
    print("kiem_trong_mau: tự kiểm phần chấm ĐẠT")


# ---------------------------------------------------------------------------------------------- engine + phát lại

def _kiem_moi_truong() -> None:
    sc = sys.modules.get("sitecustomize")
    if sc is None or os.path.normcase(os.path.dirname(os.path.abspath(sc.__file__))) != os.path.normcase(CHAN_MANG):
        raise SystemExit(f"Chưa nạp sitecustomize chặn mạng — chạy với PYTHONPATH={CHAN_MANG}")
    for bien in ("TIMCLIP_RUNTIME_MODE", "TIMCLIP_STATE_ROOT", "TIMCLIP_INSTALLATION_ID"):
        if os.environ.get(bien):
            raise SystemExit(f"Bỏ biến {bien} trước khi chạy: chỉ chạy legacy trên thư mục tạm.")
    for lenh in ("ffmpeg", "ffprobe"):
        if shutil.which(lenh) is None:
            raise SystemExit(f"Cần {lenh} trong PATH.")


def _json(p: str):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _ghi(p: str, obj) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


def _dong_engine(m, kho_goc: str) -> dict:
    """Trường Match cần cho phát lại; đường dẫn kho tạm đổi về file clip GỐC của tình huống (cùng nội dung)."""
    x = {k: getattr(m, k) for k in TRUONG_DONG}
    x["neo"] = [list(a) for a in x["neo"]]
    x["duong_dan_kho"] = os.path.join(kho_goc, os.path.basename(m.duong_dan_kho))
    return x


def chay_engine(S: str, bat_tinh_chinh: bool) -> dict:
    import engine as eng
    d = THU_MUC[S]
    st = _json(os.path.join(d, "su_that.json"))
    tam = tempfile.mkdtemp(prefix=f"p8_tm_{S}_")
    try:
        kho = os.path.join(tam, "kho")
        shutil.copytree(os.path.join(d, "kho"), kho)
        data, out = os.path.join(tam, "data"), os.path.join(tam, "out")
        os.environ["TIMCLIP_DATA_DIR"], os.environ["TIMCLIP_OUTPUT_DIR"] = data, out
        e = eng.Engine(root=MA, data_dir=data, out_dir=out)
        assert os.path.normcase(e.data_dir) == os.path.normcase(os.path.abspath(data)), e.data_dir
        e.config.ncores = 2
        for k, v in (st.get("cau_hinh_engine_doi") or {}).items():
            setattr(e.config, k, v)
        e.config.tinh_chinh_moc = bat_tinh_chinh
        e.config.validate()
        e.add_kho(f"Trong mau {S}", kho)
        t = time.perf_counter()
        kb = e.build_database(kho, "new")
        t_kho = time.perf_counter() - t
        if kb.get("thanh_cong") != len(os.listdir(os.path.join(d, "kho"))):
            raise RuntimeError(f"Dựng kho không trọn: {kb}")
        t = time.perf_counter()
        kq = e.scan_media(os.path.join(d, st["video"]))
        t_quet = time.perf_counter() - t
        if kq.status != "ok":
            raise RuntimeError(f"Quét lỗi: {kq.note}")
        dong = [_dong_engine(m, os.path.join(d, "kho")) for m in kq.matches]
        if bat_tinh_chinh:
            assert [x["clip"] for x in kq.tinh_chinh] == [x["clip"] for x in dong]
            for x, tc in zip(dong, kq.tinh_chinh):
                x["tinh_chinh"] = tc
        return {"dong": dong, "duration_s": kq.duration_s, "pham_vi_quet_s": kq.pham_vi_quet_s,
                "thoi_gian_dung_kho_s": round(t_kho, 1), "thoi_gian_quet_s": round(t_quet, 1),
                "tinh_chinh_bat": bat_tinh_chinh}
    finally:
        shutil.rmtree(tam, ignore_errors=True)


def phat_lai(S: str, luu: dict) -> dict:
    """Gọi tinh_chinh_moc như ``Engine._tinh_chinh_ket_qua`` (bỏ dòng mốc mơ hồ / lưới cao độ y như engine)."""
    import tinh_chinh_moc as tcm
    d = THU_MUC[S]
    st = _json(os.path.join(d, "su_that.json"))
    den = float(luu["pham_vi_quet_s"] or luu["duration_s"] or 0.0)
    for x in luu["dong"]:
        if x["moc_mo_ho"]:
            x["tinh_chinh"] = {"trang_thai": tcm.CHUA, "ly_do": "(engine bỏ qua: mốc mơ hồ)"}
            continue
        if x["ho"] == "resample":
            x["tinh_chinh"] = {"trang_thai": tcm.CHUA, "ly_do": "(engine bỏ qua: lưới cao độ)"}
            continue
        neo = [tuple(a) for a in x["neo"]] or [(x["vung_khop_s"] - x["he_so"] * x["clip_offset_s"], x["he_so"])]
        try:
            x["tinh_chinh"] = tcm.tinh_chinh_dong(x["duong_dan_kho"], os.path.join(d, st["video"]), neo,
                                                  x["vung_khop_s"], x["end_s"],
                                                  pham_vi_s=(0.0, den) if den > 0 else None)
        except Exception as e:  # noqa: BLE001 — như engine: lỗi chỉ thành «chưa tinh chỉnh»
            x["tinh_chinh"] = {"trang_thai": tcm.CHUA, "ly_do": f"Lỗi khi tinh chỉnh: {e!r}"}
    luu["tinh_chinh_bat"] = "phat_lai"
    return luu


def _ten_clip(st: dict) -> str:
    """Clip sự thật: ``ten_clip`` (bộ thử 14/11) hoặc «clip» của đoạn (bộ kiểm ngoài mẫu); đối chứng âm: rỗng."""
    return st.get("ten_clip") or next((x["clip"] for x in st.get("doan") or () if x.get("clip")), "")


def mot_tinh_huong(S: str, che_do: str, ra: str = RA) -> dict:
    st = _json(os.path.join(THU_MUC[S], "su_that.json"))
    p = os.path.join(ra, S, "ket_qua.json")
    if che_do == "phat_lai":
        luu = phat_lai(S, _json(os.path.join(RA, S, "ket_qua.json")))
    else:
        luu = chay_engine(S, che_do == "bat")
    if che_do == "chi_engine":
        _ghi(p, luu)
        return {"S": S, "so_dong": len(luu["dong"])}
    ten = _ten_clip(st)
    cua_clip = [x for x in luu["dong"] if x["clip"] == ten]
    khac = [x for x in luu["dong"] if x["clip"] != ten]
    luu["cham"] = cham(st["doan"], cua_clip) if ten else None
    luu["dong_clip_khac_da_tinh_chinh"] = sum(1 for x in khac if x["tinh_chinh"].get("trang_thai") == "da_tinh_chinh")
    luu["thoi_gian_tinh_chinh_s"] = [x["tinh_chinh"].get("thoi_gian_s") for x in luu["dong"]]
    _ghi(p, luu)
    return {"S": S, **(luu["cham"] or {}), "dong_clip_khac_da": luu["dong_clip_khac_da_tinh_chinh"],
            "thoi_gian_tinh_chinh_s": luu["thoi_gian_tinh_chinh_s"], "thoi_gian_quet_s": luu.get("thoi_gian_quet_s")}


def _o(x) -> str:
    return "—" if x is None else (f"{x:g}" if isinstance(x, float) else str(x))


def bang(hang: list) -> str:
    dong = ["| Tình huống | Dòng (đã TC) | Đúng/đủ theo giây TC | Engine start–end | Lỗi mép lớn nhất (s) | "
            "Đoạn thật: lỗi video_tu/video_den/clip_tu/clip_den (s) | Cắt bịa / sót | Chưa TC: lý do | TC (s) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for h in hang:
        if "loi" in h:
            dong.append(f"| {h['S']} | LỖI | | | | {h['loi'][:120]} | | | |")
            continue
        td = "; ".join("bỏ sót" if e["bo_sot"] else
                       f"{e['loi_video_tu']:+.3f}/{e['loi_video_den']:+.3f}/{e['loi_clip_tu']:+.3f}/{e['loi_clip_den']:+.3f}"
                       for e in h.get("tung_doan_that", []))
        p, r = h.get("pr_tinh_chinh", (None, None))
        pe, re_ = h.get("pr_engine_start_end", (None, None))
        chua = "; ".join(sorted(set(h.get("chua", []))))
        tg = ", ".join(_o(x) for x in h.get("thoi_gian_tinh_chinh_s", []))
        khac = f" (+{h['dong_clip_khac_da']} dòng clip khác ĐÃ TC)" if h.get("dong_clip_khac_da") else ""
        dong.append(f"| {h['S']} | {h.get('so_dong', 0)} ({h.get('so_dong_da', 0)}){khac} | {_o(p)} / {_o(r)} | "
                    f"{_o(pe)} / {_o(re_)} | {_o(h.get('loi_mep_max_s'))} | {td} | "
                    f"{len(h.get('cat_bia', []))} / {len(h.get('cat_sot', []))} | {chua} | {tg} |")
    return "\n".join(dong)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tinh_huong", nargs="*", help=" ".join(THU_MUC))
    ap.add_argument("--tat-ca", action="store_true")
    ap.add_argument("--chi-engine", action="store_true")
    ap.add_argument("--phat-lai", action="store_true")
    ap.add_argument("--tu-kiem", action="store_true")
    ap.add_argument("--ra", default=RA)
    a = ap.parse_args()
    if a.tu_kiem:
        _tu_kiem()
        return 0
    _kiem_moi_truong()
    sys.path.insert(0, MA)
    ds = list(THU_MUC) if a.tat_ca else a.tinh_huong
    sai = [x for x in ds if x not in THU_MUC]
    if sai or not ds:
        ap.error(f"tình huống không có: {sai or 'chưa chọn'}")
    che_do = "chi_engine" if a.chi_engine else "phat_lai" if a.phat_lai else "bat"
    hang = []
    for S in ds:
        t = time.perf_counter()
        try:
            h = mot_tinh_huong(S, che_do, a.ra)
        except Exception:  # noqa: BLE001 — một tình huống hỏng không chặn các tình huống khác
            h = {"S": S, "loi": traceback.format_exc()}
        hang.append(h)
        print(f"[{S}] {time.perf_counter() - t:.0f} s — " + json.dumps(
            {k: v for k, v in h.items() if k not in ("tung_doan_that",)}, ensure_ascii=False, default=str)[:900],
            flush=True)
    if che_do != "chi_engine":
        ten = "tong_hop" if a.tat_ca else "tong_hop_mot_phan"
        _ghi(os.path.join(a.ra, f"{ten}.json"), {"che_do": che_do, "hang": hang})
        with open(os.path.join(a.ra, f"{ten}.md"), "w", encoding="utf-8") as f:
            f.write(bang(hang) + "\n")
        print(bang(hang))
    return 1 if any("loi" in h for h in hang) else 0


if __name__ == "__main__":
    sys.exit(main())
