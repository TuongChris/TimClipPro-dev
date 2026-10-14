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
  Bằng chứng: `C:\Dev\pc2_test_runs\2026-10-14_cookie_node_ejs`. Chưa gửi request YouTube thật nào.
- Tiếp: duyệt đẩy + PR → PC1: lock có băm (thêm wheel yt-dlp-ejs) → runtime MỚI (lock đổi → runtime_id đổi; CapNhat.bat dựng venv
  mới, tải gói từ PyPI) → build/ký 1.1.1. Pilot thật (1 video công khai, cookie Firefox) CHỜ duyệt. Tạm trên 1.1.0: xoá ô cookie.
- Mục cũ hơn (2026-10-13, 2026-10-09): `docs/ai/handoff/LICH_SU_PC2.md`.
