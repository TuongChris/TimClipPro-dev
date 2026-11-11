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
1. Đồng bộ + quét song song (D-29): PR #20 GỘP (`dd111e8`), DEV 8502 cập nhật 27/10 13:04 (sao lưu `data_20261027_130421`).
   Chờ người dùng thử thật một tab đồng bộ + một tab quét (AppTest không chạy nhịp tự làm mới của fragment). P3 còn mở:
   giao diện không biết `cli.py kenh` ở tiến trình KHÁC đang đồng bộ cùng thư mục. Kho CoryxKenshin dựng xong 28/10 00:29
   (CLI `--ncores 2`, 1745/1745) — dựng bằng giao diện với 8 worker từng hết RAM. Máy mới: `docs/ai/TIEP_TUC_TREN_MAY_MOI.md`.
2. Dựng kho theo RAM + bỏ clip > 2 giờ (D-31): PR #23 GỘP (`73c5734`), DEV 8502 cập nhật 06/11 20:16 (sao lưu `data_20261106_201648`).
   Chờ người dùng dựng Kho_Joe_Games (CHƯA có vân tay, thư mục `E:\Kho_Tool_Quet\Kho_Joe_Games`) và đồng bộ thật một kênh để kiểm
   quy tắc 2 giờ (chưa thử YouTube thật).
3. Audit toàn repo 06/11: số 1–20 xong (17: giữ `.gs` và `session.log` vì có lý do; Docker đã xoá 08/11 theo người dùng —
   `release_tool.py` vẫn loại tên Dockerfile để build lại bản cũ trùng byte).
   Còn 8 mục nhỏ: báo cáo trong phiên 06/11 (lịch sử chat). PC1 phải cài lại hook. Tạm dừng + lưu giữa chừng khi dựng kho CHƯA làm.
4. Người dùng: nghiệm thu DEV đợt 2 theo `C:\Dev\pc2_test_runs\2026-10-26_audit_p3\NGHIEM_THU_DEV_DOT2.md` (~15 phút).
5. Người dùng quyết: P-6 (3 phương án, `…\2026-10-26_audit_p3\P6_PHUONG_AN.md`); P-7 (`P7_THIET_KE.md` cùng thư mục, công
   cụ `C:\Dev\pc2_test_tools\p7_lich_su_bong`, CHƯA chạy dữ liệu thật — chỉ chạy CHỈ ĐỌC khi duyệt); B-13, F-16; 3 ghép
   tuỳ chọn của P0 (`ket_qua_panel.json`, mục 25/10 «P0 bóng»); Stable 1.1.3 có phát hành sau P3 hay không.
6. PC1: review `…\2026-10-26_audit_p3\GOI_REVIEW_PC1.md` (PR #15–#17 đã vào `integration/current` chưa có PC1 review, mã đang
   chạy dữ liệu THẬT trên DEV); chạy bộ đột biến outbox; quyết đề xuất E-1 (`.claude/settings.json` chặn đọc khoá Google, 2
   test xfail strict); cập nhật `CURRENT_STATE.md` theo mục 26/10.
7. Còn mở từ trước: đồng bộ tiếp kênh Joe → vân tay «Kho Joe» (tab «Kho clip gốc», không tạo kho mới); hồ sơ đích Sheets +
   binding khoá NGOÀI State Stable cho DEV; ruleset GitHub (`release/github/`, chưa bật); C7; nghiệm thu preview 8502.
8. Kho Joe VODs (D-34): 150 video mới nhất tải xong 07/11 (197 file, 727 giờ, 21 GB, 0 hỏng). DEV lên `fddcf39` 15:26 (sao lưu
   `data_20261107_152616`). Người dùng muốn để đồng bộ/dựng về ĐÊM. Chưa tạo kho: RAM trống 6,2 GB, cần 15–20 GB. Rồi «Tạo lại từ đầu» → quét thử.
9. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
### 2026-11-11 — cắt / chỉnh âm / ghép video trong máy (D-46, nhánh feature/pc2/video-trong-may)
- Tab «🛠️ Video trong máy» (`video_trong_may.py`) + tab Ghép nhận đường dẫn file; file gốc không bao giờ bị sửa (so băm).
- Thử thật offline 2 video 1080p 90 s (30 + 60 hình/giây): cắt+âm 10 s, chỉ âm 4,8 s, ghép 3 phần 15,8 s; gốc không đổi. Nhanh 3688 = 3684/4/0, chậm 24/24. Gộp `878a7ce`, DEV 16:25.
- Audit 11/11 chiều (nhánh fix/pc2/audit-1111b): bản nén khớp đặt theo đường dẫn đầy đủ + cỡ + giờ sửa (2 file cùng tên khác thư mục từng lẫn nhau); xoá bản chỉnh âm cũ của lượt hỏng; chỉnh âm MP3/FLAC/WAV/MPG giữ bộ nén hợp vỏ. Nhanh 3694 = 3690/4/0, chậm 24/24.
### 2026-11-11 — thumbnail cả kênh (D-45, nhánh feature/pc2/thumbnail-kenh)
- Tab «🖼️ Tải thumbnail» thêm link kênh + số mới nhất → `tai_kenh(thumbnail=True)`; ảnh «[mã].jpg» đã có thì bỏ qua.
- Test giả (AppTest + bỏ qua phần đã có); chưa thử kênh YouTube thật (người dùng thử trên DEV). Nhanh 3675 = 3671/4/0. Gộp `bddfa7c`, DEV 14:32.
- Người dùng thấy chậm (đo 8 s/ảnh, kênh Joe 1.289 video ~3 giờ) → tải thẳng ảnh i.ytimg.com (nhánh feature/pc2/thumbnail-nhanh): thử thật 20 ảnh 3,4 s, 1280×720, trùng tên bản cũ. Nhanh 3677 = 3673/4/0. Gộp `6d0a4b7`, DEV 15:23.
### 2026-11-11 — Twitch 1440p (D-44, nhánh feature/pc2/twitch-1440p)
- Tab Tải đã tải được Twitch (720p60, thật 5,2 GB). 1440p khoá: AUTHZ_GEO + AUTHZ_NOT_LOGGED_IN → mục «🟣 Twitch»: file proxy
  (Windscribe Free, Proxy Gateway, Split Tunneling Inclusive rỗng) + cookie twitch.tv; chỉ bước trích qua proxy, tải thẳng.
