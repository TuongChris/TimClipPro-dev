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
  `private` và là máy đẩy `integration/current`; PC2 clone bằng `--origin private`, không có remote public.
- `origin` (chỉ PC1) = GitHub `TuongChris/Tool_Quet`, **PUBLIC**. Chỉ để fetch: updater cũ `cap_nhat.py` của máy
  legacy chạy `git fetch --tags` theo remote mặc định. Push vào `origin` bị chặn (mục dưới).
- HEAD thật luôn hỏi remote, KHÔNG tin SHA ghi trong tài liệu (đó là mốc lịch sử): `git fetch private` rồi
  `git log --oneline -3 private/integration/current`; chỉ đọc, không đổi ref: `git ls-remote private refs/heads/integration/current`.
- Luồng (từ giai đoạn 2 của PC2 — mục cuối): PC2 push `fix/pc2/<tên>` → mở PR vào `integration/current` → PC1 review
  (diff + test mục tiêu) → merge → PC1 build/ký Stable khi cần → chuyển bộ cài/feed sang PC2. Không push thẳng
  `integration/current` từ PC2, không force-push nhánh máy kia, không merge khi test đỏ. (Bảo vệ nhánh trên repo
  private của gói GitHub miễn phí không có — dựa vào quy ước này.) Giai đoạn 1: PC2 chỉ clone/fetch, không push.

## Remote private — ĐÃ LÀM (người dùng duyệt từng lần đẩy)
1. Lần đầu 09/10/2026: `integration/current` fast-forward `e49340d` → `9b763be`; tạo repo PRIVATE (trống, không fork —
   GitHub không cho bản fork riêng tư của repo public); PC1 thêm remote `private`; đẩy DUY NHẤT `integration/current`
   (90 commit), không tag, không nhánh cũ. Lịch sử giữ nguyên: đổi SHA sẽ cắt truy vết `e49340d` trong manifest Stable
   1.0.0 đã ký. Không dùng repo private `TOOL_QUET_BANQUYEN_AUDIO` (lịch sử khác hẳn). Các lần sau: chỉ fast-forward.
2. Trước MỖI lần đẩy: quét mọi blob + commit mới lên GitHub (khoá, token, cookie, khối PEM, mật khẩu ghi cứng, link/ID
   Sheet, link YouTube, tên kho/khách hàng, đường dẫn cục bộ, tên file nhạy cảm; đọc cả file .zip), so với lần quét đã
   báo người dùng — phát hiện MỚI là dừng. Lần đầu: 0 mới; các mục còn lại đều đã public sẵn (chi tiết ngoài Git).
3. Chặn push nhầm (PC1; cấu hình `.git` dùng chung mọi worktree):
   `git remote set-url --push origin DISABLED_KHONG_PUSH__origin_la_repo_PUBLIC`, `git config remote.pushDefault private`,
   `git config push.default upstream` (`git push` trần chỉ đẩy nhánh đã có upstream trên `private`; nhánh mới phải gõ
   rõ `git push -u private <nhánh>`).
4. Kiểm: `git remote -v`; `git ls-remote private`; `gh api repos/TuongChris/TimClipPro-dev --jq .private` → `true`.
5. Quay lại (không bước nào đụng repo public): `git remote remove private`; `git config --unset remote.pushDefault`;
   `git config --unset push.default`; lùi `integration/current` LOCAL về commit trước (`git reflog integration/current`);
   lùi trên remote cần force-push → CẤM trừ khi người dùng duyệt. Bỏ chặn push public
   (`git config --unset remote.origin.pushurl`) CHỈ khi người dùng duyệt push lên public. Xoá repo private: Settings của
   repo trên GitHub (người dùng tự làm; `gh` không có quyền `delete_repo`).

## PC2 — giai đoạn 1: clone CHỈ ĐỌC bằng Deploy Key read-only (người dùng quyết 09/10/2026)
- Quyền: khoá deploy CHỈ ĐỌC, chỉ cho repo `TimClipPro-dev` — PC2 clone/fetch được, KHÔNG push được, không đụng được repo
  public hay tài khoản. KHÔNG tick «Allow write access». Khoá riêng nằm yên trên PC2: không chép đi đâu, không dán vào chat.
- Thư mục clone: `C:\Dev\Tool_Quet` — ngoài OneDrive, KHÔNG nằm trong `C:\TimClipPro`, `C:\TimClipPro_State`,
  `C:\TimClipPro_Feed` (Claude không đọc/ghi ba thư mục này; chỉ launcher/updater do người dùng chạy được đổi chúng).
