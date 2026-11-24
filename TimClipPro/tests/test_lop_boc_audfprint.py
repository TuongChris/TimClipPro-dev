# -*- coding: utf-8 -*-
"""Lưới an toàn cho LỚP BỌC audfprint (việc nhỏ #7, đề xuất suckhoe-08).

``audfprint_match_runner.py`` và ``audfprint_progress_runner.py`` THAY HÀM của audfprint lúc chạy — không sửa source
vendored (CLAUDE.md quy tắc 3). Thay theo TÊN nên thư viện đổi tên/chữ ký là bản vá rơi im lặng: worker không báo
tiến độ, tra kho quay về bản chậm (đo 23/11: khúc 29 phút 0,9 s → 53 s) mà kết quả vẫn y hệt — so file kết quả không
bao giờ thấy. Ba lớp kiểm:

a) băm từng file ``audfprint-master/`` — đổi thư viện (kể cả thêm file) là đỏ;
b) mọi chỗ GÁN ĐÈ lên audfprint trong mã chạy (dò bằng ``ast``) đều có trong bảng; hàm gốc còn đó; hàm thay nhận được
   ĐÚNG lời gọi mà audfprint gửi cho hàm gốc, và hàm gốc nhận được lời gọi mà hàm thay gửi lại;
c) đếm số lần gọi ``_exact_cat_lat`` khi chạy ``audfprint match`` QUA lớp bọc, nhánh một nhân và nhánh joblib — hash
   tổng hợp trong file ``.afpt`` tính sẵn (audfprint không đọc audio, không cần ffmpeg).
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import sys
from pathlib import Path

import joblib
import numpy as np
import pytest

import audfprint_match_runner as bo_khop
import audfprint_progress_runner as bo_dung

REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "audfprint-master"
sys.path.insert(0, str(VENDOR))
import audfprint  # noqa: E402
import audfprint_analyze  # noqa: E402
import audfprint_match as am  # noqa: E402
import audio_read  # noqa: E402
import hash_table  # noqa: E402

# ---------------------------------------------------------------------------
#  a) Thư viện vendored không đổi
# ---------------------------------------------------------------------------

# SHA-256 nội dung tại 642ec35, xuống dòng chuẩn hoá về LF (core.autocrlf=true đổi file khi checkout; git lưu LF).
BAM_AUDFPRINT = {
    ".gitignore": "e5e7d86e748a4bda558107d6ed84682518e09867e9c03ae3510637865214a4e0",
    "LICENSE": "4126a69d389028fd8ed1ab2f3f36fc66227f6498b942afb1f9cb684cc088b9b1",
    "Makefile": "78352c4bb90f44195cef81334440b94c161a4e6885b3aefc8cd2248038bbb0e7",
    "README-dpwe-audfprint.txt": "6e1303a1617bae711974283bb3e51d77f51f11fe2abe040cb59b2d02eb7802d9",
    "README.md": "b77f4e9b1b354ca219067f15b96d94ad33b5740053c7f3902615907c15775fdb",
    "__init__.py": "7a867a19f89f6ea84c2cdce396a44356297ecb20643a654df6e8d280958d0656",
    "audfprint.py": "039b5807386da29febc94707b428ad8a1ef03dca6e2d2bc0ca208a6175a371d9",
    "audfprint_analyze.py": "46a9401e04cd31b1ffff1ce327c0dc84d852d3fb557e8195940e895d4391f9e1",
    "audfprint_match.py": "58f609722a4623c56bb18ac28bd099ea7e29f0784cf5e4c86cf5813c484d016f",
    "audio_read.py": "a09f1477115560aaf4c9fd85fc19e6d39ace8ad790f2c300759f17ae335f1cfa",
    "comp_file_lines.py": "8c709771f484dec722f29f24acee6a8360e515eed1e5be75e0d4f0042cfe4b02",
    "config.txt": "42846b07bd3f2f7bd6e0dea3f1bb8d9fa0318871b41601aeaa81a8c20648d2b4",
    "config_tiny.txt": "692e2da3ede1e431d1a64b2107c14b69ee7a2f38c804a8d2ea0ad8d99beef871",
    "dpwe_builder.py": "52718a0f123afd6038878b5866b7e45c539b5b24afeae7edd36159d6ac1e029a",
    "dpwe_matcher.py": "269ca9540162cedba3c9f32824858e1c9c9e6430fce17047d3cdcb0078c0caf2",
    "hash_table.py": "6e112ece3298e2d1f20bb44e640b2a78d1f8a994c31b75f4df8a0449f1a4a201",
    "requirements.txt": "34f6d1a4577e9dcc1930fda85036623b49d4e006090ff19aaddebe1420a720b3",
    "searching_for_ads.md": "8302ba1ec78b32cb596d828f78854327127e883f3c78eb00093cc8c3766186fa",
    "stft.py": "bb865cfc8c1f5404e085fac9b108cdf312b1ba58e6fdfdb3037945269c0ede2a",
}


def test_thu_vien_audfprint_vendored_khong_doi():
    thuc = {p.relative_to(VENDOR).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in VENDOR.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    doi = sorted(t for t in BAM_AUDFPRINT.keys() | thuc.keys() if BAM_AUDFPRINT.get(t) != thuc.get(t))
    assert not doi, (
        f"Thư viện vendored audfprint-master/ đã đổi: {doi} (file sửa, thêm hoặc mất). Không sửa thư viện vendored "
        "(CLAUDE.md quy tắc 3) — cần đổi hành vi thì bọc ngoài. Nếu CỐ Ý nâng bản audfprint: chạy test này (phần b, c), "
        "test chậm so khớp (-m slow), rồi mới cập nhật BAM_AUDFPRINT.")


# ---------------------------------------------------------------------------
#  b) Mọi chỗ vá trỏ tới hàm gốc còn tồn tại, chữ ký khớp
# ---------------------------------------------------------------------------

# Mọi chỗ GÁN ĐÈ lên audfprint trong mã chạy (khoá = (file, đích gán) đúng như ``ast.unparse``) → vì sao có.
CHO_VA = {
    ("audfprint_match_runner.py", "audfprint.matcher_file_match_to_msgs"):
        "nhánh joblib: báo khúc tra xong + gắn bản cắt lát trong worker",
    ("audfprint_match_runner.py", "type(matcher)._exact_match_counts"): "worker joblib nạp lớp Matcher mới tinh",
    ("audfprint_match_runner.py", "audfprint_match.Matcher._exact_match_counts"): "tra kho nhanh (cắt lát)",
    ("audfprint_match_runner.py", "audfprint_match.Matcher.file_match_to_msgs"): "nhánh một nhân: báo khúc tra xong",
    ("audfprint_progress_runner.py", "audfprint.multiproc_add"): "dựng kho đa nhân theo RAM, không treo",
    ("audfprint_progress_runner.py", "audfprint.do_cmd"): "dựng kho một nhân cũng qua lịch RAM",
    ("audfprint_progress_runner.py", "audio_read.audio_read"): "phát phase decoding + giữ lý do lỗi giải mã",
    ("audfprint_progress_runner.py", "audio_read.FFmpegAudioFile.read_data.__defaults__"):
        "FFmpeg im 300 giây mới là treo (thư viện: 10 giây)",
}
_TEN_MODULE_VENDORED = ("audfprint", "audfprint_match", "audfprint_analyze", "audio_read", "hash_table", "stft")


def _cho_gan_de_trong_ma_chay() -> set:
    """(file, đích) của mọi phép gán vào thuộc tính module audfprint (hoặc ``type(...)``) trong ``TimClipPro/*.py``."""
    tim = set()
    for p in sorted(REPO.glob("*.py")):
        nguon = p.read_text(encoding="utf-8")
        if not any(m in nguon for m in _TEN_MODULE_VENDORED):
            continue
        for nut in ast.walk(ast.parse(nguon)):
            if isinstance(nut, ast.Assign):
                dich = nut.targets
            elif isinstance(nut, (ast.AugAssign, ast.AnnAssign)):
                dich = [nut.target]
            else:
                continue
            for d in dich:
                for e in d.elts if isinstance(d, (ast.Tuple, ast.List)) else [d]:
                    chuoi = ast.unparse(e)
                    if isinstance(e, ast.Attribute) and (chuoi.split(".")[0] in _TEN_MODULE_VENDORED
                                                         or chuoi.startswith("type(")):
                        tim.add((p.name, chuoi))
    return tim


def test_moi_cho_gan_de_audfprint_deu_co_trong_bang_kiem():
    tim = _cho_gan_de_trong_ma_chay()
    assert tim == set(CHO_VA), (
        f"Chỗ vá audfprint chưa có trong bảng kiểm: {sorted(tim - set(CHO_VA))}; trong bảng mà không còn trong mã: "
        f"{sorted(set(CHO_VA) - tim)}. Thêm/bỏ ở CHO_VA và ở phép kiểm chữ ký bên dưới — chỗ vá không được kiểm sẽ "
        "rơi im lặng khi thư viện đổi.")


def test_cho_va_tro_toi_ham_goc_ton_tai_va_khop_chu_ky(monkeypatch):
    """Cài HAI lớp bọc lên audfprint THẬT (không chạy lệnh nào); monkeypatch trả lại nguyên trạng sau test."""
    doc = audio_read.FFmpegAudioFile.read_data
    diem = ((audfprint, "matcher_file_match_to_msgs"), (audfprint, "multiproc_add"), (audfprint, "do_cmd"),
            (am.Matcher, "_exact_match_counts"), (am.Matcher, "file_match_to_msgs"), (audio_read, "audio_read"))
    mat = [f"{getattr(o, '__name__', o)}.{t}" for o, t in diem if not callable(getattr(o, t, None))]
    assert not mat, f"audfprint không còn hàm mà lớp bọc thay: {mat} — lớp bọc sẽ gắn vào chỗ không ai gọi."
    goc = {t: getattr(o, t) for o, t in diem}
    for o, t in diem:
        monkeypatch.setattr(o, t, goc[t])                      # ghi nhận để trả lại sau test
    monkeypatch.setattr(doc, "__defaults__", doc.__defaults__)
    monkeypatch.setattr(bo_dung, "_DA_CAI_THEO_DOI_GIAI_MA", False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(audfprint, "main", lambda argv: None)  # chỉ cài, không chạy lệnh
    bo_khop.main(["audfprint_match_runner.py", str(VENDOR / "audfprint.py"), "match"])
    bo_dung.cai_dat_instrumentation(audfprint)

    assert audfprint.matcher_file_match_to_msgs is bo_khop._khop_mot_khuc
    assert am.Matcher._exact_match_counts is bo_khop._exact_cat_lat
    assert audfprint.multiproc_add is bo_dung.instrumented_multiproc_add
    assert all(getattr(o, t) is not goc[t] for o, t in diem), "có chỗ vá không thay được hàm của audfprint"
    co_mac_dinh = {p.name: p.default for p in inspect.signature(doc).parameters.values() if p.default is not p.empty}
    assert co_mac_dinh == {"timeout": bo_dung.CHO_FFMPEG_S}, (
        f"FFmpegAudioFile.read_data nay có tham số mặc định {co_mac_dinh}: gán __defaults__ = (CHO_FFMPEG_S,) sẽ rơi "
        "vào tham số khác — sửa audfprint_progress_runner.cai_dat_theo_doi_giai_ma.")

    # (ai gọi → hàm nhận, số đối số theo vị trí, tên đối số theo khoá) — đúng kiểu lời gọi trong mã audfprint / lớp bọc.
    loi_goi = [
        ("audfprint.do_cmd_multiproc → matcher_file_match_to_msgs (bản thay)", audfprint.matcher_file_match_to_msgs,
         4, ()),
        ("bản thay _khop_mot_khuc → Matcher.file_match_to_msgs gốc", goc["file_match_to_msgs"], 4, ()),
        ("audfprint.do_cmd → Matcher.file_match_to_msgs (bản thay)", am.Matcher.file_match_to_msgs, 5, ()),
        ("bản thay mot_nhan → Matcher.file_match_to_msgs gốc", goc["file_match_to_msgs"], 5, ()),
        ("Matcher.match_hashes → _exact_match_counts (bản cắt lát)", am.Matcher._exact_match_counts, 5, ()),
        ("bản cắt lát → audfprint_match.find_modes", am.find_modes, 1, ("window", "threshold")),
        ("bản cắt lát → Matcher._unique_match_hashes", am.Matcher._unique_match_hashes, 4, ()),
        ("bản cắt lát → Matcher._calculate_time_ranges", am.Matcher._calculate_time_ranges, 4, ()),
        ("audfprint.do_cmd_multiproc → multiproc_add (bản thay)", audfprint.multiproc_add, 5, ()),
        ("audfprint.main → do_cmd (bản thay)", audfprint.do_cmd, 8, ("skip_existing", "strip_prefix")),
        ("bản thay → do_cmd gốc", goc["do_cmd"], 8, ("skip_existing", "strip_prefix")),
        ("Analyzer.wavfile2peaks → audio_read.audio_read (bản thay)", audio_read.audio_read, 1, ("sr", "channels")),
        ("bản thay → audio_read gốc", goc["audio_read"], 1, ("sr", "channels")),
        ("worker dựng kho → HashTable(...)", hash_table.HashTable, 0, ("hashbits", "depth", "maxtime")),
        ("worker dựng kho → HashTable.store", hash_table.HashTable.store, 3, ()),
        ("cha dựng kho → HashTable.merge", hash_table.HashTable.merge, 2, ()),
        ("worker dựng kho → Analyzer.wavfile2hashes", audfprint_analyze.Analyzer.wavfile2hashes, 2, ()),
    ]
    hong = []
    for ai_goi, ham, so_vi_tri, ten_khoa in loi_goi:
        try:
            inspect.signature(ham).bind(*range(so_vi_tri), **dict.fromkeys(ten_khoa))
        except TypeError as e:
            hong.append(f"{ai_goi}: {ham.__qualname__}{inspect.signature(ham)} — {e}")
    assert not hong, "Chữ ký audfprint / lớp bọc không còn khớp lời gọi:\n" + "\n".join(hong)

    thieu = [f"Matcher().{a}" for a in ("window", "threshcount", "find_time_range") if not hasattr(am.Matcher(), a)]
    ht = hash_table.HashTable(hashbits=8, depth=2, maxtime=16)
    thieu += [f"HashTable().{a}" for a in ("hashbits", "depth", "maxtimebits", "names", "counts", "hashesperid",
                                           "dirty") if not hasattr(ht, a)]
    assert not thieu, f"Lớp bọc đọc/ghi thuộc tính audfprint không còn: {thieu}"


# ---------------------------------------------------------------------------
#  c) Tra kho qua lớp bọc thật sự dùng bản «cắt lát»
# ---------------------------------------------------------------------------

def _kho_va_khuc(tmp_path, so_khuc=2):
    """Kho hash tổng hợp 3 clip + ``so_khuc`` khúc ``.afpt``: khúc k chứa 200 hash của clip k lệch 500 + 100k khung,
    xen 300 hash nhiễu."""
    rng = np.random.default_rng(2311)
    ht = hash_table.HashTable(hashbits=16, depth=20, maxtime=16384)
    ht.params["samplerate"] = 11025
    clip = []
    for i in range(3):
        cap = list(zip(rng.integers(0, 3000, 400).tolist(), rng.integers(0, 1 << 16, 400).tolist()))
        ht.store(f"clip{i}.opus", cap)
        clip.append(cap)
    db = tmp_path / "kho.pklz"
    ht.save(str(db))
    khuc = []
    for k in range(so_khuc):
        nhieu = zip(rng.integers(0, 4000, 300).tolist(), rng.integers(0, 1 << 16, 300).tolist())
        p = tmp_path / f"khuc{k}.afpt"
        audfprint_analyze.hashes_save(str(p), sorted({(t + 500 + 100 * k, h) for t, h in clip[k][:200]} | set(nhieu)))
        khuc.append(str(p))
    return str(db), khuc


@pytest.mark.parametrize("ncores", [1, 2])
def test_tra_kho_qua_lop_boc_di_qua_ban_cat_lat(tmp_path, monkeypatch, capsys, ncores):
    db, khuc = _kho_va_khuc(tmp_path)
    for o, t in ((audfprint, "matcher_file_match_to_msgs"), (am.Matcher, "_exact_match_counts"),
                 (am.Matcher, "file_match_to_msgs")):
        monkeypatch.setattr(o, t, getattr(o, t))               # main() vá toàn cục: trả lại sau test
    monkeypatch.setattr(sys, "path", list(sys.path))
    cat_lat, khop_mot_khuc = bo_khop._exact_cat_lat, bo_khop._khop_mot_khuc
    goi, qua_worker = [], []

    def dem(self, hits, ids, rawcounts, hashesfor=None):
        goi.append(len(hits))
        return cat_lat(self, hits, ids, rawcounts, hashesfor)

    def ghi_worker(matcher, analyzer, hash_tab, filename):
        qua_worker.append(filename)
        return khop_mot_khuc(matcher, analyzer, hash_tab, filename)

    monkeypatch.setattr(bo_khop, "_exact_cat_lat", dem)
    monkeypatch.setattr(bo_khop, "_khop_mot_khuc", ghi_worker)
    # Đếm lần gọi cần CÙNG tiến trình nên joblib chạy bằng luồng; worker tiến trình thật (loky) đã có test chậm
    # test_tra_kho_nhanh so opfile, còn worker «mới tinh» thì test ngay dưới.
    with joblib.parallel_config(backend="threading"):
        bo_khop.main(["audfprint_match_runner.py", str(VENDOR / "audfprint.py"), "match", "--dbase", db,
                      "--ncores", str(ncores), "--continue-on-error", "--find-time-range", "--exact-count",
                      "--min-count", "10", "--max-matches", "20", *khuc])
    ra = capsys.readouterr().out
    assert len(goi) == len(khuc), (
        f"Tra kho {len(khuc)} khúc (ncores={ncores}) mà bản «cắt lát» chạy {len(goi)} lần: tra kho đã quay về "
        "Matcher._exact_match_counts gốc (chậm hàng chục lần với kho dày) — kiểm chỗ vá trong audfprint_match_runner.")
    if ncores > 1:
        assert sorted(qua_worker) == sorted(khuc), (
            "Nhánh joblib không còn gọi audfprint.matcher_file_match_to_msgs: worker tiến trình thật sẽ tra bằng bản "
            "gốc và không báo «khúc đã tra xong».")
    for k in range(len(khuc)):
        assert f"clip{k}.opus" in ra, f"đối chứng: khúc {k} phải khớp clip{k} — dữ liệu thử hỏng?\n{ra[-2000:]}"
    assert ra.count(bo_khop.PREFIX) >= len(khuc), "thiếu dòng «khúc đã tra kho xong» cho engine"


def test_worker_moi_tinh_tu_gan_ban_cat_lat_truoc_khi_tra(tmp_path, monkeypatch, capsys):
    """Worker joblib (tiến trình loky) nạp lớp Matcher CHƯA vá: ``_khop_mot_khuc`` phải tự gắn bản cắt lát rồi mới tra."""
    db, khuc = _kho_va_khuc(tmp_path, so_khuc=1)
    monkeypatch.setattr(am.Matcher, "_exact_match_counts", am.Matcher._exact_match_counts)
    cat_lat, goi = bo_khop._exact_cat_lat, []
    monkeypatch.setattr(bo_khop, "_exact_cat_lat", lambda self, *a: goi.append(1) or cat_lat(self, *a))
    m = am.Matcher()
    m.exact_count = m.find_time_range = m.verbose = True
    m.threshcount, m.max_returns = 10, 20
    msgs = bo_khop._khop_mot_khuc(m, audfprint_analyze.Analyzer(), hash_table.HashTable(db), khuc[0])
    assert goi == [1], "worker mới tinh tra kho bằng Matcher._exact_match_counts gốc (không gắn bản cắt lát)"
    assert any("clip0.opus" in x for x in msgs), msgs
    assert bo_khop.PREFIX + khuc[0] in capsys.readouterr().out
