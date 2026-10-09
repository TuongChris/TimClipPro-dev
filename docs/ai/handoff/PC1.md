# Handoff — PC1

Giữ file ≤ 80 dòng. Mục mới thêm lên ĐẦU «Nhật ký» (mẫu: `docs/ai/SESSION_START.md`); quá 6 mục thì chuyển mục cũ nhất
sang `docs/ai/handoff/LICH_SU_PC1.md`. Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

## Máy
- Vai trò: phát triển, tích hợp, review, ký Stable. Hostname `DESKTOP-UIQUSEM`.
- Production (đang chạy thật, KHÔNG sửa, không checkout lại khi chưa duyệt): worktree chính `Tool_Quet` trong thư mục
  OneDrive `ToolQuet`, HEAD `6dc3f9d` (detached). Mọi worktree khác dùng chung `.git` của nó.
- Worktree phát triển mới: đặt ở `D:\TimClipPro_Dev\<tên>` (ngoài OneDrive). 15 worktree cũ `ToolQuet\Tool_Quet_*`
  là của các vòng trước — nội dung đều đã nằm trong e49340d, riêng `nguon-chung-ca-lo`/`sua-vung-final` (a602891) đã
  được tích hợp bằng commit khác (3218aff, d67ce31). Dọn chúng = việc riêng, cần duyệt.
- Bằng chứng mỗi vòng (ngoài Git): `D:\TimClipPro_<Vòng>\<thời điểm>\checkpoints\CHECKPOINT.md`.
- Đường dẫn cục bộ khác (khoá ký, bộ phát hành, Python): `CLAUDE.local.md` của PC1 (không vào Git).

## Tiếp theo
1. Người dùng duyệt nhánh `feature/pc1/ai-shared-context` → fast-forward `integration/current` (lệnh trong
   `docs/ai/GIT_WORKFLOW.md`).
2. Người dùng duyệt kế hoạch private remote (`GIT_WORKFLOW.md`) → tạo repo, đẩy `integration/current`.
3. Gửi e49340d đi tái audit độc lập; có kết quả → quyết định C7 (giao bộ cài one-click cho PC2).
4. Sao lưu khoá ký ra USB khi có USB.

## Nhật ký
### 2026-10-09 — Ngữ cảnh chung PC1/PC2 (nhánh feature/pc1/ai-shared-context)
- Làm: inventory chỉ đọc (Git, worktree, remote, tài liệu); `CLAUDE.md` gốc, `docs/ai/*`, `.claude/rules/*`,
  `.claude/settings.json`; chuẩn hoá `TimClipPro/CLAUDE.md` 782 → 198 dòng (phần dài chuyển nguyên
  văn); tạo nhánh local `integration/current` = e49340d. Không push, không đổi remote, production giữ 6dc3f9d.
- Kiểm: test và kiểm chứng đang chạy trên commit này — kết quả ghi ở commit kế tiếp cùng nhánh.
- Bằng chứng: `D:\TimClipPro_SharedContext\20261009_111332\` (CHECKPOINT, evidence/).
- Tiếp theo: mục «Tiếp theo» ở trên.
### 2026-10-09 — Bộ cài one-click PC2 (ngoài repo)
- ZIP `b0847ea7…caa8` (129.649.071 B), 65 file; thử 13/13 trong thư mục sạch (máy không có Windows Sandbox).
- Bằng chứng: `D:\TimClipPro_StableRelease\20261008_132859\` (oneclick/, evidence/thu_oneclick_lan3.json).
### 2026-10-08 — Stable 1.0.0 ký thật từ e49340d (ngoài repo)
- C1–C6 ĐẠT: khoá thật `8aa5baa6c8f225f9`; lock có băm; gói/manifest/chữ ký; kit; cài mới thử 29/29; test trên runtime
  lock 2445/8/0 + chậm 14/14. Giữ ở PC1 chờ tái audit e49340d.
### 2026-10-08 — Sửa theo tái audit 78ba20c → e49340d
- MR-R2-P1-01, MR-R2-P2-01 đã sửa (8e7dc24, c981450, 6461327, e49340d); cổng nội bộ xanh; đột biến 123/123.
- Gói nộp tái audit: `ToolQuet\TimClipPro_source_2026-10-08_e49340d.zip` (ngoài Git).
