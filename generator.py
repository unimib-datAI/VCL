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
import time
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from utils.config import Config
from utils.file_manager import read_file


class Generator:
    """
    Class responsible for generating LLM responses using prompts and retrieved documents.

    Attributes:
        path (str): Directory path where prompt templates are stored.
        llm: The initialized LLM instance from Config.
        rag (bool): Whether to use Retrieval-Augmented Generation.
        seconds (int): Delay (in seconds) after each LLM call.
        parsers (StrOutputParser): Output parser for extracting raw text from LLM responses.
        logger: Logger instance for structured logging.
    """

    def __init__(self, cfg: Config):
        """
        Initialize the Generator with configuration settings.

        Args:
            cfg (Config): Shared configuration object providing LLM, logger, etc.
        """
        self.llm = cfg.llm
        self.rag = cfg.rag
        self.seconds = cfg.seconds
        self.parsers = StrOutputParser()
        self.logger = cfg.logger
        self.project_root = cfg.project_root
        # Path to the directory containing generator prompt templates
        self.path = os.path.join(self.project_root, "prompts", "generator")

    def generate(self, op: dict, docs: list[dict], query: str) -> str:
        """
        Generate a response based on an operation, retrieved documents, and user query.

        Workflow:
        1. Logs start of generation.
        2. Handles special case where the entire document is requested directly.
        3. Loads the appropriate prompt template for the operation.
        4. Dynamically appends conditions if present.
        5. Constructs the context from retrieved documents.
        6. Builds and runs the LangChain prompt → LLM → parser chain.
        7. Logs results, waits the configured delay, and returns output.

        Args:
            op (dict): Operation definition (contains command, what, how, etc.).
            docs (list[dict]): List of retrieved documents for context.
            query (str): User’s input query.

        Returns:
            str: Generated response text from the LLM.
        """
        self.logger.info(
            json.dumps(
                {
                    "step": "Generator.generate",
                    "action": "start",
                    "operation": op,
                    "user_query": query,
                    "num_docs": len(docs),
                }
            )
        )

        # Special case: request for the entire document (bypass LLM)
        if (op["command"] in ["estrai", "cerca"]) and op["what"][
            "name"
        ] == "intero documento":
            result = "\n\n".join([d["text"] for d in docs]).strip()
            self.logger.info(
                json.dumps(
                    {
                        "step": "Generator.generate",
                        "action": "direct_return",
                        "reason": "full_document",
                        "result_length": len(result),
                    }
                )
            )
            return result

        # Load the template corresponding to the operation
        template = read_file(os.path.join(self.path, f"{op['command']}.json"))
        template["system"] = "\n".join(template["system"])
        template["human"] = "\n".join(template["human"])

        # Add any "how" conditions (constraints) if present
        conditions = ""
        if op.get("how", {}):
            conditions = "\nInoltre la risposta deve rispettare le seguenti condizioni:"
            for condition, value in op["how"].items():
                if value:
                    conditions += f"\n- Condizione {condition}: {value}"

        if conditions.strip() and not conditions.endswith(":"):
            template["system"] += f"\n{conditions}"

        # Build context string from retrieved documents
        context = ""
        for index, doc in enumerate(docs):
            context += f"[Document {index + 1}]\n\n{doc}\n\n"

        # Construct the prompt → LLM → parser chain
        prompt = ChatPromptTemplate.from_messages(
            [("system", template["system"]), ("human", template["human"])]
        )
        chain = prompt | self.llm | self.parsers

        # Run the chain with query and context
        result = chain.invoke({"query": query, "context": context})
        self.logger.info(
            json.dumps(
                {
                    "step": "Generator.generate",
                    "action": "llm_invoked",
                    "result_preview": result[:200],  # Only log preview for readability
                }
            )
        )

        # Apply configured delay before finishing
        time.sleep(self.seconds)

        self.logger.info(
            json.dumps(
                {
                    "step": "Generator.generate",
                    "action": "end",
                    "result_length": len(result),
                }
            )
        )
        return result
