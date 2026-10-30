"""
Halaman Master Data — CRUD Wilayah, Sub Kegiatan, Rekening, Pengguna, dan Audit Log.
Hanya untuk ADMIN.

Perbaikan 10.4 Temuan: edit/hapus hadir untuk Wilayah, Sub Kegiatan, dan Pengguna
(dahulu hanya Rekening), setiap edit/hapus dilengkaki preview baris + konfirmasi
agar tidak mengandalkan indeks baris mentah.
Perbaikan 10.5 Temuan: kolom Password tidak ditampilkan di tabel dan password
baru disimpan sebagai hash (verify_password terima hash atau plaintext legacy).
"""

import streamlit as st
import pandas as pd

from app_pages import helpers  # noqa: E402

current_user = st.session_state.get("current_user") or {}
user_nama = current_user.get("Nama", "Sistem")
user_peran = str(current_user.get("Peran", "")).upper()

if user_peran != "ADMIN":
    st.warning("Menu ini hanya untuk ADMIN.")
    st.stop()

# Muat master data (cached)
df_wilayah = helpers.load_sheet("MASTER_WILAYAH")
df_kegiatan = helpers.load_sheet("MASTER_SUB_KEGIATAN")
df_rekening = helpers.load_sheet("MASTER_REKENING")
df_pengguna = helpers.load_sheet("PENGGUNA")

st.header("Master data")
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Wilayah", "Sub Kegiatan", "Rekening", "Pengguna", "Audit Log"],
    on_change="rerun",
)


def preview_row(df: pd.DataFrame, idx: int, label: str) -> None:
    """Tampilkan preview isi baris pada indeks idx, bila valid."""
    if df is not None and not df.empty and 0 <= idx < len(df):
        row = df.iloc[idx]
        parts = " | ".join(f"{c}: {row.get(c, '-')}" for c in df.columns)
        st.caption(f"Preview baris {idx} ({label}): {parts}")


def edit_delete_block(
    *,
    df: pd.DataFrame,
    key_prefix: str,
    edit_fn,
    delete_fn,
    fields: dict,  # {nama_field: (label, widget, kwargs)}
    id_column: str,
    key_for_idx: str,
    user: str,
    in_form: bool = True,
) -> None:
    """Blok Edit / Hapus generik dengan preview dan konfirmasi (10.4 Temuan).

    ``in_form=False`` dipakai bila blok ini dirender di dalam container biasa
    (bukan ``st.form``), sehingga tombol memakai ``st.button`` dan perubahan
    widget langsung memicu rerun (mis. caption nominal ter-update live).
    """

    def _submit(label: str, kind: str, key: str) -> bool:
        if in_form:
            return st.form_submit_button(label, type=kind, key=key)
        return st.button(label, type=kind, key=key)

    st.divider()
    st.markdown(f"**Edit / Hapus {key_prefix.title()}**")
    idx = st.number_input(
        "Indeks Baris", min_value=0, step=1, key=f"{key_prefix}_idx"
    )
    if not df.empty:
        valid = 0 <= int(idx) < len(df)
        if valid:
            preview_row(df, int(idx), key_prefix)
        else:
            st.error(f"Indeks baris tidak valid (0 hingga {len(df) - 1}).")

    values = {}
    for field, (label, widget, kwargs) in fields.items():
        default = ""
        if not df.empty and 0 <= int(idx) < len(df):
            default = str(df.iloc[int(idx)].get(field, ""))
        if widget == "text":
            values[field] = st.text_input(
                label, value=default, key=f"{key_prefix}_{field}", **kwargs
            )
        elif widget == "number":
            values[field] = st.number_input(
                label,
                value=float(default) if default else 0.0,
                key=f"{key_prefix}_{field}",
                **kwargs,
            )
            st.caption(f"Nilai terbaca: {helpers.format_rupiah(values[field])}")
        elif widget == "select":
            values[field] = st.selectbox(label, kwargs.get("options", []), key=f"{key_prefix}_{field}")

    konfirmasi = st.checkbox(
        "Saya yakin ingin menyimpan/menghapus baris ini.", key=f"{key_prefix}_conf"
    )
    col_simpan, col_hapus = st.columns(2)
    with col_simpan:
        if _submit("Simpan Perubahan", "primary", f"{key_prefix}_save"):
            if not konfirmasi:
                st.error("Centang konfirmasi terlebih dahulu.")
            elif not df.empty and 0 <= int(idx) < len(df):
                old_id = str(df.iloc[int(idx)].get(id_column, idx))
                if edit_fn(int(idx), user=user, **values):
                    st.success(f"{key_prefix.title()} baris {old_id} berhasil diupdate.")
                    # Reset form edit ke state awal
                    reset_keys = [f"{key_prefix}_idx", f"{key_prefix}_conf"]
                    for field in fields:
                        reset_keys.append(f"{key_prefix}_{field}")
                    helpers.reset_form_keys(*reset_keys)
                    st.rerun()
                else:
                    st.error(f"Gagal mengupdate {key_prefix.lower()}.")
            else:
                st.error("Indeks baris tidak valid.")
    with col_hapus:
        if _submit("Hapus", "secondary", f"{key_prefix}_delete"):
            if not konfirmasi:
                st.error("Centang konfirmasi terlebih dahulu.")
            elif not df.empty and 0 <= int(idx) < len(df):
                old_id = str(df.iloc[int(idx)].get(id_column, idx))
                if delete_fn(int(idx), user=user):
                    st.success(f"{key_prefix.title()} baris {old_id} berhasil dihapus.")
                    # Reset form hapus ke state awal
                    reset_keys = [f"{key_prefix}_idx", f"{key_prefix}_conf"]
                    for field in fields:
                        reset_keys.append(f"{key_prefix}_{field}")
                    helpers.reset_form_keys(*reset_keys)
                    st.rerun()
                else:
                    st.error(f"Gagal menghapus {key_prefix.lower()}.")
            else:
                st.error("Indeks baris tidak valid.")


