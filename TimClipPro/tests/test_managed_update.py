# -*- coding: utf-8 -*-
"""Bộ cập nhật Stable có quản lý (managed_update) — artifact TỔNG HỢP ký bằng khoá thử, nguồn thư mục,
runtime/health/migration giả, cổng bảo trì thật, SQLite thật. Không mạng.

Ma trận brief §17 (Update / Idle gate / Crash update / Rollback): chỉ nhận bản ký hợp lệ; draft/RC/sai
repo/sai chữ ký/băm/Zip Slip/đầy đĩa/timeout bị từ chối và bản cũ vẫn chạy; không đổi mã khi còn việc;
mất điện ở từng điểm khôi phục xác định; health lỗi quay về bản trước, không bao giờ khôi phục DB.
"""
import json
import os
import shutil
import zipfile

import pytest

import maintenance_gate as mg
import managed_update as mu
from cap_nhat_gia import KhoaThu, MoiTruongGia, cay_mac_dinh, phat_hanh


@pytest.fixture()
def mt(tmp_path):
    khoa = KhoaThu()
    goc = str(tmp_path / "cai dat có dấu")          # khoảng trắng + Unicode trong đường dẫn
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


# ---------------------------------------------------------------- đường thành công

def test_ban_ky_hop_le_duoc_stage_roi_kich_hoat(mt):
    cn = _cai(mt)
    rel = mt["cd"].release_dir("1.0.0")
    assert _hien(mt) == "1.0.0"
    assert mu.doc_json(mt["cd"].file_trang_thai("last_good.json"))["phien_ban"] == "1.0.0"
    assert open(os.path.join(rel, "TimClipPro", "app.py"), encoding="utf-8").read() == "# app 1.0.0\n"
    assert os.path.isfile(os.path.join(rel, mu.TEN_DAU_RELEASE))
    assert cn.nk.doc()["trang_thai"] == mu.ACTIVE
    assert not os.path.exists(mt["cd"].staging) or not os.listdir(mt["cd"].staging)
    assert ("kiem_suc_khoe", "1.0.0", "staging") in mt["gia"].goi
    assert ("kiem_suc_khoe", "1.0.0", "kich_hoat") in mt["gia"].goi


def test_nang_cap_giu_last_good_va_dung_lai_runtime(mt):
    _cai(mt, "1.0.0")
    cn = _cai(mt, "1.1.0")
    assert _hien(mt) == "1.1.0"
    assert [g for g in mt["gia"].goi if g[0] == "tao_moi_truong"] == [("tao_moi_truong", "1.0.0")]
    assert cn.trang_thai()["last_good"]["phien_ban"] == "1.1.0"


# ---------------------------------------------------------------- chính sách + xác thực

def test_chu_ky_khoa_la_bi_tu_choi_khong_cai_khong_cach_ly(mt):
    # Rà soát M3+M4 (P3-3): chữ ký sai chỉ BỎ QUA — không cách ly theo số phiên bản (thư mục chép dở / bản
    # đang tải lên sẽ chặn vĩnh viễn bản đúng). Xem test_managed_update_ra_soat.py.
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], ky_bang=KhoaThu())
    cn = mt["tao"]()
    kq = cn.chuan_bi()
    assert kq.trang_thai == mu.KHONG_CO and "KHÔNG tin cậy" in " ".join(kq.chi_tiet)
    assert "1.0.0" not in cn.cach_ly()
    assert not os.path.exists(mt["cd"].release_dir("1.0.0")) and _hien(mt) is None


def test_manifest_bi_sua_sau_khi_ky_bi_tu_choi(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"],
              sua_sau_ky=lambda raw: raw.replace(b'"lich_su": 3', b'"lich_su": 4'))
    cn = mt["tao"]()
    kq = cn.chuan_bi()
    assert kq.trang_thai == mu.KHONG_CO and "không hợp lệ" in " ".join(kq.chi_tiet).lower()
    assert not os.path.exists(mt["cd"].release_dir("1.0.0"))


@pytest.mark.parametrize("kw", [dict(draft=True), dict(prerelease=True), dict(tag="v1.0.0"),
                                dict(tag="stable-1.0.0-rc1"), dict(tag="latest")])
def test_draft_prerelease_tag_khong_stable_bi_bo_qua(mt, kw):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], **kw)
    kq = mt["tao"]().chuan_bi()
    assert kq.trang_thai == mu.KHONG_CO and _hien(mt) is None


