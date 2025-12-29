import re
import streamlit as st

from copy import deepcopy

# Page configuration constant
PAGE_TITLE = "Admin Dashboard"

def show_user_info():
    """
    Displays the list of registered users in a dataframe and provides
    navigation buttons to trigger administrative actions.
    """
    st.subheader("Elenco Utenti Registrati")
    
    # Retrieve a deep copy of all users from the storage to prevent accidental state mutation
    users = deepcopy(st.session_state.storage.get_all_users())
    
    # Define layout columns for navigation buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Refreshes the current view
        if st.button("Ricarica Utenti", width='stretch'):
            st.rerun()
            
    with col2:
        # Sets the session state to show the registration form
        if st.button("Aggiungi Nuovo Utente", width='stretch'):
            st.session_state.admin_action = "register_info"
            st.rerun()
            
    with col3:
        # Sets the session state to show the user deletion view
        if st.button("Rimuovi Utente", width='stretch'):
            st.session_state.admin_action = "delete_user"
            st.rerun()
    
    # Format the user data for display in the Streamlit dataframe
    users = [{
        "Username": u["username"],
        "Email": u["email"],
        "Ruolo": u.get("role", "N/A"),
    } for u in users]
    
    st.dataframe(users, width='stretch')

def show_user_registration():
    """
    Renders a registration form allowing admins to create new user accounts
    specifying username, email, password, and professional role.
    """
    st.subheader("Aggiungi Nuovo Utente")
    
    with st.form("Registrati"):
        # Form input fields for user credentials
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        role = st.radio(
            "Qual è il tuo ruolo?",
            ["Giudice", "Avvocato", "Admin", "Altro"]
        )
        
        # Form submission handling
        if st.form_submit_button("Registrati"):
            # Sanitize inputs by removing leading/trailing whitespace
            username = username.strip()
            email = email.strip()
            password = password.strip()
            
            # Attempt to register the user via the storage service
            result, user = st.session_state.storage.register_user(username, email, password, role)
            
            if result and user:
                st.success("Registrazione avvenuta con successo!")
                # Reset action state and refresh view
                del st.session_state.admin_action
                st.rerun()
            else:
                # Handle specific error messages or generic availability errors
                if isinstance(user, str):
                    st.error(user)
                else:
                    st.error("Username/Email non disponibili")
                    
def show_delete_user():
    """
    Displays a selection interface to delete an existing user from the database.
    Includes validation to prevent the current admin from deleting their own account.
    """
    st.subheader("Rimuovi Utente")
    
    # Fetch user list to populate the dropdown
    users = st.session_state.storage.get_all_users()
    usernames = [user["username"] for user in users]
    
    selected_user = st.selectbox("Seleziona l'utente da rimuovere", usernames)
    
    if st.button("Rimuovi Utente", width='stretch'):
        if selected_user:
            # Safety check: prevent self-deletion
            if selected_user == st.session_state.username:
                st.error("Non puoi rimuovere te stesso.")
            else:
                # Execute deletion through the storage service
                result = st.session_state.storage.delete_user(selected_user)
                if result:
                    st.success(f"Utente '{selected_user}' rimosso con successo.")
                    # Cleanup state and return to main dashboard view
                    del st.session_state.admin_action
                    st.rerun()
                else:
                    st.error("Errore nella rimozione dell'utente.")
        else:
            st.error("Seleziona un utente valido.")

def show_admin():
    """
    Main entry point for the Admin page. Manages routing between the dashboard,
    registration, and deletion views based on session state.
    """
    st.title(PAGE_TITLE)
    
    # Initial session validation: ensure required keys exist
    required_keys = ["config", "username", "role"]
    if not all(k in st.session_state for k in required_keys):
        st.error("Sessione non inizializzata.")
        return
    
    # Authorization check: only users with 'Admin' role can proceed
    if st.session_state.role != "Admin":
        st.error("Accesso negato. Solo gli amministratori possono accedere a questa pagina.")
        return
    
    # Logical routing based on 'admin_action' key
    if "admin_action" not in st.session_state:
        # Default view: list of users
        show_user_info()
    else:
        action = st.session_state.admin_action
        if action == "register_info":
            show_user_registration()
        elif action == "delete_user":
            show_delete_user()
        else:
            # Fallback for unrecognized actions: reset to main view
            del st.session_state.admin_action
            show_user_info()