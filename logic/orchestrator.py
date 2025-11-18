"""
Orchestrator module: orchestrates the DQL pipeline.

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
from copy import deepcopy

from utils.config import Config
from utils.file_manager import FileHandler
from logic.bot.preprocessor.preprocessor import Preprocessor
from logic.bot.translator.translator import Translator
from logic.bot.planner.planner import Planner
from logic.bot.executor.executor import Executor


class Orchestrator:
    """
    Main DQL assistant class that manages the full processing pipeline.
    
    This class initializes all necessary components (logger, preprocessor,
    translator, planner) and manages the flow of data from the initial
    user prompt to the final structured response.
    """

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, username: str = None):
        """
        Initialize the Orchestrator instance.

        Args:
            username (str): The identifier for the user, used to load
                            the correct configuration and storage.
        
        Raises:
            ValueError: If username is not provided.
        """
        # Load global configuration
        if not username:
            raise ValueError("Username must be provided to initialize Orchestrator.")
        
        self._username = username
        self._CFG = Config(username)
        self._storage = self._CFG.storage
        self._language = self._CFG.language

        # Initialize core components
        self._logger = self._CFG.get_logger("Orchestrator")
        self._preprocessor = Preprocessor(self._CFG)
        self._translator = Translator(self._CFG)
        self._planner = Planner(self._CFG)
        
        # The Executor is stateful (depends on the prompt)
        # and will be initialized within the chat() method.
        self._executor = None

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
            dict: Final response containing structured input, operations,
                  results, and used documents.
        """
        # Log the incoming request
        self._logger.info(f"Request Received: \"{prompt}\"")
        
        # Initialize the prompt-specific Executor
        # This component holds prompt-specific state (e.g., original query)
        self._executor = Executor(self._CFG, prompt)

        try:
            # --- Pipeline Execution ---
            prompt_clean = self._preprocess(prompt)
            structured_query = self._translate(prompt_clean)
            operations = self._plan(structured_query)
            result = self._execute(operations)
            # --------------------------
            
        except Exception as e:
            # Handle any failure during the pipeline execution
            self._logger.error("Request processing failed")
            self._logger.exception(e)
            # Define a safe fallback response
            structured_query, operations, result = {}, [], f"Si è verificato un errore. Riprova."

        # Compile and return the final response object
        response = self._finalize_response(prompt, structured_query, operations, result)

        return response
    
    # ---------------
    # --- Getters ---
    # ---------------
    
    def get_storage(self):
        if not self._storage:
            raise ValueError("Empty Storage")
        
        return self._storage
    
    def get_language(self):
        if not self._language:
            raise ValueError("Empty Language")
        
        return self._language
    
    def get_cfg(self):
        if not self._CFG:
            raise ValueError("Empty Config")
        
        return self._CFG

    # ------------------------------
    # --- Private Helper Methods ---
    # ------------------------------
    
    def _preprocess(self, prompt: str) -> str:
        """Run preprocessing pipeline on the user input."""
        self._logger.info("Step 1 (Preprocessing): Starting")
        prompt_clean = self._preprocessor.process(prompt)
        self._logger.info("Step 1 (Preprocessing): Done")
        return prompt_clean

    def _translate(self, prompt: str) -> dict:
        """Translate the cleaned prompt into a structured query."""
        self._logger.info("Step 2 (Translator): Starting")
        structured_query = self._translator.rewrite(prompt)
        # Assign a unique ID to this request
        structured_query["id"] = self._CFG.get_request_id()
        self._logger.info("Step 2 (Translator): Done")
        return structured_query

    def _plan(self, structured_query: dict) -> list[dict]:
        """Decompose structured query into operations."""
        self._logger.info("Step 3 (Planner): Starting")
        # Use deepcopy to ensure the original structured_query is not
        # mutated by the planner (e.g., if it pops keys).
        operations = self._planner.decompose(deepcopy(structured_query))
        self._logger.info("Step 3 (Planner): Done")
        return operations

    def _execute(self, operations: list[dict]) -> str:
        """Execute all planned operations and generate final result."""
        final_result = ""
        for index, operation in enumerate(operations):
            self._logger.info(
                f"Executing operation ID: {operation.get('id', '')} "
                f"with command: {operation.get('command', '')}"
            )
            self._logger.info("Step 4 (Executor): Starting")
            operation["order"] = index
            # The executor generates the result for the current operation
            operation["result"], _ = self._executor.generate(operation, operations)
            # The final result is the result of the last operation
            final_result = operation["result"]
            self._logger.info("Step 4 (Executor): Done")
            
        self._logger.info("Request Completed")
        return final_result

    def _finalize_response(self, prompt: str, structured_query: dict, operations: list[dict], result: str) -> dict:
        """Prepare the final response structure including used documents."""
        response = {
            "id": self._CFG.get_request_id(),
            "structured_input": structured_query,
            "input": prompt,
            "operations": operations,
            "result": result
        }

        # Aggregate all documents used across all operations
        used_docs = [doc for op in operations for doc in op.get("from", [])]
        # Store only unique document identifiers
        response["used_documents"] = list(set(used_docs))
        return response

    def store_response(self, response: dict):
        """
        Persist the response in storage (e.g., Redis) and local filesystem.

        Args:
            response (dict): The final response object to store.
        """
        try:
            # Cache the response in remote storage (e.g., Redis) for 1 hour
            self._storage.set_documents(response, ttl=3600)
        except Exception:
            self._logger.warning("Document not saved in remote storage (e.g., Redis)")
            
        # Also save a copy to the local filesystem
        id = response.get("id", "")
        file_path = os.path.join(self._CFG.project_root, "documents", f"{id}.json")
        FileHandler().write_file(file_path, response)
