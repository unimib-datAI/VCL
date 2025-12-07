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
import random

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
    "NotebookLM": "NotebookLM",
    "BattleAnon": "Battle (anonimo)",
    "BattleLabeled": "Battle (etichettato)",
}
DEFAULT_MODEL = "DQL"

BATTLE_MODELS = ["GPT", "NotebookLM"]

# ---------------------------
# --- Chat Initialization ---
# ---------------------------

def _initialize_chat() -> None:
    """
    Initialize the chat session state by retrieving history from storage.
    Sets a default greeting message if the history is empty.
    """
    # Assicuriamoci di avere un modello selezionato
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = DEFAULT_MODEL

    storage = st.session_state.assistant.get_storage()

    st.session_state.messages = storage.get_chat_messages(
        st.session_state.username,
        st.query_params.chat
    )

    current_model = st.session_state.selected_model

    first_message = [
        {
            "role": "assistant",
            "content": "Ciao! Come posso aiutarti oggi?",
            "time": datetime.now().isoformat(),
            "model": current_model,  # 👈 modello usato per questa chat
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
        model = message.get("model")  # DQL / GPT / NotebookLM / BattleAnon / BattleLabeled ...
        label = MODEL_LABELS.get(model, model) if model else None

        with st.chat_message(message["role"]):
            # Contenuto principale (per Battle, content può essere solo un riassunto)
            if message.get("battle"):
                # per i messaggi Battle mostriamo il layout speciale
                _render_battle_answers(
                    message["battle"],
                    model or "",
                    current_chat_id,
                )
            else:
                st.markdown(message["content"])

            # Mini badge modello (solo per l'assistente)
            if message["role"] == "assistant" and label:
                st.markdown(
                    f"<span style='font-size:0.75rem; opacity:0.7;'>🔌 Risposta generata con: <b>{label}</b></span>",
                    unsafe_allow_html=True,
                )

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
            authenticator = st.session_state.authenticator
            username = st.session_state.username
            new_chat_id = authenticator.create_new_chat(username)

            if new_chat_id:
                # modello corrente per la nuova chat
                current_model = st.session_state.get("selected_model", DEFAULT_MODEL)
                # salviamo subito l'associazione nella mappa
                st.session_state.chat_models[new_chat_id] = current_model

                st.query_params.chat = new_chat_id
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

    label = MODEL_LABELS.get(selected_model, selected_model)
    st.markdown(
        f"""
           <div style="
               margin-top: 0.5rem;
               margin-bottom: 0.3rem;
               display: inline-block;
               padding: 0.2rem 0.6rem;
               border-radius: 999px;
               font-size: 0.85rem;
               background-color: rgba(255, 255, 255, 0.08);
               border: 1px solid rgba(255, 255, 255, 0.25);
           ">
               🔌 Modello corrente: <b>{label}</b>
           </div>
           """,
        unsafe_allow_html=True,
    )

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
        selected_model (str): Selected engine key (e.g. 'DQL', 'GPT', 'NotebookLM', 'BattleAnon', 'BattleLabeled')
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
        raw_result = result.get("result", "")

        # -------------------------
        # --- Modalità BATTLE -----
        # -------------------------
        if selected_model in ("BattleAnon", "BattleLabeled"):
            # Generiamo un id per questa "sfida" per mantenere stabile lo stato della scelta
            battle_id = datetime.now().isoformat()

            if isinstance(raw_result, dict):
                battle_payload = raw_result
            else:
                # fallback in caso di errore inatteso
                battle_payload = {
                    "mode": "anon" if selected_model == "BattleAnon" else "labeled",
                    "answers": [],
                }

            battle_payload["battle_id"] = battle_id

            # Render layout a due colonne con Risposta A / Risposta B
            _render_battle_answers(
                battle_payload,
                selected_model,
                st.query_params.get("chat", "default"),
            )

            # Eventuali dettagli tecnici nell'expander
            _show_expander(result, log_list[1:])  # Skip "LOGS:" header

            # Messaggio assistente salvato in cronologia
            assistant_msg = {
                "role": "assistant",
                "content": "(modalità Battle: due risposte generate)",
                "time": datetime.now().isoformat(),
                "full_details": result,
                "logs": log_list[1:],
                "model": selected_model,
                "battle": battle_payload,   # 👈 payload usato da _display_chat_history
            }
            st.session_state.messages.append(assistant_msg)

        # ------------------------------
        # --- Modalità normale (non Battle)
        # ------------------------------
        else:
            text = raw_result if isinstance(raw_result, str) else str(raw_result)

            # Render final output con effetto "macchina da scrivere"
            _typewriter_effect(text, placeholder)
            _show_expander(result, log_list[1:])  # Skip the "LOGS:" header

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
    Rende il selettore del modello da interrogare.

    Comportamento:
    - Il widget radio controlla st.session_state["model_selector"].
    - last_model_for_chat tiene traccia del modello associato alla chat corrente.
    - Se l'utente cambia modello rispetto a last_model_for_chat,
      viene creata una nuova chat e associata a quel modello.
    """

    # Modello "logico" selezionato (usato anche da _initialize_chat)
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = DEFAULT_MODEL

    # Valore iniziale del widget radio
    if "model_selector" not in st.session_state:
        st.session_state.model_selector = st.session_state.selected_model

    # Modello associato alla chat corrente
    if "last_model_for_chat" not in st.session_state:
        st.session_state.last_model_for_chat = st.session_state.model_selector

    st.markdown("### Seleziona il motore da interrogare")

    # Il widget radio aggiorna automaticamente st.session_state.model_selector
    st.radio(
        "Motore",
        options=list(MODEL_LABELS.keys()),
        format_func=lambda k: MODEL_LABELS[k],
        horizontal=True,
        key="model_selector",
    )

    selected = st.session_state.model_selector

    # Se il modello selezionato è diverso da quello associato alla chat corrente,
    # creiamo una NUOVA chat con quel modello.
    if selected != st.session_state.last_model_for_chat:
        authenticator = st.session_state.get("authenticator")
        username = st.session_state.get("username")

        if authenticator and username:
            new_chat_id = authenticator.create_new_chat(username)
            if new_chat_id:
                # aggiorniamo il modello logico per la nuova chat
                st.session_state.selected_model = selected
                st.session_state.last_model_for_chat = selected

                # 👉 IMPORTANTISSIMO: registriamo subito il modello per la sidebar
                st.session_state.chat_models[new_chat_id] = selected

                st.query_params.chat = new_chat_id
                st.session_state.messages = []
                st.rerun()


    # Se non è cambiato, manteniamo selected_model allineato
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

def _build_docs_block(assistant, username: str) -> str:
    """
    Costruisce il blocco di testo con elenco e contenuto completo
    dei documenti di caso dell'utente.
    Riutilizzato da GPT e NotebookLM.
    """
    case_docs = _load_case_documents(assistant, username)

    if not case_docs:
        return "Nessun documento giudiziario disponibile per l'utente corrente."

    header_lines = ["Documenti disponibili nel progetto:"]
    for doc in case_docs:
        header_lines.append(f'- "{doc["label"]}"')

    header = "\n".join(header_lines)

    body_chunks = []
    for doc in case_docs:
        body_chunks.append(
            f'\n\n# Documento: {doc["label"]}\n{doc["text"]}'
        )

    return header + "".join(body_chunks)



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

        docs_block = _build_docs_block(assistant, username)

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


def _ask_notebooklm(prompt: str, assistant, username: str) -> Dict:
    """
    Implementazione attuale di NotebookLM nel tuo sistema:
    - legge i documenti da Mongo
    - usa OpenAI come backend
    - ma con uno stile/istruzioni simili a NotebookLM.

    In futuro, qui potrai sostituire la chiamata con:
    - API ufficiale NotebookLM Enterprise
    - oppure Gemini API con RAG personalizzato.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "result": (
                "⚠️ OPENAI_API_KEY non impostata.\n"
                "NotebookLM non può essere usato senza chiave OpenAI (implementazione attuale)."
            )
        }

    try:
        client = OpenAI(api_key=api_key)

        docs_block = _build_docs_block(assistant, username)

        system_msg = (
            "Sei una versione 'NotebookLM-like' dell'assistente.\n"
            "Lavori SOLO sui documenti forniti dall'utente (atti, memorie, sentenza, ecc.).\n"
            "Il tuo obiettivo è:\n"
            "- sintetizzare, spiegare e mettere in relazione i documenti,\n"
            "- proporre schemi, riassunti, mappe concettuali,\n"
            "- fare esplicito riferimento alle parti dei documenti da cui trai le informazioni.\n"
            "Non introdurre conoscenze esterne: resta sempre ancorato alle fonti fornite."
        )

        user_content = (
            f"{docs_block}\n\n"
            "Ora comportati come un taccuino di ricerca (NotebookLM):\n"
            "- se la domanda è generica, proponi una panoramica strutturata dei documenti;\n"
            "- se la domanda è specifica, cita i punti rilevanti delle fonti.\n\n"
            f"DOMANDA DELL'UTENTE: {prompt}"
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )

        text = completion.choices[0].message.content
        return {"result": text}

    except Exception as e:
        return {"result": f"❌ Errore chiamando NotebookLM (implementazione attuale): {e}"}


def _ask_battle(prompt: str, assistant, username: str, anonymized: bool) -> Dict:
    """
    Modalità Battle:
    - sceglie 2 modelli diversi a caso tra DQL, GPT, NotebookLM
    - genera due risposte
    - se anonymized=True: l'utente vede solo Risposta A / Risposta B
    - se anonymized=False: l'utente vede anche il modello (GPT / NotebookLM / DQL)
    """
    # Scegliamo 2 modelli diversi dalla pool
    if len(BATTLE_MODELS) < 2:
        return {"result": "⚠️ Non ci sono abbastanza modelli per la modalità Battle."}

    model_a, model_b = random.sample(BATTLE_MODELS, 2)

    ans_a = _run_single_model_for_battle(model_a, prompt, assistant, username)
    ans_b = _run_single_model_for_battle(model_b, prompt, assistant, username)

    mode = "anon" if anonymized else "labeled"

    battle_payload = {
        "mode": mode,
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


def _run_single_model_for_battle( model_key: str, prompt: str, assistant, username: str) -> Dict[str, str]:
    """
    Esegue un singolo modello (DQL / GPT / NotebookLM) e restituisce
    un dict con:
      - text: testo della risposta
      - model_key: chiave interna (es. 'GPT')
      - model_label: etichetta per l'UI (es. 'GPT' o 'NotebookLM')
    """

    if model_key == "DQL":
        resp = assistant.chat(prompt)
        text = resp.get("result", "")

    elif model_key == "GPT":
        resp = _ask_gpt(prompt, assistant, username)
        text = resp.get("result", "")

    elif model_key == "NotebookLM":
        resp = _ask_notebooklm(prompt, assistant, username)
        text = resp.get("result", "")

    else:
        text = f"⚠️ Modello '{model_key}' non supportato in modalità Battle."
        model_key = "UNKNOWN"

    return {
        "text": text,
        "model_key": model_key,
        "model_label": MODEL_LABELS.get(model_key, model_key),
    }


def _call_model(prompt: str, selected_model: str, assistant, username:str):
    """
    Dispatcher per decidere quale motore usare in base al modello selezionato.
    """
    if selected_model == "DQL":
        return assistant.chat(prompt)

    elif selected_model == "GPT":
        return _ask_gpt(prompt, assistant, username)

    elif selected_model == "NotebookLM":
        return _ask_notebooklm(prompt, assistant, username)

    elif selected_model == "BattleAnon":
        return _ask_battle(prompt, assistant, username, anonymized=True)

    elif selected_model == "BattleLabeled":
        return _ask_battle(prompt, assistant, username, anonymized=False)

    else:
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

def _render_battle_answers(battle_payload: dict, selected_model: str, chat_id: str) -> None:
    """
    Mostra due risposte in modalità 'Battle':

    - Prima fase: due riquadri affiancati con bottone "Preferisco questa risposta".
    - Dopo la scelta: una risposta va in "schermo intero".
      Ci sono frecce per passare da una risposta all'altra.
    """
    if not battle_payload:
        st.markdown("⚠️ Nessuna risposta ricevuta in modalità Battle.")
        return

    mode = battle_payload.get("mode", "anon")
    answers = battle_payload.get("answers", [])
    if len(answers) < 2:
        st.markdown("⚠️ Modalità Battle richiede almeno due risposte.")
        return

    battle_id = battle_payload.get("battle_id", "default")

    # Chiave base per lo stato di questa specifica "sfida"
    base_key = f"battle_{chat_id}_{battle_id}"
    focus_key = f"{base_key}_focus"  # "A", "B" oppure None

    focus = st.session_state.get(focus_key)  # risposta attualmente "in primo piano"

    # Helper per rendere un riquadro risposta
    def _render_answer_card(answer: dict, title_prefix: str, mode: str):
        title = title_prefix
        if mode == "labeled":
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

    st.markdown("### ⚔️ Modalità Battle")

    # -----------------------------
    # FASE 2: una risposta scelta
    # -----------------------------
    if focus in ("A", "B"):
        # Indice 0 -> A, 1 -> B
        current_idx = 0 if focus == "A" else 1
        current_answer = answers[current_idx]

        # Barra di navigazione per passare da una risposta all'altra
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

        # Risposta scelta in "schermo intero"
        _render_answer_card(current_answer, f"Risposta {focus}", mode)
        return

    # -----------------------------
    # FASE 1: nessuna scelta ancora
    # -----------------------------

    colA, colB = st.columns(2)

    # Risposta A
    with colA:
        _render_answer_card(answers[0], "Risposta A", mode)
        if st.button("✅ Preferisco questa risposta", key=f"{base_key}_pick_A"):
            st.session_state[focus_key] = "A"
            st.rerun()

    # Risposta B
    with colB:
        _render_answer_card(answers[1], "Risposta B", mode)
        if st.button("✅ Preferisco questa risposta", key=f"{base_key}_pick_B"):
            st.session_state[focus_key] = "B"
            st.rerun()

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