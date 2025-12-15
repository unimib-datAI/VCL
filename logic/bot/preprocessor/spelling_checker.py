from spellchecker import SpellChecker
from utils.config import Config


class SpellingChecker:
    """
    Provides text correction capabilities using either a traditional spell
    checker or an LLM-based rewriting system for advanced grammar and
    phrasing correction.

    Responsibilities:
        - Detect and correct spelling errors using a rule-based spell checker.
        - Optionally refine text using a language model prompt for contextual
          rewriting.

    Attributes:
        _llm (LLM): Reference to the application's language model (from Config).
        _project_root (Path): Root path of the project.
        _spell (SpellChecker): Instance of the pyspellchecker library.
        _logger: Logger instance from Config.
        _spell_check_without_llm (bool): Flag to select correction method.
        _dql_language: Language-specific settings (like prompts) from Config.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the SpellingChecker with configuration and resources.

        Args:
            cfg (Config): The global configuration object providing access to
                          the LLM instance, paths, and language settings.
        """
        self._llm = cfg.llm
        self._project_root = cfg.project_root
        # Initialize spell checker for Italian
        self._spell = SpellChecker(language="it")
        self._dql_language = cfg.language
        
        self._logger = cfg.get_logger("Spelling Checker")
        self._spell_check_without_llm = cfg.spell_check_without_llm
        
    # ------------------------
    # --- General Function ---
    # ------------------------
    
    def correct_spelling(self, text: str) -> str:
        """
        Corrects the spelling of the input text using the configured method.

        Args:
            text (str): The input text to correct.

        Returns:
            str: The corrected text.
        """
        
        if not text or not isinstance(text, str):
            raise Exception("Received empty or invalid query during spelling check.")
        
        status = "Error"
        try:
            if self._spell_check_without_llm:
                self._logger.info("Spelling Correction with pyspellchecker")
                corrected_query = self._correct_text_basic(text)
            else:
                self._logger.info("Spelling Correction with LLM")
                corrected_query = self._correct_text_llm(text)
                
            status = "Done"
        except Exception as e:
            self._logger.error(f"Error during spelling correction: {e}")
            corrected_query = text  # Fallback to original text on error
        
        # Log the final query for traceability
        self._logger.info(f"{corrected_query} - {status}")
        return corrected_query
        
    # ----------------------------
    # --- Basic Spell Checking ---
    # ----------------------------
    
    def _correct_text_basic(self, text: str) -> str:
        """
        Perform a basic spell correction on the provided text using pyspellchecker.

        Args:
            text (str): Input text to correct.

        Returns:
            tuple[str, str]: A tuple containing the corrected text and a
                             status string ("Done" or "Error").
        """
        words = text.lower().split()

        # Correct each word individually
        corrected_words = [self._spell.correction(word) for word in words]
        
        # filter(None, ...) removes potential None results if correction fails
        result = " ".join(filter(None, corrected_words))

        return result

    # ----------------------------
    # --- LLM-Based Correction ---
    # ----------------------------
    
    def _correct_text_llm(self, text: str) -> str:
        """
        Perform advanced text correction using the configured LLM model.

        This method leverages a prompt template to guide the LLM
        to rewrite the input text with improved spelling and grammar.

        Args:
            text (str): Input text to correct contextually.

        Returns:
            tuple[str, str]: A tuple containing the corrected (rewritten)
                             text and a status string ("Done" or "Error").
        """
        # Retrieve the specific prompt for query correction
        prompt = self._dql_language.prompts.get("CorrectionQuery.json", None)
            
        if not prompt:
            raise ValueError("Error during prompt retrieval")
        
        # Invoke LLM to rewrite the query based on the prompt
        result = self._llm.invoke(
            prompt,
            { "query": text },
            True
        )

        return result