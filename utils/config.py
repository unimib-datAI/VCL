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
        parsers (bool): Flag to disable LLM-based spell check.
    """
    # Singleton instance and thread lock
    _instance = None
    _lock = threading.Lock()

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    # Load env variable from file .env
    load_dotenv()
    
    DB_URL: str = os.getenv("DB_URL")
    
    # Set directories
    project_root = Path(__file__).resolve().parent.parent
    _log_dir = os.path.join(project_root, "logs")
    os.makedirs(_log_dir, exist_ok=True)
    
    # Standard format for all log messages
    _LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    
    DQL_info = None
    _storage = None
    llm = None
    
    def __init__(self, opts: argparse.Namespace = None):
        """
        Initialize the configuration object with defaults and runtime overrides.
        This constructor is private; use get_instance() to get the singleton.
        """
        # Prevent re-initialization
        if getattr(self, "_initialized", False):
            return

        # --- Extract runtime options from argparse ---
        if opts:
            # Extract values from the provided options
            self.api_key = getattr(opts, "api_key", None)
            self.seconds = self._parse_seconds(getattr(opts, "seconds", None))
            self.model_name = getattr(opts, "model_name", None)
            self.provider = getattr(opts, "provider", None)
            self.uri_db = getattr(opts, "uri_db", None)
            self.parsers = bool(getattr(opts, "parsers", False))
        else:
            # Set defaults if no 'opts' are provided
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
        
    # ---------------------------------
    # --- Authentication Management ---
    # ---------------------------------
    
    def handle_login(self, user_id: str, role):
        """
        Initialize a new user-specific configuration.

        Args:
            user_id (str): The unique identifier for the user.
            role (str): The role of the user (Giudice, Avvocato, Altro)
        """
        # Load global configuration
        if not user_id:
            raise ValueError("User ID must be provided to initialize Orchestrator.")
        
        self._user_id = user_id
        self._role = role
        self._request_id = None
        self._chat_id = None
        
        self.DQL_info = self.get_DQL()
        
    def handle_logout(self):
        self._user_id = None
        self._role = None
        self._request_id = None
        self._chat_id = None
        
        self.DQL_info = None
        
    # ------------------------------
    # --- Getters Big Components ---
    # ------------------------------
    
    def get_storage(self):
        if not self._storage:
            self._storage = Storage(self.uri_db, self.project_root)
        
        return self._storage
    
    def get_LLM(self):
        if not self.llm:
            self.llm = LLM(
                api_key=self.api_key, 
                seconds=self.seconds, 
                project_root=self.project_root, 
                model_name=self.model_name, 
                provider=self.provider
            )
        
        return self.llm
    
    def get_DQL(self):
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
        Create or retrieve a logger configured for the current request.

        This method ensures that log handlers are reset for each request
        to log to a new, request-specific file.

        Args:
            name (str): Name of the logger (e.g., "Orchestrator").
            level (int, optional): Logging level. Defaults to logging.INFO.

        Returns:
            logging.Logger: Configured logger instance.
        """
        
        # Log file is unique to this request
        log_file = os.path.join(self._log_dir, f"{self.get_request_id()}.log")
        
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Reset handlers: This is crucial. Because loggers are singletons,
        # we must clear old handlers (e.g., from a previous request)
        # to ensure we log to the correct new file (log_file).
        if logger.hasHandlers():
            logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(self._LOG_FORMAT))
        logger.addHandler(console_handler)

        # File handler (specific to this request_id)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(self._LOG_FORMAT))
        logger.addHandler(file_handler)

        return logger
    
    # -----------------------
    # --- User Identifier ---
    # -----------------------
    
    def get_user_id(self) -> str:
        if not self._user_id:
            raise ValueError("Empty user id")
        
        return self._user_id
    
    # --------------------------
    # --- Request Identifier ---
    # --------------------------
    
    def get_request_id(self) -> str:
        """
        Return the current request ID.
        
        Generates a new unique ID if one does not already exist for this
        request context.
        
        Returns:
            str: The unique request ID.
        """
        if not self._request_id:
            self.set_request_id()
        return self._request_id

    def set_request_id(self, id: str = None) -> str:
        """
        Generate a unique request ID.
        
        Format: {user_id}_{utc_timestamp}
        
        Returns:
            str: A unique request ID string.
        """
        if id:
            self._request_id = id
            return
        
        timestamp = datetime.now(timezone.utc).isoformat()
        # Sanitize timestamp for use in filenames
        sanitized = timestamp.replace(":", "").replace(".", "")
        
        if "+" in sanitized:
            sanitized = sanitized[:sanitized.rindex("+")]
            
        self._request_id = f"{self._user_id}_{sanitized}".lower()
        
    # -----------------------
    # --- Chat Identifier ---
    # -----------------------
    
    def get_chat_id(self) -> str:
        """
        Return the current request ID.
        
        Generates a new unique ID if one does not already exist for this
        request context.
        
        Returns:
            str: The unique request ID.
        """
        if not self._chat_id:
            self.set_chat_id()
        return self._chat_id
    
    def set_chat_id(self, id: str = None) -> str:
        """
        Generate a unique request ID.
        
        Format: {user_id}_{utc_timestamp}
        
        Returns:
            str: A unique request ID string.
        """
        if id:
            self._chat_id = id
        else:
            self._chat_id = self.get_storage().create_new_chat(self._user_id)
        
        return self._chat_id
        
    def get_chat_history(self) -> list:
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
        """
        Return the current request ID.
        
        Generates a new unique ID if one does not already exist for this
        request context.
        
        Returns:
            str: The unique request ID.
        """
        if not self._sources_id:
            self.set_sources_id("vitali")
        return self._sources_id
    
    def set_sources_id(self, id: str = None) -> str:
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
    def docs_in_string(docs):
        info = [
            f"- con la stringa \"{doc[1]}\" l'utente fa riferimento al documento \"{doc[0]}\""
            for doc in docs
            if len(doc) == 2 and doc[0] != doc[1]
        ]
        
        return "\n\t\t".join(info).strip()