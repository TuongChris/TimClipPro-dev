# Handoff — PC1

Giữ file ≤ 80 dòng. Mục mới thêm lên ĐẦU «Nhật ký» (mẫu: `docs/ai/SESSION_START.md`); quá 6 mục thì chuyển mục cũ nhất
sang `docs/ai/handoff/LICH_SU_PC1.md`. Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

## Máy
- Vai trò: phát triển, tích hợp, review, ký Stable. Hostname `DESKTOP-UIQUSEM`.
- Production (đang chạy thật, KHÔNG sửa, không checkout lại khi chưa duyệt): worktree chính `Tool_Quet` trong thư mục
  OneDrive `ToolQuet`, HEAD `6dc3f9d` (detached). Mọi worktree khác dùng chung `.git` của nó.
- Worktree phát triển mới: đặt ở `D:\TimClipPro_Dev\<tên>` (ngoài OneDrive; nhánh tạo bằng `--no-track` từ
  `private/integration/current`). 15 worktree cũ `ToolQuet\Tool_Quet_*`
  là của các vòng trước — nội dung đều đã nằm trong e49340d, riêng `nguon-chung-ca-lo`/`sua-vung-final` (a602891) đã
  được tích hợp bằng commit khác (3218aff, d67ce31). Dọn chúng = việc riêng, cần duyệt.
- Bằng chứng mỗi vòng (ngoài Git): `D:\TimClipPro_<Vòng>\<thời điểm>\checkpoints\CHECKPOINT.md`.
- Đường dẫn cục bộ khác (khoá ký, bộ phát hành, Python): `CLAUDE.local.md` của PC1 (không vào Git).
- Remote: `private` (`TimClipPro-dev`, PRIVATE) để push; `origin` (PUBLIC) chỉ fetch — push bị chặn bằng pushurl giả.
  PR của PC2: PC1 review + gộp fast-forward (`docs/ai/GIT_WORKFLOW.md` «Pull Request và gộp»).
- Cổng: production `ChayTool.bat` dùng 8501; PC1 không chạy server Development.

## Tiếp theo
1. Chờ PC2 nghiệm thu bản 10/10 (`handoff/PC2.md` «Tiếp theo» 1): fetch + fast-forward, Development 8502, Stable 8501
   độc lập, test hồi quy + smoke, hook `pre-push`. Preview gắn 8502 CHƯA PASS tới khi PC2 báo.
2. Nhận bằng chứng cài Stable từ PC2 → đóng C7 trong `CURRENT_STATE.md`.
3. Gửi e49340d đi tái audit độc lập.
4. Pilot thật có kiểm soát (Sheets/YouTube trên PC2) — chỉ khi người dùng duyệt.
5. Sao lưu khoá ký ra USB khi có USB.
6. (Tuỳ, cần duyệt) dọn nhánh đã gộp trên remote khi máy kia không còn dùng.

## Nhật ký
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
### 2026-10-09 — Ngữ cảnh chung PC1/PC2 (nhánh feature/pc1/ai-shared-context)
- Làm: inventory chỉ đọc (Git, worktree, remote, tài liệu); `CLAUDE.md` gốc, `docs/ai/*`, `.claude/rules/*`,
  `.claude/settings.json`; chuẩn hoá `TimClipPro/CLAUDE.md` 782 → 198 dòng (phần dài chuyển nguyên
  văn); tạo nhánh local `integration/current` = e49340d. Không push, không đổi remote, production giữ 6dc3f9d.
- Kiểm: kiem_tai_lieu 9/9 ĐẠT (phủ 646/646 dòng có chữ; 79 glob rule khớp; 138/138 file test đúng một vùng; 0 bí mật, đối chứng dương 14/14); quét lịch sử commit `b05a74d`: 0 phát hiện mới; suite nhanh trên cây `b05a74d`: 2445 đạt / 8 bỏ qua / 0 hỏng; chậm `test_hai_may_gia_lap.py` 1/1; rào chắn: sạch
- Bằng chứng: `D:\TimClipPro_SharedContext\20261009_111332\` (CHECKPOINT, evidence/).
- Tiếp theo: mục «Tiếp theo» ở trên.
### 2026-10-09 — Bộ cài one-click PC2 (ngoài repo)
- ZIP `b0847ea7…caa8` (129.649.071 B), 65 file; thử 13/13 trong thư mục sạch (máy không có Windows Sandbox).
- Bằng chứng: `D:\TimClipPro_StableRelease\20261008_132859\` (oneclick/, evidence/thu_oneclick_lan3.json).
