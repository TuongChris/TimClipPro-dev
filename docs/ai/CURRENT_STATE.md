# Trạng thái chung — TimClipPro

Cập nhật 2026-10-14 trên PC1. File này KHÔNG ghi HEAD mới nhất — HEAD thật luôn hỏi remote: `git fetch private` rồi
`git log --oneline -3 private/integration/current`. Mốc mã chạy thật: Stable **1.1.1** = `dc29b33`. Kiểm (một dòng) —
RỖNG nghĩa là mã chạy thật chưa đổi sau 1.1.1; không rỗng → đọc các commit đó + handoff mới nhất trước khi tin file này:
```bash
git diff --stat dc29b33 private/integration/current -- TimClipPro ':!TimClipPro/tests' ':!*.md'
```

## Hai máy — NGANG QUYỀN (D-23, người dùng quyết 14/10/2026)
| | PC1 (hostname DESKTOP-UIQUSEM) | PC2 |
|---|---|---|
| Vai trò | DỰ PHÒNG: phát triển, review, tích hợp, ký, phát hành khi cần | CHÍNH: phát triển, review, tích hợp, ký, phát hành; vận hành Stable |
| Đang chạy thật | `Tool_Quet` = `6dc3f9d` (legacy, `lichsu.db` v2), cổng 8501 — không đổi khi chưa duyệt | Stable 1.1.1 (managed, `C:\TimClipPro*`), cổng 8501 — người dùng báo đã cập nhật 14/10 |
| Development | worktree `D:\TimClipPro_Dev\<tên>`; không chạy server | clone `C:\Dev\Tool_Quet`, cổng 8502 bằng launcher riêng ngoài Git |
| Khoá ký Stable | `8aa5baa6c8f225f9` (`D:\TimClipPro_KhoaPhatHanh`, ngoài repo/OneDrive) — được tin | khoá riêng của PC2: CHƯA tạo / CHƯA ghi danh (chờ thiết lập — handoff PC2) |
| GitHub | `gh` (chủ repo) + SSH | Deploy Key quyền ghi + `gh auth login --web` (chưa làm) |
| Dữ liệu | của riêng PC1 | PC2 tự xây; KHÔNG chép dữ liệu giữa hai máy |

Cơ chế hai khoá: trust store của cài đặt managed đã tin NHIỀU khoá; PC2 thêm khoá của mình bằng uỷ quyền ký bởi khoá
đang tin (`TimClipPro/docs/UY_QUYEN_KHOA.md`) — PC1 chỉ cần ký MỘT lần uỷ quyền đó. Sau đó mỗi máy phát hành độc lập
(`TimClipPro/docs/PHAT_HANH_HAI_MAY.md`).

## Stable đã phát hành (GitHub Release, repo PUBLIC)
| Bản | Commit | Ký bởi | Ghi chú |
|---|---|---|---|
| 1.0.0 | `e49340d` | `8aa5baa6c8f225f9` | bộ cài one-click (09/10); bộ kit launcher = bản PC2 đang chạy |
| 1.1.0 | `ec1ff71` | `8aa5baa6c8f225f9` | Marathon; asset `TimClipPro_Feed_stable-1.1.0.zip` `b00c315f…` |
| 1.1.1 | `dc29b33` | `8aa5baa6c8f225f9` | CookieFix (Node.js ≥ 22 + yt-dlp-ejs), sửa F1/F3; runtime `py312-f955a32807a9`; asset `2f813e87…` |

Lock có băm + wheel docopt + khoá công khai đang tin nằm trong repo (`release/`); build lại 1.1.1 chỉ từ repo ra gói giống
từng byte (`510f39a6…`).

## Remote
- `private` = GitHub `TuongChris/TimClipPro-dev` — **PUBLIC** (từ 13/10, chủ ý). Nhánh `integration/current`, nhánh việc
  `feature|fix/pc1|pc2/*`, tag `stable-1.1.0`, `stable-1.1.1` (do GitHub Release tạo). Chi tiết `docs/ai/GIT_WORKFLOW.md`.
- `origin` (chỉ PC1) = `TuongChris/Tool_Quet` — PUBLIC, chỉ fetch (updater cũ); push bị chặn.
- Ruleset GitHub (chặn force-push/xoá `integration/current`, tag `stable-*` bất biến): ĐỀ XUẤT, chưa bật (cần chủ repo).

## Cổng và preview
- 8501 = Stable (PC2, `launcher.py`, `127.0.0.1`) và production legacy (PC1, `ChayTool.bat`). Development CHỈ 8502.
- `.claude/launch.json` chỉ GẮN vào 8502 (không tự khởi động); production PC1 và worktree cũ còn bản cũ tự chạy 8501.

## Đã kiểm chứng — và chưa
- PC1 có bằng chứng: 1.1.1 kiểm sau ký 10/10, diễn tập cập nhật bằng khoá thật 29/29 + 21/21 + gói tải từ GitHub 23/23;
  cơ chế hai khoá: test `test_uy_quyen_khoa.py` + diễn tập sandbox 19/19 (khoá THỬ đóng vai PC1/PC2, launcher `e49340d`).
- CHỈ có lời người dùng: PC2 đã cập nhật lên 1.1.1 và chạy 8501.
- CHƯA: khoá PC2 thật + ghi danh thật; ruleset GitHub; tái audit độc lập `e49340d`; pilot Sheets/YouTube thật có kiểm
  soát trên PC2 (chỉ khi người dùng duyệt).

## Việc đang mở (theo thứ tự)
1. Thiết lập PC2 phát hành độc lập: `gh auth login --web`, hook, khoá PC2 + yêu cầu ghi danh → PC1 ký uỷ quyền (LẦN CUỐI
   PC1 bắt buộc) → PC2 ghi danh, kiểm, dry-run phát hành, gộp PR (`docs/ai/handoff/PC2.md`).
2. Bật ruleset GitHub (một lệnh, chủ repo duyệt).
3. Bản sau: CookieFix F2, F4–F8; Marathon F1/F2 (ghi trong release notes 1.1.1).
4. Sao lưu khoá ký mỗi máy (người dùng quyết) — với hai khoá cùng được tin, mất một khoá không còn chặn phát hành.
5. PC1 production lên bản managed: quyết định riêng (lược đồ `lichsu.db` v2 → v4; sao lưu trước).
