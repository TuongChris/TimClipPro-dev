# Handoff — PC2

Giữ file ≤ 80 dòng. Mục mới thêm lên ĐẦU «Nhật ký» (mẫu: `docs/ai/SESSION_START.md`); quá 6 mục thì chuyển mục cũ nhất
sang `docs/ai/handoff/LICH_SU_PC2.md` (tạo khi cần). Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

## Máy
- Vai trò (D-23, từ 14/10): máy phát triển + phát hành CHÍNH, vận hành Stable 8501; PC1 là dự phòng, ngang quyền.
- Stable: `C:\TimClipPro` (cài đặt), `C:\TimClipPro_State` (dữ liệu, `lichsu.db`, kho), `C:\TimClipPro_Feed` (feed);
  cổng 8501 (`127.0.0.1`); người dùng báo đang chạy 1.1.1 (14/10). Claude KHÔNG đọc/ghi/chạy gì trong ba thư mục này
  (chặn trong `.claude/settings.json`); chỉ launcher/updater/công cụ do NGƯỜI DÙNG chạy (file `.bat`).
- Clone phát triển: `C:\Dev\Tool_Quet` (ngoài OneDrive). Venv `TimClipPro\.venv`; venv có lock 1.1.1 + pytest:
  `C:\Dev\TimClipPro_CookieFix\TimClipPro\.venv`. Không cài/nâng gói vào Python 3.12.10 gốc (Stable dựng từ nó).
- Development: cổng 8502, launcher RIÊNG ngoài Git — `--server.port=8502` ghi rõ, `--server.address=127.0.0.1`,
  `TIMCLIP_DEV_MODE=1`, data/output thử, không cookie/`google_key.json` thật; KHÔNG chạy `ChayTool.bat`, `CapNhat.bat`,
  `GiamSat.bat` trong clone. Preview: `.claude/launch.json` chỉ gắn 8502.
- GitHub: Deploy Key «PC2 PC_Office read-only» (tên cũ; quyền GHI cả repo) cho git; `gh` 2.102.0 đăng nhập chủ repo
  (15/10). Hook `pre-push` dùng chung `release/git-hooks/pre-push`: ĐÃ cài 15/10.
- Khoá ký phát hành PC2: key_id `d02702dd741c3e4f`, ở `C:\TimClipPro_KhoaPhatHanh` (ngoài repo; chỉ tài khoản người dùng +
  SYSTEM; Claude không đọc), mật khẩu người dùng gõ. ĐÃ GHI DANH 15/10 vào Stable PC2 (trust store 2 khoá) và vào
  `release/trusted_keys.json` — PC2 tự ký + phát hành được, PC1 không còn bắt buộc.
- Dữ liệu: PC2 tự xây; KHÔNG chép dữ liệu từ PC1. Test chỉ dùng dữ liệu synthetic/thư mục tạm.

## Tiếp theo
1. PR tích hợp (PR #9 đã vào + #10 + #11) → người dùng duyệt gộp FF → chuẩn bị Stable 1.1.2 (ký khoá PC2
   `d02702dd741c3e4f`, `TimClipPro/docs/PHAT_HANH_HAI_MAY.md`) → checkpoint người dùng ký + công bố + cập nhật Stable →
   xuất lại cookie đăng nhập → một lượt đồng bộ thật đo lợi định dạng trên cả lượt. PR #8 đã gộp (`97d36e0`).
2. Hỏi người dùng: bật ruleset GitHub (`release/github/`) — chưa bật.
3. Còn mở từ trước: C7 (người dùng tự lấy kết quả `launcher.py doctor` của Stable); `git user.name/email` riêng cho commit
   PC2 (người dùng quyết); nghiệm thu preview 8502 khi tiện.
4. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
### 2026-10-15 (tối) — tích hợp PR #9 + gom PR #10, #11 (nhánh feature/pc2/tich-hop-pr10-pr11)
- PR #9 vào `integration/current` bằng fast-forward tới `831c045` (người dùng duyệt). PR #10 (`38bd2ba`) và PR #11
  (`0ecd474`) tạo từ base cũ `97d36e0` → cherry-pick `-x` lên `831c045`: `f944d58` (nhớ client tính từ lúc học),
  `21a05db` (thanh bên cookie không đăng nhập), không xung đột mã. Handoff hợp nhất tay (commit docs của PR #11 `f9c8663`
  KHÔNG cherry-pick: mục review PR #6 nó chuyển đã nằm trong LICH_SU từ `6448543`; mục «LOCAL, CHƯA đẩy» đã lỗi thời).
- Thay PR #10 + #11 bằng PR tích hợp mới; hai PR cũ đóng sau khi PR mới vào `integration/current`. Số test: PR tích hợp.
### 2026-10-15 — thanh bên «Trạng thái YouTube» hết nói «DÙNG cookie đăng nhập» với file không đăng nhập được (fix/pc2/cookie-status-no-login)
- Ca thật (Development 8502): file cookie đúng cấu trúc, KHÔNG có LOGIN_INFO/SAPISID, máy có Node + EJS → dòng trên «KHÔNG có
  cookie đăng nhập», dòng dưới vẫn «Khi quét: DÙNG cookie đăng nhập…» (kết quả đồng bộ thì đúng: `KHONG_CO_COOKIE_DANG_NHAP`).
- Sửa `0ecd474` (PR #11; cherry-pick `21a05db`; chỉ câu chữ, `scan_ui.dong_trang_thai_youtube`), nguồn FILE + JS sẵn sàng: file thiếu/không đọc được/sai cấu
  trúc → cảnh báo «KHÔNG đăng nhập được… dừng với lỗi cookie» (đã kiểm: `LoiFileCookie` → `COOKIE_INVALID_OR_EXPIRED`, cầu dao
  ngưỡng 1; xét cấu trúc TRƯỚC vì file hỏng vẫn đếm ra LOGIN_INFO + SAPISID); đúng cấu trúc mà thiếu cookie đăng nhập → cảnh báo
  «KHÔNG đăng nhập… thiếu LOGIN_INFO / SAPISID… xuất lại cookies.txt». Trình duyệt và file có cookie đăng nhập: giữ câu cũ.
- Test: 6 mới (`tests/test_cookie_can_js.py`; 4 đỏ trên `97d36e0` đúng lý do, 2 khoá hành vi cũ); đột biến 7/7; vùng YouTube/tải
  + Giao diện 622/622; nhanh 2765 = 2763/2/0 (243 s); ruff, import sạch. Không đụng quét → không chạy chậm. Không gọi YouTube/
  Google. Venv: `TimClipPro_CookieFix`. Junit ngoài Git: `2026-10-15_cookie_status`.
### 2026-10-15 (chiều) — nghiệm thu PR #9 trên 8502 + pilot định dạng (feature/pc2/channel-sync-telemetry-performance)
- 8502 cũ (worktree ChannelSync) nhàn rỗi → dừng; nghiệm thu bằng DỮ LIỆU GIẢ trên chính app 8502 (yt-dlp giả + chặn
  mạng, FFmpeg thật, data thử): tải/nén/chờ/thiếu tổng byte/đổi client/ETA/Dừng/BI_CHAN đúng. Lỗi tìm được: thẻ
  `st.metric` cắt chữ ở 1280 px → `c399101` (giá trị HH:MM:SS/số, chữ phụ ở dòng nhỏ); test đỏ→xanh, đột biến 6/6.
- Cookie 8502: MỘT nguồn FILE, đúng cấu trúc nhưng KHÔNG có cookie đăng nhập → cần người dùng xuất lại.
- Pilot 1 video (người dùng duyệt, 17:11): tải 251 opus CHỈ TIẾNG qua visionos (5 request). Nguyên nhân mp4 CÓ HÌNH: một
  403 → `android` được nhớ cả lượt → sửa ở nhánh RIÊNG `fix/pc2/nho-client-do-lai`. Bằng chứng: `2026-10-15_pr9_nghiem_thu`,
  `2026-10-15_pilot_audio`.
### 2026-10-15 — tiến độ + hiệu suất đồng bộ kênh (nhánh feature/pc2/channel-sync-telemetry-performance)
- Đo lượt THẬT trên 8502 từ bên ngoài (psutil, chỉ đọc, 15 phút): tải 63%, nén FFmpeg 19%, khác 18%; cả lượt 88 video
  14:00–14:53 = 98,9 video/giờ (chu kỳ trung vị 30 s, p95 68 s); MỌI bản tải là mp4 CÓ HÌNH ~364 kbps → nghẽn MẠNG do
  định dạng; log cầu dao «Đã thử: android». Lượt tự dừng 14:53:39 do YouTube bot-check (BI_CHAN, đúng PR #8). Chưa đổi
  client/định dạng (cần pilot; yt-dlp không JS chỉ dùng visionos — `_video.py:143-145, 2976`).
- `tien_do_dong_bo.SoDongBo` + `ui_tien_do_dong_bo` + móc channel/process_runner/BoGhiYtdlp + app (vẽ lại 1 s); bỏ 1
  FFprobe/video (âm thanh giải mã giống hệt). Review độc lập: không P0/P1, đã sửa 2 P2 + 7 P3. Test: 24 mới, đột biến
  24/24, nhanh 2783 = 2781/2/0, chậm 19/19 (chạy sau khi lượt dừng). Benchmark: FFprobe 2→1/video (−4,4% chu kỳ tổng
  hợp ≈ 0,3% thật), CPU giao diện −18%. Bằng chứng ngoài Git `2026-10-15_sync_perf`; công cụ `pc2_test_tools\sync_perf`.
- Mục cũ hơn (2026-10-15 PR #8 xác thực đồng bộ kênh, chuyển quyền phát hành, review PR #6; 2026-10-14 trở về trước): `docs/ai/handoff/LICH_SU_PC2.md`.
