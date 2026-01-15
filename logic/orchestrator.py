"""
Orchestrator module: coordinates the multi-stage DQL pipeline.

The pipeline follows a linear flow to transform natural language into legal insights:
1. Preprocessing: Cleaning and task identification.
2. Translation: Mapping tasks to structured DQL commands.
3. Planning: Decomposing commands into atomic operations.
4. Execution: Document retrieval and LLM generation.


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
    Main DQL assistant engine that manages the full processing pipeline.
    
    This class acts as the central hub, initializing specialized components 
    and ensuring data consistency as it moves through the preprocessing, 
    translation, planning, and execution phases.
    """

    # Default error message for UI fallback
    error_msg = "Non sono in grado di rispondere alla tua richiesta in questo momento."
    
    def __init__(self, cfg: Config):
        """
        Initialize the Orchestrator with global configurations.

        Args:
            cfg (Config): The global configuration instance containing 
                          storage references and logging settings.
        """
        self._CFG = cfg
        
        # Access persistent storage and language definitions via configuration
        self._storage = self._CFG.get_storage()
        self._language = self._CFG.get_DQL()

    # ----------------------
    # --- Public Methods ---
    # ----------------------
    
    def chat(self, prompt: str) -> dict:
        """
        Entry point for processing a user query. Orchestrates the 4-step pipeline.

        Args:
            prompt (str): The raw natural language query from the user.

        Returns:
            dict: A comprehensive response object containing:
                - content: The final text answer.
                - details: Technical breakdown (tasks, DQL commands, logs).
                - metadata: Request ID, timestamp, and model used.
        """
        # Lazy initialization of specialized components for the current request
        self._logger = self._CFG.get_logger("Orchestrator")
        self._preprocessor = Preprocessor(self._CFG)
        self._translator = Translator(self._CFG)
        self._planner = Planner(self._CFG)
        self._executor = Executor(self._CFG)
        
        # Structure the base response object
        response = {
            "role": "assistant",
            "time": datetime.now().isoformat(),
            "id": self._CFG.get_request_id(),
            "model": "DQL"
        }

        try:
            # --- Pipeline Execution Flow ---
            self._logger.info(f"Starting processing for request ID \"{response['id']}\".")
            self._logger.info(f"Request received \"{prompt}\".")
            
            # Step 1: Clean input and split into logical tasks
            prompt_process, tasks = self._preprocess(prompt)
            
            # Step 2: Map tasks to structured DQL (JSON-like commands)
            structured_tasks = self._translate(tasks)
            
            # Step 3: Break down complex commands into atomic executable operations
            structured_tasks = self._plan(structured_tasks)
            
            # Step 4: Execute RAG (Retrieval Augmented Generation) and merge results
            result, last_result = self._execute(structured_tasks)
            
            self._logger.info(f"Processing completed correctly.")
        
        except Exception as e:
            # Critical error handling: provide a safe fallback for the UI
            prompt_process = prompt
            result = []
            last_result = self.error_msg
            self._logger.error(f"Processing failed with error: {e}")

        # Finalizing the response object with metadata and technical details
        response["details"] = {
            "prompt": prompt,
            "prompt_process": prompt_process,
            "tasks": result
        }
        
        response["content"] = last_result
        response["result"] = last_result
        
        self._logger.info(last_result)
        
        # Extract and deduplicate source documents referenced during the process
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
        """Executes query cleaning and semantic task decomposition."""
        self._logger.info("Starting Preprocessing step.")
        prompt_clean, tasks = self._preprocessor.process(prompt)
        self._logger.info("Preprocessing step completed.")
        return prompt_clean, tasks

    def _translate(self, prompts: list) -> list:
        """Converts natural language tasks into the structured DQL format."""
        self._logger.info("Starting Translation step.")
        structured_queries = self._translator.rewrite(prompts)
        self._logger.info("Translation step completed.")
        return structured_queries

    def _plan(self, structured_query: dict) -> list[dict]:
        """Determines the operational flow for complex cross-document queries."""
        self._logger.info("Starting Planning step.")
        operations = self._planner.decompose(deepcopy(structured_query))
        self._logger.info("Planning step completed.")
        return operations

    def _execute(self, operations: list[dict]) -> str:
        """Coordinates retrieval and LLM generation for all planned operations."""
        if len(operations) < 1:
            raise Exception("Tasks not found during execution phase.")
        
        self._logger.info("Starting Execution step.")
        results = self._executor.generate(deepcopy(operations))
        self._logger.info("Execution step completed.")
            
        # Returns the full list of results and the specific final generated text
        return results, results[-1].get("result", self.error_msg)

    def store_response(self, response: dict):
        """
        Persists the final response in both remote storage (Redis) and local JSON files.

        Args:
            response (dict): The complete response object generated by the chat method.
        """
        try:
            # Cache the response for 1 hour for quick retrieval in the UI
            self._storage.set_documents(response, ttl=3600)
        except Exception:
            self._logger.error("Failed to persist document in remote storage.")
            raise Exception("Document not saved in remote storage.")
            
        # File-based persistence for audit and long-term tracking
        request_id = response.get("id", "unknown")
        file_path = os.path.join(self._CFG.project_root, "documents", f"{request_id}.json")
        FileHandler().write_file(file_path, response)