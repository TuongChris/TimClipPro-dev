# Phân tích tải khi đồng bộ / dựng kho vân tay (06/11/2026, PC2)

Chủ dự án báo: đồng bộ kho video gốc thì Tool chạy 100%, HDD (D:/E:) bận 100%, có lúc gần 30 yêu cầu đang chờ. Máy: i5-14400F
(16 luồng), RAM 32 GB, HDD WD40EZAX 4 TB chứa cả D: lẫn E:, SSD chứa C: và pagefile (44 GB, chỉ trên C:). Số đo dưới đây lấy
trên mã `5ce1e4d`, audio thật chỉ đọc, dữ liệu ghi thử nằm ở thư mục tạm rồi xoá. Công cụ đo: `tools/do_tai/`.

## Kết luận
1. **Việc làm quá tải là DỰNG VÂN TAY, không phải tải kênh.** Sáng 06/11 ba lượt dựng Kho_Joe_Games (761 clip, ~815 giờ âm
   thanh) đều không về đích; người dùng báo lỗi ngay sau khi Dừng lượt cuối (09:56).
2. **Nguyên nhân chính: RAM.** audfprint nạp TRỌN clip vào RAM rồi tính phổ 4 lần (`--shifts 4`). RAM tăng tuyến tính ~1,5 GB/giờ
   âm thanh mỗi worker. Clip #291 dài 18,2 giờ (ngoại suy ~27 GB RSS, ~30 GB commit) cộng 7 worker khác vượt 32 GB RAM.
3. **CPU 100%** là 8 worker + 8 ffmpeg trên 16 luồng (đo 78–100%).
4. **Không có điểm lưu giữa chừng:** Dừng hoặc lỗi là mất hết; lượt 09:18 đã xong 353/761 clip vẫn mất.
5. **Chưa tái hiện được «HDD 100% + hàng đợi ~30».** Hàng đợi HDD lớn nhất đo được là 8; hàng đợi 89 và bận 100% xuất hiện ở SSD
   C: (pagefile). Cần ghi hình lúc xảy ra thật để biết tiến trình nào gây ra.

## Bằng chứng từ nhật ký sáng 06/11 (`fingerprint.log`)
| Lượt | Diễn biến |
|---|---|
| 08:19 | ~90 clip/5 phút suốt 15 phút, 1,15 s/MB; từ 08:35 tụt còn 44 → 12 → 3 clip/5 phút, 3,6–4,9 s/MB; nhật ký dừng 08:49:49 không có dòng kết thúc |
| 09:18 | Như trên; clip #291 bắt đầu 09:37:11, từ đó clip 1 giờ mất 117–221 s (bình thường ~25 s), clip 2,8 giờ mất 486 s; clip #291 chưa xong sau 19 phút, người dùng Dừng 09:56:20 |
| 08:07 | Giải mã chậm ~10 lần so với hai lượt sau trên CÙNG clip (1,68 so với 0,16 s/MB), 3 clip «Error reading» cách nhau 3 giây, tiến trình thoát mã 1073807364 (0x40010004) lúc 08:10:57. CHƯA rõ nguyên nhân |

5 clip lỗi `wavfile2peaks: Error reading` trong 3 lượt đều là file bình thường. Hai khả năng, nhật ký không phân biệt được vì
`except Exception` trong code vendored nuốt mất lý do: `MemoryError`, hoặc ffmpeg im quá 10 giây (`FFmpegAudioFile.read_data`).

## Số đo
| Bài | Tình huống | HDD bận | Hàng đợi HDD max | Ghi chú |
|---|---|---|---|---|
| A | giải mã song song 1 / 2 / 4 / 8 luồng | 5 / 10 / 19 / 33% | 1 / 1 / 1 / 2 | 1147× → 5252× thời gian thực; 8 luồng CPU 86% |
| I | 8 luồng khi RAM trống còn ~0,6–1 GB | 34–39% | 5 | RAM cạn không làm HDD quá tải |
| E | chạy lại đường đồng bộ ngoại tuyến, nhịp thật 15 s/video | 1,7% | 2 | không YouTube, file nguồn 8–14 MB |
| E | như trên, không nghỉ (4 s/video) | 4,7% | 0 | |
| G | ghi file lớn ở 40 MB/s | 11,6% | 1 | như tải livestream dài |
| G | ghi 4 GB hết tốc lực (~180 MB/s) | >90% trong 22 s | 1 | bận 100% kiểu này là bình thường |
| F | dựng thật 8 worker, clip #361 trở đi, 120 s | 7,4% | 8 | CPU 78%, RAM trống chạm 0, Tool 30,4 GB commit, 30 clip |
| J | dựng thật 8 worker, clip #285 trở đi, 156 s | 6,6% | 3 | commit 23,7 → 68,5/75,3 GB (chốt an toàn dừng), RAM 0, **SSD bận 100% 33 giây, hàng đợi 89**, 78.000 trang ghi/giây, 18 clip |

- RAM + CPU một worker (bài B, `--shifts 4`): clip 1 giờ 25,5 s, RSS 1,35 GB, commit 2,8 GB; clip 3 giờ 71,6 s, RSS 4,27 GB, commit 5,82 GB.
- Metadata (bài C, JSON 1,2 MB): mỗi video 230 ms trên HDD, 76 ms trên SSD; `fsync` 20 ms / 1,7 ms.
- Phân mảnh (bài D): Kho_Joe_Games trung vị 3 mảnh, p90 8; Kho_Cory, Kho_SML 1 mảnh.
- Loại ổ (bài H): ghi ngẫu nhiên 64 KB 470–550 IOPS, không có mức hàng nghìn IOPS đặc trưng của SMR; đa số nguồn ghi WD40EZAX là
  CMR. Chưa có datasheet chính hãng.
