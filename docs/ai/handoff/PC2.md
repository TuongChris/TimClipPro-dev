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
### 2026-11-09 — tải theo link 4 kết nối song song (D-40, nhánh feature/pc2/tai-song-song)
- Người dùng thấy ghép chậm: đo thật một kết nối 0,78–25 MB/s; 4 kết nối ~78 MB/s; tool thật tải 346 MB trong 22,5 s. Gộp `5a2e79a`, DEV 09/11 21:24 (sao lưu `data_20261109_212411`).
- Lùi một kết nối khi thiếu định dạng; Dừng giữa chừng để lại .part đang mở → sửa (test đỏ + thử thật). Bằng chứng `C:\Dev\pc2_test_runs\2026-11-09_tai_song_song`.
### 2026-11-09 — tab «🎞️ Ghép video gốc» (D-39, nhánh feature/pc2/ghep-video-goc)
- Tải H.264 ≤ 1080p + AAC rồi nối `-c copy` theo thứ tự link, lệch thông số thì dừng + giữ file; `<tên>.moc.csv` + mốc chương.
- Test: video tổng hợp FFmpeg thật, tiếng bíp riêng mỗi phần — mốc CSV khớp tiếng thật ±0,05 s. Gộp `ee8e6cd`, DEV 09/11 20:36 (sao lưu `data_20261109_203615`); chưa thử YouTube thật.
### 2026-11-09 — tab «📝 Tiêu đề kênh» (D-38, nhánh feature/pc2/tieu-de-kenh)
- Một lượt liệt kê nhanh tab Videos → bảng STT/Tiêu đề/Link/Thời lượng, tải CSV (BOM, chặn công thức) và TXT. `tai_video_goc.tieu_de_kenh`.
- Test: 8 test mới (list_channel giả, AppTest); số nhanh/chậm ở PR. Chưa thử kênh YouTube thật.
- Audit 09/11 (4 agent, nhánh fix/pc2/audit-0911): 13 sửa (danh sách kênh cụt do 429 coi là đủ, ô xoá kho còn tick, watchlist hỏng → mã 0, hook UTF-16, nút Sheets nhầm việc…); hook mới ĐÃ cài PC2.
### 2026-11-08 — tải video gốc theo link (D-37, nhánh feature/pc2/tai-video-goc)
- Tab «⬇️ Tải video gốc»: nhiều link, ô thư mục + «Chọn…», hình + tiếng cao nhất (`bv*+ba/b`, MP4/MKV). Module `tai_video_goc.py`.
- Test: nhanh và chậm ở PR #32, 17 test mới (yt-dlp giả, AppTest). Gộp `1017142`, DEV cập nhật 08/11 21:08. Người dùng tải thật trên DEV: chạy tốt.
- Bổ sung (nhánh feature/pc2/tai-video-them): ô «Chất lượng tối đa», tab «🖼️ Tải thumbnail» (JPG), tab «📺 Tải cả kênh» (số
  video mới nhất, bỏ qua video đã có). Cùng ngày: bỏ Docker `fe397a4`, sửa test chập chờn `80aa554`. PR #33 `ec2091d`, DEV 22:37; người dùng thử thật: ổn.
- Review + audit 08/11 (nhánh fix/pc2/audit-0811): 13 sửa kèm test đỏ, bỏ SheetsExporter.append −156 dòng; bác 1 (immutable
  SQLite). 09/11 người dùng chọn: `don_ban_cu` gọi sau ACTIVE, giữ 2 bản + runtime chúng dùng (nhánh fix/pc2/don-ban-cu;
  review: dọn cả runtime xoá dở, runtime đang chạy để lần sau; nhanh 3539/4/0, chậm 24/24). Tới Stable khi phát hành.
### 2026-11-07 — Codex bước 2: audit số 14 và 18 (nhánh fix/pc2/audit-14-updater)
- 14: 10 kiểm tra an toàn của updater có test mới, mỗi test đỏ khi xoá kiểm tra (1 claim sai). Sửa F1–F3: tag trước kênh; health chết không kết quả là
  tạm thời, cách ly ở lần 3; launcher không mở khi nhật ký đang kích hoạt. Updater chỉ tới máy đã cài khi bootstrap lại.
- 18: xoá code chết, gộp khoá byte 0 vào `khoa.py`, −144 dòng. 17: không xoá gì. Test khoá chập chờn (2–4/30) nay 30/30.
- Test @ `b050ee5`: nhanh 3521 = 3517/4/0, chậm 24/24, ruff sạch.
### 2026-11-07 — Codex review PR #27–#29 (D-36, nhánh fix/pc2/codex-review-0711)
- Làm: Codex chạy chỉ-nhận-văn-bản, 6 lượt, 12 phát hiện: 10 đã sửa kèm test đỏ, 1 để lại, 1 bị bác. Lỗi lớn nhất: bổ sung có thể làm tràn mã clip trong kho mà không báo.
- Lưu ý: video đang đồng bộ chạy bản cũ; DEV chỉ nhận các bản sửa này khi cập nhật. Audit 14, 17, 18 chưa giao Codex.
- Test: số ở PR. Không chạy Codex với công cụ trên máy (`-s read-only` vẫn đọc được C: và D:).
- Mục cũ hơn (2026-11-07 đồng bộ nén song song D-35; 2026-11-07 audit số 15, 19, 20; 2026-11-07 kho video dài D-34; 2026-11-07 dựng kho nhường ổ cứng D-33; 2026-11-06 audit số 7–13; 2026-11-06 audit số 1–6; 2026-11-06 gộp D-31; 2026-11-06 dựng kho theo RAM D-31; 2026-11-06 phân tích tải dựng kho; 2026-11-02 ngày đăng D-30 + máy mới; 2026-10-27 đồng bộ song song D-29; 2026-10-26 audit độc lập 25/10; 2026-10-26 13 lỗi YouTube; 2026-10-25 P0 «bóng» D-27 + P0-1; 2026-10-25 link «Đoạn vi phạm» dạng watch; 2026-10-15 DEV-ONLY D-26, tích hợp PR #9 + gom #10/#11, thanh bên cookie PR #11, nghiệm thu PR #9 + pilot, tiến độ + hiệu suất đồng bộ kênh, PR #8, chuyển quyền phát hành, review PR #6; 2026-10-14 trở về trước): `docs/ai/handoff/LICH_SU_PC2.md`.
