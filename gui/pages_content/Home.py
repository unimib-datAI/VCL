import os
import json
import html
import markdown
import re
import streamlit as st
import sys
import threading
import time
import queue

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from logic.assistant import Assistant

APP_TITLE = "DQL"

# --------------------------
# --- Page Configuration ---
# --------------------------

# st.set_page_config() is called in app.py

# ---------------------------
# --- Chat Initialization ---
# ---------------------------

def initialize_chat():
    """
    Initialize the chat session state if not already set.
    """
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Ciao! Come posso aiutarti oggi?"}
        ]

# --------------------
# --- Chat History ---
# --------------------

def display_chat_history():
    """
    Display all previous chat messages stored in session state.
    """
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            show_expander(message.get("full_details", None), message.get("logs", []))


# ---------------------------
# --- Chat Input Handling ---
# ---------------------------

def handle_user_input():
    """
    Display and Handle user input from chat_input and suggestion buttons.
    """
    # --- Suggestion Button ---
    prompt_from_button = st.session_state.pop("prompt_from_button", None)

    with st.popover("💡 Suggerimenti"):
        st.markdown("Prova a chiedere:")
        
        # Ensure logic_config is loaded
        if st.session_state.logic_config:
            for i, suggestion in enumerate(st.session_state.logic_config.language.gui_examples):
                if st.button(suggestion, key=f"suggestion_{i}"):
                    st.session_state.prompt_from_button = suggestion
                    st.rerun()
        else:
            st.info("Caricamento configurazione...")
    
    # --- Chat History ---
    display_chat_history()

    # --- Chat Input ---
    chat_prompt = st.chat_input("Scrivi un messaggio...")

    prompt_to_submit = prompt_from_button or chat_prompt
    
    if prompt_to_submit:
        submit_prompt(prompt_to_submit)


def submit_prompt(prompt: str):
    """
    Sends the prompt to the assistant and handles displaying the response.
    This function contains the logic originally in handle_user_input.

    Args:
    prompt (str): The prompt text to send.
    """
    # --- 1. Display user's message ---
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "full_details": None, "logs": []}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- 2. Prepare Assistant response ---
    with st.chat_message("assistant"):
        placeholder = st.empty()

        # Threading setup
        stop_event = threading.Event()
        result_queue = queue.Queue()
        
        if not st.session_state.logic_config:
            st.error("Errore: Configurazione utente non caricata. Impossibile contattare l'assistente.")
            return

        assistant = Assistant(st.session_state.logic_config)

        # Run assistant logic in background
        thread = threading.Thread(
            target=call_assistant, args=(prompt, assistant, stop_event, result_queue)
        )
        thread.start()

        # Log streaming display
        log_file = os.path.join(
            assistant.CFG.project_root, "logs", f"{assistant.CFG.get_request_id()}.log"
        )
        log_list = ["LOGS:"]

        for line in follow_log(log_file, stop_event):
            log_list.append(line)
            placeholder.markdown("\n\n".join(log_list).strip())

            if stop_event.is_set():
                placeholder.markdown("")
                break

        thread.join()

        # --- 3. Display assistant's response with typing effect ---
        result = result_queue.get()
        text = result.get("result", "")

        typed_text = ""
        for char in text:
            typed_text += char
            placeholder.markdown(typed_text)
            time.sleep(0.01)

        show_expander(result, log_list[1:])

    # --- 4. Save assistant's response ---
    st.session_state.messages.append(
        {"role": "assistant", "content": text, "full_details": result, "logs": log_list[1:]}
    )

# -------------------------------
# --- Assistant Communication ---
# -------------------------------

def call_assistant(prompt: str, assistant, stop_event: threading.Event, result_queue: queue.Queue):
    """
    Execute the assistant call in a separate thread and signal completion.

    Args:
        prompt (str): The user's input message.
        assistant (Assistant): Assistant instance for handling the conversation.
        stop_event (threading.Event): Event used to signal completion.
        result_queue (queue.Queue): Queue to store the result for later retrieval.
    """
    result_queue.put(assistant.chat(prompt))
    stop_event.set()

# ----------------------------
# --- LOG Following in GUI ---
# ----------------------------

