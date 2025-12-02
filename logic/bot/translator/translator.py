import queue
import threading

from copy import deepcopy

from logic.bot.translator.command_classifier import CommandClassifier
from logic.bot.translator.sources_extractor import SourcesExtractor
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
        self._llm = cfg.llm
        self._logger = cfg.get_logger("Translator")
        self._project_root = cfg.project_root
        self._user_id = cfg.get_user_id()

        # Initialize all sub-components
        self._command_classifier_class = CommandClassifier(cfg)
        self._sources_extractor_class = SourcesExtractor(cfg)
        self._what_extractor_class = WhatExtractor(cfg)
        self._conditions_extractor_class = ConditionsExtractor(cfg)

    # -----------------------------
    # --- Main Rewriting Method ---
    # -----------------------------
    
    def rewrite(self, prompts: list, user_id, chat_id: str) -> dict:
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
        
        # Create queues to receive results from threads
        result_command = queue.Queue()
        result_sources = queue.Queue()
        result_what = queue.Queue()
        result_conditions = queue.Queue()

        # Step 1: (Thread 1) Classify command
        thread1 = threading.Thread(
            target=self._command_classification, args=(deepcopy(prompts), result_command)
        )
        
        # Step 2: (Thread 2) Extract sources
        thread2 = threading.Thread(
            target=self._sources_extractor, args=(deepcopy(prompts), user_id, chat_id, result_sources)
        )
        
        # Start parallel execution
        thread1.start()
        thread2.start()
        
        thread2.join()
        
        sources = result_sources.get()
        for i, source in enumerate(sources):
            prompts[i]["from"] = source
            prompts[i]["structured_prompt"] = {}
            prompts[i]["structured_prompt"]["from"] = [s[0] for s in source]
            
        # Step 3: (Thread 3) Extract What
        thread3 = threading.Thread(
            target=self._what_extractor, args=(deepcopy(prompts), result_what)
        )
        
        thread3.start()
        
        # Wait for others threads to finish
        thread1.join()
        thread3.join()
        
        # Retrieve results from queues
        command = result_command.get()
        what = result_what.get()
        
        for i in range(len(command)):
            prompts[i]["structured_prompt"]["command"] = command[i]
            prompts[i]["structured_prompt"]["what"] = what[i]

        thread4 = threading.Thread(
            target=self._conditions_extractor, args=(prompts, result_conditions)
        )
        
        thread4.start()
        thread4.join()
        
        how = result_conditions.get()
        
        for i in range(len(how)):
            prompts[i]["structured_prompt"]["how"] = how[i]
            del prompts[i]["from"]

        return prompts
    
    # -----------------------------------
    # --- Private Threading Functions ---
    # -----------------------------------

    def _command_classification(self, prompts: list, result_queue: queue.Queue):
        """
        Thread target function to run command classification.
        Places the result dictionary into the provided queue.

        Args:
            prompt (str): The user query.
            result_queue (queue.Queue): The queue to store the result.
        """
        try:
            result = [
                self._command_classifier_class.classify(prompt.get('prompt', ''))
                for prompt in prompts
            ]
        except Exception:
            result = ["altro"] * len(prompts)
        
        result_queue.put(result)
        
    def _sources_extractor(self, prompts: list, user_id, chat_id, result_queue: queue.Queue):
        """
        Thread target function to run sources extraction.
        Places a tuple of (sources, from_sources, what) into the queue.

        Args:
            prompt (str): The user query.
            result_queue (queue.Queue): The queue to store the results tuple.
        """
        result_sources = []
        
        try:
            ids = sorted([t.get('id', '') for t in prompts])
            
            for t in prompts:
                sources = self._sources_extractor_class.extract(t.get("prompt", ''), user_id, chat_id, ids)
                result_sources.append(sources)
        except Exception as e:
            result_sources = [["", ""]] * len(prompts)
            self._logger.error(f"{e}")
            
        result_queue.put(result_sources)

    def _what_extractor(self, prompts: list, result_queue: queue.Queue):
        """
        Thread target function to run sources and 'what' extraction.
        Places a tuple of (sources, from_sources, what) into the queue.

        Args:
            prompt (str): The user query.
            result_queue (queue.Queue): The queue to store the results tuple.
        """
        result_what = []
        
        try:
            result_what = [
                self._what_extractor_class.extract(t.get("prompt", ''), t.get("from", []))
                for t in prompts
            ]
                
        except Exception:
            result_what = ["altro"] * len(prompts)
            
        result_queue.put(result_what)
        
    def _conditions_extractor(self, prompts: list, result_queue: queue.Queue):
        result_how = []
        
        try:
            
            for t in prompts:
                sources = self._conditions_extractor_class.extract(
                    t.get("prompt", ''),
                    t.get("structured_prompt", {}),
                    t.get("from", [])
                )
                
                result_how.append(sources)
                
        except Exception:
            result_how = [{}] * len(prompts)
            
        result_queue.put(result_how)