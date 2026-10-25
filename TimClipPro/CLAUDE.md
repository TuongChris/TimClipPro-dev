# TimClip Pro — Ngữ cảnh dự án cho Claude Code

> Claude Code tự nạp file này khi đọc/sửa file trong `TimClipPro/`; điểm vào chung là `CLAUDE.md` ở gốc repo.
> Giữ file NGẮN (< 200 dòng), chỉ bất biến dùng chung. Chuẩn hoá 09/10/2026 từ bản 782 dòng của e49340d — các mục dài
> được CHUYỂN NGUYÊN VĂN, không xoá: bất biến từng vùng → `.claude/rules/`; lịch sử lỗi → `docs/LOI_DA_GAP.md` («mục N»
> ở file này, trong code và test = mục N ở đó); bảng «File và vai trò» (đủ 54 module) → `docs/ai/ARCHITECTURE_INDEX.md`;
> hướng phát triển, lý do bác bỏ PyInstaller → `docs/ai/DECISIONS.md` (hai file sau nằm ở gốc repo).

## Dự án làm gì

Tìm **video gốc của tôi** (clip 5–10 phút) xuất hiện bên trong **video vi phạm** dài
3–30 tiếng, bằng **audio fingerprinting**. Chạy 100% local trên Windows. Người dùng
là người làm nội dung, **không phải lập trình viên** — mọi thứ phải bấm nút là chạy.

## Kiến trúc — quy tắc bất di bất dịch

```
app.py (Streamlit UI)   cli.py (dòng lệnh)   ← lớp giao diện, thay được
                    ↘        ↙
                    engine.py                 ← LÕI, không biết ai gọi nó
              ↙        ↓         ↘
   channel.py    sheets.py    audfprint-master/
   (tải kênh)   (Google Sheets)  (thư viện MIT, ĐỪNG SỬA)
        ↘        ↙
      ytdlp_chung.py        ← MỌI tuỳ chọn yt-dlp đi qua đây, không có ngoại lệ
            ↓
      truy_cap_youtube.py   ← MỌI lỗi YouTube được phân loại ở đây; cầu dao + thử lại hữu hạn
```

**Quy tắc:**
1. `engine.py` **không được** `import streamlit`, không `print()`, không `input()`.
   Mọi tiến độ đi qua callback `progress(pct: float, msg: str)`.
2. Logic nghiệp vụ mới → viết vào `engine.py` hoặc module riêng, **không** viết trong `app.py`.
3. `audfprint-master/` là thư viện bên thứ ba — **không sửa**. Cần đổi hành vi thì bọc lại
   trong `engine.py`.
4. Mọi chuỗi hiển thị cho người dùng viết bằng **tiếng Việt**.
5. **Không bao giờ dựng dict tuỳ chọn `yt_dlp.YoutubeDL` bằng tay.** Luôn đi qua
   `ytdlp_chung.CauHinhMang.tuy_chon()`. Ba lần trong một ngày (mục 6, 6b, 6c) cùng một
   lỗi chỉ được vá ở một trong hai đường tải vì tuỳ chọn bị chép tay ở nhiều chỗ.
6. **Mọi thao tác mạng YouTube chạy qua `PhienYouTube.chay()` của LƯỢT đang chạy** (mục 17).
   Không tự viết vòng thử lại hay `time.sleep`, không `if "bot" in str(e)` ở nơi gọi — hiểu lỗi
   chỉ ở `truy_cap_youtube.phan_loai_loi`. Vòng lặp nhiều video hỏi `phien.mo` trước mỗi việc mạng.

## Kiến thức nghiệp vụ quan trọng (đã kiểm chứng bằng thực nghiệm)

- **Chỉ audio là đủ.** Fingerprint chỉ dùng âm thanh; pixel không đóng góp gì. Đã đo:
  clip nén opus mono 64 kbps cho **225 hash** so với **221 hash** của video gốc khi
  đối chiếu với bản đã bị nén lại. Nén xuống 32 kbps vẫn tìm đúng vị trí nhưng hash
  giảm còn ~50% → **64 kbps mono 16 kHz là điểm tối ưu**, đừng hạ thấp hơn.
- audfprint hạ mẫu về 11025 Hz nên chỉ dùng phổ tới ~5.5 kHz. Lưu audio > 16 kHz là lãng phí.
- Overlap hiệu lực phải nằm trong `[60, overlap_max_s]`; mặc định
  `overlap_max_s=180`. Clip dài hơn trần có thể bị chia thành nhiều mảnh ở ranh giới
  khúc; `_merge()` phải phục hồi bằng chứng bằng hợp interval và mật độ hash tốt nhất,
  không được tăng overlap vượt trần để bao trọn clip dài nhất.
