# Hướng dẫn vận hành máy văn phòng (PC2) — bản cài có quản lý

Dành cho người vận hành (không cần biết lập trình). PC1 ở nhà là máy phát triển; PC2 ở văn phòng chỉ chạy
**bản Stable đã được chủ dự án duyệt**, tự nhận bản mới một cách an toàn. Hai máy **độc lập hoàn toàn**:
kho vân tay, lịch sử, hàng đợi gửi, cookie, khoá Google và cấu hình riêng của từng máy — không đồng bộ.

> Trạng thái: bộ công cụ đã được kiểm trên PC1 bằng HAI cài đặt giả lập. **Chưa cài trên PC2 thật** — làm
> theo `KE_HOACH_PILOT_PC2.md` khi chủ dự án duyệt pilot.

## 1. Chuẩn bị một lần

| Cần có | Ghi chú |
|---|---|
| Python 3.12 (64-bit) | Ghi lại đường dẫn tuyệt đối, ví dụ `C:\Program Files\Python312\python.exe`. Không cần quyền admin cho các bước sau. |
| Thư mục cài đặt MỚI | Ví dụ `D:\TimClipPro`. Không phải thư mục clone git cũ, KHÔNG nằm trong OneDrive/Dropbox/ổ mạng. |
| State root MỚI | Ví dụ `D:\TimClipPro_State` — chứa lịch sử, hàng đợi gửi, khoá, kết quả. KHÔNG nằm trong OneDrive/ổ mạng. |
| FFmpeg | Chép `ffmpeg.exe`, `ffprobe.exe` vào `D:\TimClipPro\tools\ffmpeg\bin\` (bản chính thức, có nguồn rõ). |
| Bộ bootstrap | File zip do chủ dự án chuẩn bị: launcher + `trusted_keys.json` (khoá công khai tin cậy) + `bootstrap.py`. |
| Khoá Google (tuỳ chọn) | File JSON của tài khoản dịch vụ. Chép bằng kênh riêng (USB) vào `D:\TimClipPro_State\secrets\`. KHÔNG lấy từ PC1 tự động. |

## 2. Bootstrap

Mở Command Prompt trong thư mục bộ bootstrap, chạy (một dòng):

```
"C:\Program Files\Python312\python.exe" bootstrap.py --goc D:\TimClipPro --state D:\TimClipPro_State --python-goc "C:\Program Files\Python312\python.exe" --tin-cay trusted_keys.json --repo <chu/du-an>
```

(`--nguon-thu-muc E:\phat_hanh` thay cho `--repo` nếu nhận bản phát hành từ USB.)

Bootstrap sẽ: kiểm đường dẫn (từ chối OneDrive/ổ mạng, từ chối ghi đè cài đặt có sẵn) → tạo **định danh máy
mới** → chép launcher + khoá tin cậy → tạo `TimClipPro.bat`, `GiamSat.bat`, `CapNhat.bat` → xuất file lịch
Windows để XEM TRƯỚC (`launcher\lich_xem_truoc\`, **chưa đăng ký**) → tải, **xác minh chữ ký** và cài bản Stable
đầu tiên. Kết thúc in ra trạng thái `ACTIVE`.

Kiểm lại bất kỳ lúc nào (chỉ đọc, không mạng):

```
D:\TimClipPro\launcher\env\Scripts\python.exe D:\TimClipPro\launcher\launcher.py doctor
```

Mọi dòng ✅ là ổn; ⚠️ cần xem; ❌ phải xử lý trước khi dùng.

## 3. Bắt đầu dùng

1. Mở `D:\TimClipPro\TimClipPro.bat` (giao diện mở ở http://localhost:8501).
2. **Tạo kho vân tay mới** trên PC2 (tab kho + đồng bộ kênh) — PC2 tự dựng kho, không chép từ PC1.
3. Tab **«📤 Gửi Google Sheets»**:
   - «Đăng ký khoá Google»: tên binding (vd. `mac_dinh`) + đường dẫn file khoá trong `secrets\`. Màn hình hiện
     địa chỉ email của tài khoản dịch vụ — chia sẻ Sheet (quyền Người chỉnh sửa) cho địa chỉ này.
   - «Thêm hồ sơ đích»: mở Sheet ở **đúng tab** rồi chép link (có `#gid=…`); tên tab để đối chiếu; định dạng
     Ngang 34 cột / Dọc 16 cột. Có thể tạo nhiều hồ sơ (nhiều bảng).
   - «🔎 Kiểm cấu hình (chỉ đọc)»: đọc thử bảng/tab/tiêu đề — KHÔNG tạo tab, không ghi gì. Đọc được chưa chứng
     minh có quyền ghi.

