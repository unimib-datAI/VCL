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
        
        self._get_request_id = self._CFG.get_request_id

    # ----------------------
    # --- Public Methods ---
    # ----------------------
    
    def chat(self, prompt: str, user_id: str, chat_id: str, request_id: str = None) -> dict:
        """
        Entry point for processing a user query. Orchestrates the 4-step pipeline.

        Args:
            prompt (str): The user's query.
            user_id (str): The ID of the user initiating the request.
            chat_id (str): The ID of the chat session.

        Returns:
            dict: A comprehensive response object containing:
                - content: The final text answer.
                - details: Technical breakdown (tasks, DQL commands, logs).
                - metadata: Request ID, timestamp, and model used.
        """
        status = {}
        
        request_id = request_id if request_id else self._get_request_id(user_id)
        
        # Lazy initialization of specialized components for the current request
        self._logger = self._CFG.get_logger("Orchestrator", request_id)
        self._preprocessor = Preprocessor(self._CFG, request_id)
        self._translator = Translator(self._CFG, request_id)
        self._planner = Planner(self._CFG, request_id)
        self._executor = Executor(self._CFG, request_id)

        try:
            if not prompt or prompt.strip() == "":
                raise ValueError("No prompt provided in the request status.")
            
            status = {
                "role": "assistant",
                "time": datetime.now().isoformat(),
                "model": "DQL",
                
                "id": request_id,
                
                "ids": {
                    "user": user_id,
                    "session": chat_id,
                    "request": request_id,
                },
                
                "details": {
                    "prompt": prompt
                }
            }
            
            self.user_id = status["ids"]["user"]
            self.session_id = status["ids"]["session"]
            self.request_id = status["ids"]["request"]

            # --- Pipeline Execution Flow ---
            self._logger.info(f"Starting processing for request ID \"{status['id']}\".")
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
            last_result = f"{self.error_msg}: ({e})"
            self._logger.error(f"Processing failed with error: {e}")

        # Finalizing the response object with metadata and technical details
        status["details"].update(
            {
                "prompt_process": prompt_process,
                "tasks": result
            }
        )
        
        status["content"] = last_result
        status["result"] = last_result
        
        self._logger.info(last_result)
        
        # Extract and deduplicate source documents referenced during the process
        used_documents = set()
        available_sources = [src["name"] for src in self._language.get_sources()]
        for task in status["details"]["tasks"]:
            for doc in task.get("structured_prompt", {}).get("from", []):
                if doc in available_sources:
                    used_documents.add(doc)
        
        status["details"]["used_documents"] = list(used_documents)

        return status

    # ------------------------------
    # --- Private Helper Methods ---
    # ------------------------------
    
    def _preprocess(self, prompt: str) -> list:
        """Executes query cleaning and semantic task decomposition."""
        self._logger.info("Starting Preprocessing step.")
        prompt_clean, tasks = self._preprocessor.process(prompt, self.user_id, self.session_id, self.request_id)
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