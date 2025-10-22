from bot.translator.command_classifier import CommandClassifier
from bot.translator.sources_extractor import SourcesExtractor
from bot.translator.what_extractor import WhatExtractor
from bot.translator.conditions_extractor import ConditionsExtractor

from bot.utils.config import Config

class Translator:
    def __init__(self, cfg: Config):
        """
        Initialize the Rewriting class.

        Args:
            cfg (Config): The global configuration instance containing logger
                          and other settings.
        """
        # Initialize the Graph and logger
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Rewriting")
        self.project_root = cfg.project_root
        self.user_id = cfg.user_id
        
        self.command_classifier = CommandClassifier(cfg)
        self.sources_extractor = SourcesExtractor(cfg)
        self.what_extractor = WhatExtractor(cfg)
        self.conditions_extractor = ConditionsExtractor(cfg)

    def rewrite(self, query: str) -> dict:
        command = self.command_classifier.classify(query)
        sources = self.sources_extractor.extract(query)
        
        what = self.what_extractor.extract(
            query,
            sources
        )
        
        structured_query = {
            "command": command["name"],
            "from": sources,
            "what": what,
        }
        
        structured_query["how"] = self.conditions_extractor.extract(
            query,
            structured_query
        )
        
        # Return the structured rewritten response
        return structured_query
