import argparse
import threading

from pathlib import Path

from utils.LLM import LLM
from utils.storage import Storage


class SystemConfig:
    """
    Singleton configuration manager for initializing and providing access to 
    shared application-level components such as LLM and Storage.

    Responsibilities:
        - Manage global configuration (API keys, DB URLs, model settings, etc.)
        - Ensure thread-safe singleton instantiation.
        - Provide access to shared, initialized services (LLM, Storage).

    Attributes:
        project_root (Path): Root directory of the project.
        llm (LLM): Singleton instance of the LLM class.
        storage (Storage): Singleton instance of the Storage class.
        spell_check_without_llm (bool): Flag to disable LLM-based spell check.
    """
    # Singleton instance and thread lock
    _instance = None
    _lock = threading.Lock()

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, opts: argparse.Namespace = None):
        """
        Initialize the configuration object with defaults and runtime overrides.
        This constructor is private; use get_instance() to get the singleton.
        """
        # Prevent re-initialization
        if getattr(self, "_initialized", False):
            return

        # Set the project's root directory
        self.project_root = Path(__file__).resolve().parent.parent

        # --- Extract runtime options from argparse ---
        if opts:
            # Extract values from the provided options
            api_key = getattr(opts, "api_key", None)
            seconds_raw = getattr(opts, "seconds", None)
            model_name = getattr(opts, "model_name", None)
            provider = getattr(opts, "provider", None)
            uri_db = getattr(opts, "uri_db", None)
            self.spell_check_without_llm = getattr(opts, "spell_check_without_llm", False)
        else:
            # Set defaults if no 'opts' are provided
            api_key = None
            seconds_raw = None
            model_name = None
            provider = None
            uri_db = None
            self.spell_check_without_llm = False
        
        # Parse and validate 'seconds'
        seconds = self._parse_seconds(seconds_raw)
        
        # --- Initialize subsystems ---
        
        # Initialize the Storage singleton
        self.storage = Storage.get_instance(uri_db, self.project_root)
        
        # Initialize the LLM singleton
        self.llm = LLM.get_instance(
            api_key=api_key, 
            seconds=seconds, 
            project_root=self.project_root, 
            model_name=model_name, 
            provider=provider
        )

        self._initialized = True
    
    @classmethod
    def get_instance(cls, opts: argparse.Namespace = None):
        """
        Retrieve the global Config singleton instance, creating it if necessary.
        This method is thread-safe.

        Args:
            opts (argparse.Namespace, optional): Command-line arguments.
                These are only used on the *first* call that creates
                the instance.

        Returns:
            SystemConfig: The singleton configuration instance.
        """
        # Use a double-check locking pattern for thread-safe singleton creation
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
        """
        Validate and parse seconds value, ensuring a non-negative integer.

        Args:
            value (any): The input value (e.g., from command line).

        Returns:
            int: A non-negative integer. Returns 0 if input is invalid,
                 None, or negative.
        """
        try:
            seconds = int(value)
            # Ensure value is not negative
            return seconds if seconds >= 0 else 0
        except (TypeError, ValueError):
            # Fallback for None or invalid string
            return 0