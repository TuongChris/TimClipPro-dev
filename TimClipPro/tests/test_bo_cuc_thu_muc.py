# -*- coding: utf-8 -*-
"""MR-P1-01 (audit độc lập f4d3cb7, 08/10/2026): state root LỒNG trong vùng bộ cập nhật được quyền xoá.

Tái hiện của audit: bootstrap chấp nhận ``state = <cài đặt>/staging/state`` (chỉ chặn hai root BẰNG nhau);
``CapNhat.phuc_hoi()`` (nhật ký CHECKED) hoặc ``chuan_bi()`` → ``ap_dung()`` gọi ``_don_staging`` →
``shutil.rmtree(<cài đặt>/staging)`` → MẤT ``lichsu.db`` + ``installation.json``.

Nay: thư mục cài đặt và state root phải TÁCH BIỆT (không bằng, không cha/con) — so cả dạng CHỮ (abspath, không
phân biệt hoa/thường trên Windows) lẫn dạng THẬT (realpath: junction/symlink). Kiểm ở bootstrap (trước khi ghi
byte nào), ở MỌI nơi dựng ``CaiDat`` (launcher, giao diện, bootstrap) và NGAY TRƯỚC mỗi lần updater xoá cây thư
mục. Cấu hình cũ không an toàn: dừng có thông báo, không tự di chuyển hay xoá gì. Cùng lớp lỗi: thư mục nguồn phát
hành (``--nguon-thu-muc``) nằm trong vùng updater.
"""
import json
import os
import sqlite3
import sys

import pytest

import bootstrap as bs
import launcher
import maintenance_gate as mg
import managed_update as mu
import runtime_paths as rp
from cap_nhat_gia import KhoaThu, MoiTruongGia, phat_hanh
from test_bootstrap import KIT

VUNG_UPDATER = ("staging", "releases", "environments", "update_state")


def _db_tong_hop(state) -> str:
    """Lịch sử TỔNG HỢP (một bản ghi) trong state root — thứ updater tuyệt đối không được xoá."""
    p = os.path.join(str(state), "data", "lichsu.db")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE IF NOT EXISTS ban_ghi(id INTEGER PRIMARY KEY, ghi_chu TEXT)")
    con.execute("INSERT INTO ban_ghi(ghi_chu) VALUES ('du lieu tong hop')")
    con.commit()
    con.close()
    return p


def _junction(dich, lien_ket) -> None:
    import _winapi

    if not hasattr(_winapi, "CreateJunction"):
        pytest.skip("Python này không tạo được junction")
    _winapi.CreateJunction(str(dich), str(lien_ket))


def _anh(tmp):
    return sorted(str(p) for p in tmp.rglob("*"))


# ---------------------------------------------------------------- kiểm bố cục (hàm thuần)

@pytest.mark.parametrize("con", ["", *VUNG_UPDATER, *(f"{v}/state" for v in VUNG_UPDATER), "state",
                                 "launcher/state", "a/b/state"])
def test_state_bang_hoac_nam_trong_thu_muc_cai_dat_bi_tu_choi(tmp_path, con):
    goc = tmp_path / "TimClipPro"
    state = goc / con if con else goc
    assert rp.ly_do_bo_cuc(str(goc), str(state))


def test_thu_muc_cai_dat_nam_trong_state_bi_tu_choi(tmp_path):
    assert rp.ly_do_bo_cuc(str(tmp_path / "State" / "TimClipPro"), str(tmp_path / "State"))


def test_hai_thu_muc_ngang_hang_hop_le_ke_ca_trung_tien_to_chuoi(tmp_path):
    goc, state = tmp_path / "TimClipPro", tmp_path / "TimClipPro_State"   # tiền tố CHUỖI, không phải cha/con
    assert rp.ly_do_bo_cuc(str(goc), str(state)) == ""
    assert rp.ly_do_bo_cuc(str(state), str(goc)) == ""
    assert rp.ly_do_bo_cuc(str(tmp_path / "pc2" / "Cai Dat"), str(tmp_path / "pc2" / "State")) == ""


@pytest.mark.skipif(os.name != "nt", reason="Windows: đường dẫn không phân biệt hoa/thường")
def test_khac_hoa_thuong_van_la_long_nhau(tmp_path):
    goc = tmp_path / "TimClipPro"
    assert rp.ly_do_bo_cuc(str(goc), str(goc).upper() + "\\STAGING\\STATE")


