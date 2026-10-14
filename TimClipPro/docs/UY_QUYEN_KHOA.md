# Hai máy ngang quyền ký phát hành — ghi danh khoá bằng uỷ quyền có chữ ký

Mã: `uy_quyen_khoa.py` (máy có cài đặt: xem / yêu cầu / ghi danh / hoàn tác), `release_tool.py` (`tao-khoa`,
`ky-uy-quyen`, `kiem-uy-quyen`). Test: `tests/test_uy_quyen_khoa.py`; diễn tập trọn vòng trong sandbox:
`tests/dien_tap_phat_hanh.py` (cấu hình `ghi_danh`). Quy trình phát hành dùng khoá này: `docs/PHAT_HANH_HAI_MAY.md`.

## 1. Hiện trạng (Phase A — đọc mã, không suy đoán)

| Câu hỏi | Trả lời | Ở đâu |
|---|---|---|
| Định dạng trust store | `{"khoa": [{"key_id", "ed25519_pub_b64", "ghi_chu", …}]}`; `key_id = sha256(khoá thô 32 byte)[:16]`; trường lạ bị bỏ qua | `managed_update.doc_khoa_tin_cay`, `tao_key_id` |
| Tin nhiều khoá? | **CÓ**: parser trả `{key_id: khoá}`; chữ ký manifest mang `key_id`, `kiem_chu_ky` tra đúng khoá đó | `kiem_chu_ky` |
| Trust store nằm đâu, ai đọc | `<cài đặt>\launcher\trusted_keys.json` — bootstrap chép từ bộ kit; launcher đọc LẠI mỗi lần chạy (`tao_cap_nhat`, `doctor`) | `bootstrap.bootstrap`, `launcher.tao_cap_nhat` |
| Release có đổi được trust store? | KHÔNG: thư mục `launcher\` cố định từ lúc bootstrap; release đã ký nằm ở `releases\` | `MANAGED_UPDATE.md` §2, §8 |
| Launcher trên PC2 | đúng 5 file của commit `e49340d` (bộ kit 1.0.0); `git diff e49340d dc29b33` trên 5 file này: RỖNG | test `..._e49340d_...` |
| Ký không lộ mật khẩu | `release_tool.py sign --hoi-mat-khau`: `getpass` trong console của người dùng; khoá PKCS8 mã hoá | `release_tool.sign` |

**Kết luận:** không cần đổi launcher, không cần bootstrap lại, không cần bản phát hành mới để PC2 có quyền ký: chỉ cần
THÊM một mục vào file dữ liệu `trusted_keys.json` của cài đặt — đúng cách, có kiểm, có duyệt.

### Rào chắn: của Claude Code hay của runtime?

| Rào chắn | Loại | Ai/cái gì cưỡng chế |
|---|---|---|
| `.claude/settings.json` deny Read/Edit `C:\TimClipPro*`, thư mục khoá, `google_key.json`, cookie | chỉ Claude Code | quyền công cụ Read/Edit của Claude (lệnh shell không bị chặn — giữ bằng quy ước) |
| `CLAUDE.md` / rules: không push/tag/release khi chưa duyệt, không đọc khoá | chỉ Claude Code | quy ước |
| Hook `pre-push` cục bộ | git (người + Claude) | máy cục bộ; bỏ qua được bằng `--no-verify` (CẤM) |
| Ruleset GitHub (không force-push/xoá `integration/current`, tag `stable-*` bất biến) | máy chủ | GitHub — áp cho mọi khoá deploy, `gh`, web (đề xuất, cần chủ repo bật) |
| Chữ ký Ed25519 + chính sách Stable + băm gói + cây release + lock có băm + bố cục + cách ly | **runtime** | `managed_update` của launcher đã cài — ai chạy cũng vậy |
| Ghi danh khoá chỉ theo uỷ quyền có chữ ký + đối chiếu khoá công khai CỦA MÁY | **runtime (thủ tục)** | `uy_quyen_khoa.py`; KHÔNG chống được người có quyền ghi file của tài khoản Windows (họ sửa tay được file) — chống NHẦM, chống tráo trên đường đi, chống làm tắt; không chống chủ máy |
| Cần console thật để tạo khoá / ký / ghi danh / hoàn tác | runtime — chỉ CHỐNG NHẦM | `co_console()`: `isatty` + `GetConsoleMode` (stdin NUL/ống dẫn → từ chối). Một chương trình tự tạo console ảo (ConPTY) vẫn vượt được — đây là gờ giảm tốc cho tự động hoá vô ý, không phải rào chắn |

## 2. Giao thức (một lần trao đổi, không bí mật nào rời máy của nó)

```
PC2 (chủ máy gõ):  release_tool tao-khoa  → khoá riêng PC2 (PKCS8 mã hoá, C:\TimClipPro_KhoaPhatHanh\, ngoài repo)
                   uy_quyen_khoa yeu-cau  → YÊU CẦU tự ký bằng khoá PC2 (chứng minh giữ khoá riêng):
                                            khoá công khai + băm định danh cài đặt + băm trust store + khoá đang tin
                   → đẩy yêu cầu lên GitHub (không bí mật)
