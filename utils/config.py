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
        - Orchestrating user login/logout session states.
        - Providing request-scoped logging with unique file handlers.
        - Managing unique identifiers for requests, chats, and data sources.
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
    DQL_info = None
    _storage = None
    llm = None
    
    # Default source identifier
    _sources_id = None

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
        
    # ---------------------------------
    # --- Authentication Management ---
    # ---------------------------------
    
    def handle_login(self, user_id: str, role: str):
        """
        Configures the session context for a specific authenticated user.

        Args:
            user_id (str): The unique user identifier from the database.
            role (str): The functional role (e.g., Judge, Lawyer) to adapt prompts.
        """
        if not user_id:
            raise ValueError("User ID must be provided to initialize Orchestrator.")
        
        self._user_id = user_id
        self._role = role
        # Reset IDs to ensure a fresh session context
        self._request_id = None
        self._chat_id = None
        
        # Pre-load the DQL language metadata for the logged user
        self.DQL_info = self.get_DQL()
        
    def handle_logout(self):
        """
        Clears all user-related state from the configuration.
        """
        self._user_id = None
        self._role = None
        self._request_id = None
        self._chat_id = None
        self.DQL_info = None
        
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
        if not self.llm:
            self.llm = LLM(
                api_key=self.api_key, 
                seconds=self.seconds, 
                project_root=self.project_root, 
                model_name=self.model_name, 
                provider=self.provider
            )
        return self.llm
    
    def get_DQL(self) -> DQLLanguage:
        """
        Returns the DQLLanguage instance. Sets user role for prompt personalization.
        """
        if not self.DQL_info:
            self.DQL_info = DQLLanguage(
                self._user_id,
                self.get_storage(), 
                self.project_root
            )
            self.DQL_info.set_role(self._role)
        return self.DQL_info
        
    # --------------
    # --- Logger ---
    # --------------
    
    def get_logger(self, name: str, level=logging.INFO) -> logging.Logger:
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
        log_file = os.path.join(self._log_dir, f"{self.get_request_id()}.log")
        
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
    
    # -----------------------
    # --- User Identifier ---
    # -----------------------
    
    def get_user_id(self) -> str:
        """Retrieves the active user ID or raises error if unauthenticated."""
        if not self._user_id:
            raise ValueError("Authentication error: Empty user id")
        return self._user_id
    
    # --------------------------
    # --- Request Identifier ---
    # --------------------------
    
    def get_request_id(self) -> str:
        """
        Provides the ID for the current execution request.
        Auto-generates one if it doesn't exist.
        """
        if not self._request_id:
            self.set_request_id()
        return self._request_id

    def set_request_id(self, id: str = None):
        """
        Generates and sets a unique request identifier.
        Format: user_id + UTC timestamp (ISO format sanitized).
        """
        if id:
            self._request_id = id
            return
        
        timestamp = datetime.now(timezone.utc).isoformat()
        # Clean timestamp for safe filename usage
        sanitized = timestamp.replace(":", "").replace(".", "")
        
        if "+" in sanitized:
            sanitized = sanitized[:sanitized.rindex("+")]
            
        self._request_id = f"{self._user_id}_{sanitized}".lower()
        
    # -----------------------
    # --- Chat Identifier ---
    # -----------------------
    
    def get_chat_id(self) -> str:
        """Retrieves the current chat session ID."""
        if not self._chat_id:
            self.set_chat_id()
        return self._chat_id
    
    def set_chat_id(self, id: str = None) -> str:
        """
        Sets a specific chat ID or requests a new one from storage.
        """
        if id:
            self._chat_id = id
        else:
            self._chat_id = self.get_storage().create_new_chat(self._user_id)
        
        return self._chat_id
        
    def get_chat_history(self) -> list:
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
                for chat in self._storage.get_chat_messages(self.get_user_id(),
                                                            self.get_chat_id())
                if "details" in chat
            ], 
            key=lambda x: x["id"]
        )
        
    # --------------------------
    # --- Sources Management ---
    # --------------------------
    
    def get_sources_id(self) -> str:
        """Retrieves the active data source identifier (default: 'vitali')."""
        if not self._sources_id:
            self.set_sources_id("vitali")
        return self._sources_id
    
    def set_sources_id(self, id: str = None) -> str:
        """
        Sets the source project ID. If 'user' is selected, it maps to the user's private ID.
        """
        if id:
            if id == "user":
                self._sources_id = self._user_id
            else:
                self._sources_id = id
        else:
            self._sources_id = "vitali"
        
        return self._sources_id
    
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