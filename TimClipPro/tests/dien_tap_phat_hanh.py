# -*- coding: utf-8 -*-
"""Diễn tập CẬP NHẬT một bản Stable trong sandbox managed — đúng đường máy vận hành, chạy được trên PC1 hoặc PC2
(docs/PHAT_HANH_HAI_MAY.md §Diễn tập). KHÔNG phải test pytest (không thu thập): chạy tay trước khi phân phối.

    <python có cryptography> -I -B tests/dien_tap_phat_hanh.py <cau_hinh.json>

Cấu hình (JSON; đường dẫn tuyệt đối):
  sandbox, logs, bang_chung        thư mục MỚI (sandbox chưa tồn tại)
  python_goc                       Python 3.12 gốc của máy (như bootstrap thật)
  wheelhouse                       wheel cho MỌI lock dùng tới (tải từ PyPI bằng ``pip download --require-hashes``)
  kit_zip                          bộ bootstrap (``release_tool.py kit``)
  feed_dau                         [thư mục stable-X.Y.Z ĐÃ KÝ] cài lúc bootstrap (bản đang chạy trên máy thật)
  feed_moi                         thư mục stable-X.Y.Z ĐÃ KÝ sẽ phát hành
  tin_cay_kiem                     danh sách khoá công khai dùng verify bản mới (release/trusted_keys.json)
  release_tool, uy_quyen_khoa      công cụ của cây đang phát hành
  ghi_danh (tuỳ)                   {"khoa_ky_pem", "khoa_moi_pem", "ten_may"}: ghi danh khoá mới bằng uỷ quyền GIỮA
                                   bản đầu và bản mới (bản mới do khoá mới ký) — khoá THỬ không mã hoá
  thu_quay_lai (tuỳ)               runtime mới hỏng sau prepare → apply QUAY VỀ + cách ly → bo-cach-ly → cập nhật lại
  feed_khoa_la, khoa_la_pem (tuỳ)  bản > bản mới do khoá LẠ ký (phải bị bỏ qua) + khoá đó (uỷ quyền giả)
  ffmpeg_bin (tuỳ)                 thư mục ffmpeg đặt đầu PATH
Tiến trình con: môi trường SẠCH (bỏ PYTHON*/PIP_*/TIMCLIP_*), pip CHỈ đọc wheelhouse (PIP_NO_INDEX), proxy
127.0.0.1:9 = bẫy mạng. Không Streamlit server, không Google/YouTube/GitHub, không Task Scheduler, không cookie thật.
"""
import sys

sys.dont_write_bytecode = True

import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import pathlib  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import zipfile  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CFG = json.load(open(sys.argv[1], encoding="utf-8"))
SB = os.path.abspath(CFG["sandbox"])
GOC, STATE, FEED, KIT = (os.path.join(SB, x) for x in ("TimClipPro", "TimClipPro_State", "TimClipPro_Feed", "kit"))
LOGS, BC = os.path.abspath(CFG["logs"]), os.path.abspath(CFG["bang_chung"])
KQ = []
BO_QUA_STATE = ("backups/", "cache/", "logs/", "data/bao_tri/")

