from langchain.chat_models import init_chat_model
from pathlib import Path
from utils.file_manager import read_file, write_file
import os
import threading


class LLM:
    # Singleton instance
    _instance = None
    # Lock to ensure thread-safety when creating the instance
    _lock = threading.Lock()

    # LLM model and provider
    model_name: str = "gemini-2.0-flash"
    provider: str = "google_genai"

    def __init__(self, api_key: str = None):
        # Path where the API key is stored
        api_path = Path(__file__).parent.parent / 'settings' / 'api_key.txt'

        # If no API key was provided, try reading it from the file
        if not api_key and os.path.exists(api_path) and os.path.isfile(api_path):
            api_key = read_file(api_path)

        # Set the environment variable for the Google GenAI API
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key

            # Save the key again (could be useful if normalized or updated)
            write_file(api_path, api_key)
        else:
            raise ValueError('No API key could be found.')

        # Initialize the LLM model from LangChain
        self.llm = init_chat_model(self.model_name, model_provider=self.provider)

    @classmethod
    def get_instance(cls, api_key: str = None):
        """
        Returns the single instance of LLM (Singleton pattern).
        If the instance does not exist, it will be created in a thread-safe way.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking to prevent race conditions
                if cls._instance is None:
                    cls._instance = cls(api_key)
        return cls._instance
