# Quy trình Git — PC1 và PC2 NGANG QUYỀN (từ 14/10/2026, D-23)

PC2 = máy phát triển + phát hành CHÍNH; PC1 = máy DỰ PHÒNG. Máy nào cũng được: tạo nhánh, PR, review, gộp
fast-forward vào `integration/current`, build, ký (bằng khoá RIÊNG của máy đó), phát hành — theo điểm duyệt dưới đây.
Quy trình phát hành: `TimClipPro/docs/PHAT_HANH_HAI_MAY.md`. Khoá ký mỗi máy: `TimClipPro/docs/UY_QUYEN_KHOA.md`.

## Git chở gì — và KHÔNG BAO GIỜ chở gì
- Chở: mã nguồn, test, tài liệu, `docs/ai/`, `.claude/rules/`, `.claude/settings.json`, `.claude/launch.json` (chỉ GẮN
  vào Development 8502), và `release/` — dữ liệu phát hành CÔNG KHAI: khoá công khai đang tin, lock CÓ BĂM, wheel
  docopt, hook `pre-push`, ruleset GitHub, yêu cầu/uỷ quyền ghi danh khoá (byte giữ nguyên: `.gitattributes`).
- Không bao giờ: `data/`, `lichsu.db`, `db.pklz`, `downloaded.txt`, `clips_meta.json`, `ketqua/`, log; kho audio/vân tay;
  dữ liệu khách hàng (link vi phạm, watchlist thật); credentials (`google_key.json`, cookie, `.env`); KHOÁ RIÊNG / mật
  khẩu (`*.pem`, `*.key` bị ignore ở gốc repo); bản phát hành, wheelhouse, bộ cài (đi bằng GitHub Release, không qua
  nhánh); auto-memory/transcript của Claude; `CLAUDE.local.md`, `.claude/settings.local.json`; venv, launcher
  Development, dữ liệu thử; định danh cài đặt, đường dẫn riêng máy, tên người dùng Windows.
- Bản Stable đến máy vận hành bằng **GitHub Release** (asset ZIP + SHA256SUMS + khối PowerShell kiểm băm) — không
  USB/RustDesk. Máy vận hành kiểm chữ ký trước khi cài (bộ cập nhật managed).

## Remote
- `private` (cả hai máy) = GitHub `TuongChris/TimClipPro-dev` — **PUBLIC** từ 13/10/2026 (người dùng chủ ý, xác nhận
  14/10). MỌI thứ đẩy lên là công khai → quét trước MỖI lần đẩy (dưới). Tên remote giữ là `private` (đổi tên = sửa mọi
  máy, không lợi gì).
- `origin` (chỉ PC1) = GitHub `TuongChris/Tool_Quet`, PUBLIC, CHỈ fetch (updater cũ của máy legacy); push bị chặn bằng
  pushurl giả `DISABLED_KHONG_PUSH__origin_la_repo_PUBLIC`.
- HEAD thật luôn hỏi remote, không tin SHA trong tài liệu: `git fetch private` rồi `git log --oneline -3
  private/integration/current` (chỉ đọc: `git ls-remote private refs/heads/integration/current`).
- Đẩy luôn ghi ĐỦ `nguồn:đích`: `git push private <nhánh>:<nhánh>` — máy đặt `push.default=upstream` mà thiếu `:đích`
  thì git đẩy vào UPSTREAM của nhánh (đã từng đẩy nhầm vào `integration/current`). Không `git push` trần.

## Nhánh
| Nhánh | Ai | Tạo từ | Vào đích khi |
|---|---|---|---|
| `integration/current` | cả hai máy | — | chỉ FAST-FORWARD tới đầu một nhánh việc đã qua PR + review + test xanh + người dùng duyệt gộp |
| `feature/pc1/<tên>`, `fix/pc1/<tên>` | PC1 | `private/integration/current` | PR vào `integration/current` |
| `feature/pc2/<tên>`, `fix/pc2/<tên>` | PC2 | `private/integration/current` | PR vào `integration/current` |
| nhánh cũ (`fix/managed-*`, `hardening/*`, `nguon-chung-ca-lo`…) | — | — | chỉ tham chiếu |
- Tên: chữ thường không dấu, gạch nối. Tạo KHÔNG gắn upstream vào integration:
  `git switch --no-track -c feature/pc2/<tên> private/integration/current`.
