# -*- coding: utf-8 -*-
"""Phép kiểm «máy giải được thử thách JavaScript của YouTube» (``ytdlp_chung.kha_nang_js``) và yt-dlp THẬT, ngoại tuyến.

Cookie đăng nhập chỉ dùng được khi yt-dlp 2026.08.19 có (1) Node.js ≥ 22 — bật qua ``js_runtimes`` vì yt-dlp chỉ tự bật
deno — và (2) gói ``yt-dlp-ejs`` ĐÚNG bản yt-dlp ghim (0.8.0; khớp băm). Tài liệu: https://github.com/yt-dlp/yt-dlp/wiki/EJS.

Test dùng yt-dlp thật CHẶN MẠNG ngay trong test (không dựa vào sitecustomize của máy chạy), cookie là file GIẢ trong thư
mục tạm — không đọc cookie trình duyệt nào. Test cần Node/EJS thật thì bỏ qua (skip) khi máy chưa có, kèm lý do.
"""

import importlib.metadata
import json
import os
import re
import socket
import subprocess
from pathlib import Path

import pytest
import yt_dlp

import truy_cap_youtube as t
import youtube_doctor
import ytdlp_chung as y

LOCK = Path(__file__).resolve().parents[1] / "requirements-lock.txt"
URL = "https://www.youtube.com/watch?v=OPgD5wl0fAY"
CANH_GAC = "CANHGAC7f3aKHONGDUOCLO"


@pytest.fixture
def chan_mang(monkeypatch):
    """Chặn mọi kết nối ra ngoài (chỉ cho loopback) — test chạy được cả trên máy không có công cụ chặn mạng."""
    goc_connect, goc_gai = socket.socket.connect, socket.getaddrinfo
    noi_bo = ("127.0.0.1", "::1", "localhost")

    def connect(self, dia_chi):
        if isinstance(dia_chi, tuple) and dia_chi and str(dia_chi[0]) not in noi_bo:
            raise OSError(f"test chặn mạng: {dia_chi!r}")
        return goc_connect(self, dia_chi)

    def getaddrinfo(host, *a, **k):
        if host not in (None, *noi_bo):
            raise socket.gaierror(f"test chặn DNS: {host!r}")
        return goc_gai(host, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(yt_dlp.cookies, "extract_cookies_from_browser",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("cấm đọc cookie trình duyệt")))


def _cookie_gia(tmp_path) -> str:
    """Đủ để yt-dlp coi là ĐÃ ĐĂNG NHẬP (LOGIN_INFO + SAPISID — `_has_auth_cookies`); giá trị giả có chuỗi canh gác."""
    p = tmp_path / "cookie_gia.txt"
    p.write_text("# Netscape HTTP Cookie File\n" + "".join(
        "\t".join([".youtube.com", "TRUE", "/", "TRUE", "2147483647", ten, f"GIA_{CANH_GAC}"]) + "\n"
        for ten in ("LOGIN_INFO", "SAPISID", "__Secure-3PAPISID")), encoding="utf-8", newline="\n")
    return str(p)


# ---------------------------------------------------------------- khớp với yt-dlp và lock

def test_node_toi_thieu_khop_yt_dlp():
    from yt_dlp.utils._jsruntime import NodeJsRuntime

    assert y.NODE_TOI_THIEU == NodeJsRuntime.MIN_SUPPORTED_VERSION


