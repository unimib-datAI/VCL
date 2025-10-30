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
        command = self.command_classifier.classify(query)

        # Step 2: Extract relevant sources
        sources = self.sources_extractor.extract(query)

        # Step 3: Extract 'what' element
        what = self.what_extractor.extract(query, sources)

        # Step 4: Build the structured query
        structured_query = {
            "command": command["name"],
            "from": sources,
            "what": what,
        }

        # Step 5: Extract additional conditions
        structured_query["how"] = self.conditions_extractor.extract(query, structured_query)

        # Log the final structured query
        self.logger.info(f"Structured query: {structured_query}")

        return structured_query
