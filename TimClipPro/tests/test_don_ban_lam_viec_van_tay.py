# -*- coding: utf-8 -*-
"""Audit C-7 (P2): bản làm việc vân tay ``data/fingerprint_jobs/<job>`` (BẢN SAO TOÀN BỘ kho)
và rác tạm của job dựng kho / tải bị bỏ lại, không có gì thu hồi.

Bất biến của chính dự án:
* ``test_fingerprint_engine_progress.py``: sau khi Dừng/lỗi, không còn
  ``fingerprint_jobs/*/database.pklz`` — kho tạm chỉ được sống trong một job đang chạy.
* ``cli.py dondep``: «còn sót nghĩa là có lượt bị kill/crash … không dọn thì đầy ổ lúc nào
  không hay» — lý do đó áp y hệt cho bản sao kho vân tay (bằng cỡ kho, hàng trăm MB).

Mọi dữ liệu ở đây là synthetic, trong ``tmp_path``. Không mạng.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
import uuid
from pathlib import Path

import pytest

from kho_gia import ghi_kho

REPO = Path(__file__).resolve().parents[1]
_BA_MUOI_NGAY = 30 * 24 * 3600


def _kho_cu_va_clip_moi(engine, tmp_path):
    """Kho hiện có (1 clip có vân tay) + thư mục nguồn có thêm 1 clip mới → «Bổ sung»."""
    folder = tmp_path / "clips"
    folder.mkdir()
    cu = folder / "cu.wav"
    moi = folder / "moi.wav"
    cu.write_bytes(b"fixture-cu")
    moi.write_bytes(b"fixture-moi")
    ghi_kho(engine.db_file, [(str(cu), 100)])
    return folder, cu


def _con_sot(engine) -> list:
    goc = Path(engine.data_dir) / "fingerprint_jobs"
    if not goc.is_dir():
        return []
    return sorted((p.name, sorted(x.name for x in p.iterdir())) for p in goc.iterdir())


def test_loi_khi_chep_ban_lam_viec_khong_de_lai_ban_sao_kho(engine, tmp_path, monkeypatch):
    """ENOSPC/quyền/diệt virus ở bước «tạo bản làm việc an toàn» (copystat sau vòng chép)."""
    folder, _ = _kho_cu_va_clip_moi(engine, tmp_path)
    kho_truoc = Path(engine.db_file).read_bytes()
    monkeypatch.setattr(engine, "require", lambda **kwargs: None)
    monkeypatch.setattr(engine, "_run_stream",
                        lambda *a, **k: pytest.fail("không được tới bước audfprint"))

    import shutil as _shutil

    def copystat_het_cho(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(_shutil, "copystat", copystat_het_cho)

    with pytest.raises(OSError):
        engine.build_database(str(folder), "add")

    assert Path(engine.db_file).read_bytes() == kho_truoc
    assert _con_sot(engine) == [], (
        "Lỗi ở bước tạo bản làm việc để lại bản sao kho trong fingerprint_jobs/: "
        f"{_con_sot(engine)}"
    )


def test_bam_dung_luc_tao_ban_lam_viec_an_toan_khong_de_lai_ban_sao_kho(
    engine, tmp_path, monkeypatch
):
    """Người dùng bấm Dừng đúng lúc thấy «Đang tạo bản làm việc an toàn…» (kho lớn: hàng chục giây)."""
    folder, _ = _kho_cu_va_clip_moi(engine, tmp_path)
    kho_truoc = Path(engine.db_file).read_bytes()
    monkeypatch.setattr(engine, "require", lambda **kwargs: None)
    monkeypatch.setattr(engine, "_run_stream",
                        lambda *a, **k: pytest.fail("không được tới bước audfprint"))

    def bam_dung(event):
        if "bản làm việc an toàn" in (event.message or ""):
            engine.cancel_event.set()

    ket_qua = engine.build_database(str(folder), "add", progress_event=bam_dung)

    assert ket_qua["da_huy"] is True
    assert Path(engine.db_file).read_bytes() == kho_truoc
    assert _con_sot(engine) == [], (
        "Dừng ở bước tạo bản làm việc để lại bản sao kho trong fingerprint_jobs/: "
        f"{_con_sot(engine)}"
    )


def test_go_van_tay_cu_loi_khong_de_lai_ban_sao_kho(engine, tmp_path, monkeypatch):
    """«Bổ sung» có clip đổi file → gỡ vân tay cũ trong kho tạm (``audfprint remove``) thất bại."""
    folder, cu = _kho_cu_va_clip_moi(engine, tmp_path)
    kho_truoc = Path(engine.db_file).read_bytes()
    monkeypatch.setattr(engine, "require", lambda **kwargs: None)
    monkeypatch.setattr(engine, "_run_stream",
                        lambda *a, **k: pytest.fail("không được tới bước audfprint add"))
    monkeypatch.setattr(engine, "_clip_doi_file_sau_cong_bo",
                        lambda files, da_co: {engine._khoa_duong_dan(str(cu))})

    def go_loi(*args, **kwargs):
        raise RuntimeError("audfprint remove kết thúc với mã lỗi 1")

    monkeypatch.setattr(engine, "_go_van_tay_cu", go_loi)

    with pytest.raises(RuntimeError, match="remove"):
        engine.build_database(str(folder), "add")

    assert Path(engine.db_file).read_bytes() == kho_truoc
    assert _con_sot(engine) == [], (
        "Gỡ vân tay cũ lỗi để lại bản sao kho trong fingerprint_jobs/: "
        f"{_con_sot(engine)}"
    )


def test_dondep_thu_hoi_ban_lam_viec_mo_coi_cua_lan_crash(engine, monkeypatch, capsys):
    """Crash/kill/mất điện giữa job dựng kho (đóng cửa sổ console Development là cách dừng
    được hướng dẫn) bỏ qua mọi ``finally``. Dọn dẹp định kỳ phải thu hồi phần mồ côi đã cũ."""
    import cli

    data = Path(engine.data_dir)
    job_cu = data / "fingerprint_jobs" / uuid.uuid4().hex
    job_cu.mkdir(parents=True)
    (job_cu / "database.pklz").write_bytes(b"\0" * 4096)   # bản sao kho (thật: hàng trăm MB)
    (job_cu / "clips.txt").write_text("a.wav\n", encoding="utf-8")
    td = data / "tien_do_tai"
    td.mkdir(parents=True, exist_ok=True)
    file_td = td / "abc123-deadbeef.txt"
    file_td.write_text("progress=continue\n", encoding="utf-8")
    cu = time.time() - _BA_MUOI_NGAY
    for p in (job_cu / "database.pklz", job_cu / "clips.txt", job_cu, file_td):
        os.utime(p, (cu, cu))

    monkeypatch.setattr("sys.argv", ["cli.py", "dondep"])
    monkeypatch.setattr(cli, "Engine", lambda *a, **k: engine)
    cli.main()
    capsys.readouterr()

    con_lai = [str(p.relative_to(data)) for p in (job_cu, file_td) if p.exists()]
    assert con_lai == [], (
        "«dondep» không thu hồi rác 30 ngày tuổi của job dựng kho / tải bị kill: "
        f"{con_lai}"
    )


_SCRIPT_RUNNER = textwrap.dedent(
    """
    import sys, time
    sys.path.insert(0, {repo!r})
    import audfprint_progress_runner as runner


    def worker_cham(*args, **kwargs):
        time.sleep(120)


    class HashTabGia:
        hashbits = 4
        depth = 2
        maxtimebits = 4

        def merge(self, khac):
            pass


    if __name__ == "__main__":
        runner._worker_ghi_hash_table = worker_cham
        print("bat_dau", flush=True)
        runner.instrumented_multiproc_add(None, HashTabGia(), ["a.wav", "b.wav"],
                                          lambda m: None, 2)
    """
)


def test_dung_job_da_nhan_khong_de_lai_bang_tam_trong_temp_he_thong(tmp_path):
    """Dừng = ``process_runner`` terminate gốc + hậu duệ (đúng như Engine khi bấm Dừng):
    ``finally`` của runner không chạy, nên thư mục ``timclip_ht_*`` (bảng gzip mỗi worker,
    hàng chục MB) nằm lại trong %TEMP% của người dùng — nơi không gì dọn. Đúng: bảng tạm
    nằm trong bản làm việc của job (được dọn cùng nó), không ở %TEMP% hệ thống.

    Runner thật nhận thư mục bản làm việc qua ``--dbase`` (``main()`` đặt biến môi trường
    ``TIMCLIP_THU_MUC_BANG_TAM``); script này gọi thẳng ``instrumented_multiproc_add`` nên
    đặt biến đó y như ``main()`` sẽ đặt."""
    import audfprint_progress_runner as runner
    import process_runner

    temp_he_thong = tmp_path / "temp_he_thong"
    temp_he_thong.mkdir()
    ban_lam_viec = tmp_path / "data" / "fingerprint_jobs" / uuid.uuid4().hex
    ban_lam_viec.mkdir(parents=True)
    script = tmp_path / "chay_runner.py"
    script.write_text(_SCRIPT_RUNNER.format(repo=str(REPO)), encoding="utf-8")
    env = dict(os.environ)
    env["TMP"] = env["TEMP"] = env["TMPDIR"] = str(temp_he_thong)
    env[runner.BIEN_THU_MUC_BANG_TAM] = str(ban_lam_viec)
    proc = subprocess.Popen([sys.executable, str(script)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        het = time.monotonic() + 30
        thay = []
        while time.monotonic() < het and not thay:
            thay = [*temp_he_thong.glob("timclip_ht_*"), *ban_lam_viec.glob("timclip_ht_*")]
            if proc.poll() is not None:
                break
            time.sleep(0.2)
        assert thay, ("runner không tạo thư mục tạm trong 30 s; đầu ra: "
                      + (proc.stdout.read().decode("utf-8", "replace") if proc.poll() is not None
                         else "(đang chạy)"))
        time.sleep(0.5)  # worker đã khởi động
        process_runner.terminate_process_tree(proc.pid, wait_seconds=10)
        proc.wait(timeout=15)
    finally:
        if proc.poll() is None:
            process_runner.terminate_process_tree(proc.pid, wait_seconds=5)
        if proc.stdout:
            proc.stdout.close()

    con_lai = sorted(p.name for p in temp_he_thong.glob("timclip_ht_*"))
    assert con_lai == [], (
        f"Dừng job dựng kho đa nhân để lại thư mục tạm trong %TEMP% hệ thống: {con_lai}"
    )
    # Bảng tạm ở trong bản làm việc — engine/dondep dọn cùng nó.
    assert list(ban_lam_viec.glob("timclip_ht_*"))


def test_runner_dat_bang_tam_canh_database_dang_dung(tmp_path, monkeypatch):
    """``main()`` lấy thư mục của ``--dbase`` (bản làm việc của job) làm chỗ đặt bảng tạm."""
    import audfprint_progress_runner as runner

    # setenv trước để monkeypatch hoàn nguyên cả biến mà main() tự đặt trong tiến trình này.
    monkeypatch.setenv(runner.BIEN_THU_MUC_BANG_TAM, "x")
    monkeypatch.delenv(runner.BIEN_THU_MUC_BANG_TAM)
    ban_lam_viec = tmp_path / "fingerprint_jobs" / "job1"
    ban_lam_viec.mkdir(parents=True)
    thay = {}

    class AudfprintGia:
        @staticmethod
        def main(argv):
            thay["dir"] = runner._thu_muc_bang_tam()

    monkeypatch.setitem(sys.modules, "audfprint", AudfprintGia)
    monkeypatch.setitem(sys.modules, "audfprint_analyze", object())
    monkeypatch.setattr(runner, "cai_dat_instrumentation", lambda *a: None)
    monkeypatch.setattr(runner, "_NHOM_CUA_RUNNER", None)
    import process_runner

    monkeypatch.setattr(process_runner, "NhomTienTrinh", None)  # không gắn Job Object trong test
    db = ban_lam_viec / "database.pklz"
    assert runner.main(["runner", str(tmp_path / "audfprint.py"), "add", "--dbase", str(db),
                        "--ncores", "2"]) == 0
    assert os.path.normcase(thay["dir"]) == os.path.normcase(str(ban_lam_viec))


def test_dondep_giu_ban_lam_viec_va_tien_do_con_moi(engine, tmp_path):
    """Job đang chạy (file mới) không bị thu hồi; ``max_ngay=0`` không xoá gì."""
    import don_dep

    data = Path(engine.data_dir)
    job = data / "fingerprint_jobs" / uuid.uuid4().hex
    job.mkdir(parents=True)
    ban_sao = job / "database.pklz"
    ban_sao.write_bytes(bytes(64))
    cu = time.time() - _BA_MUOI_NGAY
    os.utime(ban_sao, (cu, cu))              # copystat giữ mtime CŨ của kho thật
    (job / "clips.txt").write_text("a.wav", encoding="utf-8")   # nhịp sống: mới
    td = data / "tien_do_tai"
    td.mkdir(parents=True, exist_ok=True)
    (td / "dang-tai.txt").write_text("progress=continue", encoding="utf-8")

    kq = don_dep.don_rac_job_tam(str(data), max_ngay=7)
    assert kq["xoa_muc"] == 0 and kq["bo_qua_dang_chay"] == 2 and kq["loi"] == []
    assert job.is_dir() and (td / "dang-tai.txt").is_file()

    for p in (ban_sao, job / "clips.txt", job, td / "dang-tai.txt"):
        os.utime(p, (cu, cu))
    kq = don_dep.don_rac_job_tam(str(data), max_ngay=0)
    assert kq["xoa_muc"] == 0 and job.is_dir()
    kq = don_dep.don_rac_job_tam(str(data), max_ngay=7, thuc_hien=False)
    assert kq["xoa_muc"] == 2 and job.is_dir()
    kq = don_dep.don_rac_job_tam(str(data), max_ngay=7)
    assert kq["xoa_muc"] == 2 and not job.exists() and not (td / "dang-tai.txt").exists()
