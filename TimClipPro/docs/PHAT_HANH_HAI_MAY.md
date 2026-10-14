# Phát hành Stable từ PC1 HOẶC PC2 — quy trình, điểm duyệt, khôi phục

Hai máy NGANG QUYỀN (quyết định của người dùng 14/10/2026): **PC2 = máy phát triển + phát hành CHÍNH**, **PC1 = máy dự
phòng**. Máy nào cũng làm trọn: phát triển → review → tích hợp → build → ký (khoá RIÊNG của máy đó) → kiểm → phát hành
→ cập nhật. Không máy nào cần máy kia trực tuyến. Repo `TuongChris/TimClipPro-dev` là **PUBLIC** (chủ ý); bản Stable
phân phối bằng **GitHub Release** (không USB/RustDesk).

Ghi danh khoá của một máy vào trust store: `docs/UY_QUYEN_KHOA.md`. Hợp đồng bộ cập nhật: `docs/MANAGED_UPDATE.md`.
Nhánh, PR, hook, ruleset: `docs/ai/GIT_WORKFLOW.md`.

## 0. Một lần cho mỗi máy

| Việc | Ai | Lệnh / nơi |
|---|---|---|
| GitHub CLI đăng nhập bằng tài khoản chủ repo | NGƯỜI DÙNG (trình duyệt) | `gh auth login --hostname github.com --git-protocol ssh --web` (bỏ qua tải khoá SSH); kiểm `gh auth status` |
| Hook `pre-push` dùng chung | Claude | chép `release/git-hooks/pre-push` → `$(git rev-parse --path-format=absolute --git-path hooks)/pre-push` (GIT_WORKFLOW «Hook pre-push») |
| Khoá ký phát hành của máy (Ed25519, mã hoá) | NGƯỜI DÙNG gõ mật khẩu | `release_tool.py tao-khoa --thu-muc <X>:\TimClipPro_KhoaPhatHanh --ten-may PC2` (qua `.bat`, §7) |
| Ghi danh khoá vào trust store PC2 | PC2 + MỘT lần PC1 | `docs/UY_QUYEN_KHOA.md` §2 |
| Môi trường công cụ phát hành | Claude | venv bất kỳ có `cryptography` (vd. `python -m venv` + `pip install --require-hashes -r release/locks/launcher-lock.txt`) |

Thư mục khoá: `<ổ>:\TimClipPro_KhoaPhatHanh` — NGOÀI repo, ngoài OneDrive/ổ mạng, ngoài thư mục cài đặt/state/feed;
chỉ người dùng + SYSTEM đọc được (`icacls`); Claude không đọc (`.claude/settings.json` chặn cả hai ổ và `khoa_rieng*.pem`).

## 1. Dữ liệu phát hành trong repo (`release/`, byte giữ nguyên nhờ `.gitattributes`)

| File | Là gì | Đổi khi |
|---|---|---|
| `release/trusted_keys.json` | khoá CÔNG KHAI đang tin (verify trước phân phối; trust store của bộ kit cài MỚI) | ghi danh / gỡ khoá |
| `release/locks/requirements-lock.txt` | lock runtime CÓ BĂM của bản phát hành mới nhất (= lock trong gói đã ký; 1.1.1: sha `f955a328…`) | đổi thư viện |
| `release/locks/launcher-lock.txt` | lock CÓ BĂM của môi trường launcher (bộ kit; pin = `TimClipPro/launcher-lock.txt`) | đổi launcher |
| `release/wheels/docopt-0.6.2-py2.py3-none-any.whl` | wheel không có trên PyPI (dựng từ sdist đã đối chiếu; băm có trong lock) | hiếm |
| `release/git-hooks/pre-push`, `release/github/ruleset_*.json` | hook dùng chung; ruleset GitHub đề xuất | đổi quy trình |
| `release/trust/` | yêu cầu / uỷ quyền ghi danh khoá (công khai, có chữ ký) | mỗi lần ghi danh |

Build lại một bản đã phát hành CHỈ từ repo ra gói GIỐNG TỪNG BYTE (1.1.1 từ `dc29b33`: `510f39a6…` — kiểm 14/10).

## 2. Quy trình một bản phát hành — MỘT điểm duyệt

```
Development 8502 → test mục tiêu → review độc lập / PR → gộp fast-forward integration/current
→ (lock có băm) → runtime từ lock + test nhanh & chậm → build tất định → [DUYỆT PHÁT HÀNH X.Y.Z] → người dùng ký
→ kiem-sau-ky → feed → diễn tập sandbox → GitHub Release (nháp → tải lại kiểm → công bố)
→ người dùng cập nhật 8501 (khối PowerShell + CapNhat.bat) → doctor + kiểm dữ liệu
```

**Điểm duyệt duy nhất:** người dùng duyệt «phát hành X.Y.Z từ commit …» SAU khi build + test xanh. Duyệt này phủ: ký,
kiểm, diễn tập, GitHub Release. Claude KHÔNG hỏi lại giữa các bước kỹ thuật đã duyệt; DỪNG trước công bố khi: lỗi
P0/P1, kiểm sau ký không đạt, diễn tập không đạt, bản build khác commit/lock đã duyệt. Gộp PR vào `integration/current`
là một duyệt riêng (thường cùng lúc với duyệt PR).

