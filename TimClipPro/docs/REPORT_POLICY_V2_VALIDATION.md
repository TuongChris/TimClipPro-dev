# Báo cáo V2 — bằng chứng nghiệm thu

Hợp đồng: `docs/REPORT_POLICY_V2.md`. Ngày: 04/10/2026. Gốc: `7ee527a`. Repo công khai nên tài liệu
này KHÔNG chứa mã video, tên kho, số liệu lịch sử hay số đo của ca thật — các con số đó nằm ở báo
cáo nghiệm thu ngoài repo. Mọi mã video/kênh, tiêu đề, ngày, thời lượng, thời điểm quét và số hash
trong test là TỔNG HỢP; ca người dùng nêu được dựng lại bằng số giả giữ đúng hình dạng (mốc đầu
`00:15:15` → `t=915`, ngày nguyên bản và ngày quy đổi lệch một ngày, mốc kết thúc khác «mốc đầu +
thời lượng gốc»).

## Môi trường

- Windows 11, Python 3.12.10 của app (`.venv`, không cài thêm gì) + pytest 9.1.1 nạp qua
  `PYTHONPATH` riêng; FFmpeg/FFprobe của máy (chỉ đọc).
- Rào chắn kiểm thử (audit hook PEP 578, nạp vào MỌI tiến trình Python con): chặn mọi kết nối
  mạng ra ngoài loopback (YouTube, Google, GitHub) và chặn ghi vào thư mục production, các worktree
  khác, thư mục kho, bản sao lưu, bằng chứng các vòng trước, file cookie. Tự kiểm 34/34 ca. Tổng
  hợp nhật ký rào chắn của các cổng dưới đây: 0 kết nối mạng bị chặn (không test nào thử gọi ra
  ngoài), 0 vi phạm ghi.
- Cây đã nghiệm thu: `git write-tree` trước khi commit; mọi cổng chạy trên đúng cây đó (bản
  `git archive` cho test chậm, đột biến và `kiemtra.bat`).

| Commit | Cây | Nội dung |
|---|---|---|
| 1 | `655a1623` | Báo cáo V2: code, test, hợp đồng — chưa có thay đổi `GiamSat.bat` |
| 2 | `73ad4e47` | + `GiamSat.bat` bỏ link Sheet ghi cứng (+ test) — cây cổng chính |
| 3 | — | + tài liệu này (chỉ tài liệu; không test nào đọc `docs/`) |

## Kết quả

| Cổng | Kết quả |
|---|---|
| Suite nhanh, cây gốc `7ee527a` | 1765 test: 1763 đạt, 2 bỏ qua, 0 hỏng |
| Suite nhanh, cây commit 2 (worktree) | 1923 test: 1921 đạt, 2 bỏ qua, 0 hỏng (+158 test) |
| Suite nhanh, cây commit 1 (bản `git archive`) | 1919 test: 1911 đạt, 8 bỏ qua, 0 hỏng — 6 bỏ qua thêm là test `.gitignore` chỉ chạy trong repo git; 4 test của `GiamSat.bat` chưa có |
| Suite chậm (`-m slow`, audio thật), cây commit 2 | 13/13 đạt |
| Golden đường quét cũ (28 kịch bản sinh trên `f87cc85`) | trong suite nhanh — không đổi một byte |
| AppTest (giao diện thật, 2 chế độ quét) | trong suite nhanh |
| Ruff, `git diff --check`, `pip check`, import lõi | sạch |
| `audfprint-master/`, requirements | không đổi |
| Đột biến (45 đột biến của quy tắc V2, cây commit 2) | 45/45 bị bắt; lượt đối chứng không đột biến xanh |
| `kiemtra.bat` (bản `git archive`, cây commit 2) | ĐẠT — cả 3 bước |
| Nâng cấp lịch sử trên BẢN SAO lịch sử thật (ngoài repo) | dòng và cột cũ y nguyên, bản sao lưu = trạng thái trước, chạy lại không làm gì, code cũ (`fe07985`) vẫn đọc/ghi được, `integrity_check` ok |
| Quét bí mật trên khoảng commit + đối chứng dương | sạch (mọi blob mới + thông điệp commit); đối chứng: máy quét bắt đủ 7/7 loại bí mật giả cài vào |

Đột biến theo nhóm (mỗi đột biến phải làm ĐỎ ít nhất một test):

- Tên: nối lại hậu tố `[QUÉT MỘT PHẦN]`; lấy URL làm tên (exporter, wrapper `title_raw`).
- Mốc/link: lùi 3 giây; làm tròn thay vì cắt; NaN/âm thành mốc 0; nhận host giả; link gốc
  `youtu.be`; mốc kết thúc = mốc đầu + thời lượng gốc.
