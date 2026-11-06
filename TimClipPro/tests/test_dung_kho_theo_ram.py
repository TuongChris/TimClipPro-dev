# -*- coding: utf-8 -*-
"""Dựng kho theo RAM (D-31) — sự cố 06/11/2026: clip 18,2 giờ + 8 worker làm cạn RAM, cả lượt sụp.

Bốn tính chất phải giữ:

1. Clip chỉ được phát khi RAM trống đủ cho nó CỘNG phần các clip đang chạy còn sẽ chiếm; clip dài xếp cuối.
2. Clip quá RAM bị bỏ qua có báo rõ, không làm sập lượt; một clip lỗi không kéo chết worker.
3. Tiến trình dựng và mọi tiến trình con chạy ưu tiên thấp.
4. Clip lỗi đọc/thiếu RAM được thử lại một mình cuối lượt, lý do thật không bị nuốt.

Chính sách là logic thuần nên được mô phỏng; phần tiến trình chạy bằng tiến trình con THẬT, chỉ thay phân tích audio.
Chỉ dữ liệu tổng hợp trong thư mục tạm.
"""

import json
import os
import random
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import audfprint_progress_runner as runner
from engine import Engine
from fingerprint_progress import FingerprintProgressTracker, tao_fingerprint_logger, dong_fingerprint_logger

REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "audfprint-master"
sys.path.insert(0, str(VENDOR))
import hash_table  # noqa: E402

GB_NGAN_SACH = 20.0
DU_PHONG = 3.0


def _clip(ten: str, can: float) -> runner.Clip:
    return runner.Clip(ten, can)


def _lich(clips, ncores=8, ram=GB_NGAN_SACH + DU_PHONG) -> runner.LichTheoRam:
    return runner.LichTheoRam(clips, ram, DU_PHONG, ncores)


# ---------------------------------------------------------------------------
#  1) Thứ tự phát
# ---------------------------------------------------------------------------

def test_clip_vua_phan_ram_giu_thu_tu_clip_dai_xep_cuoi_tang_dan():
    clips = [_clip("b", 1), _clip("dai_12", 12), _clip("a", 2), _clip("dai_5", 5), _clip("c", 1)]
    assert [c.file for c in _lich(clips).hang] == ["b", "a", "c", "dai_5", "dai_12"]


def test_mot_nhan_clip_ngan_giu_nguyen_thu_tu_danh_sach():
    clips = [_clip(f"c{i}", 1) for i in range(5)]
    assert [c.file for c in _lich(clips, ncores=1).hang] == [c.file for c in clips]


# ---------------------------------------------------------------------------
#  2) Điều kiện phát
# ---------------------------------------------------------------------------

def test_phat_khi_du_ram_cho_ca_clip_dang_chay():
    lich = _lich([_clip("a", 5), _clip("b", 5)])
    assert lich.buoc(23.0, 0.0, 0, 0.0) == ("giao", _clip("a", 5))
    # Vừa phát a: RAM trống chưa kịp giảm, nhưng a còn sẽ chiếm 5 GB.
    assert lich.buoc(23.0, 5.0, 1, 0.0) == ("giao", _clip("b", 5))


def test_khong_phat_khi_phan_clip_dang_chay_con_chiem_lam_vuot_ngan_sach():
    lich = _lich([_clip("b", 8)])
    # Trống 23 GB nhưng các clip đang chạy còn sẽ chiếm 14 GB: 23 - 14 - 8 < dự phòng 3.
    assert lich.buoc(23.0, 14.0, 2, 0.0) is None
    assert [c.file for c in lich.hang] == ["b"], "clip phải còn nguyên trong hàng"


# ---------------------------------------------------------------------------
#  3) Clip quá RAM: chờ có hạn, bỏ qua, không dừng cả lượt
# ---------------------------------------------------------------------------

def test_clip_qua_ram_cho_co_han_roi_bi_bo_qua():
    clip = _clip("sieu_dai", 28)
    lich = _lich([clip])
    assert lich.buoc(23.0, 0.0, 0, 100.0) == ("cho", clip)
    assert lich.buoc(23.0, 0.0, 0, 100.0 + runner.CHO_RAM_S - 1) is None
    assert lich.buoc(23.0, 0.0, 0, 100.0 + runner.CHO_RAM_S) == ("bo", clip)
    assert lich.xong


def test_clip_qua_ram_khong_bi_bo_khi_con_clip_khac_dang_chay():
    lich = _lich([_clip("sieu_dai", 28)])
    for giay in (0.0, 1000.0):
        assert lich.buoc(23.0, 0.0, 1, giay) is None, "còn clip chạy thì chờ nó xong đã"
    assert not lich.xong


