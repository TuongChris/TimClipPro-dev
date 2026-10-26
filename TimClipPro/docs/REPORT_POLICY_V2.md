# Chính sách báo cáo V2 — chuẩn hoá báo cáo cho các lượt quét MỚI

Ngày: 04/10/2026. Nhánh `feature/report-policy-v2` (gốc `7ee527a`). Bằng chứng kiểm thử:
`docs/REPORT_POLICY_V2_VALIDATION.md`.

## 1. Bốn thay đổi, chỉ cho lượt quét mới

| # | Báo cáo cũ (giữ nguyên cho kết quả/lịch sử cũ) | Báo cáo V2 |
|---|---|---|
| 1 | Tên video bị nối `[QUÉT MỘT PHẦN — …]` (`nhan_pham_vi`) ở bảng ngang 34 cột và bảng dọc 16 cột | Tên đúng như yt-dlp trả (`title`), không hậu tố. Phạm vi quét nằm ở trường riêng |
| 2 | Link nhảy mốc ở bảng ngang lùi 3 giây (`bang_ngang.dinh_dang_doan`: `int(start) - 3`) | Mốc hiển thị và `t` của link là **cùng một giây**: `00:15:15` ↔ `t=915` |
| 3 | Ngày đăng đã quy đổi sang `Asia/Ho_Chi_Minh` từ `timestamp` (`publication_date.py`, từ 07/08/2026) | `upload_date` **nguyên bản** của yt-dlp, không đổi múi giờ: `20260315` → `15/03/2026` |
| 4 | Link video gốc `https://youtu.be/<ID>` | `https://www.youtube.com/watch?v=<ID>`, dựng từ mã resolver chấp nhận (định nghĩa: §2 «Link video gốc») |

Không đổi: kết quả matching (clip được chọn, `start_s`/`end_s`/`matched_s`, số hash, ngưỡng,
`_merge`, `max_matches`, search-depth, Top-N, bù tốc độ), chữ ký chính sách nhận diện
(`chu_ky_chinh_sach`, nên Watch KHÔNG quét lại video cũ), lịch sử cũ, Sheet cũ, `clips_meta.json`
cũ, tên file/mã lưu trữ/khoá vân tay trong kho.

> **Lưu ý về ngày (quyết định sản phẩm cần biết):** ngày 07/08/2026 (`6cad9d9`) tool đã CHUYỂN
> từ `upload_date` sang ngày quy đổi giờ Việt Nam vì người dùng báo ngày lệch 1 ngày so với
> YouTube. V2 quay lại `upload_date` nguyên bản theo yêu cầu mới: với video phát hành từ 17:00
> UTC trở đi, ngày V2 sớm hơn 1 ngày so với ngày người xem ở Việt Nam thấy. Luật cũ vẫn còn
> nguyên cho kết quả cũ.

## 2. Hợp đồng giá trị (`bao_cao_v2.py`, module thuần)

* **Mốc** — `giay_moc(x)`: số thực hữu hạn không âm → `floor(x)`; NaN, vô cực, số âm, bool,
  chuỗi → `None` (ô hiện `?`, không có link). Cắt phần lẻ như `engine.hhmmss` (trình phát cắt):
  `915.0` và `915.8` đều là `00:15:15` và `t=915`. Giờ vượt 24 (`25:01:01`) được giữ.
* **Link nhảy mốc** — `link_nhay(source_id, source_ref, giay)`:
  `https://www.youtube.com/watch?v=<ID>&t=<giây>` (từ 25/10/2026, chủ dự án chọn; trước đó
  `https://youtu.be/<ID>?t=<giây>` — ảnh chụp đã lưu giữ nguyên link cũ, không hồi tố; `t` phải
  sau `&`, viết `?t=` thì giây dính vào mã video). Link luôn dựng MỚI từ mã video (không nối chuỗi
  vào URL người dùng → không bao giờ có hai `t`, `start`, `#t`). Không có `source_id` hợp lệ thì chỉ đọc mã từ URL YouTube thật (`youtube.com`,
  `m.youtube.com`, `youtube-nocookie.com`, `youtu.be`); host giả kiểu `youtube.com.evil.example`,
  tên file `[ID].mp4`, mã trần → không có link.
