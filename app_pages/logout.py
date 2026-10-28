"""
Halaman logout — hapus state login dan kembali ke halaman masuk.
"""

import streamlit as st

st.title("Keluar")
st.write("Anda akan keluar dari SIMKEU.")

if st.button("Yakin keluar", type="primary"):
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.pop("pptk_filter", None)
    st.rerun()
