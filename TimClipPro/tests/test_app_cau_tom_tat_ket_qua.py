# -*- coding: utf-8 -*-
"""Câu tóm tắt xanh «✅ Đã chọn N bằng chứng tốt nhất từ M nguồn đã quét» phải đếm đúng (audit F-10).

Kịch bản tổng hợp (không mạng, không dữ liệu thật; AppTest + thư mục tạm): màn kết quả của một lô
quét YouTube, dựng bằng đúng dạng kết quả engine trả:
  * video quét xong, 1 bằng chứng, báo cáo V2 hợp lệ;
  * video bị cầu dao YouTube bỏ qua → ``Engine._ket_qua_bo_qua`` (status «error»,
    ``loi_truy_cap.category == BLOCKED_BY_BREAKER``, ghi chú «Chưa quét — …»), không gửi request nào;
  * video quét xong nhưng báo cáo V2 lỗi (``LoiBaoCaoV2``) — ``bang_ket_qua`` loại khỏi bảng/CSV (P1-02).

Đúng:
  1. Video bị cầu dao bỏ qua KHÔNG được đếm là «nguồn đã quét» — banner đỏ ngay phía trên nói «các
     video chưa quét KHÔNG được tính là đã quét».
  2. N = số bằng chứng thật sự hiện trong bảng/CSV: không cộng kết quả mang ``LoiBaoCaoV2``.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

import bao_cao_v2
import engine as engine_mod
import truy_cap_youtube
from scan_ui import dem_cau_tom_tat

APP_PY = Path(__file__).resolve().parents[1] / "app.py"


def _man_ket_qua(tmp_path, monkeypatch, ket_qua: list):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    at.session_state.job.update({"running": False, "kind": "scan", "results": ket_qua,
                                 "error": "", "pct": 1.0, "msg": ""})
    at.run()
    assert not at.exception
    return at


def _ok(ten: str, ma: str):
    from test_bao_cao_v2 import _bc, _kq_ca_that
    kq = _kq_ca_that(source_name=ten, source_ref=f"https://www.youtube.com/watch?v={ma}",
                     source_id=ma, duration_s=3600.0, vung_da_khop=None, ly_do_pham_vi="",
                     pham_vi_quet_s=3600.0)
    kq.bao_cao = _bc(kq, mo_ta_pham_vi="")
    return kq


def _bo_qua_vi_cau_dao(url: str):
    """Đúng hình dạng ``Engine._ket_qua_bo_qua`` (không kèm ảnh chụp V2 — không ảnh hưởng tóm tắt)."""
    f = truy_cap_youtube.PhienYouTube().bo_qua(truy_cap_youtube.ma_tu_url(url), "scan")
    return engine_mod.ScanResult(source_name=url, source_ref=url, status="error",
                                 note=f.human_message_vi, loi_truy_cap=f)


def _v2_loi(ten: str, ma: str):
    kq = _ok(ten, ma)
    kq.bao_cao = bao_cao_v2.LoiBaoCaoV2(bao_cao_v2.LOI_TAO, ngoai_le="ValueError")
    return kq


def _cau_xanh(at) -> str:
    return "\n".join(str(s.value) for s in at.success)


def test_nguon_bi_cau_dao_bo_qua_khong_tinh_la_da_quet(tmp_path, monkeypatch):
    ket_qua = [_ok("Video mot", "vidthu00000"),
               _bo_qua_vi_cau_dao("https://www.youtube.com/watch?v=vidthu00001"),
               _bo_qua_vi_cau_dao("https://www.youtube.com/watch?v=vidthu00002")]
    at = _man_ket_qua(tmp_path, monkeypatch, ket_qua)
    do = "\n".join(str(e.value) for e in at.error)
    assert "KHÔNG được tính là đã quét" in do or "Chưa quét" in do, "tiền đề: banner cầu dao"
    xanh = _cau_xanh(at)
    assert "Đã chọn **1** bằng chứng tốt nhất từ 1 nguồn đã quét" in xanh, xanh


def test_so_bang_chung_khong_cong_ket_qua_bao_cao_v2_loi(tmp_path, monkeypatch):
    at = _man_ket_qua(tmp_path, monkeypatch, [_ok("Video mot", "vidthu00000"),
                                              _v2_loi("Video hai V2 loi", "vidthu00001")])
    so_dong = sum(len(df.value) for df in at.dataframe
                  if "Video mot" in df.value.to_string())
    assert so_dong == 1, "tiền đề: bảng chỉ còn 1 dòng hợp lệ"
    xanh = _cau_xanh(at)
    m = re.search(r"Đã chọn \*\*(\d+)\*\*", xanh)
    assert m, "tiền đề: câu tóm tắt xanh"
    assert int(m.group(1)) == so_dong, xanh


def test_moi_bang_chung_deu_trong_bao_cao_v2_loi_thi_khong_co_cau_xanh(tmp_path, monkeypatch):
    """Không câu «Đã chọn 0 bằng chứng»: banner ⛔ của bảng nói vì sao không xuất được."""
    at = _man_ket_qua(tmp_path, monkeypatch, [_v2_loi("Video hai V2 loi", "vidthu00001")])
    assert "bằng chứng tốt nhất" not in _cau_xanh(at)
    assert any("Báo cáo V2" in str(e.value) for e in at.error)


def test_dem_cau_tom_tat_thuan():
    tran = SimpleNamespace(category="", human_message_vi="")
    cau_dao = SimpleNamespace(category=truy_cap_youtube.BLOCKED_BY_BREAKER, human_message_vi="Chưa quét — x")
    ket_qua = [
        SimpleNamespace(status="ok", matches=[1, 2], bao_cao=None, loi_truy_cap=None),
        SimpleNamespace(status="ok", matches=[3], bao_cao=bao_cao_v2.LoiBaoCaoV2(bao_cao_v2.LOI_TAO),
                        loi_truy_cap=None),
        SimpleNamespace(status="error", matches=[4], bao_cao=None, loi_truy_cap=tran),
        SimpleNamespace(status="error", matches=[], bao_cao=None, loi_truy_cap=cau_dao),
    ]
    # Bằng chứng: chỉ nguồn «ok» có báo cáo hợp lệ (đúng bảng/CSV). Đã quét: mọi nguồn trừ cầu dao
    # (nguồn lỗi thường vẫn ĐÃ được thử quét — dòng «Có nguồn bị lỗi» nói riêng).
    assert dem_cau_tom_tat(ket_qua) == (2, 3)
    assert dem_cau_tom_tat([]) == (0, 0)
