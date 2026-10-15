# Ma trận test — TimClipPro

Mốc: `e49340d` (tree `2aee2510`): 138 file test (`TimClipPro/tests/test_*.py`); 14 test chậm nằm trong 8 file (số trong ngoặc = số test chậm).
Thêm/đổi tên file test → thêm vào bảng «Chọn test theo vùng» trong CÙNG commit (mỗi file phải có đúng một vùng).

## Kết quả thật gần nhất
| Mốc | Máy, môi trường | Nhanh (`-m "not slow"`) | Chậm (`-m slow`) | Khác |
|---|---|---|---|---|
| `e49340d` (08/10/2026) | PC1; runtime dựng từ lock CÓ BĂM, Python 3.12.10; bản sao cây; chặn mạng | 2453 thu thập = 2445 đạt / 8 bỏ qua / 0 hỏng (226 s) | 14/14 (422 s) | đột biến outbox 123/123 bị bắt |
| `b05a74d` (09/10/2026, chỉ tài liệu) | PC1; cùng runtime lock có băm; bản sao cây; chặn mạng | 2453 thu thập = 2445 đạt / 8 bỏ qua / 0 hỏng (307 s) | chỉ `test_hai_may_gia_lap.py`: 1/1 | mã y hệt e49340d (diff chỉ tài liệu, `.gitignore`, `.claude/`) |
| `da66f0e` (09/10/2026, PR #1; `b627af0` chỉ thêm handoff) — PC2 tự báo | PC2; Windows 11 (người dùng báo), Python 3.12.10 gốc + venv `TimClipPro\.venv`; stdout cp1252; clone tạm; chặn mạng | 2460 thu thập = 2458 đạt / 2 bỏ qua / 0 hỏng | 14/14 trên `c1f19d8` (không chạy lại — chỉ đổi test) | `test_health_check.py` 12/12; đột biến `_utf8_dau_ra` no-op → 2 đỏ, launcher bỏ biến UTF-8 → 1 đỏ; ruff sạch |
| `b627af0` (10/10/2026, review PR #1) | PC1; runtime lock có băm, Python 3.12.10; bản sao cây; chặn mạng | 2460 thu thập = 2452 đạt / 8 bỏ qua / 0 hỏng (283 s) | — | test CŨ ép cp1252 → 1 hỏng (`UnicodeEncodeError`); `test_health_check.py` MỚI 12/12 ở UTF-8 và 12/12 khi cha cp1252 |
| `8bd69a7` (14/10/2026, review PR #4 CookieFix) | PC1; runtime lock có băm 1.1.1 (`py312-f955a32807a9` = lock 1.0.0 + yt-dlp-ejs 0.8.0), Python 3.12.10, Node.js 22.22.0; bản sao cây; chặn mạng + chặn đọc hồ sơ trình duyệt | 2582 thu thập = 2574 đạt / 8 bỏ qua / 0 hỏng | 19/19 (484 s) | ruff sạch; 6 test `.gitignore` trong worktree đạt |
| `15e4f88` (14/10/2026, sửa F1/F3 — nhánh `feature/pc1/cookiefix-f1-f3`) | như dòng trên | 2599 thu thập = 2591 đạt / 8 bỏ qua / 0 hỏng (329 s) | 19/19 (522 s) | 17 test mới: cả 17 đỏ trên mã `8bd69a7` → xanh; đột biến 6/6 bị bắt; ruff sạch |
| `c1f96fa` (15/10/2026, hai máy ngang quyền ký — nhánh `feature/pc1/dual-release-authority`) | PC1; runtime lock có băm 1.1.1, Python 3.12.10; bản sao cây; chặn mạng + chặn đọc khoá thật | 2710 thu thập = 2702 đạt / 8 bỏ qua / 0 hỏng (300 s) | 19/19 (364 s) | 103 ca test mới (`uy_quyen_khoa`, `release_tool_hai_may`, `git_hook_pre_push`) — cp1252 cũng xanh; đột biến 43/43; diễn tập sandbox `tests/dien_tap_phat_hanh.py` 19/19; ruff sạch; 6 test `.gitignore` trong worktree đạt |
| `7c60af5` (14/10/2026, sửa theo review phần sửa — mã cuối của Stable 1.1.1) | như dòng trên | 2607 thu thập = 2599 đạt / 8 bỏ qua / 0 hỏng (294 s) | 19/19 (455 s) | 25 ca test mới: cả 25 đỏ trên mã `8bd69a7` → xanh; đột biến 8/9 (còn lại: đường không tới được); ruff sạch; 6 test `.gitignore` trong worktree đạt |

Bằng chứng (ngoài Git): PC1 — junit `test_fast_rt_kiem.xml`, `test_slow_rt_kiem.xml` trong thư mục vòng phát hành Stable
08/10 và `pr1_*.xml` của vòng 10/10; PC2 — junit trong `C:\Dev\pc2_test_runs\` (handoff PC2). Số ở đây phải lấy từ
junit/kết quả thật, không ước lượng.

Bỏ qua trên PC1 (8): 6 test `test_dong_goi_bi_mat::test_gitignore_chan_bien_the_ten_bi_mat[*]` («không chạy trong repo
git» — PC1 chạy trên BẢN SAO cây từ `git archive`), 1 symlink cần quyền (WinError 1314), 1 file đang mở (`test_khoa`).
PC2 chạy trong clone nên chạy được 6 test `.gitignore`. Chỗ hở của cách chạy bản sao: PC1 phải chạy riêng 6 test đó
trong một worktree git — vòng 10/10: `pytest tests/test_dong_goi_bi_mat.py -k gitignore` trong worktree → 6/6 đạt.

## Lệnh (chạy trong `TimClipPro/`, `<py>` = Python của venv phát triển)
- Nhanh: `<py> -m pytest -q -p no:cacheprovider` (`pytest.ini` đã đặt `-m "not slow"`).
- Chậm (audio thật, cần ffmpeg/ffprobe trong `bin/` hoặc PATH): `<py> -m pytest -q -p no:cacheprovider -m slow`.
- Một file / một test: `<py> -m pytest tests/test_outbox.py -q`, thêm `-k <tên>`.
- Đếm chắc chắn: thêm `--junitxml=<file ngoài repo>` rồi đọc số trong junit.
- Lint: `<py> -m ruff check .` (`ruff.toml`: E4, E7, E9, F; bỏ `audfprint-master`). Import sạch:
  `<py> -c "import engine, channel, sheets, cli; print('ok')"`.
- Cổng 1 lệnh cho người dùng: `kiemtra.bat` (tự tìm `.venv`; `KIEMTRA_PY` = Python có pytest; `KIEMTRA_KHONG_DUNG=1`
  để khỏi `pause`).

## Venv phát triển (mỗi clone một venv riêng — KHÔNG dùng venv của production/Stable)
```bat
cd TimClipPro
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install --no-deps -r requirements-lock.txt
.venv\Scripts\python -m pip install "pytest>=9,<10" "ruff>=0.12,<1"
```
Cần mạng (PyPI); `docopt 0.6.2` chỉ có sdist nên pip tự build. `TimClipPro\.venv` đã nằm trong `.gitignore` và là chỗ
`kiemtra.bat`, `ChayTool.bat` tự tìm. Tạo venv từ Python gốc của máy thì KHÔNG cài/nâng cấp gói vào chính Python gốc
(PC2: Stable cũng dựng từ Python 3.12.10 gốc đó).

## Hai máy và bảng mã Windows (cp1252)
- PC2: Windows 11 (người dùng báo), Python 3.12.10 gốc + venv riêng, stdout mặc định cp1252 (Windows tiếng Anh). PC1:
  test trên runtime lock có băm Python 3.12.10, bản sao cây, rào chắn đặt stdout UTF-8.
- Tiến trình con in tiếng Việt phải đi qua `_utf8_dau_ra()` (như `health_check.main`) hoặc môi trường của launcher
  (`PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`). Hồi quy: `test_health_check.py` ép bảng mã tiến trình con cp1252 và utf-8
  (PR #1). Test mới có subprocess + tiếng Việt → tham số hoá cả hai bảng mã theo cùng cách.
- PC2 chạy suite với bảng mã MẶC ĐỊNH của máy (không ép UTF-8) để bắt lỗi cp1252 mà PC1 không thấy.

## Quy tắc khi viết/chạy test
- Không ghi vào `data/` của thư mục mã: dùng `tmp_path` + `TIMCLIP_DATA_DIR` / `TIMCLIP_OUTPUT_DIR`.
- KHÔNG BAO GIỜ chạy test hay Development trỏ vào dữ liệu production: không đặt `TIMCLIP_DATA_DIR` / `TIMCLIP_STATE_ROOT`
  về `C:\TimClipPro_State` hay `data/` của production; chỉ dữ liệu tổng hợp/thư mục tạm; venv riêng của clone.
- Không mạng thật: Sheets dùng `tests/sheets_http_gia.py`; YouTube dùng `tests/ytdlp_gia.py`; kho dùng `tests/kho_gia.py`.
- Lỗi: viết test ĐỎ tái hiện trước, sửa, rồi xanh; với vị từ quan trọng, đảo vị từ (đột biến) → test phải đỏ.
- Test chậm cần bộ nhớ ảo trống (đã gặp WinError 1455 khi máy đang mở ứng dụng nặng).

## Chọn test theo vùng (tên file bỏ `test_` và `.py`; `*` = mọi file cùng tiền tố)
| Vùng | Test mục tiêu | Chậm | Mở rộng khi |
|---|---|---|---|
| Matcher / quét (`.claude/rules/matcher.md`) | golden_quet_cu, muc_tieu_quet, nguon_chung_thuan, nguon_chung_ke_hoach, nguon_chung_jobs, nguon_chung_ui, match_selection, selection, merge_hash_split, quet_tang_dan, pham_vi_quet, toc_do_khop, toa_do_bu_toc_do, tang_toc, overlap_policy, shifts, nhan_vung, engine_core, engine_meta, chan_doan_zero_match, huy_batch, scan_streaming, scan_thread_boundary, scan_ui_schema, thoi_luong, gioi_han_video_dai, tien_do_quet, tien_do_lo_quet, do_dai_audio_that, tai_mot_phan_chia_khoi | integration (3), nguon_chung_audio_that (2), toa_do_audio_that (1), tai_mot_phan_that (5) | đổi `_scan_media`, `_merge`, ngưỡng, dừng sớm → cả suite nhanh + chậm + đột biến |
| Sheets / outbox (`.claude/rules/sheets-outbox.md`) | outbox*, ghi_theo_ma_tab, ghim_tab_truoc_khi_gui, viec_cu_khong_ma_tab, sheet_destinations, sheets_session, ui_gui_sheets, lich_su_v3, lich_su_v4, lich_su_theo_kho, giam_sat_bat, bang_ngang, bao_cao_v2_sheets*, bao_cao_v2_apps_script, ma_tab_arrow | — | đổi transport, trạng thái, lược đồ → cả suite nhanh + đột biến outbox |
| Updater / cài đặt / phát hành (`.claude/rules/updater.md`) | managed_update*, launcher*, bootstrap*, release_tool*, uy_quyen_khoa, git_hook_pre_push, runtime_paths, runtime_engine, bo_cuc_thu_muc, maintenance_gate, cong_bao_tri_tich_hop, health_check, ui_cap_nhat, cap_nhat*, packaging, dong_goi_*, kiemtra_gate | hai_may_gia_lap (1) | trước khi build Stable → cả suite nhanh + chậm trên runtime dựng từ lock có băm; trước khi phân phối → `tests/dien_tap_phat_hanh.py` (sandbox, `docs/PHAT_HANH_HAI_MAY.md` §2) |
| YouTube / tải | truy_cap_youtube*, phien_youtube, ytdlp_chung, cookie_*, tai_audio_fallback, channel_tai_fallback, tai_nen_an_toan, cau_hinh_toi_moi_duong, youtube_doctor, trang_thai_youtube_ui, kenh_link_videos, dong_bo_kenh_xac_thuc_kho | — | đổi phân loại lỗi/cầu dao → + watch, nguon_chung_jobs; đổi «Bổ sung» kho → + vùng Metadata / kho |
| Báo cáo V2 / ngày đăng | bao_cao_v2, bao_cao_v2_app, bao_cao_v2_kho_moi, bao_cao_v2_lich_su, bao_cao_v2_loi_anh_chup, bao_cao_v2_ngay_goc, bao_cao_v2_nguon_chung, bao_cao_v2_quet, bao_cao_v2_xoa_job, publication_date*, ngay_dang, dossier, bang_ket_qua_arrow, thoi_diem | — | + golden_quet_cu và vùng Sheets |
| Metadata / kho / vân tay | clip_metadata, metadata_*, meta_giao_dich, va_meta, kiem_ngay_dang, kiem_thoi_luong, danh_sach_video, kho_build_an_toan, fingerprint_*, audfprint_multiproc, bo_sung_lam_moi_van_tay | audfprint_progress_integration (2), bo_sung_lam_moi_van_tay (2) | đổi tạo/nạp kho → + chậm |
| Watch / giám sát | watch, watch_kho_an_toan, cli_watch, dung_lai | — | + vùng YouTube |
| Giao diện | app, app_fingerprint_progress, app_scan_no_warnings, app_scan_progress, cach_ly_main_module | — | + `kiemtra.bat` bước 3 (AppTest) |
| Hạ tầng | core, khoa, luu_tru, luu_tru_lien_tien_trinh, nhat_ky, process_runner, so_huu_tien_trinh, ffmpeg_timeout, don_dep, cau_hinh, security_regressions | — | đụng log/khoá/ghi file → cả suite nhanh |
| Phản biện đối nghịch (nhiều vùng) | phan_bien_vong_ba, phan_bien_vong_ba_quet, phan_bien_doc_lap, phan_bien_vong_hai | phan_bien_doc_lap (1), phan_bien_vong_hai (2) | trước khi chốt nhánh lớn |
