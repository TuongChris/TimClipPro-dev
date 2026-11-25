# DT-03 giai đoạn 1 — bộ đo độ đúng (audio kho thật, engine thật)

Kho đo: 60 clip SML thật (chép, chỉ đọc E:). Mỗi ca: nền 1200 s ghép từ kênh khác (Ms Rachel, Mr Ballen, Cory, MSA) + 5 đoạn clip chèn [8, 15, 30, 60, 120] s. Cấu hình khớp = DEV, tinh chỉnh BẬT. «Bắt được» = có dòng đúng clip giao đoạn thật (nới 3 s).

## Tỉ lệ bắt được theo biến đổi × độ dài đoạn chèn

| Biến đổi | 8 s | 15 s | 30 s | 60 s | 120 s | Báo nhầm (dòng) | Giây quét TB |
|---|---|---|---|---|---|---|---|
| goc | 0/3 | 0/3 | 3/3 | 3/3 | 3/3 | 0 | 15 |
| nen_24k | 0/3 | 0/3 | 1/3 | 3/3 | 3/3 | 0 | 15 |
| nhac_de | 0/3 | 0/3 | 0/3 | 1/3 | 3/3 | 0 | 15 |
| giong_de | 0/3 | 0/3 | 1/3 | 3/3 | 3/3 | 0 | 16 |
| nhanh_3 | 0/3 | 0/3 | 2/3 | 3/3 | 3/3 | 0 | 27 |
| nhanh_6 | 0/3 | 0/3 | 2/3 | 3/3 | 3/3 | 0 | 22 |
| cao_do_1 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0 | 56 |
| tua_5 | 0/3 | 0/3 | 0/3 | 0/3 | 3/3 | 0 | 60 |

## Lệch mốc «Đoạn vi phạm» (giây; trung vị / p90 / lớn nhất của |lệch|) trên các đoạn bắt được

| Nhóm | Số đoạn | Đầu — lượt quét | Cuối — lượt quét | Số đã tinh chỉnh | Đầu — tinh chỉnh | Cuối — tinh chỉnh |
|---|---|---|---|---|---|---|
| (tất cả) | 46 | 3.8 / 7.2 / 16.8 | 4.2 / 8.7 / 21.0 | 41 | 0.0 / 0.0 / 0.1 | 0.0 / 0.0 / 0.1 |
| goc | 9 | 3.3 / 7.6 / 8.5 | 3.6 / 6.3 / 13.1 | 9 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| nen_24k | 7 | 5.3 / 6.0 / 6.6 | 4.9 / 6.4 / 10.7 | 7 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| nhac_de | 4 | 4.5 / 16.8 / 16.8 | 7.7 / 21.0 / 21.0 | 2 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| giong_de | 7 | 4.0 / 6.6 / 11.4 | 5.3 / 8.7 / 17.6 | 7 | 0.0 / 0.1 / 0.1 | 0.0 / 0.0 / 0.1 |
| nhanh_3 | 8 | 4.1 / 6.9 / 9.8 | 4.2 / 6.7 / 7.4 | 8 | 0.0 / 0.0 / 0.1 | 0.0 / 0.0 / 0.0 |
| nhanh_6 | 8 | 4.3 / 6.9 / 7.1 | 3.4 / 6.2 / 8.2 | 8 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| tua_5 | 3 | 1.9 / 3.4 / 3.4 | 2.4 / 8.6 / 8.6 | 0 | — | — |

## Báo nhầm

- Đối chứng âm: 0 dòng trên 2.0 giờ (≈ 0 dòng / 100 giờ, kho 60 clip — kho thật lớn hơn 10–30 lần nên số thật có thể cao hơn).
- Trong ca có chèn: 0 dòng không thuộc đoạn chèn nào trên 7.9 giờ.

## Cờ và nhãn

- Mốc mơ hồ: 0/46 đoạn bắt được.
- Trạng thái tinh chỉnh: {'da_tinh_chinh': 41, 'chua_tinh_chinh': 5}
- Nhãn độ tin cậy: {'Rất chắc chắn': 46}
