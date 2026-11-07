# -*- coding: utf-8 -*-
"""Kho video dài (D-34): thư mục kho đánh dấu ``channel.TEP_KHO_VIDEO_DAI``.

Đánh dấu thì đồng bộ và tạo vân tay nhận video tới ``GIAY_CLIP_TOI_DA_KHO_DAI``, kho mới lưu mốc thời gian đủ dài và
báo cáo chỉ ra đúng vùng khớp. Kho không đánh dấu giữ nguyên quy tắc 2 giờ của D-31. Không mạng.
"""
from __future__ import annotations

import gzip
import json
import os
import pickle

import pytest
from streamlit.testing.v1 import AppTest

import channel
from channel import ChannelSync
from conftest import _ghi_wav, _giai_dieu
from engine import Engine, Match, liet_ke_media
from scan_ui import tom_tat_dong_bo_kenh
from test_bo_clip_dai import GIO, _do_dai_gia, _engine, _gia_audfprint, _nguon, _video, hash_table


def _kenh_dai(tmp_path, *ds) -> ChannelSync:
    kho = tmp_path / "kho"
    kho.mkdir()
    channel.dat_kho_video_dai(str(kho), True)
    cs = ChannelSync(str(kho))
    cs.list_channel = lambda *a, **k: list(ds)
    return cs


def test_danh_dau_va_bo_danh_dau_tuy_chon_tran(tmp_path):
    kho = str(tmp_path)
    assert channel.tran_clip_giay(kho) == channel.GIAY_CLIP_TOI_DA
    channel.dat_kho_video_dai(kho, True)
    channel.dat_kho_video_dai(kho, True)  # bật hai lần không lỗi
    assert channel.la_kho_video_dai(kho)
    assert channel.tran_clip_giay(kho) == channel.GIAY_CLIP_TOI_DA_KHO_DAI
    channel.dat_kho_video_dai(kho, False)
    channel.dat_kho_video_dai(kho, False)  # tắt hai lần không lỗi
    assert not channel.la_kho_video_dai(kho)
    assert channel.tran_clip_giay(kho) == channel.GIAY_CLIP_TOI_DA


def test_trang_danh_dau_khong_bi_tinh_la_media(tmp_path):
    channel.dat_kho_video_dai(str(tmp_path), True)
    assert liet_ke_media(str(tmp_path)) == []


def test_kho_dai_tai_video_dai_nhung_van_co_tran(tmp_path):
    tran = channel.GIAY_CLIP_TOI_DA_KHO_DAI
    cs = _kenh_dai(tmp_path, _video("nam_gio0000", 5 * GIO), _video("dung_tran00", tran),
                   _video("qua_tran000", tran + 1))
    da_thu = []

    def tai_gia(v):
        da_thu.append(v.id)
        raise RuntimeError("synthetic: không tải thật")

    cs._tai_va_nen = tai_gia
    kq = cs.sync("kenh")

    assert da_thu == ["nam_gio0000", "dung_tran00"]
    assert kq["qua_dai"] == 1
    assert kq["gio_toi_da"] == tran // 3600
    cau = [c for _, c in tom_tat_dong_bo_kenh(kq) if "được bỏ qua" in c]
    assert cau and f"dài hơn {tran // 3600} giờ" in cau[0]


def test_kiem_thieu_kho_dai_tinh_video_dai_la_con_thieu(tmp_path):
    cs = _kenh_dai(tmp_path, _video("nam_gio0000", 5 * GIO), _video("qua_tran000", 99 * GIO))
    kq = cs.kiem_tra_thieu("kenh")

    assert [v.id for v in kq["thieu"]] == ["nam_gio0000"]
    assert [v.id for v in kq["qua_dai"]] == ["qua_tran000"]
    assert kq["gio_toi_da"] == channel.GIAY_CLIP_TOI_DA_KHO_DAI // 3600


def _bat_lenh(e: Engine, da_chay: list) -> list:
    lenh_goc: list = []
    gia = _gia_audfprint(da_chay)

    def chay(lenh, on_line=None, **kw):
        lenh_goc.append(lenh)
        return gia(lenh, on_line, **kw)

    e._run_stream = chay
    return lenh_goc


