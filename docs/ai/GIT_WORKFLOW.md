# Quy trình Git giữa PC1 và PC2

## Git chở gì — và KHÔNG BAO GIỜ chở gì
- Chở: mã nguồn, test, tài liệu, `docs/ai/` (trạng thái, quyết định, handoff), `.claude/rules/`, `.claude/settings.json`,
  `.claude/launch.json` (chỉ cấu hình GẮN vào Development cổng 8502 — không tự khởi động gì).
- Không bao giờ (đã chặn bằng `.gitignore` hoặc nằm ngoài repo): `data/`, `lichsu.db`, `db.pklz`, `downloaded.txt`,
  `clips_meta.json`, `ketqua/`, log; kho audio/vân tay; dữ liệu khách hàng (link vi phạm, watchlist thật); credentials
  (`google_key.json`, cookie, `.env`, `.pem`); khoá ký phát hành; bản phát hành, wheelhouse, bộ cài; auto-memory và
  transcript của Claude (nằm trong `~/.claude/projects/…`, riêng từng máy); `CLAUDE.local.md`,
  `.claude/settings.local.json`; venv, launcher Development và dữ liệu thử của từng máy.
- Bản Stable sang PC2 KHÔNG đi qua Git: bộ cài/feed chuyển bằng RustDesk/USB, PC2 kiểm chữ ký trước khi cài.

## Nhánh
| Nhánh | Ai tạo | Tạo từ | Đích | Điều kiện vào đích |
|---|---|---|---|---|
| `integration/current` | PC1 giữ | — | — | chỉ fast-forward nhánh đã review qua PR + test xanh; không commit thẳng |
| `feature/pc1/<tên>` | PC1 | `integration/current` | `integration/current` (PR) | test theo TEST_MATRIX + `handoff/PC1.md` đã cập nhật |
| `fix/pc2/<tên>` | PC2 | `integration/current` | `integration/current` (PR, PC1 review) | tái hiện synthetic, test đỏ→xanh, `handoff/PC2.md` |
| nhánh cũ (`fix/managed-*`, `hardening/*`, `nguon-chung-ca-lo`…) | — | — | — | chỉ để tham chiếu, không phát triển tiếp |
- Tên nhánh: chữ thường không dấu, gạch nối, ví dụ `fix/pc2/watch-bo-qua-video`. Tạo nhánh việc KHÔNG gắn upstream vào
  `integration/current`: `git switch --no-track -c fix/pc2/<tên> private/integration/current`.
- Trước khi gửi review: cập nhật nhánh theo `integration/current` mới nhất (mục «Lấy bản mới») rồi chạy lại test.
- Stable: chỉ build từ commit trên `integration/current` đã nghiệm thu (test đầy đủ + review/audit theo rủi ro + người
  dùng duyệt), ký trên PC1. Tag `stable-X.Y.Z` (nếu dùng) chỉ PC1 đẩy, chỉ lên remote PRIVATE.

## Remote
- `private` (CẢ HAI máy) = GitHub `TuongChris/TimClipPro-dev`, **PRIVATE** (tạo 09/10/2026). PC1 là máy DUY NHẤT đẩy
  `integration/current`; PC2 clone bằng `--origin private`, không có remote public.
- `origin` (chỉ PC1) = GitHub `TuongChris/Tool_Quet`, **PUBLIC**. Chỉ để fetch: updater cũ `cap_nhat.py` của máy
  legacy chạy `git fetch --tags` theo remote mặc định. Push vào `origin` bị chặn (mục «Remote private — đã làm»).
- HEAD thật luôn hỏi remote, KHÔNG tin SHA ghi trong tài liệu (đó là mốc lịch sử): `git fetch private` rồi
  `git log --oneline -3 private/integration/current`. Chỉ đọc, không đổi ref:
  `git ls-remote private refs/heads/integration/current`.

