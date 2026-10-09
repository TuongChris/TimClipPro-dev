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
1. (Chờ PC1 + người dùng) C7: cài Stable bằng bộ one-click `TimClipPro_PC2_CaiDat_1.0.0_e49340d.zip`
   (giải nén → nhấp đúp `CAI_TIMCLIPPRO_PC2.bat` → chờ PASS); FFmpeg cài riêng (bộ cài chỉ cảnh báo).
2. Giai đoạn 1: clone CHỈ ĐỌC theo `docs/ai/GIT_WORKFLOW.md` («PC2 — giai đoạn 1»). Đang đọc file này trong clone →
   bước này xong; kiểm `git remote -v` chỉ có `private`, `git push --dry-run private integration/current` bị từ chối.
3. `CLAUDE.local.md` (Máy: PC2, quyền CHỈ ĐỌC) + `.claude/settings.local.json` theo mẫu; mở phiên ở gốc clone, `/context`
   thấy đủ `CLAUDE.md`, `docs/ai/CURRENT_STATE.md`, `CLAUDE.local.md`, `docs/ai/handoff/PC2.md`.
4. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md` — đầu phiên `git fetch private`, so HEAD với
   `private/integration/current`; chỉ dựa handoff + tài liệu, không audit toàn repo; commit LOCAL, chưa push.
5. Giai đoạn 2 (quyền ghi + PR): chờ người dùng duyệt sau khi các bước trên đạt.

## Nhật ký
- (chưa có phiên nào trên PC2)
