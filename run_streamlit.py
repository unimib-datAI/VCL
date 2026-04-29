"""Launch script for the Streamlit frontend."""

import sys
import streamlit.web.cli as stcli
from pathlib import Path
from dotenv import load_dotenv

# Ensure environment variables are loaded for the UI as well
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

def main():
    """
    Launch the Streamlit user interface.
    """
    # Override system arguments to programmatically call 'streamlit run'
    sys.argv = [
        "streamlit",
        "run",
        "gui/app.py",
        "--server.fileWatcherType=none",
    ]
    
    # Execute the Streamlit entry point
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
