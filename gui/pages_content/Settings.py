import pandas as pd
import streamlit as st

# ------------------
# --- Page setup ---
# ------------------

PAGE_TITLE = "Definisci il linguaggio DQL"

# st.set_page_config() is called in app.py

# -------------------------------
# --- Language Initialization ---
# -------------------------------

def initialize_session_state():
    """
    Initialize the Streamlit session state variables if they don't exist.
    Ensures consistent state management across page reruns.
    """
    
    # Verify that logic_config has been loaded correctly
    if not st.session_state.logic_config:
        st.error("Errore: Configurazione utente non caricata.")
        st.stop()
        
    language_class = st.session_state.logic_config.language
    st.session_state.language_class = language_class

    # 'df_what' and 'df_from' will contain the saved data
    if "df_what" not in st.session_state:
        st.session_state.df_what = pd.DataFrame(
            language_class.get_what()
        )
        
    if "df_from" not in st.session_state:
        st.session_state.df_from = pd.DataFrame(
            language_class.get_sources()
        )
        
    # 'edited_what' and 'edited_from' will contain the data being edited
    if "edited_what" not in st.session_state:
        st.session_state.edited_what = st.session_state.df_what.copy()
        
    if "edited_from" not in st.session_state:
        st.session_state.edited_from = st.session_state.df_from.copy()
        
    # Generate selectable options
    if "available_sources" not in st.session_state:
        st.session_state.available_sources = list({
            src.get("name") for src in language_class.get_sources()
        })
    
    if "available_commands" not in st.session_state:
        st.session_state.available_commands = list({
            cmd.get("command") for cmd in language_class.get_commands()
        })

# --------------------------
# --- What UI Components ---
# --------------------------

def display_what_editor():
    """
    Display a table editor for modifying the What Section of DQL configuration.
    """
    st.markdown("### Sezione WHAT")

    st.session_state.edited_what = st.data_editor(
        st.session_state.edited_what,
        num_rows="dynamic",
        column_config={
            "name": "Termine",
            "definition": "Definizione",
            "available": st.column_config.MultiselectColumn(
                "Disponibile nei documenti...",
                options=st.session_state.available_sources,
                color="primary",
                format_func=lambda x: x.capitalize(),
            ),
            "relative_command": st.column_config.MultiselectColumn(
                "Specifico dei comandi",
                options=st.session_state.available_commands,
                color="primary"
            ),
        },
    )

# --------------------------
# --- From UI Components ---
# --------------------------

def display_from_editor():
    """
    Display a table editor for modifying the From Section of DQL configuration.
    """
    st.markdown("### Sezione FROM")
    
    # The "edited" DataFrame (which has lists) is copied and transformed into strings only for display
    from_display = st.session_state.edited_from.copy()
    
    from_display["synonyms"] = from_display["synonyms"].apply(
        lambda lst: "; ".join(lst) if isinstance(lst, list) else (lst if isinstance(lst, str) else "")
    )
    
    edited_data_from_display = st.data_editor(
        from_display,
        num_rows="dynamic",
        column_config={
            "name": "Documento",
            "description": "Breve Descrizione",
            "synonyms": st.column_config.TextColumn(
                "Sinonimi",
                help="Inserisci i sinonimi separati da ;",
                width="medium"
            ),
        },
    )
    
    st.session_state.edited_from = edited_data_from_display

# --------------------------
# --- Button Components ---
# --------------------------

def display_buttons():
    col1, col2, col3 = st.columns(3)
    with col1:
        save = st.button("💾 Salva", use_container_width=True)
    with col2:
        cancel = st.button("↩️ Annulla", use_container_width=True)
    with col3:
        reset = st.button("🔄 Ripristina", use_container_width=True)

    if save:
        confirm_popup("save", save_changes)
    elif cancel:
        confirm_popup("cancel", cancel_changes)
    elif reset:
        confirm_popup("reset", reset_language)

# ----------------
# --- Actions ---
# ---------------
def is_empty_value(x):
    if x is None:
        return True
    if isinstance(x, str) and x.strip() == "":
        return True
    if isinstance(x, (list, dict, set)) and len(x) == 0:
        return True
    return False

def has_empty_values(df):
    return df.map(is_empty_value).values.any()

def save_changes():
    """
    Save the edited DataFrame back to the language configuration,
    only if there are no None, empty, or whitespace-only values.
    """
    df_what = st.session_state.edited_what.copy()
    df_from_display = st.session_state.edited_from.copy()

    if has_empty_values(df_what) or has_empty_values(df_from_display):
        st.error("⚠️ Compila tutti i campi")
        return

    # Reconvert synonyms from string to list before saving
    df_from_processed = df_from_display.copy()
    if "synonyms" in df_from_processed.columns:
        df_from_processed["synonyms"] = df_from_processed["synonyms"].apply(
            lambda x: [s.strip() for s in str(x).split(";") if s.strip()] if isinstance(x, str) else (x if isinstance(x, list) else [])
        )
    
    language_class = st.session_state.language_class
    language_class.set_what(df_what.to_dict(orient="records"))
    language_class.set_sources(df_from_processed.to_dict(orient="records"))
    
    st.session_state.df_what = df_what.copy()
    st.session_state.df_from = df_from_processed.copy()
    
    st.session_state.edited_from = df_from_processed.copy() # Aggiorna 'edited' con la versione processata
    
    # Ricarica le opzioni disponibili nel caso siano cambiati i nomi
    st.session_state.available_sources = list({
        src.get("name") for src in language_class.get_sources()
    })
    
    st.success("✅ Modifiche salvate con successo!")

def cancel_changes():
    """
    Cancel unsaved edits and restore the last saved DataFrame version.
    """
    st.session_state.edited_what = st.session_state.df_what.copy()
    st.session_state.edited_from = st.session_state.df_from.copy()
    
    st.info("Operazione annullata.")


def reset_language():
    """
    Reset the language configuration to its default state.
    """
    language_class = st.session_state.language_class
    language_class.set_default_language()
    
    st.session_state.df_what = pd.DataFrame(language_class.get_what())
    st.session_state.df_from = pd.DataFrame(language_class.get_sources())
    
    st.session_state.edited_what = st.session_state.df_what.copy()
    st.session_state.edited_from = st.session_state.df_from.copy()
    
    # Ricarica anche le opzioni
    st.session_state.available_sources = list({
        src.get("name") for src in language_class.get_sources()
    })
    st.session_state.available_commands = list({
        cmd.get("command") for cmd in language_class.get_commands()
    })

    st.warning("⚠️ Valori ripristinati ai default!")

# ---------------------------
# --- Confirmation Dialog ---
# ---------------------------

@st.dialog("Sei sicuro?")
def confirm_popup(action: str, function):
    match action:
        case "save":
            message = "Sei sicuro di voler salvare le modifiche?"
        case "cancel":
            message = "Vuoi annullare le modifiche?"
        case "reset":
            message = "Ripristinare i valori originali? Questa operazione non può essere annullata!"
        case _:
            message = ""
    
    if message:
        st.write(message)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Sì, confermo", use_container_width=True):
                function()
                st.rerun()
        with col2:
            if st.button("❌ No, annulla", use_container_width=True):
                st.rerun()

# -------------------
# --- Entry Point ---
# -------------------

def show_settings():
    """
    Main entry point for the Streamlit DQL app.
    Sets up layout, restores chat history, and handles user interactions.
    """
    st.title(PAGE_TITLE)

    initialize_session_state()
    display_what_editor()
    display_from_editor()
    display_buttons()

if __name__ == "__main__":
    show_settings()