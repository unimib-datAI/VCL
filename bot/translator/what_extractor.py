import os

from bot.utils.config import Config
from bot.utils.DQL_language import DQLlanguage

class WhatExtractor:
    
    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Translator")
        self.project_root = cfg.project_root
        
        self.dqlLanguage = DQLlanguage(cfg.storage)
    
    def extract(self, query: str, sources: str) -> dict:
        language_what = self.what_string(self.dqlLanguage.get_available_what(sources))
        
        query_dict = {
            "query": query,
            "language_what": language_what,
            "feedback": ""
        }
        
        what = ""
        
        try:
            if query_dict.get("query", "").strip():
                what = self.llm.invoke_from_file(
                    os.path.join(self.project_root, "documents", "prompts", "rewriting", "6 - WhatExtraction.json"),
                    query_dict,
                    True
                )
                
                status = "Done"
            else:
                raise Exception()
        except Exception:
            what = "intero documento"
            status = "Error"
        
        self.logger.info(f"What Extractor: {what} - {status}")
        
        return what
    
    @staticmethod
    def what_string(what_elements) -> str:
        """
        Generate a formatted string of available what.

        Returns:
            str: A formatted string listing all available what.
        """
        
        what_list = [
            f"\t- \"{what[0]}\": {what[1]}"
            for what in what_elements
        ]
            
        return "\n".join(what_list)