# ---------- Tab Wilayah ----------
if tab1.open:
    with tab1:
        st.subheader("Data wilayah")
        if not df_wilayah.empty:
            st.dataframe(df_wilayah, hide_index=True, width="stretch")
            with st.form("form_wilayah", border=True):
                col_add, col_ed = st.columns([1, 1])
                with col_add:
                    st.markdown("**Tambah Wilayah**")
                    w_nama = st.text_input("Nama Wilayah", key="w_nama")
                    w_kode = st.text_input("Kode Wilayah", key="w_kode")
                    if st.form_submit_button("Simpan Wilayah", type="primary"):
                        if helpers.add_master_wilayah(
                            w_nama, w_kode, user=user_nama
                        ):
                            st.success("Wilayah berhasil ditambahkan.")
                            helpers.reset_form_keys("w_nama", "w_kode")
                            st.rerun()
                        else:
                            st.error("Gagal menambahkan wilayah.")
                with col_ed:
                    edit_delete_block(
                        df=df_wilayah,
                        key_prefix="wilayah",
                        edit_fn=helpers.edit_master_wilayah,
                        delete_fn=helpers.delete_master_wilayah,
                        fields={
                            "Nama Wilayah": ("Nama Wilayah Baru", "text", {}),
                            "Kode Wilayah": ("Kode Wilayah Baru", "text", {}),
                        },
                        id_column="Kode Wilayah",
                        key_for_idx="w_idx",
                        user=user_nama,
                    )
        else:
            st.info("Belum ada data wilayah.")

# ---------- Tab Sub Kegiatan ----------
if tab2.open:
    with tab2:
        st.subheader("Data sub kegiatan")
        if not df_kegiatan.empty:
            st.dataframe(
                helpers.format_df_rupiah(df_kegiatan),
                hide_index=True,
                width="stretch",
            )
            with st.container(border=True):
                col_add, col_ed = st.columns([1, 1])
                with col_add:
                    st.markdown("**Tambah Sub Kegiatan**")
                    k_sub = st.text_input("Kode Sub Kegiatan", key="k_sub")
                    k_nama = st.text_input("Nama Kegiatan", key="k_nama")
                    k_pagu = st.number_input(
                        "Pagu Awal (Rp)",
                        min_value=0.0,
                        step=1000000.0,
                        format="%.2f",
                        key="k_pagu",
                    )
                    st.caption(f"Nilai terbaca: {helpers.format_rupiah(k_pagu)}")
                    if st.button("Simpan Kegiatan", type="primary", key="btn_simpan_kegiatan"):
                        if helpers.add_master_kegiatan(
                            k_sub, k_nama, k_pagu, user=user_nama
                        ):
                            st.success("Sub kegiatan berhasil ditambahkan.")
                            helpers.reset_form_keys("k_sub", "k_nama", "k_pagu")
                            st.rerun()
                        else:
                            st.error("Gagal menambahkan sub kegiatan.")
                with col_ed:
                    edit_delete_block(
                        df=df_kegiatan,
                        key_prefix="kegiatan",
                        edit_fn=helpers.edit_master_kegiatan,
                        delete_fn=helpers.delete_master_kegiatan,
                        fields={
                            "Kode Sub Kegiatan": ("Kode Sub Kegiatan Baru", "text", {}),
                            "Sub Kegiatan": ("Nama Kegiatan Baru", "text", {}),
                            "Pagu Awal": ("Pagu Awal Baru (Rp)", "number", {"min_value": 0.0, "step": 1000000.0, "format": "%.2f"}),
                        },
                        id_column="Kode Sub Kegiatan",
                        key_for_idx="k_idx",
                        user=user_nama,
                        in_form=False,
                    )
        else:
            st.info("Belum ada data sub kegiatan.")