def test_ram_tro_lai_trong_luc_cho_thi_van_chay_clip():
    clip = _clip("dai", 25)
    lich = _lich([clip])
    assert lich.buoc(23.0, 0.0, 0, 0.0) == ("cho", clip)
    assert lich.buoc(29.0, 0.0, 0, 10.0) == ("giao", clip)


def test_clip_ngan_cho_ram_lau_hon_clip_dai_roi_moi_bo():
    """RAM tụt giữa lượt: đã làm nửa kho thì chờ, không bỏ mấy trăm clip sau 60 giây."""
    clip = _clip("ngan", 1)
    lich = _lich([clip])
    assert lich.buoc(2.0, 0.0, 0, 0.0) == ("cho", clip)
    assert lich.buoc(2.0, 0.0, 0, runner.CHO_RAM_S) is None
    assert lich.buoc(2.0, 0.0, 0, runner.CHO_WORKER_S) == ("bo", clip)


def test_khong_con_clip_chay_ma_ram_van_thieu_thi_worker_ranh_nha_ram():
    lich = _lich([_clip("ngan", 1)])
    assert lich.buoc(2.0, 0.0, 0, 0.0)[0] == "cho"
    assert lich.thua_worker, "mỗi worker rảnh giữ ~0,5 GB, đó có thể chính là phần còn thiếu"


def test_clip_nho_nhat_khong_bi_coi_la_clip_dai_khi_may_it_ram():
    """Bắt đầu với 8 GB trống: phần mỗi worker 0,6 GB, clip 0,7 GB không được thành «clip dài»."""
    lich = runner.LichTheoRam([_clip("a", 0.7)], 8.0, 3.2, 8)
    assert lich.buoc(3.0, 0.0, 1, 0.0) is None
    assert not lich.thua_worker, "RAM trống lại là chạy tiếp được, worker không nên nghỉ vĩnh viễn"


def test_het_han_cho_thi_bo_lien_cac_clip_khong_vua_nhung_clip_vua_lai_duoc_chay():
    """Không chờ 60 giây CHO TỪNG clip: 300 clip mà máy hết RAM thì đợi 5 tiếng vô ích."""
    a, b, c = _clip("a", 25), _clip("b", 26), _clip("c", 27)
    lich = _lich([a, b, c])
    t = 0.0
    assert lich.buoc(23.0, 0.0, 0, t) == ("cho", a)
    t += runner.CHO_RAM_S
    assert lich.buoc(23.0, 0.0, 0, t) == ("bo", a)
    assert lich.buoc(23.0, 0.0, 0, t) == ("bo", b)
    assert lich.buoc(40.0, 0.0, 0, t) == ("giao", c)


# ---------------------------------------------------------------------------
#  4) Thử lại cuối lượt
# ---------------------------------------------------------------------------

def test_clip_loi_thu_lai_sau_cung_tung_clip_mot():
    a, b, c = _clip("a", 1), _clip("b", 1), _clip("c", 1)
    lich = _lich([a, b, c])
    assert lich.buoc(23.0, 0.0, 0, 0.0) == ("giao", a)
    assert lich.ghi_loi(a) is True, "lần đầu: chờ thử lại"
    assert lich.buoc(23.0, 0.0, 0, 0.0) == ("giao", b)
    assert lich.ghi_loi(b) is True
    assert lich.buoc(23.0, 0.0, 1, 0.0) == ("giao", c), "clip thường chạy trước"
    assert lich.buoc(23.0, 0.0, 1, 0.0) is None, "c chưa xong thì chưa thử lại"
    assert lich.buoc(23.0, 0.0, 0, 0.0) == ("giao", a)
    assert lich.buoc(23.0, 0.0, 1, 0.0) is None, "thử lại MỘT clip mỗi lúc"
    assert lich.ghi_loi(a) is False, "lần hai: kết luận hỏng, không vòng lại"
    assert lich.buoc(23.0, 0.0, 0, 0.0) == ("giao", b)
    assert lich.ghi_loi(b) is False
    assert lich.buoc(23.0, 0.0, 0, 0.0) is None
    assert lich.xong


# ---------------------------------------------------------------------------
#  5) Trả RAM: worker rảnh không giữ RAM khi hàng chỉ còn clip dài
# ---------------------------------------------------------------------------

