import json
import streamlit as st
import time

from assistant import Assistant

title = "DQL"
assistant = Assistant()

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
            show_expander(message.get("full_details", None))


def handle_user_input():
    """Manage user input and generate bot responses."""
    if prompt := st.chat_input("Scrivi un messaggio..."):
        # 1. Add and display the user's message
        st.session_state.messages.append({"role": "user", "content": prompt, "full_details": None})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. The assistant's response
        with st.chat_message("assistant"):
            with st.spinner("Sto pensando..."):
                result = assistant.chat(prompt)
                text = result.get("result", "")
            
            placeholder = st.empty()
            typed_text = ""
            for char in text:
                typed_text += char
                placeholder.markdown(typed_text)
                time.sleep(0.01)
                
            show_expander(result)

        # 3. Store the assistant's response in session state
        st.session_state.messages.append(
            {"role": "assistant", "content": text, "full_details": result}
        )

# --- EXPANDER ---
def show_expander(full_details):
    if full_details and full_details.get("structured_input", {}):
        with st.expander("Visualizza i dettagli"): 
            st.markdown(f"**Il comando strutturato identificato è:**")
            
            st.code(json.dumps(full_details.get("structured_input", {}), indent=4), language="json")
            
            operations = full_details.get("operations", [])

            if len(operations) > 1:
                st.markdown(f"Il comando è stato scomposto in **{len(operations)} operazioni**.")
                
                for index, operation in enumerate(operations, start=1):
                    st.divider()

                    st.markdown(f"### Operazione {index}: {operation.get('id', '')}")
                    
                    new_dict = {
                        "command": operation.get("command", ""),
                        "from": operation.get("from", []),
                    }
                    
                    if operation.get("what", ""):
                        new_dict["what"] = operation.get("what", "")
                        
                    if operation.get("how", ""):
                        new_dict["how"] = operation.get("how", "")

                    st.code(json.dumps(new_dict, indent=4), language="json")

                    st.markdown("**Risultato parziale:**")
                    st.code(operation.get("result", ""), language="markdown")
            else:
                st.markdown(f"Il comando non è stato necessario scomporlo.")


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
