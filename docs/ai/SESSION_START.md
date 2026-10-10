# Mở phiên Claude Code — mẫu cho PC1 và PC2

Mở Claude Code ở GỐC clone/worktree (nơi có `CLAUDE.md` gốc và `CLAUDE.local.md` của máy; PC2: `C:\Dev\Tool_Quet`),
không mở ở thư mục cha — mở ở thư mục cha thì Claude không tự nạp ngữ cảnh của repo. Gõ `/context` để thấy file nào đã
nạp. Dán một mẫu dưới đây, thay phần `<…>`. Không mẫu nào ghi cứng HEAD: mỗi phiên tự hỏi remote.

## PC1
```text
Phiên PC1. Task: <mô tả ngắn / dán brief>.
Làm theo «Mỗi phiên» trong CLAUDE.md: kiểm hostname, nhánh, HEAD, working tree; git fetch private và so với
private/integration/current (SHA trong tài liệu chỉ là mốc); đọc docs/ai/handoff/PC1.md; chỉ đọc module liên quan
(ARCHITECTURE_INDEX + rg/git diff), không quét toàn repo; lỗi thì tái hiện bằng dữ liệu synthetic và test đỏ trước;
chạy test theo TEST_MATRIX; xong cập nhật handoff/PC1.md và commit trên feature/pc1/<tên>.
Không push, không sửa production, không đụng khoá ký khi mình chưa duyệt.
```

## PC2 (giai đoạn 2 — Deploy Key có quyền ghi; chỉ `fix/pc2/*` khi được duyệt)
```text
Phiên PC2 (clone C:\Dev\Tool_Quet). Task: <triệu chứng + cách tái hiện; KHÔNG dán dữ liệu thật, link khách hàng, cookie>.
Làm theo «Mỗi phiên» trong CLAUDE.md: git fetch private và so HEAD với private/integration/current; đọc
docs/ai/handoff/PC2.md; chỉ đọc module liên quan, không audit toàn repo. Không đọc/ghi C:\TimClipPro,
C:\TimClipPro_State, C:\TimClipPro_Feed; Development chỉ cổng 8502 bằng launcher PC2, không đụng Stable 8501; test chỉ
dùng dữ liệu synthetic + thư mục tạm. Nhánh: git switch --no-track -c fix/pc2/<tên> private/integration/current; xong
cập nhật handoff/PC2.md, commit. Chỉ push khi mình duyệt, sau khi quét: git push private fix/pc2/<tên>:fix/pc2/<tên>;
KHÔNG push integration/current, tag hay force-push. PR do mình hoặc PC1 mở (GIT_WORKFLOW.md «Pull Request và gộp»).
```

## PC2 — phiên thiết lập đầu tiên (chưa có clone; mở Claude Code ở thư mục trống `C:\Dev`)
```text
Phiên PC2 — thiết lập clone phát triển TimClipPro, giai đoạn 1 CHỈ ĐỌC. Repo PRIVATE TuongChris/TimClipPro-dev, nhánh
integration/current. Làm đúng GIT_WORKFLOW.md mục «PC2 — giai đoạn 1» (xem trên GitHub, hoặc theo hướng dẫn mình
dán). KHÔNG đọc/ghi C:\TimClipPro, C:\TimClipPro_State, C:\TimClipPro_Feed. Tạo khoá deploy ~/.ssh/timclippro_dev, chỉ
in khoá CÔNG KHAI rồi dừng chờ mình thêm khoá CHỈ ĐỌC (không tick Allow write access). Kiểm vân tay máy chủ GitHub
trước khi tin. Clone vào C:\Dev\Tool_Quet; HEAD phải trùng git ls-remote private refs/heads/integration/current;
git push --dry-run phải bị từ chối. Tạo CLAUDE.local.md + .claude/settings.local.json theo mẫu. Không push.
```

## Tiếp tục việc dở (cả hai máy)
```text
Tiếp tục theo «Tiếp theo» trong docs/ai/handoff/<PC1|PC2>.md và mục nhật ký mới nhất. git fetch private; đối chiếu
nhánh/HEAD với commit ghi trong handoff và với private/integration/current trước khi làm; lệch thì báo mình.
```

## Mẫu checkpoint — thêm lên ĐẦU «Nhật ký» của `docs/ai/handoff/<máy>.md` sau mỗi việc quan trọng
```text
### YYYY-MM-DD — <việc> (nhánh <tên>)
- Làm: <1–3 dòng>
- Commit: <sha ngắn các commit mã/test của việc này>; tra commit chứa chính mục này (đúng cả sau lần sửa sau):
  git log --format=%h -S "<tiêu đề mục>" -- docs/ai/handoff/<máy>.md | tail -1
- Test: <lệnh> → <đạt / bỏ qua / hỏng> (junit hoặc bằng chứng: <đường dẫn>)
- Còn mở / rủi ro: <…>
- Tiếp theo: <bước kế, ai làm, cần duyệt gì>
```
Đổi trạng thái chung (nhánh tích hợp, bản Stable, remote, việc mở) → PC1 sửa `docs/ai/CURRENT_STATE.md` khi gộp; PC2
ghi đề xuất trong handoff hoặc mô tả PR (`docs/ai/GIT_WORKFLOW.md` «ai sửa file nào»).

## Tiết kiệm token
- Ngữ cảnh đã tự nạp (CLAUDE.md gốc + CURRENT_STATE + CLAUDE.local.md + handoff của máy) — đừng đọc lại.
- Tra `ARCHITECTURE_INDEX.md` trước, rồi `rg -n "<tên>" TimClipPro`, `git diff integration/current...HEAD --stat`,
  `git log -5 --oneline -- <file>`.
- Đọc đúng đoạn cần theo số dòng; `engine.py` ~5.700 dòng — không đọc trọn khi chỉ cần một hàm.
- Tài liệu dài (`docs/LOI_DA_GAP.md`, `MANAGED_RUNTIME_DESIGN.md`, `DATA_FLOW.md`…) chỉ `rg` theo từ khoá.
- Không mở nhiều agent nghiên cứu trùng nhau; chỉ chia việc khi các phần thật sự độc lập.
- Kết thúc việc bằng checkpoint ngắn ở trên để phiên sau đi tiếp ngay, không phải đọc lại.
