# -*- coding: utf-8 -*-
"""Rà soát đối nghịch M3+M4 — bộ cập nhật (managed_update). Mỗi test tái hiện MỘT phát hiện và đã ĐỎ trên
mã trước khi sửa:

* A  — quay lại phải về con trỏ TRƯỚC kích hoạt (``con_tro_cu``), không về ``last_good`` khi nó đã (sai) trỏ
       sang chính bản mới; ghi ACTIVE trước last_good.
* B  — lỗi lạ (timeout, subprocess, OSError) từ health/runtime/migration không được thoát khỏi updater; lỗi
       tất định (lock chưa băm, migration lỗi, runtime lỗi lặp lại) → cách ly, không vòng lặp tải lại.
* D  — máy mới (chưa có lịch sử) không phải migration; cần duyệt migration thì báo NGAY lúc chuẩn bị.
* P3 — hoãn bấm trong lúc chờ rảnh; chữ ký sai/thiếu gói không cách ly vĩnh viễn + bỏ cách ly; ghi JSON chịu
       được người đọc đồng thời (Windows); không bao giờ xoá runtime đang dùng.
"""
import os
import shutil
import subprocess
import zipfile

import pytest

import maintenance_gate as mg
import managed_update as mu
from cap_nhat_gia import KhoaThu, MoiTruongGia, phat_hanh


@pytest.fixture()
def mt(tmp_path):
    khoa = KhoaThu()
    goc = str(tmp_path / "cai dat có dấu")
    state = str(tmp_path / "state")
    nguon = str(tmp_path / "nguon")
    os.makedirs(nguon)
    cd = mu.CaiDat(goc=goc, state_root=state)
    gia = MoiTruongGia(state)
    tin_cay = mu.doc_khoa_tin_cay(khoa.ghi_tin_cay(os.path.join(goc, "launcher", "trusted_keys.json")))

    def tao(**sua):
        tham = dict(nguon=mu.NguonThuMuc(nguon), khoa_tin_cay=tin_cay,
                    cong=mg.CongBaoTri(cd.data_dir), tao_moi_truong=gia.tao_moi_truong,
                    kiem_suc_khoe=gia.kiem_suc_khoe, di_chuyen=gia.di_chuyen, sao_luu=gia.sao_luu,
                    phien_ban_db=gia.phien_ban_db, han_cho_ranh_s=0.3, chu_ky_cho_s=0.05)
        tham.update(sua)
        return mu.CapNhat(cd, **tham)

    return {"khoa": khoa, "cd": cd, "nguon": nguon, "gia": gia, "tao": tao, "tmp": tmp_path}


def _cai(mt, phien_ban="1.0.0", **kw):
    phat_hanh(mt["nguon"], phien_ban, mt["khoa"], **kw)
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.STAGED
    kq = cn.ap_dung()
    assert kq.trang_thai == mu.ACTIVE, kq
    return cn


def _hien(mt):
    d = mu.doc_json(mt["cd"].file_trang_thai("current.json"))
    return d and d["phien_ban"]


def _so(mt, ten):
    return len([g for g in mt["gia"].goi if g[0] == ten])


RUNTIME_MOI = dict(runtime={"runtime_id": "py312-moi", "lock_sha256": "d" * 64})


# ---------------------------------------------------------------- A: quay lại đúng bản trước

def _chet_sau_last_good_moi(monkeypatch, phien_ban):
    ghi_goc = mu.ghi_json_nguyen_tu

    def ghi(path, obj):
        ghi_goc(path, obj)
        if path.endswith("last_good.json") and isinstance(obj, dict) and obj.get("phien_ban") == phien_ban:
            raise mu.MatDien("ngay sau khi ghi last_good")

    monkeypatch.setattr(mu, "ghi_json_nguyen_tu", ghi)
    return ghi_goc


def test_chet_ngay_sau_last_good_roi_health_hong_khong_chay_ban_da_cach_ly(mt, monkeypatch):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    ghi_goc = _chet_sau_last_good_moi(monkeypatch, "1.1.0")
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.STAGED
    with pytest.raises(mu.MatDien):
        cn.ap_dung()
    monkeypatch.setattr(mu, "ghi_json_nguyen_tu", ghi_goc)
    mt["gia"].suc_khoe["kich_hoat"] = False              # lần kiểm lại sau mất điện hỏng
    cn2 = mt["tao"]()
    cn2.phuc_hoi()
    cl = cn2.cach_ly()
    assert not ("1.1.0" in cl and _hien(mt) == "1.1.0"), "đang chạy chính bản đã bị cách ly"
    assert (cn2.last_good() or {}).get("phien_ban") not in cl


