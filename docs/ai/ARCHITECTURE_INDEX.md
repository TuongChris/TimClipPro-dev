# Chỉ mục kiến trúc — TimClipPro

Mốc đối chiếu: `e49340d` (tree `2aee2510`). Lập 2026-10-09 từ object git (docstring module, số dòng, commit cuối
chạm file) — không phải audit lại mã. Thêm/xoá/đổi vai trò module → sửa bảng ở đây trong CÙNG commit.

## Bố cục repo
- `TimClipPro/` — toàn bộ mã ứng dụng (Python 3.12, Streamlit), test (`tests/`), tài liệu thiết kế (`docs/`),
  Apps Script (`apps_script/`), thư viện vendored `audfprint-master/` (KHÔNG sửa).
- `docs/ai/` — ngữ cảnh chung cho Claude Code trên PC1/PC2 (file này, trạng thái, quyết định, test, handoff).
- `.claude/rules/` — bất biến theo vùng (matcher, Sheets/outbox, updater); `.claude/settings.json` — quyền chặn chung;
  `.claude/launch.json` — xem trước: CHỈ gắn vào Development đang chạy ở cổng 8502, không tự khởi động (D-19).
- Gói Stable chỉ chứa mã chạy trong `TimClipPro/` (bỏ `tests/`, `docs/`, `apps_script/`, `.bat`, `CLAUDE.md`...):
  `release_tool.chon_file_phat_hanh`.
- `release/` — dữ liệu phát hành CÔNG KHAI, byte giữ nguyên (`.gitattributes`): `trusted_keys.json` (khoá công khai
  đang tin), `locks/` (lock CÓ BĂM runtime + launcher), `wheels/` (docopt), `git-hooks/pre-push` (dùng chung hai máy),
  `github/` (ruleset đề xuất), `trust/` (yêu cầu/uỷ quyền ghi danh khoá) — D-23…D-25.

## Điểm vào
| Lối vào | Gọi gì | Ghi chú |
|---|---|---|
| `ChayTool.bat` | `streamlit run app.py` bằng `.venv` | máy legacy (PC1 production) |
| `GiamSat.bat` | `cli.py watch --log [--sheet …]` | link Sheet đọc từ `SHEET_LINK` / `data\giam_sat_sheet.txt` |
| `ChayMayPhu.bat`, `thiet_lap_may_phu.py` | Watch trên «máy phụ» theo watchlist riêng | đường cũ, trước managed |
| `CapNhat.bat` → `cap_nhat.py` | tự cập nhật theo tag git `v<số>` | chỉ máy legacy; tắt ở dev/managed |
| `cai_dat.bat` | tạo `.venv` + cài thư viện | cài đặt legacy |
| `kiemtra.bat` | import + pytest + AppTest | cổng kiểm 1 lệnh |
| `launcher.py app/watch/cli/update/doctor` | cài đặt managed (PC2) | nằm NGOÀI release |
| `bootstrap.py` | dựng cài đặt managed mới | bộ cài one-click PC2 gọi nó |
| `release_tool.py lock/build/sign/verify/kiem-sau-ky/feed/kit/publish` | phát hành Stable trên PC1 HOẶC PC2 | `publish` chỉ in lệnh; `khoa-thu` chỉ tạo khoá THỬ; `tao-khoa`/`ky-uy-quyen` người dùng gõ mật khẩu |
| `uy_quyen_khoa.py xem/yeu-cau/ghi-danh/hoan-tac` | ghi danh khoá ký vào trust store của cài đặt managed | người dùng chạy (console thật); nạp launcher ĐÃ CÀI |
| `tests/dien_tap_phat_hanh.py <cau_hinh.json>` | diễn tập cập nhật trong sandbox managed | chạy tay trước khi phân phối (không phải pytest) |

## Module — bảng gốc (chuyển nguyên văn từ `TimClipPro/CLAUDE.md` bản e49340d)

