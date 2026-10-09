---
paths:
  - "TimClipPro/outbox.py"
  - "TimClipPro/sheet_destinations.py"
  - "TimClipPro/sheets.py"
  - "TimClipPro/ui_gui_sheets.py"
  - "TimClipPro/lich_su.py"
  - "TimClipPro/kiem_sheet.py"
  - "TimClipPro/kiem_header.py"
  - "TimClipPro/kiem_ngang.py"
  - "TimClipPro/bang_ngang.py"
  - "TimClipPro/danh_sach_video.py"
  - "TimClipPro/GiamSat.bat"
  - "TimClipPro/apps_script/**"
  - "TimClipPro/tests/sheets_http_gia.py"
  - "TimClipPro/tests/outbox_gia.py"
  - "TimClipPro/tests/test_outbox*.py"
  - "TimClipPro/tests/test_ghi_theo_ma_tab.py"
  - "TimClipPro/tests/test_ghim_tab_truoc_khi_gui.py"
  - "TimClipPro/tests/test_viec_cu_khong_ma_tab.py"
  - "TimClipPro/tests/test_sheet_destinations.py"
  - "TimClipPro/tests/test_sheets_session.py"
  - "TimClipPro/tests/test_ui_gui_sheets.py"
  - "TimClipPro/tests/test_lich_su_v*.py"
  - "TimClipPro/tests/test_bao_cao_v2_sheets*.py"
  - "TimClipPro/tests/test_bao_cao_v2_apps_script.py"
  - "TimClipPro/tests/test_giam_sat_bat.py"
---
# Quy tắc vùng GOOGLE SHEETS / OUTBOX

Tự nạp khi đọc/sửa file khớp `paths` ở trên. Bất biến chung (kể cả «Báo cáo V2») vẫn ở `TimClipPro/CLAUDE.md`.

## An toàn — luôn đúng
- KHÔNG gọi Google Sheets thật khi phát triển hay chạy test. Test dùng máy chủ Sheets GIẢ ở tầng HTTP + gspread thật
  (`tests/sheets_http_gia.py`, mẫu `tests/test_outbox_gspread.py`). Gửi thật chỉ khi người dùng duyệt riêng, có kế hoạch thử.
- Không in, không ghi log, không commit link Google Sheet thật, `google_key.json` hay nội dung khoá. Link của Giám sát
  đọc từ `SHEET_LINK` hoặc `data\giam_sat_sheet.txt` (ngoài Git) — không ghi cứng vào `.bat` (commit `86e6bff`).
- Đổi lược đồ `lichsu.db`: tăng phiên bản lược đồ + test migrate (mẫu `tests/test_lich_su_v4.py`); không thêm cột vào `jobs`.

## Test (chi tiết: `docs/ai/TEST_MATRIX.md`, hàng «Sheets / outbox»)
- Đổi transport, trạng thái, lược đồ: suite nhanh + kiểm đột biến outbox (mốc: 123/123 đột biến bị bắt trên e49340d).

## Tài liệu (`TimClipPro/docs/`)
`MANAGED_RUNTIME_DESIGN.md` §2, §5, §6, §10; `REPORT_POLICY_V2.md` (gửi Sheets V2); `TimClipPro/apps_script/README.md`.

Phần dưới đây chuyển NGUYÊN VĂN từ `TimClipPro/CLAUDE.md` (bản e49340d); đường dẫn `docs/…` tính từ `TimClipPro/`.

## Hàng đợi gửi Google Sheets (outbox) — bất biến

Thiết kế: `docs/MANAGED_RUNTIME_DESIGN.md` §5, §10. Những điều KHÔNG được phá:

- Việc gửi chèn trong CÙNG giao dịch `save_job` (`_xep_hang_gui`), payload tuần tự hoá ngay lúc đó.
  Không có đường gửi Sheets nào khác cho kết quả quét — đừng thêm lại «gửi đồng bộ» hay «gửi lại cả
  lô bằng link hiện tại» (H14).
- Đích GHIM theo lượt: `DichGuiChot` (JSON chuẩn hoá của revision hồ sơ + tab ID + schema + binding
  khoá + workspace) lưu trong từng dòng; người gửi, thử lại, khởi động lại chỉ đọc bản ghim đó, không
  bao giờ đọc hồ sơ/lựa chọn HIỆN TẠI. Sửa hồ sơ = revision mới; xoá hồ sơ còn việc bị chặn.
- `SENDING` commit TRƯỚC request ghi. Không bao giờ tự quay `SENDING` → `PENDING`; khởi động lại thì
  `SENDING` → `UNKNOWN_DELIVERY`. Chỉ lỗi CHỨNG MINH chưa ghi (trước dispatch, không mở được kết nối,
  HTTP 4xx trừ 408) mới thử lại/chặn; phân loại theo KIỂU ngoại lệ (`outbox.phan_loai_loi`), đừng so
  chuỗi message. `UNKNOWN_DELIVERY` chỉ người dùng xử lý (đã có trên Sheet / gửi lại chấp nhận trùng).
