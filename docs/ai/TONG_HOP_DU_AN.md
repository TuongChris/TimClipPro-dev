# Tool Quét (TimClipPro) — Tổng hợp toàn bộ dự án

> Bản tổng hợp ngày **26/10/2026**, theo mã `integration/current` @ **`ccc3ed6`** (repo `TuongChris/TimClipPro-dev`).
> Nguồn: mã nguồn, tài liệu trong repo (`TimClipPro/docs/`, `docs/ai/`), lịch sử Git, PR/Release trên GitHub và kết quả
> kiểm thử của các đợt làm việc. File này KHÔNG chứa khoá, cookie, link Google Sheet thật hay dữ liệu khách hàng.
>
> **Sau mốc này:** 27/10 PR #20 (`dd111e8`) — đồng bộ kênh chạy SONG SONG với quét trong giao diện (D-29); DEV 8502 chạy
> `dd111e8`; Kho CoryxKenshin dựng xong (1745 clip). Trạng thái mới nhất: `docs/ai/CURRENT_STATE.md` +
> `docs/ai/handoff/PC2.md`. Dựng lại trên máy mới: `docs/ai/TIEP_TUC_TREN_MAY_MOI.md`.

## Mục lục
1. [Tóm tắt nhanh](#1-tóm-tắt-nhanh)
2. [Tính năng](#2-tính-năng)
3. [Công nghệ sử dụng](#3-công-nghệ-sử-dụng)
4. [Kiến trúc](#4-kiến-trúc)
5. [Hai máy, môi trường và quy trình làm việc](#5-hai-máy-môi-trường-và-quy-trình-làm-việc)
6. [Lịch sử phát triển](#6-lịch-sử-phát-triển)
7. [Phát hành Stable](#7-phát-hành-stable)
8. [Quyết định chính (DECISIONS)](#8-quyết-định-chính-decisions)
9. [Bài học đã gặp (LOI_DA_GAP)](#9-bài-học-đã-gặp-loi_da_gap)
10. [Chất lượng và kiểm thử](#10-chất-lượng-và-kiểm-thử)
11. [Trạng thái hiện tại](#11-trạng-thái-hiện-tại)
12. [Việc còn mở](#12-việc-còn-mở)
13. [Tài liệu tham khảo](#13-tài-liệu-tham-khảo)
14. [Phụ lục: thuật ngữ](#14-phụ-lục-thuật-ngữ)

---

## 1. Tóm tắt nhanh

| Mục | Nội dung |
|---|---|
| Mục đích | Tìm **clip gốc của chủ kênh** (thường 5–10 phút) bị dùng lại bên trong **video vi phạm dài 3–30+ giờ** trên YouTube, bằng **vân tay âm thanh**; ra mốc giờ chính xác, link nhảy đúng giây và báo cáo để khiếu nại bản quyền |
| Người dùng | Chủ dự án (không lập trình), dùng hằng ngày trên dữ liệu thật |
| Chạy ở đâu | Hoàn toàn trên máy Windows; giao diện web cục bộ (Streamlit) + dòng lệnh + giám sát theo lịch |
| Lõi nhận dạng | audfprint (vân tay «landmark»), FFmpeg, yt-dlp; Python 3.12 |
| Đầu ra | Bảng kết quả, CSV, Google Sheets (ngang 34 cột / dọc 16 cột), hồ sơ khiếu nại `.md` |
| Quy mô mã | 63 module Python ≈ 37.400 dòng (không tính test và audfprint); 8 file Apps Script ≈ 3.800 dòng |
| Kiểm thử | ≈ 222 file test, 3.314 ca nhanh + 22 ca chậm; chạy chặn mạng, dữ liệu giả |
| Bản đang dùng hằng ngày | **Development 8502 trên PC2** chạy `ccc3ed6` với dữ liệu thật (DEV-ONLY từ 15/10, D-26) |
| Bản Stable mới nhất | 1.1.2 (`e74c923`, ký bằng khoá PC2); Stable trên PC2 (8501) giữ 1.1.1 làm dự phòng |
| Repo | `TuongChris/TimClipPro-dev` — **PUBLIC** (D-22); mỗi lần đẩy qua hook quét bí mật |

---

## 2. Tính năng

### 2.1 Tool làm gì, từ đầu đến cuối
1. **Đồng bộ kênh gốc** — chỉ tải phần tiếng (opus mono 64 kbps; đo thật: khớp ngang video gốc, 225 so với 221 hash).
2. **Tạo kho vân tay** từ các clip gốc.
3. **Quét** video YouTube (từng link, cả lô), cả kênh (qua Giám sát) hoặc file trong máy.
4. **Tìm các đoạn trùng** kèm mốc giờ; **chọn lọc bằng chứng** tốt nhất.
5. **Lưu lịch sử** (`lichsu.db`) và **xuất** bảng / CSV / hồ sơ `.md` / Google Sheets.

Chỉ cần mạng khi tải/đọc thông tin YouTube và khi gửi Google Sheets. Có ba cửa vào: giao diện web (`ChayTool.bat` hoặc
launcher DEV), dòng lệnh `cli.py`, và giám sát theo lịch (`GiamSat.bat` / `cli.py watch`).

### 2.2 Thanh bên (luôn hiện)
- **Tình trạng hệ thống:** ✅/❌ cho FFmpeg, FFprobe, yt-dlp, audfprint, kho vân tay; cảnh báo khởi động (sổ kho hỏng, thư
  mục dữ liệu nằm trong OneDrive/ổ mạng…).
- **ℹ️ Phiên bản và cập nhật** (bản managed): trạng thái, hoãn/bỏ hoãn cập nhật.
- **🗄️ Kho đang dùng:** chọn kho; khoá lại khi có tác vụ đang chạy.
- **⚙️ Tham số:** độ dài khúc (3600 s), khúc gối (≤ 180 s), hash tối thiểu, đoạn khớp tối thiểu, số nhân CPU, shifts; chọn
  lọc (Top-N = 5, loại dưới 1000 hash, bằng chứng mạnh từ 5000 hash, phân bổ đều Đầu/Giữa/Cuối, ưu tiên clip khác nhau);
  quét tăng dần cho video rất dài (> 10 giờ, mỗi lượt +3 giờ, «chỉ tải phần cần quét»: video 66 giờ chỉ tải 841 MB thay vì 18,4 GB).
- **🔐 Kết nối YouTube:** giãn nhịp, cookie (tên trình duyệt hoặc file `cookies.txt` — chỉ lưu đường dẫn), «Trạng thái
  YouTube» nói rõ dùng cookie được hay lượt sẽ chạy KHÔNG đăng nhập (thiếu Node.js/EJS).
- **📊 Google Sheets (cấu hình cũ)** + nút «💾 Lưu cấu hình» / «↩️ Khôi phục mặc định».

### 2.3 Bảy tab của giao diện
| Tab | Tính năng chính |
|---|---|
| **📥 Đồng bộ kênh gốc** | Xem danh sách video của kênh (không tải); đồng bộ tăng dần (`downloaded.txt` + ID trong tên file `YYYYMMDD - Tiêu đề [ID].opus`), ghi `clips_meta.json` (tiêu đề, ngày đăng gốc, link, thời lượng); thử lại video giới hạn tuổi/hội viên; kiểm file hỏng (ffprobe, chuyển vào `_hong\`, không xoá); màn tiến độ đo thật (tốc độ, ETA, MB, nhật ký); nhớ player client tải được; «Kiểm tra còn thiếu video nào»; «Dựng lại danh sách đã tải»; «Lấy lại tên video thật» |
| **🎬 Kho clip gốc** | Nhiều kho, mỗi kho một bộ vân tay; tạo/xoá kho (chỉ xoá vân tay); «Tạo lại từ đầu» / «Bổ sung clip mới» — kho mới phải qua kiểm rồi mới thay kho cũ; màn tiến độ tạo vân tay (%, công đoạn, ETA, PID, nhịp sống, Dừng an toàn); kiểm/khôi phục metadata báo cáo offline; vá metadata từ YouTube |
| **📋 Danh sách video trong kho** | Bảng tên video THẬT (từ `clips_meta.json`); sửa thư mục kho; đẩy danh sách lên tab riêng `DanhSachVideo_<Tên kho>` |
| **▶️ Quét YouTube** | Dán nhiều link; chọn Đích gửi + tự gửi; «Mỗi video tự chọn kết quả» hoặc «Một video gốc chung cho cả lô»; **giới hạn video dài** (mặc định video > 6 giờ chỉ quét 3 giờ đầu / 6 giờ đầu / toàn bộ); tải một phần nhanh (`-request_size`: 3 giờ âm thanh trong 9 giây); màn tiến độ lô chỉ số đo thật; nút Dừng giữ kết quả đã xong |
| **📁 Quét file trong máy** | Quét một file hoặc cả thư mục (không upload, không chép file lớn) |
| **📜 Lịch sử** | Mọi lần quét (kho, phạm vi, trạng thái); xem chi tiết, tải báo cáo ngang/dọc dựng từ ảnh chụp V2, CSV, gửi thêm thủ công; xoá có xác nhận |
| **📤 Gửi Google Sheets** | Hồ sơ đích, binding khoá Google, hàng đợi gửi, tạm dừng toàn bộ, cột «Vì sao chưa gửi», chẩn đoán lỗi 403/404 (mục 2.7) |

**Mở lại trang không mất việc:** tải lại trang hay mở tab thứ hai đều nhận lại việc đang chạy (lô quét, dựng kho, lô nguồn
chung, đồng bộ kênh, lấy tên, vá metadata) — có tiến độ, nút Dừng và kết quả cuối.

### 2.4 Cách so khớp và chọn kết quả
- **Cắt và so khớp:** khúc 1 giờ có gối nhau, so bằng audfprint, gộp mảnh ở ranh giới khúc.
- **Chấp nhận:** bậc A (≥ 1000 hash, mật độ ≥ 3 hash/s); bậc B cho clip ngắn (phủ vân tay ≥ 60 %, khớp ≥ 20 s, mật độ đủ).
- **Chọn lọc Top-N:** phân bổ đều Đầu/Giữa/Cuối, ưu tiên clip gốc khác nhau, sàn bằng chứng so với ứng viên mạnh nhất.
- **Chống «bóng» của âm thanh lặp (D-27):** nhạc có nhịp/vòng lặp không còn sinh dòng thừa và mốc lệch.
- **Chống tự khớp:** file/video đang quét nằm sẵn trong kho không bị báo là «tự vi phạm».
- **Quét tăng dần / dừng sớm:** đủ bằng chứng theo chính sách thì dừng; không thấy thì quét hết (chỉ đổi thứ tự, không đổi độ phủ).
- **Tìm nhanh Top-1:** quét khúc đầu trước, dừng nếu ≥ 5000 hash và ≥ 60 s khớp liền (nhanh hơn ~70 %).
- **Bù tốc độ:** chỉ chạy khi không có ứng viên đạt chuẩn — hồi quy độ trôi (±6 %) và lưới đổi cao độ [0,96; 0,98; 1,02;
  1,04], tối đa 6 lượt phụ; tìm ra nhờ bù thì báo «nhiều khả năng đã bị chỉnh tốc độ để né nhận dạng».
- **Chẩn đoán khi 0 kết quả:** phễu đếm từng tầng, chỉ đúng tầng làm mất kết quả, ứng viên mạnh nhất bị loại kèm lý do;
  quét một phần thì nói rõ không phải kết luận cho cả video.

### 2.5 Chế độ «Một video gốc chung cho cả lô»
Tìm MỘT clip gốc có mặt ở TẤT CẢ các link (≥ 2) để gom một khiếu nại: quét trọn video ngắn nhất làm mốc, xác minh ứng
viên trên các video còn lại (tối đa 2 lượt bổ sung/video). Kết luận: Tìm thấy N/N · Không tìm thấy (kèm ứng viên tốt nhất
k/N) · Chưa kết luận · Đã dừng. Giới hạn: chưa ghi lịch sử, chưa gửi Sheets (chỉ CSV), chưa có CLI.

### 2.6 Báo cáo (Report Policy V2)
- **Ảnh chụp lúc quét** lưu ở `bao_cao_job`: tải lại từ Lịch sử luôn ra đúng như lúc quét.
- Tên video sạch; **mốc hiển thị và `t` của link là cùng một giây**; ngày đăng là `upload_date` nguyên bản.
- **Ô «Đoạn vi phạm»:** `HH:MM:SS – HH:MM:SS · https://www.youtube.com/watch?v=<ID>&t=<giây>` (từ 25/10/2026; ảnh chụp cũ
  giữ dạng `youtu.be/<ID>?t=` — không sửa ngược).
- **Bảng ngang 34 cột** (một dòng/video, hợp đồng với Apps Script) và **bảng dọc 16 cột** (một dòng/đoạn).
- **CSV:** UTF-8 có BOM, chặn công thức (tên clip bắt đầu bằng `=`… không bị Excel chạy), không ghi đè; file phụ `.pham_vi.csv`.
- **Hồ sơ khiếu nại `.md`:** mỗi video vi phạm một file — thông tin chung, % video bị chiếm, từng đoạn với link nhảy mốc.
- Báo cáo V2 lỗi thì chặn xuất/gửi («⛔»), không bao giờ lùi về luật cũ.

### 2.7 Gửi Google Sheets
- **Hàng đợi bền (outbox)** trong `lichsu.db`, cùng giao dịch với lịch sử — tắt app/mất điện không mất việc; Watch và app
  dùng chung; mỗi thư mục dữ liệu một người gửi.
- **Hồ sơ đích** (link + `#gid`, tên tab, định dạng Ngang 34 / Dọc 16, khoá): mỗi lần sửa tạo revision mới; việc đã xếp
  hàng vẫn gửi theo đích cũ. Tạm dừng / Bật lại / Lưu trữ / Xoá; «Kiểm cấu hình».
- **Binding khoá Google:** hiện email tài khoản dịch vụ; kiểm khoá trước mỗi lượt (thiếu/sai thì không bắt đầu quét).
- **Trạng thái việc:** Chờ gửi, Chờ thử lại (tối đa 8 lần), Đang gửi, Đã gửi, Bị chặn, Không rõ đã gửi chưa, Đã huỷ. Việc
  «Không rõ» do người dùng xác nhận — tool không bao giờ tự gửi lại mù.
- **Mới (PR #19):** cột **«Vì sao chưa gửi»** (tạm dừng toàn bộ / hồ sơ tạm dừng / hẹn thử lại lúc mấy giờ / người gửi chưa
  chạy / tiến trình khác đang giữ / giành quyền lỗi / giữ lâu kèm lời khuyên) và **chẩn đoán lỗi theo lý do của Google**:
  API chưa bật · thiếu quyền (scope) · bảng chưa chia sẻ · 404 = mã bảng sai/bảng đã xoá — kèm `[khoá → tài khoản dịch vụ;
  bảng xxxxxx…]` (không lộ cả mã/link).
- **An toàn khi ghi:** ghi nguyên văn, định tuyến theo **mã tab** đã chốt; tiêu đề sai thì dừng; dòng lỗi YouTube không bao
  giờ lên Sheet.
- **Apps Script đi kèm:** xuất hàng sang `Ket_Qua_Json`, tô link «đã quét», dò link trùng, cập nhật «Tổng quan», khôi phục tiêu đề.

### 2.8 Giám sát tự động (Watch)
- `watchlist.json`: kênh (tối đa 50 video mới nhất) hoặc link; kho đối chiếu; giới hạn mỗi lượt (20).
- **Quy tắc quét lại:** đã dương tính → bỏ qua; âm tính → chỉ bỏ qua khi đã quét TRỌN, cùng phiên bản kho và cùng **chữ ký
  chính sách nhận diện**; lỗi/huỷ/quét dở → quét lại; `--quet-lai` quét lại tất cả.
- Dừng an toàn khi kho/đích Sheets không dùng được hoặc YouTube chặn. Cuối lượt: CSV, gửi Sheets, dọn đệm, tóm tắt.
- Chạy theo lịch bằng `GiamSat.bat`; mã thoát 0 xong · 1 lỗi · 2 bận · 3 YouTube chặn.

### 2.9 Truy cập YouTube
- Phân loại lỗi ở một chỗ (đã gỡ, riêng tư, cần đăng nhập/tuổi/hội viên, nghi bot, 429, 403, mạng, cookie hỏng, chưa công chiếu…).
- **Cầu dao:** nghi bot / 429 / cookie hỏng → dừng ngay; 403 / cần đăng nhập → dừng sau 3 lần liên tiếp. Lỗi truy cập
  **không bao giờ** bị tính là «không vi phạm».
- **Cookie:** kiểm định dạng Netscape; cần Node.js ≥ 22 + `yt-dlp-ejs`; 403 ở mọi client có cookie thì thử client không cookie
  và ghi rõ «tải KHÔNG đăng nhập»; ghi lại cookie đã xoay vòng an toàn (khoá + ghi nguyên tử, tạo `.timclip.lock` cạnh `cookies.txt`).
- `cli.py youtube-doctor [--network URL]`: chẩn đoán chỉ đọc.
- Đệm tải `data/downloads` có khoá; file đang được quét không bị dọn.

### 2.10 Dòng lệnh `cli.py` (13 lệnh)
`kenh` (đồng bộ kênh) · `taodb` (tạo lại kho) · `themclip` (bổ sung clip) · `youtube` (quét link) · `file` (quét file) ·
`watch` (một lượt giám sát) · `vameta` / `vametak` (vá metadata) · `dondep` (dọn đệm, job mồ côi) · `dung` (dừng Watch) ·
`youtube-doctor` · `dich` (liệt kê hồ sơ đích) · `gui` (chạy người gửi tới khi hết việc).

### 2.11 Công cụ kiểm riêng
`kiem_metadata_kho.py`, `kiem_ngay_dang.py`, `kiem_thoi_luong.py`, `lich_su.py --kiem/--khoi-phuc`, `kiem_header.py`,
`kiem_ngang.py`, `health_check.py`, `launcher.py doctor|update`.

### 2.12 Giới hạn đã biết
- Chỉ dựa vào âm thanh: video bị thay/đè toàn bộ tiếng thì không tìm được; bù tốc độ không phủ đổi tốc độ > ±6 %.
- Trần 200 dòng khớp mỗi khúc có thể che clip rất ngắn; Top-1 nhanh không cam kết chọn ứng viên tốt nhất toàn cục.
- Mốc «Đến» thường sớm hơn thật (audfprint cắt ~5 % mỗi rìa).
- **P-6:** cờ «mốc mơ hồ» đã tính nhưng chưa hiện ở giao diện/CSV/Sheets. **P-7:** lịch sử trước 25/10 có thể còn dòng «bóng»
  (đã có công cụ chỉ đọc ngoài Git, chưa chạy trên dữ liệu thật).
- Cột «Đánh giá» gần như luôn «Rất chắc chắn» (F-16, chờ quyết định).
- Google Sheets không có «gửi đúng một lần» tuyệt đối: việc «Không rõ» cần người đối soát.
- YouTube có thể chặn bất cứ lúc nào; tool không vượt CAPTCHA, không đổi proxy. Chưa có bản `.exe`.

---

## 3. Công nghệ sử dụng

### 3.1 Nền tảng (phiên bản theo lock có băm)
| Thành phần | Phiên bản / ghi chú |
|---|---|
| Hệ điều hành | Windows 10/11, chạy 100 % trên máy (không có máy chủ). Có `Dockerfile` chỉ để tham khảo |
| Python | **3.12.10** (`win_amd64`) |
| Giao diện | **Streamlit 1.62.0** (kèm starlette, uvicorn, websockets, altair, pyarrow 25, pydeck, watchdog) |
| Xử lý bảng | **pandas 3.0.5**, numpy 2.5.2 |
| Tải YouTube | **yt-dlp 2026.8.19** + **yt-dlp-ejs 0.8.0** (giải thử thách JavaScript khi dùng cookie; nâng cùng lúc) |
| Node.js | **≥ 22** khi dùng cookie (cài riêng; PC2 có 24.x) |
| FFmpeg / ffprobe | Cắt khúc WAV, nén opus, đổi tốc độ, tải một phần (`-request_size`) |
| Vân tay âm thanh | **audfprint** (Dan Ellis, MIT) chép sẵn trong `audfprint-master/`, không sửa; numpy + **scipy 1.18**, docopt, joblib, psutil |
| Google Sheets | **gspread 6.2.1**, google-auth 2.56, requests 2.34; xác thực bằng tài khoản dịch vụ |
| Cơ sở dữ liệu | **SQLite** (`lichsu.db`, lược đồ v4) |
| Chữ ký phát hành | **cryptography 50** (Ed25519) |
| Launcher | Môi trường riêng 8 gói (`launcher-lock.txt`) |
| Apps Script | 8 file `.gs` chạy trong Google Sheet |

- Lock runtime **55 gói**, cài `pip install --require-hashes --no-deps`; mã runtime = 12 ký tự đầu SHA-256 của lock
  (ví dụ `py312-f955a32807a9`).

### 3.2 Công cụ phát triển
- **pytest 9.x** (mặc định `-m "not slow"`; test chậm dùng audio thật + ffmpeg), **ruff** (nhóm lỗi E4/E7/E9/F).
- Test không bao giờ gọi Google/YouTube thật: máy chủ Sheets giả ở tầng HTTP, yt-dlp giả, kho giả, golden quét cũ; trên PC2
  bộ chạy test chặn mạng ra ngoài.

### 3.3 Đặc thù Windows
- Bảng mã **cp1252** (console tiếng Anh): tiến trình con in tiếng Việt phải ép UTF-8; test chạy cả hai bảng mã.
- Launcher `.bat` (ASCII, CRLF); PowerShell 5.1 cho script cập nhật/ghi danh khoá.
- Khoá liên tiến trình bằng khoá file của hệ điều hành; `os.replace` có thử lại; đường dẫn > 260 ký tự dùng `\\?\`.

---

## 4. Kiến trúc

### 4.1 Nguyên tắc lớp
```
app.py (Streamlit)    cli.py (dòng lệnh)        ← lớp giao diện
              ↘          ↙
              engine.py                         ← LÕI: không import streamlit; tiến độ qua callback + cancel_event
         ↙        ↓          ↘
  channel.py   outbox.py/sheets.py   audfprint-master/ (vendored, chạy trong tiến trình con)
        ↘        ↙
     ytdlp_chung.py         ← MỌI tuỳ chọn yt-dlp
           ↓
     truy_cap_youtube.py    ← MỌI lỗi YouTube phân loại ở đây (cầu dao + thử lại hữu hạn)
```

### 4.2 Module theo lớp (63 module, ≈ 37.400 dòng; `engine.py` 6.772 dòng)
| Lớp | Module |
|---|---|
| Giao diện (8) | `app.py` (7 tab), `scan_ui.py`, `ui_tien_do_quet.py`, `ui_tien_do_dong_bo.py`, `ui_gui_sheets.py`, `ui_cap_nhat.py`, `tac_vu_nen.py` (tác vụ nền nhận lại được sau tải lại trang), `markdown_an_toan.py` |
| Lõi quét / so khớp (13) | `engine.py`, `chap_nhan_khop.py`, `chong_bong_lap.py`, `toc_do_khop.py`, `chan_doan_quet.py`, `scan_jobs.py`, `tien_do_quet.py`, `common_original.py`, `common_original_jobs.py`, `fingerprint_progress.py`, `audfprint_progress_runner.py`, `process_runner.py`, `dung_lai.py` |
| Truy cập YouTube (6) | `ytdlp_chung.py`, `truy_cap_youtube.py`, `youtube_doctor.py`, `giam_sat_tai.py`, `channel.py`, `tien_do_dong_bo.py` |
| Kho / metadata (7) | `clip_metadata.py`, `publication_date.py`, `kiem_metadata_kho.py`, `kiem_ngay_dang.py`, `kiem_thoi_luong.py`, `danh_sach_video.py`, `don_dep.py` |
| Báo cáo (3) | `bao_cao_v2.py`, `bang_ngang.py`, `dossier.py` |
| Google Sheets / outbox (6) | `outbox.py`, `sheet_destinations.py`, `sheets.py`, `kiem_sheet.py`, `kiem_header.py`, `kiem_ngang.py` |
| Lịch sử / lưu trữ / khoá (5) | `lich_su.py`, `luu_tru.py`, `khoa.py`, `cau_hinh.py`, `nhat_ky.py` |
| Watch / CLI (4) | `cli.py`, `watch.py`, `chia_watchlist.py`, `thiet_lap_may_phu.py` |
| Runtime / cập nhật / phát hành (11) | `runtime_paths.py`, `launcher.py`, `bootstrap.py`, `managed_update.py`, `maintenance_gate.py`, `health_check.py`, `release_tool.py`, `uy_quyen_khoa.py`, `cap_nhat.py`, `dong_goi.py`, `dong_goi_may_chay.py` |

### 4.3 Đường quét (pipeline) từng bước
1. **Lấy thông tin video** qua `PhienYouTube` (bị chặn thì dừng lượt; lỗi truy cập không bao giờ là âm tính).
2. **Tải audio** (tối đa ~70 kbps vì audfprint hạ mẫu xuống 11.025 Hz); **tải một phần** bằng FFmpeg với `-request_size 10 MiB`
   (không có cờ này googlevideo trả theo nhịp phát); khoá tải riêng cho từng video; đo độ dài thật tới gói audio cuối.
3. **Phạm vi quét:** quét tăng dần (> 10 giờ, bước 3 giờ), tải một phần, giới hạn video dài của lô; kết quả ghi rõ phạm vi.
4. **Cắt khúc** WAV mono 11.025 Hz, 3600 s, gối nhau theo clip dài nhất (60–180 s).
5. **So khớp** audfprint song song nhiều nhân (`--min-count 10 --max-matches 200 --shifts 4`).
6. **Gộp** (`_merge` + `chong_bong_lap.py`): gom mảnh cùng clip ±20 s; phân loại chính/bóng/đối thủ; mốc chỉ từ mảnh chính;
   nhóm toàn bóng neo vào vị trí thật hoặc bỏ. Bất biến: **không sinh dương tính mới**.
7. **Chấp nhận** bậc A / bậc B.
8. **Chọn lọc Top-N** (phân bổ đều, ưu tiên clip khác nhau, sàn bằng chứng 0,70).
9. **Dừng sớm** (Top-1 nhanh; quét tăng dần dừng khi đủ chính sách chọn lọc; bỏ tự khớp khỏi mọi quyết định dừng).
10. **Bù tốc độ** khi không có ứng viên đạt chuẩn.
11. **Chẩn đoán + lưu:** chốt phễu chẩn đoán, ảnh chụp báo cáo V2; `save_job` ghi `jobs`, `matches`, `bao_cao_job` và việc gửi
    Sheets trong **một giao dịch**.

### 4.4 Bố cục dữ liệu
| Đường dẫn (trong thư mục dữ liệu) | Nội dung |
|---|---|
| `khos.json` | Sổ đăng ký kho (`dang_dung` + danh sách) |
| `db.pklz`, `kho_<slug>.pklz` | Kho vân tay audfprint — mất là phải dựng lại hàng chục giờ |
| `<thư mục kho>/clips_meta.json`, `downloaded.txt` | Tiêu đề, link, ngày đăng gốc; sổ đã tải (nằm cạnh audio opus) |
| `metadata/kho_<slug>.json` | Snapshot metadata riêng của từng kho |
| `cau_hinh.json` | Tuỳ chọn người dùng (chỉ lưu đường dẫn cookie, không lưu nội dung) |
| `lichsu.db` | SQLite v4: `jobs`, `matches`, `bao_cao_job`, các bảng gửi Sheets (`dich_gui`, revision, binding khoá, `hang_doi_gui` = outbox) |
| `downloads/` | Đệm audio đã tải (ngân sách 20 GB / 7 ngày) |
| `scan_jobs/<uuid>/` | Workspace từng lượt quét |
| `tool.lock`, `hang_doi_gui.lock`, `khoa_tai/`, `bao_tri/` | Khoá theo thứ tự cố định |

Hai chế độ đường dẫn (`runtime_paths.py`): **legacy** (PC1, test, Development PC2; OneDrive/ổ mạng chỉ cảnh báo) và **managed**
(bản Stable cài đặt: bắt buộc state root riêng + `installation.json`, từ chối OneDrive/ổ mạng, khoá Google ở `<state>/secrets/`).

### 4.5 Chế độ chạy
| | Legacy / Development | Managed Stable |
|---|---|---|
| Mở | `ChayTool.bat` / launcher DEV → `streamlit run app.py` | `launcher.py app|watch|cli|update|doctor` |
| Mã | Thư mục làm việc / worktree | `releases/<X.Y.Z>/` bất biến, manifest có chữ ký |
| Python | `.venv` / runtime offline | `environments/<runtime_id>/` dựng từ lock có băm |
| Cập nhật | Git fast-forward (DEV) | `managed_update.py`: xác minh chữ ký Ed25519 → kiểm gói → giải nén an toàn → health ở staging → đổi con trỏ → tự quay lại khi lỗi (đã mô phỏng mất điện 14 điểm) |

**Cổng:** 8501 = Stable (PC2) / production legacy (PC1); **8502 = Development** (trên PC2 là ứng dụng làm việc chính).

**Tin cậy hai khoá (D-23):** trust store tin khoá PC1 `8aa5baa6c8f225f9` và khoá PC2 `d02702dd741c3e4f`; thêm khoá chỉ qua
uỷ quyền có chữ ký; mọi bước cần mật khẩu do người dùng gõ trong console.

### 4.6 An toàn và bất biến
- **Outbox gần như exactly-once:** chèn cùng giao dịch với lịch sử, `dedupe_key UNIQUE`, đích ghim, `SENDING` commit trước
  request, chỉ thử lại lỗi chứng minh chưa ghi, một người gửi mỗi state root, `claim_token`, ghi theo mã tab, ô luôn là chuỗi.
- **Chữ ký chính sách:** băm các tham số nhận diện; Watch chỉ bỏ qua âm tính đã quét trọn với cùng kho + cùng chữ ký. Hằng số
  chống «bóng» cũng là chính sách; hành vi quét cũ khoá bằng golden.
- **Ghi nguyên tử:** ghi tạm → fsync → `os.replace`; file hỏng giữ lại + khôi phục từ `.bak`; lược đồ nâng cấp có sao lưu.
- **Không lộ bí mật:** che cookie/token trong log; thông báo lỗi không chứa nội dung khoá hay nguyên URL bảng.
- **Hook `pre-push` dùng chung:** chỉ cho đẩy nhánh việc; `integration/current` chỉ fast-forward; chặn tag/xoá/force-push;
  quét dòng thêm + thông điệp commit tìm mẫu bí mật (khoá, service account, token, link bảng, cookie, thư mục người dùng).

---

## 5. Hai máy, môi trường và quy trình làm việc

| | PC1 (dự phòng) | PC2 (chính) |
|---|---|---|
| Vai trò (D-23) | Phát triển, review, ký, phát hành khi cần | Phát triển + phát hành chính; **DEV-ONLY** từ 15/10 (D-26) |
| Đang chạy thật | Production legacy `6dc3f9d`, cổng 8501 | **Development 8502** (`ccc3ed6`) với dữ liệu thật; Stable 1.1.1 (8501) chỉ dự phòng |
| Khoá ký | `8aa5baa6c8f225f9` | `d02702dd741c3e4f` |
| Dữ liệu | Của riêng PC1 | PC2 tự xây; không chép giữa hai máy |

**Development vận hành trên PC2** (ngoài Git): mã ở worktree `C:\Dev\TimClipPro_VanHanh` (chỉ fast-forward theo
`integration/current`), Python offline `TimClipPro_DevRuntime`, dữ liệu thật `TimClipPro_DevState\data`, icon Desktop
«TimClipPro DEV». Cập nhật = kiểm DEV rảnh → sao lưu → fast-forward → nạp thử → mở lại. Từ 26/10 **sao lưu bỏ đệm audio**
(mỗi bản ~0,75 GB thay vì ~48 GB), lưu ở `D:\TimClipPro_Dev_SaoLuu`.

**Quy trình Git:** nhánh việc `feature|fix/pc1|pc2/<tên>` từ `integration/current` → mỗi lỗi một test ĐỎ rồi sửa → test đầy
đủ → review độc lập → người dùng duyệt → đẩy + PR → gộp fast-forward vào `integration/current` → cập nhật DEV.

**Làm việc với AI (Claude Code):** ngữ cảnh chung trong `CLAUDE.md`, `docs/ai/` (trạng thái, handoff từng máy, quyết định,
ma trận test, quy trình Git) và luật theo vùng `.claude/rules/`. Các đợt lớn dùng nhiều agent song song (tìm lỗi → tái hiện
bằng test đỏ → phản biện → sửa theo chuỗi trên worktree riêng → gộp → review độc lập).

---

## 6. Lịch sử phát triển

Repo có 261 commit trên `integration/current` (25/07 → 26/10/2026).

### Giai đoạn 1 — Nền móng (25–29/07/2026)
Hồ sơ vi phạm (dossier), giao diện, test; Phase A–E: kiểm `_merge`, **Watch**, **báo cáo dạng ngang** (CSV + Sheets), củng cố
vận hành (ghi nguyên tử, khoá một tiến trình, dọn đệm, huỷ có kiểm soát), mốc chính xác hơn; Phase 2b giới hạn khúc gối 180 s.

### Giai đoạn 2 — Mở rộng tính năng quét (06–21/08/2026)
Gộp repo; sửa treo tạo vân tay; **Scan Pipeline V2** (quét dòng chảy, gửi Sheets không làm treo); chẩn đoán 0 kết quả; chấp
nhận hai bậc; Fast Top-1; bù tốc độ; rào mật độ (hiệu chỉnh trên 1.199 kết quả lịch sử); lớp yt-dlp chung (D-2); tự cập nhật
theo tag Git (bỏ `.exe`); quét tăng dần video rất dài; tab «Danh sách video».

### Giai đoạn 3 — Audit kiến trúc và hardening (07/09–05/10/2026)
Watchdog theo nhịp sống; audit toàn dự án; **hardening 16 phát hiện TCP-01…16** (D-4; nhanh 955 → 1216 test); **«Một video gốc
chung»** (D-5); **truy cập YouTube có kiểm soát** (cầu dao, D-6); **Báo cáo V2** (D-9); PC1 production lên `6dc3f9d`.

### Giai đoạn 4 — Managed Runtime, Stable 1.0.0, hai máy (07–10/10/2026)
Tách dữ liệu khỏi cài đặt, **outbox Sheets bền**, cổng bảo trì, **updater có chữ ký**, launcher + health check (D-10); ghi theo
mã tab, lược đồ v4 (D-11, D-12); **Stable 1.0.0** (D-13); bộ cài one-click PC2 (D-14); ngữ cảnh AI chung (D-15); remote riêng
(D-16–D-18); preview chỉ gắn 8502 (D-19).

### Giai đoạn 5 — Ba bản Stable trong ba ngày (13–15/10/2026)
- **PR #3 Marathon** → **1.1.0**: giới hạn video dài, tiến độ thật, Dừng tắt được FFmpeg, tải phần đầu nhanh (3 giờ trong 9 s).
- **PR #4/#5 CookieFix** → **1.1.1**: cookie đăng nhập chạy bằng Node.js + yt-dlp-ejs; nói rõ khi KHÔNG đăng nhập.
- **PR #6/#7**: hai máy ngang quyền phát hành, uỷ quyền khoá, lock có băm trong repo, hook `pre-push` chung.
- **PR #8/#9**: đồng bộ kênh (video hạn chế là lỗi riêng, chặn trộn kho), tiến độ đồng bộ có cấu trúc.
- **PR #12** (= #10 nhớ client + #11 thanh bên cookie) → **1.1.2**, bản đầu tiên PC2 tự ký.
- **PR #13**: PC2 chuyển **DEV-ONLY** (D-26).

### Giai đoạn 6 — Audit độc lập 25/10 và năm đợt sửa (25–26/10/2026)
- **PR #14**: link «Đoạn vi phạm» dạng `watch?v=<ID>&t=<giây>`.
- **Audit độc lập** (Fable 5.1 tìm lỗi, Opus 5.5 tái hiện bằng test đỏ + 2 người phản biện): **101 phát hiện không trùng**, 6
  vùng: A so khớp/báo cáo, B Sheets/outbox, C kho/cấu hình, D YouTube, E bảo mật/Git, F giao diện.
- **PR #15** (`d04dab9`): chống **«bóng» âm thanh lặp** (D-27) + sửa P0-1 chọn qua cuộc thi 3 phương án; fuzz 2 × 10.000: 0
  dương tính mới, 0 dòng mất.
- **PR #16** (`9476387`): **13 lỗi YouTube** (cookie, 403, lượt tải đồng thời, Dừng, tải lại trang khi đồng bộ…).
- **PR #17** (`a11dac4`): **đợt 2** — 6 P1 + 17 P2 + 4 tranh cãi + 1 tài liệu (kho fsync, sổ kho, outbox kẹt, phiên Streamlit…).
- **PR #18** (`494338c`): **đợt P3** — 50 lỗi nhỏ + 3 test khoá hồi quy; **D-28** giữ chữ ký chính sách.
- **PR #19** (`ccc3ed6`): **chẩn đoán gửi Google Sheets** theo lý do của Google + cột «Vì sao chưa gửi».
- Dọn dẹp: 25 thư mục làm việc tạm, 26 nhánh cục bộ lỗi thời; sao lưu DEV bỏ đệm audio (lấy lại 220 GB trên ổ D:).

---

## 7. Phát hành Stable

| Bản | Commit | Ngày | Ký bởi | Nội dung chính |
|---|---|---|---|---|
| 1.0.0 | `e49340d` | 08–09/10 | PC1 | Managed runtime, outbox Sheets, updater có chữ ký; bộ cài one-click |
| 1.1.0 | `ec1ff71` | 13/10 | PC1 | Marathon: giới hạn video dài, tiến độ thật, tải phần đầu nhanh |
| 1.1.1 | `dc29b33` | 14/10 | PC1 | CookieFix (Node.js + yt-dlp-ejs); build lại ra gói giống từng byte |
| 1.1.2 | `e74c923` | 15/10 (Latest) | **PC2** | Tiến độ đồng bộ kênh, nhớ client, thanh bên cookie |

GitHub Release có `stable-1.1.0`, `stable-1.1.1`, `stable-1.1.2`. Toàn bộ sửa của audit 25/10 (PR #14–#19) **chưa có trong
bản Stable nào** — hiện chỉ chạy trên DEV 8502 của PC2.

---

## 8. Quyết định chính (DECISIONS)

| Mã | Quyết định |
|---|---|
| D-1 | Bỏ hướng đóng gói `.exe`; tự cập nhật theo tag Git |
| D-2 | Mọi tuỳ chọn yt-dlp qua một lớp chung `ytdlp_chung` |
| D-3 | Quy trình làm việc với AI: brief → kế hoạch → TDD → kiểm chứng → báo cáo tiếng Việt |
| D-4 | Hardening 16 phát hiện TCP-01…16 |
| D-5 | Chế độ «Một video gốc chung cho cả lô» |
| D-6 | Truy cập YouTube có kiểm soát; lỗi truy cập không bao giờ là «không vi phạm» |
| D-7 | Không nâng trần `max_matches` khi chưa có ca dương tính thật |
| D-8 | Bỏ link Sheet ghi cứng khỏi `GiamSat.bat` |
| D-9 | Báo cáo V2; PC1 production chạy `6dc3f9d` |
| D-10 | Managed Runtime: tách dữ liệu, outbox bền, Stable có chữ ký + health + quay lại |
| D-11 | Thư mục cài đặt và dữ liệu phải tách; chốt mã tab trước lần ghi đầu |
| D-12 | Outbox đọc/ghi tab theo mã tab, lược đồ v4 |
| D-13 | Stable 1.0.0 từ `e49340d` |
| D-14 | Bộ cài one-click cho PC2 |
| D-15 | Ngữ cảnh AI chung qua Git + sơ đồ nhánh |
| D-16–D-18 | Remote riêng `TimClipPro-dev`; quyền PC2 hai giai đoạn; gộp PR bằng fast-forward |
| D-19 | Preview của Claude chỉ gắn vào 8502 |
| D-20 | Stable 1.0.0 cài lên PC2 trước tái audit |
| D-21 | Stable phân phối bằng GitHub Release |
| D-22 | Repo `TimClipPro-dev` **PUBLIC** (chủ ý) |
| D-23 | PC1 và PC2 ngang quyền phát hành, mỗi máy một khoá |
| D-24 | Lock có băm + wheel docopt + khoá công khai vào repo |
| D-25 | Hook `pre-push` dùng chung + đề xuất ruleset GitHub |
| D-26 | PC2 DEV-ONLY: Development 8502 với dữ liệu thật là ứng dụng chính |
| D-27 | Sửa «bóng» âm thanh lặp trong `_merge`; giữ chữ ký chính sách |
| D-28 | Đợt P3: duyệt golden tự khớp, giữ chữ ký chính sách cho A-7/A-16 (Watch không phải quét lại hàng loạt) |

**Chờ người dùng quyết:** P-2 (PC1 production lên managed), P-4 (lịch sử repo public), P-5 (bật ruleset GitHub),
P-6 (hiển thị cờ «mốc mơ hồ»), P-7 (dòng «bóng» trong lịch sử cũ).

---

## 9. Bài học đã gặp (LOI_DA_GAP)

37 mục trong `TimClipPro/docs/LOI_DA_GAP.md`, ví dụ tiêu biểu:
- Tiến độ đứng 0 % trên Windows tiếng Việt; lỗi bị nuốt mất; cookie rò ra nhật ký; cookie hết hạn tệ hơn không có cookie.
- Tải cả video thay vì chỉ tiếng; quét tăng dần và tải một phần cho video rất dài.
- «Tool hỏng» hoá ra là âm tính đúng — lỗi ở câu chẩn đoán; nhãn Đầu/Giữa/Cuối tính theo file thay vì theo video.
- Bị YouTube chặn thì DỪNG; «bóng» của âm thanh lặp làm lệch mốc và thừa dòng.
- Từ audit 25/10 (mục 19–36): gom theo đường dẫn nhưng tra theo tên; fsync đặt sai chỗ; sổ kho đổi trước khi công bố kho;
  dọn rác chỉ trong `finally`; outbox kẹt khi lần ghi cuối lỗi DB; lỗi một revision chặn cả nhóm; tiêu đề YouTube chưa thoát
  Markdown; rào quét bí mật còn hở khi repo công khai…
- **Mục 37 (tổng kết đợt P3):** mọi lỗi đều nằm ở chỗ **giao** giữa hai phần (lượt ↔ việc nền, sổ ↔ tiến trình, dọn đệm ↔
  quét, cookie ↔ client) — sửa thì phải test đúng chỗ giao đó.

---

## 10. Chất lượng và kiểm thử

**Cách làm cố định:** tái hiện mỗi lỗi bằng dữ liệu giả và một test ĐỎ trước khi sửa; chạy test với mạng bị chặn và bảng mã
cp1252; review độc lập; thử đột biến (cố tình làm hỏng mã xem test có bắt được không).

| Mốc | Suite nhanh | Suite chậm |
|---|---|---|
| 29/07 (Phase 2b) | 248 đạt | 3 |
| 02/10 (hardening) | 1216 đạt / 2 bỏ qua / 0 hỏng | 11/11 |
| 13/10 (Marathon) | 2516 / 2 / 0 | 19/19 |
| 15/10 (hai máy) | 2712 / 2 / 0 | 19/19 |
| 26/10 (sau P3, `3456b4e`) | 3247 / 4 / 0 | 22/22 |
| **26/10 (sau PR #19)** | **3314 ca: 3309 đạt, 2 bỏ qua do môi trường, 2 xfail chờ quyết định E-1** | **22/22** |

- **Lần chạy cuối của suite nhanh:** lần chạy cuối sau PR #19 có 1 ca hỏng: test tự quét repo bắt một mẫu email tài khoản dịch vụ GIẢ chưa có dấu «giả». Đã gắn dấu, chạy lại 2 file liên quan: 84/84 đạt; chưa chạy lại toàn bộ suite nhanh sau bước này.
- **Kiểm mã và so sánh `_merge`:** ruff sạch. Fuzz so sánh `_merge` trên 10.000 tình huống giả: 0 dương tính mới, 0 dòng mất.
- **Thử đột biến** (cố tình làm hỏng mã xem test có bắt được không):
  - outbox: 123/123 (08/10);
  - hai khoá ký: 43/43;
  - chẩn đoán Sheets (PR #19): 49/49.
- **Phát hành:**
  - build lại 1.1.1 chỉ từ repo cho ra gói giống từng byte;
  - diễn tập cập nhật sandbox: 19/19 (PC1), 14/14 (PC2);
  - thu hồi + rollback: 74/74.
- **Các vòng audit:**
  - 06/08: review công việc Codex;
  - 07/09: audit kiến trúc;
  - 02/10: hardening;
  - 05/10: tái audit Báo cáo V2;
  - 08/10: 3 vòng đối nghịch Managed Runtime;
  - **25/10: audit độc lập lớn nhất (101 phát hiện)**.

---

## 11. Trạng thái hiện tại

- **Mã nguồn:** `integration/current` = **`ccc3ed6`**; PR #1–#19 đã đóng (#10, #11 gom vào #12).
- **PC2:** Development 8502 chạy `ccc3ed6` với dữ liệu thật (cập nhật 26/10 14:18, sao lưu trước khi cập nhật); Stable 1.1.1
  (8501) giữ nguyên làm dự phòng; PC2 tự build/ký/phát hành được.
- **PC1:** production legacy `6dc3f9d` (8501), không đổi khi chưa duyệt.
- **Trên máy PC2 chỉ còn 3 thư mục mã:** clone chính `C:\Dev\Tool_Quet` (đang ở `integration/current`), `TimClipPro_CookieFix`
  (môi trường chạy test) và `TimClipPro_VanHanh` (mã của DEV).
- **Tài liệu cần cập nhật:** `docs/ai/CURRENT_STATE.md` còn ghi 15/10; mục «Tiếp theo» của `docs/ai/handoff/PC2.md` trên
  `ccc3ed6` vẫn ghi đợt P3 «chưa đẩy» (thực tế đã gộp qua PR #18).

---

## 12. Việc còn mở

**Người dùng quyết**
1. **B-13** — xoá hồ sơ đích khi lượt quét đang dùng làm việc gửi mồ côi (cần lược đồ v5 hoặc đổi luồng Xoá).
2. **F-16** — cột «Đánh giá» gần như luôn «Rất chắc chắn» (chọn lại cách chia mức).
3. **P-6** — cách hiện cờ «mốc mơ hồ» (3 phương án: `C:\Dev\pc2_test_runs\2026-10-26_audit_p3\P6_PHUONG_AN.md`).
4. **P-7** — đếm dòng «bóng» trong lịch sử cũ (công cụ chỉ đọc `C:\Dev\pc2_test_tools\p7_lich_su_bong`, thiết kế `P7_THIET_KE.md`;
   chỉ chạy trên dữ liệu thật khi được duyệt).
5. 3 phần ghép tuỳ chọn cho P0 (lưới «không bỏ ứng viên cuối của clip», ngưỡng khi bắc cầu lỗ, luật khe cho C').
6. Có phát hành **Stable 1.1.3** gồm các sửa của audit 25/10 hay không.
7. Đề xuất **E-1** (thêm luật chặn đọc khoá Google vào `.claude/settings.json`; 2 test đang chờ) — để PC1 quyết.
8. **Ruleset GitHub** (P-5), P-2, P-4.

**Người dùng làm**
9. Nghiệm thu DEV ~15 phút theo `C:\Dev\pc2_test_runs\2026-10-26_audit_p3\NGHIEM_THU_DEV_DOT2.md`.
10. Xoá các nhánh đã gộp trên GitHub (PC2 không được xoá nhánh trên remote).

**PC1 làm**
11. Review PR #15–#19 (đã chạy dữ liệu thật trên DEV nhưng PC1 chưa review) — gói `GOI_REVIEW_PC1.md`.
12. Chạy bộ đột biến outbox; cập nhật `CURRENT_STATE.md`.

**Còn mở từ trước**
13. Đồng bộ tiếp kênh Joe vào «Kho Joe»; hồ sơ đích Sheets + binding khoá cho DEV; C7; nghiệm thu preview 8502; tái audit
    `e49340d`; sao lưu khoá ký mỗi máy.

---

## 13. Tài liệu tham khảo

| Muốn biết | Đọc |
|---|---|
| Cách dùng hằng ngày | `TimClipPro/HUONG_DAN.md`, `TimClipPro/docs/RUNBOOK.md` |
| Tổng quan hệ thống | `TimClipPro/docs/SYSTEM_OVERVIEW.md`, `SYSTEM_MAP.md`, `MODULE_MAP.md`, `DATA_FLOW.md` |
| Chỉ mục kiến trúc | `docs/ai/ARCHITECTURE_INDEX.md` |
| Báo cáo V2 | `TimClipPro/docs/REPORT_POLICY_V2.md` |
| Chống «bóng» | `TimClipPro/docs/BONG_AM_THANH_LAP.md` |
| Truy cập YouTube | `TimClipPro/docs/YOUTUBE_ACCESS_RELIABILITY.md` |
| Managed / cập nhật / phát hành | `MANAGED_RUNTIME_DESIGN.md`, `MANAGED_UPDATE.md`, `PHAT_HANH_HAI_MAY.md`, `UY_QUYEN_KHOA.md` |
| Quyết định | `docs/ai/DECISIONS.md` |
| Bài học | `TimClipPro/docs/LOI_DA_GAP.md` |
| Test cần chạy | `docs/ai/TEST_MATRIX.md` |
| Quy trình Git | `docs/ai/GIT_WORKFLOW.md` |
| Trạng thái từng máy | `docs/ai/CURRENT_STATE.md`, `docs/ai/handoff/PC1.md`, `docs/ai/handoff/PC2.md` |
| Bằng chứng audit 25/10 (ngoài Git, PC2) | `C:\Dev\pc2_test_runs\2026-10-25_audit\`, `2026-10-26_audit_dot2\`, `2026-10-26_audit_p3\`, `2026-10-26_sheets_chan_doan\` |

---

## 14. Phụ lục: thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Kho (vân tay) | Tập vân tay âm thanh của các clip gốc (file `.pklz`) dùng để tra |
| Vân tay / hash | Các «điểm đặc trưng» của âm thanh; càng nhiều hash khớp thì bằng chứng càng mạnh |
| Khúc | Một đoạn 1 giờ của video được cắt ra để so khớp |
| Bậc A / bậc B | Hai tiêu chí chấp nhận kết quả (mạnh / clip ngắn) |
| Top-N | Số đoạn bằng chứng tốt nhất giữ lại cho mỗi video (mặc định 5) |
| «Bóng» | Căn chỉnh giả do nhạc lặp, làm lệch mốc và sinh dòng thừa (đã sửa, D-27) |
| Mốc mơ hồ | Khi âm thanh lặp y hệt, nhiều mốc đúng như nhau (P-6, chưa hiển thị) |
| Chữ ký chính sách | Mã băm các tham số nhận diện; đổi thì Watch quét lại âm tính cũ |
| Outbox / hàng đợi gửi | Hàng đợi bền gửi kết quả lên Google Sheets, không mất việc khi tắt máy |
| Hồ sơ đích | Cấu hình một bảng Google Sheets nhận kết quả (link, tab, định dạng, khoá) |
| Binding khoá | Gắn tên với file khoá tài khoản dịch vụ Google (không lưu nội dung khoá) |
| Watch | Lượt giám sát tự động theo danh sách kênh/link |
| Legacy / Managed | Chế độ chạy kiểu cũ (thư mục làm việc) / bản Stable cài đặt có chữ ký |
| DEV 8502 | Bản Development chạy cổng 8502 — ứng dụng làm việc chính trên PC2 |
| `integration/current` | Nhánh tích hợp đã kiểm; nguồn để cập nhật DEV và build Stable |
| P0–P3 | Mức nghiêm trọng của lỗi (P0 nặng nhất, P3 nhỏ) |
| Test đỏ / xanh | Test hỏng trên mã cũ (chứng minh có lỗi) / đạt sau khi sửa |
| Fuzz | So sánh mã cũ và mới trên hàng nghìn tình huống giả sinh ngẫu nhiên |
