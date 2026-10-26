# Handoff — PC2

Giữ file ≤ 80 dòng. Mục mới thêm lên ĐẦU «Nhật ký» (mẫu: `docs/ai/SESSION_START.md`); quá 6 mục thì chuyển mục cũ nhất
sang `docs/ai/handoff/LICH_SU_PC2.md` (tạo khi cần). Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

## Máy
- Vai trò (D-23; D-26 từ 15/10 tối): máy phát triển CHÍNH, DEV-ONLY — làm việc hằng ngày bằng Development 8502.
- Stable 1.1.1: `C:\TimClipPro` / `C:\TimClipPro_State` / `C:\TimClipPro_Feed`, cổng 8501 — CHỈ dự phòng, không cập nhật,
  không xoá. Claude KHÔNG đọc/ghi/chạy gì trong ba thư mục này (chặn trong `.claude/settings.json`).
- Development VẬN HÀNH (D-26, ngoài Git):
  - mã: worktree `C:\Dev\TimClipPro_VanHanh` (nhánh cục bộ `pc2-van-hanh`, chỉ fast-forward theo `integration/current`);
  - Python: `C:\Dev\TimClipPro_DevRuntime\py312-f955a32807a9` (offline, lock có băm, yt-dlp-ejs 0.8.0; Node 24);
  - dữ liệu THẬT: `C:\Dev\TimClipPro_DevState\data`; output `…\output`; sao lưu `D:\TimClipPro_Dev_SaoLuu`;
  - launcher trong `C:\Dev\TimClipPro_DevState`: `TimClipPro_DEV.bat` (icon Desktop «TimClipPro DEV»; 127.0.0.1:8502,
    `fileWatcherType=none`), `_CLI`, `_SaoLuu`, `_CapNhat`, chung `_env`. Cập nhật: `GIT_WORKFLOW.md` «Development vận hành PC2».
  - KHÔNG `ChayTool.bat` / `CapNhat.bat` / `GiamSat.bat` của clone. Dừng 8502 chỉ khi KHÔNG có việc (yt-dlp tải TRONG tiến trình).
- Clone + worktree PHÁT TRIỂN: `C:\Dev\Tool_Quet` + worktree việc; test bằng venv `C:\Dev\TimClipPro_CookieFix\TimClipPro\.venv`
  (lock + pytest/ruff). Không cài/nâng gói vào Python 3.12.10 gốc.
- GitHub: Deploy Key «PC2 PC_Office read-only» (tên cũ; quyền GHI cả repo) cho git; `gh` 2.102.0 đăng nhập chủ repo
  (15/10). Hook `pre-push` dùng chung `release/git-hooks/pre-push`: ĐÃ cài 15/10.
- Khoá ký phát hành PC2: key_id `d02702dd741c3e4f`, ở `C:\TimClipPro_KhoaPhatHanh` (ngoài repo; chỉ tài khoản người dùng +
  SYSTEM; Claude không đọc), mật khẩu người dùng gõ. ĐÃ GHI DANH 15/10 vào Stable PC2 (trust store 2 khoá) và vào
  `release/trusted_keys.json` — PC2 tự ký + phát hành được, PC1 không còn bắt buộc.
- Dữ liệu: PC2 tự xây; KHÔNG chép dữ liệu từ PC1, KHÔNG chép State của Stable sang DEV. Test chỉ dữ liệu synthetic/thư mục
  tạm; dữ liệu thật chỉ dùng trong app DEV vận hành.

## Tiếp theo
1. Đợt P3 (`fix/pc2/audit-p3`, worktree `C:\Dev\TimClipPro_P3`, `a11dac4..HEAD`, CHƯA đẩy) — người dùng quyết trước:
   thân commit `03ecf8c` còn tên thư mục người dùng Windows (hook không bắt, chỉ grep tay `GIT_WORKFLOW.md` bắt; repo
   PUBLIC): chấp nhận, hay sửa lời commit (viết lại nhánh LOCAL — cần duyệt). Rồi: cài lại hook `release/git-hooks/pre-push`
   của nhánh (hook PC2 đang cài là bản cũ), quét, đẩy, `gh pr create`, review, FF `integration/current` (người dùng duyệt);
   cập nhật DEV 8502 (sao lưu trước, khi KHÔNG có việc đang chạy).
