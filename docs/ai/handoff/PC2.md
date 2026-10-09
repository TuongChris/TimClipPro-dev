# Handoff — PC2

Giữ file ≤ 80 dòng. Mục mới thêm lên ĐẦU «Nhật ký» (mẫu: `docs/ai/SESSION_START.md`); quá 6 mục thì chuyển mục cũ nhất
sang `docs/ai/handoff/LICH_SU_PC2.md` (tạo khi cần). Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

## Máy
- Vai trò: vận hành bản Stable + một clone phát triển riêng để sửa lỗi (nhánh `fix/pc2/<tên>`).
- Stable (sẽ cài bằng bộ one-click khi C7 được duyệt): `C:\TimClipPro` (cài đặt), `C:\TimClipPro_State` (dữ liệu,
  `lichsu.db`, kho), `C:\TimClipPro_Feed` (feed bản mới). Claude KHÔNG ghi vào ba thư mục này; cập nhật chỉ qua
  launcher/updater do người dùng chạy. Luật chặn sửa có sẵn trong `.claude/settings.json`.
- Clone phát triển (đề xuất): `D:\TimClipPro_Dev\TimClipPro` (không có D: thì `C:\Dev\TimClipPro`) — ngoài OneDrive,
  ngoài ba thư mục Stable. Venv riêng `TimClipPro\.venv` của clone; không dùng runtime của Stable để chạy test.
- Dữ liệu: PC2 tự xây kho và lịch sử; KHÔNG chép dữ liệu từ PC1. Test chỉ dùng dữ liệu synthetic/thư mục tạm; muốn
  tái hiện lỗi từ dữ liệu thật thì mô tả triệu chứng, dựng bản giả tương đương — không chép `lichsu.db`/kho vào clone.
- Khoá ký Stable: không bao giờ có trên PC2. PC2 chỉ có khoá CÔNG KHAI tin cậy (do bộ cài đặt sẵn).

## Tiếp theo
1. (Chờ PC1 + người dùng) C7: cài Stable bằng bộ one-click `TimClipPro_PC2_CaiDat_1.0.0_e49340d.zip`
   (giải nén → nhấp đúp `CAI_TIMCLIPPRO_PC2.bat` → chờ PASS); FFmpeg cài riêng (bộ cài chỉ cảnh báo).
2. (Chờ repo private) Clone phát triển theo `docs/ai/GIT_WORKFLOW.md` mục «PC2 — clone phát triển lần đầu».
3. Tạo `CLAUDE.local.md` từ `docs/ai/CLAUDE.local.md.mau` (Máy: PC2).

## Nhật ký
- (chưa có phiên nào trên PC2)
