# Runtime có quản lý, hồ sơ đích Google Sheets, outbox lưu bền, cập nhật Stable cho PC2

Design Gate của brief `CLAUDE_TIMCLIPPRO_MULTI_PC_MULTI_SHEET_IMPLEMENTATION.md` (07/10/2026). Baseline
`6dc3f9d` (cây `469ae2bd`) — commit mới nhất mọi nhánh; Report Policy V2 + ba P1 đã sửa nằm trong đó.

Nhãn bằng chứng: **CONFIRMED_IN_CODE** (đọc trong source baseline, có dòng), **REPRODUCED** (test chạy
trên mã gốc chứng minh), **DESIGN_CHOICE** (quyết định của vòng này), **UNVERIFIED_ON_PC2** (chưa có
máy PC2 để kiểm), **NOT_RUN** (cần mạng/khoá/máy thật — chờ pilot có duyệt).

Mục tiêu sản phẩm, theo thứ tự ưu tiên: **không gửi sai nơi → không mất dữ liệu/việc gửi → không hỏng
cập nhật → giữ hành vi matching → dễ dùng → hiệu năng.**

## 1. Hiện trạng đã kiểm

| # | Hiện trạng | Nhãn |
|---|---|---|
| H1 | Hàng đợi gửi Sheets nằm trong RAM (`sheet_delivery.SheetDeliveryWorker`: `queue.Queue` + `dict`); tắt app là mất việc chưa gửi (chính docstring nói vậy). | CONFIRMED_IN_CODE `sheet_delivery.py:15-19,142-143`; REPRODUCED |
| H2 | `SheetDelivery` là `@dataclass(frozen=True)` nhưng `header`/`rows` là `list` — sửa list sau khi xếp hàng làm đổi payload. | CONFIRMED `sheet_delivery.py:95-114`; REPRODUCED |
| H3 | Phân loại lỗi bằng chuỗi con của message; `timeout`, `500…504`, `connection reset/aborted` và MỌI lỗi lạ đều bị coi là tạm thời → thử lại tới 4 lần. Google đã ghi mà phản hồi mất (ReadTimeout) → **trùng dòng**. | CONFIRMED `sheet_delivery.py:45-69,232-257`; REPRODUCED (`repro/test_tai_hien_hang_doi_ram.py`) |
| H4 | Đích gửi là một chuỗi link chụp lúc bấm Bắt đầu (`ScanLaunchConfig`, frozen, chuỗi thuần) — lô đang chạy KHÔNG đổi bảng khi đổi link trên UI; nhưng không có hồ sơ, không có ID tab, không bền. Tab luôn là TÊN `KetQuaQuet`. | CONFIRMED `scan_jobs.py:65-87`, `sheets.py:113-118` |
| H5 | Một kết quả chỉ được gửi khi `status == ok`, báo cáo V2 không lỗi, và có dòng (`dong_gui_sheets`). | CONFIRMED `scan_ui.py:243-272`, `engine.py:5281-5300` |
| H6 | `save_job` là nơi DUY NHẤT ghi lịch sử, một giao dịch (`jobs` + `matches` + `bao_cao_job`); gọi NGAY trong lượt quét (`engine.py:4676`, `4870`) trên bản Engine ghim cho job. | CONFIRMED `engine.py:5329-5375` |
| H7 | Kết nối SQLite: `sqlite3.connect` mặc định (timeout 5 s, rollback journal, `synchronous` mặc định FULL), mở/đóng mỗi thao tác. Lược đồ có phiên bản (`lich_su.dam_bao_luoc_do`): `BEGIN IMMEDIATE` → sao lưu bằng backup API → DDL → `user_version`; không bao giờ hạ phiên bản; bản cũ chạy được trên DB mới. | CONFIRMED `engine.py:1504-1512`, `lich_su.py:152-199` |
| H8 | SQLite của runtime là 3.49.1 — nằm trong dải dính WAL-reset bug (3.7.0–3.51.2, sửa ở 3.51.3/3.50.7/3.44.6) khi nhiều kết nối ghi/checkpoint ở chế độ WAL. | CONFIRMED (đo `sqlite3.sqlite_version`; sqlite.org/wal.html) |
| H9 | gspread 6.2.1 dùng `HTTPClient` (KHÔNG tự thử lại) với timeout mặc định `None` (chờ vô hạn); `append_rows` trả nguyên phản hồi API (`spreadsheetId`, `tableRange`, `updates.updatedRange/updatedRows`) nhưng code hiện tại không đọc phản hồi. | CONFIRMED (site-packages `gspread/http_client.py:84-128`, `worksheet.py:1820-1865`) |
| H10 | Updater `cap_nhat.py` lấy tag `git tag --sort=-v:refname` lớn nhất (MỌI tag — không lọc `v*`, `vX-rc1` xếp trên `vX`) rồi `git checkout` TẠI CHỖ khi đang chạy app/Watch; chỉ tiến (tổ tiên) trừ `--ban`; `ChayTool.bat`/`ChayMayPhu.bat` gọi nó mỗi lần mở và gọi `pip install -r requirements.txt` vào chính `.venv` đang dùng khi mã thoát 11. | CONFIRMED `cap_nhat.py:127-132,168-225`, `ChayTool.bat:30-40` |
| H11 | `requirements-lock.txt` mã hoá UTF-16, không hash, LỆCH 20 gói so với `.venv` đang chạy thật (vd. cryptography 49.0.0 vs 50.0.0, streamlit 1.60.0 vs 1.62.0), vi phạm cả `constraints.txt`; không ai dùng. | CONFIRMED (so `importlib.metadata`) |
| H12 | Engine đã tách `root` (mã) khỏi `data_dir`/`out_dir`, nhưng CHỈ app đọc `TIMCLIP_DATA_DIR`/`TIMCLIP_OUTPUT_DIR` (`app.py:59-62`); `Engine()` của CLI/Watch bỏ qua (AUD-004) → app và Watch có thể dùng hai `tool.lock` khác nhau. Khoá Google mặc định cạnh mã (`sheets.py:116`), file `DUNG` cố định `<mã>/data` (`cli.py:57-62`), `watchlist.json` theo thư mục hiện hành (`cli.py:67`), `bin/` chèn vào PATH, `__pycache__` ghi vào cây mã. | CONFIRMED `engine.py:941-1009` |
| H13 | Quét thường từ app/CLI KHÔNG giữ `tool.lock`; Watch, tạo/xoá kho, vá metadata và lô nguồn chung thì giữ. Không có cổng bảo trì, sổ tiến trình hay dấu "đang chạy" nào. | CONFIRMED (`watch.py:350`, `engine.py:1307/2178/2246/2452`, `common_original_jobs.py:191`) |
| H14 | Watch gửi Sheets ĐỒNG BỘ trong lúc giữ `tool.lock`, không timeout; lỗi gửi chỉ thử lại một lần cuối lượt (gửi cả lô → có thể trùng); dòng lỗi mất vĩnh viễn vì lượt sau bỏ qua video đã quét. Nút «Đẩy lên Google Sheets» của app gửi lại TOÀN BỘ kết quả lô (trùng các dòng worker đã gửi) bằng link HIỆN TẠI chứ không phải link đã ghim. `kiem_tra()` có thể TẠO tab `KetQuaQuet` (`add_worksheet`). | CONFIRMED `watch.py:549-716`, `app.py:265-286`, `sheets.py:166-174` |
| H15 | `ChayTool.bat:34-35`/`ChayMayPhu.bat:46-47`: `pip` chạy giữa hai `if errorlevel` nên pip thành công đặt lại ERRORLEVEL=0 → mã 11 không khởi động lại/không bỏ lượt như tài liệu nói (chưa từng xảy ra vì requirements không đổi từ v2.2). | CONFIRMED (đọc mã) |
| H16 | `kiemtra.bat` bước 3 (AppTest) chạy trên `data/` THẬT → sẽ migrate `lichsu.db` thật lên v3 nếu chạy trên máy thật. | CONFIRMED `kiemtra.bat:57` (AUD-241) |
| H17 | PC2 hiện chạy thế nào (clone git + `ChayTool.bat`? gói `dong_goi_may_chay`? bản nào? kho nào?) | UNVERIFIED_ON_PC2 |

