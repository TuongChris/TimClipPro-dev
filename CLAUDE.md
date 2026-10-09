# TimClipPro — điểm vào cho Claude Code (PC1 và PC2)

Repo dùng chung cho hai máy: **PC1** phát triển, tích hợp, review và ký bản Stable; **PC2** vận hành bản Stable và có
một clone phát triển riêng. File này cố ý ngắn: quy tắc phiên làm việc + chỗ tìm thông tin.
- Ngữ cảnh dự án và bất biến chung: `TimClipPro/CLAUDE.md` (tự nạp khi đọc/sửa file trong `TimClipPro/`).
- Bất biến theo module: `.claude/rules/` (tự nạp khi đọc/sửa file khớp: matcher, Sheets/outbox, updater).
- Ghi chú RIÊNG của từng máy: `CLAUDE.local.md` (không vào Git; mẫu `docs/ai/CLAUDE.local.md.mau`).

Trạng thái chung hiện tại (tự nạp):
@docs/ai/CURRENT_STATE.md

## Mỗi phiên — làm đúng thứ tự
1. Kiểm máy và Git: `hostname`, `git status -sb`, `git log --oneline -3`. Máy nào thì xem `CLAUDE.local.md`; không
   có file đó thì HỎI người dùng, không đoán. HEAD lệch mốc trong CURRENT_STATE → nói rõ trước khi làm.
2. Đọc `docs/ai/handoff/<PC1|PC2>.md` của máy này (mục «Tiếp theo»). Đụng nhánh của máy kia → đọc cả handoff kia.
3. Chỉ đọc module liên quan: tra `docs/ai/ARCHITECTURE_INDEX.md`, rồi `rg`, `git diff`, `git log -- <file>`.
4. Không quét/audit toàn repo khi task không cần. «Không audit lại» KHÔNG có nghĩa là bỏ qua kiểm chứng.
5. Sửa lỗi: tái hiện bằng dữ liệu synthetic và một test ĐỎ trước khi sửa. Không dùng dữ liệu thật/khách hàng.
6. Chạy test mục tiêu theo `docs/ai/TEST_MATRIX.md`, mở rộng theo mức rủi ro; báo số thật (đạt/bỏ qua/hỏng).
7. Xong việc: cập nhật `docs/ai/handoff/<máy>.md` (nhánh, commit, test, kết quả, bước tiếp theo) và
   `docs/ai/CURRENT_STATE.md` nếu trạng thái chung đổi; commit trên CÙNG nhánh. Mẫu: `docs/ai/SESSION_START.md`.

## Nhánh (chi tiết: `docs/ai/GIT_WORKFLOW.md`)
- `integration/current` — nguồn tích hợp đã kiểm; chỉ nhận thay đổi đã review + test xanh, không commit thẳng.
- `feature/pc1/<tên>` — việc của PC1. `fix/pc2/<tên>` — sửa lỗi phát hiện trên PC2. Tạo từ `integration/current`.
- Bản Stable chỉ chuẩn bị từ commit đã nghiệm thu trên `integration/current`, và chỉ ký trên PC1.

## Cấm, trừ khi người dùng duyệt rõ trong phiên này
- Push, force-push, tạo/sửa remote, tag hay release công khai. `origin` hiện là repo PUBLIC.
- Sửa production: PC1 `Tool_Quet` đang chạy thật; Stable của PC2 `C:\TimClipPro`, `C:\TimClipPro_State`,
  `C:\TimClipPro_Feed` (chỉ launcher/updater do người dùng chạy được đổi chúng).
- Đọc, in hay chép khoá ký riêng, mật khẩu, cookie, `google_key.json`, link Google Sheet thật.
- Gọi Google Sheets/YouTube thật, đăng ký Task Scheduler, xoá/ghi đè `db.pklz`, `lichsu.db`, `downloaded.txt`,
  `clips_meta.json`.
- Đưa vào Git: dữ liệu runtime, kho vân tay, dữ liệu khách hàng, credentials, auto-memory/transcript của Claude,
  `CLAUDE.local.md`, `.claude/settings.local.json`, bản phát hành/khoá.

## Tài liệu ngữ cảnh (`docs/ai/`)
| File | Đọc khi |
|---|---|
| `CURRENT_STATE.md` | luôn (đã tự nạp ở trên) |
| `handoff/PC1.md`, `handoff/PC2.md` | đầu phiên, của máy mình |
| `ARCHITECTURE_INDEX.md` | tìm module/tài liệu thiết kế cho task |
| `TEST_MATRIX.md` | chọn test cần chạy, lệnh chạy |
| `DECISIONS.md` | trước khi đổi thiết kế, quy trình, phạm vi |
| `GIT_WORKFLOW.md` | nhánh, remote, PR, phát hành, việc KHÔNG đưa vào Git |
| `SESSION_START.md` | mẫu câu mở phiên cho PC1/PC2 và mẫu checkpoint |

Người dùng là chủ dự án, không lập trình: trả lời tiếng Việt, xưng «bạn», kèm bằng chứng, giải thích ngắn gọn.
