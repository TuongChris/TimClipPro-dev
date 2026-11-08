# -*- coding: utf-8 -*-
"""Tải video gốc theo link: không mạng — yt-dlp được thay bằng bản giả ghi file theo ``outtmpl``."""

from __future__ import annotations

import os

import pytest
import yt_dlp
from yt_dlp.utils import DownloadError

import tai_video_goc as tv

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
    ):
        goi.update(
            links=links,
            thu_muc=thu_muc,
            huy=cancel_check(),
            co_phien=phien is not None,
            chat_luong=chat_luong,
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
    assert goi == [
        ("nhieu", ([URL1], thu_muc), {"thumbnail": True}),
        (
            "kenh",
            ("https://www.youtube.com/@Kenh", thu_muc),
            {"gioi_han": 30, "chat_luong": "720p"},
        ),
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
            channel.VideoInfo(id=m, title=m, upload_date="", duration=0.0, url=f"https://www.youtube.com/watch?v={m}")
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
    for ten in ("Vlog.part 2 [abcdefghij1].mkv", "Bai.temp.1 [abcdefghij2].mp4", "Do [abcdefghij3].f137.mp4.part",
                "Do [abcdefghij4].mp4.part-Frag3", "Do [abcdefghij5].mp4.ytdl", "Do [abcdefghij6].temp.mkv"):
        (tmp_path / ten).write_bytes(b"x")
    assert [os.path.basename(f) for f in tv._file_xong(str(tmp_path))] == [
        "Bai.temp.1 [abcdefghij2].mp4", "Vlog.part 2 [abcdefghij1].mkv"]
