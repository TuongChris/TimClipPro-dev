# -*- coding: utf-8 -*-
"""Ba danh sách mẫu bí mật phải đi cùng nhau (việc nhỏ #56).

Ba nơi giữ danh sách RIÊNG:
* hook ``release/git-hooks/pre-push`` (hàm awk ``kiem()``) — quét TỪNG dòng thêm của commit sắp lên repo CÔNG KHAI;
* ``release_tool.MAU_BI_MAT`` — quét MỌI file của gói phát hành Stable (và lock);
* ``dong_goi.MAU_NOI_DUNG_NHAY_CAM`` — quét file dữ liệu của gói audit nguồn; ``release_tool.chon_file_phat_hanh``
  cũng gọi nó cho file dữ liệu của gói phát hành.

Mỗi ví dụ GIẢ trong ``MAU`` chạy qua cả ba bộ quét THẬT (hook chạy bằng git trên repo tạm như
``test_git_hook_pre_push.py``). Bộ nào không bắt phải có dòng trong ``KHONG_BAT`` kèm lý do: «có chủ ý» = khác biệt
thiết kế; «CHỖ HỞ» = lệch chưa sửa (đợt này chỉ thêm test) — sửa mã xong thì xoá dòng, test đỏ nhắc. Thêm mẫu vào MỘT
danh sách mà không có ví dụ ở ``MAU`` cũng đỏ.

Ví dụ được GHÉP từ hai mảnh để chính file này không khớp hook lẫn lệnh grep tay của GIT_WORKFLOW.md.
"""
import os
import re
import shutil

import pytest

import dong_goi
import release_tool
from test_git_hook_pre_push import HOOK, _day, _git, _tao_may

BO_QUET = ("hook", "release_tool", "dong_goi")
VI_TRI = {"hook": "release/git-hooks/pre-push, hàm kiem()", "release_tool": "release_tool.MAU_BI_MAT",
          "dong_goi": "dong_goi.MAU_NOI_DUNG_NHAY_CAM"}

_ID_44 = "1" + ("Qw3rTy_uI0-pAs9dFg7Hj" * 3)[:43]       # dạng ID bảng tính 44 ký tự, GIẢ
MAU = {
    "pem": "-----BEGIN " + "PRIVATE KEY-----",
    "json_khoa_rieng": '"private' + '_key": "gia"',
    "json_loai_tai_khoan_dv": '"type": "service' + '_account"',
    "json_ma_khoa_rieng": '"private' + '_key_id": "0123abcd"',
    "email_tai_khoan_dv": "svc-thu@du-an-thu.iam.gservice" + "account.com",
    "json_bi_mat_ung_dung": '"client' + '_secret": "gia"',
    "json_token_lam_moi": '"refresh' + '_token": "gia"',
    "khoa_api_google": "AI" + "za" + "SyGIA" + "0" * 30,
    "token_oauth": "ya" + "29." + "a0" * 15,
    "token_github": "gh" + "p_" + "A1b2" * 9,
    "pat_github": "github" + "_pat_" + "11AAAA" + "b" * 20,
    "link_bang_tinh": "https://docs.google." + "com/spreadsheets/d/" + "x" + "Ab9_" * 6,
    "id_bang_tinh_tran": "bang = " + _ID_44,
    "ma_cai_dat": '"installation' + '_id": "3b9d2c1e-7a40-4f00-8000-00000000a0a0"',
    "tieu_de_tep_cookie": "# Netscape HTTP " + "Cookie File",
    "dong_cookie": ".youtube.com\tTRUE\t/\tTRUE\t1798000000\tPREF\tf6=40000000",
    "cookie_phien_youtube": "Cookie: __Secure" + "-3PSID=g.a000GIAkhongthat000000",
    "gia_tri_bi_mat_ung_dung": "GOC" + "SPX-" + "A1b2C3d4" * 3,
    "gia_tri_token_lam_moi": "1//" + "0" + "gA1b2C3d4E5" * 3,
}

_GIAO = ("có chủ ý: MAU_BI_MAT chỉ bắt GIÁ TRỊ bí mật (ở mọi file của gói); dạng file — tên trường JSON, cookie "
         "Netscape — chon_file_phat_hanh giao cho dong_goi ở file dữ liệu (test cuối file kiểm)")
