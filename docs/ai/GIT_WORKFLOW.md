# Quy trình Git giữa PC1 và PC2

## Git chở gì — và KHÔNG BAO GIỜ chở gì
- Chở: mã nguồn, test, tài liệu, `docs/ai/` (trạng thái, quyết định, handoff), `.claude/rules/`, `.claude/settings.json`.
- Không bao giờ (đã chặn bằng `.gitignore` hoặc nằm ngoài repo): `data/`, `lichsu.db`, `db.pklz`, `downloaded.txt`,
  `clips_meta.json`, `ketqua/`, log; kho audio/vân tay; dữ liệu khách hàng (link vi phạm, watchlist thật); credentials
  (`google_key.json`, cookie, `.env`, `.pem`); khoá ký phát hành; bản phát hành, wheelhouse, bộ cài; auto-memory và
  transcript của Claude (nằm trong `~/.claude/projects/…`, riêng từng máy); `CLAUDE.local.md`,
  `.claude/settings.local.json`.
- Bản Stable sang PC2 KHÔNG đi qua Git: bộ cài/feed chuyển bằng RustDesk/USB, PC2 kiểm chữ ký trước khi cài.

## Nhánh
| Nhánh | Ai tạo | Tạo từ | Đích | Điều kiện vào đích |
|---|---|---|---|---|
| `integration/current` | PC1 giữ | — | — | chỉ fast-forward/merge nhánh đã review + test xanh; không commit thẳng |
| `feature/pc1/<tên>` | PC1 | `integration/current` | `integration/current` | test theo TEST_MATRIX + `handoff/PC1.md` đã cập nhật |
| `fix/pc2/<tên>` | PC2 | `integration/current` | `integration/current` (PC1 review) | tái hiện synthetic, test đỏ→xanh, `handoff/PC2.md` |
| nhánh cũ (`fix/managed-*`, `hardening/*`, `nguon-chung-ca-lo`…) | — | — | — | chỉ để tham chiếu, không phát triển tiếp |
- Tên nhánh: chữ thường không dấu, gạch nối, ví dụ `fix/pc2/watch-bo-qua-video`.
- Trước khi gửi review: cập nhật nhánh theo `integration/current` mới nhất rồi chạy lại test.
- Stable: chỉ build từ commit trên `integration/current` đã nghiệm thu (test đầy đủ + review/audit theo rủi ro + người
  dùng duyệt), ký trên PC1. Tag `stable-X.Y.Z` (nếu dùng) chỉ đẩy lên remote PRIVATE.
- Đưa nhánh đã duyệt vào `integration/current` khi chưa có PR (chỉ fast-forward, từ chối nếu lệch):
  `git fetch . feature/pc1/<tên>:integration/current`

## Remote
- `origin` (PC1) = GitHub `TuongChris/Tool_Quet`, **PUBLIC**. Quy trình mới KHÔNG push vào đây. Giữ tên `origin` vì
  updater cũ `cap_nhat.py` của máy legacy chạy `git fetch --tags` theo remote mặc định.
- `private` (CẢ HAI máy) = repo PRIVATE mới (đề xuất `TuongChris/TimClipPro-dev`). PC1 thêm remote tên `private`;
  PC2 clone bằng `--origin private` — hai máy cùng gõ `git push private <nhánh>`. PC2 không có remote public.
- Luồng: PC2 push `fix/pc2/<tên>` → mở PR vào `integration/current` trên repo private → PC1 review (diff + test mục
  tiêu) → merge → PC1 build/ký Stable khi cần → chuyển bộ cài/feed sang PC2. Không push thẳng `integration/current` từ
  PC2, không force-push nhánh máy kia, không merge khi test đỏ. (Bảo vệ nhánh trên repo private của gói GitHub miễn phí
  không có — dựa vào quy ước này.)

## Kế hoạch tạo private remote — CHỜ DUYỆT, CHƯA LÀM GÌ
1. Repo: tạo MỚI `TuongChris/TimClipPro-dev`, PRIVATE, trống. Không fork repo public (GitHub không cho bản fork riêng tư
   của repo public). Không dùng repo private có sẵn `TOOL_QUET_BANQUYEN_AUDIO` (lịch sử khác hẳn, không chung commit).
2. Chuyển: CHỈ nhánh `integration/current` (= e49340d + commit tài liệu đã duyệt) cùng toàn bộ commit tổ tiên.
   Không đẩy tag `v*` (đã ở public), nhánh cũ, nhánh feature đã merge.
3. Kiểm trước khi đẩy: quét mọi blob trong lịch sử sẽ đẩy theo mẫu bí mật (`release_tool.MAU_BI_MAT` + khối PEM,
   cookie, token, tên file nhạy cảm), so với lần quét đã được người dùng duyệt — phát hiện MỚI là dừng. Lịch sử có vài
   mục đã lộ sẵn ở repo public (chi tiết trong báo cáo quét ngoài Git trên PC1); repo private không làm lộ thêm.
   Không viết lại lịch sử khi đẩy: đổi SHA sẽ cắt đứt truy vết commit `e49340d` ghi trong manifest Stable 1.0.0 đã ký.
4. Lệnh (PC1, Git Bash, chạy trong một worktree bất kỳ của repo PC1 — mọi worktree dùng chung cấu hình `.git`):
   ```bash
   git fetch . feature/pc1/ai-shared-context:integration/current      # sau khi tài liệu được duyệt
   gh repo create TuongChris/TimClipPro-dev --private --description "TimClipPro dev (PC1/PC2)"
   git remote add private git@github.com:TuongChris/TimClipPro-dev.git
   git push -u private integration/current
   git ls-remote private && gh repo view TuongChris/TimClipPro-dev --json visibility
   ```
   Tuỳ chọn, duyệt riêng (chặn push nhầm lên public, fetch vẫn chạy):
   `git remote set-url --push origin DISABLED-public-repo` và `git config remote.pushDefault private`.
5. Quay lại: `git remote remove private` (chỉ local, nhánh không đổi); trả push public:
   `git remote set-url --push origin git@github.com:TuongChris/Tool_Quet.git`; `git config --unset remote.pushDefault`;
   lùi `integration/current`: `git branch -f integration/current e49340d`. Xoá repo private tạo nhầm: trang Settings của
   repo trên GitHub (người dùng tự làm; `gh` hiện không có quyền `delete_repo`). Không bước nào đụng repo public.

## PC2 — clone phát triển lần đầu (sau khi có repo private)
1. Người dùng cài Git for Windows + GitHub CLI, rồi `gh auth login` (đăng nhập qua trình duyệt) và `gh auth setup-git`.
   Chặt hơn: token fine-grained chỉ cho repo `TimClipPro-dev` (Contents: read/write).
2. `git clone --origin private --branch integration/current https://github.com/TuongChris/TimClipPro-dev.git D:\TimClipPro_Dev\TimClipPro`
   (không có D: thì `C:\Dev\TimClipPro`) — ngoài OneDrive, KHÔNG nằm trong `C:\TimClipPro*`.
3. Chép `docs/ai/CLAUDE.local.md.mau` thành `CLAUDE.local.md` (máy PC2); venv phát triển theo `docs/ai/TEST_MATRIX.md`.
4. Mỗi lỗi: `git switch -c fix/pc2/<tên> private/integration/current` … `git push -u private fix/pc2/<tên>` (khi được duyệt).
