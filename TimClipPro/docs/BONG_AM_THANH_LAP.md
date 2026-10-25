# «Bóng» của âm thanh lặp trong `_merge` — thiết kế bản sửa P0 (PC2, 10/10/2026)

Mã: `chong_bong_lap.py` (thuần) + `Engine._merge`. Test: `tests/test_bong_am_thanh_lap.py` (nhanh, mức mảnh),
`tests/test_bong_am_thanh_lap_audio_that.py` (chậm, audio thật). Dữ liệu golden: `tests/golden/bong_lap/` (README ở đó).
Báo cáo điều tra đầy đủ nằm NGOÀI Git trên PC2 (`C:\Dev\pc2_test_runs\2026-10-10_p0_loop_alias\BAO_CAO_P0.md`); file
này tóm tắt những gì cần để review và bảo trì.

## 1. Vấn đề
Nhạc có nhịp trống đều, vòng hợp âm, hay một đoạn lặp y hệt làm audfprint trả thêm những căn chỉnh của CÙNG clip lệch
bội số nửa ô nhịp so với căn chỉnh thật — gọi là «bóng». Kiểm độc lập không qua audfprint (độ tự giống phổ của chính
âm thanh, Spearman 0,59 với số hash của 178 mảnh bóng): bóng là tính chất của tín hiệu, không phải lỗi audfprint.

Bóng phủ cùng vùng video với căn chỉnh thật nhưng yếu hơn hẳn: tỷ số hash ≤ 0,30 ở 20/21 lần dùng tổng hợp (đa số
0,09–0,18). Chỉ âm thanh lặp Y HỆT TỪNG MẪU cho tỷ số ≈ 1 — khi đó mốc thật sự không xác định được duy nhất.

`_merge` trước bản sửa:
1. Neo mốc đầu clip vào mảnh có vùng SỚM NHẤT của nhóm (gom trong ±`dedup_s`). Một bóng 34 hash đủ kéo lệch mốc; sai
   số bị chặn bởi ±20 s (E2E: S02 lệch −10,7 s, dựng lại kho thì −19,2 s).
2. Nhóm toàn bóng ngoài cửa sổ ±20 s tự thành ứng viên ~1.000–1.900 hash, 4–6 hash/s → qua bậc A → dòng báo cáo thừa
   «Rất chắc chắn» (`danh_gia` chỉ xét ≥ 100 hash) và làm phồng «Tổng số đoạn phát hiện» (`so_dat_nguong`, hợp đồng =
   số ứng viên đạt chuẩn TRƯỚC Top-N — hợp đồng đúng, nội dung bị bóng thổi phồng).
3. Top-5 chỉ giấu được dòng bóng khi có ≥ 5 nguồn mạnh hơn; `len(dat) ≤ top_n` thì báo tất cả.
4. Bảng hash audfprint (depth 100) bỏ NGẪU NHIÊN phần tràn của ô quá đầy (`hash_table.py`, không seed) — trống lặp làm
   tràn nhiều ô, nên mỗi lần dựng kho bóng khác đi một chút, và (1) biến khác biệt nhỏ đó thành bước nhảy mốc lớn.

## 2. Nguyên tắc và cách làm
Một giây video chỉ có thể là MỘT vị trí trong clip gốc. Hai căn chỉnh khác nhau của cùng clip phủ cùng một vùng video thì
nhiều nhất một cái là thật.

Chỉ đổi MỐC và việc nhóm toàn bóng thành ứng viên. Mọi con số bằng chứng của nhóm thật giữ nguyên: gom nhóm, tích phân
hash, độ dài khớp, vùng khớp, cận trên vẫn tính trên ĐỦ mảnh như cũ.

