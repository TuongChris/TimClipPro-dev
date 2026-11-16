# YouTube Data API v3 — lấy thông tin video; yt-dlp chỉ còn tải (D-51, 16/11/2026)

## Mục tiêu
Giảm số lượt yt-dlp hỏi YouTube CHỈ để lấy thông tin (đúng chỗ bot-check đánh). Có khoá API thì tiêu đề, kênh, thời
lượng, ngày đăng lấy bằng YouTube Data API v3 (`videos.list`: tối đa 50 mã một lượt, 1 đơn vị hạn mức). yt-dlp còn lại:
tải âm thanh/video, liệt kê kênh (lát này), và làm đường lùi.

Nơi tiết kiệm thật (khảo sát 16/11): mỗi video QUÉT tốn một lượt `youtube_info` riêng trước khi tải (engine.py
`_scan_youtube`), và là lượt DUY NHẤT khi âm thanh đã có trong bộ đệm; các công cụ chạy loạt (vameta, vametak,
`kiem_ngay_dang --repair-network`, chuẩn bị «Một video gốc chung», xem trước kênh kèm ngày). Đồng bộ kênh KHÔNG có lượt
hỏi thông tin riêng (ngày/tiêu đề lấy ngay từ lượt tải) — ở đó API không bớt được lượt nào của yt-dlp.

## Quyết định
Người dùng (16/11):
1. Ngày đăng theo API. «Ngày đăng» V2 = ngày lịch UTC của `snippet.publishedAt` — đúng phép tính yt-dlp 2026.08.19
   dùng cho `upload_date` (`_video.py` ~4530: ngày UTC của mốc `uploadDate`), nên video đăng bình thường GIỮ NGUYÊN ngày
   cũ; chỉ có thể lệch ở video lên lịch / riêng tư rồi công khai / công chiếu / phát trực tiếp. Không dùng giờ VN: sẽ lệch
   +1 ngày với mọi video đăng 17:00–23:59 UTC và phụ thuộc biến `TIMCLIP_MUI_GIO` của từng máy.
2. Video hội viên / giới hạn tuổi: yt-dlp phát hiện lúc tải như cũ.
3. Không có khoá / hết hạn mức / API lỗi → tự lùi về đường yt-dlp hiện có, báo rõ.

Claude chọn (người dùng uỷ quyền «phương án tối ưu»): các mục «Hợp đồng» dưới đây.

## Hợp đồng

### Khoá
- Đường dẫn CỐ ĐỊNH `os.path.join(os.path.dirname(os.path.abspath(data_dir)), "secrets", "youtube_api_key.txt")`:
  DEV PC2 = `C:\Dev\TimClipPro_DevState\secrets\youtube_api_key.txt`; managed = `<state_root>\secrets\…` (người dùng tự
  chép); legacy mặc định = `<thư mục mã>\secrets\…` (đã gitignore). Không ô nhập, không trường cấu hình, KHÔNG biến môi
  trường (launcher chuyển biến môi trường sang tiến trình Stable, `launcher.py:77`).
- Định dạng: dòng trống và dòng bắt đầu `#` bỏ qua; đúng MỘT dòng còn lại, khớp `AIza[0-9A-Za-z_-]{35}`; đọc tối đa
  4 KB, `utf-8-sig`; UTF-16 (Notepad «Unicode», PowerShell 5.1) → báo «lưu lại dạng UTF-8». Lỗi chỉ nêu TÊN file.
- Không bao giờ in, ghi log, hiện bất kỳ phần nào của khoá (kể cả tiền tố, đuôi, độ dài). Gửi bằng header
  `X-Goog-Api-Key` qua `Request.add_unredirected_header` (không đi theo chuyển hướng sang máy khác); không đặt trong URL.

### `youtube_api.py` (mạng) + chính sách thuần trong `truy_cap_youtube.py`
- Truyền tải: stdlib `urllib.request` — gọi `urllib.request.urlopen(...)` qua thuộc tính module để fixture chặn mạng
  hiện có bắt được; `json`; timeout = `CauHinhMang.network_timeout_s`; KHÔNG áp nhịp `sleep_requests_s` (dành cho
  bot-check youtube.com); không proxy riêng (urllib tự theo proxy hệ thống như yt-dlp). Không thêm thư viện (lock đổi =
  phải dựng runtime mới).
