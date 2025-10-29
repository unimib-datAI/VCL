import os

from bot.utils.config import Config
from bot.utils.DQL_language import DQLlanguage

class SourcesExtractor:
    
    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Translator")
        self.project_root = cfg.project_root
        
        self.dqlLanguage = DQLlanguage(cfg)
    
    def extract(self, query: str) -> dict:
        language_sources = self.sources_string(self.dqlLanguage.sources)
        
        query_dict = {
            "query": query,
            "language_sources": language_sources,
            "number": len(self.dqlLanguage.sources),
            "feedback": ""
        }
        
        documents = []
        
        try:
            if query_dict.get("query", "").strip():
                documents = self.llm.str_in_list(
                    self.llm.invoke_from_file(
                        os.path.join(self.project_root, "documents", "prompts", "rewriting", "4 - ExplicitDocumentsExtraction.json"),
                        query_dict,
                        True
                    )
                )
                
                status = "Done"
            else:
                raise Exception()
        except Exception:
            documents = [src["name"] for src in self.dqlLanguage.sources]
            status = "Error"
        
        self.logger.info(f"Sources Extractor: {documents} - {status}")
        
        return documents
    
    @staticmethod
    def sources_string(sources) -> str:
        """
        Generate a formatted string of available sources.

        Returns:
            str: A formatted string listing all available sources.
        """
        synonyms = [
            f"'{synonym.strip()}'" for src in sources for synonym in src.get("synonyms", [])
        ]
        
        sources_list = [
            f"\t\t- \"{src['name']}\" (o {",".join(synonyms[index])}): {src['description']}"
            for index, src in enumerate(sources)
        ]
        
        if sources_list:
            sources_list = ["\t- \"Documenti Legali\": Questi possono essere soltanto i seguenti:"] + sources_list
            
        return "\n".join(sources_list)