| File | Vai trò | Sửa khi |
|---|---|---|
| `engine.py` | Lõi: cắt khúc, fingerprint, so khớp, gộp trùng, SQLite, xuất CSV | Thêm/đổi logic xử lý |
| `channel.py` | Đồng bộ kênh YouTube → kho audio nén + `clips_meta.json` | Đổi cách tải/nén/đặt tên |
| `ytdlp_chung.py` | Tuỳ chọn yt-dlp dùng chung: cookie, giãn nhịp, đường lui player client, diễn giải lỗi; cookie chỉ dùng khi máy giải được thử thách JavaScript (`kha_nang_js`: Node.js ≥ 22 + gói yt-dlp-ejs đúng bản yt-dlp ghim → `js_runtimes`) | Đổi bất cứ thứ gì liên quan yt-dlp; nâng yt-dlp thì nâng yt-dlp-ejs CÙNG lúc |
| `truy_cap_youtube.py` | THUẦN: phân loại lỗi YouTube, che bí mật, chẩn đoán cookie, bảng thử lại, `PhienYouTube` (cầu dao + số đo) | Đổi cách hiểu một lỗi YouTube / ngưỡng dừng |
| `youtube_doctor.py` | `cli.py youtube-doctor`: chẩn đoán chỉ đọc (mạng chỉ khi `--network`) | Thêm mục chẩn đoán |
| `cap_nhat.py` | (Đường cũ, máy legacy) tự cập nhật theo tag `v<số>`; tắt ở máy dev (`data/dev_mode`) và bản managed | Đổi cách cập nhật máy legacy |
| `sheets.py` | Tiện ích Google Sheets (gspread + service account): kiểm tiêu đề nghiêm ngặt, ghi danh sách video | Đổi cách ghi báo cáo |
| `runtime_paths.py` | Phân giải thư mục trạng thái: `legacy` (y như cũ) / `managed` (state root + `installation.json`, thiếu là dừng) | Đổi nơi lưu dữ liệu / cách cài đặt |
| `sheet_destinations.py` | Hồ sơ đích Google Sheets (revision bất biến), binding khoá theo principal, ghim `DichGuiChot` | Đổi cách chọn/ghim nơi gửi |
| `outbox.py` | Hàng đợi gửi Sheets LƯU BỀN trong `lichsu.db`, người gửi duy nhất, transport gspread | Đổi cách gửi / thử lại |
| `ui_gui_sheets.py` | Giao diện chọn đích cạnh nút Bắt đầu + tab «📤 Gửi Google Sheets» | Đổi giao diện gửi |
| `maintenance_gate.py` | Cổng bảo trì: lease cho mọi việc, updater rút cổng + chờ rảnh (không giết việc) | Đổi điều kiện được cập nhật |
| `managed_update.py` | Cập nhật Stable có chữ ký (PC2): chính sách, giải nén an toàn, nhật ký, kích hoạt, quay lại | Đổi cách nhận/áp dụng bản mới |
| `health_check.py` | Kiểm sức khoẻ một release (tiến trình riêng, chặn mạng, DB thật chỉ đọc) + migrate | Đổi điều kiện «bản mới khoẻ» |
| `launcher.py` | Điểm vào ổn định của cài đặt managed (app/watch/cli/update/doctor) — nằm NGOÀI release | Đổi cách mở/chạy bản managed |
| `ui_cap_nhat.py` | «ℹ️ Phiên bản và cập nhật» (chỉ đọc + hoãn) | Đổi giao diện cập nhật |
| `bootstrap.py` | Dựng cài đặt managed MỚI cho PC2 (định danh riêng, launcher, khoá tin cậy, lịch xem trước) | Đổi quy trình cài PC2 |
| `release_tool.py` | Phát hành Stable trên PC1 hoặc PC2: build từ git tree, ký, verify, kiểm sau ký, ZIP feed, bộ kit, lock; khoá mỗi máy (`tao-khoa`), ký/kiểm uỷ quyền | Đổi quy trình phát hành |
| `uy_quyen_khoa.py` | Ghi danh khoá ký vào trust store của MỘT cài đặt managed theo uỷ quyền có chữ ký (yêu cầu tự ký, ràng buộc cài đặt + trust store, ghi nguyên tử, hoàn tác) | Đổi cách tin khoá mới (`docs/UY_QUYEN_KHOA.md`) |
| `danh_sach_video.py` | Liệt kê tên video thật của một kho (chỉ đọc, offline) rồi ghi đè lên trang tính riêng | Đổi cách kiểm kê kho / cột danh sách |
| `app.py` | Giao diện Streamlit 7 tab | Đổi giao diện |
| `cli.py` | Giao diện dòng lệnh, dùng chung engine | Thêm lệnh tự động hoá |
| `bao_cao_v2.py` | THUẦN: chính sách báo cáo V2 — ảnh chụp `BaoCaoV2`, mốc/link, URL gốc `watch?v=`, ngày nguyên bản, dòng 34/16 cột + phạm vi | Đổi cách trình bày báo cáo lượt quét mới |
| `common_original.py` | Chế độ «Một video gốc chung cho cả lô» — phần THUẦN: bằng chứng, kết luận, lập kế hoạch, báo cáo | Đổi luật kết luận / chọn nguồn chung |
| `common_original_jobs.py` | Bộ điều phối lô nguồn chung: luồng nền, `tool.lock`, lấy thông tin trước, snapshot | Đổi cách chạy lô nguồn chung |

