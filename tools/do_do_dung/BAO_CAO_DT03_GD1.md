# DT-03 giai đoạn 1 — kết quả đo độ đúng

Đo ngày 25/11/2026 trên máy thật, với kho 60 clip SML và cấu hình DEV đã bật tinh chỉnh mốc.

## Tóm tắt cho bạn

- Máy bắt được **46/120 đoạn chèn**. Đoạn 8–15 giây không bắt được ca nào. Từ 30 giây, kết quả thay đổi rõ theo cách xử lý âm thanh.
- Ở 120 giây, máy bắt được **21/24 đoạn**. Cả ba đoạn bị bỏ sót đều tăng cao độ một bán cung. Biến đổi này cho kết quả **0/15** trên mọi độ dài đã thử.
- Mốc quét thường cắt hụt khoảng **4 giây ở mỗi mép**. Trong 41 đoạn tinh chỉnh được, sai số lớn nhất là **0,1 giây** ở cả hai mép.
- Trong lịch sử DEV, tinh chỉnh dời mốc đầu và cuối trung vị **36,26 và 53,22 giây**. Chưa có mốc thật để chấm. Đề xuất giữ DEV đang bật và chờ đo đoạn dài trước khi bật mặc định cho bản phát hành.
- Bộ đo ghi nhận **0 dòng báo nhầm** trên 2,0 giờ đối chứng âm và 7,9 giờ ca có chèn. Cần đo lại trên đủ **779 clip SML** trước khi cân nhắc đổi sàn 1.000 hash.
- Nhãn **«Rất chắc chắn»** xuất hiện trên cả 46 kết quả đo và cả 1.103 dòng DEV. Có thể dùng ô nhãn hiện tại để báo tình trạng mốc và giữ đủ **34 cột Sheets**.

## 1. Khả năng bắt đoạn

**Đo được.** Một đoạn được tính là bắt được khi có dòng đúng clip, giao với đoạn chèn thật sau khi nới dung sai 3 giây. Mỗi ô dưới đây có 3 mẫu.

| Biến đổi | 8 giây | 15 giây | 30 giây | 60 giây | 120 giây |
|---|---:|---:|---:|---:|---:|
| Gốc, AAC 128k | 0/3 | 0/3 | 3/3 | 3/3 | 3/3 |
| Nén Opus 24k mono | 0/3 | 0/3 | 1/3 | 3/3 | 3/3 |
| Nhạc đè cùng mức RMS | 0/3 | 0/3 | 0/3 | 1/3 | 3/3 |
| Giọng đè −3 dB | 0/3 | 0/3 | 1/3 | 3/3 | 3/3 |
| Nhanh 3%, giữ cao độ | 0/3 | 0/3 | 2/3 | 3/3 | 3/3 |
| Nhanh 6%, giữ cao độ | 0/3 | 0/3 | 2/3 | 3/3 | 3/3 |
| Tăng một bán cung, giữ độ dài | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| Tua 5%, đổi cả tốc độ và cao độ | 0/3 | 0/3 | 0/3 | 0/3 | 3/3 |
| **Tổng** | **0/24** | **0/24** | **9/24** | **16/24** | **21/24** |

**Suy luận.** Vùng 30–60 giây đáng ưu tiên đo thêm. Trong vùng này, bản gốc đạt 6/6 còn nhạc đè đạt 1/6. Hai kiểu thay đổi cao độ cho kết quả khác nhau ở 120 giây, nên cần thử riêng từng kiểu.

**Chưa biết.** Độ dài tối thiểu có thể bắt ổn định trên video thật. Cũng chưa rõ `cao_do_1` mất dấu ở bước tạo vân tay, chọn ứng viên, bù cao độ hay lọc theo ngưỡng.

## 2. Độ đúng của mốc

**Đo được.** Trên 46 đoạn bắt được, mốc quét nằm trong đoạn thật. Đầu trễ trung vị 3,8 giây, có ca trễ 16,8 giây. Cuối sớm trung vị 4,2 giây, có ca sớm 21,0 giây. Trên 41 đoạn tinh chỉnh được, sai số trung vị ở cả hai mép là 0,0 giây theo độ làm tròn của bảng. Sai số lớn nhất là 0,1 giây ở mỗi mép.