SEED = r'''
import json, os, sqlite3, sys
lenh, ma, out = sys.argv[1:4]
sys.path.insert(0, ma)
import runtime_paths
import sheet_destinations as sd
from engine import Engine
eng = Engine(runtime=runtime_paths.resolve(dict(os.environ)))
db = eng.sqlite_file
state = os.environ["TIMCLIP_STATE_ROOT"]
if lenh == "tao":
    d = os.path.join(state, "secrets"); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "khoa_congty_GIA.json")
    json.dump({"type": "service" + "_account", "client_email": "gui@congty-gia.invalid", "private_key_id": "gia12345",
               "private" + "_key": "GIA"},
              open(p, "w", encoding="utf-8"))
    sd.dang_ky_xac_thuc(db, "congty", p)
    sd.tao_dich(db, ten="Congty", spreadsheet_id="1" + "c" * 43, worksheet_id=0, worksheet_ten="KetQuaQuet",
                schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="congty", workspace="mac_dinh")
    kho = os.path.join(state, "data", "Kho_GIA"); os.makedirs(kho, exist_ok=True)
    open(os.path.join(kho, "db.pklz"), "wb").write(b"KHO-GIA-" * 4096)
    json.dump({"ghi_chu": "kho giả"}, open(os.path.join(kho, "clips_meta.json"), "w", encoding="utf-8"))
    eng.config.ytdlp_cookies_browser = "firefox"
    eng.luu_cau_hinh()
con = sqlite3.connect("file:" + db.replace(os.sep, "/") + "?mode=ro", uri=True)
try:
    kq = {"phien_ban_db": con.execute("PRAGMA user_version").fetchone()[0],
          "integrity": con.execute("PRAGMA integrity_check").fetchone()[0]}
finally:
    con.close()
kq.update({"ho_so": sorted([x.ten, x.worksheet_ten] for x in sd.ds_dich(db)),
           "khoa": sorted(x.ref for x in sd.ds_xac_thuc(db)), "installation_id": eng.installation_id(),
           "cookie": eng.config.ytdlp_cookies_browser})
json.dump(kq, open(out, "w", encoding="utf-8"), ensure_ascii=False)
'''


def ca(ma, mo_ta, ky_vong, thuc, dat):
    KQ.append({"ca": ma, "mo_ta": mo_ta, "ky_vong": ky_vong, "thuc_te": str(thuc)[:600], "dat": bool(dat)})
    print(f"[{'ĐẠT' if dat else 'LỖI'}] {ma} — {mo_ta}: {str(thuc)[:300]}", flush=True)


