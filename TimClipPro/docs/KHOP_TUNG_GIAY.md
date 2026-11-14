# Khớp «chính xác từng giây» — nghiên cứu 14/11/2026 (PC2, chỉ audio giả lập)

Người dùng hỏi (14/11): «có thể tối ưu Tool Quét, quét độ tương đồng chính xác từng giây được không». Trạng thái: CHỈ
NGHIÊN CỨU — mã sản phẩm KHÔNG đổi; chờ người dùng quyết (P-8 trong `docs/ai/DECISIONS.md`).

## Cách đo
- Mã đo `60b8b03`: engine + audfprint + FFmpeg THẬT, cấu hình mặc định, `ncores 2`, chặn mạng, audio GIẢ LẬP (nốt ngẫu
  nhiên `_giai_dieu` + nhạc có nhịp `am_thanh_lap`), sự thật biết trước từng mẫu. Không dữ liệu thật, không YouTube.
- 15 tình huống của bộ thử (S0–S9, S4b, S5b, S6b, S7b, S7c) + 3 thêm (X1–X3) + 7 ca khó NGOÀI MẪU của phản biện
  (H1a–H4) + 3 video 60 phút (L0–L2) + đo hiệu năng audio dài định dạng thật (clip opus 10–119 phút, video webm 3 giờ).
- Phản biện tự dựng lại sự thật từ audio (khớp từng mẫu) và chấm lại độc lập bằng lưới 1 ms: trùng mọi số đã báo.
- Script: `tools/khop_tung_giay/` (`bo_thu` = sinh tình huống + chạy engine + chấm; `cach_a|b|c` = 3 cách;
  `phan_bien_*` = 3 góc phản biện). Script giữ đường dẫn PC2 (`C:\Dev\pc2_test_tools\khop_tung_giay`, kết quả
  `C:\Dev\pc2_test_runs\2026-11-14_khop_tung_giay`, ~5 GB, chỉ có trên PC2) — máy khác sửa hằng ở đầu file.
  Bộ thử ~8 phút: `cd tools/khop_tung_giay/bo_thu && PYTHONPATH=<repo>/tools/test/chan_mang <venv>/python -B
  chay_bo_thu.py --tat-ca`.

## Hiện trạng engine (`60b8b03`)
| Đại lượng | Đo được |
|---|---|
| Mốc đầu clip (`start_s`, link, «giây bắt đầu» V2) | đúng ≤ 0,1 s ở mọi ca k = 1 — lấy từ căn chỉnh của mảnh chính |
| «Khớp từ giây» (`vung_khop_s`) | TRỄ +4,9 … +23,3 s (≈ 5 % độ dài mỗi mảnh) |
| Mốc cuối (`end_s`, «giây kết thúc» V2/Sheets) | SỚM −1,8 … −29,1 s (≈ 5 %, tới 8 % khi ít hash — S5 nhạc đè 0 dB) |
| Dùng một phần clip (S3) | `start_s` = mốc ẢO của giây 0 clip (280 thay vì 400, theo bất biến «link = mốc đầu clip»): khoảng hiển thị chỉ đúng 70 % số giây |
| Cắt giữa + chèn 30 s (S4) | ra 2 dòng nhưng khe báo [437,6; 491,6] (54 s) thay vì [450; 480]; dòng 2 mang mốc ảo 220 |
| Video nhanh 2 %, dùng phần sau clip (S7b) | mốc đầu lệch −5,98 s: các mảnh k = 1 trôi dần được `_merge` nối thành một nhóm ĐẠT chuẩn → lượt bù tốc độ không chạy (`engine.py:5703`) → mốc tính với k = 1. Phần sót của TCP-05; `test_toa_do_audio_that.py` không bắt vì seed của nó làm nhóm k = 1 trượt chuẩn và lượt bù chạy (S7c đúng −0,11 s) |
| Opus 32 kbps −6 dB (S2) | mốc không lệch; hash còn 23 % |
| Nhạc đè 0 dB / −5 dB (S5 / S5b) | báo được (1122 hash) / KHÔNG báo (979 < 1000 hash) dù định vị vẫn đúng |
| Vòng lặp y hệt (S6b) | mốc đầu đúng; `vung_khop_s` lấy từ mảnh bóng (min/max qua MỌI mảnh, `engine.py:4652`) |
| Đối chứng âm (S0, L0) | 0 dương tính giả |

