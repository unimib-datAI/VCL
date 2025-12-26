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
from datetime import datetime

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
    
    error_msg = "Si è verificato un errore. Riprova."
    
    def __init__(self, cfg: Config):
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
        self._CFG = cfg
        
        self._storage = self._CFG.get_storage()
        self._language = self._CFG.get_DQL()

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
        self._executor = Executor(self._CFG)
        
        response = {
            "role": "assistant",
            "time": datetime.now().isoformat(),
            "id": self._CFG.get_request_id(),
            "model": "DQL"
        }

        try:
            # --- Pipeline Execution ---
            self._logger.info(f"Starting processing for request ID \"{response['id']}\".")
            self._logger.info(f"Request received \"{prompt}\".")
            
            prompt_process, tasks = self._preprocess(prompt)
            structured_tasks = self._translate(tasks)
            structured_tasks = self._plan(structured_tasks)
            result, last_result = self._execute(structured_tasks)
            
            self._logger.info(f"Processing completed correctly.")
        except Exception as e:
            # Define a safe fallback response
            prompt_process = prompt
            result = []
            last_result = self.error_msg
            
            self._logger.info(f"Processing failed with error: {e}")

        response["details"] = {}
        response["details"]["prompt"] = prompt
        response["details"]["prompt_process"] = prompt_process
        response["details"]["tasks"] = result
        
        response["content"] = last_result
        response["result"] = last_result
        
        used_documents = set()
        available_sources = [src["name"] for src in self._language.get_sources()]
        for task in response["details"]["tasks"]:
            for doc in task.get("structured_prompt", {}).get("from", []):
                if doc in available_sources:
                    used_documents.add(doc)
        
        response["details"]["used_documents"] = list(used_documents)

        return response

    # ------------------------------
    # --- Private Helper Methods ---
    # ------------------------------
    
    def _preprocess(self, prompt: str) -> list:
        """Run preprocessing pipeline on the user input."""
        self._logger.info("Starting Preprocessing step.")
        prompt_clean, tasks = self._preprocessor.process(prompt)
        self._logger.info("Preprocessing step completed.")
        return prompt_clean, tasks

    def _translate(self, prompts: list) -> list:
        """Translate the prompts into structured queries."""
        self._logger.info("Starting Translation step.")
        structured_queries = self._translator.rewrite(prompts)
        self._logger.info("Translation step completed.")
        return structured_queries

    def _plan(self, structured_query: dict) -> list[dict]:
        """Decompose structured query into operations."""
        self._logger.info("Starting Planning step.")
        operations = self._planner.decompose(deepcopy(structured_query))
        self._logger.info("Planning step completed.")
        return operations

    def _execute(self, operations: list[dict]) -> str:
        """Execute all planned operations and generate final result."""
        if len(operations) < 1:
            raise Exception("Tasks not found")
        
        self._logger.info("Starting Execution step.")
        results = self._executor.generate(deepcopy(operations))
        self._logger.info("Execution step completed.")
            
        return results, results[-1].get("result", self.error_msg)

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
            raise Exception("Document not saved in remote storage.")
            
        # Also save a copy to the local filesystem
        id = response.get("id", "")
        file_path = os.path.join(self._CFG.project_root, "documents", f"{id}.json")
        FileHandler().write_file(file_path, response)