## 2. Design Gate — hiện tại → vấn đề → lựa chọn → lý do → test nghiệm thu

| Chủ đề | Hiện tại | Vấn đề | Lựa chọn (DESIGN_CHOICE) | Lý do | Test nghiệm thu |
|---|---|---|---|---|---|
| Nơi lưu việc gửi | RAM | Mất khi tắt/mất điện | Bảng `hang_doi_gui` trong CHÍNH `lichsu.db`, ghi trong CÙNG giao dịch `save_job` | Một commit chốt job + bằng chứng + ảnh chụp + ý định gửi; không có khoảng hở giữa hai DB | lỗi giữa insert `jobs`/`bao_cao_job`/`hang_doi_gui` → không còn dòng nào; khởi động lại vẫn thấy việc |
| Chế độ journal | rollback journal mặc định | WAL trên 3.49.1 dính WAL-reset bug; WAL cấm network FS | GIỮ rollback journal + `synchronous=FULL` + `busy_timeout`; không bật WAL | Bền khi commit trả về; đa tiến trình đúng; không phụ thuộc bản vá SQLite | test hai tiến trình claim; crash sau commit vẫn còn |
| Ghim đích | link chuỗi chụp lúc Bắt đầu | Không hồ sơ, không ID tab, không bền | `YDinhGui` bất biến (chuỗi JSON chuẩn hoá của revision hồ sơ + tab ID + schema + credential binding + workspace) ghim trên bản Engine của job (`ghim_y_dinh_gui`), `save_job` đọc từ đó | Đúng mẫu ghim chính sách báo cáo ở ranh giới job; không đổi chữ ký hàm quét | lô A đang chạy, UI chọn B → mọi việc của lô (kể cả thử lại/khởi động lại) vẫn A |
| Hồ sơ đích | không có | — | Bảng `dich_gui` (con trỏ) + `dich_gui_phien_ban` (revision BẤT BIẾN) + `xac_thuc_gui` (credential binding) trong `lichsu.db` | Ràng buộc "không xoá hồ sơ còn được tham chiếu" kiểm trong cùng giao dịch | sửa → revision mới, job cũ giữ revision cũ; xoá hồ sơ còn việc → bị chặn |
| Tab | tên `KetQuaQuet` | Đổi tên/xoá-tạo lại cùng tên không phát hiện | `worksheet_id` (gid) là định danh; tên chỉ là nhãn; link cũ không có gid → gid chốt cho revision NGAY TRƯỚC request ghi đầu tiên, cùng giao dịch `SENDING` (audit f4d3cb7 MR-P1-02) | Không coi tab tạo lại cùng tên là tab cũ | đổi tên → cập nhật nhãn; xoá-tạo lại → BLOCKED_CONFIG, 0 ghi |
| Credential | `google_key.json` cạnh mã | Thay file khoá = đổi tài khoản âm thầm | Binding = đường dẫn + `client_email` mong đợi (+ `private_key_id`); khác principal → BLOCKED_CONFIG; xoay khoá cùng principal → cho phép theo cờ, ghi nhận | Không bao giờ rơi về khoá mặc định | đổi principal → chặn, 0 ghi |
| Ai gửi | 1 thread mỗi phiên app | Không bền, không phối hợp giữa app/Watch/CLI | MỘT người gửi mỗi state root, giữ khoá HĐH `hang_doi_gui.lock`; claim nguyên tử `UPDATE … WHERE trang_thai IN (…)` + `claim_token` làm fencing | Writer cũ còn sống thì writer mới không lấy được khoá → không gửi đôi cục bộ | hai tiến trình cùng chạy: 1 lần append |
| Mơ hồ khi gửi | thử lại mù | Trùng dòng (H3) | Commit `SENDING` NGAY TRƯỚC request append; chỉ lỗi CHẮC CHẮN chưa gửi (lỗi trước dispatch, `ConnectTimeout`, `NewConnectionError`, `RefreshError`, HTTP 4xx từ Google) mới quay lại; còn lại → `UNKNOWN_DELIVERY` | Không suy "chưa ghi" từ message hay từ lease hết hạn | ReadTimeout sau ghi → UNKNOWN, không append lần hai |
| Biên nhận | không đọc | — | `SENT` chỉ khi phản hồi có `spreadsheetId` đúng, `updatedRows == số dòng`, `updatedRange` thuộc đúng tab đã kiểm theo ID; bất thường → UNKNOWN | Có bằng chứng phía Google | phản hồi lệch → UNKNOWN |
| Xoá lần quét | xoá `jobs`/`matches`/`bao_cao_job` (P1-01) | Việc gửi còn treo có thể bắn sau khi UI báo đã xoá | Cùng giao dịch: PENDING/RETRY/BLOCKED → xoá; CLAIMED/SENDING/UNKNOWN → TỪ CHỐI xoá; SENT → giữ tombstone tối thiểu (công bố), bỏ payload | Không hứa thu hồi dòng Google | race xoá ↔ claim |
| Đường dẫn | `root`/`data_dir`/`out_dir`; mặc định `<mã>/data` | Bản phát hành bất biến không được chứa dữ liệu | `runtime_paths.py`: chế độ `legacy` (y như cũ) và `managed` (BẮT BUỘC `TIMCLIP_STATE_ROOT` + `installation.json` khớp; thiếu là dừng, không rơi về `<release>/data`) | Tối thiểu: Engine đã nhận `data_dir`/`out_dir` | managed thiếu state root → lỗi rõ, không tạo thư mục |
| Cổng bảo trì | không có | Update có thể đổi mã khi đang quét/gửi | `maintenance_gate.py`: mutex ngắn + lease theo việc (khoá HĐH); `dang_rut` → không nhận việc mới; updater chờ hết lease | Chống race giữa kiểm rảnh và activate | update lúc đang quét → chờ, không đổi mã |
| Nguồn bản Stable | tag git + checkout tại chỗ | Không xác thực, đổi mã đang chạy | Release asset (ZIP) + `manifest.json` ký **Ed25519** (`cryptography`), khoá công khai tin cậy cài bằng bootstrap kit; lọc channel `stable`, bỏ draft/pre-release, không hạ bản, quarantine | HTTPS + SHA-256 chỉ chứng minh toàn vẹn; chữ ký chứng minh nguồn | sai chữ ký/hash/repo/Zip Slip → từ chối, bản cũ vẫn chạy |
| Kích hoạt | checkout + pip vào venv đang chạy | Hỏng giữa chừng không phục hồi | `releases/<ver>` bất biến + `environments/<runtime_id>` tạo tại đường dẫn cuối; journal bền; con trỏ `current.json` ghi nguyên tử; health gate; last-good | Mất điện ở mỗi bước khôi phục theo journal | kill ở từng checkpoint → phục hồi xác định |
| PC1 dev | `cap_nhat.py` có thể checkout tag | Dev không được bị cập nhật | Legacy updater chỉ xét tag `v<số>`; dấu `data/dev_mode` (hoặc biến môi trường) tắt hẳn; managed release mang `MANAGED_RELEASE.json` → mọi `.bat` cũ và `runtime_paths` từ chối chạy kiểu legacy | Updater cũ không đụng cài đặt managed | `.bat` cũ trong release → thoát, không chạy pip/updater |

