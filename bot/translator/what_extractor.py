import os

from bot.utils.config import Config
from bot.utils.file_manager import read_file

class WhatExtractor:
    
    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Translator")
        self.project_root = cfg.project_root
        
        self.source_what_map, self.definitions = self.retrieve_what()
    
    def extract(self, query: str, sources: str) -> dict:
        language_what = self.what_string(sources)
        
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
        
    def retrieve_what(self) -> list:
        """
        Retrieve the list of available what from the what.json file.

        Returns:
            list: A list of source dictionaries.
        """
        what_path = os.path.join(
            self.project_root,
            "documents",
            "language",
            "what.json"
        )
        what_data = read_file(what_path)
        
        return what_data.get("source-what", {}), what_data.get("definitions", {})
    
    def what_string(self, sources) -> str:
        """
        Generate a formatted string of available what.

        Returns:
            str: A formatted string listing all available what.
        """
        
        # If sources is empty, initialize to an empty set.
        if not sources:
            what_elements = set()
        else:
            # This block now only runs if 'sources' contains at least one item.
            what_elements = set.intersection(
                *[set(self.source_what_map.get(source, [])) for source in sources]
            )
        
        what_list = [
            f"\t- \"{what}\": {self.definitions.get(what, '')}"
            for what in what_elements
        ]
            
        return "\n".join(what_list)