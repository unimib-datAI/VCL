"""
Generator module for creating responses from retrieved documents and user queries.

Responsibilities:
- Manage prompt templates for different operations (e.g., "cerca", "riassumi").
- Handle both full-document requests and chunk-based RAG (Retrieval-Augmented Generation).
- Format system and human prompts dynamically, including optional conditions.
- Invoke the configured LLM to produce final answers.

Dependencies:
- utils.config.Config: Provides LLM, logger, and configuration values.
- utils.file_manager.read_file: Loads JSON-based prompt templates.
- langchain_core.prompts.ChatPromptTemplate: For building structured LLM prompts.
- langchain_core.output_parsers.StrOutputParser: For parsing raw LLM output.
"""

import os
import threading

from utils.config import Config

class Generator:
    """
    Class responsible for generating LLM responses using prompts and retrieved documents.

    Attributes:
        path (str): Directory path where prompt templates are stored.
        llm: The initialized LLM instance from Config.
        rag (bool): Whether to use Retrieval-Augmented Generation.
        logger: Logger instance for structured logging.
    """
    
    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization

    def __init__(self, cfg: Config):
        """
        Initialize the Generator with configuration settings.

        Args:
            cfg (Config): Shared configuration object providing LLM, logger, etc.
        """
        self.llm = cfg.llm
        self.rag = cfg.rag
        self.logger = cfg.get_logger("Generator")
        self.project_root = cfg.project_root
        # Path to the directory containing generator prompt templates
        self.path = os.path.join(self.project_root, "prompts", "generator")
        
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

    def generate(self, operation: dict, docs: list[dict], query: str) -> str:
        """
        Generate a response based on an operation, retrieved documents, and user query.

        Workflow:
        1. Logs start of generation.
        2. Handles special case where the entire document is requested directly.
        3. Loads the appropriate prompt template for the operation.
        4. Dynamically appends conditions if present.
        5. Constructs the context from retrieved documents.
        6. Runs the LangChain prompt → LLM → parser chain.
        7. Logs results, and returns output.

        Args:
            operation (dict): Operation definition (contains command, what, how, etc.).
            docs (list[dict]): List of retrieved documents for context.
            query (str): User’s input query.

        Returns:
            str: Generated response text from the LLM.
        """
        # Special case: request for the entire document (bypass LLM)
        if (operation["command"] in ["estrai", "cerca"]) and operation["what"][
            "name"
        ] == "intero documento":
            result = "\n\n".join([d["text"] for d in docs]).strip()
            self.logger.info("No need to involve the LLM. Direct return.")
            return result

        # Add any "how" conditions (constraints) if present
        conditions = ""
        if operation.get("how", {}):
            conditions = "Inoltre la risposta deve rispettare le seguenti condizioni:"
            for condition, value in operation["how"].items():
                if value:
                    conditions += f"\n- Condizione {condition}: {value}"

        if conditions.strip() == "" or conditions.endswith("condizioni:"):
            conditions = ""

        # Build context string from retrieved documents
        context = ""
        for index, doc in enumerate(docs):
            context += f"[Document {index + 1}]\n\n{doc}\n\n"
        
        self.logger.info("LLM invoked.")
        # Call the LLM with the constructed prompt and context
        result = self.llm.invoke_from_file(os.path.join(self.path, f"{operation["command"]}.json"), {"query": query, "context": context, "how": conditions})

        return result