## Module khác (vai trò lấy từ docstring đầu file tại e49340d)

| File | Vai trò (docstring) | Dòng | Commit cuối |
|---|---|---|---|
| `audfprint_progress_runner.py` | Adapter quan sát audfprint mà không sửa source vendored. | 452 | `8f0558f 2026-10-02` |
| `bang_ngang.py` | Dựng một dòng báo cáo ngang cho mỗi video vi phạm. | 131 | `35c7fc1 2026-10-04` |
| `cau_hinh.py` | Lưu tùy chọn người dùng; không lưu khóa API, mật khẩu hay nội dung google_key.json. | 72 | `354da23 2026-08-19` |
| `chan_doan_quet.py` | Chẩn đoán phễu phát hiện của một lượt quét. | 287 | `7f85c8d 2026-08-21` |
| `chap_nhan_khop.py` | Tiêu chí CHẤP NHẬN một ứng viên đã gộp vào báo cáo. | 140 | `7a6fa4c 2026-08-07` |
| `chong_bong_lap.py` | Chống «bóng» của âm thanh lặp khi gộp mảnh khớp — phần thuần của `Engine._merge` (P0, D-27; `docs/BONG_AM_THANH_LAP.md`). | 252 | `fix/pc2/chong-bong-lap` (PC2: viết 10/10, đưa lên `fe461bd` 25/10) |
| `chia_watchlist.py` | chia_watchlist.py — Chia watchlist thành N phần cho N máy chạy song song. | 109 | `1682ce6 2026-08-08` |
| `clip_metadata.py` | Resolver metadata clip gốc độc lập UI, I/O mạng và thuật toán fingerprint. | 1147 | `35c7fc1 2026-10-04` |
| `don_dep.py` | Quản lý vòng đời kho đệm và thư mục job quét theo tuổi/ngân sách dung lượng. | 243 | `0a4a572 2026-08-21` |
| `dong_goi.py` | dong_goi.py — Đóng gói MÃ NGUỒN dự án để gửi audit. | 301 | `8f0558f 2026-10-02` |
| `dong_goi_may_chay.py` | dong_goi_may_chay.py — Đóng gói bản CHẠY ĐƯỢC để đem sang máy khác. | 292 | `8f0558f 2026-10-02` |
| `dossier.py` | Mô hình dữ liệu và hàm dựng hồ sơ vi phạm. | 165 | `c7c78bc 2026-10-05` |
| `dung_lai.py` | Gom tín hiệu dừng từ hệ điều hành, Engine và file điều khiển. | 56 | `448b467 2026-08-07` |
| `fingerprint_progress.py` | Progress contract, aggregation, logging and UI-safe job controller. | 593 | `448b467 2026-08-07` |
| `giam_sat_tai.py` | Giám sát MỘT lượt tải audio của yt-dlp bằng một luồng phụ nhỏ (chu kỳ 1 giây). | 253 | nhánh `fix/pc2/live-progress-smart-marathon` (PC2, 13/10) |
| `khoa.py` | Khóa liên tiến trình dựa trên cơ chế khóa file của hệ điều hành. | 124 | `448b467 2026-08-07` |
| `kiem_header.py` | kiem_header.py — Đối chiếu HEADER_NGANG trong code với tiêu đề THẬT trong Google Sheet. | 67 | `448b467 2026-08-07` |
| `kiem_metadata_kho.py` | Audit metadata kho clip theo chế độ chỉ đọc; chỉ ghi snapshot khi có --apply. | 360 | `8f0558f 2026-10-02` |
| `kiem_ngang.py` | (không có docstring) | 77 | `448b467 2026-08-07` |
| `kiem_ngay_dang.py` | Audit và sửa ngày đăng trong clips_meta.json của một kho clip gốc. | 372 | `2cdd1d3 2026-10-03` |
| `kiem_sheet.py` | kiem_sheet.py — Ghi THỬ một dòng giả vào Google Sheet để kiểm tra dữ liệu có rơi đúng cột. | 93 | `448b467 2026-08-07` |
| `kiem_thoi_luong.py` | Kiểm tra và bổ sung độ dài media thật cho metadata clip gốc. | 193 | `8f0558f 2026-10-02` |
| `lich_su.py` | Lược đồ ``lichsu.db`` có phiên bản — lịch sử quét gắn với KHO (audit TCP-07). | 424 | `c981450 2026-10-08` |
| `luu_tru.py` | Đọc và ghi dữ liệu cấu hình theo cách nguyên tử, có khả năng phục hồi. | 330 | `8f0558f 2026-10-02` |
| `nhat_ky.py` | Ghi song song console và file log, đồng thời quản lý thời hạn lưu log. | 188 | `f95345c 2026-10-03` |
| `process_runner.py` | Subprocess runner đọc output liên tục, heartbeat khi im lặng và hủy đúng cây PID. | 662 | `8f0558f 2026-10-02` |
| `publication_date.py` | Nguồn chân lý duy nhất cho “Ngày đăng video”. | 294 | `6cad9d9 2026-08-07` |
| `scan_jobs.py` | Điều phối một batch quét: tiến độ, kết quả streaming, trạng thái giao Sheets. | 398 | `ce5a64b 2026-10-07` |
| `scan_ui.py` | Dựng dữ liệu bảng trạng thái quét. **Không import streamlit.** | 234 | `83fb6c3 2026-10-07` |
| `thiet_lap_may_phu.py` | thiet_lap_may_phu.py — Chạy MỘT LẦN trên máy phụ sau khi giải nén gói. | 143 | `8f0558f 2026-10-02` |
| `tien_do_quet.py` | Tiến độ THẬT của một lô quét: số đo từ pipeline, nhịp sống, nhật ký ngắn. | 278 | nhánh `fix/pc2/live-progress-smart-marathon` (PC2, 13/10) |
| `toc_do_khop.py` | Phát hiện video vi phạm đã bị ĐỔI TỐC ĐỘ để né vân tay âm thanh. | 253 | `1f85c79 2026-08-07` |
| `ui_tien_do_quet.py` | Màn hình tiến độ khi ĐANG quét (Streamlit) — chỉ ĐỌC ảnh chụp ``scan_jobs.BatchSnapshot``. | 146 | nhánh `fix/pc2/live-progress-smart-marathon` (PC2, 13/10) |
| `watch.py` | Mô hình dữ liệu và lưu trữ danh sách nguồn YouTube cần theo dõi. | 729 | `ce5a64b 2026-10-07` |

