# -*- coding: utf-8 -*-
"""Báo cáo V2 cho chế độ «Một video gốc chung cho cả lô».

Lô vẫn KHÔNG ghi lịch sử, KHÔNG đẩy Sheets (bất biến cũ). V2 chỉ đổi phần trình bày của lô
được ghim chính sách V2: link video gốc ``watch?v=``, ngày đăng nguyên bản (thiếu thì trống
kèm lý do), link nhảy mốc đúng giây hiển thị. Chỉ video gốc ĐƯỢC BÁO CÁO mới được bổ sung
ngày qua mạng (khi người dùng bật) — không bao giờ mọi ứng viên đạt chuẩn.
"""
import pytest

import bao_cao_v2 as v2
import common_original as co
from engine import Config, Match
from test_nguon_chung_jobs import A, EngineGia, JobGia, _chay, _url

KHO = "kho1"


def M(clip, start=0.0, hashes=6000, matched=300.0):
    return Match(clip=clip, start_s=start, end_s=start + matched, matched_s=matched,
                 clip_offset_s=0.0, hashes=hashes, confidence="x", ty_le=50.0,
                 clip_bat_dau_s=start, vung_khop_s=start)


def _lo(*starts):
    vs = []
    for i, s in enumerate(starts, 1):
        v = co.VideoTrongLo(thu_tu=i, nguon=f"https://www.youtube.com/watch?v=vid{i:08d}",
                            ma=f"vid{i:08d}", tieu_de=f"Video [{i}] thật", kenh="Kênh",
                            thoi_luong=3600.0)
        v.luot.append(co.LuotQuet(muc_tieu="collect", hop_le=True, tron=True,
                                  ung_vien=(M(A, s),), thoi_luong=3600.0))
        vs.append(v)
    return co.TrangThaiLo(kho_id=KHO, videos=vs, cfg=Config())


def _cot(rows, ten):
    return [r[co.HEADER_NGUON_CHUNG.index(ten)] for r in rows]


TT_GOC_V2 = {"chinh_sach": "v2", "title": "Tên gốc", "url": v2.url_goc_chuan("aaaaaaaaaaa"),
             "ngay_dang": "20250312", "nguon_ngay_dang": v2.NGUON_UPLOAD_DATE,
             "ly_do_thieu_ngay": "", "ngay_kho_quy_doi": "20250313", "duration": 1500.0,
             "video_id": "aaaaaaaaaaa", "status": "complete", "warnings": ()}


def test_dong_bao_cao_v2_url_watch_ngay_nguyen_ban_link_dung_giay():
    tt = _lo(915.8, 120.0)
    kql = co.dung_ket_qua_lo(tt, co.ket_luan(tt), ma_lo="lo", kho_ten="K",
                             thong_tin_goc=TT_GOC_V2, dem_ten={},
                             chinh_sach_bao_cao=v2.CHINH_SACH_V2)
    rows = co.dong_bao_cao(kql)
    assert _cot(rows, "Link video gốc") == ["https://www.youtube.com/watch?v=aaaaaaaaaaa"] * 2
    assert _cot(rows, "Ngày đăng video gốc") == ["12/03/2025"] * 2   # không phải 13/03
    assert _cot(rows, "Clip bắt đầu từ")[0] == "00:15:15"
    assert _cot(rows, "🔗 Nhảy tới đúng mốc vi phạm")[0] == "https://www.youtube.com/watch?v=vid00000001&t=915"
    assert _cot(rows, "Video vi phạm")[0] == "Video [1] thật"


def test_dong_bao_cao_v2_thieu_ngay_thi_de_trong_khong_dung_ngay_quy_doi():
    tt = _lo(10.0, 20.0)
    tt_goc = {**TT_GOC_V2, "ngay_dang": "", "nguon_ngay_dang": "",
              "ly_do_thieu_ngay": "kho chỉ lưu ngày đã quy đổi múi giờ"}
    kql = co.dung_ket_qua_lo(tt, co.ket_luan(tt), ma_lo="lo", kho_ten="K",
                             thong_tin_goc=tt_goc, dem_ten={}, chinh_sach_bao_cao="v2")
    assert _cot(co.dong_bao_cao(kql), "Ngày đăng video gốc") == ["", ""]


def test_lo_khong_ghim_chinh_sach_giu_luat_cu():
    tt = _lo(915.8, 120.0)
    kql = co.dung_ket_qua_lo(tt, co.ket_luan(tt), ma_lo="lo", kho_ten="K",
                             thong_tin_goc={"title": "T", "url": "https://youtu.be/aaaaaaaaaaa",
                                            "upload_date": "20250313", "duration": 1.0},
                             dem_ten={})
    assert kql.chinh_sach_bao_cao == ""
    rows = co.dong_bao_cao(kql)
    assert _cot(rows, "Link video gốc")[0] == "https://youtu.be/aaaaaaaaaaa"
    assert _cot(rows, "Ngày đăng video gốc")[0] == "13/03/2025"


