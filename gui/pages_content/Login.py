import streamlit as st

from utils.config import Config

PAGE_TITLE = "Benvenuto in DQL!"

def show_login():
    st.title(PAGE_TITLE)

    with st.form("Login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            if st.session_state.authenticator.login_user(username.strip(), password.strip()):
                st.success("Login avvenuto con successo!")
                        
                st.session_state.username = username
                st.session_state.auth_status = True
                st.session_state.logic_config = Config(username)
                
                st.query_params["page"] = "Home"
                st.rerun()
            else:
                st.error("Username/Password errati")

    st.markdown("---")

    if st.button("Non hai ancora un account? Registrati!", use_container_width=True):
        st.query_params["page"] = "Registration"
        st.rerun()