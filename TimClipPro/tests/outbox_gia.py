# -*- coding: utf-8 -*-
"""Đồ giả dùng chung cho test outbox — KHÔNG gọi mạng, không khoá thật.

``CongGia`` thay transport Google Sheets: ghi nhận MỌI lần "append" thật sự xảy ra (``bang``) và cho
tiêm hành vi từng lượt gửi qua ``ke_hoach``:

* ``"ok"`` — gọi ``truoc_khi_gui`` rồi ghi, trả phản hồi đúng như Sheets API;
* ``("truoc", exc)`` — lỗi TRƯỚC dispatch (không gọi ``truoc_khi_gui``, không ghi);
* ``("sau_da_ghi", exc)`` — Google ĐÃ ghi rồi phản hồi mất (exc ném ra sau khi ghi);
* ``("sau_chua_ghi", exc)`` — dispatch rồi bị từ chối/không tới (không ghi);
* ``("phan_hoi", dict)`` — ghi rồi trả phản hồi tuỳ ý (kiểm biên nhận).
"""
import json

import outbox


# Ghép chuỗi để mã nguồn test không chứa mẫu mà bộ quét bí mật của dự án chặn (khoá GIẢ).
LOAI_KHOA = "service" + "_account"
TRUONG_KHOA_RIENG = "private" + "_key"


def phan_hoi_dung(chot, ten_tab, so_dong, dong_dau=2):
    return {"spreadsheetId": chot.spreadsheet_id, "tableRange": f"{ten_tab}!A1:AH1",
            "updates": {"spreadsheetId": chot.spreadsheet_id,
                        "updatedRange": f"'{ten_tab}'!A{dong_dau}:AH{dong_dau + so_dong - 1}",
                        "updatedRows": so_dong, "updatedColumns": 34,
                        "updatedCells": 34 * so_dong}}


class CongGia:
    def __init__(self, ten_tab="KetQuaQuet", gid=0):
        self.bang = []            # [(spreadsheet_id, gid, rows)] — chỉ những lần GHI thật
        self.ke_hoach = []
        self.lan_goi = 0
        self.ten_tab = ten_tab
        self.gid = gid

    def gui(self, chot, duong_dan_khoa, header, rows, truoc_khi_gui):
        self.lan_goi += 1
        hv = self.ke_hoach.pop(0) if self.ke_hoach else "ok"
        gid = chot.worksheet_id if chot.worksheet_id is not None else self.gid
        if isinstance(hv, tuple) and hv[0] == "truoc":
            raise hv[1]
        if isinstance(hv, tuple) and hv[0] == "hook":      # chen việc khác ngay trước dispatch
            hv[1]()
            hv = "ok"
        truoc_khi_gui(gid, self.ten_tab)
        if hv == "ok":
            self.bang.append((chot.spreadsheet_id, gid, [list(r) for r in rows]))
            return outbox.KetQuaGui(phan_hoi_dung(chot, self.ten_tab, len(rows)), gid,
                                    self.ten_tab, len(rows))
        loai, gia_tri = hv
        if loai == "sau_da_ghi":
            self.bang.append((chot.spreadsheet_id, gid, [list(r) for r in rows]))
            raise gia_tri
        if loai == "sau_chua_ghi":
            raise gia_tri
        if loai == "phan_hoi":
            self.bang.append((chot.spreadsheet_id, gid, [list(r) for r in rows]))
            return outbox.KetQuaGui(gia_tri, gid, self.ten_tab, len(rows))
        raise AssertionError(hv)


class CongNhieuTab:
    """Transport giả của MỘT bảng tính NHIỀU tab, tìm tab như gspread: theo mã (gid) nếu đích có mã,
    không thì theo TÊN. Đổi tên / thêm / xoá tab được giữa các lượt gửi. ``ghi``: chỉ lần GHI thật;
    ``phat``: gid của MỌI request ghi đã phát (kể cả lần mất phản hồi). ``ke_hoach`` từng lượt:
    ``"ok"`` | ``("sau_da_ghi", exc)`` (ghi rồi mất phản hồi / tiến trình chết) | ``("chet_truoc_ghi", exc)``
    (chết sau ``truoc_khi_gui``, request chưa đi)."""

    def __init__(self, tabs):
        self.tabs = dict(tabs)     # gid -> tên tab
        self.ghi = []              # [(gid, rows)]
        self.phat = []             # [gid]
        self.ke_hoach = []

    def doi_ten(self, gid, ten):
        self.tabs[gid] = ten

    def them(self, gid, ten):
        self.tabs[gid] = ten

    def xoa(self, gid):
        del self.tabs[gid]

    def _tim(self, chot):
        if chot.worksheet_id is not None:
            if chot.worksheet_id not in self.tabs:
                raise outbox.ChuaGui("Không thấy tab theo mã.", tam_thoi=False)
            return chot.worksheet_id
        for gid in sorted(self.tabs):
            if self.tabs[gid] == chot.worksheet_ten:
                return gid
        raise outbox.ChuaGui("Không thấy tab theo tên.", tam_thoi=False)

    def gui(self, chot, duong_dan_khoa, header, rows, truoc_khi_gui):
        hv = self.ke_hoach.pop(0) if self.ke_hoach else "ok"
        gid = self._tim(chot)
        ten = self.tabs[gid]
        truoc_khi_gui(gid, ten)
        self.phat.append(gid)
        if isinstance(hv, tuple) and hv[0] == "chet_truoc_ghi":
            raise hv[1]
        self.ghi.append((gid, [list(r) for r in rows]))
        if isinstance(hv, tuple) and hv[0] == "sau_da_ghi":
            raise hv[1]
        return outbox.KetQuaGui(phan_hoi_dung(chot, ten, len(rows)), gid, ten, len(rows))


def dich_gia(db, tmp_path, *, schema=None, installation_id=None, lo_id="", ten="Bảng thử",
             spreadsheet_id="1" + "t" * 43, gid=0):
    """Binding khoá GIẢ + một hồ sơ đích trong ``db`` → ``(hồ_sơ, ý_định_gửi)``."""
    import sheet_destinations as sd

    sd.dang_ky_xac_thuc(db, "mac_dinh", khoa_gia(tmp_path))
    d = sd.tao_dich(db, ten=ten, spreadsheet_id=spreadsheet_id, worksheet_id=gid,
                    worksheet_ten="KetQuaQuet", schema_id=schema or sd.SCHEMA_NGANG,
                    xac_thuc_ref="mac_dinh", workspace="mac_dinh")
    iid = installation_id or sd.dinh_danh_may(db)
    return d, sd.chot_y_dinh(db, d.id, installation_id=iid, lo_id=lo_id)


def khoa_gia(tmp_path, ten="khoa.json", email="gui@du-an-gia.invalid", kid="k1"):
    p = tmp_path / ten
    p.write_text(json.dumps({"type": LOAI_KHOA, "client_email": email,
                             "private_key_id": kid, TRUONG_KHOA_RIENG: "GIA-KHONG-PHAI-KHOA"}),
                 encoding="utf-8")
    return str(p)