def test_worker_ranh_duoc_cho_nghi_khi_clip_dai_chua_vua():
    lich = _lich([_clip("ngan", 1), _clip("dai", 15)])
    assert lich.buoc(23.0, 0.0, 0, 0.0)[0] == "giao"
    assert not lich.thua_worker
    assert lich.buoc(23.0, 8.0, 1, 0.0) is None
    assert lich.thua_worker, "clip dài chưa vừa: worker rảnh nên nhả RAM"


def test_worker_ranh_khong_bi_cho_nghi_chi_vi_ram_tam_thieu_o_clip_ngan():
    lich = _lich([_clip("ngan", 2)])
    assert lich.buoc(5.0, 3.0, 1, 0.0) is None
    assert not lich.thua_worker, "worker nghỉ là mất luôn; clip ngắn chỉ cần chờ"


def test_may_it_ram_van_chay_tung_clip_chu_khong_bo_ca_kho():
    """Chrome chiếm RAM, máy còn 3,5 GB: clip 5 phút chạy một mình vẫn an toàn, không được bỏ qua."""
    lich = runner.LichTheoRam([_clip("a", 0.7), _clip("b", 0.7)], 3.5, 3.2, 8)
    assert lich.buoc(3.5, 0.0, 0, 0.0)[0] == "giao"
    assert lich.buoc(3.5, 0.7, 1, 0.0) is None, "chạy song song thì vẫn giữ đủ dự phòng"
    assert lich.buoc(3.5, 0.0, 0, 1.0)[0] == "giao"


# ---------------------------------------------------------------------------
#  6) Mô phỏng: bất biến trên 2.000 thế giới ngẫu nhiên
# ---------------------------------------------------------------------------

def test_mo_phong_2000_the_gioi_khong_vuot_ram_va_moi_clip_ket_thuc_dung_mot_lan():
    for seed in range(2000):
        rng = random.Random(seed)
        tong_ram = rng.uniform(4, 40)
        du_phong = rng.uniform(1, 4)
        ncores = rng.randint(1, 8)
        clips = [_clip(f"c{i}", round(rng.choice([0.7, 1, 2, 4, 9, 20, 30]) * rng.uniform(0.8, 1.2), 2))
                 for i in range(rng.randint(1, 25))]
        lich = runner.LichTheoRam(clips, tong_ram, du_phong, ncores)
        dang_chay: dict = {}
        ket_thuc: dict = {}
        gio, buoc = 0.0, 0
        while not (lich.xong and not dang_chay):
            buoc += 1
            assert buoc < 20_000, f"seed {seed}: không kết thúc"
            # RAM trống = tổng - phần đã chiếm thật; clip chiếm dần theo thời gian.
            da_chiem = {c: c.can_gb * min(1.0, (gio - t0) / 5) for c, t0 in dang_chay.items()}
            trong = tong_ram - sum(da_chiem.values())
            con_phai_chua = sum(c.can_gb - da_chiem[c] for c in dang_chay)
            hanh_dong = None
            if len(dang_chay) < ncores:
                hanh_dong = lich.buoc(trong, con_phai_chua, len(dang_chay), gio)
            if hanh_dong and hanh_dong[0] == "giao":
                clip = hanh_dong[1]
                dang_chay[clip] = gio
                tong_dinh = sum(c.can_gb for c in dang_chay)
                giu_lai = du_phong if len(dang_chay) > 1 else du_phong / 2
                assert tong_dinh <= tong_ram - giu_lai + 1e-9, (
                    f"seed {seed}: {len(dang_chay)} clip cùng chạy cần {tong_dinh:.1f} GB, "
                    f"ngân sách {tong_ram - giu_lai:.1f} GB")
                continue
            if hanh_dong and hanh_dong[0] == "bo":
                assert hanh_dong[1] not in ket_thuc
                ket_thuc[hanh_dong[1]] = "bo"
                continue
            if hanh_dong:
                continue
            gio += 1.0
            xong = [c for c, t0 in dang_chay.items() if gio - t0 >= rng.randint(1, 8)]
            for c in xong:
                del dang_chay[c]
                if rng.random() < 0.1 and lich.ghi_loi(c):
                    continue            # lỗi lần đầu: sẽ được phát lại
                assert c not in ket_thuc
                ket_thuc[c] = "xong"
        assert set(ket_thuc) == set(clips), f"seed {seed}: thiếu {set(clips) - set(ket_thuc)}"


# ---------------------------------------------------------------------------
#  7) Ước lượng RAM
# ---------------------------------------------------------------------------

def _file_gia(path: Path, byte: int) -> str:
    with open(path, "wb") as f:
        f.truncate(byte)                 # file thưa: không tốn đĩa thật
    return str(path)


