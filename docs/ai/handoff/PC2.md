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
1. Sau khi `integration/current` fast-forward tới `fix/pc2/link-doan-vi-pham-watch`: cập nhật DEV vận hành bằng
   `TimClipPro_DEV_CapNhat.bat` khi 8502 RẢNH (lock không đổi); lượt quét mới ra link `watch?v=…&t=`.
2. Người dùng: đồng bộ tiếp kênh Joe (dừng ở 266 — lỗi Claude 21:30, xem Nhật ký) → khi xong, tạo vân tay kho «Kho Joe» từ
   `E:\Kho_Tool_Quet\Kho_Joe_Bartolozzi` (tab «Kho clip gốc», không tạo kho mới). Google Sheets trong DEV: tạo hồ sơ đích
   + binding khoá nằm NGOÀI State Stable (binding «mac_dinh» đang trỏ `C:\TimClipPro_State\secrets\…`).
3. Hỏi người dùng: bật ruleset GitHub (`release/github/`) — chưa bật.
4. Còn mở từ trước: C7 (người dùng tự lấy kết quả `launcher.py doctor` của Stable); `git user.name/email` riêng cho commit
   PC2 (người dùng quyết); nghiệm thu preview 8502 khi tiện.
5. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
### 2026-10-25 — link «Đoạn vi phạm» dạng `watch?v=<ID>&t=<giây>` (nhánh fix/pc2/link-doan-vi-pham-watch)
- Chủ dự án yêu cầu: link nhảy mốc báo cáo V2 (ô «Đoạn vi phạm N…» bảng Ngang/Sheets, cột «🔗 Nhảy tới đúng mốc vi phạm»,
  CSV, hồ sơ, báo cáo nguồn chung) đổi `https://youtu.be/<ID>?t=` → `https://www.youtube.com/watch?v=<ID>&t=` cho lượt quét
  MỚI. Người dùng viết `?t=`; dùng `&t=` vì `?` thứ hai làm giây dính vào mã video (đã báo người dùng).
- Sửa một chỗ `bao_cao_v2.link_nhay`. KHÔNG đổi: ảnh chụp đã lưu (link đã chụp), hàng đợi gửi đã xếp, Sheet cũ, luật cũ
  (`Engine.link_moc`, lùi 3 s), link video gốc. Apps Script đọc ô nguyên văn, regex `[?&]v=` vẫn nhận mã → không sửa.
- Test (chặn mạng, venv `TimClipPro_CookieFix`): 13 đỏ trên mã cũ → xanh; +2 (tách `v`/`t` bằng `parse_qs`; ảnh chụp cũ giữ
  link cũ); đột biến 5/5; nhanh 2795 = 2793/2/0 (240 s); ruff sạch; không đụng quét → không chạy chậm. Bằng chứng
  `2026-10-25_link_watch`. Nhánh dựng trên `c2a66f0` (PR #13): fast-forward `integration/current` tới đây gộp cả D-26.
### 2026-10-15 (khuya) — PC2 DEV-ONLY: Development vận hành dữ liệu thật (D-26, nhánh feature/pc2/dev-van-hanh)
- Stable 1.1.2 ĐÃ công bố (GitHub, ký `d02702dd741c3e4f`, diễn tập 14/14) nhưng KHÔNG cài lên PC2. Tự động hoá cập nhật
  bị lớp quyền chặn («Production Deploy», «Self-Modification»); người dùng chọn DEV-ONLY.
- Dựng xong: venv offline 56 gói (`pip check` sạch), worktree vận hành `e74c923`, launcher, icon Desktop.
- Nghiệm thu:
  - quét file trong máy với kho SML (779/779 vân tay) trên BẢN SAO dữ liệu: đúng mốc 01:10:00, 92 s, lịch sử + CSV ghi đúng;
  - CLI cùng dữ liệu (`dich`, `youtube-doctor`: cookie FILE có đăng nhập, Node + EJS dùng được);
  - sao lưu + cập nhật Git-only: 3 ca thử (fast-forward / lệch / bẩn).
- Đồng bộ kênh THẬT (người dùng, 20:52–21:30, cookie đăng nhập, mã `e74c923`): +104 video (162 video/giờ, 97,6 giờ
  audio/giờ). LỖI CLAUDE: 21:30 tắt server Dev tạm để đổi sang bản vận hành khi lượt này còn tải (yt-dlp tải trong tiến
  trình — kiểm «nhàn rỗi» chỉ xem tiến trình con + CPU). Không mất dữ liệu: 266 file = 266 dòng `downloaded.txt` = 266
  metadata khớp kích thước; `_tam` rỗng. Bằng chứng ngoài Git: `2026-10-15_dev_van_hanh`.
### 2026-10-15 (tối) — tích hợp PR #9 + gom PR #10, #11 (nhánh feature/pc2/tich-hop-pr10-pr11)
- PR #9 vào `integration/current` bằng fast-forward tới `831c045` (người dùng duyệt, tự chạy lệnh đẩy vì lớp quyền Claude
  chặn; nhánh này chỉ vào SAU bước đó). PR #10 (`38bd2ba`) và PR #11
  (`0ecd474`) tạo từ base cũ `97d36e0` → cherry-pick `-x` lên `831c045`: `f944d58` (nhớ client tính từ lúc học),
  `21a05db` (thanh bên cookie không đăng nhập), không xung đột mã. Handoff hợp nhất tay (commit docs của PR #11 `f9c8663`
  KHÔNG cherry-pick: mục review PR #6 nó chuyển đã nằm trong LICH_SU từ `6448543`; mục «LOCAL, CHƯA đẩy» đã lỗi thời).
- PR #10: test hành vi đỏ trên mã cũ (`['android', ''] != ['', 'android']`), 3 test mới, đột biến 4/4. Pilot 1 video
  (người dùng duyệt, 17:11): client mặc định → visionos, 251 opus CHỈ TIẾNG, 5 request.
- Test trên đầu nhánh này (chặn mạng, venv `TimClipPro_CookieFix`): mục tiêu yt-dlp/cookie/đồng bộ kênh/huỷ/tiến độ/
  giao diện 607/607; nhanh 2793 = 2791/2/0; chậm 19/19 (372 s); ruff sạch; quét bí mật 0. Review độc lập (agent ngữ cảnh mới):
  không P0/P1; 2 P2 CÓ TỪ TRƯỚC, để PR sau — `scan_ui` xét «JS chưa sẵn sàng» trước trạng thái file (đồng bộ kênh vẫn dừng ở
  lỗi cookie khi file hỏng); `co_cookie_dang_nhap` đếm cả cookie đăng nhập ĐÃ HẾT HẠN.
- Thay PR #10 + #11 bằng PR tích hợp mới; hai PR cũ đóng sau khi PR mới vào `integration/current`.
- Mục cũ hơn (2026-10-15 thanh bên cookie PR #11, nghiệm thu PR #9 + pilot, tiến độ + hiệu suất đồng bộ kênh, PR #8 xác thực, chuyển quyền phát hành, review PR #6; 2026-10-14 trở về trước): `docs/ai/handoff/LICH_SU_PC2.md`.