def _trang_thai_last_good_sai(mt, diem):
    """Mất điện ở ``diem`` (sau đổi con trỏ) rồi last_good bị (sai) trỏ sang ứng viên — trạng thái mà thứ
    tự ghi cũ (last_good trước ACTIVE) để lại khi ghi nhật ký lỗi."""
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])

    def chet(ten):
        if ten == diem:
            raise mu.MatDien(ten)

    cn = mt["tao"](diem_dung=chet)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    with pytest.raises(mu.MatDien):
        cn.ap_dung()
    assert _hien(mt) == "1.1.0"
    mu.ghi_json_nguyen_tu(mt["cd"].file_trang_thai("last_good.json"),
                          mu.doc_json(mt["cd"].file_trang_thai("current.json")))


def test_khoi_phuc_health_hong_quay_ve_con_tro_cu_khi_last_good_da_tro_ban_moi(mt):
    _trang_thai_last_good_sai(mt, mu.HEALTHCHECK)
    mt["gia"].suc_khoe["kich_hoat"] = False
    cn2 = mt["tao"]()
    cn2.phuc_hoi()
    assert _hien(mt) == "1.0.0" and "1.1.0" in cn2.cach_ly()
    assert cn2.last_good()["phien_ban"] == "1.0.0"


def test_khoi_phuc_ung_vien_hong_quay_ve_con_tro_cu_khi_last_good_da_tro_ban_moi(mt):
    _trang_thai_last_good_sai(mt, "POINTER_SWITCHED")
    with open(os.path.join(mt["cd"].release_dir("1.1.0"), "TimClipPro", "app.py"), "a",
              encoding="utf-8") as f:
        f.write("# hỏng sau mất điện\n")
    cn2 = mt["tao"]()
    cn2.phuc_hoi()
    assert _hien(mt) == "1.0.0"
    assert cn2.last_good()["phien_ban"] == "1.0.0"


def test_chet_sau_active_truoc_last_good_thi_khoi_phuc_sua_last_good(mt, monkeypatch):
    """Thứ tự mới: ACTIVE rồi mới last_good — mất điện giữa hai bước thì khôi phục bù last_good."""
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    ghi_goc = mu.ghi_json_nguyen_tu

    def ghi(path, obj):
        ghi_goc(path, obj)
        if path.endswith("journal.json") and obj.get("trang_thai") == mu.ACTIVE \
                and obj.get("ung_vien") == "1.1.0":
            raise mu.MatDien("ngay sau ACTIVE")

    monkeypatch.setattr(mu, "ghi_json_nguyen_tu", ghi)
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.STAGED
    with pytest.raises(mu.MatDien):
        cn.ap_dung()
    monkeypatch.setattr(mu, "ghi_json_nguyen_tu", ghi_goc)
    cn2 = mt["tao"]()
    cn2.phuc_hoi()
    assert _hien(mt) == "1.1.0" and cn2.last_good()["phien_ban"] == "1.1.0" and not cn2.cach_ly()


# ---------------------------------------------------------------- B: lỗi lạ không thoát khỏi updater

def test_health_sau_kich_hoat_khong_chay_duoc_quay_ve_ngay_cach_ly_sau_3_lan(mt):
    """B + N3: health KHÔNG chạy được (timeout) → quay về bản trước NGAY (an toàn), nhưng có thể chỉ là máy
    chậm lúc 3 giờ sáng → chỉ cách ly sau ``SO_LAN_LOI_TOI_DA`` lần; không bao giờ thoát khỏi updater."""
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    goc = mt["gia"].kiem_suc_khoe

    def kiem(m, rel, rt, che_do):
        if che_do == "kich_hoat":
            raise subprocess.TimeoutExpired(["health_check.py"], 600)
        return goc(m, rel, rt, che_do)

    for lan in range(1, mu.SO_LAN_LOI_TOI_DA + 1):
        cn = mt["tao"](kiem_suc_khoe=kiem)
        assert cn.chuan_bi().trang_thai == mu.STAGED, lan
        kq = cn.ap_dung()
        assert _hien(mt) == "1.0.0" and cn.last_good()["phien_ban"] == "1.0.0"
        if lan < mu.SO_LAN_LOI_TOI_DA:
            assert kq.trang_thai == mu.LOI and "1.1.0" not in cn.cach_ly(), (lan, kq)
    assert kq.trang_thai == mu.QUARANTINED and "1.1.0" in cn.cach_ly()


def test_khoi_phuc_khi_health_nem_oserror_khong_lam_sap(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])

    def chet(ten):
        if ten == mu.HEALTHCHECK:
            raise mu.MatDien(ten)

    cn = mt["tao"](diem_dung=chet)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    with pytest.raises(mu.MatDien):
        cn.ap_dung()

    def kiem(m, rel, rt, che_do):
        raise OSError("không chạy được python của runtime")

    cn2 = mt["tao"](kiem_suc_khoe=kiem)
    cn2.phuc_hoi()
    assert _hien(mt) == "1.0.0" and "1.1.0" not in cn2.cach_ly()           # lần 1: có thể tạm thời
    assert cn2.nk.doc()["trang_thai"] == mu.CHECKED