def test_uoc_luong_clip_nho_theo_dung_luong_khong_goi_ffprobe(tmp_path, monkeypatch):
    def khong_duoc_goi(path):
        raise AssertionError("clip nhỏ không cần ffprobe")

    monkeypatch.setattr(runner, "_do_dai_giay", khong_duoc_goi)
    assert runner.uoc_luong_ram_gb(_file_gia(tmp_path / "n.opus", 1000)) == runner.CAN_RAM_TOI_THIEU_GB


def test_uoc_luong_clip_lon_dung_thoi_luong_that(tmp_path, monkeypatch):
    """File mp4 2 GB dài 1 giờ không được tính theo dung lượng như opus (sẽ thành 70 giờ)."""
    monkeypatch.setattr(runner, "_do_dai_giay", lambda path: 3600.0)
    can = runner.uoc_luong_ram_gb(_file_gia(tmp_path / "video.mp4", 2 * 10**9))
    assert can == pytest.approx(runner.CAN_RAM_GB_MOI_GIO)


def test_uoc_luong_ffprobe_hong_thi_lui_ve_dung_luong(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_do_dai_giay", lambda path: None)
    byte_1_gio = runner.BYTE_MOI_GIAY_OPUS * 3600
    can = runner.uoc_luong_ram_gb(_file_gia(tmp_path / "a.opus", byte_1_gio))
    assert can == pytest.approx(runner.CAN_RAM_GB_MOI_GIO)


def test_uoc_luong_file_vang_khong_lam_hong_luot(tmp_path):
    assert runner.uoc_luong_ram_gb(str(tmp_path / "khong_co.opus")) == runner.CAN_RAM_TOI_THIEU_GB


# ---------------------------------------------------------------------------
#  8) Tiến trình con THẬT
# ---------------------------------------------------------------------------

KICH_BAN = textwrap.dedent(
    """
    import json, os, pathlib, sys
    sys.path[:0] = [{repo!r}, {vendor!r}]
    import audfprint_progress_runner as runner
    import hash_table

    THU_MUC = pathlib.Path({thu_muc!r})


    class Analyzer:
        \"\"\"Hành vi theo tên file; số lần chạy đếm bằng file dấu vì worker là tiến trình khác.\"\"\"

        def wavfile2hashes(self, filename):
            ten = os.path.basename(filename)
            dau = THU_MUC / (ten + ".lan")
            lan = int(dau.read_text()) + 1 if dau.exists() else 1
            dau.write_text(str(lan))
            if ten.startswith("het_ram_mai") or (ten.startswith("het_ram_1lan") and lan == 1):
                raise MemoryError("Unable to allocate 12.3 GiB")
            if ten.startswith("loi_doc_mai"):
                runner._LOI_GIAI_MA[filename] = "ValueError: ffmpeg output: treo"
                return []
            if ten.startswith("im_lang"):
                return []
            return [(t % 16, t % 16) for t in range(5)]


    if __name__ == "__main__":
        {thiet_lap}
        ht = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
        runner.instrumented_multiproc_add(Analyzer(), ht, sys.argv[1:], lambda m: None, {ncores})
        print("KET_QUA " + json.dumps({{"names": ht.names, "dirty": ht.dirty}}), flush=True)
    """
)


def _chay(tmp_path, files, *, ncores=2, thiet_lap="pass"):
    script = tmp_path / "kich_ban.py"
    script.write_text(KICH_BAN.format(repo=str(REPO), vendor=str(VENDOR), thu_muc=str(tmp_path),
                                      thiet_lap=thiet_lap, ncores=ncores), encoding="utf-8")
    kq = subprocess.run([sys.executable, "-u", str(script), *files], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=120,
                        env={**os.environ, "PYTHONUTF8": "1"})
    assert kq.returncode == 0, kq.stdout[-800:] + kq.stderr[-800:]
    su_kien = [json.loads(d[len(runner.PREFIX):]) for d in kq.stdout.splitlines()
               if d.startswith(runner.PREFIX)]
    ket_qua = next(json.loads(d[8:]) for d in kq.stdout.splitlines() if d.startswith("KET_QUA "))
    return su_kien, ket_qua


def _ket(su_kien, ten):
    return [e for e in su_kien if e["event"] == "clip_finished" and e["file"].endswith(ten)]


def test_clip_het_ram_ca_hai_lan_khong_lam_sap_luot_va_bao_ro_ly_do(tmp_path):
    """Trước đây MemoryError trong ``find_peaks`` giết worker và mất cả lượt."""
    files = [str(tmp_path / t) for t in ("a.opus", "het_ram_mai.opus", "b.opus", "c.opus")]
    su_kien, kq = _chay(tmp_path, files)

    loi = _ket(su_kien, "het_ram_mai.opus")
    assert [e["status"] for e in loi] == ["failed"], "kết luận hỏng đúng MỘT lần"
    assert loi[0]["category"] == "MemoryError"
    assert "het_ram_mai.opus" in loi[0]["message"] and "12.3 GiB" in loi[0]["message"]
    assert (tmp_path / "het_ram_mai.opus.lan").read_text() == "2", "phải thử lại một lần"
    assert sorted(os.path.basename(n) for n in kq["names"]) == ["a.opus", "b.opus", "c.opus"]


def test_clip_loi_lan_dau_thu_lai_cuoi_luot_thanh_cong_chi_tinh_mot_lan(tmp_path):
    files = [str(tmp_path / t) for t in ("het_ram_1lan.opus", "a.opus", "b.opus")]
    su_kien, kq = _chay(tmp_path, files)

    thu_lai = [e for e in su_kien if e["event"] == "clip_cho_thu_lai"]
    assert [os.path.basename(e["file"]) for e in thu_lai] == ["het_ram_1lan.opus"]
    assert "MemoryError" in thu_lai[0]["message"]
    assert [e["status"] for e in _ket(su_kien, "het_ram_1lan.opus")] == ["success"]
    ten_kho = [os.path.basename(n) for n in kq["names"]]
    assert sorted(ten_kho) == ["a.opus", "b.opus", "het_ram_1lan.opus"], "không được có bản ghi trùng"
    thu_tu = [os.path.basename(e["file"]) for e in su_kien if e["event"] == "clip_finished"]
    assert thu_tu[-1] == "het_ram_1lan.opus", "thử lại phải sau mọi clip khác"


def test_loi_doc_bi_thu_vien_nuot_van_duoc_thu_lai_va_giu_ly_do(tmp_path):
    su_kien, kq = _chay(tmp_path, [str(tmp_path / "loi_doc_mai.opus"), str(tmp_path / "a.opus")])
    loi = _ket(su_kien, "loi_doc_mai.opus")
    assert [e["category"] for e in loi] == ["ValueError"]
    assert "ffmpeg output: treo" in loi[0]["message"]
    assert (tmp_path / "loi_doc_mai.opus.lan").read_text() == "2"
    assert [os.path.basename(n) for n in kq["names"]] == ["a.opus"]


def test_clip_im_lang_khong_co_loi_thi_khong_thu_lai(tmp_path):
    su_kien, kq = _chay(tmp_path, [str(tmp_path / "im_lang.opus")], ncores=1)
    assert [e["category"] for e in _ket(su_kien, "im_lang.opus")] == ["zero_hashes"]
    assert (tmp_path / "im_lang.opus.lan").read_text() == "1"
    assert [os.path.basename(n) for n in kq["names"]] == ["im_lang.opus"], "vẫn ghi tên như cũ"


THIEU_RAM = ("runner._ram_trong_gb = lambda: 9.0; runner._du_phong_ram_gb = lambda: 2.0; "
             "runner.CHO_RAM_S = 0.3; runner._do_dai_giay = lambda p: 30 * 3600.0")


def test_clip_qua_ram_bi_bo_qua_bao_ro_va_clip_khac_van_xong(tmp_path):
    lon = _file_gia(tmp_path / "sieu_dai.opus", 200 * 10**6)
    su_kien, kq = _chay(tmp_path, [lon, str(tmp_path / "a.opus"), str(tmp_path / "b.opus")],
                        thiet_lap=THIEU_RAM)

    bo = _ket(su_kien, "sieu_dai.opus")
    assert [e["category"] for e in bo] == ["thieu_ram"]
    assert "sieu_dai.opus" in bo[0]["message"] and "Bổ sung" in bo[0]["message"]
    assert "45 GB" in bo[0]["message"], bo[0]["message"]
    assert not (tmp_path / "sieu_dai.opus.lan").exists(), "clip bị bỏ không được chạm vào worker"
    assert sorted(os.path.basename(n) for n in kq["names"]) == ["a.opus", "b.opus"]


def test_ca_luot_bi_bo_qua_van_ghi_bang_de_engine_ket_luan_ro_rang(tmp_path):
    """Không có file bảng thì engine chỉ báo «không tạo database tạm», mất lý do thật."""
    lon = _file_gia(tmp_path / "sieu_dai.opus", 200 * 10**6)
    su_kien, kq = _chay(tmp_path, [lon], ncores=1, thiet_lap=THIEU_RAM)
    assert [e["category"] for e in _ket(su_kien, "sieu_dai.opus")] == ["thieu_ram"]
    assert kq["names"] == [] and kq["dirty"] is True


def test_worker_nghi_som_van_du_bang_va_clip_loi_o_doan_dai_van_duoc_thu_lai(tmp_path):
    """Clip dài chỉ chạy được từng cái nên worker thừa nghỉ sớm; lượt thử lại vẫn phải còn worker."""
    lon = [_file_gia(tmp_path / t, 20 * 10**6) for t in ("dai_a.opus", "het_ram_1lan_dai.opus")]
    nho = [str(tmp_path / f"c{i}.opus") for i in range(4)]
    thiet_lap = ("runner._ram_trong_gb = lambda: 9.0; runner._du_phong_ram_gb = lambda: 2.0; "
                 "runner._do_dai_giay = lambda p: 3 * 3600.0")
    su_kien, kq = _chay(tmp_path, [*lon, *nho], ncores=4, thiet_lap=thiet_lap)

    assert (tmp_path / "het_ram_1lan_dai.opus.lan").read_text() == "2"
    assert [e["status"] for e in su_kien if e["event"] == "clip_finished"] == ["success"] * 6
    assert sorted(os.path.basename(n) for n in kq["names"]) == sorted(os.path.basename(f) for f in [*lon, *nho])


def test_phan_con_phai_chua_chi_tinh_phan_clip_chua_chiem(monkeypatch):
    class P:
        pid = 1

    da_chiem_mot_phan = runner._Worker(0, P, None, "", viec=_clip("a", 5), rss_luc_giao=1 << 30)
    vuot_uoc_luong = runner._Worker(1, P, None, "", viec=_clip("b", 2), rss_luc_giao=0)
    monkeypatch.setattr(runner, "_rss", lambda w: 3 << 30)
    assert runner._con_phai_chua_gb([da_chiem_mot_phan, vuot_uoc_luong]) == pytest.approx(3.0)


def test_phan_cong_dong_viec_du_clip_lech_nang_nhe(tmp_path):
    """Worker rảnh tự nhận clip tiếp theo: cả ``ncores`` lớn hơn số file cũng về đích."""
    files = [str(tmp_path / f"c{i}.opus") for i in range(6)]
    _, kq = _chay(tmp_path, files, ncores=8)
    assert sorted(os.path.basename(n) for n in kq["names"]) == sorted(os.path.basename(f) for f in files)


# ---------------------------------------------------------------------------
#  9) Nhánh một nhân cũng đi qua lịch RAM
# ---------------------------------------------------------------------------

def test_mot_nhan_new_add_di_qua_lich_ram_lenh_khac_giu_nguyen(monkeypatch):
    goi = []

    class Audfprint:
        multiproc_add = "goc"

        @staticmethod
        def do_cmd(cmd, analyzer, hash_tab, filename_iter, matcher, outdir, type_, report,
                   skip_existing=False, strip_prefix=None):
            goi.append(("goc", cmd))

    monkeypatch.setattr(runner, "cai_dat_theo_doi_giai_ma", lambda: None)
    monkeypatch.setattr(runner, "instrumented_multiproc_add",
                        lambda a, h, f, r, n: goi.append(("ram", list(f), n)))
    runner.cai_dat_instrumentation(Audfprint)
    for cmd in ("new", "add", "match"):
        Audfprint.do_cmd(cmd, None, None, ["a"], None, None, None, None)
    assert goi == [("ram", ["a"], 1), ("ram", ["a"], 1), ("goc", "match")]


# ---------------------------------------------------------------------------
#  10) Ưu tiên thấp
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.name != "nt", reason="lớp ưu tiên của Windows")
def test_runner_va_moi_tien_trinh_con_chay_uu_tien_thap(tmp_path):
    script = tmp_path / "uu_tien.py"
    script.write_text(textwrap.dedent(
        f"""
        import multiprocessing, subprocess, sys
        sys.path.insert(0, {str(REPO)!r})
        import psutil
        import audfprint_progress_runner as runner


        def bao(q):
            q.put(psutil.Process().nice())


        if __name__ == "__main__":
            runner._ha_uu_tien_tien_trinh()
            q = multiprocessing.Queue()
            p = multiprocessing.Process(target=bao, args=(q,))
            p.start()
            con = subprocess.run([sys.executable, "-c",
                                  "import psutil; print(psutil.Process().nice())"],
                                 capture_output=True, text=True)
            print(psutil.Process().nice(), q.get(timeout=60), con.stdout.strip())
            p.join()
        """), encoding="utf-8")
    kq = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=120)
    assert kq.returncode == 0, kq.stderr[-500:]
    import psutil

    assert kq.stdout.split() == [str(int(psutil.BELOW_NORMAL_PRIORITY_CLASS))] * 3


