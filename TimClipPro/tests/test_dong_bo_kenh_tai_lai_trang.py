# -*- coding: utf-8 -*-
"""Audit D-13 — đồng bộ kênh gắn chặt vào MỘT phiên Streamlit.

Bất biến (giống lô quét, ``scan_jobs._DANG_CHAY`` / ``tests/test_tien_do_lo_quet.py``): tải lại trang = phiên mới
phải NHẬN LẠI tác vụ đang chạy — thấy tiến độ, bấm Dừng được, và thấy kết quả khi xong. Không được im lặng coi như
không có gì chạy.

Kịch bản synthetic (không mạng, không dữ liệu thật): ``ChannelSync._sync_da_khoa`` được thay bằng bản giả chặn trên
một Event (KHOÁ kho thật ``KhoaTienTrinh`` của ``ChannelSync.sync`` vẫn giữ nguyên). Phiên #1 bấm «Bắt đầu đồng bộ
kênh»; phiên #2 (= tải lại trang) mở app trên CÙNG thư mục dữ liệu.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

from channel import ChannelSync

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
NHAN_KENH = "Link kênh YouTube của bạn"
NHAN_KHO = "Thư mục kho clip gốc (ổ D, E... tùy bạn)"
NUT_DONG_BO = "⬇️ Bắt đầu đồng bộ kênh"
NUT_DUNG = "⏹️ Dừng đồng bộ"


def _o(at, nhan):
    return next(x for x in at.text_input if x.label == nhan)


def _nut(at, nhan):
    return next((b for b in at.button if b.label == nhan), None)


def _van_ban(at) -> str:
    phan = []
    for nhom in (at.markdown, at.info, at.caption, at.warning, at.error, at.success,
                 at.header, at.subheader):
        phan.extend(str(i.value) for i in nhom)
    return "\n".join(phan)


def _cho(dieu_kien, han_s=20.0):
    het = time.monotonic() + han_s
    while time.monotonic() < het:
        if dieu_kien():
            return True
        time.sleep(0.02)
    return dieu_kien()


def test_tai_lai_trang_khi_dong_bo_kenh_dang_chay_phien_moi_phai_nhan_lai(tmp_path, monkeypatch):
    import streamlit

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    kho = tmp_path / "KhoGia"
    kho.mkdir()

    da_bat_dau = threading.Event()
    tha = threading.Event()
    luot: list = []          # (ChannelSync, cancel_check) của mỗi lượt đã vào vùng khoá

    def sync_gia(self, url, limit, progress, cancel_check, thu_lai_han_che=False):
        luot.append((self, cancel_check))
        da_bat_dau.set()
        if progress:
            progress(0.1, "Đang tải video giả 1/3")
        _cho(lambda: tha.is_set() or (cancel_check is not None and cancel_check()), 30.0)
        huy = bool(cancel_check and cancel_check())
        return {"tong": 3, "moi": 0 if huy else 3, "bo_qua": 0, "loi": [], "thu_muc": self.dest,
                "da_huy": huy, "nghi_hong": [], "da_cach_ly": [], "da_doi_soat": 0, "chan_youtube": "",
                "youtube": {}, "trang_thai": "DA_HUY" if huy else "DAY_DU", "can_tai": 3, "so_loi": 0,
                "chua_thu": 3 if huy else 0, "gioi_han_tuoi": 0, "chi_hoi_vien": 0, "xac_thuc": {},
                "han_che_bo_qua": 0, "canh_bao_cookie": ""}

    monkeypatch.setattr(ChannelSync, "_sync_da_khoa", sync_gia)
    # Màn tiến độ tự st.rerun() mãi; vô hiệu hoá để mỗi at.run() vẽ đúng một khung hình.
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)

    # ---- Phiên #1: bắt đầu đồng bộ kênh (lượt dài nhiều giờ ngoài đời thật)
    at1 = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at1.exception
    _o(at1, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
    _o(at1, NHAN_KHO).set_value(str(kho))
    at1.run()
    _nut(at1, NUT_DONG_BO).click().run()
    assert not at1.exception
    assert da_bat_dau.wait(15), "thiết lập: lượt đồng bộ giả của phiên #1 không chạy"
    job1 = at1.session_state.job_dong_bo
    eng1 = at1.session_state.eng
    _, cancel_check1 = luot[0]
    at1.run()
    assert _nut(at1, NUT_DUNG) is not None, "đối chứng: chính phiên #1 thấy màn tiến độ + nút Dừng"

    try:
        # ---- Phiên #2 = người dùng TẢI LẠI TRANG (phiên mới, cùng thư mục dữ liệu, cùng tiến trình)
        at2 = AppTest.from_file(str(APP_PY), default_timeout=120).run()
        assert not at2.exception
        job2 = at2.session_state.job_dong_bo
        eng2 = at2.session_state.eng
        thay_dang_chay = bool(job2.get("running")) or _nut(at2, NUT_DUNG) is not None

        # Không thấy gì đang chạy → người dùng bấm «Bắt đầu đồng bộ kênh» lần nữa.
        loi_bam_lai = ""
        nut2 = None
        if not thay_dang_chay:
            _o(at2, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
            _o(at2, NHAN_KHO).set_value(str(kho))
            at2.run()
            nut2 = _nut(at2, NUT_DONG_BO)
        if nut2 is not None and not nut2.disabled:
            nut2.click().run()
            assert _cho(lambda: not job2.get("running"), 15.0)
            at2.run()
            loi_bam_lai = "\n".join(str(e.value) for e in at2.error)

        # Bấm Dừng ở phiên #2 (nếu có nút) phải dừng ĐÚNG lượt đang chạy.
        nut_dung2 = _nut(at2, NUT_DUNG)
        if nut_dung2 is not None:
            nut_dung2.click().run()
        dung_duoc = bool(cancel_check1())
        # Dừng duy nhất phiên #2 có được ngoài giao diện: cờ huỷ Engine của CHÍNH nó.
        eng2.cancel()
        co_huy_chung = bool(cancel_check1())
        eng2.cancel_event.clear()
    finally:
        tha.set()

    assert _cho(lambda: not job1.get("running"), 20.0), "lượt giả phiên #1 không kết thúc"
    at2.run()
    thay_ket_qua = any(("Đồng bộ xong" in str(x.value) or "Đã dừng đồng bộ" in str(x.value))
                       for x in list(at2.success) + list(at2.warning))

    quan_sat = (
        f"\n  Engine phiên #1 is phiên #2: {eng1 is eng2}"
        f"\n  phiên #2 thấy lượt đang chạy (job.running / nút Dừng): {thay_dang_chay}"
        f"\n  phiên #2 bấm đồng bộ lại -> lỗi hiển thị: {loi_bam_lai[:160]!r}"
        f"\n  Dừng từ phiên #2 tới được lượt đang chạy: {dung_duoc}"
        f"\n  eng2.cancel() làm cancel_check phiên #1 = True: {co_huy_chung}"
        f"\n  kết quả lượt (job phiên #1) = trang_thai {job1.get('results', {}).get('trang_thai')!r}, "
        f"error {job1.get('error')!r}"
        f"\n  phiên #2 hiện kết quả lượt đồng bộ: {thay_ket_qua}"
        f"\n  văn bản phiên #2: {_van_ban(at2)[:200]!r}"
    )
    assert thay_dang_chay and dung_duoc and thay_ket_qua, (
        "Tải lại trang khi đồng bộ kênh đang chạy: phiên mới phải nhận lại lượt đó (tiến độ, Dừng, kết quả)"
        + quan_sat)


def test_so_tac_vu_nen_mot_tac_vu_moi_thu_muc_du_lieu_va_tra_lease(tmp_path):
    """Sổ mức tiến trình: phiên khác bấm trùng trên CÙNG thư mục dữ liệu bị từ chối (chưa chạy gì), Dừng từ bất kỳ
    phiên nào gọi cờ huỷ của Engine đã khởi động, xong thì rời sổ và trả lease cổng bảo trì."""
    import types

    import tac_vu_nen

    eng = types.SimpleNamespace(data_dir=str(tmp_path / "data"))
    eng_phien_moi = types.SimpleNamespace(data_dir=str(tmp_path / "data"))
    huy = threading.Event()
    tha = threading.Event()
    lease = types.SimpleNamespace(da_tra=0)
    lease.tra = lambda: setattr(lease, "da_tra", lease.da_tra + 1)

    def ham(progress, so):
        progress(0.5, "nửa đường")
        _cho(lambda: tha.is_set() or huy.is_set(), 10.0)
        return {"so": so, "da_huy": huy.is_set()}

    job: dict = {}
    tv = tac_vu_nen.TacVuNen("channel", huy=huy.set)
    tv.bat_dau(eng, ham, (), {"so": 7}, job=job, lease=lease)
    try:
        assert tac_vu_nen.dang_chay_cua(eng_phien_moi) is tv
        assert _cho(lambda: tv.anh()["msg"] == "nửa đường", 5.0)
        tv2 = tac_vu_nen.TacVuNen("va_title", huy=lambda: None)
        da_chay = []
        try:
            tv2.bat_dau(eng_phien_moi, lambda progress: da_chay.append(1), (), {}, job={})
            raise AssertionError("tác vụ trùng trên cùng thư mục dữ liệu phải bị từ chối")
        except tac_vu_nen.DangCoTacVuKhac:
            pass
        assert not da_chay and not tv2.running
        tac_vu_nen.dang_chay_cua(eng_phien_moi).huy()
    finally:
        tha.set()
    assert _cho(lambda: not job.get("running", True) and not tv.running, 10.0)
    assert huy.is_set() and job["results"] == {"so": 7, "da_huy": True} and job["error"] == ""
    assert tv.anh()["results"] == job["results"] and lease.da_tra == 1
    assert tac_vu_nen.dang_chay_cua(eng_phien_moi) is None


# ------------------------------------------------ review audit D: lượt XONG trước khi người dùng tải lại trang

def test_dong_bo_xong_khi_tab_da_bi_do_phien_mo_sau_van_thay_ket_qua_mot_lan(tmp_path, monkeypatch):
    """Đồng bộ kênh nhiều giờ, trình duyệt dỡ tab (một trong các tác nhân D-13 nêu), lượt XONG lúc 03:00; người dùng mở
    trang lúc 08:00 = phiên mới. Phiên đó phải thấy kết quả cuối (trạng thái, video lỗi, đăng nhập) — đúng MỘT lần: phiên
    mở sau nữa không hiện lại kết quả cũ như việc mới."""
    import streamlit

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    kho = tmp_path / "KhoGia"
    kho.mkdir()
    da_bat_dau = threading.Event()
    tha = threading.Event()

    def sync_gia(self, url, limit, progress, cancel_check, thu_lai_han_che=False):
        da_bat_dau.set()
        if progress:
            progress(0.1, "Đang tải video giả 1/3")
        _cho(tha.is_set, 30.0)
        return {"tong": 3, "moi": 2, "bo_qua": 0, "loi": ["Video gia 3: lỗi giả đã ghi nhận"], "thu_muc": self.dest,
                "da_huy": False, "nghi_hong": [], "da_cach_ly": [], "da_doi_soat": 0, "chan_youtube": "",
                "youtube": {}, "trang_thai": "MOT_PHAN", "can_tai": 3, "so_loi": 1, "chua_thu": 0,
                "gioi_han_tuoi": 0, "chi_hoi_vien": 0, "xac_thuc": {}, "han_che_bo_qua": 0, "canh_bao_cookie": ""}

    monkeypatch.setattr(ChannelSync, "_sync_da_khoa", sync_gia)
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)

    at1 = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    _o(at1, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
    _o(at1, NHAN_KHO).set_value(str(kho))
    at1.run()
    _nut(at1, NUT_DONG_BO).click().run()
    assert da_bat_dau.wait(15), "thiết lập: lượt đồng bộ giả không chạy"
    job1 = at1.session_state.job_dong_bo
    # Tab bị dỡ: phiên #1 không vẽ lại nữa. Lượt xong khi không phiên nào đang mở.
    tha.set()
    assert _cho(lambda: not job1.get("running"), 20.0), "lượt giả không kết thúc"

    at2 = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at2.exception
    van_ban2 = _van_ban(at2)
    job2 = at2.session_state.job_dong_bo
    assert job2.get("kind") == "channel" and job2.get("results", {}).get("trang_thai") == "MOT_PHAN", (
        f"phiên mở SAU khi lượt xong không thấy kết quả: job={dict(job2)!r}; văn bản: {van_ban2[:300]!r}")
    assert "lỗi giả đã ghi nhận" in van_ban2 or "Đồng bộ xong" in van_ban2, van_ban2[:400]

    at3 = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at3.exception
    assert not at3.session_state.job_dong_bo.get("kind"), "kết quả đã có phiên nhận — phiên sau không hiện lại"


def test_so_tac_vu_nen_giu_ket_qua_vua_xong_toi_khi_mot_phien_nhan(tmp_path):
    import types

    import tac_vu_nen

    eng = types.SimpleNamespace(data_dir=str(tmp_path / "data"))
    eng_phien_moi = types.SimpleNamespace(data_dir=str(tmp_path / "data"))

    def chay_xong(ket):
        job: dict = {}
        tv = tac_vu_nen.TacVuNen("channel", huy=lambda: None)
        tv.bat_dau(eng, lambda progress: ket, (), {}, job=job)
        assert _cho(lambda: not tv.running and job.get("running") is False, 10.0)
        return tv

    tv = chay_xong({"trang_thai": "DAY_DU"})
    assert tac_vu_nen.dang_chay_cua(eng_phien_moi) is None
    nhan = tac_vu_nen.nhan_vua_xong(eng_phien_moi)
    assert nhan is tv and nhan.anh()["results"] == {"trang_thai": "DAY_DU"} and not nhan.anh()["running"]
    assert tac_vu_nen.nhan_vua_xong(eng_phien_moi) is None, "chỉ một phiên nhận"

    # Phiên đã bấm tự theo dõi tới lúc xong (đã chép kết quả) → bỏ khỏi sổ, phiên mới không nhận lại.
    tv2 = chay_xong({"trang_thai": "MOT_PHAN"})
    tac_vu_nen.da_nhan(eng, tv2)
    assert tac_vu_nen.nhan_vua_xong(eng_phien_moi) is None

    # Tác vụ mới bắt đầu thì kết quả cũ chưa ai nhận không còn là «vừa xong».
    chay_xong({"trang_thai": "cu"})
    tha = threading.Event()
    tv4 = tac_vu_nen.TacVuNen("va_title", huy=tha.set)
    tv4.bat_dau(eng, lambda progress: _cho(tha.is_set, 10.0), (), {}, job={})
    try:
        assert tac_vu_nen.nhan_vua_xong(eng_phien_moi) is None
    finally:
        tha.set()
    assert _cho(lambda: not tv4.running, 10.0)
    assert tac_vu_nen.nhan_vua_xong(eng_phien_moi) is tv4
