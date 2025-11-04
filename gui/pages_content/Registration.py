import streamlit as st
import time

from gui.change_page import change_page

def show_registration():
    st.title("Registra Nuovo Utente")
    try:
        email, user_name, name = st.session_state.authenticator.register_user("main", 
                                                                              pre_authorized=None, 
                                                                              password_hint=False)
        
        if email and user_name and name:
            st.success("Registrazione completata! Ora puoi effettuare il login.")
            
            time.sleep(1)
            
            change_page("Login")    

    except Exception as e:
        st.error(f"Errore durante la registrazione: {e}")
    
    st.markdown("---")

    if st.button("Hai già un account? Effettua il login!", use_container_width=True):
        change_page("Login")
