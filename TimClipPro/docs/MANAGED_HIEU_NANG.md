# Đo hiệu năng — bản cũ 6dc3f9d so với bản managed (07/10/2026, PC1)

Cùng đầu vào TỔNG HỢP (không mạng): 4 clip 30 s + video 6 phút chứa 3 clip ở mốc đã biết; audfprint/ffmpeg thật;
Python 3.12.10, SQLite 3.49.1. Script: `D:\TimClipPro_ManagedRuntime\20261007_203532\scripts\do_hieu_nang.py`,
`do_cap_nhat.py` (ngoài repo); số liệu thô: `evidence\hieu_nang\{cu_6dc3f9d,moi,cap_nhat}.json`. Một lần đo trên
một máy — không hứa nhanh như nhau trên phần cứng khác.

| Chỉ số | 6dc3f9d | Bản mới | Nhận xét |
|---|---|---|---|
| Dựng kho 4 clip | 13,76 s, 1 lần audfprint | 14,16 s, 1 lần audfprint | Trong sai số; số lần gọi như nhau |
| Quét video 6 phút | 5,72 s, 1 lần audfprint | 5,70 s, 1 lần audfprint | Kết quả khớp **giống hệt** (clip, mốc, số hash) |
| Lưu lần quét (không đích gửi) | 6,07 ms (p95 9,4) | 5,87 ms (p95 6,9) | Không đổi |
| Lưu lần quét + xếp hàng gửi (cùng giao dịch) | — | 6,31 ms (p95 6,9) | +0,4 ms/lần |
| Dung lượng lịch sử mỗi lần quét | 4,5 KB | 4,5 KB (không gửi) / 6,8 KB (có gửi) | +2,2 KB = payload + đích ghim |
| Độ trễ từ lưu → «Đã gửi» (transport giả tức thì) | — | trung vị 47 ms, tối đa 51 ms | Người gửi nền được đánh thức ngay sau commit |
| CPU người gửi nền khi rảnh (20 s) | — | 0,0 s CPU | Chờ theo chu kỳ, không bận |
| Request Google mỗi lần gửi (gspread thật, phiên HTTP giả) | 1–2 (đọc tiêu đề + ghi; không kiểm tab) | 4 = 3 đọc + 1 ghi | 2 lần đọc metadata (gspread đọc lại khi tìm tab theo mã) + 1 đọc hàng tiêu đề + 1 `append`. 429 → hoãn cả nhóm, có trần |
| Đóng gói + ký bản phát hành | — | 0,08 s; gói 482 KB, 163 file | ZIP tất định |
| Bootstrap + cài bản đầu | — | 2,5 s | Runtime venv thật (chế độ thử, không pip), 2 lần health check thật |
| Chuẩn bị bản mới / áp dụng | — | 1,2 s / 0,8 s | Runtime dùng lại (cùng lock) |

Ngân sách đặt TỪ số đo (kiểm lại ở pilot): lưu + xếp hàng ≤ lưu cũ + 2 ms (trung vị); độ trễ gửi cục bộ
≤ 200 ms (chưa tính Google); CPU rảnh ≈ 0; quét: số lần audfprint và kết quả khớp KHÔNG được khác bản cũ.

Cơ hội tối ưu (chưa làm, không ảnh hưởng đúng/sai): gom các việc cùng tab trong một vòng gửi để dùng lại
metadata + kiểm tiêu đề (4N → 3 + N request cho N việc).
