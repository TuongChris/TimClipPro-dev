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
0. `fix/pc2/cookie-status-no-login` (`0ecd474` + handoff, LOCAL, CHƯA đẩy): người dùng duyệt đẩy → PR vào
   `integration/current` → mở thanh bên 8502 với file cookie không đăng nhập, thấy câu cảnh báo mới.
1. PR #8 `fix/pc2/youtube-channel-sync-auth` ĐÃ gộp FF (`97d36e0`) → pilot mạng có kiểm
   soát (Development, video công khai, chỉ khi người dùng cho phép; AUTH_SESSION còn UNVERIFIED) → bản vá theo
   `TimClipPro/docs/PHAT_HANH_HAI_MAY.md` (ký khoá PC2). Trên Stable sau cập nhật: xoá trống MỘT trong hai ô cookie; tạo
   kho riêng cho kênh vừa đồng bộ, không «Bổ sung» vào kho SML.
2. Hỏi người dùng: bật ruleset GitHub (`release/github/`) — chưa bật.
3. Còn mở từ trước: C7 (người dùng tự lấy kết quả `launcher.py doctor` của Stable); `git user.name/email` riêng cho commit
   PC2 (người dùng quyết); nghiệm thu preview 8502 khi tiện.
4. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
### 2026-10-15 — thanh bên «Trạng thái YouTube» hết nói «DÙNG cookie đăng nhập» với file không đăng nhập được (fix/pc2/cookie-status-no-login)
- Ca thật (Development 8502): file cookie đúng cấu trúc, KHÔNG có LOGIN_INFO/SAPISID, máy có Node + EJS → dòng trên «KHÔNG có
  cookie đăng nhập», dòng dưới vẫn «Khi quét: DÙNG cookie đăng nhập…» (kết quả đồng bộ thì đúng: `KHONG_CO_COOKIE_DANG_NHAP`).
- Sửa `0ecd474` (chỉ câu chữ, `scan_ui.dong_trang_thai_youtube`), nguồn FILE + JS sẵn sàng: file thiếu/không đọc được/sai cấu
  trúc → cảnh báo «KHÔNG đăng nhập được… dừng với lỗi cookie» (đã kiểm: `LoiFileCookie` → `COOKIE_INVALID_OR_EXPIRED`, cầu dao
  ngưỡng 1; xét cấu trúc TRƯỚC vì file hỏng vẫn đếm ra LOGIN_INFO + SAPISID); đúng cấu trúc mà thiếu cookie đăng nhập → cảnh báo
  «KHÔNG đăng nhập… thiếu LOGIN_INFO / SAPISID… xuất lại cookies.txt». Trình duyệt và file có cookie đăng nhập: giữ câu cũ.
- Test: 6 mới (`tests/test_cookie_can_js.py`; 4 đỏ trên `97d36e0` đúng lý do, 2 khoá hành vi cũ); đột biến 7/7; vùng YouTube/tải
  + Giao diện 622/622; nhanh 2765 = 2763/2/0 (243 s); ruff, import sạch. Không đụng quét → không chạy chậm. Không gọi YouTube/
  Google. Venv: `TimClipPro_CookieFix`. Junit ngoài Git: `2026-10-15_cookie_status`.
### 2026-10-15 — đồng bộ kênh YouTube: xác thực + cầu dao từng video + PARTIAL/BLOCKED + chặn trộn kho (fix/pc2/youtube-channel-sync-auth)
- Sự cố Stable 1.1.1: kênh nhiều video giới hạn tuổi → 3 lỗi «confirm your age» liên tiếp mở cầu dao AUTH_REQUIRED (ngưỡng
  3), 1.189 video chưa thử mà banner xanh «Đồng bộ xong»; cấu hình có CẢ file cookie lẫn trình duyệt; kho đang chọn ≠ thư
  mục vừa đồng bộ. Gốc: (1) tuổi/hội viên (lỗi TỪNG video) chung loại với «cần đăng nhập»; (2) đưa cả hai nguồn → yt-dlp
  gộp hai hũ rồi `save_cookies` GHI hũ gộp vào file cookie; (3) banner chỉ xét `da_huy`; (4) «Bổ sung» thư mục khác ghi đè
  thư mục của kho + trộn clip.
