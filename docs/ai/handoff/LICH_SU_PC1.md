# Lịch sử handoff — PC1

Mục cũ chuyển từ `docs/ai/handoff/PC1.md` khi «Nhật ký» ở đó quá 6 mục. Mới hơn ở trên. Không ghi bí mật, link Sheet
thật, dữ liệu khách hàng.

### 2026-10-09 — Ngữ cảnh chung PC1/PC2 (nhánh feature/pc1/ai-shared-context)
- Làm: inventory chỉ đọc (Git, worktree, remote, tài liệu); `CLAUDE.md` gốc, `docs/ai/*`, `.claude/rules/*`,
  `.claude/settings.json`; chuẩn hoá `TimClipPro/CLAUDE.md` 782 → 198 dòng (phần dài chuyển nguyên
  văn); tạo nhánh local `integration/current` = e49340d. Không push, không đổi remote, production giữ 6dc3f9d.
- Kiểm: kiem_tai_lieu 9/9 ĐẠT (phủ 646/646 dòng có chữ; 79 glob rule khớp; 138/138 file test đúng một vùng; 0 bí mật, đối chứng dương 14/14); quét lịch sử commit `b05a74d`: 0 phát hiện mới; suite nhanh trên cây `b05a74d`: 2445 đạt / 8 bỏ qua / 0 hỏng; chậm `test_hai_may_gia_lap.py` 1/1; rào chắn: sạch
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