- Thử thật bằng mã mới: 2560×1440p60, 12,8 GB, tải ~8 phút + chỉnh âm lượng 13 phút; máy vẫn ra VN. File thử `D:\pc2_thu_twitch`.
- Review 11/11 sửa 2 (file lạ làm đứt lượt, link kênh lặng lẽ 720p). Gộp `edeb2e2`, DEV 11/11 12:48 (sao lưu `data_20261111_124831`).
- Audit 11/11 (nhánh fix/pc2/audit-1111): Dừng lúc chỉnh âm lượng giữ video đã tải; `ma_link` nhận VOD Twitch «v<số>» là đã có/trùng (cắt/ghép bấm lại không tải lại). Gộp `8c1e017`, DEV 13:17.
### 2026-11-10 — âm lượng về mức YouTube (D-43, nhánh feature/pc2/am-luong-youtube)
- Video Joe tải về -28,5 LUFS vì YouTube phát bằng «Âm lượng ổn định». Ô tick (sẵn) ở tab Tải + Ghép → `am_luong.chuan_hoa`.
- Thử 3 phút Joe thật: -28,0 → -14,4 LUFS, đỉnh -0,8 dB, hình trùng MD5, 9,8 s. Ghép: mốc vẫn khớp tiếng thật. Gộp `4742c6a`, DEV 10/11 21:30.
### 2026-11-10 — audit phần video mới (nhánh fix/pc2/audit-1011)
- 11 sửa kèm test đỏ: file đáp án `.moc.csv` bị ghi đè, cắt từ bản cũ khác chất lượng, tải song song mất định dạng thiếu dung
  lượng + gọi YouTube gấp đôi (nay `dashy,duplicate` ghép cặp theo URL), ffprobe hỏng mất kết quả, đoạn cắt lỗi đổi tên `.loi`…
- Thử thật (video Marvin): chọn `137-dashy` + `140-dashy-11` (video nhiều ngôn ngữ tiếng đánh số lại mã), tải 23,4 s, Dừng sạch. Gộp `07ae606`, DEV 10/11 08:52.
### 2026-11-09 — tải theo link chỉ lấy một đoạn (D-42, nhánh feature/pc2/cat-doan-video)
- Ô «Từ»/«Đến» ở tab «⬇️ Tải video gốc»: tải trọn rồi cắt nén lại, đúng từng khung hình; xoá video trọn khi đoạn ra đúng độ dài.
- Thử file thật 1080p: đoạn 30 s cắt 4,7 s, 899 khung = lý thuyết, tiếng đầu đoạn lệch 0 ms. Gộp `473ac5d`, DEV 23:44. Chưa thử YouTube thật.
- Mục cũ hơn (2026-11-09 tải 4 kết nối D-40; 2026-11-09 ghép video gốc D-39/D-41 + chương QuickTime; 2026-11-09 tiêu đề kênh D-38 + audit 09/11; 2026-11-08 tải video gốc D-37 + review/audit 08/11; 2026-11-07 Codex bước 2 audit 14 + 18; 2026-11-07 Codex review PR #27–#29 D-36; 2026-11-07 đồng bộ nén song song D-35; 2026-11-07 audit số 15, 19, 20; 2026-11-07 kho video dài D-34; 2026-11-07 dựng kho nhường ổ cứng D-33; 2026-11-06 audit số 7–13; 2026-11-06 audit số 1–6; 2026-11-06 gộp D-31; 2026-11-06 dựng kho theo RAM D-31; 2026-11-06 phân tích tải dựng kho; 2026-11-02 ngày đăng D-30 + máy mới; 2026-10-27 đồng bộ song song D-29; 2026-10-26 audit độc lập 25/10; 2026-10-26 13 lỗi YouTube; 2026-10-25 P0 «bóng» D-27 + P0-1; 2026-10-25 link «Đoạn vi phạm» dạng watch; 2026-10-15 DEV-ONLY D-26, tích hợp PR #9 + gom #10/#11, thanh bên cookie PR #11, nghiệm thu PR #9 + pilot, tiến độ + hiệu suất đồng bộ kênh, PR #8, chuyển quyền phát hành, review PR #6; 2026-10-14 trở về trước): `docs/ai/handoff/LICH_SU_PC2.md`.
