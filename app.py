import socket
import streamlit as st
import time

from assistant import Assistant

title = "DQL"
assistant = Assistant()

id_user = socket.gethostbyname(socket.gethostname())

# --- PAGE CONFIGURATION ---
def configure_page():
    """Set up Streamlit page and apply custom CSS."""
    st.set_page_config(
        page_title=title,
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # --- Custom CSS for Layout ---
    st.markdown("""
    <style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    /* Hide Streamlit's default header */
    header {
        visibility: hidden;
        height: 0;
    }

    /* Adjust chat message width and center them */
    [data-testid="stChatMessage"] {
        width: auto;
        margin-top: 0 auto;
        margin-bottom: 0 auto;
        margin-left: 50px;
        margin-right: 50px;
    }
    
    h1 {
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)


# --- CHAT HANDLING ---
def initialize_chat():
    """Initialize chat history if it doesn't exist."""
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Ciao! Come posso aiutarti oggi?"}
        ]


def display_chat_history():
    """Display all previous chat messages."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def handle_user_input():
    """Manage user input and generate bot responses."""
    if prompt := st.chat_input("Scrivi un messaggio..."):
        # 1. Add and display the user's message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. The assistant's response
        with st.chat_message("assistant"):
            with st.spinner("Sto pensando..."):
                response = assistant.chat(prompt, id_user)
            
            placeholder = st.empty()
            typed_text = ""
            for char in response:
                typed_text += char
                placeholder.markdown(typed_text)
                time.sleep(0.01)

        # 3. Store the assistant's response in session state
        st.session_state.messages.append(
            {"role": "assistant", "content": response}
        )


# --- SIDEBAR ---
def render_sidebar():
    """Render the sidebar with optional app settings."""
    with st.sidebar:
        st.header("Impostazioni")
        st.write("")


# --- MAIN FUNCTION ---
def main():
    """Main entry point for the Streamlit app."""
    configure_page()
    st.title(title)

    initialize_chat()
    display_chat_history()
    handle_user_input()
    render_sidebar()


# --- ENTRY POINT ---
if __name__ == "__main__":
    main()
