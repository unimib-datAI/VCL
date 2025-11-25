import logging
import os

from datetime import datetime, timezone
from dotenv import load_dotenv

from utils.DQL_language import DQLLanguage
from utils.system_config import SystemConfig

class Config:
    """
    Manages user-specific configurations and request-level context.

    This class acts as a user-scoped wrapper around the global SystemConfig.
    It provides access to shared services (LLM, Storage) but also manages
    user-specific data (user_id, language settings) and request-specific
    data (request_id, logger).
    
    Attributes:
        storage: Shared Storage (e.g., MongoDB) instance.
        language: User-specific DQLLanguage instance.
        llm: Shared LLM instance.
        project_root (Path): The root directory of the project.
        spell_check_without_llm (bool): Flag for spell checking.
        DB_URL (str): The URL for the Elasticsearch database.
    """
    
    # --- Class-level Constants ---
    
    # Load env variable from file .env
    load_dotenv()
    
    # URL for the document database
    DB_URL: str = os.getenv("DB_URL")
    
    # Standard format for all log messages
    _LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    
    def __init__(self, user_id: str, role):
        """
        Initialize a new user-specific configuration.

        Args:
            user_id (str): The unique identifier for the user.
            role (str): The role of the user (Giudice, Avvocato, Altro)
        """
        self._user_id = user_id
        self._request_id = None  # Lazily initialized on first use
        
        # Get the global (singleton) system configuration
        self._system_CFG = SystemConfig.get_instance()
        
        # --- Expose shared services from SystemConfig ---
        self.storage = self._system_CFG.storage
        self.llm = self._system_CFG.llm
        self.project_root = self._system_CFG.project_root
        self.spell_check_without_llm = self._system_CFG.spell_check_without_llm
        
        # --- Initialize user-specific components ---
        self.language = DQLLanguage.get_instance(
            self._user_id,
            self.storage, 
            self.project_root
        )
        self.language.set_role(role)
        
        # --- Setup logging directory ---
        self._log_dir = os.path.join(self.project_root, "logs")
        os.makedirs(self._log_dir, exist_ok=True)
        
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
    
    # -----------------------------
    # --- Identifier Management ---
    # -----------------------------
    
    def get_user_id(self) -> str:
        if not self._user_id:
            raise ValueError("Empty user id")
        
        return self._user_id
    
    def get_request_id(self) -> str:
        """
        Return the current request ID.
        
        Generates a new unique ID if one does not already exist for this
        request context.
        
        Returns:
            str: The unique request ID.
        """
        if not self._request_id:
            self.generate_request_id()
        return self._request_id

    def generate_request_id(self) -> str:
        """
        Generate a unique request ID.
        
        Format: {user_id}_{utc_timestamp}
        
        Returns:
            str: A unique request ID string.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        # Sanitize timestamp for use in filenames
        sanitized = timestamp.replace(":", "").replace(".", "")
        self._request_id = f"{self._user_id}_{sanitized}"