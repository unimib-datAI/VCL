import os
import json
import html
import markdown
import sys
import threading
import time
import queue
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Generator

import streamlit as st

# Add Root Directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

APP_TITLE = "DQL"

# ---------------------------
# --- Chat Initialization ---
# ---------------------------

def _initialize_chat() -> None:
    """
    Initialize the chat session state by retrieving history from storage.
    Sets a default greeting message if the history is empty.
    """ 
    st.session_state.messages = st.session_state.assistant.get_storage().get_chat_messages(
        st.session_state.username,
        st.query_params.chat
    )
    
    first_message = [
        {
            "role": "assistant",
            "content": "Ciao! Come posso aiutarti oggi?",
            "time": datetime.now().isoformat()
        }
    ]
    
    if "messages" not in st.session_state or not st.session_state.messages:
        st.session_state.messages = first_message
        _save_messages(st.session_state.messages)

# --------------------
# --- Chat History ---
# --------------------

def _display_chat_history() -> None:
    """
    Iterates through session messages and renders them in the UI.
    """
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            _show_expander(message)

# ---------------------------
# --- Chat Input Handling ---
# ---------------------------

def _handle_suggestions_and_controls() -> Optional[str]:
    """
    Renders the top control bar (Suggestions, New Chat, Delete Chat).
    
    Returns:
        Optional[str]: A prompt string if a suggestion is clicked, otherwise None.
    """
    col1, col2, col3 = st.columns([0.70, 0.15, 0.15])
    prompt_selected = None
    
    # Col 1: Suggestions
    with col1:
        # Retrieve stored suggestion trigger if page reloaded
        prompt_from_button = st.session_state.pop("prompt_from_button", None)
        if prompt_from_button:
            prompt_selected = prompt_from_button

        with st.popover("💡 Suggerimenti"):
            st.markdown("Prova a chiedere:")
            if st.session_state.assistant:
                for i, suggestion in enumerate(st.session_state.assistant.get_language().gui_examples):
                    if st.button(suggestion, key=f"suggestion_{i}"):
                        st.session_state.prompt_from_button = suggestion
                        st.rerun()
            else:
                st.info("Caricamento configurazione...")
    
    # Col 2: New Chat
    with col2:
        if st.button("📝 Nuova conversazione"):
            st.query_params.chat = st.session_state.authenticator.create_new_chat(st.session_state.username)
            st.rerun()
        
    # Col 3: Delete Chat
    with col3:
        if st.button("❌ Elimina conversazione"):
            st.session_state.authenticator.delete_chat(st.session_state.username, st.query_params.chat)
            
            all_keys = st.session_state.authenticator.get_all_chats(st.session_state.username).keys()
            all_keys = sorted(all_keys, reverse=True)
            
            if not all_keys:
                st.query_params.chat = st.session_state.authenticator.create_new_chat(st.session_state.username)
            else:
                st.query_params.chat = all_keys[0]
                
            st.rerun()

    return prompt_selected

def _display_gui_components() -> None:
    """
    Main render function for the chat interface components.
    """
    # 1. Controls & Suggestions
    suggestion_prompt = _handle_suggestions_and_controls()

    # 2. History
    _display_chat_history()

    # 3. Input
    chat_prompt = st.chat_input("Scrivi un messaggio...")

    # Determine if we have a prompt to process
    prompt_to_submit = suggestion_prompt or chat_prompt
    
    if prompt_to_submit:
        _submit_prompt(prompt_to_submit)