def test_khong_ha_duoc_uu_tien_cung_khong_lam_hong_build(monkeypatch):
    import psutil

    def hong(self, *a):
        raise psutil.AccessDenied()

    monkeypatch.setattr(psutil.Process, "nice", hong)
    runner._ha_uu_tien_tien_trinh()


# ---------------------------------------------------------------------------
#  11) Lý do thật của lỗi đọc
# ---------------------------------------------------------------------------

def test_loi_giai_ma_duoc_giu_lai_truoc_khi_thu_vien_nuot(monkeypatch):
    import audio_read

    def hong(*a, **k):
        raise MemoryError("Unable to allocate 3.1 GiB")

    monkeypatch.setattr(audio_read, "audio_read", hong)
    monkeypatch.setattr(runner, "_DA_CAI_THEO_DOI_GIAI_MA", False)
    monkeypatch.setattr(runner, "_LOI_GIAI_MA", {})
    runner.cai_dat_theo_doi_giai_ma()
    with pytest.raises(MemoryError):
        audio_read.audio_read("x.opus", sr=11025, channels=1)
    assert runner._LOI_GIAI_MA["x.opus"] == "MemoryError: Unable to allocate 3.1 GiB"


def test_ffmpeg_treo_khong_bi_ghi_thanh_typeerror():
    """``audio_read.read_data`` ghép stderr dạng bytes bằng ``''.join`` nên FFmpeg treo lộ ra thành
    TypeError — đúng trường hợp cần phân biệt với thiếu RAM (5 clip «Error reading» sáng 06/11)."""
    with pytest.raises(TypeError) as loi:
        "".join([b"ffmpeg stderr"])
    assert runner._mo_ta_loi(loi.value).startswith("FFmpegTreo: ")
    assert runner._mo_ta_loi(TypeError("khác")) == "TypeError: khác"


