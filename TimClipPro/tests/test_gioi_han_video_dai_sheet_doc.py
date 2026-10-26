# -*- coding: utf-8 -*-
"""Audit A-4: quét video dài bị GIỚI HẠN (GHVD «Tự động»: > 6 giờ chỉ quét 3 giờ đầu), 3 giờ đầu
không thấy gì, gửi tới đích Google Sheets «Dọc 16 cột».

Bất biến (tests/test_gioi_han_video_dai.py, docstring): «không thấy» KHÔNG BAO GIỜ thành kết luận
cho cả video. Ghi chú của kết quả nói rõ «KHÔNG phải kết luận cho toàn video», nhưng hàng 16 cột
gửi lên Sheet chỉ ghi «(không tìm thấy clip nào)» — đọc như đã kiểm TRỌN video 65 giờ.

Đúng: hoặc KHÔNG xếp hàng dòng âm tính nào (như bảng 34 cột), hoặc ô thứ 4 của dòng phải mang
phạm vi (vd. «chưa quét», «3 giờ đầu», «một phần»).

Dữ liệu tổng hợp, không mạng; khoá dịch vụ GIẢ (``outbox_gia.khoa_gia``).
"""
from __future__ import annotations

import outbox as ob
import sheet_destinations as sd
from engine import GHVD_TU_DONG
from outbox_gia import khoa_gia
from test_gioi_han_video_dai import BA_GIO, DAI_65H, _gia_lap

ID_A = "1" + "a" * 43
URL = "https://youtu.be/vid65hxxxxx"
DAU_HIEU_PHAM_VI = ("chưa quét", "3 giờ đầu", "một phần", "03:00:00")


def _dich_doc(e, tmp_path):
    db = e.sqlite_file
    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    d = sd.tao_dich(db, ten="Bảng dọc", spreadsheet_id=ID_A, worksheet_id=5,
                    worksheet_ten="Doc", schema_id=sd.SCHEMA_DOC,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    return db, sd.chot_y_dinh(db, d.id, installation_id=e.installation_id(), lo_id="lo1")


def _co_pham_vi(o) -> bool:
    s = str(o).lower()
    return any(k in s for k in DAU_HIEU_PHAM_VI)


def _kiem_dong(rows, nguon):
    for r in rows:
        assert len(r) == 16
        assert _co_pham_vi(r[3]), (
            f"{nguon}: video 65 giờ chỉ quét 3 giờ đầu nhưng dòng 16 cột gửi Sheet là âm tính "
            f"TRỌN video, không có phạm vi: ô 4 = {r[3]!r}; dòng = {r!r}")


def test_ghvd_khong_khop_doc16_khong_duoc_thanh_am_tinh_tron_video(tmp_path, monkeypatch):
    e, lan_tai = _gia_lap(tmp_path, monkeypatch, che_do=GHVD_TU_DONG, matches=())
    db, y = _dich_doc(e, tmp_path)

    with e.ghim_y_dinh_gui(y):
        kq = e.scan_youtube(URL, luu_lich_su=True)

    # Điều kiện tiền đề: đúng kịch bản của phát hiện.
    assert lan_tai == [BA_GIO]
    assert kq.status == "ok" and kq.matches == []
    assert kq.duration_s == DAI_65H and kq.pham_vi_quet_s == BA_GIO
    assert kq.quet_day_du is False and kq.ly_do_pham_vi == "gioi_han_video_dai"
    assert "KHÔNG phải kết luận cho toàn video" in kq.note
    assert kq.bao_cao is not None and kq.job_id

    # Việc thật đã xếp vào outbox (payload tuần tự hoá lúc save_job): hoặc không có việc nào,
    # hoặc dòng phải mang phạm vi.
    viec = ob.ds_viec(db, job_id=kq.job_id)
    for v in viec:
        assert v.trang_thai == ob.PENDING and len(v.header) == 16
        _kiem_dong(v.rows or [], "hang_doi_gui (PENDING)")

    # Dòng 16 cột dựng cho Sheet (một nơi cho app/Watch/CLI).
    header, rows, _ = e.dong_gui_sheets([kq], dang_ngang=False, an_toan_cu=False)
    assert len(header) == 16
    _kiem_dong(rows, "dong_gui_sheets")


def test_doi_chung_ngang34_bo_ket_qua_khong_khop(tmp_path, monkeypatch):
    """Đối chứng: bảng 34 cột không gửi kết quả 0 khớp — không thể đọc thành âm tính trọn video."""
    e, _ = _gia_lap(tmp_path, monkeypatch, che_do=GHVD_TU_DONG, matches=())
    kq = e.scan_youtube(URL, luu_lich_su=False)
    _, rows, _ = e.dong_gui_sheets([kq], dang_ngang=True, an_toan_cu=False)
    assert rows == []


def test_dong_doc_am_tinh_tron_video_van_tron_chua_ro_thi_noi_ro():
    """Hàm thuần: âm tính trơn CHỈ khi quét trọn; phạm vi không biết → không kết luận cả video."""
    import bao_cao_v2 as v2
    from test_bao_cao_v2 import _bc, _kq_ca_that

    tron = _bc(_kq_ca_that(matches=[], vung_da_khop=[(0.0, 14523.4)], ly_do_pham_vi="",
                           pham_vi_quet_s=14523.4))
    assert v2.dong_doc(tron)[0][3] == "(không tìm thấy clip nào)"
    chua_ro = _bc(_kq_ca_that(matches=[], vung_da_khop=None, ly_do_pham_vi="",
                              pham_vi_quet_s=0.0))
    assert v2.dong_doc(chua_ro)[0][3] == \
        "(không tìm thấy clip nào — chưa xác nhận đã quét trọn video)"
    # Tên video vẫn sạch (mục 5 REPORT_POLICY_V2): phạm vi nằm ở ô kết quả, không ở tên.
    assert v2.dong_doc(chua_ro)[0][1] == chua_ro.tieu_de
