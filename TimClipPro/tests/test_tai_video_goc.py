# -*- coding: utf-8 -*-
"""Tải video gốc theo link: không mạng — yt-dlp được thay bằng bản giả ghi file theo ``outtmpl``."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
import yt_dlp
from yt_dlp.utils import DownloadError

import tai_video_goc as tv
import ytdlp_chung

URL1 = "https://www.youtube.com/watch?v=abcdefghij1"
URL2 = "https://youtu.be/abcdefghij2"


class YdlGia:
    """Thay ``yt_dlp.YoutubeDL``: ghi file theo ``outtmpl`` và gọi progress hook như bản thật."""

    goi: list = []
    hanh_vi: dict = {}  # url -> callable(opts) chạy trước khi ghi file (ném lỗi để giả hỏng)

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        YdlGia.goi.append((url, self.opts))
        ma = url[-11:]
        mau = self.opts["outtmpl"]
        ten = mau.replace("%(title).150B", f"Tiêu đề {ma}").replace("%(id)s", ma)
        if self.opts.get(
            "writethumbnail"
        ):  # như yt-dlp + FFmpegThumbnailsConvertor: chỉ còn ảnh .jpg
            with open(ten.replace("%(ext)s", "jpg"), "wb") as f:
                f.write(b"anh")
            return {"id": ma, "title": f"Tiêu đề {ma}"}
        hook = self.opts["progress_hooks"][0]
        with open(ten.replace("%(ext)s", "f137.mp4.part"), "wb") as f:
            f.write(b"x" * 10)
        hook(
            {
                "status": "downloading",
                "downloaded_bytes": 5,
                "total_bytes": 10,
                "info_dict": {"vcodec": "vp9"},
            }
        )
        h = YdlGia.hanh_vi.get(url)
        if h:
            h(self.opts)
        os.remove(ten.replace("%(ext)s", "f137.mp4.part"))
        with open(ten.replace("%(ext)s", "mkv"), "wb") as f:
            f.write(b"video")
        hook({"status": "finished", "info_dict": {}})
        return {
            "id": ma,
            "title": f"Tiêu đề {ma}",
            "height": 2160,
            "fps": 60,
            "vcodec": "vp9",
            "acodec": "opus",
        }


@pytest.fixture
def gia(monkeypatch):
    YdlGia.goi, YdlGia.hanh_vi = [], {}
    monkeypatch.setattr(yt_dlp, "YoutubeDL", YdlGia)
    monkeypatch.setattr(tv.shutil, "which", lambda ten: "C:/ffmpeg.exe")
    return YdlGia


def test_tach_link_bo_dong_trong_va_trung():
    assert tv.tach_link(f' {URL1}\n\n"{URL2}"\n{URL1}\n') == [URL1, URL2]


@pytest.mark.parametrize(
    "url, hop_le",
    [
        (URL1, True),
        (URL2, True),
        ("https://www.youtube.com/shorts/abcdefghij3", True),
        ("https://vimeo.com/123", True),
        ("https://www.youtube.com/@TenKenh", False),
        ("https://www.youtube.com/playlist?list=PL1", False),
        ("youtube.com/watch?v=abcdefghij1", False),
        ("D:\\video.mp4", False),
    ],
)
def test_kiem_link(url, hop_le):
    assert (tv.kiem_link(url) == "") is hop_le


def test_mo_ta_chat_luong():
    assert (
        tv.mo_ta_chat_luong(
            {"height": 2160, "fps": 60, "vcodec": "vp09.00.51.08", "acodec": "opus"}
        )
        == "2160p60 · vp09 + opus"
    )
    assert (
        tv.mo_ta_chat_luong(
            {"height": 1080, "fps": 30, "vcodec": "avc1.640028", "acodec": "none"}
        )
        == "1080p · avc1"
    )


def test_tai_hai_link_chat_luong_cao_nhat_khong_ghi_de(gia, tmp_path):
    (tmp_path / "Tiêu đề abcdefghij1 [abcdefghij1].mkv").write_bytes(b"cu")
    tien_do = []
    kq = tv.tai_nhieu(
        [URL1, URL2], str(tmp_path), progress=lambda p, m: tien_do.append((p, m))
    )

    assert [k["trang_thai"] for k in kq] == ["xong", "xong"]
    assert kq[0]["duong_dan"].endswith("Tiêu đề abcdefghij1 [abcdefghij1] (2).mkv")
    assert (
        tmp_path / "Tiêu đề abcdefghij1 [abcdefghij1].mkv"
    ).read_bytes() == b"cu"  # file cũ không bị đè
    assert kq[1]["chat_luong"] == "2160p60 · vp9 + opus"
    assert not (tmp_path / tv.THU_MUC_TAM).exists()
    opts = gia.goi[0][1]
    assert opts["format"] == "bv*+ba/b" and opts["merge_output_format"] == "mp4/mkv"
    assert opts["noplaylist"] is True and opts["playlist_items"] == "1"
    assert tien_do[-1][0] == 1.0 and all(0 <= p <= 1 for p, _ in tien_do)
    assert any("đang tải hình 50%" in m for _, m in tien_do)


def test_mot_link_loi_khong_dung_ca_lo(gia, tmp_path):
    def hong(_opts):
        raise DownloadError(
            "ERROR: [youtube] abcdefghij1: Video unavailable. This video has been removed by the uploader"
        )

    gia.hanh_vi[URL1] = hong
    kq = tv.tai_nhieu(["https://www.youtube.com/@Kenh", URL1, URL2], str(tmp_path))
    assert [k["trang_thai"] for k in kq] == ["loi", "loi", "xong"]
    assert "kênh" in kq[0]["ghi_chu"] and kq[1]["ghi_chu"]
    assert sorted(os.listdir(tmp_path)) == ["Tiêu đề abcdefghij2 [abcdefghij2].mkv"]


def test_dung_giua_chung_xoa_phan_do_va_bo_qua_phan_con_lai(gia, tmp_path):
    dung = {"co": False}

    def bam_dung(opts):
        dung["co"] = True
        opts["progress_hooks"][0](
            {
                "status": "downloading",
                "downloaded_bytes": 6,
                "total_bytes": 10,
                "info_dict": {},
            }
        )

    gia.hanh_vi[URL1] = bam_dung
    kq = tv.tai_nhieu([URL1, URL2], str(tmp_path), cancel_check=lambda: dung["co"])
    assert [k["trang_thai"] for k in kq] == ["bo_qua", "bo_qua"]
    assert len(gia.goi) == 1  # Dừng: không thử client khác, không tải link sau
    assert os.listdir(tmp_path) == []  # phần .part dở và thư mục tạm đã xoá


def test_doi_client_khi_khong_co_dinh_dang_khong_de_lai_file_do(gia, tmp_path):
    lan = {"n": 0}

    def lan_dau_hong(_opts):
        lan["n"] += 1
        if lan["n"] == 1:
            raise DownloadError(
                "ERROR: [youtube] abcdefghij1: Requested format is not available"
            )

    gia.hanh_vi[URL1] = lan_dau_hong
    kq = tv.tai_nhieu([URL1], str(tmp_path), player_clients=["", "tv"])
    assert kq[0]["trang_thai"] == "xong"
    clients = [
        o.get("extractor_args", {}).get("youtube", {}).get("player_client")
        for _, o in gia.goi
    ]
    assert clients == [None, ["tv"]]
    assert os.listdir(tmp_path) == ["Tiêu đề abcdefghij1 [abcdefghij1].mkv"]


def test_thieu_ffmpeg_bao_ro_truoc_khi_tai(gia, tmp_path, monkeypatch):
    monkeypatch.setattr(tv.shutil, "which", lambda ten: None)
    with pytest.raises(RuntimeError, match="FFmpeg"):
        tv.tai_nhieu([URL1], str(tmp_path))
    assert gia.goi == []


def test_tab_tai_video_chay_nen_va_hien_ket_qua(tmp_path, monkeypatch):
    """app.py thật (AppTest): tab mới gọi ``tai_nhieu`` ở làn tác vụ nền với link + thư mục + cờ huỷ, rồi hiện kết quả."""
    import time
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    goi = {}

    def tai_gia(
        links,
        thu_muc,
        cau_hinh_mang,
        *,
        player_clients,
        phien,
        progress,
        cancel_check,
        chat_luong,
        chuan_hoa_am,
        mo_khoa_twitch,
    ):
        goi.update(
            links=links,
            thu_muc=thu_muc,
            huy=cancel_check(),
            co_phien=phien is not None,
            chat_luong=chat_luong,
            chuan_hoa_am=chuan_hoa_am,
            mo_khoa_twitch=mo_khoa_twitch,
        )
        progress(0.5, "Video 1/2: đang tải hình 50%")
        return [
            {
                "url": URL1,
                "trang_thai": "xong",
                "duong_dan": thu_muc + "/a.mkv",
                "tieu_de": "Video A",
                "chat_luong": "2160p60 · vp9 + opus",
                "ghi_chu": "",
            },
            {
                "url": URL2,
                "trang_thai": "loi",
                "duong_dan": "",
                "tieu_de": "",
                "chat_luong": "",
                "ghi_chu": "Video đã bị gỡ.",
            },
        ]

    monkeypatch.setattr(tv, "tai_nhieu", tai_gia)
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120
    ).run()
    assert not at.exception
    nut = at.button(key="bat_dau_tai_video")
    assert nut.disabled  # chưa có link, chưa có thư mục
    next(t for t in at.text_area if t.label.startswith("Link video")).input(
        f"{URL1}\n{URL2}\n{URL1}"
    ).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu video").input(
        str(tmp_path / "video")
    ).run()
    assert at.button(key="bat_dau_tai_video").label == "⬇️ Tải 2 video"
    at.selectbox(key="cl_tai").select("1080p").run()
    next(t for t in at.text_input if t.label.startswith("File proxy")).input('"D:\\bi_mat\\proxy.txt"').run()
    next(t for t in at.text_input if t.label.startswith("File cookie Twitch")).input("D:\\bi_mat\\tw.txt").run()
    at.button(key="bat_dau_tai_video").click().run()
    for _ in range(50):
        if goi and not at.session_state.job["running"]:
            break
        time.sleep(0.1)
    at.run()
    assert not at.exception
    assert goi == {
        "links": [URL1, URL2],
        "thu_muc": str(tmp_path / "video"),
        "huy": False,
        "co_phien": True,
        "chat_luong": "1080p",
        "chuan_hoa_am": True,  # D-43: ô «Đưa âm lượng về mức YouTube» tick sẵn
        # D-44: hai ĐƯỜNG DẪN Twitch đi nguyên vào tải (bỏ ngoặc ở MoKhoaTwitch).
        "mo_khoa_twitch": ytdlp_chung.MoKhoaTwitch('"D:\\bi_mat\\proxy.txt"', "D:\\bi_mat\\tw.txt"),
    }
    chu = " ".join(e.value for e in [*at.markdown, *at.warning, *at.success])
    assert (
        "Đã tải 1/2 — bỏ qua 0, lỗi 1." in chu
        and "Video A" in chu
        and "Video đã bị gỡ" in chu
    )


def test_tab_thumbnail_va_ca_kenh_goi_dung_ham(tmp_path, monkeypatch):
    """AppTest: tab thumbnail gọi ``tai_nhieu(thumbnail=True)``; tab cả kênh gọi ``tai_kenh`` với số video + chất lượng."""
    import time
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    goi = []
    xong = [
        {
            "url": URL1,
            "trang_thai": "xong",
            "duong_dan": "a.jpg",
            "tieu_de": "A",
            "chat_luong": "ảnh JPG",
            "ghi_chu": "",
        }
    ]

    def ghi(ten):
        def ham(*a, progress, cancel_check, **kw):
            goi.append(
                (
                    ten,
                    a[:2],
                    {
                        k: v
                        for k, v in kw.items()
                        if k in ("thumbnail", "gioi_han", "chat_luong")
                    },
                )
            )
            return xong

        return ham

    monkeypatch.setattr(tv, "tai_nhieu", ghi("nhieu"))
    monkeypatch.setattr(tv, "tai_kenh", ghi("kenh"))
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120
    ).run()
    thu_muc = str(tmp_path / "anh")

    def cho_xong():
        for _ in range(50):
            if not at.session_state.job["running"]:
                break
            time.sleep(0.1)
        at.run()
        assert not at.exception
        at.session_state.job.update({"results": [], "error": "", "kind": ""})
        at.run()

    next(
        t for t in at.text_area if t.label.startswith("Link video cần lấy thumbnail")
    ).input(URL1).run()
    next(t for t in at.text_input if t.label == "Thư mục lưu thumbnail").input(
        thu_muc
    ).run()
    at.button(key="bat_dau_tai_anh").click().run()
    cho_xong()
    next(t for t in at.text_input if t.label == "Link kênh YouTube cần tải").input(
        "https://www.youtube.com/@Kenh"
    ).run()
    next(
        n for n in at.number_input if n.label.startswith("Số video mới nhất")
    ).set_value(30).run()
    at.selectbox(key="cl_kenh").select("720p").run()
    at.button(key="bat_dau_tai_kenh").click().run()
    cho_xong()
    # Thumbnail cả kênh (11/11): mặc định 0 = cả kênh.
    next(t for t in at.text_input if t.label == "Link kênh YouTube cần lấy thumbnail").input(
        "https://www.youtube.com/@KenhAnh"
    ).run()
    at.button(key="bat_dau_tai_anh_kenh").click().run()
    cho_xong()
    assert goi == [
        ("nhieu", ([URL1], thu_muc), {"thumbnail": True}),
        (
            "kenh",
            ("https://www.youtube.com/@Kenh", thu_muc),
            {"gioi_han": 30, "chat_luong": "720p"},
        ),
        ("kenh", ("https://www.youtube.com/@KenhAnh", thu_muc), {"thumbnail": True, "gioi_han": None}),
    ]


@pytest.mark.parametrize(
    "muc, dinh_dang, ghep",
    [
        ("Cao nhất", "bv*+ba/b", "mp4/mkv"),
        ("1080p", "bv*[height<=1080]+ba/b[height<=1080]", "mp4/mkv"),
        ("4K (2160p)", "bv*[height<=2160]+ba/b[height<=2160]", "mp4/mkv"),
        ("Chỉ tiếng", "ba/b", None),
    ],
)
def test_tuy_chon_dinh_dang_theo_chat_luong(muc, dinh_dang, ghep):
    tc = tv.tuy_chon_dinh_dang(muc)
    assert tc["format"] == dinh_dang and tc.get("merge_output_format") == ghep


def test_chat_luong_sai_bao_loi_truoc_khi_tai(gia, tmp_path):
    with pytest.raises(ValueError):
        tv.tai_nhieu([URL1], str(tmp_path), chat_luong="8K")
    assert gia.goi == []


def test_chat_luong_chon_di_toi_yt_dlp(gia, tmp_path):
    tv.tai_nhieu([URL1], str(tmp_path), chat_luong="720p")
    assert gia.goi[0][1]["format"] == "bv*[height<=720]+ba/b[height<=720]"


def test_thumbnail_luu_jpg_khong_tai_video(gia, tmp_path):
    kq = tv.tai_nhieu([URL1], str(tmp_path), thumbnail=True)
    assert kq[0]["trang_thai"] == "xong" and kq[0]["chat_luong"] == "ảnh JPG"
    assert os.listdir(tmp_path) == ["Tiêu đề abcdefghij1 [abcdefghij1].jpg"]
    opts = gia.goi[0][1]
    assert opts["skip_download"] is True and opts["writethumbnail"] is True
    assert opts["postprocessors"] == [
        {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"}
    ]
    assert "format" not in opts


def test_bo_qua_video_da_co_nhung_khong_tinh_anh_thumbnail(gia, tmp_path):
    (tmp_path / "Cũ [abcdefghij1].mkv").write_bytes(b"cu")
    (tmp_path / "Ảnh [abcdefghij2].jpg").write_bytes(b"anh")
    kq = tv.tai_nhieu([URL1, URL2], str(tmp_path), bo_qua_da_co=True)
    assert [k["trang_thai"] for k in kq] == ["bo_qua", "xong"]
    assert [u for u, _ in gia.goi] == [URL2]


def test_tai_kenh_lay_danh_sach_roi_bo_qua_video_da_co(gia, tmp_path, monkeypatch):
    import channel

    nhan = {}

    def liet_ke(url, limit=None, **kw):
        nhan.update(url=url, limit=limit, co_phien=kw.get("phien_youtube") is not None)
        return [
            channel.VideoInfo(
                id=m,
                title=m,
                upload_date="",
                duration=0.0,
                url=f"https://www.youtube.com/watch?v={m}",
            )
            for m in ("abcdefghij1", "abcdefghij2")
        ]

    monkeypatch.setattr(channel.ChannelSync, "list_channel", staticmethod(liet_ke))
    (tmp_path / "Cũ [abcdefghij1].webm").write_bytes(b"cu")
    kq = tv.tai_kenh(
        " https://www.youtube.com/@Kenh ", str(tmp_path), gioi_han=5, chat_luong="1080p"
    )
    assert nhan == {
        "url": "https://www.youtube.com/@Kenh",
        "limit": 5,
        "co_phien": True,
    }
    assert [k["trang_thai"] for k in kq] == ["bo_qua", "xong"]
    assert gia.goi[0][1]["format"] == "bv*[height<=1080]+ba/b[height<=1080]"


def test_tai_kenh_rong_bao_loi(gia, tmp_path, monkeypatch):
    import channel

    monkeypatch.setattr(
        channel.ChannelSync, "list_channel", staticmethod(lambda *a, **k: [])
    )
    with pytest.raises(RuntimeError, match="không có video"):
        tv.tai_kenh("https://www.youtube.com/@Kenh", str(tmp_path))


def test_chon_thu_muc_doc_utf8_va_bao_loi_ro(monkeypatch):
    compile(tv._HOP_THOAI, "hop_thoai", "exec")  # mã chạy ở tiến trình con phải hợp lệ
    ra = {}

    def chay(lenh, **kw):
        ra["lenh"] = lenh
        return tv.subprocess.CompletedProcess(
            lenh, ra.get("ma", 0), "D:/Video gốc".encode("utf-8"), b""
        )

    monkeypatch.setattr(tv.subprocess, "run", chay)
    assert tv.chon_thu_muc("D:/cu") == os.path.normpath("D:/Video gốc")
    assert ra["lenh"][-1] == "D:/cu" and "-I" in ra["lenh"]
    ra["ma"] = 1
    with pytest.raises(RuntimeError, match="dán đường dẫn"):
        tv.chon_thu_muc()


def test_tieu_de_co_part_hay_temp_van_la_file_xong(tmp_path):
    """Chỉ ĐUÔI tên mới đánh dấu file dở; «.part»/«.temp.» nằm trong tiêu đề không được làm mất video đã tải."""
    for ten in (
        "Vlog.part 2 [abcdefghij1].mkv",
        "Bai.temp.1 [abcdefghij2].mp4",
        "Do [abcdefghij3].f137.mp4.part",
        "Do [abcdefghij4].mp4.part-Frag3",
        "Do [abcdefghij5].mp4.ytdl",
        "Do [abcdefghij6].temp.mkv",
    ):
        (tmp_path / ten).write_bytes(b"x")
    assert [os.path.basename(f) for f in tv._file_xong(str(tmp_path))] == [
        "Bai.temp.1 [abcdefghij2].mp4",
        "Vlog.part 2 [abcdefghij1].mkv",
    ]


def test_o_dia_sap_day_thi_dung_khong_tai_tiep(gia, tmp_path, monkeypatch):
    """Tải cả kênh qua đêm không được làm đầy ổ: dưới mức trống tối thiểu thì các video còn lại «bỏ qua»."""
    trong = {"byte": 50 * 10**9}
    monkeypatch.setattr(
        tv.shutil,
        "disk_usage",
        lambda p: SimpleNamespace(total=0, used=0, free=trong["byte"]),
    )

    def day_o(_opts):
        trong["byte"] = 10**9  # video 1 tải xong thì ổ chỉ còn 1 GB

    gia.hanh_vi[URL1] = day_o
    kq = tv.tai_nhieu([URL1, URL2], str(tmp_path))
    assert [k["trang_thai"] for k in kq] == ["xong", "bo_qua"]
    assert "Ổ đĩa" in kq[1]["ghi_chu"] and [u for u, _ in gia.goi] == [URL1]


def test_file_chi_tieng_khong_chan_tai_video_va_nguoc_lai(gia, tmp_path):
    kq = tv.tai_nhieu([URL1], str(tmp_path), chat_luong="Chỉ tiếng")
    assert kq[0]["duong_dan"].endswith(
        "[abcdefghij1].audio.mkv"
    )  # yt-dlp giả luôn ra .mkv
    # Đã có bản chỉ-tiếng: tải VIDEO cùng thư mục vẫn phải tải; tải CHỈ TIẾNG lần nữa thì bỏ qua.
    assert [
        k["trang_thai"] for k in tv.tai_nhieu([URL1], str(tmp_path), bo_qua_da_co=True)
    ] == ["xong"]
    assert [
        k["trang_thai"]
        for k in tv.tai_nhieu(
            [URL1], str(tmp_path), bo_qua_da_co=True, chat_luong="Chỉ tiếng"
        )
    ] == ["bo_qua"]


def test_thu_muc_tam_cua_luot_da_chet_tu_lau_duoc_don(gia, tmp_path):
    """App bị tắt giữa lượt tải để lại «.timclip_tai_do/<mã>/…part» (có thể vài GB): lượt sau dọn bản cũ."""
    cu = tmp_path / tv.THU_MUC_TAM / "luot_cu"
    cu.mkdir(parents=True)
    (cu / "x.f313.webm.part").write_bytes(b"x" * 10)
    xa = 1_000_000_000
    os.utime(cu, (xa, xa))
    tv.tai_nhieu([URL1], str(tmp_path))
    assert not (tmp_path / tv.THU_MUC_TAM).exists()


def test_cung_mot_video_hai_lan_trong_mot_luot_chi_tai_mot_lan(gia, tmp_path):
    kq = tv.tai_nhieu([URL1, "https://youtu.be/abcdefghij1"], str(tmp_path))
    assert [k["trang_thai"] for k in kq] == ["xong", "bo_qua"]
    assert len(gia.goi) == 1 and len(os.listdir(tmp_path)) == 1


def test_tai_khong_dang_nhap_sau_403_phai_noi_ro(gia, tmp_path, monkeypatch):
    """Mọi client nhận cookie bị 403, client không-cookie tải được: kết quả phải nói «KHÔNG đăng nhập»."""
    def thu_gia(clients, chay, opts, *, khi_lui_khong_cookie=None, **kw):
        ket_qua = chay(opts)
        khi_lui_khong_cookie("android", RuntimeError("HTTP Error 403"))
        return ket_qua

    monkeypatch.setattr(tv, "thu_tung_client", thu_gia)
    kq = tv.tai_nhieu([URL1], str(tmp_path))
    assert kq[0]["trang_thai"] == "xong" and "KHÔNG đăng nhập" in kq[0]["ghi_chu"]


# ---------------------------------------------------------------- tiêu đề của kênh (D-38)

def _kenh_gia(monkeypatch, ds):
    import channel

    nhan = {}

    def liet_ke(url, limit=None, **kw):
        nhan.update(url=url, limit=limit, co_phien=kw.get("phien_youtube") is not None)
        return [channel.VideoInfo(id=m, title=t, upload_date="", duration=d, url="")
                for m, t, d in ds]

    monkeypatch.setattr(channel.ChannelSync, "list_channel", staticmethod(liet_ke))
    return nhan


def test_tieu_de_kenh_mot_luot_liet_ke_khong_gioi_han(monkeypatch):
    nhan = _kenh_gia(monkeypatch, [("abcdefghij1", "Tập 1: Mở đầu", 3725.9), ("abcdefghij2", "Live", 0.0)])
    dong = tv.tieu_de_kenh(" https://www.youtube.com/@Kenh ")
    assert nhan == {"url": "https://www.youtube.com/@Kenh", "limit": None, "co_phien": True}
    assert dong == [
        {"STT": 1, "Tiêu đề": "Tập 1: Mở đầu", "Link": "https://www.youtube.com/watch?v=abcdefghij1",
         "Thời lượng": "01:02:05"},
        {"STT": 2, "Tiêu đề": "Live", "Link": "https://www.youtube.com/watch?v=abcdefghij2", "Thời lượng": ""},
    ]


def test_tieu_de_kenh_rong_bao_loi(monkeypatch):
    _kenh_gia(monkeypatch, [])
    with pytest.raises(RuntimeError, match="không có video"):
        tv.tieu_de_kenh("https://www.youtube.com/@Kenh")


def test_csv_tieu_de_mo_dung_trong_excel_va_chan_cong_thuc():
    import csv
    import io

    dong = [{"STT": 1, "Tiêu đề": "=HYPERLINK(\"x\")", "Link": "https://www.youtube.com/watch?v=abcdefghij1",
             "Thời lượng": "00:10:00"},
            {"STT": 2, "Tiêu đề": "Tiếng Việt, có dấu phẩy", "Link": "l", "Thời lượng": ""}]
    raw = tv.csv_tieu_de(dong)
    assert raw.startswith(b"\xef\xbb\xbf")                     # BOM: Excel đọc đúng tiếng Việt
    bang = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert bang == [["STT", "Tiêu đề", "Link", "Thời lượng"],
                    ["1", "'=HYPERLINK(\"x\")", "https://www.youtube.com/watch?v=abcdefghij1", "00:10:00"],
                    ["2", "Tiếng Việt, có dấu phẩy", "l", ""]]


def test_txt_tieu_de_moi_dong_mot_tieu_de():
    dong = [{"STT": 1, "Tiêu đề": "Tập 1"}, {"STT": 2, "Tiêu đề": "=Tập 2"}]
    assert tv.txt_tieu_de(dong) == "Tập 1\r\n=Tập 2\r\n".encode("utf-8")


@pytest.mark.parametrize("url, ten", [
    ("https://www.youtube.com/@T%C3%AAn%20K%C3%AAnh/videos", "tieu_de_Tên_Kênh"),
    ("https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv", "tieu_de_UCabcdefghijklmnopqrstuv"),
    ("https://www.youtube.com/c/a:b?x=1", "tieu_de_kenh"),
])
def test_ten_file_kenh(url, ten):
    assert tv.ten_file_kenh(url) == ten


def test_tab_tieu_de_kenh_hien_bang_va_hai_nut_tai(tmp_path, monkeypatch):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("TIMCLIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TIMCLIP_OUTPUT_DIR", str(tmp_path / "ketqua"))
    nhan = []

    def gia_lap(url, cau_hinh_mang=None, **kw):
        nhan.append(url)
        return [{"STT": 1, "Tiêu đề": "Tập 1", "Link": "https://www.youtube.com/watch?v=abcdefghij1",
                 "Thời lượng": "00:01:00"}]

    monkeypatch.setattr(tv, "tieu_de_kenh", gia_lap)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    next(t for t in at.text_input if t.label == "Link kênh YouTube cần lấy tiêu đề").input(
        "https://www.youtube.com/@Kenh").run()
    at.button(key="lay_tieu_de").click().run()
    assert not at.exception and nhan == ["https://www.youtube.com/@Kenh"]
    assert any("1 video" in s.value for s in at.success)
    assert at.session_state.tieu_de_kenh[1][0]["Tiêu đề"] == "Tập 1"
    assert sorted(e.label for e in at.get("download_button")) == [
        "⬇️ Tải file CSV (mở bằng Excel)", "⬇️ Tải file TXT (chỉ tiêu đề)"]


def _song_song(opts):
    return (
        opts.get("concurrent_fragment_downloads"),
        opts.get("extractor_args", {}).get("youtube", {}).get("formats"),
    )


def test_tai_nhieu_ket_noi_song_song_giu_player_client(gia, tmp_path):
    """Một kết nối tải lúc nhanh lúc chậm (đo 09/11: 0,78–25 MB/s); tách khúc 10 MB tải 4 khúc cùng lúc ~78 MB/s."""
    kq = tv.tai_nhieu([URL1], str(tmp_path), player_clients=["tv"])
    assert kq[0]["trang_thai"] == "xong"
    opts = gia.goi[0][1]
    assert _song_song(opts) == (4, ["dashy", "duplicate"])
    assert opts["extractor_args"]["youtube"]["player_client"] == ["tv"]


def test_loi_dinh_dang_moi_client_chi_hoi_youtube_mot_lan(gia, tmp_path):
    """Audit 10/11 mục 3: đường lui một kết nối từng chạy lại CẢ lượt trích xuất với mọi lỗi nhóm định dạng (n challenge,
    HTTP 400, «No video formats found» của client không nhận cookie) → gấp đôi số lần hỏi YouTube."""

    def hong(_opts):
        raise DownloadError("ERROR: [youtube] abcdefghij1: Requested format is not available")

    gia.hanh_vi[URL1] = hong
    kq = tv.tai_nhieu([URL1], str(tmp_path), player_clients=["tv"])
    assert kq[0]["trang_thai"] == "loi"
    assert len(gia.goi) == 1


def test_tai_nhieu_boc_bo_chon_dinh_dang_moi_lan_tai(gia, tmp_path, monkeypatch):
    goi = []
    monkeypatch.setattr(tv, "dung_ban_khuc", lambda ydl: goi.append(ydl))
    tv.tai_nhieu([URL1, URL2], str(tmp_path))
    assert len(goi) == 2


def _dd(fid, url, **kw):
    f = {"format_id": fid, "url": url, "protocol": "https", "ext": "mp4", **kw}
    if "-dashy" in fid:
        f.update(protocol="http_dash_segments", fragments=[{"url": url + "&range=0-9"}])
    return f


def test_dung_ban_khuc_chon_tren_ban_thuong_roi_doi_sang_khuc_cung_url():
    """Audit 10/11 mục 4: chỉ ``formats=dashy`` thì yt-dlp BỎ định dạng không báo dung lượng (vd. 1080p60 «299») — bộ
    chọn lặng lẽ lấy bản kém hơn. Nay chọn trên danh sách ĐỦ bản thường, rồi đổi sang bản khúc cùng URL nếu có."""
    hinh = {"vcodec": "avc1.640028", "acodec": "none", "height": 1080}
    tieng = {"vcodec": "none", "acodec": "mp4a.40.2", "ext": "m4a", "abr": 128}
    # Thật 10/11: video nhiều ngôn ngữ tiếng → yt-dlp đánh số lại mã trùng («140-11», «140-dashy-11»): ghép cặp theo URL.
    ds = [
        # bản khúc đứng TRƯỚC bản thường: yt-dlp coi định dạng đứng sau là tốt hơn — chỉ ghép cặp mới ra bản khúc.
        _dd("140-dashy-0", "U140bn", filesize=10, language="bn", **tieng),
        _dd("140-0", "U140bn", filesize=10, language="bn", **tieng),
        _dd("140-dashy-1", "U140", filesize=10, language="en", language_preference=10, **tieng),
        _dd("140-1", "U140", filesize=10, language="en", language_preference=10, **tieng),
        _dd("137-dashy", "U137", filesize=100, fps=30, tbr=4000, **hinh),
        _dd("137", "U137", filesize=100, fps=30, tbr=4000, **hinh),
        _dd("299", "U299", fps=60, tbr=6000, **hinh),  # không có dung lượng → không có bản khúc
    ]
    ydl = yt_dlp.YoutubeDL({"format": "bv*[vcodec^=avc1][height<=1080]+ba[acodec^=mp4a]", "quiet": True,
                            "extractor_args": {"youtube": {"formats": ["dashy", "duplicate"]}}})
    tv.dung_ban_khuc(ydl)
    kq = ydl._select_formats(ds, ydl.format_selector)
    assert [f["format_id"] for f in kq[0]["requested_formats"]] == ["299", "140-dashy-1"]
    assert kq[0]["protocol"] == "https+http_dash_segments"
    kq = ydl._select_formats([f for f in ds if not f["format_id"].startswith("299")], ydl.format_selector)
    assert [f["format_id"] for f in kq[0]["requested_formats"]] == ["137-dashy", "140-dashy-1"]


def test_dung_ban_khuc_khong_bat_song_song_thi_de_nguyen():
    ydl = yt_dlp.YoutubeDL({"format": "b", "quiet": True})
    goc = ydl.format_selector
    tv.dung_ban_khuc(ydl)
    assert ydl.format_selector is goc


def test_dung_khi_file_part_con_mo_trong_vong_tham_chieu_van_xoa_sach(gia, tmp_path):
    """Thật (09/11, tải song song): bị Dừng thì yt-dlp KHÔNG đóng file .part — handle nằm trong vòng tham chiếu
    frame ↔ traceback, Windows không cho xoá file đang mở → .part trăm MB nằm lại trong thư mục tạm."""
    dung = {"co": False}

    def bam_dung_khi_dang_ghi(opts):
        ctx = {}
        ctx["dest_stream"] = open(
            os.path.join(os.path.dirname(opts["outtmpl"]), "dang_ghi.f137.mp4.part"), "wb"
        )
        ctx["vong"] = ctx  # vòng tham chiếu: refcount không tự đóng file
        dung["co"] = True
        try:
            opts["progress_hooks"][0](
                {"status": "downloading", "downloaded_bytes": 6, "total_bytes": 10, "info_dict": {}}
            )
        except Exception as e:  # noqa: BLE001
            ctx["loi"] = e  # như yt-dlp: ngữ cảnh giữ lỗi, lỗi giữ traceback → frame giữ ctx
            raise

    gia.hanh_vi[URL1] = bam_dung_khi_dang_ghi
    kq = tv.tai_nhieu([URL1], str(tmp_path), cancel_check=lambda: dung["co"])
    assert kq[0]["trang_thai"] == "bo_qua"
    assert os.listdir(tmp_path) == []


def test_chuan_hoa_am_luong_chi_khi_bat_va_ghi_chu(gia, tmp_path, monkeypatch):
    """D-43: tick «Đưa âm lượng về mức YouTube» → chỉnh file vừa tải (trong thư mục tạm, trước khi ra tên cuối)."""
    import am_luong

    goi = []

    def chuan_hoa(path, **kw):
        goi.append(path)
        return "Âm lượng -28.5 → -14 LUFS (mức YouTube)."

    monkeypatch.setattr(am_luong, "chuan_hoa", chuan_hoa)
    tv.tai_nhieu([URL1], str(tmp_path / "a"))
    assert goi == []  # mặc định không đụng âm lượng
    kq = tv.tai_nhieu([URL1], str(tmp_path / "b"), chuan_hoa_am=True)
    assert len(goi) == 1 and tv.THU_MUC_TAM in goi[0]
    assert kq[0]["trang_thai"] == "xong" and "-14 LUFS" in kq[0]["ghi_chu"]


def test_chinh_am_luong_hong_van_giu_video_da_tai(gia, tmp_path, monkeypatch):
    import am_luong

    def hong(path, **kw):
        raise RuntimeError("ffmpeg hỏng")

    monkeypatch.setattr(am_luong, "chuan_hoa", hong)
    kq = tv.tai_nhieu([URL1], str(tmp_path), chuan_hoa_am=True)
    assert kq[0]["trang_thai"] == "xong" and "Chưa chỉnh được âm lượng" in kq[0]["ghi_chu"]
    assert os.path.isfile(kq[0]["duong_dan"])


def test_dung_luc_chinh_am_luong_giu_video_da_tai(gia, tmp_path, monkeypatch):
    """Audit 11/11: Dừng lúc chỉnh âm lượng KHÔNG vứt video đã tải xong (có thể 13 GB) — giữ âm lượng gốc, link sau bỏ qua."""
    import am_luong

    dung = {"co": False}

    def chuan_hoa(path, **kw):
        dung["co"] = True  # người dùng bấm Dừng giữa lúc chỉnh
        raise am_luong.DaHuyChinhAmLuong("dừng")

    monkeypatch.setattr(am_luong, "chuan_hoa", chuan_hoa)
    kq = tv.tai_nhieu([URL1, URL2], str(tmp_path), chuan_hoa_am=True, cancel_check=lambda: dung["co"])
    assert kq[0]["trang_thai"] == "xong" and os.path.isfile(kq[0]["duong_dan"])
    assert "giữ âm lượng gốc" in kq[0]["ghi_chu"]
    assert kq[1]["trang_thai"] == "bo_qua"
    assert not (tmp_path / tv.THU_MUC_TAM).exists()



# ---- audit 11/11 (2): mã video Twitch để nhận «đã có»/«trùng»
TWITCH = "https://www.twitch.tv/videos/12345678901"


@pytest.mark.parametrize("url, ma", [
    (URL1, "abcdefghij1"),
    (TWITCH, "v12345678901"),
    ("https://twitch.tv/videos/987", "v987"),
    ("https://www.twitch.tv/tenkenh/v/555", "v555"),
    ("https://www.twitch.tv/tenkenh/video/556", "v556"),
    ("https://player.twitch.tv/?video=v557&parent=x", "v557"),
    ("https://www.twitch.tv/tenkenh/videos", ""),
    ("https://clips.twitch.tv/TenClip", ""),
    ("https://evil.com/twitch.tv/videos/1", ""),
    ("https://vimeo.com/123", ""),
])
def test_ma_link(url, ma):
    assert tv.ma_link(url) == ma


def test_twitch_da_co_trong_thu_muc_thi_bo_qua(gia, tmp_path):
    (tmp_path / "Phat lai [v12345678901].mp4").write_bytes(b"cu")
    kq = tv.tai_nhieu([TWITCH], str(tmp_path), bo_qua_da_co=True)
    assert kq[0]["trang_thai"] == "bo_qua" and gia.goi == []
    assert tv.ma_da_co(str(tmp_path)) == {"v12345678901"}


def test_twitch_lap_lai_trong_luot_tai_mot_lan(gia, tmp_path):
    kq = tv.tai_nhieu([TWITCH, TWITCH.replace("www.", "")], str(tmp_path))
    assert [k["trang_thai"] for k in kq] == ["xong", "bo_qua"] and len(gia.goi) == 1



# ---- thumbnail cả kênh (11/11)
def test_ma_da_co_anh_tach_rieng_video(tmp_path):
    (tmp_path / "A [abcdefghij1].jpg").write_bytes(b"a")
    (tmp_path / "B [abcdefghij2].mp4").write_bytes(b"v")
    (tmp_path / "C [abcdefghij3].webp").write_bytes(b"w")  # ảnh gốc chưa đổi sang jpg: chưa tính
    assert tv.ma_da_co(str(tmp_path), anh=True) == {"abcdefghij1"}
    assert tv.ma_da_co(str(tmp_path)) == {"abcdefghij2"}


class _YdlAnh:
    """``yt_dlp.YoutubeDL`` giả cho thumbnail cả kênh: chỉ ``urlopen`` ảnh i.ytimg.com + ``prepare_filename``; trích thông
    tin video (đường chậm) là lỗi."""

    mo: list = []
    thieu: set = set()  # (mã, loại) trả 404

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, *a, **k):
        raise AssertionError("thumbnail cả kênh không được trích thông tin từng video")

    def prepare_filename(self, info, outtmpl=None):
        from yt_dlp.utils import sanitize_filename

        return os.path.join(os.path.dirname(self.opts["outtmpl"]),
                            f"{sanitize_filename(info['title'])} [{info['id']}].{info['ext']}")

    def urlopen(self, url):
        import io

        from yt_dlp.networking.common import Response
        from yt_dlp.networking.exceptions import HTTPError

        _YdlAnh.mo.append(url)
        ma, loai = url.split("/vi/")[1].split("/")
        if (ma, loai.split(".")[0]) in _YdlAnh.thieu:
            raise HTTPError(Response(io.BytesIO(b""), url, {}, status=404))
        return io.BytesIO(f"{ma}:{loai}".encode())


@pytest.fixture
def ydl_anh(monkeypatch):
    import channel

    _YdlAnh.mo, _YdlAnh.thieu = [], set()
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _YdlAnh)

    def liet_ke(url, limit=None, **kw):
        return [channel.VideoInfo(id=m, title=t, upload_date="", duration=0.0, url=f"https://www.youtube.com/watch?v={m}")
                for m, t in (("abcdefghij1", "Một"), ("abcdefghij2", "Hai?"), ("abcdefghij3", "Ba"))]

    monkeypatch.setattr(channel.ChannelSync, "list_channel", staticmethod(liet_ke))
    return _YdlAnh


def test_thumbnail_ca_kenh_tai_thang_anh_khong_trich_tung_video(ydl_anh, tmp_path):
    """11/11: lấy thumbnail cả kênh bằng địa chỉ ảnh cố định (i.ytimg.com) — 8 s/ảnh → dưới 1 s. Thiếu bản 1280×720 thì
    lùi 640×480; ảnh đã có bỏ qua (có VIDEO trùng mã không tính là có ảnh); tên file như đường cũ (tiêu đề [mã].jpg)."""
    (tmp_path / "Cũ [abcdefghij1].jpg").write_bytes(b"cu")
    (tmp_path / "Video [abcdefghij2].mp4").write_bytes(b"video")
    ydl_anh.thieu = {("abcdefghij3", "maxresdefault")}
    kq = tv.tai_kenh("https://www.youtube.com/@Kenh", str(tmp_path), thumbnail=True)
    assert [k["trang_thai"] for k in kq] == ["bo_qua", "xong", "xong"]
    assert kq[1]["duong_dan"] == str(tmp_path / "Hai？ [abcdefghij2].jpg")  # «?» đổi như yt-dlp
    assert (tmp_path / "Hai？ [abcdefghij2].jpg").read_bytes() == b"abcdefghij2:maxresdefault.jpg"
    assert (tmp_path / "Ba [abcdefghij3].jpg").read_bytes() == b"abcdefghij3:sddefault.jpg"
    assert kq[1]["chat_luong"] == "ảnh JPG 1280×720" and kq[2]["chat_luong"] == "ảnh JPG 640×480"
    assert kq[1]["tieu_de"] == "Hai?"
    assert all(u.startswith("https://i.ytimg.com/vi/") for u in ydl_anh.mo) and len(ydl_anh.mo) == 3
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".part")]


def test_thumbnail_ca_kenh_dung_giua_chung(ydl_anh, tmp_path):
    dung = {"co": False}
    goc = _YdlAnh.urlopen

    def mo_roi_dung(self, url):
        dung["co"] = True  # bấm Dừng ngay sau ảnh đầu
        return goc(self, url)

    _YdlAnh.urlopen = mo_roi_dung
    try:
        kq = tv.tai_kenh("https://www.youtube.com/@Kenh", str(tmp_path), thumbnail=True, cancel_check=lambda: dung["co"])
    finally:
        _YdlAnh.urlopen = goc
    assert [k["trang_thai"] for k in kq] == ["xong", "bo_qua", "bo_qua"]
    assert sorted(os.listdir(tmp_path)) == ["Một [abcdefghij1].jpg"]


def test_thumbnail_ca_kenh_khong_co_anh_nao(ydl_anh, tmp_path):
    ydl_anh.thieu = {("abcdefghij1", t) for t in ("maxresdefault", "sddefault", "hqdefault")}
    kq = tv.tai_kenh("https://www.youtube.com/@Kenh", str(tmp_path), thumbnail=True)
    assert kq[0]["trang_thai"] == "loi" and "thumbnail" in kq[0]["ghi_chu"]
    assert [k["trang_thai"] for k in kq[1:]] == ["xong", "xong"]