- Điểm mù đã biết: video vi phạm bị **thay/đè toàn bộ tiếng** thì phương pháp này bó tay.
  Hướng mở rộng khi cần: pHash + OpenCV, cao hơn nữa là VCSL/TransVCL (cần GPU).
- `data/db.pklz` chứa vân tay; `clips_meta.json` (trong thư mục kho) map tên file →
  tiêu đề + link YouTube gốc. Báo cáo dựa vào cả hai.

## Quy ước code

- Python 3.10+, chuẩn PEP 8, dùng type hint ở chữ ký hàm public.
- Tên hàm/biến nội bộ có thể bằng tiếng Việt không dấu (`tao_db`, `lam_sach_ten`) —
  giữ nhất quán với code hiện có.
- Tác vụ dài **bắt buộc** nhận `progress` callback và kiểm tra `cancel_event`.
- Không dùng `localStorage`/`sessionStorage` (không áp dụng), không dùng biến toàn cục
  cho trạng thái job — dùng `st.session_state` ở tầng UI.
- Xử lý lỗi: hàm cấp cao trả `ScanResult(status="error", note=...)` thay vì ném exception
  ra tận UI, để quét hàng loạt không bị đứt giữa chừng.

## Quy ước khoá

- Mọi thao tác nặng có thể đọc hoặc ghi kho vân tay, lịch sử hay dữ liệu giám sát phải dùng
  chung khoá cấp hệ điều hành `data/tool.lock`. Tên chủ khoá vẫn phải mô tả đúng thao tác
  đang chạy để thông báo bận có ích cho người dùng.
- Nếu sau này thật sự cần nhiều khoá, phải quy định và tuân thủ một thứ tự lấy khoá cố định
  trên toàn dự án. Không được lấy các khoá theo thứ tự tùy ý vì sẽ tạo kẹt chéo.
- Thứ tự đã quy định (`docs/MANAGED_RUNTIME_DESIGN.md` §6): cổng bảo trì → lease của việc →
  `data/tool.lock` → `data/khoa_tai/<tên>.lock` (một lượt tải audio của một video, audit D-3) → khoá
  JSON `.timclip.lock` → `data/hang_doi_gui.lock` (quyền người gửi Sheets) → giao dịch SQLite. Trong giao dịch ghi SQLite: không chờ khoá HĐH, không gọi mạng.

## Bất biến theo vùng — tự nạp từ `.claude/rules/` khi đụng file của vùng

| Vùng | Rule (gốc repo) | Mục chuyển nguyên văn từ bản cũ |
|---|---|---|
| Quét, so khớp, «Một video gốc chung cho cả lô» | `.claude/rules/matcher.md` | «Chế độ «Một video gốc chung cho cả lô» — bất biến» |
| Google Sheets, outbox | `.claude/rules/sheets-outbox.md` | «Hàng đợi gửi Google Sheets (outbox) — bất biến» |
| Cài đặt managed, cập nhật, phát hành | `.claude/rules/updater.md` | «Cài đặt managed (PC2) — bất biến bố cục» |

Sắp sửa một file của vùng mà rule chưa có trong ngữ cảnh → đọc thẳng file rule đó trước khi sửa.

## Ý nghĩa các trường thời gian trong Match

- `clip_bat_dau_s`: thời điểm **clip bắt đầu** trong video dài; dùng để hiển thị và tạo link
  nhảy mốc. `start_s` mang cùng ý nghĩa này.
- `vung_khop_s`: thời điểm **vùng vân tay bắt đầu khớp**, không phải đầu clip.
- `clip_offset_s`: độ dài phần đầu clip gốc đã bị bỏ qua trước khi vùng khớp bắt đầu.

Ba khái niệm trên không được dùng thay thế cho nhau. Khi dựng báo cáo hoặc link mốc, luôn dùng
thời điểm clip bắt đầu; khi chẩn đoán vân tay mới dùng vùng khớp và offset.

## Báo cáo V2 — bất biến (docs/REPORT_POLICY_V2.md)

- Chính sách báo cáo GHIM ở ranh giới job (`Engine._ban_sao_cho_job`); ảnh chụp `ScanResult.bao_cao`
  chốt cuối lượt quét, trước `save_job`/xếp hàng Sheets. Exporter đọc chính sách TỪ KẾT QUẢ:
  `bao_cao is None` = luật cũ y nguyên (golden, lịch sử cũ). Đừng cho dataclass mặc định V2, đừng
  để exporter hỏi hằng hiện hành hay resolver hiện tại cho kết quả V2.
