import streamlit as st

from gui.pages_content.Login import show_login
from gui.pages_content.Registration import show_registration
from gui.pages_content.Home import show_home
from gui.pages_content.Settings import show_settings

from utils.storage import Storage

st.set_page_config(page_title="DQL", layout="wide")

PAGE_MAP = {
    "Login": show_login,
    "Registration": show_registration,
    "Home": show_home,
    "Settings": show_settings,
}

if "page" not in st.query_params:
    st.query_params["page"] = "Login"
    
if "authenticator" not in st.session_state:
    st.session_state.authenticator = Storage.get_instance()
    
if "auth_status" not in st.session_state or "username" not in st.session_state or "logic_config" not in st.session_state:
    st.session_state.auth_status = False
    st.session_state.username = None
    st.session_state.logic_config = None
    
if st.session_state.auth_status and st.session_state.username:
    with st.sidebar:
        st.write(f"Benvenuto *{st.session_state['username']}*")
        
        if st.button("Home"):
            st.query_params["page"] = "Home"
            st.rerun()
        
        if st.button("Settings"):
            st.query_params["page"] = "Settings"
            st.rerun()

        if st.button("Logout"):
            st.session_state.auth_status = False
            st.session_state.username = None
            st.session_state.logic_config = None
            st.query_params["page"] = "Login"
            
            if "messages" in st.session_state:
                del st.session_state["messages"]
                
            st.rerun()
    
    if st.query_params["page"] in ["Login", "Registration"]:
        st.query_params["page"] = "Home"
        st.rerun()    
else:
    st.session_state.auth_status = False
    st.session_state.username = None
    
    if not st.query_params["page"] in ["Login", "Registration"]:
        st.query_params["page"] = "Login"
        st.rerun()  


current_page_name = st.query_params["page"]
page_to_show = PAGE_MAP.get(current_page_name, show_login)
page_to_show()