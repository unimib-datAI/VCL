import argparse
import streamlit.web.cli as stcli
import sys

from utils.config import Config

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the DQL application.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="DQL - Data Query Language",
        formatter_class=argparse.RawTextHelpFormatter,
    )

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

    parser.add_argument(
        "-wait_seconds",
        action="store",
        dest="seconds",
        type=int,
        required=False,
        default=0,
        help="Number of seconds to wait after each LLM call (default: 0).",
    )
    
    parser.add_argument(
        "-parsers",
        action="store_true",
        dest="parsers",
        help=(
             "Enable to avoid llm when possible"
        ),
    )
    
    parser.add_argument(
        "-model_name",
        action="store",
        dest="model_name",
        required=False,
        default="gemini-2.0-flash",
        help=(
            "Specify the LLM model name.\n"
            "Examples:\n"
            "  gemini-2.0-flash (default)\n"
            "  gpt-4o-mini\n"
            "  mistralai/Mistral-7B-Instruct-v0.2\n"
            "  claude-3-5-sonnet\n"
        ),
    )

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

    # Optional future flags (commented for now)
    # parser.add_argument(
    #     "-rag",
    #     action="store_true",
    #     dest="rag",
    #     help=(
    #         "Enable Retrieval-Augmented Generation (RAG) mode. "
    #         "Retrieves either entire documents or relevant chunks."
    #     ),
    # )
    #
    # parser.add_argument(
    #     "-max_iterations",
    #     action="store",
    #     dest="max_iterations",
    #     type=int,
    #     required=False,
    #     help="Maximum number of query rewrite attempts.",
    # )
    #
    # parser.add_argument(
    #     "-minimum_score",
    #     action="store",
    #     dest="minimum_score",
    #     type=float,
    #     required=False,
    #     help="Minimum rewrite score required to complete the process.",
    # )

    return parser.parse_args()


def _launch_streamlit() -> None:
    """
    Launch the Streamlit user interface for DQL within the same process.
    """

    sys.argv = [
        "streamlit",
        "run",
        "gui/app.py",
        "--server.fileWatcherType=none",
    ]
    sys.exit(stcli.main())


def main() -> None:
    """
    Entry point for the DQL CLI application.

    Parses command-line options, initializes configuration,
    and launches the Streamlit interface.
    """
    opts = parse_args()
    Config.get_instance(opts)
    _launch_streamlit()


if __name__ == "__main__":
    main()