def test_tao_runtime_loi_subprocess_khong_thoat_va_cach_ly_sau_so_lan_toi_da(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"], sua_manifest=RUNTIME_MOI)

    def tao(m, rel, rt):
        raise subprocess.CalledProcessError(1, ["pip", "install"])

    for _ in range(mu.SO_LAN_LOI_TOI_DA):
        kq = mt["tao"](tao_moi_truong=tao).chuan_bi()
        assert kq.trang_thai == mu.LOI, kq
    assert "1.1.0" in mt["tao"]().cach_ly()
    assert mt["tao"](tao_moi_truong=tao).chuan_bi().trang_thai == mu.KHONG_CO    # không tải lại mãi
    assert _hien(mt) == "1.0.0"


def test_lock_chua_bam_cach_ly_ngay(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"], sua_manifest=RUNTIME_MOI)

    def tao(m, rel, rt):
        raise mu.TuChoiGoi("lock_chua_bam", "Lock chưa có băm gói — không cài runtime chưa xác minh.")

    assert mt["tao"](tao_moi_truong=tao).chuan_bi().trang_thai == mu.TU_CHOI
    assert "1.1.0" in mt["tao"]().cach_ly() and _hien(mt) == "1.0.0"


def test_migration_loi_cach_ly_khong_lap_lai_sao_luu(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"], sua_manifest=dict(du_lieu={"lich_su": 4}))

    def di_chuyen(m, rel, rt):
        raise mu.LoiCapNhat("migration", "Migration lỗi (giả).")

    cn = mt["tao"](di_chuyen=di_chuyen)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    kq = cn.ap_dung()
    assert kq.trang_thai == mu.QUARANTINED, kq
    assert _hien(mt) == "1.0.0" and mt["gia"].phien_ban_db() == 3 and "1.1.0" in cn.cach_ly()
    so = _so(mt, "sao_luu")
    cn2 = mt["tao"](di_chuyen=di_chuyen)
    cn2.phuc_hoi()
    assert cn2.ap_dung().trang_thai != mu.ACTIVE
    assert _so(mt, "sao_luu") == so


# ---------------------------------------------------------------- D: máy mới / cần duyệt

def test_may_moi_chua_co_lich_su_khong_can_co_migration(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"],
              sua_manifest=dict(du_lieu={"tuong_thich_nguoc": False}, migration={"tu_dong_an_toan": False}))
    cn = mt["tao"](phien_ban_db=lambda: None)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    kq = cn.ap_dung()
    assert kq.trang_thai == mu.ACTIVE, kq
    assert not [g for g in mt["gia"].goi if g[0] == "di_chuyen"]   # N4: app tự tạo lược đồ lúc mở lần đầu


def test_can_duyet_migration_bao_ngay_luc_chuan_bi_khong_tai_khong_sao_luu(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"],
              sua_manifest=dict(du_lieu={"lich_su": 4}, migration={"tu_dong_an_toan": False}))
    so = _so(mt, "sao_luu")
    cn = mt["tao"]()
    kq = cn.chuan_bi()
    assert kq.trang_thai == mu.WAITING_APPROVAL, kq
    assert not os.path.exists(mt["cd"].release_dir("1.1.0"))
    assert cn.ap_dung().trang_thai != mu.ACTIVE
    assert _so(mt, "sao_luu") == so and _hien(mt) == "1.0.0"


# ---------------------------------------------------------------- P3

def test_hoan_bam_trong_luc_cho_ranh_van_duoc_ton_trong(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])

    def hoan_giua_chung(ten):
        if ten == mu.WAITING_IDLE:
            mu.dat_hoan(mt["cd"].goc, 24)

    cn = mt["tao"](diem_dung=hoan_giua_chung)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    kq = cn.ap_dung()
    assert kq.trang_thai == mu.STAGED and "hoãn" in kq.thong_diep and _hien(mt) == "1.0.0"


def test_chu_ky_sai_bo_qua_nhung_khong_cach_ly_vinh_vien(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], ky_bang=KhoaThu())     # vd. thư mục USB chép dở / sai khoá
    cn = mt["tao"]()
    kq = cn.chuan_bi()
    assert kq.trang_thai == mu.KHONG_CO and "KHÔNG tin cậy" in " ".join(kq.chi_tiet)
    assert "1.0.0" not in cn.cach_ly()
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"])                       # chép lại bản đúng
    assert mt["tao"]().chuan_bi().trang_thai == mu.STAGED


def test_thieu_goi_luc_dang_tai_len_khong_cach_ly(mt):
    thu_muc = phat_hanh(mt["nguon"], "1.0.0", mt["khoa"])
    ten = next(f for f in os.listdir(thu_muc) if f.endswith(".zip"))
    tam = os.path.join(str(mt["tmp"]), ten)
    os.replace(os.path.join(thu_muc, ten), tam)                         # gói chưa tải lên xong
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.KHONG_CO and "1.0.0" not in cn.cach_ly()
    os.replace(tam, os.path.join(thu_muc, ten))
    assert mt["tao"]().chuan_bi().trang_thai == mu.STAGED


def test_bo_cach_ly_cho_phep_thu_lai(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    mt["gia"].suc_khoe["staging"] = False
    assert mt["tao"]().chuan_bi().trang_thai == mu.QUARANTINED
    mt["gia"].suc_khoe["staging"] = True
    cn = mt["tao"]()
    assert cn.bo_cach_ly("1.1.0") is True and "1.1.0" not in cn.cach_ly()
    assert cn.bo_cach_ly("9.9.9") is False
    assert cn.chuan_bi().trang_thai == mu.STAGED


def test_ghi_json_thu_lai_khi_nguoi_doc_dang_mo_file(tmp_path, monkeypatch):
    p = str(tmp_path / "us" / "current.json")
    goc = os.replace
    lan = []

    def thay(a, b):
        lan.append(1)
        if len(lan) <= 2:
            raise PermissionError(13, "file đang được tiến trình khác mở")
        goc(a, b)

    monkeypatch.setattr(mu.time, "sleep", lambda s: None)
    monkeypatch.setattr(mu.os, "replace", thay)
    mu.ghi_json_nguyen_tu(p, {"a": 1})
    monkeypatch.setattr(mu.os, "replace", goc)
    assert mu.doc_json(p) == {"a": 1} and len(lan) == 3
    assert not [f for f in os.listdir(os.path.dirname(p)) if ".tmp-" in f]


def test_ghi_json_het_lan_thu_thi_bao_loi_va_khong_de_file_tam(tmp_path, monkeypatch):
    p = str(tmp_path / "us" / "current.json")

    def luon_loi(a, b):
        raise PermissionError(13, "file đang được tiến trình khác mở")

    monkeypatch.setattr(mu.time, "sleep", lambda s: None)
    monkeypatch.setattr(mu.os, "replace", luon_loi)
    with pytest.raises(PermissionError):
        mu.ghi_json_nguyen_tu(p, {"a": 1})
    monkeypatch.undo()
    assert not [f for f in os.listdir(os.path.dirname(p)) if ".tmp-" in f]


def test_dau_san_sang_cua_runtime_dang_dung_hong_khong_xoa_runtime(mt):
    _cai(mt, "1.0.0")
    rt = mu.doc_json(mt["cd"].file_trang_thai("current.json"))["runtime"]
    dau = os.path.join(rt, "Lib", "goi_dang_dung.txt")                  # gói đã cài trong runtime đang chạy
    os.makedirs(os.path.dirname(dau))
    with open(dau, "w", encoding="utf-8") as f:
        f.write("x")
    with open(os.path.join(rt, mu.TEN_SAN_SANG), "w", encoding="utf-8") as f:
        f.write("{hỏng")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])                         # cùng runtime (cùng lock)
    kq = mt["tao"]().chuan_bi()
    assert os.path.isfile(dau), "đã xoá runtime đang dùng"
    assert kq.trang_thai == mu.LOI and _hien(mt) == "1.0.0"


