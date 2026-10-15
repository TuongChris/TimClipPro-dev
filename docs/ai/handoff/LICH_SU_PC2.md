# Lịch sử handoff — PC2

Mục cũ chuyển từ `docs/ai/handoff/PC2.md` khi file đó chạm giới hạn 80 dòng hoặc «Nhật ký» quá 6 mục. Mới hơn ở trên.
Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

### 2026-10-15 — review độc lập PR #6 + khoá phát hành PC2 + yêu cầu ghi danh (nhánh feature/pc2/khoa-ky-pc2)
- Review PR #6 (`c81326b`) trên PC2, không dùng số của PC1: không P0/P1. Nhanh 2708/2/0, chậm 19/19, ruff sạch. Đột biến
  PC2 tự chọn 20 chốt an toàn: 19 bị bắt; M17 (bỏ so key_id gõ ở CLI `ky-uy-quyen`) sống → thêm test CLI (commit test
  trên nhánh này), nay bị bắt. Build lại 1.1.1 từ `dc29b33` chỉ bằng repo = gói `510f39a6…` trùng byte; `verify` +
  `kiem-sau-ky` bản 1.1.1 đã công bố 10/10. `release/trusted_keys.json` = trust store bộ kit đã cài PC2 (`a37dc9b6…`);
  launcher đã cài = blob `e49340d`, đọc trust store mỗi lần chạy. Ruleset GitHub hiện KHÔNG có (API công khai) — chưa bật.
- Khoá PC2: người dùng chạy `.bat` (công cụ = blob `c81326b`; venv từ `release/locks/launcher-lock.txt` cài offline có băm;
  thư mục khoá chỉ tài khoản người dùng + SYSTEM, tắt thừa kế; thử giả 24/24) → key_id `d02702dd741c3e4f`, Ed25519
  `ZtXkLr8QOo1sp1YAPpsqheIcUlGl36b3f58Kfnd5dq4=`. Yêu cầu `release/trust/yeu_cau_PC2_d02702dd741c3e4f.json` (nguyên byte,
  sha256 `4bc80809…`): tự ký đúng; khoá trùng đủ 32 byte khoá công khai do `tao-khoa` để lại; khoá đang tin
  `8aa5baa6c8f225f9`; trust store `a37dc9b6…`; bản 1.1.1; chỉ chứa BĂM định danh cài đặt.
- P3 để lại: D-21/P-5/P-6 trùng số với nhánh LOCAL `fix/pc2/loop-alias-p0` (đánh số lại khi tích hợp P0); mẫu `.bat` tạo
  khoá/ghi danh chưa nằm trong repo (PC2 có bản đã thử, ngoài Git).
- Tiếp: PC1 ký uỷ quyền MỘT lần (đối chiếu ĐỦ khoá công khai base64, không chỉ key_id) → PC2 `ghi-danh` (người dùng) →
  dry-run khoá PC2 thật, PC1 tắt → gộp. Bằng chứng ngoài Git trên PC2: `2026-10-15_release_authority`.
### 2026-10-14 — cookie đăng nhập YouTube chạy bằng Node.js + yt-dlp-ejs (nhánh fix/pc2/youtube-cookie-js-fallback, CHƯA đẩy)
- Bối cảnh: Stable 1.1.0 + `ytdlp_cookies_browser = firefox` → MỌI video «The page needs to be reloaded», cầu dao khuyên sai «có
  thể yt-dlp cần cập nhật». Bản đầu (`6ebdc72`, `ea12a28`) chỉ lùi không-cookie + nhớ 30 phút — người dùng KHÔNG muốn (YouTube từng
  đòi xác minh khi không cookie): mục tiêu là DÙNG ĐƯỢC phiên đăng nhập, minh bạch khi không dùng được.
