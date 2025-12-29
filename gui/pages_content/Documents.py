import markdown
import streamlit as st

# Application constant for the page header
PAGE_TITLE = "Visualizza i tuoi documenti giudiziari"

def _initialize_docs():
    """
    Initializes the documents in the session state by fetching them from storage.
    Sets the first document as the default selected document if available.
    """
    if "docs" not in st.session_state:
        # Fetch all documents associated with the current user from the storage backend
        st.session_state.docs = st.session_state.storage.get_all_documents(st.session_state.username)
        # Set the initial current document to the first item in the list
        st.session_state.current_doc = st.session_state.docs[0] if st.session_state.docs else {}

def _display_buttons():
    """
    Renders a horizontal navigation bar of buttons for each document.
    Uses CSS injection to enable horizontal scrolling for the button container.
    """
    if not st.session_state.docs:
        st.info("Nessun documento disponibile.")
        return

    # CSS injection to force the horizontal block to scroll instead of wrapping
    st.markdown("""
        <style>
        /* Container styling to enable horizontal scrolling */
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap;
            overflow-x: auto;
            padding-bottom: 10px;
            gap: 10px;
        }
        
        /* Column styling to prevent shrinking and maintain minimum width */
        div[data-testid="column"] {
            flex: 0 0 auto;
            min-width: 200px;
            width: auto;
        }
        
        /* Custom scrollbar styling for better UX in the document list */
        div[data-testid="stHorizontalBlock"]::-webkit-scrollbar {
            height: 6px;
        }
        
        div[data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {
            background-color: #ccc;
            border-radius: 4px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Dynamically create columns based on the number of available documents
    cols = st.columns(len(st.session_state.docs))

    for i, doc in enumerate(st.session_state.docs):
        with cols[i]:
            # Check if the current document in the loop is the one currently selected
            is_selected = (st.session_state.current_doc.get("_id") == doc.get("_id")) if st.session_state.current_doc else False
            
            # Use 'primary' color for the selected document to provide visual feedback
            btn_type = "primary" if is_selected else "secondary"
            label = f"{doc.get('type_doc', '')}\n({doc.get('name', '')})"

            # If button is clicked, update the session state and trigger a rerun to refresh text
            if st.button(label, key=f"btn_{i}", type=btn_type, width='stretch'):
                st.session_state.current_doc = doc
                st.rerun()

def _display_text():
    """
    Renders the content of the selected document. 
    Converts Markdown text to HTML and displays it inside a styled container.
    """
    if not st.session_state.current_doc:
        return

    st.divider()
    
    # Display the type and name of the active document
    st.subheader(f"{st.session_state.current_doc.get('type_doc', '')} ({st.session_state.current_doc.get('name', '')})")
    
    # Convert the document content from Markdown to HTML
    text = markdown.markdown(st.session_state.current_doc.get("text", "Nessun testo disponibile."))

    # Display the HTML content inside a bordered box for better readability
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
    Entry point for the document viewer page. 
    Checks for required session state keys and coordinates initialization and rendering.
    """
    # Guard clause: verify that necessary session components are present before proceeding
    required_keys = ["config", "username", "storage"]
    
    # Check if all keys exist in session_state or if a chat-specific parameter is present
    if not all(hasattr(st.session_state, k) for k in required_keys) and not st.query_params.get("chat"):
        return 

    st.title(PAGE_TITLE)
    
    # Initialize document data, then render the UI components
    _initialize_docs()
    _display_buttons()
    _display_text()