## Quyền PC2 — giai đoạn 2 (ĐANG ÁP DỤNG từ 09/10/2026, người dùng bật)
- Bật quyền ghi (người dùng đã làm 09/10): xoá khoá chỉ đọc trên GitHub, thêm lại CÙNG khoá công khai, tick «Allow write
  access» (khoá deploy không sửa được quyền sau khi thêm). Thu hẹp lại CHỈ ĐỌC: làm ngược lại, không tick.
- Quyền thật: Deploy Key ghi được CẢ repo `TimClipPro-dev`; tên khoá trên GitHub vẫn ghi «read-only» (tên không sửa
  được). Xem ở Settings → Deploy keys, hoặc PC1: `gh repo deploy-key list --repo TuongChris/TimClipPro-dev`.
- Quy ước tên nhánh KHÔNG phải giới hạn kỹ thuật: khoá này đẩy được MỌI nhánh, kể cả `integration/current`, và tạo được
  tag. Gói tài khoản chưa kiểm: nếu gói có bảo vệ nhánh/ruleset cho repo private thì nên bật cho `integration/current`;
  không có thì giới hạn chỉ là quy ước này + hook dưới + duyệt của người dùng.
- PC2 CHỈ đẩy `fix/pc2/<tên>`, mỗi lần khi người dùng duyệt, sau khi quét phần mới (dưới); luôn ghi ĐỦ `nguồn:đích`:
  `git push -u private fix/pc2/<tên>:fix/pc2/<tên>` lần đầu, sau đó `git push private fix/pc2/<tên>:fix/pc2/<tên>` —
  không `git push` trần, không bỏ `:đích` (máy đặt `push.default=upstream` như PC1 thì thiếu `:đích` git đẩy vào UPSTREAM
  của nhánh — đã thử: nhánh theo dõi `integration/current` bị đẩy thẳng vào `integration/current`).
- PC2 KHÔNG: đẩy `integration/current`; force-push (kể cả nhánh của mình); tạo/đẩy tag; tạo release; xoá nhánh trên
  remote; sửa nhánh của PC1.
- Quét tối thiểu trước khi đẩy (PC2) — quét TỪNG commit sắp đẩy (bí mật thêm rồi xoá ở commit sau vẫn bị đẩy); phải rỗng,
  trừ mẫu GIẢ trong test đã biết; PC1 quét lại đầy đủ khi review PR:
  `git log -p --text --format=%B private/integration/current..HEAD | grep -n -i -E "AIza|ya29\.|gh[pousr]_|github_pat_|PRIVATE KEY|docs\.google\.com/spreadsheets|__Secure-|SAPISID|cookies?\.txt|@gmail\.com"`

Hook `pre-push` CỤC BỘ — chặn kỹ thuật duy nhất phía PC2 (khuyến nghị; bỏ qua được bằng `--no-verify`: CẤM dùng). File
`C:\Dev\Tool_Quet\.git\hooks\pre-push` (không đuôi), lưu LF, KHÔNG BOM, không thụt lề, `#!` ở byte đầu (kiểm:
`head -c2 .git/hooks/pre-push` ra `#!`) — sai định dạng thì MỌI lần push hỏng. Chỉ cho `fix/pc2/*`; chặn tag, xoá, force:
```sh
#!/bin/sh
# pre-push PC2: Deploy Key ghi được CẢ repo — chỉ cho fix/pc2/*; chặn tag, xoá nhánh, force-push.
z=0000000000000000000000000000000000000000
while read lref lsha rref rsha; do
  case "$rref" in refs/heads/fix/pc2/*) ;; *) echo "pre-push: CHẶN $rref — PC2 chỉ đẩy fix/pc2/*" >&2; exit 1;; esac
  [ "$lsha" = "$z" ] && { echo "pre-push: CHẶN xoá $rref" >&2; exit 1; }
  if [ "$rsha" != "$z" ] && ! git merge-base --is-ancestor "$rsha" "$lsha" 2>/dev/null; then
    echo "pre-push: CHẶN force-push $rref (fetch trước nếu remote có commit mới)" >&2; exit 1
  fi
done
exit 0
```
Thử hook bằng ref CHƯA có trên remote (đẩy ref đã trùng remote thì git báo «Everything up-to-date»; hook không nhận dòng
nào cho ref đó nên không chặn được — thử kiểu đó luôn «đạt» dù chưa cài hook):
`git push --dry-run private HEAD:refs/heads/thu-hook-chan` và `git push --dry-run private HEAD:refs/tags/thu-hook-chan`
phải in «pre-push: CHẶN»; `git push --dry-run private HEAD:refs/heads/fix/pc2/thu-hook` phải đi qua (dry-run, không gửi gì).

