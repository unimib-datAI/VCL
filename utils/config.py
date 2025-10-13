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
import threading

from pathlib import Path

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
        minimum_score (int): Minimum rewrite grade needed to complete the process
    """

    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization

    # Default configuration values
    DB_URL: str = "http://10.0.0.108:9201"
    rag: bool = False
    max_iterations: int = 3
    url: str = "http://127.0.0.1:8000/chat"
    headers: dict = {"Content-Type": "application/json"}
    project_root = Path(__file__).resolve().parent.parent

    # Mapping from shortcut keys to commands
    command_map = {
		"a": "cerca",
		"b": "riassumi",
		"c": "estrai semantico",
		"d": "estrai logico",
		"e": "confronta",
		"f": "integra",
		"g": "verifica",
		"h": "analizza",
		"i": "riorganizza",
		"j": "classifica",
        "k": "altro",
    }

    # Descriptions for commands
    command_descriptions = {
        "cerca": "Individua nel testo entità, concetti o frasi semanticamente affini, superando la ricerca per parole chiave grazie alla comprensione del significato e del contesto d’uso dei termini.",
		"riassumi": "genera una versione più breve e coerente di un testo, mantenendo i concetti essenziali e scartando i dettagli irrilevanti tramite sintesi estrattiva o astrattiva.",
		"estrai semantico": "Isola dal testo una parte autonoma di significato (come il “fatto” o la “motivazione”), utile per concentrarsi su sezioni specifiche di un documento complesso.",
		"estrai logico": "Ricostruisce una sequenza di eventi o passaggi di ragionamento, rendendo esplicita la struttura logica o temporale implicita nel testo.",
		"confronta": "Analizza due testi per evidenziarne similitudini e differenze di contenuto, linguaggio o logica, utile per comparare atti o argomentazioni giuridiche.",
		"integra": "Combina più testi o versioni di uno stesso documento eliminando incoerenze e duplicazioni, producendo un testo unico e coerente.",
		"verifica": "Controlla la correttezza, coerenza e pertinenza di riferimenti, norme o argomentazioni rispetto al contenuto complessivo del testo.",
		"analizza": "Esamina un testo per valutarne la struttura, la completezza e la solidità logico-giuridica, individuando punti di forza e debolezza.",
		"riorganizza": "Riordina frasi o paragrafi disposti in modo caotico secondo una sequenza logica, cronologica o tematica coerente.",
		"classifica": "Assegna a ciascun elemento testuale una categoria predefinita (es. domanda, fatto, norma, dispositivo) spiegando il criterio di appartenenza.",
        "altro": "l'intento non corrisponde a nessuna delle opzioni precedenti."
    }
    
    minimum_score = 8

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
        self.llm = LLM.get_instance(api_key=api_key, seconds=seconds)
        self.storage = Storage.get_instance(self.get_logger("Storage"), self.project_root)

        # Mark as initialized
        self._initialized = True
        
    def get_logger(self, name: str, level=logging.INFO) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(level)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

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
