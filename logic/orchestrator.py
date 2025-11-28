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

import itertools
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
    
    def __init__(self, username: str = None, role: str = "Altro"):
        """
        Initialize the Orchestrator instance.

        Args:
            username (str): The identifier for the user, used to load
                            the correct configuration and storage.
            role (str):     The role of the user, used to load the correct
                            header of Generator prompt
            
        Raises:
            ValueError: If username is not provided.
        """
        # Load global configuration
        if not username:
            raise ValueError("Username must be provided to initialize Orchestrator.")
        
        self._username = username
        self._CFG = Config(username, role)
        
        self._storage = self._CFG.storage
        self._language = self._CFG.language

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
        # Initialize core components
        self._logger = self._CFG.get_logger("Orchestrator")
        self._preprocessor = Preprocessor(self._CFG)
        self._translator = Translator(self._CFG)
        self._planner = Planner(self._CFG)
        self._executor = Executor(self._CFG, prompt)
        
        # Log the incoming request
        self._logger.info(f"Request Received: \"{prompt}\"")
        
        response = {
            "id": self._CFG.get_request_id(),
            "prompt": prompt
        }

        try:
            # --- Pipeline Execution ---
            
            tasks = self._preprocess(prompt)
            structured_tasks = self._translate(tasks)
            # operations = self._plan(structured_tasks)
            result, last_result = self._execute(structured_tasks)
            
            # --------------------------
        except Exception as e:
            # Handle any failure during the pipeline execution
            self._logger.error(f"Request processing failed: {e}")
            
            # Define a safe fallback response
            structured_tasks = []
            last_result = f"Si è verificato un errore. Riprova."

        response["tasks"] = result
        response["result"] = last_result
        
        self._logger.info("Request Completed")

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
    
    def _preprocess(self, prompt: str) -> list:
        """Run preprocessing pipeline on the user input."""
        self._logger.info("Step 1 (Preprocessing): Starting")
        prompt_clean = self._preprocessor.process(prompt)
        self._logger.info("Step 1 (Preprocessing): Done")
        return prompt_clean

    def _translate(self, tasks: list) -> list:
        """Translate the prompts into structured queries."""
        self._logger.info("Step 2 (Translator): Starting")
        structured_queries = self._translator.rewrite(tasks)    
        self._logger.info("Step 2 (Translator): Done")
        return structured_queries

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
        for index, operation in enumerate(operations):
            operation_input = operation.get("structured_prompt", {})
            self._logger.info("Step 4 (Executor): Starting")
            # The executor generates the result for the current operation
            operation["order"] = index
            operation["result"], _ = self._executor.generate(operation_input, operations)
            self._logger.info("Step 4 (Executor): Done")
        
        if len(operations) < 1:
            raise Exception("Tasks not found")
            
        return operations, operations[-1].get("result", "")

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
