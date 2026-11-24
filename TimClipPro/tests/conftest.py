# -*- coding: utf-8 -*-
"""Fixture dùng chung cho toàn bộ test. Sinh audio giả lập, không cần file thật."""
import importlib.util
import os
import sys
import wave

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# app.py dùng st.navigation (chỉ chạy trang đang mở); AppTest chỉ chuyển được trang dạng FILE nên bộ test vẽ MỌI
# trang trong 15 tab như trước 23/11 (nhánh TIMCLIP_UI_VE_MOI_TRANG ở cuối app.py). Test của chính menu tự bỏ biến này.
os.environ.setdefault("TIMCLIP_UI_VE_MOI_TRANG", "1")

# Chặn mạng cho cả bộ test, kể cả tiến trình con Python (việc nhỏ #60) — trước đây chỉ khi người chạy nhớ đặt
# PYTHONPATH tới bộ chặn ngoài. Đã có bộ chặn ngoài thì không cài chồng; THẬT cần mạng: TIMCLIP_TEST_CHO_MANG=1.
_CHAN_MANG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chan_mang")
_spec = importlib.util.spec_from_file_location("timclip_chan_mang", os.path.join(_CHAN_MANG, "sitecustomize.py"))
chan_mang = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chan_mang)
# Tiến trình con nạp nó như sitecustomize qua PYTHONPATH; đã có sitecustomize khác thì không che mất nó.
CHAN_CA_TIEN_TRINH_CON = chan_mang.TRANG_THAI == "cai" and "sitecustomize" not in sys.modules
if CHAN_CA_TIEN_TRINH_CON:
    os.environ["PYTHONPATH"] = os.pathsep.join(p for p in (_CHAN_MANG, os.environ.get("PYTHONPATH")) if p)


def _ghi_wav(path, sig, sr=22050):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(sig, -1, 1) * 32000).astype(np.int16).tobytes())


def _giai_dieu(dur_s, seed, sr=22050):
    """Chuỗi nốt ngẫu nhiên -> nhiều điểm mốc phổ, giống nhạc thật."""
    rng = np.random.default_rng(seed)
    n = int(dur_s / 0.4) + 1
    freqs = rng.uniform(200, 4000, n)
    t = np.arange(int(0.4 * sr)) / sr
    env = np.hanning(len(t))
    sig = np.concatenate([np.sin(2 * np.pi * f * t) * env for f in freqs])[: int(dur_s * sr)]
    return (sig + 0.02 * rng.standard_normal(len(sig))) * 0.7


@pytest.fixture(scope="session")
def bo_clip(tmp_path_factory):
    """4 clip gốc 30 giây + 1 video dài 6 phút chứa 3 clip ở vị trí đã biết."""
    d = tmp_path_factory.mktemp("kho")
    sr = 22050
    clips = []
    for i in range(4):
        c = _giai_dieu(30, seed=500 + i, sr=sr)
        clips.append(c)
        _ghi_wav(d / f"clip_{i}.wav", c, sr)

    dai = _giai_dieu(360, seed=777, sr=sr)
    vi_tri = {0: 30, 1: 160, 2: 300}          # clip index -> giây bắt đầu
    for idx, giay in vi_tri.items():
        i0 = int(giay * sr)
        dai[i0:i0 + len(clips[idx])] = clips[idx]
    vp = tmp_path_factory.mktemp("nguon") / "vi_pham.wav"
    _ghi_wav(vp, dai, sr)
    return {"kho": str(d), "vi_pham": str(vp), "vi_tri": vi_tri, "thoi_luong": 360.0}


@pytest.fixture(autouse=True)
def _tra_lai_main_module():
    """AppTest (Streamlit) để lại ``sys.modules['__main__']`` = module của app.py. Tiến trình con
    multiprocessing (spawn — Windows) của test SAU sẽ chạy lại app.py ở cấp module → dựng Engine trên
    ``data/`` mặc định của THƯ MỤC MÃ (máy thật: lịch sử thật, có thể khởi động người gửi Sheets).
    Trả lại ``__main__`` gốc sau mỗi test (tests/test_cach_ly_main_module.py)."""
    goc = sys.modules.get("__main__")
    yield
    if goc is not None and sys.modules.get("__main__") is not goc:
        sys.modules["__main__"] = goc


@pytest.fixture(autouse=True)
def _giu_nguyen_path():
    """``Engine(root=…)`` chèn ``<root>/bin`` vào PATH của CẢ tiến trình (engine.py, __init__).
    Mỗi test một thư mục tạm thì PATH dài dần tới giới hạn 32.767 ký tự của Windows và các test
    chạy SAU hỏng vì lý do không liên quan (gặp khi thêm bộ test báo cáo V2). Trả PATH về như cũ
    sau mỗi test — production chỉ tạo một Engine nên không bị ảnh hưởng."""
    cu = os.environ.get("PATH")
    yield
    if cu is None:
        os.environ.pop("PATH", None)
    else:
        os.environ["PATH"] = cu