def test_ly_do_loi_khong_mang_duong_dan_day_du():
    class Analyzer:
        def wavfile2hashes(self, filename):
            raise ValueError("Error reading header info from " + filename)

    kq = runner._xu_ly_clip(Analyzer(), None, r"E:\Kho\thu_muc_rieng\a.opus")
    assert "thu_muc_rieng" not in kq["loi"] and "a.opus" in kq["loi"]


# ---------------------------------------------------------------------------
#  12) Engine + tiến độ
# ---------------------------------------------------------------------------

def _su_kien(**k) -> str:
    return runner.PREFIX + json.dumps(k, ensure_ascii=False)


def test_engine_clip_cho_thu_lai_khong_tinh_la_loi_va_dong_error_reading_khong_nam_lai(tmp_path):
    """Clip thử lại thành công: không còn dấu vết lỗi trong kết quả cho người dùng."""
    nguon = tmp_path / "nguon"
    nguon.mkdir()
    a, b = str(nguon / "a.opus"), str(nguon / "b.opus")
    for p in (a, b):
        Path(p).write_bytes(b"audio")
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *x, **k: None
    e._cap_nhat_snapshot_sau_build = lambda *x: []
    e.config.ncores = 2

    def chay(lenh, on_line=None, **kw):
        on_line(_su_kien(event="thong_bao_ram", message="RAM trống 20,0 GB"))
        on_line(_su_kien(event="clip_started", file=a))
        on_line(f"wavfile2peaks: Error reading {a} skipping")
        on_line(_su_kien(event="clip_cho_thu_lai", file=a, message="ValueError: ffmpeg treo"))
        on_line(_su_kien(event="clip_started", file=b))
        on_line(_su_kien(event="clip_finished", file=b, status="success", elapsed_seconds=1.0))
        on_line(_su_kien(event="clip_started", file=a))
        on_line(_su_kien(event="clip_finished", file=a, status="success", elapsed_seconds=1.0))
        ht = hash_table.HashTable(hashbits=4, depth=2, maxtime=16)
        for p in (a, b):
            ht.store(p, [(t % 16, t % 16) for t in range(5)])
        ht.save(lenh[lenh.index("--dbase") + 1])
        return 0, []

    e._run_stream = chay
    e._kiem_kho_tam = lambda *x, **k: (True, [])
    e._day_kho_tam_xuong_dia = lambda *x: None
    e._ghi_phien_ban_sau_cong_bo = lambda **k: []
    kq = e.build_database(str(nguon), "new")

    assert (kq["thanh_cong"], kq["that_bai"], kq["loi_file"]) == (2, 0, [])


