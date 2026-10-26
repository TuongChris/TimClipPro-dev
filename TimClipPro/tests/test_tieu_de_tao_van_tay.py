# -*- coding: utf-8 -*-
"""Audit F-4: tiêu đề kết quả «Tạo / Bổ sung vân tay» phải theo KẾT QUẢ THẬT của lượt.

Tình huống (synthetic, không mạng, không audio thật): kho có 1 clip tốt; thư mục nguồn có thêm 3 clip mới đều giải
mã lỗi (file cụt, 0 hash…). audfprint chạy với --continue-on-error nên thoát 0, mỗi clip «failed», kho tạm 0 hash cho
cả 3 → Engine KHÔNG ghi kho (đúng, TCP-02) — nhưng màn hình vẽ tiêu đề xanh «✅ Hoàn tất tạo vân tay: đã xử lý 3/3
clip». Người dùng quét tiếp mà tưởng clip mới đã có vân tay → mọi bản re-upload của chúng bị bỏ sót, không lỗi nào.

Phán quyết (xet_tranh_cai.json, F-4): LỚP 1 (engine + tracker) GIỮ NGUYÊN — ``add`` không raise, kho giữ nguyên byte,
``da_ghi_kho=False``, sự kiện cuối ``status="completed"`` + không ghi DB (``completed`` = vòng đời job). CHỈ LỚP 2 (cách
trình bày cho người dùng: tiêu đề giao diện + chữ trạng thái CLI) là lỗi — giống đồng bộ kênh sau sự cố 15/10/2026
(``scan_ui.tom_tat_dong_bo_kenh``: chỉ xanh khi mọi việc đã xong thật).
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from kho_gia import ghi_kho, ghi_kho_tu_lenh
from scan_ui import tom_tat_tao_van_tay, trang_thai_tao_van_tay

PREFIX = "TIMCLIP_FINGERPRINT_EVENT "
APP_PY = Path(__file__).resolve().parents[1] / "app.py"

# Đúng hình dạng dict engine.build_database trả ở nhánh «không công bố» (bổ sung mà mọi clip mới đều lỗi).
KQ_MOI_CLIP_MOI_DEU_LOI = {
    "so_clip": 3, "da_xu_ly": 3, "thanh_cong": 0, "bo_qua": 0, "that_bai": 3,
    "da_huy": False,
    "loi_file": ["Lỗi clip moi_1.wav: ffmpeg", "Lỗi clip moi_2.wav: ffmpeg",
                 "Lỗi clip moi_3.wav: ffmpeg"],
    "giay": 4.0,
    "canh_bao": ["3 clip không tạo được vân tay: moi_1.wav, moi_2.wav, moi_3.wav.",
                 "Không có clip mới nào tạo được vân tay; không ghi lại kho — kho hiện "
                 "tại giữ nguyên."],
    "da_ghi_kho": False,
}
# Nhánh «Mọi clip đều đã có vân tay» (không có gì mới): dict cũ KHÔNG có khoá da_ghi_kho.
KQ_KHONG_CO_GI_MOI = {
    "so_clip": 5, "da_xu_ly": 0, "thanh_cong": 0, "bo_qua": 5, "that_bai": 0,
    "da_huy": False, "loi_file": [], "giay": 0.2, "canh_bao": [],
}
KQ_DAY_DU = {
    "so_clip": 4, "da_xu_ly": 4, "thanh_cong": 4, "bo_qua": 0, "that_bai": 0,
    "da_huy": False, "loi_file": [], "giay": 9.0, "canh_bao": [], "da_ghi_kho": True,
}
KQ_MOT_PHAN = {**KQ_DAY_DU, "thanh_cong": 3, "that_bai": 1, "loi_file": ["Lỗi clip x.wav"]}
KQ_DA_HUY = {
    "so_clip": 4, "da_xu_ly": 2, "thanh_cong": 0, "da_tinh_xong_chua_ghi": 2, "bo_qua": 0,
    "that_bai": 0, "da_huy": True, "loi_file": [], "giay": 3.0, "canh_bao": [],
}


# ---------------------------------------------------------------------------
#  LỚP 1 — engine + tracker GIỮ NGUYÊN (khoá phán quyết; KHÔNG dùng khẳng định «status != completed» của audit)
# ---------------------------------------------------------------------------

def _line(event, path, **extra):
    return PREFIX + json.dumps(
        {"event": event, "file": path, "process_pid": 4321, **extra},
        ensure_ascii=False,
    )


def _kho_va_clip_moi_deu_loi(engine, tmp_path):
    folder = tmp_path / "clips"
    folder.mkdir()
    ten = ("cu_tot.wav", "moi_1.wav", "moi_2.wav", "moi_3.wav")
    files = []
    for t in ten:
        p = folder / t
        p.write_bytes(b"fixture")
        files.append(str(p))
    files.sort()
    cu = next(f for f in files if f.endswith("cu_tot.wav"))
    # Kho cũ THẬT (HashTable audfprint): chỉ clip cũ có vân tay. Ghi SAU file clip để clip
    # cũ không bị coi là «file đã thay sau lần tạo kho».
    ghi_kho(engine.db_file, [(cu, 100)])
    moi = [f for f in files if f != cu]
    return folder, cu, moi


def test_bo_sung_ma_moi_clip_moi_deu_loi_engine_giu_hop_dong_tcp02(engine, tmp_path, monkeypatch):
    folder, _cu, moi = _kho_va_clip_moi_deu_loi(engine, tmp_path)
    truoc = Path(engine.db_file).read_bytes()
    monkeypatch.setattr(engine, "require", lambda **kwargs: None)
    da_gui = []

    def run_stream(command, on_line=None, **kwargs):
        listfile = command[command.index("--list") + 1]
        pending = [p for p in Path(listfile).read_text(encoding="utf-8").splitlines() if p]
        da_gui.extend(pending)
        for path in pending:
            on_line(_line("clip_started", path, phase="decoding"))
            on_line(_line(
                "clip_finished", path, status="failed", category="decode_error",
                message="ffmpeg: Invalid data found when processing input",
                elapsed_seconds=0.1, hash_count=0,
            ))
        # audfprint --continue-on-error: thoát 0, kho tạm = kho cũ + 0 hash cho clip lỗi.
        ghi_kho_tu_lenh(command, loi=tuple(pending))
        return 0, ["Saved fprints for 0 files"]

    monkeypatch.setattr(engine, "_run_stream", run_stream)
    events = []
    r = engine.build_database(str(folder), "add", progress_event=events.append)

    assert sorted(da_gui) == sorted(moi)
    assert r["thanh_cong"] == 0 and r["that_bai"] == 3 and r["da_huy"] is False
    assert r["da_ghi_kho"] is False
    assert Path(engine.db_file).read_bytes() == truoc, "kho cũ phải giữ nguyên"
    cuoi = events[-1]
    assert cuoi.status == "completed" and cuoi.last_db_write_at is None
    # … và chính dict đó KHÔNG được thành tiêu đề xanh.
    assert trang_thai_tao_van_tay(r) == "KHONG_GHI_CO_LOI"
    assert tom_tat_tao_van_tay(r)[0][0] == "error"


# ---------------------------------------------------------------------------
#  LỚP 2 — hàm thuần dựng tiêu đề (5 trường hợp của phán quyết)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kq, ma, muc", [
    (KQ_DA_HUY, "DA_HUY", "warning"),
    (KQ_MOI_CLIP_MOI_DEU_LOI, "KHONG_GHI_CO_LOI", "error"),
    (KQ_KHONG_CO_GI_MOI, "KHONG_CO_GI_MOI", "success"),
    (KQ_MOT_PHAN, "MOT_PHAN", "warning"),
    (KQ_DAY_DU, "DAY_DU", "success"),
])
def test_tieu_de_theo_ket_qua_that(kq, ma, muc):
    assert trang_thai_tao_van_tay(kq) == ma
    dong = tom_tat_tao_van_tay(kq)
    assert dong[0][0] == muc
    if ma != "DAY_DU":
        assert "Hoàn tất tạo vân tay" not in dong[0][1]


def test_tieu_de_moi_clip_moi_deu_loi_noi_ro_kho_giu_nguyen_va_quet_khong_nhan_ra():
    cau = tom_tat_tao_van_tay(KQ_MOI_CLIP_MOI_DEU_LOI)[0][1]
    assert "3/3" in cau and "giữ nguyên" in cau and "CHƯA có vân tay" in cau and "Bổ sung" in cau


def test_tieu_de_khong_loi_voi_dict_thieu_khoa():
    # Kết quả cũ / dở dang không được làm vỡ giao diện.
    assert tom_tat_tao_van_tay({})[0][0] in ("success", "info")
    assert tom_tat_tao_van_tay({"so_clip": 2, "that_bai": 2})[0][0] == "error"


# ---------------------------------------------------------------------------
#  LỚP 2 — giao diện (AppTest) và CLI
# ---------------------------------------------------------------------------

@pytest.fixture
def _app(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    kho_dir = tmp_path / "kho_gia"
    kho_dir.mkdir()
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    (data_dir / "khos.json").write_text(json.dumps({
        "dang_dung": "KhoTest",
        "danh_sach": [{"ten": "KhoTest", "thu_muc": str(kho_dir), "db": "kho_test.pklz"}],
    }, ensure_ascii=False), encoding="utf-8")
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception
    return at


def _ve_ket_qua(at, ket_qua):
    at.session_state.job.update({
        "running": False, "kind": "db", "results": ket_qua, "error": "",
        "fingerprint_job_id": "", "da_day_sheet": False,
    })
    at.run()
    assert not at.exception
    return at


def test_giao_dien_khong_bao_hoan_tat_xanh_khi_bo_sung_ma_moi_clip_deu_loi(_app):
    at = _ve_ket_qua(_app, KQ_MOI_CLIP_MOI_DEU_LOI)

    xanh = [s.value for s in at.success]
    assert not any("Hoàn tất tạo vân tay" in v for v in xanh), (
        f"0/3 clip mới tạo được vân tay, kho không ghi — nhưng tiêu đề xanh: {xanh}"
    )
    do = [e.value for e in at.error]
    assert any("giữ nguyên" in v for v in do), do
    # Số đếm + cảnh báo + danh sách lỗi vẫn như cũ.
    assert [m.value for m in at.metric][:3] == ["0", "0", "3"]
    assert any("không ghi lại kho" in w.value for w in at.warning)


def test_giao_dien_khong_co_gi_moi_khong_bao_dong(_app):
    at = _ve_ket_qua(_app, KQ_KHONG_CO_GI_MOI)
    assert not at.error
    assert any("Không có gì mới" in s.value for s in at.success)


def test_giao_dien_day_du_van_xanh(_app):
    at = _ve_ket_qua(_app, KQ_DAY_DU)
    assert not at.error
    assert any("Hoàn tất tạo vân tay" in s.value for s in at.success)


def test_cli_themclip_moi_clip_moi_deu_loi_khong_in_xong(monkeypatch, capsys, tmp_path):
    import cli

    class _EngineGia:
        def __init__(self):
            self.config = SimpleNamespace(ncores=1)
            self.data_dir = ""
            self.kho_dang_dung = ""
            self.canh_bao_khoi_dong = []

        def build_database(self, *a, **k):
            return dict(KQ_MOI_CLIP_MOI_DEU_LOI)

    monkeypatch.setattr("sys.argv", ["cli.py", "themclip", str(tmp_path)])
    monkeypatch.setattr(cli, "Engine", _EngineGia)

    cli.main()  # mã thoát giữ nguyên (engine không raise ở nhánh này)

    ra = capsys.readouterr().out
    assert "XONG:" not in ra
    assert "CHƯA BỔ SUNG ĐƯỢC CLIP NÀO" in ra
