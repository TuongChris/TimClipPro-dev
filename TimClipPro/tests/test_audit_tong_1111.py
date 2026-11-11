# -*- coding: utf-8 -*-
"""Audit tổng 11/11 (Codex GPT-6 Astra, chỉ nhận chữ; mỗi phát hiện kiểm lại bằng test đỏ trước khi sửa)."""

from __future__ import annotations

import argparse
import collections
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import cli
import danh_sach_video as dsv
import dong_goi
import engine
import giam_sat_tai
import outbox
import process_runner
import release_tool
import watch
from channel import ChannelSync
from luu_tru import ghi_json_an_toan
from process_runner import run_observed_process


def _chan_mot_thu_muc(monkeypatch, bi_chan: Path) -> None:
    """``os.walk`` mở thư mục bằng ``os.scandir``: giả lập MỘT thư mục con không có quyền đọc."""
    scandir_that = os.scandir
    dich = os.path.normcase(os.path.abspath(bi_chan))

    def scandir(path="."):
        if os.path.normcase(os.path.abspath(os.fspath(path))) == dich:
            raise PermissionError(13, "Access is denied", os.fspath(path))
        return scandir_that(path)

    monkeypatch.setattr(os, "scandir", scandir)


# ---------------------------------------------------------------- tạo vân tay / bảng kho: thư mục con không đọc được


def test_tao_van_tay_thu_muc_con_khong_doc_duoc_thi_dung_khong_lam_hep_kho(
    tmp_path, monkeypatch
):
    """«Tạo lại kho»: ``os.walk`` lặng lẽ bỏ thư mục con không đọc được → clip trong đó bị coi là đã rời nguồn, kho
    mới thay kho cũ chỉ kèm một cảnh báo — vân tay của chúng mất tới lần tạo lại sau."""
    nguon = tmp_path / "nguon"
    (nguon / "doc_duoc").mkdir(parents=True)
    (nguon / "bi_chan").mkdir()
    (nguon / "doc_duoc" / "a.opus").write_bytes(b"a")
    (nguon / "bi_chan" / "b.opus").write_bytes(b"b")
    _chan_mot_thu_muc(monkeypatch, nguon / "bi_chan")
    # Quét thư mục video của người dùng: giữ nguyên hành vi cũ.
    assert engine.liet_ke_media(str(nguon)) == [str(nguon / "doc_duoc" / "a.opus")]
    with pytest.raises(RuntimeError, match="bi_chan"):
        engine.liet_ke_media(str(nguon), bo_thu_muc_lam_viec=True)


def test_bang_kho_thu_muc_con_khong_doc_duoc_bao_loi_khong_ra_bang_thieu(
    tmp_path, monkeypatch
):
    """Bảng danh sách video của kho (đẩy lên Sheet THAY bảng cũ): thiếu cả một thư mục con mà vẫn «thành công»."""
    kho = tmp_path / "kho"
    (kho / "nam_2025").mkdir(parents=True)
    (kho / "a [abcdefghijk].opus").write_bytes(b"a")
    (kho / "nam_2025" / "b [bbcdefghijk].opus").write_bytes(b"b")
    _chan_mot_thu_muc(monkeypatch, kho / "nam_2025")
    with pytest.raises(dsv.LoiKho):
        dsv._duyet_file(str(kho), "Kho thử")


# ---------------------------------------------------------------- đọc output tiến trình con không mất dòng


def _in_dong(n: int) -> list:
    return [
        sys.executable,
        "-c",
        f"import sys\nfor i in range({n}):\n    print(i)\nsys.stdout.flush()",
    ]


def test_rut_du_lo_512_dong_khong_mat_dong_ke_tiep(monkeypatch):
    """Lần rút thứ 512 lấy luôn dòng kế rồi hết lượt — vòng sau ghi đè biến đó, dòng mất hẳn (sự kiện vân tay, lỗi)."""
    du = threading.Event()

    class HangDoiDem(queue.Queue):
        def put(self, item, block=True, timeout=None):
            super().put(item, block, timeout)
            if self.qsize() >= 1200:  # 1199 dòng còn lại + dấu hết
                du.set()

    monkeypatch.setattr(process_runner, "queue", SimpleNamespace(Queue=HangDoiDem, Empty=queue.Empty, Full=queue.Full))
    monkeypatch.setattr(process_runner, "HANG_DOI_DONG", 0)  # không giới hạn
    nhan = []

    def on_line(dong):
        if not nhan:
            assert du.wait(60), "bên đọc chưa dồn đủ output vào hàng đợi"
        nhan.append(dong)

    kq = run_observed_process(_in_dong(1200), on_line=on_line, tail_lines=2000)
    assert kq.returncode == 0
    assert nhan == [str(i) for i in range(1200)]
    assert list(kq.tail) == nhan