| Bước | Hàm | Quy tắc |
|---|---|---|
| A. Phân loại mảnh | `phan_loai_manh` | Theo (clip, hệ số tốc độ). (1) Gom mảnh thành cụm vị trí đặt: lệch align ≤ `DUNG_SAI_ALIGN_S` = 0,5 s so với mảnh mạnh nhất của cụm. (2) Xét cụm theo TỔNG hash giảm dần; mảnh nằm ≥ `TY_LE_PHU` = 50% trong PHẠM VI của một vị trí đã giữ là «bóng» (hash ≤ `TY_LE_BONG` = 0,5 × mảnh mạnh nhất của vị trí đó) hoặc «đối thủ» ngang ngửa (> 0,5); còn lại là mảnh «chính». |
| A. Bỏ nhóm toàn bóng | `Engine._merge` | Nhóm (gom như cũ) không có mảnh chính nào → không thành ứng viên. |
| A. Mốc | `Engine._merge` | Mốc đầu clip = mảnh CHÍNH sớm nhất (bóng/đối thủ không bao giờ làm mốc). |
| C'. Một lần dùng | `gop_cung_vi_tri`, `cung_vi_tri` | Nhóm có mảnh chính cùng vị trí đặt: lệch align ≤ 0,1 s + `toc_do_lech_toi_thieu` (0,15%) × khoảng cách tâm, trần 1 s. Chỉ gộp khi một nhóm đã đạt bậc A và nhóm gộp vẫn đạt bậc A (gọi đúng `chap_nhan_khop.danh_gia_chap_nhan`). |
| B. Bằng chứng mốc | `bang_chung_moc` | Trên vị trí đặt LÀM MỐC của dòng: `moc_mo_ho` (có đối thủ > 0,5), `moc_thay_the` (mốc mà các đối thủ cho, ≤ 20), `ty_so_doi_thu` (căn chỉnh cạnh tranh mạnh nhất / mảnh mạnh nhất của vị trí làm mốc). `confidence` (độ chắc chắn của NGUỒN) không đổi. |

Vì sao từng chi tiết (mỗi điều có test và đột biến bắt được — mục 6):
- **Không xoá bóng trước khi gộp** (bản đầu của phương án đã duyệt): xoá làm nhóm thật mất 0–1,1% hash, đủ đánh rơi một
  ứng viên sát ngưỡng 1.000 (`test_sat_nguong_1000_hash_bong_van_gop_bang_chung_nhu_cu`).
- **Phủ theo phạm vi VỊ TRÍ, không theo từng mảnh**: căn chỉnh thật trôi tốc độ rất nhỏ vỡ thành nhiều mảnh có «lỗ» > 20 s;
  bóng nằm trong lỗ không bị mảnh thật NÀO phủ quá nửa (video B13: bóng 129,2 s phủ 48,7%) và thành dòng neo sai.
- **Gom cụm TRƯỚC, xét theo TỔNG hash**: xét từng mảnh theo hash thì một đối thủ mạnh hơn các mảnh YẾU của vị trí thật
  được xét trước khi phạm vi của vị trí thật kịp nở tới chỗ nó; xếp theo mảnh mạnh nhất thì căn chỉnh thật vỡ nhiều mảnh
  thua một bóng có một mảnh lớn.
- **Chặn trôi của C'**: bản C (chỉ trần 1 s) gộp mảnh trôi 3% của lượt CHƯA bù tốc độ — đổi 2 golden bù tốc độ. Phần lệch
  gốc 0,1 s cho độ rung vài khung 23 ms của audfprint qua ranh giới khúc.
- **Chốt chấp nhận của C'**: hai phần cùng dưới ngưỡng cộng lại thành dương tính MỚI là đổi chính sách nhận diện (mục 4);
  phần dày gộp với phần thưa có thể rớt rào mật độ bậc A và mất một dòng đạt chuẩn.
- **Cờ xét vị trí làm mốc**: mốc lấy từ đó; đối thủ của phần khác trong cùng dòng (bản cắt giữa) không làm mốc mơ hồ.
- **Hằng số ở module, không ở `Config`**: chúng không làm đổi kết luận âm tính (mục 4) nên không vào `TRUONG_CHINH_SACH`;
  ĐỔI chúng (nhất là nới) là đổi chính sách nhận diện — cần quyết định riêng (docs/ai/DECISIONS.md D-27).

## 3. Bất biến (đã kiểm)
- Ứng viên đạt chuẩn mới ⊆ ứng viên đạt chuẩn cũ (so theo bằng chứng: clip, hash, vùng), trừ nhóm do C' gộp — mà C' chỉ
  gộp khi một phần đã đạt chuẩn. ⇒ Không có dương tính MỚI ở mức video; tập clip đạt chuẩn chỉ có thể mất nhóm toàn bóng.
  Đo trên 27 lượt quét đã ghi của bộ điều tra (phát lại mảnh thô): 0 vi phạm.