Các bước (Git Bash trên PC2; Claude Code PC2 làm được, trừ bước 3 người dùng làm trên web):
1. `ssh-keygen -t ed25519 -f ~/.ssh/timclippro_dev -N "" -C "PC2 TimClipPro-dev read-only"` (file đã có → dừng, hỏi);
   in khoá CÔNG KHAI `~/.ssh/timclippro_dev.pub` (khoá riêng không có đuôi `.pub` — không in).
2. Thêm vào `~/.ssh/config`: `Host github-timclippro` · `HostName github.com` · `User git` ·
   `IdentityFile ~/.ssh/timclippro_dev` · `IdentitiesOnly yes`.
3. Người dùng: GitHub → repo `TimClipPro-dev` → Settings → Deploy keys → Add deploy key → dán khoá công khai, ĐỂ TRỐNG
   «Allow write access».
4. Kiểm máy chủ TRƯỚC khi tin: `ssh-keyscan -t ed25519 github.com > gh.tmp && ssh-keygen -lf gh.tmp` phải ra
   `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU` (GitHub công bố; PC1 tin đúng khoá này) → khớp mới
   `cat gh.tmp >> ~/.ssh/known_hosts`; lệch → DỪNG. Rồi `ssh -T github-timclippro` phải chào `TuongChris/TimClipPro-dev`.
5. `git clone --origin private --branch integration/current git@github-timclippro:TuongChris/TimClipPro-dev.git C:/Dev/Tool_Quet`
   (thư mục phải chưa tồn tại). Kiểm: `git rev-parse HEAD` trùng commit của `git ls-remote private refs/heads/integration/current`;
   `git remote -v` chỉ có `private`; `git status` sạch.
6. Xác nhận chỉ đọc: `git push --dry-run private integration/current` PHẢI bị từ chối (khoá chỉ đọc, không gửi gì).
   Không bị từ chối → DỪNG, báo người dùng.
7. Trong clone: chép `docs/ai/CLAUDE.local.md.mau` thành `CLAUDE.local.md` (Máy: PC2; quyền GitHub: Deploy Key CHỈ ĐỌC;
   dòng nhập cuối trỏ tới `docs/ai/handoff/PC2.md`); tạo `.claude/settings.local.json` =
   `{"permissions":{"deny":["Read(//c/TimClipPro_State/**)"]}}`. `git status` không được thấy hai file này (đã ignore).
8. Mở Claude Code ở GỐC clone (`C:\Dev\Tool_Quet`), gõ `/context`: phần file bộ nhớ phải có `CLAUDE.md`,
   `docs/ai/CURRENT_STATE.md`, `CLAUDE.local.md`, `docs/ai/handoff/PC2.md`. Rồi mở task bằng mẫu «PC2» trong
   `docs/ai/SESSION_START.md` — chỉ dựa handoff + tài liệu, không audit toàn repo.
9. Giai đoạn 1 làm được: đọc, tái hiện lỗi bằng dữ liệu synthetic, chạy test (venv riêng theo `docs/ai/TEST_MATRIX.md`,
   Python 3.12 riêng — không dùng Python của bản Stable), commit LOCAL trên `fix/pc2/<tên>`. Không push được.

## PC2 — giai đoạn 2: quyền ghi + Pull Request (CHƯA LÀM — chỉ khi người dùng duyệt)
Điều kiện: PC2 đã clone, `/context` đủ, phiên PC2 đầu tiên đúng quy trình, người dùng duyệt.
1. Quyền ghi: khoá deploy không đổi được quyền sau khi thêm → xoá khoá chỉ đọc, thêm lại CÙNG khoá công khai có tick
   «Allow write access» (người dùng trên web, hoặc PC1 bằng `gh repo deploy-key` khi được duyệt). Không cấp quyền cả tài
   khoản GitHub cho PC2.
2. PC2 chỉ đẩy nhánh `fix/pc2/<tên>`: `git switch -c fix/pc2/<tên> private/integration/current` …
   `git push -u private fix/pc2/<tên>` — mỗi lần đẩy cần người dùng duyệt + quét phần mới. Không đẩy
   `integration/current`, không force-push, không tag.
3. Pull Request vào `integration/current`: người dùng mở trên web GitHub, hoặc PC1
   `gh pr create --repo TuongChris/TimClipPro-dev --base integration/current --head fix/pc2/<tên>` (khoá deploy không gọi
   được API GitHub).
4. PC1 review (diff + test mục tiêu theo `TEST_MATRIX.md`) → merge/fast-forward vào `integration/current` → đẩy (người
   dùng duyệt).
5. Khi làm giai đoạn 2: cập nhật mục này, `handoff/PC2.md`, `CURRENT_STATE.md` và `CLAUDE.local.md` của PC2.
