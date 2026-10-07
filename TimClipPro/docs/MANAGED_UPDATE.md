# Cập nhật Stable có quản lý (PC2) — hợp đồng

Mã: `managed_update.py` (bộ cập nhật), `maintenance_gate.py` (cổng bảo trì), `health_check.py` (kiểm sức
khoẻ release, chạy bằng runtime của chính release), `launcher.py` (điểm vào ổn định, nằm ngoài release).
Test: `tests/test_managed_update.py`, `tests/test_maintenance_gate.py`, `tests/test_health_check.py`,
`tests/test_launcher.py` — artifact TỔNG HỢP ký bằng khoá thử sinh lúc chạy, không mạng.

## 1. Luồng

```
PC1: commit đã test → release_tool build (git tree chính xác) → ký manifest (khoá phát hành)
     → CHỦ DỰ ÁN DUYỆT → tạo GitHub Release (tag stable-X.Y.Z, không draft/pre-release)   ← bước có duyệt
PC2: launcher update prepare  (tải manifest+chữ ký → XÁC MINH → tải gói → băm → giải nén an toàn
                               → kiểm từng file → runtime tại đường dẫn cuối → health staging) = STAGED
     launcher update apply    (rút cổng → chờ rảnh CÓ HẠN → backup → migration tự động an toàn
                               → đổi con trỏ current → health sau kích hoạt → last_good) = ACTIVE
     launcher app|watch       (khôi phục nhật ký dở → chạy bản current)
```

PC1 (dev, legacy) không bao giờ bị updater này đụng tới: nó chỉ chạy trong một cài đặt managed có
`launcher.json`. `cap_nhat.py`/`.bat` cũ không có trong gói release (release_tool loại ra).

## 2. Bố cục cài đặt

```
<installation_root>/
    launcher/            launcher.py, managed_update.py, maintenance_gate.py, khoa.py,
                         launcher.json (state_root, nguon, python_goc), trusted_keys.json
    releases/<X.Y.Z>/    BẤT BIẾN: TimClipPro/…, MANAGED_RELEASE.json, RELEASE_FILES.json,
                         manifest.json, manifest.json.sig, .san_sang.json
    environments/<runtime_id>/   venv tạo TẠI CHỖ từ python_goc + lock có băm; .san_sang.json
    staging/             tạm của updater (dọn khi khôi phục)
    update_state/        journal.json, current.json, last_good.json, quarantine.json, updater.lock
<state_root>/            installation.json (UUID riêng mỗi máy), data/ (lichsu.db, kho, outbox,
                         bao_tri/), output/, secrets/, backups/, cache/pycache/
```

Tiến trình con chạy với `TIMCLIP_RUNTIME_MODE=managed`, `TIMCLIP_STATE_ROOT`, `PYTHONPYCACHEPREFIX` trong
state root (cây release đã ký không bao giờ có `__pycache__`), bỏ `TIMCLIP_DATA_DIR`/`SHEET_LINK`/`PYTHONPATH`.

## 3. Tin cậy và chính sách Stable

* Chữ ký Ed25519 (thư viện `cryptography`) trên ĐÚNG các byte `manifest.json`; file chữ ký
  `{"thuat_toan":"ed25519","key_id","chu_ky_b64"}`. Khoá công khai tin cậy cài lúc bootstrap
  (`trusted_keys.json`, `key_id = sha256(khoá)[:16]`), không bao giờ lấy từ manifest. Không có nhánh "bỏ
  chữ ký khi lỗi"; nguồn thư mục (USB/kiểm thử) cũng phải qua chữ ký.
* Chọn bản: tag `stable-X.Y.Z` (số nguyên, so theo số), không draft/pre-release, manifest ký nói
  `kenh=stable`, đúng phiên bản của tag, đúng `ung_dung`, đúng nền tảng; > bản đang chạy (không hạ bản, không
  cài lại); không bị cách ly; `launcher_toi_thieu` ≤ launcher hiện có.
