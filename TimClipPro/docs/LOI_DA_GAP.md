# Lỗi đã gặp và cách sửa (đừng để tái diễn)

> Chuyển NGUYÊN VĂN từ mục «Lỗi đã gặp và cách sửa» của `TimClipPro/CLAUDE.md` (bản e49340d) ngày 09/10/2026 để
> CLAUDE.md ngắn lại. Giữ nguyên số mục: chỗ nào trong code/test ghi «CLAUDE.md mục N» là mục N của file này.
> Bản rút gọn từng mục: `TimClipPro/CLAUDE.md`, mục «Quy tắc rút ra từ lỗi đã gặp». Thêm lỗi MỚI ở cuối, đánh số tiếp
> (18, 19…), và thêm một dòng rút gọn tương ứng vào CLAUDE.md.

**1. Tiến độ tạo kho đứng ở 0% trên Windows tiếng Việt.**
Nguyên nhân gốc: `audfprint.py` dòng 48 dùng `open(listfilename, 'r')` không chỉ định
encoding. Windows tiếng Việt dùng cp1258/cp1252 → đọc file danh sách UTF-8 có dấu tiếng
Việt là `UnicodeDecodeError` → chết ngay, không in dòng nào → tiến độ 0%.
Đã sửa: `_run_stream()` truyền `env` có `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`,
`PYTHONUNBUFFERED=1` và chạy Python con với cờ `-u`. **Không sửa thư viện bên thứ ba.**
→ Mọi lần gọi subprocess Python trong dự án này đều phải đi qua `_run_stream()`.

**2. Lỗi bị nuốt mất.** Trước đây `_run_stream` bỏ qua mọi dòng không khớp "ingesting #",
nên lỗi thật không bao giờ hiện ra. Đã sửa: giữ 30 dòng cuối, báo lỗi kèm nội dung thật,
và coi "chạy xong nhưng xử lý 0 file" cũng là lỗi.

**3. Archive lệch với thực tế.** `sync()` giờ lấy hợp của `downloaded.txt` **và** ID đọc
từ tên file trên đĩa, nên tải đứt giữa chừng không bao giờ gây tải trùng.

**4. WinError 32 khi nạp lại kho (Windows).**
`os.remove(db_file)` trong `build_database(mode="new")` thất bại vì Windows không cho xoá
file đang có handle mở. Nguồn handle: `hash_table.HashTable(path)` gọi `gzip.open()` mà
không đóng, và `db_clips()` bị Streamlit gọi lại mỗi lần vẽ màn hình.
Đã sửa 4 lớp: (a) `db_clips()` tự đọc file vào RAM trong khối `with` rồi mới unpickle —
không bao giờ giữ handle; (b) cache theo mtime nên không đọc lại liên tục; (c)
`_xoa_an_toan()` thử lại 6 lần kèm `gc.collect()` để chịu được phần mềm diệt virus khoá
tạm; (d) nếu vẫn khoá thì tự chuyển sang file vân tay mới và cập nhật đăng ký kho.
→ **Không bao giờ gọi `os.remove()` trực tiếp lên file .pklz — dùng `_xoa_an_toan()`.**
→ **Không bao giờ dùng `hash_table.HashTable(path)` ở tiến trình cha.**

**5. Chọn lọc kết quả.** `_chon_loc()` chia video vi phạm thành `top_n` vùng thời gian đều
nhau, mỗi vùng lấy 1 bằng chứng mạnh nhất, ưu tiên clip gốc khác nhau. Lý do: bằng chứng
trải đều cả video thì hồ sơ khiếu nại mạnh hơn nhiều so với 5 đoạn dồn ở đầu video.
Chỉ số `ty_le` (% vân tay của clip khớp được) là thước đo CHUẨN HOÁ — dùng nó khi so sánh
các clip dài ngắn khác nhau, vì số hash tuyệt đối phụ thuộc độ dài và độ phong phú âm thanh.

**6. HTTP 403 khi tải video (18/08/2026).** Quét trả lỗi
`unable to download video data: HTTP Error 403: Forbidden` cho MỌI video chưa có sẵn
trong `data/downloads`. Không phải link hỏng, cũng không phải yt-dlp cũ (đang là bản
mới nhất trên PyPI).

Nguyên nhân: YouTube chặn từng **player client** một cách độc lập và đổi theo thời
gian. Client mặc định của yt-dlp bị chặn ở khâu TẢI, trong khi khâu trích metadata
vẫn chạy — nên tool lấy được tiêu đề rồi mới chết, rất dễ tưởng là hỏng link. Đo thật:
mặc định 403, `android` tải bình thường, `ios`/`mweb`/`web_safari` báo "format not
available", `tv` báo "page needs to be reloaded".

Bẫy chẩn đoán: `download_audio()` dùng lại file đã tải sẵn, nên vài video vẫn "thành
công" nhờ cache và che mất mức độ nghiêm trọng. Tỉ lệ thành công thật rơi từ 98%
(12/08) xuống 1,6% (18/08).

Đã sửa: `download_audio()` thử lần lượt `Config.ytdlp_player_clients`
(mặc định `["android", "", "tv", "ios", "web_safari"]`) cho tới khi có cái chạy, ghi
log client nào hỏng/cái nào cứu được. **Không khoá cứng vào một client** — lần sau
YouTube chặn tiếp thì chỉ cần đổi thứ tự trong cấu hình, không phải sửa code.
Huỷ (`Cancelled`) không kích hoạt đường lui vì đó là ý người dùng.

**6b. Cùng lỗi 403 đó vẫn còn ở ĐỒNG BỘ KÊNH (18/08/2026, cùng ngày).** Bản vá 6
chỉ áp cho đường quét (`engine.download_audio`); `ChannelSync._tai_va_nen` vẫn dùng
client mặc định nên tab «Đồng bộ kênh gốc» tiếp tục 403. Đo trên kho SML: 744/758
video đã có, 14 video còn thiếu — ép client `android` thì 12/14 tải được ngay.

Bài học kiến trúc: **dự án có HAI đường tải yt-dlp**, vá một đường là chưa xong.
(Xem mục 6c: bài học này còn tái diễn thêm một lần nữa trước khi được sửa tận gốc.)

Đánh đổi phải biết: client `android` **không trả format audio-only**, nên `ba/b` rơi
xuống `b` và tải cả video (đo: 80 MB thay vì 16 MB cho clip 15 phút). File `.opus`
cuối vẫn nhỏ như cũ (ffmpeg `-vn` bỏ hình), chỉ tốn băng thông và đĩa tạm. Đã thử
`android_vr`/`android_music`/`web_embedded`/`mweb`: client nào có audio-only thì 403,
client nào tải được thì không có audio-only. Khi YouTube mở lại client mặc định, đưa
`""` lên đầu `ytdlp_player_clients` là hết tốn.

2 video còn lại KHÔNG phải lỗi tool: `yo-j-rj0QhA` và `gHAxs_-oaMQ` bị giới hạn độ
tuổi, mọi client đều đòi đăng nhập. Muốn tải phải nạp cookie. `sync()` nay dọn mã màu
ANSI của yt-dlp và chú thích rõ các ca này để người dùng khỏi tưởng tool hỏng.

**6c. "Sign in to confirm you're not a bot" — CHẶN THEO IP, khác hẳn 403 (18/08/2026).**
Triệu chứng dễ nhầm với mục 6, nhưng cơ chế khác nên cách chữa cũng khác.

Đo thật lúc 13h40, ngay sau khi tool tải 12 video liên tiếp (12h33–12h39) cộng một
phiên quét:

| Phép đo | Kết quả |
|---|---|
| 8 video trong watchlist | bot-check, cả 8 |
| 5 player client (`android`, `tv`, `ios`, `web_safari`, `mweb`) | bot-check, cả 5 |
| **3 video vừa tải trót lọt lúc 12h39** | **bot-check** |
| Liệt kê danh sách kênh (`extract_flat`) | vẫn chạy bình thường |

