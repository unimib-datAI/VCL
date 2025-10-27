import json
import html
import markdown
import os
import re
import streamlit as st
import threading
import time
import queue

from assistant import Assistant

title = "DQL"

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
            placeholder = st.empty()
            
            stop_event = threading.Event()
            result_queue = queue.Queue()
            
            assistant = Assistant()
            
            t1 = threading.Thread(target=call_assistant, args=(prompt, assistant, stop_event, result_queue))
            t1.start()
            
            log_list = []
        
            log_file = os.path.join(assistant.CFG.project_root, "logs", f"{assistant.get_request_id()}.log")
            log_lines = follow_log(log_file, stop_event) 
            
            for line in log_lines: 
                log_list.append(line.strip()) 
                placeholder.markdown("\n\n".join(log_list).strip()) 
                if stop_event.is_set():
                    placeholder.markdown("")
                    break

            t1.join()
            
            result = result_queue.get()
            text = result.get("result", "")
            
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
        
def call_assistant(prompt: str, assistant, stop_event, result_queue):
    result_queue.put(assistant.chat(prompt))
    stop_event.set()
    
    
def follow_log(file_path, stop_event, wait_time = 0.05):
    while not (os.path.exists(file_path) or stop_event.is_set()):
        continue
    
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            f.seek(0, 2)
            while not stop_event.is_set():
                line = f.readline()
                if not line:
                    continue
                yield line
     
# --- EXPANDER ---
def show_expander(full_details):
    if full_details and full_details.get("structured_input", {}):
        with st.expander("Visualizza i dettagli"):
            operations = full_details.get("operations", [])
            
            if len(operations) > 1:
                op_string = f"Il comando è stato scomposto in {len(operations)} operazioni."
            else:
                op_string = "Il comando non è stato necessario scomporlo."
            
            st.markdown(f"""
                <details style="margin-left:20px; margin-top:10px;">
                    <summary>Introduzione</summary>
                    Il comando identificato per la richiesta è stato:
                    <pre><code class="language-json">{json.dumps(full_details.get("structured_input", {}), indent=4)}</code></pre>
                    {op_string}
                </details>
            """, unsafe_allow_html=True)
        
            for index, operation in enumerate(operations, start=1):
                new_dict = {
                    "command": operation.get("command", ""),
                    "from": operation.get("from", []),
                }
                        
                if operation.get("what", ""):
                    new_dict["what"] = operation.get("what", "")
                    
                if operation.get("how", ""):
                    new_dict["how"] = operation.get("how", "")
                            
                operation_json = json.dumps(new_dict, indent=4)
                html_text = str(html.escape(markdown.markdown(operation.get("result", ""))))
                operation_result = str(re.sub(r'<[^>]+>', '', html_text).strip())

                st.markdown(f"""
                <details style="margin-left:20px; margin-top:10px;">
                    <summary>Operazione {index}:</b> {operation.get('command', '')} - {operation.get('id', '')}</summary>
                    <pre><code class="language-json">{operation_json}</code></pre>
                    <b>Risultato Parziale:</b>
                    <details style="margin-left:20px; margin-top:10px;">
                        <summary>Visualizza il testo</summary>
                        <pre style="white-space: pre-wrap; word-break: break-word;">
                            <code class="language-plaintext">
                                {operation_result}
                            </code>
                        </pre>
                    </details>
                </details>
                """, unsafe_allow_html=True)
            
            st.markdown("</details>", unsafe_allow_html=True)
            

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