@pytest.mark.parametrize("sua,ma", [
    (dict(kenh="beta"), "Stable"),
    (dict(ung_dung="CongCuKhac"), "không phải của TimClipPro"),
    (dict(phien_ban="1.4.0"), "Tên gói"),
    (dict(nen_tang="linux_x86_64"), "Tên gói"),
    (dict(migration={"tu_dong_an_toan": True}, du_lieu={"lich_su": 3, "tuong_thich_nguoc": False}),
     "tương thích ngược"),
])
def test_manifest_ky_dung_nhung_sai_chinh_sach_bi_tu_choi(mt, sua, ma):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], sua_manifest=sua)
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.KHONG_CO
    assert ma in cn.cach_ly()["1.0.0"]["ly_do"]


def test_khong_ha_ban_khong_cai_lai_ban_dang_chay(mt):
    _cai(mt, "1.2.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    assert mt["tao"]().chuan_bi().trang_thai == mu.KHONG_CO
    assert _hien(mt) == "1.2.0"


def test_chon_ban_stable_cao_nhat_theo_so_khong_theo_chuoi(mt):
    phat_hanh(mt["nguon"], "1.9.0", mt["khoa"])
    phat_hanh(mt["nguon"], "1.10.0", mt["khoa"])
    assert mt["tao"]().chuan_bi().phien_ban == "1.10.0"


def test_launcher_cu_hon_yeu_cau_thi_khong_cai(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], sua_manifest=dict(launcher_toi_thieu=2))
    kq = mt["tao"]().chuan_bi()
    assert kq.trang_thai == mu.KHONG_CO and any("launcher" in x for x in kq.chi_tiet)


# ---------------------------------------------------------------- gói hỏng / độc hại

def test_goi_bi_sua_khong_khop_bam_khong_cai_va_cach_ly_sau_nhieu_lan(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], sua_zip_sau=lambda b: b[:-1] + bytes([b[-1] ^ 1]))
    for lan in range(mu.SO_LAN_LOI_TOI_DA):
        cn = mt["tao"]()
        kq = cn.chuan_bi()
        assert kq.trang_thai == (mu.TU_CHOI if lan < mu.SO_LAN_LOI_TOI_DA else mu.KHONG_CO)
        assert not os.path.exists(mt["cd"].release_dir("1.0.0")) and _hien(mt) is None
    assert "1.0.0" in mt["tao"]().cach_ly()


@pytest.mark.parametrize("ten_muc, lop_chan", [
    ("../ngoai.txt", "đường dẫn không an toàn"), ("TimClipPro/../../ngoai.txt", "đường dẫn không an toàn"),
    ("/tuyet_doi.txt", "đường dẫn không an toàn"), ("C:/o_dia.txt", "đường dẫn không an toàn"),
    ("TimClipPro/CON.txt", "đường dẫn không an toàn"), ("TimClipPro/ten.  ", "đường dẫn không an toàn"),
    # zipfile trên Windows tự đổi "\" thành "/" khi ĐỌC tên mục → thành đường dẫn hợp lệ; bị chặn ở lớp
    # đối chiếu danh sách file đã ký (file thừa).
    ("TimClipPro\\sau.txt", "thừa/thiếu"),
])
def test_duong_dan_nguy_hiem_trong_zip_bi_tu_choi_khong_ghi_ra_ngoai(mt, ten_muc, lop_chan):
    zi = zipfile.ZipInfo("x")
    zi.filename = ten_muc            # bỏ chuẩn hoá của ZipInfo để giữ nguyên tên độc hại
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], them_muc=[(zi, b"doc hai")])
    cn = mt["tao"]()
    kq = cn.chuan_bi()
    assert kq.trang_thai == mu.TU_CHOI, kq
    assert lop_chan in kq.thong_diep
    assert not os.path.exists(mt["cd"].release_dir("1.0.0"))
    assert not any(".tmp-" in x for x in os.listdir(mt["cd"].releases)) if os.path.isdir(
        mt["cd"].releases) else True
    assert not (mt["tmp"] / "ngoai.txt").exists() and not os.path.exists(
        os.path.join(mt["cd"].goc, "ngoai.txt"))
    assert "1.0.0" in cn.cach_ly()