Dòng thứ ba là bằng chứng quyết định: **không phải link hỏng, không phải video bị
khoá — YouTube gắn cờ cả địa chỉ mạng.** Bot-check đánh ở khâu TRÍCH XUẤT (yt-dlp chỉ
chuyển tiếp `playabilityStatus.reason` của máy chủ), nên đường lui player client ở mục
6 không cứu được — nó chỉ chữa khâu TẢI.

Nguyên nhân từ phía tool: **không có bất kỳ cơ chế giãn nhịp nào** và không hỗ trợ
cookie, nên cứ bắn request liên tục tới lúc bị chặn.

Đã sửa — ba việc:
1. `Config.ytdlp_sleep_requests_s` mặc định **1.0 giây**, ánh xạ sang
   `sleep_interval_requests` của yt-dlp. Đây là khoá DUY NHẤT giãn nhịp ở khâu trích
   xuất; `sleep_interval`/`max_sleep_interval` chỉ tác dụng ở khâu tải.
2. Hỗ trợ cookie: `ytdlp_cookiefile` (đường dẫn cookies.txt) hoặc
   `ytdlp_cookies_browser` (`"chrome"`, `"edge:Profile 1"`). **Chỉ lưu ĐƯỜNG DẪN** —
   `cau_hinh.lay_tu_config()` serialize mọi trường Config ra `data/cau_hinh.json` mà
   không có danh sách trắng, nên trường chứa nội dung cookie sẽ bị ghi thô ra đĩa.
3. Khi có cookie, yt-dlp **gỡ** các client không hỗ trợ cookie (`android`, `ios`,
   `android_vr`, `tv_simply` — đọc `SUPPORTS_COOKIES` trong `INNERTUBE_CLIENTS`).
   `sap_xep_player_clients()` đẩy chúng xuống cuối để khỏi mất lượt thử vô ích, nhưng
   không xoá hẳn: cookie sai/hết hạn thì chúng vẫn là đường lui hợp lệ.

**Sửa tận gốc bài học của 6b:** mọi tuỳ chọn yt-dlp nay đi qua module mới
`ytdlp_chung.py` (`CauHinhMang.tuy_chon()`, `thu_tung_client()`, `giai_thich_loi()`).
Cả 6 chỗ dựng `YoutubeDL` trong dự án — 3 ở `engine.py`, 3 ở `channel.py` — đều gọi
qua đó, nên không còn chỗ nào lệch được nữa. `no_color=True` cũng đặt ở đây, chữa tận
gốc việc escape ANSI lọt lên giao diện thay vì chỉ dọn lúc hiển thị.

**7. Bảng kết quả sập vì PyArrow khi có nguồn lỗi (18/08/2026).**
`ArrowInvalid: Could not convert '' with type str: tried to convert to int64` ở cột
"Số hash khớp". Nguyên nhân: `Engine.to_rows` điền `""` vào các cột SỐ ở dòng của nguồn
lỗi / không có kết quả, còn dòng có kết quả điền số thật → cột thành dtype `object` lẫn
hai kiểu → PyArrow (Streamlit dùng để vẽ bảng) từ chối. **Một nguồn hỏng làm sập cả
trang kết quả.**

Bẫy: **không chỉ một cột.** Vá riêng "Số hash khớp" thì lần quét sau lỗi nhảy sang
"Tỷ lệ vân tay khớp (%)". Đã sửa bằng `Engine.COT_SO` (danh sách cột số, đặt cạnh
`HEADER`) và `app.df_ket_qua()` ép kiểu theo danh sách đó — thêm cột số mới sau này
không phải nhớ sửa chỗ khác. Ô trống để **NaN**, không điền 0: 0 là "đo được và bằng
không", khác hẳn "không đo được".

Tiện thể sửa luôn: `to_rows` từng ép hai cột giây thành chuỗi bằng f-string, mà Sheets
ghi bằng `RAW` nên `"9"` đứng sau `"10"` khi sắp xếp. Nay trả `int` — **và** `sheets.py`
phải thôi `str()` mọi ô (`_o_sheets` giữ nguyên `int`/`float`), vì chỉ sửa `to_rows` thì
số vẫn bị ép về chuỗi ngay trước khi gửi đi.

**8. Cookie rò ra file nhật ký (18/08/2026, phát hiện khi phản biện bản vá 6c).**
Chỉ MỘT dòng `cookies.txt` sai định dạng — hay gặp nhất là mở bằng Notepad rồi lưu lại
làm TAB thành dấu cách — thì `YoutubeDLCookieJar.load()` gọi `write_string()` in NGUYÊN
VĂN dòng đó ra `sys.stderr`, kèm giá trị `__Secure-1PSID` đủ để chiếm tài khoản.
`quiet`/`no_warnings`/`no_color` KHÔNG chặn được vì `write_string` ghi thẳng stderr chứ
không qua logger của YoutubeDL. Mà `nhat_ky.mo_nhat_ky()` lại đấu stderr vào
`ketqua/giamsat_*.log` — file giữ 30 ngày, nằm chung thư mục với CSV mà người dùng hay
nén gửi đi khi nhờ hỗ trợ; `GiamSat.bat` và `ChayMayPhu.bat` đều chạy đường này.

Đã tái hiện được bằng thực nghiệm, rồi chặn bằng **hai lớp**:
1. `ytdlp_chung.kiem_tra_file_cookie()` kiểm định dạng Netscape TRƯỚC khi giao file cho
   yt-dlp; sai thì ném lỗi chỉ nêu **số dòng**, không bao giờ nêu nội dung.
2. `nhat_ky.che_bi_mat()` thay các dòng cảnh báo cookie bằng ghi chú, cắt theo từng
   dòng nên thông tin chẩn đoán khác vẫn còn.

→ **Quy tắc: không bao giờ tin cờ `quiet` của thư viện bên thứ ba để giữ bí mật.**
Chặn ở đầu nguồn (đừng đưa dữ liệu hỏng vào) và ở đầu ra (lọc trước khi ghi).

Audit D-11 (25/10/2026): chính yt-dlp GHI LẠI file cookie sau mỗi phiên bằng `open(file, 'w')` — cắt
cụt rồi ghi tại chỗ, không khoá, ghi cả hũ. GUI, CLI, Watch, luồng đồng bộ + luồng quét dùng chung một
file: phiên khác dựng tuỳ chọn đúng lúc file rỗng → cổng báo «không có bản ghi cookie nào» → cầu dao
cookie (ngưỡng 1) dừng cả lượt, bảo xuất lại cookie dù cookie vẫn tốt; hai lần lưu đan nhau để lại file
ghép đè hỏng tới khi xuất lại; phiên nạp trước đè cookie YouTube vừa xoay bằng giá trị cũ. Đã sửa:
yt-dlp nhận bản chụp (luồng văn bản) chứ không nhận đường dẫn; tool gộp CHỈ cookie phiên đổi vào bản
mới nhất dưới khoá, thay nguyên tử (`ytdlp_chung.LuongCookieFile`). → Quy tắc: file dùng chung giữa
các tiến trình chỉ ghi bằng file tạm + `os.replace` dưới khoá, và chỉ ghi phần mình đổi. Test:
`tests/test_cookie_ghi_lai_dong_thoi.py`. Phản biện (review audit D): cookie mà CẢ HAI phiên cùng xoay
(__Secure-1PSIDTS/SIDCC — chuyện thường) vẫn «người ghi sau thắng»: lượt quét nạp lúc T0, tải ffmpeg
60 phút, đóng sau đồng bộ kênh → đè bản xoay mới hơn. Đã sửa: dòng phiên đổi cũng so-rồi-đặt như dòng
xoá (`_doi_con_ghi`) — đĩa đã khác bản phiên nạp thì giữ đĩa, trừ khi bản của phiên có hạn dùng muộn hơn
(cấp sau).

