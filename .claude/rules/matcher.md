---
paths:
  - "TimClipPro/engine.py"
  - "TimClipPro/chap_nhan_khop.py"
  - "TimClipPro/chong_bong_lap.py"
  - "TimClipPro/toc_do_khop.py"
  - "TimClipPro/common_original.py"
  - "TimClipPro/common_original_jobs.py"
  - "TimClipPro/chan_doan_quet.py"
  - "TimClipPro/scan_jobs.py"
  - "TimClipPro/scan_ui.py"
  - "TimClipPro/audfprint_progress_runner.py"
  - "TimClipPro/audfprint-master/**"
  - "TimClipPro/tests/golden/**"
  - "TimClipPro/tests/golden_quet.py"
  - "TimClipPro/tests/test_golden_quet_cu.py"
  - "TimClipPro/tests/test_muc_tieu_quet.py"
  - "TimClipPro/tests/test_nguon_chung_*.py"
  - "TimClipPro/tests/test_match_selection.py"
  - "TimClipPro/tests/test_selection.py"
  - "TimClipPro/tests/test_merge_hash_split.py"
  - "TimClipPro/tests/test_quet_tang_dan.py"
  - "TimClipPro/tests/test_pham_vi_quet.py"
  - "TimClipPro/tests/test_toc_do_khop.py"
  - "TimClipPro/tests/test_toa_do_*.py"
  - "TimClipPro/tests/test_engine_core.py"
  - "TimClipPro/tests/test_chan_doan_zero_match.py"
  - "TimClipPro/tests/test_bong_am_thanh_lap*.py"
  - "TimClipPro/tests/am_thanh_lap.py"
  - "TimClipPro/tests/tao_golden_bong_lap.py"
---
# Quy tắc vùng MATCHER — quét, so khớp, chọn lọc, «Một video gốc chung cho cả lô»

Tự nạp khi đọc/sửa file khớp `paths` ở trên. Bất biến chung vẫn ở `TimClipPro/CLAUDE.md`.

## Trước khi sửa
- Hành vi quét cũ bị khoá bằng golden (`tests/test_golden_quet_cu.py`, dữ liệu `tests/golden/`, sinh trên `f87cc85`).
  Golden đổi = hành vi cũ đổi → phải có lý do và người dùng duyệt; không «sinh lại golden cho xanh».
- `audfprint-master/` là thư viện vendored: không sửa, bọc trong `engine.py`.
- Không đổi `_merge`, ngưỡng mặc định, trần `max_matches` khi người dùng chưa yêu cầu (đã hiệu chỉnh bằng đo thật).
- Tái hiện bằng audio synthetic (chèn clip vào file dài ở mốc đã biết) — mẫu: `tests/test_nguon_chung_audio_that.py`.
  Dữ liệu cho matcher phải có cả âm thanh LẶP (`tests/am_thanh_lap.py`): `_giai_dieu` là nốt ngẫu nhiên, không bao giờ
  sinh «bóng» — bộ test cũ vì thế đã không bắt được lỗi mốc của nhạc có nhịp (LOI_DA_GAP mục 18).
- Âm thanh lặp (`chong_bong_lap.py`, `TimClipPro/docs/BONG_AM_THANH_LAP.md`): mốc đầu clip CHỈ lấy từ căn chỉnh chính;
  không xoá mảnh khỏi phép tính bằng chứng (hash sát ngưỡng sẽ rớt); gộp/lọc không được sinh dương tính MỚI — nếu
  sinh là đổi chính sách nhận diện (chữ ký chính sách, Watch quét lại âm tính). Hằng số của module cũng là chính sách.
- Bài học liên quan: `TimClipPro/docs/LOI_DA_GAP.md` mục 5, 12, 13, 15a, 15c, 16, 18.

## Test (chi tiết: `docs/ai/TEST_MATRIX.md`, hàng «Matcher / quét»)
- Đổi đường quét, `_merge`, ngưỡng, dừng sớm: suite nhanh + chậm (`-m slow`) + kiểm đột biến các vị từ đã đổi.

## Tài liệu (`TimClipPro/docs/`)
`COMMON_ORIGINAL_DESIGN.md`, `COMMON_ORIGINAL_VALIDATION.md`, `COMMON_ORIGINAL_SATURATION_ANALYSIS.md`,
`MATCH_ACCEPTANCE_ARCHITECTURE.md`, `MATCH_SELECTION_ARCHITECTURE.md`, `DA_TOC_DO.md`, `FAST_TOP1_SCAN.md`,
`ZERO_MATCH_ROOT_CAUSE.md`, `SCAN_PIPELINE_V2_DESIGN.md`, `SCAN_THREADING_AND_STATE.md`, `BONG_AM_THANH_LAP.md`.

