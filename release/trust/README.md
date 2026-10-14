# release/trust/ — yêu cầu và uỷ quyền ghi danh khoá ký (công khai, có chữ ký)

* `yeu_cau_<máy>_<key_id>.json` — máy MỚI tạo (`uy_quyen_khoa.py yeu-cau`, chủ máy gõ mật khẩu khoá mới): khoá công khai,
  băm định danh cài đặt, băm trust store, khoá đang tin; TỰ KÝ bằng khoá mới.
* `uy_quyen_<máy>_<key_id>.json` — máy ĐANG được tin ký (`release_tool.py ky-uy-quyen`, chủ máy gõ mật khẩu).
* Kiểm ngoại tuyến (máy nào cũng chạy được):
  `release_tool.py kiem-uy-quyen --uy-quyen <uy_quyen> --yeu-cau <yeu_cau> --tin-cay release/trusted_keys.json`.
* Uỷ quyền chỉ dùng được MỘT lần, cho ĐÚNG một cài đặt và đúng trust store lúc tạo yêu cầu (`docs/UY_QUYEN_KHOA.md`).