**9. Vá lệch lần thứ tư — cấu hình chỉ tới 2/6 nơi gọi (18/08/2026).**
Bản vá 6c thêm cookie + giãn nhịp vào `ytdlp_chung` nhưng chỉ nối vào nút «Đồng bộ kênh»
và `cli.py kenh`. Bốn nơi còn lại vẫn gọi mạng bằng cấu hình mặc định: nút «Xem danh
sách video», nút «Kiểm tra còn thiếu», `cli.py vameta`, và `watch.py` — vòng giám sát
tự động, tức chỗ tích luỹ nguy cơ bị chặn CAO NHẤT. Thêm một chỗ nữa bên trong chính
`list_channel`: nhánh `lay_ngay_dang=True` gọi `lay_info_video` trần, đúng vòng lặp một
request MỖI video.

Bài học: gom về module chung là ĐIỀU KIỆN CẦN, chưa đủ. Phải rà **mọi nơi gọi** — dùng
`grep -rn "ChannelSync\|list_channel\|lay_info_video" --include=*.py`. Tham số cấu hình
có giá trị mặc định là bẫy: thiếu thì rơi về mặc định lặng lẽ, không có lỗi nào báo.
Đã có `tests/test_cau_hinh_toi_moi_duong.py` khoá lại từng đường.

Đi kèm: `ChannelSync.__init__` từng để `network_timeout_s=NETWORK_TIMEOUT_S`, tức mọi
lượt khởi tạo đều ghi đè giá trị người dùng đặt lên 30 giây. Mặc định nay là `None` để
phân biệt được "người gọi chỉ định" với "người gọi không quan tâm".

**10. Cookie HẾT HẠN còn tệ hơn không có cookie (18/08/2026).**
Người dùng đổi cục wifi (IP mới) nên bot-check ở mục 6c tự hết. Nhưng file cookie nạp
lúc chiều đã chết, và chính nó làm hỏng mọi lượt quét. Đo trên 8 link + 2 video đối
chứng, cùng máy cùng lúc:

| | Không cookie | Có cookie (đã chết) |
|---|---|---|
| 8 link người dùng | **8/8 chạy** | **0/8** |
| Video SML vốn chạy tốt | chạy | hỏng |
| Số format trả về | **24** (có 139/249/140/251 audio-only) | **4, toàn storyboard** |

Gửi cookie chết đi thì YouTube trả phản hồi KHÔNG CÓ MEDIA. Tool xin `bestaudio`,
không có gì để chọn → yt-dlp báo `Requested format is not available` (hoặc
`No video formats found!`) — câu chữ chẳng liên quan gì tới nguyên nhân, đẩy người
dùng đi tìm nhầm phía link.

**Hạn ghi trong file KHÔNG phản ánh phiên còn sống.** File vẫn "còn 400 ngày" trong
khi YouTube đã huỷ phiên (lướt tiếp làm xoay vòng cookie, đăng xuất, đổi mạng).
`kiem_tra_file_cookie()` ở mục 8 chỉ kiểm ĐỊNH DẠNG, không kiểm phiên.

Đã sửa: `ytdlp_chung.chay_kem_duong_lui_cookie()` — gặp đúng dấu hiệu này thì tự chạy
lại KHÔNG cookie và cảnh báo. Bọc NGOÀI đường lui player client, vì cookie chết làm
mọi client cùng hỏng. Nối ở cả `engine.youtube_info`, `engine.download_audio` và
`channel._tai_va_nen`. Bỏ cookie mà vẫn hỏng thì ném lỗi GỐC — cookie không phải
nguyên nhân, đừng dẫn người dùng đi sửa nhầm.

Audit D-2 (25/10/2026): đường lui cookie đọc «lỗi cuối» của đường lui client, mà có cookie
đăng nhập (yt-dlp xét theo TÊN LOGIN_INFO + SAPISID, sống hay chết) thì client cuối luôn là
`android`/`ios` — yt-dlp GỠ chúng, chỉ còn «No video formats found!», trùng dấu hiệu trên.
Cookie còn sống mà mọi client nhận cookie bị 403 ở khâu tải thành «Cookie YouTube đã hết hiệu
lực» (ghi chú → lịch sử, CSV, Sheets), phiên «cookie bị từ chối», đồng bộ kênh `BI_TU_CHOI`,
lượt lùi KHÔNG đăng nhập; 403 thật bị che. Đã sửa: `thu_tung_client` lấy lỗi ĐẠI DIỆN là lỗi
cuối ở client NHẬN cookie (bỏ «không định dạng» của client không nhận cookie; lỗi làm dừng đổi
client vẫn là đại diện). Test: `tests/test_cookie_403_khong_phai_cookie_chet.py`.
Phản biện bản sửa (review audit D): nhãn đúng nhưng KẾT QUẢ đảo — trước đó lượt lùi không cookie
(dù gán nhãn sai) để `android` tải được; sau bản sửa video hỏng hẳn, 3 video liền mở cầu dao
`HTTP_FORBIDDEN` dừng cả lô, đúng chế độ mục 6/6c. Đã sửa: đại diện là 403 thì `thu_tung_client`
thử lại CHÍNH các client yt-dlp đã gỡ vì cookie đăng nhập, KHÔNG cookie, và bên gọi bắt buộc báo
(ghi chú video «tải KHÔNG đăng nhập … HTTP 403»; câu xác thực của lượt đếm số video). Không qua
đường lui cookie, không `cookie_bi_tu_choi`, không nhớ cho cả lượt; bot/429 ở lượt ẩn danh thì dừng.

Audit D-12 (25/10/2026): đường lui cookie KHÔNG nhớ gì giữa các video — cookie chết (vẫn mang tên
LOGIN_INFO + SAPISID) làm MỖI video thử đủ chuỗi client có cookie (mặc định, tv, web_safari,
android, ios) rồi mới lùi: 6 phiên yt-dlp/video, kênh 1.189 video ≈ 6.000 phiên thừa — đúng kiểu
khuếch đại request của mục 6c, mà lượt vẫn báo «đủ». Đã sửa: lượt tải (đủ chuỗi client) lùi không
cookie THÀNH CÔNG là đối chứng, ghi vào `PhienYouTube` của lượt; thao tác sau (cả lấy thông tin)
chạy thẳng không cookie, vẫn báo rõ. Video đòi
đăng nhập vẫn thử cookie; không đối chứng thì không nhớ; lượt sau thử cookie lại. Test:
`tests/test_cookie_chet_nho_trong_luot.py`.

Bẫy khi nối: cảnh báo KHÔNG được dùng chung `canh_bao_gop`, vì `_merge()` xoá trắng
danh sách đó ở mỗi lượt khớp còn cảnh báo mạng sinh ra TRƯỚC đó. Nay có
`Engine.canh_bao_mang` riêng, gắn vào `kq.note` ở cuối `scan_youtube`.

Cũng ghi lại: `youtube_info()` từng KHÔNG có đường lui player client (chỉ
`download_audio` có) — đó là lý do lỗi hiện ra dạng thô, không kèm câu "Đã thử: ...".

**11. Băng thông: đang tải CẢ VIDEO thay vì chỉ tiếng (19/08/2026).**
Từ khi bản vá 6b đưa `android` lên đầu, kho đệm sinh ra 49 file `.mp4` có luồng h264 —
toàn bộ đều từ 18-19/08, trước đó chỉ có `.webm` audio-only. `android` không trả format
audio-only nên `ba` rơi xuống `b` = video tiến trình.

Đo 19/08 trên video 121 tiếng:

