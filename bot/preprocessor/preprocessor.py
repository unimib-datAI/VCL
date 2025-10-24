from bot.preprocessor.spelling_checker import SpellingChecker
from bot.utils.config import Config

class Preprocessor:
    """
    Preprocessing pipeline for user queries.
    """
    
    def __init__(self, cfg: Config):
        """
        Initialize the Preprocessor class.

        Args:
            cfg (Config): The global configuration instance containing logger
                          and other settings.
        """
        
        self.logger = cfg.get_logger("Preprocessor")
        
        self.spelling_checker = SpellingChecker(cfg)

    def process(self, query: str) -> str:
        """
        Runs the preprocessing pipeline on the query.
        """
        # 1. Spell Correction
        query = self.spelling_checker.correct_text_llm(query)
        
        self.logger.info(f"Preprocessing: {query}")

        return query.lower()