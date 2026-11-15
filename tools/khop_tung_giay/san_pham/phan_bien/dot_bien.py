# -*- coding: utf-8 -*-
"""Kiểm ĐỘT BIẾN tại chỗ cho TimClipPro/tinh_chinh_moc.py (P-8, phản biện mã + test).

Mỗi đột biến = MỘT phép thay chuỗi (phải khớp đúng một chỗ) trên BẢN SAO của module trong thư mục tạm; file thật không
bao giờ bị sửa. pytest chạy tests/test_tinh_chinh_moc.py với plugin ``nap_dot_bien`` (sinh trong thư mục tạm) nạp bản
sao vào ``sys.modules["tinh_chinh_moc"]`` TRƯỚC khi file test import — nên test dùng đúng bản đột biến. Hai mẫu đối
chứng: «goc» (không đổi gì: phải 0 hỏng) và «pha_hong» (phải bị giết) chứng minh plugin nạp đúng bản sao.
Đột biến SỐNG = không test nào hỏng: vị từ đó không được bộ test khoá.

Chạy (Git Bash, ~10–20 s mỗi đột biến):
  cd /c/Dev/Tool_Quet/TimClipPro
  C:/Dev/TimClipPro_CookieFix/TimClipPro/.venv/Scripts/python.exe -B -X utf8 \\
      ../tools/khop_tung_giay/san_pham/phan_bien/dot_bien.py [ten_dot_bien ...]
Kết quả: ``<RA>\\dot_bien.json`` + junit từng đột biến.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

MA = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "TimClipPro"))  # checkout chứa file này
CHAN_MANG = os.path.join(os.path.dirname(MA), "tools", "test", "chan_mang")
RA = r"C:\Dev\pc2_test_runs\2026-11-14_p8\phan_bien\ma_va_test"
FILE_TEST = "tests/test_tinh_chinh_moc.py"

PLUGIN = '''import importlib.util, os, sys
_spec = importlib.util.spec_from_file_location("tinh_chinh_moc", os.environ["TCM_DOT_BIEN"])
_mod = importlib.util.module_from_spec(_spec)
sys.modules["tinh_chinh_moc"] = _mod
_spec.loader.exec_module(_mod)
'''

# (tên, chuỗi cũ, chuỗi mới) — chuỗi cũ phải xuất hiện ĐÚNG một lần trong module
DOT_BIEN = [
    ("goc", "", ""),
    # ngưỡng không thể đạt → mọi test cần «đã tinh chỉnh» phải hỏng (chứng minh plugin nạp đúng bản sao). Đổi hằng DA
    # thì KHÔNG được: test so với tcm.DA của chính bản sao
    ("pha_hong", "LE_NGUONG = 0.15", "LE_NGUONG = 2.0"),
    # 1. lưới an toàn: lõi engine để hở > 5 s → CHUA (bỏ hẳn)
    ("luoi_an_toan_tat", "_do_dai_hop([(max(a, vung), min(b, end)) for a, b in phu]) > HO_LOI_TOI_DA_S",
     "_do_dai_hop([(max(a, vung), min(b, end)) for a, b in phu]) > 1e9"),
    # 2. khe giữa hai đoạn KHÁC neo: chỉ kiểm «có mặt» theo neo của đoạn trước (tiếng đè đúng chỗ tua lùi → chỗ cắt bịa)
    ("khe_khac_neo_mot_neo", 'for d in ([a] if a["neo"] == b["neo"] else [a, b]):', "for d in [a]:"),
    # 3. luật nối khe dài cùng neo (A03) tắt
    ("noi_khe_dai_tat", "else bool(np.mean(co) >= KHE_DAI_TY_LE)", "else False"),
    # 3b. khe ≤ 5 ô cùng neo cũng chỉ cần 3/4 số ô «có mặt» (thay 3–6 s bị nối qua)
    ("noi_khe_ngan_chi_3_4", "noi = bool(co.all()) if len(idx) <= NOI_CUNG_NEO_S else bool(np.mean(co) >= KHE_DAI_TY_LE)",
     "noi = bool(np.mean(co) >= KHE_DAI_TY_LE)"),
    # 4. chốt mép về đầu/cuối clip bất kể mép đo được (H4 cũ)
    ("chot_bien_luon", "if chan and abs(mep - bien) <= CHOT_BIEN_S:", "if chan:"),
    # 5. ngưỡng > 95 % không còn trả CHUA
    ("nguong_toi_da_tat", "if nguong > NGUONG_TOI_DA:", "if False:"),
    # 6. kiểm «mơ hồ» (vòng lặp y hệt) tắt
    ("mo_ho_tat", ">= nguong) >= MO_HO_TY_LE", ">= nguong) >= 2.0"),
    # 7. khoảng lặng: bỏ điều kiện «clip có tiếng ở đó»
    ("im_lang_bo_dk_clip", ">= cl.san + CO_TIENG) >= 0.5", ">= cl.san + CO_TIENG) >= 0.0"),
    # 8. khung «lạ» không còn xếp phía ngoài mép (A03 mép)
    ("khung_la_tat", "llr = np.where(la, np.maximum(llr, 1.0), llr)", "llr = llr"),
    # 9. đường nền: không bỏ độ lệch trùng neo khác
    ("nen_khong_bo_neo_khac", "if all(abs(d - (a - dau0)) > 2.0 for a, _ in neo[1:]):", "if True:"),
    # 10. căn chỉnh: không chặn sửa k quá 1 %
    ("sua_k_khong_chan", "if abs(beta) > SUA_K_TOI_DA or abs(alpha + beta * tam) > W_BAT_S:",
     "if abs(alpha + beta * tam) > W_BAT_S:"),
    # 11–14. cham_gioi_han: bỏ từng vế (nhãn giới hạn / mép gần đầu, cuối phần giải mã / mép ngoài không kiểm được)
    ("cham_bo_gioi_han", 'set(d["cach"]) & set(GIOI_HAN) or ', ""),
    ("cham_bo_dau_video", 'or d["v"][0] < vi.t0 + 1.0', "or False"),
    ("cham_bo_cuoi_video", 'or d["v"][1] > vi.het_s - 1.0', "or False"),
    ("ngoai_khong_kiem_tat", "if not len(idx):\n            ngoai_khong_kiem |= ngoai",
     "if not len(idx):\n            pass"),
    # 15. bằng chứng clip VẮNG phía ngoài mép đo được (vòng 3) tắt
    ("bang_chung_ngoai_mep_tat",
     'if _co_mat(_do_duong(cl, vi, d["dau"], d["k"], u[idx], moc=moc)[0], muc_co_mat(d["neo"], idx, NEN_TAI_CHO_LE)):',
     "if False:"),
    # 16. nhạc tự giống: mức «có mặt» luôn theo p99 nền chung (B03)
    ("nen_tai_cho_tat", "        if not lap:\n            return np.full(len(idx), nen_p99)",
     "        if True:\n            return np.full(len(idx), nen_p99)"),
    # 17. DJ lặp ô nhịp: không kiểm khe tới đoạn sau
    ("dj_khong_kiem_khe", "idx = np.arange(i0, tho[j + 1][1] if j + 1 < len(tho) else i1 + 1)", "idx = np.arange(i0, i1 + 1)"),
    # 18. mép bám chỗ vấp ngắn sát mép (vòng 4) — bỏ luật «bằng chứng tăng lại sau chỗ trũng nông»
    ("vap_ngan_tat",
     "if G[j] >= BANG_CHUNG_MEP and hoi[m_] >= 5 * BANG_CHUNG_MEP and 3 * hoi[m_] >= g[0] - g[: m_ + 1].min():",
     "if False:"),
    # 19. first_pts=0 trở lại (đổi tần số mẫu giữa file .ts → phần sau chỗ đổi trễ)
    ("first_pts_lai", '"-af", "aresample=async=1",', '"-af", "aresample=async=1:first_pts=0",'),
    # 20. luồng canh không kiểm huỷ (bấm Dừng khi FFmpeg im lặng chờ tới HAN_KHOI_S)
    ("canh_khong_kiem_huy", "                if moc is not None:\n                    moc()\n", ""),
    # 21. video có tiếng bắt đầu sau hình (vòng 5): cửa sổ video không tránh phần trước chỗ tiếng bắt đầu
    ("tre_am_tat", "if tre > TRE_AM_TOI_DA_S:", "if False:"),
    # 22. vùng kiểm phía ngoài mép không kẹp vào phần video đã giải mã: ô vượt ra ngoài «không đo được» = «vắng»
    ("ngoai_khong_kep_cua_so", "idx = _o_ngoai(u, max(lo, vi.t0), min(hi, vi.het_s))", "idx = _o_ngoai(u, lo, hi)"),
    # 23. phần dư còn bậc (≥ 4 ô liền lệch > 0,12 s) sau căn chỉnh mà không tách được: vẫn tin (vòng 5)
    ("bac_con_lai_tat", "if _lech_chua_giai_thich(can, tho, tat_ca, len(u)):", "if False:"),
    # 24. luồng canh lại tính thời gian nơi gọi xử lý khối vào hạn một khối (vòng 5)
    ("canh_tinh_ca_xu_ly", "cho_tu[0] = None", "pass"),
    # 25. chuỗi ô lệch không cần KỀ NHAU (bóng ô nhịp từng cặp cách xa nhau thành «4 ô liền» → CHUA nhầm)
    ("lech_khong_ke_nhau", "if lech and chay and i == chay[-1] + 1:", "if lech and chay:"),
    # 25b. đoạn neo khác KHÔNG chạm lõi không còn «giải thích» ô lệch (mảnh kia của cùng clip cạnh dòng → CHUA nhầm)
    ("chu_bo_doan_ngoai_loi", "for i_neo, i0, i1 in tat_ca:\n        chu[i0:i1 + 1] = i_neo",
     "for i_neo, i0, i1 in tho:\n        chu[i0:i1 + 1] = i_neo"),
    # 26. ffprobe không đọc được → coi độ trễ là 0 (giải mã như vòng 4) thay vì CHUA
    ("tre_am_khong_ro_la_0", "            return _chua(LY_DO_TRE_AM, t_bat_dau)", "            tre = 0.0"),
    # 27. chờ ffprobe mà không kiểm huỷ / hạn chót
    ("ffprobe_khong_kiem_huy", "except subprocess.TimeoutExpired:\n                moc()",
     "except subprocess.TimeoutExpired:"),
    # 28. bỏ nhãn gói tiếng đầu: chỉ tin start_time của luồng (ffprobe dừng dò trước gói đó)
    ("tre_am_bo_goi_dau", ', *(giay(g.get("pts_time")) for g in j.get("packets", [])[:1])]', "]"),
    # 31–33. D-50: cờ chạm giới hạn TỪNG MÉP (báo cáo V2 chỉ nới đúng mép đó về mốc lượt quét)
    ("cham_dau_luon_sai", '"cham_dau": bool(False in ngoai_ben or doan[0]["cach"][0] in GIOI_HAN or doan[0]["v"][0] < vi.t0 + 1.0)',
     '"cham_dau": False'),
    ("cham_cuoi_luon_sai",
     '"cham_cuoi": bool(True in ngoai_ben or doan[-1]["cach"][1] in GIOI_HAN or doan[-1]["v"][1] > vi.het_s - 1.0)',
     '"cham_cuoi": False'),
    ("ngoai_ben_tat", "if ngoai:\n                ngoai_ben.add(mep_o_tu)", "if False:\n                ngoai_ben.add(mep_o_tu)"),
]


def _tao_ban_sao(goc: str, cu: str, moi: str) -> str:
    if not cu:
        return goc
    if goc.count(cu) != 1:
        raise SystemExit(f"Chuỗi đột biến phải khớp đúng 1 chỗ, thấy {goc.count(cu)}: {cu!r}")
    return goc.replace(cu, moi)


def _doc_junit(p: str) -> dict:
    goc = ET.parse(p).getroot()
    ca = list(goc.iter("testcase"))
    hong = [c.get("name") for c in ca if c.find("failure") is not None or c.find("error") is not None]
    bo = sum(1 for c in ca if c.find("skipped") is not None)
    return {"thu_thap": len(ca), "hong": len(hong), "bo_qua": bo, "test_hong": hong}


def chay_mot(ten: str, cu: str, moi: str, goc: str, tam: str) -> dict:
    d = os.path.join(tam, ten)
    os.makedirs(d)
    with open(os.path.join(d, "tinh_chinh_moc.py"), "w", encoding="utf-8") as f:
        f.write(_tao_ban_sao(goc, cu, moi))
    with open(os.path.join(d, "nap_dot_bien.py"), "w", encoding="utf-8") as f:
        f.write(PLUGIN)
    junit = os.path.join(RA, f"junit_dot_bien_{ten}.xml")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([d, CHAN_MANG]), "TCM_DOT_BIEN": os.path.join(d, "tinh_chinh_moc.py"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "nap_dot_bien",
                        FILE_TEST, f"--junitxml={junit}"], cwd=MA, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    kq = _doc_junit(junit) if os.path.exists(junit) else {"thu_thap": 0, "hong": -1, "test_hong": [], "bo_qua": 0}
    kq.update(ten=ten, ma_thoat=r.returncode, duoi=r.stdout[-400:])
    return kq


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(RA, exist_ok=True)
    with open(os.path.join(MA, "tinh_chinh_moc.py"), encoding="utf-8") as f:
        goc = f.read()
    chon = set(sys.argv[1:])
    ds = [x for x in DOT_BIEN if not chon or x[0] in chon]
    p_ra = os.path.join(RA, "dot_bien.json")
    ra = []
    if chon and os.path.exists(p_ra):                   # chạy một phần: giữ kết quả các đột biến khác
        with open(p_ra, encoding="utf-8") as f:
            ra = [x for x in json.load(f)["ket_qua"] if x["ten"] not in chon]
    with tempfile.TemporaryDirectory(prefix="p8_dot_bien_") as tam:
        for ten, cu, moi in ds:
            kq = chay_mot(ten, cu, moi, goc, tam)
            ra.append(kq)
            trang = ("ĐỐI CHỨNG" if ten in ("goc", "pha_hong") else "SỐNG" if kq["hong"] == 0 else "bị giết")
            print(f"[{ten}] {trang}: {kq['hong']}/{kq['thu_thap']} test hỏng {kq['test_hong'][:6]}", flush=True)
    doi_chung_dung = (next((x["hong"] for x in ra if x["ten"] == "goc"), 0) == 0
                      and next((x["hong"] for x in ra if x["ten"] == "pha_hong"), 1) > 0)
    with open(p_ra, "w", encoding="utf-8") as f:
        json.dump({"doi_chung_dung": doi_chung_dung, "ket_qua": ra}, f, ensure_ascii=False, indent=1)
    print("Đối chứng (goc 0 hỏng, pha_hong bị giết):", "ĐẠT" if doi_chung_dung else "KHÔNG ĐẠT / không chạy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