- `None` CHỈ có nghĩa luật cũ thật. Lượt V2 dựng ảnh chụp lỗi, hay ảnh chụp đã lưu không đọc
  được, mang `bao_cao_v2.LoiBaoCaoV2` (dấu lỗi lưu cùng lần quét) → mọi exporter/đường Sheets ném
  `LoiXuatBaoCaoV2`; nơi gọi tách bằng `tach_loi_bao_cao` và BÁO lỗi. Đừng bao giờ «lùi về luật
  cũ» khi V2 hỏng — đó là lỗi P1-02 của audit độc lập 05/10/2026. Xoá lần quét xoá cả `bao_cao_job`
  cùng giao dịch (P1-01).
- Ảnh chụp lưu ở bảng RIÊNG `bao_cao_job` (lịch sử phiên bản 2) — KHÔNG thêm cột vào `jobs`
  (golden so `SELECT * FROM jobs`, bản rollback đọc theo tên cột).
- Ngày V2 = `upload_date` NGUYÊN BẢN của yt-dlp. `youtube_info()["upload_date"]` là ngày ĐÃ quy
  đổi — chỉ `upload_date_raw` là nguyên bản. Kho cũ chỉ có ngày quy đổi: để trống kèm lý do, không
  đoán từ `timestamp`/tên file. Bổ sung qua mạng chỉ cho video gốc ĐÃ CHỌN, mặc định TẮT.
- Mốc hiển thị và `t` của link là CÙNG một giây (`bao_cao_v2.giay_moc`). Không trừ 3 giây, không
  cộng thời lượng gốc vào `end_s` (mốc kết thúc bị cắt bởi `--time-quantile` 0,05 của audfprint —
  sửa là đổi tham số khớp, cần duyệt riêng).
- Gửi Sheets V2: nguyên văn (RAW, không thêm `'`), nghiêm ngặt — hàng tiêu đề sai là dừng, không
  chèn/sửa hàng 1. CSV vẫn chặn công thức ở tầng ghi. Hàng 1 trống CHƯA phải bảng rỗng: dò lần hai
  toàn trang tính, có bất kỳ ô nào là dừng, không ghi gì (P1-03).

## Kiểm thử — LÀM ƠN CHẠY TRƯỚC KHI BÁO XONG

Dự án có khoảng 2.450 test nhanh và 14 test chậm (số thật trên e49340d và cách chọn test theo vùng:
`docs/ai/TEST_MATRIX.md` ở gốc repo). Trước khi kết luận một thay đổi là xong, phải chạy tối thiểu:

```bash
# 1) Toàn bộ suite nhanh
python -m pytest -q

# 2) Hai test tích hợp audio tổng hợp
python -m pytest -m slow

# 3) Lõi còn import sạch không
python -c "import engine, channel, sheets; print('ok')"
```

**Test KHÔNG BAO GIỜ được ghi vào `data/` của thư mục mã** (trên máy thật đó là lịch sử thật): luôn
`tmp_path` + `TIMCLIP_DATA_DIR`/`TIMCLIP_OUTPUT_DIR`. Bẫy đã gặp (07/10/2026): AppTest để lại
`sys.modules['__main__']` = app.py, nên tiến trình con multiprocessing (spawn) của test sau chạy lại app.py
trên `data/` mặc định — `conftest._tra_lai_main_module` trả lại `__main__` sau mỗi test.

**Nếu tôi nhờ thêm tính năng, hãy tự viết test nhỏ để tự kiểm chứng trước khi báo cáo,
đừng chỉ nói "đã xong".** Với thay đổi liên quan chất lượng khớp, hãy tạo dữ liệu giả lập
(chèn 1 clip vào file dài ở mốc đã biết) rồi kiểm tra vị trí trả về có đúng không.

## Ranh giới an toàn — ĐỪNG tự ý làm

- **Đừng xoá hay ghi đè** `data/db.pklz`, `data/lichsu.db`, `downloaded.txt`,
  `clips_meta.json` — mất là phải fingerprint lại hàng chục giờ.
- **Đừng commit** `google_key.json` (khoá riêng Google) — đã có trong `.gitignore`.
- **Đừng đổi** thuật toán gộp trùng (`_merge`) hay ngưỡng mặc định nếu tôi không yêu cầu:
  chúng đã được hiệu chỉnh bằng thực nghiệm.
