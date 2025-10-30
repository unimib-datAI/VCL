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
            "If not specified, it will be read from 'settings/api_key.txt'."
        ),
    )

    parser.add_argument(
        "-url_db",
        action="store",
        dest="url_db",
        required=False,
        help=(
            "Database connection URL.\n"
            "If not specified, it will be read from 'settings/url_db.txt'."
        )
    )

    parser.add_argument(
        "-token_db",
        action="store",
        dest="token_db",
        required=False,
        help=(
            "Database authentication token\n"
            "If not specified, it will be read from 'settings/token_db.txt'."
        )
    )

    parser.add_argument(
        "-wait_seconds",
        action="store",
        dest="seconds",
        type=int,
        required=False,
        default=5,
        help="Number of seconds to wait after each LLM call (default: 5).",
    )
    
    parser.add_argument(
        "-spell_check_without_llm",
        action="store_true",
        dest="spell_check_without_llm",
        help=(
             "Enable to avoid llm in spell checking phase"
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
        "gui/Home.py",
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
