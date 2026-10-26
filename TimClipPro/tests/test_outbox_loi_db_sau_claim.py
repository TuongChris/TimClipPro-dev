# -*- coding: utf-8 -*-
"""Audit B-1 (P2): ngoại lệ SAU khi claim (DB bị khoá quá hạn chờ / đĩa đầy ở lần ghi trạng thái cuối) để lại
việc gửi ở CLAIMED/SENDING suốt đời tiến trình người gửi.

Tái hiện TỔNG HỢP, không mạng: transport giả ``outbox_gia.CongGia``, khoá dịch vụ GIẢ, DB tạm. Khoá ghi SQLite
được giữ THẬT bởi một kết nối khác (như app/Watch/sao lưu đang giữ ``BEGIN IMMEDIATE``) đúng lúc người gửi ghi trạng
thái cuối; hạn chờ khoá rút từ 30 s xuống 0,2 s cho test nhanh (cùng đường lỗi ``database is locked``).

Hành vi ĐÚNG mà test khẳng định:
* B — lỗi xảy ra khi CHƯA phát request (CLAIMED): việc không được kẹt trong tay một người gửi vẫn đang sống — khi
  DB hết khoá, chính người gửi đó phải gửi được việc (vòng sau), hoặc ít nhất người dùng huỷ được (thiết kế §5:
  CLAIMED = chưa dispatch → an toàn quay về PENDING).
* A — Google ĐÃ ghi và biên nhận ĐÃ hợp lệ, chỉ lần ghi SENT lỗi: khi DB hết khoá việc phải thành SENT; khởi
  động lại không được biến nó thành KHÔNG RÕ («tiến trình trước đã dừng») và mở nút «Gửi lại» gây trùng dòng.
  (Lưu ý: docs/MANAGED_RUNTIME_DESIGN.md §9 ghi nhận phần «kẹt SENDING tới lần giành quyền kế» là giới hạn đã
  biết; test A mô tả hậu quả cho người dùng.)
"""
import sqlite3

import pytest

import lich_su
import outbox as ob
import sheet_destinations as sd
from outbox_gia import CongGia, khoa_gia

ID_A = "1" + "a" * 43
IID = "c" * 32
HEADER = [f"Cột {i}" for i in range(1, 35)]


