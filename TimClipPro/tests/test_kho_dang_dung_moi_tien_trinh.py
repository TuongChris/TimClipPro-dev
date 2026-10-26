# -*- coding: utf-8 -*-
"""Kho đang dùng là lựa chọn CỦA TỪNG TIẾN TRÌNH — sửa/xoá kho khác không được đổi nó (audit C-14).

Trường ``dang_dung`` của ``khos.json`` có HAI bên ghi khi giao diện và Watch/CLI dùng chung thư mục
dữ liệu (D-26): Watch theo lịch có watchlist ``kho: "B"`` gọi ``use_kho("B")``. Trước đây
``update_kho``/``delete_kho`` kết thúc bằng ``_ap_dung_kho(d["dang_dung"], d)`` — áp lại lựa chọn
của SỔ, nên bấm «Lưu thư mục cho kho này» (ô chọn ĐỘC LẬP với thanh bên) lặng lẽ chuyển Engine của
giao diện sang kho «B», lượt «Bắt đầu quét» kế tiếp đối chiếu nhầm kho.

Dữ liệu hoàn toàn synthetic trong ``tmp_path``: chỉ sổ đăng ký kho, không kho vân tay, không mạng.
Hai Engine cùng thư mục dữ liệu mô phỏng tiến trình giao diện và tiến trình Watch.
"""
from engine import Engine


def _eng(tmp_path) -> Engine:
    return Engine(root=str(tmp_path), data_dir=str(tmp_path / "data"),
                  out_dir=str(tmp_path / "out"))


def _giao_dien_va_watch(tmp_path, monkeypatch, *ten_kho):
    monkeypatch.delenv("TIMCLIP_RUNTIME_MODE", raising=False)
    giao_dien = _eng(tmp_path)
    for ten in ten_kho:
        giao_dien.add_kho(ten)
    giao_dien.use_kho("A")
    # Tiến trình Watch (Engine riêng, cùng data dir) chọn kho của watchlist → sổ ghi dang_dung = B.
    watch_proc = _eng(tmp_path)
    watch_proc.use_kho("B")
    # Đối chứng: chỉ ghi sổ thì Engine của giao diện chưa đổi.
    assert giao_dien.kho_dang_dung == "A"
    return giao_dien, watch_proc


def test_update_kho_khong_doi_kho_dang_dung_cua_tien_trinh_nay(tmp_path, monkeypatch):
    giao_dien, _ = _giao_dien_va_watch(tmp_path, monkeypatch, "A", "B")

    thu_muc_moi = tmp_path / "clip_goc_A"
    thu_muc_moi.mkdir()
    giao_dien.update_kho("A", str(thu_muc_moi))

    assert giao_dien.kho_dang_dung == "A", (
        f"update_kho('A') làm Engine của giao diện chuyển sang «{giao_dien.kho_dang_dung}» — "
        "kho do tiến trình Watch ghi vào dang_dung của sổ dùng chung, người dùng không chọn")
    # Kho đang dùng vừa đổi thư mục → Engine thấy thư mục mới ngay.
    assert giao_dien.kho_thu_muc == str(thu_muc_moi)
    assert giao_dien.db_file.endswith(
        next(k["db"] for k in giao_dien.list_khos() if k["ten"] == "A"))


def test_update_kho_khac_khong_doi_kho_dang_dung(tmp_path, monkeypatch):
    giao_dien, _ = _giao_dien_va_watch(tmp_path, monkeypatch, "A", "B")
    thu_muc_cu = giao_dien.kho_thu_muc

    thu_muc_b = tmp_path / "clip_goc_B"
    thu_muc_b.mkdir()
    giao_dien.update_kho("B", str(thu_muc_b))

    assert giao_dien.kho_dang_dung == "A"
    assert giao_dien.kho_thu_muc == thu_muc_cu


def test_delete_kho_khac_khong_doi_kho_dang_dung(tmp_path, monkeypatch):
    giao_dien, _ = _giao_dien_va_watch(tmp_path, monkeypatch, "A", "B", "C")

    giao_dien.delete_kho("C")

    assert giao_dien.kho_dang_dung == "A", (
        f"delete_kho('C') làm Engine của giao diện chuyển sang «{giao_dien.kho_dang_dung}»")


def test_delete_kho_dang_dung_van_lui_ve_kho_cua_so(tmp_path, monkeypatch):
    """Xoá chính kho đang dùng thì không còn gì để giữ: lùi về kho sổ đang ghi (như trước)."""
    giao_dien, _ = _giao_dien_va_watch(tmp_path, monkeypatch, "A", "B")

    giao_dien.delete_kho("A")

    assert giao_dien.kho_dang_dung == "B"