- Defender đọc 0 MB/s ở mọi bài; Windows Search không có quy tắc chỉ mục D:/E:.
- Lưu ý bài J: Riot Client khởi động 10:36 trên C: đúng lúc đo nên số SSD có lẫn tải của nó; không ảnh hưởng số HDD.

## Đã loại trừ
Giả thuyết bị số đo bác: 8 ffmpeg tranh đầu đọc HDD; «đọc trước tuần tự» giúp giảm tải (không tác dụng, bỏ); RAM cạn làm mất bộ
đệm đĩa gây bão HDD; ghi `clips_meta.json` + fsync; đường đồng bộ; Defender; phân mảnh. Vì vậy KHÔNG nên chuyển `_tam` sang SSD
hay gom ghi metadata: tốn công và mất an toàn dữ liệu mà không giải quyết gì.

## Đã làm (D-31, 06/11/2026)
Người dùng chọn đề xuất 1, 2, 4, 6 và thêm quy tắc: video dài hơn 2 giờ không tải, không tạo vân tay. Clip #291 đo bằng ffprobe
dài 18,15 giờ (số 18,8 ở bản đầu tài liệu suy từ dung lượng), ước lượng cần 27 GB RAM.

Lượt dựng thật Kho_Joe_Games bằng lịch RAM, 8 worker, trước khi có quy tắc 2 giờ (dừng chủ động ở 744/761 clip vì người dùng
không cần 17 clip dài nhất; trong lúc đó máy còn chạy test và có League Client):
| Chỉ số | Sáng 06/11 | Lịch RAM |
|---|---|---|
| Kết quả | 3 lượt không về đích, xa nhất 353/761 | 744/744 clip thành công, 0 lỗi, 0 lượt thử lại, 78 phút |
| RAM trống thấp nhất | 0 | 6,68 GB |
| Commit đỉnh | 68,5/75 GB (chốt an toàn dừng) | 44,5/75 GB |
| SSD | bận 100% 33 giây liền, hàng đợi 89, 78.000 trang ghi/giây | trung bình 2,7%, 12 giây trên 90%, hàng đợi 55, 8.531 trang/giây |
| HDD | 6,6%, hàng đợi 3 | trung bình 3,5%, 8 giây trên 90%, hàng đợi 7 |
| CPU | 78–100% | trung bình 63%, tiến trình chạy Below Normal |

So vân tay: cùng 32 clip, mã cũ và mã mới ra số hash giống hệt từng clip (0 clip lệch, 4,39 triệu hash). Thời gian 169 và 221 giây
không phải phép so tốc độ sạch: lượt mã mới chạy cùng lúc với test của phiên làm việc, ở ưu tiên thấp và có giới hạn RAM.
«HDD 100% + hàng đợi ~30» vẫn CHƯA tái hiện được.

Nghiệm thu mã cuối qua `Engine` thật (`do_dung_kho_ram.py d`, bản sao 36 clip trên SSD, kể cả clip 18,15 giờ và 5,99 giờ): 34/34
clip thành công, 200 giây, 0 lỗi; đúng 2 clip dài hơn 2 giờ bị bỏ có cảnh báo, 4 clip 1,79–1,92 giờ vẫn vào kho; RAM trống thấp
nhất 9,56 GB; cắt 60 giây từ 4 clip rồi tìm lại trong kho vừa gộp: 4/4 đúng clip (hạng 0). Mọi FFmpeg và tiến trình Python làm
việc đều Below Normal. Một `python.exe` ở ưu tiên thường là file khởi chạy 274 KB của venv, chỉ đứng chờ tiến trình con.

## Đề xuất (đã làm 1, 2, 4, 6; còn lại chưa làm)
| # | Việc | Tác dụng | Công |
|---|---|---|---|
| 1 | Lập lịch theo RAM: ước lượng 1,5 GB/giờ từ dung lượng file; clip dài chạy riêng sau cùng | Hết sụp tại clip dài | Vừa, trong `audfprint_progress_runner.py` |
| 2 | Clip quá dài so với RAM trống: bỏ qua và báo rõ, không làm sập cả lượt | Không mất lượt | Nhỏ, đi cùng #1 |
| 3 | Lưu giữa chừng theo lô (ví dụ 100 clip), Dừng/lỗi giữ phần đã xong | Không làm lại từ đầu | Vừa, trong `engine.py` |
| 4 | Tiến trình dựng kho chạy ưu tiên thấp (Below Normal) | Máy vẫn dùng được khi CPU 100% | Rất nhỏ |
| 5 | Mặc định số worker theo RAM thay vì luôn 8 | Giảm rủi ro | Rất nhỏ |
| 6 | Thử lại clip «Error reading» cuối lượt + ghi rõ lý do | Không sót clip vì quá tải | Nhỏ |
| 7 | Chia clip rất dài thành đoạn khi tính vân tay | RAM cố định, dựng được clip 18,2 giờ | Lớn, đổi vân tay clip dài, cần test khớp |