_TUNG_DONG = ("có chủ ý: hook quét TỪNG dòng thêm nên cần mẫu cho từng trường của file khoá tài khoản dịch vụ; hai gói "
              "quét CẢ file, mà file khoá luôn có dòng loại tài khoản dịch vụ (đã bắt)")
_DINH_DANH = ("có chủ ý: định danh, không phải bí mật — chỉ hook chặn vì lịch sử repo CÔNG KHAI giữ mãi; gói phát hành "
              "dựng từ commit đã qua hook")
_HO_AUDIT = ("CHỖ HỞ: gói audit nguồn (dong_goi.tao_goi) chỉ quét bằng danh sách của dong_goi — file dữ liệu mang mẫu "
             "này lọt vào gói (gói phát hành thì vẫn chặn nhờ MAU_BI_MAT)")
_HO_HOOK = "CHỖ HỞ: hook chỉ bắt TÊN trường JSON — giá trị dán trần (ghi chú, câu lệnh) lọt lên repo công khai"

# (loại, bộ quét KHÔNG bắt) → lý do.
KHONG_BAT = {
    ("json_khoa_rieng", "release_tool"): _GIAO,
    ("json_bi_mat_ung_dung", "release_tool"): _GIAO,
    ("json_token_lam_moi", "release_tool"): _GIAO,
    ("tieu_de_tep_cookie", "release_tool"): _GIAO,
    ("dong_cookie", "release_tool"): _GIAO,
    ("json_ma_khoa_rieng", "release_tool"): _TUNG_DONG,
    ("json_ma_khoa_rieng", "dong_goi"): _TUNG_DONG,
    ("email_tai_khoan_dv", "release_tool"): _TUNG_DONG + "; sheets.py (có trong gói) ghi email VÍ DỤ ở docstring",
    ("email_tai_khoan_dv", "dong_goi"): _TUNG_DONG,
    ("id_bang_tinh_tran", "release_tool"): _DINH_DANH + "; chuỗi 44 ký tự trần dễ trùng base64/băm trong gói",
    ("id_bang_tinh_tran", "dong_goi"): _DINH_DANH,
    ("ma_cai_dat", "release_tool"): _DINH_DANH,
    ("ma_cai_dat", "dong_goi"): _DINH_DANH,
    ("token_oauth", "dong_goi"): _HO_AUDIT,
    ("token_github", "dong_goi"): _HO_AUDIT,
    ("pat_github", "dong_goi"): _HO_AUDIT,
    ("link_bang_tinh", "dong_goi"): _HO_AUDIT,
    ("cookie_phien_youtube", "dong_goi"): _HO_AUDIT,
    ("gia_tri_bi_mat_ung_dung", "dong_goi"): _HO_AUDIT,
    ("gia_tri_token_lam_moi", "dong_goi"): _HO_AUDIT,
    ("cookie_phien_youtube", "hook"): ("CHỖ HỞ: hook chỉ bắt cookie dạng dòng file Netscape — dán dạng header "
                                       "(«Cookie: tên=giá trị») lọt; lệnh grep tay của GIT_WORKFLOW.md thì bắt"),
    ("gia_tri_bi_mat_ung_dung", "hook"): _HO_HOOK,
    ("gia_tri_token_lam_moi", "hook"): _HO_HOOK,
}


def _mau_hook() -> list:
    """Biểu thức awk trong hàm ``kiem()`` của hook, chuyển sang ``re`` (dòng đã ``tolower``)."""
    than = re.search(r"function kiem\(dong.*?\n    \}\n", open(HOOK, encoding="utf-8").read(), re.S)
    assert than, "không thấy hàm kiem() trong hook pre-push — sửa _mau_hook() của test này"
    kq = []
    for awk in re.findall(r"d ~ /((?:\\.|[^/\\])+)/", than.group(0)):
        try:
            kq.append(re.compile(awk.replace("\\/", "/")))
        except re.error as e:
            pytest.fail(f"mẫu awk /{awk}/ của hook không chuyển được sang re ({e}) — sửa _mau_hook()")
    return kq


def _release_bat(dong: str) -> bool:
    return any(m.search(dong.encode()) for _, m in release_tool.MAU_BI_MAT)


def _dong_goi_bat(dong: str) -> bool:
    return bool(dong_goi.ly_do_noi_dung_nhay_cam(dong.encode()))


