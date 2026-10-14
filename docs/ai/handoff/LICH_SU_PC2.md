# Lịch sử handoff — PC2

Mục cũ chuyển từ `docs/ai/handoff/PC2.md` khi file đó chạm giới hạn 80 dòng hoặc «Nhật ký» quá 6 mục. Mới hơn ở trên.
Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

### 2026-10-13 — video dài: giới hạn quét + tiến độ thật + Dừng giết ffmpeg + tải phần đầu nhanh (marathon, CHƯA đẩy)
- Bối cảnh (Stable, video 65 giờ): «0/5 — 1%» hàng chục phút — ffmpeg (yt-dlp FFmpegFD) tải 3 giờ đầu ~17 KB/s, không phát
  tiến độ; Dừng không giết ffmpeg; mã cũ không thấy đủ bằng chứng thì tải TRỌN 65 giờ.
- Làm (worktree `C:\Dev\TimClipPro_Marathon`, từ `7a76e71`, KHÔNG P0/Sheets): video dài theo LÔ (`engine.GHVD_*`, >6 giờ →
  3/6 giờ đầu, không tự tải trọn, kiểm gói audio CUỐI — không tin `format.duration`, đệm cụt tải lại 1 lần); `giam_sat_tai`
  (`-progress`; Dừng giết ffmpeg; 180 s không thêm byte → «Mạng đứng»); `tien_do_quet`/`ui_tien_do_quet` (số đo thật, nhịp ≠
  tiến triển, ETA từ tốc độ đo); `scan_jobs` nhận lại lô khi tải lại trang; «Mã tab» toàn chuỗi. Watch/CLI giữ hành vi cũ.
- `13f9511` tải phần đầu CHẬM (pilot thật OPgD5wl0fAY 66 giờ: 2,03×, 3 giờ đầu mất 1 giờ 30): ffmpeg xin MỘT `Range: bytes=0-`,
  googlevideo nhả theo nhịp phát; yt-dlp tải thường xin khối 10 MiB. Sửa: ffmpeg `-request_size 10485760` (tuỳ chọn ĐẦU VÀO;
  ffmpeg cũ thiếu → cách cũ + ghi rõ). A/B thật (người dùng duyệt): một yêu cầu mở 0,7× → khối 10 MiB 1280×, 2400,01 s đủ.
- Test (chặn mạng, cp1252): nhanh 2508 = 2506/2/0, chậm 18/18 (ở `53c8f3a`); `13f9511`: đỏ 7/8 → xanh 12/12 (Range thật, máy
  chủ hãm kiểu googlevideo), hồi quy liên quan 482/482. Development 8502 (`ChayTimClipPro_Dev_Marathon.bat`, ngoài Git), kho
  SML 779 clip (vân tay trong DevState). Bằng chứng: `C:\Dev\pc2_test_runs\2026-10-13_marathon*`, `…_tai_nhanh`.
- Nghiệm thu thật 16:02–16:05 (duyệt; Development 8502, SML 779): tải 3 giờ 9,0 s, âm thanh đủ 10800,01 s, cắt 15 s, khớp 146 s;
  tổng 3 phút 03; 5 kết quả = lượt trước, mốc lệch ≤ 0,094 s; phạm vi «Một phần 0–3 giờ»; outbox 0. Tiếp: duyệt đẩy + PR.
### 2026-10-09 — test bảng mã cp1252 của health_check (nhánh fix/pc2/windows-health-encoding)
- Làm: PC2 (cp1252) hỏng `test_chan_mang_truoc_khi_import`: test gọi thẳng `chan_mang()` rồi print tiếng Việt, bỏ
  `_utf8_dau_ra()` của `main()` — lỗi của test; production đúng (launcher ép UTF-8; `main` và `cli` đổi stdout). Chỉ
  sửa `tests/test_health_check.py`: test cũ chạy đúng thứ tự `main()`, ép cp1252/utf-8; +3 test hồi quy × 2 bảng mã.
- Commit: `da66f0e` (trên `c1f19d8`); commit chứa chính mục này: `b627af0` (PR #1, gộp 10/10).
- Test (clone tạm, chặn mạng, cp1252): health_check 12/12; đột biến `_utf8_dau_ra` no-op → 2 đỏ, launcher bỏ biến
  UTF-8 → 1 đỏ; ruff sạch; nhanh 2460 = 2458 đạt / 2 bỏ qua (symlink cần quyền; file đang mở) / 0 hỏng (junit ngoài
  Git: `C:\Dev\pc2_test_runs\2026-10-09_fix_encoding`); chậm 14/14 ở `c1f19d8` — chỉ đổi test nên không chạy lại.
- Còn mở / rủi ro: chưa đẩy được (khoá CHỈ ĐỌC). PC2 chưa đặt git `user.name`/`user.email` (commit tạm dùng tên PC1).
- Tiếp theo: người dùng duyệt giai đoạn 2 → đẩy nhánh + PR; PC1 review, merge; PC1 xác minh Stable đã cài trên PC2.
### 2026-10-09 — Thiết lập giai đoạn 1 (PC2 ghi ở «Tiếp theo» cũ; PC1 chuyển nguyên ý xuống đây 10/10)
- Clone CHỈ ĐỌC `C:\Dev\Tool_Quet` (`git remote -v` chỉ `private`; `push --dry-run` bị từ chối «read only»);
  `CLAUDE.local.md` + `.claude/settings.local.json`; ngữ cảnh nạp đủ 4 file; venv `TimClipPro\.venv` từ Python 3.12.10
  gốc; FFmpeg 9.0.1 có trên PATH (winget). Người dùng báo Stable 1.0.0 đã cài và chạy.
