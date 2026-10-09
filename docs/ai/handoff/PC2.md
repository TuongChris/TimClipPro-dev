# Handoff — PC2

Giữ file ≤ 80 dòng. Mục mới thêm lên ĐẦU «Nhật ký» (mẫu: `docs/ai/SESSION_START.md`); quá 6 mục thì chuyển mục cũ nhất
sang `docs/ai/handoff/LICH_SU_PC2.md` (tạo khi cần). Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

## Máy
- Vai trò: vận hành bản Stable + một clone phát triển riêng để sửa lỗi (nhánh `fix/pc2/<tên>`).
- Stable (sẽ cài bằng bộ one-click khi C7 được duyệt): `C:\TimClipPro` (cài đặt), `C:\TimClipPro_State` (dữ liệu,
  `lichsu.db`, kho), `C:\TimClipPro_Feed` (feed bản mới). Claude KHÔNG đọc/ghi ba thư mục này; cập nhật chỉ qua
  launcher/updater do người dùng chạy. Luật chặn sửa có sẵn trong `.claude/settings.json`; chặn đọc `C:\TimClipPro_State`
  trong `.claude/settings.local.json` của PC2.
- Clone phát triển: `C:\Dev\Tool_Quet` — ngoài OneDrive, ngoài ba thư mục Stable. Venv riêng `TimClipPro\.venv` của
  clone (Python 3.12 riêng); không dùng runtime của Stable để chạy test.
- Quyền GitHub: giai đoạn 1 = Deploy Key CHỈ ĐỌC cho repo `TimClipPro-dev` (clone/fetch, KHÔNG push). Giai đoạn 2
  (quyền ghi `fix/pc2/*` + Pull Request) CHƯA làm — cần người dùng duyệt (`docs/ai/GIT_WORKFLOW.md`, mục cuối).
- Dữ liệu: PC2 tự xây kho và lịch sử; KHÔNG chép dữ liệu từ PC1. Test chỉ dùng dữ liệu synthetic/thư mục tạm; muốn
  tái hiện lỗi từ dữ liệu thật thì mô tả triệu chứng, dựng bản giả tương đương — không chép `lichsu.db`/kho vào clone.
- Khoá ký Stable: không bao giờ có trên PC2. PC2 chỉ có khoá CÔNG KHAI tin cậy (do bộ cài đặt sẵn).

## Tiếp theo
1. C7: người dùng báo (09/10) Stable 1.0.0 ĐÃ cài và chạy trên PC2 — PC1 xác minh rồi sửa `CURRENT_STATE.md` (PC2 không
   tự sửa `integration/current`). FFmpeg 9.0.1 có trên PATH (winget).
2. Giai đoạn 1 — XONG 09/10: clone CHỈ ĐỌC (`git remote -v` chỉ `private`; `push --dry-run` bị từ chối «read only»).
3. XONG 09/10: `CLAUDE.local.md` + `.claude/settings.local.json`; ngữ cảnh nạp đủ 4 file; venv dev `TimClipPro\.venv`
   từ Python 3.12.10 GỐC của máy (Stable cũng dựng từ bản này — không cài gói/nâng cấp nó); chi tiết: `CLAUDE.local.md`.
4. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md` — đầu phiên `git fetch private`, so HEAD với
   `private/integration/current`; chỉ dựa handoff + tài liệu, không audit toàn repo; commit LOCAL, chưa push.
5. Giai đoạn 2 (quyền ghi + PR): chờ người dùng duyệt — cần để đưa `fix/pc2/windows-health-encoding` (nhật ký dưới)
   sang PC1 review + merge.

## Nhật ký
### 2026-10-09 — test bảng mã cp1252 của health_check (nhánh fix/pc2/windows-health-encoding)
- Làm: PC2 (cp1252) hỏng `test_chan_mang_truoc_khi_import`: test gọi thẳng `chan_mang()` rồi print tiếng Việt, bỏ
  `_utf8_dau_ra()` của `main()` — lỗi của test; production đúng (launcher ép UTF-8; `main` và `cli` đổi stdout). Chỉ
  sửa `tests/test_health_check.py`: test cũ chạy đúng thứ tự `main()`, ép cp1252/utf-8; +3 test hồi quy × 2 bảng mã.
- Commit: `da66f0e` (trên `c1f19d8`); commit chứa chính mục này: `git log -1 --format=%h -- docs/ai/handoff/PC2.md`.
- Test (clone tạm, chặn mạng, cp1252): health_check 12/12; đột biến `_utf8_dau_ra` no-op → 2 đỏ, launcher bỏ biến
  UTF-8 → 1 đỏ; ruff sạch; nhanh 2460 = 2458 đạt / 2 bỏ qua (symlink cần quyền; file đang mở) / 0 hỏng (junit ngoài
  Git: `C:\Dev\pc2_test_runs\2026-10-09_fix_encoding`); chậm 14/14 ở `c1f19d8` — chỉ đổi test nên không chạy lại.
- Còn mở / rủi ro: chưa đẩy được (khoá CHỈ ĐỌC). PC2 chưa đặt git `user.name`/`user.email` (commit tạm dùng tên PC1).
- Tiếp theo: người dùng duyệt giai đoạn 2 → đẩy nhánh + PR; PC1 review, merge; PC1 xác minh Stable đã cài trên PC2.
