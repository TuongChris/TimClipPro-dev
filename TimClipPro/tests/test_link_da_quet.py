# -*- coding: utf-8 -*-
"""Báo link đã quét (DT-09): dán 20 link, 8 link đã quét tuần trước với cùng kho → tool quét lại cả 8 (mỗi video có thể
hàng chục phút) và thêm dòng trùng lên Sheet; link dán hai lần trong một lô cũng quét hai lần.

Trang «Quét YouTube»: gộp link trùng theo mã video; tra lịch sử CHỈ ĐỌC theo đúng luật ``Engine.ids_da_quet`` (có vi
phạm: mọi phiên bản kho; không vi phạm: cùng phiên bản kho + chính sách; âm tính với kho CŨ: vẫn quét lại); ô «Bỏ qua
các link đã quét với kho này» mặc định KHÔNG tick (hành vi cũ). SQLite thật trong thư mục tạm, không mạng.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

import scan_jobs
from conftest import M
from engine import ScanResult
from kho_gia import ghi_kho
from scan_ui import gop_link_trung

APP_PY = Path(__file__).resolve().parents[1] / "app.py"
VP, KVP, CU, MOT_PHAN, LOI, KHO_B, MOI = ("vipham00001", "khongvp0001", "amtinhcu001", "motphan0001", "loi00000001",
                                          "chikhoB0001", "chuaquet001")


def _kq(ma, *, khop=False, tron=True, loi=False) -> ScanResult:
    kq = ScanResult(source_name=f"Video {ma}", source_ref=f"https://youtu.be/{ma}", source_id=ma, duration_s=100.0,
                    vung_da_khop=[(0.0, 100.0 if tron else 50.0)])
    if khop:
        kq.matches = [M()]
    if loi:
        kq.status = "error"
    return kq


def _kho(eng, tmp_path, ten="A", so_clip=1) -> None:
    thu_muc = tmp_path / f"nguon_{ten}"
    thu_muc.mkdir(exist_ok=True)
    if ten not in [k["ten"] for k in eng.list_khos()]:
        eng.add_kho(ten, str(thu_muc))
    ghi_kho(eng.db_file, [(str(thu_muc / f"goc{i}.opus"), 9) for i in range(so_clip)])


def test_gop_link_trung_theo_ma_video_giu_thu_tu():
    links = ["https://youtu.be/aaaaaaaaaaa", "https://www.youtube.com/watch?v=aaaaaaaaaaa&t=5",
             "https://youtu.be/bbbbbbbbbbb", "https://www.twitch.tv/videos/1", "https://www.twitch.tv/videos/1",
             "https://www.youtube.com/shorts/aaaaaaaaaaa"]
    assert gop_link_trung(links) == (
        ["https://youtu.be/aaaaaaaaaaa", "https://youtu.be/bbbbbbbbbbb", "https://www.twitch.tv/videos/1"], 3)
    assert gop_link_trung([]) == ([], 0)


def test_lan_quet_voi_kho_dung_luat_ids_da_quet(engine, tmp_path):
    _kho(engine, tmp_path)
    engine.save_job(_kq(VP, khop=True), "youtube")      # vi phạm thấy TRƯỚC lần bổ sung vẫn là đã thấy
    engine.save_job(_kq(CU), "youtube")                 # âm tính với kho trước khi bổ sung
    _kho(engine, tmp_path, so_clip=2)                   # «Bổ sung»: phiên bản kho mới
    engine.save_job(_kq(VP), "youtube")                 # lần sau không thấy: vẫn báo «có vi phạm»
    engine.save_job(_kq(KVP), "youtube")
    engine.save_job(_kq(MOT_PHAN, tron=False), "youtube")
    engine.save_job(_kq(LOI, loi=True), "youtube")
    _kho(engine, tmp_path, ten="B")
    engine.save_job(_kq(KHO_B, khop=True), "youtube")
    engine.use_kho("A")
    ids = [VP, KVP, CU, MOT_PHAN, LOI, KHO_B, MOI]

    lan = engine.lan_quet_voi_kho(ids)

    assert set(lan) == {VP, KVP, CU}
    assert lan[VP]["da_quet"] and lan[VP]["so_doan"] == 1
    assert lan[KVP]["da_quet"] and lan[KVP]["so_doan"] == 0 and lan[KVP]["tieu_de"] == f"Video {KVP}"
    assert lan[KVP]["ngay"][:4].isdigit()
    assert not lan[CU]["da_quet"]
    assert {m for m, v in lan.items() if v["da_quet"]} == engine.ids_da_quet() & set(ids)
    assert engine.lan_quet_voi_kho([]) == {}


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(APP_PY), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _tab_quet(at):
    return next(t for t in at.tabs if t.label == "▶️ Quét YouTube")


def _chu(tab) -> str:
    return "\n".join(str(x.value) for nhom in (tab.caption, tab.info, tab.warning, tab.markdown) for x in nhom)


def _bam_bat_dau(at) -> None:
    next(b for b in _tab_quet(at).button if b.label == "🚀 Bắt đầu quét").click().run()
    assert not at.exception, [e.value for e in at.exception]


def test_trang_quet_youtube_bao_link_da_quet_va_chi_bo_qua_khi_tick(tmp_path, monkeypatch):
    nhan = []

    def start(self, nguon, *a, **k):
        nhan.append(list(nguon))
        raise RuntimeError("test: không chạy lô thật")

    monkeypatch.setattr(scan_jobs.ScanJobController, "start", start)
    at = _app(tmp_path, monkeypatch)
    eng = at.session_state.eng
    _kho(eng, tmp_path, ten="SML")
    eng.save_job(_kq(VP, khop=True), "youtube")
    eng.save_job(_kq(KVP), "youtube")
    l_vp, l_kvp, l_moi = (f"https://youtu.be/{VP}", f"https://www.youtube.com/watch?v={KVP}",
                          f"https://youtu.be/{MOI}")
    at.text_area(key="quet_yt_links").set_value("\n".join([l_vp, l_kvp, l_moi, f"{l_vp}?t=30"])).run()
    assert not at.exception, [e.value for e in at.exception]
    chu = _chu(_tab_quet(at))
    assert "Đã nhận 3 link" in chu and "Đã gộp 1 link trùng" in chu
    assert "2/3 link đã quét với kho «SML»" in chu, chu
    assert f"Video {VP}" in chu and "có vi phạm" in chu and "không thấy vi phạm" in chu
    assert not at.checkbox(key="bo_qua_da_quet").value

    _bam_bat_dau(at)
    assert nhan[-1] == [l_vp, l_kvp, l_moi], "mặc định: quét lại cả link đã quét (hành vi cũ), link trùng đã gộp"

    at.checkbox(key="bo_qua_da_quet").check().run()
    _bam_bat_dau(at)
    assert nhan[-1] == [l_moi]