# ---------------------------------------------------------------- P3: nguồn GitHub / dọn bản cũ

class _RepHop:
    def __init__(self, url, status=200, location="", data=b"{}"):
        self.url, self.status_code, self._data = url, status, data
        self.headers = {"Location": location} if location else {}
        self.history = []

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        yield self._data

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _HttpTungBuoc:
    """Phiên HTTP giả theo kiểu ``allow_redirects=False``: mỗi URL một phản hồi, ghi lại URL đã gọi."""

    def __init__(self, bang):
        self.bang, self.goi = bang, []

    def get(self, url, **kw):
        self.goi.append((url, kw.get("allow_redirects")))
        assert kw.get("timeout"), "mọi request phải có timeout"
        return self.bang[url]


def _ban(url):
    import json as _json

    return mu.BanPhatHanh(tag="stable-1.0.0", draft=False, prerelease=False, assets=("goi.zip",),
                          tham_chieu=_json.dumps({"goi.zip": url}))


def test_github_kiem_host_tung_buoc_chuyen_huong_truoc_khi_goi(tmp_path):
    goc, xau = "https://github.com/o/r/releases/download/x/goi.zip", "https://evil.example.com/goi.zip"
    http = _HttpTungBuoc({goc: _RepHop(goc, 302, xau), xau: _RepHop(xau, data=b"x")})
    with pytest.raises(mu.TuChoiGoi):
        mu.NguonGitHub("o/r", http=http).tai(_ban(goc), "goi.zip", str(tmp_path / "g"), 1000)
    assert [u for u, _ in http.goi] == [goc]                     # KHÔNG gửi request nào tới host lạ


