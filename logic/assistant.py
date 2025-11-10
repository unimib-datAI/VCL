"""
Assistant module: orchestrates the DQL pipeline.

Responsibilities:
-----------------
- Preprocess user queries.
- Translate queries into structured commands.
- Plan operations from structured queries.
- Execute operations using document retrieval and LLM.
- Log all steps and store final results for session tracking.

Dependencies:
-------------
- utils.config.Config: Global configuration and logger.
- utils.file_manager.FileHandler: Save/retrieve JSON results.
- logic.bot.preprocessor.Preprocessor: Query preprocessing.
- logic.bot.translator.Translator: Translate query to structured commands.
- logic.bot.planner.Planner: Decompose commands into operations.
- logic.bot.executor.Executor: Execute operations and generate results.
"""

import os
import socket
from copy import deepcopy
from datetime import datetime, timezone

from utils.config import Config
from utils.file_manager import FileHandler
from logic.bot.preprocessor.preprocessor import Preprocessor
from logic.bot.translator.translator import Translator
from logic.bot.planner.planner import Planner
from logic.bot.executor.executor import Executor


class Assistant:
    """
    Main DQL assistant class that manages the full processing pipeline.
    """

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config = None):
        """
        Initialize the Assistant instance.

        Args:
            cfg (Config): Global configuration object
        """
        # Load global configuration
        self.CFG = cfg

    # ----------------------
    # --- Public Methods ---
    # ----------------------
    
    def chat(self, prompt: str) -> dict:
        """
        Process a user query through the full DQL pipeline.

        Steps:
            1. Preprocessing
            2. Translation to structured query
            3. Planning operations
            4. Executing operations and generating results

        Args:
            prompt (str): The user's input query.

        Returns:
            dict: Final response containing structured input, operations, results, and used documents.
        """
        # Initialize logger
        self.logger = self.CFG.get_logger("Assistant")
        self.logger.info(f"Request Received: \"{prompt}\"")
        
        # Initialize pipeline components
        self.preprocessor = Preprocessor(self.CFG)
        self.translator = Translator(self.CFG)
        self.planner = Planner(self.CFG)
        self.executor = Executor(self.CFG)

        try:
            prompt_clean = self._preprocess(prompt)
            structured_query = self._translate(prompt_clean)
            operations = self._plan(structured_query)
            result = self._execute(operations)
        except Exception as e:
            self.logger.error("Request processing failed")
            self.logger.exception(e)
            structured_query, operations, result = {}, [], "Si è verificato un errore. Riprova."

        response = self._finalize_response(prompt, structured_query, operations, result)

        return response

    # ------------------------------
    # --- Private Helper Methods ---
    # ------------------------------
    
    def _preprocess(self, prompt: str) -> str:
        """Run preprocessing pipeline on the user input."""
        self.logger.info("Step 1 (Preprocessing): Starting")
        prompt_clean = self.preprocessor.process(prompt)
        self.logger.info("Step 1 (Preprocessing): Done")
        return prompt_clean

    def _translate(self, prompt: str) -> dict:
        """Translate the cleaned prompt into a structured query."""
        self.logger.info("Step 2 (Translator): Starting")
        structured_query = self.translator.rewrite(prompt)
        structured_query["id"] = self.CFG.get_request_id()
        self.logger.info("Step 2 (Translator): Done")
        return structured_query

    def _plan(self, structured_query: dict) -> list[dict]:
        """Decompose structured query into operations."""
        self.logger.info("Step 3 (Planner): Starting")
        operations = self.planner.decompose(deepcopy(structured_query))
        self.logger.info("Step 3 (Planner): Done")
        return operations

    def _execute(self, operations: list[dict]) -> str:
        """Execute all planned operations and generate final result."""
        final_result = ""
        for index, operation in enumerate(operations):
            self.logger.info(
                f"Executing operation ID: {operation.get('id', '')} "
                f"with command: {operation.get('command', '')}"
            )
            self.logger.info("Step 4 (Executor): Starting")
            operation["order"] = index
            operation["result"], _ = self.executor.generate(operation, operations)
            final_result = operation["result"]
            self.logger.info("Step 4 (Executor): Done")
        self.logger.info("Request Completed")
        return final_result

    def _finalize_response(self, prompt: str, structured_query: dict, operations: list[dict], result: str) -> dict:
        """Prepare the final response structure including used documents."""
        response = {
            "id": self.CFG.get_request_id(),
            "structured_input": structured_query,
            "input": prompt,
            "operations": operations,
            "result": result
        }

        # Aggregate all documents used across operations
        used_docs = [doc for op in operations for doc in op.get("from", [])]
        response["used_documents"] = list(set(used_docs))
        return response

    def store_response(self, response: dict):
        """Persist the response in storage and local filesystem."""
        try:
            self.CFG.storage.set_documents(response, ttl=3600)  # Cache for 1 hour
        except Exception:
            self.logger.warning("Document not saved in storage")
            
        id = response.get("id", "")
        file_path = os.path.join(self.CFG.project_root, "documents", f"{id}.json")
        FileHandler().write_file(file_path, response)
