import streamlit as st

PAGE_TITLE = "Specifica del Linguaggio"

def _display_info():
    commands = st.session_state.language.get_commands()
    sources = st.session_state.language.get_sources()
    what = st.session_state.language.get_what()
    
    if commands and sources and what:
        st.markdown(
            "Di seguito è riportata la documentazione tecnica del linguaggio DQL.\n"
            "Ricordati che puoi modificare gli elementi 'FROM' e 'WHAT' nella pagina 'Impostazioni'"
        )
        
        st.markdown("## Comandi Disponibili")
        
        for cmd in commands:
            cmd_name = cmd.get('command', '').strip()
            what_cmd = [
                "\t- '" + w.get('name', '') + "': " + w.get('definition', '')
                for w in what if cmd_name in w.get('relative_command', [])
            ]
        
            what_info = ""
            if what_cmd:
                joined = "\n".join(what_cmd)
                what_info = "- Elementi WHAT che considerano '" + cmd_name + "' come comando elementare:\n" + joined
            else:
                what_info = "- Si tratta di un comando scomposto. In base al valore di WHAT e il numero di elementi in FROM verranno eseguite una serie di comandi elementari"
            
            guidelines = '\n\t' + '\n\t'.join(cmd.get('guidelines', []))
            
            st.markdown(f"### Comando: {cmd_name}")
            st.markdown(f"- **Descrizione**: {cmd.get('description', '')}")
            st.markdown(what_info)
            st.markdown(f"- **Linee Guida**: {guidelines}")
            
        st.markdown("## Fonti Documentali")
        st.markdown("Le operazioni sopra descritte possono essere eseguite sulle seguenti tipologie di documenti:")
        
        for src in sources:
            st.markdown(f"## {src.get('name', '')}")
            st.markdown("\t- **Sinonimi**: " + ', '.join(src.get('synonyms', [])))
            st.markdown("\t- **Descrizione**: " + src.get('description', ''))

    
    else:
        st.markdown("")

def show_info():
    """
    Main page entry point.
    """
    # Guard clause for missing state
    required_keys = ["config", "username", "storage"]
    
    if not all(hasattr(st.session_state, k) for k in required_keys) and not st.query_params.get("chat"):
        return 

    st.title(PAGE_TITLE)
    
    _display_info()