- **Đừng thêm** thư viện nặng (torch, tensorflow...) nếu chưa hỏi tôi — máy tôi không có GPU.
- Thay đổi lớn: giải thích phương án **trước**, chờ tôi đồng ý rồi mới code.

## Quy tắc rút ra từ lỗi đã gặp — chi tiết, số đo, bối cảnh: `docs/LOI_DA_GAP.md` (giữ nguyên số mục)

- (1) Mọi subprocess Python đi qua `_run_stream()` (env UTF-8, cờ `-u`); không sửa thư viện bên thứ ba.
- (2) Không nuốt lỗi tiến trình con: giữ các dòng cuối; «chạy xong nhưng xử lý 0 file» cũng là lỗi.
- (4) Không `os.remove()` trực tiếp file .pklz — dùng `_xoa_an_toan()`; không dùng `hash_table.HashTable(path)` ở
  tiến trình cha.
- (6, 6b, 6c, 9) Dự án có nhiều đường gọi yt-dlp: mọi tuỳ chọn qua `ytdlp_chung`; đổi cấu hình mạng thì rà MỌI nơi gọi;
  không khoá cứng vào một player client.
- (7) Cột số khai báo trong `Engine.COT_SO`; ô không đo được để NaN, không điền 0.
- (8) Không tin cờ `quiet` của thư viện để giữ bí mật: chặn ở đầu nguồn và lọc ở đầu ra.
- (10) Cookie hết hạn tệ hơn không có cookie; hạn ghi trong file không phản ánh phiên còn sống.
- (11) Đo tải phải TẢI ĐẦY ĐỦ — `test=True` (tải vài KB đầu) báo «OK» nhầm.
- (12) Trước khi kết luận từ bảng `matches`, kiểm `top_n` của thời kỳ sinh dữ liệu. Dừng-khi-thấy chỉ đổi THỨ TỰ, không
  đổi ĐỘ PHỦ: không thấy gì thì phải quét hết video.
- (13, 16) Sửa một trường phái sinh (`duration_s`) thì rà MỌI thứ tính từ nó; đổi `duration_s` ở đâu thì gọi
  `_dan_lai_nhan_vung` ngay sau đó. Vá bằng tìm-thay chuỗi phải kiểm lại bằng test tích hợp.
- (14) Âm tính bị nghi là bug: kiểm lịch sử và một đối chứng dương cùng kênh/cùng ngày trước khi đọc code.
- (15a) Không tự lật lưới bù tốc độ về mặc định (đánh đổi của người dùng); việc của tool là làm nó nhìn thấy được.
- (15c) Dừng sớm phải thoả CHÍNH SÁCH chọn lọc (đủ `top_n`, đủ clip khác nhau khi bật), không chỉ «có một ứng viên».
- (15d) `ten_file_an_toan` là hàm HIỂN THỊ, `ten_file_hop_le` là hàm ĐƯỜNG DẪN; không bọc
  `contextlib.suppress(Exception)` quanh thao tác ghi.
- (17) Một lượt chạy = một `PhienYouTube`; bị chặn thì dừng; lỗi truy cập không bao giờ là âm tính.

## Quy trình Spec-Driven (Claude lập kế hoạch → Codex viết code)

> Quy trình CŨ (Claude lập kế hoạch → Codex viết code), giữ nguyên văn. Chỉ áp dụng khi người dùng yêu cầu rõ; mặc định
> hiện nay là quy trình phiên trong `CLAUDE.md` ở gốc repo (brief → kế hoạch → TDD → kiểm chứng → handoff).

Khi tôi yêu cầu một tính năng mới, ĐỪNG viết code ngay. Hãy:
1. Đọc `CLAUDE.md` + `.github/copilot-instructions.md` để nắm ràng buộc.
2. Chia tính năng thành 4–6 task nguyên tử, mỗi task đúng 1 file hoặc 1 hàm.
3. Xuất ra `docs/EXECUTION_PLAN.md` theo đúng khuôn trong `docs/PROMPT_CONTRACT.md`.
4. Không viết văn xuôi giải thích ngoài kế hoạch.

Khi tôi dán log lỗi: phân tích nguyên nhân gốc, trả về đúng một khối `## FIX cho TASK n`.

Thứ tự task chuẩn cho dự án này: (1) data model thuần → (2) hàm xử lý thuần →
(3) nối vào `engine.py` → (4) giao diện `app.py` → (5) test.
Lý do: task 1–2 là hàm thuần nên test được ngay không cần I/O, sai sót lộ ra sớm.
