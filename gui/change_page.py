import streamlit as st
from utils.config import Config

def change_page(name, or_page=[]):
    """
    Gestisce il cambio pagina e l'inizializzazione del logic_config.
    'name' è la pagina di destinazione/desiderata.
    'or_page' è una lista di pagine alternative consentite (per i redirect).
    """
    
    # Ottieni la pagina corrente, con un default sicuro
    current_page = st.query_params.get("page", "Login")
    
    # 1. Gestione Redirect
    # Se la pagina corrente non è la destinazione e non è nelle eccezioni,
    # imposta la pagina di destinazione.
    if not (current_page == name or current_page in or_page):
        st.query_params["page"] = name
        current_page = name  # Aggiorna la pagina corrente per la logica sottostante
    
    # 2. Gestione logic_config (FIX)
    # Questa logica ora viene eseguita indipendentemente dal redirect,
    # assicurando che logic_config sia inizializzato se ci si trova
    # su Home o Settings.
    
    if current_page in ["Home", "Settings"]:
        username = st.session_state.get('username')
        
        # Inizializza solo se necessario (mancante o utente diverso)
        if username and (st.session_state.logic_config is None or 
                         st.session_state.logic_config.user_id != username):
            try:
                st.session_state.logic_config = Config(username)
            except Exception as e:
                st.error(f"Errore nell'inizializzazione della configurazione utente: {e}")
                st.session_state.logic_config = None
        elif not username:
            # Assicura che logic_config sia None se l'username non è disponibile
            st.session_state.logic_config = None
    else:
        # Pulisce logic_config per pagine non protette (Login, Registration)
        st.session_state.logic_config = None