## Pull Request và gộp (PC1 làm)
1. PR vào `integration/current`: người dùng mở trên web GitHub, hoặc PC1
   `gh pr create --repo TuongChris/TimClipPro-dev --base integration/current --head <nhánh>` (khoá deploy không gọi được
   API GitHub nên PC2 không tự mở PR).
2. PC1 review: phạm vi diff; test mục tiêu theo `TEST_MATRIX.md` (sửa lỗi → tái hiện đỏ bằng bản cũ); quét bí mật phần
   mới; ghi kết quả thành bình luận PR. Test đỏ, quét có phát hiện, hay phạm vi vượt mô tả → không gộp.
3. Gộp FAST-FORWARD, giữ nguyên SHA (GitHub tự đánh dấu PR «merged» — PR #1 ngày 10/10 làm đúng cách này). KHÔNG bấm nút
   Merge nào trên web (merge commit / squash / rebase): đổi SHA hoặc thêm commit gộp, sai quy ước «chỉ fast-forward». Lệnh:
   ```bash
   git fetch private
   git rev-parse private/<nhánh>        # phải đúng SHA đã review
   git merge-base --is-ancestor private/integration/current <SHA đã review> && git update-ref refs/heads/integration/current <SHA đã review> "$(git rev-parse private/integration/current)"
   git push private refs/heads/integration/current:refs/heads/integration/current
   ```
4. Không fast-forward được (integration đã đi tiếp): nhánh việc cập nhật theo mục dưới, rồi review lại phần mới.

## Lấy bản mới, xử lý xung đột, ai sửa file nào (cả hai máy)
- Lấy bản mới, không ghi đè việc đang làm: `git status` phải sạch (hoặc commit việc dở trên nhánh việc), rồi trên nhánh
  `integration/current` local: `git fetch private` và `git merge --ff-only private/integration/current`. Không
  fast-forward được = nhánh local đã lệch: DỪNG, báo người dùng — không `reset --hard`, không force.
- Nhánh việc đi sau `integration/current`: `git merge private/integration/current` vào nhánh việc (không rebase — rebase
  đổi SHA rồi buộc force-push) → giải xung đột → chạy lại test mục tiêu → `git push private <nhánh>:<nhánh>`. PC1 vẫn
  gộp fast-forward (commit gộp của nhánh việc đi vào `integration/current`).
- Ai sửa gì: `handoff/<máy>.md` — máy đó viết nhật ký; PC1 (trên nhánh `feature/pc1/*`, qua PR) có thể sửa «Máy»/«Tiếp
  theo» của handoff PC2, sửa tham chiếu sai, và chuyển mục «Tiếp theo» đã xong xuống Nhật ký PC2 (ghi rõ «PC1 chuyển»);
  KHÔNG xoá hay đổi ý mục nhật ký của PC2. `CURRENT_STATE.md`, `GIT_WORKFLOW.md`, `DECISIONS.md` — PC1 sửa; PC2
  ghi đề xuất trong handoff/mô tả PR. `TEST_MATRIX.md` — ai thêm/đổi tên file test thì thêm dòng vùng trong CÙNG commit
  (kể cả trên `fix/pc2/*`); bảng «Kết quả» do PC1 chép khi gộp. Giải xung đột: GIỮ cả hai phía.
- File riêng máy (`CLAUDE.local.md`, `.claude/settings.local.json`, venv, launcher, dữ liệu thử) nằm ngoài Git hoặc bị
  ignore — `git pull`/`merge` không đụng tới. Sửa cục bộ trên file đã theo dõi (ví dụ `.claude/launch.json`) phải chép ra
  ngoài và trả lại bản gốc (`git restore <file>`) trước khi lấy bản mới — không commit nhầm.

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
   `git config push.default upstream` (`git push` trần chỉ đẩy nhánh đã có upstream trên `private`). Lưu ý: với cấu
   hình này `git push private <nhánh>` THIẾU `:đích` đẩy vào upstream của nhánh — luôn gõ `git push private <nhánh>:<nhánh>`.
4. Kiểm: `git remote -v`; `git ls-remote private`; `gh api repos/TuongChris/TimClipPro-dev --jq .private` → `true`.
5. Quay lại (không bước nào đụng repo public): `git remote remove private`; `git config --unset remote.pushDefault`;
   `git config --unset push.default`; lùi `integration/current` LOCAL về commit trước (`git reflog integration/current`);
   lùi trên remote cần force-push → CẤM trừ khi người dùng duyệt. Bỏ chặn push public
   (`git config --unset remote.origin.pushurl`) CHỈ khi người dùng duyệt push lên public. Xoá repo private: Settings của
   repo trên GitHub (người dùng tự làm; `gh` không có quyền `delete_repo`).
6. 10/10: PR #1 của PC2 (`fix/pc2/windows-health-encoding`) gộp fast-forward sau review PC1 (mục «Pull Request và gộp»).

## PC2 — giai đoạn 1: clone (XONG 09/10/2026; giữ để dựng lại máy)
Dựng lại PC2 hay máy mới: bắt đầu bằng khoá deploy CHỈ ĐỌC, KHÔNG tick «Allow write access»; quyền ghi là bước riêng,
cần người dùng duyệt (mục «Quyền PC2 — giai đoạn 2»).
- Thư mục clone: `C:\Dev\Tool_Quet` — ngoài OneDrive, KHÔNG nằm trong `C:\TimClipPro`, `C:\TimClipPro_State`,
  `C:\TimClipPro_Feed` (Claude không đọc/ghi ba thư mục này; chỉ launcher/updater do người dùng chạy được đổi chúng).
Các bước (Git Bash; Claude Code PC2 làm được, trừ bước 3 người dùng làm trên web):
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
7. Trong clone: chép `docs/ai/CLAUDE.local.md.mau` thành `CLAUDE.local.md` (Máy: PC2; quyền GitHub; dòng nhập cuối trỏ
   tới `docs/ai/handoff/PC2.md`); tạo `.claude/settings.local.json` =
   `{"permissions":{"deny":["Read(//c/TimClipPro_State/**)"]}}` (từ 10/10 `.claude/settings.json` chung đã chặn đọc + sửa
   cả ba `C:\TimClipPro*`; bản local giữ làm lớp thứ hai). `git status` không được thấy hai file này (đã ignore).
8. Mở Claude Code ở GỐC clone (`C:\Dev\Tool_Quet`), gõ `/context`: phần file bộ nhớ phải có `CLAUDE.md`,
   `docs/ai/CURRENT_STATE.md`, `CLAUDE.local.md`, `docs/ai/handoff/PC2.md`. Rồi mở task bằng mẫu «PC2» trong
   `docs/ai/SESSION_START.md` — chỉ dựa handoff + tài liệu, không audit toàn repo.
9. Venv phát triển riêng `TimClipPro\.venv` theo `docs/ai/TEST_MATRIX.md` — không dùng venv/runtime của bản Stable;
   tạo từ Python 3.12 gốc của máy thì KHÔNG cài/nâng cấp gói vào chính Python gốc đó (Stable dựng từ nó).
