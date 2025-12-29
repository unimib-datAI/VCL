from spellchecker import SpellChecker
from utils.config import Config


class SpellingChecker:
    """
    Provides text correction capabilities using either a traditional rule-based 
    spell checker or an LLM-based rewriting system for advanced contextual correction.

    This component acts as a pre-processing filter to ensure that user queries 
    are grammatically correct and free of typos before they reach the DQL translation engine.

    Responsibilities:
        - Toggle between basic spell checking and advanced LLM-based rewriting.
        - Handle Italian language specific corrections.
        - Ensure robust fallback to original text in case of processing errors.
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
        self._llm = cfg.get_LLM()
        self._project_root = cfg.project_root
        
        # Initialize the rule-based spell checker for the Italian language
        self._spell = SpellChecker(language="it")
        self._dql_language = cfg.get_DQL()
        
        self._logger = cfg.get_logger("Spelling Checker")
        
        # Flag to determine the correction strategy: 
        # True for basic (pyspellchecker), False for advanced (LLM)
        self._parsers = cfg.parsers
        
    # ------------------------
    # --- General Function ---
    # ------------------------
    
    def correct_spelling(self, text: str) -> str:
        """
        Orchestrates the spelling correction process based on the active parser strategy.

        Steps:
            1. Validate input text integrity.
            2. Dispatch to either _correct_text_basic or _correct_text_llm.
            3. Handle exceptions by returning the original uncorrected text.

        Args:
            text (str): The raw input text to verify.

        Returns:
            str: The corrected version of the text.
        """
        
        if not text or not isinstance(text, str):
            raise Exception("Received empty or invalid query during spelling check.")
        
        status = "Error"
        try:
            if self._parsers:
                # Rule-based approach using Levenshtein distance/frequency dictionaries
                self._logger.info("Executing Basic Correction (pyspellchecker)")
                corrected_query = self._correct_text_basic(text)
            else:
                # Contextual approach using Large Language Model capabilities
                self._logger.info("Executing Advanced Correction (LLM)")
                corrected_query = self._correct_text_llm(text)
                
            status = "Done"
        except Exception as e:
            # Fallback mechanism: maintain the original query to prevent pipeline interruption
            self._logger.error(f"Spelling correction failed: {e}")
            corrected_query = text  
        
        # Final audit log for request traceability
        self._logger.info(f"Correction Result: \"{corrected_query}\" - Status: {status}")
        return corrected_query
        
    # ----------------------------
    # --- Basic Spell Checking ---
    # ----------------------------
    
    def _correct_text_basic(self, text: str) -> str:
        """
        Applies word-by-word correction using the pyspellchecker library.

        Args:
            text (str): Input text for lexical correction.

        Returns:
            str: The text reconstructed with correctly spelled words.
        """
        # Tokenize the input text into individual words
        words = text.lower().split()

        # Iterate through tokens and apply the most likely correction for each
        corrected_words = [self._spell.correction(word) for word in words]
        
        # Join words back together, filtering out any failed correction attempts (None)
        result = " ".join(filter(None, corrected_words))

        return result

    # ----------------------------
    # --- LLM-Based Correction ---
    # ----------------------------
    
    def _correct_text_llm(self, text: str) -> str:
        """
        Uses an LLM to rewrite the input text, focusing on grammar and context.

        This method is preferred for complex queries where word-by-word 
        correction might lose the semantic meaning of the sentence.

        Args:
            text (str): Input text for contextual rewriting.

        Returns:
            str: The rewritten text provided by the LLM.
        """
        # Load the specific prompt template from the DQL language configuration
        prompt = self._dql_language.prompts.get("CorrectionQuery.json", None)
            
        if not prompt:
            raise ValueError("Required prompt 'CorrectionQuery.json' not found.")
        
        # Request the LLM to perform a high-fidelity rewrite of the user's query
        result = self._llm.invoke(
            prompt,
            { "query": text },
            True # Setting structured output mode to True
        )

        return result