* **Link video gốc** — `url_goc_chuan(video_id)`: chỉ từ mã 11 ký tự resolver CHẤP NHẬN, tức là
  (a) mã lấy từ `clips_meta.json`/snapshot của kho, hoặc (b) hậu tố `[ID]` của tên file đúng ngữ
  pháp bộ tải `YYYYMMDD - Tiêu đề [ID].đuôi` khi kho không có mục metadata dùng được
  (`filename_fallback`, trạng thái `partial`). Resolver `ambiguous` (metadata nói mã khác hậu tố)
  hoặc không có mã (`basename_fallback`) → ô trống, không bịa. Mã (b) KHÔNG được đối chiếu với
  YouTube: link từ tên file chỉ đáng tin bằng chính tên file. File do tool tải luôn mang mã thật;
  file người dùng tự đặt tên/tự chép vào kho theo đúng ngữ pháp đó mà kết thúc bằng một từ 11 ký
  tự trong ngoặc (`… [Compilation].mp3`) cho link tới video KHÔNG tồn tại (`watch?v=Compilation`)
  — giới hạn đã chấp nhận (`HARDENING_FIX_MATRIX.md` TCP-12, audit A-6; test
  `tests/test_link_goc_tu_ten_file.py`). Sheets 34/16 cột và hồ sơ không có cột nguồn của link,
  nên giao diện cảnh báo khi có video gốc phục hồi từ tên file; CLI/Watch không có cảnh báo đó.
  Link video VI PHẠM giữ nguyên URL người dùng đã quét (không tự đổi link kênh/playlist).
* **Ngày** — `NgayNguon(gia_tri, nguon, ly_do_thieu)`; hiển thị `DD/MM/YYYY` giữ đúng ngày lịch.
  Thiếu thì ô trống và `ly_do_thieu` nói vì sao — không lùi về ngày quy đổi, `release_*`,
  `timestamp` hay ngày trong tên file.
* **Tên** — video YouTube: `title_raw` của `Engine.youtube_info` (yt-dlp nguyên văn). Wrapper cũ
  lùi `title` về URL khi thiếu — URL đó KHÔNG được coi là tên (ô trống + lý do). Quét file: tên
  file (nguồn `ten_file`, không mạo nhận là tiêu đề YouTube). Tên có `[…]` thật được giữ nguyên.

## 3. Vòng đời: ghim chính sách, chụp một lần, không hồi tố

1. **Ghim** — `Engine._ban_sao_cho_job()` (ranh giới tạo job: `scan_youtube`/`scan_media` gọi
   thẳng, `scan_iter` cho cả batch, `phien_job` cho lô nguồn chung, mỗi video Watch) gắn
   `chinh_sach_bao_cao = bao_cao_v2.CHINH_SACH_HIEN_HANH` lên bản ghim. Engine gốc không mang
   chính sách. `ScanResult.bao_cao` mặc định `None` = luật cũ (dataclass không mặc định V2).
2. **Chụp** — cuối `_scan_youtube` (và `_scan_media` khi quét file, `_ket_qua_bo_qua` khi cầu dao
   bỏ qua video): sau chọn lọc + bổ sung ngày, SAU khi ghi chú đã chốt, TRƯỚC `save_job` và trước
   khi `scan_iter` gọi `on_video` (nơi xếp hàng Sheets). `BaoCaoV2` là dataclass frozen chỉ chứa
   giá trị (không tham chiếu config/resolver/dict yt-dlp).