| Đường tải | Format | Dung lượng |
|---|---|---|
| `android` + `ba/b` (đang chạy) | 18 (360p) | **31,27 GB** |
| mặc định + `ba/b` | 251 | 6,99 GB |
| mặc định + `ba[abr<=70]` | 249 | **2,75 GB** |

Chênh **11 lần**. Thêm nữa: `_cut_chunks()` chuyển mọi thứ về WAV mono 11025 Hz trước
khi đưa cho audfprint, nên phổ trên 5,5 kHz bị vứt ngay — tải 130 kbps là trả tiền cho
dữ liệu bị ném đi. Đo hash trên 10 phút audio thật:

    128 kbps -> 47.399 hash (mốc)   |   48 kbps -> 47.539 hash (100,3%)
     64 kbps -> 47.623 hash (100,5%)|   32 kbps -> 45.118 hash ( 95,2%)

Nên `Config.ytdlp_format` nay là `ba[abr<=70]/ba/b`. KHÔNG áp cho `channel.py`: clip
trong kho là vân tay THAM CHIẾU, hạ chất lượng nguồn ở đó là hạ chuẩn cho mọi lượt
đối chiếu về sau.

**BẪY ĐO LƯỜNG quan trọng nhất của mục này:** kiểm bằng `test=True` (tải 10 KB đầu)
sẽ báo "OK" nhầm — YouTube phục vụ Range nhỏ nhưng từ chối tải đầy đủ. Phải TẢI ĐẦY ĐỦ
mới lộ ra 403. Đã suýt kết luận sai "bot-check hết rồi, client mặc định chạy lại được"
chỉ vì đo bằng chế độ test.

Thực tế 19/08: client mặc định VẪN 403 ở khâu tải (mọi format audio-only), thử cả
`mweb`/`android_vr`/`web_creator`/`web_embedded`/`tv_simply`/`android_music`/`web_music`
đều 403; chỉ `android` tải được. Nên hai tối ưu trên hiện CHƯA có hiệu lực — chúng là
cơ chế chờ sẵn, tự kích hoạt khi YouTube mở lại.

Để không phải trả giá 403 cho TỪNG video trong lúc chờ: `ytdlp_chung.NhoClientTotNhat`
nhớ client vừa tải được và đưa lên đầu, tự quên sau 30 phút để dò lại thứ tự mong muốn.
Nhờ vậy khoản tiết kiệm 11 lần được lấy lại tự động, không cần ai sửa cấu hình.

**12. Quét tăng dần cho video rất dài (19/08/2026).**
Video mục tiêu là bản tổng hợp 10-90 tiếng, mà clip gốc kho SML chỉ 15-30 phút. Quét
trọn là lãng phí lớn.

**Bài học phương pháp trước đã:** kết luận đầu tiên ("quét 3h đầu bỏ sót 38-44% video")
LÀ SAI. Nó lấy từ bảng `matches` trong lịch sử, mà 65% lượt quét chỉ lưu ĐÚNG 1 đoạn do
`top_n=1` — nên phép đo `min(start_s) <= 3h` thực chất hỏi "đoạn MẠNH NHẤT có nằm ở 3h
đầu không", không phải "có đoạn NÀO ở 3h đầu không". Hai câu hỏi khác hẳn nhau.
→ **Trước khi kết luận từ bảng `matches`, luôn kiểm `top_n` của thời kỳ sinh ra dữ liệu.**

Đo lại bằng thí nghiệm THẬT — quét trọn một video 35 tiếng, ghi vị trí mọi đoạn khớp:

| Phép đo | Kết quả |
|---|---|
| Số đoạn khớp | 180, rải ĐỀU (25-27 mỗi khối 5 tiếng) |
| Clip gốc khác nhau | 55 |
| Khoảng cách hai đoạn liên tiếp | trung vị 12 phút, **lớn nhất 19 phút** |
| Thử 64 vị trí cửa sổ 3 tiếng | **0 cửa sổ trượt** |
| Bằng chứng chọn (top_n=1) từ 1h đầu | 43.815 hash / quét trọn 47.432 = **92%** |

Đã làm: `Config.quet_tang_dan` (mặc định bật, cho video > 10 tiếng, bước 3 tiếng).
Quét từng đoạn từ đầu, thấy bằng chứng đạt chuẩn thì DỪNG. Đối chứng trên chính video
35 tiếng đó: **40 phút → 5,5 phút**, `ty_le` 52,7% → 52,6% (gần như y hệt — dùng
`ty_le` chứ đừng dùng số hash tuyệt đối để so, vì clip được chọn có thể khác).

**Ràng buộc không được phá:** dừng-khi-thấy chỉ đổi THỨ TỰ, không đổi ĐỘ PHỦ. Không
thấy gì thì phải quét hết video. Số liệu trên đúng với video tổng hợp DÀY ĐẶC; một
video chỉ lấy trộm một clip ở giờ thứ 30 vẫn phải bắt được.
Test `test_khong_thay_gi_thi_QUET_HET_khong_mat_do_phu` khoá đúng ca này.

Hai chỗ tinh tế:
* **Tách `duration_s`.** Nó đang gánh hai nghĩa: thời lượng VIDEO (hồ sơ, Sheets) và
  TRỤC ĐÃ QUÉT (chia vùng chọn lọc). Quét trọn thì trùng khít nên không ai thấy. Nay
  có `ScanResult.pham_vi_quet_s`: `_gan_chi_so` (nhãn Đầu/Giữa/Cuối) dùng video thật,
  `_chon_loc` dùng phần đã quét — chia theo cả video thì các vùng sau rỗng và Top-N
  trả về ít kết quả hơn đáng ra có.
* **Lưới mốc khúc giữ nguyên.** `_cut_chunks` vẫn tính mốc từ giây 0 rồi mới LỌC theo
  khoảng, nên ghép các đoạn cho ra đúng lưới của lượt quét trọn.

Bẫy đã sửa: `note` chỉ được hiển thị khi nguồn LỖI, nên quét một phần THÀNH CÔNG sẽ
âm thầm không nói gì và người dùng tưởng đã quét trọn. `app.py` nay hiện hộp thông báo
riêng liệt kê nguồn nào dừng sớm và quét tới đâu.

Lưu ý cấu hình: `quet_tang_dan_buoc_gio` phải DÀI HƠN clip gốc dài nhất trong kho đang
dùng. Kho SML clip 15-30 phút nên 3 tiếng rất dư; kho khác có clip 1-3 tiếng thì phải
nâng bước lên.

**13. Tải một phần cho video rất dài (19/08/2026).**
Quét tăng dần (mục 12) mới cắt phần XỬ LÝ; phần TẢI vẫn kéo trọn video. Với video 66
tiếng qua client `android` (chỉ có format 18) đó là **18,4 GB**.

Kiểm chứng `download_ranges` trước khi làm — video 15 phút: tải trọn 80,50 MB, tải 60
giây đầu **5,50 MB**. Tỉ lệ byte đúng bằng tỉ lệ thời lượng, tức yt-dlp thật sự chỉ lấy
phần cần chứ không tải hết rồi cắt.

Đã làm: `Config.tai_mot_phan` (mặc định bật), dùng chung ngưỡng/bước với quét tăng dần.
Không thấy gì trong phần đầu thì tải nốt phần còn lại — không mất độ phủ.

Chạy thật trên video 66 tiếng: **18,4 GB → 841 MB (giảm 95%)**, tổng 3,7 phút, tìm ra
"SML Movie: Jeffy's Swimming Lesson" ở phút 37 với `ty_le` 35,6%.

Ba cái bẫy:
* **API `download_ranges` là HÀM** `(info_dict, ydl) -> Iterable[Section]`, không phải
  list. Truyền list vào là yt-dlp gọi nó như hàm rồi nổ TypeError.
