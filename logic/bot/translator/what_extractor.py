from utils.config import Config
from utils.DQL_language import DQLLanguage

class WhatExtractor:
    """
    Extracts the 'what' elements (specific targets or content) from a user query
    based on available sources using an LLM.

    This class serves as a semantic filter that identifies specific entities, 
    sections, or data points requested by the user, ensuring they are valid 
    within the context of the selected document sources.

    Responsibilities:
        - Filtering valid 'what' elements based on active document sources.
        - Constructing context-aware LLM prompts for entity extraction.
        - Validating LLM outputs against the defined DQL grammar.
        - Managing fallbacks (e.g., "altro", "intero documento") for failed extractions.
    """

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config):
        """
        Initialize the WhatExtractor with configuration and dependencies.

        Args:
            cfg (Config): Global configuration object providing logger, LLM engine,
                          and DQL language definitions.
        """
        self._llm = cfg.get_LLM()
        self._logger = cfg.get_logger("What Extractor")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.get_DQL()

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def extract(self, query: str, sources: list[str]) -> list[str]:
        """
        Extract the 'what' element from a user query given the selected sources.

        The process follows a validation-heavy pipeline:
            1. Fetch valid 'what' entities allowed for the selected sources.
            2. Prompt the LLM to map user intent to these specific entities.
            3. Sanitize the result by checking for existence in the grammar.
            4. Default to generic categories if the LLM output is non-compliant.

        Args:
            query (str): User input query to analyze.
            sources (list[str]): List of relevant document names associated with the query.

        Returns:
            list[str]: A list of extracted 'what' identifiers or a default fallback list.
        """
        # Retrieve the dictionary of valid 'what' elements specific to the active sources
        available_what = [w.lower() for w in self._dql_language.get_available_what(sources)]
        language_what_str = self._what_string(
            available_what
        )

        # Prepare the input payload for the LLM injection
        query_dict = {
            "query": query,
            "what": language_what_str
        }

        what = []
        status = "Error"  # Default status for traceability

        try:
            # Load the system prompt specifically designed for 'what' entity extraction
            prompt = self._dql_language.prompts.get("WhatExtraction.json", None)
            
            if not prompt:
                raise ValueError("WhatExtraction.json prompt template not found.")
            
            # Input sanity check: ignore empty queries
            if query_dict.get("query", "").strip():
                # Invoke LLM with the prompt template and dynamic 'what' list
                # Setting result format to True to ensure structured parsing
                what = self._llm.invoke(
                    prompt,
                    query_dict,
                    True
                )
                
                # Validation: ensure every extracted term exists in the current grammar
                for i, w in enumerate(what):
                    if w not in available_what and w != "altro" and w != "intero documento":
                        self._logger.warning(f"What Extractor Validation: \"{w}\" not in available what.")
                        what[i] = "intero documento"
                
                status = "Done"
            else:
                raise ValueError("Empty query string provided.")

        except Exception as e:
            # Fallback Logic: Default to 'altro' (other) to maintain pipeline execution
            self._logger.error(f"What extraction execution failed: {e}")
            what = ["altro"]

        # Log the final mapping for audit purposes
        self._logger.info(
            f"Extraction mapping: \"{query}\" -> {what} (Status: {status})"
        )
        
        return what

    # ----------------------
    # --- Helper Methods ---
    # ----------------------
    
    @staticmethod
    def _what_string(what_list: dict) -> str:
        """
        Serializes a dictionary of 'what' elements into a formatted string for prompts.

        Args:
            what_list (dict): Dictionary mapping entity names to their definitions.

        Returns:
            str: A bulleted string listing all available targets and their meanings.
        """
        return "\n".join(f"- \"{item}\": {what_list[item]}" for item in what_list)