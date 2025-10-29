"""
This module defines the Config class, a thread-safe singleton used to manage
application-wide configuration and dependencies for the DQL system.

Responsibilities:
- Manage API keys, runtime options, and default settings.
- Provide centralized access to the LLM and Storage singletons.
- Maintain command mappings and descriptions for query operations.
- Offer utility functions for safely extracting JSON/dict/list structures from strings.

Dependencies:
- utils.LLM: Provides access to the Large Language Model (LLM).
- utils.storage: Provides access to persistent storage for query results.
"""

import argparse
import logging
import os
import socket
import threading

from pathlib import Path

from bot.utils.LLM import LLM
from bot.utils.storage import Storage


class Config:
    """
    Singleton configuration class for managing application settings.

    Ensures only one instance exists across threads. Provides access
    to system defaults, runtime options, LLM, and storage.

    Attributes:
        DB_URL (str): Default database URL.
        rag (bool): Whether to enable Retrieval-Augmented Generation (RAG).
        seconds (int): Delay between LLM calls.
        max_iterations (int): Maximum allowed query rewrite iterations.
        url (str): Default chat API endpoint.
        headers (dict): HTTP headers for API requests.
        logger (Logger): Global application logger.
        command_map (dict): Maps single-letter keys to query operation commands.
        command_descriptions (dict): Descriptions of supported query commands.
        minimum_score (int): Minimum rewrite grade needed to complete the process
    """

    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization

    # Default configuration values
    DB_URL: str = "http://10.0.0.108:9201"
    rag: bool = False
    max_iterations: int = 1
    url: str = "http://127.0.0.1:8000/chat"
    headers: dict = {"Content-Type": "application/json"}
    project_root = Path(__file__).resolve().parent.parent.parent
    
    minimum_score = 8

    @classmethod
    def get_instance(cls, request_id: str = None, user_id: str = None, opts: argparse.Namespace = None):
        """
        Retrieve the singleton instance of Config, creating it if necessary.

        Args:
            opts (argparse.Namespace, optional): Parsed command-line options.

        Returns:
            Config: The singleton instance of the configuration.
        """
        if cls._instance is None:
            with cls._lock:  # Ensure thread-safe initialization
                if cls._instance is None:
                    cls._instance = cls(request_id, user_id=user_id, opts=opts)
        return cls._instance

    def __init__(self, request_id: str = None, user_id: str = None, opts: argparse.Namespace = None):
        """
        Initialize the Config object with defaults and runtime overrides.

        Args:
            opts (argparse.Namespace, optional): Parsed command-line options.
        """
        # Prevent re-initialization if already created
        if getattr(self, "_initialized", False):
            return

        self.request_id = request_id
        self.user_id = user_id if user_id else str(socket.gethostbyname(socket.gethostname())).replace(".", "")
        
        api_key = None
        seconds = 5
        if opts:
            # Override API key if provided
            if getattr(opts, "api_key", None):
                api_key = opts.api_key
            # Enable/disable RAG if specified
            if getattr(opts, "rag", None) is not None:
                self.rag = bool(opts.rag)
            # Override wait seconds if valid
            if getattr(opts, "seconds", None) is not None and int(opts.seconds) >= 0:
                seconds = int(opts.seconds)
            # Override minimum score if valid
            if getattr(opts, "minimum_score", None) is not None and int(opts.minimum_score) > 0:
                self.minimum_score = int(opts.minimum_score)
            # Override max_iterations if valid
            if (
                getattr(opts, "max_iterations", None) is not None
                and int(opts.max_iterations) >= 1
            ):
                self.max_iterations = int(opts.max_iterations)

        # Initialize external dependencies
        self.llm = LLM.get_instance(api_key=api_key, seconds=seconds, project_root=self.project_root)
        self.storage = Storage.get_instance(self.get_logger("Storage"), self.project_root, self.user_id)

        # Mark as initialized
        self._initialized = True
        
    def get_logger(self, name: str, level=logging.INFO) -> logging.Logger:
        format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        
        os.makedirs("logs", exist_ok=True)
        log_file = os.path.join("logs", f"{self.request_id}.log")

        logger = logging.getLogger(name)
        logger.setLevel(level)

        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(format)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_formatter = logging.Formatter(format)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        return logger
    
    def set_user_id(self, user_id: str):
        """
        Set the user/session identifier for scoping storage operations.

        Args:
            user_id (str): The user/session identifier.
        """
        self.user_id = user_id