3. **Xuất** — `Engine.to_rows`, `Engine.to_rows_ngang`/`bang_ngang.dung_dong_ngang`,
   `dossier.dung_ho_so`, `Engine.export_csv*`, `Engine.dong_gui_sheets` (app, Watch) đọc chính sách
   TỪ KẾT QUẢ: có ảnh chụp → dòng từ ảnh chụp (`bao_cao_v2.dong_ngang/dong_doc`), không →
   luật cũ y nguyên, ảnh chụp lỗi/hỏng → CHẶN (mục 9). Không exporter nào hỏi hằng hiện hành hay
   resolver hiện tại cho kết quả V2.
4. **Lưu** — `save_job` ghi ảnh chụp vào bảng RIÊNG `bao_cao_job(job_id, chinh_sach, du_lieu,
   created_at)` trong cùng giao dịch với dòng `jobs`/`matches`. Bảng `jobs` không thêm cột.
5. **Xuất lại sau khởi động lại** — `Engine.bao_cao_cua_job(job_id)` /
   `dong_bao_cao_job(job_id, dang_ngang=…)` đọc đúng giá trị đã chốt; tab «Lịch sử» có nút tải
   báo cáo ngang/dọc từ ảnh chụp. Metadata kho sửa sau lần quét không làm đổi báo cáo cũ.
6. **Lịch sử cũ** — dòng không có ảnh chụp = luật cũ, không bao giờ tự nâng thành V2. Lịch sử
   cũ chưa từng lưu tên/ngày/link gốc nên **không dựng lại được** báo cáo đã xuất lúc đó (giao
   diện nói rõ điều này); không có backfill.
7. **Hàng đợi Sheets** — dòng được chốt LÚC XẾP HÀNG (`SheetDelivery.rows`); thử lại gửi đúng
   các dòng đó, không dựng lại bằng resolver/chính sách mới. Hàng đợi chỉ nằm trong bộ nhớ (như
   trước): tắt app khi còn việc chờ là mất việc đó — kết quả đã lưu lịch sử thì tải lại được.
8. **Quét lại một URL cũ** = một lượt quét MỚI (dòng lịch sử mới, ảnh chụp mới) — không ghi đè
   dòng cũ hay hàng Sheet cũ.
9. **Ảnh chụp lỗi/hỏng — không bao giờ lùi về luật cũ** (sửa sau audit độc lập 05/10/2026, P1-02).
   `ScanResult.bao_cao`/`bao_cao_cua_job` có ĐÚNG ba trạng thái: `None` = luật cũ thật (job không
   ghim V2 / lịch sử không có dòng `bao_cao_job`); `BaoCaoV2` = V2 bình thường;
   `bao_cao_v2.LoiBaoCaoV2` = lượt quét V2 không có ảnh chụp dùng được:
   * `loi_tao` — dựng ảnh chụp lỗi (kể cả bước chuẩn bị video gốc). Kết quả khớp, phạm vi, chẩn
     đoán và dòng `jobs`/`matches` giữ nguyên (quét không thành âm tính); `bao_cao_job` lưu DẤU
     LỖI `{"loi_bao_cao": {"loai", "ngoai_le"}}` chỉ gồm tên lớp ngoại lệ (không thông điệp thô,
     không dict yt-dlp; nhật ký cũng chỉ ghi tên lớp + vị trí code); ghi chú lượt quét nói rõ.
   * `hong` — dòng `bao_cao_job` không đọc được (JSON hỏng, không phải object, thiếu trường,
     phiên bản ảnh chụp hay chính sách lạ). Không dựng lại bằng resolver hiện tại.

   Cả hai: mọi exporter (bảng dọc 16 / ngang 34 cột, CSV và file phạm vi, hồ sơ Markdown,
   `dong_gui_sheets`, xuất lại từ lịch sử) ném `LoiXuatBaoCaoV2` TRƯỚC khi mở file hay dựng dòng;
   hàng đợi Sheets không xếp việc (lỗi đó là vĩnh viễn, không thử lại); giao diện, Watch và CLI
   bỏ kết quả đó khỏi CSV/Sheets và BÁO lỗi (phần hợp lệ của lô vẫn xuất); tab «Lịch sử» báo lỗi,
   không có nút tải, không gọi là «lần quét cũ». Trạng thái giữ nguyên qua khởi động lại. Khắc
   phục: quét lại video (lượt quét mới = ảnh chụp mới). Lô nguồn chung không dùng ảnh chụp từng
   lượt — dấu V2 của lô là chính sách ĐÃ GHIM, không đổi.
