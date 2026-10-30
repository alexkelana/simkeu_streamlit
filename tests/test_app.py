"""Unit / integrasi tes untuk SIMKEU Kecamatan Candisari 2027 (AppTest)."""

import sys
from pathlib import Path

import pandas as pd

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def _run_app():
    return AppTest.from_file(ROOT / "streamlit_app.py").run(timeout=60)


class TestAppRuns:
    def test_entrypoint_no_exception(self):
        at = _run_app()
        assert not at.exception, f"App error: {at.exception}"

    def test_format_rupiah(self):
        # Impor fungsi murni tanpa menjalankan UI
        sys.path.insert(0, str(ROOT))
        from app_pages.helpers import format_rupiah, is_manager

        assert format_rupiah(1000000) == "Rp 1.000.000"
        assert format_rupiah(0) == "Rp 0"
        assert format_rupiah(-500000) == "(Rp 500.000)"
        assert format_rupiah("500,000.00") == "Rp 500.000"
        assert format_rupiah("abc") == "-"
        assert format_rupiah(None) == "-"

    def test_parse_number(self):
        sys.path.insert(0, str(ROOT))
        from app_pages.helpers import parse_number

        assert parse_number("500,000.00") == 500000.0
        assert parse_number("50,000,000.00") == 50000000.0
        assert parse_number("1.234.567,89") == 1234567.89
        assert parse_number("1,234,567.89") == 1234567.89
        assert parse_number("") is None
        assert parse_number("abc") is None

    def test_is_manager(self):
        sys.path.insert(0, str(ROOT))
        from app_pages.helpers import is_manager

        assert is_manager("ADMIN") is True
        assert is_manager("KASUBAG_PEK") is True
        assert is_manager("PPTK") is False
        assert is_manager("admin") is True

    def test_menu_visibility_per_role(self):
        sys.path.insert(0, str(ROOT))
        from app_pages.helpers import menu_visibility

        # KASUBAG_PEK: Dashboard, Transaksi, Manajerial.
        kasubag = menu_visibility("KASUBAG_PEK")
        assert kasubag["dashboard"] is True
        assert kasubag["transaksi"] is True
        assert kasubag["manajerial"] is True
        assert kasubag["pengajuan_pagu"] is False
        assert kasubag["master_data"] is False

        # PPTK: Dashboard, Transaksi (tanpa Pengajuan Pagu).
        pptk = menu_visibility("pptk")
        assert pptk["dashboard"] is True
        assert pptk["transaksi"] is True
        assert pptk["manajerial"] is False
        assert pptk["pengajuan_pagu"] is False
        assert pptk["master_data"] is False

        # ADMIN: Dashboard, Master Data (tanpa Transaksi).
        admin = menu_visibility("ADMIN")
        assert admin["dashboard"] is True
        assert admin["transaksi"] is False
        assert admin["manajerial"] is False
        assert admin["pengajuan_pagu"] is False
        assert admin["master_data"] is True

        # Jumlah menu: KASUBAG_PEK = 3, PPTK = 2 (tanpa Pengajuan Pagu), ADMIN = 2 (tanpa Transaksi).
        for peran, diharapkan in (("KASUBAG_PEK", 3), ("PPTK", 2), ("ADMIN", 2)):
            menu = menu_visibility(peran)
            jumlah = int(menu["dashboard"]) + int(menu["transaksi"]) + sum(
                menu[k] for k in ("manajerial", "pengajuan_pagu", "master_data")
            )
            assert jumlah == diharapkan, (
                f"{peran} seharusnya punya {diharapkan} menu, dapat {jumlah}"
            )

    def test_password_hashing(self):
        sys.path.insert(0, str(ROOT))
        from app_pages.helpers import hash_password, verify_password, is_hashed

        hashed = hash_password("rahasia123")
        assert is_hashed(hashed)
        assert verify_password("rahasia123", hashed) is True
        assert verify_password("salah", hashed) is False
        assert verify_password("rahasia123", "") is False
        # Password plaintext legacy masih dapat diverifikasi (migrasi data lama).
        assert verify_password("admin123", "admin123") is True
        assert verify_password("admin123", "admin124") is False

    def test_predikats_keamanan(self):
        sys.path.insert(0, str(ROOT))
        from app_pages.helpers import (
            boleh_edit_transaksi, boleh_hapus_transaksi, boleh_ajukan_ulang,
        )
        import pandas as pd

        draft = pd.Series({
            "PPTK": "Budi (budi)", "STATUS": "Draft",
            "URAIAN": "x", "NOMINAL": 1000,
        })
        ditolak = pd.Series({
            "PPTK": "Budi (budi)", "STATUS": "Ditolak",
            "URAIAN": "x", "NOMINAL": 1000,
        })
        disetujui = pd.Series({
            "PPTK": "Budi (budi)", "STATUS": "Disetujui",
            "URAIAN": "x", "NOMINAL": 1000,
        })
        lain = pd.Series({
            "PPTK": "Lain (lain)", "STATUS": "Draft",
            "URAIAN": "x", "NOMINAL": 1000,
        })

        # PPTK boleh edit/hapus Draft miliknya.
        assert boleh_edit_transaksi(draft, "Budi (budi)") is True
        assert boleh_hapus_transaksi(draft, "Budi (budi)") is True
        # Tidak boleh edit/hapus bukan Draft atau bukan miliknya.
        assert boleh_edit_transaksi(disetujui, "Budi (budi)") is False
        assert boleh_edit_transaksi(draft, "Lain (lain)") is False
        assert boleh_hapus_transaksi(draft, "Lain (lain)") is False
        # PPTK boleh ajukan ulang Ditolak miliknya.
        assert boleh_ajukan_ulang(ditolak, "Budi (budi)") is True
        assert boleh_ajukan_ulang(draft, "Budi (budi)") is False
        assert boleh_ajukan_ulang(ditolak, "Lain (lain)") is False

    def test_update_transaksi_status_alasan(self, monkeypatch):
        sys.path.insert(0, str(ROOT))
        from app_pages import helpers

        df = pd.DataFrame([
            {
                "NO": 1, "STATUS": "Draft", "DISETUJUI_OLEH": "",
                "TANGGAL_APPROVAL": "", "ALASAN_PENOLAKAN": "",
                "PPTK": "Budi (budi)", "NOMINAL": 1000, "URAIAN": "x",
            }
        ])

        calls = []

        def fake_load(ws):
            if ws == "TRANSAKSI":
                return df.copy()
            return pd.DataFrame()

        def fake_update(ws, data):
            calls.append(data.copy())
            return True

        monkeypatch.setattr(helpers, "load_sheet", fake_load)
        monkeypatch.setattr(helpers, "update_sheet_data", fake_update)

        def transaksi_df(calls):
            hasil = None
            for c in calls:
                if "NO" in c.columns:
                    hasil = c
            return hasil

        # Tolak dengan alasan.
        ok = helpers.update_transaksi_status(1, "Ditolak", "Manajer", alasan="Terlalu besar")
        assert ok is True
        saved = transaksi_df(calls)
        row = saved[saved["NO"].astype(str) == "1"].iloc[0]
        assert row["STATUS"] == "Ditolak"
        assert row["ALASAN_PENOLAKAN"] == "Terlalu besar"

        # Setujui → alasan dikosongkan.
        ok = helpers.update_transaksi_status(1, "Disetujui", "Manajer")
        assert ok is True
        saved = transaksi_df(calls)
        row = saved[saved["NO"].astype(str) == "1"].iloc[0]
        assert row["STATUS"] == "Disetujui"
        assert row["ALASAN_PENOLAKAN"] == ""

    def test_edit_transaksi_pptk_guard(self, monkeypatch):
        sys.path.insert(0, str(ROOT))
        from app_pages import helpers

        df = pd.DataFrame([
            {
                "NO": 1, "STATUS": "Draft", "DISETUJUI_OLEH": "",
                "TANGGAL_APPROVAL": "", "ALASAN_PENOLAKAN": "",
                "PPTK": "Budi (budi)", "NOMINAL": 1000, "URAIAN": "lama",
            },
            {
                "NO": 2, "STATUS": "Disetujui", "DISETUJUI_OLEH": "Manajer",
                "TANGGAL_APPROVAL": "01/01/2027", "ALASAN_PENOLAKAN": "",
                "PPTK": "Budi (budi)", "NOMINAL": 2000, "URAIAN": "sudah setuju",
            },
        ])

        calls = []

        def fake_load(ws):
            if ws == "TRANSAKSI":
                return df.copy()
            return pd.DataFrame()

        def fake_update(ws, data):
            calls.append(data.copy())
            return True

        monkeypatch.setattr(helpers, "load_sheet", fake_load)
        monkeypatch.setattr(helpers, "update_sheet_data", fake_update)

        def transaksi_df(calls):
            hasil = None
            for c in calls:
                if "NO" in c.columns:
                    hasil = c
            return hasil

        # Edit Draft milik sendiri berhasil.
        ok = helpers.edit_transaksi_pptk(
            1, "SK001 - Kegiatan A", "5.2.1.01", "", "uraian baru",
            "UP/GU", 1500, "", "Budi", "Budi (budi)",
        )
        assert ok is True
        saved = transaksi_df(calls)
        row = saved[saved["NO"].astype(str) == "1"].iloc[0]
        assert row["URAIAN"] == "uraian baru"
        assert row["NOMINAL"] == 1500

        # Tidak boleh edit yang sudah Disetujui.
        ok = helpers.edit_transaksi_pptk(
            2, "SK001 - Kegiatan A", "5.2.1.01", "", "x",
            "UP/GU", 100, "", "Budi", "Budi (budi)",
        )
        assert ok is False

    def test_delete_transaksi_pptk_draft_ditolak(self, monkeypatch):
        sys.path.insert(0, str(ROOT))
        from app_pages import helpers

        df = pd.DataFrame([
            {
                "NO": 1, "STATUS": "Draft", "DISETUJUI_OLEH": "",
                "TANGGAL_APPROVAL": "", "ALASAN_PENOLAKAN": "",
                "PPTK": "Budi (budi)", "NOMINAL": 1000, "URAIAN": "draft lama",
            },
            {
                "NO": 2, "STATUS": "Ditolak", "DISETUJUI_OLEH": "Manajer",
                "TANGGAL_APPROVAL": "", "ALASAN_PENOLAKAN": "Terlalu besar",
                "PPTK": "Budi (budi)", "NOMINAL": 2000, "URAIAN": "ditolak",
            },
            {
                "NO": 3, "STATUS": "Disetujui", "DISETUJUI_OLEH": "Manajer",
                "TANGGAL_APPROVAL": "01/01/2027", "ALASAN_PENOLAKAN": "",
                "PPTK": "Budi (budi)", "NOMINAL": 3000, "URAIAN": "disetujui",
            },
        ])

        transaksi_calls = []
        arsip_calls = []

        def fake_load(ws):
            if ws == "TRANSAKSI":
                return df.copy()
            if ws == "TRANSAKSI DIHAPUS":
                return pd.DataFrame()
            return pd.DataFrame()

        def fake_update(ws, data):
            if ws == "TRANSAKSI DIHAPUS":
                arsip_calls.append(data.copy())
            elif ws == "TRANSAKSI":
                transaksi_calls.append(data.copy())
            return True

        monkeypatch.setattr(helpers, "load_sheet", fake_load)
        monkeypatch.setattr(helpers, "update_sheet_data", fake_update)

        # boleh_hapus_transaksi: Draft dan Ditolak boleh, Disetujui tidak.
        assert helpers.boleh_hapus_transaksi(
            pd.Series({"PPTK": "Budi (budi)", "STATUS": "Draft"}), "Budi (budi)"
        ) is True
        assert helpers.boleh_hapus_transaksi(
            pd.Series({"PPTK": "Budi (budi)", "STATUS": "Ditolak"}), "Budi (budi)"
        ) is True
        assert helpers.boleh_hapus_transaksi(
            pd.Series({"PPTK": "Budi (budi)", "STATUS": "Disetujui"}), "Budi (budi)"
        ) is False

        # Hapus Draft (NO=1): pindah ke arsip dan hilang dari TRANSAKSI.
        ok = helpers.delete_transaksi_pptk(1, "Budi", "Budi (budi)")
        assert ok is True
        assert any(len(c) == 1 for c in arsip_calls), "baris harus dipindah ke TRANSAKSI DIHAPUS"
        arsip_df = arsip_calls[-1]
        assert "TANGGAL_HAPUS" in arsip_df.columns, "kolom TANGGAL_HAPUS harus ada di TRANSAKSI DIHAPUS"
        assert arsip_df["TANGGAL_HAPUS"].iloc[0].count(":") == 2, "TANGGAL_HAPUS harus format hh:mm:ss"
        saved = transaksi_calls[-1]
        assert "1" not in saved["NO"].astype(str).tolist(), "NO 1 harus hilang dari TRANSAKSI"

        # Hapus Ditolak (NO=2): juga boleh.
        ok = helpers.delete_transaksi_pptk(2, "Budi", "Budi (budi)")
        assert ok is True
        saved = transaksi_calls[-1]
        assert "2" not in saved["NO"].astype(str).tolist(), "NO 2 harus hilang dari TRANSAKSI"

        # Tidak boleh hapus Disetujui (NO=3).
        ok = helpers.delete_transaksi_pptk(3, "Budi", "Budi (budi)")
        assert ok is False

    def test_append_transaksi_tanggal_format(self, monkeypatch):
        sys.path.insert(0, str(ROOT))
        from app_pages import helpers

        df = pd.DataFrame(columns=[
            "NO", "SUB KEGIATAN", "KODE REKENING BELANJA",
            "PENGELOMPOKAN BELANJA (#)", "URAIAN",
            "JENIS TRANSAKSI (UP/GU/LS)", "NOMINAL",
            "TANGGAL PENGAJUAN", "BUKTI DUKUNG SPJ", "PPTK", "STATUS",
            "DISETUJUI_OLEH", "TANGGAL_APPROVAL", "ALASAN_PENOLAKAN",
        ])

        calls = []

        def fake_load(ws):
            if ws == "TRANSAKSI":
                return df.copy()
            return pd.DataFrame()

        def fake_update(ws, data):
            if ws == "TRANSAKSI":
                calls.append(data.copy())
            return True

        monkeypatch.setattr(helpers, "load_sheet", fake_load)
        monkeypatch.setattr(helpers, "update_sheet_data", fake_update)

        new_data = {
            "SUB KEGIATAN": "SK001 - Kegiatan A",
            "KODE REKENING BELANJA": "5.2.1.01",
            "PENGELOMPOKAN BELANJA (#)": "",
            "URAIAN": "Test",
            "JENIS TRANSAKSI (UP/GU/LS)": "UP/GU",
            "NOMINAL": 1000,
            "TANGGAL PENGAJUAN": "29/10/2026 14:30:00",
            "BUKTI DUKUNG SPJ": "",
            "PPTK": "Budi (budi)",
        }
        ok, no = helpers.append_transaksi(new_data, user="Budi")
        assert ok is True
        saved = calls[-1]
        row = saved[saved["NO"].astype(str) == str(no)].iloc[0]
        tgl = str(row["TANGGAL PENGAJUAN"])
        assert tgl.count(":") == 2, f"TANGGAL PENGAJUAN harus format hh:mm:ss, dapat: {tgl}"

    def test_update_master_subkegiatan_perubahan_pagu(self, monkeypatch):
        sys.path.insert(0, str(ROOT))
        from app_pages import helpers

        df = pd.DataFrame([
            {
                "Kode Sub Kegiatan": "SK001",
                "Sub Kegiatan": "Kegiatan A",
                "Pagu Awal": 10000000,
                "Perubahan Pagu": 0,
                "Pagu Akhir": 10000000,
                "Sisa Pagu": "",
            },
        ])

        cell_updates = []

        def fake_load(ws):
            if ws == "MASTER_SUB_KEGIATAN":
                return df.copy()
            return pd.DataFrame()

        class FakeWorksheet:
            def update_cell(self, row, col, value):
                cell_updates.append({"row": row, "col": col, "value": value})

        monkeypatch.setattr(helpers, "load_sheet", fake_load)
        monkeypatch.setattr(
            helpers, "_get_gspread_worksheet", lambda ws: FakeWorksheet()
        )

        # Perubahan pagu positif (penambahan).
        ok = helpers.update_master_subkegiatan_perubahan_pagu("SK001", 2000000, user="Kasubag")
        assert ok is True
        # Perubahan Pagu ada di kolom D (index 4, 1-based), baris SK001 = baris 2 di sheet
        assert len(cell_updates) == 1
        assert cell_updates[0]["row"] == 2, f"Baris harus 2, dapat {cell_updates[0]['row']}"
        assert cell_updates[0]["col"] == 4, f"Kolom harus 4 (Perubahan Pagu), dapat {cell_updates[0]['col']}"
        assert cell_updates[0]["value"] == 2000000, f"Perubahan Pagu harus 2000000, dapat {cell_updates[0]['value']}"

        # Perubahan pagu negatif (pengurangan).
        cell_updates.clear()
        ok = helpers.update_master_subkegiatan_perubahan_pagu("SK001", -500000, user="Kasubag")
        assert ok is True
        assert len(cell_updates) == 1
        assert cell_updates[0]["value"] == -500000, f"Perubahan Pagu harus -500000, dapat {cell_updates[0]['value']}"

    def test_ajukan_ulang_transaksi(self, monkeypatch):
        sys.path.insert(0, str(ROOT))
        from app_pages import helpers

        df = pd.DataFrame([
            {
                "NO": 1, "STATUS": "Ditolak", "DISETUJUI_OLEH": "Manajer",
                "TANGGAL_APPROVAL": "01/01/2027", "ALASAN_PENOLAKAN": "Terlalu besar",
                "PPTK": "Budi (budi)", "NOMINAL": 1000, "URAIAN": "lama",
                "SUB KEGIATAN": "SK001 - Kegiatan A",
                "KODE REKENING BELANJA": "5.2.1.01",
                "PENGELOMPOKAN BELANJA (#)": "",
                "JENIS TRANSAKSI (UP/GU/LS)": "UP/GU",
                "TANGGAL PENGAJUAN": "01/01/2027",
                "BUKTI DUKUNG SPJ": "",
            },
            {
                "NO": 2, "STATUS": "Draft", "DISETUJUI_OLEH": "",
                "TANGGAL_APPROVAL": "", "ALASAN_PENOLAKAN": "",
                "PPTK": "Lain (lain)", "NOMINAL": 500, "URAIAN": "x",
            },
        ])

        calls = []

        def fake_load(ws):
            if ws == "TRANSAKSI":
                return df.copy()
            return pd.DataFrame()

        def fake_update(ws, data):
            calls.append(data.copy())
            return True

        def transaksi_df(calls):
            hasil = None
            for c in calls:
                if "NO" in c.columns:
                    hasil = c
            return hasil

        monkeypatch.setattr(helpers, "load_sheet", fake_load)
        monkeypatch.setattr(helpers, "update_sheet_data", fake_update)

        ok, new_no = helpers.ajukan_ulang_transaksi(
            1, "uraian diperbaiki", 1200, "Budi", "Budi (budi)"
        )
        assert ok is True
        assert new_no == 3  # NO baru (max 2 + 1)
        saved = transaksi_df(calls)
        baris_baru = saved[saved["NO"].astype(str) == str(new_no)].iloc[0]
        assert baris_baru["STATUS"] == "Draft"
        assert baris_baru["URAIAN"] == "uraian diperbaiki"
        assert baris_baru["NOMINAL"] == 1200
        assert baris_baru["DISETUJUI_OLEH"] == ""
        assert baris_baru["ALASAN_PENOLAKAN"] == ""

        # Tidak boleh ajukan ulang Draft.
        ok, new_no = helpers.ajukan_ulang_transaksi(2, "x", 100, "Lain", "Lain (lain)")
        assert ok is False

    def test_login_page_no_exception(self):
        at = AppTest.from_file(ROOT / "app_pages/login.py").run(timeout=60)
        assert not at.exception, f"Login page error: {at.exception}"
