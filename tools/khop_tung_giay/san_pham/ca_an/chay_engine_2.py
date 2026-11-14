# -*- coding: utf-8 -*-
"""Engine THẬT trên từng CA ẨN VÒNG 2 (ca_an_2) → ``ket_qua_engine.json`` — dùng NGUYÊN ``chay_engine.py`` của vòng 1
(import, không sửa; chỉ đổi thư mục ca): cấu hình MẶC ĐỊNH, ncores 2, tinh_chinh_moc TẮT, một lượt engine một lúc; ghi mọi
Match của ``kq.matches`` và ``kq.matches_loai`` (clip, duong_dan_kho, start_s, vung_khop_s, end_s, clip_offset_s, matched_s,
hashes, moc_mo_ho, he_so, ho, neo, rồi các trường còn lại) + so_dat_nguong, pham_vi_quet_s, duration_s, status, note;
``kq.matches`` rỗng → ``ket_luan_engine`` = «engine_khong_thay» (ca vẫn giữ).

Sau lượt engine, ``chot_ky_vong`` (chỉ HẠ, không nâng): một đoạn thật gán cho dòng engine (cùng clip, lõi nới 30 s + 10 % —
như ``kiem_ca_an.gan_doan_that``) mà nơi gọi KHÔNG thể tinh chỉnh đúng theo hợp đồng của ``Engine._tinh_chinh_ket_qua`` thì
ky_vong «da» → «chua_hoac_da», ghi ``ky_vong_thiet_ke`` + ``dieu_chinh_ky_vong`` (lý do) vào su_that.json:
  - dòng mang moc_mo_ho hoặc ho «resample» (``Engine._ly_do_khong_tinh_chinh`` bỏ qua, module không được gọi);
  - không neo nào của dòng trùng (≤ 2 s) mốc giây 0 clip của đoạn thật (video_tu − clip_tu/he_so): module chỉ đo dọc các
    căn chỉnh engine đưa, thiếu căn chỉnh thì «chưa tinh chỉnh» mới là đúng — ĐÃ thì vẫn phải đúng/đủ mọi đoạn.

Chạy (Git Bash, từ TimClipPro/; máy dùng chung):
  PYTHONPATH=C:/Dev/Tool_Quet/tools/test/chan_mang C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe \\
      -B -X utf8 ../tools/khop_tung_giay/san_pham/ca_an/chay_engine_2.py [B01 B02 ...]   # không đối số = mọi ca
  ... chay_engine_2.py --tong-hop        # chỉ chốt ky_vong + dựng lại <RA>/tong_hop.json từ file đã có
  ... chay_engine_2.py --tu-kiem         # tự kiểm luật hạ ky_vong (không cần audio, không chạy engine)
"""
from __future__ import annotations

import json
import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chay_engine as ce  # noqa: E402  (vòng 1 — chỉ import)

RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\ca_an_2"
NEO_TRUNG_S = 2.0
HO_RESAMPLE = "resample"            # = toc_do_khop.HO_RESAMPLE


def gan_doan_that(doan_that: list, matches: list) -> dict:
    """Mỗi đoạn thật → chỉ số dòng CÙNG clip có lõi nới biên (30 s + 10 % lõi) giao nó nhiều nhất (None: không dòng nào)."""
    ra = {}
    for n, t in enumerate(doan_that):
        tot = (0.0, None)
        for i, m in enumerate(matches):
            if m["clip"] != t["clip"]:
                continue
            bien = 30.0 + 0.10 * (m["end_s"] - m["vung_khop_s"])
            giao = max(0.0, min(m["end_s"] + bien, t["video_den"]) - max(m["vung_khop_s"] - bien, t["video_tu"]))
            if giao > tot[0]:
                tot = (giao, i)
        ra[n] = tot[1]
    return ra


def ly_do_ha_ky_vong(doan_that: list, matches: list) -> list:
    """Các lý do hợp đồng nơi gọi làm tinh chỉnh ĐÚNG là không thể (rỗng = không hạ)."""
    ly_do = []
    for n, i in gan_doan_that(doan_that, matches).items():
        if i is None:
            continue
        m, t = matches[i], doan_that[n]
        if m["moc_mo_ho"] or m["ho"] == HO_RESAMPLE:
            ly_do.append(f"đoạn thật {n} thuộc dòng engine {i} mang {'moc_mo_ho' if m['moc_mo_ho'] else 'ho resample'}: "
                         "nơi gọi không tinh chỉnh dòng này (Engine._ly_do_khong_tinh_chinh)")
            continue
        neo = [tuple(x) for x in m["neo"]] or [(m["vung_khop_s"] - m["he_so"] * m["clip_offset_s"], m["he_so"])]
        if min(_lech_neo(a, k, t) for a, k in neo) > NEO_TRUNG_S:
            ly_do.append(f"đoạn thật {n} (mốc giây 0 clip {t['video_tu'] - t['clip_tu'] / t['he_so']:.3f}) không có neo "
                         f"nào của dòng engine {i} đi qua trong {NEO_TRUNG_S:g} s (neo {[list(x) for x in neo]})")
    return ly_do


