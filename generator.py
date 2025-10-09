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
from utils.file_manager import text_analysis

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
        self.max_iterations = cfg.max_iterations
        
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
        if (operation["command"] in ["estrai", "cerca"]) and operation.get("what", {}).get("name", "") == "intero documento":
            result = "\n\n".join([d["text"] for d in docs]).strip()
            self.logger.info("No need to involve the LLM. Direct return.")
            return result

        state = {"feedback": ""}
        state.update({"how": self.get_additional_conditions_str(operation.get("how_str"))})
        state.update({"context": self.get_context_str(docs, operation.get("documents", []))})
        
        if not operation.get("what", {}) == {}:
            state.update({"what": operation.get("what", {})})
            
        if not operation.get("limit", {}) == {}:
            state.update({"limit": operation.get("limit", {})})
        else:
            if operation.get("command", "") in ["riassumi", "espandi"]:
                lenghts = [text_analysis(d) for d in docs]
                answer_lenght = int(0.5 * (sum(lenghts) / len(lenghts)))
                
                operation.update({"limit": {"sign": "~", "number": answer_lenght, "unit": "parole"}})
            
        # Call the LLM with the constructed prompt and context
        result = ""
        i = 1
        
        while i <= self.max_iterations and (not self.is_result_ok(operation, result)):
            if i > 1 and operation.get("limit", {}):
                state["feedback"] = self.get_feedback_str(operation, result)
            else:
                state["feedback"] = ""
                
            self.logger.info("LLM: Attempt {i}")
            print(state)
            result = self.llm.invoke_from_file(os.path.join(self.path, f"{operation["command"]}.json"), state)
            i += 1

        return result, operation
    
    @staticmethod
    def get_additional_conditions_str(how: dict) -> str:
        # Add any "how" conditions (constraints) if present
        how_str = ""
        if how:
            how_str = "Inoltre la risposta deve rispettare le seguenti condizioni:"
            for condition, value in how.items():
                if value:
                    how_str += f"\n- Condizione {condition}: {value}"

        if how_str.strip() == "" or how_str.endswith("condizioni:"):
            how_str = ""
            
        return how_str.strip()
    
    @staticmethod
    def get_context_str(docs: list, names: list) -> str:
        # Build context string from retrieved documents
        context = ""
        if len(docs) == len(names):
            for index, doc in enumerate(docs):
                context += f"[Document {index + 1}: {names[index]}]\n\n{doc['text']}\n\n"
        else:
            for index, doc in enumerate(docs):
                context += f"[Document {index + 1}]\n\n{doc['text']}\n\n"
            
        return context.strip()
    
    @staticmethod
    def is_result_ok(request, text) -> bool:
        """
        Validate whether the given text satisfies the length limits specified in the request.

        Args:
            request (dict): Request object that may contain:
                {
                    "limit": {
                        "operator": str,  # one of '=', '<=', '>=', '~'
                        "number": int,    # reference number
                        "unit": str       # 'parole', 'caratteri', or 'frasi'
                    }
                }
            text (str): The text to analyze.

        Returns:
            bool: True if the text is within the specified limits, False otherwise.
        """
        # Empty text → automatically invalid
        if text == "":
            return False

        limit = request.get("limit", {})
        # No limits specified → always valid
        if not limit:
            return True

        # Compute text length according to the specified unit
        length_text = text_analysis(text, limit.get("unit", ""))

        # Define acceptable range boundaries (min, max)
        acceptable_range = (None, None)
        operator = limit.get("operator", "")
        number = limit.get("number", 0)

        # Determine acceptable range based on operator
        match operator:
            case "=":
                acceptable_range = (number, number)
            case "<=":
                acceptable_range = (None, number)
            case ">=":
                acceptable_range = (number, None)
            case "~":
                # ±10% tolerance around the target number
                delta = number * 0.10
                acceptable_range = (number - delta, number + delta)
            case _:
                acceptable_range = (None, None)

        min_val, max_val = acceptable_range

        # Check lower bound (if defined)
        if min_val is not None and length_text < min_val:
            return False

        # Check upper bound (if defined)
        if max_val is not None and length_text > max_val:
            return False

        # Passed all checks
        return True
    
    @staticmethod
    def get_feedback_str(operation, old_response):
        feedback = ""
        limit = operation.get("limit", {})
        
        if limit:                    
            feedback = f"""
            [FEEDBACK]
            Considera che per la query è già stato generato un possibile output:
            \"{str(old_response)}\"
            
            Questo output però è stato ritenuto non valido in quanto non rispecchia il limite di {limit.get("sign")} {limit.get("number")} {limit.get("unit")}.
            
            Nella risposta tieni conto del feedback."""
            
        return feedback
