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
1. PR tiến độ + hiệu suất đồng bộ kênh (`feature/pc2/channel-sync-telemetry-performance`): người dùng xem kết quả lượt
   đã dừng trên 8502 → nghiệm thu màn mới trên 8502 (launcher Development riêng của worktree này, ngoài Git) → gộp FF → khi
   YouTube hết chặn IP: pilot 1 video công khai (người dùng duyệt) để telemetry ghi client + định dạng → quyết định sửa
   chọn client/định dạng (nghẽn: mp4 CÓ HÌNH qua client `android`). PR #8 đã gộp (`97d36e0`); bản vá Stable chờ duyệt.
2. Hỏi người dùng: bật ruleset GitHub (`release/github/`) — chưa bật.
3. Còn mở từ trước: C7 (người dùng tự lấy kết quả `launcher.py doctor` của Stable); `git user.name/email` riêng cho commit
   PC2 (người dùng quyết); nghiệm thu preview 8502 khi tiện.
4. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
### 2026-10-15 — tiến độ + hiệu suất đồng bộ kênh (nhánh feature/pc2/channel-sync-telemetry-performance)
- Đo lượt THẬT trên 8502 từ bên ngoài (psutil, chỉ đọc, 15 phút): tải 63%, nén FFmpeg 19%, khác 18%; cả lượt 88 video
  14:00–14:53 = 98,9 video/giờ (chu kỳ trung vị 30 s, p95 68 s); MỌI bản tải là mp4 CÓ HÌNH ~364 kbps → nghẽn MẠNG do
  định dạng; log cầu dao «Đã thử: android». Lượt tự dừng 14:53:39 do YouTube bot-check (BI_CHAN, đúng PR #8). Chưa đổi
  client/định dạng (cần pilot; yt-dlp không JS chỉ dùng visionos — `_video.py:143-145, 2976`).
- `tien_do_dong_bo.SoDongBo` + `ui_tien_do_dong_bo` + móc channel/process_runner/BoGhiYtdlp + app (vẽ lại 1 s); bỏ 1
  FFprobe/video (âm thanh giải mã giống hệt). Review độc lập: không P0/P1, đã sửa 2 P2 + 7 P3. Test: 24 mới, đột biến
  24/24, nhanh 2783 = 2781/2/0, chậm 19/19 (chạy sau khi lượt dừng). Benchmark: FFprobe 2→1/video (−4,4% chu kỳ tổng
  hợp ≈ 0,3% thật), CPU giao diện −18%. Bằng chứng ngoài Git `2026-10-15_sync_perf`; công cụ `pc2_test_tools\sync_perf`.
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
