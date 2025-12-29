import streamlit as st
from logic.orchestrator import Orchestrator

# Application constant for the login page title
PAGE_TITLE = "Benvenuto in DQL!"

def _initialize_user_session(user: dict):
    """
    Sets up the global session state after a successful login or registration.
    
    This function populates the user credentials, updates the configuration 
    logic with role-based settings, and triggers a full page rerun to 
    activate the authenticated UI.

    Args:
        user (dict): A dictionary containing user details (username, role, etc.) 
                     retrieved from the storage backend.
    """
    # Store core user identity in session state
    st.session_state.username = user["username"]
    st.session_state.role = user["role"]
    
    # Update the central configuration object with authenticated user info
    st.session_state.config.handle_login(
        st.session_state.username, 
        st.session_state.role
    )
    
    # Grant authentication access
    st.session_state.auth_status = True
    
    # Force a rerun to refresh the application layout with new auth status
    st.rerun()

def show_login():
    """
    Renders the login interface using a Streamlit form.
    Handles credential validation by interfacing with the storage service
    and coordinates the transition to the authenticated state.
    """
    st.title(PAGE_TITLE)

    # Use a form to group inputs and handle submission with the 'Enter' key
    with st.form("Login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        # Form submission logic
        if st.form_submit_button("Login"):
            # Attempt to authenticate through the storage provider
            # Input is stripped of whitespace to prevent common entry errors
            result, user = st.session_state.storage.login_user(
                username.strip(), 
                password.strip()
            )
            
            if result and user:
                st.success("Login avvenuto con successo!")
                # Transition to user session initialization
                _initialize_user_session(user)
            else:
                # Provide feedback for failed authentication attempts
                st.error("Username/Password errati")

    # The following sections for registration are currently disabled (commented out)
    # but kept as structural placeholders for future navigation logic.
    
    # st.markdown("---")
    # if st.button("Non hai ancora un account? Registrati!", width='stretch'):
    #     st.query_params["page"] = "Registration"
    #     st.rerun()