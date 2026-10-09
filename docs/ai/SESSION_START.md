# Mở phiên Claude Code — mẫu cho PC1 và PC2

Mở Claude Code ở GỐC clone/worktree (nơi có `CLAUDE.md` gốc và `CLAUDE.local.md` của máy), không mở ở thư mục cha —
mở ở thư mục cha thì Claude không tự nạp ngữ cảnh của repo. Dán một mẫu dưới đây, thay phần `<…>`.

## PC1
```text
Phiên PC1. Task: <mô tả ngắn / dán brief>.
Làm theo «Mỗi phiên» trong CLAUDE.md: kiểm hostname, nhánh, HEAD, working tree; đọc docs/ai/handoff/PC1.md; chỉ đọc
module liên quan (ARCHITECTURE_INDEX + rg/git diff), không quét toàn repo; lỗi thì tái hiện bằng dữ liệu synthetic và
test đỏ trước; chạy test theo TEST_MATRIX; xong cập nhật handoff/PC1.md và commit trên feature/pc1/<tên>.
Không push, không sửa production, không đụng khoá ký khi mình chưa duyệt.
```

## PC2
```text
Phiên PC2 (clone phát triển). Task: <triệu chứng + cách tái hiện; KHÔNG dán dữ liệu thật, link khách hàng, cookie>.
Làm theo «Mỗi phiên» trong CLAUDE.md; đọc docs/ai/handoff/PC2.md. Không đọc/ghi C:\TimClipPro, C:\TimClipPro_State,
C:\TimClipPro_Feed; test chỉ dùng dữ liệu synthetic + thư mục tạm. Nhánh fix/pc2/<tên> từ integration/current; xong cập
nhật handoff/PC2.md và commit; chỉ push nhánh khi mình duyệt.
```

## Tiếp tục việc dở (cả hai máy)
```text
Tiếp tục theo «Tiếp theo» trong docs/ai/handoff/<PC1|PC2>.md và mục nhật ký mới nhất. Đối chiếu nhánh/HEAD với commit
ghi trong đó trước khi làm; lệch thì báo mình.
```

## Mẫu checkpoint — thêm lên ĐẦU «Nhật ký» của `docs/ai/handoff/<máy>.md` sau mỗi việc quan trọng
```text
### YYYY-MM-DD — <việc> (nhánh <tên>)
- Làm: <1–3 dòng>
- Commit: <sha ngắn của commit trước đó>; commit chứa chính mục này: git log -1 --format=%h -- docs/ai/handoff/<máy>.md
- Test: <lệnh> → <đạt / bỏ qua / hỏng> (junit hoặc bằng chứng: <đường dẫn>)
- Còn mở / rủi ro: <…>
- Tiếp theo: <bước kế, ai làm, cần duyệt gì>
```
Đổi trạng thái chung (nhánh tích hợp, bản Stable, remote, việc mở) → sửa cả `docs/ai/CURRENT_STATE.md`.

## Tiết kiệm token
- Ngữ cảnh đã tự nạp (CLAUDE.md gốc + CURRENT_STATE + CLAUDE.local.md + handoff của máy) — đừng đọc lại.
- Tra `ARCHITECTURE_INDEX.md` trước, rồi `rg -n "<tên>" TimClipPro`, `git diff integration/current...HEAD --stat`,
  `git log -5 --oneline -- <file>`.
- Đọc đúng đoạn cần theo số dòng; `engine.py` ~5.700 dòng — không đọc trọn khi chỉ cần một hàm.
- Tài liệu dài (`docs/LOI_DA_GAP.md`, `MANAGED_RUNTIME_DESIGN.md`, `DATA_FLOW.md`…) chỉ `rg` theo từ khoá.
- Không mở nhiều agent nghiên cứu trùng nhau; chỉ chia việc khi các phần thật sự độc lập.
- Kết thúc việc bằng checkpoint ngắn ở trên để phiên sau đi tiếp ngay, không phải đọc lại.
