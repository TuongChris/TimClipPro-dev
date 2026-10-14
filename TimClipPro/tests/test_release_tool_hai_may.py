# -*- coding: utf-8 -*-
"""release_tool — các bước SAU KHI KÝ dùng chung cho mọi máy phát hành (docs/PHAT_HANH_HAI_MAY.md): kiem-sau-ky, feed
(ZIP phân phối + SHA256SUMS + khối PowerShell), kit (bộ bootstrap). Khoá thử sinh lúc chạy, không mạng."""
import hashlib
import json
import os
import subprocess
import zipfile

import pytest

import managed_update as mu
import release_tool as rt

REPO = os.environ.get("TIMCLIP_REPO_GOC") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E49 = "e49340d7d8cf01ec51cea914b3f4509197b5f964"
LOCK = b"streamlit==1.62.0 \\\n    --hash=sha256:" + b"a" * 64 + b"\n"
TAO_LUC = "2026-10-14T12:00:03Z"


def _files(pb="1.2.0") -> dict:
    return {"TimClipPro/app.py": f"# app {pb}\n".encode(), "TimClipPro/engine.py": b"# engine\n",
            "TimClipPro/lich_su.py": b"PHIEN_BAN = 4\n", "TimClipPro/health_check.py": b"# health\n"}


@pytest.fixture()
def ban_ky(tmp_path):
    goc = rt.dong_goi_tu_files(_files(), "a" * 40, "b" * 40, "1.2.0", LOCK, str(tmp_path / "phat_hanh"),
                               tao_luc=TAO_LUC)
    khoa_rieng, tin_cay = rt.tao_khoa_thu(str(tmp_path / "khoa"))
    rt.sign(goc, khoa_rieng)
    key_id = list(mu.doc_khoa_tin_cay(tin_cay))[0]
    return {"goc": goc, "tin_cay": tin_cay, "key_id": key_id, "tmp": tmp_path}


def _cay(goc):
    return {f: hashlib.sha256(open(os.path.join(goc, f), "rb").read()).hexdigest() for f in sorted(os.listdir(goc))}


def test_kiem_sau_ky_dat_va_khong_sua_ban_da_ky(ban_ky):
    truoc = _cay(ban_ky["goc"])
    kq = rt.kiem_sau_ky(ban_ky["goc"], ban_ky["tin_cay"], key_id=ban_ky["key_id"], commit="a" * 40)
    assert kq["dat"] and kq["phien_ban"] == "1.2.0" and kq["key_id"] == ban_ky["key_id"]
    assert set(kq["kiem"]) >= {"khoa_la_bi_tu_choi", "manifest_sua_1_byte_bi_tu_choi", "chu_ky_sua_1_byte_bi_tu_choi",
                               "goi_sua_1_byte_bi_tu_choi", "thu_muc_dung_4_file", "khong_draft_khong_prerelease"}
    assert _cay(ban_ky["goc"]) == truoc                         # chỉ phá trên bản sao


def test_kiem_sau_ky_bao_sai_khoa_mong_doi_hoac_sai_commit(ban_ky):
    assert not rt.kiem_sau_ky(ban_ky["goc"], ban_ky["tin_cay"], key_id="0" * 16)["dat"]
    assert not rt.kiem_sau_ky(ban_ky["goc"], ban_ky["tin_cay"], commit="c" * 40)["dat"]


def test_kiem_sau_ky_tu_choi_ban_bi_sua_sau_ky_va_thu_muc_thua_file(ban_ky):
    with open(os.path.join(ban_ky["goc"], "ghi_chu.txt"), "w", encoding="utf-8") as f:
        f.write("thừa")
    assert not rt.kiem_sau_ky(ban_ky["goc"], ban_ky["tin_cay"])["kiem"]["thu_muc_dung_4_file"]
    os.remove(os.path.join(ban_ky["goc"], "ghi_chu.txt"))
    p = os.path.join(ban_ky["goc"], "TimClipPro-1.2.0-win_amd64.zip")
    b = bytearray(open(p, "rb").read())
    b[100] ^= 1
    open(p, "wb").write(bytes(b))
    with pytest.raises(rt.LoiPhatHanh):
        rt.kiem_sau_ky(ban_ky["goc"], ban_ky["tin_cay"])


