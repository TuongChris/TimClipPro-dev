# Trạng thái chung — TimClipPro

Cập nhật 2026-10-09 trên PC1. File này KHÔNG ghi HEAD mới nhất — HEAD thật luôn hỏi remote: `git fetch private` rồi
`git log --oneline -3 private/integration/current`. Mốc mã nguồn: `e49340d` (tree `2aee2510`); `integration/current`
= mốc đó + các commit chỉ tài liệu (`docs(ai): …`). Kiểm: `git log --oneline e49340d..private/integration/current` —
có commit KHÔNG phải tài liệu → file này có thể đã cũ: đọc commit đó và handoff mới nhất trước khi tin.

## Mã nguồn
- `e49340d` (08/10) = Report Policy V2 (`6dc3f9d`) + Managed Runtime/outbox/updater, đã sửa qua hai vòng audit độc lập
  (`f4d3cb7` → `78ba20c` → `e49340d`). Cổng nội bộ xanh: 2445 đạt / 8 bỏ qua / 0 hỏng, chậm 14/14, đột biến outbox
  123/123 (`docs/ai/TEST_MATRIX.md`). **Tái audit ĐỘC LẬP của e49340d: CHƯA có.**
- Lock trong repo (`TimClipPro/requirements-lock.txt`, `launcher-lock.txt`) chưa có băm; bản có băm (cùng pin) chỉ
  nằm trong bộ phát hành Stable trên PC1.
- Bộ tài liệu chung (`CLAUDE.md` gốc, `docs/ai/`, `.claude/`) vào `integration/current` từ 09/10 qua các commit
  `docs(ai)` (người dùng duyệt từng lần đẩy); mã nguồn không đổi so với `e49340d`.

## Hai máy
| | PC1 (hostname DESKTOP-UIQUSEM) | PC2 |
|---|---|---|
| Vai trò | phát triển, tích hợp, review, ký Stable | chạy Stable + clone phát triển riêng |
| Đang chạy thật | `Tool_Quet` = `6dc3f9d` (bố cục legacy, `lichsu.db` v2) | chưa cài gì (bước C7 đang chờ) |
| Dữ liệu | của riêng PC1 | PC2 tự xây; KHÔNG chép dữ liệu từ PC1 |
| Khoá ký Stable | có — ngoài repo, ngoài OneDrive; chưa sao lưu | không bao giờ có |

PC1 lên `e49340d` là quyết định RIÊNG (lược đồ `lichsu.db` v2 → v4; sao lưu trước) — chưa được duyệt.

## Stable 1.0.0 (build từ e49340d) — đã ký, CHƯA giao
- key_id `8aa5baa6c8f225f9`; gói `c813414c…30a2`; manifest `e19a943b…5ee9`; chữ ký `4f5959e6…5f22`;
  bootstrap kit `bec08415…5c08`; bộ cài one-click PC2 `b0847ea7…caa8` (thử 13/13 trong thư mục sạch).
- Giao PC2 (C7) khi: e49340d đã được tái audit độc lập + người dùng duyệt.

## Remote
- `private` = GitHub `TuongChris/TimClipPro-dev` — **PRIVATE**, tạo 09/10/2026; chỉ có nhánh `integration/current`,
  không tag (kiểm: `git ls-remote private`). Hai máy chia sẻ mã/tài liệu/handoff qua remote này (`docs/ai/GIT_WORKFLOW.md`).
- Quyền PC2: giai đoạn 1 = Deploy Key CHỈ ĐỌC (clone/fetch, không push), clone tại `C:\Dev\Tool_Quet`. Giai đoạn 2
  (quyền ghi `fix/pc2/*` + Pull Request) CHƯA làm — cần người dùng duyệt riêng.
- `origin` (chỉ PC1) = GitHub `TuongChris/Tool_Quet` — **PUBLIC**; `main` = `7f85c8d`. Chỉ còn để fetch (updater cũ
  của máy legacy); push vào `origin` bị chặn trên PC1. 23 commit mới của e49340d KHÔNG lên repo public.

## Việc đang mở (theo thứ tự)
1. Tái audit độc lập e49340d → rồi C7 (cài PC2 bằng bộ one-click).
2. PC2 giai đoạn 1: clone CHỈ ĐỌC theo `docs/ai/GIT_WORKFLOW.md` («PC2 — giai đoạn 1»); giai đoạn 2 chờ duyệt.
3. Sao lưu khoá ký ra USB (`KEY_BACKUP = DEFERRED_BY_USER`); khi sao lưu, cân nhắc mã hoá lại (PBKDF2 hiện 2048 vòng).
4. FFmpeg cho PC2 chưa có trong bộ cài (bộ cài chỉ cảnh báo).
5. Lịch sử repo public có dữ liệu cần xử lý — chi tiết trong báo cáo quét ngoài Git trên PC1, không ghi vào đây.