**Đo được.** Có 5/46 đoạn chưa tinh chỉnh. Hai ca nhạc đè không đo được mép dù có 1.277 và 1.409 hash. Ba ca tua 5% khớp khoảng 100 giây mỗi ca, có 1.006–1.384 hash, và thuộc lượt bù cao độ chưa hỗ trợ tinh chỉnh. Cờ «mốc mơ hồ» bật ở 0/46 đoạn.

**Đo được.** Lịch sử DEV có 959 lượt quét và 1.103 dòng. Thời lượng khớp trung vị là 714,8 giây. Trong 156 dòng đã tinh chỉnh, độ dịch mốc đầu và cuối lần lượt có trung vị 36,26 và 53,22 giây, lớn nhất 106,43 và 175,95 giây. Trong 947 dòng chưa tinh chỉnh, có 6 dòng lệch hơn 5 giây so với bảng kết quả khớp, gồm 4 dòng lệch hơn 30 giây.

**Suy luận.** Tinh chỉnh cho mốc sát mép thật trên các đoạn ngắn đã xử lý thành công. Những lần dịch hàng chục giây trong DEV đáng được đối chiếu với mốc chèn thật ở giai đoạn 2.

**Chưa biết.** Mốc nào gần mép thật hơn trên các đoạn dài của DEV, và vì sao một số dòng chưa tinh chỉnh vẫn lệch so với bảng kết quả khớp. Ảnh chụp lịch sử chưa lưu cờ «mốc mơ hồ».

## 3. Báo nhầm và nhãn

**Đo được.** Với kho 60 clip, 4 tệp đối chứng âm cho 0 dòng trên 2,0 giờ. Các ca có chèn cho 0 dòng ngoài vùng chèn trên 7,9 giờ. Cả 1.103 dòng DEV mang nhãn «Rất chắc chắn». Số hash trung vị là 24.803, có 10 dòng dưới 2.000 và 33 dòng dưới 5.000. Chỉ 3 dòng có thời lượng khớp dưới 60 giây và không có dòng nào dưới 30 giây.

**Suy luận.** Một nhãn giống nhau trên mọi dòng không giúp bạn chọn dòng cần kiểm trước. Nhóm hash thấp trong DEV là một nhóm đáng lấy mẫu kiểm tay.

**Chưa biết.** Tỉ lệ báo nhầm khi dùng đủ 779 clip, độ đúng của các dòng DEV và số đoạn đúng bị sàn 1.000 hash loại.

## 4. Quyết định đề xuất

- **D-49.** Giữ tinh chỉnh bật trong DEV. Chưa bật mặc định cho bản phát hành. Chốt sau khi chấm cùng một tập đoạn 300–900 giây ở cả hai chế độ, so sai số đầu và cuối, rồi kiểm riêng các ca dời mốc trên 30 giây.
- **P-6.** Giữ mốc trong ô «Đoạn vi phạm» để bạn vẫn sao chép được. Dùng ô đang hiện nhãn tin cậy để ghi «Mốc đã tinh chỉnh», «Mốc ước lượng» hoặc «Kiểm lại mốc — tiếng đè / đổi cao độ / mép mơ hồ» theo lý do máy ghi nhận. Có thể đặt lý do dài trong ghi chú của chính ô đó. Bảng xuất vẫn có 34 cột.
- **Nhãn độ tin cậy.** Tạm thay «Rất chắc chắn» bằng các trạng thái mốc trên. Nếu cần nhãn cho độ chắc của kết quả khớp clip, hãy hiệu chuẩn bằng các dòng đã kiểm tay. Một dòng có thể đúng clip nhưng vẫn cần kiểm lại mép.
- **Sàn `min_hash_floor=1000`.** Giữ nguyên. Trên kho 779 clip, ghi ứng viên trước bước lọc và chấm cả đối chứng âm lẫn ca có chèn. So số dòng báo nhầm trên 100 giờ và số đoạn đúng bắt thêm hoặc mất đi khi áp lại các sàn lên cùng tập ứng viên.

