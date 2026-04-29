"""Global configuration and shared service factory for the DQL application."""

import argparse
import os
import logging
import threading

from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

from utils.DQL_language import DQLLanguage
from utils.LLM import LLM
from utils.storage import Storage

class Config:
    """
    Thread-safe Singleton configuration manager for the DQL application.

    This class centralizes the initialization and access to global services 
    such as the LLM engine, persistent storage (MongoDB), and the 
    domain-specific language (DQL) specifications.

    Responsibilities:
        - Loading environmental variables and managing project paths.
        - Providing request-scoped logging with unique file handlers.
    """
    
    # Static variables for the Singleton pattern
    _instance = None
    _lock = threading.Lock()

    # --- Static Initialization ---
    
    # Load environmental variables from the .env file (e.g., DB credentials)
    load_dotenv()
    
    # Global database URL shared across instances
    DB_URL: str = os.getenv("DB_URL")
    
    # Determine the project root and ensure the logs directory exists
    project_root = Path(__file__).resolve().parent.parent
    _log_dir = os.path.join(project_root, "logs")
    os.makedirs(_log_dir, exist_ok=True)
    
    # Standard format for log entries: Timestamp - Level - Module - Message
    _LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    
    # Placeholder for big components initialized lazily
    _storage = None
    _llm = None
    _DQL = {}

    def __init__(self, opts: argparse.Namespace = None):
        """
        Private constructor initialized via get_instance.
        Sets up core attributes from CLI options or system defaults.

        Args:
            opts (argparse.Namespace, optional): Runtime options (API keys, models).
        """
        # Guard against multiple initializations in the same instance
        if getattr(self, "_initialized", False):
            return

        # Map command-line arguments to instance attributes
        if opts:
            self.api_key = getattr(opts, "api_key", None)
            self.seconds = self._parse_seconds(getattr(opts, "seconds", None))
            self.model_name = getattr(opts, "model_name", None)
            self.provider = getattr(opts, "provider", None)
            self.uri_db = getattr(opts, "uri_db", None)
            self.parsers = bool(getattr(opts, "parsers", False))
        else:
            # Apply default fallback values
            self.api_key = None
            self.seconds = self._parse_seconds(None)
            self.model_name = None
            self.provider = None
            self.uri_db = None
            self.parsers = False

        self._initialized = True
    
    @classmethod
    def get_instance(cls, opts: argparse.Namespace = None):
        """
        Thread-safe method to retrieve or create the Config singleton instance.

        Args:
            opts (argparse.Namespace, optional): Options used only during creation.

        Returns:
            Config: The shared configuration instance.
        """
        # Double-checked locking pattern to ensure safety across multiple threads
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
        Validates and converts a value into a non-negative integer for time-outs.

        Returns:
            int: The parsed seconds or 0 if the input is invalid.
        """
        try:
            seconds = int(value)
            return seconds if seconds >= 0 else 0
        except (TypeError, ValueError):
            return 0
        
    # --------------------------------
    # --- Big Components Accessors ---
    # --------------------------------
    
    def get_storage(self) -> Storage:
        """
        Returns the persistent Storage (MongoDB) instance.
        Initializes it lazily if not already available.
        """
        if not self._storage:
            self._storage = Storage(self.uri_db, self.project_root)
        return self._storage
    
    def get_LLM(self) -> LLM:
        """
        Returns the Large Language Model (LLM) wrapper instance.
        """
        if not self._llm:
            self._llm = LLM(
                api_key=self.api_key, 
                seconds=self.seconds, 
                project_root=self.project_root, 
                model_name=self.model_name, 
                provider=self.provider
            )
        return self._llm
    
    def get_DQL(self, user_id: str) -> DQLLanguage:
        """
        Returns the DQLLanguage instance. Sets user role for prompt personalization.
        """
        if user_id not in self._DQL:
            self._DQL[user_id] = DQLLanguage(
                user_id,
                self.get_storage(), 
                self.project_root
            )
            self._DQL[user_id].set_role("Altro") # DA SISTEMARE
        return self._DQL[user_id]

    # --------------
    # --- Logger ---
    # --------------
    
    def get_logger(self, name: str, request_id: str, level=logging.INFO) -> logging.Logger:
        """
        Creates or retrieves a logger that writes to a request-specific file.
        Clears existing handlers to avoid duplicate logs in long-running processes.

        Args:
            name (str): The name for the logger instance.
            level: The logging severity level.

        Returns:
            logging.Logger: The configured logger.
        """
        # Path to the log file named after the current Request ID
        log_file = os.path.join(self._log_dir, f"{request_id}.log")
        
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Clear existing handlers to prevent log bleeding between requests
        if logger.hasHandlers():
            logger.handlers.clear()
        
        # Add Console output stream
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(self._LOG_FORMAT))
        logger.addHandler(console_handler)

        # Add File output stream with UTF-8 encoding for special characters
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(self._LOG_FORMAT))
        logger.addHandler(file_handler)

        return logger
        
    def get_chat_history(self, user_id: str, chat_id: str) -> list:
        """
        Retrieves the chronologically sorted chat history for the active session.
        Filters out messages without technical details to focus on actual interactions.
        """
        return sorted(
            [
                {
                    "id": chat.get("id", ""), 
                    "prompt": chat.get("details", {}).get("prompt", ""), 
                    "used_documents": chat.get("details", {}).get("used_documents", []),
                    "content": chat.get("content", "")
                }
                for chat in self._storage.get_chat_messages(user_id, chat_id)
                if "details" in chat
            ], 
            key=lambda x: x["id"]
        )
    
    # -----------------------------
    # --- Conditions Management ---
    # -----------------------------
    
    @staticmethod
    def docs_in_string(docs: list) -> str:
        """
        Converts a list of document references into a formatted instruction string.
        Used to explain to the LLM which nicknames refer to which specific documents.
        """
        info = [
            f"- con la stringa \"{doc[1]}\" l'utente fa riferimento al documento \"{doc[0]}\""
            for doc in docs
            if len(doc) == 2 and doc[0] != doc[1]
        ]
        
        return "\n\t\t".join(info).strip()
    
    @staticmethod
    def generate_request_id(user_id: str = None):
        """
        Generates and sets a unique request identifier.
        Format: user_id + UTC timestamp (ISO format sanitized).
        """
        
        timestamp = datetime.now(timezone.utc).isoformat()
        # Clean timestamp for safe filename usage
        sanitized = timestamp.replace(":", "").replace(".", "")
        
        if "+" in sanitized:
            sanitized = sanitized[:sanitized.rindex("+")]
            
        return f"{user_id}_{sanitized}".lower()