@pytest.mark.skipif(os.name != "nt", reason="junction là của Windows")
def test_alias_qua_junction_tro_vao_staging_bi_tu_choi(tmp_path):
    goc = tmp_path / "TimClipPro"
    (goc / "staging").mkdir(parents=True)
    _junction(goc / "staging", tmp_path / "Alias")
    state = tmp_path / "Alias" / "state"           # DẠNG CHỮ ngoài cài đặt — THẬT nằm trong staging
    assert os.path.commonpath([str(goc).lower(), str(state).lower()]) != str(goc).lower()
    assert rp.ly_do_bo_cuc(str(goc), str(state))


@pytest.mark.skipif(os.name != "nt", reason="junction là của Windows")
def test_junction_trong_staging_tro_ra_ngoai_van_bi_tu_choi(tmp_path):
    goc = tmp_path / "TimClipPro"
    (goc / "staging").mkdir(parents=True)
    (tmp_path / "Ngoai").mkdir()
    _junction(tmp_path / "Ngoai", goc / "staging" / "state")
    # THẬT nằm ngoài, nhưng đường dẫn khai báo nằm trong staging: dọn staging gỡ junction → state "biến mất".
    assert rp.ly_do_bo_cuc(str(goc), str(goc / "staging" / "state"))


# ---------------------------------------------------------------- bootstrap: chặn TRƯỚC khi ghi

@pytest.fixture()
def bo(tmp_path):
    khoa = KhoaThu()
    tin_cay = khoa.ghi_tin_cay(str(tmp_path / "kit" / "trusted_keys.json"))
    nguon = tmp_path / "nguon"
    nguon.mkdir()
    return {"khoa": khoa, "tin_cay": tin_cay, "nguon": str(nguon), "tmp": tmp_path}


def _tham_toi_thieu(bo, **kw):
    """Tham số bootstrap KHÔNG kèm môi trường giả (môi trường giả tự tạo state/data — làm bẩn phép so ảnh)."""
    tham = dict(kit_dir=KIT, python_goc=sys.executable, tin_cay=bo["tin_cay"],
                nguon={"loai": "thu_muc", "duong_dan": bo["nguon"]}, py_launcher=sys.executable)
    tham.update(kw)
    return tham


@pytest.mark.parametrize("con", ["staging/state", "staging", "releases/9.9.9", "environments/py312-x",
                                 "update_state/s", "State"])
def test_bootstrap_tu_choi_state_long_trong_cai_dat_truoc_khi_ghi(bo, con):
    goc = bo["tmp"] / "pc2" / "TimClipPro"
    state = goc / con
    truoc = _anh(bo["tmp"])
    with pytest.raises(bs.LoiBootstrap, match="TÁCH BIỆT"):
        bs.kiem_truoc(str(goc), str(state), sys.executable)
    with pytest.raises(bs.LoiBootstrap, match="TÁCH BIỆT"):
        bs.bootstrap(str(goc), str(state), cai_ban_dau=False, **_tham_toi_thieu(bo))
    assert _anh(bo["tmp"]) == truoc                                    # không ghi byte nào


def test_bootstrap_tu_choi_cai_dat_nam_trong_state(bo):
    state = bo["tmp"] / "pc2" / "State"
    truoc = _anh(bo["tmp"])
    with pytest.raises(bs.LoiBootstrap, match="TÁCH BIỆT"):
        bs.bootstrap(str(state / "TimClipPro"), str(state), cai_ban_dau=False, **_tham_toi_thieu(bo))
    assert _anh(bo["tmp"]) == truoc


def test_bootstrap_tu_choi_nguon_phat_hanh_trong_vung_updater_truoc_khi_ghi(bo):
    goc, state = bo["tmp"] / "pc2" / "TimClipPro", bo["tmp"] / "pc2" / "State"
    nguon = goc / "staging" / "phat_hanh"
    truoc = _anh(bo["tmp"])
    with pytest.raises(bs.LoiBootstrap, match="nguồn phát hành"):
        bs.bootstrap(str(goc), str(state), cai_ban_dau=False,
                     **_tham_toi_thieu(bo, nguon={"loai": "thu_muc", "duong_dan": str(nguon)}))
    assert _anh(bo["tmp"]) == truoc


def test_bootstrap_ngang_hang_van_cai_duoc(bo):
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    goc, state = bo["tmp"] / "pc2" / "TimClipPro", bo["tmp"] / "pc2" / "TimClipPro_State"
    gia = MoiTruongGia(str(state))
    kq = bs.bootstrap(str(goc), str(state), **_tham_toi_thieu(
        bo, tao_moi_truong=gia.tao_moi_truong, kiem_suc_khoe=gia.kiem_suc_khoe, di_chuyen=gia.di_chuyen,
        sao_luu=gia.sao_luu, phien_ban_db=gia.phien_ban_db))
    assert kq["cai_dat"]["trang_thai"] == mu.ACTIVE, kq["cai_dat"]
    assert os.path.isfile(os.path.join(str(state), "data", "lichsu.db"))


