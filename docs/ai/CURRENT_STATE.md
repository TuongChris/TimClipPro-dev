# Trạng thái chung — TimClipPro

Cập nhật 2026-10-10 trên PC1. File này KHÔNG ghi HEAD mới nhất — HEAD thật luôn hỏi remote: `git fetch private` rồi
`git log --oneline -3 private/integration/current`. Mốc mã chạy thật: `e49340d` (tree `2aee2510`); sau đó
`integration/current` chỉ thêm tài liệu và test. Kiểm (một dòng) — kết quả phải RỖNG; không rỗng → file này có thể đã
cũ: đọc các commit đó và handoff mới nhất trước khi tin.
```bash
git diff --stat e49340d private/integration/current -- TimClipPro ':!TimClipPro/tests' ':!*.md'
```

## Mã nguồn
- `e49340d` (08/10) = Report Policy V2 (`6dc3f9d`) + Managed Runtime/outbox/updater, đã sửa qua hai vòng audit độc lập
  (`f4d3cb7` → `78ba20c` → `e49340d`). Cổng nội bộ xanh: 2445 đạt / 8 bỏ qua / 0 hỏng, chậm 14/14, đột biến outbox
  123/123 (`docs/ai/TEST_MATRIX.md`). **Tái audit ĐỘC LẬP của e49340d: CHƯA có.**
- Lock trong repo (`TimClipPro/requirements-lock.txt`, `launcher-lock.txt`) chưa có băm; bản có băm (cùng pin) chỉ
  nằm trong bộ phát hành Stable trên PC1.
- Từ 09/10 chỉ thêm: bộ tài liệu chung (`CLAUDE.md` gốc, `docs/ai/`, `.claude/`; các commit `docs(ai)`) và PR #1 của
  PC2 (gộp 10/10: test bảng mã cp1252/UTF-8 của `health_check`, không đổi mã chạy thật).

## Hai máy
| | PC1 (hostname DESKTOP-UIQUSEM) | PC2 |
|---|---|---|
| Vai trò | phát triển, tích hợp, review PR, ký Stable | chạy Stable + clone phát triển `C:\Dev\Tool_Quet` |
| Đang chạy thật | `Tool_Quet` = `6dc3f9d` (bố cục legacy, `lichsu.db` v2), cổng 8501 | Stable 1.0.0, cổng 8501 — người dùng xác nhận; PC1 chưa có bằng chứng cài |
| Development | worktree `D:\TimClipPro_Dev\<tên>`; không chạy server | cổng 8502, launcher riêng ngoài Git — người dùng xác nhận chạy được (10/10); cấu hình launcher CHƯA kiểm |
| Môi trường | Windows; test trên runtime lock có băm, Python 3.12.10 | Windows 11 (người dùng báo), Python 3.12.10 gốc, venv `TimClipPro\.venv`, stdout cp1252 |
| Dữ liệu | của riêng PC1 | PC2 tự xây; KHÔNG chép dữ liệu từ PC1 |
| Khoá ký Stable | có — ngoài repo, ngoài OneDrive; chưa sao lưu | không bao giờ có |

PC1 lên `e49340d` là quyết định RIÊNG (lược đồ `lichsu.db` v2 → v4; sao lưu trước) — chưa được duyệt.

## Đã kiểm chứng — và chưa
- CÓ bằng chứng trên PC1: ngữ cảnh chung nạp thật (`/context`, rule theo vùng, quyền chặn — handoff PC1 09/10); review
  PR #1: suite nhanh 2452 / 8 / 0, `health_check` 12/12 ở cp1252 và UTF-8 (`docs/ai/TEST_MATRIX.md`).
- PC2 tự báo (junit trên PC2, handoff PC2): clone CHỈ ĐỌC + ngữ cảnh nạp đủ 4 file (09/10); PR #1 suite nhanh 2458 đạt /
  2 bỏ qua / 0 hỏng trên cp1252.
