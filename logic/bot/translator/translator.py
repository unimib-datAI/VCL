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
    Translates natural language tasks into a structured DQL format.

    This class orchestrates specialized extractors to populate the 'command', 'from', 
    'what', and 'how' components of a query. It utilizes a multi-threaded approach 
    to process these extractions in parallel, significantly reducing the overall 
    latency of the translation pipeline.

    Responsibilities:
        - Coordinating parallel execution of extraction sub-components.
        - Mapping raw user prompts to the structured DQL grammar.
        - Synchronizing results from multiple threads into a coherent task list.
        - Handling fallback logic for individual extraction failures.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the Translator with shared configuration and sub-components.

        Args:
            cfg (Config): Global configuration instance providing access to 
                          LLM services, loggers, and language definitions.
        """
        self._logger = cfg.get_logger("Translator")

        # Instantiate specialized extraction classes
        self._sources_extractor_class = SourcesExtractor(cfg)
        self._command_classifier_class = CommandClassifier(cfg)
        self._what_extractor_class = WhatExtractor(cfg)
        self._conditions_extractor_class = ConditionsExtractor(cfg)

    # -----------------------------
    # --- Main Rewriting Method ---
    # -----------------------------
    
    def rewrite(self, tasks: list) -> list:
        """
        Transforms a list of raw tasks into structured DQL commands.

        The process is optimized using a tiered threading strategy:
        1. Sources are extracted first as they provide context for 'what' and 'how'.
        2. Command classification and 'What' extraction run in parallel.
        3. 'How' extraction runs last to capture constraints based on the full context.

        Args:
            tasks (list): A list of dictionaries, each containing at least a 'prompt' key.

        Returns:
            list: The updated list of tasks with a 'structured_prompt' containing:
                  - 'command': The identified intent.
                  - 'from': The relevant document sources.
                  - 'what': The specific target object or section.
                  - 'how': Optional filters or logical constraints.
        """
        
        if not tasks or not isinstance(tasks, list):
            raise ValueError("Input tasks must be a non-empty list.")
        
        # Result queues for thread communication
        result_command = queue.Queue()
        result_from = queue.Queue()
        result_what = queue.Queue()
        result_how = queue.Queue()
        
        # --- PHASE 1: Source Extraction ---
        # This is high-priority as sources define the scope for subsequent steps
        thread_from = threading.Thread(
            target=self._from, args=(deepcopy(tasks), result_from)
        )
        
        self._logger.info("Starting sources extraction threading...")
        thread_from.start()
        thread_from.join() # Synchronous wait required for source context
        self._logger.info("Sources extraction threading completed.")
        
        from_parameters = result_from.get()
        if not from_parameters or len(from_parameters) != len(tasks):
            raise ValueError("Inconsistency detected in source extraction results.")
        
        # Mapping extracted sources back to tasks
        for i in range(len(from_parameters)):
            tasks[i]["from"] = from_parameters[i]
            tasks[i]["structured_prompt"]["from"] = [p[0] for p in from_parameters[i]] 
        
        # --- PHASE 2: Parallel Intent & Content Extraction ---
        # Command classification and 'What' extraction are independent and can run concurrently
        thread_command = threading.Thread(
            target=self._command, args=(deepcopy(tasks), result_command)
        )
        
        thread_what = threading.Thread(
            target=self._what, args=(deepcopy(tasks), result_what)
        )
        
        self._logger.info("Starting parallel command and 'what' extraction...")
        thread_command.start()
        thread_what.start()
        
        # Wait for both independent threads to finish
        thread_command.join()
        self._logger.info("Command classification completed.")
        thread_what.join()
        self._logger.info("'What' extraction completed.")
        
        command_parameters = result_command.get()
        if not command_parameters or len(command_parameters) != len(tasks):
            raise ValueError("Inconsistency detected in command classification results.")
        
        what_parameters = result_what.get()
        if not what_parameters or len(what_parameters) != len(tasks):
            raise ValueError("Inconsistency detected in 'what' extraction results.")
        
        # Update tasks with parallel results
        for i in range(len(command_parameters)):
            if "altro" == command_parameters[i] or "altro" in what_parameters[i]:
                raise ValueError("Detected 'altro' in command or 'what' extraction, indicating failure.")
            
            tasks[i]["structured_prompt"]["command"] = command_parameters[i]
            tasks[i]["structured_prompt"]["what"] = what_parameters[i]
        
        # --- PHASE 3: Conditional Constraints ('How') ---
        # Final extraction to capture filters based on the fully structured command
        thread_how = threading.Thread(
            target=self._how, args=(deepcopy(tasks), result_how)
        )
        
        self._logger.info("Starting 'how' extraction threading...")
        thread_how.start()
        thread_how.join()
        self._logger.info("'How' extraction completed.")
        
        how_parameters = result_how.get()
        if not how_parameters or len(how_parameters) != len(tasks):
            raise ValueError("Inconsistency detected in 'how' extraction results.")
        
        # Final cleanup and structuring
        for i in range(len(command_parameters)):
            if how_parameters[i]:
                tasks[i]["structured_prompt"]["how"] = how_parameters[i]
                # Clean up temporary field used for context passing
                if "from" in tasks[i]:
                    del tasks[i]["from"]

        return tasks
    
    # -----------------------------------
    # --- Private Threading Functions ---
    # -----------------------------------

    def _command(self, tasks: list, result_queue: queue.Queue):
        """Thread target: executes intent classification for all tasks."""
        result = []
        try:
            for t in tasks:
                if "command" not in t.get("structured_prompt", {}):
                    result.append(self._command_classifier_class.classify(t.get('prompt', '')))
                else:
                    result.append(t["structured_prompt"]["command"])
        except Exception as e:
            self._logger.error(f"Thread Error (Command): {e}")
            result = ["altro"] * len(tasks) # Fallback to generic command
        
        result_queue.put(result)
        
    def _from(self, tasks: list, result_queue: queue.Queue):
        """Thread target: executes source/document identification for all tasks."""
        result = []
        try:
            ids = sorted([t.get('id', '') for t in tasks])
            
            for t in tasks:
                if "from" not in t.get("structured_prompt", {}):
                    result.append(self._sources_extractor_class.extract(t.get("prompt", ''), ids))
                else:
                    result.append(t["structured_prompt"]["from"])
        except Exception as e:
            self._logger.error(f"Thread Error (Sources): {e}")
            result = [[]] * len(tasks)
            
        result_queue.put(result)

    def _what(self, tasks: list, result_queue: queue.Queue):
        """Thread target: identifies the specific content target ('what') for all tasks."""
        result = []
        
        try:
            for t in tasks:
                if "what" not in t.get("structured_prompt", {}):
                    result.append(self._what_extractor_class.extract(t.get("prompt", ''), t.get("from", [])))
                else:
                    result.append(t["structured_prompt"]["what"])
        except Exception as e:
            self._logger.error(f"Thread Error (What): {e}")
            result = ["intero documento"] * len(tasks) # Safe fallback
            
        result_queue.put(result)
        
    def _how(self, tasks: list, result_queue: queue.Queue):
        """Thread target: extracts constraints and logical filters ('how') for all tasks."""
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
            self._logger.error(f"Thread Error (How): {e}")
            result_how = [{}] * len(tasks)
            
        result_queue.put(result_how)