# ---------------------------------------------------------------------------
#  Bộ điều phối: chính sách ghim từ job, chỉ video gốc được báo cáo được bổ sung
# ---------------------------------------------------------------------------

class JobGiaV2(JobGia):
    chinh_sach_bao_cao = v2.CHINH_SACH_V2

    def goc_bao_cao_v2(self, clip, *, cho_bo_sung):
        self.eng.goi_goc_v2.append((clip, cho_bo_sung))
        return v2.GocV2(clip=clip, video_id="aaaaaaaaaaa", url=v2.url_goc_chuan("aaaaaaaaaaa"),
                        tieu_de="Tên gốc", ngay_dang=v2.NgayNguon(
                            gia_tri="20250312", nguon=v2.NGUON_UPLOAD_DATE),
                        ngay_kho_quy_doi="20250313", thoi_luong_s=1500.0,
                        trang_thai_metadata="complete")


@pytest.fixture()
def eng_v2(tmp_path):
    tg = {"v1aaaaaaaaa": {"dai": 3000, "clips": {A: 0.5}},
          "v2aaaaaaaaa": {"dai": 2000, "clips": {A: 0.2}}}
    eng = EngineGia(tmp_path, tg)
    eng.goi_goc_v2 = []
    eng.job = JobGiaV2(eng)
    return eng, tg


def test_lo_v2_chi_hoi_video_goc_duoc_bao_cao_mot_lan(eng_v2):
    eng, tg = eng_v2
    ctl, kq = _chay(eng, [_url(v) for v in tg])
    assert kq.trang_thai == co.TIM_THAY
    assert kq.chinh_sach_bao_cao == v2.CHINH_SACH_V2
    assert eng.goi_goc_v2 == [(A, True)]
    assert kq.thong_tin_goc["url"] == "https://www.youtube.com/watch?v=aaaaaaaaaaa"
    assert kq.thong_tin_goc["ngay_dang"] == "20250312"
    assert "upload_date" not in kq.thong_tin_goc        # không mang ngày quy đổi dưới tên cũ
    rows = co.dong_bao_cao(kq)
    assert _cot(rows, "Ngày đăng video gốc") == ["12/03/2025"] * 2
    assert all(x is False for x in eng.luu_lich_su), "lô vẫn KHÔNG ghi lịch sử"


def test_lo_v2_quet_file_khong_bo_sung_qua_mang(eng_v2, tmp_path):
    eng, tg = eng_v2
    eng.the_gioi = {"a.mp4": {"dai": 3000, "clips": {A: 0.5}},
                    "b.mp4": {"dai": 2000, "clips": {A: 0.2}}}
    files = []
    for ten in eng.the_gioi:
        p = tmp_path / ten
        p.write_bytes(b"x")
        files.append(str(p))
    ctl, kq = _chay(eng, files, source_type="file")
    assert kq.trang_thai == co.TIM_THAY
    assert eng.goi_goc_v2 == [(A, False)]


class JobGiaV2ThieuNgay(JobGiaV2):
    def goc_bao_cao_v2(self, clip, *, cho_bo_sung):
        self.eng.goi_goc_v2.append((clip, cho_bo_sung))
        return v2.GocV2(clip=clip, video_id="aaaaaaaaaaa", url=v2.url_goc_chuan("aaaaaaaaaaa"),
                        tieu_de="Tên gốc", ngay_dang=v2.NgayNguon(
                            ly_do_thieu="kho chỉ lưu ngày đã quy đổi múi giờ"),
                        ngay_kho_quy_doi="20250313", thoi_luong_s=1500.0)


def test_lo_v2_thieu_ngay_nguyen_ban_khong_lui_ve_ngay_quy_doi(eng_v2):
    eng, tg = eng_v2
    eng.job = JobGiaV2ThieuNgay(eng)
    ctl, kq = _chay(eng, [_url(v) for v in tg])
    assert kq.thong_tin_goc["ngay_dang"] == ""
    assert kq.thong_tin_goc["ly_do_thieu_ngay"]
    assert _cot(co.dong_bao_cao(kq), "Ngày đăng video gốc") == ["", ""]


def test_lo_v2_thieu_ten_video_khong_lay_url_lam_ten():
    tt = _lo(10.0, 20.0)
    tt.videos[0].tieu_de = ""
    v2_kql = co.dung_ket_qua_lo(tt, co.ket_luan(tt), ma_lo="lo", kho_ten="K",
                                thong_tin_goc=TT_GOC_V2, dem_ten={}, chinh_sach_bao_cao="v2")
    assert _cot(co.dong_bao_cao(v2_kql), "Video vi phạm")[0] == ""
    cu_kql = co.dung_ket_qua_lo(tt, co.ket_luan(tt), ma_lo="lo", kho_ten="K",
                                thong_tin_goc={}, dem_ten={})
    assert _cot(co.dong_bao_cao(cu_kql), "Video vi phạm")[0] == tt.videos[0].nguon
