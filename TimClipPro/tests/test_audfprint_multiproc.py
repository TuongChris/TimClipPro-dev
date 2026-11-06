# -*- coding: utf-8 -*-
"""Regression cho bản vá nhánh đa nhân của audfprint.

Ba tính chất phải giữ:

1. Mọi điểm vá đều được gắn — quên một cái là mất event hoặc quay lại nguy cơ treo.
2. Tiến trình cha KHÔNG giữ đầu ghi pipe: worker chết phải thành lỗi rõ ràng,
   không phải treo vĩnh viễn (bản vendored treo mãi mãi trong tình huống này).
3. Nhiều tiến trình con cùng ghi stdout không được làm mất/ghép dòng event.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

import audfprint_progress_runner as runner

REPO = Path(__file__).resolve().parents[1]


def test_cai_dat_du_cac_diem_va():
    class AudfprintGia:
        multiproc_add = "goc"
        do_cmd = "goc"

    runner.cai_dat_instrumentation(AudfprintGia)

    assert AudfprintGia.multiproc_add is runner.instrumented_multiproc_add
    assert AudfprintGia.do_cmd != "goc", "nhánh một nhân cũng phải đi qua lịch RAM"


class _HashTabGia:
    """Đủ thuộc tính mà instrumented_multiproc_add cần, ghi lại các lần merge."""

    hashbits = 4
    depth = 2
    maxtimebits = 4

    def __init__(self):
        self.da_merge = []

    def merge(self, khac):
        self.da_merge.append(khac)


def worker_chet_ngay(*args, **kwargs):
    """Worker chết mà KHÔNG gửi gì qua pipe. Phải ở cấp module vì Windows dùng spawn."""
    raise SystemExit(3)


def test_worker_chet_khong_gui_gi_thi_bao_loi_chu_khong_treo(monkeypatch):
    """Bản vendored giữ tx[ix] mở nên recv() chờ mãi mãi. Bản này phải raise."""
    monkeypatch.setattr(runner, "_worker_ghi_hash_table", worker_chet_ngay)
    monkeypatch.setattr(runner, "CHO_WORKER_S", 20.0)

    bat_dau = time.monotonic()
    with pytest.raises(RuntimeError, match="không trả kết quả|không phản hồi"):
        runner.instrumented_multiproc_add(
            analyzer=None,
            hash_tab=_HashTabGia(),
            filename_iter=["a.wav", "b.wav"],
            report=lambda msgs: None,
            ncores=2,
        )
    assert time.monotonic() - bat_dau < 20.0, "Phải phát hiện worker chết ngay, không chờ hết timeout."


def _khong_nap_duoc():
    raise RuntimeError("không nạp được analyzer trong tiến trình con")


class _AnalyzerHong:
    """Chết NGAY khi tiến trình con mở gói tham số, trước khi worker kịp nhận đầu pipe."""

    def __reduce__(self):
        return (_khong_nap_duoc, ())


def test_worker_chet_luc_khoi_dong_thi_bao_ngay_khong_doi_het_han(monkeypatch):
    """Windows: con chết trước khi nhận handle thì cha KHÔNG thấy EOF, chỉ còn watchdog 30 phút."""
    monkeypatch.setattr(runner, "CHO_WORKER_S", 120.0)
    bat_dau = time.monotonic()
    with pytest.raises(RuntimeError, match="không trả kết quả"):
        runner.instrumented_multiproc_add(
            analyzer=_AnalyzerHong(),
            hash_tab=_HashTabGia(),
            filename_iter=["a.wav"],
            report=lambda msgs: None,
            ncores=1,
        )
    assert time.monotonic() - bat_dau < 60.0, "Phải thấy worker chết, không chờ hết hạn."


def test_khong_con_file_tam_sau_khi_that_bai(monkeypatch, tmp_path):
    truoc = set(Path(runner.tempfile.gettempdir()).glob("timclip_ht_*"))
    monkeypatch.setattr(runner, "_worker_ghi_hash_table", worker_chet_ngay)
    monkeypatch.setattr(runner, "CHO_WORKER_S", 20.0)
    with pytest.raises(RuntimeError):
        runner.instrumented_multiproc_add(
            analyzer=None,
            hash_tab=_HashTabGia(),
            filename_iter=["a.wav"],
            report=lambda msgs: None,
            ncores=1,
        )
    sau = set(Path(runner.tempfile.gettempdir()).glob("timclip_ht_*"))
    assert sau <= truoc, "Thư mục tạm của hash table phải được dọn kể cả khi lỗi."


class _HTGia:
    """HashTable giả đủ để cha đọc lại từ gzip: cần `names` và `counts`."""

    def __init__(self, so_file):
        self.names = [f"clip_{i}.opus" for i in range(so_file)]
        self.counts = [1] * so_file


def _phuc_vu(ket_noi, duong_dan, moi_clip=lambda: None):
    """Bắt chước ĐÚNG vòng worker thật: nhận clip, trả lời, được cho nghỉ thì gzip rồi mới báo."""
    import gzip
    import pickle

    so_file = 0
    while ket_noi.recv() is not None:
        moi_clip()
        so_file += 1
        ket_noi.send({})
    with gzip.open(duong_dan, "wb", compresslevel=1) as fh:
        pickle.dump(_HTGia(so_file), fh, protocol=pickle.HIGHEST_PROTOCOL)
    ket_noi.send({"ok": True})
    ket_noi.close()


def _ngu_mot_giay():
    time.sleep(1.0)


def worker_cham_ma_khoe(analyzer, ket_noi, hashbits, depth, maxtime, duong_dan):
    """Tổng thời gian LÂU HƠN HẲN hạn chót nhưng vẫn trả lời đều đặn từng clip.

    Phải ở cấp module vì Windows dùng spawn.
    """
    _phuc_vu(ket_noi, duong_dan, _ngu_mot_giay)


def worker_nhanh_va_khoe(analyzer, ket_noi, hashbits, depth, maxtime, duong_dan):
    _phuc_vu(ket_noi, duong_dan)


def worker_ket_cung(analyzer, ket_noi, hashbits, depth, maxtime, duong_dan):
    """Trả lời 3 clip rồi treo VĨNH VIỄN mà KHÔNG đóng pipe.

    Không có EOF, nên im lặng là tín hiệu duy nhất — đúng tình huống mà bản cũ
    không tài nào phân biệt được với "chậm mà khoẻ".
    """
    for _ in range(3):
        ket_noi.recv()
        ket_noi.send({})
    time.sleep(120)


# Hạn chót trong các test dưới đây phải LỚN HƠN HẲN chi phí spawn+import của tiến
# trình con, vì lời đáp ĐẦU TIÊN chỉ tới sau khi con đã nạp xong module. Đo được: ~0,4 s
# khi máy rảnh, nhưng đã thấy vượt 2 s khi chạy cả bộ test. Đừng "tối ưu" các con số
# này xuống nữa — bản đầu dùng 1,5–2,0 s và đã flaky đúng theo kiểu đó.
# Bản chạy thật đặt CHO_WORKER_S = 1800 s nên chuyện này không bao giờ là vấn đề.


def test_worker_cham_hon_han_chot_nhung_van_tien_thi_khong_bi_giet(monkeypatch):
    """Regression trực tiếp cho sự cố 2026-09-07.

    Bản đầu coi `poll(CHO_WORKER_S)` là watchdog, nhưng pipe chỉ có MỘT message phát ra
    lúc worker đã xong hết việc — nên hằng số thành hạn chót cho TỔNG phần việc và
    giết một job 94,8% hoàn thành trong lúc cả 8 worker đều khoẻ.
    """
    monkeypatch.setattr(runner, "_worker_ghi_hash_table", worker_cham_ma_khoe)
    monkeypatch.setattr(runner, "CHO_WORKER_S", 8.0)
    monkeypatch.setattr(runner, "NHIP_KIEM_S", 0.1)

    hash_tab = _HashTabGia()
    bat_dau = time.monotonic()
    runner.instrumented_multiproc_add(
        analyzer=None,
        hash_tab=hash_tab,
        filename_iter=[f"c{i}.wav" for i in range(20)],
        report=lambda msgs: None,
        ncores=2,
    )
    troi_qua = time.monotonic() - bat_dau

    # Bắt buộc: nếu worker giả chạy nhanh hơn hạn chót thì test xanh một cách vô nghĩa.
    assert troi_qua > 8.0, (
        f"Worker phải chạy LÂU HƠN hạn chót mới chứng minh được điều gì "
        f"(chạy {troi_qua:.1f}s, hạn chót 8.0s)."
    )
    assert len(hash_tab.da_merge) == 2, "Phải merge đủ hash table của mọi worker."


def test_worker_con_song_nhung_ngung_tien_thi_bi_phat_hien_va_bao_ro_so_file(monkeypatch):
    """Kẹt thật vẫn phải bị bắt trong thời gian có giới hạn, và báo rõ đã xong bao nhiêu."""
    monkeypatch.setattr(runner, "_worker_ghi_hash_table", worker_ket_cung)
    monkeypatch.setattr(runner, "CHO_WORKER_S", 8.0)
    monkeypatch.setattr(runner, "NHIP_KIEM_S", 0.1)

    truoc = set(Path(runner.tempfile.gettempdir()).glob("timclip_ht_*"))
    bat_dau = time.monotonic()
    with pytest.raises(RuntimeError, match="không trả kết quả|không phản hồi") as loi:
        runner.instrumented_multiproc_add(
            analyzer=None,
            hash_tab=_HashTabGia(),
            filename_iter=["a.wav", "b.wav", "c.wav", "d.wav"],
            report=lambda msgs: None,
            ncores=1,
        )
    troi_qua = time.monotonic() - bat_dau

    assert troi_qua < 30.0, "Không được chờ hết 120s ngủ của worker."
    van_ban = str(loi.value)
    assert "3 file" in van_ban, (
        f"Thông báo phải nói worker đã xong bao nhiêu file — đây là dữ kiện mà một "
        f"thiết kế chỉ có dấu thời gian không bao giờ nêu được. Nhận: {van_ban!r}"
    )
    assert "Worker vân tay 0" in van_ban, f"Phải nêu đúng chỉ số worker. Nhận: {van_ban!r}"

    sau = set(Path(runner.tempfile.gettempdir()).glob("timclip_ht_*"))
    assert sau <= truoc, "Thư mục tạm phải được dọn kể cả khi worker bị treo."


def test_ncores_lon_hon_so_file_khong_sinh_worker_thua(monkeypatch):
    """Worker thừa chỉ tốn RAM cho bảng hash; bố cục giống test tích hợp (ncores=8, 6 clip)."""
    monkeypatch.setattr(runner, "_worker_ghi_hash_table", worker_nhanh_va_khoe)
    monkeypatch.setattr(runner, "CHO_WORKER_S", 30.0)
    monkeypatch.setattr(runner, "NHIP_KIEM_S", 0.1)

    hash_tab = _HashTabGia()
    runner.instrumented_multiproc_add(
        analyzer=None,
        hash_tab=hash_tab,
        filename_iter=[f"c{i}.wav" for i in range(6)],
        report=lambda msgs: None,
        ncores=8,
    )
    assert len(hash_tab.da_merge) == 6


KICH_BAN_GHI_CHUNG = """
import multiprocessing, os, sys
sys.path.insert(0, r"{repo}")
import audfprint_progress_runner as runner

