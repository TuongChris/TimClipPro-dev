# Handoff — PC2

Giữ file ≤ 80 dòng. Mục mới thêm lên ĐẦU «Nhật ký» (mẫu: `docs/ai/SESSION_START.md`); quá 6 mục thì chuyển mục cũ nhất
sang `docs/ai/handoff/LICH_SU_PC2.md` (tạo khi cần). Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

## Máy
- Vai trò: vận hành bản Stable + một clone phát triển riêng để sửa lỗi (nhánh `fix/pc2/<tên>`).
- Stable: `C:\TimClipPro` (cài đặt), `C:\TimClipPro_State` (dữ liệu, `lichsu.db`, kho), `C:\TimClipPro_Feed` (feed);
  cổng 8501 (`127.0.0.1`). Người dùng báo đã cài 1.0.0 và đang chạy; PC1 chưa có bằng chứng cài. Claude KHÔNG BAO GIỜ
  đọc/ghi/chạy gì trong ba thư mục này; chỉ launcher/updater do người dùng chạy. Chặn sửa + đọc cả ba trong
  `.claude/settings.json` chung (từ 10/10; `.claude/settings.local.json` của PC2 chặn thêm đọc `C:\TimClipPro_State`).
- Clone phát triển: `C:\Dev\Tool_Quet` (ngoài OneDrive, ngoài ba thư mục Stable). Venv riêng `TimClipPro\.venv` từ
  Python 3.12.10 GỐC của máy (Stable cũng dựng từ bản này — không cài/nâng cấp gói vào Python gốc).
- Development: cổng 8502, launcher RIÊNG ngoài Git (người dùng xác nhận chạy được 10/10). YÊU CẦU (danh sách DUY NHẤT —
  nơi khác trỏ về đây; CHƯA kiểm): `--server.port=8502` ghi rõ, `--server.address=127.0.0.1`,
  `--browser.gatherUsageStats=false`; `TIMCLIP_DEV_MODE=1`, không `TIMCLIP_RUNTIME_MODE=managed`; `TIMCLIP_DATA_DIR` /
  `TIMCLIP_OUTPUT_DIR` trỏ thư mục thử; không cookie/`google_key.json` thật. KHÔNG chạy `ChayTool.bat`, `CapNhat.bat`,
  `GiamSat.bat` trong clone (ghim 8501, gọi updater cũ). Preview: `.claude/launch.json` chỉ gắn vào 8502.
- Quyền GitHub: giai đoạn 2 (từ 09/10) — Deploy Key ghi được CẢ repo; chỉ `git push private fix/pc2/<tên>:fix/pc2/<tên>`
  khi người dùng duyệt; không `integration/current`, tag, force-push. Hook `pre-push` cục bộ: khuyến nghị — CHƯA cài.
- Dữ liệu: PC2 tự xây kho và lịch sử; KHÔNG chép dữ liệu từ PC1. Test chỉ dùng dữ liệu synthetic/thư mục tạm.
- Khoá ký Stable: không bao giờ có trên PC2. PC2 chỉ có khoá CÔNG KHAI tin cậy (do bộ cài đặt sẵn).