10. **Xoá một lần quét** (`Engine.delete_job`, P1-01): xoá `bao_cao_job`, `matches`, `jobs` của
    đúng job đó trong CÙNG một giao dịch; lỗi giữa chừng thì cả ba cùng lùi lại. Lần quét khác
    không bị đụng.

## 4. Ngày đăng nguyên bản

| Video | Nguồn ngày V2 (theo thứ tự) |
|---|---|
| Được quét (YouTube) | `youtube_info()["upload_date_raw"]` (chuỗi yt-dlp, đọc TRƯỚC resolver cũ). KHÔNG đọc `upload_date` của dict wrapper — khoá đó đã mang ngày quy đổi |
| Được quét (file) | Không có — ô trống («quét file trên máy — không có ngày đăng YouTube») |
| Video gốc | (1) `clips_meta.json`: `upload_date_raw` (clip tải từ bản này); (2) `publication_date` khi `publication_date_source == "upload_date"`; (3) ngày đã bổ sung trong job/lượt; (4) bổ sung qua YouTube nếu được bật; (5) thiếu + lý do |

**Kho hiện có (đo 04/10/2026, chỉ đọc; số liệu ở báo cáo ngoài repo):** hai trong ba kho
chỉ có ngày đã quy đổi (`timestamp`/`release_timestamp`) cho mọi clip; kho còn lại chỉ một phần
clip có ngày tương đương nguyên bản. Ngày quy đổi không suy ngược được `upload_date` (thiếu giờ),
nên V2 để trống — `ngay_kho_quy_doi` vẫn nằm trong ảnh chụp để chẩn đoán, không bao giờ hiển thị
như ngày nguyên bản.

**Bổ sung qua YouTube** (`Config.bo_sung_ngay_goc`, mặc định TẮT; ô «Bổ sung ngày đăng gốc từ
YouTube» ở thanh bên): chỉ lượt QUÉT YOUTUBE thường, chỉ video gốc ĐÃ CHỌN (Top-N) còn thiếu
ngày; lô nguồn chung chỉ video gốc ĐƯỢC BÁO CÁO. Mỗi mã video hỏi tối đa một lần trong job /
lượt Watch (`_BoNhoNgayGoc`), trần `bo_sung_ngay_goc_toi_da` (20), giãn nhịp
`ytdlp_sleep_requests_s`, đi qua `youtube_info` → `PhienYouTube` (phân loại lỗi, thử lại hữu
hạn, cầu dao); cầu dao mở hoặc đã bấm Dừng thì không gửi gì. Video gốc bị gỡ/lỗi mạng KHÔNG
đổi kết quả khớp và không đặt `loi_truy_cap` của lượt quét — chỉ ghi lý do thiếu ngày. Không
ghi ngược vào `clips_meta.json`, không có cache trên đĩa (ngày đã bổ sung nằm trong ảnh chụp).

**Clip mới:** `channel.py` ghi thêm `upload_date_raw` cạnh `upload_date`/`publication_date` cho
entry vừa tải (không đổi tên file, mã lưu trữ, entry cũ).

## 5. Phạm vi quét khi tên đã sạch

