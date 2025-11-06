import streamlit as st
import time

from gui.change_page import change_page

PAGE_TITLE = "Benvenuto in DQL!"

def show_registration():
    st.title(PAGE_TITLE)
    try:
        (email, 
         user_name, 
         name) = st.session_state.authenticator.register_user("Registra", 
                                                             pre_authorized=None, 
                                                             password_hint=True)
        
        if email and user_name and name:
            st.success("Registrazione completata! Ora puoi effettuare il login.")
            
            # Pause to allow the user to read the message
            time.sleep(1.5)
            
            # Redirect to the Login page
            change_page("Login")
            
            # Force rerun after page change
            st.rerun()

    except Exception as e:
        st.error(f"Errore durante la registrazione: {e}")
    
    st.markdown("---")

    if st.button("Hai già un account? Effettua il login!", use_container_width=True):
        change_page("Login")