- Một người gửi mỗi state root (`data/hang_doi_gui.lock`); mọi cập nhật sau claim có điều kiện
  `claim_token`. `SENT` chỉ khi biên nhận khớp: `spreadsheetId` + `replies` của `batchUpdate` nguyên tử, và mã tab +
  dòng TRONG THÂN REQUEST đã phát (`KetQuaGui.yeu_cau`) = mã vừa chốt + payload. AppendCells không trả vùng ghi —
  đừng dựng `updatedRange`/`updatedRows` giả cho biên nhận.
- «Kiểm cấu hình» CHỈ ĐỌC: không tạo tab, không chèn tiêu đề; tab định danh bằng ID (gid).
- Mã tab CHỐT theo revision (`dich_gui_tab_chot`, lần đầu thắng) TRONG CÙNG giao dịch CLAIMED→`SENDING`,
  TRƯỚC request ghi đầu tiên (`NguoiGui._bat_dau_gui`); chốt lỗi / mã khác tab vừa tìm / mất claim → không
  gửi. Đừng chuyển việc chốt về sau `SENT` hay bọc nó trong `suppress`: đó là MR-P1-02 của audit độc lập
  f4d3cb7 — UNKNOWN hoặc lỗi chốt làm lần gửi sau tìm lại theo TÊN và rơi vào tab mới cùng tên. Từ đó mọi lần
  gửi theo mã đó (tab đổi tên vẫn đúng chỗ; tab cùng tên tạo lại không bao giờ là tab cũ; tab bị xoá → chặn).
  Biên nhận phải khớp ĐÚNG mã vừa chốt. Việc đã phát mà không có mã của CHÍNH nó → không gửi lại (xem dưới).
  Đừng đọc hồ sơ HIỆN TẠI để chọn tab. Link cũ (`--sheet`, SHEET_LINK, `giam_sat_sheet.txt`) LUÔN là tab tên «KetQuaQuet» như bản
  cũ — gid trong link cũ bị bỏ qua (thường là tab đầu "Sheet1"). Hồ sơ có gid: tên tab là nhãn đối chiếu,
  lần gửi đầu mà tab mang tên khác thì chặn (dán nhầm link tab).
- Transport (`CongGspread`): sau bước tìm tab, MỌI request chạm nội dung tab định tuyến bằng `sheetId` — đọc tiêu
  đề qua `values:batchGetByDataFilter` (`_TabTheoMa`), ghi bằng MỘT `spreadsheets.batchUpdate` AppendCells{sheetId}
  (`dung_yeu_cau_ghi`). Đừng dùng `Worksheet.append_rows`/`append_row`/`get_values`/`update` của gspread trong outbox:
  chúng dựng range A1 từ TÊN tab — đổi tên + tạo tab trùng tên giữa lúc kiểm và lúc ghi làm dòng rơi sang tab khác
  mà vẫn SENT (MR-R2-P1-01, tái audit 78ba20c). Ô gửi RAW-tương-đương (`dung_o`): chuỗi → `stringValue`, KHÔNG BAO
  GIỜ `formulaValue`; ô NaN/vô cực → `BLOCKED_REPORT` trước mọi request.
- Mã tab của TỪNG LẦN PHÁT (`hang_doi_gui.gui_worksheet_id`, lược đồ v4) ghi cùng giao dịch `SENDING` và bất biến
  (phát lại phải đúng mã đó). Việc bản cũ phát theo tên (cột NULL, hồ sơ không có mã) KHÔNG BAO GIỜ được gửi lại:
  mã chốt của revision có thể do việc KHÁC tạo SAU (MR-R2-P2-01). Đừng suy nơi một việc đã ghi từ
  `dich_gui_tab_chot`; dùng `outbox._ma_tab_da_phat`.
- Phân loại lỗi: `gspread.open_by_key` gặp HTTP 403 ném `PermissionError` (là `OSError`!) — lỗi CẤU HÌNH
  (chưa chia sẻ bảng), phải xét TRƯỚC nhánh mạng. `RefreshError` theo cờ `retryable`. Không suy "chưa
  gửi" từ `__context__`/`__cause__`.
- Tạm dừng hồ sơ = tạm dừng GỬI: lượt mới vẫn ghim được, việc xếp hàng chờ. Lưu trữ = không nhận lượt mới
  (việc đã ghim vẫn gửi). Một hồ sơ tạm dừng/nhóm đang hoãn không được chiếm suất của vòng gửi (lọc trong
  SQL; hoãn nhóm lưu vào `thu_lai_sau`).
- Dừng người gửi = không nhận việc mới + CHỜ việc đang bay xong (`NguoiGuiNen.HAN_DUNG_S`); thoát giữa lúc
  request đang bay biến việc thành KHÔNG RÕ.
- Kết quả V2 lỗi / luật cũ → `BLOCKED_REPORT` không payload — không bao giờ gửi theo luật cũ.
- Hồ sơ không chứa khoá riêng/token; binding đổi principal là bị chặn, không rơi về khoá mặc định.
  Thông báo lỗi không chứa nội dung file khoá hay nguyên URL bảng.
