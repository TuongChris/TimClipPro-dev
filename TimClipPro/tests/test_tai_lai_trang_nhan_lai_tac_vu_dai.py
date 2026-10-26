# -*- coding: utf-8 -*-
"""Audit F-2: tải lại trang / mở tab thứ hai trong lúc một tác vụ dài đang chạy.

Đúng (theo cách ``ScanJobController`` đã làm cho lô quét, và theo lời hứa của giao diện
«Bạn có thể để yên và làm việc khác»): phiên trình duyệt MỚI của cùng tiến trình phải
NHẬN LẠI tác vụ đang chạy trên cùng thư mục dữ liệu — thấy màn hình tiến độ, có nút Dừng
tới đúng worker, coi là «đang bận» (không cho tạo việc trùng), và thấy kết quả khi xong.

Mọi thứ synthetic: thư mục tạm, worker giả chặn bằng ``threading.Event``, không mạng,
không FFmpeg/audfprint thật. Đối chứng: lô quét thường ĐƯỢC nhận lại (test xanh) — chứng
minh khung hai-AppTest dùng được, nên các test đỏ còn lại đỏ vì lỗi thật.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from common_original_jobs import CommonOriginalJobController
from engine import Engine, ScanResult

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
NUT_DUNG = "⏹️ Dừng lại"


def _van_ban(at) -> str:
    phan = []
    for nhom in (at.markdown, at.info, at.caption, at.warning, at.error, at.success,
                 at.header, at.subheader, at.code):
        phan.extend(str(i.value) for i in nhom)
    phan.extend(str(i.label) for i in at.metric)
    phan.extend(str(i.value) for i in at.metric)
    phan.extend(str(i.label) for i in at.expander)
    return "\n".join(phan)


def _phien_moi() -> AppTest:
    """Một phiên trình duyệt mới (F5, tab thứ hai, mở lại lối tắt) của CÙNG tiến trình."""
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def _nut_dung(at, key=None) -> list:
    return [b for b in at.button if b.label == NUT_DUNG and (key is None or b.key == key)]


def _cho_het(ham_dang_chay, han: float = 20.0) -> None:
    het = time.monotonic() + han
    while ham_dang_chay() and time.monotonic() < het:
        time.sleep(0.02)


@pytest.fixture()
def moi_truong(tmp_path, monkeypatch):
    import streamlit

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at1 = _phien_moi()
    # Màn hình tiến độ tự gọi st.rerun(); tắt để chụp đúng khung hình người dùng thấy.
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: None)
    return at1


# ---------------------------------------------------------------- đối chứng (phải XANH)

def test_doi_chung_lo_quet_thuong_duoc_phien_moi_nhan_lai(moi_truong, monkeypatch):
    at1 = moi_truong
    bat_dau, cho = threading.Event(), threading.Event()

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        bat_dau.set()
        cho.wait(30)
        return ScanResult(source_name=url, source_ref=url)

    monkeypatch.setattr(Engine, "scan_youtube", scan_youtube)
    ctl = at1.session_state.scan_controller
    ctl.start(["https://youtu.be/aaaaaaaaaaa"], "youtube")
    try:
        assert bat_dau.wait(10)
        at2 = _phien_moi()
        assert "Đang quét video" in _van_ban(at2)
        assert _nut_dung(at2)
    finally:
        cho.set()
        _cho_het(lambda: ctl.running)


# ---------------------------------------------------------------- (b) dựng kho vân tay

def test_tai_lai_trang_khi_dang_dung_kho_van_tay_mat_job(moi_truong, monkeypatch, tmp_path):
    at1 = moi_truong
    nguon = tmp_path / "ClipGoc"
    nguon.mkdir()
    (nguon / "00000000 - Clip một [aaaaaaaaaaa].opus").write_bytes(b"fixture")

    dang_chay, cho_xong, thay_dung = threading.Event(), threading.Event(), threading.Event()

    def build_gia(self, thumuc, mode="new", progress=None, tracker=None):
        # Chạy SAU khoa_tac_vu: đang giữ data/tool.lock + lease bảo trì như build thật.
        dang_chay.set()
        het = time.monotonic() + 30
        while time.monotonic() < het and not cho_xong.is_set():
            if self.cancel_event.is_set():
                thay_dung.set()
                break
            time.sleep(0.02)
        return {"so_clip": 3, "da_xu_ly": 3, "thanh_cong": 2, "bo_qua": 0, "that_bai": 1,
                "giay": 1.0, "loi_file": ["Clip ba.opus: không tạo được hash"],
                "canh_bao": ["File vân tay cũ đang bị khóa; đã ghi kết quả vào file mới an toàn."]}

    monkeypatch.setattr(Engine, "_build_database_da_khoa", build_gia)
    ctl1 = at1.session_state.fingerprint_controller
    job_id = ctl1.start(str(nguon), "new")
    at1.session_state.job.update({"running": True, "pct": 0.0, "msg": "", "results": [],
                                  "error": "", "kind": "db", "da_day_sheet": False,
                                  "fingerprint_job_id": job_id})
    loi = []
    try:
        assert dang_chay.wait(10), "worker giả chưa chạy"
        at1.run()                       # tiền đề: phiên KHỞI ĐỘNG build thấy tiến độ + Dừng
        assert "Đang tạo vân tay clip gốc" in _van_ban(at1) and _nut_dung(at1)
        at2 = _phien_moi()                                   # F5 / tab thứ hai
        chu = _van_ban(at2)
        if "Đang tạo vân tay clip gốc" not in chu:
            loi.append("phiên mới KHÔNG hiện màn hình tiến độ dựng kho (giao diện rảnh)")
        if not (at2.session_state.job.get("running")
                or at2.session_state.fingerprint_controller.running):
            loi.append("phiên mới coi như rảnh (job.running=False, controller mới) → "
                       "dang_co_tac_vu()=False: cho bắt đầu quét/dựng kho chồng lên build")
        nut = _nut_dung(at2)
        if not nut:
            loi.append("phiên mới không có nút «⏹️ Dừng lại» cho build đang chạy")
        else:
            nut[0].click()
            at2.run()
            if not thay_dung.wait(5):
                loi.append("bấm Dừng ở phiên mới không tới cờ huỷ mà worker đọc")
    finally:
        cho_xong.set()
        _cho_het(lambda: ctl1.running)
    assert not ctl1.running and ctl1.result, "worker build giả phải kết thúc có kết quả"
    at2.run()
    chu = _van_ban(at2)
    if "file có vấn đề" not in chu or "File vân tay cũ đang bị khóa" not in chu:
        loi.append("build xong nhưng phiên mới không bao giờ hiện kết quả "
                   "(loi_file / canh_bao bị bỏ)")
    assert not loi, "F-2 (b) dựng kho:\n- " + "\n- ".join(loi)


# ---------------------------------------------------------------- (a) một video gốc chung

def test_tai_lai_trang_khi_lo_nguon_chung_dang_chay_mat_lo(moi_truong, monkeypatch):
    from test_nguon_chung_ui import _kql

    at1 = moi_truong
    dang_chay, cho_xong, thay_dung = threading.Event(), threading.Event(), threading.Event()

    def chay_gia(self, job, ma_lo, nguon, source_type):
        # Chạy bên trong vao_cong_cua + KhoaTienTrinh(tool.lock) như lô thật.
        dang_chay.set()
        het = time.monotonic() + 30
        while time.monotonic() < het and not cho_xong.is_set():
            if job.cancel_event.is_set():
                thay_dung.set()
                break
            time.sleep(0.02)
        return _kql()

    monkeypatch.setattr(CommonOriginalJobController, "_chay_da_khoa", chay_gia)
    ctl1 = at1.session_state.common_controller
    ma_lo = ctl1.start([f"https://youtu.be/vid0000000{i}" for i in range(1, 4)], "youtube")
    at1.session_state.job.update({"running": True, "pct": 0.0, "msg": "", "results": [],
                                  "error": "", "kind": "nguon_chung", "da_day_sheet": True,
                                  "ma_lo": ma_lo})
    loi = []
    try:
        assert dang_chay.wait(10), "worker lô giả chưa chạy"
        # Bằng chứng: lô vô hình đang giữ tool.lock của chính tiến trình này.
        eng2_thu = Engine(data_dir=os.environ["TIMCLIP_DATA_DIR"],
                          out_dir=os.environ["TIMCLIP_OUTPUT_DIR"])
        from khoa import DangChayRoi
        with pytest.raises(DangChayRoi):
            with eng2_thu.khoa_tac_vu("dựng kho vân tay"):
                pass

        at1.run()                       # tiền đề: phiên KHỞI ĐỘNG lô thấy tiến độ + Dừng
        assert "Đang tìm video gốc chung cho cả lô" in _van_ban(at1)
        assert _nut_dung(at1, key="dung_nguon_chung")
        at2 = _phien_moi()
        chu = _van_ban(at2)
        if "Đang tìm video gốc chung cho cả lô" not in chu:
            loi.append("phiên mới KHÔNG hiện màn hình tiến độ lô nguồn chung (giao diện rảnh)")
        if not (at2.session_state.job.get("running")
                or at2.session_state.common_controller.running):
            loi.append("phiên mới coi như rảnh → dang_co_tac_vu()=False: cho quét thường song "
                       "song với lô (gấp đôi lưu lượng YouTube) / bấm tạo kho → lỗi khoá trơn")
        nut = _nut_dung(at2, key="dung_nguon_chung")
        if not nut:
            loi.append("phiên mới không có nút Dừng 'dung_nguon_chung'")
        else:
            nut[0].click()
            at2.run()
            if not thay_dung.wait(5):
                loi.append("bấm Dừng ở phiên mới không tới cờ huỷ mà worker đọc")
    finally:
        cho_xong.set()
        _cho_het(lambda: ctl1.running)
    assert not ctl1.running and ctl1.result is not None, "lô giả phải kết thúc có KetQuaLo"
    at2.run()
    chu = _van_ban(at2)
    nut_csv = [b for b in at2.button if b.key == "luu_csv_nguon_chung"]
    if "VIDEO GỐC CHUNG" not in chu and not nut_csv:
        loi.append("lô xong nhưng kết luận/bằng chứng (KetQuaLo) không hiện ở phiên mới và "
                   "không có nút lưu CSV — chỉ nằm trong controller của phiên đã chết")
    assert not loi, "F-2 (a) nguồn chung:\n- " + "\n- ".join(loi)


# ---------------------------------------------------------------- (d) tab mở TRƯỚC khi quét

def test_tab_mo_truoc_khi_lo_quet_bat_dau_khong_bao_gio_nhan_lo(moi_truong, monkeypatch):
    at_a = moi_truong
    at_b = _phien_moi()                     # tab B mở TRƯỚC khi lô bắt đầu
    bat_dau, cho = threading.Event(), threading.Event()

    def scan_youtube(self, url, progress=None, luu_lich_su=True, **kw):
        bat_dau.set()
        cho.wait(30)
        return ScanResult(source_name=url, source_ref=url)

    monkeypatch.setattr(Engine, "scan_youtube", scan_youtube)
    ctl = at_a.session_state.scan_controller
    ctl.start(["https://youtu.be/aaaaaaaaaaa"], "youtube")
    at_a.session_state.job.update({"running": True, "pct": 0.0, "msg": "", "results": [],
                                   "error": "", "kind": "scan", "da_day_sheet": True,
                                   "scan_batch_id": "t"})
    loi = []
    try:
        assert bat_dau.wait(10)
        at_a.run()                          # tiền đề: tab A thấy lô của nó
        assert "Đang quét video" in _van_ban(at_a) and _nut_dung(at_a)
        at_b.run()                          # tab B vẽ lại (bất kỳ thao tác nào)
        chu = _van_ban(at_b)
        if "Đang quét video" not in chu:
            loi.append("tab B (mở trước) không hiện lô quét đang chạy")
        if not (at_b.session_state.job.get("running")
                or at_b.session_state.scan_controller.running):
            loi.append("tab B coi như rảnh → cho «Tạo lại kho từ đầu» chồng lên lô quét")
    finally:
        cho.set()
        _cho_het(lambda: ctl.running)
    assert not loi, "F-2 (d) hai tab:\n- " + "\n- ".join(loi)


# ---------------------------------------------------------------- (b') build vs phiên khác

def test_build_cong_bo_sang_file_moi_phien_khac_van_quet_kho_cu(tmp_path, monkeypatch):
    from test_kho_build_an_toan import _eng, _kho, runner_gia

    e_b = _eng(tmp_path)                                # phiên đang dựng kho
    nguon, db_cu = _kho(e_b, tmp_path, "A", ["a.opus"], [("cu.opus", 9)])
    # Phiên khác (tab khác / trước khi tải lại), cùng thư mục dữ liệu, cùng kho «A».
    e_a = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"),
                 out_dir=str(tmp_path / "out"))
    assert os.path.normcase(e_a.db_file) == os.path.normcase(str(db_cu))

    that = os.replace
    da_chan = []

    def replace_gia(src, dst, *a, **k):
        # Windows: một lượt quét ở phiên kia đang mở file kho cũ → os.replace bị từ chối.
        if not da_chan and os.path.normcase(os.path.abspath(dst)) == os.path.normcase(str(db_cu)):
            da_chan.append(dst)
            raise PermissionError(32, "The process cannot access the file")
        return that(src, dst, *a, **k)

    monkeypatch.setattr(os, "replace", replace_gia)
    e_b._run_stream = runner_gia(e_b, {"a.opus": 9})
    try:
        e_b.build_database(str(nguon), mode="new")
    finally:
        monkeypatch.setattr(os, "replace", that)
    assert da_chan, "đường lui PermissionError phải được kích hoạt"
    assert os.path.normcase(e_b.db_file) != os.path.normcase(str(db_cu)), \
        "build phải công bố sang file mới"

    # Phiên A vẽ lại trang rồi bắt đầu một lượt quét mới.
    e_a.list_khos()
    e_a.db_clips()
    job_a = e_a._ban_sao_cho_job()
    loi = []
    if os.path.normcase(job_a.db_file) != os.path.normcase(e_b.db_file):
        loi.append(f"lượt quét mới ở phiên khác vẫn so với kho CŨ {os.path.basename(job_a.db_file)} "
                   f"thay vì kho vừa công bố {os.path.basename(e_b.db_file)}")
    if not job_a.danh_tinh_kho().get("kho_id"):
        loi.append("định danh kho của lượt quét ở phiên khác RỖNG (sổ trỏ file khác file ghim)")
    assert not loi, "F-2 (b') kho lệch giữa phiên:\n- " + "\n- ".join(loi)


# ---------------------------------------------------------------- việc XONG khi không phiên nào vẽ

def test_lo_nguon_chung_xong_khi_khong_phien_nao_ve_phien_mo_sau_thay_ket_qua_dung_mot_lan(moi_truong, monkeypatch):
    """Lô xong lúc tab bị dỡ / PC ngủ (không phiên nào vẽ): KetQuaLo không ghi lịch sử (D-5) nên phiên MỞ SAU phải
    nhận kết quả cuối (kết luận + nút lưu CSV) — đúng một lần, như tác vụ nền (review audit D)."""
    from test_nguon_chung_ui import _kql

    at1 = moi_truong

    def chay_gia(self, job, ma_lo, nguon, source_type):
        return _kql()

    monkeypatch.setattr(CommonOriginalJobController, "_chay_da_khoa", chay_gia)
    ctl1 = at1.session_state.common_controller
    ctl1.start(["https://youtu.be/vid00000001"], "youtube")
    _cho_het(lambda: ctl1.running)          # phiên #1 không vẽ lại nữa
    assert ctl1.result is not None

    at2 = _phien_moi()
    nut_csv = [b for b in at2.button if b.key == "luu_csv_nguon_chung"]
    assert at2.session_state.job.get("kind") == "nguon_chung" and not at2.session_state.job.get("running")
    assert "VIDEO GỐC CHUNG" in _van_ban(at2) and nut_csv, "phiên mở sau phải thấy kết quả lô đã xong"
    # Phiên sau chép xong → controller của CHÍNH phiên (lưu CSV / lô sau dùng Engine của phiên).
    at2.run()
    assert at2.session_state.common_controller is not ctl1
    at3 = _phien_moi()
    assert not at3.session_state.job.get("kind"), "kết quả chỉ được nhận đúng một lần"


def test_build_xong_khi_khong_phien_nao_ve_phien_mo_sau_thay_file_loi(moi_truong, monkeypatch, tmp_path):
    at1 = moi_truong
    nguon = tmp_path / "ClipGoc"
    nguon.mkdir()
    (nguon / "00000000 - Clip một [aaaaaaaaaaa].opus").write_bytes(b"fixture")

    def build_gia(self, thumuc, mode="new", progress=None, tracker=None):
        return {"so_clip": 3, "da_xu_ly": 3, "thanh_cong": 2, "bo_qua": 0, "that_bai": 1,
                "giay": 1.0, "loi_file": ["Clip ba.opus: không tạo được hash"], "canh_bao": []}

    monkeypatch.setattr(Engine, "_build_database_da_khoa", build_gia)
    ctl1 = at1.session_state.fingerprint_controller
    ctl1.start(str(nguon), "new")
    _cho_het(lambda: ctl1.running)
    assert ctl1.result

    at2 = _phien_moi()
    assert at2.session_state.job.get("kind") == "db"
    assert "file có vấn đề" in _van_ban(at2), "phiên mở sau phải thấy danh sách file lỗi của build đã xong"
    at3 = _phien_moi()
    assert not at3.session_state.job.get("kind"), "kết quả chỉ được nhận đúng một lần"


def test_phien_khac_dang_dung_kho_thi_bat_dau_dung_kho_bi_tu_choi(tmp_path, monkeypatch):
    """Hai phiên rảnh cùng bấm dựng kho (khe giữa hai lần vẽ): controller thứ hai bị từ chối, chưa chạy gì."""
    from fingerprint_progress import FingerprintJobController
    from tac_vu_nen import DangCoTacVuKhac

    cho = threading.Event()

    def build_gia(self, thumuc, mode="new", **kw):
        cho.wait(10)
        return {"so_clip": 0}

    monkeypatch.setattr(Engine, "build_database", build_gia)
    e_a = Engine(data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e_b = Engine(data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    ctl_a, ctl_b = FingerprintJobController(e_a), FingerprintJobController(e_b)
    ctl_a.start(str(tmp_path), "new")
    try:
        with pytest.raises(DangCoTacVuKhac):
            ctl_b.start(str(tmp_path), "new")
        assert not ctl_b.running
        assert FingerprintJobController.cua_phien(e_b, ctl_b) is ctl_a     # phiên B rảnh nhận lại job của A
    finally:
        cho.set()
        _cho_het(lambda: ctl_a.running)
    assert FingerprintJobController.cua_phien(e_b, ctl_b) is ctl_b         # xong: B về controller của chính nó
