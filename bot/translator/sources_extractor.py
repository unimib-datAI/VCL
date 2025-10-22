import os

from bot.utils.config import Config
from bot.utils.file_manager import read_file

class SourcesExtractor:
    
    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Translator")
        self.project_root = cfg.project_root
        
        self.sources = self.retrieve_sources()
    
    def extract(self, query: str) -> dict:
        language_sources = self.sources_string()
        
        query_dict = {
            "query": query,
            "language_sources": language_sources,
            "number": len(self.sources),
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
            documents = [src["name"] for src in self.sources]
            status = "Error"
        
        self.logger.info(f"Sources Extractor: {documents} - {status}")
        
        return documents
        
    def retrieve_sources(self) -> list:
        """
        Retrieve the list of available sources from the sources.json file.

        Returns:
            list: A list of source dictionaries.
        """
        sources_path = os.path.join(
            self.project_root,
            "documents",
            "language",
            "sources.json"
        )
        sources_data = read_file(sources_path)
        
        return sources_data.get("sources", [])
    
    def sources_string(self) -> str:
        """
        Generate a formatted string of available sources.

        Returns:
            str: A formatted string listing all available sources.
        """
        synonyms = [
            f"'{synonym.strip()}'" for src in self.sources for synonym in src.get("synonyms", [])
        ]
        
        sources_list = [
            f"\t\t- \"{src['name']}\" (o {",".join(synonyms[index])}): {src['description']}"
            for index, src in enumerate(self.sources)
        ]
        
        if sources_list:
            sources_list = ["\t- \"Documenti Legali\": Questi possono essere soltanto i seguenti:"] + sources_list
            
        return "\n".join(sources_list)