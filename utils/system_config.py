import argparse
import threading

from pathlib import Path

from utils.LLM import LLM
from utils.storage import Storage


class SystemConfig:
    """
    Singleton configuration manager for initializing and providing access to 
    shared application-level components such as LLM, Storage, and DQLLanguage.

    Responsibilities:
        - Manage global configuration (API keys, DB URLs, tokens, etc.)
        - Handle logging setup for both console and file outputs
        - Manage user and request identification
        - Ensure thread-safe singleton instantiation

    Attributes:
        DB_URL (str): Default database URL.
        project_root (Path): Root directory of the project.
        request_id (str): Unique identifier for the current request.
        llm (LLM): Singleton instance of the LLM class.
    """
    # Singleton instance and thread lock
    _instance = None
    _lock = threading.Lock()

    project_root = Path(__file__).resolve().parent.parent

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, opts: argparse.Namespace = None):
        """
        Initialize the configuration object with defaults and runtime overrides.
        """
        # Prevent re-initialization
        if getattr(self, "_initialized", False):
            return

        # Extract options safely
        api_key = getattr(opts, "api_key", None) if opts else None
        seconds = self._parse_seconds(getattr(opts, "seconds", None)) if opts else 0
        model_name = getattr(opts, "model_name", None) if opts else None
        provider = getattr(opts, "provider", None) if opts else None
        
        url_db = getattr(opts, "url_db", None) if opts else None
        self.spell_check_without_llm = getattr(opts, "spell_check_without_llm", False) if opts else False
        
        # Initialize subsystems
        self.storage = Storage.get_instance(url_db, self.project_root)
        
        self.llm = LLM.get_instance(api_key=api_key, 
                                    seconds=seconds, 
                                    project_root=self.project_root, 
                                    model_name=model_name, 
                                    provider=provider)

        self._initialized = True
    
    @classmethod
    def get_instance(cls, opts: argparse.Namespace = None):
        """
        Retrieve the global Config singleton instance, creating it if necessary.

        Args:
            opts (argparse.Namespace, optional): Command-line arguments.

        Returns:
            Config: The singleton configuration instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(opts=opts)
        return cls._instance

    # ----------------------
    # --- Helper Methods ---
    # ----------------------
    
    @staticmethod
    def _parse_seconds(value) -> int:
        """Validate and parse seconds value, ensuring a non-negative integer."""
        try:
            seconds = int(value)
            return seconds if seconds >= 0 else 5
        except (TypeError, ValueError):
            return 5