- Cơ chế (yt-dlp 2026.08.19, đo NGOẠI TUYẾN trên PC2 — `C:\Dev\pc2_test_tools\cookie_js\kiem_node_ejs.py`): có cookie → chỉ client
  phải giải thử thách JS (`web_embedded, tv_downgraded, web`); giải cần Node.js ≥ 22 (yt-dlp chỉ tự bật deno → `js_runtimes`) +
  gói `yt-dlp-ejs` ĐÚNG bản yt-dlp ghim (0.8.0, khớp băm; script đi kèm yt-dlp thiếu thư viện cho node). PC2: Node 24.21.0 có sẵn;
  Stable thiếu gói EJS. `web_embedded`/`tv_downgraded` không đòi PO token cho HTTPS (audio-only); `tv_downgraded` lỗi phía YouTube.
- Làm (`4795b18`, trên `3e98131`; mục này ở commit sau): `ytdlp_chung.kha_nang_js` (node trên PATH — bỏ thư mục hiện hành — + phiên bản + EJS
  đúng bản/băm; hỏi lại MỖI lượt, không nhớ lỗi cũ; bỏ `NhoBoCookie`); có cookie → `js_runtimes` node ở MỌI đường gọi, không
  `remote_components`; máy chưa sẵn sàng → quét/tải KHÔNG cookie, không gửi request đăng nhập, mọi kết quả ghi «KHÔNG đăng nhập»;
  đường khác ném `CookieCanJs` trước request. Loại lỗi mới `JS_CHALLENGE_ERROR` (ngưỡng 2) + `PLAYER_CLIENT_ERROR` (ngưỡng 5); bot,
  cần đăng nhập, player client, bộ giải hỏng: KHÔNG tự bỏ đăng nhập. Thanh bên + youtube-doctor nói cookie DÙNG được hay không.
  Lock + `yt-dlp-ejs==0.8.0` (sinh bằng `release_tool.py lock` từ môi trường mới: khác lock cũ ĐÚNG một dòng).
- Môi trường RIÊNG: `C:\Dev\TimClipPro_CookieFix\TimClipPro\.venv` (54 gói lock + yt-dlp-ejs + pytest/ruff, `--require-hashes`,
  không mạng); wheel `C:\Dev\wheelhouse_pc2_ejs` (PyPI, 53 443 byte, sha256 `79300e5f…bdb4`). Venv chung của clone KHÔNG đổi.
- Test (chặn mạng, cp1252): cookie/Node/EJS 57 (venv thiếu EJS: 56 + 1 bỏ qua đúng lý do), đột biến 21/21, YouTube + Watch +
  Marathon 675/675, nhanh 2582 = 2580/2/0, chậm tải phần đầu thật (Range) 5/5. Trước/sau, lô 6 video (`do_truoc_sau.py`): 1.1.0
  0/6; bản trước 6/6 nhưng 0 lượt đăng nhập; bản mới 6/6, 12/12 lượt CÓ đăng nhập; thiếu EJS 6/6, 0 request cookie, ghi rõ.
  Bằng chứng: `C:\Dev\pc2_test_runs\2026-10-14_cookie_node_ejs`.
- Pilot THẬT (người dùng duyệt; 14/10 13:07; video công khai `dSfZMQXvlfY`, cookie Firefox, Development, đúng MỘT lượt; công
  cụ ngoài Git `C:\Dev\pc2_test_tools\cookie_js\pilot_cookie_that.py` bản 2, tự kiểm ngoại tuyến 37/37): ĐẠT — trang xem
  `LOGGED_IN=true`, cookie xác thực còn nguyên, 0 cảnh báo; node `--permission` chạy thật + EJS 0.8.0 (python package); 60 s
  đầu: `-request_size` trước `-i`, `-t 60`, HTTP 206, đọc 10% luồng, 0,46 s; âm thanh thật 60,014 s, giải mã 0 lỗi; rò rỉ 0.
- Tiếp: duyệt đẩy + PR → PC1: lock có băm (thêm wheel yt-dlp-ejs) → runtime MỚI (lock đổi → runtime_id đổi; CapNhat.bat dựng venv
  mới, tải gói từ PyPI) → build/ký 1.1.1. Máy dùng cookie cần Node.js ≥ 22 trên PATH. Tạm trên 1.1.0: xoá ô cookie.
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
