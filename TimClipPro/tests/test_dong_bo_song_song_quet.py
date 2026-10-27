# -*- coding: utf-8 -*-
"""Đồng bộ kênh chạy SONG SONG với quét (người dùng duyệt 27/10/2026, hướng B).

Người dùng: một tab đồng bộ kho MỚI (nhiều giờ), một tab quét video vi phạm theo kho ĐÃ đồng bộ xong — không chờ
đồng bộ xong mới quét. Trước đây mọi việc dài dùng chung MỘT ``job`` + MỘT cờ huỷ ``eng.cancel_event`` mỗi phiên
(TCP-13): đang đồng bộ thì cả trang chỉ còn màn tiến độ, tab mới nhận lại lượt đồng bộ và không quét được, ô đổi kho
bị khoá.

Bất biến mới:
- Đồng bộ kênh = làn RIÊNG (``job_dong_bo`` + cờ huỷ riêng), tối đa 1 lượt mỗi thư mục dữ liệu; các tab vẫn hiện.
- Quét / dựng vân tay / lô «Một video gốc chung» vẫn là làn chính như cũ (một việc mỗi lúc).
- Dừng quét không dừng đồng bộ và ngược lại; bắt đầu quét không xoá cú bấm Dừng đồng bộ đang chờ.
- Đang đồng bộ vẫn đổi được «Kho đang dùng» (lượt đồng bộ đã ghim thư mục đích lúc bấm).
- Dựng vân tay đúng thư mục đang đồng bộ (và ngược lại) bị từ chối — tránh nạp file đang tải dở.
- Tải lại trang thấy CẢ HAI việc; lượt đồng bộ xong giữa lúc quét hiện kết quả mà không cắt lô quét.

Mọi thứ synthetic: thư mục tạm, đồng bộ/quét/dựng kho giả chặn bằng ``threading.Event``, không mạng.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from channel import ChannelSync
from engine import Engine, ScanResult

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
NHAN_KENH = "Link kênh YouTube của bạn"
NHAN_KHO = "Thư mục kho clip gốc (ổ D, E... tùy bạn)"
NHAN_FILE = "Đường dẫn file hoặc thư mục"
NHAN_THU_MUC_KHO = "Đường dẫn thư mục chứa video gốc của kho này"
NUT_DONG_BO = "⬇️ Bắt đầu đồng bộ kênh"
NUT_DUNG = "⏹️ Dừng lại"
NUT_DUNG_DONG_BO = "⏹️ Dừng đồng bộ"
KHOA_DUNG_DONG_BO = "dung_dong_bo"


def _o(at, nhan):
    return next(x for x in at.text_input if x.label == nhan)


def _nut(at, nhan, key=None):
    return next((b for b in at.button if b.label == nhan and (key is None or b.key == key)), None)


def _nut_dung_quet(at):
    return next((b for b in at.button if b.label == NUT_DUNG and b.key != KHOA_DUNG_DONG_BO), None)


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


class _Gia:
    """Đồng bộ, quét file và dựng kho GIẢ — mỗi việc chặn tới khi được thả hoặc bị huỷ."""

    def __init__(self):
        self.dong_bo_bat_dau = threading.Event()
        self.tha_dong_bo = threading.Event()
        self.luot_dong_bo: list = []          # (ChannelSync, cancel_check)
        self.quet_bat_dau = threading.Event()
        self.tha_quet = threading.Event()
        self.dung_kho_bat_dau = threading.Event()
        self.tha_dung_kho = threading.Event()
        self.thu_muc_dung_kho: list = []

    def tha_het(self):
        self.tha_dong_bo.set()
        self.tha_quet.set()
        self.tha_dung_kho.set()


@pytest.fixture()
def gia(tmp_path, monkeypatch):
    import streamlit

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    g = _Gia()

    def sync_gia(self, url, limit, progress, cancel_check, thu_lai_han_che=False):
        g.luot_dong_bo.append((self, cancel_check))
        g.dong_bo_bat_dau.set()
        if progress:
            progress(0.1, "Đang tải video giả 1/3")
        _cho(lambda: g.tha_dong_bo.is_set() or (cancel_check is not None and cancel_check()), 60.0)
        huy = bool(cancel_check and cancel_check())
        return {"tong": 3, "moi": 0 if huy else 3, "bo_qua": 0, "loi": [], "thu_muc": self.dest,
                "da_huy": huy, "nghi_hong": [], "da_cach_ly": [], "da_doi_soat": 0, "chan_youtube": "",
                "youtube": {}, "trang_thai": "DA_HUY" if huy else "DAY_DU", "can_tai": 3, "so_loi": 0,
                "chua_thu": 3 if huy else 0, "gioi_han_tuoi": 0, "chi_hoi_vien": 0, "xac_thuc": {},
                "han_che_bo_qua": 0, "canh_bao_cookie": ""}

    def scan_media_gia(self, path, label=None, ref="", progress=None, **kw):
        g.quet_bat_dau.set()
        _cho(lambda: g.tha_quet.is_set() or self.cancel_event.is_set(), 60.0)
        return ScanResult(source_name=str(path), source_ref=str(path))

    def build_gia(self, thumuc, mode="new", progress=None, progress_event=None, job_id=None, **kw):
        g.thu_muc_dung_kho.append(thumuc)
        g.dung_kho_bat_dau.set()
        _cho(lambda: g.tha_dung_kho.is_set() or self.cancel_event.is_set(), 60.0)
        return {"da_xu_ly": 0, "so_clip": 0, "thanh_cong": 0, "bo_qua": 0, "that_bai": 0, "loi_file": []}

    goc_check_env = Engine.check_env

    def check_env_co_kho(self):
        env = goc_check_env(self)
        env["database"] = True
        return env

    monkeypatch.setattr(ChannelSync, "_sync_da_khoa", sync_gia)
    monkeypatch.setattr(Engine, "scan_media", scan_media_gia)
    monkeypatch.setattr(Engine, "build_database", build_gia)
    monkeypatch.setattr(Engine, "check_env", check_env_co_kho)
    # Màn tiến độ tự st.rerun() mãi: thay bằng st.stop() — lượt vẽ KẾT THÚC đúng chỗ như ngoài đời (phần sau
    # st.rerun() không chạy, vd. các tab dưới màn tiến độ) mà không lặp vô hạn; at.run() sau = lượt vẽ kế.
    monkeypatch.setattr(streamlit, "rerun", lambda *a, **k: streamlit.stop())
    yield g
    g.tha_het()
    import tac_vu_nen
    _cho(lambda: all(not tv.running for tv in list(tac_vu_nen.SO_TAC_VU_NEN._dang_chay.values())), 20.0)


def _phien_moi() -> AppTest:
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def _bat_dau_dong_bo(at, g, kho: Path) -> None:
    _o(at, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
    _o(at, NHAN_KHO).set_value(str(kho))
    at.run()
    _nut(at, NUT_DONG_BO).click().run()
    assert not at.exception, at.exception
    assert g.dong_bo_bat_dau.wait(15), "thiết lập: lượt đồng bộ giả không chạy"
    at.run()


def _bat_dau_quet_file(at, g, file_quet: Path) -> None:
    _o(at, NHAN_FILE).set_value(str(file_quet))
    at.run()
    nut = _nut(at, "🚀 Bắt đầu quét", key="quet_file")
    assert nut is not None and not nut.disabled, "nút quét file phải bấm được khi đang đồng bộ"
    nut.click().run()
    assert not at.exception, at.exception


def _file_gia(tmp_path) -> Path:
    f = tmp_path / "video_vi_pham.wav"
    f.write_bytes(b"RIFF0000WAVE")
    return f


# ---------------------------------------------------------------------------------------------------- 1

def test_dang_dong_bo_tab_quet_van_dung_duoc_va_hai_nut_dung_khong_dung_nham(gia, tmp_path):
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at = _phien_moi()
    _bat_dau_dong_bo(at, gia, kho)
    _, cancel_dong_bo = gia.luot_dong_bo[0]

    chu = _van_ban(at)
    assert any(x.label == NHAN_FILE for x in at.text_input), (
        "đang đồng bộ: các tab (Quét file, Quét YouTube, …) phải còn hiện — không phải chỉ màn tiến độ đồng bộ")
    assert _nut(at, NUT_DUNG_DONG_BO, key=KHOA_DUNG_DONG_BO) is not None, "khung đồng bộ phải có nút Dừng riêng"
    assert "Đang đồng bộ kênh" in chu

    _bat_dau_quet_file(at, gia, _file_gia(tmp_path))
    assert gia.quet_bat_dau.wait(15), "lô quét file phải chạy song song với đồng bộ"
    at.run()
    ctl = at.session_state.scan_controller
    assert ctl.running and at.session_state.job.get("kind") == "scan"
    assert not cancel_dong_bo(), "bắt đầu quét không được đụng lượt đồng bộ"
    assert _nut(at, NUT_DUNG_DONG_BO, key=KHOA_DUNG_DONG_BO) is not None, "màn quét vẫn phải hiện khung đồng bộ + nút Dừng"

    # Dừng LÔ QUÉT: đồng bộ phải chạy tiếp.
    _nut_dung_quet(at).click().run()
    assert _cho(lambda: not ctl.running, 15.0)
    assert not cancel_dong_bo(), "Dừng lô quét đã dừng nhầm lượt đồng bộ"
    import tac_vu_nen
    tv = tac_vu_nen.dang_chay_cua(at.session_state.eng)
    assert tv is not None and tv.kind == "channel" and tv.running

    # Dừng ĐỒNG BỘ: đúng lượt đồng bộ dừng.
    at.run()
    _nut(at, NUT_DUNG_DONG_BO, key=KHOA_DUNG_DONG_BO).click().run()
    assert _cho(lambda: cancel_dong_bo(), 10.0), "nút Dừng của khung đồng bộ không tới được lượt đồng bộ"


def test_dung_dong_bo_khong_dung_lo_quet_va_bat_dau_quet_khong_xoa_cu_bam_dung(gia, tmp_path):
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at = _phien_moi()
    _bat_dau_dong_bo(at, gia, kho)
    _, cancel_dong_bo = gia.luot_dong_bo[0]
    _bat_dau_quet_file(at, gia, _file_gia(tmp_path))
    assert gia.quet_bat_dau.wait(15)
    at.run()
    _nut(at, NUT_DUNG_DONG_BO, key=KHOA_DUNG_DONG_BO).click().run()
    assert _cho(lambda: cancel_dong_bo(), 10.0)
    eng = at.session_state.eng
    assert not eng.cancel_event.is_set(), "Dừng đồng bộ đã đặt cờ huỷ của Engine → lô quét bị dừng nhầm"
    assert at.session_state.scan_controller.running


# ---------------------------------------------------------------------------------------------------- 2

def test_dang_dong_bo_doi_kho_dang_dung_duoc(gia, tmp_path):
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at = _phien_moi()
    eng = at.session_state.eng
    eng.add_kho("Kho A")
    eng.add_kho("Kho B")
    at.run()
    _bat_dau_dong_bo(at, gia, kho)
    o = next(x for x in at.selectbox if x.label == "Chọn kho để quét")
    assert not o.disabled, "đang đồng bộ: ô «Kho đang dùng» phải đổi được (lượt đồng bộ đã ghim thư mục đích)"


# ---------------------------------------------------------------------------------------------------- 3

def test_dong_bo_thu_hai_khi_dang_dong_bo_bi_chan(gia, tmp_path):
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    kho2 = tmp_path / "KhoKhac"
    kho2.mkdir()
    at = _phien_moi()
    _bat_dau_dong_bo(at, gia, kho)
    _o(at, NHAN_KHO).set_value(str(kho2))
    at.run()
    nut = _nut(at, NUT_DONG_BO)
    if nut is not None and not nut.disabled:
        nut.click().run()
        time.sleep(0.5)
    assert len(gia.luot_dong_bo) == 1, "hai lượt đồng bộ cùng lúc (rủi ro YouTube chặn cookie) phải bị chặn"
    nut_ten = _nut(at, "🌐 Lấy lại tên video thật cho kho này")
    assert nut_ten is not None and nut_ten.disabled, (
        "đang đồng bộ: «Lấy lại tên» (tác vụ mạng cùng ghi metadata kho) phải chờ")


# ---------------------------------------------------------------------------------------------------- 4

def test_dung_van_tay_dung_thu_muc_dang_dong_bo_bi_tu_choi_thu_muc_khac_thi_chay(gia, tmp_path):
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    kho_khac = tmp_path / "KhoDaDongBo"
    kho_khac.mkdir()
    at = _phien_moi()
    at.session_state.eng.add_kho("Kho A")
    at.run()
    _bat_dau_dong_bo(at, gia, kho)

    _o(at, NHAN_THU_MUC_KHO).set_value(str(kho))
    at.run()
    _nut(at, "➕ Bổ sung clip mới vào kho").click().run()
    time.sleep(0.3)
    assert not gia.dung_kho_bat_dau.is_set(), "dựng vân tay trên thư mục ĐANG đồng bộ phải bị từ chối"
    assert "đang đồng bộ" in "\n".join(str(w.value) for w in at.warning).lower()

    at.run()
    _o(at, NHAN_THU_MUC_KHO).set_value(str(kho_khac))
    at.run()
    _nut(at, "➕ Bổ sung clip mới vào kho").click().run()
    assert gia.dung_kho_bat_dau.wait(10), "dựng vân tay thư mục KHÁC phải chạy được khi đang đồng bộ"


def test_dang_dung_van_tay_thi_dong_bo_vao_cung_thu_muc_bi_tu_choi(gia, tmp_path):
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at = _phien_moi()
    at.session_state.eng.add_kho("Kho A")
    at.run()
    _o(at, NHAN_THU_MUC_KHO).set_value(str(kho))
    at.run()
    _nut(at, "➕ Bổ sung clip mới vào kho").click().run()
    assert gia.dung_kho_bat_dau.wait(10)
    at2 = _phien_moi()     # tab khác: đang dựng vân tay ở tab kia
    _o(at2, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
    _o(at2, NHAN_KHO).set_value(str(kho))
    at2.run()
    nut = _nut(at2, NUT_DONG_BO)
    assert nut is not None, "màn tiến độ dựng vân tay phải có ô bắt đầu đồng bộ song song"
    nut.click().run()
    time.sleep(0.5)
    at2.run()                                 # lượt vẽ kế (st.rerun ngoài đời)
    assert not gia.dong_bo_bat_dau.is_set(), "đồng bộ vào thư mục đang dựng vân tay phải bị từ chối"
    assert "đang được tạo vân tay" in "\n".join(str(w.value) for w in at2.warning)


def test_dang_quet_bat_dau_dong_bo_tu_man_tien_do_quet(gia, tmp_path):
    """Chiều ngược lại: lô quét đã chạy TRƯỚC (cả trang là màn tiến độ quét) — vẫn bắt đầu đồng bộ được."""
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at = _phien_moi()
    _bat_dau_quet_file(at, gia, _file_gia(tmp_path))
    assert gia.quet_bat_dau.wait(15)
    at.run()
    assert "Đang quét video" in _van_ban(at)
    _o(at, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
    _o(at, NHAN_KHO).set_value(str(kho))
    _nut(at, NUT_DONG_BO).click().run()
    assert not at.exception, at.exception
    assert gia.dong_bo_bat_dau.wait(15), "đang quét: ô đồng bộ trên màn tiến độ phải khởi động được lượt đồng bộ"
    at.run()
    assert at.session_state.scan_controller.running
    assert _nut(at, NUT_DUNG_DONG_BO, key=KHOA_DUNG_DONG_BO) is not None and "Đang quét video" in _van_ban(at)


# ---------------------------------------------------------------------------------------------------- 5

def test_tai_lai_trang_thay_ca_dong_bo_va_lo_quet(gia, tmp_path):
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at = _phien_moi()
    _bat_dau_dong_bo(at, gia, kho)
    _, cancel_dong_bo = gia.luot_dong_bo[0]
    _bat_dau_quet_file(at, gia, _file_gia(tmp_path))
    assert gia.quet_bat_dau.wait(15)

    at2 = _phien_moi()
    chu = _van_ban(at2)
    assert "Đang quét video" in chu, "phiên mới phải nhận lại lô quét"
    assert "Đang đồng bộ kênh" in chu, "phiên mới phải thấy lượt đồng bộ đang chạy"
    nut = _nut(at2, NUT_DUNG_DONG_BO, key=KHOA_DUNG_DONG_BO)
    assert nut is not None
    nut.click().run()
    assert _cho(lambda: cancel_dong_bo(), 10.0), "Dừng đồng bộ từ phiên mới phải tới đúng lượt"
    assert at.session_state.scan_controller.running, "Dừng đồng bộ ở phiên mới đã dừng nhầm lô quét"


def test_phien_moi_khi_chi_dang_dong_bo_van_quet_duoc(gia, tmp_path):
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at = _phien_moi()
    _bat_dau_dong_bo(at, gia, kho)
    at2 = _phien_moi()                    # tab thứ hai mở trong lúc đồng bộ
    assert "Đang đồng bộ kênh" in _van_ban(at2)
    _bat_dau_quet_file(at2, gia, _file_gia(tmp_path))
    assert gia.quet_bat_dau.wait(15), "tab thứ hai phải quét được trong lúc tab kia đồng bộ"


# ---------------------------------------------------------------------------------------------------- 6

def test_dong_bo_xong_giua_luc_quet_hien_ket_qua_khong_cat_lo_quet(gia, tmp_path):
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at = _phien_moi()
    _bat_dau_dong_bo(at, gia, kho)
    _bat_dau_quet_file(at, gia, _file_gia(tmp_path))
    assert gia.quet_bat_dau.wait(15)
    gia.tha_dong_bo.set()
    import tac_vu_nen
    assert _cho(lambda: tac_vu_nen.dang_chay_cua(at.session_state.eng) is None, 15.0)
    at.run()
    assert at.session_state.scan_controller.running and at.session_state.job.get("kind") == "scan"
    assert "Đang quét video" in _van_ban(at), "lượt đồng bộ xong không được cắt màn tiến độ của lô quét"
    assert any("Đồng bộ xong" in str(x.value) for x in at.success), "phải hiện kết quả lượt đồng bộ"
    # Đóng kết quả đồng bộ → hết hiện, lô quét vẫn chạy.
    nut = _nut(at, "Đóng kết quả đồng bộ")
    assert nut is not None
    nut.click().run()
    at.run()                              # lượt vẽ kế (st.rerun ngoài đời)
    assert not any("Đồng bộ xong" in str(x.value) for x in at.success)
    assert at.session_state.scan_controller.running


# ---------------------------------------------------------------------------------------------------- 7 thuần

def test_thu_muc_chong_nhau():
    import tac_vu_nen

    assert tac_vu_nen.thu_muc_chong_nhau(r"E:\Kho\A", r"e:\kho\a\\")
    assert tac_vu_nen.thu_muc_chong_nhau(r"E:\Kho\A", r"E:\Kho\A\con")
    assert tac_vu_nen.thu_muc_chong_nhau(r"E:\Kho\A\con", r"E:\Kho\A")
    assert not tac_vu_nen.thu_muc_chong_nhau(r"E:\Kho\A", r"E:\Kho\AB")
    assert not tac_vu_nen.thu_muc_chong_nhau(r"E:\Kho\A", r"E:\Kho\B")
    assert not tac_vu_nen.thu_muc_chong_nhau("", r"E:\Kho\B")


# ---------------------------------------------------------------------------------------------------- review độc lập

def test_duong_dan_kho_hong_khong_giu_lease_bao_tri(gia, tmp_path):
    """Review P2-1: ``ChannelSync(...)`` ném lỗi (thư mục kho nằm dưới một FILE, ổ đĩa rút ra…) — không được để lại
    lease cổng bảo trì: bộ cập nhật sẽ thấy «đang có việc» tới khi tắt Tool. Lỗi phải báo rõ, không làm sập trang."""
    import gc

    chan = tmp_path / "la_file.txt"
    chan.write_text("x")
    at = _phien_moi()
    eng = at.session_state.eng
    _o(at, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
    _o(at, NHAN_KHO).set_value(str(chan / "con"))
    at.run()
    _nut(at, NUT_DONG_BO).click().run()
    gc.collect()
    assert not eng.cong_bao_tri.viec_dang_chay(), "lease bảo trì còn giữ dù không có việc nào chạy"
    assert not at.exception, at.exception
    assert any("Chưa đồng bộ được" in str(e.value) for e in at.error)
    assert not gia.dong_bo_bat_dau.is_set() and not at.session_state.job_dong_bo.get("running")


def test_loi_tu_choi_o_o_dong_bo_tren_man_tien_do_khong_bien_mat(gia, tmp_path):
    """Review P2-2: màn tiến độ quét / dựng vân tay tự vẽ lại mỗi 0,75 giây — lời từ chối của ô đồng bộ song song phải
    còn ở lượt vẽ SAU (tới lần bấm kế), không chỉ nháy một khung."""
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at = _phien_moi()
    at.session_state.eng.add_kho("Kho A")
    at.run()
    _o(at, NHAN_THU_MUC_KHO).set_value(str(kho))
    at.run()
    _nut(at, "➕ Bổ sung clip mới vào kho").click().run()
    assert gia.dung_kho_bat_dau.wait(10)
    at.run()
    _o(at, NHAN_KENH).set_value("https://www.youtube.com/@KenhGia")
    _o(at, NHAN_KHO).set_value(str(kho))
    _nut(at, NUT_DONG_BO).click().run()
    at.run()                                   # = lượt tự vẽ lại 0,75 giây sau
    assert not gia.dong_bo_bat_dau.is_set()
    assert any("đang được tạo vân tay" in str(w.value) for w in at.warning), "lời từ chối biến mất sau một khung"


def test_dong_bo_tu_tab_mo_truoc_khi_tab_kia_bat_dau_bi_chan_dung_ly_do(gia, tmp_path):
    """Review P3: tab B mở TRƯỚC khi tab A bắt đầu đồng bộ, rồi bấm đồng bộ — bị chặn bởi chính lượt đồng bộ (không
    phải lời «Lấy lại tên / Vá metadata»), và chỉ một lượt chạy."""
    kho = tmp_path / "KhoMoi"
    kho.mkdir()
    at_b = _phien_moi()
    _o(at_b, NHAN_KENH).set_value("https://www.youtube.com/@KenhKhac")
    _o(at_b, NHAN_KHO).set_value(str(tmp_path / "KhoB"))
    (tmp_path / "KhoB").mkdir()
    at_b.run()
    nut_b = _nut(at_b, NUT_DONG_BO)
    assert nut_b is not None and not nut_b.disabled     # tiền đề: tab B thấy nút bấm được (chưa có đồng bộ)
    at_a = _phien_moi()
    _bat_dau_dong_bo(at_a, gia, kho)
    nut_b.click().run()                                 # tab B bấm trên khung hình cũ
    time.sleep(0.5)
    assert len(gia.luot_dong_bo) == 1, "hai lượt đồng bộ cùng lúc từ hai tab"
    canh_bao = "\n".join(str(w.value) for w in at_b.warning)
    assert "Lấy lại tên" not in canh_bao, f"lời từ chối nêu sai lý do: {canh_bao!r}"
