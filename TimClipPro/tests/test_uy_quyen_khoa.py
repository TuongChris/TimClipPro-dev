# -*- coding: utf-8 -*-
"""Ghi danh khoá ký THỨ HAI vào trust store của một cài đặt managed (uy_quyen_khoa.py + release_tool tao-khoa/ky-uy-quyen)
— docs/UY_QUYEN_KHOA.md. Cài đặt TỔNG HỢP như PC2: ``launcher/`` là BẢN SAO 5 file launcher của repo (= bản bootstrap
e49340d — test riêng nạp đúng blob e49340d), trust store tin MỘT khoá ``k1`` (vai PC1), bản 1.1.1 đang kích hoạt do k1
ký. Khoá thử sinh lúc chạy, không mạng, không đụng cài đặt thật."""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import launcher
import managed_update as mu
import release_tool as rt
import runtime_paths
import uy_quyen_khoa as uq
from cap_nhat_gia import KhoaThu, MoiTruongGia, phat_hanh

MA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_LAUNCHER = ("launcher.py", "managed_update.py", "maintenance_gate.py", "khoa.py", "runtime_paths.py")
BAY_GIO = datetime(2026, 10, 15, 8, 0, 0, tzinfo=timezone.utc)
REPO = os.environ.get("TIMCLIP_REPO_GOC") or os.path.dirname(MA)
E49 = "e49340d7d8cf01ec51cea914b3f4509197b5f964"          # commit của bộ bootstrap 1.0.0 đã cài trên PC2
MK_THU = b"mat-khau-thu-dai-16+"                            # mật khẩu GIẢ của khoá THỬ sinh lúc chạy
MK_PC1_THU = b"mk-pc1-thu-dai-16"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _raw(k: Ed25519PrivateKey) -> bytes:
    return k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _dung_cai_dat(tmp_path, ten: str, khoa_cu: KhoaThu, *, launcher_tu=None, trust_bytes=None) -> dict:
    goc = str(tmp_path / ten / "TimClipPro")
    state = str(tmp_path / ten / "TimClipPro_State")
    nguon = str(tmp_path / ten / "Feed")
    lc = os.path.join(goc, "launcher")
    os.makedirs(lc)
    os.makedirs(nguon)
    os.makedirs(state)
    for f in FILE_LAUNCHER:
        if launcher_tu is None:
            shutil.copy2(os.path.join(MA, f), os.path.join(lc, f))
        else:
            with open(os.path.join(lc, f), "wb") as g:
                g.write(launcher_tu[f])
    tc = os.path.join(lc, launcher.TEN_KHOA_TIN_CAY)
    with open(tc, "wb") as f:
        f.write(trust_bytes if trust_bytes is not None else json.dumps(
            {"khoa": [{"key_id": khoa_cu.key_id, "ed25519_pub_b64": _b64(khoa_cu.raw),
                       "ghi_chu": "Khoá phát hành TimClipPro kênh Stable — tạo 2026-10-08 trên PC1"}]},
            ensure_ascii=False, indent=1).encode("utf-8"))
    with open(os.path.join(lc, launcher.TEN_CAU_HINH), "w", encoding="utf-8") as f:
        json.dump({"state_root": state, "nguon": {"loai": "thu_muc", "duong_dan": nguon}, "python_goc": "",
                   "han_cho_ranh_s": 0.3}, f)
    runtime_paths.tao_dinh_danh(state, installation_root=goc)
    gia = MoiTruongGia(state)
    thay = dict(tao_moi_truong=gia.tao_moi_truong, kiem_suc_khoe=gia.kiem_suc_khoe, di_chuyen=gia.di_chuyen,
                sao_luu=gia.sao_luu, phien_ban_db=gia.phien_ban_db)

    def main(*doi_so):
        return launcher.main(list(doi_so), goc=goc, chay=lambda *a, **k: 0, **thay)

    phat_hanh(nguon, "1.1.1", khoa_cu)
    assert main("update", "prepare") == 0 and main("update", "apply") == 0
    return {"goc": goc, "state": state, "nguon": nguon, "tc": tc, "main": main, "gia": gia}


@pytest.fixture()
def may(tmp_path):
    """k1 = khoá PC1 (đang tin), k2 = khoá PC2 (mới, chưa tin), k3 = khoá lạ."""
    k1, k3 = KhoaThu(), KhoaThu()
    k2 = Ed25519PrivateKey.generate()
    pc2 = _dung_cai_dat(tmp_path, "pc2", k1)
    tin_cay_k1 = mu.doc_khoa_tin_cay(pc2["tc"])                 # danh sách khoá CÔNG KHAI phía PC1 giữ
    return {"k1": k1, "k2": k2, "k3": k3, "id2": uq.tao_key_id(_raw(k2)), "pc2": pc2,
            "tin_cay_k1": tin_cay_k1, "tmp": tmp_path, "pub2": _ghi_khoa_cong_khai(tmp_path / "pc2" / "khoa", k2)}


def _ghi_khoa_cong_khai(thu_muc, k) -> str:
    """Như ``khoa_cong_khai_<id>.json`` mà ``tao-khoa`` để lại trong thư mục khoá CỦA máy (ngoài repo)."""
    os.makedirs(thu_muc, exist_ok=True)
    kid = uq.tao_key_id(_raw(k))
    p = os.path.join(str(thu_muc), f"khoa_cong_khai_{kid}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"khoa": [{"key_id": kid, "ed25519_pub_b64": _b64(_raw(k))}]}, f)
    with open(os.path.join(str(thu_muc), f"khoa_rieng_phat_hanh_{kid}.pem"), "wb") as f:
        f.write(b"CHO GIU CHO - khong phai khoa that\n")      # công cụ chỉ kiểm file khoá riêng CÓ MẶT, không đọc
    return p


def _byte(p):
    with open(p, "rb") as f:
        return f.read()


def _cay(goc):
    """{đường dẫn tương đối: sha256} của MỌI file dưới goc (kể cả __pycache__)."""
    kq = {}
    for d, _, fs in os.walk(goc):
        for f in fs:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, goc).replace(os.sep, "/")
            if rel != "update_state/updater.lock":          # file khoá: mỗi lần lấy khoá ghi PID/thời điểm
                kq[rel] = hashlib.sha256(_byte(p)).hexdigest()
    return kq


def _yeu_cau(may, *, khoa=None, cai=None, ten_may="PC2"):
    cai = cai or may["pc2"]
    L = uq.nap_launcher(cai["goc"])
    tt = uq.doc_cai_dat(cai["goc"], L)
    return uq.tao_yeu_cau(khoa or may["k2"], ten_may=ten_may, cai_dat=tt, bay_gio=BAY_GIO)


def _uy_quyen(may, raw_yc=None, *, ky=None, tin_cay=None, bay_gio=BAY_GIO, han_ngay=30):
    return uq.tao_uy_quyen(raw_yc or _yeu_cau(may), ky or may["k1"].rieng,
                           khoa_tin_cay=tin_cay or may["tin_cay_k1"], bay_gio=bay_gio, han_ngay=han_ngay)


def _ghi_danh(may, raw_uq, cai=None, *, dong_y=True, bay_gio=BAY_GIO + timedelta(hours=1), khoa_cong_khai=None,
              **kw):
    hoi = []

    def xac_nhan(tom_tat):
        hoi.append(tom_tat)
        return dong_y
    kq = uq.ghi_danh((cai or may["pc2"])["goc"], raw_uq, khoa_cong_khai=khoa_cong_khai or may["pub2"],
                     xac_nhan=xac_nhan, bay_gio=bay_gio, **kw)
    return kq, hoi


