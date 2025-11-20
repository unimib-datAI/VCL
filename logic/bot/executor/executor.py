"""
Executor module for generating responses from retrieved documents and user queries.

Responsibilities:
- Manage prompt templates for different operations (e.g., "cerca", "riassumi").
- Handle both full-document requests and context-based generation.
- Format system and human prompts dynamically, including optional conditions.
- Invoke the configured LLM to produce final answers.

Dependencies:
- utils.config.Config: Provides LLM, logger, and configuration values.
- logic.bot.executor.retrieval.Retrieval: Retrieves relevant documents.
- utils.DQL_language.DQLLanguage: Provides prompts and language definitions.
"""

import re
from copy import deepcopy

from logic.bot.executor.retrieval import Retrieval
from utils.config import Config
from utils.DQL_language import DQLLanguage


class Executor:
    """
    Executor class to generate answers for a given operation using documents and LLM.

    Attributes:
        _pattern (str): Regex pattern for detecting headings in text.
        _llm: Configured LLM instance from Config.
        _logger: Logger instance from Config.
        _language (DQLLanguage): DQL language configuration object.
        _or_query (str): The original, raw user query.
    """

    # Regex to find markdown-style headings (e.g., # Heading, ## Subheading)
    _pattern = r'(?m)^\s*(#{1,6})\s*(.+)$'

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config, or_query: str):
        """
        Initialize the Executor.

        Args:
            cfg (Config): Global configuration object with LLM, logger, and paths.
            or_query (str): The original, raw user query.
        """
        self._cfg = cfg
        self._llm = cfg.llm
        self._logger = cfg.get_logger("Executor")
        self._language: DQLLanguage = cfg.language
        self._or_query = or_query

    # ----------------------
    # --- Public Methods ---
    # ----------------------
    
    def generate(self, operation: dict, operations: list[dict]) -> tuple[str, dict]:
        """
        Generate a response for a single operation.

        Handles full-document requests, builds context and conditions,
        and invokes the LLM.

        Args:
            operation (dict): Single operation dictionary to process.
            operations (list[dict]): Full list of operations for context
                                     (to retrieve intermediate results).

        Returns:
            tuple[str, dict]: Generated text and the (potentially modified)
                              operation dict.
        """
        # Step 1: Retrieve relevant documents for this operation
        docs = Retrieval(self._cfg, operations).execute(operation)

        # Step 2: Handle special case: request for the full document
        # If 'what' is "intero documento" and there's only one doc,
        # return its text directly without calling the LLM.
        if operation.get("what", "") == "intero documento" and len(docs) == 1:
            result = "\n\n".join([d["text"] for d in docs]).strip()
            self._logger.info("Full document requested. Skipping LLM invocation.")
            return result, operation

        # Step 3: Select prompt and build state based on the command
        
        # Case a: 'altro' (default/other command)
        # This uses a simpler prompt that relies on the raw query and context.
        if operation.get("command", "") == "altro" or operation.get("what", "") == "altro":
            state = {
                "query": self._or_query,
                "context": self._build_context(docs, operation.get("from", []))
            }
            prompt = self._language.prompts.get("GeneratorDefault.json")
        
        # Case b: Standard DQL command (e.g., 'riassumi', 'confronta')
        # This uses a structured prompt with guidelines, conditions, etc.
        else:
            state = {
                "feedback": "",
                "how": self._format_conditions(operation.get("how", {})),
                "context": self._build_context(docs, operation.get("from", [])),
                "guidelines": self._language.get_guidelines_from_command(operation.get("command", "")),
                "description_command": self._language.get_description_from_command(operation.get("command", "")),
                "what": operation.get("what", ""),
                "description_what": self._language.get_description_from_what(operation.get("what", ""))
            }
            prompt = self._language.prompts.get("Generator.json")

        # Step 4: Invoke LLM with the selected prompt and state
        if not prompt:
            self._logger.error(f"Could not find a generator prompt for command: {operation.get('command')}")
            return "Error: Could not determine how to process this request.", operation
            
        result = self._llm.invoke(prompt, state)

        # Step 5: Format headings in the result (e.g., # -> **)
        result = re.sub(self._pattern, self._format_heading, result)

        return result, operation

    # ----------------------
    # --- Input Context  ---
    # ----------------------
    
    def _format_conditions(self, how: dict) -> str:
        """
        Convert 'how' conditions (e.g., {'language': 'english'}) to a
        human-readable string for the LLM prompt.

        Args:
            how (dict): Conditions dictionary from the operation.

        Returns:
            str: Formatted conditions string (or empty string if no
                 conditions).
        """
        if not how:
            self._logger.info("No additional conditions provided.")
            return ""

        # Start of the conditions block
        conditions = ["However, the response must satisfy the following conditions:"]
        for key, value in how.items():
            if value:
                # Add each valid condition
                conditions.append(f"- Condition \"{key}\": {value}")

        if len(conditions) == 1:
            # No valid conditions were added
            self._logger.info("No additional conditions provided.")
            return ""
        else:
            self._logger.info("Additional conditions added to state.")
            return "\n".join(conditions)

    @staticmethod
    def _build_context(docs: list[dict], names: list[str]) -> str:
        """
        Build a formatted context string from retrieved documents.

        Args:
            docs (list[dict]): List of retrieved document dictionaries.
            names (list[str]): List of document names/identifiers from the
                               operation's 'from' field.

        Returns:
            str: A single string containing all concatenated document context.
        """
        if not docs:
            return ""
        
        context_lines = []
        
        # Label documents with their source names (e.g., "op_1", "doc_A")
        # This helps the LLM link intermediate results.
        if len(docs) == len(names):
            for i, doc in enumerate(docs):
                context_lines.append(f"[Document {i + 1}: \"{names[i]}\"]\n\n{doc['text']}\n\n---")
        else:
            # Fallback if names and docs mismatch (should not happen)
            for i, doc in enumerate(docs):
                context_lines.append(f"[Document {i + 1}]\n\n{doc['text']}")
        
        context_str = "\n\n".join(context_lines).strip()
        
        # Final context block wrapper
        return f"Context:\n{context_str}"
    
    # -------------------------
    # --- Output Formatting ---
    # -------------------------

    @staticmethod
    def _format_heading(match) -> str:
        """
        Convert Markdown-style headings (#, ##, ###) to formatted text
        (bold, underline, italic) for the final output.

        Args:
            match (re.Match): Regex match object for headings.

        Returns:
            str: Formatted heading string.
        """
        level = len(match.group(1))  # Number of '#'
        content = match.group(2).strip()
        
        if level == 1:
            return f"**{content}**"  # H1 -> Bold
        elif level == 2:
            return f"__{content}__"  # H2 -> Underline
        elif level == 3:
            return f"*{content}*"   # H3 -> Italic
        
        return content  # H4+ -> Plain text