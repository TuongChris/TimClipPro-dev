# Kế hoạch pilot PC2 có kiểm soát

Mỗi bước có điều kiện ĐẠT và điểm DỪNG. Bước đánh dấu **[DUYỆT]** cần chủ dự án đồng ý rõ ràng trước khi làm.
Không bước nào đụng PC1 production (`Tool_Quet`, đang ở 6dc3f9d) trừ khi ghi rõ.

| # | Bước | Cách làm | ĐẠT khi | DỪNG nếu |
|---|---|---|---|---|
| 0 | Duyệt mã | Kiểm toán độc lập vòng 1 (`f4d3cb7`, 08/10/2026): NO-GO vì 2 P1 (MR-P1-01 state root lồng trong vùng updater bị xoá; MR-P1-02 mã tab ghim sau SENT) → sửa `78ba20c`. Tái audit `78ba20c`: hai P1 cũ đóng; phát hiện mới MR-R2-P1-01 (transport ghi theo TÊN A1) + MR-R2-P2-01 (UNKNOWN của bản cũ bị «hợp thức hoá») → sửa trên nhánh `fix/managed-runtime-reaudit` → tái audit lần nữa + gói audit nguồn mới | Không còn P1/P2 mở | Có P1 |
| 1 | **[DUYỆT]** Khoá phát hành thật | Sinh cặp Ed25519 trên PC1 (ngoài repo, khoá riêng KHÔNG đưa lên máy chủ/OneDrive), ghi `trusted_keys.json` | Khoá riêng cất an toàn, có bản dự phòng | Khoá riêng lộ |
| 2 | **[DUYỆT]** Lock có băm | Trên PC1 có mạng: `pip download --only-binary=:all: --no-deps -d wheelhouse` theo `requirements-lock.txt` + `launcher-lock.txt`. **docopt 0.6.2 KHÔNG có wheel trên PyPI** (chỉ sdist — đã xác nhận qua bộ nhớ đệm wheel của pip trên PC1): tải sdist, đối chiếu băm sdist với trang PyPI, `pip wheel --no-deps` từ sdist đó vào `wheelhouse`. Rồi `release_tool.py lock --wheelhouse wheelhouse` | Mọi dòng có `--hash=sha256` | Thiếu wheel Windows / băm sdist lệch |
| 3 | Bộ bootstrap | Đóng gói launcher + `bootstrap.py` + `trusted_keys.json` thật + 2 lock | Kit kiểm lại bằng `release_tool.py verify` | — |
| 4 | **[DUYỆT]** Sao lưu PC2 | Nếu PC2 đang có bản cũ (clone + `.bat`): sao lưu thư mục + `data\` sang ổ khác, ghi lại bản đang chạy | Bản sao mở được | Thiếu chỗ trống |
| 5 | **[DUYỆT]** Tắt đường cũ trên PC2 | Gỡ/đổi tên lịch Task Scheduler cũ chạy `ChayMayPhu.bat`/`GiamSat.bat`; KHÔNG xoá clone cũ | Không còn lịch cũ chạy | Lịch cũ vẫn chạy |
| 6 | **[DUYỆT]** Phát hành Stable thử | `release_tool.py build --commit <đã duyệt> --phien-ban 1.0.0 --wheel-kem wheelhouse\docopt-0.6.2-py2.py3-none-any.whl` (máy PC2 mới: KHÔNG cần cờ migration; bản sau có nâng lịch sử thì quyết định `--tu-dong-an-toan --tuong-thich-nguoc` hay để PC2 chờ duyệt) → `sign --hoi-mat-khau` → `verify` → `publish` (in lệnh) → chủ dự án tự chạy `gh release create stable-1.0.0 …` (repo phù hợp, không draft/pre-release; commit không mang tag `v…` nhẹ — xem cuối trang) | `verify` ĐẠT; tag mới, không gắn lại | Sai chữ ký/băm |
| 7 | Bootstrap PC2 | Theo `HUONG_DAN_PC2.md` §2, thư mục MỚI, state root MỚI hoàn toàn — KHÔNG chép `lichsu.db`/state từ máy dev hay từ candidate cũ (f4d3cb7/78ba20c, lược đồ v3). TRƯỚC đó thử một lệnh cố ý sai: `--state D:\TimClipPro\staging\state` (lồng trong thư mục cài đặt) | Lệnh sai bị từ chối «Bố cục thư mục…», KHÔNG tạo thư mục/file nào; lệnh đúng (ngang hàng) → `doctor` toàn ✅ | Lệnh sai được chấp nhận / bất kỳ ❌ |
| 8 | **[DUYỆT]** Hai bảng nhỏ | Tạo 2 Sheet thử (không phải bảng khách hàng), 2 hồ sơ đích, chia sẻ cho tài khoản dịch vụ; «Kiểm cấu hình» | Đọc được cả hai | Không đọc được |
| 9 | Quét thử + ghim | Lô 2–3 video công khai: lô 1 → bảng A; giữa lô đổi chọn sang B; lô 2 → B | Dòng lô 1 chỉ ở A, lô 2 chỉ ở B; hàng đợi «✅ Đã gửi» | Dòng lạc bảng |
| 10 | Restart/outbox | Bật «Tạm dừng toàn bộ», quét 1 video, tắt app (đóng cửa sổ), mở lại, bỏ tạm dừng | Việc vẫn còn và gửi đúng 1 lần | Mất việc / trùng |
| 10b | Tab ghim theo MÃ | Trên bảng thử A (hồ sơ tạo từ link KHÔNG có `#gid`, tức theo tên): gửi 1 lần → đổi tên tab `KetQuaQuet` thành `Cu`, tạo tab mới tên `KetQuaQuet` → quét + gửi lần nữa; rồi XOÁ tab `Cu` → gửi lần ba. Thêm: một tab MỚI trống (26 cột) làm đích của bảng B; một dòng có tiêu đề video bắt đầu bằng `=`. Đây là lần ĐẦU ghi bằng `batchUpdate`/AppendCells + đọc theo mã trên Google THẬT (tái audit 78ba20c — trước đó chỉ kiểm theo tài liệu công khai + mô hình HTTP giả) | Lần 2 vào tab `Cu` (mã cũ), không vào tab mới; lần 3 bị chặn «Không thấy tab đã ghim», tab mới không có dòng nào; tab trống: hàng tiêu đề + dòng ở hàng 1–2, đủ cột; số là số, chữ `=…` vẫn là chữ | Dòng rơi vào tab mới cùng tên / hàng tiêu đề thứ hai / ô thành công thức |
| 11 | **[DUYỆT]** Cập nhật lúc rảnh | Phát hành `stable-1.0.1` (thay đổi nhỏ) → `CapNhat.bat` khi đang quét (phải hoãn) → khi rảnh (phải áp dụng) | Hoãn khi bận; áp dụng khi rảnh; `doctor` ✅ | Đổi mã khi đang quét |
| 12 | Diễn tập quay lại | Bản `1.0.2` cố ý lỗi health ký bằng khoá phát hành, đặt trong một NGUỒN PILOT RIÊNG (thư mục `--nguon-thu-muc` của một cài đặt thử, hoặc repo thử) — KHÔNG đưa vào feed Stable dùng chung (máy khác sẽ tải nó) | Tự quay về 1.0.1, 1.0.2 bị cách ly, lịch sử/hàng đợi (kể cả việc đang chờ gửi) nguyên vẹn | Mất dữ liệu / bản lỗi lọt vào feed chung |
| 13 | **[DUYỆT]** Lịch Watch thật | Import `TimClipPro_GiamSat.xml` (thay mã hồ sơ), theo dõi 2–3 ngày | Log mỗi lượt OK | Lỗi lặp lại |
| 14 | **[DUYỆT]** Lịch cập nhật tự động | Chỉ sau khi chốt 4 quyết định ở mục dưới; diễn tập trọn chuỗi: lịch kích hoạt → `update prepare` → áp dụng an toàn (bận thì hoãn) → lần mở app/Watch kế dùng bản mới; thêm một lần khởi động lại máy (cold boot) theo đúng cách vận hành đã chọn | `update status` + `doctor` sau mỗi bước khớp mong đợi; không lượt nào bị cắt ngang | Áp dụng khi đang quét / lịch không chạy sau khởi động lại |

