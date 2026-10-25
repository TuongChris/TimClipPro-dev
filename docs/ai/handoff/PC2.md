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
1. P0 đã gộp (`d04dab9`); gộp `fix/pc2/youtube-audit-d` rồi cập nhật DEV khi rảnh. Audit 25/10: báo cáo tổng
   `C:\Dev\pc2_test_runs\2026-10-25_audit\BAO_CAO_AUDIT_TONG.md` — 101 lỗi, 10 P1 + 26 P2 chứng minh; người dùng duyệt sửa hết (đợt 2: A, B, C, E, F + P3).
2. Người dùng: đồng bộ tiếp kênh Joe (dừng ở 266 — lỗi Claude 21:30, xem Nhật ký) → khi xong, tạo vân tay kho «Kho Joe» từ
   `E:\Kho_Tool_Quet\Kho_Joe_Bartolozzi` (tab «Kho clip gốc», không tạo kho mới). Google Sheets trong DEV: tạo hồ sơ đích
   + binding khoá nằm NGOÀI State Stable (binding «mac_dinh» đang trỏ `C:\TimClipPro_State\secrets\…`).
3. Hỏi người dùng: bật ruleset GitHub (`release/github/`) — chưa bật.
4. Còn mở từ trước: C7 (người dùng tự lấy kết quả `launcher.py doctor` của Stable); `git user.name/email` riêng cho commit
   PC2 (người dùng quyết); nghiệm thu preview 8502 khi tiện.
5. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
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
### 2026-10-25 — link «Đoạn vi phạm» dạng `watch?v=<ID>&t=<giây>` (nhánh fix/pc2/link-doan-vi-pham-watch)
- Chủ dự án yêu cầu: link nhảy mốc báo cáo V2 (ô «Đoạn vi phạm N…» bảng Ngang/Sheets, cột «🔗 Nhảy tới đúng mốc vi phạm»,
  CSV, hồ sơ, báo cáo nguồn chung) đổi `https://youtu.be/<ID>?t=` → `https://www.youtube.com/watch?v=<ID>&t=` cho lượt quét
  MỚI. Người dùng viết `?t=`; dùng `&t=` vì `?` thứ hai làm giây dính vào mã video (đã báo người dùng).
- Sửa một chỗ `bao_cao_v2.link_nhay`. KHÔNG đổi: ảnh chụp đã lưu (link đã chụp), hàng đợi gửi đã xếp, Sheet cũ, luật cũ
  (`Engine.link_moc`, lùi 3 s), link video gốc. Apps Script đọc ô nguyên văn, regex `[?&]v=` vẫn nhận mã → không sửa.
- Test (chặn mạng, venv `TimClipPro_CookieFix`): 13 đỏ trên mã cũ → xanh; +2 (tách `v`/`t` bằng `parse_qs`; ảnh chụp cũ giữ
  link cũ); đột biến 5/5; nhanh 2795 = 2793/2/0 (240 s); ruff sạch; không đụng quét → không chạy chậm. Bằng chứng
  `2026-10-25_link_watch`. Nhánh dựng trên `c2a66f0` (PR #13): fast-forward `integration/current` tới đây gộp cả D-26.
- Mục cũ hơn (2026-10-15 DEV-ONLY D-26, tích hợp PR #9 + gom #10/#11, thanh bên cookie PR #11, nghiệm thu PR #9 + pilot, tiến độ + hiệu suất đồng bộ kênh, PR #8, chuyển quyền phát hành, review PR #6; 2026-10-14 trở về trước): `docs/ai/handoff/LICH_SU_PC2.md`.
