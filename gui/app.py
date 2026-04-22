import streamlit as st
import time

from copy import deepcopy
from tomlkit import value
from typing import Dict, Callable

# Page component imports
from gui.pages_content.AdminPage import show_admin
from gui.pages_content.Login import show_login
# from gui.pages_content.Registration import show_registration
from gui.pages_content.Home import show_home
from gui.pages_content.Settings import show_settings
from gui.pages_content.Documents import show_documents
from gui.pages_content.Info import show_info
from gui.pages_content.QuestionsTracking import show_questions_tracking

from utils.config import Config

# Model identifiers and display labels
MODEL_LABELS = {
    "DQL": "DQL",
    "GPT": "GPT",
    "NotebookLM": "NotebookLM",
    "BattleAnon": "Battle (anonimo)",
    "BattleLabeled": "Battle (etichettato)",
}
DEFAULT_MODEL = "DQL"

# --- Main Streamlit Configuration ---
st.set_page_config(page_title="DQL", layout="wide")

# Mapping of page names to their respective rendering functions
PAGE_MAP: Dict[str, Callable] = {
    "Login": show_login,
    "Admin": show_admin,
    "Home": show_home,
    "Settings": show_settings,
    "Documents": show_documents,
    "Info": show_info,
    "QuestionTracking" : show_questions_tracking,
}

# -------------------------------
# --- Session Management Helpers ---
# -------------------------------

def _init_session_state() -> None:
    """
    Initializes core session state variables and query parameters.
    Ensures that Config, Storage, and Auth defaults are present before rendering.
    """
    # Set default page to Login if not specified in the URL
    if "page" not in st.query_params:
        st.query_params["page"] = "Login"
        
    # Lazy initialization of singleton configuration and storage objects
    if "config" not in st.session_state or "storage" not in st.session_state or "language" not in st.session_state:
        st.session_state.config = Config.get_instance()
        st.session_state.storage = st.session_state.config.get_storage()
        
    # Define and apply default values for session keys
    defaults = {
        "auth_status": False,
        "chat_models": {} # Cache to map chat IDs to their specific AI models
    }
    
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Security: strip chat-specific query parameters if the user is not logged in
    if not st.session_state.auth_status and "chat" in st.query_params:
        del st.query_params.chat

def _handle_logout() -> None:
    """
    Performs a complete session cleanup. 
    Clears session state, query parameters, and redirects the user to the Login page.
    """
    # Fully wipe session and query strings
    st.session_state.clear()
    st.query_params.clear()

    # Re-initialize basic state for the next login attempt
    _init_session_state()
    
    st.rerun()

def _infer_chat_model(messages) -> str:
    """
    Attempts to identify which AI engine was used in a specific conversation.
    Searches through the message history in reverse to find the latest assistant metadata.

    Args:
        messages (list): List of message dictionaries from the chat history.

    Returns:
        str: The model key (e.g., 'GPT', 'DQL') or the default model if not found.
    """
    if not messages:
        return DEFAULT_MODEL

    # Iterate backwards to find the most recent model assignment
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("model"):
            return msg["model"]

    return DEFAULT_MODEL

def _render_sidebar() -> None:
    """
    Renders the sidebar navigation panel for authenticated users.
    Includes chat history management and links to protected application pages.
    """
    if not st.session_state.auth_status:
        return

    with st.sidebar:
        st.write(f"👋 Benvenuto *{st.session_state['username']}*")
            
        st.divider()
        
        # --- Chat History Management ---
        chats = st.session_state.storage.get_all_chats(st.session_state.username) or {}
        # Order chats chronologically (most recent at the top)
        sorted_keys = sorted(chats.keys(), reverse=True)

        for index, chat_id in enumerate(sorted_keys):
            # Calculate display index (e.g., Chat 3, Chat 2, Chat 1)
            display_index = str(len(sorted_keys) - index)
            messages = chats.get(chat_id, [])

            # 1) Retrieve cached model if available
            model_key = st.session_state.chat_models.get(chat_id)

            # 2) Fallback: infer model from history and update cache
            if not model_key:
                model_key = _infer_chat_model(messages)
                st.session_state.chat_models[chat_id] = model_key

            model_label = MODEL_LABELS.get(model_key, model_key)
            label = f"💬 Chat {display_index} ({model_label})"

            if st.button(label, key=f"nav_{chat_id}", width='stretch'):
                # Navigation logic: update chat context and synchronize engine state
                st.query_params["chat"] = chat_id

                # Sync model selection keys for the Home view
                st.session_state.selected_model = model_key
                st.session_state.model_selector = model_key
                st.session_state.last_model_for_chat = model_key

                change_page("Home")
                st.rerun()

        st.divider()
        
        # --- Navigation Links ---
        if st.button("📁 Visualizza Documenti", width='stretch'):
            change_page("Documents")
                
        if st.button("Informazioni Linguaggio", width='stretch'):
            change_page("Info")

        if st.button("Tracking Domande", width='stretch'):
            change_page("QuestionTracking")
        
        if st.button("⚙️ Impostazioni", width='stretch'):
            change_page("Settings")
                
        # --- Administrative Access ---
        if st.session_state.role == "Admin":
            if st.button("🛠️ Admin Dashboard", width='stretch'):
                change_page("Admin")

        # --- Session Termination ---
        if st.button("🟥 Logout", width='stretch'):
            _handle_logout()
            
def change_page(dest_page):
    """
    Updates the 'page' query parameter and triggers a rerun if the 
    destination is different from the current page.
    """
    if st.query_params.get("page") != dest_page:
        st.query_params["page"] = dest_page
        st.rerun()

# --------------------
# --- Main Logic ---
# --------------------

# Establish session state baseline
_init_session_state()

# Authentication Guard: Define public pages
current_page = st.query_params["page"]
is_auth_page = current_page in ["Login"]

if st.session_state.auth_status:
    # Validate that identity data is fully loaded
    if (not st.session_state.username) or (not st.session_state.role):
        st.session_state.auth_status = False
        st.rerun()
    
    # Synchronize chat context and language specs
    if "chat" not in st.query_params or not st.query_params.chat:
        st.query_params.chat = st.session_state.storage.create_new_chat(st.session_state.username)
        
    if "language" not in st.query_params or not st.session_state.language:
        st.session_state.language = st.session_state.config.get_DQL(st.session_state.username)
    
    _render_sidebar()

    # Prevent authenticated users from visiting Login
    if is_auth_page:
        st.query_params["page"] = "Home"
        st.rerun()
else:
    # Force logout/reset if an unauthenticated user tries to access protected routes
    if not is_auth_page:
        _handle_logout()

# Routing: Fetch the appropriate page function from the map and execute it
page_to_show = PAGE_MAP.get(st.query_params["page"], show_login)
page_to_show()