# Lịch sử handoff — PC2

Mục cũ chuyển từ `docs/ai/handoff/PC2.md` khi file đó chạm giới hạn 80 dòng hoặc «Nhật ký» quá 6 mục. Mới hơn ở trên.
Không ghi bí mật, link Sheet thật, dữ liệu khách hàng.

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
### 2026-10-15 — review độc lập PR #6 + khoá phát hành PC2 + yêu cầu ghi danh (nhánh feature/pc2/khoa-ky-pc2)
- Review PR #6 (`c81326b`) trên PC2, không dùng số của PC1: không P0/P1. Nhanh 2708/2/0, chậm 19/19, ruff sạch. Đột biến
  PC2 tự chọn 20 chốt an toàn: 19 bị bắt; M17 (bỏ so key_id gõ ở CLI `ky-uy-quyen`) sống → thêm test CLI (commit test
  trên nhánh này), nay bị bắt. Build lại 1.1.1 từ `dc29b33` chỉ bằng repo = gói `510f39a6…` trùng byte; `verify` +
  `kiem-sau-ky` bản 1.1.1 đã công bố 10/10. `release/trusted_keys.json` = trust store bộ kit đã cài PC2 (`a37dc9b6…`);
  launcher đã cài = blob `e49340d`, đọc trust store mỗi lần chạy. Ruleset GitHub hiện KHÔNG có (API công khai) — chưa bật.
- Khoá PC2: người dùng chạy `.bat` (công cụ = blob `c81326b`; venv từ `release/locks/launcher-lock.txt` cài offline có băm;
  thư mục khoá chỉ tài khoản người dùng + SYSTEM, tắt thừa kế; thử giả 24/24) → key_id `d02702dd741c3e4f`, Ed25519
  `ZtXkLr8QOo1sp1YAPpsqheIcUlGl36b3f58Kfnd5dq4=`. Yêu cầu `release/trust/yeu_cau_PC2_d02702dd741c3e4f.json` (nguyên byte,
  sha256 `4bc80809…`): tự ký đúng; khoá trùng đủ 32 byte khoá công khai do `tao-khoa` để lại; khoá đang tin
  `8aa5baa6c8f225f9`; trust store `a37dc9b6…`; bản 1.1.1; chỉ chứa BĂM định danh cài đặt.
- P3 để lại: D-21/P-5/P-6 trùng số với nhánh LOCAL `fix/pc2/loop-alias-p0` (đánh số lại khi tích hợp P0); mẫu `.bat` tạo
  khoá/ghi danh chưa nằm trong repo (PC2 có bản đã thử, ngoài Git).
- Tiếp: PC1 ký uỷ quyền MỘT lần (đối chiếu ĐỦ khoá công khai base64, không chỉ key_id) → PC2 `ghi-danh` (người dùng) →
  dry-run khoá PC2 thật, PC1 tắt → gộp. Bằng chứng ngoài Git trên PC2: `2026-10-15_release_authority`.
### 2026-10-14 — cookie đăng nhập YouTube chạy bằng Node.js + yt-dlp-ejs (nhánh fix/pc2/youtube-cookie-js-fallback — lúc ghi CHƯA đẩy; đã đẩy `8bd69a7` 14/10, gộp vào Stable 1.1.1 `dc29b33`)
- Bối cảnh: Stable 1.1.0 + `ytdlp_cookies_browser = firefox` → MỌI video «The page needs to be reloaded», cầu dao khuyên sai «có
  thể yt-dlp cần cập nhật». Bản đầu (`6ebdc72`, `ea12a28`) chỉ lùi không-cookie + nhớ 30 phút — người dùng KHÔNG muốn (YouTube từng
  đòi xác minh khi không cookie): mục tiêu là DÙNG ĐƯỢC phiên đăng nhập, minh bạch khi không dùng được.
- Cơ chế (yt-dlp 2026.08.19, đo NGOẠI TUYẾN trên PC2 — `C:\Dev\pc2_test_tools\cookie_js\kiem_node_ejs.py`): có cookie → chỉ client
  phải giải thử thách JS (`web_embedded, tv_downgraded, web`); giải cần Node.js ≥ 22 (yt-dlp chỉ tự bật deno → `js_runtimes`) +
  gói `yt-dlp-ejs` ĐÚNG bản yt-dlp ghim (0.8.0, khớp băm; script đi kèm yt-dlp thiếu thư viện cho node). PC2: Node 24.21.0 có sẵn;
  Stable thiếu gói EJS. `web_embedded`/`tv_downgraded` không đòi PO token cho HTTPS (audio-only); `tv_downgraded` lỗi phía YouTube.