def test_tien_trinh_con_thoat_luc_hang_doi_day_khong_bo_cac_dong_cuoi(monkeypatch, tmp_path):
    """Con in xong + thoát trong lúc bên rút chậm một nhịp (hàng đợi đầy quá 0,2 giây): bên đọc từng bỏ phần còn
    lại của ống — mất các dòng cuối, đúng chỗ thường là thông báo lỗi (CLAUDE.md quy tắc 2)."""
    monkeypatch.setattr(process_runner, "HANG_DOI_DONG", 8)
    xong = tmp_path / "con_da_in_xong"
    lenh = [sys.executable, "-c", "import pathlib, sys\nfor i in range(100):\n    print(i)\nsys.stdout.flush()\n"
            f"pathlib.Path(r'{xong}').write_text('x')\n"]
    nhan = []

    def on_line(dong):
        if not nhan:
            han = time.monotonic() + 60
            while not xong.exists() and time.monotonic() < han:
                time.sleep(0.02)
            time.sleep(0.7)  # con đã thoát; bên đọc chờ chỗ trống quá 0,2 giây vài lần
        nhan.append(dong)

    kq = run_observed_process(lenh, on_line=on_line, tail_lines=200)
    assert xong.exists()
    assert nhan == [str(i) for i in range(100)]
    assert kq.tail[-1] == "99"


# ---------------------------------------------------------------- Watch


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ?si=abc",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://m.youtube.com/shorts/dQw4w9WgXcQ",
    ],
)
def test_watch_nhan_link_live_va_m_youtube(url):
    """Link VOD của livestream (``/live/<mã>``) và link từ trình duyệt điện thoại bị coi là «không nhận dạng được»
    và bị loại khỏi MỌI lượt Watch."""
    assert watch.lay_id_youtube(url) == "dQw4w9WgXcQ"


def test_watch_dung_giua_luc_liet_ke_kenh_khong_hoi_tiep_kenh_con_lai():
    goi = []
    dung = threading.Event()

    def lister(url, limit):
        goi.append(url)
        dung.set()  # người dùng bấm Dừng trong lúc đang liệt kê kênh đầu
        return [
            SimpleNamespace(
                id="abcdefghijk", url="https://youtu.be/abcdefghijk", title="V"
            )
        ]

    wl = watch.WatchList(
        muc=[
            watch.MucTheoDoi("kenh", f"https://www.youtube.com/@k{i}") for i in range(3)
        ]
    )
    ung_vien, loi = watch.lay_ung_vien(wl, lister=lister, dung=dung.is_set)
    assert goi == ["https://www.youtube.com/@k0"]
    assert [u.video_id for u in ung_vien] == ["abcdefghijk"]
    assert any("Đã dừng theo yêu cầu" in x and "2 kênh" in x for x in loi)


# ---------------------------------------------------------------- dòng lệnh


