# Quyết định — TimClipPro

Mỗi mục: quyết định · vì sao · bằng chứng (commit / tài liệu). Mới nhất ở trên. Đổi một quyết định = thêm mục MỚI ghi
rõ «thay D-xx», không sửa lịch sử. Đường dẫn `docs/…` không có tiền tố là `TimClipPro/docs/…`.

## Đang chờ người dùng quyết
- **P-2 PC1 production lên bản managed** — lược đồ `lichsu.db` v2 → v4; cần sao lưu + duyệt riêng.
- **P-4 Lịch sử repo public** — có dữ liệu cần xử lý (chi tiết ngoài Git); đóng repo public hay viết lại lịch sử đều
  cần duyệt (force-push đang bị cấm).
- **P-5 Bật ruleset GitHub** (`release/github/*.json`, D-25) — một lệnh `gh api`, chủ repo duyệt.
- **P-6 Thể hiện cờ «mốc mơ hồ» (D-27)** trên giao diện, CSV, Google Sheets, lịch sử — đổi chính sách báo cáo V2, PR
  riêng (`TimClipPro/docs/BONG_AM_THANH_LAP.md` §4 có phương án giữ hợp đồng 34 cột). Chưa có thì dòng mơ hồ (âm thanh lặp
  y hệt, nhiều mốc đúng như nhau) vẫn gửi như mốc chắc chắn. Từng là BLOCKER phát hành Stable; PC2 DEV-ONLY (D-26) dùng
  D-27 hằng ngày vì nó đã tốt hơn hẳn mã cũ (mã cũ gửi cả dòng «bóng» lẫn mốc lệch như chắc chắn).
- **P-7 Lịch sử có dòng «bóng»** (lượt quét trước D-27, kể cả dữ liệu THẬT của DEV PC2 từ 15/10): truy vấn CHỈ ĐỌC tìm job
  nhiều dòng cùng clip chồng vùng để kiểm lại tay — không quét lại tự động, không sửa dòng đã gửi Sheet.

## D-48 Tên file tải về không dấu cách, không ký tự đặc biệt (người dùng, 2026-11-12) — thay phần tên file của D-47
Video/audio tải về: «Tieu_de_khong_dau_<mã>.đuôi» (vd. `The_Weirdest_Anomaly_Game_Kun_Kun_Nest_RMpCKfipD-Y.mp4`; chỉ-tiếng
`…_<mã>.m4a`, bỏ dấu «.audio»); chỉ còn chữ không dấu, số, «_», «-» (`tai_video_goc.ten_khong_dau`; tiêu đề không phải chữ
Latin → chỉ còn mã). Trùng tên thêm «_2». Đoạn cắt `…_00-01-23_00-02-45.mp4`, video ghép `Video_ghep_<ngày giờ>` (tên gõ
tay cũng được làm sạch), chỉnh âm file trong máy `…_am_luong_YouTube.đuôi`. Thumbnail vẫn «<mã>.jpg». «Đã có»/«trùng» nhận
cả tên mới lẫn tên cũ «[mã]» (`_RE_MA_CUOI_TEN` bỏ qua `.m4a` = chỉ-tiếng). Tiêu đề hiển thị trong bảng kết quả giữ nguyên.

## D-47 Thumbnail tên = mã video; «Chỉ audio» rõ ràng, ra M4A (người dùng, 2026-11-12) — thay một phần D-45, D-37
Thumbnail (tải theo link + cả kênh) lưu «<mã>.jpg» (vd. `RMpCKfipD-Y.jpg`) thay «tiêu đề [mã].jpg» — người dùng muốn tên
không dấu cách; «đã có» nhận cả hai kiểu tên (`ma_da_co(anh=True)`). Tab «⬇️ Tải video gốc» có lựa chọn đầu tab «🎬 Video /
🎵 Chỉ audio» (mức «Chỉ tiếng» trước đó nằm khuất cuối ô chất lượng); chỉ-tiếng = `ba[ext=m4a]/ba/b` + `FFmpegExtractAudio`
m4a → luôn ra «tiêu đề [mã].audio.m4a» (Opus/WebM cũ Premiere/CapCut không mở; M4A của YouTube có sẵn nên không nén lại).
Tab «Tải cả kênh» và cắt đoạn dùng chung mức này. Video giữ tên cũ.

## D-46 Cắt / chỉnh âm / ghép video ĐÃ CÓ trong máy (người dùng, 2026-11-11)
Tab mới «🛠️ Video trong máy»: đường dẫn file (hoặc thư mục — chỉ file media ngay trong đó, không vào thư mục con) +
«Từ/Đến» + ô âm lượng → `video_trong_may.xu_ly`. Ghép: tab «🎞️ Ghép» nhận cả đường dẫn file, trộn với link. Bất biến: file
GỐC không bao giờ bị sửa/đổi tên/xoá — cắt ra file mới (`cat_video_goc.cat_mot`, tách từ `tai_doan`, dùng chung), chỉnh âm
ra file mới (`am_luong.chuan_hoa(dich=…)`; đã ở mức thì không tạo bản sao), ghép chỉnh âm trên bản trong thư mục tạm và
không xoá file trong máy. Đường dẫn không có → dừng trước khi tải gì.

## D-45 Tab thumbnail: lấy thumbnail cả kênh (người dùng, 2026-11-11)
Ô «Link kênh YouTube cần lấy thumbnail» + «Số thumbnail mới nhất (0 = cả kênh)» trong tab «🖼️ Tải thumbnail» → `tai_kenh(
thumbnail=True)`: liệt kê tab Videos rồi tải THẲNG ảnh theo địa chỉ cố định `i.ytimg.com/vi/<mã>/maxresdefault.jpg` (lùi
sddefault → hqdefault khi 404) bằng `YoutubeDL.urlopen` trong `PhienYouTube.chay` (bỏ cookie, giữ timeout/proxy, cầu dao,
phân loại lỗi). Bản đầu trích thông tin từng video: đo thật 8 s/ảnh (giãn nhịp + giải JS); tải thẳng 0,17 s/ảnh, cùng tên file. «Đã có» của ảnh
tính riêng (`ma_da_co(anh=True)`: «[mã].jpg»): bị chặn giữa chừng thì bấm lại lấy tiếp.