- Làm (`4795b18`, trên `3e98131`; mục này ở commit sau): `ytdlp_chung.kha_nang_js` (node trên PATH — bỏ thư mục hiện hành — + phiên bản + EJS
  đúng bản/băm; hỏi lại MỖI lượt, không nhớ lỗi cũ; bỏ `NhoBoCookie`); có cookie → `js_runtimes` node ở MỌI đường gọi, không
  `remote_components`; máy chưa sẵn sàng → quét/tải KHÔNG cookie, không gửi request đăng nhập, mọi kết quả ghi «KHÔNG đăng nhập»;
  đường khác ném `CookieCanJs` trước request. Loại lỗi mới `JS_CHALLENGE_ERROR` (ngưỡng 2) + `PLAYER_CLIENT_ERROR` (ngưỡng 5); bot,
  cần đăng nhập, player client, bộ giải hỏng: KHÔNG tự bỏ đăng nhập. Thanh bên + youtube-doctor nói cookie DÙNG được hay không.
  Lock + `yt-dlp-ejs==0.8.0` (sinh bằng `release_tool.py lock` từ môi trường mới: khác lock cũ ĐÚNG một dòng).
- Môi trường RIÊNG: `C:\Dev\TimClipPro_CookieFix\TimClipPro\.venv` (54 gói lock + yt-dlp-ejs + pytest/ruff, `--require-hashes`,
  không mạng); wheel `C:\Dev\wheelhouse_pc2_ejs` (PyPI, 53 443 byte, sha256 `79300e5f…bdb4`). Venv chung của clone KHÔNG đổi.
- Test (chặn mạng, cp1252): cookie/Node/EJS 57 (venv thiếu EJS: 56 + 1 bỏ qua đúng lý do), đột biến 21/21, YouTube + Watch +
  Marathon 675/675, nhanh 2582 = 2580/2/0, chậm tải phần đầu thật (Range) 5/5. Trước/sau, lô 6 video (`do_truoc_sau.py`): 1.1.0
  0/6; bản trước 6/6 nhưng 0 lượt đăng nhập; bản mới 6/6, 12/12 lượt CÓ đăng nhập; thiếu EJS 6/6, 0 request cookie, ghi rõ.
  Bằng chứng: `C:\Dev\pc2_test_runs\2026-10-14_cookie_node_ejs`.
- Pilot THẬT (người dùng duyệt; 14/10 13:07; video công khai `dSfZMQXvlfY`, cookie Firefox, Development, đúng MỘT lượt; công
  cụ ngoài Git `C:\Dev\pc2_test_tools\cookie_js\pilot_cookie_that.py` bản 2, tự kiểm ngoại tuyến 37/37): ĐẠT — trang xem
  `LOGGED_IN=true`, cookie xác thực còn nguyên, 0 cảnh báo; node `--permission` chạy thật + EJS 0.8.0 (python package); 60 s
  đầu: `-request_size` trước `-i`, `-t 60`, HTTP 206, đọc 10% luồng, 0,46 s; âm thanh thật 60,014 s, giải mã 0 lỗi; rò rỉ 0.
- Tiếp: duyệt đẩy + PR → PC1: lock có băm (thêm wheel yt-dlp-ejs) → runtime MỚI (lock đổi → runtime_id đổi; CapNhat.bat dựng venv
  mới, tải gói từ PyPI) → build/ký 1.1.1. Máy dùng cookie cần Node.js ≥ 22 trên PATH. Tạm trên 1.1.0: xoá ô cookie.
### 2026-10-13 — video dài: giới hạn quét + tiến độ thật + Dừng giết ffmpeg + tải phần đầu nhanh (marathon — lúc ghi CHƯA đẩy; đã đẩy `a650154` 13/10, gộp vào Stable 1.1.0 `ec1ff71`)
- Bối cảnh (Stable, video 65 giờ): «0/5 — 1%» hàng chục phút — ffmpeg (yt-dlp FFmpegFD) tải 3 giờ đầu ~17 KB/s, không phát
  tiến độ; Dừng không giết ffmpeg; mã cũ không thấy đủ bằng chứng thì tải TRỌN 65 giờ.
