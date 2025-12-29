import streamlit as st

# Application constant for the page header
PAGE_TITLE = "Specifica del Linguaggio"

def _display_info():
    """
    Renders the technical documentation for the DQL (Document Query Language).
    Iterates through commands, sources, and 'what' elements retrieved from the session state
    to build a dynamic documentation page.
    """
    # Retrieve language specifications from the session state
    commands = st.session_state.language.get_commands()
    sources = st.session_state.language.get_sources()
    what = st.session_state.language.get_what()
    
    if commands and sources and what:
        # Introductory information for the user
        st.markdown(
            "Di seguito è riportata la documentazione tecnica del linguaggio DQL.\n"
            "Ricordati che puoi modificare gli elementi 'FROM' e 'WHAT' nella pagina 'Impostazioni'"
        )
        
        st.markdown("## Comandi Disponibili")
        
        # Iterate through each command to display its specific documentation
        for cmd in commands:
            cmd_name = cmd.get('command', '').strip()
            
            # Filter 'WHAT' elements that are mapped to the current command
            what_cmd = [
                "\t- '" + w.get('name', '') + "': " + w.get('definition', '')
                for w in what if cmd_name in w.get('relative_command', [])
            ]
        
            # Determine if the command is elementary or complex (decomposed)
            what_info = ""
            if what_cmd:
                joined = "\n".join(what_cmd)
                what_info = "- Elementi WHAT che considerano '" + cmd_name + "' come comando elementare:\n" + joined
            else:
                what_info = "- Si tratta di un comando scomposto. In base al valore di WHAT e il numero di elementi in FROM verranno eseguite una serie di comandi elementari"
            
            # Format guidelines list into a indented string
            guidelines = '\n\t' + '\n\t'.join(cmd.get('guidelines', []))
            
            # Render the command details section
            st.markdown(f"### Comando: {cmd_name}")
            st.markdown(f"- **Descrizione**: {cmd.get('description', '')}")
            st.markdown(what_info)
            st.markdown(f"- **Linee Guida**: {guidelines}")
            
        st.markdown("## Fonti Documentali")
        st.markdown("Le operazioni sopra descritte possono essere eseguite sulle seguenti tipologie di documenti:")
        
        # Display each document source with its synonyms and description
        for src in sources:
            st.markdown(f"## {src.get('name', '')}")
            st.markdown("\t- **Sinonimi**: " + ', '.join(src.get('synonyms', [])))
            st.markdown("\t- **Descrizione**: " + src.get('description', ''))
    
    else:
        # Fallback for empty or missing language data
        st.markdown("")

def show_info():
    """
    Main entry point for the language specification page.
    Validates the session state before proceeding with the rendering logic.
    """
    # Guard clause: Ensure essential session state keys are initialized
    required_keys = ["config", "username", "storage"]
    
    # Check for required attributes in session_state or a chat bypass parameter
    if not all(hasattr(st.session_state, k) for k in required_keys) and not st.query_params.get("chat"):
        return 

    st.title(PAGE_TITLE)
    
    # Trigger the rendering of language information
    _display_info()