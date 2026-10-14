# Quyết định — TimClipPro

Mỗi mục: quyết định · vì sao · bằng chứng (commit / tài liệu). Mới nhất ở trên. Đổi một quyết định = thêm mục MỚI ghi
rõ «thay D-xx», không sửa lịch sử. Đường dẫn `docs/…` không có tiền tố là `TimClipPro/docs/…`.

## Đang chờ người dùng quyết
- **P-2 PC1 production lên bản managed** — lược đồ `lichsu.db` v2 → v4; cần sao lưu + duyệt riêng.
- **P-4 Lịch sử repo public** — có dữ liệu cần xử lý (chi tiết ngoài Git); đóng repo public hay viết lại lịch sử đều
  cần duyệt (force-push đang bị cấm).
- **P-5 Bật ruleset GitHub** (`release/github/*.json`, D-25) — một lệnh `gh api`, chủ repo duyệt.

## D-25 Hook `pre-push` dùng chung + ruleset GitHub đề xuất (2026-10-14) — thay hook «chỉ fix/pc2» của D-18
Quyết định: một hook cho CẢ HAI máy (`release/git-hooks/pre-push`): cho `feature|fix/pc1|pc2/*`; `integration/current`
CHỈ fast-forward tới ĐÚNG đầu một nhánh việc đã đẩy (đã có PR); chặn tag (tag `stable-*` chỉ do `gh release create` sinh
khi công bố), xoá, force-push, nhánh lạ, tạo mới integration. Máy chủ: ruleset chặn xoá + force-push `integration/current`
và tag `stable-*` bất biến — KHÔNG «require pull request» (chặn gộp fast-forward bằng push; nút Merge đổi SHA).
Vì sao: hai máy ngang quyền thì quy ước tên nhánh không đủ; hook chặn nhầm cục bộ, ruleset chặn ở máy chủ cho mọi khoá.
Bằng chứng: `tests/test_git_hook_pre_push.py` (repo tạm, 9 ca); ruleset chưa bật (P-5).

## D-24 Lock có băm + wheel docopt + khoá công khai vào repo (2026-10-14) — giải quyết P-3
Quyết định: `release/locks/requirements-lock.txt` (= lock trong gói 1.1.1 đã ký, sha `f955a328…`),
`release/locks/launcher-lock.txt` (= lock của bộ kit 1.0.0), `release/wheels/docopt-0.6.2-py2.py3-none-any.whl` (băm có
trong lock), `release/trusted_keys.json` (khoá công khai đang tin); `.gitattributes` giữ nguyên byte (`release/** -text`).
Vì sao: máy nào cũng phải build được bản Stable mà không cần thư mục phát hành của máy kia.
Bằng chứng: build lại 1.1.1 từ `dc29b33` CHỈ bằng repo → gói giống từng byte bản đã công bố (`510f39a6…`), 14/10 PC1.

## D-23 PC1 và PC2 NGANG QUYỀN phát hành; mỗi máy một khoá ký (2026-10-14) — thay D-13 (khoá chỉ ở PC1), D-10 (phát hành chỉ ở PC1)
Quyết định (người dùng): PC2 = máy phát triển + phát hành CHÍNH, PC1 = DỰ PHÒNG; cả hai được phát triển, review, tích
hợp, build, ký, phát hành. Khoá riêng không rời máy của nó; PC2 tạo khoá trên PC2. Trust store của cài đặt managed (đã
tin nhiều khoá) được THÊM khoá PC2 bằng uỷ quyền có chữ ký của khoá đang tin, ràng buộc khoá / cài đặt (băm định danh) /
trust store (băm byte) / hạn — `uy_quyen_khoa.py`, `release_tool.py ky-uy-quyen`. Không đổi launcher, không bootstrap
lại, không bản phát hành mới. Sau lần ký uỷ quyền đó PC1 KHÔNG còn bắt buộc cho việc phát hành.
Vì sao: một máy giữ khoá duy nhất = điểm hỏng đơn; launcher hiện có đã đủ khả năng tin nhiều khoá.
Bằng chứng: `TimClipPro/docs/UY_QUYEN_KHOA.md` §1 (Phase A), `tests/test_uy_quyen_khoa.py`, diễn tập sandbox 19/19 (khoá
THỬ đóng vai hai máy, launcher `e49340d`, bootstrap + `CapNhat.bat` thật), 14/10 PC1.