## 3. Sáu câu hỏi

1. **Job/report/delivery tạo và lưu ở đâu; ghim đích + send intent không có khoảng mất việc?** — Kết quả
   lưu ở `save_job` trên bản Engine ghim cho job. Ý định gửi (`YDinhGui`) được ghim lúc bấm Bắt đầu (app),
   lúc mở lượt (Watch/CLI) và đi xuống bản ghim; `save_job` chèn dòng `hang_doi_gui` (payload đã dựng
   RAW từ ảnh chụp V2) trong CÙNG giao dịch với `jobs`/`matches`/`bao_cao_job`. Commit xong mới báo "đã
   xếp hàng". Commit lỗi → lượt quét báo lỗi lưu bền (kết quả vẫn trả về UI), không có "đã lưu" giả.
2. **Runtime root nào độc lập release; entry point nào ghi theo `__file__`/CWD?** — Xem §4; chế độ
   `managed` lấy MỌI thư mục trạng thái từ `RuntimePaths` (state root + installation root), release chỉ chứa
   mã. Entry point (app, CLI/Watch, health check) gọi `runtime_paths.resolve()` một lần rồi truyền rõ.
3. **Biểu diễn profile, credential binding, job identity, outbox state?** — §5 (lược đồ v3). Định danh việc
   gửi: `dedupe_key = sha256(nguon | installation_id | workspace | job_id | dich_id | revision | schema | rieng)`
   — `rieng` rỗng cho việc tự động (ý định trùng không tạo dòng), là UUID mới cho mỗi lần «Gửi thêm (thủ
   công)» (ý định MỚI có chủ đích, phải xác nhận khi lần quét đã có việc tới cùng hồ sơ).
4. **Ai claim gửi; ai chặn nhận job khi update; thứ tự khoá?** — Người gửi duy nhất mỗi state root (khoá HĐH
   `data/hang_doi_gui.lock`), claim nguyên tử có `claim_token`. Cổng bảo trì (`data/bao_tri/`) chặn nhận
   việc mới; updater chờ hết lease. Thứ tự khoá ở §6.
5. **Stable chọn/xác minh bằng gì; khi nào rollback an toàn?** — §7: manifest ký Ed25519 + SHA-256 asset +
   chính sách channel/thứ tự phiên bản; rollback mã tự động chỉ trước mọi ghi nghiệp vụ mới, migration chỉ
   tự động khi manifest khai `tu_dong_an_toan` và bản trước đọc được lược đồ mới; không bao giờ khôi phục DB
   mù sau khi bản mới đã ghi.
