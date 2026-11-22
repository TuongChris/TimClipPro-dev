"""Đóng bộ cài ĐẦY ĐỦ (một ZIP) cho máy Windows mới: bản Stable ĐÃ KÝ + bộ kit + Python 3.12 xách tay + FFmpeg + Node.js +
wheelhouse — máy mới không cần cài gì trước, lúc cài không cần mạng. Cài: CAI_DAT_TimClipPro.bat → cai_dat/CaiDat.ps1.

    <python có cryptography> -I -B tools/bo_cai_day_du/dung_bo_cai.py --kit <kit.zip> --feed <…/stable-X.Y.Z>
        --wheelhouse <thư mục wheel> --lock <requirements-lock.txt> --python-msi <thư mục core.msi exe.msi lib.msi>
        --ffmpeg <thư mục có bin/ffmpeg.exe, bin/ffprobe.exe, LICENSE> --node <thư mục có node.exe, LICENSE> --out <x.zip>

Kiểm trước khi đóng: chữ ký bản phát hành theo trusted_keys.json CỦA KIT; MSI Python và node.exe có chữ ký Authenticode
hợp lệ của PSF / OpenJS; mỗi gói trong hai lock (runtime + launcher) có ít nhất một wheel trùng băm (chỉ lấy wheel trùng
băm). Python xách tay = giải nén quản trị (``msiexec /a``) ba MSI chính thức — không đăng ký gì vào Windows.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

THU_MUC = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THU_MUC))
sys.path.insert(0, os.path.join(REPO, "TimClipPro"))

import managed_update as mu

_GOI = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", re.MULTILINE)
_BAM = re.compile(r"--hash=sha256:([0-9a-f]{64})")
NGUOI_KY = {"python": "Python Software Foundation", "node": "OpenJS Foundation"}


class LoiDongGoi(RuntimeError):
    pass


def sha(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for khoi in iter(lambda: f.read(1 << 20), b""):
            h.update(khoi)
    return h.hexdigest()


def doc_lock(raw: str) -> dict:
    """{tên chuẩn: tập băm} — mỗi khối «tên==bản» kèm các dòng --hash ngay sau nó."""
    kq, ten = {}, None
    for dong in raw.splitlines():
        m = _GOI.match(dong.strip())
        if m:
            ten = re.sub(r"[-_.]+", "-", m.group(1)).lower()
            kq.setdefault(ten, set())
        if ten:
            kq[ten].update(_BAM.findall(dong))
    return kq


def chon_wheel(wheelhouse: str, locks: list) -> list:
    """Wheel trùng băm với lock; mỗi gói của mọi lock phải có ít nhất một wheel."""
    bam_wheel = {sha(os.path.join(wheelhouse, w)): w for w in sorted(os.listdir(wheelhouse)) if w.endswith(".whl")}
    can, thieu = set(), []
    for raw in locks:
        for ten, bams in doc_lock(raw).items():
            co = bams & set(bam_wheel)
            if not co:
                thieu.append(ten)
            can |= co
    if thieu:
        raise LoiDongGoi("wheelhouse thiếu wheel trùng băm cho: " + ", ".join(sorted(set(thieu))))
    return sorted(bam_wheel[b] for b in can)


def kiem_authenticode(p: str, nguoi_ky: str) -> None:
    duong = os.path.abspath(p).replace("'", "''")
    lenh = (f"$s = Get-AuthenticodeSignature -LiteralPath '{duong}'; "
            "'{0}|{1}' -f $s.Status, $s.SignerCertificate.Subject")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", lenh], capture_output=True, text=True, check=True)
    trang_thai, _, chu = r.stdout.strip().partition("|")
    if trang_thai != "Valid" or f"CN={nguoi_ky}," not in chu:
        raise LoiDongGoi(f"{os.path.basename(p)}: chữ ký Authenticode không hợp lệ ({trang_thai}, {chu[:80]})")


def giai_nen_python(thu_muc_msi: str, dich: str) -> str:
    thu_muc_msi, dich = os.path.abspath(thu_muc_msi), os.path.abspath(dich)  # msiexec không nhận «/» (mã 1619)
    os.makedirs(dich)
    for ten in ("core", "exe", "lib"):
        msi = os.path.join(thu_muc_msi, f"{ten}.msi")
        kiem_authenticode(msi, NGUOI_KY["python"])
        r = subprocess.run(["msiexec", "/a", msi, f"TARGETDIR={dich}", "/qn"], check=False)
        if r.returncode != 0:
            raise LoiDongGoi(f"msiexec /a {ten}.msi mã {r.returncode}")
    for f in os.listdir(dich):
        if f.lower().endswith(".msi"):
            os.remove(os.path.join(dich, f))
    py = os.path.join(dich, "python.exe")
    v = subprocess.run([py, "-I", "-B", "-c", "import sys, venv, ensurepip, ssl, sqlite3; print('%d.%d.%d' % sys.version_info[:3])"],
                       capture_output=True, text=True, check=True).stdout.strip()
    if not v.startswith("3.12."):
        raise LoiDongGoi(f"Python xách tay sai bản: {v}")
    sp = os.path.join(dich, "Lib", "site-packages")
    la = [x for x in os.listdir(sp) if x != "README.txt"] if os.path.isdir(sp) else []
    if la:
        raise LoiDongGoi(f"site-packages của Python xách tay không trống: {la}")
    return v


def phien_ban_exe(lenh: list) -> str:
    return subprocess.run(lenh, capture_output=True, text=True, check=True).stdout.splitlines()[0].strip()


def dong(a) -> dict:
    if os.path.exists(a.out):
        raise LoiDongGoi(f"Đã có {a.out} — không ghi đè.")
    with open(os.path.join(a.feed, "manifest.json"), "rb") as f:
        m = mu.doc_manifest(f.read())
    pb = m.phien_ban
    if os.path.basename(os.path.normpath(a.feed)) != f"stable-{pb}":
        raise LoiDongGoi("thư mục bản phát hành phải tên stable-<phiên bản trong manifest>")
    goc_ten = f"TimClipPro_CaiDat_{pb}"
    with tempfile.TemporaryDirectory(prefix="bo_cai_", dir=os.path.dirname(os.path.abspath(a.out))) as tam:
        goc = os.path.join(tam, goc_ten)
        cd = os.path.join(goc, "cai_dat")
        os.makedirs(cd)
        # kit + kiểm chữ ký bản phát hành bằng CHÍNH khoá tin cậy của kit (máy mới sẽ tin đúng các khoá này)
        with zipfile.ZipFile(a.kit) as z:
            commit_kit = z.comment.decode("ascii")
            z.extractall(os.path.join(cd, "kit"))
        tin_cay = os.path.join(cd, "kit", "trusted_keys.json")
        import release_tool

        mv = release_tool.verify(a.feed, tin_cay)
        if mv.phien_ban != pb or mv.commit != m.commit:
            raise LoiDongGoi("verify trả phiên bản/commit khác manifest")
        dich_feed = os.path.join(cd, "feed", f"stable-{pb}")
        os.makedirs(dich_feed)
        ten_feed = sorted(os.listdir(a.feed))
        if len(ten_feed) != 4 or "manifest.json.sig" not in ten_feed:
            raise LoiDongGoi(f"bản phát hành phải có đúng 4 file đã ký, đang có {ten_feed}")
        for f in ten_feed:
            shutil.copy2(os.path.join(a.feed, f), dich_feed)
        # wheel: runtime lock + launcher lock của kit
        locks = [pathlib.Path(a.lock).read_text(encoding="utf-8"),
                 pathlib.Path(cd, "kit", "launcher-lock.txt").read_text(encoding="utf-8")]
        wheel = chon_wheel(a.wheelhouse, locks)
        os.makedirs(os.path.join(cd, "wheelhouse"))
        for w in wheel:
            shutil.copy2(os.path.join(a.wheelhouse, w), os.path.join(cd, "wheelhouse", w))
        # Python xách tay, FFmpeg, Node
        v_py = giai_nen_python(a.python_msi, os.path.join(cd, "python"))
        os.makedirs(os.path.join(cd, "ffmpeg"))
        for f in ("bin/ffmpeg.exe", "bin/ffprobe.exe", "LICENSE"):
            shutil.copy2(os.path.join(a.ffmpeg, f), os.path.join(cd, "ffmpeg", os.path.basename(f)))
        v_ff = phien_ban_exe([os.path.join(cd, "ffmpeg", "ffmpeg.exe"), "-hide_banner", "-version"]).split()[2]
        os.makedirs(os.path.join(cd, "node"))
        shutil.copy2(os.path.join(a.node, "node.exe"), os.path.join(cd, "node", "node.exe"))
        kiem_authenticode(os.path.join(cd, "node", "node.exe"), NGUOI_KY["node"])
        v_node = phien_ban_exe([os.path.join(cd, "node", "node.exe"), "--version"])
        # Bộ cài MSI của Node không để LICENSE trong thư mục cài → ghi chú giấy phép + chỗ đọc toàn văn đúng bản.
        with open(os.path.join(cd, "node", "LICENSE.txt"), "w", encoding="utf-8") as f:
            f.write(f"Node.js {v_node} — MIT License. Copyright OpenJS Foundation and other contributors.\n"
                    f"Toàn văn (gồm giấy phép thư viện bên thứ ba): https://github.com/nodejs/node/blob/{v_node}/LICENSE\n")
        # script cài + hướng dẫn
        shutil.copy2(os.path.join(THU_MUC, "CaiDat.ps1"), os.path.join(cd, "CaiDat.ps1"))
        shutil.copy2(os.path.join(THU_MUC, "CAI_DAT_TimClipPro.bat"), os.path.join(goc, "CAI_DAT_TimClipPro.bat"))
        hd = pathlib.Path(THU_MUC, "HUONG_DAN_CAI_DAT.txt").read_text(encoding="utf-8-sig")
        for k, v in {"PHIEN_BAN": pb, "COMMIT12": m.commit[:12], "FFMPEG": v_ff, "NODE": v_node}.items():
            hd = hd.replace("{" + k + "}", v)
        if re.search(r"\{[A-Z0-9_]+\}", hd):
            raise LoiDongGoi("hướng dẫn còn chỗ trống")
        with open(os.path.join(goc, "HUONG_DAN_CAI_DAT.txt"), "wb") as f:
            f.write(b"\xef\xbb\xbf" + hd.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
        tt = {"phien_ban": pb, "commit": m.commit, "kit_commit": commit_kit, "python": v_py, "ffmpeg": v_ff,
              "node": v_node, "so_wheel": len(wheel)}
        with open(os.path.join(cd, "thong_tin.json"), "w", encoding="utf-8") as f:
            json.dump(tt, f, ensure_ascii=False, indent=1)
        # mã băm mọi file trong cai_dat/ — CaiDat.ps1 kiểm trước khi ghi gì vào máy
        dong_bam = []
        for r, _, fs in os.walk(cd):
            for f in fs:
                p = os.path.join(r, f)
                dong_bam.append(f"{sha(p)}  {os.path.relpath(p, cd).replace(os.sep, '/')}")
        with open(os.path.join(cd, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(sorted(dong_bam, key=lambda x: x[66:])) + "\n")
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with zipfile.ZipFile(a.out, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for r, _, fs in os.walk(goc):
                for f in sorted(fs):
                    p = os.path.join(r, f)
                    z.write(p, os.path.relpath(p, tam).replace(os.sep, "/"))
    return {"zip": a.out, "byte": os.path.getsize(a.out), "sha256": sha(a.out), "so_file": len(dong_bam) + 3, **tt}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    for k in ("kit", "feed", "wheelhouse", "lock", "python-msi", "ffmpeg", "node", "out"):
        ap.add_argument(f"--{k}", required=True)
    a = ap.parse_args(argv)
    try:
        print(json.dumps(dong(a), ensure_ascii=False, indent=1))
    except (LoiDongGoi, mu.LoiCapNhat, OSError, subprocess.CalledProcessError) as e:
        print(f"[LỖI] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
