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
- GitHub: Deploy Key «PC2 PC_Office read-only» (tên cũ; quyền GHI cả repo) cho git; `gh`: CHƯA cài / chưa đăng nhập
  (15/10). Hook `pre-push` dùng chung `release/git-hooks/pre-push`: ĐÃ cài 15/10 (thử `--dry-run`: chặn nhánh lạ + tag,
  cho `fix/pc2/*`, `feature/pc2/*`).
- Khoá ký phát hành PC2: ĐÃ TẠO 15/10, key_id `d02702dd741c3e4f`, ở `C:\TimClipPro_KhoaPhatHanh` (ngoài repo; chỉ tài khoản
  người dùng + SYSTEM; Claude không đọc), mật khẩu người dùng gõ; CHƯA ghi danh — chờ uỷ quyền PC1 ký MỘT lần
  (`TimClipPro/docs/UY_QUYEN_KHOA.md`).
- Dữ liệu: PC2 tự xây; KHÔNG chép dữ liệu từ PC1. Test chỉ dùng dữ liệu synthetic/thư mục tạm.

## Tiếp theo
1. Thiết lập phát hành độc lập (prompt người dùng gửi; PC1 chuẩn bị 14/10). XONG 15/10: review PR #6 trên PC2, hook mới,
   khoá PC2 + yêu cầu ghi danh (nhánh `feature/pc2/khoa-ky-pc2`). CÒN: `gh auth login --web` (người dùng) → PR nháp →
   CHỜ PC1 ký uỷ quyền (`feature/pc1/uy-quyen-pc2`) → `GHI_DANH_KHOA_PC2.bat` → `release_tool.py them-khoa-danh-sach` →
   dry-run phát hành, PC1 tắt (build 1.1.1 từ repo = `510f39a6…`, ký khoá PC2, `kiem-sau-ky`, `feed`,
   `tests/dien_tap_phat_hanh.py`; bản ký thử KHÔNG công bố) → gộp fast-forward.
2. Hỏi người dùng: bật ruleset GitHub (`release/github/`).
3. Còn mở từ trước: C7 (người dùng tự lấy kết quả `launcher.py doctor` của Stable); `git user.name/email` riêng cho commit
   PC2 (người dùng quyết); nghiệm thu preview 8502 khi tiện.
4. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
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
### 2026-10-14 — cookie đăng nhập YouTube chạy bằng Node.js + yt-dlp-ejs (nhánh fix/pc2/youtube-cookie-js-fallback, CHƯA đẩy)
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
- Mục cũ hơn (2026-10-13, 2026-10-09): `docs/ai/handoff/LICH_SU_PC2.md`.