6. **Bootstrap từ launcher cũ sang mới mà không kích updater cũ?** — §8: cài managed ở thư mục MỚI (không
   phải clone git), launcher mới không gọi `cap_nhat.py`, release không có `.git`, `.bat` cũ trong release từ
   chối chạy; tag phát hành dùng tiền tố `stable-…` mà updater cũ (lọc `v<số>`) không bao giờ chọn.

## 4. Đường dẫn runtime

`runtime_paths.RuntimePaths` (bất biến): `che_do`, `ma_nguon` (thư mục `TimClipPro` của release/worktree),
`state_root`, `data_dir`, `out_dir`, `log_dir`, `installation_root`, `installation_id`.

* `legacy` (mặc định, PC1 và mọi cài đặt cũ): y hệt hôm nay — `data_dir = TIMCLIP_DATA_DIR or <mã>/data`,
  `out_dir = TIMCLIP_OUTPUT_DIR or <mã>/ketqua`. Không di chuyển dữ liệu.
* `managed` (`TIMCLIP_RUNTIME_MODE=managed`): bắt buộc `TIMCLIP_STATE_ROOT` tuyệt đối, có
  `installation.json` hợp lệ; `data_dir = <state>/data`, `out_dir = <state>/output`, `log_dir = <state>/logs`.
  Thiếu/hỏng → `LoiRuntime` (app hiện trang lỗi, CLI thoát mã riêng), không tạo gì.
* Release có `MANAGED_RELEASE.json` mà không chạy `managed` → `LoiRuntime` (chặn `.bat` cũ / chạy tay).
* Chính sách đường dẫn: state root nằm dưới thư mục OneDrive/Dropbox/Google Drive hoặc ổ mạng (UNC, ổ map
  kiểu REMOTE) → `managed` từ chối, `legacy` chỉ cảnh báo (PC1 hiện ở OneDrive — giữ nguyên, có cảnh báo).
* ffmpeg/ffprobe: launcher thêm `<installation>/tools/ffmpeg/bin` vào `PATH` của tiến trình con.

## 5. Lược đồ `lichsu.db` phiên bản 3 (CHỈ THÊM BẢNG)

```sql
-- định danh cài đặt + cài đặt gửi (khoá/giá trị)
CREATE TABLE IF NOT EXISTS cai_dat_may(khoa TEXT PRIMARY KEY, gia_tri TEXT NOT NULL);
-- credential binding: KHÔNG chứa khoá riêng, chỉ đường dẫn + principal mong đợi
CREATE TABLE IF NOT EXISTS xac_thuc_gui(ref TEXT PRIMARY KEY, duong_dan TEXT NOT NULL,
    principal TEXT NOT NULL, key_id TEXT NOT NULL DEFAULT '', cho_xoay_khoa INTEGER NOT NULL DEFAULT 1,
    trang_thai TEXT NOT NULL DEFAULT 'hoat_dong', tao_luc TEXT NOT NULL, sua_luc TEXT NOT NULL);
-- hồ sơ đích (con trỏ) + revision bất biến
CREATE TABLE IF NOT EXISTS dich_gui(id TEXT PRIMARY KEY, workspace TEXT NOT NULL,
    phien_ban INTEGER NOT NULL, trang_thai TEXT NOT NULL,    -- hoat_dong | tam_dung | luu_tru
    nguon TEXT NOT NULL DEFAULT 'tay', tao_luc TEXT NOT NULL, sua_luc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dich_gui_phien_ban(dich_id TEXT NOT NULL, phien_ban INTEGER NOT NULL,
    ten TEXT NOT NULL, spreadsheet_id TEXT NOT NULL, worksheet_id INTEGER, worksheet_ten TEXT NOT NULL,
    schema_id TEXT NOT NULL, xac_thuc_ref TEXT NOT NULL, tao_luc TEXT NOT NULL,
    PRIMARY KEY(dich_id, phien_ban));
-- outbox
CREATE TABLE IF NOT EXISTS hang_doi_gui(id TEXT PRIMARY KEY, dedupe_key TEXT NOT NULL UNIQUE,
    installation_id TEXT NOT NULL, workspace TEXT NOT NULL, job_id INTEGER, lo_id TEXT NOT NULL DEFAULT '',
    nguon TEXT NOT NULL,                       -- auto | thu_cong
    dich_id TEXT NOT NULL, dich_phien_ban INTEGER NOT NULL, dich_json TEXT NOT NULL,
    schema_id TEXT NOT NULL, chinh_sach TEXT NOT NULL,
    header_json TEXT, rows_json TEXT, so_dong INTEGER NOT NULL DEFAULT 0, payload_sha256 TEXT NOT NULL DEFAULT '',
    trang_thai TEXT NOT NULL, so_lan_thu INTEGER NOT NULL DEFAULT 0, thu_lai_sau REAL NOT NULL DEFAULT 0,
    chu_so_huu TEXT NOT NULL DEFAULT '', claim_token TEXT NOT NULL DEFAULT '',
    claim_luc REAL, gui_luc REAL, loi TEXT NOT NULL DEFAULT '', bien_nhan TEXT NOT NULL DEFAULT '',
    da_xoa_job INTEGER NOT NULL DEFAULT 0, tao_luc REAL NOT NULL, sua_luc REAL NOT NULL);
```

Trạng thái (`hang_doi_gui.trang_thai`) và chuyển trạng thái hợp lệ:

```
PENDING ──claim──▶ CLAIMED ──(kiểm tab/tiêu đề, chỉ ĐỌC)──▶ SENDING ──phản hồi hợp lệ──▶ SENT
   ▲  ▲               │  lỗi chắc chắn trước dispatch:                  │ lỗi sau dispatch / phản hồi lạ
   │  │               ├─ tạm thời (mạng, 429, 5xx khi ĐỌC) ─▶ RETRY_WAIT ─(hết hạn chờ)─▶ (claim lại)
   │  │               └─ cấu hình (tiêu đề, quyền, tab, principal) ─▶ BLOCKED_CONFIG
   │  └─ "Thử gửi lại" (người dùng, sau khi sửa) ◀─ BLOCKED_CONFIG / RETRY_WAIT quá hạn mức
   │                                                                    ▼
   └─ "Gửi lại — có thể trùng" (xác nhận riêng) ◀─────────────── UNKNOWN_DELIVERY ─▶ "Đã kiểm: đã có" ─▶ SENT
BLOCKED_REPORT: kết quả V2 lỗi / luật cũ — không có payload gửi được.  CANCELLED: người dùng huỷ (chưa SENDING).
Khởi động người gửi (giữ khoá): CLAIMED → PENDING (chưa dispatch); SENDING của chủ cũ → UNKNOWN_DELIVERY.
```

