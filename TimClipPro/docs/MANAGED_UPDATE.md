# Cập nhật Stable có quản lý (PC2) — hợp đồng

Mã: `managed_update.py` (bộ cập nhật), `maintenance_gate.py` (cổng bảo trì), `health_check.py` (kiểm sức
khoẻ release, chạy bằng runtime của chính release), `launcher.py` (điểm vào ổn định, nằm ngoài release).
Test: `tests/test_managed_update.py`, `tests/test_maintenance_gate.py`, `tests/test_health_check.py`,
`tests/test_launcher.py`, các test rà soát M5 (`tests/test_managed_update_ra_soat.py`,
`tests/test_launcher_ra_soat.py`, `tests/test_outbox_ban_cu.py`), audit-fix `tests/test_bo_cuc_thu_muc.py` —
artifact TỔNG HỢP ký bằng khoá thử sinh lúc chạy, không mạng.

## 1. Luồng

```
PC1: commit đã test → release_tool build (git tree chính xác) → ký manifest (khoá phát hành)
     → CHỦ DỰ ÁN DUYỆT → tạo GitHub Release (tag stable-X.Y.Z, không draft/pre-release)   ← bước có duyệt
PC2: launcher update prepare  (tải manifest+chữ ký → XÁC MINH → tải gói → băm → giải nén an toàn
                               → kiểm từng file → runtime tại đường dẫn cuối → health staging) = STAGED
     launcher update apply    (rút cổng → chờ rảnh CÓ HẠN → backup → migration tự động an toàn
                               → đổi con trỏ current → health sau kích hoạt → ghi ACTIVE → last_good) = ACTIVE
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

**Hai thư mục TÁCH BIỆT (audit độc lập f4d3cb7, MR-P1-01).** Bộ cập nhật được quyền xoá/thay toàn bộ
`releases/`, `environments/`, `update_state/`, `staging/`. Bản f4d3cb7 chỉ chặn hai root BẰNG nhau, nên
`state = <cài đặt>\staging\state` được bootstrap chấp nhận rồi bị `_don_staging` xoá sạch (lịch sử + định danh).
Nay `installation_root` và `state_root` không được trùng, không cái nào nằm trong cái kia — so cả dạng CHỮ
(không phân biệt hoa/thường) lẫn dạng THẬT (`realpath`: junction/symlink/tên 8.3), bằng `commonpath` (không
theo tiền tố chuỗi). Kiểm ở ba tầng: `bootstrap.kiem_truoc` (trước khi ghi byte nào), `CaiDat` (mọi nơi dựng:
launcher, giao diện, bootstrap; mỗi lượt cập nhật kiểm lại), và `CaiDat.kiem_xoa` NGAY TRƯỚC mọi `rmtree` của
updater (`CapNhat._xoa_cay`, `don_ban_cu`): đích phải thuộc vùng updater, không chồng state root, không chứa
thư mục nguồn phát hành (`--nguon-thu-muc` cũng bị chặn nếu nằm trong vùng updater). Cấu hình cũ không an
toàn (launcher.json bị sửa tay): launcher/doctor/giao diện báo «Bố cục thư mục» và DỪNG — không tự di
chuyển, không xoá gì (`HUONG_DAN_PC2.md` §9). Test: `tests/test_bo_cuc_thu_muc.py`.

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
| con trỏ đã đổi / HEALTHCHECK | rút cổng, chạy lại health: đạt → ACTIVE; lỗi → quay mã về con trỏ TRƯỚC (`con_tro_cu` của nhật ký, không bao giờ chính bản lỗi) — lỗi tất định cách ly ngay, lỗi có thể tạm thời cách ly ở lần thứ 3; không rảnh được → tạm về con trỏ trước (không cách ly), giữ STAGED; cài lần đầu (không có bản trước) → kiểm health ngay |
| ROLLBACK | hoàn tất quay lại; cách ly theo quyết định đã ghi trong nhật ký (`cach_ly_khi_quay_lai`) |
| ACTIVE (chưa kịp ghi last_good) | ghi bù last_good — không kiểm lại health (last_good chỉ trỏ bản nhật ký đã ghi ACTIVE) |

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
  `tu_dong_an_toan` (⇒ `tuong_thich_nguoc`); không thì WAITING_APPROVAL. Schema trên máy mới hơn bản phát hành →
  BLOCKED. Cả hai được kiểm NGAY lúc `prepare` và trước khi rút cổng — không tải gói, không sao lưu, không rút
  cổng cho một bản sẽ không được áp dụng. Chưa có `lichsu.db` (máy mới, hoặc app chưa mở lần nào —
  `phien_ban_db() is None`) KHÔNG migration gì: app tạo lược đồ bằng chính mã mới khi mở lần đầu. `release_tool.py build` để hai cờ TẮT mặc định — người
  phát hành khai `--tu-dong-an-toan --tuong-thich-nguoc` cho bản có nâng lịch sử đã đánh giá.
* Lược đồ hiện hành: `lichsu.db` phiên bản 4 (chỉ thêm cột `hang_doi_gui.gui_worksheet_id`, tái audit 78ba20c). PC2
  cài mới không qua migration nào. DB v3 do candidate cũ (f4d3cb7/78ba20c) tạo — chưa có trên máy thật: mã v3 chạy
  được trên DB v4 (`tests/test_lich_su_v4.py`), nhưng nâng tự động v3→v4 chỉ khi người phát hành khai hai cờ trên
  sau khi đánh giá; health của một release v3 trên DB v4 báo «schema quá mới». Pilot không nhập state v3.
* Migration lỗi → giữ bản hiện tại; lỗi tất định (migration chạy và báo lỗi) → cách ly ngay; lỗi có thể tạm
  thời (quá hạn, CSDL bị khoá — chỉ khi đó là lỗi DUY NHẤT) → áp dụng lại lần sau, cách ly ở lần thứ 3 (không
  lặp «sao lưu + rút cổng + migration» mãi).
* Nhật ký cập nhật HỎNG lúc mở app: launcher chỉ mở khi con trỏ hiện tại trùng bản đã chốt (last_good), ngược
  lại từ chối (có thể là bản chưa qua health).
* Rollback chỉ quay MÃ (con trỏ) về con trỏ TRƯỚC kích hoạt ghi trong nhật ký (`con_tro_cu`; không bao giờ về
  chính bản lỗi, kể cả khi `last_good` đã trỏ sang nó) — **không bao giờ tự khôi phục DB**: việc đã gửi không
  thể quay về chờ gửi, kết quả quét sau backup không mất. Backup chỉ để khôi phục thủ công có duyệt.
* Health check KHÔNG chạy được (quá hạn, thiếu python của runtime, CSDL bị khoá, lỗi lạ) = KHÔNG ĐẠT → quay
  lại NGAY; vì có thể chỉ tạm thời nên chỉ cách ly sau `SO_LAN_LOI_TOI_DA` (3) lần (migration bị khoá/quá hạn
  cũng vậy). Health CHẠY và báo lỗi = tất định → cách ly ngay. Không bao giờ thoát khỏi bộ cập nhật giữa chừng. Kết quả đọc từ dòng `TIMCLIP_HEALTH_KET_QUA {json}`; cwd ở
  state root. Thứ tự chốt: nhật ký ACTIVE rồi mới `last_good` (khôi phục ở ACTIVE ghi bù last_good).
* Cách ly: chỉ khi nội dung ĐÃ KÝ sai (chính sách manifest, zip độc hại, danh sách file, lock chưa băm/không
  khớp), health/migration báo lỗi, hoặc lỗi có thể tạm thời (tải/dựng runtime, health/migration không chạy
  được) lặp `SO_LAN_LOI_TOI_DA` lần. Chữ ký sai / thiếu gói / lỗi vận chuyển (host, kích thước) khi tải manifest
  chỉ bỏ qua lần đó. Bỏ cách ly: `launcher.py update bo-cach-ly X.Y.Z`.
* Khôi phục lỗi khi nhật ký đang giữa lúc kích hoạt (kể cả một updater khác đang kiểm bản mới) → launcher KHÔNG
  mở app (con trỏ có thể là bản chưa qua health) — đợi rồi mở lại. Cài lần đầu bị cắt ở HEALTHCHECK → lần mở sau
  kiểm health ngay, không chờ rảnh (không có bản nào khác để bảo vệ).

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

* Windows không fsync được thư mục: cam kết dựa trên `FlushFileBuffers` của file (file giải nén, manifest,
  JSON trạng thái) + thay thế nguyên tử NTFS. File do `pip` ghi vào runtime không được fsync/kiểm lại sau khi
  cài (health check ở staging là lần kiểm runtime).
* `os.replace` trên Windows bị từ chối khi tiến trình khác đang MỞ file đích (giao diện/doctor đọc trạng
  thái) — ghi trạng thái thử lại có hạn (~2,75 s) rồi mới báo lỗi.
* Runtime production cần `requirements-lock.txt` CÓ BĂM (`--require-hashes --only-binary=:all:`); sinh băm
  cần mạng — bước chuẩn bị phát hành có duyệt, chưa chạy trong vòng này. **docopt 0.6.2 không có wheel trên
  PyPI** → wheel dựng từ sdist đã đối chiếu băm, kèm release (`build --wheel-kem`, PC2 dùng `--find-links`).
* Launcher cần Python có `cryptography` (môi trường riêng của launcher tạo lúc bootstrap). Bộ cập nhật không
  dựng được (khoá tin cậy hỏng, thiếu thư viện…) chỉ chặn CẬP NHẬT: app/Watch vẫn mở bản đang kích hoạt nếu
  nhật ký không dừng giữa lúc kích hoạt.
* Chưa có đường nâng cấp chính launcher (file trong `launcher/` cố định từ lúc bootstrap; `launcher_toi_thieu`
  trong manifest chặn bản cần launcher mới hơn) — bản cần launcher mới = bootstrap lại có kế hoạch.
* WAITING_APPROVAL chưa có lệnh duyệt — bản cần migration chưa đánh giá chỉ được áp dụng qua một quy trình
  riêng có duyệt (hoặc phát hành lại với cờ đã đánh giá).
* App đang mở chạy mã CŨ tới khi người dùng mở lại; sau khi bản mới kích hoạt, cổng của bản cũ từ chối việc
  mới, người gửi Sheets của bản cũ NHƯỜNG quyền cho bản mới (Watch/CLI/app mới gửi tiếp) nhưng vẫn theo dõi —
  bản mới hỏng health, quay về bản này thì nó lấy lại quyền và gửi tiếp. Trang hiện cảnh báo nổi «đóng và mở
  lại» khi bản mới đã qua health; đang kiểm thì báo «đang hoàn tất cập nhật».
* Chưa kiểm trên PC2 thật (UNVERIFIED_ON_PC2); chưa gọi GitHub thật (NOT_RUN) — nguồn GitHub tự theo chuyển
  hướng, kiểm host TRƯỚC mỗi request.