## D-22 Repo `TimClipPro-dev` PUBLIC (người dùng, 13/10/2026; xác nhận 14/10) — thay một phần D-16
Quyết định của người dùng, không phải sự cố. Hệ quả: mọi push/PR/release là công khai → quét bí mật trước MỖI lần đẩy;
asset GitHub Release tải được không cần đăng nhập. Tên remote `private` giữ nguyên.

## D-21 Stable phân phối bằng GitHub Release (2026-10-13) — thay D-14 (ZIP qua RustDesk)
Quyết định: asset `TimClipPro_Feed_stable-X.Y.Z.zip` (4 file đã ký, STORED, tất định) + `SHA256SUMS_X.Y.Z.txt` + khối
PowerShell trong ghi chú (kiểm băm → giải nén → «SAN SANG») → `CapNhat.bat`. Không USB/RustDesk.
Bằng chứng: Release `stable-1.1.0` (`b00c315f…`), `stable-1.1.1` (`2f813e87…`); diễn tập bằng đúng gói tải về 23/23.

## D-20 Stable 1.0.0 cài lên PC2 trước tái audit (người dùng, báo 09/10) — thay một phần D-13
Sự kiện/quyết định của người dùng: Stable 1.0.0 (từ e49340d) đã cài và chạy trên PC2, cổng 8501 — sớm hơn điều kiện
«GIỮ ở PC1 tới khi e49340d được tái audit độc lập» của D-13. Hệ quả: C7 chưa đóng về kiểm chứng (cần kết quả bộ cài +
health check do NGƯỜI DÙNG lấy — Claude không đụng `C:\TimClipPro*`); tái audit độc lập e49340d vẫn cần; bản Stable sau
vẫn theo quy trình ký trên PC1.
Bằng chứng: lời người dùng; handoff PC2 (09/10). PC1 chưa có log cài đặt.

## D-19 Preview an toàn: `.claude/launch.json` chỉ GẮN vào Development 8502 (2026-10-10) — thay cấu hình 20/08
Quyết định: bỏ cấu hình tự khởi động `streamlit … --server.port=8501` (có từ `b776082`, 20/08); thay bằng một cấu hình
chỉ có `url` `http://localhost:8502` + `port` 8502 + `autoPort: false`, và `autoVerify: false` (Claude không tự mở preview
sau khi sửa). Development chạy bằng launcher RIÊNG máy, ngoài Git — yêu cầu (PC2 tự kiểm, PC1 chưa xem launcher đó):
danh sách duy nhất ở `docs/ai/handoff/PC2.md` «Máy» (cổng 8502 ghi rõ, data/output thử, không cookie/khoá thật, không
`.bat` cũ trong clone). 8501 dành cho Stable (`launcher.py` `CONG_STREAMLIT`, `127.0.0.1`) và production legacy PC1
(`ChayTool.bat`).
Vì sao: cấu hình cũ trùng cổng Stable PC2/production PC1; tài liệu Claude Code ghi cấu hình chỉ `url` thì «gắn vào server
đang chạy thay vì khởi động»; `env` trong file sẽ commit chung nên đường dẫn riêng máy không đặt ở đó được.
Giới hạn: hành vi khi 8502 không có gì chạy chưa được ghi trong tài liệu; preview trên PC2 CHƯA nghiệm thu; production
PC1 (`Tool_Quet` @ `6dc3f9d`) và các worktree cũ VẪN mang bản cũ tự khởi động 8501 (không sửa production) — không mở
preview ở đó; Claude có thể tự tạo lại `.claude/launch.json` khi được nhờ xem trước → giữ quy tắc trong `CLAUDE.md`.
Bằng chứng: kiểm tĩnh K10 (không 8501, không lệnh khởi động, có `url`, `autoVerify` false) vòng 10/10 trên PC1;
https://code.claude.com/docs/en/desktop#configure-preview-servers.

