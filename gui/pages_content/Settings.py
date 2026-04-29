"""Streamlit settings page for editing DQL language definitions."""

import pandas as pd
import streamlit as st
import time
from typing import Any, Union, List

# ------------------
# --- Page setup ---
# ------------------

PAGE_TITLE = "Definisci l'ontologia di DQL"

# -------------------------------
# --- Language Initialization ---
# -------------------------------

def _convert_to_editable(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepares the dataframe for the Streamlit UI by converting list-type columns 
    into semicolon-separated strings. This allows users to edit synonyms easily 
    as plain text.
    """
    editable_df = df.copy()
    if "synonyms" in editable_df.columns:
        # Convert list of strings to a single string separated by "; "
        editable_df["synonyms"] = editable_df["synonyms"].apply(
            lambda lst: "; ".join(lst) if isinstance(lst, list) else (lst if isinstance(lst, str) else "")
        )
    elif "synonyms" not in editable_df.columns:
         editable_df["synonyms"] = ""
    return editable_df

def _convert_to_savable(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reverse process of _convert_to_editable. Parses semicolon-separated strings 
    from the data editor back into Python lists for persistent storage.
    """
    savable_df = df.copy()
    if "synonyms" in savable_df.columns:
        # Split string by ";" and strip whitespace to reconstruct the original list format
        savable_df["synonyms"] = savable_df["synonyms"].apply(
            lambda x: [s.strip() for s in str(x).split(";") if s.strip()] if (isinstance(x, str) and x.strip()) else []
        )
    return savable_df

def _reload_data_from_class() -> None:
    """
    Synchronizes the Streamlit session state with the backend Language class.
    Fetches raw dictionaries and initializes dataframes for both display and editing.
    """
    # Retrieve structured data from the logic layer
    what_data = [item for item in st.session_state.language.get_what() if isinstance(item, dict)]
    from_data = [item for item in st.session_state.language.get_sources() if isinstance(item, dict)]
    commands_data = [item for item in st.session_state.language.get_commands() if isinstance(item, dict)]
    
    # Snapshot of the data currently persisted in the backend
    st.session_state.df_what = pd.DataFrame(what_data)
    st.session_state.df_from = pd.DataFrame(from_data)

    # Working copies for the UI data editor
    st.session_state.edited_what = st.session_state.df_what.copy()
    st.session_state.edited_from = _convert_to_editable(st.session_state.df_from)

    # Cache lists of names for dropdowns and multiselect components
    st.session_state.available_sources = list({
        src.get("name") for src in from_data if src.get("name")
    })
    
    st.session_state.available_commands = list({
        cmd.get("command") for cmd in commands_data if cmd.get("command")
    })

def _initialize_session_state() -> None:
    """
    One-time initialization of the session state variables. Ensures the backend
    Language class is available before attempting to load data.
    """
    if "state_initialized" in st.session_state:
        return

    # Check for core dependency in session_state
    if "language" not in st.session_state or not st.session_state.language:
        st.error("Errore: Configurazione utente non caricata.")
        st.stop()
        
    _reload_data_from_class()
    st.session_state.state_initialized = True

# --------------------------
# --- Actions ---
# --------------------------

def _is_empty_value(x: Any) -> bool:
    """
    Validation helper to identify null, empty strings, or empty collections.
    """
    if x is None:
        return True
    if isinstance(x, str) and x.strip() == "":
        return True
    if isinstance(x, (list, dict, set)) and len(x) == 0:
        return True
    return False

def _has_empty_values(df: pd.DataFrame) -> bool:
    """
    Scans the entire dataframe to check for the presence of invalid/empty cells.
    """
    return df.map(_is_empty_value).values.any()

def _save_changes() -> Union[bool, None]:
    """
    Validates and persists UI changes to the backend.
    Converts edited dataframes back to raw dictionary lists.
    
    Returns:
        bool: True if storage update was successful.
        None: If validation fails due to empty fields.
    """
    df_what = st.session_state.edited_what.copy()
    df_from_editable = st.session_state.edited_from.copy() 

    # Block save if critical information is missing
    if _has_empty_values(df_what) or _has_empty_values(df_from_editable):
        return None

    # Prepare data for the storage layer (convert strings back to lists)
    df_from_processed = _convert_to_savable(df_from_editable)
    
    # Update backend class
    result_what = st.session_state.language.set_what(df_what.to_dict(orient="records"))
    result_sources = st.session_state.language.set_sources(df_from_processed.to_dict(orient="records"))
    
    if result_what or result_sources:
        _reload_data_from_class()
    
    return result_what or result_sources

def _cancel_changes() -> bool:
    """
    Reverts the UI state by overwriting working copies with the last saved snapshot.
    """
    st.session_state.edited_what = st.session_state.df_what.copy()
    st.session_state.edited_from = _convert_to_editable(st.session_state.df_from)
    return True

def _reset_language() -> bool:
    """
    Triggers the backend routine to restore the default language definition
    and refreshes the session state data.
    """
    result = st.session_state.language.set_default_language()
    
    if result:
        _reload_data_from_class()
        
    return result

# ---------------------------
# --- UI Components ---
# ---------------------------

def _display_confirmation_ui() -> None:
    """
    Interrupts the main flow to show a confirmation dialog for critical actions.
    Uses a mapping to determine which backend function to execute on confirmation.
    """
    action = st.session_state.action_pending
    
    action_map = {
        "save": ("Sei sicuro di voler salvare le modifiche?", _save_changes),
        "cancel": ("Vuoi annullare le modifiche?", _cancel_changes),
        "reset": ("Ripristinare i valori originali? Questa operazione non può essere annullata!", _reset_language),
    }

    if action not in action_map:
        del st.session_state.action_pending
        st.rerun()
        return

    message, function_to_run = action_map[action]
    st.warning(message)
    
    if st.button("✅ Sì, confermo", width='stretch'):
        success = function_to_run()
        
        if success is True:
            st.success("✅ Modifiche salvate con successo!")
        elif success is None:
            st.warning("⚠️ Impossibile salvare: sono presenti valori vuoti nei dati.")
        else:
            st.error("❌ Si è verificato un errore durante il salvataggio delle modifiche.")
            
        time.sleep(1)
        
        del st.session_state.action_pending
        st.rerun()
            
    if st.button("❌ No, annulla", width='stretch'):
        del st.session_state.action_pending
        st.rerun()

def _display_form_ui() -> None:
    """
    Renders the DQL language definition forms using Streamlit's data_editor.
    Manages two main sections: FROM (Sources) and WHAT (Concepts/Terms).
    """
    with st.form(key="language_form"):
        st.markdown("### Sezione FROM")
        st.markdown("Per aggiornare l'elenco dei documenti nella sezione successiva devi prima salvare le modifiche di questa sezione.")
        
        # Table for defining document types and their synonyms
        edited_from_df = st.data_editor(
            st.session_state.edited_from, 
            num_rows="dynamic",
            key="from_editor", 
            column_config={
                "name": st.column_config.TextColumn(
                    "Documento",
                    help="Inserisci il nome del documento.",
                ),
                "description": st.column_config.TextColumn(
                    "Breve Descrizione",
                    help="Fornisci una breve descrizione del documento.",
                ),
                "synonyms": st.column_config.TextColumn(
                    "Sinonimi",
                    help="Inserisci i sinonimi separati da ;",
                    width="medium"
                ),
            },
        )
        
        st.markdown("### Sezione WHAT")
        st.markdown("Definisci i termini utilizzabili nei comandi DQL e le loro caratteristiche.\nConsidera che esistono alcuni elementi non modificabili:\n- \"intero documento\": il comando deve essere applicato all'intero documento selezionato.\n- \"frase\": l'utente vuole estrarre una frase simile o relativa a un elemento nella richiesta\n- \"concetto\": l'utente vuole individuare l'occorrenza di una stringa o concetto non identificato nelle precedenti categorie.")
        
        # Dynamically link the sources available in the 'WHAT' multiselect to current 'FROM' data
        try:
            current_sources = list(edited_from_df['name'].dropna().unique())
        except Exception:
            current_sources = st.session_state.available_sources

        # Table for defining AI concepts, mapping them to sources and commands
        edited_what_df = st.data_editor(
            st.session_state.edited_what,
            num_rows="dynamic",
            key="what_editor", 
            column_config={
                "name": st.column_config.TextColumn(
                    "Termine",
                    help="Il termine o concetto principale da definire.",
                ),
                "definition": st.column_config.TextColumn(
                    "Definizione",
                    help="La spiegazione dettagliata del termine. (Utilizzata per l'AI)",
                ),
                "available": st.column_config.MultiselectColumn(
                    "Disponibile nei documenti...",
                    help="Seleziona da questa lista i **documenti** (fonti) per cui questo elemento ha senso di esistere.",
                    options=current_sources,
                    color="primary",
                    format_func=lambda x: x.capitalize(),
                ),
                "relative_command": st.column_config.MultiselectColumn(
                    "Specifico dei comandi",
                    help="Seleziona i Comandi Atomici a cui questo termine è strettamente collegato o applicabile.",
                    options=st.session_state.available_commands,
                    color="primary"
                ),
            },
        )
        
        # Action buttons for form management
        col1, col2, col3 = st.columns(3)
        with col1:
            save_pressed = st.form_submit_button("💾 Salva", width='stretch')
        with col2:
            cancel_pressed = st.form_submit_button("↩️ Annulla", width='stretch')
        with col3:
            reset_pressed = st.form_submit_button("🔄 Ripristina", width='stretch')

    # --- Post-submission routing logic ---
    if save_pressed:
        st.session_state.edited_what = edited_what_df
        st.session_state.edited_from = edited_from_df
        st.session_state.action_pending = "save"
        st.rerun()

    elif cancel_pressed:
        st.session_state.action_pending = "cancel"
        st.rerun()

    elif reset_pressed:
        st.session_state.action_pending = "reset"
        st.rerun()

# -------------------
# --- Entry Point ---
# -------------------

def show_settings():
    """
    Renders the page. Acts as a router between the main editing form 
    and the confirmation screen for critical actions.
    """
    st.title(PAGE_TITLE)
    _initialize_session_state() 

    # Determine which UI to show based on the presence of a pending action
    if "action_pending" in st.session_state:
        _display_confirmation_ui()
    else:
        _display_form_ui()

if __name__ == "__main__":
    show_settings()