* Gói: kích thước + SHA-256 khớp manifest; ZIP kiểm TRƯỚC khi ghi: đường dẫn tương đối an toàn (không `..`,
  tuyệt đối, ổ đĩa, `\`, tên thiết bị DOS, ký tự cấm, dấu chấm/khoảng trắng cuối), không symlink/kiểu đặc
  biệt, không trùng tên (không phân biệt hoa thường), không mã hoá, số file/tổng dung lượng/tỉ lệ nén có
  trần, dung lượng đếm theo byte THẬT khi ghi. Sau giải nén: cây khớp `RELEASE_FILES.json` (băm của nó nằm
  trong manifest ký) — đủ, đúng băm, không thừa, không reparse point.
* Lỗi chữ ký/chính sách/nội dung → **cách ly** phiên bản (không thử lại mỗi lần mở); tải hỏng băm → đếm,
  cách ly sau 3 lần; lỗi mạng/đĩa → giữ bản cũ, lần sau thử lại.
* `NguonGitHub`: một repo cố định, HTTPS, timeout (10 s, 60 s), chỉ host được phép (kể cả sau redirect),
  giới hạn kích thước. **Chưa gọi thật trong vòng phát triển (NOT_RUN).**

## 4. Manifest (định dạng 1)

`dinh_dang`, `ung_dung`, `kenh`, `phien_ban`, `commit`, `tree`, `tao_luc`,
`goi{ten, kich_thuoc, sha256, ds_file_sha256}`, `nen_tang` (`win_amd64`), `python` (`3.12`),
`runtime{runtime_id, lock_sha256}`, `du_lieu{lich_su, tuong_thich_nguoc}`, `migration{tu_dong_an_toan}`,
`launcher_toi_thieu`, `kho_dinh_dang`. Không có hook shell. `tu_dong_an_toan` BẮT BUỘC đi kèm
`tuong_thich_nguoc` (bản trước chạy được trên DB đã nâng) — manifest vi phạm bị từ chối.

## 5. Nhật ký và khôi phục

Trạng thái: CHECKED → DOWNLOADING → VERIFIED → STAGED → WAITING_IDLE → QUIESCED → BACKED_UP → (MIGRATING) →
ACTIVATING → HEALTHCHECK → ACTIVE; kết thúc khác: BLOCKED (schema quá mới, bản ứng viên hỏng sau gián
đoạn), WAITING_APPROVAL (migration chưa được đánh giá tự động an toàn), QUARANTINED (health lỗi). Mọi file
trạng thái ghi nguyên tử (tạm → flush → fsync → `os.replace`). File trạng thái HỎNG → dừng cập nhật, báo cần
kiểm tay (không bao giờ "đặt lại về mặc định"); bản current vẫn chạy được.

| Mất điện ở | Khi mở lại (`phuc_hoi`) |
|---|---|
| DOWNLOADING / VERIFIED | dọn `staging/` + `releases/*.tmp-*` → CHECKED, chuẩn bị lại |
| STAGED | không làm gì (release/runtime được KIỂM LẠI trước khi dùng) |
| WAITING_IDLE / QUIESCED / BACKED_UP / MIGRATING | cổng đã tự mở (khoá rút nhả theo tiến trình); con trỏ chưa đổi; migration là một giao dịch SQLite và tương thích ngược → STAGED, áp dụng lại khi rảnh |
| ACTIVATING (con trỏ chưa đổi) | STAGED |
| con trỏ đã đổi / HEALTHCHECK | rút cổng, chạy lại health: đạt → ACTIVE; lỗi → quay mã về last_good + cách ly; không rảnh được → tạm về last_good, giữ STAGED |
| ROLLBACK | hoàn tất quay lại + cách ly |

Kiểm thử: mất điện mô phỏng ở 14 điểm (`test_mat_dien_tung_diem_khoi_phuc_xac_dinh`) và giữa lúc ghi con trỏ.

## 6. Cổng bảo trì và thứ tự khoá

Nối vào MỌI loại việc: lô quét của app (`ScanJobController.start` — lease giữ suốt lô, trả ở luồng nền),
tác vụ nền của app (`chay_nen`: đồng bộ kênh, vá tên…), lượt Watch, lô nguồn chung, dựng/xoá kho và vá
metadata (`Engine.khoa_tac_vu` = lease RỒI `tool.lock`), lệnh CLI quét/đồng bộ kênh, và MỖI lần gửi Sheets
(người gửi lấy lease trước khi claim; cổng đang rút → không claim, việc đang bay → updater chờ).
`DangBaoTri` là một dạng `DangChayRoi` ("bận"): CLI thoát mã 2, Watch bỏ lượt, giao diện báo — không phải
sửa từng nơi. Bản CŨ (managed) không nhận việc mới khi `current.json` đã trỏ release khác
(`maintenance_gate.ly_do_ban_cu`, mặc định của mọi cổng) — việc đang chạy vẫn chạy xong.


Việc (lô quét, lượt Watch, dựng kho, đồng bộ kênh, một lần gửi Sheets) vào cổng: dưới mutex ngắn kiểm cờ rút
rồi tạo lease (khoá HĐH) giữ suốt việc. Updater bật cờ rút dưới CÙNG mutex → không race giữa "kiểm rảnh"
và "kích hoạt"; chờ CÓ HẠN; quá hạn thì hoãn, không giết việc. Cờ rút chỉ có hiệu lực khi updater còn giữ
`rut.lock` — updater chết thì cổng tự mở. Mutex không bao giờ chờ khoá khác khi đang giữ; lease là file mới
→ lấy được ở bất kỳ đâu mà không tạo vòng kẹt (`docs/MANAGED_RUNTIME_DESIGN.md` §6).

## 7. Migration, backup, rollback

* Backup trước khi đổi bất cứ gì: backup API của SQLite (bản sao nhất quán, `integrity_check`) + cấu hình
  nhỏ (`khos.json`, `cau_hinh.json`) vào `<state_root>/backups/<thời điểm>_truoc_<phiên bản>/`. Không sao
  lưu kho vân tay (release không chạm kho).
* Migration chạy bằng MÃ CỦA RELEASE MỚI (`health_check.py migrate`) khi cổng đã rút — tự động chỉ khi
  `tu_dong_an_toan`; không thì WAITING_APPROVAL. Schema trên máy mới hơn bản phát hành → BLOCKED.
* Rollback chỉ quay MÃ (con trỏ) — **không bao giờ tự khôi phục DB**: việc đã gửi không thể quay về chờ gửi,
  kết quả quét sau backup không mất. Backup chỉ để khôi phục thủ công có duyệt.

## 7b. Giao diện «ℹ️ Phiên bản và cập nhật»

Thanh bên của app (`ui_cap_nhat.py`): bản đang chạy, bản đang kích hoạt (khác → nhắc mở lại), lượt cập nhật
gần nhất (trạng thái, thời điểm, ghi chú), bản bị cách ly, việc đang chạy, cổng đang rút. CHỈ ĐỌC — không gọi
mạng, không chạy updater trong tiến trình app. Nút «⏸ Hoãn cập nhật 24 giờ» ghi `update_state/hoan.json`:
`update apply` giữ bản hiện tại tới hết hạn (tải/stage vẫn làm trước).

## 7c. Đường cũ (legacy — PC1, máy chưa chuyển) — cứng hoá và chuyển tiếp

* `cap_nhat.py` chỉ xét tag `v<số>` (so theo SỐ: v10 > v2.10); tag `stable-…` của kênh managed, `…-rc1`,
  `latest` không bao giờ bị nó chọn. Máy phát triển: tạo file `data/dev_mode` (hoặc đặt
  `TIMCLIP_DEV_MODE=1`) → updater cũ không fetch/checkout gì. Bản cài managed: updater cũ từ chối.
* `ChayTool.bat`/`ChayMayPhu.bat`: chuỗi cập nhật nằm TRỌN trong một khối `( … )` (cmd nạp cả khối vào bộ nhớ
  trước khi chạy — checkout đổi chính file `.bat` không làm cmd đọc nhầm byte của file mới); mã 11 xử lý
  TRONG khối mã ≥ 10 nên sau `pip` vẫn khởi động lại / bỏ lượt (H15). `pip` lỗi → dừng, không chạy mã mới
  bằng thư viện cũ.
* `kiemtra.bat`: bước AppTest chạy trên thư mục dữ liệu TẠM (H16 — trên `data/` thật nó nâng cấp lịch sử và có
  thể khởi động người gửi Sheets thật nếu còn việc chờ).
* Chuyển tiếp: PC1 đang chạy 6dc3f9d với `.bat` CŨ (còn lỗi H15). Bản kế tiếp KHÔNG đổi `requirements.txt`
  (`cryptography` đã có qua `constraints.txt`) → updater cũ trả mã 10, không phải 11 → lỗi H15 không kích hoạt.
  Nếu một bản sau ĐỔI requirements: cập nhật PC1 lần đầu bằng tay (đóng app → checkout tag → cài thư viện)
  thay vì để `.bat` cũ tự làm.
* Gói release managed KHÔNG chứa `.bat`, `cap_nhat.py`, test, tài liệu, Apps Script (`release_tool.py` loại).

## 8. Giới hạn đã biết

* Windows không fsync được thư mục: cam kết dựa trên `FlushFileBuffers` của file + thay thế nguyên tử NTFS.
* Runtime production cần `requirements-lock.txt` CÓ BĂM (`--require-hashes`); sinh băm cần mạng (tải wheel
  hoặc API PyPI) — bước chuẩn bị phát hành có duyệt, chưa chạy trong vòng này.
* Launcher cần Python có `cryptography` (môi trường riêng của launcher tạo lúc bootstrap).
* App đang mở chạy mã CŨ tới khi người dùng mở lại; sau khi bản mới kích hoạt, cổng của bản cũ từ chối việc
  mới và báo "mở lại ứng dụng".
* Chưa kiểm trên PC2 thật (UNVERIFIED_ON_PC2); chưa gọi GitHub thật (NOT_RUN).
