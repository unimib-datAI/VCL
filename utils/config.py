import argparse
import logging
import os
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path

from utils.DQL_language import DQLLanguage
from utils.LLM import LLM
from utils.storage import Storage


class Config:
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
        user_id (str): Unique identifier for the current user.
        request_id (str): Unique identifier for the current request.
        llm (LLM): Singleton instance of the LLM class.
        storage (Storage): Singleton instance of the Storage class.
        language (DQLLanguage): Singleton instance of the DQLLanguage class.
    """
    # Singleton instance and thread lock
    _instance = None
    _lock = threading.Lock()

    # Default configuration values
    DB_URL: str = "http://10.0.0.108:9201"
    project_root = Path(__file__).resolve().parent.parent

    user_id: str = None
    request_id: str = None

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, opts: argparse.Namespace = None, user_id: str = None):
        """
        Initialize the configuration object with defaults and runtime overrides.
        """
        if getattr(self, "_initialized", False):
            return  # Prevent re-initialization

        # Initialize identifiers
        self.user_id = user_id or self._generate_user_id()

        # Extract options safely
        api_key = getattr(opts, "api_key", None) if opts else None
        url_db = getattr(opts, "url_db", None) if opts else None
        token_db = getattr(opts, "token_db", None) if opts else None
        seconds = self._parse_seconds(getattr(opts, "seconds", None)) if opts else 5
        self.spell_check_without_llm = getattr(opts, "spell_check_without_llm", False) if opts else False

        # Initialize subsystems
        self.llm = LLM.get_instance(api_key=api_key, seconds=seconds, project_root=self.project_root)
        self.storage = Storage.get_instance(self.user_id, url_db, token_db, self.project_root)
        self.language = DQLLanguage.get_instance(self.storage, self.project_root)

        self._initialized = True
    
    @classmethod
    def get_instance(cls, opts: argparse.Namespace = None, user_id: str = None):
        """
        Retrieve the global Config singleton instance, creating it if necessary.

        Args:
            opts (argparse.Namespace, optional): Command-line arguments.
            user_id (str, optional): Optional user ID override.

        Returns:
            Config: The singleton configuration instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(opts=opts, user_id=user_id)
        return cls._instance

    # --------------
    # --- Logger ---
    # --------------
    
    def get_logger(self, name: str, level=logging.INFO) -> logging.Logger:
        """
        Create or retrieve a logger configured with console and file handlers.

        Args:
            name (str): Name of the logger (usually __name__).
            level (int, optional): Logging level (default: logging.INFO).

        Returns:
            logging.Logger: Configured logger instance.
        """
        log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        os.makedirs("logs", exist_ok=True)

        log_file = os.path.join("logs", f"{self.get_request_id()}.log")
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Avoid duplicate handlers
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(log_format))
            logger.addHandler(console_handler)

            # File handler
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter(log_format))
            logger.addHandler(file_handler)

        return logger

    # -----------------------------
    # --- Identifier Management ---
    # -----------------------------
    
    def get_request_id(self) -> str:
        """Return the current request ID, generating it if missing."""
        if not self.request_id:
            self.request_id = self.generate_request_id()
        return self.request_id

    def generate_request_id(self) -> str:
        """Generate a unique request ID based on user ID and current UTC timestamp."""
        if not self.user_id:
            self.user_id = self._generate_user_id()

        timestamp = datetime.now(timezone.utc).isoformat()
        sanitized = timestamp.replace(":", "").replace(".", "")
        return f"{self.user_id}_{sanitized}"

    def _generate_user_id(self) -> str:
        """Generate a unique user ID based on the machine’s hostname IP."""
        return socket.gethostbyname(socket.gethostname()).replace(".", "")

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
