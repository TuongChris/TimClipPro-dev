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
- Remote: `private` (`TimClipPro-dev`, PRIVATE) để push; `origin` (PUBLIC) chỉ fetch — push bị chặn bằng pushurl giả.

## Tiếp theo
1. Người dùng duyệt đẩy commit tài liệu cập nhật trạng thái (sau `9b763be`, cùng nhánh): fast-forward
   `integration/current` rồi `git push private integration/current` — quét phần lịch sử mới trước khi đẩy.
2. Người dùng kiểm nạp ngữ cảnh thật: mở phiên mới ở gốc worktree, gõ `/context` (phiên CLI lồng của Claude chưa đăng
   nhập nên chưa tự kiểm được).
3. PC2 clone theo `docs/ai/GIT_WORKFLOW.md` (khoá deploy — người dùng thêm khoá công khai trên GitHub).
4. Gửi e49340d đi tái audit độc lập; có kết quả → quyết định C7 (giao bộ cài one-click cho PC2).
5. Sao lưu khoá ký ra USB khi có USB.

## Nhật ký
### 2026-10-09 — Remote PRIVATE `TimClipPro-dev` (nhánh feature/pc1/ai-shared-context)
- Làm (người dùng duyệt): `integration/current` fast-forward e49340d → 9b763be; tạo repo PRIVATE; thêm remote `private`;
  đẩy DUY NHẤT `integration/current` (không tag); chặn push vào `origin`, `remote.pushDefault=private`,
  `push.default=upstream`. Repo public không đổi (18 ref như trước). Production giữ 6dc3f9d.
- Kiểm: quét lịch sử sẽ đẩy (843 blob, 90 commit, đối chứng dương 39/39) → 0 phát hiện nhạy cảm mới; GitHub
  `private=true`, ref duy nhất `refs/heads/integration/current` = `9b763be`, 0 tag; thử push nhầm `origin` → bị chặn.
- Chưa kiểm: `/context` trong phiên thật (CLI lồng chưa đăng nhập).
- Bằng chứng: `D:\TimClipPro_SharedContext\20261009_111332\` (logs/kiem_sau_push.txt, evidence/quet_truoc_push.json).
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
