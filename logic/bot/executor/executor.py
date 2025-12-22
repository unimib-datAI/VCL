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

from logic.bot.executor.tools.retrieval import Retrieval
from logic.bot.executor.tools.altro import altro
from logic.bot.executor.tools.analizza import analizza
from logic.bot.executor.tools.cerca import cerca
from logic.bot.executor.tools.classifica import classifica
from logic.bot.executor.tools.confronta import confronta
from logic.bot.executor.tools.estrai_logico import estrai_logico
from logic.bot.executor.tools.estrai_semantico import estrai_semantico
from logic.bot.executor.tools.integra import integra
from logic.bot.executor.tools.riassumi import riassumi
from logic.bot.executor.tools.riorganizza import riorganizza
from logic.bot.executor.tools.verifica import verifica
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
    
    FUNCTION_MAP = {
        "analizza": analizza,
        "cerca": cerca,
        "classifica": classifica,
        "confronta": confronta,
        "estrai logico": estrai_logico,
        "estrai semantico": estrai_semantico,
        "integra": integra,
        "riassumi": riassumi,
        "riorganizza": riorganizza,
        "verifica": verifica
    }

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config):
        """
        Initialize the Executor.

        Args:
            cfg (Config): Global configuration object with LLM, logger, and paths.
            or_query (str): The original, raw user query.
        """
        self._cfg = cfg
        self._llm = cfg.get_LLM()
        self._logger = cfg.get_logger("Executor")
        self._language: DQLLanguage = cfg.get_DQL()

    # ----------------------
    # --- Public Methods ---
    # ----------------------
    
    def generate(self, operations: list[dict], chat_id) -> tuple[str, dict]:
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
        self._retrieval = Retrieval(self._cfg, chat_id, operations)
        
        for op in operations:
            self._logger.info(f"Executing operation: {op['id']}")
            if "operations" in op:
                for o in op["operations"]:
                    self._logger.info(f"Executing sub-operation: {o}")
                    o["result"] = self._execute(o)
                op["result"] = op["operations"][-1]["result"]
            else:
                op["result"] = self._execute(op)
            
        return operations
    
    def _execute(self, op):
        structured_prompt = op.get("structured_prompt", {})
        command = structured_prompt.get("command", "altro")
        
        # Step 1: Retrieve relevant documents for this operation
        docs = self._retrieval.execute(structured_prompt)
        
        context = self._build_context(docs)
        what = structured_prompt.get("what", [""])
        how = self._format_conditions(structured_prompt.get("how", {}))
        
        self._logger.info(f"Calling '{command}' prompt")
        if command == "altro":
            result = altro("", context, self._cfg.get_LLM(), self._cfg.get_DQL())
        else:
            result = self.FUNCTION_MAP.get(command)(context, what, how, self._cfg.get_LLM(), self._cfg.get_DQL())

        # Format headings in the result (e.g., # -> **)
        return re.sub(self._pattern, self._format_heading, result)

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
            return ""

        # Start of the conditions block
        conditions = ["Tuttavia, l'utente ha posto esplicitamente che la risposta debba soddisfare le seguenti condizioni:"]
        for key, value in how.items():
            if value:
                # Add each valid condition
                conditions.append(f"- Condizione \"{key}\": {value}")

        return "\n".join(conditions) if len(conditions) > 1 else ""

    @staticmethod
    def _build_context(docs: list[dict]) -> str:
        """
        Build a formatted context string from retrieved documents.

        Args:
            docs (list[dict]): List of retrieved document dictionaries.

        Returns:
            str: A single string containing all concatenated document context.
        """
        if not docs:
            return ""
        
        context_lines = []
        
        # Label documents with their source names (e.g., "op_1", "doc_A")
        # This helps the LLM link intermediate results.
        for doc in docs:
            context_lines.append(f"[D. \"{doc['type']}\"]\n\n{doc['text']}\n\n---")
        
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