## D-44 Twitch 1440p: danh sách chất lượng qua proxy + đăng nhập, video tải thẳng (người dùng, 2026-11-11)
Tab «Tải video gốc» tải được Twitch từ trước (yt-dlp), nhưng chỉ tới 720p60. Danh sách ẩn «unavailable-media» của usher
ghi lý do khoá 1440p: từ VN `AUTHZ_GEO` + `AUTHZ_NOT_LOGGED_IN`; qua proxy Mỹ chỉ còn `AUTHZ_NOT_LOGGED_IN`. Người dùng chọn
cách miễn phí: Windscribe Free (10 GB/tháng) bật Proxy Gateway + Split Tunneling Inclusive rỗng (máy vẫn đi VN). Mục gập
«🟣 Twitch» ở tab Tải: hai ĐƯỜNG DẪN (file một dòng proxy, cookies.txt có `auth-token`), nhớ qua «Lưu cấu hình», là khoá
riêng của máy khi đóng gói. CHỈ link twitch.tv: bước trích (`extract_info(process=False)`) qua proxy + đúng cookie
twitch.tv (bỏ cookie YouTube và mọi miền khác), bước tải `process_ie_result` THẲNG — khúc CDN không chặn VN, hạn mức VPN
không hao. Proxy tắt/file sai → báo lỗi rõ, không lặng lẽ tải 720p; câu lỗi không chứa mật khẩu/cookie. Ghép (≤ 1080p)
không cần. Mã: `ytdlp_chung.MoKhoaTwitch`.

## D-43 Đưa âm lượng video tải về mức YouTube (người dùng, 2026-11-10)
Đo thật: video Joe Bartolozzi tải về -28,5 LUFS, SSS/TikTok -14; xem trên YouTube nghe to nhờ «Âm lượng ổn định» (người
dùng tắt đi thì nhỏ y như file tải). Ô tick «🔊 Đưa âm lượng về mức YouTube (-14 LUFS)» (tick sẵn) ở tab Tải video gốc
(cả cắt đoạn) và Ghép: `loudnorm` hai lượt, đỉnh ≤ -1 dBTP, hình chép nguyên, tiếng nén lại (AAC 192k; vỏ webm/opus →
Opus 160k), giữ tần số lấy mẫu. Gần mức (≤ 1 LU) thì giữ nguyên từng byte. Ghép: chỉnh TỪNG video trước khi nối. Không
chọn luồng DRC của YouTube (không phải video nào cũng có). Mã: `TimClipPro/am_luong.py`.

## D-42 Tải video theo link: chỉ lấy một đoạn «Từ … Đến …» (người dùng, 2026-11-09)
Hai ô «Từ»/«Đến» trong tab «⬇️ Tải video gốc» (trống = cả video, một đoạn dùng chung cho mọi link). Người dùng chọn
tải TRỌN (4 kết nối, D-40) rồi cắt bằng FFmpeg có nén lại đoạn cắt (`-ss` trước `-i`, H.264 crf 18 + AAC): đúng từng
khung hình; KHÔNG tải một phần bằng yt-dlp `download_ranges` (một kết nối, `-c copy` chỉ cắt ở khung hình chính).
Đoạn ra lệch độ dài > 0,06 s thì không tin; đúng thì xoá video trọn (người dùng chọn), sai/mốc vượt độ dài thì giữ ở
`.timclip_cat` để bấm lại khỏi tải lại. Mã: `TimClipPro/cat_video_goc.py`.

## D-41 Ghép video: tự chuyển video lệch thông số cho khớp video 1 (người dùng, 2026-11-09)
Thay một phần D-39 («lệch thì dừng»): người dùng gặp video 60 hình/giây giữa video 29,97 — chuyện thường gặp. Chỉ video
lệch được nén lại (libx264 veryfast crf 18; fps, thu nhỏ giữ tỉ lệ + viền, profile, kiểu điểm ảnh, nhịp thời gian của
video 1); tiếng chép nguyên khi đã khớp. Bản chuyển để ở `.timclip_ghep/khop/` (dùng lại khi bấm ghép lại). Chuyển xong
vẫn lệch → dừng như cũ. Video 1 không phải H.264 + AAC → dừng như cũ. Đo thật: 48 phút 60 hình/giây → 29,97 mất 6,5 phút,
tiếng ở mốc nối lệch 0 ms.

## D-40 Tải video theo link bằng 4 kết nối song song (người dùng, 2026-11-09)
Đo thật cùng video 334 MB: một kết nối lúc 0,78 MB/s (lượt ghép của người dùng), lúc 13–25 MB/s; cookie không làm chậm.
`formats=dashy` + `concurrent_fragment_downloads=4` (`ytdlp_chung.tai_song_song`) cho ~78 MB/s; 8 kết nối không nhanh hơn
nên giữ 4 cho đỡ giống máy tự động. Áp cho `tai_video_goc.tai_nhieu` (tab tải video gốc, thumbnail, cả kênh, ghép); đồng bộ
kênh KHÔNG đổi. Dashy bỏ định dạng không báo dung lượng → «không có định dạng» thì thử lại một kết nối cùng client.
`thu_tung_client` nay GỘP `player_client` vào `extractor_args` thay vì ghi đè. Dừng giữa chừng: yt-dlp không đóng `.part`
Sửa 10/11 (audit): `formats=dashy,duplicate` + `dung_ban_khuc` — chọn định dạng trên bản THƯỜNG rồi đổi sang bản khúc
cùng URL; bỏ đường lui một kết nối (hết mất định dạng thiếu dung lượng, hết gọi YouTube gấp đôi khi lỗi).
→ `gc.collect()` rồi xoá lại thư mục tạm.

## D-39 Ghép video gốc thành video dài có đáp án (người dùng, 2026-11-09)
Tab «🎞️ Ghép video gốc»: dán link theo thứ tự (lặp = video lặp), tải H.264 ≤ 1080p + AAC trong MP4 (người dùng chọn
định dạng chung thay vì 4K, vì tool chỉ so tiếng) rồi nối `ffmpeg -f concat -c copy` — không nén lại. Video khác thông số
(độ phân giải, số hình/giây, mã hoá, tiếng) → DỪNG, báo video nào lệch, giữ file đã tải; không tự nén lại. Kèm `<tên>.moc.csv`
(bắt đầu/kết thúc từng video gốc) + mốc chương trong video — đáp án để đo độ chính xác quét. Ghép xong, độ dài khớp
tổng (≤ 1 s) thì xoá file lẻ (người dùng chọn). Mã: `TimClipPro/ghep_video_goc.py`.

## D-38 Tab «📝 Tiêu đề kênh» (người dùng, 2026-11-09)
Lấy tiêu đề + link + thời lượng mọi video ở tab Videos của kênh (không Shorts/Live) bằng MỘT lượt liệt kê nhanh
(`ChannelSync.list_channel`, không ngày đăng/lượt xem — những thứ đó cần một request mỗi video). Hiện bảng, tải CSV (UTF-8
BOM cho Excel, ô `= + - @` được chặn công thức) và TXT (mỗi dòng một tiêu đề). Không chạy khi đang quét/tải/đồng bộ.
Mã: `TimClipPro/tai_video_goc.py` (`tieu_de_kenh`, `csv_tieu_de`, `txt_tieu_de`, `ten_file_kenh`).

