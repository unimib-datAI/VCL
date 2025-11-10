import queue
import threading

from logic.bot.translator.command_classifier import CommandClassifier
from logic.bot.translator.sources_extractor import SourcesExtractor
from logic.bot.translator.what_extractor import WhatExtractor
from logic.bot.translator.conditions_extractor import ConditionsExtractor

from utils.config import Config


class Translator:
    """
    Translates user queries into a structured format suitable for downstream processing.

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
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Translator")
        self.project_root = cfg.project_root
        self.user_id = cfg.user_id

        # Initialize all sub-components
        self.command_classifier = CommandClassifier(cfg)
        self.sources_extractor = SourcesExtractor(cfg)
        self.what_extractor = WhatExtractor(cfg)
        self.conditions_extractor = ConditionsExtractor(cfg)

    # -----------------------------
    # --- Main Rewriting Method ---
    # -----------------------------
    
    def rewrite(self, query: str) -> dict:
        """
        Rewrite a raw user query into a structured query dictionary.

        Steps:
            1. Classify the query to identify the command.
            2. Extract relevant sources/documents.
            3. Extract the 'what' element.
            4. Extract any additional conditions ('how').
            5. Combine all extracted elements into a structured dictionary.

        Args:
            query (str): Raw input query from the user.

        Returns:
            dict: Structured query containing keys:
                  - 'command': str, command name
                  - 'from': list[str], relevant sources
                  - 'what': str, target content
                  - 'how': dict, additional conditions
        """
        
        # Step 1: Classify command
        result_command = queue.Queue()
        thread1 = threading.Thread(
            target=self.command_classification, args=(query, result_command)
        )
        
        # Step 2 & 3: Extract sources and what
        result_sources_what = queue.Queue()
        thread2 = threading.Thread(
            target=self.sources_what_extractor, args=(query, result_sources_what)
        )
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        sources, from_sources, what = result_sources_what.get()

        # Step 4: Build the structured query
        structured_query = {
            "command": result_command.get().get("name", ""),
            "from": from_sources,
            "what": what,
        }

        # Step 5: Extract additional conditions
        structured_query["how"] = self.conditions_extractor.extract(query, structured_query, sources)

        # Log the final structured query
        self.logger.info(f"Structured query: {structured_query}")

        return structured_query
    
    def command_classification(self, prompt: str, result_queue: queue.Queue):
        command = self.command_classifier.classify(prompt)
        result_queue.put(command)
        
    def sources_what_extractor(self, prompt: str, result_queue: queue.Queue):
        sources = self.sources_extractor.extract(prompt)
        from_sources = [source[0] for source in sources]
        what = self.what_extractor.extract(prompt, from_sources)
        result_queue.put((sources, from_sources, what))