class DongHo:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture()
def mt(tmp_path, monkeypatch):
    monkeypatch.setattr(sd, "THOI_GIAN_CHO_KHOA_S", 0.2)     # 30 s → 0,2 s: cùng lỗi «database is locked»
    db = str(tmp_path / "data" / "lichsu.db")
    (tmp_path / "data").mkdir()
    lich_su.dam_bao_luoc_do(db)
    sd.dinh_danh_may(db, mong_doi=IID)
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    a = sd.tao_dich(db, ten="Bảng A", spreadsheet_id=ID_A, worksheet_id=0,
                    worksheet_ten="KetQuaQuet", schema_id=sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    y = sd.chot_y_dinh(db, a.id, installation_id=IID, lo_id="lo1")
    with sd.ket_noi(db, ghi=True) as con:
        vid = ob.them_viec(con, y, job_id=1, chinh_sach="v2", header=HEADER,
                           rows=[["dòng 1"] + [""] * 33])
    return {"db": db, "data": str(tmp_path / "data"), "vid": vid}


class KhoaGhiNgoai:
    """Một kết nối KHÁC giữ khoá ghi của DB (``BEGIN IMMEDIATE``) — như tiến trình khác đang ghi lâu."""

    def __init__(self, db):
        self.db, self.con = db, None

    def giu(self):
        self.con = sqlite3.connect(self.db, isolation_level=None)
        self.con.execute("BEGIN IMMEDIATE")

    def nha(self):
        if self.con is not None:
            self.con.execute("ROLLBACK")
            self.con.close()
            self.con = None


class CongKhoaDbSau(CongGia):
    """Lượt đầu: chạy ``CongGia`` bình thường (lỗi trước dispatch hoặc ghi OK) rồi ngay sau đó tiến trình khác
    giữ khoá ghi DB — đúng lúc người gửi cần ghi trạng thái cuối."""

    def __init__(self, khoa):
        super().__init__()
        self.khoa = khoa
        self.lan = 0

    def gui(self, chot, duong_dan_khoa, header, rows, truoc_khi_gui):
        self.lan += 1
        try:
            return super().gui(chot, duong_dan_khoa, header, rows, truoc_khi_gui)
        finally:
            if self.lan == 1:
                self.khoa.giu()


def _tt(mt):
    return ob.lay_viec(mt["db"], mt["vid"]).trang_thai


def test_B_claimed_khong_ket_khi_ghi_retry_wait_loi_va_nguoi_gui_van_song(mt):
    """Lỗi tạm TRƯỚC dispatch → ghi RETRY_WAIT gặp DB khoá → ngoại lệ thoát vòng. DB hết khoá: cùng người gửi
    (luồng nền vẫn giữ quyền, chỉ log round_failed rồi chạy vòng tiếp) phải gửi được việc."""
    khoa = KhoaGhiNgoai(mt["db"])
    cong = CongKhoaDbSau(khoa)
    cong.ke_hoach = [("truoc", ob.ChuaGui("Mạng chưa kết nối được (thử lại)", tam_thoi=True))]
    dong_ho = DongHo()
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=dong_ho)
    assert ng.nhan_quyen()
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            ng.chay_mot_vong()              # NguoiGuiNen._vong: chỉ log outbox.round_failed, vẫn giữ quyền
    finally:
        khoa.nha()
    assert cong.bang == []                  # chưa ghi gì lên Google
    tt_ngay_sau_loi = _tt(mt)

    # DB hết khoá; luồng nền chạy tiếp các vòng (đồng hồ vượt mọi hạn chờ thử lại).
    dong_ho.t += 24 * 3600
    for _ in range(3):
        ng.chay_mot_vong()
    tt_sau_3_vong = _tt(mt)
    ng.tha_quyen()

    assert tt_sau_3_vong == ob.SENT and len(cong.bang) == 1, (
        f"việc kẹt trong tay người gửi còn sống: ngay sau lỗi={tt_ngay_sau_loi}, sau 3 vòng (DB đã hết khoá)="
        f"{tt_sau_3_vong}, số lần ghi lên Sheet={len(cong.bang)} — chỉ khởi động lại mới gỡ được")


def test_B_claimed_bi_bo_roi_thi_nguoi_dung_huy_duoc(mt):
    """Cùng tình huống: việc CHƯA phát request nhưng người dùng không huỷ được (huy từ chối CLAIMED) tới khi
    khởi động lại app/Watch."""
    khoa = KhoaGhiNgoai(mt["db"])
    cong = CongKhoaDbSau(khoa)
    cong.ke_hoach = [("truoc", ob.ChuaGui("Mạng chưa kết nối được (thử lại)", tam_thoi=True))]
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=DongHo())
    assert ng.nhan_quyen()
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            ng.chay_mot_vong()
    finally:
        khoa.nha()
    tt = _tt(mt)
    loi_huy = ""
    try:
        ob.huy(mt["db"], mt["vid"])
    except ob.LoiHangDoi as e:
        loi_huy = str(e)
    ng.tha_quyen()
    assert cong.bang == []
    assert not loi_huy and _tt(mt) == ob.CANCELLED, (
        f"việc chưa gửi kẹt ở {tt} — huỷ bị từ chối: {loi_huy!r}")


