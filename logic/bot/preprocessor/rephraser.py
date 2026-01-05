import networkx as nx
import os
import threading

from utils.config import Config

class Rephraser():
    """
    Handles the contextual rephrasing of user queries to ensure they are self-contained.
    
    This class uses the conversation history (chat) and the current query to generate 
    a standalone prompt that can be accurately processed by the DQL pipeline, 
    resolving anaphoras and implicit references. It implements the Singleton 
    pattern for thread-safe global access.
    """
    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the Rephraser with configuration and LLM resources.

        Args:
            cfg (Config): The global configuration object providing access to
                          the LLM instance, logging services, and language settings.
        """
        self._cfg = cfg
        self._llm = cfg.get_LLM()
        self._project_root = cfg.project_root
        self._dql_language = cfg.get_DQL()
        
        self._logger = cfg.get_logger("Rephraser")
        
    @classmethod
    def get_instance(cls, cfg: Config):
        """
        Retrieve the singleton instance of the Rephraser, creating it if necessary.
        Ensures that only one rephrasing engine exists in the application lifecycle.

        Args:
            cfg (Config): The configuration instance required for initialization.

        Returns:
            Rephraser: The thread-safe singleton instance.
        """
        if cls._instance is None:
            with cls._lock:  # Double-checked locking for thread safety
                if cls._instance is None:
                    cls._instance = cls(cfg)
        return cls._instance
        
    def rephrase(self, query: str, chat: list) -> str:
        """
        Rewrites the input query into a standalone version based on chat context.

        The process follows these steps:
            1. Fetches the 'RephraseQuery.json' prompt template.
            2. Injects the raw query and the recent chat history into the LLM.
            3. Returns a rephrased query that resolves pronouns or implicit topics.

        Args:
            query (str): The raw natural language input from the user.
            chat (list): The session's chat history used as context.

        Returns:
            str: The rephrased, context-aware query, or the original query as a fallback.
        """
        status = "Error"

        try:
            # Step 1: Fetch the specialized prompt for contextual rewriting
            prompt = self._dql_language.prompts.get("RephraseQuery.json", None)
            
            if not prompt:
                raise ValueError("RephraseQuery prompt template not found in language config.")
            
            if query.strip():
                # Step 2: Invoke the LLM to process the query within the chat context
                # Setting result format to True to ensure structured/clean text output
                result = self._llm.invoke(
                    prompt,
                    { "query": query, "chat": "\n".join(chat) },
                    True
                )
                
                status = "Done"
            else:
                raise ValueError("Received an empty query string.")

        except Exception as e:
            # Fallback Logic: In case of LLM failure, use the original query to avoid breaking the pipeline
            self._logger.error(f"Error during query rephrasing: {e}")
            result = query

        # Final audit log of the rephrasing transformation
        self._logger.info(f"Rephrasing Result: \"{result}\" (Status: {status})")
            
        return result