- `videos.list`: `part=snippet,contentDetails,liveStreamingDetails` (thêm `status` khi cần biết còn/gỡ), `fields=` rút
  gọn; tối đa 50 mã/lượt; bỏ trùng, giữ thứ tự; mã lạ trong `items` bị bỏ qua; đọc thân tối đa 4 MB.
- Phân loại lỗi CHỈ theo `error.errors[].reason`, `error.status`, `error.details[].reason` của Google + mã HTTP — không
  theo chữ trong `message`, không lưu thân lỗi thô (có thể chứa số dự án):
  - `HET_HAN_MUC`: quotaExceeded, dailyLimitExceeded → tắt API tới hết lượt.
  - `KHOA_HONG`: keyInvalid, API_KEY_INVALID, accessNotConfigured, SERVICE_DISABLED, API_KEY_*_BLOCKED, keyExpired,
    forbidden và 403 khác, 401 → tắt API tới hết lượt.
  - `GIOI_HAN`: rateLimitExceeded, userRateLimitExceeded, RATE_LIMIT_EXCEEDED, 429 → tắt API tới hết lượt.
  - `TAM_THOI`: 5xx, `URLError`, `TimeoutError`, `OSError`, `http.client.HTTPException`, thân cụt → thử lại 1 lần sau
    3 s qua `ham_cho` của phiên (không `time.sleep` trần); 3 lần liên tiếp → tắt API tới hết lượt.
  - `PHAN_HOI_LA`: 2xx không đúng JSON mong đợi, 3xx, 4xx khác → tắt API tới hết lượt.
  Chỉ bắt đúng các loại ngoại lệ trên (AssertionError của test và lỗi lập trình phải nổi lên).
- Lỗi API KHÔNG BAO GIỜ đi qua `PhienYouTube.chay` / `phan_loai_loi` / `ghi_loi` / `ghi_thanh_cong` / `dem_yeu_cau`:
  403 sẽ thành `HTTP_FORBIDDEN` (cầu dao yt-dlp mở sau 3), «ratelimit» thành `RATE_LIMITED` (mở sau 1), và một lượt
  thành công xoá chuỗi lỗi của yt-dlp. Kết quả API trả về là GIÁ TRỊ, không ném ra nơi gọi.
- Phiên con: `PhienYouTube.__init__` thêm `self.api = PhienApiYouTube(ham_cho=self._cho)` — chốt tắt theo LƯỢT (an toàn
  luồng: D-29 chạy đồng bộ + quét song song trong một tiến trình), bộ đếm riêng (`yeu_cau`, `don_vi`, `video_api`,
  `video_lui`, `ly_do_tat`); `PhienYouTube.tom_tat()["api"]`. Cầu dao yt-dlp đang mở (`phien.mo`) → API cũng KHÔNG gửi
  (giữ nguyên nghĩa «Đã dừng yêu cầu mới tới YouTube»). API tắt → chỉ API nghỉ, yt-dlp chạy tiếp; lượt sau thử API lại.
- Hàm chính: `lay_video(phien, data_dir, ids, *, cancel_event=None, can_trang_thai=False) -> KetQuaApi` với
  `KetQuaApi(thong_tin: dict[mã, dict chuẩn], thieu: tuple[mã, ...], ly_do_lui: str)`. `thieu` = các mã nơi gọi phải lấy
  bằng đường yt-dlp CŨ, không đổi gì: không có khoá, khoá sai dạng, API tắt, lô lỗi, mã vắng trong phản hồi 200, video
  `liveBroadcastContent` là `upcoming` hoặc `active`. Không khoá → 0 yêu cầu API, `thieu` = tất cả.
- Dict chuẩn của một video từ API: `id`, `title`, `duration` (giây từ ISO 8601 `contentDetails.duration`; `P0D` hoặc
  thiếu → 0 = chưa biết), `channel` và `uploader` (= `snippet.channelTitle`), `channel_id`, `channel_url`
  (`https://www.youtube.com/channel/<channelId>`), `published_at` (chuỗi ISO NGUYÊN VĂN của `snippet.publishedAt`),
  `live_broadcast_content`, `actual_start_time` (nếu có), `privacy_status` / `upload_status` (khi có `status`).