def phat(chi_so):
    for lan in range(40):
        runner._emit("clip_started", file="clip_%d_%d.opus" % (chi_so, lan),
                     phase="fingerprinting", process_pid=os.getpid())

if __name__ == "__main__":
    ps = [multiprocessing.Process(target=phat, args=(i,)) for i in range(8)]
    for p in ps:
        p.start()
    for p in ps:
        p.join()
"""


def test_tam_tien_trinh_con_ghi_chung_stdout_khong_mat_hay_ghep_dong(tmp_path):
    """8 worker × 40 event = 320 dòng; tất cả phải nguyên vẹn và parse được JSON."""
    script = tmp_path / "ghi_chung.py"
    script.write_text(KICH_BAN_GHI_CHUNG.format(repo=str(REPO)), encoding="utf-8")

    ket_qua = subprocess.run(
        [sys.executable, "-u", str(script)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180,
    )
    assert ket_qua.returncode == 0, ket_qua.stderr[-500:]

    dong = [d for d in ket_qua.stdout.splitlines() if d.strip()]
    assert len(dong) == 8 * 40, f"Mất hoặc ghép dòng: nhận {len(dong)}/320"
    for d in dong:
        assert d.startswith(runner.PREFIX), f"Dòng bị ghép: {d[:120]!r}"
        payload = json.loads(d[len(runner.PREFIX):])
        assert payload["event"] == "clip_started"
        assert payload["file"].startswith("clip_")