def test_tao_kho_dai_giu_clip_dai_va_luu_du_bit(tmp_path, monkeypatch):
    nguon = _nguon(tmp_path, "nam_gio.opus", "qua_tran.opus")
    channel.dat_kho_video_dai(str(nguon), True)
    _do_dai_gia(monkeypatch, {"nam_gio.opus": 5, "qua_tran.opus": 14})
    e = _engine(tmp_path)
    e.add_kho("Dai", str(nguon))
    da_chay: list = []
    lenh = _bat_lenh(e, da_chay)

    kq = e.build_database(str(nguon), "new")

    assert da_chay == [[str(nguon / "nam_gio.opus")]]
    assert lenh[0][lenh[0].index("--maxtimebits") + 1] == str(channel.MAXTIMEBITS_KHO_DAI)
    assert any("qua_tran.opus" in c and "13 giờ" in c for c in kq["canh_bao"]), kq["canh_bao"]
    assert e._doc_khos()["danh_sach"][0]["maxtimebits"] == channel.MAXTIMEBITS_KHO_DAI
    assert e._kho_moc_dai()


def test_kho_thuong_van_16_bit_va_khong_mo_moc_dai(tmp_path, monkeypatch):
    nguon = _nguon(tmp_path, "ngan.opus")
    _do_dai_gia(monkeypatch, {})
    e = _engine(tmp_path)
    e.add_kho("Thuong", str(nguon))
    lenh = _bat_lenh(e, [])

    e.build_database(str(nguon), "new")

    assert lenh[0][lenh[0].index("--maxtimebits") + 1] == "16"
    assert not e._kho_moc_dai()


def test_bo_sung_vao_kho_16_bit_bi_chan_truoc_khi_ghi(tmp_path, monkeypatch):
    nguon = _nguon(tmp_path, "ngan.opus")
    _do_dai_gia(monkeypatch, {})
    e = _engine(tmp_path)
    e.add_kho("Cu", str(nguon))
    lenh = _bat_lenh(e, [])
    e.build_database(str(nguon), "new")
    truoc = json.dumps(e._doc_khos(), sort_keys=True)
    channel.dat_kho_video_dai(str(nguon), True)
    (nguon / "moi.opus").write_bytes(b"x")

    with pytest.raises(RuntimeError, match="Tạo lại"):
        e.build_database(str(nguon), "add")

    assert len(lenh) == 1, "không được chạy audfprint"
    assert json.dumps(e._doc_khos(), sort_keys=True) == truoc


def test_bo_sung_vao_kho_dai_van_chay(tmp_path, monkeypatch):
    nguon = _nguon(tmp_path, "mot.opus")
    channel.dat_kho_video_dai(str(nguon), True)
    _do_dai_gia(monkeypatch, {})
    e = _engine(tmp_path)
    e.add_kho("Dai", str(nguon))
    da_chay: list = []
    _bat_lenh(e, da_chay)
    e.build_database(str(nguon), "new")
    (nguon / "hai.opus").write_bytes(b"x")

    e.build_database(str(nguon), "add")

    assert da_chay[-1] == [str(nguon / "hai.opus")]
    assert e._kho_moc_dai()


def test_qua_suc_chua_clip_bi_chan_truoc_khi_dung(tmp_path, monkeypatch):
    """Vượt sức chứa thì mã clip tràn sang mốc thời gian trong ô uint32: kho hỏng mà không có lỗi nào."""
    monkeypatch.setattr(channel, "MAXTIMEBITS_KHO_DAI", 31)  # sức chứa còn 1 clip
    nguon = _nguon(tmp_path, "mot.opus", "hai.opus")
    channel.dat_kho_video_dai(str(nguon), True)
    _do_dai_gia(monkeypatch, {})
    e = _engine(tmp_path)
    e.add_kho("Dai", str(nguon))
    lenh = _bat_lenh(e, [])

    with pytest.raises(RuntimeError, match="tối đa 1 clip"):
        e.build_database(str(nguon), "new")
    assert lenh == []


def test_tat_danh_dau_roi_bo_sung_van_tinh_suc_chua_theo_kho_that(tmp_path, monkeypatch):
    """Bit của kho nằm trong file kho, không đổi theo ô đánh dấu: tắt ô không được nới sức chứa."""
    monkeypatch.setattr(channel, "MAXTIMEBITS_KHO_DAI", 31)
    nguon = _nguon(tmp_path, "mot.opus")
    channel.dat_kho_video_dai(str(nguon), True)
    _do_dai_gia(monkeypatch, {})
    e = _engine(tmp_path)
    e.add_kho("Dai", str(nguon))
    lenh = _bat_lenh(e, [])
    e.build_database(str(nguon), "new")
    channel.dat_kho_video_dai(str(nguon), False)
    (nguon / "hai.opus").write_bytes(b"x")

    with pytest.raises(RuntimeError, match="tối đa 1 clip"):
        e.build_database(str(nguon), "add")
    assert len(lenh) == 1


