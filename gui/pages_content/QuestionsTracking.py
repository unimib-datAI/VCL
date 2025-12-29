import streamlit as st
from datetime import datetime

def show_questions_tracking():
    """
    Fetches the history of user questions from the database and renders them
    in a structured dataframe. Displays a chronological list of interactions
    including timestamps, question content, and the specific AI model used.
    """
    st.title("📊 Tracking delle Domande")

    # --- Database interaction logic ---
    try:
        # Access the private collection directly from the storage service
        db = st.session_state.storage._questions
        
        # Query logs associated with the current user, sorted by most recent first
        cursor = db.find({"user": st.session_state.username}).sort("timestamp", -1)
        rows = list(cursor)
    except Exception as e:
        # Provide feedback in case of database connection or query issues
        st.error(f"Errore nel caricamento delle domande: {e}")
        return

    # Guard clause: stop rendering if no history is found
    if not rows:
        st.info("Nessuna domanda tracciata.")
        return

    # --- Data transformation for UI display ---
    table = []
    for r in rows:
        # Format the data into a list of dictionaries compatible with st.dataframe
        table.append({
            "Data/Ora": r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "Domanda": r["question"],
            "Modello": r.get("model", "-"), # Fallback if model info is missing
        })

    # Render the interactive table in the UI
    st.dataframe(table, width='stretch')

def show_page():
    """
    Main entry point for the Questions Tracking page.
    Performs security and initialization checks before invoking the dashboard logic.
    """
    # Initial session validation: ensure required components are loaded in session state
    required_keys = ["config", "username", "storage"]
    if not all(k in st.session_state for k in required_keys):
        st.error("Sessione non inizializzata.")
        return
    
    # Trigger the primary tracking view logic
    show_questions_tracking()

if __name__ == "__main__":
    # Standard Python entry point for script execution
    show_page()