def test_engine_ca_luot_loi_thi_thong_bao_neu_ly_do_that_cua_clip(tmp_path):
    """Kho một clip 18 giờ: «đều lỗi hoặc 0 hash» không cho người dùng biết phải đóng bớt ứng dụng."""
    nguon = tmp_path / "nguon"
    nguon.mkdir()
    a = str(nguon / "a.opus")
    Path(a).write_bytes(b"audio")
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e.require = lambda *x, **k: None
    e.config.ncores = 2

    def chay(lenh, on_line=None, **kw):
        on_line(_su_kien(event="clip_finished", file=a, status="failed", category="thieu_ram",
                         message="a.opus: cần khoảng 27 GB RAM", elapsed_seconds=0.0))
        hash_table.HashTable(hashbits=4, depth=2, maxtime=16).save(lenh[lenh.index("--dbase") + 1])
        return 0, []

    e._run_stream = chay
    with pytest.raises(RuntimeError, match="cần khoảng 27 GB RAM"):
        e.build_database(str(nguon), "new")


def test_tao_lai_kho_mat_clip_cu_thi_thong_bao_neu_ly_do_that(tmp_path):
    """Lời «kiểm tra file nguồn» sai hướng khi clip bị bỏ vì thiếu RAM."""
    e = Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"), out_dir=str(tmp_path / "out"))
    e._clip_huu_ich = lambda p: {"khac"}
    e._khoa_duong_dan = lambda p: p
    with pytest.raises(RuntimeError, match="cần khoảng 27 GB RAM"):
        e._kiem_kho_tam("db", "new", {"a"}, ["a"], loi_dau="a.opus: cần khoảng 27 GB RAM")


