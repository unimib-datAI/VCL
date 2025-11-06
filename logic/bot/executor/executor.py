"""
Executor module for generating responses from retrieved documents and user queries.

Responsibilities:
- Manage prompt templates for different operations (e.g., "cerca", "riassumi").
- Handle both full-document requests and chunk-based RAG (Retrieval-Augmented Generation).
- Format system and human prompts dynamically, including optional conditions.
- Invoke the configured LLM to produce final answers.

Dependencies:
- utils.config.Config: Provides LLM, logger, and configuration values.
- utils.file_manager.FileHandler: Loads JSON-based prompt templates.
- logic.bot.executor.retrieval.Retrieval: Retrieves relevant document chunks.
"""

import os
import re

from copy import deepcopy

from logic.bot.executor.retrieval import Retrieval
from utils.config import Config
from utils.DQL_language import DQLLanguage


class Executor:
    """
    Executor class to generate answers for a given operation using documents and LLM.

    Attributes:
        pattern (str): Regex pattern for detecting headings in text.
        llm: Configured LLM instance from Config.
        logger: Logger instance from Config.
        file_path (str): Path file containing prompt template.
    """

    pattern = r'(?m)^\s*(#{1,6})\s*(.+)$'

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config):
        """
        Initialize the Executor.

        Args:
            cfg (Config): Global configuration object with LLM, logger, and paths.
        """
        self.cfg = cfg
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Executor")
        self.language : DQLLanguage = cfg.language
        self.file_path = os.path.join(cfg.project_root, "documents", "prompts", "Generator.json")

    # ----------------------
    # --- Public Methods ---
    # ----------------------
    
    def generate(self, operation: dict, operations: list[dict]) -> tuple[str, dict]:
        """
        Generate a response for a single operation.

        Handles full-document requests, builds context and conditions, and invokes the LLM.

        Args:
            operation (dict): Single operation dictionary to process.
            operations (list[dict]): Full list of operations for context.

        Returns:
            tuple[str, dict]: Generated text and the operation dict.
        """
        # Step 1: Retrieve relevant documents
        docs = Retrieval(self.cfg, operations).execute(operation)

        # Step 2: Handle special case: full document request
        if operation.get("what", "") == "intero documento" and len(operation.get("from", [])) == 1:
            result = "\n\n".join([d["text"] for d in docs]).strip()
            self.logger.info("Full document requested. Skipping LLM invocation.")
            return result, operation

        # Step 3: Prepare state for LLM
        state = {
            "feedback": "",
            "how": self._format_conditions(operation.get("how", {})),
            "context": self._build_context(docs, operation.get("from", [])),
            "guidelines": self.language.get_guidelines_from_command(operation.get("command", "")),
            "description_command": self.language.get_description_from_command(operation.get("command", "")),
            "query_str": str(deepcopy(operation))
        }

        # Step 4: Invoke LLM with appropriate prompt
        result = self.llm.invoke(self.file_path, state)

        # Step 5: Format headings in the result
        result = re.sub(self.pattern, self._format_heading, result)

        return result, operation

    # ----------------------
    # --- Input Context  ---
    # ----------------------
    
    def _format_conditions(self, how: dict) -> str:
        """
        Convert 'how' conditions to a human-readable string for the LLM.

        Args:
            how (dict): Conditions dictionary.

        Returns:
            str: Formatted conditions string.
        """
        if not how:
            self.logger.info("No additional conditions provided.")
            return ""

        conditions = ["Tuttavia, la risposta deve soddisfare le seguenti condizioni:"]
        for key, value in how.items():
            if value:
                conditions.append(f"- Condizione \"{key}\": {value}")

        if len(conditions) == 1:
            self.logger.info("No additional conditions provided.")
            return ""
        else:
            self.logger.info("Additional conditions added to state.")
            return "\n".join(conditions)

    @staticmethod
    def _build_context(docs: list, names: list) -> str:
        """
        Build context string from retrieved documents.

        Args:
            docs (list[dict]): List of retrieved document dictionaries.
            names (list[str]): List of document names.

        Returns:
            str: Concatenated document context.
        """
        context_lines = []
        if len(docs) == len(names):
            for i, doc in enumerate(docs):
                context_lines.append(f"[Documento {i + 1}: \"{names[i]}\"]\n\n{doc['text']}\n\n---")
        else:
            for i, doc in enumerate(docs):
                context_lines.append(f"[Documento {i + 1}]\n\n{doc['text']}")
        return "\n\n".join(context_lines).strip()
    
    # -------------------------
    # --- Output Formatting ---
    # -------------------------

    @staticmethod
    def _format_heading(match) -> str:
        """
        Convert Markdown-style headings to formatted text.

        Args:
            match (re.Match): Regex match object for headings.

        Returns:
            str: Formatted heading.
        """
        level = len(match.group(1))
        content = match.group(2).strip()
        if level == 1:
            return f"**{content}**"
        elif level == 2:
            return f"__{content}__"
        elif level == 3:
            return f"*{content}*"
        return content

#    @staticmethod
#    def get_feedback_str(operation: dict, old_response: str) -> str:
#        """
#        Generate feedback string for the LLM if previous response did not satisfy limits.
#
#        Args:
#            operation (dict): Operation dictionary containing optional 'limit'.
#            old_response (str): Previously generated response.
#
#        Returns:
#            str: Feedback string for the LLM.
#        """
#        limit = operation.get("limit", {})
#        if not limit:
#            return ""
#
#        return (
#            f"[FEEDBACK]\n"
#            f"A previous output was generated:\n\"{old_response}\"\n\n"
#            f"However, it did not satisfy the limit of {limit.get('sign')} {limit.get('number')} {limit.get('unit')}.\n"
#            "Please consider this feedback in your next response."
#        )

    
#    @staticmethod
#    def is_result_ok(request, text) -> bool:
#        """
#        Validate whether the given text satisfies the length limits specified in the request.
#
#        Args:
#            request (dict): Request object that may contain:
#                {
#                    "limit": {
#                        "operator": str,  # one of '=', '<=', '>=', '~'
#                        "number": int,    # reference number
#                        "unit": str       # 'parole', 'caratteri', or 'frasi'
#                    }
#                }
#            text (str): The text to analyze.
#
#        Returns:
#            bool: True if the text is within the specified limits, False otherwise.
#        """
#        # Empty text → automatically invalid
#        if text == "":
#            return False
#
#        limit = request.get("limit", {})
#        # No limits specified → always valid
#        if not limit:
#            return True
#
#        # Compute text length according to the specified unit
#        length_text = text_analysis(text, limit.get("unit", ""))
#
#        # Define acceptable range boundaries (min, max)
#        acceptable_range = (None, None)
#        operator = limit.get("operator", "")
#        number = limit.get("number", 0)
#
#        # Determine acceptable range based on operator
#        match operator:
#            case "=":
#                acceptable_range = (number, number)
#            case "<=":
#                acceptable_range = (None, number)
#            case ">=":
#                acceptable_range = (number, None)
#            case "~":
#                # ±10% tolerance around the target number
#                delta = number * 0.10
#                acceptable_range = (number - delta, number + delta)
#            case _:
#                acceptable_range = (None, None)
#
#        min_val, max_val = acceptable_range
#
#        # Check lower bound (if defined)
#        if min_val is not None and length_text < min_val:
#            return False
#
#        # Check upper bound (if defined)
#        if max_val is not None and length_text > max_val:
#            return False
#
#        # Passed all checks
#        return True