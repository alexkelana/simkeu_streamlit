"""
Halaman Pengajuan Pagu — DINONAKTIFKAN.

Fitur pengajuan perubahan pagu oleh PPTK telah dihapus.
Perubahan pagu hanya dapat dilakukan langsung oleh KASUBAG_PEK
di halaman Manajerial (section "Perubahan Pagu").
Halaman ini tidak tersedia untuk semua role.
"""

import streamlit as st

from app_pages import helpers  # noqa: E402

# Fitur dinonaktifkan untuk semua role.
# Perubahan pagu hanya dapat dilakukan langsung oleh KASUBAG_PEK
# di halaman Manajerial, bukan melalui halaman ini.
st.info("Fitur pengajuan perubahan pagu tidak tersedia.")
st.caption(
    "Perubahan pagu hanya dapat dilakukan langsung oleh KASUBAG_PEK "
    "di halaman Manajerial (section 'Perubahan Pagu')."
)
st.stop()
