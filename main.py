"""
This script serves as the main entry point for the DQL system.

It allows command-line configuration of the system, including:
- Providing an API key
- Setting wait times between LLM calls
- Enabling RAG (Retrieval-Augmented Generation)
- Limiting the number of query rewrite iterations
- Saving a graphical representation of the rewrite graph

It also launches the FastAPI server using Uvicorn.
"""

import argparse
import subprocess

from bot.utils.config import Config


def parse_args():
    """
    Parse command-line arguments provided to the script.

    Returns:
        argparse.Namespace: A namespace containing the parsed arguments:
            - api_key (str, optional): API Key for Gemini.
            - wait (int, optional): Wait time after each LLM call.
            - rag (bool): Whether to retrieve relevant chunks only or full documents.
            - max_iterations (int, optional): Maximum rewrite attempts for a query.
            - save_image (bool): Whether to save the rewrite graph image.
            - minimum_score (int): Minimum rewrite grade needed to complete the process
    """
    parser = argparse.ArgumentParser(
        description="DQL", formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "-api",
        action="store",
        dest="api_key",
        required=False,
        help="API Key for Gemini. If not specified, the settings/api_key.txt file is read.",
    )
    parser.add_argument(
        "-wait",
        action="store",
        dest="seconds",
        required=False,
        help="Number of seconds the system should wait after each call to an LLM.",
    )
    parser.add_argument(
        "-rag",
        action="store_true",
        dest="rag",
        help=(
            "Indicates whether the entire documents (unspecified parameter) "
            "or only the relevant chunks (specified parameter) should be retrieved."
        ),
    )
    parser.add_argument(
        "-max_iterations",
        action="store",
        dest="max_iterations",
        required=False,
        help="Maximum number of rewrite attempts for a query.",
    )
    parser.add_argument(
        "-minimum_score",
        action="store",
        dest="minimum_score",
        required=False,
        help="Minimum rewrite grade needed to complete the process.",
    )
    
    options = parser.parse_args()

    return options


def main():
    """
    Main entry point for the DQL system.

    This function:
    1. Parses command-line arguments.
    2. Initializes the Config singleton with parsed options.
    3. Generates and saves the rewrite graph image if requested.
    4. Starts the FastAPI application using Uvicorn.
    """
    opts = parse_args()
    Config.get_instance(opts)

    subprocess.call([
        "streamlit",
        "run",
        "app.py",
        "--server.fileWatcherType=none"
    ])


if __name__ == "__main__":
    main()
