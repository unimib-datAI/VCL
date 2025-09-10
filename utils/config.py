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
import ast
import json
import logging
import threading

from utils.LLM import LLM
from utils.storage import Storage


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
    """

    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization

    # Default configuration values
    DB_URL: str = "http://10.0.0.108:9201"
    rag: bool = False
    seconds: int = 5
    max_iterations: int = 3
    url: str = "http://127.0.0.1:8000/chat"
    headers: dict = {"Content-Type": "application/json"}

    # Logging setup
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logger = logging.getLogger("DQL")

    # Mapping from shortcut keys to commands
    command_map = {
        "a": "cerca",
        "b": "riassumi",
        "c": "confronta",
        "d": "estrai",
        "e": "esplora",
        "f": "espandi",
        "g": "calcola",
        "h": "altro",
    }

    # Descriptions for commands
    command_descriptions = {
        "cerca": "Cerca porzioni del documento che contengano le informazioni richieste...",
        "riassumi": "Riassume il contenuto in modo chiaro e conciso...",
        "confronta": "Confronta due documenti per evidenziare similitudini e differenze...",
        "estrai": "Analizza il documento per estrarre componenti logiche implicite...",
        "esplora": "Identifica e raggruppa tutte le citazioni o riferimenti...",
        "espandi": "Espande un testo fino a un certo numero di parole...",
        "calcola": "Esegue calcoli basati su elementi presenti nel testo",
        "altro": "",
    }

    @classmethod
    def get_instance(cls, opts: argparse.Namespace = None):
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
                    cls._instance = cls(opts)
        return cls._instance

    def __init__(self, opts: argparse.Namespace = None):
        """
        Initialize the Config object with defaults and runtime overrides.

        Args:
            opts (argparse.Namespace, optional): Parsed command-line options.
        """
        # Prevent re-initialization if already created
        if getattr(self, "_initialized", False):
            return

        api_key = None
        if opts:
            # Override API key if provided
            if getattr(opts, "api_key", None):
                api_key = opts.api_key
            # Enable/disable RAG if specified
            if getattr(opts, "rag", None) is not None:
                self.rag = bool(opts.rag)
            # Override wait seconds if valid
            if getattr(opts, "seconds", None) is not None and int(opts.seconds) >= 0:
                self.seconds = int(opts.seconds)
            # Override max_iterations if valid
            if (
                getattr(opts, "max_iterations", None) is not None
                and int(opts.max_iterations) >= 0
            ):
                self.max_iterations = int(
                    getattr(opts, "max_iterations", self.max_iterations)
                )

        # Initialize external dependencies
        self.llm = LLM.get_instance(api_key=api_key).llm
        self.storage = Storage.get_instance()

        # Mark as initialized
        self._initialized = True

    def get_command_from_key(self, key: str) -> str:
        """
        Get the command string associated with a single-letter shortcut key.

        Args:
            key (str): A single-letter command key.

        Returns:
            str: The corresponding command, or "altro" if not found.
        """
        return self.command_map.get(key, "altro")

    def get_description_from_command(self, key: str) -> str:
        """
        Get the description of a command.

        Args:
            key (str): Either a command name or a single-letter shortcut key.

        Returns:
            str: The description of the command, or an empty string if not found.
        """
        if len(key) == 1:
            key = self.get_command_from_key(key)
        return self.command_descriptions.get(key, "")

    @staticmethod
    def str_in_dict(output: str) -> dict:
        """
        Safely extract and parse a JSON object from a string.

        Args:
            output (str): A string containing a JSON object.

        Returns:
            dict: The parsed dictionary, or an empty dict if parsing fails.
        """
        try:
            # Find the first and last curly braces and extract substring
            output = output[output.index("{") : output.rfind("}") + 1]
            return json.loads(output)
        except (ValueError, json.JSONDecodeError):
            return {}

    @staticmethod
    def str_in_list(output: str) -> list:
        """
        Safely extract and parse a Python list from a string.

        Args:
            output (str): A string containing a Python list.

        Returns:
            list: The parsed list, or an empty list if parsing fails.
        """
        try:
            # Find the first and last square brackets and extract substring
            output = output[output.index("[") : output.rfind("]") + 1]
            return ast.literal_eval(output)
        except (ValueError, SyntaxError):
            return []
