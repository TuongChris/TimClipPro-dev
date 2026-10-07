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
import subprocess

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