**Quyết định trước bước 14 (audit độc lập f4d3cb7 §5 — chưa phải lỗi, là việc pilot phải chốt):**

1. **Lịch cập nhật mới chỉ `prepare`.** XML mẫu `TimClipPro_CapNhat.xml` gọi `launcher.py update prepare` (tải +
   kiểm + stage), CHƯA áp dụng; `CapNhat.bat` chạy tay thì `prepare` rồi `apply`. Muốn PC2 tự lên bản không cần
   người trực: thêm bước `update apply` vào lịch (áp dụng vẫn qua cổng bảo trì — bận thì hoãn). KHÔNG dùng
   `CapNhat.bat` trong lịch (có `pause` khi lỗi → treo tới hết giờ giới hạn). Có XML không phải bằng chứng PC2 tự
   cập nhật.
2. **`LogonType=InteractiveToken`.** Lịch chỉ chạy khi tài khoản vận hành ĐANG đăng nhập. Muốn chạy sau khởi
   động lại mà chưa ai đăng nhập: chọn tài khoản + cách lưu mật khẩu (Task Scheduler) — cần duyệt riêng (đổi
   cấu hình bảo mật máy).
3. **`ExecutionTimeLimit=PT6H`.** Lượt Watch dài hơn 6 giờ sẽ bị Task Scheduler dừng (việc đang gửi thành KHÔNG
   RÕ). Đo thời lượng Watch thật trên PC2 rồi chọn giới hạn.
