import argparse
from utils.LLM import LLM
from typing import Optional

class Config:
    """
    Singleton configuration class for managing application settings.
    Ensures only one instance exists across the entire program.
    """
    
    # Class variable that will contain the single instance
    _instance = None

    # ElasticSearch database URL
    DB_URL: str = 'http://10.0.0.108:9201'

    # LLM model and provider
    model_name: str = "gemini-2.0-flash"
    provider: str = "google_genai"

    # Default behavior for RAG: extract full documents
    rag: bool = False

    # Default value for GEMINI API KEY
    api_key: str = None
    
    # Default value for SECONDS: time we must wait after all LLM calls
    seconds: int = 0

    # URL and headers for the rewriting system
    url: str = "http://127.0.0.1:8000/chat"
    headers: dict = {"Content-Type": "application/json"}

    # Optional: default timeout or delay settings
    seconds: int = 5

    @classmethod
    def get_instance(cls, opts: argparse.Namespace = None):
        """
        Access method for the singleton's only instance.
        If it doesn't already exist, it creates and initializes it.
        """
        if cls._instance is None:
            cls._instance = cls(opts)
        return cls._instance

    def __init__(self, opts: argparse.Namespace = None):
        """
        Initialize configuration with optional CLI arguments.
        This method will not reinitialize if the singleton already exists.
        """
        # Prevent reinitialization if instance already has 'llm' attribute
        if hasattr(self, "llm"):
            return

        # Load options from CLI arguments if provided
        if opts:
            # Override default API key if provided
            if opts.api_key:
                self.api_key = opts.api_key
            # Override RAG behavior if specified
            if opts.rag:
                self.rag = opts.rag
            # Override optional timeout/delay
            if opts.seconds and int(opts.seconds) > 0:
                self.seconds = int(opts.seconds)

        # Initialize the LLM object with the API key
        self.llm = LLM.get_instance(self.api_key).llm