def _submit_prompt(prompt: str) -> None:
    """
    Orchestrates the user prompt submission: updates UI, calls assistant thread,
    handles log streaming, and saves results.

    Args:
        prompt (str): The user's prompt.
    """
    # --- 1. Display user's message ---
    user_msg = {
        "role": "user", 
        "content": prompt,
        "time": datetime.now().isoformat()
    }
    st.session_state.messages.append(user_msg)
    
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- 2. Handle assistant's response ---
    with st.chat_message("assistant"):
        placeholder = st.empty()
        stop_event = threading.Event()
        result_queue = queue.Queue()
        
        st.session_state.assistant.get_cfg().generate_request_id()
        
        # Start Assistant in background thread
        thread = threading.Thread(
            target=_call_assistant_thread, 
            args=(prompt, st.session_state.username, st.query_params.chat, st.session_state.assistant, stop_event, result_queue)
        )
        thread.start()

        # Stream logs while waiting
        log_list = _stream_logs_to_ui(placeholder, stop_event)

        # Ensure thread completion
        thread.join()
        
        # Retrieve result
        result = result_queue.get()
        
        if "details" not in result.keys():
            result["details"] = {}
            
        # Add Logs to session state
        result["logs"] = log_list[1:]
        
        # Render final output
        _typewriter_effect(
            result.get("content", ""), 
            placeholder
        )
        _show_expander(result)
        
        st.session_state.messages.append(result)
    
    # --- 3. Persist messages ---
    # Save only the last exchange (user + assistant)
    _save_messages(st.session_state.messages[-2:])

# -------------------------------
# --- Threading & Log Helpers ---
# -------------------------------

def _call_assistant_thread(prompt: str, user_id, chat_id: str, assistant, stop_event: threading.Event, result_queue: queue.Queue) -> None:
    """
    Wrapper to run the heavy assistant logic in a thread.
    """
    try:
        response = assistant.chat(prompt, user_id, chat_id)
        result_queue.put(response)
    except Exception as e:
        result_queue.put({"result": f"Error: {str(e)}"})
    finally:
        stop_event.set()

def _stream_logs_to_ui(placeholder, stop_event: threading.Event) -> List[str]:
    """
    Follows the log file and updates the UI placeholder until the stop_event is set.
    
    Returns:
        List[str]: Collected log lines.
    """
    log_file = os.path.join(
        st.session_state.assistant.get_cfg().project_root, 
        "logs", 
        f"{st.session_state.assistant.get_cfg().get_request_id()}.log"
    )
    
    log_list = ["LOGS:"]
    
    # Generator yields lines from file
    for line in _follow_log_generator(log_file, stop_event):
        log_list.append(line)
        # Update UI with current logs
        placeholder.markdown("\n\n".join(log_list).strip())
        
        if stop_event.is_set():
            placeholder.markdown("") # Clear logs from main view when done
            break
            
    return log_list

def _follow_log_generator(file_path: str, stop_event: threading.Event, wait_time: float = 0) -> Generator[str, None, None]:
    """
    Generator that reads a log file like 'tail -f'.
    """
    # Wait for file creation
    while not (os.path.exists(file_path) or stop_event.is_set()):
        time.sleep(wait_time)

    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                f.seek(0, 2) # Optional: Start at end if we only want new logs. 
                # Since file is new per request, starting at 0 is fine.
                
                while not stop_event.is_set():
                    line = f.readline()
                    if not line:
                        time.sleep(wait_time)
                        continue
                    
                    # Clean up log lines for display
                    for label in ["INFO", "ERROR", "WARNING"]:
                        if f"- {label} -" in line:
                            line = line.split(f"- {label} -", 1)[-1].strip()

                    yield f"\t{line}"
        except Exception:
            yield "\t (Errore lettura log)"

def _typewriter_effect(text: str, placeholder) -> None:
    """Simulates typing effect for the assistant response."""
    typed_text = ""
    for char in text:
        typed_text += char
        placeholder.markdown(typed_text)
        time.sleep(0.01)

# ------------------------------
# --- UI Details (Expanders) ---
# ------------------------------

def _show_expander(message: Dict) -> None:
    """
    Renders the details expander containing input structure, operations, and logs.
    """
    details = message.get("details", {}) if message else {}
    
    prompt = details.get("prompt", "")
    tasks = details.get("tasks", [])
    logs = details.get("logs", [])
    
    if not (message and details and tasks):
        return

    with st.expander("Visualizza i dettagli"):
        if len(tasks) > 1:
            op_count_str = f"La richiesta è stata scomposta in {len(tasks)} tasks."
        else:
            op_count_str = "La richiesta non è stata scomposta."

        # 1. Structured Input
        # command_json = json.dumps(full_details.get("structured_input", {}), indent=4)
        # Il comando identificato per la richiesta è stato:
        # <pre><code class="language-json">{command_json}</code></pre>
        
        st.markdown(
            f"""
            L'utente ha richiesto \"{prompt}\".
            <p></p>
            {op_count_str}
            """,
            unsafe_allow_html=True,
        )

        # 2. Operations
        _display_task(tasks)
        
        # 3. Logs
        if logs:
            text_escaped = html.escape("\n".join([l.strip() for l in logs]).strip())
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
        