2. Người dùng: nghiệm thu DEV đợt 2 theo `C:\Dev\pc2_test_runs\2026-10-26_audit_p3\NGHIEM_THU_DEV_DOT2.md` (~15 phút).
3. Người dùng quyết: P-6 (3 phương án, `…\2026-10-26_audit_p3\P6_PHUONG_AN.md`); P-7 (`P7_THIET_KE.md` cùng thư mục, công
   cụ `C:\Dev\pc2_test_tools\p7_lich_su_bong`, CHƯA chạy dữ liệu thật — chỉ chạy CHỈ ĐỌC khi duyệt); B-13, F-16; 3 ghép
   tuỳ chọn của P0 (`ket_qua_panel.json`, mục 25/10 «P0 bóng»); Stable 1.1.3 có phát hành sau P3 hay không.
4. PC1: review `…\2026-10-26_audit_p3\GOI_REVIEW_PC1.md` (PR #15–#17 đã vào `integration/current` chưa có PC1 review, mã đang
   chạy dữ liệu THẬT trên DEV); chạy bộ đột biến outbox; quyết đề xuất E-1 (`.claude/settings.json` chặn đọc khoá Google, 2
   test xfail strict); cập nhật `CURRENT_STATE.md` theo mục 26/10.
5. Còn mở từ trước: đồng bộ tiếp kênh Joe → vân tay «Kho Joe» (tab «Kho clip gốc», không tạo kho mới); hồ sơ đích Sheets +
   binding khoá NGOÀI State Stable cho DEV; ruleset GitHub (`release/github/`, chưa bật); C7; nghiệm thu preview 8502.
6. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
### 2026-10-26 — audit độc lập 25/10: P0 bóng, YouTube, đợt 2, đợt P3 (nhánh fix/pc2/audit-p3)
- Làm: ba PR vào `integration/current` bằng fast-forward, chủ dự án duyệt từng PR: #15 P0 «bóng» D-27 + P0-1 (`d04dab9`),
  #16 YouTube D-1..D-13 (`9476387`), #17 đợt 2 vùng A, B, C, E, F (6 P1 + 17 P2 + tranh cãi A-3, C-4, C-5, F-4; `a11dac4`);
  DEV 8502 lên `a11dac4`. Đợt P3 trên nhánh này: mỗi lỗi một test đỏ → sửa; tổng kết `LOI_DA_GAP` mục 37; WR-2 không tái hiện.
- Commit: `a11dac4..HEAD` (56 commit, `daa6b31` … `7bdab54`), CHƯA đẩy; tra commit chứa mục này:
  git log --format=%h -S "audit độc lập 25/10: P0 bóng" -- docs/ai/handoff/PC2.md | tail -1
- Test (chặn mạng, cp1252, venv CookieFix) @ `3456b4e`: nhanh 3251 = 3247/4/0 (368 s; 4 bỏ qua dự kiến: symlink WinError 1314,
  file đang mở, 2 xfail strict E-1); chậm 22/22 (440 s); 52 file test mới/sửa 577/577; ruff sạch; fuzz `_merge` 10.000 trùng
  mốc `a11dac4` (dương tính mới 0, dòng mất 0, clip mất 0, crash 0). Bằng chứng ngoài Git: `2026-10-25_audit` (báo cáo tổng,
  A–F, p0), `2026-10-26_audit_dot2` (PR đợt 2, test đỏ P3), `2026-10-26_audit_p3` (junit, log, `fuzz_p3.txt`).