def _dong_khop(bat_dau, t_clip) -> dict:
    return {"clip": "C:/kho/goc.opus", "bat_dau": bat_dau, "khop": 60.0, "t_clip": t_clip, "hash": 2000,
            "align": bat_dau - t_clip}


def _co_kho(tmp_path, bits) -> Engine:
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.add_kho("K", str(tmp_path))
    e._sua_khos(lambda d: d["danh_sach"][0].update(maxtimebits=bits))
    e._bang_tong_hash = lambda: ({}, {}, {})
    return e


def test_kho_dai_bao_dung_vung_khop_kho_thuong_giu_moc_dau_clip(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    dai = _co_kho(tmp_path / "a", channel.MAXTIMEBITS_KHO_DAI)
    thuong = _co_kho(tmp_path / "b", 16)
    tho = [_dong_khop(900.0, 10800.0)]

    a = dai._merge(tho)
    dai._gan_chi_so(a, 3600.0)
    assert a[0].start_hhmmss == "00:15:00"
    assert a[0].clip_bat_dau_s == 900.0
    assert a[0].clip_offset_s == pytest.approx(10800.0)
    assert a[0].vung == "Đầu"

    b = thuong._merge(tho)
    thuong._gan_chi_so(b, 3600.0)
    assert b[0].start_s == 0.0, "kho thường giữ nguyên cách tính mốc đầu clip"


def test_loi_doc_so_kho_khong_lam_hong_luot_quet(tmp_path):
    e = _co_kho(tmp_path, channel.MAXTIMEBITS_KHO_DAI)
    e._doc_khos = lambda: (_ for _ in ()).throw(OSError("đĩa lỗi"))
    m = Match(clip="c", start_s=1.0, end_s=61.0, matched_s=60.0, clip_offset_s=0.0, hashes=2000, confidence="",
              vung_khop_s=30.0)
    e._gan_chi_so([m], 100.0)
    assert m.start_s == 1.0


def _kho_dai_ba_clip(tmp_path, monkeypatch, *ten) -> tuple:
    """Kho sức chứa 3 clip đã dựng từ ``ten``: ``(engine, nguồn, lệnh đã chạy, clip đã xử lý)``."""
    monkeypatch.setattr(channel, "MAXTIMEBITS_KHO_DAI", 30)
    nguon = _nguon(tmp_path, *ten)
    channel.dat_kho_video_dai(str(nguon), True)
    _do_dai_gia(monkeypatch, {})
    e = _engine(tmp_path)
    e.add_kho("Dai", str(nguon))
    da_chay: list = []
    lenh = _bat_lenh(e, da_chay)
    e.build_database(str(nguon), "new")
    return e, nguon, lenh, da_chay


def test_suc_chua_tinh_ca_clip_con_van_tay_ma_file_da_vang(tmp_path, monkeypatch):
    """Clip vắng file vẫn giữ vân tay nên vẫn giữ mã: đếm file trong thư mục là thiếu, mã clip tràn."""
    e, nguon, lenh, da_chay = _kho_dai_ba_clip(tmp_path, monkeypatch, "a.opus", "b.opus")
    (nguon / "c.opus").write_bytes(b"x")
    e.build_database(str(nguon), "add")  # 2 + 1 = vừa đúng sức chứa: vẫn được
    assert da_chay[-1] == [str(nguon / "c.opus")]

    (nguon / "c.opus").replace(tmp_path / "c.opus")
    (nguon / "d.opus").write_bytes(b"x")

    with pytest.raises(RuntimeError, match="tối đa 3 clip"):
        e.build_database(str(nguon), "add")
    assert len(lenh) == 2, "không được chạy audfprint"


def test_merge_cap_ma_tu_do_dai_names_khong_dung_lai_o_da_go():
    """Mọi lượt dựng đi qua `merge`: ô `None` sau `remove` vẫn tiêu hao mã clip tới lúc tạo lại kho."""
    goc = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
    goc.store("a", [(1, 1)])
    goc.store("b", [(2, 2)])
    goc.remove("b")
    them = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
    them.store("moi", [(3, 3)])

    goc.merge(them)

    assert goc.names == ["a", None, "moi"]


def test_suc_chua_tinh_ca_o_da_go_trong_kho(tmp_path, monkeypatch):
    e, nguon, lenh, _ = _kho_dai_ba_clip(tmp_path, monkeypatch, "a.opus", "b.opus", "c.opus")
    with gzip.open(e.db_file, "rb") as f:
        ht = pickle.load(f)
    ht.remove(str(nguon / "c.opus"))
    with gzip.open(e.db_file, "wb") as f:
        pickle.dump(ht, f)
    (nguon / "c.opus").unlink()
    (nguon / "d.opus").write_bytes(b"x")

    with pytest.raises(RuntimeError, match="tối đa 3 clip"):
        e.build_database(str(nguon), "add")
    assert len(lenh) == 1, "không được chạy audfprint"

    # Câu lỗi khuyên «Tạo lại từ đầu»: lối thoát đó phải chạy được khi kho đã hết mã, và thu hồi ô đã gỡ.
    e.build_database(str(nguon), "new")
    assert e.db_clips(bo_cache=True).so_ma_clip == 3


def test_ghi_so_loi_sau_cong_bo_van_theo_bit_that_cua_file_kho(tmp_path, monkeypatch):
    """Kho đã thành 21 bit mà sổ còn ghi 16: mốc phải theo file kho, không được về 00:00:00."""
    nguon = _nguon(tmp_path, "a.opus")
    _do_dai_gia(monkeypatch, {})
    e = _engine(tmp_path)
    e.add_kho("Cu", str(nguon))
    da_chay: list = []
    _bat_lenh(e, da_chay)
    e.build_database(str(nguon), "new")
    channel.dat_kho_video_dai(str(nguon), True)
    sua_that = e._sua_khos

    def sua_loi(_ham):
        raise OSError("synthetic: sổ đăng ký đang bị khoá")

    e._sua_khos = sua_loi
    kq = e.build_database(str(nguon), "new")
    e._sua_khos = sua_that

    assert any("sổ đăng ký" in c for c in kq["canh_bao"]), kq["canh_bao"]
    assert e._doc_khos()["danh_sach"][0]["maxtimebits"] == channel.MAXTIMEBITS_MAC_DINH

    ket_qua = e._merge([_dong_khop(900.0, 10800.0)])
    e._gan_chi_so(ket_qua, 3600.0)
    assert ket_qua[0].start_hhmmss == "00:15:00"

    # «Bổ sung» cũng theo file kho: không từ chối oan một kho thật sự 21 bit.
    (nguon / "b.opus").write_bytes(b"x")
    e.build_database(str(nguon), "add")
    assert da_chay[-1] == [str(nguon / "b.opus")]


def test_giao_dien_bat_tat_kho_video_dai(tmp_path, monkeypatch):
    import test_app as ta

    kho = tmp_path / "kho_dai"
    kho.mkdir()
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    at = AppTest.from_file(str(ta.APP_PY), default_timeout=120).run()
    o = next(x for x in at.text_input if x.label.startswith("Thư mục kho clip gốc"))
    o.set_value(str(kho)).run()
    hop = [c for c in at.checkbox if c.label.startswith("Kho video dài")]
    assert hop and not hop[0].value

    hop[0].check().run()

    assert channel.la_kho_video_dai(str(kho))
    assert [c for c in at.checkbox if c.label.startswith("Kho video dài")][0].value
    assert not at.exception


@pytest.mark.slow
def test_audio_that_clip_dai_hon_mot_vong_van_dung_moc(tmp_path):
    """Mốc 28 phút vượt vòng cũ 25,4 phút: kho dài phải báo đúng giây trong clip và đúng đoạn vi phạm."""
    sr = 11025
    goc = _giai_dieu(1740, seed=71, sr=sr)
    kho = tmp_path / "kho"
    kho.mkdir()
    _ghi_wav(kho / "goc_dai.wav", goc, sr)
    channel.dat_kho_video_dai(str(kho), True)
    e = Engine(root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
               data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.add_kho("Dai", str(kho))
    e.build_database(str(kho), "new")
    nen = _giai_dieu(240, seed=72, sr=sr) * 0.6
    i, tu, dai = 120 * sr, 1680 * sr, 60 * sr
    nen[i:i + dai] = goc[tu:tu + dai]
    video = tmp_path / "vi_pham.wav"
    _ghi_wav(video, nen, sr)

    kq = e.scan_media(str(video))

    assert kq.matches, "phải tìm thấy đoạn sao chép"
    m = kq.matches[0]
    assert m.clip_offset_s == pytest.approx(1680, abs=5)
    assert m.start_s == pytest.approx(120, abs=5)
