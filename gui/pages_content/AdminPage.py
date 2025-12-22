import re
import streamlit as st

from copy import deepcopy

PAGE_TITLE = "Admin Dashboard"

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
        role = st.radio(
            "Qual è il tuo ruolo?",
            ["Giudice", "Avvocato", "Admin", "Altro"]
        )
        
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

def show_admin():
    st.title(PAGE_TITLE)
    
    # Controlli iniziali
    required_keys = ["config", "username", "role"]
    if not all(k in st.session_state for k in required_keys):
        st.error("Sessione non inizializzata.")
        return
    
    if st.session_state.role != "Admin":
        st.error("Accesso negato. Solo gli amministratori possono accedere a questa pagina.")
        return
    
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