- Review độc lập đợt P3: 7 điểm, 2 nghiêm trọng (P2) đều thật, test đỏ trước rồi sửa — thu hẹp WR-1 làm lọt link
  `/spreadsheets/u/<n>/d/<ID>` qua hook (`7e63d9c`, hook 47/0); E-7 chỉ bắt đường dẫn gạch ngược (`7bdab54`, bắt cả
  `C:/Users/<tên>`, 4 dòng tài liệu; 86/0). Không đụng `_merge` sau review → không fuzz lại.
- Còn mở / rủi ro: «Tiếp theo» 1–4. Đề xuất `CURRENT_STATE.md` (PC1 sửa): integration = `a11dac4` (#15–#17), PC1 chưa review.
### 2026-10-26 — sửa 13 lỗi vùng YouTube theo audit (nhánh fix/pc2/youtube-audit-d)
- D-1/2/3 (P1) + D-4..D-13 (P2) + D-5: mỗi lỗi một commit test đỏ → sửa; review độc lập (Fable) → 1 P1 + 2 P2 do chính bản
  sửa gây ra, đã sửa (403 → thử client bị gỡ KHÔNG cookie, báo rõ; ghi lại cookie so-rồi-đặt; kết quả đồng bộ khi tab bị dỡ).
  9 P3 review để đợt P3 (file khoá cạnh cookie người dùng, `data/khoa_tai/*.lock` không dọn, …).
- Đặt lại nền lên `d04dab9` (P0). Test: nhanh 2931 = 2929/2/0; chậm 22/22; ruff sạch. Bằng chứng `2026-10-25_audit\D`
  (`ket_qua_sua.json`, junit). Lưu ý vận hành: ghi lại cookie tạo `.timclip.lock` cạnh `cookies.txt`.
### 2026-10-25 — P0 «bóng» (D-27) lên mã chạy + sửa P0-1 theo review độc lập (nhánh fix/pc2/chong-bong-lap)
- Cherry-pick 4128adb/200ddcf/409f609 (10/10) lên `fe461bd` (`50dcbd2`, `6ee8f43`, `6953e97`; D-21 → D-27, P-6/P-7). Review độc
  lập (Fable tìm, Opus tái hiện + phản biện): P0-1 P1 CHỨNG MINH — phủ theo khoảng [min,max] bỏ mất lần dùng thật thứ hai,
  xấu nhất thành âm tính Watch không quét lại. Thi 3 phương án, 2 giám khảo chọn `cuc_bo` → `ed2727f` (phủ theo bằng chứng
  cục bộ ngoài cửa sổ dedup_s, neo nhóm bóng đạt chuẩn vào vị trí thật, C' cần mật độ ngang bằng).
- Test (chặn mạng, cp1252, venv CookieFix): nhanh 2832 = 2830/2/0; matcher 748/0; tái hiện P0-1/2/3 13/13; chậm P0 3/3; fuzz
  mã cũ ↔ mới 2 × 10.000: dương tính mới 0, dòng mất 0, video mất dương tính 0 (6ee8f43: 18/15). Bằng chứng
  `2026-10-25_p0_bong_v2`, `2026-10-25_audit\p0`. Ghép đề xuất CHƯA làm: lưới «không bỏ ứng viên đạt cuối của clip»,
  ngưỡng chạm khi bắc cầu lỗ, luật khe cho C' (`ket_qua_panel.json`). Giới hạn: một mảnh audfprint/khúc 1 giờ phủ cả lỗ.
- Mục cũ hơn (2026-10-25 link «Đoạn vi phạm» dạng watch; 2026-10-15 DEV-ONLY D-26, tích hợp PR #9 + gom #10/#11, thanh bên cookie PR #11, nghiệm thu PR #9 + pilot, tiến độ + hiệu suất đồng bộ kênh, PR #8, chuyển quyền phát hành, review PR #6; 2026-10-14 trở về trước): `docs/ai/handoff/LICH_SU_PC2.md`.