## D-37 Tải video gốc theo link (người dùng, 2026-11-08)
Tab «⬇️ Tải video gốc»: nhiều link (mỗi dòng một), ô thư mục + nút «Chọn…» (hộp thoại Windows qua tkinter ở tiến trình con),
tải hình + tiếng chất lượng cao nhất (`bv*+ba/b`, ghép bằng FFmpeg vào MP4 nếu hợp mã hoá, không thì MKV — không chuyển mã).
Không nén, không vào kho vân tay. Link kênh/playlist YouTube bị từ chối. Chạy ở làn chính (`chay_nen`): không cùng lúc với quét,
dựng kho hay đồng bộ kênh. Mã: `TimClipPro/tai_video_goc.py`.
Bổ sung 08/11 (người dùng chọn): ô «Chất lượng tối đa» (Cao nhất, 4K, 1440p, 1080p, 720p, 480p, Chỉ tiếng — lọc
`height<=`); tab «🖼️ Tải thumbnail» (ảnh lớn nhất, đổi sang JPG, không tải video); tab «📺 Tải cả kênh» (tab Videos, ô số
video mới nhất, 0 = cả kênh; video đã có file «[mã].đuôi» trong thư mục thì bỏ qua, ảnh không tính). Ba tab chung một thư mục.

## D-36 Dùng Codex làm người review độc lập, không cho chạm máy (người dùng, 2026-11-07)
Codex CLI đăng nhập gói ChatGPT của người dùng, dùng để review mã. Rào chắn của Claude không áp cho Codex: thử bằng file giả, `-s read-only`
chặn ghi và mạng nhưng VẪN đọc được file ngoài thư mục làm việc trên C: và D:. Nên chỉ chạy kiểu chỉ-nhận-văn-bản: tự gói mã công khai vào lời nhắc,
chạy ở thư mục rỗng với `--ignore-user-config --ignore-rules --ephemeral --disable shell_tool --disable unified_exec --disable apps --disable plugins
--disable hooks --disable multi_agent --disable browser_use --disable computer_use --disable image_generation -c web_search="disabled"`. Thử lại file giả
trước khi đổi cách chạy. Kết quả của Codex là lời khai: phải tái hiện bằng test đỏ mới sửa. Codex không commit, không chạm dữ liệu thật.
Bằng chứng: `C:\Dev\codex_ketqua` (ngoài Git); 6 lượt, 12 phát hiện: 10 đã sửa, 1 để lại (file ngắn hợp lệ gặp mất điện đúng lúc thì tải lại), 1 bị bác (dọn job cần đồng hồ nhảy 8 ngày).

## D-35 Đồng bộ kênh nén song song với tải video kế tiếp (người dùng, 2026-11-07)
Quyết định: video tải xong thì video kế tiếp bắt đầu tải ngay, video trước nén cùng lúc. Vì sao: mỗi video dài mất ~2 phút, gồm ~1 phút tải và
~50 giây nén; CPU chỉ 8% nên nén không cần chờ tải. Không tăng số luồng tải: tải nhiều luồng cùng cookie dễ bị YouTube chặn, nên vẫn một luồng,
kể cả lần tải lại ở bước nén (`_khoa_luong_tai`); bỏ giãn nhịp cũng không làm. Tối đa hai video trong đường ống, một nén một tải, để đĩa tạm có
trần. Cổng nén giữ tới khi vòng chính ghi xong metadata + sổ đã tải, nên số đo vừa kiểm chỉ thuộc một video và thứ tự ghi không đổi.
Tốc độ lượt trước 65 video/giờ trên video ngắn không bị chặn; bản này dự kiến ~60 video/giờ với video dài (chưa đo).
Sổ tiến độ có thêm làn nén; tốc độ video/giờ không cộng đôi phần chồng thời gian. Bằng chứng: `tests/test_nen_song_song.py`.

## D-34 Kho video dài theo từng thư mục (người dùng, 2026-11-07) — nới D-31 cho thư mục được đánh dấu
Bổ sung sau review: sức chứa tính theo MÃ clip đã cấp, không theo số file. `merge` cấp mã nối tiếp và không dùng lại ô đã gỡ, nên bổ sung hay làm mới clip
đều tiêu mã; hết mã thì phải «Tạo lại từ đầu». Bit mốc đọc từ chính file kho, sổ `khos.json` chỉ là phương án lùi.
Quyết định: kênh Joe Bart VODs có gần 900 video, phần lớn dài hơn 2 giờ, người dùng cần đồng bộ cả các video đó. Ô «Kho video dài» ở tab
Đồng bộ ghi file dấu `.kho_video_dai` vào THƯ MỤC kho (đồng bộ chỉ biết thư mục, có thể chạy trước khi kho được đăng ký). Thư mục có dấu:
đồng bộ và tạo vân tay nhận video tới 13 giờ; «Tạo lại từ đầu» dùng `--maxtimebits 21` (mốc đúng tới 13,5 giờ, tối đa 2.047 clip), ghi
`maxtimebits` vào sổ kho; báo cáo lấy `start_s` = vùng khớp thật ở `_gan_chi_so`, không sửa `_merge`. Thư mục không dấu giữ D-31 và 16 bit.
Vì sao: chỉ nới 2 giờ thì đo video 6 giờ tìm đúng 8/8 nhưng đúng vị trí 1/8; 20 bit đúng 8/8, RAM như cũ, tốc độ so khớp trên bảng cỡ thật
không đổi (20 bit 29–31 giây, 21 bit 29–30 giây, 16 bit 28–30 giây). `_merge` tính mốc ĐẦU CLIP nên đoạn giữa video gốc dài bị báo từ 00:00:00. Chia khúc 25 phút cũng đúng
nhưng phải thêm ánh xạ khúc → video và vẫn vỡ đoạn dài. Chốt: «Bổ sung» vào kho 16 bit bị chặn (mốc lưu cố định lúc tạo); vượt sức chứa
clip bị chặn (mã clip tràn sang phần mốc trong ô 32 bit, không có lỗi nào). Video trên 13 giờ vẫn bỏ qua có báo: RAM ~1,5 GB/giờ, 13 giờ ~20 GB.
Bảng 104,8 triệu ô, ~185.000 hash/giờ âm thanh: kênh lớn dựng theo đợt (`Chỉ lấy N video mới nhất`), không dồn hết vào một kho.
Chưa làm: chọn lọc Top-N trong kho video dài vẫn theo `ty_le` (phần trăm clip), clip càng dài tỉ lệ càng nhỏ. Bằng chứng: `tests/test_kho_video_dai.py`,
`C:\Dev\pc2_test_runs\2026-11-07_clip_dai\ket_qua.json`.