- CHỈ có lời người dùng: Stable 1.0.0 đã cài và chạy cổng 8501 trên PC2; Development PC2 chạy cổng 8502.
- CHƯA làm: tái audit độc lập e49340d; nghiệm thu C7 có bằng chứng (kết quả bộ cài + health check của Stable trên PC2);
  thử Google Sheets thật (outbox) và quét YouTube thật trên PC2; launcher Development PC2 đúng yêu cầu (dưới); preview
  `.claude/launch.json` gắn vào 8502 trên PC2.

## Stable 1.0.0 (build từ e49340d) — đã ký; người dùng báo đã cài trên PC2
- key_id `8aa5baa6c8f225f9`; gói `c813414c…30a2`; manifest `e19a943b…5ee9`; chữ ký `4f5959e6…5f22`;
  bootstrap kit `bec08415…5c08`; bộ cài one-click PC2 `b0847ea7…caa8` (thử 13/13 trong thư mục sạch).
- Người dùng báo đã cài trên PC2 (09/10) — TRƯỚC tái audit độc lập e49340d (điều kiện ban đầu của C7). C7 chưa đóng
  về kiểm chứng: cần kết quả bộ cài (PASS) và health check của bản đang chạy trên PC2.

## Remote
- `private` = GitHub `TuongChris/TimClipPro-dev` — **PRIVATE**, tạo 09/10/2026: nhánh `integration/current` + nhánh việc
  (`fix/pc2/*`, `feature/pc1/*`) đi kèm PR; không tag (kiểm: `git ls-remote private`). Chi tiết `docs/ai/GIT_WORKFLOW.md`.
- Quyền PC2: giai đoạn 2 (người dùng bật 09/10) — Deploy Key READ-WRITE cho CẢ repo (tên khoá vẫn ghi «read-only»);
  PC2 chỉ đẩy `fix/pc2/*` khi người dùng duyệt; PC1 review + gộp qua PR (PR #1 gộp fast-forward 10/10).
- `origin` (chỉ PC1) = GitHub `TuongChris/Tool_Quet` — **PUBLIC**; `main` = `7f85c8d`. Chỉ còn để fetch (updater cũ
  của máy legacy); push vào `origin` bị chặn trên PC1. Commit mới từ e49340d trở đi KHÔNG lên repo public.

## Cổng và preview
- 8501 = Stable (PC2, `launcher.py`, ghim `127.0.0.1:8501`) và production legacy (PC1, `ChayTool.bat`).
- Development chỉ ở 8502, bằng launcher PC2 ngoài Git. Yêu cầu cho launcher (danh sách duy nhất, CHƯA kiểm — PC1 chưa
  xem launcher đó): `docs/ai/handoff/PC2.md` «Máy». Mấu chốt: `--server.port=8502` phải GHI RÕ (Streamlit chỉ tự nhảy
  cổng khi cổng không ghi rõ, nên «thấy chạy ở 8502 khi Stable giữ 8501» chưa chứng minh gì); không chạy `ChayTool.bat`
  trong clone (ghim 8501, gọi updater cũ `cap_nhat.py` trước).
- `.claude/launch.json` (từ 10/10) chỉ GẮN vào 8502, không tự khởi động. Production PC1 (`Tool_Quet` @ `6dc3f9d`) và các
  worktree cũ vẫn mang bản CŨ tự khởi động 8501 — không mở preview ở đó.

## Việc đang mở (theo thứ tự)
1. PC2 nghiệm thu bản tài liệu/preview 10/10: fetch + fast-forward, Development 8502 và Stable 8501 độc lập, test hồi
   quy + smoke (`docs/ai/handoff/PC2.md`).
2. Tái audit độc lập e49340d; bằng chứng C7 trên PC2.
3. Pilot thật có kiểm soát (Sheets/YouTube trên PC2) — chỉ khi người dùng duyệt.
4. Sao lưu khoá ký ra USB (`KEY_BACKUP = DEFERRED_BY_USER`); khi sao lưu, cân nhắc mã hoá lại (PBKDF2 hiện 2048 vòng).
5. FFmpeg: PC2 có trên PATH (winget 9.0.1, handoff PC2); bộ cài vẫn chỉ cảnh báo khi thiếu.
6. Lịch sử repo public có dữ liệu cần xử lý — chi tiết trong báo cáo quét ngoài Git trên PC1, không ghi vào đây.
