import streamlit as st
from logic.orchestrator import Orchestrator

PAGE_TITLE = "Benvenuto in DQL!"

def _initialize_user_session(user: dict):
    """
    Sets up the session state after a successful login or registration.
    """
    st.session_state.username = user["username"]
    st.session_state.role = user["role"]
    st.session_state.auth_status = True
    st.session_state.config.handle_login(st.session_state.username, st.session_state.role)
    
    # Create a new chat and redirect
    st.query_params.chat = st.session_state.storage.create_new_chat(st.session_state.username)
    st.query_params["page"] = "Home"
    st.rerun()

def show_login():
    st.title(PAGE_TITLE)

    with st.form("Login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            result, user = st.session_state.storage.login_user(username.strip(), password.strip())
            
            if result and user:
                st.success("Login avvenuto con successo!")
                _initialize_user_session(user)
            else:
                st.error("Username/Password errati")

    # st.markdown("---")

    # if st.button("Non hai ancora un account? Registrati!", width='stretch'):
    #     st.query_params["page"] = "Registration"
    #    st.rerun()