"""Launch script for the FastAPI backend."""

import argparse
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

from utils.config import Config

# Load environment variables
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments strictly for the API backend.
    """
    parser = argparse.ArgumentParser(description="DQL - API Server")

    parser.add_argument("-api", action="store", dest="api_key", required=False, help="API key for the Gemini model.")
    parser.add_argument("-uri_db", action="store", dest="uri_db", required=False, help="MongoDB connection URI.")
    parser.add_argument("-wait_seconds", action="store", dest="seconds", type=int, required=False, default=0, help="Number of seconds to wait after each LLM call.")
    parser.add_argument("-parsers", action="store_true", dest="parsers", help="Enable to avoid llm when possible")
    parser.add_argument("-model_name", action="store", dest="model_name", required=False, default="gemini-2.5-flash", help="Specify the LLM model name.")
    parser.add_argument("-provider", action="store", dest="provider", required=False, default="google_genai", choices=["google_genai", "openai", "azure_openai", "copilot", "huggingface"], help="Specify the LLM provider.")
    
    # We include evaluation_mode here just so argparse doesn't throw an error if it's passed
    parser.add_argument("-evaluation_mode", action="store_true", dest="evaluation_mode", help=argparse.SUPPRESS)

    return parser.parse_args()

def main():
    """Initialize configuration and start Uvicorn."""
    opts = parse_args()
    
    # Bootstrap the configuration singleton for the API process
    Config.get_instance(opts)
    
    # Start the server
    uvicorn.run(
        "api.api:app", 
        host="0.0.0.0", 
        port=9000, 
        reload=False,
        timeout_keep_alive=36000
    )

if __name__ == "__main__":
    main()