- Nhóm còn lại giữ nguyên `hashes`, `matched_s`, `vung_khop_s`, `end_s` (chỉ `start_s`/`clip_bat_dau_s`/`clip_offset_s` có
  thể đổi vì mốc đổi).
- Hai clip khác nhau, hai hệ số tốc độ khác nhau không bao giờ xét nhau (nhạc hiệu chung, âm thanh chồng, lượt bù).
- Không có bóng thì kết quả Y HỆT mã cũ: golden quét cũ 29/29 không đổi.

## 4. Báo cáo, lịch sử, chữ ký chính sách
**Trường mới của `Match`** (`moc_mo_ho`, `moc_thay_the`, `ty_so_doi_thu`): mặc định = mốc chắc chắn, `compare=False`; chỉ
sống trong bộ nhớ — KHÔNG vào `lichsu.db`, ảnh chụp V2, CSV, Sheets. Kết quả cũ/đọc lại từ lịch sử = mốc chắc chắn.

**Các đường trình bày/xuất mốc** (mốc = `start_s`/`clip_bat_dau_s`; không đường nào đọc cờ mới):

| Đường | Nơi | Thấy cờ mơ hồ? |
|---|---|---|
| Bảng kết quả khi quét xong | `app.py` (cột «Xuất hiện từ», «Đánh giá») | Không |
| Lịch sử trên giao diện | `app.py` (đọc bảng `matches`) | Không |
| Dòng lệnh | `cli.py` | Không |
| CSV dọc 16 cột | `Engine` (luật cũ) / `bao_cao_v2.dong_doc` | Không (cột «Đánh giá» = độ chắc chắn nguồn) |
| CSV ngang 34 cột + Google Sheets (qua outbox) | `bang_ngang` / `bao_cao_v2.dong_ngang` → `outbox` | Không (không có cột nhãn) |
| Hồ sơ khiếu nại `.md` | `dossier.py` | Không |
| Lịch sử bền | `lichsu.db` (`jobs`, `matches`), ảnh chụp V2 `bao_cao_job` | Không lưu |
| Báo cáo lô nguồn chung | `common_original.dong_bao_cao` | Không |

**Việc còn mở (P-6 trong `docs/ai/DECISIONS.md`; từng là BLOCKER phát hành Stable — PC2 DEV-ONLY dùng D-27 từ 25/10):** dòng mơ hồ (âm thanh lặp y hệt) vẫn được hiển thị, xuất CSV và TỰ ĐỘNG gửi Sheets
như một mốc chắc chắn. Mã cũ cũng vậy (còn tệ hơn: 4–5 dòng «Rất chắc chắn» ở các mốc khác nhau), nhưng quy tắc «không
gửi kết quả mơ hồ như mốc chắc chắn» CHƯA được bảo đảm. Cần một PR riêng (đổi chính sách báo cáo V2 — người dùng duyệt):
- Ảnh chụp V2: thêm `moc_mo_ho`, `moc_thay_the`, `ty_so_doi_thu` vào `DoanV2` (đọc ảnh chụp cũ thiếu khoá = mốc chắc
  chắn), tăng `PHIEN_BAN_ANH_CHUP` kèm đọc được bản cũ.
- Bảng 34 cột/Sheets GIỮ hợp đồng cột: chỉ đổi NỘI DUNG ô «Đoạn vi phạm i» của dòng mơ hồ, ví dụ
  `≈ HH:MM:SS – HH:MM:SS · link (mốc mơ hồ: âm thanh lặp; mốc khác: …)` — phải kiểm Apps Script có tách chuỗi ô này
  không (`apps_script/`).
- CSV dọc: cột «Đánh giá» giữ nguyên nghĩa; thêm thông tin mốc vào cột ghi chú hoặc file phụ (sidecar như `dong_pham_vi`).
- Giao diện + lịch sử: nhãn «mốc mơ hồ» cạnh mốc; lưu cờ bền (bảng riêng hoặc ảnh chụp V2 — không thêm cột vào `jobs`).
- Hoặc (thay thế, cũng cần duyệt): outbox không tự gửi dòng có mốc mơ hồ, chờ người dùng xác nhận.