Phạm vi (`quet_day_du`, `quet_mot_phan`, `ly_do_pham_vi`, `vung_da_khop`, `vung_loi`,
`dat_muc_tieu`, mô tả, ghi chú) nằm ở: trường cũ của `ScanResult` (giữ nguyên), ảnh chụp
(`BaoCaoV2.pham_vi`), hộp «Chưa quét trọn» trên giao diện, file phụ `<csv>.pham_vi.csv` cạnh mọi
CSV V2 (`Engine.export_csv*`, nút «⬇️ Tải phạm vi quét (CSV)»), mục «Phạm vi đã quét» của hồ sơ
Markdown, cột «Phạm vi đã quét» của CSV nguồn chung.

**Giới hạn:** bảng Google Sheets 34/16 cột không có cột phạm vi (hợp đồng Apps Script giữ nguyên)
nên hàng V2 trên Sheet độc lập KHÔNG còn cho biết video chỉ quét một phần. Ngoại lệ (audit A-4):
dòng «không thấy» của bảng dọc 16 cột / CSV khi CHƯA quét trọn mang phạm vi ngay trong ô kết quả
(«(không tìm thấy clip nào — QUÉT MỘT PHẦN: …)», `bao_cao_v2._han_che_am_tinh`) — vì «Giới hạn quét
video dài» cho ra `ok` + 0 khớp + chỉ phần đầu, âm tính trơn sẽ đọc thành kết luận cho cả video. Chưa ghi ghi chú ô
(note) — muốn làm thì phải định vị đúng hàng vừa ghi từ phản hồi API, việc của vòng sau.

## 6. Google Sheets

* Giá trị V2 gửi nguyên văn bằng `RAW` (Sheets không hiểu `=…` là công thức, nên không thêm dấu
  `'` — dấu đó sẽ hiện ra trong ô). CSV vẫn chặn công thức (`o_bang_tinh_an_toan`) ở tầng ghi.
  Ngày gửi bằng chuỗi `DD/MM/YYYY` (không bị diễn giải lại theo locale), số vẫn là số.
* Gửi V2 ở chế độ **nghiêm ngặt** (`SheetsExporter.append(..., nghiem_ngat=True)`): hàng 1 phải
  đúng tiêu đề của công cụ theo thứ tự (cột người dùng thêm SAU cột cuối thì được). Có dữ liệu mà
  thiếu/sai tiêu đề → `LoiHeaderSheet` (lỗi vĩnh viễn, không thử lại), KHÔNG chèn/sửa hàng 1,
  KHÔNG append (append theo vị trí dưới tiêu đề sai là lệch cột). Không bao giờ
  `ghi_de`/clear/sort/resize/update hàng cũ. Đường gửi cũ giữ nguyên hành vi cũ. Watch gặp lỗi
  tiêu đề thì thôi gửi cả lượt và báo một lần.
* **Hàng 1 trống CHƯA phải bảng rỗng** (sửa sau audit, P1-03): hàng 1 trống trong bề rộng tiêu đề
  → dò LẦN HAI toàn trang tính (`get_all_values`, chỉ ở nhánh này; đường chính — hàng 1 đúng tiêu
  đề — vẫn đúng một lần đọc). Có bất kỳ ô nào mang giá trị (hàng 2 trở đi, cột ngoài bề rộng báo
  cáo, một ô lẻ ở xa, kể cả ô chỉ có dấu cách) → `LoiHeaderSheet` nêu đúng ô, không ghi gì. Trống
  thật → ghi tiêu đề MỘT lần rồi ghi dòng. Lần dò lỗi/hết giờ → lỗi đó được ném ra (hàng đợi thử
  lại hữu hạn như lỗi mạng), không ghi gì. Không dùng `row_count` làm bằng chứng có dữ liệu.
* Apps Script trong repo chỉ đọc giá trị theo tên cột — không cần sửa (fixture:
  `tests/test_bao_cao_v2_apps_script.py`); bản gắn vào Sheet thật không được đụng.

## 7. Lược đồ `lichsu.db` phiên bản 2

