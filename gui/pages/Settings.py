import pandas as pd
import streamlit as st

from utils.config import Config

# ------------------
# --- Page setup ---
# ------------------

PAGE_TITLE = "Definisci il campo \"WHAT\""

def configure_page():
    """
    Configure the Streamlit page and apply custom CSS styles for layout and aesthetics.
    """
    st.set_page_config(
        page_title=PAGE_TITLE, 
        page_icon="🧠", 
        layout="wide"
    )

    # --- Custom CSS ---
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }

        /* Hide default Streamlit header */
        header {
            visibility: hidden;
            height: 0;
        }

        /* Adjust chat message layout */
        [data-testid="stChatMessage"] {
            width: auto;
            margin-left: 50px;
            margin-right: 50px;
        }

        h1 {
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------
# --- Language Initialization ---
# -------------------------------

def initialize_session_state():
    """
    Initialize the Streamlit session state variables if they don't exist.
    Ensures consistent state management across page reruns.
    """
    if "language_class" not in st.session_state:
        # Initialize the DQLLanguage instance
        st.session_state.language_class = Config.get_instance().language
    
    if "language" not in st.session_state:
        st.session_state.language = st.session_state.language_class.get_language()

    if "df" not in st.session_state:
        st.session_state.df = None

    if "edited_df" not in st.session_state:
        st.session_state.edited_df = None


# ---------------------
# --- UI Components ---
# ---------------------

def display_language_editor():
    """
    Display a table editor for modifying the DQL language configuration.
    Provides UI controls for saving, canceling, or resetting changes.
    """
    # Load the language data into DataFrames
    st.session_state.df = pd.DataFrame(
        st.session_state.language.get("what", [])
    ).copy()

    if st.session_state.edited_df is None:
        st.session_state.edited_df = st.session_state.df.copy()

    # Generate selectable options for the "available" column
    available_sources = list({
        src.get("name") for src in st.session_state.language.get("sources", [])
    })

    # Display editable DataFrame
    st.session_state.edited_df = st.data_editor(
        st.session_state.edited_df.copy(),
        num_rows="dynamic",
        column_config={
            "name": "Termine",
            "definition": "Definizione",
            "available": st.column_config.MultiselectColumn(
                "Disponibile nei documenti...",
                options=available_sources,
                color="primary",
                format_func=lambda x: x.capitalize(),
            ),
        },
    )

    # Control buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        save_clicked = st.button("💾 Salva", use_container_width=True)
    with col2:
        cancel_clicked = st.button("↩️ Annulla", use_container_width=True)
    with col3:
        reset_clicked = st.button("🔄 Ripristina", use_container_width=True)

    # Handle button actions with confirmation dialogs
    if save_clicked:
        confirm_popup("Sei sicuro di voler salvare le modifiche?", save_changes)
    elif cancel_clicked:
        confirm_popup("Vuoi annullare le modifiche?", cancel_changes)
    elif reset_clicked:
        confirm_popup(
            "Ripristinare i valori originali? Questa operazione non può essere annullata!",
            reset_language,
        )


# ----------------
# --- Actions ---
# ---------------

def save_changes():
    """
    Save the edited DataFrame back to the language configuration.
    Updates both the DQL language and session state.
    """
    st.session_state.language["what"] = st.session_state.edited_df.to_dict(orient="records")
    st.session_state.language_class.set_language(st.session_state.language)
    update_session_state()
    st.session_state.df = st.session_state.edited_df.copy()
    st.success("✅ Modifiche salvate!")


def cancel_changes():
    """
    Cancel unsaved edits and restore the last saved DataFrame version.
    """
    st.session_state.edited_df = st.session_state.df.copy()
    st.info("Operazione annullata.")


def reset_language():
    """
    Reset the language configuration to its default state.
    """
    st.session_state.language_class.set_default_language()
    update_session_state()
    st.session_state.df = pd.DataFrame(st.session_state.language.get("what", [])).copy()
    st.session_state.edited_df = st.session_state.df.copy()
    st.warning("⚠️ Valori ripristinati ai default!")


def update_session_state():
    """
    Refresh the language data in the Streamlit session state
    after changes or reset operations.
    """
    st.session_state.language = st.session_state.language_class.get_language()


# ---------------------------
# --- Confirmation Dialog ---
# ---------------------------

@st.dialog("Sei sicuro?")
def confirm_popup(message: str, action):
    """
    Generic confirmation popup for critical actions (save, cancel, reset).

    Args:
        message (str): Message to display in the dialog.
        action (callable): Function to execute upon confirmation.
    """
    st.write(message)

    if st.button("✅ Sì, confermo"):
        action()
        st.rerun()

# -------------------
# --- Entry Point ---
# -------------------

def main():
    """
    Main entry point for the Streamlit DQL app.
    Sets up layout, restores chat history, and handles user interactions.
    """
    configure_page()
    st.title(PAGE_TITLE)

    initialize_session_state()
    display_language_editor()

if __name__ == "__main__":
    main()
