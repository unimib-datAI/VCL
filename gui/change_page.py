import streamlit as st

from utils.config import Config

def change_page(name, or_page=[]):
    if not (st.query_params["page"] == name or st.query_params["page"] in or_page):
        st.query_params["page"] = name
        
        if name == "Home" or name == "Settings":
            st.session_state.logic_config = Config(st.session_state['username'])
        else:
            st.session_state.logic_config = None