# ---------------------------------------------------------------------------
#  Phase A: bộ cập nhật HIỆN CÓ đã tin nhiều khoá — chỉ thiếu đường ghi danh
# ---------------------------------------------------------------------------

def test_trust_store_hien_tai_tin_nhieu_khoa_chon_theo_key_id(tmp_path):
    a, b = KhoaThu(), KhoaThu()
    p = str(tmp_path / "trusted_keys.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"khoa": [{"key_id": k.key_id, "ed25519_pub_b64": _b64(k.raw)} for k in (a, b)]}, f)
    tc = mu.doc_khoa_tin_cay(p)
    assert set(tc) == {a.key_id, b.key_id}
    for k in (a, b):
        assert mu.kiem_chu_ky(b"manifest", k.ky(b"manifest"), tc) == k.key_id


# ---------------------------------------------------------------------------
#  Yêu cầu (PC2) — không bí mật, không đường dẫn; tự ký bằng khoá mới
# ---------------------------------------------------------------------------

def test_yeu_cau_rang_buoc_cai_dat_khong_lo_dinh_danh_duong_dan(may):
    raw = _yeu_cau(may)
    yc = uq.doc_yeu_cau(raw)
    iid = runtime_paths.doc_dinh_danh(may["pc2"]["state"])["installation_id"]
    assert yc["khoa_moi"] == {"key_id": may["id2"], "ed25519_pub_b64": _b64(_raw(may["k2"]))}
    assert yc["cai_dat_sha256"] == hashlib.sha256(uq.MIEN_CAI_DAT + iid.encode()).hexdigest()
    assert yc["trust_store_sha256"] == hashlib.sha256(_byte(may["pc2"]["tc"])).hexdigest()
    assert yc["khoa_hien_co"] == [may["k1"].key_id] and yc["ban_dang_chay"] == "1.1.1"
    van_ban = raw.decode("utf-8")
    for bi_mat in (iid, may["pc2"]["goc"], may["pc2"]["state"], json.dumps(may["pc2"]["goc"])[1:-1],
                   os.environ.get("USERNAME", "khong-co-ten") + os.sep, "PRIVATE"):
        assert bi_mat not in van_ban


def test_yeu_cau_bi_sua_hoac_khong_do_khoa_moi_ky_thi_pc1_tu_choi(may):
    d = json.loads(_yeu_cau(may))
    d["noi_dung"]["khoa_moi"] = {"key_id": may["k3"].key_id, "ed25519_pub_b64": _b64(may["k3"].raw)}
    with pytest.raises(uq.LoiUyQuyen):
        uq.doc_yeu_cau(json.dumps(d).encode())
    with pytest.raises(uq.LoiUyQuyen):
        _uy_quyen(may, json.dumps(d).encode())


def test_pc1_chi_ky_bang_khoa_dang_duoc_tin_ca_hai_phia(may):
    with pytest.raises(uq.LoiUyQuyen, match="danh sách khoá công khai"):
        _uy_quyen(may, ky=may["k3"].rieng)                    # khoá ký không có trong trust list của PC1
    tin_k3 = {**may["tin_cay_k1"], **mu.doc_khoa_tin_cay(may["k3"].ghi_tin_cay(str(may["tmp"] / "k3.json")))}
    with pytest.raises(uq.LoiUyQuyen, match="KHÔNG tin"):
        _uy_quyen(may, ky=may["k3"].rieng, tin_cay=tin_k3)     # máy đích không tin k3


# ---------------------------------------------------------------------------
#  Đường chính: PC1 ký → PC2 ghi danh → hai khoá cùng xác minh
# ---------------------------------------------------------------------------

def test_ghi_danh_roi_ban_do_pc2_ky_cai_duoc_va_ban_pc1_ky_van_cai_duoc(may):
    pc2, k1 = may["pc2"], may["k1"]
    phat_hanh(pc2["nguon"], "1.1.2", None, ky_bang=_KyBang(may["k2"]))
    assert pc2["main"]("update", "prepare") == 0                       # TRƯỚC ghi danh: bỏ qua (khoá lạ)
    assert json.loads(_byte(os.path.join(pc2["goc"], "update_state", "current.json")))["phien_ban"] == "1.1.1"
    truoc = _byte(pc2["tc"])
    kq, hoi = _ghi_danh(may, _uy_quyen(may))
    assert kq["trang_thai"] == "DA_GHI_DANH" and len(hoi) == 1 and hoi[0]["khoa_moi"] == may["id2"]
    tc = mu.doc_khoa_tin_cay(pc2["tc"])
    assert set(tc) == {k1.key_id, may["id2"]}
    assert tc[k1.key_id].public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw) == k1.raw
    cu = json.loads(truoc)["khoa"][0]
    assert json.loads(_byte(pc2["tc"]))["khoa"][0] == cu                # mục khoá PC1 giữ NGUYÊN
    assert _byte(kq["sao_luu"]) == truoc                                # sao lưu đúng byte cũ
    assert pc2["main"]("update", "prepare") == 0 and pc2["main"]("update", "apply") == 0
    cur = json.loads(_byte(os.path.join(pc2["goc"], "update_state", "current.json")))
    assert cur["phien_ban"] == "1.1.2"                                  # bản do PC2 ký
    phat_hanh(pc2["nguon"], "1.1.3", k1)
    assert pc2["main"]("update", "prepare") == 0 and pc2["main"]("update", "apply") == 0
    cur = json.loads(_byte(os.path.join(pc2["goc"], "update_state", "current.json")))
    assert cur["phien_ban"] == "1.1.3"                                  # PC1 vẫn ký được (máy dự phòng)
    bac_si = {ten: (muc, ghi_chu) for muc, ten, ghi_chu in launcher.doctor(pc2["goc"])}
    assert bac_si["Khoá tin cậy"] == (launcher.DAT, "2 khoá")
    assert bac_si["Bản đang kích hoạt"][0] == launcher.DAT


class _KyBang:
    """Ký manifest bằng một Ed25519PrivateKey (giao diện như KhoaThu.ky)."""

    def __init__(self, k):
        self.k = k
        self.key_id = uq.tao_key_id(_raw(k))

    def ky(self, raw):
        return json.dumps({"thuat_toan": "ed25519", "key_id": self.key_id,
                           "chu_ky_b64": _b64(self.k.sign(raw))}).encode()


def test_khoa_la_van_bi_tu_choi_sau_ghi_danh(may):
    pc2 = may["pc2"]
    _ghi_danh(may, _uy_quyen(may))
    phat_hanh(pc2["nguon"], "1.1.2", may["k3"])
    assert pc2["main"]("update", "prepare") == 0
    assert json.loads(_byte(os.path.join(pc2["goc"], "update_state", "current.json")))["phien_ban"] == "1.1.1"
    assert "1.1.2" not in json.loads(_byte(os.path.join(pc2["goc"], "update_state", "current.json")))["release"]


# ---------------------------------------------------------------------------
#  Uỷ quyền giả / sai đích / dùng lại — từ chối, trust store KHÔNG đổi, không sao lưu
# ---------------------------------------------------------------------------

def _sua_noi_dung(raw, **sua):
    d = json.loads(raw)
    d["noi_dung"].update(sua)
    return json.dumps(d).encode()


