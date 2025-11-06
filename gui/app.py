import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

from gui.change_page import change_page

from gui.pages_content.Login import show_login
from gui.pages_content.Registration import show_registration
from gui.pages_content.Home import show_home
from gui.pages_content.Settings import show_settings

# --- Configurazione Pagina ---
# Deve essere chiamata solo una volta, all'inizio.
st.set_page_config(page_title="DQL", layout="wide")

# --- Inizializzazione Session State ---
def initialize_app_state():
    """
    Inizializza tutte le chiavi necessarie nel session_state
    per evitare KeyError, specialmente per 'authentication_status'.
    """
    defaults = {
        "logic_config": None,
        "config": None,
        "authenticator": None,
        "authentication_status": None,
        "name": None,
        "username": None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_app_state()

# --- Caricamento Configurazione ---
if st.session_state.config is None:
    try:
        with open('settings/config.yaml', 'r', encoding='utf-8') as file:
            st.session_state.config = yaml.load(file, Loader=SafeLoader)
    except FileNotFoundError:
        st.error("Errore: File 'config.yaml' non trovato. Assicurati che esista.")
        st.stop()
    except Exception as e:
        st.error(f"Errore during caricamento di 'config.yaml': {e}")
        st.stop()

# --- Inizializzazione Authenticator ---
if st.session_state.authenticator is None:
    try:
        st.session_state.authenticator = stauth.Authenticate(
            st.session_state.config['credentials'],
            st.session_state.config['cookie']['name'],
            st.session_state.config['cookie']['key'],
            st.session_state.config['cookie']['expiry_days']
        )
    except Exception as e:
        st.error(f"Errore durante l'inizializzazione dell'authenticator: {e}")
        st.stop()

# --- Page Routing Map ---
PAGE_MAP = {
    "Login": show_login,
    "Registration": show_registration,
    "Home": show_home,
    "Settings": show_settings,
}

# --- Gestione Pagina Default ---
if "page" not in st.query_params:
    st.query_params["page"] = "Login"

# --- Logica di Autenticazione e Redirect ---
auth_status = st.session_state["authentication_status"]

if auth_status:
    # --- Utente Loggato ---
    try:
        with open("settings/config.yaml", "w", encoding="utf-8") as file:
            yaml.dump(st.session_state.config, file, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        st.warning(f"Impossibile salvare 'config.yaml': {e}")
    
    with st.sidebar:
        st.write(f"Benvenuto *{st.session_state['name']}*")
        
        if st.button("Home"):
            change_page("Home")
        
        if st.button("Settings"):
            change_page("Settings")

        st.session_state.authenticator.logout('Logout', 'main')
    
    # Redirect se l'utente è loggato ma su Login/Registration
    # change_page gestirà anche l'init di logic_config
    change_page("Home", ["Settings", "Home"])

elif auth_status is False:
    # --- Login Fallito ---
    st.error('Username/password non corretti')
    change_page("Login", ["Registration", "Login"])

elif auth_status is None:
    # --- Utente Non Loggato ---
    # Redirect se l'utente non è loggato e cerca di accedere a pagine protette
    change_page("Login", ["Registration", "Login"])

# --- Rendering della Pagina Corrente ---
# st.query_params potrebbe essere stato modificato da change_page
current_page_name = st.query_params["page"]
page_to_show = PAGE_MAP.get(current_page_name, show_login) # Default a Login
page_to_show()