def _ghim(ten: str) -> str:
    m = re.search(rf"^{re.escape(ten)}==(\S+)", LOCK.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else ""


def test_lock_ghim_yt_dlp_ejs_dung_ban_yt_dlp_can():
    """Nâng yt-dlp mà quên nâng yt-dlp-ejs thì yt-dlp BỎ QUA script cũ (khác major.minor) → cookie lại hỏng cả lô."""
    from yt_dlp.extractor.youtube.jsc._builtin import vendor

    ejs, ban_ytdlp = _ghim("yt-dlp-ejs"), _ghim("yt-dlp")
    assert ejs, "lock phải ghim yt-dlp-ejs (cookie đăng nhập cần nó)"
    if importlib.metadata.version("yt-dlp") != ban_ytdlp:
        pytest.skip(f"venv có yt-dlp {importlib.metadata.version('yt-dlp')} ≠ lock {ban_ytdlp}")
    assert vendor.VERSION == ejs
    can = [r for r in importlib.metadata.requires("yt-dlp") or () if r.replace(" ", "").startswith("yt-dlp-ejs==")]
    assert can and all(r.replace(" ", "").split(";")[0] == f"yt-dlp-ejs=={ejs}" for r in can), can


# ---------------------------------------------------------------- tìm node, đọc phiên bản

def _ten_node() -> str:
    return "node.exe" if os.name == "nt" else "node"


def test_tim_node_bo_qua_thu_muc_hien_hanh(tmp_path, monkeypatch):
    """yt-dlp/`shutil.which` trên Windows xét cả thư mục làm việc: một node.exe lạ ở đó sẽ được CHẠY."""
    lam_viec = tmp_path / "lam_viec"
    lam_viec.mkdir()
    (lam_viec / _ten_node()).write_bytes(b"")
    monkeypatch.chdir(lam_viec)
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", str(tmp_path / "khong_co")]))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    monkeypatch.delenv("ProgramW6432", raising=False)
    assert y._tim_node() == ""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / _ten_node()).write_bytes(b"")
    monkeypatch.setenv("PATH", os.pathsep.join([".", str(bin_)]))
    assert y._tim_node() == str(bin_ / _ten_node())


