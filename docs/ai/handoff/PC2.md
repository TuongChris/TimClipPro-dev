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
