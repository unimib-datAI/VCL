import queue
import threading

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
        self._command_classifier = CommandClassifier(cfg)
        self._sources_extractor = SourcesExtractor(cfg)
        self._what_extractor = WhatExtractor(cfg)
        self._conditions_extractor = ConditionsExtractor(cfg)

    # -----------------------------
    # --- Main Rewriting Method ---
    # -----------------------------
    
    def rewrite(self, query: str) -> dict:
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
        result_sources_what = queue.Queue()

        # Step 1: (Thread 1) Classify command
        thread1 = threading.Thread(
            target=self._command_classification, args=(query, result_command)
        )
        
        # Step 2 & 3: (Thread 2) Extract sources and what
        thread2 = threading.Thread(
            target=self._sources_what_extractor, args=(query, result_sources_what)
        )
        
        # Start parallel execution
        thread1.start()
        thread2.start()
        
        # Wait for both threads to finish
        thread1.join()
        thread2.join()
        
        # Retrieve results from queues
        sources, from_sources, what = result_sources_what.get()
        command_result = result_command.get()

        # Step 4: Build the initial structured query
        structured_query = {
            "command": command_result.get("name", ""),
            "from": from_sources,
            "what": what,
        }

        # Step 5: Extract additional conditions
        structured_query["how"] = self._conditions_extractor.extract(query, structured_query, sources)

        # Log the final structured query
        self._logger.info(f"Structured query: {structured_query}")

        return structured_query
    
    # -----------------------------------
    # --- Private Threading Functions ---
    # -----------------------------------

    def _command_classification(self, prompt: str, result_queue: queue.Queue):
        """
        Thread target function to run command classification.
        Places the result dictionary into the provided queue.

        Args:
            prompt (str): The user query.
            result_queue (queue.Queue): The queue to store the result.
        """
        try:
            command = self._command_classifier.classify(prompt)
            result_queue.put(command)
        except Exception as e:
            self._logger.error(f"Command classification thread failed: {e}")
            # Provide a fallback value to prevent queue.get() from blocking
            result_queue.put({"name": "error"})

    def _sources_what_extractor(self, prompt: str, result_queue: queue.Queue):
        """
        Thread target function to run sources and 'what' extraction.
        Places a tuple of (sources, from_sources, what) into the queue.

        Args:
            prompt (str): The user query.
            result_queue (queue.Queue): The queue to store the results tuple.
        """
        try:
            sources = self._sources_extractor.extract(prompt)
            from_sources = [source[0] for source in sources]
            what = self._what_extractor.extract(prompt, from_sources)
            result_queue.put((sources, from_sources, what))
        except Exception as e:
            self._logger.error(f"Sources/What extraction thread failed: {e}")
            # Provide fallback values
            result_queue.put(([], [], "error"))