## D-33 Dựng kho nhường ổ cứng cho việc khác (người dùng, 2026-11-06) — thêm vào D-31
Quyết định: runner dựng kho đặt `IOPRIO_LOW` cùng Below Normal, worker và FFmpeg thừa hưởng; lượt quét không đổi. Hai chốt thời
gian đổi theo: FFmpeg im 300 giây mới là treo (`CHO_FFMPEG_S`, thư viện 10 giây, không sửa vendored), `CHO_WORKER_S` hết hạn mà CPU/I-O
của worker và FFmpeg vẫn tăng thì gia hạn. Vì sao: Below Normal không hạ ưu tiên ổ cứng; đo trên HDD thật, 8 luồng đọc lung tung
làm việc khác tụt từ 252 xuống 166 lần đọc/giây khi dựng kho, ưu tiên thấp giữ 249/giây. Đổi lại, HDD bận liên tục thì giải mã chỉ
còn ~0,9 lần tốc độ phát, FFmpeg im tới 15 giây: giữ chốt cũ thì clip hỏng oan, clip 1 giờ làm hỏng cả lượt.
Máy rảnh gần như không đổi. Bằng chứng: `tools/do_tai/do_uu_tien_o_cung.py`, `tests/test_dung_kho_theo_ram.py`,
runner thật 24 clip (đọc dồn 180 giây): 24/24, không thử lại, hash trùng lượt không tải. Chưa làm: tạm dừng và lưu giữa chừng.

## D-32 «Quét toàn bộ video» quét hết thật (người dùng duyệt audit 06/11, 2026-11-06)
Lô ghim «Quét toàn bộ video» (`Engine._quet_tron_theo_lo`) tải trọn ngay, không chia đoạn tăng dần, không đi đường Top-1 nhanh:
đây là lựa chọn chủ động, có ô xác nhận. Trước đây phần đầu đủ Top-N thì vẫn dừng ở 3 giờ. Watch, CLI và lô không ghim giữ nguyên
(3 giờ đầu rồi tải nốt khi chưa đủ, đếm số ĐOẠN; golden `yt_top5_nam_doan_ba_clip_trong_phan_tai_dau` khoá hành vi đó).

## D-31 Dựng kho theo RAM; bỏ clip dài hơn 2 giờ (người dùng, 2026-11-06) — thay cách chia cứng `filelists[ix % ncores]`
Quyết định (phân tích: `docs/PHAN_TICH_TAI_DUNG_KHO_2026-11.md`, người dùng chọn đề xuất 1, 2, 4, 6 và ngưỡng 2 giờ):
- Tiến trình cha phát TỪNG clip (`audfprint_progress_runner.LichTheoRam`, thuần logic): clip chỉ được phát khi RAM trống đủ
  cho nó cộng phần các clip đang chạy còn sẽ chiếm, sau khi chừa `max(2 GB, 10% RAM)`; chạy một mình chỉ giữ nửa mức đó (máy
  ít RAM thì chậm, không bỏ cả kho). Ước lượng 1,5 GB/giờ âm thanh (đo 06/11). Clip vừa phần RAM một worker giữ nguyên thứ tự,
  clip lớn hơn xếp cuối, nhỏ trước lớn; worker rảnh nghỉ sớm để nhả RAM. Nhánh một nhân đi qua cùng đường.
- Clip không vừa RAM khi không còn clip nào chạy: clip dài chờ 60 giây, clip ngắn chờ tới 30 phút, rồi bỏ qua có báo rõ
  (`thieu_ram`). Clip lỗi đọc/`MemoryError` thử lại một mình cuối lượt; KHÔNG ghi vào bảng của worker (bản ghi trùng, audit C-3).
  Một clip lỗi không còn giết cả lượt. Lý do thật lấy trước khi `wavfile2peaks` nuốt lỗi.
- Runner chạy Below Normal, worker và FFmpeg thừa hưởng.
- `channel.GIAY_CLIP_TOI_DA` = 2 giờ: video dài hơn không tải khi đồng bộ, clip dài hơn không tạo vân tay (so sau khi làm tròn
  giây, như thời lượng YouTube, nên file đúng 2 giờ qua được cả hai bước). Không phải lỗi: không
  đổi trạng thái lượt, không vào sổ đã tải, file trên đĩa giữ nguyên. Clip ĐÃ có vân tay vẫn ở lại khi «Bổ sung», clip đang
  được làm mới vẫn xử lý; «Tạo lại từ đầu» thì bỏ chúng và cảnh báo. Danh sách kênh thiếu thời lượng thì vẫn tải, chặn ở
  bước tạo vân tay. Đổi ngưỡng: sửa một hằng số.
Chưa làm: lưu theo lô (Dừng giữa chừng vẫn mất phần đã tính), chia clip rất dài thành đoạn. Bằng chứng:
`tests/test_dung_kho_theo_ram.py`, `tests/test_bo_clip_dai.py`, `tools/do_tai/do_dung_kho_ram.py`, báo cáo ở tài liệu phân tích.

## D-30 Ngày đăng trong báo cáo dạng «October 31, 2026» (người dùng, 2026-11-02) — thay `DD/MM/YYYY`
Quyết định: mọi ngày đăng trong báo cáo (Google Sheets bảng Ngang 34 cột / Dọc 16 cột, CSV, hồ sơ, giao diện) hiển thị
`Month D, YYYY` tiếng Anh cố định (không theo locale máy). Một hàm duy nhất `publication_date.format_publication_date`;
báo cáo V2 (`NgayNguon.hien_thi`) gọi lại nó. Không đổi ngày lịch, nguồn ngày, chữ ký chính sách (Watch không quét lại),
cách gửi RAW. Dòng ĐÃ gửi lên Sheet không bị sửa (vẫn `31/10/2026`); dòng mới dạng mới. Apps Script File03 giữ nguyên
chữ khi không nhận ra ngày dạng số. Bằng chứng: `tests/test_ngay_dang_thang_chu.py`.

## D-29 Đồng bộ kênh chạy SONG SONG với quét trong giao diện (người dùng, 2026-10-27) — nới «một việc mỗi lúc» của TCP-13
Quyết định (người dùng chọn «hướng B» trong phiên 27/10): một tab đồng bộ kho mới, một tab quét theo kho đã đồng bộ —
không chờ đồng bộ xong. Đồng bộ kênh thành làn RIÊNG (`tac_vu_nen.LOAI_SONG_SONG`, `job_dong_bo`, cờ huỷ riêng của lượt,
khung tiến độ tự làm mới ở đầu trang); quét / dựng vân tay / lô «Một video gốc chung» / «Lấy lại tên» / «Vá metadata» giữ
luật cũ một việc mỗi lúc. Vẫn CẤM: hai lượt đồng bộ cùng lúc (cùng cookie YouTube → dễ bị chặn), đồng bộ cùng «Lấy lại
tên» / «Vá metadata» (chung sổ tác vụ nền, cùng ghi metadata kho), dựng vân tay trên thư mục đang đồng bộ và ngược lại
(nạp file đang tải dở). Đang đồng bộ vẫn đổi được «Kho đang dùng» — lượt đồng bộ đã ghim thư mục đích + cấu hình mạng lúc bấm.
Vì sao: đồng bộ chỉ TẢI file vào thư mục đích, quét đọc kho vân tay đã dựng — không chung dữ liệu; cái thật sự chung là
cờ huỷ `eng.cancel_event` (TCP-13), nay đồng bộ không dùng nó nữa. Đổi lại: quét link YouTube trong lúc đồng bộ dùng chung
cookie + mạng (cảnh báo trên khung đồng bộ). Bằng chứng: `tests/test_dong_bo_song_song_quet.py`.

