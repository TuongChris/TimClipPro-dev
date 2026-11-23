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
0n. 23/11: tra kho nhanh (`fix/pc2/tra-kho-nhanh`, ĐÃ ĐẨY, CHƯA gộp/DEV) — chờ duyệt gộp + DEV. Đo thật 4 khúc video 1
    × kho Mr Ballen, 3 worker: 401 → 45 s, 800 dòng kết quả TRÙNG (`C:\Dev\pc2_test_runs\2026-11-23_tien_do_khop`).
0m. 23/11: «🎧 Tạo file kiểm claim» (D-64, `feature/pc2/file-kiem-claim`) — GỘP 23/11 (người dùng duyệt); người dùng thử tải 1 file lên kênh phụ.
0l. 23/11: sửa 14 mục `/ponytail-review` của D-63 (`fix/pc2/review-d63`): nhanh 4362 = 4358/4/0, 9 test mới đỏ→xanh — GỘP 23/11 (người dùng duyệt).
0k. 23/11: tiến độ so khớp trung thực (`fix/pc2/tien-do-so-khop`) — GỘP `34c5403` (người dùng duyệt), DEV 19:23
    (sao lưu `data_20261123_192339`), health ok, mở lại bằng icon. Người dùng: quét thử, xem dòng «tra kho xong».
0j. 23/11: giao diện D-63 (menu 5 nhóm + mở nhanh + bớt thao tác tay + gọn chữ, `feature/pc2/giao-dien-tong2`): nhanh 4356 = 4352/4/0 trên 8a9045d, chậm 25/25 trên bc16ef9 — GỘP integration, DEV cập nhật — người dùng thử.
0i. 23/11: khoá JSON chậm 0,1–1,2 s mỗi lượt vẽ (nhánh `fix/pc2/khoa-lay-hut`) — GỘP `9203bfd` (người dùng duyệt 23/11), DEV 11:10 (sao lưu `data_20261123_111036`), health ok. Người dùng: thấy thanh bên/tab Lịch sử còn khựng khi máy bận thì báo.
0h. 23/11: sửa test chập chờn `test_dung_giua_chung` (nhánh `fix/pc2/test-dung-giua-chung`, chỉ test) — GỘP vào integration/current 23/11 (người dùng duyệt); mã chạy không đổi → DEV không cần cập nhật.
0g. 20/11: 3 việc hoãn review Codex (`fix/pc2/ba-viec-hoan`): nhanh 4327 = 4322/4/1 (test đo thời gian chỉ hỏng khi cả
    bộ chạy, riêng 3/3 đạt), chậm 25/25 — GỘP `7a9561e`, DEV 10:49 (sao lưu `data_20261120_104911`) — người dùng thử: ĐẠT.
0f. 20/11: review Codex 20/11 (D-62) — 14 mục sửa GỘP `6770c40`, DEV 10:12 (sao lưu `data_20261120_101200`) — người
    dùng thử trên DEV 20/11: ĐẠT.
0a–0e. 17–20/11: bỏ các đoạn D-59, giữ tab, Apps Script «Xuất hàng», chụp ảnh D-60, ghép chỉ audio D-61 — GỘP + DEV, người dùng thử: ĐẠT.
0. 16/11: YouTube Data API (D-51) + D-52…D-58 trên `feature/pc2/tong-hop-1611` (nhanh 4265 = 4261/4/0, chậm 25/25) — GỘP `0390784`, DEV 8502 cập nhật 16/11 13:05 (sao lưu `data_20261116_130446`), khoá DEV nhận «CO_KHOA». Người dùng thử: thanh bên «🔐 Kết nối YouTube» báo có khoá, quét 1 video, tab «📊 Thống kê» / «🔎 Tìm video nghi vấn», nút kiểm video còn/gỡ ở «📜 Lịch sử», «📝 Tiêu đề kênh», Dừng khi dựng kho. Worktree đã dọn 16/11 (24 cái tạm + cũ, đều đã gộp): còn `Tool_Quet`, `TimClipPro_VanHanh` (DEV), `TimClipPro_CookieFix` (venv test chuẩn).
1. Đồng bộ + quét song song (D-29): PR #20 GỘP (`dd111e8`), DEV 8502 cập nhật 27/10 13:04 (sao lưu `data_20261027_130421`).
   Chờ người dùng thử thật một tab đồng bộ + một tab quét (AppTest không chạy nhịp tự làm mới của fragment).
   Kho CoryxKenshin dựng xong 28/10 00:29
   (CLI `--ncores 2`, 1745/1745) — dựng bằng giao diện với 8 worker từng hết RAM. Máy mới: `docs/ai/TIEP_TUC_TREN_MAY_MOI.md`.
