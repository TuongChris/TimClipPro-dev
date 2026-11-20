# -*- coding: utf-8 -*-
"""P-8 — thuật toán «tinh chỉnh mốc từng giây» (tinh_chinh_moc.py) trên audio TỔNG HỢP có sự thật biết trước.

Ống nối trong engine có test riêng (test_tinh_chinh_engine.py). Ở đây: mép tới ~0,1 s, đoạn/chỗ cắt/tua lùi, và các
lỗi của bản nghiên cứu «Cách C» mà phản biện bắt được — mỗi lỗi một test sẽ ĐỎ với hành vi cũ:
  H3  nhạc đè chỉ một phần clip → bản cũ bịa chỗ cắt (ngưỡng neo vào trung vị lõi engine);
  H1b tua lùi < 20 s, engine gộp một dòng hai neo → bản cũ chỉ đo một neo, mất phần phát lại;
  H4  bỏ 0,6 s đầu clip → bản cũ chốt mép về đầu clip (báo 0).
Và hai lỗi bộ kiểm NGOÀI MẪU vòng 1 bắt được (mẫu tái hiện bằng audio tổng hợp, không chép audio của bộ kiểm):
  A05 im lặng tuyệt đối giữa đoạn → miếng phương sai 0 cho «giống» vô nghĩa, luật nối 5 ô nối qua khoảng lặng;
  A03 giọng nói đè 0 dB một phần ba giữa → khe dài cùng neo để hở, «chưa tinh chỉnh» dù clip vẫn ở dưới lớp đè; và
      khi đã nối, mép cuối lấn 0,175 s sang một nốt nền cùng dải mel với nốt clip đang ngân.
Và các lỗi phản biện vòng 2 bắt được (mục «vòng 3» cuối file, mẫu tái hiện bằng audio tổng hợp nhỏ): FFmpeg lặp vô hạn
(AAC, cuối file), mẫu đầu AAC trễ một khung, câu lỗi tiếng Anh; neo trôi hội tụ thành «lặp y hệt» giả; kiểm huỷ thưa và
không từ chối sớm ở lõi dài; nhảy nhỏ trong một neo thành k giả; khe giữa hai neo luôn tính là chỗ cắt (tiếng đè quanh
chỗ tua lùi → chỗ cắt bịa); mép «thô» dưới tiếng đè vẫn ĐÃ; thay 3–6 s bị nối qua; DJ lặp ô nhịp bị nối qua; im lặng
dài của chính clip; khoảng lặng bịa ở clip chèn nhỏ; và các vị từ chưa test nào khoá (đột biến sống).
Và review trước khi gộp (mục «vòng 4» cuối file): đổi tần số mẫu giữa file .ts làm lệch phần sau; bấm Dừng khi FFmpeg im
lặng phải chờ tới 2 phút; câu lỗi FFmpeg tiếng Anh kèm đường dẫn; mép bám vào một chỗ vấp ngắn sát mép; mép ngoài sát
giới hạn đo không kiểm được phía ngoài mà không cờ; lý do «file ngắn hơn dự kiến» cho clip ngắn.
Và kiểm độc lập sau vòng 4 (mục «vòng 5» cuối file): video có tiếng bắt đầu sau hình làm mọi mốc sớm đúng độ trễ; ô kiểm
phía ngoài mép không đo được bị coi là «clip vắng»; nhảy nhỏ trong lần dùng ngắn thành một đoạn ánh xạ lệch; luồng canh
FFmpeg tính cả thời gian nơi gọi xử lý khối; và hai vị từ chưa test nào khoá (đột biến sống).
Phần lớn test đọc audio qua ``doc_pcm`` giả (mảng trong bộ nhớ, 11025 Hz) cho nhanh; vài test đi qua FFmpeg thật.
"""
import json
import shutil
import subprocess
import sys
import threading
import time

import numpy as np
import pytest

import tinh_chinh_moc as tcm
from am_thanh_lap import O_NHIP, doi_toc_do, nhac_co_nhip, vong_lap_y_het
from conftest import _ghi_wav, _giai_dieu

SR = tcm.SR
co_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg trong PATH")


def _am(dai_s: float, seed: int) -> np.ndarray:
    return _giai_dieu(dai_s, seed=seed, sr=SR).astype(np.float32)


def _chen(nen: np.ndarray, doan: np.ndarray, P: float) -> np.ndarray:
    ra = nen.copy()
    ra[int(round(P * SR)): int(round(P * SR)) + len(doan)] = doan
    return ra


def _cat(x: np.ndarray, tu: float, den: float) -> np.ndarray:
    return x[int(round(tu * SR)): int(round(den * SR))]


def _doc_gia(tin_hieu: dict, goi: list | None = None):
    """``doc_pcm`` giả: phục vụ mảng float32 11025 Hz theo tên file, ghi lại (tên, từ, dài) của từng lời gọi."""
    def doc(duong, tu_s, dai_s):
        if goi is not None:
            goi.append((duong, tu_s, dai_s))
        i0 = int(round(tu_s * SR))
        return tin_hieu[duong][i0: i0 + int(round(dai_s * SR))], i0 / SR
    return doc


def _chay(clip, video, neo, vung, end, **kw):
    return tcm.tinh_chinh_dong("clip", "video", neo, vung, end, doc_pcm=_doc_gia({"clip": clip, "video": video}), **kw)


def _gan(a: float, b: float, sai: float = 0.1) -> bool:
    return abs(a - b) <= sai


def _kieu_thuan(x) -> None:
    if isinstance(x, dict):
        for v in x.values():
            _kieu_thuan(v)
    elif isinstance(x, list):
        for v in x:
            _kieu_thuan(v)
    else:
        assert type(x) in (str, int, float, bool), (type(x), x)


def _khop_doan(d: dict, video_tu, video_den, clip_tu, clip_den, sai: float = 0.1) -> None:
    thay = [d["video_tu"], d["video_den"], d["clip_tu"], d["clip_den"]]
    assert all(_gan(x, y, sai) for x, y in zip(thay, [video_tu, video_den, clip_tu, clip_den])), \
        (thay, [video_tu, video_den, clip_tu, clip_den])


# ---------------------------------------------------------------------------------------------- đúng chỗ

@co_ffmpeg
def test_chen_tron_clip_sach_mep_toi_0_1_s_va_ket_qua_json_tat_dinh(tmp_path):
    clip, P = _giai_dieu(60, seed=7101), 40.37
    video = _giai_dieu(150, seed=7102)
    video[int(P * 22050): int(P * 22050) + len(clip)] = clip
    _ghi_wav(tmp_path / "clip.wav", clip)
    _ghi_wav(tmp_path / "video.wav", video)
    goi = (str(tmp_path / "clip.wav"), str(tmp_path / "video.wav"), [(P + 0.08, 1.0)], P + 3.1, P + 57.2)
    kq = tcm.tinh_chinh_dong(*goi, pham_vi_s=(0.0, 150.0))
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert len(kq["doan"]) == 1 and kq["cho_cat"] == [] and not kq["cham_gioi_han"]
    assert kq["cham_dau"] is False and kq["cham_cuoi"] is False
    _khop_doan(kq["doan"][0], P, P + 60, 0, 60)
    assert kq["doan"][0]["cach_tim_mep"] == ["dau_clip", "cuoi_clip"]
    assert kq["doan"][0]["tuong_dong_min"] > 90 and kq["nguong_pct"] < 60
    assert all(P - 1 <= t <= P + 61 for t, _ in kq["ho_so"]) and len(kq["ho_so"]) >= 58
    # JSON khứ hồi y hệt, chỉ kiểu Python thuần (không numpy), và cùng đầu vào → cùng kết quả (trừ thời gian chạy)
    assert json.loads(json.dumps(kq)) == kq
    _kieu_thuan(kq)
    lai = tcm.tinh_chinh_dong(*goi, pham_vi_s=(0.0, 150.0))
    assert {k: v for k, v in lai.items() if k != "thoi_gian_s"} == {k: v for k, v in kq.items() if k != "thoi_gian_s"}


def test_dung_mot_phan_clip_bao_dung_cho_khong_phai_moc_ao():
    clip = _am(120, 7201)
    c_tu, c_den, P = 30.37, 90.81, 50.53
    video = _chen(_am(160, 7202), _cat(clip, c_tu, c_den), P)
    kq = _chay(clip, video, [(P - c_tu, 1.0)], P + 3.0, P + 57.4)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    _khop_doan(d, P, P + c_den - c_tu, c_tu, c_den)
    assert d["cach_tim_mep"] == ["bac_thang", "bac_thang"]


