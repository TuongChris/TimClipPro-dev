# -*- coding: utf-8 -*-
"""Chống «bóng» của âm thanh lặp khi gộp mảnh khớp — phần thuần của ``Engine._merge`` (P0, 10/10/2026).

VẤN ĐỀ (điều tra P0 trên 16 video tổng hợp, 21 lần dùng có ground truth)

Nhạc có nhịp trống đều, vòng hợp âm hay một đoạn lặp y hệt làm audfprint trả thêm những căn chỉnh của CÙNG clip
lệch bội số nửa ô nhịp so với căn chỉnh thật — gọi là «bóng». Bóng phủ cùng vùng video với căn chỉnh thật nhưng
yếu hơn hẳn (tỷ số hash ≤ 0,30, đa số 0,09–0,18). ``_merge`` trước đây:

* neo mốc đầu clip vào mảnh có vùng SỚM NHẤT của nhóm — một bóng 34 hash đủ kéo lệch mốc tới ±``dedup_s``;
* để nhóm toàn bóng thành ứng viên riêng ≥ 1.000 hash: «đạt chuẩn», dòng báo cáo thừa «Rất chắc chắn», làm phồng
  «Tổng số đoạn phát hiện».

Chỉ khi âm thanh lặp Y HỆT TỪNG MẪU thì nhiều mốc giải thích video như nhau (tỷ số ≈ 1): mốc mơ hồ thật.

NGUYÊN TẮC: một giây video chỉ có thể là MỘT vị trí trong clip gốc.

CÁCH LÀM — chỉ đổi MỐC và việc nhóm toàn bóng thành ứng viên. Mọi con số bằng chứng của nhóm thật giữ nguyên: gom
nhóm, tích phân hash, độ dài khớp, vùng khớp, cận trên vẫn tính trên ĐỦ mảnh như cũ. Xoá bóng trước khi gộp (bản
đầu của phương án) làm nhóm thật mất 0–1,1% hash và có thể rớt một ứng viên sát ngưỡng 1.000 — nên không xoá.

1. ``phan_loai_manh`` — với từng (clip, hệ số tốc độ), xét mảnh từ mạnh tới yếu; gom căn chỉnh cùng vị trí đặt
   (lệch ≤ ``DUNG_SAI_ALIGN_S`` so với mảnh mạnh nhất của vị trí đó) thành ``ViTriDat``. Mảnh khác vị trí mà vùng
   video nằm ≥ ``TY_LE_PHU`` trong PHẠM VI của một vị trí đặt mạnh hơn là «bóng» (hash ≤ ``TY_LE_BONG`` × mảnh mạnh
   nhất của vị trí đó) hoặc «đối thủ» ngang ngửa (lớn hơn — âm thanh lặp y hệt). Xét theo phạm vi của VỊ TRÍ chứ
   không theo từng mảnh: căn chỉnh thật bị trôi tốc độ rất nhỏ vỡ thành nhiều mảnh có «lỗ» giữa chúng, và bóng nằm
   trong lỗ không bị mảnh thật NÀO phủ quá nửa (video B13 của bộ điều tra).
2. Nhóm (gom như cũ) không có mảnh «chính» nào → không thành ứng viên.
3. Mốc đầu clip lấy từ mảnh «chính» sớm nhất — bóng và đối thủ không bao giờ làm mốc.
4. ``gop_cung_vi_tri`` (C') — các nhóm có mảnh chính CÙNG vị trí đặt là MỘT lần dùng → gộp, chỉ khi không đổi kết
   luận chấp nhận: một nhóm đã đạt bậc A và nhóm gộp vẫn đạt bậc A.
5. ``bang_chung_moc`` (B) — cờ mốc mơ hồ, các mốc thay thế, tỷ số đối thủ, xét trên vị trí đặt LÀM MỐC của dòng.
   Độ chắc chắn của NGUỒN (``Match.confidence``) không đổi.

HỆ QUẢ: tập ứng viên đạt chuẩn chỉ có thể MẤT nhóm toàn bóng; nhóm còn lại giữ nguyên số liệu, trừ nhóm do C' gộp
(mà một phần của nó đã đạt chuẩn). Không sinh dương tính mới ở mức video ⇒ âm tính cũ vẫn đúng, chữ ký chính sách
(``engine.chu_ky_chinh_sach``) giữ nguyên — các hằng số dưới đây vì vậy nằm ở module này, KHÔNG ở ``Config``; đổi
chúng là đổi chính sách nhận diện, cần quyết định riêng (docs/ai/DECISIONS.md).

Module thuần: không I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from chap_nhan_khop import BAC_TUYET_DOI, danh_gia_chap_nhan

DUNG_SAI_ALIGN_S = 0.5          # lệch align ≤ 0,5 s so với mảnh mạnh nhất của vị trí: cùng vị trí (khúc gối, trôi nhỏ)
TY_LE_PHU = 0.5                 # vùng video của mảnh nằm ≥ 50% trong phạm vi của vị trí đặt mạnh hơn
TY_LE_BONG = 0.5                # ≤ 50% hash mảnh mạnh nhất của vị trí đó: bóng; > 50%: đối thủ ngang ngửa
LECH_ALIGN_GOC_S = 0.1          # C': phần lệch align không do trôi (khung 23 ms của audfprint, khúc gối)
TRAN_LECH_CUNG_VI_TRI_S = 1.0   # C': trần lệch align của hai mảnh cùng vị trí đặt
SO_MOC_THAY_THE_TOI_DA = 20

CHINH = "chinh"
BONG = "bong"
DOI_THU = "doi_thu"


@dataclass
class ViTriDat:
    """Một vị trí đặt clip trên video: cụm căn chỉnh cùng align, chỉ gồm mảnh «chính»."""
    align: float                # align của mảnh mạnh nhất (mảnh đầu tiên của vị trí)
    hash_manh_nhat: int
    tu: float                   # phạm vi video phủ bởi các mảnh của vị trí
    den: float


@dataclass(frozen=True)
class NhanManh:
    loai: str                   # CHINH | BONG | DOI_THU
    vi_tri: int                 # CHINH: vị trí của chính nó; BONG/DOI_THU: vị trí đặt mạnh hơn phủ nó
    ty_so: float = 0.0          # BONG/DOI_THU: hash mảnh / hash mảnh mạnh nhất của vị trí phủ nó


def he_so(x: dict) -> float:
    """Hệ số tốc độ của mảnh, làm tròn như ``_merge`` (mảnh lượt thường không có khoá → 1,0)."""
    return round(float(x.get("he_so", 1.0) or 1.0), 5)


def _phu(x: dict, tu: float, den: float) -> float:
    """Độ dài (giây) phần vùng video của mảnh ``x`` nằm trong [tu, den]."""
    return max(0.0, min(x["bat_dau"] + x["khop"], den) - max(x["bat_dau"], tu))


def phan_loai_manh(manh: list) -> tuple:
    """Nhãn của TỪNG mảnh (cùng thứ tự ``manh``) và danh sách vị trí đặt: ``(list[NhanManh], list[ViTriDat])``.

    Hai bước, cho từng (clip, hệ số tốc độ) — mảnh của hai clip khác nhau, hay hai hệ số tốc độ khác nhau (không
    cùng trục khúc), không bao giờ xét nhau:

    1. Gom mảnh thành cụm theo vị trí đặt: lệch align ≤ ``DUNG_SAI_ALIGN_S`` so với mảnh mạnh nhất của cụm.
    2. Xét cụm theo TỔNG hash giảm dần. Mảnh nằm ≥ ``TY_LE_PHU`` trong phạm vi một vị trí đã giữ là bóng/đối thủ của
       vị trí đó; phần còn lại của cụm là mảnh chính, phạm vi của chúng thành một vị trí đặt mới.

    Phải gom cụm TRƯỚC rồi mới xét: xét từng mảnh theo hash thì một đối thủ mạnh hơn các mảnh YẾU của vị trí thật
    được xét trước khi phạm vi của vị trí thật kịp nở tới chỗ nó, và thành một vị trí riêng. Thứ tự xét tất định.
    """
    nhan: list = [None] * len(manh)
    vi_tri: list = []
    theo_khoa: dict = {}
    for i, x in enumerate(manh):
        theo_khoa.setdefault((x["clip"], he_so(x)), []).append(i)
    for chi_so in theo_khoa.values():
        cum: list = []                  # mỗi cụm: chỉ số mảnh, mảnh mạnh nhất đứng đầu
        for i in sorted(chi_so, key=lambda i: (-manh[i]["hash"], -manh[i]["khop"], manh[i]["align"], i)):
            c = next((c for c in cum if abs(manh[i]["align"] - manh[c[0]]["align"]) <= DUNG_SAI_ALIGN_S), None)
            if c is None:
                cum.append([i])
            else:
                c.append(i)
        giu: list = []                  # vị trí đặt đã giữ của khoá này, mạnh trước
        for c in sorted(cum, key=lambda c: (-sum(manh[i]["hash"] for i in c), c[0])):
            chinh = []
            for i in c:
                x = manh[i]
                trum = next((v for v in giu
                             if _phu(x, vi_tri[v].tu, vi_tri[v].den) >= TY_LE_PHU * x["khop"]), None)
                if trum is None:
                    chinh.append(i)
                    continue
                ty_so = x["hash"] / max(1, vi_tri[trum].hash_manh_nhat)
                nhan[i] = NhanManh(BONG if ty_so <= TY_LE_BONG else DOI_THU, trum, ty_so)
            if not chinh:
                continue
            vi_tri.append(ViTriDat(manh[chinh[0]]["align"], int(manh[chinh[0]]["hash"]),
                                   min(manh[i]["bat_dau"] for i in chinh),
                                   max(manh[i]["bat_dau"] + manh[i]["khop"] for i in chinh)))
            giu.append(len(vi_tri) - 1)
            for i in chinh:
                nhan[i] = NhanManh(CHINH, len(vi_tri) - 1)
    return nhan, vi_tri


def cung_vi_tri(a: dict, b: dict, troi_toi_da: float) -> bool:
    """Hai mảnh CÙNG vị trí đặt clip (cùng một lần dùng)?

    Độ lệch align phải giải thích được bằng mức trôi NHỎ HƠN ngưỡng bù tốc độ ``troi_toi_da``
    (``Config.toc_do_lech_toi_thieu``) qua khoảng cách tâm hai vùng, cộng ``LECH_ALIGN_GOC_S``; trần
    ``TRAN_LECH_CUNG_VI_TRI_S``. Trôi lớn hơn là việc của lượt bù tốc độ — gộp ở đây sẽ dẫm lên đường đó (bản C không
    chặn trôi đã đổi 2 golden bù tốc độ).
    """
    lech = abs(a["align"] - b["align"])
    if lech > TRAN_LECH_CUNG_VI_TRI_S:
        return False
    tam = abs((a["bat_dau"] + a["khop"] / 2) - (b["bat_dau"] + b["khop"] / 2))
    return lech <= LECH_ALIGN_GOC_S + troi_toi_da * tam


@dataclass
class _UngVienTam:
    """Đủ trường cho ``danh_gia_chap_nhan``; ``ty_le = 0`` nên chỉ bậc A (bằng chứng tuyệt đối) có thể nhận."""
    hashes: int
    matched_s: float
    ty_le: float = 0.0


def _dat_bac_a(so_lieu: tuple, cfg) -> bool:
    kq = danh_gia_chap_nhan(_UngVienTam(*so_lieu), cfg)
    return kq.chap_nhan and kq.bac == BAC_TUYET_DOI


def gop_cung_vi_tri(nhom: list, manh: list, nhan: list, cfg, so_lieu: Callable[[list], tuple]) -> tuple:
    """C': gộp các nhóm có mảnh chính cùng vị trí đặt thành một lần dùng. Trả ``(nhóm, số lần gộp)``.

    ``nhom``: các nhóm của ``_merge`` (khoá ``clip``, ``he_so``, ``manh``, ``cs`` = chỉ số trong ``manh``).
    ``so_lieu(cs)``: ``(hash đã áp cận trên, độ dài khớp)`` của nhóm gồm các mảnh ``cs`` — đúng số ``_merge`` báo.

    Chỉ gộp khi KHÔNG đổi kết luận chấp nhận: một nhóm đã đạt bậc A và nhóm gộp vẫn đạt bậc A. Hai phần cùng dưới
    ngưỡng không được cộng thành dương tính mới (đó là đổi chính sách nhận diện — chữ ký chính sách, Watch); phần dày
    không được gộp với phần thưa tới mức rớt rào mật độ. Thứ tự nhóm sau gộp giữ như trước (tất định, khớp mã cũ khi
    không có gì để gộp).
    """
    cache: dict = {}

    def sl(cs: list) -> tuple:
        khoa = tuple(cs)
        if khoa not in cache:
            cache[khoa] = so_lieu(cs)
        return cache[khoa]

    def chinh(g: dict) -> list:
        return [manh[i] for i in g["cs"] if nhan[i].loai == CHINH]

    theo_khoa: dict = {}
    for thu_tu, g in enumerate(nhom):
        theo_khoa.setdefault((g["clip"], g["he_so"]), []).append((thu_tu, g))
    ra: list = []                   # [thứ tự gốc, nhóm]
    so_lan = 0
    for ds in theo_khoa.values():
        if len(ds) == 1:            # clip chỉ có một nhóm: không có gì để gộp, khỏi tính số liệu
            ra.append(list(ds[0]))
            continue
        xong: list = []             # nhóm mạnh xét trước để làm đích gộp
        for thu_tu, g in sorted(ds, key=lambda t: (-sl(t[1]["cs"])[0], t[0])):
            dich = next((
                t for t in xong
                if any(cung_vi_tri(a, b, cfg.toc_do_lech_toi_thieu) for a in chinh(t[1]) for b in chinh(g))
                and (_dat_bac_a(sl(t[1]["cs"]), cfg) or _dat_bac_a(sl(g["cs"]), cfg))
                and _dat_bac_a(sl(t[1]["cs"] + g["cs"]), cfg)
            ), None)
            if dich is None:
                xong.append([thu_tu, g])
                continue
            dich[0] = min(dich[0], thu_tu)
            dich[1] = {**dich[1], "manh": dich[1]["manh"] + g["manh"], "cs": dich[1]["cs"] + g["cs"]}
            so_lan += 1
        ra.extend(xong)
    return [g for _, g in sorted(ra, key=lambda t: t[0])], so_lan


def chi_muc_canh_tranh(nhan: list) -> dict:
    """Vị trí đặt → chỉ số các mảnh bóng/đối thủ của nó. Dựng MỘT lần cho cả lượt gộp: ``bang_chung_moc`` gọi cho
    từng dòng, quét lại mọi mảnh mỗi lần thì tốn số dòng × số mảnh (video tổng hợp dài: hàng chục nghìn mảnh)."""
    ra: dict = {}
    for j, n in enumerate(nhan):
        if n.loai != CHINH:
            ra.setdefault(n.vi_tri, []).append(j)
    return ra


def bang_chung_moc(chi_so_moc: int, manh: list, nhan: list, canh_tranh: dict, vung_khop_s: float, end_s: float,
                   k: float) -> tuple:
    """Bằng chứng về MỐC của một dòng: ``(moc_mo_ho, moc_thay_the, ty_so_doi_thu)``.

    Chỉ xét vị trí đặt LÀM MỐC (vị trí của mảnh chính ``chi_so_moc`` được neo): mốc lấy từ đó, nên chỉ đối thủ của
    nó làm mốc không duy nhất; đối thủ của phần khác trong cùng dòng (bản cắt giữa) thì không. Bóng/đối thủ được tính
    khi vùng của nó nằm ≥ ``TY_LE_PHU`` trong vùng của dòng.

    * ``moc_mo_ho``: có đối thủ ngang ngửa (tỷ số > ``TY_LE_BONG``) — âm thanh lặp y hệt.
    * ``moc_thay_the``: mốc đầu clip mà các đối thủ đó cho (giây, làm tròn 0,1; tối đa ``SO_MOC_THAY_THE_TOI_DA``,
      mạnh trước; xếp tăng dần).
    * ``ty_so_doi_thu``: hash căn chỉnh cạnh tranh mạnh nhất (bóng hay đối thủ) / hash mảnh mạnh nhất của vị trí làm
      mốc; 0 = không có căn chỉnh nào cạnh tranh.
    """
    vt = nhan[chi_so_moc].vi_tri
    moc = round(max(0.0, manh[chi_so_moc]["bat_dau"] - k * manh[chi_so_moc]["t_clip"]), 1)
    ty_so, doi = 0.0, []
    for j in canh_tranh.get(vt, ()):
        n, x = nhan[j], manh[j]
        if _phu(x, vung_khop_s, end_s) < TY_LE_PHU * x["khop"]:
            continue
        ty_so = max(ty_so, n.ty_so)
        if n.loai == DOI_THU:
            doi.append((n.ty_so, round(max(0.0, x["bat_dau"] - k * x["t_clip"]), 1)))
    thay: list = []
    for _, t in sorted(doi, key=lambda d: (-d[0], d[1])):
        if abs(t - moc) > 0.05 and t not in thay:
            thay.append(t)
    return bool(doi), tuple(sorted(thay[:SO_MOC_THAY_THE_TOI_DA])), round(ty_so, 3)