**`so_dat_nguong`** («Tổng số đoạn phát hiện»): ngữ nghĩa giữ nguyên — số ứng viên đạt chuẩn TRƯỚC Top-N; giá trị giảm
vì ứng viên bóng không còn (bộ điều tra: 74 → 22 trên 16 video).

**Chữ ký chính sách (`chu_ky_chinh_sach`) GIỮ NGUYÊN — có lý do, không phải để né:**
- Watch bỏ qua (`Engine.ids_da_quet`): dương tính cùng kho — luôn; âm tính — chỉ khi quét trọn, cùng phiên bản kho, cùng
  chữ ký chính sách. Đổi chữ ký ⇒ mọi âm tính cũ bị quét lại (hàng nghìn video dài).
- Âm tính cũ VẪN ĐÚNG với mã mới: bản sửa không sinh dương tính mới (mục 3) — đó cũng là lý do C' có chốt chấp nhận.
- Dương tính cũ: kết luận «có vi phạm» vẫn đúng (bóng chỉ xuất hiện quanh căn chỉnh thật của cùng clip), nhưng DÒNG trong
  lịch sử/Sheets cũ có thể mang mốc lệch tới ±20 s và dòng bóng. Không quét lại tự động; đề xuất PC1 chạy truy vấn CHỈ
  ĐỌC trên lịch sử production tìm job có nhiều dòng cùng clip chồng vùng/mốc gần nhau (dấu hiệu bóng) để kiểm lại tay.
- Không có cache kết quả khớp nào khác: lô nguồn chung giữ kết quả trong bộ nhớ, kho đệm chỉ chứa media.
- Kết quả mới và cũ hiện KHÔNG phân biệt được trong lịch sử (cùng chữ ký). Đề xuất kèm PR trình bày: ghi «phiên bản thuật
  toán gộp» (vd. `gop-p0`) vào ảnh chụp V2 — không vào chữ ký chính sách, vì không đổi kết luận âm tính.

## 5. Giới hạn đã biết
- Cùng một clip phát CHỒNG chính nó ở hai độ lệch (hiệu ứng vang/mashup) với lớp yếu ≤ 50% → lớp yếu bị coi là bóng
  (không thành dòng; nếu > 50% thì thành mốc thay thế của dòng mơ hồ). Chưa thấy ca thật.
- Gom nhóm vẫn là thuật toán tham lam cũ (nhóm lấy align của mảnh đầu làm mốc so): bản reup cắt giữa có khe > `dedup_s`
  vẫn ra 2 dòng (mỗi dòng đúng mốc của một phần), như trước. C' chỉ gộp các phần CÙNG vị trí đặt.
- Vòng lặp y hệt: mốc báo là căn chỉnh mạnh nhất trong các mốc tương đương (tuỳ ý giữa các mốc ngang nhau) — luôn kèm cờ.
- Một bóng có MỘT mảnh lớn hơn từng mảnh của căn chỉnh thật bị vỡ (trôi) → mốc vẫn đúng nhưng dòng được đánh dấu mơ hồ
  (thận trọng). Âm thanh lặp có đoạn mở đầu riêng (B05) cũng được đánh dấu: tỷ số 0,89.
- Tràn bảng hash vẫn làm bóng khác nhau giữa các lần dựng kho; bản sửa làm MỐC không còn phụ thuộc vào bóng.

## 6. Kiểm thử
- Nhanh: 26 test — tái hiện lỗi (đỏ trên mã cũ: commit đưa test vào đánh dấu `xfail(strict=True)`), khoá hành vi cũ
  (clip cắt giữa, dùng hai lần, phát lại liền nhau, khúc gối, trôi nối tiếp, nhạc hiệu chung, hai nguồn chồng tiếng, sát
  ngưỡng 1.000, khác hệ số tốc độ), C' và chốt, bằng chứng mốc, tương thích trường mới.
- Chậm: 3 test audio thật (nhạc có nhịp trích giữa, vòng lặp y hệt, đối chứng không lặp).
- Đột biến (bộ công cụ PC2 ngoài Git): mỗi điều kiện mới bị vô hiệu → ít nhất một test đỏ.
- Số đo đầy đủ (16 video, dựng lại kho, hiệu năng): handoff PC2 và mô tả PR.