def _ky_lai(raw, k: Ed25519PrivateKey, mien=None):
    d = json.loads(raw)
    d["chu_ky"] = {"thuat_toan": "ed25519", "key_id": uq.tao_key_id(_raw(k)),
                   "chu_ky_b64": _b64(k.sign((mien or uq.MIEN_UY_QUYEN) + uq.chuan_hoa(d["noi_dung"])))}
    return json.dumps(d).encode()


def _gia_mao(may):
    raw = _uy_quyen(may)
    k3, k2 = may["k3"].rieng, may["k2"]
    d = json.loads(raw)
    sig = bytearray(base64.b64decode(d["chu_ky"]["chu_ky_b64"]))
    sig[5] ^= 1
    d["chu_ky"]["chu_ky_b64"] = _b64(bytes(sig))
    lat_bit = json.dumps(d).encode()
    k3_ky_ten_k1 = json.loads(_ky_lai(raw, k3))
    k3_ky_ten_k1["chu_ky"]["key_id"] = may["k1"].key_id
    return {
        "khoa_la_ky": _ky_lai(_sua_noi_dung(raw, ky_boi=may["k3"].key_id), k3),
        "khoa_moi_tu_uy_quyen": _ky_lai(_sua_noi_dung(raw, ky_boi=may["id2"]), k2),
        "doi_khoa_moi_sau_ky": _sua_noi_dung(raw, khoa_moi={"key_id": may["k3"].key_id,
                                                           "ed25519_pub_b64": _b64(may["k3"].raw)}),
        "gia_han_sau_ky": _sua_noi_dung(raw, het_han="2026-11-29T08:00:00Z"),       # +45 ngày: hợp lệ về hạn
        "lat_1_bit_chu_ky": lat_bit,
        "k3_ky_mao_key_id_k1": json.dumps(k3_ky_ten_k1).encode(),
        "ky_nham_mien_yeu_cau": _ky_lai(raw, may["k1"].rieng, uq.MIEN_YEU_CAU),
        "chu_ky_manifest_dung_lai": json.dumps({**d, "chu_ky": json.loads(may["k1"].ky(uq.chuan_hoa(
            json.loads(raw)["noi_dung"])))}).encode(),
        "doi_loai": _ky_lai(_sua_noi_dung(raw, loai=uq.LOAI_YEU_CAU), may["k1"].rieng),
        # khoá JSON trùng CÙNG giá trị: parser «khoá sau thắng» vẫn ra đúng nội dung đã ký → chỉ luật cấm trùng bắt được
        "trung_khoa_json": raw.replace(b'"noi_dung": {', b'"noi_dung": {"ten_may": "PC2", ', 1),
        "qua_lon": raw + b" " * (uq.GIOI_HAN_FILE + 1),
        "khong_phai_json": b"\x00\xff",
        "thieu_truong": _ky_lai(json.dumps({**json.loads(raw), "noi_dung": {
            k: v for k, v in json.loads(raw)["noi_dung"].items() if k != "trust_store_sha256"}}).encode(),
            may["k1"].rieng),
    }


LY_DO_GIA_MAO = {"khoa_la_ky": "KHÔNG được tin", "khoa_moi_tu_uy_quyen": "tự uỷ quyền",
                 "doi_khoa_moi_sau_ky": "KHÔNG hợp lệ", "gia_han_sau_ky": "KHÔNG hợp lệ", "lat_1_bit_chu_ky": "KHÔNG hợp lệ",
                 "k3_ky_mao_key_id_k1": "KHÔNG hợp lệ", "ky_nham_mien_yeu_cau": "KHÔNG hợp lệ",
                 "chu_ky_manifest_dung_lai": "KHÔNG hợp lệ", "doi_loai": "Sai loại", "trung_khoa_json": "trùng khoá JSON",
                 "qua_lon": "quá lớn", "khong_phai_json": "hỏng", "thieu_truong": "thiếu/thừa"}


@pytest.mark.parametrize("ca", ["khoa_la_ky", "khoa_moi_tu_uy_quyen", "doi_khoa_moi_sau_ky", "gia_han_sau_ky",
                                "lat_1_bit_chu_ky", "k3_ky_mao_key_id_k1", "ky_nham_mien_yeu_cau",
                                "chu_ky_manifest_dung_lai", "doi_loai", "trung_khoa_json", "qua_lon",
                                "khong_phai_json", "thieu_truong"])
def test_uy_quyen_gia_mao_bi_tu_choi_khong_doi_gi(may, ca):
    raw = _gia_mao(may)[ca]
    truoc = _cay(may["pc2"]["goc"])
    with pytest.raises(uq.LoiUyQuyen, match=LY_DO_GIA_MAO[ca]):
        _ghi_danh(may, raw)
    assert _cay(may["pc2"]["goc"]) == {k: v for k, v in truoc.items()}        # không file nào đổi/thêm
    assert not os.path.exists(os.path.join(may["pc2"]["goc"], "launcher", uq.THU_MUC_SAO_LUU))


