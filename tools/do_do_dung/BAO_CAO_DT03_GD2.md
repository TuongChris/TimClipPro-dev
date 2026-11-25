# DT-03 giai đoạn 2 — kết quả đo độ đúng

TimClipPro đã chạy 159/159 ca với kho 779 clip SML và cấu hình DEV. Bộ đo chèn clip thật vào tệp khoảng 20 phút ở mốc đã biết. TimClipPro dò bằng vân tay âm thanh, bật tinh chỉnh mốc và báo tối đa 3 dòng mỗi tệp, phân bổ theo vị trí.

## Tóm tắt

- **Đo được.** Bắt đủ 36/36 đoạn dài 300–900 giây qua cả bốn biến đổi.
- **Đo được.** Với đoạn dài, sai số mốc quét điển hình khoảng 32 giây ở mỗi mép. Sau tinh chỉnh, sai số trung vị ở cả hai mép là 0,0 giây theo độ làm tròn của bảng. Trong 147 ca đã tinh chỉnh, 0 ca tệ hơn lượt quét quá 0,5 giây.
- **Đo được.** Hai ca dài vẫn lệch nhiều sau tinh chỉnh. Một mốc đầu muộn 20,55 giây và một mốc cuối sớm 77,09 giây.
- **Đo được.** Trong 240 đoạn dài 30–60 giây, 114 đoạn được báo và 36 đoạn đạt ngưỡng nhưng bị giới hạn 3 dòng cắt. Còn 90 đoạn sót thật.
- **Đo được.** Đổi cao độ giữ nguyên tốc độ cho kết quả 0/12 ở hai mức ±1 bán cung và 0/6 ở mức +0,5 bán cung, kể cả với đoạn 300 giây. Tua 5% bắt được 5/6 đoạn.
- **Chưa biết.** 20 giờ đối chứng từ kênh khác sinh 0 ứng viên. Phép đo còn thiếu đối chứng cùng kênh SML để ước lượng báo nhầm khi nội dung giống nhau.
- **Suy luận.** Có thể bật tinh chỉnh mặc định và ghi rõ trạng thái mốc. Nên giữ sàn 1.000 hash trong lúc đo thêm và thử lượt bù cao độ theo yêu cầu hoặc khi lượt thường không có kết quả.

## Đo được

### Đoạn dài và độ đúng của mốc

Cả bốn biến đổi gồm bản gốc, nén 24k, nhạc đè và giọng đè đều đạt 3/3 ở mỗi độ dài 300, 600 và 900 giây. Có 30/36 đoạn dài được tinh chỉnh.

| Sai số tuyệt đối trung vị | Mốc đầu | Mốc cuối | Số đoạn |
|---|---:|---:|---:|
| Lượt quét | 32,8 giây | 32,1 giây | 36 |
| Sau tinh chỉnh | 0,0 giây | 0,0 giây | 30 |

Hai dòng trung vị dùng số đoạn khác nhau. Khi so từng ca có tinh chỉnh với chính lượt quét của nó, toàn bộ phép đo có **0/147 ca tệ hơn quá 0,5 giây**. Có 4/147 ca vẫn lệch quá 1 giây sau tinh chỉnh, gồm hai ca dài và hai ca ngắn.

| Ca dài | Lệch đầu / cuối khi quét | Lệch đầu / cuối sau tinh chỉnh |
|---|---:|---:|
| 600 giây, giọng đè (`dai_600_giong_de_2`) | +36,64 / −52,46 giây | +20,55 / −0,01 giây |
| 900 giây, bản gốc (`dai_900_goc_2`) | +38,20 / −175,70 giây | −0,01 / −77,09 giây |

Dấu `+` là muộn so với mốc thật. Dấu `−` là sớm.

### Vùng 30–60 giây

Mỗi ô theo độ dài có 12 đoạn và ghi **số bắt + số đạt ngưỡng nhưng bị cắt = tổng đạt ngưỡng**. Hai cột cuối đếm số sót thật trên cả năm độ dài.