# ---------- Tab Rekening ----------
if tab3.open:
    with tab3:
        st.subheader("Data rekening belanja")
        if not df_rekening.empty:
            st.dataframe(df_rekening, hide_index=True, width="stretch")
            with st.form("form_rekening", border=True):
                col_add, col_ed = st.columns([1, 1])
                with col_add:
                    st.markdown("**Tambah Rekening**")
                    r_kode = st.text_input("Kode Rekening", key="r_kode")
                    r_uraian = st.text_input("Uraian Rekening", key="r_uraian")
                    if st.form_submit_button("Simpan Rekening", type="primary"):
                        if helpers.add_master_rekening(
                            r_kode, r_uraian, user=user_nama
                        ):
                            st.success("Rekening berhasil ditambahkan.")
                            helpers.reset_form_keys("r_kode", "r_uraian")
                            st.rerun()
                        else:
                            st.error("Gagal menambahkan rekening.")
                with col_ed:
                    edit_delete_block(
                        df=df_rekening,
                        key_prefix="rekening",
                        edit_fn=helpers.edit_master_rekening,
                        delete_fn=helpers.delete_master_rekening,
                        fields={
                            "Kode Rekening": ("Kode Rekening Baru", "text", {}),
                            "Uraian Rekening": ("Uraian Rekening Baru", "text", {}),
                        },
                        id_column="Kode Rekening",
                        key_for_idx="r_idx",
                        user=user_nama,
                    )
        else:
            st.info("Belum ada data rekening.")

# ---------- Tab Pengguna ----------
if tab4.open:
    with tab4:
        st.subheader("Data pengguna")
        if not df_pengguna.empty:
            # Kolom Password disembunyikan dari tampilan (10.5 Temuan).
            df_pengguna_display = df_pengguna.drop(
                columns=["Password"], errors="ignore"
            )
            st.dataframe(df_pengguna_display, hide_index=True, width="stretch")
            with st.form("form_user", border=True):
                col_add, col_ed = st.columns([1, 1])
                with col_add:
                    st.markdown("**Tambah Pengguna**")
                    u_user = st.text_input("User Name", key="u_user")
                    u_pass = st.text_input("Password", type="password", key="u_pass")
                    u_nama = st.text_input("Nama Lengkap", key="u_nama")
                    u_peran = st.selectbox(
                        "Peran", ["ADMIN", "KASUBAG_PEK", "PPTK"], key="u_peran"
                    )
                    if st.form_submit_button("Simpan Pengguna", type="primary"):
                        if not u_pass:
                            st.error("Password tidak boleh kosong.")
                        elif helpers.add_master_user(
                            u_user,
                            helpers.hash_password(u_pass),
                            u_nama,
                            u_peran,
                            user=user_nama,
                        ):
                            st.success("Pengguna berhasil ditambahkan.")
                            helpers.reset_form_keys("u_user", "u_pass", "u_nama", "u_peran")
                            st.rerun()
                        else:
                            st.error("Gagal menambahkan pengguna.")
                with col_ed:
                    edit_delete_block(
                        df=df_pengguna,
                        key_prefix="user",
                        edit_fn=helpers.edit_master_user,
                        delete_fn=helpers.delete_master_user,
                        fields={
                            "User Name": ("User Name Baru", "text", {}),
                            "Password": ("Password Baru (kosongkan jika tidak diubah)", "text", {"type": "password"}),
                            "Nama": ("Nama Lengkap Baru", "text", {}),
                            "Peran": ("Peran Baru", "select", {"options": ["ADMIN", "KASUBAG_PEK", "PPTK"]}),
                        },
                        id_column="User Name",
                        key_for_idx="u_idx",
                        user=user_nama,
                    )
        else:
            st.info("Belum ada data pengguna.")

# ---------- Tab Audit Log ----------
if tab5.open:
    with tab5:
        st.subheader("Audit log — riwayat perubahan data")
        df_audit = helpers.load_sheet("AUDIT_LOG")
        if not df_audit.empty:
            df_audit = df_audit.sort_values("WAKTU", ascending=False)
            st.dataframe(df_audit, hide_index=True, width="stretch")
            st.divider()
            if st.button("Refresh Audit Log", key="btn_refresh_audit"):
                helpers.load_sheet.clear()
                st.rerun()
        else:
            st.info("Belum ada riwayat audit log.")