- Link dùng được API: `ma_video_cho_api(url) -> str` — chỉ host youtube.com, www./m./music.youtube.com, youtu.be,
  youtube-nocookie.com; mã ĐÚNG 11 ký tự `[A-Za-z0-9_-]` từ `watch?v=`, `youtu.be/`, `/shorts/`, `/live/`, `/embed/`.
  Khác → `''` → đường yt-dlp như cũ (Twitch, kênh, danh sách phát, trang khác).
- Tab «📝 Tiêu đề kênh»: `lay_ngay_luot_xem(phien, data_dir, ids, *, cancel_event=None) -> (dict, lý do)` —
  `part=snippet,statistics`, 50 mã/lượt qua `_goi`; `{mã: {"published_at", "view_count": int | None}}`; KHÔNG lùi về
  yt-dlp (ô để trống). Có khoá → thêm cột «Ngày đăng» (ngày lịch UTC, định dạng D-30) và «Lượt xem» (ẩn → trống,
  không 0); API lỗi → hai cột trống + một cảnh báo kèm lý do; không khoá → bảng / CSV / TXT y như trước + một dòng
  nhắc nơi đặt khoá.

### Ngày đăng
- Phép đổi đặt trong `publication_date.py` (test cấu trúc cấm `fromtimestamp(` ở module khác):
  `ngay_utc_tu_published_at(s) -> str` (YYYYMMDD) và `epoch_tu_published_at(s) -> int | None`; nhận `Z`, phần giây lẻ,
  `±hh:mm`; rỗng / không múi giờ / sai / ngoài khoảng `epoch_hop_le` → rỗng hoặc None (không bịa ngày).
- Lưu: khoá MỚI `published_at` (ISO nguyên văn) trong dict `Engine.youtube_info` và trong mục `clips_meta.json` khi nguồn
  là API. KHÔNG ghi vào `upload_date_raw` (giữ nghĩa «yt-dlp nguyên văn»: bản cũ rollback đọc nó là của yt-dlp), không gắn
  `publication_date_source` 'timestamp' / 'upload_date'.
- Ưu tiên V2: `published_at` → `upload_date_raw` → (như cũ). Nhãn `NgayNguon.nguon`: `youtube_api.published_at` (video
  quét), `clips_meta.published_at` (video gốc). KHÔNG đổi trường `BaoCaoV2`/`GocV2`, `PHIEN_BAN_ANH_CHUP`, `'v2'`,
  `chu_ky_chinh_sach` → Watch không quét lại, ảnh chụp cũ đọc như cũ, rollback an toàn (bản cũ bỏ qua khoá lạ).
- Ngày «quy đổi» giờ VN cũ (tên file kho, `clips_meta.upload_date`, `ScanResult.upload_date`, xuất luật cũ): giữ resolver
  hiện có; nguồn API thì đưa `{"release_timestamp": epoch(actualStartTime) nếu có, "timestamp": epoch(publishedAt)}`.

### Báo cho người dùng
- Không có khoá: KHÔNG ghi vào ghi chú kết quả (`canh_bao_mang` giữ rỗng như `tests/test_cookie_can_js.py:598`); chỉ dòng
  trạng thái ở thanh bên «🔐 Kết nối YouTube» và `cli.py youtube-doctor` (ngoại tuyến, không gọi mạng).
- Có khoá: một dòng trạng thái riêng «API YouTube: N video lấy bằng API (~U đơn vị) · K video lùi về yt-dlp — <lý do>»
  ở thanh bên, tóm tắt CLI và báo cáo Watch. Không cộng vào `NHAN_TRUONG_THAT_BAI` (không phải lỗi truy cập YouTube),
  không đổi mã thoát 3 của CLI (chỉ theo cầu dao yt-dlp), không đưa vào ghi chú từng kết quả.

### Chống lộ khoá
- `.gitignore` gốc thêm `youtube_api_key*`; `dong_goi.py` thêm từ khoá tên `youtube_api_key` và mẫu nội dung
  `AIza[0-9A-Za-z_-]{35}`; `truy_cap_youtube.che_bi_mat` thêm luật che chuỗi `AIza…` trần (vẫn lũy đẳng).