- Làm (worktree `C:\Dev\TimClipPro_Marathon`, từ `7a76e71`, KHÔNG P0/Sheets): video dài theo LÔ (`engine.GHVD_*`, >6 giờ →
  3/6 giờ đầu, không tự tải trọn, kiểm gói audio CUỐI — không tin `format.duration`, đệm cụt tải lại 1 lần); `giam_sat_tai`
  (`-progress`; Dừng giết ffmpeg; 180 s không thêm byte → «Mạng đứng»); `tien_do_quet`/`ui_tien_do_quet` (số đo thật, nhịp ≠
  tiến triển, ETA từ tốc độ đo); `scan_jobs` nhận lại lô khi tải lại trang; «Mã tab» toàn chuỗi. Watch/CLI giữ hành vi cũ.
- `13f9511` tải phần đầu CHẬM (pilot thật OPgD5wl0fAY 66 giờ: 2,03×, 3 giờ đầu mất 1 giờ 30): ffmpeg xin MỘT `Range: bytes=0-`,
  googlevideo nhả theo nhịp phát; yt-dlp tải thường xin khối 10 MiB. Sửa: ffmpeg `-request_size 10485760` (tuỳ chọn ĐẦU VÀO;
  ffmpeg cũ thiếu → cách cũ + ghi rõ). A/B thật (người dùng duyệt): một yêu cầu mở 0,7× → khối 10 MiB 1280×, 2400,01 s đủ.
- Test (chặn mạng, cp1252): nhanh 2508 = 2506/2/0, chậm 18/18 (ở `53c8f3a`); `13f9511`: đỏ 7/8 → xanh 12/12 (Range thật, máy
  chủ hãm kiểu googlevideo), hồi quy liên quan 482/482. Development 8502 (`ChayTimClipPro_Dev_Marathon.bat`, ngoài Git), kho
  SML 779 clip (vân tay trong DevState). Bằng chứng: `C:\Dev\pc2_test_runs\2026-10-13_marathon*`, `…_tai_nhanh`.
- Nghiệm thu thật 16:02–16:05 (duyệt; Development 8502, SML 779): tải 3 giờ 9,0 s, âm thanh đủ 10800,01 s, cắt 15 s, khớp 146 s;
  tổng 3 phút 03; 5 kết quả = lượt trước, mốc lệch ≤ 0,094 s; phạm vi «Một phần 0–3 giờ»; outbox 0. Tiếp: duyệt đẩy + PR.
### 2026-10-09 — test bảng mã cp1252 của health_check (nhánh fix/pc2/windows-health-encoding)
- Làm: PC2 (cp1252) hỏng `test_chan_mang_truoc_khi_import`: test gọi thẳng `chan_mang()` rồi print tiếng Việt, bỏ
  `_utf8_dau_ra()` của `main()` — lỗi của test; production đúng (launcher ép UTF-8; `main` và `cli` đổi stdout). Chỉ
  sửa `tests/test_health_check.py`: test cũ chạy đúng thứ tự `main()`, ép cp1252/utf-8; +3 test hồi quy × 2 bảng mã.
- Commit: `da66f0e` (trên `c1f19d8`); commit chứa chính mục này: `b627af0` (PR #1, gộp 10/10).
- Test (clone tạm, chặn mạng, cp1252): health_check 12/12; đột biến `_utf8_dau_ra` no-op → 2 đỏ, launcher bỏ biến
  UTF-8 → 1 đỏ; ruff sạch; nhanh 2460 = 2458 đạt / 2 bỏ qua (symlink cần quyền; file đang mở) / 0 hỏng (junit ngoài
  Git: `C:\Dev\pc2_test_runs\2026-10-09_fix_encoding`); chậm 14/14 ở `c1f19d8` — chỉ đổi test nên không chạy lại.
- Còn mở / rủi ro: chưa đẩy được (khoá CHỈ ĐỌC). PC2 chưa đặt git `user.name`/`user.email` (commit tạm dùng tên PC1).
- Tiếp theo: người dùng duyệt giai đoạn 2 → đẩy nhánh + PR; PC1 review, merge; PC1 xác minh Stable đã cài trên PC2.
### 2026-10-09 — Thiết lập giai đoạn 1 (PC2 ghi ở «Tiếp theo» cũ; PC1 chuyển nguyên ý xuống đây 10/10)
- Clone CHỈ ĐỌC `C:\Dev\Tool_Quet` (`git remote -v` chỉ `private`; `push --dry-run` bị từ chối «read only»);
  `CLAUDE.local.md` + `.claude/settings.local.json`; ngữ cảnh nạp đủ 4 file; venv `TimClipPro\.venv` từ Python 3.12.10
  gốc; FFmpeg 9.0.1 có trên PATH (winget). Người dùng báo Stable 1.0.0 đã cài và chạy.
