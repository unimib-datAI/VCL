import pandas as pd
import streamlit as st
import time
from typing import Any, Union, List

# ------------------
# --- Page setup ---
# ------------------

PAGE_TITLE = "Definisci il linguaggio DQL"

# -------------------------------
# --- Language Initialization ---
# -------------------------------

def _convert_to_editable(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts list columns (like 'synonyms') to semicolon-separated strings for the data editor.
    """
    editable_df = df.copy()
    if "synonyms" in editable_df.columns:
        editable_df["synonyms"] = editable_df["synonyms"].apply(
            lambda lst: "; ".join(lst) if isinstance(lst, list) else (lst if isinstance(lst, str) else "")
        )
    elif "synonyms" not in editable_df.columns:
         editable_df["synonyms"] = ""
    return editable_df

def _convert_to_savable(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parses semicolon-separated strings back into lists for storage.
    """
    savable_df = df.copy()
    if "synonyms" in savable_df.columns:
        savable_df["synonyms"] = savable_df["synonyms"].apply(
            lambda x: [s.strip() for s in str(x).split(";") if s.strip()] if (isinstance(x, str) and x.strip()) else []
        )
    return savable_df

def _reload_data_from_class() -> None:
    """
    Fetches current configuration from the Assistant's Language class 
    and populates session state dataframes.
    """
    language_class = st.session_state.language_class

    what_data = [item for item in language_class.get_what() if isinstance(item, dict)]
    from_data = [item for item in language_class.get_sources() if isinstance(item, dict)]
    commands_data = [item for item in language_class.get_commands() if isinstance(item, dict)]
    
    # df_what/df_from contain the "saved" data (with lists)
    st.session_state.df_what = pd.DataFrame(what_data)
    st.session_state.df_from = pd.DataFrame(from_data)

    # edited_what/edited_from contain the data for the editor (with strings)
    st.session_state.edited_what = st.session_state.df_what.copy()
    st.session_state.edited_from = _convert_to_editable(st.session_state.df_from)

    st.session_state.available_sources = list({
        src.get("name") for src in from_data if src.get("name")
    })
    
    st.session_state.available_commands = list({
        cmd.get("command") for cmd in commands_data if cmd.get("command")
    })

def _initialize_session_state() -> None:
    """
    Initialize session_state variables *only once* ensuring assistant is ready.
    """
    if "state_initialized" in st.session_state:
        return

    if "assistant" not in st.session_state or not st.session_state.assistant:
        st.error("Errore: Configurazione utente non caricata.")
        st.stop()
        
    st.session_state.language_class = st.session_state.assistant.get_language()
    _reload_data_from_class()
    st.session_state.state_initialized = True

# --------------------------
# --- Actions ---
# --------------------------

def _is_empty_value(x: Any) -> bool:
    """Checks if a value is considered empty."""
    if x is None:
        return True
    if isinstance(x, str) and x.strip() == "":
        return True
    if isinstance(x, (list, dict, set)) and len(x) == 0:
        return True
    return False

def _has_empty_values(df: pd.DataFrame) -> bool:
    """Checks if any cell in the dataframe is empty."""
    return df.map(_is_empty_value).values.any()

def _save_changes() -> Union[bool, None]:
    """
    Persists data from 'edited_what'/'edited_from' back to the Language Class.
    
    Returns:
        bool: True if save successful.
        None: If validation fails (empty values).
    """
    df_what = st.session_state.edited_what.copy()
    df_from_editable = st.session_state.edited_from.copy() 

    if _has_empty_values(df_what) or _has_empty_values(df_from_editable):
        return None

    df_from_processed = _convert_to_savable(df_from_editable)
    
    language_class = st.session_state.language_class
    result_what = language_class.set_what(df_what.to_dict(orient="records"))
    result_sources = language_class.set_sources(df_from_processed.to_dict(orient="records"))
    
    if result_what or result_sources:
        _reload_data_from_class()
    
    return result_what or result_sources

def _cancel_changes() -> bool:
    """
    Discards changes by reloading the last saved state.
    """
    st.session_state.edited_what = st.session_state.df_what.copy()
    st.session_state.edited_from = _convert_to_editable(st.session_state.df_from)
    return True

def _reset_language() -> bool:
    """
    Resets configuration to the default hardcoded language definition.
    """
    language_class = st.session_state.language_class
    result = language_class.set_default_language()
    
    if result:
        _reload_data_from_class()
        
    return result

# ---------------------------
# --- UI Components ---
# ---------------------------

def _display_confirmation_ui() -> None:
    """
    Renders the confirmation UI for sensitive actions (Save, Cancel, Reset).
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
    
    if st.button("✅ Sì, confermo", use_container_width=True):
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
            
    if st.button("❌ No, annulla", use_container_width=True):
        del st.session_state.action_pending
        st.rerun()

def _display_form_ui() -> None:
    """
    Renders the main data editor forms and action buttons.
    """
    with st.form(key="language_form"):
        st.markdown("### Sezione FROM")
        st.markdown("Per aggiornare l'elenco dei documenti nella sezione successiva devi prima salvare le modifiche di questa sezione.")
        
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
        st.markdown("Definisci i termini utilizzabili nei comandi DQL e le loro caratteristiche.\nConsidera che esistono due elementi non modificabili:\n- \"intero documento\": il comando deve essere applicato all'intero documento selezionato.\n- \"altro\": riguarda tutti quei casi in cui non è possibile categorizzare l'elemento richiesto.")
        
        try:
            current_sources = list(edited_from_df['name'].dropna().unique())
        except Exception:
            current_sources = st.session_state.available_sources

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
        
        col1, col2, col3 = st.columns(3)
        with col1:
            save_pressed = st.form_submit_button("💾 Salva", use_container_width=True)
        with col2:
            cancel_pressed = st.form_submit_button("↩️ Annulla", use_container_width=True)
        with col3:
            reset_pressed = st.form_submit_button("🔄 Ripristina", use_container_width=True)

    # --- Handling logic *after* form submission ---
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
    Main entry point. Acts as a router between editing and confirmation states.
    """
    st.title(PAGE_TITLE)
    _initialize_session_state() 

    if "action_pending" in st.session_state:
        _display_confirmation_ui()
    else:
        _display_form_ui()

if __name__ == "__main__":
    show_settings()