## D-18 PC2 giai đoạn 2 và cách gộp PR (2026-10-09/10) — bổ sung D-17
Quyết định: người dùng bật quyền GHI cho Deploy Key của PC2 (09/10; quyền ở mức cả repo, tên khoá vẫn ghi «read-only»).
PC2 chỉ đẩy `fix/pc2/*` khi được duyệt; PC1 review rồi gộp FAST-FORWARD bằng `update-ref` có kiểm SHA đã review (giữ SHA,
GitHub tự đánh dấu merged); không bấm nút Merge nào trên web. Khuyến nghị hook `pre-push` cục bộ trên PC2 (chặn
`integration/current`, tag, xoá, force-push) vì quy ước tên nhánh không phải giới hạn kỹ thuật.
Vì sao: repo private gói miễn phí (gói tài khoản chưa kiểm) không có bảo vệ nhánh; giữ SHA để handoff/commit của PC2 trỏ
đúng.
Bằng chứng: PR #1 (`b627af0`) gộp 10/10 sau review PC1; hook trích từ `GIT_WORKFLOW.md` thử 11/11 tình huống trên repo giả
(kể cả 3 lệnh thử ghi cho PC2) — vòng 10/10 trên PC1.

## D-17 PC2 truy cập GitHub theo hai giai đoạn; tài liệu không ghi cứng HEAD (2026-10-09) — bổ sung D-16
Quyết định (người dùng): giai đoạn 1 — Deploy Key CHỈ ĐỌC cho `TimClipPro-dev` (KHÔNG «Allow write access»), clone tại
`C:\Dev\Tool_Quet`; giai đoạn 2 — quyền ghi `fix/pc2/*` + Pull Request, thiết lập riêng sau khi PC2 clone, kiểm shared
context và người dùng duyệt. Tài liệu không ghi HEAD «mới nhất»; mỗi phiên hỏi remote (`git fetch private`).
Vì sao: PC2 chạy dữ liệu thật — quyền tối thiểu cho tới khi quy trình PC2 được kiểm; SHA ghi trong tài liệu cũ đi ngay
sau lần đẩy kế tiếp.
Bằng chứng: `docs/ai/GIT_WORKFLOW.md` (mục «PC2 — giai đoạn 1/2»), `handoff/PC2.md`, `SESSION_START.md`.

## D-16 Remote PRIVATE cho PC1/PC2 (2026-10-09) — giải quyết P-1
Quyết định: repo MỚI `TuongChris/TimClipPro-dev` (private, không fork); chỉ đẩy `integration/current` (lần đầu
`9b763be`, 90 commit, giữ nguyên lịch sử để không cắt truy vết `e49340d` trong manifest Stable 1.0.0); không đẩy tag
hay nhánh cũ. PC1: remote `private`, `remote.pushDefault=private`, `push.default=upstream`; push vào `origin` (PUBLIC)
bị chặn bằng pushurl giả, fetch vẫn chạy. PC2: clone với `--origin private`, khoá deploy chỉ cho repo này.
Vì sao: hai máy chia sẻ mã, tài liệu, handoff qua Git mà không đụng repo public.
Bằng chứng: quét toàn bộ lịch sử sẽ đẩy (843 blob, 90 commit, đối chứng dương 39/39) → 0 phát hiện nhạy cảm mới, chỉ
còn các mục đã báo người dùng và đã public sẵn (chi tiết ngoài Git, bằng chứng vòng 09/10 trên PC1); GitHub báo
`private=true`, ref duy nhất `refs/heads/integration/current` = `9b763be`, 0 tag; thử push nhầm `origin` → bị chặn.

## D-15 Ngữ cảnh chung qua Git + sơ đồ nhánh (2026-10-09)
Quyết định: `CLAUDE.md` gốc ngắn + `docs/ai/` + `.claude/rules/` theo vùng; `TimClipPro/CLAUDE.md` rút từ 782 xuống
dưới 200 dòng, phần dài chuyển nguyên văn sang `docs/LOI_DA_GAP.md`, rules, chỉ mục và file này. Nhánh
`integration/current` (= e49340d), `feature/pc1/*`, `fix/pc2/*`. Ghi chú riêng máy ở `CLAUDE.local.md` (gitignore).
Vì sao: PC1/PC2 hiểu dự án mà không đọc lại toàn bộ mã mỗi phiên; Claude Code khuyên CLAUDE.md < 200 dòng.
Bằng chứng: nhánh `feature/pc1/ai-shared-context`; inventory + kiểm chứng trong bằng chứng vòng 09/10 trên PC1.

