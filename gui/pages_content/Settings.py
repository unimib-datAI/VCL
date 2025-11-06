import pandas as pd
import streamlit as st
import time

# ------------------
# --- Page setup ---
# ------------------

PAGE_TITLE = "Definisci il linguaggio DQL"

# st.set_page_config() è chiamato in app.py

# -------------------------------
# --- Language Initialization ---
# -------------------------------

def convert_from_df_to_editable(df: pd.DataFrame) -> pd.DataFrame:
    """Converts the 'synonyms' column from a list to a string for editing."""
    editable_df = df.copy()
    if "synonyms" in editable_df.columns:
        editable_df["synonyms"] = editable_df["synonyms"].apply(
            lambda lst: "; ".join(lst) if isinstance(lst, list) else (lst if isinstance(lst, str) else "")
        )
    # Ensures column exists even for empty dfs
    elif "synonyms" not in editable_df.columns:
         editable_df["synonyms"] = ""
    return editable_df

def convert_from_df_to_savable(df: pd.DataFrame) -> pd.DataFrame:
    """Reconverts the 'synonyms' column from a string to a list for saving."""
    savable_df = df.copy()
    if "synonyms" in savable_df.columns:
        savable_df["synonyms"] = savable_df["synonyms"].apply(
            lambda x: [s.strip() for s in str(x).split(";") if s.strip()] if (isinstance(x, str) and x.strip()) else []
        )
    return savable_df

def reload_data_from_class():
    """
    Reloads all data from the language_class instance into the session_state.
    Used after saving or restoring to default values.
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
    st.session_state.edited_from = convert_from_df_to_editable(st.session_state.df_from)

    st.session_state.available_sources = list({
        src.get("name") for src in from_data if src.get("name")
    })
    
    st.session_state.available_commands = list({
        cmd.get("command") for cmd in commands_data if cmd.get("command")
    })

def initialize_session_state():
    """
    Initialize session_state variables *only once*.
    """
    
    if "state_initialized" in st.session_state:
        return

    if "logic_config" not in st.session_state or not st.session_state.logic_config:
        st.error("Errore: Configurazione utente non caricata.")
        st.stop()
        
    st.session_state.language_class = st.session_state.logic_config.language
    reload_data_from_class()
    st.session_state.state_initialized = True

# --------------------------
# --- Actions ---
# --------------------------

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
    Saves data from 'edited_what'/'edited_from' to the class.
    Returns True if the save is successful, False otherwise.
    """
    df_what = st.session_state.edited_what.copy()
    df_from_editable = st.session_state.edited_from.copy() 

    if has_empty_values(df_what) or has_empty_values(df_from_editable):
        return False

    df_from_processed = convert_from_df_to_savable(df_from_editable)
    
    language_class = st.session_state.language_class
    language_class.set_what(df_what.to_dict(orient="records"))
    language_class.set_sources(df_from_processed.to_dict(orient="records"))
    
    reload_data_from_class()
    return True

def cancel_changes():
    """
    Reloads the "saved" data (df_what/df_from), overwriting
    the changes in 'edited_what'/'edited_from'.
    """
    st.session_state.edited_what = st.session_state.df_what.copy()
    st.session_state.edited_from = convert_from_df_to_editable(st.session_state.df_from)
    return True

def reset_language():
    """
    Resets the default data and reloads it into the state.
    """
    language_class = st.session_state.language_class
    language_class.set_default_language()
    reload_data_from_class()
    return True

# ---------------------------
# --- UI Components ---
# ---------------------------

def display_confirmation_ui():
    """
    Shows the confirmation interface (instead of the form).
    This function handles "Yes" and "No" clicks.
    """
    action = st.session_state.action_pending
    
    if action == "save":
        message = "Sei sicuro di voler salvare le modifiche?"
        function_to_run = save_changes
    elif action == "cancel":
        message = "Vuoi annullare le modifiche?"
        function_to_run = cancel_changes
    elif action == "reset":
        message = "Ripristinare i valori originali? Questa operazione non può essere annullata!"
        function_to_run = reset_language
    else:
        # Failsafe: If the state is invalid, clear it and reload
        del st.session_state.action_pending
        st.rerun()
        return

    st.warning(message)
    
    if st.button("✅ Sì, confermo", use_container_width=True):
        success = function_to_run()
        
        if success:
            st.success("✅ Modifiche salvate con successo!")
        else:
            st.warning("Compila tutti i campi!")
        
        time.sleep(1)
        
        # Clear the flag and reload to return to the form
        del st.session_state.action_pending
        st.rerun()
            
    if st.button("❌ No, annulla", use_container_width=True):
        # Clear the flag and reload to return to the form
        del st.session_state.action_pending
        st.rerun()

def display_form_ui():
    """
    Displays the form with the data_editor and submit buttons.
    This function sets the 'action_pending' flag when a button is pressed.
    """
    with st.form(key="language_form"):
        st.markdown("### Sezione FROM")
        
        edited_from_df = st.data_editor(
            st.session_state.edited_from, 
            num_rows="dynamic",
            key="from_editor", 
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
        
        st.markdown("### Sezione WHAT")
        
        try:
            current_sources = list(edited_from_df['name'].dropna().unique())
        except Exception:
            current_sources = st.session_state.available_sources

        edited_what_df = st.data_editor(
            st.session_state.edited_what,
            num_rows="dynamic",
            key="what_editor", 
            column_config={
                "name": "Termine",
                "definition": "Definizione",
                "available": st.column_config.MultiselectColumn(
                    "Disponibile nei documenti...",
                    options=current_sources,
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
        
        col1, col2, col3 = st.columns(3)
        with col1:
            save_pressed = st.form_submit_button("💾 Salva", use_container_width=True)
        with col2:
            cancel_pressed = st.form_submit_button("↩️ Annulla", use_container_width=True)
        with col3:
            reset_pressed = st.form_submit_button("🔄 Ripristina", use_container_width=True)

    # --- Handling logic *after* form submission ---
    if save_pressed:
        # Save modified data in state
        st.session_state.edited_what = edited_what_df
        st.session_state.edited_from = edited_from_df
        # Set the flag to show confirmation on next rerun
        st.session_state.action_pending = "save"
        st.rerun()

    elif cancel_pressed:
        # Do NOT save data. Set the flag only.
        st.session_state.action_pending = "cancel"
        st.rerun()

    elif reset_pressed:
        # Do NOT save data. Set the flag only.
        st.session_state.action_pending = "reset"
        st.rerun()

# -------------------
# --- Entry Point ---
# -------------------

def show_settings():
    """
    Main entry point.
    It acts as a "router" that displays the confirmation interface
    or the form interface based on the state.
    """
    st.title(PAGE_TITLE)
    initialize_session_state() 

    if "action_pending" in st.session_state:
        # Status = "confirm"
        display_confirmation_ui()
    else:
        # Status = "editing" (default)
        display_form_ui()

if __name__ == "__main__":
    show_settings()