## D-28 Đợt P3 audit 25/10: duyệt golden `file_tu_khop_chinh_no.json`, GIỮ chữ ký chính sách (người dùng, 2026-10-26)
Quyết định (người dùng chọn trong phiên 26/10): A-7 (tự khớp không còn làm dừng sớm / chặn bù tốc độ ở nhánh quét
thường) và A-16 (parser không còn bỏ dòng audfprint «to time -0.0 s») được giữ mà KHÔNG đổi chữ ký chính sách — Watch
không quét lại âm tính đã chốt. Golden `tests/golden/file_tu_khop_chinh_no.json` sinh lại ở commit A-7 được duyệt: kết quả
(0 vi phạm), đường đi và chẩn đoán cuối giữ nguyên; chỉ khác số khúc / dòng thô / dòng tiến độ vì lượt bù tốc độ nay chạy.
Vì sao: hai trường hợp hiếm (file đang quét nằm sẵn trong kho; mảnh khớp đúng mép cửa sổ với `to time` âm 0); đổi chữ ký
buộc Watch tải và quét lại TOÀN BỘ video đã chốt âm tính — chi phí lớn so với lợi ích. Fuzz `_merge` 10.000 tình huống
giống hệt `a11dac4` (0 dương tính mới, 0 dòng mất).
Ràng buộc: nếu sau này thấy video thật bị bỏ sót vì một trong hai lỗi, quét lại riêng video đó (`--quet-lai`), không đổi
chữ ký hàng loạt. Bằng chứng: `tests/test_tu_khop_dung_som.py`, `tests/test_parser_to_time_am.py`; handoff PC2 26/10.