Nguyên nhân «khớp từ» trễ / mốc cuối sớm: engine không truyền `--time-quantile` → audfprint mặc định 0,05 bỏ 5 % số hit
mỗi đầu (`audfprint_match.py:188–189`) — như `docs/REPORT_POLICY_V2.md` §8 đã ghi 04/10. Không có thông tin TỪNG GIÂY
nào: không biết giây nào trong đoạn thật sự trùng, chỗ cắt nhỏ hơn ~20 s bị che.

## Ba cách đã thử
**A — đổi `-Q` (time-quantile): LOẠI.** Q = 0 đúng ≤ 1,1 s khi đoạn liền mạch, nhưng MỘT hit tình cờ cùng căn chỉnh kéo
mép đi 130 s (S4), 37–387 s (đoạn trích trong video 60 phút). Q 0,01–0,02 bền hơn nhưng vẫn sai 1–8 s; không Q nào vừa
chính xác vừa bền. Mọi Q mới là ĐỔI CHÍNH SÁCH NHẬN DIỆN: đổi `khop` → lọc `min_match_s`, mật độ bậc A, gộp dòng (S4b
2 → 1), có chạy lượt bù tốc độ không (S7c Q0: mốc −8,28 s), chống bóng (golden `cat_giua` đỏ); 2/13 test chậm đỏ ở Q0;
chữ ký chính sách + 28 golden đổi; Watch quét lại toàn bộ âm tính.

**B — dòng thời gian hash** (băm lại quanh căn chỉnh bằng `audfprint_analyze`): mép 0,1–0,3 s trong mẫu, nhưng 3,3–8,5 s
mỗi dòng, ~1,35 GB RAM mỗi giờ audio, cần danh sách mảnh từ engine, luật ngưỡng rò theo tên file. Chỉ làm đối chứng.

**C — tương đồng phổ từng giây** (log-mel 40 dải, Pearson cửa sổ 3 s chuẩn hoá theo miếng, bám độ trôi tốc độ, ngưỡng
theo đường nền tại chỗ trên chính cặp clip–video): ỨNG VIÊN.
- Trong mẫu (18 ca): mép ≤ 0,052 s, đúng/đủ theo giây ≥ 99,98 %; thấy chỗ cắt S4 [450,010; 480,011], S4b [449,986;
  455,000]; đo được tốc độ (k 1,02001), sửa mốc S7b −5,98 → −0,022 s; từ chối 120/120 video không liên quan, 74/76 căn
  chỉnh lệch, 12/12 bóng; 0,45–2,92 s mỗi kết quả trên WAV; chỉ numpy + FFmpeg.
- NGOÀI MẪU hỏng 4/7 ca:
  - H3 nhạc đè chỉ MỘT PHẦN clip → bịa «chỗ cắt» 120 s, mất 1/3 đoạn (ngưỡng neo vào trung vị lõi engine);
  - H1b tua lùi < 20 s rồi phát lại → engine gộp một dòng, C chỉ đo một căn chỉnh → bỏ phần phát lại;
  - H4 bỏ 0,6 s đầu clip → luật «chốt về đầu clip» sai −0,598 s (22/36 mép trong mẫu là chốt, không phải đo);
  - H2a đoạn nằm trọn trong vòng lặp y hệt → engine nhảy lần lặp (+34 s, `moc_mo_ho` BẬT), C theo bóng 94,5 %.
- Nhạc có nhịp lệch nửa phách còn lọt 2/76 dòng giả. Số % không phải «tỉ lệ clip» (nhạc đè 0 dB chỉ 56 % dù khớp chắc).

## Ràng buộc tích hợp (đọc mã `60b8b03`; `phan_bien_san_pham/kiem_rui_ro.py` 23/23)
- Chạy SAU `_chon_loc` (`engine.py:5738–5740`), chỉ trên `kq.matches`: không tạo/bỏ dòng; trường Config mới NGOÀI
  `TRUONG_CHINH_SACH` giữ chữ ký `v1:373c474c3359d380`.