def test_github_theo_chuyen_huong_hop_le(tmp_path):
    goc = "https://github.com/o/r/releases/download/x/goi.zip"
    cdn = "https://objects.githubusercontent.com/github-production-release-asset/goi.zip"
    http = _HttpTungBuoc({goc: _RepHop(goc, 302, cdn), cdn: _RepHop(cdn, data=b"abc")})
    mu.NguonGitHub("o/r", http=http).tai(_ban(goc), "goi.zip", str(tmp_path / "g"), 1000)
    assert open(tmp_path / "g", "rb").read() == b"abc"
    assert [a for _, a in http.goi] == [False, False]


def test_don_ban_cu_con_tro_hong_khong_xoa_gi(mt):
    for pb in ("1.0.0", "1.1.0", "1.2.0"):
        _cai(mt, pb)
    with open(mt["cd"].file_trang_thai("current.json"), "w", encoding="utf-8") as f:
        f.write("{hỏng")
    with pytest.raises(mu.LoiCapNhat):
        mu.don_ban_cu(mt["cd"], giu=1)
    assert all(os.path.isdir(mt["cd"].release_dir(pb)) for pb in ("1.0.0", "1.1.0", "1.2.0"))


# ---------------------------------------------------------------- rà soát lại 908d946 (N3, N4, N6)

def test_health_staging_khong_chay_duoc_cach_ly_sau_3_lan(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])

    def kiem(m, rel, rt, che_do):
        raise subprocess.TimeoutExpired(["health_check.py"], 600)

    for lan in range(1, mu.SO_LAN_LOI_TOI_DA):
        kq = mt["tao"](kiem_suc_khoe=kiem).chuan_bi()
        assert kq.trang_thai == mu.LOI and "1.1.0" not in mt["tao"]().cach_ly(), (lan, kq)
    assert mt["tao"](kiem_suc_khoe=kiem).chuan_bi().trang_thai == mu.QUARANTINED
    assert _hien(mt) == "1.0.0"


def test_migration_tam_thoi_khong_cach_ly_ngay(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"], sua_manifest=dict(du_lieu={"lich_su": 4}))

    def di_chuyen(m, rel, rt):
        raise mu.LoiTamThoi("migration", "database is locked (giả)")

    cn = mt["tao"](di_chuyen=di_chuyen)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    kq = cn.ap_dung()
    assert kq.trang_thai == mu.LOI and "1.1.0" not in cn.cach_ly() and _hien(mt) == "1.0.0"
    assert cn.nk.doc()["trang_thai"] == mu.STAGED                       # lần sau áp dụng lại, không tải lại
    for _ in range(mu.SO_LAN_LOI_TOI_DA - 1):
        kq = mt["tao"](di_chuyen=di_chuyen).ap_dung()
    assert kq.trang_thai == mu.QUARANTINED and "1.1.0" in mt["tao"]().cach_ly()


@pytest.mark.parametrize("ma", ["nguon", "qua_lon"])
def test_tai_manifest_loi_van_chuyen_khong_cach_ly(mt, ma):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"])

    class NguonLoi(mu.NguonThuMuc):
        def tai(self, ban, ten, dich, gioi_han):
            raise mu.TuChoiGoi(ma, "lỗi vận chuyển (giả)")

    cn = mt["tao"](nguon=NguonLoi(mt["nguon"]))
    assert cn.chuan_bi().trang_thai == mu.KHONG_CO and "1.0.0" not in cn.cach_ly()
    assert mt["tao"]().chuan_bi().trang_thai == mu.STAGED


def test_ban_cai_da_co_ban_ma_chua_co_lich_su_khong_migration(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"], sua_manifest=dict(du_lieu={"lich_su": 4},
                                                                migration={"tu_dong_an_toan": False}))
    cn = mt["tao"](phien_ban_db=lambda: None)                         # app chưa mở lần nào
    assert cn.chuan_bi().trang_thai == mu.STAGED
    assert cn.ap_dung().trang_thai == mu.ACTIVE
    assert not [g for g in mt["gia"].goi if g[0] == "di_chuyen"]