## 4. Quét và gửi

* Cạnh nút **Bắt đầu**: chọn **Đích gửi** (hoặc «Chỉ lưu cục bộ») và «Tự động gửi khi từng video hoàn tất».
  Đích được **ghim lúc bấm Bắt đầu**: đổi lựa chọn giữa chừng chỉ áp dụng cho lượt SAU (có dòng nhắc).
* Mỗi video quét xong được **lưu + xếp hàng gửi cùng một lúc** — tắt máy, mất điện cũng không mất việc gửi.
* Tab «📤 Gửi Google Sheets» → **Hàng đợi gửi**: trạng thái từng việc. Việc **❓ Không rõ đã gửi chưa** (mất
  mạng/mất điện đúng lúc gửi): mở Sheet tìm dòng của lần quét đó — có rồi thì «✅ Đã kiểm: dòng đã có trên
  Sheet», chưa có thì tick «chấp nhận có thể trùng» rồi «⚠️ Gửi lại». Tool **không tự gửi lại** việc không rõ.
* «⏸ Tạm dừng toàn bộ việc gửi»: quét vẫn chạy, việc vẫn xếp hàng; bật lại thì gửi tiếp.
* Xoá một lần quét đang gửi / không rõ → bị chặn (đối soát trước). Xoá lần quét đã gửi KHÔNG xoá dòng trên Sheet.

## 5. Giám sát theo lịch

`GiamSat.bat --destination <MÃ_HỒ_SƠ>` chạy một lượt giám sát (mã hồ sơ xem bằng
`launcher.py cli dich`). File lịch mẫu ở `launcher\lich_xem_truoc\` — **chỉ import vào Task Scheduler khi
pilot được duyệt** (thay `<MÃ_HỒ_SƠ_ĐÍCH>`). Lịch chạy không cần quyền admin, không chạy chồng.

## 6. Cập nhật

* `CapNhat.bat`: tải + kiểm bản Stable mới (chữ ký, băm, từng file), rồi áp dụng **khi không có việc nào đang
  chạy** — có việc thì hoãn, không bao giờ cắt ngang. Mất điện giữa chừng: lần mở sau tự khôi phục đúng chỗ.
* Thanh bên ứng dụng → «ℹ️ Phiên bản và cập nhật»: bản đang chạy, bản đang kích hoạt, bản chờ áp dụng, việc đang
  chạy; nút «⏸ Hoãn cập nhật 24 giờ».
* Bản mới đã kích hoạt mà ứng dụng còn mở bản cũ → ứng dụng báo «mở lại» và không nhận việc mới.
* Bản lỗi health check → tự quay về bản trước và **cách ly** (không cài lại mỗi lần mở). Lịch sử không bao giờ bị
  khôi phục mù — bản sao lưu trước mỗi lần cập nhật nằm ở `D:\TimClipPro_State\backups\`.

## 7. KHÔNG làm

* Không chép kho, `lichsu.db`, hàng đợi, cookie, khoá từ PC1 sang.
* Không chạy `ChayTool.bat`/`GiamSat.bat`/`cap_nhat.py` cũ trong thư mục cài đặt managed (bản cài từ chối).
* Không sửa/xoá file trong `releases\` hay `environments\` (chữ ký sẽ không khớp → doctor báo ❌).
* Không đặt state root vào OneDrive.

## 8. Khi có sự cố

1. Chạy `launcher.py doctor` — đọc các dòng ❌/⚠️.
2. `launcher.py update status` — trạng thái cập nhật (nhật ký, bản đang kích hoạt, bản cách ly).
3. Gửi chủ dự án ảnh màn hình doctor + `update status` (không gửi file khoá, cookie, `lichsu.db`).