def _display_task(tasks: list) -> None:
    """Renders a single operation detail block."""
    for index, task in enumerate(tasks, start=1):
        structured_prompt = task.get("structured_prompt", {})
        
        # Create a clean subset for display
        display_dict = {
            "command": structured_prompt.get("command", ""),
            "from": structured_prompt.get("from", []),
        }
        
        for key in ["what", "how"]:
            if structured_prompt.get(key, None):
                display_dict[key] = structured_prompt[key]

        task_json = json.dumps(display_dict, indent=4)
        task_result = markdown.markdown(task.get("result", ""))
        
        operation = [_display_operation(i, t) for i, t in enumerate(task.get("operations", []))]
        
        html_code = [
            '<details style="margin-left:20px; margin-top:10px;">',
            '\t' + f'<summary>Task {index}: {task.get('prompt', '')}</summary>' if len(tasks) == 1 else '\t <summary>Comando DQL</summary>',
            '\t<p></p>',
            '\t' + f'<pre><code class="language-json">{task_json}</code></pre>'
        ]
        
        for o in operation:
            for r in o:
                html_code.append("\t" + r)
        
        html_code.append('</details>')
        
        if len(tasks) != 1:
            html_code.append('\t<details style="margin-left:20px; margin-top:10px;">')
            html_code.append('\t\t<summary>Risultato Parziale</summary>')
            html_code.append('\t\t<div style="margin:10px; padding:10px; border:1px solid #ccc; border-radius:8px;">')
            html_code.append('\t\t\t' + task_result)
            html_code.append('\t\t</div>')
            html_code.append('\t</details>')
        
        html_code.append('</details>')
            
        st.markdown(
            "\n".join([h for h in html_code if h.strip()]),
            unsafe_allow_html=True,
        )

def _display_operation(index: int, operation: Dict) -> None:
    """Renders a single operation detail block."""
    
    structured_prompt = operation.get("structured_prompt", {})
    
    # Create a clean subset for display
    display_dict = {
        "command": structured_prompt.get("command", ""),
        "from": structured_prompt.get("from", []),
    }
    for key in ["what", "how"]:
        if structured_prompt.get(key):
            display_dict[key] = structured_prompt.get(key)

    operation_json = json.dumps(display_dict, indent=4)
    operation_result = markdown.markdown(operation.get("result", ""))

    return [
        '<details style="margin-left:20px; margin-top:10px;">',
        '\t' + f'<summary>Operazione {index}: {operation.get('command', '')}</summary>',
        '\t<p></p>',
        '\t' + f'<pre><code class="language-json">{operation_json}</code></pre>',
        '\t<b>Risultato Parziale:</b>',
        '\t<details style="margin-left:20px; margin-top:10px;">',
        '\t\t<summary>Visualizza il testo</summary>',
        '\t\t<div style="margin:10px; padding:10px; border:1px solid #ccc; border-radius:8px;">',
        '\t\t\t' + operation_result,
        '\t\t</div>',
        '\t</details>',
        '</details>'
    ]

def _save_messages(messages: List[Dict]) -> None:
    """Helper to persist messages to storage."""
    if "assistant" in st.session_state and st.session_state.username:
        for message in messages:
            st.session_state.assistant.get_storage().add_chat_message(
                st.session_state.username,
                st.query_params.chat,
                message
            )

# -------------------
# --- Entry Point ---
# -------------------

def show_home():
    """
    Main page entry point.
    """
    # Guard clause for missing state
    required_keys = ["assistant", "username", "authenticator"]
    if not all(hasattr(st.session_state, k) and getattr(st.session_state, k) for k in required_keys) or not st.query_params.get("chat"):
        st.warning("Inizializzazione della configurazione in corso... Ricarica se il messaggio persiste.")
        st.stop()

    _initialize_chat()
    _display_gui_components()

if __name__ == "__main__":
    show_home()