def test_symlink_trong_zip_bi_tu_choi(mt):
    zi = zipfile.ZipInfo("TimClipPro/lien_ket")
    zi.external_attr = (0o120777 << 16)
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], them_muc=[(zi, b"C:/Windows")])
    assert mt["tao"]().chuan_bi().trang_thai == mu.TU_CHOI


def test_ten_trung_khong_phan_biet_hoa_thuong_bi_tu_choi(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], them_muc=[("timclippro/APP.PY", b"khac")])
    assert mt["tao"]().chuan_bi().trang_thai == mu.TU_CHOI


def test_zip_bom_bi_tu_choi(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], them_muc=[("TimClipPro/bom.bin", b"\0" * 5_000_000)])
    kq = mt["tao"]().chuan_bi()
    assert kq.trang_thai == mu.TU_CHOI and "tỉ lệ nén" in kq.thong_diep


def test_file_thua_ngoai_danh_sach_ky_bi_tu_choi(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], them_muc=[("TimClipPro/la.py", b"import os")])
    kq = mt["tao"]().chuan_bi()
    assert kq.trang_thai == mu.TU_CHOI and "thừa/thiếu" in kq.thong_diep


def test_file_sai_bam_so_voi_danh_sach_bi_tu_choi(mt):
    cay = cay_mac_dinh("1.0.0")
    ds = json.dumps({"files": [{"path": p, "size": len(b), "sha256": "0" * 64}
                               for p, b in sorted(cay.items())]}).encode()
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], cay=cay, ds_file=ds)
    kq = mt["tao"]().chuan_bi()
    assert kq.trang_thai == mu.TU_CHOI and "không khớp băm" in kq.thong_diep


def test_day_dia_khi_giai_nen_khong_de_lai_gi_va_giu_ban_cu(mt, monkeypatch):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    goc = mu.giai_nen_an_toan

    def day(fo, khoi):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(mu, "giai_nen_an_toan", lambda z, d, **kw: goc(z, d, ghi=day))
    kq = mt["tao"]().chuan_bi()
    assert kq.trang_thai == mu.LOI and "OSError" in kq.thong_diep
    assert not os.path.exists(mt["cd"].release_dir("1.1.0"))
    assert not [x for x in os.listdir(mt["cd"].releases) if ".tmp-" in x]
    assert _hien(mt) == "1.0.0"


def test_mat_mang_khi_kiem_van_chay_ban_cu(mt):
    _cai(mt, "1.0.0")

    class NguonDut:
        def ds(self):
            raise ConnectionError("mất mạng")

    for ham in ("kiem_tra", "chuan_bi"):
        kq = getattr(mt["tao"](nguon=NguonDut()), ham)()
        assert kq.trang_thai == mu.LOI and _hien(mt) == "1.0.0"


def test_asset_lon_hon_khai_bao_dung_tai(mt):
    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"], sua_zip_sau=lambda b: b + b"\0" * 1000)
    kq = mt["tao"]().chuan_bi()
    assert kq.trang_thai == mu.TU_CHOI and "giới hạn" in kq.thong_diep


# ---------------------------------------------------------------- cổng bảo trì

