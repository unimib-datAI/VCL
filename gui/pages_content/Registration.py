import streamlit as st
import re
from logic.orchestrator import Orchestrator

PAGE_TITLE = "Benvenuto in DQL!"
EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
PASSWORD_PATTERN = r'^(?=(.*[a-z]){1,})(?=(.*[A-Z]){1,})(?=(.*[0-9]){1,})(?=(.*[!@#$%^&*()\-__+.]){1,}).{8,}$'

def _initialize_user_session(user: dict):
    """
    Sets up the session state after a successful login or registration.
    Duplicated from Login to keep modules independent, or could be shared in utils.
    """
    st.session_state.username = user["username"]
    st.session_state.auth_status = True
    st.session_state.assistant = Orchestrator(user["username"], user["role"])
    
    st.query_params.chat = st.session_state.authenticator.create_new_chat(user["username"])
    st.query_params["page"] = "Home"
    st.rerun()

def show_registration():
    st.title(PAGE_TITLE)
    
    with st.form("Registrati"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        role = st.radio(
            "Qual è il tuo ruolo?",
            ["Giudice", "Avvocato", "Altro"]
        )
        
        if st.form_submit_button("Registrati"):
            username = username.strip()
            email = email.strip()
            password = password.strip()
             
            if not re.fullmatch(EMAIL_PATTERN, email):
                st.error("Formato Email non valido")
            elif not re.match(PASSWORD_PATTERN, password):
                st.error("La password deve avere almeno 8 caratteri, con 1 minuscola, 1 maiuscola, 1 numero e 1 simbolo speciale (!@#$%^&*()-_+.)")
            else:
                result, user = st.session_state.authenticator.register_user(username, email, password, role)
                if result and user:
                    st.success("Registrazione avvenuta con successo!")
                    _initialize_user_session(user)
                else:
                    st.error(user)
                    st.error("Username/Email non disponibili")
    
    st.markdown("---")

    if st.button("Hai già un account? Effettua il login!", use_container_width=True):
        st.query_params["page"] = "Login"
        st.rerun()