def test_cai_lan_dau_khoi_phuc_kiem_ngay_khong_cho_ranh(mt):
    """N6: cài lần đầu (không có bản trước) bị cắt ở HEALTHCHECK; lúc mở lại đã có việc chạy trên CHÍNH bản đó →
    không chờ rảnh (không có bản nào khác để bảo vệ) — kiểm health ngay và chốt."""
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"])

    def chet(ten):
        if ten == mu.HEALTHCHECK:
            raise mu.MatDien(ten)

    cn = mt["tao"](diem_dung=chet)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    with pytest.raises(mu.MatDien):
        cn.ap_dung()
    with mg.CongBaoTri(mt["cd"].data_dir).viec("lô quét đang chạy trên bản 1.0.0"):
        cn2 = mt["tao"]()
        assert cn2.phuc_hoi() == mu.ACTIVE
    assert _hien(mt) == "1.0.0" and cn2.last_good()["phien_ban"] == "1.0.0"


def test_ghi_bo_dem_loi_tam_thoi_hong_van_quay_ve_ban_truoc(mt, monkeypatch):
    """Ghi bộ đếm lỗi tạm thời lỗi (đĩa đầy) KHÔNG được chặn việc quay về bản trước."""
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    goc = mt["gia"].kiem_suc_khoe

    def kiem(m, rel, rt, che_do):
        if che_do == "kich_hoat":
            raise subprocess.TimeoutExpired(["health_check.py"], 600)
        return goc(m, rel, rt, che_do)

    def hong(self, phien_ban):
        raise OSError("đĩa đầy (giả)")

    monkeypatch.setattr(mu.CapNhat, "_het_luot_tam_thoi", hong)
    cn = mt["tao"](kiem_suc_khoe=kiem)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    kq = cn.ap_dung()
    assert _hien(mt) == "1.0.0", kq


# ---------------------------------------------------------------- kiểm đột biến trên dfdce2e: mã đã đúng, test
# này ĐỎ dưới đột biến «ghi last_good trước ACTIVE» (test kết quả an toàn ở mục A vẫn xanh khi đảo thứ tự vì
# quay lại không dựa vào last_good — ``_con_tro_truoc``)

def test_last_good_chi_tro_ban_moi_khi_nhat_ky_da_ghi_ben_active(mt, monkeypatch):
    """last_good chỉ trỏ bản mới SAU KHI nhật ký đã ghi bền ACTIVE (bản đã chốt). Mất điện ngay sau khi ghi
    last_good → lần mở sau không rút cổng, không kiểm lại health; bản mới vẫn ACTIVE, không bị cách ly."""
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    ghi_goc = mu.ghi_json_nguyen_tu
    nk_luc_ghi = []

    def la_last_good_moi(path, obj):
        return path.endswith("last_good.json") and isinstance(obj, dict) and obj.get("phien_ban") == "1.1.0"

    def ghi(path, obj):
        if la_last_good_moi(path, obj):
            nk = mu.doc_json(mt["cd"].file_trang_thai("journal.json")) or {}
            nk_luc_ghi.append(nk.get("trang_thai"))
        ghi_goc(path, obj)
        if la_last_good_moi(path, obj):
            raise mu.MatDien("ngay sau khi ghi last_good")

    monkeypatch.setattr(mu, "ghi_json_nguyen_tu", ghi)
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.STAGED
    with pytest.raises(mu.MatDien):
        cn.ap_dung()
    monkeypatch.setattr(mu, "ghi_json_nguyen_tu", ghi_goc)
    assert nk_luc_ghi == [mu.ACTIVE], nk_luc_ghi
    truoc = _so(mt, "kiem_suc_khoe")
    cn2 = mt["tao"]()
    assert cn2.phuc_hoi() == mu.ACTIVE
    assert _so(mt, "kiem_suc_khoe") == truoc, "khôi phục kiểm lại health của bản đã chốt"
    assert _hien(mt) == "1.1.0" and cn2.last_good()["phien_ban"] == "1.1.0" and not cn2.cach_ly()


# ---------------------------------------------------------------- audit 06/11

def test_manifest_nam_sai_tag_khong_cach_ly_so_phien_ban_tuong_lai(mt):
    """Chép thư mục feed để chuẩn bị bản sau: «update check» (chỉ kiểm) từng cách ly 1.2.0, bản 1.2.0 thật bị bỏ qua."""
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    shutil.copytree(os.path.join(mt["nguon"], "stable-1.1.0"), os.path.join(mt["nguon"], "stable-1.2.0"))
    kq = mt["tao"]().kiem_tra()
    assert any("không khớp tag" in x for x in kq.chi_tiet), kq
    assert mt["tao"]().cach_ly() == {}
    shutil.rmtree(os.path.join(mt["nguon"], "stable-1.2.0"))
    phat_hanh(mt["nguon"], "1.2.0", mt["khoa"])
    assert mt["tao"]().chuan_bi().phien_ban == "1.2.0"