def follow_log(file_path: str, stop_event: threading.Event, wait_time: float = 0.05):
    """
    Continuously read and yield lines from a log file until stopped.

    Args:
        file_path (str): Path to the log file.
        stop_event (threading.Event): Event to stop reading.
        wait_time (float): Polling interval between file reads.

    Yields:
        str: New log lines as they appear.
    """
    # Wait until log file exists or stop event triggered
    while not (os.path.exists(file_path) or stop_event.is_set()):
        time.sleep(wait_time) # Aggiunto sleep per evitare busy-waiting

    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                f.seek(0, 2)  # Move to end of file
                while not stop_event.is_set():
                    line = f.readline()
                    if not line:
                        time.sleep(wait_time)
                        continue
                    
                    for label in ["INFO", "ERROR", "WARNING"]:
                        if f"- {label} -" in line:
                            line = line.split(f"- {label} -", 1)[-1].strip()

                    line = f"\t{line}"
                    
                    yield line
        except Exception:
            # There may be a race condition
            yield "\t (Errore lettura log)"

# ----------------------------------------------
# --- Expander in every assistant’s response ---
# ----------------------------------------------

def show_expander(full_details: dict, logs: list = []):
    """
    Display structured details and intermediate operations of the assistant’s response.

    Args:
        full_details (dict): Structured response details including operations, commands, and results.
    """
    if not (full_details and full_details.get("structured_input", {})):
        return

    with st.expander("Visualizza i dettagli"):
        operations = full_details.get("operations", [])
        if len(operations) > 1:
            op_string = f"Il comando è stato scomposto in {len(operations)} operazioni."
        else:
            op_string = "Il comando non è stato necessario scomporlo."

        # Show structured input overview
        command_json = json.dumps(full_details.get("structured_input", {}), indent=4)
        st.markdown(
            f"""
            <details style="margin-left:20px; margin-top:10px;">
                <summary>Introduzione</summary>
                Il comando identificato per la richiesta è stato:
                <p></p>
                <pre><code class="language-json">{command_json}</code></pre>
                {op_string}
            </details>
            """,
            unsafe_allow_html=True,
        )

        # Display operations (if multiple)
        if len(operations) > 1:
            for index, operation in enumerate(operations, start=1):
                display_operation(index, operation)

            st.markdown("</details>", unsafe_allow_html=True)
        
        # Display logs (if available)
        if len(logs) > 0:
            text = "\n".join([l.strip() for l in logs]).strip()
            # Escaping HTML
            text_escaped = html.escape(text)
            st.markdown(
                f"""
                <details style="margin-left:20px; margin-top:10px;">
                    <summary>Logs</summary>
                    <p></p>
                    <pre style="white-space: pre-wrap; word-break: break-word;">
                        <code class="language-plaintext">{text_escaped}</code>
                    </pre>
                </details>
                """,
                unsafe_allow_html=True,
            )
            
        st.markdown("\n", unsafe_allow_html=True)


def display_operation(index: int, operation: dict):
    """
    Render a single operation block inside the expander.

    Args:
        index (int): Sequential index of the operation.
        operation (dict): Operation data with command, inputs, and result.
    """
    new_dict = {
        "command": operation.get("command", ""),
        "from": operation.get("from", []),
    }

    # Include optional fields if present
    for key in ["what", "how"]:
        if operation.get(key, ""):
            new_dict[key] = operation.get(key, "")

    operation_json = json.dumps(new_dict, indent=4)
    html_text = str(html.escape(markdown.markdown(operation.get("result", ""))))
    operation_result = re.sub(r"<[^>]+>", "", html_text).strip()

    st.markdown(
        f"""
        <details style="margin-left:20px; margin-top:10px;">
            <summary>Operazione {index}: {operation.get('command', '')} - {operation.get('id', '')}</summary>
            <p></p>
            <pre><code class="language-json">{operation_json}</code></pre>
            <b>Risultato Parziale:</b>
            <details style="margin-left:20px; margin-top:10px;">
                <summary>Visualizza il testo</summary>
                <pre style="white-space: pre-wrap; word-break: break-word;">
                    <code class="language-plaintext">{operation_result}</code>
                </pre>
            </details>
        </details>
        """,
        unsafe_allow_html=True,
    )


# -------------------
# --- Entry Point ---
# -------------------

def show_home():
    """
    Main entry point for the Streamlit DQL app.
    Sets up layout, restores chat history, and handles user interactions.
    """

    # Verify that logic_config has been loaded correctly
    if not st.session_state.logic_config:
        st.warning("Inizializzazione della configurazione in corso... Ricarica se il messaggio persiste.")
        st.stop()

    initialize_chat()
    handle_user_input()

if __name__ == "__main__":
    show_home()