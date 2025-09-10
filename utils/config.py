import argparse
import threading

from utils.LLM import LLM
from utils.config_graph import GraphConfig
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
    url: str = "http://127.0.0.1:8000/chat"
    headers: dict = {"Content-Type": "application/json"}

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

        # External dependencies
        self.config_graph = GraphConfig.get_instance(opts)
        self.llm = LLM.get_instance(api_key=api_key).llm
        self.storage = Storage.get_instance()

        self._initialized = True