- Sửa (`ef50b3d`): `AGE_RESTRICTED`/`MEMBERS_ONLY` (ngưỡng hàng loạt 20; AUTH_REQUIRED 3; bot/429/cookie hỏng vẫn 1); MỘT
  nguồn cookie (có file → chỉ file) + cảnh báo; sync có `trang_thai` DAY_DU/MOT_PHAN/BI_CHAN/DA_HUY + số đếm; UI/CLI chỉ xanh
  khi DAY_DU; engine từ chối «Bổ sung» thư mục khác kho đã có vân tay TRƯỚC mọi ghi. Test: 23 mới (mã cũ 19 đỏ), đột biến 14/14.
- Vòng 2 (review): (a) kho CŨ `thu_muc` rỗng: «Bổ sung» chỉ nhận thư mục TRÙNG thư mục chung của clip trong vân tay
  (`Engine.thu_muc_nguon_tu_van_tay`; thư mục cha bị từ chối), chốt đọc vân tay rồi mới ghi sổ; nút «Tạo lại kho từ đầu»
  khoá tới khi tick xác nhận khi thư mục khác nguồn; (b) DA_XAC_MINH chỉ khi tải được nội dung `subscriber_only`/
  `premium_only` bằng cookie tài khoản (video công khai / 18+ KHÔNG đủ — yt-dlp có client web_embedded vượt cổng tuổi);
  miền cookie phải THUỘC youtube.com; youtube-doctor cùng luật; (c) sổ `video_han_che.json` trong thư mục kho: video giới
  hạn tuổi/hội viên đã gặp với CÙNG cách đăng nhập không thử lại (vẫn CHƯA tải, không vào archive), video chưa biết thử
  trước; đổi nguồn cookie/JS → tự thử lại; `thu_lai_han_che` (UI + `--thu-lai-han-che`) vẫn chịu trần 20.
- Test vòng 2: 16 đỏ trên `6018873` (đúng lý do) → mục tiêu 44/44 + liên quan 84/84; đột biến 18/18 (V18 sống lần đầu →
  siết test); nhanh 2759 = 2757/2/0; chậm 19/19 (363 s); ruff, import sạch. Không gọi YouTube/Google. Bằng chứng + mô tả PR ngoài Git: `2026-10-15_channel_sync`.
### 2026-10-15 — chuyển quyền phát hành HOÀN TẤT: ghi danh khoá PC2 + dry-run phát hành độc lập (PC1 tắt)
- PC1 ký uỷ quyền MỘT lần (`889ec35`, `release/trust/uy_quyen_PC2_d02702dd741c3e4f.json`, sha256 `5e4dd6a5…`, mã `a893c182…`,
  hết hạn 2026-11-14): PC2 kiểm `kiem-uy-quyen` ĐẠT + kiểm Ed25519 độc lập 17/17 (chữ ký PC1, tự ký PC2, đủ 32 byte, 6 ràng
  buộc). Người dùng chạy `.bat` ghi danh (đã thử trên sandbox bootstrap thật 25/25): ĐẠT 8/8 — Stable PC2 tin 2 khoá, khoá PC1
  giữ nguyên byte, sao lưu trust store gốc `a37dc9b6…` trong `launcher\trust_backups`, 1.1.1 vẫn ACTIVE + xác minh chữ ký/cây
  file, `doctor` không lỗi, `update status` y hệt, State (định danh, lịch sử, Outbox, kho vân tay) không đổi.
- `them-khoa-danh-sach` → `release/trusted_keys.json` 2 khoá (`bacd738`). Dry-run, PC1 tắt: build 1.1.1 từ `dc29b33` = gói
  `510f39a6…` trùng byte; người dùng ký bằng khoá PC2 → chữ ký `d02702dd741c3e4f` (Ed25519 độc lập 9/9; danh sách cũ 1 khoá
  từ chối); `kiem-sau-ky` 10/10; `feed` thử; kit thật 2 khoá; `tests/dien_tap_phat_hanh.py` 14/14 (1.1.0 do PC1 ký cài qua kit
  → runtime hỏng tự QUAY VỀ + cách ly → CapNhat lên 1.1.1 do PC2 ký → dữ liệu giữ byte, doctor 2 khoá, không `__pycache__`;
  1.1.2 khoá lạ bị bỏ qua). Test: nhanh 2712/2/0, chậm 19/19, thu hồi + rollback 74/74. Bản ký thử KHÔNG công bố.
- Mục cũ hơn (2026-10-15 review PR #6, 2026-10-14, 2026-10-13, 2026-10-09): `docs/ai/handoff/LICH_SU_PC2.md`.