Phần dưới đây chuyển NGUYÊN VĂN từ `TimClipPro/CLAUDE.md` (bản e49340d); đường dẫn `docs/…`, `tests/…` tính từ
`TimClipPro/`.

## Chế độ «Một video gốc chung cho cả lô» — bất biến

Thiết kế đầy đủ: `docs/COMMON_ORIGINAL_DESIGN.md`. Những điều KHÔNG được phá:

- Ứng viên lấy từ `ScanResult.ung_vien_dat` (đạt chuẩn TRƯỚC khi cắt Top-N), không bao giờ từ
  `matches`: video gốc chung có thể không là Top-1 của video nào. Trường này chỉ sống trong bộ
  nhớ — không vào lịch sử, không vào báo cáo 16/34 cột.
- Mục tiêu quét (`ScanObjective`) truyền TƯỜNG MINH bằng `muc_tieu=`; `None` = hành vi cũ, không
  kế thừa. Ở mọi điểm dừng sớm / tải tiếp / bù tốc độ, nhánh cũ giữ NGUYÊN VĂN biểu thức cũ —
  `tests/test_golden_quet_cu.py` (golden sinh trên `f87cc85`) khoá điều đó. Đừng gom các luật cũ
  vào một hàm: chúng khác nhau thật (đếm clip khác nhau ≠ đếm đoạn đã chọn).
- Chế độ xác minh chỉ dừng khi thấy ĐÚNG video gốc cần xác minh; nguồn khác dù mạnh tới đâu cũng
  không làm dừng, không chặn bù tốc độ.
- Chỉ loại một video gốc bằng lượt quét HỢP LỆ và TRỌN (`quet_day_du`, không vùng lỗi). Dừng sớm,
  tải một phần, lỗi, huỷ không bao giờ là «vắng mặt».
- Định danh = (kho, basename clip). Không dùng tiêu đề, không gộp theo mã `[ID]` trong tên file
  (tên kiểu «X [Compilation].mp3» cũng ra mã 11 ký tự).
- `_merge` chỉ giữ basename nên hai bản ghi vân tay cùng tên (ví dụ `dir1/same.opus` và
  `dir2/same.opus`) cho ra CÙNG một `Match.clip`. Tên có >1 bản ghi trong kho không bao giờ được
  xác nhận là nguồn chung và không điều khiển kế hoạch (không làm đích, không xác nhận ngay);
  chỉ còn ứng viên trùng tên thì lô CHƯA KẾT LUẬN. Không đọc được danh sách clip của kho thì
  không chạy lô — chạy tiếp là mất chốt chặn này một cách lặng lẽ.
- «Không tìm thấy» không phải chứng minh tuyệt đối: kết luận mang `gioi_han` (khúc chạm trần
  `max_matches`, lượt quét trọn không thử bù tốc độ) tới tận giao diện và CSV. Đừng hạ thành
  «chưa kết luận» chỉ vì chạm trần — gần như mọi lượt quét thật đều chạm
  (`docs/ZERO_MATCH_ROOT_CAUSE.md` mục 9). Đo thật trên lô Joe ngày 04/10/2026
  (`docs/COMMON_ORIGINAL_SATURATION_ANALYSIS.md`): trần 200 chỉ cắt 93 dòng nhạc hiệu dùng chung;
  nâng trần, kể cả bỏ `--search-depth`, không lộ ứng viên đạt chuẩn nào và chi phí khớp không đổi.
  Đừng thêm «quét lại khúc chạm trần» hay nâng trần khi chưa có một ca dương thật.
- Lô giữ `data/tool.lock` suốt thời gian chạy và so định danh kho/chính sách ở MỖI lượt quét;
  lệch là dừng, không trộn hai phiên bản kho.
- Lô KHÔNG ghi `lichsu.db` (lượt dừng sớm sẽ làm Watch bỏ qua video mãi mãi) và chưa đẩy Sheets.
- Mỗi video tối đa 2 lượt quét; bộ điều phối luôn kết thúc. Mô phỏng 2.000 thế giới ngẫu nhiên
  trong `tests/test_nguon_chung_ke_hoach.py` khoá tính đúng/đủ.
- Khớp vân tay không phải xác nhận quyền sở hữu — giao diện phải nói rõ điều này.
