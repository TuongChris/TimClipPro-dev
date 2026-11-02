# Tiếp tục dự án trên máy mới (clone từ GitHub)

Viết 02/11/2026 trên PC2 (máy công ty) theo yêu cầu chủ dự án: nếu phải xoá sạch máy công ty, chỉ cần đăng nhập GitHub,
clone repo về máy mới (ví dụ máy ở nhà) là Claude Code hiểu và phát triển tiếp được. Repo `TuongChris/TimClipPro-dev` là
**PUBLIC** (D-22): không bao giờ đưa khoá, cookie, link Google Sheet thật, dữ liệu kho hay bộ nhớ của Claude lên đây.

## 1. Trên GitHub đã có gì — đọc theo thứ tự này
1. `CLAUDE.md` (gốc repo) — quy tắc phiên làm việc; Claude Code tự nạp, kèm `docs/ai/CURRENT_STATE.md`.
2. `docs/ai/TONG_HOP_DU_AN.md` — toàn cảnh dự án: tính năng, công nghệ, kiến trúc, lịch sử, quyết định, bài học.
3. `docs/ai/handoff/PC2.md` mục «Tiếp theo» — việc đang dở; `docs/ai/DECISIONS.md` — mọi quyết định của chủ dự án.
4. `TimClipPro/CLAUDE.md` + `.claude/rules/` (bất biến theo vùng, tự nạp), `TimClipPro/docs/LOI_DA_GAP.md` (lỗi đã gặp).

Nhánh mặc định = `integration/current` (mã đã kiểm, đang chạy thật). Mọi commit của PC2 đến 02/11/2026 đều đã đẩy.

## 2. KHÔNG có trên GitHub (cố ý) — và cách có lại
| Thứ | Ở máy công ty | Trên máy mới |
|---|---|---|
| Dữ liệu DEV: kho vân tay `*.pklz`, `lichsu.db`, `khos.json`, `cau_hinh.json` (~0,8 GB) | `C:\Dev\TimClipPro_DevState\data`; bản sao lưu `D:\TimClipPro_Dev_SaoLuu\data_<giờ>` | Chép bản sao lưu mới nhất ra ổ CÁ NHÂN trước khi xoá máy; hoặc dựng lại (đồng bộ kênh + tạo vân tay: nhiều giờ) |
| Audio các kho gốc (~75 GB: Cory, Flamingo, Joe, MSA, Papa Meat, SML, Ms Rachel, Danny) | `E:\Kho_Tool_Quet\Kho_*` (mỗi kho có `downloaded.txt`, `clips_meta.json`) | Ổ cá nhân; hoặc đồng bộ kênh tải lại (chỉ tải phần thiếu) |
| Khoá Google service account `google_key*.json` | thư mục mã + `DevState\secrets` | Tạo khoá MỚI trong Google Cloud Console; xoá khoá cũ |
| Cookie YouTube `cookies.txt` | `E:\cookies.txt` | Xuất lại từ trình duyệt đã đăng nhập ở máy mới |
| Khoá ký phát hành PC2 `d02702dd741c3e4f` | `C:\TimClipPro_KhoaPhatHanh` (chỉ người dùng đọc) | Không cần để phát triển; khoá PC1 `8aa5baa6c8f225f9` vẫn được tin. Không mang theo → thu hồi khỏi `release/trusted_keys.json` bằng PR riêng |
| `CLAUDE.local.md` (ghi chú riêng máy) | gốc clone | Tạo lại từ `docs/ai/CLAUDE.local.md.mau` (mục 3) |
| Bộ nhớ tự động + lịch sử chat của Claude | `%USERPROFILE%\.claude\projects\…` | Riêng tư, không lên repo công khai. Bài học quan trọng đã chép vào mục 4 + handoff |
| Bằng chứng test, công cụ thử riêng PC2 | `C:\Dev\pc2_test_runs`, `C:\Dev\pc2_test_tools` | Chỉ để tham khảo. Hai công cụ test cần dùng đã có trong `tools/test/` |
| Stable đã cài (managed) | `C:\TimClipPro*` | Tải bản phát hành từ GitHub Release nếu cần |

## 3. Dựng môi trường phát triển (Windows)
1. Cài Git, GitHub CLI, Python 3.12 64-bit (python.org), Node.js ≥ 22, FFmpeg (`winget install Gyan.FFmpeg`).
2. `gh auth login`, rồi clone với tên remote `private` như tài liệu dùng:
   `git clone -o private https://github.com/TuongChris/TimClipPro-dev.git C:\Dev\Tool_Quet`