4. **Bộ kit mẫu `…_MAU_…` chỉ để kiểm từ chối** (khoá thử + lock chưa băm). Bộ kit triển khai cần khoá thật
   (bước 1), lock có băm (bước 2), wheelhouse, rồi bootstrap trên Windows sạch.

PC1: giữ bản legacy để phát triển. Trên các bản clone dùng để phát triển, tạo `data\dev_mode` để updater cũ
không bao giờ checkout tag (cần duyệt riêng nếu áp dụng lên `Tool_Quet` production). Chuyển PC1 production sang
bản mới là một quyết định riêng. `cap_nhat.py` CŨ (6dc3f9d, đang chạy trên PC1) không lọc tên tag — nó lấy tag
đầu tiên của `git tag --sort=-v:refname`; đã kiểm thực nghiệm 07/10/2026: `stable-…` luôn xếp SAU `v…` (chữ `s` < `v`)
nên không bị chọn khi repo còn tag `v…`. Bản mới lọc hẳn `v<số>`. Vì vậy: không bao giờ xoá các tag `v…` cũ và
không tạo tag nào bắt đầu bằng chữ đứng sau `v` (ví dụ `w…`, `x…`).

**Quy tắc thêm cho updater CŨ (đã tái hiện 08/10/2026):** updater cũ xác định «bản đang chạy» bằng
`git describe --tags --exact-match`. Commit mang CẢ tag `v…` NHẸ và tag `stable-…` (`gh release create` tạo tag
nhẹ) → describe trả `stable-…` → updater cũ thấy «khác `v…`» và «cập nhật» lặp mỗi lần chạy (mã 10:
`ChayMayPhu.bat` bỏ MỌI lượt Watch). Trong repo hiện có 9 tag `v…` nhẹ + 1 tag có chú thích. Cho tới khi PC1
production chạy updater mới (đã sửa: chỉ khớp `v<số>` + so commit): **KHÔNG gắn `stable-…` lên commit đang có
tag `v…` nhẹ**; nếu buộc cùng commit thì tag `v…` phải là tag CÓ CHÚ THÍCH (`git tag -a`) — describe ưu tiên tag
có chú thích (đã kiểm).
