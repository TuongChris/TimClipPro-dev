# -*- coding: utf-8 -*-
"""Tinh chỉnh mốc từng giây (P-8, thử nghiệm) — đo lại MỘT dòng kết quả engine bằng độ giống phổ từng giây.

Engine (audfprint) chỉ cho «lõi» [vung_khop_s, end_s], bị cắt 5 % mỗi đầu mảnh, và không biết giây nào trong đoạn thật
sự trùng. Bước này chạy SAU khi engine đã chọn dòng (``Engine._tinh_chinh_ket_qua``): không tạo/bỏ dòng, không đổi số nào
của engine — chỉ trả các đoạn dùng thật (mép tới khung 11,6 ms), chỗ cắt/tua lùi giữa chúng và độ giống từng giây; không
chắc thì «chưa tinh chỉnh» (``CHUA``) kèm lý do. Hàm thuần: numpy + FFmpeg (tiến trình con), không ghi file, không in,
không đổi biến môi trường; cùng đầu vào → cùng kết quả (trừ ``thoi_gian_s``). Nguồn gốc: «Cách C» của nghiên cứu 14/11
(``tools/khop_tung_giay/cach_c/tuong_dong.py``, ``docs/KHOP_TUNG_GIAY.md``) + các sửa của phản biện (H3, H1b, H4, H2a), của
bộ kiểm ngoài mẫu vòng 1 (A03, A05), của phản biện vòng 2 (N.., «vòng 3» dưới đây), của review trước khi gộp
(«vòng 4») và của vòng kiểm độc lập sau đó («vòng 5»).

1. Cửa sổ — không bao giờ giải mã cả clip. Biên = 30 s + 10 % độ dài lõi. Clip: hợp theo mọi neo của
   [(vung − dau)/k − biên, (end − dau)/k + biên]; video: [vung − biên − 45 s, end + biên + 45 s] ∩ phạm vi đã quét.
   MỘT tiến trình FFmpeg mỗi cửa sổ (tua một lần: các khối nối liền từng mẫu), đọc dần từng khối ≤ 2 phút →
   mono float32 11025 Hz, mỗi khối đổi ngay sang log-mel 40 dải 300–5000 Hz (khung 512, bước 128, sàn −60 dB) lưu
   float32; giữa hai khối kiểm huỷ + hạn chót, và trong lúc chờ FFmpeg một luồng canh kiểm mỗi 0,2 s (vòng 4: FFmpeg im
   lặng — ổ cứng bận — thì bấm Dừng phải chờ tới 2 phút); khối không về trong 2 phút thì giết FFmpeg. Tua thô tới 1 s
   TRƯỚC rồi bỏ phần thừa theo nhãn thời gian ở đầu ra, ``aresample=async=1`` lấp khe nhãn thời gian như trình phát: mẫu
   đầu đúng giây đã tua — AAC (m4a/mp4) từng trễ 1 khung 1024 mẫu (≤ 46 ms), nay 0; Opus trong webm còn ~6 ms (dưới một
   khung). Không ``first_pts=0`` (vòng 4): file đổi tần số mẫu/số kênh giữa chừng (bản ghi .ts) làm FFmpeg dựng lại bộ
   lọc, áp lại từ đầu cửa sổ — phần sau chỗ đổi trễ đúng (chỗ đổi − đầu cửa sổ). Vì thế không gì đệm im lặng trước mẫu
   tiếng đầu: video có luồng tiếng bắt đầu SAU đầu file (bản ghi, bản cắt chép luồng: hình có trước tiếng — ffprobe:
   nhãn GÓI tiếng đầu, vì ``start_time`` của luồng chỉ là của file khi ffprobe dừng dò trước gói đó — video bitrate cao)
   thì cửa sổ video bắt đầu sau chỗ tiếng bắt đầu ≥ 1 s (vòng 5: cửa sổ ở 0 có mẫu tiếng đầu mang nhãn giây 0 — mọi mốc
   sớm đúng độ trễ, không cờ); lần dùng bắt đầu trong khoảng bỏ qua → cờ chạm giới hạn; không đọc được ffprobe → CHUA.
   Bộ đọc tiêm vào (``doc_pcm``) gọi theo khối: khối trả thiếu = hết file, không bao giờ xin mẩu < 50 ms (vòng 2: xin 1–26 ms, FFmpeg trả 0 mẫu mãi → lặp vô hạn
   tới hạn chót). Đo trên PC2 (opus 64 kbps, một neo): lõi 10 phút 3,0 s / RAM đỉnh 95 MB; 1 giờ 21 s / 183 MB; 2 giờ
   42 s / 286 MB (5 neo trôi: 49 s); khe dài nhất giữa hai lần kiểm huỷ ≤ 0,35 s. Có hạn chót mà ước tính (2,4 ms mỗi
   giây âm thanh của hai cửa sổ + 0,3 ms mỗi giây lõi cho mỗi neo thêm) vượt phần còn lại: CHUA ngay, không giải mã (để
   ngân sách cho dòng sau). Lõi > 2 giờ 30 phút: CHUA.
2. Độ giống của ô video u (giây [u, u + 1)) theo neo (dau, k): Pearson giữa miếng 3 s của clip quanh giây
   c = (u + 0,5 − dau)/k và miếng video cùng căn chỉnh, sau khi trừ trung bình TỪNG DẢI của mỗi miếng; đỉnh trong ±0,1 s.
   Căn chỉnh từng neo: vòng đầu tìm ±0,5 s (audfprint in mốc 1 số lẻ: neo lệch tới 0,1 s), khớp thẳng bền độ lệch đỉnh
   theo giây clip → sửa dau và k (bám độ trôi tốc độ), tối đa 3 vòng. Neo đã sửa trùng một căn chỉnh đã có (lệch ≤ 0,1 s
   trên cả cửa sổ clip: các neo engine tách vì độ trôi hội tụ về cùng đường) thì bỏ — vòng 2: hai neo trùng nhau làm
   «lặp y hệt» giả và tốn thêm 3–5 s mỗi neo ở lõi 2 giờ. Phần dư của độ lệch đỉnh vòng đầu so với đường cuối (MAD) lớn
   mà HAI mảnh song song cùng tốc độ giải thích được (nhảy/tua lùi 0,1–0,5 s trong MỘT neo — engine gộp hai căn chỉnh
   cách < 1 s): tách thành hai căn chỉnh → hai đoạn + chỗ cắt dài 0 (vòng 2: nhảy 0,3 s thành MỘT đoạn với k giả
   0,9964). Không tách được (mảnh < 10 ô chắc chắn, mảnh lệch là số ít nên MAD nhỏ, tốc độ khác > 1 % bị chặn sửa) mà
   ≥ 4 ô chắc chắn KỀ NHAU vẫn lệch đường cuối > 0,12 s mà không đoạn thô nào của neo KHÁC (kể cả đoạn không chạm lõi)
   giải thích: clip có ở đó nhưng ở căn chỉnh không đoạn nào báo → CHUA (vòng 5: một đoạn ánh xạ lệch 0,2–0,4 s, hay mảnh sau bị bỏ còn mép lấn
   0,5 s vào nó, mép sớm tới 5,5 s, không cờ). Ô lệch nằm trong đoạn của neo khác (bóng của clip tự giống: B07; mảnh
   kia của cùng clip ngay cạnh dòng) không tính; mảnh lệch < 4 ô (mảnh xa < ~4,5 s, lần dùng < ~13 s) lọt luật này.
   Miếng không đổi theo thời gian (im lặng tuyệt đối, tiếng đều: phương sai mỗi phần tử < SAN_PHUONG_SAI) không
   mang thông tin: video không đổi mà clip có thay đổi → 0 (tiếng clip không có ở đó); clip không đổi → không đo được
   (trung tính: không bao giờ là bằng chứng có hay vắng).
3. Ngưỡng — đường nền tại chỗ = CÙNG giây clip, video lệch 6 khoảng LECH_NEN_S (bỏ khoảng trùng độ lệch giữa hai neo).
   T = p99(nền) + 15 điểm %; T > 95 % → CHUA. Mức «clip CÓ MẶT» của một ô (dưới tiếng đè, dùng cho nối khe và kiểm mép):
   clip không tự giống → ≥ p99 nền chung; clip tự giống ở độ lệch L (nhạc có nhịp: bội ô nhịp; vòng lặp — đỉnh tương quan
   từng khung, L 1–16 s) → hơn «nền TẠI CHỖ» = độ giống lớn nhất của CHÍNH các ô video đó với các giây clip khác (lệch
   LECH_NEN_S và ±L). Tiếng đè làm nền tại chỗ giảm cùng căn chỉnh thật, còn p99 chung của nhạc có nhịp bị khoảng lệch
   trùng vạch ô nhịp đẩy lên (B03: +19,1 s = 8,99 ô nhịp ở 113 BPM, p99 50,9 % thay vì 33,6 %). Ngược lại với clip không tự
   giống, nền tại chỗ thiếu các độ lệch cùng lưới nốt nên thấp giả (A12, B19: ô ngoài đoạn 0,10–0,18 «hơn» nền 0,01–0,10).
   Biên đo trong mẫu: ``tools/khop_tung_giay/san_pham/kiem_trong_mau.py``.
4. Ô thuộc neo ≥ T (giữ neo của ô trước nếu nó còn ≥ T — trừ khi neo tốt nhất là căn chỉnh GẦN, cách < 1 s, mảnh kia của
   một bước nhảy nhỏ, hơn nó quá 5 điểm; không thì neo giống nhất). Đoạn = chuỗi ô cùng neo ≥ 3 ô. Hai chuỗi CÙNG neo được
   nối khi MỌI ô đo được của khe còn «có mặt» nếu khe ≤ 5 ô, hay ≥ 3/4 số ô nếu khe dài hơn: tiếng ĐÈ giữ ô trên nền,
   tiếng THAY kéo ô xuống bằng nền (vòng 2: thay 3–6 s bị nối qua, «một đoạn liền» với độ giống thấp nhất 0 %). Khe chỉ
   gồm ô không đo được (clip tự im lặng) luôn nối (vòng 2: im lặng ≥ 9 s của chính clip → CHƯA). Bỏ đoạn không chạm lõi.
   Neo đổi giữa chừng (tua lùi/phát lại hay cắt rồi chèn mà engine gộp MỘT dòng nhiều neo — H1b) → nhiều đoạn,
   ``cho_cat`` giữa chúng (``clip_bo_den < clip_bo_tu`` = clip lùi lại). Một neo KHÁC (không gần) cũng ≥ T trên ≥ 80 % số
   ô của một đoạn → vòng lặp y hệt, CHUA. Trên một đoạn và khe tới đoạn sau, căn chỉnh lệch ±L (L: độ lệch clip tự giống)
   hơn MỌI neo ≥ 10 điểm (và ≥ T) trên ≥ 3 ô liền → video phát CHỖ KHÁC của clip ở đó (DJ lặp ô nhịp), CHUA (vòng 2:
   12,75 s mang giây clip sai).
5. Mép tới khung: tương quan từng khung dọc căn chỉnh (trừ trung bình từng dải của CẢ cửa sổ, không phụ thuộc vị trí
   mép) trong ±2,5 s quanh mép thô; phân bố «trong» (≤ 10 s khung sâu trong đoạn) và «ngoài» (cùng khung, video lệch)
   theo Laplace; mép = cực đại tổng tích luỹ log tỉ số hợp lẽ, cần ≥ 30. Chỉ chốt về đầu/cuối clip khi mép đo được nằm
   trong 0,1 s quanh đó (H4). Khung lạ với CẢ hai phân bố (cách cả hai trung vị > 4 lần độ lệch) xếp phía ngoài — mốc là
   ước lượng PHÍA TRONG (A03). Đi từ mép ra ngoài, bằng chứng lại tăng ≥ 5 lần ngưỡng sau một chỗ trũng nông hơn 3 lần
   mức tăng = clip còn tiếp sau một chỗ vấp ngắn (tiếng lạ, rớt tiếng): mép «thô» (vòng 4: mép bám chỗ vấp, sớm 1–2 s mà
   vẫn «đo được»). Không tìm được mép trong cửa sổ («thô») mà phía ngoài là im lặng của chính clip ≥ 0,25 s
   tới hết cửa sổ: mép = chỗ clip bắt đầu/hết tiếng, coi như chạm giới hạn (``clip_lang``: không đo được phần im lặng có
   được dùng hay không). Mép «thô» còn lại → CHUA (vòng 2: tiếng đè đầu đoạn → mép thô trễ 10 s mà vẫn ĐÃ).
   Khoảng lặng: video im lặng (mọi dải ≤ sàn + 3 dB và ≥ 50 dB dưới p99 của CHÍNH đoạn đang xét trong video)
   liền ≥ 0,25 s trong khi clip ở cùng căn chỉnh có tiếng (một dải ≥ sàn + 30 dB) ở ≥ nửa số khung = clip vắng chắc chắn
   (tiếng đè chỉ CỘNG năng lượng): tách đoạn ở đó, mép = biên khoảng lặng (``im_lang``) — A05. Mức tham chiếu lấy trong
   đoạn chứ không từ nội dung to bên cạnh (vòng 2: clip chèn nhỏ −36 dB, đoạn khẽ thêm −25 dB thành «khoảng lặng» bịa).
6. Bằng chứng ở mép (vòng 3): mỗi mép đo được (``bac_thang``) phải có bằng chứng clip VẮNG phía ngoài — ≤ 4 ô sát mép có
   miếng nằm trọn phía ngoài (tới 10 s, hay tới đoạn kề), theo neo của chính đoạn: ≥ 3/4 số ô «có mặt» (nhạc tự giống:
   hơn nền tại chỗ ≥ 5 điểm) → tiếng đè chứ không phải hết đoạn → CHUA. Khe giữa hai đoạn (cùng hay khác neo) dài > 1 s
   là chỗ cắt chỉ khi ô sát cả hai mép vắng clip theo neo của TỪNG bên, và các ô nằm trọn trong khe không «có mặt» theo
   NEO NÀO trong hai neo ở ≥ 1/2 số ô (tiếng đè đúng chỗ tua lùi: mỗi neo chỉ có mặt ở một phía chỗ nối) — vòng 2: tiếng
   đè quanh chỗ tua lùi thành «chỗ cắt» 16 s bịa; mép bậc thang ở chỗ tiếng đè đầu đoạn hết. Một nốt nền trùng tình cờ
   chỉ làm 1–2 ô kề nhau vượt p99. Mép NGOÀI cùng sát giới hạn đo (đầu cửa sổ phân tích, cuối phần đã quét) không còn ô
   nào nằm trọn phía ngoài TRONG phần video đã giải mã để kiểm → cờ chạm giới hạn (vòng 4: tiếng đè bắt đầu 2–3 s trước
   cuối phần đã quét → mép sớm 13 s mà không cờ; vòng 5: ô có miếng vượt phần đã giải mã cho độ giống «không đo được» —
   từng bị coi là clip vắng).
7. Lưới an toàn: các đoạn + chỗ cắt + khoảng lặng đã đo để hở > 5 s của lõi engine → CHUA: neo thiếu, bóng của vòng lặp
   (H2b), nhạc đè quá to.
Giới hạn: dòng chỉ có MỘT neo là bóng của vòng lặp y hệt (H2a) cho mốc video đúng nhưng giây clip lệch bội chu kỳ —
engine không gọi bước này cho dòng ``moc_mo_ho``. Độ phân giải theo ô 3 s: tiếng THAY < ~2,5 s giữa đoạn bị nối qua (một
đoạn liền); khe < 3 s ngay chỗ nối hai neo không có ô nằm trọn trong khe để kiểm — tiếng đè ngắn đúng chỗ nối thành chỗ
cắt ngắn bịa; tiếng đè TO HƠN clip ≥ 6 dB kéo ô xuống ngang nền: không phân biệt được với tiếng thay (thành chỗ cắt);
to hơn ≥ 3 dB và dài ≥ 10 s ở mép ngoài thì ô phía ngoài cũng «vắng»: mép vào trong tới hết đoạn đè, không cờ.
Tiếng đè ≤ ~4 s đúng ở mép ngoài một lần dùng có thể đẩy mép vào trong tới độ dài tiếng đè; chỗ vấp ngắn sát mép mà
sau nó clip chỉ còn < 0,3 s (nhạc có nhịp: < 0,6 s) vẫn kéo mép vào trong tới ~0,6 s (~0,9 s). Mảnh ngắn (< 10 ô chắc
chắn) giữ k của engine: k lệch 0,2–0,3 % làm khung hai đầu mảnh ~10 s lệch quá nửa khung, mép bị kéo vào ~1 s. CLIP
có luồng tiếng bắt đầu trễ (hiếm: clip trong kho thường chỉ có tiếng): giây clip có thể lệch đúng độ trễ đó. Video có
tiếng trễ > ~0,45 s: lần dùng trong khối đầu của engine (mốc engine theo trục tiếng) thường CHUA. Nhạc 4 phách đều nối
khớp nhịp với bài bên cạnh (DJ): đoạn có thể lấn sang bài kia, mép «đầu/cuối clip» không cờ; giọng nói đè lên nhạc nhiều
trầm (năng lượng dưới 300 Hz) mạnh hơn clip TRONG dải 300–5000 Hz dù nhỏ hơn cả dải: chỗ cắt bịa, mép lệch tới ~5 s;
chỗ nối sau khi tách hai mảnh (nhảy nhỏ) có thể lệch 0,15–0,5 s — ba lớp này đo trên nhạc tổng hợp (kiểm độc lập vòng
5). Mẩu NGOÀI cùng < 1 s sau một khoảng lặng (tắt tiếng sát mép) bị bỏ như mọi mẩu ngắn: lần dùng ngắn đi tới ~1,25 s,
mép = biên khoảng lặng. Nhảy 0,5–1 s trong MỘT neo
(engine gộp) không thấy được ở vòng tìm ±0,5 s: phần sau thành lỗ hổng của lõi → CHUA. «Tắt tiếng» còn tiếng ồn trên sàn
−57 dB không nhận là khoảng lặng. Nốt nền TRÙNG tần số với nốt clip ngay sau mép (cùng nội dung) vẫn kéo mép ra tới hết
nốt đó.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import NamedTuple

import numpy as np

CHUA = "chua_tinh_chinh"
DA = "da_tinh_chinh"
PHIEN_BAN = 1

SR = 11025
N_FFT, HOP = 512, 128
FPS = SR / HOP                          # 86,13 khung/giây
TAM_KHUNG_S = N_FFT / 2 / SR            # khung f của cửa sổ bắt đầu ở t0 có tâm ở t0 + f/FPS + TAM_KHUNG_S
N_MEL, FMIN, FMAX = 40, 300.0, 5000.0
SAN_DB = -60.0
KHOI_GIAI_MA_S = 120.0                  # giây PCM mỗi khối đọc (giữa hai khối: kiểm huỷ + hạn chót)
HAN_KHOI_S = 120.0                      # FFmpeg không trả xong một khối trong chừng này: coi như treo
CANH_S = 0.2                            # luồng canh: kiểm huỷ + hạn chót mỗi chừng này trong lúc chờ FFmpeg
DU_CUOI_S = 0.05                        # phần cửa sổ còn lại ngắn hơn: không xin nữa; khối thiếu hơn: hết file
KHOI_KHUNG = 2048                       # khung mỗi lượt FFT (giới hạn bộ nhớ tạm)
KHOI_O = 256                            # ô mỗi lượt đo (giới hạn bộ nhớ tạm; kiểm huỷ mỗi lượt)

F_MIENG = int(round(3.0 * FPS))         # miếng 3 s
W_S = 0.1                               # tìm đỉnh ±0,1 s quanh căn chỉnh (đo và đường nền)
W_BAT_S = 0.5                           # vòng căn chỉnh đầu: neo engine lệch tới ±0,1 s (audfprint in 1 số lẻ) + trôi
LECH_NEN_S = (7.3, -11.9, 19.1, -23.7, 31.3, -41.7)
BIEN_NEN_S = 45.0
BIEN_CO_DINH_S, BIEN_TY_LE = 30.0, 0.10
LOI_TOI_DA_S = 9000.0
CHI_PHI_GIAI_MA_S = 0.0024              # ước giây máy cho mỗi giây âm thanh của hai cửa sổ (PC2 đo 2,1–2,7 ms)
CHI_PHI_NEO_S = 0.0003                  # ... cộng thêm mỗi neo sau neo đầu, mỗi giây lõi

SAN_PHUONG_SAI = 1e-4                   # phương sai mỗi phần tử (log10², ≈ (0,1 dB)²) dưới mức này: miếng không đổi

LE_NGUONG = 0.15                        # ngưỡng = p99 đường nền + 15 điểm %
NGUONG_TOI_DA = 0.95                    # ngưỡng cao hơn thế = nền giống như «trong»: không phân biệt được
CHAY_TOI_THIEU = 3                      # ô
NOI_CUNG_NEO_S = 5                      # khe ≤ 5 ô đo được: nối khi MỌI ô còn «có mặt»
KHE_DAI_TY_LE = 0.75                    # khe dài hơn: nối khi ≥ 3/4 số ô còn «có mặt»
GIU_NEO = 0.05                          # giữ neo của ô trước khi nó kém neo tốt nhất không quá 5 điểm
MO_HO_TY_LE = 0.8
GAN_S = 1.0                             # hai căn chỉnh cách < 1 s: cùng một lần dùng (bước nhảy nhỏ), không phải bóng
HO_LOI_TOI_DA_S = 5.0
VONG_CAN_CHINH = 3
SUA_K_TOI_DA = 0.01
MAD_THANG_S = 0.01                      # phần dư (MAD) của độ lệch đỉnh quanh đường căn chỉnh lớn hơn: thử hai mảnh
BAC_TOI_THIEU_S = 0.12                  # hai mảnh lệch nhau ít hơn: một đường (sai số ánh xạ ≤ 0,12 s)
MANH_TOI_THIEU = 10                     # ô (và ≥ 5 s) mỗi mảnh
BAC_O_LIEN = 4                          # ≥ chừng này ô chắc chắn liền nhau lệch đường cuối > BAC_TOI_THIEU_S: ánh xạ sai
TRE_AM_TOI_DA_S = 0.02                  # luồng tiếng bắt đầu sau đầu file hơn chừng này: cửa sổ video tránh phần đầu
FFPROBE_TOI_DA_S = 60.0                 # ffprobe không xong trong chừng này: coi như không đọc được

NEN_TAI_CHO_LE = 0.05                   # nhạc tự giống: «có mặt» = hơn nền tại chỗ ≥ 5 điểm
SAU_NGOAI_S = 10.0                      # kiểm có mặt phía ngoài mép: tới 10 s ...
SAT_MEP_O = 4                           # ... trên ≤ 4 ô sát mép nhất (khe giữa hai neo: phía xa là phần của neo kia)
CO_MAT_TY_LE = 0.75                     # ≥ 3/4 số ô sát mép đạt mức «có mặt» (một nốt trùng tình cờ: 1–2 ô kề nhau)
KHE_NOI_S = 1.0                         # khe ≤ 1 s giữa hai đoạn: chỗ nối (tua lùi/nhảy), không cần bằng chứng
LAP_R_TOI_THIEU = 0.25                  # tương quan tự thân từng khung tối thiểu để thử độ lệch L của vòng lặp
LAP_L_S = (1.0, 16.0)
LAP_SO_DINH = 6
LAP_HON = 0.10                          # căn chỉnh lệch L hơn neo ≥ 10 điểm ...
LAP_O_LIEN = 3                          # ... trên ≥ 3 ô liền

NUA_CUA_SO_MEP_S = 2.5
SAU_MEP_S = 10.0                        # phân bố «trong» đo trên ≤ 10 s khung sâu trong đoạn
KHUNG_PHAN_BO = 20
SAN_LECH = 0.03
CHENH_PHAN_BO = 0.15                    # «trong» phải hơn «ngoài» ít nhất chừng này, không thì không tinh mép
BANG_CHUNG_MEP = 30.0                   # log tỉ số hợp lẽ tối thiểu để nhận một mép trong cửa sổ
LA_K = 4.0                              # khung cách cả hai trung vị > 4 lần độ lệch: «lạ», xếp phía ngoài mép
CHOT_BIEN_S = 0.1

IM_TREN_SAN = 0.3                       # khung «im lặng»: mọi dải ≤ sàn + 3 dB ...
IM_DUOI_DINH = 5.0                      # ... và ≥ 50 dB dưới p99 của chính đoạn đang xét trong video
CO_TIENG = 3.0                          # khung clip «có tiếng»: một dải ≥ sàn + 30 dB
IM_TOI_THIEU_S = 0.25                   # khoảng lặng ngắn hơn: không tách đoạn
DOAN_TOI_THIEU_S = 1.0                  # mẩu ngắn hơn còn lại sau khi tách ở khoảng lặng: bỏ
GIOI_HAN = ("gioi_han", "clip_lang")    # mép chạm giới hạn đo được: mép thật có thể nằm ngoài

LY_DO_HET_GIO = "Hết thời gian dành cho bước tinh chỉnh — giữ mốc của lượt quét."
LY_DO_KHONG_KIP = "Không đủ thời gian còn lại để tinh chỉnh dòng này — giữ mốc của lượt quét."
LY_DO_QUA_DAI = "Đoạn khớp dài hơn 2 giờ 30 phút — chưa hỗ trợ tinh chỉnh."
LY_DO_HO_LOI = "Chưa tinh chỉnh được: phần lượt quét đã khớp không giải thích hết bằng đoạn đo được."
LY_DO_THIEU_NEO = "Thiếu mốc của lượt quét — không tinh chỉnh được."
LY_DO_THIEU_AM = "Không đọc được đủ âm thanh quanh kết quả (file clip hoặc video ngắn hơn dự kiến)."
LY_DO_NEN_IT = ("Đoạn khớp quá ngắn (hoặc sát đầu/cuối video) để đo độ giống so sánh — giữ mốc của lượt quét.")
LY_DO_KHONG_THAY = "Không đo được đoạn giống rõ rệt quanh mốc của lượt quét — giữ mốc của lượt quét."
LY_DO_MO_HO = ("Âm thanh lặp y hệt — nhiều mốc giải thích đoạn như nhau, không xác định được giây clip: giữ mốc của "
               "lượt quét.")
LY_DO_LAP_CHO_KHAC = ("Âm thanh lặp — một phần đoạn giống chỗ KHÁC của clip hơn (vòng lặp, DJ lặp ô nhịp), không "
                      "xác định được giây clip: giữ mốc của lượt quét.")
LY_DO_TUONG_PHAN = ("Âm thanh quanh kết quả giống nhau ở mọi độ lệch (nhạc lặp, nền đều) — không phân biệt được "
                    "đoạn dùng thật.")
LY_DO_MEP = ("Không đo được mép đoạn (tiếng đè hoặc âm thanh giống nhau quanh mép) — giữ mốc của lượt quét.")
LY_DO_CON_DUOI_DE = ("Tiếng clip có vẻ vẫn còn dưới tiếng đè ở mép đoạn hay chỗ cắt — không đo được mép thật: giữ mốc "
                     "của lượt quét.")
LY_DO_TRE_AM = "Không đọc được thông tin luồng tiếng của video (ffprobe) — giữ mốc của lượt quét."
LY_DO_LECH_NEO = ("Một phần đoạn khớp lệch khỏi mốc của lượt quét (chỗ nhảy/tua nhỏ hay tốc độ khác) mà không đo tách "
                  "được — giữ mốc của lượt quét.")


class _HetGio(Exception):
    pass


class _CuaSo(NamedTuple):
    """Một cửa sổ âm thanh đã giải mã: log-mel X (khung × dải, float32), giây của mẫu đầu, giây sau mẫu cuối, file
    đã hết trước cuối cửa sổ xin, trung bình từng dải trên cả cửa sổ, sàn log10 (p99 − 60 dB: mức của im lặng)."""
    X: np.ndarray
    t0: float
    het_s: float
    het_file: bool
    tb: np.ndarray
    san: float


# ---------------------------------------------------------------------------------------------- giải mã + đặc trưng

def _lenh_ffmpeg(duong: str, tu: float, dai: float) -> list:
    # tua thô tới 1 s TRƯỚC «tu», rồi «-ss» phía đầu ra bỏ phần thừa theo nhãn thời gian: mẫu đầu ra đúng giây «tu» kể cả
    # khi bộ giải mã bỏ khung đầu sau khi tua (AAC trong m4a/mp4 trễ tới 1024 mẫu = 46 ms, nay 0; Opus trong webm ~6 ms
    # — FFmpeg 9.0.1). Không tua thô khi tho = 0: «-ss 0» ở đầu vào làm AAC bỏ khung đầu (+46 ms). Không first_pts=0:
    # đổi tần số mẫu/số kênh giữa file làm FFmpeg dựng lại bộ lọc và áp lại từ đầu cửa sổ (phần sau chỗ đổi bị trễ).
    tho = max(0.0, tu - 1.0)
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", *(["-ss", f"{tho:.6f}"] if tho else []),
            "-i", duong, "-ss", f"{tu - tho:.6f}", "-t", f"{dai:.6f}", "-map", "0:a:0", "-af", "aresample=async=1",
            "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]


def _khoi_ffmpeg(duong: str, tu_s: float, den_s: float, moc=None):
    """MỘT tiến trình FFmpeg cho cả cửa sổ [tu_s, den_s) — một lần tua, các khối nối liền từng mẫu — đọc dần từng khối
    ≤ KHOI_GIAI_MA_S giây PCM. Sinh (mẫu float32, giây của mẫu đầu khối). Luồng canh gọi ``moc`` (kiểm huỷ + hạn chót)
    mỗi CANH_S giây suốt lúc FFmpeg chạy: ``moc`` ném lỗi (huỷ, hết hạn) hay một khối không về trong HAN_KHOI_S thì giết
    FFmpeg, lỗi của ``moc`` ném lại ở luồng gọi. Lỗi FFmpeg → RuntimeError một câu tiếng Việt ngắn (engine hiện nguyên văn
    ở giao diện + CSV phụ); chữ FFmpeg (tiếng Anh, có đường dẫn) chỉ ở ``__cause__`` cho nhật ký."""
    ten = os.path.basename(duong)
    tu = max(0.0, round(tu_s * SR) / SR)
    try:
        p = subprocess.Popen(_lenh_ffmpeg(duong, tu, den_s - tu), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        raise RuntimeError(f"Không chạy được FFmpeg để đọc «{ten}» — giữ mốc của lượt quét.") from e
    loi: list = []
    doc_loi = threading.Thread(target=lambda: loi.append(p.stderr.read()), daemon=True)
    doc_loi.start()
    giet: list = []                                     # vì sao đã giết FFmpeg: ngoại lệ của ``moc``, hay "lau"
    xong = threading.Event()
    cho_tu: list = [None]                               # lúc bắt đầu chờ khối hiện tại (None: không chờ FFmpeg)

    def canh() -> None:
        while not xong.wait(CANH_S):
            try:
                if moc is not None:
                    moc()
                c = cho_tu[0]
                if c is None or time.monotonic() - c <= HAN_KHOI_S:
                    continue
                giet.append("lau")
            except BaseException as e:  # noqa: BLE001 — huỷ/hết hạn: giết FFmpeg, luồng gọi ném lại đúng lỗi đó
                giet.append(e)
            p.kill()
            return

    luong_canh = threading.Thread(target=canh, daemon=True)
    luong_canh.start()
    try:
        t, can = tu, 4 * int(round(KHOI_GIAI_MA_S * SR))
        while True:
            cho_tu[0] = time.monotonic()
            b = p.stdout.read(can)
            cho_tu[0] = None                            # nơi gọi xử lý khối (log-mel, máy bận): không tính vào hạn
            if giet:
                break
            n = len(b) // 4
            if n:
                yield np.frombuffer(b, dtype=np.float32, count=n), t
                t += n / SR
            if len(b) < can:
                break
        if not giet:
            try:
                p.wait(timeout=30.0)
            except subprocess.TimeoutExpired:
                giet.append("lau")
        if giet:
            if isinstance(giet[0], BaseException):
                raise giet[0]
            raise RuntimeError(f"FFmpeg đọc «{ten}» quá lâu — giữ mốc của lượt quét.")
        doc_loi.join(timeout=5.0)
        if p.returncode:
            chu = (loi[0] if loi else b"").decode("utf-8", "replace").strip()[-300:]
            raise RuntimeError(f"FFmpeg không đọc được «{ten}» (file mất, đang bị khoá, hỏng hoặc không có tiếng) — giữ "
                               "mốc của lượt quét.") from RuntimeError(chu)
    finally:
        xong.set()
        if p.poll() is None:
            p.kill()
        p.wait()
        p.stdout.close()
        doc_loi.join(timeout=1.0)                       # FFmpeg đã chết: ống stderr hết ngay
        if not doc_loi.is_alive():
            p.stderr.close()
        luong_canh.join(timeout=1.0)


def _lenh_ffprobe(duong: str) -> list:
    # nhãn GÓI tiếng đầu: start_time của luồng chỉ là start_time của file khi ffprobe dừng dò (5 MB / 5 s) trước gói đó
    return ["ffprobe", "-v", "error", "-select_streams", "a:0", "-read_intervals", "%+#1", "-show_entries",
            "packet=pts_time:stream=start_time:format=start_time", "-of", "json", "-i", duong]


def _tre_am(duong: str, moc) -> float | None:
    """Giây luồng tiếng (a:0) bắt đầu SAU đầu file theo trục thời gian trình phát: max(``start_time`` của luồng, nhãn gói
    tiếng đầu) − ``start_time`` của file (bản ghi, bản cắt chép luồng: hình có trước tiếng). File chỉ có tiếng: 0. None =
    không đọc được (ffprobe hỏng, không có luồng tiếng, quá FFPROBE_TOI_DA_S). Kiểm huỷ + hạn chót (``moc``, ném lỗi đi
    thẳng ra ngoài, ffprobe bị giết) mỗi CANH_S trong lúc chờ."""
    try:
        p = subprocess.Popen(_lenh_ffprobe(duong), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        return None
    han = time.monotonic() + FFPROBE_TOI_DA_S
    try:
        while True:
            try:
                ra = p.communicate(timeout=CANH_S)[0]
                break
            except subprocess.TimeoutExpired:
                moc()
                if time.monotonic() > han:
                    return None
    finally:
        if p.poll() is None:
            p.kill()
            p.communicate()
    if p.returncode:
        return None

    def giay(x):
        return float(x) if x not in (None, "N/A") else None
    try:
        j = json.loads(ra or b"{}")
        moc_tieng = [giay(j["streams"][0].get("start_time")), *(giay(g.get("pts_time")) for g in j.get("packets", [])[:1])]
        f0 = giay(j.get("format", {}).get("start_time")) or 0.0
        return max(0.0, max((x for x in moc_tieng if x is not None), default=f0) - f0)
    except (ValueError, LookupError, TypeError):
        return None


def _doc_pcm_ffmpeg(duong: str, tu_s: float, dai_s: float) -> tuple:
    """Đọc trọn [tu_s, tu_s + dai_s) bằng một tiến trình FFmpeg: (mẫu float32 mono 11025 Hz, giây của mẫu đầu). Cho công
    cụ kiểm; đường chính đọc theo khối (``_khoi_ffmpeg``)."""
    khoi = [x for x, _ in _khoi_ffmpeg(duong, tu_s, tu_s + dai_s)]
    return (np.concatenate(khoi) if khoi else np.zeros(0, np.float32)), max(0.0, round(tu_s * SR) / SR)


def _khoi_doc(doc, duong: str, tu_s: float, den_s: float):
    """Bộ đọc tiêm vào (``doc_pcm``), gọi theo khối ≤ KHOI_GIAI_MA_S. Dừng khi một khối trả thiếu > DU_CUOI_S hay 0 mẫu
    (hết file — kể cả cửa sổ xin quá cuối file vài ms), sau khối cuối (thiếu vài mẫu vẫn là hết cửa sổ), và không bao
    giờ xin phần còn lại < DU_CUOI_S (vòng 2: xin 1–26 ms, FFmpeg trả 0 mẫu, vị trí không tiến → lặp vô hạn)."""
    vi_tri, t0, so_mau = tu_s, None, 0
    while den_s - vi_tri >= DU_CUOI_S:
        dai = min(KHOI_GIAI_MA_S, den_s - vi_tri)
        x, tu_thuc = doc(duong, vi_tri, dai)
        x = np.asarray(x, dtype=np.float32).reshape(-1)
        if t0 is None:
            t0 = float(tu_thuc)
        if len(x):
            yield x, float(tu_thuc)
        so_mau += len(x)
        if not len(x) or len(x) < (dai - DU_CUOI_S) * SR or dai < KHOI_GIAI_MA_S:
            return
        vi_tri = t0 + so_mau / SR


def _bo_loc_mel() -> np.ndarray:
    f = np.fft.rfftfreq(N_FFT, 1.0 / SR)

    def mel(hz):
        return 2595.0 * np.log10(1.0 + hz / 700.0)
    diem = 700.0 * (10 ** (np.linspace(mel(FMIN), mel(FMAX), N_MEL + 2) / 2595.0) - 1.0)
    fb = np.zeros((N_MEL, len(f)))
    for i in range(N_MEL):
        a, b, c = diem[i: i + 3]
        fb[i] = np.clip(np.minimum((f - a) / (b - a), (c - f) / (c - b)), 0.0, None)
    return np.ascontiguousarray(fb.T, dtype=np.float32)


_FB = _bo_loc_mel()                                     # (N_FFT/2 + 1) × N_MEL
_CUA_SO_HANN = np.hanning(N_FFT).astype(np.float32)


def _dac_trung(doc, duong: str, tu_s: float, den_s: float, moc) -> _CuaSo:
    """Giải mã [tu_s, den_s) theo khối (``doc`` None = FFmpeg, một tiến trình), đổi ngay mỗi khối sang công suất mel (PCM
    không giữ quá một khối; mẫu thừa cuối khối nối sang khối sau để lưới khung liền mạch), rồi log10 với sàn −60 dB.
    Kiểm huỷ/hạn chót (``moc``) trước khối đầu, sau mỗi khối, và — FFmpeg — mỗi CANH_S giây trong lúc chờ."""
    tu_s = max(0.0, tu_s)
    X = np.empty((int((den_s - tu_s) * FPS) + 2, N_MEL), dtype=np.float32)
    n, du, t0, so_mau = 0, np.zeros(0, np.float32), None, 0
    moc()
    khoi = _khoi_ffmpeg(duong, tu_s, den_s, moc) if doc is None else _khoi_doc(doc, duong, tu_s, den_s)
    try:
        for x, tu_thuc in khoi:
            if t0 is None:
                t0 = float(tu_thuc)
            buf = np.concatenate([du, x])
            so_khung = min(1 + (len(buf) - N_FFT) // HOP if len(buf) >= N_FFT else 0, len(X) - n)
            khung = np.lib.stride_tricks.sliding_window_view(buf, N_FFT)[::HOP] if so_khung else None
            for i in range(0, so_khung, KHOI_KHUNG):
                j = min(i + KHOI_KHUNG, so_khung)
                pho = np.fft.rfft(khung[i:j] * _CUA_SO_HANN, axis=1)
                X[n + i: n + j] = (pho.real ** 2 + pho.imag ** 2) @ _FB
            n += so_khung
            du = buf[so_khung * HOP:].copy()            # không giữ cả khối trong RAM tới lần giải mã sau
            so_mau += len(x)
            moc()
    finally:
        khoi.close()                                    # huỷ/hết giờ giữa chừng: giết FFmpeg ngay
    X = X[:n]
    san = 1e-20
    if n:
        buoc = max(1, n // 20000)                       # phân vị trên mẫu thưa, tất định
        san = max(float(np.percentile(X[::buoc], 99)) * 10 ** (SAN_DB / 10), 1e-20)
        np.log10(np.maximum(X, san, out=X), out=X)
    t0 = tu_s if t0 is None else t0
    het = t0 + so_mau / SR < den_s - DU_CUOI_S
    return _CuaSo(X, t0, t0 + so_mau / SR, het, X.mean(axis=0) if n else np.zeros(N_MEL, np.float32),
                  float(np.log10(san)))


# ---------------------------------------------------------------------------------------------- đo độ giống

def _cs(x: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])


def _cs2(X: np.ndarray) -> np.ndarray:
    return np.vstack([np.zeros((1, X.shape[1])), np.cumsum(X, axis=0, dtype=np.float64)])


def _khong() -> None:
    pass


def _do_duong(cl: _CuaSo, vi: _CuaSo, dau: float, k: float, u: np.ndarray, lech_s: float = 0.0,
              w_s: float = W_S, moc=_khong) -> tuple:
    """Độ giống của từng ô video ``u`` (giây [u, u + 1)) theo căn chỉnh (dau + lech_s, k): tương quan Pearson giữa
    miếng 3 s của clip quanh giây c = (u + 0,5 − dau)/k và miếng video cùng căn chỉnh, sau khi trừ trung bình TỪNG DẢI
    của chính mỗi miếng (bù âm lượng, EQ); đỉnh trong ±w_s, nội suy parabol. Mọi ô một lượt bằng tổng tích luỹ (video
    nắn theo k: khung clip f ↔ khung video gần nhất); kiểm huỷ (``moc``) mỗi KHOI_O ô. Miếng không đổi theo thời gian
    (phương sai ≤ ``san_v``): video → 0, clip → không đo được. Trả (s, r, cc): s (NaN = không đo được), r = độ lệch đỉnh
    so với căn chỉnh (giây video; NaN khi đỉnh sát mép vùng tìm), cc = giây clip tâm miếng (miếng kẹp trong cửa sổ)."""
    C, V = cl.X, vi.X
    F, L = F_MIENG, int(round(w_s * FPS))
    san_v = SAN_PHUONG_SAI * F * N_MEL
    s, r = np.full(len(u), np.nan), np.full(len(u), np.nan)
    c = (u + 0.5 - dau) / k
    fc = np.clip(np.round((c - cl.t0 - TAM_KHUNG_S) * FPS - F / 2).astype(np.int64), 0, max(len(C) - F, 0))
    cc = cl.t0 + TAM_KHUNG_S + (fc + F / 2) / FPS
    do_duoc = np.nonzero((c >= cl.t0) & (c <= cl.t0 + len(C) / FPS) & (len(C) >= F))[0]
    for i0 in range(0, len(do_duoc), KHOI_O):
        moc()
        idx = do_duoc[i0: i0 + KHOI_O]
        f_lo, f_hi = int(fc[idx].min()), int(fc[idx].max()) + F
        n = f_hi - f_lo
        f = np.arange(f_lo - L, f_hi + L)
        gv = np.round((dau + lech_s + k * (cl.t0 + TAM_KHUNG_S + f / FPS) - vi.t0 - TAM_KHUNG_S) * FPS).astype(np.int64)
        hop_le = (gv >= 0) & (gv < len(V))
        Wv = V[np.clip(gv, 0, max(len(V) - 1, 0))]
        Wv[~hop_le] = 0.0
        dem = _cs(hop_le)
        Cr = C[f_lo:f_hi]
        a = fc[idx] - f_lo
        cC, cW = _cs2(Cr), _cs2(Wv)
        eC, eW = _cs(np.einsum("fb,fb->f", Cr, Cr)), _cs(np.einsum("fb,fb->f", Wv, Wv))
        tC = cC[a + F] - cC[a]
        vC = eC[a + F] - eC[a] - np.einsum("ib,ib->i", tC, tC) / F
        clip_doi = vC > san_v
        ncc = np.full((len(idx), 2 * L + 1), -2.0)      # −2: độ trễ không đo được (tương quan luôn ≥ −1)
        for j in range(2 * L + 1):
            p = _cs(np.einsum("fb,fb->f", Cr, Wv[j: j + n]))
            b0 = a + j
            tW = cW[b0 + F] - cW[b0]
            tu = p[a + F] - p[a] - np.einsum("ib,ib->i", tC, tW) / F
            vW = eW[b0 + F] - eW[b0] - np.einsum("ib,ib->i", tW, tW) / F
            # phương sai 0 → 0/0: sai số làm tròn float32 từng cho ±1,9 ở miếng im lặng (A05)
            gia_tri = np.where(vW > san_v, tu / np.sqrt(np.maximum(vC * vW, 0.0) + 1e-9), 0.0)
            ncc[:, j] = np.where((dem[b0 + F] - dem[b0] == F) & clip_doi, gia_tri, -2.0)
        j = np.argmax(ncc, axis=1)
        hang = np.arange(len(idx))
        dinh = ncc[hang, j]
        y0, y2 = ncc[hang, np.maximum(j - 1, 0)], ncc[hang, np.minimum(j + 1, 2 * L)]
        mau = y0 - 2 * dinh + y2
        ok = (j > 0) & (j < 2 * L) & (y0 > -1.5) & (y2 > -1.5) & (mau < 0)
        d = np.where(ok, 0.5 * (y0 - y2) / np.where(ok, mau, -1.0), 0.0)
        s[idx] = np.where(dinh > -1.5, dinh, np.nan)
        r[idx] = np.where(ok, k * (j - L + d) / FPS, np.nan)
    return s, r, cc


def _khop_thang(cc: np.ndarray, r: np.ndarray, s: np.ndarray, nguong: float):
    """Khớp thẳng bền r = α + β·c trên các ô chắc chắn (s ≥ ngưỡng, r hữu hạn), bỏ ngoại lai lặp lại.
    Trả (α, β); None khi ít hơn 3 điểm (dưới 10 điểm hoặc trải < 10 s: chỉ α = trung vị)."""
    m = np.isfinite(r) & (np.nan_to_num(s, nan=-1.0) >= nguong)
    if m.sum() < 10 or np.ptp(cc[m]) < 10.0:
        return (float(np.median(r[m])), 0.0) if m.sum() >= 3 else None
    x, y = cc[m] - cc[m].mean(), r[m]
    giu = np.ones(len(x), bool)
    for _ in range(5):
        beta, alpha = np.polyfit(x[giu], y[giu], 1)
        du = y - (alpha + beta * x)
        mad = 1.4826 * float(np.median(np.abs(du[giu] - np.median(du[giu]))))
        moi = np.abs(du) <= max(0.02, 3.0 * mad)
        if moi.sum() < 10 or (moi == giu).all():
            break
        giu = moi
    return float(alpha - beta * cc[m].mean()), float(beta)


def _mad(x: np.ndarray) -> float:
    return 1.4826 * float(np.median(np.abs(x - np.median(x)))) if len(x) else 0.0


def _hai_manh(cc: np.ndarray, y: np.ndarray):
    """Hai mảnh song song (cùng độ dốc, khác hằng số) cho phần dư y theo giây clip cc (đã sắp): mỗi mảnh ≥ MANH_TOI_THIEU
    ô và ≥ 5 s, chỗ tách tối thiểu tổng bình phương phần dư. Trả (chỉ số tách, a_trái, a_phải, β, MAD phần dư) hoặc
    None."""
    n = len(cc)
    if n < 2 * MANH_TOI_THIEU:
        return None
    sx, sy, sxx, sxy, syy = (_cs(v) for v in (cc, y, cc * cc, cc * y, y * y))
    tot = (sx[n], sy[n], sxx[n], sxy[n], syy[n])
    tot_tren: list = []
    for i in range(MANH_TOI_THIEU, n - MANH_TOI_THIEU + 1):
        if cc[i - 1] - cc[0] < 5.0 or cc[-1] - cc[i] < 5.0:
            continue
        cxx = cxy = cyy = 0.0
        for (ax, ay, axx, axy, ayy, m) in ((sx[i], sy[i], sxx[i], sxy[i], syy[i], i),
                                          (tot[0] - sx[i], tot[1] - sy[i], tot[2] - sxx[i], tot[3] - sxy[i],
                                           tot[4] - syy[i], n - i)):
            cxx += axx - ax * ax / m
            cxy += axy - ax * ay / m
            cyy += ayy - ay * ay / m
        if cxx > 0:
            tot_tren.append((cyy - cxy * cxy / cxx, i, cxy / cxx))
    if not tot_tren:
        return None
    _, i, beta = min(tot_tren)
    a_t = float(np.mean(y[:i] - beta * cc[:i]))
    a_p = float(np.mean(y[i:] - beta * cc[i:]))
    du = np.concatenate([y[:i] - a_t - beta * cc[:i], y[i:] - a_p - beta * cc[i:]])
    return i, a_t, a_p, float(beta), _mad(du)


def _trung(duong: list, dau: float, k: float, c_khoang: tuple) -> bool:
    """(dau, k) trùng một căn chỉnh trong ``duong`` (lệch ≤ W_S trên suốt c_khoang giây clip)."""
    return any(all(abs((dau - d[0]) + (k - d[1]) * c) <= W_S for c in c_khoang) for d in duong)


def _can_chinh(cl: _CuaSo, vi: _CuaSo, dau: float, k: float, u: np.ndarray, nguong: float, moc, da_co: list,
               c_khoang: tuple) -> list:
    """Sửa (dau, k) của một neo theo độ lệch đỉnh của các ô chắc chắn (bám độ trôi tốc độ); vòng đầu tìm rộng
    ±W_BAT_S. Sửa quá W_BAT_S hay quá 1 % tốc độ thì giữ căn chỉnh đang có. Trả danh sách [(dau, k, s, lech)] — s đo
    với ±W_S: rỗng khi neo hội tụ về một căn chỉnh đã có trong ``da_co`` (thôi đo ngay); HAI phần tử khi độ lệch đỉnh vòng
    đầu là hai mảnh song song lệch ≥ BAC_TOI_THIEU_S (nhảy/tua lùi nhỏ hơn 1 s mà engine gộp một neo) — một đường thẳng
    qua hai mảnh cho k giả và ánh xạ lệch tới nửa bước nhảy. ``lech``: chỉ số ô (trong ``u``) của các chuỗi ≥ BAC_O_LIEN
    ô chắc chắn liền nhau (theo giây clip) vẫn lệch đường cuối > BAC_TOI_THIEU_S khi không tách được — clip có ở đó
    nhưng lệch đường này hơn 0,12 s."""
    da_co = [(d[0], d[1]) for d in da_co]
    if _trung(da_co, dau, k, c_khoang):
        return []
    dau0, k0, vong0, s = dau, k, None, None
    for vong in range(VONG_CAN_CHINH):
        moc()
        s_v, r, cc = _do_duong(cl, vi, dau, k, u, w_s=W_BAT_S if vong == 0 else W_S, moc=moc)
        s = s_v if vong else None                       # chỉ độ giống đo với ±W_S trên đường hiện tại dùng được
        if vong == 0:
            vong0 = (s_v, r, cc)
        kq = _khop_thang(cc, r, s_v, nguong)
        if kq is None:
            break
        alpha, beta = kq
        m = np.isfinite(s_v) & (s_v >= nguong)
        tam, trai = (float(np.median(cc[m])), float(np.ptp(cc[m]))) if m.any() else (float(np.median(cc)), 0.0)
        if abs(beta) > SUA_K_TOI_DA or abs(alpha + beta * tam) > W_BAT_S:
            break
        if vong and abs(alpha + beta * tam) < 0.003 and abs(beta) * trai < 0.006:
            break
        dau, k, s = dau + alpha, k + beta, None
        if _trung(da_co, dau, k, c_khoang):
            return []
    # bước nhảy nhỏ trong một neo: phần dư vòng đầu so với đường cuối thành hai bậc
    s0, r0, cc0 = vong0
    m = np.isfinite(r0) & (np.nan_to_num(s0, nan=-1.0) >= nguong)
    o = np.argsort(cc0[m])
    x = cc0[m][o]
    y = r0[m][o] - ((dau - dau0) + (k - k0) * x)        # phần dư (giây video) so với đường cuối
    if m.sum() >= 2 * MANH_TOI_THIEU:
        hm = _hai_manh(x, y) if _mad(y) > MAD_THANG_S else None
        if hm is not None and hm[4] <= MAD_THANG_S and abs(hm[2] - hm[1]) >= BAC_TOI_THIEU_S \
                and hm[4] * 3.0 <= _mad(y):
            ra = []
            for a in (hm[1], hm[2]):
                d2, k2 = dau + a, k + hm[3]
                if not _trung(da_co + [(x_[0], x_[1]) for x_ in ra], d2, k2, c_khoang):
                    moc()
                    ra.append((d2, k2, _do_duong(cl, vi, d2, k2, u, moc=moc)[0], np.zeros(0, np.int64)))
            return ra
    if s is None:
        moc()
        s = _do_duong(cl, vi, dau, k, u, moc=moc)[0]
    return [(dau, k, s, _chuoi_lech(np.nonzero(m)[0][o], np.abs(y) > BAC_TOI_THIEU_S))]


def _chuoi_lech(o_chac: np.ndarray, xa: np.ndarray) -> np.ndarray:
    """Chỉ số các ô (trong ``u``) thuộc chuỗi ≥ BAC_O_LIEN ô KỀ NHAU (u, u + 1, …) đều lệch đường (``xa``), theo các ô chắc
    chắn ``o_chac`` đã sắp: ô không chắc chắn hay không lệch ở giữa làm đứt chuỗi."""
    ra, chay = [], []
    for i, lech in zip(o_chac.tolist(), xa.tolist()):
        if lech and chay and i == chay[-1] + 1:
            chay.append(i)
            continue
        if len(chay) >= BAC_O_LIEN:
            ra += chay
        chay = [i] if lech else []
    if len(chay) >= BAC_O_LIEN:
        ra += chay
    return np.array(ra, dtype=np.int64)


def _nen_p99(cl: _CuaSo, vi: _CuaSo, neo: list, u: np.ndarray, moc):
    """p99 của đường nền tại chỗ: CÙNG giây clip, video lệch từng khoảng LECH_NEN_S dọc neo mạnh nhất (bỏ khoảng trùng
    độ lệch tới một neo khác — ở đó «nền» lại là lần dùng thật). None khi quá ít ô đo được."""
    dau0, k0 = neo[0]
    nen = [np.zeros(0)]
    for d in LECH_NEN_S:
        if all(abs(d - (a - dau0)) > 2.0 for a, _ in neo[1:]):
            moc()
            nen.append(_do_duong(cl, vi, dau0, k0, u, lech_s=d, moc=moc)[0])
    nen = np.concatenate(nen)
    nen = nen[np.isfinite(nen)]
    return float(np.percentile(nen, 99)) if len(nen) >= 30 else None


def _nen_tai_cho(cl: _CuaSo, vi: _CuaSo, dau: float, k: float, u: np.ndarray, moc, lap: list) -> np.ndarray:
    """Nền TẠI CHỖ của các ô ``u`` theo căn chỉnh (dau, k): độ giống lớn nhất của CHÍNH các ô video đó với các giây clip
    KHÁC — lệch LECH_NEN_S và ±L với L trong ``lap`` (độ lệch clip tự giống: nhạc có nhịp thì nội dung khác cùng nhịp,
    khớp vạch ô nhịp, cũng giống ~40–55 %; thiếu chúng thì nền nhạc cùng nhịp thành «có mặt» — X3). Tiếng đè trên ô làm
    nó giảm cùng căn chỉnh thật — khác p99 chung (B03). −1 = không đo được."""
    if not len(u):
        return np.zeros(0)
    lech = list(LECH_NEN_S) + [s * L for L in lap for s in (1.0, -1.0)]
    B = np.vstack([_do_duong(cl, vi, dau + k * d, k, u, moc=moc)[0] for d in lech])
    return np.max(np.nan_to_num(B, nan=-1.0), axis=0)


# ---------------------------------------------------------------------------------------------- đoạn + mép

def _co_mat(s: np.ndarray, muc: np.ndarray) -> bool:
    """Clip «có mặt» ở nhóm ô sát mép (s: độ giống theo căn chỉnh, NaN bỏ): ≥ CO_MAT_TY_LE số ô đạt mức ``muc`` của
    từng ô (``_muc_co_mat``)."""
    m = np.isfinite(s)
    return bool(m.sum() and np.sum(s[m] >= muc[m]) >= CO_MAT_TY_LE * m.sum())


def _cac_doan_tho(S: np.ndarray, nguong: float, muc_co_mat, gan=None) -> list:
    """S: (số neo × số ô) độ giống. Ô thuộc neo ≥ ngưỡng: giữ neo của ô trước nếu nó vẫn ≥ ngưỡng (bóng gần bằng của
    vòng lặp không làm đổi neo qua lại) — trừ khi neo tốt nhất là căn chỉnh GẦN (``gan[i][j]``: cách < GAN_S, hai mảnh
    của một bước nhảy nhỏ) hơn nó quá GIU_NEO; không thì neo giống nhất. Trả các đoạn [neo, ô đầu, ô cuối] (chỉ số ô):
    bỏ chuỗi < CHAY_TOI_THIEU ô; nối hai chuỗi CÙNG neo liền nhau khi khe chỉ gồm ô không đo được (clip tự im lặng), khi
    khe ≤ NOI_CUNG_NEO_S ô đo được mà MỌI ô còn «có mặt» (độ giống ≥ ``muc_co_mat(i_neo, chỉ số ô)``), hoặc khe dài hơn
    mà ≥ 3/4 số ô còn có mặt (clip ở dưới tiếng đè to: A03, B03; tiếng THAY kéo ô xuống bằng nền — không nối). Trả MỌI
    đoạn — nơi gọi bỏ đoạn không chạm lõi (luật G cần cả chúng)."""
    S0 = np.nan_to_num(S, nan=-1.0)
    dat = S0 >= nguong
    chuoi: list = []
    for i in range(S.shape[1]):
        if not dat[:, i].any():
            continue
        tot = int(np.argmax(np.where(dat[:, i], S0[:, i], -np.inf)))
        if chuoi and chuoi[-1][2] == i - 1 and dat[chuoi[-1][0], i] and not (
                gan is not None and gan[chuoi[-1][0]][tot] and S0[tot, i] > S0[chuoi[-1][0], i] + GIU_NEO):
            chuoi[-1][2] = i
        else:
            chuoi.append([tot, i, i])
    doan: list = []
    for c in (c for c in chuoi if c[2] - c[1] + 1 >= CHAY_TOI_THIEU):
        noi = False
        if doan and doan[-1][0] == c[0]:
            idx = np.arange(doan[-1][2] + 1, c[1])          # u liền: ô giữa hai chuỗi
            idx = idx[np.isfinite(S[c[0], idx])]
            co = S[c[0], idx] >= muc_co_mat(c[0], idx)
            noi = bool(co.all()) if len(idx) <= NOI_CUNG_NEO_S else bool(np.mean(co) >= KHE_DAI_TY_LE)
        if noi:
            doan[-1][2] = c[2]
        else:
            doan.append(c)
    return doan


def _mo_ho(S: np.ndarray, tho: list, nguong: float, gan=None) -> bool:
    """Một neo KHÁC cũng ≥ ngưỡng trên ≥ 80 % số ô của một đoạn: vòng lặp y hệt, giây clip không xác định duy nhất. Căn
    chỉnh GẦN (``gan``: cách < GAN_S) là mảnh kia của cùng một lần dùng (bước nhảy nhỏ), không phải bóng: bỏ qua."""
    S0 = np.nan_to_num(S, nan=-1.0)
    return any(np.mean(S0[j, i0: i1 + 1] >= nguong) >= MO_HO_TY_LE
               for i_neo, i0, i1 in tho for j in range(len(S))
               if j != i_neo and not (gan is not None and gan[i_neo][j]))


def _lech_tu_giong(cl: _CuaSo, c0: float, c1: float) -> list:
    """Các độ lệch L (giây clip, LAP_L_S) mà clip tự giống chính nó trên [c0, c1] — nhạc có nhịp: bội ô nhịp; vòng lặp:
    bội chu kỳ: đỉnh của tương quan từng khung (trừ trung bình dải, chuẩn hoá từng khung; khung im lặng = 0) giữa giây c
    và c + L, ≥ LAP_R_TOI_THIEU, tối đa LAP_SO_DINH đỉnh cách nhau ≥ 0,5 s. Đo trên ≤ 4 cửa sổ 60 s rải đều (tự tương
    quan qua FFT từng dải): RAM và thời gian không tăng theo độ dài clip."""
    f0 = max(int((c0 - cl.t0) * FPS), 0)
    f1 = min(int((c1 - cl.t0) * FPS), len(cl.X))
    N = min(f1 - f0, int(60.0 * FPS))
    l0, l1 = int(LAP_L_S[0] * FPS), min(int(LAP_L_S[1] * FPS), N - int(4.0 * FPS))
    if l1 <= l0 + 2:
        return []
    so_cua = min(4, max(1, (f1 - f0) // N))
    R = np.zeros(l1 + 1)
    for w in range(so_cua):
        a = f0 + ((f1 - f0 - N) * w) // max(so_cua - 1, 1)
        A = cl.X[a: a + N] - cl.tb
        A = A - A.mean(axis=1, keepdims=True)
        chuan = np.sqrt((A * A).sum(axis=1))
        A = np.where((chuan > 1e-3)[:, None], A / np.maximum(chuan, 1e-6)[:, None], 0.0)
        P = np.fft.rfft(A, n=2 * N, axis=0)
        R += np.fft.irfft(P * P.conj(), n=2 * N, axis=0)[: l1 + 1].sum(axis=1) / (N - np.arange(l1 + 1))
    R /= so_cua
    dinh = [lg for lg in range(l0 + 1, l1) if R[lg] >= LAP_R_TOI_THIEU and R[lg] >= R[lg - 1] and R[lg] >= R[lg + 1]]
    chon: list = []
    for lg in sorted(dinh, key=lambda x: -R[x]):
        if all(abs(lg - x) > 0.5 * FPS for x in chon):
            chon.append(lg)
        if len(chon) >= LAP_SO_DINH:
            break
    return [x / FPS for x in chon]


def _lap_cho_khac(cl: _CuaSo, vi: _CuaSo, can: list, S: np.ndarray, u: np.ndarray, tho: list, nguong: float,
                  moc, lap: list) -> bool:
    """Trên một đoạn và khe tới đoạn sau, căn chỉnh lệch ±L (L trong ``lap``: độ lệch clip tự giống —
    ``_lech_tu_giong``) theo neo của đoạn hơn MỌI neo ≥ LAP_HON và ≥ ngưỡng trên ≥ LAP_O_LIEN ô liền: video phát CHỖ
    KHÁC của clip ở đó (DJ lặp ô nhịp: ô nhịp giống nhau giữ neo trên ngưỡng, hay tách đoạn và để khe trông như «vắng»)."""
    if not lap:
        return False
    S0 = np.nan_to_num(S, nan=-1.0).max(axis=0)
    for j, (i_neo, i0, i1) in enumerate(tho):
        dau, k = can[i_neo][0], can[i_neo][1]
        idx = np.arange(i0, tho[j + 1][1] if j + 1 < len(tho) else i1 + 1)
        tot = np.full(len(idx), -1.0)
        for L in lap:
            for dau2 in (dau + k * L, dau - k * L):
                moc()
                tot = np.maximum(tot, np.nan_to_num(_do_duong(cl, vi, dau2, k, u[idx], moc=moc)[0], nan=-1.0))
        hon = (tot >= nguong) & (tot >= S0[idx] + LAP_HON)
        chay = 0
        for h in hon:
            chay = chay + 1 if h else 0
            if chay >= LAP_O_LIEN:
                return True
    return False


def _tuong_quan_khung(cl: _CuaSo, vi: _CuaSo, dau: float, k: float, c_tu: float, c_den: float) -> tuple:
    """Tương quan từng khung dọc căn chỉnh, khung clip có tâm trong [c_tu, c_den]: (giây clip tâm khung, tương quan
    giữa hai phổ sau khi trừ trung bình từng dải của CẢ cửa sổ giải mã — không phụ thuộc vị trí mép)."""
    f = np.arange(max(int(np.ceil((c_tu - cl.t0 - TAM_KHUNG_S) * FPS)), 0),
                  min(int(np.floor((c_den - cl.t0 - TAM_KHUNG_S) * FPS)) + 1, len(cl.X)))
    t = cl.t0 + TAM_KHUNG_S + f / FPS
    gv = np.round((dau + k * t - vi.t0 - TAM_KHUNG_S) * FPS).astype(np.int64)
    ok = (gv >= 0) & (gv < len(vi.X))
    f, t, gv = f[ok], t[ok], gv[ok]
    a, v = cl.X[f] - cl.tb, vi.X[gv] - vi.tb
    a, v = a - a.mean(axis=1, keepdims=True), v - v.mean(axis=1, keepdims=True)
    return t, (a * v).sum(axis=1) / np.sqrt((a * a).sum(axis=1) * (v * v).sum(axis=1) + 1e-9)


def _khoang_im(cl: _CuaSo, vi: _CuaSo, dau: float, k: float, v_tu: float, v_den: float) -> list:
    """Khoảng clip vắng chắc chắn (giây video) trong [v_tu, v_den]: khung video im lặng (mọi dải ≤ sàn + IM_TREN_SAN
    và ≥ IM_DUOI_DINH dưới p99 của chính các khung video trong khoảng xét; mức tham chiếu thấp tới mức 50 dB dưới nó
    chìm dưới sàn thì im lặng không đo được) liền nhau ≥ IM_TOI_THIEU_S, trong
    khi clip ở cùng căn chỉnh có tiếng (một dải ≥ sàn + CO_TIENG) ở ≥ nửa số khung. Tiếng đè chỉ CỘNG năng lượng nên
    video im lặng không thể chứa tiếng clip; clip tự im lặng ở đó thì không tính. Mức tham chiếu lấy trong ĐOẠN, không
    từ nội dung to bên cạnh: clip chèn nhỏ −36 dB mà có chỗ khẽ thêm −25 dB không thành «khoảng lặng»."""
    j0 = max(int(np.ceil((v_tu - vi.t0) * FPS)), 0)
    j1 = min(int(np.floor((v_den - vi.t0 - 2 * TAM_KHUNG_S) * FPS)) + 1, len(vi.X))   # khung nằm trọn trong khoảng
    if j1 - j0 < IM_TOI_THIEU_S * FPS:
        return []
    muc = float(np.percentile(vi.X[j0:j1:max(1, (j1 - j0) // 20000)], 99))
    if muc - IM_DUOI_DINH < vi.san + IM_TREN_SAN:       # sàn quá gần mức của đoạn: im lặng không đo được
        return []
    im = vi.X[j0:j1].max(axis=1) <= vi.san + IM_TREN_SAN
    bien = np.diff(np.concatenate([[0], im.astype(np.int8), [0]]))
    ra = []
    for a, b in zip(np.nonzero(bien == 1)[0], np.nonzero(bien == -1)[0]):    # khung [j0 + a, j0 + b) im lặng
        s0 = vi.t0 + (j0 + a - 0.5) / FPS                                   # giữa khung có tiếng cuối và khung im đầu
        s1 = vi.t0 + (j0 + b - 0.5) / FPS + 2 * TAM_KHUNG_S
        f = np.arange(max(int(np.ceil(((s0 - dau) / k - cl.t0 - TAM_KHUNG_S) * FPS)), 0),
                      min(int(np.floor(((s1 - dau) / k - cl.t0 - TAM_KHUNG_S) * FPS)) + 1, len(cl.X)))
        if s1 - s0 >= IM_TOI_THIEU_S and len(f) and np.mean(cl.X[f].max(axis=1) >= cl.san + CO_TIENG) >= 0.5:
            ra.append((max(s0, v_tu), min(s1, v_den)))
    return ra


def _laplace(x: np.ndarray) -> tuple:
    """(trung vị, độ lệch tuyệt đối trung bình ≥ SAN_LECH): tham số phân bố Laplace hợp lẽ cực đại."""
    m = float(np.median(x))
    return m, max(float(np.mean(np.abs(x - m))), SAN_LECH)


def _clip_lang_ngoai(cl: _CuaSo, c_tho: float, dau_ben: bool, c_lim: tuple):
    """Giây clip nơi tiếng clip bắt đầu (mép đầu) / hết (mép cuối) khi cửa sổ ±2,5 s quanh mép thô (trong ``c_lim``) bắt
    đầu từ phía ngoài bằng im lặng của CHÍNH clip (mọi dải ≤ sàn + 3 dB) liền ≥ IM_TOI_THIEU_S; None nếu không. Chỗ
    chuyển có thể nằm phía trong mép thô (mép thô theo ô 1 s, miếng 3 s đã chạm phần có tiếng)."""
    a, b = max(c_tho - NUA_CUA_SO_MEP_S, c_lim[0]), min(c_tho + NUA_CUA_SO_MEP_S, c_lim[1])
    f = np.arange(max(int(np.ceil((a - cl.t0 - TAM_KHUNG_S) * FPS)), 0),
                  min(int(np.floor((b - cl.t0 - TAM_KHUNG_S) * FPS)) + 1, len(cl.X)))
    if not len(f):
        return None
    lang = cl.X[f].max(axis=1) <= cl.san + IM_TREN_SAN
    if not dau_ben:
        lang = lang[::-1]
    so = int(np.argmin(lang)) if not lang.all() else len(lang)   # số khung im lặng liền tính từ phía ngoài cùng
    if so < IM_TOI_THIEU_S * FPS:
        return None
    t = cl.t0 + TAM_KHUNG_S + f / FPS
    return float(t[so - 1] + 0.5 / FPS) if dau_ben else float(t[::-1][so - 1] - 0.5 / FPS)


def _mep(cl: _CuaSo, vi: _CuaSo, dau: float, k: float, c_tho: float, phia: str, gioi_han: tuple,
         c_doan: tuple) -> tuple:
    """Mép một đoạn tới khung (11,6 ms) quanh giây clip thô ``c_tho``, trong ±NUA_CUA_SO_MEP_S.

    Mỗi khung có tương quan x dọc căn chỉnh. Phân bố «trong» = x của ≤ SAU_MEP_S giây khung sâu trong chính đoạn
    (``c_doan``: giây clip hai đầu chuỗi ô thô); phân bố «ngoài» = x của cùng các khung với video lệch LECH_NEN_S[:3];
    cả hai mô hình Laplace (đuôi dày: nhạc có nhịp có khung thưa giống kém, nền có nốt tình cờ giống). Mép = cực đại của
    tổng tích luỹ log tỉ số hợp lẽ «ngoài»/«trong» về phía ngoài mép; bằng chứng < BANG_CHUNG_MEP coi như không có mép
    trong cửa sổ. ``gioi_han`` = (giây clip nhỏ nhất, lớn nhất đo được, mỗi phía có phải đầu/cuối FILE clip): cửa sổ bị
    chặn ở phía «ngoài» chỉ chốt về chỗ chặn khi mép đo được nằm trong CHOT_BIEN_S quanh đó (gồm «không có mép trong cửa
    sổ»). Khung lạ với CẢ hai phân bố xếp phía ngoài: mốc là ước lượng phía trong. Không tìm được mép mà phía ngoài là im
    lặng của chính clip: mép = chỗ clip có tiếng, «clip_lang». Trả (giây clip của mép, cách tìm — «tho» = không đo
    được)."""
    c_min, c_max, min_la_file, max_la_file = gioi_han
    dau_ben = phia == "dau"
    tu, den = max(c_tho - NUA_CUA_SO_MEP_S, c_min), min(c_tho + NUA_CUA_SO_MEP_S, c_max)
    chan, bien = (c_tho - NUA_CUA_SO_MEP_S < c_min, c_min) if dau_ben else (c_tho + NUA_CUA_SO_MEP_S > c_max, c_max)
    ten_bien = ("dau_clip" if min_la_file else "gioi_han") if dau_ben else ("cuoi_clip" if max_la_file else "gioi_han")

    def tho() -> tuple:
        lang = _clip_lang_ngoai(cl, c_tho, dau_ben, (c_min, c_max))
        return (lang, "clip_lang") if lang is not None else (c_tho, "tho")
    t, x = _tuong_quan_khung(cl, vi, dau, k, tu, den)
    sau = (den, min(den + SAU_MEP_S, c_doan[1] - 1.5)) if dau_ben else (max(tu - SAU_MEP_S, c_doan[0] + 1.5), tu)
    x_trong = _tuong_quan_khung(cl, vi, dau, k, *sau)[1]
    x_ngoai = np.concatenate([_tuong_quan_khung(cl, vi, dau + d, k, tu, den)[1] for d in LECH_NEN_S[:3]])
    if len(t) < 8 or len(x_trong) < KHUNG_PHAN_BO or len(x_ngoai) < KHUNG_PHAN_BO:
        return tho()
    (m1, b1), (m0, b0) = _laplace(x_trong), _laplace(x_ngoai)
    if m1 - m0 < CHENH_PHAN_BO:
        return tho()
    llr = np.abs(x - m1) / b1 + np.log(b1) - np.abs(x - m0) / b0 - np.log(b0)
    # khung lạ với CẢ hai phân bố (nốt nền cùng dải mel với nốt clip đang ngân ngay sau mép: giống ~0,75 khi «trong»
    # 0,99 ± 0,03): đuôi dày của Laplace xếp nó vào «trong», mép lấn ra ngoài tới 0,2 s (A03) — xếp phía ngoài
    la = (np.abs(x - m1) > LA_K * b1) & (np.abs(x - m0) > LA_K * b0)
    llr = np.where(la, np.maximum(llr, 1.0), llr)
    G = _cs(llr) if dau_ben else float(np.sum(llr)) - _cs(llr)       # G[j]: bằng chứng «ngoài» phía ngoài khung j
    j = int(np.argmax(G))
    # đi từ mép ra ngoài, bằng chứng lại tăng ≥ 5 lần ngưỡng sau một chỗ trũng nông hơn 3 lần mức tăng: clip còn tiếp
    # sau một chỗ vấp ngắn (khung lạ +30, khung clip sạch chỉ −9: cực đại giả định MỘT chỗ đổi bám vào chỗ vấp)
    g = G[j::-1] if dau_ben else G[j:]
    hoi = g - np.minimum.accumulate(g)
    m_ = int(np.argmax(hoi))
    if G[j] >= BANG_CHUNG_MEP and hoi[m_] >= 5 * BANG_CHUNG_MEP and 3 * hoi[m_] >= g[0] - g[: m_ + 1].min():
        return tho()
    if G[j] < BANG_CHUNG_MEP:
        j = 0 if dau_ben else len(x)                                  # không có mép trong cửa sổ: đoạn phủ cả cửa sổ
    if 0 < j < len(x):
        mep = float((t[j - 1] + t[j]) / 2)
    elif chan:
        mep = bien
    else:
        return tho()                                                   # mép thô lệch quá nửa cửa sổ
    if chan and abs(mep - bien) <= CHOT_BIEN_S:
        return bien, ten_bien
    return mep, "bac_thang"


# ---------------------------------------------------------------------------------------------- lắp kết quả

def _chua(ly_do: str, t_bat_dau: float, nguong: float = 0.0, nen: float = 0.0) -> dict:
    return {"phien_ban": PHIEN_BAN, "trang_thai": CHUA, "ly_do": ly_do, "doan": [], "cho_cat": [], "ho_so": [],
            "nguong_pct": round(100.0 * nguong, 1), "nen_p99_pct": round(100.0 * nen, 1), "cham_gioi_han": False,
            "thoi_gian_s": round(time.monotonic() - t_bat_dau, 3)}


def _pct(x: float) -> float:
    return round(100.0 * min(max(float(x), 0.0), 1.0), 1)


def _do_dai_hop(khoang: list) -> float:
    tong, cuoi = 0.0, -np.inf
    for a, b in sorted(khoang):
        a = max(a, cuoi)
        if b > a:
            tong, cuoi = tong + b - a, b
    return tong


def tinh_chinh_dong(clip_path, video_path, neo, vung_khop_s, end_s, *, pham_vi_s=None, kiem_huy=None,
                    han_chot=None, doc_pcm=None) -> dict:
    """Tinh chỉnh một dòng engine (hợp đồng: ``Engine._tinh_chinh_ket_qua``). ``neo``: ((giây video của giây 0 clip,
    k), …) mạnh trước; [vung_khop_s, end_s]: lõi engine trên trục video; ``pham_vi_s``: (0, giây cuối đã quét) hoặc
    None; ``kiem_huy``: gọi giữa các bước, ngoại lệ của nó đi thẳng ra ngoài; ``han_chot``: mốc ``time.monotonic()``;
    ``doc_pcm(path, tu_s, dai_s) -> (mẫu float32 mono 11025 Hz, giây thật mẫu đầu)``. Trả dict JSON được."""
    t_bat_dau = time.monotonic()

    def moc() -> None:
        if kiem_huy is not None:
            kiem_huy()
        if han_chot is not None and time.monotonic() > han_chot:
            raise _HetGio

    neo = [(float(a), float(b)) for a, b in (neo or ()) if np.isfinite(a) and np.isfinite(b) and 0.5 <= b <= 2.0]
    vung, end = float(vung_khop_s), float(end_s)
    if not neo or not end > vung:
        return _chua(LY_DO_THIEU_NEO, t_bat_dau)
    if end - vung > LOI_TOI_DA_S:
        return _chua(LY_DO_QUA_DAI, t_bat_dau)
    try:
        return _tinh_chinh(clip_path, video_path, neo, vung, end, pham_vi_s, doc_pcm, moc, han_chot, t_bat_dau)
    except _HetGio:
        return _chua(LY_DO_HET_GIO, t_bat_dau)


def _lech_chua_giai_thich(can: list, tho: list, tat_ca: list, so_o: int) -> bool:
    """Luật G: một căn chỉnh có đoạn thô chạm lõi (``tho``) mà ≥ BAC_O_LIEN ô lệch của nó (``can[j][3]``, từ
    ``_can_chinh``) KHÔNG thuộc đoạn thô của neo khác (``tat_ca``: kể cả đoạn không chạm lõi) — thuộc đoạn của chính nó
    hay không đoạn nào. Ô thuộc đoạn neo khác = bóng của clip tự giống (B07) hay mảnh kia của cùng clip cạnh dòng."""
    chu = np.full(so_o, -1)                             # neo của đoạn chứa ô (−1: không đoạn nào)
    for i_neo, i0, i1 in tat_ca:
        chu[i0:i1 + 1] = i_neo
    return any(np.count_nonzero(np.isin(chu[can[j][3]], (-1, j))) >= BAC_O_LIEN for j in {t[0] for t in tho})


def _o_ngoai(u: np.ndarray, lo: float, hi: float, le: float = W_S) -> np.ndarray:
    """Chỉ số các ô có miếng 3 s (nới thêm ``le`` mỗi đầu: ±W_S tìm đỉnh) nằm trọn trong [lo, hi] giây video."""
    return np.nonzero((u - 1.0 - le >= lo) & (u + 2.0 + le <= hi))[0]


def _tinh_chinh(clip_path, video_path, neo, vung, end, pham_vi_s, doc, moc, han_chot, t_bat_dau) -> dict:
    bien = BIEN_CO_DINH_S + BIEN_TY_LE * (end - vung)
    c_tu = max(0.0, min((vung - a) / b for a, b in neo) - bien)
    c_den = max((end - a) / b for a, b in neo) + bien
    v_tu = max(0.0, vung - bien - BIEN_NEN_S)
    v_den = end + bien + BIEN_NEN_S if pham_vi_s is None else min(end + bien + BIEN_NEN_S, float(pham_vi_s[1]))
    if c_den <= c_tu or v_den <= v_tu:
        return _chua(LY_DO_THIEU_AM, t_bat_dau)
    moc()
    if han_chot is not None:                            # không kịp thì từ chối NGAY, để ngân sách cho dòng sau
        uoc = CHI_PHI_GIAI_MA_S * (c_den - c_tu + v_den - v_tu) + CHI_PHI_NEO_S * (end - vung) * (len(neo) - 1)
        if time.monotonic() + uoc > han_chot:
            return _chua(LY_DO_KHONG_KIP, t_bat_dau)
    if doc is None:                                     # FFmpeg thật: tua thô (1 s trước «tu») phải rơi vào luồng tiếng
        tre = _tre_am(video_path, moc)
        if tre is None:
            return _chua(LY_DO_TRE_AM, t_bat_dau)
        if tre > TRE_AM_TOI_DA_S:
            v_tu = max(v_tu, tre + 1.1)                 # tua thô rơi sau mẫu tiếng đầu ≥ 0,1 s
            if v_den <= v_tu:
                return _chua(LY_DO_THIEU_AM, t_bat_dau)
    cl = _dac_trung(doc, clip_path, c_tu, c_den, moc)
    vi = _dac_trung(doc, video_path, v_tu, v_den, moc)
    u = np.arange(int(np.floor(max(vung - bien, vi.t0 + 1.5))),
                  int(np.ceil(min(end + bien, vi.t0 + len(vi.X) / FPS - 1.5))))
    if len(cl.X) <= F_MIENG or len(vi.X) <= F_MIENG or len(u) < CHAY_TOI_THIEU:
        return _chua(LY_DO_THIEU_AM, t_bat_dau)
    nen_p99 = _nen_p99(cl, vi, neo, u, moc)
    if nen_p99 is None:                                 # hai file đọc đủ, chỉ thiếu chỗ đặt đường nền (clip/đoạn ngắn)
        return _chua(LY_DO_NEN_IT, t_bat_dau)
    nguong = nen_p99 + LE_NGUONG
    if nguong > NGUONG_TOI_DA:
        return _chua(LY_DO_TUONG_PHAN, t_bat_dau, nguong, nen_p99)

    def chua(ly_do: str) -> dict:
        return _chua(ly_do, t_bat_dau, nguong, nen_p99)
    can: list = []
    for a, b in neo:
        can += _can_chinh(cl, vi, a, b, u, nguong, moc, can, (cl.t0, cl.het_s))
    if not can:
        return chua(LY_DO_KHONG_THAY)
    S = np.vstack([x[2] for x in can])
    lap = _lech_tu_giong(cl, cl.t0, cl.het_s)
    gan = [[all(abs((a[0] - b[0]) + (a[1] - b[1]) * c) < GAN_S for c in (cl.t0, cl.het_s)) for b in can] for a in can]

    def muc_co_mat(i_neo: int, idx: np.ndarray, le: float = 1e-9) -> np.ndarray:
        """Mức «clip có mặt» (dưới tiếng đè) của từng ô theo neo: p99 nền chung; clip tự giống (nhạc có nhịp) thì
        nền TẠI CHỖ + ``le`` — p99 chung của nó có thể bị khoảng lệch trùng vạch ô nhịp đẩy lên (B03), còn nền tại
        chỗ thiếu các độ lệch cùng nhịp thì thấp giả với clip không tự giống (nốt cùng lưới thời gian)."""
        if not lap:
            return np.full(len(idx), nen_p99)
        return _nen_tai_cho(cl, vi, can[i_neo][0], can[i_neo][1], u[idx], moc, lap) + le
    tat_ca = _cac_doan_tho(S, nguong, muc_co_mat, gan)
    tho = [c for c in tat_ca if u[c[1]] < end and u[c[2]] + 1 > vung]     # bỏ đoạn không chạm lõi engine
    if not tho:
        return chua(LY_DO_KHONG_THAY)
    if _mo_ho(S, tho, nguong, gan):
        return chua(LY_DO_MO_HO)
    if _lap_cho_khac(cl, vi, can, S, u, tho, nguong, moc, lap):
        return chua(LY_DO_LAP_CHO_KHAC)
    if _lech_chua_giai_thich(can, tho, tat_ca, len(u)):
        return chua(LY_DO_LECH_NEO)
    doan = []
    for i_neo, i0, i1 in tho:
        moc()
        dau, k = can[i_neo][0], can[i_neo][1]
        c_min, c_max = max(cl.t0, (vi.t0 - dau) / k), min(cl.het_s, (vi.het_s - dau) / k)
        gh = (c_min, c_max, c_min == cl.t0 and cl.t0 < 1.0 / SR, c_max == cl.het_s and cl.het_file)
        c_doan = ((u[i0] - dau) / k, (u[i1] + 1 - dau) / k)
        ca, cach_a = _mep(cl, vi, dau, k, c_doan[0], "dau", gh, c_doan)
        cb, cach_b = _mep(cl, vi, dau, k, c_doan[1], "cuoi", gh, c_doan)
        if "tho" in (cach_a, cach_b):
            return chua(LY_DO_MEP)
        # tách ở khoảng lặng đo được (clip vắng chắc chắn), kể cả khi ô hai bên vẫn ≥ ngưỡng hay đã nối qua — A05
        im = _khoang_im(cl, vi, dau, k, dau + k * ca, dau + k * cb)
        moc_c = [ca, *((s - dau) / k for ab in im for s in ab), cb]
        cach = [cach_a, *["im_lang"] * (2 * len(im)), cach_b]
        for j in range(0, len(moc_c), 2):
            c1, c2 = moc_c[j], moc_c[j + 1]
            o = (i0, i1) if not im else (max(i0, int(np.searchsorted(u, dau + k * c1 - 1, "right"))),
                                         min(i1, int(np.searchsorted(u, dau + k * c2)) - 1))
            if not im or (k * (c2 - c1) >= DOAN_TOI_THIEU_S and o[0] <= o[1]):
                doan.append({"neo": i_neo, "dau": dau, "k": k, "c": [c1, c2], "v": [dau + k * c1, dau + k * c2],
                             "cach": cach[j: j + 2], "o": o})
    if not doan:
        return chua(LY_DO_KHONG_THAY)
    for a, b in zip(doan, doan[1:]):                    # hai đoạn kề chồng nhau sau khi tinh mép: gặp ở giữa
        if a["v"][1] > b["v"][0]:
            g = (a["v"][1] + b["v"][0]) / 2
            a["v"][1], b["v"][0] = g, g
            a["c"][1], b["c"][0] = (g - a["dau"]) / a["k"], (g - b["dau"]) / b["k"]
    # bằng chứng clip VẮNG phía ngoài mỗi mép đo được: ô sát mép trong khe giữa hai đoạn (theo neo của TỪNG bên) và
    # tới 10 s ngoài đoạn đầu / cuối. Clip còn «có mặt» ở đó = tiếng đè, không phải hết đoạn → mép/chỗ cắt bịa
    kiem = []                                           # (đoạn, từ, đến, mép ở «từ», mép NGOÀI cùng)
    if doan[0]["cach"][0] == "bac_thang":
        kiem.append((doan[0], doan[0]["v"][0] - SAU_NGOAI_S, doan[0]["v"][0], False, True))
    if doan[-1]["cach"][1] == "bac_thang":
        kiem.append((doan[-1], doan[-1]["v"][1], doan[-1]["v"][1] + SAU_NGOAI_S, True, True))
    for a, b in zip(doan, doan[1:]):
        if b["v"][0] - a["v"][1] > KHE_NOI_S:
            kiem += [(x, a["v"][1], b["v"][0], phia == 1, False) for x, phia in ((a, 1), (b, 0))
                     if x["cach"][phia] == "bac_thang"]
    ngoai_khong_kiem = False                            # mép ngoài sát giới hạn đo: phía ngoài chưa hề được đo
    ngoai_ben = set()                                   # ... ở mép nào: False = mép đầu, True = mép cuối
    for d, lo, hi, mep_o_tu, ngoai in kiem:
        idx = _o_ngoai(u, max(lo, vi.t0), min(hi, vi.het_s))   # miếng vượt phần đã giải mã: chưa đo, không phải «vắng»
        idx = idx[:SAT_MEP_O] if mep_o_tu else idx[-SAT_MEP_O:]
        if not len(idx):
            ngoai_khong_kiem |= ngoai
            if ngoai:
                ngoai_ben.add(mep_o_tu)
            continue
        moc()
        if _co_mat(_do_duong(cl, vi, d["dau"], d["k"], u[idx], moc=moc)[0], muc_co_mat(d["neo"], idx, NEN_TAI_CHO_LE)):
            return chua(LY_DO_CON_DUOI_DE)
    # khe giữa hai đoạn: ô có miếng nằm trọn trong khe, clip «có mặt» theo NEO NÀO trong hai neo ở ≥ 1/2 số ô → tiếng đè
    # đúng chỗ nối (tua lùi dưới tiếng đè: mỗi neo chỉ có mặt ở một phía của chỗ nối, ô sát mép không đủ thấy)
    for a, b in zip(doan, doan[1:]):
        idx = _o_ngoai(u, a["v"][1], b["v"][0], 0.0) if b["v"][0] - a["v"][1] > KHE_NOI_S else []
        if not len(idx):
            continue
        co = np.zeros(len(idx), bool)
        for d in ([a] if a["neo"] == b["neo"] else [a, b]):
            moc()
            s_x = np.nan_to_num(_do_duong(cl, vi, d["dau"], d["k"], u[idx], moc=moc)[0], nan=-1.0)
            co |= s_x >= muc_co_mat(d["neo"], idx, NEN_TAI_CHO_LE)
        if np.mean(co) >= 0.5:
            return chua(LY_DO_CON_DUOI_DE)
    # lưới an toàn: lõi engine phải được các đoạn + chỗ cắt đã đo (khe giữa hai đoạn đã qua kiểm ở trên) giải thích
    phu = [tuple(d["v"]) for d in doan] + [(a["v"][1], b["v"][0]) for a, b in zip(doan, doan[1:])]
    if (end - vung) - _do_dai_hop([(max(a, vung), min(b, end)) for a, b in phu]) > HO_LOI_TOI_DA_S:
        return chua(LY_DO_HO_LOI)
    cham = ngoai_khong_kiem or any(set(d["cach"]) & set(GIOI_HAN) or d["v"][0] < vi.t0 + 1.0
                                   or d["v"][1] > vi.het_s - 1.0 for d in doan)
    return {"phien_ban": PHIEN_BAN, "trang_thai": DA, "ly_do": "", **_doan_ra(S, u, doan),
            "ho_so": _ho_so(S, u, doan), "nguong_pct": round(100.0 * nguong, 1),
            "nen_p99_pct": round(100.0 * nen_p99, 1), "cham_gioi_han": bool(cham),
            # từng mép NGOÀI (báo cáo V2 chỉ nới đúng mép đó về mốc lượt quét — D-50); đoạn đã xếp theo video, không chồng
            "cham_dau": bool(False in ngoai_ben or doan[0]["cach"][0] in GIOI_HAN or doan[0]["v"][0] < vi.t0 + 1.0),
            "cham_cuoi": bool(True in ngoai_ben or doan[-1]["cach"][1] in GIOI_HAN or doan[-1]["v"][1] > vi.het_s - 1.0),
            "thoi_gian_s": round(time.monotonic() - t_bat_dau, 3)}


def _doan_ra(S: np.ndarray, u: np.ndarray, doan: list) -> dict:
    """«doan» + «cho_cat» của kết quả. Độ giống TB/thấp nhất tính trên các ô có miếng 3 s nằm trọn trong đoạn đã tinh
    mép (đoạn quá ngắn: mọi ô của chuỗi)."""
    ra = []
    for d in doan:
        i = np.arange(d["o"][0], d["o"][1] + 1)
        gt = S[d["neo"], i]
        trong = gt[(u[i] - 1 >= d["v"][0]) & (u[i] + 2 <= d["v"][1]) & np.isfinite(gt)]
        gt = trong if len(trong) else gt[np.isfinite(gt)]
        gt = gt if len(gt) else np.zeros(1)             # mẩu sau khi tách không có ô đo được
        ra.append({"video_tu": round(float(d["v"][0]), 3), "video_den": round(float(d["v"][1]), 3),
                   "clip_tu": round(float(d["c"][0]), 3), "clip_den": round(float(d["c"][1]), 3),
                   "k": round(float(d["k"]), 6), "tuong_dong_tb": _pct(np.mean(gt)),
                   "tuong_dong_min": _pct(np.min(gt)), "cach_tim_mep": list(d["cach"])})
    cho_cat = [{"video_tu": a["video_den"], "video_den": b["video_tu"], "clip_bo_tu": a["clip_den"],
                "clip_bo_den": b["clip_tu"]} for a, b in zip(ra, ra[1:])]
    return {"doan": ra, "cho_cat": cho_cat}


def _ho_so(S: np.ndarray, u: np.ndarray, doan: list) -> list:
    """[[giây video (tâm ô), %], …]: dọc neo của đoạn chứa ô; ô ngoài mọi đoạn theo neo của đoạn gần nhất."""
    ra = []
    for i in range(len(u)):
        d = min(doan, key=lambda d: max(d["o"][0] - i, i - d["o"][1], 0))
        x = S[d["neo"], i]
        if np.isfinite(x):
            ra.append([round(float(u[i]) + 0.5, 3), _pct(x)])
    return ra