* **Tên file phải khác bản đầy đủ.** Dùng `<id>__p<giây>.<ext>` nên
  `glob(id + ".*")` — thứ tìm bản đầy đủ — không khớp phải. Nếu nhận nhầm, lượt quét
  sau sẽ lặng lẽ chỉ quét 3 tiếng rồi báo "không tìm thấy" cho cả video 66 tiếng: SAI
  MÀ KHÔNG CÓ DẤU HIỆU NÀO.
* **Ghi chú bị mất — lỗi thật, phát hiện khi chạy kiểm chứng.** File tải về chỉ dài 3
  tiếng nên `scan_media` tưởng đã quét trọn "video 3 tiếng" và không ghi chú gì;
  `scan_youtube` sửa `duration_s` lại thành 66 tiếng SAU đó nhưng quên ghi chú. Kết
  quả: báo cáo và lịch sử im lặng đúng như đã quét cả 66 tiếng — chính cái hiểu nhầm
  mà ghi chú sinh ra để chặn. Nay `scan_youtube` tự ghi chú sau khi sửa thời lượng.
  → **Bài học: sửa một trường phái sinh (`duration_s`) thì phải rà lại MỌI thứ tính
  từ nó**, ở đây là `quet_mot_phan` và ghi chú.

Còn để lại: client mặc định (có audio-only, 3 tiếng chỉ ~66 MB thay vì 841 MB) vẫn bị
403 nên bản tải một phần hiện đi qua `android` = video tiến trình. Đã xác nhận
`download_ranges` + ffmpeg chạy tốt với `android`, nên khi YouTube mở lại client mặc
định sẽ có thêm khoảng 12 lần tiết kiệm nữa, tự động.

**Bài học quy trình:** khi vá code bằng tìm-thay chuỗi, PHẢI kiểm tra lại là bản vá đã áp
dụng thật (chạy test tích hợp), vì chuỗi cũ có thể đã bị đổi ở lần vá trước.

Audit D-3 (25/10/2026): hai lượt quét ĐỒNG THỜI cùng một video (Watch giữ `tool.lock`, tab «Quét
YouTube» của GUI và `cli.py youtube` thì không) dùng chung `downloads/<tên>.<ext>.part` với
`continuedl`: lượt sau thấy `.part` của lượt trước đang ghi, xin `Range` từ cuối file rồi mở `'ab'` —
file đệm thành bản trộn hai luồng (tái hiện: khối `[0,1,2,3,2,3]`), lượt kia hỏng vì WinError 32 lúc
đổi tên, và mọi lượt quét sau dùng lại file hỏng («Đã có sẵn audio») không báo gì (kiểm thiếu đuôi chỉ
bắt file NGẮN). Trên Windows `sanitize_open` của yt-dlp cố ý không khoá file nên lần mở thứ hai không
lỗi (đóng G6 của `DATA_FLOW.md`). Đã sửa: `download_audio` giữ khoá HĐH theo tên file tải
(`data/khoa_tai/<tên>.lock`, ngoài `downloads/`); lượt sau chờ (bấm Dừng là thôi chờ), rồi kiểm lại bộ
đệm DƯỚI khoá. → Quy tắc: `continuedl` chỉ an toàn khi mỗi `.part` có đúng MỘT người ghi. Test:
`tests/test_tai_audio_dong_thoi.py`.

**14. "Tool hỏng rồi" hoá ra là ÂM TÍNH ĐÚNG — lỗi nằm ở câu chẩn đoán (21/08/2026).**

Người dùng gửi 4 link kênh `SML Remix` kèm ảnh báo cáo 0 kết quả và hỏi "có phải hôm
qua mình xoá gì làm hỏng cả tool không". Không có gì hỏng cả:

| Kiểm chứng | Kết quả |
|---|---|
| Lịch sử 4 link đó | đã 0 kết quả từ **17/08**, tức TRƯỚC mọi commit bị nghi |
| Cùng kênh, cùng kho, cùng sáng 21/08 | `91uQvipfkow` **16.445 hash**, `2YWROJViBw4` **24.809**, `q24gBBLI3dM` **58.569** |
| Toàn bộ 21/08 | 178 lượt quét, 116 có kết quả |
| Test + ruff | 926 passed, sạch |
| Kho SML | 756 clip, phủ **đúng 100%** 759 video còn trên kênh SML |

Nguyên nhân thật: `SML Remix` chuyên reup video SML **đã bị xoá khỏi kênh gốc**. Video
đã xoá thì không tải về làm vân tay tham chiếu được, nên clip gốc vĩnh viễn không có
trong kho. Đo trên chính kênh đó: tool đã quét 298/915 video, **24,5% ra kết quả,
68,8% ra 0** — 4 link kia rơi đúng vào nhóm 68,8%, hoàn toàn bình thường.

**Cái thật sự hỏng là CÂU CHẨN ĐOÁN, và nó hỏng theo hướng nguy hiểm nhất: đẩy người
dùng đi sửa nhầm chỗ.** Hai ca:

* `audfprint_khong_ra_match` nêu nghi vấn "sai kho vân tay, **kho rỗng**" trong khi
  kho vừa nạp xong 756 clip — hệ thống ĐÃ BIẾT hai nghi vấn đó là sai mà vẫn nêu.
* `khong_dat_chap_nhan` nghe như CHÍNH SÁCH quá chặt nên phản xạ đầu tiên là hạ
  ngưỡng. Trong khi cả 3 link đều bị loại bởi CÙNG một clip («Jeffy Wick») với
  ~380 hash trong ~10 giây — nhạc hiệu dùng chung. Hạ ngưỡng ở đây là hỏng thật.

Đã sửa: `ChanDoanQuet` mang thêm `ten_kho`/`so_clip_kho` (engine đổ vào ở
`_chot_chan_doan`, dùng cache `db_clips()` nên không tốn I/O) và cờ `dau_hieu_nhac_hieu`
(`_deu_la_nhac_hieu` trong chan_doan_quet.py). Câu chung được thay bằng câu chỉ đúng
nguyên nhân. Sửa ở tầng `mat_o_dau()` nên CẢ giao diện và CLI cùng hưởng, không phải
vá hai nơi.

**Ràng buộc không được phá:** `_deu_la_nhac_hieu` đòi **MỌI** ứng viên đều dưới ngưỡng
(phủ <5%, khớp <30s) và phải có **≥2** ứng viên. Xét theo ứng viên MẠNH NHẤT là sai:
chỉ cần một ứng viên khớp dài là lượt đó không còn thuộc ca này, gán nhãn "toàn nhạc
hiệu" sẽ khiến người dùng bỏ qua một reup thật. Test
`test_mot_ung_vien_khop_dai_thi_KHONG_goi_la_nhac_hieu` khoá đúng ca đó. Quan sát
thực tế của bản vá: link `JVdXCI63mTM` có 10 ứng viên nên KHÔNG được gắn nhãn — bảo
thủ đúng như thiết kế.