def test_tim_node_o_thu_muc_cai_mac_dinh(tmp_path, monkeypatch):
    (tmp_path / "pf" / "nodejs").mkdir(parents=True)
    (tmp_path / "pf" / "nodejs" / _ten_node()).write_bytes(b"")
    monkeypatch.setenv("PATH", str(tmp_path / "khong_co"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    monkeypatch.delenv("ProgramW6432", raising=False)
    assert y._tim_node() == str(tmp_path / "pf" / "nodejs" / _ten_node())


def test_phien_ban_node_doc_dung_nho_theo_file_khong_nho_lan_hong(tmp_path, monkeypatch):
    monkeypatch.setattr(y, "_CACHE_NODE", {})
    node = tmp_path / _ten_node()
    node.write_bytes(b"1")
    goi = []

    def chay(lenh, **k):
        goi.append(lenh)
        return subprocess.CompletedProcess(lenh, 0, stdout="v24.21.0\n", stderr="")

    assert y._phien_ban_node(str(node), chay) == "24.21.0"
    assert y._phien_ban_node(str(node), chay) == "24.21.0" and len(goi) == 1, "mỗi lượt chỉ tốn một lần stat"
    assert goi[0] == [str(node), "--version"]
    node.write_bytes(b"22")             # nâng Node: file đổi → hỏi lại thật
    assert y._phien_ban_node(str(node), chay) == "24.21.0" and len(goi) == 2

    def hong(lenh, **k):
        goi.append(lenh)
        return subprocess.CompletedProcess(lenh, 1, stdout="", stderr="lỗi")

    node.write_bytes(b"333")
    assert y._phien_ban_node(str(node), hong) == "" and y._phien_ban_node(str(node), hong) == ""
    assert len(goi) == 4, "lần hỏng không được nhớ"


@pytest.mark.parametrize("node,pb,ejs,san_sang,chua", [
    ("", "", ("0.8.0", "0.8.0", ""), False, ["không thấy node"]),
    ("n", "", ("0.8.0", "0.8.0", ""), False, ["không chạy được"]),
    ("n", "20.11.1", ("0.8.0", "0.8.0", ""), False, ["20.11.1", "quá cũ", "≥ 22"]),
    ("n", "22.0.0", ("0.8.0", "0.8.0", ""), True, []),
    ("n", "24.21.0", ("", "0.8.0", "máy thiếu gói yt-dlp-ejs 0.8.0"), False, ["thiếu gói yt-dlp-ejs 0.8.0"]),
    ("", "", ("", "0.8.0", "máy thiếu gói yt-dlp-ejs 0.8.0"), False, ["Node.js ≥ 22", "; máy thiếu gói yt-dlp-ejs"]),
])
def test_kha_nang_js_tung_truong_hop(monkeypatch, kha_nang_js_that, node, pb, ejs, san_sang, chua):
    monkeypatch.setattr(y, "_tim_node", lambda: node)
    monkeypatch.setattr(y, "_phien_ban_node", lambda _p: pb)
    monkeypatch.setattr(y, "_kiem_ejs", lambda: ejs)
    kn = kha_nang_js_that()
    assert kn.san_sang is san_sang
    assert all(c in kn.ly_do for c in chua), kn.ly_do
    assert (kn.ly_do == "") is san_sang
    if san_sang:
        assert kn.mo_ta() == f"Node.js {pb} + yt-dlp-ejs 0.8.0"


def test_kiem_ejs_dung_luat_cua_yt_dlp(monkeypatch, kha_nang_js_that):
    from yt_dlp.dependencies import yt_dlp_ejs
    from yt_dlp.extractor.youtube.jsc._builtin import vendor

    monkeypatch.setattr(y, "_CACHE_EJS", [])
    co, can, loi = y._kiem_ejs()
    assert can == vendor.VERSION
    if yt_dlp_ejs is None:
        assert co == "" and f"thiếu gói yt-dlp-ejs {vendor.VERSION}" in loi
    else:
        assert (co, loi) == (yt_dlp_ejs.version, ""), "gói đúng bản + đúng băm phải được nhận"


def test_kiem_ejs_sai_ban_hay_sai_bam(monkeypatch, kha_nang_js_that):
    import types

    import yt_dlp.dependencies as dep

    giai = types.SimpleNamespace(lib=lambda: "lib khác", core=lambda: "core khác")
    gia = types.SimpleNamespace(version="0.8.0", yt=types.SimpleNamespace(solver=giai))
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp_ejs", gia)
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp_ejs.yt", gia.yt)
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp_ejs.yt.solver", giai)
    monkeypatch.setattr(dep, "yt_dlp_ejs", gia)
    monkeypatch.setattr(y, "_CACHE_EJS", [])
    assert "sai băm" in y._kiem_ejs()[2]
    gia.version = "0.7.9"
    monkeypatch.setattr(y, "_CACHE_EJS", [])
    assert "không khớp" in y._kiem_ejs()[2]


# ---------------------------------------------------------------- yt-dlp THẬT trên máy này (ngoại tuyến)

def _may_san_sang(kha_nang_js_that):
    kn = kha_nang_js_that()
    if not kn.san_sang:
        pytest.skip(f"máy chưa giải được thử thách JavaScript: {kn.ly_do}")
    return kn


def test_yt_dlp_that_dung_node_va_ejs_khi_co_cookie(tmp_path, chan_mang, kha_nang_js_that):
    """Đúng tuỳ chọn tool dựng (`CauHinhMang.tuy_chon`) → yt-dlp thật: đã đăng nhập, Node sẵn sàng, script EJS lấy từ
    GÓI python (không tải web), client đăng nhập đều nhận cookie; Node chạy được bộ giải trên player TỔNG HỢP."""
    kn = _may_san_sang(kha_nang_js_that)
    from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS
    from yt_dlp.extractor.youtube.jsc.provider import JsChallengeRequest, JsChallengeType, NChallengeInput

    opts = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path)).tuy_chon("metadata", logger=y.BoGhiYtdlp())
    with yt_dlp.YoutubeDL(opts) as ydl:
        ie = ydl.get_info_extractor("Youtube")
        ie.initialize()
        assert ie.is_authenticated
        node = next(p for p in ie._jsc_director.providers.values() if p.PROVIDER_NAME == "node")
        assert node.is_available() and node.runtime_info.path == kn.node
        lib = node._lib_script
        assert lib.source.value == "python package" and lib.version == kn.ejs_phien_ban
        ds = list(ie._get_requested_clients(URL, {}, False))
        assert ds and "web_embedded" in ds and all(INNERTUBE_CLIENTS[c]["SUPPORTS_COOKIES"] for c in ds), ds
        player = "var _yt_player={};(function(g){})(_yt_player);"
        hoi = [JsChallengeRequest(JsChallengeType.N, NChallengeInput("https://www.youtube.com/s/player/0/base.js",
                                                                     ["abc"]), "OPgD5wl0fAY")]
        ra = json.loads(node._run_js_runtime(node._construct_stdin(player, False, hoi)))
        assert ra["type"] == "result" and len(ra["responses"]) == 1, "Node + EJS chạy và trả JSON đúng khuôn"


