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

from openai import OpenAI
import docx

# Add Root Directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

LEGAL_DOCS_DIR = ROOT_DIR / "documents"

APP_TITLE = "DQL"

# --- Modelli disponibili (UI) ---
MODEL_LABELS = {
    "DQL": "DQL",
    "GPT": "GPT",
    "NotebookLM": "NotebookLM (coming soon)",
    "Copilot": "Copilot (coming soon)",
}

DEFAULT_MODEL = "DQL"

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
            _show_expander(message.get("full_details", None), message.get("logs", []))

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
    # 0. Selettore modello
    selected_model = _render_model_selector()

    # 1. Controls & Suggestions
    suggestion_prompt = _handle_suggestions_and_controls()

    # 2. History
    _display_chat_history()

    # 3. Input
    chat_prompt = st.chat_input("Scrivi un messaggio...")

    # Determine if we have a prompt to process
    prompt_to_submit = suggestion_prompt or chat_prompt
    
    if prompt_to_submit:
        _submit_prompt(prompt_to_submit, selected_model)

def _submit_prompt(prompt: str, selected_model: str) -> None:
    """
    Orchestrates the user prompt submission: updates UI, calls assistant thread,
    handles log streaming, and saves results.

    Args:
        prompt (str): The user's prompt.
        selected_model (str): Selected engine key (e.g. 'DQL', 'GPT', ...)
    """
    # --- 1. Display user's message ---
    user_msg = {
        "role": "user", 
        "content": prompt,
        "time": datetime.now().isoformat(),
        "model": selected_model,
    }
    st.session_state.messages.append(user_msg)

    # --- USER QUESTION TRACKING ---
    try:
        storage = st.session_state.assistant.get_storage()
        storage.log_user_question(
            user_id=st.session_state.username,
            question=prompt,
            model=selected_model,
        )
    except Exception as e:
        print(f"[WARN] Impossibile tracciare domanda utente: {e}")
    
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- 2. Handle assistant's response ---
    with st.chat_message("assistant"):
        placeholder = st.empty()
        stop_event = threading.Event()
        result_queue = queue.Queue()
        
        st.session_state.assistant.get_cfg().generate_request_id()
        
        # Start Assistant in background thread
        assistant = st.session_state.assistant
        username = st.session_state.username

        thread = threading.Thread(
            target=_call_assistant_thread, 
            args=(prompt, selected_model, assistant, username, stop_event, result_queue),
        )
        thread.start()

        # Stream logs while waiting
        log_list = _stream_logs_to_ui(placeholder, stop_event)

        # Ensure thread completion
        thread.join()
        
        # Retrieve result
        result = result_queue.get()
        text = result.get("result", "")
        
        # Render final output
        _typewriter_effect(text, placeholder)
        _show_expander(result, log_list[1:]) # Skip the "LOGS:" header
        
        # Append to session state
        assistant_msg = {
            "role": "assistant", 
            "content": text,
            "time": datetime.now().isoformat(),
            "full_details": result, 
            "logs": log_list[1:],
            "model": selected_model,
        }
        st.session_state.messages.append(assistant_msg)
    
    # --- 3. Persist messages ---
    # Save only the last exchange (user + assistant)
    _save_messages(st.session_state.messages[-2:])

# ---------------------------
# -- Render Model Selector --
# ---------------------------
def _render_model_selector() -> str:
    """
    Rende il selettore del modello da interrogare e lo salva in session_state.

    Ritorna:
        str: il modello selezionato (chiave in MODEL_LABELS)
    """
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = DEFAULT_MODEL

    # Piccolo titolo sopra il selettore
    st.markdown("### Seleziona il motore da interrogare")

    # UI del selettore (radio orizzontale)
    selected = st.radio(
        "Motore",
        options=list(MODEL_LABELS.keys()),
        format_func=lambda k: MODEL_LABELS[k],
        index=list(MODEL_LABELS.keys()).index(st.session_state.selected_model),
        horizontal=True,
    )

    st.session_state.selected_model = selected
    return selected

# -------------------------------
# --- Threading & Log Helpers ---
# -------------------------------

def _call_assistant_thread(prompt: str, selected_model: str, assistant, username: str, stop_event: threading.Event, result_queue: queue.Queue) -> None:
    """
    Wrapper to run the heavy assistant logic in a thread.
    """
    try:
        response = _call_model(prompt, selected_model, assistant, username)
        result_queue.put(response)
    except Exception as e:
        result_queue.put({"result": f"Error: {str(e)}"})
    finally:
        stop_event.set()

def _load_case_documents(assistant, username: str) -> List[Dict[str, str]]:
    """
    Recupera i documenti utente da Mongo tramite assistant.storage
    SENZA usare st.session_state (che non è thread-safe).
    """
    docs = []

    storage = assistant.get_storage()
    raw_docs = storage.get_all_documents(username) or []

    TEXT_KEYS = ["text", "contenuto", "content", "body"]
    NAME_KEYS = ["name", "titolo", "filename"]
    TYPE_KEYS = ["type_doc", "tipo_documento", "tipo"]

    for doc in raw_docs:
        type_doc = next((doc.get(k, "").strip() for k in TYPE_KEYS if doc.get(k)), "")
        name = next((doc.get(k, "").strip() for k in NAME_KEYS if doc.get(k)), "")
        text = next((doc.get(k, "").strip() for k in TEXT_KEYS if doc.get(k)), "")

        if not text:
            continue  # documento vuoto → skip

        label = (
            f"{type_doc} ({name})" if type_doc and name
            else type_doc or name or "Documento senza nome"
        )

        docs.append({
            "label": label,
            "filename": name or label,
            "text": text
        })

    return docs


