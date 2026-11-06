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
3. Audit toàn repo 06/11: số 1–6 GỘP (PR #24, `256e848`), DEV 8502 cập nhật 06/11 22:09 (sao lưu `data_20261106_220855`). PC1 phải cài lại
   hook. Số 7–13 đã sửa trên `fix/pc2/audit-0611-dot2`, chờ duyệt gộp + cập nhật DEV. Còn 14–20 + 8 mục nhỏ: báo cáo trong phiên
   06/11 (lịch sử chat), số 14 có 21 ca đột biến updater sống.
4. Người dùng: nghiệm thu DEV đợt 2 theo `C:\Dev\pc2_test_runs\2026-10-26_audit_p3\NGHIEM_THU_DEV_DOT2.md` (~15 phút).
5. Người dùng quyết: P-6 (3 phương án, `…\2026-10-26_audit_p3\P6_PHUONG_AN.md`); P-7 (`P7_THIET_KE.md` cùng thư mục, công
   cụ `C:\Dev\pc2_test_tools\p7_lich_su_bong`, CHƯA chạy dữ liệu thật — chỉ chạy CHỈ ĐỌC khi duyệt); B-13, F-16; 3 ghép
   tuỳ chọn của P0 (`ket_qua_panel.json`, mục 25/10 «P0 bóng»); Stable 1.1.3 có phát hành sau P3 hay không.
6. PC1: review `…\2026-10-26_audit_p3\GOI_REVIEW_PC1.md` (PR #15–#17 đã vào `integration/current` chưa có PC1 review, mã đang
   chạy dữ liệu THẬT trên DEV); chạy bộ đột biến outbox; quyết đề xuất E-1 (`.claude/settings.json` chặn đọc khoá Google, 2
   test xfail strict); cập nhật `CURRENT_STATE.md` theo mục 26/10.
7. Còn mở từ trước: đồng bộ tiếp kênh Joe → vân tay «Kho Joe» (tab «Kho clip gốc», không tạo kho mới); hồ sơ đích Sheets +
   binding khoá NGOÀI State Stable cho DEV; ruleset GitHub (`release/github/`, chưa bật); C7; nghiệm thu preview 8502.
8. Mỗi task: mẫu «PC2» trong `docs/ai/SESSION_START.md`.

## Nhật ký
### 2026-11-06 — sửa số 7–13 của audit toàn repo (nhánh fix/pc2/audit-0611-dot2)
- Làm: hồ sơ không cộng đôi vùng chồng nhau; lưu cấu hình chỉ ghi khoá phiên này đổi; tab cũ theo thư mục nguồn mới; `Thread.start` lỗi không để
  lại việc ma; lỗi đọc tạm không bị coi là file hỏng; hoàn tác ghi bản `sau_hoan_tac`; updater không báo ACTIVE khi không áp dụng gì. Mỗi lỗi có
  test đỏ trước. `launcher.py` + `managed_update.py` chỉ có hiệu lực trên máy đã cài sau bootstrap lại. Chưa gộp, DEV chưa cập nhật.
- Test (chặn mạng, cp1252, venv CookieFix) @ `79ded22`: nhanh 3455 = 3451/4/0, chậm 22/22, ruff sạch (`C:\Dev\pc2_test_runs\2026-11-06_audit_0611_dot2`).
  Review độc lập: 2 P2 + 4 P3 trong chính bản sửa (lỗi đọc tạm lúc mở phiên chọn nhầm kho, xoá cấu hình), đã sửa kèm test đỏ.
### 2026-11-06 — sửa số 1–6 của audit toàn repo (nhánh fix/pc2/audit-0611)
- Làm: nút Dừng đồng bộ sau bấm đúp; lô nguồn chung tự lưu CSV; đọc kho lỗi không bị nhớ thành kho rỗng; hook quét merge commit, tên có
  dấu cách, đổi tên y nguyên (hook mới ĐÃ CÀI trên PC2, bản cũ không có khối quét nội dung); «Quét toàn bộ» quét hết (D-32); bản đệm cụt bị bỏ.
- Mỗi lỗi có test đỏ trước khi sửa. Test (chặn mạng, cp1252, venv CookieFix) @ `ee414ed`: nhanh 3429 = 3425/4/0, chậm 22/22, ruff sạch
  (`C:\Dev\pc2_test_runs\2026-11-06_audit_0611`). Review độc lập: 0 P1, 2 P2 và 5 P3 ở hook/đệm/test, đã sửa hết.
- Gộp PR #24 + cập nhật DEV: trước khi tắt, tiến trình thật không có con, ghi 0 B trong 30 s, 26 khoá không bị giữ, hàng đợi Sheets 584 SENT.
  Sau cập nhật: health ok, đủ 7 tab, console 0 lỗi, dữ liệu không đổi. Đề xuất `CURRENT_STATE.md` (PC1 sửa): integration = `256e848`, PC1 chưa review.
### 2026-11-06 — gộp D-31 (PR #23) và cập nhật DEV 8502
- Người dùng duyệt gộp + cập nhật DEV. Test lại đúng `73c5734`: nhanh 3394 = 3390/4/0, chậm 22/22, ruff sạch (`…\2026-11-06_dung_kho_ram\gop_73c5734`).
- Trước khi tắt DEV: không tiến trình con, không ghi mới, `tool.lock` rảnh, ghi 0 B trong 15 s, hàng đợi Sheets 584 SENT. Smoke: health ok,
  CLI `dich` đạt, đủ 7 tab, console 0 lỗi. Dữ liệu không đổi. Đề xuất `CURRENT_STATE.md` (PC1 sửa): integration = `73c5734`, PC1 chưa review.
### 2026-11-06 — dựng kho theo RAM, bỏ clip dài hơn 2 giờ (D-31, nhánh feature/pc2/dung-kho-theo-ram)
- Làm: cha phát từng clip theo RAM (`LichTheoRam`), clip lỗi thử lại cuối lượt, clip quá RAM bỏ qua có báo rõ, Below Normal, nhánh
  một nhân đi cùng đường. Người dùng chốt thêm: video > 2 giờ không tải, clip > 2 giờ không tạo vân tay (`channel.GIAY_CLIP_TOI_DA`).
- Test (chặn mạng, cp1252, venv CookieFix): nhanh 3394 = 3390/4/0 (373 s), chậm 22/22 (379 s), ruff sạch. Nghiệm thu `do_dung_kho_ram.py d`
  qua Engine thật: 34/34 clip, đúng 2 clip > 2 giờ bị bỏ, tìm lại 4/4, RAM trống thấp nhất 9,56 GB. Dựng trọn Kho_Joe chưa chạy lại.
- Bằng chứng: `C:\Dev\pc2_test_runs\2026-11-06_dung_kho_ram`, số đo ở tài liệu phân tích. Review độc lập: 0 P1, 1 P2 (RAM tụt 60
  giây bỏ cả hàng), 5 P3, đều test đỏ rồi sửa. `/ponytail-review`: 1 test đỏ, video đúng 2:00:00 lệch giữa hai bước, bản chép đo
  độ dài, 2 câu báo sai, đều đã sửa. Bẫy: `audio_read.read_data` ghép stderr bytes nên FFmpeg treo lộ thành TypeError.
### 2026-11-06 — phân tích tải dựng kho (nhánh feature/pc2/phan-tich-tai-dung-kho)
- Đo thật 10 bài (`TimClipPro/docs/PHAN_TICH_TAI_DUNG_KHO_2026-11.md`, công cụ `tools/do_tai/`): quá tải là DỰNG VÂN TAY, nguyên
  nhân RAM (~1,5 GB/giờ âm thanh mỗi worker; clip #291 của Kho_Joe_Games dài 18,2 giờ làm cả lượt sụp), không có điểm lưu giữa
  chừng. Đường đồng bộ chỉ làm HDD bận tối đa 5%. CHƯA tái hiện «HDD 100% + hàng đợi ~30». Chưa sửa mã, chờ người dùng chọn.
- Mục cũ hơn (2026-11-02 ngày đăng D-30 + máy mới; 2026-10-27 đồng bộ song song D-29; 2026-10-26 audit độc lập 25/10; 2026-10-26 13 lỗi YouTube; 2026-10-25 P0 «bóng» D-27 + P0-1; 2026-10-25 link «Đoạn vi phạm» dạng watch; 2026-10-15 DEV-ONLY D-26, tích hợp PR #9 + gom #10/#11, thanh bên cookie PR #11, nghiệm thu PR #9 + pilot, tiến độ + hiệu suất đồng bộ kênh, PR #8, chuyển quyền phát hành, review PR #6; 2026-10-14 trở về trước): `docs/ai/handoff/LICH_SU_PC2.md`.