def test_yt_dlp_that_khong_cookie_khong_dung_js(chan_mang):
    """Đường không-cookie đã nghiệm thu: tool không bật bộ chạy JS → yt-dlp dùng visionos (không cần JS) — đúng
    ``['visionos']`` trên máy không có deno (PC2)."""
    opts = y.CauHinhMang().tuy_chon("metadata", logger=y.BoGhiYtdlp())
    assert "js_runtimes" not in opts
    with yt_dlp.YoutubeDL(opts) as ydl:
        ie = ydl.get_info_extractor("Youtube")
        ie.initialize()
        assert not ie.is_authenticated
        ds = list(ie._get_requested_clients(URL, {}, False))
        assert ds[0] == "visionos"
        if not any(p.is_available() for p in ie._jsc_director.providers.values()):
            assert ds == ["visionos"]


class _GhiHet(y.BoGhiYtdlp):
    """Logger gom CẢ debug — để kiểm rò rỉ ở mức chi tiết nhất."""

    def __init__(self):
        super().__init__()
        self.tat_ca: list = []

    def debug(self, msg):
        self.tat_ca.append(str(msg))

    def info(self, msg):
        self.tat_ca.append(str(msg))

    def warning(self, msg):
        self.tat_ca.append(str(msg))
        super().warning(msg)

    def error(self, msg):
        self.tat_ca.append(str(msg))
        super().error(msg)


def test_khong_lo_cookie_vao_log_dau_ra_hay_loi(tmp_path, monkeypatch, chan_mang, caplog, capfd, kha_nang_js_that):
    """Trích xuất thật (mạng bị chặn → lỗi) với cookie giả + Node (nếu máy có), verbose: giá trị cookie không được xuất
    hiện ở log yt-dlp (kể cả debug), log của tool, stdout/stderr, câu lỗi hay bản phân loại."""
    import logging

    if not kha_nang_js_that().san_sang:
        # Máy chưa có Node/EJS: vẫn kiểm đường cookie với một node KHÔNG tồn tại (yt-dlp coi như không có bộ chạy).
        monkeypatch.setattr(y, "kha_nang_js", lambda: y.KhaNangJs(True, node=str(tmp_path / "khong_co" / "node.exe"),
                                                                  node_phien_ban="0", ejs_phien_ban="0"))
    caplog.set_level(logging.DEBUG)
    bo_ghi = _GhiHet()
    opts = y.CauHinhMang(cookiefile=_cookie_gia(tmp_path)).tuy_chon(
        "metadata", logger=bo_ghi, verbose=True, extractor_retries=0, socket_timeout=5)
    with pytest.raises(Exception) as ei:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(URL, download=False)
    f = t.phan_loai_loi(ei.value)
    ra = capfd.readouterr()
    tat_ca = "\n".join([*bo_ghi.tat_ca, *bo_ghi.canh_bao, *bo_ghi.loi, caplog.text, ra.out, ra.err, str(ei.value),
                        f.human_message_vi, f.technical_summary])
    assert len(bo_ghi.tat_ca) > 5, "verbose phải sinh log để phép kiểm có ý nghĩa"
    assert CANH_GAC not in tat_ca


# ---------------------------------------------------------------- youtube-doctor

def test_youtube_doctor_bao_cookie_dung_duoc_hay_khong(tmp_path, capsys):
    kq = youtube_doctor.chan_doan(str(tmp_path))
    assert kq["kha_nang_js"] == {"san_sang": True, "node": r"C:\gia\nodejs\node.exe", "node_phien_ban": "24.0.0",
                                 "ejs_phien_ban": "0.8.0", "ly_do": ""}
    youtube_doctor._in(kq)
    assert "Cookie đăng nhập (cần giải thử thách JavaScript): DÙNG ĐƯỢC — Node.js 24.0.0 + yt-dlp-ejs 0.8.0" in \
        capsys.readouterr().out
