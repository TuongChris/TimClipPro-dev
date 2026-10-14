# Handoff — PC1

Giữ file ≤ 80 dòng. Mục mới thêm lên ĐẦU «Nhật ký» (mẫu: `docs/ai/SESSION_START.md`); quá 6 mục thì chuyển mục cũ nhất
sang `docs/ai/handoff/LICH_SU_PC1.md`. Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

## Máy
- Vai trò (D-23, từ 14/10): máy DỰ PHÒNG, NGANG QUYỀN PC2 — phát triển, review, tích hợp, ký (khoá `8aa5baa6c8f225f9`,
  `D:\TimClipPro_KhoaPhatHanh`), phát hành. Hostname `DESKTOP-UIQUSEM`.
- Production (đang chạy thật, KHÔNG sửa, không checkout lại khi chưa duyệt): worktree chính `Tool_Quet` trong thư mục
  OneDrive `ToolQuet`, HEAD `6dc3f9d` (detached). Mọi worktree khác dùng chung `.git` của nó.
- Worktree phát triển: `D:\TimClipPro_Dev\<tên>` (ngoài OneDrive; nhánh `--no-track` từ `private/integration/current`).
  15 worktree cũ `ToolQuet\Tool_Quet_*` của các vòng trước — dọn = việc riêng, cần duyệt.
- Bằng chứng mỗi vòng (ngoài Git): `D:\TimClipPro_<Vòng>\<thời điểm>\checkpoints\CHECKPOINT.md`.
- Remote: `private` (`TimClipPro-dev`, PUBLIC) để push; `origin` (PUBLIC) chỉ fetch — push bị chặn bằng pushurl giả.
  Hook `pre-push` dùng chung (`release/git-hooks/pre-push`): CHƯA cài trên PC1 (đề xuất, một lệnh `cp`).
- Cổng: production `ChayTool.bat` dùng 8501; PC1 không chạy server Development.

## Tiếp theo
1. (LẦN CUỐI PC1 bắt buộc) Khi người dùng báo «PC2 đã gửi yêu cầu ghi danh khoá …»: chạy
   `D:\TimClipPro_PC2Authority\20261014_222039\scripts\p_ky_uy_quyen_pc1.sh chuan-bi feature/pc2/khoa-ky-pc2` (kiểm
   yêu cầu tự ký, trust store PC2 = byte bộ kit `a37dc9b6…`, khoá đang tin = `8aa5…`) → người dùng nhấp đúp
   `KY_UY_QUYEN_PC2.bat` (gõ 8 ký tự cuối khoá PC2 + mật khẩu khoá PC1) → `… sau-ky` (kiem-uy-quyen, commit) → đẩy
   `feature/pc1/uy-quyen-pc2` (người dùng duyệt). Sau bước này PC1 không còn bắt buộc cho phát hành.