## Tiếp theo
1. Nghiệm thu bản tài liệu/preview 10/10 (HEAD thật hỏi remote, không dùng SHA ghi sẵn):
   a. `git status` sạch (file riêng máy đã ignore); `.claude/launch.json` có sửa cục bộ → chép ra ngoài, `git restore` nó.
   b. `git fetch private`, `git switch integration/current`, `git merge --ff-only private/integration/current`;
      `git rev-parse HEAD` phải trùng `git ls-remote private refs/heads/integration/current`.
   c. Giữ nguyên NGOÀI Git: venv `TimClipPro\.venv`, dữ liệu thử, launcher Development — không commit, không chép vào repo.
   d. Đọc launcher (file của PC2), báo từng yêu cầu ở «Máy». Thiếu BẤT KỲ mục nào → KHÔNG chạy, báo người dùng. Đủ →
      chạy nó: `http://localhost:8502/_stcore/health` = `ok`.
   e. Stable độc lập: `http://localhost:8501/_stcore/health` vẫn `ok` khi Development chạy và sau khi dừng; không bấm gì
      trên giao diện Stable.
   f. Trong `C:\Dev\Tool_Quet\TimClipPro`, bảng mã MẶC ĐỊNH:
      `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_health_check.py` (12/12) và
      `.venv/Scripts/python.exe -c "import engine, channel, sheets, cli; print('ok')"` (+ suite nhanh nếu kịp).
   g. (Tuỳ) Browser pane, cấu hình `TimClipPro-DEV-8502-chi-gan`: khi Development chạy → mở 8502; khi đã dừng → báo lỗi,
      tuyệt đối không ra 8501.
   h. Hook `pre-push` (`GIT_WORKFLOW.md` «Quyền PC2 — giai đoạn 2»): cài đúng định dạng, rồi 3 lệnh thử ở đó (ref CHƯA
      có trên remote) — 2 lệnh phải in «pre-push: CHẶN», 1 lệnh đi qua.
   i. Cập nhật `CLAUDE.local.md` của PC2 theo mẫu mới `docs/ai/CLAUDE.local.md.mau` (dòng «Quyền GitHub» giai đoạn 2,
      «Development», trạng thái hook).
   j. `/context` vẫn đủ 4 file. Ghi kết quả a–i vào Nhật ký trên nhánh mới
      `git switch --no-track -c fix/pc2/<tên> private/integration/current`, commit. Khi người dùng duyệt: quét theo
      `GIT_WORKFLOW.md` «Quét tối thiểu», rồi `git push -u private fix/pc2/<tên>:fix/pc2/<tên>`.
2. C7: NGƯỜI DÙNG tự lấy kết quả bộ cài và health check của Stable, dán tóm tắt (không bí mật) — Claude PC2 không đụng
   `C:\TimClipPro*`; PC1 đóng C7 trong `CURRENT_STATE.md`.
3. Git `user.name` / `user.email` riêng cho commit của PC2 (người dùng quyết tên hiển thị) — hiện commit PC2 mang tên chung.
4. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md` — chỉ dựa handoff + tài liệu, không audit toàn repo.

## Nhật ký
### 2026-10-14 — cookie đăng nhập trên máy không có bộ chạy JavaScript (nhánh fix/pc2/youtube-cookie-js-fallback, CHƯA đẩy)
- Bối cảnh: Stable 1.1.0 đặt `ytdlp_cookies_browser = firefox` → MỌI video «The page needs to be reloaded»; cầu dao trích xuất
  dừng lô sau 5 video với lời khuyên «có thể yt-dlp cần cập nhật» (sai hướng).
- Cơ chế (yt-dlp 2026.08.19; đo NGOẠI TUYẾN trên PC2, cookie giả, chặn mạng — `C:\Dev\pc2_test_tools\cookie_js`): có cookie
  đăng nhập → client `web_embedded, tv_downgraded, web` (đều cần JS), `visionos` bị loại (không hỗ trợ cookie); không client nào
  vừa nhận cookie vừa không cần JS; PC2 không có bộ chạy JS yt-dlp dùng được (không deno; node có nhưng chưa bật; không gói
  yt-dlp-ejs). `player_client=default,web_embedded` (yt-dlp#17389) cho đúng danh sách đó → không cứu được.
- Sửa (`6ebdc72`, `ea12a28`, từ `ec1ff71`): đường lui cookie dùng chung nhận lỗi này → lùi không-cookie (visionos, đã nghiệm thu) +
  nhớ 30 phút theo cấu hình cookie (`NhoBoCookie`); cảnh báo nói đúng «thiếu JavaScript». Cookie chết/không-cookie giữ nguyên.
- Test (chặn mạng, cp1252): mới 19 (14 đỏ trước sửa; lô 6 video qua Engine + phiên + cầu dao thật), đột biến 8/8, vùng YouTube
  549/549, nhanh 2537 = 2535/2/0. Bằng chứng: `C:\Dev\pc2_test_runs\2026-10-14_cookie_js`. Chưa gửi request YouTube thật nào.
- Tiếp: duyệt đẩy + PR → PC1 review, build/ký 1.1.1. Cookie thật sự chạy cần bộ chạy JS (node có sẵn) + gói yt-dlp-ejs trong lock —
  quyết định riêng của PC1. Tạm trên Stable: xoá trống ô cookie («🔐 Kết nối YouTube») → đường không-cookie.
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
- Mục cũ hơn (2026-10-09): `docs/ai/handoff/LICH_SU_PC2.md`.