## D-14 Bộ cài one-click cho PC2 (2026-10-09)
Quyết định: một ZIP chuyển qua RustDesk; `.bat` kiểm checksum, chữ ký, khoá công khai, lock TRƯỚC khi cài; cài offline
từ wheelhouse; dừng nếu thư mục đích đã có; hỏi trước khi tạo lối tắt. Mặc định `C:\TimClipPro`, `C:\TimClipPro_State`.
Bằng chứng: ZIP `b0847ea7…caa8`, thử 13/13 (thư mục sạch; máy không có Windows Sandbox).

## D-13 Stable 1.0.0 thật từ e49340d, chưa giao (2026-10-08)
Quyết định: khoá Ed25519 thật chỉ ở PC1 (ngoài repo/OneDrive), mã hoá bằng mật khẩu người dùng gõ; bản đã ký GIỮ ở PC1
tới khi e49340d được tái audit độc lập; PC2 tự xây dữ liệu, KHÔNG chép từ PC1. `KEY_BACKUP = DEFERRED_BY_USER`.
Rủi ro đã chấp nhận: mất khoá = bootstrap lại PC2 bằng khoá mới (launcher chưa có đường xoay khoá).
Bằng chứng: key_id `8aa5baa6c8f225f9`; manifest `e19a943b…`; cài mới thử 29/29.

## D-12 Sửa theo tái audit 78ba20c (2026-10-08)
Quyết định: outbox đọc/ghi tab theo MÃ `sheetId`, không theo tên A1 (MR-R2-P1-01); lưu mã tab của TỪNG lần phát cùng
giao dịch SENDING, lược đồ v4; việc cũ phát theo tên không bao giờ gửi lại (MR-R2-P2-01).
Bằng chứng: `8e7dc24`, `c981450`, `6461327`, `e49340d`; `docs/MANAGED_RUNTIME_DESIGN.md` §5; đột biến 123/123.

## D-11 Sửa theo audit độc lập f4d3cb7 (2026-10-08)
Quyết định: thư mục cài đặt và state root tách biệt, chốt bố cục trước mọi lần updater xoá (MR-P1-01); chốt mã tab
trong cùng giao dịch SENDING, trước request ghi đầu tiên (MR-P1-02).
Bằng chứng: `022349f`, `7d69380`, `78ba20c`; `docs/MANAGED_UPDATE.md`.

## D-10 Managed Runtime cho PC2 (2026-10-07…08)
Quyết định: state root tách khỏi cài đặt; outbox Sheets lưu bền trong `lichsu.db` (một người gửi, đích ghim theo
lượt); cổng bảo trì; Stable có chữ ký Ed25519 + health check + quay lại; launcher nằm ngoài release; phát hành chỉ
ở PC1 bằng `release_tool.py`. Nguồn bản mới đã thử: feed thư mục (`NguonThuMuc`); `NguonGitHub` có trong mã, chưa dùng.
Bằng chứng: `e341a1c` (M1) … `f4d3cb7` (M5); `docs/MANAGED_RUNTIME_DESIGN.md`, `docs/MANAGED_UPDATE.md`.

## D-9 Báo cáo V2 (2026-10-04…05) — PC1 production chạy bản này
Quyết định: chính sách báo cáo ghim ở ranh giới job; ảnh chụp lỗi chặn xuất, không lùi về luật cũ; gửi Sheets nghiêm
ngặt. Tái audit độc lập 05/10 (hồ sơ ngoài repo): PASS FOR CONTROLLED ROLLOUT PREPARATION, còn 2 mục P3.
Người dùng duyệt chuyển PC1 production sang `6dc3f9d` ngày 05/10 (có sao lưu trước).
Bằng chứng: `35c7fc1` … `6dc3f9d`; `docs/REPORT_POLICY_V2.md`, `docs/REPORT_POLICY_V2_VALIDATION.md`.

