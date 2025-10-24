import os

from bot.utils.config import Config

class ConditionsExtractor:
    
    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Translator")
        self.project_root = cfg.project_root
    
    def extract(self, query: str, query_str: dict) -> dict:
        query_dict = {
            "query": query,
            "query_str": str(query_str),
            "feedback": "",
            "what": query_str.get("what", "")
        }
        
        conditions = {}
        
        try:
            if query_dict.get("query", "").strip():
                conditions = self.llm.str_in_dict(
                    self.llm.invoke_from_file(
                        os.path.join(self.project_root, "documents", "prompts", "rewriting", "7 - AdditionalConditionsExtraction.json"),
                        query_dict,
                        True
                    )
                )
                
                status = "Done"
            else:
                raise Exception()
        except Exception:
            conditions = {}
            status = "Error"
        
        self.logger.info(f"Conditions Extractor: {conditions} - {status}")
        
        return conditions