def test_feed_tat_dinh_dung_noi_dung_va_khoi_powershell_ascii(ban_ky):
    a = rt.dong_feed(ban_ky["goc"], ban_ky["tin_cay"], str(ban_ky["tmp"] / "a"))
    b = rt.dong_feed(ban_ky["goc"], ban_ky["tin_cay"], str(ban_ky["tmp"] / "b"))
    assert a["zip_sha256"] == b["zip_sha256"]                  # cùng bản ký → cùng ZIP trên mọi máy
    with zipfile.ZipFile(a["zip"]) as z:
        ten = [i.filename for i in z.infolist()]
        assert ten == sorted(f"stable-1.2.0/{t}" for t in _cay(ban_ky["goc"]))
        assert all(i.compress_type == zipfile.ZIP_STORED and i.date_time == (2026, 10, 14, 12, 0, 2)
                   for i in z.infolist())
        for t, s in _cay(ban_ky["goc"]).items():
            assert hashlib.sha256(z.read(f"stable-1.2.0/{t}")).hexdigest() == s
    dong = open(a["sha256sums"], encoding="ascii").read().splitlines()
    assert dong[0] == f"{a['zip_sha256']}  TimClipPro_Feed_stable-1.2.0.zip" and len(dong) == 5
    ps = open(a["khoi_powershell"], encoding="ascii").read()
    assert a["zip_sha256"] in ps and all(s in ps for s in _cay(ban_ky["goc"]).values())
    assert "TimClipPro_Feed_stable-1.2.0.zip" in ps and "SAN SANG" in ps
    with pytest.raises(rt.LoiPhatHanh, match="không ghi đè"):
        rt.dong_feed(ban_ky["goc"], ban_ky["tin_cay"], str(ban_ky["tmp"] / "a"))


def test_feed_tu_choi_ban_khong_ky_bang_khoa_dang_tin(ban_ky):
    _, la = rt.tao_khoa_thu(str(ban_ky["tmp"] / "la"))
    with pytest.raises(mu.TuChoiGoi):
        rt.dong_feed(ban_ky["goc"], la, str(ban_ky["tmp"] / "c"))
    assert not os.path.exists(ban_ky["tmp"] / "c" / "TimClipPro_Feed_stable-1.2.0.zip")


