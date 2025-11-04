import logging
import os

from datetime import datetime, timezone

from utils.DQL_language import DQLLanguage
from utils.system_config import SystemConfig
from utils.storage import Storage

class Config():
    user_id = None
    request_id = None
    
    DB_URL: str = "http://10.0.0.108:9201"
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.system_CFG = SystemConfig.get_instance()
        
        self.storage = Storage.get_instance(self.user_id, 
                                            self.system_CFG.url_db, 
                                            self.system_CFG.token_db, 
                                            self.system_CFG.project_root)
        
        self.language = DQLLanguage.get_instance(self.storage, 
                                                 self.system_CFG.project_root)
        
        self.llm = self.system_CFG.llm
        self.project_root = self.system_CFG.project_root
        self.spell_check_without_llm = self.system_CFG.spell_check_without_llm
        
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
        timestamp = datetime.now(timezone.utc).isoformat()
        sanitized = timestamp.replace(":", "").replace(".", "")
        return f"{self.user_id}_{sanitized}"