import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

from gui.change_page import change_page

from gui.pages_content.Login import show_login
from gui.pages_content.Registration import show_registration
from gui.pages_content.Home import show_home
from gui.pages_content.Settings import show_settings

# --- Configurazione Iniziale ---
st.set_page_config(page_title="DQL", layout="wide")

# --- Caricamento Configurazione YAML ---
if "logic_config" not in st.session_state:
    st.session_state.logic_config = None

if "config" not in st.session_state:
    try:
        with open('settings/config.yaml', 'r', encoding='utf-8') as file:
            st.session_state.config = yaml.load(file, Loader=SafeLoader)
    except FileNotFoundError:
        st.error("Errore: File 'config.yaml' non trovato. Assicurati che esista.")
        st.stop()
    except Exception as e:
        st.error(f"Errore durante il caricamento di 'config.yaml': {e}")
        st.stop()


# --- Inizializzazione Authenticator ---
if "authenticator" not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(
        st.session_state.config['credentials'],
        st.session_state.config['cookie']['name'],
        st.session_state.config['cookie']['key'],
        st.session_state.config['cookie']['expiry_days']
    )

# --- Logica di Navigazione  ---
if "page" not in st.query_params:
    st.query_params["page"] = "Login"

page = st.query_params["page"]

if page == "Login":
    show_login()
elif page == "Registration":
    show_registration()
elif page == "Home":
    show_home()
elif page == "Settings":
    show_settings()

# --- Gestione dello Stato di Autenticazione ---

# `st.session_state["authentication_status"]` è il cuore della sessione.
# Può essere:
# True: Utente loggato (o ricordato tramite cookie)
# False: Login fallito
# None: Utente non ancora loggato

if st.session_state["authentication_status"]:
    # --- AREA PROTETTA (Cosa vede l'utente loggato) ---
    # 🔒 Aggiorna il file YAML con le nuove credenziali
    with open("settings/config.yaml", "w", encoding="utf-8") as file:
        yaml.dump(st.session_state.config, file, default_flow_style=False, allow_unicode=True)
    
    with st.sidebar:
        st.write(f"Benvenuto *{st.session_state['name']}*")
        
        # Recuperiamo il ruolo dal file di configurazione
        # Questo è il campo personalizzato che abbiamo richiesto!
        username_loggato = st.session_state['username']
        
        #ruolo_utente = config['credentials']['usernames'][username_loggato].get('role', 'N/D')
        #st.info(f"**Ruolo:** {ruolo_utente.capitalize()}")
        
        if st.button("Home"):
            change_page("Home")
        
        if st.button("Settings"):
            change_page("Settings")

        st.session_state.authenticator.logout('Logout', 'main')
        
    change_page("Home", ["Settings"])


elif st.session_state["authentication_status"] is False:
    # --- Login Failed ---
    st.error('Username/password non corretti')
    change_page("Login", ["Registration"])

elif st.session_state["authentication_status"] is None:
    # --- User not Logged ---
    change_page("Login", ["Registration"])