- Lúc đó khúc WAV đã xoá → đọc lại file media, giữ `_giu_file_dem(path)`; clip lấy từ `Match.duong_dan_kho` (`.pklz`
  không có audio); clip đổi sau dựng kho (`_clip_doi_file_sau_cong_bo`) → bỏ qua. Lỗi/huỷ của bước mới phải tự nuốt:
  khối try của `_scan_media` biến mọi ngoại lệ thành `error` → mất dương tính.
- `Match` chưa mang hệ số k + họ biến đổi; suy ngược từ các mốc sai ở ca biên → thêm trường `compare=False` gán trong
  `_merge`.
- KHÔNG thêm trường vào `BaoCaoV2` (ảnh chụp cũ thành «hỏng», `bao_cao_v2.py:364, 435`), KHÔNG thêm cột Sheets (kiểm
  tiêu đề nghiêm ngặt `sheets.py:112–152` → lỗi vĩnh viễn). Đổi giây trong ô «Đoạn vi phạm»/CSV/hồ sơ = chính sách báo
  cáo V3 (8 chỗ so cứng «v2»). Lịch sử cũ không tinh chỉnh lại được (không lưu `vung_khop_s`; đệm audio dọn sau 7 ngày).
- Bật mặc định chạm ~47 file test quét (harness golden coi lệnh FFmpeg lạ là lỗi) → ra mắt TẮT mặc định.
- Hiệu năng: Top-5 thêm 6–10 % một lượt quét 3 giờ (10–15 s), RAM 100–150 MB — nếu cắt cửa sổ quanh đoạn khớp + giải mã
  dòng chảy float32. Bản thô giải mã CẢ clip: clip 2 giờ 38 s / 903 MB; kho D-34 clip 13 giờ ước 5,5–7,2 GB → bắt buộc
  cắt cửa sổ, ngân sách thời gian, kiểm huỷ, tiến trình con.
- Kho thường 16 bit, clip > 25,4 phút: mốc cuộn (W40: một lần dùng tách 3 dòng, mốc lệch tới 1521,7 s) — giới hạn đã
  biết (`docs/FINGERPRINT_RECOVERY_ARCHITECTURE.md` §6.1); tinh chỉnh không cứu.

## Đề xuất (người dùng chọn «1 và 2» ngày 14/11 → D-49 trong `docs/ai/DECISIONS.md`)
1. Giai đoạn 1: tuỳ chọn «Tinh chỉnh mốc từng giây» TẮT mặc định. Lõi Cách C + 5 sửa của phản biện (ngưỡng tuyệt đối theo
   đường nền + trễ; xét mọi căn chỉnh trong nhóm, hụt vùng engine thì «chưa tinh chỉnh»; chỉ chốt mép khi đo thấy; không
   chạy khi `moc_mo_ho`; H1b/H1c/H2a/H2b/H3/H4 vào hồi quy) + các chặn hiệu năng. Hiển thị biểu đồ từng giây + CSV phụ;
   KHÔNG đổi V2/Sheets/lịch sử. Test đỏ trước; test bất biến tắt/bật (matches, V2, Sheets, lịch sử trùng từng byte).
2. Thử vài video thật trên DEV 8502 khi người dùng duyệt.
3. Giai đoạn 2: lưu bảng riêng (`lichsu.db` v5). Giai đoạn 3 (duyệt riêng): giây tinh chỉnh vào Sheets/CSV = chính sách
   báo cáo V3.
4. Riêng: phần sót TCP-05 (S7b) — sửa trong matcher (ước độ trôi cho nhóm k = 1 nối từ mảnh trôi, hoặc vẫn chạy lượt bù
   khi nhóm đạt có độ trôi) đổi mốc báo cáo → cần duyệt riêng, test đỏ bằng S7b.

## Đã làm (D-49, 14/11 — nhánh `feature/pc2/khop-tung-giay`)
- Việc 2 (`1d8b6d9`): nhóm lượt thường có mảnh chính trôi đều → mốc đầu tính với k đo từ độ trôi
  (`toc_do_khop.he_so_moc_theo_troi`). S7b −5,98 s → đúng; golden đổi đúng một dòng BỊ LOẠI (43,7 → 50,0 s = mốc thật).