`lich_su.dam_bao_luoc_do`: nâng `user_version` 1 → 2 bằng `CREATE TABLE IF NOT EXISTS
bao_cao_job` — sao lưu trước bằng SQLite backup API (`lichsu.db.v1_<thời điểm>.bak`), trong giao
dịch ghi, chạy lại không làm gì thêm. Không đổi dòng/cột cũ. Rollback: bản cũ ghi theo tên cột
và kiểm `user_version < 1 or thiếu cột` — vẫn đúng trên DB v2; muốn bỏ hẳn thì khôi phục bản
`.bak`. **Chưa áp lên production** (sẽ tự chạy ở lần mở app đầu tiên sau khi triển khai).

Vòng sửa sau audit KHÔNG đổi lược đồ (`NO_NEW_SCHEMA_MIGRATION_REQUIRED`): dấu lỗi V2 nằm trong
cột `du_lieu` sẵn có của `bao_cao_job`; có dòng = lượt quét V2, không dòng = luật cũ. Rollback về
bản cũ sau khi đã chạy V2: bản cũ không biết `bao_cao_job` nên xoá lần quét bằng bản cũ để lại ảnh
chụp mồ côi — vô hại vì `jobs.id` là `AUTOINCREMENT` (id không bao giờ được cấp lại cho lần quét
khác); không có bước dọn tự động.

## 8. Mốc kết thúc — điều tra ca người dùng nêu (không đổi số)

Mã video, lịch sử và MỌI số đo của ca thật nằm ở báo cáo nghiệm thu NGOÀI repo (repo công
khai). Cặp video được xác nhận trong lịch sử; tái hiện offline trên bản sao (mã 7ee527a, cùng blob
engine với production) ra đúng từng số của match đã lưu.

Vì sao mốc kết thúc sớm hơn «mốc đầu + thời lượng clip gốc» (ca người dùng: hơn một phút): tool
gọi `audfprint match --find-time-range` và không truyền `--time-quantile`, nên audfprint dùng mặc
định 0,05 — khoảng thời gian báo về chỉ phủ từ phân vị 5 % tới 95 % của các hash khớp
(`audfprint_match.py` `_calc_time_ranges`). Kết quả: đầu và cuối vùng khớp bị cắt khoảng 5 % mỗi
bên. Đo lại trên khúc chứa đoạn khớp với kho một clip: hạ quantile xuống 0,01 rồi 0 thì mốc cuối
dời dần tới gần «mốc đầu + thời lượng gốc»; audio quanh mốc đó cho thấy clip gốc vẫn phát gần
hết, và clip kế tiếp bắt đầu đúng tại «mốc đầu + thời lượng gốc». Mốc ĐẦU là mốc ngoại suy
(`bat_dau − t_clip`), không bị cắt.

Sửa đúng gốc là đổi tham số khớp (`--time-quantile`) — nhưng 0 làm mảnh yếu phình ra hàng trăm
giây, và mọi giá trị khác đều đổi `khop` → mật độ hash → chấp nhận/gộp: vượt phạm vi, cần duyệt
và hiệu chỉnh riêng. V2 GIỮ NGUYÊN `end_s`; không đặt `end = start + thời lượng gốc`.

## 9. Giới hạn còn lại

* Sheet độc lập không mang phạm vi quét (mục 5).
* Ngày video gốc của kho cũ trống tới khi bật bổ sung (mạng) hoặc tải lại clip.
* Mốc kết thúc vẫn là phân vị 95 % (mục 8) — `END_CASE_PENDING`.
* Lịch sử trước V2 không dựng lại được báo cáo đã xuất.
* Lượt quét có báo cáo V2 lỗi/hỏng chỉ khắc phục bằng quét lại (không có nút «dựng lại báo cáo» —
  dựng lại bằng resolver hiện tại là đúng điều V2 cấm).
* Hàng đợi Sheets vẫn chỉ trong bộ nhớ; nút «📊 Đẩy lên Google Sheets» bấm hai lần vẫn ghi hai lần
  (hành vi cũ, không có đối soát exactly-once).
