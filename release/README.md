# release/ — dữ liệu phát hành CÔNG KHAI (repo PUBLIC)

Byte của mọi file ở đây phải giữ NGUYÊN (`.gitattributes`: `release/** -text` — không đổi xuống dòng khi checkout).
Không bao giờ đặt khoá riêng, mật khẩu, định danh cài đặt, đường dẫn riêng máy vào đây.

| Đường dẫn | Là gì | Sửa bằng |
|---|---|---|
| `trusted_keys.json` | khoá CÔNG KHAI đang được tin (verify trước phân phối; trust store của bộ kit cài mới) | `release_tool.py them-khoa-danh-sach` (theo uỷ quyền đã ký) — không sửa tay |
| `locks/requirements-lock.txt` | lock runtime CÓ BĂM của bản Stable mới nhất | `release_tool.py lock` + PR |
| `locks/launcher-lock.txt` | lock CÓ BĂM môi trường launcher (bộ kit) | khi đổi `TimClipPro/launcher-lock.txt` |
| `wheels/docopt-0.6.2-py2.py3-none-any.whl` | wheel không có trên PyPI (băm có trong lock) | hiếm |
| `git-hooks/pre-push` | hook dùng chung PC1/PC2 | PR |
| `github/ruleset_*.json` | ruleset GitHub đề xuất (bật bằng `gh api`, chủ repo duyệt) | PR |
| `trust/` | yêu cầu (`yeu_cau_*.json`) / uỷ quyền (`uy_quyen_*.json`) ghi danh khoá — có chữ ký | `uy_quyen_khoa.py yeu-cau`, `release_tool.py ky-uy-quyen` |

Quy trình: `TimClipPro/docs/PHAT_HANH_HAI_MAY.md`. Ghi danh khoá: `TimClipPro/docs/UY_QUYEN_KHOA.md`.