2. Đề xuất người dùng duyệt: bật ruleset GitHub (`release/github/`); cài hook dùng chung trên PC1.
3. Còn từ trước: tái audit độc lập `e49340d`; C7 (bằng chứng Stable PC2); sao lưu khoá ký (`KEY_BACKUP =
   DEFERRED_BY_USER`); dọn worktree cũ + sandbox `D:\` (~11 GB vòng 1.1.1, ~2 GB vòng này) khi người dùng bảo.

## Nhật ký
### 2026-10-14 — Hai máy ngang quyền phát hành: ghi danh khoá PC2 bằng uỷ quyền (nhánh feature/pc1/dual-release-authority)
- Phase A (đọc mã): trust store `{"khoa":[…]}` đã tin NHIỀU khoá (chọn theo `key_id` của chữ ký); nằm ngoài release,
  launcher đọc mỗi lần chạy; launcher PC2 = 5 file của `e49340d` (không đổi tới `dc29b33`) → không cần đổi launcher.
- Làm (`bd17691` mã + test + `release/`; `c1f96fa` sửa theo review): `uy_quyen_khoa.py` (yêu cầu tự ký → uỷ quyền ký bởi khoá đang tin, ràng buộc
  băm định danh cài đặt + băm trust store + hạn; ghi danh nguyên tử bằng parser launcher ĐÃ CÀI; hoàn tác), `release_tool`
  `tao-khoa / ky-uy-quyen / kiem-uy-quyen / them-khoa-danh-sach / kiem-sau-ky / feed / kit`, hook `pre-push` dùng chung,
  ruleset đề xuất, lock có băm + docopt + khoá công khai vào `release/` (D-21…D-25); tài liệu GIT_WORKFLOW, CURRENT_STATE…
- Kiểm: 103 ca test mới (đỏ trước khi có mã/sửa; cp1252 cũng xanh); đột biến 43/43; build lại 1.1.1 CHỈ từ repo = gói
  đã công bố (`510f39a6…`); diễn tập sandbox 19/19 (kit `e49340d` + 1.1.0 đã công bố, khoá THỬ vai PC1/PC2/lạ: trước
  ghi danh bị bỏ qua → ghi danh → quay về → cập nhật lên bản «PC2» ký → khoá lạ bị bỏ qua; dữ liệu giữ byte); nhanh
  2702/8/0, chậm 19/19, ruff sạch, 6 test `.gitignore` trong worktree. Review độc lập 2 lượt (agent): lượt 1 — 1 P1
  (danh tính khoá chỉ 32 bit) + 4 P2 (dùng lại sau hoàn tác, hoàn tác gỡ được khoá gốc, `sign` ký byte tuỳ ý, test
  cp1252) → đã sửa; lượt 2 — chỉ P3 → đã sửa (còn ghi chú: `icacls` nằm trong `.bat` của prompt PC2).
- Bằng chứng: `D:\TimClipPro_PC2Authority\20261014_222039\` (CHECKPOINT, logs/, evidence/, e2e/).
### 2026-10-14 — Review CookieFix (PR #4) + sửa F1/F3 trước Stable 1.1.1 (nhánh feature/pc1/cookiefix-f1-f3)
- Review PR #4 (PC2, `8bd69a7`): không P0/P1; P2 F1, P3 F2–F8. Người dùng chọn sửa F1 + F3 trước khi phát hành.
- Làm (`15e4f88`, `7c60af5` sau review phần sửa): `chay_kem_duong_lui_cookie(bo_qua=…)` — Dừng/mạng đứng đi thẳng
  ra ở lượt đầu và lượt lùi không-cookie; mọi lời gọi truyền `bo_qua` của phiên; bỏ UNKNOWN khỏi tập «có thể do JS»;
  câu «node không chạy được» không còn đường dẫn; chi tiết `LoiGiaiJs` che `X:\Users\<tên>` (`an_thu_muc_nguoi_dung`).
- Kiểm: 25 ca test mới (cả 25 đỏ trên mã `8bd69a7`), đột biến 8/9 (còn lại = đường không tới được); review độc lập
  phần sửa 2 lượt (agent): không P0/P1/P2; nhanh 2599/8/0, chậm 19/19 (455 s), ruff sạch.
- Bằng chứng: `D:\TimClipPro_Release111\20261014_154558\` (vòng review: `…\20261014_135520\`).
### 2026-10-10 — PR #1 PC2 + quy trình chung giai đoạn 2 + preview an toàn (nhánh feature/pc1/shared-workflow-preview)
- Làm: review + gộp fast-forward PR #1 của PC2 (`b627af0`, chỉ test + handoff); tài liệu chung: giai đoạn 2, gộp PR,
  lấy bản mới/xung đột, hai máy + cp1252 (D-18, D-19); `.claude/launch.json` → chỉ gắn vào 8502, `autoVerify` false;
  hook `pre-push` khuyến nghị cho PC2. Nhật ký cũ nhất chuyển sang `handoff/LICH_SU_PC1.md`.
- Kiểm: PR #1 trên PC1 — test cũ ép cp1252 → 1 hỏng (tái hiện), `test_health_check.py` 12/12 ở UTF-8 và cp1252, suite
  nhanh 2452 đạt / 8 bỏ qua / 0 hỏng, quét 0 phát hiện; 6 test `.gitignore` (bỏ qua khi chạy bản sao) chạy trong worktree
  6/6; hook trích từ tài liệu thử 11/11 trên repo giả; review độc lập 2 lượt (agent) → đã sửa mâu thuẫn/lệnh sai (đáng
  kể: thử hook phải dùng ref chưa có trên remote; PC1 `push.default=upstream` làm `git push private <nhánh>` thiếu `:đích`
  đẩy vào upstream — đã thử; `.claude/settings.json` chặn thêm ĐỌC `C:\TimClipPro*`); K1–K10 ĐẠT.
- Chưa kiểm: preview gắn 8502 trên PC2; Development 8502 / Stable 8501 mới có lời người dùng — chờ PC2 nghiệm thu.
- Bằng chứng: `D:\TimClipPro_SharedWorkflow\20261010_083311\` (CHECKPOINT, logs/, evidence/).
### 2026-10-09 — Chốt PC1 shared development (nhánh feature/pc1/ai-shared-context)
- Làm: đẩy `bff0ac3` lên `private` (fast-forward, người dùng duyệt); chuẩn hoá tài liệu: PC2 giai đoạn 1 = Deploy Key
  CHỈ ĐỌC, clone `C:\Dev\Tool_Quet`; giai đoạn 2 (ghi + PR) chỉ mô tả; mỗi phiên hỏi HEAD từ remote (D-17).
- Kiểm nạp thật (phiên Claude Code CLI ở worktree này, người dùng đăng nhập lại CLI): `/context` → Memory files đúng 4
  file `CLAUDE.md`, `docs/ai/CURRENT_STATE.md`, `CLAUDE.local.md`, `docs/ai/handoff/PC1.md`; dòng đầu phiên lồng khai
  trùng file thật. Đọc một file vùng matcher / sheets-outbox / updater → transcript ghi Claude Code chèn đúng rule của
  vùng đó + `TimClipPro/CLAUDE.md`; đọc file ngoài vùng → không chèn gì.
- Quyền chặn (dữ liệu GIẢ, đã xoá): đọc `google_key.json`, `*cookie*.txt`, `giam_sat_sheet.txt` và sửa `db.pklz`,
  `lichsu.db`, `downloaded.txt`, `clips_meta.json` → bị chặn; file đối chứng đọc/sửa được; ghi `C:\TimClipPro*` → bị chặn;
  cú pháp chặn đường dẫn tuyệt đối `//c/…` thử bằng thư mục nháp → đúng. Không thử production hay thư mục khoá.
- Bằng chứng: `D:\TimClipPro_SharedContext\20261009_111332\` (logs/nap_that/, evidence/kiem_nap_that.json).
### 2026-10-09 — Remote PRIVATE `TimClipPro-dev` (nhánh feature/pc1/ai-shared-context)
- Làm (người dùng duyệt): `integration/current` fast-forward e49340d → 9b763be; tạo repo PRIVATE; thêm remote `private`;
  đẩy DUY NHẤT `integration/current` (không tag); chặn push vào `origin`, `remote.pushDefault=private`,
  `push.default=upstream`. Repo public không đổi (18 ref như trước). Production giữ 6dc3f9d.
- Kiểm: quét lịch sử sẽ đẩy (843 blob, 90 commit, đối chứng dương 39/39) → 0 phát hiện nhạy cảm mới; GitHub
  `private=true`, ref duy nhất `refs/heads/integration/current` = `9b763be`, 0 tag; thử push nhầm `origin` → bị chặn.
- Chưa kiểm: `/context` trong phiên thật (CLI lồng chưa đăng nhập).
- Bằng chứng: `D:\TimClipPro_SharedContext\20261009_111332\` (logs/kiem_sau_push.txt, evidence/quet_truoc_push.json).