3. Môi trường Python (đúng lock có băm, như bản chạy thật):
   ```
   cd C:\Dev\Tool_Quet\TimClipPro
   py -3.12 -m venv .venv
   .venv\Scripts\python -m pip install --require-hashes -r ..\release\locks\requirements-lock.txt
   .venv\Scripts\python -m pip install pytest ruff
   ```
4. Hook kiểm bí mật trước khi đẩy: chép `release/git-hooks/pre-push` vào `.git\hooks\pre-push`.
5. `CLAUDE.local.md` ở gốc clone: chép từ `docs/ai/CLAUDE.local.md.mau`. Máy mới THAY máy công ty thì ghi «Máy: PC2 (máy mới
   thay máy công ty)» và giữ dòng cuối `@docs/ai/handoff/PC2.md` để Claude đọc tiếp đúng handoff.
6. Chạy test (trong `TimClipPro\`; `chan_mang` chặn mọi kết nối mạng ra ngoài khi test):
   ```
   set PYTHONPATH=..\tools\test\chan_mang
   .venv\Scripts\python -m pytest -q -p no:cacheprovider --junitxml=%TEMP%\junit.xml
   .venv\Scripts\python ..\tools\test\doc_junit.py %TEMP%\junit.xml
   ```
   Mốc 27/10/2026: nhanh 3328 = 3324 đạt / 4 bỏ qua do môi trường / 0 hỏng; chậm (`-m slow`) 22/22.
7. Chạy ứng dụng Development — CHỈ cổng 8502, dữ liệu ngoài thư mục mã:
   ```
   set TIMCLIP_DATA_DIR=C:\Dev\TimClipPro_DevState\data
   set TIMCLIP_OUTPUT_DIR=C:\Dev\TimClipPro_DevState\output
   set TIMCLIP_RUNTIME_MODE=legacy
   set TIMCLIP_DEV_MODE=1
   .venv\Scripts\python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8502 --server.fileWatcherType=none
   ```

## 4. Quy tắc làm việc rút ra từ sự cố (Claude phải theo)
- **Mỗi việc xong: commit + đẩy nhánh việc lên GitHub** (chủ dự án dặn 02/11/2026) — GitHub là bản lưu trữ chính. Gộp vào
  `integration/current`, phát hành, đổi cấu hình GitHub vẫn hỏi chủ dự án như `CLAUDE.md` quy định. Trước khi đẩy: quét bí mật.
- **Trước khi dừng app 8502: chứng minh không có việc chạy.** yt-dlp tải TRONG tiến trình (không có tiến trình con): kiểm
  kết nối ra ngoài, CPU/IO, file mới ghi trong thư mục kho và dữ liệu. 15/10 từng giết nhầm một lượt đồng bộ đang chạy.
- **Cookie lỗi thì làm cho đăng nhập chạy được, nói rõ khi đang tải KHÔNG đăng nhập** — chủ dự án từ chối bản sửa chỉ lặng
  lẽ lùi về không cookie.
- Không đặt backtick trong chuỗi `"..."` của bash (từng chạy nhầm `git checkout`); chuỗi Python có `\2026` (đường dẫn
  Windows) phải dùng raw string hoặc ghi file bằng công cụ Write.
- Tạo vân tay kho lớn nhiều livestream dài: «Số nhân CPU» 2–3 (8 worker từng hết RAM — 27/10, Kho Cory).
- Sửa lỗi: tái hiện bằng dữ liệu GIẢ và một test ĐỎ trước khi sửa; không bao giờ test trên dữ liệu thật.

## 5. Trước khi rời máy công ty (chủ dự án tự làm)
- Chép ra ổ cá nhân: bản sao lưu DEV mới nhất (`D:\TimClipPro_Dev_SaoLuu\data_<giờ mới nhất>`) và (tuỳ) audio `E:\Kho_Tool_Quet`.
- GitHub → repo → Settings → Deploy keys: xoá khoá «PC2 PC_Office» (có quyền GHI). Trên máy công ty: `gh auth logout`.
- Google Cloud Console: xoá khoá service account đã đặt trên máy công ty. Đăng xuất Google/YouTube trong trình duyệt máy công ty.
- Khoá ký PC2 không mang theo → báo Claude ở máy mới làm PR thu hồi khỏi `release/trusted_keys.json`.
