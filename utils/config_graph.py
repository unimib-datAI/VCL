import argparse
import threading
import json
import ast

from utils.LLM import LLM

class GraphConfig:
    """
    System configuration class.
    Implemented as a thread-safe singleton to ensure only one global instance.
    """

    _instance = None
    _lock = threading.Lock()

    max_iterations: int = 3
    api_key: str = None
    seconds: int = 5

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
        """
        Access method for the singleton's only instance.
        Uses double-checked locking for thread safety.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(opts)
        return cls._instance

    def __init__(self, opts: argparse.Namespace = None):
        """
        Initializes configuration values only the first time.
        Avoids overwriting values if already initialized.
        """
        if getattr(self, "_initialized", False):
            return

        if opts:
            self.max_iterations = int(getattr(opts, "max_iterations", self.max_iterations))
            self.seconds = int(getattr(opts, "seconds", self.seconds))

        self.llm = LLM.get_instance(api_key=getattr(opts, "api_key", self.api_key)).llm
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
            output = output[output.index("{"): output.rfind("}") + 1]
            return json.loads(output)
        except Exception:
            return {}

    @staticmethod
    def str_in_list(output: str) -> list:
        try:
            output = output[output.index("["): output.rfind("]") + 1]
            return ast.literal_eval(output)
        except Exception:
            return []
