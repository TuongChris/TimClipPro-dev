# -*- coding: utf-8 -*-
"""Chống «bóng» của âm thanh lặp khi gộp mảnh khớp — phần thuần của ``Engine._merge`` (P0, 10/10/2026; P0-1/P0-3
sửa 25/10/2026).

VẤN ĐỀ (điều tra P0 trên 16 video tổng hợp, 21 lần dùng có ground truth)

Nhạc có nhịp trống đều, vòng hợp âm hay một đoạn lặp y hệt làm audfprint trả thêm những căn chỉnh của CÙNG clip
lệch bội số nửa ô nhịp so với căn chỉnh thật — gọi là «bóng». Bóng phủ cùng vùng video với căn chỉnh thật nhưng
yếu hơn hẳn (tỷ số hash ≤ 0,30, đa số 0,09–0,18). ``_merge`` trước đây:

* neo mốc đầu clip vào mảnh có vùng SỚM NHẤT của nhóm — một bóng 34 hash đủ kéo lệch mốc tới ±``dedup_s``;
* để nhóm toàn bóng thành ứng viên riêng ≥ 1.000 hash: «đạt chuẩn», dòng báo cáo thừa «Rất chắc chắn», làm phồng
  «Tổng số đoạn phát hiện».

Chỉ khi âm thanh lặp Y HỆT TỪNG MẪU thì nhiều mốc giải thích video như nhau (tỷ số ≈ 1): mốc mơ hồ thật.

NGUYÊN TẮC: một giây video chỉ có thể là MỘT vị trí trong clip gốc. Hai căn chỉnh khác nhau của cùng clip chỉ tranh
nhau ở chỗ CẢ HAI có bằng chứng; ở đó cái yếu kiểu bóng là bóng. Vùng video không có mảnh nào của một vị trí đặt thì
vị trí đó không giải thích được gì ở đó: một lần dùng thật KHÁC của cùng clip (phần khác của clip lấp vào lỗ, đoạn
chèn giữa hai mảnh rời, phát tiếp sau khi dừng) vẫn là lần dùng thật.

CÁCH LÀM — chỉ đổi MỐC và việc nhóm toàn bóng thành ứng viên. Mọi con số bằng chứng của nhóm thật giữ nguyên: gom
nhóm, tích phân hash, độ dài khớp, vùng khớp, cận trên vẫn tính trên ĐỦ mảnh như cũ. Xoá bóng trước khi gộp (bản
đầu của phương án) làm nhóm thật mất 0–1,1% hash và có thể rớt một ứng viên sát ngưỡng 1.000 — nên không xoá.

1. ``phan_loai_manh`` — với từng (clip, hệ số tốc độ): gom cụm căn chỉnh cùng vị trí đặt (lệch align ≤
   ``DUNG_SAI_ALIGN_S`` so với mảnh mạnh nhất của cụm), xét cụm theo TỔNG hash giảm dần. Mảnh bị một vị trí đặt đã
   giữ PHỦ (``_xet_phu``) là «bóng» (hash ≤ ``TY_LE_BONG`` × mảnh mạnh nhất của vị trí đó) hoặc «đối thủ» ngang ngửa
   (lớn hơn — âm thanh lặp y hệt); mảnh không bị phủ là mảnh «chính», tập mảnh chính của cụm thành một ``ViTriDat``.
   Phủ xét theo khoảng cách align tới vị trí (``cua_so_s`` = ``Config.dedup_s``, cửa sổ gom nhóm của ``_merge``):
   a. TRONG cửa sổ một lần xuất hiện (mã cũ luôn gộp hai căn chỉnh như thế thành một dòng): ≥ ``TY_LE_PHU`` độ dài
      mảnh nằm trong BAO [min, max] các mảnh chính của vị trí. Lỗ trong bao (căn chỉnh thật trôi tốc độ rất nhỏ vỡ
      thành nhiều mảnh — video B13; tiếng nói đè một đoạn) thuộc lần dùng ấy: bóng nằm trong lỗ không bị mảnh thật
      NÀO phủ quá nửa vẫn là bóng.
   b. NGOÀI cửa sổ (ứng viên một lần dùng khác — mã cũ cho dòng riêng): chỉ bị phủ ở chỗ vị trí THẬT SỰ có bằng
      chứng — ≥ ``TY_LE_PHU`` độ dài mảnh nằm trong hợp vùng các mảnh chính của vị trí; hoặc mảnh gối lên bằng chứng
      ấy, yếu kiểu bóng so với nó (mật độ ≤ ``TY_LE_BONG`` × mật độ của vị trí trên phần gối) và ≥ ``TY_LE_PHU`` nằm
      trong bao — bóng của vị trí thò vào lỗ (một mảnh là MỘT căn chỉnh: đã là bóng ở phần gối thì phần trong lỗ
      cũng là bóng). Mảnh chính của vị trí mà bản thân là bóng của mảnh đang xét (nằm ≥ ``TY_LE_PHU`` trong mảnh
      ấy, mật độ ≤ ``TY_LE_BONG`` × mật độ của nó) không được dùng để phủ: nó là điểm lưới bóng của căn chỉnh mạnh
      hơn lọt vào cụm (phát tiếp sau khi dừng — lưới bóng của lần 2 có một điểm rơi đúng align lần 1); khi mảnh đang
      xét thành chính, điểm ấy đổi nhãn thành bóng của vị trí mới và rút khỏi bằng chứng của vị trí cũ.
   Bản đầu (10/10) xét theo bao cho MỌI mảnh: một lần dùng thật khác nằm giữa hai mảnh rời của một vị trí yếu hơn
   bị gắn nhãn bóng/đối thủ, nhóm của nó bị bỏ, video thành âm tính mà Watch không quét lại (P0-1, audit 25/10).
2. ``neo_lai_nhom_bong`` (D) — nhóm (gom như cũ) không có mảnh «chính» nào là bằng chứng của clip ở vị trí đặt đã
   giải thích nó, nhưng không có mốc đúng. Vị trí ấy đã có nhóm chính tự đạt bậc A → nhóm bóng thừa (dòng «Rất chắc
   chắn» thừa của mã cũ), bỏ. Chưa có mà nhóm bóng TỰ đạt bậc A — mã cũ đã nhận video qua nó, mốc lệch — thì gộp nó
   vào các nhóm chính kề nó của vị trí đó (cùng chốt như C': nhóm gộp vẫn đạt bậc A): mốc từ mảnh chính, bằng chứng
   giữ (P0-3: căn chỉnh thật vỡ thành mảnh < 1.000 hash, chuỗi bóng bắc cầu qua các lỗ). Còn lại → bỏ như cũ.
3. Mốc đầu clip lấy từ mảnh «chính» sớm nhất — bóng và đối thủ không bao giờ làm mốc.
4. ``gop_cung_vi_tri`` (C') — các nhóm có mảnh chính CÙNG vị trí đặt là MỘT lần dùng → gộp, chỉ khi không đổi kết
   luận chấp nhận (một nhóm đã đạt bậc A và nhóm gộp vẫn đạt bậc A) và bằng chứng riêng của hai phần (các mảnh chính)
   có mật độ ngang nhau (không phần nào ≤ ``TY_LE_BONG`` × phần kia): một mảnh lẻ 18 hash cùng align cách vùng thật
   hàng trăm giây không được kéo giãn «Đoạn vi phạm» hay dời mốc (P0-2).
5. ``bang_chung_moc`` (B) — cờ mốc mơ hồ, các mốc thay thế, tỷ số đối thủ, xét trên vị trí đặt LÀM MỐC của dòng.
   Độ chắc chắn của NGUỒN (``Match.confidence``) không đổi.

HỆ QUẢ: tập ứng viên đạt chuẩn chỉ có thể MẤT nhóm toàn bóng mà vị trí thật của nó đã đạt chuẩn; nhóm toàn bóng tự
đạt chuẩn được neo lại (dòng mới trùm dòng cũ, mốc đúng); nhóm còn lại giữ nguyên số liệu, trừ nhóm do C'/D gộp (mà
một phần của nó đã đạt chuẩn). Không sinh dương tính mới ở mức video ⇒ âm tính cũ vẫn đúng, chữ ký chính sách
(``engine.chu_ky_chinh_sach``) giữ nguyên — các hằng số dưới đây vì vậy nằm ở module này, KHÔNG ở ``Config``; đổi
chúng là đổi chính sách nhận diện, cần quyết định riêng (docs/ai/DECISIONS.md).

Module thuần: không I/O.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import Callable

from chap_nhan_khop import BAC_TUYET_DOI, danh_gia_chap_nhan

DUNG_SAI_ALIGN_S = 0.5          # lệch align ≤ 0,5 s so với mảnh mạnh nhất của vị trí: cùng vị trí (khúc gối, trôi nhỏ)
TY_LE_PHU = 0.5                 # ≥ 50% độ dài mảnh nằm trong bao / bằng chứng của vị trí đặt mạnh hơn: bị phủ
TY_LE_BONG = 0.5                # ≤ 50% hash mảnh mạnh nhất của vị trí đó: bóng; > 50%: đối thủ ngang ngửa
LECH_ALIGN_GOC_S = 0.1          # C': phần lệch align không do trôi (khung 23 ms của audfprint, khúc gối)
TRAN_LECH_CUNG_VI_TRI_S = 1.0   # C': trần lệch align của hai mảnh cùng vị trí đặt
SO_MOC_THAY_THE_TOI_DA = 20
O_CHI_MUC_S = 60.0              # P0-4: ô thời gian video của chỉ mục bao vị trí đặt — chỉ đổi tốc độ, không đổi nhãn
TRAN_O_CHI_MUC = 100_000        # bao / mảnh trải quá chừng ấy ô (hay không hữu hạn): xét tuần tự như cũ

CHINH = "chinh"
BONG = "bong"
DOI_THU = "doi_thu"


@dataclass
class ViTriDat:
    """Một vị trí đặt clip trên video: cụm căn chỉnh cùng align, chỉ gồm mảnh «chính»."""
    align: float                # align của mảnh mạnh nhất (mảnh đầu tiên của vị trí)
    hash_manh_nhat: int
    cs: list = field(default_factory=list)   # chỉ số các mảnh chính — bằng chứng của vị trí, xếp theo bat_dau


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


def _mat_do(x: dict) -> float:
    """Hash trên mỗi giây của mảnh (``_merge`` đã lọc ``khop > 0``)."""
    return x["hash"] / x["khop"]


def _bao(manh: list, cs: list) -> tuple:
    """Bao [min, max] trên trục video của các mảnh ``cs``."""
    return (min(manh[j]["bat_dau"] for j in cs), max(manh[j]["bat_dau"] + manh[j]["khop"] for j in cs))


def _bang_chung_tren(manh: list, cs: list, tu: float, den: float) -> tuple:
    """``(độ dài, hash)`` bằng chứng của các mảnh ``cs`` trong [tu, den]: hợp vùng, mỗi đoạn lấy mật độ tốt nhất
    (cùng cách tích phân với ``_merge``), nên hai mảnh gối nhau không bị đếm đôi."""
    ds = [manh[j] for j in cs]
    bien = sorted({tu, den, *(m for x in ds for m in (x["bat_dau"], x["bat_dau"] + x["khop"]) if tu < m < den)})
    dai = h = 0.0
    for a, b in zip(bien, bien[1:]):
        phu = [_mat_do(x) for x in ds if x["bat_dau"] <= a and b <= x["bat_dau"] + x["khop"]]
        if phu:
            dai += b - a
            h += (b - a) * max(phu)
    return dai, h


def _xet_phu(x: dict, manh: list, vt: ViTriDat, cua_so_s: float) -> tuple:
    """Vị trí đặt ``vt`` có PHỦ mảnh ``x`` không — ``(phu, bong_cua_x)``; quy tắc 1a/1b của module.

    Trong cửa sổ một lần xuất hiện (lệch align ≤ ``cua_so_s``): bao của vị trí. Ngoài cửa sổ: bằng chứng cục bộ —
    ``bong_cua_x`` là các mảnh chính của ``vt`` mà bản thân là bóng của ``x`` (nằm ≥ ``TY_LE_PHU`` trong ``x``, mật độ
    ≤ ``TY_LE_BONG`` × mật độ ``x``), không được dùng để phủ; phủ = ≥ ``TY_LE_PHU`` độ dài ``x`` gối lên các mảnh còn
    lại, hoặc ``x`` gối lên chúng, yếu kiểu bóng so với bằng chứng trên phần gối và ≥ ``TY_LE_PHU`` nằm trong bao.
    """
    if not vt.cs:
        return False, []
    du = TY_LE_PHU * x["khop"]
    if abs(x["align"] - vt.align) <= cua_so_s:
        return _phu(x, *_bao(manh, vt.cs)) >= du, []
    x0, x1 = x["bat_dau"], x["bat_dau"] + x["khop"]
    mat_do_x = _mat_do(x)
    bong_cua_x = [j for j in vt.cs
                  if _phu(manh[j], x0, x1) >= TY_LE_PHU * manh[j]["khop"] and _mat_do(manh[j]) <= TY_LE_BONG * mat_do_x]
    con = [j for j in vt.cs if j not in bong_cua_x]
    dai, h = _bang_chung_tren(manh, [j for j in con if _phu(manh[j], x0, x1) > 0], x0, x1)
    if dai >= du:
        return True, bong_cua_x
    if dai > 0 and mat_do_x <= TY_LE_BONG * (h / dai) and _phu(x, *_bao(manh, con)) >= du:
        return True, bong_cua_x
    return False, bong_cua_x


def _dat_vi_tri(vt: ViTriDat, manh: list) -> None:
    """Xếp mảnh chính theo ``bat_dau`` và tính lại mảnh mạnh nhất (sau khi thêm/rút mảnh)."""
    vt.cs.sort(key=lambda j: (manh[j]["bat_dau"], j))
    if vt.cs:
        vt.hash_manh_nhat = max(int(manh[j]["hash"]) for j in vt.cs)


def _cac_o(tu: float, den: float):
    """Các ô ``O_CHI_MUC_S`` mà đoạn video [tu, den] chạm; ``None`` khi không hữu hạn hoặc quá ``TRAN_O_CHI_MUC`` ô."""
    if not (math.isfinite(tu) and math.isfinite(den)):
        return None
    dau, cuoi = math.floor(tu / O_CHI_MUC_S), math.floor(den / O_CHI_MUC_S)
    return range(dau, cuoi + 1) if cuoi - dau < TRAN_O_CHI_MUC else None


def _cac_o_vi_tri(vt: ViTriDat, manh: list):
    """Ô của BAO vị trí ``vt`` lúc tạo — ``None``: luôn xét vị trí này.

    Ngoài bao, ``_xet_phu`` luôn trả ``(False, [])`` với mảnh có ``khop > 0``: mọi nhánh «phủ» và «bóng của x» đều
    cần một phần dương gối lên vùng mảnh. Bao chỉ CO lại (mảnh chính bị rút khi đổi nhãn), nên bao lúc tạo là tập
    trùm an toàn. Vị trí có mảnh ``khop <= 0`` (``_merge`` đã lọc; gọi trực tiếp thì có thể) không có tính chất ấy."""
    if not vt.cs or any(not manh[j]["khop"] > 0 for j in vt.cs):
        return None
    return _cac_o(*_bao(manh, vt.cs))


def _nhan_bi_phu(x: dict, vt: int, vi_tri: list) -> NhanManh:
    ty_so = x["hash"] / max(1, vi_tri[vt].hash_manh_nhat)
    return NhanManh(BONG if ty_so <= TY_LE_BONG else DOI_THU, vt, ty_so)


def phan_loai_manh(manh: list, cua_so_s: float) -> tuple:
    """Nhãn của TỪNG mảnh (cùng thứ tự ``manh``) và danh sách vị trí đặt: ``(list[NhanManh], list[ViTriDat])``.

    ``cua_so_s``: cửa sổ align của MỘT lần xuất hiện (``Config.dedup_s``, cửa sổ gom nhóm của ``_merge``).

    Hai bước, cho từng (clip, hệ số tốc độ) — mảnh của hai clip khác nhau, hay hai hệ số tốc độ khác nhau (không
    cùng trục khúc), không bao giờ xét nhau:

    1. Gom mảnh thành cụm theo vị trí đặt: lệch align ≤ ``DUNG_SAI_ALIGN_S`` so với mảnh mạnh nhất của cụm.
    2. Xét cụm theo TỔNG hash giảm dần. Mảnh bị một vị trí đã giữ phủ (``_xet_phu``: bao trong cửa sổ một lần xuất
       hiện, bằng chứng cục bộ ngoài cửa sổ) là bóng/đối thủ của vị trí đó; phần còn lại của cụm là mảnh chính, thành
       một vị trí đặt mới. Mảnh chính của vị trí cũ mà là bóng của một mảnh chính mới đổi nhãn và rút khỏi bằng
       chứng của vị trí cũ.

    Phải gom cụm TRƯỚC rồi mới xét: xét từng mảnh theo hash thì một đối thủ mạnh hơn các mảnh YẾU của vị trí thật
    được xét trước khi bằng chứng của vị trí thật kịp có mặt ở chỗ nó, và thành một vị trí riêng. Thứ tự xét tất định.

    Chi phí (P0-4, audit 25/10): clip ngắn lặp suốt video dài cho hàng nghìn mảnh và cụm của MỘT khoá, ``_merge`` chạy
    lại sau mỗi đoạn quét tăng dần. Tìm cụm qua đầu cụm xếp theo align (``bisect``), và mỗi mảnh chỉ ``_xet_phu`` các
    vị trí có bao chạm ô thời gian của nó (``_cac_o_vi_tri``) — vẫn theo thứ tự ``giu``, nên nhãn y hệt cách duyệt
    tuần tự; quét tuần tự mọi cụm / mọi vị trí là bậc hai theo số mảnh.
    """
    nhan: list = [None] * len(manh)
    vi_tri: list = []
    theo_khoa: dict = {}
    for i, x in enumerate(manh):
        theo_khoa.setdefault((x["clip"], he_so(x)), []).append(i)
    for chi_so in theo_khoa.values():
        cum: list = []                  # mỗi cụm: chỉ số mảnh, mảnh mạnh nhất đứng đầu
        dau_cum: list = []              # (align đầu cụm, số thứ tự cụm), xếp theo align — chỉ align hữu hạn
        for i in sorted(chi_so, key=lambda i: (-manh[i]["hash"], -manh[i]["khop"], manh[i]["align"], i)):
            a = manh[i]["align"]
            c = None
            if math.isfinite(a):        # align không hữu hạn không bao giờ lệch ≤ dung sai với align nào
                # Cụm TẠO SỚM NHẤT có đầu cụm lệch ≤ dung sai (như duyệt tuần tự); xét rộng gấp đôi dung sai rồi lọc
                # bằng đúng phép so cũ, để làm tròn số thực không đổi kết quả.
                k = bisect.bisect_left(dau_cum, (a - 2 * DUNG_SAI_ALIGN_S,))
                while k < len(dau_cum) and dau_cum[k][0] <= a + 2 * DUNG_SAI_ALIGN_S:
                    if abs(a - dau_cum[k][0]) <= DUNG_SAI_ALIGN_S and (c is None or dau_cum[k][1] < c):
                        c = dau_cum[k][1]
                    k += 1
            if c is None:
                if math.isfinite(a):
                    bisect.insort(dau_cum, (a, len(cum)))
                cum.append([i])
            else:
                cum[c].append(i)
        giu: list = []                  # vị trí đặt đã giữ của khoá này, mạnh trước
        o_giu: dict = {}                # ô thời gian video → vị trí đã giữ có bao (lúc tạo) chạm ô ấy
        luon_xet: list = []             # vị trí không đưa được vào ô: luôn xét
        for c in sorted(cum, key=lambda c: (-sum(manh[i]["hash"] for i in c), c[0])):
            chinh: list = []
            doi_nhan: dict = {}         # mảnh chính của vị trí cũ là bóng của mảnh chính mới: chỉ số → vị trí cũ
            for i in c:
                x = manh[i]
                trum, loai_tru = None, []
                o = _cac_o(x["bat_dau"], x["bat_dau"] + x["khop"]) if x["khop"] > 0 else None
                xet = giu if o is None else sorted({v for k in o for v in o_giu.get(k, ())}.union(luon_xet))
                for v in xet:           # cùng thứ tự với giu: vị trí phủ đầu tiên không đổi
                    phu, bong_cua_x = _xet_phu(x, manh, vi_tri[v], cua_so_s)
                    if phu:
                        trum = v
                        break
                    loai_tru.extend((j, v) for j in bong_cua_x)
                if trum is None:
                    chinh.append(i)
                    doi_nhan.update(loai_tru)
                else:
                    nhan[i] = _nhan_bi_phu(x, trum, vi_tri)
            if not chinh:
                continue
            moi = len(vi_tri)
            vi_tri.append(ViTriDat(manh[chinh[0]]["align"], 0, list(chinh)))
            _dat_vi_tri(vi_tri[moi], manh)
            giu.append(moi)
            o_moi = _cac_o_vi_tri(vi_tri[moi], manh)
            if o_moi is None:
                luon_xet.append(moi)
            else:
                for k in o_moi:
                    o_giu.setdefault(k, []).append(moi)
            for i in chinh:
                nhan[i] = NhanManh(CHINH, moi)
            for j, v in doi_nhan.items():
                if nhan[j].loai == CHINH and j in vi_tri[v].cs:
                    vi_tri[v].cs.remove(j)
                    _dat_vi_tri(vi_tri[v], manh)
                    nhan[j] = _nhan_bi_phu(manh[j], moi, vi_tri)
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


def _ngang_bang(a: tuple, b: tuple) -> bool:
    """Hai phần có mật độ bằng chứng ngang nhau: không phần nào yếu kiểu bóng (≤ ``TY_LE_BONG``) so với phần kia."""
    da = a[0] / a[1] if a[1] > 0 else 0.0
    db = b[0] / b[1] if b[1] > 0 else 0.0
    return min(da, db) > TY_LE_BONG * max(da, db)


def _co_chinh(g: dict, nhan: list) -> bool:
    return any(nhan[i].loai == CHINH for i in g["cs"])


def _khe_nhom(a: dict, b: dict) -> float:
    """Khoảng trống nhỏ nhất (giây) giữa vùng video của hai nhóm; 0 khi chạm/chồng nhau."""
    return min(max(0.0, max(x["bat_dau"], y["bat_dau"]) - min(x["bat_dau"] + x["khop"], y["bat_dau"] + y["khop"]))
               for x in a["manh"] for y in b["manh"])


def _gop_nhom(a: dict, b: dict) -> dict:
    return {**a, "manh": a["manh"] + b["manh"], "cs": a["cs"] + b["cs"]}


def _bo_nho(so_lieu: Callable[[list], tuple]) -> Callable[[list], tuple]:
    cache: dict = {}

    def sl(cs: list) -> tuple:
        khoa = tuple(cs)
        if khoa not in cache:
            cache[khoa] = so_lieu(cs)
        return cache[khoa]
    return sl


def neo_lai_nhom_bong(nhom: list, manh: list, nhan: list, cfg, so_lieu: Callable[[list], tuple]) -> tuple:
    """D: xử lý nhóm KHÔNG có mảnh chính nào (toàn bóng/đối thủ). Trả ``(nhóm còn lại, số nhóm bỏ, số nhóm neo lại)``.

    ``nhom``: các nhóm của ``_merge`` (khoá ``clip``, ``he_so``, ``manh``, ``cs`` = chỉ số trong ``manh``);
    ``so_lieu(cs)``: ``(hash đã áp cận trên, độ dài khớp)`` của nhóm gồm các mảnh ``cs`` — đúng số ``_merge`` báo.

    Nhóm như thế là bằng chứng của clip ở vị trí đặt đã giải thích nó (bóng là âm thanh của chính clip khớp lệch nhịp)
    nhưng không có mốc đúng. Vị trí xét = vị trí phủ nhiều hash nhất của nhóm.

    * Vị trí đó đã có nhóm chính tự đạt bậc A → nhóm bóng thừa (dòng «Rất chắc chắn» thừa của mã cũ): bỏ, số liệu
      nhóm chính giữ nguyên.
    * Chưa có, và nhóm bóng TỰ đạt bậc A — mã cũ đã nhận video qua chính nhóm này (mốc lệch) → gộp nó với các nhóm
      chính của vị trí đó cách nó ≤ ``dedup_s`` (không có thì nhóm gần nhất), nếu nhóm gộp vẫn đạt bậc A (cùng chốt
      với C'): mốc lấy từ mảnh chính, bằng chứng giữ. Video đã dương tính ở mã cũ nên không có dương tính mới; dòng mới
      trùm vùng dòng cũ. Bỏ nhóm này mà không neo lại biến một dương tính cũ thành âm tính quét trọn, Watch không bao
      giờ quét lại (P0-3).
    * Còn lại (bóng dưới chuẩn) → bỏ như cũ.
    """
    sl = _bo_nho(so_lieu)
    ra: list = [[t, g] for t, g in enumerate(nhom) if _co_chinh(g, nhan)]      # [thứ tự gốc, nhóm]
    so_bo = so_neo = 0
    for t, g in enumerate(nhom):
        if _co_chinh(g, nhan):
            continue
        theo_vt: dict = {}
        for i in g["cs"]:
            theo_vt[nhan[i].vi_tri] = theo_vt.get(nhan[i].vi_tri, 0) + manh[i]["hash"]
        vt = max(theo_vt, key=lambda v: (theo_vt[v], -v))
        cua_vt = [r for r in ra if any(nhan[i].loai == CHINH and nhan[i].vi_tri == vt for i in r[1]["cs"])]
        if not cua_vt or any(_dat_bac_a(sl(r[1]["cs"]), cfg) for r in cua_vt) or not _dat_bac_a(sl(g["cs"]), cfg):
            so_bo += 1
            continue
        ke = ([r for r in cua_vt if _khe_nhom(r[1], g) <= cfg.dedup_s]
              or [min(cua_vt, key=lambda r: (_khe_nhom(r[1], g), r[0]))])
        gop = g
        for r in ke:
            gop = _gop_nhom(r[1], gop)
        if not _dat_bac_a(sl(gop["cs"]), cfg):
            so_bo += 1
            continue
        for r in ke[1:]:
            ra.remove(r)
        ke[0][0] = min(t, *(r[0] for r in ke))
        ke[0][1] = gop
        so_neo += 1
    return [g for _, g in sorted(ra, key=lambda r: r[0])], so_bo, so_neo


def gop_cung_vi_tri(nhom: list, manh: list, nhan: list, cfg, so_lieu: Callable[[list], tuple]) -> tuple:
    """C': gộp các nhóm có mảnh chính cùng vị trí đặt thành một lần dùng. Trả ``(nhóm, số lần gộp)``.

    ``nhom``: các nhóm của ``_merge`` (khoá ``clip``, ``he_so``, ``manh``, ``cs`` = chỉ số trong ``manh``).
    ``so_lieu(cs)``: ``(hash đã áp cận trên, độ dài khớp)`` của nhóm gồm các mảnh ``cs`` — đúng số ``_merge`` báo.

    Chỉ gộp khi KHÔNG đổi kết luận chấp nhận: một nhóm đã đạt bậc A và nhóm gộp vẫn đạt bậc A. Hai phần cùng dưới
    ngưỡng không được cộng thành dương tính mới (đó là đổi chính sách nhận diện — chữ ký chính sách, Watch); phần dày
    không được gộp với phần thưa tới mức rớt rào mật độ. Và chỉ gộp hai phần mà bằng chứng RIÊNG (các mảnh chính, không
    tính bóng gom kèm) có mật độ ngang nhau (``_ngang_bang``): C' dành cho phần tiếp nối tự có bằng chứng (bị tiếng nói
    che một đoạn); một mảnh lẻ yếu kiểu bóng cùng align không được kéo giãn vùng khớp hay dời mốc của dòng đạt chuẩn
    (P0-2). Thứ tự nhóm sau gộp giữ như trước (tất định, khớp mã cũ khi không có gì để gộp).
    """
    sl = _bo_nho(so_lieu)

    def cs_chinh(g: dict) -> list:
        return [i for i in g["cs"] if nhan[i].loai == CHINH]

    def chinh(g: dict) -> list:
        return [manh[i] for i in cs_chinh(g)]

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
                and _ngang_bang(sl(cs_chinh(t[1])), sl(cs_chinh(g)))
                and _dat_bac_a(sl(t[1]["cs"] + g["cs"]), cfg)
            ), None)
            if dich is None:
                xong.append([thu_tu, g])
                continue
            dich[0] = min(dich[0], thu_tu)
            dich[1] = _gop_nhom(dich[1], g)
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
