---
paths:
  - "TimClipPro/managed_update.py"
  - "TimClipPro/launcher.py"
  - "TimClipPro/bootstrap.py"
  - "TimClipPro/release_tool.py"
  - "TimClipPro/runtime_paths.py"
  - "TimClipPro/maintenance_gate.py"
  - "TimClipPro/health_check.py"
  - "TimClipPro/ui_cap_nhat.py"
  - "TimClipPro/cap_nhat.py"
  - "TimClipPro/CapNhat.bat"
  - "TimClipPro/dong_goi.py"
  - "TimClipPro/dong_goi_may_chay.py"
  - "TimClipPro/thiet_lap_may_phu.py"
  - "TimClipPro/requirements*.txt"
  - "TimClipPro/launcher-lock.txt"
  - "TimClipPro/constraints.txt"
  - "TimClipPro/tests/cap_nhat_gia.py"
  - "TimClipPro/tests/test_managed_update*.py"
  - "TimClipPro/tests/test_launcher*.py"
  - "TimClipPro/tests/test_bootstrap*.py"
  - "TimClipPro/tests/test_release_tool*.py"
  - "TimClipPro/uy_quyen_khoa.py"
  - "TimClipPro/tests/test_uy_quyen_khoa.py"
  - "TimClipPro/tests/dien_tap_phat_hanh.py"
  - "TimClipPro/tests/test_git_hook_pre_push.py"
  - "release/**"
  - "TimClipPro/tests/test_runtime_*.py"
  - "TimClipPro/tests/test_bo_cuc_thu_muc.py"
  - "TimClipPro/tests/test_hai_may_gia_lap.py"
  - "TimClipPro/tests/test_maintenance_gate.py"
  - "TimClipPro/tests/test_cong_bao_tri_tich_hop.py"
  - "TimClipPro/tests/test_health_check.py"
  - "TimClipPro/tests/test_cap_nhat*.py"
  - "TimClipPro/tests/test_packaging.py"
  - "TimClipPro/tests/test_dong_goi_*.py"
---
# Quy tắc vùng UPDATER — cài đặt managed, cập nhật Stable, phát hành

Tự nạp khi đọc/sửa file khớp `paths` ở trên. Bất biến chung vẫn ở `TimClipPro/CLAUDE.md`.

## An toàn — luôn đúng
- Mỗi máy (PC1, PC2) một khoá ký phát hành RIÊNG, ngoài repo và ngoài OneDrive (`<ổ>:\TimClipPro_KhoaPhatHanh`); khoá
  riêng không rời máy của nó: không đọc, không in, không chép, không đưa vào lệnh. Bước cần mật khẩu (`tao-khoa`, `sign`,
  `ky-uy-quyen`) và bước đổi trust store (`uy_quyen_khoa.py ghi-danh`/`hoan-tac`) do NGƯỜI DÙNG tự gõ trong console
  riêng (công cụ từ chối khi stdin không phải console thật — chống nhầm, KHÔNG phải rào chắn: Claude không tự chạy các
  lệnh đó, kể cả qua console ảo). `release_tool.py khoa-thu` chỉ tạo khoá THỬ — không bao giờ
  dùng cho bản giao máy vận hành.
- Không nới kiểm chữ ký, băm, bố cục hay khoá tin cậy để «cho chạy được»: PC2 phải TỪ CHỐI gói, lock, khoá sai.
- PC2: không ghi vào `C:\TimClipPro`, `C:\TimClipPro_State`, `C:\TimClipPro_Feed`; cập nhật chỉ qua launcher do người
  dùng chạy. Test dùng thư mục tạm, không bao giờ trỏ vào cài đặt thật.
- Stable chỉ build từ commit đã nghiệm thu trên `integration/current` (`release_tool.py build` đọc object git, không
  đọc cây làm việc); `publish` chỉ in lệnh. Gói giao máy vận hành bắt buộc lock CÓ BĂM (`release/locks/`).
- Thêm khoá tin cậy: CHỈ qua uỷ quyền có chữ ký (`uy_quyen_khoa.py`, `docs/UY_QUYEN_KHOA.md`, D-23) — không sửa tay
  `trusted_keys.json`, không đưa trust store vào release, không đổi launcher. `release/**` giữ nguyên byte (lock, khoá
  công khai, hook): đừng đổi xuống dòng.

## Test (chi tiết: `docs/ai/TEST_MATRIX.md`, hàng «Updater / cài đặt / phát hành»)
- Trước khi build Stable: suite nhanh + chậm (có `test_hai_may_gia_lap.py`) trên runtime dựng từ lock có băm.

## Tài liệu (`TimClipPro/docs/`)
`MANAGED_UPDATE.md`, `UY_QUYEN_KHOA.md`, `PHAT_HANH_HAI_MAY.md`, `MANAGED_RUNTIME_DESIGN.md`, `MANAGED_HIEU_NANG.md`,
`HUONG_DAN_PC2.md`, `KE_HOACH_PILOT_PC2.md`;
đường cũ của máy legacy: `TU_CAP_NHAT.md`, `TRIEN_KHAI_MAY_PHU.md`.

Phần dưới đây chuyển NGUYÊN VĂN từ `TimClipPro/CLAUDE.md` (bản e49340d); tên hàm/test tính từ `TimClipPro/`.

## Cài đặt managed (PC2) — bất biến bố cục

- Thư mục cài đặt và state root TÁCH BIỆT: không trùng, không cái nào nằm trong cái kia — so cả dạng chữ lẫn
  `realpath` (junction/symlink), bằng `commonpath`, không theo tiền tố chuỗi (`runtime_paths.ly_do_bo_cuc`).
  Bộ cập nhật được quyền xoá/thay `releases/`, `environments/`, `update_state/`, `staging/` — bản f4d3cb7 nhận
  `state = <cài đặt>\staging\state` rồi tự xoá sạch lịch sử (MR-P1-01). `CaiDat` kiểm khi dựng; mọi `rmtree` của
  updater lên thư mục có sẵn đi qua `CapNhat._xoa_cay` / `CaiDat.kiem_xoa` (đích thuộc vùng updater, không chồng
  state root, không chứa thư mục nguồn phát hành) — chỉ `giai_nen_an_toan` tự xoá thư mục chính nó vừa tạo.
  Đừng thêm `shutil.rmtree` trực tiếp vào `managed_update.py` (test `test_moi_rmtree_cua_updater_deu_qua_chot`
  khoá điều này). Bố cục cũ không an toàn → dừng có thông báo, không tự di chuyển/xoá.
