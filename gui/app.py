import streamlit as st
from typing import Dict, Callable

from gui.pages_content.Login import show_login
from gui.pages_content.Registration import show_registration
from gui.pages_content.Home import show_home
from gui.pages_content.Settings import show_settings
from gui.pages_content.Documents import show_documents
from gui.pages_content.Info import show_info
from gui.pages_content.QuestionsTracking import show_questions_tracking

from utils.storage import Storage

MODEL_LABELS = {
    "DQL": "DQL",
    "GPT": "GPT",
    "NotebookLM": "NotebookLM",
}

DEFAULT_MODEL = "DQL"


# --- Configuration ---
st.set_page_config(page_title="DQL", layout="wide")

PAGE_MAP: Dict[str, Callable] = {
    "Login": show_login,
    "Registration": show_registration,
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
        
    if "authenticator" not in st.session_state:
        st.session_state.authenticator = Storage.get_instance()
        
    # Initialize default auth keys
    defaults = {
        "auth_status": False,
        "username": None,
        "assistant": None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Mappa chat_id -> modello
    if "chat_models" not in st.session_state:
        st.session_state.chat_models = {}

    # Clean query params if not authenticated
    if not st.session_state.auth_status and "chat" in st.query_params:
        del st.query_params.chat

def _handle_logout() -> None:
    """
    Resets session state and redirects to Login.
    """
    st.session_state.auth_status = False
    st.session_state.username = None
    st.session_state.assistant = None
    
    if "chat" in st.query_params:
        del st.query_params.chat
        
    if "messages" in st.session_state:
        del st.session_state["messages"]
        
    if "docs" in st.session_state:
        del st.session_state["docs"]
        
    if "current_doc" in st.session_state:
        del st.session_state["current_doc"]

    st.query_params["page"] = "Login"
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
    if not (st.session_state.auth_status and st.session_state.username and st.session_state.authenticator):
        return

    with st.sidebar:
        st.write(f"👋 Benvenuto *{st.session_state['username']}*")
        
        # Navigation to Home
        if st.button("🏠 Home", use_container_width=True):
            if st.query_params.get("page") != "Home":
                st.query_params["page"] = "Home"
                st.rerun()
            
        st.divider()
        
        # Chat History List
        chats = st.session_state.authenticator.get_all_chats(st.session_state.username) or {}
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

            if st.button(label, key=f"nav_{chat_id}", use_container_width=True):
                # Cambiamo chat
                st.query_params["chat"] = chat_id

                # Allineiamo il modello nello stato di Home
                st.session_state.selected_model = model_key
                st.session_state.model_selector = model_key
                st.session_state.last_model_for_chat = model_key

                if st.query_params.get("page") != "Home":
                    st.query_params["page"] = "Home"

                st.rerun()

        
        st.divider()
        
        # Documents
        if st.button("📁 Visualizza Documenti", use_container_width=True):
            if st.query_params.get("page") != "Documents":
                st.query_params["page"] = "Documents"
                st.rerun()
                
        # Informazioni Linguaggio
        if st.button("ℹ️ Informazioni Linguaggio", use_container_width=True):
            if st.query_params.get("page") != "Info":
                st.query_params["page"] = "Info"
                st.rerun()

        # Tracking domande utente
        if st.button("ℹ️ Tracking Domande", use_container_width=True):
                    if st.query_params.get("page") != "QuestionTracking":
                        st.query_params["page"] = "QuestionTracking"
                        st.rerun()
        
        # Settings
        if st.button("⚙️ Impostazioni", use_container_width=True):
            if st.query_params.get("page") != "Settings":
                st.query_params["page"] = "Settings"
                st.rerun()

        # Logout
        if st.button("🟥 Logout", use_container_width=True):
            _handle_logout()

# --- Main Logic ---

_init_session_state()

# Security Check: Redirect unauthenticated users to Login/Registration
current_page = st.query_params["page"]
is_auth_page = current_page in ["Login", "Registration"]

if st.session_state.auth_status:
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