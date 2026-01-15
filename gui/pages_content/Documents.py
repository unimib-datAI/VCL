import json
import markdown
import streamlit as st

PAGE_TITLE = "Visualizza i tuoi documenti giudiziari"

def _initialize_docs(username_input):
    """Sincronizza i documenti basandosi sull'utente selezionato."""
    if username_input in ["vitali", "salomone"]:
        user_id = username_input
    else:
        user_id = st.session_state.get("username", "user")
                
    if hasattr(st.session_state, 'storage'):
        docs = st.session_state.storage.get_all_documents(user_id)
        
        st.session_state.docs = docs
        st.session_state.current_doc = docs[0] if docs else None

def _display_header():
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        c_source = st.session_state.config.get_sources_id()
        current_source = "user" if c_source not in ["salomone", "vitali"] else c_source
        
        options = ["salomone", "vitali", "user"]
        
        selected_source = st.pills(
            "Seleziona la fonte",
            options=options,
            format_func=lambda option: option.capitalize(),
            selection_mode="single",
            default=current_source if current_source in options else "user",
            key="source_pill_widget"
        )

        if selected_source != current_source:
            selected_source = st.session_state.username if selected_source not in ["salomone", "vitali"] else selected_source
            st.session_state.config.set_sources_id(selected_source)
            _initialize_docs(selected_source)
            st.rerun()
    
    with col2:
        if st.button("Carica Documenti", use_container_width=True):
            st.session_state.show_uploader = True

        files = None
        if st.session_state.show_uploader:
            files = st.file_uploader(
                "Carica i tuoi documenti giudiziari (TXT, JSON).",
                type=["txt", "json"],
                accept_multiple_files=True,
                key="doc_uploader",
            )
            
        if st.session_state.show_uploader and st.button("Conferma upload"):
            if not files:
                st.warning("Seleziona almeno un file.")
                st.stop()

            with st.spinner("Caricamento documenti in corso..."):
                for file in files:
                    raw = file.read().decode("utf-8", errors="ignore")

                    if file.name.lower().endswith(".json"):
                        file_content = json.loads(raw)
                    else:
                        file_content = raw

                    st.session_state.storage.upload_document(
                        st.session_state.username,
                        file_content,
                        file.name
                    )

            st.success("Documenti caricati con successo.")
            _initialize_docs(st.session_state.config.get_sources_id())
            st.session_state.show_uploader = False
            st.rerun()
        
    with col3:
        if st.session_state.get("current_doc") and st.session_state.username == st.session_state.config.get_sources_id():
            doc_to_del = st.session_state.current_doc.get("_id", None)
            if doc_to_del:
                if st.button("🗑️ Elimina Documento Corrente", use_container_width=True, type="secondary"):
                    if st.session_state.storage.delete_document(st.session_state.username, doc_to_del):
                        st.success("Documento eliminato con successo.")
                        _initialize_docs(st.session_state.config.get_sources_id())
                        st.rerun()
                    else:
                        st.error("Errore durante l'eliminazione del documento.")
            else:
                st.button("🗑️ Elimina Documento Corrente", use_container_width=True, disabled=True)
        else:
            st.button("🗑️ Elimina Documento Corrente", use_container_width=True, disabled=True)

def _display_buttons():
    """
    Initializes the documents in the session state by fetching them from storage.
    """
    if "docs" not in st.session_state or not st.session_state.docs:
        st.info("Nessun documento disponibile.")
        return

    st.markdown("""
        <style>
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap;
            overflow-x: auto;
            padding-bottom: 10px;
            gap: 10px;
        }
        div[data-testid="column"] {
            flex: 0 0 auto;
            min-width: 200px;
        }
        </style>
    """, unsafe_allow_html=True)

    cols = st.columns(len(st.session_state.docs))

    for i, doc in enumerate(st.session_state.docs):
        with cols[i]:
            current_id = st.session_state.current_doc.get("_id") if st.session_state.current_doc else None
            is_selected = (current_id == doc.get("_id"))
            
            btn_type = "primary" if is_selected else "secondary"
            label = f"{doc.get('type_doc', 'Doc')}\n({doc.get('name', 'N/A')})"

            if st.button(label, key=f"btn_{i}", type=btn_type, use_container_width=True):
                st.session_state.current_doc = doc
                st.rerun()

def _display_text():
    """Visualizza il contenuto del documento selezionato."""
    if not st.session_state.get("current_doc"):
        return

    st.divider()
    doc = st.session_state.current_doc
    st.subheader(f"{doc.get('type_doc', '')} ({doc.get('name', '')})")
    
    content = doc.get("text", "Nessun testo disponibile.")
    html_text = markdown.markdown(content)

    st.markdown(
        f"""<div style="margin:10px; padding:15px; border:1px solid #ccc; border-radius:8px; background-color: #f9f9f9; color: black;">
            {html_text}
        </div>""",
        unsafe_allow_html=True,
    )

def show_documents():
    required_keys = ["config", "username", "storage"]
    if not all(hasattr(st.session_state, k) for k in required_keys):
        return 

    st.title(PAGE_TITLE)

    if "docs" not in st.session_state:
        _initialize_docs(st.session_state.config.get_sources_id())
        
    if "show_uploader" not in st.session_state:
        st.session_state.show_uploader = False

    _display_header()

    if st.session_state.get("docs") and len(st.session_state.docs) > 0:
        _display_buttons()
        _display_text()
    else:
        
        st.info("📂 Nessun documento disponibile per questa fonte.")