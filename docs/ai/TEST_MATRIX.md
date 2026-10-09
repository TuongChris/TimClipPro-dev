# Ma trận test — TimClipPro

Mốc: `e49340d` (tree `2aee2510`): 138 file test (`TimClipPro/tests/test_*.py`); 14 test chậm nằm trong 8 file (số trong ngoặc = số test chậm).
Thêm/đổi tên file test → thêm vào bảng «Chọn test theo vùng» trong CÙNG commit (mỗi file phải có đúng một vùng).

## Kết quả thật gần nhất
| Mốc | Máy, môi trường | Nhanh (`-m "not slow"`) | Chậm (`-m slow`) | Khác |
|---|---|---|---|---|
| `e49340d` (08/10/2026) | PC1; runtime dựng từ lock CÓ BĂM, Python 3.12.10; bản sao cây; chặn mạng | 2453 thu thập = 2445 đạt / 8 bỏ qua / 0 hỏng (226 s) | 14/14 (422 s) | đột biến outbox 123/123 bị bắt |
| `b05a74d` (09/10/2026, chỉ tài liệu) | PC1; cùng runtime lock có băm; bản sao cây; chặn mạng | 2453 thu thập = 2445 đạt / 8 bỏ qua / 0 hỏng (307 s) | chỉ `test_hai_may_gia_lap.py`: 1/1 | mã y hệt e49340d (diff chỉ tài liệu, `.gitignore`, `.claude/`) |

Bằng chứng (ngoài Git, trên PC1): junit `test_fast_rt_kiem.xml`, `test_slow_rt_kiem.xml` trong thư mục vòng phát hành
Stable 08/10. Số ở đây phải lấy từ junit/kết quả thật, không ước lượng.

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
`kiemtra.bat`, `ChayTool.bat`, `.claude/launch.json` tự tìm.

## Quy tắc khi viết/chạy test
- Không ghi vào `data/` của thư mục mã: dùng `tmp_path` + `TIMCLIP_DATA_DIR` / `TIMCLIP_OUTPUT_DIR`.
- Không mạng thật: Sheets dùng `tests/sheets_http_gia.py`; YouTube dùng `tests/ytdlp_gia.py`; kho dùng `tests/kho_gia.py`.
- Lỗi: viết test ĐỎ tái hiện trước, sửa, rồi xanh; với vị từ quan trọng, đảo vị từ (đột biến) → test phải đỏ.
- Test chậm cần bộ nhớ ảo trống (đã gặp WinError 1455 khi máy đang mở ứng dụng nặng).

## Chọn test theo vùng (tên file bỏ `test_` và `.py`; `*` = mọi file cùng tiền tố)
| Vùng | Test mục tiêu | Chậm | Mở rộng khi |
|---|---|---|---|
| Matcher / quét (`.claude/rules/matcher.md`) | golden_quet_cu, muc_tieu_quet, nguon_chung_thuan, nguon_chung_ke_hoach, nguon_chung_jobs, nguon_chung_ui, match_selection, selection, merge_hash_split, quet_tang_dan, pham_vi_quet, toc_do_khop, toa_do_bu_toc_do, tang_toc, overlap_policy, shifts, nhan_vung, engine_core, engine_meta, chan_doan_zero_match, huy_batch, scan_streaming, scan_thread_boundary, scan_ui_schema, thoi_luong | integration (3), nguon_chung_audio_that (2), toa_do_audio_that (1) | đổi `_scan_media`, `_merge`, ngưỡng, dừng sớm → cả suite nhanh + chậm + đột biến |
| Sheets / outbox (`.claude/rules/sheets-outbox.md`) | outbox*, ghi_theo_ma_tab, ghim_tab_truoc_khi_gui, viec_cu_khong_ma_tab, sheet_destinations, sheets_session, ui_gui_sheets, lich_su_v3, lich_su_v4, lich_su_theo_kho, giam_sat_bat, bang_ngang, bao_cao_v2_sheets*, bao_cao_v2_apps_script | — | đổi transport, trạng thái, lược đồ → cả suite nhanh + đột biến outbox |
| Updater / cài đặt / phát hành (`.claude/rules/updater.md`) | managed_update*, launcher*, bootstrap*, release_tool*, runtime_paths, runtime_engine, bo_cuc_thu_muc, maintenance_gate, cong_bao_tri_tich_hop, health_check, ui_cap_nhat, cap_nhat*, packaging, dong_goi_*, kiemtra_gate | hai_may_gia_lap (1) | trước khi build Stable → cả suite nhanh + chậm trên runtime dựng từ lock có băm |
| YouTube / tải | truy_cap_youtube*, phien_youtube, ytdlp_chung, cookie_*, tai_audio_fallback, channel_tai_fallback, tai_nen_an_toan, cau_hinh_toi_moi_duong, youtube_doctor, trang_thai_youtube_ui, kenh_link_videos | — | đổi phân loại lỗi/cầu dao → + watch, nguon_chung_jobs |
| Báo cáo V2 / ngày đăng | bao_cao_v2, bao_cao_v2_app, bao_cao_v2_kho_moi, bao_cao_v2_lich_su, bao_cao_v2_loi_anh_chup, bao_cao_v2_ngay_goc, bao_cao_v2_nguon_chung, bao_cao_v2_quet, bao_cao_v2_xoa_job, publication_date*, ngay_dang, dossier, bang_ket_qua_arrow, thoi_diem | — | + golden_quet_cu và vùng Sheets |
| Metadata / kho / vân tay | clip_metadata, metadata_*, meta_giao_dich, va_meta, kiem_ngay_dang, kiem_thoi_luong, danh_sach_video, kho_build_an_toan, fingerprint_*, audfprint_multiproc, bo_sung_lam_moi_van_tay | audfprint_progress_integration (2), bo_sung_lam_moi_van_tay (2) | đổi tạo/nạp kho → + chậm |
| Watch / giám sát | watch, watch_kho_an_toan, cli_watch, dung_lai | — | + vùng YouTube |
| Giao diện | app, app_fingerprint_progress, app_scan_no_warnings, app_scan_progress, cach_ly_main_module | — | + `kiemtra.bat` bước 3 (AppTest) |
| Hạ tầng | core, khoa, luu_tru, luu_tru_lien_tien_trinh, nhat_ky, process_runner, so_huu_tien_trinh, ffmpeg_timeout, don_dep, cau_hinh, security_regressions | — | đụng log/khoá/ghi file → cả suite nhanh |
| Phản biện đối nghịch (nhiều vùng) | phan_bien_vong_ba, phan_bien_vong_ba_quet, phan_bien_doc_lap, phan_bien_vong_hai | phan_bien_doc_lap (1), phan_bien_vong_hai (2) | trước khi chốt nhánh lớn |
