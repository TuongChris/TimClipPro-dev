# Dữ liệu golden mức mảnh — «bóng» của âm thanh lặp (P0, 10/10/2026)

Dùng bởi `tests/test_bong_am_thanh_lap.py`. Mỗi file là ĐÚNG danh sách mảnh thô mà `Engine._merge` nhận ở lần gộp
cuối của một lượt quét thật (audfprint thật qua parser của engine), trên dữ liệu 100% TỔNG HỢP — không có dữ liệu
thật/khách hàng, không có đường dẫn máy (tên clip chỉ giữ basename).

| File | Kịch bản (ground truth tính trực tiếp từ cách dựng) |
|---|---|
| `trich_giua.json` | Nhạc có trống lặp 113 BPM, trích `clip[60 → 360 s]` chèn ở giây 120 → MỘT lần dùng, mốc đầu clip 60,0 s |
| `cat_giua.json` | Bản reup cắt bỏ 12 s giữa clip: `[0, 100) + [112, 300)` liền nhau từ giây 120 → MỘT lần dùng, hai phần có vị trí đặt 120,0 s và 108,0 s |
| `troi_nho.json` | Nhạc lặp dài 480 s chèn nguyên clip ở giây 120, phát chậm 0,12% (dưới ngưỡng bù tốc độ) → MỘT lần dùng, mốc 120,0 s |

Trường trong file: `mo_ta`, `sinh_boi`, `ngay_sinh`, `chinh_sach_nhan_dien` (chữ ký chính sách lúc sinh), ground truth
(`moc_that_s`, `moc_phan_s`, `so_lan_dung`), `duration_s`, `pham_vi_quet_s`, `tong_hash_kho` (cận trên hash theo clip),
`tho` (mảnh thô: `clip, bat_dau, khop, t_clip, hash, he_so, align`; số thực làm tròn 0,001).

## Sinh lại
```bash
cd TimClipPro
python tests/tao_golden_bong_lap.py            # ghi đè tests/golden/bong_lap/*.json
python tests/tao_golden_bong_lap.py <thư_mục>  # hoặc ghi ra chỗ khác để so
```
Cần ffmpeg (PATH hoặc `bin/`). Âm thanh tất định theo seed (`tests/am_thanh_lap.py`, seed 9301–9324 trong script).
Kho vân tay và lượt quét chạy trong thư mục tạm, không đụng `data/` của thư mục mã.

Không tái lập TỪNG BYTE: bảng hash audfprint (depth 100) bỏ ngẫu nhiên phần tràn của ô hash quá đầy
(`audfprint-master/hash_table.py`, `random.randint` không seed) — trống lặp làm tràn nhiều ô, nên số mảnh/hash của bóng
xê dịch giữa các lần sinh. Test chỉ khẳng định tính chất bền (số dòng, mốc ±1 s, không dòng bóng), không so từng số.
Sinh lại = đổi dữ liệu golden: chạy lại test trên mã CŨ (phải đỏ đúng chỗ) và mã mới (phải xanh) trước khi commit.

Bản hiện tại: sinh trên PC2 ngày 10/10/2026 từ `7a76e71` (mã quét = `e49340d`), Config mặc định.
Trên mã đó (trước khi sửa): `trich_giua` 5 dòng / 11 ứng viên đạt chuẩn, dòng chính lệch +7,4 s; `cat_giua` 5 dòng /
12 đạt, một dòng neo vào bóng (99,5 s); `troi_nho` 5 dòng / 12 đạt, dòng chính lệch −2,1 s.
