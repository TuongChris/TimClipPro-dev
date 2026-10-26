# -*- coding: utf-8 -*-
"""Hồi quy audit B-3 (P2): ``_chan_nhom`` gom nhóm theo bảng/mã tab/khoá/lược đồ nhưng KHÔNG theo revision hồ sơ.

Kịch bản (synthetic, ngoại tuyến): hồ sơ P ghim mã tab 101, tên đối chiếu «KQ» (revision 1). Trên Google tab 101 đã
đổi tên thành «KQ2»; người dùng sửa ĐÚNG hồ sơ (tên «KQ2», revision 2, cùng mã 101) và lô mới xếp J3 (rev 2). Còn
việc rev 1 chờ trong cùng vòng → người gửi xử lý rev 1 trước, chặn «khác tên đối chiếu «KQ»» và ``_chan_nhom`` chặn
luôn J3 — dù J3 (tên «KQ2» khớp tab 101) gửi được.

Hành vi ĐÚNG: lỗi tên đối chiếu là lỗi của REVISION 1 (nhãn của revision đó), không phải của mọi việc cùng
bảng + mã tab; J3 (rev 2) phải được gửi (hoặc ít nhất không mang lý do trỏ về «KQ» của revision khác).
"""
import lich_su
import outbox as ob
import pytest
import sheet_destinations as sd
from outbox_gia import CongNhieuTab, khoa_gia

ID_A = "1" + "a" * 43
IID = "c" * 32
HEADER = [f"Cột {i}" for i in range(1, 35)]


class DongHo:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture()
def mt(tmp_path):
    db = str(tmp_path / "data" / "lichsu.db")
    (tmp_path / "data").mkdir()
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    return {"db": db, "data": str(tmp_path / "data")}


def _xep(mt, dich_id, job_id, tao_luc):
    y = sd.chot_y_dinh(mt["db"], dich_id, installation_id=IID, lo_id="lo")
    with sd.ket_noi(mt["db"], ghi=True) as con:
        vid = ob.them_viec(con, y, job_id=job_id, chinh_sach="v2", header=HEADER,
                           rows=[[f"dòng {job_id}"] + [""] * 33], nguon=ob.NGUON_AUTO, khoa_rieng="")
        # Thứ tự xếp hàng tất định (việc cũ trước) — không phụ thuộc độ phân giải time.time().
        con.execute("UPDATE hang_doi_gui SET tao_luc=? WHERE id=?", (float(tao_luc), vid))
    return vid


def _ng(mt, cong):
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, moi_vong=20, dong_ho=DongHo())
    assert ng.nhan_quyen()
    return ng


def _ho_so_rev1(mt):
    return sd.tao_dich(mt["db"], ten="P", spreadsheet_id=ID_A, worksheet_id=101, worksheet_ten="KQ",
                       schema_id=sd.SCHEMA_NGANG, xac_thuc_ref="mac_dinh", workspace="mac_dinh")


def test_viec_rev2_dung_ten_khong_bi_chan_boi_viec_rev1_lech_ten(mt):
    d = _ho_so_rev1(mt)
    j1 = _xep(mt, d.id, 1, 1.0)                        # rev 1 (tên đối chiếu «KQ»)
    j2 = _xep(mt, d.id, 2, 2.0)
    d2 = sd.sua_dich(mt["db"], d.id, worksheet_ten="KQ2")   # người dùng sửa đúng: rev 2, cùng mã 101
    assert d2.phien_ban == 2
    j3 = _xep(mt, d.id, 3, 3.0)                        # rev 2 (tên «KQ2»)
    assert ob.lay_viec(mt["db"], j1).dich.phien_ban == 1
    assert ob.lay_viec(mt["db"], j3).dich.phien_ban == 2

    cong = CongNhieuTab({101: "KQ2"})                  # tab 101 trên Google đã đổi tên thành «KQ2»
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    ng.chay_mot_vong()

    v1, v2, v3 = (ob.lay_viec(mt["db"], j) for j in (j1, j2, j3))
    # Việc rev 1 bị chặn là đúng (nhãn của revision 1 lệch tab thật).
    assert v1.trang_thai == ob.BLOCKED_CONFIG and "«KQ»" in v1.loi
    # Việc chờ CÙNG revision 1 vẫn bị chặn theo nhóm (cùng nhãn lệch) — phạm vi chặn thu về revision, không bỏ.
    assert v2.trang_thai == ob.BLOCKED_CONFIG and "«KQ»" in v2.loi
    # Việc rev 2 có nhãn KHỚP tab 101 → phải gửi được, không bị kéo theo lỗi của revision khác.
    assert v3.trang_thai == ob.SENT, (
        f"J3 (rev 2, tên «KQ2» khớp tab 101) bị {v3.trang_thai}: {v3.loi!r}; ghi={cong.ghi}; J2={v2.trang_thai}")
    assert [g for g, _ in cong.ghi] == [101]


def test_thu_lai_viec_rev1_khong_chan_lai_viec_rev2(mt):
    d = _ho_so_rev1(mt)
    j1 = _xep(mt, d.id, 1, 1.0)
    cong = CongNhieuTab({101: "KQ2"})
    ng = _ng(mt, cong)
    ng.chay_mot_vong()
    assert ob.lay_viec(mt["db"], j1).trang_thai == ob.BLOCKED_CONFIG   # rev 1 chặn: đúng
    sd.sua_dich(mt["db"], d.id, worksheet_ten="KQ2")                    # sửa hồ sơ đúng → rev 2
    j3 = _xep(mt, d.id, 3, 3.0)
    ob.thu_lai(mt["db"], j1)                                            # người dùng bấm «Thử gửi lại» việc cũ
    ng.chay_mot_vong()
    ng.chay_mot_vong()
    v3 = ob.lay_viec(mt["db"], j3)
    assert v3.trang_thai == ob.SENT, f"J3 (rev 2) bị {v3.trang_thai}: {v3.loi!r}; ghi={cong.ghi}"


def test_doi_chung_viec_rev2_mot_minh_thi_gui_duoc(mt):
    """Đối chứng (phải XANH): không còn việc rev 1 chờ → J3 rev 2 gửi được vào tab 101. Chứng tỏ hai test trên đỏ
    chỉ vì ``_chan_nhom`` kéo J3 theo lỗi của revision 1, không phải do dựng dữ liệu sai."""
    d = _ho_so_rev1(mt)
    sd.sua_dich(mt["db"], d.id, worksheet_ten="KQ2")
    j3 = _xep(mt, d.id, 3, 3.0)
    cong = CongNhieuTab({101: "KQ2"})
    _ng(mt, cong).chay_mot_vong()
    assert ob.lay_viec(mt["db"], j3).trang_thai == ob.SENT and [g for g, _ in cong.ghi] == [101]