2. Dựng kho theo RAM + bỏ clip > 2 giờ (D-31): PR #23 GỘP (`73c5734`), DEV 8502 cập nhật 06/11 20:16 (sao lưu `data_20261106_201648`).
   Chờ người dùng dựng Kho_Joe_Games (CHƯA có vân tay, thư mục `E:\Kho_Tool_Quet\Kho_Joe_Games`) và đồng bộ thật một kênh để kiểm
   quy tắc 2 giờ (chưa thử YouTube thật).
3. Audit toàn repo 06/11: số 1–20 xong (17: giữ `.gs` và `session.log` vì có lý do; Docker đã xoá 08/11 theo người dùng —
   `release_tool.py` vẫn loại tên Dockerfile để build lại bản cũ trùng byte).
   8 mục nhỏ 06/11 (tra lại 16/11): 2 đã sửa (`1c5c938`); 6 cần thiết kế/quyết — tràn bảng audfprint 2^20 không cảnh báo, bootstrap --repo máy mới, xoá bộ máy phụ ~777 dòng / nhánh V1 ~140 dòng, tách `_build_database_da_khoa`; 5 ô «Đoạn vi phạm» người dùng giữ như cũ. Dừng dựng kho giữ phần đã xong: D-52.
   Audit 16/11 (`/ponytail-audit`, 20 mục + 6 mã thừa): ĐÃ SỬA HẾT, gộp `3101580`, DEV 16/11 03:06 (sao lưu `data_20261116_030552`). PC1 cài lại hook (installation_id 32 hex).
4. Người dùng: nghiệm thu DEV đợt 2 theo `C:\Dev\pc2_test_runs\2026-10-26_audit_p3\NGHIEM_THU_DEV_DOT2.md` (~15 phút).
5. Người dùng quyết: P-6 (3 phương án, `…\2026-10-26_audit_p3\P6_PHUONG_AN.md`); P-7 (`P7_THIET_KE.md` cùng thư mục, công
   cụ `C:\Dev\pc2_test_tools\p7_lich_su_bong`, CHƯA chạy dữ liệu thật — chỉ chạy CHỈ ĐỌC khi duyệt); B-13, F-16; 3 ghép
   tuỳ chọn của P0 (`ket_qua_panel.json`, mục 25/10 «P0 bóng»); Stable 1.1.3 có phát hành sau P3 hay không.
6. PC1: review `…\2026-10-26_audit_p3\GOI_REVIEW_PC1.md` (PR #15–#17 đã vào `integration/current` chưa có PC1 review, mã đang
   chạy dữ liệu THẬT trên DEV); chạy bộ đột biến outbox; quyết đề xuất E-1 (`.claude/settings.json` chặn đọc khoá Google, 2
   test xfail strict); cập nhật `CURRENT_STATE.md` theo mục 26/10.
7. Còn mở từ trước: đồng bộ tiếp kênh Joe → vân tay «Kho Joe» (tab «Kho clip gốc», không tạo kho mới); hồ sơ đích Sheets +
   binding khoá NGOÀI State Stable cho DEV; ruleset GitHub (`release/github/`, chưa bật); C7; nghiệm thu preview 8502.
8. Kho Joe VODs (D-34): 150 video tải xong 07/11 (197 file, 727 giờ, 21 GB, 0 hỏng). Về ĐÊM (cần RAM 15–20 GB): «Tạo lại từ đầu» → quét thử.
9. D-49/D-50: ô «🎯 Tinh chỉnh mốc từng giây» (thanh bên «⚙️ Tham số» → «Mở để tinh chỉnh», DEV đang BẬT) nay đổi
   «Đoạn vi phạm» của báo cáo/Sheets/lịch sử cho dòng tinh chỉnh được (D-50). Người dùng kiểm tay vài video nữa; giai đoạn 2
   (lưu chỗ cắt/hồ sơ từng giây vào lịch sử) = quyết định riêng: `TimClipPro/docs/KHOP_TUNG_GIAY.md`.
10. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
### 2026-11-23 — tra kho nhanh (nhánh fix/pc2/tra-kho-nhanh)
- `_exact_match_counts` gốc quét lại MỌI hits cho mỗi (clip, mode). Bản «cắt lát» trong `audfprint_match_runner`
  (gom theo clip, sắp theo độ lệch, mỗi mode đọc đúng lát; gắn cả worker joblib) — y hệt từng phần tử. Thật:
  khúc 29 phút 53 → 0,9 s, khúc 60 phút 205 → 2,2 s; trọn 4 khúc 401 → 45 s. `tests/test_tra_kho_nhanh.py` 11/11.
### 2026-11-23 — file kiểm claim (D-64, nhánh feature/pc2/file-kiem-claim)
- `video_trong_may.tao_file_kiem_claim`: khung đen 256×144 1 fps `d=<độ dài>` + `1:a:0` (copy khi AAC, không thì AAC 320k; tuỳ chọn 96k/48k); ô ở «Video trong máy». 7 test mới (MD5 tiếng, độ dài, độ trễ, MP3, không tiếng, UI).
- Mục cũ hơn (2026-11-23 sửa 14 mục review D-63; 2026-11-23 so khớp «4/4 khúc, 99%» rồi đứng ~15 phút; 2026-11-23 giao diện D-63: menu 5 nhóm + mở nhanh + bớt thao tác tay + gọn chữ; 2026-11-23 khoá JSON chậm; 2026-11-23 test «Dừng giữa chừng»; 2026-11-20 3 việc hoãn của review Codex; 2026-11-20 review Codex + 14 bản sửa; 2026-11-20 ghép chỉ audio D-61; 2026-11-19 chụp ảnh D-60; 2026-11-17 giữ tab đang mở; 2026-11-17 bỏ nhiều đoạn D-59; 2026-11-16 YouTube Data API + 7 tính năng D-51…D-58; 2026-11-16 audit toàn repo 20 mục; 2026-11-15 «Đoạn vi phạm» theo mốc tinh chỉnh D-50; 2026-11-14/15 tinh chỉnh mốc từng giây D-49; 2026-11-11 audit tổng Codex; 2026-11-12 thumbnail tên = mã D-47/D-48; 2026-11-11 video trong máy D-46; 2026-11-11 thumbnail cả kênh D-45; 2026-11-11 Twitch 1440p D-44; 2026-11-10 âm lượng D-43; 2026-11-10 audit phần video mới; 2026-11-09 cắt đoạn D-42; 2026-11-09 tải 4 kết nối D-40; 2026-11-09 ghép video gốc D-39/D-41 + chương QuickTime; 2026-11-09 tiêu đề kênh D-38 + audit 09/11; 2026-11-08 tải video gốc D-37 + review/audit 08/11; 2026-11-07 Codex bước 2 audit 14 + 18; 2026-11-07 Codex review PR #27–#29 D-36; 2026-11-07 đồng bộ nén song song D-35; 2026-11-07 audit số 15, 19, 20; 2026-11-07 kho video dài D-34; 2026-11-07 dựng kho nhường ổ cứng D-33; 2026-11-06 audit số 7–13; 2026-11-06 audit số 1–6; 2026-11-06 gộp D-31; 2026-11-06 dựng kho theo RAM D-31; 2026-11-06 phân tích tải dựng kho; 2026-11-02 ngày đăng D-30 + máy mới; 2026-10-27 đồng bộ song song D-29; 2026-10-26 audit độc lập 25/10; 2026-10-26 13 lỗi YouTube; 2026-10-25 P0 «bóng» D-27 + P0-1; 2026-10-25 link «Đoạn vi phạm» dạng watch; 2026-10-15 DEV-ONLY D-26, tích hợp PR #9 + gom #10/#11, thanh bên cookie PR #11, nghiệm thu PR #9 + pilot, tiến độ + hiệu suất đồng bộ kênh, PR #8, chuyển quyền phát hành, review PR #6; 2026-10-14 trở về trước): `docs/ai/handoff/LICH_SU_PC2.md`.