# ---------------------------------------------------------------- tái hiện ĐÚNG hai kịch bản của audit

def _cap_nhat(cd, nguon, khoa, gia, **sua):
    tham = dict(nguon=mu.NguonThuMuc(str(nguon)),
                khoa_tin_cay=mu.doc_khoa_tin_cay(khoa.ghi_tin_cay(os.path.join(cd.goc, "launcher",
                                                                               "trusted_keys.json"))),
                cong=mg.CongBaoTri(cd.data_dir), tao_moi_truong=gia.tao_moi_truong,
                kiem_suc_khoe=gia.kiem_suc_khoe, di_chuyen=gia.di_chuyen, sao_luu=gia.sao_luu,
                phien_ban_db=gia.phien_ban_db, han_cho_ranh_s=0.3, chu_ky_cho_s=0.05)
    tham.update(sua)
    return mu.CapNhat(cd, **tham)


def test_tai_hien_audit_chuan_bi_roi_ap_dung_khong_xoa_state(bo):
    """Audit, tái hiện 2: gói ký thật (khoá thử) + nguồn thư mục; ``chuan_bi()`` STAGED rồi ``ap_dung()`` LOI và
    lichsu.db + installation.json đã mất. Nay bố cục lồng nhau bị từ chối ngay khi dựng ``CaiDat``."""
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    goc = bo["tmp"] / "TimClipPro"
    state = goc / "staging" / "state"
    gia = MoiTruongGia(str(state))                  # tạo state/data/lichsu.db (SQLite thật)
    rp.tao_dinh_danh(str(state), installation_root=str(goc))
    db = os.path.join(str(state), "data", "lichsu.db")
    try:
        cd = mu.CaiDat(goc=str(goc), state_root=str(state))
    except mu.LoiCapNhat as e:
        assert e.ma == "bo_cuc"
        cd = None
    if cd is not None:                              # mã CŨ nhận bố cục này — chạy đúng đường public của audit
        cn = _cap_nhat(cd, bo["nguon"], bo["khoa"], gia)
        cn.chuan_bi()
        cn.ap_dung()
    assert os.path.isfile(db), "bộ cập nhật đã XOÁ lịch sử nằm trong state root"
    assert os.path.isfile(os.path.join(str(state), rp.TEN_DINH_DANH))
    assert cd is None, "bố cục state root lồng trong staging phải bị từ chối khi dựng CaiDat"


@pytest.fixture()
def lan_truoc(bo):
    """Cài đặt bootstrap ĐÚNG (ngang hàng), sau đó launcher.json bị SỬA tay thành state root nằm trong staging
    — có định danh + lịch sử tổng hợp ở đó, nhật ký cập nhật dừng ở CHECKED (audit, tái hiện 1)."""
    goc, state_ok = bo["tmp"] / "pc2" / "TimClipPro", bo["tmp"] / "pc2" / "State"
    bs.bootstrap(str(goc), str(state_ok), cai_ban_dau=False, **_tham_toi_thieu(bo))
    state = goc / "staging" / "state"
    state.mkdir(parents=True)
    with open(os.path.join(str(state_ok), rp.TEN_DINH_DANH), encoding="utf-8") as f:
        dd = f.read()
    (state / rp.TEN_DINH_DANH).write_text(dd, encoding="utf-8")
    db = _db_tong_hop(state)
    p = goc / "launcher" / "launcher.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg["state_root"] = str(state)
    p.write_text(json.dumps(cfg), encoding="utf-8")
    mu.ghi_json_nguyen_tu(str(goc / "update_state" / "journal.json"),
                          {"trang_thai": mu.CHECKED, "lich_su": []})
    return {"goc": str(goc), "state": str(state), "db": db}


@pytest.mark.parametrize("lenh", [["update", "recover"], ["update", "prepare"], ["update", "apply"],
                                  ["update", "status"], ["app"], ["watch"], ["cli", "dich"]])
def test_launcher_json_bi_sua_thanh_long_nhau_thi_dung_khong_xoa(lan_truoc, lenh, capsys):
    goi = []
    assert launcher.main(lenh, goc=lan_truoc["goc"], chay=lambda *a, **k: goi.append(a) or 0) == 1
    assert goi == []                                                   # không mở app/Watch/CLI nào
    err = capsys.readouterr().err
    assert "Bố cục thư mục" in err
    assert "mở bản đang kích hoạt" not in err                          # không hứa mở app rồi lại dừng
    assert os.path.isfile(lan_truoc["db"])
    assert os.path.isfile(os.path.join(lan_truoc["state"], rp.TEN_DINH_DANH))