def test_khong_co_gi_de_ap_dung_khong_bao_active(mt):
    """Tài liệu lấy «[ACTIVE] …» làm dấu hiệu cập nhật thành công: feed rỗng mà in ACTIVE là báo sai."""
    _cai(mt, "1.0.0")
    assert mt["tao"]().ap_dung().trang_thai == mu.KHONG_CO


def test_cho_duyet_migration_tra_ma_khac_0_de_cua_so_khong_tu_dong():
    import launcher

    kq = mu.KetQua(mu.WAITING_APPROVAL, "1.1.0", "Cần duyệt migration trước khi cập nhật.")
    assert launcher._in(kq) != 0


def test_ban_cho_duyet_bi_rut_khoi_feed_khong_lam_capnhat_dung_loi(mt):
    """Nhật ký còn WAITING_APPROVAL của bản đã rút: «apply» không có gì để làm, không được báo lỗi."""
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"],
              sua_manifest=dict(du_lieu={"lich_su": 4}, migration={"tu_dong_an_toan": False}))
    assert mt["tao"]().chuan_bi().trang_thai == mu.WAITING_APPROVAL
    shutil.rmtree(os.path.join(mt["nguon"], "stable-1.1.0"))
    assert mt["tao"]().chuan_bi().trang_thai == mu.KHONG_CO
    assert mt["tao"]().ap_dung().trang_thai == mu.KHONG_CO


# ---------------------------------------------------------------- audit số 14: kẽ hở tìm bằng đột biến (xoá chốt thì
# test cũ vẫn xanh)

def _chet_tai(diem):
    def chet(ten):
        if ten == diem:
            raise mu.MatDien(ten)

    return chet


def test_khoi_phuc_con_viec_chay_khong_kiem_health_tam_ve_ban_truoc(mt):
    """Test cài lần đầu không đi qua nhánh này: đã có bản trước thì còn việc chạy = chưa được chốt bản mới."""
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    cn = mt["tao"](diem_dung=_chet_tai("POINTER_SWITCHED"))
    assert cn.chuan_bi().trang_thai == mu.STAGED
    with pytest.raises(mu.MatDien):
        cn.ap_dung()
    assert _hien(mt) == "1.1.0"
    truoc = _so(mt, "kiem_suc_khoe")
    with mg.CongBaoTri(mt["cd"].data_dir).viec("lô quét đang chạy"):
        cn2 = mt["tao"]()
        assert cn2.phuc_hoi() == mu.STAGED
    assert _hien(mt) == "1.0.0" and _so(mt, "kiem_suc_khoe") == truoc
    assert not cn2.cach_ly()


def test_chet_giua_quay_lai_khoi_phuc_hoan_tat_quay_lai_va_cach_ly(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    mt["gia"].suc_khoe["kich_hoat"] = False
    cn = mt["tao"](diem_dung=_chet_tai(mu.ROLLBACK))
    assert cn.chuan_bi().trang_thai == mu.STAGED
    with pytest.raises(mu.MatDien):
        cn.ap_dung()
    mt["gia"].suc_khoe["kich_hoat"] = True               # health lần này đạt cũng không cứu được bản đã bị từ chối
    cn2 = mt["tao"]()
    assert cn2.phuc_hoi() == mu.QUARANTINED
    assert _hien(mt) == "1.0.0" and cn2.last_good()["phien_ban"] == "1.0.0"
    assert "1.1.0" in cn2.cach_ly()


def test_mat_dau_san_sang_runtime_ung_vien_truoc_ap_dung_khong_doi_con_tro(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"], sua_manifest=RUNTIME_MOI)
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.STAGED
    os.remove(os.path.join(cn.nk.doc()["con_tro_moi"]["runtime"], mu.TEN_SAN_SANG))
    truoc = _so(mt, "sao_luu"), _so(mt, "kiem_suc_khoe")
    assert cn.ap_dung().trang_thai == mu.LOI
    assert _hien(mt) == "1.0.0" and (_so(mt, "sao_luu"), _so(mt, "kiem_suc_khoe")) == truoc


def test_manifest_ky_dung_khac_nen_tang_bi_cach_ly(mt):
    """Ca linux_x86_64 cũ dừng ở «Tên gói»: phải có tên gói khớp nền tảng lạ mới tới được chốt nền tảng."""
    ten = "TimClipPro-1.0.0-linux_x86_64.zip"
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], sua_manifest=dict(nen_tang="linux_x86_64", goi={"ten": ten}))
    cn = mt["tao"]()
    assert cn.kiem_tra().trang_thai == mu.KHONG_CO
    assert "nền tảng này" in cn.cach_ly()["1.0.0"]["ly_do"]