def test_cat_giua_chen_doan_khac_ra_hai_doan_va_cho_cat():
    clip = _am(120, 7301)
    chen = np.concatenate([_cat(clip, 0, 50), _am(4, 7303), _cat(clip, 60, 120)])
    video = _chen(_am(180, 7302), chen, 30.0)
    kq = _chay(clip, video, [(30.0, 1.0), (24.0, 1.0)], 33.0, 141.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert len(kq["doan"]) == 2
    _khop_doan(kq["doan"][0], 30, 80, 0, 50, 0.2)
    _khop_doan(kq["doan"][1], 84, 144, 60, 120, 0.2)
    (c,) = kq["cho_cat"]
    assert _gan(c["video_tu"], 80, 0.2) and _gan(c["video_den"], 84, 0.2)
    assert _gan(c["clip_bo_tu"], 50, 0.2) and _gan(c["clip_bo_den"], 60, 0.2)


@pytest.mark.parametrize("lech_k", [0.0, 0.004], ids=["k_engine_dung", "k_engine_lech_0.4pct"])
def test_video_nhanh_2_phan_tram_k_tu_neo(lech_k):
    clip = _am(90, 7401)
    c_tu, c_den, P, toc = 12.37, 71.81, 33.13, 1.02
    video = _chen(_am(150, 7402), doi_toc_do(_cat(clip, c_tu, c_den), 1.0 / toc).astype(np.float32), P)
    k = (1.0 / toc) * (1.0 + lech_k)
    tam = (c_tu + c_den) / 2                     # neo engine đúng ở giữa đoạn, trôi dần ra hai đầu khi k lệch
    dau = P + (tam - c_tu) / toc - k * tam
    kq = _chay(clip, video, [(dau, k)], P + 3.0, P + 55.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    _khop_doan(d, P, P + (c_den - c_tu) / toc, c_tu, c_den)
    assert abs(d["k"] - 1.0 / toc) < 0.003


# ---------------------------------------------------------------------------------------------- nhạc đè, giọng nói đè

def _giong_noi(dai_s: float, seed: int, sr: int = SR) -> np.ndarray:
    """Âm GIỐNG giọng nói: ồn dải 300–3400 Hz phủ gần hết các dải mel, điều chế âm tiết 3–5 Hz theo câu 1,5–4 s, ngắt
    hơi 0,2–0,7 s giữa câu, mỗi âm tiết một độ to."""
    rng = np.random.default_rng(seed)
    n = int(dai_s * sr)
    pho = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / sr)
    pho[(f < 300) | (f > 3400)] = 0
    bao, t = np.zeros(n), 0.0
    while t < dai_s:
        cau, toc = rng.uniform(1.5, 4.0), rng.uniform(3.0, 5.0)
        i0, i1 = int(t * sr), min(int((t + cau) * sr), n)
        pha = np.arange(i1 - i0) / sr * toc
        bao[i0:i1] = np.sin(np.pi * pha) ** 2 * rng.uniform(0.4, 1.0, int(pha[-1]) + 1)[pha.astype(int)]
        t += cau + rng.uniform(0.2, 0.7)
    return np.fft.irfft(pho, n) * bao


def _de(video: np.ndarray, doan_tu: float, doan_den: float, snr_db: float, seed: int, chi_vung=None,
        nguon=nhac_co_nhip) -> np.ndarray:
    """Cộng tiếng đè (mặc định nhạc có nhịp), mức sao cho SNR (RMS đoạn clip / RMS tiếng đè) = snr_db trong
    [doan_tu, doan_den]."""
    de = nguon(len(video) / SR + 1.0, seed=seed, sr=SR)[: len(video)]
    if chi_vung is not None:
        mat_na = np.zeros(len(video))
        mat_na[int(chi_vung[0] * SR): int(chi_vung[1] * SR)] = 1.0
        de = de * mat_na
    v = slice(int(doan_tu * SR), int(doan_den * SR))
    tham_chieu = slice(int(chi_vung[0] * SR), int(chi_vung[1] * SR)) if chi_vung is not None else v
    de = de * (np.sqrt(np.mean(video[v] ** 2) / np.mean(de[tham_chieu] ** 2)) * 10 ** (-snr_db / 20))
    tron = video + de
    return (tron * (0.95 / np.abs(tron).max())).astype(np.float32)


def test_nhac_de_0_dB_suot_doan_van_tinh_duoc():
    clip, P = _am(90, 7501), 30.0
    video = _de(_chen(_am(150, 7502), clip, P), P, P + 90, 0.0, 7503)
    kq = _chay(clip, video, [(P, 1.0)], P + 4.5, P + 84.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    _khop_doan(d, P, P + 90, 0, 90, 0.15)
    assert 35 < d["tuong_dong_tb"] < 80                  # % giống thấp vì nhạc đè, nhưng vẫn trên ngưỡng tại chỗ


def test_nhac_de_mot_phan_clip_khong_bia_cho_cat():
    """H3: nhạc đè 0 dB CHỈ trên giây clip 40–80. Bản cũ lấy ngưỡng = (trung vị lõi ≈ 99 % + nền)/2 ≈ 60 % nên phần
    bị đè (~50 %) rơi xuống dưới ngưỡng → bịa «chỗ cắt» 40 s. Ngưỡng mới theo đường nền: một đoạn liền."""
    clip, P = _am(120, 7601), 30.0
    video = _de(_chen(_am(180, 7602), clip, P), P + 40, P + 80, 0.0, 7603, chi_vung=(P + 40, P + 80))
    kq = _chay(clip, video, [(P, 1.0)], P + 6.0, P + 114.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert kq["cho_cat"] == [] and len(kq["doan"]) == 1
    _khop_doan(kq["doan"][0], P, P + 120, 0, 120)
    bi_de = [p for t, p in kq["ho_so"] if P + 42 <= t <= P + 78]
    sach = [p for t, p in kq["ho_so"] if P + 2 <= t <= P + 38]
    assert np.median(bi_de) < 60 < np.median(sach)       # đúng tình huống làm bản cũ hỏng
    assert min(bi_de) > kq["nguong_pct"]


def test_giong_noi_de_0_dB_mot_phan_ba_giua_van_mot_doan():
    """A03: âm giống giọng nói đè 0 dB một phần ba giữa đoạn. Giọng phủ gần hết các dải nên % giống 3 s chỉ hơn nền
    ~10 điểm, phần lớn ô dưới ngưỡng (nền + 15). Bản cũ để hở cả khe ~60 s giữa hai phần sạch cùng neo → lưới an toàn
    trả «chưa tinh chỉnh». Clip vẫn ở dưới lớp đè: khe dài mà ≥ 3/4 số ô vẫn cao hơn p99 nền thì nối."""
    clip, P = _am(180, 9301), 40.0
    video = _de(_chen(_am(260, 9302), clip, P), P + 60, P + 120, 0.0, 9303, chi_vung=(P + 60, P + 120),
                nguon=_giong_noi)
    kq = _chay(clip, video, [(P, 1.0)], P + 9.0, P + 171.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert kq["cho_cat"] == [] and len(kq["doan"]) == 1
    _khop_doan(kq["doan"][0], P, P + 180, 0, 180)
    bi_de = [p for t, p in kq["ho_so"] if P + 62 <= t <= P + 118]
    assert np.mean(np.array(bi_de) >= kq["nguong_pct"]) < 0.5         # đúng tình huống làm bản cũ hỏng


def test_khe_dai_cung_neo_bi_thay_am_khac_khong_noi_qua():
    """Đối chứng của luật nối khe dài: 20 s tiếng clip bị THAY bằng âm khác (trục clip vẫn chạy, cùng neo). Các ô của
    khe giống như nền → không nối; không phân biệt được «thay» với «đè quá to» nên đúng là chưa tinh chỉnh, hoặc hai
    đoạn đúng — không bao giờ một đoạn phủ qua khe."""
    clip, P = _am(120, 9501), 40.0
    video = _chen(_chen(_am(220, 9502), clip, P), _am(20, 9503), P + 50)
    kq = _chay(clip, video, [(P, 1.0)], P + 6.0, P + 114.0)
    if kq["trang_thai"] == tcm.DA:
        assert len(kq["doan"]) == 2, kq["doan"]
        _khop_doan(kq["doan"][0], P, P + 50, 0, 50)
        _khop_doan(kq["doan"][1], P + 70, P + 120, 70, 120)
    else:
        assert kq["ly_do"]


def test_nen_nhac_co_nhip_cung_nhip_khong_noi_dai_doan():
    """X3: clip nhạc có nhịp chèn vào nền cũng là nhạc có nhịp 113 BPM, khớp ô nhịp với clip → ngoài đoạn vẫn giống
    40–60 %; mép không được nới ra phần nền."""
    clip = nhac_co_nhip(90, seed=7701, sr=SR).astype(np.float32)
    c_tu, c_den = 20.5, 70.25
    P = c_tu + 10 * O_NHIP                               # giây 0 của clip rơi đúng vạch ô nhịp của nền
    video = _chen(nhac_co_nhip(150, seed=7702, sr=SR).astype(np.float32), _cat(clip, c_tu, c_den), P)
    kq = _chay(clip, video, [(P - c_tu, 1.0)], P + 2.5, P + 47.3)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    _khop_doan(d, P, P + c_den - c_tu, c_tu, c_den)


def test_nhac_co_nhip_bi_giong_noi_de_giua_doan_khong_bia_cho_cat():
    """B03: clip nhạc có nhịp (tự giống ở bội ô nhịp) bị giọng nói đè 0 dB một phần ba giữa. p99 nền CHUNG bị các khoảng
    lệch trùng vạch ô nhịp đẩy lên → phần bị đè coi như «vắng» → chỗ cắt 40 s bịa trong khi clip phát suốt. Mức «có
    mặt» theo nền TẠI CHỖ giữ một đoạn liền."""
    clip, P = nhac_co_nhip(120, seed=7001, sr=SR).astype(np.float32), 40.0
    video = _de(_chen(_am(220, 7002), clip, P), P + 40, P + 80, 0.0, 7003, chi_vung=(P + 40, P + 80), nguon=_giong_noi)
    kq = _chay(clip, video, [(P + 0.04, 1.0)], P + 6.0, P + 114.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert kq["cho_cat"] == [] and len(kq["doan"]) == 1
    _khop_doan(kq["doan"][0], P, P + 120, 0, 120)


# ---------------------------------------------------------------------------------------------- im lặng giữa đoạn

def _im(x: np.ndarray, tu: float, den: float) -> np.ndarray:
    """Thay [tu, den) bằng im lặng tuyệt đối (mẫu 0) — tắt tiếng; trục clip vẫn chạy."""
    ra = x.copy()
    ra[int(round(tu * SR)): int(round(den * SR))] = 0.0
    return ra


@pytest.mark.parametrize("dai_im", [1.0, 4.0, 8.0])
def test_im_lang_giua_doan_la_cho_cat_va_giay_im_lang_khong_giong(dai_im):
    """A05: tiếng clip bị thay bằng im lặng tuyệt đối giữa đoạn, trục clip vẫn chạy. Bản cũ: (1) miếng video 3 s toàn
    im lặng có phương sai 0 → Pearson 0/0, sai số làm tròn float32 của tổng tích luỹ cho «giống» ±1,9 hay NaN (biểu đồ
    100 %); (2) nối hai chuỗi cùng neo cách ≤ 5 ô qua khoảng lặng 4 s → mất chỗ cắt; khoảng lặng 1 s các ô vẫn trên
    ngưỡng; dài hơn 5 s thì lõi hở → «chưa tinh chỉnh». Tiếng đè chỉ CỘNG năng lượng: video im lặng trong khi clip có
    tiếng là clip vắng chắc chắn — chỗ cắt đo được."""
    clip, P, a = _am(120, 9101), 40.0, 50.4
    s0, s1 = P + a, P + a + dai_im
    video = _im(_chen(_am(220, 9102), clip, P), s0, s1)
    kq = _chay(clip, video, [(P, 1.0)], P + 6.0, P + 114.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert len(kq["doan"]) == 2, kq["doan"]
    _khop_doan(kq["doan"][0], P, s0, 0, a)
    _khop_doan(kq["doan"][1], s1, P + 120, a + dai_im, 120)
    (c,) = kq["cho_cat"]
    assert _gan(c["video_tu"], s0) and _gan(c["video_den"], s1)
    assert _gan(c["clip_bo_tu"], a) and _gan(c["clip_bo_den"], a + dai_im)
    # ô có miếng 3 s (cả ±0,1 s tìm đỉnh) nằm trọn trong khoảng lặng: 0 %, không phải «giống» vô nghĩa
    trong_im = [u + 0.5 for u in range(int(s0), int(s1) + 1) if u - 1.1 >= s0 and u + 2.1 <= s1]
    ho_so = {t: p for t, p in kq["ho_so"]}
    assert [ho_so.get(t) for t in trong_im] == [0.0] * len(trong_im)
    assert json.loads(json.dumps(kq)) == kq
    _kieu_thuan(kq)                                       # mép từ khoảng lặng cũng là float thuần, không numpy


def test_khoang_lang_cua_chinh_clip_khong_phai_cho_cat():
    """Đối chứng của luật trên: clip TỰ có 4 s im lặng (nghỉ giữa bài), video dùng nguyên clip → video im lặng đúng chỗ
    clip im lặng: không có bằng chứng clip vắng, không được báo chỗ cắt."""
    clip, P = _im(_am(120, 9401), 50.4, 54.4), 40.0
    video = _chen(_am(220, 9402), clip, P)
    kq = _chay(clip, video, [(P, 1.0)], P + 6.0, P + 114.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert kq["cho_cat"] == [] and len(kq["doan"]) == 1
    _khop_doan(kq["doan"][0], P, P + 120, 0, 120)


# ---------------------------------------------------------------------------------------------- tua lùi, mép sát clip

def test_tua_lui_phat_lai_do_ca_hai_neo():
    """H1b: phát clip[0..70] rồi tua lùi 12 s phát clip[58..100]; engine gộp MỘT dòng mang hai neo (30, 42). Bản cũ
    chỉ đo một căn chỉnh nên mất phần phát lại."""
    clip = _am(100, 7801)
    chen = np.concatenate([_cat(clip, 0, 70), _cat(clip, 58, 100)])
    video = _chen(_am(170, 7802), chen, 30.0)
    kq = _chay(clip, video, [(30.0, 1.0), (42.0, 1.0)], 33.0, 139.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert len(kq["doan"]) == 2
    _khop_doan(kq["doan"][0], 30, 100, 0, 70, 0.2)
    _khop_doan(kq["doan"][1], 100, 142, 58, 100, 0.2)
    (c,) = kq["cho_cat"]
    assert _gan(c["video_tu"], 100, 0.2) and _gan(c["video_den"], 100, 0.2)
    assert _gan(c["clip_bo_tu"], 70, 0.2) and _gan(c["clip_bo_den"], 58, 0.2) and c["clip_bo_den"] < c["clip_bo_tu"]


def test_bo_0_6_s_dau_clip_khong_chot_ve_dau_clip():
    """H4: video dùng clip[0,6..59,0]. Bản cũ thấy chuỗi giây chạm giây 0 của clip là chốt mép về 0 (sai 0,6 s)."""
    clip, P = _am(60, 7901), 40.0
    video = _chen(_am(150, 7902), _cat(clip, 0.6, 59.0), P)
    kq = _chay(clip, video, [(P - 0.6, 1.0)], P + 2.9, P + 55.6)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    _khop_doan(d, P, P + 58.4, 0.6, 59.0)
    assert d["cach_tim_mep"] == ["bac_thang", "bac_thang"]


@pytest.mark.parametrize("seed", [9602, 9603, 9604])
def test_mep_khong_lan_sang_not_nen_cung_dai_mel(seed):
    """A03, mép cuối +0,175 s: ngay sau mép thật video phát một nốt nền 1073 Hz trong khi nốt clip 1120 Hz đang ngân —
    cùng dải mel, khung giống ~0,7–0,8: xa cả phân bố «trong» (0,99 ± 0,03) lẫn «ngoài». Laplace đuôi dày xếp các khung
    đó vào «trong» nên bản cũ lấn mép ra ngoài 0,15–0,18 s; khung lạ với cả hai phân bố xếp phía ngoài — mốc là ước lượng
    PHÍA TRONG."""
    t = np.arange(int(0.4 * SR)) / SR

    def not_nhac(f: float, s: int) -> np.ndarray:
        nhieu = np.random.default_rng(s).standard_normal(len(t))
        return (0.7 * (np.sin(2 * np.pi * f * t) * np.hanning(len(t)) + 0.02 * nhieu)).astype(np.float32)
    P, c_den = 40.0, 58.2                                 # mép cuối giữa nốt clip [58,0; 58,4)
    clip = _chen(_am(80, seed), not_nhac(1120.0, seed + 100), 58.0)
    video = _chen(_chen(_am(160, seed + 1), _cat(clip, 0, c_den), P), not_nhac(1073.0, seed + 200), P + c_den)
    kq = _chay(clip, video, [(P, 1.0)], P + 3.0, P + 55.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    _khop_doan(d, P, P + c_den, 0, c_den, 0.05)


def test_doan_cham_cuoi_pham_vi_da_quet_thi_bao_cham_gioi_han():
    clip, P = _am(60, 8001), 60.0
    video = _chen(_am(150, 8002), clip, P)
    kq = _chay(clip, video, [(P, 1.0)], P + 3.0, 97.0, pham_vi_s=(0.0, 100.0))
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    assert _gan(d["video_tu"], P) and d["video_den"] <= 100.0 and d["cach_tim_mep"][1] == "gioi_han"
    assert kq["cham_gioi_han"] is True
    assert (kq["cham_dau"], kq["cham_cuoi"]) == (False, True)       # D-50: chỉ mép cuối được nới về mốc lượt quét


# ---------------------------------------------------------------------------------------------- không chắc → chưa tinh chỉnh

def test_am_thanh_khong_lien_quan_thi_chua_tinh_chinh():
    kq = _chay(_am(60, 8101), _am(150, 8102), [(40.0, 1.0)], 43.0, 97.0)
    assert kq["trang_thai"] == tcm.CHUA and kq["doan"] == [] and kq["ly_do"]


@pytest.mark.parametrize("lech_s", [1.5, -1.7])
def test_neo_lech_hon_1_s_thi_chua_hoac_dung_khong_bao_gio_sai(lech_s):
    clip, P = _am(60, 8201), 40.0
    video = _chen(_am(150, 8202), clip, P)
    kq = _chay(clip, video, [(P + lech_s, 1.0)], P + 3.0, P + 57.0)
    if kq["trang_thai"] == tcm.DA:
        (d,) = kq["doan"]
        _khop_doan(d, P, P + 60, 0, 60)
    else:
        assert kq["ly_do"]


def test_vong_lap_y_het_neo_mo_ho_khong_loi_va_khong_ket_luan():
    """Đoạn dùng nằm trọn trong vòng lặp y hệt (H2a): hai neo cách nhau đúng một chu kỳ giải thích như nhau."""
    lap, chu_ky = vong_lap_y_het(80, seed=8302, sr=SR)
    clip = np.concatenate([nhac_co_nhip(20, seed=8301, sr=SR), lap, nhac_co_nhip(20, seed=8303, sr=SR)])
    clip = clip.astype(np.float32)
    P = 50.0
    video = _chen(_am(150, 8304), _cat(clip, 40, 80), P)
    kq = _chay(clip, video, [(P - 40 - chu_ky, 1.0), (P - 40, 1.0)], P + 2.0, P + 38.0)
    assert json.loads(json.dumps(kq)) == kq
    assert kq["trang_thai"] == tcm.CHUA and "lặp" in kq["ly_do"]


# ---------------------------------------------------------------------------------------------- cửa sổ, huỷ, hạn giờ

def test_chi_giai_ma_cua_so_quanh_loi_theo_khoi(monkeypatch):
    monkeypatch.setattr(tcm, "KHOI_GIAI_MA_S", 100.0)    # ép nhiều khối để kiểm chỗ nối khối
    clip = _am(400, 8401)
    video = _chen(_am(600, 8402), _cat(clip, 100, 300), 200.0)
    goi: list = []
    vung, end, dau = 210.0, 390.0, 100.0
    kq = tcm.tinh_chinh_dong("clip", "video", [(dau, 1.0)], vung, end,
                             doc_pcm=_doc_gia({"clip": clip, "video": video}, goi))
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    _khop_doan(kq["doan"][0], 200, 400, 100, 300)
    bien = 30 + 0.1 * (end - vung)
    cua_so = {"clip": (vung - dau - bien, end - dau + bien), "video": (vung - bien - 45, end + bien + 45)}
    for ten, tu, dai in goi:
        assert dai <= 100.0 + 1e-6
        assert cua_so[ten][0] - 1e-3 <= tu and tu + dai <= cua_so[ten][1] + 1e-3, (ten, tu, dai)
    for ten, (a, b) in cua_so.items():
        assert sum(dai for t, _, dai in goi if t == ten) == pytest.approx(b - a, abs=1e-3)


def test_kiem_huy_nem_loi_thi_loi_di_thang_ra_ngoai():
    class Dung(Exception):
        pass

    def huy():
        raise Dung

    with pytest.raises(Dung):
        _chay(_am(60, 8501), _am(150, 8502), [(40.0, 1.0)], 43.0, 97.0, kiem_huy=huy)


def test_qua_han_chot_thi_chua_tinh_chinh_khong_giai_ma():
    goi: list = []
    kq = tcm.tinh_chinh_dong("clip", "video", [(40.0, 1.0)], 43.0, 97.0, han_chot=time.monotonic() - 1.0,
                             doc_pcm=_doc_gia({"clip": _am(60, 8601), "video": _am(150, 8602)}, goi))
    assert kq["trang_thai"] == tcm.CHUA and kq["ly_do"] == tcm.LY_DO_HET_GIO and goi == []


def test_loi_dai_hon_2_gio_30_thi_chua_tinh_chinh_khong_giai_ma():
    goi: list = []
    kq = tcm.tinh_chinh_dong("clip", "video", [(0.0, 1.0)], 100.0, 100.0 + 9000.5, doc_pcm=_doc_gia({}, goi))
    assert kq["trang_thai"] == tcm.CHUA and kq["ly_do"] == tcm.LY_DO_QUA_DAI and goi == []
    assert json.loads(json.dumps(kq)) == kq


# ---------------------------------------------------------------------------------------------- vòng 3: giải mã

def _gioi_han_goi(doc, toi_da: int = 30):
    """Bọc ``doc_pcm`` giả: quá ``toi_da`` lần gọi = vòng giải mã không tiến — hỏng ngay thay vì treo cả bộ test."""
    dem = [0]

    def boc(*a):
        dem[0] += 1
        assert dem[0] <= toi_da, "vòng giải mã không tiến"
        return doc(*a)
    return boc


def test_cua_so_qua_cuoi_file_vai_ms_khong_lap_vo_han():
    """Phạm vi đã quét dài hơn âm thanh giải mã được 7 ms (pre-skip Opus; MP4 có luồng hình dài hơn tiếng): khối cuối
    xin vài ms, bộ đọc trả 0 mẫu, vị trí không tiến — bản cũ gọi lại tới hạn chót (không hạn chót: mãi mãi). Khối về
    thiếu = hết file; không bao giờ xin mẩu < 50 ms."""
    clip, P = _am(60, 9901), 85.0
    video = _chen(_am(150, 9902), clip, P)
    goi: list = []
    kq = tcm.tinh_chinh_dong("clip", "video", [(P, 1.0)], P + 3.0, P + 57.0, pham_vi_s=(0.0, 150.007),
                             han_chot=time.monotonic() + 5.0,
                             doc_pcm=_gioi_han_goi(_doc_gia({"clip": clip, "video": video}, goi)))
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    _khop_doan(kq["doan"][0], P, P + 60, 0, 60)
    assert len(goi) <= 4 and all(dai >= tcm.DU_CUOI_S for _, _, dai in goi), goi


def test_khoi_tra_thieu_vai_mau_van_doc_het_cua_so(monkeypatch):
    """Bộ giải mã AAC trả mỗi khối thiếu vài mẫu — thiếu < 50 ms không phải hết file. Bản cũ xin tiếp phần dư 1 ms của
    khối cuối, nhận 0 mẫu, lặp tới hạn chót. Khối CUỐI thiếu vài mẫu = hết cửa sổ."""
    monkeypatch.setattr(tcm, "KHOI_GIAI_MA_S", 40.0)
    clip = _am(60, 9911)
    tin = {"clip": clip, "video": _chen(_am(200, 9912), clip, 70.0)}
    goi: list = []

    def doc(duong, tu_s, dai_s):
        goi.append((duong, tu_s, dai_s))
        i0 = int(round(tu_s * SR))
        x = tin[duong][i0: i0 + int(round(dai_s * SR))]
        return x[: max(len(x) - 10, 0)], i0 / SR        # thiếu 10 mẫu như AAC
    kq = tcm.tinh_chinh_dong("clip", "video", [(70.0, 1.0)], 73.0, 127.0, han_chot=time.monotonic() + 5.0,
                             doc_pcm=_gioi_han_goi(doc))
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    _khop_doan(kq["doan"][0], 70, 130, 0, 60)
    assert all(dai >= tcm.DU_CUOI_S for _, _, dai in goi) and len(goi) < 20, goi


def test_khoi_tra_ve_0_mau_la_het_file(monkeypatch):
    """File hết đúng ở chỗ nối khối, phần dư còn lại bằng đúng mức tối thiểu được xin: khối trả 0 mẫu = hết file (bản
    cũ: «thiếu < (dài − 0,05) s» với dài = 0,05 s thì 0 < 0 sai, vị trí không tiến, xin lại mãi)."""
    monkeypatch.setattr(tcm, "KHOI_GIAI_MA_S", 50.0)
    monkeypatch.setattr(tcm, "DU_CUOI_S", 0.0625)                  # số nhị phân đúng: phần dư 0,0625 s không bị làm tròn
    goi: list = []
    dem: list = []

    def moc():
        dem.append(1)
        assert len(dem) < 10, "vòng giải mã không tiến"
    cs = tcm._dac_trung(_gioi_han_goi(_doc_gia({"v": _am(100, 9991)}, goi), 10), "v", 0.0, 100.0625, moc)
    assert len(goi) == 3 and goi[-1][2] == 0.0625 and len(cs.X) > 0


@pytest.fixture(scope="module")
def video_aac(tmp_path_factory):
    """Clip 60 s (WAV) chèn ở 75,37 s của video tổng hợp 300 s, video mã hoá AAC (.m4a, bộ mã aac của FFmpeg) + bản WAV
    gốc của video."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("cần ffmpeg trong PATH")
    d = tmp_path_factory.mktemp("aac")
    clip, P = _giai_dieu(60, seed=9941), 75.37
    video = _giai_dieu(300, seed=9942)
    video[int(round(P * 22050)): int(round(P * 22050)) + len(clip)] = clip
    _ghi_wav(d / "clip.wav", clip)
    _ghi_wav(d / "video.wav", video)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(d / "video.wav"), "-c:a", "aac",
                    "-b:a", "128k", str(d / "video.m4a")], check=True)
    return d, P


@co_ffmpeg
def test_ffmpeg_aac_doc_het_cua_so_va_luoi_khung_khop_ban_wav(video_aac, monkeypatch):
    """AAC (.m4a/.mp4): (1) bản cũ gọi FFmpeg MỖI khối, khối về thiếu vài ms rồi xin phần dư 1 ms → 0 mẫu mãi (3/5 cửa
    sổ kẹt); (2) mẫu đầu sau khi tua trễ tới một khung AAC (1024 mẫu = 46 ms ở 22 kHz), mỗi khối một độ lệch khác. Nay
    MỘT tiến trình mỗi cửa sổ + aresample first_pts: đọc hết [10, 290) qua nhiều khối, lưới khung khớp bản WAV."""
    d, _ = video_aac
    monkeypatch.setattr(tcm, "KHOI_GIAI_MA_S", 60.0)
    dem: list = []

    def moc():
        if threading.current_thread() is threading.main_thread():    # luồng canh FFmpeg cũng gọi moc mỗi 0,2 s
            dem.append(1)
            assert len(dem) < 40, "vòng giải mã không tiến"
    a = tcm._dac_trung(None, str(d / "video.m4a"), 10.0, 290.0, moc)
    b = tcm._dac_trung(None, str(d / "video.wav"), 10.0, 290.0, lambda: None)
    assert len(dem) >= 5 and len(a.X) == len(b.X) and not a.het_file and a.t0 == b.t0
    ea, eb = a.X.mean(axis=1), b.X.mean(axis=1)                       # đường năng lượng từng khung
    lech = max(range(-6, 7), key=lambda j: float(np.corrcoef(ea[50 + j: -50 + j], eb[50:-50])[0, 1]))
    assert lech == 0
    # bộ đọc theo khối kiểu cũ (mỗi khối một lần gọi FFmpeg) cũng phải dừng
    dem.clear()
    c = tcm._dac_trung(tcm._doc_pcm_ffmpeg, str(d / "video.m4a"), 10.0, 290.0, moc)
    assert abs(len(c.X) - len(b.X)) <= 2


@co_ffmpeg
def test_video_aac_mep_toi_mot_khung(video_aac):
    """Cùng audio dạng WAV thì đúng tới vài ms; bản cũ với video AAC: hết giờ (vòng lặp) hoặc mép sớm 25 ms."""
    d, P = video_aac
    kq = tcm.tinh_chinh_dong(str(d / "clip.wav"), str(d / "video.m4a"), [(P + 0.04, 1.0)], P + 3.0, P + 57.0,
                             pham_vi_s=(0.0, 300.0), han_chot=time.monotonic() + 30.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    _khop_doan(kq["doan"][0], P, P + 60, 0, 60, 0.015)


def test_ffmpeg_treo_hay_loi_bao_cau_tieng_viet_ngan(tmp_path, monkeypatch):
    """FFmpeg treo: bản cũ để subprocess.TimeoutExpired lên giao diện — câu tiếng Anh kèm cả dòng lệnh, đường dẫn. Nay
    giết FFmpeg, câu tiếng Việt ngắn; quá hạn chót thì «hết thời gian» ngay, không chờ HAN_KHOI_S."""
    p = tmp_path / "c.wav"
    p.write_bytes(b"")
    monkeypatch.setattr(tcm, "_lenh_ffmpeg", lambda duong, tu, dai: [sys.executable, "-c", "import time; time.sleep(30)"])
    monkeypatch.setattr(tcm, "HAN_KHOI_S", 0.5)
    t = time.monotonic()
    with pytest.raises(RuntimeError) as loi:
        tcm._doc_pcm_ffmpeg(str(p), 0.0, 30.0)
    assert str(loi.value) == "FFmpeg đọc «c.wav» quá lâu — giữ mốc của lượt quét." and time.monotonic() - t < 10
    monkeypatch.setattr(tcm, "HAN_KHOI_S", 120.0)
    monkeypatch.setattr(tcm, "CHI_PHI_GIAI_MA_S", 0.0)  # kiểm đường giết-khi-hết-hạn, không phải ước tính (đo trên PC2)
    monkeypatch.setattr(tcm, "_tre_am", lambda *a: 0.0)  # file rỗng: kiểm đường FFmpeg, không phải ffprobe
    t = time.monotonic()
    kq = tcm.tinh_chinh_dong(str(p), str(p), [(0.0, 1.0)], 3.0, 27.0, han_chot=t + 0.5)
    assert kq["ly_do"] == tcm.LY_DO_HET_GIO and time.monotonic() - t < 10
    monkeypatch.setattr(tcm, "_lenh_ffmpeg", lambda duong, tu, dai: [
        sys.executable, "-c", "import sys; sys.stderr.write('hong C:/Users/ai/c.wav'); sys.exit(3)"])
    with pytest.raises(RuntimeError) as loi:
        tcm._doc_pcm_ffmpeg(str(p), 0.0, 30.0)
    # giao diện + CSV phụ: một câu tiếng Việt, không chữ tiếng Anh, không đường dẫn; chi tiết FFmpeg ở __cause__ (nhật ký)
    assert str(loi.value) == ("FFmpeg không đọc được «c.wav» (file mất, đang bị khoá, hỏng hoặc không có tiếng) — giữ "
                              "mốc của lượt quét.")
    assert "hong" in str(loi.value.__cause__)


def test_do_duong_kiem_huy_moi_khoi_o():
    """Một lượt đo (vòng căn chỉnh đầu tìm ±0,5 s trên MỌI ô) không gọi kiem_huy: lõi 2 giờ 1,3–2,5 s không kiểm huỷ/hạn
    chót. Nay kiểm mỗi KHOI_O ô, ngoại lệ đi thẳng ra ngoài."""
    clip = _am(700, 9961)
    doc = _doc_gia({"clip": clip, "video": _chen(_am(800, 9962), clip, 50.0)})
    cl = tcm._dac_trung(doc, "clip", 0.0, 700.0, lambda: None)
    vi = tcm._dac_trung(doc, "video", 0.0, 800.0, lambda: None)
    u = np.arange(52, 748)
    goi: list = []
    tcm._do_duong(cl, vi, 50.0, 1.0, u, w_s=tcm.W_BAT_S, moc=lambda: goi.append(1))
    assert len(goi) >= len(u) // tcm.KHOI_O

    class Dung(Exception):
        pass

    def huy():
        raise Dung
    with pytest.raises(Dung):
        tcm._do_duong(cl, vi, 50.0, 1.0, u, moc=huy)


def test_doan_khop_dai_khong_kip_han_chot_thi_tu_choi_ngay():
    """Lõi 1 giờ với 5 s còn lại: bản cũ giải mã tới hết hạn rồi mới «hết thời gian» — tiêu cả ngân sách, các dòng sau của
    video bị bỏ không thử. Ước tính vượt phần còn lại → từ chối ngay, không giải mã."""
    goi: list = []
    t = time.monotonic()
    kq = tcm.tinh_chinh_dong("clip", "video", [(100.0, 1.0)], 110.0, 3710.0, han_chot=t + 5.0,
                             doc_pcm=_doc_gia({}, goi))
    assert kq["trang_thai"] == tcm.CHUA and kq["ly_do"] == tcm.LY_DO_KHONG_KIP and goi == []
    assert time.monotonic() - t < 1.0


# ---------------------------------------------------------------------------------------------- vòng 3: căn chỉnh

def test_hai_neo_troi_hoi_tu_mot_duong_khong_thanh_lap_y_het(monkeypatch):
    """Video chậm 0,2 %: hai neo engine tách vì độ trôi hội tụ về CÙNG một đường sau khi sửa độ trôi — bản cũ có hai hàng
    độ giống y hệt nên «lặp y hệt» (CHƯA), và mỗi neo thừa tốn cả một lượt căn chỉnh (3–5 s ở lõi 2 giờ). Trùng đường thì
    thôi đo neo đó, không thêm hàng."""
    clip, P, toc = _am(300, 9951), 40.0, 1.002
    video = _chen(_am(420, 9952), doi_toc_do(clip, toc).astype(np.float32), P)
    goc, ra = tcm._can_chinh, []
    monkeypatch.setattr(tcm, "_can_chinh", lambda *a: ra.append(goc(*a)) or ra[-1])
    kq = _chay(clip, video, [(P, 1.0), (P + 0.45, 1.0)], P + 10.0, P + 290.0)
    assert [len(x) for x in ra] == [1, 0]
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    _khop_doan(d, P, P + 300 * toc, 0, 300)
    assert abs(d["k"] - toc) < 2e-4


@pytest.mark.parametrize("delta, sai", [(0.3, 0.1), (-0.3, 0.1), (0.15, 0.15)])
def test_nhay_nho_trong_mot_neo_ra_hai_doan_khong_k_gia(delta, sai):
    """Video = clip[0, 60) + clip[60 + δ, 120): engine gộp hai căn chỉnh cách < 1 s thành MỘT neo. Bản cũ khớp một đường
    thẳng qua hai mảnh: MỘT đoạn với k giả (0,9964 — «video nhanh 0,36 %»), ánh xạ lệch 0,15 s, mất chỗ nhảy. Phần dư hai
    bậc → hai căn chỉnh: hai đoạn k = 1 và chỗ cắt dài 0 (δ < 0 = phát lại)."""
    clip, P = _am(120, 7301), 40.0
    chen = np.concatenate([_cat(clip, 0, 60), _cat(clip, 60 + delta, 120)])
    video = _chen(_am(220, 7302), chen, P)
    kq = _chay(clip, video, [(P, 1.0)], P + 3.0, P + len(chen) / SR - 3.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert len(kq["doan"]) == 2, kq["doan"]
    _khop_doan(kq["doan"][0], P, P + 60, 0, 60, sai)
    _khop_doan(kq["doan"][1], P + 60, P + 120 - delta, 60 + delta, 120, sai)
    assert all(abs(d["k"] - 1.0) < 1e-3 for d in kq["doan"])
    (c,) = kq["cho_cat"]
    assert c["video_den"] - c["video_tu"] < 0.1 and _gan(c["clip_bo_den"] - c["clip_bo_tu"], delta, 0.1)


def test_nhay_0_9_s_trong_mot_neo_khong_bao_gio_mot_doan():
    """Nhảy 0,9 s (ngoài tầm tìm ±0,5 s): chỉ thấy mảnh đầu — phải CHƯA (lưới an toàn: nửa lõi không giải thích được)
    hoặc đúng hai đoạn, KHÔNG BAO GIỜ một đoạn bỏ mất 60 s."""
    clip, P = _am(120, 7311), 40.0
    chen = np.concatenate([_cat(clip, 0, 60), _cat(clip, 60.9, 120)])
    video = _chen(_am(220, 7312), chen, P)
    kq = _chay(clip, video, [(P, 1.0)], P + 3.0, P + len(chen) / SR - 3.0)
    if kq["trang_thai"] == tcm.DA:
        assert len(kq["doan"]) == 2, kq["doan"]
        _khop_doan(kq["doan"][0], P, P + 60, 0, 60)
        _khop_doan(kq["doan"][1], P + 60, P + 119.1, 60.9, 120)
    else:
        assert kq["ly_do"]


# ---------------------------------------------------------------------------------------------- vòng 3: mép, khe, tiếng đè

def _anh_xa_dung(kq: dict, that: list, sai: float = 0.15) -> None:
    """Mọi giây (bước 0,1 s) của mọi đoạn ĐÃ báo nằm trong một đoạn thật và ánh xạ sang giây clip lệch ≤ ``sai``."""
    for d in kq["doan"]:
        for t in np.arange(d["video_tu"] + 0.2, d["video_den"] - 0.2, 0.1):
            c = d["clip_tu"] + (t - d["video_tu"]) / d["k"]
            assert any(vt <= t <= vd and abs(ct + (t - vt) - c) <= sai for vt, vd, ct in that), (t, c, d)


@pytest.mark.parametrize("de", [(80.0, 100.0), (88.0, 112.0), (100.0, 120.0), (96.0, 104.0)])
def test_tieng_de_quanh_cho_tua_lui_khong_bia_cho_cat(de):
    """Tua lùi (engine: một dòng HAI neo) + giọng nói đè 0 dB quanh chỗ nối 100 s. Bản cũ coi MỌI khe giữa hai đoạn khác
    neo là chỗ cắt đã đo: «chỗ cắt» bịa 4–20 s với mép khung chính xác, trong khi ô của khe vẫn hơn p99 nền (clip còn
    dưới lớp đè). Nay khe chỉ là chỗ cắt khi ô sát mép vắng clip theo CẢ HAI neo; không thì CHƯA (hoặc đúng)."""
    clip = _am(100, 7801)
    chen = np.concatenate([_cat(clip, 0, 70), _cat(clip, 58, 100)])
    video = _de(_chen(_am(170, 7802), chen, 30.0), de[0], de[1], 0.0, 7803, chi_vung=de, nguon=_giong_noi)
    kq = _chay(clip, video, [(30.0, 1.0), (42.0, 1.0)], 33.0, 139.0)
    if kq["trang_thai"] == tcm.DA:
        assert all(c["video_den"] - c["video_tu"] <= 1.0 for c in kq["cho_cat"]), kq["cho_cat"]
        _anh_xa_dung(kq, [(30.0, 100.0, 0.0), (100.0, 142.0, 58.0)])
    else:
        assert kq["ly_do"]


def test_tieng_de_truoc_cho_cat_chen_khong_doi_cho_cat():
    """Cắt + chèn 6 s âm khác (hai neo cách 6 s) + giọng nói đè 8 s TRƯỚC chỗ cắt: bản cũ báo chỗ cắt [82, 96] thay vì
    [90, 96] (đoạn đầu dừng ở chỗ tiếng đè bắt đầu)."""
    clip, P = _am(120, 9901), 30.0
    v = _chen(_am(220, 9902), np.concatenate([_cat(clip, 0, 60), _am(6, 9903), _cat(clip, 60, 120)]), P)
    video = _de(v, P + 52.0, P + 60.0, 0.0, 9904, chi_vung=(P + 52.0, P + 60.0), nguon=_giong_noi)
    kq = _chay(clip, video, [(P + 0.04, 1.0), (P + 5.95, 1.0)], P + 3.0, P + 123.0)
    if kq["trang_thai"] == tcm.DA:
        _anh_xa_dung(kq, [(P, P + 60, 0.0), (P + 66, P + 126, 60.0)])
        for c in kq["cho_cat"]:
            assert _gan(c["video_tu"], P + 60, 0.2) and _gan(c["video_den"], P + 66, 0.2), c
    else:
        assert kq["ly_do"]


@pytest.mark.parametrize("de_dau, loi_tu", [(40.0, 8.0), (25.0, 22.0), (12.0, 9.0), (8.0, 5.0)],
                         ids=["mep_tho", "mep_bac_thang", "bang_chung_ngoai_mep", "bang_chung_ngoai_mep_8s"])
def test_tieng_de_dau_doan_khong_bao_mep_tre(de_dau, loi_tu):
    """Giọng nói đè 0 dB lên ĐẦU đoạn dùng; lõi engine bắt đầu trong vùng bị đè. Bản cũ: ĐÃ với mép đầu «thô» trễ 10 s
    (40 s đè) hay mép «bậc thang» ở chỗ tiếng đè hết (25 s đè), không cờ chạm giới hạn — giao diện nói clip giây 0–25
    không được dùng. Mép thô → CHƯA; ô ngoài mép còn hơn p99 nền (clip dưới tiếng đè) → CHƯA. Ca 12 s chỉ bước kiểm bằng
    chứng ngoài mép bắt được (hai ca kia đã dừng ở mép thô): bỏ bước đó là ĐÃ với mép trễ 12 s. Từ vòng 4 luật «chỗ vấp
    ngắn» dừng ca 12 s trước bước đó; ca 8 s thì chỉ bước đó bắt được (bỏ nó: ĐÃ, mép trễ 8 s, không cờ)."""
    clip, P = _am(120, 9831), 40.0
    video = _de(_chen(_am(240, 9832), clip, P), P, P + de_dau, 0.0, 9833, chi_vung=(P, P + de_dau), nguon=_giong_noi)
    kq = _chay(clip, video, [(P + 0.04, 1.0)], P + loi_tu, P + 114.0)
    if kq["trang_thai"] == tcm.DA:
        _khop_doan(kq["doan"][0], P, P + 120, 0, 120)
    else:
        assert kq["ly_do"]


@pytest.mark.parametrize("dai_thay", [3.0, 5.0])
def test_thay_tieng_vai_giay_cung_neo_khong_noi_thanh_mot_doan(dai_thay):
    """3–6 s tiếng clip bị THAY bằng âm khác (trục clip vẫn chạy, cùng neo): bản cũ nối khe ≤ 5 ô bất kể nội dung — MỘT
    đoạn liền với độ giống thấp nhất 0 %. Tiếng đè giữ ô trên nền, tiếng thay kéo ô xuống bằng nền: không nối."""
    clip, P, a = _am(120, 9821), 40.0, 50.2
    video = _chen(_chen(_am(220, 9822), clip, P), _am(dai_thay, 9823), P + a)
    kq = _chay(clip, video, [(P + 0.05, 1.0)], P + 6.0, P + 114.0)
    if kq["trang_thai"] == tcm.DA:
        assert len(kq["doan"]) == 2, kq["doan"]
        _khop_doan(kq["doan"][0], P, P + a, 0, a)
        _khop_doan(kq["doan"][1], P + a + dai_thay, P + 120, a + dai_thay, 120)
    else:
        assert kq["ly_do"]


@pytest.mark.parametrize("o, lan", [(2, 4), (1, 8)], ids=["2_o_x4", "1_o_x8"])
def test_dj_lap_o_nhip_khong_noi_qua_anh_xa_sai(o, lan):
    """Nhạc có nhịp: o ô nhịp phát lan lần thay o·lan ô nhịp (cùng neo trước/sau). Ô nhịp giống nhau giữ độ giống trên
    ngưỡng nên bản cũ nối qua: 12,75 s video mang giây clip không có trong video. Căn chỉnh lệch bội ô nhịp hơn hẳn neo →
    CHƯA (hoặc không đoạn nào ánh xạ sai). 1 ô × 8: vòng lặp tách đoạn, khe trông như «vắng» — chỉ phần kiểm KHE tới
    đoạn sau bắt được."""
    clip, P, a = nhac_co_nhip(120, seed=9861, sr=SR).astype(np.float32), 40.0, 50.0
    lap = np.tile(_cat(clip, a, a + o * O_NHIP), lan)
    sau = a + o * lan * O_NHIP
    video = _chen(_am(220, 9862), np.concatenate([_cat(clip, 0, a), lap, _cat(clip, sau, 120)]), P)
    kq = _chay(clip, video, [(P + 0.04, 1.0)], P + 6.0, P + 114.0)
    if kq["trang_thai"] == tcm.DA:
        that = [(P, P + a, 0.0)] + [(P + a + o * O_NHIP * j, P + a + o * O_NHIP * (j + 1), a) for j in range(lan)] + \
            [(P + sau, P + 120, sau)]
        _anh_xa_dung(kq, that)
    else:
        assert kq["ly_do"]


@pytest.mark.parametrize("dai_im", [9.0, 12.0])
def test_im_lang_dai_cua_chinh_clip_van_mot_doan(dai_im):
    """Clip TỰ im lặng tuyệt đối ≥ 9 s giữa bài, video dùng trọn: ô có miếng clip không đổi không đo được — bản cũ coi
    là khe (−1), khe > 5 ô không nối, lưới an toàn → CHƯA. Ô không đo được là trung tính: khe chỉ gồm chúng thì nối."""
    clip, P = _im(_am(120, 9401), 50.4, 50.4 + dai_im), 40.0
    video = _chen(_am(220, 9402), clip, P)
    kq = _chay(clip, video, [(P, 1.0)], P + 6.0, P + 114.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert kq["cho_cat"] == [] and len(kq["doan"]) == 1
    _khop_doan(kq["doan"][0], P, P + 120, 0, 120)


def test_clip_chen_nho_canh_noi_dung_to_khong_bia_khoang_lang():
    """Clip chèn −36 dB giữa nội dung to, clip có 1,5 s khẽ thêm −25 dB: bản cũ đo «im lặng» của video theo nội dung to
    bên cạnh (p99 cửa sổ − 60 dB) nên chỗ khẽ thành khoảng lặng → chỗ cắt «chắc chắn» 1,36 s bịa. Mức tham chiếu lấy trong
    chính đoạn."""
    clip, P = _am(20, 9873), 70.0
    clip[int(9.25 * SR): int(10.75 * SR)] *= 10 ** (-25.0 / 20)
    video = _chen(_am(200, 9874), clip * 10 ** (-36.0 / 20), P)
    kq = _chay(clip, video, [(P + 0.04, 1.0)], P + 1.0, P + 19.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert kq["cho_cat"] == [] and len(kq["doan"]) == 1
    _khop_doan(kq["doan"][0], P, P + 20, 0, 20)


def test_clip_mo_dau_bang_im_lang_dai_mep_o_cho_co_tieng_va_cham_gioi_han():
    """Clip mở đầu bằng 20 s im lặng tuyệt đối, video dùng trọn (im lặng theo): phần im lặng không đo được là có dùng hay
    không — mép = chỗ clip bắt đầu có tiếng, cờ chạm giới hạn bật; không phải mép «thô» lệch 1,4 s như bản cũ, cũng
    không CHƯA vì mép thô."""
    clip, P = _im(_am(80, 9701), 0.0, 20.0), 50.37
    video = _chen(_am(220, 9702), clip, P)
    kq = _chay(clip, video, [(P + 0.05, 1.0)], P + 23.0, P + 77.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    _khop_doan(d, P + 20, P + 80, 20, 80)
    assert d["cach_tim_mep"][0] == "clip_lang" and kq["cham_gioi_han"] is True
    assert (kq["cham_dau"], kq["cham_cuoi"]) == (True, False)


# ---------------------------------------------------------------------------------------------- vòng 3: khoá vị từ

def test_cat_chen_30_s_hai_neo_ra_hai_doan_va_cho_cat():
    """Đối chứng của luật khe giữa hai neo: chỗ cắt + chèn 30 s âm khác — ô sát hai mép trong khe vắng clip theo cả hai
    neo → chỗ cắt đã đo [80, 110], không phải tiếng đè."""
    clip = _am(120, 9971)
    chen = np.concatenate([_cat(clip, 0, 50), _am(30, 9974), _cat(clip, 60, 120)])
    video = _chen(_am(220, 9972), chen, 30.0)
    kq = _chay(clip, video, [(30.0, 1.0), (50.0, 1.0)], 33.0, 167.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert len(kq["doan"]) == 2
    _khop_doan(kq["doan"][0], 30, 80, 0, 50)
    _khop_doan(kq["doan"][1], 110, 170, 60, 120)
    (c,) = kq["cho_cat"]
    assert _gan(c["video_tu"], 80) and _gan(c["video_den"], 110)


def test_loi_ngan_giua_doan_dai_cham_gioi_han_cua_so():
    """Lõi 20 s nằm giữa đoạn dùng 200 s: cửa sổ phân tích (lõi ± 32 s) cắt đoạn ở cả hai đầu — mép là «giới hạn» và cờ
    chạm giới hạn phải bật (mép thật có thể nằm ngoài)."""
    clip, P = _am(240, 9981), 30.0
    video = _chen(_am(300, 9982), _cat(clip, 20, 220), P)
    kq = _chay(clip, video, [(P - 20.0, 1.0)], P + 90.0, P + 110.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    assert d["cach_tim_mep"] == ["gioi_han", "gioi_han"] and kq["cham_gioi_han"] is True
    assert d["video_tu"] > P + 50 and d["video_den"] < P + 150


@pytest.mark.parametrize("o_dau", [True, False], ids=["dau_file", "cuoi_file"])
def test_doan_trung_dau_hay_cuoi_file_video_bao_cham_gioi_han(o_dau):
    """Clip trùng ĐÚNG đầu (hay sát cuối) file video: mép đo được là đầu/cuối clip, nhưng file có thể là bản cắt của
    video dài hơn — lần dùng có thể bắt đầu trước / kéo dài sau file: cờ chạm giới hạn phải bật. Cuối: còn 0,5 s nền sau
    clip, nhãn mép là «cuối clip» — cờ bật vì mép cách cuối phần giải mã < 1 s, không nhờ nhãn giới hạn."""
    clip, nen = _am(60, 9985), _am(90, 9986)
    video = np.concatenate([clip, nen] if o_dau else [nen[: int(89.5 * SR)], clip, _am(0.5, 9987)])
    P = 0.0 if o_dau else 89.5
    kq = _chay(clip, video, [(P, 1.0)], P + 3.0, P + 57.0, pham_vi_s=(0.0, 150.0))
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    (d,) = kq["doan"]
    _khop_doan(d, P, P + 60, 0, 60)
    assert kq["cham_gioi_han"] is True


def test_am_thanh_giong_nhau_moi_do_lech_thi_chua_tinh_chinh():
    """Tiếng lặp đúng chu kỳ 0,1 s (mọi khoảng lệch nền là bội của nó): nền giống như «trong», ngưỡng > 95 % — không
    phân biệt được đoạn dùng thật."""
    t = np.arange(int(90 * SR)) / SR
    clip = (0.5 * np.sin(2 * np.pi * 440 * t) * (0.55 + 0.45 * np.sign(np.sin(2 * np.pi * 10 * t)))).astype(np.float32)
    video = _chen(_am(200, 9992), clip, 60.0)
    kq = _chay(clip, video, [(60.0, 1.0)], 63.0, 147.0)
    assert kq["trang_thai"] == tcm.CHUA and kq["ly_do"] == tcm.LY_DO_TUONG_PHAN


def test_neo_thu_hai_lech_dung_mot_khoang_nen_van_do_duoc():
    """Tua lùi đúng 7,3 s (= một khoảng lệch của đường nền): khoảng đó phải bị bỏ khỏi đường nền — ở đó «nền» là lần phát
    lại thật, đẩy p99 nền lên như «trong»."""
    clip = _am(100, 7821)
    chen = np.concatenate([_cat(clip, 0, 60), _cat(clip, 52.7, 100)])
    video = _chen(_am(170, 7822), chen, 30.0)
    kq = _chay(clip, video, [(30.0, 1.0), (37.3, 1.0)], 33.0, 134.0)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert len(kq["doan"]) == 2
    _khop_doan(kq["doan"][0], 30, 90, 0, 60, 0.2)
    _khop_doan(kq["doan"][1], 90, 137.3, 52.7, 100, 0.2)


# ---------------------------------------------------------------------------------------------- vòng 4: review trước khi gộp

@co_ffmpeg
def test_doi_tan_so_mau_giua_cua_so_khong_day_lui_phan_sau(tmp_path):
    """Bản ghi .ts (truyền hình, OBS) đổi 44,1 → 48 kHz giữa chừng, nhãn thời gian liền mạch: FFmpeg dựng lại bộ lọc và
    «aresample first_pts=0» áp LẠI từ đầu cửa sổ → mọi mẫu sau chỗ đổi trễ đúng (chỗ đổi − đầu cửa sổ): cửa sổ 10 s ra
    15 s âm thanh, mép «đo được» mà sai. Nay mẫu sau chỗ đổi vẫn đúng giây của nó (lệch còn lại vài chục ms là độ trễ mồi
    AAC của chính file .ts — engine cũng thấy như vậy)."""
    _ghi_wav(tmp_path / "goc.wav", _giai_dieu(20, seed=9701))
    phan = []
    for i, (vao, ar) in enumerate(((["-t", "10"], 44100), (["-ss", "10"], 48000))):
        p = tmp_path / f"p{i}.ts"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *vao, "-i", str(tmp_path / "goc.wav"),
                        "-ar", str(ar), "-c:a", "aac", "-b:a", "128k", *(["-output_ts_offset", "10"] if i else []),
                        "-f", "mpegts", str(p)], check=True)
        phan.append(p.read_bytes())
    (tmp_path / "v.ts").write_bytes(b"".join(phan))
    x, _ = tcm._doc_pcm_ffmpeg(str(tmp_path / "v.ts"), 5.0, 10.0)
    ref, _ = tcm._doc_pcm_ffmpeg(str(tmp_path / "goc.wav"), 5.0, 10.0)
    assert abs(len(x) / SR - 10.0) < 0.1, len(x) / SR
    tim, n = int(0.25 * SR), int(2.0 * SR)
    for c in (2.0, 7.0):                                # 3 s trước và 2 s sau chỗ đổi (giây 10 của file)
        a, v = x[int(c * SR) - tim: int(c * SR) + n + tim], ref[int(c * SR): int(c * SR) + n]
        r = np.fft.irfft(np.fft.rfft(a, len(a) + n) * np.conj(np.fft.rfft(v, len(a) + n)), len(a) + n)[: 2 * tim + 1]
        assert abs(int(np.argmax(r)) - tim) / SR < 0.08, (c, (int(np.argmax(r)) - tim) / SR)


def test_bam_dung_khi_ffmpeg_im_lang_thi_dung_ngay(tmp_path, monkeypatch):
    """FFmpeg còn sống mà không trả mẫu nào (ổ cứng bận/ngủ — D-33 cho FFmpeg im tới 5 phút): bản cũ chỉ kiểm huỷ GIỮA
    hai khối, nên bấm Dừng phải chờ tới hạn chót hay HAN_KHOI_S (2 phút) rồi báo «hết thời gian»/«quá lâu». Nay luồng
    canh kiểm huỷ mỗi 0,2 s, giết FFmpeg, lỗi huỷ đi thẳng ra ngoài."""
    p = tmp_path / "c.wav"
    p.write_bytes(b"")
    monkeypatch.setattr(tcm, "_lenh_ffmpeg", lambda duong, tu, dai: [sys.executable, "-c", "import time; time.sleep(30)"])
    monkeypatch.setattr(tcm, "HAN_KHOI_S", 8.0)
    monkeypatch.setattr(tcm, "_tre_am", lambda *a: 0.0)  # file rỗng: kiểm đường FFmpeg, không phải ffprobe

    class Dung(Exception):
        pass
    t = time.monotonic()

    def huy():
        if time.monotonic() - t > 0.5:
            raise Dung
    with pytest.raises(Dung):
        tcm.tinh_chinh_dong(str(p), str(p), [(0.0, 1.0)], 3.0, 27.0, kiem_huy=huy)
    assert time.monotonic() - t < 3.0


@pytest.mark.parametrize("kieu, vap, duoi", [("on", 0.4, 0.9), ("tat_tieng", 0.4, 0.6)])
def test_cho_vap_ngan_sat_mep_khong_keo_mep_vao_trong(kieu, vap, duoi):
    """0,4 s tiếng lạ (ồn −30 dB) hay tắt tiếng trong video, cách mép cuối lần dùng 0,6–0,9 s, clip vẫn tiếp tới hết: một
    khung lạ cộng ~+30 bằng chứng «ngoài», một khung clip sạch chỉ ~−9 «trong» — cực đại tổng tích luỹ (giả định MỘT chỗ
    đổi) rơi vào chỗ vấp: bản cũ báo ĐÃ với mép «đo được» sớm 1–1,3 s, bỏ cả phần clip sạch sau chỗ vấp. Bằng chứng tăng
    lại sau một chỗ trũng nông (clip còn tiếp) → không đo được mép (hoặc đúng)."""
    clip, P, U = _am(80, 6001), 40.0, 50.0
    v = clip[: int(U * SR)].copy()
    i0, i1 = int(round((U - duoi - vap) * SR)), int(round((U - duoi) * SR))
    v[i0:i1] = 0.0 if kieu == "tat_tieng" else \
        0.7 * 10 ** (-30 / 20) * np.random.default_rng(6008).standard_normal(i1 - i0)
    video = _chen(_am(180, 6002), v, P)
    kq = _chay(clip, video, [(P + 0.04, 1.0)], P + 2.5, P + 47.5, pham_vi_s=(0.0, 180.0))
    if kq["trang_thai"] == tcm.DA:
        _anh_xa_dung(kq, [(P, P + U, 0.0)])
        assert _gan(kq["doan"][-1]["video_den"], P + U, 0.15), kq["doan"]
    else:
        assert kq["ly_do"]


@pytest.mark.parametrize("de_tu", [147.0, 148.0])
def test_tieng_de_sat_cuoi_pham_vi_quet_thi_cham_gioi_han(de_tu):
    """Lần dùng kéo qua cuối phần đã quét (150 s), giọng nói đè bắt đầu 2–3 s trước đó: ô kiểm bằng chứng phía ngoài mép
    không còn chỗ (miếng 3 s phải nằm trọn trong phần đã giải mã) — bản cũ bỏ qua bước kiểm và báo ĐÃ với mép «đo được»
    sớm 12–13 s, không cờ chạm giới hạn. Không kiểm được phía ngoài mép = chạm giới hạn."""
    clip, P = _am(120, 9991), 40.0
    video = _de(_chen(_am(220, 9992), clip, P), de_tu, 170.0, 0.0, 9993, chi_vung=(de_tu, 170.0), nguon=_giong_noi)
    kq = _chay(clip, video, [(P + 0.04, 1.0)], 45.0, 144.0, pham_vi_s=(0.0, 150.0))
    assert kq["trang_thai"] == tcm.CHUA or kq["cham_gioi_han"] is True, kq["doan"]
    assert kq["trang_thai"] == tcm.CHUA or kq["cham_cuoi"] is True, kq["doan"]     # D-50: đúng mép đó


def test_tieng_de_sat_dau_cua_so_phan_tich_thi_cham_gioi_han():
    """Lõi engine chỉ phủ [100, 155] của lần dùng [40, 160] (ô phân tích bắt đầu ở 64 s), giọng nói đè hết ở 65,5 s: bản
    cũ báo mép đầu «đo được» ở 65,5 s (sai 25 s), không cờ — phía ngoài mép chưa hề được đo."""
    clip, P = _am(120, 9981), 40.0
    video = _de(_chen(_am(220, 9982), clip, P), 50.0, 65.5, 0.0, 9984, chi_vung=(50.0, 65.5), nguon=_giong_noi)
    kq = _chay(clip, video, [(P + 0.04, 1.0)], 100.0, 155.0)
    assert kq["trang_thai"] == tcm.CHUA or kq["cham_gioi_han"] is True, kq["doan"]
    assert kq["trang_thai"] == tcm.CHUA or kq["cham_dau"] is True, kq["doan"]     # D-50: đúng mép đó


def test_clip_ngan_sat_dau_video_khong_bao_file_ngan_hon_du_kien():
    """Clip trọn vẹn 6 s (engine nhận khớp từ 5 s) dùng ở giây 1 của video: các khoảng lệch của đường nền rơi ra ngoài
    file, không đủ ô để đo nền — bản cũ báo «file clip hoặc video ngắn hơn dự kiến» dù cả hai file đọc đủ, người dùng
    tưởng file hỏng."""
    clip, P = _am(6.0, 7011), 1.0
    video = _chen(_am(200, 7012), clip, P)
    kq = _chay(clip, video, [(P + 0.04, 1.0)], P + 0.3, P + 5.7, pham_vi_s=(0.0, 200.0))
    assert kq["trang_thai"] == tcm.CHUA and kq["ly_do"] == tcm.LY_DO_NEN_IT

# ---------------------------------------------------------------------------------------------- vòng 5: kiểm độc lập

@co_ffmpeg
@pytest.mark.parametrize("vo", ["mkv", "mp4", "ts"])
def test_video_tieng_bat_dau_tre_hon_hinh_moc_theo_trinh_phat(tmp_path, vo):
    """Video có luồng tiếng bắt đầu 0,5 s SAU hình (bản ghi, bản cắt chép luồng): trình phát đặt clip ở giây 30. Vòng 4
    bỏ first_pts=0: cửa sổ bắt đầu trước mẫu tiếng đầu thì không còn gì đệm im lặng — mẫu tiếng đầu mang nhãn giây 0, mọi
    mốc sớm 0,5 s mà vẫn «đã tinh chỉnh», không cờ (.ts: sai từ trước vòng 4). Cửa sổ video phải bắt đầu sau chỗ tiếng
    bắt đầu ≥ 1 s (tua thô 1 s trước «tu» phải rơi vào luồng tiếng)."""
    clip, a, P, tre = _giai_dieu(40, seed=8101), _giai_dieu(100, seed=8102), 30.0, 0.5
    i0 = int(round((P - tre) * 22050))
    a[i0: i0 + len(clip)] = clip
    _ghi_wav(tmp_path / "clip.wav", clip)
    _ghi_wav(tmp_path / "a.wav", a)
    v = tmp_path / f"v.{vo}"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=gray:s=160x120:r=25:d=101", "-itsoffset", str(tre), "-i", str(tmp_path / "a.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "mpeg4", "-c:a", "aac", "-ar", "44100", "-b:a", "128k",
                    *(["-f", "mpegts"] if vo == "ts" else []), str(v)], check=True)
    neo = P - tre + 0.04                                 # engine đọc tiếng từ mẫu đầu (khối 0 không đệm): sớm 0,5 s
    kq = tcm.tinh_chinh_dong(str(tmp_path / "clip.wav"), str(v), [(neo, 1.0)], neo + 2.5, neo + 37.5,
                             pham_vi_s=(0.0, 100.0))
    assert kq["trang_thai"] == tcm.CHUA or _gan(kq["doan"][0]["video_tu"], P, 0.05), kq["doan"]


@pytest.mark.parametrize("het", [148.0, 148.6])
def test_o_ngoai_mep_vuot_phan_da_giai_ma_khong_tinh_la_clip_vang(het):
    """Nhạc đè 0 dB từ 145,3 s tới hết lần dùng [30, 150,75], phần đã quét dừng ở 148–148,6 s: mép cuối «đo được» ở chỗ
    nhạc đè bắt đầu (sớm 5,5 s). Ở 148,6 s ô kiểm duy nhất phía ngoài mép có miếng 3 s vượt phần đã giải mã — độ giống
    không đo được (NaN) mà vòng 4 coi là «clip vắng»: ĐÃ không cờ. Không đo được = chưa kiểm → cờ chạm giới hạn."""
    clip, P = _am(130, 9771), 30.0
    v = _chen(_am(152, 9772) * 0.3, _cat(clip, 0, 120.75), P)
    video = _de(v, 145.3, 150.75, 0.0, 9773, chi_vung=(145.3, 151.2))
    kq = _chay(clip, video, [(P + 0.04, 1.0)], P + 6.0, 144.0, pham_vi_s=(0.0, het))
    assert kq["trang_thai"] == tcm.CHUA or kq["cham_gioi_han"] is True, kq["doan"]
    assert kq["trang_thai"] == tcm.CHUA or kq["cham_cuoi"] is True, kq["doan"]     # D-50: đúng mép đó


@pytest.mark.parametrize("A, B, delta", [(10, 10, 0.4), (10, 6, 0.3)], ids=["10+10_nhay_0.4", "10+6_nhay_0.3"])
def test_nhay_nho_trong_lan_dung_ngan_khong_anh_xa_sai(A, B, delta):
    """Lần dùng ngắn 16–20 s có chỗ nhảy 0,3–0,4 s mà engine gộp MỘT neo: hai mảnh quá ngắn để tách (< 20 ô chắc chắn).
    Bỏ chặn sửa tốc độ 1 %: đường thẳng qua hai mảnh cho k giả 0,989, ánh xạ lệch 0,21 s (10+10). Có chặn mà không tách
    thì giữ đường của engine: một đoạn ánh xạ lệch 0,34 s, mép cuối sớm 5,5 s, không cờ (10+6). ≥ 4 ô chắc chắn liền
    nhau còn lệch đường cuối > 0,12 s → CHƯA (hoặc đúng)."""
    clip, P, c0 = _am(60, 5101), 50.0, 10.0
    v = np.concatenate([_cat(clip, c0, c0 + A), _cat(clip, c0 + A + delta, c0 + A + delta + B)])
    L = A + B
    kq = _chay(clip, _chen(_am(200, 5102), v, P), [(P - c0 + 0.04, 1.0)], P + 0.05 * L, P + 0.95 * L)
    if kq["trang_thai"] == tcm.DA:
        _anh_xa_dung(kq, [(P, P + A, c0), (P + A, P + L, c0 + A + delta)])
        assert _gan(kq["doan"][0]["video_tu"], P, 0.15) and _gan(kq["doan"][-1]["video_den"], P + L, 0.15), kq["doan"]
    else:
        assert kq["ly_do"]


@co_ffmpeg
def test_canh_ffmpeg_khong_tinh_thoi_gian_noi_goi_xu_ly_khoi(tmp_path, monkeypatch):
    """Luồng canh đo «một khối không về trong HAN_KHOI_S» từ lúc BẮT ĐẦU đọc khối — cả thời gian nơi gọi xử lý khối
    trước (đổi log-mel, máy bận) cũng bị tính: xử lý chậm thì FFmpeg khoẻ vẫn bị giết, «đọc quá lâu». Chỉ tính lúc chờ."""
    _ghi_wav(tmp_path / "a.wav", _giai_dieu(3, seed=9711))
    monkeypatch.setattr(tcm, "KHOI_GIAI_MA_S", 1.0)
    monkeypatch.setattr(tcm, "HAN_KHOI_S", 2.5)          # đủ cho FFmpeg khởi động + đọc một khối cả khi máy bận
    goi: list = []

    def moc():
        if threading.current_thread() is threading.main_thread():
            goi.append(1)
            if len(goi) == 2:                            # sau khối đầu: nơi gọi xử lý lâu hơn HAN_KHOI_S
                time.sleep(3.5)
    cs = tcm._dac_trung(None, str(tmp_path / "a.wav"), 0.0, 3.0, moc)
    assert abs(cs.het_s - 3.0) < 0.05 and not cs.het_file


@co_ffmpeg
def test_tieng_tre_qua_tam_do_cua_ffprobe_van_khong_som(tmp_path):
    """Tiếng trễ 5,1 s sau hình nhỏ (mkv + FLAC): ffprobe ngừng dò sau 5 s nên ``start_time`` của luồng tiếng = của file
    (0) — vòng 5 lượt đầu đọc độ trễ 0, giải mã như vòng 4: «đã tinh chỉnh» sớm đúng 5,1 s, không cờ (video bitrate cao:
    5 MB dò ≈ 1 s hình, trễ 0,3 s đã lọt). Đọc nhãn GÓI tiếng đầu."""
    clip, a, P, tre = _giai_dieu(40, seed=8111), _giai_dieu(100, seed=8112), 30.0, 5.1
    i0 = int(round((P - tre) * 22050))
    a[i0: i0 + len(clip)] = clip
    _ghi_wav(tmp_path / "clip.wav", clip)
    _ghi_wav(tmp_path / "a.wav", a)
    v = tmp_path / "v.mkv"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=gray:s=64x48:r=10:d=106", "-itsoffset", str(tre), "-i", str(tmp_path / "a.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "mpeg4", "-c:a", "flac", str(v)], check=True)
    assert tcm._tre_am(str(v), lambda: None) == pytest.approx(tre, abs=0.01)
    neo = P - tre + 0.04                                 # engine: khối 0 theo trục tiếng
    kq = tcm.tinh_chinh_dong(str(tmp_path / "clip.wav"), str(v), [(neo, 1.0)], neo + 2.5, neo + 37.5,
                             pham_vi_s=(0.0, 100.0))
    assert kq["trang_thai"] == tcm.CHUA or _gan(kq["doan"][0]["video_tu"], P, 0.05), kq["doan"]


def test_ffprobe_treo_bam_dung_hay_het_han_thi_dung_ngay(tmp_path, monkeypatch):
    """ffprobe đọc độ trễ tiếng (vòng 5) chạy bằng subprocess.run 60 s, trước lần kiểm huỷ đầu: ổ mạng/ổ ngủ không trả
    byte nào thì bấm Dừng hay hết ngân sách phải chờ tới 60 s. Nay kiểm huỷ + hạn chót mỗi 0,2 s, giết ffprobe."""
    p = tmp_path / "c.wav"
    p.write_bytes(b"")
    monkeypatch.setattr(tcm, "_lenh_ffprobe", lambda duong: [sys.executable, "-c", "import time; time.sleep(30)"])
    monkeypatch.setattr(tcm, "CHI_PHI_GIAI_MA_S", 0.0)

    class Dung(Exception):
        pass
    t = time.monotonic()

    def huy():
        if time.monotonic() - t > 0.5:
            raise Dung
    with pytest.raises(Dung):
        tcm.tinh_chinh_dong(str(p), str(p), [(0.0, 1.0)], 3.0, 27.0, kiem_huy=huy)
    assert time.monotonic() - t < 3.0
    t = time.monotonic()
    kq = tcm.tinh_chinh_dong(str(p), str(p), [(0.0, 1.0)], 3.0, 27.0, han_chot=t + 0.5)
    assert kq["ly_do"] == tcm.LY_DO_HET_GIO and time.monotonic() - t < 3.0


def test_ffprobe_khong_doc_duoc_thi_chua_tinh_chinh_khong_giai_ma(tmp_path, monkeypatch):
    """ffprobe hỏng: lượt đầu coi độ trễ là 0 và giải mã như vòng 4 (sai cả độ trễ nếu tiếng trễ). Chưa biết → CHƯA."""
    p = tmp_path / "c.wav"
    p.write_bytes(b"")
    monkeypatch.setattr(tcm, "_lenh_ffprobe", lambda duong: [sys.executable, "-c", "import sys; sys.exit(1)"])

    def khong_giai_ma(*a, **k):
        raise AssertionError("không được giải mã khi chưa biết độ trễ tiếng")
    monkeypatch.setattr(tcm, "_khoi_ffmpeg", khong_giai_ma)
    kq = tcm.tinh_chinh_dong(str(p), str(p), [(0.0, 1.0)], 3.0, 27.0)
    assert kq["trang_thai"] == tcm.CHUA and kq["ly_do"] == tcm.LY_DO_TRE_AM


def test_luat_lech_khong_dem_o_thuoc_doan_neo_khac_ke_ca_doan_khong_cham_loi():
    """Luật G (ô chắc chắn lệch đường > 0,12 s): đếm ô của đoạn chính nó hay không đoạn nào — kể cả xa lõi engine (lõi
    hẹp hơn lần dùng: chỉ đếm quanh lõi ± 3 s từng thả lại 6 kết quả sai mà tự tin, kiểm độc lập vòng 5). Không đếm ô
    thuộc đoạn neo khác (bóng của clip tự giống — B07), kể cả đoạn bị bỏ vì không chạm lõi (mảnh kia của cùng clip ngay
    cạnh dòng — một kết quả đúng thành CHƯA)."""
    def can(*lech):
        return [(0.0, 1.0, None, np.array(ds, np.int64)) for ds in lech]
    mot = [(0, 10, 40)]                                 # đoạn thô (chạm lõi) của neo 0: ô 10–40
    hai = mot + [(1, 41, 70)]                           # thêm đoạn của neo 1: ô 41–70
    assert tcm._lech_chua_giai_thich(can([20, 21, 22, 23]), mot, mot, 80)                 # trong đoạn chính nó
    assert tcm._lech_chua_giai_thich(can([60, 61, 62, 63]), mot, mot, 80)                 # không đoạn nào, xa lõi
    assert not tcm._lech_chua_giai_thich(can([20, 21, 22]), mot, mot, 80)                 # < 4 ô
    assert not tcm._lech_chua_giai_thich(can([50, 51, 52, 53], []), hai, hai, 80)         # trong đoạn neo 1
    assert not tcm._lech_chua_giai_thich(can([50, 51, 52, 53], []), mot, hai, 80)         # đoạn neo 1 không chạm lõi


def test_chuoi_lech_chi_tinh_o_ke_nhau():
    """Chuỗi ô lệch = ô KỀ NHAU (u, u + 1, …): ô không chắc chắn ở giữa làm đứt chuỗi. Bản trước nối cả các ô cách nhau
    hàng chục giây (bóng ô nhịp từng cặp, nhạc có nhịp trôi 0,3–0,9 %) thành «4 ô liền» → kết quả đúng thành CHƯA."""
    def chuoi(o, xa=None):
        return tcm._chuoi_lech(np.array(o, np.int64), np.ones(len(o), bool) if xa is None else np.array(xa)).tolist()
    assert chuoi([10, 11, 12, 13, 20]) == [10, 11, 12, 13]
    assert chuoi([10, 11, 13, 14, 15, 16]) == [13, 14, 15, 16]
    assert chuoi([250, 251, 258, 259]) == []
    assert chuoi([10, 11, 12, 13], [True, True, False, True]) == []
    assert chuoi([5, 6, 7, 8, 9]) == [5, 6, 7, 8, 9]


@pytest.mark.parametrize("phia, c_tho", [("dau", 1.0), ("cuoi", 59.0)])
def test_mep_khong_chot_ve_bien_khi_ca_cua_so_o_ngoai(monkeypatch, phia, c_tho):
    def tuong_quan(cl, vi, dau, k, tu, den):
        muc = 0.0 if tu <= c_tho <= den else 1.0
        return np.linspace(tu, den, 64), np.full(64, muc)

    monkeypatch.setattr(tcm, "_tuong_quan_khung", tuong_quan)
    monkeypatch.setattr(tcm, "_clip_lang_ngoai", lambda *a: None)
    kq = tcm._mep(None, None, 100.0, 1.0, c_tho, phia, (0.0, 60.0, True, True), (1.0, 59.0))
    assert kq == (c_tho, "tho")


def test_o_ngoai_mep_dau_toan_nan_chi_danh_dau_mep_dau(monkeypatch):
    clip = _am(120, 7201)
    bat_dau = 50.53
    video = _chen(_am(160, 7202), _cat(clip, 30.37, 90.81), bat_dau)
    do_goc = tcm._do_duong
    o_ngoai = []

    def do_duong(cl, vi, dau, k, u, **kw):
        s, r, cc = do_goc(cl, vi, dau, k, u, **kw)
        if 0 < len(u) <= tcm.SAT_MEP_O and u[-1] < bat_dau:
            o_ngoai.extend(u)
            s[:] = np.nan
        return s, r, cc

    monkeypatch.setattr(tcm, "_do_duong", do_duong)
    kq = _chay(clip, video, [(bat_dau - 30.37, 1.0)], bat_dau + 3.0, bat_dau + 57.4)
    assert kq["trang_thai"] == tcm.DA, kq["ly_do"]
    assert o_ngoai
    assert kq["cham_gioi_han"] is True
    assert (kq["cham_dau"], kq["cham_cuoi"]) == (True, False)
