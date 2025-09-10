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
    Thread-safe, ensures only one instance exists.
    """

    _instance = None
    _lock = threading.Lock()

    DB_URL: str = "http://10.0.0.108:9201"
    rag: bool = False
    seconds: int = 5
    max_iterations: int = 3
    url: str = "http://127.0.0.1:8000/chat"
    headers: dict = {"Content-Type": "application/json"}

    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    logger = logging.getLogger("DQL")

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
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(opts)
        return cls._instance

    def __init__(self, opts: argparse.Namespace = None):
        if getattr(self, "_initialized", False):
            return

        api_key = None
        if opts:
            if getattr(opts, "api_key", None):
                api_key = opts.api_key
            if getattr(opts, "rag", None) is not None:
                self.rag = bool(opts.rag)
            if getattr(opts, "seconds", None) is not None and int(opts.seconds) >= 0:
                self.seconds = int(opts.seconds)
            if (
                getattr(opts, "max_iterations", None) is not None
                and int(opts.max_iterations) >= 0
            ):
                self.max_iterations = int(
                    getattr(opts, "max_iterations", self.max_iterations)
                )

        # External dependencies
        self.llm = LLM.get_instance(api_key=api_key).llm
        self.storage = Storage.get_instance()

        self._initialized = True

    def get_command_from_key(self, key: str) -> str:
        return self.command_map.get(key, "altro")

    def get_description_from_command(self, key: str) -> str:
        if len(key) == 1:
            key = self.get_command_from_key(key)
        return self.command_descriptions.get(key, "")

    @staticmethod
    def str_in_dict(output: str) -> dict:
        try:
            output = output[output.index("{") : output.rfind("}") + 1]
            return json.loads(output)
        except (ValueError, json.JSONDecodeError):
            return {}

    @staticmethod
    def str_in_list(output: str) -> list:
        try:
            output = output[output.index("[") : output.rfind("]") + 1]
            return ast.literal_eval(output)
        except (ValueError, SyntaxError):
            return []