- Việc 1: ống nối trong engine (`4e1728d`, `1c6d693`, `16332aa`) + `tinh_chinh_moc.py` (lõi Cách C + các sửa dưới đây).
  Tắt mặc định; bật thì matches/V2/Sheets/lịch sử/Watch giống hệt từng trường (28 tình huống golden + 12 lượt engine thật
  tắt/bật). Sau 3 vòng viết → kiểm ngoài mẫu → phản biện → sửa (workflow 10 tác tử):
  - Trong mẫu, 27 tình huống qua engine thật: mép lệch ≤ 0,028 s (riêng X1 — dùng một phần clip + nhạc đè 0 dB — 0,055 s);
    0 chỗ cắt bịa, 0 chỗ cắt sót; đúng/đủ theo giây ≥ 0,9998.
  - Ca ẩn bộ 1 (18 ca, người dựng khác, không xem mã): vòng 1 đạt 14, hỏng 2 (1 nghiêm trọng: im lặng 4 s bị nối qua và
    miếng im lặng cho «giống 100 %») → vòng 3 đạt 16/16. Bộ 2 (20 ca mới): vòng 2 đạt 16, hỏng 2 → vòng 3 đạt 18/18.
    Ca còn lại: engine không ra dòng (video đổi tốc độ ±2–3 %) — bước này không chạy.
  - 55 ca đối kháng của 3 phản biện (thuật toán, hiệu năng, mã + test): vòng 2 có 5 kết quả sai mà tự tin → vòng 3 đạt 54,
    hụt 1 (mép ở giới hạn cửa sổ, có cờ «chạm giới hạn»).
  - Lỗi lớn đã sửa: FFmpeg lặp vô hạn (AAC, cuối file — nay MỘT tiến trình FFmpeg mỗi cửa sổ, đọc theo khối); khe giữa
    hai neo luôn tính là chỗ cắt (tiếng đè quanh chỗ tua lùi → chỗ cắt bịa); mép «thô» dưới tiếng đè vẫn báo ĐÃ; thay 3–6 s
    bị nối thành một đoạn; DJ lặp ô nhịp; nhảy 0,15–0,5 s trong một neo thành k giả; neo trôi hội tụ → «lặp y hệt» giả.
  - Hiệu năng (PC2, một neo): lõi 10 phút 3,0 s / 95 MB; 1 giờ 21 s / 183 MB; 2 giờ 42 s / 286 MB; huỷ ≤ 0,35 s; lõi
    2 giờ mà ngân sách 30 s → từ chối ngay. Qua engine: thêm ~1–2 s mỗi dòng.
  - Review trước khi gộp (vòng 4, 15/11; 4 góc review + kiểm lại từng phát hiện) — 7 lỗi sửa kèm test đỏ→xanh: bản ghi .ts
    đổi tần số mẫu giữa chừng làm phần sau lệch (bỏ `first_pts=0`, tua thô 1 s trước rồi cắt theo nhãn thời gian); bấm Dừng
    khi FFmpeg im lặng phải chờ tới 2 phút (luồng canh 0,2 s); câu lỗi FFmpeg tiếng Anh kèm đường dẫn; mép bám chỗ vấp ngắn
    sát mép; mép ngoài sát giới hạn đo không kiểm được mà không cờ; dòng lõi dài tiêu hết ngân sách của các dòng sau (nay
    dòng lõi ngắn chạy trước); CSV phụ xếp sai chỗ cắt dài 0.
  - Kiểm độc lập vòng 4 (15/11, 71 tác tử: tái hiện cũ/mới, chạy lại các bộ, đột biến, review mới, fuzz 2.100 ca, phản biện
    từng phát hiện): 7 sửa đều đúng; 65 ca trong/ngoài mẫu không đổi; đột biến 19/21 bị giết (2 sống = thiếu test, nay có).
    Tìm thêm 3 lỗi, sửa ở vòng 5 kèm test đỏ→xanh: (1) video có luồng tiếng bắt đầu SAU hình (bản ghi mkv/mp4/ts): vòng 4
    làm mọi mốc sớm đúng độ trễ (0,5 s) mà vẫn «đã tinh chỉnh» → cửa sổ video bắt đầu sau chỗ tiếng bắt đầu ≥ 1 s (ffprobe
    `start_time`); nay mkv/mp4/ts trễ 0,3–0,5 s ra đúng giây (lệch ≤ 6 ms), trễ 0,8–1,5 s «chưa tinh chỉnh»; (2) ô kiểm phía
    ngoài mép có miếng vượt phần đã giải mã cho độ giống «không đo được» mà bị coi là «clip vắng» → mép sớm 5,5 s không cờ →
    kẹp vùng kiểm vào phần đã giải mã; (3) nhảy/tua nhỏ 0,15–0,45 s trong lần dùng ngắn (engine gộp một neo) hay tốc độ lệch
    > 1 %: một đoạn ánh xạ lệch 0,2–0,4 s, mép sớm tới 5,5 s, không cờ → ≥ 4 ô chắc chắn liền nhau lệch đường > 0,12 s mà
    không đoạn nào của neo khác giải thích → «chưa tinh chỉnh». Cộng: luồng canh không tính thời gian xử lý khối, đóng ống
    stderr, câu lỗi «file mất, đang bị khoá, hỏng hoặc không có tiếng».
  - Số đo sau vòng 5: 27 ca trong mẫu + 38 ca ngoài mẫu: kết quả giống hệt vòng 4 (lượt đầu của luật (3) từng làm hỏng
    B07 — tua lùi 10 s, clip tự giống chu kỳ ~10 s: ô «bóng» thuộc đoạn của neo kia — đã thu hẹp). Lưới 96 ca nhảy nhỏ: sai
    mà tự tin 27 → 0, mất 0 ca đúng; lưới 48 ca tốc độ lệch 1,2–3 %: 22 → 0. Fuzz 2.100 ca: đúng 1.307 → 1.308, sai có cờ
    33 → 26, sai không cờ 30 → 29. 55 ca đối kháng: 54 đạt + 1 hụt có cờ (như vòng 4). Đột biến 25/25 bị giết (đối chứng
    đạt ở cả 3 lô). Test: nhanh 3885 = 3881 đạt / 4 bỏ qua / 0 hỏng, chậm 25/25.
