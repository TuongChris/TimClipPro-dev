# TimClipPro — điểm vào cho Claude Code (PC1 và PC2)

Repo dùng chung cho hai máy NGANG QUYỀN (D-23): **PC2** = máy phát triển + phát hành CHÍNH (và vận hành Stable 8501),
**PC1** = máy DỰ PHÒNG. Máy nào cũng phát triển, review, tích hợp, build, ký (khoá RIÊNG của máy đó), phát hành.
File này cố ý ngắn: quy tắc phiên làm việc + chỗ tìm thông tin.
- Ngữ cảnh dự án và bất biến chung: `TimClipPro/CLAUDE.md` (tự nạp khi đọc/sửa file trong `TimClipPro/`).
- Bất biến theo module: `.claude/rules/` (tự nạp khi đọc/sửa file khớp: matcher, Sheets/outbox, updater).
- Ghi chú RIÊNG của từng máy: `CLAUDE.local.md` (không vào Git; mẫu `docs/ai/CLAUDE.local.md.mau`).

Trạng thái chung hiện tại (tự nạp):
@docs/ai/CURRENT_STATE.md

## Mỗi phiên — làm đúng thứ tự
1. Kiểm máy và Git: `hostname`, `git status -sb`, `git log --oneline -3`. Máy nào thì xem `CLAUDE.local.md`; không
   có file đó thì HỎI người dùng, không đoán. Kiểm remote THẬT mỗi phiên: `git fetch private` rồi
   `git log --oneline -3 private/integration/current` — SHA ghi trong tài liệu chỉ là mốc lịch sử, KHÔNG phải bản mới
   nhất. Nhánh đang làm lệch remote, hoặc remote có commit mới → đọc phần mới và nói rõ trước khi làm.
2. Đọc `docs/ai/handoff/<PC1|PC2>.md` của máy này (mục «Tiếp theo»). Đụng nhánh của máy kia → đọc cả handoff kia.
3. Chỉ đọc module liên quan: tra `docs/ai/ARCHITECTURE_INDEX.md`, rồi `rg`, `git diff`, `git log -- <file>`.
4. Không quét/audit toàn repo khi task không cần. «Không audit lại» KHÔNG có nghĩa là bỏ qua kiểm chứng.
5. Sửa lỗi: tái hiện bằng dữ liệu synthetic và một test ĐỎ trước khi sửa. Không dùng dữ liệu thật/khách hàng.
6. Chạy test mục tiêu theo `docs/ai/TEST_MATRIX.md`, mở rộng theo mức rủi ro; báo số thật (đạt/bỏ qua/hỏng).
7. Xong việc: cập nhật `docs/ai/handoff/<máy>.md` (nhánh, commit, test, kết quả, bước tiếp theo); commit trên CÙNG
   nhánh. Trạng thái chung đổi → PC1 sửa `docs/ai/CURRENT_STATE.md` khi gộp (PC2 ghi đề xuất trong handoff/mô tả PR).
   Mẫu: `docs/ai/SESSION_START.md`.

## Nhánh (chi tiết: `docs/ai/GIT_WORKFLOW.md`)
- `integration/current` — nguồn tích hợp đã kiểm; chỉ nhận thay đổi đã review + test xanh, không commit thẳng.
- `feature|fix/pc1/<tên>` — việc của PC1; `feature|fix/pc2/<tên>` — việc của PC2. Tạo KHÔNG gắn upstream vào
  integration: `git switch --no-track -c <nhánh> private/integration/current`. Đẩy luôn ghi đủ
  `git push private <nhánh>:<nhánh>` (máy đặt `push.default=upstream`: thiếu `:<nhánh>` thì git đẩy vào upstream).
- Bản Stable chỉ build từ commit đã nghiệm thu trên `integration/current`; máy nào cũng ký được bằng khoá CỦA NÓ —
  quy trình + MỘT điểm duyệt: `TimClipPro/docs/PHAT_HANH_HAI_MAY.md`.

## Không bao giờ (muốn đổi: sửa quy ước này qua PR được người dùng duyệt)
- Chạy Development hay preview ở cổng 8501 (Stable PC2, production PC1), hay thêm cấu hình TỰ KHỞI ĐỘNG vào
  `.claude/launch.json` — Development chỉ cổng 8502 bằng launcher riêng máy; file đó chỉ GẮN vào 8502.
- Claude đọc/ghi `C:\TimClipPro`, `C:\TimClipPro_State`, `C:\TimClipPro_Feed` (chỉ launcher/updater/công cụ do NGƯỜI DÙNG
  chạy), hay thư mục khoá ký `C:\TimClipPro_KhoaPhatHanh`, `D:\TimClipPro_KhoaPhatHanh`.
- Force-push, xoá nhánh/tag trên remote, đẩy tag bằng git, gắn lại/tái dùng tag, `--no-verify`.

## Cấm, trừ khi người dùng duyệt rõ trong phiên này
- Push (kể cả lên `private` — repo PUBLIC), gộp vào `integration/current`, tạo/sửa remote, release, đổi cấu hình
  GitHub (ruleset, khoá deploy). `origin` của PC1 cũng PUBLIC (chỉ fetch).
- Sửa production PC1 (`Tool_Quet` đang chạy thật).
- Đọc, in hay chép khoá ký riêng, mật khẩu, cookie, `google_key.json`, link Google Sheet thật. Bước cần mật khẩu (tạo
  khoá, ký bản, ký uỷ quyền) và bước đổi trust store (ghi danh / hoàn tác) do NGƯỜI DÙNG chạy qua `.bat` trong console.
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