## D-8 Bỏ link Google Sheet ghi cứng khỏi `GiamSat.bat` (2026-10-04)
Quyết định: đọc `SHEET_LINK` hoặc `data\giam_sat_sheet.txt` (ngoài Git). Bằng chứng: `86e6bff`.

## D-7 Không nâng trần `max_matches` khi chưa có ca dương thật (2026-10-04)
Vì sao: đo trên lô thật, trần 200 chỉ cắt dòng nhạc hiệu; nâng trần không lộ ứng viên đạt chuẩn nào.
Bằng chứng: `7ee527a`; `docs/COMMON_ORIGINAL_SATURATION_ANALYSIS.md`.

## D-6 Truy cập YouTube có kiểm soát (2026-10-03)
Quyết định: một `PhienYouTube` mỗi lượt, phân loại lỗi tập trung, thử lại hữu hạn, cầu dao; lỗi truy cập không bao giờ
là âm tính. Bằng chứng: `f95345c` … `fe07985`; `docs/YOUTUBE_ACCESS_RELIABILITY.md`.

## D-5 Chế độ «Một video gốc chung cho cả lô» V1 (2026-10-03)
Quyết định: ứng viên lấy trước Top-N (`ung_vien_dat`); mục tiêu quét truyền tường minh; định danh (kho, basename);
V1 không ghi `lichsu.db`, không đẩy Sheets. Bằng chứng: `3218aff`, `d67ce31`; `docs/COMMON_ORIGINAL_DESIGN.md`.

## D-4 Hardening sau audit kiến trúc 4b7e5bd (2026-10-02)
Bằng chứng: `8f0558f` (16 phát hiện TCP-01…TCP-16), `f87cc85`; `docs/HARDENING_FIX_MATRIX.md`.

## D-3 Quy trình làm việc với AI
Hiện hành: người dùng dán brief (thường do GPT soạn) → Claude lập kế hoạch, làm TDD, kiểm chứng, báo cáo tiếng Việt kèm
bằng chứng; commit/push chỉ khi brief/người dùng cho phép. Quy trình CŨ «Claude lập kế hoạch → Codex viết code» vẫn
giữ nguyên văn cuối `TimClipPro/CLAUDE.md`, chỉ dùng khi được yêu cầu rõ.

## D-2 Mọi tuỳ chọn yt-dlp đi qua `ytdlp_chung` (2026-08-18)
Vì sao: ba lần trong một ngày cùng một lỗi chỉ được vá ở một đường tải. Bằng chứng: `docs/LOI_DA_GAP.md` mục 6, 6b, 6c, 9.

## D-1 Hướng phát triển và PyInstaller — chuyển nguyên văn từ `TimClipPro/CLAUDE.md` (e49340d)

## Hướng phát triển đang cân nhắc

1. Tự động quét định kỳ (Task Scheduler) → đẩy Sheets → gửi email cảnh báo.
2. Sinh sẵn hồ sơ khiếu nại bản quyền (điền form YouTube) từ dòng kết quả.
3. Nhánh so khớp hình ảnh cho trường hợp video bị thay tiếng.
4. ~~Đóng gói `.exe` bằng PyInstaller~~ — **đã khảo sát 18/08/2026 và BÁC BỎ.**
   Ba lý do cứng: (a) Streamlit bắt buộc đọc `app.py` dưới dạng văn bản rồi mới
   compile (`runtime/scriptrunner/script_cache.py`), nên bản .exe vẫn phải kèm .py;
   (b) `engine.py:1589` và `:1601` chạy `sys.executable` lên file .py — đóng băng là
   hỏng toàn bộ tạo vân tay và khớp; (c) mục tiêu thật là TỰ CẬP NHẬT, mà .exe làm
   việc đó tệ hơn hẳn: mỗi lần cập nhật phải chuyển ~700 MB thay vì vài KB, và
   Windows khoá file .exe đang chạy nên không tự ghi đè được.
   Đã thay bằng `cap_nhat.py` — cập nhật theo tag git. Xem `docs/TU_CAP_NHAT.md`.