def test_A_da_ghi_bien_nhan_hop_le_nhung_ghi_SENT_loi_thi_khong_thanh_khong_ro_va_khong_gui_trung(mt):
    """Google ĐÃ ghi, biên nhận hợp lệ, ghi SENT gặp DB khoá → việc kẹt SENDING; khởi động lại → UNKNOWN với lời
    «tiến trình trước đã dừng…», «Gửi lại» được mở và ghi trùng dòng."""
    khoa = KhoaGhiNgoai(mt["db"])
    cong = CongKhoaDbSau(khoa)                # lượt 1: "ok" — ghi thật lên Sheet giả rồi DB bị khoá
    dong_ho = DongHo()
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=dong_ho)
    assert ng.nhan_quyen()
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            ng.chay_mot_vong()
    finally:
        khoa.nha()
    assert len(cong.bang) == 1                # Google ĐÃ ghi (biên nhận hợp lệ trước khi _chot(SENT) lỗi)

    dong_ho.t += 24 * 3600
    for _ in range(3):
        ng.chay_mot_vong()
    tt_sau_3_vong = _tt(mt)

    # Khởi động lại app/Watch: người gửi mới giành quyền → phuc_hoi.
    ng.tha_quyen()
    ng2 = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=dong_ho)
    assert ng2.nhan_quyen()
    v = ob.lay_viec(mt["db"], mt["vid"])
    tt_sau_khoi_dong_lai, loi = v.trang_thai, v.loi
    nut_gui_lai_mo = v.trang_thai == ob.UNKNOWN and ob.ly_do_khong_gui_lai(mt["db"], v) == ""
    if nut_gui_lai_mo:                        # người dùng tin lời «tiến trình đã dừng», bấm «Gửi lại»
        ob.gui_lai_co_the_trung(mt["db"], mt["vid"])
        ng2.chay_mot_vong()
    ng2.tha_quyen()

    assert (tt_sau_3_vong == ob.SENT and tt_sau_khoi_dong_lai == ob.SENT and len(cong.bang) == 1), (
        f"lần ghi Google ĐÃ xác nhận bị mất: sau 3 vòng={tt_sau_3_vong}, sau khởi động lại={tt_sau_khoi_dong_lai} "
        f"(lỗi hiển thị: {loi!r}), nút Gửi lại mở={nut_gui_lai_mo}, số dòng trên Sheet={len(cong.bang)}")


def test_loi_doc_ngay_sau_claim_thi_vong_sau_tra_claim_theo_luat_loi_tam(mt, monkeypatch):
    """Lỗi DB ở lần ĐỌC ngay sau claim (chưa có lần chốt nào để nhớ): vòng sau trả claim → RETRY_WAIT có hạn chờ
    (không kẹt CLAIMED, không gửi ngay), hết hạn chờ thì gửi bình thường."""
    goc = ob.lay_viec
    lan = {"n": 0}

    def doc_loi(db, vid):
        lan["n"] += 1
        if lan["n"] == 1:
            raise sqlite3.OperationalError("disk I/O error")
        return goc(db, vid)

    monkeypatch.setattr(ob, "lay_viec", doc_loi)
    cong = CongGia()
    dong_ho = DongHo()
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=dong_ho)
    assert ng.nhan_quyen()
    with pytest.raises(sqlite3.OperationalError):
        ng.chay_mot_vong()
    assert _tt(mt) == ob.CLAIMED and cong.bang == []
    ng.chay_mot_vong()                       # đầu vòng: trả claim; việc chưa tới hạn thử lại
    v = ob.lay_viec(mt["db"], mt["vid"])
    assert v.trang_thai == ob.RETRY_WAIT and "OperationalError" in v.loi and v.thu_lai_sau > dong_ho.t
    assert cong.bang == []
    dong_ho.t += 24 * 3600
    ng.chay_mot_vong()
    ng.tha_quyen()
    assert _tt(mt) == ob.SENT and len(cong.bang) == 1


def test_loi_ngoai_du_kien_sau_dispatch_thi_vong_sau_thanh_khong_ro(mt, monkeypatch):
    """Ngoại lệ ngoài dự kiến SAU khi request đã phát (SENDING) → vòng sau: KHÔNG RÕ (không bao giờ quay về chờ
    gửi, không gửi lại mù)."""
    def bien_nhan_loi(*a, **k):
        raise RuntimeError("lỗi giả")

    monkeypatch.setattr(ob, "kiem_bien_nhan", bien_nhan_loi)
    cong = CongGia()
    ng = ob.NguoiGui(mt["db"], mt["data"], cong, dong_ho=DongHo())
    assert ng.nhan_quyen()
    with pytest.raises(RuntimeError):
        ng.chay_mot_vong()
    assert _tt(mt) == ob.SENDING
    ng.chay_mot_vong()
    ng.tha_quyen()
    v = ob.lay_viec(mt["db"], mt["vid"])
    assert v.trang_thai == ob.UNKNOWN and "RuntimeError sau khi gửi" in v.loi and len(cong.bang) == 1