def _ask_gpt(prompt: str, assistant, username: str) -> Dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "result": (
                "⚠️ OPENAI_API_KEY non impostata.\n"
                "Imposta la variabile d'ambiente OPENAI_API_KEY per usare GPT."
            )
        }

    try:
        client = OpenAI(api_key=api_key)

        # 1) Documenti dal Mongo via Storage
        case_docs = _load_case_documents(assistant, username)

        if not case_docs:
            docs_block = "Nessun documento giudiziario disponibile per l'utente corrente."
        else:
            header_lines = ["Documenti disponibili nel progetto:"]
            for doc in case_docs:
                header_lines.append(f'- "{doc["label"]}"')

            header = "\n".join(header_lines)

            body_chunks = []
            for doc in case_docs:
                body_chunks.append(
                    f'\n\n# Documento: {doc["label"]}\n{doc["text"]}'
                )

            docs_block = header + "".join(body_chunks)

        base_system = (
            "Sei un assistente legale integrato nell'interfaccia DQL.\n"
            "Ti verranno forniti dei documenti giuridici relativi a una causa (atti, memorie, sentenza).\n"
            "Devi rispondere alle domande dell'utente basandoti esclusivamente su quei documenti.\n"
            "Se una certa informazione non è ricavabile dai documenti, devi dirlo esplicitamente.\n"
            "Non inventare articoli, commi o decisioni che non sono contenute nei testi."
        )

        user_content = (
            f"{docs_block}\n\n"
            "Ora rispondi alla seguente domanda dell'utente, basandoti solo sui documenti sopra:\n"
            f"DOMANDA: {prompt}"
        )

        messages = [
            {"role": "system", "content": base_system},
            {"role": "user", "content": user_content},
        ]

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )

        text = completion.choices[0].message.content
        return {"result": text}

    except Exception as e:
        return {"result": f"❌ Errore chiamando GPT: {e}"}


def _call_model(prompt: str, selected_model: str, assistant, username:str):
    """
    Dispatcher per decidere quale motore usare in base al modello selezionato.
    """
    if selected_model == "DQL":
        # Comportamento attuale: usa l'assistant esistente
        return assistant.chat(prompt)

    elif selected_model == "GPT":
        return _ask_gpt(prompt, assistant, username)

    elif selected_model == "NotebookLM":
        # TODO: integrazione futura
        return {"result": "⚠️ NotebookLM non è ancora stato integrato. Seleziona DQL per ora."}

    elif selected_model == "Copilot":
        # TODO: integrazione futura
        return {"result": "⚠️ Copilot non è ancora stato integrato. Seleziona DQL per ora."}

    else:
        # fallback di sicurezza
        return {"result": f"⚠️ Modello '{selected_model}' non riconosciuto."}


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

def _show_expander(full_details: Dict, logs: List[str] = []) -> None:
    """
    Renders the details expander containing input structure, operations, and logs.
    """
    if not (full_details and full_details.get("structured_input", {})):
        return

    with st.expander("Visualizza i dettagli"):
        operations = full_details.get("operations", [])
        op_count_str = (f"Il comando è stato scomposto in {len(operations)} operazioni." 
                        if len(operations) > 1 else "Il comando non è stato necessario scomporlo.")

        # 1. Structured Input
        command_json = json.dumps(full_details.get("structured_input", {}), indent=4)
        st.markdown(
            f"""
            <details style="margin-left:20px; margin-top:10px;">
                <summary>Introduzione</summary>
                Il comando identificato per la richiesta è stato:
                <p></p>
                <pre><code class="language-json">{command_json}</code></pre>
                {op_count_str}
            </details>
            """,
            unsafe_allow_html=True,
        )

        # 2. Operations
        if len(operations) > 1:
            for index, operation in enumerate(operations, start=1):
                _display_operation(index, operation)
            st.markdown("</details>", unsafe_allow_html=True)
        
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

def _display_operation(index: int, operation: Dict) -> None:
    """Renders a single operation detail block."""
    
    # Create a clean subset for display
    display_dict = {
        "command": operation.get("command", ""),
        "from": operation.get("from", []),
    }
    for key in ["what", "how"]:
        if operation.get(key):
            display_dict[key] = operation.get(key)

    operation_json = json.dumps(display_dict, indent=4)
    operation_result = markdown.markdown(operation.get("result", ""))

    st.markdown(
        f"""
        <details style="margin-left:20px; margin-top:10px;">
            <summary>Operazione {index}: {operation.get('command', '')} - {operation.get('id', '')}</summary>
            <p></p>
            <pre><code class="language-json">{operation_json}</code></pre>
            <b>Risultato Parziale:</b>
            <details style="margin-left:20px; margin-top:10px;">
                <summary>Visualizza il testo</summary>
                <div style="margin:10px; padding:10px; border:1px solid #ccc; border-radius:8px;">
                    {operation_result}
                </div>
            </details>
        </details>
        """,
        unsafe_allow_html=True,
    )

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