- Tên module/test KHÔNG chứa `youtube_api_key`, `token`, `secret`, `credential`, `google_key`. Khoá giả trong test: ghép
  chuỗi và ghi `gia-khong-bi-mat` trên cùng dòng. Không viết khoá 39 ký tự trông như thật trong mã hay docstring.
- Test: fixture autouse «không có khoá» trong `tests/conftest.py` (như `_may_giai_duoc_js_gia`); fixture tuỳ chọn khoá giả +
  transport giả trong `tests/youtube_api_gia.py`. Không test nào gọi mạng thật.

## Phạm vi theo nhánh (16/11)
| Nhánh | Phần |
|---|---|
| `feature/pc2/youtube-data-api` | Lõi: module, phiên con, đọc khoá, phân loại lỗi, chống lộ, đổi ngày; `Engine.youtube_info` API trước (dict thêm `published_at`); ưu tiên ngày V2; trạng thái thanh bên / CLI / doctor; tài liệu |
| `feature/pc2/youtube-api-hang-loat` | `lay_video` theo lô cho vameta (`ChannelSync.va_metadata`), vametak (`Engine.va_metadata_thieu`), `kiem_ngay_dang --repair-network`, chuẩn bị «Một video gốc chung», xem trước kênh kèm ngày (`list_channel(lay_ngay_dang=True)`) |
| `feature/pc2/youtube-api-dong-bo-anh` | Đồng bộ kênh: sau các lượt tải, một `videos.list` cho mã vừa tải để ghi `published_at` (không đổi tên file; `bo_sung_video_info` không ghi đè `published_at`); thumbnail theo link của video YouTube lấy thẳng `i.ytimg` (như D-45) thay vì trích xuất yt-dlp |
| `feature/pc2/kiem-video-con-tren-youtube` | Kiểm video vi phạm còn / đã gỡ (`part=status`); KHÔNG lùi về yt-dlp (mục đích là không chạm YouTube bằng yt-dlp) — lỗi → «Chưa kiểm được — lý do»; lưu JSON trong `data_dir` bằng `luu_tru.cap_nhat_json` (không đổi lược đồ `lichsu.db`); bảng ở tab Lịch sử |
| `feature/pc2/tim-video-nghi-van` | Tìm video nghi vấn theo tiêu đề clip (`search.list`, hạn mức RIÊNG 100 lượt/ngày), loại kênh gốc, đánh dấu đã quét, đưa vào ô quét |
| `feature/pc2/tieu-de-kenh-ngay-luot-xem` | Tab «📝 Tiêu đề kênh» (D-38): cột «Ngày đăng» + «Lượt xem» khi có khoá (`lay_ngay_luot_xem`); liệt kê vẫn bằng yt-dlp |

## Ngoài phạm vi lát này (quyết sau)
- Liệt kê kênh bằng API: danh sách tải lên gồm cả Shorts và buổi phát trực tiếp (khác nghĩa «tab Videos» của D-38); link
  `/c/` không có trong API.
- Bật mặc định «Bổ sung ngày đăng gốc» khi có khoá (TimClipPro/CLAUDE.md đòi TẮT mặc định).
- Thăm dò thật khoảng 20 video (cần người dùng duyệt): so `publishedAt` / `actualStartTime` với yt-dlp ở video công chiếu,
  phát trực tiếp, lên lịch, riêng tư rồi công khai.
- Chính sách lưu dữ liệu API của Google (có thể đòi làm mới / xoá dữ liệu sau khoảng 30 ngày — CHƯA xác minh).

## Sự thật đã tra (Context7 — developers.google.com, 16/11)
- Hạn mức mặc định 10.000 đơn vị/ngày cho các endpoint thường; `search.list` có hạn mức RIÊNG 100 lượt/ngày; đặt lại
  lúc nửa đêm giờ Thái Bình Dương; mọi yêu cầu (kể cả không hợp lệ) tốn ít nhất 1 đơn vị.
- `snippet.liveBroadcastContent`: `upcoming` / `active` / `none`; `liveStreamingDetails`: `actualStartTime`,
  `actualEndTime`, `scheduledStartTime`.
- Khoá DEV kiểm 16/11: HTTP 200 (`C:\Dev\pc2_test_tools\youtube_api\kiem_key.py`, 1 đơn vị).