def _tracker(tmp_path) -> FingerprintProgressTracker:
    return FingerprintProgressTracker("job", logger=tao_fingerprint_logger(str(tmp_path)))


def test_heartbeat_khong_che_mat_loi_nhac_ram_cho_toi_clip_tiep_theo(tmp_path):
    t = _tracker(tmp_path)
    t.set_files(["a.opus"])
    t.thong_bao_ram("Đang chờ RAM")
    t.heartbeat(1, "Job vẫn hoạt động", phase="decoding")
    assert t.state.message == "Đang chờ RAM"
    t.clip_started("a.opus")
    t.heartbeat(1, "Job vẫn hoạt động", phase="decoding")  # khác phase hiện tại: không bị giới hạn 0,25 giây
    assert t.state.message == "Job vẫn hoạt động"
    dong_fingerprint_logger(t.logger)


def test_tracker_clip_cho_thu_lai_khong_con_la_clip_dang_chay_va_nhat_ky_co_ly_do(tmp_path):
    t = _tracker(tmp_path)
    t.set_files(["a.opus"])
    t.clip_started("a.opus")
    t.clip_cho_thu_lai("a.opus", "MemoryError: thiếu RAM")
    assert t.state.failed_count == 0 and t.state.processed_count == 0
    assert not t._active
    dong_fingerprint_logger(t.logger)
    nhat_ky = (tmp_path / "fingerprint.log").read_text(encoding="utf-8")
    assert "MemoryError: thiếu RAM" in nhat_ky


def test_tracker_ghi_ly_do_clip_loi_vao_nhat_ky(tmp_path):
    """Sáng 06/11 năm clip lỗi không để lại lý do trong nhật ký: chỉ có «Error reading»."""
    t = _tracker(tmp_path)
    t.set_files(["a.opus"])
    t.clip_finished("a.opus", success=False, elapsed=1.0, error_category="thieu_ram",
                    message="cần khoảng 28 GB RAM")
    dong_fingerprint_logger(t.logger)
    nhat_ky = (tmp_path / "fingerprint.log").read_text(encoding="utf-8")
    assert "thieu_ram" in nhat_ky and "cần khoảng 28 GB RAM" in nhat_ky


def test_tracker_thong_bao_ram_hien_len_giao_dien_va_vao_nhat_ky(tmp_path):
    t = _tracker(tmp_path)
    t.thong_bao_ram("Đang chờ RAM trống")
    assert t.state.message == "Đang chờ RAM trống"
    dong_fingerprint_logger(t.logger)
    assert "Đang chờ RAM trống" in (tmp_path / "fingerprint.log").read_text(encoding="utf-8")