def env_sach(*, them=None):
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(("PYTHON", "PIP_", "TIMCLIP_")) and k.upper() != "VIRTUAL_ENV"}
    duong = [p for p in env.get("PATH", "").split(os.pathsep) if "tool_quet" not in p.lower()]
    if CFG.get("ffmpeg_bin"):
        duong.insert(0, CFG["ffmpeg_bin"])
    env["PATH"] = os.pathsep.join(duong)
    env.update(PIP_NO_INDEX="1", PIP_FIND_LINKS=pathlib.Path(CFG["wheelhouse"]).as_uri(), PIP_CONFIG_FILE=os.devnull,
               HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", NO_PROXY="",
               http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", PYTHONDONTWRITEBYTECODE="1")
    env.update(them or {})
    return env


def chay(ten, lenh, env=None, cwd=None, timeout=3600):
    log = os.path.join(LOGS, f"{ten}.txt")
    with open(log, "w", encoding="utf-8") as lg:
        lg.write("$ " + (lenh if isinstance(lenh, str) else subprocess.list2cmdline(lenh)) + "\n")
        lg.flush()
        try:
            rc = subprocess.run(lenh, env=env or env_sach(), cwd=cwd, stdout=lg, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            rc = "QUÁ_HẠN"
    return rc, open(log, encoding="utf-8", errors="replace").read()


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def anh_chup(goc, *, bo=()):
    kq = {}
    for g, _, fs in os.walk(goc):
        for f in fs:
            rel = os.path.relpath(os.path.join(g, f), goc).replace("\\", "/")
            if not rel.startswith(bo) and rel != "update_state/updater.lock":
                kq[rel] = sha(os.path.join(g, f))
    return kq


def khac(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def doc_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def trang_thai():
    us = os.path.join(GOC, "update_state")
    return {t: doc_json(os.path.join(us, f"{t}.json")) for t in ("journal", "current", "last_good", "quarantine")}


def ban(con_tro):
    return (con_tro or {}).get("phien_ban") or ""


def dong_lenh_bat(ten):
    for d in open(os.path.join(GOC, ten), encoding="ascii").read().splitlines():
        if d.startswith('"') and "-E -s" in d:
            p = d.split('"')
            return p[1], p[3]
    raise SystemExit(f"không đọc được lệnh trong {ten}")


def launcher(ten, *doi_so):
    py, lc = dong_lenh_bat("TimClipPro.bat")
    return chay(ten, [py, "-E", "-s", lc, *doi_so])


def cap_nhat(ten):
    return chay(ten, f'cmd.exe /d /s /c ""{os.path.join(GOC, "CapNhat.bat")}""', cwd=GOC)


def dat_feed(thu_muc):
    dich = os.path.join(FEED, os.path.basename(os.path.normpath(thu_muc)))
    shutil.copytree(thu_muc, dich)
    return dich


def manifest(thu_muc):
    return doc_json(os.path.join(thu_muc, "manifest.json")) or {}


def verify(ten, thu_muc, tin_cay):
    return chay(ten, [sys.executable, "-E", "-s", "-B", CFG["release_tool"], "verify", "--dir", thu_muc,
                      "--tin-cay", tin_cay])


def du_lieu(ten, lenh, phien_ban, runtime_id):
    py = os.path.join(GOC, "environments", runtime_id, "Scripts", "python.exe")
    ma = os.path.join(GOC, "releases", phien_ban, "TimClipPro")
    p_seed, out = os.path.join(LOGS, "seed_du_lieu.py"), os.path.join(BC, f"du_lieu_{ten}.json")
    if not os.path.exists(p_seed):
        with open(p_seed, "w", encoding="utf-8") as f:
            f.write(SEED)
    rc, o = chay(ten, [py, "-B", "-s", p_seed, lenh, ma, out],
                 env=env_sach(them={"TIMCLIP_RUNTIME_MODE": "managed", "TIMCLIP_STATE_ROOT": STATE}), cwd=STATE)
    return rc, doc_json(out) or {}


def doctor(ten):
    rc, o = launcher(ten, "doctor")
    dong = {x.split(":", 1)[0].strip("✅⚠️❌ ️"): x for x in o.splitlines() if x[:1] in "✅⚠❌"}
    return rc, o, dong


def kiem_release(ten):
    """Mọi release đã cài: khớp danh sách đã ký (đúng parser của launcher đã cài), không có __pycache__."""
    sys.path.insert(0, os.path.join(GOC, "launcher"))
    try:
        import managed_update as mu_cai
    finally:
        sys.path.pop(0)
    loi = []
    for pb in sorted(os.listdir(os.path.join(GOC, "releases"))):
        rel = os.path.join(GOC, "releases", pb)
        try:
            with open(os.path.join(rel, "manifest.json"), "rb") as f:
                mu_cai.kiem_cay_release(rel, mu_cai.doc_manifest(f.read()))
        except Exception as e:  # noqa: BLE001
            loi.append(f"{pb}: {e}")
        loi += [f"{pb}: __pycache__ {g}" for g, ds, _ in os.walk(rel) if "__pycache__" in ds]
    ca(ten, "cây release đã ký: khớp danh sách đã ký, KHÔNG có __pycache__", "0 lỗi",
       f"{sorted(os.listdir(os.path.join(GOC, 'releases')))}; lỗi {loi}", not loi)


def main() -> int:
    if os.path.exists(SB):
        print("Sandbox đã có — dừng (không ghi đè).")
        return 3
    for d in (LOGS, BC):
        os.makedirs(d, exist_ok=True)
    m_moi = manifest(CFG["feed_moi"])
    pb_moi, rt_moi = m_moi.get("phien_ban"), (m_moi.get("runtime") or {}).get("runtime_id")
    # ---- 1. kit + verify
    with zipfile.ZipFile(CFG["kit_zip"]) as z:
        z.extractall(KIT)
    tc_kit = os.path.join(KIT, "trusted_keys.json")
    khoa_kit = sorted(k["key_id"] for k in doc_json(tc_kit)["khoa"])
    rc_dau = [verify(f"F0_verify_dau_{i}", d, tc_kit)[0] for i, d in enumerate(CFG["feed_dau"])]
    rc_moi_kit, o_moi_kit = verify("F0_verify_moi_bang_kit", CFG["feed_moi"], tc_kit)
    rc_moi_kiem, o_moi_kiem = verify("F0_verify_moi_bang_danh_sach", CFG["feed_moi"], CFG["tin_cay_kiem"])
    co_ghi_danh = bool(CFG.get("ghi_danh"))
    ca("F0", "verify: bản đầu bằng kit; bản mới bằng danh sách khoá phát hành"
       + (" (TRƯỚC ghi danh: kit chưa tin khoá ký bản mới)" if co_ghi_danh else ""),
       "bản đầu ĐẠT; bản mới ĐẠT với danh sách" + ("; bị kit từ chối" if co_ghi_danh else " và với kit"),
       f"kit tin {khoa_kit}; đầu rc {rc_dau}; mới/kit rc {rc_moi_kit} {o_moi_kit.strip()[-80:]}; "
       f"mới/danh sách rc {rc_moi_kiem} {o_moi_kiem.strip()[-80:]}",
       all(r == 0 for r in rc_dau) and rc_moi_kiem == 0
       and ((rc_moi_kit != 0 and "KHÔNG tin cậy" in o_moi_kit) if co_ghi_danh else rc_moi_kit == 0))
    # ---- 2. bootstrap như máy cài mới, feed chỉ có bản đầu
    os.makedirs(FEED)
    for d in CFG["feed_dau"]:
        dat_feed(d)
    pb_dau = manifest(CFG["feed_dau"][-1]).get("phien_ban")
    rc, o = chay("B1_bootstrap", [CFG["python_goc"], os.path.join(KIT, "bootstrap.py"), "--goc", GOC, "--state", STATE,
                                  "--python-goc", CFG["python_goc"], "--tin-cay", tc_kit, "--nguon-thu-muc", FEED],
                 cwd=KIT)
    tt = trang_thai()
    ca("B1", "bootstrap bộ kit + feed bản đầu", f"rc 0, ACTIVE {pb_dau}",
       f"rc {rc}, journal {(tt['journal'] or {}).get('trang_thai')}, current {ban(tt['current'])}",
       rc == 0 and ban(tt["current"]) == pb_dau)
    if ban(tt["current"]) != pb_dau:
        return ket_thuc()
    rt_dau = os.path.basename(tt["current"]["runtime"])
    rc, d0 = du_lieu("D0_tao", "tao", pb_dau, rt_dau)
    ca("D0", f"dữ liệu GIẢ bằng mã {pb_dau}: khoá dịch vụ giả, hồ sơ Congty, kho giả, cookie «firefox»",
       "rc 0, integrity ok", f"rc {rc}, {d0}", rc == 0 and d0.get("integrity") == "ok" and d0.get("ho_so"))
    s0, rel0 = anh_chup(STATE, bo=BO_QUA_STATE), anh_chup(os.path.join(GOC, "releases"))
    f_moi = dat_feed(CFG["feed_moi"])
    # ---- 3. (tuỳ) ghi danh khoá mới bằng uỷ quyền — giữa bản đầu và bản mới
    if co_ghi_danh:
        rc, o = launcher("G0_prepare_truoc_ghi_danh", "update", "prepare")
        tt = trang_thai()
        ca("G0", f"TRƯỚC ghi danh: update prepare với bản {pb_moi} do khoá mới ký", f"bỏ qua; vẫn {pb_dau}; không cách ly",
           f"rc {rc}, journal {(tt['journal'] or {}).get('trang_thai')}, current {ban(tt['current'])}, "
           f"cách ly {sorted(tt['quarantine'] or {})}; {' | '.join(x for x in o.splitlines() if 'tin cậy' in x)[:200]}",
           ban(tt["current"]) == pb_dau and pb_moi not in (tt["quarantine"] or {})
           and (tt["journal"] or {}).get("trang_thai") != "STAGED")
        ghi_danh_ca(f_moi)
    # ---- 4. (tuỳ) QUAY VỀ khi runtime mới hỏng sau prepare
    if CFG.get("thu_quay_lai"):
        rc, o = launcher("Q1_prepare", "update", "prepare")
        tt = trang_thai()
        j = tt["journal"] or {}
        ca("Q1", f"update prepare {pb_moi} — CHƯA kích hoạt", f"rc 0, STAGED {pb_moi}, current {pb_dau}",
           f"rc {rc}, journal {j.get('trang_thai')} {j.get('ung_vien')}, current {ban(tt['current'])}",
           rc == 0 and j.get("trang_thai") == "STAGED" and j.get("ung_vien") == pb_moi and ban(tt["current"]) == pb_dau)
        sp = os.path.join(GOC, "environments", rt_moi, "Lib", "site-packages")
        di = sorted(x for x in (os.listdir(sp) if os.path.isdir(sp) else [])
                    if x.lower().startswith("gspread-") and x.endswith(".dist-info"))
        cat = os.path.join(SB, "gspread_dist_info_cat_tam")
        co = len(di) == 1
        if co:
            shutil.move(os.path.join(sp, di[0]), cat)
        rc, o = launcher("Q2_apply_runtime_hong", "update", "apply")
        tt = trang_thai()
        j = tt["journal"] or {}
        doi_state = khac(s0, anh_chup(STATE, bo=BO_QUA_STATE))
        ca("Q2", "apply khi runtime thiếu thư viện: health SAU kích hoạt lỗi → QUAY VỀ + cách ly",
           f"rc ≠ 0, QUARANTINED, current = last_good = {pb_dau}, cách ly {pb_moi}, state không đổi",
           f"cắt {co}; rc {rc}, journal {j.get('trang_thai')} «{str(j.get('loi'))[:120]}», current {ban(tt['current'])}, "
           f"last_good {ban(tt['last_good'])}, cách ly {sorted(tt['quarantine'] or {})}, state đổi {doi_state}",
           co and rc != 0 and j.get("trang_thai") == "QUARANTINED" and ban(tt["current"]) == pb_dau
           and ban(tt["last_good"]) == pb_dau and pb_moi in (tt["quarantine"] or {}) and not doi_state)
        rc, o, _ = doctor("Q3_doctor_sau_quay_ve")
        ca("Q3", f"sau quay về: doctor — bản {pb_dau} mở được", "rc 0, không ❌", f"rc {rc}, ❌ {o.count('❌')}",
           rc == 0 and "❌" not in o)
        if co:
            shutil.move(cat, os.path.join(sp, di[0]))
        rc, o = launcher("Q4_bo_cach_ly", "update", "bo-cach-ly", pb_moi)
        tt = trang_thai()
        ca("Q4", f"khôi phục thư viện + «update bo-cach-ly {pb_moi}»", "rc 0, hết cách ly",
           f"rc {rc}, cách ly {sorted(tt['quarantine'] or {})}", rc == 0 and pb_moi not in (tt["quarantine"] or {}))
    # ---- 5. cập nhật thật bằng CapNhat.bat do bootstrap sinh
    rc, o = cap_nhat("U1_CapNhat")
    tt = trang_thai()
    j = tt["journal"] or {}
    ca("U1", f"CapNhat.bat {pb_dau} → {pb_moi}", f"rc 0, ACTIVE {pb_moi}, current = last_good, không cách ly",
       f"rc {rc}, journal {j.get('trang_thai')} {j.get('ung_vien')}, current {ban(tt['current'])}, "
       f"last_good {ban(tt['last_good'])}, cách ly {tt['quarantine']}; "
       f"{' | '.join(x for x in o.splitlines() if x.startswith('['))[:200]}",
       rc == 0 and j.get("trang_thai") == "ACTIVE" and ban(tt["current"]) == pb_moi and ban(tt["last_good"]) == pb_moi
       and not (tt["quarantine"] or {}))
    if ban(tt["current"]) != pb_moi:
        return ket_thuc()
    s1 = anh_chup(STATE, bo=BO_QUA_STATE)
    ca("U2", "state root: mọi file có sẵn giữ nguyên byte (lịch sử, hồ sơ, khoá giả, kho giả, cấu hình)",
       "0 đổi / mất / thêm ngoài backups, cache, logs, bao_tri", f"khác {khac(s0, s1)}", not khac(s0, s1))
    rc, d1 = du_lieu("D1_doc_ban_moi", "doc", pb_moi, rt_moi)
    giong = {k: d0.get(k) == d1.get(k) for k in ("phien_ban_db", "ho_so", "khoa", "installation_id", "cookie")}
    ca("D1", f"mã {pb_moi} + runtime của nó đọc dữ liệu của bản đầu", "rc 0, integrity ok, mọi mục giống",
       f"rc {rc}, giống {giong}", rc == 0 and d1.get("integrity") == "ok" and all(giong.values()))
    rc, o, dong = doctor("U3_doctor")
    ca("U3", "launcher doctor sau cập nhật", "rc 0, không ❌" + (", khoá tin cậy tăng 1" if co_ghi_danh else ""),
       f"rc {rc}, ❌ {o.count('❌')}, {dong.get('Khoá tin cậy', '')}",
       rc == 0 and "❌" not in o and (f"{len(khoa_kit) + 1} khoá" in dong.get("Khoá tin cậy", "")
                                       if co_ghi_danh else True))
    kiem_release("R1")
    ca("R2", "release đã cài trước đó KHÔNG đổi byte", "0 file khác",
       f"khác {[k for k in khac(rel0, anh_chup(os.path.join(GOC, 'releases'))) if k in rel0]}",
       not [k for k in khac(rel0, anh_chup(os.path.join(GOC, "releases"))) if k in rel0])
    # ---- 6. (tuỳ) khoá lạ
    if CFG.get("feed_khoa_la"):
        dat_feed(CFG["feed_khoa_la"])
        pb_la = manifest(CFG["feed_khoa_la"]).get("phien_ban")
        rc, o = launcher("L1_prepare_khoa_la", "update", "prepare")
        tt = trang_thai()
        ca("L1", f"bản {pb_la} (cao hơn) do khoá LẠ ký", f"bỏ qua; vẫn ACTIVE {pb_moi}; không STAGED {pb_la}",
           f"rc {rc}, journal {(tt['journal'] or {}).get('trang_thai')} {(tt['journal'] or {}).get('ung_vien')}, "
           f"current {ban(tt['current'])}; {' | '.join(x for x in o.splitlines() if 'tin cậy' in x)[:200]}",
           ban(tt["current"]) == pb_moi and (tt["journal"] or {}).get("ung_vien") != pb_la
           and "KHÔNG tin cậy" in o)
    return ket_thuc()


def ghi_danh_ca(f_moi):
    from cryptography.hazmat.primitives import serialization

    sys.path.insert(0, os.path.dirname(os.path.abspath(CFG["uy_quyen_khoa"])))
    import uy_quyen_khoa as uq

    g = CFG["ghi_danh"]

    def pem(p):
        with open(p, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    k_ky, k_moi = pem(g["khoa_ky_pem"]), pem(g["khoa_moi_pem"])
    lc_truoc, rel_truoc = anh_chup(os.path.join(GOC, "launcher")), anh_chup(os.path.join(GOC, "releases"))
    L = uq.nap_launcher(GOC)
    tt = uq.doc_cai_dat(GOC, L)
    raw_yc = uq.tao_yeu_cau(k_moi, ten_may=g.get("ten_may", "PC2"), cai_dat=tt)
    raw_uq = uq.tao_uy_quyen(raw_yc, k_ky, khoa_tin_cay=L.mu.doc_khoa_tin_cay(os.path.join(KIT, "trusted_keys.json")))
    raw_pub = k_moi.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    kid_moi = uq.tao_key_id(raw_pub)
    p_pub = os.path.join(BC, f"khoa_cong_khai_{kid_moi}.json")        # như tao-khoa để lại trong thư mục khoá của máy
    for ten, b in (("yeu_cau.json", raw_yc), ("uy_quyen.json", raw_uq),
                   (f"khoa_cong_khai_{kid_moi}.json", json.dumps({"khoa": [{"key_id": kid_moi,
                    "ed25519_pub_b64": __import__("base64").b64encode(raw_pub).decode()}]}).encode()),
                   (f"khoa_rieng_phat_hanh_{kid_moi}.pem", b"CHO GIU CHO - khoa rieng that o file cau hinh\n")):
        with open(os.path.join(BC, ten), "wb") as f:
            f.write(b)
    if CFG.get("khoa_la_pem"):
        k_la = pem(CFG["khoa_la_pem"])
        try:
            nd = {**json.loads(raw_uq)["noi_dung"], "ky_boi": uq.tao_key_id(k_la.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw))}
            uq.ghi_danh(GOC, uq._ky(nd, k_la, uq.MIEN_UY_QUYEN), khoa_cong_khai=p_pub, xac_nhan=lambda t: True)
            gia = "CHẤP NHẬN (SAI)"
        except uq.LoiUyQuyen as e:
            gia = f"từ chối: {e}"
        ca("G1a", "uỷ quyền GIẢ (khoá lạ tự ký, ky_boi = chính nó)", "bị từ chối «KHÔNG được tin», launcher không đổi",
           gia, gia.startswith("từ chối") and "KHÔNG được tin" in gia
           and anh_chup(os.path.join(GOC, "launcher")) == lc_truoc)
    kq = uq.ghi_danh(GOC, raw_uq, khoa_cong_khai=p_pub, xac_nhan=lambda t: True)
    lc_sau = anh_chup(os.path.join(GOC, "launcher"))
    doi = khac(lc_truoc, lc_sau)
    sao_luu = [k for k in doi if k.startswith(f"{uq.THU_MUC_SAO_LUU}/")]
    moi_ids = sorted(L.mu.doc_khoa_tin_cay(os.path.join(GOC, "launcher", "trusted_keys.json")))
    ca("G1", "ghi danh khoá mới bằng uỷ quyền của khoá đang tin (parser của launcher ĐÃ CÀI)",
       "DA_GHI_DANH; chỉ đổi trusted_keys.json + 2 file sao lưu; release không đổi; không __pycache__",
       f"{kq['trang_thai']}, khoá {moi_ids}, launcher đổi {doi}",
       kq["trang_thai"] == "DA_GHI_DANH" and set(doi) - set(sao_luu) == {"trusted_keys.json"} and len(sao_luu) == 2
       and not [k for k in lc_sau if "__pycache__" in k and k not in lc_truoc]
       and anh_chup(os.path.join(GOC, "releases")) == rel_truoc)
    try:
        uq.ghi_danh(GOC, raw_uq, khoa_cong_khai=p_pub, xac_nhan=lambda t: True)
        lai = "CHẤP NHẬN (SAI)"
    except uq.LoiUyQuyen as e:
        lai = f"từ chối: {e}"
    ca("G2", "dùng LẠI uỷ quyền đã dùng", "bị từ chối (khoá đã được tin), không đổi gì", lai,
       lai.startswith("từ chối") and anh_chup(os.path.join(GOC, "launcher")) == lc_sau)
    py, _ = dong_lenh_bat("TimClipPro.bat")
    rc, o = chay("G3_xem_bang_python_launcher", [py, "-I", "-B", CFG["uy_quyen_khoa"], "xem", "--goc", GOC])
    ca("G3", "«uy_quyen_khoa.py xem» chạy bằng Python của launcher đã cài (-I -B)",
       "rc 0, liệt kê đủ khoá, không đổi file nào", f"rc {rc}; {o.strip()[-200:]}",
       rc == 0 and all(k in o for k in moi_ids) and anh_chup(os.path.join(GOC, "launcher")) == lc_sau)


def ket_thuc():
    out = os.path.join(BC, "dien_tap.json")
    json.dump({"cau_hinh": CFG, "ket_qua": KQ, "trang_thai_cuoi": trang_thai() if os.path.isdir(GOC) else None},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    dat = sum(1 for k in KQ if k["dat"])
    print(f"== {dat}/{len(KQ)} ca ĐẠT → {out}")
    return 0 if KQ and dat == len(KQ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