def test_khoa_tin_cay_key_id_khong_khop_bi_tu_choi(tmp_path):
    path = KhoaThu().ghi_tin_cay(str(tmp_path / "trusted_keys.json"))
    d = mu.doc_json(path)
    d["khoa"][0]["key_id"] = "0" * 16
    mu.ghi_json_nguyen_tu(path, d)
    with pytest.raises(mu.LoiCapNhat) as loi:
        mu.doc_khoa_tin_cay(path)
    assert loi.value.ma == "khoa_tin_cay" and "key_id" in str(loi.value)


@pytest.mark.skipif(os.name != "nt", reason="junction chỉ có trên Windows")
def test_cay_release_chua_junction_bi_tu_choi(mt):
    _cai(mt, "1.0.0")
    rel = mt["cd"].release_dir("1.0.0")
    with open(os.path.join(rel, mu.TEN_MANIFEST), "rb") as f:
        m = mu.doc_manifest(f.read())
    mu.kiem_cay_release(rel, m)                          # cây lành thì đạt: lỗi dưới đây chỉ do junction
    dich = os.path.join(str(mt["tmp"]), "ngoai_release")
    os.makedirs(dich)
    junction = os.path.join(rel, "TimClipPro", "lien_ket")
    subprocess.run(["cmd", "/c", "mklink", "/J", junction, dich], check=True, capture_output=True)
    try:
        with pytest.raises(mu.TuChoiGoi) as loi:
            mu.kiem_cay_release(rel, m)
        assert loi.value.ma == "zip_symlink"
    finally:
        os.rmdir(junction)


def test_zip_co_muc_ma_hoa_bi_tu_choi(tmp_path):
    goi, dich = tmp_path / "goi.zip", tmp_path / "dich"
    with zipfile.ZipFile(goi, "w", zipfile.ZIP_STORED) as z:
        z.writestr("a.txt", b"noi dung")
    raw = bytearray(goi.read_bytes())
    raw[6] |= 1                                          # cờ mã hoá ở header cục bộ
    raw[raw.index(b"PK\x01\x02") + 8] |= 1               # và ở thư mục trung tâm (zipfile đọc cờ ở đây)
    goi.write_bytes(raw)
    with pytest.raises(mu.TuChoiGoi) as loi:
        mu.giai_nen_an_toan(str(goi), str(dich))
    assert loi.value.ma == "zip" and "mã hoá" in str(loi.value)
    assert not dich.exists()


def test_runtime_id_thoat_khoi_environments_bi_cach_ly_truoc_khi_tao(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], sua_manifest=dict(runtime={"runtime_id": "../escaped-runtime"}))
    goi = []
    cn = mt["tao"](tao_moi_truong=lambda m, rel, rt: goi.append(rt))
    assert cn.chuan_bi().trang_thai == mu.KHONG_CO
    assert "Mã runtime" in cn.cach_ly()["1.0.0"]["ly_do"] and goi == []


def test_zip_qua_so_file_bi_tu_choi_khong_giai_nen(tmp_path):
    goi, dich = tmp_path / "goi.zip", tmp_path / "dich"
    with zipfile.ZipFile(goi, "w") as z:
        for ten in ("a.txt", "b.txt", "c.txt"):
            z.writestr(ten, b"")
    with pytest.raises(mu.TuChoiGoi) as loi:
        mu.giai_nen_an_toan(str(goi), str(dich), gioi_han_so_file=2)
    assert loi.value.ma == "zip" and "quá nhiều file" in str(loi.value)
    assert not dich.exists()


def test_manifest_khai_goi_vuot_tran_bi_cach_ly_khong_tai(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], sua_manifest=dict(goi={"kich_thuoc": mu.GIOI_HAN_GOI + 1}))
    cn = mt["tao"]()
    assert cn.kiem_tra().trang_thai == mu.KHONG_CO
    assert "Kích thước gói khai báo vượt giới hạn" in cn.cach_ly()["1.0.0"]["ly_do"]


# ---------------------------------------------------------------- phản biện ngoài 07/11 (F2)

def test_manifest_kenh_khac_nam_sai_tag_khong_cach_ly_so_phien_ban_cua_tag(mt):
    """Manifest beta 1.1.0 ký đúng nằm nhầm thư mục stable-2.0.0: nó không nói gì về bản 2.0.0 thật chép vào sau."""
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"], tag="stable-2.0.0", sua_manifest=dict(kenh="beta"))
    kq = mt["tao"]().kiem_tra()
    assert any("không khớp tag" in x for x in kq.chi_tiet), kq
    assert mt["tao"]().cach_ly() == {}
    shutil.rmtree(os.path.join(mt["nguon"], "stable-2.0.0"))
    phat_hanh(mt["nguon"], "2.0.0", mt["khoa"])
    assert mt["tao"]().chuan_bi().phien_ban == "2.0.0"