## 5. Kế hoạch giai đoạn 2

1. **Dựng kho đủ 779 clip SML và đo thử tốc độ.** Kho 60 clip mất 100 giây để dựng. Nội suy theo số clip cho khoảng 22 phút, cần đo lại vì độ dài clip khác nhau. Quét thử 6 tệp khoảng 20 phút, gồm ca dễ và ca phải chạy lưới bù cao độ. Các ước tính dưới đây giả định kho lớn mất **1–4 phút máy mỗi lượt quét**. Cập nhật dự toán sau lượt thử.
2. **Đo báo nhầm trên 30 giờ đối chứng âm.** Dùng 90 tệp khoảng 20 phút, đa dạng kênh và thể loại đã loại trừ SML. Kiểm tay mọi dòng phát sinh. Báo số dòng nhầm, số tệp bị báo nhầm và số dòng nhầm trên 100 giờ. Lưu ứng viên trước lọc để đo tác động của sàn hash. Ước **1,5–6 giờ máy**, cộng lượt quét lại nếu dữ liệu đã lưu thiếu.
3. **Chấm mốc trên 36 đoạn dài.** Thử 300, 600 và 900 giây, mỗi độ dài có 3 clip nguồn cho mỗi kiểu âm thanh: gốc, nén thấp, nhạc đè và giọng đè. Chạy bật và tắt tinh chỉnh trên cùng tệp. Báo sai số trung vị, p90, lớn nhất và số ca sai lệch tăng sau tinh chỉnh. Ước **1,2–4,8 giờ máy** cho 72 lượt.
4. **Tăng mẫu ở vùng 30–60 giây.** Dùng các mốc 30, 40, 45, 50 và 60 giây, mỗi mốc 12 mẫu cho từng kiểu trong bốn kiểu trên. Ghép 5 đoạn vào mỗi tệp như giai đoạn 1, tổng cộng 48 tệp. Ước **48 phút–3,2 giờ máy**.
5. **Tách nguyên nhân `cao_do_1`.** Dùng cùng clip và nền để so bản gốc, bản tăng một bán cung, bản hạ lại một bán cung và bản tua 5%. Thử trên đoạn 60, 120 và 300 giây. Ghi số hash, thứ hạng ứng viên và bước loại. Ước **24–96 phút máy** cho 24 lượt, gồm hai clip nguồn cho mỗi tổ hợp.
6. **Thêm ô kiểm tay «Đúng/Sai/Chưa chắc» trên tab rà soát.** Ghi cạnh nhãn lý do chọn và mốc thật nếu xác định được. Kiểm mọi dòng đối chứng âm phát sinh, các ca tinh chỉnh dịch trên 30 giây và một mẫu DEV gồm dòng hash thấp lẫn cao. Thời gian kiểm tay tùy số dòng phát sinh.
7. **Giữ một bộ 8 tệp cố định để chạy sau mỗi thay đổi.** Gồm hai đối chứng âm, ba ca 30–60 giây, một ca đoạn dài, một ca tăng một bán cung và một ca tua 5%. So số bắt được, báo nhầm và sai số mốc với lần chạy trước. Ước **8–32 phút máy** mỗi lần trên kho lớn.

## 6. Giới hạn của phép đo

- Giai đoạn 1 dùng 60/779 clip SML, bốn nguồn nền và ba mẫu cho mỗi ô. Số 0 báo nhầm chỉ mô tả thời lượng và kho đã thử.
- Đoạn chèn được dựng có mốc thật, dài tối đa 120 giây, và mỗi biến đổi áp lên cả tệp. Video thật có thể đổi cách xử lý âm thanh giữa các đoạn.
- Sai số mốc chỉ được chấm trên đoạn đã bắt được. Kết quả tinh chỉnh chỉ tính 41 đoạn có mốc tinh chỉnh.
- Lịch sử DEV có độ dài khớp gần với thực tế sử dụng, nhưng thiếu mốc thật và nhãn kiểm tay. Các số dịch mốc trong lịch sử chỉ đo mức thay đổi giữa hai kết quả.