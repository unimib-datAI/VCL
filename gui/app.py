import streamlit as st

from copy import deepcopy
from tomlkit import value
from typing import Dict, Callable

from gui.pages_content.AdminPage import show_admin
from gui.pages_content.Login import show_login
# from gui.pages_content.Registration import show_registration
from gui.pages_content.Home import show_home
from gui.pages_content.Settings import show_settings
from gui.pages_content.Documents import show_documents
from gui.pages_content.Info import show_info
from gui.pages_content.QuestionsTracking import show_questions_tracking

from utils.config import Config

MODEL_LABELS = {
    "DQL": "DQL",
    "GPT": "GPT",
    "NotebookLM": "NotebookLM",
    "BattleAnon": "Battle (anonimo)",
    "BattleLabeled": "Battle (etichettato)",
}
DEFAULT_MODEL = "DQL"

# --- Configuration ---
st.set_page_config(page_title="DQL", layout="wide")

PAGE_MAP: Dict[str, Callable] = {
    "Login": show_login,
    "Admin": show_admin,
    # "Registration": show_registration,
    "Home": show_home,
    "Settings": show_settings,
    "Documents": show_documents,
    "Info": show_info,
    "QuestionTracking" : show_questions_tracking,
}

# --- Session Management Helpers ---

def _init_session_state() -> None:
    """
    Initializes the necessary session state variables if they are missing.
    """
    if "page" not in st.query_params:
        st.query_params["page"] = "Login"
        
    if "config" not in st.session_state or "storage" not in st.session_state or "language" not in st.session_state:
        st.session_state.config = Config.get_instance()
        st.session_state.storage = st.session_state.config.get_storage()
        
    # Initialize default auth keys
    defaults = {
        "auth_status": False,
        "chat_models": {}
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Clean query params if not authenticated
    if not st.session_state.auth_status and "chat" in st.query_params:
        del st.query_params.chat

def _handle_logout() -> None:
    """
    Resets session state and redirects to Login.
    """
    st.session_state.config.handle_logout()
    
    st.session_state.clear()
    st.query_params.clear()

    _init_session_state()
    
    st.rerun()

def _infer_chat_model(messages) -> str:
    """
    Prova a determinare il modello usato in una chat
    guardando l'ultimo messaggio dell'assistente che contiene 'model'.
    Se non trova nulla, torna DEFAULT_MODEL.
    """
    if not messages:
        return DEFAULT_MODEL

    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("model"):
            return msg["model"]

    return DEFAULT_MODEL

def _render_sidebar() -> None:
    """
    Renders the sidebar navigation for authenticated users.
    """
    if not st.session_state.auth_status:
        return

    with st.sidebar:
        st.write(f"👋 Benvenuto *{st.session_state['username']}*")
            
        st.divider()
        
        # Chat History List
        chats = st.session_state.storage.get_all_chats(st.session_state.username) or {}
        # Sort keys in reverse order (assuming timestamps or incremental IDs)
        sorted_keys = sorted(chats.keys(), reverse=True)

        for index, chat_id in enumerate(sorted_keys):
            # Display logic: Chat 1, Chat 2 based on chronological order reversed
            display_index = str(len(sorted_keys) - index)

            messages = chats.get(chat_id, [])

            # 1) Se abbiamo già un modello salvato per questa chat, usiamo quello
            model_key = st.session_state.chat_models.get(chat_id)

            # 2) Altrimenti lo inferiamo dai messaggi e lo cache-iamo
            if not model_key:
                model_key = _infer_chat_model(messages)
                st.session_state.chat_models[chat_id] = model_key

            model_label = MODEL_LABELS.get(model_key, model_key)
            label = f"💬 Chat {display_index} ({model_label})"

            if st.button(label, key=f"nav_{chat_id}", width='stretch'):
                # Cambiamo chat
                st.query_params["chat"] = st.session_state.config.set_chat_id(chat_id)

                # Allineiamo il modello nello stato di Home
                st.session_state.selected_model = model_key
                st.session_state.model_selector = model_key
                st.session_state.last_model_for_chat = model_key

                change_page("Home")

                st.rerun()

        st.divider()
        
        # Documents
        if st.button("📁 Visualizza Documenti", width='stretch'):
            change_page("Documents")
                
        # Informazioni Linguaggio
        if st.button("ℹ️ Informazioni Linguaggio", width='stretch'):
            change_page("Info")

        # Tracking domande utente
        if st.button("ℹ️ Tracking Domande", width='stretch'):
            change_page("QuestionTracking")
        
        # Settings
        if st.button("⚙️ Impostazioni", width='stretch'):
            change_page("Settings")
                
        # Admin Page (only for admins)
        if st.session_state.role == "Admin":
            if st.button("🛠️ Admin Dashboard", width='stretch'):
                change_page("Admin")

        # Logout
        if st.button("🟥 Logout", width='stretch'):
            _handle_logout()
            
# --- Change Page Function --- #
def change_page(dest_page):
    if st.query_params.get("page") != dest_page:
        st.query_params["page"] = dest_page
        st.rerun()

# --- Main Logic ---

_init_session_state()

# Security Check: Redirect unauthenticated users to Login/Registration
current_page = st.query_params["page"]
is_auth_page = current_page in ["Login"] #, "Registration"]

if st.session_state.auth_status:
    if (not st.session_state.username) or (not st.session_state.role):
        st.session_state.auth_status = False
        st.rerun()
    
    # Create a new chat and redirect
    st.query_params.chat = st.session_state.config.get_chat_id()
    st.session_state.language = st.session_state.config.get_DQL()
    
    _render_sidebar()
    # If authenticated user tries to access Login/Registration, redirect to Home
    if is_auth_page:
        st.query_params["page"] = "Home"
        st.rerun()
else:
    # If unauthenticated user tries to access protected pages, redirect to Login
    if not is_auth_page:
        _handle_logout() # Clean reset

# Page Routing
page_to_show = PAGE_MAP.get(st.query_params["page"], show_login)
page_to_show()