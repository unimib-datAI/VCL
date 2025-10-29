import os
import pandas as pd
import streamlit as st
import sys

from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(project_root)

from bot.utils.config import Config
from bot.utils.DQL_language import DQLlanguage

st.title("Definisci il linguaggio")

dqlLanguage = DQLlanguage(Config.get_instance())

def initialize_language():
    if "language" not in st.session_state:
        st.session_state.language = dqlLanguage.get_language()
        
    if "df" not in st.session_state:
        st.session_state.df = None
        
    if "edited_df" not in st.session_state:
        st.session_state.edited_df = None

def display_language():
    """Display all previous chat messages."""
    st.session_state.df = pd.DataFrame(st.session_state.language.get("what", [])).copy()
    
    if st.session_state.edited_df is None:
        st.session_state.edited_df = st.session_state.df.copy()
    
    st.session_state.edited_df = st.data_editor(
        st.session_state.edited_df.copy(),
        num_rows="dynamic",
        column_config={
            "available": st.column_config.MultiselectColumn(
                "Disponibile nei documenti...",
                options=list(
                    set(
                        [
                            src.get("name") 
                            for src in st.session_state.language.get("sources", [])
                        ]
                    )
                ),
                color="primary",
                format_func=lambda x: x.capitalize(),
            ),
        },
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        save_clicked = st.button("💾 Salva")
    with col2:
        cancel_clicked = st.button("↩️ Annulla")
    with col3:
        reset_clicked = st.button("🔄 Ripristina")
        
    if save_clicked:
        confirm_popup("Sei sicuro di voler salvare le modifiche?", save)
    elif cancel_clicked:
        confirm_popup("Vuoi annullare le modifiche?", cancel)
    elif reset_clicked:
        confirm_popup("Ripristinare i valori originali? Questa operazione non può essere cancellata!", reset)

def save():
    st.session_state.language["what"] = st.session_state.edited_df.to_dict(orient="records")
    dqlLanguage.set_language(st.session_state.language)
    update_session_state()
    st.session_state.df = st.session_state.edited_df.copy()
    st.success("✅ Modifiche salvate!")
    
def cancel():
    st.session_state.edited_df = st.session_state.df.copy()
    st.info("Operazione annullata.")
    
def reset():
    dqlLanguage.set_default_language()
    update_session_state()
    
    st.session_state.df = pd.DataFrame(st.session_state.language.get("what", [])).copy()
    st.session_state.edited_df = st.session_state.df.copy()
    
    st.warning("Valori ripristinati!")

def update_session_state():
    st.session_state.language = dqlLanguage.get_language()

@st.dialog("Sei sicuro?") 
def confirm_popup(message, action):
    st.write(message)
    
    if st.button("Sì, confermo"):
        action()
        st.rerun()

if __name__ == "__main__":
    initialize_language()
    display_language()