### Lệnh (thay `<…>`; `PY` = Python có `cryptography`; chạy ở gốc clone; thư mục ra NGOÀI repo)

1. **Tích hợp.** Nhánh `feature/<máy>/<tên>` hoặc `fix/<máy>/<tên>` → PR → review (máy kia nếu trực tuyến, nếu không:
   agent review ngữ cảnh mới + test theo `docs/ai/TEST_MATRIX.md`) → gộp fast-forward (`GIT_WORKFLOW.md` «Gộp»).
2. **Lock.** Thư viện không đổi → dùng `release/locks/requirements-lock.txt`. Đổi → venv sạch theo `requirements.txt`
   đã nghiệm thu → `PY TimClipPro/release_tool.py lock --python <venv>\Scripts\python.exe --out <lock mới>
   --wheelhouse <wheel đã tải>` → PR thay file lock (diff phải đúng phần đã đổi).
3. **Runtime + test.**
   `py -3.12 -m venv <rt>` → `<rt>\Scripts\python -m pip install --require-hashes --no-deps --only-binary=:all:
   --find-links release\wheels -r release\locks\requirements-lock.txt` → pytest riêng (không vào lock) → trong
   `TimClipPro\`: `-m "not slow"` và `-m slow`; báo số thật (đạt/bỏ qua/hỏng).
4. **Build** (đọc object git, không đọc cây làm việc):
   `PY -s -B TimClipPro\release_tool.py build --commit <sha trên integration/current> --phien-ban X.Y.Z
   --lock release\locks\requirements-lock.txt --wheel-kem release\wheels\docopt-0.6.2-py2.py3-none-any.whl
   --out <D:\TimClipPro_PhatHanh\X.Y.Z>` (+ `--tu-dong-an-toan --tuong-thich-nguoc` CHỈ khi có migration đã đánh giá).
5. **Ký** — NGƯỜI DÙNG chạy `KY_BAN.bat` (§7): `release_tool.py sign --dir <…>\stable-X.Y.Z --khoa <khoá riêng>
   --hoi-mat-khau`.
6. **Kiểm sau ký:** `PY -s -B TimClipPro\release_tool.py kiem-sau-ky --dir <…>\stable-X.Y.Z
   --tin-cay release\trusted_keys.json --key-id <key_id máy ký> --commit <sha> --json <bằng chứng>` → KẾT QUẢ ĐẠT.
7. **Feed:** `… release_tool.py feed --dir <…>\stable-X.Y.Z --tin-cay release\trusted_keys.json --out <…>\github`
   → `TimClipPro_Feed_stable-X.Y.Z.zip`, `SHA256SUMS_X.Y.Z.txt`, `KHOI_POWERSHELL_X.Y.Z.txt` (dán nguyên văn vào ghi chú).
8. **Diễn tập** (sandbox, không đụng cài đặt thật):
   * bộ kit: `release_tool.py kit --commit e49340d7d8cf01ec51cea914b3f4509197b5f964 --lock-launcher
     release\locks\launcher-lock.txt --tin-cay release\trusted_keys.json --out <…>\kit.zip` (launcher = bản máy
     vận hành đang chạy; mọi khoá trong `--tin-cay` phải có trong `release/trusted_keys.json` ĐÃ COMMIT ở HEAD — commit
     thay đổi danh sách khoá trước khi dựng kit);
   * bản đang chạy trên máy thật: `gh release download stable-<bản trước> --repo TuongChris/TimClipPro-dev
     --pattern "TimClipPro_Feed_*" --dir <…>` → kiểm SHA256SUMS → giải nén;
   * wheel: `py -3.12 -m pip download --require-hashes --no-deps --only-binary=:all: --platform win_amd64
     --python-version 3.12 --implementation cp --find-links release\wheels -d <wheelhouse> -r <lock>` cho lock bản
     trước, lock mới và `release\locks\launcher-lock.txt`;
   * `PY -I -B TimClipPro\tests\dien_tap_phat_hanh.py <cau_hinh.json>` (mô tả cấu hình ở đầu file;
     `"thu_quay_lai": true`) → `== N/N ca ĐẠT`.
9. **GitHub Release** (repo PUBLIC — mọi asset công khai):
   `gh release create stable-X.Y.Z <zip> <SHA256SUMS> <HUONG_DAN…md> --repo TuongChris/TimClipPro-dev --target <sha>
   --title "TimClipPro X.Y.Z (Stable)" --notes-file <RELEASE_NOTES.md> --draft` → `gh release download` lại vào thư mục
   MỚI, so băm từng byte → `gh release edit stable-X.Y.Z --draft=false --latest` → tải ẩn danh (HTTP 200, cùng băm).
   Tag chỉ sinh lúc công bố; KHÔNG bao giờ xoá/gắn lại tag (ruleset chặn).
10. **Cập nhật 8501** — NGƯỜI DÙNG: khối PowerShell → `SAN SANG` → `C:\TimClipPro\CapNhat.bat` → `[ACTIVE] …` →
    `launcher.py doctor` không ❌ → so số đếm (hồ sơ đích, Outbox, lịch sử, kho) với trước khi cập nhật.

## 3. Khôi phục

| Tình huống | Làm |
|---|---|
| Bản mới hỏng sau kích hoạt | bộ cập nhật tự QUAY VỀ + cách ly; sửa → phát hành `X.Y.Z+1` (không gắn lại tag); bỏ cách ly chỉ khi đã khắc phục nguyên nhân: `launcher.py update bo-cach-ly X.Y.Z` |
| Một máy mất khoá / quên mật khẩu | máy kia phát hành bình thường; máy mất: `tao-khoa` mới → ghi danh bằng uỷ quyền của máy còn khoá (`UY_QUYEN_KHOA.md`) |
| Lộ khoá riêng + mật khẩu | DỪNG phát hành bằng khoá đó; khoá đã ghi danh (PC2) → `uy_quyen_khoa.py hoan-tac --sao-luu launcher\trust_backups\<bản trước ghi danh>` — khoá vào «thu_hoi», không ghi danh lại được (bị chặn nếu bản đang chạy do khoá đó ký — phát hành bản do khoá còn lại ký trước); VÀ gỡ khỏi danh sách repo: `release_tool.py go-khoa-danh-sach --key-id <id> --tin-cay release/trusted_keys.json` (PR) để verify / kiem-sau-ky / feed / bộ kit không tin nó nữa; khoá gốc của bộ kit (PC1) → bootstrap lại bằng kit mới chỉ tin khoá còn an toàn (kế hoạch riêng có duyệt) |
| `trusted_keys.json` hỏng | launcher vẫn mở bản đang chạy, chỉ chặn CẬP NHẬT; chép bản trong `launcher\trust_backups\` (mới nhất) về `launcher\trusted_keys.json`, chạy `launcher.py doctor` |
| Ghi danh bị cắt ngang (mất điện) | chạy lại đúng lệnh: xong, hoặc báo «khoá đã được tin» (file luôn là bản cũ hoặc bản mới hoàn chỉnh) |
| Release nháp sai | xoá bản NHÁP được (chưa có tag); bản đã công bố sai → KHÔNG xoá tag, phát hành bản sửa |
| PC1 và PC2 cùng đẩy | quy ước nhánh theo máy + hook + PR; `integration/current` chỉ fast-forward — đi sau thì cập nhật nhánh việc, review lại |

## 4. Kiểm đã có (14/10/2026, PC1, khoá THỬ đóng vai PC1/PC2)

* Build 1.1.1 từ `dc29b33` CHỈ bằng repo → gói = bản đã công bố (giống từng byte); ký bằng khoá «PC2» thử →
  `kiem-sau-ky` 9/9; feed + khối PowerShell (3 ca thật trong test).
* Diễn tập sandbox: bộ kit `e49340d` + bản 1.1.0 ĐÃ CÔNG BỐ (khoá PC1 thật) → bản do khoá «PC2» ký bị bỏ qua TRƯỚC
  ghi danh → ghi danh bằng uỷ quyền → quay về khi runtime hỏng → cập nhật lên bản do «PC2» ký → khoá lạ bị bỏ qua; dữ
  liệu giữ nguyên byte; release không `__pycache__`. Số liệu: handoff PC1 14/10, `docs/ai/TEST_MATRIX.md`.
* Chưa có: khoá PC2 THẬT (chờ PC2 tạo) và uỷ quyền thật (PC1 ký một lần).

## 7. File `.bat` (CHỈ ASCII, CRLF; người dùng nhấp đúp — mật khẩu gõ trong cửa sổ đó, không hiện, không lưu)

Claude tạo các file này NGOÀI repo (thư mục làm việc của vòng), điền đường dẫn thật, kiểm `exist` trước khi chạy.
Mẫu ký bản (máy nào cũng dùng):
```bat
@echo off
REM Ky ban phat hanh <X.Y.Z> bang khoa cua MAY NAY. Ban tu go mat khau - chu khong hien, khong luu.
set "PY=<python co cryptography>"
set "RT=<clone>\TimClipPro\release_tool.py"
set "BAN=<thu muc>\stable-<X.Y.Z>"
set "KHOA="
set "DEM=0"
for %%f in ("<o>:\TimClipPro_KhoaPhatHanh\khoa_rieng_phat_hanh_*.pem") do (set "KHOA=%%~ff" & set /a DEM+=1)
if not "%DEM%"=="1" (echo Can DUNG MOT file khoa rieng - dang thay %DEM%. Dung lai. & pause & exit /b 1)
if exist "%BAN%\manifest.json.sig" (echo Ban da co chu ky - khong ky lai. & pause & exit /b 1)
"%PY%" -E -s -B "%RT%" sign --dir "%BAN%" --khoa "%KHOA%" --hoi-mat-khau
echo Ma thoat: %errorlevel%   (0 = DA KY)
pause
```
Mẫu tạo khoá + yêu cầu ghi danh (PC2) và ghi danh: prompt thiết lập PC2 (báo cáo bàn giao 14/10) — cùng cách viết.
