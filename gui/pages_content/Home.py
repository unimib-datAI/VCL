import os
import json
import html
import markdown
import sys
import threading
import time
import queue
import requests

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Generator, Tuple

import streamlit as st
import random

from openai import OpenAI

# import docx

# Add Root Directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

LEGAL_DOCS_DIR = ROOT_DIR / "documents"

APP_TITLE = "DQL"

# --- Available Models (UI) ---
MODEL_LABELS = {
    "DQL": "DQL",
    "GPT": "GPT",
    # "NotebookLM": "NotebookLM",
    "BattleAnon": "Battle (anonimo)",
    "BattleLabeled": "Battle (etichettato)",
}

DEFAULT_MODEL = "DQL"

BATTLE_MODELS = ["DQL", "GPT"]

# ---------------------------
# --- Chat Initialization ---
# ---------------------------

def _initialize_chat() -> None:
    """
    Initialize the chat session state by retrieving history from storage.
    Sets a default greeting message if the history is empty.
    """
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = DEFAULT_MODEL

    st.session_state.messages = st.session_state.storage.get_chat_messages(
        st.session_state.username,
        st.query_params.chat
    )

    current_model = st.session_state.selected_model or DEFAULT_MODEL

    first_message = [
        {
            "role": "assistant",
            "content": "Ciao! Come posso aiutarti oggi?",
            "time": datetime.now().isoformat(),
            "model": current_model,
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
    current_chat_id = st.query_params.get("chat", "default")

    for message in st.session_state.messages:
        model = message.get("model")
        label = MODEL_LABELS.get(model, model) if model else None

        with st.chat_message(message.get("role", "assistant")):
            if message.get("battle"):
                _render_battle_answers(
                    message["battle"],
                    model or "",
                    current_chat_id,
                )
            else:
                st.markdown(message.get("content", "Errore!"))

            if message.get("role", "assistant") == "assistant" and message.get("content", "Errore!") != "Ciao! Come posso aiutarti oggi?" and label:
                st.markdown(
                    f"<span style='font-size:0.75rem; opacity:0.7;'>🔌 Risposta generata con: <b>{label}</b></span>",
                    unsafe_allow_html=True,
                )

            _show_expander(message)

# ---------------------------
# --- Chat Input Handling ---
# ---------------------------

def _handle_suggestions_and_controls() -> Tuple[Optional[str], str]:
    """
    Renders the top control bar (Suggestions, New Chat, Delete Chat).
    Returns the prompt string (if a suggestion is clicked) and the selected model.
    """
    col1, col2, col3, col4, col5 = st.columns([0.15, 0.45, 0.20, 0.10, 0.10])
    prompt_selected = None

    # Col 1: Suggestions
    with col1:
        prompt_from_button = st.session_state.pop("prompt_from_button", None)
        if prompt_from_button:
            prompt_selected = prompt_from_button

        with st.popover("💡 Suggerimenti"):
            st.markdown("Prova a chiedere:")
            if st.session_state.language:
                for i, suggestion in enumerate(st.session_state.language.gui_examples):
                    if st.button(suggestion, key=f"suggestion_{i}"):
                        st.session_state.prompt_from_button = suggestion
                        st.rerun()
            else:
                st.info("Caricamento configurazione...")

    # Col 2: Model Selector
    with col2:
        selected_model = _render_model_selector()

    # Col 3: Source Pill Widget
    with col3:
        options = ["salomone", "vitali", "user"]

        pill_val = st.pills(
            "Seleziona la fonte",
            options=options,
            format_func=lambda option: option.capitalize(),
            default="vitali" if st.session_state.get("active_source") is None else st.session_state.active_source,
            selection_mode="single",
            key="source_pill_widget",
        )
        
        if pill_val:
            st.session_state.active_source = pill_val

    # Col 4: New Chat
    with col4:
        if st.button("📝 Nuova conversazione"):
            storage = st.session_state.storage
            username = st.session_state.username
            new_chat_id = storage.create_new_chat(username)

            if new_chat_id:
                current_model = st.session_state.get("selected_model", DEFAULT_MODEL)
                st.session_state.chat_models[new_chat_id] = current_model

                st.query_params.chat = new_chat_id
                st.rerun()

    # Col 5: Delete Chat
    with col5:
        if st.button("❌ Elimina conversazione"):
            st.session_state.storage.delete_chat(st.session_state.username, st.query_params.chat)

            all_keys = st.session_state.storage.get_all_chats(st.session_state.username).keys()
            all_keys = sorted(all_keys, reverse=True)

            if not all_keys:
                st.query_params.chat = st.session_state.storage.create_new_chat(st.session_state.username)
            else:
                st.query_params.chat = all_keys[0]

            st.rerun()

    return prompt_selected, selected_model


def _display_gui_components() -> None:
    """
    Main render function for the chat interface components.
    """
    # 1. Controls & Suggestions
    suggestion_prompt, selected_model = _handle_suggestions_and_controls()

    # 2. History
    _display_chat_history()

    # 3. Input
    chat_prompt = st.chat_input("Scrivi un messaggio...")

    prompt_to_submit = suggestion_prompt or chat_prompt

    if prompt_to_submit:
        _submit_prompt(prompt_to_submit, selected_model)
        

# ---------------------------
# -- Render Model Selector --
# ---------------------------

def _render_model_selector() -> str:
    """
    Rende il selettore del modello da interrogare.
    """
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = DEFAULT_MODEL

    if "model_selector" not in st.session_state:
        st.session_state.model_selector = st.session_state.selected_model

    if "last_model_for_chat" not in st.session_state:
        st.session_state.last_model_for_chat = st.session_state.model_selector

    st.radio(
        "Seleziona il motore da interrogare",
        options=list(MODEL_LABELS.keys()),
        format_func=lambda k: MODEL_LABELS[k],
        horizontal=True,
        key="model_selector",
    )

    selected = st.session_state.model_selector

    # Create a new chat if the model changes
    if selected != st.session_state.last_model_for_chat:
        storage = st.session_state.get("storage")
        username = st.session_state.get("username")

        if storage and username:
            new_chat_id = storage.create_new_chat(username)
            if new_chat_id:
                st.session_state.selected_model = selected
                st.session_state.last_model_for_chat = selected
                st.session_state.chat_models[new_chat_id] = selected

                st.query_params.chat = new_chat_id
                st.session_state.messages = []
                st.rerun()

    st.session_state.selected_model = selected

    return selected


def _submit_prompt(prompt: str, selected_model: str) -> None:
    """
    Orchestrates the user prompt submission: updates UI, calls assistant thread,
    handles log streaming, and saves results.
    """
    # --- 1. Display user's message ---
    user_msg = {
        "role": "user",
        "content": prompt,
        "time": datetime.now().isoformat(),
        "model": selected_model,
    }

    st.session_state.messages.append(user_msg)
    
    user_info = deepcopy(user_msg)
    user_info["chat_id"] = st.query_params.get("chat", "default")
    user_info["user_id"] = st.session_state.username
    user_info["request_id"] = st.session_state.config.generate_request_id(st.session_state.username)
    
    if hasattr(st.session_state, "active_source") and st.session_state.active_source and st.session_state.active_source in ["salomone", "vitali"]:
        user_info["source_id"] = st.session_state.active_source
    else:
        user_info["source_id"] = st.session_state.username
    
    user_info["storage"] = st.session_state.storage
    
    # --- USER QUESTION TRACKING ---
    try:
        st.session_state.storage.log_user_question(
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

        thread = threading.Thread(
            target=_call_assistant_thread,
            args=(user_info, stop_event, result_queue),
        )
        thread.start()

        # Stream logs while waiting
        if selected_model not in ("BattleAnon", "BattleLabeled"):
            log_list = _stream_logs_to_ui(placeholder, stop_event, user_info["request_id"])
        else:
            log_list = ["LOGS:", "\t (Log non mostrati in modalità Battle)", ""]

        # Ensure thread completion
        thread.join()

        # Retrieve result
        result = result_queue.get()
        raw_result = result.get("result", "")

        # -------------------------
        # --- Modalità BATTLE -----
        # -------------------------
        if selected_model in ("BattleAnon", "BattleLabeled"):
            battle_id = datetime.now().isoformat()

            if isinstance(raw_result, dict):
                battle_payload = raw_result
            else:
                battle_payload = {
                    "mode": "anon" if selected_model == "BattleAnon" else "labeled",
                    "answers": [],
                }

            battle_payload["battle_id"] = battle_id

            _render_battle_answers(
                battle_payload,
                selected_model,
                st.query_params.get("chat", "default"),
            )

            _show_expander(result)

            assistant_msg = {
                "role": "assistant",
                "content": "(modalità Battle: due risposte generate)",
                "time": datetime.now().isoformat(),
                "full_details": result,
                "logs": log_list[1:],
                "model": selected_model,
                "battle": battle_payload,
            }
            st.session_state.messages.append(assistant_msg)

        # ------------------------------
        # --- Modalità normale (non Battle)
        # ------------------------------
        else:
            text = raw_result if isinstance(raw_result, str) else str(raw_result)

            _typewriter_effect(text, placeholder)

            if selected_model == "DQL":
                assistant_msg = result
                if "details" not in assistant_msg or assistant_msg["details"] is None:
                    assistant_msg["details"] = {}
                if "logs" not in assistant_msg["details"]:
                    assistant_msg["details"]["logs"] = log_list[1:]
                _show_expander(assistant_msg)
            else:
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
    _save_messages(st.session_state.messages[-2:])

# -------------------------------
# --- Threading & Log Helpers ---
# -------------------------------

def _call_assistant_thread(user_msg: Dict, stop_event: threading.Event, result_queue: queue.Queue) -> None:
    try:
        response = _call_model(user_msg)
        result_queue.put(response)
    except Exception as e:
        result_queue.put({"result": f"Error: {str(e)}"})
    finally:
        stop_event.set()

def _load_case_documents(user_msg: Dict = None) -> List[Dict[str, str]]:
    docs: List[Dict[str, str]] = []

    raw_docs = user_msg["storage"].get_all_documents(user_msg["source_id"])
    
    if not raw_docs:
        raw_docs = []

    TEXT_KEYS = ["text", "contenuto", "content", "body"]
    NAME_KEYS = ["name", "titolo", "filename"]
    TYPE_KEYS = ["type_doc", "tipo_documento", "tipo"]

    for doc in raw_docs:
        type_doc = next((doc.get(k, "").strip() for k in TYPE_KEYS if doc.get(k)), "")
        name = next((doc.get(k, "").strip() for k in NAME_KEYS if doc.get(k)), "")
        text = next((doc.get(k, "").strip() for k in TEXT_KEYS if doc.get(k)), "")

        if not text:
            continue

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

def _build_docs_block(user_msg) -> str:
    case_docs = _load_case_documents(user_msg)

    if not case_docs:
        return "Nessun documento giudiziario disponibile per l'utente corrente."

    header_lines = ["Documenti disponibili nel progetto:"]
    for doc in case_docs:
        header_lines.append(f'- "{doc["label"]}"')

    header = "\n".join(header_lines)

    body_chunks = []
    for doc in case_docs:
        body_chunks.append(f'\n\n# Documento: {doc["label"]}\n{doc["text"]}')

    return header + "".join(body_chunks)

# -------------------------------
# --- Model calls (thread-safe)
# -------------------------------

def _ask_dql(user_msg: Dict) -> Dict:
    payload = {
        "prompt": user_msg.get("content", "Errore!"),
        "user_id": user_msg["user_id"],
        "chat_id": user_msg["chat_id"],
        "request_id": user_msg["request_id"],
        "source_id": user_msg["source_id"]
    }
    
    try:
        response = requests.post("http://localhost:9000/api/v2/chat", json=payload)
        response.raise_for_status()
        
        return response.json()
    except requests.exceptions.RequestException as e:
        return {
            "role": "assistant",
            "time": datetime.now().isoformat(),
            "model": "DQL",
            
            "id": user_msg["request_id"],
            
            "ids": {
                "user": user_msg["user_id"],
                "session": user_msg["chat_id"],
                "request": user_msg["request_id"],
            },
            
            "content": "Errore durante la chiamata al modello DQL. Per favore riprova più tardi.",
            "result": "Errore durante la chiamata al modello DQL. Per favore riprova più tardi.",
            
            "details": {
                "prompt": user_msg.get("content", "Errore!"), 
                "prompt_process": "Errore durante la chiamata al modello DQL.",
                "tasks": []
            }
        }

def _ask_gpt(user_msg: Dict) -> Dict:
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

        docs_block = _build_docs_block(user_msg)

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
            f"DOMANDA: {user_msg['content']}"
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


def _ask_battle(user_msg: Dict, anonymized: bool) -> Dict:
    if len(BATTLE_MODELS) < 2:
        return {"result": "⚠️ Non ci sono abbastanza modelli per la modalità Battle."}

    model_a, model_b = random.sample(BATTLE_MODELS, 2)

    ans_a = _run_single_model_for_battle(model_a, user_msg)
    ans_b = _run_single_model_for_battle(model_b, user_msg)

    mode = "anon" if anonymized else "labeled"

    battle_payload = {
        "mode": mode,
        "prompt": user_msg['content'],
        "answers": [
            {
                "id": "A",
                "text": ans_a["text"],
                "model_key": ans_a["model_key"],
                "model_label": ans_a["model_label"],
            },
            {
                "id": "B",
                "text": ans_b["text"],
                "model_key": ans_b["model_key"],
                "model_label": ans_b["model_label"],
            },
        ],
    }

    return {"result": battle_payload}


def _run_single_model_for_battle(model_key: str, user_msg: Dict) -> Dict[str, str]: 
    new_user_msg = deepcopy(user_msg)
    new_user_msg["model"] = model_key  
     
    try:
        text = _call_model(new_user_msg).get("result", "")
    except Exception as e:
        text = f"⚠️ Modello '{model_key}' non supportato in modalità Battle."
        model_key = "UNKNOWN"

    return {
        "text": text,
        "model_key": model_key,
        "model_label": MODEL_LABELS.get(model_key, model_key),
    }


def _call_model(user_msg) -> Dict:
    selected_model = user_msg.get("model", DEFAULT_MODEL)
    
    if selected_model == "DQL":
        return _ask_dql(user_msg)

    elif selected_model == "GPT":
        return _ask_gpt(user_msg)

    elif selected_model == "BattleAnon":
        return _ask_battle(user_msg, True)

    elif selected_model == "BattleLabeled":
        return _ask_battle(user_msg, False)

    else:
        return {"result": f"⚠️ Modello '{selected_model}' non riconosciuto."}

# -------------------------------
# --- Logs streaming (main thread)
# -------------------------------

def _stream_logs_to_ui(placeholder, stop_event: threading.Event, request_id: str) -> List[str]:
    log_file = os.path.join(
        st.session_state.config.project_root,
        "logs",
        f"{request_id}.log"
    )

    log_list = ["LOGS:"]

    for line in _follow_log_generator(log_file, stop_event):
        log_list.append(line)
        placeholder.markdown("\n\n".join(log_list).strip())

        if stop_event.is_set():
            placeholder.markdown("")
            break

    return log_list


def _follow_log_generator(file_path: str, stop_event: threading.Event, wait_time: float = 0) -> Generator[str, None, None]:
    while not (os.path.exists(file_path) or stop_event.is_set()):
        time.sleep(wait_time)

    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                f.seek(0, 2)

                while not stop_event.is_set():
                    line = f.readline()
                    if not line:
                        time.sleep(wait_time)
                        continue

                    for label in ["INFO", "ERROR", "WARNING"]:
                        if f"- {label} -" in line:
                            line = line.split(f"- {label} -", 1)[-1].strip()

                    yield f"\t{line}"
        except Exception:
            yield "\t (Errore lettura log)"


def _typewriter_effect(text: str, placeholder) -> None:
    typed_text = ""
    for char in text:
        typed_text += char
        placeholder.markdown(typed_text)
        time.sleep(0.01)

# -------------------------------
# --- Battle UI (main thread)
# -------------------------------

def _render_battle_answers(battle_payload: dict, selected_model: str, chat_id: str) -> None:
    if not battle_payload:
        st.markdown("⚠️ Nessuna risposta ricevuta in modalità Battle.")
        return

    mode = battle_payload.get("mode", "anon")
    answers = battle_payload.get("answers", [])
    if len(answers) < 2:
        st.markdown("⚠️ Modalità Battle richiede almeno due risposte.")
        return

    battle_id = battle_payload.get("battle_id", "default")

    base_key = f"battle_{chat_id}_{battle_id}"
    focus_key = f"{base_key}_focus"

    focus = st.session_state.get(focus_key)

    def _render_answer_card(answer: dict, title_prefix: str, mode_: str):
        title = title_prefix
        if mode_ == "labeled":
            label = answer.get("model_label") or answer.get("model_key", "")
            if label:
                title += f"  \n<sub style='opacity:0.7;'>Modello: <b>{label}</b></sub>"
        st.markdown(f"**{title}**", unsafe_allow_html=True)

        st.markdown(
            """
            <div style="
                border: 1px solid rgba(255,255,255,0.25);
                border-radius: 0.75rem;
                padding: 0.75rem;
                margin-top: 0.25rem;
                margin-bottom: 0.5rem;
            ">
            """,
            unsafe_allow_html=True,
        )
        st.markdown(answer.get("text", ""))
        st.markdown("</div>", unsafe_allow_html=True)

    def _log_vote(chosen_side: str):
        try:
            storage = st.session_state.storage
            chat = st.query_params.get("chat", "")
            prompt = battle_payload.get("prompt") or ""

            model_a = answers[0].get("model_key", "UNKNOWN")
            model_b = answers[1].get("model_key", "UNKNOWN")
            chosen_model = model_a if chosen_side == "A" else model_b

            storage.log_battle_vote(
                user_id=st.session_state.username,
                chat_id=chat,
                battle_id=battle_id,
                prompt=prompt,
                mode=mode,
                model_a=model_a,
                model_b=model_b,
                chosen_model=chosen_model,
                chosen_side=chosen_side,
            )
        except Exception as e:
            print(f"[WARN] impossibile loggare voto battle: {e}")

    st.markdown("### ⚔️ Modalità Battle")

    if focus in ("A", "B"):
        current_idx = 0 if focus == "A" else 1
        current_answer = answers[current_idx]

        nav_col1, nav_col2, nav_col3 = st.columns([0.25, 0.5, 0.25])

        with nav_col1:
            if st.button("⬅️ Risposta A", key=f"{base_key}_goto_A"):
                st.session_state[focus_key] = "A"
                st.rerun()

        with nav_col2:
            st.markdown(
                f"<div style='text-align:center; opacity:0.8;'>Stai visualizzando: <b>Risposta {focus}</b></div>",
                unsafe_allow_html=True,
            )

        with nav_col3:
            if st.button("Risposta B ➡️", key=f"{base_key}_goto_B"):
                st.session_state[focus_key] = "B"
                st.rerun()

        st.markdown("---")
        _render_answer_card(current_answer, f"Risposta {focus}", mode)
        return

    colA, colB = st.columns(2)

    with colA:
        _render_answer_card(answers[0], "Risposta A", mode)
        if st.button("✅ Preferisco questa risposta", key=f"{base_key}_pick_A"):
            _log_vote("A")
            st.session_state[focus_key] = "A"
            st.rerun()

    with colB:
        _render_answer_card(answers[1], "Risposta B", mode)
        if st.button("✅ Preferisco questa risposta", key=f"{base_key}_pick_B"):
            _log_vote("B")
            st.session_state[focus_key] = "B"
            st.rerun()

# ------------------------------
# --- UI Details (Expanders) ---
# ------------------------------

def _show_expander(message: Dict) -> None:
    details = message.get("details", {}) if message else {}

    prompt = details.get("prompt", "")
    prompt_process = details.get("prompt_process", prompt)
    tasks = details.get("tasks", [])
    logs = details.get("logs", [])

    if not (message and details and tasks):
        return

    with st.expander("Visualizza i dettagli"):
        if len(tasks) > 1:
            op_count_str = f"La richiesta è stata scomposta in {len(tasks)} tasks."
        else:
            op_count_str = "La richiesta non è stata scomposta."

        st.markdown(
            f"""
            L'utente ha richiesto \"{prompt}\".
            <p></p>
            Ai fini di rendere la richiesta gestibile dal sistema, essa è stata rifomulata come: \"{prompt_process}\". 
            <p></p>
            {op_count_str}
            """,
            unsafe_allow_html=True,
        )

        _display_task(tasks)

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
    for index, task in enumerate(tasks, start=1):
        prompt_task = task.get("prompt", "")
        structured_prompt = task.get("structured_prompt", {})

        display_dict = {
            "command": structured_prompt.get("command", ""),
            "from": structured_prompt.get("from", []),
        }

        for key in ["what", "how"]:
            if structured_prompt.get(key, None):
                display_dict[key] = structured_prompt[key]

        task_json = json.dumps(display_dict, indent=4)
        task_result = markdown.markdown(task.get("result", ""))

        html_code = [
            '<details style="margin-left:20px; margin-top:10px;">',
            "\t" + f"<summary>Task {index}: {prompt_task}</summary>",
            "\t<p></p>",
            "\tIl Task è stato trodotto in DQL nel seguente modo:"
            "\t<p></p>",
            "\t" + f'<pre><code class="language-json">{task_json}</code></pre>',
            "\t<p></p>",
        ]

        n_operations = len(task.get("operations", []))
        if n_operations > 1:
            html_code.append("\t" + f"Dopo essere stato tradotto, è stato necessario scomporre il task in {n_operations} operazioni.")
            operation_blocks = [_display_operation(i, t) for i, t in enumerate(task.get("operations", []))]
            for block in operation_blocks:
                for row in block:
                    html_code.append("\t" + row)
        else:
            html_code.append("\t" + "Dopo essere stato tradotto, non è stato necessario scomporre il task.")

        html_code.append('\t<details style="margin-left:20px; margin-top:10px;">')
        html_code.append("\t\t<summary>Visualizza il risultato del task</summary>")
        html_code.append('\t\t<div style="margin:10px; padding:10px; border:1px solid #ccc; border-radius:8px;">')
        html_code.append("\t\t\t" + task_result)
        html_code.append("\t\t</div>")
        html_code.append("\t</details>")

        html_code.append("</details>")

        st.markdown("\n".join([h for h in html_code if h.strip()]), unsafe_allow_html=True)


def _display_operation(index: int, operation: Dict) -> List[str]:
    structured_prompt = operation.get("structured_prompt", {})

    display_dict = {
        "command": structured_prompt.get("command", ""),
        "from": structured_prompt.get("from", []),
    }
    for key in ["what", "how"]:
        if structured_prompt.get(key):
            display_dict[key] = structured_prompt.get(key)

    operation_json = json.dumps(display_dict, indent=4)
    operation_result = markdown.markdown(operation.get("result", ""))
    operation_command = display_dict.get("command", "")

    return [
        '<details style="margin-left:20px; margin-top:10px;">',
        "\t" + f"<summary>Operazione {index}: {operation_command}</summary>",
        "\t<p></p>",
        "\tIl comando della singola operazione è:"
        "\t<p></p>",
        "\t" + f'<pre><code class="language-json">{operation_json}</code></pre>',
        '\t<details style="margin-left:20px; margin-top:10px;">',
        "\t\t<summary>Visualizza il risultato dell'operazione</summary>",
        '\t\t<div style="margin:10px; padding:10px; border:1px solid #ccc; border-radius:8px;">',
        "\t\t\t" + operation_result,
        "\t\t</div>",
        "\t</details>",
        "</details>",
    ]


def _save_messages(messages: List[Dict]) -> None:
    if "storage" in st.session_state and st.session_state.username:
        for message in messages:
            st.session_state.storage.add_chat_message(
                st.session_state.username,
                st.query_params.chat,
                message
            )

# -------------------
# --- Entry Point ---
# -------------------

def show_home():
    required_keys = ["config", "username", "storage"]
    if not all(hasattr(st.session_state, k) and getattr(st.session_state, k) for k in required_keys) or not st.query_params.get("chat"):
        st.warning("Inizializzazione della configurazione in corso... Ricarica se il messaggio persiste.")
        st.stop()

    _initialize_chat()
    _display_gui_components()


if __name__ == "__main__":
    show_home()