def _lech_neo(a: float, k: float, t: dict) -> float:
    """Khoảng cách nhỏ nhất (giây video) giữa đường neo «video = a + k·giây clip» và ánh xạ thật của đoạn ``t`` trên
    [clip_tu, clip_den]: neo lấy từ một mảnh nên chỉ chính xác gần mảnh đó khi k của engine lệch chút ít (đoạn tốc độ)."""
    lech = [a + k * c - (t["video_tu"] + (c - t["clip_tu"]) / t["he_so"]) for c in (t["clip_tu"], t["clip_den"])]
    return 0.0 if lech[0] * lech[1] <= 0 else min(abs(x) for x in lech)


def _tu_kiem() -> None:
    t = [{"clip": "c", "video_tu": 300.0, "video_den": 400.0, "clip_tu": 20.0, "clip_den": 120.0, "he_so": 1.0},
         {"clip": "c", "video_tu": 400.0, "video_den": 500.0, "clip_tu": 123.0, "clip_den": 223.0, "he_so": 1.0}]
    m = {"clip": "c", "vung_khop_s": 305.0, "end_s": 495.0, "clip_offset_s": 25.0, "he_so": 1.0, "ho": "",
         "moc_mo_ho": False, "neo": [[280.0, 1.0], [277.0, 1.0]]}
    assert ly_do_ha_ky_vong(t, [m]) == []                              # đủ neo cho cả hai đoạn (cắt 3 s)
    assert len(ly_do_ha_ky_vong(t, [dict(m, neo=[[280.0, 1.0]])])) == 1   # thiếu neo của đoạn sau
    assert "moc_mo_ho" in ly_do_ha_ky_vong(t[:1], [dict(m, moc_mo_ho=True)])[0]
    assert ly_do_ha_ky_vong(t, [dict(m, clip="khac")]) == []           # không dòng nào cùng clip: không gán, không hạ
    # đoạn chậm 0,98 (k thật 1,0204): neo k = 1 lấy từ mảnh ở giây clip 120 vẫn đi qua ánh xạ thật → không hạ
    toc = [{"clip": "c", "video_tu": 300.0, "video_den": 504.08, "clip_tu": 20.0, "clip_den": 220.0, "he_so": 0.98}]
    a = 300.0 + (120.0 - 20.0) / 0.98 - 120.0
    assert ly_do_ha_ky_vong(toc, [dict(m, end_s=500.0, neo=[[a, 1.0]])]) == []
    assert len(ly_do_ha_ky_vong(toc, [dict(m, end_s=500.0, neo=[[a + 6.0, 1.0]])])) == 1
    print("chay_engine_2: tự kiểm luật hạ ky_vong ĐẠT")


def chot_ky_vong(ten: str) -> str:
    d = os.path.join(RA, ten)
    p_st, p_ke = os.path.join(d, "su_that.json"), os.path.join(d, "ket_qua_engine.json")
    if not os.path.exists(p_ke):
        return "chưa có ket_qua_engine.json"
    st, ke = ce._doc(p_st), ce._doc(p_ke)
    thiet_ke = st.get("ky_vong_thiet_ke", st["ky_vong"])
    ly_do = ly_do_ha_ky_vong(st["doan"], ke["matches"])
    moi = "chua_hoac_da" if thiet_ke == "da" and ly_do else thiet_ke
    if moi != st["ky_vong"] or ly_do != st.get("dieu_chinh_ky_vong", {}).get("ly_do", []):
        st["ky_vong_thiet_ke"] = thiet_ke
        st["ky_vong"] = moi
        st["dieu_chinh_ky_vong"] = {"ly_do": ly_do, "theo_ket_qua_engine": ke.get("chay_luc"),
                                    "quy_tac": "chỉ hạ «da» → «chua_hoac_da» khi hợp đồng nơi gọi làm tinh chỉnh đúng là "
                                               "không thể (dòng bị engine bỏ qua, hoặc thiếu neo của đoạn thật)"}
        with open(p_st, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
    return f"{thiet_ke} → {moi}" + (f" ({'; '.join(ly_do)})" if ly_do else "")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--tu-kiem" in sys.argv:
        _tu_kiem()
        return 0
    ce.RA = RA                                            # chay_engine (vòng 1) đọc/ghi thư mục vòng 2
    rc = 0
    if "--tong-hop" not in sys.argv:
        rc = ce.main()                                    # tự đọc sys.argv: [mã ca …]
    chon = [x for x in sys.argv[1:] if not x.startswith("--")]
    for ten in ce._ds_ca():
        if not chon or ten in chon or ten.split("_")[0] in chon:
            print(f"[{ten}] ky_vong: {chot_ky_vong(ten)}", flush=True)
    ce.tong_hop()
    return rc


if __name__ == "__main__":
    sys.exit(main())
