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
  `git fetch . feature/pc1/<tên>:integration/current`, rồi (khi được duyệt) `git push private integration/current`.

## Remote
- `private` (CẢ HAI máy) = GitHub `TuongChris/TimClipPro-dev`, **PRIVATE** (tạo 09/10/2026). PC1 có remote tên
  `private`; PC2 clone bằng `--origin private` — hai máy cùng gõ `git push private <nhánh>`. PC2 không có remote public.
- `origin` (chỉ PC1) = GitHub `TuongChris/Tool_Quet`, **PUBLIC**. Chỉ để fetch: updater cũ `cap_nhat.py` của máy
  legacy chạy `git fetch --tags` theo remote mặc định. Push vào `origin` bị chặn (mục dưới).
- Luồng: PC2 push `fix/pc2/<tên>` → mở PR vào `integration/current` (trang web GitHub, hoặc `gh` trên PC1 — khoá deploy
  của PC2 không mở được PR) → PC1 review (diff + test mục tiêu) → merge → PC1 build/ký Stable khi cần → chuyển bộ
  cài/feed sang PC2. Không push thẳng `integration/current` từ PC2, không force-push nhánh máy kia, không merge khi test
  đỏ. (Bảo vệ nhánh trên repo private của gói GitHub miễn phí không có — dựa vào quy ước này.)

## Remote private — ĐÃ LÀM 09/10/2026 (người dùng duyệt)
1. `integration/current` fast-forward `e49340d` → `9b763be`; tạo repo PRIVATE `TuongChris/TimClipPro-dev` (trống, không
   fork — GitHub không cho bản fork riêng tư của repo public); PC1 thêm remote `private`; đẩy DUY NHẤT
   `integration/current` (90 commit), không tag, không nhánh cũ. Lịch sử giữ nguyên: đổi SHA sẽ cắt truy vết `e49340d`
   trong manifest Stable 1.0.0 đã ký. Không dùng repo private `TOOL_QUET_BANQUYEN_AUDIO` (lịch sử khác hẳn).
2. Trước khi đẩy: quét mọi blob + commit sẽ đẩy (khoá, token, cookie, khối PEM, mật khẩu ghi cứng, link/ID Sheet, link
   YouTube, tên kho/khách hàng, đường dẫn cục bộ, tên file nhạy cảm; đọc cả file .zip trong lịch sử), so với lần quét
   đã báo người dùng — phát hiện MỚI là dừng. Kết quả: 0 mới; các mục còn lại đều đã public sẵn (chi tiết ngoài Git
   trên PC1). Mỗi lần đẩy thêm vẫn quét phần lịch sử MỚI theo cùng cách.
3. Chặn push nhầm (PC1; cấu hình `.git` dùng chung mọi worktree):
   `git remote set-url --push origin DISABLED_KHONG_PUSH__origin_la_repo_PUBLIC`, `git config remote.pushDefault private`,
   `git config push.default upstream` (`git push` trần chỉ đẩy nhánh đã có upstream trên `private`; nhánh mới phải gõ
   rõ `git push -u private <nhánh>`).
4. Kiểm: `git remote -v`; `git ls-remote private`; `gh api repos/TuongChris/TimClipPro-dev --jq .private` → `true`.
5. Quay lại (không bước nào đụng repo public): `git remote remove private`; `git config --unset remote.pushDefault`;
   `git config --unset push.default`; lùi `integration/current`: `git branch -f integration/current e49340d`. Bỏ chặn
   push public (`git config --unset remote.origin.pushurl`) CHỈ khi người dùng duyệt push lên public. Xoá repo private:
   Settings của repo trên GitHub (người dùng tự làm; `gh` không có quyền `delete_repo`).

## PC2 — clone phát triển lần đầu
Quyền GitHub cho PC2 (chọn một):
- **Khuyên dùng — khoá deploy chỉ cho repo này**: PC2 đọc/ghi được đúng `TimClipPro-dev`, không đụng được repo public
  hay tài khoản. Khoá riêng nằm yên trên PC2 — không chép đi đâu, không dán vào chat.
- Đơn giản hơn nhưng rộng quyền: GitHub CLI `gh auth login` (trình duyệt) + `gh auth setup-git`, clone bằng
  `https://github.com/TuongChris/TimClipPro-dev.git` — PC2 có quyền như cả tài khoản (kể cả repo public).
Các bước khoá deploy (Git Bash trên PC2; Claude Code PC2 làm được, trừ bước 3 người dùng làm trên web):
1. `ssh-keygen -t ed25519 -f ~/.ssh/timclippro_dev -N "" -C "PC2 TimClipPro-dev"`; in khoá CÔNG KHAI
   `~/.ssh/timclippro_dev.pub` (khoá riêng không có đuôi `.pub` — không in).
2. Thêm vào `~/.ssh/config`: `Host github-timclippro` · `HostName github.com` · `User git` ·
   `IdentityFile ~/.ssh/timclippro_dev` · `IdentitiesOnly yes`.
3. Người dùng: GitHub → repo `TimClipPro-dev` → Settings → Deploy keys → Add deploy key → dán khoá công khai, tick
   «Allow write access».
4. Kiểm máy chủ TRƯỚC khi tin: `ssh-keyscan -t ed25519 github.com > gh.tmp && ssh-keygen -lf gh.tmp` phải ra
   `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU` (GitHub công bố; PC1 tin đúng khoá này) → khớp mới
   `cat gh.tmp >> ~/.ssh/known_hosts`; lệch → DỪNG. Rồi `ssh -T github-timclippro` phải chào `TuongChris/TimClipPro-dev`.
5. Clone vào thư mục RIÊNG, ngoài OneDrive, KHÔNG nằm trong `C:\TimClipPro`, `C:\TimClipPro_State`, `C:\TimClipPro_Feed`:
   `git clone --origin private --branch integration/current git@github-timclippro:TuongChris/TimClipPro-dev.git D:/TimClipPro_Dev/TimClipPro`
   (không có ổ D: thì `C:/Dev/TimClipPro`).
6. Trong clone: `git config push.default upstream`; chép `docs/ai/CLAUDE.local.md.mau` thành `CLAUDE.local.md` (Máy:
   PC2; dòng nhập cuối file trỏ tới `docs/ai/handoff/PC2.md`). Venv phát triển theo `docs/ai/TEST_MATRIX.md` (cần
   Python 3.12 riêng — không dùng Python của bản Stable).
7. Mở Claude Code ở GỐC clone, gõ `/context`: phải thấy `CLAUDE.md`, `docs/ai/CURRENT_STATE.md`, `CLAUDE.local.md`,
   `docs/ai/handoff/PC2.md`.
8. Mỗi lỗi: `git switch -c fix/pc2/<tên> private/integration/current` … `git push -u private fix/pc2/<tên>` (khi được duyệt).
