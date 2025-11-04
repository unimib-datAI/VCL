import streamlit as st

from gui.change_page import change_page

def show_login():
    st.title("Login Utente")

    try:
        st.session_state.authenticator.login()
    except Exception as e:
        st.error(f"Errore durante il login: {e}")

    st.markdown("---")

    if st.button("Non hai ancora un account? Registrati!", use_container_width=True):
        change_page("Registration")