def test_doctor_bao_loi_bo_cuc_khong_sap(lan_truoc):
    ket = launcher.doctor(lan_truoc["goc"])
    assert any(muc == launcher.LOI and ten == "Bố cục thư mục" for muc, ten, _ in ket), ket
    assert os.path.isfile(lan_truoc["db"])


# ---------------------------------------------------------------- lớp cuối: ngay trước khi xoá

@pytest.fixture()
def cn_hop_le(bo):
    goc, state = bo["tmp"] / "TimClipPro", bo["tmp"] / "State"
    gia = MoiTruongGia(str(state))
    cd = mu.CaiDat(goc=str(goc), state_root=str(state))
    return {"cd": cd, "cn": _cap_nhat(cd, bo["nguon"], bo["khoa"], gia), "goc": goc, "gia": gia}


def _lot_vao(cd, state) -> None:
    """Giả lập state root "lọt" vào vùng updater SAU khi đã dựng (junction đổi đích, đối tượng bị sửa…)."""
    object.__setattr__(cd, "state_root", str(state))


def test_lop_cuoi_khoi_phuc_khong_xoa_staging_chua_state(cn_hop_le):
    cd, cn, goc = cn_hop_le["cd"], cn_hop_le["cn"], cn_hop_le["goc"]
    state = goc / "staging" / "state"
    db = _db_tong_hop(state)
    mu.ghi_json_nguyen_tu(cd.file_trang_thai("journal.json"), {"trang_thai": mu.CHECKED, "lich_su": []})
    _lot_vao(cd, state)
    with pytest.raises(mu.LoiCapNhat) as e:
        cn.phuc_hoi()
    assert e.value.ma == "bo_cuc" and os.path.isfile(db)


def test_lop_cuoi_chuan_bi_khong_xoa_staging_chua_state(cn_hop_le, bo):
    cd, cn, goc = cn_hop_le["cd"], cn_hop_le["cn"], cn_hop_le["goc"]
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    state = goc / "staging" / "state"
    db = _db_tong_hop(state)
    _lot_vao(cd, state)
    kq = cn.chuan_bi()
    assert kq.trang_thai == mu.LOI and "Bố cục thư mục" in kq.thong_diep
    assert os.path.isfile(db)


def test_lop_cuoi_ap_dung_sau_staged_khong_xoa_staging_chua_state(cn_hop_le, bo):
    """Đúng đường của audit: bản mới đã STAGED; lần ``ap_dung`` kế (khôi phục → dọn staging) mới là lúc xoá."""
    cd, cn, goc = cn_hop_le["cd"], cn_hop_le["cn"], cn_hop_le["goc"]
    phat_hanh(bo["nguon"], "1.0.0", bo["khoa"])
    assert cn.chuan_bi().trang_thai == mu.STAGED
    state = goc / "staging" / "state"
    db = _db_tong_hop(state)
    _lot_vao(cd, state)
    kq = cn.ap_dung()
    assert kq.trang_thai == mu.LOI and "Bố cục thư mục" in kq.thong_diep
    assert os.path.isfile(db)


@pytest.mark.parametrize("con", ["staging/state", "releases/9.9.9.tmp-1", "staging/x/y/state"])
def test_chot_xoa_tu_choi_ngay_tai_cho_xoa(cn_hop_le, con):
    """Chốt NGAY TRƯỚC rmtree (không dựa vào lần kiểm đầu lượt): dọn staging / bản dở dang đều đi qua nó."""
    cd, cn, goc = cn_hop_le["cd"], cn_hop_le["cn"], cn_hop_le["goc"]
    state = goc / con
    db = _db_tong_hop(state)
    (goc / "releases").mkdir(exist_ok=True)
    (goc / "releases" / "1.0.0.tmp-abc").mkdir(exist_ok=True)
    _lot_vao(cd, state)
    with pytest.raises(mu.LoiCapNhat) as e:
        cn._don_staging()
    assert e.value.ma == "bo_cuc" and os.path.isfile(db)


def test_chot_xoa_khong_xoa_thu_muc_nguon_phat_hanh(cn_hop_le, bo):
    """Thư mục nguồn phát hành "lọt" vào staging sau khi dựng bộ cập nhật: lần dọn staging phải dừng, không xoá."""
    cn, goc = cn_hop_le["cn"], cn_hop_le["goc"]
    nguon = goc / "staging" / "phat_hanh"
    goi = phat_hanh(str(nguon), "1.0.0", bo["khoa"])
    cn._bao_ve = (str(nguon),)
    with pytest.raises(mu.LoiCapNhat) as e:
        cn._don_staging()
    assert e.value.ma == "bo_cuc" and os.path.isdir(goi)