PC1 (chủ máy gõ):  release_tool ky-uy-quyen → kiểm yêu cầu, gõ ĐỦ 16 ký tự key_id mà PC2 báo qua tin nhắn của chủ
                                            máy (màn hình KHÔNG hiện sẵn), gõ mật khẩu khoá PC1 → UỶ QUYỀN có chữ ký
                                            → đẩy lên GitHub                                    ← LẦN CUỐI PC1 bắt buộc
PC2 (chủ máy gõ):  uy_quyen_khoa ghi-danh --khoa-cong-khai <file tao-khoa để lại trên PC2> → kiểm → khoá được uỷ quyền
                                            phải TRÙNG ĐỦ 32 byte khoá tạo trên PC2 → gõ «GHI DANH» → sao lưu → ghi
                                            nguyên tử → kiểm lại
```

### Định dạng (file JSON, đọc được, đưa lên repo công khai được)

`{"noi_dung": {…}, "chu_ky": {"thuat_toan": "ed25519", "key_id", "chu_ky_b64"}}` — chữ ký trên
`MIỀN + JSON chuẩn hoá(noi_dung)` (sắp khoá, không khoảng trắng, ASCII). Miền khác nhau cho yêu cầu / uỷ quyền / tự
kiểm → chữ ký uỷ quyền KHÔNG BAO GIỜ là chữ ký hợp lệ của một manifest (manifest ký trên byte thô, không miền); chiều
ngược lại: `release_tool.py sign` CHỈ ký `manifest.json` parse được là manifest và bắt đầu bằng «{» (miền bắt đầu bằng
«TimClipPro/») — không ký byte tuỳ ý. Khoá công khai bậc nhỏ (điểm xoắn, «xác minh» mọi chữ ký giả) bị từ chối ở mọi
đường: yêu cầu, uỷ quyền, khoá của máy, danh sách khoá, bộ kit. JSON có khoá trùng bị từ chối; trường thiếu/thừa bị từ chối; file > 16 KB bị từ chối.

| Trường uỷ quyền | Ràng buộc |
|---|---|
| `khoa_moi {key_id, ed25519_pub_b64}` | đúng một khoá Ed25519 hợp lệ, `key_id` khớp khoá |
| `cai_dat_sha256` | `sha256(MIỀN_CÀI_ĐẶT + installation_id)` — đúng MỘT cài đặt, không công bố định danh |
| `trust_store_sha256`, `khoa_hien_co` | trust store ĐÚNG TỪNG BYTE lúc tạo yêu cầu → sau khi ghi danh (và sau hoàn tác — có danh sách «thu_hoi») không dùng lại được |
| `ma_yeu_cau`, `yeu_cau_sha256` | gắn với ĐÚNG yêu cầu đã tự ký (kiểm được ngoại tuyến bằng `kiem-uy-quyen --yeu-cau`) |
| `ma_uy_quyen`, `tao_luc`, `het_han` (mặc định 30 ngày, tối đa 90) | hạn dùng; lệch đồng hồ ≤ 1 ngày |
| `ky_boi` | khoá ký PHẢI đang được chính trust store đích tin; khoá mới không tự uỷ quyền |

### Ghi danh (máy đích) — thứ tự và bất biến

1. Nạp `managed_update`/`runtime_paths`/`khoa` **ĐÃ CÀI** ở `<cài đặt>\launcher` (đúng parser launcher dùng; không
   sinh `__pycache__`; không lẫn module của repo).
2. Giữ khoá `update_state\updater.lock` (cùng khoá với bộ cập nhật); nhật ký cập nhật đang dở → dừng.
3. Đọc (không ghi): bố cục, định danh (phải trỏ đúng thư mục cài đặt), trust store (byte + parser), **bản đang chạy
   phải xác minh được** (chữ ký + con trỏ + cây file) — cài đặt chưa lành thì không đổi gì.
4. Xác minh uỷ quyền bằng trust store HIỆN TẠI → không nằm trong «thu_hoi» → ràng buộc (cài đặt, khoá chưa có, trust
   store đúng byte, hạn) → khoá được uỷ quyền TRÙNG ĐỦ 32 byte khoá công khai do `tao-khoa` để lại trên chính máy này
   (đối chiếu danh tính QUYẾT ĐỊNH: yêu cầu bị tráo trên đường đi, kể cả khoá «mài» trùng vài ký tự key_id, bị từ chối).
   File đó phải nằm NGOÀI mọi bản clone git và cạnh `khoa_rieng_phat_hanh_<cùng key_id>.pem` (chỉ kiểm có mặt, không
   đọc) — kẻ tráo yêu cầu có thể gửi kèm file khoá công khai của hắn trong repo.
5. Chủ máy gõ «GHI DANH» (xác nhận ý định; chỉ console thật; không có cờ bỏ qua).
6. Sao lưu byte cũ + bản uỷ quyền vào `launcher\trust_backups\` (tạo mới, fsync).
7. Ghi: file tạm cùng thư mục → fsync → `os.replace` (thử lại khi file đang mở). Chỉ THÊM một mục; mọi mục cũ giữ
   nguyên; mục mới ghi `ghi_danh {ma_uy_quyen, ky_boi, luc}`.
8. Kiểm lại bằng parser của launcher: tập khoá = cũ ∪ {mới}, khoá cũ cùng byte, bản đang chạy vẫn xác minh được.
   Lỗi bất kỳ → ghi lại byte cũ, báo «đã TRẢ LẠI».

Mất điện ở bất kỳ điểm nào: file là bản cũ HOẶC bản mới hoàn chỉnh (thay thế nguyên tử NTFS); chạy lại → xong, hoặc
báo «khoá đã được tin». File tạm sót (`trusted_keys.json.tmp-*`) được dọn ở lần chạy sau.

**Hoàn tác** (`hoan-tac --sao-luu <file>`): chỉ nhận bản sao lưu DO CÔNG CỤ tạo (`launcher\trust_backups\trusted_keys_*`);
không nhận liên kết cứng; chỉ GỠ khoá đã ghi danh (có bản ghi «ghi_danh») — không bao giờ gỡ khoá gốc của bộ kit; khoá gỡ vào danh sách
«thu_hoi» (trường lạ, launcher bỏ qua) → uỷ quyền cũ và MỌI uỷ quyền mới cho khoá đó bị từ chối (cần khoá mới); từ
chối nếu bản đang chạy hoặc bản đã chốt (`last_good`) do khoá sắp gỡ ký — cập nhật lên bản do khoá còn lại ký trước.

**Giới hạn đã biết:** khoá riêng PKCS8 mã hoá bằng PBKDF2-HMAC-SHA256 2048 vòng (`cryptography` không cho đổi số vòng
với PKCS8; OpenSSH/bcrypt cần thư viện không có trong môi trường launcher) → mật khẩu DÀI (≥ 16 ký tự, nên là 4–6 từ
ngẫu nhiên) + thư mục khoá chỉ người dùng và SYSTEM đọc được (`icacls` trong `.bat` tạo khoá).

## 3. Không làm (và vì sao)

* Không thay launcher, không thêm lệnh vào launcher: launcher hiện có đã tin nhiều khoá; thay launcher cần kế hoạch
  bảo trì riêng (bootstrap lại) — không cần cho việc này.
* Không đưa trust store vào bản phát hành: một bản phát hành không được tự đổi gốc tin cậy của chính nó.
* Không ràng buộc uỷ quyền vào byte của công cụ: nếu công cụ cần sửa, uỷ quyền đã ký vẫn dùng được (không bắt PC1 ký
  lại) — cái được ký là THAY ĐỔI (khoá nào, cài đặt nào, trust store nào), công cụ đi qua review PR.
* Không gỡ / thay khoá PC1. Không tắt kiểm chữ ký, chống hạ bản, cách ly.

## 4. Sau khi ghi danh

* Hai khoá cùng được tin: PC2 ký bản thường lệ; PC1 là máy dự phòng ký được bất cứ lúc nào. Mất một khoá → máy kia vẫn
  phát hành, rồi ghi danh khoá thay thế bằng chính giao thức này (khoá nào đang được tin cũng uỷ quyền được).
* `release/trusted_keys.json` (repo) = danh sách khoá công khai đang tin — dùng để `verify` trước khi phân phối và để
  dựng bộ kit cho máy cài MỚI (máy mới tin cả hai khoá ngay từ bootstrap, không cần uỷ quyền).
* Cài đặt bootstrap LẠI (định danh mới) không dùng được uỷ quyền cũ (ràng buộc cài đặt) — dùng bộ kit mới.

## 5. Kiểm chứng

`tests/test_uy_quyen_khoa.py` (cài đặt tổng hợp với launcher là bản sao 5 file của repo, và một ca với ĐÚNG blob
`e49340d`): đường chính (PC1 ký → PC2 ghi danh → bản PC2 ký cài được, bản PC1 ký vẫn cài được, doctor «2 khoá»);
TRƯỚC ghi danh bản PC2 ký bị bỏ qua; khoá lạ bị bỏ qua; 13 kiểu uỷ quyền giả; sai cài đặt; trust store đã đổi; dùng
lại; hết hạn / tương lai; không xác nhận; đang cập nhật; nhật ký dở; bản đang chạy không lành; mất điện ở 4 điểm; kiểm
sau ghi lỗi → trả lại; hoàn tác (và bị chặn khi bản đang chạy do khoá sắp gỡ ký); không TTY (NUL, ống dẫn) cho 5 lệnh;
không `__pycache__`, chỉ đổi đúng 1 file + 2 file sao lưu, state root không đổi.
Diễn tập sandbox (bộ kit dựng từ `e49340d`, bootstrap + `CapNhat.bat` thật, runtime thật): `tests/dien_tap_phat_hanh.py`
— kết quả ghi ở handoff PC1 và `docs/ai/TEST_MATRIX.md`.