def test_moi_mau_cua_ba_danh_sach_deu_co_vi_du():
    thieu = [f"hook: /{m.pattern}/" for m in _mau_hook() if not any(m.search(v.lower()) for v in MAU.values())]
    thieu += [f"release_tool.MAU_BI_MAT: {t}" for t, m in release_tool.MAU_BI_MAT
              if not any(m.search(v.encode()) for v in MAU.values())]
    thieu += [f"dong_goi.MAU_NOI_DUNG_NHAY_CAM: {t}" for t, m in dong_goi.MAU_NOI_DUNG_NHAY_CAM
              if not any(m.search(v) for v in MAU.values())]
    assert not thieu, ("Mẫu chưa có ví dụ trong MAU: " + "; ".join(thieu) + ". Thêm ví dụ GIẢ (ghép hai mảnh để file test "
                       "không khớp hook) rồi khai bộ quét nào không bắt — kèm lý do — ở KHONG_BAT.")
    sai = [k for k in KHONG_BAT if k[0] not in MAU or k[1] not in BO_QUET]
    assert not sai, f"KHONG_BAT có dòng sai tên loại/bộ quét: {sai}"
    ca_ba = [loai for loai in MAU if all((loai, bo) in KHONG_BAT for bo in BO_QUET)]
    assert not ca_ba, f"ví dụ không thuộc danh sách nào: {ca_ba}"


@pytest.fixture(scope="module")
def hook_bat(tmp_path_factory) -> set:
    """Loại nào hook THẬT chặn: mỗi ví dụ một file trong một commit, đẩy lên remote bare cục bộ."""
    if not (shutil.which("git") and os.path.isfile(HOOK)):
        pytest.skip("cần git + hook trong repo")
    may = _tao_may(tmp_path_factory.mktemp("hook"))
    _git(may, "switch", "-q", "--no-track", "-c", "fix/pc2/mau", "private/integration/current")
    ten = sorted(MAU)
    os.makedirs(os.path.join(may, "mau"))
    for i, loai in enumerate(ten):       # tên file trung tính: luật TÊN file của hook không được lẫn vào
        with open(os.path.join(may, "mau", f"{i:02d}.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(MAU[loai] + "\n")
    _git(may, "add", "mau")
    _git(may, "commit", "-q", "-m", "thu: mau")
    _, ra = _day(may, "fix/pc2/mau:fix/pc2/mau")
    assert "… và" not in ra, "hook cắt bớt danh sách in ra — chia ví dụ thành nhiều lần đẩy"
    return {ten[int(i)] for i in re.findall(r"mau/(\d\d)\.txt: ", ra)}


@pytest.mark.parametrize("loai", sorted(MAU))
def test_mau_co_o_mot_noi_thi_co_o_hai_noi_kia(loai, hook_bat):
    dong = MAU[loai]
    bat = {bo for bo, co in (("hook", loai in hook_bat), ("release_tool", _release_bat(dong)),
                             ("dong_goi", _dong_goi_bat(dong))) if co}
    mong = {bo for bo in BO_QUET if (loai, bo) not in KHONG_BAT}
    loi = [f"{bo} nay ĐÃ bắt — xoá dòng ({loai!r}, {bo!r}) khỏi KHONG_BAT" for bo in sorted(bat - mong)]
    loi += [f"{bo} KHÔNG bắt ({VI_TRI[bo]}) trong khi {sorted(bat)} bắt — thêm mẫu vào đó, hoặc ghi ngoại lệ CÓ CHỦ Ý "
            "kèm lý do ở KHONG_BAT" for bo in sorted(mong - bat)]
    assert not loi, f"«{loai}»: " + "; ".join(loi)


@pytest.mark.parametrize("loai", sorted(loai for (loai, bo), ly_do in KHONG_BAT.items() if ly_do == _GIAO))
def test_ban_phat_hanh_van_chan_dang_file_qua_dong_goi(loai):
    """Lý do ``_GIAO`` chỉ đúng khi file DỮ LIỆU của gói phát hành vẫn bị chặn qua dong_goi."""
    with pytest.raises(release_tool.LoiPhatHanh, match="nhạy cảm"):
        # .txt: file .json ở gốc TimClipPro/ bị nen_lay bỏ hẳn (không quét)
        release_tool.chon_file_phat_hanh({"TimClipPro/ghi_chu.txt": MAU[loai].encode()})