@pytest.fixture()
def kha_nang_js_that():
    """Dùng phép kiểm THẬT của máy (``ytdlp_chung.kha_nang_js``: Node.js ≥ 22 + gói yt-dlp-ejs) thay cho bản giả mặc định
    của ``_may_giai_duoc_js_gia`` — chỉ cho test về chính phép kiểm đó."""
    import ytdlp_chung

    return ytdlp_chung.kha_nang_js


@pytest.fixture(autouse=True)
def _may_giai_duoc_js_gia(request, monkeypatch):
    """Cookie đăng nhập chỉ dùng được khi máy giải được thử thách JavaScript của YouTube — trạng thái của MÁY (có Node
    không, venv có gói yt-dlp-ejs không), khác nhau giữa các máy chạy test. Mặc định GIẢ «sẵn sàng» như bản phát hành có
    yt-dlp-ejs trên máy có Node.js, để test không phụ thuộc máy; test nào cần trạng thái khác thì tự đặt lại
    (tests/test_cookie_can_js.py), test về phép kiểm thật thì xin fixture ``kha_nang_js_that``."""
    if "kha_nang_js_that" in request.fixturenames:
        return
    import ytdlp_chung

    gia = ytdlp_chung.KhaNangJs(True, node=r"C:\gia\nodejs\node.exe", node_phien_ban="24.0.0",
                                ejs_phien_ban="0.8.0")
    monkeypatch.setattr(ytdlp_chung, "kha_nang_js", lambda: gia)


@pytest.fixture()
def khoa_api_that():
    """Đọc khoá YouTube Data API THẬT theo ``data_dir`` (``youtube_api._doc_khoa_cho``) thay cho «chưa có khoá» mặc định
    của ``_khong_co_khoa_api_gia`` — chỉ cho test về chính phép đọc khoá (file khoá GIẢ trong tmp_path)."""
    import youtube_api

    return youtube_api._doc_khoa_cho


@pytest.fixture(autouse=True)
def _khong_co_khoa_api_gia(request, monkeypatch):
    """Khoá YouTube Data API nằm NGOÀI repo, cạnh ``data_dir`` (D-51) — máy có khoá thật thì test không được gửi yêu cầu
    API nào. Mặc định GIẢ «chưa có khoá»: mọi đường gọi giữ nguyên đường yt-dlp cũ, 0 yêu cầu API. Test đường API xin
    fixture ``api_youtube_gia`` (tests/youtube_api_gia.py); test về chính phép đọc khoá xin ``khoa_api_that``."""
    if "khoa_api_that" in request.fixturenames:
        return
    import youtube_api

    monkeypatch.setattr(youtube_api, "_doc_khoa_cho", lambda data_dir: "")


@pytest.fixture()
def api_youtube_gia(tmp_path, monkeypatch):
    """Khoá GIẢ + YouTube Data API giả thay ``urllib.request.urlopen``; trả ``youtube_api_gia.TransportGia``."""
    import youtube_api_gia

    return youtube_api_gia.lap_api_gia(tmp_path, monkeypatch)


_DATA_CANH_MA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DATA_CANH_MA_CO_SAN = os.path.exists(_DATA_CANH_MA)


def pytest_sessionfinish(session, exitstatus):
    """Chốt cách ly: bộ test KHÔNG được tạo ``data/`` cạnh mã (trên máy thật đó là lịch sử, kho, khoá thật).
    Chỉ kiểm được khi thư mục CHƯA có lúc bắt đầu (bản gương, cây xuất từ git) — có sẵn thì bỏ qua."""
    if not _DATA_CANH_MA_CO_SAN and os.path.exists(_DATA_CANH_MA):
        print(f"\n[LỖI CÁCH LY] Bộ test đã tạo {_DATA_CANH_MA} — test phải dùng tmp_path / TIMCLIP_DATA_DIR.",
              file=sys.stderr)
        session.exitstatus = 1


@pytest.fixture()
def engine(tmp_path):
    """Engine sạch, dữ liệu ghi vào thư mục tạm — không đụng data/ thật."""
    from engine import Engine
    goc = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return Engine(
        root=goc,
        data_dir=str(tmp_path / "data"),
        out_dir=str(tmp_path / "ketqua"),
    )


def M(clip="a.opus", start=0.0, hashes=1000, matched=60.0, offset=0.0):
    """Tạo nhanh một Match giả để test thuần logic (không cần audio)."""
    from engine import Match
    return Match(clip=clip, start_s=start, end_s=start + matched, matched_s=matched,
                 clip_offset_s=offset, hashes=hashes, confidence="x")