**Đính chính một số đo ở mục 11.** Bảng "48 kbps -> 100,3% hash" đo **số hash SINH RA**,
không phải **số hash KHỚP** — hai đại lượng khác nhau và chỉ cái sau mới quyết định
kết quả. Đo lại trên `91uQvipfkow` (bản reup thật, khớp clip *Jeffy's Trophy!*):

    nguồn 128 kbps AAC      14.503 hash (mạnh nhất) | 44.006 tổng
    ép qua opus 48k          11.685 hash (-19,4%)   | 35.252 tổng (-19,9%)

Tức trần `ba[abr<=70]` CÓ làm giảm bằng chứng ~20%, không phải ~0% như bảng cũ hàm ý.
Nhưng **không đổi kết luận nào**: 11.685 vẫn gấp 11 lần `min_hash_floor`. Lưu ý phép đo
này dùng nén ĐỜI 2 (AAC→opus) nên là CẬN TRÊN của thiệt hại; opus 50k gốc của YouTube
sẽ tốt hơn. Hiện chưa đo trực tiếp được vì mọi format audio-only vẫn 403 (xem mục 11).

**Bài học:** khi một kết quả âm tính bị nghi là bug, thứ phải kiểm ĐẦU TIÊN là lịch sử
(`data/lichsu.db`) và một ĐỐI CHỨNG DƯƠNG cùng kênh/cùng ngày — rẻ hơn đọc code rất
nhiều và trả lời dứt điểm câu "có phải mới hỏng không".

**15. Ba việc còn để lại của mục 14, và một bug thứ tư lộ ra khi kiểm chứng (21/08/2026).**

**15a. `da_thu_toc_do: []` gộp chung "chưa từng chạy" với "chạy rồi mà không thấy".**
Cấu hình sống để `luoi_resample: []` và `luoi_tempo: []` — **đánh đổi CỐ Ý, có tài liệu**
(`docs/DA_TOC_DO.md:184`: bỏ lưới quét mù để khỏi trả giá 2,9× cho mỗi video âm tính).
Hệ quả KHÔNG cố ý: `_quet_da_toc_do` thoát ngay ở `if not hang_doi` TRƯỚC khi ghi gì
vào `da_thu_toc_do`, nên `quet_da_toc_do: true` trông như đang chạy trong khi nó chưa
từng chạy một lượt nào — điểm mù đã che việc lưới bị để rỗng suốt nhiều tuần.

Đã sửa: `ChanDoanQuet.ly_do_khong_bu_toc_do` nói rõ nguyên nhân và chỉ đúng tên khoá
cần sửa, hiện ở cả giao diện lẫn CLI. **KHÔNG tự lật lưới về mặc định** — đó là quyết
định đánh đổi tốc độ của người dùng, việc của tool là làm nó NHÌN THẤY ĐƯỢC.
Phần bù tốc độ vẫn hoạt động cho video bị đổi TỐC ĐỘ (đọc độ trôi, ±6%); chỉ video bị
đổi CAO ĐỘ là lọt.

**15b. Tắt «Quét tăng dần» không tắt được tải một phần.** `app.py` bảo người dùng
"muốn quét trọn thì tắt «Quét tăng dần»", nhưng `_gioi_han_tai` chỉ đọc `tai_mot_phan`
— trường KHÔNG có ô nào trên giao diện. Bỏ tick xong vẫn chỉ tải 3 tiếng đầu của video
40 tiếng, không một dấu hiệu nào. Đã sửa: `quet_tang_dan` là CÔNG TẮC TỔNG, và
`tai_mot_phan` có ô riêng LỒNG bên trong. Chiều `quet_tang_dan` bật + `tai_mot_phan`
tắt (tải trọn, xử lý tăng dần) vẫn hợp lệ và có test canh.

**15c. Dừng sớm bỏ qua `top_n` — và `Config.top_n` mặc định là 5, không phải 1.**
`_co_ung_vien_dat` trả True ngay ở ứng viên ĐẦU TIÊN, nên đặt `top_n=5` để lấy 5 bằng
chứng cho hồ sơ khiếu nại thì đoạn đầu tìm được 1 ứng viên là dừng luôn — mất trắng 4
suất. Phép đo ở mục 12 chạy ở `top_n=1` nên không chạm tới. Nửa còn lại của cùng lỗi:
`scan_youtube` chỉ tải nốt khi `not r.matches`.

Đã sửa: `_du_de_dung_som` hỏi "chính sách chọn lọc đã thoả mãn chưa" — đủ `top_n` ứng
viên, và đủ `top_n` CLIP KHÁC NHAU khi bật `uu_tien_clip_khac_nhau` (năm đoạn của cùng
một clip chỉ điền được một suất). `scan_youtube` so với `top_n` thay vì với 0.

**Cân nhắc đã bác bỏ:** chặn hẳn dừng sớm khi `phan_bo_deu` bật. Đúng về ngữ nghĩa
(không thể kết luận "trải dài toàn video" từ 3 tiếng đầu) nhưng `phan_bo_deu` cũng mặc
định bật, nên sẽ vô hiệu hoá toàn bộ tính năng ở cấu hình mặc định. Báo cáo ĐÃ nói thật:
`_gan_chi_so` dán nhãn vùng theo VIDEO THẬT nên 5 đoạn lấy từ 3 tiếng đầu đều mang nhãn
«Đầu», và `note` ghi rõ đã dừng ở đâu. **Giá phải trả cần biết:** với `top_n>1`, video
dài nay bị tải/quét nhiều hơn hẳn trước — đó là cái giá đúng của việc thật sự đi tìm đủ
`top_n` bằng chứng. Máy đang chạy để `top_n: 1` nên không đổi gì.

**15d. BUG THỨ TƯ — dấu hai chấm trong tiêu đề làm MẤT TRẮNG bản ghi chẩn đoán.**
Lộ ra khi kiểm chứng 15a: quét xong, CLI in đúng chẩn đoán mới nhưng `data/chan_doan/`
không hề có file mới.

Nguyên nhân: `_luu_chan_doan` dựng tên file bằng `fingerprint_progress.ten_file_an_toan`
— hàm chỉ lọc ký tự ĐIỀU KHIỂN vì nó sinh ra để rút gọn tên cho LOG, không phải để dựng
đường dẫn. Trên Windows, ghi vào `chan_doan\SML Movie: Abc.json` **không ném lỗi**: nó
tạo một file RỖNG tên «SML Movie» kèm NTFS Alternate Data Stream tên «Abc.json». Nội
dung nằm trong stream, `os.listdir` chỉ thấy «SML Movie», `glob("*.json")` không thấy gì.
Ghi nguyên tử qua `.tmp` + `os.replace` còn hỏng nốt trên đường ADS nên rốt cuộc **không
lưu được gì cả**, chỉ để lại file rác 0 byte. Nơi gọi bọc `contextlib.suppress(Exception)`
nên im lặng tuyệt đối.

Phạm vi: mọi video có dấu hai chấm trong tiêu đề — tức gần như TOÀN BỘ kho SML
(«SML Movie: …», «SML ROBLOX: …», «SML Parody: …»). Đúng những video người dùng quan tâm
nhất là những video mất bản ghi. Máy thật còn 5 file rác 0 byte (`SML Movie`, `SML Parody`,
`SML ROBLOX`, `SML Story`, `SML YTP`), đã kiểm bằng `Get-Item -Stream *`: không stream nào
còn dữ liệu, nên xoá là an toàn. Vòng dọn giữ-200-file cũng đi theo `glob("*.json")` nên
không bao giờ nhìn thấy chúng để dọn.

Đã sửa: `luu_tru.ten_file_hop_le()` — lọc `<>:"/\|?*` và ký tự điều khiển, cắt dấu
chấm/khoảng trắng CUỐI (Windows tự bỏ chúng nên `"a. "` và `"a"` là cùng một file), chặn
tên thiết bị DOS (`CON.json` ghi ra console chứ không ra đĩa).

→ **Quy tắc: `ten_file_an_toan` là hàm HIỂN THỊ, `ten_file_hop_le` là hàm ĐƯỜNG DẪN.
Đừng bao giờ dựng tên file từ dữ liệu người dùng bằng hàm dành cho log.**
→ **Bài học rộng hơn: `contextlib.suppress(Exception)` quanh một thao tác ghi biến mất
mát dữ liệu thành vô hình.** Nếu không tình cờ đếm số file trước/sau khi quét thì bug này
còn nằm đó vô thời hạn. Test `test_ghi_json_voi_ten_da_lam_sach_thi_glob_TIM_RA` và
`test_ban_ghi_chan_doan_cua_video_CO_DAU_HAI_CHAM_khong_duoc_bien_mat` khoá lại ở cả tầng
hàm thuần lẫn tầng engine — chốt chặn là **glob phải TÌM RA**, không phải "ghi không ném lỗi".

Kiểm chứng cả mục 15: 952 passed, ruff sạch, đã kiểm đột biến từng nhánh (8 đột biến,
mỗi cái bị đúng test bắt), và chạy quét thật để xác nhận bản ghi nay lưu được.

**16. Nhãn Đầu/Giữa/Cuối tính theo FILE thay vì theo VIDEO (02/10/2026).**
Đúng bài học cuối mục 13 lại tái diễn. Có ba chỗ đổi `duration_s` từ độ dài FILE đang xử lý
sang độ dài VIDEO thật: tải một phần, âm thanh YouTube ngắn hơn video, file tải thiếu đuôi.
Cả ba đều quên dán lại nhãn vùng mà `_gan_chi_so` đã tính theo file — đoạn ở giờ thứ 1 của
video 66 tiếng mang nhãn «Giữa» (1/3 của file 3 tiếng) trong cột «Vùng» của báo cáo.
Đã sửa: `Engine._nhan_vung` là luật 1/3–2/3 DUY NHẤT, và `_dan_lai_nhan_vung(r)` được gọi ngay
sau cả ba chỗ đổi. → **Đổi `duration_s` ở đâu thì gọi `_dan_lai_nhan_vung` ngay sau đó.**
Ranh giới 1/3–2/3 nay có test riêng (`tests/test_nhan_vung.py`); trước đó đổi 2/3 thành 3/4
mà cả bộ test vẫn xanh.

**17. Bị YouTube chặn thì DỪNG, đừng đâm tiếp vào tường (03/10/2026).** Chi tiết:
`docs/YOUTUBE_ACCESS_RELIABILITY.md`. Trước bản này, mọi vòng lặp nhiều video (batch quét, Watch,
lô nguồn chung, đồng bộ kênh, vá metadata) chạy tiếp tới hết khi YouTube đòi xác minh bot, và mỗi
video còn thử đủ 5 player client — một lần bị chặn thành hàng chục request nữa, đúng thứ làm bị
chặn nặng thêm (mục 6c). Lỗi chỉ được hiểu bằng vài phép so chuỗi; `Video unavailable` (chữ ký
thật của video bị gỡ ở Tier 2) không được nhận ra; liệt kê kênh nuốt lỗi thành "kênh rỗng".
→ **Một lượt chạy = một `PhienYouTube`**: phân loại lỗi (11 loại), thử lại CHỈ lỗi mạng tạm thời
  và HTTP 429 theo bảng `NGAN_SACH` (nghỉ huỷ được), cầu dao mở theo `NGUONG_MO` (bot 1, 429 1,
  cookie hỏng 1, đăng nhập 3, 403 3, mạng 3) — mở là không gửi request nào nữa trong lượt đó.
→ **Lỗi truy cập không bao giờ là âm tính**: `status="error"` + `ScanResult.loi_truy_cap`; video
  bị bỏ qua không vào lịch sử; lô nguồn chung CHƯA KẾT LUẬN; Watch không đẩy dòng lỗi YouTube lên
  Sheets; CLI thoát mã 3.
→ **403 không tự thành "cookie hỏng"**, `Video unavailable` không thành bot: đừng suy đoán mạnh
  hơn bằng chứng. 403 ở khâu tải vẫn đổi client (mục 6); bot/đăng nhập/429/video gỡ thì không.
→ **Khâu tải không có vòng thử lại ngoài**: chạy lại cả danh sách client sẽ đụng `.part` của client
  khác (`don_file_do_dang`). yt-dlp tự nối tiếp bên trong, nay có nghỉ có trần.
→ **Cổng cookie kiểm đúng luật nạp của yt-dlp**: dòng `#HttpOnly_` là bản ghi (dòng hỏng bị yt-dlp
  in nguyên văn ra stderr), dòng 1 phải là tiêu đề Netscape. Cấu trúc đúng ≠ YouTube chấp nhận
  phiên; chỉ request thật mới biết (`cli.py youtube-doctor --network URL`).
  Audit D-1 (25/10/2026): cổng bỏ sót luật thứ ba của `http.cookiejar` — cờ include-subdomains phải
  khớp dấu chấm đầu miền; lệch một dòng thì yt-dlp từ chối CẢ file bằng câu lỗi mang đường dẫn + repr
  nguyên dòng (giá trị cookie), lọt qua `che_bi_mat` (TAB đã thành chữ `\t`) vào log, lịch sử, CSV,
  và bị xếp «chưa rõ» (thử đủ 5 client, cầu dao đợi 5 lỗi). Đã sửa cả hai lớp: cổng kiểm luật đó;
  `che_bi_mat` che câu lỗi nạp; câu đó xếp cookie hỏng. Test: `tests/test_cookie_co_mien_dau_cham.py`
  so cổng với bộ nạp THẬT của yt-dlp.
  Audit D-4 (25/10/2026): mục SẮP phát (premiere / live đã lên lịch) nằm trên đầu tab Videos, `list_channel`
  giữ lại, yt-dlp ném «This live event will begin in …» / «Premieres in …» — không luật nào nhận ra nên thành
  «chưa phân loại»: mỗi mục thử đủ 5 client, 5 mục liền nhau mở cầu dao, đồng bộ kênh/Watch `BI_CHAN` mỗi ngày
  trước khi tới video thật. Đã sửa: loại riêng `UPCOMING_NOT_STARTED` — lỗi của TỪNG video, không bao giờ mở cầu
  dao, không đổi client, không vào sổ hạn chế (lượt sau tự thử lại khi đã phát). Test:
  `tests/test_truy_cap_youtube_sap_phat.py`.
  Audit D-10 (25/10/2026): «Trạng thái YouTube» ở thanh bên báo XANH «truy cập YouTube bình thường» chỉ vì
  `youtube_operations` > 0 — số đó đếm lượt THỬ (tăng trước khi chạy). Lô 1–2 link hỏng hết (403, mạng) chưa tới
  ngưỡng cầu dao vẫn xanh; đường quét thật (metadata được, tải 403) thì cầu dao không bao giờ mở. Đã sửa: xanh chỉ
  khi có thành công và 0 lỗi; 0 thành công → cảnh báo kèm số lỗi theo loại; có cả hai → dòng thông tin kèm số. Test:
  `tests/test_trang_thai_youtube_luot_hong.py`.

**18. «Bóng» của âm thanh lặp làm lệch mốc và thừa dòng (10/10/2026, PC2).** Chi tiết: `docs/BONG_AM_THANH_LAP.md`.
Nhạc có nhịp trống đều, vòng hợp âm hay đoạn lặp y hệt làm audfprint trả thêm căn chỉnh của CÙNG clip lệch bội số nửa
ô nhịp («bóng», 8–30% số hash của căn chỉnh thật, phủ cùng vùng video). `_merge` neo mốc vào mảnh có vùng SỚM NHẤT của
nhóm nên một bóng 34 hash kéo lệch mốc tới ±`dedup_s` (E2E trên PC2: −10,7 s; dựng lại kho: −19,2 s, vì bảng hash
audfprint bỏ ngẫu nhiên phần tràn); nhóm toàn bóng ≥ 1.000 hash thành dòng «Rất chắc chắn» thừa và làm phồng «Tổng số
đoạn phát hiện». Bộ test không bắt được vì `_giai_dieu` là nốt ngẫu nhiên — không bao giờ lặp.
→ **Mốc chỉ lấy từ căn chỉnh CHÍNH**; bóng vẫn được gom và tính bằng chứng như cũ. Đừng xoá mảnh để «làm sạch»: bản
  xoá-trước-khi-gộp làm nhóm thật mất tới 1,1% hash — đủ đánh rơi ứng viên sát ngưỡng 1.000.
→ **Dữ liệu test cho matcher phải có âm thanh lặp** (`tests/am_thanh_lap.py`), không chỉ giai điệu ngẫu nhiên.
→ **Đổi gộp/chấp nhận thì hỏi: có sinh dương tính MỚI không?** Có = đổi chính sách nhận diện (chữ ký chính sách, Watch
  quét lại âm tính). Bản sửa P0 cố ý không sinh (C' chỉ gộp khi một phần đã đạt chuẩn) nên chữ ký giữ nguyên.

**19. Gom theo đường dẫn, tra theo tên: hai bản ghi kho cùng tên lẫn số của nhau (26/10/2026, PC2, audit A-1).**
Kho dựng ĐỆ QUY và chỉ khử trùng theo đường dẫn đầy đủ nên «Season 1/x.opus» và «Season 2/x.opus» (hay một thư mục
`backup/` chép vào kho) là hai bản ghi vân tay. `_merge` gom mảnh theo đường dẫn, nhưng tổng hash (cận trên) và mẫu số
`ty_le` ở `_gan_chi_so` lại tra bằng dict theo basename — bản ghi đứng sau đè bản trước: khớp 4,5% bản lớn thành 90%,
bậc phủ cao nhận NHẦM; khớp hợp lệ bị kẹp và báo «đếm trùng» oan; hai bản sao giống hệt thành hai dòng báo cáo giống
nhau và `so_dat_nguong` đếm đôi.
→ **Số của một kết quả lấy từ ĐÚNG bản ghi đã khớp** (`Match.duong_dan_kho`, chỉ trong bộ nhớ); tên chỉ là đường lùi
  và khi tên trùng thì chọn phía an toàn (tổng lớn nhất). Bản sao cùng tên khớp cùng vị trí đặt = MỘT lần dùng (giữ
  bản mạnh nhất, không cộng bằng chứng hai bản ghi), có cảnh báo cho người dùng.
→ **Đổi định danh ở một bước thì rà mọi bảng tra dùng chung định danh đó** (dict comprehension theo tên im lặng nuốt
  bản trùng). Test: `tests/test_ban_ghi_kho_cung_ten.py`.

**20. Dấu nguồn gốc ghi cho dữ liệu không rõ gốc thành ngày «nguyên bản» lệch 1 ngày (26/10/2026, PC2, audit A-2).**
`kiem_ngay_dang --repair-offline --apply` đọc lại chính entry trong `clips_meta.json`; entry không có epoch rơi vào
nhánh chuỗi của resolver và được đóng dấu `publication_date_source="upload_date"` — vô hại lúc viết, vì khi đó chỉ là
«độ tin cậy thấp». Sau này V2 đọc đúng dấu đó là `upload_date` NGUYÊN BẢN của yt-dlp, trong khi `va_metadata` và seed
tên file ghi vào `upload_date` ngày ĐÃ quy đổi giờ VN → video đăng sau 17:00 UTC hiện ngày gốc trễ 1 ngày trên Sheets,
CSV, hồ sơ, không cảnh báo (`Engine._bo_sung_ngay_goc` còn bỏ qua vì tưởng đã có ngày nguyên bản).
→ **Chỉ ghi dấu nguồn gốc khi dữ liệu THẬT SỰ đến từ nguồn đó** (info yt-dlp vừa hỏi lại); dữ liệu đã lưu không rõ gốc
  thì để nguyên, không «nâng hạng». Repair offline nay chỉ ghi entry suy được từ epoch; còn lại «Bỏ qua» → cần
  `--repair-network`.
→ **Thêm người đọc mới cho một dấu cũ thì rà mọi nơi GHI dấu đó** và hỏi: nơi ghi có chắc như người đọc mới giả định?
  Entry đã bị bản cũ đóng dấu không phân biệt được với dấu đúng — chỉ `--repair-network` ghi lại được.
  Test: `tests/test_ngay_quy_doi_khong_thanh_ngay_nguyen_ban.py`.

**21. fsync đặt sai chỗ: kho vân tay công bố bằng `os.replace` khi dữ liệu còn trong cache (26/10/2026, PC2, audit C-1).**
`build_database` có fsync bản làm việc (chế độ «Bổ sung») nhưng TRƯỚC khi audfprint (tiến trình con, `gzip.open` +
`pickle.dump`, không fsync) ghi lại toàn bộ file; cha chỉ ĐỌC kho tạm để kiểm (đọc không đẩy trang bẩn) rồi đổi tên đè
kho cũ, trong khi sổ đăng ký ngay sau đó được fsync. Mất điện vài giây sau «Tạo lại kho»/«Bổ sung» → kho cụt/toàn số 0,
kho cũ đã bị thay — mất hàng giờ tạo vân tay. Nhánh file cũ bị khoá có cùng lỗ hổng.
→ **fsync file ĐÚNG bản sẽ công bố, SAU lần ghi cuối, ngay trước `os.replace`** — kể cả khi người ghi là tiến trình con
  (mở `r+b` rồi `os.fsync`: Windows `FlushFileBuffers` cần quyền ghi). Một fsync ở bước trước không bảo vệ gì nếu
  bước sau ghi lại file. Test: `tests/test_kho_cong_bo_ben_vung.py`.

**22. Sổ đăng ký đổi TRƯỚC khi công bố: «Tạo lại kho» bị Dừng/lỗi để lại nguồn mới trên kho cũ (26/10/2026, PC2, audit C-2).**
`build_database` ghi `thu_muc` (nguồn) vào `khos.json` ngay đầu job cho cả «Tạo lại kho từ đầu» sang thư mục KHÁC. Dừng,
audfprint lỗi, mọi clip 0 hash, mất điện → file `.pklz` vẫn là vân tay của nguồn cũ («kho trước job vẫn nguyên») nhưng sổ
nói nguồn mới; lớp chống trộn nguồn (`_kiem_nguon_bo_sung`) tin sổ, so mới với mới và nhận «Bổ sung» → trộn hai nguồn vào
một kho (đúng sự cố 15/10).
→ **Thông tin MÔ TẢ nội dung file (nguồn, phiên bản…) chỉ đổi SAU khi nội dung đó đã công bố**, cùng một lần sửa sổ với
  phiên bản mới (`_ghi_phien_ban_sau_cong_bo(thu_muc=…)`). «Bổ sung» vẫn ghi sớm vì nguồn đã được chứng minh trùng.
→ **Lớp chặn dựa vào một bản ghi thì mọi đường thoát (huỷ/lỗi/không công bố) phải để bản ghi đó khớp dữ liệu thật.**
  Test: `tests/test_tao_lai_kho_giu_nguon_khi_khong_cong_bo.py`.

**23. Nhánh đa nhân khác ngữ nghĩa nhánh một nhân: clip 0 hash thử lại thành HAI bản ghi (26/10/2026, PC2, audit C-3).**
Clip hỏng/im lặng được ghi TÊN với 0 hash và «Bổ sung» thử lại nó (chỉ clip CÓ hash mới bị bỏ qua). Một nhân
(`HashTable.store` → `name_to_id`) tái dùng id cũ; đa nhân (GUI mặc định, `ncores=0` → tự dò > 1) chạy
`instrumented_multiproc_add` → `HashTable.merge` chỉ nối `names`, không khử trùng → x(0) + x(N): đếm clip +1 mỗi lần,
«Một video gốc chung» coi x là trùng tên mãi mãi («CHƯA KẾT LUẬN», cảnh báo đổ lỗi chép/đổi thư mục kho). Test cũ dùng
runner giả gọi `store` nên không bao giờ thấy.
→ **Hai đường cho cùng một thao tác phải cùng ngữ nghĩa**; test phải đi qua ĐÚNG đường người dùng chạy (đa nhân thật),
  không chỉ đường dễ giả. Sửa ở lớp bọc (`giai_phong_ban_ghi_rong` trước `merge`), không sửa thư viện vendored.
  Test: `tests/test_bo_sung_da_nhan_khong_trung_ten.py`.
