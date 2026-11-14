# -*- coding: utf-8 -*-
"""In bảng gọn từ tong_hop.json của phần 1 (truc_tiep) và phần 2 (quet) — chỉ đọc, để đọc nhanh/đối chiếu.

Chạy: <venv python> -B xem.py [truc_tiep|quet]
"""
from __future__ import annotations

import os
import sys

import chung as c


def _f(x, n=1):
    return "—" if x is None else (f"{x:+.{n}f}" if isinstance(x, (int, float)) else str(x))


def truc_tiep() -> None:
    th = c.doc_json(os.path.join(c.KET_QUA, "truc_tiep", "tong_hop.json"))
    print("PHẦN 1 — audfprint trực tiếp (mức mảnh). Ô = sai đầu/sai cuối (s) của hợp mảnh thật; [bóng gần vượt đầu/cuối]")
    for h in th["kich_ban"]:
        if h.get("chua_chay"):
            print(h["kich_ban"], "chưa chạy")
            continue
        o = []
        for tq in ("Q0.05", "Q0.02", "Q0.01", "Q0"):
            v = h[tq]
            dd = "; ".join(f"{_f(d['sai_so_dau_s'])}/{_f(d['sai_so_cuoi_s'])}"
                           + (f"[{_f(d['bong_gan_vuot_dau_s'])}/{_f(d['bong_gan_vuot_cuoi_s'])}]"
                              if d.get("bong_gan_qua_loc") else "") for d in v["doan"]) or "—"
            bb = v.get("bat_bien")
            o.append(f"{tq}:{v['luot'][:6]} {dd}" + ("" if not bb else f" bb={'OK' if bb['cung_tap_dong_moi_luot'] else 'KHÁC'}"))
        m0 = h["Q0"]["manh_qua_loc_tat_ca_luot"]
        m5 = h["Q0.05"]["manh_qua_loc_tat_ca_luot"]
        print(f"{h['kich_ban']:4s} tái lập={h['tai_lap_Q0.05_trung_bo_thu']} | " + " | ".join(o)
              + f" | clip khác qua lọc {m5['clip_khac']}→{m0['clip_khac']}, khớp dài nhất {m5['clip_khac_khop_dai_nhat_s']}→"
                f"{m0['clip_khac_khop_dai_nhat_s']} s, bóng qua lọc {m5['bong']}→{m0['bong']}")


def quet() -> None:
    th = c.doc_json(os.path.join(c.KET_QUA, "quet", "tong_hop.json"))
    print("PHẦN 2 — engine.scan_media THẬT. Ô = dòng/đạt/dương giả; theo clip: sai đầu clip, đầu vùng, cuối; P/R [start..end]; "
          "P/R [vùng..end]")
    for h in th["kich_ban"]:
        print(h["kich_ban"])
        for tq, v in h["theo_q"].items():
            tc = " ; ".join(
                f"{k}: n={x['so_dong']} {_f(x['sai_so_dau_clip_s'], 2)}/{_f(x['sai_so_dau_vung_s'])}/{_f(x['sai_so_cuoi_s'])}"
                f" P/R={x['precision_giay']}/{x['recall_giay']} vùng={x['precision_giay_tu_vung_khop']}/"
                f"{x['recall_giay_tu_vung_khop']}" for k, x in v["theo_clip"].items())
            sv = v.get("so_voi_Q0.05")
            doi = ""
            if sv:
                cac = [k for k in ("doi_tap_ung_vien_dat", "doi_so_dong_bao_cao", "doi_clip_bao_cao", "doi_moc_mo_ho",
                                   "doi_luot_bu_toc_do") if sv[k]]
                if sv["doi_moc_dau_clip_tren_0_15s"]:
                    cac.append(f"mốc đầu {sv['doi_moc_dau_clip_tren_0_15s']}")
                doi = f" ĐỔI={cac or 'không'} min_match {sv['qua_min_match_s']} nhóm {sv['so_nhom_sau_merge']} loại {sv['so_dong_bi_loai']}"
            cd = v["chan_doan"]
            print(f"  {tq:5s} {v['thoi_gian_quet_s']:6.1f}s dòng={v['so_dong_bao_cao']} đạt={v['so_dat_nguong']} "
                  f"giả={v['duong_tinh_gia']} bù={bool(cd.get('da_thu_toc_do'))} | {tc}{doi}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    phan = sys.argv[1:] or ["truc_tiep", "quet"]
    for p in phan:
        {"truc_tiep": truc_tiep, "quet": quet}[p]()
