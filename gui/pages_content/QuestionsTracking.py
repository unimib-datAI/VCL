import streamlit as st
import pandas as pd

MODEL_LABELS = {
    "DQL": "DQL",
    "GPT": "GPT",
    "NotebookLM": "NotebookLM",
    "BattleAnon": "Battle (anonimo)",
    "BattleLabeled": "Battle (etichettato)",
}

def _scores_summary_to_df(scores: dict) -> pd.DataFrame:
    by_model = (scores or {}).get("by_model", {}) if isinstance(scores, dict) else {}
    rows = []
    for model_key, stats in by_model.items():
        rows.append({
            "Model": MODEL_LABELS.get(model_key, model_key),
            "Wins": int(stats.get("wins", 0)),
            "Losses": int(stats.get("losses", 0)),
            "Matches": int(stats.get("matches", 0)),
            "Win rate (%)": round(float(stats.get("win_rate", 0.0)) * 100.0, 2),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Win rate (%)", "Wins", "Matches"], ascending=False)
    return df


def _render_questions_log():
    st.subheader("🧾 Storico domande (tutti i modelli)")

    try:
        db = st.session_state.storage._questions
        cursor = db.find({"user": st.session_state.username}).sort("timestamp", -1)
        rows = list(cursor)
    except Exception as e:
        st.error(f"Errore nel caricamento delle domande: {e}")
        return

    if not rows:
        st.info("Nessuna domanda tracciata.")
        return

    table = []
    for r in rows:
        table.append({
            "Data/Ora": r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "Domanda": r.get("question", ""),
            "Modello": MODEL_LABELS.get(r.get("model", "-"), r.get("model", "-")),
        })

    st.dataframe(table, use_container_width=True, hide_index=True)


def _render_battle_scores():
    st.subheader("⚔️ Punteggi Battle (solo tue domande)")

    storage = st.session_state.storage
    if not hasattr(storage, "get_battle_scores_summary"):
        st.warning("Lo Storage non espone `get_battle_scores_summary`. Aggiorna lo Storage con la versione nuova.")
        return

    mode_ui = st.selectbox("Modalità Battle", ["All", "BattleAnon", "BattleLabeled"], index=0)

    # Mapping UI -> storage mode (tu salvi 'anon' / 'labeled')
    if mode_ui == "All":
        mode_filter = None
    elif mode_ui == "BattleAnon":
        mode_filter = "anon"
    else:
        mode_filter = "labeled"

    scores = storage.get_battle_scores_summary(user_id=st.session_state.username, mode=mode_filter)
    total = scores.get("total_matches", 0)
    st.caption(f"Totale match: {total}")
    st.dataframe(_scores_summary_to_df(scores), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🗳️ Ultimi voti battle")

    if not hasattr(storage, "get_battle_results"):
        st.info("Per vedere la lista degli ultimi voti, aggiungi anche `get_battle_results(...)` nello Storage.")
        return

    results = storage.get_battle_results(user_id=st.session_state.username, mode=mode_filter, limit=100)
    if not results:
        st.info("Nessun voto battle registrato.")
        return

    # pulizia campi per UI
    table = []
    for r in results:
        ts = r.get("timestamp")
        if hasattr(ts, "strftime"):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts_str = str(ts) if ts else "-"

        model_a = r.get("model_a", "-")
        model_b = r.get("model_b", "-")
        chosen = r.get("chosen_model", "-")

        table.append({
            "Data/Ora": ts_str,
            "Chat": r.get("chat_id", "-"),
            "Battle ID": r.get("battle_id", "-"),
            "Modalità": r.get("mode", "-"),
            "Confronto": f"{model_a} vs {model_b}",
            "Vincitore scelto": chosen,
            "Side": r.get("chosen_side", "-"),
            "Prompt": r.get("prompt", ""),
        })

    st.dataframe(table, use_container_width=True, hide_index=True)


def show_questions_tracking():
    st.title("📊 Tracking delle Domande")

    required_keys = ["config", "username", "storage"]
    if not all(k in st.session_state for k in required_keys):
        st.error("Sessione non inizializzata.")
        return

    tab1, tab2 = st.tabs(["🧾 Domande", "⚔️ Battle Scores"])

    with tab1:
        _render_questions_log()

    with tab2:
        _render_battle_scores()


def show_page():
    show_questions_tracking()


if __name__ == "__main__":
    show_page()