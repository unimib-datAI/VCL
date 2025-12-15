from logic.bot.preprocessor.spelling_checker import SpellingChecker
from logic.bot.preprocessor.decomposer import Decomposer
from utils.config import Config


class Preprocessor:
    """
    Handles preprocessing of user queries before passing them to the assistant.

    Responsibilities:
        - Apply spelling and grammar correction.
        - Normalize text for consistent downstream processing.
        - Log preprocessing actions for debugging and traceability.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the Preprocessor with configuration and dependencies.

        Args:
            cfg (Config): Global configuration instance providing logger,
                          LLM instance, and project paths.
        """
        self._logger = cfg.get_logger("Preprocessor")
        self._spelling_checker = SpellingChecker(cfg)
        self._decomposer_class = Decomposer(cfg)

    # -----------------------------------
    # --- Main Preprocessing Pipeline ---
    # -----------------------------------
    
    def process(self, query: str) -> list:
        """
        Execute the preprocessing pipeline on the given user query.

        The current implementation performs:
            1. Spell and grammar correction via LLM.
            2. Lowercasing for normalization.
            3. Decomposition in tasks

        Args:
            query (str): Raw input query from the user.

        Returns:
            list: Preprocessed query, corrected, normalized and divided in tasks.
        """
        if not query or not isinstance(query, str):
            raise Exception("Received empty or invalid query during preprocessing.")

        # Step 1: Correct spelling and grammar using the LLM-based correction module
        self._logger.info("Starting spelling and grammar correction.")
        corrected_query = self._spelling_checker.correct_spelling(query)
        self._logger.info("Spelling and grammar correction completed.")

        # Step 2: Normalize casing
        normalized_query = corrected_query.lower()
        
        # Step 3: Decompose prompt in tasks
        self._logger.info("Starting query decomposition into tasks.")
        prompts = self._decomposer_class.decompose(normalized_query)
        self._logger.info("Query decomposition completed.")

        return prompts