def test_cli_gui_con_bao_cao_loi_bi_chan_thi_thoat_ma_1(tmp_path, monkeypatch, capsys):
    """``cli.py gui``: việc BLOCKED_REPORT (báo cáo V2 lỗi) không gửi được mà mã thoát 0 — ``_in_tong_ket_gui`` cùng
    file coi đúng trạng thái đó là lỗi."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("TIMCLIP_STATE_ROOT", raising=False)
    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(data))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(outbox, "tom_tat", lambda *a, **k: collections.defaultdict(int))
    monkeypatch.setattr(
        outbox,
        "cho_gui_xong",
        lambda *a, **k: collections.defaultdict(int, {outbox.BLOCKED_REPORT: 1}),
    )
    with pytest.raises(SystemExit) as e:
        cli._lenh_dich_va_gui(argparse.Namespace(lenh="gui", cho=0))
    assert e.value.code == 1
    assert "báo cáo lỗi" in capsys.readouterr().out


# ---------------------------------------------------------------- bí mật trong gói phát hành / gói nguồn


def test_phat_hanh_chan_token_github_kieu_moi():
    """Token GitHub fine-grained (``github_pat_…``): hook pre-push đã chặn, bộ quét gói phát hành thì chưa."""
    token = b"github_pat_" + b"A1b2" * 21
    files = {
        "TimClipPro/app.py": b"TOKEN = '" + token + b"'\n",
        "TimClipPro/engine.py": b"x = 1\n",
    }
    with pytest.raises(release_tool.LoiPhatHanh) as e:
        release_tool.chon_file_phat_hanh(files)
    assert "A1b2" not in str(e.value)


def test_goi_nguon_bat_khoa_dich_vu_luu_bang_utf16():
    """PowerShell 5.1 ``>`` ghi UTF-16: byte 0 xen giữa mọi ký tự làm mẫu không khớp — khoá lọt vào gói gửi audit."""
    noi_dung = {
        "type": "service" + "_account",
        "private" + "_key": "-----BEGIN " + "PRIVATE KEY-----\nabc",
    }
    assert dong_goi.ly_do_noi_dung_nhay_cam(json.dumps(noi_dung).encode("utf-16"))
    assert dong_goi.ly_do_noi_dung_nhay_cam(json.dumps(noi_dung).encode("utf-16-le"))
    assert not dong_goi.ly_do_noi_dung_nhay_cam(
        json.dumps({"ten": "Kho SML"}).encode("utf-16")
    )


# ---------------------------------------------------------------- giám sát tải


def test_giam_sat_callback_loi_van_giet_ffmpeg_khi_bam_dung(tmp_path):
    """Callback nhịp (hiển thị) ném lỗi mỗi chu kỳ → bước kiểm Dừng phía sau không bao giờ chạy, ffmpeg tải tiếp."""
    huy = threading.Event()
    huy.set()
    da_giet = []

    def nhip():
        raise RuntimeError("giao diện đã đóng")

    gs = giam_sat_tai.GiamSatTai(
        str(tmp_path / "vid"),
        None,
        huy,
        khi_nhip=nhip,
        tim=lambda _p: [SimpleNamespace(pid=101)],
        ham_giet=lambda ds: da_giet.append([p.pid for p in ds]) or len(ds),
    )
    gs.tick(0.0)
    assert da_giet == [[101]]


# ---------------------------------------------------------------- đồng bộ kênh


def test_dung_lai_so_da_tai_khong_xoa_video_luot_khac_vua_ghi(tmp_path, monkeypatch):
    """«Dựng lại danh sách đã tải» chụp đĩa TRƯỚC khi lấy khoá: video một lượt đồng bộ khác vừa đặt + ghi sổ trong
    khoảng đó bị xoá khỏi sổ."""
    cs = ChannelSync(str(tmp_path / "kho"))
    (Path(cs.dest) / "A [aaaaaaaaaaa].opus").write_bytes(b"a")
    quet_that = cs.quet_id_tren_dia
    luong = []

    def quet_roi_luot_khac_ghi():
        kq = quet_that()
        (Path(cs.dest) / "B [bbbbbbbbbbb].opus").write_bytes(b"b")
        t = threading.Thread(target=cs._mark_done, args=("bbbbbbbbbbb",))
        t.start()
        luong.append(t)
        t.join(
            timeout=1.0
        )  # chụp đĩa ngoài khoá: lượt kia ghi sổ xong ngay trong khoảng này
        return kq

    monkeypatch.setattr(cs, "quet_id_tren_dia", quet_roi_luot_khac_ghi)
    cs.sua_archive()
    luong[0].join(timeout=30)
    assert {"aaaaaaaaaaa", "bbbbbbbbbbb"} <= cs.done_ids()


def test_doi_soat_file_da_doi_lay_do_dai_cua_file_moi(tmp_path):
    """Metadata còn ``duration_media`` 60 giây của bản cụt cũ; bản đủ 600 giây đã thay vào kho nhưng chưa kịp ghi
    metadata. Đối soát đóng dấu file MỚI mà giữ số đo CŨ — resolver ưu tiên ``duration_media`` nên clip mãi là 60 giây."""
    cs = ChannelSync(str(tmp_path / "kho"))
    ten = "Clip [abcdefghijk].opus"
    (Path(cs.dest) / ten).write_bytes(b"x" * 1000)
    ghi_json_an_toan(
        cs.meta_file,
        {
            ten: {
                "id": "abcdefghijk",
                "title": "Clip",
                "url": "https://youtu.be/abcdefghijk",
                "upload_date": "20260101",
                "duration": 600,
                "duration_media": 60.0,
            }
        },
    )
    cs._doi_soat({"abcdefghijk": (ten, 600.0, ten, True)})
    assert cs.load_meta()[ten]["duration_media"] == 600.0
    # File KHÔNG đổi (dấu khớp): số đo đã lưu giữ nguyên, không ghi lại mỗi lượt.
    meta = cs.load_meta()
    meta[ten]["duration_media"] = 599.98
    ghi_json_an_toan(cs.meta_file, meta)
    cs._doi_soat({"abcdefghijk": (ten, 600.0, ten, True)})
    assert cs.load_meta()[ten]["duration_media"] == 599.98