| Biến đổi | 30 giây | 40 giây | 45 giây | 50 giây | 60 giây | Dưới ngưỡng | Không có ứng viên đúng |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bản gốc | 3 + 8 = 11 | 5 + 7 = 12 | 6 + 6 = 12 | 11 + 1 = 12 | 11 + 1 = 12 | 1 | 0 |
| Nén 24k | 0 + 0 = 0 | 5 + 4 = 9 | 8 + 3 = 11 | 10 + 1 = 11 | 12 + 0 = 12 | 17 | 0 |
| Nhạc đè | 1 + 0 = 1 | 1 + 0 = 1 | 3 + 0 = 3 | 4 + 0 = 4 | 3 + 0 = 3 | 44 | 4 |
| Giọng đè | 1 + 0 = 1 | 6 + 1 = 7 | 7 + 2 = 9 | 5 + 2 = 7 | 12 + 0 = 12 | 24 | 0 |
| **Tổng** | **5 + 8 = 13** | **17 + 12 = 29** | **24 + 11 = 35** | **30 + 4 = 34** | **38 + 1 = 39** | **86** | **4** |

Tổng cộng **150/240 đoạn đạt ngưỡng**, gồm 114 đoạn được báo và 36 đoạn bị cắt. Trong 90 đoạn sót thật, 86 có ứng viên đúng dưới ngưỡng và 4 thiếu ứng viên đúng. Cả 4 ca thiếu ứng viên đúng đều có nhạc đè.

### Hạ sàn hash và báo nhầm

Luật hiện tại nhận bậc A khi có ít nhất 1.000 hash và mật độ từ 3 hash/giây. Bậc B cần phủ ít nhất 60% vân tay clip, khớp ít nhất 20 giây và có mật độ từ 3 hash/giây.

Trên toàn bộ nhóm có chèn clip, bảng tự động ghi 145 đoạn sót. Cột «Bị sàn loại» của bảng đó gộp mọi đoạn sót có dòng đúng bị loại, kể cả do giới hạn 3 dòng. Bảng dưới chỉ xét số hash. Muốn biết số đoạn thực sự bắt thêm, cần chạy lại cả luật chấp nhận và giới hạn số dòng.

| Sàn hash | Đoạn sót có dòng đúng đạt mức hash | Dòng sai có thể lọt thêm khi chỉ xét hash |
|---:|---:|---:|
| 500 | 111 | 1 |
| 600 | Tối đa 101 | 1 |
| 700 | 92 | 1 |
| 800 | 75 | 1 |
| 900 | 58 | 1 |
| 1.000 | 37 | 0 |

Ở mức 600, dữ liệu cho tối đa 101 **dòng** đúng, nên 101 là mức trần cho số **đoạn**. Bản phân tích sàn quy 37 đoạn có từ 1.000 hash cho giới hạn số dòng, trong khi bảng chấm lại đếm 36 đoạn bị cắt. Chưa rõ nguyên nhân chênh 1 đoạn.

Dòng sai cao nhất có **954 hash**, khớp 57,2 giây trong `dai_600_giong_de_2`. Đây là dòng sai đủ hash ở cả năm mức sàn từ 500 đến 900. Trong 60 tệp đối chứng dài 20 phút từ 7 kênh khác, có **0 ứng viên và 0 báo nhầm trong 20 giờ**.

### Cao độ và thời gian quét

| Biến đổi | 120 giây | 300 giây | Tổng bắt |
|---|---:|---:|---:|
| Bản gốc | 3/3 | 3/3 | 6/6 |
| Tăng 0,5 bán cung | 0/3 | 0/3 | 0/6 |
| Tăng 1 bán cung | 0/3 | 0/3 | 0/6 |
| Hạ 1 bán cung | 0/3 | 0/3 | 0/6 |
| Tua 5% | 2/3 | 3/3 | 5/6 |

Kết quả **0/12** ứng với hai mức ±1 bán cung. Tính cả mức +0,5 bán cung, tổng là **0/18**. Bảng thiếu ca −0,5 bán cung.

Lượt quét thường mất khoảng 20 giây cho một tệp 20 phút. Các ca có lưới bù mất trung bình 71–80 giây, tùy biến đổi. Lưới `luoi_resample` thử 0,96, 0,98, 1,02 và 1,04, đổi cả tốc độ lẫn cao độ. Lưới giữ cao độ `luoi_tempo` đang trống. Cấu hình hiện tại có 0 lượt bù cao độ giữ nguyên tốc độ.

## Suy luận