@pytest.mark.parametrize("dich", ["launcher", "", "../State", "staging/../launcher"])
def test_chot_xoa_chi_cho_vung_updater(cn_hop_le, dich):
    cd, goc = cn_hop_le["cd"], cn_hop_le["goc"]
    with pytest.raises(mu.LoiCapNhat):
        cd.kiem_xoa(os.path.normpath(os.path.join(str(goc), dich)))


def test_moi_rmtree_cua_updater_deu_qua_chot():
    """Không lần xoá cây thư mục nào của updater lách được chốt bố cục: ``shutil.rmtree`` chỉ xuất hiện trong
    ``_xoa_cay`` (sau ``kiem_xoa``), ``don_ban_cu`` (ngay sau ``kiem_xoa``) và ``giai_nen_an_toan`` (chỉ xoá thư mục
    chính nó vừa tạo — chưa tồn tại trước đó)."""
    import ast
    import inspect

    cay = ast.parse(inspect.getsource(mu))
    noi = {}
    for ham in ast.walk(cay):
        if isinstance(ham, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(ham):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "rmtree"
                        and isinstance(n.func.value, ast.Name) and n.func.value.id == "shutil"):
                    noi[ham.name] = noi.get(ham.name, 0) + 1
    assert noi == {"_xoa_cay": 1, "don_ban_cu": 1, "giai_nen_an_toan": 1}, noi
    nguon = inspect.getsource(mu.don_ban_cu)
    assert nguon.index("kiem_xoa(") < nguon.index("shutil.rmtree(")
    nguon = inspect.getsource(mu.CapNhat._xoa_cay)
    assert nguon.index("kiem_xoa(") < nguon.index("shutil.rmtree(")


def test_lop_cuoi_don_ban_cu_khong_xoa_release_chua_state(cn_hop_le):
    cd, goc = cn_hop_le["cd"], cn_hop_le["goc"]
    for pb in ("0.0.1", "0.0.2", "0.0.3", "0.0.4"):
        (goc / "releases" / pb).mkdir(parents=True)
    db = _db_tong_hop(goc / "releases" / "0.0.1")       # bản CŨ NHẤT — đúng thứ dọn bản cũ sẽ xoá
    _lot_vao(cd, goc / "releases" / "0.0.1")
    with pytest.raises(mu.LoiCapNhat) as e:
        mu.don_ban_cu(cd, giu=2)
    assert e.value.ma == "bo_cuc" and os.path.isfile(db)


def test_nguon_phat_hanh_trong_vung_updater_bi_tu_choi_khi_dung_bo_cap_nhat(cn_hop_le, bo):
    cd = cn_hop_le["cd"]
    nguon = cn_hop_le["goc"] / "staging" / "phat_hanh"
    phat_hanh(str(nguon), "1.0.0", bo["khoa"])
    with pytest.raises(mu.LoiCapNhat) as e:
        _cap_nhat(cd, nguon, bo["khoa"], cn_hop_le["gia"])
    assert e.value.ma == "bo_cuc"
    assert os.path.isdir(nguon)


def test_bo_cuc_hop_le_van_don_staging_binh_thuong(cn_hop_le):
    cd, cn = cn_hop_le["cd"], cn_hop_le["cn"]
    rac = os.path.join(cd.staging, "do-dang")
    os.makedirs(rac)
    mu.ghi_json_nguyen_tu(cd.file_trang_thai("journal.json"), {"trang_thai": mu.CHECKED, "lich_su": []})
    assert cn.phuc_hoi() == mu.CHECKED
    assert not os.path.exists(cd.staging)


# ---------------------------------------------------------------- giao diện «Phiên bản và cập nhật»

def test_ui_bo_cuc_khong_an_toan_bao_loi_khong_sap(tmp_path, monkeypatch):
    from test_ui_cap_nhat import _chay, _chu

    goc = tmp_path / "state" / "TimClipPro"                   # thư mục cài đặt nằm TRONG state root
    at = _chay(tmp_path, monkeypatch, {"TIMCLIP_RUNTIME_MODE": "managed",
                                       "TIMCLIP_INSTALLATION_ROOT": str(goc), "TIMCLIP_RELEASE": "1.0.0"})
    assert not at.exception
    assert "Bố cục thư mục" in _chu(at)