## Bộ giả và dữ liệu test dùng chung (`TimClipPro/tests/`)
`conftest.py` (cách ly `__main__`, thư mục tạm), `golden_quet.py` + `golden/` (golden hành vi quét cũ, sinh trên
`f87cc85`), `sheets_http_gia.py` (máy chủ Google Sheets GIẢ ở tầng HTTP, gspread thật), `outbox_gia.py`, `kho_gia.py`,
`ytdlp_gia.py`, `cap_nhat_gia.py`.

## Tài liệu thiết kế (`TimClipPro/docs/` trừ khi ghi khác) — đọc theo vùng của task

Cột «Cuối» = commit cuối chạm file (tính tới e49340d). Bốn bản đồ cũ được đánh dấu theo số module KHÔNG được nhắc tới
(đếm bằng tên file, 54 module tại e49340d): dùng cho phần cũ, đừng coi là nguồn chân lý cho managed/outbox/báo cáo V2/nguồn chung/
YouTube — dùng bảng module ở trên.

| Tài liệu | Nhóm | Dòng | Cuối | Ghi chú |
|---|---|---|---|---|
| `AUDIT_REPORT.md` | Audit cũ | 258 | 448b467 2026-08-07 |  |
| `CLAUDE_AUDIT_REPORT.md` | Audit cũ | 490 | 448b467 2026-08-07 |  |
| `CLAUDE_VALIDATION_REPORT.md` | Audit cũ | 353 | 448b467 2026-08-07 |  |
| `FUTURE_DEVELOPMENT_READINESS.md` | Audit cũ | 765 | 4b7e5bd 2026-09-07 |  |
| `PROJECT_MASTER_AUDIT.md` | Audit cũ | 996 | 4b7e5bd 2026-09-07 |  |
| `CLIP_METADATA_ARCHITECTURE.md` | Báo cáo / metadata | 421 | 448b467 2026-08-07 |  |
| `PUBLICATION_DATE_ARCHITECTURE.md` | Báo cáo / metadata | 187 | 6cad9d9 2026-08-07 |  |
| `PUBLICATION_DATE_AUDIT.md` | Báo cáo / metadata | 171 | 6cad9d9 2026-08-07 |  |
| `REPORT_POLICY_V2.md` | Báo cáo / metadata | 196 | 6dc3f9d 2026-10-05 |  |
| `REPORT_POLICY_V2_VALIDATION.md` | Báo cáo / metadata | 136 | 6dc3f9d 2026-10-05 |  |
| `DATA_FLOW.md` | Bản đồ hệ thống | 835 | 4b7e5bd 2026-09-07 | lỗi thời một phần: không nhắc 27/54 module |
| `MODULE_MAP.md` | Bản đồ hệ thống | 588 | 4b7e5bd 2026-09-07 | lỗi thời một phần: không nhắc 15/54 module |
| `SYSTEM_MAP.md` | Bản đồ hệ thống | 941 | 4b7e5bd 2026-09-07 | lỗi thời một phần: không nhắc 23/54 module |
| `SYSTEM_OVERVIEW.md` | Bản đồ hệ thống | 160 | b776082 2026-08-20 | lỗi thời một phần: không nhắc 36/54 module |
| `DATA_MIGRATION_AND_RECOVERY.md` | Hardening sau audit 4b7e5bd | 207 | f87cc85 2026-10-02 |  |
| `HARDENING_FIX_MATRIX.md` | Hardening sau audit 4b7e5bd | 172 | f87cc85 2026-10-02 |  |
| `HARDENING_PLAN.md` | Hardening sau audit 4b7e5bd | 276 | f87cc85 2026-10-02 |  |
| `HARDENING_VALIDATION_REPORT.md` | Hardening sau audit 4b7e5bd | 194 | f87cc85 2026-10-02 |  |
| `CHANGELOG.md` | Lịch sử / kế hoạch cũ | 14 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `CHANGELOG_OPTIMIZATION.md` | Lịch sử / kế hoạch cũ | 545 | 1682ce6 2026-08-08 | lịch sử — không dùng làm nguồn chân lý |
| `CLAUDE_HANDOFF.md` | Lịch sử / kế hoạch cũ | 274 | 1682ce6 2026-08-08 | lịch sử — không dùng làm nguồn chân lý |
| `CLAUDE_HANDOFF_2026-09.md` | Lịch sử / kế hoạch cũ | 1027 | f87cc85 2026-10-02 | lịch sử — không dùng làm nguồn chân lý |
| `EXECUTION_PLAN.md` | Lịch sử / kế hoạch cũ | 193 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `EXECUTION_PLAN.md (gốc repo)` | Lịch sử / kế hoạch cũ | 275 | 2a06090 2026-08-06 | lịch sử — không dùng làm nguồn chân lý |
| `EXECUTION_PLAN_B.md` | Lịch sử / kế hoạch cũ | 438 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `EXECUTION_PLAN_C.md` | Lịch sử / kế hoạch cũ | 351 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `EXECUTION_PLAN_D.md` | Lịch sử / kế hoạch cũ | 514 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `EXECUTION_PLAN_E.md` | Lịch sử / kế hoạch cũ | 378 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `OPTIMIZATION_PLAN.md` | Lịch sử / kế hoạch cũ | 97 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `PHASE2_FIX_PLAN.md` | Lịch sử / kế hoạch cũ | 355 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `PROMPT_CONTRACT.md` | Lịch sử / kế hoạch cũ | 76 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `PROMPT_CONTRACT.md (gốc repo)` | Lịch sử / kế hoạch cũ | 76 | 2a06090 2026-08-06 | lịch sử — không dùng làm nguồn chân lý |
| `SETUP_VSCODE.md` | Lịch sử / kế hoạch cũ | 78 | b776082 2026-08-20 | lịch sử — không dùng làm nguồn chân lý |
| `SETUP_VSCODE.md (gốc repo)` | Lịch sử / kế hoạch cũ | 78 | b776082 2026-08-20 | lịch sử — không dùng làm nguồn chân lý |
| `TEST_REPORT.md` | Lịch sử / kế hoạch cũ | 489 | 1682ce6 2026-08-08 | lịch sử — không dùng làm nguồn chân lý |
| `TimClipPro/.github/copilot-instructions.md` | Lịch sử / kế hoạch cũ | 30 | 448b467 2026-08-07 | lịch sử — không dùng làm nguồn chân lý |
| `HUONG_DAN_PC2.md` | Managed runtime / PC2 | 143 | 78ba20c 2026-10-08 | lỗi thời một phần: đường dẫn `D:\TimClipPro…` của kế hoạch cũ — cài đặt thật dùng `C:\TimClipPro*` (`docs/ai/handoff/PC2.md`) |
| `KE_HOACH_PILOT_PC2.md` | Managed runtime / PC2 | 53 | 6461327 2026-10-08 |  |
| `MANAGED_HIEU_NANG.md` | Managed runtime / PC2 | 46 | f4d3cb7 2026-10-08 |  |
| `MANAGED_RUNTIME_DESIGN.md` | Managed runtime / PC2 | 308 | 6461327 2026-10-08 |  |
| `MANAGED_UPDATE.md` | Managed runtime / PC2 | 200 | 6461327 2026-10-08 |  |
| `UY_QUYEN_KHOA.md` | Managed runtime / phát hành | — | 2026-10-14 | hai máy ngang quyền ký: giao thức ghi danh khoá (Phase A + thiết kế) |
| `PHAT_HANH_HAI_MAY.md` | Managed runtime / phát hành | — | 2026-10-14 | quy trình phát hành + khôi phục, chạy trên PC1 hoặc PC2 |
| `INSTALL_WINDOWS.md` | Máy legacy | 199 | 448b467 2026-08-07 |  |
| `TRIEN_KHAI_MAY_PHU.md` | Máy legacy | 165 | 1682ce6 2026-08-08 |  |
| `TU_CAP_NHAT.md` | Máy legacy | 119 | 451e382 2026-08-19 |  |
| `LOI_DA_GAP.md` | Ngữ cảnh Claude | 488 | mới 09/10 | chuyển nguyên văn từ CLAUDE.md (mục 1–17) |
| `TimClipPro/CLAUDE.md` | Ngữ cảnh Claude | 198 | 09/10 | chuẩn hoá 09/10: 782 → 198 dòng (xem đầu file) |
| `COMMON_ORIGINAL_DESIGN.md` | Quét / so khớp / vân tay | 187 | 7ee527a 2026-10-04 |  |
| `COMMON_ORIGINAL_SATURATION_ANALYSIS.md` | Quét / so khớp / vân tay | 194 | 7ee527a 2026-10-04 |  |
| `COMMON_ORIGINAL_VALIDATION.md` | Quét / so khớp / vân tay | 116 | 3218aff 2026-10-03 |  |
| `DA_TOC_DO.md` | Quét / so khớp / vân tay | 202 | 1f85c79 2026-08-07 |  |
| `DURATION_ARCHITECTURE.md` | Quét / so khớp / vân tay | 142 | 1703684 2026-08-08 |  |
| `DURATION_DRIFT_AUDIT.md` | Quét / so khớp / vân tay | 181 | eb4a947 2026-08-08 |  |
| `FAST_TOP1_SCAN.md` | Quét / so khớp / vân tay | 196 | 1f85c79 2026-08-07 |  |
| `FINGERPRINT_PROGRESS_ARCHITECTURE.md` | Quét / so khớp / vân tay | 204 | 448b467 2026-08-07 |  |
| `FINGERPRINT_RECOVERY_ARCHITECTURE.md` | Quét / so khớp / vân tay | 245 | a43296c 2026-09-07 |  |
| `JOEBARTOLOZZI_FAILURE_FORENSICS.md` | Quét / so khớp / vân tay | 302 | a43296c 2026-09-07 |  |
| `MATCH_ACCEPTANCE_ARCHITECTURE.md` | Quét / so khớp / vân tay | 168 | 7a6fa4c 2026-08-07 |  |
| `MATCH_SELECTION_ARCHITECTURE.md` | Quét / so khớp / vân tay | 230 | 2bbb7f9 2026-08-07 |  |
| `SCAN_PIPELINE_V2_DESIGN.md` | Quét / so khớp / vân tay | 101 | 6cad9d9 2026-08-07 |  |
| `SCAN_THREADING_AND_STATE.md` | Quét / so khớp / vân tay | 188 | 8cb2597 2026-08-07 |  |
| `ZERO_MATCH_ROOT_CAUSE.md` | Quét / so khớp / vân tay | 307 | 1f85c79 2026-08-07 |  |
| `README.md (gốc repo)` | Vận hành / người dùng | 19 | b776082 2026-08-20 |  |
| `RUNBOOK.md` | Vận hành / người dùng | 578 | f87cc85 2026-10-02 |  |
| `TimClipPro/HUONG_DAN.md` | Vận hành / người dùng | 467 | b776082 2026-08-20 |  |
| `TimClipPro/README.md` | Vận hành / người dùng | 88 | b776082 2026-08-20 |  |
| `TimClipPro/apps_script/README.md` | Vận hành / người dùng | 137 | b776082 2026-08-20 |  |
| `YOUTUBE_ACCESS_RELIABILITY.md` | YouTube | 145 | fe07985 2026-10-03 |  |
