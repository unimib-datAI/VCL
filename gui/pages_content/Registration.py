import streamlit as st
import re

from utils.config import Config

PAGE_TITLE = "Benvenuto in DQL!"

EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
PASSWORD_PATTERN = r'^(?=(.*[a-z]){1,})(?=(.*[A-Z]){1,})(?=(.*[0-9]){1,})(?=(.*[!@#$%^&*()\-__+.]){1,}).{8,}$'

def show_registration():
    st.title(PAGE_TITLE)
    
    with st.form("Registrati"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Registrati"):
            username = username.strip()
            email = email.strip()
            password = password.strip()
             
            if re.fullmatch(EMAIL_PATTERN, email):
                if re.match(PASSWORD_PATTERN, password):
                    if st.session_state.authenticator.register_user(username, email, password):
                        st.success("Registrazione avvenuta con successo!")
                        
                        st.session_state.username = username
                        st.session_state.auth_status = True
                        st.session_state.logic_config = Config(username)
                        
                        st.query_params["page"] = "Home"
                        st.rerun()
                    else:
                        st.error("Username/Email non disponibili")
                else:
                    st.error("La password deve avere almeno 8 caratteri, con 1 minuscola, 1 maiuscola, 1 numero e 1 simbolo speciale (!@#$%^&*()-_+.)")
            else:
                st.error("Formato Email non valido")
    
    st.markdown("---")

    if st.button("Hai già un account? Effettua il login!", use_container_width=True):
        st.query_params["page"] = "Login"
        st.rerun()