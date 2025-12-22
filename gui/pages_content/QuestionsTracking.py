import streamlit as st
from datetime import datetime

def show_questions_tracking():
    st.title("📊 Tracking delle Domande")

    # --- Leggi domande dal DB ---
    try:
        db = st.session_state.storage._questions  # la collection
        cursor = db.find({"user": st.session_state.username}).sort("timestamp", -1)
        rows = list(cursor)
    except Exception as e:
        st.error(f"Errore nel caricamento delle domande: {e}")
        return

    if not rows:
        st.info("Nessuna domanda tracciata.")
        return

    # --- Trasforma in tabella ---
    table = []
    for r in rows:
        table.append({
            "Data/Ora": r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "Domanda": r["question"],
            "Modello": r.get("model", "-"),
        })

    st.dataframe(table, width='stretch')

# Entry point della pagina
def show_page():
    
    # Controlli iniziali
    required_keys = ["config", "username", "storage"]
    if not all(k in st.session_state for k in required_keys):
        st.error("Sessione non inizializzata.")
        return
    
    show_questions_tracking()

if __name__ == "__main__":
    show_page()