def test_con_viec_dang_chay_thi_hoan_khong_doi_ma(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.STAGED
    cong = mg.CongBaoTri(mt["cd"].data_dir)
    with cong.viec("lô quét YouTube"):
        kq = cn.ap_dung()
        assert kq.trang_thai == mu.STAGED and "hoãn" in kq.thong_diep
        assert _hien(mt) == "1.0.0"
    with cong.viec("lô mới sau khi hoãn"):     # cổng đã mở lại
        pass
    assert cn.ap_dung().trang_thai == mu.ACTIVE and _hien(mt) == "1.1.0"


def test_viec_moi_bi_tu_choi_trong_luc_ap_dung(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    bi_chan = []

    def thu_vao(ten):
        if ten in (mu.QUIESCED, mu.MIGRATING, mu.ACTIVATING, mu.HEALTHCHECK):
            try:
                with mg.CongBaoTri(mt["cd"].data_dir).viec("lượt Watch"):
                    bi_chan.append((ten, False))
            except mg.DangBaoTri:
                bi_chan.append((ten, True))

    cn = mt["tao"](diem_dung=thu_vao)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    assert cn.ap_dung().trang_thai == mu.ACTIVE
    assert bi_chan and all(chan for _, chan in bi_chan)


def test_hai_updater_khong_chay_cung_luc(mt):
    from khoa import KhoaTienTrinh

    phat_hanh(mt["nguon"], "1.0.0", mt["khoa"])
    with KhoaTienTrinh(mt["cd"].file_trang_thai("updater.lock"), "updater khác"):
        assert mt["tao"]().chuan_bi().trang_thai == mu.BAN
    assert mt["tao"]().chuan_bi().trang_thai == mu.STAGED


# ---------------------------------------------------------------- health / rollback / migration

def test_health_staging_loi_thi_cach_ly_khong_kich_hoat_khong_lap_lai(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    mt["gia"].suc_khoe["staging"] = False
    assert mt["tao"]().chuan_bi().trang_thai == mu.QUARANTINED
    assert _hien(mt) == "1.0.0"
    assert mt["tao"]().chuan_bi().trang_thai == mu.KHONG_CO   # không cài đi cài lại mỗi lần mở


def test_health_sau_kich_hoat_loi_quay_ve_ban_truoc_khong_khoi_phuc_db(mt):
    _cai(mt, "1.0.0")
    da_gui = mt["gia"].them_viec("SENT")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"], sua_manifest=dict(du_lieu={"lich_su": 4}))
    mt["gia"].suc_khoe["kich_hoat"] = False

    def ghi_sau_backup(ten):
        if ten == mu.MIGRATING:
            mt["gia"].them_viec("SENT")             # dữ liệu nghiệp vụ mới sau backup

    cn = mt["tao"](diem_dung=ghi_sau_backup)
    assert cn.chuan_bi().trang_thai == mu.STAGED
    kq = cn.ap_dung()
    assert kq.trang_thai == mu.QUARANTINED
    assert _hien(mt) == "1.0.0" and "1.1.0" in cn.cach_ly()
    assert mt["gia"].ds_viec() == [(da_gui, "SENT"), (da_gui + 1, "SENT")]   # không restore DB
    assert mt["gia"].phien_ban_db() == 4                                       # migration giữ nguyên


def test_migration_chua_tu_dong_an_toan_cho_duyet(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"],
              sua_manifest=dict(du_lieu={"lich_su": 4}, migration={"tu_dong_an_toan": False}))
    cn = mt["tao"]()
    # Rà soát M3+M4 (P3-1): cần duyệt thì báo NGAY lúc chuẩn bị — không tải gói, không rút cổng, không sao lưu.
    assert cn.chuan_bi().trang_thai == mu.WAITING_APPROVAL
    assert cn.ap_dung().trang_thai == mu.WAITING_APPROVAL
    assert _hien(mt) == "1.0.0" and mt["gia"].phien_ban_db() == 3
    assert not [g for g in mt["gia"].goi if g[0] == "di_chuyen"]


def test_schema_tren_may_moi_hon_ban_phat_hanh_bi_chan(mt):
    _cai(mt, "1.0.0")
    mt["gia"].di_chuyen(type("M", (), {"phien_ban": "x", "lich_su": 5})(), "", "")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    assert mt["tao"]().chuan_bi().trang_thai == mu.BLOCKED
    assert _hien(mt) == "1.0.0"


def test_release_da_stage_bi_sua_thi_khong_kich_hoat_va_cai_lai(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.STAGED
    with open(os.path.join(mt["cd"].release_dir("1.1.0"), "TimClipPro", "app.py"), "a",
              encoding="utf-8") as f:
        f.write("# bị sửa\n")
    assert cn.ap_dung().trang_thai == mu.LOI and _hien(mt) == "1.0.0"
    assert cn.chuan_bi().trang_thai == mu.STAGED
    assert cn.ap_dung().trang_thai == mu.ACTIVE
    assert "# bị sửa" not in open(os.path.join(mt["cd"].release_dir("1.1.0"), "TimClipPro", "app.py"),
                                   encoding="utf-8").read()


def test_nhat_ky_hong_khong_tu_dat_lai(mt):
    _cai(mt, "1.0.0")
    with open(mt["cd"].file_trang_thai("journal.json"), "w", encoding="utf-8") as f:
        f.write("{hỏng")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    cn = mt["tao"]()
    kq = cn.chuan_bi()
    assert kq.trang_thai == mu.LOI and "hỏng" in kq.thong_diep
    with pytest.raises(mu.LoiCapNhat):
        cn.phuc_hoi()
    assert open(mt["cd"].file_trang_thai("journal.json"), encoding="utf-8").read() == "{hỏng"
    assert _hien(mt) == "1.0.0"


# ---------------------------------------------------------------- mất điện ở từng điểm

DIEM = [mu.DOWNLOADING, mu.VERIFIED, "RELEASE_READY", "RUNTIME_READY", mu.STAGED, mu.WAITING_IDLE,
        mu.QUIESCED, mu.BACKED_UP, mu.MIGRATING, "MIGRATED", mu.ACTIVATING, "POINTER_SWITCHED",
        mu.HEALTHCHECK, mu.ACTIVE]


@pytest.mark.parametrize("diem", DIEM)
def test_mat_dien_tung_diem_khoi_phuc_xac_dinh(mt, diem):
    _cai(mt, "1.0.0")
    da_gui = mt["gia"].them_viec("SENT")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"], sua_manifest=dict(du_lieu={"lich_su": 4}))

    def chet(ten):
        if ten == diem:
            raise mu.MatDien(ten)

    cn = mt["tao"](diem_dung=chet)
    with pytest.raises(mu.MatDien):
        if cn.chuan_bi().trang_thai == mu.STAGED:
            cn.ap_dung()
    # Ngay sau "mất điện": con trỏ luôn là một bản chạy được (cũ hoặc mới), JSON hợp lệ.
    assert _hien(mt) in ("1.0.0", "1.1.0")
    # Khởi động lại: bộ cập nhật MỚI (tiến trình mới) khôi phục rồi làm tiếp.
    cn2 = mt["tao"]()
    cn2.phuc_hoi()
    assert _hien(mt) in ("1.0.0", "1.1.0")
    if cn2.nk.doc()["trang_thai"] != mu.ACTIVE:
        assert cn2.chuan_bi().trang_thai == mu.STAGED
        assert cn2.ap_dung().trang_thai == mu.ACTIVE
    assert _hien(mt) == "1.1.0" and cn2.last_good()["phien_ban"] == "1.1.0"
    assert mt["gia"].phien_ban_db() == 4
    assert mt["gia"].ds_viec() == [(da_gui, "SENT")]                  # không phát lại / không reset
    assert not cn2.cach_ly()
    assert not [x for x in os.listdir(mt["cd"].releases) if ".tmp-" in x]


def test_mat_dien_khi_ghi_con_tro_giu_ban_cu_nguyen_ven(mt, monkeypatch):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.STAGED
    goc = os.replace

    def replace_chet(a, b):
        if b.endswith("current.json"):
            raise mu.MatDien("trước khi replace")
        return goc(a, b)

    monkeypatch.setattr(os, "replace", replace_chet)
    with pytest.raises(mu.MatDien):
        cn.ap_dung()
    monkeypatch.setattr(os, "replace", goc)
    assert _hien(mt) == "1.0.0"
    cn2 = mt["tao"]()
    assert cn2.phuc_hoi() == mu.STAGED
    assert cn2.ap_dung().trang_thai == mu.ACTIVE and _hien(mt) == "1.1.0"


# ---------------------------------------------------------------- nguồn GitHub (HTTP giả, không mạng)

class _Rep:
    def __init__(self, url, data=b"", js=None, history=()):
        self.url, self._data, self._js, self.history = url, data, js, list(history)

    def raise_for_status(self):
        pass

    def json(self):
        return self._js

    def iter_content(self, n):
        yield self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _HttpGia:
    def __init__(self, ds, tai):
        self.ds, self.tai, self.goi = ds, tai, []

    def get(self, url, **kw):
        self.goi.append((url, kw.get("timeout")))
        assert kw.get("timeout"), "mọi request phải có timeout"
        if "api.github.com" in url:
            return _Rep(url, js=self.ds)
        return self.tai(url)


def test_nguon_github_doc_co_draft_prerelease_va_chi_tai_tu_host_duoc_phep(tmp_path):
    ds = [{"tag_name": "stable-1.0.0", "draft": False, "prerelease": False,
           "assets": [{"name": "manifest.json",
                       "browser_download_url": "https://github.com/o/r/releases/download/x/manifest.json"},
                      {"name": "manifest.json.sig",
                       "browser_download_url": "https://evil.example.com/manifest.json.sig"}]},
          {"tag_name": "stable-2.0.0", "draft": True, "prerelease": False, "assets": []}]
    http = _HttpGia(ds, lambda url: _Rep(
        url, data=b"{}", history=[_Rep("https://github.com/o/r/releases/download/x/manifest.json")]))
    ng = mu.NguonGitHub("o/r", http=http)
    ban = ng.ds()
    assert [(b.tag, b.draft) for b in ban] == [("stable-1.0.0", False), ("stable-2.0.0", True)]
    ng.tai(ban[0], "manifest.json", str(tmp_path / "m.json"), 1000)
    with pytest.raises(mu.TuChoiGoi):
        ng.tai(ban[0], "manifest.json.sig", str(tmp_path / "s.json"), 1000)
    redirect_xau = _HttpGia(ds, lambda url: _Rep("https://evil.example.com/x", data=b"{}",
                                                 history=[_Rep(url)]))
    with pytest.raises(mu.TuChoiGoi):
        mu.NguonGitHub("o/r", http=redirect_xau).tai(ban[0], "manifest.json",
                                                     str(tmp_path / "m2.json"), 1000)


def test_nguon_github_gioi_han_kich_thuoc_khi_tai(tmp_path):
    ds = [{"tag_name": "stable-1.0.0", "draft": False, "prerelease": False, "assets": [
        {"name": "goi.zip", "browser_download_url": "https://github.com/o/r/releases/download/x/goi.zip"}]}]
    http = _HttpGia(ds, lambda url: _Rep(url, data=b"x" * 5000))
    ng = mu.NguonGitHub("o/r", http=http)
    with pytest.raises(mu.TuChoiGoi):
        ng.tai(ng.ds()[0], "goi.zip", str(tmp_path / "g.zip"), 1000)


# ---------------------------------------------------------------- dọn bản cũ

def test_don_ban_cu_khong_xoa_ban_dang_dung_hay_last_good(mt):
    for pb in ("1.0.0", "1.1.0", "1.2.0"):
        _cai(mt, pb)
    shutil.copy(mt["cd"].file_trang_thai("current.json"), mt["cd"].file_trang_thai("x.json"))
    lg = mu.doc_json(mt["cd"].file_trang_thai("current.json"))
    lg = {**lg, "phien_ban": "1.1.0", "release": mt["cd"].release_dir("1.1.0")}
    mu.ghi_json_nguyen_tu(mt["cd"].file_trang_thai("last_good.json"), lg)
    da_xoa = mu.don_ban_cu(mt["cd"], giu=1)
    assert da_xoa == [mt["cd"].release_dir("1.0.0")]
    assert os.path.isdir(mt["cd"].release_dir("1.1.0")) and os.path.isdir(mt["cd"].release_dir("1.2.0"))


# ---------------------------------------------------------------- người dùng hoãn

def test_nguoi_dung_hoan_thi_khong_ap_dung_toi_han(mt):
    _cai(mt, "1.0.0")
    phat_hanh(mt["nguon"], "1.1.0", mt["khoa"])
    cn = mt["tao"]()
    assert cn.chuan_bi().trang_thai == mu.STAGED            # tải/stage vẫn được làm trước
    mu.dat_hoan(mt["cd"].goc, 24)
    kq = cn.ap_dung()
    assert kq.trang_thai == mu.STAGED and "hoãn" in kq.thong_diep and _hien(mt) == "1.0.0"
    mu.bo_hoan(mt["cd"].goc)
    assert cn.ap_dung().trang_thai == mu.ACTIVE and _hien(mt) == "1.1.0"


@pytest.mark.parametrize("ten", ["TimClipPro/CON.txt", "TimClipPro/ten.  ", "TimClipPro/a?b.txt",
                                 "../ngoai.txt", "C:/o_dia.txt", "/tuyet_doi.txt"])
def test_giai_nen_tu_choi_ten_nguy_hiem_truoc_khi_ghi(tmp_path, ten):
    """Lớp kiểm TÊN chặn trước khi ghi byte nào (không chờ lớp đối chiếu danh sách đã ký)."""
    zi = zipfile.ZipInfo("x")
    zi.filename = ten
    p = tmp_path / "g.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("TimClipPro/app.py", b"x")
        z.writestr(zi, b"doc hai")
    with pytest.raises(mu.TuChoiGoi) as e:
        mu.giai_nen_an_toan(str(p), str(tmp_path / "dich"))
    assert e.value.ma == "zip_slip" and not (tmp_path / "dich").exists()
