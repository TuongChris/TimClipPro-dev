# Trạng thái chung — TimClipPro

Cập nhật 2026-11-02 trên PC2 (máy công ty; chủ dự án chuẩn bị khả năng rời máy này — dựng lại trên máy mới:
`docs/ai/TIEP_TUC_TREN_MAY_MOI.md`; toàn cảnh: `docs/ai/TONG_HOP_DU_AN.md`). File này KHÔNG ghi HEAD mới nhất — HEAD thật
luôn hỏi remote: `git fetch private` rồi `git log --oneline -3 private/integration/current`. Mốc 02/11: `integration/current`
= `dd111e8` (PR #15–#20: audit độc lập 25/10 + đợt P3 + chẩn đoán Sheets + đồng bộ song song D-29); DEV 8502 trên PC2 chạy
đúng `dd111e8`. Kiểm (một dòng) — RỖNG nghĩa là mã chạy thật trên PC2 chưa sau integration:
```bash
git diff --stat pc2-van-hanh private/integration/current -- TimClipPro ':!TimClipPro/tests' ':!*.md'
```

## Hai máy — NGANG QUYỀN (D-23, người dùng quyết 14/10/2026)
| | PC1 (hostname DESKTOP-UIQUSEM) | PC2 |
|---|---|---|
| Vai trò | DỰ PHÒNG: phát triển, review, tích hợp, ký, phát hành khi cần | CHÍNH: phát triển, review, tích hợp; từ 15/10 tối DEV-ONLY — làm việc hằng ngày bằng Development 8502 (D-26), không phát hành Stable để tự dùng |
| Đang chạy thật | `Tool_Quet` = `6dc3f9d` (legacy, `lichsu.db` v2), cổng 8501 — không đổi khi chưa duyệt | **Development 8502** = ứng dụng làm việc chính, dữ liệu THẬT (`C:\Dev\TimClipPro_DevState\data`), mã = worktree vận hành `C:\Dev\TimClipPro_VanHanh` (chỉ fast-forward theo `integration/current`). Stable 1.1.1 (managed, `C:\TimClipPro*`, 8501) GIỮ NGUYÊN chỉ để dự phòng — không cập nhật, không xoá |
| Development | worktree `D:\TimClipPro_Dev\<tên>`; không chạy server | vận hành: launcher `TimClipPro_DEV.bat` ngoài Git (127.0.0.1:8502); phát triển: clone `C:\Dev\Tool_Quet` + worktree việc riêng — test chỉ dữ liệu synthetic |
| Khoá ký Stable | `8aa5baa6c8f225f9` (`D:\TimClipPro_KhoaPhatHanh`, ngoài repo/OneDrive) — được tin | `d02702dd741c3e4f` (`C:\TimClipPro_KhoaPhatHanh`, chỉ tài khoản chủ máy + SYSTEM) — được tin; ghi danh vào Stable PC2 15/10 theo uỷ quyền `a893c182…` của `8aa5…` |
| GitHub | `gh` (chủ repo) + SSH | Deploy Key quyền ghi + `gh` đăng nhập chủ repo (15/10) + hook `pre-push` dùng chung |
| Dữ liệu | của riêng PC1 | PC2 tự xây; KHÔNG chép dữ liệu giữa hai máy |

Cơ chế hai khoá: trust store của cài đặt managed đã tin NHIỀU khoá; PC2 thêm khoá của mình bằng uỷ quyền ký bởi khoá
đang tin (`TimClipPro/docs/UY_QUYEN_KHOA.md`). ĐÃ XONG 15/10: PC1 ký uỷ quyền MỘT lần (`release/trust/uy_quyen_PC2_…`),
Stable PC2 tin 2 khoá, `release/trusted_keys.json` 2 khoá. Từ nay mỗi máy phát hành độc lập, PC1 KHÔNG còn bắt buộc
(`TimClipPro/docs/PHAT_HANH_HAI_MAY.md`).

## Stable đã phát hành (GitHub Release, repo PUBLIC)
| Bản | Commit | Ký bởi | Ghi chú |
|---|---|---|---|
| 1.0.0 | `e49340d` | `8aa5baa6c8f225f9` | bộ cài one-click (09/10); bộ kit launcher = bản PC2 đang chạy |
| 1.1.0 | `ec1ff71` | `8aa5baa6c8f225f9` | Marathon; asset `TimClipPro_Feed_stable-1.1.0.zip` `b00c315f…` |
| 1.1.1 | `dc29b33` | `8aa5baa6c8f225f9` | CookieFix (Node.js ≥ 22 + yt-dlp-ejs), sửa F1/F3; runtime `py312-f955a32807a9`; asset `2f813e87…` |
| 1.1.2 | `e74c923` | `d02702dd741c3e4f` | tiến độ đồng bộ kênh + nhớ client + thanh bên cookie (PR #9, #12); cùng runtime; asset `756061b0…`; KHÔNG cài lên Stable PC2 (D-26) |

Lock có băm + wheel docopt + khoá công khai đang tin (`8aa5…` PC1 + `d027…` PC2) nằm trong repo (`release/`); build lại
1.1.1 chỉ từ repo ra gói giống từng byte (`510f39a6…`) — kiểm trên PC1 (14/10) và PC2 (15/10).

## Remote
- `private` = GitHub `TuongChris/TimClipPro-dev` — **PUBLIC** (từ 13/10, chủ ý). Nhánh `integration/current`, nhánh việc
  `feature|fix/pc1|pc2/*`, tag `stable-1.1.0`, `stable-1.1.1`, `stable-1.1.2` (do GitHub Release tạo). Chi tiết `docs/ai/GIT_WORKFLOW.md`.
- `origin` (chỉ PC1) = `TuongChris/Tool_Quet` — PUBLIC, chỉ fetch (updater cũ); push bị chặn.
- Ruleset GitHub (chặn force-push/xoá `integration/current`, tag `stable-*` bất biến): ĐỀ XUẤT, chưa bật (cần chủ repo).

## Cổng và preview
- 8501 = Stable (PC2 — dự phòng, `launcher.py`, `127.0.0.1`) và production legacy (PC1, `ChayTool.bat`). Development
  CHỈ 8502 — trên PC2 đó là ứng dụng làm việc chính (D-26).
- `.claude/launch.json` chỉ GẮN vào 8502 (không tự khởi động); production PC1 và worktree cũ còn bản cũ tự chạy 8501.

## Đã kiểm chứng — và chưa
- PC1 có bằng chứng: 1.1.1 kiểm sau ký 10/10, diễn tập cập nhật bằng khoá thật 29/29 + 21/21 + gói tải từ GitHub 23/23;
  cơ chế hai khoá: test `test_uy_quyen_khoa.py` + diễn tập sandbox 19/19 (khoá THỬ đóng vai PC1/PC2, launcher `e49340d`).
- PC2 có bằng chứng (15/10, ngoài Git trên PC2 `2026-10-15_release_authority`; tóm tắt `docs/ai/handoff/PC2.md`): review
  độc lập PR #6 (nhanh 2708/2/0, chậm 19/19, đột biến 19/20 → M17 có test); ghi danh khoá PC2 vào Stable 8/8 (State không
  đổi); dry-run PHÁT HÀNH ĐỘC LẬP khi PC1 tắt — build trùng byte, ký khoá PC2, `kiem-sau-ky` 10/10, diễn tập sandbox 14/14
  (bản PC1 ký + bản PC2 ký cùng được nhận, rollback runtime hỏng, khoá lạ bị bỏ qua, không `__pycache__`); thu hồi + rollback
  74/74. Bản ký thử không công bố; Stable 1.1.1 không cập nhật.
- CHƯA: ruleset GitHub; tái audit độc lập `e49340d`; pilot Sheets/YouTube thật có kiểm soát trên PC2 (khi người dùng duyệt).

## Việc đang mở (theo thứ tự)
1. Người dùng: nghiệm thu đồng bộ + quét song song (D-29) trên DEV 8502; nghiệm thu DEV đợt 2 audit.
2. Người dùng quyết: P-6, P-7 (`DECISIONS.md`), B-13, F-16, 3 ghép tuỳ chọn của P0; có phát hành Stable 1.1.3 không; có nới
   giới hạn mốc 25,4 phút (`--maxtimebits 16`, `TimClipPro/docs/FINGERPRINT_RECOVERY_ARCHITECTURE.md` §6.1) trước lần dựng kho
   tới không.
3. PC1: review PR #15–#20 (đã vào `integration/current`, chưa có PC1 review); đề xuất E-1 (`.claude/settings.json`).
4. Bật ruleset GitHub (`release/github/`, một lệnh, chủ repo duyệt).
5. PC1 production lên bản managed: quyết định riêng (lược đồ `lichsu.db` v2 → v4; sao lưu trước).
6. Rời máy công ty: thu hồi Deploy Key «PC2 PC_Office», `gh auth logout`, khoá Google cũ, khoá ký PC2 (mục 5 của
   `TIEP_TUC_TREN_MAY_MOI.md`).
