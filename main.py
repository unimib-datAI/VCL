from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

import argparse
import streamlit.web.cli as stcli
import sys
import multiprocessing
import subprocess
import uvicorn

from scripts.evaluation.main import evaluation
from utils.config import Config

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the DQL application.

    Provides options for configuring LLM providers, API credentials, 
    database connection strings, and processing behavior.

    Returns:
        argparse.Namespace: Object containing the parsed and validated arguments.
    """
    parser = argparse.ArgumentParser(
        description="DQL - Data Query Language",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Authentication argument for the AI model
    parser.add_argument(
        "-api",
        action="store",
        dest="api_key",
        required=False,
        help=(
            "API key for the Gemini model.\n"
            "If not specified, it will be read from '.env'."
        ),
    )

    # Persistence layer connection string
    parser.add_argument(
        "-uri_db",
        action="store",
        dest="uri_db",
        required=False,
        help=(
            "MongoDB connection URI.\n"
            "If not specified, it will be read from '.env'."
        )
    )

    # Throttle control for API rate limits
    parser.add_argument(
        "-wait_seconds",
        action="store",
        dest="seconds",
        type=int,
        required=False,
        default=0,
        help="Number of seconds to wait after each LLM call (default: 0).",
    )
    
    # Optimization flag to reduce LLM overhead
    parser.add_argument(
        "-parsers",
        action="store_true",
        dest="parsers",
        help=(
             "Enable to avoid llm when possible"
        ),
    )
    
    # Specific model selection
    parser.add_argument(
        "-model_name",
        action="store",
        dest="model_name",
        required=False,
        default="gemini-2.5-flash",
        help=(
            "Specify the LLM model name.\n"
            "Examples:\n"
            "  gemini-2.5-flash (default)\n"
            "  gpt-4o-mini\n"
            "  mistralai/Mistral-7B-Instruct-v0.2\n"
            "  claude-3-5-sonnet\n"
        ),
    )

    # AI engine provider selection
    parser.add_argument(
        "-provider",
        action="store",
        dest="provider",
        required=False,
        default="google_genai",
        choices=["google_genai", "openai", "copilot", "huggingface"],
        help=(
            "Specify the LLM provider (default: google_genai).\n"
            "Available options:\n"
            "  google_genai  → Google Gemini\n"
            "  openai        → OpenAI GPT models\n"
            "  copilot       → GitHub Copilot API\n"
            "  huggingface   → Hugging Face models\n"
        ),
    )
    
    # Evaluation Script
    parser.add_argument(
        "-evaluation_mode",
        action="store_true",
        dest="evaluation_mode",
        help=(
             "The streamlit application is not applied, but the 'evaluation' script."
        ),
    )

    return parser.parse_args()


def _launch_uvicorn(opts: argparse.Namespace) -> None:
    """
    Launch the Uvicorn server in a separate process.
    """
    
    Config.get_instance(opts)
    uvicorn.run("logic.api:app", host="0.0.0.0", port=8000, reload=False)


def _launch_streamlit() -> None:
    """
    Launch the Streamlit user interface for DQL within the same process.

    This helper overrides the system arguments to simulate a direct call 
    to the 'streamlit run' command pointing to the application's entry point.
    """

    sys.argv = [
        "streamlit",
        "run",
        "gui/app.py",
        "--server.fileWatcherType=none",
    ]
    
    # Execute the Streamlit entry point and exit the parent process
    sys.exit(stcli.main())
    
def _launch_fast_api(opts: argparse.Namespace) -> None:
    api_process = multiprocessing.Process(
        target=_launch_uvicorn, 
        args=(opts,), 
        daemon=True
    )
    api_process.start()


def main() -> None:
    """
    Entry point for the DQL CLI application.
    """
    # Parse CLI options
    opts = parse_args()
    
    # Bootstrap the configuration singleton before starting the UI
    Config.get_instance(opts)
    
    print("Avvio dei container Docker...")
    subprocess.run(
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--build"
        ]
    )
    
    try:
        if opts:
            if opts.evaluation_mode:
                evaluation()
            else:
                # 1. PRIMA avviamo l'API in background (NON bloccante)
                #_launch_fast_api(opts)
                _launch_uvicorn(opts)
                # 2. DOPO passiamo il controllo a Streamlit (Bloccante)
                #_launch_streamlit()

    except KeyboardInterrupt:
        print("\nInterruzione manuale rilevata. Arresto in corso...")
        subprocess.run(["docker", "compose", "down"])
        print("Chiusura completata.")

if __name__ == "__main__":
    main()