Thử lại tạm thời: tối đa 8 lần, chờ `min(60·2^n, 3600)` s; quá hạn mức → `BLOCKED_CONFIG` (lý do "quá số lần
thử"). Tạm dừng toàn bộ / tạm dừng một hồ sơ: người gửi bỏ qua, KHÔNG đổi trạng thái hay đích.

## 6. Thứ tự khoá toàn dự án (bổ sung «Quy ước khoá» của CLAUDE.md)

1. `data/bao_tri/cong.lock` — mutex của cổng bảo trì; giữ vài mili-giây, KHÔNG BAO GIỜ chờ khoá khác khi
   đang giữ (nên lấy được ở bất kỳ đâu mà không tạo vòng).
2. Lease của một việc (`data/bao_tri/viec_<uuid>.lock`) — giữ suốt việc (lô quét, lượt Watch, dựng kho,
   đồng bộ kênh, lô nguồn chung, một lượt gửi).
3. `data/tool.lock` (việc nặng — giữ nguyên quy ước cũ).
4. Khoá JSON `.timclip.lock` (ngắn — giữ nguyên `luu_tru`).
5. `data/hang_doi_gui.lock` — quyền làm người gửi (dài hạn trong tiến trình gửi).
6. Giao dịch SQLite — trong cùng; KHÔNG chờ khoá HĐH và KHÔNG gọi mạng khi đang mở giao dịch ghi.

Ngoại lệ có chủ đích: người gửi giữ (5) suốt đời tiến trình nhưng lấy lease (2) cho TỪNG lần gửi. Không thể
kẹt chéo vì mutex của cổng không bao giờ chờ khoá khác khi đang giữ, và lease là file mới không ai tranh.

## 7. Cập nhật Stable (PC2) — xem `docs/MANAGED_UPDATE.md` khi hoàn tất M3

Manifest JSON (khoá sắp xếp, UTF-8) gồm: `dinh_dang`, `ung_dung`, `kenh`, `phien_ban`, `commit`, `tree`,
`tao_luc`, `goi{ten,kich_thuoc,sha256}`, `nen_tang`, `python`, `runtime{lock_sha256}`, `du_lieu{lich_su,
tuong_thich_nguoc}`, `migration{tu_dong_an_toan}`, `launcher_toi_thieu`. Chữ ký Ed25519 tách rời
(`manifest.json.sig`). Không có hook shell tuỳ ý. Trạng thái journal: CHECKED → DOWNLOADING → VERIFIED →
STAGED → WAITING_IDLE → QUIESCED → BACKED_UP → MIGRATING → ACTIVATING → HEALTHCHECK → ACTIVE (hoặc
ROLLBACK / BLOCKED / QUARANTINED). Ghi nguyên tử = file tạm + `flush` + `os.fsync` + `os.replace`
(NTFS: MoveFileEx thay thế nguyên tử; Windows không fsync được thư mục — ghi rõ giới hạn).

## 8. Bootstrap PC2 và chuyển khỏi updater cũ

Bootstrap kit = `launcher.py` + khoá công khai tin cậy + hướng dẫn. Chạy một lần trên PC2: chọn installation
root/state root (không OneDrive/ổ mạng), tạo `installation.json` (UUID MỚI), cài release đầu tiên (đã xác
minh), tạo runtime tại đường dẫn cuối, ghi `TimClipPro.bat` mới, xuất XML Task Scheduler để XEM (không
đăng ký). PC2 bắt đầu với kho RỖNG và tự dựng. Clone/launcher cũ (nếu có) để nguyên tới khi pilot đạt.

## 9. Giới hạn đã biết (cập nhật khi xong từng milestone)

* Không exactly-once phía Google: UNKNOWN_DELIVERY là cơ chế xử lý mơ hồ, người dùng đối soát.
* Race đổi tên/xoá-tạo tab giữa lúc kiểm theo ID và lúc append (cùng tên) không loại trừ tuyệt đối —
  append của Sheets API nhận dải A1 theo TÊN; sau append kiểm `updatedRange` khớp tên tab của đúng ID.
* Hai PC cùng gửi một bảng: không có dedup toàn cục; khuyến nghị mỗi lịch Watch do một máy phụ trách.
* Không fsync được thư mục trên Windows; cam kết sống qua mất điện dựa trên `FlushFileBuffers` của file +
  thay thế nguyên tử của NTFS.
* (M2) Việc kẹt ở `SENDING` trong một tiến trình CÒN SỐNG (ví dụ ghi biên nhận lỗi vì DB bị khoá quá 30 s)
  chỉ thành `UNKNOWN_DELIVERY` ở lần người gửi giành quyền kế tiếp (khởi động lại app/Watch) — không bao
  giờ tự quay về `PENDING`.
* (M2) «Kiểm cấu hình (chỉ đọc)» chứng minh ĐỌC được bảng/tab/tiêu đề, KHÔNG chứng minh quyền ghi; lỗi
  quyền ghi chỉ lộ ra ở lần gửi thật (Google trả 403 → `BLOCKED_CONFIG`, không ghi gì).
* (M2) Kết quả lưu theo luật báo cáo cũ (trước V2) không được hàng đợi nhận (`BLOCKED_REPORT`) — cần quét
  lại để có ảnh chụp V2.
* (M2) Hành vi ĐỔI CÓ CHỦ ĐÍCH so với 6dc3f9d (ghi vào hướng dẫn vận hành):
  - Watch có `--sheet`/SHEET_LINK mà file khoá thiếu/sai → DỪNG lượt TRƯỚC khi quét (bản cũ quét + CSV rồi
    không gửi được, và video đó không bao giờ được gửi lại). Mã thoát 1 tới khi sửa khoá.
  - Chỉ kết quả QUÉT XONG (`ok`) mới lên Sheets — kể cả Watch `--dang-doc` (bản cũ gửi cả dòng «(LỖI: …)»).
  - Người dùng bản cũ bật «tự động gửi» trong app: sau nâng cấp mặc định «Chỉ lưu cục bộ» tới khi chọn hồ
    sơ đích (không tự bật gửi vì có khoá).
  - Không còn tự TẠO tab «KetQuaQuet» khi thiếu (bản cũ `add_worksheet`): thiếu tab → `BLOCKED_CONFIG`; tạo
    tab là thao tác riêng của người dùng.
* (M2) Watch giữ `tool.lock` trong lúc chờ gửi cuối lượt (tối đa `cho_gui_s`, mặc định 120 s); yêu cầu dừng
  (file DUNG / Ctrl+C) cắt ngang lúc chờ.

## 10. Trạng thái triển khai (checkpoint chi tiết: `D:\TimClipPro_ManagedRuntime\<vòng>\checkpoints\CHECKPOINT.md`)

**M1 — đường dẫn runtime + lược đồ v3 + hồ sơ đích** (commit `e341a1c`): `runtime_paths.py`,
`lich_su.PHIEN_BAN = 3` (chỉ thêm bảng; bản 6dc3f9d chạy được trên DB v3 — test chạy chính mã cũ),
`sheet_destinations.py` (hồ sơ + revision bất biến, binding khoá theo principal, `DichGuiChot`, nhập link
cũ idempotent). Engine/CLI dùng `RuntimePaths` (sửa AUD-004: CLI/Watch nay theo `TIMCLIP_DATA_DIR`).

**M2 — outbox lưu bền + tích hợp** (commit kế tiếp `e341a1c`):

| Phần | Nơi | Ghi chú |
|---|---|---|
| Outbox, người gửi, transport gspread | `outbox.py` | Thay `sheet_delivery.py` (đã xoá cùng test của nó; bất biến tương đương ở `tests/test_outbox*.py`). Phân loại lỗi theo KIỂU ngoại lệ; timeout (10 s, 60 s); một `append_rows` RAW (tiêu đề + dòng khi trang trống). |
| Xếp hàng cùng giao dịch | `Engine.save_job` → `_xep_hang_gui` | Chỉ kết quả `ok`; V2 lỗi / luật cũ / dựng dòng lỗi → `BLOCKED_REPORT` không payload; không có dòng → không tạo việc. `danh_thuc` SAU commit. |
| Ghim | `ScanJobController.start(y_dinh_gui=…)` → `scan_iter(y_dinh_gui=…)` (bản sao job); Watch/CLI: `Engine.ghim_y_dinh_gui` | Đổi chọn trên UI chỉ áp cho lượt SAU; banner «Lượt đang chạy gửi A; lựa chọn B dùng cho lượt tiếp theo». |
| Xoá lần quét | `Engine.delete_job` | `BEGIN IMMEDIATE`; CLAIMED/SENDING/UNKNOWN → `LoiXoaJob`; SENT → tombstone; ô xác nhận gắn mã lần quét, tự bỏ chọn sau khi xoá. |
| Kiểm cấu hình chỉ đọc | `outbox.kiem_cau_hinh` → `CongGspread.kiem`, `sheets.kiem_tieu_de_nghiem_ngat`, `SheetsExporter.kiem_tra` | Không tạo tab, không chèn tiêu đề; tab theo mã đã chốt / mã ghim (đối chiếu tên) / tên. |
| Tab định danh | `sheet_destinations._chot_tab`/`tab_da_chot`, bảng `dich_gui_tab_chot`; `NguoiGui._tab_gui`, `NguoiGui._bat_dau_gui` | Mã tab chốt theo revision ở request ghi đầu (từ audit f4d3cb7: TRONG giao dịch `SENDING`, trước khi phát — không còn chốt sau SENT); link cũ = tab «KetQuaQuet» (bỏ gid của link); hồ sơ có gid đối chiếu tên ở lần gửi đầu. Sửa hồ sơ cùng bảng/tab → revision mới kế thừa mã đã chốt. |
| Rà soát độc lập M2 | `tests/test_outbox_ra_soat.py` + test UI/CLI | 1 P1 + 8 P2 + 12 P3 đã kiểm trên mã; mọi phát hiện có giá trị được tái hiện bằng test ĐỎ trước khi sửa. |
| Giao diện | `ui_gui_sheets.py` + `app.py` | Bộ chọn đích cạnh nút Bắt đầu (mỗi tab quét một trạng thái riêng, có «Chỉ lưu cục bộ»), tab «📤 Gửi Google Sheets» (hàng đợi + thao tác theo trạng thái, hồ sơ, binding khoá, nhập link cũ), «Gửi thêm (thủ công)» dựng lại payload TỪ LỊCH SỬ. Bỏ nút «Đẩy lên Google Sheets» (gửi lại cả lô bằng link hiện tại — H14). |
| Watch | `watch.py` | Phân giải đích TRƯỚC khi liệt kê/quét (lỗi cấu hình → dừng trước khi quét); gửi qua outbox bằng người gửi nền; cuối lượt chờ CÓ HẠN (`cho_gui_s`, mặc định 120 s); bỏ gửi đồng bộ và «gửi lại cả lô cuối lượt». |
| CLI | `cli.py` | `--destination` (hồ sơ) hoặc `--sheet`/`SHEET_LINK` (nhập link cũ có kiểm soát, idempotent; hai nơi khác nhau → lỗi rõ), `--cho`; lệnh `dich` (liệt kê hồ sơ + binding khoá) và `gui` (chạy người gửi tới khi hết việc tới hạn hoặc hết `--cho` giây). Mã thoát 1 khi còn việc bị chặn vì cấu hình hoặc không rõ đã gửi. |

**M3 — cổng bảo trì + cập nhật Stable + launcher + health check** (commit kế M2): `maintenance_gate.py` nối vào
mọi loại việc (lô quét, tác vụ nền, Watch, nguồn chung, kho, CLI, MỖI lần gửi Sheets); `managed_update.py`
(manifest ký Ed25519, chính sách Stable, giải nén an toàn, nhật ký + khôi phục mất điện 14 điểm, health,
quay mã về last-good, cách ly, hoãn); `health_check.py`; `launcher.py`; `ui_cap_nhat.py`; cứng hoá đường cũ
(`cap_nhat.py` chỉ tag `v<số>`, dev_mode, `.bat` H15, `kiemtra.bat` H16). Chi tiết: `docs/MANAGED_UPDATE.md`.
Kiểm đột biến: cổng 7/7, M2+M3 21/21 bị bắt (2 đột biến sống sót lần đầu → thêm test fencing + kiểm tên zip).

**M4 — bootstrap + công cụ phát hành + vận hành**: `bootstrap.py` (PC2, định danh mới, launcher + khoá tin cậy,
`.bat`, XML lịch XEM TRƯỚC không đăng ký, cài bản đầu qua bộ cập nhật), `release_tool.py` (build từ git tree,
ký thử, verify như PC2, publish CHỈ in lệnh, lock từ runtime đã nghiệm thu), `launcher.py doctor`, sửa hồ sơ
đích trên UI (khoá, link/tab), `requirements-lock.txt` UTF-8 tạo lại từ runtime đã nghiệm thu (thay bản UTF-16
lệch — H11), `launcher-lock.txt`. Mô phỏng HAI cài đặt end-to-end (`tests/test_hai_may_gia_lap.py`, -m slow).
Hướng dẫn: `docs/HUONG_DAN_PC2.md`; pilot: `docs/KE_HOACH_PILOT_PC2.md`.

**M5 — sửa theo rà soát đối nghịch M3+M4** (0 P1 · 7 P2 · 16 P3, mọi phát hiện đã kiểm trên mã; mỗi sửa có
test ĐỎ trước — `tests/test_*_ra_soat.py`, `tests/test_outbox_ban_cu.py`):

| # | Phát hiện | Sửa |
|---|---|---|
| A | Quay lại về `last_good` có thể là CHÍNH bản mới (last_good ghi trước ACTIVE; `con_tro_cu` không dùng) | Quay về `con_tro_cu`, không bao giờ về bản lỗi; ACTIVE trước last_good, khôi phục ghi bù |
| B | Timeout/OSError/CalledProcessError/sqlite3.Error thoát khỏi updater/launcher → app không mở được | Health không chạy được = không đạt; lỗi lạ → LOI/LoiCapNhat; lock chưa băm + migration lỗi + runtime lỗi lặp → cách ly |
| C | Người gửi Sheets của app CŨ giữ quyền mãi sau khi bản mới kích hoạt | `BanCu(DangBaoTri)`: nhường quyền + dừng hẳn; cảnh báo nổi ở app cũ |
| D | Cờ «tự động an toàn» luôn bật mặc định; máy mới bị coi là migration | Cờ mặc định TẮT + cờ CLI; DB chưa có = tạo mới; cần duyệt báo ngay lúc prepare |
| E | Bootstrap dở dang không làm lại được (`.bat` ASCII với đường dẫn có dấu; Python gốc thiếu cryptography) | Hai giai đoạn (Python gốc → môi trường launcher → chạy lại); `.bat` ASCII `%~dp0`; định danh + launcher.json ghi cuối, làm tiếp được |
| F | docopt 0.6.2 không có wheel → PC2 `--only-binary` không cài được | Wheel kèm release (`--wheel-kem`, băm trong lock) + `--find-links` |
| G | Updater cũ: commit có cả `v…` nhẹ và `stable-…` → «cập nhật» lặp (mã 10) | So `v<số>` + so commit; quy tắc gắn tag cho PC1 production (KE_HOACH_PILOT) |

P3 đã sửa: kiểm chính sách trước sao lưu/rút cổng; hoãn bấm trong lúc chờ rảnh; chữ ký sai/thiếu gói không
cách ly + `update bo-cach-ly`; ghi JSON thử lại khi bị khoá đọc; doctor ⚠️ cho lượt lỗi/dở dang + so con trỏ
với manifest; Ctrl+C không giết app; health theo dòng đánh dấu + cwd ngoài release; bỏ biến PYTHON* nguy
hiểm, `-P`; `vameta`/`dondep` vào cổng; release_tool quét lock + mẫu bí mật mới + chặn `.py` bị loại + khoá ký
có mật khẩu; bootstrap từ chối thư mục trong bản clone git / có dữ liệu cập nhật cũ; không xoá runtime đang
dùng; `don_ban_cu` đọc con trỏ nghiêm ngặt; fsync file giải nén; GitHub kiểm host từng bước chuyển hướng;
app vẫn mở khi bộ cập nhật không dựng được. Còn lại (giới hạn, `docs/MANAGED_UPDATE.md` §8): chưa có đường
nâng cấp launcher, chưa có lệnh duyệt WAITING_APPROVAL, runtime pip không kiểm lại, `data/dev_mode` là opt-in.

**Rà soát lại commit sửa 908d946** (chỉ đọc): A, B, D, E, F, G xác nhận đúng; C sửa chưa trọn — N1 (P2): người
gửi của bản cũ nhường quyền rồi KHOÁ CHẾT, bản mới hỏng health quay về bản này thì app đang mở không gửi Sheets
nữa (đúng bước diễn tập quay lại của pilot). Sửa (M5b): nhường quyền nhưng vẫn theo dõi, lấy lại quyền khi bản
này lại đang kích hoạt. P3 sửa cùng: launcher không mở bản chưa qua health khi khôi phục lỗi giữa lúc kích hoạt
(N2); lỗi có thể tạm thời (health/migration không chạy được, CSDL bị khoá, quá hạn) quay về ngay nhưng chỉ cách
ly sau 3 lần, lỗi vận chuyển khi tải manifest không cách ly (N3); chưa có lịch sử thì không migration (N4);
`.bat` tuyệt đối khi đường dẫn không dấu (N5); cài lần đầu bị cắt ở HEALTHCHECK thì kiểm ngay (N6); doctor
⚠️ cho WAITING_IDLE (N7); app chỉ bảo «mở lại» khi bản mới đã qua health (N8).
Kiểm lại riêng N1–N8 (chỉ đọc, 34a0e80): xác nhận cả 8, không P1/P2 mới. P3 còn lại sửa (M5c): nhật ký hỏng
lúc mở → chỉ mở khi con trỏ trùng bản đã chốt; ghi bộ đếm lỗi hỏng vẫn quay về; health chỉ «tạm thời» khi CSDL
bị khoá là lỗi duy nhất; hướng dẫn CapNhat.bat khi chưa có bản kích hoạt; `update recover` in rõ trạng thái.
Kiểm đột biến toàn bộ (62) trên dfdce2e: 58 bị bắt; 4 sống sót — 2 do kế hoạch gộp lấy nhầm bản cũ (tên test đổi
ở M5a; mục fencing lấy bản M3 chưa sửa, bản chạy lại M3 đã bắt), 1 do test Ctrl+C để `KeyboardInterrupt` lọt ra
(pytest ngắt CẢ phiên thay vì báo đúng test hỏng), 1 «ghi last_good trước ACTIVE» tương đương VỀ AN TOÀN sau M5b
(quay lại không còn dựa vào thứ tự ghi). Sửa (M5d — chỉ test, chú thích, tài liệu): test Ctrl+C báo đúng test; test
khoá bất biến «last_good chỉ trỏ bản mới khi nhật ký đã ghi bền ACTIVE»; chú thích `_kiem_sau_kich_hoat` và bảng
khôi phục `MANAGED_UPDATE.md` §5 khớp mã.

**Audit độc lập `f4d3cb7` (08/10/2026) — NO-GO pilot dữ liệu thật vì 2 P1; sửa trên nhánh
`fix/managed-runtime-audit`** (tạo từ đúng `f4d3cb7`; mỗi kịch bản của audit tái hiện bằng test ĐỎ trước khi sửa —
reproducer gốc của reviewer không đi kèm nên đã viết lại thành test):

| # | Phát hiện (đã tái hiện trên mã) | Sửa | Test |
|---|---|---|---|
| MR-P1-01 | `bootstrap.kiem_truoc` chỉ chặn hai root BẰNG nhau → nhận `state = <cài đặt>\staging\state`; `CapNhat.phuc_hoi()` (nhật ký CHECKED) hay `chuan_bi()`→`ap_dung()` gọi `_don_staging` → `rmtree(staging)` xoá `lichsu.db` + `installation.json`. Cùng lớp: `don_ban_cu`, runtime/release dở dang; thư mục nguồn phát hành nằm trong staging | Hai root TÁCH BIỆT (`runtime_paths.ly_do_bo_cuc`: không bằng, không cha/con; so dạng chữ + `realpath` qua junction/symlink, `commonpath` không theo tiền tố chuỗi). Kiểm ở bootstrap (trước khi ghi), `CaiDat.__post_init__` (launcher/UI/bootstrap; mỗi lượt cập nhật kiểm lại trong `_giu_quyen`), và `CaiDat.kiem_xoa` NGAY TRƯỚC mọi rmtree (`CapNhat._xoa_cay`, `don_ban_cu`); nguồn phát hành trong vùng updater bị từ chối. Cấu hình cũ không an toàn: dừng có thông báo «Bố cục thư mục», không tự di chuyển/xoá (`HUONG_DAN_PC2.md` §9) | `tests/test_bo_cuc_thu_muc.py` |
| MR-P1-02 | `truoc_khi_gui` chỉ COMMIT `SENDING`; mã tab chỉ chốt SAU `SENT` và lỗi chốt bị `suppress` → hồ sơ theo tên (gồm link cũ): UNKNOWN rồi «Gửi lại» sau khi tab đổi tên + tab mới cùng tên → payload cũ vào tab MỚI; SENT + lỗi chốt → việc kế cùng revision vào tab mới | Chốt mã tab (lần đầu thắng) TRONG CÙNG giao dịch CLAIMED→`SENDING` (`NguoiGui._bat_dau_gui`, fencing `claim_token`); chốt lỗi / mã đã chốt ≠ tab vừa tìm / tab ≠ mã của hồ sơ / mất claim → rollback, KHÔNG phát request. Bỏ chốt sau SENT. Biên nhận phải khớp ĐÚNG mã vừa chốt (cả hồ sơ theo tên). Việc ĐÃ phát (`gui_luc`) mà không có mã nào (dòng do bản cũ để lại) → không gửi lại theo tên (`gui_lai_co_the_trung` từ chối, người gửi chặn), vẫn «Đã có trên Sheet»/huỷ được. Giao diện việc KHÔNG RÕ hiện «Tab đích đã ghim: mã …» | `tests/test_ghim_tab_truoc_khi_gui.py` |

Không cần migration: nhánh mới chưa triển khai ở đâu (production PC1 vẫn 6dc3f9d, chưa có outbox). Các «gap vận
hành» của audit (§5: lịch cập nhật chỉ `prepare`, `InteractiveToken`/`PT6H`, bộ kit mẫu) là quyết định của
pilot — ghi ở `docs/KE_HOACH_PILOT_PC2.md` (bước 14 + 4 quyết định), không đổi hành vi lịch trong vòng sửa này.