- Giới hạn đã biết: độ phân giải theo ô 3 s — tiếng THAY < ~2,5 s giữa đoạn bị nối qua; tiếng đè ngắn đúng chỗ nối hai
  neo có thể thành chỗ cắt ngắn bịa; tiếng đè to hơn clip ≥ 6 dB không phân biệt được với tiếng thay (≥ 3 dB và dài ≥ 10 s
  ở mép ngoài: mép vào trong không cờ); nhảy 0,5–1 s trong một neo → «chưa tinh chỉnh»; engine tách một lần dùng thành hai
  dòng (B07) → dòng đầu «chưa tinh chỉnh» (sửa phía engine); hằng ước tính thời gian đo trên PC2. Fuzz 2.100 ca còn 29 ca
  (1,4 %) sai mà không cờ, có từ trước vòng 4: 22 ca mép lệch 0,15–0,6 s (nốt nền cùng dải mel, nốt clip < 300 Hz, chỗ
  vấp sát mép), 7 ca tiếng đè ở mép hay quanh chỗ thay đẩy mép 0,8–4 s. Clip có luồng tiếng bắt đầu trễ: giây clip có thể
  lệch đúng độ trễ đó.
- Công cụ kiểm: `tools/khop_tung_giay/san_pham/` (`kiem_trong_mau.py`; `ca_an/` dựng + chấm ca ẩn; `phan_bien/` ca đối
  kháng, đột biến, hiệu năng). Bằng chứng (ngoài Git): `C:\Dev\pc2_test_runs\2026-11-14_p8\`,
  `…\2026-11-15_p8_vong4\`, `…\2026-11-15_p8_vong5\`.
- Tiếp: người dùng thử thật trên DEV 8502 (ô «🎯 Tinh chỉnh mốc từng giây» ở thanh bên) → giai đoạn 2 (lưu lịch sử),
  giai đoạn 3 (giây tinh chỉnh vào Sheets/CSV chính) là quyết định riêng.