- **Tinh chỉnh có thể sửa đúng cả khi phải dời mốc hàng chục giây.** Các ca dài có mốc chèn biết trước đã xác nhận điều này. Hai ca còn lệch lớn cho thấy bạn vẫn có thể cần kiểm lại mốc trước khi đưa vào hồ sơ. Với 1.103 dòng DEV từng dời mốc trung vị 36 giây ở đầu và 53 giây ở cuối, độ đúng vẫn chưa biết vì thiếu mốc thật.
- **Hạ sàn có thể đưa thêm ứng viên đúng lẫn sai qua điều kiện hash.** Dòng 954 hash có thể đến từ một đoạn xuất hiện trong nhiều clip SML. Giả thuyết này cần kiểm bằng cách nghe và đối chiếu hai clip.
- **Có thể thử bù cao độ trên bản âm thanh dùng để dò.** Tạo bốn bản dịch ở ±0,5 và ±1 bán cung, giữ nguyên tốc độ, bằng FFmpeg `rubberband` hoặc `asetrate` kết hợp `atempo`. Chỉ chạy khi lượt thường không có kết quả hoặc khi bạn bật tùy chọn. Nếu mỗi bản mất khoảng 20 giây để quét, thử đủ bốn bản sẽ cộng khoảng 80 giây cho tệp cần bù, chưa tính thời gian tạo bản âm thanh. Mốc 71–80 giây là số đo của lưới hiện tại. Thử thêm nhiều bản có thể làm tăng báo nhầm, nhất là với các clip có âm thanh giống nhau.

## Chưa biết và việc đo tiếp

- **Tỉ lệ bắt đoạn ngắn.** Giới hạn 3 dòng ảnh hưởng cả hai giai đoạn vì mỗi tệp thử có 5 đoạn. Giai đoạn 1 ghi 0/48 ở 8–15 giây, 9/24 ở 30 giây, 16/24 ở 60 giây và 21/24 ở 120 giây. Khi đo lại, dùng tối đa 3 đoạn mỗi tệp hoặc tăng giới hạn đủ để giữ mọi đoạn chèn. Ghi riêng số dòng người dùng sẽ thấy với cấu hình phát hành.
- **Báo nhầm trong nội dung giống kho.** Thêm đối chứng âm từ chính kênh SML, chọn clip ngoài kho và kiểm tra trước các đoạn dùng chung. Chạy lại các mức sàn và ghi số dòng sai thực sự được báo. Đối chiếu số đếm 37 và 36 theo từng đoạn trước khi dùng bảng sàn để quyết định.
- **Hiệu quả của lượt bù cao độ.** Chạy lại chính bộ «cao» với và không có lượt bù, bổ sung mức −0,5 bán cung. So số đoạn bắt đúng, sai số hai mốc, số báo nhầm và thời gian quét. Dùng cả ca gốc, ca tua 5% và đối chứng âm cùng kênh để kiểm tra tác động.

## Quyết định đề xuất cho bạn duyệt

| Mục | Đề xuất |
|---|---|
| **D-49 · Tinh chỉnh mốc** | Bật mặc định cho bản phát hành. |
| **P-6 · Nhãn mốc** | Thay «Rất chắc chắn» bằng «Mốc đã tinh chỉnh», «Mốc ước lượng» hoặc «Kiểm lại mốc — lý do». Nhãn đầu cho biết mốc đã qua tinh chỉnh. Nhãn cuối ghi lý do cụ thể khi có dấu hiệu cần kiểm. |
| **Sàn hash** | Giữ sàn bậc A ở 1.000 hash cho bản phát hành. Xem lại sau phép đo với đối chứng cùng kênh. |
| **Lượt bù cao độ** | Duyệt thử nghiệm trên bộ «cao». Quyết định bật mặc định sau khi có số đo về số đoạn bắt thêm, báo nhầm và thời gian. |
| **Giới hạn 3 dòng (`top_n`)** | Đây là thiết kế để chọn tối đa 3 dòng đưa vào hồ sơ khiếu nại. Video ghép nhiều clip ngắn có thể có thêm đoạn đạt ngưỡng. Bạn muốn tăng số dòng trong hồ sơ hay giữ 3 dòng và thêm danh sách «Các clip khác tìm thấy»? |