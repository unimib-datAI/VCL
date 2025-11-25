import markdown
import streamlit as st

PAGE_TITLE = "Visualizza i tuoi documenti giudiziari"

def _initialize_docs():
    if "docs" not in st.session_state:
        st.session_state.docs = st.session_state.authenticator.get_all_documents(st.session_state.username)
        st.session_state.current_doc = st.session_state.docs[0] if st.session_state.docs else {}

def _display_buttons():
    """
    Display buttons horizontally with a scrollbar using CSS injection.
    """
    if not st.session_state.docs:
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
            width: auto;
        }
        
        div[data-testid="stHorizontalBlock"]::-webkit-scrollbar {
            height: 6px;
        }
        
        div[data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {
            background-color: #ccc;
            border-radius: 4px;
        }
        </style>
    """, unsafe_allow_html=True)

    # We create as many columns as there are documents
    cols = st.columns(len(st.session_state.docs))

    for i, doc in enumerate(st.session_state.docs):
        with cols[i]:
            # Determines whether this button matches the selected document
            is_selected = (st.session_state.current_doc.get("_id") == doc.get("_id")) if st.session_state.current_doc else False
            
            btn_type = "primary" if is_selected else "secondary"
            label = f"{doc.get('type_doc', '')}\n({doc.get('name', '')})"

            if st.button(label, key=f"btn_{i}", type=btn_type, use_container_width=True):
                st.session_state.current_doc = doc
                st.rerun()

def _display_text():
    if not st.session_state.current_doc:
        return

    st.divider()
    
    # Title of the selected document above the text
    st.subheader(f"{st.session_state.current_doc.get('type_doc', '')} ({st.session_state.current_doc.get('name', '')})")
    
    text = markdown.markdown(st.session_state.current_doc.get("text", "Nessun testo disponibile."))

    st.markdown(
        f"""
            <div style="margin:10px; padding:10px; border:1px solid #ccc; border-radius:8px;">
                {text}
            </div>
        """,
        unsafe_allow_html=True,
    )
            
def show_documents():
    """
    Main page entry point.
    """
    # Guard clause for missing state
    required_keys = ["assistant", "username", "authenticator"]
    
    if not all(hasattr(st.session_state, k) for k in required_keys) and not st.query_params.get("chat"):
        return 

    st.title(PAGE_TITLE)
    
    _initialize_docs()
    _display_buttons()
    _display_text()