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
        self._decomposer = Decomposer(cfg)

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
            self._logger.warning("Received empty or invalid query during preprocessing.")
            return ""

        # Step 1: Correct spelling and grammar using the LLM-based correction module
        corrected_query = self._spelling_checker.correct_spelling(query)

        # Step 2: Normalize casing
        normalized_query = corrected_query.lower()

        # Log the preprocessed query for traceability
        self._logger.info(f"Normalized query: {normalized_query}")
        
        # Step 3: Division in step
        task_list = self._decomposer.decompose(normalized_query)

        return task_list