## D-27 Sửa «bóng» của âm thanh lặp trong `_merge` (P0) — PC2 viết 10/10 (`fix/pc2/loop-alias-p0`), đưa lên `fe461bd` 25/10 (người dùng duyệt)
Quyết định (người dùng duyệt triển khai thử A + B + C' 10/10; duyệt đưa vào mã chạy 25/10 trong kế hoạch audit): mốc đầu clip
chỉ lấy từ căn chỉnh CHÍNH; mảnh «bóng» (căn chỉnh khác của cùng clip nằm trong phạm vi một vị trí đặt mạnh hơn) vẫn được gom
và tính hash như cũ; nhóm toàn bóng không thành ứng viên; nhóm cùng vị trí đặt (trôi < ngưỡng bù) gộp thành một lần dùng CHỈ
khi không đổi kết luận chấp nhận; `Match` có `moc_mo_ho`, `moc_thay_the`, `ty_so_doi_thu` (chỉ trong bộ nhớ), tách khỏi
`confidence` (độ chắc chắn nguồn). Hằng số ở `chong_bong_lap.py`, không vào `Config`/`TRUONG_CHINH_SACH`; chữ ký chính sách
GIỮ NGUYÊN. (Viết 10/10 với số D-21; số đó đã dùng cho «Stable phân phối bằng GitHub Release» nên đánh lại là D-27.)
Vì sao: bản «xoá bóng trước khi gộp» (đã mô phỏng khi điều tra) làm nhóm thật mất tới 1,1% hash — rớt ứng viên sát
ngưỡng; phân loại theo từng mảnh bỏ sót bóng nằm trong «lỗ» của căn chỉnh bị trôi. Bản sửa không sinh dương tính mới
(đo: 0 vi phạm trên 27 lượt quét tổng hợp) nên âm tính cũ vẫn đúng — không cần Watch quét lại.
Ràng buộc: hiển thị cờ mơ hồ là P-6; đổi/nới hằng số hoặc muốn cộng các phần dưới ngưỡng thành dương tính = đổi chính
sách nhận diện → quyết định mới kèm phương án chữ ký/Watch.
Bằng chứng: `TimClipPro/docs/BONG_AM_THANH_LAP.md`; `tests/test_bong_am_thanh_lap*.py`; handoff PC2 (10/10 và 25/10).

## D-26 PC2 DEV-ONLY: Development 8502 là ứng dụng làm việc chính, dữ liệu THẬT; Stable chỉ dự phòng (người dùng, 2026-10-15) — thay một phần D-19 (Development chỉ dữ liệu thử) và D-21/D-23 cho việc tự dùng trên PC2
Quyết định:
- Trên PC2, chủ dự án làm việc hằng ngày bằng Development 8502, KHÔNG qua phát hành / ký / cập nhật Stable.
- Stable 1.1.1 (`C:\TimClipPro*`, 8501) và dữ liệu của nó GIỮ NGUYÊN để dự phòng: không xoá, không cập nhật, không dùng hằng
  ngày. Claude vẫn KHÔNG đọc/ghi/chạy gì trong `C:\TimClipPro*`.
- Development vận hành (ngoài Git, riêng máy):
  - mã = worktree `C:\Dev\TimClipPro_VanHanh`, nhánh cục bộ `pc2-van-hanh`, CHỈ fast-forward tới `integration/current`, không
    sửa tay;
  - Python = venv riêng cài OFFLINE từ `release/locks/requirements-lock.txt` có băm (`py312-f955a32807a9`, gồm yt-dlp-ejs; Node ≥ 22
    trên máy);
  - dữ liệu THẬT bền vững `C:\Dev\TimClipPro_DevState\data`, output `…\output`, sao lưu `D:\TimClipPro_Dev_SaoLuu`;
  - launcher `TimClipPro_DEV.bat` (+ `_CLI`, `_SaoLuu`, `_CapNhat` dùng chung `_env`): `127.0.0.1:8502`,
    `--server.fileWatcherType=none` (không tự tải lại giữa lúc tải / tạo vân tay / quét).
- GUI, CLI, Watch dùng CÙNG thư mục dữ liệu. Không dùng chung SQLite / hàng đợi gửi với Stable, không chép State của Stable.
- Phát triển vẫn như cũ: worktree việc riêng, test CHỈ dữ liệu synthetic (CLAUDE.md bước 5), PR + review + fast-forward
  `integration/current`; rồi cập nhật worktree vận hành bằng Git (`GIT_WORKFLOW.md` «Development vận hành PC2»).
- Không dừng / khởi động lại 8502 khi đang có việc (tải, tạo vân tay, quét, gửi).
Vì sao: chủ dự án ưu tiên có công cụ làm việc ngay; vòng phát hành + ký + cập nhật Stable tốn thời gian và (15/10) bị lớp quyền
Claude Code chặn khi tự động hoá trên máy production.
Bằng chứng: handoff PC2 15/10 (tối) — venv offline 56 gói, quét file thật với kho SML 779 vân tay đúng mốc, CLI cùng dữ
liệu, sao lưu + cập nhật Git-only thử 3 ca.

## D-25 Hook `pre-push` dùng chung + ruleset GitHub đề xuất (2026-10-14) — thay hook «chỉ fix/pc2» của D-18
Quyết định: một hook cho CẢ HAI máy (`release/git-hooks/pre-push`): cho `feature|fix/pc1|pc2/*`; `integration/current`
CHỈ fast-forward tới ĐÚNG đầu một nhánh việc đã đẩy (đã có PR); chặn tag (tag `stable-*` chỉ do `gh release create` sinh
khi công bố), xoá, force-push, nhánh lạ, tạo mới integration. Máy chủ: ruleset chặn xoá + force-push `integration/current`
và tag `stable-*` bất biến — KHÔNG «require pull request» (chặn gộp fast-forward bằng push; nút Merge đổi SHA).
Vì sao: hai máy ngang quyền thì quy ước tên nhánh không đủ; hook chặn nhầm cục bộ, ruleset chặn ở máy chủ cho mọi khoá.
Bằng chứng: `tests/test_git_hook_pre_push.py` (repo tạm, 9 ca); ruleset chưa bật (P-5).

## D-24 Lock có băm + wheel docopt + khoá công khai vào repo (2026-10-14) — giải quyết P-3
Quyết định: `release/locks/requirements-lock.txt` (= lock trong gói 1.1.1 đã ký, sha `f955a328…`),
`release/locks/launcher-lock.txt` (= lock của bộ kit 1.0.0), `release/wheels/docopt-0.6.2-py2.py3-none-any.whl` (băm có
trong lock), `release/trusted_keys.json` (khoá công khai đang tin); `.gitattributes` giữ nguyên byte (`release/** -text`).
Vì sao: máy nào cũng phải build được bản Stable mà không cần thư mục phát hành của máy kia.
Bằng chứng: build lại 1.1.1 từ `dc29b33` CHỈ bằng repo → gói giống từng byte bản đã công bố (`510f39a6…`), 14/10 PC1.

## D-23 PC1 và PC2 NGANG QUYỀN phát hành; mỗi máy một khoá ký (2026-10-14) — thay D-13 (khoá chỉ ở PC1), D-10 (phát hành chỉ ở PC1)
Quyết định (người dùng): PC2 = máy phát triển + phát hành CHÍNH, PC1 = DỰ PHÒNG; cả hai được phát triển, review, tích
hợp, build, ký, phát hành. Khoá riêng không rời máy của nó; PC2 tạo khoá trên PC2. Trust store của cài đặt managed (đã
tin nhiều khoá) được THÊM khoá PC2 bằng uỷ quyền có chữ ký của khoá đang tin, ràng buộc khoá / cài đặt (băm định danh) /
trust store (băm byte) / hạn — `uy_quyen_khoa.py`, `release_tool.py ky-uy-quyen`. Không đổi launcher, không bootstrap
lại, không bản phát hành mới. Sau lần ký uỷ quyền đó PC1 KHÔNG còn bắt buộc cho việc phát hành.
Vì sao: một máy giữ khoá duy nhất = điểm hỏng đơn; launcher hiện có đã đủ khả năng tin nhiều khoá.
Bằng chứng: `TimClipPro/docs/UY_QUYEN_KHOA.md` §1 (Phase A), `tests/test_uy_quyen_khoa.py`, diễn tập sandbox 19/19 (khoá
THỬ đóng vai hai máy, launcher `e49340d`, bootstrap + `CapNhat.bat` thật), 14/10 PC1.

## D-22 Repo `TimClipPro-dev` PUBLIC (người dùng, 13/10/2026; xác nhận 14/10) — thay một phần D-16
Quyết định của người dùng, không phải sự cố. Hệ quả: mọi push/PR/release là công khai → quét bí mật trước MỖI lần đẩy;
asset GitHub Release tải được không cần đăng nhập. Tên remote `private` giữ nguyên.

## D-21 Stable phân phối bằng GitHub Release (2026-10-13) — thay D-14 (ZIP qua RustDesk)
Quyết định: asset `TimClipPro_Feed_stable-X.Y.Z.zip` (4 file đã ký, STORED, tất định) + `SHA256SUMS_X.Y.Z.txt` + khối
PowerShell trong ghi chú (kiểm băm → giải nén → «SAN SANG») → `CapNhat.bat`. Không USB/RustDesk.
Bằng chứng: Release `stable-1.1.0` (`b00c315f…`), `stable-1.1.1` (`2f813e87…`); diễn tập bằng đúng gói tải về 23/23.

## D-20 Stable 1.0.0 cài lên PC2 trước tái audit (người dùng, báo 09/10) — thay một phần D-13
Sự kiện/quyết định của người dùng: Stable 1.0.0 (từ e49340d) đã cài và chạy trên PC2, cổng 8501 — sớm hơn điều kiện
«GIỮ ở PC1 tới khi e49340d được tái audit độc lập» của D-13. Hệ quả: C7 chưa đóng về kiểm chứng (cần kết quả bộ cài +
health check do NGƯỜI DÙNG lấy — Claude không đụng `C:\TimClipPro*`); tái audit độc lập e49340d vẫn cần; bản Stable sau
vẫn theo quy trình ký trên PC1.
Bằng chứng: lời người dùng; handoff PC2 (09/10). PC1 chưa có log cài đặt.

## D-19 Preview an toàn: `.claude/launch.json` chỉ GẮN vào Development 8502 (2026-10-10) — thay cấu hình 20/08
Quyết định: bỏ cấu hình tự khởi động `streamlit … --server.port=8501` (có từ `b776082`, 20/08); thay bằng một cấu hình
chỉ có `url` `http://localhost:8502` + `port` 8502 + `autoPort: false`, và `autoVerify: false` (Claude không tự mở preview
sau khi sửa). Development chạy bằng launcher RIÊNG máy, ngoài Git — yêu cầu (PC2 tự kiểm, PC1 chưa xem launcher đó):
danh sách duy nhất ở `docs/ai/handoff/PC2.md` «Máy» (cổng 8502 ghi rõ, data/output thử, không cookie/khoá thật, không
`.bat` cũ trong clone). 8501 dành cho Stable (`launcher.py` `CONG_STREAMLIT`, `127.0.0.1`) và production legacy PC1
(`ChayTool.bat`).
Vì sao: cấu hình cũ trùng cổng Stable PC2/production PC1; tài liệu Claude Code ghi cấu hình chỉ `url` thì «gắn vào server
đang chạy thay vì khởi động»; `env` trong file sẽ commit chung nên đường dẫn riêng máy không đặt ở đó được.
Giới hạn: hành vi khi 8502 không có gì chạy chưa được ghi trong tài liệu; preview trên PC2 CHƯA nghiệm thu; production
PC1 (`Tool_Quet` @ `6dc3f9d`) và các worktree cũ VẪN mang bản cũ tự khởi động 8501 (không sửa production) — không mở
preview ở đó; Claude có thể tự tạo lại `.claude/launch.json` khi được nhờ xem trước → giữ quy tắc trong `CLAUDE.md`.
Bằng chứng: kiểm tĩnh K10 (không 8501, không lệnh khởi động, có `url`, `autoVerify` false) vòng 10/10 trên PC1;
https://code.claude.com/docs/en/desktop#configure-preview-servers.

## D-18 PC2 giai đoạn 2 và cách gộp PR (2026-10-09/10) — bổ sung D-17
Quyết định: người dùng bật quyền GHI cho Deploy Key của PC2 (09/10; quyền ở mức cả repo, tên khoá vẫn ghi «read-only»).
PC2 chỉ đẩy `fix/pc2/*` khi được duyệt; PC1 review rồi gộp FAST-FORWARD bằng `update-ref` có kiểm SHA đã review (giữ SHA,
GitHub tự đánh dấu merged); không bấm nút Merge nào trên web. Khuyến nghị hook `pre-push` cục bộ trên PC2 (chặn
`integration/current`, tag, xoá, force-push) vì quy ước tên nhánh không phải giới hạn kỹ thuật.
Vì sao: repo private gói miễn phí (gói tài khoản chưa kiểm) không có bảo vệ nhánh; giữ SHA để handoff/commit của PC2 trỏ
đúng.
Bằng chứng: PR #1 (`b627af0`) gộp 10/10 sau review PC1; hook trích từ `GIT_WORKFLOW.md` thử 11/11 tình huống trên repo giả
(kể cả 3 lệnh thử ghi cho PC2) — vòng 10/10 trên PC1.

## D-17 PC2 truy cập GitHub theo hai giai đoạn; tài liệu không ghi cứng HEAD (2026-10-09) — bổ sung D-16
Quyết định (người dùng): giai đoạn 1 — Deploy Key CHỈ ĐỌC cho `TimClipPro-dev` (KHÔNG «Allow write access»), clone tại
`C:\Dev\Tool_Quet`; giai đoạn 2 — quyền ghi `fix/pc2/*` + Pull Request, thiết lập riêng sau khi PC2 clone, kiểm shared
context và người dùng duyệt. Tài liệu không ghi HEAD «mới nhất»; mỗi phiên hỏi remote (`git fetch private`).
Vì sao: PC2 chạy dữ liệu thật — quyền tối thiểu cho tới khi quy trình PC2 được kiểm; SHA ghi trong tài liệu cũ đi ngay
sau lần đẩy kế tiếp.
Bằng chứng: `docs/ai/GIT_WORKFLOW.md` (mục «PC2 — giai đoạn 1/2»), `handoff/PC2.md`, `SESSION_START.md`.

## D-16 Remote PRIVATE cho PC1/PC2 (2026-10-09) — giải quyết P-1
Quyết định: repo MỚI `TuongChris/TimClipPro-dev` (private, không fork); chỉ đẩy `integration/current` (lần đầu
`9b763be`, 90 commit, giữ nguyên lịch sử để không cắt truy vết `e49340d` trong manifest Stable 1.0.0); không đẩy tag
hay nhánh cũ. PC1: remote `private`, `remote.pushDefault=private`, `push.default=upstream`; push vào `origin` (PUBLIC)
bị chặn bằng pushurl giả, fetch vẫn chạy. PC2: clone với `--origin private`, khoá deploy chỉ cho repo này.
Vì sao: hai máy chia sẻ mã, tài liệu, handoff qua Git mà không đụng repo public.
Bằng chứng: quét toàn bộ lịch sử sẽ đẩy (843 blob, 90 commit, đối chứng dương 39/39) → 0 phát hiện nhạy cảm mới, chỉ
còn các mục đã báo người dùng và đã public sẵn (chi tiết ngoài Git, bằng chứng vòng 09/10 trên PC1); GitHub báo
`private=true`, ref duy nhất `refs/heads/integration/current` = `9b763be`, 0 tag; thử push nhầm `origin` → bị chặn.

## D-15 Ngữ cảnh chung qua Git + sơ đồ nhánh (2026-10-09)
Quyết định: `CLAUDE.md` gốc ngắn + `docs/ai/` + `.claude/rules/` theo vùng; `TimClipPro/CLAUDE.md` rút từ 782 xuống
dưới 200 dòng, phần dài chuyển nguyên văn sang `docs/LOI_DA_GAP.md`, rules, chỉ mục và file này. Nhánh
`integration/current` (= e49340d), `feature/pc1/*`, `fix/pc2/*`. Ghi chú riêng máy ở `CLAUDE.local.md` (gitignore).
Vì sao: PC1/PC2 hiểu dự án mà không đọc lại toàn bộ mã mỗi phiên; Claude Code khuyên CLAUDE.md < 200 dòng.
Bằng chứng: nhánh `feature/pc1/ai-shared-context`; inventory + kiểm chứng trong bằng chứng vòng 09/10 trên PC1.

## D-14 Bộ cài one-click cho PC2 (2026-10-09)
Quyết định: một ZIP chuyển qua RustDesk; `.bat` kiểm checksum, chữ ký, khoá công khai, lock TRƯỚC khi cài; cài offline
từ wheelhouse; dừng nếu thư mục đích đã có; hỏi trước khi tạo lối tắt. Mặc định `C:\TimClipPro`, `C:\TimClipPro_State`.
Bằng chứng: ZIP `b0847ea7…caa8`, thử 13/13 (thư mục sạch; máy không có Windows Sandbox).

## D-13 Stable 1.0.0 thật từ e49340d, chưa giao (2026-10-08)
Quyết định: khoá Ed25519 thật chỉ ở PC1 (ngoài repo/OneDrive), mã hoá bằng mật khẩu người dùng gõ; bản đã ký GIỮ ở PC1
tới khi e49340d được tái audit độc lập; PC2 tự xây dữ liệu, KHÔNG chép từ PC1. `KEY_BACKUP = DEFERRED_BY_USER`.
Rủi ro đã chấp nhận: mất khoá = bootstrap lại PC2 bằng khoá mới (launcher chưa có đường xoay khoá).
Bằng chứng: key_id `8aa5baa6c8f225f9`; manifest `e19a943b…`; cài mới thử 29/29.

## D-12 Sửa theo tái audit 78ba20c (2026-10-08)
Quyết định: outbox đọc/ghi tab theo MÃ `sheetId`, không theo tên A1 (MR-R2-P1-01); lưu mã tab của TỪNG lần phát cùng
giao dịch SENDING, lược đồ v4; việc cũ phát theo tên không bao giờ gửi lại (MR-R2-P2-01).
Bằng chứng: `8e7dc24`, `c981450`, `6461327`, `e49340d`; `docs/MANAGED_RUNTIME_DESIGN.md` §5; đột biến 123/123.

## D-11 Sửa theo audit độc lập f4d3cb7 (2026-10-08)
Quyết định: thư mục cài đặt và state root tách biệt, chốt bố cục trước mọi lần updater xoá (MR-P1-01); chốt mã tab
trong cùng giao dịch SENDING, trước request ghi đầu tiên (MR-P1-02).
Bằng chứng: `022349f`, `7d69380`, `78ba20c`; `docs/MANAGED_UPDATE.md`.

## D-10 Managed Runtime cho PC2 (2026-10-07…08)
Quyết định: state root tách khỏi cài đặt; outbox Sheets lưu bền trong `lichsu.db` (một người gửi, đích ghim theo
lượt); cổng bảo trì; Stable có chữ ký Ed25519 + health check + quay lại; launcher nằm ngoài release; phát hành chỉ
ở PC1 bằng `release_tool.py`. Nguồn bản mới đã thử: feed thư mục (`NguonThuMuc`); `NguonGitHub` có trong mã, chưa dùng.
Bằng chứng: `e341a1c` (M1) … `f4d3cb7` (M5); `docs/MANAGED_RUNTIME_DESIGN.md`, `docs/MANAGED_UPDATE.md`.

## D-9 Báo cáo V2 (2026-10-04…05) — PC1 production chạy bản này
Quyết định: chính sách báo cáo ghim ở ranh giới job; ảnh chụp lỗi chặn xuất, không lùi về luật cũ; gửi Sheets nghiêm
ngặt. Tái audit độc lập 05/10 (hồ sơ ngoài repo): PASS FOR CONTROLLED ROLLOUT PREPARATION, còn 2 mục P3.
Người dùng duyệt chuyển PC1 production sang `6dc3f9d` ngày 05/10 (có sao lưu trước).
Bằng chứng: `35c7fc1` … `6dc3f9d`; `docs/REPORT_POLICY_V2.md`, `docs/REPORT_POLICY_V2_VALIDATION.md`.

## D-8 Bỏ link Google Sheet ghi cứng khỏi `GiamSat.bat` (2026-10-04)
Quyết định: đọc `SHEET_LINK` hoặc `data\giam_sat_sheet.txt` (ngoài Git). Bằng chứng: `86e6bff`.

## D-7 Không nâng trần `max_matches` khi chưa có ca dương thật (2026-10-04)
Vì sao: đo trên lô thật, trần 200 chỉ cắt dòng nhạc hiệu; nâng trần không lộ ứng viên đạt chuẩn nào.
Bằng chứng: `7ee527a`; `docs/COMMON_ORIGINAL_SATURATION_ANALYSIS.md`.

## D-6 Truy cập YouTube có kiểm soát (2026-10-03)
Quyết định: một `PhienYouTube` mỗi lượt, phân loại lỗi tập trung, thử lại hữu hạn, cầu dao; lỗi truy cập không bao giờ
là âm tính. Bằng chứng: `f95345c` … `fe07985`; `docs/YOUTUBE_ACCESS_RELIABILITY.md`.

## D-5 Chế độ «Một video gốc chung cho cả lô» V1 (2026-10-03)
Quyết định: ứng viên lấy trước Top-N (`ung_vien_dat`); mục tiêu quét truyền tường minh; định danh (kho, basename);
V1 không ghi `lichsu.db`, không đẩy Sheets. Bằng chứng: `3218aff`, `d67ce31`; `docs/COMMON_ORIGINAL_DESIGN.md`.

## D-4 Hardening sau audit kiến trúc 4b7e5bd (2026-10-02)
Bằng chứng: `8f0558f` (16 phát hiện TCP-01…TCP-16), `f87cc85`; `docs/HARDENING_FIX_MATRIX.md`.

## D-3 Quy trình làm việc với AI
Hiện hành: người dùng dán brief (thường do GPT soạn) → Claude lập kế hoạch, làm TDD, kiểm chứng, báo cáo tiếng Việt kèm
bằng chứng; commit/push chỉ khi brief/người dùng cho phép. Quy trình CŨ «Claude lập kế hoạch → Codex viết code» vẫn
giữ nguyên văn cuối `TimClipPro/CLAUDE.md`, chỉ dùng khi được yêu cầu rõ.

## D-2 Mọi tuỳ chọn yt-dlp đi qua `ytdlp_chung` (2026-08-18)
Vì sao: ba lần trong một ngày cùng một lỗi chỉ được vá ở một đường tải. Bằng chứng: `docs/LOI_DA_GAP.md` mục 6, 6b, 6c, 9.

## D-1 Hướng phát triển và PyInstaller — chuyển nguyên văn từ `TimClipPro/CLAUDE.md` (e49340d)

## Hướng phát triển đang cân nhắc

1. Tự động quét định kỳ (Task Scheduler) → đẩy Sheets → gửi email cảnh báo.
2. Sinh sẵn hồ sơ khiếu nại bản quyền (điền form YouTube) từ dòng kết quả.
3. Nhánh so khớp hình ảnh cho trường hợp video bị thay tiếng.
4. ~~Đóng gói `.exe` bằng PyInstaller~~ — **đã khảo sát 18/08/2026 và BÁC BỎ.**
   Ba lý do cứng: (a) Streamlit bắt buộc đọc `app.py` dưới dạng văn bản rồi mới
   compile (`runtime/scriptrunner/script_cache.py`), nên bản .exe vẫn phải kèm .py;
   (b) `engine.py:1589` và `:1601` chạy `sys.executable` lên file .py — đóng băng là
   hỏng toàn bộ tạo vân tay và khớp; (c) mục tiêu thật là TỰ CẬP NHẬT, mà .exe làm
   việc đó tệ hơn hẳn: mỗi lần cập nhật phải chuyển ~700 MB thay vì vài KB, và
   Windows khoá file .exe đang chạy nên không tự ghi đè được.
   Đã thay bằng `cap_nhat.py` — cập nhật theo tag git. Xem `docs/TU_CAP_NHAT.md`.