- Tag `stable-X.Y.Z`: KHÔNG đẩy bằng git; chỉ sinh khi công bố GitHub Release (`gh release create`, sau duyệt phát hành).
  Không bao giờ xoá, gắn lại, hay tái dùng tag.

## Quyền, rào chắn, điểm duyệt
| | PC1 | PC2 |
|---|---|---|
| Git push | SSH `private` | Deploy Key «PC2 PC_Office read-only» — tên cũ, quyền GHI cả repo |
| GitHub API (PR, release) | `gh` đăng nhập tài khoản chủ repo | `gh auth login --web` bằng tài khoản chủ repo (người dùng tự đăng nhập; không PAT/token vào chat/repo) |
| Hook `pre-push` (`release/git-hooks/pre-push`) | cài | cài |
| Khoá ký Stable | `D:\TimClipPro_KhoaPhatHanh` (key_id `8aa5baa6c8f225f9`) | `C:\TimClipPro_KhoaPhatHanh` (tạo trên PC2, ghi danh bằng uỷ quyền) |
- Người dùng duyệt (trong phiên): đẩy nhánh / mở PR (một duyệt cho cả việc), gộp vào `integration/current`, phát hành
  một bản (MỘT điểm duyệt — phủ ký → công bố, `PHAT_HANH_HAI_MAY.md` §2), đổi cấu hình GitHub (ruleset, khoá deploy).
- Rào chắn kỹ thuật: hook cục bộ (chặn NHẦM: tag, xoá, force-push, nhánh lạ, integration không phải fast-forward tới
  đầu nhánh việc đã đẩy — bỏ qua được bằng `--no-verify`: CẤM); ruleset GitHub (máy chủ — áp cho MỌI khoá/tài khoản):
  `release/github/ruleset_integration_current.json` (chặn xoá + force-push `integration/current`) và
  `release/github/ruleset_tag_stable.json` (tag `stable-*` không xoá/không dời). Bật (chủ repo, một lần):
  `gh api -X POST repos/TuongChris/TimClipPro-dev/rulesets --input release/github/<file>.json`; kiểm:
  `gh api repos/TuongChris/TimClipPro-dev/rulesets`. Không dùng «require pull request» (chặn fast-forward bằng push,
  nút Merge của GitHub đổi SHA).

## Quét trước MỖI lần đẩy (cả hai máy — repo công khai)
Quét TỪNG commit sắp đẩy (bí mật thêm rồi xoá ở commit sau vẫn bị đẩy); phải rỗng, trừ mẫu GIẢ đã biết trong test:
`git log -p --text --format=%B private/integration/current..HEAD | grep -n -i -E "AIza|ya29\.|gh[pousr]_|github_pat_|BEGIN [A-Z ]*PRIVATE|docs\.google\.com/spreadsheets|__Secure-|SAPISID|cookies?\.txt|@gmail\.com|[A-Z]:\\\\Users\\\\"`
và thêm: không file `.pem`/`.key`/`google_key.json`, không định danh cài đặt (`installation_id`), không đường dẫn riêng
máy. Có phát hiện MỚI → dừng, báo người dùng.

## Hook `pre-push` (cả hai máy)
Cài (Git Bash, gốc clone hoặc worktree): `H="$(git rev-parse --path-format=absolute --git-path hooks)"; cp release/git-hooks/pre-push "$H/pre-push"`
rồi kiểm `cmp release/git-hooks/pre-push "$H/pre-push" && head -c2 "$H/pre-push"` → `#!` (file LF, không BOM —
`release/**` không đổi xuống dòng khi checkout). `git config --get core.hooksPath` phải RỖNG (có giá trị thì hook ở
chỗ khác bị bỏ qua — báo người dùng). Thử bằng ref CHƯA có trên remote (dry-run, không gửi gì):
`git push --dry-run private HEAD:refs/heads/thu-hook-chan` và `git push --dry-run private HEAD:refs/tags/thu-hook-chan`
phải in «pre-push: CHẶN»; `git push --dry-run private HEAD:refs/heads/fix/pc2/thu-hook` phải qua. Test tự động:
`TimClipPro/tests/test_git_hook_pre_push.py` (repo tạm).

## Pull Request, review, gộp (máy nào cũng làm)
1. PR: `gh pr create --repo TuongChris/TimClipPro-dev --base integration/current --head <nhánh> --title … --body-file …`.
2. Review: máy KIA nếu đang làm việc; nếu không, agent review ngữ cảnh mới (chỉ đọc) + test mục tiêu theo `TEST_MATRIX.md`
   (sửa lỗi → tái hiện đỏ bằng bản cũ) + quét bí mật phần mới; ghi kết quả thành bình luận PR. Đỏ/phát hiện/vượt phạm vi →
   không gộp.
