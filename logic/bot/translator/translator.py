import queue
import threading

from copy import deepcopy

from logic.bot.translator.sources_extractor import SourcesExtractor
from logic.bot.translator.command_classifier import CommandClassifier
from logic.bot.translator.what_extractor import WhatExtractor
from logic.bot.translator.conditions_extractor import ConditionsExtractor

from utils.config import Config


class Translator:
    """
    Translates user queries into a structured format suitable for downstream
    processing.

    This class runs multiple extraction components in parallel (threading)
    to optimize performance and reduce latency.

    Responsibilities:
        - Classify the user's intent into a command.
        - Identify relevant sources/documents.
        - Determine the 'what' element (specific target/content).
        - Extract additional conditions or constraints.
        - Return a fully structured query dictionary.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the Translator with configuration and dependencies.

        Args:
            cfg (Config): Global configuration instance providing LLM, logger,
                          project paths, and DQL language data.
        """
        self._logger = cfg.get_logger("Translator")

        # Initialize all sub-components
        self._sources_extractor_class = SourcesExtractor(cfg)
        self._command_classifier_class = CommandClassifier(cfg)
        self._what_extractor_class = WhatExtractor(cfg)
        self._conditions_extractor_class = ConditionsExtractor(cfg)

    # -----------------------------
    # --- Main Rewriting Method ---
    # -----------------------------
    
    def rewrite(self, tasks: list) -> dict:
        """
        Rewrite a raw user query into a structured query dictionary.

        This method runs command classification and source/what extraction
        in parallel threads to reduce latency.

        Steps:
            1. (Thread 1) Classify the query to identify the command.
            2. (Thread 2) Extract relevant sources/documents.
            3. (Thread 2) Extract the 'what' element based on the query.
            4. (Main) Wait for parallel threads to complete.
            5. (Main) Extract any additional conditions ('how').
            6. (Main) Combine all elements into a structured dictionary.

        Args:
            query (str): Raw input query from the user.

        Returns:
            dict: Structured query containing keys:
                  - 'command': str, command name
                  - 'from': list[str], relevant sources
                  - 'what': str, target content
                  - 'how': dict, additional conditions
        """
        
        if not tasks or not isinstance(tasks, list):
            raise ValueError("Input tasks must be a non-empty list.")
        
        # Create queues to receive results from threads
        result_command = queue.Queue()
        result_from = queue.Queue()
        result_what = queue.Queue()
        result_how = queue.Queue()
        
        # Step 1: (Thread 1) Source Extraction
        thread_from = threading.Thread(
            target=self._from, args=(deepcopy(tasks), result_from)
        )
        
        self._logger.info("Starting sources extraction threading...")
        thread_from.start()
        thread_from.join()
        self._logger.info("Sources extraction threading completed.")
        
        from_parameters = result_from.get()
        if not from_parameters or len(from_parameters) != len(tasks):
            raise ValueError("Error in source extraction threading.")
        
        for i in range(len(from_parameters)):
            tasks[i]["from"] = from_parameters[i]
            tasks[i]["structured_prompt"]["from"] = [p[0] for p in from_parameters[i]] 
        
        # Step 2: (Thread 2) Classify command
        thread_command = threading.Thread(
            target=self._command, args=(deepcopy(tasks), result_command)
        )
        
        self._logger.info("Starting command classification threading...")
        thread_command.start()
        
        # Step 3: (Thread 3) What Extraction
        thread_what = threading.Thread(
            target=self._what, args=(deepcopy(tasks), result_what)
        )
        
        self._logger.info("Starting 'what' extraction threading...")
        thread_what.start()
        
        thread_command.join()
        self._logger.info("Command classification threading completed.")
        thread_what.join()
        self._logger.info("'What' extraction threading completed.")
        
        command_parameters = result_command.get()
        if not command_parameters or len(command_parameters) != len(tasks):
            raise ValueError("Error in command classification threading.")
        
        what_parameters = result_what.get()
        if not what_parameters or len(what_parameters) != len(tasks):
            raise ValueError("Error in what extraction threading.")
        
        for i in range(len(command_parameters)):
            tasks[i]["structured_prompt"]["command"] = command_parameters[i]
            tasks[i]["structured_prompt"]["what"] = what_parameters[i]
        
        # Step 4: (Thread 4) How Extraction
        thread_how = threading.Thread(
            target=self._how, args=(deepcopy(tasks), result_how)
        )
        
        self._logger.info("Starting 'how' extraction threading...")
        thread_how.start()
        thread_how.join()
        self._logger.info("'How' extraction threading completed.")
        
        how_parameters = result_how.get()
        if not how_parameters or len(how_parameters) != len(tasks):
            raise ValueError("Error in how extraction threading.")
        
        for i in range(len(command_parameters)):
            if how_parameters[i]:
                tasks[i]["structured_prompt"]["how"] = how_parameters[i]
                del tasks[i]["from"]  # Clean up to avoid redundancy

        return tasks
    
    # -----------------------------------
    # --- Private Threading Functions ---
    # -----------------------------------

    def _command(self, tasks: list, result_queue: queue.Queue):
        """
        Thread target function to run command classification.

        Args:
            prompt (str): The user query.
            result_queue (queue.Queue): The queue to store the result.
        """
        try:
            result = [
                self._command_classifier_class.classify(t.get('prompt', ''))
                for t in tasks
            ]
        except Exception as e:
            self._logger.error("Command classification failed: " + str(e))
            result = ["altro"] * len(tasks)
        
        result_queue.put(result)
        
    def _from(self, tasks: list, result_queue: queue.Queue):
        """
        Thread target function to run sources extraction.

        Args:
            prompt (str): The user query.
            result_queue (queue.Queue): The queue to store the results tuple.
        """
        try:
            ids = sorted([t.get('id', '') for t in tasks])
            result_sources = [
                self._sources_extractor_class.extract(
                    t.get("prompt", ''),
                    ids
                )
                for t in tasks
            ]
        except Exception as e:
            self._logger.error("Sources extraction failed: " + str(e))
            result_sources = [[]] * len(tasks)
            
        result_queue.put(result_sources)

    def _what(self, tasks: list, result_queue: queue.Queue):
        """
        Thread target function to run 'what' extraction.

        Args:
            prompt (str): The user query.
            result_queue (queue.Queue): The queue to store the results tuple.
        """
        try:
            result_what = [
                self._what_extractor_class.extract(t.get("prompt", ''), t.get("from", []))
                for t in tasks
            ]
        except Exception as e:
            self._logger.error("What extraction failed: " + str(e))
            result_what = [["altro"]] * len(tasks)
            
        result_queue.put(result_what)
        
    def _how(self, tasks: list, result_queue: queue.Queue):
        """
        Thread target function to run 'conditions' extraction.

        Args:
            prompt (list): The user tasks.
            result_queue (queue.Queue): The queue to store the results tuple.
        """
        
        try:
            result_how = [
                self._conditions_extractor_class.extract(
                    t.get("prompt", ''),
                    t.get("structured_prompt", {}),
                    t.get("from", [])
                ) 
                for t in tasks
            ]
        except Exception as e:
            self._logger.error("Conditions extraction failed: " + str(e))
            result_how = [{}] * len(tasks)
            
        result_queue.put(result_how)