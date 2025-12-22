import networkx as nx
import os
import threading

from utils.config import Config

class Rephraser():
    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the Rephraser with configuration and resources.

        Args:
            cfg (Config): The global configuration object providing access to
                          the LLM instance, paths, and language settings.
        """
        self._cfg = cfg
        self._llm = cfg.get_LLM()
        self._project_root = cfg.project_root
        self._dql_language = cfg.get_DQL()
        
        self._logger = cfg.get_logger("Rephraser")
        
    @classmethod
    def get_instance(cls, cfg: Config):
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
                    cls._instance = cls(cfg)
        return cls._instance
        
    def rephrase(self, query: str, chat: list) -> list:
        status = "Error"

        try:
            # Retrieve the specific prompt for query rephrasing
            prompt = self._dql_language.prompts.get("RephraseQuery.json", None)
            
            if not prompt:
                raise ValueError("Error during prompt retrieval")
            
            if query.strip():
                # Invoke LLM to rewrite the query based on the prompt
                result = self._llm.invoke(
                    prompt,
                    { "query": query, "chat": chat },
                    True
                )
                
                status = "Done"
            else:
                raise ValueError("Empty query provided")

        except Exception as e:
            self._logger.error(f"Error during query rephrasing: {e}")
            result = query
            # Return original text on failure

        self._logger.info(f"{result} - {status}")
            
        return result