- Ngày: dùng ngày đã quy đổi (wrapper, thứ tự đọc, `timestamp` của kho, lùi về ngày kho); thứ tự
  nguồn ngày trong ảnh chụp; clip mới lưu ngày quy đổi vào `upload_date_raw`.
- Vòng đời: không lưu ảnh chụp; bỏ chính sách khi đọc lịch sử; dựng lại bảng dọc/ngang/hồ sơ bằng
  resolver hiện tại; Engine gốc mặc định V2; lô nguồn chung không mang chính sách đã ghim.
- Sheets: bỏ kiểm hàng tiêu đề; tự chèn tiêu đề; bỏ cờ nghiêm ngặt (hàng đợi, giao diện, Watch);
  thử lại lỗi tiêu đề; thêm dấu `'`.
- CSV: thôi chặn công thức; không kèm file phạm vi.
- Bổ sung ngày gốc: mặc định bật; bỏ cầu dao; bỏ trần; không dùng lại kết quả; quét file cũng hỏi;
  hỏi cho mọi ứng viên; lỗi làm hỏng lượt quét; bỏ qua lệnh Dừng; nguồn chung hỏi khi quét file.
- Lược đồ: nâng cấp không tạo bảng ảnh chụp; ảnh chụp thành cột của `jobs`.

## Test mới (theo ma trận brief §15)

| Nhóm | File |
|---|---|
| Tên, mốc/link, URL gốc, ngày, ảnh chụp, dòng 34/16 cột | `tests/test_bao_cao_v2.py` |
| Đường quét thật (thế giới giả của golden): ảnh chụp, cũ/mới cạnh nhau, lịch sử, khởi động lại, đồng nhất exporter, CSV/Sheets escape, file phạm vi, không gọi mạng khi xuất | `tests/test_bao_cao_v2_quet.py` |
| Ngày nguyên bản video gốc + bổ sung: mặc định tắt, chỉ video gốc đã chọn, dùng lại trong batch/lượt Watch, trần, cầu dao, Dừng, video gốc bị gỡ, quét file, không ghi ngược clips_meta | `tests/test_bao_cao_v2_ngay_goc.py` |
| Sheets nghiêm ngặt, payload chốt, thử lại | `tests/test_bao_cao_v2_sheets.py` |
| Lịch sử phiên bản 2: sao lưu, giữ dòng cũ, idempotent, rollback | `tests/test_bao_cao_v2_lich_su.py` |
| Nguồn chung V2 | `tests/test_bao_cao_v2_nguon_chung.py` |
| Clip mới lưu `upload_date_raw` | `tests/test_bao_cao_v2_kho_moi.py` |
| Hợp đồng Apps Script (fixture) | `tests/test_bao_cao_v2_apps_script.py` |
| Giao diện: xuất lại từ ảnh chụp, công tắc bổ sung | `tests/test_bao_cao_v2_app.py` |
| `GiamSat.bat` không mang link Sheet | `tests/test_giam_sat_bat.py` |

Mọi test mặc định offline: số lần gọi YouTube trong test = số lần gọi bản giả đếm được (0 request
thật — rào chắn chặn ở tầng socket).

## Test cũ được cập nhật (có lý do)

- `test_engine_meta.py::test_youtube_info_lay_du_khoa`: `youtube_info` thêm khoá `title_raw`
  (khoá cũ y nguyên) — test ghim đúng danh sách khoá nên khai thêm khoá mới.
- `test_pham_vi_quet.py::test_bao_cao_ngang_va_doc_mang_pham_vi_ma_khong_them_cot`: luật cũ
  (hậu tố trong tên) vẫn được kiểm trên kết quả KHÔNG có ảnh chụp; thêm khẳng định V2 cho lượt
  quét mới (tên sạch, phạm vi ở ảnh chụp).
- `test_truy_cap_youtube_lo.py`: bản `SheetsExporter` giả nhận thêm `**kw` như bản thật (V2 gửi
  `nghiem_ngat=True`) và khẳng định Watch gửi V2 ở chế độ nghiêm ngặt.
- `tests/conftest.py`: fixture tự động trả PATH về như cũ sau mỗi test — `Engine(root=…)` chèn
  `<root>/bin` vào PATH của cả tiến trình; thêm ~150 test tạo Engine riêng làm PATH vượt 32.767
  ký tự của Windows và các test chạy sau hỏng vì lý do không liên quan.

## Chưa làm / giới hạn

Xem `docs/REPORT_POLICY_V2.md` mục 9. Không gọi YouTube hay Google thật trong vòng này; bổ sung
ngày qua mạng chỉ được kiểm bằng bản giả — cần một lượt smoke có kiểm soát (duyệt riêng) trước khi
bật ở máy thật.
