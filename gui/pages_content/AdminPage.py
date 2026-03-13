import streamlit as st
import pandas as pd
from copy import deepcopy

# Page configuration constant
PAGE_TITLE = "Admin Dashboard"

MODEL_LABELS = {
    "DQL": "DQL",
    "GPT": "GPT",
    "NotebookLM": "NotebookLM",
    "BattleAnon": "Battle (anonimo)",
    "BattleLabeled": "Battle (etichettato)",
}

def _scores_summary_to_df(scores: dict) -> pd.DataFrame:
    """
    Atteso:
    {
      "by_model": {
        "DQL": {"wins": 10, "losses": 6, "matches": 16, "win_rate": 0.625},
        ...
      },
      "total_matches": 16
    }
    """
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


def show_user_info():
    st.subheader("Elenco Utenti Registrati")

    users = deepcopy(st.session_state.storage.get_all_users())

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("Ricarica Utenti", width='stretch'):
            st.rerun()

    with col2:
        if st.button("Aggiungi Nuovo Utente", width='stretch'):
            st.session_state.admin_action = "register_info"
            st.rerun()

    with col3:
        if st.button("Rimuovi Utente", width='stretch'):
            st.session_state.admin_action = "delete_user"
            st.rerun()

    users = [{
        "Username": u["username"],
        "Email": u["email"],
        "Ruolo": u.get("role", "N/A"),
    } for u in users]

    st.dataframe(users, width='stretch')


def show_user_registration():
    st.subheader("Aggiungi Nuovo Utente")

    with st.form("Registrati"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        role = st.radio("Qual è il tuo ruolo?", ["Giudice", "Avvocato", "Admin", "Altro"])

        if st.form_submit_button("Registrati"):
            username = username.strip()
            email = email.strip()
            password = password.strip()

            result, user = st.session_state.storage.register_user(username, email, password, role)

            if result and user:
                st.success("Registrazione avvenuta con successo!")
                del st.session_state.admin_action
                st.rerun()
            else:
                if isinstance(user, str):
                    st.error(user)
                else:
                    st.error("Username/Email non disponibili")


def show_delete_user():
    st.subheader("Rimuovi Utente")

    users = st.session_state.storage.get_all_users()
    usernames = [user["username"] for user in users]

    selected_user = st.selectbox("Seleziona l'utente da rimuovere", usernames)

    if st.button("Rimuovi Utente", width='stretch'):
        if selected_user:
            if selected_user == st.session_state.username:
                st.error("Non puoi rimuovere te stesso.")
            else:
                result = st.session_state.storage.delete_user(selected_user)
                if result:
                    st.success(f"Utente '{selected_user}' rimosso con successo.")
                    del st.session_state.admin_action
                    st.rerun()
                else:
                    st.error("Errore nella rimozione dell'utente.")
        else:
            st.error("Seleziona un utente valido.")


def _show_battle_scores_admin():
    st.subheader("📊 Battle Scores (tutti gli utenti)")

    storage = st.session_state.storage

    if not hasattr(storage, "get_battle_scores_summary"):
        st.warning(
            "Lo Storage non espone ancora `get_battle_scores_summary(...)`.\n"
            "Aggiorna lo Storage con il codice che ti ho fornito."
        )
        return

    mode_ui = st.selectbox("Modalità", ["All", "BattleAnon", "BattleLabeled"], index=0)

    # Mapping UI -> storage (tu salvi 'anon' / 'labeled')
    if mode_ui == "All":
        mode_filter = None
    elif mode_ui == "BattleAnon":
        mode_filter = "anon"
    else:
        mode_filter = "labeled"

    # ---- Globale ----
    scores_global = storage.get_battle_scores_summary(user_id=None, mode=mode_filter)
    total_global = scores_global.get("total_matches", 0)
    st.caption(f"Totale match registrati: {total_global}")
    st.dataframe(_scores_summary_to_df(scores_global), use_container_width=True, hide_index=True)

    st.divider()

    # ---- Per utente ----
    st.subheader("👤 Breakdown per utente")

    users = storage.get_all_users() or []
    usernames = sorted([u.get("username") for u in users if u.get("username")])

    if not usernames:
        st.info("Nessun utente disponibile.")
        return

    selected_user = st.selectbox("Seleziona utente", usernames, index=0)

    scores_user = storage.get_battle_scores_summary(user_id=selected_user, mode=mode_filter)
    total_user = scores_user.get("total_matches", 0)
    st.caption(f"Match di {selected_user}: {total_user}")
    st.dataframe(_scores_summary_to_df(scores_user), use_container_width=True, hide_index=True)


def show_admin():
    st.title(PAGE_TITLE)

    required_keys = ["config", "username", "role"]
    if not all(k in st.session_state for k in required_keys):
        st.error("Sessione non inizializzata.")
        return

    if st.session_state.role != "Admin":
        st.error("Accesso negato. Solo gli amministratori possono accedere a questa pagina.")
        return

    tab_users, tab_scores = st.tabs(["👥 Utenti", "📊 Battle Scores"])

    with tab_users:
        if "admin_action" not in st.session_state:
            show_user_info()
        else:
            action = st.session_state.admin_action
            if action == "register_info":
                show_user_registration()
            elif action == "delete_user":
                show_delete_user()
            else:
                del st.session_state.admin_action
                show_user_info()

    with tab_scores:
        _show_battle_scores_admin()