3. Gộp FAST-FORWARD, giữ SHA (GitHub tự đánh dấu PR «merged»); KHÔNG bấm nút Merge nào trên web:
   ```bash
   git fetch private
   git rev-parse private/<nhánh>        # phải đúng SHA đã review
   git merge-base --is-ancestor private/integration/current <SHA đã review> && git update-ref refs/heads/integration/current <SHA đã review> "$(git rev-parse private/integration/current)"
   git push private refs/heads/integration/current:refs/heads/integration/current
   ```
4. Không fast-forward được (integration đã đi tiếp): nhánh việc `git merge private/integration/current` (không rebase),
   test lại, review phần mới.

## Lấy bản mới, xung đột, ai sửa file nào
- Lấy bản mới: `git status` sạch → `git fetch private` → trên nhánh `integration/current` local
  `git merge --ff-only private/integration/current`. Không fast-forward được → DỪNG, báo người dùng (không `reset --hard`).
- `handoff/<máy>.md`: máy đó viết nhật ký; máy kia (qua PR) được sửa «Máy»/«Tiếp theo», sửa tham chiếu sai, chuyển mục
  «Tiếp theo» đã xong xuống nhật ký (ghi rõ máy chuyển) — KHÔNG xoá/đổi ý nhật ký của máy kia.
- `CURRENT_STATE.md`, `GIT_WORKFLOW.md`, `DECISIONS.md`, `TEST_MATRIX.md`: máy nào cũng sửa, qua PR; xung đột: GIỮ cả hai.
  Thêm/đổi tên file test → thêm dòng vùng trong CÙNG commit.
- File riêng máy (`CLAUDE.local.md`, `.claude/settings.local.json`, venv, launcher, dữ liệu thử) ngoài Git/ignore. Sửa cục
  bộ file đã theo dõi (vd. `.claude/launch.json`) → chép ra ngoài và `git restore` trước khi lấy bản mới.

## Dựng lại một máy phát triển (vd. PC2 mới)
1. Khoá deploy riêng: `ssh-keygen -t ed25519 -f ~/.ssh/timclippro_dev -N "" -C "<máy> TimClipPro-dev"`; in khoá CÔNG KHAI;
   `~/.ssh/config`: `Host github-timclippro` · `HostName github.com` · `User git` · `IdentityFile ~/.ssh/timclippro_dev` ·
   `IdentitiesOnly yes`. Người dùng thêm khoá ở Settings → Deploy keys (quyền ghi = quyết định riêng).
2. Vân tay máy chủ GitHub TRƯỚC khi tin: `ssh-keyscan -t ed25519 github.com > gh.tmp && ssh-keygen -lf gh.tmp` phải ra
   `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU` → khớp mới thêm vào `known_hosts`.
3. `git clone --origin private --branch integration/current git@github-timclippro:TuongChris/TimClipPro-dev.git <thư mục
   ngoài OneDrive, ngoài C:\TimClipPro*>`; `git config push.default upstream`; cài hook; `gh auth login --web`.
4. `CLAUDE.local.md` theo `docs/ai/CLAUDE.local.md.mau`; `.claude/settings.local.json` chặn thêm theo máy; `/context` phải
   thấy `CLAUDE.md`, `CURRENT_STATE.md`, `CLAUDE.local.md`, handoff của máy.
5. Venv phát triển `TimClipPro\.venv` theo `TEST_MATRIX.md` — không cài gói vào Python gốc (Stable dựng từ nó).

## Lịch sử (tóm tắt — chi tiết ở `DECISIONS.md`)
- 09/10: tạo repo `TimClipPro-dev` (private lúc đó), đẩy `integration/current` từ `e49340d` giữ nguyên lịch sử; PC2 clone
  chỉ đọc (giai đoạn 1) rồi được quyền ghi `fix/pc2/*` (giai đoạn 2); PR gộp fast-forward bằng `update-ref`.
- 13/10: repo chuyển PUBLIC (người dùng). Stable 1.1.0, 1.1.1 phát hành bằng GitHub Release, ký trên PC1.
- 14/10: hai máy ngang quyền (D-23) — PC2 có khoá ký riêng (ghi danh bằng uỷ quyền), quyền PR/gộp/phát hành; hook dùng
  chung; ruleset đề xuất.