def _co_commit(c):
    try:
        subprocess.run(["git", "-C", REPO, "cat-file", "-e", f"{c}^{{commit}}"], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _lock_launcher_co_bam():
    goc = subprocess.run(["git", "-C", REPO, "-c", "core.autocrlf=false", "show", f"{E49}:TimClipPro/launcher-lock.txt"],
                         capture_output=True, check=True).stdout.decode()
    return "".join(f"{d} \\\n    --hash=sha256:{'b' * 64}\n" for d in goc.splitlines()
                   if d and not d.startswith("#")).encode()


@pytest.mark.skipif(not _co_commit(E49), reason="cần repo git có commit e49340d")
def test_kit_dung_blob_git_cua_commit_va_tat_dinh(tmp_path):
    _, tin_cay = rt.tao_khoa_thu(str(tmp_path / "khoa"))
    lk = _lock_launcher_co_bam()
    a = rt.dung_kit(REPO, E49, lk, tin_cay, str(tmp_path / "a.zip"), cho_khoa_thu=True)
    b = rt.dung_kit(REPO, E49, lk, tin_cay, str(tmp_path / "b.zip"), cho_khoa_thu=True)
    assert a["zip_sha256"] == b["zip_sha256"] and a["commit"] == E49
    with zipfile.ZipFile(a["zip"]) as z:
        for f in rt.FILE_KIT:
            assert z.read(f) == subprocess.run(["git", "-C", REPO, "-c", "core.autocrlf=false", "show",
                                                f"{E49}:TimClipPro/{f}"], capture_output=True, check=True).stdout
        assert z.read("launcher-lock.txt") == lk and z.read("trusted_keys.json") == open(tin_cay, "rb").read()
        assert "KIT DIỄN TẬP" in z.read("DOC_TRUOC_KIT.txt").decode("utf-8")


@pytest.mark.skipif(not _co_commit(E49), reason="cần repo git có commit e49340d")
def test_kit_that_tu_choi_khoa_thu_lock_chua_bam_va_lech_pin(tmp_path):
    _, tin_cay = rt.tao_khoa_thu(str(tmp_path / "khoa"))
    lk = _lock_launcher_co_bam()
    with pytest.raises(rt.LoiPhatHanh, match="KHOÁ THỬ"):
        rt.dung_kit(REPO, E49, lk, tin_cay, str(tmp_path / "a.zip"))
    d = json.load(open(tin_cay, encoding="utf-8"))
    d["khoa"][0]["ghi_chu"] = "Khoá phát hành — PC2"                 # khoá lạ KHÔNG ghi chữ «THỬ» (review P3)
    la = tmp_path / "la.json"
    la.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(rt.LoiPhatHanh, match="release/trusted_keys.json"):
        rt.dung_kit(REPO, E49, lk, str(la), str(tmp_path / "e.zip"))
    that = os.path.join(REPO, "release", "trusted_keys.json")          # danh sách khoá công khai đang tin của repo
    with pytest.raises(rt.LoiPhatHanh, match="thiếu băm"):
        rt.dung_kit(REPO, E49, lk.replace(b"--hash=sha256:" + b"b" * 64, b""), that, str(tmp_path / "b.zip"))
    with pytest.raises(rt.LoiPhatHanh, match="pin"):
        rt.dung_kit(REPO, E49, lk.replace(b"cryptography==50.0.0", b"cryptography==49.0.0"), that,
                    str(tmp_path / "c.zip"))
    assert rt.dung_kit(REPO, E49, lk, that, str(tmp_path / "d.zip"))["khoa"] == sorted(mu.doc_khoa_tin_cay(that))
    assert not any(os.path.exists(tmp_path / f"{x}.zip") for x in "abce")


@pytest.mark.skipif(os.name != "nt" or not __import__("shutil").which("powershell.exe"), reason="cần PowerShell")
def test_khoi_powershell_chay_that_ba_ca(ban_ky):
    """Khối PowerShell NGUYÊN VĂN (chỉ đổi 2 dòng $zip/$feed sang thư mục tạm): ZIP đúng → «SAN SANG» + 4 «KHOP»;
    chạy lại → «DA CO», không giải nén đè; ZIP sửa 1 byte → «ZIP SAI MA BAM», không giải nén gì."""
    tmp = ban_ky["tmp"]
    kq = rt.dong_feed(ban_ky["goc"], ban_ky["tin_cay"], str(tmp / "feed_ra"))
    khoi = open(kq["khoi_powershell"], encoding="ascii").read()
    dong_zip = r"  $zip  = Join-Path $env:USERPROFILE 'Downloads\TimClipPro_Feed_stable-1.2.0.zip'"
    dong_feed = r"  $feed = 'C:\TimClipPro_Feed'"
    assert khoi.count(dong_zip) == 1 and khoi.count(dong_feed) == 1

    def chay(ten, zip_p, feed_p):
        os.makedirs(feed_p, exist_ok=True)
        b = khoi.replace(dong_zip, f"  $zip  = '{zip_p}'").replace(dong_feed, f"  $feed = '{feed_p}'")
        p = tmp / f"{ten}.ps1"
        p.write_text(b, encoding="ascii", newline="\r\n")
        r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(p)],
                           capture_output=True, text=True, encoding="cp1252", errors="replace", timeout=300)
        return (r.stdout + r.stderr).strip()
    o1 = chay("dung", kq["zip"], str(tmp / "Feed1"))
    assert o1.count("KHOP") == 4 and "SAI" not in o1 and o1.endswith(r"SAN SANG: chay C:\TimClipPro\CapNhat.bat")
    o2 = chay("chay_lai", kq["zip"], str(tmp / "Feed1"))
    assert o2.startswith("DA CO") and "SAN SANG" not in o2
    hong = tmp / "hong.zip"
    b = bytearray(open(kq["zip"], "rb").read())
    b[len(b) // 2] ^= 1
    hong.write_bytes(bytes(b))
    o3 = chay("zip_hong", str(hong), str(tmp / "Feed2"))
    assert o3.startswith("ZIP SAI MA BAM") and not os.listdir(tmp / "Feed2")


def test_sign_chi_ky_manifest_hop_le(ban_ky, tmp_path):
    """Review P2-3: «sign» ký đúng byte của manifest.json — nếu file đó là nội dung uỷ quyền (tiền tố miền) thì chữ ký
    thành chữ ký uỷ quyền hợp lệ, vượt qua bước ky-uy-quyen. Không phải manifest hợp lệ → từ chối, không ghi chữ ký."""
    import uy_quyen_khoa as uq

    goc = tmp_path / "stable-9.9.9"
    goc.mkdir()
    (goc / mu.TEN_MANIFEST).write_bytes(uq.MIEN_UY_QUYEN + uq.chuan_hoa({"loai": uq.LOAI_UY_QUYEN}))
    khoa_rieng, _ = rt.tao_khoa_thu(str(tmp_path / "k"))
    with pytest.raises((rt.LoiPhatHanh, mu.LoiCapNhat)):
        rt.sign(str(goc), khoa_rieng)
    assert not (goc / mu.TEN_CHU_KY).exists()


def test_kiem_sau_ky_bat_khoa_yeu_trong_danh_sach(ban_ky):
    d = json.load(open(ban_ky["tin_cay"], encoding="utf-8"))
    raw = bytes.fromhex("01" + "00" * 31)
    import base64

    import uy_quyen_khoa as uq

    d["khoa"].append({"key_id": uq.tao_key_id(raw), "ed25519_pub_b64": base64.b64encode(raw).decode()})
    p = ban_ky["tmp"] / "co_khoa_yeu.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    kq = rt.kiem_sau_ky(ban_ky["goc"], str(p))
    assert not kq["dat"] and not kq["kiem"]["danh_sach_khong_co_khoa_yeu"]


@pytest.mark.skipif(not _co_commit(E49), reason="cần repo git có commit e49340d")
def test_kit_doi_chieu_danh_sach_DA_COMMIT_khong_phai_file_dang_sua(tmp_path):
    """Review lượt 2: danh sách mặc định là release/trusted_keys.json của HEAD (đã qua PR) — sửa file cây làm việc (thêm
    khoá lạ) rồi dùng chính file đó làm --tin-cay KHÔNG qua được."""
    _, tin_cay = rt.tao_khoa_thu(str(tmp_path / "khoa"))
    lk = _lock_launcher_co_bam()
    goc = json.load(open(os.path.join(REPO, "release", "trusted_keys.json"), encoding="utf-8"))
    la = json.load(open(tin_cay, encoding="utf-8"))["khoa"][0]
    la["ghi_chu"] = "Khoá phát hành — máy lạ"
    sua = tmp_path / "trusted_keys_da_sua.json"
    sua.write_text(json.dumps({"khoa": goc["khoa"] + [la]}), encoding="utf-8")
    with pytest.raises(rt.LoiPhatHanh, match="release/trusted_keys.json"):
        rt.dung_kit(REPO, E49, lk, str(sua), str(tmp_path / "a.zip"))
    assert not os.path.exists(tmp_path / "a.zip")