def test_uy_quyen_cho_cai_dat_khac_bi_tu_choi(may):
    """Hai cài đặt cùng trust store (cùng bộ kit) — uỷ quyền chỉ dùng được ở ĐÚNG cài đặt đã tạo yêu cầu."""
    may_b = _dung_cai_dat(may["tmp"], "may_b", may["k1"], trust_bytes=_byte(may["pc2"]["tc"]))
    raw = _uy_quyen(may)                                          # yêu cầu tạo trên pc2
    truoc = _byte(may_b["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="cài đặt KHÁC"):
        _ghi_danh(may, raw, may_b)
    assert _byte(may_b["tc"]) == truoc


def test_uy_quyen_khi_trust_store_da_doi_bi_tu_choi(may):
    raw = _uy_quyen(may)
    d = json.loads(_byte(may["pc2"]["tc"]))
    with open(may["pc2"]["tc"], "w", encoding="utf-8") as f:     # cùng khoá, khác byte (ai đó sửa tay/định dạng lại)
        json.dump(d, f, indent=4)
    truoc = _byte(may["pc2"]["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="Trust store đã đổi"):
        _ghi_danh(may, raw)
    assert _byte(may["pc2"]["tc"]) == truoc


def test_dung_lai_uy_quyen_sau_khi_da_ghi_danh_bi_tu_choi(may):
    raw = _uy_quyen(may)
    _ghi_danh(may, raw)
    sau = _byte(may["pc2"]["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="ĐÃ được tin"):
        _ghi_danh(may, raw)
    assert _byte(may["pc2"]["tc"]) == sau


@pytest.mark.parametrize("lech", [timedelta(days=31), timedelta(days=-2)])
def test_uy_quyen_het_han_hoac_tu_tuong_lai_bi_tu_choi(may, lech):
    raw = _uy_quyen(may)
    truoc = _byte(may["pc2"]["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="hạn|tương lai"):
        _ghi_danh(may, raw, bay_gio=BAY_GIO + lech)
    assert _byte(may["pc2"]["tc"]) == truoc


def test_han_uy_quyen_toi_da_90_ngay(may):
    with pytest.raises(uq.LoiUyQuyen):
        _uy_quyen(may, han_ngay=91)


def test_chu_may_khong_xac_nhan_thi_khong_doi_gi(may):
    truoc = _cay(may["pc2"]["goc"])
    with pytest.raises(uq.LoiUyQuyen, match="không xác nhận"):
        _ghi_danh(may, _uy_quyen(may), dong_y=False)
    assert _cay(may["pc2"]["goc"]) == truoc


def test_dang_cap_nhat_thi_khong_ghi_danh(may):
    from khoa import KhoaTienTrinh

    raw = _uy_quyen(may)
    truoc = _byte(may["pc2"]["tc"])
    with KhoaTienTrinh(os.path.join(may["pc2"]["goc"], "update_state", "updater.lock"), "updater khác"):
        with pytest.raises(uq.LoiUyQuyen, match="cập nhật đang chạy"):
            _ghi_danh(may, raw)
    assert _byte(may["pc2"]["tc"]) == truoc


def test_ban_dang_chay_khong_xac_minh_duoc_thi_dung_truoc_khi_doi(may):
    raw = _uy_quyen(may)
    cur = json.loads(_byte(os.path.join(may["pc2"]["goc"], "update_state", "current.json")))
    with open(os.path.join(cur["release"], "TimClipPro", "app.py"), "ab") as f:
        f.write(b"# sua tay\n")
    truoc = _byte(may["pc2"]["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="Bản đang chạy"):
        _ghi_danh(may, raw)
    assert _byte(may["pc2"]["tc"]) == truoc


def test_nhat_ky_cap_nhat_dang_do_thi_khong_ghi_danh(may):
    raw = _uy_quyen(may)
    p = os.path.join(may["pc2"]["goc"], "update_state", "journal.json")
    nk = json.loads(_byte(p))
    nk["trang_thai"] = mu.HEALTHCHECK
    mu.ghi_json_nguyen_tu(p, nk)
    with pytest.raises(uq.LoiUyQuyen, match="dở"):
        _ghi_danh(may, raw)


# ---------------------------------------------------------------------------
#  Mất điện / lỗi giữa chừng — trust store luôn là bản CŨ hoặc bản MỚI hợp lệ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("diem", ["truoc_sao_luu", "sau_sao_luu", "sau_ghi_tam", "sau_thay"])
def test_mat_dien_tung_diem_trust_store_cu_hoac_moi_hop_le_roi_chay_lai_xong(may, diem):
    raw = _uy_quyen(may)
    truoc = _byte(may["pc2"]["tc"])

    def dung(ten):
        if ten == diem:
            raise uq.MatDien(ten)
    with pytest.raises(uq.MatDien):
        _ghi_danh(may, raw, diem_dung=dung)
    tc = mu.doc_khoa_tin_cay(may["pc2"]["tc"])                       # đúng parser launcher: luôn đọc được
    if diem == "sau_thay":
        assert set(tc) == {may["k1"].key_id, may["id2"]}
        with pytest.raises(uq.LoiUyQuyen, match="ĐÃ được tin"):
            _ghi_danh(may, raw)                                         # chạy lại: báo đã xong, không đổi gì
        assert uq.xem(may["pc2"]["goc"])["ban_dang_chay_ky_boi"] == may["k1"].key_id
    else:
        assert _byte(may["pc2"]["tc"]) == truoc
        kq, _ = _ghi_danh(may, raw)                                     # chạy lại: xong, dọn file tạm sót
        assert kq["trang_thai"] == "DA_GHI_DANH"
    lc = os.path.join(may["pc2"]["goc"], "launcher")
    assert not [f for f in os.listdir(lc) if f.startswith(uq.TEN_TIN_CAY + ".tmp-")] or diem == "sau_thay"


def test_kiem_sau_ghi_loi_thi_tra_lai_trust_store_cu(may, monkeypatch):
    raw = _uy_quyen(may)
    truoc = _byte(may["pc2"]["tc"])
    goc = uq._kiem_sau_ghi

    def hong(*a, **k):
        goc(*a, **k)
        raise uq.LoiUyQuyen("kiem_sau_ghi", "giả lập: parser launcher đọc ra khác mong đợi")
    monkeypatch.setattr(uq, "_kiem_sau_ghi", hong)
    with pytest.raises(uq.LoiUyQuyen, match="TRẢ LẠI"):
        _ghi_danh(may, raw)
    assert _byte(may["pc2"]["tc"]) == truoc


# ---------------------------------------------------------------------------
#  Hoàn tác (rollback có kiểm)
# ---------------------------------------------------------------------------

def test_hoan_tac_ve_ban_sao_luu(may):
    truoc = _byte(may["pc2"]["tc"])
    kq, _ = _ghi_danh(may, _uy_quyen(may))
    hoi = []
    kq2 = uq.hoan_tac(may["pc2"]["goc"], kq["sao_luu"], xac_nhan=lambda t: hoi.append(t) or True)
    assert kq2["trang_thai"] == "DA_HOAN_TAC" and hoi[0]["go_bo"] == [may["id2"]]
    assert set(mu.doc_khoa_tin_cay(may["pc2"]["tc"])) == {may["k1"].key_id}
    sau = json.loads(_byte(may["pc2"]["tc"]))
    assert sau["khoa"] == json.loads(truoc)["khoa"]                    # mục khoá PC1 giữ nguyên
    assert [x["key_id"] for x in sau["thu_hoi"]] == [may["id2"]]       # khoá gỡ ghi vào danh sách thu hồi


def test_hoan_tac_bi_chan_khi_ban_dang_chay_do_khoa_se_go_ky(may):
    pc2 = may["pc2"]
    kq, _ = _ghi_danh(may, _uy_quyen(may))
    phat_hanh(pc2["nguon"], "1.1.2", None, ky_bang=_KyBang(may["k2"]))
    assert pc2["main"]("update", "prepare") == 0 and pc2["main"]("update", "apply") == 0
    sau = _byte(pc2["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="khoá sắp gỡ"):
        uq.hoan_tac(pc2["goc"], kq["sao_luu"], xac_nhan=lambda t: True)
    assert _byte(pc2["tc"]) == sau


def test_hoan_tac_tu_choi_file_khong_phai_ban_truoc(may):
    _ghi_danh(may, _uy_quyen(may))
    la = may["k3"].ghi_tin_cay(str(may["tmp"] / "la" / "trusted_keys.json"))
    sau = _byte(may["pc2"]["tc"])
    with pytest.raises(uq.LoiUyQuyen):
        uq.hoan_tac(may["pc2"]["goc"], la, xac_nhan=lambda t: True)
    assert _byte(may["pc2"]["tc"]) == sau


# ---------------------------------------------------------------------------
#  Nạp đúng launcher ĐÃ CÀI; không __pycache__; cây release không đổi
# ---------------------------------------------------------------------------

def test_nap_launcher_dung_module_cua_cai_dat_khong_lan_module_repo(may):
    lc = os.path.join(may["pc2"]["goc"], "launcher")
    L = uq.nap_launcher(may["pc2"]["goc"])
    for m in (L.mu, L.rp, L.khoa):
        assert os.path.normcase(os.path.dirname(os.path.realpath(m.__file__))) == os.path.normcase(os.path.realpath(lc))
    assert sys.modules["managed_update"] is mu                       # module của repo được trả lại
    assert not os.path.exists(os.path.join(lc, "__pycache__"))


def test_cli_chay_rieng_khong_sinh_pycache_khong_doi_cay_release(may, tmp_path):
    pc2 = may["pc2"]
    raw = _uy_quyen(may)
    p_uq = str(tmp_path / "uy_quyen.json")
    with open(p_uq, "wb") as f:
        f.write(raw)
    truoc = _cay(pc2["goc"])
    cong_cu = os.path.join(MA, "uy_quyen_khoa.py")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    for doi_so in (["xem", "--goc", pc2["goc"]], ["ghi-danh", "--goc", pc2["goc"], "--uy-quyen", p_uq, "--khoa-cong-khai", may["pub2"]]):
        r = subprocess.run([sys.executable, "-I", cong_cu, *doi_so], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, env=env, timeout=120)
        if doi_so[0] == "xem":
            assert r.returncode == 0, r.stderr
            assert may["k1"].key_id in r.stdout and "1.1.1" in r.stdout
        else:
            assert r.returncode == 2 and "cửa sổ" in (r.stdout + r.stderr)   # không TTY → không ghi danh
    assert _cay(pc2["goc"]) == truoc                                    # không __pycache__, không đổi file nào
    m = mu.doc_manifest(_byte(os.path.join(json.loads(_byte(os.path.join(
        pc2["goc"], "update_state", "current.json")))["release"], mu.TEN_MANIFEST)))
    mu.kiem_cay_release(json.loads(_byte(os.path.join(pc2["goc"], "update_state", "current.json")))["release"], m)


def test_ghi_danh_chi_doi_trust_store_va_them_sao_luu(may):
    pc2 = may["pc2"]
    truoc = _cay(pc2["goc"])
    state_truoc = _cay(pc2["state"])
    kq, _ = _ghi_danh(may, _uy_quyen(may))
    sau = _cay(pc2["goc"])
    doi = {k for k in set(truoc) | set(sau) if truoc.get(k) != sau.get(k)}
    them = {k for k in doi if k.startswith(f"launcher/{uq.THU_MUC_SAO_LUU}/")}
    assert doi - them == {"launcher/trusted_keys.json"}
    assert len(them) == 2                                   # bản sao trust store cũ + bản uỷ quyền đã dùng
    assert {k for k in sau if "__pycache__" in k} == {k for k in truoc if "__pycache__" in k}
    assert _cay(pc2["state"]) == state_truoc                # state root (lịch sử, outbox, kho) không đụng


def test_launcher_ban_bootstrap_e49340d_doc_va_kiem_duoc_trust_store_sau_ghi_danh(tmp_path):
    """PC2 chạy launcher của bộ bootstrap 1.0.0 (commit e49340d) — công cụ phải dùng đúng API của bản đó."""
    try:
        blob = {f: subprocess.run(["git", "-C", REPO, "-c", "core.autocrlf=false", "show", f"{E49}:TimClipPro/{f}"],
                                  capture_output=True, check=True).stdout for f in FILE_LAUNCHER}
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("cần repo git có commit e49340d")
    k1 = KhoaThu()
    k2 = Ed25519PrivateKey.generate()
    cai = _dung_cai_dat(tmp_path, "e49", k1, launcher_tu=blob)
    L = uq.nap_launcher(cai["goc"])
    raw_yc = uq.tao_yeu_cau(k2, ten_may="PC2", cai_dat=uq.doc_cai_dat(cai["goc"], L), bay_gio=BAY_GIO)
    raw = uq.tao_uy_quyen(raw_yc, k1.rieng, khoa_tin_cay=mu.doc_khoa_tin_cay(cai["tc"]), bay_gio=BAY_GIO)
    kq = uq.ghi_danh(cai["goc"], raw, khoa_cong_khai=_ghi_khoa_cong_khai(tmp_path / "e49" / "khoa", k2),
                     xac_nhan=lambda t: True, bay_gio=BAY_GIO)
    assert kq["trang_thai"] == "DA_GHI_DANH"
    assert set(L.mu.doc_khoa_tin_cay(cai["tc"])) == {k1.key_id, uq.tao_key_id(_raw(k2))}


def test_xem_bao_cao_trust_store_va_ban_dang_chay(may):
    x = uq.xem(may["pc2"]["goc"])
    assert x["khoa"] == [may["k1"].key_id] and x["ban_dang_chay"] == "1.1.1"
    assert x["ban_dang_chay_ky_boi"] == may["k1"].key_id
    assert x["trust_store_sha256"] == hashlib.sha256(_byte(may["pc2"]["tc"])).hexdigest()


# ---------------------------------------------------------------------------
#  release_tool: tạo khoá phát hành (PC2) + ký / kiểm uỷ quyền (PC1)
# ---------------------------------------------------------------------------

def test_tao_khoa_phat_hanh_ma_hoa_tu_kiem_va_khoa_cong_khai_doc_duoc(tmp_path):
    mk = MK_THU
    kq = rt.tao_khoa_phat_hanh(str(tmp_path / "khoa"), mat_khau=mk, ten_may="PC2")
    assert all(kq["tu_kiem"].values()) and kq["tu_kiem"]
    pem = _byte(kq["khoa_rieng"])
    assert pem.startswith(b"-----BEGIN ENCRYPTED ")
    k = serialization.load_pem_private_key(pem, password=mk)
    assert uq.tao_key_id(_raw(k)) == kq["key_id"]
    assert list(mu.doc_khoa_tin_cay(kq["khoa_cong_khai"])) == [kq["key_id"]]
    assert b"PRIVATE" not in _byte(kq["khoa_cong_khai"])
    with pytest.raises(rt.LoiPhatHanh, match="đã có"):
        rt.tao_khoa_phat_hanh(str(tmp_path / "khoa"), mat_khau=mk, ten_may="PC2")   # không ghi đè khoá cũ


def test_tao_khoa_tu_choi_thu_muc_dong_bo_va_ban_clone_git(tmp_path, monkeypatch):
    monkeypatch.setenv("OneDrive", str(tmp_path / "od"))
    with pytest.raises(rt.LoiPhatHanh, match="OneDrive"):
        rt.tao_khoa_phat_hanh(str(tmp_path / "od" / "khoa"), mat_khau=MK_THU, ten_may="PC2")
    os.makedirs(tmp_path / "clone" / ".git")
    with pytest.raises(rt.LoiPhatHanh, match="git"):
        rt.tao_khoa_phat_hanh(str(tmp_path / "clone" / "khoa"), mat_khau=MK_THU, ten_may="PC2")


@pytest.mark.parametrize("mk,dat", [("ngan", False), ("mat khau có dấu rất dài", False), ("aaaaaaaaaaaaaaaaaaaa", False),
                                    ("Dai-Du-16-Ky-Tu!x", True)])
def test_chinh_sach_mat_khau(mk, dat):
    assert (rt.ly_do_mat_khau_yeu(mk) == "") is dat


def test_ky_va_kiem_uy_quyen_tu_file_khoa_ma_hoa(may, tmp_path):
    """Đúng đường PC1: khoá riêng PEM mã hoá + file khoá công khai đang tin → uỷ quyền → PC2 ghi danh được."""
    k1 = may["k1"]
    pem = k1.rieng.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                 serialization.BestAvailableEncryption(MK_PC1_THU))
    p_pem = tmp_path / "khoa_rieng.pem"
    p_pem.write_bytes(pem)
    raw_yc = _yeu_cau(may)
    raw = rt.ky_uy_quyen(raw_yc, str(p_pem), may["pc2"]["tc"], mat_khau=MK_PC1_THU, bay_gio=BAY_GIO)
    tom_tat = rt.kiem_uy_quyen(raw, may["pc2"]["tc"], raw_yeu_cau=raw_yc, bay_gio=BAY_GIO)
    assert tom_tat["khoa_moi"] == may["id2"] and tom_tat["ky_boi"] == k1.key_id
    with pytest.raises(rt.LoiPhatHanh, match="mật khẩu"):
        rt.ky_uy_quyen(raw_yc, str(p_pem), may["pc2"]["tc"], mat_khau=b"sai", bay_gio=BAY_GIO)
    kq, _ = _ghi_danh(may, raw)
    assert kq["trang_thai"] == "DA_GHI_DANH"


@pytest.mark.parametrize("go", ["sai_mot_ky_tu", "thieu_mot_ky_tu", "dung", "dung_hoa_co_cach"])
def test_cli_ky_uy_quyen_phai_go_dung_key_id_moi_hoi_mat_khau(may, tmp_path, monkeypatch, capsys, go):
    """Review PC2 15/10 (P3-1, đột biến M17 sống sót): đường CLI ``ky-uy-quyen`` mà PC1 chạy thật. key_id KHÔNG hiện
    trước khi gõ; chủ máy gõ theo tin nhắn của máy kia — phải trùng ĐỦ 16 ký tự key_id khoá mới trong yêu cầu. Sai → không
    hỏi mật khẩu, không ký, không tạo file. (Console giả lập bằng monkeypatch; đường console thật: test không-console.)"""
    pem = may["k1"].rieng.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.BestAvailableEncryption(MK_PC1_THU))
    p_pem, p_yc, p_ra = tmp_path / "khoa_rieng.pem", tmp_path / "yeu_cau.json", tmp_path / "uy_quyen.json"
    p_pem.write_bytes(pem)
    L = uq.nap_launcher(may["pc2"]["goc"])
    p_yc.write_bytes(uq.tao_yeu_cau(may["k2"], ten_may="PC2", cai_dat=uq.doc_cai_dat(may["pc2"]["goc"], L)))
    kid = may["id2"]
    go_vao = {"sai_mot_ky_tu": kid[:15] + ("0" if kid[15] != "0" else "1"), "thieu_mot_ky_tu": kid[:15],
              "dung": kid, "dung_hoa_co_cach": "  " + kid.upper() + " "}[go]
    da_go, hoi_mk = [], []
    monkeypatch.setattr(rt, "_co_console", lambda: True)
    monkeypatch.setattr("builtins.input", lambda dong="": da_go.append(dong) or go_vao)
    monkeypatch.setattr("getpass.getpass", lambda dong="": hoi_mk.append(dong) or MK_PC1_THU.decode())
    rc = rt.main(["ky-uy-quyen", "--yeu-cau", str(p_yc), "--khoa", str(p_pem), "--tin-cay", may["pc2"]["tc"],
                  "--ra", str(p_ra)])
    ra = capsys.readouterr()
    assert len(da_go) == 1 and kid not in ra.out.split("khớp:")[0]          # key_id không hiện sẵn trước khi gõ
    if go.startswith("dung"):
        assert rc == 0 and len(hoi_mk) == 1 and p_ra.exists()
        t = rt.kiem_uy_quyen(p_ra.read_bytes(), may["pc2"]["tc"], raw_yeu_cau=p_yc.read_bytes())
        assert t["khoa_moi"] == kid and t["ky_boi"] == may["k1"].key_id
    else:
        assert rc == 1 and hoi_mk == [] and not p_ra.exists() and "KHÔNG khớp" in ra.err
        assert sorted(os.listdir(tmp_path)) == sorted(["pc2", "khoa_rieng.pem", "yeu_cau.json"])


def test_kiem_uy_quyen_bao_khong_khop_yeu_cau(may):
    raw_yc = _yeu_cau(may)
    raw_khac = _yeu_cau(may, khoa=may["k3"].rieng)
    raw = _uy_quyen(may, raw_yc)
    with pytest.raises(rt.LoiPhatHanh, match="không khớp"):
        rt.kiem_uy_quyen(raw, may["pc2"]["tc"], raw_yeu_cau=raw_khac, bay_gio=BAY_GIO)


def test_chu_ky_uy_quyen_khong_dung_duoc_lam_chu_ky_manifest(may):
    """Miền ký tách biệt: chữ ký uỷ quyền không bao giờ hợp lệ cho chính các byte nội dung (như một manifest)."""
    d = json.loads(_uy_quyen(may))
    sig = json.dumps(d["chu_ky"]).encode()
    with pytest.raises(mu.TuChoiGoi):
        mu.kiem_chu_ky(uq.chuan_hoa(d["noi_dung"]), sig, may["tin_cay_k1"])


@pytest.mark.parametrize("dau_vao", ["nul", "ong_dan"])
@pytest.mark.parametrize("lenh", ["tao-khoa", "ky-uy-quyen", "ghi-danh", "hoan-tac", "yeu-cau"])
def test_lenh_can_nguoi_go_tu_choi_khi_khong_co_console(may, tmp_path, dau_vao, lenh):
    """Tiến trình tự động (stdin là NUL — Windows coi là «tty» — hoặc ống dẫn) không bao giờ tạo khoá, ký hay đổi
    trust store: cần cửa sổ console thật, mật khẩu/xác nhận do người gõ."""
    pc2 = may["pc2"]
    gia = str(tmp_path / "khong_co.json")
    doi_so = {"tao-khoa": ["release_tool.py", "tao-khoa", "--thu-muc", str(tmp_path / "khoa"), "--ten-may", "PC2"],
              "ky-uy-quyen": ["release_tool.py", "ky-uy-quyen", "--yeu-cau", gia, "--khoa", gia, "--tin-cay", pc2["tc"],
                              "--ra", str(tmp_path / "uq.json")],
              "ghi-danh": ["uy_quyen_khoa.py", "ghi-danh", "--goc", pc2["goc"], "--uy-quyen", gia, "--khoa-cong-khai", gia],
              "hoan-tac": ["uy_quyen_khoa.py", "hoan-tac", "--goc", pc2["goc"], "--sao-luu", gia],
              "yeu-cau": ["uy_quyen_khoa.py", "yeu-cau", "--goc", pc2["goc"], "--khoa-rieng", gia, "--ten-may", "PC2",
                          "--ra", str(tmp_path / "yc.json")]}[lenh]
    co = ["-E", "-s", "-B"] if doi_so[0] == "release_tool.py" else ["-I"]
    truoc = _cay(pc2["goc"])
    kw = {"stdin": subprocess.DEVNULL} if dau_vao == "nul" else {"input": "DONG Y\n" * 5}
    r = subprocess.run([sys.executable, *co, os.path.join(MA, doi_so[0]), *doi_so[1:]], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(tmp_path), **kw)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "console" in r.stderr
    assert _cay(pc2["goc"]) == truoc and sorted(os.listdir(tmp_path)) == ["pc2"]      # không khoá, không file ra


def test_them_khoa_danh_sach_repo_chi_theo_uy_quyen_hop_le(may, tmp_path):
    """``release/trusted_keys.json`` của repo chỉ thêm khoá qua uỷ quyền đã ký bởi khoá trong CHÍNH danh sách đó."""
    ds, ds_gia = tmp_path / "trusted_keys.json", tmp_path / "gia.json"
    for p in (ds, ds_gia):
        p.write_bytes(_byte(may["pc2"]["tc"]))
    muc_cu = json.loads(ds.read_text(encoding="utf-8"))["khoa"][0]
    raw = _uy_quyen(may)
    kq = rt.them_khoa_danh_sach(raw, str(ds))
    assert kq["khoa"] == sorted([may["k1"].key_id, may["id2"]]) and kq["them"] == may["id2"]
    assert json.loads(ds.read_text(encoding="utf-8"))["khoa"][0] == muc_cu
    assert set(mu.doc_khoa_tin_cay(str(ds))) == {may["k1"].key_id, may["id2"]}
    with pytest.raises(rt.LoiPhatHanh, match="đã có"):
        rt.them_khoa_danh_sach(raw, str(ds))
    gia = _ky_lai(_sua_noi_dung(raw, ky_boi=may["k3"].key_id), may["k3"].rieng)
    with pytest.raises(rt.LoiPhatHanh):
        rt.them_khoa_danh_sach(gia, str(ds_gia))
    assert ds_gia.read_bytes() == _byte(may["pc2"]["tc"])


@pytest.mark.parametrize("truong", ["cai_dat_sha256", "trust_store_sha256", "ten_may"])
def test_yeu_cau_bi_sua_noi_dung_sau_khi_tu_ky_bi_tu_choi(may, truong):
    d = json.loads(_yeu_cau(may))
    d["noi_dung"][truong] = "PC9" if truong == "ten_may" else "0" * 64
    with pytest.raises(uq.LoiUyQuyen, match="KHÔNG hợp lệ"):
        uq.doc_yeu_cau(json.dumps(d).encode())


@pytest.mark.parametrize("loi", ["mat_khoa_cu", "nham_khoa_moi"])
def test_noi_dung_ghi_sai_bi_kiem_sau_ghi_bat_va_tra_lai(may, monkeypatch, loi):
    """Lưới an toàn: bản ghi mới sai (lỗi lập trình) — thiếu khoá cũ, hoặc ghi NHẦM khoá khác thay khoá được uỷ quyền
    (bản đang chạy vẫn xác minh được, chỉ phép so tập khoá bắt) — đọc lại bằng parser của launcher phải bắt và trả lại."""
    raw = _uy_quyen(may)
    truoc = _byte(may["pc2"]["tc"])

    def sai(byte_cu, nd, luc):
        d = json.loads(byte_cu)
        if loi == "mat_khoa_cu":
            d["khoa"] = [{"key_id": nd["khoa_moi"]["key_id"], "ed25519_pub_b64": nd["khoa_moi"]["ed25519_pub_b64"]}]
        else:
            d["khoa"].append({"key_id": may["k3"].key_id, "ed25519_pub_b64": _b64(may["k3"].raw)})
        return json.dumps(d).encode()
    monkeypatch.setattr(uq, "_trust_store_moi", sai)
    with pytest.raises(uq.LoiUyQuyen, match="TRẢ LẠI"):
        _ghi_danh(may, raw)
    assert _byte(may["pc2"]["tc"]) == truoc


def test_them_khoa_danh_sach_tu_choi_danh_sach_thieu_khoa_may_dich_dang_tin(may, tmp_path):
    k1, kx = may["k1"], KhoaThu()
    hai = json.dumps({"khoa": [{"key_id": k.key_id, "ed25519_pub_b64": _b64(k.raw)} for k in (k1, kx)]}).encode()
    may_b = _dung_cai_dat(may["tmp"], "may_hai_khoa", k1, trust_bytes=hai)
    raw = _uy_quyen(may, _yeu_cau(may, cai=may_b), tin_cay=mu.doc_khoa_tin_cay(may_b["tc"]))
    chi_k1 = tmp_path / "chi_k1.json"
    chi_k1.write_bytes(_byte(may["pc2"]["tc"]))
    with pytest.raises(rt.LoiPhatHanh, match="thiếu khoá"):
        rt.them_khoa_danh_sach(raw, str(chi_k1))
    assert chi_k1.read_bytes() == _byte(may["pc2"]["tc"])


def test_cay_release_thua_pycache_xem_bao_ro_ghi_danh_tu_choi(may):
    """Lỗi từng gặp: công cụ chẩn đoán chạy không -B sinh ``__pycache__`` trong cây release ĐÃ KÝ → cây «thừa file».
    ``xem`` báo rõ (không dừng giữa chừng); ghi danh từ chối tới khi cài đặt lành (người dùng dọn ``__pycache__``)."""
    cur = json.loads(_byte(os.path.join(may["pc2"]["goc"], "update_state", "current.json")))
    rac = os.path.join(cur["release"], "TimClipPro", "__pycache__")
    os.makedirs(rac)
    with open(os.path.join(rac, "app.cpython-312.pyc"), "wb") as f:
        f.write(b"\x00" * 16)
    x = uq.xem(may["pc2"]["goc"])
    assert x["khoa"] == [may["k1"].key_id] and x["ban_dang_chay"] == "" and "thừa" in x["loi_ban_dang_chay"]
    truoc = _byte(may["pc2"]["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="Bản đang chạy"):
        _ghi_danh(may, _uy_quyen(may, _yeu_cau_bo_kiem_ban(may)))
    assert _byte(may["pc2"]["tc"]) == truoc
    shutil.rmtree(rac)
    assert uq.xem(may["pc2"]["goc"])["loi_ban_dang_chay"] == ""


def _yeu_cau_bo_kiem_ban(may):
    L = uq.nap_launcher(may["pc2"]["goc"])
    tt = uq.doc_cai_dat(may["pc2"]["goc"], L, kiem_ban=False)
    return uq.tao_yeu_cau(may["k2"], ten_may="PC2", cai_dat=tt, bay_gio=BAY_GIO)


# ---------------------------------------------------------------------------
#  Review độc lập lượt 1 (14/10): P1-1, P2-1, P2-2, P3 khoá bậc nhỏ, nhật ký hỏng
# ---------------------------------------------------------------------------

def test_uy_quyen_hop_le_cho_khoa_KHONG_phai_cua_may_nay_bi_tu_choi(may):
    """P1-1: kẻ tráo yêu cầu trên đường đi (PR) bằng khoá của mình (mài trùng vài ký tự key_id) — PC1 ký thật — máy đích
    vẫn từ chối vì khoá được uỷ quyền KHÁC đúng 32 byte khoá công khai do tao-khoa để lại trên CHÍNH máy này."""
    raw = _uy_quyen(may, _yeu_cau(may, khoa=may["k3"].rieng))       # yêu cầu tự ký hợp lệ, nhưng của khoá k3
    truoc = _cay(may["pc2"]["goc"])
    with pytest.raises(uq.LoiUyQuyen, match="KHÔNG khớp khoá công khai của máy này"):
        _ghi_danh(may, raw)
    assert _cay(may["pc2"]["goc"]) == truoc


def test_khoa_cong_khai_cua_may_phai_dung_mot_khoa_hop_le(may, tmp_path):
    hai = tmp_path / "hai.json"
    hai.write_text(json.dumps({"khoa": [{"key_id": k.key_id, "ed25519_pub_b64": _b64(k.raw)}
                                        for k in (may["k1"], may["k3"])]}), encoding="utf-8")
    for p in (str(hai), str(tmp_path / "khong_co.json")):
        with pytest.raises(uq.LoiUyQuyen, match="khoá công khai của máy"):
            _ghi_danh(may, _uy_quyen(may), khoa_cong_khai=p)


def test_hoan_tac_xong_khong_dung_lai_duoc_uy_quyen_va_khoa_bi_thu_hoi(may):
    """P2-1: sau hoàn tác, uỷ quyền cũ (còn hạn) không dùng lại được; uỷ quyền MỚI cho khoá đã thu hồi cũng bị từ chối."""
    raw = _uy_quyen(may)
    kq, _ = _ghi_danh(may, raw)
    uq.hoan_tac(may["pc2"]["goc"], kq["sao_luu"], xac_nhan=lambda t: True)
    sau = _byte(may["pc2"]["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="THU HỒI"):
        _ghi_danh(may, raw)
    moi = _uy_quyen(may, _yeu_cau(may))                               # yêu cầu mới trên trust store hiện tại
    with pytest.raises(uq.LoiUyQuyen, match="THU HỒI"):
        _ghi_danh(may, moi)
    assert _byte(may["pc2"]["tc"]) == sau


def test_hoan_tac_chi_nhan_ban_sao_luu_cua_cong_cu_va_khong_go_khoa_goc(may):
    """P2-2: file tập con bất kỳ (vd. khoa_cong_khai của PC2) không dùng để hoàn tác được; không bao giờ gỡ khoá gốc của
    bộ kit (mục không có bản ghi «ghi_danh»)."""
    kq, _ = _ghi_danh(may, _uy_quyen(may))
    sau = _byte(may["pc2"]["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="trust_backups"):
        uq.hoan_tac(may["pc2"]["goc"], may["pub2"], xac_nhan=lambda t: True)
    ngoai = os.path.join(may["tmp"], "pc2", "trusted_keys_ban_cu.json")    # đúng mẫu tên nhưng NGOÀI trust_backups
    shutil.copyfile(kq["sao_luu"], ngoai)
    with pytest.raises(uq.LoiUyQuyen, match="trust_backups"):
        uq.hoan_tac(may["pc2"]["goc"], ngoai, xac_nhan=lambda t: True)
    gia = os.path.join(os.path.dirname(kq["sao_luu"]), "trusted_keys_gia_chi_khoa_pc2.json")
    shutil.copyfile(may["pub2"], gia)
    with pytest.raises(uq.LoiUyQuyen, match="khoá gốc"):
        uq.hoan_tac(may["pc2"]["goc"], gia, xac_nhan=lambda t: True)
    assert _byte(may["pc2"]["tc"]) == sau


# Mã hoá các điểm bậc nhỏ (torsion) của Ed25519 — danh sách chặn của libsodium (ge25519_has_small_order).
DIEM_BAC_NHO = ["0000000000000000000000000000000000000000000000000000000000000000",
                "0100000000000000000000000000000000000000000000000000000000000000",
                "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
                "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
                "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f"]


@pytest.mark.parametrize("hex_diem", DIEM_BAC_NHO)
def test_khoa_bac_nho_bi_tu_choi(hex_diem):
    """P3: khoá công khai bậc nhỏ «xác minh» mọi chữ ký R=điểm đơn vị, S=0 — không bao giờ được vào trust store."""
    raw = bytes.fromhex(hex_diem)
    assert uq.la_khoa_yeu(raw)
    with pytest.raises(uq.LoiUyQuyen, match="yếu"):
        uq.doc_khoa_cong_khai({"key_id": uq.tao_key_id(raw), "ed25519_pub_b64": _b64(raw)})


def test_khoa_that_va_diem_co_so_khong_bi_coi_la_yeu():
    co_so = bytes.fromhex("5866666666666666666666666666666666666666666666666666666666666666")
    assert not uq.la_khoa_yeu(co_so)
    assert uq._giai_ma_diem(co_so)[0] == \
        15112221349535400772501151409588531511454012693041857206046113283949847762202      # x của điểm cơ sở B
    for _ in range(50):
        assert not uq.la_khoa_yeu(_raw(Ed25519PrivateKey.generate()))


def test_nhat_ky_cap_nhat_hong_thi_khong_ghi_danh(may):
    """Review P3: nhật ký cập nhật HỎNG = cần kiểm tay (như bộ cập nhật) — không coi là rảnh."""
    raw = _uy_quyen(may)
    with open(os.path.join(may["pc2"]["goc"], "update_state", "journal.json"), "w", encoding="utf-8") as f:
        f.write("{hong")
    truoc = _byte(may["pc2"]["tc"])
    with pytest.raises(uq.LoiUyQuyen, match="hỏng"):
        _ghi_danh(may, raw)
    assert _byte(may["pc2"]["tc"]) == truoc


# ---------------------------------------------------------------------------
#  Review độc lập lượt 2 (P3)
# ---------------------------------------------------------------------------

def test_khoa_cong_khai_cua_may_trong_repo_hoac_khong_canh_khoa_rieng_bi_tu_choi(may, tmp_path):
    """Kẻ tráo yêu cầu có thể gửi kèm file khoá công khai CỦA HẮN trong repo — file của máy phải nằm ngoài mọi bản clone
    git và cạnh khoá riêng cùng key_id (thư mục khoá do tao-khoa tạo)."""
    k3 = may["k3"].rieng
    raw = _uy_quyen(may, _yeu_cau(may, khoa=k3))
    clone = tmp_path / "clone"
    os.makedirs(clone / ".git")
    trong_repo = _ghi_khoa_cong_khai(clone / "release" / "trust", k3)
    with pytest.raises(uq.LoiUyQuyen, match="NGOÀI repo"):
        _ghi_danh(may, raw, khoa_cong_khai=trong_repo)
    le = tmp_path / "le"
    p = _ghi_khoa_cong_khai(le, k3)
    os.remove(os.path.join(str(le), f"khoa_rieng_phat_hanh_{uq.tao_key_id(_raw(k3))}.pem"))
    with pytest.raises(uq.LoiUyQuyen, match="khoá riêng"):
        _ghi_danh(may, raw, khoa_cong_khai=p)
    assert set(mu.doc_khoa_tin_cay(may["pc2"]["tc"])) == {may["k1"].key_id}


def test_hoan_tac_tu_choi_hard_link_trong_trust_backups(may, tmp_path):
    kq, _ = _ghi_danh(may, _uy_quyen(may))
    ngoai = tmp_path / "ngoai.json"
    shutil.copyfile(kq["sao_luu"], ngoai)
    lien_ket = os.path.join(os.path.dirname(kq["sao_luu"]), "trusted_keys_lien_ket.json")
    os.link(str(ngoai), lien_ket)
    with pytest.raises(uq.LoiUyQuyen, match="liên kết"):
        uq.hoan_tac(may["pc2"]["goc"], lien_ket, xac_nhan=lambda t: True)


def test_go_khoa_khoi_danh_sach_repo(may, tmp_path):
    """Khoá bị lộ phải rời CẢ danh sách khoá công khai của repo (verify, kiem-sau-ky, feed, kit dùng danh sách đó)."""
    ds = tmp_path / "trusted_keys.json"
    ds.write_bytes(_byte(may["pc2"]["tc"]))
    rt.them_khoa_danh_sach(_uy_quyen(may), str(ds))
    muc_k1 = json.loads(ds.read_text(encoding="utf-8"))["khoa"][0]
    kq = rt.go_khoa_danh_sach(may["id2"], str(ds))
    assert kq["khoa"] == [may["k1"].key_id] and kq["go"] == may["id2"]
    d = json.loads(ds.read_text(encoding="utf-8"))
    assert d["khoa"] == [muc_k1] and [x["key_id"] for x in d["thu_hoi"]] == [may["id2"]]
    with pytest.raises(rt.LoiPhatHanh, match="không có"):
        rt.go_khoa_danh_sach(may["id2"], str(ds))
    with pytest.raises(rt.LoiPhatHanh, match="cuối cùng"):
        rt.go_khoa_danh_sach(may["k1"].key_id, str(ds))
    with pytest.raises(rt.LoiPhatHanh, match="thu hồi"):
        rt.them_khoa_danh_sach(_uy_quyen(may), str(ds))       # khoá đã gỡ không thêm lại được qua danh sách repo
    assert [p.name for p in tmp_path.iterdir() if ".tmp-" in p.name] == []
