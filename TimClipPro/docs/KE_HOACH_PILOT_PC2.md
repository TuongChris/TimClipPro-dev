# Kế hoạch pilot PC2 có kiểm soát

Mỗi bước có điều kiện ĐẠT và điểm DỪNG. Bước đánh dấu **[DUYỆT]** cần chủ dự án đồng ý rõ ràng trước khi làm.
Không bước nào đụng PC1 production (`Tool_Quet`, đang ở 6dc3f9d) trừ khi ghi rõ.

| # | Bước | Cách làm | ĐẠT khi | DỪNG nếu |
|---|---|---|---|---|
| 0 | Duyệt mã | Kiểm toán độc lập nhánh `feature/managed-runtime-sheet-profiles` + gói audit nguồn | Không còn P1/P2 mở | Có P1 |
| 1 | **[DUYỆT]** Khoá phát hành thật | Sinh cặp Ed25519 trên PC1 (ngoài repo, khoá riêng KHÔNG đưa lên máy chủ/OneDrive), ghi `trusted_keys.json` | Khoá riêng cất an toàn, có bản dự phòng | Khoá riêng lộ |
| 2 | **[DUYỆT]** Lock có băm | Trên PC1 có mạng: `pip download --only-binary=:all: --no-deps -d wheelhouse` theo `requirements-lock.txt` + `launcher-lock.txt`. **docopt 0.6.2 KHÔNG có wheel trên PyPI** (chỉ sdist — đã xác nhận qua bộ nhớ đệm wheel của pip trên PC1): tải sdist, đối chiếu băm sdist với trang PyPI, `pip wheel --no-deps` từ sdist đó vào `wheelhouse`. Rồi `release_tool.py lock --wheelhouse wheelhouse` | Mọi dòng có `--hash=sha256` | Thiếu wheel Windows / băm sdist lệch |
| 3 | Bộ bootstrap | Đóng gói launcher + `bootstrap.py` + `trusted_keys.json` thật + 2 lock | Kit kiểm lại bằng `release_tool.py verify` | — |
| 4 | **[DUYỆT]** Sao lưu PC2 | Nếu PC2 đang có bản cũ (clone + `.bat`): sao lưu thư mục + `data\` sang ổ khác, ghi lại bản đang chạy | Bản sao mở được | Thiếu chỗ trống |
| 5 | **[DUYỆT]** Tắt đường cũ trên PC2 | Gỡ/đổi tên lịch Task Scheduler cũ chạy `ChayMayPhu.bat`/`GiamSat.bat`; KHÔNG xoá clone cũ | Không còn lịch cũ chạy | Lịch cũ vẫn chạy |
| 6 | **[DUYỆT]** Phát hành Stable thử | `release_tool.py build --commit <đã duyệt> --phien-ban 1.0.0 --wheel-kem wheelhouse\docopt-0.6.2-py2.py3-none-any.whl` (máy PC2 mới: KHÔNG cần cờ migration; bản sau có nâng lịch sử thì quyết định `--tu-dong-an-toan --tuong-thich-nguoc` hay để PC2 chờ duyệt) → `sign --hoi-mat-khau` → `verify` → `publish` (in lệnh) → chủ dự án tự chạy `gh release create stable-1.0.0 …` (repo phù hợp, không draft/pre-release; commit không mang tag `v…` nhẹ — xem cuối trang) | `verify` ĐẠT; tag mới, không gắn lại | Sai chữ ký/băm |
| 7 | Bootstrap PC2 | Theo `HUONG_DAN_PC2.md` §2, thư mục MỚI | `doctor` toàn ✅ | Bất kỳ ❌ |
| 8 | **[DUYỆT]** Hai bảng nhỏ | Tạo 2 Sheet thử (không phải bảng khách hàng), 2 hồ sơ đích, chia sẻ cho tài khoản dịch vụ; «Kiểm cấu hình» | Đọc được cả hai | Không đọc được |
| 9 | Quét thử + ghim | Lô 2–3 video công khai: lô 1 → bảng A; giữa lô đổi chọn sang B; lô 2 → B | Dòng lô 1 chỉ ở A, lô 2 chỉ ở B; hàng đợi «✅ Đã gửi» | Dòng lạc bảng |
| 10 | Restart/outbox | Bật «Tạm dừng toàn bộ», quét 1 video, tắt app (đóng cửa sổ), mở lại, bỏ tạm dừng | Việc vẫn còn và gửi đúng 1 lần | Mất việc / trùng |
| 11 | **[DUYỆT]** Cập nhật lúc rảnh | Phát hành `stable-1.0.1` (thay đổi nhỏ) → `CapNhat.bat` khi đang quét (phải hoãn) → khi rảnh (phải áp dụng) | Hoãn khi bận; áp dụng khi rảnh; `doctor` ✅ | Đổi mã khi đang quét |
| 12 | Diễn tập quay lại | Phát hành `stable-1.0.2` cố ý lỗi health (chỉ trên bảng thử) | Tự quay về 1.0.1, 1.0.2 bị cách ly, lịch sử/hàng đợi nguyên vẹn | Mất dữ liệu |
| 13 | **[DUYỆT]** Lịch Watch thật | Import `TimClipPro_GiamSat.xml` (thay mã hồ sơ), theo dõi 2–3 ngày | Log mỗi lượt OK | Lỗi lặp lại |

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
